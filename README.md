# Plex Quest TV/controller patch

An unofficial, source-only patch tool for **Plex Android 2026.17.0
(version code 971050399, play build)**, tested on Quest 3.

The output is **one standalone APK** with the separate package ID
**`com.plexapp.android.tv`**. It includes the supplied native-library and resource
splits and can coexist with the official `com.plexapp.android` application.

## Changes

- Enable Plex's TV layout and initialize its TV startup dependencies.
- Point at a scrollable area and use the stick for smooth native pixel scrolling.
- During playback, hold left/right to repeat seek jumps. Greater deflection repeats
  faster (600 / 300 / 150 ms); releasing the stick stops the repeats.
- Fix the hidden-overlay seek race that could leave Plex's seek timer running
  after key release.
- Down once shows playback controls; a second down opens the episode/play-queue
  deck. Up returns to the transport overlay. Point at the episode row and scroll
  left/right smoothly while the deck is open.
- Top-menu pointer taps establish TV focus before opening the popover, so its
  anchor is measured below the selected menu item. Back and outside taps dismiss it.
- Restore inline season and episode lists using Plex's existing child-data renderer.
- Tap the playback background for play/pause; overlay buttons receive normal clicks.
- Map controller A and thumbstick-click buttons to play/pause.
- Merge native libraries and configuration resources into a single APK.
- Use a separate installation identity, including provider authorities, custom
  permissions, launcher aliases, resource package name, and native BuildConfig.

The patch validates the supported native and Hermes layouts before editing.
During code patching it preserves the input manifest and resources byte-for-byte.
The packaging step then merges supplied configuration resources and updates the
installation identity. A binary comparison verifies that renaming changes only
the resource package names, preserving all resource IDs, values, and configurations.
Patched DEX files, Hermes assets, and native libraries are checked byte-for-byte
across merging and renaming.

## GitHub Action: URL in, patched artifact out

1. Put this repository in your GitHub account.
2. Open **Actions → Patch Plex APK → Run workflow**.
3. Enter a **direct download URL** to a complete APKM/XAPK or universal APK for the supported version.
   A download page URL is not an APK URL.
   The input must include ARM64 native libraries; a split `base.apk` alone is rejected.
4. Configure the signing secrets below and run the workflow with signing enabled
   (the default). Download its `plex-quest-signed-*` artifact after completion.

The signed artifact contains **`plex-quest-tv-aligned-signed.apk`**, ready for a
single-file install, plus a JSON patch/checksum report. No separate split APKs
are needed at installation time. An unsigned artifact is also a complete standalone
APK, but it must be signed before Android will install it.

### Signing

To get a ready-to-install APK, configure these **repository Actions secrets**:

| Secret | Value |
| --- | --- |
| `APK_KEYSTORE_BASE64` | Base64-encoded PKCS12/JKS keystore, on one line |
| `APK_KEY_ALIAS` | Signing-key alias |
| `APK_STORE_PASSWORD` | Keystore password |
| `APK_KEY_PASSWORD` | Key password, if different from the store password |

Enable **Sign the standalone APK for installation** when running the workflow. The private key
signs the final merged APK. Signing material is temporary and is excluded from
the artifact. Keep that key for future patched updates.

## Local usage

Requires Python 3.12 and a Java 21 JDK, or Docker for the Java tools.
Apktool 3.0.3, APKEditor 1.4.9, and Uber APK Signer 1.3.0 are downloaded with pinned SHA-256 checksums.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python scripts/patch_apk.py --input /path/to/complete-package.apkm --out dist/build
# Or download directly:
python scripts/patch_apk.py --url 'https://your-host/package.apkm' --out dist/build
# If Java is not installed locally:
python scripts/patch_apk.py --input /path/to/complete-package.apkm --out dist/build --docker
# Or supply matching splits with a base-only input:
python scripts/patch_apk.py --input base.apk \
  --split split_config.arm64_v8a.apk --split split_config.en.apk \
  --split split_config.tvdpi.apk --out dist/build --docker
```

Use a new or empty output directory for each build. APKM and XAPK inputs are also
supported. To sign locally, set the signing environment variables described above:

```bash
python scripts/sign_apks.py --directory dist/build/unsigned --output dist/build/signed
# Or supply a local key file, with APK_KEY_ALIAS and APK_STORE_PASSWORD in the environment:
python scripts/sign_apks.py --directory dist/build/unsigned --output dist/build/signed --keystore /path/to/your-key.p12
```

Install the signed standalone APK with ADB Master's single-file APK upload, or:

```bash
adb install -r plex-quest-tv-aligned-signed.apk
```

The separate package is a new application with its own login/settings data. Updates
to this patched application require the same signing certificate. The tool does
not uninstall either application or clear its data.

## Sharing and licensing

Only this project's original patch/tooling code is covered by the MIT license.
Plex remains the property of its respective rights holders; this project is not
affiliated with Plex. Supply your own APK. The repository contains no Plex APKs,
bundles, disassembled application source, signing keys, or account credentials.

Generated APK artifacts contain modified third-party application code. Keep those
artifacts private unless you have permission to redistribute them; publishing the
patch source does not grant redistribution rights to Plex itself.

To create a clean source archive for sharing:

```bash
python scripts/package_source.py
```

This includes only source, workflows, tests, documentation, and license files.

## Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Each build additionally parses the patched Hermes functions, checks the footer
hash, verifies the merged executable payload, and checks installation identity and
resource preservation. Headset validation of the v27 controls confirmed episode browsing,
pointer scrolling, held-stick seek/release, second-down deck opening, up returning
to transport controls, and top-menu popover positioning/dismissal.
