# -*- coding: utf-8 -*-
"""Pure, Python 2.7-compatible logic for Twilight Forest ruin placement.

The numeric operations in this module deliberately reproduce Java's signed
integer overflow and java.util.Random behavior.  Keeping this module free of
ModSDK imports makes the landmark grid testable on a desktop Python runtime.
"""

import collections
import copy
import math
import threading


try:
    import TwilightBossSlice.entry_diagnostics as _entry_diagnostics
except ImportError:
    try:
        import entry_diagnostics as _entry_diagnostics
    except ImportError:
        _entry_diagnostics = None


JAVA_LONG_MASK = (1 << 64) - 1
JAVA_LONG_SIGN = 1 << 63
JAVA_RANDOM_MULTIPLIER = 0x5DEECE66D
JAVA_RANDOM_ADDEND = 0xB
JAVA_RANDOM_MASK = (1 << 48) - 1
FNV64_OFFSET_BASIS = 1469598103934665603
FNV64_PRIME = 1099511628211
SPLITMIX64_INCREMENT = 0x9E3779B97F4A7C15
SPLITMIX64_MULTIPLIER_A = 0xBF58476D1CE4E5B9
SPLITMIX64_MULTIPLIER_B = 0x94D049BB133111EB
LANDMARK_LAYOUT_CACHE_MAX = 512
_LANDMARK_LAYOUT_CACHE = {}
HOLLOW_TREE_CELL_CHUNKS = 2
HOLLOW_TREE_CELL_CHANCE_NUMERATOR = 4
HOLLOW_TREE_CELL_CHANCE_DENOMINATOR = 35


_SELECTION_CACHE_MISS = object()
WORLDGEN_SELECTION_CACHE_MAX = 512


class _SelectionCache(object):
    """Bounded FIFO of immutable pure results, shared by chunk workers.

    No terrain, biome queries, catalog records or ledger state may be stored
    here. Misses compute outside the lock; concurrent duplicate work is safe.
    Eviction affects cost only, never the deterministic selection result.
    """

    def __init__(self, limit):
        self._limit = max(1, int(limit))
        self._values = collections.OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            return self._values.get(key, _SELECTION_CACHE_MISS)

    def put(self, key, value):
        with self._lock:
            if key not in self._values:
                if len(self._values) >= self._limit:
                    self._values.popitem(last=False)
                self._values[key] = value


_LANDMARK_CENTER_CACHE = _SelectionCache(WORLDGEN_SELECTION_CACHE_MAX)
_LANDMARK_VARIETY_CACHE = _SelectionCache(WORLDGEN_SELECTION_CACHE_MAX)
_HOLLOW_TREE_CELL_CACHE = _SelectionCache(WORLDGEN_SELECTION_CACHE_MAX)

HOLLOW_HILL_KIND_DATA = {
    "small_hill": (1, 36, 48),
    "medium_hill": (2, 68, 80),
    "large_hill": (3, 100, 112),
}
# With the 4.3.2508 biome provider's base factor (2.5) and offset (-1.25),
# ordinary Twilight Forest terrain sits only about four blocks above its
# configured sea level (zero). Hollow-hill pieces are anchored at sea level.
HOLLOW_HILL_GROUND_ABOVE_SEA = 4
ROUTE_LANDMARK_KINDS = frozenset(
    ("labyrinth", "hydra_lair", "knight_stronghold", "dark_tower")
)
# The source biome stack gives every key landmark one companion biome in each
# cardinal landmark cell.  Keep the block offsets in this pure module so native
# feature rules, map discovery, locate/recovery, and tests cannot drift apart.
ROUTE_LANDMARK_GRID_BLOCKS = 256
ROUTE_LANDMARK_CARDINAL_OFFSETS = (
    (-ROUTE_LANDMARK_GRID_BLOCKS, 0),
    (0, -ROUTE_LANDMARK_GRID_BLOCKS),
    (0, ROUTE_LANDMARK_GRID_BLOCKS),
    (ROUTE_LANDMARK_GRID_BLOCKS, 0),
)
ROUTE_FIRST_GENERATION_SOURCES = frozenset(
    ("surface_feature",)
)


def _trace_worldgen(event, **fields):
    diagnostics = _entry_diagnostics
    if diagnostics is None:
        return False
    try:
        return bool(diagnostics.write_worldgen_event(event, **fields))
    except Exception:
        return False


def allows_automatic_route_placement(landmark_kind, generation_source):
    """Keep route megastructures out of already-generated chunks.

    Manual diagnostic placement bypasses discovery. This automatic-discovery
    gate deliberately leaves the center unreserved so a later native surface
    handoff can still win a race with ChunkLoadedServerEvent.
    """
    if str(landmark_kind) not in ROUTE_LANDMARK_KINDS:
        return True
    return str(generation_source) in ROUTE_FIRST_GENERATION_SOURCES


def hollow_hill_piece_depth(size):
    """Return the source bounding-box depth below the landmark sea level."""
    size = int(size)
    if size not in (1, 2, 3):
        raise ValueError("unsupported hollow hill size")
    # HollowHillStructure first offsets Y, then TFLandmark's centerBounds
    # adjustment shifts the component again. The resulting minima are
    # -5/-7/-9 for small/medium/large hills.
    return size * 2 + 3
HOLLOW_HILL_LOCAL_MONSTER_CAPS = {
    "small_hill": 12,
    "medium_hill": 20,
    "large_hill": 28,
}
# identifier, weight, minimum group size, maximum group size. These are the
# labelled monster spawn lists in the 4.3.2508 hollow-hill structure JSON.
HOLLOW_HILL_CONTROLLED_SPAWNS = {
    "small_hill": (
        ("minecraft:spider", 10, 4, 4),
        ("minecraft:zombie", 10, 4, 4),
        ("tf_slice:redcap", 10, 4, 4),
        ("tf_slice:swarm_spider", 10, 4, 4),
        ("tf_slice:kobold", 10, 4, 8),
    ),
    "medium_hill": (
        ("tf_slice:redcap", 10, 1, 2),
        ("tf_slice:redcap_sapper", 1, 1, 2),
        ("tf_slice:kobold", 10, 2, 4),
        ("minecraft:skeleton", 10, 2, 3),
        ("tf_slice:swarm_spider", 10, 2, 4),
        ("minecraft:spider", 10, 1, 3),
        ("minecraft:creeper", 10, 1, 2),
        ("tf_slice:fire_beetle", 5, 1, 1),
        ("tf_slice:slime_beetle", 5, 1, 1),
        ("minecraft:witch", 1, 1, 1),
    ),
    "large_hill": (
        ("tf_slice:redcap", 10, 2, 4),
        ("tf_slice:redcap_sapper", 2, 1, 2),
        ("minecraft:skeleton", 10, 2, 3),
        ("minecraft:cave_spider", 10, 1, 2),
        ("minecraft:creeper", 10, 1, 1),
        ("minecraft:enderman", 1, 1, 1),
        ("tf_slice:wraith", 2, 1, 2),
        ("tf_slice:fire_beetle", 10, 1, 2),
        ("tf_slice:slime_beetle", 10, 1, 2),
        ("tf_slice:pinch_beetle", 10, 1, 2),
        ("minecraft:witch", 1, 1, 1),
    ),
}
HOLLOW_HILL_CONTROLLED_MOBS = frozenset(
    entry[0]
    for entries in HOLLOW_HILL_CONTROLLED_SPAWNS.values()
    for entry in entries
)

# 4.3.2508 Lich Tower room-spawner weights.  Group ranges match the locked
# structure configuration while the service applies a mobile-safe tower cap.
LICH_TOWER_SPAWN_WEIGHTS = (
    ("minecraft:zombie", 10, (1, 2)),
    ("minecraft:skeleton", 10, (1, 2)),
    ("tf_slice:death_tome", 10, (2, 3)),
    ("minecraft:creeper", 1, (1, 1)),
    ("minecraft:enderman", 1, (1, 2)),
    ("minecraft:witch", 1, (1, 1)),
)
LICH_TOWER_CONTROLLED_MOBS = frozenset(
    entry[0] for entry in LICH_TOWER_SPAWN_WEIGHTS
)


def java_long(value):
    value &= JAVA_LONG_MASK
    if value & JAVA_LONG_SIGN:
        return value - (1 << 64)
    return value


def java_remainder(value, divisor):
    """Java's remainder keeps the dividend's sign."""
    return value - int(float(value) / float(divisor)) * divisor


def java_math_round(value):
    """Equivalent to Math.round(float) for the coordinate range we use."""
    return int(math.floor(float(value) + 0.5))


def _unsigned_mix64(value):
    """SplitMix64 finalizer with explicit unsigned 64-bit overflow."""
    value = (int(value) + SPLITMIX64_INCREMENT) & JAVA_LONG_MASK
    value = (
        (value ^ (value >> 30)) * SPLITMIX64_MULTIPLIER_A
    ) & JAVA_LONG_MASK
    value = (
        (value ^ (value >> 27)) * SPLITMIX64_MULTIPLIER_B
    ) & JAVA_LONG_MASK
    return (value ^ (value >> 31)) & JAVA_LONG_MASK


def _stable_text_hash(value):
    """FNV-1a hash that is stable across Python 2/3 and process restarts."""
    result = FNV64_OFFSET_BASIS
    for character in str(value):
        result ^= ord(character)
        result = (result * FNV64_PRIME) & JAVA_LONG_MASK
    return result


def landmark_stream_seed(
    world_seed,
    center_x,
    center_z,
    landmark_kind,
    stream_name,
    salt=0,
):
    """Derive an isolated deterministic RNG stream for one landmark."""
    value = int(world_seed) & JAVA_LONG_MASK
    parts = (
        int(center_x),
        int(center_z),
        _stable_text_hash(landmark_kind),
        _stable_text_hash(stream_name),
        int(salt),
    )
    for part in parts:
        value = _unsigned_mix64(value ^ (int(part) & JAVA_LONG_MASK))
    return java_long(value)


def landmark_stream_index(
    world_seed,
    center_x,
    center_z,
    landmark_kind,
    stream_name,
    bound,
    salt=0,
):
    """Select a stable bounded index without coupling independent systems."""
    if int(bound) <= 0:
        raise ValueError("bound must be positive")
    cache_key = None
    if str(stream_name) == "layout":
        cache_key = (
            int(world_seed),
            int(center_x),
            int(center_z),
            str(landmark_kind),
            str(stream_name),
            int(bound),
            int(salt),
        )
        if cache_key in _LANDMARK_LAYOUT_CACHE:
            return _LANDMARK_LAYOUT_CACHE[cache_key]
    seed = landmark_stream_seed(
        world_seed,
        center_x,
        center_z,
        landmark_kind,
        stream_name,
        salt,
    )
    selected = JavaRandom(seed).next_int(int(bound))
    if str(stream_name) == "layout":
        if len(_LANDMARK_LAYOUT_CACHE) >= LANDMARK_LAYOUT_CACHE_MAX:
            _LANDMARK_LAYOUT_CACHE.clear()
        _LANDMARK_LAYOUT_CACHE[cache_key] = selected
        _trace_worldgen(
            "worldgen.landmark.layout",
            worldSeed=int(world_seed),
            center=[int(center_x), int(center_z)],
            landmarkKind=str(landmark_kind),
            streamName=str(stream_name),
            bound=int(bound),
            salt=int(salt),
            selectedIndex=selected,
        )
    return selected


def weighted_variant_index(weights, roll):
    """Map one bounded roll to a variant index without float weights."""
    normalized = [max(0, int(weight)) for weight in weights]
    total = sum(normalized)
    if total <= 0:
        raise ValueError("variant weights must contain a positive value")
    remaining = int(roll) % total
    for index, weight in enumerate(normalized):
        if remaining < weight:
            return index
        remaining -= weight
    raise AssertionError("weighted variant selection fell through")


def hollow_tree_chunk_tile(
    chunk_x,
    chunk_z,
    world_seed,
    variant_count,
):
    """Select one chunk-local tile from a shared 2x2 hollow-tree cell.

    A 29x29 hollow oak crosses four native worldgen chunks. NetEase clips a
    structure feature to the chunk that invoked it, so every chunk in the
    cell must independently derive the same presence roll and variant. The
    4/35 per-cell roll preserves the source density of one tree per 35
    chunks: one accepted cell creates one tree across four chunks.
    """
    variant_count = int(variant_count)
    if variant_count <= 0:
        raise ValueError("variant_count must be positive")
    chunk_x = int(chunk_x)
    chunk_z = int(chunk_z)
    cell_chunk_x = (
        chunk_x // HOLLOW_TREE_CELL_CHUNKS
    ) * HOLLOW_TREE_CELL_CHUNKS
    cell_chunk_z = (
        chunk_z // HOLLOW_TREE_CELL_CHUNKS
    ) * HOLLOW_TREE_CELL_CHUNKS
    cache_key = (
        int(world_seed), cell_chunk_x, cell_chunk_z, variant_count,
        HOLLOW_TREE_CELL_CHANCE_NUMERATOR,
        HOLLOW_TREE_CELL_CHANCE_DENOMINATOR,
    )
    variant = _HOLLOW_TREE_CELL_CACHE.get(cache_key)
    if variant is _SELECTION_CACHE_MISS:
        variant = _hollow_tree_cell_variant(
            cell_chunk_x, cell_chunk_z, world_seed, variant_count,
        )
        _HOLLOW_TREE_CELL_CACHE.put(cache_key, variant)
    if variant is None:
        return None
    result = {
        "cellChunkX": cell_chunk_x,
        "cellChunkZ": cell_chunk_z,
        "tileX": chunk_x - cell_chunk_x,
        "tileZ": chunk_z - cell_chunk_z,
        "variant": variant,
    }
    _trace_worldgen(
        "worldgen.hollow_tree.tile",
        cellChunk=[cell_chunk_x, cell_chunk_z],
        chunk=[chunk_x, chunk_z],
        tile=[result["tileX"], result["tileZ"]],
        variant=variant,
    )
    return result


def _hollow_tree_cell_variant(cell_chunk_x, cell_chunk_z, world_seed, variant_count):
    center_x = cell_chunk_x * 16 + 16
    center_z = cell_chunk_z * 16 + 16
    presence = landmark_stream_index(
        world_seed, center_x, center_z, "hollow_tree", "presence",
        HOLLOW_TREE_CELL_CHANCE_DENOMINATOR,
    )
    if presence >= HOLLOW_TREE_CELL_CHANCE_NUMERATOR:
        return None
    return landmark_stream_index(
        world_seed, center_x, center_z, "hollow_tree", "variant", variant_count,
    )


def _surface_native_coordinate(value):
    value = int(value)
    return "%s%02d" % ("m" if value < 0 else "p", abs(value))


def surface_native_tile_reference(
    prefix,
    alignment,
    delta_x,
    delta_z,
):
    """Return the builder/runtime shared reference for one world-chunk tile."""
    center_mod_x, center_mod_z = (
        int(value) for value in str(alignment).split(",", 1)
    )
    reference = (
        "%s/mx%02d_mz%02d/x%s_z%s"
        % (
            str(prefix).rstrip("/"),
            center_mod_x,
            center_mod_z,
            _surface_native_coordinate(delta_x),
            _surface_native_coordinate(delta_z),
        )
    )
    _trace_worldgen(
        "worldgen.surface.tile",
        prefix=str(prefix).rstrip("/"),
        alignment=str(alignment),
        delta=[int(delta_x), int(delta_z)],
        reference=reference,
    )
    return reference


class JavaRandom(object):
    """Small java.util.Random implementation used by landmark selection."""

    def __init__(self, seed):
        self.seed = (int(seed) ^ JAVA_RANDOM_MULTIPLIER) & JAVA_RANDOM_MASK

    def next_bits(self, bits):
        self.seed = (
            self.seed * JAVA_RANDOM_MULTIPLIER + JAVA_RANDOM_ADDEND
        ) & JAVA_RANDOM_MASK
        return self.seed >> (48 - bits)

    def next_int(self, bound):
        if bound <= 0:
            raise ValueError("bound must be positive")
        if bound & (bound - 1) == 0:
            return (bound * self.next_bits(31)) >> 31
        while True:
            bits = self.next_bits(31)
            value = bits % bound
            if bits - value + (bound - 1) < (1 << 31):
                return value


def _terrain_noise_sample(seed, grid_x, grid_z):
    sample_seed = landmark_stream_seed(
        seed,
        grid_x,
        grid_z,
        "hollow_hill",
        "terrain_detail",
    )
    return (JavaRandom(sample_seed).next_int(2001) - 1000) / 1000.0


def hollow_hill_terrain_detail(
    seed,
    local_x,
    local_z,
    radius,
    amplitude=2,
):
    """Return smooth source-style hill variation that fades at the rim."""
    local_x = float(local_x)
    local_z = float(local_z)
    radius = max(1.0, float(radius))
    amplitude = max(0, int(amplitude))
    center = radius
    distance = math.sqrt(
        (local_x - center) ** 2 + (local_z - center) ** 2
    )
    if distance >= radius or amplitude == 0:
        return 0

    cell_size = 8.0
    grid_x = int(math.floor(local_x / cell_size))
    grid_z = int(math.floor(local_z / cell_size))
    fraction_x = (local_x / cell_size) - grid_x
    fraction_z = (local_z / cell_size) - grid_z
    smooth_x = fraction_x * fraction_x * (3.0 - 2.0 * fraction_x)
    smooth_z = fraction_z * fraction_z * (3.0 - 2.0 * fraction_z)
    north_west = _terrain_noise_sample(seed, grid_x, grid_z)
    north_east = _terrain_noise_sample(seed, grid_x + 1, grid_z)
    south_west = _terrain_noise_sample(seed, grid_x, grid_z + 1)
    south_east = _terrain_noise_sample(seed, grid_x + 1, grid_z + 1)
    north = north_west + (north_east - north_west) * smooth_x
    south = south_west + (south_east - south_west) * smooth_x
    noise = north + (south - north) * smooth_z

    rim_width = min(8.0, radius)
    rim_fade = min(1.0, max(0.0, (radius - distance) / rim_width))
    return int(round(noise * amplitude * rim_fade))


def nearest_landmark_center(chunk_x, chunk_z):
    """Port of LegacyLandmarkPlacements.getNearestCenterXZ."""
    region_x = (int(chunk_x) + 8) >> 4
    region_z = (int(chunk_z) + 8) >> 4
    key = (region_x, region_z)
    center = _LANDMARK_CENTER_CACHE.get(key)
    if center is _SELECTION_CACHE_MISS:
        center = _landmark_center_for_region(region_x, region_z)
        _LANDMARK_CENTER_CACHE.put(key, center)
    return center


def _landmark_center_for_region(region_x, region_z):
    seed = java_long(region_x * 3129871) ^ java_long(region_z * 116129781)
    seed = java_long(java_long(java_long(seed * seed) * 42317861) + seed * 7)

    unsigned_seed = seed & JAVA_LONG_MASK
    num0 = (unsigned_seed >> 12) & 3
    num1 = (unsigned_seed >> 15) & 3
    num2 = (unsigned_seed >> 18) & 3
    num3 = (unsigned_seed >> 21) & 3

    center_x = 8 + num0 - num1
    center_z = 8 + num2 - num3

    if region_x >= 0:
        block_x = (region_x * 16 + center_x - 8) * 16 + 8
    else:
        block_x = (region_x * 16 + (16 - center_x) - 8) * 16 + 9

    if region_z >= 0:
        block_z = (region_z * 16 + center_z - 8) * 16 + 8
    else:
        block_z = (region_z * 16 + (16 - center_z) - 8) * 16 + 9

    return int(block_x), int(block_z)


def nearest_route_landmark_center(chunk_x, chunk_z):
    """Return the fixed nominal center for a progression-route grid cell."""
    region_x = (int(chunk_x) + 8) >> 4
    region_z = (int(chunk_z) + 8) >> 4
    return (
        region_x * ROUTE_LANDMARK_GRID_BLOCKS + 8,
        region_z * ROUTE_LANDMARK_GRID_BLOCKS + 8,
    )


def legacy_landmark_center_for_nominal(block_x, block_z):
    """Return the old jittered center that belongs to one nominal cell."""
    region_x = (int(block_x) - 8) // ROUTE_LANDMARK_GRID_BLOCKS
    region_z = (int(block_z) - 8) // ROUTE_LANDMARK_GRID_BLOCKS
    return nearest_landmark_center(region_x * 16, region_z * 16)


def landmark_region_sample(block_x, block_z):
    """Return the nominal biome sample shared by one 256-block landmark cell.

    Legacy landmark centers jitter by up to three chunks, but landmark choice
    samples the aligned region center.  This matches the native feature-rule
    expression ``floor((origin + 128) / 256) * 256 + 8`` for both positive and
    negative coordinates.
    """
    spacing = ROUTE_LANDMARK_GRID_BLOCKS
    return (
        ((int(block_x) + spacing // 2) // spacing) * spacing + 8,
        ((int(block_z) + spacing // 2) // spacing) * spacing + 8,
    )


def route_landmark_centers(center_x, center_z):
    """Return the source-style main center followed by four cardinal centers."""
    center_x = int(center_x)
    center_z = int(center_z)
    return ((center_x, center_z),) + tuple(
        (center_x + offset_x, center_z + offset_z)
        for offset_x, offset_z in ROUTE_LANDMARK_CARDINAL_OFFSETS
    )


def landmark_center_candidates(chunk_x, chunk_z, region_radius=1):
    """Return nearby legacy-grid centers ordered by distance to one chunk.

    A landmark center can jitter three chunks away from its nominal 16x16
    region center.  Surface-native envelopes extend another four or five
    chunks, so their outer tiles can belong to an adjacent rounded region.
    Looking only at ``nearest_landmark_center(chunk_x, chunk_z)`` truncates
    those envelopes at the region boundary.
    """
    chunk_x = int(chunk_x)
    chunk_z = int(chunk_z)
    region_radius = max(0, int(region_radius))
    region_x = (chunk_x + 8) >> 4
    region_z = (chunk_z + 8) >> 4
    block_x = chunk_x * 16 + 8
    block_z = chunk_z * 16 + 8
    centers = set()
    for candidate_region_x in range(
        region_x - region_radius,
        region_x + region_radius + 1,
    ):
        for candidate_region_z in range(
            region_z - region_radius,
            region_z + region_radius + 1,
        ):
            centers.add(
                nearest_landmark_center(
                    candidate_region_x * 16,
                    candidate_region_z * 16,
                )
            )
    return sorted(
        centers,
        key=lambda center: (
            (int(center[0]) - block_x) ** 2
            + (int(center[1]) - block_z) ** 2,
            int(center[0]),
            int(center[1]),
        ),
    )


def route_landmark_center_candidates(chunk_x, chunk_z, region_radius=1):
    """Return nearby fixed route centers ordered by distance to one chunk."""
    chunk_x = int(chunk_x)
    chunk_z = int(chunk_z)
    region_radius = max(0, int(region_radius))
    region_x = (chunk_x + 8) >> 4
    region_z = (chunk_z + 8) >> 4
    block_x = chunk_x * 16 + 8
    block_z = chunk_z * 16 + 8
    centers = set()
    for candidate_region_x in range(
        region_x - region_radius,
        region_x + region_radius + 1,
    ):
        for candidate_region_z in range(
            region_z - region_radius,
            region_z + region_radius + 1,
        ):
            centers.add(
                (
                    candidate_region_x * ROUTE_LANDMARK_GRID_BLOCKS + 8,
                    candidate_region_z * ROUTE_LANDMARK_GRID_BLOCKS + 8,
                )
            )
    return sorted(
        centers,
        key=lambda center: (
            (int(center[0]) - block_x) ** 2
            + (int(center[1]) - block_z) ** 2,
            int(center[0]),
            int(center[1]),
        ),
    )


def is_landmark_center_chunk(chunk_x, chunk_z):
    """True only for the chunk that owns its legacy-grid landmark center."""
    center_x, center_z = nearest_landmark_center(chunk_x, chunk_z)
    return (
        (int(center_x) >> 4) == int(chunk_x)
        and (int(center_z) >> 4) == int(chunk_z)
    )


def blended_surface_height(
    source_height,
    target_height,
    distance,
    flat_radius,
    blend_width,
):
    """Flatten the core and smoothly return to the generated terrain."""
    source_height = int(source_height)
    target_height = int(target_height)
    distance = max(0.0, float(distance))
    flat_radius = max(0.0, float(flat_radius))
    blend_width = max(0.0, float(blend_width))
    if distance <= flat_radius or blend_width <= 0.0:
        return target_height
    if distance >= flat_radius + blend_width:
        return source_height
    terrain_weight = (distance - flat_radius) / blend_width
    # Smoothstep keeps both the landmark rim and untouched terrain tangent
    # visually flat, avoiding the visible straight ramp of linear blending.
    terrain_weight = terrain_weight * terrain_weight * (
        3.0 - 2.0 * terrain_weight
    )
    blended = (
        target_height * (1.0 - terrain_weight)
        + source_height * terrain_weight
    )
    return int(round(blended))


def hollow_hill_profile(diameter, horizontal_distance):
    """Return the source-style dome shell and hollow interior profile."""
    diameter = int(diameter)
    landmark_sizes = {36: 1, 68: 2, 100: 3}
    if diameter not in landmark_sizes:
        raise ValueError("unsupported hollow hill diameter")
    size = landmark_sizes[diameter]
    terrain_diameter = (size * 2 + 1) * 16
    radius = terrain_diameter / 2.0
    horizontal_distance = max(0.0, float(horizontal_distance))
    if horizontal_distance > radius:
        return None
    # ChunkGeneratorTwilight truncates distance before applying this cosine.
    surface = int(
        math.cos(
            int(horizontal_distance) / float(terrain_diameter) * math.pi
        )
        * (terrain_diameter / 3.0)
    )
    hollow = max(0, surface - 4 - size)
    return {
        "surface": surface,
        "shellBottom": max(1, surface - 2),
        "cavityFloor": 1,
        "cavityCeiling": max(1, hollow),
        "terrainDiameter": terrain_diameter,
    }


def hollow_hill_surface_target(source_y, landmark_sea_y, hill_height):
    """Port ChunkGeneratorTwilight.raiseHills' resulting surface height."""
    ground_height = int(source_y) - int(landmark_sea_y)
    total_height_raw = ground_height * 0.75 + float(hill_height)
    total_height = int(
        ((int(total_height_raw) >> 1) * 0.375)
        + total_height_raw * 0.625
    )
    calculated_y = int(landmark_sea_y) + total_height
    # Upstream fills from groundHeight through totalHeight.  When the
    # compressed height falls below the existing ground, that loop is empty;
    # it never excavates a one-block trench around the foot of the hill.
    return max(int(source_y), calculated_y)


def hollow_hill_spawn_choice(kind, seed):
    """Select one source-weighted controlled-spawn group."""
    entries = HOLLOW_HILL_CONTROLLED_SPAWNS.get(str(kind))
    if not entries:
        return None
    random_source = JavaRandom(seed)
    total_weight = sum(entry[1] for entry in entries)
    roll = random_source.next_int(total_weight)
    selected = entries[-1]
    for entry in entries:
        if roll < entry[1]:
            selected = entry
            break
        roll -= entry[1]
    minimum = selected[2]
    maximum = selected[3]
    count = minimum + random_source.next_int(maximum - minimum + 1)
    return {
        "identifier": selected[0],
        "count": count,
    }


def lich_tower_spawn_choice(seed):
    """Return ``(identifier, group_count)`` from the locked tower weights."""
    random_source = JavaRandom(seed)
    total_weight = sum(entry[1] for entry in LICH_TOWER_SPAWN_WEIGHTS)
    roll = random_source.next_int(total_weight)
    selected = LICH_TOWER_SPAWN_WEIGHTS[-1]
    for entry in LICH_TOWER_SPAWN_WEIGHTS:
        if roll < entry[1]:
            selected = entry
            break
        roll -= entry[1]
    minimum, maximum = selected[2]
    count = minimum + random_source.next_int(maximum - minimum + 1)
    return selected[0], count


def lich_tower_spawn_candidates(job, seed, limit):
    """Return deterministic candidates from compiled tower-interior air cells."""
    anchor = job.get("anchor")
    contract = job.get("controlledSpawns") or {}
    offsets = contract.get("interiorOffsets") or []
    if not anchor or len(anchor) != 3 or not offsets or int(limit) <= 0:
        return []

    unique_offsets = []
    seen = set()
    for value in offsets[:4096]:
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            continue
        try:
            offset = tuple(int(coordinate) for coordinate in value)
        except (TypeError, ValueError):
            continue
        if offset in seen:
            continue
        seen.add(offset)
        unique_offsets.append(offset)

    random_source = JavaRandom(seed)
    result = []
    while unique_offsets and len(result) < int(limit):
        offset = unique_offsets.pop(random_source.next_int(len(unique_offsets)))
        result.append(
            (
                (
                    float(anchor[0] + offset[0]) + 0.5,
                    float(anchor[1] + offset[1]),
                    float(anchor[2] + offset[2]) + 0.5,
                ),
                float(random_source.next_int(360)),
            )
        )
    return result


def hollow_hill_cavity_range(job, block_x, block_z):
    """Return the physical walkable Y range for one generated hill column."""
    return _hollow_hill_cavity_range(job, block_x, block_z, 0.85)


def hollow_hill_generated_cavity_range(job, block_x, block_z):
    """Return every Y position that the generated hill stores as air."""
    return _hollow_hill_cavity_range(job, block_x, block_z, 1.0)


def _hollow_hill_cavity_range(job, block_x, block_z, radius_scale):
    kind = str(job.get("kind", ""))
    hill_data = HOLLOW_HILL_KIND_DATA.get(kind)
    anchor = job.get("anchor")
    if hill_data is None or not anchor or len(anchor) != 3:
        return None
    size, diameter, terrain_diameter = hill_data
    center_x = float(anchor[0]) + (terrain_diameter - 1) / 2.0
    center_z = float(anchor[2]) + (terrain_diameter - 1) / 2.0
    delta_x = float(math.floor(block_x)) - center_x
    delta_z = float(math.floor(block_z)) - center_z
    distance = math.sqrt(delta_x * delta_x + delta_z * delta_z)
    # Controlled spawns use the shortened component radius; explicit carving
    # uses the full source cavity radius.
    radius_squared = (diameter / 2.0) ** 2 * float(radius_scale)
    outside = (
        distance * distance >= radius_squared
        if float(radius_scale) >= 1.0
        else distance * distance > radius_squared
    )
    if outside:
        return None
    underground_offset = hollow_hill_piece_depth(size)
    floor_relative = int(
        math.floor(
            size * 2
            - math.cos(
                distance / float(terrain_diameter) * math.pi
            )
            * (terrain_diameter / 20.0)
            + 1.25
        )
    )
    ceiling_relative = int(
        math.ceil(
            math.cos(
                distance / float(terrain_diameter) * math.pi
            )
            * (terrain_diameter / 4.0)
        )
    )
    floor_y = int(anchor[1]) - underground_offset + floor_relative + 1
    ceiling_y = (
        int(anchor[1])
        - underground_offset
        + ceiling_relative
        - 1
    )
    if ceiling_y < floor_y:
        return None
    return floor_y, ceiling_y


def player_inside_completed_hollow_hill(job, position, dimension_id):
    """Whether a player is inside the completed physical hill cavity."""
    if job.get("state") != "complete":
        return False
    if str(job.get("kind", "")) not in HOLLOW_HILL_KIND_DATA:
        return False
    if int(position.get("dimensionId", -1)) != int(dimension_id):
        return False
    player_position = position.get("position")
    if not player_position or len(player_position) != 3:
        return False
    cavity_range = hollow_hill_cavity_range(
        job,
        player_position[0],
        player_position[2],
    )
    if cavity_range is None:
        return False
    return (
        float(cavity_range[0]) - 0.5
        <= float(player_position[1])
        <= float(cavity_range[1]) + 1.0
    )


def hollow_hill_spawn_candidates(job, player_position, seed, limit):
    """Return deterministic, floor-aligned candidate monster positions."""
    hill_data = HOLLOW_HILL_KIND_DATA.get(str(job.get("kind", "")))
    anchor = job.get("anchor")
    if (
        hill_data is None
        or not anchor
        or len(anchor) != 3
        or not player_position
        or len(player_position) != 3
    ):
        return []
    _size, diameter, terrain_diameter = hill_data
    center_x = float(anchor[0]) + (terrain_diameter - 1) / 2.0
    center_z = float(anchor[2]) + (terrain_diameter - 1) / 2.0
    random_source = JavaRandom(seed)
    radius = max(1, int(diameter / 2.0))
    result = []
    attempts = max(8, int(limit) * 8)
    for _unused in range(attempts):
        block_x = int(center_x) + random_source.next_int(radius * 2 + 1) - radius
        block_z = int(center_z) + random_source.next_int(radius * 2 + 1) - radius
        cavity_range = hollow_hill_cavity_range(job, block_x, block_z)
        if cavity_range is None:
            continue
        delta_x = block_x + 0.5 - float(player_position[0])
        delta_z = block_z + 0.5 - float(player_position[2])
        if delta_x * delta_x + delta_z * delta_z < 36.0:
            continue
        result.append(
            (
                (block_x + 0.5, float(cavity_range[0]), block_z + 0.5),
                float(random_source.next_int(360)),
            )
        )
        if len(result) >= int(limit):
            break
    return result


def landmark_centers_in_radius(block_x, block_z, radius_blocks):
    """Return deterministic landmark-grid centers, nearest first."""
    block_x = int(block_x)
    block_z = int(block_z)
    radius_blocks = max(0, int(radius_blocks))
    chunk_x = int(math.floor(float(block_x) / 16.0))
    chunk_z = int(math.floor(float(block_z) / 16.0))
    region_x = (chunk_x + 8) >> 4
    region_z = (chunk_z + 8) >> 4
    region_radius = int(math.ceil(radius_blocks / 256.0)) + 1
    radius_squared = radius_blocks * radius_blocks
    centers = set()
    for candidate_region_x in range(
        region_x - region_radius,
        region_x + region_radius + 1,
    ):
        for candidate_region_z in range(
            region_z - region_radius,
            region_z + region_radius + 1,
        ):
            center = nearest_landmark_center(
                candidate_region_x * 16,
                candidate_region_z * 16,
            )
            dx = center[0] - block_x
            dz = center[1] - block_z
            if dx * dx + dz * dz <= radius_squared:
                centers.add(center)
    return sorted(
        centers,
        key=lambda center: (
            (center[0] - block_x) ** 2 + (center[1] - block_z) ** 2,
            center[0],
            center[1],
        ),
    )


def route_landmark_centers_in_radius(block_x, block_z, radius_blocks):
    """Return fixed nominal route centers within a block radius."""
    block_x = int(block_x)
    block_z = int(block_z)
    radius_blocks = max(0, int(radius_blocks))
    chunk_x = int(math.floor(float(block_x) / 16.0))
    chunk_z = int(math.floor(float(block_z) / 16.0))
    region_x = (chunk_x + 8) >> 4
    region_z = (chunk_z + 8) >> 4
    region_radius = int(math.ceil(radius_blocks / 256.0)) + 1
    radius_squared = radius_blocks * radius_blocks
    centers = set()
    for candidate_region_x in range(
        region_x - region_radius,
        region_x + region_radius + 1,
    ):
        for candidate_region_z in range(
            region_z - region_radius,
            region_z + region_radius + 1,
        ):
            center = (
                candidate_region_x * ROUTE_LANDMARK_GRID_BLOCKS + 8,
                candidate_region_z * ROUTE_LANDMARK_GRID_BLOCKS + 8,
            )
            delta_x = center[0] - block_x
            delta_z = center[1] - block_z
            if delta_x * delta_x + delta_z * delta_z <= radius_squared:
                centers.add(center)
    return sorted(
        centers,
        key=lambda center: (
            (center[0] - block_x) ** 2 + (center[1] - block_z) ** 2,
            center[0],
            center[1],
        ),
    )


def _rounded_region_chunk(chunk_coordinate):
    return java_math_round(float(chunk_coordinate) / 16.0) * 16


def pick_variety_landmark(chunk_x, chunk_z, world_seed):
    """Port of LegacyLandmarkPlacements.pickVarietyLandmark."""
    chunk_x = _rounded_region_chunk(chunk_x)
    chunk_z = _rounded_region_chunk(chunk_z)
    key = (int(world_seed), chunk_x, chunk_z)
    landmark = _LANDMARK_VARIETY_CACHE.get(key)
    if landmark is _SELECTION_CACHE_MISS:
        landmark = _pick_variety_for_region(chunk_x, chunk_z, world_seed)
        _LANDMARK_VARIETY_CACHE.put(key, landmark)
    return landmark


def _pick_variety_for_region(chunk_x, chunk_z, world_seed):
    offset_x = abs(java_remainder((chunk_x + 64) >> 4, 8))
    offset_z = abs(java_remainder((chunk_z + 64) >> 4, 8))

    if (offset_x == 4 and offset_z in (3, 5)):
        return "lich_tower"
    if (offset_z == 4 and offset_x in (3, 5)):
        return "naga_courtyard"

    seed = java_long(
        int(world_seed) + chunk_x * 25117 + chunk_z * 151121
    )
    roll = JavaRandom(seed).next_int(16)
    if roll in (6, 7, 8):
        return "medium_hill"
    if roll == 9:
        return "large_hill"
    if roll in (10, 11):
        return "hedge_maze"
    if roll in (12, 13):
        return "naga_courtyard"
    if roll in (14, 15):
        return "lich_tower"
    return "small_hill"


def ported_landmark(landmark, supported):
    if landmark in supported:
        return landmark
    return None


def resolve_variety_landmark(
    chunk_x,
    chunk_z,
    world_seed,
    supported,
    unported_fallback=None,
):
    """Resolve every legacy variety slot to an available landmark.

    The raw picker remains byte-for-byte compatible in behavior with the Java
    landmark selector. Until the lich tower is ported, its slots are reused
    deterministically so a valid landmark center never becomes an empty hole.
    A biome-specific fallback may claim those slots, such as mushroom towers
    inside dense mushroom forest.
    """
    landmark = pick_variety_landmark(chunk_x, chunk_z, world_seed)
    # Dense mushroom forest intentionally preserves the already-shipped
    # mushroom tower override even after Lich Tower becomes supported.  Old
    # worlds used this argument only as an unported fallback; treating it as a
    # biome preference for the one claimed slot is additive and keeps every
    # recorded landmark stable.
    if landmark == "lich_tower" and unported_fallback is not None:
        return str(unported_fallback)
    resolved = ported_landmark(landmark, supported)
    if resolved is not None:
        return resolved
    if landmark != "lich_tower":
        return None
    if unported_fallback is not None:
        return str(unported_fallback)

    replacements = [
        kind
        for kind in ("naga_courtyard", "large_hill")
        if kind in supported
    ]
    if not replacements:
        return None
    rounded_x = _rounded_region_chunk(chunk_x)
    rounded_z = _rounded_region_chunk(chunk_z)
    seed = java_long(
        int(world_seed)
        + rounded_x * 341873128712
        + rounded_z * 132897987541
        + 0x4C494348
    )
    return replacements[JavaRandom(seed).next_int(len(replacements))]


def boss_activation_position(job, players, dimension_id):
    """Return a generic source-style boss spawn position for a landmark."""
    if (
        job.get("state") != "complete"
        and not job.get("bossSpawnerReady")
    ):
        return None
    if job.get("bossSpawned") or job.get("bossDefeated"):
        return None
    spawner = job.get("bossSpawner")
    anchor = job.get("anchor")
    if not isinstance(spawner, dict) or not anchor or len(anchor) != 3:
        return None
    offset = spawner.get("offset")
    if not offset or len(offset) != 3:
        return None
    marker_x = float(anchor[0]) + float(offset[0]) + 0.5
    marker_y = float(anchor[1]) + float(offset[1]) + 0.5
    marker_z = float(anchor[2]) + float(offset[2]) + 0.5
    spawn_y = marker_y + float(spawner.get("spawnYOffset", 0.0))
    radius = max(1.0, float(spawner.get("activationRadius", 9)))
    radius_squared = radius * radius
    minimum_player_y = marker_y + float(
        spawner.get("minPlayerYOffset", -1000000.0)
    )
    maximum_player_y = marker_y + float(
        spawner.get("maxPlayerYOffset", 1000000.0)
    )
    required_progress = tuple(
        str(value) for value in spawner.get("progressAll", ())
    )
    for player in players:
        if int(player.get("dimensionId", -1)) != int(dimension_id):
            continue
        position = player.get("position")
        if position is None or len(position) < 3:
            continue
        if float(position[1]) <= minimum_player_y:
            continue
        if float(position[1]) >= maximum_player_y:
            continue
        progress = player.get("progress", {})
        if any(
            int(progress.get(objective, 0)) <= 0
            for objective in required_progress
        ):
            continue
        dx = float(position[0]) - marker_x
        dy = float(position[1]) - marker_y
        dz = float(position[2]) - marker_z
        if dx * dx + dy * dy + dz * dz <= radius_squared:
            return marker_x, spawn_y, marker_z
    return None


def boss_spawner_for_variant(entry, variant=None):
    """Return an isolated spawner contract with any layout-local offset."""
    if not isinstance(entry, dict):
        return None
    base = entry.get("bossSpawner")
    if not isinstance(base, dict):
        return None
    resolved = copy.deepcopy(base)
    if isinstance(variant, dict):
        variant_spawner = variant.get("bossSpawner")
        if isinstance(variant_spawner, dict):
            for key, value in variant_spawner.items():
                resolved[key] = copy.deepcopy(value)
        offset = variant.get("bossSpawnerOffset")
        if isinstance(offset, (list, tuple)) and len(offset) == 3:
            resolved["offset"] = [int(value) for value in offset]
    return resolved


def is_inside_landmark_clearance(
    block_x,
    block_z,
    world_seed,
    supported,
    clearance_chunks,
    unported_fallback=None,
):
    """Apply AvoidLandmarkModifier's square, per-landmark clearance."""
    center_x, center_z = nearest_landmark_center(
        int(block_x) >> 4,
        int(block_z) >> 4,
    )
    # A type-specific exclusion square cannot extend beyond the largest
    # configured square. Keep the strict '< radius' edge and the live policy;
    # this is not a new no-tree envelope or a landmark-candidate filter.
    try:
        maximum_radius = max([0] + [int(value) for value in clearance_chunks.values()]) * 16
    except (TypeError, ValueError):
        # Preserve the old lookup behavior for unused malformed policy values.
        maximum_radius = None
    if maximum_radius is not None and (
        abs(center_x - int(block_x)) >= maximum_radius
        or abs(center_z - int(block_z)) >= maximum_radius
    ):
        return False
    landmark = resolve_variety_landmark(
        center_x >> 4,
        center_z >> 4,
        world_seed,
        supported,
        unported_fallback,
    )
    if landmark is None:
        return False
    radius = int(clearance_chunks.get(landmark, 0)) * 16
    if radius <= 0:
        return False
    return (
        abs(center_x - int(block_x)) < radius
        and abs(center_z - int(block_z)) < radius
    )


def landmark_ledger_key(anchor):
    return "%d,%d" % (int(anchor[0]), int(anchor[2]))


def create_landmark_job(kind, anchor, variant, pieces, bounds=None):
    copied_pieces = []
    for piece in pieces:
        copied_piece = {
            "structure": str(piece["structure"]),
            "offset": [int(value) for value in piece["offset"]],
        }
        if "layer" in piece:
            copied_piece["layer"] = str(piece["layer"])
        if "removeBlock" in piece:
            copied_piece["removeBlock"] = bool(piece["removeBlock"])
        if "rotation" in piece:
            copied_piece["rotation"] = int(piece["rotation"])
        if "mirror" in piece:
            copied_piece["mirror"] = int(piece["mirror"])
        if "size" in piece:
            copied_piece["size"] = [
                int(value) for value in piece["size"]
            ]
        copied_pieces.append(copied_piece)
    if bounds is None:
        bounds = [
            int(anchor[0]),
            int(anchor[1]),
            int(anchor[2]),
            int(anchor[0]),
            int(anchor[1]),
            int(anchor[2]),
        ]
    return {
        "kind": str(kind),
        "anchor": [int(value) for value in anchor],
        "variant": int(variant),
        "bounds": [int(value) for value in bounds],
        "pieces": copied_pieces,
        "nextPiece": 0,
        "retries": 0,
        "state": "planned",
    }


def claim_next_pieces(job, limit):
    if job.get("state") in ("complete", "failed"):
        return []
    start = int(job.get("nextPiece", 0))
    pieces = job.get("pieces", [])
    if start >= len(pieces) or limit <= 0:
        return []
    end = min(start + int(limit), len(pieces))
    claimed = pieces[start:end]
    job["nextPiece"] = end
    job["state"] = "placing"
    return claimed


def complete_if_finished(job):
    if job.get("state") == "complete":
        return True
    if job.get("state") == "failed":
        return False
    if int(job.get("nextPiece", 0)) >= len(job.get("pieces", [])):
        job["state"] = "complete"
        return True
    return False


def record_job_failure(job, max_retries=3):
    job["retries"] = int(job.get("retries", 0)) + 1
    if job["retries"] >= int(max_retries):
        job["state"] = "failed"
    else:
        job["state"] = "planned"
    return job["state"]


def courtyard_activation_position(job, players, dimension_id):
    """Return the one source-style Naga spawn point when a player is near."""
    if job.get("kind") != "naga_courtyard":
        return None
    if (
        job.get("state") != "complete"
        and not job.get("bossSpawnerReady")
    ):
        return None
    if job.get("bossSpawned") or job.get("bossDefeated"):
        return None
    spawner = job.get("bossSpawner")
    if not isinstance(spawner, dict):
        return None
    offset = spawner.get("offset")
    anchor = job.get("anchor")
    if not offset or len(offset) != 3 or not anchor or len(anchor) != 3:
        return None
    marker_x = float(anchor[0]) + float(offset[0])
    marker_y = float(anchor[1]) + float(offset[1])
    marker_z = float(anchor[2]) + float(offset[2])
    radius = max(1.0, float(spawner.get("activationRadius", 64)))
    radius_squared = radius * radius
    for player in players:
        if int(player.get("dimensionId", -1)) != int(dimension_id):
            continue
        position = player.get("position")
        if position is None or len(position) < 3:
            continue
        dx = float(position[0]) - (marker_x + 0.5)
        dz = float(position[2]) - (marker_z + 0.5)
        if dx * dx + dz * dz <= radius_squared:
            return marker_x + 0.5, marker_y + 1.0, marker_z + 0.5
    return None


def bounds_overlap(first, second):
    if not first or not second or len(first) != 6 or len(second) != 6:
        return False
    return not (
        first[3] < second[0]
        or second[3] < first[0]
        or first[4] < second[1]
        or second[4] < first[1]
        or first[5] < second[2]
        or second[5] < first[2]
    )
