# -*- coding: utf-8 -*-
"""Pure 128x128 one-block-per-pixel Labyrinth map rules."""

import math


MAP_SIZE = 128
VERTICAL_SCAN_RADIUS = 3
EXTRA_ID_PREFIX = "tfmz:v1:"
DISCOVERY_RADIUS = 8
SCAN_BUDGET = 32
PASSABLE_BLOCKS = frozenset((
    "air", "minecraft:air", "minecraft:cave_air", "minecraft:void_air",
    "minecraft:torch", "minecraft:wall_torch", "minecraft:redstone_torch",
))
SCAN_OFFSETS = sorted(
    ((x, z) for z in range(-DISCOVERY_RADIUS, DISCOVERY_RADIUS + 1)
     for x in range(-DISCOVERY_RADIUS, DISCOVERY_RADIUS + 1)
     if x * x + z * z <= DISCOVERY_RADIUS * DISCOVERY_RADIUS),
    key=lambda point: (point[0] * point[0] + point[1] * point[1], point),
)


def encode_identity(labyrinth_id, center_x, y_center, center_z):
    escaped_id = str(labyrinth_id).replace("%", "%25").replace(":", "%3A")
    if not escaped_id:
        raise ValueError("invalid labyrinth id")
    return "%s%s:%d:%d:%d" % (
        EXTRA_ID_PREFIX,
        escaped_id,
        int(center_x),
        int(y_center),
        int(center_z),
    )


def decode_identity(value):
    value = str(value or "")
    if not value.startswith(EXTRA_ID_PREFIX):
        return None
    parts = value[len(EXTRA_ID_PREFIX):].split(":")
    if len(parts) != 4 or not parts[0]:
        return None
    try:
        labyrinth_id = parts[0].replace("%3A", ":").replace("%25", "%")
        return (
            labyrinth_id,
            int(parts[1]),
            int(parts[2]),
            int(parts[3]),
        )
    except (TypeError, ValueError):
        return None


def create_record(labyrinth_id, center, player_y):
    center_x, center_y, center_z = (int(value) for value in center)
    return {
        "schemaVersion": 1,
        "mapKind": "maze",
        "labyrinthId": str(labyrinth_id),
        "centerX": center_x,
        "centerZ": center_z,
        "yCenter": center_y,
        "verticalOffset": 0,
        "verticalMarker": vertical_marker(player_y, center_y),
        "blocksPerPixel": 1,
        "width": MAP_SIZE,
        "height": MAP_SIZE,
        "exploredCells": {},
    }


def map_identity(record):
    return encode_identity(record["labyrinthId"], record["centerX"],
                           record["yCenter"], record["centerZ"])


def update_player_height(snapshot, player_y):
    if snapshot.get("mapKind") == "maze":
        snapshot["verticalOffset"] = int(math.floor(player_y)) - int(snapshot["yCenter"])
        snapshot["verticalMarker"] = vertical_marker(player_y, snapshot["yCenter"])


def normalize_explored_cells(raw):
    cells = {}
    if not isinstance(raw, dict):
        return cells
    for index, value in raw.items():
        try:
            index = int(index)
        except (ValueError, TypeError):
            continue
        if 0 <= index < MAP_SIZE * MAP_SIZE and value in ("unknown", "clearing"):
            cells[str(index)] = value
    return cells


def explored_runs(cells):
    cells = normalize_explored_cells(cells)
    runs = []
    for row in range(MAP_SIZE):
        column = 0
        while column < MAP_SIZE:
            color = cells.get(str(row * MAP_SIZE + column))
            if color is None:
                column += 1
                continue
            end = column + 1
            while end < MAP_SIZE and cells.get(str(row * MAP_SIZE + end)) == color:
                end += 1
            runs.append([row, column, end, color])
            column = end
    return runs


def explore(record, player, get_block, budget=SCAN_BUDGET):
    """Refresh a bounded rotating window of live, loaded passage columns."""
    if vertical_marker(player[1], record["yCenter"]) != "same":
        return False
    px, pz = int(math.floor(player[0])), int(math.floor(player[2]))
    minimum_x = int(record["centerX"]) - MAP_SIZE // 2
    minimum_z = int(record["centerZ"]) - MAP_SIZE // 2
    if not (minimum_x <= px < minimum_x + MAP_SIZE
            and minimum_z <= pz < minimum_z + MAP_SIZE):
        return False
    origin = (px, pz)
    cursor = int(record.get("_scanCursor", 0)) if record.get("_scanOrigin") == origin else 0
    cells = record.setdefault("exploredCells", {})
    changed = False
    for step in range(min(max(0, int(budget)), len(SCAN_OFFSETS))):
        dx, dz = SCAN_OFFSETS[(cursor + step) % len(SCAN_OFFSETS)]
        x, z = px + dx, pz + dz
        if not (minimum_x <= x < minimum_x + MAP_SIZE
                and minimum_z <= z < minimum_z + MAP_SIZE):
            continue
        blocks = [get_block((x, int(record["yCenter"]) + offset, z)) for offset in (0, 1)]
        if any(not isinstance(block, dict) or not block.get("name") for block in blocks):
            continue
        color = "clearing" if all(block["name"] in PASSABLE_BLOCKS for block in blocks) else "unknown"
        index = str((z - minimum_z) * MAP_SIZE + x - minimum_x)
        if cells.get(index) != color:
            cells[index] = color
            changed = True
    record["_scanOrigin"] = origin
    record["_scanCursor"] = (cursor + min(max(0, int(budget)), len(SCAN_OFFSETS))) % len(SCAN_OFFSETS)
    return changed


def snapshot_runs(passage_runs, structure_origin, map_center):
    """Translate compiled local passage runs into a 128px wire snapshot."""
    origin_x, origin_z = int(structure_origin[0]), int(structure_origin[1])
    center_x, center_z = int(map_center[0]), int(map_center[1])
    minimum_x = center_x - MAP_SIZE // 2
    minimum_z = center_z - MAP_SIZE // 2
    result = []
    for row in range(MAP_SIZE):
        result.append([row, 0, MAP_SIZE, "unknown"])
    for run in passage_runs or ():
        try:
            world_z = origin_z + int(run[0])
            start = origin_x + int(run[1]) - minimum_x
            end = origin_x + int(run[2]) - minimum_x
            row = world_z - minimum_z
        except (IndexError, TypeError, ValueError):
            continue
        start = max(0, start)
        end = min(MAP_SIZE, end)
        if 0 <= row < MAP_SIZE and start < end:
            result.append([row, start, end, "clearing"])
    return result


def build_snapshot(record, passage_runs, structure_origin, player):
    center_x = int(record["centerX"])
    center_z = int(record["centerZ"])
    return {
        "schemaVersion": 3,
        "mapKind": "maze",
        "labyrinthId": str(record["labyrinthId"]),
        "mapId": map_identity(record),
        "dimensionId": int(record.get("dimensionId", 0)),
        "center": [center_x, center_z],
        "bounds": [
            center_x - MAP_SIZE // 2,
            center_z - MAP_SIZE // 2,
            center_x + MAP_SIZE // 2 - 1,
            center_z + MAP_SIZE // 2 - 1,
        ],
        "player": [int(math.floor(player[0])), int(math.floor(player[2]))],
        "players": [],
        "gridSize": MAP_SIZE,
        "blocksPerPixel": 1,
        "biomeRuns": explored_runs(record.get("exploredCells", {})),
        "landmarks": [],
        "yCenter": int(record["yCenter"]),
        "verticalOffset": int(math.floor(player[1])) - int(record["yCenter"]),
        "verticalMarker": vertical_marker(player[1], record["yCenter"]),
    }


def visible_passages(blocks, y_center):
    pixels = set()
    y_center = int(y_center)
    for x, y, z, block_name in blocks:
        if abs(int(y) - y_center) > VERTICAL_SCAN_RADIUS:
            continue
        if str(block_name) in ("air", "minecraft:air"):
            pixels.add((int(x), int(z)))
    return pixels


def vertical_marker(player_y, y_center):
    difference = int(math.floor(player_y)) - int(y_center)
    if difference > VERTICAL_SCAN_RADIUS:
        return "up"
    if difference < -VERTICAL_SCAN_RADIUS:
        return "down"
    return "same"
