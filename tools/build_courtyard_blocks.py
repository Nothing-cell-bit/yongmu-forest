#!/usr/bin/env python3
"""Build stateful Bedrock courtyard blocks from Twilight Forest 4.3.2508."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
UPSTREAM = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
    / "textures"
    / "block"
)

FACING_VALUES = ["north", "east", "south", "west"]
ETCHED_FLAVORS = {
    "etched_nagastone": "",
    "mossy_etched_nagastone": "_mossy",
    "cracked_etched_nagastone": "_weathered",
}
PILLAR_FLAVORS = {
    "nagastone_pillar": "",
    "mossy_nagastone_pillar": "_mossy",
    "cracked_nagastone_pillar": "_weathered",
}
STAIR_FLAVORS = {
    "nagastone_stairs_left": ("left", ""),
    "mossy_nagastone_stairs_left": ("left", "_mossy"),
    "cracked_nagastone_stairs_left": ("left", "_weathered"),
    "nagastone_stairs_right": ("right", ""),
    "mossy_nagastone_stairs_right": ("right", "_mossy"),
    "cracked_nagastone_stairs_right": ("right", "_weathered"),
}
NAGASTONE_VARIANTS = [
    "axis_x",
    "axis_y",
    "axis_z",
    "east_down",
    "east_up",
    "north_down",
    "north_up",
    "solid",
    "south_down",
    "south_up",
    "west_down",
    "west_up",
]
STAIR_SHAPES = [
    "straight",
    "inner_left",
    "inner_right",
    "outer_left",
    "outer_right",
]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def material(texture):
    return {
        "texture": texture,
        "render_method": "opaque",
        "ambient_occlusion": True,
        "face_dimming": True,
    }


def full_cube_aabb():
    box = {
        "min": [0.0, 0.0, 0.0],
        "max": [1.0, 1.0, 1.0],
    }
    return {
        "collision": box,
        "clip": box,
    }


def block_components(geometry, materials, aabb=None):
    return {
        "minecraft:destructible_by_mining": {
            "seconds_to_destroy": 1.5,
        },
        "minecraft:destructible_by_explosion": {
            "explosion_resistance": 6.0,
        },
        "minecraft:geometry": geometry,
        "minecraft:material_instances": {
            name: material(texture)
            for name, texture in materials.items()
        },
        "netease:aabb": aabb or full_cube_aabb(),
        "netease:render_layer": {"value": "opaque"},
        "netease:solid": {"value": True},
        "netease:pathable": {"value": False},
    }


def block_document(
    identifier,
    states,
    geometry,
    materials,
    permutations,
    aabb=None,
):
    return {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": {
                "identifier": identifier,
                "register_to_creative_menu": True,
                "states": states,
            },
            "components": block_components(geometry, materials, aabb),
            "permutations": permutations,
        },
    }


def transform_permutations(state_name="tf_slice:facing"):
    rotations = {
        "north": [0, 0, 0],
        "east": [0, -90, 0],
        "south": [0, 180, 0],
        "west": [0, 90, 0],
        "up": [-90, 0, 0],
        "down": [90, 0, 0],
    }
    return [
        {
            "condition": "query.block_state('%s') == '%s'"
            % (state_name, facing),
            "components": {
                "minecraft:transformation": {
                    "rotation": rotation,
                }
            },
        }
        for facing, rotation in rotations.items()
    ]


def etched_document(block_name, suffix):
    materials = {
        "*": "tf_slice:nagastone_bare%s" % suffix,
        "front": "tf_slice:etched_nagastone_down%s" % suffix,
        "back": "tf_slice:etched_nagastone_up%s" % suffix,
        "left": "tf_slice:etched_nagastone_left%s" % suffix,
        "right": "tf_slice:etched_nagastone_right%s" % suffix,
        "end": "tf_slice:nagastone_end",
    }
    permutations = transform_permutations()
    return block_document(
        "tf_slice:%s" % block_name,
        {
            "tf_slice:facing": [
                "down",
                "east",
                "north",
                "south",
                "up",
                "west",
            ]
        },
        "geometry.tf_slice.courtyard_oriented_cube",
        materials,
        permutations,
    )


def pillar_document(block_name, suffix):
    materials = {
        "*": "tf_slice:nagastone_pillar_side%s" % suffix,
        "side": "tf_slice:nagastone_pillar_side%s" % suffix,
        "end": "tf_slice:nagastone_pillar_end%s" % suffix,
    }
    permutations = [
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
        {
            "condition": "query.block_state('tf_slice:reversed')",
            "components": {
                "minecraft:material_instances": {
                    "*": material(
                        "tf_slice:nagastone_pillar_side%s_alt" % suffix
                    ),
                    "side": material(
                        "tf_slice:nagastone_pillar_side%s_alt" % suffix
                    ),
                    "end": material(
                        "tf_slice:nagastone_pillar_end%s" % suffix
                    ),
                }
            },
        },
    ]
    return block_document(
        "tf_slice:%s" % block_name,
        {
            "tf_slice:axis": ["x", "y", "z"],
            "tf_slice:reversed": [False, True],
        },
        "geometry.tf_slice.courtyard_pillar",
        materials,
        permutations,
    )


def head_document():
    return block_document(
        "tf_slice:nagastone_head",
        {"tf_slice:facing": FACING_VALUES},
        "geometry.tf_slice.courtyard_oriented_cube",
        {
            "*": "tf_slice:nagastone_cross_section",
            "front": "tf_slice:nagastone_face_front",
            "back": "tf_slice:nagastone_cross_section",
            "left": "tf_slice:nagastone_face_left",
            "right": "tf_slice:nagastone_face_right",
            "end": "tf_slice:nagastone_top_tip",
        },
        transform_permutations(),
    )


def stair_document(block_name, side, suffix):
    permutations = []
    for half in ("bottom", "top"):
        for shape in STAIR_SHAPES:
            cubes = stair_cubes(shape, half)
            for facing, rotation in {
                "north": [0, 0, 0],
                "east": [0, -90, 0],
                "south": [0, 180, 0],
                "west": [0, 90, 0],
            }.items():
                permutations.append(
                    {
                        "condition": (
                            "query.block_state('tf_slice:half') == '%s' && "
                            "query.block_state('tf_slice:shape') == '%s' && "
                            "query.block_state('tf_slice:facing') == '%s'"
                        )
                        % (half, shape, facing),
                        "components": {
                            "minecraft:geometry": (
                                "geometry.tf_slice.courtyard_stairs_%s_%s"
                                % (shape, half)
                            ),
                            "minecraft:transformation": {
                                "rotation": rotation,
                            },
                            "netease:aabb": stair_aabb(cubes, facing),
                        },
                    }
                )
    return block_document(
        "tf_slice:%s" % block_name,
        {
            "tf_slice:facing": FACING_VALUES,
            "tf_slice:half": ["bottom", "top"],
            "tf_slice:shape": STAIR_SHAPES,
        },
        "geometry.tf_slice.courtyard_stairs_straight_bottom",
        {
            "*": "tf_slice:etched_nagastone_%s%s" % (side, suffix),
            "side": "tf_slice:etched_nagastone_%s%s" % (side, suffix),
            "middle": "tf_slice:nagastone_bare%s" % suffix,
            "end": "tf_slice:nagastone_end",
        },
        permutations,
        stair_aabb(stair_cubes("straight", "bottom"), "north"),
    )


def nagastone_document():
    permutations = []
    rotations = {
        "axis_x": [0, 0, 90],
        "axis_z": [90, 0, 0],
        "east_down": [0, -90, 0],
        "east_up": [0, -90, 0],
        "south_down": [0, 180, 0],
        "south_up": [0, 180, 0],
        "west_down": [0, 90, 0],
        "west_up": [0, 90, 0],
    }
    for variant, rotation in rotations.items():
        permutations.append(
            {
                "condition": (
                    "query.block_state('tf_slice:variant') == '%s'"
                    % variant
                ),
                "components": {
                    "minecraft:transformation": {"rotation": rotation}
                },
            }
        )
    return block_document(
        "tf_slice:nagastone",
        {"tf_slice:variant": NAGASTONE_VARIANTS},
        "geometry.tf_slice.courtyard_segment",
        {
            "*": "tf_slice:nagastone_long_side",
            "side": "tf_slice:nagastone_long_side",
            "top": "tf_slice:nagastone_turn_top",
            "bottom": "tf_slice:nagastone_bottom_long",
        },
        permutations,
    )


def face_uv(material_name, uv_size):
    return {
        "uv": [0, 0],
        "uv_size": list(uv_size),
        "material_instance": material_name,
    }


def cube(origin, size, face_materials):
    face_sizes = {
        "north": [size[0], size[1]],
        "south": [size[0], size[1]],
        "east": [size[2], size[1]],
        "west": [size[2], size[1]],
        "up": [size[0], size[2]],
        "down": [size[0], size[2]],
    }
    return {
        "origin": origin,
        "size": size,
        "uv": {
            face: face_uv(
                face_materials.get(face, "*"),
                face_sizes[face],
            )
            for face in ("north", "south", "east", "west", "up", "down")
        },
    }


def stair_aabb(cubes, facing):
    boxes = []
    for value in cubes:
        origin = value["origin"]
        size = value["size"]
        minimum = [
            (origin[0] + 8.0) / 16.0,
            origin[1] / 16.0,
            (origin[2] + 8.0) / 16.0,
        ]
        maximum = [
            minimum[0] + size[0] / 16.0,
            minimum[1] + size[1] / 16.0,
            minimum[2] + size[2] / 16.0,
        ]
        corners = (
            (minimum[0], minimum[2]),
            (minimum[0], maximum[2]),
            (maximum[0], minimum[2]),
            (maximum[0], maximum[2]),
        )
        rotated = []
        for x_value, z_value in corners:
            if facing == "east":
                rotated.append((1.0 - z_value, x_value))
            elif facing == "south":
                rotated.append((1.0 - x_value, 1.0 - z_value))
            elif facing == "west":
                rotated.append((z_value, 1.0 - x_value))
            else:
                rotated.append((x_value, z_value))
        box = {
            "min": [
                min(value[0] for value in rotated),
                minimum[1],
                min(value[1] for value in rotated),
            ],
            "max": [
                max(value[0] for value in rotated),
                maximum[1],
                max(value[1] for value in rotated),
            ],
        }
        boxes.append(box)
    return {
        "collision": boxes,
        "clip": boxes,
    }


def geometry(identifier, cubes):
    return {
        "description": {
            "identifier": identifier,
            "texture_width": 16,
            "texture_height": 16,
            "visible_bounds_width": 2,
            "visible_bounds_height": 2,
            "visible_bounds_offset": [0, 0.5, 0],
        },
        "bones": [
            {
                "name": "block",
                "pivot": [0, 8, 0],
                "cubes": cubes,
            }
        ],
    }


def stair_cubes(shape, half):
    lower_y = 0 if half == "bottom" else 8
    upper_y = 8 if half == "bottom" else 0
    cubes = [
        cube(
            [-8, lower_y, -8],
            [16, 8, 16],
            {
                "north": "side",
                "south": "side",
                "east": "side",
                "west": "side",
                "up": "end",
                "down": "end",
            },
        )
    ]
    upper_parts = {
        "straight": [([-8, upper_y, -8], [16, 8, 8])],
        "inner_left": [
            ([-8, upper_y, -8], [16, 8, 8]),
            ([-8, upper_y, 0], [8, 8, 8]),
        ],
        "inner_right": [
            ([-8, upper_y, -8], [16, 8, 8]),
            ([0, upper_y, 0], [8, 8, 8]),
        ],
        "outer_left": [([-8, upper_y, -8], [8, 8, 8])],
        "outer_right": [([0, upper_y, -8], [8, 8, 8])],
    }
    for origin, size in upper_parts[shape]:
        cubes.append(
            cube(
                origin,
                size,
                {
                    "north": "side",
                    "south": "middle",
                    "east": "side",
                    "west": "side",
                    "up": "end",
                    "down": "end",
                },
            )
        )
    return cubes


def geometry_document():
    oriented_faces = {
        "north": "front",
        "south": "back",
        "east": "right",
        "west": "left",
        "up": "end",
        "down": "end",
    }
    pillar_faces = {
        "north": "side",
        "south": "side",
        "east": "side",
        "west": "side",
        "up": "end",
        "down": "end",
    }
    segment_faces = {
        "north": "side",
        "south": "side",
        "east": "side",
        "west": "side",
        "up": "top",
        "down": "bottom",
    }
    geometries = [
        geometry(
            "geometry.tf_slice.courtyard_cube",
            [cube([-8, 0, -8], [16, 16, 16], segment_faces)],
        ),
        geometry(
            "geometry.tf_slice.courtyard_oriented_cube",
            [cube([-8, 0, -8], [16, 16, 16], oriented_faces)],
        ),
        geometry(
            "geometry.tf_slice.courtyard_pillar",
            [cube([-8, 0, -8], [16, 16, 16], pillar_faces)],
        ),
        geometry(
            "geometry.tf_slice.courtyard_segment",
            [cube([-8, 0, -8], [16, 16, 16], segment_faces)],
        ),
    ]
    for half in ("bottom", "top"):
        for shape in STAIR_SHAPES:
            geometries.append(
                geometry(
                    "geometry.tf_slice.courtyard_stairs_%s_%s"
                    % (shape, half),
                    stair_cubes(shape, half),
                )
            )
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": geometries,
    }


def register_texture(atlas, key, source_name):
    source = UPSTREAM / ("%s.png" % source_name)
    if not source.is_file():
        raise FileNotFoundError(source)
    target = RP / "textures" / "blocks" / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    atlas[key] = {"textures": "textures/blocks/%s" % source_name}


def build():
    write_json(
        BP / "netease_blocks" / "nagastone.json",
        nagastone_document(),
    )
    for block_name, suffix in ETCHED_FLAVORS.items():
        write_json(
            BP / "netease_blocks" / ("%s.json" % block_name),
            etched_document(block_name, suffix),
        )
    for block_name, suffix in PILLAR_FLAVORS.items():
        write_json(
            BP / "netease_blocks" / ("%s.json" % block_name),
            pillar_document(block_name, suffix),
        )
    write_json(
        BP / "netease_blocks" / "nagastone_head.json",
        head_document(),
    )
    for block_name, (side, suffix) in STAIR_FLAVORS.items():
        write_json(
            BP / "netease_blocks" / ("%s.json" % block_name),
            stair_document(block_name, side, suffix),
        )
    courtyard_geometry = geometry_document()
    write_json(
        RP / "models" / "blocks" / "courtyard.geo.json",
        courtyard_geometry,
    )
    write_json(
        RP / "models" / "blocks" / "courtyard_blocks.geo.json",
        courtyard_geometry,
    )

    terrain_path = RP / "textures" / "terrain_texture.json"
    terrain = load_json(terrain_path)
    atlas = terrain["texture_data"]
    sources = {
        "tf_slice:nagastone_bare": "nagastone_bare",
        "tf_slice:nagastone_bare_mossy": "nagastone_bare_mossy",
        "tf_slice:nagastone_bare_weathered": "nagastone_bare_weathered",
        "tf_slice:nagastone_cross_section": "nagastone_cross_section",
        "tf_slice:nagastone_face_front": "nagastone_face_front",
        "tf_slice:nagastone_face_left": "nagastone_face_left",
        "tf_slice:nagastone_face_right": "nagastone_face_right",
        "tf_slice:nagastone_top_tip": "nagastone_top_tip",
        "tf_slice:nagastone_long_side": "nagastone_long_side",
        "tf_slice:nagastone_turn_top": "nagastone_turn_top",
        "tf_slice:nagastone_bottom_long": "nagastone_bottom_long",
    }
    for suffix in ("", "_mossy", "_weathered"):
        for direction in ("down", "up", "left", "right"):
            sources[
                "tf_slice:etched_nagastone_%s%s" % (direction, suffix)
            ] = "etched_nagastone_%s%s" % (direction, suffix)
        sources[
            "tf_slice:nagastone_pillar_side%s" % suffix
        ] = "nagastone_pillar_side%s" % suffix
        sources[
            "tf_slice:nagastone_pillar_side%s_alt" % suffix
        ] = "nagastone_pillar_side%s_alt" % suffix
        sources[
            "tf_slice:nagastone_pillar_end%s" % suffix
        ] = "nagastone_pillar_end%s" % suffix
    for key, source_name in sources.items():
        register_texture(atlas, key, source_name)
    write_json(terrain_path, terrain)


if __name__ == "__main__":
    build()
