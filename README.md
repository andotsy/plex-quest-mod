# Plex Quest patch

![Quest controller controls for scrolling, seeking, play/pause, and episode-queue navigation](assets/quest-controls.png)

Patch your own Plex Android APK for TV-style browsing and Quest controller input.
No Plex APK is provided here. The original Play build has been used on Quest 3.
The Meta build has passed patching and standalone-build checks; playback on the
headset still needs verification.

For the Meta build, the patch selects Plex's built-in fallback for the missing
Vizbee casting receiver. This prevents a TV-mode crash when theme music or other
media starts and the receiver tries to call the absent native player adapter.
The Play build retains its native Vizbee receiver.

Episode rows retain Plex's minimum loading height and grow to fit their cards,
so episode descriptions stay above the next section's heading.

Tap a top navigation button or popup row to move TV focus to it. Popup rows get
the normal focused highlight and activate through Plex's existing menu handlers.
Foreground dialogs keep their own taps and Back handling; hidden navigation
popups do not take focus away from them.

During playback, the first screen-background click or assigned play/pause button
press reveals hidden controls without changing playback. While controls are
visible, further presses toggle play/pause. Once controls hide again, the next
press only reveals them. Clicking a visible control or the timeline still performs
that control's action.

Click the playback timeline with the index trigger to seek to that point.
Either thumbstick seeks ±10 seconds per jump, increasing to ±30 seconds after
2 seconds of holding and ±60 seconds after 5 seconds. Release or change direction
to reset the jump size.

**Supported inputs:**

| Source | Plex version | Version code |
| --- | --- | --- |
| Meta Horizon Store (token or Quest extraction) | **2026.18.0** | **971050431** |
| Google Play | **2026.17.0** | **971050399** |

The patcher detects the build automatically. Other versions or store variants are
rejected; a matching version name alone is not enough. Supply a standalone `.apk`
or a complete `.apkm` / `.xapk` containing ARM64 libraries.

## Patch with GitHub Actions

1. **Fork this repository**, then open **Actions** in **your fork** and enable workflows if prompted.
2. Add the [signing secrets](#signing) to your fork. This is a one-time setup.
3. Choose a source below. For `manual`, prepare a direct APK URL. For `meta`, add
   the optional `META_ACCESS_TOKEN` secret using the [Meta setup](#optional-meta-store-download).
4. Open **Actions → Patch Plex APK → Run workflow**. Choose **`apk_source`**,
   leave **signing enabled**, and run it.
5. When the run finishes, download the **`plex-quest-signed-…`** artifact under **Artifacts** and unzip it.
6. Sideload **`plex-quest-tv-aligned-signed.apk`** onto your Quest. With ADB:

   ```bash
   adb install -r plex-quest-tv-aligned-signed.apk
   ```

| `apk_source` | Setup | `apk_url` |
| --- | --- | --- |
| **`manual`** (default) | [Extract your APK](#get-the-apk-from-your-quest) or supply another supported complete APK/APKM/XAPK; upload it to a file host accessible to GitHub Actions without a browser login | Paste the **direct download URL**, not a download page |
| **`meta`** (optional) | Save your own Meta user access token as the **`META_ACCESS_TOKEN`** repository secret | Leave blank |

The run has two jobs: **Download original APK**, then **Patch and sign APK**.
A download or authentication failure stops in the first job, before patching.
The original package is transferred between jobs as a short-lived Actions
artifact, retained for one day. Only the download job receives the Meta token;
only the patch/sign job receives signing secrets. You can rerun a failed patch
job while the original-package artifact is available. After it expires, rerun
both jobs to download it again.

The result is **one signed, standalone APK**. It uses `com.plexapp.android.tv`,
with its own login/settings, and can coexist with the official Plex app. Reuse the
same signing key for updates to an existing mod installation.

## Optional Meta Store download

The `meta` source lets GitHub Actions download Plex directly from Meta, without
extracting or hosting an APK yourself. Set it up in **your own fork**:

1. Add [Plex](https://www.meta.com/experiences/plex-find-movies-tv-shows/1136900442841511/)
   to the Quest library of the Meta account you will use.
2. Sign in to the [Meta Horizon Developer Dashboard](https://developers.meta.com/horizon/manage/)
   with that same Meta account.
3. In the dashboard's left navigation, open **Account → Account settings**.
4. Find **Get Oculus platform utility token** and select **Linux**, since this
   workflow runs on an Ubuntu GitHub Actions runner. Click **Generate token** and
   copy the complete **user token**. Meta documents
   these steps in its [Platform Utility credentials guide](https://developers.meta.com/vr/resources/publish-reference-platform-command-line-utility/).
5. In your GitHub fork, open **Settings → Secrets and variables → Actions →
   New repository secret**. Name it **`META_ACCESS_TOKEN`** and paste the token
   into its value.
6. Run the workflow with **`apk_source: meta`** and **`apk_url` empty**. While this
   change is still in a pull request, select the PR's branch in **Run workflow**.

If the dashboard does not offer token generation, an alternative documented by
[BSManager](https://github.com/Zagrios/bs-manager/wiki/How-to-obtain-your-Oculus-Token)
is to sign in at [secure.oculus.com](https://secure.oculus.com), open Chrome/Edge
Developer Tools (**⌘⌥I** on macOS, **Ctrl+Shift+I** on Windows), then choose
**Application → Storage → Cookies → https://secure.oculus.com**. Find **`oc_ac_at`**
and copy its entire **Value** as your user token. Meta can change its session
storage; if the cookie is absent, use dashboard generation or the manual APK path.

Only this source uses the token. The downloader reads it from the secret/environment;
there is no token command-line option or workflow input, and it does not print
authenticated URLs or Meta response bodies. Do not put the token in `apk_url`.

The lookup selects the exact supported **2026.18.0 (971050431)** version from the
official Plex app's public version list. It does **not** switch to a newer release. The downloaded APK
must still pass all patcher version, code-layout, and ARM64 checks. If Meta rejects
the token or no longer serves that build, refresh the secret or choose `manual`.
This integration uses an [unofficial Meta API](https://github.com/ComputerElite/OculusGraphQLApiLib/blob/main/OculusGraphQLApiLib/GraphQL/GraphQLClient.cs).
The supported-version lookup and authenticated APK download have been verified
in GitHub Actions with a live user token. The account token is sent only to
Meta's APK download endpoint; the build lookup uses public Store metadata.

## Get the APK from your Quest

Install the supported Plex version from the Meta Horizon Store. On your computer,
enable Quest developer mode and USB debugging, connect the headset, and authorize
ADB in the headset. See the [Android ADB documentation](https://developer.android.com/tools/adb).

You can use an APK extraction/backup tool such as SideQuest or ADB Master, or find
the installed APK with ADB:

```bash
adb shell pm path com.plexapp.android
```

Copy the returned path without the `package:` prefix:

```bash
adb pull /data/app/.../base.apk plex-original.apk
```

The inspected Meta **2026.18.0** build is a complete standalone APK, including ARM64
libraries, so this extracted file can be used directly. If `pm path` returns more
than one APK, pull **all** of them, put them in a ZIP archive, and give that archive
a `.xapk` extension. A split `base.apk` alone is incomplete.

Extraction runs on your computer; patching and signing run on GitHub. The workflow
cannot connect to your headset. Google Play downloading is not integrated.

<details>
<summary>Optional: patch and sign locally instead of uploading an APK</summary>

With Python and a Java JDK installed, run:

```bash
python -m pip install -r requirements.txt
python scripts/patch_apk.py --input plex-original.apk --out dist
```

For a split install, add `--split path/to/split.apk` for every configuration APK.
For the optional Meta source, set `META_ACCESS_TOKEN` in your environment and use
`python scripts/patch_apk.py --meta --out dist` instead. Do not pass the token as
an argument.

Sign the output with your saved key from the [signing setup](#signing):

```bash
export APK_KEY_ALIAS=plex-quest
read -s -p "Keystore password: " APK_STORE_PASSWORD; echo
export APK_STORE_PASSWORD
python scripts/sign_apks.py --directory dist/unsigned --output dist/signed \
  --keystore plex-quest.p12
adb install -r dist/signed/plex-quest-tv-aligned-signed.apk
```

The password prompt above uses Bash. If your key has a separate key password,
also set `APK_KEY_PASSWORD`. Keep the same keystore for future updates.

</details>

## Signing

<details>
<summary>One-time signing setup</summary>

Android requires a signed APK. On a computer with a Java JDK installed, create
a signing key and choose a password when prompted:

```bash
keytool -genkeypair -keystore plex-quest.p12 -storetype PKCS12 \
  -alias plex-quest -keyalg RSA -keysize 4096 -validity 10000 \
  -dname "CN=Plex Quest"
```

Convert the key file to a single Base64 line:

```bash
base64 < plex-quest.p12 | tr -d '\n'
```

In **your fork**, go to **Settings → Secrets and variables → Actions → New repository secret**
and add:

| Secret | Value |
| --- | --- |
| `APK_KEYSTORE_BASE64` | The Base64 output above |
| `APK_KEY_ALIAS` | `plex-quest` |
| `APK_STORE_PASSWORD` | The password you chose |

If using an existing keystore with a different key password, also add `APK_KEY_PASSWORD`.
Keep your key file and password for future updates.

</details>

---

Unofficial; not affiliated with Plex. The [MIT license](LICENSE) covers this tooling,
not Plex or generated APKs.
