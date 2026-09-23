#!/usr/bin/env python3
"""Normalize the custom creative group without cross-category overrides."""

from __future__ import print_function

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATEGORY_ORDER = ("nature", "equipment", "construction", "items")
HIDDEN_TECHNICAL_BLOCKS = frozenset(
    "tf_slice:" + name
    for name in (
        "knight_phantom_boss_spawner",
        "naga_boss_spawner",
        "ur_ghast_boss_spawner",
        "temporary_builder_block",
        "restored_block",
        "reactor_debris",
        "tower_key_door",
        "fake_gold",
        "fake_diamond",
    )
)
WOOD_SHAPE_SUFFIXES = (
    "stairs",
    "slab",
    "button",
    "fence",
    "fence_gate",
    "pressure_plate",
    "door",
    "trapdoor",
    "sign",
    "wall_sign",
    "hanging_sign",
    "wall_hanging_sign",
    "banister",
    "chest",
)
OBSOLETE_WOOD_SUFFIXES = tuple(
    suffix for suffix in WOOD_SHAPE_SUFFIXES if suffix != "banister"
)
OBSOLETE_WOOD_BLOCK_IDS = tuple(
    "tf_slice:%s_%s" % (family, suffix)
    for family in ("dark", "mangrove")
    for suffix in OBSOLETE_WOOD_SUFFIXES
)
REQUIRED_EXTRA_PUBLIC_IDS = (
    "tf_slice:canopy_planks",
    "tf_slice:cicada",
    "tf_slice:fortification_scepter",
    "tf_slice:lifedrain_scepter",
    "tf_slice:liveroot",
    "tf_slice:twilight_scepter",
    "tf_slice:zombie_scepter",
    "tf_slice:hedge",
    "tf_slice:liveroot_block",
    "tf_slice:raw_ironwood",
    "tf_slice:root_block",
    "tf_slice:steeleaf_block",
    "tf_slice:transformation_powder",
)
HIDDEN_DYNAMIC_ITEM_IDS = frozenset(
    (
        "tf_slice:filled_magic_map",
        "tf_slice:filled_maze_map",
    )
)
VANILLA_WOOD_TEMPLATE_IDS = tuple(
    "minecraft:%s_%s" % (family, suffix)
    for family in ("dark_oak", "mangrove")
    for suffix in (
        "stairs",
        "slab",
        "button",
        "fence",
        "fence_gate",
        "pressure_plate",
        "door",
        "trapdoor",
        "sign",
        "hanging_sign",
    )
) + tuple(
    "minecraft:cherry_%s" % suffix
    for suffix in (
        "stairs",
        "slab",
        "button",
        "fence",
        "fence_gate",
        "pressure_plate",
        "door",
        "trapdoor",
    )
)
PUBLIC_WOOD_SHAPE_IDS = tuple(
    "tf_slice:%s_banister" % family
    for family in ("dark", "mangrove")
)
CANOPY_CONSTRUCTION_ORDER = (
    "tf_slice:canopy_log",
    "tf_slice:canopy_wood",
    "tf_slice:stripped_canopy_log",
    "tf_slice:stripped_canopy_wood",
    "tf_slice:canopy_planks",
    "tf_slice:canopy_banister",
    "tf_slice:canopy_bookshelf",
    "tf_slice:canopy_chest",
)
CANOPY_PUBLIC_IDS = CANOPY_CONSTRUCTION_ORDER
MIGRATED_WOOD_ALIAS_IDS = frozenset(
    "tf_slice:%s_%s" % (family, suffix)
    for family in ("dark", "mangrove")
    for suffix in WOOD_SHAPE_SUFFIXES
    if suffix not in ("banister", "chest")
) | frozenset(
    "tf_slice:canopy_%s" % suffix
    for suffix in (
        "stairs",
        "slab",
        "button",
        "fence",
        "fence_gate",
        "pressure_plate",
        "door",
        "trapdoor",
    )
)


def player_visible_wood_item(item_name):
    item_name = str(item_name)
    if item_name not in MIGRATED_WOOD_ALIAS_IDS:
        return item_name
    name = item_name.split(":", 1)[1]
    family, suffix = name.split("_", 1)
    vanilla_family = {
        "dark": "dark_oak",
        "canopy": "cherry",
    }.get(family, family)
    suffix = {
        "wall_sign": "sign",
        "wall_hanging_sign": "hanging_sign",
    }.get(suffix, suffix)
    return "minecraft:%s_%s" % (vanilla_family, suffix)


def order_canopy_construction(items):
    """Keep the Canopy family contiguous in the established wood order."""
    items = tuple(items)
    family = frozenset(CANOPY_CONSTRUCTION_ORDER)
    positions = [index for index, item in enumerate(items) if item in family]
    if not positions:
        return items
    first = min(positions)
    prefix = [
        item for index, item in enumerate(items)
        if index < first and item not in family
    ]
    suffix = [
        item for index, item in enumerate(items)
        if index >= first and item not in family
    ]
    ordered = [
        item for item in CANOPY_CONSTRUCTION_ORDER if item in items
    ]
    return tuple(prefix + ordered + suffix)
PUBLIC_TROPHY_IDS = tuple(
    "tf_slice:%s_trophy_item" % variant
    for variant in (
        "naga",
        "lich",
        "hydra",
        "ur_ghast",
        "knight_phantom",
        "minoshroom",
        "quest_ram",
    )
)
PUBLIC_TROPHY_BLOCK_IDS = tuple(
    identifier[: -len("_item")]
    for identifier in PUBLIC_TROPHY_IDS
)
INTERNAL_TROPHY_WALL_IDS = frozenset(
    identifier.replace("_trophy", "_wall_trophy")
    for identifier in PUBLIC_TROPHY_BLOCK_IDS
)
HIDDEN_TECHNICAL_BLOCKS = (
    HIDDEN_TECHNICAL_BLOCKS
    | INTERNAL_TROPHY_WALL_IDS
)


def _load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _registered_categories(bp):
    result = {}
    for path in (bp / "items").glob("*.json"):
        item = _load(path).get("minecraft:item", {})
        description = item.get("description", {})
        identifier = description.get("identifier")
        if identifier:
            result[identifier] = description.get("menu_category", {}).get(
                "category", description.get("category", "items")
            )
    for folder in ("blocks", "netease_blocks"):
        for path in (bp / folder).glob("*.json"):
            block = _load(path).get("minecraft:block", {})
            identifier = block.get("description", {}).get("identifier")
            if identifier:
                result[identifier] = "construction"
    return result


def modernize_item_menu_categories(bp):
    """Use the 1.21.60 menu category schema understood by the current client."""
    changed = 0
    for path in sorted((bp / "items").glob("*.json")):
        document = _load(path)
        item = document.get("minecraft:item", {})
        description = item.get("description", {})
        legacy_category = description.pop("category", None)
        if legacy_category is None:
            continue
        document["format_version"] = "1.21.60"
        description["menu_category"] = {"category": legacy_category}
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        changed += 1
    return changed


def modernize_item_icons(bp):
    """Replace the icon member rejected by the current 1.21 item schema."""
    changed = 0
    for path in sorted((bp / "items").glob("*.json")):
        document = _load(path)
        components = document.get("minecraft:item", {}).get("components", {})
        icon = components.get("minecraft:icon")
        if not isinstance(icon, dict) or "texture" not in icon:
            continue
        texture = icon.pop("texture")
        icon["textures"] = {"default": texture}
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        changed += 1
    return changed


def hide_technical_blocks(bp):
    """Keep runtime markers addressable without exposing them as player blocks."""
    changed = 0
    for identifier in sorted(HIDDEN_TECHNICAL_BLOCKS):
        name = identifier.split(":", 1)[1]
        path = bp / "netease_blocks" / (name + ".json")
        if not path.is_file():
            continue
        document = _load(path)
        description = document.get("minecraft:block", {}).get(
            "description", {}
        )
        if description.get("register_to_creative_menu") is False:
            continue
        description["register_to_creative_menu"] = False
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        changed += 1
    return changed


def show_migrated_wood_alias_blocks(bp):
    """Keep every public wood alias visible in the NetEase creative catalog."""
    changed = 0
    for identifier in sorted(MIGRATED_WOOD_ALIAS_IDS):
        name = identifier.split(":", 1)[1]
        path = bp / "netease_blocks" / (name + ".json")
        if not path.is_file():
            continue
        document = _load(path)
        description = document.get("minecraft:block", {}).get(
            "description", {}
        )
        if description.get("register_to_creative_menu") is True:
            continue
        description["register_to_creative_menu"] = True
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        changed += 1
    return changed


def suppress_catalog_auto_registration(bp, catalog_ids):
    """Let the explicit catalog be the only creative-menu registration."""
    catalog_ids = set(catalog_ids)
    changed = 0
    for path in sorted((bp / "items").glob("*.json")):
        document = _load(path)
        description = document.get("minecraft:item", {}).get(
            "description", {}
        )
        if description.get("identifier") not in catalog_ids:
            continue
        if description.pop("menu_category", None) is None:
            continue
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        changed += 1
    for folder in ("blocks", "netease_blocks"):
        for path in sorted((bp / folder).glob("*.json")):
            document = _load(path)
            description = document.get("minecraft:block", {}).get(
                "description", {}
            )
            if description.get("identifier") not in catalog_ids:
                continue
            if description.get("register_to_creative_menu") is False:
                continue
            description["register_to_creative_menu"] = False
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            changed += 1
    return changed


def _registered_block_ids(bp):
    result = set()
    for folder in ("blocks", "netease_blocks"):
        for path in (bp / folder).glob("*.json"):
            block = _load(path).get("minecraft:block", {})
            identifier = block.get("description", {}).get("identifier")
            if identifier:
                result.add(identifier)
    return result


def _catalog_category(identifier, block_ids):
    name = str(identifier).split(":", 1)[-1]
    if name.endswith("_spawn_egg"):
        return "nature"
    natural_tokens = (
        "sapling",
        "leaves",
        "fiddlehead",
        "mushgloom",
        "fallen_leaves",
        "huge_lily_pad",
        "huge_water_lily",
        "firefly",
        "hedge",
        "root_block",
        "liveroot",
    )
    if identifier in block_ids:
        if any(token in name for token in natural_tokens):
            return "nature"
        return "construction"
    equipment_suffixes = (
        "_sword",
        "_axe",
        "_pickaxe",
        "_shovel",
        "_hoe",
        "_helmet",
        "_chestplate",
        "_leggings",
        "_boots",
        "_shield",
        "_scepter",
    )
    if name.endswith(equipment_suffixes) or name in (
        "block_and_chain",
        "knightmetal_ring",
    ):
        return "equipment"
    return "items"


def _construction_order(identifier):
    name = str(identifier).split(":", 1)[-1]
    groups = (
        ("dark_", "hollow_dark", "darkwood"),
        (
            "towerwood",
            "cracked_towerwood",
            "mossy_towerwood",
            "infested_towerwood",
            "encased_towerwood",
            "vanishing",
            "unbreakable_vanishing",
            "locked_vanishing",
            "reappearing",
            "carminite",
            "ghast_trap",
            "experiment_115",
        ),
        ("mazestone", "cut_mazestone", "decorative_mazestone"),
        ("mangrove_", "hollow_mangrove"),
        ("underbrick", "knightmetal_block", "stronghold", "trophy_pedestal"),
        ("twilight_oak", "canopy_", "rainbow_oak"),
        ("nagastone", "etched_nagastone", "spiral_bricks"),
        ("trophy",),
    )
    for index, prefixes in enumerate(groups):
        if any(name.startswith(prefix) or prefix in name for prefix in prefixes):
            return index
    return len(groups)


def normalize_creative_catalog(root=ROOT):
    root = Path(root)
    bp = root / "TwilightBossSliceB"
    modernize_item_menu_categories(bp)
    modernize_item_icons(bp)
    hide_technical_blocks(bp)
    path = bp / "item_catalog" / "crafting_item_catalog.json"
    document = _load(path)
    catalog = document["minecraft:crafting_items_catalog"]
    ordered_items = []
    seen = set()
    group_identifier = None
    for category in catalog.get("categories", []):
        for group in category.get("groups", []):
            if group_identifier is None:
                group_identifier = group.get("group_identifier")
            for identifier in group.get("items", []):
                if identifier not in seen:
                    seen.add(identifier)
                    ordered_items.append(identifier)
    if group_identifier is None:
        group_identifier = {
            "icon": "tf_slice:forest_wyrm_spawn_egg",
            "name": "tf_slice:itemGroup.name.twilight_forest",
        }

    ordered_items = [
        identifier
        for identifier in ordered_items
        if identifier not in VANILLA_WOOD_TEMPLATE_IDS
        and identifier not in OBSOLETE_WOOD_BLOCK_IDS
        and identifier not in MIGRATED_WOOD_ALIAS_IDS
        and identifier not in HIDDEN_DYNAMIC_ITEM_IDS
    ]
    registered = _registered_categories(bp)
    for identifier in PUBLIC_WOOD_SHAPE_IDS:
        if identifier in registered and identifier not in ordered_items:
            ordered_items.append(identifier)
    for identifier in CANOPY_PUBLIC_IDS:
        if identifier in registered and identifier not in ordered_items:
            ordered_items.append(identifier)
    for identifier in PUBLIC_TROPHY_IDS:
        if identifier in registered and identifier not in ordered_items:
            ordered_items.append(identifier)
    for identifier in REQUIRED_EXTRA_PUBLIC_IDS:
        if identifier in registered and identifier not in ordered_items:
            ordered_items.append(identifier)

    block_ids = _registered_block_ids(bp)
    for identifier in PUBLIC_WOOD_SHAPE_IDS:
        if identifier.startswith("minecraft:"):
            registered[identifier] = "construction"
    grouped = dict((category, []) for category in CATEGORY_ORDER)
    for identifier in ordered_items:
        if identifier in HIDDEN_TECHNICAL_BLOCKS:
            continue
        if identifier not in registered and not identifier.endswith(
            "_spawn_egg"
        ):
            raise ValueError(
                "creative catalog contains an unregistered entry: %s"
                % identifier
            )
        category = _catalog_category(identifier, block_ids)
        grouped.setdefault(category, []).append(identifier)

    original_positions = {
        identifier: index for index, identifier in enumerate(ordered_items)
    }
    grouped["construction"].sort(
        key=lambda identifier: (
            _construction_order(identifier),
            original_positions[identifier],
        )
    )
    grouped["construction"] = list(
        order_canopy_construction(grouped["construction"])
    )
    suppress_catalog_auto_registration(bp, ordered_items)

    catalog["categories"] = [
        {
            "category_name": category,
            "groups": [
                {
                    "group_identifier": dict(group_identifier),
                    "items": grouped[category],
                }
            ],
        }
        for category in CATEGORY_ORDER
        if grouped.get(category)
    ]
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dict((key, len(value)) for key, value in grouped.items() if value)


if __name__ == "__main__":
    counts = normalize_creative_catalog()
    print(
        "normalized creative categories: "
        + ", ".join("%s=%d" % item for item in sorted(counts.items()))
    )
