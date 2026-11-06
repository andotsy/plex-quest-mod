"""Optional, authenticated download of the exact supported Plex Horizon build."""
import json
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

from .build import MAX_INPUT_SIZE, require_native_libraries
from .profiles import HORIZON_2026_18


PLEX_META_APP_ID = "1136900442841511"
GRAPHQL_URL = "https://graph.oculus.com/graphql"
DOWNLOAD_URL = "https://securecdn.oculus.com/binaries/download/"
MAX_METADATA_SIZE = 1024 * 1024
# Public Store metadata credential, published by OculusGraphQLApiLib. It is not
# an account credential. Only the APK download needs META_ACCESS_TOKEN.
STORE_METADATA_TOKEN = "OC|752908224809889|"
VERSION_LIST_DOCUMENT = "2885322071572384"


class MetaDownloadError(ValueError):
    """A deliberately sanitized error: never include a token, URL, or response body."""


class MetaRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        host = (parsed.hostname or "").lower()
        domains = ("oculus.com", "oculuscdn.com", "fbcdn.net", "fbsbx.com", "meta.com")
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or parsed.port not in (None, 443)
                or not any(host == domain or host.endswith("." + domain) for domain in domains)):
            raise MetaDownloadError("Meta returned an unexpected download redirect. Use a manual APK URL instead.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = build_opener(MetaRedirectHandler())


def _open(request: Request, stage: str):
    try:
        return OPENER.open(request, timeout=60)
    except HTTPError as error:
        status = error.code
        error.close()
        if stage == "APK download" and status in (400, 401, 403):
            raise MetaDownloadError(
                f"Meta rejected the APK download (HTTP {status}). Refresh META_ACCESS_TOKEN and make sure Plex is in "
                "that account's Quest library, or use a manual APK URL."
            ) from None
        raise MetaDownloadError(f"Meta {stage} returned HTTP {status}. Retry or use a manual APK URL.") from None
    except MetaDownloadError:
        raise
    except Exception:
        # urllib errors can contain the full credential-bearing URL.
        raise MetaDownloadError(f"Could not contact Meta during {stage}. Retry or use a manual APK URL.") from None


def _resolve_binary() -> str:
    # A registered version-list query is supported by the public Store API. An
    # inline app_binary_info query can be rejected even with a valid user token.
    fields = {
        "access_token": STORE_METADATA_TOKEN,
        "doc_id": VERSION_LIST_DOCUMENT,
        "variables": json.dumps({"applicationID": PLEX_META_APP_ID}),
    }
    request = Request(GRAPHQL_URL, data=urlencode(fields).encode("utf-8"), method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "OculusGraphQLApiLib/1.0",
    })
    try:
        with _open(request, "build lookup") as response:
            raw = response.read(MAX_METADATA_SIZE + 1)
        if len(raw) > MAX_METADATA_SIZE:
            raise MetaDownloadError("Meta returned an oversized build lookup response.")
        result = json.loads(raw)
        if result.get("errors") or result.get("error"):
            raise MetaDownloadError(
                "Meta's public build lookup failed. Retry or use a manual APK URL. "
                "The account token has not been used yet."
            )
        app = result["data"]["node"]
        if app.get("id") != PLEX_META_APP_ID:
            raise MetaDownloadError("Meta returned an unexpected app in the build lookup.")
        binaries = set()
        for binary in app["primary_binaries"]["nodes"]:
            binary_id = str(binary.get("id", ""))
            if (binary.get("__typename") == "AndroidBinary"
                    and binary.get("version") == HORIZON_2026_18.version
                    and str(binary.get("version_code")) == str(HORIZON_2026_18.version_code)
                    and binary_id.isascii() and binary_id.isdecimal() and len(binary_id) <= 30):
                binaries.add(binary_id)
        if len(binaries) != 1:
            raise MetaDownloadError(
                f"Meta did not return a unique Plex {HORIZON_2026_18.label} build. "
                "Use a manual APK URL; newer releases are not substituted."
            )
        return binaries.pop()
    except MetaDownloadError:
        raise
    except Exception:
        raise MetaDownloadError("Meta returned an unexpected build lookup response. Use a manual APK URL.") from None


def download_meta(destination: Path) -> Path:
    token = os.environ.get("META_ACCESS_TOKEN", "").strip()
    if not token:
        raise MetaDownloadError("Add the META_ACCESS_TOKEN repository secret for Meta downloads, or choose a manual APK URL.")
    if "\r" in token or "\n" in token:
        raise MetaDownloadError("META_ACCESS_TOKEN must contain just the token on one line.")
    print(f"Looking up Plex {HORIZON_2026_18.label} in Meta Store metadata...", flush=True)
    binary_id = _resolve_binary()
    print(f"Downloading supported Plex binary {binary_id}...", flush=True)
    request = Request(DOWNLOAD_URL + "?" + urlencode({"id": binary_id, "access_token": token}), headers={
        "User-Agent": "OculusGraphQLApiLib/1.0",
    })
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as target:
            temporary = Path(target.name)
            total = 0
            with _open(request, "APK download") as response:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_INPUT_SIZE:
                        raise MetaDownloadError("Meta APK exceeds the 512 MiB input limit.")
                    target.write(chunk)
        with ZipFile(temporary) as archive:
            if not {"AndroidManifest.xml", "assets/index.android.bundle"}.issubset(archive.namelist()):
                raise MetaDownloadError("Meta did not return a complete Plex APK. Refresh the token or use a manual APK URL.")
        require_native_libraries([temporary])
        temporary.replace(destination)
        return destination
    except MetaDownloadError:
        raise
    except (BadZipFile, ValueError):
        raise MetaDownloadError("Meta did not return a complete ARM64 Plex APK. Refresh the token or use a manual APK URL.") from None
    except Exception:
        raise MetaDownloadError("The Meta APK download could not be completed. Retry or use a manual APK URL.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
