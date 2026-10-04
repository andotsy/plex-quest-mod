import base64
import json
import os
import shutil
import subprocess
import tempfile
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile

from . import SUPPORTED_PLEX, VERSION
from .hermes import patch_bundle
from .smali import patch_smali


ROOT = Path(__file__).resolve().parents[2]
MAX_INPUT_SIZE = 512 * 1024 * 1024
TOOLS = {
    "apktool": (
        "https://github.com/iBotPeaches/Apktool/releases/download/v3.0.3/apktool_3.0.3.jar",
        "dbf930b076c6b9be08d57c449cacefc3bdd6b71ebd59b3066fc0e1f5b14f9423",
    ),
    "signer": (
        "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar",
        "e1299fd6fcf4da527dd53735b56127e8ea922a321128123b9c32d619bba1d835",
    ),
}


def download(url: str, destination: Path, expected_hash: str | None = None) -> Path:
    if urlparse(url).scheme not in ("https", "http"):
        raise ValueError("The download URL must use HTTP or HTTPS.")
    request = Request(url, headers={"User-Agent": "plex-quest-patch/" + VERSION})
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        total = 0
        with urlopen(request, timeout=60) as response, destination.open("wb") as target:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_INPUT_SIZE:
                    raise ValueError("Download exceeds the 512 MiB input limit.")
                target.write(chunk)
        if expected_hash and sha256(destination.read_bytes()).hexdigest() != expected_hash:
            raise ValueError("Download checksum does not match the pinned tool release.")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def tool(name: str, supplied: Path | None = None) -> Path:
    url, checksum = TOOLS[name]
    path = supplied.resolve() if supplied else ROOT / "tools" / (name + ".jar")
    if path.exists():
        if sha256(path.read_bytes()).hexdigest() != checksum:
            raise ValueError(f"Incorrect checksum for {name}; use the supported release.")
        return path
    if supplied:
        raise FileNotFoundError(path)
    return download(url, path, checksum)


def package_apks(source: Path, directory: Path) -> tuple[Path, list[Path]]:
    """Accept a base/universal APK or an APKM/XAPK split archive."""
    directory.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as archive:
        if "AndroidManifest.xml" in archive.namelist():
            base = directory / "base.apk"
            shutil.copyfile(source, base)
            return base, []
        bases = []
        splits = []
        names = set()
        for entry in archive.infolist():
            if not entry.filename.lower().endswith(".apk"):
                continue
            # Flatten entries instead of trusting archive paths.
            name = Path(entry.filename).name
            if name in names or entry.file_size > MAX_INPUT_SIZE:
                raise ValueError("Duplicate APK names or oversized APK in input archive.")
            names.add(name)
            content = archive.read(entry)
            with ZipFile(BytesIO(content)) as apk:
                is_base = "assets/index.android.bundle" in apk.namelist()
            destination = directory / name
            destination.write_bytes(content)
            (bases if is_base else splits).append(destination)
        if len(bases) != 1:
            raise ValueError("Input must contain exactly one Plex base APK with a Hermes bundle.")
        return bases[0], splits


def java_jar(jar: Path, arguments: list[str], mounts: dict[Path, str] | None = None,
             docker: bool = False) -> None:
    if not docker:
        subprocess.run(["java", "-jar", str(jar), *arguments], check=True)
        return
    mounts = mounts or {}
    mapping = {jar.resolve(): "/tool.jar", **{path.resolve(): value for path, value in mounts.items()}}
    translated = []
    for argument in arguments:
        converted = argument
        for host, container in mapping.items():
            if argument == str(host) or argument.startswith(str(host) + os.sep):
                converted = container + argument[len(str(host)):].replace(os.sep, "/")
                break
        translated.append(converted)
    command = ["docker", "run", "--rm"]
    for host, container in mapping.items():
        command += ["-v", f"{host}:{container}"]
    command += ["eclipse-temurin:21-jre", "java", "-jar", "/tool.jar", *translated]
    subprocess.run(command, check=True)


def build(source: Path, output: Path, apktool: Path, docker: bool = False) -> Path:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; choose a new directory.")
    output.mkdir(parents=True, exist_ok=True)
    work_root = ROOT / ".work"
    work_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="patch-", dir=work_root) as temporary:
        work = Path(temporary)
        base, splits = package_apks(source.resolve(), work / "input")
        with ZipFile(base) as archive:
            bundle = patch_bundle(archive.read("assets/index.android.bundle"))
            preserved = {name: archive.read(name) for name in ("AndroidManifest.xml", "resources.arsc")}
        tree = work / "decoded"
        java_jar(apktool, ["d", "-r", str(base), "-o", str(tree)], {work: "/work"}, docker)
        patch_smali(tree)
        (tree / "assets/index.android.bundle").write_bytes(bundle)
        built = work / "base-patched.apk"
        java_jar(apktool, ["b", str(tree), "-o", str(built)], {work: "/work"}, docker)
        with ZipFile(built) as archive:
            for name, original in preserved.items():
                if archive.read(name) != original:
                    raise ValueError(f"Apktool unexpectedly changed {name}.")
            if archive.read("assets/index.android.bundle") != bundle:
                raise ValueError("Rebuilt APK does not contain the verified Hermes patches.")
        unsigned = output / "unsigned"
        unsigned.mkdir()
        shutil.copyfile(built, unsigned / "base-patched.apk")
        for split in splits:
            shutil.copyfile(split, unsigned / split.name)
        report = {
            "patch_version": VERSION,
            "plex_version": SUPPORTED_PLEX,
            "source_sha256": sha256(source.read_bytes()).hexdigest(),
            "manifest_preserved": True,
            "resources_preserved": True,
            "patches": ["tv-layout", "controller-input", "pointer-scroll", "episode-deck-input", "navigation-popover-input",
                        "seek-wake-race", "inline-season-episode-rows"],
            "unsigned_apks": {path.name: sha256(path.read_bytes()).hexdigest()
                              for path in sorted(unsigned.glob("*.apk"))},
        }
        (output / "patch-report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Verified patched output: {output}")
    return output


def sign(directory: Path, output: Path, signer: Path, docker: bool = False,
         keystore: Path | None = None) -> None:
    """Sign every APK using one private key supplied only through environment variables."""
    required = ("APK_KEY_ALIAS", "APK_STORE_PASSWORD")
    if keystore is None:
        required += ("APK_KEYSTORE_BASE64",)
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ValueError("Missing signing configuration: " + ", ".join(missing))
    work_root = ROOT / ".work"
    work_root.mkdir(exist_ok=True)
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Signing output directory must be empty.")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sign-", dir=work_root) as temporary:
        work = Path(temporary)
        key = work / "signing.p12"
        if keystore:
            shutil.copyfile(keystore.resolve(), key)
        else:
            key.write_bytes(base64.b64decode(os.environ["APK_KEYSTORE_BASE64"], validate=True))
        key.chmod(0o600)
        password = os.environ["APK_STORE_PASSWORD"]
        arguments = ["--apks", str(directory.resolve()), "--out", str(output),
                     "--ks", str(key), "--ksAlias", os.environ["APK_KEY_ALIAS"],
                     "--ksPass", password,
                     "--ksKeyPass", os.environ.get("APK_KEY_PASSWORD") or password,
                     "--allowResign"]
        java_jar(signer, arguments, {work: "/signing", directory.resolve(): "/input",
                                  output: "/output"}, docker)
        signed = list(output.glob("*-signed.apk"))
        if len(signed) != len(list(directory.glob("*.apk"))):
            raise ValueError("Signer did not produce the complete install set.")
        report_path = directory.resolve().parent / "patch-report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text())
            report["signed_apks"] = {path.name: sha256(path.read_bytes()).hexdigest()
                                     for path in sorted(signed)}
            report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Verified signed APKs: {output}")
