#!/usr/bin/env python3
"""Build real player-visible shapes for the public Twilight block catalog.

The route builders historically registered every catalog entry through one
legacy full-cube document.  This module is the single modern source for wood
families, hollow logs, trophies, and the shared canopy fence.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
from itertools import product
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
UPSTREAM_TEXTURES = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
    / "textures"
)
UPSTREAM_MODELS = UPSTREAM_TEXTURES.parent / "models"
MINECRAFT_JAVA_MODELS = (
    ROOT
    / "tools"
    / "references"
    / "minecraft_java_1_20_1"
    / "assets"
    / "minecraft"
    / "models"
)
NATIVE_CREATIVE_INVENTORY_ICONS = (
    ROOT / "tools" / "references" / "native_inventory_icons_20260831"
)
SELECTED_NATIVE_HOTBAR_ICONS = (
    ROOT
    / "tools"
    / "references"
    / "selected_native_hotbar_icons_20260901"
)
ACCEPTED_ENGINE_INVENTORY_ICONS = (
    ROOT / "tools" / "references" / "accepted_inventory_icons_20260830"
)
MATCHED_DARK_INVENTORY_ICONS = (
    ROOT / "tools" / "references" / "matched_dark_inventory_icons_20260901"
)
MANGROVE_SELECTED_ICON_SUFFIXES = {
    "stairs": "stairs",
    "slab": "slab",
    "button": "button",
    "fence": "fence",
    "fence_gate": "fence_gate",
    "pressure_plate": "pressure_plate",
    "banister": "fence",
}
NATIVE_CREATIVE_ICON_SUFFIXES = {
    "stairs": "stairs",
    "slab": "slab",
    "button": "button",
    "fence": "fence",
    "fence_gate": "fence_gate",
    "pressure_plate": "pressure_plate",
    "door": "door",
    "trapdoor": "trapdoor",
    "sign": "sign",
    "wall_sign": "sign",
    "hanging_sign": "hanging_sign",
    "wall_hanging_sign": "hanging_sign",
    "banister": "fence",
}
OBSOLETE_WOOD_SUFFIXES = (
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
    "chest",
)
UPSTREAM_STATIC_ITEM_MODEL_SUFFIXES = {
    "stairs",
    "slab",
    "pressure_plate",
    "trapdoor",
}
UPSTREAM_ITEM_ICON_MODEL_SUFFIXES = {
    "stairs",
    "slab",
    "button",
    "fence",
    "fence_gate",
    "pressure_plate",
    "trapdoor",
    "banister",
}
FACING_VALUES = ["north", "east", "south", "west"]
FACING_ROTATIONS = {
    "north": [0, 0, 0],
    "east": [0, -90, 0],
    "south": [0, 180, 0],
    "west": [0, 90, 0],
}
TROPHY_FACING_ROTATIONS = {
    "north": [0, 0, 0],
    "east": [0, 90, 0],
    "south": [0, 180, 0],
    "west": [0, -90, 0],
}
WOOD_FAMILIES = {
    "dark": {
        "planks": "tf_slice:dark_planks",
        "log": "tf_slice:dark_log",
        "log_top": "tf_slice:dark_log_top",
        "stripped_log": "tf_slice:stripped_dark_log",
        "stripped_log_top": "tf_slice:stripped_dark_log_top",
        "sapling": "tf_slice:darkwood_sapling",
    },
    "mangrove": {
        "planks": "tf_slice:mangrove_planks",
        "log": "tf_slice:mangrove_log",
        "log_top": "tf_slice:mangrove_log_top",
        "stripped_log": "tf_slice:stripped_mangrove_log",
        "stripped_log_top": "tf_slice:stripped_mangrove_log_top",
        "sapling": "tf_slice:mangrove_sapling",
    },
}

CANOPY_WOOD_SPEC = {
    "planks": "tf_slice:canopy_planks",
    "log": "tf_slice:canopy_log",
    "log_top": "tf_slice:canopy_log_top",
    "stripped_log": "tf_slice:stripped_canopy_log",
    "stripped_log_top": "tf_slice:stripped_canopy_log_top",
    "sapling": "tf_slice:canopy_sapling",
}
CANOPY_NATIVE_TEMPLATE_FAMILY = "cherry"
CANOPY_NATIVE_SUFFIXES = (
    "stairs",
    "slab",
    "button",
    "fence",
    "fence_gate",
    "pressure_plate",
    "door",
    "trapdoor",
)
CANOPY_NETEASE_SUFFIXES = (
    "bookshelf",
    "chest",
)
CANOPY_CUSTOM_SUFFIXES = ("banister",) + CANOPY_NETEASE_SUFFIXES
CANOPY_CONSTRUCTION_SUFFIXES = CANOPY_NATIVE_SUFFIXES + CANOPY_CUSTOM_SUFFIXES

TREE_SAPLINGS = {
    "twilight_oak_sapling": "block/twilight_oak_sapling.png",
    "canopy_sapling": "block/canopy_sapling.png",
    "rainbow_oak_sapling": "block/rainbow_oak_sapling.png",
}
GROWABLE_SAPLINGS = frozenset(
    tuple(TREE_SAPLINGS) + ("darkwood_sapling", "mangrove_sapling")
)

TROPHY_SPECS = {
    "naga": {
        "model_textures": ("model/nagahead.png",),
        "item_texture": "item/naga_trophy.png",
        "composite_item": False,
    },
    "lich": {
        "model_textures": ("model/twilightlich64.png",),
        "item_texture": "item/lich_trophy.png",
        "composite_item": False,
    },
    "hydra": {
        "model_textures": ("model/hydra4.png",),
        "item_texture": "item/hydra_trophy.png",
        "composite_item": False,
    },
    "ur_ghast": {
        "model_textures": ("model/towerboss.png",),
        "item_texture": "item/ur_ghast_trophy.png",
        "composite_item": False,
    },
    "knight_phantom": {
        "model_textures": (
            "model/phantomskeleton.png",
            "armor/phantom_1.png",
        ),
        "item_texture": "item/trophy_minor.png",
        "composite_item": True,
        "icon_foreground_size": 32,
        "icon_canvas_size": 32,
        "icon_outline": False,
    },
    "minoshroom": {
        "model_textures": ("model/minoshroomtaur.png",),
        "item_texture": "item/trophy_minor.png",
        "composite_item": True,
        "icon_foreground_size": 32,
        "icon_canvas_size": 32,
        "icon_outline": False,
    },
    "quest_ram": {
        "model_textures": ("model/questram.png",),
        "item_texture": "item/trophy_quest.png",
        "composite_item": True,
        "icon_foreground_size": 16,
    },
}
PUBLIC_TROPHY_IDS = tuple(
    "tf_slice:%s_trophy" % name
    for name in TROPHY_SPECS
)
PUBLIC_TROPHY_ITEM_IDS = tuple(
    "tf_slice:%s_trophy_item" % name
    for name in TROPHY_SPECS
)
INTERNAL_TROPHY_BLOCK_IDS = tuple(
    "tf_slice:%s%s_trophy" % (name, wall)
    for name in TROPHY_SPECS
    for wall in ("", "_wall")
)
UR_GHAST_TROPHY_VISUAL = "tf_slice:ur_ghast_trophy_visual"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def material(texture, render_method="opaque"):
    return {
        "texture": texture,
        "render_method": render_method,
        "ambient_occlusion": True,
        "face_dimming": True,
    }


def aabb(minimum=(0.0, 0.0, 0.0), maximum=(1.0, 1.0, 1.0)):
    return {
        "collision": {"min": list(minimum), "max": list(maximum)},
        "clip": {"min": list(minimum), "max": list(maximum)},
    }


def base_components(
    geometry,
    texture,
    *,
    render_method="opaque",
    solid=True,
    bounds=None,
    seconds=2.0,
    explosion_resistance=3.0,
):
    return {
        "minecraft:destructible_by_mining": {
            "seconds_to_destroy": float(seconds)
        },
        "minecraft:destructible_by_explosion": {
            "explosion_resistance": float(explosion_resistance)
        },
        "minecraft:geometry": geometry,
        "minecraft:material_instances": {
            "*": material(texture, render_method)
        },
        "netease:aabb": bounds if bounds is not None else aabb(),
        "netease:render_layer": {
            "value": "optionalAlpha"
            if render_method != "opaque"
            else "opaque"
        },
        "netease:solid": {"value": bool(solid)},
        "netease:pathable": {"value": False},
    }


def block_document(identifier, states, components, permutations=None):
    description = {
        "identifier": "tf_slice:" + identifier,
        "register_to_creative_menu": True,
    }
    if states:
        description["states"] = states
    value = {"description": description, "components": components}
    if permutations:
        value["permutations"] = permutations
    return {"format_version": "1.20.60", "minecraft:block": value}


def facing_permutations(state="tf_slice:facing"):
    return [
        {
            "condition": "query.block_state('%s') == '%s'" % (state, facing),
            "components": {
                "minecraft:transformation": {"rotation": rotation}
            },
        }
        for facing, rotation in FACING_ROTATIONS.items()
    ]


def face_uv(material_name="*", uv_size=(16, 16)):
    return {
        "uv": [0, 0],
        "uv_size": [float(uv_size[0]), float(uv_size[1])],
        "material_instance": material_name,
    }


def cube(origin, size, material_name="*", *, rotation=None, pivot=None):
    face_sizes = {
        "north": (size[0], size[1]),
        "south": (size[0], size[1]),
        "east": (size[2], size[1]),
        "west": (size[2], size[1]),
        "up": (size[0], size[2]),
        "down": (size[0], size[2]),
    }
    value = {
        "origin": list(origin),
        "size": list(size),
        "uv": {
            face: face_uv(material_name, face_sizes[face])
            for face in ("north", "south", "east", "west", "up", "down")
        },
    }
    if rotation is not None:
        value["rotation"] = list(rotation)
    if pivot is not None:
        value["pivot"] = list(pivot)
    return value


def _box_uv_faces(uv_offset, size, material_name="*"):
    """Expand Bedrock box UVs before geometric scaling changes their span."""
    u_value, v_value = [float(value) for value in uv_offset]
    x_size, y_size, z_size = [float(value) for value in size]
    layout = {
        "east": ([0.0, z_size], [z_size, y_size]),
        "west": ([z_size + x_size, z_size], [z_size, y_size]),
        "up": ([z_size + x_size, z_size], [-x_size, -z_size]),
        "down": ([z_size + x_size * 2.0, 0.0], [-x_size, z_size]),
        "south": ([z_size * 2.0 + x_size, z_size], [x_size, y_size]),
        "north": ([z_size, z_size], [x_size, y_size]),
    }
    return {
        face: {
            "uv": [
                round(u_value + origin[0], 6),
                round(v_value + origin[1], 6),
            ],
            "uv_size": [round(value, 6) for value in uv_size],
            "material_instance": material_name,
        }
        for face, (origin, uv_size) in layout.items()
    }


def geometry(identifier, cubes, *, height=1.0, bones=None, display_scale=None):
    if bones is None:
        bones = [{"name": "block", "pivot": [0, 0, 0], "cubes": cubes}]
    description = {
        "identifier": identifier,
        "texture_width": 16,
        "texture_height": 16,
        "visible_bounds_width": 2,
        "visible_bounds_height": max(1.0, float(height)),
        "visible_bounds_offset": [0, float(height) / 2.0, 0],
    }
    if display_scale is not None:
        description["display_scale"] = float(display_scale)
    return {
        "description": description,
        "bones": bones,
    }


def sapling_geometry():
    plane = {
        "origin": [-8, 0, -0.05],
        "size": [16, 16, 0.1],
        "pivot": [0, 0, 0],
        "uv": {
            "north": face_uv(),
            "south": face_uv(),
        },
    }
    first = copy.deepcopy(plane)
    first["rotation"] = [0, 45, 0]
    second = copy.deepcopy(plane)
    second["rotation"] = [0, -45, 0]
    return geometry(
        "geometry.tf_slice.wood_sapling",
        [],
        bones=[
            {"name": "cross_a", "pivot": [0, 0, 0], "cubes": [first]},
            {"name": "cross_b", "pivot": [0, 0, 0], "cubes": [second]},
        ],
    )


def sapling_geometry_document():
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [sapling_geometry()],
    }


def stair_geometry(top=False):
    if top:
        parts = [
            cube([-8, 8, -8], [16, 8, 16]),
            cube([-8, 0, -8], [16, 8, 8]),
        ]
        suffix = "top"
    else:
        parts = [
            cube([-8, 0, -8], [16, 8, 16]),
            cube([-8, 8, -8], [16, 8, 8]),
        ]
        suffix = "bottom"
    return geometry("geometry.tf_slice.wood_stairs_" + suffix, parts)


def slab_geometry(top=False):
    suffix = "top" if top else "bottom"
    y = 8 if top else 0
    return geometry(
        "geometry.tf_slice.wood_slab_" + suffix,
        [cube([-8, y, -8], [16, 8, 16])],
    )


def fence_geometry(connections):
    cubes = [cube([-2, 0, -2], [4, 16, 4])]
    if "north" in connections:
        cubes.extend(
            [
                cube([-2, 5, -8], [4, 3, 6]),
                cube([-2, 11, -8], [4, 3, 6]),
            ]
        )
    if "south" in connections:
        cubes.extend(
            [
                cube([-2, 5, 2], [4, 3, 6]),
                cube([-2, 11, 2], [4, 3, 6]),
            ]
        )
    if "east" in connections:
        cubes.extend(
            [
                cube([2, 5, -2], [6, 3, 4]),
                cube([2, 11, -2], [6, 3, 4]),
            ]
        )
    if "west" in connections:
        cubes.extend(
            [
                cube([-8, 5, -2], [6, 3, 4]),
                cube([-8, 11, -2], [6, 3, 4]),
            ]
        )
    name = "_".join(connections) if connections else "none"
    return geometry("geometry.tf_slice.wood_fence_" + name, cubes)


def gate_geometry(opened=False):
    cubes = [
        cube([-8, 0, -2], [3, 16, 4]),
        cube([5, 0, -2], [3, 16, 4]),
    ]
    if opened:
        cubes.extend(
            [
                cube([-5, 4, -2], [3, 3, 8]),
                cube([2, 4, -6], [3, 3, 8]),
                cube([-5, 10, -2], [3, 3, 8]),
                cube([2, 10, -6], [3, 3, 8]),
            ]
        )
        suffix = "open"
    else:
        cubes.extend(
            [
                cube([-5, 4, -2], [10, 3, 4]),
                cube([-5, 10, -2], [10, 3, 4]),
                cube([-1, 3, -2], [2, 11, 4]),
            ]
        )
        suffix = "closed"
    return geometry("geometry.tf_slice.wood_gate_" + suffix, cubes)


def door_geometry(half, opened, hinge):
    if opened:
        x = -8 if hinge == "left" else 5
        cubes = [cube([x, 0, -8], [3, 16, 16])]
    else:
        cubes = [cube([-8, 0, -8], [16, 16, 3])]
    return geometry(
        "geometry.tf_slice.wood_door_%s_%s_%s"
        % (half, "open" if opened else "closed", hinge),
        cubes,
    )


def trapdoor_geometry(half, opened):
    if opened:
        cubes = [cube([-8, 0, -8], [16, 16, 3])]
        suffix = "open"
    else:
        y = 13 if half == "top" else 0
        cubes = [cube([-8, y, -8], [16, 3, 16])]
        suffix = "closed"
    return geometry(
        "geometry.tf_slice.wood_trapdoor_%s_%s" % (half, suffix), cubes
    )


def button_geometry(pressed=False):
    depth = 1 if pressed else 2
    return geometry(
        "geometry.tf_slice.wood_button_" + ("pressed" if pressed else "up"),
        [cube([-3, 6, -8], [6, 4, depth])],
    )


def pressure_plate_geometry(pressed=False):
    height = 1 if pressed else 2
    return geometry(
        "geometry.tf_slice.wood_pressure_plate_"
        + ("pressed" if pressed else "up"),
        [cube([-7, 0, -7], [14, height, 14])],
    )


def sign_geometry(kind):
    board = cube([-7, 8, -1], [14, 7, 2])
    cubes = [board]
    if kind == "standing":
        cubes.append(cube([-1, 0, -1], [2, 8, 2]))
    elif kind == "hanging":
        cubes.extend(
            [
                cube([-6, 15, -1], [2, 1, 2]),
                cube([4, 15, -1], [2, 1, 2]),
            ]
        )
    elif kind == "wall_hanging":
        cubes.extend(
            [
                cube([-7, 15, -1], [2, 1, 4]),
                cube([5, 15, -1], [2, 1, 4]),
            ]
        )
    return geometry("geometry.tf_slice.wood_sign_" + kind, cubes)


def banister_geometry(shape, extended):
    """Return the exact upstream north-facing banister cuboid layout."""
    support_height = {"short": 4, "connected": 16, "tall": 12}[shape]
    cubes = []
    if shape != "connected":
        rail_y = 4 if shape == "short" else 12
        cubes.append(cube([-8, rail_y, -8], [16, 4, 4]))
    for x_value, texture_v in ((-5.5, 4), (2.5, 8)):
        support = cube([x_value, 0, -8], [3, support_height, 3])
        for face in ("north", "south", "east", "west"):
            support["uv"][face] = {
                "uv": [0, texture_v],
                "uv_size": [support_height, 3],
                "uv_rotation": 270,
                "material_instance": "*",
            }
        cubes.append(support)
    if extended:
        texture_u = 8 if shape == "connected" else 0
        for x_value, texture_v in ((-5.5, 4), (2.5, 8)):
            extension = cube([x_value, -8, -8], [3, 8, 3])
            for face in ("north", "south", "east", "west"):
                extension["uv"][face] = {
                    "uv": [texture_u, texture_v],
                    "uv_size": [8, 3],
                    "uv_rotation": 270,
                    "material_instance": "*",
                }
            cubes.append(extension)
    return geometry(
        "geometry.tf_slice.wood_banister_%s_%s"
        % (shape, "extended" if extended else "plain"),
        cubes,
    )


def banister_geometry_document():
    return {
        "format_version": "1.21.0",
        "minecraft:geometry": [
            banister_geometry(shape, extended)
            for shape in ("tall", "connected", "short")
            for extended in (False, True)
        ],
    }


def chest_geometry():
    return geometry(
        "geometry.tf_slice.wood_chest",
        [
            cube([-7, 0, -7], [14, 10, 14]),
            cube([-7, 10, -7], [14, 5, 14]),
            cube([-1, 7, -8], [2, 4, 1]),
        ],
    )


def hollow_geometry(kind):
    if kind == "horizontal":
        cubes = [
            cube([-8, 0, -8], [16, 3, 16]),
            cube([-8, 13, -8], [16, 3, 16]),
            cube([-8, 3, -8], [3, 10, 16]),
            cube([5, 3, -8], [3, 10, 16]),
        ]
    else:
        cubes = [
            cube([-8, 0, -8], [16, 16, 3]),
            cube([-8, 0, 5], [16, 16, 3]),
            cube([-8, 0, -5], [3, 16, 10]),
            cube([5, 0, -5], [3, 16, 10]),
        ]
        if kind == "climbable":
            cubes.append(cube([-5, 0, -4.5], [10, 16, 1]))
    return geometry("geometry.tf_slice.hollow_log_" + kind, cubes)


def full_geometry_document():
    entries = [
        sapling_geometry(),
        stair_geometry(False),
        stair_geometry(True),
        slab_geometry(False),
        slab_geometry(True),
        gate_geometry(False),
        gate_geometry(True),
        button_geometry(False),
        button_geometry(True),
        pressure_plate_geometry(False),
        pressure_plate_geometry(True),
        sign_geometry("standing"),
        sign_geometry("wall"),
        sign_geometry("hanging"),
        sign_geometry("wall_hanging"),
        chest_geometry(),
        hollow_geometry("horizontal"),
        hollow_geometry("vertical"),
        hollow_geometry("climbable"),
    ]
    directions = ("north", "east", "south", "west")
    for mask in product((False, True), repeat=4):
        connections = tuple(
            direction for direction, enabled in zip(directions, mask) if enabled
        )
        entries.append(fence_geometry(connections))
    for half in ("lower", "upper"):
        for opened in (False, True):
            for hinge in ("left", "right"):
                entries.append(door_geometry(half, opened, hinge))
    for half in ("bottom", "top"):
        for opened in (False, True):
            entries.append(trapdoor_geometry(half, opened))
    for shape in ("short", "connected", "tall"):
        for extended in (False, True):
            entries.append(banister_geometry(shape, extended))
    return {"format_version": "1.12.0", "minecraft:geometry": entries}


def axis_document(name, side_texture, end_texture, *, all_bark=False):
    components = base_components(
        "geometry.tf_slice.courtyard_cube", side_texture
    )
    components["minecraft:material_instances"] = {
        "*": material(side_texture),
        "side": material(side_texture),
        "top": material(side_texture if all_bark else end_texture),
        "bottom": material(side_texture if all_bark else end_texture),
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
    ]
    return block_document(
        name,
        {"tf_slice:axis": ["y", "x", "z"]},
        components,
        permutations,
    )


def simple_cube_document(
    name,
    texture,
    *,
    alpha=False,
    seconds=2.0,
    explosion_resistance=3.0,
):
    return block_document(
        name,
        {},
        base_components(
            "geometry.tf_slice.courtyard_cube",
            texture,
            render_method="alpha_test" if alpha else "opaque",
            seconds=seconds,
            explosion_resistance=explosion_resistance,
        ),
    )


def sapling_document(name, texture, *, grows=False):
    components = base_components(
        "geometry.tf_slice.wood_sapling",
        texture,
        render_method="alpha_test",
        solid=False,
        bounds=aabb((0.125, 0.0, 0.125), (0.875, 0.875, 0.875)),
        seconds=0.2,
    )
    components["netease:may_place_on"] = {
        "block": [
            "minecraft:grass",
            "minecraft:grass_block",
            "minecraft:dirt",
            "minecraft:podzol",
        ]
    }
    if grows:
        components["netease:random_tick"] = {
            "enable": True,
            "tick_to_script": True,
        }
    return block_document(
        name,
        {"tf_slice:growth_stage": [0, 1]},
        components,
    )


def build_tree_saplings(client_blocks, atlas):
    for name, source_name in TREE_SAPLINGS.items():
        identifier = "tf_slice:" + name
        copy_texture(
            UPSTREAM_TEXTURES / source_name,
            RP / "textures" / "blocks" / (name + ".png"),
        )
        atlas[identifier] = {"textures": "textures/blocks/" + name}
        client_blocks[identifier] = {
            "textures": identifier,
            "sound": "grass",
        }
        write_json(
            BP / "netease_blocks" / (name + ".json"),
            sapling_document(name, identifier, grows=True),
        )


def scaled_trophy_geometry(
    source_path,
    source_identifier,
    target_identifier,
    bone_names,
    anchor,
    scale,
    offset,
    bone_renames=None,
):
    document = load_json(source_path)
    source = next(
        entry
        for entry in document["minecraft:geometry"]
        if entry["description"]["identifier"] == source_identifier
    )
    selected = set(bone_names)
    bone_renames = dict(bone_renames or {})

    def transform(values):
        return [
            round((float(values[index]) - anchor[index]) * scale + offset[index], 4)
            for index in range(3)
        ]

    bones = [{"name": "root", "pivot": [0, 0, 0]}]
    for source_bone in source["bones"]:
        if source_bone.get("name") not in selected:
            continue
        target = copy.deepcopy(source_bone)
        target["name"] = bone_renames.get(
            source_bone.get("name"), source_bone.get("name")
        )
        source_parent = source_bone.get("parent")
        target["parent"] = (
            bone_renames.get(source_parent, source_parent)
            if source_bone.get("parent") in selected
            else "root"
        )
        if "pivot" in target:
            target["pivot"] = transform(target["pivot"])
        for source_cube in target.get("cubes", []):
            source_cube["origin"] = transform(source_cube["origin"])
            source_size = [float(value) for value in source_cube["size"]]
            if isinstance(source_cube.get("uv"), list):
                source_cube["uv"] = _box_uv_faces(
                    source_cube["uv"], source_size
                )
            source_cube["size"] = [
                round(float(value) * scale, 4)
                for value in source_size
            ]
            if "pivot" in source_cube:
                source_cube["pivot"] = transform(source_cube["pivot"])
            if "inflate" in source_cube:
                source_cube["inflate"] = round(
                    float(source_cube["inflate"]) * scale, 4
                )
        bones.append(target)
    value = geometry(target_identifier, [], height=1.25, bones=bones)
    value["description"]["texture_width"] = source["description"][
        "texture_width"
    ]
    value["description"]["texture_height"] = source["description"][
        "texture_height"
    ]
    value["description"]["visible_bounds_width"] = 2
    value["description"]["visible_bounds_height"] = 1.5
    value["description"]["visible_bounds_offset"] = [0, 0.5, 0]
    return value


def _source_trophy_geometry(
    identifier,
    texture_width,
    texture_height,
    bones,
    *,
    visible_height=1.5,
):
    for bone in bones:
        for source_cube in bone.get("cubes", []):
            if isinstance(source_cube.get("uv"), list):
                source_cube["uv"] = _box_uv_faces(
                    source_cube["uv"], source_cube["size"]
                )
    value = geometry(identifier, [], height=visible_height, bones=bones)
    value["description"]["texture_width"] = texture_width
    value["description"]["texture_height"] = texture_height
    value["description"]["visible_bounds_width"] = 2
    value["description"]["visible_bounds_height"] = visible_height
    value["description"]["visible_bounds_offset"] = [0, 0.5, 0]
    return value


def _naga_trophy_geometry():
    return _source_trophy_geometry(
        "geometry.tf_slice.naga_trophy",
        64,
        32,
        [
            {"name": "root", "pivot": [0, 0, 0]},
            {
                "name": "head",
                "parent": "root",
                "pivot": [0, 2, 0],
                "cubes": [
                    {
                        "origin": [-4, 0, -4],
                        "size": [8, 8, 8],
                        "uv": _box_uv_faces([0, 0], [16, 16, 16]),
                    }
                ],
            },
            {
                "name": "tongue",
                "parent": "head",
                "pivot": [0, 2, 0],
                "cubes": [
                    {
                        "origin": [-1.5, 1.5, -7],
                        "size": [3, 0.1, 3],
                        "uv": _box_uv_faces([42, 0], [6, 0, 6]),
                    }
                ],
            },
        ],
    )


def _lich_trophy_geometry():
    return _source_trophy_geometry(
        "geometry.tf_slice.lich_trophy",
        64,
        64,
        [
            {"name": "root", "pivot": [0, 0, 0]},
            {
                "name": "head",
                "parent": "root",
                "pivot": [0, 6, 0],
                "cubes": [
                    {"origin": [-4, 2, -4], "size": [8, 8, 8], "uv": [0, 0]}
                ],
            },
            {
                "name": "crown",
                "parent": "head",
                "pivot": [0, 10, 0],
                "cubes": [
                    {
                        "origin": [-4, 6, -4],
                        "size": [8, 8, 8],
                        "uv": [32, 0],
                        "inflate": 0.5,
                    }
                ],
            },
        ],
    )


def _legacy_knight_phantom_trophy_geometry():
    return _source_trophy_geometry(
        "geometry.tf_slice.knight_phantom_trophy",
        128,
        32,
        [
            {"name": "root", "pivot": [0, 0, 0]},
            {
                "name": "head",
                "parent": "root",
                "pivot": [0, 6, 0],
                "cubes": [
                    {"origin": [-4, 2, -4], "size": [8, 8, 8], "uv": [0, 0]}
                ],
            },
            {
                "name": "helmet",
                "parent": "root",
                "pivot": [0, 6, 0],
                "cubes": [
                    {
                        "origin": [-4, 2, -4],
                        "size": [8, 8, 8],
                        "uv": [64, 0],
                        "inflate": 0.25,
                    }
                ],
            },
            {
                "name": "right_horn_1",
                "parent": "helmet",
                "pivot": [-4, 8.5, 0],
                "rotation": [0, 0, 85],
                "cubes": [
                    {
                        "origin": [-9.5, 7, -1.5],
                        "size": [5, 3, 3],
                        "uv": [88, 0],
                        "inflate": 0.25,
                    }
                ],
            },
            {
                "name": "right_horn_2",
                "parent": "right_horn_1",
                "pivot": [-8.5, 8.5, 0],
                "rotation": [0, 0, 0],
                "cubes": [
                    {
                        "origin": [-12, 7.5, -1],
                        "size": [3, 2, 2],
                        "uv": [118, 16],
                        "inflate": 0.25,
                    }
                ],
            },
            {
                "name": "left_horn_1",
                "parent": "helmet",
                "pivot": [4, 8.5, 0],
                "rotation": [0, 0, -85],
                "cubes": [
                    {
                        "origin": [4.5, 7, -1.5],
                        "size": [5, 3, 3],
                        "uv": [88, 0],
                        "mirror": True,
                        "inflate": 0.25,
                    }
                ],
            },
            {
                "name": "left_horn_2",
                "parent": "left_horn_1",
                "pivot": [8.5, 8.5, 0],
                "rotation": [0, 0, 0],
                "cubes": [
                    {
                        "origin": [9, 7.5, -1],
                        "size": [3, 2, 2],
                        "uv": [118, 16],
                        "inflate": 0.25,
                    }
                ],
            },
        ],
    )


def _complete_ur_ghast_trophy_geometry(source):
    """Restore the four-piece upstream trophy tentacles without flattening them."""
    value = copy.deepcopy(source)
    source_bones = {bone["name"]: bone for bone in value["bones"]}
    bones = [source_bones["root"], source_bones["body"]]
    for index in range(9):
        base_name = "tentacle_%d_base" % index
        base_source = source_bones[base_name]
        pivot = [float(part) for part in base_source["pivot"]]
        x_value, y_value, z_value = pivot
        base = {
            "name": base_name,
            "parent": "body",
            "pivot": pivot,
            "cubes": [
                {
                    "origin": [x_value - 0.75, y_value - 2.5, z_value - 0.75],
                    "size": [1.5, 2.5, 1.5],
                    "uv": _box_uv_faces([index % 3, 0], [3, 5, 3]),
                }
            ],
        }
        if "rotation" in base_source:
            base["rotation"] = copy.deepcopy(base_source["rotation"])
        extension_pivot = [x_value, y_value - 2.0, z_value]
        extension_2_pivot = [x_value, y_value - 4.0, z_value]
        tip_pivot = [x_value, y_value - 6.0, z_value]
        extension = {
            "name": "tentacle_%d_extension" % index,
            "parent": base_name,
            "pivot": extension_pivot,
            "cubes": [
                {
                    "origin": [x_value - 0.75, y_value - 4.5, z_value - 0.75],
                    "size": [1.5, 2.0, 1.5],
                    "uv": _box_uv_faces([index % 4, 0], [3, 4, 3]),
                }
            ],
        }
        extension_2 = {
            "name": "tentacle_%d_extension_2" % index,
            "parent": extension["name"],
            "pivot": extension_2_pivot,
            "cubes": [
                {
                    "origin": [x_value - 0.75, y_value - 6.5, z_value - 0.75],
                    "size": [1.5, 2.0, 1.5],
                    "uv": _box_uv_faces([index % 4, 4], [3, 4, 3]),
                }
            ],
        }
        tip = {
            "name": "tentacle_%d_tip" % index,
            "parent": extension_2["name"],
            "pivot": tip_pivot,
            "cubes": [
                {
                    "origin": [x_value - 0.75, y_value - 8.5, z_value - 0.75],
                    "size": [1.5, 2.0, 1.5],
                    "uv": _box_uv_faces([index % 4, 9], [3, 4, 3]),
                }
            ],
        }
        bones.extend((base, extension, extension_2, tip))
    value["bones"] = bones
    return value


def _knight_phantom_trophy_geometry():
    """Reuse the shipped Phantom Helmet bones, translated onto the trophy head."""
    document = load_json(RP / "models" / "entity" / "phantom_armor.geo.json")
    helmet = next(
        entry
        for entry in document["minecraft:geometry"]
        if entry["description"]["identifier"]
        == "geometry.tf_slice.phantom_helmet"
    )
    value = _source_trophy_geometry(
        "geometry.tf_slice.knight_phantom_trophy",
        128,
        32,
        [
            {"name": "root", "pivot": [0, 0, 0]},
            {
                "name": "head",
                "parent": "root",
                "pivot": [0, 6, 0],
                "cubes": [
                    {"origin": [-4, 2, -4], "size": [8, 8, 8], "uv": [0, 0]}
                ],
            },
        ],
    )
    for source_bone in helmet["bones"]:
        bone = copy.deepcopy(source_bone)
        source_name = bone["name"]
        bone["name"] = "helmet" if source_name == "head" else source_name
        if source_name == "head":
            bone["parent"] = "root"
        elif bone.get("parent") == "head":
            bone["parent"] = "helmet"
        bone.pop("binding", None)
        if "pivot" in bone:
            bone["pivot"][1] = float(bone["pivot"][1]) - 22.0
        for cube_value in bone.get("cubes", []):
            cube_value["origin"][1] = float(cube_value["origin"][1]) - 22.0
            if isinstance(cube_value.get("uv"), list):
                cube_value["uv"][0] = float(cube_value["uv"][0]) + 64.0
        value["bones"].append(bone)
    return value


def trophy_geometry_document():
    hydra_models = RP / "models" / "entity" / "hydra_route.geo.json"
    quest_models = RP / "models" / "entity" / "quest_ram.geo.json"
    phantom_models = (
        RP / "models" / "entity" / "phantom_urghast_route.geo.json"
    )
    ur_ghast_source = next(
        entry
        for entry in load_json(phantom_models)["minecraft:geometry"]
        if entry["description"]["identifier"]
        == "geometry.tf_slice.ur_ghast"
    )
    ur_ghast_bones = {
        bone["name"]
        for bone in ur_ghast_source["bones"]
        if bone["name"] not in ("root", "pose_root")
    }
    ur_ghast_renames = {
        "tentacle_%d" % index: "tentacle_%d_base" % index
        for index in range(9)
    }
    entries = [
        _naga_trophy_geometry(),
        _lich_trophy_geometry(),
        scaled_trophy_geometry(
            hydra_models,
            "geometry.tf_slice.minoshroom",
            "geometry.tf_slice.minoshroom_trophy",
            {
                "head",
                "snout",
                "right_horn_1",
                "right_horn_2",
                "left_horn_1",
                "left_horn_2",
            },
            [0, 30, -14],
            1.0,
            [0, 3, -3],
        ),
        scaled_trophy_geometry(
            hydra_models,
            "geometry.tf_slice.hydra_head",
            "geometry.tf_slice.hydra_trophy",
            {"head", "jaw", "frill"},
            [0, 6, -56],
            0.25,
            [0, 2, -8],
        ),
        _complete_ur_ghast_trophy_geometry(
            scaled_trophy_geometry(
                phantom_models,
                "geometry.tf_slice.ur_ghast",
                "geometry.tf_slice.ur_ghast_trophy",
                ur_ghast_bones,
                [0, 16, 0],
                0.5,
                [0, 12, 0],
                bone_renames=ur_ghast_renames,
            )
        ),
        _knight_phantom_trophy_geometry(),
        scaled_trophy_geometry(
            quest_models,
            "geometry.tf_slice.quest_ram",
            "geometry.tf_slice.quest_ram_trophy",
            {"head", "face"},
            [0, 32.5, -20],
            0.7,
            [0, 3, -4],
            bone_renames={"face": "nose"},
        ),
    ]
    return {"format_version": "1.12.0", "minecraft:geometry": entries}


def _ur_ghast_trophy_body_geometry(source):
    value = copy.deepcopy(source)
    value["description"]["identifier"] = "geometry.tf_slice.ur_ghast_trophy_body"
    for bone in value["bones"]:
        bone.pop("cubes", None)
    root = next(bone for bone in value["bones"] if bone["name"] == "root")
    root["cubes"] = [
        {
            "origin": [-0.5, 0.0, -0.5],
            "size": [1.0, 1.0, 1.0],
            "uv": _box_uv_faces([0, 0], [1, 1, 1]),
        }
    ]
    return value


def _rotated_floor_trophy_geometry(name, source, rotation):
    value = copy.deepcopy(source)
    if name == "ur_ghast":
        value = _ur_ghast_trophy_body_geometry(value)
    value["description"]["identifier"] = (
        "geometry.tf_slice.%s_trophy_rotation_%d" % (name, rotation)
    )
    root = next(bone for bone in value["bones"] if bone["name"] == "root")
    root["rotation"] = [0.0, 22.5 * int(rotation), 0.0]
    return value


def trophy_floor_rotation_geometry_document():
    entries = trophy_geometry_document()["minecraft:geometry"]
    ur_ghast = next(
        entry
        for entry in entries
        if entry["description"]["identifier"]
        == "geometry.tf_slice.ur_ghast_trophy"
    )
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            _ur_ghast_trophy_body_geometry(ur_ghast)
        ]
        + [
            _rotated_floor_trophy_geometry(
                entry["description"]["identifier"]
                .replace("geometry.tf_slice.", "")
                .replace("_trophy", ""),
                entry,
                rotation,
            )
            for entry in entries
            for rotation in (0, 4, 8, 12)
        ],
    }


def ur_ghast_trophy_visual_geometry_document():
    source = next(
        entry
        for entry in trophy_geometry_document()["minecraft:geometry"]
        if entry["description"]["identifier"]
        == "geometry.tf_slice.ur_ghast_trophy"
    )
    value = copy.deepcopy(source)
    value["description"]["identifier"] = (
        "geometry.tf_slice.ur_ghast_trophy_visual"
    )
    bones = {bone["name"]: bone for bone in value["bones"]}
    # Match UrGhastModel.makeTentacle: the two roots on each side are
    # mounted at 45 and 60 degrees, rather than behaving like bottom limbs.
    for index, z_rotation in ((5, 45.0), (6, 60.0), (7, -45.0), (8, -60.0)):
        bones["tentacle_%d_base" % index]["rotation"] = [
            0.0,
            0.0,
            z_rotation,
        ]
    return {"format_version": "1.12.0", "minecraft:geometry": [value]}


def trophy_wearable_animation_document():
    idle = copy.deepcopy(ur_ghast_trophy_visual_animation_document()["animations"][
        "animation.tf_slice.ur_ghast_trophy_visual.idle"
    ])
    idle["bones"] = {"trophy_" + name: value for name, value in idle["bones"].items()}
    return {
        "format_version": "1.8.0",
        "animations": {
            "animation.tf_slice.trophy_wearable.hide_first_person": {
                "loop": True,
                "bones": {"trophy_root": {"scale": [0.0, 0.0, 0.0]}},
            },
            "animation.tf_slice.trophy_wearable.ur_ghast_idle": idle,
        },
    }


def ur_ghast_trophy_visual_animation_document():
    bones = {}
    for index in range(9):
        base_name = "tentacle_%d_base" % index
        extension_name = "tentacle_%d_extension" % index
        extension_2_name = "tentacle_%d_extension_2" % index
        tip_name = "tentacle_%d_tip" % index
        phase = index * 77.3493
        bones[base_name] = {
            "rotation": [
                "11.4592 + math.cos(query.life_time * 60.1606 + %0.4f) * 8.5944"
                % phase,
                "math.sin(query.life_time * 27.0000 + %0.4f) * 22.9183"
                % phase,
                # Bedrock adds animation rotations to the geometry rest pose.
                # The side mounts already carry their 45/60-degree roll there.
                0.0,
            ]
        }
        bones[extension_name] = {
            "rotation": [
                "5.7296 + math.cos(query.life_time * 66.8807 + %0.4f) * 11.4592"
                % (index * 85.9863),
                0.0,
                0.0,
            ]
        }
        bones[extension_2_name] = {
            "rotation": [
                "5.7296 + math.cos(query.life_time * 76.3944 + %0.4f) * 14.3239"
                % (index * 98.2676),
                0.0,
                0.0,
            ]
        }
        bones[tip_name] = {
            "rotation": [
                "5.7296 + math.cos(query.life_time * 89.1405 + %0.4f) * 17.1887"
                % (index * 114.6059),
                0.0,
                0.0,
            ]
        }
    return {
        "format_version": "1.8.0",
        "animations": {
            "animation.tf_slice.ur_ghast_trophy_visual.idle": {
                "loop": True,
                "bones": bones,
            }
        },
    }


def trophy_animation_document():
    document = ur_ghast_trophy_visual_animation_document()
    document["animations"].update(trophy_wearable_animation_document()["animations"])
    return document


def ur_ghast_trophy_visual_client_document():
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": UR_GHAST_TROPHY_VISUAL,
                "materials": {"default": "entity_alphatest"},
                "textures": {
                    "default": "textures/entity/tf_slice/trophies/ur_ghast"
                },
                "geometry": {
                    "default": "geometry.tf_slice.ur_ghast_trophy_visual"
                },
                "animations": {
                    "idle": "animation.tf_slice.ur_ghast_trophy_visual.idle"
                },
                "scripts": {"animate": ["idle"]},
                "render_controllers": ["controller.render.default"],
            }
        },
    }


def ur_ghast_trophy_visual_behavior_document():
    return {
        "format_version": "1.20.0",
        "minecraft:entity": {
            "description": {
                "identifier": UR_GHAST_TROPHY_VISUAL,
                "is_spawnable": False,
                "is_summonable": True,
                "is_experimental": False,
            },
            "components": {
                "minecraft:type_family": {
                    "family": ["ur_ghast_trophy_visual"]
                },
                "minecraft:collision_box": {"width": 0.01, "height": 0.01},
                "minecraft:health": {"value": 1, "max": 1},
                "minecraft:physics": {
                    "has_gravity": False,
                    "has_collision": False,
                },
                "minecraft:pushable": {
                    "is_pushable": False,
                    "is_pushable_by_piston": False,
                },
                "minecraft:persistent": {},
                "minecraft:damage_sensor": {
                    "triggers": [{"cause": "all", "deals_damage": False}]
                },
            },
        },
    }


def _wearable_trophy_geometry(name, source):
    if name == "ur_ghast":
        source = ur_ghast_trophy_visual_geometry_document()["minecraft:geometry"][0]
    source = copy.deepcopy(source)
    display = load_json(UPSTREAM_MODELS / "item" / "template_trophy.json")["display"]["head"]
    override = load_json(UPSTREAM_MODELS / "item" / (name + "_trophy.json"))
    display = override.get("display", {}).get("head", display)
    # Java's CustomHeadLayer applies 0.625 before display.head (1.6), so
    # the authored head dimensions stay at their normal size. Its two 180
    # rotations cancel in the converted, north-facing Bedrock geometry.
    scale = [float(value) * 0.625 for value in display["scale"]]
    head_name = "body" if name == "ur_ghast" else "head"
    core = next(bone for bone in source["bones"] if bone["name"] == head_name)["cubes"][0]
    anchor = [core["origin"][axis] + core["size"][axis] / 2 for axis in range(3)]
    # The world Ur-Ghast's body already sits 8 units above an ordinary head.
    # Its head display adds (18 - 6) * 0.625 = 7.5 units of compensation.
    extra_lift = (float(display["translation"][1]) - 6.0) * 0.625
    center = [0.0, 28.0 + extra_lift - (8.0 if name == "ur_ghast" else 0.0), 0.0]

    def transform(point):
        return [round((float(point[axis]) - anchor[axis]) * scale[axis] + center[axis], 6) for axis in range(3)]

    bones = [{"name": "trophy_mount", "pivot": [0, 24, 0], "binding": "'head'"}]
    for source_bone in source.get("bones", []):
        bone = copy.deepcopy(source_bone)
        original_name = source_bone["name"]
        bone["name"] = "trophy_" + original_name
        parent = source_bone.get("parent")
        bone["parent"] = "trophy_" + parent if parent else "trophy_mount"
        bone.pop("binding", None)
        if "pivot" in bone:
            bone["pivot"] = transform(bone["pivot"])
        for cube_value in bone.get("cubes", []):
            cube_value["origin"] = transform(cube_value["origin"])
            cube_value["size"] = [round(value * scale[axis], 6) for axis, value in enumerate(cube_value["size"])]
            if "inflate" in cube_value:
                cube_value["inflate"] *= scale[0]
            if "pivot" in cube_value:
                cube_value["pivot"] = transform(cube_value["pivot"])
        if original_name == head_name:
            # The player's skin remains intact. Enclose it with the trophy
            # shell to prevent coincident faces or exposed forehead pixels.
            shell = bone["cubes"][0]
            needed = [shell.get("inflate", 0.0)]
            for axis, (low, high) in enumerate(((-4, 4), (24, 32), (-4, 4))):
                needed.extend((shell["origin"][axis] - low, high - shell["origin"][axis] - shell["size"][axis]))
            shell["inflate"] = round(max(needed) + 0.125, 6)
        bones.append(bone)
    description = copy.deepcopy(source["description"])
    description["identifier"] = (
        "geometry.tf_slice.%s_trophy_wearable" % name
    )
    description["visible_bounds_width"] = 3
    description["visible_bounds_height"] = 3
    description["visible_bounds_offset"] = [0, 1.5, 0]
    return {"description": description, "bones": bones}


def trophy_wearable_geometry_document():
    entries = trophy_geometry_document()["minecraft:geometry"]
    return {
        "format_version": "1.16.0",
        "minecraft:geometry": [
            _wearable_trophy_geometry(
                entry["description"]["identifier"]
                .replace("geometry.tf_slice.", "")
                .replace("_trophy", ""),
                entry,
            )
            for entry in entries
        ],
    }


def trophy_attachable_document(name):
    identifier = "tf_slice:%s_trophy_item" % name
    # item predicates run in the owning entity context. context.item_slot is
    # only available in geometry bindings on NetEase 3.8 (runtime repro).
    worn = "query.is_item_name_any('slot.armor.head', '%s')" % identifier
    document = {
        "format_version": "1.20.30",
        "minecraft:attachable": {
            "description": {
                "identifier": identifier,
                "item": {
                    identifier: worn
                },
                "materials": {
                    "default": "entity_alphatest",
                    "enchanted": "entity_alphatest_glint",
                },
                "textures": {
                    "default": "textures/entity/tf_slice/trophies/%s" % name,
                    "enchanted": "textures/misc/enchanted_actor_glint",
                },
                "geometry": {
                    "default": "geometry.tf_slice.%s_trophy_wearable" % name
                },
                "scripts": {
                    "parent_setup": "variable.helmet_layer_visible = (%s) ? 0.0 : variable.helmet_layer_visible;" % worn,
                    "animate": [
                        {
                            "hide_first_person": (
                                "context.is_first_person == 1.0"
                            )
                        }
                    ],
                },
                "animations": {
                    "hide_first_person": (
                        "animation.tf_slice.trophy_wearable.hide_first_person"
                    )
                },
                "render_controllers": [{"controller.render.armor": worn}],
            }
        },
    }
    if name == "ur_ghast":
        description = document["minecraft:attachable"]["description"]
        description["animations"]["idle"] = "animation.tf_slice.trophy_wearable.ur_ghast_idle"
        description["scripts"]["animate"].insert(0, "idle")
    return document


def _geometry_bounds(geometry_entry, translation=(0.0, 0.0, 0.0)):
    vertices = _transformed_geometry_vertices(geometry_entry)
    if not vertices:
        raise ValueError("geometry has no cubes")
    converted = [
        [
            (point[0] + 8.0) / 16.0 + float(translation[0]),
            point[1] / 16.0 + float(translation[1]),
            (point[2] + 8.0) / 16.0 + float(translation[2]),
        ]
        for point in vertices
    ]
    minimum = [min(point[index] for point in converted) for index in range(3)]
    maximum = [max(point[index] for point in converted) for index in range(3)]
    return {
        "min": [round(value, 6) for value in minimum],
        "max": [round(value, 6) for value in maximum],
    }


def _rotated_aabb_box(box, facing):
    corners = (
        (box["min"][0], box["min"][2]),
        (box["min"][0], box["max"][2]),
        (box["max"][0], box["min"][2]),
        (box["max"][0], box["max"][2]),
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
    return {
        "min": [
            round(min(value[0] for value in rotated), 6),
            box["min"][1],
            round(min(value[1] for value in rotated), 6),
        ],
        "max": [
            round(max(value[0] for value in rotated), 6),
            box["max"][1],
            round(max(value[1] for value in rotated), 6),
        ],
    }


def _rotated_aabb_degrees(box, degrees, translation=(0.0, 0.0, 0.0)):
    corners = []
    for x_value in (box["min"][0], box["max"][0]):
        for z_value in (box["min"][2], box["max"][2]):
            point = _rotate_geometry_point(
                [x_value, 0.0, z_value], [0.5, 0.0, 0.5], [0, degrees, 0]
            )
            corners.append(point)
    return {
        "min": [
            round(min(point[0] for point in corners) + translation[0], 6),
            round(box["min"][1] + translation[1], 6),
            round(min(point[2] for point in corners) + translation[2], 6),
        ],
        "max": [
            round(max(point[0] for point in corners) + translation[0], 6),
            round(box["max"][1] + translation[1], 6),
            round(max(point[2] for point in corners) + translation[2], 6),
        ],
    }


def _single_box_aabb(box):
    return {"collision": copy.deepcopy(box), "clip": copy.deepcopy(box)}


def _trophy_source_box(variant, wall=False, facing="north"):
    if variant == "ur_ghast":
        return {"min": [0.25, 0.5, 0.25], "max": [0.75, 1.0, 0.75]}
    if not wall:
        return {"min": [0.25, 0.0, 0.25], "max": [0.75, 0.5, 0.75]}
    return {
        "north": {"min": [0.25, 0.25, 0.5], "max": [0.75, 0.75, 1.0]},
        "south": {"min": [0.25, 0.25, 0.0], "max": [0.75, 0.75, 0.5]},
        "east": {"min": [0.0, 0.25, 0.25], "max": [0.5, 0.75, 0.75]},
        "west": {"min": [0.5, 0.25, 0.25], "max": [1.0, 0.75, 0.75]},
    }[facing]


def trophy_document(
    name,
    base_name,
    geometry_name,
    geometry_entry,
    wall=False,
):
    texture = "tf_slice:%s_model" % base_name
    variant = base_name[: -len("_trophy")]
    has_visual_entity = variant == "ur_ghast"
    wall_geometry = (
        _ur_ghast_trophy_body_geometry(geometry_entry)
        if has_visual_entity
        else geometry_entry
    )
    floor_geometries = [
        entry
        for entry in trophy_floor_rotation_geometry_document()[
            "minecraft:geometry"
        ]
        if entry["description"]["identifier"].startswith(
            "geometry.tf_slice.%s_trophy_rotation_" % variant
        )
    ]
    default_geometry = wall_geometry if wall else floor_geometries[0]
    north_box = (
        _trophy_source_box(variant, wall=wall)
        if has_visual_entity
        else _geometry_bounds(default_geometry)
    )
    components = base_components(
        default_geometry["description"]["identifier"],
        texture,
        render_method="alpha_test",
        solid=False,
        bounds=_single_box_aabb(north_box),
        seconds=1.0,
    )
    if has_visual_entity:
        components["netease:block_entity"] = {"tick": True, "movable": False}
        # BlockRemoveServerEvent is opt-in; it drives debris and visual cleanup.
        components["netease:listen_block_remove"] = {"value": True}
        components["minecraft:material_instances"]["*"]["texture"] = (
            "tf_slice:trophy_anchor_transparent"
        )
    components["minecraft:loot"] = (
        "loot_tables/blocks/tf_slice/%s.json" % base_name
    )
    permutations = []
    if wall:
        states = {
            "tf_slice:facing": FACING_VALUES,
            "tf_slice:powered": [False, True],
        }
        for facing in FACING_VALUES:
            rotation = TROPHY_FACING_ROTATIONS[facing]
            transformation = {"rotation": rotation}
            translation = [0.0, 0.0, 0.0]
            if variant != "ur_ghast":
                local_translation = [0.0, 0.24, 0.249]
                translation = _rotate_point(local_translation, rotation)
                transformation["translation"] = [
                    round(value, 6) for value in translation
                ]
            permutations.append(
                {
                    "condition": (
                        "query.block_state('tf_slice:facing') == '%s'" % facing
                    ),
                    "components": {
                        "minecraft:geometry": wall_geometry["description"][
                            "identifier"
                        ],
                        "minecraft:transformation": transformation,
                        "netease:aabb": _single_box_aabb(
                            _rotated_aabb_degrees(
                                north_box, rotation[1], translation
                            )
                        ),
                    },
                }
            )
        by_facing = {
            facing: copy.deepcopy(permutations[index]["components"])
            for index, facing in enumerate(FACING_VALUES)
        }
        for cardinal, facing in (
            ("south", "north"),
            ("west", "east"),
            ("north", "south"),
            ("east", "west"),
        ):
            permutations.append(
                {
                    "condition": (
                        "query.block_state('tf_slice:facing') == 'north' && "
                        "query.block_state('minecraft:cardinal_direction') == '%s'"
                        % cardinal
                    ),
                    "components": by_facing[facing],
                }
            )
    else:
        states = {
            "tf_slice:rotation": [0, 4, 8, 12],
            "tf_slice:powered": [False, True],
        }
        by_rotation = {
            int(
                frame_geometry["description"]["identifier"].rsplit("_", 1)[1]
            ): frame_geometry
            for frame_geometry in floor_geometries
        }
        for rotation in (0, 4, 8, 12):
            frame_geometry = by_rotation[rotation]
            permutations.append(
                {
                    "condition": (
                        "query.block_state('tf_slice:rotation') == %d" % rotation
                    ),
                    "components": {
                        "minecraft:geometry": frame_geometry["description"][
                            "identifier"
                        ],
                        "netease:aabb": _single_box_aabb(
                            north_box
                            if has_visual_entity
                            else _geometry_bounds(frame_geometry)
                        ),
                    },
                }
            )
        for facing, rotation in (
            ("south", 0),
            ("west", 4),
            ("north", 8),
            ("east", 12),
        ):
            frame_geometry = by_rotation[rotation]
            permutations.append(
                {
                    "condition": (
                        "query.block_state('tf_slice:rotation') == 0 && "
                        "query.block_state('minecraft:cardinal_direction') == '%s'"
                        % facing
                    ),
                    "components": {
                        "minecraft:geometry": frame_geometry["description"][
                            "identifier"
                        ],
                        "netease:aabb": _single_box_aabb(
                            north_box
                            if has_visual_entity
                            else _geometry_bounds(frame_geometry)
                        ),
                    },
                }
            )
    document = block_document(name, states, components, permutations)
    document["format_version"] = "1.21.60"
    document["minecraft:block"]["description"]["traits"] = {
        "minecraft:placement_direction": {
            "enabled_states": ["minecraft:cardinal_direction"]
        }
    }
    # Public floor trophies are exposed through the crafting-items catalog;
    # wall variants are internal. Neither block should add a duplicate entry.
    document["minecraft:block"]["description"][
        "register_to_creative_menu"
    ] = False
    return document


def copy_texture(source, target):
    source = Path(source)
    target = Path(target)
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(target))


def ensure_wood_textures(atlas):
    sources = {
        "tf_slice:mangrove_log_top": "block/mangrove_log_top.png",
        "tf_slice:stripped_mangrove_log_top": "block/stripped_mangrove_log_top.png",
        "tf_slice:stripped_mangrove_wood": "block/stripped_mangrove_log.png",
        "tf_slice:dark_log_top": "block/dark_log_top.png",
        "tf_slice:stripped_dark_log_top": "block/stripped_dark_log_top.png",
    }
    for key, source_name in sources.items():
        target_name = key.split(":", 1)[1] + ".png"
        copy_texture(
            UPSTREAM_TEXTURES / source_name,
            RP / "textures" / "blocks" / target_name,
        )
        atlas[key] = {
            "textures": "textures/blocks/" + target_name[:-4]
        }


def ensure_vanilla_adapter_textures(atlas):
    """Retexture vanilla behavior adapters with the locked Twilight woods."""
    copies = {
        "block/wood/trapdoor/darkwood_trapdoor.png": "dark_trapdoor.png",
        "block/wood/door/darkwood_lower.png": "dark_door_lower.png",
        "block/wood/door/darkwood_upper.png": "dark_door_upper.png",
        "block/wood/trapdoor/mangrove_trapdoor.png": "mangrove_trapdoor.png",
        "block/wood/door/mangrove_lower.png": "mangrove_door_lower.png",
        "block/wood/door/mangrove_upper.png": "mangrove_door_upper.png",
        "block/wood/trapdoor/canopy_trapdoor.png": "canopy_trapdoor.png",
        "block/wood/door/canopy_lower.png": "canopy_door_lower.png",
        "block/wood/door/canopy_upper.png": "canopy_door_upper.png",
    }
    for source_name, target_name in copies.items():
        copy_texture(
            UPSTREAM_TEXTURES / source_name,
            RP / "textures" / "blocks" / target_name,
        )
    overrides = {
        "dark_oak_planks": "textures/blocks/dark_planks",
        "wood_big_oak": "textures/blocks/dark_planks",
        "darkoak_sign": "textures/blocks/dark_planks",
        "dark_oak_trapdoor": "textures/blocks/dark_trapdoor",
        "mangrove_planks": "textures/blocks/mangrove_planks",
        "mangrove_sign": "textures/blocks/mangrove_planks",
        "mangrove_trapdoor": "textures/blocks/mangrove_trapdoor",
        "mangrove_door_bottom": "textures/blocks/mangrove_door_lower",
        "mangrove_door_top": "textures/blocks/mangrove_door_upper",
        "cherry_planks": "textures/blocks/canopy_planks",
        "cherry_trapdoor": "textures/blocks/canopy_trapdoor",
        "cherry_door_bottom": "textures/blocks/canopy_door_lower",
        "cherry_door_top": "textures/blocks/canopy_door_upper",
        "tf_slice:dark_door_lower": "textures/blocks/dark_door_lower",
        "tf_slice:dark_door_upper": "textures/blocks/dark_door_upper",
        "tf_slice:mangrove_door_lower": "textures/blocks/mangrove_door_lower",
        "tf_slice:mangrove_door_upper": "textures/blocks/mangrove_door_upper",
    }
    for key, path in overrides.items():
        atlas[key] = {"textures": path}
    atlas["door_lower"] = {
        "textures": [
            "textures/blocks/door_wood_lower",
            "textures/blocks/door_spruce_lower",
            "textures/blocks/door_birch_lower",
            "textures/blocks/door_jungle_lower",
            "textures/blocks/door_acacia_lower",
            "textures/blocks/dark_door_lower",
            "textures/blocks/door_iron_lower",
        ]
    }
    atlas["door_upper"] = {
        "textures": [
            "textures/blocks/door_wood_upper",
            "textures/blocks/door_spruce_upper",
            "textures/blocks/door_birch_upper",
            "textures/blocks/door_jungle_upper",
            "textures/blocks/door_acacia_upper",
            "textures/blocks/dark_door_upper",
            "textures/blocks/door_iron_upper",
        ]
    }


def ensure_vanilla_adapter_item_textures(atlas):
    """Retexture carried vanilla adapters with upstream Twilight icons."""
    copies = {
        "item/dark_door.png": "dark_door.png",
        "item/dark_sign.png": "dark_sign.png",
        "item/dark_hanging_sign.png": "dark_hanging_sign.png",
        "item/mangrove_door.png": "mangrove_door.png",
        "item/mangrove_sign.png": "mangrove_sign.png",
        "item/mangrove_hanging_sign.png": "mangrove_hanging_sign.png",
        "item/canopy_door.png": "canopy_door.png",
    }
    for source_name, target_name in copies.items():
        copy_texture(
            UPSTREAM_TEXTURES / source_name,
            RP / "textures" / "items" / target_name,
        )
    overrides = {
        "dark_oak_door": "textures/items/dark_door",
        "sign_darkoak": "textures/items/dark_sign",
        "sign_darkoak_hanging": "textures/items/dark_hanging_sign",
        "mangrove_door": "textures/items/mangrove_door",
        "mangrove_sign": "textures/items/mangrove_sign",
        "sign_mangrove_hanging": "textures/items/mangrove_hanging_sign",
        "cherry_door": "textures/items/canopy_door",
    }
    for key, path in overrides.items():
        atlas[key] = {"textures": path}


def ensure_vanilla_adapter_client_blocks(client_blocks):
    """Bind vanilla behavior templates to explicit Twilight material aliases."""
    shared_suffixes = (
        "stairs",
        "slab",
        "button",
        "fence",
        "fence_gate",
        "pressure_plate",
        "sign",
        "wall_sign",
        "hanging_sign",
        "wall_hanging_sign",
    )
    for family, texture_prefix in (
        ("dark_oak", "dark"),
        ("mangrove", "mangrove"),
        ("cherry", "canopy"),
    ):
        planks = "tf_slice:%s_planks" % texture_prefix
        active_suffixes = (
            tuple(
                suffix
                for suffix in shared_suffixes
                if suffix in CANOPY_NATIVE_SUFFIXES
            )
            if family == "cherry"
            else shared_suffixes
        )
        for suffix in active_suffixes:
            client_blocks["%s_%s" % (family, suffix)] = {
                "textures": planks,
                "sound": "wood",
            }
        if "slab" in active_suffixes:
            client_blocks["%s_double_slab" % family] = {
                "textures": planks,
                "sound": "wood",
            }
        client_blocks["%s_trapdoor" % family] = {
            "textures": "%s_trapdoor" % family,
            "sound": "wood",
        }
        client_blocks["%s_door" % family] = {
            "textures": {
                "up": "tf_slice:%s_door_lower" % texture_prefix,
                "down": "tf_slice:%s_door_lower" % texture_prefix,
                "side": "tf_slice:%s_door_upper" % texture_prefix,
            },
            "sound": "wood",
        }


def build_base_wood_blocks():
    for family, spec in WOOD_FAMILIES.items():
        if family == "dark":
            log_names = (
                ("dark_log", spec["log"], spec["log_top"], False),
                ("dark_wood", spec["log"], spec["log_top"], True),
                (
                    "stripped_dark_log",
                    spec["stripped_log"],
                    spec["stripped_log_top"],
                    False,
                ),
                (
                    "stripped_dark_wood",
                    spec["stripped_log"],
                    spec["stripped_log_top"],
                    True,
                ),
            )
            simple_names = (
                ("dark_leaves", "tf_slice:dark_leaves", True, 2.0, 10.0),
                (
                    "hardened_dark_leaves",
                    "tf_slice:hardened_dark_leaves",
                    False,
                    2.0,
                    10.0,
                ),
                ("dark_planks", spec["planks"], False, 2.0, 3.0),
            )
            sapling_name = "darkwood_sapling"
        else:
            log_names = (
                ("mangrove_log", spec["log"], spec["log_top"], False),
                ("mangrove_wood", spec["log"], spec["log_top"], True),
                (
                    "stripped_mangrove_log",
                    spec["stripped_log"],
                    spec["stripped_log_top"],
                    False,
                ),
                (
                    "stripped_mangrove_wood",
                    spec["stripped_log"],
                    spec["stripped_log_top"],
                    True,
                ),
            )
            simple_names = (
                (
                    "mangrove_leaves",
                    "tf_slice:mangrove_leaves",
                    True,
                    0.2,
                    1.0,
                ),
                ("mangrove_root", "tf_slice:mangrove_root", False, 2.0, 3.0),
                ("mangrove_planks", spec["planks"], False, 2.0, 3.0),
            )
            sapling_name = "mangrove_sapling"
        for name, side, top, all_bark in log_names:
            write_json(
                BP / "netease_blocks" / (name + ".json"),
                axis_document(name, side, top, all_bark=all_bark),
            )
        for name, texture, alpha, seconds, resistance in simple_names:
            write_json(
                BP / "netease_blocks" / (name + ".json"),
                simple_cube_document(
                    name,
                    texture,
                    alpha=alpha,
                    seconds=seconds,
                    explosion_resistance=resistance,
                ),
            )
        write_json(
            BP / "netease_blocks" / (sapling_name + ".json"),
            sapling_document(
                sapling_name,
                spec["sapling"],
                grows=sapling_name in GROWABLE_SAPLINGS,
            ),
        )


def _netease_model_name(name):
    return "tf_slice:public_%s" % name


def _netease_model_path(name):
    return (
        RP
        / "models"
        / "netease_block"
        / ("tf_slice_public_%s.json" % name)
    )


def _netease_coordinate(values):
    return [
        round(float(values[0]) + 8.0, 4),
        round(float(values[1]), 4),
        round(float(values[2]) + 8.0, 4),
    ]


def _netease_cube(source, texture_indexes):
    value = {
        "origin": _netease_coordinate(source["origin"]),
        "size": [round(float(item), 4) for item in source["size"]],
        "uv": {},
    }
    for face, source_uv in source.get("uv", {}).items():
        material_name = source_uv.get("material_instance", "*")
        face_value = {
            "texture": int(texture_indexes.get(material_name, 0)),
            "uv": list(source_uv.get("uv", [0, 0])),
            "uv_size": list(source_uv.get("uv_size", [16, 16])),
        }
        if source_uv.get("rotation"):
            face_value["rotation"] = int(source_uv["rotation"])
        value["uv"][face] = face_value
    if "pivot" in source:
        value["pivot"] = _netease_coordinate(source["pivot"])
    if "rotation" in source:
        value["rotation"] = list(source["rotation"])
    return value


def _netease_model_document(
    name,
    geometry_entry,
    textures,
    item_texture,
    texture_indexes=None,
):
    texture_indexes = texture_indexes or {"*": 0}
    bones = []
    for source_bone in geometry_entry["bones"]:
        bone = {
            "name": source_bone.get("name", "block"),
            "pivot": _netease_coordinate(
                source_bone.get("pivot", [0, 0, 0])
            ),
            "cubes": [
                _netease_cube(source_cube, texture_indexes)
                for source_cube in source_bone.get("cubes", [])
            ],
        }
        if source_bone.get("parent"):
            bone["parent"] = source_bone["parent"]
        if source_bone.get("rotation"):
            bone["rotation"] = list(source_bone["rotation"])
        if source_bone.get("enable"):
            bone["enable"] = source_bone["enable"]
        bones.append(bone)
    description = {
        "identifier": _netease_model_name(name),
        "textures": list(textures),
        "use_ao": True,
    }
    if item_texture is not None:
        description["item_texture"] = item_texture
    return {
        "format_version": "1.13.0",
        "netease:block_geometry": {
            "description": description,
            "bones": bones,
        },
    }


def _atlas_texture_path(atlas, alias):
    textures = atlas[alias]["textures"]
    if isinstance(textures, list):
        textures = textures[0]
    if isinstance(textures, dict):
        textures = textures["path"]
    return RP / (str(textures) + ".png")


def _item_icon_cubes(geometry_entry):
    cubes = []
    for bone in geometry_entry.get("bones", []):
        if bone.get("enable") and bone.get("name") not in ("north", "east"):
            continue
        cubes.extend((bone, cube) for cube in bone.get("cubes", []))
    return cubes


def _rotate_geometry_point(point, pivot, rotation):
    relative = [
        float(point[index]) - float(pivot[index]) for index in range(3)
    ]
    rotated = _rotate_point(relative, rotation)
    return [rotated[index] + float(pivot[index]) for index in range(3)]


def _transform_geometry_point(point, cube, bone, bones_by_name):
    point = [float(value) for value in point]
    cube_rotation = cube.get("rotation", [0, 0, 0])
    if any(float(value) for value in cube_rotation):
        origin = [float(value) for value in cube["origin"]]
        size = [float(value) for value in cube["size"]]
        pivot = cube.get(
            "pivot",
            [origin[index] + size[index] / 2.0 for index in range(3)],
        )
        point = _rotate_geometry_point(point, pivot, cube_rotation)
    current = bone
    visited = set()
    while current is not None:
        name = str(current.get("name", ""))
        if name in visited:
            raise ValueError("cyclic geometry bone hierarchy at %s" % name)
        visited.add(name)
        rotation = current.get("rotation", [0, 0, 0])
        if any(float(value) for value in rotation):
            point = _rotate_geometry_point(
                point, current.get("pivot", [0, 0, 0]), rotation
            )
        current = bones_by_name.get(current.get("parent"))
    return point


def _transform_geometry_vector(vector, cube, bone, bones_by_name):
    vector = [float(value) for value in vector]
    cube_rotation = cube.get("rotation", [0, 0, 0])
    if any(float(value) for value in cube_rotation):
        vector = _rotate_point(vector, cube_rotation)
    current = bone
    visited = set()
    while current is not None:
        name = str(current.get("name", ""))
        if name in visited:
            raise ValueError("cyclic geometry bone hierarchy at %s" % name)
        visited.add(name)
        rotation = current.get("rotation", [0, 0, 0])
        if any(float(value) for value in rotation):
            vector = _rotate_point(vector, rotation)
        current = bones_by_name.get(current.get("parent"))
    return vector


def _geometry_cube_face_vertices(cube, face):
    inflate = float(cube.get("inflate", 0.0))
    origin = [float(value) - inflate for value in cube["origin"]]
    size = [float(value) + inflate * 2.0 for value in cube["size"]]
    return _java_element_face_vertices(
        {
            "from": origin,
            "to": [origin[index] + size[index] for index in range(3)],
        },
        face,
    )


def _transformed_geometry_vertices(geometry_entry):
    bones_by_name = {
        bone.get("name"): bone for bone in geometry_entry.get("bones", [])
    }
    vertices = []
    for bone, cube in _item_icon_cubes(geometry_entry):
        for x_value in (0, 1):
            for y_value in (0, 1):
                for z_value in (0, 1):
                    inflate = float(cube.get("inflate", 0.0))
                    origin = [
                        float(value) - inflate for value in cube["origin"]
                    ]
                    size = [
                        float(value) + inflate * 2.0
                        for value in cube["size"]
                    ]
                    point = [
                        origin[0] + size[0] * x_value,
                        origin[1] + size[1] * y_value,
                        origin[2] + size[2] * z_value,
                    ]
                    vertices.append(
                        _transform_geometry_point(
                            point, cube, bone, bones_by_name
                        )
                    )
    return vertices


def _solve_linear_system(matrix, vector):
    size = len(vector)
    rows = [
        [float(value) for value in matrix[index]]
        + [float(vector[index])]
        for index in range(size)
    ]
    for column in range(size):
        pivot = max(
            range(column, size),
            key=lambda index: abs(rows[index][column]),
        )
        if abs(rows[pivot][column]) < 1.0e-9:
            raise ValueError("degenerate perspective transform")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [value / divisor for value in rows[column]]
        for row_index in range(size):
            if row_index == column:
                continue
            factor = rows[row_index][column]
            rows[row_index] = [
                rows[row_index][index] - factor * rows[column][index]
                for index in range(size + 1)
            ]
    return [rows[index][-1] for index in range(size)]


def _perspective_coefficients(destination, source):
    matrix = []
    vector = []
    for (x_value, y_value), (u_value, v_value) in zip(
        destination, source
    ):
        matrix.append(
            [
                x_value,
                y_value,
                1.0,
                0.0,
                0.0,
                0.0,
                -u_value * x_value,
                -u_value * y_value,
            ]
        )
        vector.append(u_value)
        matrix.append(
            [
                0.0,
                0.0,
                0.0,
                x_value,
                y_value,
                1.0,
                -v_value * x_value,
                -v_value * y_value,
            ]
        )
        vector.append(v_value)
    return _solve_linear_system(matrix, vector)


def _texture_quad_for_face(source_uv, texture_size, canvas_size):
    texture_width, texture_height = [float(value) for value in texture_size]
    u_value, v_value = [float(value) for value in source_uv.get("uv", [0, 0])]
    u_size, v_size = [
        float(value) for value in source_uv.get("uv_size", texture_size)
    ]
    left = u_value * canvas_size / texture_width
    right = (u_value + u_size) * canvas_size / texture_width
    top = v_value * canvas_size / texture_height
    bottom = (v_value + v_size) * canvas_size / texture_height
    return [(left, top), (right, top), (right, bottom), (left, bottom)]


def _normalize_java_model_id(model_id):
    model_id = str(model_id)
    if ":" not in model_id:
        return "minecraft:" + model_id
    return model_id


def _java_model_path(model_id):
    model_id = _normalize_java_model_id(model_id)
    namespace, relative = model_id.split(":", 1)
    if namespace == "twilightforest":
        return UPSTREAM_MODELS / (relative + ".json")
    if namespace == "minecraft":
        return MINECRAFT_JAVA_MODELS / (relative + ".json")
    raise ValueError("unsupported Java model namespace: %s" % namespace)


def _load_java_model(model_id):
    model_id = _normalize_java_model_id(model_id)
    if model_id == "minecraft:builtin/entity":
        return {}
    path = _java_model_path(model_id)
    if not path.is_file():
        raise FileNotFoundError(path)
    return load_json(path)


def resolve_java_wood_item_model(name):
    """Resolve the locked Java item/block parent chain and texture variables."""
    source_chain = []
    documents = []
    current = "twilightforest:item/%s" % str(name)
    for unused in range(16):
        current = _normalize_java_model_id(current)
        source_chain.append(current)
        document = _load_java_model(current)
        documents.append(document)
        parent = document.get("parent")
        if not parent:
            break
        current = _normalize_java_model_id(parent)
        if current == "minecraft:builtin/entity":
            source_chain.append(current)
            documents.append({})
            break
    else:
        raise ValueError("Java model parent chain is too deep: %s" % name)

    textures = {}
    display = {}
    elements = None
    gui_light = None
    for document in reversed(documents):
        textures.update(document.get("textures", {}))
        display.update(document.get("display", {}))
        if "elements" in document:
            elements = copy.deepcopy(document["elements"])
        if "gui_light" in document:
            gui_light = document["gui_light"]

    def resolve_texture(value):
        value = str(value)
        seen = set()
        while value.startswith("#"):
            key = value[1:]
            if key in seen or key not in textures:
                raise ValueError("unresolved Java texture variable: %s" % value)
            seen.add(key)
            value = str(textures[key])
        if ":" not in value:
            value = "minecraft:" + value
        return value

    resolved_textures = {
        key: resolve_texture(value)
        for key, value in textures.items()
        if not str(value).startswith("#") or str(value)[1:] in textures
    }
    return {
        "source_chain": source_chain,
        "textures": textures,
        "resolved_textures": resolved_textures,
        "display": display,
        "elements": elements or [],
        "gui_light": gui_light or "side",
    }


def java_item_model_geometry(name):
    """Mechanically convert the locked upstream Java model into static cubes.

    This deliberately preserves the upstream element bounds, per-face UV
    rectangles, and UV rotation.  It does not rasterize or redraw an inventory
    icon; NetEase renders this query-free geometry directly in inventory UI.
    """
    model = resolve_java_wood_item_model(name)
    cubes = []
    for element in model["elements"]:
        source_from = [float(value) for value in element["from"]]
        source_to = [float(value) for value in element["to"]]
        source_uv = {}
        for face, face_data in element.get("faces", {}).items():
            if "uv" not in face_data:
                raise ValueError(
                    "%s %s is missing an explicit upstream UV" % (name, face)
                )
            left, top, right, bottom = face_data["uv"]
            face_uv = {
                "uv": [left, top],
                "uv_size": [right - left, bottom - top],
                "material_instance": "*",
            }
            if face_data.get("rotation"):
                face_uv["rotation"] = int(face_data["rotation"])
            source_uv[face] = face_uv
        converted = {
            "origin": [
                source_from[0] - 8.0,
                source_from[1],
                source_from[2] - 8.0,
            ],
            "size": [
                source_to[index] - source_from[index]
                for index in range(3)
            ],
            "uv": source_uv,
        }
        element_rotation = element.get("rotation")
        if element_rotation:
            if element_rotation.get("rescale"):
                raise ValueError(
                    "%s uses unsupported Java element rescale" % name
                )
            axis = str(element_rotation.get("axis", "y"))
            rotation = [0.0, 0.0, 0.0]
            rotation[("x", "y", "z").index(axis)] = float(
                element_rotation.get("angle", 0)
            )
            pivot = [float(value) for value in element_rotation["origin"]]
            converted["rotation"] = rotation
            converted["pivot"] = [
                pivot[0] - 8.0,
                pivot[1],
                pivot[2] - 8.0,
            ]
        cubes.append(converted)
    if not cubes:
        raise ValueError("%s has no extractable upstream Java elements" % name)
    return geometry(
        "geometry.tf_slice.upstream_item_%s" % name,
        cubes,
    )


def _java_texture_path(texture_id):
    texture_id = str(texture_id)
    namespace, relative = texture_id.split(":", 1)
    if namespace == "twilightforest":
        return UPSTREAM_TEXTURES / (relative + ".png")
    raise ValueError("unsupported Java item texture: %s" % texture_id)


def _resolve_java_face_texture(model, texture_ref):
    value = str(texture_ref)
    seen = set()
    while value.startswith("#"):
        key = value[1:]
        if key in seen or key not in model["textures"]:
            raise ValueError("unresolved Java face texture: %s" % value)
        seen.add(key)
        value = str(model["textures"][key])
    if ":" not in value:
        value = "minecraft:" + value
    return value


def _rotate_point(point, rotation):
    x_value, y_value, z_value = [float(value) for value in point]
    for axis, degrees in zip(("x", "y", "z"), rotation):
        radians = math.radians(float(degrees))
        cosine = math.cos(radians)
        sine = math.sin(radians)
        if axis == "x":
            y_value, z_value = (
                y_value * cosine - z_value * sine,
                y_value * sine + z_value * cosine,
            )
        elif axis == "y":
            x_value, z_value = (
                x_value * cosine + z_value * sine,
                -x_value * sine + z_value * cosine,
            )
        else:
            x_value, y_value = (
                x_value * cosine - y_value * sine,
                x_value * sine + y_value * cosine,
            )
    return [x_value, y_value, z_value]


def _rotate_java_gui_point(point, rotation):
    """Apply JOML Quaternionf.rotationXYZ composition to one point.

    The quaternion matrix is Rx * Ry * Rz, so a column vector encounters the
    Z, Y, and X rotations in reverse call order.  Applying X first made every
    GUI model appear to lean sideways.
    """
    x_value, y_value, z_value = [float(value) for value in point]
    angles = dict(zip(("x", "y", "z"), rotation))
    for axis in ("z", "y", "x"):
        radians = math.radians(float(angles[axis]))
        cosine = math.cos(radians)
        sine = math.sin(radians)
        if axis == "x":
            y_value, z_value = (
                y_value * cosine - z_value * sine,
                y_value * sine + z_value * cosine,
            )
        elif axis == "y":
            x_value, z_value = (
                x_value * cosine + z_value * sine,
                -x_value * sine + z_value * cosine,
            )
        else:
            x_value, y_value = (
                x_value * cosine - y_value * sine,
                x_value * sine + y_value * cosine,
            )
    return [x_value, y_value, z_value]


def _rotate_around(point, origin, axis, degrees):
    relative = [
        float(point[index]) - float(origin[index]) for index in range(3)
    ]
    rotation = [0.0, 0.0, 0.0]
    rotation[("x", "y", "z").index(str(axis))] = float(degrees)
    rotated = _rotate_point(relative, rotation)
    return [
        rotated[index] + float(origin[index]) for index in range(3)
    ]


def _java_element_face_vertices(element, face):
    x_min, y_min, z_min = [float(value) for value in element["from"]]
    x_max, y_max, z_max = [float(value) for value in element["to"]]
    return {
        "up": [
            [x_min, y_max, z_min], [x_max, y_max, z_min],
            [x_max, y_max, z_max], [x_min, y_max, z_max],
        ],
        "down": [
            [x_min, y_min, z_max], [x_max, y_min, z_max],
            [x_max, y_min, z_min], [x_min, y_min, z_min],
        ],
        "north": [
            [x_max, y_max, z_min], [x_min, y_max, z_min],
            [x_min, y_min, z_min], [x_max, y_min, z_min],
        ],
        "south": [
            [x_min, y_max, z_max], [x_max, y_max, z_max],
            [x_max, y_min, z_max], [x_min, y_min, z_max],
        ],
        "west": [
            [x_min, y_max, z_min], [x_min, y_max, z_max],
            [x_min, y_min, z_max], [x_min, y_min, z_min],
        ],
        "east": [
            [x_max, y_max, z_max], [x_max, y_max, z_min],
            [x_max, y_min, z_min], [x_max, y_min, z_max],
        ],
    }[face]


def _java_face_texture_quad(face_data, texture_size, canvas_size):
    uv = face_data.get("uv", [0, 0, 16, 16])
    left, top, right, bottom = [float(value) for value in uv]
    width, height = [float(value) for value in texture_size]
    quad = [
        (left * canvas_size / width, top * canvas_size / height),
        (right * canvas_size / width, top * canvas_size / height),
        (right * canvas_size / width, bottom * canvas_size / height),
        (left * canvas_size / width, bottom * canvas_size / height),
    ]
    turns = int(face_data.get("rotation", 0)) // 90
    if turns:
        turns %= 4
        quad = quad[-turns:] + quad[:-turns]
    return quad


def _java_gui_face_is_visible(vertices):
    first = [
        vertices[1][index] - vertices[0][index] for index in range(3)
    ]
    second = [
        vertices[2][index] - vertices[0][index] for index in range(3)
    ]
    # Java block-model face vertices use clockwise winding when viewed from
    # outside.  After the screen-space Y flip, front-facing quads therefore
    # have a negative signed area.
    signed_area = first[0] * second[1] - first[1] * second[0]
    return signed_area < -1.0e-9


def _render_java_item_model_icon(name, target):
    """Bake one upstream Java item model into a deterministic GUI icon.

    Java renders every item in the same 16-unit GUI coordinate system.  Keep
    that shared canvas: fitting every model independently makes buttons and
    pressure plates as large as full blocks.  The rasterizer also keeps the
    upstream GUI transform, per-face UVs, side lighting, and pixel depth.
    """
    model = resolve_java_wood_item_model(name)
    if not model["elements"]:
        return False
    gui = model["display"].get("gui", {})
    rotation = gui.get("rotation", [30, 225, 0])
    scale = gui.get("scale", [0.625, 0.625, 0.625])
    translation = gui.get("translation", [0, 0, 0])
    raw_faces = []
    for element in model["elements"]:
        element_rotation = element.get("rotation") or {}
        for face_name, face_data in element.get("faces", {}).items():
            vertices = _java_element_face_vertices(element, face_name)
            if element_rotation:
                vertices = [
                    _rotate_around(
                        point,
                        element_rotation.get("origin", [8, 8, 8]),
                        element_rotation.get("axis", "y"),
                        element_rotation.get("angle", 0),
                    )
                    for point in vertices
                ]
            transformed = []
            for point in vertices:
                centered = [
                    (float(point[index]) - 8.0) * float(scale[index])
                    for index in range(3)
                ]
                rotated = _rotate_java_gui_point(centered, rotation)
                transformed.append(
                    [
                        rotated[index] + float(translation[index])
                        for index in range(3)
                    ]
                )
            if not _java_gui_face_is_visible(transformed):
                continue
            texture_id = _resolve_java_face_texture(
                model, face_data.get("texture", "#particle")
            )
            raw_faces.append(
                {
                    "vertices": transformed,
                    "texture": texture_id,
                    "face": face_data,
                    "shade": _java_gui_face_shade(
                        face_name, model["gui_light"]
                    ),
                }
            )
    if not raw_faces:
        return False

    canvas_size = 256
    pixels_per_model_unit = canvas_size / 16.0
    x_offset = canvas_size / 2.0
    y_offset = canvas_size / 2.0
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    output_pixels = image.load()
    depth_buffer = [float("-inf")] * (canvas_size * canvas_size)
    texture_cache = {}
    for face in raw_faces:
        path = _java_texture_path(face["texture"])
        if path not in texture_cache:
            source = Image.open(str(path)).convert("RGBA")
            texture_cache[path] = (
                source.size,
                source.resize(
                    (canvas_size, canvas_size), Image.Resampling.NEAREST
                ),
            )
        source_size, source_texture = texture_cache[path]
        screen_vertices = [
            (
                point[0] * pixels_per_model_unit + x_offset,
                -point[1] * pixels_per_model_unit + y_offset,
                point[2],
            )
            for point in face["vertices"]
        ]
        polygon = [
            (int(round(point[0])), int(round(point[1])))
            for point in screen_vertices
        ]
        mask = Image.new("L", (canvas_size, canvas_size), 0)
        ImageDraw.Draw(mask).polygon(polygon, fill=255)
        texture_quad = _java_face_texture_quad(
            face["face"], source_size, canvas_size
        )
        coefficients = _perspective_coefficients(polygon, texture_quad)
        warped = source_texture.transform(
            (canvas_size, canvas_size),
            Image.Transform.PERSPECTIVE,
            coefficients,
            resample=Image.Resampling.NEAREST,
        )
        # Create validity mask: transform a white image the same way to find
        # which pixels have valid source data. Pixels that become non-white
        # are outside the source bounds and filled with black by the transform.
        white = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
        validity = white.transform(
            (canvas_size, canvas_size),
            Image.Transform.PERSPECTIVE,
            coefficients,
            resample=Image.Resampling.NEAREST,
        )
        validity_mask = Image.new("L", (canvas_size, canvas_size), 0)
        vp = validity.load()
        vm = validity_mask.load()
        for y in range(canvas_size):
            for x in range(canvas_size):
                if vp[x, y][0] > 200 and vp[x, y][1] > 200 and vp[x, y][2] > 200:
                    vm[x, y] = 255
        # Combine: only include pixels that are both in the polygon AND valid
        combined = Image.new("L", (canvas_size, canvas_size), 0)
        mp = mask.load()
        cp = combined.load()
        for y in range(canvas_size):
            for x in range(canvas_size):
                if mp[x, y] > 0 and vm[x, y] > 0:
                    cp[x, y] = 255
        depth_plane = _screen_depth_plane(screen_vertices)
        if depth_plane is None:
            continue
        red_factor = face["shade"]
        warped_pixels = warped.load()
        combined_pixels = combined.load()
        left = max(0, min(point[0] for point in polygon))
        right = min(canvas_size - 1, max(point[0] for point in polygon))
        top = max(0, min(point[1] for point in polygon))
        bottom = min(canvas_size - 1, max(point[1] for point in polygon))
        depth_x, depth_y, depth_constant = depth_plane
        for y_value in range(top, bottom + 1):
            for x_value in range(left, right + 1):
                if not combined_pixels[x_value, y_value]:
                    continue
                pixel = warped_pixels[x_value, y_value]
                if not pixel[3]:
                    continue
                depth = (
                    depth_x * (x_value + 0.5)
                    + depth_y * (y_value + 0.5)
                    + depth_constant
                )
                offset = y_value * canvas_size + x_value
                if depth <= depth_buffer[offset] + 1.0e-7:
                    continue
                depth_buffer[offset] = depth
                output_pixels[x_value, y_value] = (
                    int(round(pixel[0] * red_factor)),
                    int(round(pixel[1] * red_factor)),
                    int(round(pixel[2] * red_factor)),
                    pixel[3],
                )
    image = image.resize((64, 64), Image.Resampling.NEAREST)
    
    # 清理黑色边缘：将接近黑色的半透明像素设为完全透明
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            # 如果像素接近黑色且不是完全不透明，则透明化
            if a < 255 and r < 30 and g < 30 and b < 30:
                pixels[x, y] = (0, 0, 0, 0)
    
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(target), format="PNG", optimize=False)
    return True


def _screen_depth_plane(vertices):
    """Return z = ax + by + c for a projected planar face."""
    first, second, third = vertices[:3]
    denominator = (
        (second[1] - third[1]) * (first[0] - third[0])
        + (third[0] - second[0]) * (first[1] - third[1])
    )
    if abs(denominator) < 1.0e-9:
        return None
    x_factor = (
        (second[1] - third[1]) * (first[2] - third[2])
        + (third[2] - second[2]) * (first[1] - third[1])
    ) / denominator
    y_factor = (
        (third[0] - second[0]) * (first[2] - third[2])
        + (first[0] - third[0]) * (second[2] - third[2])
    ) / denominator
    constant = first[2] - x_factor * first[0] - y_factor * first[1]
    return x_factor, y_factor, constant


def _java_gui_face_shade(face_name, gui_light):
    if str(gui_light) == "front":
        return 1.0
    return {
        "down": 0.5,
        "up": 1.0,
        "north": 0.8,
        "south": 0.8,
        "west": 0.6,
        "east": 0.6,
    }.get(str(face_name), 1.0)


def _render_geometry_item_icon(
    geometry_entry,
    texture_path,
    target,
    output_size=64,
    projection_mode="isometric",
):
    cubes = _item_icon_cubes(geometry_entry)
    canvas_size = 256
    texture_image = Image.open(str(texture_path)).convert("RGBA")
    texture_size = texture_image.size
    bones_by_name = {
        bone.get("name"): bone for bone in geometry_entry.get("bones", [])
    }

    def project(point):
        x_value, y_value, z_value = point
        if projection_mode == "front":
            return (x_value, -y_value)
        return (
            (x_value + z_value) * 0.9,
            (x_value - z_value) * 0.45 - y_value * 0.9,
        )

    face_normals = {
        "up": [0, 1, 0],
        "down": [0, -1, 0],
        "east": [1, 0, 0],
        "west": [-1, 0, 0],
        "south": [0, 0, 1],
        "north": [0, 0, -1],
    }
    faces = []
    for bone, value in cubes:
        source_uv = value.get("uv", {})
        if not isinstance(source_uv, dict):
            source_uv = _box_uv_faces(source_uv, value["size"])
        for face in ("up", "down", "east", "west", "south", "north"):
            if face not in source_uv:
                continue
            uv_size = source_uv[face].get("uv_size", texture_size)
            if any(abs(float(value)) <= 1.0e-9 for value in uv_size):
                continue
            normal = _transform_geometry_vector(
                face_normals[face], value, bone, bones_by_name
            )
            visibility = (
                -normal[2]
                if projection_mode == "front"
                else normal[0] + normal[1] - normal[2]
            )
            if visibility <= 1.0e-9:
                continue
            vertices = [
                _transform_geometry_point(point, value, bone, bones_by_name)
                for point in _geometry_cube_face_vertices(value, face)
            ]
            projected = [project(point) for point in vertices]
            signed_area = sum(
                projected[index][0] * projected[(index + 1) % 4][1]
                - projected[(index + 1) % 4][0] * projected[index][1]
                for index in range(4)
            )
            if abs(signed_area) <= 1.0e-9:
                continue
            depth = (
                -sum(point[2] for point in vertices) / len(vertices)
                if projection_mode == "front"
                else sum(
                    point[0] + point[1] - point[2]
                    for point in vertices
                )
                / len(vertices)
            )
            faces.append(
                (
                    depth,
                    projected,
                    1.0,
                    _texture_quad_for_face(
                        source_uv[face], texture_size, canvas_size
                    ),
                )
            )
    if not faces:
        raise ValueError("geometry has no visible item-icon faces")
    points = [
        point
        for unused, polygon, unused_brightness, unused_texture in faces
        for point in polygon
    ]
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    width = max(x_values) - min(x_values)
    height = max(y_values) - min(y_values)
    scale = min(220.0 / max(width, 1.0), 220.0 / max(height, 1.0))
    # Apply per-item display scale (like vanilla's gui display.scale).
    # Vanilla uses different scales per item (button=0.625, fence_gate=0.8,
    # fence=0.625). Applied after auto-scale so items actually render smaller.
    display_scale = geometry_entry.get("description", {}).get(
        "display_scale", 1.0
    )
    scale *= display_scale
    x_offset = 128.0 - (min(x_values) + max(x_values)) * scale / 2.0
    y_offset = 128.0 - (min(y_values) + max(y_values)) * scale / 2.0

    image = Image.new(
        "RGBA", (canvas_size, canvas_size), (0, 0, 0, 0)
    )
    source_texture = texture_image.resize(
        (canvas_size, canvas_size), Image.Resampling.NEAREST
    )
    for unused_depth, polygon, unused_brightness, texture_quad in sorted(
        faces, key=lambda item: item[0]
    ):
        transformed = [
            (
                int(round(point[0] * scale + x_offset)),
                int(round(point[1] * scale + y_offset)),
            )
            for point in polygon
        ]
        transformed_area = sum(
            transformed[index][0] * transformed[(index + 1) % 4][1]
            - transformed[(index + 1) % 4][0] * transformed[index][1]
            for index in range(4)
        )
        if abs(transformed_area) <= 1.0e-9:
            continue
        mask = Image.new("L", (canvas_size, canvas_size), 0)
        ImageDraw.Draw(mask).polygon(transformed, fill=255)
        coefficients = _perspective_coefficients(
            transformed, texture_quad
        )
        warped_texture = source_texture.transform(
            (canvas_size, canvas_size),
            Image.Transform.PERSPECTIVE,
            coefficients,
            resample=Image.Resampling.NEAREST,
        )
        # Create validity mask to exclude black-filled pixels from perspective transform
        white = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
        validity = white.transform(
            (canvas_size, canvas_size),
            Image.Transform.PERSPECTIVE,
            coefficients,
            resample=Image.Resampling.NEAREST,
        )
        validity_mask = Image.new("L", (canvas_size, canvas_size), 0)
        vp = validity.load()
        vm = validity_mask.load()
        for y in range(canvas_size):
            for x in range(canvas_size):
                if vp[x, y][0] > 200 and vp[x, y][1] > 200 and vp[x, y][2] > 200:
                    vm[x, y] = 255
        combined = Image.new("L", (canvas_size, canvas_size), 0)
        mp = mask.load()
        cp = combined.load()
        for y in range(canvas_size):
            for x in range(canvas_size):
                if mp[x, y] > 0 and vm[x, y] > 0:
                    cp[x, y] = 255
        combined = ImageChops.multiply(
            combined, warped_texture.getchannel("A")
        )
        image.paste(warped_texture, (0, 0), combined)
    image = image.resize(
        (output_size, output_size), Image.Resampling.NEAREST
    )
    
    # 清理黑色边缘：将接近黑色的半透明像素设为完全透明
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            # 如果像素接近黑色且不是完全不透明，则透明化
            if a < 255 and r < 30 and g < 30 and b < 30:
                pixels[x, y] = (0, 0, 0, 0)
    
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(target), format="PNG", optimize=False)


def twilight_item_icon_source(family, suffix):
    family_sources = {
        "dark": {
            "door": "item/dark_door.png",
            "sign": "item/dark_sign.png",
            "hanging_sign": "item/dark_hanging_sign.png",
        },
        "mangrove": {
            "door": "item/mangrove_door.png",
            "sign": "item/mangrove_sign.png",
            "hanging_sign": "item/mangrove_hanging_sign.png",
        },
        "canopy": {
            "door": "item/canopy_door.png",
            "sign": "item/canopy_sign.png",
            "hanging_sign": "item/canopy_hanging_sign.png",
        },
    }
    kind = {
        "door": "door",
        "sign": "sign",
        "wall_sign": "sign",
        "hanging_sign": "hanging_sign",
        "wall_hanging_sign": "hanging_sign",
    }.get(suffix)
    if kind is None:
        return None
    return UPSTREAM_TEXTURES / family_sources[family][kind]


def native_creative_inventory_icon_source(family, suffix):
    """Legacy screenshot-source hook retained for compatibility.

    Wood icons now come from upstream model baking or original upstream item
    art.  Returning a captured engine frame here would make a rebuild depend
    on UI background pixels, selection state, and a non-reproducible camera.
    """
    return None


def _ensure_item_icon(
    name,
    geometry_entry,
    texture_alias,
    atlas,
    source=None,
    java_model_name=None,
    resource_pack=None,
):
    if resource_pack is None:
        resource_pack = RP
    alias = "tf_slice:%s_item" % name
    relative = "textures/blocks/item_icons/%s" % name
    target = Path(resource_pack) / (relative + ".png")
    if source:
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = UPSTREAM_TEXTURES / source_path
        copy_texture(source_path, target)
    elif java_model_name:
        if not _render_java_item_model_icon(java_model_name, target):
            raise ValueError(
                "%s has no renderable upstream Java item model"
                % java_model_name
            )
    else:
        _render_geometry_item_icon(
            geometry_entry,
            _atlas_texture_path(atlas, texture_alias),
            target,
        )
    atlas[alias] = {"textures": relative}
    return alias


def _remove_generated_item_icon(name, atlas):
    alias = "tf_slice:%s_item" % name
    atlas.pop(alias, None)
    target = RP / "textures" / "blocks" / "item_icons" / (name + ".png")
    if target.exists():
        target.unlink()


def _dynamic_fence_geometry(identifier, banister=False):
    post_height = 16 if not banister else 13
    post = cube([-2, 0, -2], [4, post_height, 4])
    bones = [{"name": "post", "pivot": [0, 0, 0], "cubes": [post]}]
    direction_specs = {
        "north": (2, [
            cube([-2, 5, -8], [4, 3, 6]),
            cube([-2, 11, -8], [4, 3, 6]),
        ]),
        "south": (3, [
            cube([-2, 5, 2], [4, 3, 6]),
            cube([-2, 11, 2], [4, 3, 6]),
        ]),
        "west": (4, [
            cube([-8, 5, -2], [6, 3, 4]),
            cube([-8, 11, -2], [6, 3, 4]),
        ]),
        "east": (5, [
            cube([2, 5, -2], [6, 3, 4]),
            cube([2, 11, -2], [6, 3, 4]),
        ]),
    }
    if banister:
        direction_specs = {
            name: (
                index,
                [part for part in parts if part["origin"][1] <= 5],
            )
            for name, (index, parts) in direction_specs.items()
        }
    for name, (index, parts) in direction_specs.items():
        bones.append(
            {
                "name": name,
                "pivot": [0, 0, 0],
                "enable": "query.is_connect(%d)" % index,
                "cubes": parts,
            }
        )
    return geometry(identifier, [], bones=bones)


def _fence_inventory_icon_geometry(banister=False):
    """Fence geometry for item icon rendering, matching vanilla fence_inventory.json.

    Unlike _dynamic_fence_geometry (which has one post + conditional rails for
    in-game placement), this has two posts with all rails unconditionally visible,
    matching the vanilla Java fence_inventory model's isometric icon appearance.
    """
    post_height = 16 if not banister else 13
    left_post = cube([-2, 0, -6], [4, post_height, 4])
    right_post = cube([-2, 0, 2], [4, post_height, 4])
    bones = [
        {"name": "left_post", "pivot": [0, 0, 0], "cubes": [left_post]},
        {"name": "right_post", "pivot": [0, 0, 0], "cubes": [right_post]},
    ]
    if not banister:
        top_rail = cube([-1, 12, -6], [2, 3, 12])
        lower_rail = cube([-1, 6, -6], [2, 3, 12])
        bones.append(
            {"name": "top_rail", "pivot": [0, 0, 0], "cubes": [top_rail]}
        )
        bones.append(
            {"name": "lower_rail", "pivot": [0, 0, 0], "cubes": [lower_rail]}
        )
    return geometry(
        "geometry.tf_slice.fence_inventory_icon",
        [],
        bones=bones,
        display_scale=0.625,
    )


def _button_inventory_icon_geometry():
    """Button geometry for item icon, matching vanilla button_inventory.json.

    Vanilla: from [5,6,6] to [11,10,10] with gui scale 0.625.
    We use display_scale=0.625 so the renderer shrinks the button to
    ~62.5% of a full block's visual size, matching vanilla's appearance.
    """
    return geometry(
        "geometry.tf_slice.button_inventory_icon",
        [cube([-3, -2, -2], [6, 4, 4])],
        display_scale=0.625,
    )


def _fence_gate_inventory_icon_geometry():
    """Fence gate geometry for item icon, matching vanilla template_fence_gate.json.

    Vanilla closed gate has two outer posts + two gate doors meeting in the
    middle. Each door has an inner vertical post and two horizontal bars.
    The in-game gate_geometry(closed) uses a solid wide bar which looks like
    a wall instead of a gate.

    display_scale=0.8 matches vanilla's gui scale for fence_gate.
    Bars use z_size=4 (wider than vanilla's 2) because our renderer's
    isometric projection needs more depth to show visible side faces.
    """
    bones = [
        {"name": "left_post", "pivot": [0, 0, 0], "cubes": [cube([-8, 0, -2], [2, 16, 4])]},
        {"name": "right_post", "pivot": [0, 0, 0], "cubes": [cube([6, 0, -2], [2, 16, 4])]},
        {"name": "left_inner", "pivot": [0, 0, 0], "cubes": [cube([-2, 1, -2], [2, 14, 4])]},
        {"name": "right_inner", "pivot": [0, 0, 0], "cubes": [cube([0, 1, -2], [2, 14, 4])]},
        {"name": "left_lower", "pivot": [0, 0, 0], "cubes": [cube([-6, 1, -2], [4, 3, 4])]},
        {"name": "left_upper", "pivot": [0, 0, 0], "cubes": [cube([-6, 7, -2], [4, 3, 4])]},
        {"name": "right_lower", "pivot": [0, 0, 0], "cubes": [cube([2, 1, -2], [4, 3, 4])]},
        {"name": "right_upper", "pivot": [0, 0, 0], "cubes": [cube([2, 7, -2], [4, 3, 4])]},
    ]
    return geometry(
        "geometry.tf_slice.fence_gate_inventory_icon",
        [],
        bones=bones,
        display_scale=0.8,
    )


def _geometry_aabb(geometry_entry):
    boxes = []
    for bone in geometry_entry.get("bones", []):
        for source_cube in bone.get("cubes", []):
            origin = source_cube["origin"]
            size = source_cube["size"]
            box = {
                "min": [
                    round((float(origin[0]) + 8.0) / 16.0, 6),
                    round(float(origin[1]) / 16.0, 6),
                    round((float(origin[2]) + 8.0) / 16.0, 6),
                ],
                "max": [
                    round((float(origin[0]) + float(size[0]) + 8.0) / 16.0, 6),
                    round((float(origin[1]) + float(size[1])) / 16.0, 6),
                    round((float(origin[2]) + float(size[2]) + 8.0) / 16.0, 6),
                ],
            }
            if bone.get("enable"):
                box["enable"] = bone["enable"]
            boxes.append(box)
    return {"collision": copy.deepcopy(boxes), "clip": boxes}


def _rotated_geometry_aabb(geometry_entry, facing):
    bounds = _geometry_aabb(geometry_entry)
    return {
        key: [_rotated_aabb_box(box, facing) for box in boxes]
        for key, boxes in bounds.items()
    }


def banister_block_document(family):
    name = "%s_banister" % family
    texture = (
        CANOPY_WOOD_SPEC
        if family == "canopy"
        else WOOD_FAMILIES[family]
    )["planks"]
    default_geometry = banister_geometry("tall", False)
    components = base_components(
        default_geometry["description"]["identifier"],
        texture,
        solid=False,
        bounds=_rotated_geometry_aabb(default_geometry, "north"),
    )
    components["minecraft:liquid_detection"] = {
        "detection_rules": [
            {
                "liquid_type": "water",
                "can_contain_liquid": True,
                "on_liquid_touches": "blocking",
            }
        ]
    }
    components["netease:neighborchanged_sendto_script"] = {"value": True}
    permutations = []
    for shape in ("tall", "connected", "short"):
        for extended in (False, True):
            geometry_entry = banister_geometry(shape, extended)
            geometry_id = geometry_entry["description"]["identifier"]
            for facing in FACING_VALUES:
                condition = (
                    "query.block_state('tf_slice:shape') == '%s' && "
                    "query.block_state('tf_slice:extended') == %s && "
                    "query.block_state('minecraft:cardinal_direction') == '%s'"
                    % (
                        shape,
                        "true" if extended else "false",
                        facing,
                    )
                )
                permutations.append(
                    {
                        "condition": condition,
                        "components": {
                            "minecraft:geometry": geometry_id,
                            "minecraft:transformation": {
                                "rotation": FACING_ROTATIONS[facing]
                            },
                            "netease:aabb": _rotated_geometry_aabb(
                                geometry_entry, facing
                            ),
                        },
                    }
                )
    document = block_document(
        name,
        {
            "tf_slice:shape": ["tall", "connected", "short"],
            "tf_slice:extended": [False, True],
        },
        components,
        permutations,
    )
    document["minecraft:block"]["description"]["traits"] = {
        "minecraft:placement_direction": {
            "enabled_states": ["minecraft:cardinal_direction"]
        }
    }
    document["format_version"] = "1.21.60"
    return document


def _native_shape_document(family, suffix):
    name = "%s_%s" % (family, suffix)
    shape_geometry = _shape_geometry(suffix)
    components = {
        "minecraft:destroy_time": {"value": 2.0},
        "minecraft:explosion_resistance": {"value": 3.0},
        "minecraft:block_light_absorption": {"value": 0},
        "netease:aabb": _geometry_aabb(shape_geometry),
        "netease:render_layer": {"value": "opaque"},
        # NetEase custom models must not use full-cube face culling. Collision
        # is supplied by netease:aabb instead.
        "netease:solid": {"value": False},
        "netease:pathable": {"value": False},
    }
    if suffix in (
        "stairs",
        "button",
        "fence_gate",
        "door",
        "trapdoor",
        "sign",
        "wall_sign",
        "hanging_sign",
        "wall_hanging_sign",
        "banister",
    ):
        components["netease:face_directional"] = {"type": "direction"}
    if suffix in ("fence", "banister"):
        components["netease:connection"] = {
            "blocks": [
                "tf_slice:%s_fence" % family,
                "tf_slice:%s_fence_gate" % family,
                "tf_slice:%s_banister" % family,
            ]
        }
    if suffix == "chest":
        components["netease:block_chest"] = {
            "chest_capacity": 3,
            "can_pair": True,
            "mute": False,
            "can_be_blocked": True,
        }
    return {
        "format_version": "1.10.0",
        "minecraft:block": {
            "description": {
                "identifier": "tf_slice:" + name,
                "register_to_creative_menu": True,
            },
            "components": components,
        },
    }


def _native_hollow_document(family, kind):
    name = "hollow_%s_log_%s" % (family, kind)
    hollow_geometry = _geometry_by_identifier(
        "geometry.tf_slice.hollow_log_" + kind
    )
    components = {
        "minecraft:destroy_time": {"value": 2.0},
        "minecraft:explosion_resistance": {"value": 3.0},
        "minecraft:block_light_absorption": {"value": 0},
        "netease:aabb": _geometry_aabb(hollow_geometry),
        "netease:render_layer": {"value": "optionalAlpha"},
        "netease:solid": {"value": False},
        "netease:pathable": {"value": False},
    }
    if kind in ("horizontal", "climbable"):
        components["netease:face_directional"] = {"type": "direction"}
    return {
        "format_version": "1.10.0",
        "minecraft:block": {
            "description": {
                "identifier": "tf_slice:" + name,
                "register_to_creative_menu": True,
            },
            "components": components,
        },
    }


def _geometry_by_identifier(identifier):
    return next(
        entry
        for entry in full_geometry_document()["minecraft:geometry"]
        if entry["description"]["identifier"] == identifier
    )


def _shape_geometry(suffix):
    if suffix == "bookshelf":
        return _canopy_bookshelf_geometry()
    identifier = {
        "stairs": "geometry.tf_slice.wood_stairs_bottom",
        "slab": "geometry.tf_slice.wood_slab_bottom",
        "button": "geometry.tf_slice.wood_button_up",
        "fence_gate": "geometry.tf_slice.wood_gate_closed",
        "pressure_plate": "geometry.tf_slice.wood_pressure_plate_up",
        "door": "geometry.tf_slice.wood_door_lower_closed_left",
        "trapdoor": "geometry.tf_slice.wood_trapdoor_bottom_closed",
        "sign": "geometry.tf_slice.wood_sign_standing",
        "wall_sign": "geometry.tf_slice.wood_sign_wall",
        "hanging_sign": "geometry.tf_slice.wood_sign_hanging",
        "wall_hanging_sign": "geometry.tf_slice.wood_sign_wall_hanging",
        "chest": "geometry.tf_slice.wood_chest",
    }.get(suffix)
    if identifier is None:
        return _dynamic_fence_geometry(
            "geometry.tf_slice.native_%s" % suffix,
            banister=suffix == "banister",
        )
    return _geometry_by_identifier(identifier)


def _canopy_direction_traits(*, cardinal=False, vertical=False):
    traits = {}
    if cardinal:
        traits["minecraft:placement_direction"] = {
            "enabled_states": ["minecraft:cardinal_direction"]
        }
    if vertical:
        traits["minecraft:placement_position"] = {
            "enabled_states": ["minecraft:vertical_half"]
        }
    return traits


def _canopy_rotated_permutations(state_combinations):
    permutations = []
    for states, geometry_entry in state_combinations:
        geometry_id = geometry_entry["description"]["identifier"]
        for facing in FACING_VALUES:
            conditions = list(states)
            conditions.append(
                "query.block_state('minecraft:cardinal_direction') == '%s'"
                % facing
            )
            permutations.append(
                {
                    "condition": " && ".join(conditions),
                    "components": {
                        "minecraft:geometry": geometry_id,
                        "minecraft:transformation": {
                            "rotation": FACING_ROTATIONS[facing]
                        },
                        "netease:aabb": _rotated_geometry_aabb(
                            geometry_entry, facing
                        ),
                    },
                }
            )
    return permutations


def _microsoft_canopy_shape_document(suffix):
    """Return one functional, independently textured Canopy wood block."""
    if suffix not in CANOPY_CONSTRUCTION_SUFFIXES:
        raise ValueError("unsupported Canopy construction shape: %s" % suffix)
    name = "canopy_" + suffix
    planks = CANOPY_WOOD_SPEC["planks"]

    if suffix == "banister":
        document = banister_block_document("canopy")
        document["minecraft:block"]["description"][
            "register_to_creative_menu"
        ] = False
        return document

    if suffix == "fence":
        shape = _dynamic_fence_geometry(
            "geometry.tf_slice.native_canopy_fence"
        )
        components = base_components(
            shape["description"]["identifier"],
            planks,
            solid=False,
            bounds=_geometry_aabb(shape),
        )
        components["netease:connection"] = {
            "blocks": [
                "tf_slice:canopy_fence",
                "tf_slice:canopy_fence_gate",
                "tf_slice:canopy_banister",
            ]
        }
        document = block_document(name, {}, components)
    elif suffix == "stairs":
        bottom = stair_geometry(False)
        top = stair_geometry(True)
        components = base_components(
            bottom["description"]["identifier"],
            planks,
            solid=False,
            bounds=_rotated_geometry_aabb(bottom, "north"),
        )
        permutations = _canopy_rotated_permutations(
            (
                (("query.block_state('minecraft:vertical_half') == 'bottom'",), bottom),
                (("query.block_state('minecraft:vertical_half') == 'top'",), top),
            )
        )
        document = block_document(name, {}, components, permutations)
        document["minecraft:block"]["description"]["traits"] = (
            _canopy_direction_traits(cardinal=True, vertical=True)
        )
    elif suffix == "slab":
        bottom = slab_geometry(False)
        top = slab_geometry(True)
        components = base_components(
            bottom["description"]["identifier"],
            planks,
            solid=False,
            bounds=_geometry_aabb(bottom),
        )
        permutations = [
            {
                "condition": (
                    "query.block_state('minecraft:vertical_half') == 'top'"
                ),
                "components": {
                    "minecraft:geometry": top["description"]["identifier"],
                    "netease:aabb": _geometry_aabb(top),
                },
            }
        ]
        document = block_document(name, {}, components, permutations)
        document["minecraft:block"]["description"]["traits"] = (
            _canopy_direction_traits(vertical=True)
        )
    elif suffix == "button":
        up = button_geometry(False)
        pressed = button_geometry(True)
        components = base_components(
            up["description"]["identifier"],
            planks,
            solid=False,
            bounds=_geometry_aabb(up),
        )
        components["netease:face_directional"] = {
            "type": "facing_direction"
        }
        components["netease:redstone"] = {
            "type": "producer",
            "strength": 0,
        }
        document = block_document(
            name,
            {"tf_slice:powered": [False, True]},
            components,
            [
                {
                    "condition": (
                        "query.block_state('tf_slice:powered') == true"
                    ),
                    "components": {
                        "minecraft:geometry": pressed["description"]["identifier"],
                        "netease:aabb": _geometry_aabb(pressed),
                        "netease:redstone": {
                            "type": "producer",
                            "strength": 15,
                        },
                    },
                }
            ],
        )
    elif suffix == "pressure_plate":
        up = pressure_plate_geometry(False)
        pressed = pressure_plate_geometry(True)
        components = base_components(
            up["description"]["identifier"],
            planks,
            solid=False,
            bounds=_geometry_aabb(up),
        )
        components["netease:on_entity_inside"] = {
            "send_python_event": True
        }
        components["netease:redstone"] = {
            "type": "producer",
            "strength": 0,
        }
        document = block_document(
            name,
            {"tf_slice:powered": [False, True]},
            components,
            [
                {
                    "condition": (
                        "query.block_state('tf_slice:powered') == true"
                    ),
                    "components": {
                        "minecraft:geometry": pressed["description"]["identifier"],
                        "netease:aabb": _geometry_aabb(pressed),
                        "netease:redstone": {
                            "type": "producer",
                            "strength": 15,
                        },
                    },
                }
            ],
        )
    elif suffix == "fence_gate":
        closed = gate_geometry(False)
        opened = gate_geometry(True)
        components = base_components(
            closed["description"]["identifier"],
            planks,
            solid=False,
            bounds=_rotated_geometry_aabb(closed, "north"),
        )
        permutations = _canopy_rotated_permutations(
            (
                (("query.block_state('tf_slice:open') == false",), closed),
                (("query.block_state('tf_slice:open') == true",), opened),
            )
        )
        document = block_document(
            name, {"tf_slice:open": [False, True]}, components, permutations
        )
        document["minecraft:block"]["description"]["traits"] = (
            _canopy_direction_traits(cardinal=True)
        )
    elif suffix == "door":
        lower = door_geometry("lower", False, "left")
        components = base_components(
            lower["description"]["identifier"],
            "tf_slice:canopy_door_lower",
            render_method="alpha_test",
            solid=False,
            bounds=_rotated_geometry_aabb(lower, "north"),
        )
        combinations = []
        for half in ("lower", "upper"):
            for opened in (False, True):
                geometry_entry = door_geometry(half, opened, "left")
                combinations.append(
                    (
                        (
                            "query.block_state('tf_slice:half') == '%s'" % half,
                            "query.block_state('tf_slice:open') == %s"
                            % ("true" if opened else "false"),
                        ),
                        geometry_entry,
                    )
                )
        permutations = _canopy_rotated_permutations(combinations)
        for permutation in permutations:
            half = "upper" if "'upper'" in permutation["condition"] else "lower"
            permutation["components"]["minecraft:material_instances"] = {
                "*": material(
                    "tf_slice:canopy_door_%s" % half, "alpha_test"
                )
            }
        document = block_document(
            name,
            {
                "tf_slice:open": [False, True],
                "tf_slice:half": ["lower", "upper"],
            },
            components,
            permutations,
        )
        document["minecraft:block"]["description"]["traits"] = (
            _canopy_direction_traits(cardinal=True)
        )
        document["minecraft:block"]["components"][
            "netease:listen_block_remove"
        ] = {"value": True}
    elif suffix == "trapdoor":
        bottom = trapdoor_geometry("bottom", False)
        components = base_components(
            bottom["description"]["identifier"],
            "tf_slice:canopy_trapdoor",
            render_method="alpha_test",
            solid=False,
            bounds=_rotated_geometry_aabb(bottom, "north"),
        )
        combinations = []
        for half in ("bottom", "top"):
            for opened in (False, True):
                geometry_entry = trapdoor_geometry(half, opened)
                combinations.append(
                    (
                        (
                            "query.block_state('minecraft:vertical_half') == '%s'" % half,
                            "query.block_state('tf_slice:open') == %s"
                            % ("true" if opened else "false"),
                        ),
                        geometry_entry,
                    )
                )
        document = block_document(
            name,
            {"tf_slice:open": [False, True]},
            components,
            _canopy_rotated_permutations(combinations),
        )
        document["minecraft:block"]["description"]["traits"] = (
            _canopy_direction_traits(cardinal=True, vertical=True)
        )
    elif suffix == "bookshelf":
        components = base_components(
            "geometry.tf_slice.courtyard_cube",
            "tf_slice:canopy_bookshelf",
        )
        components["minecraft:material_instances"] = {
            "*": material("tf_slice:canopy_bookshelf"),
            "side": material("tf_slice:canopy_bookshelf"),
            "top": material(planks),
            "bottom": material(planks),
        }
        document = block_document(name, {}, components)
    else:  # chest
        shape = chest_geometry()
        components = base_components(
            shape["description"]["identifier"],
            planks,
            solid=False,
            bounds=_geometry_aabb(shape),
        )
        components["netease:block_chest"] = {
            "custom_description": "tile.tf_slice:canopy_chest.name",
            "chest_capacity": 3,
            "can_pair": True,
            "mute": False,
            "can_be_blocked": True,
        }
        document = block_document(name, {}, components)

    document["minecraft:block"]["description"][
        "register_to_creative_menu"
    ] = False
    return document


def _canopy_bookshelf_geometry():
    source_cube = cube([-8, 0, -8], [16, 16, 16])
    for face in ("up", "down"):
        source_cube["uv"][face]["material_instance"] = "end"
    return geometry(
        "geometry.tf_slice.native_canopy_bookshelf", [source_cube]
    )


def canopy_world_geometry(suffix):
    if suffix == "fence":
        return _dynamic_fence_geometry(
            "geometry.tf_slice.native_canopy_fence"
        )
    if suffix == "bookshelf":
        return _canopy_bookshelf_geometry()
    return _shape_geometry(suffix)


def canopy_model_textures(suffix):
    if suffix == "door":
        return (
            "tf_slice:canopy_door_lower",
            "tf_slice:canopy_door_upper",
        )
    if suffix == "trapdoor":
        return ("tf_slice:canopy_trapdoor",)
    if suffix == "bookshelf":
        return (
            "tf_slice:canopy_bookshelf",
            CANOPY_WOOD_SPEC["planks"],
        )
    return (CANOPY_WOOD_SPEC["planks"],)


def canopy_shape_document(suffix):
    """Return the runtime-supported public-block schema for Canopy wood."""
    if suffix == "banister":
        document = banister_block_document("canopy")
    elif suffix in CANOPY_NETEASE_SUFFIXES:
        document = _native_shape_document("canopy", suffix)
        if suffix == "fence":
            document["minecraft:block"]["components"][
                "netease:connection"
            ] = {
                "blocks": [
                    "tf_slice:canopy_fence",
                    "tf_slice:canopy_fence_gate",
                    "tf_slice:canopy_banister",
                ]
            }
    else:
        raise ValueError("unsupported Canopy construction shape: %s" % suffix)
    document["minecraft:block"]["description"][
        "register_to_creative_menu"
    ] = False
    return document


def canopy_netease_model_document(suffix, item_texture):
    if suffix not in CANOPY_NETEASE_SUFFIXES:
        raise ValueError("Canopy shape does not use a NetEase model: %s" % suffix)
    texture_indexes = {"*": 0}
    if suffix == "bookshelf":
        texture_indexes["end"] = 1
    return _netease_model_document(
        "canopy_" + suffix,
        canopy_world_geometry(suffix),
        canopy_model_textures(suffix),
        item_texture,
        texture_indexes=texture_indexes,
    )


def _canopy_shaped_recipe(suffix, pattern, key, count=1):
    return {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": "tf_slice:canopy_" + suffix},
            "tags": ["crafting_table"],
            "pattern": list(pattern),
            "key": dict(key),
            "unlock": {"context": "AlwaysUnlocked"},
            "result": {
                "item": "tf_slice:canopy_" + suffix,
                "count": int(count),
            },
        },
    }


def canopy_recipe_documents():
    planks = {"item": "tf_slice:canopy_planks"}
    stick = {"item": "minecraft:stick"}
    recipes = {
        "stairs": _canopy_shaped_recipe(
            "stairs", ("#  ", "## ", "###"), {"#": planks}, 8
        ),
        "slab": _canopy_shaped_recipe(
            "slab", ("###",), {"#": planks}, 6
        ),
        "fence": _canopy_shaped_recipe(
            "fence", ("#S#", "#S#"), {"#": planks, "S": stick}, 3
        ),
        "fence_gate": _canopy_shaped_recipe(
            "fence_gate", ("S#S", "S#S"), {"#": planks, "S": stick}
        ),
        "pressure_plate": _canopy_shaped_recipe(
            "pressure_plate", ("##",), {"#": planks}
        ),
        "door": _canopy_shaped_recipe(
            "door", ("##", "##", "##"), {"#": planks}, 3
        ),
        "trapdoor": _canopy_shaped_recipe(
            "trapdoor", ("###", "###"), {"#": planks}, 2
        ),
        "banister": _canopy_shaped_recipe(
            "banister",
            ("---", "| |"),
            {
                "-": {"item": "tf_slice:canopy_slab"},
                "|": stick,
            },
            3,
        ),
        "bookshelf": _canopy_shaped_recipe(
            "bookshelf",
            ("---", "B B", "---"),
            {"-": planks, "B": {"item": "minecraft:book"}},
        ),
        "chest": _canopy_shaped_recipe(
            "chest",
            ("###", "#C#", "###"),
            {"#": planks, "C": {"item": "minecraft:chest"}},
            2,
        ),
    }
    recipes["button"] = {
        "format_version": "1.20.10",
        "minecraft:recipe_shapeless": {
            "description": {"identifier": "tf_slice:canopy_button"},
            "tags": ["crafting_table"],
            "ingredients": [planks],
            "unlock": {"context": "AlwaysUnlocked"},
            "result": {"item": "tf_slice:canopy_button", "count": 1},
        },
    }
    for suffix in CANOPY_NATIVE_SUFFIXES:
        recipe = recipes[suffix]
        value = recipe.get("minecraft:recipe_shaped") or recipe.get(
            "minecraft:recipe_shapeless"
        )
        value["result"]["item"] = (
            "minecraft:%s_%s"
            % (CANOPY_NATIVE_TEMPLATE_FAMILY, suffix)
        )
    return recipes


def canopy_geometry_document():
    entries = [
        stair_geometry(False),
        stair_geometry(True),
        slab_geometry(False),
        slab_geometry(True),
        gate_geometry(False),
        gate_geometry(True),
        button_geometry(False),
        button_geometry(True),
        pressure_plate_geometry(False),
        pressure_plate_geometry(True),
        chest_geometry(),
        _dynamic_fence_geometry(
            "geometry.tf_slice.native_canopy_fence"
        ),
    ]
    for half in ("lower", "upper"):
        for opened in (False, True):
            entries.append(door_geometry(half, opened, "left"))
    for half in ("bottom", "top"):
        for opened in (False, True):
            entries.append(trapdoor_geometry(half, opened))
    return {"format_version": "1.12.0", "minecraft:geometry": entries}


def canopy_output_manifest():
    paths = [
        "TwilightBossSliceR/textures/terrain_texture.json",
        "TwilightBossSliceR/textures/item_texture.json",
        "TwilightBossSliceR/blocks.json",
        "TwilightBossSliceR/texts/en_US.lang",
        "TwilightBossSliceR/texts/zh_CN.lang",
        "TwilightBossSliceR/textures/items/canopy_door.png",
        "TwilightBossSliceB/item_catalog/crafting_item_catalog.json",
        "TwilightBossSliceB/recipes/canopy_wood.recipe.json",
    ]
    for suffix in CANOPY_CONSTRUCTION_SUFFIXES:
        paths.append(
            "TwilightBossSliceB/recipes/canopy_%s.recipe.json" % suffix
        )
    for suffix in CANOPY_CUSTOM_SUFFIXES:
        paths.append(
            "TwilightBossSliceB/netease_blocks/canopy_%s.json" % suffix
        )
    for suffix in CANOPY_NETEASE_SUFFIXES:
        paths.append(
            "TwilightBossSliceR/models/netease_block/"
            "tf_slice_public_canopy_%s.json" % suffix
        )
        paths.append(
            "TwilightBossSliceR/textures/blocks/item_icons/"
            "canopy_%s.png" % suffix
        )
    for name in (
        "canopy_wood",
        "stripped_canopy_log",
        "stripped_canopy_wood",
    ):
        paths.append("TwilightBossSliceB/netease_blocks/%s.json" % name)
    for name in (
        "canopy_planks",
        "canopy_log",
        "canopy_log_top",
        "stripped_canopy_log",
        "stripped_canopy_log_top",
        "canopy_door_lower",
        "canopy_door_upper",
        "canopy_trapdoor",
        "canopy_bookshelf",
    ):
        paths.append("TwilightBossSliceR/textures/blocks/%s.png" % name)
    return tuple(paths)


def canopy_removed_artifacts():
    paths = [
        "TwilightBossSliceR/models/blocks/public_canopy_wood.geo.json",
        "TwilightBossSliceB/TwilightBossSlice/canopy_wood_logic.py",
    ]
    for suffix in CANOPY_NATIVE_SUFFIXES:
        name = "canopy_" + suffix
        paths.extend(
            (
                "TwilightBossSliceB/netease_blocks/%s.json" % name,
                "TwilightBossSliceR/models/netease_block/"
                "tf_slice_public_%s.json" % name,
                "TwilightBossSliceR/textures/blocks/item_icons/%s.png" % name,
            )
        )
    return tuple(paths)


def ensure_canopy_textures(atlas):
    sources = {
        "canopy_planks": "block/wood/planks_canopy_0.png",
        "canopy_log": "block/canopy_log.png",
        "canopy_log_top": "block/canopy_log_top.png",
        "stripped_canopy_log": "block/stripped_canopy_log.png",
        "stripped_canopy_log_top": "block/stripped_canopy_log_top.png",
        "canopy_door_lower": "block/wood/door/canopy_lower.png",
        "canopy_door_upper": "block/wood/door/canopy_upper.png",
        "canopy_trapdoor": "block/wood/trapdoor/canopy_trapdoor.png",
        "canopy_bookshelf": "block/wood/bookshelf_canopy.png",
    }
    for name, source in sources.items():
        target = RP / "textures" / "blocks" / (name + ".png")
        copy_texture(UPSTREAM_TEXTURES / source, target)
        atlas["tf_slice:" + name] = {
            "textures": "textures/blocks/" + name
        }


def build_canopy_wood_family():
    """Rebuild only the Canopy wood family and its catalog-facing resources."""
    terrain_path = RP / "textures" / "terrain_texture.json"
    item_path = RP / "textures" / "item_texture.json"
    blocks_path = RP / "blocks.json"
    terrain = load_json(terrain_path)
    item_atlas = load_json(item_path)
    client_blocks = load_json(blocks_path)
    atlas = terrain["texture_data"]
    ensure_canopy_textures(atlas)
    ensure_vanilla_adapter_textures(atlas)
    ensure_vanilla_adapter_item_textures(item_atlas["texture_data"])
    ensure_vanilla_adapter_client_blocks(client_blocks)
    for identifier in (
        "cherry_sign",
        "cherry_wall_sign",
        "cherry_hanging_sign",
        "cherry_wall_hanging_sign",
    ):
        client_blocks.pop(identifier, None)

    unsupported_geometry = (
        RP / "models" / "blocks" / "public_canopy_wood.geo.json"
    )
    if unsupported_geometry.exists():
        unsupported_geometry.unlink()
    write_json(
        BP / "netease_blocks" / "canopy_wood.json",
        axis_document(
            "canopy_wood",
            CANOPY_WOOD_SPEC["log"],
            CANOPY_WOOD_SPEC["log_top"],
            all_bark=True,
        ),
    )
    write_json(
        BP / "netease_blocks" / "stripped_canopy_log.json",
        axis_document(
            "stripped_canopy_log",
            CANOPY_WOOD_SPEC["stripped_log"],
            CANOPY_WOOD_SPEC["stripped_log_top"],
        ),
    )
    write_json(
        BP / "netease_blocks" / "stripped_canopy_wood.json",
        axis_document(
            "stripped_canopy_wood",
            CANOPY_WOOD_SPEC["stripped_log"],
            CANOPY_WOOD_SPEC["stripped_log_top"],
            all_bark=True,
        ),
    )
    for name, texture in (
        ("canopy_wood", CANOPY_WOOD_SPEC["log"]),
        ("stripped_canopy_log", CANOPY_WOOD_SPEC["stripped_log"]),
        ("stripped_canopy_wood", CANOPY_WOOD_SPEC["stripped_log"]),
    ):
        client_blocks["tf_slice:" + name] = {
            "textures": texture,
            "sound": "wood",
        }

    for suffix in CANOPY_NATIVE_SUFFIXES:
        name = "canopy_" + suffix
        for path in (
            BP / "netease_blocks" / (name + ".json"),
            _netease_model_path(name),
            RP / "textures" / "blocks" / "item_icons" / (name + ".png"),
        ):
            if path.exists():
                path.unlink()
        client_blocks.pop("tf_slice:" + name, None)
        atlas.pop("tf_slice:" + name, None)
        atlas.pop("tf_slice:" + name + "_item", None)

    for suffix in CANOPY_CUSTOM_SUFFIXES:
        name = "canopy_" + suffix
        write_json(
            BP / "netease_blocks" / (name + ".json"),
            canopy_shape_document(suffix),
        )
        if suffix == "banister":
            client_blocks["tf_slice:" + name] = {
                "textures": CANOPY_WOOD_SPEC["planks"],
                "sound": "wood",
            }
            stale_model = _netease_model_path(name)
            if stale_model.exists():
                stale_model.unlink()
            _remove_generated_item_icon(name, atlas)
            continue

        icon_geometry = canopy_world_geometry(suffix)
        icon_source = twilight_item_icon_source("canopy", suffix)
        java_model_name = None
        if (
            icon_source is None
            and suffix in UPSTREAM_ITEM_ICON_MODEL_SUFFIXES
        ):
            java_model_name = name
        icon_texture_alias = (
            "tf_slice:canopy_bookshelf"
            if suffix == "bookshelf"
            else CANOPY_WOOD_SPEC["planks"]
        )
        item_texture = _ensure_item_icon(
            name,
            icon_geometry,
            icon_texture_alias,
            atlas,
            source=icon_source,
            java_model_name=java_model_name,
        )
        write_json(
            _netease_model_path(name),
            canopy_netease_model_document(suffix, item_texture),
        )
        client_blocks["tf_slice:" + name] = {
            "netease_model": _netease_model_name(name),
            "sound": "wood",
        }

    for suffix, document in canopy_recipe_documents().items():
        write_json(
            BP / "recipes" / ("canopy_%s.recipe.json" % suffix),
            document,
        )
    write_json(
        BP / "recipes" / "canopy_wood.recipe.json",
        _canopy_shaped_recipe(
            "wood",
            ("##", "##"),
            {"#": {"item": "tf_slice:canopy_log"}},
            3,
        ),
    )
    write_json(terrain_path, terrain)
    write_json(item_path, item_atlas)
    write_json(blocks_path, client_blocks)

    try:
        from build_creative_catalog import normalize_creative_catalog
        from build_localization import write_native_wood_name_overrides
    except ImportError:  # pragma: no cover - package import in tests
        from tools.build_creative_catalog import normalize_creative_catalog
        from tools.build_localization import write_native_wood_name_overrides
    write_native_wood_name_overrides(ROOT)
    normalize_creative_catalog(ROOT)
    return {
        "blocks": len(CANOPY_CONSTRUCTION_SUFFIXES) + 3,
        "recipes": len(CANOPY_CONSTRUCTION_SUFFIXES),
        "manifest": len(canopy_output_manifest()),
    }


def build_shape_blocks(client_blocks, atlas):
    for family, spec in WOOD_FAMILIES.items():
        name = "%s_banister" % family
        write_json(
            BP / "netease_blocks" / (name + ".json"),
            banister_block_document(family),
        )
        client_blocks["tf_slice:" + name] = {
            "textures": spec["planks"],
            "sound": "wood",
        }
        for kind in ("horizontal", "vertical", "climbable"):
            name = "hollow_%s_log_%s" % (family, kind)
            hollow_geometry = _geometry_by_identifier(
                "geometry.tf_slice.hollow_log_" + kind
            )
            write_json(
                BP / "netease_blocks" / (name + ".json"),
                _native_hollow_document(family, kind),
            )
            item_texture = _ensure_item_icon(
                name,
                hollow_geometry,
                spec["log"],
                atlas,
            )
            write_json(
                _netease_model_path(name),
                _netease_model_document(
                    name,
                    hollow_geometry,
                    [spec["log"]],
                    item_texture,
                ),
            )
            client_blocks["tf_slice:" + name] = {
                "netease_model": _netease_model_name(name),
                "sound": "wood",
            }
    write_json(
        BP / "netease_blocks" / "canopy_fence.json",
        _native_shape_document("canopy", "fence"),
    )
    canopy_document = load_json(BP / "netease_blocks" / "canopy_fence.json")
    canopy_document["minecraft:block"]["components"]["netease:connection"] = {
        "blocks": ["tf_slice:canopy_fence"]
    }
    write_json(BP / "netease_blocks" / "canopy_fence.json", canopy_document)
    write_json(
        _netease_model_path("canopy_fence"),
        _netease_model_document(
            "canopy_fence",
            _dynamic_fence_geometry("geometry.tf_slice.native_canopy_fence"),
            ["tf_slice:canopy_fence"],
            _ensure_item_icon(
                "canopy_fence",
                _dynamic_fence_geometry(
                    "geometry.tf_slice.native_canopy_fence"
                ),
                "tf_slice:canopy_fence",
                atlas,
            ),
        ),
    )
    client_blocks["tf_slice:canopy_fence"] = {
        "netease_model": _netease_model_name("canopy_fence"),
        "sound": "wood",
    }


def remove_obsolete_wood_artifacts(client_blocks, atlas):
    removed = []
    for family in WOOD_FAMILIES:
        for suffix in OBSOLETE_WOOD_SUFFIXES:
            name = "%s_%s" % (family, suffix)
            for path in (
                BP / "netease_blocks" / (name + ".json"),
                _netease_model_path(name),
                RP / "textures" / "blocks" / "item_icons" / (name + ".png"),
            ):
                if path.exists():
                    path.unlink()
                    removed.append(path)
            if suffix != "trapdoor":
                texture_path = RP / "textures" / "blocks" / (name + ".png")
                if texture_path.exists():
                    texture_path.unlink()
                    removed.append(texture_path)
            identifier = "tf_slice:" + name
            client_blocks.pop(identifier, None)
            atlas.pop(identifier, None)
            atlas.pop(identifier + "_item", None)
        name = "%s_banister" % family
        for path in (
            _netease_model_path(name),
            RP / "textures" / "blocks" / "item_icons" / (name + ".png"),
            RP / "textures" / "blocks" / (name + ".png"),
        ):
            if path.exists():
                path.unlink()
                removed.append(path)
        atlas.pop("tf_slice:" + name, None)
        atlas.pop("tf_slice:" + name + "_item", None)
    return tuple(removed)


def _build_knight_phantom_trophy_texture(target):
    skeleton = Image.open(
        str(UPSTREAM_TEXTURES / "model/phantomskeleton.png")
    ).convert("RGBA")
    armor = Image.open(
        str(UPSTREAM_TEXTURES / "armor/phantom_1.png")
    ).convert("RGBA")
    texture = Image.new("RGBA", (128, 32), (0, 0, 0, 0))
    texture.paste(skeleton, (0, 0))
    texture.paste(armor, (64, 0))
    target.parent.mkdir(parents=True, exist_ok=True)
    texture.save(str(target), format="PNG", optimize=False)


def _build_composited_trophy_item_icon(
    geometry_entry,
    model_texture,
    upstream_base,
    target,
    foreground_size,
    canvas_size=16,
    draw_outline=True,
):
    _render_geometry_item_icon(
        geometry_entry,
        model_texture,
        target,
        output_size=foreground_size,
        projection_mode="front",
    )
    rendered = Image.open(str(target)).convert("RGBA")
    rendered_head = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    offset = ((canvas_size - int(foreground_size)) // 2,) * 2
    rendered_head.paste(rendered, offset, rendered)
    base = Image.open(str(upstream_base)).convert("RGBA")
    # Preserve the original medal pixels; give horns and the face enough
    # samples to survive the inventory renderer without a heavy black halo.
    base = base.resize((canvas_size, canvas_size), Image.Resampling.NEAREST)
    combined = base
    if draw_outline:
        head_alpha = rendered_head.getchannel("A")
        outline_alpha = head_alpha.filter(ImageFilter.MaxFilter(3))
        outline = Image.new("RGBA", rendered_head.size, (30, 28, 26, 0))
        outline.putalpha(outline_alpha)
        combined = Image.alpha_composite(base, outline)
    combined = Image.alpha_composite(combined, rendered_head)
    pixels = combined.load()
    for y_value in range(combined.height):
        for x_value in range(combined.width):
            red, green, blue, alpha = pixels[x_value, y_value]
            pixels[x_value, y_value] = (
                red,
                green,
                blue,
                255 if alpha >= 128 else 0,
            )
    combined.save(str(target), format="PNG", optimize=False)


def trophy_item_document(name):
    block_identifier = "tf_slice:%s_trophy" % name
    identifier = block_identifier + "_item"
    return {
        "format_version": "1.21.60",
        "minecraft:item": {
            "description": {
                "identifier": identifier,
                "menu_category": {"category": "nature"},
            },
            "components": {
                "minecraft:display_name": {
                    "value": "tile.%s.name" % block_identifier
                },
                "minecraft:icon": {
                    "textures": {"default": identifier}
                },
                "minecraft:block_placer": {
                    "block": block_identifier
                },
                "minecraft:wearable": {
                    "slot": "slot.armor.head",
                    "protection": 0,
                },
                "minecraft:max_stack_size": 64,
            },
        },
    }


def trophy_loot_document(name):
    return {
        "pools": [
            {
                "rolls": 1,
                "entries": [
                    {
                        "type": "item",
                        "name": "tf_slice:%s_trophy_item" % name,
                        "weight": 1,
                    }
                ],
            }
        ]
    }


def build_trophies(atlas, item_atlas, client_blocks, trophy_geometries):
    model_directory = RP / "textures" / "entity" / "tf_slice" / "trophies"
    item_directory = RP / "textures" / "blocks"
    transparent_target = item_directory / "trophy_anchor_transparent.png"
    transparent_target.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(
        str(transparent_target),
        format="PNG",
        optimize=False,
    )
    atlas["tf_slice:trophy_anchor_transparent"] = {
        "textures": "textures/blocks/trophy_anchor_transparent"
    }
    for variant, spec in TROPHY_SPECS.items():
        base_name = variant + "_trophy"
        geometry_name = "geometry.tf_slice.%s_trophy" % variant
        model_target = model_directory / (variant + ".png")
        if len(spec["model_textures"]) == 1:
            copy_texture(
                UPSTREAM_TEXTURES / spec["model_textures"][0], model_target
            )
        else:
            _build_knight_phantom_trophy_texture(model_target)
        atlas["tf_slice:%s_model" % base_name] = {
            "textures": "textures/entity/tf_slice/trophies/%s" % variant
        }

        item_target = item_directory / (base_name + ".png")
        if spec["composite_item"]:
            _build_composited_trophy_item_icon(
                trophy_geometries[geometry_name],
                model_target,
                UPSTREAM_TEXTURES / spec["item_texture"],
                item_target,
                spec["icon_foreground_size"],
                canvas_size=spec.get("icon_canvas_size", 16),
                draw_outline=spec.get("icon_outline", True),
            )
        elif spec["item_texture"]:
            copy_texture(
                UPSTREAM_TEXTURES / spec["item_texture"], item_target
            )
        else:
            _render_geometry_item_icon(
                trophy_geometries[geometry_name], model_target, item_target
            )
        item_path = "textures/blocks/%s" % base_name
        atlas["tf_slice:" + base_name] = {"textures": item_path}
        item_atlas["tf_slice:" + base_name] = {"textures": item_path}
        item_atlas["tf_slice:" + base_name + "_item"] = {
            "textures": item_path
        }
        write_json(
            BP / "items" / (base_name + ".item.json"),
            trophy_item_document(variant),
        )
        write_json(
            BP / "loot_tables" / "blocks" / "tf_slice" / (base_name + ".json"),
            trophy_loot_document(variant),
        )
    definitions = tuple(
        (
            "%s%s_trophy" % (variant, wall_name),
            "%s_trophy" % variant,
            "geometry.tf_slice.%s_trophy" % variant,
            bool(wall_name),
        )
        for variant in TROPHY_SPECS
        for wall_name in ("", "_wall")
    )
    for name, base_name, geometry_name, wall in definitions:
        write_json(
            BP / "netease_blocks" / (name + ".json"),
            trophy_document(
                name,
                base_name,
                geometry_name,
                trophy_geometries[geometry_name],
                wall=wall,
            ),
        )
        atlas["tf_slice:" + name] = copy.deepcopy(
            atlas["tf_slice:" + base_name]
        )
        item_atlas["tf_slice:" + name] = copy.deepcopy(
            item_atlas["tf_slice:" + base_name]
        )
        client_blocks["tf_slice:" + name] = {
            "textures": "tf_slice:" + name,
            "sound": "stone",
        }
def build_trophy_wearable_resources():
    """Write only head attachments; keep inventory icons and block shapes intact."""
    write_json(RP / "models" / "entity" / "wearable_trophies.geo.json", trophy_wearable_geometry_document())
    write_json(RP / "animations" / "trophy.animation.json", trophy_animation_document())
    for name in TROPHY_SPECS:
        write_json(RP / "attachables" / (name + "_trophy.attachable.json"), trophy_attachable_document(name))
        write_json(BP / "items" / (name + "_trophy.item.json"), trophy_item_document(name))


def normalize_trophy_creative_catalog():
    path = BP / "item_catalog" / "crafting_item_catalog.json"
    document = load_json(path)
    replacements = {
        "tf_slice:%s_trophy" % name: "tf_slice:%s_trophy_item" % name
        for name in TROPHY_SPECS
    }
    catalog = document["minecraft:crafting_items_catalog"]
    for category in catalog.get("categories", []):
        for group in category.get("groups", []):
            items = []
            for identifier in group.get("items", []):
                identifier = replacements.get(identifier, identifier)
                if identifier not in items:
                    items.append(identifier)
            group["items"] = items
    catalog_items = {
        identifier
        for category in catalog.get("categories", [])
        for group in category.get("groups", [])
        for identifier in group.get("items", [])
    }
    if "tf_slice:canopy_fence" not in catalog_items:
        construction = next(
            (
                category
                for category in catalog.get("categories", [])
                if category.get("category_name") == "construction"
            ),
            None,
        )
        if construction and construction.get("groups"):
            construction["groups"][0].setdefault("items", []).append(
                "tf_slice:canopy_fence"
            )
    write_json(path, document)
    return tuple(replacements.values())


def build_trophy_resources():
    """Rebuild only trophy-owned resources and their atlas registrations."""
    trophy_geometry = trophy_geometry_document()
    write_json(
        RP / "models" / "blocks" / "public_trophies.geo.json",
        trophy_geometry,
    )
    write_json(
        RP / "models" / "blocks" / "trophy_floor_rotations.geo.json",
        trophy_floor_rotation_geometry_document(),
    )
    obsolete_item_visual = (
        RP / "models" / "blocks" / "trophy_item_icon.geo.json"
    )
    if obsolete_item_visual.exists():
        obsolete_item_visual.unlink()
    write_json(
        RP / "models" / "entity" / "ur_ghast_trophy_visual.geo.json",
        ur_ghast_trophy_visual_geometry_document(),
    )
    write_json(
        RP / "animations" / "trophy.animation.json",
        trophy_animation_document(),
    )
    write_json(
        RP / "entity" / "ur_ghast_trophy_visual.entity.json",
        ur_ghast_trophy_visual_client_document(),
    )
    write_json(
        BP / "entities" / "ur_ghast_trophy_visual.entity.json",
        ur_ghast_trophy_visual_behavior_document(),
    )
    obsolete_animation = (
        RP / "models" / "blocks" / "ur_ghast_trophy_animation.geo.json"
    )
    if obsolete_animation.exists():
        obsolete_animation.unlink()
    terrain_path = RP / "textures" / "terrain_texture.json"
    item_path = RP / "textures" / "item_texture.json"
    blocks_path = RP / "blocks.json"
    terrain = load_json(terrain_path)
    item_atlas = load_json(item_path)
    client_blocks = load_json(blocks_path)
    build_trophies(
        terrain["texture_data"],
        item_atlas["texture_data"],
        client_blocks,
        {
            entry["description"]["identifier"]: entry
            for entry in trophy_geometry["minecraft:geometry"]
        },
    )
    build_trophy_wearable_resources()
    write_json(terrain_path, terrain)
    write_json(item_path, item_atlas)
    write_json(blocks_path, client_blocks)
    normalize_trophy_creative_catalog()
    return {
        "trophies": len(INTERNAL_TROPHY_BLOCK_IDS),
        "geometryFiles": 4,
        "attachables": len(TROPHY_SPECS),
        "itemIcons": len(TROPHY_SPECS),
    }


def build():
    obsolete_wood_geometry = (
        RP / "models" / "blocks" / "public_wood_shapes.geo.json"
    )
    if obsolete_wood_geometry.exists():
        obsolete_wood_geometry.unlink()
    write_json(
        RP / "models" / "blocks" / "wood_sapling.geo.json",
        sapling_geometry_document(),
    )
    write_json(
        RP / "models" / "blocks" / "wood_banister.geo.json",
        banister_geometry_document(),
    )
    trophy_geometry = trophy_geometry_document()
    write_json(
        RP / "models" / "blocks" / "public_trophies.geo.json",
        trophy_geometry,
    )
    write_json(
        RP / "models" / "blocks" / "trophy_floor_rotations.geo.json",
        trophy_floor_rotation_geometry_document(),
    )
    obsolete_item_visual = (
        RP / "models" / "blocks" / "trophy_item_icon.geo.json"
    )
    if obsolete_item_visual.exists():
        obsolete_item_visual.unlink()
    write_json(
        RP / "models" / "entity" / "ur_ghast_trophy_visual.geo.json",
        ur_ghast_trophy_visual_geometry_document(),
    )
    write_json(
        RP / "animations" / "trophy.animation.json",
        trophy_animation_document(),
    )
    write_json(
        RP / "entity" / "ur_ghast_trophy_visual.entity.json",
        ur_ghast_trophy_visual_client_document(),
    )
    write_json(
        BP / "entities" / "ur_ghast_trophy_visual.entity.json",
        ur_ghast_trophy_visual_behavior_document(),
    )
    obsolete_animation = (
        RP / "models" / "blocks" / "ur_ghast_trophy_animation.geo.json"
    )
    if obsolete_animation.exists():
        obsolete_animation.unlink()
    terrain_path = RP / "textures" / "terrain_texture.json"
    item_path = RP / "textures" / "item_texture.json"
    blocks_path = RP / "blocks.json"
    terrain = load_json(terrain_path)
    item_atlas = load_json(item_path)
    client_blocks = load_json(blocks_path)
    atlas = terrain["texture_data"]
    remove_obsolete_wood_artifacts(client_blocks, atlas)
    ensure_wood_textures(atlas)
    ensure_vanilla_adapter_textures(atlas)
    ensure_vanilla_adapter_item_textures(item_atlas["texture_data"])
    ensure_vanilla_adapter_client_blocks(client_blocks)
    build_base_wood_blocks()
    build_tree_saplings(client_blocks, atlas)
    build_shape_blocks(client_blocks, atlas)
    build_trophies(
        atlas,
        item_atlas["texture_data"],
        client_blocks,
        {
            entry["description"]["identifier"]: entry
            for entry in trophy_geometry["minecraft:geometry"]
        },
    )
    build_trophy_wearable_resources()
    atlas["tf_slice:reactor_debris"] = {
        "textures": "textures/blocks/reactor_debris"
    }
    write_json(terrain_path, terrain)
    write_json(item_path, item_atlas)
    write_json(blocks_path, client_blocks)
    try:
        from build_creative_catalog import normalize_creative_catalog
    except ImportError:  # pragma: no cover - package import in tests
        from tools.build_creative_catalog import normalize_creative_catalog
    normalize_creative_catalog(ROOT)
    canopy_result = build_canopy_wood_family()
    return {
        "woodFamilies": len(WOOD_FAMILIES),
        "canopyBlocks": canopy_result["blocks"],
        "treeSaplings": len(TREE_SAPLINGS),
        "trophies": len(INTERNAL_TROPHY_BLOCK_IDS),
        "geometryFiles": 5,
        "neteaseModels": 7,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trophies-only",
        action="store_true",
        help="rebuild only trophy models, icons, attachables, blocks, and atlas entries",
    )
    parser.add_argument(
        "--canopy-only",
        action="store_true",
        help="rebuild only the custom Canopy wood family and catalog entries",
    )
    options = parser.parse_args()
    if options.trophies_only and options.canopy_only:
        parser.error("choose only one scoped rebuild")
    if options.trophies_only:
        result = build_trophy_resources()
    elif options.canopy_only:
        result = build_canopy_wood_family()
    else:
        result = build()
    print(json.dumps(result, sort_keys=True))
