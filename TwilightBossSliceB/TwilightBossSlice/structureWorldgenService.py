# -*- coding: utf-8 -*-
"""Chunk-local placement service for Twilight Forest ruins and landmarks."""

import base64
import copy
import collections
import json
import math
import zlib

import TwilightBossSlice.biome_catalog as biome_catalog
import TwilightBossSlice.magic_map_logic as magic_map_logic
import TwilightBossSlice.knight_route_logic as knight_route_logic
import TwilightBossSlice.ruin_worldgen_logic as ruin_logic
import TwilightBossSlice.ruin_catalog_data as ruin_catalog_data


LEDGER_KEY = "tf_slice:ruin_landmarks_v1"
LEDGER_STORAGE_FORMAT = "sharded_json_v2"
LEGACY_LEDGER_STORAGE_FORMAT = "sharded_v1"
LEDGER_SHARD_MAX_WEIGHT = 3500
WORLD_SEED_KEY = "tf_slice:ruin_world_seed_v1"
MAX_PIECES_PER_TICK = 1
MAX_RETRIES = 3
SCAN_INTERVAL_TICKS = 40
PLAYER_BACKFILL_RADIUS = 64
MAX_PLAYER_BACKFILLS_PER_SCAN = 4
HOLLOW_HILL_SPAWN_INTERVAL_TICKS = 100
MAX_HOLLOW_HILL_GROUPS_PER_SCAN = 2
LICH_TOWER_SPAWN_INTERVAL_TICKS = 100
LICH_TOWER_LOCAL_MONSTER_CAP = 12
CONTROLLED_STRUCTURE_SPAWN_INTERVAL_TICKS = 100
MAX_CONTROLLED_STRUCTURE_GROUPS_PER_SCAN = 2
CONTROLLED_SPAWN_MIN_COOLDOWN_TICKS = 200
CONTROLLED_SPAWN_MAX_COOLDOWN_TICKS = 400
CONTROLLED_SPAWN_CHANCE_DENOMINATOR = 2
CONTROLLED_SPAWN_MIN_PLAYER_DISTANCE_SQUARED = 24.0 * 24.0
CONTROLLED_SPAWN_MAX_PLAYER_DISTANCE_SQUARED = 48.0 * 48.0
CONTROLLED_STRUCTURE_CAPS = {
    "stronghold": 18,
    "lower": 18,
    "roof": 6,
    "water": 8,
}
CONTROLLED_STRUCTURE_FLYING_MOBS = frozenset(
    ("tf_slice:mini_ghast", "tf_slice:tower_ghast")
)
CONTROLLED_STRUCTURE_WATER_MOBS = frozenset(("minecraft:squid",))
CONTROLLED_STRUCTURE_TALL_MOBS = frozenset(
    ("tf_slice:carminite_golem", "tf_slice:minotaur")
)
DARK_FOREST_BIOME = biome_catalog.BIOMES_BY_KEY["dark_forest"]["identifier"]
DARK_FOREST_SPAWN_INTERVAL_TICKS = 40
DARK_FOREST_LOCAL_MONSTER_CAP = 18
MAX_DARK_FOREST_GROUPS_PER_SCAN = 2
DARK_FOREST_CONTROLLED_SPAWNS = (
    ("minecraft:enderman", 2, 1, 2),
    ("minecraft:zombie", 5, 1, 2),
    ("minecraft:skeleton", 5, 1, 2),
    ("tf_slice:mist_wolf", 5, 1, 1),
    ("tf_slice:skeleton_druid", 5, 1, 1),
    ("tf_slice:king_spider", 1, 1, 1),
    ("tf_slice:kobold", 10, 1, 3),
    ("minecraft:witch", 2, 1, 1),
)
DARK_FOREST_CONTROLLED_MOBS = frozenset(
    entry[0] for entry in DARK_FOREST_CONTROLLED_SPAWNS
)
AREA_WARMUP_TICKS = 20
AREA_LOAD_MARGIN = 80
AREA_CHUNK_READY_RECHECK_TICKS = 10
AUTOMATIC_JOB_PLAYER_RADIUS = 192
MAX_SLICE_READY_CHECKS_PER_JOB = 4
PIECE_CHECKPOINT_COUNT = 8
MAX_NATIVE_HANDOFFS = 512
MAX_NATIVE_HANDOFFS_PER_TICK = 8
LANDMARK_TRIGGER_STRUCTURE = "tf_slice:ruin_landmark_trigger"
LANDMARK_NOOP_STRUCTURE = "tf_slice:ruin_landmark_noop"
HOLLOW_TREE_TRIGGER_STRUCTURE = "tf_slice:hollow_tree_chunk_trigger"
DARK_TOWER_CANOPY_CLEANUP_TRIGGER_STRUCTURE = (
    "tf_slice:dark_tower_canopy_cleanup_trigger"
)
DARK_TOWER_CANOPY_CLEANUP_POLICY_VERSION = 1
DARK_TOWER_CANOPY_CLEANUP_DEFAULT_SETTLE_TICKS = 80
DARK_TOWER_CANOPY_CLEANUP_DEFAULT_BUDGET = 64
DARK_TOWER_CANOPY_CLEANUP_CHUNK_MARGIN = 16
DARK_TOWER_CANOPY_CLEANUP_CHECKPOINT_BLOCKS = 2048
DARK_TOWER_CANOPY_LEAF_BLOCKS = frozenset(
    (
        "tf_slice:hardened_dark_leaves",
        "tf_slice:hardened_dark_leaves_center",
    )
)
LANDMARK_SURFACE_WATCHDOG_STRUCTURE = (
    "tf_slice:ruin_landmark_surface_watchdog"
)
SURFACE_LANDMARK_TRIGGER_BY_MODE = {
    "ordinary": "tf_slice:ruin_landmark_surface_ordinary",
    "dense_mushroom": (
        "tf_slice:ruin_landmark_surface_dense_mushroom"
    ),
    "enchanted": "tf_slice:ruin_landmark_surface_enchanted",
    "swamp": "tf_slice:ruin_landmark_surface_swamp",
    "fire_swamp": "tf_slice:ruin_landmark_surface_fire_swamp",
    "dark_forest": "tf_slice:ruin_landmark_surface_dark_forest",
    "dark_forest_center": (
        "tf_slice:ruin_landmark_surface_dark_forest_center"
    ),
}
SURFACE_LANDMARK_TRIGGER_CONFIG = dict(
    (structure_name, mode)
    for mode, structure_name in SURFACE_LANDMARK_TRIGGER_BY_MODE.items()
)
SURFACE_LANDMARK_MODE_BY_TRIGGER = dict(
    SURFACE_LANDMARK_TRIGGER_CONFIG
)
ROUTE_SURFACE_LANDMARK_MODES = frozenset(
    ("swamp", "fire_swamp", "dark_forest", "dark_forest_center")
)
MAX_SURFACE_LANDMARK_HANDOFFS = 128
MAX_SURFACE_LANDMARK_HANDOFFS_PER_TICK = 8
MAX_LANDMARK_TRIGGERS = 128
MAX_LANDMARK_TRIGGERS_PER_TICK = 4
MAX_LANDMARK_DISCOVERY_RETRIES = 90
MAX_TERRAIN_BLOCKS_PER_TICK = 32
MAX_TERRAIN_COLUMNS_PER_TICK = 8
TERRAIN_CHECKPOINT_COLUMNS = 64
MAX_SURFACE_EDGE_BLOCKS_PER_TICK = 48
MAX_SURFACE_EDGE_COLUMNS_PER_TICK = 12
MAX_SURFACE_EDGE_SCAN_PER_TICK = 256
SURFACE_EDGE_CHECKPOINT_COLUMNS = 256
MAX_HOLLOW_HILL_CARVE_BLOCKS_PER_TICK = 256
HOLLOW_HILL_CARVE_CHECKPOINT_BLOCKS = 2048
HOLLOW_HILL_CARVE_POLICY_VERSION = 2
CHUNK_ASSEMBLY_POLICY_VERSION = 2
COURTYARD_LAYOUT_POLICY_VERSION = 5
COURTYARD_SURFACE_POLICY_VERSION = 2
SURFACE_EDGE_BLEND_POLICY_VERSION = 1
SURFACE_TILE_SETTLE_TICKS = 40
MAX_TERRAIN_SURFACE_SCAN = 96
MAX_TERRAIN_DECORATION_CLEARANCE = 4
COURTYARD_VEGETATION_CLEARANCE = 48
COURTYARD_REPAIR_STRUCTURE_CLEARANCE = 16
COURTYARD_BOSS_CONFIRMATION_TICKS = 40
COURTYARD_SPAWNER_EVENT_INTERVAL_TICKS = 20
COURTYARD_SPAWNER_BLOCK = "tf_slice:naga_boss_spawner"
MINOSHROOM_SPAWNER_BLOCK = "tf_slice:minoshroom_boss_spawner"
HYDRA_SPAWNER_BLOCK = "tf_slice:hydra_boss_spawner"
KNIGHT_PHANTOM_SPAWNER_BLOCK = "tf_slice:knight_phantom_boss_spawner"
UR_GHAST_SPAWNER_BLOCK = "tf_slice:ur_ghast_boss_spawner"
COURTYARD_EMPTY_COLLISION_BLOCKS = frozenset(
    (
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
        "minecraft:water",
        "minecraft:flowing_water",
        "minecraft:tallgrass",
        "minecraft:double_plant",
        "minecraft:vine",
        "minecraft:snow_layer",
    )
)
LICH_SPAWNER_BLOCK = "tf_slice:lich_boss_spawner"
DEFAULT_LOCATE_RADIUS = 4096
MAX_LOCATE_RADIUS = 8192
SLOPE_POLICY_VERSION = 4
BIOME_POLICY_VERSION = 3
LANDMARK_OVERLAP_POLICY_VERSION = 2
DEFAULT_LANDMARK_SLOPE_LIMIT = 8
LANDMARK_SLOPE_LIMITS = {
    "hollow_hill": 16,
    "naga_courtyard": 12,
    "lich_tower": 12,
    "labyrinth": 8,
    "hydra_lair": 12,
    "knight_stronghold": 12,
}
SUPPORTED_VARIETY = set(
    (
        "small_hill",
        "medium_hill",
        "large_hill",
        "hedge_maze",
        "naga_courtyard",
        "lich_tower",
    )
)
TERRAIN_ADAPTING_LANDMARKS = frozenset(
    set(SUPPORTED_VARIETY) | set(("labyrinth", "hydra_lair", "dark_tower"))
)
BOSS_VARIETY_LANDMARKS = frozenset(
    ("naga_courtyard", "lich_tower", "labyrinth", "hydra_lair", "dark_tower")
)
LANDMARK_CLEARANCE_CHUNKS = {
    "small_hill": 1,
    "medium_hill": 2,
    "large_hill": 3,
    "hedge_maze": 2,
    "naga_courtyard": 3,
    "lich_tower": 2,
    "quest_grove": 1,
    "mushroom_tower": 2,
    "labyrinth": 3,
    "hydra_lair": 2,
    "knight_stronghold": 3,
    "dark_tower": 1,
}
PERSISTENT_TEMPLATE_LANDMARKS = frozenset(
    ("knight_stronghold", "dark_tower")
)
HOLLOW_TREE_CLEARANCE_CHUNKS = dict(
    (kind, radius + 2)
    for kind, radius in LANDMARK_CLEARANCE_CHUNKS.items()
)
SPECIAL_BIOMES = biome_catalog.SPECIAL_LANDMARK_BY_BIOME
HOLLOW_HILL_SPAWN_AIR_BLOCKS = set(
    (
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
    )
)
NATIVE_REPLACEABLE_BLOCKS = set(
    (
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
        "minecraft:water",
        "minecraft:flowing_water",
        "minecraft:tallgrass",
        "minecraft:double_plant",
        "minecraft:vine",
        "minecraft:snow_layer",
        "minecraft:deadbush",
        "minecraft:brown_mushroom",
        "minecraft:red_mushroom",
        "minecraft:yellow_flower",
        "minecraft:red_flower",
        "tf_slice:mayapple",
    )
)
TERRAIN_GROUND_BLOCKS = set(
    (
        "minecraft:grass_block",
        "minecraft:dirt",
        "minecraft:coarse_dirt",
        "minecraft:podzol",
        "minecraft:mycelium",
        "minecraft:moss_block",
        "minecraft:stone",
        "minecraft:deepslate",
        "minecraft:gravel",
        "minecraft:sand",
        "minecraft:red_sand",
        "minecraft:clay",
        "minecraft:snow",
        "minecraft:bedrock",
    )
)
TERRAIN_DECORATION_BLOCKS = set(NATIVE_REPLACEABLE_BLOCKS)
TERRAIN_DECORATION_BLOCKS.update(
    (
        "minecraft:grass",
        "minecraft:leaves",
        "minecraft:leaves2",
        "minecraft:log",
        "minecraft:log2",
        "minecraft:oak_leaves",
        "minecraft:spruce_leaves",
        "minecraft:birch_leaves",
        "minecraft:jungle_leaves",
        "minecraft:acacia_leaves",
        "minecraft:dark_oak_leaves",
        "minecraft:oak_log",
        "minecraft:spruce_log",
        "minecraft:birch_log",
        "minecraft:jungle_log",
        "minecraft:acacia_log",
        "minecraft:dark_oak_log",
        "minecraft:brown_mushroom_block",
        "minecraft:red_mushroom_block",
        "tf_slice:twilight_oak_leaves",
        "tf_slice:twilight_oak_log",
        "tf_slice:canopy_leaves",
        "tf_slice:canopy_log",
        "tf_slice:rainbow_oak_leaves",
        "tf_slice:fallen_leaves",
        "tf_slice:fiddlehead",
        "tf_slice:mushgloom",
        "tf_slice:firefly",
    )
)
COURTYARD_REPAIRABLE_STRUCTURE_BLOCKS = frozenset(
    (
        "minecraft:black_terracotta",
        "minecraft:chiseled_stone_bricks",
        "minecraft:cobblestone",
        "minecraft:cobblestone_slab",
        "minecraft:cobblestone_wall",
        "minecraft:cracked_stone_bricks",
        "minecraft:fire",
        "minecraft:iron_bars",
        "minecraft:magma",
        "minecraft:mossy_cobblestone",
        "minecraft:mossy_stone_bricks",
        "minecraft:polished_andesite",
        "minecraft:sandstone_slab",
        "minecraft:smooth_stone_slab",
        "minecraft:stone_brick_slab",
        "minecraft:stone_brick_stairs",
        "minecraft:stone_bricks",
        "minecraft:stone_stairs",
        "tf_slice:cracked_etched_nagastone",
        "tf_slice:cracked_nagastone_pillar",
        "tf_slice:cracked_nagastone_stairs_left",
        "tf_slice:cracked_nagastone_stairs_right",
        "tf_slice:etched_nagastone",
        "tf_slice:mossy_etched_nagastone",
        "tf_slice:mossy_nagastone_pillar",
        "tf_slice:mossy_nagastone_stairs_left",
        "tf_slice:mossy_nagastone_stairs_right",
        "tf_slice:naga_boss_spawner",
        "tf_slice:nagastone",
        "tf_slice:nagastone_head",
        "tf_slice:nagastone_pillar",
        "tf_slice:nagastone_stairs_left",
        "tf_slice:nagastone_stairs_right",
        "tf_slice:spiral_bricks",
    )
)
try:
    INTEGER_TYPES = (int, long)
except NameError:  # pragma: no cover - Python 3 test tooling
    INTEGER_TYPES = (int,)

try:
    TEXT_TYPES = (basestring,)
except NameError:  # pragma: no cover - Python 3 test tooling
    TEXT_TYPES = (str,)


def _ledger_shard_key(generation, index):
    return "%s:shard:%d:%03d" % (
        LEDGER_KEY,
        int(generation),
        int(index),
    )


def _load_catalog_document():
    # ModSDK may copy the Python package outside the behavior-pack directory,
    # so __file__ cannot reliably locate sibling structure resources.
    return json.loads(ruin_catalog_data.CATALOG_JSON)


def _load_catalog():
    document = _load_catalog_document()
    return dict((entry["id"], entry) for entry in document["structures"])


def _load_structure_aliases():
    aliases = _load_catalog_document().get("structureAliases", {})
    if not isinstance(aliases, dict):
        return {}
    return dict((str(key), str(value)) for key, value in aliases.items())


def _stable_seed(value):
    """FNV-1a is stable across Python 2/3 and ModSDK process restarts."""
    result = 2166136261
    for character in str(value):
        result ^= ord(character)
        result = (result * 16777619) & 0xFFFFFFFF
    if result >= 0x80000000:
        result -= 0x100000000
    return result


def _resolve_structure_reference(reference, aliases=None):
    current = str(reference)
    mapping = aliases if isinstance(aliases, dict) else {}
    visited = set()
    while current in mapping:
        if current in visited:
            raise ValueError("ruin structure alias cycle at %s" % current)
        visited.add(current)
        current = str(mapping[current])
    if current in visited:
        raise ValueError("ruin structure alias cycle at %s" % current)
    prefix = "tf_slice/ruins/"
    if not current.startswith(prefix):
        raise ValueError("invalid ruin structure reference: %s" % current)
    return current


def _structure_engine_name(reference, aliases=None):
    resolved = _resolve_structure_reference(reference, aliases)
    return "tf_slice:%s" % resolved[len("tf_slice/") :]


class StructureWorldgenService(object):
    """Maps native worldgen features and runs explicit debug placement."""

    def __init__(
        self,
        component_factory,
        level_id,
        dimension_id,
        entity_spawner=None,
        boss_spawner=None,
        boss_confirmer=None,
    ):
        self._factory = component_factory
        self._level_id = level_id
        self._dimension_id = int(dimension_id)
        self._structure_aliases = _load_structure_aliases()
        self._catalog = _load_catalog()
        self._native_structure_index = (
            self._build_native_structure_index()
        )
        self._extra = component_factory.CreateExtraData(level_id)
        self._chunk = component_factory.CreateChunkSource(level_id)
        self._game = component_factory.CreateGame(level_id)
        self._biome = component_factory.CreateBiome(level_id)
        self._block = component_factory.CreateBlockInfo(level_id)
        try:
            self._block_state = component_factory.CreateBlockState(level_id)
        except Exception:
            self._block_state = None
        self._feature = component_factory.CreateFeature(level_id)
        self._ledger_storage_generation = 0
        self._ledger = self._load_ledger()
        self._courtyard_job_keys = set()
        self._boss_job_keys = set()
        self._knight_group_job_keys = set()
        self._hollow_hill_job_keys = set()
        self._surface_blend_job_keys = set()
        self._rebuild_runtime_job_indexes()
        self._manual_jobs = []
        self._native_structure_handoffs = collections.deque()
        self._surface_landmark_handoffs = collections.deque()
        self._pending_surface_landmark_centers = set()
        self._pending_surface_landmark_tiles = set()
        self._landmark_chunk_handoffs = collections.deque()
        self._pending_landmark_centers = set()
        self._dropped_native_handoffs = 0
        self._dropped_surface_landmark_handoffs = 0
        self._accepted_surface_landmark_tiles = 0
        self._dropped_landmark_triggers = 0
        self._failed_landmark_discoveries = 0
        self._accepted_chunk_generation_events = 0
        self._accepted_chunk_load_events = 0
        self._accepted_player_backfills = 0
        self._accepted_structure_triggers = 0
        self._rejected_native_collisions = 0
        self._entity_spawner = entity_spawner
        self._boss_spawner = boss_spawner or entity_spawner
        self._boss_confirmer = boss_confirmer
        self._hill_spawn_groups = 0
        self._hill_spawn_entities = 0
        self._hill_spawn_query_failures = 0
        self._lich_tower_spawn_groups = 0
        self._lich_tower_spawn_entities = 0
        self._labyrinth_spawn_groups = 0
        self._labyrinth_spawn_entities = 0
        self._controlled_structure_spawn_groups = 0
        self._controlled_structure_spawn_entities = 0
        self._controlled_structure_spawn_groups_by_kind = {}
        self._controlled_structure_spawn_entities_by_kind = {}
        self._controlled_spawn_next_ticks = {}
        self._dark_forest_spawn_groups = 0
        self._dark_forest_spawn_entities = 0
        self._courtyard_marker_tick_scans = {}
        self._ledger_persist_failures = 0
        self._last_ledger_persist_error = None
        self._chunk_ready_waits = 0
        self._hill_carves_started = 0
        self._hill_carves_completed = 0
        self._hill_carve_blocks = 0
        self._dark_tower_canopy_blocks_checked = 0
        self._dark_tower_canopy_leaves_removed = 0
        self._dark_tower_canopy_jobs_completed = 0
        self._areas = {}
        self._area_sequence = 0
        self._scheduled_job_key = None
        self._current_tick = 0
        self._world_seed = self._load_or_create_world_seed()
        self._whitelisted_structures = []
        self._register_structure_feature_whitelist()

    @staticmethod
    def _controlled_spawns_for_variant(entry, variant, existing=None):
        base = entry.get("controlledSpawns") if isinstance(entry, dict) else None
        contract = copy.deepcopy(base) if isinstance(base, dict) else {}
        if isinstance(existing, dict):
            for key, value in existing.items():
                contract[key] = copy.deepcopy(value)
        offsets = (
            variant.get("controlledSpawnOffsets")
            if isinstance(variant, dict)
            else None
        )
        if isinstance(offsets, list):
            contract["interiorOffsets"] = copy.deepcopy(offsets)
        return contract

    def _load_ledger(self):
        try:
            value = self._extra.GetExtraData(LEDGER_KEY)
        except Exception as error:
            print "[TwilightBossSlice] ruin ledger load failed:", error
            value = None
        if isinstance(value, TEXT_TYPES):
            try:
                value = json.loads(value)
            except (TypeError, ValueError) as error:
                print (
                    "[TwilightBossSlice] ruin ledger manifest decode failed:",
                    error,
                )
                return {}
        if isinstance(value, dict) and value.get("format") in (
            LEDGER_STORAGE_FORMAT,
            LEGACY_LEDGER_STORAGE_FORMAT,
        ):
            try:
                generation = int(value.get("generation", 0))
                shard_count = int(value.get("shards", 0))
                if shard_count < 0 or shard_count > 4096:
                    raise ValueError("invalid shard count")
                storage_format = value.get("format")
                if storage_format == LEDGER_STORAGE_FORMAT:
                    encoded_chunks = []
                    for index in range(shard_count):
                        shard = self._extra.GetExtraData(
                            _ledger_shard_key(generation, index)
                        )
                        if not isinstance(shard, TEXT_TYPES):
                            raise ValueError(
                                "missing ledger text shard %d" % index
                            )
                        encoded_chunks.append(shard)
                    encoded = "".join(encoded_chunks)
                    compressed = base64.b64decode(encoded)
                    serialized = zlib.decompress(compressed)
                    if not isinstance(serialized, str):
                        serialized = serialized.decode("utf-8")
                    restored = json.loads(serialized)
                    if not isinstance(restored, dict):
                        raise ValueError("decoded ledger is not a dictionary")
                else:
                    restored = {}
                    for index in range(shard_count):
                        shard = self._extra.GetExtraData(
                            _ledger_shard_key(generation, index)
                        )
                        if not isinstance(shard, dict):
                            raise ValueError(
                                "missing legacy ledger shard %d" % index
                            )
                        restored.update(shard)
                value = restored
                self._ledger_storage_generation = generation
            except Exception as error:
                print (
                    "[TwilightBossSlice] sharded ruin ledger load failed:",
                    error,
                )
                return {}
        if not isinstance(value, dict):
            return {}
        cleaned = {}
        for key, job in value.items():
            if not isinstance(job, dict):
                continue
            copied = copy.deepcopy(job)
            if (
                str(key).startswith("native:")
                and copied.get("state") != "complete"
            ):
                # Before the chunk-local worldgen policy, every accepted
                # placed-feature token became a persistent construction job
                # with an 80-block forced-load margin. Those jobs are unsafe
                # to resume because loading them recursively discovers more
                # jobs. Completed entries are location records and remain.
                continue
            if copied.get("surfaceGenerated"):
                # Surface-native terrain is final before the chunk leaves
                # worldgen. Retire persisted 0.10.x edge writers so upgrading
                # cannot resume visible terrain edits beside a player.
                copied.pop("edgeBlend", None)
                copied["terrainAdaptationStage"] = "surface_pass"
                self._refresh_surface_landmark_state(copied)
            reason = copied.get("reason")
            # A ledger slot is an immutable record of what this world saw.
            # New landmark support applies only to centers with no record;
            # even old fallback/failure decisions must not mutate explored
            # terrain into a different landmark after a pack upgrade.
            retry_obsolete = False
            if reason == "terrain_slope":
                policy_version = copied.get("slopePolicyVersion")
                retry_obsolete = (
                    not isinstance(policy_version, INTEGER_TYPES)
                    or int(policy_version) < SLOPE_POLICY_VERSION
                )
            elif reason == "forbidden_biome":
                policy_version = copied.get("biomePolicyVersion")
                retry_obsolete = (
                    not isinstance(policy_version, INTEGER_TYPES)
                    or int(policy_version) < BIOME_POLICY_VERSION
                )
            elif reason == "landmark_overlap":
                policy_version = copied.get("overlapPolicyVersion")
                retry_obsolete = (
                    not isinstance(policy_version, INTEGER_TYPES)
                    or int(policy_version)
                    < LANDMARK_OVERLAP_POLICY_VERSION
                )
            elif reason in (
                "unported_landmark_slot",
                "discovery_not_ready",
            ):
                # These records describe a center an older build already
                # observed. Preserve it so adding new landmark support never
                # rewrites explored terrain on pack upgrade.
                retry_obsolete = False
            if (
                copied.get("state") in ("skipped", "failed")
                and retry_obsolete
            ):
                # These decisions came from older placement rules. Dropping
                # only the decision record lets the normal loaded-chunk and
                # proximity handoffs retry the center without touching any
                # completed or in-progress structure.
                continue
            if (
                copied.get("state") == "failed"
                and str(copied.get("kind", ""))
                in ruin_logic.HOLLOW_HILL_KIND_DATA
                and not copied.get("hollowHillCarveComplete")
                and int(copied.get("hollowHillCarvePolicyVersion", 0))
                < HOLLOW_HILL_CARVE_POLICY_VERSION
            ):
                # 0.9.13 treated SetBlockNew(False) as a write failure even
                # when the target was already air. Resume those interrupted
                # hills exactly once under the corrected idempotent policy.
                copied["state"] = "planned"
                copied["retries"] = 0
                copied["hollowHillCarvePolicyVersion"] = (
                    HOLLOW_HILL_CARVE_POLICY_VERSION
                )
            if (
                copied.get("state") in ("planned", "placing", "complete")
                and str(copied.get("kind", ""))
                in TERRAIN_ADAPTING_LANDMARKS
                and copied.get("pieces")
                and isinstance(copied.get("terrain"), dict)
                and (
                    not isinstance(
                        copied.get("chunkAssemblyPolicyVersion"),
                        INTEGER_TYPES,
                    )
                    or int(copied.get("chunkAssemblyPolicyVersion", 0))
                    < CHUNK_ASSEMBLY_POLICY_VERSION
                )
            ):
                # 0.9.20 assigned each 16x16 structure tile only to the
                # world chunk containing its origin. Landmark anchors are
                # not chunk aligned, so most tiles overlap a second or
                # fourth world chunk. A later terrain slice could therefore
                # erase the already placed half of a wall, floor, pool, or
                # boss marker. Re-run terrain and replay the pieces once
                # under the overlap-aware assembly policy.
                copied["chunkAssemblyPolicyVersion"] = (
                    CHUNK_ASSEMBLY_POLICY_VERSION
                )
                copied["state"] = "planned"
                copied["retries"] = 0
                copied["nextPiece"] = 0
                copied["completedPieces"] = []
                copied.pop("activeChunkSlice", None)
                copied.pop("chunkSlices", None)
                copied.pop("bossSpawnerReady", None)
                terrain = copied.get("terrain")
                if isinstance(terrain, dict):
                    terrain["nextColumn"] = 0
                    terrain["complete"] = False
            if (
                str(copied.get("kind", "")) == "naga_courtyard"
                and not copied.get("surfaceGenerated")
                and int(copied.get("courtyardLayoutPolicyVersion", 0))
                < COURTYARD_LAYOUT_POLICY_VERSION
            ):
                entry = self._catalog.get("naga_courtyard")
                variants = entry.get("variants", []) if entry else []
                try:
                    variant = variants[int(copied.get("variant", 0))]
                except (IndexError, TypeError, ValueError):
                    variant = None
                if variant is not None:
                    bounds = variant.get("bounds") or entry.get("bounds")
                    width = int(bounds[3]) - int(bounds[0]) + 1
                    depth = int(bounds[5]) - int(bounds[2]) + 1
                    copied["pieces"] = copy.deepcopy(
                        variant.get("pieces", [])
                    )
                    copied["state"] = "planned"
                    copied["retries"] = 0
                    copied["nextPiece"] = 0
                    copied["completedPieces"] = []
                    copied["chunkAssemblyPolicyVersion"] = (
                        CHUNK_ASSEMBLY_POLICY_VERSION
                    )
                    copied["courtyardLayoutPolicyVersion"] = (
                        COURTYARD_LAYOUT_POLICY_VERSION
                    )
                    copied["surfaceGenerated"] = False
                    copied["generationSource"] = "layout_repair"
                    copied.pop("surfaceTile", None)
                    copied.pop("nativeStructure", None)
                    copied.pop("activeChunkSlice", None)
                    copied.pop("chunkSlices", None)
                    copied["terrain"] = {
                        "mode": "flatten",
                        "width": width,
                        "depth": depth,
                        "flatRadius": 48.0,
                        "blendWidth": 8.0,
                        "diameter": 0,
                        "terrainDiameter": min(width, depth),
                        "detailSeed": int(
                            variant.get("terrainDetailSeed", 0)
                        ),
                        "clearStructure": True,
                        "nextColumn": 0,
                        "complete": False,
                    }
                    copied["bossSpawnerReady"] = False
                    copied.pop("bossSpawnPendingId", None)
                    copied.pop("bossSpawnPendingUntil", None)
                    if not copied.get("bossDefeated"):
                        copied["bossSpawned"] = False
                        copied.pop("bossEntityId", None)
            if str(copied.get("kind", "")) == "naga_courtyard":
                if copied.get("surfaceGenerated"):
                    copied["courtyardLayoutPolicyVersion"] = (
                        COURTYARD_LAYOUT_POLICY_VERSION
                    )
                copied["courtyardSurfacePolicyVersion"] = (
                    COURTYARD_SURFACE_POLICY_VERSION
                )
                if copied.get("surfaceGenerated"):
                    # Persisted native records are observations, not rebuild
                    # requests. Missing historical tile metadata stays
                    # pending instead of creating a full Tick repair job.
                    self._refresh_surface_landmark_state(copied)
                entry = self._catalog.get("naga_courtyard") or {}
                catalog_spawner = entry.get("bossSpawner")
                if isinstance(catalog_spawner, dict):
                    copied_spawner = copied.get("bossSpawner")
                    if not isinstance(copied_spawner, dict):
                        copied_spawner = copy.deepcopy(catalog_spawner)
                        copied["bossSpawner"] = copied_spawner
                    copied_spawner["activationRadius"] = int(
                        catalog_spawner.get("activationRadius", 64)
                    )
            kind = str(copied.get("kind", ""))
            if kind == "lich_tower":
                entry = self._catalog.get(kind) or {}
                variants = entry.get("variants", [])
                try:
                    variant = variants[int(copied.get("variant", 0))]
                except (IndexError, TypeError, ValueError):
                    variant = {}
                copied["controlledSpawns"] = (
                    self._controlled_spawns_for_variant(
                        entry,
                        variant,
                        copied.get("controlledSpawns"),
                    )
                )
            if kind in PERSISTENT_TEMPLATE_LANDMARKS:
                entry = self._catalog.get(kind) or {}
                variants = entry.get("variants", [])
                try:
                    variant = variants[int(copied.get("variant", 0))]
                except (IndexError, TypeError, ValueError):
                    variant = {}
                if isinstance(entry.get("controlledSpawns"), dict):
                    copied["controlledSpawns"] = (
                        self._controlled_spawns_for_variant(
                            entry,
                            variant,
                            copied.get("controlledSpawns"),
                        )
                    )
                if entry.get("placementProfile"):
                    self._apply_template_job_contract_defaults(
                        copied,
                        entry,
                        variant,
                    )
                if (
                    kind == "knight_stronghold"
                    and copied.get("surfaceGenerated")
                ):
                    self._ensure_surface_boss_tile(copied)
                    self._refresh_surface_landmark_state(copied)
            if kind in BOSS_VARIETY_LANDMARKS:
                entry = self._catalog.get(kind) or {}
                catalog_spawner = entry.get("bossSpawner")
                if isinstance(catalog_spawner, dict):
                    copied_spawner = copied.get("bossSpawner")
                    if not isinstance(copied_spawner, dict):
                        copied_spawner = copy.deepcopy(catalog_spawner)
                        copied["bossSpawner"] = copied_spawner
                    else:
                        for field, value in catalog_spawner.items():
                            copied_spawner.setdefault(field, copy.deepcopy(value))
                    if kind == "hydra_lair":
                        # Old worlds may keep the marker at a historical
                        # offset, but the trigger contract follows the source:
                        # 50-block range and no progression prerequisite.
                        copied_spawner["activationRadius"] = int(
                            catalog_spawner.get("activationRadius", 50)
                        )
                        copied_spawner.pop("progressAll", None)
                    elif kind == "labyrinth":
                        # Old ledgers kept the first Bedrock approximation:
                        # a 20-block, progression-gated trigger spawning above
                        # the marker. Restore MinoshroomSpawnerBlockEntity's
                        # source range and below-marker spawn position.
                        for field in (
                            "activationRadius",
                            "spawnYOffset",
                            "maxPlayerYOffset",
                        ):
                            if field in catalog_spawner:
                                copied_spawner[field] = copy.deepcopy(
                                    catalog_spawner[field]
                                )
                        copied_spawner.pop("progressAll", None)
                    elif kind == "dark_tower":
                        # UrGhastSpawnerBlockEntity uses the generic short
                        # nine-block range and only requires the player to be
                        # above markerY - 4. Route access remains a separate
                        # restriction and must not permanently poison old
                        # spawner records with a duplicated progression gate.
                        for field in (
                            "activationRadius",
                            "minPlayerYOffset",
                        ):
                            if field in catalog_spawner:
                                copied_spawner[field] = copy.deepcopy(
                                    catalog_spawner[field]
                                )
                        copied_spawner.pop("progressAll", None)
                    copied.setdefault(
                        "bossKind",
                        str(catalog_spawner.get("kind", "naga")),
                    )
                    copied.setdefault("bossSpawned", False)
                    copied.setdefault("bossDefeated", False)
                    copied.setdefault("rewardClaimed", False)
            if (
                copied.get("state") in ("planned", "placing")
                and not str(key).startswith("manual:")
                and kind not in PERSISTENT_TEMPLATE_LANDMARKS
            ):
                # Natural landmarks must finish inside their declared
                # worldgen pass. Older builds persisted automatic terrain and
                # structure jobs which resumed beside players after restart.
                # Keep the observed slot as a terminal diagnostic record, but
                # never resume those writes or let a pack upgrade mutate the
                # already explored terrain again.
                copied["state"] = "retired"
                copied["reason"] = "runtime_worldgen_disabled"
                copied.pop("activeChunkSlice", None)
                copied.pop("chunkSlices", None)
                copied["bossSpawnerReady"] = False
            elif copied.get("state") == "placing":
                copied["state"] = "planned"
            cleaned[str(key)] = copied
        return cleaned

    def _rebuild_runtime_job_indexes(self):
        self._courtyard_job_keys.clear()
        self._boss_job_keys.clear()
        self._knight_group_job_keys.clear()
        self._hollow_hill_job_keys.clear()
        self._surface_blend_job_keys.clear()
        for key, job in self._ledger.items():
            self._index_job(key, job)

    def _index_job(self, key, job):
        kind = str((job or {}).get("kind", ""))
        key = str(key)
        if kind == "naga_courtyard":
            self._courtyard_job_keys.add(key)
        if kind in BOSS_VARIETY_LANDMARKS:
            self._boss_job_keys.add(key)
        if isinstance((job or {}).get("bossGroupSpawner"), dict):
            self._knight_group_job_keys.add(key)
        if kind in ruin_logic.HOLLOW_HILL_KIND_DATA:
            self._hollow_hill_job_keys.add(key)
        edge_blend = (job or {}).get("edgeBlend")
        if isinstance(edge_blend, dict) and not edge_blend.get("complete"):
            self._surface_blend_job_keys.add(key)

    def _load_or_create_world_seed(self):
        try:
            value = self._extra.GetExtraData(WORLD_SEED_KEY)
        except Exception:
            value = None
        if isinstance(value, INTEGER_TYPES):
            return int(value)
        try:
            value = self._game.GetSeed()
        except Exception:
            value = None
        if not isinstance(value, INTEGER_TYPES):
            value = _stable_seed(self._level_id)
        value = int(value)
        try:
            self._extra.SetExtraData(WORLD_SEED_KEY, value, False)
            self._extra.SaveExtraData()
        except Exception as error:
            print "[TwilightBossSlice] ruin world seed save failed:", error
        return value

    def _persist(self):
        try:
            shards = self._ledger_storage_shards()
            generation = 1 - int(self._ledger_storage_generation)
            for index, shard in enumerate(shards):
                stored = self._extra.SetExtraData(
                    _ledger_shard_key(generation, index),
                    shard,
                    False,
                )
                if stored is False:
                    self._ledger_persist_failures += 1
                    self._last_ledger_persist_error = "set_extra_data"
                    print (
                        "[TwilightBossSlice] ruin ledger shard "
                        "SetExtraData failed:",
                        index,
                    )
                    return False
            manifest = {
                "format": LEDGER_STORAGE_FORMAT,
                "generation": generation,
                "shards": len(shards),
                "records": len(self._ledger),
            }
            manifest_payload = json.dumps(
                manifest,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            stored = self._extra.SetExtraData(
                LEDGER_KEY,
                manifest_payload,
                False,
            )
            if stored is False:
                self._ledger_persist_failures += 1
                self._last_ledger_persist_error = "set_extra_data"
                print "[TwilightBossSlice] ruin ledger manifest write failed"
                return False
            saved = self._extra.SaveExtraData()
            if saved is False:
                self._ledger_persist_failures += 1
                self._last_ledger_persist_error = "save_extra_data"
                print "[TwilightBossSlice] ruin ledger SaveExtraData failed"
                return False
            self._ledger_storage_generation = generation
            self._last_ledger_persist_error = None
            return True
        except Exception as error:
            self._ledger_persist_failures += 1
            self._last_ledger_persist_error = "exception:%s" % error
            print "[TwilightBossSlice] ruin ledger save failed:", error
            return False

    def _ledger_storage_shards(self):
        serialized = json.dumps(
            self._ledger,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        if not isinstance(serialized, bytes):
            serialized = serialized.encode("utf-8")
        encoded = base64.b64encode(zlib.compress(serialized, 9))
        if not isinstance(encoded, str):
            encoded = encoded.decode("ascii")
        return [
            encoded[index : index + LEDGER_SHARD_MAX_WEIGHT]
            for index in range(0, len(encoded), LEDGER_SHARD_MAX_WEIGHT)
        ] or [""]

    def _courtyard_marker_job(self, marker_position):
        marker_position = tuple(int(value) for value in marker_position)
        marker_xz = (marker_position[0], marker_position[2])
        for ledger_key in list(self._boss_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict):
                self._boss_job_keys.discard(ledger_key)
                self._courtyard_job_keys.discard(ledger_key)
                continue
            physical = job.get("physicalBossSpawnerMarker")
            if physical and tuple(int(value) for value in physical) == (
                marker_position
            ):
                return ledger_key, job
            spawner = job.get("bossSpawner")
            anchor = job.get("anchor")
            if not isinstance(spawner, dict) or not anchor:
                continue
            offset = spawner.get("offset", [0, 0, 0])
            expected_xz = (
                int(anchor[0]) + int(offset[0]),
                int(anchor[2]) + int(offset[2]),
            )
            if expected_xz == marker_xz:
                return ledger_key, job
        return None, None

    def _courtyard_marker_center(self, marker_x, marker_z):
        entry = self._catalog.get("naga_courtyard")
        if not entry or not isinstance(entry.get("bossSpawner"), dict):
            return None
        spawner = entry["bossSpawner"]
        centers = ruin_logic.landmark_centers_in_radius(
            int(marker_x),
            int(marker_z),
            32,
        )
        for center_x, center_z in centers:
            variant_index, variant = self._entry_variant(
                entry,
                "naga_courtyard",
                center_x,
                center_z,
            )
            if variant is None:
                continue
            expected = self._courtyard_marker_position_xz(
                (center_x, center_z),
                variant,
                spawner,
            )
            if expected == (int(marker_x), int(marker_z)):
                return center_x, center_z, variant_index, variant
        return None

    def _courtyard_marker_anchor_y(self, marker_position, spawner):
        marker_x, marker_y, marker_z = marker_position
        offset_y = int(spawner.get("offset", [0, 3, 0])[1])
        if offset_y != 1:
            below_name = self._block_name(
                marker_x,
                marker_y - 1,
                marker_z,
            )
            if below_name not in HOLLOW_HILL_SPAWN_AIR_BLOCKS:
                # Courtyards built before layout policy 4 placed the marker
                # one block above their floor. Preserve that floor while the
                # corrected Y=3 structure is replayed.
                return marker_y - 1
        return marker_y - offset_y

    def _recover_courtyard_from_tick_marker(self, marker_position):
        resolved = self._courtyard_marker_center(
            marker_position[0],
            marker_position[2],
        )
        if resolved is None:
            return None, None
        center_x, center_z, variant_index, _variant = resolved
        entry = self._catalog["naga_courtyard"]
        spawner = entry["bossSpawner"]
        anchor_y = self._courtyard_marker_anchor_y(
            marker_position,
            spawner,
        )
        offset = spawner.get("offset", [0, 0, 0])
        record = {
            "center": [int(center_x), int(center_z)],
            "variant": int(variant_index),
            "bossSpawned": False,
            "bossDefeated": False,
        }
        anchor = [
            int(marker_position[0]) - int(offset[0]),
            int(anchor_y),
            int(marker_position[2]) - int(offset[2]),
        ]
        job = self._courtyard_marker_recovery_job(
            record,
            anchor,
            marker_position,
        )
        if job is None:
            return None, None
        ledger_key = "%d,%d" % (center_x, center_z)
        self._ledger[ledger_key] = job
        self._index_job(ledger_key, job)
        self._scheduled_job_key = None
        self._persist()
        return ledger_key, job

    def _recover_lich_from_tick_marker(self, marker_position):
        """Re-arm an orphaned physical Lich marker after a ledger loss."""
        entry = self._catalog.get("lich_tower") or {}
        catalog_spawner = entry.get("bossSpawner")
        if not isinstance(catalog_spawner, dict):
            return None, None
        marker = tuple(int(value) for value in marker_position)
        spawner = copy.deepcopy(catalog_spawner)
        # The physical marker is authoritative.  A lost ledger no longer has
        # the layout variant needed to reconstruct its original local offset,
        # so anchor this recovery record directly on the marker.
        spawner["offset"] = [0, 0, 0]
        bounds = [
            marker[0] - 32,
            marker[1] - 96,
            marker[2] - 32,
            marker[0] + 32,
            marker[1] + 32,
            marker[2] + 32,
        ]
        job = ruin_logic.create_landmark_job(
            "lich_tower",
            marker,
            0,
            [],
            bounds,
        )
        job.update(
            {
                "state": "complete",
                "entryId": "lich_tower",
                "center": [marker[0], marker[2]],
                "generationSource": "physical_marker_recovery",
                "bossSpawner": spawner,
                "bossKind": str(spawner.get("kind", "lich")),
                "bossSpawnerReady": True,
                "bossSpawned": False,
                "bossDefeated": False,
                "rewardClaimed": False,
                "physicalBossSpawnerMarker": list(marker),
            }
        )
        ledger_key = "lich_marker:%d,%d,%d" % marker
        self._ledger[ledger_key] = job
        self._index_job(ledger_key, job)
        self._scheduled_job_key = None
        self._persist()
        return ledger_key, job

    def _recover_route_from_tick_marker(self, marker_position, kind):
        """Recover a route encounter from its authoritative boss marker."""
        entry = self._catalog.get(str(kind)) or {}
        if not isinstance(entry.get("bossSpawner"), dict):
            return None, None
        resolved = None
        for center_x, center_z in ruin_logic.landmark_centers_in_radius(
            int(marker_position[0]),
            int(marker_position[2]),
            128,
        ):
            variant_index, variant = self._entry_variant(
                entry,
                str(kind),
                center_x,
                center_z,
            )
            if variant is None:
                continue
            spawner = ruin_logic.boss_spawner_for_variant(entry, variant)
            if not isinstance(spawner, dict):
                continue
            expected = self._courtyard_marker_position_xz(
                (center_x, center_z),
                variant,
                spawner,
            )
            if expected == (
                int(marker_position[0]),
                int(marker_position[2]),
            ):
                resolved = (
                    center_x,
                    center_z,
                    variant_index,
                    variant,
                    spawner,
                )
                break
        if resolved is None:
            return None, None
        center_x, center_z, variant_index, variant, spawner = resolved
        offset = spawner.get("offset", [0, 0, 0])
        anchor = [
            int(marker_position[0]) - int(offset[0]),
            int(marker_position[1]) - int(offset[1]),
            int(marker_position[2]) - int(offset[2]),
        ]
        local_bounds = variant.get("bounds") or entry.get("bounds")
        if not local_bounds or len(local_bounds) != 6:
            return None, None
        world_bounds = [
            anchor[0] + int(local_bounds[0]),
            anchor[1] + int(local_bounds[1]),
            anchor[2] + int(local_bounds[2]),
            anchor[0] + int(local_bounds[3]),
            anchor[1] + int(local_bounds[4]),
            anchor[2] + int(local_bounds[5]),
        ]
        job = ruin_logic.create_landmark_job(
            str(kind),
            anchor,
            variant_index,
            [],
            world_bounds,
        )
        job.update(
            {
                "state": "complete",
                "entryId": str(entry.get("id", kind)),
                "center": [int(center_x), int(center_z)],
                "generationSource": "physical_marker_recovery",
                "surfaceGenerated": True,
                "bossSpawner": spawner,
                "bossKind": str(spawner.get("kind", kind)),
                "bossSpawnerReady": True,
                "encounterReady": True,
                "bossSpawned": False,
                "bossDefeated": False,
                "rewardClaimed": False,
                "physicalBossSpawnerMarker": [
                    int(value) for value in marker_position
                ],
            }
        )
        ledger_key = "%s_marker:%d,%d,%d" % (
            str(kind),
            int(marker_position[0]),
            int(marker_position[1]),
            int(marker_position[2]),
        )
        self._ledger[ledger_key] = job
        self._index_job(ledger_key, job)
        self._scheduled_job_key = None
        self._persist()
        return ledger_key, job

    def on_courtyard_spawner_tick(self, args, players, current_tick):
        """Make the physical Naga marker authoritative, like upstream."""
        marker_block = str(args.get("blockName", ""))
        if marker_block not in (
            COURTYARD_SPAWNER_BLOCK,
            LICH_SPAWNER_BLOCK,
            MINOSHROOM_SPAWNER_BLOCK,
            HYDRA_SPAWNER_BLOCK,
        ):
            return False
        try:
            dimension_id = int(args.get("dimension"))
            marker_position = (
                int(args.get("posX")),
                int(args.get("posY")),
                int(args.get("posZ")),
            )
            current_tick = int(current_tick)
        except (TypeError, ValueError):
            return False
        if dimension_id != self._dimension_id:
            return False
        if self._block_name(*marker_position) != marker_block:
            return False
        last_tick = self._courtyard_marker_tick_scans.get(marker_position)
        if (
            last_tick is not None
            and current_tick - int(last_tick)
            < COURTYARD_SPAWNER_EVENT_INTERVAL_TICKS
        ):
            return True
        self._courtyard_marker_tick_scans[marker_position] = current_tick

        _ledger_key, job = self._courtyard_marker_job(marker_position)
        if job is None and marker_block == COURTYARD_SPAWNER_BLOCK:
            _ledger_key, job = self._recover_courtyard_from_tick_marker(
                marker_position
            )
        elif job is None and marker_block == LICH_SPAWNER_BLOCK:
            _ledger_key, job = self._recover_lich_from_tick_marker(
                marker_position
            )
        elif job is None and marker_block == MINOSHROOM_SPAWNER_BLOCK:
            _ledger_key, job = self._recover_route_from_tick_marker(
                marker_position,
                "labyrinth",
            )
        elif job is None and marker_block == HYDRA_SPAWNER_BLOCK:
            _ledger_key, job = self._recover_route_from_tick_marker(
                marker_position,
                "hydra_lair",
            )
        if job is None:
            return False
        if self._rearm_stale_lich_marker(job, marker_position, marker_block):
            self._persist()
        if job.get("bossSpawned") or job.get("bossDefeated"):
            self._remove_courtyard_marker_at(marker_position)
            return True
        job["physicalBossSpawnerMarker"] = [
            int(value) for value in marker_position
        ]
        job["bossSpawnerReady"] = True
        self._activate_courtyard_bosses(players, current_tick)
        return True

    @staticmethod
    def _rearm_stale_lich_marker(job, marker_position, marker_block):
        """Repair a false defeat left by a non-landmark Lich death.

        A real landmark spawn consumes its physical marker before combat and
        claims the one-shot reward when defeated.  Seeing the marker still in
        place with spawned+defeated but no reward is therefore the legacy
        impossible state produced when a nearby spawn-egg Lich died.
        """
        if (
            marker_block != LICH_SPAWNER_BLOCK
            or str(job.get("kind", "")) != "lich_tower"
            or not job.get("bossSpawned")
            or not job.get("bossDefeated")
            or job.get("rewardClaimed")
        ):
            return False
        physical = job.get("physicalBossSpawnerMarker")
        if physical and tuple(int(value) for value in physical) != tuple(
            int(value) for value in marker_position
        ):
            return False
        job["bossSpawned"] = False
        job["bossDefeated"] = False
        job["bossSpawnerReady"] = True
        job.pop("bossEntityId", None)
        job.pop("bossSpawnPendingId", None)
        job.pop("bossSpawnPendingUntil", None)
        return True

    def _surface_boss_repair_job(self, record, generation_source, anchor=None):
        landmark_kind = str(record.get("kind", ""))
        if landmark_kind not in BOSS_VARIETY_LANDMARKS:
            return None
        entry = self._catalog.get(landmark_kind)
        variants = entry.get("variants", []) if entry else []
        try:
            variant_index = int(record.get("variant", 0))
            variant = variants[variant_index]
        except (IndexError, TypeError, ValueError):
            return None
        center = record.get("center")
        if not center or len(center) != 2:
            return None
        if anchor is None:
            anchor = record.get("anchor")
        if not anchor or len(anchor) != 3:
            return None
        anchor = [int(value) for value in anchor]
        bounds = variant.get("bounds") or entry.get("bounds")
        world_bounds = [
            anchor[0] + int(bounds[0]),
            anchor[1] + int(bounds[1]),
            anchor[2] + int(bounds[2]),
            anchor[0] + int(bounds[3]),
            anchor[1] + int(bounds[4]),
            anchor[2] + int(bounds[5]),
        ]
        job = ruin_logic.create_landmark_job(
            landmark_kind,
            anchor,
            variant_index,
            variant.get("pieces", []),
            world_bounds,
        )
        job["center"] = [int(center[0]), int(center[1])]
        job["entryId"] = str(entry.get("id", landmark_kind))
        job["generationSource"] = str(generation_source)
        job["chunkAssemblyPolicyVersion"] = CHUNK_ASSEMBLY_POLICY_VERSION
        if landmark_kind == "naga_courtyard":
            job["courtyardLayoutPolicyVersion"] = (
                COURTYARD_LAYOUT_POLICY_VERSION
            )
            job["courtyardSurfacePolicyVersion"] = (
                COURTYARD_SURFACE_POLICY_VERSION
            )
        job["surfaceGenerated"] = False
        expected = set(record.get("surfaceExpectedTiles", []))
        seen = set(record.get("surfaceTiles", []))
        if expected:
            job["surfaceRepairMissingTiles"] = sorted(
                expected - seen,
                key=self._surface_tile_sort_key,
            )
        width = int(bounds[3]) - int(bounds[0]) + 1
        depth = int(bounds[5]) - int(bounds[2]) + 1
        component_diameter = int(variant.get("diameter", 0))
        terrain_diameter = int(
            variant.get(
                "terrainDiameter",
                component_diameter + 12
                if component_diameter
                else min(width, depth),
            )
        )
        job["terrain"] = {
            "mode": "flatten",
            "width": width,
            "depth": depth,
            "flatRadius": (
                48.0
                if landmark_kind == "naga_courtyard"
                else max(0.0, terrain_diameter / 2.0 - 8.0)
            ),
            "blendWidth": 8.0,
            "diameter": component_diameter,
            "terrainDiameter": terrain_diameter,
            "detailSeed": int(variant.get("terrainDetailSeed", 0)),
            "clearStructure": True,
            "nextColumn": 0,
            "complete": False,
        }
        if landmark_kind == "naga_courtyard":
            variant_spawner = copy.deepcopy(entry.get("bossSpawner"))
        else:
            variant_spawner = ruin_logic.boss_spawner_for_variant(
                entry,
                variant,
            )
        if variant_spawner:
            job["bossSpawner"] = variant_spawner
            job["bossKind"] = str(
                job["bossSpawner"].get("kind", "naga")
            )
            defeated = bool(record.get("bossDefeated", False))
            spawned = bool(record.get("bossSpawned", False)) and not defeated
            job["bossDefeated"] = defeated
            job["bossSpawned"] = spawned
            job["rewardClaimed"] = bool(
                record.get("rewardClaimed", False)
            )
            job["bossSpawnerReady"] = False
            if spawned and record.get("bossEntityId") is not None:
                job["bossEntityId"] = str(record["bossEntityId"])
        return job

    def _courtyard_repair_job(self, record, generation_source, anchor=None):
        record = copy.deepcopy(record)
        record.setdefault("kind", "naga_courtyard")
        return self._surface_boss_repair_job(
            record,
            generation_source,
            anchor,
        )

    def _courtyard_marker_recovery_job(self, record, anchor, marker_position):
        """Recover Naga gameplay state without rebuilding terrain or pieces."""
        entry = self._catalog.get("naga_courtyard")
        variants = entry.get("variants", []) if entry else []
        try:
            variant_index = int(record.get("variant", 0))
            variant = variants[variant_index]
        except (IndexError, TypeError, ValueError):
            return None
        center = record.get("center")
        if not center or len(center) != 2 or not anchor or len(anchor) != 3:
            return None
        anchor = [int(value) for value in anchor]
        local_bounds = variant.get("bounds") or entry.get("bounds")
        world_bounds = [
            anchor[0] + int(local_bounds[0]),
            anchor[1] + int(local_bounds[1]),
            anchor[2] + int(local_bounds[2]),
            anchor[0] + int(local_bounds[3]),
            anchor[1] + int(local_bounds[4]),
            anchor[2] + int(local_bounds[5]),
        ]
        job = ruin_logic.create_landmark_job(
            "naga_courtyard",
            anchor,
            variant_index,
            [],
            world_bounds,
        )
        spawner = copy.deepcopy(entry.get("bossSpawner"))
        job.update(
            {
                "state": "complete",
                "entryId": "naga_courtyard",
                "center": [int(center[0]), int(center[1])],
                "generationSource": "physical_marker_recovery",
                "surfaceGenerated": False,
                "bossSpawner": spawner,
                "bossKind": str(spawner.get("kind", "naga")),
                "bossSpawnerReady": True,
                "bossSpawned": bool(record.get("bossSpawned", False)),
                "bossDefeated": bool(record.get("bossDefeated", False)),
                "rewardClaimed": bool(record.get("rewardClaimed", False)),
                "physicalBossSpawnerMarker": [
                    int(value) for value in marker_position
                ],
                "courtyardLayoutPolicyVersion": (
                    COURTYARD_LAYOUT_POLICY_VERSION
                ),
                "courtyardSurfacePolicyVersion": (
                    COURTYARD_SURFACE_POLICY_VERSION
                ),
            }
        )
        return job

    def _courtyard_marker_position_xz(self, center, variant, spawner):
        surface = variant.get("surfaceNative")
        if not isinstance(surface, dict):
            return None
        placement_center_x = int(center[0]) - ((int(center[0]) & 15) - 8)
        placement_center_z = int(center[1]) - ((int(center[1]) & 15) - 8)
        origin_offset = surface.get("originOffset", [0, 0, 0])
        marker_offset = spawner.get("offset", [0, 0, 0])
        return (
            placement_center_x
            + int(origin_offset[0])
            + int(marker_offset[0]),
            placement_center_z
            + int(origin_offset[2])
            + int(marker_offset[2]),
        )

    def _find_courtyard_marker_y(self, marker_x, marker_z, marker_block):
        top_y = self._top_y(marker_x, marker_z)
        if top_y is None:
            return None
        minimum_y = max(0, int(top_y) - MAX_TERRAIN_SURFACE_SCAN)
        for y in range(int(top_y) + 4, minimum_y - 1, -1):
            if self._block_name(marker_x, y, marker_z) == marker_block:
                return y
        return None

    def _recover_surface_courtyard_from_marker(self, center_x, center_z):
        entry = self._catalog.get("naga_courtyard")
        if not entry or not isinstance(entry.get("bossSpawner"), dict):
            return None
        variant_index, variant = self._entry_variant(
            entry,
            "naga_courtyard",
            center_x,
            center_z,
        )
        if variant is None:
            return None
        spawner = entry["bossSpawner"]
        marker_position = self._courtyard_marker_position_xz(
            (center_x, center_z),
            variant,
            spawner,
        )
        if marker_position is None:
            return None
        marker_y = self._find_courtyard_marker_y(
            marker_position[0],
            marker_position[1],
            str(spawner.get("markerBlock", "tf_slice:naga_boss_spawner")),
        )
        if marker_y is None:
            return None
        marker_position_3d = (
            int(marker_position[0]),
            int(marker_y),
            int(marker_position[1]),
        )
        record = {
            "center": [int(center_x), int(center_z)],
            "variant": int(variant_index),
            "bossSpawned": False,
            "bossDefeated": False,
        }
        anchor = [
            int(marker_position[0]) - int(spawner.get("offset", [0, 0, 0])[0]),
            self._courtyard_marker_anchor_y(marker_position_3d, spawner),
            int(marker_position[1]) - int(spawner.get("offset", [0, 0, 0])[2]),
        ]
        job = self._courtyard_marker_recovery_job(
            record,
            anchor,
            marker_position_3d,
        )
        return job

    def _build_native_structure_index(self):
        result = {}
        for entry in self._catalog.values():
            if entry.get("strategy") not in (
                "native_feature",
                "hollow_tree_attachment",
            ):
                continue
            for variant in entry.get("variants", []):
                native = variant.get("nativeFeature")
                if not isinstance(native, dict):
                    continue
                reference = str(native.get("structure", ""))
                if not reference.startswith("tf_slice/ruins/"):
                    continue
                structure_name = _structure_engine_name(
                    reference,
                    self._structure_aliases,
                )
                ruin_id = reference[len("tf_slice/ruins/") :].split(
                    "/",
                    1,
                )[0]
                indexed = {
                    "entryId": entry["id"],
                    "ruinId": ruin_id,
                    "structure": reference,
                    "bounds": copy.deepcopy(
                        variant.get("bounds")
                        or entry.get("bounds")
                        or [0, 0, 0, 0, 0, 0]
                    ),
                    "surfaceOffset": int(
                        native.get("surfaceOffset", 0)
                    ),
                }
                previous = result.get(structure_name)
                if previous is None:
                    result[structure_name] = indexed
                else:
                    previous_bounds = previous.get("bounds", [])
                    current_bounds = indexed.get("bounds", [])
                    if (
                        len(previous_bounds) == 6
                        and len(current_bounds) == 6
                    ):
                        previous["bounds"] = [
                            min(previous_bounds[0], current_bounds[0]),
                            min(previous_bounds[1], current_bounds[1]),
                            min(previous_bounds[2], current_bounds[2]),
                            max(previous_bounds[3], current_bounds[3]),
                            max(previous_bounds[4], current_bounds[4]),
                            max(previous_bounds[5], current_bounds[5]),
                        ]
        return result

    def _all_native_structure_names(self):
        return sorted(
            list(self._native_structure_index)
            + list(SURFACE_LANDMARK_MODE_BY_TRIGGER)
            + [
                HOLLOW_TREE_TRIGGER_STRUCTURE,
                LANDMARK_SURFACE_WATCHDOG_STRUCTURE,
                LANDMARK_NOOP_STRUCTURE,
            ]
        )

    def _register_structure_feature_whitelist(self):
        for structure_name in self._all_native_structure_names():
            try:
                if self._feature.AddNeteaseFeatureWhiteList(structure_name):
                    self._whitelisted_structures.append(structure_name)
            except Exception as error:
                print (
                    "[TwilightBossSlice] ruin feature whitelist failed:",
                    structure_name,
                    error,
                )

    def destroy(self):
        for key in list(self._areas):
            self._release_area(key)
        for structure_name in self._whitelisted_structures:
            try:
                self._feature.RemoveNeteaseFeatureWhiteList(structure_name)
            except Exception:
                pass
        self._whitelisted_structures = []

    def _surface_landmark_kind(self, mode, center_x, center_z):
        if str(mode) == "swamp":
            return "labyrinth"
        if str(mode) == "fire_swamp":
            return "hydra_lair"
        if str(mode) == "dark_forest":
            return "knight_stronghold"
        if str(mode) == "dark_forest_center":
            return "dark_tower"
        fallback = (
            "mushroom_tower"
            if str(mode) == "dense_mushroom"
            else None
        )
        variety = ruin_logic.resolve_variety_landmark(
            int(center_x) >> 4,
            int(center_z) >> 4,
            self._world_seed,
            SUPPORTED_VARIETY,
            fallback,
        )
        if str(mode) == "enchanted":
            if variety in BOSS_VARIETY_LANDMARKS:
                return variety
            return "quest_grove"
        return variety

    @staticmethod
    def _surface_tile_key(delta_x, delta_z):
        return "%d,%d" % (int(delta_x), int(delta_z))

    @staticmethod
    def _surface_tile_sort_key(value):
        try:
            delta_x, delta_z = str(value).split(",", 1)
            return int(delta_x), int(delta_z)
        except (TypeError, ValueError):
            return 0, 0

    def _ensure_surface_boss_tile(self, record):
        if record.get("surfaceBossTile"):
            return str(record["surfaceBossTile"])
        markers = record.get("markers")
        marker = (
            markers.get("bossGroupSpawner")
            if isinstance(markers, dict)
            else None
        )
        offset = marker.get("offset") if isinstance(marker, dict) else None
        anchor = record.get("anchor")
        center = record.get("center")
        if (
            not offset
            or not anchor
            or not center
            or len(offset) != 3
            or len(anchor) != 3
            or len(center) != 2
        ):
            return None
        marker_x = int(anchor[0]) + int(offset[0])
        marker_z = int(anchor[2]) + int(offset[2])
        boss_tile = self._surface_tile_key(
            (marker_x >> 4) - (int(center[0]) >> 4),
            (marker_z >> 4) - (int(center[1]) >> 4),
        )
        record["surfaceBossTile"] = boss_tile
        return boss_tile

    def _refresh_surface_landmark_state(self, record):
        expected = set(
            str(value)
            for value in record.get("surfaceExpectedTiles", [])
        )
        seen = set(str(value) for value in record.get("surfaceTiles", []))
        record["surfaceExpectedTiles"] = sorted(
            expected,
            key=self._surface_tile_sort_key,
        )
        record["surfaceTiles"] = sorted(
            seen,
            key=self._surface_tile_sort_key,
        )
        tiles_complete = bool(expected) and expected.issubset(seen)
        # Surface-native templates already contain their final terrain
        # envelope. Tile handoff is bookkeeping only; it must never create a
        # post-worldgen terrain-editing phase beside a player.
        complete = tiles_complete
        if complete:
            record["state"] = "complete"
        else:
            record["state"] = "surface_pending"
        boss_contract = record.get("bossSpawner")
        if not isinstance(boss_contract, dict):
            boss_contract = record.get("bossGroupSpawner")
        if isinstance(boss_contract, dict):
            if str(record.get("kind", "")) == "knight_stronghold":
                self._ensure_surface_boss_tile(record)
            boss_tile = str(record.get("surfaceBossTile", ""))
            local_boss_tile_ready = bool(boss_tile and boss_tile in seen)
            route_encounter = str(record.get("kind", "")) in (
                "labyrinth",
                "hydra_lair",
                "knight_stronghold",
            )
            boss_ready = bool(
                local_boss_tile_ready
                if route_encounter
                else complete and local_boss_tile_ready
            )
            record["bossSpawnerReady"] = boss_ready
            if route_encounter:
                # A route structure spans many chunks. Its boss and local
                # encounter logic become safe as soon as the authoritative
                # marker tile exists; empty far-edge tiles must not suppress
                # all spawns until a player explores the full footprint.
                record["encounterReady"] = boss_ready
        return complete

    def _merge_surface_landmark_record(self, existing, record):
        existing_tiles = set(existing.get("surfaceTiles", []))
        existing_tiles.update(record.get("surfaceTiles", []))
        expected_tiles = set(existing.get("surfaceExpectedTiles", []))
        expected_tiles.update(record.get("surfaceExpectedTiles", []))
        existing["surfaceTiles"] = list(existing_tiles)
        existing["surfaceExpectedTiles"] = list(expected_tiles)
        existing["surfaceTile"] = list(record.get("surfaceTile", [0, 0]))
        existing["nativeStructure"] = record.get("nativeStructure")
        existing["surfaceLastSeenTick"] = int(self._current_tick)
        if record.get("surfaceBossTile") is not None:
            existing["surfaceBossTile"] = str(record["surfaceBossTile"])
        if (
            existing.get("kind") == "dark_tower"
            and not isinstance(existing.get("canopyCleanup"), dict)
            and isinstance(record.get("canopyCleanup"), dict)
        ):
            existing["canopyCleanup"] = copy.deepcopy(
                record["canopyCleanup"]
            )
        if existing.get("kind") == "naga_courtyard":
            existing["courtyardSurfacePolicyVersion"] = (
                COURTYARD_SURFACE_POLICY_VERSION
            )
        self._refresh_surface_landmark_state(existing)
        return existing

    def _surface_native_tile(
        self,
        mode,
        chunk_x,
        chunk_z,
        event_y,
    ):
        selected = None
        alignment = "8,8"
        center_candidates = (
            ruin_logic.route_landmark_center_candidates
            if str(mode) in ROUTE_SURFACE_LANDMARK_MODES
            else ruin_logic.landmark_center_candidates
        )
        for center_x, center_z in center_candidates(chunk_x, chunk_z):
            kind = self._surface_landmark_kind(
                mode,
                center_x,
                center_z,
            )
            if kind is None:
                continue
            entry = self._entry_for_landmark(kind)
            if entry is None:
                continue
            delta_x = int(chunk_x) - (int(center_x) >> 4)
            delta_z = int(chunk_z) - (int(center_z) >> 4)

            # Avoid selecting/logging a layout variant for the eight adjacent
            # regions unless at least one variant can actually cover this
            # chunk.  Exact bounds are checked again after deterministic
            # variant selection.
            can_cover = False
            for candidate_variant in entry.get("variants", []):
                candidate_surface = candidate_variant.get("surfaceNative")
                if not isinstance(candidate_surface, dict):
                    continue
                candidate_bounds = candidate_surface.get(
                    "centerAlignments",
                    {},
                ).get(alignment)
                if not candidate_bounds or len(candidate_bounds) != 4:
                    continue
                if (
                    int(candidate_bounds[0])
                    <= delta_x
                    <= int(candidate_bounds[2])
                    and int(candidate_bounds[1])
                    <= delta_z
                    <= int(candidate_bounds[3])
                ):
                    can_cover = True
                    break
            if not can_cover:
                continue

            variant_index, variant = self._entry_variant(
                entry,
                kind,
                center_x,
                center_z,
            )
            if variant is None:
                continue
            surface = variant.get("surfaceNative")
            if not isinstance(surface, dict):
                continue
            chunk_bounds = surface.get("centerAlignments", {}).get(
                alignment
            )
            if not chunk_bounds or len(chunk_bounds) != 4:
                continue
            if not (
                int(chunk_bounds[0]) <= delta_x <= int(chunk_bounds[2])
                and int(chunk_bounds[1]) <= delta_z <= int(chunk_bounds[3])
            ):
                continue
            selected = (
                center_x,
                center_z,
                kind,
                entry,
                variant_index,
                variant,
                surface,
                chunk_bounds,
                delta_x,
                delta_z,
            )
            break
        if selected is None:
            return None
        (
            center_x,
            center_z,
            kind,
            entry,
            variant_index,
            variant,
            surface,
            chunk_bounds,
            delta_x,
            delta_z,
        ) = selected
        # Legacy negative regions put the center at local coordinate 9 while
        # positive regions use 8. Normalize only that one-block asymmetry so
        # every world can reuse one mobile-sized set of chunk templates.
        placement_center_x = int(center_x) - ((int(center_x) & 15) - 8)
        placement_center_z = int(center_z) - ((int(center_z) & 15) - 8)
        expected_tiles = []
        for expected_x in range(
            int(chunk_bounds[0]),
            int(chunk_bounds[2]) + 1,
        ):
            for expected_z in range(
                int(chunk_bounds[1]),
                int(chunk_bounds[3]) + 1,
            ):
                expected_tiles.append(
                    self._surface_tile_key(expected_x, expected_z)
                )
        reference = ruin_logic.surface_native_tile_reference(
            surface["prefix"],
            alignment,
            delta_x,
            delta_z,
        )
        origin_offset = surface.get("originOffset", [0, 0, 0])
        anchor = [
            placement_center_x + int(origin_offset[0]),
            int(event_y)
            + int(surface.get("groundY", 0))
            + int(origin_offset[1]),
            placement_center_z + int(origin_offset[2]),
        ]
        local_bounds = variant.get("bounds") or entry.get("bounds")
        world_bounds = [
            anchor[0] + int(local_bounds[0]),
            anchor[1] + int(local_bounds[1]),
            anchor[2] + int(local_bounds[2]),
            anchor[0] + int(local_bounds[3]),
            anchor[1] + int(local_bounds[4]),
            anchor[2] + int(local_bounds[5]),
        ]
        record = {
            "entryId": entry["id"],
            "kind": kind,
            "state": "surface_pending",
            "center": [int(center_x), int(center_z)],
            "anchor": anchor,
            "bounds": world_bounds,
            "variant": int(variant_index),
            "surfaceGenerated": True,
            "surfaceTile": [delta_x, delta_z],
            "surfaceTiles": [self._surface_tile_key(delta_x, delta_z)],
            "surfaceExpectedTiles": expected_tiles,
            "nativeStructure": _structure_engine_name(
                reference,
                self._structure_aliases,
            ),
            "generationSource": "surface_feature",
            "pieces": [],
            "nextPiece": 0,
            "retries": 0,
        }
        if isinstance(entry.get("controlledSpawns"), dict):
            record["controlledSpawns"] = self._controlled_spawns_for_variant(
                entry,
                variant,
            )
        if isinstance(variant.get("markers"), dict):
            record["markers"] = copy.deepcopy(variant["markers"])
        if (
            kind == "dark_tower"
            and isinstance(variant.get("canopyCleanup"), dict)
        ):
            record["canopyCleanup"] = copy.deepcopy(
                variant["canopyCleanup"]
            )
        if kind in PERSISTENT_TEMPLATE_LANDMARKS:
            self._apply_template_job_contract(record, entry, variant)
        record["terrainAdaptationStage"] = "surface_pass"
        if kind == "naga_courtyard":
            record["courtyardLayoutPolicyVersion"] = (
                COURTYARD_LAYOUT_POLICY_VERSION
            )
            record["courtyardSurfacePolicyVersion"] = (
                COURTYARD_SURFACE_POLICY_VERSION
            )
        variant_spawner = ruin_logic.boss_spawner_for_variant(entry, variant)
        if variant_spawner:
            record["bossSpawner"] = variant_spawner
            record["bossKind"] = str(
                record["bossSpawner"].get("kind", "naga")
            )
            record["bossSpawned"] = False
            record["bossDefeated"] = False
            record["rewardClaimed"] = False
            marker_offset = record["bossSpawner"].get("offset", [0, 0, 0])
            marker_world_x = anchor[0] + int(marker_offset[0])
            marker_world_z = anchor[2] + int(marker_offset[2])
            record["surfaceBossTile"] = self._surface_tile_key(
                (int(marker_world_x) >> 4) - (int(center_x) >> 4),
                (int(marker_world_z) >> 4) - (int(center_z) >> 4),
            )
            record["bossSpawnerReady"] = False
        if isinstance(record.get("bossGroupSpawner"), dict):
            self._ensure_surface_boss_tile(record)
            record["bossSpawnerReady"] = False
        if kind in ruin_logic.HOLLOW_HILL_KIND_DATA:
            record["hollowHillCarveComplete"] = True
        return reference, record

    def _dark_tower_canopy_cleanup_tile(
        self,
        chunk_x,
        chunk_z,
        event_y,
    ):
        selected = self._surface_native_tile(
            "dark_forest_center",
            chunk_x,
            chunk_z,
            event_y,
        )
        if selected is None:
            return None
        _surface_reference, record = selected
        if str(record.get("kind", "")) != "dark_tower":
            return None
        entry = self._entry_for_landmark("dark_tower")
        if not isinstance(entry, dict):
            return None
        variants = entry.get("variants", [])
        try:
            variant_index = int(record.get("variant", -1))
        except (TypeError, ValueError):
            return None
        if not (0 <= variant_index < len(variants)):
            return None
        cleanup = variants[variant_index].get("canopyCleanup")
        if not isinstance(cleanup, dict):
            return None
        bounds = cleanup.get("centerAlignments", {}).get("8,8")
        tile = record.get("surfaceTile", [])
        if (
            not bounds
            or len(bounds) != 4
            or not isinstance(tile, (tuple, list))
            or len(tile) != 2
        ):
            return None
        delta_x = int(tile[0])
        delta_z = int(tile[1])
        if not (
            int(bounds[0]) <= delta_x <= int(bounds[2])
            and int(bounds[1]) <= delta_z <= int(bounds[3])
        ):
            return None
        prefix = cleanup.get("prefix")
        if not prefix:
            return None
        return ruin_logic.surface_native_tile_reference(
            prefix,
            "8,8",
            delta_x,
            delta_z,
        )

    def _enqueue_surface_landmark_handoff(self, record):
        center = record["center"]
        ledger_key = "%d,%d" % (int(center[0]), int(center[1]))
        center_key = (int(center[0]), int(center[1]))
        tile = record.get("surfaceTile", [0, 0])
        tile_key = self._surface_tile_key(tile[0], tile[1])
        pending_key = center_key + (tile_key,)
        existing_key = ledger_key
        existing = self._ledger.get(ledger_key)
        if (
            existing is None
            and str(record.get("kind", "")) in ruin_logic.ROUTE_LANDMARK_KINDS
        ):
            existing_key, existing = self._route_ledger_record(
                center[0],
                center[1],
            )
            if existing is not None and existing_key != ledger_key:
                return False
        if isinstance(existing, dict):
            if not (
                existing.get("surfaceGenerated")
                and existing.get("generationSource") == "surface_feature"
                and existing.get("kind") == record.get("kind")
                and int(existing.get("variant", -1))
                == int(record.get("variant", -2))
            ):
                return False
            if tile_key in set(existing.get("surfaceTiles", [])):
                return False
        if pending_key in self._pending_surface_landmark_tiles:
            return False
        if (
            len(self._surface_landmark_handoffs)
            >= MAX_SURFACE_LANDMARK_HANDOFFS
        ):
            self._dropped_surface_landmark_handoffs += 1
            return False
        self._surface_landmark_handoffs.append(record)
        self._pending_surface_landmark_centers.add(center_key)
        self._pending_surface_landmark_tiles.add(pending_key)
        return True

    @staticmethod
    def _replace_structure_with_noop(args):
        args["structureName"] = LANDMARK_NOOP_STRUCTURE

    def _on_surface_landmark_event(self, args, mode):
        self._replace_structure_with_noop(args)
        try:
            dimension_id = int(args.get("dimensionId", -1))
            block_x = int(args.get("x", 0))
            block_y = int(args.get("y", 0))
            block_z = int(args.get("z", 0))
        except (TypeError, ValueError):
            return
        if dimension_id != self._dimension_id:
            return
        selected = self._surface_native_tile(
            mode,
            block_x >> 4,
            block_z >> 4,
            block_y,
        )
        if selected is None:
            return
        reference, record = selected
        args["structureName"] = _structure_engine_name(
            reference,
            self._structure_aliases,
        )
        self._accepted_surface_landmark_tiles += 1
        self._enqueue_surface_landmark_handoff(record)

    def _hollow_tree_native_tile(self, chunk_x, chunk_z, event_y):
        entry = self._catalog.get("leaf_dungeon") or {}
        variants = entry.get("variants", [])
        selection = ruin_logic.hollow_tree_chunk_tile(
            chunk_x,
            chunk_z,
            self._world_seed,
            len(variants),
        )
        if selection is None:
            return None
        center_x = int(selection["cellChunkX"]) * 16 + 16
        center_z = int(selection["cellChunkZ"]) * 16 + 16
        if ruin_logic.is_inside_landmark_clearance(
            center_x,
            center_z,
            self._world_seed,
            SUPPORTED_VARIETY,
            HOLLOW_TREE_CLEARANCE_CHUNKS,
        ):
            return None
        variant_index = int(selection["variant"])
        variant = variants[variant_index]
        source_x = int(selection["tileX"]) * 16
        source_z = int(selection["tileZ"]) * 16
        piece = None
        for candidate in variant.get("pieces", []):
            offset = candidate.get("offset", [0, 0, 0])
            if (
                int(offset[0]) == source_x
                and int(offset[2]) == source_z
            ):
                piece = candidate
                break
        if piece is None:
            return None
        anchor = [
            int(selection["cellChunkX"]) * 16,
            int(event_y),
            int(selection["cellChunkZ"]) * 16,
        ]
        bounds = variant.get("bounds") or entry.get("bounds")
        world_bounds = [
            anchor[0] + int(bounds[0]),
            anchor[1] + int(bounds[1]),
            anchor[2] + int(bounds[2]),
            anchor[0] + int(bounds[3]),
            anchor[1] + int(bounds[4]),
            anchor[2] + int(bounds[5]),
        ]
        reference = str(piece["structure"])
        record = {
            "entryId": entry["id"],
            "kind": "hollow_tree",
            "structure": _structure_engine_name(
                reference,
                self._structure_aliases,
            ),
            "origin": [int(chunk_x) * 16, int(event_y), int(chunk_z) * 16],
            "anchor": anchor,
            "bounds": world_bounds,
            "variant": variant_index,
            "treeCell": [
                int(selection["cellChunkX"]),
                int(selection["cellChunkZ"]),
            ],
            "treeTile": [
                int(selection["tileX"]),
                int(selection["tileZ"]),
            ],
        }
        return reference, record

    def _on_hollow_tree_event(self, args):
        self._replace_structure_with_noop(args)
        try:
            dimension_id = int(args.get("dimensionId", -1))
            block_x = int(args.get("x", 0))
            block_y = int(args.get("y", 0))
            block_z = int(args.get("z", 0))
        except (TypeError, ValueError):
            return
        if dimension_id != self._dimension_id:
            return
        selected = self._hollow_tree_native_tile(
            block_x >> 4,
            block_z >> 4,
            block_y,
        )
        if selected is None:
            return
        reference, record = selected
        args["structureName"] = _structure_engine_name(
            reference,
            self._structure_aliases,
        )
        if len(self._native_structure_handoffs) >= MAX_NATIVE_HANDOFFS:
            self._dropped_native_handoffs += 1
            return
        self._native_structure_handoffs.append(record)

    def _on_dark_tower_canopy_cleanup_event(self, args):
        self._replace_structure_with_noop(args)
        try:
            dimension_id = int(args.get("dimensionId", -1))
            block_x = int(args.get("x", 0))
            block_y = int(args.get("y", 0))
            block_z = int(args.get("z", 0))
        except (TypeError, ValueError):
            return
        if dimension_id != self._dimension_id:
            return
        reference = self._dark_tower_canopy_cleanup_tile(
            block_x >> 4,
            block_z >> 4,
            block_y,
        )
        if reference is not None:
            args["structureName"] = _structure_engine_name(
                reference,
                self._structure_aliases,
            )

    def on_structure_feature_event(self, args):
        """Filter native worldgen with pure data and record accepted ruins."""
        structure_name = str(args.get("structureName", ""))
        surface_config = SURFACE_LANDMARK_TRIGGER_CONFIG.get(
            structure_name
        )
        if surface_config is not None:
            self._on_surface_landmark_event(
                args,
                surface_config,
            )
            return
        if structure_name == DARK_TOWER_CANOPY_CLEANUP_TRIGGER_STRUCTURE:
            self._on_dark_tower_canopy_cleanup_event(args)
            return
        if structure_name == HOLLOW_TREE_TRIGGER_STRUCTURE:
            self._on_hollow_tree_event(args)
            return
        if structure_name == LANDMARK_SURFACE_WATCHDOG_STRUCTURE:
            # Compatibility only: old cached packs can still emit this token.
            # Replace it with a registered empty structure; it must never
            # schedule post-worldgen terrain or structure writes.
            self._replace_structure_with_noop(args)
            return
        if structure_name == LANDMARK_TRIGGER_STRUCTURE:
            # Compatibility with worlds that still have the pre-surface
            # token cached. New packs no longer emit this structure.
            self._replace_structure_with_noop(args)
            return
        native = self._native_structure_index.get(structure_name)
        if native is None:
            return
        # This callback can run on the terrain-generation worker. It may only
        # use event fields and deterministic pure logic. Accepted structures
        # stay in the engine pipeline; no server-tick placement is scheduled.
        try:
            dimension_id = int(args.get("dimensionId", -1))
            origin = [
                int(args.get("x", 0)),
                int(args.get("y", 0)),
                int(args.get("z", 0)),
            ]
        except (TypeError, ValueError):
            self._replace_structure_with_noop(args)
            return
        if dimension_id != self._dimension_id:
            self._replace_structure_with_noop(args)
            return
        ruin_id = native["ruinId"]
        biome_name = str(args.get("biomeName", ""))
        if ruin_id == "graveyard":
            if biome_name != "dm33027004_roofed_forest":
                self._replace_structure_with_noop(args)
                return
        elif ruin_id == "hollow_tree":
            if biome_name not in biome_catalog.LARGE_LANDMARK_BIOMES:
                self._replace_structure_with_noop(args)
                return
        elif biome_name not in biome_catalog.SMALL_RUIN_BIOMES:
            self._replace_structure_with_noop(args)
            return

        clearance = LANDMARK_CLEARANCE_CHUNKS
        if ruin_id == "hollow_tree":
            clearance = HOLLOW_TREE_CLEARANCE_CHUNKS
        if ruin_logic.is_inside_landmark_clearance(
            origin[0],
            origin[2],
            self._world_seed,
            SUPPORTED_VARIETY,
            clearance,
            biome_catalog.UNPORTED_LANDMARK_FALLBACK_BY_BIOME.get(
                biome_name
            ),
        ):
            self._replace_structure_with_noop(args)
            return

        if len(self._native_structure_handoffs) >= MAX_NATIVE_HANDOFFS:
            self._dropped_native_handoffs += 1
            return
        self._native_structure_handoffs.append(
            {
                "structure": structure_name,
                "origin": origin,
            }
        )

    def _on_landmark_trigger_event(
        self,
        args,
        generation_source="new_chunk",
    ):
        """Capture a watchdog token without touching ModSDK components."""
        self._replace_structure_with_noop(args)
        try:
            dimension_id = int(args.get("dimensionId", -1))
            block_x = int(args.get("x", 0))
            block_z = int(args.get("z", 0))
        except (TypeError, ValueError):
            return
        if dimension_id != self._dimension_id:
            return
        chunk_x = block_x >> 4
        chunk_z = block_z >> 4
        if self._enqueue_landmark_chunk(
            chunk_x,
            chunk_z,
            generation_source,
        ):
            self._accepted_structure_triggers += 1

    def on_chunk_generated_event(self, args):
        """Count first-generation chunks; surface features own placement."""
        try:
            dimension_id = int(
                args.get("dimension", args.get("dimensionId", -1))
            )
            chunk_x = int(args.get("chunkPosX"))
            chunk_z = int(args.get("chunkPosZ"))
        except (TypeError, ValueError):
            return
        if dimension_id != self._dimension_id:
            return
        self._accepted_chunk_generation_events += 1

    def on_chunk_loaded_event(self, args):
        """Observe loaded chunks without mutating already-generated terrain."""
        try:
            dimension_id = int(
                args.get("dimension", args.get("dimensionId", -1))
            )
            chunk_x = int(args.get("chunkPosX"))
            chunk_z = int(args.get("chunkPosZ"))
        except (TypeError, ValueError):
            return
        if dimension_id != self._dimension_id:
            return
        # Deliberately do not discover or reserve a landmark here. A load
        # event means the chunk already exists; changing it would be an
        # upgrade-time or player-visible terrain mutation.

    @staticmethod
    def _is_retryable_discovery_failure(job):
        return (
            isinstance(job, dict)
            and job.get("state") == "failed"
            and job.get("reason") == "discovery_not_ready"
        )

    def _enqueue_landmark_chunk(
        self,
        chunk_x,
        chunk_z,
        generation_source="new_chunk",
    ):
        """Reject legacy requests for post-worldgen landmark construction."""
        return False

    def _backfill_landmarks_near_players(self, current_tick, players):
        """Compatibility no-op: player position never starts worldgen."""
        return

    def _players_near_courtyard(self, job, players, radius):
        spawn_position = self._courtyard_spawn_position(job)
        if spawn_position is None:
            center = job.get("center")
            if not center or len(center) != 2:
                return False
            target_x = float(center[0])
            target_z = float(center[1])
        else:
            target_x = float(spawn_position[0])
            target_z = float(spawn_position[2])
        radius_squared = float(radius) * float(radius)
        for player in players or []:
            try:
                if int(player.get("dimensionId", -1)) != self._dimension_id:
                    continue
                position = player["position"]
                delta_x = float(position[0]) - target_x
                delta_z = float(position[2]) - target_z
            except (IndexError, KeyError, TypeError, ValueError):
                continue
            if delta_x * delta_x + delta_z * delta_z <= radius_squared:
                return True
        return False

    def _repair_incomplete_surface_boss_landmarks(
        self,
        current_tick,
        players,
    ):
        # Missing native tiles remain pending until their owning chunks are
        # generated. Rebuilding a whole arena after this settle clock is the
        # player-visible construction regression this service must prevent.
        return False

    @staticmethod
    def _rotated_world_bounds(origin, local_bounds, rotation, mirror=0):
        points = (
            (local_bounds[0], local_bounds[2]),
            (local_bounds[0], local_bounds[5]),
            (local_bounds[3], local_bounds[2]),
            (local_bounds[3], local_bounds[5]),
        )
        rotated = []
        rotation = int(rotation) % 360
        for x, z in points:
            if int(mirror) in (1, 3):
                x = -x
            if int(mirror) in (2, 3):
                z = -z
            if rotation == 90:
                rotated.append((-z, x))
            elif rotation == 180:
                rotated.append((-x, -z))
            elif rotation == 270:
                rotated.append((z, -x))
            else:
                rotated.append((x, z))
        return [
            int(origin[0] + min(point[0] for point in rotated)),
            int(origin[1] + local_bounds[1]),
            int(origin[2] + min(point[1] for point in rotated)),
            int(origin[0] + max(point[0] for point in rotated)),
            int(origin[1] + local_bounds[4]),
            int(origin[2] + max(point[1] for point in rotated)),
        ]

    @staticmethod
    def _native_job_key(structure_name, origin):
        return "native:%s:%d,%d,%d" % (
            structure_name,
            int(origin[0]),
            int(origin[1]),
            int(origin[2]),
        )

    def _drain_landmark_chunk_handoffs(self):
        # Snapshot the queue length so a failed record appended below cannot
        # be consumed again in this tick. Chunk biome and height components
        # can lag the generation event, so retries must observe later ticks.
        available = min(
            len(self._landmark_chunk_handoffs),
            MAX_LANDMARK_TRIGGERS_PER_TICK,
        )
        for _index in range(available):
            record = self._landmark_chunk_handoffs.popleft()
            center_key = (record["chunkX"], record["chunkZ"])
            self._pending_landmark_centers.discard(center_key)
            job = self.discover_for_generated_chunk(
                record["chunkX"],
                record["chunkZ"],
                record.get("generationSource", "new_chunk"),
            )
            if job is not None:
                continue
            record["attempts"] = int(record.get("attempts", 0)) + 1
            if record["attempts"] < MAX_LANDMARK_DISCOVERY_RETRIES:
                self._landmark_chunk_handoffs.append(record)
                self._pending_landmark_centers.add(center_key)
                continue
            center_x, center_z = ruin_logic.nearest_landmark_center(
                record["chunkX"],
                record["chunkZ"],
            )
            ledger_key = "%d,%d" % (center_x, center_z)
            if ledger_key not in self._ledger:
                self._ledger[ledger_key] = {
                    "state": "failed",
                    "reason": "discovery_not_ready",
                    "center": [center_x, center_z],
                    "attempts": record["attempts"],
                }
                self._failed_landmark_discoveries += 1
                self._persist()

    def _drain_surface_landmark_handoffs(self):
        changed = False
        drained = 0
        while (
            self._surface_landmark_handoffs
            and drained < MAX_SURFACE_LANDMARK_HANDOFFS_PER_TICK
        ):
            record = self._surface_landmark_handoffs.popleft()
            drained += 1
            center = record.get("center", [0, 0])
            center_key = (int(center[0]), int(center[1]))
            tile = record.get("surfaceTile", [0, 0])
            tile_key = self._surface_tile_key(tile[0], tile[1])
            self._pending_surface_landmark_tiles.discard(
                center_key + (tile_key,)
            )
            if not any(
                pending[0:2] == center_key
                for pending in self._pending_surface_landmark_tiles
            ):
                self._pending_surface_landmark_centers.discard(center_key)
            ledger_key = "%d,%d" % center_key
            existing = self._ledger.get(ledger_key)
            if isinstance(existing, dict):
                if not (
                    existing.get("surfaceGenerated")
                    and existing.get("generationSource")
                    == "surface_feature"
                    and existing.get("kind") == record.get("kind")
                    and int(existing.get("variant", -1))
                    == int(record.get("variant", -2))
                ):
                    continue
                copied = self._merge_surface_landmark_record(
                    existing,
                    record,
                )
            else:
                copied = copy.deepcopy(record)
                copied["surfaceLastSeenTick"] = int(self._current_tick)
                self._refresh_surface_landmark_state(copied)
                self._ledger[ledger_key] = copied
                self._index_job(ledger_key, copied)
            changed = True
        if changed:
            self._scheduled_job_key = None
            self._persist()

    def _drain_native_structure_handoffs(self):
        changed = False
        drained = 0
        while (
            self._native_structure_handoffs
            and drained < MAX_NATIVE_HANDOFFS_PER_TICK
        ):
            record = self._native_structure_handoffs.popleft()
            drained += 1
            structure_name = record["structure"]
            origin = record["origin"]
            if record.get("kind") == "hollow_tree":
                tree_cell = record.get("treeCell", [0, 0])
                ledger_key = "native:hollow_tree:%d,%d" % (
                    int(tree_cell[0]),
                    int(tree_cell[1]),
                )
                tile = record.get("treeTile", [0, 0])
                tile_key = self._surface_tile_key(tile[0], tile[1])
                existing = self._ledger.get(ledger_key)
                if existing is None:
                    existing = {
                        "entryId": record["entryId"],
                        "kind": "hollow_tree",
                        "state": "surface_pending",
                        "anchor": list(record["anchor"]),
                        "bounds": list(record["bounds"]),
                        "variant": int(record["variant"]),
                        "treeCell": list(tree_cell),
                        "treeTiles": [],
                        "treeExpectedTiles": ["0,0", "0,1", "1,0", "1,1"],
                        "nativeStructure": structure_name,
                        "generationSource": "chunk_feature",
                        "pieces": [],
                        "nextPiece": 0,
                        "retries": 0,
                    }
                    self._ledger[ledger_key] = existing
                if (
                    int(existing.get("variant", -1))
                    != int(record["variant"])
                ):
                    continue
                seen_tiles = set(existing.get("treeTiles", []))
                if tile_key in seen_tiles:
                    continue
                seen_tiles.add(tile_key)
                existing["treeTiles"] = sorted(seen_tiles)
                if set(existing["treeExpectedTiles"]).issubset(seen_tiles):
                    existing["state"] = "complete"
                changed = True
                continue
            ledger_key = self._native_job_key(structure_name, origin)
            if ledger_key in self._ledger:
                continue
            native = self._native_structure_index.get(structure_name)
            if native is None:
                continue
            bounds = native.get("bounds", [0, 0, 0, 0, 0, 0])
            world_bounds = [
                int(origin[0]) + int(bounds[0]),
                int(origin[1]) + int(bounds[1]),
                int(origin[2]) + int(bounds[2]),
                int(origin[0]) + int(bounds[3]),
                int(origin[1]) + int(bounds[4]),
                int(origin[2]) + int(bounds[5]),
            ]
            self._ledger[ledger_key] = {
                "entryId": native["entryId"],
                "kind": native["ruinId"],
                "state": "complete",
                "anchor": [int(value) for value in origin],
                "bounds": world_bounds,
                "nativeStructure": structure_name,
                "pieces": [],
                "nextPiece": 0,
                "retries": 0,
            }
            changed = True
        if changed:
            self._persist()

    def _top_y(self, x, z):
        try:
            value = self._block.GetTopBlockHeight(
                (int(x), int(z)),
                self._dimension_id,
            )
            if value is None:
                return None
            return int(value)
        except Exception as error:
            print "[TwilightBossSlice] ruin height query failed:", error
            return None

    def _block_name(self, x, y, z):
        try:
            block = self._block.GetBlockNew(
                (int(x), int(y), int(z)),
                self._dimension_id,
            )
        except Exception:
            return None
        if not isinstance(block, dict):
            return None
        name = block.get("name")
        return str(name) if name else None

    def _is_terrain_decoration(self, block_name):
        if block_name in TERRAIN_DECORATION_BLOCKS:
            return True
        return bool(
            block_name
            and block_name.endswith(
                (
                    "_leaves",
                    "_log",
                    "_wood",
                    "_sapling",
                    "_flower",
                    "_mushroom_block",
                )
            )
        )

    def _terrain_surface_y(self, x, z):
        """Find generated ground below trees and other decoration blocks."""
        top_y = self._top_y(x, z)
        if top_y is None:
            return None
        fallback_y = None
        minimum_y = max(0, top_y - MAX_TERRAIN_SURFACE_SCAN)
        for y in range(top_y, minimum_y - 1, -1):
            block_name = self._block_name(x, y, z)
            if block_name in TERRAIN_GROUND_BLOCKS:
                return y
            if (
                fallback_y is None
                and block_name is not None
                and not self._is_terrain_decoration(block_name)
            ):
                fallback_y = y
        return fallback_y if fallback_y is not None else top_y

    @staticmethod
    def _is_tree_trunk(block_name):
        if block_name in (
            "minecraft:log",
            "minecraft:log2",
        ):
            return True
        return bool(
            block_name
            and block_name.endswith(("_log", "_wood", "_stem"))
        )

    @staticmethod
    def _surface_edge_geometry(blend, column_index):
        core_size = blend.get("coreSize", [0, 0, 0])
        if len(core_size) != 3:
            return None
        core_width = max(1, int(core_size[0]))
        core_depth = max(1, int(core_size[2]))
        blend_width = max(1, int(blend.get("width", 1)))
        total_width = core_width + blend_width * 2
        total_depth = core_depth + blend_width * 2
        column_index = int(column_index)
        if column_index < 0 or column_index >= total_width * total_depth:
            return None
        local_x = column_index % total_width
        local_z = column_index // total_width

        if str(blend.get("shape", "")) == "circle":
            center_x = blend_width + (core_width - 1) / 2.0
            center_z = blend_width + (core_depth - 1) / 2.0
            radius = min(core_width, core_depth) / 2.0
            radial_distance = math.sqrt(
                (local_x - center_x) * (local_x - center_x)
                + (local_z - center_z) * (local_z - center_z)
            )
            distance = radial_distance - radius
        else:
            core_min_x = blend_width
            core_min_z = blend_width
            core_max_x = blend_width + core_width - 1
            core_max_z = blend_width + core_depth - 1
            outside_x = max(
                core_min_x - local_x,
                0,
                local_x - core_max_x,
            )
            outside_z = max(
                core_min_z - local_z,
                0,
                local_z - core_max_z,
            )
            distance = math.sqrt(
                outside_x * outside_x + outside_z * outside_z
            )
        if distance <= 0.0 or distance > blend_width:
            return None
        return local_x, local_z, distance, total_width, total_depth

    def _prepare_surface_edge_blend_column(
        self,
        job,
        blend,
        column_index,
    ):
        geometry = self._surface_edge_geometry(blend, column_index)
        if geometry is None:
            return {"skip": True, "reason": "outside_blend"}
        local_x, local_z, distance, _total_width, _total_depth = geometry
        blend_width = max(1, int(blend.get("width", 1)))
        world_x = int(job["anchor"][0]) + local_x - blend_width
        world_z = int(job["anchor"][2]) + local_z - blend_width
        if not self._chunk_position_ready(
            world_x,
            int(job["anchor"][1]),
            world_z,
        ):
            return None

        source_y = self._terrain_surface_y(world_x, world_z)
        if source_y is None:
            return None
        surface_block = self._block_name(world_x, source_y, world_z)
        if surface_block not in TERRAIN_GROUND_BLOCKS:
            return {
                "skip": True,
                "reason": "non_natural_surface",
                "x": world_x,
                "z": world_z,
            }

        top_y = self._top_y(world_x, world_z)
        if top_y is None:
            return None
        water_level = None
        for y in range(source_y + 1, top_y + 1):
            block_name = self._block_name(world_x, y, world_z)
            if self._is_tree_trunk(block_name):
                return {
                    "skip": True,
                    "reason": "tree_root",
                    "x": world_x,
                    "z": world_z,
                }
            if block_name in ("minecraft:water", "minecraft:flowing_water"):
                water_level = y

        # A small position-stable offset keeps the band from reading as a
        # perfect geometric outline without changing either endpoint.
        detail_seed = _stable_seed(
            "%d:%d:%d" % (self._world_seed, world_x, world_z)
        )
        edge_fraction = float(distance) / float(blend_width)
        endpoint_fade = max(
            0.0,
            4.0 * edge_fraction * (1.0 - edge_fraction),
        )
        jitter = (
            (((detail_seed & 255) / 255.0) - 0.5)
            * 1.5
            * endpoint_fade
        )
        effective_distance = min(
            float(blend_width),
            max(0.0, float(distance) + jitter),
        )
        target_y = ruin_logic.blended_surface_height(
            source_y,
            int(job["anchor"][1]),
            effective_distance,
            0.0,
            float(blend_width),
        )

        changes = {}
        if source_y > target_y:
            for y in range(source_y, target_y, -1):
                changes[y] = "minecraft:air"
            # Remove only lightweight surface decoration.  Logs and wood were
            # rejected above, so a real tree is never cut or left floating.
            for y in range(source_y + 1, top_y + 1):
                block_name = self._block_name(world_x, y, world_z)
                if (
                    self._is_terrain_decoration(block_name)
                    and block_name
                    not in ("minecraft:water", "minecraft:flowing_water")
                    and not str(block_name).endswith("_leaves")
                    and block_name
                    not in ("minecraft:leaves", "minecraft:leaves2")
                ):
                    changes[y] = "minecraft:air"
        elif source_y < target_y:
            if surface_block in (
                "minecraft:sand",
                "minecraft:red_sand",
                "minecraft:gravel",
                "minecraft:clay",
            ):
                subsurface_block = surface_block
            elif surface_block in (
                "minecraft:stone",
                "minecraft:deepslate",
                "minecraft:bedrock",
            ):
                subsurface_block = "minecraft:stone"
            else:
                subsurface_block = "minecraft:dirt"
            stone_top = max(source_y, target_y - 3)
            for y in range(source_y + 1, stone_top + 1):
                changes[y] = "minecraft:stone"
            for y in range(stone_top + 1, target_y):
                changes[y] = subsurface_block

        if source_y != target_y:
            changes[target_y] = surface_block
        if water_level is not None and target_y < water_level:
            for y in range(target_y + 1, water_level + 1):
                changes[y] = "minecraft:water"
        return {
            "x": world_x,
            "z": world_z,
            "changes": [
                [y, changes[y]] for y in sorted(changes)
            ],
            "nextChange": 0,
        }

    def _biome_name(self, x, z):
        try:
            return self._biome.GetBiomeName(
                (int(x), 64, int(z)),
                self._dimension_id,
            )
        except Exception as error:
            print "[TwilightBossSlice] ruin biome query failed:", error
            return None

    def _landmark_biome_name(self, center_x, center_z):
        """Sample the aligned 256-block landmark cell used by native rules."""
        sample_x, sample_z = ruin_logic.landmark_region_sample(
            center_x,
            center_z,
        )
        return self._biome_name(sample_x, sample_z)

    def _entry_variant(self, entry, landmark_kind, anchor_x, anchor_z):
        variants = entry.get("variants", [])
        candidate_indexes = list(range(len(variants)))
        if landmark_kind in ("small_hill", "medium_hill", "large_hill"):
            candidate_indexes = [
                index
                for index, variant in enumerate(variants)
                if variant.get("landmarkKind") == landmark_kind
            ]
        if not candidate_indexes:
            return None, None
        weights = [
            max(0, int(variants[index].get("weight", 1)))
            for index in candidate_indexes
        ]
        roll = ruin_logic.landmark_stream_index(
            self._world_seed,
            anchor_x,
            anchor_z,
            landmark_kind,
            "layout",
            sum(weights),
        )
        local_index = ruin_logic.weighted_variant_index(weights, roll)
        index = candidate_indexes[local_index]
        return index, variants[index]

    def _entry_for_landmark(self, landmark_kind):
        if landmark_kind == "hedge_maze":
            return self._catalog.get("hedge_maze")
        if landmark_kind == "naga_courtyard":
            return self._catalog.get("naga_courtyard")
        if landmark_kind == "lich_tower":
            return self._catalog.get("lich_tower")
        if landmark_kind == "mushroom_tower":
            return self._catalog.get("mushroom_tower")
        if landmark_kind == "quest_grove":
            return self._catalog.get("quest_grove")
        if landmark_kind == "labyrinth":
            return self._catalog.get("labyrinth")
        if landmark_kind == "hydra_lair":
            return self._catalog.get("hydra_lair")
        if landmark_kind == "knight_stronghold":
            return self._catalog.get("knight_stronghold")
        if landmark_kind == "dark_tower":
            return self._catalog.get("dark_tower")
        if landmark_kind in ("small_hill", "medium_hill", "large_hill"):
            return self._catalog.get("hollow_hill")
        return None

    @staticmethod
    def _apply_template_job_contract_defaults(job, entry, variant):
        """Migrate a persisted route-template ledger without losing state."""
        placement_profile = str(
            entry.get("placementProfile", "surface_beard_thin")
        )
        if placement_profile not in (
            "surface_beard_thin",
            "buried_entry",
        ):
            raise ValueError("unsupported placement profile %s" % placement_profile)
        job.setdefault("placementProfile", placement_profile)
        job.setdefault("entrySurfaceOffset", int(entry.get("entrySurfaceOffset", 0)))
        job.setdefault("verticalSliceHeight", int(entry.get("verticalSliceHeight", 0)))
        job.setdefault("structureLockObjective", str(
            entry.get("structureLockObjective", "")
        ))
        job.setdefault("templateCursor", int(job.get("nextPiece", 0)))
        job.setdefault("markersVerified", False)
        job.setdefault("finalCommit", False)
        if isinstance(entry.get("bossGroupSpawner"), dict):
            job.setdefault("bossGroupSpawner", copy.deepcopy(entry["bossGroupSpawner"]))
            job.setdefault("bossGroupSpawned", False)
            job.setdefault("bossGroupDefeated", False)
            job.setdefault("rewardClaimed", False)
        if isinstance(variant.get("markers"), dict):
            job.setdefault("markers", copy.deepcopy(variant["markers"]))
        return job

    @classmethod
    def _apply_template_job_contract(cls, job, entry, variant):
        """Copy the fail-closed route template contract into a new ledger."""
        cls._apply_template_job_contract_defaults(job, entry, variant)
        job["templateCursor"] = int(job.get("nextPiece", 0))
        job["markersVerified"] = False
        job["finalCommit"] = False
        return job

    def _route_companion_has_single_core(
        self,
        companion_biome,
        center_x,
        center_z,
    ):
        """Require one cardinal core for a route companion landmark."""
        core_biome = (
            biome_catalog.ROUTE_CORE_BIOME_BY_COMPANION_BIOME.get(
                companion_biome
            )
        )
        if core_biome is None:
            return True
        sample_x, sample_z = ruin_logic.landmark_region_sample(
            center_x,
            center_z,
        )
        matches = 0
        for offset_x, offset_z in ruin_logic.ROUTE_LANDMARK_CARDINAL_OFFSETS:
            if self._biome_name(
                sample_x + int(offset_x),
                sample_z + int(offset_z),
            ) == core_biome:
                matches += 1
        return matches == 1

    def _landmark_kind_at_center(
        self,
        biome_name,
        center_x,
        center_z,
    ):
        if not self._route_companion_has_single_core(
            biome_name,
            center_x,
            center_z,
        ):
            return None
        special_landmark = biome_catalog.SPECIAL_LANDMARK_BY_BIOME.get(
            biome_name
        )
        variety_landmark = ruin_logic.resolve_variety_landmark(
            int(center_x) >> 4,
            int(center_z) >> 4,
            self._world_seed,
            SUPPORTED_VARIETY,
            biome_catalog.UNPORTED_LANDMARK_FALLBACK_BY_BIOME.get(
                biome_name
            ),
        )
        if special_landmark is not None:
            # Enchanted forest keeps the upstream rule used by the native
            # surface trigger: a seed-selected boss slot is not replaced by
            # the Quest Grove.  Swamp and Fire Swamp are progression-route
            # key biomes, so their Labyrinth/Hydra mappings remain absolute.
            if (
                special_landmark == "quest_grove"
                and variety_landmark in BOSS_VARIETY_LANDMARKS
            ):
                return variety_landmark
            return special_landmark
        if biome_name not in biome_catalog.LARGE_LANDMARK_BIOMES:
            return None
        return variety_landmark

    def _magic_map_kind_at_center(self, center_x, center_z):
        """Resolve a landmark without creating jobs or mutating the ledger."""
        ledger_key = "%d,%d" % (int(center_x), int(center_z))
        recorded = self._ledger.get(ledger_key)
        if recorded is None:
            _legacy_key, legacy_record = self._route_ledger_record(
                center_x,
                center_z,
            )
            if legacy_record is not None:
                recorded = legacy_record
        if isinstance(recorded, dict):
            if recorded.get("state") in ("skipped", "failed"):
                return None
            kind = recorded.get("kind")
            if magic_map_logic.icon_for_landmark(kind) is not None:
                return str(kind)
            return None

        biome_name = self._landmark_biome_name(center_x, center_z)
        if biome_name is None:
            return None
        kind = self._landmark_kind_at_center(
            biome_name,
            center_x,
            center_z,
        )
        if kind is None:
            return None
        if magic_map_logic.icon_for_landmark(kind) is None:
            return None
        return str(kind)

    def _route_ledger_record(self, center_x, center_z):
        """Read a nominal route record, including a pre-migration jitter key."""
        nominal_x, nominal_z = ruin_logic.landmark_region_sample(
            center_x,
            center_z,
        )
        nominal_key = "%d,%d" % (nominal_x, nominal_z)
        recorded = self._ledger.get(nominal_key)
        if isinstance(recorded, dict):
            return nominal_key, recorded
        legacy_x, legacy_z = ruin_logic.legacy_landmark_center_for_nominal(
            nominal_x,
            nominal_z,
        )
        legacy_key = "%d,%d" % (legacy_x, legacy_z)
        recorded = self._ledger.get(legacy_key)
        if (
            isinstance(recorded, dict)
            and str(recorded.get("kind", ""))
            in ruin_logic.ROUTE_LANDMARK_KINDS
        ):
            return legacy_key, recorded
        return nominal_key, None

    def magic_map_landmarks_near(
        self,
        position,
        center_x,
        center_z,
        radius=magic_map_logic.DISCOVERY_RADIUS,
    ):
        """Return map-visible landmarks near a player, with no side effects."""
        try:
            player_x = int(position[0])
            player_z = int(position[2])
        except (IndexError, TypeError, ValueError):
            return []
        result = []
        centers = ruin_logic.landmark_centers_in_radius(
            player_x,
            player_z,
            int(radius) + 48,
        )
        seen = set()
        for landmark_x, landmark_z in centers:
            kind = self._magic_map_kind_at_center(
                landmark_x,
                landmark_z,
            )
            if kind is None:
                continue
            if kind in ruin_logic.ROUTE_LANDMARK_KINDS:
                landmark_x, landmark_z = ruin_logic.landmark_region_sample(
                    landmark_x,
                    landmark_z,
                )
            delta_x = int(landmark_x) - player_x
            delta_z = int(landmark_z) - player_z
            if delta_x * delta_x + delta_z * delta_z > int(radius) ** 2:
                continue
            if not magic_map_logic.is_inside_map(
                landmark_x,
                landmark_z,
                center_x,
                center_z,
            ):
                continue
            marker_key = (str(kind), int(landmark_x), int(landmark_z))
            if marker_key in seen:
                continue
            seen.add(marker_key)
            if kind in ruin_logic.ROUTE_LANDMARK_KINDS:
                _record_key, recorded = self._route_ledger_record(
                    landmark_x,
                    landmark_z,
                )
            else:
                recorded = self._ledger.get(
                    "%d,%d" % (landmark_x, landmark_z)
                )
            result.append(
                {
                    "kind": kind,
                    "position": [int(landmark_x), int(landmark_z)],
                    "conquered": bool(
                        (recorded or {}).get("bossDefeated", False)
                    ),
                }
            )
        return result

    def _surface_is_acceptable(self, entry, variant, center_x, center_z):
        bounds = variant.get("bounds") or entry.get(
            "bounds",
            [0, 0, 0, 0, 0, 0],
        )
        half_x = max(1, (bounds[3] - bounds[0] + 1) // 2)
        half_z = max(1, (bounds[5] - bounds[2] + 1) // 2)
        samples = []
        for x, z in (
            (center_x, center_z),
            (center_x - half_x, center_z - half_z),
            (center_x + half_x, center_z - half_z),
            (center_x - half_x, center_z + half_z),
            (center_x + half_x, center_z + half_z),
        ):
            height = self._terrain_surface_y(x, z)
            if height is None:
                return None
            samples.append(height)
        allowed_slope = LANDMARK_SLOPE_LIMITS.get(
            entry["id"],
            DEFAULT_LANDMARK_SLOPE_LIMIT,
        )
        if max(samples) - min(samples) > allowed_slope:
            return False
        return int(round(sum(samples) / float(len(samples))))

    def _overlaps_existing(self, bounds, ignore_native=False):
        for key, existing in self._ledger.items():
            if existing.get("state") in ("skipped", "failed"):
                continue
            if ignore_native and str(key).startswith("native:"):
                continue
            if ruin_logic.bounds_overlap(bounds, existing.get("bounds")):
                return True
        return False

    def _is_courtyard_repairable_block(self, block_name):
        return (
            block_name in TERRAIN_GROUND_BLOCKS
            or block_name in COURTYARD_REPAIRABLE_STRUCTURE_BLOCKS
            or self._is_terrain_decoration(block_name)
        )

    def discover_for_position(self, position):
        chunk_x = int(math.floor(float(position[0]) / 16.0))
        chunk_z = int(math.floor(float(position[2]) / 16.0))
        center_x, center_z = ruin_logic.nearest_landmark_center(chunk_x, chunk_z)
        return self._discover_landmark_center(
            center_x,
            center_z,
            "legacy_player_scan",
        )

    def discover_for_generated_chunk(
        self,
        chunk_x,
        chunk_z,
        generation_source="new_chunk",
    ):
        chunk_x = int(chunk_x)
        chunk_z = int(chunk_z)
        if not ruin_logic.is_landmark_center_chunk(chunk_x, chunk_z):
            return None
        center_x, center_z = ruin_logic.nearest_landmark_center(
            chunk_x,
            chunk_z,
        )
        return self._discover_landmark_center(
            center_x,
            center_z,
            generation_source,
        )

    def _discover_landmark_center(
        self,
        center_x,
        center_z,
        generation_source,
    ):
        ledger_key = "%d,%d" % (center_x, center_z)
        if ledger_key in self._ledger:
            existing = self._ledger[ledger_key]
            if not self._is_retryable_discovery_failure(existing):
                return existing
            self._ledger.pop(ledger_key, None)

        # Chunk generation events can arrive before NetEase exposes the
        # corresponding level chunk to block and height components. Querying
        # those components early floods `get_top_block_height has no lc` and
        # can stall dimension entry, so leave the handoff queued until the
        # center chunk is actually readable.
        if not self._chunk_position_ready(center_x, 64, center_z):
            return None

        recovered = self._recover_surface_courtyard_from_marker(
            center_x,
            center_z,
        )
        if recovered is not None:
            self._ledger[ledger_key] = recovered
            self._index_job(ledger_key, recovered)
            self._scheduled_job_key = None
            self._persist()
            return recovered

        biome_name = self._landmark_biome_name(center_x, center_z)
        if biome_name is None:
            return None
        landmark_kind = self._landmark_kind_at_center(
            biome_name,
            center_x,
            center_z,
        )
        if landmark_kind is None:
            self._ledger[ledger_key] = {
                "state": "skipped",
                "reason": "forbidden_biome",
                "biomePolicyVersion": BIOME_POLICY_VERSION,
                "center": [center_x, center_z],
            }
            self._persist()
            return self._ledger[ledger_key]

        # Route megastructures are first-generation native structures. Old
        # explored chunks are intentionally left untouched; the administrator
        # diagnostic placement path does not pass through this gate.
        if not ruin_logic.allows_automatic_route_placement(
            landmark_kind,
            generation_source,
        ):
            return None

        entry = self._entry_for_landmark(landmark_kind)
        if entry is None:
            return None
        variant_index, variant = self._entry_variant(
            entry,
            landmark_kind,
            center_x,
            center_z,
        )
        if variant is None:
            return None
        adapts_terrain = landmark_kind in TERRAIN_ADAPTING_LANDMARKS
        if generation_source == "new_chunk" or adapts_terrain:
            # Original Twilight Forest adapts terrain while the chunk is
            # generated. NetEase reports decorated chunks here, so descend
            # through any tree canopy before anchoring the terrain profile.
            # Loaded-chunk recovery must use the same terrain adaptation;
            # otherwise every missing courtyard on non-flat terrain is
            # permanently skipped before its flattening job can be created.
            surface_y = self._terrain_surface_y(center_x, center_z)
        else:
            surface_y = self._surface_is_acceptable(
                entry,
                variant,
                center_x,
                center_z,
            )
        if surface_y is None:
            return None
        if surface_y is False:
            self._ledger[ledger_key] = {
                "state": "skipped",
                "reason": "terrain_slope",
                "slopePolicyVersion": SLOPE_POLICY_VERSION,
                "center": [center_x, center_z],
            }
            self._persist()
            return self._ledger[ledger_key]

        bounds = variant.get("bounds") or entry.get("bounds")
        width = bounds[3] - bounds[0] + 1
        depth = bounds[5] - bounds[2] + 1
        origin = [
            center_x - width // 2,
            (
                int(surface_y)
                - ruin_logic.HOLLOW_HILL_GROUND_ABOVE_SEA
                if landmark_kind in ruin_logic.HOLLOW_HILL_KIND_DATA
                else int(surface_y)
            ),
            center_z - depth // 2,
        ]
        lowering_step = int(entry.get("worldHeightLoweringStep", 0))
        maximum_world_y = int(entry.get("maximumWorldY", 319))
        if lowering_step > 0:
            while origin[1] + int(bounds[4]) > maximum_world_y:
                origin[1] -= lowering_step
        world_bounds = [
            origin[0] + bounds[0],
            origin[1] + bounds[1],
            origin[2] + bounds[2],
            origin[0] + bounds[3],
            origin[1] + bounds[4],
            origin[2] + bounds[5],
        ]
        if self._overlaps_existing(world_bounds, ignore_native=True):
            self._ledger[ledger_key] = {
                "state": "skipped",
                "reason": "landmark_overlap",
                "overlapPolicyVersion": LANDMARK_OVERLAP_POLICY_VERSION,
                "center": [center_x, center_z],
            }
            self._persist()
            return self._ledger[ledger_key]

        job = ruin_logic.create_landmark_job(
            landmark_kind,
            origin,
            variant_index,
            variant["pieces"],
            world_bounds,
        )
        job["center"] = [center_x, center_z]
        job["entryId"] = entry["id"]
        job["generationSource"] = str(generation_source)
        if isinstance(entry.get("controlledSpawns"), dict):
            job["controlledSpawns"] = self._controlled_spawns_for_variant(
                entry,
                variant,
            )
        if isinstance(variant.get("markers"), dict):
            job["markers"] = copy.deepcopy(variant["markers"])
        if entry.get("placementProfile"):
            self._apply_template_job_contract(job, entry, variant)
        job["chunkAssemblyPolicyVersion"] = (
            CHUNK_ASSEMBLY_POLICY_VERSION
        )
        if landmark_kind == "naga_courtyard":
            job["courtyardLayoutPolicyVersion"] = (
                COURTYARD_LAYOUT_POLICY_VERSION
            )
        if adapts_terrain:
            component_diameter = int(variant.get("diameter", 0))
            terrain_diameter = int(
                variant.get(
                    "terrainDiameter",
                    component_diameter + 12
                    if component_diameter
                    else min(width, depth),
                )
            )
            if landmark_kind == "naga_courtyard":
                flat_radius = 48.0
            elif landmark_kind == "hedge_maze":
                flat_radius = 32.0
            elif landmark_kind == "dark_tower":
                # The source's beard-thin adaptation supports only the main
                # foundation; the surrounding center biome remains intact.
                flat_radius = 12.0
            else:
                flat_radius = max(0.0, terrain_diameter / 2.0 - 8.0)
            blend_width = 8.0
            job["terrain"] = {
                "mode": (
                    "hill_base"
                    if landmark_kind in (
                        "small_hill",
                        "medium_hill",
                        "large_hill",
                    )
                    else "flatten"
                ),
                "width": int(width),
                "depth": int(depth),
                "flatRadius": flat_radius,
                "blendWidth": blend_width,
                "diameter": component_diameter,
                "terrainDiameter": terrain_diameter,
                "detailSeed": int(variant.get("terrainDetailSeed", 0)),
                "nextColumn": 0,
                "complete": False,
            }
        variant_spawner = ruin_logic.boss_spawner_for_variant(entry, variant)
        if variant_spawner:
            job["bossSpawner"] = variant_spawner
            job["bossKind"] = str(
                job["bossSpawner"].get("kind", "naga")
            )
            job["bossSpawned"] = False
            job["bossDefeated"] = False
            job["rewardClaimed"] = False
        self._ledger[ledger_key] = job
        self._index_job(ledger_key, job)
        self._scheduled_job_key = None
        self._persist()
        return job

    def _start_area(self, job_key, job, current_tick):
        self._area_sequence += 1
        area_key = "tf_slice_ruin_%d" % self._area_sequence
        bounds = job["bounds"]
        margin = max(
            AREA_LOAD_MARGIN,
            int(job.get("areaMargin", AREA_LOAD_MARGIN)),
        )
        try:
            started = self._chunk.SetAddArea(
                area_key,
                self._dimension_id,
                (
                    bounds[0] - margin,
                    max(0, bounds[1]),
                    bounds[2] - margin,
                ),
                (
                    bounds[3] + margin,
                    bounds[4],
                    bounds[5] + margin,
                ),
            )
        except Exception as error:
            print "[TwilightBossSlice] ruin SetAddArea failed:", error
            started = False
        if started is False:
            ruin_logic.record_job_failure(job, MAX_RETRIES)
            return False
        self._areas[job_key] = {
            "key": area_key,
            "readyTick": int(current_tick) + AREA_WARMUP_TICKS,
            "chunksReady": False,
            "nextChunkCheckTick": int(current_tick) + AREA_WARMUP_TICKS,
        }
        return True

    def _job_chunks_ready(self, job):
        checker = getattr(self._chunk, "CheckChunkState", None)
        if checker is None:
            return True
        bounds = job.get("bounds")
        if not bounds or len(bounds) != 6:
            return False
        check_y = int(job.get("anchor", [0, bounds[1], 0])[1])
        minimum_chunk_x = int(bounds[0]) >> 4
        maximum_chunk_x = int(bounds[3]) >> 4
        minimum_chunk_z = int(bounds[2]) >> 4
        maximum_chunk_z = int(bounds[5]) >> 4
        for chunk_x in range(minimum_chunk_x, maximum_chunk_x + 1):
            for chunk_z in range(minimum_chunk_z, maximum_chunk_z + 1):
                check_position = (
                    chunk_x * 16 + 8,
                    check_y,
                    chunk_z * 16 + 8,
                )
                try:
                    if not checker(self._dimension_id, check_position):
                        return False
                except Exception as error:
                    print (
                        "[TwilightBossSlice] ruin chunk readiness failed:",
                        check_position,
                        error,
                    )
                    return False
        return True

    def _release_area(self, job_key):
        state = self._areas.pop(job_key, None)
        if state is None:
            return
        try:
            self._chunk.DeleteArea(state["key"])
        except Exception as error:
            print "[TwilightBossSlice] ruin DeleteArea failed:", error

    def _place_piece(self, job, piece):
        origin = job["anchor"]
        offset = piece["offset"]
        position = (
            int(origin[0] + offset[0]),
            int(origin[1] + offset[1]),
            int(origin[2] + offset[2]),
        )
        structure_name = _structure_engine_name(
            piece["structure"],
            self._structure_aliases,
        )
        try:
            result = self._game.PlaceStructure(
                None,
                position,
                structure_name,
                self._dimension_id,
                int(piece.get("rotation", 0)),
                0,
                0,
                True,
                bool(piece.get("removeBlock", False)),
                int(piece.get("mirror", job.get("mirror", 0))),
                100.0,
                int(job.get("variant", 0)),
            )
            return result is not False
        except Exception as error:
            print (
                "[TwilightBossSlice] ruin PlaceStructure failed:",
                structure_name,
                position,
                error,
            )
            return False

    def _advance_hollow_hill_carve(self, job):
        hill_data = ruin_logic.HOLLOW_HILL_KIND_DATA.get(
            str(job.get("kind", ""))
        )
        if hill_data is None:
            return True, False
        anchor = job.get("anchor")
        if not anchor or len(anchor) != 3:
            return False, True

        terrain_diameter = int(hill_data[2])
        total_columns = terrain_diameter * terrain_diameter
        job["hollowHillCarvePolicyVersion"] = (
            HOLLOW_HILL_CARVE_POLICY_VERSION
        )
        carve = job.get("hollowHillCarve")
        if not isinstance(carve, dict):
            carve = {
                "nextColumn": 0,
                "nextY": None,
                "blocksCleared": 0,
                "complete": False,
            }
            job["hollowHillCarve"] = carve
            self._hill_carves_started += 1
            print (
                "[TwilightBossSlice] hollow hill carve started:",
                str(job.get("kind", "")),
                tuple(anchor),
            )
        if carve.get("complete"):
            return True, False

        column_index = int(carve.get("nextColumn", 0))
        next_y = carve.get("nextY")
        blocks_cleared = int(carve.get("blocksCleared", 0))
        before_call_blocks = blocks_cleared
        changed = 0
        while (
            changed < MAX_HOLLOW_HILL_CARVE_BLOCKS_PER_TICK
            and column_index < total_columns
        ):
            local_x = column_index % terrain_diameter
            local_z = column_index // terrain_diameter
            world_x = int(anchor[0]) + local_x
            world_z = int(anchor[2]) + local_z
            cavity = ruin_logic.hollow_hill_generated_cavity_range(
                job,
                world_x,
                world_z,
            )
            if cavity is None:
                column_index += 1
                next_y = None
                continue

            minimum_y, maximum_y = cavity
            y = int(minimum_y if next_y is None else next_y)
            if not self._set_terrain_block(
                world_x,
                y,
                world_z,
                "minecraft:air",
            ):
                carve["nextColumn"] = column_index
                carve["nextY"] = y
                carve["blocksCleared"] = blocks_cleared
                return False, True

            changed += 1
            blocks_cleared += 1
            self._hill_carve_blocks += 1
            y += 1
            if y > int(maximum_y):
                column_index += 1
                next_y = None
            else:
                next_y = y

        carve["nextColumn"] = column_index
        carve["nextY"] = next_y
        carve["blocksCleared"] = blocks_cleared
        if (
            blocks_cleared // HOLLOW_HILL_CARVE_CHECKPOINT_BLOCKS
            > before_call_blocks // HOLLOW_HILL_CARVE_CHECKPOINT_BLOCKS
        ):
            print (
                "[TwilightBossSlice] hollow hill carve progress:",
                str(job.get("kind", "")),
                tuple(anchor),
                blocks_cleared,
            )
        if column_index >= total_columns:
            carve["complete"] = True
            job["hollowHillCarveComplete"] = True
            self._hill_carves_completed += 1
            print (
                "[TwilightBossSlice] hollow hill carve completed:",
                str(job.get("kind", "")),
                tuple(anchor),
                blocks_cleared,
            )
            return True, False
        return False, False

    def _set_terrain_block(self, x, y, z, block_name):
        position = (int(x), int(y), int(z))
        requested_name = str(block_name)
        try:
            result = self._block.SetBlockNew(
                position,
                {"name": requested_name, "aux": 0},
                0,
                self._dimension_id,
                True,
                False,
            )
            if result is not False:
                return True

            # SetBlockNew returns False both for a real failure and when the
            # requested block already occupies the position.  The latter is
            # success for idempotent terrain/carving work and is common while
            # hollowing a hill that intersects pre-existing cave air.
            current = self._block.GetBlockNew(
                position,
                self._dimension_id,
            )
            if isinstance(current, dict):
                return str(current.get("name", "")) == requested_name
            return bool(current) and str(current[0]) == requested_name
        except Exception as error:
            print (
                "[TwilightBossSlice] landmark terrain edit failed:",
                (x, y, z),
                error,
            )
            return False

    def _prepare_terrain_column(self, job, terrain, column_index):
        width = int(terrain["width"])
        depth = int(terrain["depth"])
        local_x = int(column_index) % width
        local_z = int(column_index) // width
        center_x = (width - 1) / 2.0
        center_z = (depth - 1) / 2.0
        delta_x = abs(local_x - center_x)
        delta_z = abs(local_z - center_z)
        if terrain.get("mode") == "hill_base":
            distance = math.sqrt(delta_x * delta_x + delta_z * delta_z)
            component_diameter = int(terrain.get("diameter", 0))
            try:
                hill_profile = ruin_logic.hollow_hill_profile(
                    component_diameter,
                    distance,
                )
            except ValueError:
                hill_profile = None
            if hill_profile is None:
                return {"skip": True}
        else:
            distance = max(delta_x, delta_z)
            hill_profile = None

        world_x = int(job["anchor"][0]) + local_x
        world_z = int(job["anchor"][2]) + local_z
        source_y = self._terrain_surface_y(world_x, world_z)
        if source_y is None:
            return None
        if hill_profile is not None:
            terrain_detail = ruin_logic.hollow_hill_terrain_detail(
                int(terrain.get("detailSeed", 0)),
                local_x,
                local_z,
                float(terrain.get("terrainDiameter", width)) / 2.0,
                2 if "detailSeed" in terrain else 0,
            )
            target_y = ruin_logic.hollow_hill_surface_target(
                source_y,
                int(job["anchor"][1]),
                int(hill_profile["surface"]) + terrain_detail,
            )
        else:
            target_y = ruin_logic.blended_surface_height(
                source_y,
                int(job["anchor"][1]),
                distance,
                float(terrain["flatRadius"]),
                float(terrain["blendWidth"]),
            )
        changes = []
        if source_y > target_y:
            for y in range(source_y, target_y, -1):
                changes.append([y, "minecraft:air"])
            changes.append([target_y, "minecraft:grass_block"])
        elif source_y < target_y:
            stone_top = max(source_y, target_y - 3)
            for y in range(source_y + 1, stone_top + 1):
                changes.append([y, "minecraft:stone"])
            for y in range(stone_top + 1, target_y):
                changes.append([y, "minecraft:dirt"])
            changes.append([target_y, "minecraft:grass_block"])

        cleared_y = set()
        if terrain.get("clearStructure"):
            target_name = self._block_name(world_x, target_y, world_z)
            if (
                target_name != "minecraft:grass_block"
                and self._is_courtyard_repairable_block(target_name)
            ):
                changes.append([target_y, "minecraft:grass_block"])
            for y in range(
                target_y + 1,
                target_y + COURTYARD_REPAIR_STRUCTURE_CLEARANCE + 1,
            ):
                block_name = self._block_name(world_x, y, world_z)
                if (
                    block_name is not None
                    and block_name not in HOLLOW_HILL_SPAWN_AIR_BLOCKS
                    and self._is_courtyard_repairable_block(block_name)
                ):
                    changes.append([y, "minecraft:air"])
                    cleared_y.add(y)

        top_y = self._top_y(world_x, world_z)
        decoration_top = max(source_y, target_y)
        if top_y is not None:
            decoration_top = max(decoration_top, top_y)
        decoration_top += MAX_TERRAIN_DECORATION_CLEARANCE
        if str(job.get("kind", "")) == "naga_courtyard":
            decoration_top = max(
                decoration_top,
                max(source_y, target_y)
                + COURTYARD_VEGETATION_CLEARANCE,
            )
        for y in range(max(source_y, target_y) + 1, decoration_top + 1):
            if y in cleared_y:
                continue
            block_name = self._block_name(world_x, y, world_z)
            if (
                block_name not in HOLLOW_HILL_SPAWN_AIR_BLOCKS
                and self._is_terrain_decoration(block_name)
            ):
                changes.append([y, "minecraft:air"])
        return {
            "x": world_x,
            "z": world_z,
            "changes": changes,
            "nextChange": 0,
        }

    def _advance_terrain(self, job):
        terrain = job.get("terrain")
        if not isinstance(terrain, dict) or terrain.get("complete"):
            return True
        total_columns = int(terrain["width"]) * int(terrain["depth"])
        blocks_changed = 0
        columns_started = 0
        while (
            blocks_changed < MAX_TERRAIN_BLOCKS_PER_TICK
            and columns_started < MAX_TERRAIN_COLUMNS_PER_TICK
        ):
            column_index = int(terrain.get("nextColumn", 0))
            if column_index >= total_columns:
                terrain["complete"] = True
                terrain.pop("activeColumn", None)
                return True
            active = terrain.get("activeColumn")
            if not isinstance(active, dict):
                active = self._prepare_terrain_column(
                    job,
                    terrain,
                    column_index,
                )
                if active is None:
                    return False
                columns_started += 1
                if active.get("skip") or not active.get("changes"):
                    terrain["nextColumn"] = column_index + 1
                    continue
                terrain["activeColumn"] = active

            changes = active.get("changes", [])
            next_change = int(active.get("nextChange", 0))
            while (
                next_change < len(changes)
                and blocks_changed < MAX_TERRAIN_BLOCKS_PER_TICK
            ):
                y, block_name = changes[next_change]
                if not self._set_terrain_block(
                    active["x"],
                    y,
                    active["z"],
                    block_name,
                ):
                    return False
                next_change += 1
                blocks_changed += 1
                active["nextChange"] = next_change
            if next_change < len(changes):
                break
            terrain.pop("activeColumn", None)
            terrain["nextColumn"] = column_index + 1
        if int(terrain.get("nextColumn", 0)) >= total_columns:
            terrain["complete"] = True
            terrain.pop("activeColumn", None)
            return True
        return False

    def _advance_surface_edge_blend_job(self, job):
        blend = job.get("edgeBlend")
        if not isinstance(blend, dict) or blend.get("complete"):
            return True
        core_size = blend.get("coreSize", [0, 0, 0])
        if len(core_size) != 3:
            blend["complete"] = True
            self._refresh_surface_landmark_state(job)
            return True
        blend_width = max(1, int(blend.get("width", 1)))
        total_width = max(1, int(core_size[0])) + blend_width * 2
        total_depth = max(1, int(core_size[2])) + blend_width * 2
        total_columns = total_width * total_depth
        blocks_changed = 0
        columns_started = 0
        columns_scanned = 0
        while (
            blocks_changed < MAX_SURFACE_EDGE_BLOCKS_PER_TICK
            and columns_started < MAX_SURFACE_EDGE_COLUMNS_PER_TICK
            and columns_scanned < MAX_SURFACE_EDGE_SCAN_PER_TICK
        ):
            column_index = int(blend.get("nextColumn", 0))
            if column_index >= total_columns:
                blend["complete"] = True
                blend.pop("activeColumn", None)
                self._refresh_surface_landmark_state(job)
                return True
            active = blend.get("activeColumn")
            if not isinstance(active, dict):
                active = self._prepare_surface_edge_blend_column(
                    job,
                    blend,
                    column_index,
                )
                if active is None:
                    return False
                columns_scanned += 1
                if active.get("reason") != "outside_blend":
                    columns_started += 1
                if active.get("skip") or not active.get("changes"):
                    blend["nextColumn"] = column_index + 1
                    continue
                blend["activeColumn"] = active

            changes = active.get("changes", [])
            next_change = int(active.get("nextChange", 0))
            while (
                next_change < len(changes)
                and blocks_changed < MAX_SURFACE_EDGE_BLOCKS_PER_TICK
            ):
                y, block_name = changes[next_change]
                if not self._set_terrain_block(
                    active["x"],
                    y,
                    active["z"],
                    block_name,
                ):
                    return False
                next_change += 1
                blocks_changed += 1
                active["nextChange"] = next_change
            if next_change < len(changes):
                break
            blend.pop("activeColumn", None)
            blend["nextColumn"] = column_index + 1
        if int(blend.get("nextColumn", 0)) >= total_columns:
            blend["complete"] = True
            blend.pop("activeColumn", None)
            self._refresh_surface_landmark_state(job)
            return True
        return False

    def _advance_surface_edge_blends(self, players):
        candidates = []
        for key in list(self._surface_blend_job_keys):
            job = self._ledger.get(key)
            if not isinstance(job, dict):
                self._surface_blend_job_keys.discard(key)
                continue
            edge_blend = job.get("edgeBlend")
            if not isinstance(edge_blend, dict) or edge_blend.get("complete"):
                self._surface_blend_job_keys.discard(key)
                continue
            if (
                job.get("state") == "surface_blending"
                and self._job_has_nearby_player(job, players)
            ):
                candidates.append((key, job))
        if not candidates:
            return False
        key, job = sorted(
            candidates,
            key=lambda item: (
                self._job_player_distance_squared(item[1], players),
                str(item[0]),
            ),
        )[0]
        blend = job["edgeBlend"]
        before_column = int(blend.get("nextColumn", 0))
        complete = self._advance_surface_edge_blend_job(job)
        after_column = int(blend.get("nextColumn", 0))
        crossed_checkpoint = (
            after_column // SURFACE_EDGE_CHECKPOINT_COLUMNS
            > before_column // SURFACE_EDGE_CHECKPOINT_COLUMNS
        )
        if complete or crossed_checkpoint:
            self._persist()
        if complete:
            self._surface_blend_job_keys.discard(str(key))
        return True

    def _job_player_distance_squared(self, job, players):
        center = job.get("center")
        if not center or len(center) < 2:
            anchor = job.get("anchor", [0, 0, 0])
            center = [anchor[0], anchor[2]]
        nearest_distance = None
        for player in players or []:
            try:
                if int(player.get("dimensionId", -1)) != self._dimension_id:
                    continue
                position = player["position"]
                delta_x = float(position[0]) - float(center[0])
                delta_z = float(position[2]) - float(center[1])
                distance = delta_x * delta_x + delta_z * delta_z
            except (IndexError, KeyError, TypeError, ValueError):
                continue
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
        return nearest_distance

    def _job_has_nearby_player(self, job, players):
        distance = self._job_player_distance_squared(job, players)
        return (
            distance is not None
            and distance
            <= AUTOMATIC_JOB_PLAYER_RADIUS * AUTOMATIC_JOB_PLAYER_RADIUS
        )

    def _chunk_position_ready(self, x, y, z):
        checker = getattr(self._chunk, "CheckChunkState", None)
        if checker is None:
            return True
        chunk_x = int(x) >> 4
        chunk_z = int(z) >> 4
        position = (
            chunk_x * 16 + 8,
            int(y),
            chunk_z * 16 + 8,
        )
        try:
            chunk_ready = bool(checker(self._dimension_id, position))
        except Exception as error:
            print (
                "[TwilightBossSlice] ruin chunk readiness failed:",
                position,
                error,
            )
            return False
        if not chunk_ready:
            return False
        try:
            block = self._block.GetBlockNew(
                position,
                self._dimension_id,
            )
        except Exception:
            return False
        if isinstance(block, dict):
            return bool(block.get("name"))
        return bool(isinstance(block, (tuple, list)) and block)

    def _piece_world_bounds(self, job, piece):
        origin = job.get("anchor", [0, 0, 0])
        offset = piece.get("offset", [0, 0, 0])
        size = piece.get("size", [1, 1, 1])
        local_bounds = [
            int(offset[0]),
            int(offset[1]),
            int(offset[2]),
            int(offset[0]) + max(1, int(size[0])) - 1,
            int(offset[1]) + max(1, int(size[1])) - 1,
            int(offset[2]) + max(1, int(size[2])) - 1,
        ]
        return self._rotated_world_bounds(
            origin,
            local_bounds,
            int(piece.get("rotation", 0)),
            int(piece.get("mirror", job.get("mirror", 0))),
        )

    def _piece_chunk_keys(self, job, piece):
        bounds = self._piece_world_bounds(job, piece)
        result = []
        for chunk_x in range(
            int(bounds[0]) >> 4,
            (int(bounds[3]) >> 4) + 1,
        ):
            for chunk_z in range(
                int(bounds[2]) >> 4,
                (int(bounds[5]) >> 4) + 1,
            ):
                result.append(self._slice_key(chunk_x, chunk_z))
        return result

    def _piece_chunks_ready(self, job, piece):
        origin = job.get("anchor", [0, 0, 0])
        offset = piece.get("offset", [0, 0, 0])
        bounds = self._piece_world_bounds(job, piece)
        check_y = int(origin[1]) + int(offset[1])
        for chunk_x in range(
            int(bounds[0]) >> 4,
            (int(bounds[3]) >> 4) + 1,
        ):
            for chunk_z in range(
                int(bounds[2]) >> 4,
                (int(bounds[5]) >> 4) + 1,
            ):
                if not self._chunk_position_ready(
                    chunk_x * 16 + 8,
                    check_y,
                    chunk_z * 16 + 8,
                ):
                    return False
        return True

    def _piece_terrain_ready(self, job, piece):
        slices = self._ensure_chunk_slices(job)
        for key in self._piece_chunk_keys(job, piece):
            state = slices.get(key)
            if not isinstance(state, dict):
                return False
            if not state.get("terrainComplete", True):
                return False
            if not state.get("carveComplete", True):
                return False
        return True

    @staticmethod
    def _slice_key(chunk_x, chunk_z):
        return "%d,%d" % (int(chunk_x), int(chunk_z))

    @staticmethod
    def _chunk_range_for_rectangle(minimum_x, minimum_z, maximum_x, maximum_z):
        result = []
        for chunk_x in range(
            int(minimum_x) >> 4,
            (int(maximum_x) >> 4) + 1,
        ):
            for chunk_z in range(
                int(minimum_z) >> 4,
                (int(maximum_z) >> 4) + 1,
            ):
                result.append((chunk_x, chunk_z))
        return result

    def _ensure_chunk_slices(self, job):
        existing = job.get("chunkSlices")
        if isinstance(existing, dict) and existing:
            if not isinstance(job.get("completedPieces"), list):
                job["completedPieces"] = []
            return existing

        slices = {}
        terrain = job.get("terrain")
        anchor = job.get("anchor", [0, 0, 0])
        completed_pieces = set(
            int(value) for value in job.get("completedPieces", [])
        )
        if not completed_pieces:
            completed_pieces.update(
                range(
                    min(
                        int(job.get("nextPiece", 0)),
                        len(job.get("pieces", [])),
                    )
                )
            )

        if isinstance(terrain, dict):
            width = max(1, int(terrain.get("width", 1)))
            depth = max(1, int(terrain.get("depth", 1)))
            minimum_x = int(anchor[0])
            minimum_z = int(anchor[2])
            maximum_x = minimum_x + width - 1
            maximum_z = minimum_z + depth - 1
            old_next_column = max(0, int(terrain.get("nextColumn", 0)))
            for chunk_x, chunk_z in self._chunk_range_for_rectangle(
                minimum_x,
                minimum_z,
                maximum_x,
                maximum_z,
            ):
                slice_minimum_x = max(minimum_x, chunk_x * 16)
                slice_minimum_z = max(minimum_z, chunk_z * 16)
                slice_maximum_x = min(maximum_x, chunk_x * 16 + 15)
                slice_maximum_z = min(maximum_z, chunk_z * 16 + 15)
                slice_width = slice_maximum_x - slice_minimum_x + 1
                completed_columns = 0
                for world_z in range(
                    slice_minimum_z,
                    slice_maximum_z + 1,
                ):
                    for world_x in range(
                        slice_minimum_x,
                        slice_maximum_x + 1,
                    ):
                        global_column = (
                            (world_z - minimum_z) * width
                            + (world_x - minimum_x)
                        )
                        if global_column < old_next_column:
                            completed_columns += 1
                total_slice_columns = (
                    slice_width
                    * (slice_maximum_z - slice_minimum_z + 1)
                )
                key = self._slice_key(chunk_x, chunk_z)
                slices[key] = {
                    "chunkX": chunk_x,
                    "chunkZ": chunk_z,
                    "terrainBounds": [
                        slice_minimum_x,
                        slice_minimum_z,
                        slice_maximum_x,
                        slice_maximum_z,
                    ],
                    "terrainNext": completed_columns,
                    "terrainComplete": bool(terrain.get("complete"))
                    or completed_columns >= total_slice_columns,
                    "carveComplete": bool(
                        job.get("hollowHillCarveComplete")
                    ),
                    "pieceIndices": [],
                    "complete": False,
                }

        for piece_index, piece in enumerate(job.get("pieces", [])):
            offset = piece.get("offset", [0, 0, 0])
            chunk_x = (int(anchor[0]) + int(offset[0])) >> 4
            chunk_z = (int(anchor[2]) + int(offset[2])) >> 4
            owner_key = self._slice_key(chunk_x, chunk_z)
            for key in self._piece_chunk_keys(job, piece):
                state = slices.get(key)
                if state is None:
                    chunk_values = key.split(",", 1)
                    state = {
                        "chunkX": int(chunk_values[0]),
                        "chunkZ": int(chunk_values[1]),
                        "terrainComplete": True,
                        "carveComplete": bool(
                            job.get("hollowHillCarveComplete")
                            or str(job.get("kind", ""))
                            not in ruin_logic.HOLLOW_HILL_KIND_DATA
                        ),
                        "pieceIndices": [],
                        "complete": False,
                    }
                    slices[key] = state
            slices[owner_key]["pieceIndices"].append(piece_index)

        if not slices:
            chunk_x = int(anchor[0]) >> 4
            chunk_z = int(anchor[2]) >> 4
            slices[self._slice_key(chunk_x, chunk_z)] = {
                "chunkX": chunk_x,
                "chunkZ": chunk_z,
                "terrainComplete": True,
                "carveComplete": True,
                "pieceIndices": [],
                "complete": False,
            }

        for state in slices.values():
            if str(job.get("kind", "")) not in ruin_logic.HOLLOW_HILL_KIND_DATA:
                state["carveComplete"] = True
            pending_piece = any(
                int(piece_index) not in completed_pieces
                for piece_index in state.get("pieceIndices", [])
            )
            state["complete"] = bool(
                state.get("terrainComplete")
                and state.get("carveComplete")
                and not pending_piece
            )

        job["completedPieces"] = sorted(completed_pieces)
        job["chunkSlices"] = slices
        self._refresh_courtyard_spawner_ready(job, completed_pieces)
        return slices

    def _slice_has_runnable_work(self, job, state):
        if not state.get("terrainComplete"):
            return True
        if not state.get("carveComplete"):
            return True
        completed = set(
            int(value) for value in job.get("completedPieces", [])
        )
        pending = [
            int(piece_index)
            for piece_index in state.get("pieceIndices", [])
            if int(piece_index) not in completed
        ]
        if not pending:
            return True
        pieces = job.get("pieces", [])
        return any(
            piece_index < len(pieces)
            and self._piece_terrain_ready(job, pieces[piece_index])
            for piece_index in pending
        )

    def _slice_player_distance_squared(self, state, players):
        center_x = int(state["chunkX"]) * 16 + 8
        center_z = int(state["chunkZ"]) * 16 + 8
        nearest = None
        for player in players or []:
            try:
                if int(player.get("dimensionId", -1)) != self._dimension_id:
                    continue
                position = player["position"]
                delta_x = float(position[0]) - center_x
                delta_z = float(position[2]) - center_z
                distance = delta_x * delta_x + delta_z * delta_z
            except (IndexError, KeyError, TypeError, ValueError):
                continue
            if nearest is None or distance < nearest:
                nearest = distance
        return float("inf") if nearest is None else nearest

    def _select_ready_chunk_slice(self, job, players):
        slices = self._ensure_chunk_slices(job)
        active_key = job.get("activeChunkSlice")
        active = slices.get(active_key)
        if (
            isinstance(active, dict)
            and not active.get("complete")
            and self._slice_has_runnable_work(job, active)
            and self._chunk_position_ready(
                int(active["chunkX"]) * 16 + 8,
                int(job.get("anchor", [0, 0, 0])[1]),
                int(active["chunkZ"]) * 16 + 8,
            )
        ):
            return active_key, active

        job.pop("activeChunkSlice", None)
        candidates = sorted(
            (
                (
                    self._slice_player_distance_squared(state, players),
                    str(key),
                    state,
                )
                for key, state in slices.items()
                if not state.get("complete")
                and self._slice_has_runnable_work(job, state)
            ),
            key=lambda item: (item[0], item[1]),
        )
        check_y = int(job.get("anchor", [0, 0, 0])[1])
        checked = 0
        for _distance, key, state in candidates:
            if not self._chunk_position_ready(
                int(state["chunkX"]) * 16 + 8,
                check_y,
                int(state["chunkZ"]) * 16 + 8,
            ):
                checked += 1
                if checked >= MAX_SLICE_READY_CHECKS_PER_JOB:
                    break
                continue
            job["activeChunkSlice"] = key
            return key, state
        return None, None

    def _refresh_courtyard_spawner_ready(
        self,
        job,
        completed_pieces=None,
    ):
        if str(job.get("kind", "")) not in BOSS_VARIETY_LANDMARKS:
            return False
        spawner = job.get("bossSpawner")
        if not isinstance(spawner, dict):
            return False
        offset = spawner.get("offset")
        if not offset or len(offset) != 3:
            return False
        if completed_pieces is None:
            completed_pieces = set(
                int(value) for value in job.get("completedPieces", [])
            )
        else:
            completed_pieces = set(
                int(value) for value in completed_pieces
            )
        marker_x = int(offset[0])
        marker_y = int(offset[1])
        marker_z = int(offset[2])
        for piece_index, piece in enumerate(job.get("pieces", [])):
            piece_offset = piece.get("offset", [0, 0, 0])
            piece_size = piece.get("size", [1, 1, 1])
            if not (
                int(piece_offset[0])
                <= marker_x
                < int(piece_offset[0]) + max(1, int(piece_size[0]))
                and int(piece_offset[1])
                <= marker_y
                < int(piece_offset[1]) + max(1, int(piece_size[1]))
                and int(piece_offset[2])
                <= marker_z
                < int(piece_offset[2]) + max(1, int(piece_size[2]))
            ):
                continue
            ready = piece_index in completed_pieces
            job["bossSpawnerReady"] = ready
            job["bossSpawnerPiece"] = piece_index
            if ready and (
                job.get("bossSpawned") or job.get("bossDefeated")
            ):
                self._remove_courtyard_job_marker(job)
            return ready
        job["bossSpawnerReady"] = False
        return False

    def _advance_terrain_slice(self, job, state):
        terrain = job.get("terrain")
        bounds = state.get("terrainBounds")
        if (
            not isinstance(terrain, dict)
            or not bounds
            or state.get("terrainComplete")
        ):
            state["terrainComplete"] = True
            return True

        minimum_x, minimum_z, maximum_x, maximum_z = [
            int(value) for value in bounds
        ]
        slice_width = maximum_x - minimum_x + 1
        slice_depth = maximum_z - minimum_z + 1
        total_columns = slice_width * slice_depth
        blocks_changed = 0
        columns_started = 0
        while (
            blocks_changed < MAX_TERRAIN_BLOCKS_PER_TICK
            and columns_started < MAX_TERRAIN_COLUMNS_PER_TICK
        ):
            column_index = int(state.get("terrainNext", 0))
            if column_index >= total_columns:
                state["terrainComplete"] = True
                state.pop("activeTerrainColumn", None)
                break
            active = state.get("activeTerrainColumn")
            if not isinstance(active, dict):
                world_x = minimum_x + column_index % slice_width
                world_z = minimum_z + column_index // slice_width
                global_width = max(1, int(terrain.get("width", 1)))
                global_column = (
                    (world_z - int(job["anchor"][2])) * global_width
                    + (world_x - int(job["anchor"][0]))
                )
                active = self._prepare_terrain_column(
                    job,
                    terrain,
                    global_column,
                )
                if active is None:
                    return False
                columns_started += 1
                if active.get("skip") or not active.get("changes"):
                    state["terrainNext"] = column_index + 1
                    continue
                state["activeTerrainColumn"] = active

            changes = active.get("changes", [])
            next_change = int(active.get("nextChange", 0))
            while (
                next_change < len(changes)
                and blocks_changed < MAX_TERRAIN_BLOCKS_PER_TICK
            ):
                y, block_name = changes[next_change]
                if not self._set_terrain_block(
                    active["x"],
                    y,
                    active["z"],
                    block_name,
                ):
                    return False
                next_change += 1
                blocks_changed += 1
                active["nextChange"] = next_change
            if next_change < len(changes):
                break
            state.pop("activeTerrainColumn", None)
            state["terrainNext"] = column_index + 1

        if int(state.get("terrainNext", 0)) >= total_columns:
            state["terrainComplete"] = True
            state.pop("activeTerrainColumn", None)

        completed_columns = sum(
            int(slice_state.get("terrainNext", 0))
            for slice_state in job.get("chunkSlices", {}).values()
        )
        terrain["completedColumns"] = completed_columns
        terrain["nextColumn"] = completed_columns
        terrain["complete"] = all(
            slice_state.get("terrainComplete", True)
            for slice_state in job.get("chunkSlices", {}).values()
        )
        return bool(state.get("terrainComplete"))

    def _advance_hollow_hill_carve_slice(self, job, state):
        kind = str(job.get("kind", ""))
        hill_data = ruin_logic.HOLLOW_HILL_KIND_DATA.get(kind)
        if hill_data is None or state.get("carveComplete"):
            state["carveComplete"] = True
            return True, False
        bounds = state.get("terrainBounds")
        if not bounds:
            state["carveComplete"] = True
            return True, False

        if not job.get("hollowHillCarveStarted"):
            job["hollowHillCarveStarted"] = True
            self._hill_carves_started += 1
            print (
                "[TwilightBossSlice] hollow hill chunk carve started:",
                kind,
                tuple(job.get("anchor", [])),
            )
        minimum_x, minimum_z, maximum_x, maximum_z = [
            int(value) for value in bounds
        ]
        slice_width = maximum_x - minimum_x + 1
        slice_depth = maximum_z - minimum_z + 1
        total_columns = slice_width * slice_depth
        column_index = int(state.get("carveNextColumn", 0))
        next_y = state.get("carveNextY")
        changed = 0
        while (
            changed < MAX_HOLLOW_HILL_CARVE_BLOCKS_PER_TICK
            and column_index < total_columns
        ):
            world_x = minimum_x + column_index % slice_width
            world_z = minimum_z + column_index // slice_width
            cavity = ruin_logic.hollow_hill_generated_cavity_range(
                job,
                world_x,
                world_z,
            )
            if cavity is None:
                column_index += 1
                next_y = None
                continue
            minimum_y, maximum_y = cavity
            y = int(minimum_y if next_y is None else next_y)
            if not self._set_terrain_block(
                world_x,
                y,
                world_z,
                "minecraft:air",
            ):
                state["carveNextColumn"] = column_index
                state["carveNextY"] = y
                return False, True
            changed += 1
            self._hill_carve_blocks += 1
            y += 1
            if y > int(maximum_y):
                column_index += 1
                next_y = None
            else:
                next_y = y

        state["carveNextColumn"] = column_index
        state["carveNextY"] = next_y
        carve = job.get("hollowHillCarve")
        if not isinstance(carve, dict):
            carve = {
                "blocksCleared": 0,
                "complete": False,
            }
            job["hollowHillCarve"] = carve
        carve["blocksCleared"] = int(
            carve.get("blocksCleared", 0)
        ) + changed
        if column_index >= total_columns:
            state["carveComplete"] = True
            state.pop("carveNextY", None)

        all_complete = all(
            slice_state.get("carveComplete", True)
            for slice_state in job.get("chunkSlices", {}).values()
        )
        if all_complete and not job.get("hollowHillCarveComplete"):
            job["hollowHillCarveComplete"] = True
            carve["complete"] = True
            self._hill_carves_completed += 1
            print (
                "[TwilightBossSlice] hollow hill chunk carve completed:",
                kind,
                tuple(job.get("anchor", [])),
                int(carve.get("blocksCleared", 0)),
            )
        return bool(state.get("carveComplete")), False

    def _refresh_automatic_job_completion(self, job):
        completed = set(
            int(value) for value in job.get("completedPieces", [])
        )
        pieces = job.get("pieces", [])
        slices = job.get("chunkSlices", {})
        terrain = job.get("terrain")
        terrain_complete = (
            not isinstance(terrain, dict)
            or all(
                state.get("terrainComplete", True)
                for state in slices.values()
            )
        )
        if isinstance(terrain, dict):
            terrain["complete"] = terrain_complete
        carve_complete = (
            str(job.get("kind", ""))
            not in ruin_logic.HOLLOW_HILL_KIND_DATA
            or all(
                state.get("carveComplete", True)
                for state in slices.values()
            )
        )
        if (
            carve_complete
            and str(job.get("kind", ""))
            in ruin_logic.HOLLOW_HILL_KIND_DATA
        ):
            job["hollowHillCarveComplete"] = True
        all_complete = (
            terrain_complete
            and carve_complete
            and len(completed) >= len(pieces)
            and all(state.get("complete") for state in slices.values())
        )
        if completed:
            contiguous = 0
            while contiguous in completed:
                contiguous += 1
            job["nextPiece"] = contiguous
            job["templateCursor"] = contiguous
        if all_complete:
            if not self._verify_template_markers(job):
                job["state"] = "placing"
                job["finalCommit"] = False
                return False
            job["markersVerified"] = True
            job["finalCommit"] = True
            job["state"] = "complete"
            job.pop("activeChunkSlice", None)
        elif completed or any(
            state.get("terrainNext", 0) > 0
            or state.get("carveNextColumn", 0) > 0
            for state in slices.values()
        ):
            job["state"] = "placing"
        return all_complete

    def _verify_template_markers(self, job):
        """Verify physical route markers before committing a landmark.

        Marker-bearing templates fail closed: a missing pedestal or boss
        group marker keeps the ledger in ``placing`` so a restart can retry
        the affected slice instead of recording a truncated landmark.
        """
        if not job.get("placementProfile"):
            return True
        markers = job.get("markers")
        anchor = job.get("anchor")
        if not isinstance(markers, dict) or not anchor:
            job["markersVerified"] = False
            return False
        verified = 0
        required = 0
        for marker in markers.values():
            marker_values = marker if isinstance(marker, list) else [marker]
            for value in marker_values:
                if not isinstance(value, dict):
                    continue
                expected = value.get("block")
                offset = value.get("offset")
                if not expected or not offset or len(offset) != 3:
                    continue
                required += 1
                position = tuple(
                    int(anchor[index]) + int(offset[index])
                    for index in range(3)
                )
                if self._block_name(*position) == str(expected):
                    verified += 1
        job["markerVerification"] = {
            "required": required,
            "verified": verified,
        }
        job["markersVerified"] = bool(required and verified == required)
        return job["markersVerified"]

    def _advance_automatic_job(self, job_key, job, current_tick, players):
        _slice_key, state = self._select_ready_chunk_slice(job, players)
        if state is None:
            self._chunk_ready_waits += 1
            return

        if not state.get("terrainComplete"):
            completed = self._advance_terrain_slice(job, state)
            if completed:
                self._persist()
            self._refresh_automatic_job_completion(job)
            return

        if not state.get("carveComplete"):
            completed, failed = self._advance_hollow_hill_carve_slice(
                job,
                state,
            )
            if failed:
                ruin_logic.record_job_failure(job, MAX_RETRIES)
                self._persist()
                return
            if completed:
                self._persist()
            self._refresh_automatic_job_completion(job)
            return

        completed_pieces = set(
            int(value) for value in job.get("completedPieces", [])
        )
        pending = [
            int(piece_index)
            for piece_index in state.get("pieceIndices", [])
            if int(piece_index) not in completed_pieces
        ]
        if pending:
            piece_index = pending[0]
            piece = job.get("pieces", [])[piece_index]
            if not self._piece_terrain_ready(job, piece):
                job.pop("activeChunkSlice", None)
                return
            if not self._piece_chunks_ready(job, piece):
                job.pop("activeChunkSlice", None)
                self._chunk_ready_waits += 1
                return
            if not self._place_piece(job, piece):
                ruin_logic.record_job_failure(job, MAX_RETRIES)
                self._persist()
                return
            completed_pieces.add(piece_index)
            job["completedPieces"] = sorted(completed_pieces)
            job["templateCursor"] = len(completed_pieces)
            job["state"] = "placing"
            self._refresh_courtyard_spawner_ready(
                job,
                completed_pieces,
            )

        pending_after = any(
            int(piece_index) not in completed_pieces
            for piece_index in state.get("pieceIndices", [])
        )
        if not pending_after:
            state["complete"] = True
            job.pop("activeChunkSlice", None)
        job_complete = self._refresh_automatic_job_completion(job)
        if (
            job_complete
            or len(completed_pieces) % PIECE_CHECKPOINT_COUNT == 0
            or state.get("complete")
        ):
            self._persist()

    def _job_schedule_priority(self, key, job, players):
        kind = str(job.get("kind", ""))
        if kind == "naga_courtyard":
            category = 0
        elif not str(key).startswith("native:"):
            category = 1
        else:
            category = 2

        nearest_distance = self._job_player_distance_squared(job, players)
        if nearest_distance is None:
            nearest_distance = float("inf")
        active_rank = 0 if key in self._areas else 1
        return (category, nearest_distance, active_rank, str(key))

    def _next_persistent_job(self, players):
        # Persistent construction is reserved for an explicit administrator
        # placement. Natural landmarks are complete surface-pass templates;
        # watchdog, loaded-chunk, proximity, migration and repair records may
        # never become Tick-driven terrain/structure jobs.
        self._scheduled_job_key = None

        candidates = [
            (key, job)
            for key, job in self._ledger.items()
            if job.get("state") in ("planned", "placing")
            and (
                str(key).startswith("manual:")
                or str(job.get("kind", ""))
                in PERSISTENT_TEMPLATE_LANDMARKS
            )
        ]
        if candidates:
            ordered = sorted(
                candidates,
                key=lambda item: self._job_schedule_priority(
                    item[0],
                    item[1],
                    players,
                ),
            )
            for key, job in ordered:
                _slice_key, state = self._select_ready_chunk_slice(
                    job,
                    players,
                )
                if state is not None:
                    return key, job, True
            self._chunk_ready_waits += 1
        if self._manual_jobs:
            return "manual", self._manual_jobs[0], False
        return None, None, False

    def _advance_one_job(self, current_tick, players):
        job_key, job, persistent = self._next_persistent_job(players)
        if job is None:
            return
        if persistent:
            self._advance_automatic_job(
                job_key,
                job,
                current_tick,
                players,
            )
            return

        # Explicit administrator/debug placement keeps the old temporary
        # loading behavior. Automatic worldgen never enters this branch.
        if job_key not in self._areas:
            if not self._start_area(job_key, job, current_tick):
                return
        area = self._areas.get(job_key)
        if area is None or int(current_tick) < area["readyTick"]:
            return
        if not area.get("chunksReady", False):
            if int(current_tick) < int(area["nextChunkCheckTick"]):
                return
            if not self._job_chunks_ready(job):
                self._chunk_ready_waits += 1
                area["nextChunkCheckTick"] = (
                    int(current_tick) + AREA_CHUNK_READY_RECHECK_TICKS
                )
                return
            area["chunksReady"] = True

        terrain = job.get("terrain")
        if isinstance(terrain, dict) and not terrain.get("complete"):
            before_column = int(terrain.get("nextColumn", 0))
            terrain_complete = self._advance_terrain(job)
            after_column = int(terrain.get("nextColumn", 0))
            crossed_checkpoint = (
                after_column // TERRAIN_CHECKPOINT_COLUMNS
                > before_column // TERRAIN_CHECKPOINT_COLUMNS
            )
            if persistent and (terrain_complete or crossed_checkpoint):
                self._persist()
            return

        start = int(job.get("nextPiece", 0))
        pieces = job.get("pieces", [])
        if start >= len(pieces):
            if self._verify_template_markers(job):
                job["markersVerified"] = True
                job["finalCommit"] = True
                job["state"] = "complete"
            else:
                job["finalCommit"] = False
                job["state"] = "placing"
                return
            if not persistent:
                self._release_area(job_key)
            if not persistent:
                self._manual_jobs.pop(0)
            else:
                self._persist()
            return

        if (
            str(job.get("kind", "")) in ruin_logic.HOLLOW_HILL_KIND_DATA
            and not job.get("hollowHillCarveComplete")
        ):
            carve = job.get("hollowHillCarve") or {}
            before_blocks = int(carve.get("blocksCleared", 0))
            carve_complete, carve_failed = self._advance_hollow_hill_carve(job)
            after_blocks = int(
                job.get("hollowHillCarve", {}).get("blocksCleared", 0)
            )
            crossed_checkpoint = (
                after_blocks // HOLLOW_HILL_CARVE_CHECKPOINT_BLOCKS
                > before_blocks // HOLLOW_HILL_CARVE_CHECKPOINT_BLOCKS
            )
            if carve_failed:
                ruin_logic.record_job_failure(job, MAX_RETRIES)
                if not persistent:
                    self._release_area(job_key)
                if persistent:
                    self._persist()
                elif job["state"] == "failed":
                    self._manual_jobs.pop(0)
                return
            job["state"] = "placing"
            if persistent and (carve_complete or crossed_checkpoint):
                self._persist()
            return

        placed = 0
        while placed < MAX_PIECES_PER_TICK and start < len(pieces):
            if not self._place_piece(job, pieces[start]):
                ruin_logic.record_job_failure(job, MAX_RETRIES)
                if not persistent:
                    self._release_area(job_key)
                if persistent:
                    self._persist()
                elif job["state"] == "failed":
                    self._manual_jobs.pop(0)
                return
            start += 1
            placed += 1
            job["nextPiece"] = start
            job["templateCursor"] = start
            job["state"] = "placing"

        if start >= len(pieces):
            if self._verify_template_markers(job):
                job["markersVerified"] = True
                job["finalCommit"] = True
                job["state"] = "complete"
            else:
                job["finalCommit"] = False
                job["state"] = "placing"
                return
            if not persistent:
                self._release_area(job_key)
            if not persistent:
                self._manual_jobs.pop(0)
        if persistent and (
            job.get("state") in ("complete", "failed")
            or int(job.get("nextPiece", 0)) % PIECE_CHECKPOINT_COUNT == 0
        ):
            self._persist()

    def _remove_courtyard_marker_at(self, marker_position):
        marker_position = tuple(int(value) for value in marker_position)
        try:
            current = self._block.GetBlockNew(
                marker_position,
                self._dimension_id,
            )
            current_name = (
                str(current.get("name", ""))
                if isinstance(current, dict)
                else str(current[0]) if current else ""
            )
            if current_name not in (
                COURTYARD_SPAWNER_BLOCK,
                LICH_SPAWNER_BLOCK,
                MINOSHROOM_SPAWNER_BLOCK,
                HYDRA_SPAWNER_BLOCK,
                KNIGHT_PHANTOM_SPAWNER_BLOCK,
                UR_GHAST_SPAWNER_BLOCK,
                "minecraft:air",
                "minecraft:cave_air",
                "minecraft:void_air",
            ):
                return False
            return self._block.SetBlockNew(
                marker_position,
                {"name": "minecraft:air", "aux": 0},
                0,
                self._dimension_id,
                True,
                False,
            )
        except Exception as error:
            print (
                "[TwilightBossSlice] courtyard spawner cleanup failed:",
                marker_position,
                error,
            )
            return False

    @staticmethod
    def _courtyard_expected_marker_position(job):
        spawner = job.get("bossSpawner")
        anchor = job.get("anchor")
        if not isinstance(spawner, dict) or not anchor:
            return None
        offset = spawner.get("offset")
        if not offset or len(offset) != 3 or len(anchor) != 3:
            return None
        return tuple(
            int(anchor[index]) + int(offset[index])
            for index in range(3)
        )

    @classmethod
    def _courtyard_marker_position(cls, job):
        physical = job.get("physicalBossSpawnerMarker")
        if physical and len(physical) == 3:
            return tuple(int(value) for value in physical)
        return cls._courtyard_expected_marker_position(job)

    def _courtyard_spawn_position(self, job):
        marker = self._courtyard_marker_position(job)
        if marker is None:
            return None
        below = (marker[0], marker[1] - 1, marker[2])
        spawn_y = marker[1]
        if self._block_name(below[0], below[1], below[2]) in (
            COURTYARD_EMPTY_COLLISION_BLOCKS
        ):
            # BossSpawnerBlockEntity places the source Naga one block below
            # its marker whenever that block has an empty collision shape.
            spawn_y = below[1]
        return (marker[0] + 0.5, float(spawn_y), marker[2] + 0.5)

    def _remove_courtyard_job_marker(self, job):
        markers = []
        expected = self._courtyard_expected_marker_position(job)
        if expected is not None:
            markers.append(expected)
        physical = job.get("physicalBossSpawnerMarker")
        if physical and len(physical) == 3:
            marker = tuple(int(value) for value in physical)
            if marker not in markers:
                markers.append(marker)
        removed = False
        for marker in markers:
            removed = self._remove_courtyard_marker_at(marker) or removed
        return removed

    def _commit_courtyard_boss(self, job, boss_id):
        job["bossSpawned"] = True
        job["bossEntityId"] = str(boss_id)
        job.pop("bossSpawnPendingId", None)
        job.pop("bossSpawnPendingUntil", None)
        self._remove_courtyard_job_marker(job)

    def _activate_courtyard_bosses(self, players, current_tick):
        if self._boss_spawner is None:
            return
        changed = False
        for ledger_key in list(self._boss_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict):
                self._boss_job_keys.discard(ledger_key)
                self._courtyard_job_keys.discard(ledger_key)
                continue
            pending_id = job.get("bossSpawnPendingId")
            if pending_id:
                expected_entity = str(
                    job.get("bossSpawner", {}).get(
                        "entity",
                        "tf_slice:forest_wyrm",
                    )
                )
                if self._confirmed_boss_identifier(
                    job,
                    pending_id,
                    expected_entity,
                ) == expected_entity:
                    self._commit_courtyard_boss(job, pending_id)
                    changed = True
                    continue
                if int(current_tick) < int(
                    job.get("bossSpawnPendingUntil", 0)
                ):
                    continue
                job.pop("bossSpawnPendingId", None)
                job.pop("bossSpawnPendingUntil", None)
                changed = True
            if str(job.get("kind", "")) == "naga_courtyard":
                activation_position = ruin_logic.courtyard_activation_position(
                    job,
                    players,
                    self._dimension_id,
                )
                spawn_position = (
                    self._courtyard_spawn_position(job)
                    if activation_position is not None
                    else None
                )
            else:
                spawn_position = ruin_logic.boss_activation_position(
                    job,
                    players,
                    self._dimension_id,
                )
            if spawn_position is None:
                continue
            spawner = job.get("bossSpawner", {})
            try:
                boss_id = self._boss_spawner(
                    spawner.get("entity", "tf_slice:forest_wyrm"),
                    spawn_position,
                    180.0,
                    self._dimension_id,
                )
            except Exception as error:
                print "[TwilightBossSlice] landmark boss spawn failed:", error
                boss_id = None
            if not boss_id:
                continue
            expected_entity = str(
                spawner.get("entity", "tf_slice:forest_wyrm")
            )
            if self._confirmed_boss_identifier(
                job,
                boss_id,
                expected_entity,
            ) == expected_entity:
                self._commit_courtyard_boss(job, boss_id)
            else:
                job["bossSpawnPendingId"] = str(boss_id)
                job["bossSpawnPendingUntil"] = (
                    int(current_tick) + COURTYARD_BOSS_CONFIRMATION_TICKS
                )
            changed = True
        if changed:
            self._persist()

    def _confirmed_boss_identifier(self, job, entity_id, expected_entity):
        if (
            str(job.get("kind", "")) in (
                "naga_courtyard",
                "lich_tower",
            )
            and self._boss_confirmer is not None
        ):
            try:
                return self._boss_confirmer(entity_id, expected_entity)
            except Exception as error:
                print (
                    "[TwilightBossSlice] courtyard boss confirmation failed:",
                    entity_id,
                    error,
                )
                return None
        return self._entity_identifier(entity_id)

    def _entity_identifier(self, entity_id):
        candidates = [entity_id]
        string_id = str(entity_id)
        if entity_id != string_id:
            candidates.append(string_id)
        try:
            numeric_id = int(string_id)
            if numeric_id != entity_id:
                candidates.append(numeric_id)
        except (TypeError, ValueError):
            pass
        for candidate in candidates:
            try:
                component = self._factory.CreateEngineType(candidate)
                identifier = str(component.GetEngineTypeStr())
                if identifier:
                    return identifier
            except Exception:
                continue
        return None

    def _count_hollow_hill_monsters(self, job):
        bounds = job.get("bounds")
        if not bounds or len(bounds) != 6:
            self._hill_spawn_query_failures += 1
            return ruin_logic.HOLLOW_HILL_LOCAL_MONSTER_CAPS.get(
                str(job.get("kind", "")),
                0,
            )
        try:
            entity_ids = self._game.GetEntitiesInSquareArea(
                None,
                (bounds[0], bounds[1], bounds[2]),
                (bounds[3] + 1, bounds[4] + 1, bounds[5] + 1),
                self._dimension_id,
            )
        except Exception:
            entity_ids = None
        if entity_ids is None:
            self._hill_spawn_query_failures += 1
            return ruin_logic.HOLLOW_HILL_LOCAL_MONSTER_CAPS.get(
                str(job.get("kind", "")),
                0,
            )
        return sum(
            1
            for entity_id in entity_ids
            if self._entity_identifier(entity_id)
            in ruin_logic.HOLLOW_HILL_CONTROLLED_MOBS
        )

    def _is_hollow_hill_spawn_position_clear(self, position):
        block_x = int(math.floor(position[0]))
        block_y = int(math.floor(position[1]))
        block_z = int(math.floor(position[2]))
        try:
            ground = self._block.GetBlockNew(
                (block_x, block_y - 1, block_z),
                self._dimension_id,
            )
            feet = self._block.GetBlockNew(
                (block_x, block_y, block_z),
                self._dimension_id,
            )
            head = self._block.GetBlockNew(
                (block_x, block_y + 1, block_z),
                self._dimension_id,
            )
        except Exception:
            return False
        ground_name = str((ground or {}).get("name", ""))
        feet_name = str((feet or {}).get("name", ""))
        head_name = str((head or {}).get("name", ""))
        return (
            ground_name not in HOLLOW_HILL_SPAWN_AIR_BLOCKS
            and feet_name in HOLLOW_HILL_SPAWN_AIR_BLOCKS
            and head_name in HOLLOW_HILL_SPAWN_AIR_BLOCKS
        )

    def _spawn_hollow_hill_group(
        self,
        _ledger_key,
        job,
        player,
        current_tick,
        players=None,
    ):
        kind = str(job.get("kind", ""))
        local_cap = ruin_logic.HOLLOW_HILL_LOCAL_MONSTER_CAPS.get(kind)
        if local_cap is None:
            return 0
        active_monsters = self._count_hollow_hill_monsters(job)
        remaining = int(local_cap) - int(active_monsters)
        if remaining <= 0:
            return 0
        center = job.get("center") or job.get("anchor") or (0, 0, 0)
        center_x = int(center[0])
        center_z = int(center[1] if len(center) == 2 else center[2])
        spawn_seed = ruin_logic.landmark_stream_seed(
            self._world_seed,
            center_x,
            center_z,
            kind,
            "spawn_group",
            int(current_tick),
        )
        selected = ruin_logic.hollow_hill_spawn_choice(
            kind,
            spawn_seed,
        )
        if selected is None:
            return 0
        requested = min(remaining, int(selected["count"]))
        candidates = ruin_logic.hollow_hill_spawn_candidates(
            job,
            player.get("position"),
            ruin_logic.landmark_stream_seed(
                self._world_seed,
                center_x,
                center_z,
                kind,
                "spawn_position",
                int(current_tick),
            ),
            requested * 3,
        )
        spawned = 0
        for position, yaw in candidates:
            if not self._controlled_spawn_position_allowed(
                job,
                position,
                players if players is not None else (player,),
            ):
                continue
            if not self._is_hollow_hill_spawn_position_clear(position):
                continue
            try:
                entity_id = self._entity_spawner(
                    selected["identifier"],
                    position,
                    yaw,
                    self._dimension_id,
                )
            except Exception as error:
                print (
                    "[TwilightBossSlice] hollow hill controlled spawn failed:",
                    selected["identifier"],
                    error,
                )
                entity_id = None
            if not entity_id:
                continue
            spawned += 1
            self._hill_spawn_entities += 1
            if spawned >= requested:
                break
        if spawned:
            self._hill_spawn_groups += 1
        return spawned

    def _controlled_spawn_attempt_due(self, ledger_key, job, current_tick):
        pacing_key = str(ledger_key)
        current_tick = int(current_tick)
        next_tick = self._controlled_spawn_next_ticks.get(pacing_key)
        if next_tick is not None and current_tick < int(next_tick):
            return False
        center = job.get("center") or job.get("anchor") or (0, 0, 0)
        center_x = int(center[0]) if center else 0
        center_z = int(center[1] if len(center) == 2 else center[2])
        rng = ruin_logic.JavaRandom(
            ruin_logic.landmark_stream_seed(
                self._world_seed,
                center_x,
                center_z,
                str(job.get("kind", "controlled_structure")),
                "spawn_pacing_%s" % pacing_key,
                current_tick,
            )
        )
        cooldown_range = (
            CONTROLLED_SPAWN_MAX_COOLDOWN_TICKS
            - CONTROLLED_SPAWN_MIN_COOLDOWN_TICKS
            + 1
        )
        self._controlled_spawn_next_ticks[pacing_key] = (
            current_tick
            + CONTROLLED_SPAWN_MIN_COOLDOWN_TICKS
            + rng.next_int(cooldown_range)
        )
        return rng.next_int(CONTROLLED_SPAWN_CHANCE_DENOMINATOR) == 0

    def _spawn_hollow_hill_monsters(self, current_tick, players):
        if self._entity_spawner is None:
            return
        if int(current_tick) % HOLLOW_HILL_SPAWN_INTERVAL_TICKS != 0:
            return
        active_hills_scanned = 0
        for ledger_key in sorted(self._hollow_hill_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict):
                self._hollow_hill_job_keys.discard(ledger_key)
                continue
            active_player = None
            for player in players:
                if ruin_logic.player_inside_completed_hollow_hill(
                    job,
                    player,
                    self._dimension_id,
                ):
                    active_player = player
                    break
            if active_player is None:
                continue
            if not self._controlled_spawn_attempt_due(
                "hollow_hill:%s" % str(ledger_key),
                job,
                current_tick,
            ):
                continue
            active_hills_scanned += 1
            self._spawn_hollow_hill_group(
                ledger_key,
                job,
                active_player,
                current_tick,
                players,
            )
            if active_hills_scanned >= MAX_HOLLOW_HILL_GROUPS_PER_SCAN:
                break

    def _count_lich_tower_monsters(self, job):
        bounds = job.get("bounds")
        if not bounds or len(bounds) != 6:
            return LICH_TOWER_LOCAL_MONSTER_CAP
        try:
            entity_ids = self._game.GetEntitiesInSquareArea(
                None,
                (bounds[0], bounds[1], bounds[2]),
                (bounds[3] + 1, bounds[4] + 1, bounds[5] + 1),
                self._dimension_id,
            )
        except Exception:
            entity_ids = None
        if entity_ids is None:
            return LICH_TOWER_LOCAL_MONSTER_CAP
        return sum(
            1
            for entity_id in entity_ids
            if self._entity_identifier(entity_id)
            in ruin_logic.LICH_TOWER_CONTROLLED_MOBS
        )

    def _lich_tower_player(self, job, players):
        bounds = job.get("bounds")
        if not bounds or len(bounds) != 6:
            return None
        center_x = (float(bounds[0]) + float(bounds[3])) * 0.5
        center_z = (float(bounds[2]) + float(bounds[5])) * 0.5
        radius_squared = 32.0 * 32.0
        for player in players or []:
            try:
                if int(player.get("dimensionId", -1)) != self._dimension_id:
                    continue
                position = player["position"]
                dx = float(position[0]) - center_x
                dz = float(position[2]) - center_z
            except (IndexError, KeyError, TypeError, ValueError):
                continue
            if dx * dx + dz * dz <= radius_squared:
                return player
        return None

    def _spawn_lich_tower_group(self, job, current_tick, players=None):
        remaining = (
            LICH_TOWER_LOCAL_MONSTER_CAP
            - self._count_lich_tower_monsters(job)
        )
        if remaining <= 0:
            return 0
        center = job.get("center") or (0, 0)
        seed = ruin_logic.landmark_stream_seed(
            self._world_seed,
            int(center[0]),
            int(center[1]),
            "lich_tower",
            "spawn_group",
            int(current_tick),
        )
        identifier, requested = ruin_logic.lich_tower_spawn_choice(seed)
        requested = min(int(requested), int(remaining))
        spawn_job = job
        contract = job.get("controlledSpawns") or {}
        if not contract.get("interiorOffsets"):
            entry = self._catalog.get("lich_tower") or {}
            variants = entry.get("variants", [])
            try:
                variant = variants[int(job.get("variant", 0))]
            except (IndexError, TypeError, ValueError):
                variant = {}
            resolved = self._controlled_spawns_for_variant(
                entry,
                variant,
                contract,
            )
            spawn_job = dict(job)
            spawn_job["controlledSpawns"] = resolved
        candidates = ruin_logic.lich_tower_spawn_candidates(
            spawn_job,
            seed ^ 0x544F574552,
            max(12, requested * 12),
        )
        spawned = 0
        for position, yaw in candidates:
            if not self._controlled_spawn_position_allowed(
                job,
                position,
                players or (),
            ):
                continue
            if not self._chunk_position_ready(*position):
                continue
            if not self._is_hollow_hill_spawn_position_clear(position):
                continue
            try:
                entity_id = self._entity_spawner(
                    identifier,
                    position,
                    yaw,
                    self._dimension_id,
                )
            except Exception as error:
                print "[TwilightBossSlice] Lich Tower spawn failed:", error
                entity_id = None
            if not entity_id:
                continue
            spawned += 1
            self._lich_tower_spawn_entities += 1
            if spawned >= requested:
                break
        if spawned:
            self._lich_tower_spawn_groups += 1
        return spawned

    def _spawn_lich_tower_monsters(self, current_tick, players):
        if self._entity_spawner is None:
            return
        if int(current_tick) % LICH_TOWER_SPAWN_INTERVAL_TICKS != 0:
            return
        for ledger_key in sorted(self._boss_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict) or job.get("kind") != "lich_tower":
                continue
            if job.get("state") != "complete":
                continue
            if self._lich_tower_player(job, players) is None:
                continue
            if not self._controlled_spawn_attempt_due(
                "lich_tower:%s" % str(ledger_key),
                job,
                current_tick,
            ):
                continue
            self._spawn_lich_tower_group(job, current_tick, players)
            # One active tower per scan keeps the mobile budget bounded.
            break

    def mark_boss_defeated(self, home, boss_kind=None, reward_claimed=False):
        if home is None:
            return False
        changed = False
        for ledger_key in list(self._boss_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict):
                self._boss_job_keys.discard(ledger_key)
                self._courtyard_job_keys.discard(ledger_key)
                continue
            job_boss_kind = str(job.get("bossKind", ""))
            if not job_boss_kind and str(job.get("kind", "")) == "naga_courtyard":
                # Compatibility with pre-bossKind courtyard ledgers.
                job_boss_kind = "naga"
            if boss_kind is not None and job_boss_kind != str(boss_kind):
                continue
            spawner = job.get("bossSpawner")
            anchor = job.get("anchor")
            if not spawner or not anchor:
                continue
            offset = spawner.get("offset", [0, 0, 0])
            spawn_x = float(anchor[0]) + float(offset[0]) + 0.5
            spawn_z = float(anchor[2]) + float(offset[2]) + 0.5
            dx = float(home[0]) - spawn_x
            dz = float(home[2]) - spawn_z
            if dx * dx + dz * dz > 64.0:
                continue
            job["bossSpawned"] = True
            job["bossDefeated"] = True
            job.pop("bossEntityId", None)
            job.pop("bossSpawnPendingId", None)
            job.pop("bossSpawnPendingUntil", None)
            if reward_claimed:
                job["rewardClaimed"] = True
            changed = True
        if changed:
            self._persist()
        return changed

    def mark_naga_defeated(self, home):
        return self.mark_boss_defeated(home, "naga")

    def claim_boss_reward(self, home, boss_kind):
        """Atomically reserve the one reward for a defeated landmark boss."""
        if home is None:
            return False
        for ledger_key in list(self._boss_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict):
                continue
            if str(job.get("bossKind", "")) != str(boss_kind):
                continue
            if not job.get("bossDefeated") or job.get("rewardClaimed"):
                continue
            spawner = job.get("bossSpawner") or {}
            anchor = job.get("anchor") or []
            offset = spawner.get("offset") or []
            if len(anchor) != 3 or len(offset) != 3:
                continue
            spawn_x = float(anchor[0]) + float(offset[0]) + 0.5
            spawn_z = float(anchor[2]) + float(offset[2]) + 0.5
            dx = float(home[0]) - spawn_x
            dz = float(home[2]) - spawn_z
            if dx * dx + dz * dz > 64.0:
                continue
            job["rewardClaimed"] = True
            if not self._persist():
                job["rewardClaimed"] = False
                return False
            return True
        return False

    def is_locked_lich_tower_position(self, position):
        """Return whether progression protection owns this tower block."""
        if position is None or len(position) < 3:
            return False
        try:
            x = float(position[0])
            y = float(position[1])
            z = float(position[2])
        except (TypeError, ValueError):
            return False
        for ledger_key in list(self._boss_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict):
                continue
            if str(job.get("kind", "")) != "lich_tower":
                continue
            if job.get("bossDefeated"):
                continue
            bounds = job.get("bounds") or []
            if len(bounds) != 6:
                continue
            if (
                float(bounds[0]) <= x <= float(bounds[3])
                and float(bounds[1]) <= y <= float(bounds[4])
                and float(bounds[2]) <= z <= float(bounds[5])
            ):
                return True
        return False

    def route_landmark_kind_at_position(self, position):
        """Return the protected route landmark owning a world position."""
        if position is None or len(position) < 3:
            return None
        try:
            x, y, z = (float(position[index]) for index in range(3))
        except (TypeError, ValueError):
            return None
        for job in self._ledger.values():
            if not isinstance(job, dict):
                continue
            kind = str(job.get("kind", ""))
            if kind not in (
                "labyrinth",
                "hydra_lair",
                "knight_stronghold",
                "dark_tower",
            ):
                continue
            bounds = job.get("bounds") or ()
            if len(bounds) != 6:
                continue
            if (
                float(bounds[0]) <= x <= float(bounds[3])
                and float(bounds[1]) <= y <= float(bounds[4])
                and float(bounds[2]) <= z <= float(bounds[5])
            ):
                return kind
        return None

    def labyrinth_map_context(self, position, labyrinth_id=None):
        """Return compiled map metadata for the Labyrinth owning a player."""
        if position is None or len(position) < 3:
            return None
        try:
            x, y, z = (float(position[index]) for index in range(3))
        except (TypeError, ValueError):
            return None
        jobs = []
        for ledger_key, job in self._ledger.items():
            jobs.append((str(ledger_key), job))
        for index, job in enumerate(self._manual_jobs):
            jobs.append(("manual,%d" % index, job))
        for job_id, job in jobs:
            if not isinstance(job, dict) or job.get("kind") != "labyrinth":
                continue
            if labyrinth_id is not None and str(labyrinth_id) != job_id:
                continue
            bounds = job.get("bounds") or ()
            anchor = job.get("anchor") or ()
            markers = job.get("markers") or {}
            if len(bounds) != 6 or len(anchor) != 3:
                continue
            if not (
                float(bounds[0]) <= x <= float(bounds[3])
                and float(bounds[1]) <= y <= float(bounds[4])
                and float(bounds[2]) <= z <= float(bounds[5])
            ):
                continue
            try:
                local_levels = [int(value) for value in markers.get("levels", (1, 8))]
            except (TypeError, ValueError):
                continue
            if not local_levels:
                continue
            world_levels = [int(anchor[1]) + value for value in local_levels]
            level_y = min(world_levels, key=lambda value: abs(float(value) - y))
            local_y = level_y - int(anchor[1])
            map_center = markers.get("mapCenter") or (55, local_y, 55)
            return {
                "labyrinthId": job_id,
                "center": [
                    int(anchor[0]) + int(map_center[0]),
                    int(level_y),
                    int(anchor[2]) + int(map_center[2]),
                ],
                "structureOrigin": [int(anchor[0]), int(anchor[2])],
                "levelLocalY": int(local_y),
                "passageRuns": copy.deepcopy(
                    (markers.get("mapPassageRuns") or {}).get(
                        str(local_y),
                        (),
                    )
                ),
            }
        return None

    def blocked_lich_activators(self, players):
        """List nearby players held back by the Naga progression gate."""
        blocked = set()
        for ledger_key in list(self._boss_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict) or job.get("kind") != "lich_tower":
                continue
            if job.get("bossSpawned") or job.get("bossDefeated"):
                continue
            spawner = job.get("bossSpawner") or {}
            anchor = job.get("anchor") or []
            offset = spawner.get("offset") or []
            if len(anchor) != 3 or len(offset) != 3:
                continue
            marker = (
                float(anchor[0]) + float(offset[0]) + 0.5,
                float(anchor[1]) + float(offset[1]) + 0.5,
                float(anchor[2]) + float(offset[2]) + 0.5,
            )
            radius = float(spawner.get("activationRadius", 9.0))
            minimum_y = marker[1] + float(
                spawner.get("minPlayerYOffset", -1000000.0)
            )
            objective = str(
                spawner.get("progressObjective", "tf_naga_defeated")
            )
            for player in players or []:
                position = player.get("position")
                if (
                    position is None
                    or int(player.get("dimensionId", -1))
                    != self._dimension_id
                    or float(position[1]) <= minimum_y
                    or int(player.get("progress", {}).get(objective, 0)) > 0
                ):
                    continue
                dx = float(position[0]) - marker[0]
                dy = float(position[1]) - marker[1]
                dz = float(position[2]) - marker[2]
                if dx * dx + dy * dy + dz * dz <= radius * radius:
                    blocked.add(player.get("playerId"))
        return list(blocked)

    def mark_boss_missing(self, home, entity_id=None, boss_kind=None):
        """Re-arm a landmark whose boss vanished without a death event."""
        changed = False
        for ledger_key in list(self._boss_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict):
                self._boss_job_keys.discard(ledger_key)
                self._courtyard_job_keys.discard(ledger_key)
                continue
            job_boss_kind = str(job.get("bossKind", ""))
            if not job_boss_kind and str(job.get("kind", "")) == "naga_courtyard":
                # Compatibility with pre-bossKind courtyard ledgers.
                job_boss_kind = "naga"
            if boss_kind is not None and job_boss_kind != str(boss_kind):
                continue
            if job.get("bossDefeated") or not job.get("bossSpawned"):
                continue
            recorded_id = job.get("bossEntityId")
            if (
                entity_id is not None
                and recorded_id is not None
                and str(recorded_id) != str(entity_id)
            ):
                continue
            spawner = job.get("bossSpawner")
            anchor = job.get("anchor")
            if not spawner or not anchor:
                continue
            if home is not None:
                offset = spawner.get("offset", [0, 0, 0])
                spawn_x = float(anchor[0]) + float(offset[0]) + 0.5
                spawn_z = float(anchor[2]) + float(offset[2]) + 0.5
                dx = float(home[0]) - spawn_x
                dz = float(home[2]) - spawn_z
                if dx * dx + dz * dz > 64.0:
                    continue
            job["bossSpawned"] = False
            job.pop("bossEntityId", None)
            job.pop("bossSpawnPendingId", None)
            job.pop("bossSpawnPendingUntil", None)
            changed = True
        if changed:
            self._persist()
        return changed

    def mark_naga_missing(self, home, entity_id=None):
        return self.mark_boss_missing(home, entity_id, "naga")

    def _labyrinth_player(self, job, players):
        if (
            job.get("state") != "complete"
            and not job.get("encounterReady")
        ):
            return None
        bounds = job.get("bounds") or ()
        if len(bounds) != 6:
            return None
        for player in players or ():
            position = player.get("position")
            if (
                position is None
                or int(player.get("dimensionId", -1)) != self._dimension_id
            ):
                continue
            if (
                float(bounds[0]) - 8 <= float(position[0]) <= float(bounds[3]) + 8
                and float(bounds[1]) - 8 <= float(position[1]) <= float(bounds[4]) + 8
                and float(bounds[2]) - 8 <= float(position[2]) <= float(bounds[5]) + 8
            ):
                return player
        return None

    def _count_labyrinth_monsters(self, job, identifiers, local_cap):
        bounds = job.get("bounds") or ()
        if len(bounds) != 6:
            return int(local_cap)
        try:
            entities = self._game.GetEntitiesInSquareArea(
                None,
                (bounds[0], bounds[1], bounds[2]),
                (bounds[3] + 1, bounds[4] + 1, bounds[5] + 1),
                self._dimension_id,
            ) or ()
        except Exception:
            return int(local_cap)
        return sum(
            1
            for entity_id in entities
            if self._entity_identifier(entity_id) in identifiers
        )

    @staticmethod
    def _weighted_spawn_entry(entries, rng):
        total = sum(max(0, int(entry.get("weight", 0))) for entry in entries)
        if total <= 0:
            return None
        roll = rng.next_int(total)
        for entry in entries:
            roll -= max(0, int(entry.get("weight", 0)))
            if roll < 0:
                return entry
        return entries[-1]

    def _spawn_labyrinth_group(self, ledger_key, job, current_tick, players=None):
        contract = job.get("controlledSpawns") or {}
        entries = list(contract.get("weights", ()))
        identifiers = set(str(entry.get("entity")) for entry in entries)
        local_cap = int(contract.get("cap", 18))
        remaining = local_cap - self._count_labyrinth_monsters(
            job, identifiers, local_cap
        )
        if remaining <= 0 or self._entity_spawner is None:
            return 0
        seed = ruin_logic.landmark_stream_seed(
            self._world_seed,
            int((job.get("center") or (0, 0))[0]),
            int((job.get("center") or (0, 0))[1]),
            "labyrinth_spawn",
            int(current_tick) // max(1, int(contract.get("intervalTicks", 100))),
        )
        rng = ruin_logic.JavaRandom(seed)
        entry = self._weighted_spawn_entry(entries, rng)
        if entry is None:
            return 0
        group = entry.get("group", (1, 1))
        requested = int(group[0]) + rng.next_int(max(1, int(group[1]) - int(group[0]) + 1))
        requested = min(remaining, requested)
        zones = list((job.get("markers") or {}).get("spawnZones", ()))
        anchor = job.get("anchor") or (0, 0, 0)
        if not zones:
            zones = [{"center": [55, 8, 55], "radius": 7}]
        spawned = 0
        for index in range(requested):
            zone = zones[rng.next_int(len(zones))]
            center = zone.get("center", (55, 8, 55))
            radius = max(1, int(zone.get("radius", 7)) - 2)
            position = (
                float(anchor[0]) + float(center[0]) + rng.next_int(radius * 2 + 1) - radius + 0.5,
                float(anchor[1]) + float(center[1]),
                float(anchor[2]) + float(center[2]) + rng.next_int(radius * 2 + 1) - radius + 0.5,
            )
            if not self._controlled_spawn_position_allowed(
                job,
                position,
                players or (),
            ):
                continue
            if not self._is_hollow_hill_spawn_position_clear(position):
                continue
            try:
                entity_id = self._entity_spawner(
                    entry.get("entity"),
                    position,
                    float(rng.next_int(360)),
                    self._dimension_id,
                )
            except Exception:
                entity_id = None
            if entity_id:
                spawned += 1
        if spawned:
            self._labyrinth_spawn_groups += 1
            self._labyrinth_spawn_entities += spawned
        return spawned

    def _spawn_labyrinth_monsters(self, current_tick, players):
        if int(current_tick) % 100 != 0:
            return
        for ledger_key in sorted(self._boss_job_keys):
            job = self._ledger.get(ledger_key)
            if (
                not isinstance(job, dict)
                or job.get("kind") != "labyrinth"
                or self._controlled_structure_is_conquered(job)
                or (
                    job.get("state") != "complete"
                    and not job.get("encounterReady")
                )
                or self._labyrinth_player(job, players) is None
            ):
                continue
            if not self._controlled_spawn_attempt_due(
                "labyrinth:%s" % str(ledger_key),
                job,
                current_tick,
            ):
                continue
            self._spawn_labyrinth_group(ledger_key, job, current_tick, players)
            break

    @staticmethod
    def _dark_forest_spawn_choice(seed):
        rng = ruin_logic.JavaRandom(seed)
        total = sum(entry[1] for entry in DARK_FOREST_CONTROLLED_SPAWNS)
        roll = rng.next_int(total)
        selected = DARK_FOREST_CONTROLLED_SPAWNS[-1]
        for entry in DARK_FOREST_CONTROLLED_SPAWNS:
            if roll < int(entry[1]):
                selected = entry
                break
            roll -= int(entry[1])
        minimum = int(selected[2])
        maximum = int(selected[3])
        return {
            "entity": str(selected[0]),
            "count": minimum + rng.next_int(maximum - minimum + 1),
        }

    def _count_dark_forest_monsters(self, player):
        position = player.get("position") or ()
        if len(position) != 3:
            return DARK_FOREST_LOCAL_MONSTER_CAP
        radius = 48.0
        try:
            entities = self._game.GetEntitiesInSquareArea(
                None,
                (
                    float(position[0]) - radius,
                    float(position[1]) - radius,
                    float(position[2]) - radius,
                ),
                (
                    float(position[0]) + radius,
                    float(position[1]) + radius,
                    float(position[2]) + radius,
                ),
                self._dimension_id,
            )
        except Exception:
            entities = None
        if entities is None:
            return DARK_FOREST_LOCAL_MONSTER_CAP
        return sum(
            1
            for entity_id in entities
            if self._entity_identifier(entity_id) in DARK_FOREST_CONTROLLED_MOBS
        )

    def _dark_forest_spawn_candidates(self, player, seed, limit):
        player_position = player.get("position") or ()
        if len(player_position) != 3 or int(limit) <= 0:
            return []
        rng = ruin_logic.JavaRandom(seed)
        center_x = int(math.floor(float(player_position[0])))
        center_y = int(math.floor(float(player_position[1])))
        center_z = int(math.floor(float(player_position[2])))
        result = []
        attempts = max(24, int(limit) * 24)
        for _unused in range(attempts):
            block_x = center_x + rng.next_int(97) - 48
            block_z = center_z + rng.next_int(97) - 48
            if self._biome_name(block_x, block_z) != DARK_FOREST_BIOME:
                continue
            start_y = center_y + rng.next_int(17) - 8
            y_offsets = [0]
            for distance in range(1, 9):
                y_offsets.extend((-distance, distance))
            for offset_y in y_offsets:
                position = (
                    block_x + 0.5,
                    float(start_y + offset_y),
                    block_z + 0.5,
                )
                if not self._is_hollow_hill_spawn_position_clear(position):
                    continue
                result.append((position, float(rng.next_int(360))))
                break
            if len(result) >= int(limit):
                break
        return result

    def _spawn_dark_forest_group(self, player, players, current_tick):
        remaining = (
            DARK_FOREST_LOCAL_MONSTER_CAP
            - self._count_dark_forest_monsters(player)
        )
        if remaining <= 0 or self._entity_spawner is None:
            return 0
        position = player.get("position") or (0, 0, 0)
        seed = ruin_logic.landmark_stream_seed(
            self._world_seed,
            int(math.floor(float(position[0]))),
            int(math.floor(float(position[2]))),
            "dark_forest",
            "controlled_spawn",
            int(current_tick) // DARK_FOREST_SPAWN_INTERVAL_TICKS,
        )
        selected = self._dark_forest_spawn_choice(seed)
        requested = min(int(remaining), int(selected["count"]))
        candidates = self._dark_forest_spawn_candidates(
            player,
            seed ^ 0x4441524B,
            max(12, requested * 12),
        )
        spawned = 0
        for candidate, yaw in candidates:
            if self._biome_name(candidate[0], candidate[2]) != DARK_FOREST_BIOME:
                continue
            if not self._controlled_spawn_position_allowed(
                {},
                candidate,
                players,
            ):
                continue
            if not self._is_hollow_hill_spawn_position_clear(candidate):
                continue
            if not self._chunk_position_ready(*candidate):
                continue
            try:
                entity_id = self._entity_spawner(
                    selected["entity"],
                    candidate,
                    yaw,
                    self._dimension_id,
                )
            except Exception as error:
                print (
                    "[TwilightBossSlice] Dark Forest spawn failed:",
                    selected["entity"],
                    error,
                )
                entity_id = None
            if not entity_id:
                continue
            spawned += 1
            if spawned >= requested:
                break
        if spawned:
            self._dark_forest_spawn_groups += 1
            self._dark_forest_spawn_entities += spawned
        return spawned

    def _spawn_dark_forest_monsters(self, current_tick, players):
        if self._entity_spawner is None:
            return
        if int(current_tick) % DARK_FOREST_SPAWN_INTERVAL_TICKS != 0:
            return
        scanned = 0
        for player in players or ():
            position = player.get("position") or ()
            if (
                int(player.get("dimensionId", -1)) != self._dimension_id
                or len(position) != 3
                or self._biome_name(position[0], position[2])
                != DARK_FOREST_BIOME
            ):
                continue
            scanned += 1
            self._spawn_dark_forest_group(player, players, current_tick)
            if scanned >= MAX_DARK_FOREST_GROUPS_PER_SCAN:
                break

    @staticmethod
    def _controlled_structure_is_conquered(job):
        if str((job or {}).get("kind", "")) == "knight_stronghold":
            return bool((job or {}).get("bossGroupDefeated"))
        return bool((job or {}).get("bossDefeated"))

    @staticmethod
    def _controlled_structure_job_ready(job):
        if not isinstance(job, dict):
            return False
        if str(job.get("state", "")) == "complete":
            return True
        return bool(
            job.get("surfaceGenerated")
            and str(job.get("state", "")) == "surface_pending"
        )

    def _controlled_structure_player(self, job, players):
        if not self._controlled_structure_job_ready(job):
            return None
        bounds = job.get("bounds") or ()
        if len(bounds) != 6:
            return None
        for player in players or ():
            position = player.get("position")
            try:
                in_dimension = (
                    int(player.get("dimensionId", -1)) == self._dimension_id
                )
                inside = (
                    float(bounds[0]) <= float(position[0]) <= float(bounds[3])
                    and float(bounds[1]) <= float(position[1]) <= float(bounds[4])
                    and float(bounds[2]) <= float(position[2]) <= float(bounds[5])
                )
            except (IndexError, TypeError, ValueError):
                continue
            if in_dimension and inside:
                return player
        return None

    def _controlled_spawn_in_boss_area(self, job, position):
        anchor = job.get("anchor") or ()
        if len(anchor) != 3 or position is None or len(position) != 3:
            return False
        markers = job.get("markers") or {}
        kind = str(job.get("kind", ""))

        if kind == "labyrinth":
            for room in markers.get("rooms", ()):
                if not isinstance(room, dict) or room.get("kind") != "minoshroom":
                    continue
                origin = room.get("origin") or ()
                size = room.get("size") or ()
                if len(origin) != 3 or len(size) != 3:
                    continue
                minimum = [
                    float(anchor[index]) + float(origin[index])
                    for index in range(3)
                ]
                maximum = [
                    minimum[index] + float(size[index])
                    for index in range(3)
                ]
                if all(
                    minimum[index]
                    <= float(position[index])
                    <= maximum[index]
                    for index in range(3)
                ):
                    return True

        marker_specs = (
            ("bossRoom", 13.0, 8.0, 8.0),
            ("bossPlatform", 8.0, 4.0, 20.0),
            ("boss", 10.0, 8.0, 8.0),
        )
        for marker_name, default_radius, below, above in marker_specs:
            marker = markers.get(marker_name)
            if not isinstance(marker, dict):
                continue
            offset = marker.get("offset") or ()
            if len(offset) != 3:
                continue
            radius = float(marker.get("radius", default_radius))
            center = [
                float(anchor[index]) + float(offset[index])
                for index in range(3)
            ]
            delta_x = float(position[0]) - center[0]
            delta_y = float(position[1]) - center[1]
            delta_z = float(position[2]) - center[2]
            if (
                delta_x * delta_x + delta_z * delta_z <= radius * radius
                and -below <= delta_y <= above
            ):
                return True

        boss_spawner = job.get("bossSpawner") or {}
        offset = boss_spawner.get("offset") if isinstance(boss_spawner, dict) else None
        if offset and len(offset) == 3:
            radius = max(
                9.0,
                float(boss_spawner.get("activationRadius", 9.0)),
            )
            center = [
                float(anchor[index]) + float(offset[index])
                for index in range(3)
            ]
            delta_x = float(position[0]) - center[0]
            delta_y = abs(float(position[1]) - center[1])
            delta_z = float(position[2]) - center[2]
            if (
                delta_x * delta_x + delta_z * delta_z <= radius * radius
                and delta_y <= 10.0
            ):
                return True
        return False

    def _controlled_spawn_position_allowed(self, job, position, players):
        if self._controlled_spawn_in_boss_area(job, position):
            return False
        has_player = False
        within_activation_range = False
        for player in players or ():
            player_position = player.get("position")
            try:
                if (
                    int(player.get("dimensionId", -1)) != self._dimension_id
                    or len(player_position) != 3
                ):
                    continue
                delta_x = float(position[0]) - float(player_position[0])
                delta_y = float(position[1]) - float(player_position[1])
                delta_z = float(position[2]) - float(player_position[2])
            except (TypeError, ValueError):
                continue
            has_player = True
            distance_squared = (
                delta_x * delta_x + delta_y * delta_y + delta_z * delta_z
            )
            if distance_squared < CONTROLLED_SPAWN_MIN_PLAYER_DISTANCE_SQUARED:
                return False
            if distance_squared <= CONTROLLED_SPAWN_MAX_PLAYER_DISTANCE_SQUARED:
                within_activation_range = True
        return bool(not has_player or within_activation_range)

    @staticmethod
    def _dark_tower_roof_zones(job, player=None):
        markers = job.get("markers") or {}
        anchor = job.get("anchor") or ()
        if len(anchor) != 3:
            return []
        towers = {}
        for tower in list(markers.get("mainTowers", ())) + list(
            markers.get("wingTowers", ())
        ):
            if isinstance(tower, dict) and tower.get("id"):
                towers[str(tower["id"])] = tower
        player_position = (player or {}).get("position") or ()
        result = []
        for roof in markers.get("roofs", ()):
            if not isinstance(roof, dict):
                continue
            offset = roof.get("offset") or ()
            if len(offset) != 3:
                continue
            tower = towers.get(str(roof.get("tower", ""))) or {}
            size = max(5, int(tower.get("size", 9)))
            center = [
                float(anchor[index]) + float(offset[index])
                for index in range(3)
            ]
            if len(player_position) == 3:
                delta_x = center[0] - float(player_position[0])
                delta_y = center[1] - float(player_position[1])
                delta_z = center[2] - float(player_position[2])
                if (
                    delta_x * delta_x + delta_y * delta_y + delta_z * delta_z
                    > CONTROLLED_SPAWN_MAX_PLAYER_DISTANCE_SQUARED
                ):
                    continue
            result.append({"center": center, "size": size})
        return result

    def _controlled_structure_spawn_table(self, job, player):
        contract = job.get("controlledSpawns") or {}
        tiers = contract.get("tiers") or {}
        kind = str(job.get("kind", ""))
        position = player.get("position") or ()
        if kind == "knight_stronghold":
            return "stronghold", list(tiers.get("stronghold", ()))
        if kind != "dark_tower":
            return None, []

        try:
            player_block = self._block_name(
                int(math.floor(float(position[0]))),
                int(math.floor(float(position[1]))),
                int(math.floor(float(position[2]))),
            )
        except (IndexError, TypeError, ValueError):
            return None, []
        if player_block in ("minecraft:water", "minecraft:flowing_water"):
            water = list(tiers.get("water", ()))
            if water:
                return "water", water

        roof_entries = list(tiers.get("roof", ()))
        if roof_entries and self._dark_tower_roof_zones(job, player):
            return "roof", roof_entries
        return "lower", list(tiers.get("lower", ()))

    @staticmethod
    def _controlled_structure_identifiers(entries, kind):
        identifiers = set(
            str(entry.get("entity"))
            for entry in entries
            if isinstance(entry, dict) and entry.get("entity")
        )
        if str(kind) == "knight_stronghold":
            # A naturally spawned lower knight creates its upper rider. Both
            # count against the source monster population budget.
            identifiers.add("tf_slice:upper_goblin_knight")
        return identifiers

    def _count_controlled_structure_monsters(
        self,
        job,
        _player,
        identifiers,
        local_cap,
    ):
        bounds = job.get("bounds") or ()
        if len(bounds) != 6:
            return int(local_cap)
        minimum = (bounds[0], bounds[1], bounds[2])
        maximum = (
            bounds[3] + 1,
            bounds[4] + 1,
            bounds[5] + 1,
        )
        try:
            entities = self._game.GetEntitiesInSquareArea(
                None,
                minimum,
                maximum,
                self._dimension_id,
            )
        except Exception:
            entities = None
        if entities is None:
            return int(local_cap)
        return sum(
            1
            for entity_id in entities
            if self._entity_identifier(entity_id) in identifiers
        )

    def _controlled_structure_spawn_position_clear(self, identifier, position):
        block_x = int(math.floor(float(position[0])))
        block_y = int(math.floor(float(position[1])))
        block_z = int(math.floor(float(position[2])))
        if identifier in CONTROLLED_STRUCTURE_WATER_MOBS:
            return self._block_name(block_x, block_y, block_z) in (
                "minecraft:water",
                "minecraft:flowing_water",
            )
        clearance = 3 if identifier in CONTROLLED_STRUCTURE_TALL_MOBS else 2
        for offset_y in range(clearance):
            if self._block_name(block_x, block_y + offset_y, block_z) not in (
                HOLLOW_HILL_SPAWN_AIR_BLOCKS
            ):
                return False
        if identifier in CONTROLLED_STRUCTURE_FLYING_MOBS:
            return True
        return self._block_name(block_x, block_y - 1, block_z) not in (
            HOLLOW_HILL_SPAWN_AIR_BLOCKS
        )

    def _dark_tower_roof_spawn_candidates(
        self,
        job,
        player,
        seed,
        limit,
    ):
        zones = self._dark_tower_roof_zones(job, player)
        if not zones or int(limit) <= 0:
            return []
        rng = ruin_logic.JavaRandom(seed)
        result = []
        attempts = max(16, int(limit) * 16)
        for _unused in range(attempts):
            zone = zones[rng.next_int(len(zones))]
            center = zone["center"]
            radius = max(1, (int(zone["size"]) - 3) // 2)
            block_x = int(math.floor(center[0])) + rng.next_int(
                radius * 2 + 1
            ) - radius
            block_y = int(math.floor(center[1])) + 1 + rng.next_int(8)
            block_z = int(math.floor(center[2])) + rng.next_int(
                radius * 2 + 1
            ) - radius
            position = (block_x + 0.5, float(block_y), block_z + 0.5)
            if not self._controlled_structure_spawn_position_clear(
                "tf_slice:tower_ghast",
                position,
            ):
                continue
            result.append((position, float(rng.next_int(360))))
            if len(result) >= int(limit):
                break
        return result

    def _controlled_structure_spawn_candidates(
        self,
        job,
        player,
        identifier,
        seed,
        limit,
    ):
        bounds = job.get("bounds") or ()
        player_position = player.get("position") or ()
        if len(bounds) != 6 or len(player_position) != 3 or int(limit) <= 0:
            return []
        if identifier == "tf_slice:tower_ghast":
            return self._dark_tower_roof_spawn_candidates(
                job,
                player,
                seed,
                limit,
            )
        rng = ruin_logic.JavaRandom(seed)
        radius = 48
        minimum_x = max(
            int(math.floor(float(bounds[0]))),
            int(math.floor(float(player_position[0]))) - radius,
        )
        maximum_x = min(
            int(math.floor(float(bounds[3]))),
            int(math.floor(float(player_position[0]))) + radius,
        )
        minimum_z = max(
            int(math.floor(float(bounds[2]))),
            int(math.floor(float(player_position[2]))) - radius,
        )
        maximum_z = min(
            int(math.floor(float(bounds[5]))),
            int(math.floor(float(player_position[2]))) + radius,
        )
        minimum_y = max(
            int(math.floor(float(bounds[1]))),
            int(math.floor(float(player_position[1]))) - 8,
        )
        maximum_y = min(
            int(math.floor(float(bounds[4]))),
            int(math.floor(float(player_position[1]))) + 8,
        )
        if minimum_x > maximum_x or minimum_y > maximum_y or minimum_z > maximum_z:
            return []
        result = []
        attempts = max(16, int(limit) * 16)
        for _unused in range(attempts):
            block_x = minimum_x + rng.next_int(maximum_x - minimum_x + 1)
            block_z = minimum_z + rng.next_int(maximum_z - minimum_z + 1)
            delta_x = block_x + 0.5 - float(player_position[0])
            delta_z = block_z + 0.5 - float(player_position[2])
            start_y = minimum_y + rng.next_int(maximum_y - minimum_y + 1)
            y_offsets = [0]
            for distance in range(1, 9):
                y_offsets.extend((-distance, distance))
            for offset_y in y_offsets:
                block_y = start_y + offset_y
                if block_y < minimum_y or block_y > maximum_y:
                    continue
                position = (block_x + 0.5, float(block_y), block_z + 0.5)
                if not self._controlled_structure_spawn_position_clear(
                    identifier,
                    position,
                ):
                    continue
                result.append((position, float(rng.next_int(360))))
                break
            if len(result) >= int(limit):
                break
        return result

    def _spawn_controlled_structure_group(
        self,
        _ledger_key,
        job,
        player,
        current_tick,
        players=None,
    ):
        tier, entries = self._controlled_structure_spawn_table(job, player)
        if not entries or self._entity_spawner is None:
            return 0
        kind = str(job.get("kind", ""))
        contract = job.get("controlledSpawns") or {}
        local_cap = int(
            contract.get(
                "cap",
                CONTROLLED_STRUCTURE_CAPS.get(tier, 18),
            )
        )
        identifiers = self._controlled_structure_identifiers(entries, kind)
        remaining = local_cap - self._count_controlled_structure_monsters(
            job,
            player,
            identifiers,
            local_cap,
        )
        if remaining <= 0:
            return 0
        center = job.get("center") or (0, 0)
        seed = ruin_logic.landmark_stream_seed(
            self._world_seed,
            int(center[0]),
            int(center[1]),
            kind,
            "controlled_spawn_%s" % str(tier),
            int(current_tick) // CONTROLLED_STRUCTURE_SPAWN_INTERVAL_TICKS,
        )
        rng = ruin_logic.JavaRandom(seed)
        selected = self._weighted_spawn_entry(entries, rng)
        if selected is None:
            return 0
        group = selected.get("group", (1, 1))
        minimum_group = max(1, int(group[0]))
        maximum_group = max(minimum_group, int(group[1]))
        requested = minimum_group + rng.next_int(
            maximum_group - minimum_group + 1
        )
        requested = min(int(remaining), requested)
        identifier = str(selected.get("entity", ""))
        candidates = self._controlled_structure_spawn_candidates(
            job,
            player,
            identifier,
            seed ^ 0x535041574E,
            max(12, requested * 12),
        )
        spawned = 0
        for position, yaw in candidates:
            if not self._controlled_spawn_position_allowed(
                job,
                position,
                players if players is not None else (player,),
            ):
                continue
            if not self._chunk_position_ready(*position):
                continue
            try:
                entity_id = self._entity_spawner(
                    identifier,
                    position,
                    yaw,
                    self._dimension_id,
                )
            except Exception as error:
                print (
                    "[TwilightBossSlice] structure controlled spawn failed:",
                    kind,
                    identifier,
                    error,
                )
                entity_id = None
            if not entity_id:
                continue
            spawned += 1
            if spawned >= requested:
                break
        if spawned:
            self._controlled_structure_spawn_groups += 1
            self._controlled_structure_spawn_entities += spawned
            self._controlled_structure_spawn_groups_by_kind[kind] = (
                self._controlled_structure_spawn_groups_by_kind.get(kind, 0)
                + 1
            )
            self._controlled_structure_spawn_entities_by_kind[kind] = (
                self._controlled_structure_spawn_entities_by_kind.get(kind, 0)
                + spawned
            )
        return spawned

    def _spawn_controlled_structure_monsters(self, current_tick, players):
        if self._entity_spawner is None:
            return
        if int(current_tick) % CONTROLLED_STRUCTURE_SPAWN_INTERVAL_TICKS != 0:
            return
        active_structures = 0
        for ledger_key in sorted(self._ledger):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict) or str(job.get("kind", "")) not in (
                "knight_stronghold",
                "dark_tower",
            ):
                continue
            if self._controlled_structure_is_conquered(job):
                continue
            player = self._controlled_structure_player(job, players)
            if player is None:
                continue
            if not self._controlled_spawn_attempt_due(
                "controlled_structure:%s" % str(ledger_key),
                job,
                current_tick,
            ):
                continue
            active_structures += 1
            self._spawn_controlled_structure_group(
                ledger_key,
                job,
                player,
                current_tick,
                players,
            )
            if active_structures >= MAX_CONTROLLED_STRUCTURE_GROUPS_PER_SCAN:
                break

    @staticmethod
    def _knight_group_marker_position(job):
        marker = (job.get("markers") or {}).get("bossGroupSpawner") or {}
        offset = marker.get("offset") if isinstance(marker, dict) else None
        anchor = job.get("anchor")
        if not offset or not anchor or len(offset) != 3 or len(anchor) != 3:
            return None
        return tuple(
            int(anchor[index]) + int(offset[index])
            for index in range(3)
        )

    def _knight_group_players(self, job, players):
        home = self._knight_group_marker_position(job)
        if home is None:
            return []
        radius = int((job.get("bossGroupSpawner") or {}).get("homeRadius", 30))
        result = []
        for player in players:
            if int(player.get("dimensionId", -1)) != self._dimension_id:
                continue
            position = player.get("position")
            if not position:
                continue
            dx = float(position[0]) - float(home[0])
            dy = float(position[1]) - float(home[1])
            dz = float(position[2]) - float(home[2])
            if dx * dx + dy * dy + dz * dz <= radius * radius:
                result.append(player)
        return result

    def _write_knight_member_identity(self, entity_id, ledger_key, slot):
        try:
            extra = self._factory.CreateExtraData(entity_id)
            return bool(
                extra.SetExtraData(
                    "tf_slice:knight_group_member_v1",
                    {
                        "ledgerKey": str(ledger_key),
                        "slot": int(slot),
                        "number": int(slot),
                    },
                    False,
                )
            )
        except Exception as error:
            print "[TwilightBossSlice] Knight member identity write failed:", error
            return False

    def _activate_knight_groups(self, players, current_tick):
        if self._boss_spawner is None:
            return
        changed = False
        for ledger_key in sorted(self._knight_group_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict):
                continue
            template_committed = bool(
                job.get("state") == "complete"
                and job.get("finalCommit")
            )
            surface_encounter_committed = bool(
                job.get("surfaceGenerated")
                and job.get("encounterReady")
            )
            if (
                not (template_committed or surface_encounter_committed)
                or job.get("bossGroupDefeated")
            ):
                continue
            near_players = self._knight_group_players(job, players)
            if not near_players and not job.get("bossGroupSpawned"):
                continue
            home = self._knight_group_marker_position(job)
            if home is None:
                continue
            if (
                not job.get("bossGroupSpawned")
                and self._block_name(*home) != KNIGHT_PHANTOM_SPAWNER_BLOCK
            ):
                continue
            group = job.get("bossGroupState")
            if not isinstance(group, dict):
                group = knight_route_logic.create_group_state(
                    ledger_key,
                    home,
                    (job.get("bossGroupSpawner") or {}).get(
                        "memberNumbers", range(6)
                    ),
                )
                job["bossGroupState"] = group
                changed = True
            else:
                try:
                    group = knight_route_logic.load_group_state(group)
                except ValueError:
                    job["state"] = "failed"
                    job["reason"] = "invalid_knight_group_state"
                    changed = True
                    continue
                job["bossGroupState"] = group
            for player in near_players:
                knight_route_logic.record_participant(
                    group, player.get("playerId")
                )
            death_slots = set(group.get("deathSlots", ()))
            for member in group.get("members", ()):
                number = int(member.get("number", -1))
                slot = int(member.get("slot", number))
                if slot in death_slots or member.get("entityId"):
                    continue
                spawn_position = knight_route_logic.ring_position(home, number)
                try:
                    entity_id = self._boss_spawner(
                        "tf_slice:knight_phantom",
                        spawn_position,
                        float(number * 60),
                        self._dimension_id,
                    )
                except Exception as error:
                    print "[TwilightBossSlice] Knight group spawn failed:", error
                    entity_id = None
                if not entity_id:
                    continue
                member["entityId"] = str(entity_id)
                self._write_knight_member_identity(entity_id, ledger_key, slot)
                changed = True
            alive_members = [
                member for member in group.get("members", ())
                if int(member.get("slot", member.get("number", -1)))
                not in death_slots
            ]
            complete_group = bool(alive_members) and all(
                member.get("entityId") for member in alive_members
            )
            if complete_group and not job.get("bossGroupSpawned"):
                job["bossGroupSpawned"] = True
                marker = self._knight_group_marker_position(job)
                if marker is not None:
                    self._remove_courtyard_marker_at(marker)
                changed = True
            if job.get("bossGroupSpawned") and not group.get("defeated"):
                knight_route_logic.advance_formation(group, 1)
                if int(current_tick) % 20 == 0:
                    changed = True
        if changed:
            self._persist()

    def _reset_knight_groups_for_peaceful(self):
        changed = False
        for ledger_key in list(self._knight_group_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict) or job.get("bossGroupDefeated"):
                continue
            group = job.get("bossGroupState")
            if not isinstance(group, dict):
                continue
            job["bossGroupState"] = knight_route_logic.reset_for_peaceful(group)
            job["bossGroupSpawned"] = False
            marker = self._knight_group_marker_position(job)
            if marker is not None:
                try:
                    self._block.SetBlockNew(
                        marker,
                        {"name": KNIGHT_PHANTOM_SPAWNER_BLOCK, "aux": 0},
                        0,
                        self._dimension_id,
                        True,
                        False,
                    )
                except Exception:
                    pass
            changed = True
        if changed:
            self._persist()

    def bind_knight_member(self, entity_id):
        try:
            identity = self._factory.CreateExtraData(entity_id).GetExtraData(
                "tf_slice:knight_group_member_v1"
            )
        except Exception:
            identity = None
        if not isinstance(identity, dict):
            return None
        ledger_key = str(identity.get("ledgerKey", ""))
        slot = int(identity.get("slot", identity.get("number", -1)))
        job = self._ledger.get(ledger_key)
        group = job.get("bossGroupState") if isinstance(job, dict) else None
        if not isinstance(group, dict) or slot in group.get("deathSlots", ()):
            return None
        for member in group.get("members", ()):
            member_slot = int(member.get("slot", member.get("number", -1)))
            if member_slot == slot:
                member["entityId"] = str(entity_id)
                return {
                    "ledgerKey": ledger_key,
                    "slot": slot,
                    "number": int(member.get("number", 0)),
                }
        return None

    def active_knight_groups(self):
        """Expose live persisted encounter state to the server AI driver.

        The returned group mappings are the ledger-owned values. The server may
        refresh member health, while formation advancement and checkpointing
        remain owned by this service so there is still one persistence writer.
        """
        active = []
        for ledger_key in sorted(self._knight_group_job_keys):
            job = self._ledger.get(ledger_key)
            group = job.get("bossGroupState") if isinstance(job, dict) else None
            if (
                isinstance(group, dict)
                and job.get("bossGroupSpawned")
                and not job.get("bossGroupDefeated")
                and not group.get("defeated")
            ):
                active.append(group)
        return active

    def knight_member_context(self, entity_id):
        entity_key = str(entity_id)
        for group in self.active_knight_groups():
            for member in group.get("members", ()):
                if str(member.get("entityId")) == entity_key:
                    return {"group": group, "member": member}
        return None

    def record_knight_member_death(self, entity_id, killer_id=None):
        entity_key = str(entity_id)
        for ledger_key in list(self._knight_group_job_keys):
            job = self._ledger.get(ledger_key)
            group = job.get("bossGroupState") if isinstance(job, dict) else None
            if not isinstance(group, dict):
                continue
            for member in group.get("members", ()):
                if str(member.get("entityId")) != entity_key:
                    continue
                if killer_id is not None:
                    knight_route_logic.record_participant(group, killer_id)
                final = knight_route_logic.record_member_death(
                    group, member.get("slot", member.get("number"))
                )
                if final:
                    job["bossGroupDefeated"] = True
                self._persist()
                return {
                    "handled": True,
                    "final": final,
                    "home": list(group.get("home", ())),
                    "participants": list(group.get("participants", ())),
                }
        return {"handled": False, "final": False}

    def claim_knight_group_reward(self, home):
        if home is None:
            return False
        for ledger_key in list(self._knight_group_job_keys):
            job = self._ledger.get(ledger_key)
            group = job.get("bossGroupState") if isinstance(job, dict) else None
            if not isinstance(group, dict) or not job.get("bossGroupDefeated"):
                continue
            group_home = group.get("home") or ()
            if len(group_home) != 3:
                continue
            dx = float(home[0]) - float(group_home[0])
            dz = float(home[2]) - float(group_home[2])
            if dx * dx + dz * dz > 64.0:
                continue
            if not knight_route_logic.claim_reward(group):
                return False
            if not self._persist():
                group["rewardClaimed"] = False
                group["rewardChestPlaced"] = False
                return False
            job["rewardClaimed"] = True
            return True
        return False

    def activate_trophy_pedestal(self, position):
        """Atomically open only the shield wall owned by one Stronghold."""
        if position is None or len(position) != 3:
            return False
        target = tuple(int(value) for value in position)
        for ledger_key in list(self._knight_group_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict) or job.get("kind") != "knight_stronghold":
                continue
            markers = job.get("markers") or {}
            pedestal = markers.get("trophyPedestal") or {}
            offset = pedestal.get("offset") if isinstance(pedestal, dict) else None
            anchor = job.get("anchor") or ()
            if not offset or len(anchor) != 3:
                continue
            world_pedestal = tuple(
                int(anchor[index]) + int(offset[index])
                for index in range(3)
            )
            if world_pedestal != target:
                continue
            if job.get("trophyPedestalActivated"):
                return False
            removed = 0
            for shield_offset in markers.get("shieldWalls", ()):
                if not isinstance(shield_offset, (list, tuple)) or len(shield_offset) != 3:
                    continue
                shield_position = tuple(
                    int(anchor[index]) + int(shield_offset[index])
                    for index in range(3)
                )
                if self._block_name(*shield_position) != "tf_slice:stronghold_shield":
                    continue
                try:
                    result = self._block.SetBlockNew(
                        shield_position,
                        {"name": "minecraft:air", "aux": 0},
                        0,
                        self._dimension_id,
                        True,
                        False,
                    )
                except Exception:
                    result = False
                if result is not False:
                    removed += 1
            if removed <= 0:
                return False
            active_visual = False
            if self._block_state is not None:
                try:
                    states = self._block_state.GetBlockStates(
                        target,
                        self._dimension_id,
                    ) or {}
                    states["tf_slice:active"] = True
                    active_visual = self._block_state.SetBlockStates(
                        target,
                        states,
                        self._dimension_id,
                    ) is not False
                except Exception:
                    active_visual = False
            if not active_visual:
                # Older ModSDK builds may not expose BlockState.  Replacing
                # the same block with an explicit state is the compatible
                # fallback; opening the shield remains the authoritative act.
                try:
                    active_visual = self._block.SetBlockNew(
                        target,
                        {
                            "name": "tf_slice:trophy_pedestal",
                            "aux": 0,
                            "states": {"tf_slice:active": True},
                        },
                        0,
                        self._dimension_id,
                        True,
                        False,
                    ) is not False
                except Exception:
                    active_visual = False
            job["trophyPedestalActivated"] = True
            job["trophyPedestalActiveVisual"] = bool(active_visual)
            job["shieldWallsRemoved"] = removed
            return bool(self._persist())
        return False

    def ur_ghast_context(self, position):
        """Return the persisted tower/trap context nearest one spawned boss."""
        if position is None or len(position) != 3:
            return None
        nearest = None
        nearest_distance = None
        for ledger_key in list(self._boss_job_keys):
            job = self._ledger.get(ledger_key)
            if not isinstance(job, dict) or job.get("kind") != "dark_tower":
                continue
            spawner = job.get("bossSpawner") or {}
            anchor = job.get("anchor") or ()
            offset = spawner.get("offset") or ()
            if len(anchor) != 3 or len(offset) != 3:
                continue
            home = [
                float(anchor[index]) + float(offset[index]) + 0.5
                for index in range(3)
            ]
            dx = float(position[0]) - home[0]
            dy = float(position[1]) - home[1]
            dz = float(position[2]) - home[2]
            distance = dx * dx + dy * dy + dz * dz
            if distance > 256.0 or (
                nearest_distance is not None and distance >= nearest_distance
            ):
                continue
            traps = []
            for marker in (job.get("markers") or {}).get("ghastTraps", ()):
                marker_offset = marker.get("offset") if isinstance(marker, dict) else None
                if marker_offset and len(marker_offset) == 3:
                    traps.append(
                        [
                            float(anchor[index]) + float(marker_offset[index])
                            for index in range(3)
                        ]
                    )
            nearest = {
                "ledgerKey": str(ledger_key),
                "home": home,
                "trapPoints": traps,
                "structureBounds": list(job.get("bounds", ())),
            }
            nearest_distance = distance
        return nearest

    def _dark_tower_canopy_cleanup_contract(self, job):
        contract = job.get("canopyCleanup")
        if isinstance(contract, dict):
            return contract
        entry = self._entry_for_landmark("dark_tower")
        if not isinstance(entry, dict):
            return None
        try:
            variant_index = int(job.get("variant", -1))
        except (TypeError, ValueError):
            return None
        variants = entry.get("variants", ())
        if not (0 <= variant_index < len(variants)):
            return None
        contract = variants[variant_index].get("canopyCleanup")
        if not isinstance(contract, dict):
            return None
        job["canopyCleanup"] = copy.deepcopy(contract)
        return job["canopyCleanup"]

    def _dark_tower_canopy_chunks_ready(self, job):
        checker = getattr(self._chunk, "CheckChunkState", None)
        if checker is None:
            return True
        bounds = job.get("bounds")
        anchor = job.get("anchor")
        if not bounds or len(bounds) != 6 or not anchor or len(anchor) != 3:
            return False
        minimum_x = int(bounds[0]) - DARK_TOWER_CANOPY_CLEANUP_CHUNK_MARGIN
        maximum_x = int(bounds[3]) + DARK_TOWER_CANOPY_CLEANUP_CHUNK_MARGIN
        minimum_z = int(bounds[2]) - DARK_TOWER_CANOPY_CLEANUP_CHUNK_MARGIN
        maximum_z = int(bounds[5]) + DARK_TOWER_CANOPY_CLEANUP_CHUNK_MARGIN
        check_y = int(anchor[1])
        for chunk_x in range(minimum_x >> 4, (maximum_x >> 4) + 1):
            for chunk_z in range(minimum_z >> 4, (maximum_z >> 4) + 1):
                position = (chunk_x * 16 + 8, check_y, chunk_z * 16 + 8)
                try:
                    if not checker(self._dimension_id, position):
                        return False
                except Exception:
                    return False
        return True

    @staticmethod
    def _dark_tower_cleanup_run(run):
        if not isinstance(run, (tuple, list)) or len(run) != 4:
            return None
        try:
            x, z, minimum_y, maximum_y = [int(value) for value in run]
        except (TypeError, ValueError):
            return None
        if minimum_y > maximum_y:
            return None
        return x, z, minimum_y, maximum_y

    def _advance_dark_tower_canopy_cleanup(self, current_tick, players):
        candidates = []
        for ledger_key, job in self._ledger.items():
            if not isinstance(job, dict) or job.get("kind") != "dark_tower":
                continue
            if job.get("state") != "complete":
                continue
            state = job.get("canopyCleanupState")
            if isinstance(state, dict) and state.get("complete"):
                continue
            contract = self._dark_tower_canopy_cleanup_contract(job)
            if (
                not isinstance(contract, dict)
                or int(contract.get("schemaVersion", 0)) != 1
                or not isinstance(contract.get("runs"), list)
            ):
                continue
            distance = self._job_player_distance_squared(job, players)
            if (
                distance is None
                or distance
                > AUTOMATIC_JOB_PLAYER_RADIUS * AUTOMATIC_JOB_PLAYER_RADIUS
            ):
                continue
            candidates.append((distance, str(ledger_key), job, contract))
        if not candidates:
            return False
        _distance, _ledger_key, job, contract = sorted(candidates)[0]
        state = job.get("canopyCleanupState")
        if (
            not isinstance(state, dict)
            or int(state.get("policyVersion", 0))
            != DARK_TOWER_CANOPY_CLEANUP_POLICY_VERSION
        ):
            settle_ticks = max(
                1,
                int(
                    contract.get(
                        "settleTicks",
                        DARK_TOWER_CANOPY_CLEANUP_DEFAULT_SETTLE_TICKS,
                    )
                ),
            )
            state = {
                "policyVersion": DARK_TOWER_CANOPY_CLEANUP_POLICY_VERSION,
                "complete": False,
                "runIndex": 0,
                "nextY": None,
                "checked": 0,
                "removed": 0,
                "notBeforeTick": max(
                    int(current_tick) + settle_ticks,
                    int(job.get("surfaceLastSeenTick", 0)) + settle_ticks,
                ),
                "nextChunkCheckTick": int(current_tick),
                "persistedChecked": 0,
            }
            job["canopyCleanupState"] = state
        if int(current_tick) < int(state.get("notBeforeTick", 0)):
            return False
        if int(current_tick) < int(state.get("nextChunkCheckTick", 0)):
            return False
        if not self._dark_tower_canopy_chunks_ready(job):
            state["nextChunkCheckTick"] = int(current_tick) + 20
            return False

        runs = contract.get("runs", ())
        anchor = job.get("anchor") or ()
        if len(anchor) != 3:
            return False
        allowed = set(contract.get("leafBlocks", ()))
        allowed.intersection_update(DARK_TOWER_CANOPY_LEAF_BLOCKS)
        if not allowed:
            allowed = set(DARK_TOWER_CANOPY_LEAF_BLOCKS)
        budget = max(
            1,
            min(
                256,
                int(
                    contract.get(
                        "scanBudgetPerTick",
                        DARK_TOWER_CANOPY_CLEANUP_DEFAULT_BUDGET,
                    )
                ),
            ),
        )
        checked_this_tick = 0
        while checked_this_tick < budget:
            run_index = int(state.get("runIndex", 0))
            if run_index >= len(runs):
                state["complete"] = True
                state["completedTick"] = int(current_tick)
                self._dark_tower_canopy_jobs_completed += 1
                self._persist()
                return True
            run = self._dark_tower_cleanup_run(runs[run_index])
            if run is None:
                state["runIndex"] = run_index + 1
                state["nextY"] = None
                continue
            local_x, local_z, minimum_y, maximum_y = run
            next_y = state.get("nextY")
            y = minimum_y if next_y is None else int(next_y)
            position = (
                int(anchor[0]) + local_x,
                int(anchor[1]) + y,
                int(anchor[2]) + local_z,
            )
            try:
                current = self._block.GetBlockNew(
                    position,
                    self._dimension_id,
                )
            except Exception:
                state["nextChunkCheckTick"] = int(current_tick) + 20
                return False
            current_name = (
                str(current.get("name", ""))
                if isinstance(current, dict)
                else ""
            )
            if current_name in allowed:
                try:
                    self._block.SetBlockNew(
                        position,
                        {"name": "minecraft:air", "aux": 0},
                        0,
                        self._dimension_id,
                        True,
                        False,
                    )
                    after = self._block.GetBlockNew(
                        position,
                        self._dimension_id,
                    )
                    if (
                        isinstance(after, dict)
                        and str(after.get("name", ""))
                        in ("minecraft:air", "minecraft:cave_air")
                    ):
                        state["removed"] = int(state.get("removed", 0)) + 1
                        self._dark_tower_canopy_leaves_removed += 1
                except Exception:
                    state["nextChunkCheckTick"] = int(current_tick) + 20
                    return False
            checked_this_tick += 1
            state["checked"] = int(state.get("checked", 0)) + 1
            self._dark_tower_canopy_blocks_checked += 1
            if y >= maximum_y:
                state["runIndex"] = run_index + 1
                state["nextY"] = None
            else:
                state["nextY"] = y + 1

        if (
            int(state.get("checked", 0))
            - int(state.get("persistedChecked", 0))
            >= DARK_TOWER_CANOPY_CLEANUP_CHECKPOINT_BLOCKS
        ):
            state["persistedChecked"] = int(state.get("checked", 0))
            self._persist()
        return False

    def tick(self, current_tick, players, boss_spawning_enabled=True):
        self._current_tick = int(current_tick)
        self._drain_surface_landmark_handoffs()
        self._drain_native_structure_handoffs()
        self._advance_one_job(current_tick, players)
        self._advance_dark_tower_canopy_cleanup(current_tick, players)
        if boss_spawning_enabled:
            self._activate_courtyard_bosses(players, current_tick)
            self._activate_knight_groups(players, current_tick)
            self._spawn_dark_forest_monsters(current_tick, players)
        else:
            self._reset_knight_groups_for_peaceful()
        self._spawn_hollow_hill_monsters(current_tick, players)
        self._spawn_lich_tower_monsters(current_tick, players)
        self._spawn_labyrinth_monsters(current_tick, players)
        self._spawn_controlled_structure_monsters(current_tick, players)

    def debug_list(self):
        return sorted(self._catalog)

    def debug_status(self):
        counts = {}
        active_carves = []
        failed_jobs = []
        for job in self._ledger.values():
            state = str(job.get("state", "unknown"))
            counts[state] = counts.get(state, 0) + 1
            if state == "failed":
                terrain = job.get("terrain") or {}
                failed_jobs.append(
                    "%s@%s:r%d:p%d:t%d/%s"
                    % (
                        str(job.get("kind", "")),
                        ",".join(
                            str(value)
                            for value in job.get("center", ["?", "?"])[:2]
                        ),
                        int(job.get("retries", 0)),
                        int(job.get("nextPiece", 0)),
                        int(terrain.get("nextColumn", 0)),
                        (
                            int(terrain.get("width", 0))
                            * int(terrain.get("depth", 0))
                        ),
                    )
                )
            if (
                str(job.get("kind", ""))
                in ruin_logic.HOLLOW_HILL_KIND_DATA
                and not job.get("hollowHillCarveComplete")
                and state in ("planned", "placing")
            ):
                carve = job.get("hollowHillCarve") or {}
                active_carves.append(
                    "%s:%s:%d"
                    % (
                        str(job.get("kind", "")),
                        state,
                        int(carve.get("blocksCleared", 0)),
                    )
                )
        return {
            "seed": self._world_seed,
            "ledger": counts,
            "manualQueued": len(self._manual_jobs),
            "nativeHandoffs": len(self._native_structure_handoffs),
            "nativeHandoffsDropped": self._dropped_native_handoffs,
            "surfaceLandmarkHandoffs": len(
                self._surface_landmark_handoffs
            ),
            "surfaceLandmarkHandoffsDropped": (
                self._dropped_surface_landmark_handoffs
            ),
            "surfaceLandmarkTilesAccepted": (
                self._accepted_surface_landmark_tiles
            ),
            "landmarkTriggers": len(self._landmark_chunk_handoffs),
            "landmarkTriggersDropped": self._dropped_landmark_triggers,
            "landmarkDiscoveryFailures": (
                self._failed_landmark_discoveries
            ),
            "ledgerPersistFailures": self._ledger_persist_failures,
            "lastLedgerPersistError": self._last_ledger_persist_error,
            "chunkGenerationEvents": (
                self._accepted_chunk_generation_events
            ),
            "chunkLoadBackfillEvents": self._accepted_chunk_load_events,
            "playerProximityBackfillEvents": (
                self._accepted_player_backfills
            ),
            "structureTriggerEvents": self._accepted_structure_triggers,
            "nativeCollisionsRejected": self._rejected_native_collisions,
            "activeAreas": len(self._areas),
            "hollowHillSpawnGroups": self._hill_spawn_groups,
            "hollowHillSpawnEntities": self._hill_spawn_entities,
            "hollowHillSpawnQueryFailures": (
                self._hill_spawn_query_failures
            ),
            "labyrinthSpawnGroups": self._labyrinth_spawn_groups,
            "labyrinthSpawnEntities": self._labyrinth_spawn_entities,
            "controlledStructureSpawnGroups": (
                self._controlled_structure_spawn_groups
            ),
            "controlledStructureSpawnEntities": (
                self._controlled_structure_spawn_entities
            ),
            "controlledStructureSpawnGroupsByKind": dict(
                self._controlled_structure_spawn_groups_by_kind
            ),
            "controlledStructureSpawnEntitiesByKind": dict(
                self._controlled_structure_spawn_entities_by_kind
            ),
            "darkForestSpawnGroups": self._dark_forest_spawn_groups,
            "darkForestSpawnEntities": self._dark_forest_spawn_entities,
            "structureChunkReadyWaits": self._chunk_ready_waits,
            "hollowHillCarvesStarted": self._hill_carves_started,
            "hollowHillCarvesCompleted": self._hill_carves_completed,
            "hollowHillCarveBlocks": self._hill_carve_blocks,
            "hollowHillCarveActive": active_carves[:3],
            "failedJobs": failed_jobs[:3],
        }

    def debug_near(self, position, radius_blocks=256):
        try:
            position = [
                int(position[0]),
                int(position[1]),
                int(position[2]),
            ]
            radius_blocks = max(1, min(1024, int(radius_blocks)))
        except (IndexError, TypeError, ValueError):
            return []
        nearby = []
        for key, job in self._ledger.items():
            if not isinstance(job, dict):
                continue
            located = self._job_locate_position(job)
            if located is None:
                continue
            distance_squared = self._horizontal_distance_squared(
                position,
                located,
            )
            if distance_squared > radius_blocks * radius_blocks:
                continue
            terrain = job.get("terrain") or {}
            nearby.append(
                (
                    distance_squared,
                    "%s=%s/%s/%s:r%d:p%d:t%d"
                    % (
                        str(key),
                        str(job.get("entryId", "")),
                        str(job.get("kind", "")),
                        str(job.get("state", "")),
                        int(job.get("retries", 0)),
                        int(job.get("nextPiece", 0)),
                        int(terrain.get("nextColumn", 0)),
                    ),
                )
            )
        nearby.sort(key=lambda item: (item[0], item[1]))
        return [item[1] for item in nearby[:5]]

    def debug_grid(self, position):
        try:
            block_x = int(position[0])
            block_z = int(position[2])
        except (IndexError, TypeError, ValueError):
            return "invalid position"
        center_x, center_z = ruin_logic.nearest_landmark_center(
            block_x >> 4,
            block_z >> 4,
        )
        ledger_key = "%d,%d" % (center_x, center_z)
        recorded = self._ledger.get(ledger_key)
        raw_kind = ruin_logic.resolve_variety_landmark(
            int(center_x) >> 4,
            int(center_z) >> 4,
            self._world_seed,
            SUPPORTED_VARIETY,
        )
        biome_name = self._landmark_biome_name(center_x, center_z)
        resolved_kind = (
            self._landmark_kind_at_center(
                biome_name,
                center_x,
                center_z,
            )
            if biome_name is not None
            else None
        )
        if isinstance(recorded, dict):
            recorded_detail = "%s/%s/%s"
            recorded_detail %= (
                str(recorded.get("entryId", "")),
                str(recorded.get("kind", "")),
                str(recorded.get("state", "")),
            )
        else:
            recorded_detail = repr(recorded)
        return (
            "pos=%d,%d center=%d,%d raw=%s biome=%s resolved=%s "
            "record=%s"
            % (
                block_x,
                block_z,
                center_x,
                center_z,
                raw_kind,
                biome_name,
                resolved_kind,
                recorded_detail,
            )
        )

    @staticmethod
    def _job_entry_id(job):
        entry_id = job.get("entryId")
        if entry_id:
            return str(entry_id)
        kind = str(job.get("kind", ""))
        if kind in ("small_hill", "medium_hill", "large_hill"):
            return "hollow_hill"
        return kind

    @staticmethod
    def _job_locate_position(job):
        anchor = job.get("anchor")
        bounds = job.get("bounds")
        if not anchor or len(anchor) < 3:
            return None
        if bounds and len(bounds) == 6:
            return [
                int(round((int(bounds[0]) + int(bounds[3])) / 2.0)),
                int(anchor[1]),
                int(round((int(bounds[2]) + int(bounds[5])) / 2.0)),
            ]
        center = job.get("center")
        if center and len(center) >= 2:
            return [int(center[0]), int(anchor[1]), int(center[1])]
        return [int(anchor[0]), int(anchor[1]), int(anchor[2])]

    @staticmethod
    def _horizontal_distance_squared(first, second):
        dx = int(first[0]) - int(second[0])
        dz = int(first[2]) - int(second[2])
        return dx * dx + dz * dz

    def _tracked_ruin_location(self, ruin_id, position, radius_blocks):
        nearest = None
        nearest_distance = None
        jobs = list(self._ledger.values()) + list(self._manual_jobs)
        for job in jobs:
            if not isinstance(job, dict):
                continue
            if job.get("state") in ("skipped", "failed"):
                continue
            if self._job_entry_id(job) != ruin_id:
                continue
            located = self._job_locate_position(job)
            if located is None:
                continue
            distance_squared = self._horizontal_distance_squared(
                position,
                located,
            )
            if distance_squared > radius_blocks * radius_blocks:
                continue
            if (
                nearest_distance is None
                or distance_squared < nearest_distance
            ):
                nearest = located
                nearest_distance = distance_squared
        if nearest is None:
            return None
        return {
            "id": ruin_id,
            "position": nearest,
            "distance": int(round(math.sqrt(nearest_distance))),
            "source": "tracked",
            "radius": radius_blocks,
        }

    def _predicted_landmark_location(
        self,
        ruin_id,
        position,
        radius_blocks,
    ):
        centers_in_radius = (
            ruin_logic.route_landmark_centers_in_radius
            if ruin_id in ruin_logic.ROUTE_LANDMARK_KINDS
            else ruin_logic.landmark_centers_in_radius
        )
        centers = centers_in_radius(position[0], position[2], radius_blocks)
        for center_x, center_z in centers:
            ledger_key = "%d,%d" % (center_x, center_z)
            recorded = self._ledger.get(ledger_key)
            if ruin_id in ruin_logic.ROUTE_LANDMARK_KINDS:
                _record_key, recorded = self._route_ledger_record(
                    center_x,
                    center_z,
                )
            if (
                recorded is not None
                and not self._is_retryable_discovery_failure(recorded)
            ):
                continue
            biome_name = self._landmark_biome_name(center_x, center_z)
            if biome_name is None:
                continue
            landmark_kind = self._landmark_kind_at_center(
                biome_name,
                center_x,
                center_z,
            )
            entry = self._entry_for_landmark(landmark_kind)
            if entry is None or entry.get("id") != ruin_id:
                continue
            _, variant = self._entry_variant(
                entry,
                landmark_kind,
                center_x,
                center_z,
            )
            if variant is None:
                continue
            surface_y = self._surface_is_acceptable(
                entry,
                variant,
                center_x,
                center_z,
            )
            if surface_y is None or surface_y is False:
                continue
            located = [center_x, int(surface_y), center_z]
            distance_squared = self._horizontal_distance_squared(
                position,
                located,
            )
            return {
                "id": ruin_id,
                "position": located,
                "distance": int(round(math.sqrt(distance_squared))),
                "source": "predicted",
                "radius": radius_blocks,
            }
        return None

    def _grid_predicted_landmark_location(
        self,
        ruin_id,
        position,
        radius_blocks,
    ):
        """Locate a deterministic variety slot without loading its chunks."""
        centers = ruin_logic.landmark_centers_in_radius(
            position[0],
            position[2],
            radius_blocks,
        )
        for center_x, center_z in centers:
            ledger_key = "%d,%d" % (center_x, center_z)
            recorded = self._ledger.get(ledger_key)
            if (
                recorded is not None
                and not self._is_retryable_discovery_failure(recorded)
            ):
                continue
            landmark_kind = ruin_logic.resolve_variety_landmark(
                int(center_x) >> 4,
                int(center_z) >> 4,
                self._world_seed,
                SUPPORTED_VARIETY,
            )
            entry = self._entry_for_landmark(landmark_kind)
            if entry is None or entry.get("id") != ruin_id:
                continue
            located = [center_x, int(position[1]), center_z]
            distance_squared = self._horizontal_distance_squared(
                position,
                located,
            )
            return {
                "id": ruin_id,
                "position": located,
                "distance": int(round(math.sqrt(distance_squared))),
                "source": "grid_predicted",
                "radius": radius_blocks,
            }
        return None

    def debug_locate(
        self,
        ruin_id,
        position,
        radius_blocks=DEFAULT_LOCATE_RADIUS,
    ):
        ruin_id = str(ruin_id)
        entry = self._catalog.get(ruin_id)
        if entry is None:
            return False, "unknown ruin id"
        try:
            radius_blocks = max(
                1,
                min(MAX_LOCATE_RADIUS, int(radius_blocks)),
            )
            position = [
                int(position[0]),
                int(position[1]),
                int(position[2]),
            ]
        except (IndexError, TypeError, ValueError):
            return False, "invalid locate position or radius"

        tracked = self._tracked_ruin_location(
            ruin_id,
            position,
            radius_blocks,
        )
        if tracked is not None:
            return True, tracked
        if entry.get("strategy") != "landmark_service":
            return (
                False,
                "no tracked %s found in explored chunks within %d blocks"
                % (ruin_id, radius_blocks),
            )
        try:
            predicted = self._predicted_landmark_location(
                ruin_id,
                position,
                radius_blocks,
            )
        except Exception:
            # Live biome/surface APIs may reject unloaded candidate chunks.
            # Locate is read-only, so retain the deterministic landmark-grid
            # answer instead of canceling the chat command without a target.
            predicted = None
        if predicted is None:
            predicted = self._grid_predicted_landmark_location(
                ruin_id,
                position,
                radius_blocks,
            )
        if predicted is None:
            return (
                False,
                "no %s landmark found within %d blocks"
                % (ruin_id, radius_blocks),
            )
        return True, predicted

    def debug_place(self, ruin_id, position):
        entry = self._catalog.get(str(ruin_id))
        if entry is None:
            return False, "unknown ruin id"
        variants = entry.get("variants", [])
        selected_variant = None
        if not variants:
            pieces = entry.get("pieces", [])
            variant_index = 0
        else:
            variant_index = 0
            selected_variant = variants[0]
            pieces = selected_variant.get("pieces", [])
        if not pieces:
            return False, "ruin has no structure pieces"
        origin = [int(position[0]), int(position[1]), int(position[2])]
        local_bounds = (
            (selected_variant or {}).get("bounds")
            or entry.get("bounds", [0, 0, 0, 0, 0, 0])
        )
        world_bounds = [
            origin[0] + local_bounds[0],
            origin[1] + local_bounds[1],
            origin[2] + local_bounds[2],
            origin[0] + local_bounds[3],
            origin[1] + local_bounds[4],
            origin[2] + local_bounds[5],
        ]
        job_kind = str(
            (selected_variant or {}).get("landmarkKind", ruin_id)
        )
        job = ruin_logic.create_landmark_job(
            job_kind,
            origin,
            variant_index,
            pieces,
            world_bounds,
        )
        job["entryId"] = entry["id"]
        if isinstance(entry.get("controlledSpawns"), dict):
            job["controlledSpawns"] = self._controlled_spawns_for_variant(
                entry,
                selected_variant or {},
            )
        if entry.get("placementProfile"):
            self._apply_template_job_contract(
                job,
                entry,
                selected_variant or {},
            )
        if job_kind == "naga_courtyard":
            job["courtyardLayoutPolicyVersion"] = (
                COURTYARD_LAYOUT_POLICY_VERSION
            )
        variant_spawner = ruin_logic.boss_spawner_for_variant(
            entry,
            selected_variant,
        )
        if variant_spawner:
            job["bossSpawner"] = variant_spawner
            job["bossKind"] = str(
                job["bossSpawner"].get("kind", "naga")
            )
            job["bossSpawned"] = False
            job["bossDefeated"] = False
            job["rewardClaimed"] = False
            manual_key = "manual:%d,%d" % (origin[0], origin[2])
            self._ledger[manual_key] = job
            self._index_job(manual_key, job)
            self._persist()
        elif job_kind in ruin_logic.HOLLOW_HILL_KIND_DATA:
            manual_key = "manual:%d,%d" % (origin[0], origin[2])
            self._ledger[manual_key] = job
            self._persist()
        else:
            self._manual_jobs.append(job)
        return True, "queued"
