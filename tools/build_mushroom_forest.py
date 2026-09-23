#!/usr/bin/env python3
"""Build source-faithful Mushroom Forest and Dense Mushroom Forest features."""

import json
import io
import math
import random
import shutil
import struct
from pathlib import Path

try:
    from build_ruin_structures import (
        SparseStructure,
        TAG_COMPOUND,
        _read_payload,
        write_mcstructure,
    )
except ImportError:  # Imported as ``tools.build_mushroom_forest`` in tests.
    from tools.build_ruin_structures import (
        SparseStructure,
        TAG_COMPOUND,
        _read_payload,
        write_mcstructure,
    )


SOURCE_VERSION = "4.3.2508"
BROWN_VARIANTS = 16
RED_VARIANTS = 24
STRUCTURE_SIZE = (41, 40, 41)
CENTER = (20, 5, 20)
STEM_STATE = {"huge_mushroom_bits": 10}
FIREFLY_DIRECTIONS = (
    ("north", (0, 0, -1)),
    ("south", (0, 0, 1)),
    ("west", (-1, 0, 0)),
    ("east", (1, 0, 0)),
)


def firefly_quota(roll):
    """Decode CanopyMushroomFeature's max(0, nextInt(10) - 4) / 2."""
    if not 0 <= roll < 10:
        raise ValueError("firefly roll must be in [0, 9]")
    return max(0, roll - 4) // 2


def red_cap_style(roll):
    """Decode RedCanopyMushroomFeature.altHeads (the upstream 1..100 roll)."""
    if not 1 <= roll <= 100:
        raise ValueError("red cap roll must be in [1, 100]")
    if roll <= 33:
        return "vanilla"
    if roll <= 66:
        return "smooth"
    return "spheroid"


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_structure_summary(path):
    """Read the small amount of little-endian NBT used by contract tests."""
    stream = io.BytesIO(Path(path).read_bytes())
    root_type = struct.unpack("B", stream.read(1))[0]
    if root_type != TAG_COMPOUND:
        raise ValueError("%s does not contain a compound root" % path)
    name_length = struct.unpack("<H", stream.read(2))[0]
    stream.read(name_length)
    document = _read_payload(stream, TAG_COMPOUND, "<")
    return {
        "size": document["size"],
        "block_count": sum(
            1
            for value in document["structure"]["block_indices"][0]
            if int(value) >= 0
        ),
    }


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


def _cap_state(offset, offsets):
    """Map exposed horizontal faces to Bedrock's legacy mushroom state."""
    dx, dy, dz = offset
    west = (dx - 1, dy, dz) not in offsets
    east = (dx + 1, dy, dz) not in offsets
    north = (dx, dy, dz - 1) not in offsets
    south = (dx, dy, dz + 1) not in offsets
    if west != east:
        horizontal = -1 if west else 1
    elif west and east:
        horizontal = -1 if dx < 0 else (1 if dx > 0 else 0)
    else:
        horizontal = 0
    if north != south:
        vertical = -1 if north else 1
    elif north and south:
        vertical = -1 if dz < 0 else (1 if dz > 0 else 0)
    else:
        vertical = 0
    return {
        (-1, -1): 1,
        (0, -1): 2,
        (1, -1): 3,
        (-1, 0): 4,
        (0, 0): 5,
        (1, 0): 6,
        (-1, 1): 7,
        (0, 1): 8,
        (1, 1): 9,
    }[(horizontal, vertical)]


def _inside_smooth_shape(height, radius, x, y, z):
    vertical_offset = y - (height - 2)
    if vertical_offset == 4 or abs(x) > radius or abs(z) > radius:
        return False
    if vertical_offset >= 2:
        return True
    x_edge = abs(x) == radius
    z_edge = abs(z) == radius
    if vertical_offset == 1 and (
        (x_edge and abs(z) == radius - 1)
        or (z_edge and abs(x) == radius - 1)
    ):
        return False
    return (
        x_edge != z_edge
        or (abs(x) == abs(z) == radius - 1)
    )


def cap_offsets(style):
    """Return exact branch-head offsets used by 4.3.2508 at radius two."""
    offsets = set()
    if style == "flat":
        radius = 2
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if abs(dx) == radius and abs(dz) == radius:
                    continue
                offsets.add((dx, 0, dz))
        return offsets
    if style == "vanilla":
        height = 1
        radius = 2
        for dy in range(height - 3, height + 1):
            layer_radius = radius if dy < height else radius - 1
            for dx in range(-layer_radius, layer_radius + 1):
                for dz in range(-layer_radius, layer_radius + 1):
                    if dy < height:
                        x_edge = abs(dx) == layer_radius
                        z_edge = abs(dz) == layer_radius
                        if x_edge == z_edge:
                            continue
                    offsets.add((dx, dy, dz))
        return offsets
    if style == "smooth":
        height = 1
        radius = 2
        for dy in range(height - 2, height + 2):
            layer_radius = (
                radius - max(0, dy - (height - 1)) + 1
            )
            for dx in range(-layer_radius, layer_radius + 1):
                for dz in range(-layer_radius, layer_radius + 1):
                    if _inside_smooth_shape(
                        height, layer_radius, dx, dy, dz
                    ):
                        offsets.add((dx, dy, dz))
        return offsets
    if style == "spheroid":
        height = 1
        radius = 2
        for dy in range(height - 2, height + 1):
            layer_radius = radius + (2 if dy == height - 1 else 1)
            for dx in range(-layer_radius, layer_radius + 1):
                for dz in range(-layer_radius, layer_radius + 1):
                    if math.sqrt(dx * dx + dz * dz) <= layer_radius + 0.1:
                        offsets.add((dx, dy, dz))
        return offsets
    raise ValueError("unknown mushroom cap style %r" % style)


def _place_cap(structure, center, block, style):
    offsets = cap_offsets(style)
    for offset in offsets:
        structure.set(
            center[0] + offset[0],
            center[1] + offset[1],
            center[2] + offset[2],
            block,
            {"huge_mushroom_bits": _cap_state(offset, offsets)},
        )


def branch_points(start, end):
    """Match the upstream horizontal branch plus terminal vertical stalk."""
    horizontal_end = (end[0], start[1], end[2])
    points = _line(start, horizontal_end)
    lower_y = min(start[1], end[1])
    upper_y = max(start[1], end[1])
    for y in range(lower_y, upper_y + 1):
        point = (end[0], y, end[2])
        if point not in points:
            points.append(point)
    return points


def _wall_attachment(structure, point, rng):
    directions = list(FIREFLY_DIRECTIONS)
    rng.shuffle(directions)
    for facing, offset in directions:
        target = (
            point[0] + offset[0],
            point[1] + offset[1],
            point[2] + offset[2],
        )
        if target not in structure.blocks:
            return target, facing
    return None


def build_canopy_mushroom(kind, seed, name):
    """Build one upstream-style branching canopy mushroom and its metadata."""
    if kind not in ("brown", "red"):
        raise ValueError("unknown canopy mushroom kind %r" % kind)
    rng = random.Random(seed)
    structure = SparseStructure(STRUCTURE_SIZE, name)
    center_x, base_y, center_z = CENTER
    is_red = kind == "red"
    if is_red:
        cap_style = red_cap_style(rng.randrange(100) + 1)
    else:
        cap_style = "flat"
    firefly_budget = firefly_quota(rng.randrange(10))
    height = 9 + rng.randint(0, 4) + (3 if is_red else 0)
    branch_count = 3 if is_red else max(rng.randint(0, 4), 3)
    start_yaw = rng.random()
    cap_block = (
        "minecraft:red_mushroom_block"
        if is_red
        else "minecraft:brown_mushroom_block"
    )

    for y in range(base_y, base_y + height + 1):
        structure.set(
            center_x, y, center_z, "minecraft:mushroom_stem", STEM_STATE
        )

    firefly_candidates = [
        (center_x, y, center_z)
        for y in range(base_y + height // 2 + 1, base_y + height)
    ]
    branch_tips = []
    branch_lengths = []
    maximum_reach = 0
    pitch = 0.2
    for branch_index in range(branch_count):
        branch_length = (
            10 + rng.randint(0, 1)
            if is_red
            else 9 - rng.randint(0, 1)
        )
        branch_lengths.append(branch_length)
        yaw = start_yaw + 0.3 * branch_index
        start = (
            center_x,
            base_y + height - 6 + branch_index,
            center_z,
        )
        horizontal = math.sin(pitch * math.pi) * branch_length
        end = (
            start[0]
            + int(round(math.sin(yaw * math.tau) * horizontal)),
            start[1] + int(round(math.cos(pitch * math.pi) * branch_length)),
            start[2]
            + int(round(math.cos(yaw * math.tau) * horizontal)),
        )
        points = branch_points(start, end)
        for point in points:
            structure.set(
                point[0],
                point[1],
                point[2],
                "minecraft:mushroom_stem",
                STEM_STATE,
            )
        vertical_points = [
            point
            for point in points
            if point[0] == end[0]
            and point[2] == end[2]
            and point[1] > min(start[1], end[1])
        ]
        firefly_candidates.extend(vertical_points)
        branch_tips.append(end)
        maximum_reach = max(
            maximum_reach,
            abs(end[0] - center_x),
            abs(end[2] - center_z),
        )

    for tip in branch_tips:
        _place_cap(structure, tip, cap_block, cap_style)

    # The upstream budget is 0/1/2 with a 60/20/20 distribution. Each placed
    # firefly stores the direction from its supporting stem to the bug block.
    candidates = [
        point
        for point in firefly_candidates
        if structure.blocks.get(point, (None,))[0]
        == "minecraft:mushroom_stem"
    ]
    rng.shuffle(candidates)
    placed_fireflies = 0
    for point in candidates:
        if placed_fireflies >= firefly_budget:
            break
        attachment = _wall_attachment(structure, point, rng)
        if attachment is not None:
            target, facing = attachment
            structure.set(
                target[0],
                target[1],
                target[2],
                "tf_slice:firefly",
                {"tf_slice:facing": facing},
            )
            placed_fireflies += 1

    return structure, {
        "id": name,
        "kind": kind,
        "height": height,
        "branch_count": branch_count,
        "branch_length": branch_lengths[0],
        "branch_lengths": branch_lengths,
        "branch_pitch": pitch,
        "horizontal_reach": maximum_reach,
        "cap_style": cap_style,
        "cap_radius": {
            "flat": 2,
            "vanilla": 2,
            "smooth": 3,
            "spheroid": 4,
        }[cap_style],
        "branch_geometry": "horizontal_then_vertical",
        "firefly_count": placed_fireflies,
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
            reference = "tf_slice:mushroom/runtime/%s/%s/%s" % (
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
                    "bounds": _structure_bounds(piece),
                }
            )
    return pieces


def _variant_catalog(kind, name, structure):
    return {
        "kind": kind,
        "name": name,
        "bounds": _structure_bounds(structure),
        "occupied": [
            list(position) for position in sorted(structure.blocks)
        ],
    }


def _write_catalog_module(bp, catalog):
    path = bp / "TwilightBossSlice" / "mushroom_catalog_data.py"
    payload = json.dumps(catalog, ensure_ascii=True, separators=(",", ":"))
    path.write_text(
        "# -*- coding: utf-8 -*-\n"
        "# Generated by tools/build_mushroom_forest.py; do not edit by hand.\n"
        "CATALOG_JSON = %r\n" % payload,
        encoding="utf-8",
    )


def _selector(identifier, weighted_features):
    return {
        "format_version": "1.20.30",
        "minecraft:weighted_random_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "features": [
                ["tf_slice:%s" % feature, weight]
                for feature, weight in weighted_features
            ],
        },
    }


def _biome_filter(keys):
    tags = [
        {
            "test": "has_biome_tag",
            "operator": "==",
            "value": "tf_slice_biome_%s" % key,
        }
        for key in keys
    ]
    selected = tags[0] if len(tags) == 1 else {"any_of": tags}
    return [
        {
            "all_of": [
                {
                    "test": "has_biome_tag",
                    "operator": "==",
                    "value": "dm33027004",
                },
                selected,
            ]
        }
    ]


def _surface_rule(
    identifier,
    feature,
    keys,
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
                "minecraft:biome_filter": _biome_filter(keys),
            },
            "distribution": distribution,
        },
    }


def _copy_tree(source, identifier):
    document = json.loads(source.read_text(encoding="utf-8"))
    tree = document["minecraft:tree_feature"]
    tree["description"]["identifier"] = "tf_slice:%s" % identifier
    grow_on = tree.setdefault("may_grow_on", [])
    if "minecraft:grass_block" not in grow_on:
        grow_on.append("minecraft:grass_block")
    if "minecraft:mycelium" not in grow_on:
        grow_on.append("minecraft:mycelium")
    return document


def _vanilla_tree_feature(identifier, log, leaves, height):
    return {
        "format_version": "1.14.0",
        "minecraft:tree_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "trunk": {
                "trunk_height": {
                    "range_min": height[0],
                    "range_max": height[1],
                },
                "trunk_block": {"name": log},
            },
            "canopy": {
                "canopy_offset": {"min": -2, "max": 0},
                "variation_chance": [
                    {"numerator": 1, "denominator": 2},
                    {"numerator": 1, "denominator": 2},
                    {"numerator": 1, "denominator": 1},
                ],
                "leaf_block": {"name": leaves},
            },
            "base_block": ["minecraft:dirt"],
            "may_grow_on": [
                "minecraft:grass",
                "minecraft:grass_block",
                "minecraft:dirt",
                "minecraft:podzol",
                "minecraft:mycelium",
            ],
            "may_replace": [
                "minecraft:air",
                "minecraft:tallgrass",
                "minecraft:double_plant",
                "tf_slice:twilight_oak_leaves",
                "tf_slice:canopy_leaves",
            ],
            "may_grow_through": [
                "minecraft:air",
                "minecraft:tallgrass",
                "minecraft:double_plant",
            ],
        },
    }


def _patch_mycelium_ground(feature_dir):
    for filename in (
        "forest_mushroom_feature.json",
        "forest_groundcover_feature.json",
        "mayapple_feature.json",
    ):
        path = feature_dir / filename
        document = json.loads(path.read_text(encoding="utf-8"))
        bottom = document["minecraft:single_block_feature"][
            "may_attach_to"
        ]["bottom"]
        if "minecraft:mycelium" not in bottom:
            bottom.append("minecraft:mycelium")
        write_json(path, document)


def _patch_biome_surfaces(root):
    dense_path = (
        root
        / "TwilightBossSliceB"
        / "netease_biomes"
        / "dm33027004"
        / "dm33027004_mushroom_island.json"
    )
    dense = json.loads(dense_path.read_text(encoding="utf-8"))
    dense["minecraft:biome"]["components"]["minecraft:surface_parameters"][
        "top_material"
    ] = "minecraft:grass"
    write_json(dense_path, dense)

    rp_biomes = root / "TwilightBossSliceR" / "biomes"
    regular = json.loads(
        (
            rp_biomes
            / "dm33027004_mushroom_island_shore.client_biome.json"
        ).read_text(encoding="utf-8")
    )["minecraft:client_biome"]["components"]
    dense_client_path = (
        rp_biomes / "dm33027004_mushroom_island.client_biome.json"
    )
    dense_client = json.loads(dense_client_path.read_text(encoding="utf-8"))
    components = dense_client["minecraft:client_biome"]["components"]
    components["minecraft:sky_color"] = regular["minecraft:sky_color"]
    components["minecraft:water_appearance"] = regular[
        "minecraft:water_appearance"
    ]
    write_json(dense_client_path, dense_client)


def _build_mycelium_blob(feature_dir, rule_dir):
    write_json(
        feature_dir / "mushroom_mycelium_surface_feature.json",
        {
            "format_version": "1.21.40",
            "minecraft:single_block_feature": {
                "description": {
                    "identifier": "tf_slice:mushroom_mycelium_surface_feature"
                },
                "places_block": "minecraft:mycelium",
                "enforce_placement_rules": False,
                "enforce_survivability_rules": False,
                "may_replace": [
                    "minecraft:grass",
                    "minecraft:grass_block",
                    "minecraft:dirt",
                    "minecraft:podzol",
                ],
            },
        },
    )
    variants = []
    for radius, iterations in ((4, 64), (5, 96), (6, 128)):
        identifier = "mushroom_mycelium_blob_r%d_feature" % radius
        write_json(
            feature_dir / ("%s.json" % identifier),
            {
                "format_version": "1.21.10",
                "minecraft:scatter_feature": {
                    "description": {
                        "identifier": "tf_slice:%s" % identifier
                    },
                    "places_feature": (
                        "tf_slice:mushroom_mycelium_surface_feature"
                    ),
                    "project_input_to_floor": True,
                    "distribution": {
                        "iterations": iterations,
                        "coordinate_eval_order": "xzy",
                        "x": {
                            "distribution": "triangle",
                            "extent": [-radius, radius],
                        },
                        "y": -1,
                        "z": {
                            "distribution": "triangle",
                            "extent": [-radius, radius],
                        },
                    },
                },
            },
        )
        variants.append((identifier, 1))
    write_json(
        feature_dir / "mushroom_mycelium_blob_selector_feature.json",
        _selector("mushroom_mycelium_blob_selector_feature", variants),
    )
    write_json(
        rule_dir / "mushroom_mycelium_blob_feature_rule.json",
        _surface_rule(
            "mushroom_mycelium_blob_feature_rule",
            "mushroom_mycelium_blob_selector_feature",
            ["mushroom_forest", "dense_mushroom_forest"],
            chance=100.0 / 3.0,
            pass_name="after_surface_pass",
        ),
    )


def _remove_independent_vanilla_huge_mushrooms(bp, feature_dir, rule_dir):
    """Remove the old unfiltered giant red/brown mushroom approximation."""
    stale_files = [
        rule_dir / "mushroom_vanilla_huge_feature_rule.json",
        feature_dir / "vanilla_mushroom_selector_feature.json",
        feature_dir / "vanilla_brown_mushroom_selector_feature.json",
        feature_dir / "vanilla_red_mushroom_selector_feature.json",
    ]
    stale_files.extend(
        feature_dir.glob("vanilla_brown_mushroom_v*_feature.json")
    )
    stale_files.extend(
        feature_dir.glob("vanilla_red_mushroom_v*_feature.json")
    )
    for stale_path in stale_files:
        if stale_path.is_file():
            stale_path.unlink()

    mushroom_root = bp / "structures" / "tf_slice" / "mushroom"
    for directory_name in ("vanilla_brown", "vanilla_red"):
        stale_directory = mushroom_root / directory_name
        if stale_directory.parent != mushroom_root:
            raise ValueError("unsafe mushroom cleanup path: %s" % stale_directory)
        if stale_directory.is_dir():
            for stale_structure in stale_directory.glob("*.mcstructure"):
                stale_structure.unlink()
            stale_directory.rmdir()


def build_mushroom_forest(root):
    root = Path(root)
    bp = root / "TwilightBossSliceB"
    feature_dir = bp / "netease_features"
    rule_dir = bp / "netease_feature_rules"
    metadata_dir = bp / "metadata"
    mushroom_root = bp / "structures" / "tf_slice" / "mushroom"
    runtime_root = mushroom_root / "runtime"
    if runtime_root.is_dir():
        shutil.rmtree(str(runtime_root))

    catalog = {"format_version": 1, "variants": {"brown": [], "red": []}}

    brown_metadata = []
    for index in range(BROWN_VARIANTS):
        name = "v%02d" % index
        structure, metadata = build_canopy_mushroom(
            "brown", 0xB001 + index * 977, name
        )
        structure_name = "tf_slice:mushroom/brown_canopy/%s" % name
        write_mcstructure(_structure_path(bp, structure_name), structure)
        variant = _variant_catalog("brown", name, structure)
        variant["pieces"] = _write_runtime_pieces(
            bp, "brown", name, structure
        )
        catalog["variants"]["brown"].append(variant)
        brown_metadata.append(metadata)

    red_metadata = []
    for index in range(RED_VARIANTS):
        name = "v%02d" % index
        structure, metadata = build_canopy_mushroom(
            "red", 0xD001 + index * 977, name
        )
        structure_name = "tf_slice:mushroom/red_canopy/%s" % name
        write_mcstructure(_structure_path(bp, structure_name), structure)
        variant = _variant_catalog("red", name, structure)
        variant["pieces"] = _write_runtime_pieces(
            bp, "red", name, structure
        )
        catalog["variants"]["red"].append(variant)
        red_metadata.append(metadata)

    for kind in ("brown", "red"):
        trigger_structure = SparseStructure(
            (1, 1, 1), "%s_canopy_mushroom_trigger" % kind
        )
        trigger_structure.set(0, 0, 0, "minecraft:stone")
        trigger_name = "tf_slice:mushroom/canopy_trigger/%s" % kind
        write_mcstructure(
            _structure_path(bp, trigger_name),
            trigger_structure,
        )
        write_json(
            feature_dir / ("%s_canopy_mushroom_trigger_feature.json" % kind),
            _native_feature(
                "%s_canopy_mushroom_trigger_feature" % kind,
                trigger_name,
            ),
        )

    empty_structure_name = "tf_slice:mushroom/dummy"
    write_mcstructure(
        _structure_path(bp, empty_structure_name),
        SparseStructure((1, 1, 1), "mushroom_dummy"),
    )
    write_json(
        feature_dir / "mushroom_canopy_dummy_feature.json",
        _native_feature("mushroom_canopy_dummy_feature", empty_structure_name),
    )
    write_json(
        feature_dir / "mushroom_canopy_sparse_selector_feature.json",
        _selector(
            "mushroom_canopy_sparse_selector_feature",
            (
                ("brown_canopy_mushroom_trigger_feature", 60),
                ("red_canopy_mushroom_trigger_feature", 17),
                ("mushroom_canopy_dummy_feature", 323),
            ),
        ),
    )
    write_json(
        feature_dir / "mushroom_canopy_dense_selector_feature.json",
        _selector(
            "mushroom_canopy_dense_selector_feature",
            (
                ("brown_canopy_mushroom_trigger_feature", 1080),
                ("red_canopy_mushroom_trigger_feature", 117),
                ("mushroom_canopy_dummy_feature", 403),
            ),
        ),
    )

    structure_y = "query.get_height_at(variable.worldx, variable.worldz)"
    for rule_name, feature, keys, iterations in (
        (
            "mushroom_canopy_sparse_feature_rule",
            "mushroom_canopy_sparse_selector_feature",
            ["mushroom_forest"],
            "3 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
        ),
        (
            "mushroom_canopy_dense_feature_rule",
            "mushroom_canopy_dense_selector_feature",
            ["dense_mushroom_forest"],
            "5 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
        ),
    ):
        write_json(
            rule_dir / ("%s.json" % rule_name),
            _surface_rule(
                rule_name,
                feature,
                keys,
                iterations=iterations,
                y=structure_y,
                pass_name="after_surface_pass",
            ),
        )

    for identifier, log, leaves, height in (
        (
            "mushroom_vanilla_oak_tree_feature",
            "minecraft:oak_log",
            "minecraft:oak_leaves",
            (4, 6),
        ),
        (
            "mushroom_vanilla_birch_tree_feature",
            "minecraft:birch_log",
            "minecraft:birch_leaves",
            (5, 7),
        ),
    ):
        write_json(
            feature_dir / ("%s.json" % identifier),
            _vanilla_tree_feature(identifier, log, leaves, height),
        )
    for source_name, identifier in (
        ("twilight_oak_tree_feature.json", "mushroom_twilight_oak_tree_feature"),
        (
            "large_twilight_oak_tree_feature.json",
            "mushroom_large_twilight_oak_tree_feature",
        ),
        ("canopy_tree_feature.json", "mushroom_canopy_tree_feature"),
    ):
        write_json(
            feature_dir / ("%s.json" % identifier),
            _copy_tree(feature_dir / source_name, identifier),
        )
    write_json(
        feature_dir / "mushroom_vanilla_trees_selector_feature.json",
        _selector(
            "mushroom_vanilla_trees_selector_feature",
            (
                ("mushroom_vanilla_oak_tree_feature", 3),
                ("mushroom_vanilla_birch_tree_feature", 4),
                ("mushroom_twilight_oak_tree_feature", 9),
            ),
        ),
    )
    write_json(
        feature_dir / "mushroom_canopy_tree_selector_feature.json",
        _selector(
            "mushroom_canopy_tree_selector_feature",
            (
                ("mushroom_canopy_tree_feature", 3),
                ("mushroom_twilight_oak_tree_feature", 2),
            ),
        ),
    )

    common_keys = ["mushroom_forest", "dense_mushroom_forest"]
    tree_rules = (
        (
            "mushroom_biomes_vanilla_tree_feature_rule",
            "mushroom_vanilla_trees_selector_feature",
            1,
        ),
        (
            "mushroom_biomes_twilight_oak_tree_feature_rule",
            "mushroom_twilight_oak_tree_feature",
            "1 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
        ),
        (
            "mushroom_biomes_large_twilight_oak_tree_feature_rule",
            "mushroom_large_twilight_oak_tree_feature",
            "1 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
        ),
        (
            "mushroom_biomes_canopy_tree_feature_rule",
            "mushroom_canopy_tree_selector_feature",
            1,
        ),
    )
    for rule_name, feature, iterations in tree_rules:
        write_json(
            rule_dir / ("%s.json" % rule_name),
            _surface_rule(
                rule_name,
                feature,
                common_keys,
                iterations=iterations,
            ),
        )

    _build_mycelium_blob(feature_dir, rule_dir)
    _patch_mycelium_ground(feature_dir)
    _patch_biome_surfaces(root)
    _remove_independent_vanilla_huge_mushrooms(
        bp, feature_dir, rule_dir
    )

    for stale_path in (
        feature_dir / "brown_canopy_mushroom_selector_feature.json",
        feature_dir / "red_canopy_mushroom_selector_feature.json",
        feature_dir / "brown_canopy_mushroom_tree_feature.json",
        feature_dir / "red_canopy_mushroom_tree_feature.json",
        feature_dir / "mushroom_forest_tree_profile_feature.json",
        feature_dir / "dense_mushroom_forest_tree_profile_feature.json",
        rule_dir / "mushroom_forest_tree_profile_feature_rule.json",
        rule_dir / "dense_mushroom_forest_tree_profile_feature_rule.json",
    ):
        if stale_path.exists():
            stale_path.unlink()
    for stale_pattern in (
        "brown_canopy_mushroom_v*_feature.json",
        "red_canopy_mushroom_v*_feature.json",
    ):
        for stale_path in feature_dir.glob(stale_pattern):
            stale_path.unlink()

    _write_catalog_module(bp, catalog)

    write_json(
        metadata_dir / "mushroom_forest_generation.json",
        {
            "source_version": SOURCE_VERSION,
            "brown_canopy_variants": brown_metadata,
            "red_canopy_variants": red_metadata,
            "selector_weights": {
                "sparse": {"brown": 60, "red": 17, "dummy": 323},
                "dense": {"brown": 1080, "red": 117, "dummy": 403},
            },
            "placement": (
                "noop 1x1 trigger plus deferred chunk-piece placement"
            ),
            "attempts": {
                "sparse": "3 + 10% chance of 1",
                "dense": "5 + 10% chance of 1",
            },
            "mycelium_blob": {
                "chance": "1/3",
                "radius": [4, 5, 6],
                "source_half_height": 3,
                "implementation": "surface-conforming scatter patch",
            },
            "huge_mushroom_bits": {
                "cap": list(range(1, 10)),
                "stem": 10,
            },
        },
    )


if __name__ == "__main__":
    build_mushroom_forest(Path(__file__).resolve().parents[1])
