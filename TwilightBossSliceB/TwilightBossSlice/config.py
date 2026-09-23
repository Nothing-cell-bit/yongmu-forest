# -*- coding: utf-8 -*-

from TwilightBossSlice.release_metadata import (
    PACK_VERSION,
    PACK_VERSION_STRING,
)

ModName = "TwilightBossSlice"
ServerSystemName = "ServerSystem"
ClientSystemName = "ClientSystem"

# Native attached-layer candidate; first/third-person acceptance is still
# required. False selects the retained independent-entity comparison path.
FORTIFICATION_USE_PLAYER_LAYER = True

BOSS_IDENTIFIER = "tf_slice:forest_wyrm"
DIMENSION_ID = 33027004
TWILIGHT_TIME_OF_DAY = 13000
# The cubemap already contains the upstream full-bright quad field. Disable
# the engine's second star pass so it cannot overlay vanilla/cross-shaped
# sprites on top of those deterministic stars.
TWILIGHT_STAR_BRIGHTNESS = 0.0
# NetEase 1.21.90 can terminate the Windows client inside SkyRender while a
# high numeric custom dimension is attaching its LevelRenderer. Keep the
# implementation available for future engine builds, but quarantine every
# native environment effect that depends on that readiness signal.
TWILIGHT_NATIVE_ENVIRONMENT_EFFECTS_ENABLED = False
TWILIGHT_SKY_REFRESH_TICKS = 20
TWILIGHT_SKY_RENDER_WARMUP_TICKS = 40
TWILIGHT_SKY_DIAGNOSTIC_LIMIT = 12
# SkyRender cubemap face order: -Z, +X, +Z, -X, +Y, -Y.
# These fixed faces are the NetEase equivalent of the upstream renderer's
# deterministic world-space star vertex buffer.
TWILIGHT_SKY_TEXTURES = [
    "textures/environment/twilight_sky/negative_z",
    "textures/environment/twilight_sky/positive_x",
    "textures/environment/twilight_sky/positive_z",
    "textures/environment/twilight_sky/negative_x",
    "textures/environment/twilight_sky/positive_y",
    "textures/environment/twilight_sky/negative_y",
]
# NetEase only resolves native `{dimension}_clouds.png` overrides for the
# built-in/mirror dimension ID range. Dimension 33027004 therefore owns an
# explicit, horizontally oriented Microsoft-particle cloud plane instead.
TWILIGHT_CLOUD_PARTICLE = "tf_slice:twilight_cloud_layer"
TWILIGHT_CLOUD_HEIGHT = 192.0
TWILIGHT_CLOUD_TILE_SIZE = 768.0
TWILIGHT_CLOUD_GRID_RADIUS = 1
TWILIGHT_CLOUD_UPDATE_TICKS = 2
TWILIGHT_CLOUD_DRIFT_PER_TICK = 0.02
AMBIENT_FIREFLY_PARTICLE = "tf_slice:wandering_firefly"
AMBIENT_FIREFLY_INTERVAL_TICKS = 8
AMBIENT_FIREFLY_RADIUS = 10.0
ENTRY_POS = (3.5, 97.0, 0.5)
# Default to one native dimension change centered on the final portal exit.
# The first target LevelChunk does not exist yet, so Y is corrected behind
# the loading overlay after DimensionChangeFinish; X/Z already match the
# deterministic west edge selected by portal_logic.find_exit.
PORTAL_DIRECT_ENTRY_ENABLED = True
WORLDGEN_DIRECT_ENTRY_FOOT_Y = 97.0
# Native structure callbacks can race the first LevelChunk publication during
# ChangePlayerDimension. Enter at a deterministic structure-free staging area,
# then move to the coordinate-matched destination after the finish-event grace.
# Retained only as a rollback path while direct-entry cold starts are verified.
WORLDGEN_STAGING_FOOT_POS = (8192.5, 97.0, 8192.5)
WORLDGEN_STAGING_GUARD_RADIUS = 512
# A zero entity gravity factor falls back to the world's gravity in the
# NetEase API, so use the smallest practical non-zero factor while a staged
# player waits for the destination chunks and portal exit to become ready.
PORTAL_STAGING_GRAVITY = 0.000001
RETURN_PORTAL_ORIGIN = (0, 96, 0)
PORTAL_IDENTIFIER = "tf_slice:twilight_portal"
PORTAL_CATALYST = "minecraft:diamond"
PORTAL_MIN_SIZE = 4
PORTAL_MAX_SIZE = 64
PORTAL_SCAN_INTERVAL_TICKS = 2
PORTAL_CATALYST_TIMEOUT_TICKS = 200
PORTAL_COOLDOWN_TICKS = 60
PORTAL_ARRIVAL_TIMEOUT_TICKS = 400
PORTAL_ARRIVAL_TIMEOUT_SECONDS = 60.0
PORTAL_ENTRY_BOOTSTRAP_TICKS = 40
PORTAL_ENTRY_BOOTSTRAP_SECONDS = 3.0
PORTAL_AREA_WARMUP_TICKS = 20
PORTAL_BUILD_RETRY_TICKS = 5
PORTAL_AREA_MARGIN = 80
PORTAL_CLIENT_READY_TIMEOUT_TICKS = 180
PORTAL_CLIENT_READY_STABLE_TICKS = 2
PORTAL_CLIENT_ENGINE_READY_FALLBACK_TICKS = 80
PORTAL_CLIENT_RENDER_SETTLE_TICKS = 20
PORTAL_CLIENT_LOADING_TIMEOUT_TICKS = 1800
PORTAL_LIGHTNING_FIRE_RADIUS = 3
PORTAL_LIGHTNING_FIRE_VERTICAL_RADIUS = 3
PORTAL_LIGHTNING_FIRE_CLEANUP_TICKS = 8
PORTAL_RETURN_POINTS_KEY = "tf_slice:portal_return_points_v1"
MAX_PENDING_CATALYSTS = 32
BOSS_MAX_HEALTH = 200.0
DEFAULT_DIFFICULTY_ID = 2
CONTACT_COOLDOWN_TICKS = 20
SEGMENT_COLLISION_SCAN_RADIUS = 32
SEGMENT_REMOVAL_RETRY_TICKS = 2
WAYPOINT_REACHED_DISTANCE = 2.25
DEFAULT_MOB_GRIEFING = True
BOSS_DISCOVERY_INTERVAL_TICKS = 20
BOSS_DISCOVERY_RADIUS = 96
BOSS_MISSING_ACTOR_GRACE_TICKS = 60
COURTYARD_BOSS_STABLE_CONFIRM_TICKS = 2
COURTYARD_BOSS_PENDING_TIMEOUT_TICKS = 40
NAVIGATION_MAX_ITERATIONS = 1000
NAVIGATION_CANCEL_MAX_ITERATIONS = 1
NAVIGATION_REISSUE_TICKS = 60
NAVIGATION_SPEED = 1.0
NAVIGATION_CHARGE_SPEED = 1.5
NAVIGATION_STUCK_TICKS = 30
NAVIGATION_MIN_PROGRESS = 0.12
MAX_BLOCKS_PER_CLEAR = 125
BLOCK_CLEAR_INTERVAL_TICKS = 1
MOB_HIT_BLOCK_PRECISION = 0.05
NAGA_LOOT_TABLE = "loot_tables/chests/naga_courtyard.json"
LICH_IDENTIFIER = "tf_slice:lich"
LICH_LOOT_TABLE = "loot_tables/chests/tf_slice/lich_tower_reward.json"
HYDRA_LOOT_TABLE = "loot_tables/chests/tf_slice/hydra_reward.json"
LEGACY_PLAYER_PROGRESS_KEYS = (
    "tf_slice:boss_progress_v2",
    "tf_slice:boss_progress_v1",
)
# Retained as a compatibility alias for older runtime helpers. New migration
# code iterates LEGACY_PLAYER_PROGRESS_KEYS and only removes neither key.
LEGACY_PLAYER_PROGRESS_KEY = LEGACY_PLAYER_PROGRESS_KEYS[-1]
PLAYER_PROGRESS_KEY = "tf_slice:boss_progress_v3"
KEEPING_CHARM_SNAPSHOTS_KEY = "tf_slice:keeping_charm_snapshots_v1"
HYDRA_STATE_EXTRA_KEY = "tf_slice:hydra_state_v1"
MINOSHROOM_STATE_EXTRA_KEY = "tf_slice:minoshroom_state_v1"
LEAF_DECAY_PERSISTENT_POSITIONS_KEY = "tf_slice:persistent_leaves_v1"
LEAF_DECAY_MIN_DELAY_TICKS = 200
LEAF_DECAY_MAX_DELAY_TICKS = 1200
LEAF_DECAY_PROCESS_INTERVAL_TICKS = 5
LEAF_DECAY_TICK_BUDGET = 1
LEAF_DECAY_MAX_PENDING = 4096
LEAF_DECAY_SAVE_INTERVAL_TICKS = 100

# The original Naga evaluates movement, collision, and griefing every tick.
AI_INTERVAL_TICKS = 1
SYNC_INTERVAL_TICKS = 10
PERF_INTERVAL_TICKS = 100
MAX_ACTIVE_BOSSES = 4
MAX_SAMPLE_COUNT = 200
BOSS_HUD_RANGE = 64.0
UR_GHAST_HUD_RANGE = 128.0

# Magic-map constants mirror the upstream 128px * 16 blocks/px map. The
# filled item remains custom so its upstream icon and TF-only biome pixels
# cannot be replaced by Minecraft's terrain-map renderer. Maps created by
# 0.9.17-0.9.29 used the vanilla carrier; only stacks with a valid tfmm
# identity are migrated back to the custom item.
MAGIC_MAP_RULESET = "twilightforest:1.20.1-4.3.2508"
MAGIC_MAP_ITEM = "tf_slice:magic_map"
FILLED_MAGIC_MAP_ITEM = "tf_slice:filled_magic_map"
LEGACY_NATIVE_MAGIC_MAP_ITEM = "minecraft:filled_map"
# Consume one bounded batch from an already cached discovery frontier every
# script tick so the map fills smoothly without querying the item registry.
MAGIC_MAP_SCAN_INTERVAL_TICKS = 1
# Held-map changes are event-driven on the client. Keep a bounded server-side
# item reconciliation scan for offhand and missed-event recovery.
MAGIC_MAP_ITEM_RECONCILE_INTERVAL_TICKS = 10
# Client carried-item events update the HUD immediately.  This slower poll is
# only a fallback for offhand changes and engine builds that drop an event.
MAGIC_MAP_CLIENT_RECONCILE_INTERVAL_TICKS = 30
# The held-map HUD was isolated during crash diagnosis.  Chunk-worker dump
# evidence ruled that path out, so restore both the native proxy and fallback
# HUD while keeping the temporary diagnostic stream disabled by default.
MAGIC_MAP_HELD_HUD_ENABLED = True
MAGIC_MAP_DIAGNOSTICS_ENABLED = False
MAGIC_MAP_DISCOVERY_RADIUS = 512
MAGIC_MAP_SECTORS_KEY = "tf_slice:magic_map_sectors_v1"
MAGIC_MAP_RECORDS_KEY = "tf_slice:magic_map_records_v2"
MAZE_MAP_ITEM = "tf_slice:maze_map"
FILLED_MAZE_MAP_ITEM = "tf_slice:filled_maze_map"
MAZE_MAP_RECORDS_KEY = "tf_slice:maze_map_records_v1"
MAGIC_MAP_SAMPLE_BUDGET = 13
MAGIC_MAP_SAVE_INTERVAL_TICKS = 20
MAGIC_MAP_UI_NAME = "MagicMapUI"
MAGIC_MAP_HUD_UI_NAME = "MagicMapHudUI"
FIRE_REACT_UI_NAME = "FireReactUI"
LICH_BOSS_HUD_UI_NAME = "LichBossHudUI"
NAGA_BOSS_HUD_UI_NAME = "NagaBossHudUI"
MINOSHROOM_BOSS_HUD_UI_NAME = "MinoshroomBossHudUI"
HYDRA_BOSS_HUD_UI_NAME = "HydraBossHudUI"
KNIGHT_PHANTOMS_BOSS_HUD_UI_NAME = "KnightPhantomsBossHudUI"
UR_GHAST_BOSS_HUD_UI_NAME = "UrGhastBossHudUI"
PORTAL_LOADING_UI_NAME = "PortalLoadingUI"
