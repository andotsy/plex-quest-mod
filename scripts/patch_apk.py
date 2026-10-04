#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plex_quest.build import ROOT, build, download, tool


def main():
    parser = argparse.ArgumentParser(description="Patch Plex 2026.17.0 for Quest TV/controller use.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Locally supplied APK, APKM, or XAPK")
    source.add_argument("--url", help="Direct download URL to APK, APKM, or XAPK")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--apktool", type=Path, help="Apktool 3.0.3 JAR; downloaded/verified if omitted")
    parser.add_argument("--docker", action="store_true", help="Use Docker's Java runtime instead of local Java")
    args = parser.parse_args()
    source_path = args.input
    if args.url:
        source_path = download(args.url, ROOT / ".work/downloaded-package.zip")
    build(source_path, args.out, tool("apktool", args.apktool), args.docker)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Patch failed: {error}", file=sys.stderr)
        sys.exit(1)
