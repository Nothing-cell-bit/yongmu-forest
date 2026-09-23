#!/usr/bin/env python3
"""Publish native wood-template items without rebuilding route content."""

from __future__ import print_function

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

try:
    from build_creative_catalog import normalize_creative_catalog
    from build_localization import build_localization
    from build_public_block_shapes import build as build_public_blocks
except ImportError:  # pragma: no cover - package import in tests
    from tools.build_creative_catalog import normalize_creative_catalog
    from tools.build_localization import build_localization
    from tools.build_public_block_shapes import build as build_public_blocks

from TwilightBossSlice import vanilla_block_adapter_logic


def migrate_recipe_document(document):
    changed = False
    for key in ("minecraft:recipe_shaped", "minecraft:recipe_shapeless"):
        recipe = document.get(key)
        if not isinstance(recipe, dict):
            continue
        result = recipe.get("result")
        if not isinstance(result, dict):
            continue
        item_name = str(result.get("item", ""))
        public_name = vanilla_block_adapter_logic.player_visible_wood_item(
            item_name
        )
        if public_name == item_name:
            continue
        result["item"] = public_name
        changed = True
    return changed


def migrate_recipe_outputs():
    changed = 0
    for path in sorted((BP / "recipes").glob("*.recipe.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if not migrate_recipe_document(document):
            continue
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        changed += 1
    return changed


def build():
    public_blocks = build_public_blocks()
    recipes = migrate_recipe_outputs()
    creative = normalize_creative_catalog()
    localization = build_localization()
    return {
        "publicBlocks": public_blocks,
        "recipes": recipes,
        "creative": creative,
        "localization": localization,
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True))
