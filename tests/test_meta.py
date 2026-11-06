import importlib.util
import json
import os
import tempfile
import traceback
import unittest
from io import BytesIO, StringIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request
from zipfile import ZipFile
from contextlib import redirect_stderr
from unittest.mock import patch

from plex_quest.build import ROOT
from plex_quest.meta import (
    DOWNLOAD_URL, GRAPHQL_URL, PLEX_META_APP_ID, MetaDownloadError,
    MetaRedirectHandler, STORE_METADATA_TOKEN, VERSION_LIST_DOCUMENT, download_meta,
)
from plex_quest.profiles import HORIZON_2026_18


TOKEN = "fixture-token+with/reserved&characters=?"


def binary(**changes):
    return {"id": "1234567890123456", "__typename": "AndroidBinary",
            "version": HORIZON_2026_18.version,
            "version_code": str(HORIZON_2026_18.version_code), **changes}


def lookup(*binaries):
    return BytesIO(json.dumps({"data": {"node": {
        "id": PLEX_META_APP_ID, "primary_binaries": {"nodes": list(binaries)},
    }}}).encode())


def apk_bytes(native=True):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"fixture manifest")
        archive.writestr("assets/index.android.bundle", b"fixture bundle")
        if native:
            for name in ("libhermesvm.so", "libreactnative.so", "libPlexVideo.so"):
                archive.writestr("lib/arm64-v8a/" + name, b"fixture library")
    return stream.getvalue()


class MetaDownloadTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"META_ACCESS_TOKEN": TOKEN})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.destination = Path(self.directory.name) / "original.apk"

    def assert_sanitized(self, error):
        rendered = "".join(traceback.format_exception(error))
        self.assertNotIn(TOKEN, rendered)
        self.assertNotIn(urlencode({"access_token": TOKEN}), rendered)
        self.assertNotIn("securecdn.oculus.com/binaries", rendered)

    def test_resolves_exact_supported_app_and_version_and_downloads_original_bytes(self):
        payload = apk_bytes()
        with patch("plex_quest.meta.OPENER.open", side_effect=[lookup(binary()), BytesIO(payload)]) as open_request:
            result = download_meta(self.destination)
        self.assertEqual(result, self.destination)
        self.assertEqual(result.read_bytes(), payload)
        metadata, download = [call.args[0] for call in open_request.call_args_list]
        self.assertEqual(metadata.full_url, GRAPHQL_URL)
        self.assertEqual(metadata.get_method(), "POST")
        form = parse_qs(metadata.data.decode())
        self.assertEqual(form["access_token"], [STORE_METADATA_TOKEN])
        self.assertNotIn(TOKEN, metadata.data.decode())
        self.assertEqual(form["doc_id"], [VERSION_LIST_DOCUMENT])
        self.assertNotIn("doc", form)
        self.assertEqual(json.loads(form["variables"][0]), {"applicationID": PLEX_META_APP_ID})
        parsed = urlparse(download.full_url)
        self.assertEqual(parsed.scheme + "://" + parsed.netloc + parsed.path, DOWNLOAD_URL)
        self.assertEqual(parse_qs(parsed.query), {"id": [binary()["id"]], "access_token": [TOKEN]})
        self.assertEqual(list(self.destination.parent.glob("*.part")), [])

    def test_missing_token_fails_before_contacting_meta(self):
        with patch.dict(os.environ, {"META_ACCESS_TOKEN": ""}), patch("plex_quest.meta.OPENER.open") as network:
            with self.assertRaisesRegex(MetaDownloadError, "META_ACCESS_TOKEN repository secret"):
                download_meta(self.destination)
        network.assert_not_called()
        self.assertFalse(self.destination.exists())

    def test_missing_wrong_or_ambiguous_build_never_downloads_latest(self):
        responses = ((), (binary(version_code="971050999"),),
                     (binary(__typename="RiftBinary"),),
                     (binary(id="not-a-binary-id"),),
                     (binary(), binary(id="9876543210987654")))
        for entries in responses:
            with self.subTest(entries=entries), patch("plex_quest.meta.OPENER.open", return_value=lookup(*entries)) as network:
                with self.assertRaisesRegex(MetaDownloadError, "newer releases are not substituted"):
                    download_meta(self.destination)
                self.assertEqual(network.call_count, 1)
                self.assertFalse(self.destination.exists())

    def test_graphql_errors_and_malformed_responses_do_not_echo_response_or_token(self):
        responses = [json.dumps({"errors": [{"message": TOKEN}]}).encode(),
                     json.dumps({"error": {"message": TOKEN}}).encode(),
                     json.dumps({"data": {"node": None}}).encode(),
                     ("<html>" + TOKEN + "</html>").encode()]
        for response in responses:
            with self.subTest(response=response), patch("plex_quest.meta.OPENER.open", return_value=BytesIO(response)) as network:
                with self.assertRaises(MetaDownloadError) as caught:
                    download_meta(self.destination)
                self.assert_sanitized(caught.exception)
                self.assertEqual(network.call_count, 1)

    def test_auth_and_network_failures_are_sanitized_and_keep_existing_input(self):
        self.destination.write_bytes(b"previous input")
        sensitive_url = DOWNLOAD_URL + "?" + urlencode({"access_token": TOKEN})
        errors = [HTTPError(sensitive_url, 403, TOKEN, {}, BytesIO(TOKEN.encode())),
                  URLError(TOKEN + sensitive_url)]
        for error in errors:
            with self.subTest(error_type=type(error)), patch("plex_quest.meta.OPENER.open", side_effect=[lookup(binary()), error]):
                with self.assertRaises(MetaDownloadError) as caught:
                    download_meta(self.destination)
                self.assert_sanitized(caught.exception)
                self.assertEqual(self.destination.read_bytes(), b"previous input")
                self.assertEqual(list(self.destination.parent.glob("*.part")), [])

    def test_html_and_incomplete_apks_are_rejected_and_partial_files_are_removed(self):
        self.destination.write_bytes(b"previous input")
        for response in (("<html>" + TOKEN + "</html>").encode(), apk_bytes(native=False)):
            with self.subTest(length=len(response)), patch("plex_quest.meta.OPENER.open", side_effect=[lookup(binary()), BytesIO(response)]):
                with self.assertRaisesRegex(MetaDownloadError, "complete ARM64") as caught:
                    download_meta(self.destination)
                self.assert_sanitized(caught.exception)
                self.assertEqual(self.destination.read_bytes(), b"previous input")
                self.assertEqual(list(self.destination.parent.glob("*.part")), [])

    def test_oversized_apk_is_rejected_without_leaving_partial_output(self):
        with patch("plex_quest.meta.MAX_INPUT_SIZE", 32), patch(
            "plex_quest.meta.OPENER.open", side_effect=[lookup(binary()), BytesIO(apk_bytes())]
        ):
            with self.assertRaisesRegex(MetaDownloadError, "512 MiB"):
                download_meta(self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.destination.parent.glob("*.part")), [])

    def test_redirects_only_allow_https_meta_cdn_hosts(self):
        handler = MetaRedirectHandler()
        request = Request(DOWNLOAD_URL + "?" + urlencode({"access_token": TOKEN}))
        for url in ("http://securecdn.oculus.com/file", "https://example.com/file",
                    "https://meta.com.example.com/file", "https://securecdn.oculus.com:444/file",
                    "https://user:password@securecdn.oculus.com/file"):
            with self.subTest(url=url), self.assertRaises(MetaDownloadError) as caught:
                handler.redirect_request(request, None, 302, "Found", {}, url)
            self.assert_sanitized(caught.exception)
        accepted = handler.redirect_request(request, None, 302, "Found", {},
                                            "https://securecdn-lhr6-2.oculus.com/file?signed=value")
        self.assertEqual(accepted.full_url, "https://securecdn-lhr6-2.oculus.com/file?signed=value")
        self.assertNotIn(TOKEN, accepted.full_url)


class SourceSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("patch_cli", ROOT / "scripts/patch_apk.py")
        cls.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.cli)

    def test_manual_url_remains_independent_of_meta_secret(self):
        with patch.dict(os.environ, {"META_ACCESS_TOKEN": ""}), patch.object(self.cli, "download", return_value=Path("manual.apk")) as manual, \
                patch.object(self.cli, "download_meta") as meta, patch.object(self.cli, "build") as build, \
                patch.object(self.cli, "tool", return_value=Path("tool.jar")):
            self.cli.main(["--url", "https://example.com/plex.apk"])
            manual.assert_called_once()
            meta.assert_not_called()
            self.assertEqual(build.call_args.args[0], Path("manual.apk"))

    def test_meta_source_requires_no_apk_url_and_keeps_token_out_of_arguments(self):
        with patch.object(self.cli, "download_meta", return_value=Path("meta.apk")) as meta, \
                patch.object(self.cli, "download") as manual, patch.object(self.cli, "build") as build, \
                patch.object(self.cli, "tool", return_value=Path("tool.jar")):
            self.cli.main(["--meta"])
            meta.assert_called_once_with(ROOT / ".work/downloaded-meta.apk")
            manual.assert_not_called()
            self.assertEqual(build.call_args.args[0], Path("meta.apk"))

    def test_empty_manual_url_and_combined_sources_are_rejected(self):
        for arguments in (["--url", ""], ["--meta", "--url", "https://example.com/plex.apk"]):
            with self.subTest(arguments=arguments), redirect_stderr(StringIO()), patch.object(self.cli, "build") as build:
                with self.assertRaises(SystemExit):
                    self.cli.main(arguments)
                build.assert_not_called()


class DownloadOnlySelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("download_cli", ROOT / "scripts/download_apk.py")
        cls.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.cli)

    def test_download_job_acquires_meta_package_without_patching(self):
        with patch.object(self.cli, "download_meta") as meta, patch.object(self.cli, "download") as manual:
            self.cli.main(["--meta", "--out", "input/plex-source.zip"])
        meta.assert_called_once_with(Path("input/plex-source.zip"))
        manual.assert_not_called()
        self.assertNotIn("build", self.cli.__dict__)
        self.assertNotIn("sign", self.cli.__dict__)

    def test_download_job_preserves_manual_source_and_validates_missing_url(self):
        with patch.object(self.cli, "download_meta") as meta, patch.object(self.cli, "download") as manual:
            self.cli.main(["--url", "https://example.com/plex.apkm", "--out", "input/plex-source.zip"])
            manual.assert_called_once_with("https://example.com/plex.apkm", Path("input/plex-source.zip"))
            meta.assert_not_called()
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            self.cli.main(["--url", "", "--out", "input/plex-source.zip"])


if __name__ == "__main__":
    unittest.main()
