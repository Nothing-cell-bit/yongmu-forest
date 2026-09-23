# -*- coding: utf-8 -*-
"""Pure, Python 2.7-compatible logic for source-faithful magic maps."""

import base64
import math
import struct
import zlib

import TwilightBossSlice.biome_catalog as biome_catalog
import TwilightBossSlice.maze_map_logic as maze_map_logic


MAP_SIZE_BLOCKS = 2048
MAP_HALF_SIZE = MAP_SIZE_BLOCKS // 2
DISCOVERY_RADIUS = 512
MAP_GRID_SIZE = 128
MAP_CELL_BLOCKS = MAP_SIZE_BLOCKS // MAP_GRID_SIZE
MAP_OFF_LIMIT_BLOCKS = MAP_CELL_BLOCKS * 320
EXTRA_ID_PREFIX = "tfmm:v1:"
EXTRA_ID_V2_PREFIX = "tfmm:v2:"
EXTRA_ID_V3_PREFIX = "tfmm:v3:"
SNAPSHOT_SCHEMA_VERSION = 3
UNKNOWN_BIOME_KEY = "unknown"
MAGIC_MAP_RULESET = "twilightforest:1.20.1-4.3.2508"


def resolve_canvas_size(reported_size, grid_size=MAP_GRID_SIZE):
    """Return a drawable canvas extent for a fixed-resolution map grid.

    Native HUD controls can report a transient 0x0 or 1x1 size before their
    JSON layout has settled.  A map canvas must reserve at least one UI unit
    per grid cell or every run and marker collapses into its top-left corner.
    """
    try:
        grid_size = max(1.0, float(grid_size))
        width = float(reported_size[0])
        height = float(reported_size[1])
    except (IndexError, TypeError, ValueError):
        return (grid_size, grid_size)
    return (
        max(grid_size, width),
        max(grid_size, height),
    )


def select_held_item(
    carried,
    offhand,
    predicate,
    preferred_item=None,
):
    """Return the selected hand and item using the client's main-hand priority."""
    candidates = (("carried", carried), ("offhand", offhand))
    if preferred_item is not None:
        for hand, item in candidates:
            if item == preferred_item and predicate(item):
                return hand, item
    for hand, item in candidates:
        if predicate(item):
            return hand, item
    return None, None


def held_map_transition(previous_state, held, map_id=None):
    """Describe a held-map transition, including swaps without an empty hand."""
    held = bool(held)
    current_map_id = None
    if held and map_id is not None:
        current_map_id = (str(map_id) if maze_map_logic.decode_identity(map_id) is not None
                          else int(map_id))
    has_previous = previous_state is not None
    previous_held = False
    previous_map_id = None
    if isinstance(previous_state, (list, tuple)) and len(previous_state) == 2:
        previous_held = bool(previous_state[0])
        previous_map_id = previous_state[1]
    elif isinstance(previous_state, bool):
        # Accept in-memory state left by an older hot-reloaded server script.
        previous_held = previous_state

    current_state = (held, current_map_id)
    held_changed = not has_previous or previous_held != held
    map_changed = bool(
        held
        and has_previous
        and previous_held
        and previous_map_id != current_map_id
    )
    snapshot_needed = bool(
        held
        and (
            not has_previous
            or not previous_held
            or previous_map_id != current_map_id
        )
    )
    return {
        "state": current_state,
        "heldChanged": held_changed,
        "mapChanged": map_changed,
        "snapshotNeeded": snapshot_needed,
    }


def clone_magic_map_stack(source, blank_count):
    """Clone a filled magic map while preserving its shared map identity."""
    if not isinstance(source, dict):
        raise ValueError("magic map clone source must be an item dictionary")
    if (decode_map_identity(source.get("extraId")) is None
            and maze_map_logic.decode_identity(source.get("extraId")) is None):
        raise ValueError("magic map clone source has no valid identity")
    blank_count = int(blank_count)
    if blank_count < 1 or blank_count > 63:
        raise ValueError("magic map clone count is out of range")
    result = dict(source)
    result["count"] = blank_count + 1
    return result


def player_marker_direction(yaw, state="inside"):
    """Return the image-sprite direction for a tracked map player."""
    if state in ("off_map", "off_limits"):
        return "off_map"
    directions = ("south", "west", "north", "east")
    direction = int((float(yaw) + 45.0) // 90.0) % 4
    return directions[direction]


def player_marker_text(yaw, state="inside"):
    """Return the legacy text marker used by older full-screen layouts."""
    direction = player_marker_direction(yaw, state)
    return {
        "south": "v",
        "west": "<",
        "north": "^",
        "east": ">",
        "off_map": "o",
        None: "",
    }[direction]


def map_marker_position(
    block_x,
    block_z,
    bounds,
    canvas_width,
    canvas_height,
    edge_padding=0,
):
    """Project a marker and classify vanilla-style map tracking state."""
    try:
        min_x = float(bounds[0])
        min_z = float(bounds[1])
        max_x = float(bounds[2])
        max_z = float(bounds[3])
        width = max_x - min_x + 1.0
        height = max_z - min_z + 1.0
        canvas_width = max(1.0, float(canvas_width))
        canvas_height = max(1.0, float(canvas_height))
        block_x = float(block_x)
        block_z = float(block_z)
        padding = max(0.0, float(edge_padding))
    except (IndexError, TypeError, ValueError):
        return None
    if width <= 0.0 or height <= 0.0:
        return None
    inside = (
        min_x <= block_x <= max_x
        and min_z <= block_z <= max_z
    )
    center_x = min_x + width / 2.0
    center_z = min_z + height / 2.0
    if inside:
        state = "inside"
    elif (
        abs(block_x - center_x) >= MAP_OFF_LIMIT_BLOCKS
        or abs(block_z - center_z) >= MAP_OFF_LIMIT_BLOCKS
    ):
        state = "off_limits"
    else:
        state = "off_map"
    # Keep the same north-west to south-east row-major plane used when biome
    # samples and landmark positions are persisted.  The native HUD does not
    # add another map-space rotation of its own.
    pixel_x = (block_x - min_x) * canvas_width / width
    pixel_z = (block_z - min_z) * canvas_height / height
    max_pixel_x = max(padding, canvas_width - padding)
    max_pixel_z = max(padding, canvas_height - padding)
    return (
        max(padding, min(max_pixel_x, pixel_x)),
        max(padding, min(max_pixel_z, pixel_z)),
        state,
    )
MAX_SNAPSHOT_LANDMARKS = 128
_BASE_TWILIGHT_BIOME_PALETTE = (
    None,
    "forest",
    "dense_forest",
    "oak_savannah",
    "mushroom_forest",
    "firefly_forest",
    "stream",
    "dense_mushroom_forest",
    "lake",
    "enchanted_forest",
    "clearing",
    "spooky_forest",
    UNKNOWN_BIOME_KEY,
)
TWILIGHT_BIOME_PALETTE = _BASE_TWILIGHT_BIOME_PALETTE + tuple(
    biome_key
    for profile in biome_catalog.ACTIVE_TERRITORY_CONTENT_PROFILES
    for biome_key in (profile["companionBiome"], profile["coreBiome"])
)
TWILIGHT_BIOME_KEYS = frozenset(
    key for key in TWILIGHT_BIOME_PALETTE if key is not None
)
TWILIGHT_BIOME_INDEXES = dict(
    (key, index)
    for index, key in enumerate(TWILIGHT_BIOME_PALETTE)
    if key is not None
)
LOD_PRIORITY_BIOME_KEYS = ("stream",) + tuple(
    profile["coreBiome"]
    for profile in biome_catalog.ACTIVE_TERRITORY_CONTENT_PROFILES
) + tuple(
    profile["companionBiome"]
    for profile in biome_catalog.ACTIVE_TERRITORY_CONTENT_PROFILES
)

# TFMagicMapData's player-decoration packet is bounded before crossing the
# client boundary.  The HUD uses the same fixed-size pool.
MAX_SHARED_PLAYERS = 64

# TFMagicMapData's complete 1.20.1-4.3.2508 landmark icon table.
LANDMARK_ICONS = {
    "small_hill": "small_hill",
    "medium_hill": "medium_hill",
    "large_hill": "large_hill",
    "hedge_maze": "hedge_maze",
    "naga_courtyard": "naga_courtyard",
    "lich_tower": "lich_tower",
    "ice_tower": "ice_tower",
    "quest_grove": "quest_grove",
    "hydra_lair": "hydra_lair",
    "labyrinth": "labyrinth",
    "dark_tower": "dark_tower",
    "knight_stronghold": "knight_stronghold",
    "yeti_cave": "yeti_cave",
    "troll_cave": "troll_cave",
    "final_castle": "final_castle",
}


def _java_round(value):
    return int(math.floor(float(value) + 0.5))


def map_center_coordinate(coordinate):
    """Match EmptyMagicMapItem's 2048-block center alignment."""
    region = _java_round(
        (float(coordinate) - MAP_HALF_SIZE) / float(MAP_SIZE_BLOCKS)
    )
    return region * MAP_SIZE_BLOCKS + MAP_HALF_SIZE


def map_center(block_x, block_z):
    return (
        map_center_coordinate(block_x),
        map_center_coordinate(block_z),
    )


def map_bounds(center_x, center_z):
    center_x = int(center_x)
    center_z = int(center_z)
    return (
        center_x - MAP_HALF_SIZE,
        center_z - MAP_HALF_SIZE,
        center_x + MAP_HALF_SIZE - 1,
        center_z + MAP_HALF_SIZE - 1,
    )


def is_inside_map(block_x, block_z, center_x, center_z):
    min_x, min_z, max_x, max_z = map_bounds(center_x, center_z)
    return (
        min_x <= int(block_x) <= max_x
        and min_z <= int(block_z) <= max_z
    )


def discovery_cell_samples(
    player_x,
    player_z,
    center_x,
    center_z,
    known_indexes=(),
    radius=DISCOVERY_RADIUS,
    max_samples=None,
):
    """Return a bounded batch of source-scale pixels in reveal range."""
    player_x = int(player_x)
    player_z = int(player_z)
    min_x, min_z, _, _ = map_bounds(center_x, center_z)
    known = set()
    for value in known_indexes or ():
        try:
            known.add(int(value))
        except (TypeError, ValueError):
            continue
    column_start, row_start, column_end, row_end = discovery_candidate_bounds(
        player_x,
        player_z,
        center_x,
        center_z,
        radius,
    )
    ranked_samples = []
    for row in range(row_start, row_end):
        block_z = min_z + row * MAP_CELL_BLOCKS
        for column in range(column_start, column_end):
            index = row * MAP_GRID_SIZE + column
            if index in known:
                continue
            block_x = (
                min_x + column * MAP_CELL_BLOCKS
            )
            if should_reveal_pixel(
                column,
                row,
                player_x,
                player_z,
                center_x,
                center_z,
                radius,
            ):
                dx = block_x - player_x
                dz = block_z - player_z
                ranked_samples.append(
                    (dx * dx + dz * dz, index, block_x, block_z)
                )
    ranked_samples.sort(key=lambda sample: (sample[0], sample[1]))
    samples = [
        (index, block_x, block_z)
        for _, index, block_x, block_z in ranked_samples
    ]
    if max_samples is not None:
        return samples[:max(0, int(max_samples))]
    return samples


def discovery_frontier_batch(
    candidates,
    known_indexes=(),
    cursor=0,
    max_samples=None,
):
    """Consume a bounded batch from a cached, distance-ranked frontier."""
    candidates = list(candidates or ())
    known = set()
    for value in known_indexes or ():
        try:
            known.add(int(value))
        except (TypeError, ValueError):
            continue
    try:
        cursor = max(0, min(len(candidates), int(cursor)))
    except (TypeError, ValueError):
        cursor = 0
    if max_samples is None:
        max_samples = len(candidates)
    try:
        max_samples = max(0, int(max_samples))
    except (TypeError, ValueError):
        max_samples = 0
    batch = []
    while cursor < len(candidates) and len(batch) < max_samples:
        sample = candidates[cursor]
        cursor += 1
        if not isinstance(sample, (list, tuple)) or len(sample) != 3:
            continue
        try:
            index = int(sample[0])
        except (TypeError, ValueError):
            continue
        if index in known:
            continue
        batch.append((index, sample[1], sample[2]))
    return batch, cursor


def discovery_candidate_bounds(
    player_x,
    player_z,
    center_x,
    center_z,
    radius=DISCOVERY_RADIUS,
):
    """Return the exclusive pixel bounds that can pass reveal filtering."""
    viewer_column = int(
        math.floor(
            (float(player_x) - float(center_x))
            / float(MAP_CELL_BLOCKS)
        )
    ) + MAP_GRID_SIZE // 2
    viewer_row = int(
        math.floor(
            (float(player_z) - float(center_z))
            / float(MAP_CELL_BLOCKS)
        )
    ) + MAP_GRID_SIZE // 2
    radius_pixels = max(0, int(radius) // MAP_CELL_BLOCKS)
    return (
        max(0, viewer_column - radius_pixels + 1),
        max(0, viewer_row - radius_pixels - 1),
        min(MAP_GRID_SIZE, viewer_column + radius_pixels),
        min(MAP_GRID_SIZE, viewer_row + radius_pixels),
    )


def should_reveal_pixel(
    column,
    row,
    player_x,
    player_z,
    center_x,
    center_z,
    radius=DISCOVERY_RADIUS,
):
    """Match the original map's circular reveal and checker-fuzzy rim."""
    column = int(column)
    row = int(row)
    if not (
        0 <= column < MAP_GRID_SIZE
        and 0 <= row < MAP_GRID_SIZE
    ):
        return False
    viewer_column = int(
        math.floor(
            (float(player_x) - float(center_x))
            / float(MAP_CELL_BLOCKS)
        )
    ) + MAP_GRID_SIZE // 2
    viewer_row = int(
        math.floor(
            (float(player_z) - float(center_z))
            / float(MAP_CELL_BLOCKS)
        )
    ) + MAP_GRID_SIZE // 2
    radius_pixels = max(0, int(radius) // MAP_CELL_BLOCKS)
    if radius_pixels <= 0:
        return False
    if not (
        viewer_column - radius_pixels + 1
        <= column
        < viewer_column + radius_pixels
        and viewer_row - radius_pixels - 1
        <= row
        < viewer_row + radius_pixels
    ):
        return False
    dx = column - viewer_column
    dz = row - viewer_row
    distance_squared = dx * dx + dz * dz
    if distance_squared >= radius_pixels * radius_pixels:
        return False
    solid_radius = max(0, radius_pixels - 2)
    if distance_squared <= solid_radius * solid_radius:
        return True
    return (column + row) & 1 == 1


def normalize_biome_cells(persisted):
    """Validate persisted cells and return a compact canonical dictionary."""
    result = {}
    if not isinstance(persisted, dict):
        return result
    max_index = MAP_GRID_SIZE * MAP_GRID_SIZE
    for raw_index, raw_key in persisted.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        key = str(raw_key)
        if (
            0 <= index < max_index
            and key in TWILIGHT_BIOME_KEYS
        ):
            result[str(index)] = key
    return result


def biome_rectangles(cells, grid_size=MAP_GRID_SIZE):
    """Merge explored cells into solid upstream-oriented rectangles.

    Horizontal runs with the same span and biome are extended through
    adjacent rows.  This removes the one-row stripe controls that otherwise
    leave visible seams on a scaled held map and reduces UI control count
    while preserving every source pixel.
    """
    try:
        grid_size = int(grid_size)
    except (TypeError, ValueError):
        return []
    if grid_size <= 0 or not isinstance(cells, dict):
        return []

    normalized = {}
    max_index = grid_size * grid_size
    for raw_index, raw_key in cells.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        biome_key = str(raw_key)
        if 0 <= index < max_index and biome_key in TWILIGHT_BIOME_KEYS:
            normalized[index] = biome_key

    active = {}
    source_rectangles = []
    for row in range(grid_size):
        row_signatures = set()
        column = 0
        while column < grid_size:
            biome_key = normalized.get(row * grid_size + column)
            if biome_key is None:
                column += 1
                continue
            run_end = column + 1
            while (
                run_end < grid_size
                and normalized.get(row * grid_size + run_end) == biome_key
            ):
                run_end += 1
            signature = (column, run_end, biome_key)
            row_signatures.add(signature)
            if signature in active:
                active[signature][2] = row + 1
            else:
                active[signature] = [
                    row,
                    column,
                    row + 1,
                    run_end,
                    biome_key,
                ]
            column = run_end

        for signature in list(active):
            if signature not in row_signatures:
                source_rectangles.append(active.pop(signature))

    source_rectangles.extend(active.values())
    rectangles = list(source_rectangles)
    rectangles.sort(key=lambda rectangle: tuple(rectangle[:4]))
    return rectangles


def biome_rectangle_changes(
    previous_rectangles,
    cells,
    grid_size=MAP_GRID_SIZE,
):
    """Diff exact biome rectangles by identity instead of list position.

    A newly explored rectangle near the start of row-major order must not make
    every later HUD control look changed.  Rectangle tuples are stable visual
    identities, so unchanged regions retain their controls regardless of the
    order in which new regions are discovered.
    """
    current = biome_rectangles(cells, grid_size)
    previous_by_key = {}
    for rectangle in previous_rectangles or ():
        if not isinstance(rectangle, (list, tuple)) or len(rectangle) != 5:
            continue
        previous_by_key[tuple(rectangle)] = rectangle
    current_keys = set(tuple(rectangle) for rectangle in current)
    added = [
        rectangle
        for rectangle in current
        if tuple(rectangle) not in previous_by_key
    ]
    removed = [
        rectangle
        for key, rectangle in previous_by_key.items()
        if key not in current_keys
    ]
    removed.sort(key=lambda rectangle: tuple(rectangle[:4]))
    return current, added, removed


def budgeted_biome_rectangles(
    cells,
    grid_size=MAP_GRID_SIZE,
    max_rectangles=None,
):
    """Keep the whole explored extent inside a fixed HUD control budget.

    Exact source pixels are used whenever they fit.  Fragmented maps that
    exceed the native HUD pool are reduced at the smallest power-of-two tile
    size that fits, with each tile taking its most common explored biome.
    This trades a small amount of color detail for complete map coverage
    instead of silently dropping every rectangle after the pool limit.
    """
    rectangles = biome_rectangles(cells, grid_size)
    if max_rectangles is None:
        return rectangles
    try:
        grid_size = int(grid_size)
        max_rectangles = max(0, int(max_rectangles))
    except (TypeError, ValueError):
        return []
    if len(rectangles) <= max_rectangles:
        return rectangles
    if grid_size <= 0 or max_rectangles <= 0:
        return []

    normalized = {}
    max_index = grid_size * grid_size
    for raw_index, raw_key in cells.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        biome_key = str(raw_key)
        if 0 <= index < max_index and biome_key in TWILIGHT_BIOME_KEYS:
            normalized[index] = biome_key

    tile_size = 2
    while tile_size <= grid_size:
        coarse_size = (grid_size + tile_size - 1) // tile_size
        coarse_cells = {}
        for coarse_row in range(coarse_size):
            row_start = coarse_row * tile_size
            row_end = min(grid_size, row_start + tile_size)
            for coarse_column in range(coarse_size):
                column_start = coarse_column * tile_size
                column_end = min(grid_size, column_start + tile_size)
                biome_counts = {}
                for row in range(row_start, row_end):
                    for column in range(column_start, column_end):
                        biome_key = normalized.get(row * grid_size + column)
                        if biome_key is not None:
                            biome_counts[biome_key] = (
                                biome_counts.get(biome_key, 0) + 1
                            )
                if not biome_counts:
                    continue
                priority_keys = [
                    key
                    for key in LOD_PRIORITY_BIOME_KEYS
                    if key in biome_counts
                ]
                if priority_keys:
                    biome_key = priority_keys[0]
                else:
                    biome_key = min(
                        biome_counts,
                        key=lambda key: (
                            -biome_counts[key],
                            TWILIGHT_BIOME_INDEXES.get(
                                key,
                                len(TWILIGHT_BIOME_PALETTE),
                            ),
                            key,
                        ),
                    )
                coarse_cells[
                    coarse_row * coarse_size + coarse_column
                ] = biome_key

        coarse_rectangles = biome_rectangles(coarse_cells, coarse_size)
        scaled = [
            [
                row_start * tile_size,
                column_start * tile_size,
                min(grid_size, row_end * tile_size),
                min(grid_size, column_end * tile_size),
                biome_key,
            ]
            for (
                row_start,
                column_start,
                row_end,
                column_end,
                biome_key,
            ) in coarse_rectangles
        ]
        if len(scaled) <= max_rectangles:
            return scaled
        if tile_size == grid_size:
            break
        tile_size = min(grid_size, tile_size * 2)
    return []


def rectangle_pool_delta(
    previous_rectangles,
    cells,
    grid_size=MAP_GRID_SIZE,
    max_slots=None,
):
    """Return only changed rectangle slots for a fixed native-HUD pool."""
    current = tuple(
        budgeted_biome_rectangles(
            cells,
            grid_size,
            max_slots,
        )
    )
    previous = tuple(previous_rectangles or ())
    updates = []
    for index, rectangle in enumerate(current):
        if index >= len(previous) or previous[index] != rectangle:
            updates.append((index, rectangle))
    hidden = list(range(len(current), len(previous)))
    return current, updates, hidden


def encode_biome_pixels(persisted):
    """Pack 5-bit palette pixels, compress, and encode for ExtraData.

    The ``z5:`` discriminator keeps the original nibble decoder available for
    maps written before Dark Forest expanded the stable palette past 16 slots.
    """
    cells = normalize_biome_cells(persisted)
    total = MAP_GRID_SIZE * MAP_GRID_SIZE
    packed = []
    accumulator = 0
    bit_count = 0
    for index in range(total):
        value = TWILIGHT_BIOME_INDEXES.get(cells.get(str(index)), 0)
        accumulator |= int(value) << bit_count
        bit_count += 5
        while bit_count >= 8:
            packed.append(accumulator & 255)
            accumulator >>= 8
            bit_count -= 8
    if bit_count:
        packed.append(accumulator & 255)
    raw = struct.pack("%dB" % len(packed), *packed)
    encoded = base64.b64encode(zlib.compress(raw, 9))
    if not isinstance(encoded, str):
        encoded = encoded.decode("ascii")
    return "z5:" + encoded


def decode_biome_pixels(encoded):
    """Decode v3 5-bit storage or legacy v2 nibbles atomically."""
    if not isinstance(encoded, str):
        return {}
    if encoded.startswith("z5:"):
        try:
            raw = zlib.decompress(base64.b64decode(encoded[3:]))
        except (TypeError, ValueError, zlib.error):
            return {}
        total = MAP_GRID_SIZE * MAP_GRID_SIZE
        expected = (total * 5 + 7) // 8
        if len(raw) != expected:
            return {}
        values = bytearray(raw)
        result = {}
        accumulator = 0
        bit_count = 0
        raw_index = 0
        for pixel_index in range(total):
            while bit_count < 5:
                accumulator |= int(values[raw_index]) << bit_count
                raw_index += 1
                bit_count += 8
            palette_index = accumulator & 31
            accumulator >>= 5
            bit_count -= 5
            if palette_index == 0:
                continue
            if palette_index >= len(TWILIGHT_BIOME_PALETTE):
                return {}
            result[str(pixel_index)] = TWILIGHT_BIOME_PALETTE[palette_index]
        return result
    try:
        raw = base64.b64decode(encoded)
    except (TypeError, ValueError):
        return {}
    expected = (MAP_GRID_SIZE * MAP_GRID_SIZE + 1) // 2
    if len(raw) != expected:
        return {}
    result = {}
    for packed_index, value in enumerate(bytearray(raw)):
        for offset, palette_index in (
            (0, value & 15),
            (1, (value >> 4) & 15),
        ):
            pixel_index = packed_index * 2 + offset
            if (
                pixel_index >= MAP_GRID_SIZE * MAP_GRID_SIZE
                or palette_index == 0
            ):
                continue
            if palette_index >= len(TWILIGHT_BIOME_PALETTE):
                return {}
            result[str(pixel_index)] = TWILIGHT_BIOME_PALETTE[
                palette_index
            ]
    return result


def biome_row_runs(persisted):
    """Encode explored pixels as compact [row, start, end, biome] runs."""
    cells = normalize_biome_cells(persisted)
    runs = []
    for row in range(MAP_GRID_SIZE):
        column = 0
        while column < MAP_GRID_SIZE:
            biome_key = cells.get(str(row * MAP_GRID_SIZE + column))
            if biome_key is None:
                column += 1
                continue
            run_end = column + 1
            while (
                run_end < MAP_GRID_SIZE
                and cells.get(str(row * MAP_GRID_SIZE + run_end))
                == biome_key
            ):
                run_end += 1
            runs.append([row, column, run_end, biome_key])
            column = run_end
    return runs


def snapshot_biome_cells(snapshot):
    """Decode validated biome cells from snapshot or delta wire fields."""
    if not isinstance(snapshot, dict):
        return {}
    try:
        grid_size = int(snapshot.get("gridSize", MAP_GRID_SIZE))
    except (TypeError, ValueError):
        return {}
    if grid_size != MAP_GRID_SIZE:
        return {}
    cells = {}
    for run in snapshot.get("biomeRuns", ()):
        if not isinstance(run, (list, tuple)) or len(run) != 4:
            continue
        try:
            row = int(run[0])
            start = int(run[1])
            end = int(run[2])
        except (TypeError, ValueError):
            continue
        biome_key = str(run[3])
        if (
            biome_key not in TWILIGHT_BIOME_KEYS
            or not 0 <= row < grid_size
            or not 0 <= start < end <= grid_size
        ):
            continue
        for column in range(start, end):
            cells[str(row * grid_size + column)] = biome_key
    cells.update(normalize_biome_cells(snapshot.get("biomeCells")))
    return cells


def merge_map_delta(snapshot, delta):
    """Merge a wire delta without discarding previously explored pixels."""
    current = dict(snapshot) if isinstance(snapshot, dict) else {}
    if not isinstance(delta, dict):
        return current
    current_map_id = current.get("mapId")
    delta_map_id = delta.get("mapId", current_map_id)
    if current_map_id is not None and delta_map_id != current_map_id:
        return current
    cells = snapshot_biome_cells(current)
    cells.update(snapshot_biome_cells(delta))
    current.update(delta)
    current["gridSize"] = MAP_GRID_SIZE
    current["biomeRuns"] = biome_row_runs(cells)
    current.pop("biomeCells", None)
    return current


def _is_canonical_center(value):
    return (int(value) - MAP_HALF_SIZE) % MAP_SIZE_BLOCKS == 0


def encode_extra_id(center_x, center_z, map_id=None):
    center_x = int(center_x)
    center_z = int(center_z)
    if not (
        _is_canonical_center(center_x)
        and _is_canonical_center(center_z)
    ):
        raise ValueError("magic map center is not aligned")
    if map_id is None:
        return "%s%d:%d" % (EXTRA_ID_PREFIX, center_x, center_z)
    map_id = int(map_id)
    if map_id <= 0:
        raise ValueError("magic map id must be positive")
    return "%s%d:%d:%d" % (
        EXTRA_ID_V3_PREFIX,
        map_id,
        center_x,
        center_z,
    )


def decode_extra_id(extra_id):
    if not isinstance(extra_id, str) or not extra_id.startswith(
        EXTRA_ID_PREFIX
    ):
        return None
    if extra_id.strip() != extra_id:
        return None
    parts = extra_id[len(EXTRA_ID_PREFIX) :].split(":")
    if len(parts) != 2:
        return None
    try:
        center_x = int(parts[0])
        center_z = int(parts[1])
    except (TypeError, ValueError):
        return None
    if not (
        _is_canonical_center(center_x)
        and _is_canonical_center(center_z)
    ):
        return None
    if encode_extra_id(center_x, center_z) != extra_id:
        return None
    return center_x, center_z


def decode_map_identity(extra_id):
    """Return (map id, center x, center z), accepting legacy v1/v2 maps."""
    legacy = decode_extra_id(extra_id)
    if legacy is not None:
        return None, legacy[0], legacy[1]
    version = extra_id_version(extra_id)
    if version not in (2, 3):
        return None
    if extra_id.strip() != extra_id:
        return None
    prefix = (
        EXTRA_ID_V3_PREFIX
        if version == 3
        else EXTRA_ID_V2_PREFIX
    )
    parts = extra_id[len(prefix) :].split(":")
    if len(parts) != 3:
        return None
    try:
        map_id = int(parts[0])
        center_x = int(parts[1])
        center_z = int(parts[2])
    except (TypeError, ValueError):
        return None
    if (
        map_id <= 0
        or not _is_canonical_center(center_x)
        or not _is_canonical_center(center_z)
    ):
        return None
    canonical = "%s%d:%d:%d" % (
        prefix,
        map_id,
        center_x,
        center_z,
    )
    if canonical != extra_id:
        return None
    return map_id, center_x, center_z


def extra_id_version(extra_id):
    if not isinstance(extra_id, str):
        return None
    if extra_id.startswith(EXTRA_ID_PREFIX):
        return 1
    if extra_id.startswith(EXTRA_ID_V2_PREFIX):
        return 2
    if extra_id.startswith(EXTRA_ID_V3_PREFIX):
        return 3
    return None


def sector_key(center_x, center_z):
    return "%d,%d" % (int(center_x), int(center_z))


def landmark_key(kind, block_x, block_z):
    return "%s:%d,%d" % (str(kind), int(block_x), int(block_z))


def icon_for_landmark(kind):
    return LANDMARK_ICONS.get(str(kind))


def _clean_landmark(candidate):
    if not isinstance(candidate, dict):
        return None
    kind = str(candidate.get("kind", ""))
    icon = icon_for_landmark(kind)
    position = candidate.get("position")
    if icon is None or not isinstance(position, (list, tuple)):
        return None
    if len(position) != 2:
        return None
    try:
        block_x = int(position[0])
        block_z = int(position[1])
    except (TypeError, ValueError):
        return None
    return {
        "key": landmark_key(kind, block_x, block_z),
        "kind": kind,
        "position": [block_x, block_z],
        "icon": icon,
        "conquered": bool(candidate.get("conquered", False)),
    }


def discover_landmarks(
    candidates,
    player_x,
    player_z,
    center_x,
    center_z,
    radius=DISCOVERY_RADIUS,
):
    player_x = int(player_x)
    player_z = int(player_z)
    radius_squared = max(0, int(radius)) ** 2
    discovered = {}
    for candidate in candidates or ():
        cleaned = _clean_landmark(candidate)
        if cleaned is None:
            continue
        block_x, block_z = cleaned["position"]
        if not is_inside_map(block_x, block_z, center_x, center_z):
            continue
        dx = block_x - player_x
        dz = block_z - player_z
        if dx * dx + dz * dz > radius_squared:
            continue
        discovered[cleaned["key"]] = cleaned
    return sorted(
        discovered.values(),
        key=lambda entry: (
            (entry["position"][0] - player_x) ** 2
            + (entry["position"][1] - player_z) ** 2,
            entry["key"],
        ),
    )


def merge_landmarks(persisted, discovered):
    result = {}
    if isinstance(persisted, dict):
        for key, value in persisted.items():
            cleaned = _clean_landmark(value)
            if cleaned is not None and cleaned["key"] == str(key):
                result[cleaned["key"]] = {
                    "kind": cleaned["kind"],
                    "position": cleaned["position"],
                    "conquered": cleaned["conquered"],
                }
    for value in discovered or ():
        cleaned = _clean_landmark(value)
        if cleaned is not None:
            position = tuple(cleaned["position"])
            for existing_key in list(result):
                if existing_key == cleaned["key"]:
                    continue
                existing_position = result[existing_key].get("position")
                if tuple(existing_position or ()) == position:
                    result.pop(existing_key, None)
            result[cleaned["key"]] = {
                "kind": cleaned["kind"],
                "position": cleaned["position"],
                "conquered": cleaned["conquered"],
            }
    return result


def clean_map_players(players, limit=MAX_SHARED_PLAYERS):
    """Validate and deterministically order shared-map player markers."""
    cleaned = {}
    for candidate in players or ():
        if not isinstance(candidate, dict):
            continue
        player_id = str(candidate.get("id", ""))
        position = candidate.get("position")
        if not player_id or not isinstance(position, (list, tuple)):
            continue
        if len(position) != 2:
            continue
        try:
            block_x = int(position[0])
            block_z = int(position[1])
            yaw = float(candidate.get("yaw", 0.0))
        except (TypeError, ValueError):
            continue
        cleaned[player_id] = {
            "id": player_id,
            "position": [block_x, block_z],
            "yaw": yaw,
        }
    return [cleaned[key] for key in sorted(cleaned)[:max(0, int(limit))]]


def build_snapshot(
    center_x,
    center_z,
    player_x,
    player_z,
    dimension_id,
    persisted_landmarks,
    persisted_biomes=None,
    map_id=None,
    players=None,
):
    center_x = int(center_x)
    center_z = int(center_z)
    player_x = int(player_x)
    player_z = int(player_z)
    cleaned = merge_landmarks(persisted_landmarks, ())
    landmarks = []
    for key in sorted(cleaned):
        entry = _clean_landmark(cleaned[key])
        if entry is None:
            continue
        if not is_inside_map(
            entry["position"][0],
            entry["position"][1],
            center_x,
            center_z,
        ):
            continue
        packet_entry = dict(entry)
        packet_entry.pop("conquered", None)
        landmarks.append(packet_entry)
        if len(landmarks) >= MAX_SNAPSHOT_LANDMARKS:
            break
    snapshot = {
        "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
        "ruleset": MAGIC_MAP_RULESET,
        "dimensionId": int(dimension_id),
        "gridSize": MAP_GRID_SIZE,
        "cellBlocks": MAP_CELL_BLOCKS,
        "center": [center_x, center_z],
        "bounds": list(map_bounds(center_x, center_z)),
        "player": [player_x, player_z],
        "players": clean_map_players(players),
        "biomeRuns": biome_row_runs(persisted_biomes),
        "landmarks": landmarks,
    }
    if map_id is not None:
        snapshot["mapId"] = int(map_id)
    return snapshot
