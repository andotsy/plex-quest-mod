import os
import tempfile
import threading
import unittest
from hashlib import sha1
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch

from plex_quest.build import download, package_apks, sign
from plex_quest.hermes import patch_bundle
from plex_quest.smali import TEMPLATE, get_method, inject_navigation_handler, patch_activity, patch_application, patch_key_mapping


class NativePatchTests(unittest.TestCase):
    def test_stock_startup_patch_is_complete_and_idempotent(self):
        text = (
            ".class public final Ltv/plex/app/MainApplication;\n"
            ".method public final onCreate()V\n    .locals 8\n"
            "    invoke-super {p0}, Landroid/app/Application;->onCreate()V\n"
            "    sget-object v0, Lcom/facebook/react/defaults/DefaultNewArchitectureEntryPoint;->INSTANCE:Ljava/lang/Object;\n"
        )
        for register in ("v1", "v5", "v3"):
            text += (
                f"    check-cast {register}, Landroid/app/UiModeManager;\n"
                f"    invoke-virtual {{{register}}}, Landroid/app/UiModeManager;->getCurrentModeType()I\n"
                f"    .line 100\n    move-result {register}\n"
            )
        text += "    return-void\n.end method\n"
        patched = patch_application(text)
        self.assertNotIn("getCurrentModeType", patched)
        self.assertEqual(patched.count("0x4"), 3)
        self.assertLess(patched.index("->setApplication"), patched.index("DefaultNewArchitectureEntryPoint"))
        self.assertEqual(patch_application(patched), patched)

    def test_unknown_startup_logic_is_rejected(self):
        text = ".method public final onCreate()V\n    .locals 8\n    return-void\n.end method"
        with self.assertRaises(ValueError):
            patch_application(text)

    def test_activity_patch_preserves_existing_key_routing_and_unrelated_fields(self):
        original = (
            ".class public final Ltv/plex/app/MainActivity;\n"
            ".super Lcom/facebook/react/ReactActivity;\n"
            ".field private userState:I\n"
            ".method public constructor <init>()V\n    .locals 0\n    return-void\n.end method\n"
            ".method public final dispatchKeyEvent(Landroid/view/KeyEvent;)Z\n"
            "    .locals 1\n    const/4 v0, 0x1\n    return v0\n.end method\n"
        )
        patched = patch_activity(original, TEMPLATE.read_text())
        descriptor = "dispatchKeyEvent(Landroid/view/KeyEvent;)Z"
        self.assertEqual(get_method(patched, descriptor), get_method(original, descriptor))
        self.assertIn(".field private userState:I", patched)
        self.assertEqual(patched.count(".field private static questSeekDirection:I"), 1)
        repatched = patch_activity(patched, TEMPLATE.read_text())
        for descriptor in (
            "dispatchGenericMotionEvent(Landroid/view/MotionEvent;)Z",
            "dispatchTouchEvent(Landroid/view/MotionEvent;)Z",
            "questScrollAtPointer(Landroid/view/MotionEvent;)Z",
        ):
            self.assertEqual(get_method(repatched, descriptor), get_method(patched, descriptor))
        self.assertEqual(repatched.count(".field private static questSeekDirection:I"), 1)

    def test_controller_mapping_does_not_replace_other_buttons(self):
        original = (
            ".method public static final b(Landroid/view/KeyEvent;)Ljava/lang/String;\n"
            "    .locals 1\n"
            "    invoke-virtual {p0}, Landroid/view/KeyEvent;->getKeyCode()I\n"
            "    .line 9\n    move-result p0\n"
            "    const/16 v0, 0x63\n    if-eq p0, v0, :play\n"
            "    const-string p0, \"unknown\"\n    return-object p0\n"
            ":play\n    const-string p0, \"playOrPause\"\n    return-object p0\n.end method\n"
        )
        patched = patch_key_mapping(original)
        self.assertIn("const/16 v0, 0x63", patched)
        self.assertIn(".locals 2", patched)
        for code in ("0x60", "0x6a", "0x6b"):
            self.assertIn(f"const/16 v1, {code}\n    if-eq p0, v1, :play", patched)
        self.assertEqual(patch_key_mapping(patched), patched)

    def test_navigation_back_hook_keeps_original_dispatch_and_is_idempotent(self):
        descriptor = "dispatchKeyEvent(Landroid/view/KeyEvent;)Z"
        original = (
            ".method public final " + descriptor + "\n    .locals 1\n"
            "    const-string v0, \"event\"\n"
            "    invoke-super {p0, p1}, Landroid/app/Activity;->dispatchKeyEvent(Landroid/view/KeyEvent;)Z\n"
            "    move-result v0\n    return v0\n.end method\n"
        )
        patched = inject_navigation_handler(original, descriptor, "questHandleNavigationBack")
        self.assertIn("->questHandleNavigationBack(Landroid/view/KeyEvent;)Z", patched)
        self.assertIn('const-string v0, "event"', patched)
        self.assertIn("invoke-super {p0, p1}", patched)
        self.assertEqual(inject_navigation_handler(patched, descriptor, "questHandleNavigationBack"), patched)


class InputArchiveTests(unittest.TestCase):
    @staticmethod
    def apk_bytes(base=False):
        stream = BytesIO()
        with ZipFile(stream, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"manifest")
            if base:
                archive.writestr("assets/index.android.bundle", b"bundle")
        return stream.getvalue()

    def test_split_package_is_extracted_without_trusting_member_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.xapk"
            with ZipFile(source, "w") as archive:
                archive.writestr("../../base.apk", self.apk_bytes(base=True))
                archive.writestr("splits/config.arm64_v8a.apk", self.apk_bytes())
            base, splits = package_apks(source, root / "extracted")
            self.assertEqual(base.parent, root / "extracted")
            self.assertEqual([path.name for path in splits], ["config.arm64_v8a.apk"])
            self.assertFalse((root / "base.apk").exists())

    def test_archive_with_two_base_apks_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.apkm"
            with ZipFile(source, "w") as archive:
                archive.writestr("one.apk", self.apk_bytes(base=True))
                archive.writestr("two.apk", self.apk_bytes(base=True))
            with self.assertRaises(ValueError):
                package_apks(source, root / "extracted")

    def test_plain_apk_is_preserved_as_the_input_base(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.apk"
            source.write_bytes(self.apk_bytes(base=True))
            base, splits = package_apks(source, root / "extracted")
            self.assertEqual(base.read_bytes(), source.read_bytes())
            self.assertEqual(splits, [])

    def test_non_http_download_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "download"
            with self.assertRaises(ValueError):
                download("file:///etc/passwd", destination)
            self.assertFalse(destination.exists())

    def test_direct_url_download_produces_the_exact_apk_bytes(self):
        payload = self.apk_bytes(base=True)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "package.apk"
                download(f"http://127.0.0.1:{server.server_port}/download", destination)
                self.assertEqual(destination.read_bytes(), payload)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


class SigningConfigurationTests(unittest.TestCase):
    def test_github_secret_key_is_temporary_and_empty_key_password_uses_store_password(self):
        key_paths = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsigned = root / "unsigned"
            unsigned.mkdir()
            (unsigned / "base.apk").write_bytes(b"unsigned fixture")
            output = root / "signed"

            def signer_stub(_jar, arguments, _mounts, _docker):
                key = Path(arguments[arguments.index("--ks") + 1])
                key_paths.append(key)
                self.assertEqual(key.read_bytes(), b"local private key fixture")
                self.assertEqual(arguments[arguments.index("--ksKeyPass") + 1], "test-password")
                (output / "base-aligned-signed.apk").write_bytes(b"signed fixture")

            environment = {
                "APK_KEYSTORE_BASE64": "bG9jYWwgcHJpdmF0ZSBrZXkgZml4dHVyZQ==",
                "APK_KEY_ALIAS": "test-alias",
                "APK_STORE_PASSWORD": "test-password",
                "APK_KEY_PASSWORD": "",
            }
            with patch.dict(os.environ, environment), patch("plex_quest.build.java_jar", signer_stub):
                sign(unsigned, output, root / "signer.jar")
            self.assertEqual(len(key_paths), 1)
            self.assertFalse(key_paths[0].exists())
            self.assertEqual([path.name for path in output.iterdir()], ["base-aligned-signed.apk"])


@unittest.skipUnless(os.environ.get("PLEX_TEST_APK"), "Local APK fixture is optional and is never committed")
class HermesIntegrationTests(unittest.TestCase):
    def test_actual_bundle_changes_are_limited_and_idempotent(self):
        with ZipFile(os.environ["PLEX_TEST_APK"]) as archive:
            original = archive.read("assets/index.android.bundle")
        patched = patch_bundle(original)
        allowed = set(range(0x788FDB + 0x5E4, 0x788FDB + 0x5E8))
        allowed.update(range(0xC10E00 + 0x12, 0xC10E00 + 0x16))
        allowed.update((0xC48F4D + 0xA6, 0xC48F4D + 0xA9, 0xC48F4D + 0x146))
        allowed.update(range(0xC48D93 + 0x73, 0xC48D93 + 0x78))
        allowed.update(range(len(original) - 20, len(original)))
        changed = {index for index, (old, new) in enumerate(zip(original, patched)) if old != new}
        self.assertEqual(len(original), len(patched))
        self.assertTrue(changed.issubset(allowed))
        self.assertEqual(sha1(patched[:-20]).digest(), patched[-20:])
        self.assertEqual(patch_bundle(patched), patched)


if __name__ == "__main__":
    unittest.main()
