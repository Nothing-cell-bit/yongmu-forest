#!/usr/bin/env python3
"""Offline component port of Twilight Forest 4.3.2508's Dark Tower.

The Java landmark is a graph of three ascending main towers, bridges,
recursive wings, key towers and four boss-trap towers.  NetEase cannot run the
Java piece assembler during world generation, so this module materializes two
deterministic selections of that grammar into one sparse structure each.
"""

from __future__ import print_function

import random


TOWERWOOD = "tf_slice:towerwood"
CRACKED_TOWERWOOD = "tf_slice:cracked_towerwood"
MOSSY_TOWERWOOD = "tf_slice:mossy_towerwood"
INFESTED_TOWERWOOD = "tf_slice:infested_towerwood"
ENCASED_TOWERWOOD = "tf_slice:encased_towerwood"
# Retained for catalog compatibility with already-built cleanup tiles.  New
# center-biome trees are prevented from tunnelling through tower floors, so no
# active feature rule dispatches this legacy post-tree cleanup mask.
DARK_FOREST_CANOPY_CLEANUP_HEIGHT = 44

PLANTER_TREE_PROFILES = (
    # Match the source configured features' straight-trunk height ranges.
    ("minecraft:oak_log", "minecraft:oak_leaves", 4, 6),
    ("minecraft:jungle_log", "minecraft:jungle_leaves", 3, 7),
    ("minecraft:birch_log", "minecraft:birch_leaves", 5, 7),
    (
        "tf_slice:twilight_oak_log",
        "tf_slice:twilight_oak_leaves",
        4,
        6,
    ),
    (
        "tf_slice:twilight_oak_log",
        "tf_slice:rainbow_oak_leaves",
        4,
        6,
    ),
)

PLANTER_TREE_REPLACEABLE_BLOCKS = frozenset(
    (
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:tallgrass",
        "minecraft:tall_grass",
        "minecraft:double_plant",
        "minecraft:vine",
        "minecraft:oak_leaves",
        "minecraft:jungle_leaves",
        "minecraft:birch_leaves",
        "tf_slice:twilight_oak_leaves",
        "tf_slice:rainbow_oak_leaves",
    )
)

MAIN_ROOM_TYPES = (
    "bottom_entrance",
    "reappearing_maze",
    "antibuilder_maze",
    "aquarium",
    "botanical",
    "netherwart",
    "lounge",
    "forge",
)
RANDOMIZED_MAIN_ROOM_TYPES = frozenset(MAIN_ROOM_TYPES[1:])
SMALL_ROOM_TYPES = (
    "reappearing_floor",
    "spawner",
    "lounge",
    "library",
    "piston_pulser",
    "lamp_experiment",
    "puzzle_chest",
)
ROOF_TYPES = ("antenna", "cactus", "rings", "four_post")
REQUIRED_ROOM_TYPES = frozenset(
    MAIN_ROOM_TYPES
    + SMALL_ROOM_TYPES
    + (
        "timber_maze",
        "builder_platforms",
        "small_timber_beams",
        "key_treasure",
        "reactor_experiment",
        "boss_trap",
    )
)
REQUIRED_LAYOUT_ROOM_TYPES = REQUIRED_ROOM_TYPES - RANDOMIZED_MAIN_ROOM_TYPES


def _select_main_room_type(roll, world_y, is_bottom=False, is_top=False):
    """Match DarkTowerMainComponent.decorateFloor's Java switch table."""
    roll = int(roll)
    world_y = int(world_y)
    if is_top:
        return ("aquarium", "botanical", "netherwart")[roll % 3]
    if is_bottom:
        choice = roll % 4
        if choice == 0:
            return "aquarium"
        if choice == 1:
            return "botanical"
        if choice == 2 and world_y > 64:
            return "netherwart"
        return "forge"

    choice = roll % 8
    if choice in (0, 1):
        return "reappearing_maze"
    if choice == 2:
        return "antibuilder_maze"
    if choice == 3:
        return "aquarium"
    if choice == 4:
        return "botanical"
    if choice == 5 and world_y > 64:
        return "netherwart"
    if choice in (5, 6):
        return "lounge"
    return "forge"


def _towerwood_for(x, y, z, salt=0):
    """Coordinate-stable equivalent of the source towerwood selector."""
    value = (x * 73428767 + y * 912931 + z * 19349663 + salt * 83492791) & 0xFF
    if value < 26:
        return CRACKED_TOWERWOOD
    if value < 52:
        return MOSSY_TOWERWOOD
    if value < 58:
        return INFESTED_TOWERWOOD
    return TOWERWOOD


def _bounds(center, size):
    radius = int(size) // 2
    return (
        int(center[0]) - radius,
        int(center[1]) - radius,
        int(center[0]) + radius,
        int(center[1]) + radius,
    )


def dark_tower_canopy_cleanup_positions(
    structure,
    markers,
    surface_ground_y,
):
    """Return low tower-interior cells which the author left as air."""
    cleanup_top = int(surface_ground_y) + DARK_FOREST_CANOPY_CLEANUP_HEIGHT
    towers = []
    seen = set()
    for marker_group in ("mainTowers", "wingTowers"):
        for tower in markers.get(marker_group, ()):
            tower_id = str(tower.get("id", ""))
            if not tower_id or tower_id in seen:
                continue
            seen.add(tower_id)
            towers.append(tower)

    cleanup_positions = set()
    for tower in towers:
        bottom_y = int(tower["bottomY"])
        height = int(tower["height"])
        minimum_y = max(bottom_y + 1, int(surface_ground_y) + 1)
        maximum_y = min(bottom_y + height - 2, cleanup_top)
        if minimum_y > maximum_y:
            continue
        center_x, center_z = [int(value) for value in tower["center"]]
        radius = int(tower["size"]) // 2
        for x in range(center_x - radius + 1, center_x + radius):
            for z in range(center_z - radius + 1, center_z + radius):
                for y in range(minimum_y, maximum_y + 1):
                    position = (x, y, z)
                    existing = structure.blocks.get(position)
                    if (
                        existing is not None
                        and existing[0]
                        not in ("minecraft:air", "minecraft:cave_air")
                    ):
                        continue
                    cleanup_positions.add(position)
    return cleanup_positions


def dark_tower_canopy_cleanup_runs(positions):
    """Compress exact authored-air cells into deterministic vertical runs."""
    columns = {}
    for x, y, z in positions:
        columns.setdefault((int(x), int(z)), set()).add(int(y))
    runs = []
    for x, z in sorted(columns):
        heights = sorted(columns[(x, z)])
        if not heights:
            continue
        minimum_y = maximum_y = heights[0]
        for y in heights[1:]:
            if y == maximum_y + 1:
                maximum_y = y
                continue
            runs.append([x, z, minimum_y, maximum_y])
            minimum_y = maximum_y = y
        runs.append([x, z, minimum_y, maximum_y])
    return runs


def dark_tower_tree_root_shield_positions(
    markers,
    surface_ground_y,
    structure_minimum_y=0,
):
    """Return hidden foundation cells beneath authored ground-level rooms.

    The center-biome tree search must stay bounded for NetEase Chunk PP
    stability.  A one-block tower floor does not stop that search from finding
    buried grass, so only the real interior columns of towers touching the
    terrain receive a solid hidden foundation down to the structure bottom.
    Elevated wings and every column outside those authored interiors remain
    untouched.
    """
    ground_y = int(surface_ground_y)
    minimum_y = int(structure_minimum_y)
    if minimum_y > ground_y:
        return set()

    towers = []
    seen = set()
    for marker_group in ("mainTowers", "wingTowers"):
        for tower in markers.get(marker_group, ()):
            tower_id = str(tower.get("id", ""))
            if not tower_id or tower_id in seen:
                continue
            seen.add(tower_id)
            if int(tower["bottomY"]) <= ground_y:
                towers.append(tower)

    positions = set()
    for tower in towers:
        center_x, center_z = [int(value) for value in tower["center"]]
        radius = int(tower["size"]) // 2
        for x in range(center_x - radius + 1, center_x + radius):
            for z in range(center_z - radius + 1, center_z + radius):
                for y in range(minimum_y, ground_y + 1):
                    positions.add((x, y, z))
    return positions


def _fill(structure, start, end, block, states=None):
    for x in range(int(start[0]), int(end[0]) + 1):
        for y in range(int(start[1]), int(end[1]) + 1):
            for z in range(int(start[2]), int(end[2]) + 1):
                structure.set(x, y, z, block, states)


def _local(center, size, x, z, rotation=0):
    minimum_x, minimum_z, maximum_x, maximum_z = _bounds(center, size)
    x = int(x)
    z = int(z)
    rotation = int(rotation) % 4
    if rotation == 1:
        x, z = size - 1 - z, x
    elif rotation == 2:
        x, z = size - 1 - x, size - 1 - z
    elif rotation == 3:
        x, z = z, size - 1 - x
    return minimum_x + x, minimum_z + z


def _rotated_states(states, rotation):
    """Rotate Bedrock cardinal block states with the authored local geometry."""
    states = dict(states or {})
    stair_clockwise = {0: 2, 2: 1, 1: 3, 3: 0}
    facing_clockwise = {2: 5, 5: 3, 3: 4, 4: 2}
    cardinal_clockwise = {
        "north": "east",
        "east": "south",
        "south": "west",
        "west": "north",
    }
    lever_clockwise = {
        "north": "east",
        "east": "south",
        "south": "west",
        "west": "north",
        "up_north_south": "up_east_west",
        "up_east_west": "up_north_south",
        "down_north_south": "down_east_west",
        "down_east_west": "down_north_south",
    }
    for _unused in range(int(rotation) % 4):
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
        if states.get("cardinal_direction") in cardinal_clockwise:
            states["cardinal_direction"] = cardinal_clockwise[
                states["cardinal_direction"]
            ]
        if states.get("lever_direction") in lever_clockwise:
            states["lever_direction"] = lever_clockwise[
                states["lever_direction"]
            ]
    return states


def _stair_states(direction, upside_down=False):
    # Java's stair FACING names the direction the stair ascends.  Bedrock's
    # legacy ``weirdo_direction`` names the opposite/high back edge, so copying
    # the cardinal name directly turns every authored stair through 180°.
    return {
        "weirdo_direction": {
            "east": 1,
            "west": 0,
            "south": 3,
            "north": 2,
        }[str(direction)],
        "upside_down_bit": bool(upside_down),
    }


def _ladder_states(java_facing):
    """Translate Java ladder FACING to Bedrock's backing-face state."""
    return {
        "facing_direction": {2: 3, 3: 2, 4: 5, 5: 4}[int(java_facing)]
    }


def _lever_states(attachment, axis_or_direction="east_west", powered=False):
    attachment = str(attachment)
    value = str(axis_or_direction)
    if attachment == "floor":
        direction = "up_%s" % value
    elif attachment == "ceiling":
        direction = "down_%s" % value
    elif attachment == "wall" and value in ("north", "east", "south", "west"):
        # Java's wall-lever direction points toward its supporting block.
        # Bedrock's lever_direction points away from that support, so copying
        # the cardinal name puts the support on the wrong side and makes the
        # post-pass support repair synthesize a stray towerwood block.
        direction = {
            "north": "south",
            "east": "west",
            "south": "north",
            "west": "east",
        }[value]
    else:
        raise ValueError("invalid lever attachment: %s %s" % (attachment, value))
    return {"lever_direction": direction, "open_bit": bool(powered)}


LEVER_SUPPORT_DELTAS = {
    # Bedrock's cardinal value is the direction the lever faces; the block it
    # is attached to is behind it on the opposite side.
    "east": (-1, 0, 0),
    "west": (1, 0, 0),
    "south": (0, 0, -1),
    "north": (0, 0, 1),
    "up_north_south": (0, -1, 0),
    "up_east_west": (0, -1, 0),
    "down_north_south": (0, 1, 0),
    "down_east_west": (0, 1, 0),
}


def _restore_authored_lever_supports(structure):
    """Keep structure-serialized levers attached after all piece overlays."""
    for position, block in list(structure.blocks.items()):
        if block[0] != "minecraft:lever":
            continue
        direction = block[1].get("lever_direction")
        delta = LEVER_SUPPORT_DELTAS.get(direction)
        if delta is None:
            continue
        support = tuple(
            int(position[index]) + int(delta[index]) for index in range(3)
        )
        existing = structure.blocks.get(support)
        if existing is not None and existing[0] != "minecraft:air":
            continue
        structure.set(
            support[0], support[1], support[2], ENCASED_TOWERWOOD
        )


def _set_local(structure, center, size, x, y, z, block, rotation=0, states=None):
    world_x, world_z = _local(center, size, x, z, rotation)
    structure.set(world_x, y, world_z, block, _rotated_states(states, rotation))


def _set_item_frame_local(
    structure, center, size, x, y, z, item_name, facing, rotation=0
):
    world_x, world_z = _local(center, size, x, z, rotation)
    structure.set(
        world_x,
        y,
        world_z,
        "minecraft:frame",
        _rotated_states({"facing_direction": int(facing)}, rotation),
        {
            "id": "ItemFrame",
            "x": world_x,
            "y": int(y),
            "z": world_z,
            "isMovable": 1,
            "ItemDropChance": 1.0,
            "ItemRotation": 0.0,
            "Item": {
                "Name": str(item_name),
                "Count": 1,
                "Damage": 0,
            },
        },
    )


def _fill_local(
    structure, center, size, start_x, start_y, start_z, end_x, end_y, end_z,
    block, rotation=0, states=None,
):
    for x in range(start_x, end_x + 1):
        for y in range(start_y, end_y + 1):
            for z in range(start_z, end_z + 1):
                _set_local(
                    structure, center, size, x, y, z, block, rotation, states
                )


def _render_encased_shell(structure, center, size, bottom_y, height, salt):
    minimum_x, minimum_z, maximum_x, maximum_z = _bounds(center, size)
    top_y = int(bottom_y) + int(height) - 1
    for y in range(bottom_y, top_y + 1):
        for x in range(minimum_x, maximum_x + 1):
            for z in (minimum_z, maximum_z):
                edge_count = int(x in (minimum_x, maximum_x)) + int(
                    y in (bottom_y, top_y)
                )
                block = ENCASED_TOWERWOOD if edge_count >= 2 else _towerwood_for(
                    x, y, z, salt
                )
                structure.set(x, y, z, block)
        for z in range(minimum_z + 1, maximum_z):
            for x in (minimum_x, maximum_x):
                edge_count = int(z in (minimum_z, maximum_z)) + int(
                    y in (bottom_y, top_y)
                )
                block = ENCASED_TOWERWOOD if edge_count >= 2 else _towerwood_for(
                    x, y, z, salt
                )
                structure.set(x, y, z, block)
    for x in range(minimum_x, maximum_x + 1):
        for z in range(minimum_z, maximum_z + 1):
            edge = x in (minimum_x, maximum_x) or z in (minimum_z, maximum_z)
            structure.set(
                x,
                bottom_y,
                z,
                ENCASED_TOWERWOOD if edge else TOWERWOOD,
            )
            structure.set(
                x,
                top_y,
                z,
                ENCASED_TOWERWOOD if edge else TOWERWOOD,
            )
    return top_y


def _render_beard(structure, center, size, bottom_y):
    # The source beard narrows down from elevated wings instead of extending a
    # full rectangular column to terrain.
    radius = int(size) // 2
    for depth in range(1, radius + 1):
        inset = depth
        y = int(bottom_y) - depth
        if y < 0:
            break
        minimum_x, minimum_z, maximum_x, maximum_z = _bounds(center, size)
        for x in range(minimum_x + inset, maximum_x - inset + 1):
            for z in range(minimum_z + inset, maximum_z - inset + 1):
                structure.set(x, y, z, ENCASED_TOWERWOOD)


def _bridge_path(start, end):
    x, y, z = [int(value) for value in start]
    end_x, end_y, end_z = [int(value) for value in end]
    points = []
    while x != end_x:
        points.append((x, y, z))
        x += 1 if end_x > x else -1
    while z != end_z:
        points.append((x, y, z))
        z += 1 if end_z > z else -1
    points.append((x, y, z))
    return points


def _render_bridge(structure, start, end):
    points = _bridge_path(start, end)
    for index, (x, y, z) in enumerate(points):
        previous = points[max(0, index - 1)]
        following = points[min(len(points) - 1, index + 1)]
        along_x = previous[0] != following[0]
        for across in range(-2, 3):
            px = x if along_x else x + across
            pz = z + across if along_x else z
            structure.set(px, y, pz, ENCASED_TOWERWOOD)
            structure.set(px, y + 4, pz, ENCASED_TOWERWOOD)
            if abs(across) == 2:
                for py in range(y + 1, y + 4):
                    structure.set(px, py, pz, TOWERWOOD)
            else:
                for py in range(y + 1, y + 4):
                    structure.set(px, py, pz, "minecraft:air")


def _render_connection(structure, first_center, first_size, second_center, second_size, y):
    """Join two tower walls without drawing a corridor through their cores."""
    first_center = tuple(first_center)
    second_center = tuple(second_center)
    dx = second_center[0] - first_center[0]
    dz = second_center[1] - first_center[1]
    if dx and dz:
        raise ValueError(
            "DarkTowerBridgeComponent requires cardinal tower centers: %r -> %r"
            % (first_center, second_center)
        )
    if abs(dx) >= abs(dz):
        direction = 1 if dx >= 0 else -1
        start = (
            first_center[0] + direction * (int(first_size) // 2),
            y,
            first_center[1],
        )
        end = (
            second_center[0] - direction * (int(second_size) // 2),
            y,
            second_center[1],
        )
    else:
        direction = 1 if dz >= 0 else -1
        start = (
            first_center[0],
            y,
            first_center[1] + direction * (int(first_size) // 2),
        )
        end = (
            second_center[0],
            y,
            second_center[1] - direction * (int(second_size) // 2),
        )
    points = [start, end]
    segments = []
    for segment_start, segment_end in zip(points, points[1:]):
        _render_bridge(structure, segment_start, segment_end)
        segments.append(
            {"start": list(segment_start), "end": list(segment_end)}
        )
    # DarkTowerBridgeComponent starts one block below the opening supplied by
    # each tower component.  Consequently both tower doors start at y + 1 and
    # the bridge floor itself remains at y.  Materialize both source openings
    # here; callers may replace one plane with a locked/reappearing variant.
    _door_plane(
        structure,
        first_center,
        second_center,
        int(y) + 1,
        size=first_size,
    )
    _door_plane(
        structure,
        second_center,
        first_center,
        int(y) + 1,
        size=second_size,
    )

    # The source bridge and accent threshold stop at the wall plane.  Extending
    # a synthetic landing two blocks into the room puts a floor block directly
    # above the final stair/ladder tread and seals the authored circulation.
    return segments


def _render_balcony(structure, markers, tower, direction, y, balcony_id):
    """Attach the source five-wide fenced balcony through a reappearing door."""
    cx, cz = tower["center"]
    dx, dz = direction
    perpendicular_x, perpendicular_z = -dz, dx
    radius = int(tower["size"]) // 2
    outer = radius + 4
    for forward in range(radius + 1, outer + 1):
        for across in range(-2, 3):
            x = cx + dx * forward + perpendicular_x * across
            z = cz + dz * forward + perpendicular_z * across
            structure.set(x, y, z, ENCASED_TOWERWOOD)
            if forward == outer or abs(across) == 2:
                structure.set(x, y + 1, z, "minecraft:oak_fence")

    door_positions = []
    for across in range(-1, 2):
        for dy in range(1, 4):
            x = cx + dx * radius + perpendicular_x * across
            z = cz + dz * radius + perpendicular_z * across
            structure.set(x, y + dy, z, "tf_slice:reappearing_block")
            door_positions.append([x, y + dy, z])
    markers["balconies"].append(
        {
            "id": balcony_id,
            "tower": tower["id"],
            "offset": [cx + dx * outer, y, cz + dz * outer],
            "door": door_positions[4],
            "doorBlock": "tf_slice:reappearing_block",
        }
    )


def _render_three_quarter_floor(
    structure,
    center,
    y,
    rotation,
    is_bottom=False,
    is_top=False,
    include_stairs=True,
):
    size = 19
    half = size // 2
    _fill_local(
        structure, center, size, half + 1, y, 1, size - 2, y, half + 1,
        TOWERWOOD, rotation,
    )
    _fill_local(
        structure, center, size, 1, y, half + 1, size - 2, y, size - 2,
        TOWERWOOD, rotation,
    )
    start_z = 1 if is_bottom else 3
    _fill_local(
        structure, center, size, 1, y, half, half, y, half,
        ENCASED_TOWERWOOD, rotation,
    )
    _fill_local(
        structure, center, size, half, y, start_z, half, y, half,
        ENCASED_TOWERWOOD, rotation,
    )
    _fill_local(
        structure, center, size, 1, y + 1, half, half, y + 1, half,
        "minecraft:oak_fence", rotation,
    )
    _fill_local(
        structure, center, size, half, y + 1, start_z, half, y + 1, half,
        "minecraft:oak_fence", rotation,
    )
    if is_top:
        _fill_local(
            structure, center, size, 1, y, half - 2, 3, y, half,
            ENCASED_TOWERWOOD, rotation,
        )
        _fill_local(
            structure, center, size, 1, y + 1, half - 2, 3, y + 1, half,
            "minecraft:oak_fence", rotation,
        )
    if include_stairs:
        _render_large_stairs_up(structure, center, y, rotation)


def _render_large_stairs_up(structure, center, y, rotation):
    """Port DarkTowerMainComponent.makeLargeStairsUp verbatim."""
    size = 19
    half = size // 2
    for step in range(5):
        z = half - step + 4
        stair_y = y + step + 1
        for x in (1, 2):
            _set_local(
                structure, center, size, x, stair_y, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states("south"),
            )
        for x in (1, 2, 3):
            _set_local(
                structure, center, size, x, stair_y, z - 1,
                TOWERWOOD, rotation,
            )
        if 0 < step < 4:
            _set_local(
                structure, center, size, 3, stair_y, z,
                ENCASED_TOWERWOOD, rotation,
            )
            for dy in (1, 2):
                _set_local(
                    structure, center, size, 3, stair_y + dy, z,
                    "minecraft:oak_fence", rotation,
                )
        elif step == 0:
            _set_local(
                structure, center, size, 3, stair_y, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states("east"),
            )


def _main_stair_flights(tower, zone):
    """Return every non-arena main flight in its authored rotation."""
    flights = [(int(tower["bottomY"]), int(tower["bottomY"]) % 4)]
    rotation = (int(tower["bottomY"]) % 4 - 1) % 4
    lower_floors = list(zone["lowerFloors"])
    for index, floor_y in enumerate(lower_floors):
        if index < len(lower_floors) - 1:
            flights.append((int(floor_y), rotation))
        rotation = (rotation - 1) % 4
    rotation = int(zone["topFloorsStart"]) % 4
    upper_floors = list(zone["upperFloors"])
    for index, floor_y in enumerate(upper_floors):
        if index < len(upper_floors) - 1:
            flights.append((int(floor_y), rotation))
        rotation = (rotation - 1) % 4
    return flights


def _restore_main_stair_circulation(structure, tower, zone):
    """Reapply source stairs after merged child openings and clear headroom."""
    center = tuple(tower["center"])
    for floor_y, rotation in _main_stair_flights(tower, zone):
        _render_large_stairs_up(structure, center, floor_y, rotation)
        for step in range(5):
            stair_y = floor_y + step + 1
            stair_z = 19 // 2 - step + 4
            for local_x in (1, 2):
                for head_y in (stair_y + 1, stair_y + 2):
                    _set_local(
                        structure,
                        center,
                        19,
                        local_x,
                        head_y,
                        stair_z,
                        "minecraft:air",
                        rotation,
                    )


def _pillar_frame(structure, center, size, x, y, z, width, height, length, rotation):
    for dx in range(width):
        for dz in range(length):
            post = (
                (dx % 3 == 0 or dx == width - 1)
                and (dz % 3 == 0 or dz == length - 1)
            )
            if post:
                for dy in range(1, height + 1):
                    _set_local(
                        structure, center, size, x + dx, y + dy, z + dz,
                        ENCASED_TOWERWOOD, rotation,
                    )
                continue
            direction = None
            if dx == 0:
                direction = "west"
            elif dx == width - 1:
                direction = "east"
            elif dz == 0:
                direction = "north"
            elif dz == length - 1:
                direction = "south"
            if direction is None:
                continue
            for dy, upside_down in ((1, False), (height, True)):
                _set_local(
                    structure, center, size, x + dx, y + dy, z + dz,
                    "minecraft:spruce_stairs", rotation,
                    _stair_states(direction, upside_down),
                )
            for dy in range(2, height):
                _set_local(
                    structure, center, size, x + dx, y + dy, z + dz,
                    "minecraft:oak_fence", rotation,
                )


def _fire_pit(structure, center, size, x, y, z, rotation):
    for stair_x, stair_z, direction in (
        (x - 1, z, "west"),
        (x + 1, z, "east"),
        (x, z + 1, "south"),
        (x, z - 1, "north"),
    ):
        _set_local(
            structure, center, size, stair_x, y, stair_z,
            "minecraft:spruce_stairs", rotation,
            _stair_states(direction),
        )
    for dx, dz in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        _set_local(
            structure, center, size, x + dx, y, z + dz,
            ENCASED_TOWERWOOD, rotation,
        )
    _set_local(
        structure, center, size, x, y, z,
        "minecraft:netherrack", rotation,
    )
    _set_local(
        structure, center, size, x, y + 1, z,
        "minecraft:fire", rotation,
    )


def _record_room(markers, tower_id, room_type, center, y, size=19):
    markers["rooms"].append(
        {
            "tower": tower_id,
            "type": room_type,
            "offset": [int(center[0]), int(y), int(center[1])],
            "size": int(size),
        }
    )


def _grow_tree_planter(
    structure,
    tower_id,
    center,
    floor_y,
    rotation,
):
    """Grow one deterministic source-height tree into final authored air."""
    planter_y = int(floor_y) + 1
    tree_seed = (
        sum(ord(character) for character in str(tower_id))
        + int(floor_y)
        + int(rotation)
    )
    tree_index = tree_seed % len(PLANTER_TREE_PROFILES)
    log_block, leaf_block, minimum_height, maximum_height = (
        PLANTER_TREE_PROFILES[tree_index]
    )
    trunk_height = minimum_height + (
        (tree_seed // len(PLANTER_TREE_PROFILES))
        % (maximum_height - minimum_height + 1)
    )
    root_y = planter_y + 1
    trunk_positions = []
    for tree_y in range(root_y, root_y + trunk_height):
        world_x, world_z = _local(center, 19, 6, 12, rotation)
        position = (world_x, tree_y, world_z)
        existing = structure.blocks.get(position)
        if (
            existing is not None
            and existing[0] not in PLANTER_TREE_REPLACEABLE_BLOCKS
        ):
            return False
        trunk_positions.append(position)

    for world_x, tree_y, world_z in trunk_positions:
        structure.set(world_x, tree_y, world_z, log_block)

    trunk_top = root_y + trunk_height - 1
    for canopy_y, radius in (
        (trunk_top - 1, 2),
        (trunk_top, 2),
        (trunk_top + 1, 1),
    ):
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if abs(dx) == radius and abs(dz) == radius:
                    continue
                world_x, world_z = _local(
                    center,
                    19,
                    6 + dx,
                    12 + dz,
                    rotation,
                )
                position = (world_x, canopy_y, world_z)
                existing = structure.blocks.get(position)
                if (
                    existing is not None
                    and existing[0] != log_block
                    and existing[0] not in PLANTER_TREE_REPLACEABLE_BLOCKS
                ):
                    continue
                if existing is not None and existing[0] == log_block:
                    continue
                structure.set(world_x, canopy_y, world_z, leaf_block)
    return True


def _render_tree_planter(
    structure,
    tower_id,
    center,
    floor_y,
    rotation,
    grow_tree=True,
):
    """Restore the source's five-way live tree inside its authored planter."""
    planter_y = int(floor_y) + 1
    for local_x, local_z in ((5, 11), (5, 13), (7, 11), (7, 13)):
        _set_local(
            structure,
            center,
            19,
            local_x,
            planter_y,
            local_z,
            ENCASED_TOWERWOOD,
            rotation,
        )
    for local_x, local_z, direction in (
        (5, 12, "west"),
        (7, 12, "east"),
        (6, 13, "south"),
        (6, 11, "north"),
    ):
        _set_local(
            structure,
            center,
            19,
            local_x,
            planter_y,
            local_z,
            "minecraft:spruce_stairs",
            rotation,
            _stair_states(direction),
        )
    _set_local(
        structure,
        center,
        19,
        6,
        planter_y,
        12,
        # NetEase's later biome tree pass must not treat the same indoor soil
        # as another natural tree root.
        "minecraft:coarse_dirt",
        rotation,
    )
    if not grow_tree:
        return True
    return _grow_tree_planter(
        structure,
        tower_id,
        center,
        floor_y,
        rotation,
    )


def _decorate_main_room(
    structure,
    markers,
    api,
    tower_id,
    room_type,
    center,
    floor_y,
    rotation,
    pending_planters=None,
):
    size = 19
    set_loot_container = api["set_loot_container"]
    set_spawner = api["set_spawner"]
    _record_room(markers, tower_id, room_type, center, floor_y, size)

    if room_type == "bottom_entrance":
        for x, z in ((3, 13), (13, 3), (13, 13)):
            _fire_pit(
                structure, center, size, x, floor_y + 1, z, rotation
            )
        _pillar_frame(structure, center, size, 7, floor_y, 7, 3, 4, 3, rotation)
    elif room_type == "reappearing_maze":
        # Port the source 6x6 TFMaze raw grid.  The staircase quarter is marked
        # as ROOM, a recursive backtracker carves the remaining L-shaped area,
        # and only a 30% subset of carved walls become reappearing doors.
        raw_size = 13
        room_value = 5
        door_value = 6
        raw = [[0 for _z in range(raw_size)] for _x in range(raw_size)]

        def put_raw(raw_x, raw_z, value):
            if 0 <= raw_x < raw_size and 0 <= raw_z < raw_size:
                raw[raw_x][raw_z] = value

        for edge in range(raw_size):
            put_raw(edge, 0, room_value)
            put_raw(edge, raw_size - 1, room_value)
            put_raw(0, edge, room_value)
            put_raw(raw_size - 1, edge, room_value)
        for raw_x in range(1, 6):
            for raw_z in range(1, 6):
                put_raw(raw_x, raw_z, room_value)
        for raw_z in range(6, 10):
            put_raw(1, raw_z, room_value)
        put_raw(1, 10, door_value)
        put_raw(6, 1, room_value)
        put_raw(7, 1, room_value)
        put_raw(8, 1, door_value)

        maze_random = random.Random(
            int(floor_y) * 90342903
            + int(center[0]) * 73428767
            + int(center[1]) * 19349663
        )

        def cell_value(cell_x, cell_z):
            if not (0 <= cell_x < 6 and 0 <= cell_z < 6):
                return None
            return raw[cell_x * 2 + 1][cell_z * 2 + 1]

        def visit(cell_x, cell_z):
            put_raw(cell_x * 2 + 1, cell_z * 2 + 1, 1)
            while True:
                neighbors = [
                    (next_x, next_z)
                    for next_x, next_z in (
                        (cell_x + 1, cell_z),
                        (cell_x - 1, cell_z),
                        (cell_x, cell_z + 1),
                        (cell_x, cell_z - 1),
                    )
                    if cell_value(next_x, next_z) == 0
                ]
                if not neighbors:
                    return
                next_x, next_z = maze_random.choice(neighbors)
                wall_x = cell_x + next_x + 1
                wall_z = cell_z + next_z + 1
                put_raw(
                    wall_x,
                    wall_z,
                    door_value if maze_random.random() <= 0.3 else 2,
                )
                visit(next_x, next_z)

        visit(0, 5)

        def write_maze_column(local_x, local_z, block):
            for dy in range(1, 4):
                _set_local(
                    structure, center, size,
                    local_x, floor_y + dy, local_z,
                    block, rotation,
                )
            _set_local(
                structure, center, size,
                local_x, floor_y + 4, local_z,
                ENCASED_TOWERWOOD, rotation,
            )

        for raw_x in range(raw_size):
            for raw_z in range(raw_size):
                value = raw[raw_x][raw_z]
                if value not in (0, door_value):
                    continue
                block = (
                    "tf_slice:reappearing_block"
                    if value == door_value else TOWERWOOD
                )
                base_x = (raw_x // 2) * 3
                base_z = (raw_z // 2) * 3
                if raw_x % 2 == 0 and raw_z % 2 == 0:
                    write_maze_column(base_x, base_z, block)
                elif raw_x % 2 == 0:
                    for offset in (1, 2):
                        write_maze_column(base_x, base_z + offset, block)
                elif raw_z % 2 == 0:
                    for offset in (1, 2):
                        write_maze_column(base_x + offset, base_z, block)

        # The source decorates every recursive-maze dead end with a cache.
        for cell_x in range(6):
            for cell_z in range(6):
                if cell_value(cell_x, cell_z) in (0, room_value, None):
                    continue
                openings = []
                for next_x, next_z in (
                    (cell_x + 1, cell_z),
                    (cell_x - 1, cell_z),
                    (cell_x, cell_z + 1),
                    (cell_x, cell_z - 1),
                ):
                    if not (0 <= next_x < 6 and 0 <= next_z < 6):
                        continue
                    wall_x = cell_x + next_x + 1
                    wall_z = cell_z + next_z + 1
                    if raw[wall_x][wall_z] != 0:
                        openings.append((next_x, next_z))
                if len(openings) != 1:
                    continue
                chest_x = cell_x * 3 + 1
                chest_z = cell_z * 3 + 1
                _set_local(
                    structure, center, size,
                    chest_x, floor_y + 1, chest_z,
                    ENCASED_TOWERWOOD, rotation,
                )
                position = _local(
                    center, size, chest_x, chest_z, rotation
                )
                set_loot_container(
                    structure, position[0], floor_y + 2,
                    position[1], "dark_tower_cache",
                )
                markers["lootChests"].append(
                    [position[0], floor_y + 2, position[1]]
                )
    elif room_type == "antibuilder_maze":
        for x in range(9, 18):
            for z in range(3, 18):
                if x % 2 == 1 and z % 2 == 1:
                    for dy in range(1, 5):
                        _set_local(
                            structure, center, size, x, floor_y + dy, z,
                            ENCASED_TOWERWOOD, rotation,
                        )
                elif x % 2 == 1 or z % 2 == 1:
                    for dy in range(1, 5):
                        _set_local(
                            structure, center, size, x, floor_y + dy, z,
                            "minecraft:oak_fence", rotation,
                        )
                    # Keep the source's irregular perforated lattice, but make
                    # each selected opening two blocks tall so it remains a
                    # real player passage in Bedrock collision.
                    if (x + z + floor_y) % 3 == 0:
                        for dy in (1, 2):
                            _set_local(
                                structure, center, size, x, floor_y + dy, z,
                                "minecraft:air", rotation,
                            )
        for x, block_y, z in (
            (15, floor_y + 2, 7),
            (11, floor_y + 3, 7),
            (15, floor_y + 2, 13),
            (11, floor_y + 3, 13),
            (5, floor_y + 3, 13),
        ):
            position = _local(center, size, x, z, rotation)
            _set_local(
                structure, center, size, x, block_y, z,
                "tf_slice:carminite_antibuilder", rotation,
            )
            markers["mechanisms"].append(
                {
                    "offset": [position[0], block_y, position[1]],
                    "block": "tf_slice:carminite_antibuilder",
                }
            )
    elif room_type == "aquarium":
        _pillar_frame(
            structure, center, size, 12, floor_y, 3, 4, 4, 13, rotation
        )
        _fill_local(
            structure, center, size, 13, floor_y + 4, 4,
            14, floor_y + 4, 14, "minecraft:water", rotation,
        )
        _pillar_frame(
            structure, center, size, 6, floor_y, 12, 4, 4, 4, rotation
        )
        _fill_local(
            structure, center, size, 6, floor_y + 5, 12,
            9, floor_y + 5, 15, ENCASED_TOWERWOOD, rotation,
        )
        _fill_local(
            structure, center, size, 7, floor_y + 4, 13,
            8, floor_y + 5, 14, "minecraft:water", rotation,
        )
    elif room_type == "botanical":
        _pillar_frame(
            structure, center, size, 12, floor_y, 12, 4, 4, 4, rotation
        )
        for y_offset in (1, 4):
            _fill_local(
                structure, center, size, 13, floor_y + y_offset, 13,
                14, floor_y + y_offset, 14, TOWERWOOD, rotation,
            )
        for x in (13, 14):
            for z in (13, 14):
                _set_local(
                    structure, center, size, x, floor_y + 2, z,
                    "minecraft:flower_pot", rotation,
                )

        for pillar_x in (12, 15):
            for dy in range(1, 5):
                _set_local(
                    structure, center, size, pillar_x, floor_y + dy, 4,
                    ENCASED_TOWERWOOD, rotation,
                )
        for x, direction in ((13, "east"), (14, "west")):
            _set_local(
                structure, center, size, x, floor_y + 1, 4,
                "minecraft:spruce_stairs", rotation,
                _stair_states(direction, True),
            )
        position = _local(center, size, 13, 4, rotation)
        set_loot_container(structure, position[0], floor_y + 2, position[1], "dark_tower_cache")
        markers["lootChests"].append([position[0], floor_y + 2, position[1]])
        _set_local(
            structure, center, size, 14, floor_y + 2, 4,
            "minecraft:crafting_table", rotation,
        )
        for bench_z in (7, 10):
            _set_local(
                structure, center, size, 12, floor_y + 1, bench_z,
                "minecraft:spruce_stairs", rotation,
                _stair_states("east", True),
            )
            for x in (13, 14):
                _set_local(
                    structure, center, size, x, floor_y + 1, bench_z,
                    "minecraft:spruce_slab", rotation,
                    {"top_slot_bit": True},
                )
            _set_local(
                structure, center, size, 15, floor_y + 1, bench_z,
                "minecraft:spruce_stairs", rotation,
                _stair_states("west", True),
            )
            for x in range(12, 16):
                _set_local(
                    structure, center, size, x, floor_y + 2, bench_z,
                    "minecraft:flower_pot", rotation,
                )

        _render_tree_planter(
            structure,
            tower_id,
            center,
            floor_y,
            rotation,
            grow_tree=pending_planters is None,
        )
        if pending_planters is not None:
            pending_planters.append(
                (tower_id, center, floor_y, rotation)
            )
    elif room_type == "netherwart":
        _pillar_frame(
            structure, center, size, 12, floor_y, 9, 4, 4, 7, rotation
        )
        _fill_local(
            structure, center, size, 13, floor_y + 1, 10,
            14, floor_y + 1, 14, "minecraft:soul_sand", rotation,
        )
        _fill_local(
            structure, center, size, 13, floor_y + 2, 10,
            14, floor_y + 2, 14, "minecraft:nether_wart", rotation,
        )
        _fill_local(
            structure, center, size, 13, floor_y + 4, 10,
            14, floor_y + 4, 14, "minecraft:soul_sand", rotation,
        )
        _pillar_frame(
            structure, center, size, 5, floor_y, 12, 3, 4, 3, rotation
        )
        _set_local(
            structure, center, size, 6, floor_y + 1, 13,
            TOWERWOOD, rotation,
        )
        _set_local(
            structure, center, size, 6, floor_y + 4, 13,
            TOWERWOOD, rotation,
        )
        spawner = _local(center, size, 6, 13, rotation)
        set_spawner(
            structure, spawner[0], floor_y + 3, spawner[1],
            "minecraft:blaze",
        )
        markers["structureSpawners"].append(
            {
                "offset": [spawner[0], floor_y + 3, spawner[1]],
                "entity": "minecraft:blaze",
            }
        )
    elif room_type == "lounge":
        # Brewing alcove walls and raised floor.
        _fill_local(
            structure, center, size, 17, floor_y + 1, 1, 17,
            floor_y + 4, 6, ENCASED_TOWERWOOD, rotation,
        )
        _fill_local(
            structure, center, size, 12, floor_y + 1, 1, 17,
            floor_y + 4, 1, ENCASED_TOWERWOOD, rotation,
        )
        _fill_local(
            structure, center, size, 13, floor_y + 1, 2, 16,
            floor_y + 1, 5, TOWERWOOD, rotation,
        )
        for z in range(2, 7):
            _set_local(
                structure, center, size, 12, floor_y + 1, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states("west"),
            )
        for x in range(12, 17):
            _set_local(
                structure, center, size, x, floor_y + 1, 6,
                "minecraft:spruce_stairs", rotation,
                _stair_states("south"),
            )
        for x, z, direction, dispenser_facing in (
            (13, 1, "south", 2),
            (15, 1, "south", 2),
            (17, 3, "west", 5),
            (17, 5, "west", 5),
        ):
            _set_local(
                structure, center, size, x, floor_y + 2, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states(direction, True),
            )
            _set_local(
                structure, center, size, x, floor_y + 3, z,
                "minecraft:dispenser", rotation,
                {"facing_direction": dispenser_facing},
            )
            _set_local(
                structure, center, size, x, floor_y + 4, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states(direction),
            )
        _set_local(
            structure, center, size, 13, floor_y + 2, 5,
            "minecraft:brewing_stand", rotation,
        )
        _set_local(
            structure, center, size, 15, floor_y + 2, 3,
            "minecraft:cauldron", rotation,
        )

        # Bookshelf corner, four-stair table and two chairs.
        for value in range(10, 18):
            for dy in range(1, 5):
                _set_local(
                    structure, center, size, value, floor_y + dy, 17,
                    TOWERWOOD, rotation,
                )
                _set_local(
                    structure, center, size, 17, floor_y + dy, value,
                    TOWERWOOD, rotation,
                )
        for start, end in ((11, 12), (14, 15)):
            for value in range(start, end + 1):
                for dy in range(1, 5):
                    _set_local(
                        structure, center, size, value, floor_y + dy, 17,
                        "minecraft:bookshelf", rotation,
                    )
                    _set_local(
                        structure, center, size, 17, floor_y + dy, value,
                        "minecraft:bookshelf", rotation,
                    )
        for x, z, direction in (
            (13, 14, "south"),
            (14, 14, "east"),
            (14, 13, "north"),
            (13, 13, "west"),
        ):
            _set_local(
                structure, center, size, x, floor_y + 1, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states(direction, True),
            )
        for x, z, direction in ((11, 13, "east"), (13, 11, "south")):
            _set_local(
                structure, center, size, x, floor_y + 1, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states(direction),
            )
        _set_local(
            structure, center, size, 8, floor_y + 3, 8,
            "minecraft:redstone_lamp", rotation,
        )
        _set_local(
            structure, center, size, 8, floor_y + 2, 8,
            "minecraft:lever", rotation,
            _lever_states("ceiling", "east_west"),
        )
        _render_tree_planter(
            structure,
            tower_id,
            center,
            floor_y,
            rotation,
            grow_tree=pending_planters is None,
        )
        if pending_planters is not None:
            pending_planters.append(
                (tower_id, center, floor_y, rotation)
            )
    elif room_type == "forge":
        for start, end in (
            ((17, floor_y + 1, 1), (17, floor_y + 4, 6)),
            ((12, floor_y + 1, 1), (17, floor_y + 4, 1)),
            ((12, floor_y + 1, 17), (17, floor_y + 4, 17)),
            ((17, floor_y + 1, 12), (17, floor_y + 4, 17)),
        ):
            _fill_local(
                structure, center, size,
                start[0], start[1], start[2], end[0], end[1], end[2],
                ENCASED_TOWERWOOD, rotation,
            )
        for min_x, min_z, max_x, max_z in ((13, 2, 16, 5), (13, 13, 16, 16)):
            _fill_local(
                structure, center, size, min_x, floor_y + 1, min_z,
                max_x, floor_y + 1, max_z, TOWERWOOD, rotation,
            )
        for z in range(2, 7):
            _set_local(
                structure, center, size, 12, floor_y + 1, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states("west"),
            )
        for x in range(12, 17):
            _set_local(
                structure, center, size, x, floor_y + 1, 6,
                "minecraft:spruce_stairs", rotation,
                _stair_states("south"),
            )
        for z in range(12, 17):
            _set_local(
                structure, center, size, 12, floor_y + 1, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states("west"),
            )
        for x in range(12, 17):
            _set_local(
                structure, center, size, x, floor_y + 1, 12,
                "minecraft:spruce_stairs", rotation,
                _stair_states("north"),
            )
        for x, z, direction, furnace_facing in (
            (13, 1, "south", 2), (15, 1, "south", 2),
            (17, 3, "west", 5), (17, 5, "west", 5),
            (13, 17, "north", 3), (15, 17, "north", 3),
            (17, 13, "west", 5), (17, 15, "west", 5),
        ):
            _set_local(
                structure, center, size, x, floor_y + 2, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states(direction, True),
            )
            _set_local(
                structure, center, size, x, floor_y + 3, z,
                "minecraft:furnace", rotation,
                {"facing_direction": furnace_facing},
            )
            _set_local(
                structure, center, size, x, floor_y + 4, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states(direction),
            )
        for x, z in ((13, 5), (13, 13)):
            _set_local(
                structure, center, size, x, floor_y + 2, z,
                "minecraft:anvil", rotation,
            )
        fire_x, fire_z = 6, 12
        for x, z, direction in (
            (fire_x - 1, fire_z, "west"),
            (fire_x + 1, fire_z, "east"),
            (fire_x, fire_z + 1, "south"),
            (fire_x, fire_z - 1, "north"),
        ):
            _set_local(
                structure, center, size, x, floor_y + 1, z,
                "minecraft:spruce_stairs", rotation,
                _stair_states(direction),
            )
        for dx, dz in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            _set_local(
                structure, center, size, fire_x + dx, floor_y + 1,
                fire_z + dz, ENCASED_TOWERWOOD, rotation,
            )
        _set_local(
            structure, center, size, fire_x, floor_y + 1, fire_z,
            "minecraft:netherrack", rotation,
        )
        _set_local(
            structure, center, size, fire_x, floor_y + 2, fire_z,
            "minecraft:fire", rotation,
        )


def _decorate_high_room(structure, markers, api, tower_id, room_type, center, bottom, top, rotation):
    _record_room(markers, tower_id, room_type, center, bottom, 19)
    if room_type == "timber_maze":
        floorside = 0
        for floor_index, y in enumerate(range(bottom, top, 5)):
            floorside = (floorside + 1) % 4
            for x in (4, 9, 14):
                for z in range(1, 18):
                    _set_local(
                        structure,
                        center,
                        19,
                        x,
                        y,
                        z,
                        "tf_slice:twilight_oak_log",
                        floorside,
                    )
            # The source adds two short cross beams between the three long
            # beams.  Stable coordinate picks retain its lattice silhouette
            # without relying on Python RNG implementation details.
            cross_z_1 = (6, 11, 7, 12)[floor_index % 4]
            cross_z_2 = (12, 7, 11, 6)[floor_index % 4]
            for x in range(5, 9):
                _set_local(
                    structure, center, 19, x, y, cross_z_1,
                    "tf_slice:twilight_oak_log", floorside,
                )
            for x in range(10, 14):
                _set_local(
                    structure, center, 19, x, y, cross_z_2,
                    "tf_slice:twilight_oak_log", floorside,
                )
            post_z = (
                (4, 9, 14),
                (9, 14, 4),
                (14, 4, 9),
            )[floor_index % 3]
            for dy in range(1, 5):
                for post_x, post_position_z in zip((4, 9, 14), post_z):
                    _set_local(
                        structure, center, 19, post_x, y - dy,
                        post_position_z, "tf_slice:twilight_oak_log",
                        floorside,
                    )
                    _set_local(
                        structure, center, 19, 5, y - dy, post_z[0],
                        "minecraft:ladder", floorside,
                        _ladder_states(4),
                )
                    _set_local(
                        structure, center, 19, 13, y - dy, post_z[2],
                        "minecraft:ladder", floorside,
                        _ladder_states(5),
                )
            if y == bottom:
                # checkPost() in the Java component only keeps bottom posts
                # which meet the last lower floor.  Give the retained posts a
                # definite foot so no ladder/log column hangs in mid-air.
                for post_x, post_position_z in zip((4, 9, 14), post_z):
                    _set_local(
                        structure, center, 19, post_x, y - 5,
                        post_position_z, ENCASED_TOWERWOOD, floorside,
                    )
            is_top = y >= top - 5
            if is_top:
                top_rotation = (top + 1) % 4
                for dy in range(1, 5):
                    _set_local(
                        structure, center, 19, 4, y + dy, 9,
                        "tf_slice:twilight_oak_log", top_rotation,
                    )
                    _set_local(
                        structure, center, 19, 4, y + dy, 10,
                        "minecraft:ladder", top_rotation,
                        _ladder_states(2),
                    )
                # The source's three-quarter floor leaves this ascender in an
                # open quadrant.  Our static floor/railing compilation can
                # occupy that cell, so materialize the complete landing just
                # as the builder-room top ascender does: an open ladder shaft,
                # a solid source-side step, two blocks of headroom, and guard
                # rails only beside the opening.
                for clear_y, clear_z in (
                    (top, 10),
                    (top + 1, 10),
                    (top + 2, 10),
                    (top + 1, 9),
                    (top + 2, 9),
                ):
                    _set_local(
                        structure,
                        center,
                        19,
                        4,
                        clear_y,
                        clear_z,
                        "minecraft:air",
                        top_rotation,
                    )
                _set_local(
                    structure,
                    center,
                    19,
                    4,
                    top,
                    9,
                    ENCASED_TOWERWOOD,
                    top_rotation,
                )
                for fence_x in (3, 5):
                    for fence_y in (top, top + 1):
                        _set_local(
                            structure,
                            center,
                            19,
                            fence_x,
                            fence_y,
                            10,
                            "minecraft:oak_fence",
                            top_rotation,
                        )
            elif y != bottom:
                pos = _local(center, 19, 11, 11, rotation)
                api["set_spawner"](structure, pos[0], y + 2, pos[1], "tf_slice:mini_ghast")
                markers["structureSpawners"].append({"offset": [pos[0], y + 2, pos[1]], "entity": "tf_slice:mini_ghast"})
    else:
        # Source builder rooms are a vertical sequence of paired 2x3 launch
        # pads. Their builders project the temporary path selected by the
        # nearest player's look direction; ladders only join adjacent pads.
        def builder_platform(platform_y, platform_z, platform_rotation, hole):
            for local_x in (1, 2):
                for local_z in range(platform_z - 1, platform_z + 2):
                    if hole and local_x == 1 and local_z == platform_z:
                        continue
                    _set_local(
                        structure, center, 19,
                        local_x, platform_y, local_z,
                        ENCASED_TOWERWOOD, platform_rotation,
                    )
            builder_z = platform_z + 1 if hole else platform_z - 1
            _set_local(
                structure, center, 19, 2, platform_y, builder_z,
                "tf_slice:carminite_builder", platform_rotation,
            )
            position = _local(
                center, 19, 2, builder_z, platform_rotation
            )
            markers["mechanisms"].append(
                {
                    "offset": [position[0], platform_y, position[1]],
                    "block": "tf_slice:carminite_builder",
                }
            )
            _set_local(
                structure, center, 19, 2, platform_y + 1, platform_z,
                "minecraft:lever", platform_rotation,
                _lever_states("floor", "east_west"),
            )

        for bottom_rotation in (1, 3):
            builder_platform(bottom, 5, bottom_rotation, True)
            for ladder_y in range(bottom - 4, bottom):
                _set_local(
                    structure, center, 19, 1, ladder_y, 5,
                    "minecraft:ladder", bottom_rotation,
                    _ladder_states(4),
                )

        for index, platform_y in enumerate(range(bottom, top - 5, 5)):
            platform_rotation = index % 4
            platform_z = 7 + ((bottom + index * 3) % 5)
            builder_platform(
                platform_y, platform_z, platform_rotation, False
            )
            for ladder_y in range(platform_y + 1, platform_y + 5):
                _set_local(
                    structure, center, 19, 1, ladder_y, platform_z,
                    "minecraft:ladder", platform_rotation,
                    _ladder_states(4),
                )
            builder_platform(
                platform_y + 5, platform_z, platform_rotation, True
            )

            if platform_y % 2:
                anti_x = (5, 9, 13)[index % 3]
                anti_z = 13 if anti_x == 9 and index % 2 else 9
                _set_local(
                    structure, center, 19, anti_x, platform_y + 2,
                    anti_z, "tf_slice:carminite_antibuilder",
                    platform_rotation,
                )
                position = _local(
                    center, 19, anti_x, anti_z, platform_rotation
                )
                markers["mechanisms"].append(
                    {
                        "offset": [
                            position[0], platform_y + 2, position[1]
                        ],
                        "block": "tf_slice:carminite_antibuilder",
                    }
                )
            else:
                lamp_x = 5 if index % 2 == 0 else 13
                lamp_z = 13 if index % 3 else 5
                for dx, dy, dz in (
                    (0, 0, 0), (1, 0, 0), (-1, 0, 0),
                    (0, 1, 0), (0, 0, 1),
                ):
                    _set_local(
                        structure, center, 19,
                        lamp_x + dx, platform_y + 2 + dy, lamp_z + dz,
                        "minecraft:redstone_lamp", platform_rotation,
                    )
                _set_local(
                    structure, center, 19, lamp_x, platform_y + 1,
                    lamp_z, "minecraft:lever", platform_rotation,
                    _lever_states("ceiling", "north_south"),
                )

        top_rotation = (top + 1) % 4
        _fill_local(
            structure, center, 19, 5, top - 5, 9,
            7, top - 5, 11, ENCASED_TOWERWOOD, top_rotation,
        )
        for support_y in range(top - 5, top + 1):
            _set_local(
                structure, center, 19, 6, support_y, 9,
                ENCASED_TOWERWOOD, top_rotation,
            )
        for ladder_y in range(top - 4, top):
            _set_local(
                structure, center, 19, 6, ladder_y, 10,
                "minecraft:ladder", top_rotation,
                _ladder_states(2),
            )
        # addTopBuilderPlatform exits over the backing block at local z=9.
        # Keep the ladder cell itself open at floor height and preserve two
        # blocks of headroom over the source-side step.
        for clear_y, clear_z in (
            (top, 10),
            (top + 1, 10),
            (top + 2, 10),
            (top + 1, 9),
            (top + 2, 9),
        ):
            _set_local(
                structure, center, 19, 6, clear_y, clear_z,
                "minecraft:air", top_rotation,
            )
        for fence_x in (5, 7):
            for fence_y in (top, top + 1):
                _set_local(
                    structure, center, 19,
                    fence_x, fence_y, 10,
                    "minecraft:oak_fence", top_rotation,
                )
        _set_local(
            structure, center, 19, 7, top - 5, 10,
            "tf_slice:carminite_builder", top_rotation,
        )
        position = _local(center, 19, 7, 10, top_rotation)
        markers["mechanisms"].append(
            {
                "offset": [position[0], top - 5, position[1]],
                "block": "tf_slice:carminite_builder",
            }
        )
        _set_local(
            structure, center, 19, 7, top - 4, 11,
            "minecraft:lever", top_rotation,
            _lever_states("floor", "east_west"),
        )


def _decorate_reactor_room(structure, markers, tower_id, center, y, rotation):
    _record_room(markers, tower_id, "reactor_experiment", center, y, 19)

    # DarkTowerMainComponent.decorateExperiment: retain the complete crafting
    # alcove instead of leaving the reactor assembly alone in an empty room.
    _fill_local(
        structure, center, 19, 17, y + 1, 1,
        17, y + 4, 6, ENCASED_TOWERWOOD, rotation,
    )
    _fill_local(
        structure, center, 19, 12, y + 1, 1,
        17, y + 4, 1, ENCASED_TOWERWOOD, rotation,
    )
    _fill_local(
        structure, center, 19, 13, y + 1, 2,
        16, y + 1, 5, TOWERWOOD, rotation,
    )
    for z in range(2, 7):
        _set_local(
            structure, center, 19, 12, y + 1, z,
            "minecraft:spruce_stairs", rotation,
            _stair_states("west"),
        )
    for x in range(12, 17):
        _set_local(
            structure, center, 19, x, y + 1, 6,
            "minecraft:spruce_stairs", rotation,
            _stair_states("south"),
        )
    for x, z in ((13, 1), (15, 1), (17, 3), (17, 5)):
        for dy in range(2, 5):
            _set_local(
                structure, center, 19, x, y + dy, z,
                "tf_slice:twilight_oak_log", rotation,
            )
    _set_local(
        structure, center, 19, 12, y + 1, 1,
        ENCASED_TOWERWOOD, rotation,
    )
    _set_local(
        structure, center, 19, 17, y + 1, 6,
        ENCASED_TOWERWOOD, rotation,
    )
    _set_local(
        structure, center, 19, 14, y + 2, 4,
        "minecraft:crafting_table", rotation,
    )

    # Source recipe walls: nine frames face south from the north alcove and
    # nine face west from its east wall.  The previous port omitted every
    # frame, leaving the workshop as an unexplained machine skeleton.
    south_recipe = (
        ("tf_slice:borer_essence", "minecraft:redstone", "tf_slice:borer_essence"),
        ("minecraft:redstone", "minecraft:ghast_tear", "minecraft:redstone"),
        ("tf_slice:borer_essence", "minecraft:redstone", "tf_slice:borer_essence"),
    )
    for row, items in enumerate(south_recipe):
        for column, item_name in enumerate(items):
            _set_item_frame_local(
                structure,
                center,
                19,
                13 + column,
                y + 2 + row,
                2,
                item_name,
                3,
                rotation,
            )
    west_recipe = (
        ("tf_slice:encased_towerwood", "tf_slice:towerwood", "tf_slice:encased_towerwood"),
        ("tf_slice:towerwood", "tf_slice:carminite", "tf_slice:towerwood"),
        ("tf_slice:encased_towerwood", "tf_slice:towerwood", "tf_slice:encased_towerwood"),
    )
    for row, items in enumerate(west_recipe):
        for column, item_name in enumerate(items):
            _set_item_frame_local(
                structure,
                center,
                19,
                16,
                y + 2 + row,
                3 + column,
                item_name,
                4,
                rotation,
            )

    # Reactor cage: lower and upper redstone cores, netherrack middle braces,
    # and the inactive carminite reactor at the center.
    for x, z in ((13, 13), (15, 13), (13, 15), (15, 15)):
        _set_local(structure, center, 19, x, y + 1, z, "minecraft:obsidian", rotation)
        _set_local(structure, center, 19, x, y + 2, z, "minecraft:netherrack", rotation)
        _set_local(structure, center, 19, x, y + 3, z, "minecraft:obsidian", rotation)
    for x, z in ((13, 14), (14, 13), (15, 14), (14, 15)):
        _set_local(structure, center, 19, x, y + 1, z, "minecraft:netherrack", rotation)
        _set_local(structure, center, 19, x, y + 3, z, "minecraft:netherrack", rotation)
    _set_local(structure, center, 19, 14, y + 1, 14, "minecraft:redstone_block", rotation)
    _set_local(structure, center, 19, 14, y + 2, 14, "tf_slice:carminite_reactor", rotation)
    _set_local(structure, center, 19, 14, y + 3, 14, "minecraft:redstone_block", rotation)
    reactor = _local(center, 19, 14, 14, rotation)
    markers["mechanisms"].append(
        {
            "offset": [reactor[0], y + 2, reactor[1]],
            "block": "tf_slice:carminite_reactor",
        }
    )

    # Two short and two long piston plungers are the room's visible controls.
    for x, z, support_x, support_z, piston_facing in (
        (14, 17, 13, 17, 3),
        (17, 14, 17, 13, 5),
    ):
        _set_local(
            structure, center, 19, x, y + 1, z,
            ENCASED_TOWERWOOD, rotation,
        )
        _set_local(
            structure, center, 19, support_x, y + 1, support_z,
            "minecraft:lever", rotation,
            _lever_states("wall", "east" if x == 14 else "south"),
        )
        _set_local(
            structure, center, 19, x, y + 2, z,
            "minecraft:piston", rotation,
            {"facing_direction": piston_facing},
        )
    for x, z in ((14, 16), (16, 14), (14, 11), (11, 14)):
        _set_local(
            structure, center, 19, x, y + 2, z,
            "minecraft:redstone_block", rotation,
        )
    for piston_x, piston_z, accent_x, accent_z, lever_x, lever_z, piston, facing, lever_direction in (
        (14, 10, 14, 11, 13, 11, "minecraft:piston", 2, "east"),
        (14, 9, 14, 9, 13, 9, "minecraft:sticky_piston", 2, "east"),
        (10, 14, 11, 14, 11, 13, "minecraft:piston", 4, "south"),
        (9, 14, 9, 14, 9, 13, "minecraft:sticky_piston", 4, "south"),
    ):
        _set_local(
            structure, center, 19, accent_x, y + 1, accent_z,
            ENCASED_TOWERWOOD, rotation,
        )
        _set_local(
            structure, center, 19, lever_x, y + 1, lever_z,
            "minecraft:lever", rotation,
            _lever_states("wall", lever_direction),
        )
        _set_local(
            structure, center, 19, piston_x, y + 2, piston_z,
            piston, rotation,
            {"facing_direction": facing},
        )


def _render_main_tower(
    structure,
    markers,
    api,
    tower,
    room_cursor,
    layout_seed,
    decoration_seed,
):
    center = tuple(tower["center"])
    bottom_y = tower["bottomY"]
    height = tower["height"]
    top_y = _render_encased_shell(
        structure,
        center,
        19,
        bottom_y,
        height,
        layout_seed * 17 + tower["stage"],
    )
    if tower["stage"] == 0:
        # DarkTowerMainComponent places a complete accent layer at local y=-1
        # for the first main component.  Besides matching the source, this
        # closes one-block terrain undulations beneath the surface foundation.
        minimum_x, minimum_z, maximum_x, maximum_z = _bounds(center, 19)
        _fill(
            structure,
            (minimum_x, bottom_y - 1, minimum_z),
            (maximum_x, bottom_y - 1, maximum_z),
            ENCASED_TOWERWOOD,
        )
    else:
        # Every recursive main component after the ground tower calls
        # makeABeard().  Without it the upper stages are visibly suspended.
        _render_beard(structure, center, 19, bottom_y)
    beam_maze = (decoration_seed + tower["stage"]) % 2 == 0
    total_floors = height // 5
    center_floors = 4 if beam_maze else total_floors // 2
    bottom_floors = (total_floors - center_floors) // 2
    center_bottom = bottom_y + bottom_floors * 5
    top_floors_start = bottom_y + height - (bottom_floors * 5 + 1)
    lower_floors = list(range(bottom_y + 5, center_bottom, 5))
    upper_floors = list(range(top_floors_start, top_y, 5))
    pending_planters = []
    markers["mainFloorZones"].append(
        {
            "tower": tower["id"],
            "type": "timber_maze" if beam_maze else "builder_platforms",
            "lowerFloors": list(lower_floors),
            "centerBottom": center_bottom,
            "topFloorsStart": top_floors_start,
            "upperFloors": list(upper_floors),
        }
    )

    # addThreeQuarterFloors(bottom=0) first creates the initial staircase,
    # rotates counter-clockwise, and only then starts its first floor at y=5.
    base_rotation = bottom_y % 4
    _render_large_stairs_up(structure, center, bottom_y, base_rotation)
    local_rotation = (base_rotation - 1) % 4
    _decorate_main_room(
        structure,
        markers,
        api,
        tower["id"],
        "bottom_entrance",
        center,
        bottom_y,
        local_rotation,
        pending_planters=pending_planters,
    )

    decorated_count = 1
    room_rng = random.Random(
        (int(decoration_seed) + 1) * 341873128712
        + int(tower["stage"]) * 132897987541
        + int(room_cursor) * 31
    )
    for index, floor_y in enumerate(lower_floors):
        is_zone_top = index == len(lower_floors) - 1
        _render_three_quarter_floor(
            structure,
            center,
            floor_y,
            local_rotation,
            include_stairs=not is_zone_top,
        )
        if not is_zone_top:
            is_bottom_room = index == 0
            room_type = _select_main_room_type(
                room_rng.randrange(4 if is_bottom_room else 8),
                floor_y,
                is_bottom=is_bottom_room,
            )
            _decorate_main_room(
                structure, markers, api, tower["id"], room_type,
                center, floor_y, local_rotation,
                pending_planters=pending_planters,
            )
            decorated_count += 1
        local_rotation = (local_rotation - 1) % 4

    local_rotation = top_floors_start % 4
    for index, floor_y in enumerate(upper_floors):
        is_zone_top = index == len(upper_floors) - 1
        _render_three_quarter_floor(
            structure,
            center,
            floor_y,
            local_rotation,
            is_bottom=index == 0,
            is_top=is_zone_top,
            include_stairs=not is_zone_top,
        )
        if tower["stage"] == 2:
            # addThreeQuarterFloorsDecorateBoss reserves every non-top upper
            # floor for a reactor experiment.  Generic decoration here used to
            # overwrite the experiment and record two rooms at the same Y.
            if not is_zone_top:
                _decorate_reactor_room(
                    structure, markers, tower["id"], center,
                    floor_y, local_rotation,
                )
                decorated_count += 1
        else:
            room_type = _select_main_room_type(
                room_rng.randrange(3 if is_zone_top else 8),
                floor_y,
                is_top=is_zone_top,
            )
            _decorate_main_room(
                structure, markers, api, tower["id"], room_type,
                center, floor_y, local_rotation,
                pending_planters=pending_planters,
            )
            decorated_count += 1
        local_rotation = (local_rotation - 1) % 4

    # DarkTowerMainComponent authors both ordinary floor zones first and only
    # then adds the central timber maze or builder platforms.  Reversing this
    # order lets the first upper room overwrite the top ladder exit with a
    # full towerwood wall.
    high_room = "timber_maze" if beam_maze else "builder_platforms"
    _decorate_high_room(
        structure, markers, api, tower["id"], high_room, center,
        center_bottom, top_floors_start, 0,
    )
    # Grow after every floor and the central high room have claimed their
    # solid cells.  This matches the source feature's collision semantics:
    # trees rise through an authored three-quarter-floor opening, while a
    # blocked planter stays empty instead of leaving a cut trunk or floating
    # canopy above a later overlay.
    for planter in pending_planters:
        _grow_tree_planter(structure, *planter)
    return top_y, room_cursor + decorated_count


def _render_small_floor(
    structure,
    center,
    size,
    y,
    rotation,
    full_floor=False,
    include_stairs=True,
):
    half = size // 2
    start_x = 1 if full_floor else half
    for x in range(start_x, size - 1):
        for z in range(1, size - 1):
            _set_local(structure, center, size, x, y, z, TOWERWOOD, rotation)
    if not full_floor:
        for z in range(1, size - 1):
            _set_local(
                structure, center, size, half - 1, y, z,
                ENCASED_TOWERWOOD, rotation,
            )
    else:
        for z in range(1, size - 1):
            _set_local(
                structure, center, size, half, y, z,
                ENCASED_TOWERWOOD, rotation,
            )

    if include_stairs:
        _render_small_stairs_down(structure, center, size, y, rotation)


def _render_small_stairs_down(structure, center, size, y, rotation):
    """Port DarkTowerWingComponent.addStairsDown after room decoration."""

    lane_positions = [size - 2]
    if size > 9:
        lane_positions.append(size - 3)
    for lane_z in lane_positions:
        for step in range(4):
            x = size - 3 - step
            stair_y = y - step
            _set_local(
                structure, center, size, x, stair_y, lane_z,
                "minecraft:spruce_stairs", rotation,
                _stair_states("west"),
            )
            _set_local(
                structure, center, size, x, stair_y - 1, lane_z,
                ENCASED_TOWERWOOD, rotation,
            )
            for clear_x, clear_y in (
                (x, stair_y + 1),
                (x, stair_y + 2),
                (x - 1, stair_y + 2),
                (x, stair_y + 3),
                (x - 1, stair_y + 3),
            ):
                _set_local(
                    structure, center, size, clear_x, clear_y, lane_z,
                    "minecraft:air", rotation,
                )


def _decorate_small_room(structure, markers, api, tower, room_type, y, rotation):
    center = tuple(tower["center"])
    size = tower["size"]
    _record_room(markers, tower["id"], room_type, center, y, size)
    if room_type == "reappearing_floor":
        for x in range(4, 8):
            for z in range(3, 6):
                _set_local(
                    structure, center, size, x, y, z,
                    "tf_slice:reappearing_block", rotation,
                )
        for x in range(4, 8):
            for z in (2, 6):
                _set_local(
                    structure, center, size, x, y + 1, z,
                    "minecraft:wooden_pressure_plate", rotation,
                )
    elif room_type == "spawner":
        frame_x = 4 if size > 9 else 3
        frame_z = 5 if size > 9 else 4
        _pillar_frame(
            structure, center, size,
            frame_x, y, frame_z, 3, 3, 3, rotation,
        )
        pos = _local(
            center, size, frame_x + 1, frame_z + 1, rotation
        )
        entity = (
            "tf_slice:carminite_golem"
            if size > 9 and (y + rotation) % 2 == 0
            else "tf_slice:tower_broodling"
        )
        api["set_spawner"](
            structure, pos[0], y + 2, pos[1], entity
        )
        markers["structureSpawners"].append(
            {"offset": [pos[0], y + 2, pos[1]], "entity": entity}
        )
    elif room_type == "lounge":
        couch_x = 9 if size > 9 else 7
        couch_z = 4 if size > 9 else 3
        for dz, direction in ((0, "south"), (1, "west"), (2, "north")):
            _set_local(
                structure, center, size, couch_x, y + 1, couch_z + dz,
                "minecraft:spruce_stairs", rotation,
                _stair_states(direction),
            )
        table_x = 5 if size > 9 else 3
        _set_local(
            structure, center, size, table_x, y + 1, couch_z,
            "minecraft:spruce_stairs", rotation,
            _stair_states("south", True),
        )
        _set_local(
            structure, center, size, table_x, y + 1, couch_z + 1,
            "minecraft:spruce_slab", rotation, {"top_slot_bit": True},
        )
        _set_local(
            structure, center, size, table_x, y + 1, couch_z + 2,
            "minecraft:spruce_stairs", rotation,
            _stair_states("north", True),
        )
    elif room_type == "library":
        for shelf_x in ((4, 9) if size > 9 else (3, 7)):
            shelf_z = 3 if size > 9 else 2
            _set_local(
                structure, center, size, shelf_x, y + 1, shelf_z,
                "minecraft:spruce_stairs", rotation,
                _stair_states("north"),
            )
            _set_local(
                structure, center, size, shelf_x, y + 2, shelf_z,
                "minecraft:spruce_stairs", rotation,
                _stair_states("north", True),
            )
            _set_local(
                structure, center, size, shelf_x, y + 1, shelf_z + 3,
                "minecraft:spruce_stairs", rotation,
                _stair_states("south"),
            )
            _set_local(
                structure, center, size, shelf_x, y + 2, shelf_z + 3,
                "minecraft:spruce_stairs", rotation,
                _stair_states("south", True),
            )
            for dz in (1, 2):
                for dy in (1, 2):
                    _set_local(
                        structure, center, size, shelf_x, y + dy,
                        shelf_z + dz, "minecraft:bookshelf", rotation,
                    )
    elif room_type == "piston_pulser":
        cx = 6 if size > 9 else 5
        cz = 4 if size > 9 else 3
        _set_local(
            structure, center, size, cx, y + 1, cz + 1,
            "minecraft:sticky_piston", rotation, {"facing_direction": 3},
        )
        _set_local(
            structure, center, size, cx, y + 1, cz,
            ENCASED_TOWERWOOD, rotation,
        )
        for x, z in ((cx + 1, cz), (cx - 2, cz), (cx - 2, cz + 1), (cx - 1, cz + 1)):
            _set_local(
                structure, center, size, x, y + 1, z,
                "minecraft:redstone_wire", rotation,
            )
        _set_local(
            structure, center, size, cx + 2, y + 1, cz,
            "minecraft:wooden_pressure_plate", rotation,
        )
        _set_local(
            structure, center, size, cx - 1, y + 1, cz,
            "minecraft:unpowered_repeater", rotation, {"direction": 1},
        )
    elif room_type == "lamp_experiment":
        cx = 5 if size > 9 else 3
        cz = 5 if size > 9 else 4
        _set_local(
            structure, center, size, cx, y + 1, cz,
            "minecraft:sticky_piston", rotation, {"facing_direction": 1},
        )
        _set_local(
            structure, center, size, cx, y + 2, cz,
            "minecraft:redstone_lamp", rotation,
        )
        _set_local(
            structure, center, size, cx, y + 1, cz + 1,
            ENCASED_TOWERWOOD, rotation,
        )
        _set_local(
            structure, center, size, cx, y + 1, cz + 2,
            "minecraft:lever", rotation,
            _lever_states("wall", "north"),
        )
        _set_local(
            structure, center, size, cx, y + 3, cz - 1,
            ENCASED_TOWERWOOD, rotation,
        )
        _set_local(
            structure, center, size, cx, y + 3, cz - 2,
            "minecraft:lever", rotation,
            _lever_states("wall", "south"),
        )
    elif room_type == "puzzle_chest":
        x = 4 if size > 9 else 3
        z = 5 if size > 9 else 4
        _pillar_frame(structure, center, size, x, y, z, 3, 3, 3, rotation)
        for dx, dz in ((1, 0), (0, 1), (2, 1), (1, 2)):
            _set_local(
                structure, center, size, x + dx, y + 1, z + dz,
                TOWERWOOD, rotation,
            )
        for dx, dz in ((0, 1), (2, 1), (1, 2), (1, 1)):
            _set_local(
                structure, center, size, x + dx, y + 3, z + dz,
                TOWERWOOD, rotation,
            )
        _set_local(
            structure, center, size, x + 1, y + 3, z - 1,
            "minecraft:sticky_piston", rotation, {"facing_direction": 2},
        )
        _set_local(
            structure, center, size, x + 1, y + 3, z - 2,
            ENCASED_TOWERWOOD, rotation,
        )
        _set_local(
            structure, center, size, x + 2, y + 3, z - 2,
            "minecraft:lever", rotation,
            _lever_states("wall", "west"),
        )
        pos = _local(center, size, x + 1, z + 1, rotation)
        api["set_loot_container"](
            structure, pos[0], y + 2, pos[1], "dark_tower_cache"
        )
        markers["lootChests"].append([pos[0], y + 2, pos[1]])


def _render_roof(structure, markers, tower, roof_type):
    center = tuple(tower["center"])
    size = int(tower["size"])
    roof_y = int(tower["bottomY"]) + int(tower["height"])
    minimum_x, minimum_z, maximum_x, maximum_z = _bounds(center, size)
    for x in range(minimum_x, maximum_x + 1):
        for z in range(minimum_z, maximum_z + 1):
            if x in (minimum_x, maximum_x) or z in (minimum_z, maximum_z):
                structure.set(x, roof_y, z, "minecraft:oak_fence")
    if roof_type == "antenna":
        for y in range(roof_y, roof_y + 8):
            structure.set(center[0], y, center[1], ENCASED_TOWERWOOD)
    elif roof_type == "cactus":
        for y in range(roof_y, roof_y + 6):
            structure.set(center[0], y, center[1], ENCASED_TOWERWOOD)
        for dx, dz in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            structure.set(center[0] + dx, roof_y + 3, center[1] + dz, ENCASED_TOWERWOOD)
    elif roof_type == "rings":
        for radius, y in ((2, roof_y + 3), (4, roof_y + 5)):
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if max(abs(dx), abs(dz)) == radius:
                        structure.set(center[0] + dx, y, center[1] + dz, ENCASED_TOWERWOOD)
    else:
        radius = size // 2 - 1
        for dx, dz in ((radius, radius), (-radius, radius), (radius, -radius), (-radius, -radius)):
            for y in range(roof_y, roof_y + 6):
                structure.set(center[0] + dx, y, center[1] + dz, ENCASED_TOWERWOOD)
    markers["roofs"].append(
        {"tower": tower["id"], "type": roof_type, "offset": [center[0], roof_y, center[1]]}
    )


def _render_side_tower(structure, markers, api, tower, roof_type, room_seed):
    center = tuple(tower["center"])
    top_y = _render_encased_shell(
        structure,
        center,
        tower["size"],
        tower["bottomY"],
        tower["height"],
        room_seed,
    )
    if tower["bottomY"] > 20:
        _render_beard(structure, center, tower["size"], tower["bottomY"])
    levels = list(range(tower["bottomY"] + 4, top_y, 4))
    if tower["size"] == 9 and room_seed % 3 == 0:
        rotation = 0
        for index, y in enumerate(levels):
            rotation = (rotation + 1) % 4
            is_top = index == len(levels) - 1
            if is_top and tower.get("keyTower"):
                # Source small-timber key towers close with a mostly solid log
                # floor, two ladder holes and the normal framed key cache.
                for x in range(1, tower["size"] - 1):
                    for z in range(1, tower["size"] - 1):
                        _set_local(
                            structure, center, tower["size"], x, y, z,
                            "tf_slice:twilight_oak_log", rotation,
                        )
                for x, z in ((3, 2), (5, 6)):
                    _set_local(
                        structure, center, tower["size"], x, y, z,
                        "minecraft:air", rotation,
                    )
                _record_room(
                    markers, tower["id"], "key_treasure",
                    center, y, tower["size"],
                )
                pos = _local(
                    center, tower["size"],
                    tower["size"] // 2, tower["size"] // 2, rotation,
                )
                api["set_loot_container"](
                    structure, pos[0], y + 2, pos[1], "dark_tower_key"
                )
                key_marker = {
                    "tower": tower["id"],
                    "stage": tower["stage"],
                    "offset": [pos[0], y + 2, pos[1]],
                }
                markers["keyChests"].append(list(key_marker["offset"]))
                markers["keyTowers"].append(key_marker)
                continue

            _record_room(
                markers, tower["id"], "small_timber_beams",
                center, y, tower["size"],
            )
            for z in range(1, tower["size"] - 1):
                for x in (2, 6):
                    _set_local(
                        structure, center, tower["size"], x, y, z,
                        "tf_slice:twilight_oak_log", rotation,
                    )
            cross_z = 3 + (room_seed + index) % 3
            for x in range(3, 6):
                _set_local(
                    structure, center, tower["size"], x, y, cross_z,
                    "tf_slice:twilight_oak_log", rotation,
                )
            for post_x, post_z, ladder_facing in (
                (2, 2 if index % 2 == 0 else 6, 4),
                (6, 6 if index % 2 == 0 else 2, 5),
            ):
                for dy in range(1, 4):
                    _set_local(
                        structure, center, tower["size"],
                        post_x, y - dy, post_z,
                        "tf_slice:twilight_oak_log", rotation,
                    )
                    _set_local(
                        structure, center, tower["size"],
                        post_x + (1 if post_x == 2 else -1),
                        y - dy, post_z, "minecraft:ladder", rotation,
                        _ladder_states(ladder_facing),
                    )
        _render_roof(structure, markers, tower, roof_type)
        return

    rotation = (tower["bottomY"] + 4) % 3
    for index, y in enumerate(levels):
        # addHalfFloors rotates before each floor, decorates it, and only then
        # writes the descending stairs/air column.  The order is significant:
        # room furniture must never be able to refill stair headroom.
        rotation = (rotation + 2) % 4
        _render_small_floor(
            structure,
            center,
            tower["size"],
            y,
            rotation,
            full_floor=index == len(levels) - 1,
            include_stairs=False,
        )
        if tower.get("keyTower") and index == len(levels) - 1:
            room_type = "key_treasure"
            _record_room(markers, tower["id"], room_type, center, y, tower["size"])
            pos = _local(center, tower["size"], tower["size"] // 2, tower["size"] // 2, rotation)
            api["set_loot_container"](structure, pos[0], y + 1, pos[1], "dark_tower_key")
            key_marker = {
                "tower": tower["id"],
                "stage": tower["stage"],
                "offset": [pos[0], y + 1, pos[1]],
            }
            markers["keyChests"].append(list(key_marker["offset"]))
            markers["keyTowers"].append(key_marker)
        else:
            room_type = SMALL_ROOM_TYPES[(room_seed + index) % len(SMALL_ROOM_TYPES)]
            if tower["size"] > 9 and room_type == "reappearing_floor":
                # The source falls through to the spawner case: a 4x3
                # pressure-plate bridge is only suitable for size-nine wings.
                room_type = "spawner"
            _decorate_small_room(
                structure, markers, api, tower, room_type, y, rotation
            )
        _render_small_stairs_down(
            structure, center, tower["size"], y, rotation
        )
    # Source adds one more 180-degree flight from the last full landing to the
    # roof.  This is separate from the per-floor loop.
    rotation = (rotation + 2) % 4
    _render_small_stairs_down(
        structure, center, tower["size"], top_y, rotation
    )
    _render_roof(structure, markers, tower, roof_type)


def _render_boss_trap_trigger(structure, markers, tower, rotation, record_marker):
    center = tuple(tower["center"])
    size = int(tower["size"])
    bottom = int(tower["bottomY"])
    trap_x, trap_z = _local(center, size, 5, 5, rotation)
    trap_position = (trap_x, bottom + 1, trap_z)
    structure.set(
        trap_position[0], trap_position[1], trap_position[2],
        "tf_slice:ghast_trap", {"tf_slice:active": False},
    )
    for local_x, local_z in ((5, 6), (5, 7), (5, 8), (4, 8), (3, 8)):
        x, z = _local(center, size, local_x, local_z, rotation)
        structure.set(x, bottom + 1, z, "minecraft:redstone_wire")
    plate_x, plate_z = _local(center, size, 2, 8, rotation)
    structure.set(
        plate_x, bottom + 1, plate_z, "minecraft:wooden_pressure_plate"
    )
    if record_marker:
        markers["ghastTraps"].append(
            {"offset": list(trap_position), "block": "tf_slice:ghast_trap"}
        )


def _render_boss_trap_tower(structure, markers, tower, rotation, shell_seed):
    """Port the open DarkTowerBossTrapComponent room and trigger circuit."""
    center = tuple(tower["center"])
    size = int(tower["size"])
    bottom = int(tower["bottomY"])
    height = int(tower["height"])
    top = _render_encased_shell(
        structure, center, size, bottom, height, shell_seed
    )
    _render_beard(structure, center, size, bottom)

    # The source adds one double-wide flight down from the middle landing and
    # one double-wide flight down from the upper rim.  These are relative
    # counter-clockwise/clockwise rotations of the oriented trap component,
    # not opposed duplicate flights on both sides of each level.
    middle_y = bottom + 4
    _fill_local(
        structure, center, size, 1, middle_y, 1,
        size - 2, middle_y, size - 2, TOWERWOOD, rotation,
    )
    _render_small_stairs_down(
        structure, center, size, middle_y, (rotation + 3) % 4
    )
    _render_small_stairs_down(
        structure, center, size, top, (rotation + 1) % 4
    )

    # makeARoof is a no-op, but makeEncasedWalls still creates the top shell.
    # The source then punches three irregular upper bursts plus a smaller beam
    # shaft; deleting the entire plane produced the flat boxes in the report.
    for local_x, local_y, local_z, amount, salt in (
        (5, height + 2, 5, 4, 0),
        (0, height, 0, 3, 1),
        (0, height, 8, 4, 2),
        (5, 6, 5, 2, 3),
    ):
        burst_x, burst_z = _local(
            center, size, local_x, local_z, rotation
        )
        radius = amount + ((int(shell_seed) + salt * 17) % amount)
        _carve_bombed_breach(
            structure, markers, (burst_x, burst_z),
            bottom + local_y, radius, int(shell_seed) + salt,
        )

    # Source redraws the lower half-floor and the air above it after the beam
    # burst so the trigger circuit remains traversable and visible.
    _fill_local(
        structure, center, size, 1, bottom, 1,
        size // 2, bottom, size - 2, TOWERWOOD, rotation,
    )
    _fill_local(
        structure, center, size, 1, bottom + 1, 1,
        size // 2, bottom + 1, size - 2, "minecraft:air", rotation,
    )

    _record_room(markers, tower["id"], "boss_trap", center, bottom, size)
    _render_boss_trap_trigger(
        structure, markers, tower, rotation, record_marker=True
    )


def _carve_bombed_breach(structure, markers, center, y, radius, salt):
    cx, cz = (int(value) for value in center)
    y = int(y)
    radius = int(radius)
    salt = int(salt)

    def blob_positions(blob_center, blob_radius):
        blob_radius = max(0, int(blob_radius))
        bx, by, bz = blob_center
        for dx in range(-blob_radius, blob_radius + 1):
            for dy in range(-blob_radius, blob_radius + 1):
                for dz in range(-blob_radius, blob_radius + 1):
                    ordered = sorted(
                        (abs(dx), abs(dy), abs(dz)), reverse=True
                    )
                    distance = (
                        ordered[0]
                        + int(ordered[1] * 0.5)
                        + int(ordered[2] * 0.25)
                    )
                    if distance <= blob_radius:
                        yield (bx + dx, by + dy, bz + dz)

    def clear_blob(blob_center, blob_radius):
        for position in blob_positions(blob_center, blob_radius):
            structure.blocks.pop(position, None)

    def transform_blob(blob_center, blob_radius, transform_salt):
        for position in blob_positions(blob_center, blob_radius):
            existing = structure.blocks.get(position)
            if existing is None or existing[0] == "minecraft:air":
                continue
            structure.set(
                position[0], position[1], position[2],
                "minecraft:netherrack",
            )
            above = (position[0], position[1] + 1, position[2])
            above_block = structure.blocks.get(above)
            if (
                (position[0] + position[1] + position[2] + transform_salt)
                % 2 == 0
                and (
                    above_block is None
                    or above_block[0] == "minecraft:air"
                )
            ):
                structure.set(above[0], above[1], above[2], "minecraft:fire")

    # DarkTowerWingComponent.destroyTower first clears the main blob, then
    # performs three offset nether-transform/clear passes.  Critically, the
    # source transforms only non-air blocks; it never constructs a shell in
    # the sky around the explosion.
    clear_blob((cx, y, cz), radius)
    offset = max(0, radius - 1)
    for index in range(3):
        signs = tuple(
            1 if (salt * 31 + index * 17 + axis * 13) % 2 else -1
            for axis in range(3)
        )
        secondary = (
            cx + offset * signs[0],
            y + offset * signs[1],
            cz + offset * signs[2],
        )
        transform_blob(secondary, radius - 1, salt + index)
        clear_blob(secondary, radius - 2)
    markers["bombedBreaches"].append(
        {"offset": [int(cx), int(y), int(cz)], "radius": radius}
    )


def _open_ruined_boss_top(structure, markers, tower, platform_y, seed):
    """Materialize the final main component's five source destruction bursts."""
    center_x, center_z = (int(value) for value in tower["center"])
    top_y = int(tower["bottomY"]) + int(tower["height"]) - 1
    minimum_x = center_x - 9
    minimum_z = center_z - 9
    source_bursts = ((12, 3, 4), (3, 12, 4), (3, 3, 4), (12, 12, 4), (8, 8, 5))
    for index, (local_x, local_z, amount) in enumerate(source_bursts):
        radius = int(amount) + (
            int(seed) * 31 + index * 17 + local_x * 3 + local_z
        ) % int(amount)
        _carve_bombed_breach(
            structure,
            markers,
            (minimum_x + local_x, minimum_z + local_z),
            top_y + 5,
            radius,
            int(seed) * 31 + index,
        )


def _door_plane(
    structure,
    center,
    toward,
    y,
    locked=False,
    door_block="tf_slice:unbreakable_vanishing_block",
    size=19,
):
    cx, cz = center
    tx, tz = toward
    dx = 0 if tx == cx else (1 if tx > cx else -1)
    dz = 0 if tz == cz else (1 if tz > cz else -1)
    radius = int(size) // 2
    wall_x = cx + dx * radius
    wall_z = cz + dz * radius
    positions = []
    for across in range(-1, 2):
        for dy in range(3):
            x = wall_x + (across if dz else 0)
            z = wall_z + (across if dx else 0)
            block = door_block
            if locked and (across, dy) in ((-1, 0), (1, 0), (-1, 2), (1, 2)):
                block = "tf_slice:tower_key_door"
            states = (
                {"tf_slice:locked": True}
                if block == "tf_slice:tower_key_door"
                else None
            )
            structure.set(x, y + dy, z, block, states)
            positions.append((x, y + dy, z, block))
    return positions


def _framed_door_plane(
    structure,
    center,
    toward,
    y,
    door_block="tf_slice:reappearing_block",
    size=19,
):
    """Author the source five-wide accent frame around a 3x3 door."""
    cx, cz = center
    tx, tz = toward
    dx = 0 if tx == cx else (1 if tx > cx else -1)
    dz = 0 if tz == cz else (1 if tz > cz else -1)
    radius = int(size) // 2
    wall_x = cx + dx * radius
    wall_z = cz + dz * radius
    frame = []
    for across in range(-2, 3):
        for height in range(-1, 4):
            if abs(across) != 2 and height not in (-1, 3):
                continue
            x = wall_x + (across if dz else 0)
            z = wall_z + (across if dx else 0)
            structure.set(x, y + height, z, ENCASED_TOWERWOOD)
            frame.append((x, y + height, z))
    door = _door_plane(
        structure,
        center,
        toward,
        y,
        False,
        door_block,
        size,
    )
    return door, frame


def _layout(seed):
    if int(seed) == 0:
        centers = ((64, 80), (96, 80), (96, 48))
        heights = (61, 66, 76)
        key_layouts = (
            (((45, 80), (31, 80)), ((64, 61), (64, 47)), ((64, 99), (64, 113)), ((45, 100), (31, 100))),
            (((115, 80), (129, 80)), ((115, 60), (129, 60)), ((96, 99), (96, 113)), ((115, 100), (129, 100))),
        )
        entrance_centers = ((64, 63), (64, 97))
    elif int(seed) == 1:
        centers = ((96, 96), (96, 64), (64, 64))
        heights = (66, 61, 76)
        key_layouts = (
            (((115, 96), (129, 96)), ((96, 115), (96, 129)), ((77, 96), (63, 96)), ((115, 115), (129, 115))),
            (((96, 45), (96, 31)), ((115, 64), (129, 64)), ((115, 45), (129, 45)), ((115, 83), (129, 83))),
        )
        entrance_centers = ((79, 96), (113, 96))
    else:
        raise ValueError("only locked dark-tower layout seeds 0 and 1 are releasable")
    # The authored complex is at most 107 blocks wide.  Keep its exact relative
    # geometry while trimming empty template margins so surface adaptation does
    # not emit scores of empty 16x16 tiles.
    coordinate_offset = 23
    centers = tuple(
        (x - coordinate_offset, z - coordinate_offset) for x, z in centers
    )
    key_layouts = tuple(
        tuple(
            (
                (support[0] - coordinate_offset, support[1] - coordinate_offset),
                (key[0] - coordinate_offset, key[1] - coordinate_offset),
            )
            for support, key in stage
        )
        for stage in key_layouts
    )
    entrance_centers = tuple(
        (x - coordinate_offset, z - coordinate_offset)
        for x, z in entrance_centers
    )
    bottoms = [16]
    for height in heights[:-1]:
        bottoms.append(bottoms[-1] + height - 5)
    main_towers = [
        {
            "id": "main_%d" % stage,
            "stage": stage,
            "center": list(centers[stage]),
            "bottomY": bottoms[stage],
            "height": heights[stage],
            "size": 19,
        }
        for stage in range(3)
    ]
    return main_towers, key_layouts, entrance_centers


def render(seed, api, surface_ground_y, decoration_seed=None):
    seed = int(seed)
    decoration_seed = (
        seed if decoration_seed is None else int(decoration_seed)
    )
    SparseStructure = api["SparseStructure"]
    structure = SparseStructure(
        (112, 224, 112),
        "dark_tower_%d_rooms_%d" % (seed, decoration_seed),
    )
    markers = {
        "mainTowers": [],
        "wingTowers": [],
        "entranceTowers": [],
        "keyTowers": [],
        "bossTrapTowers": [],
        "keyDoors": [],
        "keyChests": [],
        "mechanisms": [],
        "ghastTraps": [],
        "lootChests": [],
        "structureSpawners": [],
        "rooms": [],
        "roofs": [],
        "bombedBreaches": [],
        "balconies": [],
        "bridges": [],
        "mainFloorZones": [],
    }
    graph = []
    main_towers, key_layouts, entrance_centers = _layout(seed)

    room_cursor = 0
    main_tops = []
    for tower in main_towers:
        top_y, room_cursor = _render_main_tower(
            structure,
            markers,
            api,
            tower,
            room_cursor,
            seed,
            decoration_seed,
        )
        main_tops.append(top_y)
        markers["mainTowers"].append(dict(tower))
        if tower["stage"] < 2:
            _render_roof(
                structure,
                markers,
                tower,
                ROOF_TYPES[(seed + tower["stage"]) % len(ROOF_TYPES)],
            )

    # Locked source main bridges: one four-lock door after each set of four
    # key towers, never three arbitrary vertical doors in one shell.
    for stage in range(2):
        current = main_towers[stage]
        following = main_towers[stage + 1]
        bridge_y = following["bottomY"]
        markers["bridges"].extend(_render_connection(
            structure,
            current["center"],
            current["size"],
            following["center"],
            following["size"],
            bridge_y,
        ))
        locks = _door_plane(
            structure,
            tuple(current["center"]),
            tuple(following["center"]),
            bridge_y + 1,
            True,
        )
        lock_positions = [list(value[:3]) for value in locks if value[3] == "tf_slice:tower_key_door"]
        markers["keyDoors"].append(
            {
                "stage": stage,
                "offset": lock_positions[0],
                "locks": lock_positions,
                "block": "tf_slice:tower_key_door",
                "requiredKeys": 4,
            }
        )
        graph.append([current["id"], following["id"]])

    # Two low reappearing-door entrance towers, as in the source component.
    surface_entrance_position = None
    for index, center in enumerate(entrance_centers):
        tower = {
            "id": "entrance_%d" % index,
            "stage": 0,
            "center": list(center),
            "bottomY": 16,
            "height": 13,
            "size": 9,
        }
        _render_encased_shell(structure, center, 9, 16, 13, seed * 31 + index)
        markers["bridges"].extend(_render_connection(
            structure,
            center,
            tower["size"],
            main_towers[0]["center"],
            main_towers[0]["size"],
            16,
        ))
        entrance_door = _door_plane(
            structure,
            center,
            tuple(main_towers[0]["center"]),
            17,
            False,
            "tf_slice:reappearing_block",
            tower["size"],
        )
        marker = dict(tower)
        toward_main_x = (
            0 if main_towers[0]["center"][0] == center[0]
            else (1 if main_towers[0]["center"][0] > center[0] else -1)
        )
        toward_main_z = (
            0 if main_towers[0]["center"][1] == center[1]
            else (1 if main_towers[0]["center"][1] > center[1] else -1)
        )
        exterior_doors = []
        for outside_x, outside_z in (
            (-toward_main_z, toward_main_x),
            (toward_main_z, -toward_main_x),
        ):
            exterior, exterior_frame = _framed_door_plane(
                structure,
                center,
                (center[0] + outside_x, center[1] + outside_z),
                17,
                "tf_slice:reappearing_block",
                tower["size"],
            )
            exterior_doors.append(
                {
                    "center": list(exterior[4][:3]),
                    "blocks": [list(value[:3]) for value in exterior],
                    "frame": [list(value) for value in exterior_frame],
                }
            )
        marker["exteriorDoors"] = exterior_doors
        if surface_entrance_position is None:
            surface_entrance_position = list(
                exterior_doors[0]["center"]
            )
        markers["entranceTowers"].append(marker)
        markers["wingTowers"].append(marker)
        graph.append(["main_0", tower["id"]])

    # The first two stages each own four recursive size-9 key towers.  Size-11
    # intermediary wings preserve the source's branch/bridge silhouettes.
    roof_cursor = 0
    for stage, pairs in enumerate(key_layouts):
        main = main_towers[stage]
        support_bottom = main["bottomY"] + main["height"] - 29
        stage_supports = []
        for branch, (support_center, key_center) in enumerate(pairs):
            support = {
                "id": "stage_%d_support_%d" % (stage, branch),
                "stage": stage,
                "center": list(support_center),
                "bottomY": support_bottom,
                "height": 29,
                "size": 11,
                "keyTower": False,
            }
            key = {
                "id": "stage_%d_key_%d" % (stage, branch),
                "stage": stage,
                "center": list(key_center),
                "bottomY": support_bottom + 8,
                "height": 21,
                "size": 9,
                "keyTower": True,
            }
            for tower in (support, key):
                _render_side_tower(
                    structure,
                    markers,
                    api,
                    tower,
                    ROOF_TYPES[roof_cursor % len(ROOF_TYPES)],
                    decoration_seed * 101
                    + stage * 29
                    + branch * 5
                    + int(tower["size"]),
                )
                roof_cursor += 1
                markers["wingTowers"].append({key: value for key, value in tower.items() if key != "keyTower"})
            branch_dx = 0 if key_center[0] == support_center[0] else (
                1 if key_center[0] > support_center[0] else -1
            )
            branch_dz = 0 if key_center[1] == support_center[1] else (
                1 if key_center[1] > support_center[1] else -1
            )
            balcony_direction = (-branch_dz, branch_dx)
            if (seed + stage + branch) % 2:
                balcony_direction = (-balcony_direction[0], -balcony_direction[1])
            balcony_id = "stage_%d_balcony_%d" % (stage, branch)
            _render_balcony(
                structure,
                markers,
                support,
                balcony_direction,
                support_bottom + 8,
                balcony_id,
            )
            parent = main
            if (
                support_center[0] != main["center"][0]
                and support_center[1] != main["center"][1]
            ):
                aligned = [
                    candidate for candidate in stage_supports
                    if candidate["center"][0] == support_center[0]
                    or candidate["center"][1] == support_center[1]
                ]
                if not aligned:
                    raise ValueError(
                        "no cardinal parent for side tower %s" % support["id"]
                    )
                parent = min(
                    aligned,
                    key=lambda candidate: (
                        abs(candidate["center"][0] - support_center[0])
                        + abs(candidate["center"][1] - support_center[1])
                    ),
                )
            markers["bridges"].extend(_render_connection(
                structure,
                parent["center"],
                parent["size"],
                support_center,
                support["size"],
                support["bottomY"] + support["height"] - 5,
            ))
            markers["bridges"].extend(_render_connection(
                structure,
                support_center,
                support["size"],
                key_center,
                key["size"],
                key["bottomY"] + key["height"] - 5,
            ))
            graph.append([parent["id"], support["id"]])
            graph.append([support["id"], key["id"]])
            graph.append([support["id"], balcony_id])
            stage_supports.append(support)
            if (stage + branch + seed) % 2 == 0:
                breach_y = support_bottom + 15
                edge_x = support_center[0] + (5 if key_center[0] >= support_center[0] else -5)
                _carve_bombed_breach(
                    structure,
                    markers,
                    (edge_x, support_center[1]),
                    breach_y,
                    3,
                    seed * 11 + stage * 5 + branch,
                )

    # Merged child pieces and openings are now complete.  The Java main piece
    # owns its circulation independently, so reapply its source flights before
    # the final component's deliberate destruction pass.
    zones_by_tower = {
        zone["tower"]: zone for zone in markers["mainFloorZones"]
    }
    for tower in main_towers:
        _restore_main_stair_circulation(
            structure, tower, zones_by_tower[tower["id"]]
        )

    # Final main tower: four open boss-trap towers, each with a ghast trap and
    # redstone approach.  The Ur-Ghast marker sits on the ruined top floor.
    boss_main = main_towers[2]
    boss_platform_y = main_tops[2] - 5
    # In the source each child bridge is post-processed after the main tower's
    # destruction pass.  Our sparse port merges all pieces, so running this
    # later would let the main burst erase already-authored child bridges.
    _open_ruined_boss_top(
        structure, markers, boss_main, boss_platform_y, seed
    )
    trap_centers = (
        (boss_main["center"][0] + 19, boss_main["center"][1]),
        (boss_main["center"][0] - 19, boss_main["center"][1]),
        (boss_main["center"][0], boss_main["center"][1] + 19),
        (boss_main["center"][0], boss_main["center"][1] - 19),
    )
    for index, center in enumerate(trap_centers):
        tower = {
            "id": "boss_trap_%d" % index,
            "stage": 2,
            "center": list(center),
            "bottomY": boss_platform_y,
            "height": 9,
            "size": 11,
        }
        _render_boss_trap_tower(
            structure, markers, tower, index, seed * 73 + index
        )
        markers["bossTrapTowers"].append(dict(tower))
        markers["wingTowers"].append(dict(tower))
        markers["bridges"].extend(_render_connection(
            structure,
            boss_main["center"],
            boss_main["size"],
            center,
            tower["size"],
            boss_platform_y,
        ))
        # The bridge landing is emitted after the room, just as the component
        # graph does.  Redraw the six-part trigger so landing headroom cannot
        # erase the pressure plate or the last turns of redstone wire.
        _render_boss_trap_trigger(
            structure, markers, tower, index, record_marker=False
        )
        graph.append(["main_2", tower["id"]])

    # DarkTowerMainComponent runs makeOpenings after its destruction pass.
    # Re-cut the four trap approaches so transformed netherrack cannot seal a
    # bridge that the component graph already connected.
    boss_center = tuple(boss_main["center"])
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for across in range(-1, 2):
            doorway_x = (
                boss_center[0] + dx * 9 + (across if dz else 0)
            )
            doorway_z = (
                boss_center[1] + dz * 9 + (across if dx else 0)
            )
            for doorway_y in range(
                boss_platform_y + 1, boss_platform_y + 4
            ):
                structure.set(
                    doorway_x, doorway_y, doorway_z, "minecraft:air"
                )

    # Bridge pieces are separate source components and retain their landing
    # blocks even when the main-component destruction pass opens the adjacent
    # wall.  Restore only endpoints erased by the port's merged full-structure
    # blast simulation so every authored connection still has a foothold.
    for bridge in markers["bridges"]:
        for endpoint_name in ("start", "end"):
            endpoint = tuple(int(value) for value in bridge[endpoint_name])
            existing = structure.blocks.get(endpoint)
            if existing is None or existing[0] == "minecraft:air":
                structure.set(
                    endpoint[0], endpoint[1], endpoint[2], TOWERWOOD
                )

    # The final main component already authored the source three-quarter floor.
    # Keep that asymmetrical landing instead of replacing it with a 17x17 slab.
    boss_spawner = (boss_center[0], boss_platform_y + 4, boss_center[1])
    structure.set(*boss_spawner, name="tf_slice:ur_ghast_boss_spawner")
    markers["bossPlatform"] = {
        "offset": [boss_center[0], boss_platform_y, boss_center[1]],
        "radius": 8,
    }
    markers["urGhastSpawner"] = {
        "offset": list(boss_spawner),
        "block": "tf_slice:ur_ghast_boss_spawner",
    }
    _restore_authored_lever_supports(structure)
    markers["surfaceEntrance"] = {
        "offset": surface_entrance_position,
        "block": "tf_slice:reappearing_block",
    }
    markers["roof"] = {
        "minimum": [boss_center[0] - 9, boss_platform_y, boss_center[1] - 9],
        "maximum": [boss_center[0] + 9, main_tops[2], boss_center[1] + 9],
    }

    tree_root_shield = dark_tower_tree_root_shield_positions(
        markers,
        surface_ground_y,
        structure_minimum_y=0,
    )
    shield_fill_blocks = {
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
        "minecraft:grass",
        "minecraft:grass_block",
        "minecraft:dirt",
        "minecraft:podzol",
    }
    filled_root_shield = 0
    for x, y, z in sorted(tree_root_shield):
        existing = structure.blocks.get((x, y, z))
        if existing is None or existing[0] in shield_fill_blocks:
            structure.set(x, y, z, TOWERWOOD)
            filled_root_shield += 1
    shield_columns = set((x, z) for x, _y, z in tree_root_shield)
    markers["treeRootShield"] = {
        "blocks": len(tree_root_shield),
        "columns": len(shield_columns),
        "filledBlocks": filled_root_shield,
        "minimumY": 0,
        "maximumY": int(surface_ground_y),
        "scope": "authored_ground_tower_interiors_only",
    }

    reached = _reachable(graph, "main_0")
    room_types = set(room["type"] for room in markers["rooms"])
    main_room_types = set(
        room["type"]
        for room in markers["rooms"]
        if str(room["tower"]).startswith("main_")
    )
    allowed_main_room_types = set(MAIN_ROOM_TYPES) | {
        "timber_maze",
        "builder_platforms",
        "reactor_experiment",
    }
    validation = {
        "entranceReachable": all(tower["id"] in reached for tower in markers["entranceTowers"]),
        "keyPathReachable": len(markers["keyDoors"]) == 2 and len(markers["keyChests"]) == 8,
        "bossPlatformReachable": "main_2" in reached,
        "roofComplete": sum(
            1
            for x in range(boss_center[0] - 8, boss_center[0] + 9)
            for z in range(boss_center[1] - 8, boss_center[1] + 9)
            if structure.blocks.get(
                (x, boss_platform_y, z), ("minecraft:air",)
            )[0] != "minecraft:air"
        ) >= 160,
        "allMainTowersReachable": all(tower["id"] in reached for tower in main_towers),
        "allKeyTowersReachable": all(tower["tower"] in reached for tower in markers["keyTowers"]),
        "bossTrapsReachable": all(tower["id"] in reached for tower in markers["bossTrapTowers"]),
        # Random Java floor decoration does not promise that every weighted
        # branch occurs in each structure.  Require every deterministic room
        # family, at least one weighted main-floor room, and no unknown main
        # room type; the two locked variants jointly exercise the full pool.
        "roomCoverageComplete": (
            REQUIRED_LAYOUT_ROOM_TYPES.issubset(room_types)
            and bool(main_room_types & RANDOMIZED_MAIN_ROOM_TYPES)
            and main_room_types.issubset(allowed_main_room_types)
        ),
        "forbiddenBlocks": sorted(
            set(value[0] for value in structure.blocks.values())
            & set(api["FORBIDDEN_OUTPUT_BLOCKS"])
        ),
    }
    if not all(
        validation[key]
        for key in (
            "entranceReachable",
            "keyPathReachable",
            "bossPlatformReachable",
            "roofComplete",
            "allMainTowersReachable",
            "allKeyTowersReachable",
            "bossTrapsReachable",
            "roomCoverageComplete",
        )
    ):
        raise ValueError("dark tower layout %d failed topology validation: %r" % (seed, validation))
    if validation["forbiddenBlocks"]:
        raise ValueError("dark tower layout contains forbidden blocks")

    # Only the first 19x19 main component owns terrain adaptation.  Elevated
    # wings keep their source beards and the surrounding forest stays native.
    structure.surface_ground_y = int(surface_ground_y)
    structure.surface_core_center = tuple(main_towers[0]["center"])
    structure.surface_core_radius = 10
    structure.surface_columns = {
        (x, z): int(surface_ground_y)
        for x in range(structure.size[0])
        for z in range(structure.size[2])
        if (x - main_towers[0]["center"][0]) ** 2
        + (z - main_towers[0]["center"][1]) ** 2
        <= 10 ** 2
    }
    return structure, markers, validation, graph, boss_spawner


def _reachable(edges, start):
    adjacency = {}
    for left, right in edges:
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)
    seen = set((start,))
    pending = [start]
    while pending:
        current = pending.pop()
        for neighbor in adjacency.get(current, ()):
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    return seen
