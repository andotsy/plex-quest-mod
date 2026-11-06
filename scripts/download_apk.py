#!/usr/bin/env python3
"""Acquire an original Plex package without patching it or loading signing keys."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plex_quest.build import download
from plex_quest.meta import download_meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Direct URL to your APK/APKM/XAPK")
    source.add_argument("--meta", action="store_true", help="Use the META_ACCESS_TOKEN environment variable")
    parser.add_argument("--out", type=Path, required=True, help="Destination for the original package")
    args = parser.parse_args(argv)
    if args.url is not None and not args.url.strip():
        parser.error("The manual APK URL is required when using --url.")
    if args.meta:
        download_meta(args.out)
    else:
        download(args.url, args.out)
    print(f"Original Plex package downloaded: {args.out}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Download failed: {error}", file=sys.stderr)
        sys.exit(1)
