"""Find and download a patchable Plex build from the Meta Horizon Store."""
import json
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

from .build import MAX_INPUT_SIZE, UnsupportedAPK, probe_horizon_apk, require_native_libraries, tool
from .profiles import BuildProfile, PROFILES


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


@dataclass(frozen=True)
class MetaBinary:
    id: str
    version: str
    code: int

    @property
    def label(self) -> str:
        return f"{self.version} ({self.code})"


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


def _resolve_binaries() -> tuple[list[MetaBinary], set[MetaBinary]]:
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
        latest, binaries = set(), set()
        for binary in app["primary_binaries"]["nodes"]:
            binary_id = str(binary.get("id", ""))
            version = str(binary.get("version", ""))
            code = str(binary.get("version_code", ""))
            if (binary.get("__typename") != "AndroidBinary" or not re.fullmatch(r"[0-9]{1,30}", binary_id)
                    or not re.fullmatch(r"[0-9]{1,4}(\.[0-9]{1,4}){2}", version)
                    or not re.fullmatch(r"[0-9]{1,10}", code)):
                continue
            candidate = MetaBinary(binary_id, version, int(code))
            binaries.add(candidate)
            channels = (binary.get("binary_release_channels") or {}).get("nodes") or []
            if any(channel.get("channel_name") == "LIVE" for channel in channels):
                latest.add(candidate)
        return sorted(latest, key=lambda binary: binary.code, reverse=True), binaries
    except MetaDownloadError:
        raise
    except Exception:
        raise MetaDownloadError("Meta returned an unexpected build lookup response. Use a manual APK URL.") from None


def _download_binary(binary: MetaBinary, token: str, destination: Path) -> None:
    request = Request(DOWNLOAD_URL + "?" + urlencode({"id": binary.id, "access_token": token}), headers={
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
                        raise UnsupportedAPK("Meta APK exceeds the 512 MiB input limit.")
                    target.write(chunk)
        with ZipFile(temporary) as archive:
            if not {"AndroidManifest.xml", "assets/index.android.bundle"}.issubset(archive.namelist()):
                raise UnsupportedAPK("The store APK is missing its manifest or Hermes bundle.")
        try:
            require_native_libraries([temporary])
        except ValueError as error:
            raise UnsupportedAPK(str(error)) from None
        temporary.replace(destination)
    except (MetaDownloadError, UnsupportedAPK):
        raise
    except (BadZipFile, ValueError):
        raise MetaDownloadError("Meta did not return a complete ARM64 Plex APK. Refresh the token or use a manual APK URL.") from None
    except Exception:
        raise MetaDownloadError("The Meta APK download could not be completed. Retry or use a manual APK URL.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _probe_latest(source: Path) -> BuildProfile:
    return probe_horizon_apk(source, tool("apktool"))


def download_meta(destination: Path, *, probe: Callable[[Path], BuildProfile] = _probe_latest) -> Path:
    token = os.environ.get("META_ACCESS_TOKEN", "").strip()
    if not token:
        raise MetaDownloadError("Add the META_ACCESS_TOKEN repository secret for Meta downloads, or choose a manual APK URL.")
    if "\r" in token or "\n" in token:
        raise MetaDownloadError("META_ACCESS_TOKEN must contain just the token on one line.")
    print("Looking up the latest LIVE Plex release in Meta Store metadata...", flush=True)
    live, binaries = _resolve_binaries()
    reviewed = {(profile.version, profile.version_code) for profile in PROFILES if profile.flavor == "horizon"}
    fallback = sorted((binary for binary in binaries if (binary.version, binary.code) in reviewed),
                      key=lambda binary: binary.code, reverse=True)
    latest = live[0] if live else None
    if latest and len(live) > 1 and live[1].code == latest.code:
        print(f"Meta listed multiple LIVE binaries for version code {latest.code}.", flush=True)
        latest = None
    if latest and fallback and latest.code < fallback[0].code:
        latest = None

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="meta-download-", dir=destination.parent) as temporary:
        candidate = Path(temporary) / "plex.apk"
        if latest:
            print(f"Downloading and probing latest Meta Plex {latest.label}...", flush=True)
            try:
                _download_binary(latest, token, candidate)
                profile = probe(candidate)
                if (profile.flavor, profile.version, profile.version_code) != ("horizon", latest.version, latest.code):
                    raise UnsupportedAPK("The APK build identity differs from the LIVE store metadata.")
            except UnsupportedAPK as error:
                reason = " ".join(str(error).split())
                print(f"Latest Meta Plex {latest.label} failed compatibility checks: {reason}", flush=True)
            else:
                candidate.replace(destination)
                print(f"Selected latest compatible Meta Plex {latest.label}.", flush=True)
                return destination
        if not fallback or (len(fallback) > 1 and fallback[1].code == fallback[0].code) or fallback[0] == latest:
            raise MetaDownloadError("No compatible latest APK or unique reviewed fallback is available. Use a manual APK URL.")
        print(f"Falling back to reviewed Meta Plex {fallback[0].label}.", flush=True)
        try:
            _download_binary(fallback[0], token, candidate)
        except UnsupportedAPK as error:
            raise MetaDownloadError(f"The reviewed fallback is incomplete: {error} Use a manual APK URL.") from None
        candidate.replace(destination)
    return destination
