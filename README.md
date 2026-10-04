# Plex Quest TV/controller patch

An unofficial, source-only patch tool for **Plex Android 2026.17.0
(version code 971050399, play build)**, tested on Quest 3.

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

The patch validates the supported native and Hermes layouts before editing.
It preserves the binary Android manifest and resource table byte-for-byte.

## GitHub Action: URL in, patched artifact out

1. Put this repository in your GitHub account.
2. Open **Actions → Patch Plex APK → Run workflow**.
3. Enter a **direct download URL** to your APK, APKM, or XAPK for the supported version.
   A download page URL is not an APK URL.
4. Run the workflow. Download its `plex-quest-unsigned-*` artifact after completion.

The artifact contains the rebuilt base APK, any supplied configuration splits,
and a JSON patch/checksum report. An APKM/XAPK preserves its split APKs; a base-only
APK input produces only a base APK. A split base still needs its matching architecture,
language, and density splits to install.

### Optional signing

To get a ready-to-install signed set, configure these **repository Actions secrets**:

| Secret | Value |
| --- | --- |
| `APK_KEYSTORE_BASE64` | Base64-encoded PKCS12/JKS keystore, on one line |
| `APK_KEY_ALIAS` | Signing-key alias |
| `APK_STORE_PASSWORD` | Keystore password |
| `APK_KEY_PASSWORD` | Key password, if different from the store password |

Enable **Sign the complete APK set** when running the workflow. The same private key
signs the base and every split. Signing material is temporary and is excluded from
the artifact. Keep that key for future patched updates.

## Local usage

Requires Python 3.12 and Java 21, or Docker for the Java runtime.
Apktool 3.0.3 and Uber APK Signer 1.3.0 are downloaded with pinned SHA-256 checksums.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python scripts/patch_apk.py --input /path/to/your-package.apk --out dist
# Or download directly:
python scripts/patch_apk.py --url 'https://your-host/package.apk' --out dist
# If Java is not installed locally:
python scripts/patch_apk.py --input /path/to/your-package.apk --out dist --docker
```

Use a new or empty output directory for each build. APKM and XAPK inputs are also
supported. To sign locally, set the signing environment variables described above:

```bash
python scripts/sign_apks.py --directory dist/unsigned --output dist/signed
# Or supply a local key file, with APK_KEY_ALIAS and APK_STORE_PASSWORD in the environment:
python scripts/sign_apks.py --directory dist/unsigned --output dist/signed --keystore /path/to/your-key.p12
```

Install a signed universal APK with `adb install -r`. For split packages, select
the matching splits for your device and install them together:

```bash
adb install-multiple -r base-patched-signed.apk matching-split-1.apk matching-split-2.apk
```

An update preserving app data requires the same signing certificate as the installed
app. A custom-signed APK cannot update an official Plex-signed installation. This
tool does not uninstall Plex or clear its app data.

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
hash, and verifies that the rebuilt manifest/resources and patched bundle match
the expected bytes. Headset validation of the final build confirmed episode browsing,
pointer scrolling, held-stick seek/release, second-down deck opening, up returning
to transport controls, and top-menu popover positioning/dismissal.
