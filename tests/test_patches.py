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

from hermes_dec.parsers.hbc_bytecode_parser import parse_hbc_bytecode
from hermes_dec.parsers.hbc_file_parser import HBCReader

from plex_quest.build import download, package_apks, require_native_libraries, sign, verify_standalone
from plex_quest.hermes import UnsupportedBundle, patch_bundle
from plex_quest.smali import TEMPLATE, get_method, inject_navigation_handler, patch_activity, patch_application, patch_application_id, patch_key_mapping, patch_seek_event


class NativePatchTests(unittest.TestCase):
    def test_queued_seek_events_capture_their_own_hold_duration(self):
        original = (
            '.method public final emitOnKeyEvent(Landroid/view/KeyEvent;)V\n    .locals 3\n'
            '    invoke-static {}, Lcom/facebook/react/bridge/Arguments;->createMap()Lcom/facebook/react/bridge/WritableMap;\n'
            '    move-result-object v0\n'
            '    invoke-virtual {p1}, Landroid/view/KeyEvent;->getAction()I\n'
            '    move-result p1\n'
            '    invoke-virtual {p0, v0}, Ltv/plex/video/NativeKeyHandlerSpec;->emitOnKey(Lcom/facebook/react/bridge/ReadableMap;)V\n'
            '    return-void\n.end method\n'
        )
        patched = patch_seek_event(original)
        self.assertIn('->getEventTime()J', patched)
        self.assertIn('->getDownTime()J', patched)
        self.assertLess(patched.index('->questSeekStepForHold'), patched.index('move-result p1'))
        self.assertEqual(patch_seek_event(patched), patched)
        self.assertIn('NativeKeyHandlerSpec;->emitOnKey', patched)

    def test_package_identity_changes_without_renaming_native_classes(self):
        original = (
            '.class public final Ltv/plex/app/BuildConfig;\n'
            '.field public static final APPLICATION_ID:Ljava/lang/String; = "com.plexapp.android"\n'
            '.field public static final FLAVOR:Ljava/lang/String; = "play"\n'
        )
        patched = patch_application_id(original)
        self.assertIn('APPLICATION_ID:Ljava/lang/String; = "com.plexapp.android.tv"', patched)
        self.assertIn('.class public final Ltv/plex/app/BuildConfig;', patched)
        self.assertIn('FLAVOR:Ljava/lang/String; = "play"', patched)
        self.assertEqual(patch_application_id(patched), patched)
        with self.assertRaises(ValueError):
            patch_application_id(original.replace('com.plexapp.android', 'unrelated.application'))

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

    def test_incomplete_split_base_is_rejected_before_a_standalone_build(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.apk"
            base.write_bytes(self.apk_bytes(base=True))
            with self.assertRaisesRegex(ValueError, "base.apk alone is incomplete"):
                require_native_libraries([base])

    def test_armv7_split_does_not_satisfy_quest_native_requirements(self):
        with tempfile.TemporaryDirectory() as directory:
            wrong_abi = Path(directory) / "wrong-abi.apk"
            with ZipFile(wrong_abi, "w") as archive:
                for library in ("libhermesvm.so", "libreactnative.so", "libPlexVideo.so"):
                    archive.writestr("lib/armeabi-v7a/" + library, b"wrong architecture")
            with self.assertRaisesRegex(ValueError, "ARM64"):
                require_native_libraries([wrong_abi])

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
        allowed.update(range(0x788FDB + 0x5E8, 0x788FDB + 0x606))
        allowed.update(range(0x788F0E + 0xE, 0x788F0E + 0x2D))
        allowed.update(range(0xC10E00 + 0x12, 0xC10E00 + 0x16))
        allowed.update((0xC48F4D + 0xA6, 0xC48F4D + 0xA9, 0xC48F4D + 0x146))
        allowed.update(range(0xC48D93 + 0x73, 0xC48D93 + 0x78))
        allowed.add(0xC08CD1 + 0x76)
        allowed.update(range(0xC08E2C + 0x30F, 0xC08E2C + 0x3B1))
        allowed.update(range(0xC0DE59 + 0xE, 0xC0DE59 + 0x17))
        allowed.update(range(len(original) - 20, len(original)))
        changed = {index for index, (old, new) in enumerate(zip(original, patched)) if old != new}
        self.assertEqual(len(original), len(patched))
        self.assertTrue(changed.issubset(allowed))
        self.assertEqual(sha1(patched[:-20]).digest(), patched[-20:])
        self.assertEqual(patch_bundle(patched), patched)

    def test_timeline_uses_the_existing_pointer_wrapper_and_a_scoped_native_marker(self):
        with ZipFile(os.environ["PLEX_TEST_APK"]) as archive:
            patched = patch_bundle(archive.read("assets/index.android.bundle"))
        reader = HBCReader()
        reader.read_whole_file(BytesIO(patched))
        selector = {ins.original_pos: ins for ins in parse_hbc_bytecode(reader.function_headers[57908], reader)}
        self.assertEqual((selector[0x74].arg1, selector[0x74].arg2), (4, 1))
        wrapper = list(parse_hbc_bytecode(reader.function_headers[57910], reader))
        native_marker = [ins for ins in wrapper if ins.inst.name == "LoadConstStringLongIndex"
                         and ins.arg1 == 18 and ins.arg2 == 84136]
        test_id = [ins for ins in wrapper if ins.inst.name == "PutNewOwnByIdShort"
                   and (ins.arg1, ins.arg2, ins.arg3) == (0, 18, 237)]
        self.assertEqual(len(native_marker), 1)
        self.assertEqual(len(test_id), 1)
        renderer = next(ins for ins in wrapper if ins.original_pos > test_id[0].original_pos
                        and ins.inst.name == "Call3")
        self.assertLess(native_marker[0].original_pos, test_id[0].original_pos)
        self.assertLess(test_id[0].original_pos, renderer.original_pos)
        native_root = [ins for ins in wrapper if ins.inst.name == "LoadConstStringLongIndex"
                       and ins.arg1 == 8 and ins.arg2 == 34614]
        self.assertEqual(len(native_root), 1)
        self.assertTrue(any(ins.inst.name == "GetByVal" and (ins.arg1, ins.arg2, ins.arg3) == (8, 7, 8)
                            for ins in wrapper))
        self.assertTrue(any(ins.inst.name == "PutNewOwnById" and (ins.arg1, ins.arg2, ins.arg3) == (0, 7, 64756)
                            for ins in wrapper))
        self.assertTrue(any(ins.inst.name == "LoadConstStringLongIndex" and ins.arg2 == 63009
                            for ins in wrapper))
        self.assertTrue(any(ins.inst.name == "PutByVal" and (ins.arg1, ins.arg2, ins.arg3) == (18, 7, 17)
                            for ins in wrapper))
        callback = {ins.original_pos: ins for ins in parse_hbc_bytecode(reader.function_headers[58007], reader)}
        self.assertEqual((callback[0xE].inst.name, callback[0xE].arg1), ("LoadConstFalse", 0))
        self.assertEqual((callback[0x10].inst.name, callback[0x10].arg1), ("Jmp", 7))

    def test_unknown_timeline_selector_is_rejected(self):
        with ZipFile(os.environ["PLEX_TEST_APK"]) as archive:
            bundle = bytearray(archive.read("assets/index.android.bundle"))
        bundle[0xC08CD1 + 0x75] = 5  # Different destination register / module wiring.
        bundle[-20:] = sha1(bundle[:-20]).digest()
        with self.assertRaisesRegex(UnsupportedBundle, "TV seekbar component selector"):
            patch_bundle(bytes(bundle))

    def test_relative_seek_has_a_symmetric_default_and_one_captured_distance(self):
        with ZipFile(os.environ["PLEX_TEST_APK"]) as archive:
            patched = patch_bundle(archive.read("assets/index.android.bundle"))
        reader = HBCReader()
        reader.read_whole_file(BytesIO(patched))
        delta = list(parse_hbc_bytecode(reader.function_headers[24578], reader))
        default = next(ins for ins in delta if ins.original_pos == 0xE)
        self.assertEqual((default.inst.name, default.arg1, default.arg2), ("LoadConstInt", 4, 10000))
        self.assertTrue(any(ins.inst.name == "Sub" and (ins.arg1, ins.arg2, ins.arg3) == (4, 5, 4)
                            for ins in delta))
        self.assertEqual(sum(ins.inst.name == "Call2" and ins.original_pos == 0x4B for ins in delta), 1)


@unittest.skipUnless(os.environ.get("PLEX_TEST_MERGED_APK") and os.environ.get("PLEX_TEST_RENAMED_APK"),
                     "Merged/renamed APK fixtures are optional and are never committed")
class StandaloneIntegrationTests(unittest.TestCase):
    def test_actual_package_rename_preserves_resources_and_executable_payload(self):
        merged = Path(os.environ["PLEX_TEST_MERGED_APK"])
        renamed = Path(os.environ["PLEX_TEST_RENAMED_APK"])
        report = verify_standalone([merged], merged, renamed)
        self.assertEqual(report["dex_files"], 4)
        self.assertGreater(report["native_libraries"], 0)
        self.assertTrue(report["resource_ids_values_and_configurations_preserved_on_rename"])


if __name__ == "__main__":
    unittest.main()
