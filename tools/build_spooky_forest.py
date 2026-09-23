#!/usr/bin/env python3
"""Build source-faithful spooky-forest trees and decorations."""

import json
import math
import random
from pathlib import Path

from build_ruin_structures import SparseStructure, write_mcstructure
from swamp_tree_placement import structure_tree_documents


TREE_VARIANTS = 16
TREE_SIZE = (19, 36, 19)
TREE_CENTER = (9, 5, 9)
DEAD_TREE_GROUND = (
    "minecraft:grass",
    "minecraft:grass_block",
    "minecraft:dirt",
    "minecraft:podzol",
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


def _axis_block(prefix, axis):
    if axis == "x":
        return "tf_slice:%s_log_x" % prefix
    if axis == "z":
        return "tf_slice:%s_log_z" % prefix
    return "tf_slice:%s_log" % prefix


def _axis(previous, current):
    dx = current[0] - previous[0]
    dz = current[2] - previous[2]
    if dx:
        return "x"
    if dz:
        return "z"
    return "y"


def _dead_tree(seed, name):
    rng = random.Random(seed)
    structure = SparseStructure(TREE_SIZE, name)
    center_x, base_y, center_z = TREE_CENTER
    height = 20 + rng.randint(0, 5) + rng.randint(0, 5)
    branch_count = 3 + rng.randint(0, 1)
    branch_length = 10 + rng.randint(0, 1)
    start_yaw = rng.random()
    pitch = 0.2
    axis_counts = {"x": 0, "y": 0, "z": 0}
    maximum_reach = 0

    for y in range(base_y, base_y + height + 1):
        structure.set(center_x, y, center_z, "tf_slice:canopy_log")
        axis_counts["y"] += 1

    for branch_index in range(branch_count):
        yaw = start_yaw + 0.3 * branch_index
        start = (
            center_x,
            base_y + height - 7 + branch_index,
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
        maximum_reach = max(
            maximum_reach,
            abs(end[0] - center_x),
            abs(end[2] - center_z),
        )
        points = _line(start, end)
        for index, point in enumerate(points):
            previous = points[max(0, index - 1)]
            axis = _axis(previous, point) if index else "y"
            structure.set(
                point[0],
                point[1],
                point[2],
                _axis_block("canopy", axis),
            )
            axis_counts[axis] += 1
        tip_blocks = (
            ((0, -1, 0), "y"),
            ((1, 0, 0), "x"),
            ((-1, 0, 0), "x"),
            ((0, 0, 1), "z"),
            ((0, 0, -1), "z"),
        )
        for offset, axis in tip_blocks:
            structure.set(
                end[0] + offset[0],
                end[1] + offset[1],
                end[2] + offset[2],
                _axis_block("canopy", axis),
            )
            axis_counts[axis] += 1

    root_count = 3 + rng.randint(0, 1)
    root_yaw = rng.random()
    for root_index in range(root_count):
        yaw = root_yaw + float(root_index) / float(root_count)
        end = (
            center_x + int(round(math.sin(yaw * math.tau) * 5)),
            0,
            center_z + int(round(math.cos(yaw * math.tau) * 5)),
        )
        for point in _line((center_x, base_y, center_z), end):
            root_block = (
                "tf_slice:liveroot_block"
                if rng.randint(1, 7) == 1
                else "tf_slice:root_block"
            )
            structure.set(point[0], point[1], point[2], root_block)

    return structure, {
        "id": name,
        "height": height,
        "branch_count": branch_count,
        "branch_length": branch_length,
        "branch_pitch": pitch,
        "horizontal_reach": maximum_reach,
        "axis_counts": axis_counts,
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


def _dead_tree_anchor_feature():
    return dead_tree_placement_documents()["spooky_dead_tree_anchor_feature.json"]


def dead_tree_placement_documents():
    return structure_tree_documents(
        "spooky_dead_tree", "tf_slice:canopy_log", DEAD_TREE_GROUND,
        ("minecraft:air", "minecraft:tallgrass", "minecraft:short_grass", "minecraft:vine"),
        TREE_VARIANTS,
    )


def _dead_tree_offset_feature(identifier, placed_feature):
    center_x, base_y, center_z = TREE_CENTER
    return {
        "format_version": "1.20.30",
        "minecraft:scatter_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_feature": "tf_slice:%s" % placed_feature,
            "distribution": {
                "iterations": 1,
                "coordinate_eval_order": "xzy",
                "x": -center_x,
                "y": -base_y,
                "z": -center_z,
            },
        },
    }


def _dead_tree_sequence_feature(identifier, offset_feature):
    expected_offset = identifier.replace("_sequence_feature", "_offset_feature")
    if offset_feature != expected_offset:
        raise ValueError("dead tree offset does not match variant")
    return dead_tree_placement_documents()[identifier + ".json"]


def _spooky_filter():
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
                    "value": "tf_slice_biome_spooky_forest",
                },
            ]
        }
    ]


def _surface_rule(identifier, feature, chance=None, y=None, pass_name="after_surface_pass"):
    distribution = {
        "iterations": 1,
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
                "minecraft:biome_filter": _spooky_filter(),
            },
            "distribution": distribution,
        },
    }


def _copy_tree_with_spooky_leaves(source, identifier):
    document = json.loads(source.read_text(encoding="utf-8"))
    tree = document["minecraft:tree_feature"]
    tree["description"]["identifier"] = "tf_slice:%s" % identifier
    encoded = json.dumps(document)
    encoded = encoded.replace(
        "tf_slice:twilight_oak_leaves",
        "tf_slice:spooky_twilight_oak_leaves",
    )
    return json.loads(encoded)


def _small_structure_features(bp, feature_dir):
    lamp_features = []
    for height in range(1, 5):
        structure = SparseStructure((1, height + 1, 1), "spooky_lamp_%d" % height)
        for y in range(height):
            structure.set(0, y, 0, "tf_slice:canopy_fence")
        structure.set(0, height, 0, "minecraft:lit_pumpkin")
        structure_name = "tf_slice:spooky/pumpkin_lamppost/h%d" % height
        write_mcstructure(
            _structure_path(bp, structure_name),
            structure,
        )
        feature_id = "spooky_pumpkin_lamppost_h%d_feature" % height
        write_json(feature_dir / ("%s.json" % feature_id), _native_feature(feature_id, structure_name))
        lamp_features.append(feature_id)
    write_json(
        feature_dir / "spooky_pumpkin_lamppost_selector_feature.json",
        _selector("spooky_pumpkin_lamppost_selector_feature", lamp_features),
    )

    for prefix in ("canopy", "twilight_oak"):
        log_features = []
        block_prefix = "canopy" if prefix == "canopy" else "twilight_oak"
        for axis in ("x", "z"):
            for length in range(3, 7):
                size = (length, 1, 1) if axis == "x" else (1, 1, length)
                structure = SparseStructure(size, "spooky_%s_log_%s_%d" % (prefix, axis, length))
                for offset in range(length):
                    x = offset if axis == "x" else 0
                    z = offset if axis == "z" else 0
                    structure.set(x, 0, z, _axis_block(block_prefix, axis))
                structure_name = "tf_slice:spooky/fallen_%s/%s%d" % (prefix, axis, length)
                write_mcstructure(
                    _structure_path(bp, structure_name),
                    structure,
                )
                feature_id = "spooky_%s_fallen_log_%s%d_feature" % (prefix, axis, length)
                write_json(feature_dir / ("%s.json" % feature_id), _native_feature(feature_id, structure_name))
                log_features.append(feature_id)
        selector_id = "spooky_%s_fallen_log_selector_feature" % prefix
        write_json(feature_dir / ("%s.json" % selector_id), _selector(selector_id, log_features))


def build_spooky_forest(root):
    root = Path(root)
    bp = root / "TwilightBossSliceB"
    feature_dir = bp / "netease_features"
    rule_dir = bp / "netease_feature_rules"
    metadata_dir = bp / "metadata"

    variants = []
    tree_features = []
    write_json(
        feature_dir / "spooky_dead_tree_anchor_feature.json",
        _dead_tree_anchor_feature(),
    )
    for index in range(TREE_VARIANTS):
        name = "v%02d" % index
        structure, metadata = _dead_tree(0x5F001 + index * 977, name)
        structure_name = "tf_slice:spooky/dead_tree/%s" % name
        write_mcstructure(
            _structure_path(bp, structure_name),
            structure,
        )
        feature_id = "spooky_dead_tree_%s_feature" % name
        write_json(
            feature_dir / ("%s.json" % feature_id),
            _native_feature(feature_id, structure_name),
        )
        offset_id = "spooky_dead_tree_%s_offset_feature" % name
        sequence_id = "spooky_dead_tree_%s_sequence_feature" % name
        write_json(
            feature_dir / ("%s.json" % offset_id),
            _dead_tree_offset_feature(offset_id, feature_id),
        )
        write_json(
            feature_dir / ("%s.json" % sequence_id),
            _dead_tree_sequence_feature(sequence_id, offset_id),
        )
        tree_features.append(sequence_id)
        variants.append(metadata)
    for filename, document in dead_tree_placement_documents().items():
        write_json(feature_dir / filename, document)
    write_json(
        feature_dir / "spooky_dead_tree_selector_feature.json",
        _selector("spooky_dead_tree_selector_feature", tree_features),
    )

    write_json(
        feature_dir / "spooky_twilight_oak_tree_feature.json",
        _copy_tree_with_spooky_leaves(
            feature_dir / "twilight_oak_tree_feature.json",
            "spooky_twilight_oak_tree_feature",
        ),
    )
    write_json(
        feature_dir / "spooky_large_twilight_oak_tree_feature.json",
        _copy_tree_with_spooky_leaves(
            feature_dir / "large_twilight_oak_tree_feature.json",
            "spooky_large_twilight_oak_tree_feature",
        ),
    )
    _small_structure_features(bp, feature_dir)

    web_feature = {
        "format_version": "1.21.40",
        "minecraft:single_block_feature": {
            "description": {"identifier": "tf_slice:spooky_web_feature"},
            "places_block": [{"block": "minecraft:web", "weight": 1}],
            "enforce_placement_rules": False,
            "enforce_survivability_rules": False,
            "may_replace": ["minecraft:air"],
            "may_attach_to": {
                "auto_rotate": False,
                "min_sides_must_attach": 1,
                "top": [
                    "tf_slice:canopy_log",
                    "tf_slice:canopy_log_x",
                    "tf_slice:canopy_log_z",
                    "tf_slice:twilight_oak_log",
                    "tf_slice:twilight_oak_log_x",
                    "tf_slice:twilight_oak_log_z",
                    "tf_slice:canopy_leaves",
                    "tf_slice:twilight_oak_leaves",
                    "tf_slice:spooky_twilight_oak_leaves",
                    "minecraft:oak_log",
                    "minecraft:birch_log",
                    "minecraft:oak_leaves",
                    "minecraft:birch_leaves",
                ],
            },
        },
    }
    write_json(feature_dir / "spooky_web_feature.json", web_feature)
    write_json(
        feature_dir / "spooky_web_search_feature.json",
        {
            "format_version": "1.13.0",
            "minecraft:search_feature": {
                "description": {
                    "identifier": "tf_slice:spooky_web_search_feature"
                },
                "places_feature": "tf_slice:spooky_web_feature",
                "search_volume": {
                    "min": [0, -31, 0],
                    "max": [0, 0, 0],
                },
                "search_axis": "-y",
                "required_successes": 1,
            },
        },
    )
    web_rule = _surface_rule(
        "spooky_web_feature_rule",
        "spooky_web_search_feature",
    )
    web_rule["minecraft:feature_rules"]["distribution"]["iterations"] = 60
    write_json(rule_dir / "spooky_web_feature_rule.json", web_rule)

    write_json(
        rule_dir / "spooky_pumpkin_lamppost_feature_rule.json",
        _surface_rule(
            "spooky_pumpkin_lamppost_feature_rule",
            "spooky_pumpkin_lamppost_selector_feature",
            10.0,
        ),
    )
    for prefix, rule_name in (
        ("canopy", "spooky_canopy_fallen_log_feature_rule"),
        ("twilight_oak", "spooky_oak_fallen_log_feature_rule"),
    ):
        write_json(
            rule_dir / ("%s.json" % rule_name),
            _surface_rule(
                rule_name,
                "spooky_%s_fallen_log_selector_feature" % prefix,
                2.5,
            ),
        )

    for name, block, iterations, radius, chance in (
        ("spooky_dead_bush", "minecraft:deadbush", 20, 7, None),
        ("spooky_pumpkin", "minecraft:pumpkin", 8, 5, 3.125),
    ):
        base_id = "%s_feature" % name
        patch_id = "%s_patch_feature" % name
        write_json(
            feature_dir / ("%s.json" % base_id),
            {
                "format_version": "1.21.40",
                "minecraft:single_block_feature": {
                    "description": {"identifier": "tf_slice:%s" % base_id},
                    "places_block": [{"block": block, "weight": 1}],
                    "enforce_placement_rules": False,
                    "enforce_survivability_rules": False,
                    "may_replace": ["minecraft:air"],
                    "may_attach_to": {
                        "auto_rotate": False,
                        "min_sides_must_attach": 1,
                        "bottom": ["minecraft:grass", "minecraft:grass_block", "minecraft:dirt"],
                    },
                },
            },
        )
        write_json(
            feature_dir / ("%s.json" % patch_id),
            {
                "format_version": "1.21.10",
                "minecraft:scatter_feature": {
                    "description": {"identifier": "tf_slice:%s" % patch_id},
                    "places_feature": "tf_slice:%s" % base_id,
                    "project_input_to_floor": True,
                    "distribution": {
                        "iterations": iterations,
                        "coordinate_eval_order": "xzy",
                        "x": {"distribution": "triangle", "extent": [-radius, radius]},
                        "y": 0,
                        "z": {"distribution": "triangle", "extent": [-radius, radius]},
                    },
                },
            },
        )
        write_json(
            rule_dir / ("%s_rule.json" % patch_id),
            _surface_rule("%s_rule" % patch_id, patch_id, chance),
        )

    write_json(
        rule_dir / "spooky_mayapple_patch_feature_rule.json",
        _surface_rule(
            "spooky_mayapple_patch_feature_rule",
            "mayapple_patch_feature",
        ),
    )
    write_json(
        rule_dir / "spooky_groundcover_patch_feature_rule.json",
        _surface_rule(
            "spooky_groundcover_patch_feature_rule",
            "forest_groundcover_patch_feature",
        ),
    )
    write_json(
        metadata_dir / "spooky_forest_generation.json",
        {
            "source_version": "4.3.2508",
            "dead_tree_variants": variants,
            "web_attempts_per_chunk": 60,
            "web_search_depth": 32,
            "pumpkin_lamppost_chance_percent": 10.0,
            "fallen_log_chance_percent_each": 2.5,
        },
    )


if __name__ == "__main__":
    build_spooky_forest(Path(__file__).resolve().parents[1])
