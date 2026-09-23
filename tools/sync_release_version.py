#!/usr/bin/env python3
"""Synchronize JSON pack surfaces from the canonical release metadata."""

from __future__ import print_function

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "TwilightBossSliceB"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from TwilightBossSlice import release_metadata


MANIFESTS = (
    ROOT / "TwilightBossSliceB" / "manifest.json",
    ROOT / "TwilightBossSliceR" / "manifest.json",
)


def rendered_manifest(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    version = list(release_metadata.PACK_VERSION)
    document["header"]["version"] = version
    for module in document.get("modules", []):
        module["version"] = version
    for dependency in document.get("dependencies", []):
        dependency["version"] = version
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for path in MANIFESTS:
        rendered = rendered_manifest(path)
        if path.read_text(encoding="utf-8") != rendered:
            stale.append(path)
            if not args.check:
                path.write_text(rendered, encoding="utf-8")
    if args.check and stale:
        raise SystemExit(
            "release version drift: " + ", ".join(str(path) for path in stale)
        )
    print(
        "%s release version %s"
        % ("checked" if args.check else "synchronized", release_metadata.PACK_VERSION_STRING)
    )


if __name__ == "__main__":
    main()
