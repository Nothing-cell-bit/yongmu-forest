#!/usr/bin/env python3
"""Build source-locked Twilight Swamp and Fire Swamp worldgen features."""

from __future__ import print_function

import json
import math
import random
import shutil
from pathlib import Path

from build_ruin_structures import SparseStructure, write_mcstructure
from native_structure_worldgen_safety import guard_native_structure_rules
from swamp_tree_placement import TREE_LOGS, tree_placement_documents
from PIL import Image

HUGE_LILY_QUADRANT_POSITIONS = {
    "nw": (0, 0),
    "ne": (1, 0),
    "se": (1, 1),
    "sw": (0, 1),
}
HUGE_LILY_SINGLE_CLEARANCE_POSITIONS = (
    ("nw", (0, 0)),
    ("ne", (1, 0)),
    ("se", (1, 1)),
    ("sw", (0, 1)),
    ("west", (-1, 0)),
    ("northwest", (-1, -1)),
    ("north", (0, -1)),
    ("northeast", (1, -1)),
    ("southwest", (-1, 1)),
)
HUGE_LILY_QUADRANT_TEXTURE_BOXES = {
    "nw": (0, 0, 16, 16),
    "ne": (16, 0, 32, 16),
    "se": (16, 16, 32, 32),
    "sw": (0, 16, 16, 32),
}
HUGE_LILY_PAD_TEXTURE_REVISION_SUFFIX = "_clean_v2"
HUGE_LILY_PAD_WORLD_TINT = "#208030"
HUGE_LILY_PAD_ITEM_TINT = "#71C35C"


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def biome_filter(biome_key):
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
                    "value": "tf_slice_biome_%s" % biome_key,
                },
            ]
        }
    ]


def feature_rule(
    identifier,
    feature,
    biome_key,
    iterations,
    y=None,
    chance=None,
    pass_name="after_surface_pass",
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
                "minecraft:biome_filter": biome_filter(biome_key),
            },
            "distribution": distribution,
        },
    }


def single_block_feature(identifier, block, bottom, may_replace=None):
    return {
        "format_version": "1.21.40",
        "minecraft:single_block_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_block": [{"block": block, "weight": 1}],
            "enforce_placement_rules": False,
            "enforce_survivability_rules": False,
            "may_replace": may_replace or ["minecraft:air"],
            "may_attach_to": {
                "auto_rotate": False,
                "min_sides_must_attach": 1,
                "bottom": bottom,
            },
        },
    }


def offset_feature(identifier, feature, x, y, z):
    return {
        "format_version": "1.20.30",
        "minecraft:scatter_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_feature": "tf_slice:%s" % feature,
            "distribution": {
                "iterations": 1,
                "coordinate_eval_order": "xzy",
                "x": x,
                "y": y,
                "z": z,
            },
        },
    }


def patch_feature(
    identifier,
    feature,
    iterations,
    radius=7,
    project_input_to_floor=False,
):
    body = {
        "description": {"identifier": "tf_slice:%s" % identifier},
        "places_feature": "tf_slice:%s" % feature,
        "distribution": {
            "iterations": iterations,
            "coordinate_eval_order": "xzy",
            "x": {"distribution": "triangle", "extent": [-radius, radius]},
            "y": 0,
            "z": {"distribution": "triangle", "extent": [-radius, radius]},
        },
    }
    if project_input_to_floor:
        body["project_input_to_floor"] = True
    return {
        "format_version": "1.21.10",
        "minecraft:scatter_feature": body,
    }


def sequence_feature(identifier, features):
    return {
        "format_version": "1.20.30",
        "minecraft:sequence_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "features": ["tf_slice:%s" % feature for feature in features],
        },
    }


def huge_lily_pad_texture_entry(texture_name, tint_color):
    return {
        "textures": [
            {
                "path": "textures/blocks/%s" % texture_name,
                "tint_color": str(tint_color),
            }
        ]
    }


def huge_lily_pad_texture_stem(block_id):
    return "%s%s" % (block_id, HUGE_LILY_PAD_TEXTURE_REVISION_SUFFIX)


def huge_lily_pad_quadrant_images(source_image):
    rgba = source_image.convert("RGBA")
    if rgba.size != (32, 32):
        raise ValueError(
            "huge lily pad source texture must be 32x32, got %r"
            % (rgba.size,)
        )
    return {
        quadrant: rgba.crop(box).transpose(
            Image.Transpose.FLIP_LEFT_RIGHT
        )
        for quadrant, box in HUGE_LILY_QUADRANT_TEXTURE_BOXES.items()
    }


def huge_lily_pad_public_image(source_image):
    rgba = source_image.convert("RGBA")
    if rgba.size != (32, 32):
        raise ValueError(
            "huge lily pad source texture must be 32x32, got %r"
            % (rgba.size,)
        )

    return rgba.transpose(Image.Transpose.ROTATE_270)


def huge_lily_pad_clearance_documents(bottom):
    block_feature = "huge_lily_pad_clearance_block_feature"
    documents = {
        block_feature + ".json": single_block_feature(
            block_feature,
            "minecraft:air",
            bottom,
        )
    }
    position_features = []
    for name, (x, z) in HUGE_LILY_SINGLE_CLEARANCE_POSITIONS:
        position_feature = (
            "huge_lily_pad_clearance_%s_position_feature" % name
        )
        documents[position_feature + ".json"] = offset_feature(
            position_feature,
            block_feature,
            x,
            0,
            z,
        )
        position_features.append(position_feature)
    return documents, position_features


def huge_lily_pad_structure(facing):
    facings = ("north", "east", "south", "west")
    if facing not in facings:
        raise ValueError("unknown huge lily pad facing: %s" % facing)
    turns = facings.index(facing)
    structure = SparseStructure(
        (2, 1, 2),
        "huge_lily_pad_%s" % facing,
    )
    for quadrant in ("nw", "ne", "se", "sw"):
        x, z = HUGE_LILY_QUADRANT_POSITIONS[quadrant]
        for _ in range(turns):
            x, z = 1 - z, x
        structure.set(
            x,
            0,
            z,
            "tf_slice:huge_lily_pad_%s" % quadrant,
            {"tf_slice:facing": facing},
        )
    return structure


def huge_lily_pad_structure_feature_document(identifier, structure_name):
    return {
        "format_version": "1.20.30",
        "minecraft:structure_template_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "structure_name": structure_name,
            "adjustment_radius": 0,
            "facing_direction": "north",
            "constraints": {
                "block_intersection": {
                    "block_allowlist": ["minecraft:air"],
                }
            },
        },
    }


def huge_lily_pad_atomic_sequence_document(
    identifier,
    clearance_features,
    structure_feature,
):
    return sequence_feature(
        identifier,
        list(clearance_features) + [structure_feature],
    )


def huge_lily_pad_single_sequence_document(identifier, clearance_features):
    return sequence_feature(
        identifier,
        list(clearance_features) + ["huge_lily_pad_feature"],
    )


def huge_lily_pad_natural_sequences():
    return (("huge_lily_pad_2x2_feature", 1),)


def native_structure_feature(identifier, structure_name):
    return {
        "format_version": "1.14.0",
        "netease:structure_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_structure": structure_name,
            "rotation": 0,
        },
    }


def selector_feature(identifier, features):
    return {
        "format_version": "1.20.30",
        "minecraft:weighted_random_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "features": [["tf_slice:%s" % feature, 1] for feature in features],
        },
    }


def weighted_selector_feature(identifier, features):
    return {
        "format_version": "1.20.30",
        "minecraft:weighted_random_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "features": [
                ["tf_slice:%s" % feature, weight]
                for feature, weight in features
            ],
        },
    }


def search_feature(identifier, feature, minimum, maximum, axis="-y"):
    return {
        "format_version": "1.13.0",
        "minecraft:search_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_feature": "tf_slice:%s" % feature,
            "search_volume": {"min": minimum, "max": maximum},
            "search_axis": axis,
            "required_successes": 1,
        },
    }


def lily_quadrant_block(identifier):
    rotations = {
        "north": 0,
        "east": -90,
        "south": 180,
        "west": 90,
    }
    return {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": {
                "identifier": "tf_slice:%s" % identifier,
                "register_to_creative_menu": False,
                "states": {
                    "tf_slice:facing": ["north", "east", "south", "west"]
                },
            },
            "components": {
                "netease:neighborchanged_sendto_script": {"value": True},
                "netease:random_tick": {"enable": True, "tick_to_script": True},
                "minecraft:destructible_by_mining": {
                    "seconds_to_destroy": 0.0
                },
                "minecraft:destructible_by_explosion": {
                    "explosion_resistance": 0.0
                },
                "minecraft:geometry": (
                    "geometry.tf_slice.huge_lily_pad_quadrant"
                ),
                "minecraft:material_instances": {
                    "*": {
                        "texture": "tf_slice:%s" % identifier,
                        "render_method": "alpha_test",
                        "ambient_occlusion": False,
                        "face_dimming": False,
                    }
                },
                "netease:render_layer": {"value": "optionalAlpha"},
                "netease:solid": {"value": False},
                "netease:pathable": {"value": True},
                "netease:aabb": {
                    "collision": {
                        "min": [0.0, 0.0, 0.0],
                        "max": [1.0, 0.0625, 1.0],
                    },
                    "clip": {
                        "min": [0.0, 0.0, 0.0],
                        "max": [1.0, 0.0625, 1.0],
                    },
                },
            },
            "permutations": [
                {
                    "condition": (
                        "query.block_state('tf_slice:facing') == '%s'" % facing
                    ),
                    "components": {
                        "minecraft:transformation": {
                            "rotation": [0, rotation, 0]
                        }
                    },
                }
                for facing, rotation in rotations.items()
            ],
        },
    }


def huge_lily_pad_block():
    return {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": {
                "identifier": "tf_slice:huge_lily_pad",
                "register_to_creative_menu": True,
            },
            "components": {
                "netease:neighborchanged_sendto_script": {"value": True},
                "netease:random_tick": {"enable": True, "tick_to_script": True},
                "minecraft:destructible_by_mining": {
                    "seconds_to_destroy": 0.0
                },
                "minecraft:destructible_by_explosion": {
                    "explosion_resistance": 0.0
                },
                # NetEase accepts a 30-pixel plane but rejects the source's
                # full 32-pixel block schematic.
                "minecraft:geometry": "geometry.tf_slice.huge_lily_pad_item",
                "minecraft:material_instances": {
                    "*": {
                        "texture": "tf_slice:huge_lily_pad",
                        "render_method": "alpha_test",
                        "ambient_occlusion": False,
                        "face_dimming": False,
                    }
                },
                "netease:render_layer": {"value": "optionalAlpha"},
                "netease:solid": {"value": False},
                "netease:pathable": {"value": True},
                "netease:aabb": {
                    "collision": {
                        "min": [0.0, 0.0, 0.0],
                        "max": [1.875, 0.0625, 1.875],
                    },
                    "clip": {
                        "min": [0.0, 0.0, 0.0],
                        "max": [1.875, 0.0625, 1.875],
                    },
                },
            },
        },
    }


def huge_water_lily_block():
    return {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": {
                "identifier": "tf_slice:huge_water_lily",
                "register_to_creative_menu": True,
            },
            "components": {
                "netease:neighborchanged_sendto_script": {"value": True},
                "netease:random_tick": {"enable": True, "tick_to_script": True},
                "minecraft:destructible_by_mining": {
                    "seconds_to_destroy": 0.0
                },
                "minecraft:destructible_by_explosion": {
                    "explosion_resistance": 0.0
                },
                "minecraft:collision_box": False,
                "minecraft:selection_box": {
                    "origin": [-7, 0, -7],
                    "size": [14, 16, 14],
                },
                "minecraft:geometry": "geometry.tf_slice.huge_water_lily",
                "minecraft:material_instances": {
                    "*": {
                        "texture": "tf_slice:huge_water_lily",
                        "render_method": "alpha_test",
                        "ambient_occlusion": False,
                        "face_dimming": False,
                    }
                },
                "netease:render_layer": {"value": "optionalAlpha"},
                "netease:solid": {"value": False},
                "netease:pathable": {"value": True},
            },
        },
    }


def swamp_plant_geometry():
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": "geometry.tf_slice.huge_lily_pad_item",
                    "texture_width": 32,
                    "texture_height": 32,
                    "visible_bounds_width": 2,
                    "visible_bounds_height": 1,
                    "visible_bounds_offset": [0, 0.03125, 0],
                },
                "bones": [
                    {
                        "name": "pad",
                        "pivot": [0, 0, 0],
                        "cubes": [
                            {
                                "origin": [-8, 0, -8],
                                "size": [30, 1, 30],
                                "uv": {
                                    "up": {
                                        "uv": [0, 0],
                                        "uv_size": [32, 32],
                                        "material_instance": "*",
                                    }
                                },
                            }
                        ],
                    }
                ],
            },
            {
                "description": {
                    "identifier": (
                        "geometry.tf_slice.huge_lily_pad_quadrant"
                    ),
                    "texture_width": 16,
                    "texture_height": 16,
                    "visible_bounds_width": 2,
                    "visible_bounds_height": 1,
                    "visible_bounds_offset": [0, 0.03125, 0],
                },
                "bones": [
                    {
                        "name": "pad",
                        "pivot": [0, 0, 0],
                        "cubes": [
                            {
                                "origin": [-8, 0, -8],
                                "size": [16, 1, 16],
                                "uv": {
                                    "up": {
                                        "uv": [0, 0],
                                        "uv_size": [16, 16],
                                        "material_instance": "*",
                                    },
                                },
                            }
                        ],
                    }
                ],
            },
            {
                "description": {
                    "identifier": "geometry.tf_slice.huge_water_lily",
                    "texture_width": 16,
                    "texture_height": 16,
                    "visible_bounds_width": 2,
                    "visible_bounds_height": 1,
                    "visible_bounds_offset": [0, 0.5, 0],
                },
                "bones": [
                    {
                        "name": "cross_%s" % name,
                        "pivot": [0, 0, 0],
                        "cubes": [
                            {
                                "origin": [-8, 0, -0.05],
                                "size": [16, 16, 0.1],
                                "pivot": [0, 0, 0],
                                "rotation": [0, rotation, 0],
                                "uv": {
                                    face: {
                                        "uv": [0, 0],
                                        "uv_size": [16, 16],
                                        "material_instance": "*",
                                    }
                                    for face in ("north", "south")
                                },
                            }
                        ],
                    }
                    for name, rotation in (("a", 45), ("b", -45))
                ],
            },
        ],
    }


def axis_log_block(identifier, side_texture, end_texture, axis):
    return {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": {
                "identifier": "tf_slice:%s" % identifier,
                "register_to_creative_menu": False,
            },
            "components": {
                "minecraft:destructible_by_mining": {
                    "seconds_to_destroy": 2.0
                },
                "minecraft:destructible_by_explosion": {
                    "explosion_resistance": 3.0
                },
                "minecraft:geometry": "geometry.tf_slice.log_%s" % axis,
                "minecraft:material_instances": {
                    "side": {"texture": side_texture, "render_method": "opaque"},
                    "end": {"texture": end_texture, "render_method": "opaque"},
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


def set_if_empty(structure, x, y, z, block, states=None):
    position = (int(x), int(y), int(z))
    if position not in structure.blocks:
        structure.set(position[0], position[1], position[2], block, states)


TREE_VINE_SUPPORT_BLOCKS = frozenset(
    (
        "tf_slice:mangrove_log",
        "tf_slice:mangrove_log_x",
        "tf_slice:mangrove_log_z",
        "tf_slice:mangrove_leaves",
        "tf_slice:twilight_oak_log",
        "tf_slice:twilight_oak_leaves",
    )
)

# Each tuple describes an empty candidate relative to its support block.  The
# state bit points back from that candidate to the real support face.
TREE_VINE_OUTWARD_CANDIDATES = (
    (1, 0, 2),
    (-1, 0, 8),
    (0, 1, 4),
    (0, -1, 1),
)


def place_log_line(structure, start, end, vertical, horizontal_x, horizontal_z):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dz = end[2] - start[2]
    steps = max(abs(dx), abs(dy), abs(dz), 1)
    horizontal = horizontal_x if abs(dx) >= abs(dz) else horizontal_z
    block = vertical if abs(dy) > max(abs(dx), abs(dz)) else horizontal
    for step in range(steps + 1):
        progress = float(step) / float(steps)
        structure.set(
            round(start[0] + dx * progress),
            round(start[1] + dy * progress),
            round(start[2] + dz * progress),
            block,
        )


def place_leaf_spheroid(structure, center, radius, vertical_radius, leaf, rng, shag):
    cx, cy, cz = center
    limit = int(math.ceil(radius))
    vertical_limit = int(math.ceil(vertical_radius))
    for x in range(cx - limit, cx + limit + 1):
        for y in range(cy - vertical_limit, cy + vertical_limit + 1):
            for z in range(cz - limit, cz + limit + 1):
                distance = (
                    ((x - cx) / float(radius)) ** 2
                    + ((y - cy) / float(vertical_radius)) ** 2
                    + ((z - cz) / float(radius)) ** 2
                )
                edge_noise = rng.random() * 0.22 if shag else 0.0
                if distance <= 1.0 + edge_noise:
                    set_if_empty(structure, x, y, z, leaf)
    for unused in range(shag):
        angle = rng.random() * math.pi * 2.0
        distance = radius + rng.uniform(-0.4, 0.8)
        set_if_empty(
            structure,
            round(cx + math.cos(angle) * distance),
            cy + rng.choice((-1, 0, 0, 1)),
            round(cz + math.sin(angle) * distance),
            leaf,
        )


def place_hanging_vines(structure, center, crown_y, radius, rng, count):
    candidates = {}
    maximum_distance_squared = (radius + 1) ** 2
    for (support_x, support_y, support_z), block in sorted(
        structure.blocks.items()
    ):
        if support_y != crown_y or block[0] not in TREE_VINE_SUPPORT_BLOCKS:
            continue
        if (
            (support_x - center) ** 2 + (support_z - center) ** 2
            > maximum_distance_squared
        ):
            continue
        for offset_x, offset_z, direction_bit in TREE_VINE_OUTWARD_CANDIDATES:
            position = (
                support_x + offset_x,
                support_y,
                support_z + offset_z,
            )
            if not (
                0 <= position[0] < structure.size[0]
                and 0 <= position[1] < structure.size[1]
                and 0 <= position[2] < structure.size[2]
            ):
                continue
            if position in structure.blocks:
                continue
            candidates[position] = candidates.get(position, 0) | direction_bit

    ranked_candidates = []
    for position, direction_bits in candidates.items():
        empty_run = 0
        for drop in range(3):
            strand_position = (position[0], position[1] - drop, position[2])
            if strand_position[1] < 0 or strand_position in structure.blocks:
                break
            empty_run += 1
        if empty_run:
            ranked_candidates.append((empty_run, position, direction_bits))

    rng.shuffle(ranked_candidates)
    ranked_candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    used_columns = set()
    placed_strands = 0
    for empty_run, position, direction_bits in ranked_candidates:
        column = (position[0], position[2])
        if placed_strands >= count:
            break
        if column in used_columns or position in structure.blocks:
            continue
        used_columns.add(column)
        length = min(rng.randint(1, 3), empty_run)
        for drop in range(length):
            structure.set(
                position[0],
                position[1] - drop,
                position[2],
                "minecraft:vine",
                {"vine_direction_bits": direction_bits},
            )
        placed_strands += 1


def place_fireflies(structure, center, base_y, heights):
    placements = (
        (center + 1, base_y + heights[0], center, "west"),
        (center, base_y + heights[1], center - 1, "south"),
    )
    for x, y, z, facing in placements:
        structure.set(
            x,
            y,
            z,
            "tf_slice:firefly",
            {"tf_slice:facing": facing},
        )


def mangrove_tree_structure(variant):
    rng = random.Random(4325080 + variant)
    center = 12
    base_y = 4
    height = 10 + rng.randrange(5)
    structure = SparseStructure((25, 25, 25), "mangrove_tree_v%02d" % variant)
    for y in range(base_y, base_y + height + 1):
        structure.set(center, y, center, "tf_slice:mangrove_log")

    branch_count = variant % 4
    crowns = [(center, base_y + height, center)]
    for index in range(branch_count):
        angle = (math.pi * 2.0 * index / max(branch_count, 1)) + variant * 0.63
        length = rng.randint(6, 8)
        start = (center, base_y + height - rng.randint(2, 5), center)
        end = (
            round(center + math.cos(angle) * length),
            start[1] + rng.randint(1, 3),
            round(center + math.sin(angle) * length),
        )
        place_log_line(
            structure,
            start,
            end,
            "tf_slice:mangrove_log",
            "tf_slice:mangrove_log_x",
            "tf_slice:mangrove_log_z",
        )
        crowns.append(end)

    for crown in crowns:
        place_leaf_spheroid(
            structure,
            crown,
            2.5 + rng.randrange(3),
            1.5,
            "tf_slice:mangrove_leaves",
            rng,
            15,
        )
    place_hanging_vines(
        structure, center, base_y + height - 1, 4, rng, 8
    )
    place_fireflies(structure, center, base_y, (5, 8))
    return structure, center, base_y


def swampy_oak_tree_structure(variant):
    rng = random.Random(4326080 + variant)
    center = 8
    base_y = 3
    height = 4 + rng.randrange(3)
    structure = SparseStructure((17, 14, 17), "swampy_oak_v%02d" % variant)
    for y in range(base_y, base_y + height + 1):
        structure.set(center, y, center, "tf_slice:twilight_oak_log")
    place_leaf_spheroid(
        structure,
        (center, base_y + height, center),
        2.25,
        2.0,
        "tf_slice:twilight_oak_leaves",
        rng,
        8,
    )
    place_hanging_vines(
        structure, center, base_y + height - 1, 2, rng, 6
    )
    return structure, center, base_y


def canopy_tree_structure(variant):
    rng = random.Random(4327080 + variant)
    center = 17
    base_y = 3
    height = 20 + rng.randrange(6) + rng.randrange(6)
    structure = SparseStructure((35, 36, 35), "canopy_tree_v%02d" % variant)
    for y in range(base_y, base_y + height + 1):
        structure.set(center, y, center, "tf_slice:canopy_log")
    crowns = [(center, base_y + height, center)]
    branch_count = 3 + (variant % 2)
    for index in range(branch_count):
        angle = (math.pi * 2.0 * index / float(branch_count)) + variant * 0.47
        length = rng.randint(10, 11)
        start = (center, base_y + height - 7 + rng.randint(0, 4), center)
        end = (
            round(center + math.cos(angle) * length),
            start[1] + rng.randint(1, 3),
            round(center + math.sin(angle) * length),
        )
        place_log_line(
            structure,
            start,
            end,
            "tf_slice:canopy_log",
            "tf_slice:canopy_log_x",
            "tf_slice:canopy_log_z",
        )
        crowns.append(end)
    for crown in crowns:
        place_leaf_spheroid(
            structure,
            crown,
            4.5 + rng.random(),
            1.5,
            "tf_slice:canopy_leaves",
            rng,
            24,
        )
    place_fireflies(structure, center, base_y, (7, 13))
    return structure, center, base_y


def build_tree_variants(bp, features, kind, factory, bottom):
    anchor_id = "%s_tree_anchor_feature" % kind
    placement_documents = (
        tree_placement_documents(kind) if kind in TREE_LOGS else {}
    )
    write_json(
        features / (anchor_id + ".json"),
        placement_documents.get(anchor_id + ".json") or single_block_feature(
            anchor_id,
            # The probe only validates the candidate floor.  A real trunk
            # block survives when the following cross-chunk structure is
            # rejected, producing the orphan one-block stumps seen in game.
            "minecraft:air",
            bottom,
            may_replace=[
                "minecraft:air",
                "minecraft:water",
                "minecraft:flowing_water",
                "minecraft:tallgrass",
                "minecraft:short_grass",
                "minecraft:vine",
            ],
        ),
    )
    sequences = []
    for variant in range(4):
        structure, center, base_y = factory(variant)
        structure_name = "tf_slice:swamp/trees/%s/v%02d" % (kind, variant)
        structure_path = (
            bp
            / "structures"
            / "tf_slice"
            / "swamp"
            / "trees"
            / kind
            / ("v%02d.mcstructure" % variant)
        )
        write_mcstructure(structure_path, structure)
        structure_id = "%s_tree_v%02d_structure_feature" % (kind, variant)
        offset_id = "%s_tree_v%02d_offset_feature" % (kind, variant)
        sequence_id = "%s_tree_v%02d_sequence_feature" % (kind, variant)
        write_json(
            features / (structure_id + ".json"),
            native_structure_feature(structure_id, structure_name),
        )
        write_json(
            features / (offset_id + ".json"),
            offset_feature(
                offset_id, structure_id, -center, -base_y, -center
            ),
        )
        write_json(
            features / (sequence_id + ".json"),
            placement_documents.get(sequence_id + ".json")
            or sequence_feature(sequence_id, [anchor_id, offset_id]),
        )
        sequences.append((sequence_id, 1))
    for filename, document in placement_documents.items():
        write_json(features / filename, document)
    return sequences


def vine_feature():
    supports = [
        "tf_slice:mangrove_log",
        "tf_slice:twilight_oak_log",
        "tf_slice:canopy_log",
        "minecraft:oak_log",
    ]
    attach = {
        "auto_rotate": True,
        "min_sides_must_attach": 1,
    }
    for side in ("north", "south", "east", "west"):
        attach[side] = supports
    return {
        "format_version": "1.21.40",
        "minecraft:single_block_feature": {
            "description": {"identifier": "tf_slice:swamp_vines_feature"},
            "places_block": [{"block": "minecraft:vine", "weight": 1}],
            "enforce_placement_rules": False,
            "enforce_survivability_rules": False,
            "may_replace": ["minecraft:air"],
            "may_attach_to": attach,
        },
    }


def fire_swamp_device_structure(identifier):
    """Return the source-visible 5x3x5 jet/smoker ground profile.

    The top layer is the source's repaired grass pad with the device embedded
    at its center.  The middle layer is the 3x3 lava reservoir and stone wall;
    the bottom layer is the complete stone floor.  Keeping this as one native
    structure avoids a partial sequence suppressing the final device block.
    """
    structure = SparseStructure(
        (5, 3, 5), "fire_swamp_%s" % identifier
    )
    for x in range(5):
        for z in range(5):
            structure.set(x, 0, z, "minecraft:stone")
            structure.set(
                x,
                1,
                z,
                (
                    "minecraft:lava"
                    if 1 <= x <= 3 and 1 <= z <= 3
                    else "minecraft:stone"
                ),
            )
            structure.set(x, 2, z, "minecraft:grass_block")
    states = {"tf_slice:jet_state": "idle"} if identifier == "fire_jet" else None
    structure.set(2, 2, 2, "tf_slice:%s" % identifier, states)
    return structure


def build_fire_swamp_devices(bp, features, rules):
    structure_root = bp / "structures" / "tf_slice" / "fire_swamp"
    source_surface = [
        "minecraft:grass",
        "minecraft:grass_block",
        "minecraft:dirt",
        "minecraft:clay",
        "minecraft:gravel",
    ]
    source_substrate = [
        "minecraft:dirt",
        "minecraft:grass",
        "minecraft:grass_block",
        "minecraft:clay",
        "minecraft:gravel",
    ]
    write_json(
        features / "fire_swamp_device_anchor_feature.json",
        single_block_feature(
            "fire_swamp_device_anchor_feature",
            "minecraft:grass_block",
            source_substrate,
            may_replace=source_surface,
        ),
    )

    for rule_kind, block_identifier in (
        ("jet", "fire_jet"),
        ("smoker", "smoker"),
    ):
        structure_name = "tf_slice:fire_swamp/%s" % block_identifier
        write_mcstructure(
            structure_root / (block_identifier + ".mcstructure"),
            fire_swamp_device_structure(block_identifier),
        )
        native_id = "fire_swamp_%s_structure_feature" % rule_kind
        offset_id = "fire_swamp_%s_structure_offset_feature" % rule_kind
        write_json(
            features / (native_id + ".json"),
            native_structure_feature(native_id, structure_name),
        )
        write_json(
            features / (offset_id + ".json"),
            offset_feature(offset_id, native_id, -2, -2, -2),
        )
        write_json(
            features / ("fire_swamp_%s_feature.json" % rule_kind),
            sequence_feature(
                "fire_swamp_%s_feature" % rule_kind,
                ["fire_swamp_device_anchor_feature", offset_id],
            ),
        )
        write_json(
            rules / ("fire_swamp_%s_feature_rule.json" % rule_kind),
            feature_rule(
                "fire_swamp_%s_feature_rule" % rule_kind,
                "fire_swamp_%s_feature" % rule_kind,
                "fire_swamp",
                4,
            ),
        )

    stale_names = [
        "fire_swamp_%s_block_feature.json" % kind
        for kind in ("jet", "smoker")
    ]
    stale_names.extend(
        "fire_swamp_device_lava_%s_%s_feature.json" % (x_name, z_name)
        for x_name in ("n1", "z0", "p1")
        for z_name in ("n1", "z0", "p1")
    )
    for stale_name in stale_names:
        stale_path = features / stale_name
        if stale_path.exists():
            stale_path.unlink()


def build_swamp_features(root):
    root = Path(root)
    bp = root / "TwilightBossSliceB"
    rp = root / "TwilightBossSliceR"
    features = bp / "netease_features"
    rules = bp / "netease_feature_rules"
    blocks_dir = bp / "netease_blocks"
    upstream_textures = (
        root.parent
        / "twilightforest-1.20.1-4.3.2508-extracted"
        / "00_original_tree"
        / "assets"
        / "twilightforest"
        / "textures"
        / "block"
    )
    terrain_path = rp / "textures" / "terrain_texture.json"
    terrain = json.loads(terrain_path.read_text("utf-8"))
    blocks_path = rp / "blocks.json"
    client_blocks = json.loads(blocks_path.read_text("utf-8"))

    # The generic Bedrock tree feature cannot express Twilight's branching
    # trunks, ground/exposed roots, hanging vines, or firefly decorators.
    # Sparse structure variants preserve those source-visible traits without
    # clearing surrounding terrain. Swamp trees use a real ground probe and
    # order-independent lone-probe cleanup, so an air-to-air no-op cannot
    # short-circuit placement and a rejected template cannot leave a stump.
    tree_ground = [
        "minecraft:grass",
        "minecraft:grass_block",
        "minecraft:dirt",
        "minecraft:clay",
        "minecraft:podzol",
        "minecraft:mycelium",
    ]
    mangrove_variants = build_tree_variants(
        bp,
        features,
        "mangrove",
        mangrove_tree_structure,
        tree_ground,
    )
    swampy_variants = build_tree_variants(
        bp,
        features,
        "swampy_oak",
        swampy_oak_tree_structure,
        tree_ground,
    )
    canopy_variants = build_tree_variants(
        bp,
        features,
        "canopy",
        canopy_tree_structure,
        tree_ground,
    )
    write_json(
        features / "twilight_mangrove_tree_feature.json",
        weighted_selector_feature(
            "twilight_mangrove_tree_feature", mangrove_variants
        ),
    )
    write_json(
        features / "swampy_oak_tree_feature.json",
        weighted_selector_feature("swampy_oak_tree_feature", swampy_variants),
    )
    write_json(
        features / "canopy_tree_source_shape_feature.json",
        weighted_selector_feature(
            "canopy_tree_source_shape_feature", canopy_variants
        ),
    )
    write_json(
        features / "canopy_tree_selector_feature.json",
        weighted_selector_feature(
            "canopy_tree_selector_feature",
            (
                ("canopy_tree_source_shape_feature", 3),
                ("twilight_oak_tree_feature", 2),
            ),
        ),
    )
    write_json(
        features / "twilight_tree_mix_selector_feature.json",
        weighted_selector_feature(
            "twilight_tree_mix_selector_feature",
            (
                ("forest_vanilla_birch_tree_feature", 4),
                ("forest_vanilla_oak_tree_feature", 3),
                ("twilight_oak_tree_feature", 9),
            ),
        ),
    )

    top_source = upstream_textures / "mangrove_log_top.png"
    top_target = rp / "textures" / "blocks" / "mangrove_log_top.png"
    top_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(top_source), str(top_target))
    terrain["texture_data"]["tf_slice:mangrove_log_top"] = {
        "textures": "textures/blocks/mangrove_log_top"
    }
    client_blocks["tf_slice:mangrove_log"] = {
        "textures": {
            "up": "tf_slice:mangrove_log_top",
            "down": "tf_slice:mangrove_log_top",
            "side": "tf_slice:mangrove_log",
        },
        "sound": "wood",
    }
    for axis in ("x", "z"):
        identifier = "mangrove_log_%s" % axis
        write_json(
            blocks_dir / (identifier + ".json"),
            axis_log_block(
                identifier,
                "tf_slice:mangrove_log",
                "tf_slice:mangrove_log_top",
                axis,
            ),
        )
        client_blocks["tf_slice:%s" % identifier] = {
            "textures": "tf_slice:mangrove_log",
            "sound": "wood",
        }

    write_json(
        features / "twilight_mangrove_tree_water_search_feature.json",
        search_feature(
            "twilight_mangrove_tree_water_search_feature",
            "twilight_mangrove_tree_feature",
            [0, -6, 0],
            [0, 0, 0],
        ),
    )
    write_json(
        rules / "mangrove_tree_feature_rule.json",
        feature_rule(
            "mangrove_tree_feature_rule",
            "mangrove_tree_landmark_surface_project_feature",
            "swamp",
            "3 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
            y="(query.get_height_at(variable.worldx, variable.worldz) + 1) + 64",
        ),
    )
    write_json(
        features / "swampy_oak_tree_search_feature.json",
        search_feature(
            "swampy_oak_tree_search_feature",
            "swampy_oak_tree_feature",
            [0, -2, 0],
            [0, 0, 0],
        ),
    )
    for biome_key in ("swamp", "fire_swamp"):
        rule_id = "%s_swampy_oak_tree_feature_rule" % biome_key
        write_json(
            rules / (rule_id + ".json"),
            feature_rule(
                rule_id,
                "%s_swampy_oak_tree_landmark_surface_project_feature"
                % biome_key,
                biome_key,
                "4 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
                y="(query.get_height_at(variable.worldx, variable.worldz) + 1) + 64",
            ),
        )

    # Source fallen mangroves are one-in-forty and can be normal or hollow.
    # Axis-specific blocks keep the exposed end grain and horizontal silhouette.
    log_features = []
    for axis in ("x", "z"):
        for length in range(3, 7):
            structure = SparseStructure(
                (length, 1, 1) if axis == "x" else (1, 1, length),
                "mangrove_fallen_log_%s%d" % (axis, length),
            )
            for offset in range(length):
                structure.set(
                    offset if axis == "x" else 0,
                    0,
                    offset if axis == "z" else 0,
                    "tf_slice:mangrove_log_%s" % axis,
                )
            structure_name = "tf_slice:swamp/fallen_mangrove/%s%d" % (
                axis,
                length,
            )
            structure_path = (
                bp
                / "structures"
                / "tf_slice"
                / "swamp"
                / "fallen_mangrove"
                / ("%s%d.mcstructure" % (axis, length))
            )
            structure_path.parent.mkdir(parents=True, exist_ok=True)
            write_mcstructure(structure_path, structure)
            feature_id = "mangrove_fallen_log_%s%d_feature" % (axis, length)
            write_json(
                features / (feature_id + ".json"),
                native_structure_feature(feature_id, structure_name),
            )
            log_features.append(feature_id)
    write_json(
        features / "mangrove_fallen_log_selector_feature.json",
        selector_feature("mangrove_fallen_log_selector_feature", log_features),
    )
    write_json(
        rules / "mangrove_fallen_log_feature_rule.json",
        feature_rule(
            "mangrove_fallen_log_feature_rule",
            "mangrove_fallen_log_selector_feature",
            "swamp",
            1,
            chance=2.5,
        ),
    )

    water = ["minecraft:water", "minecraft:flowing_water"]
    write_json(blocks_dir / "huge_lily_pad.json", huge_lily_pad_block())
    terrain["texture_data"]["tf_slice:huge_lily_pad"] = (
        huge_lily_pad_texture_entry(
            huge_lily_pad_texture_stem("huge_lily_pad"),
            HUGE_LILY_PAD_ITEM_TINT,
        )
    )
    client_blocks["tf_slice:huge_lily_pad"] = {
        "textures": "tf_slice:huge_lily_pad",
        "sound": "grass",
    }
    write_json(
        features / "huge_lily_pad_feature.json",
        single_block_feature(
            "huge_lily_pad_feature", "tf_slice:huge_lily_pad", water
        ),
    )
    with Image.open(upstream_textures / "huge_lily_pad.png") as source:
        public_image = huge_lily_pad_public_image(source)
        quadrant_images = huge_lily_pad_quadrant_images(public_image)
    public_texture = (
        rp
        / "textures"
        / "blocks"
        / (huge_lily_pad_texture_stem("huge_lily_pad") + ".png")
    )
    public_texture.parent.mkdir(parents=True, exist_ok=True)
    public_image.save(public_texture, format="PNG")
    for quadrant in ("nw", "ne", "se", "sw"):
        block_id = "huge_lily_pad_%s" % quadrant
        block_name = "tf_slice:%s" % block_id
        write_json(blocks_dir / (block_id + ".json"), lily_quadrant_block(block_id))
        texture_stem = huge_lily_pad_texture_stem(block_id)
        target = rp / "textures" / "blocks" / (texture_stem + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        quadrant_images[quadrant].save(target, format="PNG")
        terrain["texture_data"][block_name] = (
            huge_lily_pad_texture_entry(
                texture_stem,
                HUGE_LILY_PAD_WORLD_TINT,
            )
        )
        client_blocks[block_name] = {"textures": block_name, "sound": "grass"}

    for stale in features.glob("huge_lily_pad_clearance_*feature.json"):
        stale.unlink()
    clearance_documents, clearance_features = (
        huge_lily_pad_clearance_documents(water)
    )
    for file_name, document in clearance_documents.items():
        write_json(features / file_name, document)

    structure_root = (
        bp / "structures" / "tf_slice" / "swamp" / "huge_lily_pad"
    )
    for facing in ("north", "east", "south", "west"):
        structure_name = "tf_slice:swamp/huge_lily_pad/%s" % facing
        write_mcstructure(
            structure_root / (facing + ".mcstructure"),
            huge_lily_pad_structure(facing),
        )
        structure_feature = "huge_lily_pad_%s_structure_feature" % facing
        write_json(
            features / (structure_feature + ".json"),
            huge_lily_pad_structure_feature_document(
                structure_feature,
                structure_name,
            ),
        )
        sequence_id = (
            "huge_lily_pad_2x2_feature"
            if facing == "north"
            else "huge_lily_pad_2x2_%s_feature" % facing
        )
        write_json(
            features / (sequence_id + ".json"),
            (
                huge_lily_pad_single_sequence_document(
                    sequence_id,
                    clearance_features,
                )
                if facing == "north"
                else huge_lily_pad_atomic_sequence_document(
                    sequence_id,
                    clearance_features,
                    structure_feature,
                )
            ),
        )
    candidate = structure_root / "candidate.mcstructure"
    if candidate.is_file():
        candidate.unlink()

    write_json(
        features / "huge_lily_pad_rotation_selector_feature.json",
        weighted_selector_feature(
            "huge_lily_pad_rotation_selector_feature",
            huge_lily_pad_natural_sequences(),
        ),
    )
    write_json(
        features / "huge_lily_pad_water_search_feature.json",
        search_feature(
            "huge_lily_pad_water_search_feature",
            "huge_lily_pad_rotation_selector_feature",
            [0, -2, 0],
            [0, 8, 0],
        ),
    )
    write_json(
        features / "huge_lily_pad_cluster_feature.json",
        patch_feature(
            "huge_lily_pad_cluster_feature",
            "huge_lily_pad_water_search_feature",
            1,
            project_input_to_floor=True,
        ),
    )
    write_json(
        rules / "huge_lily_pad_feature_rule.json",
        feature_rule(
            "huge_lily_pad_feature_rule",
            "huge_lily_pad_cluster_feature",
            "swamp",
            "math.random(0, 1) < 0.5 ? 1 : 0",
            y="(query.get_height_at(variable.worldx, variable.worldz) + 1) + 64",
        ),
    )

    write_json(
        blocks_dir / "huge_water_lily.json",
        huge_water_lily_block(),
    )
    write_json(
        rp / "models" / "blocks" / "swamp_plants.geo.json",
        swamp_plant_geometry(),
    )
    client_blocks["tf_slice:huge_water_lily"] = {
        "textures": "tf_slice:huge_water_lily",
        "sound": "grass",
    }
    write_json(terrain_path, terrain)
    write_json(blocks_path, client_blocks)

    write_json(
        features / "huge_water_lily_feature.json",
        single_block_feature(
            "huge_water_lily_feature", "tf_slice:huge_water_lily", water
        ),
    )
    write_json(
        features / "huge_water_lily_water_search_feature.json",
        search_feature(
            "huge_water_lily_water_search_feature",
            "huge_water_lily_feature",
            [0, -2, 0],
            [0, 8, 0],
        ),
    )
    write_json(
        features / "huge_water_lily_patch_feature.json",
        patch_feature(
            "huge_water_lily_patch_feature",
            "huge_water_lily_water_search_feature",
            5,
            project_input_to_floor=True,
        ),
    )
    write_json(
        rules / "huge_water_lily_feature_rule.json",
        feature_rule(
            "huge_water_lily_feature_rule",
            "huge_water_lily_patch_feature",
            "swamp",
            "math.random(0, 1) < 0.04 ? 1 : 0",
            y="(query.get_height_at(variable.worldx, variable.worldz) + 1) + 64",
        ),
    )

    bank_ground = [
        "minecraft:grass",
        "minecraft:grass_block",
        "minecraft:dirt",
        "minecraft:sand",
        "minecraft:clay",
    ]
    plant_specs = (
        ("swamp_waterlily", "minecraft:waterlily", water, 10, 1),
        ("swamp_sugar_cane", "minecraft:reeds", bank_ground, 6, 2),
        ("swamp_dead_bush", "minecraft:deadbush", bank_ground, 4, 1),
    )
    for name, block, bottom, patch_count, chunk_attempts in plant_specs:
        base_id = "%s_feature" % name
        patch_id = "%s_patch_feature" % name
        write_json(
            features / (base_id + ".json"),
            single_block_feature(base_id, block, bottom),
        )
        placed_id = base_id
        project_input_to_floor = name == "swamp_waterlily"
        if project_input_to_floor:
            search_id = "%s_water_search_feature" % name
            placed_id = search_id
            write_json(
                features / (search_id + ".json"),
                search_feature(
                    search_id,
                    base_id,
                    [0, -2, 0],
                    [0, 8, 0],
                ),
            )
        write_json(
            features / (patch_id + ".json"),
            patch_feature(
                patch_id,
                placed_id,
                patch_count,
                project_input_to_floor=project_input_to_floor,
            ),
        )
        write_json(
            rules / (base_id + "_rule.json"),
            feature_rule(
                base_id + "_rule",
                patch_id,
                "swamp",
                chunk_attempts,
                y=(
                    "(query.get_height_at(variable.worldx, variable.worldz) + 1) + 64"
                    if name == "swamp_waterlily"
                    else "query.get_height_at(variable.worldx, variable.worldz) + 1"
                ),
            ),
        )

    write_json(features / "swamp_vines_feature.json", vine_feature())
    write_json(
        rules / "swamp_vines_feature_rule.json",
        feature_rule(
            "swamp_vines_feature_rule",
            "swamp_vines_feature",
            "swamp",
            24,
        ),
    )

    build_fire_swamp_devices(bp, features, rules)

    for stale in (
        rules / "fire_swamp_tree_feature_rule.json",
    ):
        if stale.exists():
            stale.unlink()

    write_json(
        bp / "metadata" / "swamp_generation.json",
        {
            "source_version": "4.3.2508",
            "fire_swamp_seed_core": [1, 1],
            "swamp_companion_offsets": [
                [-1, 0],
                [0, -1],
                [0, 1],
                [1, 0],
            ],
            "mangrove_attempts": "90% 3 / 10% 4",
            "swampy_oak_attempts": "90% 4 / 10% 5",
            "mangrove_water_depth": 6,
            "tree_root_placement": {
                "upstream": "terrain_aware_trace_exposed_root",
                "implementation": "omit_static_roots",
            },
            "huge_lily_pad": (
                "1/2 chunks x 1 single-block 30px visual with nine "
                "water-supported clearance predicates, floor search y -2..+8"
            ),
            "huge_water_lily": (
                "1/25 chunks x 5 candidates, floor search y -2..+8"
            ),
            "fallen_mangrove": "1/40 chunks",
            "fire_swamp_devices": {
                "source_candidates_per_feature": 4,
                "surface_profile": "5x3x5 atomic structure",
                "reservoir": "3x3 lava with stone wall and floor",
            },
        },
    )
    guard_native_structure_rules(root)


if __name__ == "__main__":
    build_swamp_features(Path(__file__).resolve().parents[1])
