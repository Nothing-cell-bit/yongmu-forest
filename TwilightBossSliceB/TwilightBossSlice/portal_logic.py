# -*- coding: utf-8 -*-
"""Pure Twilight portal validation shared by ModSDK code and unit tests."""

import math

PLAYER_POSITION_HEIGHT = 1.62
PORTAL_SERVER_SAFE_CHUNK_RADIUS = 1
PORTAL_CLIENT_READY_CHUNK_RADIUS = 1
PORTAL_BACKGROUND_PRELOAD_CHUNK_RADIUS = 4

HORIZONTAL = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
)

WATER_BLOCKS = set(
    (
        "minecraft:water",
        "minecraft:flowing_water",
    )
)

EXIT_AIR_BLOCKS = set(
    (
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
    )
)

PORTAL_EDGE_BLOCKS = set(
    (
        "minecraft:coarse_dirt",
        "minecraft:dirt",
        "minecraft:dirt_path",
        "minecraft:farmland",
        "minecraft:grass",
        "minecraft:grass_block",
        "minecraft:grass_path",
        "minecraft:mud",
        "minecraft:mycelium",
        "minecraft:podzol",
    )
)

PORTAL_GROUND_BLOCKS = set(
    (
        "minecraft:clay",
        "minecraft:coarse_dirt",
        "minecraft:deepslate",
        "minecraft:dirt",
        "minecraft:dirt_path",
        "minecraft:farmland",
        "minecraft:grass",
        "minecraft:grass_block",
        "minecraft:gravel",
        "minecraft:mud",
        "minecraft:mycelium",
        "minecraft:podzol",
        "minecraft:red_sand",
        "minecraft:sand",
        "minecraft:snow",
        "minecraft:stone",
        "minecraft:terracotta",
    )
)

FLOWER_BLOCKS = set(
    (
        "minecraft:allium",
        "minecraft:azure_bluet",
        "minecraft:blue_orchid",
        "minecraft:cactus_flower",
        "minecraft:closed_eyeblossom",
        "minecraft:cornflower",
        "minecraft:dandelion",
        "minecraft:double_plant",
        "minecraft:flowering_azalea",
        "minecraft:lilac",
        "minecraft:lily_of_the_valley",
        "minecraft:orange_tulip",
        "minecraft:open_eyeblossom",
        "minecraft:oxeye_daisy",
        "minecraft:peony",
        "minecraft:pink_petals",
        "minecraft:pink_tulip",
        "minecraft:pitcher_plant",
        "minecraft:poppy",
        "minecraft:red_flower",
        "minecraft:red_tulip",
        "minecraft:rose_bush",
        "minecraft:spore_blossom",
        "minecraft:sunflower",
        "minecraft:torchflower",
        "minecraft:white_tulip",
        "minecraft:wildflowers",
        "minecraft:wither_rose",
        "minecraft:yellow_flower",
    )
)

PORTAL_DECORATION_BLOCKS = FLOWER_BLOCKS | set(
    (
        "minecraft:azalea",
        "minecraft:bamboo",
        "minecraft:brown_mushroom",
        "minecraft:crimson_fungus",
        "minecraft:deadbush",
        "minecraft:fern",
        "minecraft:glow_lichen",
        "minecraft:grass",
        "minecraft:red_mushroom",
        "minecraft:sapling",
        "minecraft:sugar_cane",
        "minecraft:tall_grass",
        "minecraft:tallgrass",
        "minecraft:vine",
        "minecraft:warped_fungus",
    )
)


def block_name(block):
    if isinstance(block, dict):
        return block.get("name", "")
    return block or ""


def item_name(item):
    if not item:
        return ""
    return (
        item.get("newItemName")
        or item.get("itemName")
        or item.get("name")
        or ""
    )


def is_water(block):
    return block_name(block) in WATER_BLOCKS


def is_edge(block):
    return block_name(block) in PORTAL_EDGE_BLOCKS


def is_decoration(block):
    name = block_name(block)
    if name in PORTAL_DECORATION_BLOCKS:
        return True
    return name.endswith(
        (
            "_flower",
            "_leaves",
            "_mushroom",
            "_sapling",
            "_tulip",
        )
    )


def is_support(block, portal_identifier):
    name = block_name(block)
    return bool(
        name
        and name not in WATER_BLOCKS
        and name not in ("minecraft:air", portal_identifier)
        and not is_decoration(name)
    )


def is_portal_ground(block):
    """Return whether a block is suitable terrain below a generated portal."""
    name = block_name(block)
    return (
        name in PORTAL_GROUND_BLOCKS
        or name.endswith("_terracotta")
    )


def paired_portal_origin(source_surface, surface_y):
    """Keep a source portal's lowest X/Z when pairing it in another dimension."""
    if not source_surface:
        return None
    return (
        min(pos[0] for pos in source_surface),
        int(surface_y),
        min(pos[2] for pos in source_surface),
    )


def find_portal_surface_y(
    x,
    z,
    get_top_height,
    get_block,
    minimum_y=-64,
    maximum_y=320,
):
    """Find terrain below foliage so arrivals never begin above a tree canopy."""
    top_y = get_top_height((int(x), int(z)))
    if top_y is None:
        return None
    try:
        top_y = int(top_y)
    except (TypeError, ValueError):
        return None
    if top_y < int(minimum_y) or top_y > int(maximum_y):
        return None
    for y in range(top_y, int(minimum_y) - 1, -1):
        if is_portal_ground(get_block((int(x), y, int(z)))):
            return y + 1
    return None


def _offset(pos, dx=0, dy=0, dz=0):
    return (pos[0] + dx, pos[1] + dy, pos[2] + dz)


def collect_enclosed_surface(
    start,
    get_block,
    surface_names,
    portal_identifier,
    minimum_size=4,
    maximum_size=64,
):
    """Return connected surface cells when support and decorated edge are valid."""
    if block_name(get_block(start)) not in surface_names:
        return None

    checked = collect_connected_surface(
        start, get_block, surface_names, maximum_size
    )
    if checked is None:
        return None
    for pos in checked:
        if not is_support(get_block(_offset(pos, dy=-1)), portal_identifier):
            return None

        for dx, dz in HORIZONTAL:
            neighbor = _offset(pos, dx=dx, dz=dz)
            neighbor_name = block_name(get_block(neighbor))
            if neighbor_name in surface_names:
                continue
            if not is_edge(get_block(neighbor)):
                return None
            if not is_decoration(get_block(_offset(neighbor, dy=1))):
                return None

    if len(checked) < minimum_size:
        return None
    return checked


def collect_connected_surface(
    start,
    get_block,
    surface_names,
    maximum_size=64,
):
    """Collect a bounded horizontal surface without validating its frame."""
    if block_name(get_block(start)) not in surface_names:
        return None
    checked = set()
    queued = set((start,))
    queue = [start]
    while queue:
        pos = queue.pop()
        queued.discard(pos)
        if pos in checked:
            continue
        checked.add(pos)
        if len(checked) > maximum_size:
            return None
        for dx, dz in HORIZONTAL:
            neighbor = _offset(pos, dx=dx, dz=dz)
            if (
                block_name(get_block(neighbor)) in surface_names
                and neighbor not in checked
                and neighbor not in queued
            ):
                queue.append(neighbor)
                queued.add(neighbor)
    return sorted(checked)


def collect_portal(
    start,
    get_block,
    portal_identifier,
    minimum_size=1,
    maximum_size=64,
):
    return collect_enclosed_surface(
        start,
        get_block,
        set((portal_identifier,)),
        portal_identifier,
        minimum_size,
        maximum_size,
    )


def collect_stable_portal(
    start,
    get_block,
    portal_identifier,
    minimum_size=1,
    maximum_size=64,
):
    """Validate an active portal without requiring its activation flowers."""
    surface_names = set((portal_identifier,))
    checked = collect_connected_surface(
        start, get_block, surface_names, maximum_size
    )
    if checked is None:
        return None
    for pos in checked:
        if not is_support(get_block(_offset(pos, dy=-1)), portal_identifier):
            return None
        for dx, dz in HORIZONTAL:
            neighbor = _offset(pos, dx=dx, dz=dz)
            if block_name(get_block(neighbor)) in surface_names:
                continue
            if not is_edge(get_block(neighbor)):
                return None
    if len(checked) < minimum_size:
        return None
    return checked


def exit_edges(surface, get_block):
    """Return deterministic frame cells that can support a portal exit."""
    surface_set = set(surface or ())
    candidates = set()
    for pos in surface_set:
        for dx, dz in HORIZONTAL:
            edge = _offset(pos, dx=dx, dz=dz)
            if edge in surface_set:
                continue
            if is_edge(get_block(edge)):
                candidates.add(edge)
    return sorted(
        candidates,
        key=lambda value: (value[0], value[2], value[1]),
    )


def is_exit_passable(block):
    """Return whether a player's body may safely occupy this block."""
    name = block_name(block)
    return bool(name in EXIT_AIR_BLOCKS or is_decoration(block))


def find_exit(surface, get_block, portal_identifier):
    """Find an edge with passable blocks at both feet and head height."""
    del portal_identifier
    for edge in exit_edges(surface, get_block):
        feet = _offset(edge, dy=1)
        head = _offset(edge, dy=2)
        if (
            is_exit_passable(get_block(feet))
            and is_exit_passable(get_block(head))
        ):
            return (edge[0] + 0.5, edge[1] + 1.0, edge[2] + 0.5)
    return None


def player_position_from_foot(foot_position):
    """Convert an internal foot position to the ModSDK player position."""
    if foot_position is None:
        return None
    return (
        float(foot_position[0]),
        float(foot_position[1]) + PLAYER_POSITION_HEIGHT,
        float(foot_position[2]),
    )


def player_foot_from_position(player_position):
    """Convert a ModSDK player position to the internal foot position."""
    if player_position is None:
        return None
    return (
        float(player_position[0]),
        float(player_position[1]) - PLAYER_POSITION_HEIGHT,
        float(player_position[2]),
    )


def client_render_chunk_sample_positions(
    destination_exit,
    chunk_radius=PORTAL_BACKGROUND_PRELOAD_CHUNK_RADIUS,
    chunk_size=16,
):
    """Return center probes for chunks surrounding the portal destination."""
    if destination_exit is None:
        return []
    try:
        radius = max(0, int(chunk_radius))
        size = int(chunk_size)
        if size <= 0:
            return []
        block_x = int(math.floor(float(destination_exit[0])))
        block_z = int(math.floor(float(destination_exit[2])))
    except (TypeError, ValueError, IndexError):
        return []
    center_x = (block_x // size) * size + size // 2
    center_z = (block_z // size) * size + size // 2
    offsets = [
        (offset_x, offset_z)
        for offset_x in range(-radius, radius + 1)
        for offset_z in range(-radius, radius + 1)
    ]
    offsets.sort(
        key=lambda offset: (
            max(abs(offset[0]), abs(offset[1])),
            abs(offset[0]) + abs(offset[1]),
            offset[0],
            offset[1],
        )
    )
    return [
        (center_x + offset_x * size, center_z + offset_z * size)
        for offset_x, offset_z in offsets
    ]


def background_preload_chunk_positions(
    destination_exit,
    view_yaw=0.0,
    chunk_radius=PORTAL_BACKGROUND_PRELOAD_CHUNK_RADIUS,
    exclude_radius=PORTAL_SERVER_SAFE_CHUNK_RADIUS,
    chunk_size=16,
):
    """Return outer chunk coordinates ordered front-to-back by ring."""
    if destination_exit is None:
        return []
    try:
        radius = max(0, int(chunk_radius))
        excluded = max(-1, int(exclude_radius))
        size = int(chunk_size)
        yaw = math.radians(float(view_yaw))
        if size <= 0 or radius <= excluded:
            return []
        block_x = int(math.floor(float(destination_exit[0])))
        block_z = int(math.floor(float(destination_exit[2])))
    except (TypeError, ValueError, IndexError):
        return []
    center_chunk_x = block_x // size
    center_chunk_z = block_z // size
    look_x = -math.sin(yaw)
    look_z = math.cos(yaw)
    offsets = [
        (offset_x, offset_z)
        for offset_x in range(-radius, radius + 1)
        for offset_z in range(-radius, radius + 1)
        if max(abs(offset_x), abs(offset_z)) > excluded
    ]

    def priority(offset):
        offset_x, offset_z = offset
        ring = max(abs(offset_x), abs(offset_z))
        forward = offset_x * look_x + offset_z * look_z
        cross = offset_x * look_z - offset_z * look_x
        return (
            ring,
            round(-forward, 12),
            round(abs(cross), 12),
            abs(offset_x) + abs(offset_z),
            offset_x,
            offset_z,
        )

    offsets.sort(key=priority)
    return [
        (center_chunk_x + offset_x, center_chunk_z + offset_z)
        for offset_x, offset_z in offsets
    ]


def chunk_block_bounds(
    chunk_position,
    min_y=0,
    max_y=255,
    chunk_size=16,
):
    """Return inclusive block bounds for one chunk."""
    try:
        chunk_x = int(chunk_position[0])
        chunk_z = int(chunk_position[1])
        size = int(chunk_size)
        low_y = int(min_y)
        high_y = int(max_y)
    except (TypeError, ValueError, IndexError):
        return None
    if size <= 0 or high_y < low_y:
        return None
    minimum = (chunk_x * size, low_y, chunk_z * size)
    maximum = (
        minimum[0] + size - 1,
        high_y,
        minimum[2] + size - 1,
    )
    return (minimum, maximum)


def client_render_probe_batch(positions, start_index, max_probes):
    """Return one bounded probe batch and the cursor for the next tick."""
    try:
        items = list(positions or ())
        index = max(0, int(start_index))
        limit = max(1, int(max_probes))
    except (TypeError, ValueError):
        return ([], 0, True)
    if not items:
        return ([], 0, True)
    if index >= len(items):
        index = 0
    end_index = min(len(items), index + limit)
    pass_complete = end_index >= len(items)
    return (
        items[index:end_index],
        0 if pass_complete else end_index,
        pass_complete,
    )


def client_required_chunk_positions(
    destination_exit,
    chunk_radius=PORTAL_CLIENT_READY_CHUNK_RADIUS,
    chunk_size=16,
):
    """Return chunk coordinates required before the client-ready ACK."""
    if destination_exit is None:
        return []
    try:
        radius = max(0, int(chunk_radius))
        size = int(chunk_size)
        if size <= 0:
            return []
        block_x = int(math.floor(float(destination_exit[0])))
        block_z = int(math.floor(float(destination_exit[2])))
    except (TypeError, ValueError, IndexError):
        return []
    center_chunk_x = block_x // size
    center_chunk_z = block_z // size
    return [
        (center_chunk_x + offset_x, center_chunk_z + offset_z)
        for offset_x in range(-radius, radius + 1)
        for offset_z in range(-radius, radius + 1)
    ]


def client_required_chunks_loaded(required_chunks, loaded_chunks):
    """Return whether every required target chunk emitted a client event."""
    required = set(required_chunks or ())
    loaded = set(loaded_chunks or ())
    return bool(required and required.issubset(loaded))


def _client_top_height_ready(top_height):
    try:
        value = int(top_height)
    except (TypeError, ValueError):
        return False
    # NetEase exposes 32767 while the client has no LevelChunk for a column.
    return 0 <= value < 32767


def _client_support_name(support_block):
    if isinstance(support_block, dict):
        return support_block.get("name", "")
    if isinstance(support_block, (tuple, list)):
        return support_block[0] if support_block else ""
    return support_block


def client_destination_anchor_ready(
    player_foot_position,
    destination_exit,
    support_block,
    max_distance=4.0,
):
    """Return whether the player arrived and the exit support is readable."""
    if (
        player_foot_position is None
        or destination_exit is None
        or support_block is None
    ):
        return False
    try:
        distance_sq = sum(
            (
                float(player_foot_position[index])
                - float(destination_exit[index])
            )
            ** 2
            for index in range(3)
        )
        if distance_sq > float(max_distance) ** 2:
            return False
    except (TypeError, ValueError, IndexError):
        return False
    support_name = _client_support_name(support_block)
    return bool(support_name and support_name not in EXIT_AIR_BLOCKS)


def client_destination_render_ready(
    player_foot_position,
    destination_exit,
    top_height,
    support_block,
    surrounding_top_heights,
    max_distance=4.0,
):
    """Return whether the client can render and stand at the portal exit."""
    if top_height is None or not surrounding_top_heights:
        return False
    if not client_destination_anchor_ready(
        player_foot_position,
        destination_exit,
        support_block,
        max_distance,
    ):
        return False
    try:
        if not _client_top_height_ready(top_height):
            return False
    except (TypeError, ValueError):
        return False
    if not all(
        _client_top_height_ready(height)
        for height in surrounding_top_heights
    ):
        return False
    return True
