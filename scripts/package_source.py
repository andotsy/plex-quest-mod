#!/usr/bin/env python3
"""Create a shareable archive containing only this project's public source files."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist/plex-quest-patch-source.zip")
    args = parser.parse_args()
    files = [ROOT / name for name in (".gitignore", "LICENSE", "README.md", "requirements.txt")]
    extensions = {".py", ".java", ".smali", ".yml"}
    for directory in (".github", "patches", "scripts", "src", "tests"):
        files.extend(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and not path.is_symlink() and path.suffix in extensions)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.out, "w", ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, "plex-quest-mod/" + path.relative_to(ROOT).as_posix())
    print(f"Packaged {len(files)} source files: {args.out}")


if __name__ == "__main__":
    main()
