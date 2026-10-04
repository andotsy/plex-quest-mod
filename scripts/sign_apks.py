#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plex_quest.build import sign, tool


def main():
    parser = argparse.ArgumentParser(description="Sign a patched APK install set using private environment secrets.")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--signer", type=Path)
    parser.add_argument("--keystore", type=Path, help="Local key file, instead of APK_KEYSTORE_BASE64")
    parser.add_argument("--docker", action="store_true")
    args = parser.parse_args()
    sign(args.directory, args.output, tool("signer", args.signer), args.docker, args.keystore)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Signing failed: {error}", file=sys.stderr)
        sys.exit(1)
