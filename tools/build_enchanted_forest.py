#!/usr/bin/env python3
"""Build source-derived Enchanted Forest trees, colors and decorations."""

import json
import math
import random
import shutil
from pathlib import Path

from build_ruin_structures import SparseStructure, write_mcstructure


PHASE_COUNT = 16
REGULAR_SIZE = (15, 16, 15)
LARGE_SIZE = (25, 24, 25)
BASE_Y = 5
RAINBOW_LEAF_COLORS = (
    "#00FF00",
    "#B010EF",
    "#9FDF20",
    "#1030CF",
    "#C0BF40",
    "#8F50AF",
    "#209F60",
    "#D0708F",
    "#7F7F80",
    "#30906F",
    "#E05FA0",
    "#6FB04F",
    "#403FC0",
    "#F0D02F",
    "#5F1FE0",
    "#50F00F",
)


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _structure_path(bp, structure_name):
    namespace, relative = structure_name.split(":", 1)
    return bp / "structures" / namespace / ("%s.mcstructure" % relative)


def _line(start, end):
    delta = tuple(end[index] - start[index] for index in range(3))
    steps = max(abs(value) for value in delta)
    result = []
    for index in range(steps + 1):
        ratio = float(index) / float(steps or 1)
        point = tuple(
            int(round(start[axis] + delta[axis] * ratio))
            for axis in range(3)
        )
        if not result or result[-1] != point:
            result.append(point)
    return result


def _triangle_wave(value):
    if value & 256:
        value = 255 - (value & 255)
    return value & 255


def _source_rainbow_color(x, y, z):
    red = _triangle_wave(x * 32 + y * 16)
    green = _triangle_wave(y * 32 + z * 16) ^ 255
    blue = _triangle_wave(x * 16 + z * 32)
    return red, green, blue


def _rgb(hex_color):
    return tuple(
        int(hex_color[offset : offset + 2], 16)
        for offset in (1, 3, 5)
    )


PALETTE_RGB = tuple(_rgb(color) for color in RAINBOW_LEAF_COLORS)


def _leaf_block(x, y, z, phase):
    source = _source_rainbow_color(
        x + phase * 17,
        y + phase * 5,
        z + phase * 11,
    )
    nearest = min(
        range(PHASE_COUNT),
        key=lambda index: sum(
            (source[channel] - PALETTE_RGB[index][channel]) ** 2
            for channel in range(3)
        ),
    )
    return "tf_slice:rainbow_oak_leaves_%02d" % nearest


def _axis(previous, current):
    if current[0] != previous[0]:
        return "x"
    if current[2] != previous[2]:
        return "z"
    return "y"


def _log(axis):
    if axis == "x":
        return "tf_slice:twilight_oak_log_x"
    if axis == "z":
        return "tf_slice:twilight_oak_log_z"
    return "tf_slice:twilight_oak_log"


def _set_leaf_blob(structure, center, radius, phase):
    cx, cy, cz = center
    for x in range(cx - radius, cx + radius + 1):
        for y in range(cy - 1, cy + 2):
            for z in range(cz - radius, cz + radius + 1):
                dx = abs(x - cx)
                dy = abs(y - cy)
                dz = abs(z - cz)
                if dx + dz > radius * 2 - dy:
                    continue
                if (x, y, z) in structure.blocks:
                    continue
                structure.set(x, y, z, _leaf_block(x, y, z, phase))


def _set_fixed_leaf_blob(structure, center, radius, block):
    cx, cy, cz = center
    for x in range(cx - radius, cx + radius + 1):
        for y in range(cy - 1, cy + 2):
            for z in range(cz - radius, cz + radius + 1):
                dx = abs(x - cx)
                dy = abs(y - cy)
                dz = abs(z - cz)
                if dx + dz > radius * 2 - dy:
                    continue
                if (x, y, z) not in structure.blocks:
                    structure.set(x, y, z, block)


def _add_roots(structure, center_x, center_z, rng):
    """Keep terrain-dependent rainbow-oak roots out of static structures.

    Twilight Forest's TreeRootsDecorator calls traceRoot, which places each
    root segment only when canRootGrowIn accepts the existing terrain and
    stops at the first invalid position. A Bedrock mcstructure cannot perform
    that per-block terrain check. Baking the same diagonal strands into the
    structure therefore turns underground roots into floating logs on slopes.
    """
    del structure, center_x, center_z, rng
    return 0


def _regular_tree(seed, phase):
    rng = random.Random(seed)
    center_x = REGULAR_SIZE[0] // 2
    center_z = REGULAR_SIZE[2] // 2
    height = 4 + rng.randint(0, 2)
    structure = SparseStructure(REGULAR_SIZE, "enchanted_regular_%02d" % phase)
    root_count = _add_roots(structure, center_x, center_z, rng)
    top_y = BASE_Y + height
    _set_leaf_blob(structure, (center_x, top_y - 1, center_z), 2, phase)
    _set_leaf_blob(structure, (center_x, top_y + 1, center_z), 1, phase)
    for y in range(BASE_Y, top_y + 1):
        structure.set(center_x, y, center_z, _log("y"))
    return structure, {
        "id": "v%02d" % phase,
        "height": height,
        "root_count": root_count,
        "leaf_phase": phase,
    }


def _large_tree(seed, phase):
    rng = random.Random(seed)
    center_x = LARGE_SIZE[0] // 2
    center_z = LARGE_SIZE[2] // 2
    height = 3 + rng.randint(0, 11)
    structure = SparseStructure(LARGE_SIZE, "enchanted_large_%02d" % phase)
    root_count = _add_roots(structure, center_x, center_z, rng)
    top_y = BASE_Y + height
    branch_count = 2 + rng.randint(0, 2)
    branch_tips = []
    start_yaw = rng.random()
    for branch_index in range(branch_count):
        yaw = start_yaw + float(branch_index) / float(branch_count)
        start = (
            center_x,
            max(BASE_Y + 2, top_y - 4 + branch_index),
            center_z,
        )
        reach = 3 + rng.randint(0, 2)
        end = (
            center_x + int(round(math.sin(yaw * math.tau) * reach)),
            min(LARGE_SIZE[1] - 3, start[1] + 1 + rng.randint(0, 2)),
            center_z + int(round(math.cos(yaw * math.tau) * reach)),
        )
        points = _line(start, end)
        for point_index, point in enumerate(points):
            previous = points[max(0, point_index - 1)]
            structure.set(
                point[0],
                point[1],
                point[2],
                _log(_axis(previous, point) if point_index else "y"),
            )
        branch_tips.append(end)
    for tip in branch_tips:
        _set_leaf_blob(structure, tip, 2, phase)
    _set_leaf_blob(
        structure,
        (center_x, min(LARGE_SIZE[1] - 3, top_y), center_z),
        3,
        phase,
    )
    _set_leaf_blob(
        structure,
        (center_x, min(LARGE_SIZE[1] - 2, top_y + 2), center_z),
        2,
        phase,
    )
    for y in range(BASE_Y, min(LARGE_SIZE[1] - 1, top_y + 1)):
        structure.set(center_x, y, center_z, _log("y"))
    return structure, {
        "id": "v%02d" % phase,
        "height": height,
        "root_count": root_count,
        "branch_count": branch_count,
        "leaf_phase": phase,
    }


def _native_feature(identifier, structure_name):
    return {
        "format_version": "1.14.0",
        "netease:structure_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_structure": structure_name,
            "rotation": 0,
        },
    }


def _selector(identifier, features):
    return {
        "format_version": "1.20.30",
        "minecraft:weighted_random_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "features": [["tf_slice:%s" % feature, 1] for feature in features],
        },
    }


def _biome_filter():
    return [
        {
            "all_of": [
                {
                    "test": "has_biome_tag",
                    "operator": "==",
                    "value": "dm33027004",
                },
                {
                    "test": "has_biome_tag",
                    "operator": "==",
                    "value": "tf_slice_biome_enchanted_forest",
                },
            ]
        }
    ]


def _surface_rule(
    identifier,
    feature,
    iterations=1,
    chance=None,
    y=None,
    pass_name="surface_pass",
):
    distribution = {
        "iterations": iterations,
        "coordinate_eval_order": "xzy",
        "x": {"distribution": "uniform", "extent": [0, 15]},
        "y": y or "query.get_height_at(variable.worldx, variable.worldz)",
        "z": {"distribution": "uniform", "extent": [0, 15]},
    }
    if chance is not None:
        distribution["scatter_chance"] = chance
    return {
        "format_version": "1.14.0",
        "minecraft:feature_rules": {
            "description": {
                "identifier": "tf_slice:%s" % identifier,
                "places_feature": "tf_slice:%s" % feature,
            },
            "conditions": {
                "placement_pass": pass_name,
                "minecraft:biome_filter": _biome_filter(),
            },
            "distribution": distribution,
        },
    }


def _leaf_block_document(identifier):
    return {
        "format_version": "1.10.0",
        "minecraft:block": {
            "description": {
                "identifier": "tf_slice:%s" % identifier,
                "register_to_creative_menu": False,
            },
            "components": {
                "minecraft:destroy_time": {"value": 0.2},
                "minecraft:explosion_resistance": {"value": 0.2},
                "minecraft:block_light_absorption": {"value": 0},
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
                "netease:render_layer": {"value": "optionalAlpha"},
                "netease:no_crop_face_block": {},
                "netease:solid": {"value": False},
                "netease:pathable": {"value": False},
            },
        },
    }


def _copy_tree_with_leaf(source, identifier, old_leaf, new_leaf):
    document = json.loads(source.read_text(encoding="utf-8"))
    tree = document["minecraft:tree_feature"]
    tree["description"]["identifier"] = "tf_slice:%s" % identifier
    return json.loads(json.dumps(document).replace(old_leaf, new_leaf))


def _vanilla_structure(identifier, log, leaves, height):
    structure = SparseStructure(REGULAR_SIZE, identifier)
    center_x = REGULAR_SIZE[0] // 2
    center_z = REGULAR_SIZE[2] // 2
    top_y = BASE_Y + height
    _set_fixed_leaf_blob(
        structure,
        (center_x, top_y - 1, center_z),
        2,
        leaves,
    )
    _set_fixed_leaf_blob(
        structure,
        (center_x, top_y + 1, center_z),
        1,
        leaves,
    )
    for y in range(BASE_Y, top_y + 1):
        structure.set(center_x, y, center_z, log)
    return structure


def _structure_bounds(structure):
    positions = list(structure.blocks)
    if not positions:
        return [0, 0, 0, 0, 0, 0]
    return [
        min(point[0] for point in positions),
        min(point[1] for point in positions),
        min(point[2] for point in positions),
        max(point[0] for point in positions),
        max(point[1] for point in positions),
        max(point[2] for point in positions),
    ]


def _write_runtime_pieces(bp, kind, name, structure):
    pieces = []
    for start_x in range(0, structure.size[0], 16):
        for start_z in range(0, structure.size[2], 16):
            size_x = min(16, structure.size[0] - start_x)
            size_z = min(16, structure.size[2] - start_z)
            piece_name = "x%02d_z%02d" % (start_x, start_z)
            piece = structure.crop(
                start_x,
                start_z,
                size_x,
                size_z,
                "%s_%s_%s" % (kind, name, piece_name),
            )
            if not piece.blocks and not piece.entities:
                continue
            reference = "tf_slice:enchanted/runtime/%s/%s/%s" % (
                kind,
                name,
                piece_name,
            )
            write_mcstructure(_structure_path(bp, reference), piece)
            pieces.append(
                {
                    "structure": reference,
                    "offset": [start_x, 0, start_z],
                    "size": list(piece.size),
                }
            )
    return pieces


def _variant_catalog(bp, kind, name, structure, center):
    return {
        "kind": kind,
        "name": name,
        "center": list(center),
        "bounds": _structure_bounds(structure),
        "occupied": [
            list(position) for position in sorted(structure.blocks)
        ],
        "pieces": _write_runtime_pieces(bp, kind, name, structure),
    }


def _write_catalog_module(bp, catalog):
    path = bp / "TwilightBossSlice" / "enchanted_tree_catalog_data.py"
    payload = json.dumps(catalog, ensure_ascii=True, separators=(",", ":"))
    path.write_text(
        "# -*- coding: utf-8 -*-\n"
        "# Generated by tools/build_enchanted_forest.py; do not edit by hand.\n"
        "CATALOG_JSON = %r\n" % payload,
        encoding="utf-8",
    )


def build_enchanted_forest(root):
    root = Path(root)
    bp = root / "TwilightBossSliceB"
    rp = root / "TwilightBossSliceR"
    feature_dir = bp / "netease_features"
    rule_dir = bp / "netease_feature_rules"
    block_dir = bp / "netease_blocks"
    runtime_root = bp / "structures" / "tf_slice" / "enchanted" / "runtime"
    if runtime_root.is_dir():
        shutil.rmtree(str(runtime_root))

    atlas_path = rp / "textures" / "terrain_texture.json"
    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    texture_data = atlas["texture_data"]
    blocks_path = rp / "blocks.json"
    client_blocks = json.loads(blocks_path.read_text(encoding="utf-8"))

    texture_data["tf_slice:rainbow_oak_leaves"]["textures"][0][
        "tint_color"
    ] = "#00FF80"
    leaf_specs = list(
        ("rainbow_oak_leaves_%02d" % index, color)
        for index, color in enumerate(RAINBOW_LEAF_COLORS)
    )
    leaf_specs.extend(
        (
            ("enchanted_twilight_oak_leaves", "#00FFFF"),
            ("enchanted_canopy_leaves", "#23CCB2"),
        )
    )
    for identifier, color in leaf_specs:
        write_json(block_dir / ("%s.json" % identifier), _leaf_block_document(identifier))
        client_blocks["tf_slice:%s" % identifier] = {
            "textures": "tf_slice:%s" % identifier,
            "sound": "grass",
        }
        texture_data["tf_slice:%s" % identifier] = {
            "textures": [
                {
                    "path": (
                        "textures/blocks/rainbow_oak_leaves"
                        if identifier.startswith("rainbow_oak_leaves_")
                        else "textures/blocks/leaves_oak"
                    ),
                    "tint_color": color,
                }
            ]
        }
    write_json(atlas_path, atlas)
    write_json(blocks_path, client_blocks)

    metadata = {"regular": [], "large": []}
    catalog = {
        "format_version": 1,
        "variants": {
            "regular_rainbow": [],
            "vanilla_oak": [],
            "vanilla_birch": [],
            "large_rainbow": [],
        },
    }
    for kind, builder in (("regular", _regular_tree), ("large", _large_tree)):
        for phase in range(PHASE_COUNT):
            structure, variant = builder(
                0xEFC001 + phase * 1049 + (0 if kind == "regular" else 50000),
                phase,
            )
            structure_name = "tf_slice:enchanted/%s/v%02d" % (kind, phase)
            write_mcstructure(_structure_path(bp, structure_name), structure)
            catalog_kind = (
                "regular_rainbow" if kind == "regular" else "large_rainbow"
            )
            center = (
                REGULAR_SIZE[0] // 2,
                BASE_Y,
                REGULAR_SIZE[2] // 2,
            ) if kind == "regular" else (
                LARGE_SIZE[0] // 2,
                BASE_Y,
                LARGE_SIZE[2] // 2,
            )
            catalog["variants"][catalog_kind].append(
                _variant_catalog(
                    bp,
                    catalog_kind,
                    "v%02d" % phase,
                    structure,
                    center,
                )
            )
            metadata[kind].append(variant)

    for tree_kind, tree_name, log, leaves, height in (
        (
            "vanilla_oak",
            "enchanted_vanilla_oak_tree",
            "minecraft:oak_log",
            "minecraft:oak_leaves",
            5,
        ),
        (
            "vanilla_birch",
            "enchanted_vanilla_birch_tree",
            "minecraft:birch_log",
            "minecraft:birch_leaves",
            6,
        ),
    ):
        structure_name = "tf_slice:enchanted/vanilla/%s" % tree_name
        structure = _vanilla_structure(tree_name, log, leaves, height)
        write_mcstructure(
            _structure_path(bp, structure_name),
            structure,
        )
        catalog["variants"][tree_kind].append(
            _variant_catalog(
                bp,
                tree_kind,
                "v00",
                structure,
                (REGULAR_SIZE[0] // 2, BASE_Y, REGULAR_SIZE[2] // 2),
            )
        )

    for tree_kind in (
        "regular_rainbow",
        "vanilla_oak",
        "vanilla_birch",
        "large_rainbow",
    ):
        trigger = SparseStructure((1, 1, 1), "%s_tree_trigger" % tree_kind)
        trigger.set(0, 0, 0, "minecraft:stone")
        trigger_name = "tf_slice:enchanted/tree_trigger/%s" % tree_kind
        write_mcstructure(_structure_path(bp, trigger_name), trigger)
        feature_id = "enchanted_%s_tree_trigger_feature" % tree_kind
        write_json(
            feature_dir / ("%s.json" % feature_id),
            _native_feature(feature_id, trigger_name),
        )

    for stale_pattern in (
        "regular_rainbow_oak_tree_v*_feature.json",
        "large_rainbow_oak_tree_v*_feature.json",
    ):
        for stale_path in feature_dir.glob(stale_pattern):
            stale_path.unlink()
    for stale_name in (
        "rainbow_oak_tree_selector_feature.json",
        "large_rainbow_oak_tree_selector_feature.json",
        "enchanted_vanilla_oak_tree_feature.json",
        "enchanted_vanilla_birch_tree_feature.json",
    ):
        stale_path = feature_dir / stale_name
        if stale_path.exists():
            stale_path.unlink()
    _write_catalog_module(bp, catalog)
    write_json(
        feature_dir / "enchanted_twilight_oak_tree_feature.json",
        _copy_tree_with_leaf(
            feature_dir / "twilight_oak_tree_feature.json",
            "enchanted_twilight_oak_tree_feature",
            "tf_slice:twilight_oak_leaves",
            "tf_slice:enchanted_twilight_oak_leaves",
        ),
    )
    write_json(
        feature_dir / "enchanted_canopy_tree_feature.json",
        _copy_tree_with_leaf(
            feature_dir / "canopy_tree_feature.json",
            "enchanted_canopy_tree_feature",
            "tf_slice:canopy_leaves",
            "tf_slice:enchanted_canopy_leaves",
        ),
    )
    write_json(
        feature_dir / "enchanted_canopy_tree_selector_feature.json",
        {
            "format_version": "1.20.30",
            "minecraft:weighted_random_feature": {
                "description": {
                    "identifier": (
                        "tf_slice:enchanted_canopy_tree_selector_feature"
                    )
                },
                "features": [
                    ["tf_slice:enchanted_canopy_tree_feature", 3],
                    ["tf_slice:enchanted_twilight_oak_tree_feature", 2],
                ],
            },
        },
    )
    write_json(
        rule_dir / "enchanted_canopy_tree_feature_rule.json",
        _surface_rule(
            "enchanted_canopy_tree_feature_rule",
            "enchanted_canopy_tree_selector_feature",
        ),
    )

    write_json(
        feature_dir / "enchanted_vines_feature.json",
        {
            "format_version": "1.21.40",
            "minecraft:single_block_feature": {
                "description": {
                    "identifier": "tf_slice:enchanted_vines_feature"
                },
                "places_block": [
                    {
                        "block": "minecraft:vine",
                        "weight": 1,
                    }
                ],
                "enforce_placement_rules": False,
                "enforce_survivability_rules": False,
                "may_replace": ["minecraft:air"],
                "may_attach_to": {
                    "auto_rotate": True,
                    "min_sides_must_attach": 1,
                    "north": [
                        "tf_slice:twilight_oak_log",
                        "tf_slice:canopy_log",
                        "minecraft:oak_log",
                        "minecraft:birch_log",
                    ],
                    "south": [
                        "tf_slice:twilight_oak_log",
                        "tf_slice:canopy_log",
                        "minecraft:oak_log",
                        "minecraft:birch_log",
                    ],
                    "east": [
                        "tf_slice:twilight_oak_log",
                        "tf_slice:canopy_log",
                        "minecraft:oak_log",
                        "minecraft:birch_log",
                    ],
                    "west": [
                        "tf_slice:twilight_oak_log",
                        "tf_slice:canopy_log",
                        "minecraft:oak_log",
                        "minecraft:birch_log",
                    ],
                },
            },
        },
    )
    vine_rule = _surface_rule(
        "enchanted_vines_feature_rule",
        "enchanted_vines_feature",
        iterations=32,
        y=(
            "query.get_height_at(variable.worldx, variable.worldz)"
            " - math.random_integer(1, 14)"
        ),
    )
    write_json(rule_dir / "enchanted_vines_feature_rule.json", vine_rule)
    write_json(
        rule_dir / "enchanted_fallen_log_feature_rule.json",
        _surface_rule(
            "enchanted_fallen_log_feature_rule",
            "spooky_twilight_oak_fallen_log_selector_feature",
            chance=5.0,
            pass_name="after_surface_pass",
        ),
    )
    write_json(
        bp / "metadata" / "enchanted_forest_generation.json",
        {
            "source_version": "4.3.2508",
            "rainbow_leaf_colors": list(RAINBOW_LEAF_COLORS),
            "grass_color_approximation": "#00FF80",
            "root_placement": {
                "upstream": "terrain_aware_underground_only",
                "implementation": "omit_static_roots",
                "reason": (
                    "mcstructure cannot reproduce traceRoot/canRootGrowIn "
                    "without exposing roots on slopes"
                ),
            },
            "tree_variants": metadata,
            "tree_selector_weights": {
                "regular_rainbow": 650,
                "oak": 150,
                "birch": 128,
                "large_rainbow": 72,
            },
            "placement": "noop_1x1_trigger_deferred_root_anchor",
            "fiddlehead_attempts_per_chunk": 96,
        },
    )


if __name__ == "__main__":
    build_enchanted_forest(Path(__file__).resolve().parents[1])
