# -*- coding: utf-8 -*-
"""Canonical Twilight Forest biome metadata for worldgen and services.

The NetEase generator cannot run Twilight Forest's Java layer classes, but its
``transition`` source stage can reproduce the important river-seam behavior.
The five common forests and four source-rare biomes form the low-frequency
base map. Fire Swamp and Dark Forest Center are equal-weight key biomes.
NetEase ``condition`` stages first grow a complete companion-biome domain and
then restore a smaller concentric key-biome core. That gives the route
structures independent landmark-grid interiors without letting a later
envelope stage overwrite the core. Streams are injected only after every land
zoom completes.
"""


import io
import json
import math
import posixpath


BIOMES = (
    {
        "key": "forest",
        "identifier": "dm33027004_plains",
        "inherits": "plains",
        "noise_params": [0.025, 0.05],
        "temperature": 0.5,
        "downfall": 0.5,
        "weight": 14,
    },
    {
        "key": "dense_forest",
        "identifier": "dm33027004_jungle",
        "inherits": "jungle",
        "noise_params": [0.1, 0.2],
        "temperature": 0.7,
        "downfall": 0.8,
        "weight": 14,
    },
    {
        "key": "oak_savannah",
        "identifier": "dm33027004_savanna",
        "inherits": "savanna",
        "noise_params": [0.05, 0.1],
        "temperature": 0.9,
        "downfall": 0.0,
        "weight": 14,
    },
    {
        "key": "mushroom_forest",
        "identifier": "dm33027004_mushroom_island_shore",
        "inherits": "mushroom_island_shore",
        "noise_params": [0.025, 0.05],
        "temperature": 0.8,
        "downfall": 0.8,
        "weight": 14,
    },
    {
        "key": "firefly_forest",
        "identifier": "dm33027004_flower_forest",
        "inherits": "flower_forest",
        "noise_params": [0.0625, 0.05],
        "temperature": 0.5,
        "downfall": 1.0,
        "weight": 14,
    },
    {
        "key": "stream",
        "identifier": "dm33027004_river",
        "inherits": "river",
        # Java's stream depth is interpreted through Twilight's custom terrain
        # wrapper. NetEase inserts this biome after the final land zoom and
        # applies its height directly, so even vanilla's -0.5 river depth makes
        # a hard cliff trench at Dark Forest seams. Match the lowest adjacent
        # land profile instead: every configured stream seam then stays within
        # a 0.20 depth delta while still settling at shallow-water height.
        "noise_params": [-0.1, 0.0],
        "temperature": 0.5,
        "downfall": 0.1,
        "weight": 3,
    },
    {
        "key": "dense_mushroom_forest",
        "identifier": "dm33027004_mushroom_island",
        "inherits": "mushroom_island",
        "noise_params": [0.05, 0.05],
        "temperature": 0.8,
        "downfall": 1.0,
        "weight": 1,
    },
    {
        "key": "lake",
        "identifier": "dm33027004_ocean",
        "inherits": "ocean",
        "noise_params": [-1.97, 0.0],
        "temperature": 0.66,
        "downfall": 1.0,
        "weight": 1,
    },
    {
        "key": "enchanted_forest",
        "identifier": "dm33027004_birch_forest_mutated",
        "inherits": "birch_forest_mutated",
        "noise_params": [0.025, 0.05],
        "temperature": 0.5,
        "downfall": 0.5,
        "weight": 1,
    },
    {
        "key": "clearing",
        "identifier": "dm33027004_sunflower_plains",
        "inherits": "sunflower_plains",
        "noise_params": [0.005, 0.005],
        "temperature": 0.8,
        "downfall": 0.4,
        "weight": 1,
    },
    {
        "key": "spooky_forest",
        "identifier": "dm33027004_roofed_forest",
        "inherits": "roofed_forest",
        "noise_params": [0.025, 0.05],
        "temperature": 0.5,
        "downfall": 1.0,
        "weight": 1,
    },
    {
        "key": "swamp",
        "identifier": "dm33027004_swampland",
        "inherits": "swampland",
        "noise_params": [-0.10, 0.15],
        "temperature": 0.8,
        "downfall": 0.9,
        "weight": 1,
    },
    {
        "key": "fire_swamp",
        "identifier": "dm33027004_swampland_mutated",
        "inherits": "swampland_mutated",
        "noise_params": [-0.02, 0.05],
        "temperature": 1.0,
        "downfall": 0.4,
        "weight": 1,
    },
    {
        "key": "dark_forest",
        # NetEase requires the custom identifier suffix to exactly match the
        # inherited vanilla biome.  The semantic route name remains in key.
        "identifier": "dm33027004_roofed_forest_mutated",
        "inherits": "roofed_forest_mutated",
        "noise_params": [0.025, 0.005],
        "temperature": 0.7,
        "downfall": 0.8,
        "weight": 1,
    },
    {
        "key": "dark_forest_center",
        "identifier": "dm33027004_redwood_taiga_mutated",
        "inherits": "redwood_taiga_mutated",
        "noise_params": [0.025, 0.005],
        "temperature": 0.5,
        "downfall": 0.5,
        "weight": 1,
    },
)

BIOMES_BY_IDENTIFIER = dict(
    (entry["identifier"], entry) for entry in BIOMES
)
BIOMES_BY_KEY = dict((entry["key"], entry) for entry in BIOMES)


_DEFAULT_TERRITORY_SLOT_LOCALS = (
    (2, 2),
    (6, 2),
    (6, 6),
    (2, 6),
)
_DEFAULT_TERRITORY_PROFILES = (
    {
        "id": "fire_route",
        "enabled": True,
        "homeSlot": 0,
        "coreBiome": "fire_swamp",
        "companionBiome": "swamp",
        "mainLandmark": "hydra_lair",
        "companionLandmark": "labyrinth",
        "coreMapColor": [97, 3, 0, 255],
        "companionMapColor": [48, 115, 112, 255],
        "outerPhase": 0,
        "corePhase": 0,
    },
    {
        "id": "dark_route",
        "enabled": True,
        "homeSlot": 1,
        "coreBiome": "dark_forest_center",
        "companionBiome": "dark_forest",
        "mainLandmark": "dark_tower",
        "companionLandmark": "knight_stronghold",
        "coreMapColor": [112, 66, 27, 255],
        "companionMapColor": [53, 66, 27, 255],
        "outerPhase": 180,
        "corePhase": 53,
    },
    {
        "id": "glacier_route",
        "enabled": False,
        "homeSlot": 2,
        "coreBiome": None,
        "companionBiome": None,
        "mainLandmark": None,
        "companionLandmark": None,
        "coreMapColor": None,
        "companionMapColor": None,
        "fallbackProfile": "fire_route",
        "outerPhase": 90,
        "corePhase": 106,
        "plannedCoreBiome": "glacier",
        "plannedCompanionBiome": "snowy_forest",
        "plannedMainLandmark": "aurora_palace",
        "plannedCompanionLandmark": "yeti_cave",
    },
    {
        "id": "final_highlands_route",
        "enabled": False,
        "homeSlot": 3,
        "coreBiome": None,
        "companionBiome": None,
        "mainLandmark": None,
        "companionLandmark": None,
        "coreMapColor": None,
        "companionMapColor": None,
        "fallbackProfile": "dark_route",
        "outerPhase": 270,
        "corePhase": 159,
        "plannedCoreBiome": "final_plateau",
        "plannedCompanionBiome": "highlands",
        "plannedMainLandmark": "final_castle",
        "plannedCompanionLandmark": "troll_cave",
    },
)


def _default_territory_profile_pool():
    """Return the last known-good runtime pool without filesystem access."""
    slots = tuple(tuple(item) for item in _DEFAULT_TERRITORY_SLOT_LOCALS)
    profiles = tuple(dict(item) for item in _DEFAULT_TERRITORY_PROFILES)
    document = {
        "schemaVersion": 1,
        "slotLocals": [list(item) for item in slots],
        "profiles": [dict(item) for item in profiles],
    }
    return document, slots, profiles


def _load_territory_profile_pool():
    path = posixpath.join(
        posixpath.dirname(__file__.replace("\\", "/")),
        "territory_profiles.json",
    )
    with io.open(path, "r", encoding="utf-8") as stream:
        document = json.load(stream)
    if int(document.get("schemaVersion", 0)) != 1:
        raise ValueError("territory profile schemaVersion must be 1")
    slots = tuple(tuple(int(value) for value in item) for item in document.get("slotLocals", ()))
    profiles = tuple(dict(item) for item in document.get("profiles", ()))
    if len(slots) != 4 or len(set(slots)) != 4:
        raise ValueError("territory profile pool requires four unique slots")
    if len(profiles) != 4:
        raise ValueError("territory profile pool requires four profiles")
    if len(set(profile.get("id") for profile in profiles)) != 4:
        raise ValueError("territory profile ids must be unique")
    if set(int(profile.get("homeSlot", -1)) for profile in profiles) != set(range(4)):
        raise ValueError("territory profile homeSlot values must be 0..3")
    profile_by_id = dict((profile["id"], profile) for profile in profiles)
    required = (
        "coreBiome",
        "companionBiome",
        "mainLandmark",
        "companionLandmark",
        "coreMapColor",
        "companionMapColor",
    )
    for profile in profiles:
        if not profile.get("enabled"):
            continue
        if any(not profile.get(key) for key in required):
            raise ValueError("enabled territory profiles require biome and landmark bindings")
        if profile["coreBiome"] not in BIOMES_BY_KEY or profile["companionBiome"] not in BIOMES_BY_KEY:
            raise ValueError("enabled territory profile references an unknown biome")
        for color_key in ("coreMapColor", "companionMapColor"):
            color = profile[color_key]
            if (
                not isinstance(color, list)
                or len(color) != 4
                or any(int(channel) < 0 or int(channel) > 255 for channel in color)
            ):
                raise ValueError(
                    "enabled territory profile requires an RGBA map color"
                )
    for profile in profiles:
        fallback_id = profile.get("fallbackProfile")
        if profile.get("enabled") or not fallback_id:
            continue
        fallback = profile_by_id.get(fallback_id)
        if (
            fallback is None
            or fallback is profile
            or not fallback.get("enabled")
        ):
            raise ValueError(
                "territory fallbackProfile must reference an enabled profile"
            )
    return document, slots, profiles


TERRITORY_PROFILE_LOAD_ERROR = None
try:
    (
        TERRITORY_PROFILE_DOCUMENT,
        TERRITORY_SLOT_LOCALS,
        TERRITORY_PROFILES,
    ) = _load_territory_profile_pool()
except Exception as error:
    # Runtime sidecars are an authoring convenience, never a reason to lose
    # the entire ModSDK server system (portal and chat listeners included).
    TERRITORY_PROFILE_LOAD_ERROR = "%s: %s" % (
        type(error).__name__,
        error,
    )
    (
        TERRITORY_PROFILE_DOCUMENT,
        TERRITORY_SLOT_LOCALS,
        TERRITORY_PROFILES,
    ) = _default_territory_profile_pool()
TERRITORY_PROFILE_BY_ID = dict(
    (profile["id"], profile) for profile in TERRITORY_PROFILES
)
ENABLED_TERRITORY_PROFILES = tuple(
    profile for profile in TERRITORY_PROFILES if profile.get("enabled")
)


def _resolved_territory_profiles():
    binding_keys = (
        "coreBiome",
        "companionBiome",
        "mainLandmark",
        "companionLandmark",
        "coreMapColor",
        "companionMapColor",
        "outerPhase",
        "corePhase",
    )
    resolved = []
    for profile in TERRITORY_PROFILES:
        if profile.get("enabled"):
            effective = dict(profile)
            effective["sourceProfileId"] = profile["id"]
            effective["usesFallback"] = False
            resolved.append(effective)
            continue
        fallback_id = profile.get("fallbackProfile")
        if not fallback_id:
            continue
        source = TERRITORY_PROFILE_BY_ID[fallback_id]
        effective = dict(profile)
        for key in binding_keys:
            effective[key] = source[key]
        effective["sourceProfileId"] = source["id"]
        effective["usesFallback"] = True
        resolved.append(effective)
    return tuple(resolved)


ACTIVE_TERRITORY_PROFILES = _resolved_territory_profiles()
ACTIVE_TERRITORY_PROFILE_BY_ID = dict(
    (profile["id"], profile) for profile in ACTIVE_TERRITORY_PROFILES
)
_active_content_ids = set()
_active_content_profiles = []
for _territory_profile in ACTIVE_TERRITORY_PROFILES:
    _content_id = _territory_profile["sourceProfileId"]
    if _content_id in _active_content_ids:
        continue
    _active_content_ids.add(_content_id)
    _active_content_profiles.append(TERRITORY_PROFILE_BY_ID[_content_id])
ACTIVE_TERRITORY_CONTENT_PROFILES = tuple(_active_content_profiles)


def _unique_profile_values(profiles, key):
    values = []
    seen = set()
    for profile in profiles:
        value = profile[key]
        if value in seen:
            continue
        seen.add(value)
        values.append(value)
    return tuple(values)
AQUATIC_BIOME_KEYS = frozenset(("lake", "stream"))
BASE_SOURCE_BIOMES = tuple(
    entry
    for entry in BIOMES
    if entry["key"] not in AQUATIC_BIOME_KEYS
)
COMMON_SOURCE_BIOME_KEYS = (
    "forest",
    "dense_forest",
    "oak_savannah",
    "mushroom_forest",
    "firefly_forest",
)
RARE_SOURCE_BIOME_KEYS = (
    "dense_mushroom_forest",
    "enchanted_forest",
    "clearing",
    "spooky_forest",
)
RARE_KEY_BIOME_KEYS = tuple(
    _unique_profile_values(ACTIVE_TERRITORY_CONTENT_PROFILES, "coreBiome")
)
COMMON_SOURCE_BIOMES = tuple(
    BIOMES_BY_KEY[key] for key in COMMON_SOURCE_BIOME_KEYS
)
RARE_SOURCE_BIOMES = tuple(
    BIOMES_BY_KEY[key] for key in RARE_SOURCE_BIOME_KEYS
)
RARE_KEY_BIOMES = tuple(
    BIOMES_BY_KEY[key] for key in RARE_KEY_BIOME_KEYS
)
ASSOCIATED_BIOME_KEYS = tuple(
    _unique_profile_values(
        ACTIVE_TERRITORY_CONTENT_PROFILES,
        "companionBiome",
    )
)
ASSOCIATED_BIOMES = tuple(
    BIOMES_BY_KEY[key] for key in ASSOCIATED_BIOME_KEYS
)
RANDOM_SOURCE_BIOMES = COMMON_SOURCE_BIOMES + RARE_SOURCE_BIOMES
SOURCE_POOL_BIOMES = RANDOM_SOURCE_BIOMES + RARE_KEY_BIOMES
ACTIVE_LAND_BIOMES = SOURCE_POOL_BIOMES + ASSOCIATED_BIOMES
# Upstream assigns four distinct key-biome slots inside one 8x8 macro. This
# slice implements only Fire Swamp and Dark Forest Center, so exactly two slots
# become routes while the other two remain ordinary parent land. One private
# zoom keeps ordinary biomes broad; route seeds then receive the upstream split
# of two zooms, a 3x3 stabilize interior, and four final zooms. Coordinate-only
# stages replace Java neighborhood transformers without evaluating conditions at
# final resolution, which previously saturated NetEase's native chunk workers.
KEY_BIOME_GRID = {
    "len_x": 8,
    "len_z": 8,
    "border_x": 2,
    "border_z": 2,
}
# Ordinary land receives all seven zooms. Route seeds are inserted after the
# private first zoom and therefore receive the same six zooms as upstream.
PRE_KEY_LAND_ZOOM_STAGES = ("vanilla_zoom_2x",)
ROUTE_PRE_STABILIZE_ZOOM_STAGES = ("vanilla_zoom_2x",) * 2
FINAL_LAND_ZOOM_STAGES = ("vanilla_zoom_2x",) * 4
KEY_BIOME_ANCHOR_KEY = "fire_swamp"
KEY_BIOME_ALTERNATE_KEY = "dark_forest_center"


def key_biome_classifier_condition():
    """Return the NetEase Molang checkerboard for deterministic route keys."""
    region_x = "math.floor(variable.worldx / %d)" % KEY_BIOME_GRID["len_x"]
    region_z = "math.floor(variable.worldz / %d)" % KEY_BIOME_GRID["len_z"]
    region_sum = "(%s + %s)" % (region_x, region_z)
    odd_region = "(%s - (math.floor(%s / 2) * 2)) == 1" % (
        region_sum,
        region_sum,
    )
    anchor_query_type = BIOME_QUERY_TYPES[KEY_BIOME_ANCHOR_KEY]
    return (
        "(query.get_neighborhood_is_biome(0, 0, %d)) && (%s) ? 0 : -1"
        % (anchor_query_type, odd_region)
    )


# Compatibility aliases retained for older route-foundation diagnostics. The
# canonical coordinate stencil below does not execute neighborhood dilation.
CARDINAL_COMPANION_POSITIONS = (
    (-1, 0),
    (0, -1),
    (0, 1),
    (1, 0),
)
IMMEDIATE_COMPANION_POSITIONS = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)
KEY_BIOME_COMPANION_DILATION_STAGES = 5
KEY_BIOME_CORE_DILATION_STAGES = 1
KEY_BIOME_CORE_POSITIONS = ((0, 0),) + IMMEDIATE_COMPANION_POSITIONS
KEY_BIOME_CORE_QUERY_OFFSETS = KEY_BIOME_CORE_POSITIONS
RARE_KEY_COMPANION_KEYS = dict(
    (profile["coreBiome"], profile["companionBiome"])
    for profile in ACTIVE_TERRITORY_CONTENT_PROFILES
)
ROUTE_CORE_BIOME_BY_COMPANION_BIOME = dict(
    (
        BIOMES_BY_KEY[companion_key]["identifier"],
        BIOMES_BY_KEY[core_key]["identifier"],
    )
    for core_key, companion_key in RARE_KEY_COMPANION_KEYS.items()
)

# NetEase condition coordinates empirically propagate as one world block per
# source unit, not Bedrock/Java's four-block quart. Scale the logical *center
# positions* by four so six route zooms recover the legacy 256-block landmark
# spacing. Do not also widen each seed to four units: after the two pre-
# stabilize zooms that produces a 256-block seed which unions with Stabilize
# into a roughly 320-block territory and can swallow diagonal landmark
# centers. A one-unit seed plus the centered 128-block stable box keeps the
# layout natural while preserving the native +/-256 structure query.
ROUTE_BIOME_SOURCE_CELL_BLOCKS = 1
ROUTE_BIOME_COORDINATE_SCALE = 4
ROUTE_BIOME_SEED_CELL_SPAN = 1
ROUTE_BIOME_REGION_CELLS = (
    KEY_BIOME_GRID["len_x"] * ROUTE_BIOME_COORDINATE_SCALE
)
ROUTE_BIOME_COORDINATE_BLOCKS = (
    ROUTE_BIOME_SOURCE_CELL_BLOCKS
    * (
        1
        << (
            len(ROUTE_PRE_STABILIZE_ZOOM_STAGES)
            + len(FINAL_LAND_ZOOM_STAGES)
        )
    )
)
ROUTE_BIOME_SEED_BLOCKS = (
    ROUTE_BIOME_COORDINATE_BLOCKS * ROUTE_BIOME_SEED_CELL_SPAN
)
# Compatibility name for one legacy route landmark cell. This is center
# spacing, not the visible width of a route biome territory.
ROUTE_BIOME_CELL_BLOCKS = (
    ROUTE_BIOME_COORDINATE_BLOCKS * ROUTE_BIOME_COORDINATE_SCALE
)
ROUTE_LAYOUT_VARIANTS = (0, 1, 2, 3)
ROUTE_PROFILE_CORE_LOCALS_BY_VARIANT = dict(
    (
        variant,
        dict(
            (
                profile["id"],
                TERRITORY_SLOT_LOCALS[
                    (int(profile["homeSlot"]) + int(variant)) % 4
                ],
            )
            for profile in ACTIVE_TERRITORY_PROFILES
        ),
    )
    for variant in ROUTE_LAYOUT_VARIANTS
)
# Content-keyed compatibility view. Production placement uses the profile-keyed
# view above so temporary fallbacks cannot overwrite another instance of the
# same core biome.
ROUTE_CORE_LOCALS_BY_VARIANT = dict(
    (
        variant,
        dict(
            (
                profile["coreBiome"],
                TERRITORY_SLOT_LOCALS[
                    (int(profile["homeSlot"]) + int(variant)) % 4
                ],
            )
            for profile in ACTIVE_TERRITORY_CONTENT_PROFILES
        ),
    )
    for variant in ROUTE_LAYOUT_VARIANTS
)
ROUTE_BIOME_COMPANION_CELL_DISTANCE = 1


def route_layout_variant(region_x, region_z):
    """Return the deterministic four-way territory rotation for one macro."""
    region_x = int(region_x)
    region_z = int(region_z)
    parity_turn = 2 * (region_x % 2) * (region_z % 2)
    return (3 * region_x + region_z + parity_turn) % len(
        ROUTE_LAYOUT_VARIANTS
    )
ROUTE_COMPANION_LOCALS_BY_VARIANT = dict(
    (
        variant,
        dict(
            (
                route_key,
                tuple(
                    (
                        core_local[0] + offset_x,
                        core_local[1] + offset_z,
                    )
                    for offset_x, offset_z in CARDINAL_COMPANION_POSITIONS
                ),
            )
            for route_key, core_local in routes.items()
        ),
    )
    for variant, routes in ROUTE_CORE_LOCALS_BY_VARIANT.items()
)
ROUTE_PROFILE_COMPANION_LOCALS_BY_VARIANT = dict(
    (
        variant,
        dict(
            (
                profile_id,
                tuple(
                    (
                        core_local[0] + offset_x,
                        core_local[1] + offset_z,
                    )
                    for offset_x, offset_z in CARDINAL_COMPANION_POSITIONS
                ),
            )
            for profile_id, core_local in routes.items()
        ),
    )
    for variant, routes in ROUTE_PROFILE_CORE_LOCALS_BY_VARIANT.items()
)


def _route_seed_box(source_local):
    min_x = int(source_local[0]) * ROUTE_BIOME_COORDINATE_SCALE
    min_z = int(source_local[1]) * ROUTE_BIOME_COORDINATE_SCALE
    return (
        min_x,
        min_z,
        min_x + ROUTE_BIOME_SEED_CELL_SPAN,
        min_z + ROUTE_BIOME_SEED_CELL_SPAN,
    )


ROUTE_CORE_SEED_BOXES_BY_VARIANT = dict(
    (
        variant,
        dict(
            (route_key, _route_seed_box(core_local))
            for route_key, core_local in routes.items()
        ),
    )
    for variant, routes in ROUTE_CORE_LOCALS_BY_VARIANT.items()
)
ROUTE_COMPANION_SEED_BOXES_BY_VARIANT = dict(
    (
        variant,
        dict(
            (
                route_key,
                tuple(
                    _route_seed_box(companion_local)
                    for companion_local in companions
                ),
            )
            for route_key, companions in routes.items()
        ),
    )
    for variant, routes in ROUTE_COMPANION_LOCALS_BY_VARIANT.items()
)
ROUTE_PROFILE_CORE_SEED_BOXES_BY_VARIANT = dict(
    (
        variant,
        dict(
            (profile_id, _route_seed_box(core_local))
            for profile_id, core_local in routes.items()
        ),
    )
    for variant, routes in ROUTE_PROFILE_CORE_LOCALS_BY_VARIANT.items()
)
ROUTE_PROFILE_COMPANION_SEED_BOXES_BY_VARIANT = dict(
    (
        variant,
        dict(
            (
                profile_id,
                tuple(
                    _route_seed_box(companion_local)
                    for companion_local in companions
                ),
            )
            for profile_id, companions in routes.items()
        ),
    )
    for variant, routes in ROUTE_PROFILE_COMPANION_LOCALS_BY_VARIANT.items()
)

# Stabilize runs after two route zooms. At that stage the one-unit seed has
# become 4x4 units. Route structures use fixed nominal centers, so one noisy
# Euclidean body can cover the main center and all four cardinal companions
# with a one-cell margin. The final four zooms naturalize its low-resolution
# edge without the four square pockets that previously produced a clover.
ROUTE_STABILIZE_SCALE = 1 << len(ROUTE_PRE_STABILIZE_ZOOM_STAGES)
ROUTE_STABILIZE_REGION_CELLS = (
    ROUTE_BIOME_REGION_CELLS * ROUTE_STABILIZE_SCALE
)
ROUTE_STABILIZE_CELL_BLOCKS = (
    ROUTE_BIOME_SOURCE_CELL_BLOCKS * (1 << len(FINAL_LAND_ZOOM_STAGES))
)
ROUTE_STABILIZE_HALF_WIDTH_CELLS = ROUTE_BIOME_COORDINATE_SCALE
ROUTE_STABILIZE_WIDTH_CELLS = ROUTE_STABILIZE_HALF_WIDTH_CELLS * 2
ROUTE_STABLE_INTERIOR_BLOCKS = (
    ROUTE_STABILIZE_WIDTH_CELLS * ROUTE_STABILIZE_CELL_BLOCKS
)
ROUTE_EFFECTIVE_TERRITORY_BLOCKS = (
    max(
        ROUTE_BIOME_SEED_CELL_SPAN * ROUTE_STABILIZE_SCALE,
        ROUTE_STABILIZE_WIDTH_CELLS,
    )
    * ROUTE_STABILIZE_CELL_BLOCKS
)
ROUTE_OUTER_COARSE_RADIUS_CELLS = 19
ROUTE_OUTER_RADIUS_SQUARED_BASE = 285.0
ROUTE_OUTER_RADIUS_SQUARED_FLOOR = 291.5
ROUTE_OUTER_RADIUS_WAVES = (
    (40.0, 7, 11, 29),
    (25.0, -17, 5, 103),
    (15.0, 29, -31, 211),
)
ROUTE_OUTER_PHASE_OFFSET_BY_PROFILE_ID = dict(
    (profile["id"], int(profile.get("outerPhase", 0)))
    for profile in ACTIVE_TERRITORY_PROFILES
)
ROUTE_OUTER_PHASE_OFFSET_BY_KEY = dict(
    (profile["coreBiome"], int(profile.get("outerPhase", 0)))
    for profile in ACTIVE_TERRITORY_CONTENT_PROFILES
)
ROUTE_ANCHOR_SAFE_MARGIN_CELLS = 1
ROUTE_CORE_RADIUS_SQUARED_BASE = 48.5
ROUTE_CORE_COARSE_RADIUS_CELLS = 8
ROUTE_CORE_X_BIAS = 1.25
ROUTE_CORE_Z_BIAS = -0.75
ROUTE_CORE_RADIUS_WAVES = (
    (5.6, 31, 17, 47),
    (2.8, 11, -29, 113),
)
ROUTE_CORE_PHASE_OFFSET_BY_PROFILE_ID = dict(
    (profile["id"], int(profile.get("corePhase", 0)))
    for profile in ACTIVE_TERRITORY_PROFILES
)
ROUTE_CORE_PHASE_OFFSET_BY_KEY = dict(
    (profile["coreBiome"], int(profile.get("corePhase", 0)))
    for profile in ACTIVE_TERRITORY_CONTENT_PROFILES
)
ROUTE_OUTER_BODY_ENVELOPE_BLOCKS = (
    (ROUTE_OUTER_COARSE_RADIUS_CELLS * 2 - 1)
    * ROUTE_STABILIZE_CELL_BLOCKS
)
ROUTE_OUTER_MAX_ENVELOPE_BLOCKS = max(
    ROUTE_OUTER_BODY_ENVELOPE_BLOCKS,
    (
        (
            ROUTE_BIOME_COMPANION_CELL_DISTANCE
            * ROUTE_BIOME_COORDINATE_SCALE
            * ROUTE_STABILIZE_SCALE
            + ROUTE_ANCHOR_SAFE_MARGIN_CELLS
        )
        * 2
        + 1
    )
    * ROUTE_STABILIZE_CELL_BLOCKS,
)
# Compatibility names retained for older diagnostics.
ROUTE_ROUNDED_ENVELOPE_BLOCKS = ROUTE_OUTER_BODY_ENVELOPE_BLOCKS
ROUTE_ROUNDED_MAX_ENVELOPE_BLOCKS = ROUTE_OUTER_MAX_ENVELOPE_BLOCKS


def _route_stable_origin(source_local):
    return (
        int(source_local[0])
        * ROUTE_BIOME_COORDINATE_SCALE
        * ROUTE_STABILIZE_SCALE,
        int(source_local[1])
        * ROUTE_BIOME_COORDINATE_SCALE
        * ROUTE_STABILIZE_SCALE,
    )


def _route_wave_sum(world_cell_x, world_cell_z, waves, phase_offset=0):
    return sum(
        float(amplitude)
        * math.sin(
            math.radians(
                int(world_cell_x) * int(x_frequency)
                + int(world_cell_z) * int(z_frequency)
                + int(phase)
                + int(phase_offset)
            )
        )
        for amplitude, x_frequency, z_frequency, phase in waves
    )


def _route_mask_local(world_cell_x, world_cell_z):
    region_size = int(ROUTE_STABILIZE_REGION_CELLS)
    world_cell_x = int(world_cell_x)
    world_cell_z = int(world_cell_z)
    return (
        world_cell_x - (world_cell_x // region_size) * region_size,
        world_cell_z - (world_cell_z // region_size) * region_size,
    )


def _route_outer_phase_offset(route_key):
    if route_key in ROUTE_OUTER_PHASE_OFFSET_BY_PROFILE_ID:
        return ROUTE_OUTER_PHASE_OFFSET_BY_PROFILE_ID[route_key]
    return ROUTE_OUTER_PHASE_OFFSET_BY_KEY[route_key]


def _route_core_phase_offset(route_key):
    if route_key in ROUTE_CORE_PHASE_OFFSET_BY_PROFILE_ID:
        return ROUTE_CORE_PHASE_OFFSET_BY_PROFILE_ID[route_key]
    return ROUTE_CORE_PHASE_OFFSET_BY_KEY[route_key]


def route_companion_mask_contains(
    world_cell_x,
    world_cell_z,
    mask_origin,
    route_key="fire_swamp",
):
    """Return whether one stabilize cell belongs to a route's outer mask."""
    local_x, local_z = _route_mask_local(world_cell_x, world_cell_z)
    delta_x = local_x - int(mask_origin[0])
    delta_z = local_z - int(mask_origin[1])
    phase_offset = _route_outer_phase_offset(route_key)
    radius_squared = max(
        ROUTE_OUTER_RADIUS_SQUARED_FLOOR,
        ROUTE_OUTER_RADIUS_SQUARED_BASE
        + _route_wave_sum(
            world_cell_x,
            world_cell_z,
            ROUTE_OUTER_RADIUS_WAVES,
            phase_offset,
        ),
    )
    return (
        abs(delta_x) < ROUTE_OUTER_COARSE_RADIUS_CELLS
        and abs(delta_z) < ROUTE_OUTER_COARSE_RADIUS_CELLS
        and delta_x * delta_x + delta_z * delta_z < radius_squared
    )


def route_core_mask_contains(
    world_cell_x,
    world_cell_z,
    mask_origin,
    route_key="fire_swamp",
):
    """Return whether one stabilize cell belongs to the noisy inner core."""
    local_x, local_z = _route_mask_local(world_cell_x, world_cell_z)
    delta_x = local_x - int(mask_origin[0])
    delta_z = local_z - int(mask_origin[1])
    radius_squared = ROUTE_CORE_RADIUS_SQUARED_BASE + _route_wave_sum(
        world_cell_x,
        world_cell_z,
        ROUTE_CORE_RADIUS_WAVES,
        _route_core_phase_offset(route_key),
    )
    return (
        abs(delta_x) < ROUTE_CORE_COARSE_RADIUS_CELLS
        and abs(delta_z) < ROUTE_CORE_COARSE_RADIUS_CELLS
        and (
            delta_x * delta_x
            + delta_z * delta_z
            + ROUTE_CORE_X_BIAS * delta_x
            + ROUTE_CORE_Z_BIAS * delta_z
        )
        < radius_squared
    )


ROUTE_STABLE_CORE_MASKS_BY_VARIANT = dict(
    (
        variant,
        dict(
            (route_key, _route_stable_origin(core_local))
            for route_key, core_local in routes.items()
        ),
    )
    for variant, routes in ROUTE_CORE_LOCALS_BY_VARIANT.items()
)
ROUTE_STABLE_COMPANION_MASKS_BY_VARIANT = dict(
    (
        variant,
        dict(
            (
                route_key,
                _route_stable_origin(core_local),
            )
            for route_key, core_local in routes.items()
        ),
    )
    for variant, routes in ROUTE_CORE_LOCALS_BY_VARIANT.items()
)
ROUTE_PROFILE_STABLE_CORE_MASKS_BY_VARIANT = dict(
    (
        variant,
        dict(
            (profile_id, _route_stable_origin(core_local))
            for profile_id, core_local in routes.items()
        ),
    )
    for variant, routes in ROUTE_PROFILE_CORE_LOCALS_BY_VARIANT.items()
)
ROUTE_PROFILE_STABLE_COMPANION_MASKS_BY_VARIANT = dict(
    (
        variant,
        dict(
            (profile_id, _route_stable_origin(core_local))
            for profile_id, core_local in routes.items()
        ),
    )
    for variant, routes in ROUTE_PROFILE_CORE_LOCALS_BY_VARIANT.items()
)

# Compatibility aliases describe the variant-0 Fire Swamp route used by older
# diagnostics. Production generation consumes the per-variant dictionaries.
ROUTE_BIOME_CORE_LOCAL = ROUTE_CORE_LOCALS_BY_VARIANT[0]["fire_swamp"]
ROUTE_BIOME_COMPANION_ANCHOR_LOCALS = (
    ROUTE_COMPANION_LOCALS_BY_VARIANT[0]["fire_swamp"]
)
ROUTE_BIOME_CORE_LOCALS = (ROUTE_BIOME_CORE_LOCAL,)
ROUTE_BIOME_COMPANION_LOCALS = ROUTE_BIOME_COMPANION_ANCHOR_LOCALS
ROUTE_BIOME_COMPANION_BLOCKS = tuple(
    (anchor,)
    for anchor in ROUTE_BIOME_COMPANION_ANCHOR_LOCALS
)


def _route_biome_condition_prelude(region_size, extra_assignments=()):
    """Cache coordinate terms shared by one low-resolution condition."""
    region_size = int(region_size)
    assignments = [
        (
            "temp.region_x",
            "math.floor(variable.worldx / %d)" % region_size,
        ),
        (
            "temp.region_z",
            "math.floor(variable.worldz / %d)" % region_size,
        ),
        (
            "temp.local_x",
            "variable.worldx - (temp.region_x * %d)" % region_size,
        ),
        (
            "temp.local_z",
            "variable.worldz - (temp.region_z * %d)" % region_size,
        ),
        (
            "temp.parity_x",
            "temp.region_x - (math.floor(temp.region_x / 2) * 2)",
        ),
        (
            "temp.parity_z",
            "temp.region_z - (math.floor(temp.region_z / 2) * 2)",
        ),
        (
            "temp.route_hash",
            "(temp.region_x * 3) + temp.region_z + "
            "((temp.parity_x * temp.parity_z) * 2)",
        ),
        (
            "temp.variant",
            "temp.route_hash - (math.floor(temp.route_hash / 4) * 4)",
        ),
    ]
    assignments.extend(extra_assignments)
    return " ".join(
        "%s = %s;" % (name, expression)
        for name, expression in assignments
    )


def _route_biome_variant_condition(
    region_size,
    clauses_by_variant,
    extra_assignments=(),
):
    """Return a negative-safe four-variant coordinate condition."""
    selected_clause = clauses_by_variant.get(ROUTE_LAYOUT_VARIANTS[-1], "0")
    for variant in reversed(ROUTE_LAYOUT_VARIANTS[:-1]):
        selected_clause = "((%s==%d)?(%s):(%s))" % (
            "temp.variant",
            int(variant),
            clauses_by_variant.get(variant, "0"),
            selected_clause,
        )
    return "%s return (%s) ? 0 : -1;" % (
        _route_biome_condition_prelude(
            region_size,
            extra_assignments,
        ),
        selected_clause,
    )


def _route_layout_variant_molang(region_x, region_z):
    parity_x = "(%s - (math.floor(%s / 2) * 2))" % (
        region_x,
        region_x,
    )
    parity_z = "(%s - (math.floor(%s / 2) * 2))" % (
        region_z,
        region_z,
    )
    hashed = "((%s * 3) + %s + ((%s * %s) * 2))" % (
        region_x,
        region_z,
        parity_x,
        parity_z,
    )
    return "(%s - (math.floor(%s / 4) * 4))" % (hashed, hashed)


def route_biome_seed_condition(seed_boxes_by_variant):
    """Return one position-scaled key or cardinal companion seed."""
    region_size = int(ROUTE_BIOME_REGION_CELLS)
    local_x = "temp.local_x"
    local_z = "temp.local_z"
    clauses = {}
    for variant in ROUTE_LAYOUT_VARIANTS:
        boxes = seed_boxes_by_variant.get(variant, ())
        terms = []
        for box in boxes:
            if int(box[2]) == int(box[0]) + 1 and int(box[3]) == int(box[1]) + 1:
                terms.append(
                    "((%s==%d)&&(%s==%d))"
                    % (local_x, int(box[0]), local_z, int(box[1]))
                )
            else:
                terms.append(
                    "((%s>=%d)&&(%s<%d)&&(%s>=%d)&&(%s<%d))"
                    % (
                        local_x,
                        int(box[0]),
                        local_x,
                        int(box[2]),
                        local_z,
                        int(box[1]),
                        local_z,
                        int(box[3]),
                    )
                )
        clauses[variant] = "||".join(terms) or "0"
    return _route_biome_variant_condition(region_size, clauses)


def route_biome_stabilize_condition(boxes_by_variant):
    """Return bounded 128-block interiors after two route zooms."""
    region_size = int(ROUTE_STABILIZE_REGION_CELLS)
    local_x = "temp.local_x"
    local_z = "temp.local_z"
    clauses = {}
    for variant in ROUTE_LAYOUT_VARIANTS:
        clauses[variant] = " || ".join(
            "((%s >= %d) && (%s < %d) && (%s >= %d) && (%s < %d))"
            % (
                local_x,
                int(box[0]),
                local_x,
                int(box[2]),
                local_z,
                int(box[1]),
                local_z,
                int(box[3]),
            )
            for box in boxes_by_variant.get(variant, ())
        ) or "0"
    return _route_biome_variant_condition(region_size, clauses)


def _route_molang_wave_sum(waves, phase_offset=0):
    terms = []
    for amplitude, x_frequency, z_frequency, phase in waves:
        angle = (
            "((variable.worldx * %d) + (variable.worldz * %d) + %d)"
            % (
                int(x_frequency),
                int(z_frequency),
                int(phase) + int(phase_offset),
            )
        )
        terms.append("(math.sin(%s) * %s)" % (angle, float(amplitude)))
    return " + ".join(terms) or "0"


def _route_stabilize_local_expressions():
    return ("temp.local_x", "temp.local_z")


def route_biome_companion_stabilize_condition(
    mask_origins_by_variant,
    route_key="fire_swamp",
):
    """Return one deterministic noisy outer territory at stabilize scale."""
    region_size = int(ROUTE_STABILIZE_REGION_CELLS)
    local_x, local_z = _route_stabilize_local_expressions()
    phase_offset = _route_outer_phase_offset(route_key)
    radius_squared = "math.max(%s, (%s + %s))" % (
        ROUTE_OUTER_RADIUS_SQUARED_FLOOR,
        ROUTE_OUTER_RADIUS_SQUARED_BASE,
        _route_molang_wave_sum(
            ROUTE_OUTER_RADIUS_WAVES,
            phase_offset,
        ),
    )
    clauses = {}
    for variant in ROUTE_LAYOUT_VARIANTS:
        terms = []
        for origin_x, origin_z in mask_origins_by_variant.get(variant, ()):
            delta_x = "(%s - %d)" % (local_x, int(origin_x))
            delta_z = "(%s - %d)" % (local_z, int(origin_z))
            distance_squared = "((%s * %s) + (%s * %s))" % (
                delta_x,
                delta_x,
                delta_z,
                delta_z,
            )
            noisy_outer = (
                "((math.abs(%s) < %d) && (math.abs(%s) < %d) "
                "&& (%s < temp.outer_radius_sq))"
                % (
                    delta_x,
                    ROUTE_OUTER_COARSE_RADIUS_CELLS,
                    delta_z,
                    ROUTE_OUTER_COARSE_RADIUS_CELLS,
                    distance_squared,
                )
            )
            terms.append(noisy_outer)
        clauses[variant] = " || ".join(terms) or "0"
    return _route_biome_variant_condition(
        region_size,
        clauses,
        (
            ("temp.outer_radius_sq", radius_squared),
        ),
    )


def route_biome_core_stabilize_condition(
    mask_origins_by_variant,
    route_key="fire_swamp",
):
    """Return one deterministic noisy inner route core at stabilize scale."""
    region_size = int(ROUTE_STABILIZE_REGION_CELLS)
    local_x, local_z = _route_stabilize_local_expressions()
    radius_squared = "(%s + %s)" % (
        ROUTE_CORE_RADIUS_SQUARED_BASE,
        _route_molang_wave_sum(
            ROUTE_CORE_RADIUS_WAVES,
            _route_core_phase_offset(route_key),
        ),
    )
    clauses = {}
    for variant in ROUTE_LAYOUT_VARIANTS:
        terms = []
        for origin_x, origin_z in mask_origins_by_variant.get(variant, ()):
            delta_x = "(%s - %d)" % (local_x, int(origin_x))
            delta_z = "(%s - %d)" % (local_z, int(origin_z))
            terms.append(
                "((math.abs(%s) < %d) && (math.abs(%s) < %d) "
                "&& (((%s * %s) + (%s * %s) + (%s * %s) + (%s * %s)) < %s))"
                % (
                    delta_x,
                    ROUTE_CORE_COARSE_RADIUS_CELLS,
                    delta_z,
                    ROUTE_CORE_COARSE_RADIUS_CELLS,
                    delta_x,
                    delta_x,
                    delta_z,
                    delta_z,
                    delta_x,
                    ROUTE_CORE_X_BIAS,
                    delta_z,
                    ROUTE_CORE_Z_BIAS,
                    "temp.radius_squared",
                )
            )
        clauses[variant] = " || ".join(terms) or "0"
    return _route_biome_variant_condition(
        region_size,
        clauses,
        (("temp.radius_squared", radius_squared),),
    )


def route_biome_stencil_condition(region_parity, local_positions):
    """Return a negative-coordinate-safe Molang route stencil condition."""
    region_size = int(ROUTE_BIOME_REGION_CELLS)
    region_x = "math.floor(variable.worldx / %d)" % region_size
    region_z = "math.floor(variable.worldz / %d)" % region_size
    local_x = "(variable.worldx - (%s * %d))" % (region_x, region_size)
    local_z = "(variable.worldz - (%s * %d))" % (region_z, region_size)
    region_sum = "(%s + %s)" % (region_x, region_z)
    parity = "(%s - (math.floor(%s / 2) * 2)) == %d" % (
        region_sum,
        region_sum,
        int(region_parity),
    )
    positions = " || ".join(
        "((%s == %d) && (%s == %d))"
        % (local_x, int(local_pos[0]), local_z, int(local_pos[1]))
        for local_pos in local_positions
    )
    return "(%s) && (%s) ? 0 : -1" % (parity, positions)
# query.get_neighborhood_is_biome uses the inherited vanilla BiomeType enum.
BIOME_QUERY_TYPES = {
    "swamp": 6,
    "fire_swamp": 134,
    "dark_forest": 157,
    "dark_forest_center": 160,
}
ORDINARY_FOREST_BIOMES = frozenset(
    entry["identifier"]
    for entry in BASE_SOURCE_BIOMES
    if entry["key"] != "spooky_forest"
)
AQUATIC_BIOMES = frozenset(
    entry["identifier"]
    for entry in BIOMES
    if entry["key"] in AQUATIC_BIOME_KEYS
)
# Upstream root veins run in every standard surface biome, including Spooky
# Forest, but are absent from its lake and stream biome generation settings.
UNDERGROUND_ROOT_BIOMES = frozenset(
    entry["identifier"] for entry in BASE_SOURCE_BIOMES
)

# Twilight Forest's SeamLayer leaves open/dry biomes and the two related
# mushroom forests directly connected.  Every other pair below receives the
# stream transition after the land layout has been enlarged into broad regions.
STREAM_TRANSITION_KEY_PAIRS = (
    ("forest", "dense_forest"),
    ("forest", "mushroom_forest"),
    ("forest", "firefly_forest"),
    ("forest", "dense_mushroom_forest"),
    ("forest", "enchanted_forest"),
    ("forest", "spooky_forest"),
    ("dense_forest", "mushroom_forest"),
    ("dense_forest", "firefly_forest"),
    ("dense_forest", "dense_mushroom_forest"),
    ("dense_forest", "enchanted_forest"),
    ("dense_forest", "spooky_forest"),
    ("mushroom_forest", "firefly_forest"),
    ("mushroom_forest", "enchanted_forest"),
    ("mushroom_forest", "spooky_forest"),
    ("firefly_forest", "dense_mushroom_forest"),
    ("firefly_forest", "enchanted_forest"),
    ("firefly_forest", "spooky_forest"),
    ("dense_mushroom_forest", "enchanted_forest"),
    ("dense_mushroom_forest", "spooky_forest"),
    ("enchanted_forest", "spooky_forest"),
    ("swamp", "forest"),
    ("swamp", "dense_forest"),
    ("swamp", "oak_savannah"),
    ("swamp", "mushroom_forest"),
    ("swamp", "firefly_forest"),
    ("swamp", "dense_mushroom_forest"),
    ("swamp", "enchanted_forest"),
    ("swamp", "clearing"),
    ("swamp", "spooky_forest"),
    ("dark_forest", "forest"),
    ("dark_forest", "dense_forest"),
    ("dark_forest", "mushroom_forest"),
    ("dark_forest", "firefly_forest"),
    ("dark_forest", "dense_mushroom_forest"),
    ("dark_forest", "enchanted_forest"),
    ("dark_forest", "spooky_forest"),
    ("dark_forest", "swamp"),
    ("dark_forest", "fire_swamp"),
)
STREAM_TRANSITION_IDENTIFIER_PAIRS = tuple(
    (
        BIOMES_BY_KEY[first_key]["identifier"],
        BIOMES_BY_KEY[second_key]["identifier"],
    )
    for first_key, second_key in STREAM_TRANSITION_KEY_PAIRS
)

# Structure eligibility is deliberately stricter than the general Twilight
# biome tag.  Streams and lakes must never receive terrain-bound ruins, while
# spooky forest reserves its native feature slot for the graveyard.
SMALL_RUIN_BIOMES = frozenset(
    BIOMES_BY_KEY[key]["identifier"]
    for key in (
        "forest",
        "dense_forest",
        "oak_savannah",
        "mushroom_forest",
        "firefly_forest",
        "dense_mushroom_forest",
        "enchanted_forest",
        "clearing",
        "swamp",
    )
)
LARGE_LANDMARK_BIOMES = frozenset(
    BIOMES_BY_KEY[key]["identifier"]
    for key in (
        "forest",
        "dense_forest",
        "oak_savannah",
        "mushroom_forest",
        "firefly_forest",
        "dense_mushroom_forest",
        "clearing",
        "spooky_forest",
    )
)
SPECIAL_LANDMARK_BY_BIOME = {
    BIOMES_BY_KEY["enchanted_forest"]["identifier"]: "quest_grove",
}
for _territory_profile in ACTIVE_TERRITORY_CONTENT_PROFILES:
    SPECIAL_LANDMARK_BY_BIOME[
        BIOMES_BY_KEY[_territory_profile["coreBiome"]]["identifier"]
    ] = _territory_profile["mainLandmark"]
    SPECIAL_LANDMARK_BY_BIOME[
        BIOMES_BY_KEY[_territory_profile["companionBiome"]]["identifier"]
    ] = _territory_profile["companionLandmark"]
# The upstream biome tag allows the ordinary variety landmarks in dense
# mushroom forest too. Mushroom towers therefore replace only a variety slot
# whose original landmark has not been ported, instead of replacing every
# landmark center in this biome.
UNPORTED_LANDMARK_FALLBACK_BY_BIOME = {
    BIOMES_BY_KEY["dense_mushroom_forest"]["identifier"]: "mushroom_tower",
}
