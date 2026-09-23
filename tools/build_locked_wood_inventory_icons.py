#!/usr/bin/env python3
"""Rebuild wood inventory icons from upstream Java models and item art."""

from __future__ import annotations

import json
from pathlib import Path

try:
    import build_public_block_shapes as public_blocks
except ImportError:  # pragma: no cover - package import in tests
    from tools import build_public_block_shapes as public_blocks


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_ICON_SUFFIXES = ()


def build(root=ROOT):
    # Deprecated aliases now use native vanilla items.  Keep this entry point
    # as a no-op so old local scripts cannot recreate deleted icon artifacts.
    Path(root)
    return ()


if __name__ == "__main__":
    result = build()
    print("rebuilt %d upstream wood inventory icons" % len(result))
