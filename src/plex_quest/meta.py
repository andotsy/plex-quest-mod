"""Optional, authenticated download of the exact supported Plex Horizon build."""
import json
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

from . import ORIGINAL_PACKAGE
from .build import MAX_INPUT_SIZE, require_native_libraries
from .profiles import HORIZON_2026_18


PLEX_META_APP_ID = "1136900442841511"
GRAPHQL_URL = "https://graph.oculus.com/graphql"
DOWNLOAD_URL = "https://securecdn.oculus.com/binaries/download/"
MAX_METADATA_SIZE = 1024 * 1024
# This lookup requests a version code, never the moving "latest" release.
# Protocol reference: ComputerElite/OculusGraphQLApiLib, GraphQLClient.GetAssetFiles.
BINARY_QUERY = """query ($params: AppBinaryInfoArgs!) {
  app_binary_info(args: $params) {
    info { binary { ... on OculusBinary { id package_name version_code } } }
  }
}"""


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


def _open(request: Request):
    try:
        return OPENER.open(request, timeout=60)
    except HTTPError as error:
        status = error.code
        error.close()
        if status in (400, 401, 403):
            raise MetaDownloadError(
                "Meta rejected the request. Refresh META_ACCESS_TOKEN and make sure Plex is in "
                "that account's Quest library, or use a manual APK URL."
            ) from None
        raise MetaDownloadError(f"Meta download service returned HTTP {status}. Retry or use a manual APK URL.") from None
    except MetaDownloadError:
        raise
    except Exception:
        # urllib errors can contain the full credential-bearing URL.
        raise MetaDownloadError("Could not contact Meta. Retry or use a manual APK URL.") from None


def _resolve_binary(token: str) -> str:
    fields = {
        "access_token": token,
        "doc_id": "",
        "doc": BINARY_QUERY,
        "variables": json.dumps({"params": {"app_params": [{
            "app_id": PLEX_META_APP_ID,
            "version_code": str(HORIZON_2026_18.version_code),
        }]}}),
    }
    request = Request(GRAPHQL_URL, data=urlencode(fields).encode("utf-8"), method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "OculusGraphQLApiLib/1.0",
    })
    try:
        with _open(request) as response:
            raw = response.read(MAX_METADATA_SIZE + 1)
        if len(raw) > MAX_METADATA_SIZE:
            raise MetaDownloadError("Meta returned an oversized build lookup response.")
        result = json.loads(raw)
        if result.get("errors") or result.get("error"):
            raise MetaDownloadError(
                "Meta could not look up the supported Plex build. Refresh META_ACCESS_TOKEN and "
                "check that Plex is in your Quest library, or use a manual APK URL."
            )
        entries = result["data"]["app_binary_info"]["info"]
        binaries = set()
        for entry in entries:
            binary = entry.get("binary") or {}
            binary_id = str(binary.get("id", ""))
            if (binary.get("package_name") == ORIGINAL_PACKAGE
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
    binary_id = _resolve_binary(token)
    request = Request(DOWNLOAD_URL + "?" + urlencode({"id": binary_id, "access_token": token}), headers={
        "User-Agent": "OculusGraphQLApiLib/1.0",
    })
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as target:
            temporary = Path(target.name)
            total = 0
            with _open(request) as response:
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
