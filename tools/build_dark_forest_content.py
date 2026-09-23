#!/usr/bin/env python3
"""Build Dark Forest wood, trees, mobs, spawn rules and public registries."""

from __future__ import print_function

import copy
import json
import math
import random
import shutil
import sys
from pathlib import Path

from PIL import Image

from build_creative_catalog import (
    normalize_creative_catalog,
    player_visible_wood_item,
)
from build_localization import build_localization
from build_ruin_structures import SparseStructure, write_mcstructure
from landmark_surface_decorations import (
    normalize_landmark_surface_decorations,
)
from native_structure_worldgen_safety import guard_native_structure_rules
try:
    from build_public_block_shapes import build as build_public_block_shapes
except ImportError:  # pragma: no cover - package import in tests
    from tools.build_public_block_shapes import build as build_public_block_shapes


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
UPSTREAM = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
)

# The previous 16-candidate aggregate -> scatter -> search/sequence graph
# fail-fasted NetEase's native Chunk PP worker. One bounded search per direct
# rule attempt avoids both nested job fan-out and the center-biome floor-
# projection stall observed during native dimension streaming.
SAFE_DARK_FOREST_TREE_ATTEMPTS = 16
SAFE_DARKWOOD_TRUNK_HEIGHT_BASE = 16
SAFE_DARKWOOD_TRUNK_HEIGHT_VARIANCE = 8
SAFE_DARKWOOD_CANOPY_RADIUS = 6
SAFE_DARKWOOD_CANOPY_HEIGHT = 4
SAFE_DARK_FOREST_BIRCH_WEIGHT = 4
SAFE_DARK_FOREST_OAK_WEIGHT = 3
SAFE_DARK_FOREST_DARKWOOD_WEIGHT = 93
SAFE_DARK_FOREST_TREE_SEARCH_DEPTH = 64
SAFE_DARK_FOREST_TREE_SEARCH_ABOVE_REFERENCE = 32
SAFE_DARK_FOREST_TREE_RING_RADIUS = 96
SAFE_DARK_FOREST_TREE_RING_MAX_RISE = 6

DARK_BLOCKS = (
    "dark_log",
    "dark_wood",
    "stripped_dark_log",
    "stripped_dark_wood",
    "dark_leaves",
    "hardened_dark_leaves",
    "darkwood_sapling",
    "hollow_dark_log_horizontal",
    "hollow_dark_log_vertical",
    "hollow_dark_log_climbable",
    "dark_planks",
    "dark_banister",
)
INTERNAL_DARK_BLOCKS = (
    "hardened_dark_leaves_center",
    "dark_log_vertical",
)
AXIS_BLOCKS = frozenset(
    (
        "dark_log",
        "dark_wood",
        "stripped_dark_log",
        "stripped_dark_wood",
    )
)
NO_COLLISION_BLOCKS = frozenset(
    (
        "darkwood_sapling",
    )
)

NAMES = {
    "dark_log": ("Dark Log", u"黑木原木"),
    "dark_wood": ("Dark Wood", u"黑木"),
    "stripped_dark_log": ("Stripped Dark Log", u"去皮黑木原木"),
    "stripped_dark_wood": ("Stripped Dark Wood", u"去皮黑木"),
    "dark_leaves": ("Dark Leaves", u"黑木树叶"),
    "hardened_dark_leaves": ("Hardened Dark Leaves", u"硬化黑木树叶"),
    "darkwood_sapling": ("Darkwood Sapling", u"黑木树苗"),
    "hollow_dark_log_horizontal": ("Horizontal Hollow Dark Log", u"横向中空黑木原木"),
    "hollow_dark_log_vertical": ("Vertical Hollow Dark Log", u"竖向中空黑木原木"),
    "hollow_dark_log_climbable": ("Climbable Hollow Dark Log", u"可攀爬中空黑木原木"),
    "dark_planks": ("Darkwood Planks", u"黑木木板"),
    "dark_stairs": ("Darkwood Stairs", u"黑木楼梯"),
    "dark_slab": ("Darkwood Slab", u"黑木台阶"),
    "dark_button": ("Darkwood Button", u"黑木按钮"),
    "dark_fence": ("Darkwood Fence", u"黑木栅栏"),
    "dark_fence_gate": ("Darkwood Fence Gate", u"黑木栅栏门"),
    "dark_pressure_plate": ("Darkwood Pressure Plate", u"黑木压力板"),
    "dark_door": ("Darkwood Door", u"黑木门"),
    "dark_trapdoor": ("Darkwood Trapdoor", u"黑木活板门"),
    "dark_sign": ("Darkwood Sign", u"黑木告示牌"),
    "dark_wall_sign": ("Wall Darkwood Sign", u"墙上黑木告示牌"),
    "dark_hanging_sign": ("Darkwood Hanging Sign", u"黑木悬挂告示牌"),
    "dark_wall_hanging_sign": ("Wall Darkwood Hanging Sign", u"墙上黑木悬挂告示牌"),
    "dark_banister": ("Darkwood Banister", u"黑木栏杆"),
    "dark_boat": ("Darkwood Boat", u"黑木船"),
    "dark_chest_boat": ("Darkwood Chest Boat", u"黑木运输船"),
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def copy_texture(source, target):
    source_path = UPSTREAM / "textures" / source
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_path), str(target))


def copy_tinted_texture(source, target, tint):
    """Bake Java's foliage multiplier into a NetEase-safe RGBA texture."""
    source_path = UPSTREAM / "textures" / source
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        rgba = image.convert("RGBA")
        pixels = []
        for red, green, blue, alpha in rgba.getdata():
            source_channels = (red, green, blue)
            pixels.append(
                tuple(
                    (source_channels[channel] * tint[channel] + 127) // 255
                    for channel in range(3)
                )
                + (alpha,)
            )
        rgba.putdata(pixels)
        rgba.save(target, format="PNG")


def texture_sources(identifier):
    if identifier in ("dark_log", "dark_wood", "dark_log_vertical"):
        side = "block/dark_log.png"
        top = (
            "block/dark_log_top.png"
            if identifier in ("dark_log", "dark_log_vertical")
            else side
        )
        return side, top
    if identifier in ("stripped_dark_log", "stripped_dark_wood"):
        side = "block/stripped_dark_log.png"
        top = (
            "block/stripped_dark_log_top.png"
            if identifier == "stripped_dark_log"
            else side
        )
        return side, top
    if identifier in (
        "dark_leaves",
        "hardened_dark_leaves",
        "hardened_dark_leaves_center",
    ):
        return "block/darkwood_leaves.png", None
    if identifier == "darkwood_sapling":
        return "block/darkwood_sapling.png", None
    if identifier == "dark_door":
        return "block/wood/door/darkwood_lower.png", None
    if identifier == "dark_trapdoor":
        return "block/wood/trapdoor/darkwood_trapdoor.png", None
    if identifier.startswith("hollow_dark_log"):
        return "block/dark_log.png", None
    return "block/wood/planks_darkwood_0.png", None


def axis_block(identifier):
    side_key = "tf_slice:%s" % identifier
    top_key = side_key + "_top"
    return {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": {
                "identifier": side_key,
                "register_to_creative_menu": True,
                # A generated tree does not always provide an explicit custom
                # state.  Keep the vertical axis first so its fallback state
                # renders bark on the four trunk sides instead of end grain.
                "states": {"tf_slice:axis": ["y", "x", "z"]},
            },
            "components": {
                "minecraft:destructible_by_mining": {"seconds_to_destroy": 2.0},
                "minecraft:destructible_by_explosion": {
                    "explosion_resistance": 3.0
                },
                "minecraft:geometry": "geometry.tf_slice.courtyard_cube",
                "minecraft:material_instances": {
                    "*": {"texture": side_key, "render_method": "opaque"},
                    "side": {"texture": side_key, "render_method": "opaque"},
                    "top": {"texture": top_key, "render_method": "opaque"},
                    "bottom": {"texture": top_key, "render_method": "opaque"},
                },
                "netease:aabb": {
                    "collision": {
                        "min": [0.0, 0.0, 0.0],
                        "max": [1.0, 1.0, 1.0],
                    },
                    "clip": {
                        "min": [0.0, 0.0, 0.0],
                        "max": [1.0, 1.0, 1.0],
                    },
                },
                "netease:render_layer": {"value": "opaque"},
                "netease:solid": {"value": True},
                "netease:pathable": {"value": False},
            },
            "permutations": [
                {
                    "condition": "query.block_state('tf_slice:axis') == 'x'",
                    "components": {
                        "minecraft:transformation": {"rotation": [0, 0, 90]}
                    },
                },
                {
                    "condition": "query.block_state('tf_slice:axis') == 'z'",
                    "components": {
                        "minecraft:transformation": {"rotation": [90, 0, 0]}
                    },
                },
            ],
        },
    }


def vertical_log_block():
    """State-free worldgen log; native tree placement cannot rotate it."""
    return {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": {
                "identifier": "tf_slice:dark_log_vertical",
                "register_to_creative_menu": False,
            },
            "components": {
                "minecraft:destructible_by_mining": {
                    "seconds_to_destroy": 2.0
                },
                "minecraft:destructible_by_explosion": {
                    "explosion_resistance": 3.0
                },
                "minecraft:geometry": "geometry.tf_slice.courtyard_cube",
                "minecraft:material_instances": {
                    "*": {
                        "texture": "tf_slice:dark_log_vertical",
                        "render_method": "opaque",
                    },
                    "side": {
                        "texture": "tf_slice:dark_log_vertical",
                        "render_method": "opaque",
                    },
                    "top": {
                        "texture": "tf_slice:dark_log_vertical_top",
                        "render_method": "opaque",
                    },
                    "bottom": {
                        "texture": "tf_slice:dark_log_vertical_top",
                        "render_method": "opaque",
                    },
                },
                "netease:aabb": {
                    "collision": {
                        "min": [0.0, 0.0, 0.0],
                        "max": [1.0, 1.0, 1.0],
                    },
                    "clip": {
                        "min": [0.0, 0.0, 0.0],
                        "max": [1.0, 1.0, 1.0],
                    },
                },
                "netease:render_layer": {"value": "opaque"},
                "netease:solid": {"value": True},
                "netease:pathable": {"value": False},
            },
        },
    }


def ordinary_block(identifier, register_to_creative_menu=True):
    translucent = identifier in (
        "dark_leaves",
        "hardened_dark_leaves",
        "hardened_dark_leaves_center",
        "darkwood_sapling",
    )
    no_collision = identifier in NO_COLLISION_BLOCKS
    is_leaf = identifier in (
        "dark_leaves",
        "hardened_dark_leaves",
        "hardened_dark_leaves_center",
    )
    is_hardened_leaf = identifier in (
        "hardened_dark_leaves",
        "hardened_dark_leaves_center",
    )
    components = {
        "minecraft:destroy_time": {"value": 2.0 if is_leaf else (0.2 if translucent else 2.0)},
        "minecraft:explosion_resistance": {
            "value": 10.0 if is_leaf else (1.0 if translucent else 3.0)
        },
        "netease:render_layer": {
            "value": (
                "opaque"
                if is_hardened_leaf
                else ("optionalAlpha" if translucent else "opaque")
            )
        },
        "netease:solid": {"value": not no_collision},
        "netease:pathable": {"value": False},
    }
    if identifier == "darkwood_sapling":
        components["netease:random_tick"] = {
            "enable": True,
            "tick_to_script": True,
        }
    if no_collision:
        components["netease:aabb"] = {
            "collision": {
                "min": [0.0, 0.0, 0.0],
                "max": [0.0, 0.0, 0.0],
            },
            "clip": {
                "min": [0.125, 0.0, 0.125],
                "max": [0.875, 0.875, 0.875],
            },
        }
    description = {
        "identifier": "tf_slice:" + identifier,
        "register_to_creative_menu": register_to_creative_menu,
    }
    if identifier == "darkwood_sapling":
        description["states"] = {"tf_slice:growth_stage": [0, 1]}
    return {
        "format_version": "1.10.0",
        "minecraft:block": {
            "description": description,
            "components": components,
        },
    }


def item_document(identifier):
    return {
        "format_version": "1.21.60",
        "minecraft:item": {
            "description": {
                "identifier": "tf_slice:" + identifier,
                "menu_category": {"category": "nature"},
            },
            "components": {
                "minecraft:display_name": {
                    "value": "item.tf_slice:%s.name" % identifier
                },
                "minecraft:icon": {
                    "textures": {"default": "tf_slice:" + identifier}
                },
                "minecraft:max_stack_size": 1,
                "minecraft:hand_equipped": True,
            },
        },
    }


def shaped(identifier, pattern, keys, count=1, result_item=None):
    return {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": "tf_slice:" + identifier},
            "tags": ["crafting_table"],
            "pattern": pattern,
            "key": dict((key, {"item": value}) for key, value in keys.items()),
            "unlock": {"context": "AlwaysUnlocked"},
            "result": {
                "item": player_visible_wood_item(
                    result_item or ("tf_slice:" + identifier)
                ),
                "count": count,
            },
        },
    }


def shapeless(identifier, ingredients, count=1):
    return {
        "format_version": "1.20.10",
        "minecraft:recipe_shapeless": {
            "description": {"identifier": "tf_slice:" + identifier},
            "tags": ["crafting_table"],
            "ingredients": [{"item": item} for item in ingredients],
            "unlock": {"context": "AlwaysUnlocked"},
            "result": {
                "item": player_visible_wood_item(
                    "tf_slice:" + identifier
                ),
                "count": count,
            },
        },
    }


def build_blocks_and_items():
    terrain = load(RP / "textures" / "terrain_texture.json")
    client_blocks = load(RP / "blocks.json")
    for identifier in DARK_BLOCKS + INTERNAL_DARK_BLOCKS:
        if identifier in AXIS_BLOCKS:
            document = axis_block(identifier)
        elif identifier == "dark_log_vertical":
            document = vertical_log_block()
        else:
            document = ordinary_block(
                identifier,
                register_to_creative_menu=(identifier in DARK_BLOCKS),
            )
        write(BP / "netease_blocks" / (identifier + ".json"), document)
        side_source, top_source = texture_sources(identifier)
        texture_key = "tf_slice:" + identifier
        tint = {
            "dark_leaves": (0x3B, 0x5E, 0x3F),
            "hardened_dark_leaves": (0x3B, 0x5E, 0x3F),
            # FoliageColorHandler normalizes the noise to [0, 1] and then
            # compares it with -0.1, making E94E14 the effective 4.3.2508
            # runtime color at every coordinate.
            "hardened_dark_leaves_center": (0xE9, 0x4E, 0x14),
        }.get(identifier)
        texture_target = RP / "textures" / "blocks" / (identifier + ".png")
        if tint:
            copy_tinted_texture(side_source, texture_target, tint)
        else:
            copy_texture(side_source, texture_target)
        terrain["texture_data"][texture_key] = {
            "textures": "textures/blocks/" + identifier
        }
        if top_source:
            copy_texture(
                top_source,
                RP / "textures" / "blocks" / (identifier + "_top.png"),
            )
            terrain["texture_data"][texture_key + "_top"] = {
                "textures": "textures/blocks/" + identifier + "_top"
            }
            client_blocks[texture_key] = {
                "textures": {
                    "up": texture_key + "_top",
                    "down": texture_key + "_top",
                    "side": texture_key,
                },
                "sound": "wood",
            }
        else:
            client_blocks[texture_key] = {
                "textures": texture_key,
                "sound": "grass" if "leaves" in identifier else "wood",
            }
    write(RP / "textures" / "terrain_texture.json", terrain)
    write(RP / "blocks.json", client_blocks)

    item_atlas = load(RP / "textures" / "item_texture.json")
    for identifier, source in (
        ("dark_boat", "item/dark_boat.png"),
        ("dark_chest_boat", "item/dark_chest_boat.png"),
    ):
        write(BP / "items" / (identifier + ".item.json"), item_document(identifier))
        copy_texture(source, RP / "textures" / "items" / (identifier + ".png"))
        item_atlas["texture_data"]["tf_slice:" + identifier] = {
            "textures": "textures/items/" + identifier
        }
    write(RP / "textures" / "item_texture.json", item_atlas)

    recipes = {
        "dark_planks": shapeless(
            "dark_planks", ["tf_slice:dark_log"], 4
        ),
        "dark_stairs": shaped(
            "dark_stairs", ["#  ", "## ", "###"], {"#": "tf_slice:dark_planks"}, 4
        ),
        "dark_slab": shaped(
            "dark_slab", ["###"], {"#": "tf_slice:dark_planks"}, 6
        ),
        "dark_fence": shaped(
            "dark_fence", ["#S#", "#S#"], {"#": "tf_slice:dark_planks", "S": "minecraft:stick"}, 3
        ),
        "dark_fence_gate": shaped(
            "dark_fence_gate", ["S#S", "S#S"], {"#": "tf_slice:dark_planks", "S": "minecraft:stick"}
        ),
        "dark_banister": shaped(
            "dark_banister",
            ["---", "| |"],
            {"-": "minecraft:dark_oak_slab", "|": "minecraft:stick"},
            3,
        ),
        "dark_door": shaped(
            "dark_door", ["##", "##", "##"], {"#": "tf_slice:dark_planks"}, 3
        ),
        "dark_trapdoor": shaped(
            "dark_trapdoor", ["###", "###"], {"#": "tf_slice:dark_planks"}, 2
        ),
        "dark_boat": shaped(
            "dark_boat", ["# #", "###"], {"#": "tf_slice:dark_planks"}
        ),
        "dark_chest_boat": shapeless(
            "dark_chest_boat", ["tf_slice:dark_boat", "minecraft:chest"]
        ),
    }
    for identifier, recipe in recipes.items():
        write(BP / "recipes" / (identifier + ".recipe.json"), recipe)
    register_public_content(list(DARK_BLOCKS) + ["dark_boat", "dark_chest_boat"])


def register_public_content(identifiers):
    creative_path = BP / "item_catalog" / "crafting_item_catalog.json"
    creative = load(creative_path)
    items = creative["minecraft:crafting_items_catalog"]["categories"][0][
        "groups"
    ][0]["items"]
    for identifier in identifiers:
        full_id = "tf_slice:" + identifier
        if full_id not in items:
            items.append(full_id)
    write(creative_path, creative)
    for language, index in (("en_US.lang", 0), ("zh_CN.lang", 1)):
        path = RP / "texts" / language
        lines = path.read_text(encoding="utf-8").splitlines()
        by_key = dict(
            (line.split("=", 1)[0], position)
            for position, line in enumerate(lines)
            if "=" in line
        )
        for identifier in identifiers:
            prefix = "item" if identifier in ("dark_boat", "dark_chest_boat") else "tile"
            key = "%s.tf_slice:%s.name" % (prefix, identifier)
            rendered = key + "=" + NAMES[identifier][index]
            if key in by_key:
                lines[by_key[key]] = rendered
            else:
                by_key[key] = len(lines)
                lines.append(rendered)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def java_round(value):
    return int(math.floor(float(value) + 0.5))


def translated(position, distance, angle, tilt):
    radians = float(angle) * math.pi * 2.0
    tilt_radians = float(tilt) * math.pi
    return (
        position[0]
        + java_round(math.sin(radians) * math.sin(tilt_radians) * distance),
        position[1] + java_round(math.cos(tilt_radians) * distance),
        position[2]
        + java_round(math.cos(radians) * math.sin(tilt_radians) * distance),
    )


def place_line(structure, start, end, block, weighted_blocks=None, rng=None):
    dx = int(end[0]) - int(start[0])
    dy = int(end[1]) - int(start[1])
    dz = int(end[2]) - int(start[2])
    steps = max(abs(dx), abs(dy), abs(dz), 1)
    for step in range(steps + 1):
        progress = float(step) / float(steps)
        selected = block
        if weighted_blocks and rng is not None:
            roll = rng.randrange(sum(weight for _name, weight in weighted_blocks))
            for name, weight in weighted_blocks:
                if roll < weight:
                    selected = name
                    break
                roll -= weight
        structure.set(
            java_round(start[0] + dx * progress),
            java_round(start[1] + dy * progress),
            java_round(start[2] + dz * progress),
            selected,
        )


def place_leaf(structure, position, leaf_block):
    if tuple(position) not in structure.blocks:
        structure.set(position[0], position[1], position[2], leaf_block)


def place_source_spheroid(structure, center, radius, leaf_block, rng):
    """Port LeafSpheroidFoliagePlacer's biased oval and 2x2 shag."""
    horizontal = float(radius)
    source_horizontal = 4.5
    vertical = 2.25
    bias = 0.45
    horizontal_squared = horizontal * horizontal
    vertical_squared = vertical * vertical
    super_squared = horizontal_squared * vertical_squared

    def place_symmetric(dx, dy, dz):
        for x, z in (
            (dx, dz),
            (-dx, -dz),
            (-dz, dx),
            (dz, -dx),
        ):
            place_leaf(
                structure,
                (center[0] + x, center[1] + dy, center[2] + z),
                leaf_block,
            )

    # FeaturePlacers.placeSpheroid builds the centre axes separately, then
    # mirrors one quadrant.  In particular, the negative half uses y + bias;
    # applying the bias to a negative dy makes the underside much too full.
    place_leaf(structure, center, leaf_block)
    for dy in range(0, int(vertical) + 1):
        place_leaf(
            structure,
            (center[0], center[1] + dy, center[2]),
            leaf_block,
        )
        place_leaf(
            structure,
            (center[0], center[1] - dy, center[2]),
            leaf_block,
        )
    for dx in range(0, int(horizontal) + 1):
        for dz in range(1, int(horizontal) + 1):
            radial_squared = dx * dx + dz * dz
            if radial_squared > horizontal_squared:
                continue
            place_symmetric(dx, 0, dz)
            scaled_radial = radial_squared * vertical_squared
            for dy in range(1, int(vertical) + 1):
                upper = (dy - bias) * (dy - bias) * horizontal_squared
                if scaled_radial + upper <= super_squared:
                    place_symmetric(dx, dy, dz)
                lower = (dy + bias) * (dy + bias) * horizontal_squared
                if scaled_radial + lower <= super_squared:
                    place_symmetric(dx, -dy, dz)

    for _index in range(36):
        random_yaw = rng.random() * math.pi * 2.0
        random_pitch = rng.random() * 2.0 - 1.0
        y_unit = math.sqrt(max(0.0, 1.0 - random_pitch * random_pitch))
        # Upstream deliberately uses the configured 4.5 radius here, not the
        # random-expanded 5.5 radius used by the spheroid body.
        x_offset = y_unit * math.cos(random_yaw) * (source_horizontal - 1.0)
        z_offset = y_unit * math.sin(random_yaw) * (source_horizontal - 1.0)
        placement = (
            center[0] + int(x_offset + (int(x_offset) >> 31)),
            center[1] + int(random_pitch * (vertical + 0.25) + bias),
            center[2] + int(z_offset + (int(z_offset) >> 31)),
        )
        for dx, dz in ((0, 0), (1, 0), (0, 1), (1, 1)):
            place_leaf(
                structure,
                (placement[0] + dx, placement[1], placement[2] + dz),
                leaf_block,
            )


def darkwood_tree_structure(profile_name, leaf_block, variant):
    rng = random.Random(4312508 + variant * 97 + sum(ord(c) for c in profile_name))
    center = 18
    base_y = 10
    configured_height = 9 + rng.randrange(2) + rng.randrange(2)
    structure = SparseStructure(
        (37, 34, 37), "%s_v%02d" % (profile_name, variant)
    )
    log_block = "tf_slice:dark_log_vertical"
    for y in range(base_y, base_y + configured_height + 1):
        structure.set(center, y, center, log_block)

    foliage_centers = [(center, base_y + configured_height, center)]
    branch_offset = rng.random()
    branch_ends = []
    for branch in range(4):
        start = (
            center,
            base_y + configured_height - 3 + branch,
            center,
        )
        end = translated(start, 8.0, 0.23 * branch + branch_offset, 0.23)
        place_line(structure, start, end, log_block)
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            structure.set(end[0] + dx, end[1], end[2] + dz, log_block)
        foliage_centers.append(end)
        branch_ends.append(list(end))

    foliage_radii = []
    for foliage_center in foliage_centers:
        radius = 4.5 + rng.randrange(2)
        foliage_radii.append(radius)
        place_source_spheroid(
            structure, foliage_center, radius, leaf_block, rng
        )

    # NetEase structure placement would write these roots through authored
    # underbrick.  Keep them out of the unconditional tree template; a
    # natural-block-only ore cluster is sequenced after the tree instead.
    root_count = 0
    root_ends = []
    metadata = {
        "variant": variant,
        "configuredHeight": configured_height,
        "trunkBlockCount": configured_height + 1,
        "branchCount": 4,
        "branchEnds": branch_ends,
        "foliageRadii": foliage_radii,
        "rootCount": root_count,
        "rootEnds": root_ends,
        "center": [center, base_y, center],
        "bounds": list(structure.size),
    }
    return structure, metadata


def single_block_feature(identifier, block, bottom):
    return {
        "format_version": "1.21.40",
        "minecraft:single_block_feature": {
            "description": {"identifier": "tf_slice:" + identifier},
            "places_block": [{"block": block, "weight": 1}],
            "enforce_placement_rules": False,
            "enforce_survivability_rules": False,
            "may_replace": [
                "minecraft:air",
                "minecraft:tallgrass",
                "minecraft:short_grass",
                "minecraft:double_plant",
                "tf_slice:dark_leaves",
                "tf_slice:hardened_dark_leaves",
                "tf_slice:hardened_dark_leaves_center",
            ],
            "may_attach_to": {
                "auto_rotate": False,
                "min_sides_must_attach": 1,
                "bottom": list(bottom),
            },
        },
    }


def native_structure_feature(identifier, structure_name):
    return {
        "format_version": "1.14.0",
        "netease:structure_feature": {
            "description": {"identifier": "tf_slice:" + identifier},
            "places_structure": structure_name,
            "rotation": 0,
        },
    }


def native_darkwood_tree_feature(identifier, leaf_block):
    """Build a dense, branching engine tree without a nested feature graph."""
    replaceable = [
        "minecraft:air",
        "minecraft:tallgrass",
        "minecraft:double_plant",
        "tf_slice:fallen_leaves",
        "tf_slice:dark_leaves",
        "tf_slice:hardened_dark_leaves",
        "tf_slice:hardened_dark_leaves_center",
    ]
    grow_through = list(replaceable)
    return {
        "format_version": "1.14.0",
        "minecraft:tree_feature": {
            "description": {"identifier": "tf_slice:" + identifier},
            "fancy_trunk": {
                "trunk_width": 1,
                "trunk_height": {
                    "base": SAFE_DARKWOOD_TRUNK_HEIGHT_BASE,
                    "variance": SAFE_DARKWOOD_TRUNK_HEIGHT_VARIANCE,
                    "scale": 1.0,
                },
                "trunk_block": {"name": "tf_slice:dark_log_vertical"},
                "branches": {
                    "slope": 0.2,
                    "density": 0.35,
                    "min_altitude_factor": 0.65,
                },
                "width_scale": 1.0,
                "foliage_altitude_factor": 0.65,
            },
            "fancy_canopy": {
                "height": SAFE_DARKWOOD_CANOPY_HEIGHT,
                "radius": SAFE_DARKWOOD_CANOPY_RADIUS,
                "leaf_block": {"name": leaf_block},
            },
            "base_block": ["minecraft:dirt"],
            "may_grow_on": [
                "minecraft:grass",
                "minecraft:grass_block",
                "minecraft:dirt",
                "minecraft:podzol",
            ],
            "may_replace": replaceable,
            "may_grow_through": grow_through,
        },
    }


def conditional_ore_feature(identifier, block, count, replaceable):
    return {
        "format_version": "1.16.0",
        "minecraft:ore_feature": {
            "description": {"identifier": "tf_slice:" + identifier},
            "count": int(count),
            "replace_rules": [
                {
                    "places_block": block,
                    "may_replace": [
                        {"name": name} for name in replaceable
                    ],
                }
            ],
        },
    }


def offset_feature(identifier, placed_feature, offset):
    return {
        "format_version": "1.20.30",
        "minecraft:scatter_feature": {
            "description": {"identifier": "tf_slice:" + identifier},
            "places_feature": "tf_slice:" + placed_feature,
            "distribution": {
                "iterations": 1,
                "coordinate_eval_order": "xzy",
                "x": -int(offset[0]),
                "y": -int(offset[1]),
                "z": -int(offset[2]),
            },
        },
    }


def sequence_feature(identifier, features):
    return {
        "format_version": "1.20.30",
        "minecraft:sequence_feature": {
            "description": {"identifier": "tf_slice:" + identifier},
            "features": ["tf_slice:" + feature for feature in features],
        },
    }


def downward_search_feature(identifier, placed_feature, depth):
    return {
        "format_version": "1.13.0",
        "minecraft:search_feature": {
            "description": {"identifier": "tf_slice:" + identifier},
            "places_feature": "tf_slice:" + placed_feature,
            "search_volume": {
                "min": [0, -int(depth), 0],
                "max": [0, 0, 0],
            },
            "search_axis": "-y",
            "required_successes": 1,
        },
    }


def build_chunk_safe_darkwood_tree(identifier, leaf_block):
    """Retire the unsafe 37x37 templates and emit one native tree feature."""
    feature_dir = BP / "netease_features"
    structure_root = (
        BP / "structures" / "tf_slice" / "dark_forest" / "trees" / identifier
    )
    if structure_root.is_dir():
        shutil.rmtree(str(structure_root))
    for suffix in ("structure", "offset", "sequence"):
        for stale_feature in feature_dir.glob(
            identifier + "_v*_" + suffix + "_feature.json"
        ):
            stale_feature.unlink()
    for stale_suffix in ("ground_anchor", "ground_search", "anchor"):
        stale_feature = feature_dir / (
            identifier + "_" + stale_suffix + "_feature.json"
        )
        if stale_feature.exists():
            stale_feature.unlink()

    write(
        feature_dir / (identifier + ".json"),
        native_darkwood_tree_feature(identifier, leaf_block),
    )

    # Preserve source-shape metadata for parity documentation without routing
    # natural worldgen through the retired structure templates.
    variants = []
    for variant in range(16):
        _structure, metadata = darkwood_tree_structure(
            identifier, leaf_block, variant
        )
        variants.append(metadata)
    return variants


def dark_forest_filter(biome_key):
    return [
        {
            "test": "has_biome_tag",
            "operator": "==",
            "value": "dm33027004",
        },
        {
            "test": "has_biome_tag",
            "operator": "==",
            "value": "tf_slice_biome_" + biome_key,
        },
    ]


def scatter_tree_batch(identifier, placed_feature, base_count):
    return {
        "format_version": "1.21.10",
        "minecraft:scatter_feature": {
            "description": {"identifier": "tf_slice:" + identifier},
            "places_feature": "tf_slice:" + placed_feature,
            "project_input_to_floor": True,
            "distribution": {
                "iterations": (
                    "%d + (math.random_integer(0, 9) == 0 ? 1 : 0)"
                    % base_count
                ),
                "coordinate_eval_order": "xzy",
                "x": {"distribution": "uniform", "extent": [0, 15]},
                "y": 0,
                "z": {"distribution": "uniform", "extent": [0, 15]},
            },
        },
    }


def dark_forest_tree_rule_iterations(biome_key):
    """Return the native rule gate for one Dark Forest tree profile."""
    return SAFE_DARK_FOREST_TREE_ATTEMPTS


def _offset_molang(expression, offset):
    offset = int(offset)
    if offset < 0:
        return "(%s - %d)" % (expression, abs(offset))
    if offset > 0:
        return "(%s + %d)" % (expression, offset)
    return "(%s)" % expression


def dark_forest_center_ground_reference():
    """Estimate untouched ground from a ring outside the 112x112 tower."""
    center_x = "math.floor((variable.originx + 128) / 256) * 256 + 8"
    center_z = "math.floor((variable.originz + 128) / 256) * 256 + 8"
    radius = SAFE_DARK_FOREST_TREE_RING_RADIUS
    offsets = (
        (-radius, -radius),
        (-radius, 0),
        (-radius, radius),
        (0, -radius),
        (0, radius),
        (radius, -radius),
        (radius, 0),
        (radius, radius),
    )
    samples = [
        "query.get_height_at(%s, %s)"
        % (
            _offset_molang(center_x, offset_x),
            _offset_molang(center_z, offset_z),
        )
        for offset_x, offset_z in offsets
    ]
    minimum = samples[0]
    maximum = samples[0]
    for sample in samples[1:]:
        minimum = "math.min(%s, %s)" % (minimum, sample)
        maximum = "math.max(%s, %s)" % (maximum, sample)
    return "math.floor(math.min(%s, %s + %d))" % (
        maximum,
        minimum,
        SAFE_DARK_FOREST_TREE_RING_MAX_RISE,
    )


def dark_forest_tree_rule_y(biome_key):
    local_height = "query.get_height_at(variable.worldx, variable.worldz)"
    if biome_key != "dark_forest_center":
        return local_height
    return "math.min(%s, (%s) + %d)" % (
        local_height,
        dark_forest_center_ground_reference(),
        SAFE_DARK_FOREST_TREE_SEARCH_ABOVE_REFERENCE,
    )


def remove_retired_dark_forest_tree_graph(biome_key):
    """Delete native feature graphs retired after the Chunk PP fail-fast."""
    feature_dir = BP / "netease_features"
    stale = set(feature_dir.glob(biome_key + "_*batch*_feature.json"))
    stale.add(
        feature_dir
        / (biome_key + "_tree_profile_landmark_surface_project_feature.json")
    )
    if biome_key == "dark_forest_center":
        stale.update(
            feature_dir.glob(
                "dark_forest_center_*aerial*_feature.json"
            )
        )
        stale.add(
            feature_dir
            / "dark_forest_center_tree_cleanup_sequence_feature.json"
        )
        stale.add(
            feature_dir
            / "dark_forest_center_tree_cleanup_offset_feature.json"
        )
        stale.update(
            feature_dir.glob(
                "dark_tower_canopy_cleanup_offset_*_feature.json"
            )
        )
        stale.add(
            feature_dir
            / (
                "dark_tower_canopy_cleanup_"
                "neighborhood_sequence_feature.json"
            )
        )
        stale.add(
            BP
            / "netease_feature_rules"
            / "dark_tower_canopy_cleanup_feature_rule.json"
        )
    for path in sorted(stale):
        if path.exists():
            path.unlink()


def build_tree_profile(biome_key, profile_name, darkwood_name):
    write(
        BP / "netease_features" / (profile_name + ".json"),
        {
            "format_version": "1.20.30",
            "minecraft:weighted_random_feature": {
                "description": {"identifier": "tf_slice:" + profile_name},
                # Flatten the source's three mixed attempts plus thirteen
                # pure darkwood attempts into one direct selector: about
                # 4% birch / 3% oak / 93% darkwood.
                "features": [
                    [
                        "tf_slice:forest_vanilla_birch_tree_feature",
                        SAFE_DARK_FOREST_BIRCH_WEIGHT,
                    ],
                    [
                        "tf_slice:forest_vanilla_oak_tree_feature",
                        SAFE_DARK_FOREST_OAK_WEIGHT,
                    ],
                    [
                        "tf_slice:" + darkwood_name,
                        SAFE_DARK_FOREST_DARKWOOD_WEIGHT,
                    ],
                ],
            },
        },
    )

    remove_retired_dark_forest_tree_graph(biome_key)
    search_name = biome_key + "_tree_ground_search_feature"
    placement = downward_search_feature(
        search_name,
        profile_name,
        SAFE_DARK_FOREST_TREE_SEARCH_DEPTH,
    )
    write(BP / "netease_features" / (search_name + ".json"), placement)
    placed_feature = "tf_slice:" + search_name
    rule_iterations = dark_forest_tree_rule_iterations(biome_key)
    rule_y = dark_forest_tree_rule_y(biome_key)
    rule_name = biome_key + "_tree_profile_feature_rule"
    write(
        BP / "netease_feature_rules" / (rule_name + ".json"),
        {
            "format_version": "1.14.0",
            "minecraft:feature_rules": {
                "description": {
                    "identifier": "tf_slice:" + rule_name,
                    "places_feature": placed_feature,
                },
                "conditions": {
                    "placement_pass": "after_surface_pass",
                    "minecraft:biome_filter": [
                        {"all_of": dark_forest_filter(biome_key)}
                    ],
                },
                "distribution": {
                    "iterations": rule_iterations,
                    "coordinate_eval_order": "xzy",
                    "x": {
                        "distribution": "uniform",
                        "extent": [0, 15],
                    },
                    "y": rule_y,
                    "z": {
                        "distribution": "uniform",
                        "extent": [0, 15],
                    },
                },
            },
        },
    )


def remove_legacy_dark_forest_canopy():
    """Remove the old synthetic leaf slab; upstream canopy comes from trees."""
    for biome_key in ("dark_forest", "dark_forest_center"):
        for path in (BP / "netease_features").glob(
            biome_key + "_canopy_*_feature.json"
        ):
            path.unlink()
        rule = (
            BP
            / "netease_feature_rules"
            / (biome_key + "_canopy_feature_rule.json")
        )
        if rule.exists():
            rule.unlink()


def groundcover_single_feature(identifier, block):
    return {
        "format_version": "1.21.40",
        "minecraft:single_block_feature": {
            "description": {"identifier": "tf_slice:" + identifier},
            "places_block": [{"block": block, "weight": 1}],
            "enforce_placement_rules": False,
            "enforce_survivability_rules": False,
            "may_replace": ["minecraft:air"],
            "may_attach_to": {
                "auto_rotate": False,
                "min_sides_must_attach": 1,
                "bottom": ["minecraft:grass", "minecraft:grass_block"],
            },
        },
    }


def groundcover_patch_feature(identifier, placed_feature, tries):
    return {
        "format_version": "1.21.10",
        "minecraft:scatter_feature": {
            "description": {"identifier": "tf_slice:" + identifier},
            "places_feature": "tf_slice:" + placed_feature,
            "project_input_to_floor": True,
            "distribution": {
                "iterations": int(tries),
                "coordinate_eval_order": "xzy",
                "x": {"distribution": "triangle", "extent": [-7, 7]},
                "y": 0,
                "z": {"distribution": "triangle", "extent": [-7, 7]},
            },
        },
    }


def dark_groundcover_filter():
    return [
        {
            "test": "has_biome_tag",
            "operator": "==",
            "value": "dm33027004",
        },
        {
            "test": "has_biome_tag",
            "operator": "==",
            "value": "tf_slice_dark_forest_groundcover",
        },
    ]


def surface_patch_rule(identifier, placed_feature, biome_filter, iterations=1, chance=None):
    distribution = {
        "iterations": int(iterations),
        "coordinate_eval_order": "xzy",
        "x": {"distribution": "uniform", "extent": [0, 15]},
        "y": "query.get_height_at(variable.worldx, variable.worldz)",
        "z": {"distribution": "uniform", "extent": [0, 15]},
    }
    if chance is not None:
        distribution["scatter_chance"] = float(chance)
    return {
        "format_version": "1.14.0",
        "minecraft:feature_rules": {
            "description": {
                "identifier": "tf_slice:" + identifier,
                "places_feature": "tf_slice:" + placed_feature,
            },
            "conditions": {
                "placement_pass": "after_surface_pass",
                "minecraft:biome_filter": [{"all_of": list(biome_filter)}],
            },
            "distribution": distribution,
        },
    }


def build_dark_forest_groundcover():
    profiles = (
        ("grass", "minecraft:short_grass", 128, 25.0),
        ("ferns", "minecraft:fern", 128, 25.0),
        ("mushglooms", "tf_slice:mushgloom", 50, 100.0 / 30.0),
        ("dead_bushes", "minecraft:deadbush", 50, 100.0 / 15.0),
        ("pumpkins", "minecraft:pumpkin", 50, 100.0 / 30.0),
        ("mushrooms", "minecraft:brown_mushroom", 50, None),
    )
    for suffix, block, tries, chance in profiles:
        single_name = "dark_%s_feature" % suffix
        patch_name = "dark_%s_patch_feature" % suffix
        rule_name = "dark_%s_feature_rule" % suffix
        write(
            BP / "netease_features" / (single_name + ".json"),
            groundcover_single_feature(single_name, block),
        )
        write(
            BP / "netease_features" / (patch_name + ".json"),
            groundcover_patch_feature(patch_name, single_name, tries),
        )
        write(
            BP / "netease_feature_rules" / (rule_name + ".json"),
            surface_patch_rule(
                rule_name,
                patch_name,
                dark_groundcover_filter(),
                chance=chance,
            ),
        )

    flower_rule = "dark_forest_flowers_feature_rule"
    write(
        BP / "netease_feature_rules" / (flower_rule + ".json"),
        surface_patch_rule(
            flower_rule,
            "twilight_flower_patch_feature",
            dark_forest_filter("dark_forest"),
            iterations=3,
            chance=50.0,
        ),
    )


def build_trees():
    remove_legacy_dark_forest_canopy()
    profiles = (
        (
            "dark_forest",
            "dark_forest_tree_profile_feature",
            "darkwood_tree_feature",
            "tf_slice:hardened_dark_leaves",
        ),
        (
            "dark_forest_center",
            "dark_forest_center_tree_profile_feature",
            "darkwood_tree_center_feature",
            "tf_slice:hardened_dark_leaves_center",
        ),
    )
    tree_metadata = {
        "sourceVersion": "4.3.2508",
        "generationMode": "bounded_ground_search_dense_fancy_tree_feature",
        "attemptsPerChunk": SAFE_DARK_FOREST_TREE_ATTEMPTS,
        "groundSearchDepth": SAFE_DARK_FOREST_TREE_SEARCH_DEPTH,
        "runtimeCanopyHeight": SAFE_DARKWOOD_CANOPY_HEIGHT,
        "activeVariantCountPerProfile": 0,
        "retiredStructureTemplateBounds": [37, 34, 37],
        "variantCountPerProfile": 16,
        "logBlock": "tf_slice:dark_log_vertical",
        "branchCount": 4,
        "configuredBranchLengthRange": [8.0, 10.0],
        # BranchingTrunkPlacer 4.3.2508 decodes random_add_length but calls
        # BranchesConfig.length() directly, so the effective runtime is 8.
        "effectiveBranchLength": 8.0,
        "branchStartOffsetDown": 3,
        "branchPitch": 0.23,
        "branchYawSpacing": 0.23,
        "foliage": {
            "horizontalRadius": 4.5,
            "randomAddHorizontal": 1,
            "verticalRadius": 2.25,
            "verticalFillerBias": 0.45,
            "shagFactor": 36,
        },
        "roots": {
            "placementMode": "conditional_natural_block_cluster",
            "clusterOffsetY": -4,
            "rootCount": 12,
            "liverootCount": 2,
            "replaceableBlocks": [
                "minecraft:dirt",
                "minecraft:grass_block",
                "minecraft:gravel",
                "minecraft:podzol",
                "minecraft:stone",
                "minecraft:deepslate",
            ],
        },
        "profiles": {},
    }
    for biome_key, profile_name, darkwood_name, leaf_block in profiles:
        tree_metadata["profiles"][darkwood_name] = {
            "leafBlock": leaf_block,
            "variants": build_chunk_safe_darkwood_tree(
                darkwood_name, leaf_block
            ),
        }
        build_tree_profile(biome_key, profile_name, darkwood_name)
    write(
        BP / "metadata" / "dark_forest_tree_generation.json",
        tree_metadata,
    )
    build_dark_forest_groundcover()
    normalize_landmark_surface_decorations(ROOT)
    guard_native_structure_rules(ROOT)


def hostile_entity(identifier, health, movement, damage, box, profile):
    source_name = "hostile_wolf" if profile == "wolf" else "hedge_spider"
    source = load(BP / "entities" / (source_name + ".entity.json"))
    entity = copy.deepcopy(source)
    body = entity["minecraft:entity"]
    body["description"]["identifier"] = "tf_slice:" + identifier
    components = body["components"]
    components["minecraft:type_family"]["family"] = [
        identifier,
        profile,
        "monster",
        "mob",
    ]
    components["minecraft:health"] = {"value": health, "max": health}
    components["minecraft:movement"] = {"value": movement}
    components["minecraft:attack"] = {"damage": damage}
    components["minecraft:collision_box"] = {
        "width": box[0],
        "height": box[1],
    }
    components["minecraft:loot"] = {
        "table": "loot_tables/entities/tf_slice/%s.json" % identifier
    }
    if identifier == "king_spider":
        components.pop("minecraft:can_climb", None)
        components["minecraft:behavior.melee_attack"]["speed_multiplier"] = 1.0
        components["minecraft:behavior.random_stroll"]["speed_multiplier"] = 0.8
        components["minecraft:behavior.leap_at_target"]["yd"] = 0.4
        target = components["minecraft:behavior.nearest_attackable_target"]
        target["must_see"] = True
        target["entity_types"][0]["max_dist"] = 16
        components["minecraft:rideable"]["seats"]["position"] = [0, 1.2, 0]
    return entity


def client_entity(identifier, geometry, texture, egg, profile):
    animations = {"look": "animation.common.look_at_target"}
    if profile == "wolf":
        animations["move"] = "animation.tf_slice.wolf.walk"
    document = {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": "tf_slice:" + identifier,
                "materials": {"default": "entity_alphatest"},
                "textures": {"default": texture},
                "geometry": {"default": geometry},
                "render_controllers": ["controller.render.default"],
                "spawn_egg": {"base_color": egg[0], "overlay_color": egg[1]},
                "animations": animations,
                "scripts": {"animate": list(animations)},
            }
        },
    }
    if identifier == "king_spider":
        description = document["minecraft:client_entity"]["description"]
        description["animations"] = {
            "default_leg_pose": "animation.spider.default_leg_pose",
            "look_at_target": "animation.spider.look_at_target",
            "walk": "animation.spider.walk",
        }
        description["scripts"] = {
            "scale": "1.9",
            "animate": [
                "default_leg_pose",
                {"walk": "query.modified_move_speed"},
                "look_at_target",
            ],
        }
    return document


def spawn_rule(identifier, weight, minimum, maximum):
    return {
        "format_version": "1.8.0",
        "minecraft:spawn_rules": {
            "description": {
                "identifier": "tf_slice:" + identifier,
                "population_control": "monster",
            },
            "conditions": [
                {
                    "minecraft:spawns_on_surface": {},
                    "minecraft:spawns_on_block_filter": [
                        "minecraft:grass",
                        "minecraft:grass_block",
                        "minecraft:dirt",
                        "minecraft:podzol",
                    ],
                    "minecraft:brightness_filter": {
                        "min": 0,
                        "max": 7,
                        "adjust_for_weather": False,
                    },
                    "minecraft:weight": {"default": weight},
                    "minecraft:herd": {
                        "min_size": minimum,
                        "max_size": maximum,
                    },
                    "minecraft:density_limit": {"surface": 8, "underground": 0},
                    "minecraft:biome_filter": {
                        "all_of": [
                            {
                                "test": "has_biome_tag",
                                "operator": "==",
                                "value": "dm33027004",
                            },
                            {
                                "test": "has_biome_tag",
                                "operator": "==",
                                "value": "tf_slice_biome_dark_forest",
                            },
                        ]
                    },
                }
            ],
        },
    }


def build_mobs():
    mobs = {
        "mist_wolf": {
            "stats": (30, 0.3, 6, (0.8, 0.85), "wolf"),
            "geometry": "geometry.tf_slice.hostile_wolf",
            "texture": "textures/entity/tf_slice/mist_wolf",
            "source": "model/mistwolf.png",
            "egg": ("#6E7C77", "#D9E4DF"),
        },
        "king_spider": {
            "stats": (30, 0.35, 6, (1.6, 1.6), "spider"),
            "geometry": "geometry.spider.v1.8",
            "texture": "textures/entity/tf_slice/king_spider",
            "source": "model/kingspider.png",
            "egg": ("#2D241C", "#6D5038"),
        },
    }
    for identifier, spec in mobs.items():
        health, movement, damage, box, profile = spec["stats"]
        write(
            BP / "entities" / (identifier + ".entity.json"),
            hostile_entity(identifier, health, movement, damage, box, profile),
        )
        write(
            RP / "entity" / (identifier + ".entity.json"),
            client_entity(
                identifier,
                spec["geometry"],
                spec["texture"],
                spec["egg"],
                profile,
            ),
        )
        copy_texture(
            spec["source"],
            RP / "textures" / "entity" / "tf_slice" / (identifier + ".png"),
        )
        write(
            BP / "loot_tables" / "entities" / "tf_slice" / (identifier + ".json"),
            {"pools": []},
        )
    spawn_specs = {
        "mist_wolf": (5, 1, 1),
        "skeleton_druid": (5, 1, 1),
        "king_spider": (1, 1, 1),
        "kobold": (10, 1, 3),
    }
    for identifier, values in spawn_specs.items():
        write(
            BP / "spawn_rules" / (identifier + "_dark_forest.json"),
            spawn_rule(identifier, *values),
        )
    register_entity_names(mobs)


def register_entity_names(mobs):
    translations = {
        "mist_wolf": ("Mist Wolf", u"迷雾狼"),
        "king_spider": ("King Spider", u"国王蜘蛛"),
    }
    creative_path = BP / "item_catalog" / "crafting_item_catalog.json"
    creative = load(creative_path)
    items = creative["minecraft:crafting_items_catalog"]["categories"][0][
        "groups"
    ][0]["items"]
    for identifier in mobs:
        item = "tf_slice:%s_spawn_egg" % identifier
        if item not in items:
            items.append(item)
    write(creative_path, creative)
    for language, index in (("en_US.lang", 0), ("zh_CN.lang", 1)):
        path = RP / "texts" / language
        lines = path.read_text(encoding="utf-8").splitlines()
        known = dict(
            (line.split("=", 1)[0], position)
            for position, line in enumerate(lines)
            if "=" in line
        )
        for identifier in mobs:
            for key in (
                "entity.tf_slice:%s.name" % identifier,
                "item.spawn_egg.entity.tf_slice:%s.name" % identifier,
            ):
                value = key + "=" + translations[identifier][index]
                if key in known:
                    lines[known[key]] = value
                else:
                    known[key] = len(lines)
                    lines.append(value)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    build_blocks_and_items()
    build_trees()
    build_mobs()
    build_public_block_shapes()
    # Public content generators must finish through the canonical registries;
    # incremental language/catalog writes above are only intermediate state.
    build_localization(ROOT)
    normalize_creative_catalog(ROOT)
    print("generated %d darkwood blocks, 2 boats, trees, and 2 mobs" % len(DARK_BLOCKS))


if __name__ == "__main__":
    if sys.argv[1:] == ["--center-tree-cleanup-only"]:
        build_tree_profile(
            "dark_forest_center",
            "dark_forest_center_tree_profile_feature",
            "darkwood_tree_center_feature",
        )
        print("rebuilt Dark Forest center chunk-local cleanup rule")
    elif sys.argv[1:]:
        raise SystemExit(
            "usage: build_dark_forest_content.py "
            "[--center-tree-cleanup-only]"
        )
    else:
        main()
