#!/usr/bin/env python3
"""Build the 4.3.2508 Twilight Forest ruin structure pack.

The source templates are Java Edition gzip-compressed, big-endian NBT. Bedrock
`.mcstructure` files are uncompressed, little-endian NBT with a different
palette and block-index layout. This tool performs that conversion explicitly
and generates the structures that were procedural in the upstream mod.
"""

from __future__ import print_function

import argparse
import contextlib
import copy
import datetime
import gzip
import hashlib
import io
import json
import math
import os
import random
import shutil
import struct
import sys

try:
    from pathlib import Path
except ImportError:  # pragma: no cover - build tooling requires Python 3
    Path = None


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import ruin_worldgen_logic as ruin_logic
from TwilightBossSlice import release_metadata
try:
    import lich_tower_legacy_port
except ImportError:  # pragma: no cover - package import in lock tests
    from tools import lich_tower_legacy_port
try:
    from native_structure_worldgen_safety import guard_native_structure_rules
except ImportError:  # pragma: no cover - package import in tests
    from tools.native_structure_worldgen_safety import (
        guard_native_structure_rules,
    )
try:
    from ruin_structure_dedup import (
        collect_external_ruin_structure_references,
        deduplicate_ruin_structure_files,
        plan_ruin_structure_deduplication,
        resolve_ruin_structure_reference,
    )
except ImportError:  # pragma: no cover - package import in tests
    from tools.ruin_structure_dedup import (
        collect_external_ruin_structure_references,
        deduplicate_ruin_structure_files,
        plan_ruin_structure_deduplication,
        resolve_ruin_structure_reference,
    )


SOURCE_ROOT = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
)
JAVA_STRUCTURES = SOURCE_ROOT / "data" / "twilightforest" / "structures"
OUTPUT_ROOT = BP / "structures" / "tf_slice" / "ruins"
HANDOFF_ROOT = BP / "structures" / "tf_slice" / "ruin_handoff"
BUILD_LOCK_PATH = ROOT / ".build_ruin_structures.lock"
WRITE_LEASE_PATH = ROOT / "source_locks" / "ruin_structure_write_lease.json"
SOURCE_VERSION = "4.3.2508"
# NetEase 3.8 serializes current vanilla block palettes with this version.
# Keeping the older 1.18-era value makes structure-restored grass_block skip
# the current grass tint path, leaving the top texture visibly gray.
BEDROCK_BLOCK_VERSION = 0x01153C21
COURTYARD_ROW_OF_CELLS = 8
COURTYARD_CELL_SIZE = 12
COURTYARD_RADIUS = int(
    (((COURTYARD_ROW_OF_CELLS - 2) / 2.0) * COURTYARD_CELL_SIZE) + 8
)
COURTYARD_HEDGE_FLOOF = 0.5
COURTYARD_WALL_INTEGRITY = 0.95
COURTYARD_WALL_DECAY = 0.1
COURTYARD_MARGIN = 8
COURTYARD_SIZE = COURTYARD_RADIUS * 2 + COURTYARD_MARGIN * 2
COURTYARD_HEIGHT = 12
COURTYARD_WALKWAY_Y = 2
COURTYARD_TERRACE_ORIGIN_Y = 0
COURTYARD_PIECE_VERTICAL_OFFSET = -2
SURFACE_NATIVE_GROUND_Y = 16
LABYRINTH_SURFACE_GROUND_Y = 41
TWILIGHT_FLAT_SURFACE_Y = 64
SURFACE_NATIVE_FOUNDATION_DEPTH = 16
HOLLOW_HILL_CAVE_FLOOR_SUPPORT_DEPTH = 1
SURFACE_NATIVE_WORLDGEN_MARGIN = 24
SURFACE_NATIVE_TRANSITION_MAX_DEVIATION = 16
SURFACE_NATIVE_TERRAIN_CLEARANCE = SURFACE_NATIVE_TRANSITION_MAX_DEVIATION
SURFACE_NATIVE_VEGETATION_CLEARANCE = 0
SURFACE_NATIVE_ANCHOR_SAMPLE_RADIUS = 64
SURFACE_NATIVE_ANCHOR_MAX_RISE = 3
SURFACE_NATIVE_CONTOUR_NOISE_AMPLITUDE = 5
SURFACE_NATIVE_CONTOUR_NOISE_CELL_SIZE = 12
SURFACE_NATIVE_MAX_ADJACENT_STEP = 1
# Compatibility alias for tooling that imported the old runtime policy name.
SURFACE_NATIVE_EDGE_BLEND_WIDTH = SURFACE_NATIVE_WORLDGEN_MARGIN
SURFACE_NATIVE_TERRAIN_ADAPTATION_STAGE = "surface_pass"
SURFACE_NATIVE_TERRAIN_ADAPTATION_MODE = "beard_thin"
SURFACE_NATIVE_PLACEMENT_PASS = "surface_pass"
POST_LANDMARK_PLACEMENT_PASS = "after_surface_pass"
POST_LANDMARK_ENVIRONMENT_RUINS = frozenset(
    ("fallen_hollow_log", "hollow_stump", "hollow_tree")
)
# Compatibility alias retained for tools that referenced the older split pass.
NAGA_COURTYARD_NATIVE_PLACEMENT_PASS = SURFACE_NATIVE_PLACEMENT_PASS
LANDMARK_PROTECTED_GRASS_BLOCK = "tf_slice:landmark_protected_grass"
SURFACE_VEGETATION_EXCLUSION_RADIUS = 6
DARK_TOWER_VEGETATION_EXCLUSION_RADIUS = 16
SURFACE_VEGETATION_PROTECTED_KINDS = frozenset(
    ("hedge_maze", "naga_courtyard", "dark_tower")
)
SURFACE_NATIVE_GRASS_BLOCKS = frozenset(
    ("minecraft:grass", "minecraft:grass_block")
)
# Kept as compatibility aliases for callers that imported the older terrain
# clearance names. Vegetation is generated after the surface pass and does not
# need an authored air column.
SURFACE_NATIVE_CLEARANCE = SURFACE_NATIVE_TERRAIN_CLEARANCE
NAGA_COURTYARD_NATIVE_CLEARANCE = SURFACE_NATIVE_TERRAIN_CLEARANCE
SURFACE_LANDMARK_BIOME_TYPES = {
    "ordinary": (1, 15, 21, 29, 35, 129, 132),
    "dense_mushroom": (14,),
    "enchanted": (155,),
    "swamp": (6,),
    "fire_swamp": (134,),
    "dark_forest": (157,),
    "dark_forest_center": (160,),
}
HOLLOW_TREE_BIOME_TYPES = (1, 14, 15, 21, 29, 35, 129, 132)
HOLLOW_TREE_CELL_BLOCKS = 32
HOLLOW_TREE_CELL_CHANCE_NUMERATOR = 4
HOLLOW_TREE_CELL_CHANCE_DENOMINATOR = 35
HOLLOW_TREE_TRIGGER_REFERENCE = "tf_slice/hollow_tree_chunk_trigger"
HOLLOW_TREE_TRIGGER_STRUCTURE = "tf_slice:hollow_tree_chunk_trigger"
HOLLOW_TREE_ROOT_BURY_DEPTH = 1
HOLLOW_ROOT_SUBSURFACE_DEPTH = 9
HOLLOW_TRUNK_SUBSURFACE_DEPTH = 4
HOLLOW_ROOT_RING_SPECS = (
    (3, 2, 6, 0.75),
    (1, 2, 8, 0.9),
)
DARK_TOWER_CANOPY_CLEANUP_TRIGGER_REFERENCE = (
    "tf_slice/dark_tower_canopy_cleanup_trigger"
)
# Route structures are selected by the biome at the nominal 256-block
# landmark center. Requiring an entire structure-sized square to remain in one
# biome rejected valid boundary centers and multiplied Molang work per chunk.
ROUTE_CORE_MODE_BIOME_TYPES = {
    "fire_swamp": (134,),
    "dark_forest_center": (160,),
}
ROUTE_COMPANION_MODE_CORE_TYPES = {
    "swamp": (134,),
    "dark_forest": (160,),
}
# The source places one companion landmark in every cardinal 256-block cell.
# Use the pure shared offsets instead of accepting every matching envelope
# sample, so native placement, map icons, locate, and recovery all see exactly
# one main landmark plus four companions.
ROUTE_COMPANION_TO_CORE_OFFSETS = (
    ruin_logic.ROUTE_LANDMARK_CARDINAL_OFFSETS
)
SURFACE_LANDMARK_TILE_RADIUS_CHUNKS = {
    "ordinary": 5,
    "dense_mushroom": 5,
    "enchanted": 5,
    "swamp": 5,
    "fire_swamp": 4,
    "dark_forest": 5,
    "dark_forest_center": 3,
}
LEGACY_LANDMARK_CENTER_JITTER_CHUNKS = 3
SURFACE_LANDMARK_TRIGGER_RADIUS_CHUNKS = {
    mode: tile_radius + LEGACY_LANDMARK_CENTER_JITTER_CHUNKS
    for mode, tile_radius in SURFACE_LANDMARK_TILE_RADIUS_CHUNKS.items()
}

TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12

FORBIDDEN_OUTPUT_BLOCKS = {
    "minecraft:structure_block",
    "minecraft:jigsaw",
    "minecraft:structure_void",
}
STATELESS_COURTYARD_BLOCKS = {
    "tf_slice:spiral_bricks",
    "tf_slice:hedge",
    "tf_slice:mazestone",
    "tf_slice:mazestone_mosaic",
    "tf_slice:naga_boss_spawner",
    "tf_slice:lich_boss_spawner",
    "tf_slice:minoshroom_boss_spawner",
    "tf_slice:hydra_boss_spawner",
}
STATELESS_AXIS_BLOCKS = {
    "tf_slice:twilight_oak_log": {
        "x": "tf_slice:twilight_oak_log_x",
        "y": "tf_slice:twilight_oak_log",
        "z": "tf_slice:twilight_oak_log_z",
    },
    "tf_slice:canopy_log": {
        "x": "tf_slice:canopy_log_x",
        "y": "tf_slice:canopy_log",
        "z": "tf_slice:canopy_log_z",
    },
}
STATELESS_AXIS_BLOCK_IDS = frozenset(
    identifier
    for variants in STATELESS_AXIS_BLOCKS.values()
    for identifier in variants.values()
)
DIRECT_BEDROCK_BLOCKS = {
    "minecraft:air",
    "minecraft:andesite",
    "minecraft:barrel",
    "minecraft:birch_fence",
    "minecraft:birch_planks",
    "minecraft:birch_slab",
    "minecraft:birch_stairs",
    "minecraft:bookshelf",
    "minecraft:black_terracotta",
    "minecraft:brick_stairs",
    "minecraft:cauldron",
    "minecraft:chain",
    "minecraft:chest",
    "minecraft:cobblestone",
    "minecraft:cobblestone_slab",
    "minecraft:cobblestone_wall",
    "minecraft:dark_oak_fence",
    "minecraft:dirt",
    "minecraft:dispenser",
    "minecraft:fire",
    "minecraft:flower_pot",
    "minecraft:glass_pane",
    "minecraft:gravel",
    "minecraft:hopper",
    "minecraft:iron_bars",
    "minecraft:ladder",
    "minecraft:light_gray_carpet",
    "minecraft:mossy_cobblestone",
    "minecraft:mossy_cobblestone_slab",
    "minecraft:mossy_cobblestone_stairs",
    "minecraft:mossy_cobblestone_wall",
    "minecraft:mossy_stone_brick_slab",
    "minecraft:mossy_stone_brick_stairs",
    "minecraft:mossy_stone_brick_wall",
    "minecraft:nether_brick_fence",
    "minecraft:oak_stairs",
    "minecraft:polished_andesite",
    "minecraft:red_candle",
    "minecraft:red_carpet",
    "minecraft:redstone_wire",
    "minecraft:sandstone_slab",
    "minecraft:smooth_stone_slab",
    "minecraft:spruce_door",
    "minecraft:spruce_leaves",
    "minecraft:spruce_stairs",
    "minecraft:sticky_piston",
    "minecraft:stone",
    "minecraft:stone_button",
    "minecraft:stone_brick_slab",
    "minecraft:stone_brick_stairs",
    "minecraft:stone_stairs",
    "minecraft:tnt",
    "minecraft:torch",
    "minecraft:trapped_chest",
    "minecraft:tripwire_hook",
    "minecraft:vine",
    "minecraft:water",
    "minecraft:white_carpet",
    "tf_slice:lich_boss_spawner",
}
TEMPLATE_WEATHERING = {
    "minecraft:cobblestone": "minecraft:mossy_cobblestone",
    "minecraft:cobblestone_slab": "minecraft:mossy_cobblestone_slab",
    "minecraft:cobblestone_stairs": "minecraft:mossy_cobblestone_stairs",
    "minecraft:cobblestone_wall": "minecraft:mossy_cobblestone_wall",
    "minecraft:stone_bricks": "minecraft:mossy_stone_bricks",
    "minecraft:stone_brick_slab": "minecraft:mossy_stone_brick_slab",
    "minecraft:stone_brick_stairs": "minecraft:mossy_stone_brick_stairs",
    "minecraft:stone_brick_wall": "minecraft:mossy_stone_brick_wall",
}
STAIR_DIRECTIONS = {
    "east": 0,
    "west": 1,
    "south": 2,
    "north": 3,
}
CARDINAL_DIRECTIONS = {
    "south": 0,
    "west": 1,
    "north": 2,
    "east": 3,
}
FACING_DIRECTIONS = {
    "down": 0,
    "up": 1,
    "north": 2,
    "south": 3,
    "west": 4,
    "east": 5,
}

SMALL_RARITIES = {
    "monolith": 90,
    "stone_circle": 105,
    "well": 80,
    "foundation": 90,
    "druid_hut": 105,
    "outside_stalagmite": 77,
    "hollow_stump": 80,
    "fallen_hollow_log": 85,
    "grove_ruins": 110,
}
SMALL_VERTICAL_OFFSETS = {
    "well": -20,
    "druid_hut": -12,
    "foundation": -2,
    "hollow_stump": -HOLLOW_ROOT_SUBSURFACE_DEPTH,
}


class NbtTag(object):
    def __init__(self, tag_type, value):
        self.tag_type = tag_type
        self.value = value


def byte(value):
    return NbtTag(TAG_BYTE, int(value))


def integer(value):
    return NbtTag(TAG_INT, int(value))


def string(value):
    return NbtTag(TAG_STRING, str(value))


def compound(value):
    return NbtTag(TAG_COMPOUND, value)


def list_tag(element_type, values):
    return NbtTag(TAG_LIST, (element_type, values))


def _read_exact(stream, size):
    value = stream.read(size)
    if len(value) != size:
        raise ValueError("unexpected end of NBT stream")
    return value


def _read_number(stream, fmt):
    return struct.unpack(fmt, _read_exact(stream, struct.calcsize(fmt)))[0]


def _read_string(stream, endian):
    length = _read_number(stream, endian + "H")
    return _read_exact(stream, length).decode("utf-8")


def _read_payload(stream, tag_type, endian):
    if tag_type == TAG_BYTE:
        return _read_number(stream, "b")
    if tag_type == TAG_SHORT:
        return _read_number(stream, endian + "h")
    if tag_type == TAG_INT:
        return _read_number(stream, endian + "i")
    if tag_type == TAG_LONG:
        return _read_number(stream, endian + "q")
    if tag_type == TAG_FLOAT:
        return _read_number(stream, endian + "f")
    if tag_type == TAG_DOUBLE:
        return _read_number(stream, endian + "d")
    if tag_type == TAG_BYTE_ARRAY:
        length = _read_number(stream, endian + "i")
        return _read_exact(stream, length)
    if tag_type == TAG_STRING:
        return _read_string(stream, endian)
    if tag_type == TAG_LIST:
        element_type = _read_number(stream, "B")
        length = _read_number(stream, endian + "i")
        return [
            _read_payload(stream, element_type, endian) for _ in range(length)
        ]
    if tag_type == TAG_COMPOUND:
        result = {}
        while True:
            child_type = _read_number(stream, "B")
            if child_type == TAG_END:
                return result
            child_name = _read_string(stream, endian)
            result[child_name] = _read_payload(stream, child_type, endian)
    if tag_type == TAG_INT_ARRAY:
        length = _read_number(stream, endian + "i")
        return [_read_number(stream, endian + "i") for _ in range(length)]
    if tag_type == TAG_LONG_ARRAY:
        length = _read_number(stream, endian + "i")
        return [_read_number(stream, endian + "q") for _ in range(length)]
    raise ValueError("unsupported NBT tag type %r" % tag_type)


def read_java_nbt(path):
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    stream = io.BytesIO(raw)
    root_type = _read_number(stream, "B")
    if root_type != TAG_COMPOUND:
        raise ValueError("%s does not contain a compound root" % path)
    _read_string(stream, ">")
    return _read_payload(stream, TAG_COMPOUND, ">")


def _write_string(stream, value):
    encoded = value.encode("utf-8")
    stream.write(struct.pack("<H", len(encoded)))
    stream.write(encoded)


def _write_payload(stream, tag):
    tag_type = tag.tag_type
    value = tag.value
    if tag_type == TAG_BYTE:
        stream.write(struct.pack("b", value))
    elif tag_type == TAG_SHORT:
        stream.write(struct.pack("<h", value))
    elif tag_type == TAG_INT:
        stream.write(struct.pack("<i", value))
    elif tag_type == TAG_LONG:
        stream.write(struct.pack("<q", value))
    elif tag_type == TAG_FLOAT:
        stream.write(struct.pack("<f", value))
    elif tag_type == TAG_DOUBLE:
        stream.write(struct.pack("<d", value))
    elif tag_type == TAG_STRING:
        _write_string(stream, value)
    elif tag_type == TAG_LIST:
        element_type, values = value
        stream.write(struct.pack("B", element_type))
        stream.write(struct.pack("<i", len(values)))
        for child in values:
            child_tag = child
            if not isinstance(child, NbtTag):
                child_tag = NbtTag(element_type, child)
            if child_tag.tag_type != element_type:
                raise ValueError("mixed NBT list types")
            _write_payload(stream, child_tag)
    elif tag_type == TAG_COMPOUND:
        for name, child in value.items():
            stream.write(struct.pack("B", child.tag_type))
            _write_string(stream, name)
            _write_payload(stream, child)
        stream.write(struct.pack("B", TAG_END))
    elif tag_type == TAG_INT_ARRAY:
        stream.write(struct.pack("<i", len(value)))
        for item in value:
            stream.write(struct.pack("<i", item))
    else:
        raise ValueError("unsupported output NBT tag %r" % tag_type)


def write_nbt(path, root):
    stream = io.BytesIO()
    stream.write(struct.pack("B", TAG_COMPOUND))
    _write_string(stream, "")
    _write_payload(stream, compound(root))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(stream.getvalue())


class SparseStructure(object):
    def __init__(self, size, name=""):
        self.size = tuple(int(value) for value in size)
        self.name = name
        self.blocks = {}
        self.entities = []

    def set(self, x, y, z, name, states=None, block_entity=None):
        x, y, z = int(x), int(y), int(z)
        if not (
            0 <= x < self.size[0]
            and 0 <= y < self.size[1]
            and 0 <= z < self.size[2]
        ):
            return
        if name in FORBIDDEN_OUTPUT_BLOCKS:
            raise ValueError("forbidden output block %s in %s" % (name, self.name))
        self.blocks[(x, y, z)] = (
            str(name),
            dict(states or {}),
            dict(block_entity or {}),
        )

    def fill(self, start, end, name, states=None):
        for x in range(start[0], end[0] + 1):
            for y in range(start[1], end[1] + 1):
                for z in range(start[2], end[2] + 1):
                    self.set(x, y, z, name, states)

    def add_entity(self, x, y, z, identifier, yaw=0.0):
        if not (
            0.0 <= float(x) < self.size[0]
            and 0.0 <= float(y) < self.size[1]
            and 0.0 <= float(z) < self.size[2]
        ):
            raise ValueError("entity outside structure %s" % self.name)
        self.entities.append(
            (float(x), float(y), float(z), str(identifier), float(yaw))
        )

    def merge(self, other, offset=(0, 0, 0)):
        for (x, y, z), block in other.blocks.items():
            self.set(
                x + offset[0],
                y + offset[1],
                z + offset[2],
                block[0],
                block[1],
                block[2],
            )
        for x, y, z, identifier, yaw in other.entities:
            self.add_entity(
                x + offset[0],
                y + offset[1],
                z + offset[2],
                identifier,
                yaw,
            )

    def crop(self, start_x, start_z, size_x, size_z, name):
        result = SparseStructure((size_x, self.size[1], size_z), name)
        for (x, y, z), block in self.blocks.items():
            if (
                start_x <= x < start_x + size_x
                and start_z <= z < start_z + size_z
            ):
                result.set(
                    x - start_x,
                    y,
                    z - start_z,
                    block[0],
                    block[1],
                    block[2],
                )
        for x, y, z, identifier, yaw in self.entities:
            if (
                start_x <= x < start_x + size_x
                and start_z <= z < start_z + size_z
            ):
                result.add_entity(
                    x - start_x,
                    y,
                    z - start_z,
                    identifier,
                    yaw,
                )
        return result


def _state_tag(value):
    if isinstance(value, bool):
        return byte(1 if value else 0)
    if isinstance(value, int):
        return integer(value)
    return string(value)


def write_mcstructure(path, structure):
    palette_keys = []
    palette_indexes = {}
    for block in structure.blocks.values():
        key = (block[0], tuple(sorted(block[1].items())))
        if key not in palette_indexes:
            palette_indexes[key] = len(palette_keys)
            palette_keys.append(key)

    palette = []
    for name, states in palette_keys:
        _validate_custom_block_states(name, dict(states), structure.name)
        palette.append(
            compound(
                {
                    "name": string(name),
                    "states": compound(
                        {key: _state_tag(value) for key, value in states}
                    ),
                    "version": integer(BEDROCK_BLOCK_VERSION),
                }
            )
        )

    volume = structure.size[0] * structure.size[1] * structure.size[2]
    primary = [-1] * volume
    block_position_data = {}
    for (x, y, z), block in structure.blocks.items():
        index = x * structure.size[1] * structure.size[2] + y * structure.size[2] + z
        key = (block[0], tuple(sorted(block[1].items())))
        primary[index] = palette_indexes[key]
        if block[2]:
            block_position_data[str(index)] = compound(
                {"block_entity_data": compound(_python_to_nbt(block[2]))}
            )

    entities = []
    for x, y, z, identifier, yaw in structure.entities:
        entities.append(
            compound(
                {
                    "blockPos": list_tag(
                        TAG_INT,
                        [int(math.floor(x)), int(math.floor(y)), int(math.floor(z))],
                    ),
                    "pos": list_tag(TAG_FLOAT, [x, y, z]),
                    "nbt": compound(
                        {
                            "identifier": string(identifier),
                            "Pos": list_tag(TAG_FLOAT, [x, y, z]),
                            "Rotation": list_tag(TAG_FLOAT, [yaw, 0.0]),
                            "OnGround": byte(1),
                        }
                    ),
                }
            )
        )

    root = {
        "format_version": integer(1),
        "size": list_tag(TAG_INT, list(structure.size)),
        "structure": compound(
            {
                "block_indices": list_tag(
                    TAG_LIST,
                    [
                        list_tag(TAG_INT, primary),
                        list_tag(TAG_INT, [-1] * volume),
                    ],
                ),
                "entities": list_tag(TAG_COMPOUND, entities),
                "palette": compound(
                    {
                        "default": compound(
                            {
                                "block_palette": list_tag(TAG_COMPOUND, palette),
                                "block_position_data": compound(block_position_data),
                            }
                        )
                    }
                ),
            }
        ),
        "structure_world_origin": list_tag(TAG_INT, [0, 0, 0]),
    }
    write_nbt(path, root)


_CUSTOM_BLOCK_STATE_SCHEMAS = None


def _custom_block_state_schemas():
    global _CUSTOM_BLOCK_STATE_SCHEMAS
    if _CUSTOM_BLOCK_STATE_SCHEMAS is not None:
        return _CUSTOM_BLOCK_STATE_SCHEMAS
    schemas = {}
    for block_path in (BP / "netease_blocks").glob("*.json"):
        with block_path.open("r", encoding="utf-8") as handle:
            block = json.load(handle).get("minecraft:block", {})
        description = block.get("description", {})
        identifier = description.get("identifier")
        if isinstance(identifier, str) and identifier.startswith("tf_slice:"):
            schemas[identifier] = description.get("states", {})
    _CUSTOM_BLOCK_STATE_SCHEMAS = schemas
    return schemas


def _validate_custom_block_states(identifier, states, structure_name):
    if not identifier.startswith("tf_slice:"):
        return
    declared = _custom_block_state_schemas().get(identifier)
    if declared is None:
        raise ValueError(
            "unregistered custom block %s in %s"
            % (identifier, structure_name)
        )
    for state_name, state_value in states.items():
        if state_name not in declared:
            raise ValueError(
                "undeclared custom state %s on %s in %s"
                % (state_name, identifier, structure_name)
            )
        if state_value not in declared[state_name]:
            raise ValueError(
                "invalid custom state value %r for %s on %s in %s"
                % (state_value, state_name, identifier, structure_name)
            )


def _render_safe_structure_proxy(name):
    """Return an engine-placeable proxy that changes no world blocks.

    NetEase 3.8 can forward a rejected structure feature into the client
    tessellator. A nominally empty mcstructure (empty palette with only a
    ``-1`` block index) then has no material to bake and can terminate the
    native client. ``minecraft:structure_void`` is the format's explicit
    non-replacing block, so it keeps the proxy a no-op while giving the
    engine a real palette entry.

    Structure void remains forbidden through ``SparseStructure.set`` for
    authored ruins. Only these dedicated worldgen proxies may contain it.
    """
    proxy = SparseStructure((1, 1, 1), name)
    proxy.blocks[(0, 0, 0)] = (
        "minecraft:structure_void",
        {},
        {},
    )
    return proxy


def _python_to_nbt(value):
    result = {}
    for key, item in value.items():
        if isinstance(item, bool):
            result[str(key)] = byte(1 if item else 0)
        elif isinstance(item, int):
            result[str(key)] = integer(item)
        elif isinstance(item, str):
            result[str(key)] = string(item)
        elif isinstance(item, dict):
            result[str(key)] = compound(_python_to_nbt(item))
    return result


def loot_table_path(loot_id):
    return "loot_tables/chests/tf_slice/%s.json" % loot_id


def set_loot_container(
    structure,
    x,
    y,
    z,
    loot_id,
    block="minecraft:chest",
    states=None,
):
    block_entity_id = "Barrel" if block == "minecraft:barrel" else "Chest"
    structure.set(
        x,
        y,
        z,
        block,
        states,
        block_entity={
            "id": block_entity_id,
            "LootTable": loot_table_path(loot_id),
            "LootTableSeed": 0,
        },
    )


def set_spawner(structure, x, y, z, entity_id):
    structure.set(
        x,
        y,
        z,
        "minecraft:mob_spawner",
        block_entity={
            "id": "MobSpawner",
            "EntityIdentifier": entity_id,
            "Delay": 20,
            "MinSpawnDelay": 200,
            "MaxSpawnDelay": 800,
            "SpawnCount": 2,
            "MaxNearbyEntities": 6,
            "RequiredPlayerRange": 16,
            "SpawnRange": 4,
        },
    )


def _default_template_loot(template_name):
    if "well" in template_name:
        return "well"
    if "druid" in template_name or "basement" in template_name:
        return "druid_hut"
    if "grave" in template_name:
        return "graveyard"
    return None


def _default_template_spawner(template_name):
    if "druid" in template_name or "basement" in template_name:
        return "tf_slice:skeleton_druid"
    if "grave" in template_name:
        return "tf_slice:rising_zombie"
    return None


def _bedrock_block(java_name, properties):
    properties = dict(properties or {})
    if java_name == "minecraft:repeater":
        target_name = (
            "minecraft:powered_repeater"
            if properties.get("powered") == "true"
            else "minecraft:unpowered_repeater"
        )
        target_states = {}
    elif java_name == "minecraft:redstone_wall_torch":
        target_name = (
            "minecraft:unlit_redstone_torch"
            if properties.get("lit") == "false"
            else "minecraft:redstone_torch"
        )
        target_states = {}
    elif java_name == "minecraft:piston_head":
        target_name = (
            "minecraft:sticky_piston_arm_collision"
            if properties.get("type") == "sticky"
            else "minecraft:piston_arm_collision"
        )
        target_states = {}
    else:
        target_name = None
        target_states = None
    explicit = {
        "minecraft:grass_block": ("minecraft:grass_block", {}),
        "minecraft:bricks": ("minecraft:brick_block", {}),
        "minecraft:cobblestone_stairs": ("minecraft:stone_stairs", {}),
        "minecraft:cobweb": ("minecraft:web", {}),
        "minecraft:magma_block": ("minecraft:magma", {}),
        "minecraft:oak_trapdoor": ("minecraft:trapdoor", {}),
        "minecraft:potted_dead_bush": ("minecraft:flower_pot", {}),
        "minecraft:tripwire": ("minecraft:stone_pressure_plate", {}),
        "minecraft:oak_planks": ("minecraft:oak_planks", {}),
        "minecraft:spruce_planks": ("minecraft:spruce_planks", {}),
        "minecraft:stone_bricks": ("minecraft:stone_bricks", {}),
        "minecraft:mossy_stone_bricks": (
            "minecraft:mossy_stone_bricks",
            {},
        ),
        "minecraft:cracked_stone_bricks": (
            "minecraft:cracked_stone_bricks",
            {},
        ),
        "minecraft:chiseled_stone_bricks": (
            "minecraft:chiseled_stone_bricks",
            {},
        ),
        "minecraft:oak_slab": ("minecraft:oak_slab", {}),
        "minecraft:spruce_slab": ("minecraft:spruce_slab", {}),
        "minecraft:oak_fence": ("minecraft:oak_fence", {}),
        "minecraft:oak_door": ("minecraft:wooden_door", {}),
        "minecraft:oak_sign": ("minecraft:standing_sign", {}),
        "minecraft:oak_wall_sign": ("minecraft:wall_sign", {}),
        "twilightforest:twilight_oak_log": ("tf_slice:twilight_oak_log", {}),
        "twilightforest:twilight_oak_wood": ("tf_slice:twilight_oak_log", {}),
        "twilightforest:twilight_oak_leaves": ("tf_slice:twilight_oak_leaves", {}),
        "twilightforest:canopy_log": ("tf_slice:canopy_log", {}),
        "twilightforest:canopy_wood": ("tf_slice:canopy_log", {}),
        "twilightforest:canopy_leaves": ("tf_slice:canopy_leaves", {}),
        "twilightforest:canopy_fence": (
            "minecraft:cherry_fence",
            {},
        ),
        "twilightforest:dark_fence": ("minecraft:dark_oak_fence", {}),
        "twilightforest:oak_banister": (
            "minecraft:oak_fence",
            {},
        ),
        "twilightforest:iron_ladder": ("minecraft:ladder", {}),
        "twilightforest:wither_skeleton_skull_candle": (
            "minecraft:black_candle",
            {},
        ),
        "twilightforest:root": ("tf_slice:root_block", {}),
        "twilightforest:liveroot_block": ("tf_slice:liveroot_block", {}),
        "twilightforest:mangrove_root": ("minecraft:mangrove_roots", {}),
        "twilightforest:firefly": ("tf_slice:firefly", {}),
        "twilightforest:cicada": ("minecraft:glowstone", {}),
        "twilightforest:firefly_jar": ("tf_slice:firefly_jar", {}),
        "twilightforest:hedge": ("tf_slice:hedge", {}),
        "twilightforest:mazestone": ("tf_slice:mazestone", {}),
        "twilightforest:mazestone_mosaic": (
            "tf_slice:mazestone_mosaic",
            {},
        ),
        "twilightforest:nagastone": ("tf_slice:nagastone", {}),
        "twilightforest:etched_nagastone": (
            "tf_slice:etched_nagastone",
            {},
        ),
        "twilightforest:nagastone_pillar": (
            "tf_slice:nagastone_pillar",
            {},
        ),
        "twilightforest:nagastone_head": (
            "tf_slice:nagastone_head",
            {},
        ),
        "twilightforest:nagastone_stairs_left": (
            "tf_slice:nagastone_stairs_left",
            {},
        ),
        "twilightforest:nagastone_stairs_right": (
            "tf_slice:nagastone_stairs_right",
            {},
        ),
        "twilightforest:spiral_bricks": (
            "tf_slice:spiral_bricks",
            {},
        ),
        "twilightforest:boss_spawner": (
            "tf_slice:naga_boss_spawner",
            {},
        ),
        "twilightforest:candelabra": ("minecraft:lantern", {}),
    }
    if target_name is not None:
        states = dict(target_states)
    elif java_name in explicit:
        target_name, target_states = explicit[java_name]
        states = dict(target_states)
    elif java_name in DIRECT_BEDROCK_BLOCKS:
        target_name = java_name
        states = {}
    else:
        raise ValueError("unmapped Java block %s" % java_name)

    axis = properties.get("axis")
    axis_variants = STATELESS_AXIS_BLOCKS.get(target_name)
    if axis_variants is not None and axis in axis_variants:
        target_name = axis_variants[axis]

    if target_name == "tf_slice:nagastone":
        states["tf_slice:variant"] = properties.get("variant", "solid")
    elif target_name in (
        "tf_slice:etched_nagastone",
        "tf_slice:nagastone_head",
    ):
        states["tf_slice:facing"] = properties.get(
            "facing",
            "down" if target_name.endswith("etched_nagastone") else "north",
        )
    elif target_name == "tf_slice:nagastone_pillar":
        states["tf_slice:axis"] = properties.get("axis", "y")
        states["tf_slice:reversed"] = (
            properties.get("reversed") == "true"
        )
    elif target_name in (
        "tf_slice:nagastone_stairs_left",
        "tf_slice:nagastone_stairs_right",
    ):
        states["tf_slice:facing"] = properties.get("facing", "north")
        states["tf_slice:half"] = properties.get("half", "bottom")
        states["tf_slice:shape"] = properties.get("shape", "straight")

    if (
        target_name not in STATELESS_COURTYARD_BLOCKS
        and target_name not in STATELESS_AXIS_BLOCK_IDS
    ):
        if (
            axis in ("x", "y", "z")
            and target_name != "tf_slice:nagastone_pillar"
        ):
            states["pillar_axis"] = axis
        if properties.get("type") in ("top", "bottom"):
            states["top_slot_bit"] = properties["type"] == "top"
        if properties.get("waterlogged") == "true":
            states["waterlogged_bit"] = True
        facing = properties.get("facing")
        if target_name == "minecraft:vine":
            vine_bits = 0
            for side, bit_value in (
                ("south", 1),
                ("west", 2),
                ("north", 4),
                ("east", 8),
            ):
                if properties.get(side) == "true":
                    vine_bits |= bit_value
            states["vine_direction_bits"] = vine_bits
        if target_name.endswith("_wall"):
            connection_values = {
                "none": "none",
                "low": "short",
                "tall": "tall",
            }
            for side in ("east", "north", "south", "west"):
                connection = properties.get(side)
                if connection in connection_values:
                    states[
                        "wall_connection_type_%s" % side
                    ] = connection_values[connection]
            if "up" in properties:
                states["wall_post_bit"] = properties.get("up") == "true"
        if target_name.endswith("_stairs") and facing in STAIR_DIRECTIONS:
            states["weirdo_direction"] = STAIR_DIRECTIONS[facing]
            states["upside_down_bit"] = properties.get("half") == "top"
        if target_name in (
            "minecraft:barrel",
            "minecraft:chest",
            "minecraft:dispenser",
            "minecraft:hopper",
            "minecraft:ladder",
            "minecraft:piston",
            "minecraft:sticky_piston",
        ) and facing in FACING_DIRECTIONS:
            states["facing_direction"] = FACING_DIRECTIONS[facing]
        if target_name == "minecraft:barrel":
            states["open_bit"] = properties.get("open") == "true"
        if target_name == "minecraft:dispenser":
            states["triggered_bit"] = properties.get("triggered") == "true"
        if target_name == "minecraft:hopper":
            states["toggle_bit"] = properties.get("enabled") == "false"
        if target_name in (
            "minecraft:spruce_door",
            "minecraft:wooden_door",
        ):
            if facing in CARDINAL_DIRECTIONS:
                states["direction"] = CARDINAL_DIRECTIONS[facing]
            states["door_hinge_bit"] = properties.get("hinge") == "right"
            states["open_bit"] = properties.get("open") == "true"
            states["upper_block_bit"] = properties.get("half") == "upper"
        if target_name == "minecraft:tripwire_hook":
            if facing in CARDINAL_DIRECTIONS:
                states["direction"] = CARDINAL_DIRECTIONS[facing]
            states["attached_bit"] = properties.get("attached") == "true"
            states["powered_bit"] = properties.get("powered") == "true"
        if target_name == "minecraft:vine":
            vine_bits = 0
            for property_name, bit in (
                ("south", 1),
                ("west", 2),
                ("north", 4),
                ("east", 8),
            ):
                if properties.get(property_name) == "true":
                    vine_bits |= bit
            states["vine_direction_bits"] = vine_bits
        if target_name == "minecraft:trapdoor":
            if facing in CARDINAL_DIRECTIONS:
                states["direction"] = CARDINAL_DIRECTIONS[facing]
            states["open_bit"] = properties.get("open") == "true"
            states["upside_down_bit"] = properties.get("half") == "top"
        if target_name in (
            "minecraft:powered_repeater",
            "minecraft:unpowered_repeater",
        ):
            if facing in CARDINAL_DIRECTIONS:
                states["direction"] = CARDINAL_DIRECTIONS[facing]
            if "delay" in properties:
                states["repeater_delay"] = int(properties["delay"])
        if target_name in (
            "minecraft:redstone_torch",
            "minecraft:unlit_redstone_torch",
        ) and facing in CARDINAL_DIRECTIONS:
            states["torch_facing_direction"] = facing
        if target_name in (
            "minecraft:piston_arm_collision",
            "minecraft:sticky_piston_arm_collision",
        ) and facing in FACING_DIRECTIONS:
            states["facing_direction"] = FACING_DIRECTIONS[facing]
    return target_name, states


def _uses_original_template_weathering(path):
    normalized = str(path).replace("\\", "/")
    return (
        "/feature/druid_hut/" in normalized
        or "/feature/well/" in normalized
    )


def _weathered_java_name(path, java_name, position):
    replacement = TEMPLATE_WEATHERING.get(java_name)
    if replacement is None or not _uses_original_template_weathering(path):
        return java_name
    fingerprint = "%s:%s:%d,%d,%d" % (
        str(path).replace("\\", "/"),
        java_name,
        int(position[0]),
        int(position[1]),
        int(position[2]),
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).digest()
    # Upstream's RuleProcessor uses a 0.5 random_block_match predicate. A
    # position-stable coin gives exported templates the same distribution
    # without changing between builds.
    return replacement if ord(digest[:1]) < 128 else java_name


def java_template(path, name):
    source = read_java_nbt(path)
    size = tuple(source["size"])
    result = SparseStructure(size, name)
    palette = source.get("palette")
    if palette is None:
        palettes = source.get("palettes", [])
        if not palettes:
            raise ValueError("template %s has no palette" % path)
        palette = palettes[0]

    converted_palette = []
    for block in palette:
        if block["Name"] in FORBIDDEN_OUTPUT_BLOCKS:
            converted_palette.append(None)
        else:
            converted_palette.append(
                _bedrock_block(block["Name"], block.get("Properties", {}))
            )

    for block in source.get("blocks", []):
        java_name = palette[block["state"]]["Name"]
        if java_name in ("minecraft:structure_void", "minecraft:jigsaw"):
            continue
        x, y, z = block["pos"]
        if java_name == "minecraft:structure_block":
            metadata = str(block.get("nbt", {}).get("metadata", "")).lower()
            if "spawner" in metadata:
                target = ("minecraft:mob_spawner", {})
            elif "chest" in metadata or "loot" in metadata:
                target = ("minecraft:chest", {})
            elif "trap" in metadata:
                target = ("minecraft:tnt", {})
            else:
                continue
        else:
            weathered_name = _weathered_java_name(
                path,
                java_name,
                (x, y, z),
            )
            if weathered_name == java_name:
                target = converted_palette[block["state"]]
            else:
                target = _bedrock_block(
                    weathered_name,
                    palette[block["state"]].get("Properties", {}),
                )
        block_entity = {}
        if target[0] in ("minecraft:chest", "minecraft:trapped_chest", "minecraft:barrel"):
            loot_id = _default_template_loot(name)
            if loot_id is not None:
                block_entity = {
                    "id": "Barrel" if target[0] == "minecraft:barrel" else "Chest",
                    "LootTable": loot_table_path(loot_id),
                    "LootTableSeed": 0,
                }
        elif target[0] == "minecraft:mob_spawner":
            entity_id = _default_template_spawner(name)
            if entity_id is not None:
                block_entity = {
                    "id": "MobSpawner",
                    "EntityIdentifier": entity_id,
                    "Delay": 20,
                }
        result.set(x, y, z, target[0], target[1], block_entity)
    return result


def quest_grove():
    """Convert the upstream grove and resolve its two data markers."""
    path = JAVA_STRUCTURES / "quest_grove.nbt"
    result = java_template(path, "quest_grove")
    source = read_java_nbt(path)
    palette = source.get("palette", [])
    for block in source.get("blocks", []):
        palette_entry = palette[block["state"]]
        if palette_entry.get("Name") != "minecraft:structure_block":
            continue
        x, y, z = block["pos"]
        metadata = str(block.get("nbt", {}).get("metadata", "")).lower()
        if metadata == "quest_ram":
            result.add_entity(
                x + 0.5,
                y,
                z + 0.5,
                "tf_slice:quest_ram",
            )
        elif metadata == "dispenser":
            result.set(
                x,
                y,
                z,
                "minecraft:dispenser",
                block_entity={
                    "id": "Dispenser",
                    "LootTable": "loot_tables/chests/quest_grove_dropper.json",
                    "LootTableSeed": 0,
                },
            )
    return result


def monolith(seed):
    height = 10 + seed % 10
    result = SparseStructure((2, height, 2), "monolith_%02d" % seed)
    heights = [height, (height * 3) // 4, (height * 3) // 4, height // 2]
    positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
    rotation = seed % 4
    heights = heights[rotation:] + heights[:rotation]
    for index, (x, z) in enumerate(positions):
        for y in range(heights[index]):
            block = "minecraft:obsidian"
            if heights[index] == height and y == height - 1:
                block = "minecraft:lapis_block"
            result.set(x, y, z, block)
    result.add_entity(0.25, 1.0, 0.25, "tf_slice:raven", seed * 37.0)
    result.add_entity(1.25, 1.0, 1.25, "tf_slice:raven", seed * 37.0 + 180.0)
    return result


def foundation(seed):
    rng = random.Random(0xF00D + seed)
    size_x = 6 + rng.randrange(5)
    size_z = 6 + rng.randrange(5)
    result = SparseStructure((size_x, 7, size_z), "foundation_%02d" % seed)
    palette = [
        "minecraft:cobblestone",
        "minecraft:cobblestone",
        "minecraft:mossy_cobblestone",
    ]
    for x in range(size_x):
        for z in range(size_z):
            if x in (0, size_x - 1) or z in (0, size_z - 1):
                height = 1 + rng.randrange(4)
                for y in range(height):
                    result.set(x, y + 2, z, rng.choice(palette))
            elif seed % 3 != 0:
                result.set(
                    x,
                    2,
                    z,
                    "minecraft:oak_planks",
                )
    if seed % 2 == 0:
        for x in range(1, size_x - 1):
            for z in range(1, size_z - 1):
                result.set(x, 0, z, "minecraft:air")
                result.set(x, 1, z, "minecraft:air")
        set_loot_container(
            result,
            size_x // 2,
            0,
            size_z // 2,
            "foundation_basement",
        )
    return result


def stalagmite(length):
    radius = max(0, int(math.floor(length / 4.5)))
    diameter = radius * 2 + 1
    result = SparseStructure((diameter, length, diameter), "stalagmite_%02d" % length)
    center = radius
    for y in range(length):
        layer_radius = int(round(radius * (1.0 - float(y) / max(1, length))))
        for x in range(diameter):
            for z in range(diameter):
                if (x - center) ** 2 + (z - center) ** 2 <= layer_radius ** 2:
                    result.set(x, y, z, "minecraft:stone")
    return result


def _face_connected_line(start, end):
    """Return a straight-looking voxel path with face-adjacent steps."""
    current = [int(value) for value in start]
    target = [int(value) for value in end]
    delta = [target[index] - current[index] for index in range(3)]
    totals = [abs(value) for value in delta]
    moved = [0, 0, 0]
    directions = [1 if value > 0 else -1 for value in delta]
    points = [tuple(current)]
    axis_priority = {1: 0, 0: 1, 2: 2}
    while current != target:
        candidates = [
            axis for axis in range(3) if moved[axis] < totals[axis]
        ]
        axis = min(
            candidates,
            key=lambda item: (
                float(moved[item] + 1) / float(totals[item]),
                axis_priority[item],
            ),
        )
        current[axis] += directions[axis]
        moved[axis] += 1
        points.append(tuple(current))
    return points


def _add_hollow_root_rings(result, center, radius, surface_y, seed):
    """Approximate the source terrain-aware roots on a flat surface plane."""
    rng = random.Random(0xA601 + int(seed))
    for branch_height, height_variance, length, tilt in HOLLOW_ROOT_RING_SPECS:
        root_count = 4 + rng.randrange(2)
        angle_offset = rng.random() * math.pi * 2.0
        horizontal_length = math.sin(math.pi * tilt) * length
        vertical_drop = int(round(math.cos(math.pi * tilt) * length))
        for root_index in range(root_count):
            angle = (
                angle_offset
                + root_index * (math.pi * 2.0 / float(root_count))
            )
            root_height = (
                branch_height
                - height_variance
                + rng.randrange(height_variance * 2)
            )
            start = (
                int(round(center + math.sin(angle) * radius)),
                int(surface_y + root_height),
                int(round(center + math.cos(angle) * radius)),
            )
            end = (
                int(round(start[0] + math.sin(angle) * horizontal_length)),
                int(start[1] + vertical_drop),
                int(round(start[2] + math.cos(angle) * horizontal_length)),
            )
            for x, y, z in _face_connected_line(start, end):
                result.set(
                    x,
                    y,
                    z,
                    (
                        "tf_slice:twilight_oak_log"
                        if y >= surface_y
                        else "tf_slice:root_block"
                    ),
                )


def hollow_stump(seed):
    rng = random.Random(0x51A7 + seed)
    radius = 2 + seed % 2
    size = 15
    surface_y = HOLLOW_ROOT_SUBSURFACE_DEPTH
    result = SparseStructure(
        (size, surface_y + 6, size),
        "hollow_stump_%02d" % seed,
    )
    center = size // 2
    for x in range(size):
        for z in range(size):
            distance = math.sqrt((x - center) ** 2 + (z - center) ** 2)
            if distance <= radius + 0.25:
                for depth in range(1, HOLLOW_TRUNK_SUBSURFACE_DEPTH + 1):
                    result.set(
                        x,
                        surface_y - depth,
                        z,
                        "tf_slice:root_block",
                    )
            if radius - 0.8 <= distance <= radius + 0.35:
                height = 2 + rng.randrange(4)
                for y in range(height):
                    result.set(
                        x,
                        surface_y + y,
                        z,
                        "tf_slice:twilight_oak_log",
                    )
    _add_hollow_root_rings(result, center, radius, surface_y, seed)
    return result


def fallen_log(seed):
    length = 9
    result = SparseStructure((length, 5, 5), "fallen_log_%02d" % seed)
    for x in range(length):
        for y in range(1, 5):
            for z in range(5):
                outer = y in (1, 4) or z in (0, 4)
                inner = y in (2, 3) and z in (1, 2, 3)
                if outer:
                    result.set(
                        x,
                        y,
                        z,
                        "tf_slice:twilight_oak_log_x",
                    )
                elif inner:
                    result.set(x, y, z, "minecraft:air")
        if (x + seed) % 3 == 0:
            result.set(x, 0, 0, "minecraft:moss_block")
            result.set(x, 4, 4, "minecraft:oak_leaves")
    result.set(length // 2, 3, 0, "minecraft:glowstone")
    return result


def hollow_tree(seed, include_dungeon=False):
    rng = random.Random(0x7EEE + seed)
    radius = 2 + seed % 3
    height = 30 + seed % 8
    surface_y = HOLLOW_ROOT_SUBSURFACE_DEPTH
    # The upstream tree is a real multi-chunk feature: its crown is assembled
    # from branch rings and can extend well beyond the hollow trunk. Keep a
    # stable 33x33 envelope for the engine-owned native feature. The catalog
    # also keeps 16x16 tiles for explicit manual/debug placement.
    size = 33
    center = size // 2
    result = SparseStructure(
        (size, surface_y + height + 10, size),
        "hollow_tree_%02d" % seed,
    )

    def set_log(x, y, z):
        result.set(x, y, z, "tf_slice:twilight_oak_log")

    def set_leaf(x, y, z):
        existing = result.blocks.get((x, y, z))
        if existing is None or existing[0] == "minecraft:air":
            result.set(x, y, z, "tf_slice:twilight_oak_leaves")

    def branch(start, end):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dz = end[2] - start[2]
        steps = max(abs(dx), abs(dy), abs(dz), 1)
        points = []
        for index in range(steps + 1):
            amount = float(index) / float(steps)
            point = (
                int(round(start[0] + dx * amount)),
                int(round(start[1] + dy * amount)),
                int(round(start[2] + dz * amount)),
            )
            set_log(*point)
            points.append(point)
        return points

    def leaf_blob(cx, cy, cz, horizontal_radius, vertical_radius):
        horizontal_radius = int(horizontal_radius)
        vertical_radius = int(vertical_radius)
        for x in range(cx - horizontal_radius, cx + horizontal_radius + 1):
            for y in range(cy - vertical_radius, cy + vertical_radius + 1):
                for z in range(cz - horizontal_radius, cz + horizontal_radius + 1):
                    distance = (
                        ((x - cx) / float(horizontal_radius + 0.35)) ** 2
                        + ((y - cy) / float(vertical_radius + 0.35)) ** 2
                        + ((z - cz) / float(horizontal_radius + 0.35)) ** 2
                    )
                    if distance <= 1.0:
                        set_leaf(x, y, z)

    def branch_ring(y, count, length, angle_offset, rise, leaf_radius):
        for branch_index in range(count):
            angle = (
                angle_offset
                + branch_index * (math.pi * 2.0 / float(count))
            )
            end = (
                int(round(center + math.cos(angle) * length)),
                y + rise + (branch_index % 2),
                int(round(center + math.sin(angle) * length)),
            )
            branch((center, y, center), end)
            leaf_blob(
                end[0],
                end[1],
                end[2],
                leaf_radius,
                max(2, leaf_radius - 1),
            )

    for depth in range(1, HOLLOW_TRUNK_SUBSURFACE_DEPTH + 1):
        y = surface_y - depth
        for x in range(size):
            for z in range(size):
                distance = math.sqrt((x - center) ** 2 + (z - center) ** 2)
                if distance <= radius + 0.25:
                    result.set(x, y, z, "tf_slice:root_block")

    for trunk_y in range(height):
        y = surface_y + trunk_y
        for x in range(size):
            for z in range(size):
                distance = math.sqrt((x - center) ** 2 + (z - center) ** 2)
                if radius - 0.85 <= distance <= radius + 0.25:
                    set_log(x, y, z)
                elif distance < radius - 0.85:
                    result.set(x, y, z, "minecraft:air")

    # Taper the top into a solid crown support instead of leaving a flat,
    # sawn-off cylinder.
    for y in range(surface_y + height, surface_y + height + 5):
        top_radius = max(1, radius - (y - surface_y - height) // 2)
        for x in range(center - top_radius, center + top_radius + 1):
            for z in range(center - top_radius, center + top_radius + 1):
                if (x - center) ** 2 + (z - center) ** 2 <= top_radius ** 2:
                    set_log(x, y, z)

    # The source traces two rings of roots through the live terrain, using
    # wood while exposed and root blocks after entering soil.  A structure
    # cannot inspect each destination block, so model the same transition
    # against this template's explicit flat surface plane.
    _add_hollow_root_rings(result, center, radius, surface_y, seed)

    # Source-style full crown: several offset branch rings plus smaller side
    # branches. Every leaf blob grows around an actual branch endpoint.
    branch_ring(surface_y + height - 8, 5, 8, 0.35, 3, 3)
    branch_ring(surface_y + height - 4, 8, 10, 0.0, 3, 4)
    branch_ring(surface_y + height, 8, 8, math.pi / 8.0, 2, 4)
    branch_ring(surface_y + height + 3, 5, 6, 0.7, 1, 3)
    leaf_blob(center, surface_y + height + 5, center, radius + 3, 3)

    for side_index in range(3 + rng.randrange(3)):
        angle = rng.random() * math.pi * 2.0
        branch_y = surface_y + rng.randrange(max(8, height // 3), height - 10)
        length = 5 + rng.randrange(3)
        end = (
            int(round(center + math.cos(angle) * length)),
            branch_y + 2 + rng.randrange(3),
            int(round(center + math.sin(angle) * length)),
        )
        branch(
            (
                int(round(center + math.cos(angle) * radius)),
                branch_y,
                int(round(center + math.sin(angle) * radius)),
            ),
            end,
        )
        leaf_blob(end[0], end[1], end[2], 2, 2)

    if include_dungeon:
        dungeon_angle = (seed % 4) * math.pi / 2.0
        branch_y = surface_y + height - 10
        dungeon_center = (
            int(round(center + math.cos(dungeon_angle) * 9)),
            branch_y + 3,
            int(round(center + math.sin(dungeon_angle) * 9)),
        )
        dungeon_branch = branch(
            (
                int(round(center + math.cos(dungeon_angle) * radius)),
                branch_y,
                int(round(center + math.sin(dungeon_angle) * radius)),
            ),
            dungeon_center,
        )
        leaf_blob(
            dungeon_center[0],
            dungeon_center[1],
            dungeon_center[2],
            5,
            4,
        )
        for x in range(dungeon_center[0] - 2, dungeon_center[0] + 3):
            for y in range(dungeon_center[1] - 2, dungeon_center[1] + 3):
                for z in range(dungeon_center[2] - 2, dungeon_center[2] + 3):
                    distance = math.sqrt(
                        (x - dungeon_center[0]) ** 2
                        + ((y - dungeon_center[1]) * 1.25) ** 2
                        + (z - dungeon_center[2]) ** 2
                    )
                    if distance <= 2.1:
                        result.set(x, y, z, "minecraft:air")
        # Restore the approach only as far as the leaf shell, keeping the
        # dungeon chamber open while physically attaching it to the trunk.
        for point in dungeon_branch[:-3]:
            set_log(*point)
        for x in range(dungeon_center[0] - 5, dungeon_center[0] + 6):
            for y in range(dungeon_center[1] - 4, dungeon_center[1] + 5):
                for z in range(dungeon_center[2] - 5, dungeon_center[2] + 6):
                    distance = math.sqrt(
                        (x - dungeon_center[0]) ** 2
                        + ((y - dungeon_center[1]) * 1.25) ** 2
                        + (z - dungeon_center[2]) ** 2
                    )
                    if 2.1 < distance <= 4.6:
                        set_leaf(x, y, z)
        set_spawner(
            result,
            dungeon_center[0],
            dungeon_center[1],
            dungeon_center[2],
            "tf_slice:swarm_spider",
        )
        set_loot_container(
            result,
            dungeon_center[0] + 2,
            dungeon_center[1] - 1,
            dungeon_center[2],
            "tree_cache",
        )
    return result


def graveyard_structure():
    base = java_template(
        JAVA_STRUCTURES / "feature" / "graveyard" / "graveyard.nbt",
        "graveyard",
    )
    for index, (x, z, template_name) in enumerate(
        [
            (2, 2, "grave_full.nbt"),
            (10, 2, "grave_upper.nbt"),
            (2, 10, "grave_lower.nbt"),
            (10, 10, "grave_trap.nbt"),
        ]
    ):
        grave = java_template(
            JAVA_STRUCTURES / "feature" / "graveyard" / template_name,
            "grave_%d" % index,
        )
        base.merge(grave, (x, 0, z))
    # The Java graveyard is wider than a Bedrock native feature cell. Keep the
    # source-accurate western 16-block section so it can use the native feature
    # pipeline without crossing an unloaded chunk.
    base = base.crop(
        0,
        0,
        min(16, base.size[0]),
        min(16, base.size[2]),
        "graveyard",
    )
    set_loot_container(
        base,
        max(0, base.size[0] // 2 - 1),
        1,
        base.size[2] // 2,
        "graveyard",
    )
    set_spawner(
        base,
        base.size[0] // 2,
        1,
        base.size[2] // 2,
        "tf_slice:rising_zombie",
    )
    return base


def _maze_edges(cell_count, seed):
    rng = random.Random(seed)
    visited = {(0, 0)}
    stack = [(0, 0)]
    open_edges = set()
    while stack:
        x, z = stack[-1]
        neighbors = []
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            target = (x + dx, z + dz)
            if (
                0 <= target[0] < cell_count
                and 0 <= target[1] < cell_count
                and target not in visited
            ):
                neighbors.append(target)
        if not neighbors:
            stack.pop()
            continue
        target = rng.choice(neighbors)
        open_edges.add(tuple(sorted(((x, z), target))))
        visited.add(target)
        stack.append(target)
    return open_edges


def hedge_maze(seed):
    size = 50
    cells = 16
    result = SparseStructure((size, 6, size), "hedge_maze")
    edges = _maze_edges(cells, 0x48454447 + seed)
    for x in range(size):
        for z in range(size):
            result.set(x, 0, z, "minecraft:grass_block")
    for grid_x in range(cells + 1):
        world_x = min(size - 1, 1 + grid_x * 3)
        for z in range(1, size - 1):
            cell_z = min(cells - 1, max(0, (z - 1) // 3))
            left = grid_x - 1
            right = grid_x
            edge = tuple(sorted(((left, cell_z), (right, cell_z))))
            boundary = grid_x in (0, cells)
            if boundary or edge not in edges:
                for y in range(1, 4):
                    result.set(world_x, y, z, "tf_slice:hedge")
                result.set(world_x, 0, z, "tf_slice:mazestone")
    for grid_z in range(cells + 1):
        world_z = min(size - 1, 1 + grid_z * 3)
        for x in range(1, size - 1):
            cell_x = min(cells - 1, max(0, (x - 1) // 3))
            above = grid_z - 1
            below = grid_z
            edge = tuple(sorted(((cell_x, above), (cell_x, below))))
            boundary = grid_z in (0, cells)
            if boundary or edge not in edges:
                for y in range(1, 4):
                    result.set(x, y, world_z, "tf_slice:hedge")
                result.set(x, 0, world_z, "tf_slice:mazestone")
    # TFMaze.add4Exits removes the two corridor blocks between the center
    # pillars.  The outer hedge walls are at coordinates 1 and size - 1,
    # rather than at the low-side structure edge.
    entrance_span = (size // 2 + 1, size // 2 + 2)
    entrance_corridors = (
        (entrance_span, range(0, 4)),
        (entrance_span, range(size - 3, size)),
        (range(0, 4), entrance_span),
        (range(size - 3, size), entrance_span),
    )
    for xs, zs in entrance_corridors:
        for x in xs:
            for z in zs:
                for y in range(1, 4):
                    result.set(x, y, z, "minecraft:air")
    for xs, zs in (
        (entrance_span, (1, size - 1)),
        ((1, size - 1), entrance_span),
    ):
        for x in xs:
            for z in zs:
                result.set(x, 0, z, "minecraft:grass_block")
    rooms = [(4, 4), (12, 4), (25, 25), (37, 13), (40, 40)]
    for index, (x, z) in enumerate(rooms):
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                for y in range(1, 4):
                    result.set(x + dx, y, z + dz, "minecraft:air")
        maze_mobs = (
            "tf_slice:hedge_spider",
            "tf_slice:swarm_spider",
            "tf_slice:hostile_wolf",
        )
        set_spawner(result, x, 1, z, maze_mobs[index % len(maze_mobs)])
        set_loot_container(result, x + 1, 1, z, "hedge_maze")
        if index == seed % 5:
            set_loot_container(result, x - 1, 1, z, "hedge_maze")

    # TFMaze uses the dedicated firefly block for maze lights.  Attach a
    # deterministic selection to hedge faces that border open corridors.
    light_rng = random.Random(0x46495245 + seed)
    light_candidates = []
    # The shared block model is authored for trees and mushrooms.  Maze
    # lights therefore select the face that points back toward the supporting
    # hedge instead of globally flipping the firefly geometry.
    facing_by_delta = {
        (1, 0): "west",
        (-1, 0): "east",
        (0, 1): "north",
        (0, -1): "south",
    }
    for (x, y, z), block in sorted(result.blocks.items()):
        if y != 2 or block[0] != "tf_slice:hedge":
            continue
        for (dx, dz), facing in facing_by_delta.items():
            target = (x + dx, y, z + dz)
            if (
                0 <= target[0] < size
                and 0 <= target[2] < size
                and result.blocks.get(target, ("minecraft:air",))[0]
                == "minecraft:air"
            ):
                light_candidates.append((target, facing))
    light_rng.shuffle(light_candidates)
    placed_lights = set()
    for target, facing in light_candidates:
        if len(placed_lights) >= 24:
            break
        if target in placed_lights or target in result.blocks:
            continue
        result.set(
            target[0],
            target[1],
            target[2],
            "tf_slice:firefly",
            {"tf_slice:facing": facing},
        )
        placed_lights.add(target)
    return result


COURTYARD_TEMPLATE_NAMES = (
    "courtyard_wall.nbt",
    "courtyard_wall_corner.nbt",
    "courtyard_wall_corner_decayed.nbt",
    "courtyard_wall_corner_inner.nbt",
    "courtyard_wall_corner_inner_decayed.nbt",
    "courtyard_wall_decayed.nbt",
    "courtyard_wall_padding.nbt",
    "courtyard_wall_padding_decayed.nbt",
    "hedge_between.nbt",
    "hedge_between_big.nbt",
    "hedge_corner.nbt",
    "hedge_corner_big.nbt",
    "hedge_end.nbt",
    "hedge_end_big.nbt",
    "hedge_end_pillar.nbt",
    "hedge_end_pillar_big.nbt",
    "hedge_intersection.nbt",
    "hedge_intersection_big.nbt",
    "hedge_line.nbt",
    "hedge_line_big.nbt",
    "hedge_t.nbt",
    "hedge_t_big.nbt",
    "hydra_statue.nbt",
    "pathway.nbt",
    "terrace_duct.nbt",
    "terrace_fire.nbt",
    "terrace_statue.nbt",
)

COURTYARD_FACINGS = (
    # bit, opposite, inverted, inverted-opposite, dx, dz
    (0b0001, 0b0100, 0b1110, 0b1011, 1, 0),
    (0b0010, 0b1000, 0b1101, 0b0111, 0, 1),
    (0b0100, 0b0001, 0b1011, 0b1110, -1, 0),
    (0b1000, 0b0010, 0b0111, 0b1101, 0, -1),
)


def _courtyard_templates():
    templates = {}
    for filename in COURTYARD_TEMPLATE_NAMES:
        templates[filename[:-4]] = java_template(
            JAVA_STRUCTURES / "courtyard" / filename,
            filename[:-4],
        )
    return templates


def _rotated_xz(x, z, rotation):
    rotation = int(rotation) % 4
    if rotation == 1:
        return -z, x
    if rotation == 2:
        return -x, -z
    if rotation == 3:
        return z, -x
    return x, z


def _rotated_states(states, rotation):
    states = dict(states or {})
    rotation = int(rotation) % 4
    if rotation % 2 and states.get("pillar_axis") in ("x", "z"):
        states["pillar_axis"] = (
            "z" if states["pillar_axis"] == "x" else "x"
        )
    if rotation % 2 and states.get("tf_slice:axis") in ("x", "z"):
        states["tf_slice:axis"] = (
            "z" if states["tf_slice:axis"] == "x" else "x"
        )
    stair_clockwise = {0: 2, 2: 1, 1: 3, 3: 0}
    facing_clockwise = {2: 5, 5: 3, 3: 4, 4: 2}
    cardinal_clockwise = {
        "north": "east",
        "east": "south",
        "south": "west",
        "west": "north",
    }
    for _ in range(rotation):
        if "weirdo_direction" in states:
            states["weirdo_direction"] = stair_clockwise[
                int(states["weirdo_direction"])
            ]
        if "direction" in states:
            states["direction"] = (int(states["direction"]) + 1) % 4
        if states.get("facing_direction") in facing_clockwise:
            states["facing_direction"] = facing_clockwise[
                states["facing_direction"]
            ]
        if states.get("torch_facing_direction") in cardinal_clockwise:
            states["torch_facing_direction"] = cardinal_clockwise[
                states["torch_facing_direction"]
            ]
        if states.get("cardinal_direction") in cardinal_clockwise:
            states["cardinal_direction"] = cardinal_clockwise[
                states["cardinal_direction"]
            ]
        if states.get("tf_slice:facing") in cardinal_clockwise:
            states["tf_slice:facing"] = cardinal_clockwise[
                states["tf_slice:facing"]
            ]
        custom_variant = states.get("tf_slice:variant")
        if isinstance(custom_variant, str) and "_" in custom_variant:
            side, suffix = custom_variant.split("_", 1)
            if side in cardinal_clockwise:
                states["tf_slice:variant"] = "%s_%s" % (
                    cardinal_clockwise[side],
                    suffix,
                )
        if "vine_direction_bits" in states:
            bits = int(states["vine_direction_bits"])
            states["vine_direction_bits"] = ((bits << 1) & 15) | (
                (bits >> 3) & 1
            )
        wall_states = dict(
            (
                side,
                states.get("wall_connection_type_%s" % side),
            )
            for side in ("east", "north", "south", "west")
        )
        if any(value is not None for value in wall_states.values()):
            states["wall_connection_type_south"] = wall_states["east"]
            states["wall_connection_type_west"] = wall_states["south"]
            states["wall_connection_type_north"] = wall_states["west"]
            states["wall_connection_type_east"] = wall_states["north"]
    return states


def _rotated_block(name, states, rotation):
    rotation = int(rotation) % 4
    if rotation % 2:
        for variants in STATELESS_AXIS_BLOCKS.values():
            if name == variants["x"]:
                name = variants["z"]
                break
            if name == variants["z"]:
                name = variants["x"]
                break
    return name, _rotated_states(states, rotation)


def _courtyard_variant(block, rng):
    name, states, block_entity = block
    variant_groups = {
        "tf_slice:etched_nagastone": (
            "tf_slice:mossy_etched_nagastone",
            "tf_slice:cracked_etched_nagastone",
        ),
        "tf_slice:nagastone_pillar": (
            "tf_slice:mossy_nagastone_pillar",
            "tf_slice:cracked_nagastone_pillar",
        ),
        "tf_slice:nagastone_stairs_left": (
            "tf_slice:mossy_nagastone_stairs_left",
            "tf_slice:cracked_nagastone_stairs_left",
        ),
        "tf_slice:nagastone_stairs_right": (
            "tf_slice:mossy_nagastone_stairs_right",
            "tf_slice:cracked_nagastone_stairs_right",
        ),
    }
    if name in variant_groups and rng.random() < 0.5:
        name = rng.choice(variant_groups[name])
    elif (
        name == "minecraft:stone_bricks" and rng.random() < 0.5
    ):
        name = rng.choice(
            (
                "minecraft:mossy_stone_bricks",
                "minecraft:cracked_stone_bricks",
            )
        )
    elif name == "minecraft:cobblestone" and rng.random() < 0.5:
        name = "minecraft:mossy_cobblestone"
    return name, states, block_entity


COURTYARD_PROCESSOR_STONE_BRICKS = frozenset(
    (
        "minecraft:stone_bricks",
        "minecraft:mossy_stone_bricks",
        "minecraft:cracked_stone_bricks",
        "minecraft:chiseled_stone_bricks",
        "minecraft:stone_brick_slab",
        "minecraft:mossy_stone_brick_slab",
    )
)


def _courtyard_terrace_processor(block, existing):
    if block[0] != "minecraft:sandstone_slab":
        return block
    existing_name = existing[0] if existing else "minecraft:air"
    is_double = "top_slot_bit" not in (block[1] or {})
    if is_double:
        if existing_name in COURTYARD_PROCESSOR_STONE_BRICKS:
            return ("minecraft:stone_brick_slab", {}, {})
        if existing_name == "minecraft:air":
            return None
        return ("minecraft:stone_bricks", {}, {})
    if existing_name == "minecraft:air":
        return None
    return ("minecraft:stone_brick_slab", {}, {})


def _place_courtyard_template(
    result,
    template,
    origin,
    rotation,
    rng,
    integrity=1.0,
    ignore_air=False,
    variants=False,
    terrace_processor=False,
):
    rotation = int(rotation) % 4
    for (x, y, z), source_block in sorted(template.blocks.items()):
        block = source_block
        if block[0] == "minecraft:air":
            if ignore_air:
                continue
        elif rng.random() > float(integrity):
            continue
        target_x, target_z = _rotated_xz(x, z, rotation)
        target = (
            origin[0] + target_x,
            origin[1] + y,
            origin[2] + target_z,
        )
        if terrace_processor and block[0] != "minecraft:air":
            existing = result.blocks.get(target)
            if existing is None and target[1] < COURTYARD_WALKWAY_Y:
                # The native envelope supplies two dirt foundation layers
                # below the courtyard surface before the source processor
                # samples the world at terrace placement time.
                existing = ("minecraft:dirt", {}, {})
            block = _courtyard_terrace_processor(block, existing)
            if block is None:
                continue
        if variants and block[0] != "minecraft:air":
            block = _courtyard_variant(block, rng)
        rotated_name, rotated_states = _rotated_block(
            block[0],
            block[1],
            rotation,
        )
        result.set(
            target[0],
            target[1],
            target[2],
            rotated_name,
            rotated_states,
            block[2],
        )


def _generate_courtyard_maze(rng):
    cell_count = COURTYARD_ROW_OF_CELLS - 1
    maze = [[0 for _ in range(cell_count)] for _ in range(cell_count)]
    selected = [[0 for _ in range(cell_count)] for _ in range(cell_count)]
    for x in range(cell_count):
        for z in range(cell_count):
            selected[x][z] = rng.randrange(len(COURTYARD_FACINGS))
            maze[x][z] |= COURTYARD_FACINGS[selected[x][z]][0]
    # Java's int[][] clone is intentionally shallow. The 4.3.2508 source
    # reads the live rows again in its zero-cell repair pass below.
    maze_local = list(maze)

    center = (COURTYARD_ROW_OF_CELLS // 2) - 1
    for z in range(cell_count):
        for x in range(cell_count):
            if x == center and z == center:
                continue
            facing = COURTYARD_FACINGS[selected[x][z]]
            bit, opposite, inverted, _, dx, dz = facing
            target_x = x + dx
            target_z = z + dz
            if not (
                0 <= target_x < cell_count
                and 0 <= target_z < cell_count
            ):
                continue
            if maze[target_x][target_z] & bit != bit:
                maze[target_x][target_z] |= opposite
            else:
                maze[x][z] &= inverted
                neighbor = COURTYARD_FACINGS[selected[target_x][target_z]]
                maze[target_x][target_z] &= neighbor[3]

    for _, _, _, inverted_opposite, dx, dz in COURTYARD_FACINGS:
        maze[center + dx][center + dz] &= inverted_opposite
    maze[center][center] = 0b10000

    for x in range(1, cell_count):
        for z in range(1, cell_count):
            if maze_local[x][z] != 0:
                continue
            if maze_local[x - 1][z] == 0:
                maze[x][z] |= 0b0100
                maze[x - 1][z] |= 0b0001
            if maze_local[x][z - 1] == 0:
                maze[x][z] |= 0b1000
                maze[x][z - 1] |= 0b0010

    # Diagonals enum order: top-right, bottom-right, bottom-left, top-left.
    diagonals = (
        (False, True),
        (False, False),
        (True, False),
        (True, True),
    )
    clips = []
    for is_left, is_top in diagonals:
        clip_z = rng.randrange(2) + 1
        clip_x = rng.randrange(2) + 1
        clips.append((clip_z, clip_x))
        for local_z in range(clip_z):
            for local_x in range(clip_x):
                x = local_x if is_left else (cell_count - 1) - local_x
                z = local_z if is_top else (cell_count - 1) - local_z
                maze[x][z] |= 0b10000
    return maze, clips


def _courtyard_hedge_kind(bits):
    links = bits & 0b1111
    if links in (0b0010, 0b0001, 0b1000, 0b0100):
        rotations = {
            0b0010: 3,
            0b0001: 2,
            0b1000: 1,
            0b0100: 0,
        }
        return "cap", rotations[links]
    if links in (0b1001, 0b1100, 0b0110, 0b0011):
        rotations = {
            0b1001: 3,
            0b1100: 2,
            0b0110: 1,
            0b0011: 0,
        }
        return "corner", rotations[links]
    if links in (0b1101, 0b1110, 0b0111, 0b1011):
        rotations = {
            0b1101: 3,
            0b1110: 2,
            0b0111: 1,
            0b1011: 0,
        }
        return "t", rotations[links]
    if links in (0b1010, 0b0101):
        return "line", 1 if links == 0b1010 else 0
    if links == 0b1111:
        return "intersection", 0
    return "terrace", 0


def _courtyard_needs_inner_padding(neighbor_bits):
    return int(neighbor_bits) & 0b10000 != 0b10000


def _courtyard_terrace_kind(rng):
    if rng.randrange(150) == 0:
        return "statue"
    return "fire" if rng.randrange(2) == 0 else "duct"


def naga_courtyard(seed):
    rng = random.Random(0x4E414741 + int(seed))
    templates = _courtyard_templates()
    result = SparseStructure(
        (COURTYARD_SIZE, COURTYARD_HEIGHT, COURTYARD_SIZE),
        "naga_courtyard",
    )
    margin = COURTYARD_MARGIN
    minimum = margin
    maximum = margin + (COURTYARD_RADIUS * 2) - 1
    center = margin + COURTYARD_RADIUS
    maze, clips = _generate_courtyard_maze(rng)

    for x in range(minimum, maximum + 1):
        for z in range(minimum, maximum + 1):
            result.set(x, COURTYARD_WALKWAY_Y, z, "minecraft:grass_block")

    def place(name, x, y, z, rotation=0, integrity=1.0,
              ignore_air=False, variants=False,
              terrace_processor=False):
        _place_courtyard_template(
            result,
            templates[name],
            (x, y, z),
            rotation,
            rng,
            integrity,
            ignore_air,
            variants,
            terrace_processor,
        )

    def place_hedge(kind, x, z, rotation=0, pillar=False):
        if kind == "cap":
            template_name = "hedge_end_pillar" if pillar else "hedge_end"
        else:
            template_name = {
                "between": "hedge_between",
                "corner": "hedge_corner",
                "intersection": "hedge_intersection",
                "line": "hedge_line",
                "t": "hedge_t",
            }[kind]
        place(
            template_name,
            x,
            COURTYARD_WALKWAY_Y + 1,
            z,
            rotation,
            variants=True,
        )
        place(
            template_name + "_big",
            x,
            COURTYARD_WALKWAY_Y + 1,
            z,
            rotation,
            COURTYARD_HEDGE_FLOOF,
            True,
        )

    def place_path(x, z):
        place("pathway", x, COURTYARD_WALKWAY_Y, z, 0, variants=True)

    def place_terrace(x, z):
        terrace_kind = _courtyard_terrace_kind(rng)
        if terrace_kind == "statue":
            place(
                "terrace_statue",
                x,
                COURTYARD_TERRACE_ORIGIN_Y,
                z,
                0,
                variants=True,
                terrace_processor=True,
            )
        elif terrace_kind == "fire":
            place(
                "terrace_fire",
                x,
                COURTYARD_TERRACE_ORIGIN_Y,
                z,
                0,
                variants=True,
                terrace_processor=True,
            )
        else:
            place(
                "terrace_duct",
                x,
                COURTYARD_TERRACE_ORIGIN_Y,
                z,
                0,
                variants=True,
                terrace_processor=True,
            )

    cells = COURTYARD_ROW_OF_CELLS - 1
    center_cell = (COURTYARD_ROW_OF_CELLS // 2) - 1
    offset = 6
    for cell_x in range(cells):
        for cell_z in range(cells):
            x_center = cell_x == center_cell
            z_center = cell_z == center_cell
            bits = maze[cell_x][cell_z]
            if not (x_center or z_center) and bits & 0b10000:
                continue
            x_bb = minimum + cell_x * COURTYARD_CELL_SIZE + offset
            z_bb = minimum + cell_z * COURTYARD_CELL_SIZE + offset

            if not (x_center and z_center):
                kind, rotation = _courtyard_hedge_kind(bits)
                if kind == "terrace":
                    place_terrace(x_bb - 6, z_bb - 6)
                else:
                    place_hedge(
                        kind,
                        x_bb,
                        z_bb,
                        rotation,
                        kind == "cap" and rng.randrange(2) == 0,
                    )

            connect_west = bool(bits & 0b0100)
            connect_north = bool(bits & 0b1000)
            connect_east = bool(bits & 0b0001)
            connect_south = bool(bits & 0b0010)
            if connect_west:
                place_hedge("between", x_bb - 1, z_bb)
                if cell_x > 0 and _courtyard_needs_inner_padding(
                    maze[cell_x - 1][cell_z]
                ):
                    place_hedge("between", x_bb - 7, z_bb)
                place_hedge("line", x_bb - 6, z_bb)
            if connect_north:
                place_hedge("between", x_bb + 4, z_bb - 1, 1)
                if cell_z > 0 and _courtyard_needs_inner_padding(
                    maze[cell_x][cell_z - 1]
                ):
                    place_hedge("between", x_bb + 4, z_bb - 7, 1)
                place_hedge("line", x_bb, z_bb - 6, 1)
            if (
                connect_east
                and (
                    cell_x >= cells - 1
                    or maze[cell_x + 1][cell_z] & 0b10000
                )
            ):
                place_hedge("between", x_bb + 5, z_bb)
                place_hedge("line", x_bb + 6, z_bb)
            if (
                connect_south
                and (
                    cell_z >= cells - 1
                    or maze[cell_x][cell_z + 1] & 0b10000
                )
            ):
                place_hedge("between", x_bb + 4, z_bb + 5, 1)
                place_hedge("line", x_bb, z_bb + 6, 1)

            has_no_terrace = bool(bits & 0b1111)
            west_safe = (
                cell_x == 0
                or maze[cell_x - 1][cell_z] & 0b10000
                or maze[cell_x - 1][cell_z] & 0b1111
            )
            north_safe = (
                cell_z == 0
                or maze[cell_x][cell_z - 1] & 0b10000
                or maze[cell_x][cell_z - 1] & 0b1111
            )
            east_safe = (
                cell_x == cells - 1
                or maze[cell_x + 1][cell_z] & 0b10000
            )
            south_safe = (
                cell_z == cells - 1
                or maze[cell_x][cell_z + 1] & 0b10000
            )
            northwest_safe = (
                cell_x == 0
                or cell_z == 0
                or maze[cell_x - 1][cell_z - 1] != 0
            )
            southwest_safe = (
                cell_x == 0
                or cell_z == cells - 1
                or maze[cell_x - 1][cell_z + 1] != 0
            )
            northeast_safe = (
                cell_x == cells - 1
                or cell_z == 0
                or maze[cell_x + 1][cell_z - 1] != 0
            )
            southeast_safe = (
                cell_x == cells - 1
                or cell_z == cells - 1
                or maze[cell_x + 1][cell_z + 1] != 0
            )
            if x_center and z_center:
                place_path(x_bb - 1, z_bb - 1)
            if has_no_terrace and west_safe and not connect_west:
                place_path(x_bb - 7, z_bb - 1)
            if has_no_terrace and north_safe and not connect_north:
                place_path(x_bb - 1, z_bb - 7)
            if has_no_terrace and east_safe:
                place_path(x_bb + 5, z_bb - 1)
            if has_no_terrace and south_safe:
                place_path(x_bb - 1, z_bb + 5)
            if has_no_terrace and west_safe and north_safe and northwest_safe:
                place_path(x_bb - 7, z_bb - 7)
            if has_no_terrace and west_safe and south_safe and southwest_safe:
                place_path(x_bb - 7, z_bb + 5)
            if has_no_terrace and east_safe and north_safe and northeast_safe:
                place_path(x_bb + 5, z_bb - 7)
            if has_no_terrace and east_safe and south_safe and southeast_safe:
                place_path(x_bb + 5, z_bb + 5)

    def place_wall(kind, x, z, rotation=0):
        main_name = {
            "wall": "courtyard_wall",
            "padding": "courtyard_wall_padding",
            "outer": "courtyard_wall_corner",
            "inner": "courtyard_wall_corner_inner",
        }[kind]
        decay_name = {
            "wall": "courtyard_wall_decayed",
            "padding": "courtyard_wall_padding_decayed",
            "outer": "courtyard_wall_corner_decayed",
            "inner": "courtyard_wall_corner_inner_decayed",
        }[kind]
        place(
            main_name,
            x,
            COURTYARD_WALKWAY_Y + 1,
            z,
            rotation,
            COURTYARD_WALL_INTEGRITY,
            False,
            True,
        )
        place(
            decay_name,
            x,
            COURTYARD_WALKWAY_Y + 1,
            z,
            rotation,
            COURTYARD_WALL_DECAY,
            True,
            True,
        )

    diagonal_data = (
        (False, True),
        (False, False),
        (True, False),
        (True, True),
    )

    def corner_shift(shift_z, shift_x, both, z_only, x_only, neither):
        if shift_z:
            return both if shift_x else z_only
        return x_only if shift_x else neither

    for diagonal, (is_left, is_top) in enumerate(diagonal_data):
        clip_z, clip_x = clips[diagonal]
        z_bound_x = (
            minimum + clip_z * COURTYARD_CELL_SIZE - 3
            if is_top
            else maximum - clip_z * COURTYARD_CELL_SIZE + 1
        )
        place_wall(
            "padding",
            minimum + 2 if is_left else maximum - 2,
            z_bound_x,
        )
        x_pad_offset = 11 if is_left else -1
        for index in range(clip_x - 1):
            x_bound = (
                minimum + index * COURTYARD_CELL_SIZE + 3
                if is_left
                else maximum - index * COURTYARD_CELL_SIZE - 13
            )
            place_wall("wall", x_bound, z_bound_x)
            place_wall("padding", x_bound + x_pad_offset, z_bound_x)

        x_bound_z = (
            minimum + clip_x * COURTYARD_CELL_SIZE - 1
            if is_left
            else maximum - clip_x * COURTYARD_CELL_SIZE + 3
        )
        place_wall(
            "padding",
            x_bound_z,
            minimum + 2 if is_top else maximum - 2,
            1,
        )
        z_pad_offset = 11 if is_top else -1
        for index in range(clip_z - 1):
            z_bound = (
                minimum + index * COURTYARD_CELL_SIZE + 3
                if is_top
                else maximum - index * COURTYARD_CELL_SIZE - 13
            )
            place_wall("wall", x_bound_z, z_bound, 1)
            place_wall("padding", x_bound_z, z_bound + z_pad_offset, 1)

        corner_x = minimum + (
            (cells - clip_x) if not is_left else clip_x
        ) * COURTYARD_CELL_SIZE
        corner_z = minimum + (
            (cells - clip_z) if not is_top else clip_z
        ) * COURTYARD_CELL_SIZE
        rotation = diagonal
        shift_x = rotation in (2, 3)
        shift_z = rotation in (1, 2)
        place_wall(
            "outer",
            corner_x + corner_shift(shift_z, shift_x, 1, 7, -3, 3),
            (minimum if is_top else maximum - 1)
            + corner_shift(shift_z, shift_x, 4, 0, 1, -3),
            rotation,
        )
        place_wall(
            "outer",
            (minimum if is_left else maximum - 1)
            + corner_shift(shift_z, shift_x, 1, 4, -3, 0),
            corner_z + corner_shift(shift_z, shift_x, 7, 3, 1, -3),
            rotation,
        )
        place_wall(
            "inner",
            corner_x + corner_shift(shift_z, shift_x, -1, 13, -9, 5),
            corner_z + corner_shift(shift_z, shift_x, 13, 5, -1, -9),
            rotation,
        )

    for index in range(clips[3][1], cells - clips[0][1]):
        x = minimum + index * COURTYARD_CELL_SIZE + offset - 3
        place_wall("wall", x, minimum - 3)
        place_wall("padding", x - 1, minimum - 3)
    place_wall(
        "padding",
        minimum + (cells - clips[0][1]) * COURTYARD_CELL_SIZE + offset - 4,
        minimum - 3,
    )
    for index in range(clips[2][1], cells - clips[1][1]):
        x = minimum + index * COURTYARD_CELL_SIZE + offset - 3
        place_wall("wall", x, maximum + 1)
        place_wall("padding", x - 1, maximum + 1)
    place_wall(
        "padding",
        minimum + (cells - clips[1][1]) * COURTYARD_CELL_SIZE + offset - 4,
        maximum + 1,
    )
    for index in range(clips[3][0], cells - clips[2][0]):
        z = minimum + index * COURTYARD_CELL_SIZE + offset - 3
        place_wall("wall", minimum - 1, z, 1)
        place_wall("padding", minimum - 1, z - 1, 1)
    place_wall(
        "padding",
        minimum - 1,
        minimum + (cells - clips[2][0]) * COURTYARD_CELL_SIZE + offset - 4,
        1,
    )
    for index in range(clips[0][0], cells - clips[1][0]):
        z = minimum + index * COURTYARD_CELL_SIZE + offset - 3
        place_wall("wall", maximum + 3, z, 1)
        place_wall("padding", maximum + 3, z - 1, 1)
    place_wall(
        "padding",
        maximum + 3,
        minimum + (cells - clips[1][0]) * COURTYARD_CELL_SIZE + offset - 4,
        1,
    )

    result.set(
        center,
        COURTYARD_WALKWAY_Y + 3,
        center,
        "tf_slice:naga_boss_spawner",
    )
    return result


def mushroom_tower(seed):
    size = 47
    height = 38
    result = SparseStructure((size, height, size), "mushroom_tower")

    def tower(cx, cz, radius, tower_height, mushroom):
        for y in range(tower_height):
            for x in range(cx - radius, cx + radius + 1):
                for z in range(cz - radius, cz + radius + 1):
                    boundary = x in (cx - radius, cx + radius) or z in (
                        cz - radius,
                        cz + radius,
                    )
                    if boundary:
                        result.set(x, y, z, "minecraft:stone_bricks")
                    elif y % 4 == 0:
                        result.set(
                            x,
                            y,
                            z,
                            "minecraft:oak_planks",
                        )
                    else:
                        result.set(x, y, z, "minecraft:air")
        roof_y = tower_height
        for x in range(cx - radius - 3, cx + radius + 4):
            for z in range(cz - radius - 3, cz + radius + 4):
                distance = math.sqrt((x - cx) ** 2 + (z - cz) ** 2)
                if distance <= radius + 3:
                    result.set(x, roof_y, z, mushroom)
                    if distance <= radius + 1:
                        result.set(x, roof_y + 1, z, mushroom)

    towers = [
        (23, 23, 7, 28, "minecraft:red_mushroom_block"),
        (8, 23, 4, 18, "minecraft:brown_mushroom_block"),
        (38, 23, 4, 22, "minecraft:red_mushroom_block"),
        (23, 8, 4, 15, "minecraft:brown_mushroom_block"),
        (23, 38, 4, 20, "minecraft:red_mushroom_block"),
    ]
    for spec in towers:
        tower(*spec)
    for x in range(12, 35):
        for y in range(8, 12):
            result.set(x, y, 23, "minecraft:stone_bricks")
            result.set(23, y, x, "minecraft:stone_bricks")
    return result


def lich_tower(seed):
    return lich_tower_legacy_port.build_lich_tower(
        int(seed),
        SparseStructure,
        set_loot_container,
        set_spawner,
    )


HOLLOW_HILL_SPIKES = {
    "small": (
        (
            (("minecraft:coal_ore", 1),),
            12,
            0.8,
            24,
        ),
        (
            (
                ("minecraft:copper_ore", 20),
                ("minecraft:raw_copper_block", 1),
            ),
            12,
            0.6,
            12,
        ),
        (
            (("minecraft:glowstone", 1),),
            8,
            0.5,
            12,
        ),
        (
            (
                ("minecraft:iron_ore", 20),
                ("minecraft:raw_iron_block", 1),
            ),
            8,
            0.7,
            24,
        ),
    ),
    "medium": (
        (
            (
                ("minecraft:gold_ore", 10),
                ("minecraft:raw_gold_block", 1),
            ),
            6,
            0.6,
            20,
        ),
        (
            (("minecraft:redstone_ore", 1),),
            8,
            0.8,
            40,
        ),
    ),
    "large": (
        (
            (("minecraft:diamond_ore", 1),),
            4,
            0.5,
            30,
        ),
        (
            (("minecraft:emerald_ore", 1),),
            3,
            0.5,
            15,
        ),
        (
            (("minecraft:lapis_ore", 1),),
            8,
            0.8,
            30,
        ),
    ),
}

HOLLOW_HILL_MOBS = {
    1: (
        "minecraft:spider",
        "minecraft:spider",
        "minecraft:spider",
        "minecraft:zombie",
        "minecraft:zombie",
        "minecraft:silverfish",
        "tf_slice:redcap",
        "tf_slice:swarm_spider",
        "tf_slice:swarm_spider",
        "tf_slice:swarm_spider",
    ),
    2: (
        "minecraft:zombie",
        "minecraft:zombie",
        "minecraft:zombie",
        "minecraft:skeleton",
        "minecraft:skeleton",
        "tf_slice:swarm_spider",
        "minecraft:cave_spider",
        "tf_slice:redcap",
        "tf_slice:redcap",
        "tf_slice:redcap",
    ),
    3: (
        "tf_slice:slime_beetle",
        "tf_slice:fire_beetle",
        "tf_slice:pinch_beetle",
        "minecraft:skeleton",
        "minecraft:skeleton",
        "minecraft:skeleton",
        "minecraft:cave_spider",
        "minecraft:cave_spider",
        "minecraft:cave_spider",
        "minecraft:creeper",
        "tf_slice:wraith",
    ),
}

HOLLOW_HILL_VARIANT_SEEDS = {
    36: 95,
    68: 35,
    100: 107,
}
HOLLOW_HILL_CONTENT_SEEDS = {
    diameter: tuple(
        HOLLOW_HILL_VARIANT_SEEDS[diameter] + index * 104729
        for index in range(8)
    )
    for diameter in (36, 68, 100)
}
HOLLOW_HILL_TERRAIN_SEEDS = {
    36: 0x534D414C4C,
    68: 0x4D454449554D,
    100: 0x4C41524745,
}
def _maze_raw_index(raw_width, x, z):
    return int(z) * int(raw_width) + int(x)


def _maze_raw_get(raw, raw_width, raw_depth, x, z):
    if not (0 <= int(x) < raw_width and 0 <= int(z) < raw_depth):
        return None
    return raw[_maze_raw_index(raw_width, x, z)]


def _maze_raw_set(raw, raw_width, raw_depth, x, z, value):
    if 0 <= int(x) < raw_width and 0 <= int(z) < raw_depth:
        raw[_maze_raw_index(raw_width, x, z)] = int(value)


class _JavaRandomSource:
    """Minecraft LegacyRandomSource/java.util.Random compatible stream."""

    _MULTIPLIER = 0x5DEECE66D
    _ADDEND = 0xB
    _MASK = (1 << 48) - 1

    def __init__(self, seed):
        self.set_seed(seed)

    def set_seed(self, seed):
        self._seed = (int(seed) ^ self._MULTIPLIER) & self._MASK

    def _next(self, bits):
        self._seed = (
            self._seed * self._MULTIPLIER + self._ADDEND
        ) & self._MASK
        return self._seed >> (48 - int(bits))

    def next_int(self, bound):
        bound = int(bound)
        if bound <= 0:
            raise ValueError("bound must be positive")
        if bound & (bound - 1) == 0:
            return (bound * self._next(31)) >> 31
        while True:
            bits = self._next(31)
            value = bits % bound
            # Java evaluates this expression as a signed 32-bit int. Values
            # at or above 2^31 are the overflow/rejection case.
            if bits - value + (bound - 1) < (1 << 31):
                return value

    def next_float(self):
        return self._next(24) / float(1 << 24)

    def next_boolean(self):
        return self._next(1) != 0


def _carve_source_maze_room(raw, raw_width, raw_depth, cell_x, cell_z):
    """Reserve the source mod's five-by-five raw-cell room footprint."""
    raw_x = int(cell_x) * 2 + 1
    raw_z = int(cell_z) * 2 + 1
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            _maze_raw_set(
                raw, raw_width, raw_depth, raw_x + dx, raw_z + dz, 5
            )

    # Preserve TFMaze.carveRoom1's four putCell calls, including its use of
    # already-converted raw coordinates. Although unusual, this is observable
    # for rooms near the northwest corner and is part of the locked source.
    for source_cell_x, source_cell_z in (
        (raw_x, raw_z + 1),
        (raw_x, raw_z - 1),
        (raw_x + 1, raw_z),
        (raw_x - 1, raw_z),
    ):
        _maze_raw_set(
            raw,
            raw_width,
            raw_depth,
            source_cell_x * 2 + 1,
            source_cell_z * 2 + 1,
            0,
        )
    for dx, dz in ((3, 0), (-3, 0), (0, 3), (0, -3)):
        if _maze_raw_get(
            raw, raw_width, raw_depth, raw_x + dx * 4 // 3, raw_z + dz * 4 // 3
        ) is not None:
            _maze_raw_set(
                raw, raw_width, raw_depth, raw_x + dx, raw_z + dz, 5
            )


def _carve_source_maze(raw, raw_width, raw_depth, rng):
    """Run TFMaze.rbGen while preserving every RandomSource consumption."""
    width = (int(raw_width) - 1) // 2
    depth = (int(raw_depth) - 1) // 2
    stack = [(0, 0)]
    _maze_raw_set(raw, raw_width, raw_depth, 1, 1, 1)
    while stack:
        cell_x, cell_z = stack[-1]
        candidates = []
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_x = cell_x + dx
            next_z = cell_z + dz
            if not (0 <= next_x < width and 0 <= next_z < depth):
                continue
            raw_x = next_x * 2 + 1
            raw_z = next_z * 2 + 1
            if _maze_raw_get(
                raw, raw_width, raw_depth, raw_x, raw_z
            ) == 0:
                candidates.append((next_x, next_z, dx, dz))
        if not candidates:
            stack.pop()
            continue
        next_x, next_z, dx, dz = candidates[rng.next_int(len(candidates))]
        # doorRarity is zero in MinotaurMazeComponent, but upstream still
        # calls nextFloat for every carved edge. Omitting it changes all later
        # choices and produces the repeated box-room topology seen in game.
        wall_value = 6 if rng.next_float() <= 0.0 else 2
        _maze_raw_set(
            raw,
            raw_width,
            raw_depth,
            cell_x * 2 + 1 + dx,
            cell_z * 2 + 1 + dz,
            wall_value,
        )
        _maze_raw_set(
            raw, raw_width, raw_depth, next_x * 2 + 1, next_z * 2 + 1, 1
        )
        stack.append((next_x, next_z))


def _source_maze_layout(
    width, depth, seed, entrance_cell=(11, 11), room_count=7
):
    """Build rooms and maze with the single stream used by TF 4.3.2508."""
    raw_width = int(width) * 2 + 1
    raw_depth = int(depth) * 2 + 1
    raw = [0] * (raw_width * raw_depth)
    rng = _JavaRandomSource(seed)
    room_cells = [tuple(entrance_cell)]
    _carve_source_maze_room(
        raw,
        raw_width,
        raw_depth,
        room_cells[0][0],
        room_cells[0][1],
    )
    while len(room_cells) < int(room_count):
        candidate = (
            rng.next_int(int(width) - 2) + 1,
            rng.next_int(int(depth) - 2) + 1,
        )
        separation = 7 if len(room_cells) == 1 else 4
        if candidate == (1, 1) or any(
            abs(candidate[0] - placed[0]) < separation
            and abs(candidate[1] - placed[1]) < separation
            for placed in room_cells
        ):
            continue
        room_cells.append(candidate)
        _carve_source_maze_room(
            raw,
            raw_width,
            raw_depth,
            candidate[0],
            candidate[1],
        )

    _carve_source_maze(raw, raw_width, raw_depth, rng)
    return raw, raw_width, raw_depth, room_cells


def _source_maze_raw(width, depth, seed, room_cells):
    """Compatibility helper for callers that supply preselected rooms."""
    raw_width = int(width) * 2 + 1
    raw_depth = int(depth) * 2 + 1
    raw = [0] * (raw_width * raw_depth)
    for room_x, room_z in room_cells:
        _carve_source_maze_room(
            raw, raw_width, raw_depth, room_x, room_z
        )
    _carve_source_maze(
        raw, raw_width, raw_depth, _JavaRandomSource(seed)
    )
    return raw, raw_width, raw_depth


def _weathered_mazestone(rng):
    # StructureTFMazeStones: 50% brick, 30% cracked, 20% mossy.
    roll = rng.randrange(10)
    if roll < 2:
        return "tf_slice:mossy_mazestone"
    if roll < 5:
        return "tf_slice:cracked_mazestone"
    return "tf_slice:mazestone_brick"


def _maze_wall_is_pillar(raw, raw_width, raw_depth, raw_x, raw_z):
    """Match TFMaze's chiseled turn/intersection pillar selection."""
    north = _maze_raw_get(raw, raw_width, raw_depth, raw_x, raw_z - 1) == 0
    south = _maze_raw_get(raw, raw_width, raw_depth, raw_x, raw_z + 1) == 0
    west = _maze_raw_get(raw, raw_width, raw_depth, raw_x - 1, raw_z) == 0
    east = _maze_raw_get(raw, raw_width, raw_depth, raw_x + 1, raw_z) == 0
    return not ((north and south and not west and not east) or (
        west and east and not north and not south
    ))


def _place_source_maze_level(structure, raw, raw_width, raw_depth, floor_y, seed):
    """Render four-wide passages and layered source-style maze walls."""
    rng = random.Random(int(seed) ^ (int(floor_y) * 0x9E3779B1))
    air_y = int(floor_y) + 1
    ceiling_y = int(floor_y) + 5
    # MinotaurMazeComponent has a 112-block bounding box around its 110-block
    # interior. The source clears/floors local 1..110, leaving the outer shell
    # behind the maze-rendered boundary instead of clipping the final cells.
    maze_diameter = ((int(raw_width) - 1) // 2) * 5
    structure.fill(
        (1, floor_y, 1),
        (maze_diameter, floor_y, maze_diameter),
        "tf_slice:mazestone_mosaic",
    )
    structure.fill(
        (1, air_y, 1),
        (maze_diameter, ceiling_y - 1, maze_diameter),
        "minecraft:air",
    )
    structure.fill(
        (1, ceiling_y, 1),
        (maze_diameter, ceiling_y, maze_diameter),
        "tf_slice:mazestone",
    )

    for raw_x in range(raw_width):
        for raw_z in range(raw_depth):
            if _maze_raw_get(raw, raw_width, raw_depth, raw_x, raw_z) != 0:
                continue
            base_x = 1 + (raw_x // 2) * 5
            base_z = 1 + (raw_z // 2) * 5
            if raw_x % 2 == 0 and raw_z % 2 == 0:
                positions = ((base_x, base_z),)
                pillar = _maze_wall_is_pillar(
                    raw, raw_width, raw_depth, raw_x, raw_z
                )
            elif raw_x % 2 == 0:
                positions = tuple((base_x, base_z + offset) for offset in range(1, 5))
                pillar = False
            else:
                positions = tuple((base_x + offset, base_z) for offset in range(1, 5))
                pillar = False
            for world_x, world_z in positions:
                structure.set(world_x, air_y, world_z, "tf_slice:decorative_mazestone")
                middle = (
                    "tf_slice:cut_mazestone"
                    if pillar
                    else _weathered_mazestone(rng)
                )
                structure.set(world_x, air_y + 1, world_z, middle)
                structure.set(world_x, air_y + 2, world_z, middle)
                structure.set(world_x, air_y + 3, world_z, "tf_slice:decorative_mazestone")
                if pillar and rng.random() < 0.05:
                    # A standing torch inside the pillar replaces its wall
                    # block and renders as the recessed floor torch reported
                    # in game. Put a facing torch in the adjacent open passage.
                    open_sides = []
                    for facing, raw_dx, raw_dz, world_dx, world_dz in (
                        ("east", 1, 0, 1, 0),
                        ("west", -1, 0, -1, 0),
                        ("south", 0, 1, 0, 1),
                        ("north", 0, -1, 0, -1),
                    ):
                        if _maze_raw_get(
                            raw,
                            raw_width,
                            raw_depth,
                            raw_x + raw_dx,
                            raw_z + raw_dz,
                        ) not in (0, None):
                            open_sides.append(
                                (facing, world_dx, world_dz)
                            )
                    if open_sides:
                        facing, world_dx, world_dz = open_sides[
                            rng.randrange(len(open_sides))
                        ]
                        # Java WallTorchBlock.FACING points away from the
                        # backing wall. Bedrock torch_facing_direction names
                        # the block the torch is attached to, so the serialized
                        # state must use the opposite direction.
                        attachment_direction = {
                            "east": "west",
                            "west": "east",
                            "south": "north",
                            "north": "south",
                        }[facing]
                        structure.set(
                            world_x + world_dx,
                            air_y + 2,
                            world_z + world_dz,
                            "minecraft:torch",
                            {
                                "torch_facing_direction": (
                                    attachment_direction
                                )
                            },
                        )


def _set_oak_stair(structure, x, y, z, direction, upside_down=False):
    structure.set(
        x,
        y,
        z,
        "minecraft:oak_stairs",
        {
            "weirdo_direction": STAIR_DIRECTIONS[direction],
            "upside_down_bit": bool(upside_down),
        },
    )


def _maze_passage_runs(structure, air_y):
    """Encode walkable pixels as compact Z/X runs for the maze map."""
    rows = []
    for z in range(int(structure.size[2])):
        start = None
        for x in range(int(structure.size[0]) + 1):
            block = (
                structure.blocks.get((x, int(air_y), z))
                if x < structure.size[0]
                else None
            )
            walkable = bool(
                block
                and block[0] in ("minecraft:air", "minecraft:cave_air")
            )
            if walkable and start is None:
                start = x
            elif not walkable and start is not None:
                rows.append([z, start, x])
                start = None
    return rows


def _legacy_labyrinth_structure(seed):
    """Compile the source-scale 22x22 two-level Labyrinth.

    The two maze floors stay 10 blocks apart and 14/24 blocks below the
    surface entrance, matching ``MinotaurMazeComponent``.  Only the 35-block
    entrance mound owns surface columns; the remaining 110x110 footprint is
    underground payload and must leave the native swamp surface untouched.
    """
    rng = random.Random(int(seed) ^ 0x4D415A45)
    result = SparseStructure((110, 38, 110), "labyrinth_%02d" % seed)
    cell_size = 5
    grid = 22
    surface_ground_y = 25
    # Upper first, lower second. Walkable Y values differ by exactly 10.
    levels = ((11, 12, 16), (1, 2, 6))
    level_rooms = (
        ("entrance", "exit", "collapse", "collapse", "fountain", "spawner_chest", "spawner_chest"),
        ("entrance", "minoshroom", "mushroom", "mushroom", "vault", "spawner_chest", "spawner_chest"),
    )
    marker_chests = []
    spawn_zones = []
    rooms_meta = []
    level_room_cells = []

    def choose_room_cells(room_seed, entrance):
        room_rng = random.Random(int(room_seed) ^ 0x524F4F4D)
        cells = [tuple(entrance)]
        while len(cells) < 7:
            candidate = (room_rng.randint(1, 19), room_rng.randint(1, 19))
            separation = 7 if len(cells) == 1 else 4
            if any(
                abs(candidate[0] - placed[0]) < separation
                and abs(candidate[1] - placed[1]) < separation
                for placed in cells
            ):
                continue
            cells.append(candidate)
        return cells

    upper_cells = choose_room_cells(seed * 2, (11, 11))
    lower_cells = choose_room_cells(seed * 2 + 1, upper_cells[1])
    level_room_cells.extend((upper_cells, lower_cells))

    # The source lower maze is completely surrounded by bedrock.
    for x in range(110):
        for z in range(110):
            result.set(x, 0, z, "minecraft:bedrock")
            result.set(x, 7, z, "minecraft:bedrock")
            if x in (0, 109) or z in (0, 109):
                for y in range(0, 8):
                    result.set(x, y, z, "minecraft:bedrock")

    def carve_passage(first, second, air_y, ceiling_y):
        ax = 2 + first[0] * cell_size
        az = 2 + first[1] * cell_size
        bx = 2 + second[0] * cell_size
        bz = 2 + second[1] * cell_size
        minimum_x = min(ax, bx) - 1
        maximum_x = max(ax, bx) + 1
        minimum_z = min(az, bz) - 1
        maximum_z = max(az, bz) + 1
        for x in range(minimum_x, maximum_x + 1):
            for z in range(minimum_z, maximum_z + 1):
                for y in range(air_y, ceiling_y):
                    result.set(x, y, z, "minecraft:air")

    def room_origin(cell):
        return cell[0] * cell_size - 4, cell[1] * cell_size - 4

    def decorate_room(room_kind, origin_x, origin_z, floor_y, air_y, ceiling_y):
        center_x = origin_x + 7
        center_z = origin_z + 7
        for x in range(origin_x, origin_x + 16):
            for z in range(origin_z, origin_z + 16):
                border = x in (origin_x, origin_x + 15) or z in (
                    origin_z,
                    origin_z + 15,
                )
                result.set(
                    x,
                    floor_y,
                    z,
                    "tf_slice:mazestone_border"
                    if border
                    else "tf_slice:mazestone_mosaic",
                )
                for y in range(air_y, ceiling_y):
                    result.set(x, y, z, "minecraft:air")

        # Four two-wide doorways with fence shoulders.
        for dx, dz in ((7, 0), (7, 15), (0, 7), (15, 7)):
            for side in (-1, 2):
                x = origin_x + dx + (side if dz in (0, 15) else 0)
                z = origin_z + dz + (side if dx in (0, 15) else 0)
                for y in range(air_y, ceiling_y):
                    result.set(x, y, z, "minecraft:oak_fence")

        if room_kind == "collapse":
            for index in range(22):
                x = origin_x + 2 + rng.randrange(12)
                z = origin_z + 2 + rng.randrange(12)
                height = 1 + rng.randrange(3)
                for y in range(air_y, min(ceiling_y, air_y + height)):
                    result.set(x, y, z, "minecraft:gravel")
                if index % 4 == 0:
                    result.set(x, ceiling_y - 1, z, "tf_slice:root_strand")
        elif room_kind == "fountain":
            for x in range(center_x - 2, center_x + 3):
                for z in range(center_z - 2, center_z + 3):
                    result.set(x, floor_y, z, "tf_slice:decorative_mazestone")
                    if x not in (center_x - 2, center_x + 2) and z not in (
                        center_z - 2,
                        center_z + 2,
                    ):
                        result.set(x, air_y, z, "minecraft:water")
        elif room_kind == "spawner_chest":
            for dx, dz in ((-4, -4), (4, -4), (-4, 4), (4, 4)):
                for y in range(air_y, ceiling_y):
                    result.set(
                        center_x + dx,
                        y,
                        center_z + dz,
                        "tf_slice:cut_mazestone",
                    )
            set_spawner(
                result,
                center_x - 3,
                air_y + 1,
                center_z - 3,
                "tf_slice:minotaur",
            )
            for chest_x, chest_z in (
                (center_x - 3, center_z + 4),
                (center_x + 4, center_z - 3),
            ):
                set_loot_container(
                    result,
                    chest_x,
                    air_y + 1,
                    chest_z,
                    "labyrinth_room",
                )
                marker_chests.append(
                    {
                        "kind": "labyrinth_room",
                        "offset": [chest_x, air_y + 1, chest_z],
                    }
                )
            result.set(
                center_x + 4,
                air_y,
                center_z + 4,
                "minecraft:wooden_pressure_plate",
            )
            for dx, dz in ((3, 4), (4, 3), (5, 4), (4, 5)):
                result.set(
                    center_x + dx,
                    floor_y,
                    center_z + dz,
                    "minecraft:tnt",
                )
        elif room_kind in ("mushroom", "minoshroom"):
            for x in range(origin_x + 1, origin_x + 15):
                for z in range(origin_z + 1, origin_z + 15):
                    if (x * 31 + z * 17 + int(seed)) % 3 == 0:
                        result.set(x, floor_y, z, "minecraft:mycelium")
                    if (x * 13 + z * 7 + int(seed)) % 11 == 0:
                        result.set(
                            x,
                            air_y,
                            z,
                            "minecraft:red_mushroom"
                            if (x + z) % 2
                            else "minecraft:brown_mushroom",
                        )
            for dx, dz, block in (
                (-4, -4, "minecraft:red_mushroom_block"),
                (4, -4, "minecraft:brown_mushroom_block"),
                (-4, 4, "minecraft:brown_mushroom_block"),
                (4, 4, "minecraft:red_mushroom_block"),
            ):
                result.set(center_x + dx, air_y, center_z + dz, "minecraft:mushroom_stem")
                for cap_x in range(center_x + dx - 1, center_x + dx + 2):
                    for cap_z in range(center_z + dz - 1, center_z + dz + 2):
                        result.set(cap_x, air_y + 1, cap_z, block)
            if room_kind == "minoshroom":
                for chest_x, chest_z in (
                    (origin_x + 3, origin_z + 3),
                    (origin_x + 12, origin_z + 3),
                    (origin_x + 3, origin_z + 12),
                    (origin_x + 12, origin_z + 12),
                ):
                    set_loot_container(
                        result,
                        chest_x,
                        air_y + 1,
                        chest_z,
                        "labyrinth_room",
                    )
                    marker_chests.append(
                        {
                            "kind": "labyrinth_room",
                            "offset": [chest_x, air_y + 1, chest_z],
                        }
                    )
                result.set(
                    center_x,
                    air_y + 1,
                    center_z,
                    "tf_slice:minoshroom_boss_spawner",
                )
        elif room_kind == "vault":
            for x in range(origin_x, origin_x + 16):
                for z in range(origin_z, origin_z + 16):
                    if not (
                        center_x - 1 <= x <= center_x + 2
                        and center_z - 1 <= z <= center_z + 2
                    ):
                        for y in range(air_y, ceiling_y):
                            result.set(x, y, z, "tf_slice:mazestone_brick")
            for dx, dz in ((-2, 0), (3, 0), (0, -2), (0, 3)):
                result.set(
                    center_x + dx,
                    air_y,
                    center_z + dz,
                    "minecraft:wooden_pressure_plate",
                )
                result.set(
                    center_x + dx,
                    floor_y,
                    center_z + dz,
                    "minecraft:tnt",
                )
            for index, (dx, dz) in enumerate(
                ((-1, -1), (2, -1), (-1, 2), (2, 2))
            ):
                loot_kind = (
                    "labyrinth_jackpot" if index == int(seed) % 4 else "labyrinth_vault"
                )
                set_loot_container(
                    result,
                    center_x + dx,
                    air_y + 1,
                    center_z + dz,
                    loot_kind,
                )
                marker_chests.append(
                    {
                        "kind": loot_kind,
                        "offset": [center_x + dx, air_y + 1, center_z + dz],
                    }
                )

        return center_x, center_z

    for level_index, (floor_y, air_y, ceiling_y) in enumerate(levels):
        edges = _perfect_maze_edges(grid, grid, seed * 2 + level_index)
        for x in range(110):
            for z in range(110):
                result.set(
                    x,
                    floor_y,
                    z,
                    "tf_slice:mazestone_mosaic"
                    if (x + z + level_index) % 17 == 0
                    else "tf_slice:mazestone",
                )
                result.set(x, ceiling_y, z, "tf_slice:cut_mazestone")
                for y in range(air_y, ceiling_y):
                    result.set(x, y, z, _weathered_mazestone(rng))
        for cell_x in range(grid):
            for cell_z in range(grid):
                carve_passage(
                    (cell_x, cell_z),
                    (cell_x, cell_z),
                    air_y,
                    ceiling_y,
                )
        for first, second in edges:
            carve_passage(first, second, air_y, ceiling_y)

        for room_index, room_kind in enumerate(level_rooms[level_index]):
            cell = level_room_cells[level_index][room_index]
            origin_x, origin_z = room_origin(cell)
            center_x, center_z = decorate_room(
                room_kind,
                origin_x,
                origin_z,
                floor_y,
                air_y,
                ceiling_y,
            )
            rooms_meta.append(
                {
                    "kind": room_kind,
                    "level": level_index,
                    "offset": [center_x, air_y, center_z],
                    "origin": [origin_x, floor_y, origin_z],
                    "size": [16, 5, 16],
                }
            )
            spawn_zones.append(
                {"level": level_index, "center": [center_x, air_y, center_z], "radius": 7}
            )

    # The upper exit room and lower entrance share the source-style shaft.
    exit_room = rooms_meta[1]
    shaft_x, _shaft_y, shaft_z = exit_room["offset"]
    for y in range(7, 12):
        for dx in (-1, 0, 1, 2):
            for dz in (-1, 0, 1, 2):
                result.set(shaft_x + dx, y, shaft_z + dz, "minecraft:air")
        result.set(
            shaft_x - 1,
            y,
            shaft_z,
            "minecraft:ladder",
            {"facing_direction": 5},
        )

    # Surface mound and ruined 16x16 entrance. No other surface column is
    # claimed, so the forest above the underground maze remains native.
    center = 55
    surface_columns = {}
    for x in range(center - 18, center + 19):
        for z in range(center - 18, center + 19):
            distance = math.sqrt((x - center) ** 2 + (z - center) ** 2)
            if distance > 18:
                continue
            mound_height = max(
                0,
                int(
                    math.cos(distance / 35.0 * math.pi)
                    * (35.0 / 3.0)
                ),
            )
            top = surface_ground_y + mound_height
            for y in range(surface_ground_y - 3, top):
                result.set(x, y, z, "minecraft:dirt")
            result.set(x, top, z, "minecraft:grass_block")
            surface_columns[(x, z)] = top

    entrance_min = center - 7
    entrance_max = entrance_min + 15
    for x in range(entrance_min, entrance_max + 1):
        for z in range(entrance_min, entrance_max + 1):
            result.set(x, surface_ground_y, z, "tf_slice:mazestone_mosaic")
            if x in (entrance_min, entrance_max) or z in (
                entrance_min,
                entrance_max,
            ):
                for y in range(surface_ground_y + 1, surface_ground_y + 5):
                    if (x * 17 + z * 31 + int(seed)) % 5:
                        result.set(x, y, z, "tf_slice:mazestone_brick")
    for y in range(17, surface_ground_y + 12):
        for dx in (-1, 0, 1, 2):
            for dz in (-1, 0, 1, 2):
                result.set(center + dx, y, center + dz, "minecraft:air")
        result.set(
            center - 1,
            y,
            center,
            "minecraft:ladder",
            {"facing_direction": 5},
        )
    for dx in range(-3, 4):
        for dz in range(-3, 4):
            if abs(dx) == 3 or abs(dz) == 3:
                result.set(
                    center + dx,
                    surface_ground_y + 1,
                    center + dz,
                    "minecraft:iron_bars",
                )

    boss_room = next(room for room in rooms_meta if room["kind"] == "minoshroom")
    boss_offset = [
        boss_room["offset"][0],
        boss_room["offset"][1] + 1,
        boss_room["offset"][2],
    ]
    result.surface_ground_y = surface_ground_y
    result.surface_columns = surface_columns
    result.surface_core_radius = 18
    result.landmark_metadata = {
        "markerPolicy": "physical_boss_spawner_and_catalog",
        "boss": {"kind": "minoshroom", "offset": boss_offset},
        "mapCenter": [center, levels[0][1], center],
        "chests": marker_chests,
        "spawnZones": spawn_zones,
        "rooms": rooms_meta,
        "levels": [levels[0][1], levels[1][1]],
        "mazeGrid": [grid, grid],
        "cellPitch": cell_size,
        "levelOffset": 10,
        "lowerBedrockShell": True,
        "mapPassageRuns": {
            str(levels[0][1]): _maze_passage_runs(result, levels[0][1]),
            str(levels[1][1]): _maze_passage_runs(result, levels[1][1]),
        },
        "connected": True,
    }
    return result


def labyrinth_structure(seed):
    """Compile the source-scale, deeply buried two-level Minotaur Labyrinth."""
    seed = int(seed)
    rng = random.Random(seed ^ 0x4D415A45)
    result = SparseStructure((112, 54, 112), "labyrinth_%02d" % seed)
    grid = 22
    cell_pitch = 5
    surface_ground_y = LABYRINTH_SURFACE_GROUND_Y
    # floor, walkable air, ceiling. The two walkable levels remain 10 apart.
    levels = ((11, 12, 16), (1, 2, 6))
    level_room_kinds = (
        (
            "entrance",
            "exit",
            "collapse",
            "collapse",
            "fountain",
            "spawner_chest",
            "spawner_chest",
        ),
        (
            "entrance",
            "minoshroom",
            "mushroom",
            "mushroom",
            "vault",
            "spawner_chest",
            "spawner_chest",
        ),
    )
    marker_chests = []
    spawn_zones = []
    rooms_meta = []
    decorations = []

    upper_layout = _source_maze_layout(
        grid, grid, seed * 2, (11, 11), 7
    )
    upper_cells = upper_layout[3]
    lower_layout = _source_maze_layout(
        grid, grid, seed * 2 + 1, upper_cells[1], 7
    )
    level_layouts = (upper_layout, lower_layout)
    level_room_cells = (upper_cells, lower_layout[3])

    def room_origin(cell):
        return cell[0] * cell_pitch - 4, cell[1] * cell_pitch - 4

    def place_room_fence_panel(origin_x, origin_z, air_y, side):
        if side in ("north", "south"):
            local_z = 0 if side == "north" else 15
            panel = ((local_x, local_z) for local_x in range(6, 10))
            opening = ((local_x, local_z) for local_x in range(7, 9))
        else:
            local_x = 0 if side == "west" else 15
            panel = ((local_x, local_z) for local_z in range(6, 10))
            opening = ((local_x, local_z) for local_z in range(7, 9))
        for local_x, local_z in panel:
            for y in range(air_y, air_y + 4):
                result.set(
                    origin_x + local_x,
                    y,
                    origin_z + local_z,
                    "minecraft:oak_fence",
                )
        for local_x, local_z in opening:
            for y in range(air_y, air_y + 3):
                result.set(
                    origin_x + local_x,
                    y,
                    origin_z + local_z,
                    "minecraft:air",
                )

    def prepare_room(origin_x, origin_z, floor_y, air_y, ceiling_y):
        # MazeRoomComponent only replaces the 14x14 interior. Keeping the
        # perimeter generated by the maze piece prevents room corners and
        # surrounding walls from being punched out.
        for local_x in range(1, 15):
            for local_z in range(1, 15):
                border = local_x in (1, 14) or local_z in (1, 14)
                result.set(
                    origin_x + local_x,
                    floor_y,
                    origin_z + local_z,
                    "tf_slice:mazestone_border"
                    if border
                    else "tf_slice:mazestone_mosaic",
                )
                for y in range(air_y, ceiling_y):
                    result.set(
                        origin_x + local_x, y, origin_z + local_z, "minecraft:air"
                    )
        for side in ("north", "south", "west", "east"):
            place_room_fence_panel(origin_x, origin_z, air_y, side)

    def place_pillar_enclosure(origin_x, origin_z, floor_y, local_x, local_z):
        for dx, dz in ((0, 0), (2, 0), (0, 2), (2, 2)):
            for y in range(floor_y + 1, floor_y + 5):
                result.set(
                    origin_x + local_x + dx,
                    y,
                    origin_z + local_z + dz,
                    "tf_slice:cut_mazestone",
                )
        center_x = origin_x + local_x + 1
        center_z = origin_z + local_z + 1
        result.set(center_x, floor_y + 1, center_z, "minecraft:oak_planks")
        for y in (floor_y + 2, floor_y + 3):
            for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                result.set(center_x + dx, y, center_z + dz, "minecraft:iron_bars")
        for direction, dx, dz in (
            ("south", 0, -1),
            ("north", 0, 1),
            ("east", -1, 0),
            ("west", 1, 0),
        ):
            _set_oak_stair(
                result,
                center_x + dx,
                floor_y + 1,
                center_z + dz,
                direction,
            )
            _set_oak_stair(
                result,
                center_x + dx,
                floor_y + 4,
                center_z + dz,
                direction,
                True,
            )

    def add_marker_chest(
        x, y, z, loot_kind, block="minecraft:chest", states=None
    ):
        set_loot_container(
            result, x, y, z, loot_kind, block=block, states=states
        )
        marker_chests.append({"kind": loot_kind, "offset": [x, y, z]})

    def place_box(origin_x, floor_y, origin_z, bounds, block_name):
        min_x, min_y, min_z, max_x, max_y, max_z = bounds
        for local_x in range(min_x, max_x + 1):
            for local_y in range(min_y, max_y + 1):
                for local_z in range(min_z, max_z + 1):
                    states = None
                    if block_name in (
                        "minecraft:red_mushroom_block",
                        "minecraft:brown_mushroom_block",
                    ):
                        # Java's default huge-mushroom block state exposes cap
                        # skin on every face. Bedrock's equivalent is bit 14.
                        states = {"huge_mushroom_bits": 14}
                    result.set(
                        origin_x + local_x,
                        floor_y + local_y,
                        origin_z + local_z,
                        block_name,
                        states,
                    )

    def mushroom_block(origin_x, floor_y, origin_z, x, y, z, block_name, bits):
        result.set(
            origin_x + x,
            floor_y + y,
            origin_z + z,
            block_name,
            {"huge_mushroom_bits": int(bits)},
        )

    def make_medium_mushroom(
        origin_x, floor_y, origin_z, mushroom_x, mushroom_y, mushroom_z, block_name
    ):
        # MazeMushRoomComponent.makeMediumMushroom. Bedrock's legacy mushroom
        # bits are physical NW..SE states, so map them by the emitted world
        # offset. The old mapping was rotated 180 degrees and exposed the pale
        # pore texture around the entire outside of every cap.
        cap = (
            (0, 0, 5),
            (1, 0, 6),
            (1, 1, 9),
            (0, 1, 8),
            (-1, 1, 7),
            (-1, 0, 4),
            (-1, -1, 1),
            (0, -1, 2),
            (1, -1, 3),
        )
        for dx, dz, bits in cap:
            mushroom_block(
                origin_x,
                floor_y,
                origin_z,
                mushroom_x + dx,
                mushroom_y,
                mushroom_z + dz,
                block_name,
                bits,
            )
        for local_y in range(1, mushroom_y):
            mushroom_block(
                origin_x,
                floor_y,
                origin_z,
                mushroom_x,
                local_y,
                mushroom_z,
                "minecraft:mushroom_stem",
                10,
            )

    def scatter_mushroom_floor(origin_x, origin_z, floor_y, air_y):
        # Both source mushroom rooms use the same inverse-distance scatter:
        # sparse at the walls and dense around (7.5, 7.5).
        for local_x in range(1, 14):
            for local_z in range(1, 14):
                distance = math.sqrt(
                    (7.5 - local_x) ** 2 + (7.5 - local_z) ** 2
                )
                dist = max(1, int(math.floor(7.0 / distance + 0.5)))
                if rng.randrange(dist + 1) > 0:
                    result.set(
                        origin_x + local_x,
                        floor_y,
                        origin_z + local_z,
                        "minecraft:mycelium",
                    )
                if rng.randrange(dist) > 0:
                    result.set(
                        origin_x + local_x,
                        air_y,
                        origin_z + local_z,
                        "minecraft:red_mushroom"
                        if rng.randrange(2) == 0
                        else "minecraft:brown_mushroom",
                    )

    def seal_boss_room_fences(origin_x, origin_z, air_y):
        # MazeRoomBossComponent deliberately omits the 2x3 doorway cuts made
        # by MazeRoomComponent, leaving the Minoshroom enclosed on all sides.
        for side in ("north", "south", "west", "east"):
            if side in ("north", "south"):
                local_z = 0 if side == "north" else 15
                openings = ((local_x, local_z) for local_x in range(7, 9))
            else:
                local_x = 0 if side == "west" else 15
                openings = ((local_x, local_z) for local_z in range(7, 9))
            for local_x, local_z in openings:
                for y in range(air_y, air_y + 3):
                    result.set(
                        origin_x + local_x,
                        y,
                        origin_z + local_z,
                        "minecraft:oak_fence",
                    )

    def decorate_room(room_kind, origin_x, origin_z, floor_y, air_y, ceiling_y):
        prepare_room(origin_x, origin_z, floor_y, air_y, ceiling_y)
        center_x = origin_x + 7
        center_z = origin_z + 7

        if room_kind == "collapse":
            for x in range(origin_x + 1, origin_x + 15):
                for z in range(origin_z + 1, origin_z + 15):
                    distance = math.sqrt((x - center_x) ** 2 + (z - center_z) ** 2)
                    if rng.random() < max(0.0, (8.5 - distance) / 23.0):
                        height = 1 + rng.randrange(3)
                        for y in range(air_y, min(ceiling_y, air_y + height)):
                            result.set(x, y, z, "minecraft:gravel")
                    if rng.random() < 0.045:
                        result.set(x, ceiling_y - 1, z, "tf_slice:root_strand")
        elif room_kind == "exit":
            # MazeRoomExitComponent: four layers surround the upper-level
            # 4x4 fall opening. There is deliberately no ladder in this cage.
            for local_x in range(5, 11):
                for local_z in range(5, 11):
                    inner = 6 <= local_x <= 9 and 6 <= local_z <= 9
                    for local_y, block_name in (
                        (1, "tf_slice:decorative_mazestone"),
                        (2, "minecraft:iron_bars"),
                        (3, "minecraft:iron_bars"),
                        (4, "tf_slice:decorative_mazestone"),
                    ):
                        result.set(
                            origin_x + local_x,
                            floor_y + local_y,
                            origin_z + local_z,
                            "minecraft:air" if inner else block_name,
                        )
        elif room_kind == "fountain":
            for x in range(center_x - 3, center_x + 3):
                for z in range(center_z - 3, center_z + 3):
                    result.set(x, floor_y, z, "tf_slice:decorative_mazestone")
                    if center_x - 2 <= x <= center_x + 1 and center_z - 2 <= z <= center_z + 1:
                        result.set(x, air_y, z, "minecraft:water")
        elif room_kind == "spawner_chest":
            for local_x, local_z in ((3, 3), (10, 3), (3, 10), (10, 10)):
                place_pillar_enclosure(
                    origin_x, origin_z, floor_y, local_x, local_z
                )
            set_spawner(
                result, origin_x + 4, air_y + 1, origin_z + 4, "tf_slice:minotaur"
            )
            add_marker_chest(
                origin_x + 4, air_y + 1, origin_z + 11, "labyrinth_room"
            )
            add_marker_chest(
                origin_x + 11, air_y + 1, origin_z + 4, "labyrinth_room"
            )
            result.set(
                origin_x + 11,
                air_y,
                origin_z + 11,
                "minecraft:wooden_pressure_plate",
            )
            for dx, dz in ((10, 11), (11, 10), (11, 12), (12, 11)):
                # These are hidden below the four lower oak stairs of the
                # southeast enclosure, exactly as MazeRoomSpawnerChests places
                # them; the prior central cross had no cage blocks above it.
                result.set(
                    origin_x + dx,
                    floor_y,
                    origin_z + dz,
                    "minecraft:tnt",
                )
        elif room_kind in ("mushroom", "minoshroom"):
            scatter_mushroom_floor(origin_x, origin_z, floor_y, air_y)
            if room_kind == "minoshroom":
                seal_boss_room_fences(origin_x, origin_z, air_y)
                red = "minecraft:red_mushroom_block"
                brown = "minecraft:brown_mushroom_block"
                # Four source mushroom chest shelves. These are shelves/cages,
                # not free-standing giant mushrooms.
                for bounds in (
                    (1, 1, 1, 3, 1, 3),
                    (1, 2, 1, 1, 3, 4),
                    (2, 2, 1, 4, 3, 1),
                    (1, 4, 1, 3, 4, 3),
                    (12, 1, 12, 14, 1, 14),
                    (14, 2, 11, 14, 3, 14),
                    (11, 2, 14, 14, 3, 14),
                    (12, 4, 12, 14, 4, 14),
                    (1, 1, 12, 3, 1, 14),
                    (1, 2, 11, 1, 3, 14),
                    (2, 2, 14, 4, 3, 14),
                    (1, 4, 12, 3, 4, 14),
                ):
                    place_box(origin_x, floor_y, origin_z, bounds, red)
                for bounds in (
                    (12, 1, 1, 14, 1, 3),
                    (11, 2, 1, 14, 3, 1),
                    (14, 2, 2, 14, 3, 4),
                    (12, 4, 1, 14, 4, 3),
                ):
                    place_box(origin_x, floor_y, origin_z, bounds, brown)
                place_box(origin_x, floor_y, origin_z, (5, 4, 5, 7, 5, 7), brown)
                place_box(origin_x, floor_y, origin_z, (8, 4, 8, 10, 5, 10), red)
                for local_x, local_z in ((3, 3), (12, 12), (3, 12), (12, 3)):
                    add_marker_chest(
                        origin_x + local_x,
                        floor_y + 2,
                        origin_z + local_z,
                        "labyrinth_room",
                    )
                result.set(
                    center_x,
                    air_y,
                    center_z,
                    "minecraft:air",
                )
                result.set(
                    center_x,
                    floor_y + 2,
                    center_z,
                    "tf_slice:minoshroom_boss_spawner",
                )
            else:
                red = "minecraft:red_mushroom_block"
                brown = "minecraft:brown_mushroom_block"
                make_medium_mushroom(origin_x, floor_y, origin_z, 5, 2, 9, red)
                make_medium_mushroom(origin_x, floor_y, origin_z, 5, 3, 9, red)
                make_medium_mushroom(origin_x, floor_y, origin_z, 9, 2, 5, red)
                make_medium_mushroom(origin_x, floor_y, origin_z, 6, 3, 4, brown)
                make_medium_mushroom(origin_x, floor_y, origin_z, 10, 1, 9, brown)

                mushroom_block(origin_x, floor_y, origin_z, 1, 2, 1, "minecraft:mushroom_stem", 10)
                mushroom_block(origin_x, floor_y, origin_z, 1, 3, 1, red, 5)
                mushroom_block(origin_x, floor_y, origin_z, 2, 3, 1, red, 6)
                mushroom_block(origin_x, floor_y, origin_z, 1, 3, 2, red, 8)
                mushroom_block(origin_x, floor_y, origin_z, 14, 3, 1, "minecraft:mushroom_stem", 10)
                mushroom_block(origin_x, floor_y, origin_z, 14, 4, 1, brown, 5)
                mushroom_block(origin_x, floor_y, origin_z, 13, 4, 1, brown, 4)
                mushroom_block(origin_x, floor_y, origin_z, 14, 4, 2, brown, 8)
                mushroom_block(origin_x, floor_y, origin_z, 1, 1, 14, "minecraft:mushroom_stem", 10)
                mushroom_block(origin_x, floor_y, origin_z, 1, 2, 14, brown, 5)
                mushroom_block(origin_x, floor_y, origin_z, 2, 2, 14, brown, 6)
                mushroom_block(origin_x, floor_y, origin_z, 1, 2, 13, brown, 2)
                mushroom_block(origin_x, floor_y, origin_z, 14, 1, 14, brown, 5)
                mushroom_block(origin_x, floor_y, origin_z, 13, 1, 14, brown, 4)
                mushroom_block(origin_x, floor_y, origin_z, 14, 1, 13, brown, 2)
        elif room_kind == "vault":
            # The source vault is a sealed brick mass with a decorated central trap.
            for x in range(origin_x + 1, origin_x + 15):
                for z in range(origin_z + 1, origin_z + 15):
                    if not (
                        center_x - 2 <= x <= center_x + 2
                        and center_z - 2 <= z <= center_z + 2
                    ):
                        for y in range(air_y, ceiling_y):
                            result.set(x, y, z, "tf_slice:mazestone_brick")
            for x in range(center_x - 2, center_x + 3):
                for z in range(center_z - 2, center_z + 3):
                    if x in (center_x - 2, center_x + 2) or z in (
                        center_z - 2,
                        center_z + 2,
                    ):
                        result.set(x, floor_y, z, "minecraft:tnt")
                        result.set(
                            x, air_y, z, "minecraft:wooden_pressure_plate"
                        )
            chest_sites = (
                (center_x - 1, center_z - 1),
                (center_x + 1, center_z - 1),
                (center_x - 1, center_z + 1),
                (center_x + 1, center_z + 1),
            )
            for index, (chest_x, chest_z) in enumerate(chest_sites):
                loot_kind = "labyrinth_jackpot" if index == seed % 4 else "labyrinth_vault"
                add_marker_chest(chest_x, air_y + 1, chest_z, loot_kind)

        return center_x, center_z

    def cell_openings(raw, raw_width, raw_depth, cell_x, cell_z):
        raw_x = cell_x * 2 + 1
        raw_z = cell_z * 2 + 1
        openings = []
        for direction, dx, dz in (
            ("east", 1, 0),
            ("west", -1, 0),
            ("south", 0, 1),
            ("north", 0, -1),
        ):
            if _maze_raw_get(raw, raw_width, raw_depth, raw_x + dx, raw_z + dz) not in (0, None):
                openings.append((direction, dx, dz))
        return openings

    def corridor_has_source_side_walls(
        raw, raw_width, raw_depth, cell_x, cell_z, openings
    ):
        """Match MinotaurMazeComponent's eight corridor wall predicates."""
        raw_x = cell_x * 2 + 1
        raw_z = cell_z * 2 + 1
        north_south = all(dx == 0 for _direction, dx, _dz in openings)
        if north_south:
            checks = (
                (raw_x - 1, raw_z - 2),
                (raw_x + 1, raw_z - 2),
                (raw_x - 1, raw_z + 2),
                (raw_x + 1, raw_z + 2),
            )
        else:
            checks = (
                (raw_x - 2, raw_z - 1),
                (raw_x - 2, raw_z + 1),
                (raw_x + 2, raw_z - 1),
                (raw_x + 2, raw_z + 1),
            )
        return all(
            _maze_raw_get(raw, raw_width, raw_depth, x, z) in (0, None)
            for x, z in checks
        )

    def place_dead_end(
        kind,
        cell_x,
        cell_z,
        floor_y,
        air_y,
        ceiling_y,
        opening,
        raw_cell_value,
    ):
        origin_x = 1 + cell_x * cell_pitch
        origin_z = 1 + cell_z * cell_pitch
        direction = opening[0]

        def transform(local_x, local_z):
            if direction == "north":
                return origin_x + local_x, origin_z + local_z
            if direction == "south":
                return origin_x + local_x, origin_z + 5 - local_z
            if direction == "west":
                return origin_x + local_z, origin_z + local_x
            return origin_x + 5 - local_z, origin_z + local_x

        def transform_facing(local_facing):
            # MinotaurMazeComponent passes the component orientation opposite
            # the open side of a dead end. TFStructureComponentOld then
            # rotates block states by that component orientation. Coordinates
            # here are already transformed into the open-side frame, so the
            # state mapping must reproduce the source's opposite rotation.
            maps = {
                "north": {
                    "north": "south",
                    "south": "north",
                    "west": "east",
                    "east": "west",
                },
                "south": {
                    "north": "north",
                    "south": "south",
                    "west": "west",
                    "east": "east",
                },
                "west": {
                    "north": "east",
                    "south": "west",
                    "west": "north",
                    "east": "south",
                },
                "east": {
                    "north": "west",
                    "south": "east",
                    "west": "south",
                    "east": "north",
                },
            }
            return maps[direction][local_facing]

        def transform_support_direction(local_direction):
            # Bedrock torch_facing_direction points at the backing block,
            # unlike Java WallTorchBlock.FACING, which points away from it.
            # Transform the physical local support vector with the coordinate
            # frame instead of reusing the component block-state rotation.
            maps = {
                "north": {
                    "north": "north",
                    "south": "south",
                    "west": "west",
                    "east": "east",
                },
                "south": {
                    "north": "south",
                    "south": "north",
                    "west": "west",
                    "east": "east",
                },
                "west": {
                    "north": "west",
                    "south": "east",
                    "west": "north",
                    "east": "south",
                },
                "east": {
                    "north": "east",
                    "south": "west",
                    "west": "north",
                    "east": "south",
                },
            }
            return maps[direction][local_direction]

        def set_local(local_x, local_y, local_z, block, states=None):
            x, z = transform(local_x, local_z)
            result.set(x, floor_y + local_y, z, block, states)
            return [x, floor_y + local_y, z]

        if kind not in ("chest", "trap"):
            # The base dead-end owns this fence arch. Chest variants replace
            # it with their source decorative lintel and double iron-bar gate.
            for local_x in range(1, 5):
                for local_y in range(1, 5):
                    set_local(local_x, local_y, 0, "minecraft:oak_fence")
            for local_x in range(2, 4):
                for local_y in range(1, 4):
                    set_local(local_x, local_y, 0, "minecraft:air")

        far_x, far_z = transform(2, 4)
        source_offsets = []
        receptacle_offsets = []
        if kind in ("chest", "trap"):
            trapped = kind == "trap"
            chest_block = (
                "minecraft:trapped_chest" if trapped else "minecraft:chest"
            )
            chest_states = {
                "facing_direction": FACING_DIRECTIONS[
                    transform_facing("south")
                ]
            }

            # MazeDeadEndChestComponent / MazeDeadEndTrappedChestComponent:
            # a two-wide stair-and-plank dais carrying a double chest.
            chest_positions = []
            for local_x in (2, 3):
                stair_x, stair_z = transform(local_x, 3)
                _set_oak_stair(
                    result,
                    stair_x,
                    floor_y + 1,
                    stair_z,
                    transform_facing("north"),
                )
                set_local(local_x, 1, 4, "minecraft:oak_planks")
                chest_x, chest_z = transform(local_x, 4)
                add_marker_chest(
                    chest_x,
                    floor_y + 2,
                    chest_z,
                    "labyrinth_dead_end",
                    block=chest_block,
                    states=chest_states,
                )
                chest_positions.append((chest_x, floor_y + 2, chest_z))

            # Bedrock does not reliably infer a double chest when two block
            # entities arrive together in an mcstructure. Pair both halves
            # explicitly so the source's one large chest is preserved.
            for index, position in enumerate(chest_positions):
                other = chest_positions[1 - index]
                name, states, block_entity = result.blocks[position]
                paired_entity = dict(block_entity)
                paired_entity.update(
                    {
                        "pairx": other[0],
                        "pairz": other[2],
                        "pairlead": index == 0,
                    }
                )
                result.blocks[position] = (name, states, paired_entity)

            if trapped:
                # Four TNT blocks are fully concealed by the two stairs and
                # two planks. They are never part of the visible floor.
                for local_x in (2, 3):
                    for local_z in (3, 4):
                        set_local(local_x, 0, local_z, "minecraft:tnt")

            # Source chest dead ends have a thick barred gate and decorative
            # cap instead of the ordinary fence arch.
            for local_x in range(1, 5):
                for local_z in (0, 1):
                    for local_y in range(1, 4):
                        set_local(
                            local_x,
                            local_y,
                            local_z,
                            "tf_slice:cut_mazestone",
                        )
                    set_local(
                        local_x,
                        4,
                        local_z,
                        "tf_slice:decorative_mazestone",
                    )
            for local_x in (2, 3):
                for local_z in (0, 1):
                    for local_y in range(1, 4):
                        set_local(
                            local_x,
                            local_y,
                            local_z,
                            "minecraft:iron_bars",
                        )
        elif kind == "torches":
            # MazeDeadEndTorchesComponent fills three walls with oriented
            # wall torches. Bedrock represents both standing and wall torches
            # as minecraft:torch, distinguished by torch_facing_direction.
            for local_x in (2, 3):
                for local_y in range(1, 5):
                    set_local(
                        local_x,
                        local_y,
                        4,
                        "minecraft:torch",
                        {
                            "torch_facing_direction": transform_support_direction(
                                "south"
                            )
                        },
                    )
            for local_z in range(1, 5):
                for local_y in range(1, 5):
                    for local_x, local_facing in ((1, "west"), (4, "east")):
                        set_local(
                            local_x,
                            local_y,
                            local_z,
                            "minecraft:torch",
                            {
                                "torch_facing_direction": transform_support_direction(
                                    local_facing
                                )
                            },
                        )
        elif kind in ("water", "lava"):
            liquid = "minecraft:water" if kind == "water" else "minecraft:lava"
            # MazeDeadEndFountainComponent uses a solid rear wall with two
            # elevated sources that fall into a pair of floor receptacles.
            # A source directly on the open floor spreads through the maze.
            for local_x in range(1, 5):
                for local_y in range(1, 5):
                    set_local(
                        local_x,
                        local_y,
                        4,
                        "tf_slice:mazestone_brick",
                    )
            for local_x in (2, 3):
                source_offsets.append(set_local(local_x, 3, 4, liquid))
                receptacle_offsets.append(
                    set_local(local_x, 0, 3, "minecraft:air")
                )
        elif kind == "roots":
            for dx, dz in ((0, 0), (1, 0), (0, 1)):
                x, z = transform(2 + dx, 2 + dz)
                result.set(x, ceiling_y - 1, z, "tf_slice:root_strand")
        elif kind == "shrooms":
            result.set(far_x, air_y, far_z, "minecraft:red_mushroom")
            x, z = transform(3, 3)
            result.set(x, air_y, z, "minecraft:brown_mushroom")
        decorations.append(
            {
                "component": "dead_end",
                "kind": kind,
                "offset": [origin_x + 2, air_y, origin_z + 2],
                "origin": [origin_x, floor_y, origin_z],
                "opening": direction,
                "floorY": floor_y,
                "sourceOffsets": source_offsets,
                "receptacleOffsets": receptacle_offsets,
                "rawCellValue": raw_cell_value,
            }
        )

    def place_corridor(
        kind,
        cell_x,
        cell_z,
        floor_y,
        air_y,
        ceiling_y,
        openings,
        raw_cell_value,
        side_walls_verified,
    ):
        origin_x = 1 + cell_x * cell_pitch
        origin_z = 1 + cell_z * cell_pitch
        north_south = all(dx == 0 for _direction, dx, _dz in openings)

        def transform(local_x, local_z):
            if north_south:
                return origin_x + local_x, origin_z + local_z
            return origin_x + local_z, origin_z + local_x

        def set_local(local_x, local_y, local_z, block):
            x, z = transform(local_x, local_z)
            result.set(x, floor_y + local_y, z, block)

        if kind == "fence_arch":
            for local_x in range(1, 5):
                for local_z in range(2, 4):
                    for local_y in range(1, 5):
                        set_local(
                            local_x, local_y, local_z, "minecraft:oak_fence"
                        )
            for local_x in range(2, 4):
                for local_z in range(2, 4):
                    for local_y in range(1, 4):
                        set_local(local_x, local_y, local_z, "minecraft:air")
        elif kind == "iron_gate":
            for local_x in range(1, 5):
                for local_z in range(2, 4):
                    set_local(
                        local_x,
                        4,
                        local_z,
                        "tf_slice:decorative_mazestone",
                    )
                    for local_y in range(1, 4):
                        set_local(
                            local_x,
                            local_y,
                            local_z,
                            "tf_slice:cut_mazestone",
                        )
            for local_x in range(2, 4):
                for local_z in range(2, 4):
                    for local_y in range(1, 4):
                        set_local(
                            local_x,
                            local_y,
                            local_z,
                            "minecraft:iron_bars",
                        )
        elif kind == "roots":
            for local_x, local_z in ((2, 2), (3, 3)):
                x, z = transform(local_x, local_z)
                result.set(x, ceiling_y - 1, z, "tf_slice:root_strand")
        elif kind == "shrooms":
            for local_x, local_z, block in (
                (1, 1, "minecraft:brown_mushroom"),
                (4, 4, "minecraft:red_mushroom"),
            ):
                x, z = transform(local_x, local_z)
                result.set(x, air_y, z, block)
        decorations.append(
            {
                "component": "corridor",
                "kind": kind,
                "offset": [origin_x + 2, air_y, origin_z + 2],
                "origin": [origin_x, floor_y, origin_z],
                "orientation": "north_south" if north_south else "east_west",
                "rawCellValue": raw_cell_value,
                "sideWallsVerified": bool(side_walls_verified),
            }
        )

    # The source creates the lower bedrock envelope first, then clears the
    # 110x110 interior and renders maze walls over its visible boundary.
    # Rendering the shell last overwrites those walls with exposed bedrock.
    for x in range(result.size[0]):
        for z in range(result.size[2]):
            result.set(x, 0, z, "minecraft:bedrock")
            result.set(x, 7, z, "minecraft:bedrock")
            if x in (0, result.size[0] - 1) or z in (
                0,
                result.size[2] - 1,
            ):
                for y in range(0, 8):
                    result.set(x, y, z, "minecraft:bedrock")

    raw_levels = []
    component_serial = 0
    for level_index, (floor_y, air_y, ceiling_y) in enumerate(levels):
        raw, raw_width, raw_depth, _room_cells = level_layouts[level_index]
        raw_levels.append((raw, raw_width, raw_depth))
        _place_source_maze_level(
            result,
            raw,
            raw_width,
            raw_depth,
            floor_y,
            seed * 2 + level_index,
        )

        dead_end_pool = (
            "chest",
            "trap",
            "torches",
            "water",
            "lava",
            "torches",
            "roots" if level_index == 0 else "shrooms",
        )
        corridor_pool = (
            "none",
            "fence_arch",
            "iron_gate",
            "none",
            "roots" if level_index == 0 else "shrooms",
        )
        for cell_z in range(grid):
            for cell_x in range(grid):
                # The source component bounding boxes need one complete 5x5
                # cell. Do not decorate the outer ring where the lower-level
                # bedrock shell or the maze boundary would clip the piece.
                if cell_x in (0, grid - 1) or cell_z in (0, grid - 1):
                    continue
                raw_x = cell_x * 2 + 1
                raw_z = cell_z * 2 + 1
                raw_cell_value = _maze_raw_get(
                    raw, raw_width, raw_depth, raw_x, raw_z
                )
                # ROOM cells have raw value 5. Treating them as normal cells
                # adds components that the later 16x16 room pass clips into
                # the disconnected fence/gate fragments seen in game.
                if raw_cell_value != 1:
                    continue
                openings = cell_openings(
                    raw, raw_width, raw_depth, cell_x, cell_z
                )
                if len(openings) == 1:
                    kind = dead_end_pool[(component_serial + seed) % len(dead_end_pool)]
                    place_dead_end(
                        kind,
                        cell_x,
                        cell_z,
                        floor_y,
                        air_y,
                        ceiling_y,
                        openings[0],
                        raw_cell_value,
                    )
                    component_serial += 1
                elif len(openings) == 2:
                    straight = openings[0][1] == -openings[1][1] and openings[0][2] == -openings[1][2]
                    side_walls_verified = (
                        straight
                        and corridor_has_source_side_walls(
                            raw,
                            raw_width,
                            raw_depth,
                            cell_x,
                            cell_z,
                            openings,
                        )
                    )
                    if side_walls_verified:
                        kind = corridor_pool[(component_serial + seed) % len(corridor_pool)]
                        if kind != "none":
                            place_corridor(
                                kind,
                                cell_x,
                                cell_z,
                                floor_y,
                                air_y,
                                ceiling_y,
                                openings,
                                raw_cell_value,
                                side_walls_verified,
                            )
                        component_serial += 1

        for room_index, room_kind in enumerate(level_room_kinds[level_index]):
            cell = level_room_cells[level_index][room_index]
            origin_x, origin_z = room_origin(cell)
            center_x, center_z = decorate_room(
                room_kind, origin_x, origin_z, floor_y, air_y, ceiling_y
            )
            rooms_meta.append(
                {
                    "kind": room_kind,
                    "level": level_index,
                    "offset": [center_x, air_y, center_z],
                    "origin": [origin_x, floor_y, origin_z],
                    "size": [16, 5, 16],
                }
            )
            spawn_zones.append(
                {
                    "level": level_index,
                    "center": [center_x, air_y, center_z],
                    "radius": 7,
                }
            )

    upper_exit = next(
        room for room in rooms_meta if room["level"] == 0 and room["kind"] == "exit"
    )
    exit_origin_x, upper_floor_y, exit_origin_z = upper_exit["origin"]

    def build_source_fall_shaft(
        origin_x, origin_z, minimum_y, maximum_y, preserve_top_ring=False
    ):
        """Build the source 6x6 shell around a ladder-free 4x4 fall pit."""
        for y in range(int(minimum_y), int(maximum_y) + 1):
            for local_x in range(5, 11):
                for local_z in range(5, 11):
                    boundary = local_x in (5, 10) or local_z in (5, 10)
                    position = (origin_x + local_x, y, origin_z + local_z)
                    if boundary:
                        if not (
                            preserve_top_ring
                            and y == int(maximum_y)
                            and result.blocks.get(position, ("minecraft:air",))[0]
                            != "minecraft:air"
                        ):
                            result.set(
                                position[0],
                                position[1],
                                position[2],
                                "tf_slice:mazestone_brick",
                            )
                    else:
                        result.set(
                            position[0],
                            position[1],
                            position[2],
                            "minecraft:air",
                        )

    build_source_fall_shaft(
        exit_origin_x,
        exit_origin_z,
        levels[1][2],
        upper_floor_y,
        preserve_top_ring=True,
    )

    # Recreate the surface pieces from MazeMoundComponent,
    # MazeUpperEntranceComponent and MazeEntranceShaftComponent. The mound leaves
    # a central hole and four open approaches instead of becoming a solid disk.
    upper_entrance = next(
        room
        for room in rooms_meta
        if room["level"] == 0 and room["kind"] == "entrance"
    )
    entrance_x, _entrance_y, entrance_z = upper_entrance["offset"]
    entrance_origin_x = upper_entrance["origin"][0]
    entrance_origin_z = upper_entrance["origin"][2]
    surface_columns = {}
    mound_origin_x = entrance_x - 17
    mound_origin_z = entrance_z - 17
    for local_x in range(35):
        for local_z in range(35):
            cx = local_x - 17
            cz = local_z - 17
            distance = int(math.sqrt(cx * cx + cz * cz))
            mound_height = int(
                math.cos(float(distance) / 35.0 * math.pi) * (35 // 3)
            )
            # Negative-height edge writes are buried by Java terrain. Omitting
            # them in a fixed Bedrock template avoids replacing native soil
            # below the visible mound with an artificial grass shelf.
            if mound_height < 0:
                continue
            x = mound_origin_x + local_x
            z = mound_origin_z + local_z
            central_hole = -1 <= cx <= 2 and -1 <= cz <= 2
            cross_column = -1 <= cx <= 2 or -1 <= cz <= 2
            # Every visible mound-footprint column needs a ground-height base
            # so the surface envelope cannot leave vertical foundation gaps
            # along the shaft or four approaches.
            result.set(x, surface_ground_y, z, "minecraft:grass_block")
            surface_columns[(x, z)] = surface_ground_y
            if central_hole:
                continue
            if cross_column:
                for y in range(surface_ground_y + 1, surface_ground_y + 6):
                    result.set(x, y, z, "minecraft:air")
                if mound_height <= 6:
                    continue
            top = surface_ground_y + mound_height
            if cross_column:
                for y in range(surface_ground_y + 6, top):
                    result.set(x, y, z, "minecraft:dirt")
            else:
                result.set(x, top - 1, z, "minecraft:dirt")
            result.set(x, top, z, "minecraft:grass_block")
            surface_columns[(x, z)] = top

    entrance_rng = random.Random(seed ^ 0x55505045)
    # Five source layers: mosaic floor, decorative band, two brick courses,
    # decorative cornice. The interior is then hollowed exactly as upstream.
    for local_x in range(16):
        for local_z in range(16):
            x = entrance_origin_x + local_x
            z = entrance_origin_z + local_z
            result.set(x, surface_ground_y, z, "tf_slice:mazestone_mosaic")
            result.set(
                x,
                surface_ground_y + 1,
                z,
                "tf_slice:decorative_mazestone",
            )
            for y in (surface_ground_y + 2, surface_ground_y + 3):
                result.set(x, y, z, "tf_slice:mazestone_brick")
            result.set(
                x,
                surface_ground_y + 4,
                z,
                "tf_slice:decorative_mazestone",
            )
            if entrance_rng.random() < 0.7:
                result.set(x, surface_ground_y + 5, z, "tf_slice:mazestone")
            else:
                result.set(x, surface_ground_y + 5, z, "minecraft:air")

    for local_x in range(1, 15):
        for local_z in range(1, 15):
            for y in range(surface_ground_y + 1, surface_ground_y + 5):
                result.set(
                    entrance_origin_x + local_x,
                    y,
                    entrance_origin_z + local_z,
                    "minecraft:air",
                )

    for side in ("north", "south", "west", "east"):
        place_room_fence_panel(
            entrance_origin_x,
            entrance_origin_z,
            surface_ground_y + 1,
            side,
        )

    # Decorative pit rim plus the source's partially broken iron-bar cage.
    for local_x in range(5, 11):
        for local_z in range(5, 11):
            for local_y in (1, 4):
                result.set(
                    entrance_origin_x + local_x,
                    surface_ground_y + local_y,
                    entrance_origin_z + local_z,
                    "tf_slice:decorative_mazestone",
                )
            for local_y in (2, 3):
                if entrance_rng.random() < 0.7:
                    result.set(
                        entrance_origin_x + local_x,
                        surface_ground_y + local_y,
                        entrance_origin_z + local_z,
                        "minecraft:iron_bars",
                    )

    # MazeEntranceShaftComponent ends at the maze roof. The 4x4 opening drops
    # through that roof into an otherwise ordinary entrance room; extending
    # the shell to the room floor creates the incorrect freestanding booth.
    build_source_fall_shaft(
        entrance_origin_x,
        entrance_origin_z,
        levels[0][2],
        surface_ground_y,
        preserve_top_ring=True,
    )

    # Re-open the 4x4 pit through the upper entrance floor and cage. This is
    # deliberately last so neither roof decay nor mound fill can plug it.
    for local_x in range(6, 10):
        for local_z in range(6, 10):
            for y in range(surface_ground_y, result.size[1]):
                result.set(
                    entrance_origin_x + local_x,
                    y,
                    entrance_origin_z + local_z,
                    "minecraft:air",
                )
    # Reopening the surface pit removes only the 4x4 void; the source rim and
    # shaft shell remain intact around it.

    boss_room = next(room for room in rooms_meta if room["kind"] == "minoshroom")
    boss_offset = [
        boss_room["offset"][0],
        boss_room["origin"][1] + 2,
        boss_room["offset"][2],
    ]
    result.surface_ground_y = surface_ground_y
    result.surface_columns = surface_columns
    result.surface_core_radius = 18
    result.surface_core_center = (entrance_x, entrance_z)
    result.landmark_metadata = {
        "markerPolicy": "physical_boss_spawner_and_catalog",
        "boss": {"kind": "minoshroom", "offset": boss_offset},
        "mapCenter": [entrance_x, levels[0][1], entrance_z],
        "chests": marker_chests,
        "spawnZones": spawn_zones,
        "rooms": rooms_meta,
        "decorations": decorations,
        "surfaceEntrance": {
            "origin": [
                entrance_origin_x,
                surface_ground_y,
                entrance_origin_z,
            ],
            "moundDiameter": 35,
            "crossTunnelWidth": 4,
            "shaftOuter": [6, 6],
            "shaftInner": [4, 4],
        },
        "levels": [levels[0][1], levels[1][1]],
        "ceilings": [levels[0][2], levels[1][2]],
        "mazeGrid": [grid, grid],
        "cellPitch": cell_pitch,
        "corridorWidth": 4,
        "mazeRandomSource": "minecraft:legacy_random_source",
        "mazeSeeds": [seed * 2, seed * 2 + 1],
        "wallPalettePercent": {"brick": 50, "cracked": 30, "mossy": 20},
        "levelOffset": 10,
        "lowerBedrockShell": True,
        "mapPassageRuns": {
            str(levels[0][1]): _maze_passage_runs(result, levels[0][1]),
            str(levels[1][1]): _maze_passage_runs(result, levels[1][1]),
        },
        "connected": True,
    }
    return result


def hydra_lair_structure(seed):
    """Compile the source ``raiseHills`` Hydra mound and cavern geology."""
    rng = random.Random(int(seed) ^ 0x48594452)
    ground_y = 16
    hill_size = 2
    hill_diameter = float((hill_size * 2 + 1) * 16)
    terrain_radius = hill_diameter / 2.0
    maximum_surface_y = ground_y + int(hill_diameter / 3.0)
    result = SparseStructure(
        (80, maximum_surface_y + 1, 80),
        "hydra_lair_%02d" % seed,
    )
    center = 40
    ceiling_by_column = {}
    surface_columns = {}
    open_columns = set()

    for x in range(80):
        for z in range(80):
            delta_x = x - center
            delta_z = z - center
            distance = math.sqrt(delta_x ** 2 + delta_z ** 2)
            if distance > terrain_radius:
                continue

            # ChunkGeneratorTwilight.raiseHills uses this 80-block cosine
            # profile.  Its floor is the Fire Swamp surface/sea level; only
            # the mound rises, so the arena must never be sunk below ground.
            hill_height = max(
                0,
                int(
                    math.cos(distance / hill_diameter * math.pi)
                    * (hill_diameter / 3.0)
                ),
            )
            surface_y = ground_y + hill_height

            # Base hollow: min(hillHeight - 4 - size, totalHeight - 3).
            # With an unperturbed local surface the first term is the limit.
            hollow_height = hill_height - 4 - hill_size

            # The original Hydra-only branch raises the hollow around
            # feature (-16, -16), removing a northwest piece of the mound.
            # This is a cutaway flank, not an east-facing tunnel or crater.
            mouth_dx = delta_x + 16
            mouth_dz = delta_z + 16
            mouth_distance = int(
                math.sqrt(mouth_dx * mouth_dx + mouth_dz * mouth_dz)
            )
            mouth_diameter = hill_diameter / 1.5
            mouth_height = int(
                math.cos(mouth_distance / mouth_diameter * math.pi)
                * mouth_diameter
            )
            hollow_height = max(mouth_height - 4, hollow_height)
            mouth = hollow_height > hill_height
            if mouth:
                open_columns.add((x, z))

            # Keep only a shallow authored floor/support. Native terrain
            # already supplies everything farther below the surface.
            for y in range(ground_y - 2, ground_y + 1):
                result.set(x, y, z, "minecraft:stone")

            for y in range(ground_y + 1, max(ground_y + 1, surface_y - 2)):
                result.set(x, y, z, "minecraft:stone")
            for y in range(max(ground_y + 1, surface_y - 2), surface_y):
                result.set(x, y, z, "minecraft:dirt")
            result.set(x, surface_y, z, "minecraft:grass_block")

            cave_ceiling = ground_y + max(0, hollow_height)
            ceiling_by_column[(x, z)] = cave_ceiling
            for y in range(ground_y + 1, min(result.size[1], cave_ceiling)):
                result.set(x, y, z, "minecraft:air")

            if mouth:
                # Source terrain continues clearing above the authored mound;
                # explicit air is needed here to cut any generated shell.
                for y in range(
                    max(ground_y + 1, cave_ceiling),
                    result.size[1],
                ):
                    result.set(x, y, z, "minecraft:air")
            else:
                surface_columns[(x, z)] = surface_y

    ore_positions = []
    stone_positions = []
    stalagmites = []
    candidates = [
        (x, z)
        for (x, z), ceiling in ceiling_by_column.items()
        if (
            (x, z) not in open_columns
            and 7 < math.sqrt((x - center) ** 2 + (z - center) ** 2) < 34
            and ceiling >= ground_y + 7
        )
    ]
    rng.shuffle(candidates)

    candidate_index = 0
    while len(ore_positions) < 64 and candidate_index < len(candidates):
        x, z = candidates[candidate_index]
        candidate_index += 1
        ceiling = ceiling_by_column[(x, z)]
        config = _hollow_hill_spike_config(rng, 2)
        if _place_hollow_hill_spike(
            result,
            rng,
            x,
            ceiling - 1,
            z,
            ceiling - 3,
            True,
            config,
        ):
            ore_positions.append([x, ceiling - 1, z])

    stone_config = ((('minecraft:stone', 1),), 11, 0.25, 1)
    while len(stone_positions) < 64 and candidate_index < len(candidates):
        x, z = candidates[candidate_index]
        candidate_index += 1
        ceiling = ceiling_by_column[(x, z)]
        if _place_hollow_hill_spike(
            result,
            rng,
            x,
            ceiling - 1,
            z,
            ceiling - 3,
            True,
            stone_config,
        ):
            stone_positions.append([x, ceiling - 1, z])

    while len(stalagmites) < 8 and candidate_index < len(candidates):
        x, z = candidates[candidate_index]
        candidate_index += 1
        ceiling = ceiling_by_column[(x, z)]
        if _place_hollow_hill_spike(
            result,
            rng,
            x,
            ground_y + 1,
            z,
            ceiling - ground_y - 1,
            False,
            stone_config,
        ):
            stalagmites.append([x, ground_y + 1, z])

    boss_offset = [center, ground_y, center]
    result.set(
        boss_offset[0],
        boss_offset[1],
        boss_offset[2],
        "tf_slice:hydra_boss_spawner",
    )
    result.surface_ground_y = ground_y
    result.surface_columns = surface_columns
    result.surface_core_radius = 39

    result.landmark_metadata = {
        "markerPolicy": "physical_boss_spawner_and_catalog",
        "boss": {"kind": "hydra", "offset": boss_offset},
        "mapCenter": [center, ground_y, center],
        "chests": [],
        "spawnZones": [{"center": [center, ground_y, center], "radius": 32}],
        "geology": {
            "oreStalactites": ore_positions,
            "stoneStalactites": stone_positions,
            "stalagmites": stalagmites,
        },
        "terrainShape": "open_wedge",
        "featureRadius": 34,
        "entranceDirection": "northwest",
    }
    return result


HEDGE_MAZE_VARIANT_COUNT = 8
NAGA_COURTYARD_VARIANT_COUNT = 8
# The source terrace branch remains 1/150.  A finite eight-template bank
# needs stratified seeds, however, or its rare statue branch is permanently
# absent.  These samples retain water in every layout and one source-selected
# statue layout without changing the generator itself.
COURTYARD_VARIANT_SEEDS = (1, 2, 3, 4, 5, 6, 7, 137)
MUSHROOM_TOWER_VARIANT_COUNT = 8
LICH_TOWER_VARIANT_COUNT = 8


def _weighted_hollow_hill_spike(rng, configs):
    total_weight = sum(config[3] for config in configs)
    roll = rng.randrange(total_weight)
    for config in configs:
        roll -= config[3]
        if roll < 0:
            return config
    return configs[-1]


def _hollow_hill_spike_config(rng, landmark_size):
    if landmark_size >= 3 and rng.randrange(5) == 0:
        pool = HOLLOW_HILL_SPIKES["large"]
    elif landmark_size >= 2 and rng.randrange(5) == 0:
        pool = HOLLOW_HILL_SPIKES["medium"]
    else:
        pool = HOLLOW_HILL_SPIKES["small"]
    return _weighted_hollow_hill_spike(rng, pool)


def _hollow_hill_spike_block(rng, blocks):
    total_weight = sum(weight for _, weight in blocks)
    roll = rng.randrange(total_weight)
    for block_name, weight in blocks:
        roll -= weight
        if roll < 0:
            return block_name
    return blocks[-1][0]


def _place_hollow_hill_spike(
    structure,
    rng,
    x,
    start_y,
    z,
    available_length,
    hanging,
    config,
):
    blocks, maximum_length, size_variation, _weight = config
    minimum_length = int(maximum_length * size_variation)
    sampled_length = rng.randint(minimum_length, maximum_length)
    length = min(sampled_length, max(0, int(available_length)))
    if length < minimum_length:
        return False

    diameter = int(length / 4.5)
    direction = -1 if hanging else 1
    for delta_x in range(-diameter, diameter + 1):
        for delta_z in range(-diameter, diameter + 1):
            absolute_x = abs(delta_x)
            absolute_z = abs(delta_z)
            distance = int(
                max(absolute_x, absolute_z)
                + min(absolute_x, absolute_z) * 0.5
            )
            if distance <= 0:
                column_length = length
            else:
                upper_bound = int(length / (distance + 0.25))
                if upper_bound <= 0:
                    continue
                column_length = rng.randrange(upper_bound)
            for index in range(column_length):
                block_y = start_y + index * direction
                existing = structure.blocks.get(
                    (x + delta_x, block_y, z + delta_z)
                )
                if existing is None or existing[0] != "minecraft:air":
                    continue
                structure.set(
                    x + delta_x,
                    block_y,
                    z + delta_z,
                    _hollow_hill_spike_block(rng, blocks),
                )
    return True


def _hollow_hill_floor_y(landmark_size, terrain_diameter, distance):
    height = (
        landmark_size * 2
        - math.cos(distance / float(terrain_diameter) * math.pi)
        * (terrain_diameter / 20.0)
        + 1
    )
    return int(math.floor(height + 0.25))


def _hollow_hill_ceiling_y(terrain_diameter, distance):
    height = (
        math.cos(distance / float(terrain_diameter) * math.pi)
        * (terrain_diameter / 4.0)
    )
    return int(math.ceil(height))


def _hollow_hill_lattice(terrain_diameter):
    spacing = 3.75
    x_offset = math.cos(math.pi / 6.0) * spacing
    z_offset = math.sin(math.pi / 6.0) * spacing
    x_spacing = x_offset * 2.0
    for offset_x, offset_z in ((0.0, 0.0), (x_offset, z_offset)):
        row = 0
        while offset_x + row * x_spacing < terrain_diameter:
            column = 0
            while offset_z + column * spacing < terrain_diameter:
                yield (
                    int(round(offset_x + row * x_spacing)),
                    int(round(offset_z + column * spacing)),
                )
                column += 1
            row += 1


def hollow_hill(diameter, seed, split_layers=False, terrain_seed=None):
    landmark_size = {36: 1, 68: 2, 100: 3}[diameter]
    terrain_diameter = (landmark_size * 2 + 1) * 16
    underground_offset = ruin_logic.hollow_hill_piece_depth(landmark_size)
    dome_height = int(terrain_diameter / 3.0) + 1
    height = underground_offset + dome_height
    result = SparseStructure(
        (terrain_diameter, height, terrain_diameter),
        "hollow_hill_%d" % diameter,
    )
    center = (terrain_diameter - 1) / 2.0
    terrain_radius = terrain_diameter / 2.0
    hollow_radius = diameter / 2.0
    rng = random.Random(0x48494C4C + seed + diameter)
    if terrain_seed is None:
        terrain_seed = seed

    for x in range(terrain_diameter):
        for z in range(terrain_diameter):
            horizontal = math.sqrt((x - center) ** 2 + (z - center) ** 2)
            if horizontal > terrain_radius:
                continue

            # Port of ChunkGeneratorTwilight.deformTerrainForFeature:
            # distance is truncated before the cosine mound is evaluated.
            surface_height = int(
                math.cos(
                    int(horizontal)
                    / float(terrain_diameter)
                    * math.pi
                )
                * (terrain_diameter / 3.0)
            )
            surface_height += ruin_logic.hollow_hill_terrain_detail(
                terrain_seed,
                x,
                z,
                terrain_radius,
                2,
            )
            if horizontal >= hollow_radius:
                continue
            floor_y = _hollow_hill_floor_y(
                landmark_size,
                terrain_diameter,
                horizontal,
            )
            ceiling_y = _hollow_hill_ceiling_y(
                terrain_diameter,
                horizontal,
            )
            result.set(x, floor_y, z, "minecraft:stone")
            for y in range(floor_y + 1, min(ceiling_y, height)):
                result.set(x, y, z, "minecraft:air")

    shell_blocks = dict(result.blocks)
    shortened_radius_squared = hollow_radius * hollow_radius * 0.85
    size_name = {1: "small", 2: "medium", 3: "large"}[landmark_size]
    stone_spike = (
        (("minecraft:stone", 1),),
        11,
        0.25,
        1,
    )
    for x, z in _hollow_hill_lattice(terrain_diameter):
        distance_squared = (x - center) ** 2 + (z - center) ** 2
        if distance_squared > shortened_radius_squared:
            continue
        horizontal = math.sqrt(distance_squared)
        floor_y = _hollow_hill_floor_y(
            landmark_size,
            terrain_diameter,
            horizontal,
        )
        ceiling_y = _hollow_hill_ceiling_y(
            terrain_diameter,
            horizontal,
        )
        open_height = ceiling_y - floor_y - 1
        if open_height < 2:
            continue

        ceiling_config = (
            _hollow_hill_spike_config(rng, landmark_size)
            if rng.random() < 0.85
            else stone_spike
        )
        _place_hollow_hill_spike(
            result,
            rng,
            x,
            ceiling_y - 1,
            z,
            open_height,
            True,
            ceiling_config,
        )

        roll = rng.random()
        if roll < 0.025:
            pedestal_x = max(0, min(terrain_diameter - 1, x + rng.choice((-1, 0, 1))))
            pedestal_z = max(0, min(terrain_diameter - 1, z + rng.choice((-1, 0, 1))))
            result.set(
                pedestal_x,
                max(0, floor_y - 1),
                pedestal_z,
                "minecraft:cobblestone",
            )
            result.set(
                pedestal_x,
                floor_y,
                pedestal_z,
                "minecraft:cobblestone",
            )
            set_spawner(
                result,
                pedestal_x,
                floor_y + 1,
                pedestal_z,
                rng.choice(HOLLOW_HILL_MOBS[landmark_size]),
            )
        elif roll < 0.05:
            pedestal_x = max(0, min(terrain_diameter - 1, x + rng.choice((-1, 0, 1))))
            pedestal_z = max(0, min(terrain_diameter - 1, z + rng.choice((-1, 0, 1))))
            result.set(
                pedestal_x,
                max(0, floor_y - 1),
                pedestal_z,
                "minecraft:cobblestone",
            )
            result.set(
                pedestal_x,
                floor_y,
                pedestal_z,
                "minecraft:cobblestone",
            )
            set_loot_container(
                result,
                pedestal_x,
                floor_y + 1,
                pedestal_z,
                "hollow_hill_%s" % size_name,
            )
        else:
            _place_hollow_hill_spike(
                result,
                rng,
                x,
                floor_y + 1,
                z,
                max(0, open_height - 4),
                False,
                stone_spike,
            )
    if split_layers:
        shell = SparseStructure(result.size, result.name + "_shell")
        # Leave cavity cells unspecified (-1 in the Bedrock structure
        # palette), rather than encoding minecraft:air.  The runtime terrain
        # pass carves the exact cosine cavity before these tiles are placed.
        # Explicit air in a structure still replaces terrain even when
        # removeBlock is false, which can cut the generated stone roof away
        # and expose the whole ore field to the sky.
        shell.blocks = {
            position: block
            for position, block in shell_blocks.items()
            if block[0] != "minecraft:air"
        }
        interior = SparseStructure(result.size, result.name + "_interior")
        for position, block in result.blocks.items():
            if shell_blocks.get(position) != block:
                interior.blocks[position] = block
        interior.entities = list(result.entities)
        return shell, interior
    return result


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _courtyard_material_instances(side, top=None, bottom=None):
    return {
        "*": {
            "texture": side,
            "render_method": "opaque",
        },
        "side": {
            "texture": side,
            "render_method": "opaque",
        },
        "top": {
            "texture": top or side,
            "render_method": "opaque",
        },
        "bottom": {
            "texture": bottom or top or side,
            "render_method": "opaque",
        },
    }


def _courtyard_block_document(
    identifier,
    states,
    geometry,
    materials,
    permutations,
):
    return {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": {
                "identifier": identifier,
                "register_to_creative_menu": True,
                "states": states,
            },
            "components": {
                "minecraft:destructible_by_mining": {
                    "seconds_to_destroy": 1.5,
                },
                "minecraft:destructible_by_explosion": {
                    "explosion_resistance": 6.0,
                },
                "minecraft:geometry": geometry,
                "minecraft:material_instances": materials,
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
            "permutations": permutations,
        },
    }


def _courtyard_facing_permutations(include_vertical=False):
    rotations = (
        ("north", [0, 0, 0]),
        ("east", [0, 90, 0]),
        ("south", [0, 180, 0]),
        ("west", [0, 270, 0]),
    )
    if include_vertical:
        rotations += (
            ("up", [90, 0, 0]),
            ("down", [270, 0, 0]),
        )
    return [
        {
            "condition": (
                "query.block_state('tf_slice:facing') == '%s'" % facing
            ),
            "components": {
                "minecraft:transformation": {"rotation": rotation},
            },
        }
        for facing, rotation in rotations
    ]


def _courtyard_geometry_document():
    def face_uv(material):
        return {
            "uv": [0, 0],
            "uv_size": [16, 16],
            "material_instance": material,
        }

    cube_uv = {
        "north": face_uv("side"),
        "south": face_uv("side"),
        "east": face_uv("side"),
        "west": face_uv("side"),
        "up": face_uv("top"),
        "down": face_uv("bottom"),
    }
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": "geometry.tf_slice.courtyard_cube",
                    "texture_width": 16,
                    "texture_height": 16,
                    "visible_bounds_width": 2,
                    "visible_bounds_height": 1,
                    "visible_bounds_offset": [0, 0.5, 0],
                },
                "bones": [
                    {
                        "name": "block",
                        "pivot": [0, 0, 0],
                        "cubes": [
                            {
                                "origin": [-8, 0, -8],
                                "size": [16, 16, 16],
                                "uv": cube_uv,
                            }
                        ],
                    }
                ],
            },
            {
                "description": {
                    "identifier": "geometry.tf_slice.courtyard_stairs",
                    "texture_width": 16,
                    "texture_height": 16,
                    "visible_bounds_width": 2,
                    "visible_bounds_height": 1,
                    "visible_bounds_offset": [0, 0.5, 0],
                },
                "bones": [
                    {
                        "name": "block",
                        "pivot": [0, 0, 0],
                        "cubes": [
                            {
                                "origin": [-8, 0, -8],
                                "size": [16, 8, 16],
                                "uv": cube_uv,
                            },
                            {
                                "origin": [-8, 8, 0],
                                "size": [16, 8, 8],
                                "uv": cube_uv,
                            },
                        ],
                    }
                ],
            },
        ],
    }


def write_courtyard_directional_block_resources():
    _write_json(
        RP / "models" / "blocks" / "courtyard_blocks.geo.json",
        _courtyard_geometry_document(),
    )
    cube = "geometry.tf_slice.courtyard_cube"
    stairs = "geometry.tf_slice.courtyard_stairs"

    nagastone_states = {
        "tf_slice:variant": [
            "solid",
            "axis_x",
            "axis_y",
            "axis_z",
            "north_up",
            "north_down",
            "east_up",
            "east_down",
            "south_up",
            "south_down",
            "west_up",
            "west_down",
        ]
    }
    _write_json(
        BP / "netease_blocks" / "nagastone.json",
        _courtyard_block_document(
            "tf_slice:nagastone",
            nagastone_states,
            cube,
            _courtyard_material_instances(
                "tf_slice:nagastone_side",
                "tf_slice:nagastone_top",
                "tf_slice:nagastone_bottom",
            ),
            [],
        ),
    )

    etched_names = (
        "etched_nagastone",
        "mossy_etched_nagastone",
        "cracked_etched_nagastone",
    )
    for block_name in etched_names:
        _write_json(
            BP / "netease_blocks" / ("%s.json" % block_name),
            _courtyard_block_document(
                "tf_slice:%s" % block_name,
                {
                    "tf_slice:facing": [
                        "north",
                        "east",
                        "south",
                        "west",
                        "up",
                        "down",
                    ]
                },
                cube,
                _courtyard_material_instances(
                    "tf_slice:%s" % block_name,
                    "tf_slice:nagastone_end",
                ),
                _courtyard_facing_permutations(True),
            ),
        )

    pillar_names = (
        "nagastone_pillar",
        "mossy_nagastone_pillar",
        "cracked_nagastone_pillar",
    )
    for block_name in pillar_names:
        texture_prefix = block_name
        _write_json(
            BP / "netease_blocks" / ("%s.json" % block_name),
            _courtyard_block_document(
                "tf_slice:%s" % block_name,
                {
                    "tf_slice:axis": ["x", "y", "z"],
                    "tf_slice:reversed": [False, True],
                },
                cube,
                _courtyard_material_instances(
                    "tf_slice:%s_side" % texture_prefix,
                    "tf_slice:%s_end" % texture_prefix,
                ),
                [
                    {
                        "condition": (
                            "query.block_state('tf_slice:axis') == 'x'"
                        ),
                        "components": {
                            "minecraft:transformation": {
                                "rotation": [0, 0, 90],
                            }
                        },
                    },
                    {
                        "condition": (
                            "query.block_state('tf_slice:axis') == 'z'"
                        ),
                        "components": {
                            "minecraft:transformation": {
                                "rotation": [90, 0, 0],
                            }
                        },
                    },
                ],
            ),
        )

    _write_json(
        BP / "netease_blocks" / "nagastone_head.json",
        _courtyard_block_document(
            "tf_slice:nagastone_head",
            {
                "tf_slice:facing": [
                    "north",
                    "east",
                    "south",
                    "west",
                ]
            },
            cube,
            _courtyard_material_instances(
                "tf_slice:nagastone_head_face",
                "tf_slice:nagastone_head_top",
                "tf_slice:nagastone_head_bottom",
            ),
            _courtyard_facing_permutations(False),
        ),
    )

    stair_names = (
        "nagastone_stairs_left",
        "mossy_nagastone_stairs_left",
        "cracked_nagastone_stairs_left",
        "nagastone_stairs_right",
        "mossy_nagastone_stairs_right",
        "cracked_nagastone_stairs_right",
    )
    for block_name in stair_names:
        permutations = _courtyard_facing_permutations(False)
        permutations.append(
            {
                "condition": (
                    "query.block_state('tf_slice:half') == 'top'"
                ),
                "components": {
                    "minecraft:transformation": {
                        "rotation": [180, 0, 0],
                    }
                },
            }
        )
        _write_json(
            BP / "netease_blocks" / ("%s.json" % block_name),
            _courtyard_block_document(
                "tf_slice:%s" % block_name,
                {
                    "tf_slice:facing": [
                        "north",
                        "east",
                        "south",
                        "west",
                    ],
                    "tf_slice:half": ["bottom", "top"],
                    "tf_slice:shape": [
                        "straight",
                        "inner_left",
                        "inner_right",
                        "outer_left",
                        "outer_right",
                    ],
                },
                stairs,
                _courtyard_material_instances(
                    "tf_slice:%s" % block_name,
                    "tf_slice:nagastone_end",
                ),
                permutations,
            ),
        )

    # The dedicated courtyard builder owns the state-complete stair models.
    # Run it last so the structure build cannot replace the 10 stair shapes,
    # face-sized UVs, or geometry-matched AABBs with the legacy cube fallback.
    try:
        from tools.build_courtyard_blocks import build as build_courtyard_blocks
    except ImportError:  # pragma: no cover - direct tools/ execution
        from build_courtyard_blocks import build as build_courtyard_blocks
    build_courtyard_blocks()


def _write_runtime_catalog(value):
    target = BP / "TwilightBossSlice" / "ruin_catalog_data.py"
    payload = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    target.write_text(
        "# -*- coding: utf-8 -*-\n"
        "# Generated by tools/build_ruin_structures.py; do not edit.\n"
        "CATALOG_JSON = %r\n" % payload,
        encoding="utf-8",
    )


def _structure_ref(relative_path):
    relative_path = relative_path.replace("\\", "/")
    return "tf_slice/ruins/%s" % relative_path


def _engine_structure_name(reference):
    prefix = "tf_slice/"
    if not reference.startswith(prefix):
        raise ValueError(reference)
    return "tf_slice:%s" % reference[len(prefix) :]


def write_single(relative_path, structure, offset=(0, 0, 0)):
    reference = _structure_ref(relative_path)
    write_mcstructure(BP / "structures" / (reference + ".mcstructure"), structure)
    return {
        "structure": reference,
        "offset": list(offset),
        "size": list(structure.size),
    }


def _trim_unused_structure_height(structure):
    """Drop only unused top index planes from a structure tile."""
    highest_y = max(
        [int(position[1]) for position in structure.blocks]
        + [int(math.floor(entity[1])) for entity in structure.entities]
        + [0]
    )
    trimmed_height = max(1, highest_y + 1)
    if trimmed_height < int(structure.size[1]):
        structure.size = (
            int(structure.size[0]),
            trimmed_height,
            int(structure.size[2]),
        )
    return structure


def _ensure_surface_native_tile_has_render_safe_palette(structure):
    """Keep an empty terrain tile world-neutral but safe for native rendering."""
    if not structure.blocks:
        # NetEase can forward every dynamically selected structure tile to the
        # client renderer.  An empty palette (all block indices are -1) can
        # terminate the native tessellator.  structure_void supplies a baked
        # palette entry while preserving the tile's intended no-write behavior.
        structure.blocks[(0, 0, 0)] = (
            "minecraft:structure_void",
            {},
            {},
        )
    return structure


def write_tiled(relative_root, structure, vertical_offset=0):
    pieces = []
    for start_x in range(0, structure.size[0], 16):
        for start_z in range(0, structure.size[2], 16):
            size_x = min(16, structure.size[0] - start_x)
            size_z = min(16, structure.size[2] - start_z)
            name = "%s/x%03d_z%03d" % (relative_root, start_x, start_z)
            tile = structure.crop(start_x, start_z, size_x, size_z, name)
            if not tile.blocks:
                continue
            _trim_unused_structure_height(tile)
            pieces.append(
                write_single(
                    name,
                    tile,
                    (start_x, int(vertical_offset), start_z),
                )
            )
    return pieces


def surface_native_tile_reference(
    prefix,
    alignment,
    delta_x,
    delta_z,
):
    return ruin_logic.surface_native_tile_reference(
        prefix,
        alignment,
        delta_x,
        delta_z,
    )


def _surface_native_transition_deviation(distance, width):
    """Return the untouched height corridor at a transition distance."""
    width = max(1.0, float(width))
    progress = min(1.0, max(0.0, float(distance) / width))
    smooth = progress * progress * (3.0 - 2.0 * progress)
    return int(
        math.floor(
            smooth * SURFACE_NATIVE_TRANSITION_MAX_DEVIATION
        )
    )


def _surface_native_transition_distance(
    x,
    z,
    structure,
    margin,
    hill_data,
):
    """Measure from the actual rectangular or circular terrain core."""
    if hill_data is not None:
        terrain_radius = int(hill_data[2]) / 2.0
        center_x = margin + (structure.size[0] - 1) / 2.0
        center_z = margin + (structure.size[2] - 1) / 2.0
        radial = math.sqrt(
            (float(x) - center_x) ** 2
            + (float(z) - center_z) ** 2
        )
        return radial - terrain_radius
    if hasattr(structure, "surface_core_radius"):
        terrain_radius = float(structure.surface_core_radius)
        encoded_center = getattr(structure, "surface_core_center", None)
        if encoded_center is None:
            center_x = margin + (structure.size[0] - 1) / 2.0
            center_z = margin + (structure.size[2] - 1) / 2.0
        else:
            center_x = margin + float(encoded_center[0])
            center_z = margin + float(encoded_center[1])
        radial = math.sqrt(
            (float(x) - center_x) ** 2
            + (float(z) - center_z) ** 2
        )
        return radial - terrain_radius
    core_min_x = int(margin)
    core_min_z = int(margin)
    core_max_x = core_min_x + int(structure.size[0]) - 1
    core_max_z = core_min_z + int(structure.size[2]) - 1
    outside_x = max(core_min_x - x, 0, x - core_max_x)
    outside_z = max(core_min_z - z, 0, z - core_max_z)
    return math.sqrt(outside_x * outside_x + outside_z * outside_z)


def _surface_native_contour_noise_sample(seed, grid_x, grid_z):
    payload = "%d|%d|%d|surface_native_contour" % (
        int(seed),
        int(grid_x),
        int(grid_z),
    )
    value = int(
        hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8],
        16,
    )
    return value / float(0xFFFFFFFF) * 2.0 - 1.0


def _surface_native_contour_noise(seed, x, z, cache=None):
    """Return smooth deterministic noise used to loosen contour geometry."""
    cell_size = float(SURFACE_NATIVE_CONTOUR_NOISE_CELL_SIZE)
    grid_x = int(math.floor(float(x) / cell_size))
    grid_z = int(math.floor(float(z) / cell_size))
    fraction_x = float(x) / cell_size - grid_x
    fraction_z = float(z) / cell_size - grid_z
    smooth_x = fraction_x * fraction_x * (3.0 - 2.0 * fraction_x)
    smooth_z = fraction_z * fraction_z * (3.0 - 2.0 * fraction_z)
    if cache is None:
        cache = {}

    def sample(sample_x, sample_z):
        key = (int(sample_x), int(sample_z))
        if key not in cache:
            cache[key] = _surface_native_contour_noise_sample(
                seed,
                key[0],
                key[1],
            )
        return cache[key]

    north_west = sample(grid_x, grid_z)
    north_east = sample(grid_x + 1, grid_z)
    south_west = sample(grid_x, grid_z + 1)
    south_east = sample(grid_x + 1, grid_z + 1)
    north = north_west + (north_east - north_west) * smooth_x
    south = south_west + (south_east - south_west) * smooth_x
    return north + (south - north) * smooth_z


def _surface_native_transition_deviation_field(
    structure,
    margin,
    hill_data,
    contour_seed,
):
    """Build a natural deterministic contour field with one-block slopes.

    Low-frequency value noise bends the otherwise rectangular distance
    contours. A small integer distance transform then lowers sharp peaks until
    every cardinally adjacent transition column differs by at most one block.
    """
    margin = max(1, int(margin))
    size_x = int(structure.size[0]) + margin * 2
    size_z = int(structure.size[2]) + margin * 2
    values = {}
    noise_cache = {}
    fade_width = min(5.0, max(1.0, margin / 3.0))
    for x in range(size_x):
        for z in range(size_z):
            distance = _surface_native_transition_distance(
                x,
                z,
                structure,
                margin,
                hill_data,
            )
            if distance <= 0.0 or distance >= float(margin):
                continue
            edge_fade = min(
                1.0,
                distance / fade_width,
                (float(margin) - distance) / fade_width,
            )
            contour_noise = _surface_native_contour_noise(
                contour_seed,
                x,
                z,
                noise_cache,
            )
            warped_distance = min(
                float(margin),
                max(
                    0.0,
                    distance
                    + contour_noise
                    * SURFACE_NATIVE_CONTOUR_NOISE_AMPLITUDE
                    * edge_fade,
                ),
            )
            position = (x, z)
            values[position] = _surface_native_transition_deviation(
                warped_distance,
                margin,
            )

    # Pin the first transition column to the flat core, then propagate every
    # low point outwards. Processing buckets from low to high computes the
    # greatest field no higher than the noisy target whose cardinal gradient
    # is at most one block.
    maximum = int(SURFACE_NATIVE_TRANSITION_MAX_DEVIATION)
    buckets = [[] for _unused in range(maximum + 1)]
    for position in values:
        x, z = position
        if any(
            _surface_native_transition_distance(
                neighbor_x,
                neighbor_z,
                structure,
                margin,
                hill_data,
            )
            <= 0.0
            for neighbor_x, neighbor_z in (
                (x - 1, z),
                (x + 1, z),
                (x, z - 1),
                (x, z + 1),
            )
        ):
            values[position] = min(
                values[position],
                SURFACE_NATIVE_MAX_ADJACENT_STEP,
            )
        buckets[values[position]].append(position)

    for deviation in range(maximum + 1):
        bucket = buckets[deviation]
        while bucket:
            position = bucket.pop()
            if values.get(position) != deviation:
                continue
            x, z = position
            candidate = deviation + SURFACE_NATIVE_MAX_ADJACENT_STEP
            if candidate > maximum:
                continue
            for neighbor in (
                (x - 1, z),
                (x + 1, z),
                (x, z - 1),
                (x, z + 1),
            ):
                if neighbor not in values or values[neighbor] <= candidate:
                    continue
                values[neighbor] = candidate
                buckets[candidate].append(neighbor)
    return values


def _bake_surface_native_transition(
    result,
    structure,
    kind,
    hill_data,
    terrain_clear_height,
    margin,
    occupied_columns,
    contour_seed=0,
):
    """Bake a sparse beard that widens back into untouched native terrain.

    The lower clamp raises terrain that falls too far below the landmark.
    The upper clamp trims terrain that rises too far above it. Between those
    bounds the template contains no blocks, so the engine's existing surface
    survives. The allowed corridor widens with smoothstep and the outermost
    column is completely absent, avoiding another hard template boundary.
    """
    if margin <= 0:
        return
    ground_y = int(
        getattr(structure, "surface_ground_y", SURFACE_NATIVE_GROUND_Y)
    )
    deviation_field = _surface_native_transition_deviation_field(
        structure,
        margin,
        hill_data,
        contour_seed,
    )
    for x in range(result.size[0]):
        for z in range(result.size[2]):
            if (x, z) in occupied_columns:
                continue
            if (x, z) not in deviation_field:
                continue
            deviation = deviation_field[(x, z)]
            lower_y = max(0, ground_y - deviation)
            upper_y = min(
                terrain_clear_height - 1,
                ground_y + deviation,
            )
            for y in range(0, max(0, lower_y - 3)):
                result.set(x, y, z, "minecraft:stone")
            for y in range(max(0, lower_y - 3), lower_y):
                result.set(x, y, z, "minecraft:dirt")
            result.set(x, lower_y, z, "minecraft:grass_block")
            # Hollow hills already anchor to the sampled maximum before any
            # vegetation exists. Their irregular dome must not pay for an
            # upper-air clamp across the whole transition: native air already
            # occupies that space, while an unsampled high point is a more
            # natural join than another authored cut face.
            if hill_data is None:
                for y in range(upper_y + 1, terrain_clear_height):
                    result.set(x, y, z, "minecraft:air")


def _surface_environment_seed(
    landmark_kind,
    variant_id,
    terrain_detail_seed=0,
):
    """Derive a stable decoration stream without Python's randomized hash."""
    payload = "%s|%s|%d" % (
        str(landmark_kind),
        str(variant_id),
        int(terrain_detail_seed),
    )
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8], 16)


def _protect_landmark_surface(
    result,
    structure,
    landmark_kind,
    source_offset_y,
    margin,
):
    """Make only authored arena/path grass ineligible for later vegetation."""
    if str(landmark_kind) not in SURFACE_VEGETATION_PROTECTED_KINDS:
        return 0

    kind = str(landmark_kind)
    if kind == "dark_tower":
        # DarkTowerStructure disables biome surface decorations and its tree
        # features request up to 16 blocks of no-structure clearance. Protect
        # the complete tower footprint plus that clearance, even though the
        # tower template itself does not author grass roots.
        radius = DARK_TOWER_VEGETATION_EXCLUSION_RADIUS
        protected_columns = {
            (x, z)
            for x in range(int(margin) - radius, int(margin) + structure.size[0] + radius)
            for z in range(int(margin) - radius, int(margin) + structure.size[2] + radius)
        }
    elif kind == "knight_stronghold":
        # The native darkwood tree is a structure template: unlike the Java
        # root placer, it cannot stop when it reaches underbrick.  Mark only
        # the surface projection of upper rooms (already expanded by the
        # stronghold port's root radius), preserving trees over the deeper
        # lower maze while preventing roots from overwriting shallow roofs.
        protected_columns = {
            (int(x) + int(margin), int(z) + int(margin))
            for x, z in getattr(
                structure, "surface_protection_columns", ()
            )
        }
        default_surface_y = int(
            getattr(structure, "surface_ground_y", SURFACE_NATIVE_GROUND_Y)
        )
        encoded_surface = dict(
            getattr(structure, "surface_columns", {}) or {}
        )
        authored_positions = {
            (
                int(x) + int(margin),
                int(y) + int(source_offset_y),
                int(z) + int(margin),
            )
            for (x, y, z) in structure.blocks
        }
        written = 0
        for x, z in protected_columns:
            if not (0 <= x < result.size[0] and 0 <= z < result.size[2]):
                continue
            local_column = (int(x) - int(margin), int(z) - int(margin))
            surface_y = int(
                encoded_surface.get(local_column, default_surface_y)
            )
            # The access ruin deliberately authors both a brick ring and an
            # open stair mouth at ground level.  Root protection may replace
            # native/BURY surface grass around it, but must not overwrite an
            # authored block or authored air at that column's actual surface.
            if (x, surface_y, z) in authored_positions:
                continue
            result.set(x, surface_y, z, LANDMARK_PROTECTED_GRASS_BLOCK)
            written += 1
        return written
    else:
        roots = {
            (int(x) + int(margin), int(z) + int(margin))
            for (x, _y, z), block in structure.blocks.items()
            if block[0] in SURFACE_NATIVE_GRASS_BLOCKS
        }
        if not roots:
            return 0

        radius = SURFACE_VEGETATION_EXCLUSION_RADIUS
        protected_columns = set()
        for root_x, root_z in roots:
            for delta_x in range(-radius, radius + 1):
                for delta_z in range(-radius, radius + 1):
                    if delta_x * delta_x + delta_z * delta_z > radius * radius:
                        continue
                    protected_columns.add((root_x + delta_x, root_z + delta_z))

    exposed = {}
    for (x, y, z), block in result.blocks.items():
        if (x, z) not in protected_columns:
            continue
        if block[0] not in SURFACE_NATIVE_GRASS_BLOCKS:
            continue
        above = result.blocks.get((x, y + 1, z))
        if above is not None and above[0] not in (
            "minecraft:air",
            "minecraft:cave_air",
            "minecraft:void_air",
        ):
            continue
        previous_y = exposed.get((x, z))
        if previous_y is None or y > previous_y:
            exposed[(x, z)] = y

    for (x, z), y in exposed.items():
        result.set(x, y, z, LANDMARK_PROTECTED_GRASS_BLOCK)
    return len(exposed)


def _native_environment_integration(protected_columns, protection_radius):
    return {
        "mode": "native_biome_decorations",
        "landmarkPass": SURFACE_NATIVE_PLACEMENT_PASS,
        "treePass": "after_surface_pass",
        "groundcoverPasses": ["after_surface_pass"],
        "runtimeWrites": False,
        "bakedTrees": 0,
        "bakedGroundcover": 0,
        "protectedSurfaceBlock": LANDMARK_PROTECTED_GRASS_BLOCK,
        "protectedColumns": int(protected_columns),
        "protectionRadius": int(protection_radius),
    }


def _surface_native_terrain_clearance(landmark_kind):
    return {
        "labyrinth": 12,
        "hydra_lair": 12,
        # Upstream uses TerrainAdjustment.BURY here. Preserve native high
        # terrain instead of trimming a generic 57x57 air window around the
        # access chamber; the sparse beard still fills low terrain.
        "knight_stronghold": 0,
        "dark_tower": 0,
    }.get(str(landmark_kind), SURFACE_NATIVE_TERRAIN_CLEARANCE)


def _surface_native_ground_y(structure, landmark_kind):
    if str(landmark_kind) == "knight_stronghold":
        return route_stronghold_ground_y()
    return int(
        getattr(structure, "surface_ground_y", SURFACE_NATIVE_GROUND_Y)
    )


def route_stronghold_ground_y():
    try:
        import build_phantom_urghast_structures as route_structures
    except ImportError:  # pragma: no cover - package import in tests
        from tools import build_phantom_urghast_structures as route_structures
    return int(route_structures.STRONGHOLD_ENTRY_Y)


def _surface_native_envelope(
    structure,
    landmark_kind,
    terrain_detail_seed=0,
    environment_seed=None,
    transition_seed=None,
):
    """Bake terrain adaptation into a first-generation structure template."""
    kind = str(landmark_kind)
    hill_data = ruin_logic.HOLLOW_HILL_KIND_DATA.get(kind)
    ground_y = _surface_native_ground_y(structure, kind)
    if kind == "dark_tower":
        # Dark Forest's one surface-pass trigger is shared with the Knight
        # Stronghold and therefore runs at local Y=-52.  Keep the tower's
        # authored ground at Y=16, but shift its sparse blocks to template
        # Y=52 so the main foundation lands on the sampled surface.  The old
        # generic envelope instead wrote a 112x112 slab of stone/dirt/air at
        # Y=16, producing the giant void and cross-cut trees visible in game.
        placement_ground_y = route_stronghold_ground_y()
        source_offset_y = int(placement_ground_y) - int(ground_y)
        result = SparseStructure(
            (
                int(structure.size[0]),
                int(structure.size[1]) + source_offset_y,
                int(structure.size[2]),
            ),
            "%s_surface_native" % kind,
        )
        result.merge(structure, (0, source_offset_y, 0))
        result.environment_integration = _native_environment_integration(
            0,
            DARK_TOWER_VEGETATION_EXCLUSION_RADIUS,
        )
        result.surface_ground_y = int(placement_ground_y)
        result.worldgen_margin = 0
        # The catalog anchor maps original source/marker coordinates into the
        # shifted surface tile.  eventY + 52 - 16 == eventY + 36.
        result.source_origin_offset_y = -int(ground_y)
        result.terrain_adaptation_mode = "none"
        return result
    if kind in ("labyrinth", "hydra_lair", "knight_stronghold"):
        # Route structures encode both their underground body and their own
        # sparse surface columns, so no runtime excavation is required.
        source_offset_y = 0
    elif hill_data is None:
        source_offset_y = ground_y
    else:
        source_offset_y = (
            ground_y
            - ruin_logic.HOLLOW_HILL_GROUND_ABOVE_SEA
            - ruin_logic.hollow_hill_piece_depth(hill_data[0])
        )
    if kind == "naga_courtyard":
        source_offset_y += COURTYARD_PIECE_VERTICAL_OFFSET
    terrain_clearance = _surface_native_terrain_clearance(kind)
    terrain_clear_height = ground_y + terrain_clearance + 1
    margin = SURFACE_NATIVE_WORLDGEN_MARGIN
    height = max(
        terrain_clear_height,
        source_offset_y + int(structure.size[1]),
    )
    result = SparseStructure(
        (
            structure.size[0] + margin * 2,
            height,
            structure.size[2] + margin * 2,
        ),
        "%s_surface_native" % kind,
    )
    surface_by_column = {}

    encoded_surface = getattr(structure, "surface_columns", None)
    if hill_data is None and isinstance(encoded_surface, dict):
        for (x, z), surface_y in encoded_surface.items():
            surface_by_column[(int(x) + margin, int(z) + margin)] = int(
                surface_y
            )
    elif hill_data is None:
        for x in range(structure.size[0]):
            for z in range(structure.size[2]):
                output_x = x + margin
                output_z = z + margin
                surface_by_column[(output_x, output_z)] = ground_y
    else:
        _size, component_diameter, terrain_diameter = hill_data
        terrain_radius = int(terrain_diameter) / 2.0
        center_x = (structure.size[0] - 1) / 2.0
        center_z = (structure.size[2] - 1) / 2.0
        cavity_job = {
            "kind": kind,
            "anchor": [
                0,
                ground_y
                - ruin_logic.HOLLOW_HILL_GROUND_ABOVE_SEA,
                0,
            ],
        }
        for x in range(structure.size[0]):
            for z in range(structure.size[2]):
                distance = math.sqrt(
                    (x - center_x) ** 2 + (z - center_z) ** 2
                )
                if distance > terrain_radius:
                    continue
                profile = ruin_logic.hollow_hill_profile(
                    component_diameter,
                    distance,
                )
                if profile is None:
                    continue
                detail = ruin_logic.hollow_hill_terrain_detail(
                    int(terrain_detail_seed),
                    x,
                    z,
                    terrain_radius,
                    2,
                )
                surface_y = ruin_logic.hollow_hill_surface_target(
                    ground_y,
                    ground_y
                    - ruin_logic.HOLLOW_HILL_GROUND_ABOVE_SEA,
                    int(profile["surface"]) + detail,
                )
                output_x = x + margin
                output_z = z + margin
                for y in range(0, max(0, surface_y - 2)):
                    result.set(output_x, y, output_z, "minecraft:stone")
                for y in range(max(0, surface_y - 2), surface_y):
                    result.set(output_x, y, output_z, "minecraft:dirt")
                result.set(
                    output_x,
                    surface_y,
                    output_z,
                    "minecraft:grass_block",
                )
                surface_by_column[(output_x, output_z)] = surface_y

                # The native surface path bypasses the runtime terrain job,
                # so it must carry both the complete dome and its exact cave.
                cavity = ruin_logic.hollow_hill_generated_cavity_range(
                    cavity_job,
                    x,
                    z,
                )
                if cavity is not None:
                    # Native terrain already occupies the material below the
                    # generated cave. Keep one authored support layer under
                    # its floor, but do not serialize a stone column all the
                    # way down to the landmark template origin.
                    for y in range(
                        0,
                        max(
                            0,
                            int(cavity[0])
                            - HOLLOW_HILL_CAVE_FLOOR_SUPPORT_DEPTH,
                        ),
                    ):
                        result.blocks.pop((output_x, y, output_z), None)
                    for y in range(int(cavity[0]), int(cavity[1]) + 1):
                        if y < ground_y:
                            result.set(
                                output_x,
                                y,
                                output_z,
                                "minecraft:air",
                            )
                        else:
                            # Surface-pass runs before trees and groundcover,
                            # so above-ground cave space is already air. Leave
                            # it unspecified instead of serializing another
                            # replacement block for every hollow cell.
                            result.blocks.pop((output_x, y, output_z), None)

    # Bake the core and its sparse beard in the first-generation template.
    # No server-tick writer is needed: the widening untouched corridor lets
    # existing surface terrain meet the platform inside the worldgen pass.
    if hill_data is None:
        for (x, z), surface_y in surface_by_column.items():
            for y in range(
                ground_y - SURFACE_NATIVE_FOUNDATION_DEPTH,
                surface_y - 3,
            ):
                result.set(x, y, z, "minecraft:stone")
            for y in range(max(0, surface_y - 3), surface_y):
                result.set(x, y, z, "minecraft:dirt")
            result.set(x, surface_y, z, "minecraft:grass_block")
            for y in range(surface_y + 1, terrain_clear_height):
                result.set(x, y, z, "minecraft:air")

    if transition_seed is None:
        transition_seed = _surface_environment_seed(
            kind,
            "terrain_transition",
            terrain_detail_seed,
        )
    if kind == "knight_stronghold":
        # The stronghold owns only its compact 9x9 surface access. Applying
        # the generic height-corridor beard around that entrance authors a
        # ring of lowered grass and upper air, which becomes the giant forest
        # crack seen around an otherwise fully buried structure.
        result.surface_transition_columns = set()
    else:
        _bake_surface_native_transition(
            result,
            structure,
            kind,
            hill_data,
            terrain_clear_height,
            margin,
            surface_by_column,
            int(transition_seed),
        )

    result.merge(structure, (margin, source_offset_y, margin))
    protected_columns = _protect_landmark_surface(
        result,
        structure,
        kind,
        source_offset_y,
        margin,
    )
    result.environment_integration = _native_environment_integration(
        protected_columns,
        (
            DARK_TOWER_VEGETATION_EXCLUSION_RADIUS
            if kind == "dark_tower"
            else SURFACE_VEGETATION_EXCLUSION_RADIUS
        ),
    )
    result.surface_ground_y = ground_y
    return result


def write_surface_native_tiles(
    landmark_kind,
    variant_id,
    structure,
    terrain_detail_seed=0,
):
    transition_seed = _surface_environment_seed(
        landmark_kind,
        "terrain_transition|%s" % variant_id,
        terrain_detail_seed,
    )
    prepared = _surface_native_envelope(
        structure,
        landmark_kind,
        terrain_detail_seed,
        None,
        transition_seed,
    )
    prefix = _structure_ref(
        "surface_native/%s/%s" % (landmark_kind, variant_id)
    )
    worldgen_margin = int(
        getattr(prepared, "worldgen_margin", SURFACE_NATIVE_WORLDGEN_MARGIN)
    )
    authored_center = getattr(structure, "surface_core_center", None)
    if (
        str(landmark_kind) == "knight_stronghold"
        and isinstance(authored_center, (tuple, list))
        and len(authored_center) >= 2
    ):
        anchor_x = int(authored_center[0])
        anchor_z = int(authored_center[1])
    else:
        anchor_x = structure.size[0] // 2
        anchor_z = structure.size[2] // 2
    # A procedural port can legitimately shrink its compiled envelope between
    # releases.  Clear only this variant's generated tile directory so stale
    # edge chunks cannot remain loadable outside the new metadata bounds.
    variant_output = BP / "structures" / prefix
    if variant_output.is_dir():
        shutil.rmtree(str(variant_output))
    alignments = {}
    for center_mod_x in (8,):
        for center_mod_z in (8,):
            alignment = "%d,%d" % (center_mod_x, center_mod_z)
            origin_x = (
                center_mod_x
                - anchor_x
                - worldgen_margin
            )
            origin_z = (
                center_mod_z
                - anchor_z
                - worldgen_margin
            )
            minimum_x = int(math.floor(origin_x / 16.0))
            minimum_z = int(math.floor(origin_z / 16.0))
            maximum_x = int(
                math.floor(
                    (origin_x + prepared.size[0] - 1) / 16.0
                )
            )
            maximum_z = int(
                math.floor(
                    (origin_z + prepared.size[2] - 1) / 16.0
                )
            )
            tiles = {}
            for delta_x in range(minimum_x, maximum_x + 1):
                for delta_z in range(minimum_z, maximum_z + 1):
                    tiles[(delta_x, delta_z)] = SparseStructure(
                        (16, prepared.size[1], 16),
                        "%s_%s_%d_%d"
                        % (
                            landmark_kind,
                            variant_id,
                            delta_x,
                            delta_z,
                        ),
                    )
            for (x, y, z), block in prepared.blocks.items():
                relative_x = origin_x + x
                relative_z = origin_z + z
                delta_x = int(math.floor(relative_x / 16.0))
                delta_z = int(math.floor(relative_z / 16.0))
                tile = tiles[(delta_x, delta_z)]
                tile.set(
                    relative_x - delta_x * 16,
                    y,
                    relative_z - delta_z * 16,
                    block[0],
                    block[1],
                    block[2],
                )
            for (delta_x, delta_z), tile in tiles.items():
                _trim_unused_structure_height(tile)
                _ensure_surface_native_tile_has_render_safe_palette(tile)
                reference = surface_native_tile_reference(
                    prefix,
                    alignment,
                    delta_x,
                    delta_z,
                )
                write_mcstructure(
                    BP / "structures" / (reference + ".mcstructure"),
                    tile,
                )
            alignments[alignment] = [
                minimum_x,
                minimum_z,
                maximum_x,
                maximum_z,
            ]
    return {
        "groundY": int(prepared.surface_ground_y),
        "vegetationClearance": SURFACE_NATIVE_VEGETATION_CLEARANCE,
        "terrainClearance": _surface_native_terrain_clearance(
            landmark_kind
        ),
        "terrainAdaptationStage": SURFACE_NATIVE_TERRAIN_ADAPTATION_STAGE,
        "terrainAdaptation": {
            "mode": getattr(
                prepared,
                "terrain_adaptation_mode",
                SURFACE_NATIVE_TERRAIN_ADAPTATION_MODE,
            ),
            "width": worldgen_margin,
            "maxDeviation": SURFACE_NATIVE_TRANSITION_MAX_DEVIATION,
            "contourMode": "seeded_low_frequency",
            "noiseAmplitude": SURFACE_NATIVE_CONTOUR_NOISE_AMPLITUDE,
            "noiseCellSize": SURFACE_NATIVE_CONTOUR_NOISE_CELL_SIZE,
            "maxAdjacentStep": SURFACE_NATIVE_MAX_ADJACENT_STEP,
            "runtimeWrites": False,
        },
        "terrainAnchor": (
            {"mode": "center_height", "radius": 0}
            if str(landmark_kind)
            in ("labyrinth", "hydra_lair", "knight_stronghold")
            else {
                "mode": "center_capped_max_3x3",
                "radius": SURFACE_NATIVE_ANCHOR_SAMPLE_RADIUS,
                "maxRise": SURFACE_NATIVE_ANCHOR_MAX_RISE,
            }
        ),
        "environmentIntegration": dict(
            prepared.environment_integration
        ),
        "sourceSize": list(structure.size),
        "placementPass": SURFACE_NATIVE_PLACEMENT_PASS,
        "originOffset": [
            -anchor_x,
            int(
                getattr(
                    prepared,
                    "source_origin_offset_y",
                    -int(prepared.surface_ground_y)
                    if str(landmark_kind) in ("labyrinth", "hydra_lair")
                    else 0,
                )
            ),
            -anchor_z,
        ],
        "prefix": prefix,
        "centerAlignments": alignments,
    }


def write_dark_tower_canopy_cleanup_tiles(variant_id, cleanup_structure):
    """Write native air-only tiles for one authored Dark Tower variant.

    The surface-native tower is authored with ground at Y=16 but placed with
    ground at Y=52. These cleanup tiles share the surface trigger's world Y,
    so their explicit air cells need the same 36-block local lift.
    """
    prefix = _structure_ref(
        "dark_tower_canopy_cleanup/%s" % str(variant_id)
    )
    variant_output = BP / "structures" / prefix
    if variant_output.is_dir():
        shutil.rmtree(str(variant_output))

    alignment = "8,8"
    anchor_x = int(cleanup_structure.size[0]) // 2
    anchor_z = int(cleanup_structure.size[2]) // 2
    origin_x = 8 - anchor_x
    origin_z = 8 - anchor_z
    vertical_offset = route_stronghold_ground_y() - SURFACE_NATIVE_GROUND_Y
    tile_blocks = {}
    for (x, y, z), block in cleanup_structure.blocks.items():
        if block[0] != "minecraft:air":
            raise ValueError(
                "dark tower canopy cleanup contains non-air block %s"
                % block[0]
            )
        relative_x = origin_x + int(x)
        relative_z = origin_z + int(z)
        delta_x = int(math.floor(relative_x / 16.0))
        delta_z = int(math.floor(relative_z / 16.0))
        tile_blocks.setdefault((delta_x, delta_z), []).append(
            (
                relative_x - delta_x * 16,
                int(y) + vertical_offset,
                relative_z - delta_z * 16,
                block,
            )
        )
    if not tile_blocks:
        raise ValueError(
            "dark tower canopy cleanup is empty for %s" % variant_id
        )

    minimum_x = min(position[0] for position in tile_blocks)
    minimum_z = min(position[1] for position in tile_blocks)
    maximum_x = max(position[0] for position in tile_blocks)
    maximum_z = max(position[1] for position in tile_blocks)
    maximum_y = max(
        position[1] + vertical_offset
        for position in cleanup_structure.blocks
    )
    for delta_x in range(minimum_x, maximum_x + 1):
        for delta_z in range(minimum_z, maximum_z + 1):
            tile = SparseStructure(
                (16, maximum_y + 1, 16),
                "dark_tower_canopy_cleanup_%s_%d_%d"
                % (variant_id, delta_x, delta_z),
            )
            for local_x, local_y, local_z, block in tile_blocks.get(
                (delta_x, delta_z),
                (),
            ):
                tile.set(
                    local_x,
                    local_y,
                    local_z,
                    block[0],
                    block[1],
                    block[2],
                )
            _trim_unused_structure_height(tile)
            _ensure_surface_native_tile_has_render_safe_palette(tile)
            reference = surface_native_tile_reference(
                prefix,
                alignment,
                delta_x,
                delta_z,
            )
            write_mcstructure(
                BP / "structures" / (reference + ".mcstructure"),
                tile,
            )
    return {
        "prefix": prefix,
        "centerAlignments": {
            alignment: [minimum_x, minimum_z, maximum_x, maximum_z]
        },
        "count": len(cleanup_structure.blocks),
        "authoredGroundY": SURFACE_NATIVE_GROUND_Y,
        "placementGroundY": route_stronghold_ground_y(),
        "placementPass": POST_LANDMARK_PLACEMENT_PASS,
    }


def _load_template(relative_path, name):
    return java_template(JAVA_STRUCTURES / relative_path, name)


def _combine_well(kind):
    bottom = _load_template(
        "feature/well/%s_well_bottom.nbt" % kind,
        "%s_well_bottom" % kind,
    )
    top = _load_template(
        "feature/well/%s_well_top.nbt" % kind,
        "%s_well_top" % kind,
    )
    size = (
        max(bottom.size[0], top.size[0]),
        bottom.size[1] + top.size[1],
        max(bottom.size[2], top.size[2]),
    )
    result = SparseStructure(size, "%s_well" % kind)
    result.merge(bottom)
    result.merge(top, (0, bottom.size[1], 0))
    set_loot_container(
        result,
        result.size[0] // 2,
        max(0, bottom.size[1] - 1),
        result.size[2] // 2,
        "well",
        "minecraft:barrel",
    )
    return result


def _combine_druid(top_name, basement_name=None):
    top = _load_template("feature/druid_hut/%s.nbt" % top_name, top_name)
    if basement_name is None:
        result = SparseStructure(
            (top.size[0], top.size[1] + 12, top.size[2]),
            top_name,
        )
        result.merge(top, (0, 12, 0))
        return result
    basement = _load_template(
        "feature/druid_hut/%s.nbt" % basement_name,
        basement_name,
    )
    size = (
        max(top.size[0], basement.size[0]),
        top.size[1] + basement.size[1],
        max(top.size[2], basement.size[2]),
    )
    result = SparseStructure(size, "%s_%s" % (top_name, basement_name))
    result.merge(basement)
    result.merge(top, (0, basement.size[1], 0))
    set_spawner(
        result,
        result.size[0] // 2,
        max(0, basement.size[1] - 1),
        result.size[2] // 2,
        "tf_slice:skeleton_druid",
    )
    set_loot_container(
        result,
        max(0, result.size[0] // 2 - 1),
        max(0, basement.size[1] - 1),
        result.size[2] // 2,
        "druid_hut",
    )
    return result


def generate_small_variants():
    variants = {}
    variants["monolith"] = [
        ("v%02d" % index, monolith(index), 1) for index in range(16)
    ]
    variants["stone_circle"] = [
        (
            "v00",
            _load_template("feature/ruins/stone_circle.nbt", "stone_circle"),
            1,
        )
    ]
    variants["well"] = [
        ("simple", _combine_well("simple"), 19),
        ("fancy", _combine_well("fancy"), 1),
    ]
    variants["foundation"] = [
        ("v%02d" % index, foundation(index), 1) for index in range(16)
    ]
    druid_variants = []
    tops = ["druid_hut", "druid_sideways", "druid_doubledeck"]
    basements = [
        "basement_gallery",
        "basement_gallery_trap",
        "basement_shelves",
        "basement_shelves_trap",
        "basement_study",
        "basement_study_trap",
    ]
    for top_name in tops:
        druid_variants.append(
            (top_name, _combine_druid(top_name), 6)
        )
        for basement_name in basements:
            variant_name = "%s_%s" % (top_name, basement_name)
            druid_variants.append(
                (
                    variant_name,
                    _combine_druid(top_name, basement_name),
                    1,
                )
            )
    variants["druid_hut"] = druid_variants
    variants["outside_stalagmite"] = [
        ("length_%02d" % length, stalagmite(length), 1)
        for length in range(2, 12)
    ]
    variants["hollow_stump"] = [
        ("v%02d" % index, hollow_stump(index), 1) for index in range(8)
    ]
    variants["fallen_hollow_log"] = [
        ("v%02d" % index, fallen_log(index), 1) for index in range(4)
    ]
    variants["grove_ruins"] = [
        (
            "arch",
            _load_template("feature/ruins/grove_arch.nbt", "grove_arch"),
            1,
        ),
        (
            "pillar",
            _load_template("feature/ruins/grove_pillar.nbt", "grove_pillar"),
            1,
        ),
    ]
    return variants


def _native_feature(identifier, structure_reference, rotation=0):
    return {
        "format_version": "1.14.0",
        "netease:structure_feature": {
            "description": {"identifier": identifier},
            "places_structure": _engine_structure_name(structure_reference),
            "rotation": int(rotation),
        },
    }


def _selector_feature(identifier, features):
    return {
        "format_version": "1.20.30",
        "minecraft:weighted_random_feature": {
            "description": {"identifier": identifier},
            "features": features,
        },
    }


def _surface_slope_expression(size_x, size_z):
    offsets = (
        (0, 0),
        (max(0, int(size_x) - 1), 0),
        (0, max(0, int(size_z) - 1)),
        (max(0, int(size_x) - 1), max(0, int(size_z) - 1)),
    )
    samples = []
    for offset_x, offset_z in offsets:
        samples.append(
            "query.get_height_at(variable.originx + %d, variable.originz + %d)"
            % (offset_x, offset_z)
        )
    maximum = samples[0]
    minimum = samples[0]
    for sample in samples[1:]:
        maximum = "math.max(%s, %s)" % (maximum, sample)
        minimum = "math.min(%s, %s)" % (minimum, sample)
    return "(%s - %s <= 2) ? 1 : 0" % (maximum, minimum)


def _offset_molang_coordinate(expression, offset):
    offset = int(offset)
    if offset < 0:
        return "(%s - %d)" % (expression, abs(offset))
    if offset > 0:
        return "(%s + %d)" % (expression, offset)
    return "(%s)" % expression


def _surface_region_anchor_expression(
    region_x,
    region_z,
    radius,
    ground_y=SURFACE_NATIVE_GROUND_Y,
    max_rise=SURFACE_NATIVE_ANCHOR_MAX_RISE,
):
    """Anchor landmarks near the center while accounting for nearby terrain.

    A single center sample can land in a shallow noise valley even when the
    surrounding forest is higher, producing a sunken clearing with a dirt
    wall. The old unbounded maximum fixed that case by raising the whole
    landmark to the highest point in a 128x128 area, which systematically
    floated landmarks above their centers. Keep one shared Y for every tile,
    but cap the sampled maximum to a small rise above the center surface.
    """
    samples = []
    for offset_x in (-int(radius), 0, int(radius)):
        for offset_z in (-int(radius), 0, int(radius)):
            samples.append(
                "query.get_height_at(%s, %s)"
                % (
                    _offset_molang_coordinate(region_x, offset_x),
                    _offset_molang_coordinate(region_z, offset_z),
                )
            )
    maximum = samples[0]
    for sample in samples[1:]:
        maximum = "math.max(%s, %s)" % (maximum, sample)
    center = "query.get_height_at(%s, %s)" % (region_x, region_z)
    capped_maximum = "math.min(%s, %s + %d)" % (
        maximum,
        center,
        int(max_rise),
    )
    # get_height_at is the first placeable layer above the terrain.  The
    # template coordinate named ground_y contains the authored surface block,
    # so it must land one block below that layer rather than replacing air.
    return "math.floor(%s) - %d" % (
        capped_maximum,
        int(ground_y) + 1,
    )


def _scatter_feature(
    identifier,
    selector_identifier,
    denominator,
    size_x,
    size_z,
):
    return {
        "format_version": "1.20.30",
        "minecraft:scatter_feature": {
            "description": {"identifier": identifier},
            "places_feature": selector_identifier,
            "iterations": _surface_slope_expression(size_x, size_z),
            "scatter_chance": {"numerator": 1, "denominator": denominator},
            "x": 0,
            "y": 0,
            "z": 0,
        },
    }


def _feature_rule(
    identifier,
    feature_identifier,
    extra_biome_tag=None,
    vertical_offset=0,
    placement_pass=SURFACE_NATIVE_PLACEMENT_PASS,
):
    filters = [
        {"test": "has_biome_tag", "operator": "==", "value": "dm33027004"},
    ]
    if extra_biome_tag is None:
        filters.append(
            {
                "test": "has_biome_tag",
                "operator": "==",
                "value": "tf_slice_twilight_forest",
            }
        )
        filters.append(
            {
                "test": "has_biome_tag",
                "operator": "!=",
                "value": "tf_slice_spooky_forest",
            }
        )
        filters.append(
            {
                "test": "has_biome_tag",
                "operator": "!=",
                "value": "tf_slice_dense_mushroom_forest",
            }
        )
    else:
        filters.append(
            {
                "test": "has_biome_tag",
                "operator": "==",
                "value": extra_biome_tag,
            }
        )
    y_expression = "query.get_height_at(variable.worldx, variable.worldz)"
    if vertical_offset < 0:
        y_expression += " - %d" % abs(int(vertical_offset))
    elif vertical_offset > 0:
        y_expression += " + %d" % int(vertical_offset)
    return {
        "format_version": "1.14.0",
        "minecraft:feature_rules": {
            "description": {
                "identifier": identifier,
                "places_feature": feature_identifier,
            },
            "conditions": {
                "placement_pass": placement_pass,
                "minecraft:biome_filter": [{"all_of": filters}],
            },
            "distribution": {
                "iterations": 1,
                "coordinate_eval_order": "xzy",
                "x": {"distribution": "uniform", "extent": [0, 15]},
                "y": y_expression,
                "z": {"distribution": "uniform", "extent": [0, 15]},
            },
        },
    }


def write_native_resources(
    ruin_id,
    variant_specs,
    denominator,
    biome_tag=None,
    vertical_offset=0,
    include_rotations=True,
    include_mirrors=False,
):
    feature_weights = []
    catalog_variants = []
    maximum_size_x = max(spec[1].size[0] for spec in variant_specs)
    maximum_size_z = max(spec[1].size[2] for spec in variant_specs)
    for variant_name, structure, weight in variant_specs:
        relative = "%s/%s" % (ruin_id, variant_name)
        if structure.size[0] > 16 or structure.size[2] > 16:
            pieces = write_tiled(relative, structure)
            # Native structure features are already clipped and scheduled by
            # the engine's current world-generation call. Keep one complete
            # template for that path while retaining 16x16 pieces for manual
            # placement and catalog inspection.
            native_piece = write_single(
                "%s/%s_native" % (ruin_id, variant_name),
                structure,
            )
        else:
            pieces = [write_single(relative, structure)]
            native_piece = pieces[0]
        rotations = (0, 90, 180, 270) if include_rotations else (0,)
        for rotation in rotations:
            rotated_name = "%s_r%03d" % (variant_name, rotation)
            feature_id = "tf_slice:%s_%s_structure_feature" % (
                ruin_id,
                rotated_name,
            )
            feature_file = "%s_%s_structure_feature.json" % (
                ruin_id,
                rotated_name,
            )
            _write_json(
                BP / "netease_features" / feature_file,
                _native_feature(
                    feature_id,
                    native_piece["structure"],
                    rotation,
                ),
            )
            feature_weights.append([feature_id, weight])
            native_feature = {
                "identifier": feature_id,
                "structure": native_piece["structure"],
                "rotation": rotation,
                "surfaceOffset": -int(vertical_offset),
            }
            catalog_variants.append(
                {
                    "id": rotated_name,
                    "weight": weight,
                    "rotation": rotation,
                    "pieces": pieces,
                    "bounds": _combined_bounds(pieces),
                    "nativeFeature": native_feature,
                }
            )
    selector_id = "tf_slice:%s_structure_selector_feature" % ruin_id
    scatter_id = "tf_slice:%s_scatter_feature" % ruin_id
    _write_json(
        BP
        / "netease_features"
        / ("%s_structure_selector_feature.json" % ruin_id),
        _selector_feature(selector_id, feature_weights),
    )
    _write_json(
        BP / "netease_features" / ("%s_scatter_feature.json" % ruin_id),
        _scatter_feature(
            scatter_id,
            selector_id,
            denominator,
            maximum_size_x,
            maximum_size_z,
        ),
    )
    _write_json(
        BP / "netease_feature_rules" / ("%s_feature_rule.json" % ruin_id),
        _feature_rule(
            "tf_slice:%s_feature_rule" % ruin_id,
            scatter_id,
            biome_tag,
            vertical_offset,
            (
                POST_LANDMARK_PLACEMENT_PASS
                if ruin_id in POST_LANDMARK_ENVIRONMENT_RUINS
                else SURFACE_NATIVE_PLACEMENT_PASS
            ),
        ),
    )
    return catalog_variants


def write_hollow_tree_chunk_resources(variant_specs):
    """Emit four native 16x16 tiles selected from one shared tree cell."""
    catalog_variants = []
    for variant_name, structure, weight in variant_specs:
        pieces = write_tiled("hollow_tree/%s" % variant_name, structure)
        expected_offsets = set(((0, 0), (0, 16), (16, 0), (16, 16)))
        actual_offsets = set(
            (int(piece["offset"][0]), int(piece["offset"][2]))
            for piece in pieces
        )
        if actual_offsets != expected_offsets:
            raise ValueError(
                "hollow tree %s does not fill its four native tiles: %r"
                % (variant_name, sorted(actual_offsets))
            )
        catalog_variants.append(
            {
                "id": variant_name,
                "weight": weight,
                "rotation": 0,
                "pieces": pieces,
                "bounds": _combined_bounds(pieces),
            }
        )

    proxy = _render_safe_structure_proxy("hollow_tree_chunk_trigger")
    write_mcstructure(
        BP
        / "structures"
        / "tf_slice"
        / "hollow_tree_chunk_trigger.mcstructure",
        proxy,
    )
    feature_id = "tf_slice:hollow_tree_chunk_trigger_structure_feature"
    _write_json(
        BP
        / "netease_features"
        / "hollow_tree_chunk_trigger_structure_feature.json",
        _native_feature(feature_id, HOLLOW_TREE_TRIGGER_REFERENCE),
    )

    cell_origin_x = (
        "math.floor(variable.originx / %d) * %d"
        % (HOLLOW_TREE_CELL_BLOCKS, HOLLOW_TREE_CELL_BLOCKS)
    )
    cell_origin_z = (
        "math.floor(variable.originz / %d) * %d"
        % (HOLLOW_TREE_CELL_BLOCKS, HOLLOW_TREE_CELL_BLOCKS)
    )
    center_x = "(%s + 16)" % cell_origin_x
    center_z = "(%s + 16)" % cell_origin_z
    height_samples = []
    for offset_x, offset_z in ((2, 2), (30, 2), (2, 30), (30, 30)):
        height_samples.append(
            "query.get_height_at((%s + %d), (%s + %d))"
            % (cell_origin_x, offset_x, cell_origin_z, offset_z)
        )
    maximum = height_samples[0]
    minimum = height_samples[0]
    for sample in height_samples[1:]:
        maximum = "math.max(%s, %s)" % (maximum, sample)
        minimum = "math.min(%s, %s)" % (minimum, sample)
    slope = "(%s - %s <= 2)" % (maximum, minimum)
    biome = _biome_sample_expression(
        center_x,
        center_z,
        HOLLOW_TREE_BIOME_TYPES,
    )
    iterations = "((%s && %s) ? 1 : 0)" % (biome, slope)
    rule = {
        "format_version": "1.14.0",
        "minecraft:feature_rules": {
            "description": {
                "identifier": "tf_slice:hollow_tree_feature_rule",
                "places_feature": feature_id,
            },
            "conditions": {
                "placement_pass": POST_LANDMARK_PLACEMENT_PASS,
                "minecraft:biome_filter": [
                    {
                        "test": "has_biome_tag",
                        "operator": "==",
                        "value": "dm33027004",
                    }
                ],
            },
            "distribution": {
                "iterations": iterations,
                "coordinate_eval_order": "xzy",
                "x": 0,
                "y": _molang_offset(
                    "query.get_height_at(%s, %s)" % (
                        center_x,
                        center_z,
                    ),
                    -(
                        HOLLOW_ROOT_SUBSURFACE_DEPTH
                        + HOLLOW_TREE_ROOT_BURY_DEPTH
                    ),
                ),
                "z": 0,
            },
        },
    }
    _write_json(
        BP / "netease_feature_rules" / "hollow_tree_feature_rule.json",
        rule,
    )
    return catalog_variants


def _molang_offset(expression, offset):
    offset = int(offset)
    if offset == 0:
        return str(expression)
    if offset > 0:
        return "(%s + %d)" % (expression, offset)
    return "(%s - %d)" % (expression, abs(offset))


def _biome_sample_expression(x_expression, z_expression, biome_types):
    return "query.is_biome(%s, %s, %s)" % (
        x_expression,
        z_expression,
        ", ".join(str(value) for value in biome_types),
    )


def _surface_mode_biome_expression(mode, region_x, region_z, biome_types):
    core_types = ROUTE_CORE_MODE_BIOME_TYPES.get(str(mode))
    if core_types is not None:
        return _biome_sample_expression(region_x, region_z, core_types)

    linked_core_types = ROUTE_COMPANION_MODE_CORE_TYPES.get(str(mode))
    if linked_core_types is not None:
        companion_center = _biome_sample_expression(
            region_x,
            region_z,
            biome_types,
        )
        linked_core_centers = []
        for offset_x, offset_z in ROUTE_COMPANION_TO_CORE_OFFSETS:
            linked_core_centers.append(
                _biome_sample_expression(
                    _molang_offset(region_x, offset_x),
                    _molang_offset(region_z, offset_z),
                    linked_core_types,
                )
            )
        return "((%s) && (%s))" % (
            companion_center,
            " || ".join(linked_core_centers),
        )

    return _biome_sample_expression(region_x, region_z, biome_types)


def write_landmark_trigger_resources():
    """Emit one bounded, non-destructive trigger per surface biome mode."""
    region_x = (
        "math.floor((variable.originx + 128) / 256) * 256 + 8"
    )
    region_z = (
        "math.floor((variable.originz + 128) / 256) * 256 + 8"
    )
    center_height = (
        "query.get_height_at(%s, %s) - %d"
        % (region_x, region_z, SURFACE_NATIVE_GROUND_Y + 1)
    )
    labyrinth_center_height = (
        "query.get_height_at(%s, %s) - %d"
        % (region_x, region_z, LABYRINTH_SURFACE_GROUND_Y)
    )
    stronghold_center_height = (
        "query.get_height_at(%s, %s) - %d"
        % (region_x, region_z, route_stronghold_ground_y() + 1)
    )
    sampled_max_height = _surface_region_anchor_expression(
        region_x,
        region_z,
        SURFACE_NATIVE_ANCHOR_SAMPLE_RADIUS,
    )
    dark_tower_sampled_max_height = _surface_region_anchor_expression(
        region_x,
        region_z,
        SURFACE_NATIVE_ANCHOR_SAMPLE_RADIUS,
        route_stronghold_ground_y(),
    )
    biome_filter = [
        {
            "all_of": [
                {
                    "test": "has_biome_tag",
                    "operator": "==",
                    "value": "dm33027004",
                }
            ]
        }
    ]
    noop = _render_safe_structure_proxy("ruin_landmark_noop")
    write_mcstructure(
        BP / "structures" / "tf_slice" / "ruin_landmark_noop.mcstructure",
        noop,
    )
    cleanup_proxy = _render_safe_structure_proxy(
        "dark_tower_canopy_cleanup_trigger"
    )
    write_mcstructure(
        BP
        / "structures"
        / (DARK_TOWER_CANOPY_CLEANUP_TRIGGER_REFERENCE + ".mcstructure"),
        cleanup_proxy,
    )
    _write_json(
        BP
        / "netease_features"
        / "dark_tower_canopy_cleanup_trigger_structure_feature.json",
        _native_feature(
            "tf_slice:dark_tower_canopy_cleanup_trigger_structure_feature",
            DARK_TOWER_CANOPY_CLEANUP_TRIGGER_REFERENCE,
        ),
    )
    for mode, biome_types in SURFACE_LANDMARK_BIOME_TYPES.items():
        trigger_radius = int(SURFACE_LANDMARK_TRIGGER_RADIUS_CHUNKS[mode]) * 16
        region_origin_x = "(%s - 8)" % region_x
        region_origin_z = "(%s - 8)" % region_z
        biome_expression = _surface_mode_biome_expression(
            mode,
            region_x,
            region_z,
            biome_types,
        )
        distribution = {
            "iterations": (
                "((%s && "
                "math.abs(variable.originx - %s) <= %d && "
                "math.abs(variable.originz - %s) <= %d) ? 1 : 0)"
                % (
                    biome_expression,
                    region_origin_x,
                    trigger_radius,
                    region_origin_z,
                    trigger_radius,
                )
            ),
            "coordinate_eval_order": "xzy",
            "scatter_chance": 100.0,
            "x": 0,
            "y": sampled_max_height,
            "z": 0,
        }
        if mode == "swamp":
            # Anchor the mound to its own center. Even a capped regional
            # maximum raises the whole 35-block mound above rolling swamp
            # terrain and produces the broad elevated skirt seen in game.
            distribution["y"] = labyrinth_center_height
        elif mode == "fire_swamp":
            # Fire Swamp uses a local center anchor so the lair follows
            # the volcano shelf instead of a distant high sample.
            distribution["y"] = center_height
        elif mode == "dark_forest":
            # The surface entrance is authored at the route port's ground Y
            # while the rest
            # of the stronghold remains buried under untouched forest soil.
            distribution["y"] = stronghold_center_height
        elif mode == "dark_forest_center":
            # The tower's authored base is shifted from local Y=16 to Y=52
            # inside the shared Dark Forest template envelope.  Subtract that
            # actual template ground here; subtracting 16 raises every tower
            # exactly 36 blocks above the sampled forest surface.
            distribution["y"] = dark_tower_sampled_max_height
        resource_name = "ruin_landmark_surface_%s" % mode
        reference = "tf_slice/%s" % resource_name
        proxy = _render_safe_structure_proxy(resource_name)
        write_mcstructure(
            BP / "structures" / (reference + ".mcstructure"),
            proxy,
        )
        feature_id = "tf_slice:%s_structure_feature" % resource_name
        _write_json(
            BP
            / "netease_features"
            / ("%s_structure_feature.json" % resource_name),
            _native_feature(feature_id, reference),
        )
        rule_id = "tf_slice:%s_feature_rule" % resource_name
        rule = {
            "format_version": "1.14.0",
            "minecraft:feature_rules": {
                "description": {
                    "identifier": rule_id,
                    "places_feature": feature_id,
                },
                "conditions": {
                    "placement_pass": SURFACE_NATIVE_PLACEMENT_PASS,
                    "minecraft:biome_filter": biome_filter,
                },
                "distribution": distribution,
            },
        }
        _write_json(
            BP
            / "netease_feature_rules"
            / ("%s_feature_rule.json" % resource_name),
            rule,
        )

def _catalog_entry(
    ruin_id,
    strategy,
    biome_tags,
    pieces,
    dependencies=None,
    post_processors=None,
    **extra
):
    entry = {
        "id": ruin_id,
        "sourceVersion": SOURCE_VERSION,
        "strategy": strategy,
        "biomeTags": biome_tags,
        "bounds": _combined_bounds(pieces),
        "pieces": pieces,
        "dependencies": list(dependencies or []),
        "postProcessors": list(post_processors or []),
    }
    entry.update(extra)
    return entry


def _combined_bounds(pieces):
    if not pieces:
        return [0, 0, 0, 0, 0, 0]
    min_x = min(piece["offset"][0] for piece in pieces)
    min_y = min(piece["offset"][1] for piece in pieces)
    min_z = min(piece["offset"][2] for piece in pieces)
    max_x = max(piece["offset"][0] + piece["size"][0] - 1 for piece in pieces)
    max_y = max(piece["offset"][1] + piece["size"][1] - 1 for piece in pieces)
    max_z = max(piece["offset"][2] + piece["size"][2] - 1 for piece in pieces)
    return [min_x, min_y, min_z, max_x, max_y, max_z]


def _clean_generated_resources():
    if OUTPUT_ROOT.exists():
        shutil.rmtree(str(OUTPUT_ROOT))
    if HANDOFF_ROOT.exists():
        shutil.rmtree(str(HANDOFF_ROOT))
    native_prefixes = list(SMALL_RARITIES) + [
        "hollow_tree",
        "graveyard",
    ]
    for directory in (BP / "netease_features", BP / "netease_feature_rules"):
        for path in directory.glob("*_structure_feature.json"):
            if any(
                path.name.startswith(key + "_")
                for key in native_prefixes
            ):
                path.unlink()
        for suffix in ("*_structure_selector_feature.json", "*_scatter_feature.json"):
            for path in directory.glob(suffix):
                if any(
                    path.name.startswith(key + "_")
                    for key in native_prefixes
                ):
                    path.unlink()
        for ruin_id in native_prefixes:
            path = directory / ("%s_feature_rule.json" % ruin_id)
            if path.exists():
                path.unlink()
    trigger_files = [
        BP
        / "netease_features"
        / "ruin_landmark_trigger_structure_feature.json",
        BP
        / "netease_feature_rules"
        / "ruin_landmark_trigger_feature_rule.json",
        BP / "structures" / "tf_slice" / "ruin_landmark_trigger.mcstructure",
        BP
        / "netease_features"
        / "ruin_landmark_surface_watchdog_structure_feature.json",
        BP
        / "netease_feature_rules"
        / "ruin_landmark_surface_watchdog_feature_rule.json",
        BP
        / "structures"
        / "tf_slice"
        / "ruin_landmark_surface_watchdog.mcstructure",
        BP / "structures" / "tf_slice" / "ruin_landmark_noop.mcstructure",
    ]
    for mode in SURFACE_LANDMARK_BIOME_TYPES:
        for family_suffix in ("", "_naga"):
            resource_name = "ruin_landmark_surface_%s%s" % (
                mode,
                family_suffix,
            )
            trigger_files.extend(
                (
                    BP
                    / "netease_features"
                    / ("%s_structure_feature.json" % resource_name),
                    BP
                    / "netease_feature_rules"
                    / ("%s_feature_rule.json" % resource_name),
                    BP
                    / "structures"
                    / "tf_slice"
                    / ("%s.mcstructure" % resource_name),
                )
            )
    for path in trigger_files:
        if path.exists():
            path.unlink()


@contextlib.contextmanager
def _exclusive_build_lock():
    """Prevent concurrent builders from leaving a partially mixed pack."""
    handle = open(str(BUILD_LOCK_PATH), "a+b")
    locked = False
    backend = None
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                backend = msvcrt
            else:  # pragma: no cover - release builds currently run on Windows
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                backend = fcntl
            locked = True
        except (IOError, OSError):
            raise SystemExit(
                "another ruin structure build is already running: %s"
                % BUILD_LOCK_PATH
            )
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                backend.locking(handle.fileno(), backend.LK_UNLCK, 1)
            else:  # pragma: no cover - release builds currently run on Windows
                backend.flock(handle.fileno(), backend.LOCK_UN)
        handle.close()


def _consume_shared_artifact_write_lease(token):
    if not WRITE_LEASE_PATH.is_file():
        raise RuntimeError(
            "shared ruin structure writes are frozen: no active write lease"
        )
    lease = json.loads(WRITE_LEASE_PATH.read_text(encoding="utf-8-sig"))
    if int(lease.get("schemaVersion", 0)) != 1:
        raise RuntimeError("shared ruin structure write lease schema is invalid")
    if lease.get("status") != "active":
        raise RuntimeError(
            "shared ruin structure writes are frozen; explicit user approval "
            "is required to create a new one-shot lease"
        )
    expected = str(lease.get("token", ""))
    if not token or token != expected:
        raise RuntimeError("shared ruin structure write lease token mismatch")

    lease["status"] = "frozen"
    lease.pop("token", None)
    lease["consumedAt"] = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()
    WRITE_LEASE_PATH.write_text(
        json.dumps(lease, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build():
    if not JAVA_STRUCTURES.is_dir():
        raise SystemExit("missing extracted 4.3.2508 structures: %s" % JAVA_STRUCTURES)
    _clean_generated_resources()
    write_courtyard_directional_block_resources()
    write_landmark_trigger_resources()

    catalog_entries = []
    small_variants = generate_small_variants()
    small_tags = ["dm33027004", "tf_slice_small_ruins"]
    large_tags = ["dm33027004", "tf_slice_large_landmarks"]
    for ruin_id, denominator in SMALL_RARITIES.items():
        variants = write_native_resources(
            ruin_id,
            small_variants[ruin_id],
            denominator,
            biome_tag="tf_slice_small_ruins",
            vertical_offset=SMALL_VERTICAL_OFFSETS.get(ruin_id, 0),
            include_mirrors=ruin_id in ("well", "druid_hut"),
        )
        canonical_pieces = variants[0]["pieces"]
        extra = {
            "rarity": {"numerator": 1, "denominator": denominator},
            "variants": variants,
        }
        if ruin_id == "outside_stalagmite":
            extra["palette"] = ["minecraft:stone"]
        catalog_entries.append(
            _catalog_entry(
                ruin_id,
                "native_feature",
                small_tags,
                canonical_pieces,
                post_processors=(
                    []
                    if ruin_id == "fallen_hollow_log"
                    else ["loot_and_spawner_markers"]
                    if ruin_id in ("well", "druid_hut", "foundation")
                    else []
                ),
                **extra
            )
        )

    tree_variants = [
        ("v%02d" % index, hollow_tree(index, index == 0), 1)
        for index in range(8)
    ]
    tree_catalog_variants = write_hollow_tree_chunk_resources(tree_variants)
    leaf_pieces = tree_catalog_variants[0]["pieces"]
    catalog_entries.append(
        _catalog_entry(
            "leaf_dungeon",
            "hollow_tree_attachment",
            large_tags,
            leaf_pieces,
            dependencies=["swarm_spider", "tree_cache_loot"],
            post_processors=["loot_and_spawner_markers"],
            variants=tree_catalog_variants,
            chunkNative={
                "triggerStructure": HOLLOW_TREE_TRIGGER_STRUCTURE,
                "cellChunks": [2, 2],
                "cellChance": {
                    "numerator": HOLLOW_TREE_CELL_CHANCE_NUMERATOR,
                    "denominator": HOLLOW_TREE_CELL_CHANCE_DENOMINATOR,
                },
                "sharedGroundSample": [16, 16],
                "placementPass": POST_LANDMARK_PLACEMENT_PASS,
            },
            parentRarity={"numerator": 1, "denominator": 35},
            attachmentChance={"numerator": 1, "denominator": 8},
        )
    )

    grave = graveyard_structure()
    grave_variants = write_native_resources(
        "graveyard",
        [("v00", grave, 1)],
        70,
        "tf_slice_spooky_forest",
        vertical_offset=-2,
    )
    catalog_entries.append(
        _catalog_entry(
            "graveyard",
            "native_feature",
            ["dm33027004", "tf_slice_spooky_forest"],
            grave_variants[0]["pieces"],
            dependencies=["wraith", "rising_zombie", "graveyard_loot"],
            post_processors=["loot_and_spawner_markers", "grave_traps"],
            variants=grave_variants,
            rarity={"numerator": 1, "denominator": 70},
        )
    )

    hedge_variants = []
    for seed in range(HEDGE_MAZE_VARIANT_COUNT):
        variant_id = "v%02d" % seed
        structure = hedge_maze(seed)
        pieces = write_tiled("hedge_maze/%s" % variant_id, structure)
        hedge_variants.append(
            {
                "id": variant_id,
                "weight": 1,
                "layoutSeed": seed,
                "pieces": pieces,
                "bounds": _combined_bounds(pieces),
                "surfaceNative": write_surface_native_tiles(
                    "hedge_maze",
                    variant_id,
                    structure,
                ),
            }
        )
    catalog_entries.append(
        _catalog_entry(
            "hedge_maze",
            "landmark_service",
            large_tags,
            hedge_variants[0]["pieces"],
            dependencies=["hedge_spider", "swarm_spider", "hostile_wolf"],
            post_processors=["loot_and_spawner_markers"],
            variants=hedge_variants,
            landmarkKind="hedge_maze",
        )
    )

    labyrinth_variants = []
    for seed in range(8):
        variant_id = "v%02d" % seed
        structure = labyrinth_structure(seed)
        pieces = write_tiled("labyrinth/%s" % variant_id, structure)
        metadata = structure.landmark_metadata
        spawner = {
            "kind": "minoshroom",
            "entity": "tf_slice:minoshroom",
            "offset": list(metadata["boss"]["offset"]),
            "markerBlock": "tf_slice:minoshroom_boss_spawner",
            # Source MinoshroomSpawnerBlockEntity places the spawner at room
            # y=2, spawns one block below it, activates within SHORT_RANGE=9,
            # and only accepts players below markerY+4.
            "spawnYOffset": -1.5,
            "activationRadius": 9,
            "maxPlayerYOffset": 3.5,
        }
        digest_payload = json.dumps(
            sorted(
                (x, y, z, block[0], sorted(block[1].items()))
                for (x, y, z), block in structure.blocks.items()
            ),
            separators=(",", ":"),
        ).encode("utf-8")
        labyrinth_variants.append(
            {
                "id": variant_id,
                "weight": 1,
                "layoutSeed": seed,
                "layoutSha256": hashlib.sha256(digest_payload).hexdigest(),
                "pieces": pieces,
                "bounds": _combined_bounds(pieces),
                "surfaceNative": write_surface_native_tiles(
                    "labyrinth", variant_id, structure, seed
                ),
                "bossSpawner": spawner,
                "markers": metadata,
            }
        )
    labyrinth_spawner = copy.deepcopy(labyrinth_variants[0]["bossSpawner"])
    catalog_entries.append(
        _catalog_entry(
            "labyrinth",
            "landmark_service",
            ["dm33027004", "tf_slice_biome_swamp"],
            labyrinth_variants[0]["pieces"],
            dependencies=[
                "minotaur",
                "minoshroom",
                "maze_slime",
                "fire_beetle",
                "slime_beetle",
                "pinch_beetle",
                "labyrinth_loot",
                "maze_map",
            ],
            post_processors=[
                "java_rng_layout",
                "weathered_mazestone",
                "compiled_marker_catalog",
                "controlled_labyrinth_spawns",
                "proximity_boss_activation",
            ],
            variants=labyrinth_variants,
            landmarkKind="labyrinth",
            bossSpawner=labyrinth_spawner,
            clearanceChunks=3,
            placementPass=SURFACE_NATIVE_PLACEMENT_PASS,
            controlledSpawns={
                "cap": 18,
                "intervalTicks": 100,
                "activationRadius": 48,
                "despawnRadius": 72,
                "weights": [
                    {"entity": "tf_slice:minotaur", "weight": 20, "group": [2, 3]},
                    {"entity": "minecraft:cave_spider", "weight": 10, "group": [1, 2]},
                    {"entity": "minecraft:creeper", "weight": 10, "group": [1, 2]},
                    {"entity": "tf_slice:maze_slime", "weight": 10, "group": [2, 4]},
                    {"entity": "minecraft:enderman", "weight": 1, "group": [1, 2]},
                    {"entity": "tf_slice:fire_beetle", "weight": 10, "group": [1, 2]},
                    {"entity": "tf_slice:slime_beetle", "weight": 10, "group": [1, 2]},
                    {"entity": "tf_slice:pinch_beetle", "weight": 10, "group": [1, 1]},
                ],
            },
            lootTables=[
                "loot_tables/chests/tf_slice/labyrinth_dead_end.json",
                "loot_tables/chests/tf_slice/labyrinth_room.json",
                "loot_tables/chests/tf_slice/labyrinth_vault.json",
                "loot_tables/chests/tf_slice/labyrinth_jackpot.json",
            ],
        )
    )

    hydra_lair_variants = []
    for seed in range(8):
        variant_id = "v%02d" % seed
        structure = hydra_lair_structure(seed)
        pieces = write_tiled("hydra_lair/%s" % variant_id, structure)
        metadata = structure.landmark_metadata
        spawner = {
            "kind": "hydra",
            "entity": "tf_slice:hydra",
            "offset": list(metadata["boss"]["offset"]),
            "markerBlock": "tf_slice:hydra_boss_spawner",
            "spawnYOffset": 1.0,
            "activationRadius": 50,
        }
        digest_payload = json.dumps(
            sorted(
                (x, y, z, block[0], sorted(block[1].items()))
                for (x, y, z), block in structure.blocks.items()
            ),
            separators=(",", ":"),
        ).encode("utf-8")
        hydra_lair_variants.append(
            {
                "id": variant_id,
                "weight": 1,
                "layoutSeed": seed,
                "layoutSha256": hashlib.sha256(digest_payload).hexdigest(),
                "pieces": pieces,
                "bounds": _combined_bounds(pieces),
                "surfaceNative": write_surface_native_tiles(
                    "hydra_lair", variant_id, structure, seed
                ),
                "bossSpawner": spawner,
                "markers": metadata,
            }
        )
    hydra_spawner = copy.deepcopy(hydra_lair_variants[0]["bossSpawner"])
    catalog_entries.append(
        _catalog_entry(
            "hydra_lair",
            "landmark_service",
            ["dm33027004", "tf_slice_biome_fire_swamp"],
            hydra_lair_variants[0]["pieces"],
            dependencies=["hydra", "hydra_head", "hydra_mortar", "hydra_rewards"],
            post_processors=[
                "open_hill_cavity",
                "source_stalactites_64_64_8",
                "compiled_marker_catalog",
                "proximity_boss_activation",
            ],
            variants=hydra_lair_variants,
            landmarkKind="hydra_lair",
            bossSpawner=hydra_spawner,
            clearanceChunks=2,
            placementPass=SURFACE_NATIVE_PLACEMENT_PASS,
            rewardLoot="loot_tables/chests/tf_slice/hydra_reward.json",
        )
    )

    courtyard_variants = []
    for variant_index, layout_seed in enumerate(COURTYARD_VARIANT_SEEDS):
        variant_id = "v%02d" % variant_index
        structure = naga_courtyard(layout_seed)
        pieces = write_tiled(
            "naga_courtyard/%s" % variant_id,
            structure,
            COURTYARD_PIECE_VERTICAL_OFFSET,
        )
        courtyard_variants.append(
            {
                "id": variant_id,
                "weight": 1,
                "layoutSeed": layout_seed,
                "pieces": pieces,
                "bounds": _combined_bounds(pieces),
                "surfaceNative": write_surface_native_tiles(
                    "naga_courtyard",
                    variant_id,
                    structure,
                ),
            }
        )
    courtyard_spawner = {
        "entity": "tf_slice:forest_wyrm",
        "offset": [
            COURTYARD_MARGIN + COURTYARD_RADIUS,
            3,
            COURTYARD_MARGIN + COURTYARD_RADIUS,
        ],
        "activationRadius": 50,
        "markerBlock": "tf_slice:naga_boss_spawner",
    }
    catalog_entries.append(
        _catalog_entry(
            "naga_courtyard",
            "landmark_service",
            large_tags,
            courtyard_variants[0]["pieces"],
            dependencies=["forest_wyrm"],
            post_processors=[
                "source_maze_connectome",
                "hedge_floof_0_5",
                "wall_integrity_0_95",
                "wall_decay_0_1",
                "terrace_template_processor",
                "proximity_boss_activation",
            ],
            variants=courtyard_variants,
            landmarkKind="naga_courtyard",
            bossSpawner=courtyard_spawner,
        )
    )

    lich_variants = []
    for seed in range(LICH_TOWER_VARIANT_COUNT):
        variant_id = "v%02d" % seed
        structure = lich_tower(seed)
        pieces = write_tiled(
            "lich_tower/%s" % variant_id,
            structure,
        )
        lich_variants.append(
            {
                "id": variant_id,
                "weight": 1,
                "layoutSeed": structure.lich_tower_metadata["layoutSeed"],
                "bossSpawnerOffset": structure.lich_tower_metadata[
                    "bossSpawnerOffset"
                ],
                "controlledSpawnOffsets": structure.lich_tower_metadata[
                    "controlledSpawnOffsets"
                ],
                "rotations": [0, 90, 180, 270],
                "pieces": pieces,
                "bounds": _combined_bounds(pieces),
                "surfaceNative": write_surface_native_tiles(
                    "lich_tower",
                    variant_id,
                    structure,
                ),
            }
        )
    lich_spawner = {
        "kind": "lich",
        "entity": "tf_slice:lich",
        "offset": list(lich_variants[0]["bossSpawnerOffset"]),
        "activationRadius": 9,
        "minPlayerYOffset": -4,
        # NetEase keeps the marker collision-solid until the actor survives
        # stable confirmation. Spawn on top of it instead of inside it.
        "spawnYOffset": 0.5,
        "progressObjective": "tf_naga_defeated",
        "initialAttackCooldown": 40,
        "markerBlock": "tf_slice:lich_boss_spawner",
    }
    for variant in lich_variants:
        variant["bossSpawner"] = dict(
            lich_spawner,
            offset=list(variant["bossSpawnerOffset"]),
        )
    catalog_entries.append(
        _catalog_entry(
            "lich_tower",
            "landmark_service",
            [
                "dm33027004",
                "tf_slice_biome_forest",
                "tf_slice_biome_dense_forest",
                "tf_slice_biome_oak_savannah",
                "tf_slice_biome_mushroom_forest",
                "tf_slice_biome_firefly_forest",
                "tf_slice_biome_clearing",
                "tf_slice_biome_spooky_forest",
            ],
            lich_variants[0]["pieces"],
            dependencies=[
                "lich",
                "lich_shadow_clone",
                "lich_minion",
                "death_tome",
                "lich_tower_loot",
            ],
            post_processors=[
                "loot_and_spawner_markers",
                "proximity_boss_activation",
                "controlled_tower_spawns",
            ],
            variants=lich_variants,
            landmarkKind="lich_tower",
            bossSpawner=lich_spawner,
            controlledSpawns={
                "cap": 12,
                "intervalTicks": 100,
                "activationRadius": 32,
                "weights": [
                    {"entity": "minecraft:zombie", "weight": 10, "group": [1, 2]},
                    {"entity": "minecraft:skeleton", "weight": 10, "group": [1, 2]},
                    {"entity": "tf_slice:death_tome", "weight": 10, "group": [2, 3]},
                    {"entity": "minecraft:creeper", "weight": 1, "group": [1, 1]},
                    {"entity": "minecraft:enderman", "weight": 1, "group": [1, 2]},
                    {"entity": "minecraft:witch", "weight": 1, "group": [1, 1]},
                ],
            },
            rewardLoot="loot_tables/chests/tf_slice/lich_tower_reward.json",
            sourceManifest={
                "jarSha256": "0BDC89263616D1B35C32EF82C5E9C14CBD20368E2FE8B468C72A28320BE7A778",
                "layout": "4.3.2508 programmatic lichtower component grammar",
                "sourceCommit": lich_tower_legacy_port.SOURCE_COMMIT,
                "sourceClasses": list(lich_tower_legacy_port.SOURCE_CLASSES),
                "excluded": "4.7+ rights-reserved structure templates",
            },
        )
    )

    quest_grove_structure = quest_grove()
    quest_grove_pieces = write_tiled(
        "quest_grove/v00",
        quest_grove_structure,
    )
    quest_grove_variant = {
        "id": "v00",
        "weight": 1,
        "layoutSeed": 0,
        "pieces": quest_grove_pieces,
        "bounds": _combined_bounds(quest_grove_pieces),
        "surfaceNative": write_surface_native_tiles(
            "quest_grove",
            "v00",
            quest_grove_structure,
        ),
    }
    catalog_entries.append(
        _catalog_entry(
            "quest_grove",
            "landmark_service",
            ["dm33027004", "tf_slice_biome_enchanted_forest"],
            quest_grove_pieces,
            dependencies=["quest_ram", "quest_grove_dropper"],
            post_processors=["quest_ram_and_wool_dropper_markers"],
            variants=[quest_grove_variant],
            landmarkKind="quest_grove",
        )
    )

    mushroom_variants = []
    for seed in range(MUSHROOM_TOWER_VARIANT_COUNT):
        variant_id = "v%02d" % seed
        structure = mushroom_tower(seed)
        pieces = write_tiled(
            "mushroom_tower/%s" % variant_id,
            structure,
        )
        mushroom_variants.append(
            {
                "id": variant_id,
                "weight": 1,
                "layoutSeed": seed,
                "pieces": pieces,
                "bounds": _combined_bounds(pieces),
                "surfaceNative": write_surface_native_tiles(
                    "mushroom_tower",
                    variant_id,
                    structure,
                ),
            }
        )
    catalog_entries.append(
        _catalog_entry(
            "mushroom_tower",
            "landmark_service",
            ["dm33027004", "tf_slice_dense_mushroom_forest"],
            mushroom_variants[0]["pieces"],
            post_processors=[],
            variants=mushroom_variants,
            landmarkKind="mushroom_tower",
        )
    )

    hill_variants = []
    for index, diameter in enumerate((36, 68, 100)):
        underground_offset = ruin_logic.hollow_hill_piece_depth(index + 1)
        size_name = ("small", "medium", "large")[index]
        landmark_kind = (
            "small_hill",
            "medium_hill",
            "large_hill",
        )[index]
        terrain_seed = HOLLOW_HILL_TERRAIN_SEEDS[diameter]
        shell, _unused_interior = hollow_hill(
            diameter,
            HOLLOW_HILL_CONTENT_SEEDS[diameter][0],
            split_layers=True,
            terrain_seed=terrain_seed,
        )
        shell_pieces = write_tiled(
            "hollow_hill/%s/shell" % size_name,
            shell,
        )
        for piece in shell_pieces:
            piece["offset"][1] = -underground_offset
            piece["layer"] = "shell"
            # The service already carves the exact cosine cavity block by
            # block. Clearing the whole sparse-template box here also removes
            # the terrain-generated stone roof above that cavity.
            piece["removeBlock"] = False
        for variant_index, content_seed in enumerate(
            HOLLOW_HILL_CONTENT_SEEDS[diameter]
        ):
            _unused_shell, interior = hollow_hill(
                diameter,
                content_seed,
                split_layers=True,
                terrain_seed=terrain_seed,
            )
            interior_pieces = write_tiled(
                "hollow_hill/%s/interior_v%02d"
                % (size_name, variant_index),
                interior,
            )
            for piece in interior_pieces:
                piece["offset"][1] = -underground_offset
                piece["layer"] = "interior"
                piece["removeBlock"] = False
            pieces = shell_pieces + interior_pieces
            combined = SparseStructure(
                shell.size,
                "hollow_hill_%s_v%02d_surface"
                % (size_name, variant_index),
            )
            combined.merge(shell)
            combined.merge(interior)
            variant_id = "%s_v%02d" % (size_name, variant_index)
            hill_variants.append(
                {
                    "id": variant_id,
                    "landmarkKind": landmark_kind,
                    "diameter": diameter,
                    "terrainDiameter": diameter + 12,
                    "terrainDetailSeed": terrain_seed,
                    "weight": 1,
                    "layoutSeed": content_seed,
                    "pieces": pieces,
                    "bounds": _combined_bounds(pieces),
                    "surfaceNative": write_surface_native_tiles(
                        landmark_kind,
                        variant_id,
                        combined,
                        terrain_seed,
                    ),
                }
            )
    catalog_entries.append(
        _catalog_entry(
            "hollow_hill",
            "landmark_service",
            large_tags,
            hill_variants[0]["pieces"],
            dependencies=[
                "hollow_hill_loot",
                "redcap",
                "redcap_sapper",
                "kobold",
                "swarm_spider",
                "wraith",
                "slime_beetle",
                "fire_beetle",
                "pinch_beetle",
            ],
            post_processors=["loot_and_spawner_markers"],
            variants=hill_variants,
            landmarkKind=["small_hill", "medium_hill", "large_hill"],
        )
    )

    try:
        import build_phantom_urghast_structures as route_structures
    except ImportError:  # pragma: no cover - package import in tests
        from tools import build_phantom_urghast_structures as route_structures
    route_api = {
        "SparseStructure": SparseStructure,
        "FORBIDDEN_OUTPUT_BLOCKS": FORBIDDEN_OUTPUT_BLOCKS,
        "set_loot_container": set_loot_container,
        "set_spawner": set_spawner,
        "write_single": write_single,
        "combined_bounds": _combined_bounds,
        "catalog_entry": _catalog_entry,
        "write_surface_native_tiles": write_surface_native_tiles,
        "write_dark_tower_canopy_cleanup_tiles": (
            write_dark_tower_canopy_cleanup_tiles
        ),
    }
    catalog_entries.append(
        route_structures.build_knight_stronghold_entry(route_api)
    )
    catalog_entries.append(
        route_structures.build_dark_tower_entry(route_api)
    )

    catalog = {
        "schemaVersion": 3,
        "sourceVersion": SOURCE_VERSION,
        "source": {
            "jar": "twilightforest-1.20.1-4.3.2508-universal.jar",
            "policy": "local jar behavior overrides encyclopedia prose",
        },
        "budget": {
            "baselineFileCount": release_metadata.STRUCTURE_BASELINE_FILE_COUNT,
            "baselineUncompressedBytes": release_metadata.STRUCTURE_BASELINE_UNCOMPRESSED_BYTES,
            "maxFileCount": release_metadata.STRUCTURE_FILE_COUNT_LIMIT,
            "maxUncompressedBytes": release_metadata.STRUCTURE_UNCOMPRESSED_BYTES_LIMIT,
            "finalZipBaselineMultiplier": release_metadata.FINAL_ZIP_BASELINE_MULTIPLIER,
        },
        "structures": catalog_entries,
    }
    pinned_references = collect_external_ruin_structure_references(
        BP,
        OUTPUT_ROOT,
    )
    aliases, deduplication = deduplicate_ruin_structure_files(
        OUTPUT_ROOT,
        pinned_references,
    )
    catalog["structureAliases"] = aliases
    catalog["structureDeduplication"] = deduplication
    _write_json(OUTPUT_ROOT / "structure_catalog_v1.json", catalog)
    _write_runtime_catalog(catalog)
    guard_native_structure_rules(ROOT)
    return catalog


def validate(catalog):
    errors = []
    aliases = catalog.get("structureAliases", {})
    if not isinstance(aliases, dict):
        errors.append("structureAliases must be an object")
        aliases = {}
    for reference in sorted(aliases):
        try:
            resolved = resolve_ruin_structure_reference(reference, aliases)
        except ValueError as error:
            errors.append(str(error))
            continue
        source_path = BP / "structures" / (reference + ".mcstructure")
        target_path = BP / "structures" / (resolved + ".mcstructure")
        if source_path.exists():
            errors.append("aliased structure still exists %s" % source_path)
        if not target_path.is_file() or target_path.stat().st_size <= 64:
            errors.append("missing or empty alias target %s" % target_path)
    deduplication = catalog.get("structureDeduplication")
    if isinstance(deduplication, dict) and int(
        deduplication.get("removedFileCount", -1)
    ) != len(aliases):
        errors.append("structure deduplication alias count mismatch")
    ids = [entry["id"] for entry in catalog["structures"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate catalog ids")
    if "camp" in ids:
        errors.append("4.8 camp must not be generated")
    for entry in catalog["structures"]:
        references = list(entry.get("pieces", []))
        for variant in entry.get("variants", []):
            references.extend(variant.get("pieces", []))
            native = variant.get("nativeFeature")
            if native is not None:
                native_reference = str(native.get("structure", ""))
                if not native_reference.startswith("tf_slice/ruins/"):
                    errors.append(
                        "%s native feature is not a real ruin"
                        % entry["id"]
                    )
                try:
                    native_reference = resolve_ruin_structure_reference(
                        native_reference,
                        aliases,
                    )
                except ValueError as error:
                    errors.append(str(error))
                    continue
                native_path = BP / "structures" / (
                    native_reference + ".mcstructure"
                )
                if (
                    not native_path.is_file()
                    or native_path.stat().st_size <= 64
                ):
                    errors.append(
                        "missing or empty native feature %s" % native_path
                    )
        for piece in references:
            if piece["size"][0] > 16 and entry["strategy"] == "landmark_service":
                errors.append("%s has an oversized x tile" % entry["id"])
            if piece["size"][2] > 16 and entry["strategy"] == "landmark_service":
                errors.append("%s has an oversized z tile" % entry["id"])
            if (
                entry.get("verticalSliceHeight")
                and piece["size"][1] > int(entry["verticalSliceHeight"])
            ):
                errors.append("%s has an oversized y tile" % entry["id"])
            try:
                piece_reference = resolve_ruin_structure_reference(
                    piece["structure"],
                    aliases,
                )
            except ValueError as error:
                errors.append(str(error))
                continue
            path = BP / "structures" / (piece_reference + ".mcstructure")
            if not path.is_file() or path.stat().st_size <= 64:
                errors.append("missing or empty %s" % path)
    structure_files = list((BP / "structures").rglob("*.mcstructure"))
    structure_bytes = sum(path.stat().st_size for path in structure_files)
    budget = catalog.get("budget", {})
    if len(structure_files) > int(budget.get("maxFileCount", 0)):
        errors.append(
            "structure file budget exceeded: %d > %d"
            % (len(structure_files), int(budget["maxFileCount"]))
        )
    if structure_bytes > int(budget.get("maxUncompressedBytes", 0)):
        errors.append(
            "structure byte budget exceeded: %d > %d"
            % (structure_bytes, int(budget["maxUncompressedBytes"]))
        )
    if errors:
        raise ValueError("\n".join(errors))


def main(argv=None):
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="validate existing generated artifacts without rewriting them",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="explicitly rebuild generated artifacts, then validate them",
    )
    parser.add_argument(
        "--acknowledge-shared-artifact-write",
        action="store_true",
        help=(
            "confirm that this task owns the shared generated-artifact set"
        ),
    )
    parser.add_argument(
        "--write-lease-token",
        help="consume the one-shot user-approved shared-artifact write lease",
    )
    args = parser.parse_args(argv)
    if args.write and not args.acknowledge_shared_artifact_write:
        parser.error(
            "--write requires --acknowledge-shared-artifact-write"
        )
    if args.acknowledge_shared_artifact_write and not args.write:
        parser.error(
            "--acknowledge-shared-artifact-write is valid only with --write"
        )
    if args.write_lease_token and not args.write:
        parser.error("--write-lease-token is valid only with --write")
    with _exclusive_build_lock():
        if args.write:
            _consume_shared_artifact_write_lease(args.write_lease_token)
            catalog = build()
        else:
            catalog_path = OUTPUT_ROOT / "structure_catalog_v1.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        validate(catalog)
        catalog_bytes = json.dumps(
            catalog, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        print(
            "%s %d ruin entries; catalog sha256=%s"
            % (
                "built" if args.write else "checked",
                len(catalog["structures"]),
                hashlib.sha256(catalog_bytes).hexdigest(),
            )
        )
        print("structure pack validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
