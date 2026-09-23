# -*- coding: utf-8 -*-
import copy
import math
import random
import time
import uuid

import server.extraServerApi as serverApi
import TwilightBossSlice.config as config
from TwilightBossSlice.item_effects import ItemEffects
import TwilightBossSlice.reward_delivery as reward_delivery
import TwilightBossSlice.entry_diagnostics as entry_diagnostics
import TwilightBossSlice.entity_registry_logic as entity_registry_logic
import TwilightBossSlice.forest_animal_logic as forest_animal_logic
import TwilightBossSlice.fire_swamp_logic as fire_swamp_logic
import TwilightBossSlice.flight_logic as flight_logic
import TwilightBossSlice.leaf_decay_logic as leaf_decay_logic
import TwilightBossSlice.magic_map_logic as magic_map_logic
import TwilightBossSlice.native_item_diagnostics as native_item_diagnostics
import TwilightBossSlice.maze_map_logic as maze_map_logic
import TwilightBossSlice.lich_logic as lich_logic
import TwilightBossSlice.naga_logic as naga_logic
import TwilightBossSlice.cindercoil_visuals as cindercoil_visuals
import TwilightBossSlice.hydra_logic as hydra_logic
import TwilightBossSlice.maze_slime_logic as maze_slime_logic
import TwilightBossSlice.minotaur_logic as minotaur_logic
import TwilightBossSlice.mosquito_swarm_logic as mosquito_swarm_logic
import TwilightBossSlice.knight_route_logic as knight_route_logic
import TwilightBossSlice.phantom_urghast_mob_logic as phantom_urghast_mob_logic
import TwilightBossSlice.goblin_combat as goblin_combat
import TwilightBossSlice.dark_tower_logic as dark_tower_logic
import TwilightBossSlice.ur_ghast_logic as ur_ghast_logic
import TwilightBossSlice.ur_ghast_effect_logic as ur_ghast_effect_logic
import TwilightBossSlice.route_progression_logic as route_progression_logic
import TwilightBossSlice.portal_logic as portal_logic
import TwilightBossSlice.public_block_logic as public_block_logic
import TwilightBossSlice.banister_logic as banister_logic
import TwilightBossSlice.vanilla_block_adapter_logic as vanilla_block_adapter_logic
import TwilightBossSlice.quest_ram_logic as quest_ram_logic
import TwilightBossSlice.spawn_policy as spawn_policy
import TwilightBossSlice.scepter_logic as scepter_logic
import TwilightBossSlice.spider_logic as spider_logic
import TwilightBossSlice.beetle_combat_logic as beetle_combat_logic
import TwilightBossSlice.boss_hud_logic as boss_hud_logic
import TwilightBossSlice.cave_plant_logic as cave_plant_logic
import TwilightBossSlice.plant_support_logic as plant_support_logic
import TwilightBossSlice.chat_command_logic as chat_command_logic
import TwilightBossSlice.transformation_logic as transformation_logic
from TwilightBossSlice.biome_catalog import BIOMES_BY_IDENTIFIER
from TwilightBossSlice.structureWorldgenService import (
    StructureWorldgenService, DEFAULT_LOCATE_RADIUS
)
from TwilightBossSlice.mushroomWorldgenService import (
    MushroomWorldgenService
)
from TwilightBossSlice.lilyPadWorldgenService import (
    LilyPadWorldgenService, TRIGGER as LILY_PAD_CANDIDATE
)
from TwilightBossSlice.enchantedTreeWorldgenService import (
    EnchantedTreeWorldgenService
)


CF = serverApi.GetEngineCompFactory()
ENGINE_NAMESPACE = serverApi.GetEngineNamespace()
ENGINE_SYSTEM = serverApi.GetEngineSystemName()
LEVEL_ID = serverApi.GetLevelId()
ENTRY_DIAGNOSTIC_VERSION = config.PACK_VERSION_STRING

try:
    _ENGINE_TEXT_TYPE = unicode
except NameError:
    _ENGINE_TEXT_TYPE = str


def _engine_text(value):
    """Return the native ``str`` required by NetEase 3.8 message APIs."""
    if _ENGINE_TEXT_TYPE is not str and isinstance(
        value, _ENGINE_TEXT_TYPE
    ):
        return value.encode("utf-8")
    if isinstance(value, str):
        return value
    return str(value)

STATE_IDS = {
    naga_logic.CIRCLE: 0,
    naga_logic.INTIMIDATE: 1,
    naga_logic.CRUMBLE: 2,
    naga_logic.CHARGE: 3,
    naga_logic.STUNLESS_CHARGE: 4,
    naga_logic.DAZE: 5,
}
SEGMENT_IDENTIFIER = "tf_slice:forest_wyrm_segment"
NATURE_BOLT_IDENTIFIER = "tf_slice:nature_bolt"
SLIME_BLOB_IDENTIFIER = "tf_slice:slime_blob"
LICH_IDENTIFIER = "tf_slice:lich"
LICH_CLONE_IDENTIFIER = "tf_slice:lich_shadow_clone"
LICH_MINION_IDENTIFIER = "tf_slice:lich_minion"
DEATH_TOME_IDENTIFIER = "tf_slice:death_tome"
LOYAL_ZOMBIE_IDENTIFIER = "tf_slice:loyal_zombie"
LICH_BOLT_IDENTIFIER = "tf_slice:lich_bolt"
LICH_BOMB_IDENTIFIER = "tf_slice:lich_bomb"
MINOTAUR_IDENTIFIER = "tf_slice:minotaur"
MINOSHROOM_IDENTIFIER = "tf_slice:minoshroom"
MAZE_SLIME_IDENTIFIER = "tf_slice:maze_slime"
MOSQUITO_SWARM_IDENTIFIER = "tf_slice:mosquito_swarm"
HYDRA_IDENTIFIER = "tf_slice:hydra"
HYDRA_HEAD_IDENTIFIER = "tf_slice:hydra_head"
HYDRA_NECK_IDENTIFIER = "tf_slice:hydra_neck"
HYDRA_MORTAR_IDENTIFIER = "tf_slice:hydra_mortar"
HYDRA_PART_PROXY_IDENTIFIER = "tf_slice:hydra_part_proxy"
KNIGHT_PHANTOM_IDENTIFIER = "tf_slice:knight_phantom"
UR_GHAST_IDENTIFIER = "tf_slice:ur_ghast"
UR_GHAST_FIREBALL_IDENTIFIER = "tf_slice:ur_ghast_fireball"
MINI_GHAST_IDENTIFIER = "tf_slice:mini_ghast"
KNIGHT_AXE_PROJECTILE = "tf_slice:knight_axe_projectile"
KNIGHT_PICKAXE_PROJECTILE = "tf_slice:knight_pickaxe_projectile"
BLOCK_CHAIN_PROJECTILE = "tf_slice:block_chain_projectile"
BLOCK_CHAIN_LINK_IDENTIFIER = "tf_slice:block_chain_link"
BLOCK_CHAIN_GOBLIN_IDENTIFIER = "tf_slice:block_chain_goblin"
LOWER_GOBLIN_KNIGHT_IDENTIFIER = "tf_slice:lower_goblin_knight"
UPPER_GOBLIN_KNIGHT_IDENTIFIER = "tf_slice:upper_goblin_knight"
HELMET_CRAB_IDENTIFIER = "tf_slice:helmet_crab"
CARMINITE_GOLEM_IDENTIFIER = "tf_slice:carminite_golem"
TOWER_BROODLING_IDENTIFIER = "tf_slice:tower_broodling"
TOWER_GHAST_IDENTIFIER = "tf_slice:tower_ghast"
TOWERWOOD_BORER_IDENTIFIER = "tf_slice:towerwood_borer"
PHANTOM_UR_GHAST_MOB_IDENTIFIERS = set(
    (
        BLOCK_CHAIN_GOBLIN_IDENTIFIER,
        LOWER_GOBLIN_KNIGHT_IDENTIFIER,
        UPPER_GOBLIN_KNIGHT_IDENTIFIER,
        HELMET_CRAB_IDENTIFIER,
        CARMINITE_GOLEM_IDENTIFIER,
        TOWER_BROODLING_IDENTIFIER,
        MINI_GHAST_IDENTIFIER,
        TOWER_GHAST_IDENTIFIER,
        TOWERWOOD_BORER_IDENTIFIER,
    )
)
UR_GHAST_STATE_EXTRA_KEY = "tf_slice:ur_ghast_state_v1"
DARK_TOWER_STATE_EXTRA_KEY = "tf_slice:dark_tower_mechanisms_v1"
HYDRA_HEAD_COUNT = 7
HYDRA_NECK_COUNT = 5
TOME_BOLT_IDENTIFIER = "tf_slice:tome_bolt"
TWILIGHT_WAND_BOLT_IDENTIFIER = "tf_slice:twilight_wand_bolt"
LICH_STATE_EXTRA_KEY = "tf_slice:lich_state_v2"
NAGA_STATE_EXTRA_KEY = "tf_slice:naga_state_v1"
MINOSHROOM_STATE_EXTRA_KEY = "tf_slice:minoshroom_state_v1"
LICH_DEPENDENT_EXTRA_KEY = "tf_slice:lich_dependent_v1"
LICH_SPAWNER_BLOCK = "tf_slice:lich_boss_spawner"
QUEST_RAM_IDENTIFIER = "tf_slice:quest_ram"
TINY_BIRD_IDENTIFIER = "tf_slice:tiny_bird"
PENGUIN_IDENTIFIER = "tf_slice:penguin"
ITEM_ENTITY_IDENTIFIERS = set(("minecraft:item", "minecraft:item_entity"))
LICH_POPPABLE_IDENTIFIERS = set(
    (
        "minecraft:skeleton",
        "minecraft:stray",
        "minecraft:wither_skeleton",
        "minecraft:zombie",
        "minecraft:enderman",
        "minecraft:spider",
        "minecraft:creeper",
        "tf_slice:swarm_spider",
    )
)
LICH_BYPASS_DAMAGE_CAUSES = set(
    ("void", "out_of_world", "suicide", "kill", "override")
)
WATER_BLOCKS = set(
    ("minecraft:water", "minecraft:flowing_water")
)
LAVA_BLOCKS = set(
    ("minecraft:lava", "minecraft:flowing_lava")
)
FIRE_SWAMP_FIRE_IMMUNE = set(
    (
        "minecraft:blaze",
        "minecraft:magma_cube",
        "minecraft:strider",
        HYDRA_IDENTIFIER,
        HYDRA_HEAD_IDENTIFIER,
        HYDRA_NECK_IDENTIFIER,
        HYDRA_MORTAR_IDENTIFIER,
        HYDRA_PART_PROXY_IDENTIFIER,
    )
)
FIRE_SWAMP_DISCOVERY_RADIUS = 12
FIRE_SWAMP_DISCOVERY_INTERVAL_TICKS = 40
DIMENSION_NATIVE_COMPONENT_GRACE_TICKS = 80
FIRE_SWAMP_DISCOVERY_GRACE_TICKS = DIMENSION_NATIVE_COMPONENT_GRACE_TICKS
PORTAL_BACKGROUND_PRELOAD_TIMEOUT_TICKS = 200
FIRE_SWAMP_DISCOVERY_COLUMNS_PER_TICK = 16
SIGHT_PASSABLE_BLOCKS = set(
    (
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
        "minecraft:water",
        "minecraft:flowing_water",
        "minecraft:tallgrass",
        "minecraft:double_plant",
        "minecraft:yellow_flower",
        "minecraft:red_flower",
        "minecraft:brown_mushroom",
        "minecraft:red_mushroom",
        "minecraft:snow_layer",
        "minecraft:vine",
    )
)
RUIN_MOB_IDENTIFIERS = set(
    (
        "tf_slice:raven",
        "tf_slice:skeleton_druid",
        "tf_slice:swarm_spider",
        "tf_slice:hedge_spider",
        "tf_slice:hostile_wolf",
        "tf_slice:wraith",
        "tf_slice:rising_zombie",
        "tf_slice:redcap",
        "tf_slice:redcap_sapper",
        "tf_slice:kobold",
        "tf_slice:fire_beetle",
        "tf_slice:slime_beetle",
        "tf_slice:pinch_beetle",
        "tf_slice:mist_wolf",
        "tf_slice:king_spider",
    )
)

MAZESTONE_BLOCKS = frozenset(
    "tf_slice:" + name
    for name in (
        "mazestone", "mazestone_brick", "cut_mazestone",
        "decorative_mazestone", "cracked_mazestone",
        "mossy_mazestone", "mazestone_mosaic", "mazestone_border",
    )
)
TROPHY_BLOCKS = frozenset(
    (
        "tf_slice:naga_trophy",
        "tf_slice:naga_wall_trophy",
        "tf_slice:lich_trophy",
        "tf_slice:lich_wall_trophy",
        "tf_slice:hydra_trophy",
        "tf_slice:hydra_wall_trophy",
        "tf_slice:ur_ghast_trophy",
        "tf_slice:ur_ghast_wall_trophy",
        "tf_slice:knight_phantom_trophy",
        "tf_slice:knight_phantom_wall_trophy",
        "tf_slice:minoshroom_trophy",
        "tf_slice:minoshroom_wall_trophy",
        "tf_slice:quest_ram_trophy",
        "tf_slice:quest_ram_wall_trophy",
    )
)
UR_GHAST_TROPHY_BLOCKS = frozenset(
    ("tf_slice:ur_ghast_trophy", "tf_slice:ur_ghast_wall_trophy")
)
UR_GHAST_TROPHY_VISUAL = "tf_slice:ur_ghast_trophy_visual"
HUGE_LILY_PAD_BLOCK = "tf_slice:huge_lily_pad"
HUGE_LILY_QUADRANTS = frozenset(
    "tf_slice:huge_lily_pad_" + quadrant
    for quadrant in ("nw", "ne", "se", "sw")
)

PROTECTED_BLOCKS = set(
    (
        "minecraft:air",
        "minecraft:bedrock",
        "minecraft:barrier",
        "minecraft:command_block",
        "minecraft:repeating_command_block",
        "minecraft:chain_command_block",
        "minecraft:structure_block",
        "minecraft:jigsaw",
        "minecraft:end_portal",
        "minecraft:end_portal_frame",
        "minecraft:nether_portal",
        "minecraft:chest",
        "minecraft:trapped_chest",
        "minecraft:ender_chest",
        "minecraft:barrel",
        "minecraft:furnace",
        "minecraft:lit_furnace",
        "minecraft:blast_furnace",
        "minecraft:smoker",
        "minecraft:hopper",
        "minecraft:dropper",
        "minecraft:dispenser",
        "minecraft:brewing_stand",
        "minecraft:beacon",
        "minecraft:obsidian",
        "minecraft:crying_obsidian",
        "minecraft:reinforced_deepslate",
    )
)

def _distance_xz(first, second):
    dx = float(first[0]) - float(second[0])
    dz = float(first[2]) - float(second[2])
    return math.sqrt(dx * dx + dz * dz)


def _distance_sq(first, second):
    dx = float(first[0]) - float(second[0])
    dy = float(first[1]) - float(second[1])
    dz = float(first[2]) - float(second[2])
    return dx * dx + dy * dy + dz * dz


def _normalized_xz(first, second):
    dx = float(second[0]) - float(first[0])
    dz = float(second[2]) - float(first[2])
    length = math.sqrt(dx * dx + dz * dz)
    if length < 0.0001:
        return (0.0, 0.0)
    return (dx / length, dz / length)


class ServerSystem(serverApi.GetServerSystemCls()):
    """Server-authoritative Twilight Forest Naga vertical slice."""

    def __init__(self, namespace, systemName):
        super(ServerSystem, self).__init__(namespace, systemName)
        self._tick = 0
        self._native_item_diag_sequence = 0
        self._entry_diagnostics = entry_diagnostics.EntryDiagnostics(
            version=ENTRY_DIAGNOSTIC_VERSION
        )
        self._entry_diag_structure_events = 0
        self._entry_trace(
            "system.init",
            namespace=namespace,
            systemName=systemName,
            tracePath=self._entry_diagnostics.path,
        )
        self._sequence = 0
        self._boss_sync_dirty = False
        self._bosses = {}
        self._lich_bosses = {}
        self._lich_clones = {}
        self._lich_minions = {}
        self._recent_lich_projectile_hits = {}
        self._recent_lich_effect_damage = {}
        self._loyal_zombies = {}
        self._lich_projectiles = {}
        self._slime_projectiles = {}
        self._player_fortification = {}
        self._fortification_cooldowns = {}
        self._fortification_visuals = {}
        self._lifedrain_users = {}
        self._recent_lifedrain_hits = {}
        self._route_mobs = {}
        self._ur_ghast_trophy_visuals = {}
        self._knight_phantoms = {}
        self._phantom_urghast_mobs = {}
        self._goblin_combat = goblin_combat.GoblinCombat(self, CF, LEVEL_ID)
        self._pending_broodling_children = 0
        self._block_chain_projectiles = {}
        self._knightmetal_shield_users = {}
        self._knight_projectiles = {}
        self._knightmetal_contact_cooldowns = {}
        self._ur_ghasts = {}
        self._ur_ghast_projectiles = {}
        self._pending_ur_ghast_player_attacks = {}
        self._ur_ghast_internal_health_writes = {}
        self._ur_ghast_projectile_tombstones = {}
        self._ur_ghast_logic_clock_remainder = 0
        self._ur_ghast_logic_tick = 0
        self._ur_ghast_logic_step = False
        self._ur_ghast_native_weather_active = False
        self._ur_ghast_weather_refresh_tick = 0
        self._ghast_player_perception_cache = {}
        self._ghast_traps = {}
        self._dark_tower_mechanisms = {}
        self._pending_maze_slime_sizes = {}
        self._hydras = {}
        self._hydra_heads = {}
        self._hydra_necks = {}
        self._hydra_parts = {}
        self._hydra_mortars = {}
        self._pending_hydra_player_attacks = {}
        self._fire_swamp_devices = {}
        self._fire_swamp_discovery_queue = []
        self._fire_swamp_discovery_ready_ticks = {}
        self._dimension_change_in_progress = set()
        self._dimension_worldgen_ready_ticks = {}
        self._route_penalty_ticks = {}
        self._keeping_snapshots = {}
        self._progress_notice_cooldowns = {}
        self._fire_react_sessions = {}
        self._segment_owners = {}
        self._pending_naga_spawns = []
        self._pending_courtyard_nagas = []
        self._return_points = {}
        self._client_acks = {}
        self._shield_cooldowns = {}
        self._pending_catalysts = {}
        self._pending_quest_offerings = {}
        self._tiny_birds = {}
        self._penguins = set()
        self._portal_cooldowns = {}
        self._portal_links = {}
        self._pending_portal_entries = {}
        self._portal_background_preload_queue = []
        self._portal_background_preload_keys = set()
        self._portal_background_preload_inflight = None
        self._worldgen_perf_counters = {}
        self._worldgen_perf_structure_counts = {}
        self._pending_portal_recovery_players = set()
        self._portal_area_sequence = 0
        self._portal_fire_cleanups = []
        self._known_players = set()
        self._ruin_mobs = {}
        self._pending_swarm_children = 0
        self._magic_map_extra = CF.CreateExtraData(LEVEL_ID)
        self._progress_extra = CF.CreateExtraData(LEVEL_ID)
        self._portal_extra = CF.CreateExtraData(LEVEL_ID)
        self._leaf_decay_queue = {}
        self._leaf_decay_bridge_propagated = set()
        self._persistent_leaf_positions = (
            self._load_persistent_leaf_positions()
        )
        self._leaf_decay_state_dirty = False
        self._load_dark_tower_runtime()
        self._return_points = self._load_portal_return_points()
        self._player_progress = self._load_player_progress()
        self._keeping_snapshots = self._load_keeping_snapshots()
        self._magic_map_sectors = self._load_magic_map_sectors()
        (
            self._magic_map_records,
            self._magic_map_next_id,
        ) = self._load_magic_map_records()
        self._maze_map_records = self._load_maze_map_records()
        self._maze_map_dirty = False
        self._magic_map_dirty = False
        self._magic_map_use_cooldowns = {}
        self._magic_map_held_states = {}
        self._magic_map_delta_states = {}
        self._magic_map_discovery_frontiers = {}
        self._pending_magic_map_clone_sources = {}
        self._block_comp = CF.CreateBlockInfo(LEVEL_ID)
        self._register_leaf_decay_listeners()
        self._chunk_comp = CF.CreateChunkSource(LEVEL_ID)
        self._biome_comp = CF.CreateBiome(LEVEL_ID)
        try:
            self._weather_comp = CF.CreateWeather(LEVEL_ID)
        except Exception:
            self._weather_comp = None
        try:
            self._block_state_comp = CF.CreateBlockState(LEVEL_ID)
        except Exception:
            self._block_state_comp = None
        try:
            self._block_use_whitelist = CF.CreateBlockUseEventWhiteList(
                LEVEL_ID
            )
            for blockName in banister_logic.BANISTER_BLOCKS:
                self._block_use_whitelist.AddBlockItemListenForUseEvent(
                    blockName
                )
        except Exception:
            self._block_use_whitelist = None
        try:
            self._redstone_comp = CF.CreateRedStone(LEVEL_ID)
        except Exception:
            self._redstone_comp = None
        try:
            self._ruin_worldgen = StructureWorldgenService(
                CF,
                LEVEL_ID,
                config.DIMENSION_ID,
                self._spawn_ruin_entity,
                self._spawn_courtyard_naga,
                self._confirm_courtyard_naga,
            )
        except Exception as error:
            self._ruin_worldgen = None
            print "[TwilightBossSlice] ruin worldgen init failed:", error
        try:
            lilyChunk = CF.CreateChunkSource(LEVEL_ID)
            self._lily_pad_worldgen = LilyPadWorldgenService(
                CF.CreateFeature(LEVEL_ID), self._get_block, self._set_block,
                config.DIMENSION_ID,
                lambda position, dimension: bool(lilyChunk.CheckChunkState(dimension, position)),
            )
        except Exception as error:
            self._lily_pad_worldgen = None
            print "[TwilightBossSlice] lily worldgen init failed:", error
        try:
            self._mushroom_worldgen = MushroomWorldgenService(
                CF,
                LEVEL_ID,
                config.DIMENSION_ID,
            )
        except Exception as error:
            self._mushroom_worldgen = None
            print "[TwilightBossSlice] mushroom worldgen init failed:", error
        try:
            self._enchanted_tree_worldgen = EnchantedTreeWorldgenService(
                CF,
                LEVEL_ID,
                config.DIMENSION_ID,
            )
        except Exception as error:
            self._enchanted_tree_worldgen = None
            print "[TwilightBossSlice] enchanted tree init failed:", error
        self._samples_ms = []
        self._last_perf = {
            "avgMs": 0.0,
            "maxMs": 0.0,
            "p95Ms": 0.0,
            "p99Ms": 0.0,
            "sampleCount": 0,
        }
        self._item_effects = ItemEffects(self, CF, serverApi, LEVEL_ID)
        self._listen_engine("DamageEvent", self._item_effects.on_damage)
        self._listen_engine("ActuallyHurtServerEvent", self._item_effects.on_hurt)
        self._listen_engine("DamageEvent", self.OnGoblinDamageEvent)
        self._listen_engine("PlayerEatFoodServerEvent", self._item_effects.on_eat)
        self._listen_engine("DestroyBlockEvent", self._item_effects.on_destroy_block)
        self._listen_engine("ServerChatEvent", self.OnServerChatEvent)
        self._listen_engine("AddEntityServerEvent", self.OnAddEntity)
        self._listen_engine("ServerSpawnMobEvent", self.OnServerSpawnMob)
        self._listen_engine("RemoveEntityServerEvent", self.OnRemoveEntity)
        self._listen_engine("MobDieEvent", self.OnMobDie)
        self._listen_engine("PlayerDieEvent", self.OnRoutePlayerDie)
        self._listen_engine(
            "PlayerRespawnFinishServerEvent", self.OnRoutePlayerRespawn
        )
        self._listen_engine(
            "HealthChangeBeforeServerEvent", self.OnHealthChangeBefore
        )
        self._listen_engine(
            "ActorHurtServerEvent", self.OnActorHurtServerEvent
        )
        self._listen_engine(
            "EntityEffectDamageServerEvent", self.OnLichEffectDamage
        )
        self._listen_engine(
            "OnMobHitBlockServerEvent", self.OnMobHitBlock
        )
        self._listen_engine("PlayerDropItemServerEvent", self.OnPlayerDropItem)
        self._listen_engine("ActorAcquiredItemServerEvent", self.OnTrophyStackItemEvent)
        self._listen_engine("OnCarriedNewItemChangedServerEvent", self.OnTrophyStackItemEvent)
        self._listen_engine(
            "PlayerDoInteractServerEvent",
            self.OnPlayerDoInteractServerEvent,
        )
        self._listen_engine(
            "ServerItemTryUseEvent",
            self.OnLichScepterTryUseEvent,
        )
        self._listen_engine(
            "ServerItemTryUseEvent",
            self.OnServerItemTryUseEvent,
        )
        self._listen_engine(
            "ServerItemTryUseEvent",
            self.OnHydraRouteItemTryUseEvent,
        )
        self._listen_engine(
            "ItemReleaseUsingServerEvent",
            self.OnItemReleaseUsingServerEvent,
        )
        self._listen_engine(
            "PlayerAttackEntityEvent",
            self.OnPlayerAttackEntityEvent,
        )
        self._listen_engine(
            "ServerPlayerTryDestroyBlockEvent",
            self.OnServerPlayerTryDestroyBlockEvent,
        )
        self._listen_engine(
            "ServerEntityTryPlaceBlockEvent",
            self.OnServerEntityTryPlaceBlockEvent,
        )
        self._listen_engine(
            "EntityPlaceBlockAfterServerEvent",
            self.OnEntityPlaceBlockAfterServerEvent,
        )
        self._listen_engine(
            "ServerItemUseOnEvent",
            self.OnServerItemUseOnEvent,
        )
        self._listen_engine(
            "ServerItemUseOnEvent",
            self.OnHydraRouteItemUseOnEvent,
        )
        self._listen_engine(
            "UIContainerItemChangedServerEvent",
            self.OnMagicMapCraftingInputChanged,
        )
        self._listen_engine(
            "CraftItemOutputChangeServerEvent",
            self.OnMagicMapCrafted,
        )
        self._listen_engine(
            "ServerBlockUseEvent", self.OnServerBlockUseEvent
        )
        self._listen_engine(
            "BlockRemoveServerEvent", self.OnBlockRemoveServerEvent
        )
        self._listen_engine(
            "BlockRandomTickServerEvent", self.OnBlockRandomTickServerEvent
        )
        self._listen_engine(
            "OnEntityInsideBlockServerEvent", self.OnEntityInsideBlock
        )
        self._listen_engine(
            "BlockNeighborChangedServerEvent", self.OnBlockNeighborChanged
        )
        self._listen_engine(
            "ActuallyHurtServerEvent", self.OnActuallyHurtServerEvent
        )
        self._listen_engine(
            "ClientLoadAddonsFinishServerEvent", self.OnClientReady
        )
        self._listen_engine(
            "LoadServerAddonScriptsAfter",
            self.OnLoadServerAddonScriptsAfter,
        )
        self._listen_engine(
            "DimensionChangeServerEvent",
            self.OnDimensionChangeServerEvent,
        )
        self._listen_engine(
            "DimensionChangeFinishServerEvent",
            self.OnDimensionChangeFinish,
        )
        self._listen_engine(
            "ChunkGeneratedServerEvent",
            self.OnChunkGeneratedServerEvent,
        )
        self._listen_engine(
            "ChunkLoadedServerEvent",
            self.OnChunkLoadedServerEvent,
        )
        self._listen_engine(
            "PlaceNeteaseStructureFeatureEvent",
            self.OnPlaceNeteaseStructureFeatureEvent,
        )
        self._listen_engine(
            "ServerBlockEntityTickEvent",
            self.OnNagaSpawnerBlockEntityTick,
        )
        self._listen_engine(
            "ProjectileDoHitEffectEvent",
            self.OnProjectileDoHitEffectEvent,
        )
        self.ListenForEvent(
            config.ModName,
            config.ClientSystemName,
            "BossSyncAck",
            self,
            self.OnBossSyncAck,
        )
        self.ListenForEvent(
            config.ModName,
            config.ClientSystemName,
            "LifedrainReleaseRequest",
            self,
            self.OnLifedrainReleaseRequest,
        )
        self.ListenForEvent(
            config.ModName,
            config.ClientSystemName,
            "KnightItemUseRequest",
            self,
            self.OnKnightItemUseRequest,
        )
        self.ListenForEvent(
            config.ModName,
            config.ClientSystemName,
            "PortalArrivalEngineReady",
            self,
            self.OnPortalArrivalEngineReady,
        )
        self.ListenForEvent(
            config.ModName,
            config.ClientSystemName,
            "PortalArrivalClientReady",
            self,
            self.OnPortalArrivalClientReady,
        )
        self.ListenForEvent(
            config.ModName,
            config.ClientSystemName,
            "MagicMapOpenRequest",
            self,
            self.OnMagicMapOpenRequest,
        )
        self.ListenForEvent(
            config.ModName,
            config.ClientSystemName,
            "FireReactApplyRequest",
            self,
            self.OnFireReactApplyRequest,
        )
        self._configure_twilight_time()
        self._configure_twilight_weather()
        self._configure_fire_swamp_climate()
        print "[TwilightBossSlice] Naga server system ready"

    def _listen_engine(self, eventName, callback):
        listener = getattr(callback, "im_self", None)
        if listener is None:
            listener = getattr(callback, "__self__", None)
        if listener is None:
            listener = self
        self.ListenForEvent(
            ENGINE_NAMESPACE, ENGINE_SYSTEM, eventName, listener, callback
        )

    def OnLoadServerAddonScriptsAfter(self, _args):
        """Keep custom worldgen server-authoritative on NetEase clients."""
        try:
            result = self._chunk_comp.OpenClientChunkGeneration(False)
            self._entry_trace(
                "worldgen.client_chunk_generation.disabled",
                result=bool(result),
            )
            if result:
                print (
                    "[TwilightBossSlice] client chunk generation disabled"
                )
            else:
                print (
                    "[TwilightBossSlice] disabling client chunk generation "
                    "returned failure"
                )
        except Exception as error:
            self._entry_trace(
                "worldgen.client_chunk_generation.disable_failed",
                error=str(error),
            )
            print (
                "[TwilightBossSlice] disabling client chunk generation "
                "failed:",
                error,
            )

    def _configure_twilight_time(self):
        """Match the upstream dimension's fixed twilight time."""
        try:
            dimensionComp = CF.CreateDimension(LEVEL_ID)
            dimensionComp.CreateDimension(config.DIMENSION_ID)
            useLocalTime = dimensionComp.SetUseLocalTime(
                config.DIMENSION_ID, True
            )
            setTime = dimensionComp.SetLocalTimeOfDay(
                config.DIMENSION_ID, config.TWILIGHT_TIME_OF_DAY
            )
            lockCycle = dimensionComp.SetLocalDoDayNightCycle(
                config.DIMENSION_ID, False
            )
            if useLocalTime and setTime and lockCycle:
                print "[TwilightBossSlice] local twilight time configured"
            else:
                print (
                    "[TwilightBossSlice] local twilight time returned failure:",
                    useLocalTime,
                    setTime,
                    lockCycle,
                )
        except Exception as error:
            print (
                "[TwilightBossSlice] failed to configure local twilight time:",
                error,
            )

    def _configure_twilight_weather(self):
        """Own a clear, cycle-disabled baseline for the Twilight dimension."""
        if self._weather_comp is None:
            return False
        try:
            local = self._weather_comp.SetDimensionUseLocalWeather(
                config.DIMENSION_ID, True
            )
            cycle = self._weather_comp.SetDimensionLocalDoWeatherCycle(
                config.DIMENSION_ID, False
            )
            rain = self._weather_comp.SetDimensionLocalRain(
                config.DIMENSION_ID, 0.0, 12000
            )
            thunder = self._weather_comp.SetDimensionLocalThunder(
                config.DIMENSION_ID, 0.0, 12000
            )
            self._ur_ghast_native_weather_active = False
            self._ur_ghast_weather_refresh_tick = self._tick
            return all(result is not False for result in (
                local, cycle, rain, thunder
            ))
        except Exception as error:
            print "[TwilightBossSlice] twilight weather setup failed:", error
            return False

    def _update_ur_ghast_native_weather(self, force=False):
        """Drive dimension-local native thunder from live tantrum ownership."""
        if self._weather_comp is None:
            return False
        active = any(
            state.get("phase") == "tantrum" and not state.get("dying")
            for state in self._ur_ghasts.values()
        )
        changed = active != bool(self._ur_ghast_native_weather_active)
        refresh = active and self._tick >= int(
            self._ur_ghast_weather_refresh_tick
        )
        if not force and not changed and not refresh:
            return True
        try:
            localResult = self._weather_comp.SetDimensionUseLocalWeather(
                config.DIMENSION_ID, True
            )
            cycleResult = self._weather_comp.SetDimensionLocalDoWeatherCycle(
                config.DIMENSION_ID, False
            )
            levels = ur_ghast_effect_logic.native_weather_levels(active)
            rainResult = self._weather_comp.SetDimensionLocalRain(
                config.DIMENSION_ID, levels["rain"], 12000
            )
            thunderResult = self._weather_comp.SetDimensionLocalThunder(
                config.DIMENSION_ID, levels["thunder"], 12000
            )
            self._entry_trace(
                "ur_ghast.weather_write",
                active=bool(active),
                changed=bool(changed),
                refresh=bool(refresh),
                rainLevel=float(levels["rain"]),
                thunderLevel=float(levels["thunder"]),
                localResult=localResult is not False,
                cycleResult=cycleResult is not False,
                rainResult=rainResult is not False,
                thunderResult=thunderResult is not False,
            )
            if any(result is False for result in (
                localResult, cycleResult, rainResult, thunderResult
            )):
                return False
            self._ur_ghast_native_weather_active = active
            self._ur_ghast_weather_refresh_tick = self._tick + 200
            return True
        except Exception as error:
            print "[TwilightBossSlice] Ur-Ghast weather update failed:", error
            return False

    def _configure_fire_swamp_climate(self):
        """Keep upstream Fire Swamp humidity without enabling precipitation."""
        try:
            configured = self._biome_comp.SetBiomeInfo(
                "dm33027004_swampland_mutated",
                (0.0, 0.01),
                1.0,
                0.4,
                False,
            )
            if not configured:
                print "[TwilightBossSlice] Fire Swamp climate returned failure"
        except Exception as error:
            print "[TwilightBossSlice] Fire Swamp climate failed:", error

    def Destroy(self):
        self._configure_twilight_weather()
        if self._magic_map_dirty:
            self._persist_magic_map_records()
        if self._leaf_decay_state_dirty:
            self._persist_leaf_decay_state()
        self._persist_maze_map_records()
        self._persist_player_progress()
        self._persist_keeping_snapshots()
        for hydraId, state in self._hydras.items():
            self._save_hydra_state(hydraId, state)
        for entityId, state in self._route_mobs.items():
            if state.get("type") == MINOSHROOM_IDENTIFIER:
                self._save_minoshroom_state(entityId, state)
        for request in list(self._pending_portal_entries.values()):
            self._release_portal_area(request)
        self._pending_portal_entries = {}
        self._portal_background_preload_queue = []
        self._portal_background_preload_keys = set()
        self._portal_background_preload_inflight = None
        self._pending_portal_recovery_players = set()
        self._portal_fire_cleanups = []
        if self._ruin_worldgen is not None:
            self._ruin_worldgen.destroy()
        if self._mushroom_worldgen is not None:
            self._mushroom_worldgen.destroy()
        if self._lily_pad_worldgen is not None:
            self._lily_pad_worldgen.destroy()
        if self._enchanted_tree_worldgen is not None:
            self._enchanted_tree_worldgen.destroy()
        for bossId, state in self._bosses.items():
            self._save_naga_state(bossId, state)
            self._destroy_all_segments(state)
        print "[TwilightBossSlice] Naga server system destroyed"

    def _entry_trace(self, event, **fields):
        diagnostics = getattr(self, "_entry_diagnostics", None)
        if diagnostics is None:
            return False
        fields.setdefault("tick", getattr(self, "_tick", None))
        try:
            return diagnostics.write(event, **fields)
        except Exception:
            return False

    def _worldgen_perf_increment(self, name, amount=1):
        counters = getattr(self, "_worldgen_perf_counters", None)
        if counters is None:
            counters = {}
            self._worldgen_perf_counters = counters
        counters[name] = counters.get(name, 0) + int(amount)

    def _worldgen_perf_record_structure(self, structureName):
        self._worldgen_perf_increment("structureEvents")
        name = str(structureName or "")
        counts = getattr(self, "_worldgen_perf_structure_counts", None)
        if counts is None:
            counts = {}
            self._worldgen_perf_structure_counts = counts
        counts[name] = counts.get(name, 0) + 1
        if name.startswith("tf_slice:ruin_landmark_surface_"):
            self._worldgen_perf_increment("surfaceLandmarkEvents")

    def _worldgen_perf_snapshot(self):
        return {
            "counters": dict(
                getattr(self, "_worldgen_perf_counters", {})
            ),
            "structures": dict(
                getattr(self, "_worldgen_perf_structure_counts", {})
            ),
        }

    def _worldgen_perf_delta(self, start):
        start = start or {}
        current = self._worldgen_perf_snapshot()
        result = {}
        for section in ("counters", "structures"):
            before = start.get(section, {})
            result[section] = dict(
                (name, value - before.get(name, 0))
                for name, value in current[section].items()
                if value - before.get(name, 0)
            )
        return result

    def _notify(self, playerId, message, color="GREEN"):
        # NetEase 3.8 still rejects SetNotifyMsg with
        # ``show_tip_message message is not string`` even after converting
        # Python 2 unicode to UTF-8 str.  It is cosmetic and shares the UI
        # thread that disappears immediately before the current hard exit, so
        # keep the notice in the durable trace and do not call the native API.
        self._entry_trace(
            "notify.native_tip_skipped",
            playerId=playerId,
            message=message,
            messageType=type(message).__name__,
            color=color,
        )
        try:
            print (
                "[TwilightBossSlice] notify skipped:",
                playerId,
                repr(message),
                color,
            )
        except Exception:
            pass

    def _notify_lines(self, playerId, messages, color="GREEN"):
        for message in messages or []:
            self._notify(playerId, message, color)

    @staticmethod
    def _clean_return_point(value):
        if not isinstance(value, dict):
            return None
        try:
            dimensionId = int(value.get("dimensionId"))
            pos = value.get("pos")
            cleaned = {
                "dimensionId": dimensionId,
                "pos": (
                    float(pos[0]),
                    float(pos[1]),
                    float(pos[2]),
                ),
            }
            portalOrigin = value.get("portalOrigin")
            if portalOrigin is not None:
                cleaned["portalOrigin"] = [
                    int(portalOrigin[0]),
                    int(portalOrigin[1]),
                    int(portalOrigin[2]),
                ]
            return cleaned
        except (IndexError, TypeError, ValueError):
            return None

    def _load_player_progress(self):
        value = None
        try:
            value = self._progress_extra.GetExtraData(
                config.PLAYER_PROGRESS_KEY
            )
        except Exception as error:
            print "[TwilightBossSlice] progress load failed:", error
            value = None
        if not isinstance(value, dict):
            for legacyKey in config.LEGACY_PLAYER_PROGRESS_KEYS:
                try:
                    value = self._progress_extra.GetExtraData(legacyKey)
                except Exception:
                    value = None
                if isinstance(value, dict):
                    break
        if not isinstance(value, dict):
            return {}
        cleaned = {}
        for playerId, objectives in value.items():
            if not isinstance(objectives, dict):
                continue
            migrated = route_progression_logic.migrate_progress(objectives)
            cleaned[str(playerId)] = migrated
        if cleaned:
            # Save immediately so an old world is upgraded before the next
            # crash or clean shutdown.  The old key is intentionally retained.
            try:
                self._progress_extra.SetExtraData(
                    config.PLAYER_PROGRESS_KEY,
                    copy.deepcopy(cleaned),
                    False,
                )
                self._progress_extra.SaveExtraData()
            except Exception:
                pass
        return cleaned

    def _persist_player_progress(self):
        try:
            self._progress_extra.SetExtraData(
                config.PLAYER_PROGRESS_KEY,
                copy.deepcopy(self._player_progress),
                False,
            )
            return bool(self._progress_extra.SaveExtraData())
        except Exception as error:
            print "[TwilightBossSlice] progress save failed:", error
            return False

    def _load_persistent_leaf_positions(self):
        try:
            value = self._progress_extra.GetExtraData(
                config.LEAF_DECAY_PERSISTENT_POSITIONS_KEY
            )
        except Exception as error:
            print "[TwilightBossSlice] persistent leaves load failed:", error
            return set()
        if not isinstance(value, (tuple, list)):
            return set()
        cleaned = set()
        for key in value:
            if leaf_decay_logic.parse_position_key(key) is not None:
                cleaned.add(str(key))
        return cleaned

    def _persist_leaf_decay_state(self):
        try:
            self._progress_extra.SetExtraData(
                config.LEAF_DECAY_PERSISTENT_POSITIONS_KEY,
                sorted(self._persistent_leaf_positions),
                False,
            )
            saved = bool(self._progress_extra.SaveExtraData())
            if saved:
                self._leaf_decay_state_dirty = False
            return saved
        except Exception as error:
            print "[TwilightBossSlice] persistent leaves save failed:", error
            return False

    def _discard_persistent_leaf(self, dimensionId, position):
        key = leaf_decay_logic.position_key(dimensionId, position)
        if key not in self._persistent_leaf_positions:
            return False
        self._persistent_leaf_positions.discard(key)
        self._leaf_decay_bridge_propagated.discard(key)
        self._leaf_decay_state_dirty = True
        return True

    def _progress_for_player(self, playerId):
        return self._player_progress.setdefault(
            str(playerId), route_progression_logic.default_progress()
        )

    @staticmethod
    def _canonical_progress_name(objective):
        return {
            "tf_naga_defeated": "naga_defeated",
            "tf_lich_defeated": "lich_defeated",
            "tf_minoshroom_defeated": "minoshroom_defeated",
            "tf_meef_stroganoff_eaten": "meef_stroganoff_eaten",
            "tf_hydra_defeated": "hydra_defeated",
            "tf_trophy_pedestal_activated": "trophy_pedestal_activated",
            "tf_knight_phantoms_defeated": "knight_phantoms_defeated",
            "tf_ghast_trap_activated": "ghast_trap_activated",
            "tf_ur_ghast_defeated": "ur_ghast_defeated",
        }.get(str(objective), str(objective))

    def _has_progress(self, playerId, objective):
        objective = self._canonical_progress_name(objective)
        return int(
            self._progress_for_player(playerId).get(str(objective), 0)
        ) > 0

    def _grant_progress(self, playerId, objective):
        scoreboardObjective = str(objective)
        objective = self._canonical_progress_name(objective)
        progress = self._progress_for_player(playerId)
        if int(progress.get(objective, 0)) > 0:
            return False
        progress[objective] = 1
        self._persist_player_progress()
        try:
            commandComp = CF.CreateCommand(LEVEL_ID)
            try:
                playerName = CF.CreateName(playerId).GetName()
            except Exception:
                playerName = str(playerId)
            commandComp.SetCommand(
                "/scoreboard objectives add %s dummy" % scoreboardObjective
            )
            commandComp.SetCommand(
                "/scoreboard players set @a[name=\"%s\"] %s 1"
                % (str(playerName), scoreboardObjective)
            )
        except Exception:
            pass
        return True

    def _load_keeping_snapshots(self):
        try:
            value = self._progress_extra.GetExtraData(
                config.KEEPING_CHARM_SNAPSHOTS_KEY
            )
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _persist_keeping_snapshots(self):
        try:
            self._progress_extra.SetExtraData(
                config.KEEPING_CHARM_SNAPSHOTS_KEY,
                copy.deepcopy(self._keeping_snapshots),
                False,
            )
            return bool(self._progress_extra.SaveExtraData())
        except Exception as error:
            print "[TwilightBossSlice] keeping snapshot save failed:", error
            return False

    def _load_portal_return_points(self):
        try:
            value = self._portal_extra.GetExtraData(
                config.PORTAL_RETURN_POINTS_KEY
            )
        except Exception as error:
            print "[TwilightBossSlice] portal return data load failed:", error
            value = None
        if not isinstance(value, dict):
            return {}
        cleaned = {}
        for rawPlayerId, rawPoint in value.items():
            point = self._clean_return_point(rawPoint)
            if point is not None:
                cleaned[str(rawPlayerId)] = point
        return cleaned

    def _persist_portal_return_points(self):
        payload = {}
        for rawPlayerId, rawPoint in self._return_points.items():
            point = self._clean_return_point(rawPoint)
            if point is None:
                continue
            payload[str(rawPlayerId)] = {
                "dimensionId": point["dimensionId"],
                "pos": list(point["pos"]),
            }
            if point.get("portalOrigin") is not None:
                payload[str(rawPlayerId)]["portalOrigin"] = list(
                    point["portalOrigin"]
                )
        try:
            self._portal_extra.SetExtraData(
                config.PORTAL_RETURN_POINTS_KEY,
                payload,
                False,
            )
            return bool(self._portal_extra.SaveExtraData())
        except Exception as error:
            print "[TwilightBossSlice] portal return data save failed:", error
            return False

    def _return_point_for_player(self, playerId):
        point = self._return_points.get(playerId)
        if point is None:
            point = self._return_points.get(str(playerId))
        return self._clean_return_point(point)

    def _store_return_point(self, playerId, point, portal_origin=None):
        cleaned = self._clean_return_point(point)
        if cleaned is None:
            return False
        if portal_origin is not None:
            try:
                cleaned["portalOrigin"] = [
                    int(portal_origin[0]),
                    int(portal_origin[1]),
                    int(portal_origin[2]),
                ]
            except (IndexError, TypeError, ValueError):
                return False
        self._return_points[str(playerId)] = cleaned
        return self._persist_portal_return_points()

    def _load_magic_map_sectors(self):
        try:
            value = self._magic_map_extra.GetExtraData(
                config.MAGIC_MAP_SECTORS_KEY
            )
        except Exception as error:
            print "[TwilightBossSlice] magic map data load failed:", error
            value = None
        if not isinstance(value, dict):
            return {}
        cleaned = {}
        for rawKey, rawSector in value.items():
            key = str(rawKey)
            parts = key.split(",")
            if len(parts) != 2 or not isinstance(rawSector, dict):
                continue
            try:
                centerX = int(parts[0])
                centerZ = int(parts[1])
                magic_map_logic.encode_extra_id(centerX, centerZ)
            except (TypeError, ValueError):
                continue
            landmarks = magic_map_logic.merge_landmarks(
                rawSector.get("landmarks"),
                (),
            )
            biomes = magic_map_logic.normalize_biome_cells(
                rawSector.get("biomes")
            )
            cleaned[magic_map_logic.sector_key(centerX, centerZ)] = {
                "landmarks": landmarks,
                "biomes": biomes,
            }
        return cleaned

    def _persist_magic_map_sectors(self):
        try:
            self._magic_map_extra.SetExtraData(
                config.MAGIC_MAP_SECTORS_KEY,
                copy.deepcopy(self._magic_map_sectors),
                False,
            )
            return self._magic_map_extra.SaveExtraData()
        except Exception as error:
            print "[TwilightBossSlice] magic map data save failed:", error
            return False

    def _load_magic_map_records(self):
        try:
            value = self._magic_map_extra.GetExtraData(
                config.MAGIC_MAP_RECORDS_KEY
            )
        except Exception as error:
            print "[TwilightBossSlice] magic map v2 load failed:", error
            value = None
        if not isinstance(value, dict):
            return {}, 1
        rawMaps = value.get("maps")
        if not isinstance(rawMaps, dict):
            return {}, 1
        records = {}
        highestId = 0
        for rawMapId, rawRecord in rawMaps.items():
            if not isinstance(rawRecord, dict):
                continue
            try:
                mapId = int(rawMapId)
                center = rawRecord.get("center")
                centerX = int(center[0])
                centerZ = int(center[1])
                magic_map_logic.encode_extra_id(
                    centerX,
                    centerZ,
                    map_id=mapId,
                )
            except (IndexError, TypeError, ValueError):
                continue
            records[str(mapId)] = {
                "center": [centerX, centerZ],
                "landmarks": magic_map_logic.merge_landmarks(
                    rawRecord.get("landmarks"),
                    (),
                ),
                "biomes": magic_map_logic.decode_biome_pixels(
                    rawRecord.get("biomesPacked", "")
                ),
            }
            highestId = max(highestId, mapId)
        try:
            nextId = max(int(value.get("nextId", 1)), highestId + 1)
        except (TypeError, ValueError):
            nextId = highestId + 1
        return records, max(1, nextId)

    def _persist_magic_map_records(self):
        maps = {}
        for rawMapId, record in self._magic_map_records.items():
            if not isinstance(record, dict):
                continue
            maps[str(rawMapId)] = {
                "center": list(record.get("center", ()))[:2],
                "landmarks": magic_map_logic.merge_landmarks(
                    record.get("landmarks"),
                    (),
                ),
                "biomesPacked": magic_map_logic.encode_biome_pixels(
                    record.get("biomes")
                ),
            }
        payload = {
            "schemaVersion": 2,
            "nextId": int(self._magic_map_next_id),
            "maps": maps,
        }
        try:
            self._magic_map_extra.SetExtraData(
                config.MAGIC_MAP_RECORDS_KEY,
                payload,
                False,
            )
            saved = bool(self._magic_map_extra.SaveExtraData())
            if saved:
                self._magic_map_dirty = False
            return saved
        except Exception as error:
            print "[TwilightBossSlice] magic map v2 save failed:", error
            return False

    def _load_maze_map_records(self):
        try:
            value = self._magic_map_extra.GetExtraData(
                config.MAZE_MAP_RECORDS_KEY
            )
        except Exception as error:
            print "[TwilightBossSlice] maze map load failed:", error
            value = None
        if not isinstance(value, dict):
            return {}
        records = {}
        for extraId, raw in value.items():
            identity = maze_map_logic.decode_identity(extraId)
            if identity is None or not isinstance(raw, dict):
                continue
            try:
                record = maze_map_logic.create_record(
                    identity[0],
                    (identity[1], identity[2], identity[3]),
                    identity[2],
                )
                record["dimensionId"] = int(
                    raw.get("dimensionId", config.DIMENSION_ID)
                )
                record["structureOrigin"] = [
                    int(raw["structureOrigin"][0]),
                    int(raw["structureOrigin"][1]),
                ]
                record["passageRuns"] = [
                    [int(run[0]), int(run[1]), int(run[2])]
                    for run in raw.get("passageRuns", ())
                    if isinstance(run, (list, tuple)) and len(run) == 3
                ]
                record["exploredCells"] = maze_map_logic.normalize_explored_cells(
                    raw.get("exploredCells", {})
                )
            except (IndexError, KeyError, TypeError, ValueError):
                continue
            records[str(extraId)] = record
        return records

    def _persist_maze_map_records(self):
        payload = {}
        for extraId, record in self._maze_map_records.items():
            if maze_map_logic.decode_identity(extraId) is None:
                continue
            payload[str(extraId)] = {
                "schemaVersion": 1,
                "mapKind": "maze",
                "labyrinthId": str(record.get("labyrinthId", "")),
                "yCenter": int(record.get("yCenter", 0)),
                "verticalOffset": int(record.get("verticalOffset", 0)),
                "dimensionId": int(
                    record.get("dimensionId", config.DIMENSION_ID)
                ),
                "structureOrigin": list(
                    record.get("structureOrigin", (0, 0))
                )[:2],
                "passageRuns": [
                    list(run)[:3]
                    for run in record.get("passageRuns", ())
                ],
                "exploredCells": maze_map_logic.normalize_explored_cells(
                    record.get("exploredCells", {})
                ),
            }
        try:
            if self._magic_map_extra.SetExtraData(
                config.MAZE_MAP_RECORDS_KEY, payload, False,
            ) is False:
                return False
            saved = bool(self._magic_map_extra.SaveExtraData())
            if saved:
                self._maze_map_dirty = False
            return saved
        except Exception as error:
            print "[TwilightBossSlice] maze map save failed:", error
            return False

    def _allocate_magic_map(self, centerX, centerZ, seed=None):
        mapId = int(self._magic_map_next_id)
        self._magic_map_next_id = mapId + 1
        seed = seed if isinstance(seed, dict) else {}
        self._magic_map_records[str(mapId)] = {
            "center": [int(centerX), int(centerZ)],
            "landmarks": magic_map_logic.merge_landmarks(
                seed.get("landmarks"),
                (),
            ),
            "biomes": magic_map_logic.normalize_biome_cells(
                seed.get("biomes")
            ),
        }
        self._magic_map_dirty = True
        return mapId

    def _ensure_magic_map_record(self, mapId, centerX, centerZ):
        key = str(int(mapId))
        record = self._magic_map_records.get(key)
        if isinstance(record, dict):
            if record.get("center") == [int(centerX), int(centerZ)]:
                return record
            return None
        self._magic_map_records[key] = {
            "center": [int(centerX), int(centerZ)],
            "landmarks": {},
            "biomes": {},
        }
        self._magic_map_next_id = max(
            int(self._magic_map_next_id),
            int(mapId) + 1,
        )
        self._magic_map_dirty = True
        return self._magic_map_records[key]

    @staticmethod
    def _hand_pos_type(hand):
        itemPos = serverApi.GetMinecraftEnum().ItemPosType
        if hand == "offhand":
            return itemPos.OFFHAND
        return itemPos.CARRIED

    def _hand_item(self, playerId, hand):
        self._native_item_diag_sequence += 1
        sequence = self._native_item_diag_sequence
        trace = native_item_diagnostics.should_trace(sequence)
        started = time.time()
        if trace:
            print native_item_diagnostics.begin_line(
                "server", sequence, hand, self._tick
            )
        try:
            itemComp = CF.CreateItem(playerId)
            posType = self._hand_pos_type(hand)
            # extraId is part of the ordinary item dictionary.  Requesting
            # user data here forces a native registry expansion and produced
            # BlockTypeRegistry lookups for every held item during polling.
            item = itemComp.GetPlayerItem(posType, 0, False)
        except Exception as error:
            if trace:
                print native_item_diagnostics.end_line(
                    "server",
                    sequence,
                    hand,
                    self._tick,
                    (time.time() - started) * 1000.0,
                    error=error,
                )
            return None
        if trace:
            print native_item_diagnostics.end_line(
                "server",
                sequence,
                hand,
                self._tick,
                (time.time() - started) * 1000.0,
                item=item,
            )
        return item

    def _carried_item(self, playerId):
        return self._hand_item(playerId, "carried")

    def _offhand_item(self, playerId):
        return self._hand_item(playerId, "offhand")

    def _set_hand_item(self, playerId, hand, item):
        try:
            itemComp = CF.CreateItem(playerId)
            posType = self._hand_pos_type(hand)
            result = itemComp.SetPlayerAllItems(
                {(posType, 0): copy.deepcopy(item)}
            )
            return bool(result.get((posType, 0), False))
        except Exception as error:
            print "[TwilightBossSlice] carried item update failed:", error
            return False

    def _set_carried_item(self, playerId, item):
        return self._set_hand_item(playerId, "carried", item)

    def _magic_map_hand_item(
        self,
        playerId,
        include_blank=False,
        preferred_item=None,
    ):
        def eligible(item):
            if self._is_magic_map_stack(item):
                return True
            return bool(
                include_blank
                and portal_logic.item_name(item) == config.MAGIC_MAP_ITEM
            )

        return magic_map_logic.select_held_item(
            self._carried_item(playerId),
            self._offhand_item(playerId),
            eligible,
            preferred_item,
        )

    def _is_creative(self, playerId):
        try:
            return int(
                CF.CreateGame(LEVEL_ID).GetPlayerGameType(playerId)
            ) == 1
        except Exception:
            return False

    def _is_invulnerable_player(self, playerId):
        try:
            return int(
                CF.CreateGame(LEVEL_ID).GetPlayerGameType(playerId)
            ) in (1, 3, 6)
        except Exception:
            return False

    def _filled_magic_map_item(self, extraId):
        return {
            "itemName": config.FILLED_MAGIC_MAP_ITEM,
            "count": 1,
            "auxValue": 0,
            "extraId": str(extraId),
        }

    @staticmethod
    def _filled_maze_map_item(extraId):
        return {
            "itemName": config.FILLED_MAZE_MAP_ITEM,
            "count": 1,
            "auxValue": 0,
            "extraId": str(extraId),
        }

    @staticmethod
    def _is_maze_map_stack(item):
        return bool(
            isinstance(item, dict)
            and portal_logic.item_name(item) == config.FILLED_MAZE_MAP_ITEM
            and maze_map_logic.decode_identity(item.get("extraId"))
            is not None
        )

    def _maze_map_hand_item(self, playerId, preferred_item=None):
        def eligible(item):
            name = portal_logic.item_name(item or {})
            return bool(
                name == config.MAZE_MAP_ITEM
                or self._is_maze_map_stack(item)
            )

        return magic_map_logic.select_held_item(
            self._carried_item(playerId),
            self._offhand_item(playerId),
            eligible,
            preferred_item,
        )

    def _held_map_hand_item(self, playerId):
        return magic_map_logic.select_held_item(
            self._carried_item(playerId),
            self._offhand_item(playerId),
            lambda item: self._is_magic_map_stack(item) or self._is_maze_map_stack(item),
        )

    def _replace_blank_maze_map(self, playerId, hand, current, extraId):
        filled = self._filled_maze_map_item(extraId)
        count = max(1, int(current.get("count", 1)))
        if count == 1:
            return self._set_hand_item(playerId, hand, filled)
        remainder = copy.deepcopy(current)
        remainder["count"] = count - 1
        if not self._set_hand_item(playerId, hand, remainder):
            return False
        if self._deliver_item(playerId, filled):
            return True
        self._set_hand_item(playerId, hand, current)
        return False

    def _create_maze_map(self, playerId, hand, item, position):
        if self._ruin_worldgen is None:
            return False
        context = self._ruin_worldgen.labyrinth_map_context(position)
        if context is None:
            self._notify(
                playerId,
                u"只能在地下迷宫范围内制作迷宫地图。",
                "RED",
            )
            return False
        center = context["center"]
        record = maze_map_logic.create_record(
            context["labyrinthId"],
            center,
            position[1],
        )
        record["dimensionId"] = config.DIMENSION_ID
        record["structureOrigin"] = list(context["structureOrigin"])
        record["passageRuns"] = list(context["passageRuns"])
        extraId = maze_map_logic.encode_identity(
            record["labyrinthId"],
            record["centerX"],
            record["yCenter"],
            record["centerZ"],
        )
        if not self._replace_blank_maze_map(
            playerId,
            hand,
            item,
            extraId,
        ):
            return False
        # Maps made at the same place share their existing exploration record.
        self._maze_map_records.setdefault(extraId, record)
        self._maze_map_dirty = True
        self._persist_maze_map_records()
        self._notify(
            playerId,
            u"迷宫地图已吸附到当前楼层。",
            "AQUA",
        )
        return self._send_maze_map_snapshot(playerId, extraId, position)

    def _send_maze_map_snapshot(self, playerId, extraId, position=None, openScreen=True):
        record = self._maze_map_records.get(str(extraId))
        if not isinstance(record, dict):
            return False
        if self._get_dimension(playerId) != record.get("dimensionId", config.DIMENSION_ID):
            return False
        if position is None:
            position = self._get_foot_pos(playerId)
        if position is None:
            return False
        if maze_map_logic.explore(
            record, position,
            lambda pos: self._get_block(pos, record.get("dimensionId", config.DIMENSION_ID)),
        ):
            self._maze_map_dirty = True
            record["_revision"] = int(record.get("_revision", 0)) + 1
        state = {"mazeMapId": str(extraId), "mazeRevision": int(record.get("_revision", 0))}
        if not openScreen and self._magic_map_delta_states.get(playerId) == state:
            return True
        snapshot = maze_map_logic.build_snapshot(
            record,
            record.get("passageRuns", ()),
            record.get("structureOrigin", (0, 0)),
            position,
        )
        snapshot["openScreen"] = bool(openScreen)
        self.NotifyToClient(playerId, "MagicMapSnapshot", snapshot)
        self._magic_map_delta_states[playerId] = state
        return True

    def _is_magic_map_stack(self, item):
        if not isinstance(item, dict):
            return False
        itemName = portal_logic.item_name(item)
        if itemName == config.FILLED_MAGIC_MAP_ITEM:
            return True
        if itemName != config.LEGACY_NATIVE_MAGIC_MAP_ITEM:
            return False
        return (
            magic_map_logic.decode_map_identity(item.get("extraId"))
            is not None
        )

    def _migrate_legacy_native_magic_map(
        self,
        playerId,
        item,
        hand="carried",
    ):
        if (
            portal_logic.item_name(item)
            != config.LEGACY_NATIVE_MAGIC_MAP_ITEM
        ):
            return item
        extraId = item.get("extraId")
        if magic_map_logic.decode_map_identity(extraId) is None:
            return None
        migrated = self._filled_magic_map_item(extraId)
        migrated["count"] = max(1, int(item.get("count", 1)))
        if not self._set_hand_item(playerId, hand, migrated):
            return None
        return migrated

    def _deliver_item(self, playerId, item):
        try:
            itemComp = CF.CreateItem(playerId)
            if itemComp.SpawnItemToPlayerInv(
                copy.deepcopy(item),
                playerId,
                -1,
            ):
                return True
        except Exception:
            pass
        position = self._get_foot_pos(playerId)
        dimensionId = self._get_dimension(playerId)
        if position is None or dimensionId is None:
            return False
        try:
            return bool(
                self.CreateEngineItemEntity(
                    copy.deepcopy(item),
                    int(dimensionId),
                    position,
                )
            )
        except Exception as error:
            print "[TwilightBossSlice] magic map item drop failed:", error
            return False

    def _replace_blank_magic_map(
        self,
        playerId,
        current,
        extraId,
        hand="carried",
    ):
        filledMap = self._filled_magic_map_item(extraId)
        count = max(1, int(current.get("count", 1)))
        if count == 1:
            return self._set_hand_item(playerId, hand, filledMap)
        remainder = copy.deepcopy(current)
        remainder["count"] = count - 1
        if not self._set_hand_item(playerId, hand, remainder):
            return False
        if self._deliver_item(playerId, filledMap):
            return True
        self._set_hand_item(playerId, hand, current)
        return False

    def _queue_blank_magic_map_use(self, playerId, hand="carried"):
        try:
            CF.CreateGame(LEVEL_ID).AddTimer(
                0.05,
                self._complete_blank_magic_map_use,
                {"playerId": playerId, "hand": hand},
            )
            return True
        except Exception as error:
            print "[TwilightBossSlice] magic map timer failed:", error
            self._notify(
                playerId,
                "魔法地图暂时无法记录，请重试。",
                "RED",
            )
            return False

    def _complete_blank_magic_map_use(self, data):
        playerId = data.get("playerId")
        if playerId is None:
            return
        hand = data.get("hand") or "carried"
        item = self._hand_item(playerId, hand) or {}
        position = self._get_foot_pos(playerId)
        if (
            self._get_dimension(playerId) != config.DIMENSION_ID
            or position is None
            or portal_logic.item_name(item) != config.MAGIC_MAP_ITEM
        ):
            return
        centerX, centerZ = magic_map_logic.map_center(
            position[0],
            position[2],
        )
        mapId = self._allocate_magic_map(centerX, centerZ)
        extraId = magic_map_logic.encode_extra_id(
            centerX,
            centerZ,
            map_id=mapId,
        )
        if self._replace_blank_magic_map(
            playerId,
            item,
            extraId,
            hand,
        ):
            self._persist_magic_map_records()
            self._notify(
                playerId,
                "魔法地图记录了这一片暮色森林。",
                "AQUA",
            )
        else:
            self._notify(
                playerId,
                "无法生成已填充的魔法地图。",
                "RED",
            )

    def _queue_filled_magic_map_open(self, playerId, hand=None):
        try:
            CF.CreateGame(LEVEL_ID).AddTimer(
                0.05,
                self._complete_filled_magic_map_open,
                {"playerId": playerId, "hand": hand},
            )
            return True
        except Exception as error:
            print "[TwilightBossSlice] filled magic map timer failed:", error
            return False

    def _complete_filled_magic_map_open(self, data):
        playerId = data.get("playerId")
        if playerId is not None:
            self._send_magic_map_snapshot(
                playerId,
                hand=data.get("hand"),
            )

    def _initialize_filled_magic_map(
        self,
        playerId,
        position,
        hand="carried",
    ):
        centerX, centerZ = magic_map_logic.map_center(
            position[0],
            position[2],
        )
        mapId = self._allocate_magic_map(centerX, centerZ)
        extraId = magic_map_logic.encode_extra_id(
            centerX,
            centerZ,
            map_id=mapId,
        )
        if not self._set_filled_magic_map_extra_id(
            playerId,
            extraId,
            hand,
        ):
            self._magic_map_records.pop(str(mapId), None)
            return None
        self._persist_magic_map_records()
        return mapId, centerX, centerZ

    def _set_filled_magic_map_extra_id(
        self,
        playerId,
        extraId,
        hand="carried",
    ):
        try:
            if not self._set_hand_item(
                playerId,
                hand,
                self._filled_magic_map_item(extraId),
            ):
                return False
        except Exception as error:
            print "[TwilightBossSlice] magic map init failed:", error
            return False
        return True

    def _magic_map_identity(
        self,
        playerId,
        item,
        position,
        hand="carried",
    ):
        rawExtraId = item.get("extraId")
        if rawExtraId in (None, ""):
            return self._initialize_filled_magic_map(
                playerId,
                position,
                hand,
            )
        identity = magic_map_logic.decode_map_identity(rawExtraId)
        if identity is None:
            return None
        mapId, centerX, centerZ = identity
        if mapId is None:
            legacy = self._magic_map_sectors.get(
                magic_map_logic.sector_key(centerX, centerZ),
                {},
            )
            mapId = self._allocate_magic_map(
                centerX,
                centerZ,
                legacy,
            )
            extraId = magic_map_logic.encode_extra_id(
                centerX,
                centerZ,
                map_id=mapId,
            )
            if not self._set_filled_magic_map_extra_id(
                playerId,
                extraId,
                hand,
            ):
                self._magic_map_records.pop(str(mapId), None)
                return None
            self._persist_magic_map_records()
        elif magic_map_logic.extra_id_version(rawExtraId) != 3:
            extraId = magic_map_logic.encode_extra_id(
                centerX,
                centerZ,
                map_id=mapId,
            )
            if not self._set_filled_magic_map_extra_id(
                playerId,
                extraId,
                hand,
            ):
                return None
        if self._ensure_magic_map_record(mapId, centerX, centerZ) is None:
            return None
        return mapId, centerX, centerZ

    def _magic_map_record(self, mapId, centerX, centerZ):
        return self._ensure_magic_map_record(mapId, centerX, centerZ)

    def _magic_map_record_landmarks(self, mapId, centerX, centerZ):
        record = self._magic_map_record(mapId, centerX, centerZ)
        if record is None:
            return {}
        landmarks = record.get("landmarks")
        if not isinstance(landmarks, dict):
            landmarks = {}
            record["landmarks"] = landmarks
        return landmarks

    def _magic_map_record_biomes(self, mapId, centerX, centerZ):
        record = self._magic_map_record(mapId, centerX, centerZ)
        if record is None:
            return {}
        biomes = magic_map_logic.normalize_biome_cells(
            record.get("biomes")
        )
        record["biomes"] = biomes
        return biomes

    def _discover_magic_map_biomes(
        self,
        playerId,
        position,
        mapId,
        centerX,
        centerZ,
    ):
        current = self._magic_map_record_biomes(
            mapId,
            centerX,
            centerZ,
        )
        updated = dict(current)
        changedPixels = {}
        viewerCell = (
            int(
                math.floor(
                    (float(position[0]) - float(centerX))
                    / float(magic_map_logic.MAP_CELL_BLOCKS)
                )
            )
            + magic_map_logic.MAP_GRID_SIZE // 2,
            int(
                math.floor(
                    (float(position[2]) - float(centerZ))
                    / float(magic_map_logic.MAP_CELL_BLOCKS)
                )
            )
            + magic_map_logic.MAP_GRID_SIZE // 2,
        )
        frontier = self._magic_map_discovery_frontiers.get(playerId)
        if (
            not isinstance(frontier, dict)
            or frontier.get("mapId") != int(mapId)
            or frontier.get("viewerCell") != viewerCell
        ):
            frontier = {
                "mapId": int(mapId),
                "viewerCell": viewerCell,
                "candidates": magic_map_logic.discovery_cell_samples(
                    position[0],
                    position[2],
                    centerX,
                    centerZ,
                    current.keys(),
                    config.MAGIC_MAP_DISCOVERY_RADIUS,
                    None,
                ),
                "cursor": 0,
            }
            self._magic_map_discovery_frontiers[playerId] = frontier
        samples, cursor = magic_map_logic.discovery_frontier_batch(
            frontier.get("candidates", ()),
            current.keys(),
            frontier.get("cursor", 0),
            config.MAGIC_MAP_SAMPLE_BUDGET,
        )
        frontier["cursor"] = cursor
        for index, blockX, blockZ in samples:
            biomeKey = self._magic_map_biome_key(blockX, blockZ)
            if biomeKey != "stream":
                for neighborX, neighborZ in (
                    (blockX + 4, blockZ),
                    (blockX, blockZ + 4),
                ):
                    neighborKey = self._magic_map_biome_key(
                        neighborX,
                        neighborZ,
                    )
                    if neighborKey == "stream":
                        biomeKey = neighborKey
                        break
            if biomeKey is not None:
                updated[str(index)] = biomeKey
                changedPixels[str(index)] = biomeKey
        return current, updated, changedPixels

    def _magic_map_biome_key(self, blockX, blockZ):
        try:
            identifier = self._biome_comp.GetBiomeName(
                (blockX, 0, blockZ),
                config.DIMENSION_ID,
            )
        except Exception:
            identifier = None
        identifier = str(identifier or "")
        biome = BIOMES_BY_IDENTIFIER.get(identifier)
        if biome is None and ":" in identifier:
            biome = BIOMES_BY_IDENTIFIER.get(
                identifier.split(":", 1)[1]
            )
        if biome is not None:
            return biome["key"]
        return magic_map_logic.UNKNOWN_BIOME_KEY

    def _discover_magic_map(
        self,
        playerId,
        position,
        mapId,
        centerX,
        centerZ,
        discoverLandmarks=True,
        discoverBiomes=True,
    ):
        if not magic_map_logic.is_inside_map(
            position[0],
            position[2],
            centerX,
            centerZ,
        ):
            return False
        changed = False
        landmarksChanged = False
        record = self._magic_map_record(mapId, centerX, centerZ)
        if record is None:
            return False
        current = self._magic_map_record_landmarks(
            mapId,
            centerX,
            centerZ,
        )
        if discoverLandmarks and self._ruin_worldgen is not None:
            candidates = self._ruin_worldgen.magic_map_landmarks_near(
                position,
                centerX,
                centerZ,
                config.MAGIC_MAP_DISCOVERY_RADIUS,
            )
            discovered = magic_map_logic.discover_landmarks(
                candidates,
                position[0],
                position[2],
                centerX,
                centerZ,
                config.MAGIC_MAP_DISCOVERY_RADIUS,
            )
            merged = magic_map_logic.merge_landmarks(current, discovered)
            if merged != current:
                record["landmarks"] = merged
                changed = True
                landmarksChanged = True
        changedPixels = {}
        if discoverBiomes:
            (
                currentBiomes,
                updatedBiomes,
                changedPixels,
            ) = self._discover_magic_map_biomes(
                playerId,
                position,
                mapId,
                centerX,
                centerZ,
            )
            if updatedBiomes != currentBiomes:
                record["biomes"] = updatedBiomes
                changed = True
        if not changed:
            return False
        self._magic_map_dirty = True
        return {
            "biomes": changedPixels,
            "landmarks": landmarksChanged,
        }

    def _send_magic_map_delta(
        self,
        playerId,
        position,
        mapId,
        centerX,
        centerZ,
        changes,
        includePlayers=True,
    ):
        players = None
        delta_state = self._magic_map_delta_states.get(playerId)
        if includePlayers:
            players = self._magic_map_player_markers(mapId, playerId)
            delta_state = (int(mapId), repr(players))
        has_map_changes = bool(
            changes.get("biomes") or changes.get("landmarks")
        )
        if (
            not has_map_changes
            and (
                not includePlayers
                or self._magic_map_delta_states.get(playerId) == delta_state
            )
        ):
            return False
        if includePlayers:
            self._magic_map_delta_states[playerId] = delta_state
        delta = {
            "schemaVersion": magic_map_logic.SNAPSHOT_SCHEMA_VERSION,
            "dimensionId": config.DIMENSION_ID,
            "mapId": int(mapId),
            "player": [int(position[0]), int(position[2])],
            "biomeRuns": magic_map_logic.biome_row_runs(
                changes.get("biomes")
            ),
        }
        if includePlayers:
            delta["players"] = players
        if changes.get("landmarks"):
            snapshot = magic_map_logic.build_snapshot(
                centerX,
                centerZ,
                position[0],
                position[2],
                config.DIMENSION_ID,
                self._magic_map_record_landmarks(
                    mapId,
                    centerX,
                    centerZ,
                ),
                {},
                mapId,
            )
            delta["landmarks"] = snapshot["landmarks"]
        self.NotifyToClient(playerId, "MagicMapDelta", delta)
        return True

    def _magic_map_player_markers(self, mapId, ownerId):
        players = []
        for playerId in list(self._known_players):
            if playerId == ownerId:
                continue
            if self._get_dimension(playerId) != config.DIMENSION_ID:
                continue
            hand, item = self._magic_map_hand_item(playerId)
            del hand
            item = item or {}
            identity = magic_map_logic.decode_map_identity(
                item.get("extraId")
            )
            if identity is None or identity[0] is None:
                continue
            if int(identity[0]) != int(mapId):
                continue
            position = self._get_foot_pos(playerId)
            if position is None:
                continue
            try:
                rotation = CF.CreateRot(playerId).GetRot()
                yaw = float(rotation[1])
            except Exception:
                yaw = 0.0
            players.append(
                {
                    "id": str(playerId),
                    "position": [int(position[0]), int(position[2])],
                    "yaw": yaw,
                }
            )
        return magic_map_logic.clean_map_players(players)

    def _send_magic_map_snapshot(
        self,
        playerId,
        openScreen=True,
        hand=None,
    ):
        if self._get_dimension(playerId) != config.DIMENSION_ID:
            self._notify(
                playerId,
                "魔法地图只能在暮色森林中展开。",
                "RED",
            )
            return False
        position = self._get_foot_pos(playerId)
        if hand is None:
            hand, item = self._magic_map_hand_item(playerId)
        else:
            item = self._hand_item(playerId, hand)
        item = item or {}
        if (
            portal_logic.item_name(item)
            == config.LEGACY_NATIVE_MAGIC_MAP_ITEM
        ):
            item = self._migrate_legacy_native_magic_map(
                playerId,
                item,
                hand or "carried",
            )
            if item is None:
                return False
        if (
            position is None
            or not self._is_magic_map_stack(item)
        ):
            return False
        identity = self._magic_map_identity(
            playerId,
            item,
            position,
            hand or "carried",
        )
        if identity is None:
            self._notify(playerId, "这张魔法地图已经损坏。", "RED")
            return False
        mapId, centerX, centerZ = identity
        self._discover_magic_map(
            playerId,
            position,
            mapId,
            centerX,
            centerZ,
        )
        snapshot = magic_map_logic.build_snapshot(
            centerX,
            centerZ,
            position[0],
            position[2],
            config.DIMENSION_ID,
            self._magic_map_record_landmarks(
                mapId,
                centerX,
                centerZ,
            ),
            self._magic_map_record_biomes(
                mapId,
                centerX,
                centerZ,
            ),
            mapId,
            players=self._magic_map_player_markers(
                mapId,
                playerId,
            ),
        )
        snapshot["openScreen"] = bool(openScreen)
        self.NotifyToClient(playerId, "MagicMapSnapshot", snapshot)
        return True

    def _scan_carried_magic_maps(self):
        for playerId in list(self._known_players):
            dimensionId = self._get_dimension(playerId)
            hand, item = self._held_map_hand_item(playerId)
            item = item or {}
            if dimensionId == config.DIMENSION_ID and self._is_maze_map_stack(item):
                self._magic_map_discovery_frontiers.pop(playerId, None)
                transition = magic_map_logic.held_map_transition(
                    self._magic_map_held_states.get(playerId), True, item.get("extraId"),
                )
                self._magic_map_held_states[playerId] = transition["state"]
                if transition["snapshotNeeded"]:
                    self._magic_map_delta_states.pop(playerId, None)
                if transition["heldChanged"]:
                    self.NotifyToClient(playerId, "MagicMapHeldState", {
                        "held": True, "dimensionId": dimensionId, "mapId": item.get("extraId"),
                    })
                self._send_maze_map_snapshot(playerId, item.get("extraId"), openScreen=False)
                continue
            if (
                portal_logic.item_name(item)
                == config.LEGACY_NATIVE_MAGIC_MAP_ITEM
                and self._is_magic_map_stack(item)
            ):
                migrated = self._migrate_legacy_native_magic_map(
                    playerId,
                    item,
                    hand or "carried",
                )
                if migrated is not None:
                    item = migrated
            held = bool(
                dimensionId == config.DIMENSION_ID
                and self._is_magic_map_stack(item)
            )
            previousState = self._magic_map_held_states.get(playerId)
            if not held:
                self._magic_map_discovery_frontiers.pop(playerId, None)
                transition = magic_map_logic.held_map_transition(
                    previousState,
                    False,
                )
                self._magic_map_held_states[playerId] = transition["state"]
                if transition["heldChanged"]:
                    self.NotifyToClient(
                        playerId,
                        "MagicMapHeldState",
                        {
                            "held": False,
                            "dimensionId": dimensionId,
                            "mapId": None,
                        },
                    )
                self._magic_map_delta_states.pop(playerId, None)
                continue
            position = self._get_foot_pos(playerId)
            if position is None:
                self._magic_map_discovery_frontiers.pop(playerId, None)
                transition = magic_map_logic.held_map_transition(
                    previousState,
                    True,
                )
                self._magic_map_held_states[playerId] = transition["state"]
                if transition["heldChanged"]:
                    self.NotifyToClient(
                        playerId,
                        "MagicMapHeldState",
                        {
                            "held": True,
                            "dimensionId": dimensionId,
                            "mapId": None,
                        },
                    )
                continue
            identity = self._magic_map_identity(
                playerId,
                item,
                position,
                hand or "carried",
            )
            if identity is None:
                self._magic_map_discovery_frontiers.pop(playerId, None)
                continue
            mapId, centerX, centerZ = identity
            transition = magic_map_logic.held_map_transition(
                previousState,
                True,
                mapId,
            )
            self._magic_map_held_states[playerId] = transition["state"]
            if transition["heldChanged"]:
                self.NotifyToClient(
                    playerId,
                    "MagicMapHeldState",
                    {
                        "held": True,
                        "dimensionId": dimensionId,
                        "mapId": mapId,
                    },
                )
            if transition["snapshotNeeded"]:
                self._send_magic_map_snapshot(
                    playerId,
                    openScreen=False,
                    hand=hand,
                )
                # The snapshot path already discovers one complete batch and
                # includes it in the payload.  Running discovery again below
                # doubled biome-engine queries and made first hold hitch.
                continue
            changes = {}
            if magic_map_logic.is_inside_map(
                position[0],
                position[2],
                centerX,
                centerZ,
            ):
                changes = self._discover_magic_map(
                    playerId,
                    position,
                    mapId,
                    centerX,
                    centerZ,
                    discoverBiomes=False,
                ) or {}
            self._send_magic_map_delta(
                playerId,
                position,
                mapId,
                centerX,
                centerZ,
                changes,
            )

    def _tick_cached_magic_map_discovery(self):
        """Advance cached biome frontiers without native item queries."""
        for playerId, state in list(self._magic_map_held_states.items()):
            if (
                not isinstance(state, (tuple, list))
                or len(state) < 2
                or not state[0]
                or state[1] is None
                or self._get_dimension(playerId) != config.DIMENSION_ID
            ):
                continue
            try:
                mapId = int(state[1])
            except (TypeError, ValueError):
                continue
            record = self._magic_map_records.get(str(mapId))
            center = record.get("center") if isinstance(record, dict) else None
            if not isinstance(center, (tuple, list)) or len(center) < 2:
                continue
            position = self._get_foot_pos(playerId)
            if position is None:
                continue
            centerX, centerZ = int(center[0]), int(center[1])
            changes = self._discover_magic_map(
                playerId,
                position,
                mapId,
                centerX,
                centerZ,
                discoverLandmarks=False,
            ) or {}
            self._send_magic_map_delta(
                playerId,
                position,
                mapId,
                centerX,
                centerZ,
                changes,
                includePlayers=False,
            )

    def _get_dimension(self, entityId):
        if not self._valid_entity_id(entityId):
            return None
        try:
            return CF.CreateDimension(entityId).GetEntityDimensionId()
        except Exception:
            return None

    def _get_foot_pos(self, entityId):
        if not self._valid_entity_id(entityId):
            return None
        try:
            return CF.CreatePos(entityId).GetFootPos()
        except Exception:
            return None

    def _get_engine_type(self, entityId):
        if not self._valid_entity_id(entityId):
            return None
        try:
            return CF.CreateEngineType(entityId).GetEngineTypeStr()
        except Exception:
            return None

    def _lich_display_name(self, entityId):
        try:
            name = CF.CreateName(entityId).GetName()
            if name:
                return name
        except Exception:
            pass
        return u"\u5deb\u5996"

    def _boss_key(self, entityId):
        return entity_registry_logic.matching_entity_key(
            self._bosses,
            entityId,
        )

    def _boss_state(self, entityId):
        key = self._boss_key(entityId)
        if key is None:
            return None
        return self._bosses.get(key)

    def _on_boss_actor_removed(
        self, registry, entityId, terminalFields=()
    ):
        """Detach a streamed-out Boss without converting unload into death."""
        key = entity_registry_logic.matching_entity_key(registry, entityId)
        if key is None:
            return None, None, False
        state = registry.get(key)
        if state is None:
            return key, None, False
        terminal = any(bool(state.get(field)) for field in terminalFields)
        if terminal:
            registry.pop(key, None)
        else:
            state["actorLoaded"] = False
            state["targetId"] = None
        return key, state, terminal

    def _boss_home_is_observed(self, state):
        home = state.get("home") if isinstance(state, dict) else None
        if home is None or len(home) != 3:
            return False
        dimensionId = state.get("dimensionId")
        radiusSquared = float(config.BOSS_DISCOVERY_RADIUS) ** 2
        for playerId in self._get_online_players():
            if self._get_dimension(playerId) != dimensionId:
                continue
            playerPos = self._get_foot_pos(playerId)
            if (
                playerPos is not None
                and _distance_sq(playerPos, home) <= radiusSquared
            ):
                return True
        return False

    def _difficulty(self):
        try:
            return int(CF.CreateGame(LEVEL_ID).GetGameDiffculty())
        except Exception:
            return config.DEFAULT_DIFFICULTY_ID

    def _mob_griefing(self):
        try:
            rules = CF.CreateGame(LEVEL_ID).GetGameRulesInfoServer() or {}
            cheats = rules.get("cheat_info", {})
            return bool(
                cheats.get("mob_griefing", config.DEFAULT_MOB_GRIEFING)
            )
        except Exception:
            return config.DEFAULT_MOB_GRIEFING

    def _home_conflicts(self, home, dimensionId, excludedBossId=None):
        if home is None:
            return False
        for bossId, state in self._bosses.items():
            if (
                str(bossId) == str(excludedBossId)
                or state.get("dead")
            ):
                continue
            if state.get("dimensionId") != dimensionId:
                continue
            if naga_logic.courtyards_overlap(home, state.get("home")):
                return True
        return False

    def _pending_home_conflicts(self, home, dimensionId):
        for pending in self._pending_naga_spawns:
            if pending["dimensionId"] != dimensionId:
                continue
            if naga_logic.courtyards_overlap(home, pending["home"]):
                return True
        return False

    def _pending_courtyard_home_conflicts(self, home, dimensionId):
        for pending in self._pending_courtyard_nagas:
            if pending["dimensionId"] != int(dimensionId):
                continue
            if naga_logic.courtyards_overlap(home, pending["home"]):
                return True
        return False

    def _pending_courtyard_naga(
        self,
        entityId,
        dimensionId=None,
        home=None,
        expectedIdentifier=None,
    ):
        for pending in self._pending_courtyard_nagas:
            pendingIdentifier = str(
                pending.get("identifier", config.BOSS_IDENTIFIER)
            )
            if (
                expectedIdentifier is not None
                and pendingIdentifier != str(expectedIdentifier)
            ):
                continue
            pendingId = pending.get("entityId")
            if (
                entityId is not None
                and pendingId is not None
                and str(pendingId) == str(entityId)
            ):
                return pending
            if pendingId is not None or dimensionId is None:
                continue
            if pending.get("dimensionId") != int(dimensionId):
                continue
            if home is None or naga_logic.courtyards_overlap(
                home,
                pending.get("home"),
            ):
                return pending
        return None

    def _purge_pending_naga_spawns(self):
        self._pending_naga_spawns = [
            pending
            for pending in self._pending_naga_spawns
            if pending["expires"] >= self._tick
        ]
        expired = [
            pending
            for pending in self._pending_courtyard_nagas
            if pending["expires"] < self._tick
        ]
        self._pending_courtyard_nagas = [
            pending
            for pending in self._pending_courtyard_nagas
            if pending["expires"] >= self._tick
        ]
        for pending in expired:
            if pending.get("entityId") is not None:
                self._remove_excess_boss(pending["entityId"])

    def _enable_mob_hit_detection(self, bossId):
        try:
            return CF.CreateGame(LEVEL_ID).OpenMobHitBlockDetection(
                bossId, config.MOB_HIT_BLOCK_PRECISION
            )
        except Exception as exc:
            print "[TwilightBossSlice] mob-hit detection failed:", bossId, exc
            return False

    def _get_block(self, pos, dimensionId):
        try:
            return self._block_comp.GetBlockNew(pos, dimensionId)
        except Exception:
            return None

    def _set_block(self, pos, blockName, dimensionId):
        try:
            return self._block_comp.SetBlockNew(
                pos,
                {"name": blockName, "aux": 0},
                0,
                dimensionId,
                True,
                False,
            )
        except Exception as exc:
            print "[TwilightBossSlice] SetBlockNew failed:", pos, exc
            return False

    def _register_leaf_decay_listeners(self):
        registered = 0
        for blockName in leaf_decay_logic.listener_block_ids():
            try:
                if self._block_comp.ListenOnBlockRemoveEvent(blockName, True):
                    registered += 1
            except Exception as error:
                print (
                    "[TwilightBossSlice] leaf removal listener failed:",
                    blockName,
                    error,
                )
        return registered

    def _enqueue_leaf_decay(self, position, dimensionId, delayTicks=None):
        key = leaf_decay_logic.position_key(dimensionId, position)
        if (
            key not in self._leaf_decay_queue
            and len(self._leaf_decay_queue) >= config.LEAF_DECAY_MAX_PENDING
        ):
            return False
        if delayTicks is None:
            delayTicks = random.randint(
                config.LEAF_DECAY_MIN_DELAY_TICKS,
                config.LEAF_DECAY_MAX_DELAY_TICKS,
            )
        return leaf_decay_logic.enqueue_candidate(
            self._leaf_decay_queue,
            dimensionId,
            position,
            self._tick + max(1, int(delayTicks)),
        )

    def _queue_neighbor_leaf_decay(self, position, dimensionId):
        queued = 0
        for neighbor in leaf_decay_logic.orthogonal_neighbors(position):
            block = self._get_block(neighbor, dimensionId)
            if block is None:
                continue
            if not leaf_decay_logic.is_connecting_leaf(
                leaf_decay_logic.block_name(block)
            ):
                continue
            if self._enqueue_leaf_decay(neighbor, dimensionId):
                queued += 1
        return queued

    def _spawn_leaf_decay_drops(self, blockName, position, dimensionId):
        drops = leaf_decay_logic.decay_drops(
            blockName,
            random.random(),
            random.random(),
            random.random(),
        )
        dropPosition = (
            float(position[0]) + 0.5,
            float(position[1]) + 0.5,
            float(position[2]) + 0.5,
        )
        for item in drops:
            try:
                engineItem = copy.deepcopy(item)
                engineItem["newItemName"] = engineItem["itemName"]
                engineItem["newAuxValue"] = engineItem.get("auxValue", 0)
                self.CreateEngineItemEntity(
                    engineItem, int(dimensionId), dropPosition
                )
            except Exception as error:
                print "[TwilightBossSlice] leaf decay drop failed:", error

    def _cached_leaf_block(self, cache, position, dimensionId):
        key = leaf_decay_logic.position_key(dimensionId, position)
        if key not in cache:
            cache[key] = self._get_block(position, dimensionId)
        return cache[key]

    def _process_leaf_decay_queue(self):
        if not leaf_decay_logic.is_decay_processing_tick(
            self._tick, config.LEAF_DECAY_PROCESS_INTERVAL_TICKS
        ):
            return
        candidates = leaf_decay_logic.pop_due_candidates(
            self._leaf_decay_queue,
            self._tick,
            config.LEAF_DECAY_TICK_BUDGET,
        )
        blockCache = {}
        for dimensionId, position in candidates:
            block = self._cached_leaf_block(
                blockCache, position, dimensionId
            )
            if block is None:
                self._enqueue_leaf_decay(
                    position,
                    dimensionId,
                    config.LEAF_DECAY_MIN_DELAY_TICKS,
                )
                continue
            blockName = leaf_decay_logic.block_name(block)
            key = leaf_decay_logic.position_key(dimensionId, position)
            if not leaf_decay_logic.is_decayable_leaf(blockName):
                self._discard_persistent_leaf(dimensionId, position)
                if (
                    leaf_decay_logic.is_connecting_leaf(blockName)
                    and key not in self._leaf_decay_bridge_propagated
                ):
                    self._leaf_decay_bridge_propagated.add(key)
                    self._queue_neighbor_leaf_decay(position, dimensionId)
                continue
            if key in self._persistent_leaf_positions:
                if key not in self._leaf_decay_bridge_propagated:
                    self._leaf_decay_bridge_propagated.add(key)
                    self._queue_neighbor_leaf_decay(position, dimensionId)
                continue
            supported = leaf_decay_logic.is_leaf_supported(
                position,
                lambda target: self._cached_leaf_block(
                    blockCache, target, dimensionId
                ),
            )
            if supported is None:
                self._enqueue_leaf_decay(
                    position,
                    dimensionId,
                    config.LEAF_DECAY_MIN_DELAY_TICKS,
                )
                continue
            if supported:
                continue
            if self._set_block(position, "minecraft:air", dimensionId) is False:
                self._enqueue_leaf_decay(
                    position,
                    dimensionId,
                    config.LEAF_DECAY_MIN_DELAY_TICKS,
                )
                continue
            blockCache[leaf_decay_logic.position_key(
                dimensionId, position
            )] = {"name": "minecraft:air", "aux": 0}
            self._spawn_leaf_decay_drops(blockName, position, dimensionId)
            self._queue_neighbor_leaf_decay(position, dimensionId)

    def _register_persistent_leaf_position(
        self, position, dimensionId, expectedBlockName
    ):
        position = tuple(int(value) for value in position)
        blockName = leaf_decay_logic.block_name(
            self._get_block(position, dimensionId)
        )
        if (
            blockName != str(expectedBlockName)
            or not leaf_decay_logic.is_decayable_leaf(blockName)
        ):
            return False
        key = leaf_decay_logic.position_key(dimensionId, position)
        if key in self._persistent_leaf_positions:
            return True
        self._leaf_decay_bridge_propagated.discard(key)
        self._persistent_leaf_positions.add(key)
        self._leaf_decay_state_dirty = True
        return True

    def _sapling_growth_stage(self, position, dimensionId):
        if self._block_state_comp is None:
            return None
        try:
            states = self._block_state_comp.GetBlockStates(
                tuple(position), int(dimensionId)
            ) or {}
            return max(
                0,
                min(1, int(states.get("tf_slice:growth_stage", 0))),
            )
        except (TypeError, ValueError):
            return 0
        except Exception:
            return None

    def _set_sapling_growth_stage(self, position, dimensionId, stage):
        if self._block_state_comp is None:
            return False
        try:
            states = self._block_state_comp.GetBlockStates(
                tuple(position), int(dimensionId)
            ) or {}
            states["tf_slice:growth_stage"] = max(0, min(1, int(stage)))
            return self._block_state_comp.SetBlockStates(
                tuple(position), states, int(dimensionId)
            ) is not False
        except Exception:
            return False

    def _rainbow_sapling_clearance_open(self, position, dimensionId):
        for probe in leaf_decay_logic.rainbow_sapling_clearance_positions(
            position
        ):
            probeName = leaf_decay_logic.block_name(
                self._get_block(probe, dimensionId)
            )
            if not leaf_decay_logic.rainbow_sapling_can_replace(probeName):
                return False
        return True

    def _grow_rainbow_sapling_structure(self, position, dimensionId):
        variantIndex = random.randrange(
            leaf_decay_logic.RAINBOW_SAPLING_STRUCTURE_COUNT
        )
        structureName = leaf_decay_logic.rainbow_sapling_structure(
            variantIndex
        )
        origin = leaf_decay_logic.rainbow_sapling_structure_origin(position)
        if structureName is None or origin is None:
            return False
        try:
            result = CF.CreateGame(LEVEL_ID).PlaceStructure(
                None,
                origin,
                structureName,
                int(dimensionId),
                0,
                0,
                0,
                True,
                False,
                0,
                100.0,
                variantIndex,
            )
        except Exception as error:
            print "[TwilightBossSlice] rainbow sapling structure failed:", error
            return False
        if result is False:
            return False
        rootName = leaf_decay_logic.block_name(
            self._get_block(position, dimensionId)
        )
        return leaf_decay_logic.rainbow_sapling_has_grown(rootName)

    def _grow_twilight_sapling(
        self, blockName, position, dimensionId, restoreStage=1
    ):
        featureNames = leaf_decay_logic.sapling_feature_attempts(blockName)
        if not featureNames:
            return False
        currentName = leaf_decay_logic.block_name(
            self._get_block(position, dimensionId)
        )
        if currentName != str(blockName):
            return False
        useRainbowStructure = (
            str(blockName) == "tf_slice:rainbow_oak_sapling"
        )
        if useRainbowStructure and not self._rainbow_sapling_clearance_open(
            position, dimensionId
        ):
            return False
        if self._set_block(position, "minecraft:air", dimensionId) is False:
            return False
        if useRainbowStructure:
            if self._grow_rainbow_sapling_structure(position, dimensionId):
                return True
            self._set_block(position, blockName, dimensionId)
            self._set_sapling_growth_stage(
                position, dimensionId, restoreStage
            )
            return False
        placed = False
        for featureName in featureNames:
            try:
                placed = bool(
                    CF.CreateGame(LEVEL_ID).PlaceFeature(
                        featureName,
                        int(dimensionId),
                        tuple(int(value) for value in position),
                    )
                )
            except Exception as error:
                print "[TwilightBossSlice] sapling feature failed:", featureName, error
                placed = False
            if placed:
                return True
        print "[TwilightBossSlice] no sapling feature placed:", blockName, position, dimensionId, featureNames
        self._set_block(position, blockName, dimensionId)
        self._set_sapling_growth_stage(
            position, dimensionId, restoreStage
        )
        return False

    def _advance_twilight_sapling(self, blockName, position, dimensionId):
        stage = self._sapling_growth_stage(position, dimensionId)
        if stage is None:
            return False
        if leaf_decay_logic.sapling_growth_action(stage) == "advance":
            return self._set_sapling_growth_stage(
                position, dimensionId, 1
            )
        return self._grow_twilight_sapling(
            blockName, position, dimensionId, restoreStage=stage
        )

    def _broadcast_sapling_growth_effect(
        self, position, dimensionId, advanced=False, grown=False
    ):
        self.BroadcastToAllClient(
            "SaplingGrowthEffect",
            {
                "dimensionId": int(dimensionId),
                "position": tuple(position),
                "advanced": bool(advanced),
                "grown": bool(grown),
            },
        )

    def _try_bonemeal_twilight_sapling(self, args, itemName):
        if str(itemName) != "minecraft:bone_meal":
            return False
        position = (
            int(args.get("x", args.get("blockX", 0))),
            int(args.get("y", args.get("blockY", 0))),
            int(args.get("z", args.get("blockZ", 0))),
        )
        playerId = args.get("playerId", args.get("entityId"))
        dimensionId = int(
            args.get("dimensionId", self._get_dimension(playerId) or 0)
        )
        blockName = leaf_decay_logic.block_name(
            self._get_block(position, dimensionId)
        )
        if leaf_decay_logic.sapling_feature(blockName) is None:
            return False
        consumed, original = self._consume_one_carried_item(playerId)
        if not consumed:
            return True
        stageBefore = self._sapling_growth_stage(position, dimensionId)
        advanced = False
        grown = False
        if leaf_decay_logic.bonemeal_growth_succeeds(random.random()):
            advanced = self._advance_twilight_sapling(
                blockName, position, dimensionId
            )
            grown = bool(advanced and stageBefore is not None and stageBefore >= 1)
            if not advanced and original is not None:
                currentName = leaf_decay_logic.block_name(
                    self._get_block(position, dimensionId)
                )
                if currentName == blockName and stageBefore is not None:
                    self._set_carried_item(playerId, original)
        self._broadcast_sapling_growth_effect(
            position, dimensionId, advanced=advanced, grown=grown
        )
        args["ret"] = True
        return True

    def _portal_block_getter(self, dimensionId):
        return lambda pos: self._get_block(pos, dimensionId)

    def _portal_surface(self, pos, dimensionId):
        return portal_logic.collect_stable_portal(
            pos,
            self._portal_block_getter(dimensionId),
            config.PORTAL_IDENTIFIER,
            1,
            config.PORTAL_MAX_SIZE,
        )

    def _portal_exit(self, surface, dimensionId):
        return portal_logic.find_exit(
            surface,
            self._portal_block_getter(dimensionId),
            config.PORTAL_IDENTIFIER,
        )

    def _get_top_block_height(self, xz, dimensionId):
        try:
            return self._block_comp.GetTopBlockHeight(
                (int(xz[0]), int(xz[1])),
                int(dimensionId),
            )
        except Exception as exc:
            print (
                "[TwilightBossSlice] portal height query failed:",
                xz,
                exc,
            )
            return None

    def _block_view_ready(self, position, dimensionId):
        """Require BlockInfo to expose the LevelChunk, not just chunk state."""
        try:
            block = self._block_comp.GetBlockNew(
                tuple(int(value) for value in position),
                int(dimensionId),
            )
        except Exception:
            return False
        if isinstance(block, dict):
            return bool(block.get("name"))
        return bool(isinstance(block, (tuple, list)) and block)

    def _fire_swamp_device_key(self, position, dimensionId):
        return (
            int(dimensionId),
            int(position[0]),
            int(position[1]),
            int(position[2]),
        )

    def _fire_swamp_block_states(self, position, dimensionId):
        if self._block_state_comp is None:
            return {}
        blockName = self._block_name(
            self._get_block(tuple(position), int(dimensionId))
        )
        if not blockName or blockName in SIGHT_PASSABLE_BLOCKS:
            return {}
        try:
            return self._block_state_comp.GetBlockStates(
                tuple(position), int(dimensionId)
            ) or {}
        except Exception:
            return {}

    def _set_fire_swamp_device_visual(self, position, dimensionId, state):
        if self._block_state_comp is None:
            return False
        blockStates = self._fire_swamp_block_states(position, dimensionId)
        blockName = state.get("block")
        if blockName in (
            fire_swamp_logic.FIRE_JET,
            fire_swamp_logic.ENCASED_FIRE_JET,
        ):
            blockStates["tf_slice:jet_state"] = str(
                state.get("phase", "idle")
            )
        elif blockName == fire_swamp_logic.ENCASED_SMOKER:
            blockStates["tf_slice:active"] = (
                "on" if state.get("active") else "off"
            )
        else:
            return False
        try:
            return self._block_state_comp.SetBlockStates(
                tuple(position), blockStates, int(dimensionId)
            )
        except Exception:
            return False

    def _register_fire_swamp_device(
        self, blockName, position, dimensionId
    ):
        blockName = str(blockName)
        if blockName not in fire_swamp_logic.DEVICE_BLOCKS:
            return None
        position = tuple(int(value) for value in position)
        dimensionId = int(dimensionId)
        key = self._fire_swamp_device_key(position, dimensionId)
        existing = self._fire_swamp_devices.get(key)
        if existing is not None and existing.get("block") == blockName:
            return existing
        state = fire_swamp_logic.new_device(blockName)
        blockStates = self._fire_swamp_block_states(position, dimensionId)
        phase = str(blockStates.get("tf_slice:jet_state", "idle"))
        if phase in ("idle", "popping", "flame", "timeout"):
            state["phase"] = phase
        if blockName == fire_swamp_logic.ENCASED_SMOKER:
            state["active"] = (
                str(blockStates.get("tf_slice:active", "off")) == "on"
            )
        state["position"] = position
        state["dimensionId"] = dimensionId
        self._fire_swamp_devices[key] = state
        return state

    def _delay_fire_swamp_discovery(self, playerId):
        if playerId is None:
            return
        if not hasattr(self, "_fire_swamp_discovery_ready_ticks"):
            self._fire_swamp_discovery_ready_ticks = {}
        if not hasattr(self, "_fire_swamp_discovery_queue"):
            self._fire_swamp_discovery_queue = []
        self._fire_swamp_discovery_ready_ticks[playerId] = (
            self._tick + FIRE_SWAMP_DISCOVERY_GRACE_TICKS
        )
        # A queued column can belong to terrain that is unloading while the
        # player changes dimension. Rebuild only after the arrival grace.
        self._fire_swamp_discovery_queue = []

    def _fire_swamp_chunk_ready(self, x, z):
        checker = getattr(self._chunk_comp, "CheckChunkState", None)
        if checker is None:
            return False
        chunkX = int(x) >> 4
        chunkZ = int(z) >> 4
        checkPosition = (
            chunkX * 16 + 8,
            64,
            chunkZ * 16 + 8,
        )
        try:
            chunkReady = bool(
                checker(config.DIMENSION_ID, checkPosition)
            )
        except Exception:
            return False
        return bool(
            chunkReady
            and self._block_view_ready(
                checkPosition,
                config.DIMENSION_ID,
            )
        )

    def _queue_fire_swamp_discovery_columns(self):
        columns = set()
        onlinePlayers = set(self._get_online_players())
        for playerId in onlinePlayers:
            if self._get_dimension(playerId) != config.DIMENSION_ID:
                self._fire_swamp_discovery_ready_ticks.pop(playerId, None)
                continue
            if playerId in getattr(
                self,
                "_dimension_change_in_progress",
                set(),
            ):
                continue
            worldgenReadyTick = getattr(
                self,
                "_dimension_worldgen_ready_ticks",
                {},
            ).get(playerId)
            if (
                worldgenReadyTick is not None
                and self._tick < worldgenReadyTick
            ):
                continue
            readyTick = self._fire_swamp_discovery_ready_ticks.get(playerId)
            if readyTick is None:
                self._delay_fire_swamp_discovery(playerId)
                continue
            if self._tick < readyTick:
                continue
            playerPos = self._get_foot_pos(playerId)
            if playerPos is None:
                continue
            centerX = int(math.floor(playerPos[0]))
            centerZ = int(math.floor(playerPos[2]))
            radius = FIRE_SWAMP_DISCOVERY_RADIUS
            for x in range(centerX - radius, centerX + radius + 1):
                for z in range(centerZ - radius, centerZ + radius + 1):
                    columns.add((x, z))
        for playerId in list(self._fire_swamp_discovery_ready_ticks):
            if playerId not in onlinePlayers:
                self._fire_swamp_discovery_ready_ticks.pop(playerId, None)
        self._fire_swamp_discovery_queue = sorted(columns, reverse=True)

    def _discover_fire_swamp_devices(self):
        if (
            not self._fire_swamp_discovery_queue
            and self._tick % FIRE_SWAMP_DISCOVERY_INTERVAL_TICKS == 1
        ):
            self._queue_fire_swamp_discovery_columns()
        readyChunks = {}
        budget = FIRE_SWAMP_DISCOVERY_COLUMNS_PER_TICK
        while self._fire_swamp_discovery_queue and budget > 0:
            budget -= 1
            x, z = self._fire_swamp_discovery_queue.pop()
            chunk = (int(x) >> 4, int(z) >> 4)
            chunkReady = readyChunks.get(chunk)
            if chunkReady is None:
                chunkReady = self._fire_swamp_chunk_ready(x, z)
                readyChunks[chunk] = chunkReady
            if not chunkReady:
                continue
            top = self._get_top_block_height(
                (x, z), config.DIMENSION_ID
            )
            if top is None:
                # CheckChunkState can briefly lead the block component during
                # dimension entry. Stop touching this chunk for the tick.
                readyChunks[chunk] = False
                continue
            for y in range(int(top), int(top) - 7, -1):
                position = (x, y, z)
                blockName = self._block_name(
                    self._get_block(position, config.DIMENSION_ID)
                )
                if blockName in fire_swamp_logic.DEVICE_BLOCKS:
                    self._register_fire_swamp_device(
                        blockName, position, config.DIMENSION_ID
                    )

    def _fire_swamp_device_powered(self, position, dimensionId):
        return self._adjacent_redstone_powered(
            position, dimensionId
        )

    @staticmethod
    def _redstone_state_truthy(value):
        if isinstance(value, basestring):
            return value.lower() in ("1", "true", "on", "powered")
        return bool(value)

    def _redstone_carrier_powered(self, position, dimensionId):
        block = self._get_block(position, dimensionId) or {}
        if isinstance(block, dict):
            blockName = str(block.get("name", ""))
            aux = int(block.get("aux", 0))
        else:
            blockName = str(block[0]) if block else ""
            aux = int(block[1]) if len(block) > 1 else 0
        states = self._fire_swamp_block_states(
            position, dimensionId
        )
        for key in (
            "redstone_signal",
            "tf_slice:redstone_signal",
            "output_signal",
        ):
            try:
                if int(states.get(key, 0)) > 0:
                    return True
            except (TypeError, ValueError):
                pass
        for key in (
            "powered_bit",
            "open_bit",
            "button_pressed_bit",
            "tf_slice:powered",
        ):
            if self._redstone_state_truthy(states.get(key, False)):
                return True
        if blockName == "minecraft:redstone_block":
            return True
        if blockName == "minecraft:redstone_torch":
            return True
        if blockName in (
            "minecraft:powered_repeater",
            "minecraft:powered_comparator",
        ):
            return True
        if blockName == "minecraft:redstone_wire":
            return aux > 0
        if blockName in (
            "minecraft:lever",
            "minecraft:stone_button",
            "minecraft:wooden_button",
            "minecraft:repeater",
            "minecraft:unpowered_repeater",
            "minecraft:comparator",
            "minecraft:unpowered_comparator",
        ):
            return bool(aux & 8)
        return False

    def _adjacent_redstone_powered(self, position, dimensionId):
        if position is None:
            return False
        for dx, dy, dz in (
            (-1, 0, 0), (1, 0, 0),
            (0, -1, 0), (0, 1, 0),
            (0, 0, -1), (0, 0, 1),
        ):
            neighbor = (
                int(position[0]) + dx,
                int(position[1]) + dy,
                int(position[2]) + dz,
            )
            if self._redstone_carrier_powered(
                neighbor, int(dimensionId)
            ):
                return True
        return False

    def _consume_fire_swamp_jet_fuel(self, state):
        candidates = fire_swamp_logic.lava_fuel_candidates(
            state["position"]
        )
        probes = [candidates[0]]
        for _unused in range(3):
            probes.append(random.choice(candidates[1:]))
        checked = set()
        for position in probes:
            if position in checked:
                continue
            checked.add(position)
            blockName = self._block_name(
                self._get_block(position, state["dimensionId"])
            )
            if blockName not in LAVA_BLOCKS:
                continue
            return self._set_block(
                position, "minecraft:air", state["dimensionId"]
            ) is not False
        return False

    def _send_fire_swamp_device_effect(self, state, effect):
        position = state.get("position")
        if position is None:
            return
        packet = {
            "effect": str(effect),
            "position": [float(value) for value in position],
            "dimensionId": int(state.get("dimensionId", 0)),
            "phase": str(state.get("phase", "idle")),
        }
        for playerId in self._get_online_players():
            if self._get_dimension(playerId) != packet["dimensionId"]:
                continue
            playerPos = self._get_foot_pos(playerId)
            if playerPos is None or _distance_sq(playerPos, position) > 64 * 64:
                continue
            self.NotifyToClient(
                playerId, "FireSwampDeviceEffect", packet
            )

    def _damage_with_fire_swamp_jet(self, state):
        start, end = fire_swamp_logic.fire_jet_damage_bounds(
            state["position"]
        )
        try:
            entities = CF.CreateGame(LEVEL_ID).GetEntitiesInSquareArea(
                None, start, end, int(state["dimensionId"])
            ) or ()
        except Exception:
            return
        damageCauses = serverApi.GetMinecraftEnum().ActorDamageCause
        cause = getattr(
            damageCauses,
            "Fire",
            getattr(damageCauses, "Lava", damageCauses.EntityAttack),
        )
        for entityId in entities:
            if self._get_engine_type(entityId) in FIRE_SWAMP_FIRE_IMMUNE:
                continue
            try:
                CF.CreateHurt(entityId).Hurt(
                    float(fire_swamp_logic.FIRE_JET_DAMAGE),
                    cause,
                    None,
                    None,
                    False,
                )
            except Exception:
                continue
            self._set_entity_on_fire(
                entityId, fire_swamp_logic.FIRE_JET_SECONDS
            )

    def _update_fire_swamp_devices(self):
        self._discover_fire_swamp_devices()
        for key, state in list(self._fire_swamp_devices.items()):
            position = state.get("position")
            dimensionId = state.get("dimensionId")
            blockName = self._block_name(
                self._get_block(position, dimensionId)
            )
            if blockName != state.get("block"):
                self._fire_swamp_devices.pop(key, None)
                continue
            previousPhase = state.get("phase")
            previousActive = bool(state.get("active"))
            if blockName in (
                fire_swamp_logic.ENCASED_SMOKER,
                fire_swamp_logic.ENCASED_FIRE_JET,
            ):
                state, powerEvents = fire_swamp_logic.apply_power(
                    state,
                    self._fire_swamp_device_powered(
                        position, dimensionId
                    ),
                )
                for effect in powerEvents:
                    self._send_fire_swamp_device_effect(state, effect)
            elif (
                blockName == fire_swamp_logic.FIRE_JET
                and state.get("phase") == "idle"
                and random.randrange(1365) == 0
            ):
                consumed = self._consume_fire_swamp_jet_fuel(state)
                state, _consumeEvent = fire_swamp_logic.ignite_natural_jet(
                    state, consumed
                )
            state, effects = fire_swamp_logic.tick_device(state)
            state["position"] = position
            state["dimensionId"] = dimensionId
            self._fire_swamp_devices[key] = state
            if (
                state.get("phase") != previousPhase
                or bool(state.get("active")) != previousActive
            ):
                self._set_fire_swamp_device_visual(
                    position, dimensionId, state
                )
            for effect in effects:
                if effect == "damage":
                    self._damage_with_fire_swamp_jet(state)
                else:
                    self._send_fire_swamp_device_effect(state, effect)

    def _portal_now_seconds(self):
        return time.time()

    def _portal_request_expired(self, request):
        expiresAt = request.get("expiresAt")
        if expiresAt is not None:
            try:
                return self._portal_now_seconds() > float(expiresAt)
            except (TypeError, ValueError):
                pass
        return self._tick > request.get("expires", self._tick)

    def _portal_target_chunks_ready(self, request):
        checker = getattr(self._chunk_comp, "CheckChunkState", None)
        if checker is None:
            return False
        destinationX, destinationZ = request["destinationXZ"]
        samplePositions = (
            portal_logic.client_render_chunk_sample_positions(
                (destinationX, 64, destinationZ),
                portal_logic.PORTAL_SERVER_SAFE_CHUNK_RADIUS,
            )
        )
        for sampleX, sampleZ in samplePositions:
            checkPosition = (sampleX, 64, sampleZ)
            try:
                if not checker(config.DIMENSION_ID, checkPosition):
                    return False
            except Exception as exc:
                print (
                    "[TwilightBossSlice] portal chunk readiness failed:",
                    checkPosition,
                    exc,
                )
                return False
            if not self._block_view_ready(
                checkPosition,
                config.DIMENSION_ID,
            ):
                return False
        return True

    def _start_portal_area(self, request):
        if request.get("areaKey"):
            return True
        self._portal_area_sequence += 1
        areaKey = "tf_slice_portal_%d" % self._portal_area_sequence
        destinationX, destinationZ = request["destinationXZ"]
        margin = config.PORTAL_AREA_MARGIN
        try:
            started = self._chunk_comp.SetAddArea(
                areaKey,
                config.DIMENSION_ID,
                (
                    int(destinationX) - margin,
                    0,
                    int(destinationZ) - margin,
                ),
                (
                    int(destinationX) + margin + 1,
                    255,
                    int(destinationZ) + margin + 1,
                ),
            )
        except Exception as exc:
            print "[TwilightBossSlice] portal SetAddArea failed:", exc
            started = False
        if not started:
            return False
        request["areaKey"] = areaKey
        request["readyTick"] = (
            self._tick + config.PORTAL_AREA_WARMUP_TICKS
        )
        request["nextAttemptTick"] = request["readyTick"]
        request["state"] = "loading"
        return True

    def _release_portal_area(self, request):
        areaKey = request.pop("areaKey", None)
        if not areaKey:
            return
        try:
            self._chunk_comp.DeleteArea(areaKey)
        except Exception as exc:
            print "[TwilightBossSlice] portal DeleteArea failed:", exc

    def _drop_portal_arrival(self, playerId, request, message):
        self._release_staged_portal_hold(playerId, request)
        if self._pending_portal_entries.get(playerId) is request:
            self._pending_portal_entries.pop(playerId, None)
        self._release_portal_area(request)
        self.NotifyToClient(
            playerId,
            "PortalArrivalFinished",
            {"cancelled": True},
        )
        print (
            "[TwilightBossSlice] portal arrival dropped:",
            playerId,
            request.get("state"),
            request.get("destinationXZ"),
        )
        self._notify(playerId, message, "RED")

    def _portal_entry_bootstrap_due(self, request):
        bootstrapAt = request.get("bootstrapAt")
        if bootstrapAt is not None:
            try:
                return self._portal_now_seconds() >= float(bootstrapAt)
            except (TypeError, ValueError):
                pass
        return self._tick >= request.get(
            "bootstrapAtTick",
            self._tick + 1,
        )

    def _bootstrap_portal_entry(self, playerId, request):
        """Let the engine create the first chunks at the final destination."""
        self._entry_trace(
            "entry.bootstrap.begin",
            playerId=playerId,
            state=request.get("state"),
            destinationXZ=request.get("destinationXZ"),
        )
        if request.get("recovery"):
            self._entry_trace(
                "entry.bootstrap.rejected",
                playerId=playerId,
                reason="recovery",
            )
            return False
        directEntry = bool(config.PORTAL_DIRECT_ENTRY_ENABLED)
        if directEntry:
            destinationX, destinationZ = request["destinationXZ"]
            bootstrapFootPos = (
                float(destinationX) - 0.5,
                float(config.WORLDGEN_DIRECT_ENTRY_FOOT_Y),
                float(destinationZ) + 0.5,
            )
        else:
            bootstrapFootPos = tuple(config.WORLDGEN_STAGING_FOOT_POS)
        request["state"] = "changing_dimension"
        request["bootstrapEntry"] = True
        request["directEntry"] = directEntry
        request["bootstrapFootPos"] = bootstrapFootPos
        if directEntry:
            request["directEntryFootPos"] = bootstrapFootPos
        self._release_portal_area(request)
        if not hasattr(self, "_dimension_change_in_progress"):
            self._dimension_change_in_progress = set()
        # Arm the native-structure guard before ChangePlayerDimension can
        # schedule target chunks.  Waiting for DimensionChangeServerEvent
        # leaves a worker-thread race in which a structure feature may start
        # first on a fresh dimension.
        self._dimension_change_in_progress.add(playerId)
        targetPosition = portal_logic.player_position_from_foot(
            bootstrapFootPos
        )
        self._entry_trace(
            (
                "entry.direct.change.call"
                if directEntry
                else "dimension.change.call"
            ),
            playerId=playerId,
            dimensionId=config.DIMENSION_ID,
            position=targetPosition,
        )
        request["nativeChangeStartedAt"] = self._portal_now_seconds()
        result = self._change_dimension(
            playerId,
            config.DIMENSION_ID,
            targetPosition,
        )
        self._entry_trace(
            (
                "entry.direct.change.return"
                if directEntry
                else "dimension.change.return"
            ),
            playerId=playerId,
            result=result,
        )
        if result is False:
            self._dimension_change_in_progress.discard(playerId)
            request["state"] = "queued"
            request["bootstrapEntry"] = False
            request["nextAttemptTick"] = (
                self._tick + config.PORTAL_BUILD_RETRY_TICKS
            )
            request["bootstrapAtTick"] = (
                self._tick + config.PORTAL_ENTRY_BOOTSTRAP_TICKS
            )
            request["bootstrapAt"] = (
                self._portal_now_seconds()
                + config.PORTAL_ENTRY_BOOTSTRAP_SECONDS
            )
            return False
        self._notify(
            playerId,
            u"\u76ee\u6807\u7ef4\u5ea6\u6b63\u5728\u521d\u59cb\u5316\uff0c\u62b5\u8fbe\u540e\u4f1a\u81ea\u52a8\u8865\u5efa\u8fd4\u7a0b\u95e8\u2026\u2026",
            "AQUA",
        )
        print (
            "[TwilightBossSlice] portal entry bootstrapped:",
            playerId,
            bootstrapFootPos,
        )
        return True

    def _prepare_direct_portal_arrival(self, playerId, request):
        """Prepare the portal in chunks loaded by the arriving player ticket."""
        request["bootstrapEntry"] = False
        request["recovery"] = True
        request["stagedRelocationPending"] = True
        request["state"] = "loading"
        request["directFinishTick"] = self._tick
        request["nextAttemptTick"] = self._tick + 1
        request["expires"] = (
            self._tick + config.PORTAL_ARRIVAL_TIMEOUT_TICKS
        )
        request["expiresAt"] = (
            self._portal_now_seconds()
            + config.PORTAL_ARRIVAL_TIMEOUT_SECONDS
        )
        self._release_portal_area(request)
        for key in (
            "destinationOrigin",
            "destinationSurface",
            "destinationExit",
            "readyTick",
        ):
            request.pop(key, None)
        self._entry_trace(
            "entry.direct.destination_finish",
            playerId=playerId,
            destinationXZ=request.get("destinationXZ"),
            enteredAt=request.get("directEntryFootPos"),
            portalCheckAtTick=request["nextAttemptTick"],
        )
        return True

    def _prepare_portal_client_relocation(
        self, playerId, request, targetFootPos
    ):
        """Wait for the client respawn pipeline before the direct Y adjust."""
        targetFootPos = tuple(float(value) for value in targetFootPos)
        request["preparedExit"] = targetFootPos
        request["clientEngineReadyPending"] = True
        request["clientEngineReady"] = False
        request["clientEngineReadyFallback"] = False
        request["clientEngineReadyToken"] = "engine:%d:%d" % (
            int(self._portal_area_sequence),
            int(self._tick),
        )
        request["clientEngineReadyFallbackTick"] = max(
            self._tick + 1,
            int(request.get("directFinishTick", self._tick))
            + config.PORTAL_CLIENT_ENGINE_READY_FALLBACK_TICKS,
        )
        request["state"] = "awaiting_engine_ready"
        request["nextAttemptTick"] = self._tick + 1
        self.NotifyToClient(
            playerId,
            "PortalArrivalPrepared",
            {
                "position": targetFootPos,
                "token": request["clientEngineReadyToken"],
            },
        )
        self._entry_trace(
            "entry.direct.engine_ready.waiting",
            playerId=playerId,
            position=targetFootPos,
            fallbackAtTick=request["clientEngineReadyFallbackTick"],
        )
        return True

    def _prepare_staged_portal_relocation(self, playerId, request):
        """Wait beyond DimensionChangeFinish before moving to real chunks."""
        request["bootstrapEntry"] = False
        request["recovery"] = True
        request["stagedRelocationPending"] = True
        request["state"] = "staging_arrived"
        request["nextAttemptTick"] = (
            self._tick + DIMENSION_NATIVE_COMPONENT_GRACE_TICKS
        )
        request["expires"] = (
            self._tick + config.PORTAL_ARRIVAL_TIMEOUT_TICKS
        )
        request["expiresAt"] = (
            self._portal_now_seconds()
            + config.PORTAL_ARRIVAL_TIMEOUT_SECONDS
        )
        for key in (
            "destinationOrigin",
            "destinationSurface",
            "destinationExit",
            "readyTick",
        ):
            request.pop(key, None)
        self._entry_trace(
            "entry.bootstrap.staging_ready",
            playerId=playerId,
            destinationXZ=request.get("destinationXZ"),
            relocateAtTick=request["nextAttemptTick"],
        )
        return True

    def _hold_staged_portal_entry(self, playerId, request):
        """Keep a staged player stationary while real destination loads."""
        if "stagingOriginalGravity" not in request:
            try:
                gravityComp = CF.CreateGravity(playerId)
                originalGravity = gravityComp.GetGravity()
                if originalGravity is None:
                    originalGravity = 0.0
                result = gravityComp.SetGravity(
                    float(config.PORTAL_STAGING_GRAVITY)
                )
                if result is not False:
                    request["stagingOriginalGravity"] = float(
                        originalGravity
                    )
            except Exception as exc:
                self._entry_trace(
                    "entry.bootstrap.gravity.exception",
                    playerId=playerId,
                    error=repr(exc),
                )
        try:
            result = CF.CreateActorMotion(playerId).SetPlayerMotion(
                (0.0, 0.0, 0.0)
            )
            if result is not False:
                request["stagingMotionHeld"] = True
            return result
        except Exception as exc:
            self._entry_trace(
                "entry.bootstrap.motion.exception",
                playerId=playerId,
                error=repr(exc),
            )
            return False

    def _release_staged_portal_hold(self, playerId, request):
        """Restore movement settings after relocation or cancellation."""
        originalGravity = request.pop("stagingOriginalGravity", None)
        motionHeld = request.pop("stagingMotionHeld", False)
        if originalGravity is not None:
            try:
                CF.CreateGravity(playerId).SetGravity(
                    float(originalGravity)
                )
            except Exception as exc:
                self._entry_trace(
                    "entry.bootstrap.gravity_restore.exception",
                    playerId=playerId,
                    error=repr(exc),
                )
        if not motionHeld:
            return
        try:
            CF.CreateActorMotion(playerId).SetPlayerMotion(
                (0.0, 0.0, 0.0)
            )
        except Exception as exc:
            self._entry_trace(
                "entry.bootstrap.motion_clear.exception",
                playerId=playerId,
                error=repr(exc),
            )

    def _relocate_staged_portal_entry(
        self, playerId, request, targetFootPos
    ):
        targetFootPos = tuple(float(value) for value in targetFootPos)
        if request.get("directEntry"):
            enteredAt = request.get("directEntryFootPos")
            if enteredAt is None:
                return False
            enteredChunk = (
                int(math.floor(float(enteredAt[0]))) >> 4,
                int(math.floor(float(enteredAt[2]))) >> 4,
            )
            targetChunk = (
                int(math.floor(float(targetFootPos[0]))) >> 4,
                int(math.floor(float(targetFootPos[2]))) >> 4,
            )
            if enteredChunk != targetChunk:
                self._entry_trace(
                    "entry.direct.vertical_adjust.rejected",
                    playerId=playerId,
                    enteredAt=enteredAt,
                    position=targetFootPos,
                    reason="cross_chunk",
                )
                return False
            self._entry_trace(
                "entry.direct.vertical_adjust",
                playerId=playerId,
                enteredAt=enteredAt,
                position=targetFootPos,
            )
        self._entry_trace(
            "entry.bootstrap.relocate.call",
            playerId=playerId,
            position=targetFootPos,
        )
        try:
            result = CF.CreatePos(playerId).SetPos(targetFootPos)
        except Exception as exc:
            self._entry_trace(
                "entry.bootstrap.relocate.exception",
                playerId=playerId,
                error=repr(exc),
            )
            return False
        self._entry_trace(
            "entry.bootstrap.relocate.result",
            playerId=playerId,
            result=result,
        )
        if result is False:
            return False
        request["stagedRelocationPending"] = False
        request["clientReadyPending"] = True
        request["clientReady"] = False
        request["clientReadyToken"] = "%d:%d" % (
            int(self._portal_area_sequence),
            int(self._tick),
        )
        request["clientReadyDeadlineTick"] = (
            self._tick + config.PORTAL_CLIENT_READY_TIMEOUT_TICKS
        )
        request["relocationFootPos"] = targetFootPos
        request["state"] = "client_loading"
        request["nextAttemptTick"] = self._tick + 1
        self.NotifyToClient(
            playerId,
            "PortalArrivalRelocated",
            {
                "position": targetFootPos,
                "token": request["clientReadyToken"],
            },
        )
        self._notify(
            playerId,
            u"\u76ee\u6807\u5df2\u5b9a\u4f4d\uff0c\u6b63\u5728\u7b49\u5f85\u5ba2\u6237\u7aef\u5b8c\u6210\u6e32\u67d3\u2026\u2026",
            "AQUA",
        )
        return True

    def _schedule_portal_client_release(self, request, fallback=False):
        """End the movement hold after a bounded client render settle."""
        request["clientReadyPending"] = False
        request["clientReady"] = True
        request["clientReadyFallback"] = bool(fallback)
        request["clientReadyReleaseTick"] = (
            self._tick + config.PORTAL_CLIENT_RENDER_SETTLE_TICKS
        )
        request["nextAttemptTick"] = request["clientReadyReleaseTick"]
        return request["clientReadyReleaseTick"]

    def _prepare_bootstrap_portal_recovery(self, playerId, request, targetPos):
        if targetPos is None:
            targetPos = request.get("bootstrapFootPos")
        if targetPos is None:
            return False
        destinationX = int(math.floor(float(targetPos[0])))
        destinationZ = int(math.floor(float(targetPos[2])))
        surfaceY = int(math.floor(float(targetPos[1]) - 1.0))
        request["sourceSurface"] = (
            (destinationX, surfaceY, destinationZ),
            (destinationX + 1, surfaceY, destinationZ),
            (destinationX, surfaceY, destinationZ + 1),
            (destinationX + 1, surfaceY, destinationZ + 1),
        )
        request["destinationXZ"] = (destinationX, destinationZ)
        request["recovery"] = True
        request["state"] = "queued"
        request["nextAttemptTick"] = self._tick
        request["expires"] = (
            self._tick + config.PORTAL_ARRIVAL_TIMEOUT_TICKS
        )
        request["expiresAt"] = (
            self._portal_now_seconds()
            + config.PORTAL_ARRIVAL_TIMEOUT_SECONDS
        )
        for key in (
            "destinationOrigin",
            "destinationSurface",
            "destinationExit",
            "readyTick",
        ):
            request.pop(key, None)
        self._notify(
            playerId,
            u"\u5df2\u8fdb\u5165\u66ae\u8272\u7ef4\u5ea6\uff0c\u6b63\u5728\u5f53\u524d\u843d\u70b9\u8865\u5efa\u8fd4\u7a0b\u95e8\u2026\u2026",
            "AQUA",
        )
        return True

    def _queue_portal_recovery(
        self,
        playerId,
        targetPos=None,
        returnPoint=None,
    ):
        if playerId in self._pending_portal_entries:
            return True
        if self._get_dimension(playerId) != config.DIMENSION_ID:
            return False
        targetPos = targetPos or self._get_foot_pos(playerId)
        if targetPos is None:
            return False

        point = self._clean_return_point(
            returnPoint or self._return_point_for_player(playerId)
        )
        if point is None:
            point = {
                "dimensionId": 0,
                "pos": (
                    float(targetPos[0]),
                    float(targetPos[1]),
                    float(targetPos[2]),
                ),
            }
            self._store_return_point(playerId, point)

        portalOrigin = point.get("portalOrigin")
        if portalOrigin is not None:
            portalOrigin = tuple(portalOrigin)
            existing = self._portal_surface(
                portalOrigin,
                config.DIMENSION_ID,
            )
            if (
                existing
                and self._ensure_portal_exit(
                    existing,
                    config.DIMENSION_ID,
                )
                is not None
            ):
                self._remember_portal_link(
                    existing,
                    config.DIMENSION_ID,
                    point,
                )
                print (
                    "[TwilightBossSlice] portal recovery reused:",
                    playerId,
                    portalOrigin,
                )
                return True

        destinationX = int(math.floor(float(targetPos[0])))
        destinationZ = int(math.floor(float(targetPos[2])))
        surfaceY = int(math.floor(float(targetPos[1]) - 1.0))
        sourceSurface = (
            (destinationX, surfaceY, destinationZ),
            (destinationX + 1, surfaceY, destinationZ),
            (destinationX, surfaceY, destinationZ + 1),
            (destinationX + 1, surfaceY, destinationZ + 1),
        )
        entryStartedAt = self._portal_now_seconds()
        self._pending_portal_entries[playerId] = {
            "sourceDimensionId": point["dimensionId"],
            "sourceSurface": sourceSurface,
            "returnPoint": point,
            "destinationXZ": (destinationX, destinationZ),
            "entryStartedAt": entryStartedAt,
            "worldgenPerfStart": self._worldgen_perf_snapshot(),
            "recovery": True,
            "state": "queued",
            "nextAttemptTick": self._tick,
            "expires": (
                self._tick + config.PORTAL_ARRIVAL_TIMEOUT_TICKS
            ),
            "expiresAt": (
                entryStartedAt
                + config.PORTAL_ARRIVAL_TIMEOUT_SECONDS
            ),
        }
        print (
            "[TwilightBossSlice] portal recovery queued:",
            playerId,
            (destinationX, destinationZ),
            point["dimensionId"],
        )
        self._notify(
            playerId,
            u"\u6b63\u5728\u6062\u590d\u66ae\u8272\u7ef4\u5ea6\u8fd4\u7a0b\u95e8\u2026\u2026",
            "AQUA",
        )
        return True

    def _process_portal_recovery_players(self):
        for playerId in list(self._pending_portal_recovery_players):
            if playerId in self._pending_portal_entries:
                self._pending_portal_recovery_players.discard(playerId)
                continue
            if self._get_dimension(playerId) != config.DIMENSION_ID:
                self._pending_portal_recovery_players.discard(playerId)
                continue
            if self._queue_portal_recovery(playerId):
                self._pending_portal_recovery_players.discard(playerId)

    def _ensure_portal_exit(self, surface, dimensionId):
        destinationExit = self._portal_exit(surface, dimensionId)
        if destinationExit is not None:
            return destinationExit
        getBlock = self._portal_block_getter(dimensionId)
        for edge in portal_logic.exit_edges(surface, getBlock):
            self._set_block(
                (edge[0], edge[1] + 1, edge[2]),
                "minecraft:air",
                dimensionId,
            )
            self._set_block(
                (edge[0], edge[1] + 2, edge[2]),
                "minecraft:air",
                dimensionId,
            )
            destinationExit = self._portal_exit(surface, dimensionId)
            if destinationExit is not None:
                return destinationExit
        return None

    def _make_return_portal(self, origin, dimensionId=config.DIMENSION_ID):
        originX, originY, originZ = origin
        existing = self._portal_surface(origin, dimensionId)
        if existing:
            return bool(self._ensure_portal_exit(existing, dimensionId))

        portalCells = set(
            (
                (originX, originY, originZ),
                (originX + 1, originY, originZ),
                (originX, originY, originZ + 1),
                (originX + 1, originY, originZ + 1),
            )
        )
        edgeCells = set()
        for pos in portalCells:
            for dx, dz in portal_logic.HORIZONTAL:
                neighbor = (pos[0] + dx, pos[1], pos[2] + dz)
                if neighbor not in portalCells:
                    edgeCells.add(neighbor)

        for x in range(originX - 2, originX + 4):
            for z in range(originZ - 2, originZ + 4):
                self._set_block(
                    (x, originY - 1, z),
                    "minecraft:dirt",
                    dimensionId,
                )
                self._set_block(
                    (x, originY, z),
                    "minecraft:grass",
                    dimensionId,
                )
                self._set_block((x, originY + 1, z), "minecraft:air", dimensionId)
                self._set_block((x, originY + 2, z), "minecraft:air", dimensionId)
        for pos in edgeCells:
            self._set_block(pos, "minecraft:grass", dimensionId)
            self._set_block(
                (pos[0], pos[1] + 1, pos[2]),
                "minecraft:blue_orchid",
                dimensionId,
            )
        for pos in portalCells:
            self._set_block(
                pos,
                config.PORTAL_IDENTIFIER,
                dimensionId,
            )
        # ModSDK can return None even when a write was rejected. Read the
        # finished frame and body clearance back instead of trusting writes.
        surface = self._portal_surface(origin, dimensionId)
        return bool(
            surface
            and self._ensure_portal_exit(surface, dimensionId) is not None
        )

    def _remember_portal_link(self, surface, dimensionId, returnPoint):
        for pos in surface or ():
            self._portal_links[
                (dimensionId, int(pos[0]), int(pos[1]), int(pos[2]))
            ] = copy.deepcopy(returnPoint)

    def _portal_link(self, surface, dimensionId):
        for pos in surface or ():
            point = self._portal_links.get(
                (dimensionId, int(pos[0]), int(pos[1]), int(pos[2]))
            )
            if point is not None:
                return copy.deepcopy(point)
        return None

    def _dropped_item(self, itemEntityId):
        try:
            return CF.CreateItem(LEVEL_ID).GetDroppedItem(itemEntityId)
        except Exception:
            return None

    def _consume_catalyst(self, itemEntityId, item, dimensionId, pos):
        count = max(1, int(item.get("count", 1)))
        try:
            removed = self.DestroyEntity(itemEntityId)
            if removed is False:
                return False
        except Exception as exc:
            print "[TwilightBossSlice] catalyst removal failed:", exc
            return False
        if count > 1:
            remainder = copy.deepcopy(item)
            remainder["count"] = count - 1
            try:
                self.CreateEngineItemEntity(remainder, dimensionId, pos)
            except Exception as exc:
                print "[TwilightBossSlice] catalyst remainder failed:", exc
        return True

    def _prepare_portal_fire_cleanup(self, center, dimensionId):
        centerX = int(math.floor(float(center[0])))
        centerY = int(math.floor(float(center[1])))
        centerZ = int(math.floor(float(center[2])))
        radius = config.PORTAL_LIGHTNING_FIRE_RADIUS
        verticalRadius = config.PORTAL_LIGHTNING_FIRE_VERTICAL_RADIUS
        positions = []
        existingFire = set()
        for x in range(centerX - radius, centerX + radius + 1):
            for y in range(
                centerY - verticalRadius,
                centerY + verticalRadius + 1,
            ):
                for z in range(centerZ - radius, centerZ + radius + 1):
                    pos = (x, y, z)
                    positions.append(pos)
                    if portal_logic.block_name(
                        self._get_block(pos, dimensionId)
                    ) in ("minecraft:fire", "minecraft:soul_fire"):
                        existingFire.add(pos)
        return {
            "dimensionId": dimensionId,
            "positions": tuple(positions),
            "existingFire": existingFire,
            "expires": (
                self._tick + config.PORTAL_LIGHTNING_FIRE_CLEANUP_TICKS
            ),
        }

    def _process_portal_fire_cleanups(self):
        remaining = []
        for cleanup in self._portal_fire_cleanups:
            dimensionId = cleanup["dimensionId"]
            existingFire = cleanup["existingFire"]
            for pos in cleanup["positions"]:
                if pos in existingFire:
                    continue
                if portal_logic.block_name(
                    self._get_block(pos, dimensionId)
                ) in ("minecraft:fire", "minecraft:soul_fire"):
                    self._set_block(pos, "minecraft:air", dimensionId)
            if self._tick < cleanup["expires"]:
                remaining.append(cleanup)
        self._portal_fire_cleanups = remaining

    def _activate_portal(self, itemEntityId, pending, item, surface):
        dimensionId = pending["dimensionId"]
        itemPos = pending["pos"]
        placed = []
        for pos in surface:
            if self._set_block(pos, config.PORTAL_IDENTIFIER, dimensionId) is False:
                for placedPos in placed:
                    self._set_block(placedPos, "minecraft:water", dimensionId)
                return False
            placed.append(pos)
        if not self._consume_catalyst(
            itemEntityId, item, dimensionId, itemPos
        ):
            for placedPos in placed:
                self._set_block(placedPos, "minecraft:water", dimensionId)
            return False
        fireCleanup = self._prepare_portal_fire_cleanup(
            itemPos,
            dimensionId,
        )
        try:
            command = "/summon lightning_bolt %s %s %s" % (
                itemPos[0],
                itemPos[1],
                itemPos[2],
            )
            commandResult = CF.CreateCommand(LEVEL_ID).SetCommand(command)
            if commandResult is not False:
                self._portal_fire_cleanups.append(fireCleanup)
        except Exception:
            pass
        playerId = pending.get("playerId")
        if playerId is not None:
            self._notify(playerId, u"\u66ae\u8272\u4f20\u9001\u95e8\u5df2\u6fc0\u6d3b\u3002", "AQUA")
        return True

    def _process_portal_catalysts(self):
        if self._tick % config.PORTAL_SCAN_INTERVAL_TICKS != 0:
            return
        for itemEntityId, pending in list(self._pending_catalysts.items()):
            if self._tick > pending["expires"]:
                self._pending_catalysts.pop(itemEntityId, None)
                continue
            item = self._dropped_item(itemEntityId)
            if not item:
                continue
            if portal_logic.item_name(item) != config.PORTAL_CATALYST:
                self._pending_catalysts.pop(itemEntityId, None)
                continue
            itemPos = self._get_foot_pos(itemEntityId)
            dimensionId = self._get_dimension(itemEntityId)
            if itemPos is None or dimensionId is None:
                continue
            pending["pos"] = itemPos
            pending["dimensionId"] = dimensionId
            blockX = int(math.floor(itemPos[0]))
            blockZ = int(math.floor(itemPos[2]))
            candidateYs = (
                int(math.floor(itemPos[1])),
                int(math.floor(itemPos[1] - 0.25)),
                int(math.floor(itemPos[1] - 1.0)),
            )
            activated = False
            getter = self._portal_block_getter(dimensionId)
            for blockY in candidateYs:
                start = (blockX, blockY, blockZ)
                if not portal_logic.is_water(getter(start)):
                    continue
                surface = portal_logic.collect_enclosed_surface(
                    start,
                    getter,
                    portal_logic.WATER_BLOCKS,
                    config.PORTAL_IDENTIFIER,
                    config.PORTAL_MIN_SIZE,
                    config.PORTAL_MAX_SIZE,
                )
                if surface:
                    activated = self._activate_portal(
                        itemEntityId, pending, item, surface
                    )
                    break
            if activated:
                self._pending_catalysts.pop(itemEntityId, None)

    def _quest_ram_state(self, entityId):
        default = {"mask": 0, "rewarded": False}
        try:
            extra = CF.CreateExtraData(entityId)
            value = extra.GetExtraData("tf_slice:quest_ram_state_v1")
            if isinstance(value, dict):
                return {
                    "mask": int(value.get("mask", 0)),
                    "rewarded": bool(value.get("rewarded", False)),
                    "lootDeliveryKey": value.get("lootDeliveryKey"),
                }
        except Exception:
            pass
        return default

    def _save_quest_ram_state(self, entityId, state):
        try:
            extra = CF.CreateExtraData(entityId)
            extra.SetExtraData(
                "tf_slice:quest_ram_state_v1",
                {
                    "mask": int(state["mask"]),
                    "rewarded": bool(state["rewarded"]),
                    "lootDeliveryKey": state.get("lootDeliveryKey"),
                },
                False,
            )
            return extra.SaveExtraData()
        except Exception as error:
            print "[TwilightBossSlice] Quest Ram state save failed:", error
            return False

    def _nearby_quest_rams(self, itemEntityId):
        filters = {
            "any_of": [
                {
                    "test": "is_family",
                    "subject": "other",
                    "value": "quest_ram",
                }
            ]
        }
        try:
            return CF.CreateGame(LEVEL_ID).GetEntitiesAround(
                itemEntityId,
                16,
                filters,
            ) or []
        except Exception:
            return []

    @staticmethod
    def _block_name(block):
        if isinstance(block, dict):
            return str(block.get("name", ""))
        if isinstance(block, (tuple, list)) and block:
            return str(block[0])
        return ""

    def _quest_wool_is_settled(self, itemPos, dimensionId):
        blockPos = (
            int(math.floor(itemPos[0])),
            int(math.floor(itemPos[1])),
            int(math.floor(itemPos[2])),
        )
        current = self._block_name(
            self._get_block(blockPos, dimensionId)
        )
        if current in WATER_BLOCKS:
            return True
        below = self._block_name(
            self._get_block(
                (blockPos[0], blockPos[1] - 1, blockPos[2]),
                dimensionId,
            )
        )
        return bool(below and below not in SIGHT_PASSABLE_BLOCKS)

    def _quest_ram_can_see_wool(
        self,
        ramPos,
        itemPos,
        dimensionId,
    ):
        start = (ramPos[0], ramPos[1] + 1.35, ramPos[2])
        end = (itemPos[0], itemPos[1] + 0.2, itemPos[2])
        for blockPos in quest_ram_logic.ray_samples(start, end):
            blockName = self._block_name(
                self._get_block(blockPos, dimensionId)
            )
            if blockName and blockName not in SIGHT_PASSABLE_BLOCKS:
                return False
        return True

    def _navigate_quest_ram_to_wool(
        self,
        ramId,
        itemPos,
        pending,
    ):
        if self._tick - int(pending.get("lastNavTick", -20)) < 10:
            return True
        pending["lastNavTick"] = self._tick

        def callback(entityId, result):
            return None

        try:
            moveComp = CF.CreateMoveTo(ramId)
            moveComp.SetMoveSetting(
                tuple(float(value) for value in itemPos),
                1.0,
                config.NAVIGATION_MAX_ITERATIONS,
                callback,
            )
            ramPos = self._get_foot_pos(ramId)
            if ramPos is not None:
                self._look_along(
                    ramId,
                    itemPos[0] - ramPos[0],
                    itemPos[2] - ramPos[2],
                )
            return True
        except Exception as error:
            print "[TwilightBossSlice] Quest Ram navigation failed:", error
            return False

    def _save_reward_deliveries(self, records):
        extra = CF.CreateExtraData(LEVEL_ID)
        extra.SetExtraData("tf_slice:reward_deliveries_v1", records, False)
        return bool(extra.SaveExtraData())

    def _fill_reward_chest(self, position, dimensionId, table):
        if self._set_block(position, "minecraft:chest", dimensionId) is False:
            return False
        if table == "":
            return True
        return bool(self._block_comp.SetChestLootTable(position, dimensionId, table))

    def _put_reward_chest_item(self, item, dimensionId, position, slot):
        return bool(CF.CreateItem(LEVEL_ID).SpawnItemToContainer(
            item, slot, position, dimensionId,
        ))

    def _reward_queue(self):
        queue = getattr(self, "_loot_reward_delivery", None)
        if queue is None:
            # Do not overwrite persisted deliveries if reading ExtraData fails.
            saved = CF.CreateExtraData(LEVEL_ID).GetExtraData(
                "tf_slice:reward_deliveries_v1"
            )
            queue = reward_delivery.RewardDelivery(
                saved, self._save_reward_deliveries, self._fill_reward_chest,
                self.CreateEngineItemEntity, self._put_reward_chest_item,
            )
            self._loot_reward_delivery = queue
        return queue

    def _queue_loot_reward(self, state, kind, position, table, items, containerItems=False):
        if position is None or len(position) != 3:
            return False
        if not state.get("lootDeliveryKey"):
            state["lootDeliveryKey"] = kind + ":" + uuid.uuid4().hex
        queue = self._reward_queue()
        accepted = queue.submit(
            state["lootDeliveryKey"],
            int(state.get("dimensionId", config.DIMENSION_ID)),
            tuple(int(math.floor(value)) for value in position), table, items,
            container_items=containerItems,
        )
        queue.flush()
        return accepted

    def _flush_reward_deliveries(self):
        if self._tick % 20 != 0:
            return
        try:
            self._reward_queue().flush()
        except Exception as error:
            print "[TwilightBossSlice] Reward delivery deferred:", error

    def _award_minoshroom_items(self, entityId, state):
        return self._queue_loot_reward(
            state, "minoshroom", self._get_foot_pos(entityId) or state.get("home"),
            "", reward_delivery.minoshroom_items(
                state.get("lastLootingLevel", 0), random,
            ),
            containerItems=True,
        )

    def _drop_quest_ram_rewards(self, ramId):
        position = self._get_foot_pos(ramId)
        dimensionId = self._get_dimension(ramId)
        if position is None or dimensionId is None:
            return False
        state = self._quest_ram_state(ramId)
        state["dimensionId"] = dimensionId
        accepted = self._queue_loot_reward(
            state, "quest_ram", position, None,
            [reward_delivery.item(name, 1) for name in quest_ram_logic.REWARD_ITEMS],
        )
        self._save_quest_ram_state(ramId, state)
        return accepted

    def _notify_quest_ram_progress(self, playerId, result):
        if playerId is None:
            return
        if result["reward_due"]:
            self._notify(
                playerId,
                u"\u4efb\u52a1\u7f8a\u5df2\u96c6\u9f50 16 \u8272\u7f8a\u6bdb\uff01",
                "GOLD",
            )
            return
        collected = bin(int(result["mask"])).count("1")
        self._notify(
            playerId,
            u"\u4efb\u52a1\u7f8a\u6536\u4e0b\u4e86\u7f8a\u6bdb\uff1a%d/16"
            % collected,
            "AQUA",
        )

    def _accept_quest_ram_wool(self, ramId, color, playerId=None):
        state = self._quest_ram_state(ramId)
        result = quest_ram_logic.feed_wool(
            state["mask"],
            state["rewarded"],
            color,
        )
        if not result["accepted"]:
            return None
        if not self._save_quest_ram_state(ramId, result):
            return None
        if result["reward_due"]:
            self._drop_quest_ram_rewards(ramId)
        self._notify_quest_ram_progress(playerId, result)
        return result

    def _process_quest_ram_offerings(self):
        if self._tick % 5 != 0:
            return
        for itemEntityId, pending in list(
            self._pending_quest_offerings.items()
        ):
            expires = pending.get("expires")
            if expires is not None and self._tick > expires:
                self._pending_quest_offerings.pop(itemEntityId, None)
                continue
            item = self._dropped_item(itemEntityId)
            if not item:
                self._pending_quest_offerings.pop(itemEntityId, None)
                continue
            itemName = portal_logic.item_name(item)
            color = quest_ram_logic.WOOL_ITEMS.get(itemName)
            if color is None:
                self._pending_quest_offerings.pop(itemEntityId, None)
                continue
            itemPos = self._get_foot_pos(itemEntityId)
            dimensionId = self._get_dimension(itemEntityId)
            if itemPos is None or dimensionId != config.DIMENSION_ID:
                continue
            settled = self._quest_wool_is_settled(
                itemPos,
                dimensionId,
            )
            if not settled:
                continue
            candidates = self._nearby_quest_rams(itemEntityId)
            if not candidates:
                continue
            candidates.sort(
                key=lambda entityId: _distance_sq(
                    self._get_foot_pos(entityId) or itemPos,
                    itemPos,
                )
            )
            selected = None
            for ramId in candidates:
                ramPos = self._get_foot_pos(ramId)
                if ramPos is None:
                    continue
                state = self._quest_ram_state(ramId)
                preview = quest_ram_logic.feed_wool(
                    state["mask"],
                    state["rewarded"],
                    color,
                )
                if not preview["accepted"]:
                    continue
                visible = self._quest_ram_can_see_wool(
                    ramPos,
                    itemPos,
                    dimensionId,
                )
                if visible:
                    selected = (ramId, ramPos)
                    break
            if selected is None:
                continue
            ramId, ramPos = selected
            distanceSq = _distance_sq(ramPos, itemPos)
            if not quest_ram_logic.can_consume_wool(
                distanceSq,
                settled,
                True,
            ):
                self._navigate_quest_ram_to_wool(
                    ramId,
                    itemPos,
                    pending,
                )
                continue
            if not self._consume_catalyst(
                itemEntityId,
                item,
                dimensionId,
                itemPos,
            ):
                continue
            playerId = pending.get("playerId")
            self._accept_quest_ram_wool(ramId, color, playerId)
            self._pending_quest_offerings.pop(itemEntityId, None)

    def _register_tiny_bird(self, entityId, dimensionId=None):
        if entityId in self._tiny_birds:
            return
        self._tiny_birds[entityId] = {
            "dimensionId": (
                dimensionId
                if dimensionId is not None
                else self._get_dimension(entityId)
            ),
            "landed": True,
            "flightTicks": 0,
            "target": None,
            "spookedUntil": 0,
        }

    def _discover_small_entity_runtime(self):
        if self._tick % 100 != 0:
            return
        for entityId, actor in self._loaded_actors():
            identifier = (
                actor.get("identifier")
                if isinstance(actor, dict)
                else None
            )
            if identifier is None:
                identifier = self._get_engine_type(entityId)
            if identifier == TINY_BIRD_IDENTIFIER:
                self._register_tiny_bird(entityId)
            elif identifier == PENGUIN_IDENTIFIER:
                self._penguins.add(entityId)
            elif identifier in ITEM_ENTITY_IDENTIFIERS:
                self._pending_quest_offerings.setdefault(
                    entityId,
                    {"playerId": None, "expires": None},
                )

    def _player_holds_tiny_bird_seed(self, playerId):
        carried = self._carried_item(playerId) or {}
        carriedName = portal_logic.item_name(carried)
        if carriedName in forest_animal_logic.SEED_ITEMS:
            return True
        try:
            itemComp = CF.CreateItem(playerId)
            posType = serverApi.GetMinecraftEnum().ItemPosType.OFFHAND
            offhand = itemComp.GetPlayerItem(posType, 0, True) or {}
            return (
                portal_logic.item_name(offhand)
                in forest_animal_logic.SEED_ITEMS
            )
        except Exception:
            return False

    def _nearest_tiny_bird_player_item(
        self,
        birdPos,
        dimensionId,
    ):
        nearest = None
        nearestDistance = 16.0
        for playerId in list(self._known_players):
            if self._get_dimension(playerId) != dimensionId:
                continue
            playerPos = self._get_foot_pos(playerId)
            if playerPos is None:
                continue
            distanceSq = _distance_sq(birdPos, playerPos)
            if distanceSq >= nearestDistance:
                continue
            nearest = playerId
            nearestDistance = distanceSq
        if nearest is None:
            return ()
        if self._player_holds_tiny_bird_seed(nearest):
            return ("minecraft:wheat_seeds",)
        carried = self._carried_item(nearest) or {}
        return (portal_logic.item_name(carried) or "minecraft:air",)

    def _is_water_at(self, pos, dimensionId):
        blockPos = tuple(int(math.floor(value)) for value in pos)
        return (
            self._block_name(self._get_block(blockPos, dimensionId))
            in WATER_BLOCKS
        )

    def _is_landable_below(self, pos, dimensionId):
        blockPos = (
            int(math.floor(pos[0])),
            int(math.floor(pos[1] - 0.05)),
            int(math.floor(pos[2])),
        )
        blockName = self._block_name(
            self._get_block(blockPos, dimensionId)
        )
        return bool(
            blockName and blockName not in SIGHT_PASSABLE_BLOCKS
        )

    def _tiny_bird_target_is_valid(self, target, dimensionId):
        if target is None or target[1] <= 0.0:
            return False
        blockPos = tuple(int(math.floor(value)) for value in target)
        blockName = self._block_name(
            self._get_block(blockPos, dimensionId)
        )
        return not blockName or blockName in SIGHT_PASSABLE_BLOCKS

    def _take_off_tiny_bird(self, entityId, state, pos):
        state["landed"] = False
        state["flightTicks"] = 0
        state["target"] = None
        self._trigger_entity_event(entityId, "tf_slice:take_off")
        self._play_world_sound(
            "tf_slice.tiny_bird.takeoff",
            pos,
            0.05,
            random.uniform(0.6, 0.8),
        )

    def _land_tiny_bird(self, entityId, state):
        state["landed"] = True
        state["flightTicks"] = 0
        state["target"] = None
        self._trigger_entity_event(entityId, "tf_slice:land")
        try:
            motionComp = CF.CreateActorMotion(entityId)
            motion = motionComp.GetMotion() or (0.0, 0.0, 0.0)
            motionComp.SetMotion(
                (float(motion[0]), 0.0, float(motion[2]))
            )
        except Exception:
            pass

    def _update_tiny_birds(self):
        for entityId, state in list(self._tiny_birds.items()):
            pos = self._get_foot_pos(entityId)
            dimensionId = self._get_dimension(entityId)
            if pos is None or dimensionId is None:
                self._tiny_birds.pop(entityId, None)
                continue
            state["dimensionId"] = dimensionId
            landable = self._is_landable_below(pos, dimensionId)
            playerItems = self._nearest_tiny_bird_player_item(
                pos,
                dimensionId,
            )
            spooked = forest_animal_logic.is_tiny_bird_spooked(
                self._tick < int(state.get("spookedUntil", 0)),
                playerItems,
            )
            if state.get("landed", True):
                takeOff = (
                    forest_animal_logic.should_tiny_bird_take_off(
                        spooked=spooked,
                        in_water=self._is_water_at(pos, dimensionId),
                        landable=landable,
                        random_roll=random.randrange(200),
                    )
                )
                if takeOff:
                    self._take_off_tiny_bird(entityId, state, pos)
                continue

            state["flightTicks"] = int(state.get("flightTicks", 0)) + 1
            target = state.get("target")
            if not self._tiny_bird_target_is_valid(
                target,
                dimensionId,
            ):
                target = None
            if (
                target is None
                or random.randrange(30) == 0
                or forest_animal_logic.target_reached(pos, target, 2.0)
            ):
                target = forest_animal_logic.tiny_bird_target(
                    pos,
                    state["flightTicks"],
                    (
                        random.randrange(7),
                        random.randrange(7),
                        random.randrange(6),
                        random.randrange(7),
                        random.randrange(7),
                    ),
                )
                state["target"] = target
            try:
                motionComp = CF.CreateActorMotion(entityId)
                current = motionComp.GetMotion() or (0.0, 0.0, 0.0)
                if (
                    landable
                    and abs(float(pos[1]) - round(float(pos[1]))) < 0.2
                ):
                    current = (
                        float(current[0]),
                        0.1,
                        float(current[2]),
                    )
                motion = forest_animal_logic.tiny_bird_motion(
                    current,
                    pos,
                    target,
                )
                motionComp.SetMotion(motion)
                CF.CreateRot(entityId).SetRot(
                    (0.0, forest_animal_logic.flight_yaw(motion))
                )
            except Exception:
                continue
            if forest_animal_logic.should_tiny_bird_land(
                landable
                and abs(float(pos[1]) - round(float(pos[1]))) < 0.2,
                random.randrange(10),
            ):
                self._land_tiny_bird(entityId, state)

    def _update_penguins(self):
        for entityId in list(self._penguins):
            pos = self._get_foot_pos(entityId)
            dimensionId = self._get_dimension(entityId)
            if pos is None or dimensionId is None:
                self._penguins.discard(entityId)
                continue
            try:
                motionComp = CF.CreateActorMotion(entityId)
                current = motionComp.GetMotion() or (0.0, 0.0, 0.0)
                onGround = self._is_landable_below(pos, dimensionId)
                slowed = forest_animal_logic.penguin_slow_fall(
                    current,
                    onGround,
                )
                if slowed != tuple(float(value) for value in current):
                    motionComp.SetMotion(slowed)
            except Exception:
                continue

    def _get_health(self, entityId, fallback):
        try:
            attrType = serverApi.GetMinecraftEnum().AttrType.HEALTH
            return max(
                0.0, float(CF.CreateAttr(entityId).GetAttrValue(attrType))
            )
        except Exception:
            return float(fallback)

    def _target_armor_points(self, entityId):
        try:
            attrType = serverApi.GetMinecraftEnum().AttrType.ARMOR
            return max(0.0, float(CF.CreateAttr(entityId).GetAttrValue(attrType)))
        except Exception:
            pass
        if self._is_online_player(entityId):
            try:
                itemPos = serverApi.GetMinecraftEnum().ItemPosType.ARMOR
                armor = CF.CreateItem(entityId).GetPlayerAllItems(itemPos, True) or ()
                return float(sum(1 for item in armor if item))
            except Exception:
                pass
        return 0.0

    def _set_health(self, entityId, value):
        try:
            attrType = serverApi.GetMinecraftEnum().AttrType.HEALTH
            return CF.CreateAttr(entityId).SetAttrValue(
                attrType, float(value)
            )
        except Exception as exc:
            print "[TwilightBossSlice] SetAttrValue failed:", exc
            return False

    def _set_health_cap(self, entityId, maxHealth):
        try:
            attrType = serverApi.GetMinecraftEnum().AttrType.HEALTH
            comp = CF.CreateAttr(entityId)
            comp.SetAttrMaxValue(attrType, float(maxHealth))
            comp.SetAttrValue(attrType, float(maxHealth))
            return True
        except Exception as exc:
            print "[TwilightBossSlice] health setup failed:", exc
            return False

    def _set_health_max(self, entityId, maxHealth):
        try:
            attrType = serverApi.GetMinecraftEnum().AttrType.HEALTH
            return CF.CreateAttr(entityId).SetAttrMaxValue(
                attrType, float(maxHealth)
            )
        except Exception as exc:
            print "[TwilightBossSlice] health max setup failed:", exc
            return False

    def _load_naga_state(self, entityId):
        try:
            value = CF.CreateExtraData(entityId).GetExtraData(
                NAGA_STATE_EXTRA_KEY
            )
        except Exception:
            return None
        if not isinstance(value, dict):
            return None
        home = value.get("home")
        try:
            if home is None or len(home) != 3:
                return None
            return {
                "home": tuple(float(component) for component in home),
                "dimensionId": int(value.get("dimensionId")),
                "health": max(0.0, float(value.get("health"))),
                "ticksSinceDamaged": max(
                    0, int(value.get("ticksSinceDamaged", 0))
                ),
                "brain": value.get("brain"),
                "stunless": bool(value.get("stunless", False)),
                "lastLootingLevel": max(0, int(value.get("lastLootingLevel", 0))),
                "lootDeliveryKey": value.get("lootDeliveryKey"),
                "participants": set(
                    str(playerId)
                    for playerId in value.get("participants", ())
                    if playerId not in (None, "")
                ),
                "dying": bool(value.get("dying", False)),
                "deathTime": max(0, int(value.get("deathTime", 0))),
                "lootAwarded": bool(value.get("lootAwarded", False)),
                "dead": bool(value.get("dead", False)),
                "worldgenManaged": bool(
                    value.get("worldgenManaged", False)
                ),
            }
        except (TypeError, ValueError):
            return None

    def _save_naga_state(self, entityId, state):
        if entityId is None or state is None or state.get("home") is None:
            return False
        try:
            value = {
                "home": [float(component) for component in state["home"]],
                "dimensionId": int(
                    state.get("dimensionId", config.DIMENSION_ID)
                ),
                "health": float(state.get("health", 0.0)),
                "ticksSinceDamaged": max(
                    0, int(state.get("ticksSinceDamaged", 0))
                ),
                "brain": state["brain"].snapshot(),
                "stunless": bool(state.get("stunless", False)),
                "lastLootingLevel": max(0, int(state.get("lastLootingLevel", 0))),
                "lootDeliveryKey": state.get("lootDeliveryKey"),
                "participants": sorted(
                    str(playerId)
                    for playerId in state.get("participants", ())
                ),
                "dying": bool(state.get("dying", False)),
                "deathTime": max(0, int(state.get("deathTime", 0))),
                "lootAwarded": bool(state.get("lootAwarded", False)),
                "dead": bool(state.get("dead", False)),
                "worldgenManaged": bool(
                    state.get("worldgenManaged", False)
                ),
            }
            extra = CF.CreateExtraData(entityId)
            extra.SetExtraData(NAGA_STATE_EXTRA_KEY, value, False)
            return extra.SaveExtraData()
        except Exception as exc:
            print "[TwilightBossSlice] Naga state save failed:", exc
            return False

    def _trigger_entity_event(self, entityId, eventName):
        if not self._valid_entity_id(entityId):
            return False
        try:
            comp = CF.CreateEntityEvent(entityId)
            return comp.TriggerCustomEvent(entityId, eventName)
        except Exception as exc:
            print "[TwilightBossSlice] entity event failed:", eventName, exc
            return False

    def _set_entity_property(self, entityId, propertyName, value):
        try:
            comp = CF.CreateQueryVariable(entityId)
            # Bool properties require a native bool. A "true"/"false"
            # string takes the expression path and is rejected by the engine.
            encoded = value if isinstance(value, bool) else str(value)
            return comp.SetPropertyValue(propertyName, encoded)
        except Exception as exc:
            print (
                "[TwilightBossSlice] entity property failed:",
                propertyName,
                exc,
            )
            return False

    def _push_state_property(self, bossId, brainState):
        stateId = STATE_IDS.get(brainState, 0)
        self._trigger_entity_event(
            bossId, "tf_slice:set_state_%d" % stateId
        )

    def _set_naga_idle_ai(self, bossId, state, enabled):
        enabled = bool(enabled)
        if state.get("idleAiEnabled") == enabled:
            return True
        eventName = (
            "tf_slice:enable_idle_ai"
            if enabled
            else "tf_slice:disable_idle_ai"
        )
        result = self._trigger_entity_event(bossId, eventName)
        if result is False:
            return False
        state["idleAiEnabled"] = enabled
        return True

    def _broadcast_segment_bursts(self, bossId, dimensionId, positions):
        if not positions:
            return
        self.BroadcastToAllClient(
            "NagaSegmentBurst",
            {
                "id": str(bossId),
                "dimensionId": int(dimensionId),
                "positions": [tuple(pos) for pos in positions],
            },
        )

    def _broadcast_combat_effect(
        self, dimensionId, position, effectKind
    ):
        if position is None or dimensionId is None:
            return
        self.BroadcastToAllClient(
            "NagaCombatEffect",
            {
                "dimensionId": int(dimensionId),
                "position": tuple(position),
                "kind": str(effectKind),
            },
        )

    def _broadcast_naga_death_effect(
        self, dimensionId, effectKind, positions, bossId
    ):
        positions = [tuple(position) for position in positions if position]
        if dimensionId is None or not positions:
            return
        self.BroadcastToAllClient(
            "NagaDeathEffect",
            {
                "id": str(bossId),
                "dimensionId": int(dimensionId),
                "kind": str(effectKind),
                "positions": positions,
            },
        )

    def _broadcast_beetle_effect(
        self, dimensionId, effectKind, positions
    ):
        if dimensionId is None or not positions:
            return
        self.BroadcastToAllClient(
            "BeetleCombatEffect",
            {
                "dimensionId": int(dimensionId),
                "kind": str(effectKind),
                "positions": [tuple(position) for position in positions],
            },
        )

    def _register_boss(self, bossId, dimensionId=None, home=None):
        if bossId is None:
            return None
        persistent = self._load_naga_state(bossId)
        observedHome = home
        if persistent is not None:
            observedHome = persistent.get("home") or observedHome
        if observedHome is None:
            observedHome = self._get_foot_pos(bossId)
        existingKey = self._boss_key(bossId)
        existing = (
            self._bosses.get(existingKey)
            if existingKey is not None
            else None
        )
        if existing is not None:
            existing["actorLoaded"] = True
            existing["missingActorTicks"] = 0
            if existing.get("home") is None and observedHome is not None:
                existing["home"] = tuple(observedHome)
            if existing.get("dimensionId") is None and dimensionId is not None:
                existing["dimensionId"] = dimensionId
            self._save_naga_state(existingKey, existing)
            return existing
        if len(self._bosses) >= config.MAX_ACTIVE_BOSSES:
            return None
        resolvedDimension = dimensionId
        if persistent is not None:
            resolvedDimension = persistent.get("dimensionId", resolvedDimension)
        if resolvedDimension is None:
            resolvedDimension = self._get_dimension(bossId)
        if self._home_conflicts(observedHome, resolvedDimension, bossId):
            return None
        difficulty = self._difficulty()
        maxHealth = naga_logic.max_health_for_difficulty(
            difficulty
        )
        health = maxHealth
        ticksSinceDamaged = 0
        if persistent is not None:
            health = min(maxHealth, persistent.get("health", maxHealth))
            ticksSinceDamaged = persistent.get("ticksSinceDamaged", 0)
        dying = bool(persistent and persistent.get("dying"))
        dead = bool(persistent and persistent.get("dead"))
        if dying or dead:
            health = 0.0
        segments = naga_logic.segment_count(health, maxHealth)
        state = {
            "brain": naga_logic.NagaBrain.from_snapshot(
                persistent.get("brain") if persistent else None,
                random.Random(),
            ),
            "home": tuple(observedHome) if observedHome is not None else None,
            "waypoint": None,
            "targetId": None,
            "health": health,
            "maxHealth": maxHealth,
            "dead": dead,
            "segments": segments,
            "segmentIds": [None] * naga_logic.MAX_SEGMENTS,
            "segmentBurstTicks": {},
            "dimensionId": resolvedDimension,
            "difficulty": difficulty,
            "ticksSinceDamaged": ticksSinceDamaged,
            "contactReadyTick": 0,
            "bodyContactReadyTicks": {},
            "stunless": bool(
                persistent and persistent.get("stunless", False)
            ),
            "suppressDamageEvents": 0,
            "navDestination": None,
            "navIssuedTick": 0,
            "navGeneration": 0,
            "navResult": None,
            "waypointBestDistance": None,
            "stuckTicks": 0,
            "headStrafe": 0.0,
            "returningHome": False,
            "combatStarted": False,
            "idleAiEnabled": None,
            "idleWaypointIndex": 0,
            "idlePauseUntilTick": 0,
            "dazeRecoilStopTick": 0,
            "lastSegmentHeadPos": None,
            "segmentPoseOffsets": None,
            "segmentPoseRotations": None,
            "segmentPoseUntilTick": 0,
            "noTargetTicks": 0,
            "lastLootingLevel": int(persistent.get("lastLootingLevel", 0)) if persistent else 0,
            "lootDeliveryKey": persistent.get("lootDeliveryKey") if persistent else None,
            "participants": set(
                persistent.get("participants", ()) if persistent else ()
            ),
            "dying": dying,
            "deathTime": int(
                persistent.get("deathTime", 0) if persistent else 0
            ),
            "lootAwarded": bool(
                persistent and persistent.get("lootAwarded", False)
            ),
            "worldgenManaged": bool(
                persistent and persistent.get("worldgenManaged", False)
            ),
            "missingActorTicks": 0,
            "actorLoaded": True,
        }
        self._bosses[bossId] = state
        self._set_health_max(bossId, maxHealth)
        self._set_health(bossId, 1.0 if dying else health)
        self._save_naga_state(bossId, state)
        self._push_state_property(
            bossId, naga_logic.CHARGE if dying else naga_logic.CIRCLE
        )
        self._enable_mob_hit_detection(bossId)
        self._set_naga_idle_ai(
            bossId, state, not dying and not dead
        )
        return state

    def _get_rotation(self, entityId):
        try:
            rotation = CF.CreateRot(entityId).GetRot()
            if rotation is None:
                return (0.0, 0.0)
            return (float(rotation[0]), float(rotation[1]))
        except Exception:
            return (0.0, 0.0)

    def _spawn_segment(self, bossId, state, index, pos, yaw):
        try:
            segmentId = self.CreateEngineEntityByTypeStr(
                SEGMENT_IDENTIFIER,
                tuple(pos),
                (0.0, float(yaw)),
                state["dimensionId"],
                False,
                False,
            )
        except Exception as exc:
            print "[TwilightBossSlice] Naga segment spawn failed:", index, exc
            segmentId = None
        if not segmentId:
            return None
        state["segmentIds"][index] = segmentId
        self._segment_owners[segmentId] = (bossId, index)
        return segmentId

    def _spawn_ruin_entity(self, identifier, pos, yaw, dimensionId):
        try:
            entityId = self.CreateEngineEntityByTypeStr(
                str(identifier),
                tuple(pos),
                (0.0, float(yaw)),
                int(dimensionId),
                False,
                False,
            )
            if not self._valid_entity_id(entityId):
                return None
            return entityId
        except Exception as error:
            print "[TwilightBossSlice] ruin mob spawn failed:", identifier, error
            return None

    @staticmethod
    def _valid_entity_id(entityId):
        return entityId not in (None, "", -1, "-1")

    @staticmethod
    def _tower_position_key(position):
        return "%d,%d,%d" % tuple(int(math.floor(value)) for value in position)

    def _load_dark_tower_runtime(self):
        try:
            value = self._progress_extra.GetExtraData(
                DARK_TOWER_STATE_EXTRA_KEY
            )
        except Exception:
            value = None
        if not isinstance(value, dict):
            value = {}
        traps = value.get("ghastTraps")
        mechanisms = value.get("mechanisms")
        self._ghast_traps = copy.deepcopy(traps) if isinstance(traps, dict) else {}
        loadedMechanisms = (
            copy.deepcopy(mechanisms) if isinstance(mechanisms, dict) else {}
        )
        # Java's Antibuilder blockData is an in-memory proximity snapshot. It
        # is deliberately discarded outside the 16-block player range and is
        # never serialized with every builder-path checkpoint.
        self._dark_tower_mechanisms = dict(
            (key, record)
            for key, record in loadedMechanisms.items()
            if not (
                isinstance(record, dict)
                and record.get("kind") == "antibuilder"
            )
        )

    def _persistent_dark_tower_mechanisms(self):
        result = {}
        for key, record in self._dark_tower_mechanisms.items():
            if (
                isinstance(record, dict)
                and record.get("kind") == "antibuilder"
            ):
                continue
            result[key] = copy.deepcopy(record)
        return result

    def _save_dark_tower_runtime(self):
        persistentTraps = copy.deepcopy(self._ghast_traps)
        for trap in persistentTraps.values():
            trap.pop("_effectTargets", None)
        try:
            return bool(
                self._progress_extra.SetExtraData(
                    DARK_TOWER_STATE_EXTRA_KEY,
                    {
                        "ghastTraps": persistentTraps,
                        "mechanisms": self._persistent_dark_tower_mechanisms(),
                    },
                    False,
                )
            )
        except Exception as error:
            print "[TwilightBossSlice] Dark Tower state save failed:", error
            return False

    @staticmethod
    def _block_event_position(args):
        for keys in (
            ("x", "y", "z"),
            ("blockX", "blockY", "blockZ"),
            ("posX", "posY", "posZ"),
        ):
            if all(key in args for key in keys):
                try:
                    return tuple(int(args[key]) for key in keys)
                except (TypeError, ValueError):
                    return None
        for key in ("position", "pos"):
            value = args.get(key)
            if value is None or len(value) != 3:
                continue
            try:
                return tuple(int(value[index]) for index in range(3))
            except (TypeError, ValueError):
                return None
        return None

    def _dark_tower_event_position(self, args):
        return self._block_event_position(args)

    def _ghast_trap_powered(self, position, dimensionId):
        # Includes redstone_wire, torches, levers, buttons and powered repeaters.
        return self._adjacent_redstone_powered(
            position, dimensionId
        )

    def _capture_antibuilder_snapshot(self, position, dimensionId):
        snapshot = {}
        for current in dark_tower_logic.antibuilder_snapshot_positions(position):
            block = self._get_block(current, dimensionId)
            name = self._block_name(block) or "minecraft:air"
            snapshot[self._tower_position_key(current)] = name
        return snapshot

    def _dark_tower_builder_powered(self, position, dimensionId):
        """Accept direct power or power relayed through the authored pad."""
        return any(
            self._fire_swamp_device_powered(probe, dimensionId)
            for probe in dark_tower_logic.builder_power_probe_positions(
                position
            )
        )

    def _set_builder_block_state(self, position, dimensionId, builderState):
        if self._block_state_comp is None:
            return False
        states = self._fire_swamp_block_states(position, dimensionId)
        states["tf_slice:builder_state"] = str(builderState)
        try:
            return self._block_state_comp.SetBlockStates(
                tuple(position), states, int(dimensionId)
            )
        except Exception:
            return False

    def _set_temporary_builder_active(self, position, dimensionId, active):
        if self._block_state_comp is None:
            return False
        states = self._fire_swamp_block_states(position, dimensionId)
        states["tf_slice:active"] = bool(active)
        try:
            return self._block_state_comp.SetBlockStates(
                tuple(position), states, int(dimensionId)
            )
        except Exception:
            return False

    def _arm_next_builder_cleanup(self, record, dimensionId):
        builtBlocks = list(record.get("builtBlocks") or ())
        index = int(record.get("cleanupIndex", 0))
        if not (0 <= index < len(builtBlocks)):
            return False
        position = tuple(builtBlocks[index].get("position", ()))
        if len(position) != 3:
            return False
        if self._block_name(
            self._get_block(position, dimensionId)
        ) != "tf_slice:temporary_builder_block":
            return False
        return self._set_temporary_builder_active(
            position, dimensionId, True
        ) is not False

    def _tick_dark_tower_block_entity(self, args):
        blockName = str(args.get("blockName", args.get("fullName", "")))
        if blockName not in (
            "tf_slice:carminite_builder",
            "tf_slice:carminite_antibuilder",
            "tf_slice:carminite_reactor",
            "tf_slice:experiment_115",
            "tf_slice:ghast_trap",
        ):
            return False
        position = self._dark_tower_event_position(args)
        if position is None:
            return False
        dimensionId = int(
            args.get(
                "dimensionId",
                args.get("dimension", config.DIMENSION_ID),
            )
        )
        key = self._tower_position_key(position)
        if blockName == "tf_slice:carminite_builder":
            record = self._dark_tower_mechanisms.get(key)
            if not isinstance(record, dict) or record.get("kind") != "builder_power":
                record = dark_tower_logic.create_builder_state(position)
                record["dimensionId"] = dimensionId
                self._dark_tower_mechanisms[key] = record
            record["position"] = list(position)
            record["dimensionId"] = dimensionId

            probeDue = dark_tower_logic.builder_power_probe_due(
                record,
                neighbor_changed=bool(
                    args.get("_builderNeighborChanged", False)
                ),
            )
            powered = bool(record.get("powered"))
            if probeDue:
                powered = self._dark_tower_builder_powered(
                    position, dimensionId
                )

            builderPlayer = record.get("trackedPlayerId")
            if (
                builderPlayer is not None
                and self._get_dimension(builderPlayer) != dimensionId
            ):
                builderPlayer = None
                record["trackedPlayerId"] = None
            if record.get("phase") == "building" and builderPlayer is None:
                nearest = self._nearest_player(
                    position, dimensionId, 16.0
                )
                if nearest is not None:
                    builderPlayer = nearest[0]
                    record["trackedPlayerId"] = builderPlayer
            facing = None
            if builderPlayer is not None:
                pitch, yaw = self._get_rotation(builderPlayer)
                facing = dark_tower_logic.builder_facing_from_rotation(
                    pitch, yaw
                )

            event = dark_tower_logic.advance_builder(
                record, powered, facing
            )
            if event is not None and event.get("kind") == "started":
                self._set_builder_block_state(
                    position, dimensionId, "active"
                )
                nearest = self._nearest_player(
                    position, dimensionId, 16.0
                )
                if nearest is not None:
                    record["trackedPlayerId"] = nearest[0]
                self._broadcast_dark_tower_mechanism_effect(
                    "builder_start", position, dimensionId, 1
                )
            if event is not None and event.get("kind") == "place":
                target = tuple(event.get("position", ()))
                current = self._block_name(
                    self._get_block(target, dimensionId)
                )
                succeeded = (
                    current in (
                        "minecraft:air",
                        "minecraft:cave_air",
                        "minecraft:void_air",
                    )
                    and self._set_block(
                        target,
                        "tf_slice:temporary_builder_block",
                        dimensionId,
                    ) is not False
                )
                dark_tower_logic.complete_builder_placement(
                    record,
                    target,
                    succeeded,
                    restore_block=current or "minecraft:air",
                )
                if succeeded:
                    self._broadcast_dark_tower_mechanism_effect(
                        "builder_path", position, dimensionId, 1
                    )
            if event is not None and event.get("kind") == "cleanup_started":
                self._set_builder_block_state(
                    position,
                    dimensionId,
                    event.get("builderState", "timeout"),
                )
                self._arm_next_builder_cleanup(record, dimensionId)
                self._broadcast_dark_tower_mechanism_effect(
                    "builder_stop", position, dimensionId, 1
                )
            if event is not None and event.get("kind") == "remove":
                target = tuple(event.get("position", ()))
                currentName = self._block_name(
                    self._get_block(target, dimensionId)
                )
                succeeded = True
                if currentName == "tf_slice:temporary_builder_block":
                    succeeded = self._set_block(
                        target,
                        str(event.get("restoreBlock", "minecraft:air")),
                        dimensionId,
                    ) is not False
                dark_tower_logic.complete_builder_removal(
                    record, target, succeeded
                )
                if succeeded:
                    self._arm_next_builder_cleanup(record, dimensionId)
                    self._broadcast_dark_tower_mechanism_effect(
                        "builder_remove", target, dimensionId, 1
                    )
            if event is not None and event.get("kind") in (
                "stopped", "reset", "cleanup_complete"
            ):
                self._set_builder_block_state(
                    position,
                    dimensionId,
                    event.get("builderState", "inactive"),
                )
                if event.get("kind") == "stopped":
                    self._broadcast_dark_tower_mechanism_effect(
                        "builder_stop", position, dimensionId, 1
                    )
            if event is not None:
                self._save_dark_tower_runtime()
            return True
        if blockName == "tf_slice:ghast_trap":
            trap = self._ghast_traps.setdefault(
                key, ur_ghast_logic.create_trap_state(position)
            )
            trap["dimensionId"] = int(dimensionId)
            if self._ur_ghast_logic_tick >= int(
                trap.get("nextPowerCheckTick", 0)
            ):
                trap["nextPowerCheckTick"] = (
                    self._ur_ghast_logic_tick + 4
                )
                previousPowered = bool(
                    trap.get("redstonePowered", False)
                )
                powered = self._ghast_trap_powered(
                    position, dimensionId
                )
                trap["redstonePowered"] = powered
                if powered and not previousPowered:
                    synthetic = copy.deepcopy(args)
                    synthetic["position"] = position
                    synthetic["blockName"] = blockName
                    self._activate_ghast_trap(synthetic)
            return True
        if blockName == "tf_slice:experiment_115":
            self._dark_tower_mechanisms.setdefault(
                key,
                {
                    "kind": "experiment_115",
                    "position": list(position),
                    "state": dark_tower_logic.create_experiment_115_state(),
                },
            )
            return True
        if blockName == "tf_slice:carminite_antibuilder":
            record = self._dark_tower_mechanisms.get(key)
            nearest = self._nearest_player(
                position, dimensionId, 16.0
            )
            if nearest is None:
                if isinstance(record, dict) and record.get("kind") == "antibuilder":
                    self._dark_tower_mechanisms.pop(key, None)
                return True
            if not isinstance(record, dict) or record.get("kind") != "antibuilder":
                record = {
                    "kind": "antibuilder",
                    "position": list(position),
                    "dimensionId": dimensionId,
                    "snapshot": self._capture_antibuilder_snapshot(
                        position, dimensionId
                    ),
                    "tickCount": 0,
                    "slowScan": True,
                    "ticksSinceChange": 0,
                }
                self._dark_tower_mechanisms[key] = record
            record["tickCount"] = int(record.get("tickCount", 0)) + 1
            record.setdefault("slowScan", True)
            record.setdefault("ticksSinceChange", 0)
            if (
                record["slowScan"]
                and record["tickCount"] % 20 != 0
            ):
                return True
            currentBlocks = {}
            for positionKey in sorted(record["snapshot"]):
                values = tuple(int(value) for value in positionKey.split(","))
                currentBlocks[positionKey] = (
                    self._block_name(self._get_block(values, dimensionId))
                    or "minecraft:air"
                )
            restored = 0
            scan = dark_tower_logic.antibuilder_scan(
                record["snapshot"], currentBlocks
            )
            for positionKey, blockName in scan[
                "snapshotUpdates"
            ].items():
                record["snapshot"][positionKey] = blockName
            if scan["hasRevertableDifferences"]:
                record["slowScan"] = False
                record["ticksSinceChange"] = 0
            elif not record["slowScan"]:
                record["ticksSinceChange"] = int(
                    record.get("ticksSinceChange", 0)
                ) + 1
                if record["ticksSinceChange"] > 20:
                    record["slowScan"] = True
            changes = scan["changes"]
            for change in changes[:64]:
                values = tuple(
                    int(value)
                    for value in str(change["position"]).split(",")
                )
                if self._set_block(
                    values, str(change["block"]), dimensionId
                ) is not False:
                    restored += 1
            if restored:
                self._broadcast_dark_tower_mechanism_effect(
                    "antibuilder_restore",
                    record["position"],
                    dimensionId,
                    restored,
                )
            return True
        if blockName == "tf_slice:carminite_reactor":
            record = self._dark_tower_mechanisms.get(key)
            if record is None:
                directions = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
                ready = all(
                    self._block_name(
                        self._get_block(
                            (position[0] + dx, position[1] + dy, position[2] + dz),
                            dimensionId,
                        )
                    ) == "minecraft:redstone_block"
                    for dx, dy, dz in directions
                )
                if ready:
                    self._set_reactor_active_state(
                        position, dimensionId, True
                    )
                    self._dark_tower_mechanisms[key] = {
                        "kind": "reactor",
                        "dimensionId": dimensionId,
                        "state": dark_tower_logic.create_reactor_state(position),
                    }
                    self._broadcast_dark_tower_mechanism_effect(
                        "reactor_start", position, dimensionId, 1
                    )
                    self._save_dark_tower_runtime()
            return True
        return False

    def _set_reactor_active_state(self, position, dimensionId, active):
        if self._block_state_comp is None:
            return False
        states = self._fire_swamp_block_states(position, dimensionId)
        states["tf_slice:active"] = bool(active)
        try:
            return self._block_state_comp.SetBlockStates(
                tuple(position), states, int(dimensionId)
            )
        except Exception:
            return False

    def _reactor_can_transform(
        self, position, dimensionId, requireSolid=False
    ):
        blockName = self._block_name(
            self._get_block(position, dimensionId)
        )
        if not blockName:
            return False
        if blockName in dark_tower_logic.REACTOR_IMMUNE_BLOCKS:
            return False
        if requireSolid and blockName == "minecraft:air":
            return False
        return True

    def _apply_reactor_event(self, record, event):
        state = record.get("state") or {}
        position = tuple(int(value) for value in state.get("position", (0, 0, 0)))
        dimensionId = int(record.get("dimensionId", config.DIMENSION_ID))
        kind = event.get("kind")
        if kind == "fake_ores":
            changed = 0
            for write in dark_tower_logic.reactor_fake_block_writes(
                position
            ):
                targetPosition = tuple(write["position"])
                if not self._reactor_can_transform(
                    targetPosition, dimensionId, requireSolid=True
                ):
                    continue
                if self._set_block(
                    targetPosition, write["block"], dimensionId
                ) is not False:
                    changed += 1
            if changed:
                self._broadcast_dark_tower_mechanism_effect(
                    "reactor_transform",
                    position,
                    dimensionId,
                    changed,
                )
        elif kind in (
            "primary_debris",
            "primary_clear",
            "secondary_clear",
            "secondary_expand",
            "tertiary_clear",
            "tertiary_expand",
        ):
            center = tuple(
                int(value) for value in event.get("center", position)
            )
            radius = max(0, int(event.get("radius", 0)))
            fuzz = int(event.get("fuzz", 0))
            netherTransform = kind in (
                "secondary_expand", "tertiary_expand"
            )
            target = (
                "minecraft:air"
                if kind.endswith("_clear")
                else "tf_slice:reactor_debris"
            )
            changed = 0
            for write in dark_tower_logic.reactor_blob_writes(
                center, radius, fuzz
            ):
                targetPosition = tuple(write["position"])
                if not self._reactor_can_transform(
                    targetPosition,
                    dimensionId,
                    requireSolid=netherTransform,
                ):
                    continue
                if netherTransform:
                    target = (
                        random.choice(
                            dark_tower_logic.REACTOR_NETHER_ORES
                        )
                        if random.randrange(8) == 0
                        else "minecraft:netherrack"
                    )
                currentName = self._block_name(
                    self._get_block(targetPosition, dimensionId)
                )
                if currentName == target:
                    continue
                if self._set_block(
                    targetPosition, target, dimensionId
                ) is False:
                    continue
                changed += 1
                if netherTransform and int(write["fuzz"]) % 3 == 0:
                    above = (
                        targetPosition[0],
                        targetPosition[1] + 1,
                        targetPosition[2],
                    )
                    if self._block_name(
                        self._get_block(above, dimensionId)
                    ) == "minecraft:air":
                        self._set_block(
                            above, "minecraft:fire", dimensionId
                        )
            if changed:
                self._broadcast_dark_tower_mechanism_effect(
                    "reactor_transform",
                    center,
                    dimensionId,
                    changed,
                )
        elif kind == "ambient":
            self._broadcast_dark_tower_mechanism_effect(
                "reactor_ambient",
                position,
                dimensionId,
                int(event.get("counter", 0)),
            )
        elif kind == "explode":
            try:
                CF.CreateExplosion(LEVEL_ID).CreateExplosion(
                    tuple(float(value) + 0.5 for value in position),
                    int(event.get("power", 4)),
                    True,
                    True,
                    None,
                    None,
                )
            except Exception as error:
                print (
                    "[TwilightBossSlice] reactor explosion failed:",
                    position,
                    error,
                )
            self._set_block(position, "minecraft:air", dimensionId)
            self._broadcast_dark_tower_mechanism_effect(
                "reactor_burst", position, dimensionId, 1
            )
            for offset in (state.get("secondary"), state.get("tertiary")):
                for _unused in range(3):
                    ghastId = self._spawn_ruin_entity(
                        MINI_GHAST_IDENTIFIER,
                        tuple(
                            float(position[index])
                            + float(offset[index])
                            - 1.5
                            + random.random() * 3.0
                            for index in range(3)
                        ),
                        random.uniform(0.0, 360.0),
                        dimensionId,
                    )
                    if ghastId:
                        try:
                            CF.CreateEffect(ghastId).AddEffectToEntity(
                                "fire_resistance", 10, 0, False
                            )
                        except Exception:
                            pass

    def _set_reappearing_visual_state(
        self, position, dimensionId, active, vanished
    ):
        if self._block_state_comp is None:
            return False
        blockName = self._block_name(
            self._get_block(position, dimensionId)
        )
        if blockName == "minecraft:air":
            if self._set_block(
                position, "tf_slice:reappearing_block", dimensionId
            ) is False:
                return False
        elif blockName != "tf_slice:reappearing_block":
            return False
        states = self._fire_swamp_block_states(position, dimensionId)
        states["tf_slice:active"] = bool(active)
        states["tf_slice:vanished"] = bool(vanished)
        try:
            return self._block_state_comp.SetBlockStates(
                tuple(position), states, int(dimensionId)
            )
        except Exception:
            return False

    def _update_dark_tower_mechanisms(self):
        changed = False
        for key in list(self._dark_tower_mechanisms):
            record = self._dark_tower_mechanisms.get(key) or {}
            kind = record.get("kind")
            if kind == "reactor":
                events = dark_tower_logic.advance_reactor(record["state"], 1)
                for event in events:
                    self._apply_reactor_event(record, event)
                if record["state"].get("exploded"):
                    self._dark_tower_mechanisms.pop(key, None)
                    changed = True
                    continue
                if events or self._tick % 20 == 0:
                    changed = True
            elif kind == "temporary":
                if self._tick < int(record.get("restoreTick", 0)):
                    continue
                position = tuple(record.get("position", ()))
                if len(position) != 3:
                    self._dark_tower_mechanisms.pop(key, None)
                    changed = True
                    continue
                writeSucceeded = self._set_block(
                    position,
                    str(record.get("restoreBlock", "minecraft:air")),
                    int(record.get("dimensionId", config.DIMENSION_ID)),
                ) is not False
                if not writeSucceeded:
                    continue
                self._dark_tower_mechanisms.pop(key, None)
                changed = True
            elif kind in ("vanishing", "reappearing"):
                position = tuple(record.get("position", ()))
                if len(position) != 3:
                    self._dark_tower_mechanisms.pop(key, None)
                    changed = True
                    continue
                dimensionId = int(
                    record.get("dimensionId", config.DIMENSION_ID)
                )
                phase = str(record.get("phase", "pending_vanish"))
                if phase == "pending_vanish":
                    if self._tick < int(record.get("vanishTick", 0)):
                        continue
                    if kind == "vanishing":
                        writeSucceeded = self._set_block(
                            position, "minecraft:air", dimensionId
                        ) is not False
                        if not writeSucceeded:
                            continue
                        self._dark_tower_mechanisms.pop(key, None)
                        changed = True
                        continue
                    if not self._set_reappearing_visual_state(
                        position, dimensionId, False, True
                    ):
                        continue
                    record["phase"] = "vanished_trace"
                    changed = True
                    continue
                if phase == "vanished":
                    # Migrate durable records created by the previous
                    # air-only implementation without losing their timer.
                    if not self._set_reappearing_visual_state(
                        position, dimensionId, False, True
                    ):
                        continue
                    record["phase"] = "vanished_trace"
                    changed = True
                    continue
                if phase == "vanished_trace":
                    traceActiveTick = int(record.get(
                        "traceActiveTick",
                        int(record.get("restoreTick", 0))
                        - dark_tower_logic.REAPPEARING_GREEN_TRACE_TICKS,
                    ))
                    if self._tick < traceActiveTick:
                        continue
                    if not self._set_reappearing_visual_state(
                        position, dimensionId, True, True
                    ):
                        continue
                    record["phase"] = "active_trace"
                    changed = True
                    continue
                if phase != "active_trace" or self._tick < int(
                    record.get("restoreTick", 0)
                ):
                    continue
                if not self._set_reappearing_visual_state(
                    position, dimensionId, False, False
                ):
                    # Chunk writes can fail while a structure fragment is still
                    # loading. Keep the durable record and retry next tick.
                    continue
                self._dark_tower_mechanisms.pop(key, None)
                changed = True
        if changed:
            self._save_dark_tower_runtime()

    def _set_ghast_trap_active_state(self, trap, active):
        position = tuple(
            int(math.floor(value)) for value in trap.get("position", ())
        )
        if len(position) != 3 or self._block_state_comp is None:
            return False
        dimensionId = int(trap.get("dimensionId", config.DIMENSION_ID))
        states = self._fire_swamp_block_states(position, dimensionId)
        states["tf_slice:active"] = bool(active)
        try:
            return self._block_state_comp.SetBlockStates(
                position, states, dimensionId
            )
        except Exception:
            return False

    def _record_ghast_trap_effect_target(self, trap, position):
        if position is None or len(position) != 3:
            return False
        cleaned = [float(value) for value in position]
        targets = trap.setdefault("_effectTargets", [])
        if any(
            sum((cleaned[index] - current[index]) ** 2 for index in range(3))
            <= 0.01
            for current in targets
        ):
            return False
        if len(targets) >= 13:
            return False
        targets.append(cleaned)
        return True

    def _broadcast_ghast_trap_effect(
        self, trap, kind, ghastPosition=None, targetPositions=None
    ):
        position = trap.get("position") or ()
        if len(position) != 3:
            return
        payload = {
            "dimensionId": int(
                trap.get("dimensionId", config.DIMENSION_ID)
            ),
            "position": list(position),
            "kind": str(kind),
            "charge": int(trap.get("deathCount", 0)),
            "activeTicks": int(trap.get("activeTicks", 0)),
        }
        if ghastPosition is not None and len(ghastPosition) == 3:
            payload["ghastPosition"] = list(ghastPosition)
        rawTargets = (
            targetPositions
            if targetPositions is not None
            else trap.get("_effectTargets", ())
        )
        cleanedTargets = []
        for targetPosition in list(rawTargets or ())[:13]:
            if targetPosition is None or len(targetPosition) != 3:
                continue
            cleanedTargets.append(
                [float(value) for value in targetPosition]
            )
        if cleanedTargets:
            payload["targetPositions"] = cleanedTargets
        self.BroadcastToAllClient("GhastTrapEffect", payload)

    def _broadcast_dark_tower_mechanism_effect(
        self, kind, position, dimensionId, count=0
    ):
        self.BroadcastToAllClient(
            "DarkTowerMechanismEffect",
            {
                "kind": str(kind),
                "position": [float(value) for value in position],
                "dimensionId": int(dimensionId),
                "count": max(0, int(count)),
            },
        )

    def _apply_active_trap_to_loaded_ghasts(self, trap):
        """Pull loaded ghasts which missed AddEntityServerEvent registration."""
        position = trap.get("position") or ()
        if len(position) != 3 or not trap.get("active"):
            return 0
        dimensionId = int(
            trap.get("dimensionId", config.DIMENSION_ID)
        )
        radius = float(ur_ghast_logic.TRAP_ACTIVE_HORIZONTAL_RADIUS)
        height = float(ur_ghast_logic.TRAP_ACTIVE_HEIGHT)
        start = (
            float(position[0]) - radius,
            float(position[1]),
            float(position[2]) - radius,
        )
        end = (
            float(position[0]) + radius + 1.0,
            float(position[1]) + height + 1.0,
            float(position[2]) + radius + 1.0,
        )
        try:
            entityIds = CF.CreateGame(LEVEL_ID).GetEntitiesInSquareArea(
                None, start, end, dimensionId
            ) or ()
        except Exception:
            return 0
        affected = 0
        for entityId in entityIds:
            key = str(entityId)
            # Registered custom mobs are handled once by the normal AI driver.
            if key in self._phantom_urghast_mobs:
                continue
            entityType = self._get_engine_type(entityId)
            if entityType not in (
                "minecraft:ghast",
                MINI_GHAST_IDENTIFIER,
                TOWER_GHAST_IDENTIFIER,
            ):
                continue
            entityPosition = self._get_foot_pos(entityId)
            if entityPosition is None:
                continue
            event = ur_ghast_logic.apply_active_trap_to_ghast(
                trap,
                entityPosition,
                deal_damage=(
                    random.randint(
                        0, ur_ghast_logic.TRAP_DAMAGE_ROLL - 1
                    ) == 0
                ),
            )
            if not event.get("affected"):
                continue
            self._record_ghast_trap_effect_target(
                trap,
                (
                    float(entityPosition[0]),
                    float(entityPosition[1]) + 1.0,
                    float(entityPosition[2]),
                ),
            )
            self._set_full_motion(
                entityId, event.get("motion", (0.0, 0.0, 0.0))
            )
            if event.get("damage", 0.0) > 0.0:
                self._hurt(entityId, event["damage"], None)
            affected += 1
        return affected

    def _update_ghast_traps(self):
        """Advance every charged trap's source-equivalent 120-tick beam."""
        shouldSave = False
        for trap in self._ghast_traps.values():
            if not trap.get("active"):
                if (
                    int(trap.get("deathCount", 0)) > 0
                    and self._ur_ghast_logic_tick % 10 == 0
                ):
                    self._broadcast_ghast_trap_effect(
                        trap, "charged"
                    )
                continue
            if (
                self._ur_ghast_logic_tick
                % ur_ghast_logic.TRAP_FALLBACK_SCAN_INTERVAL == 0
            ):
                self._apply_active_trap_to_loaded_ghasts(trap)
            event = ur_ghast_logic.advance_trap(trap, 1)
            if not event.get("active"):
                self._set_ghast_trap_active_state(trap, False)
                trap["effectStage"] = "idle"
                self._broadcast_ghast_trap_effect(trap, "stop")
                self._play_world_sound(
                    "random.fizz", trap.get("position"), 1.0, 0.8
                )
                shouldSave = True
                continue
            activeTicks = int(trap.get("activeTicks", 0))
            stage = ur_ghast_effect_logic.trap_effect_stage(activeTicks)
            previousStage = str(trap.get("effectStage", "idle"))
            changed = stage != previousStage
            if changed:
                trap["effectStage"] = stage
                soundName = {
                    "warmup": "beacon.activate",
                    "active": "conduit.activate",
                    "spindown": "portal.trigger",
                }.get(stage)
                if soundName:
                    self._play_world_sound(
                        soundName,
                        trap.get("position"),
                        1.0,
                        2.0 if stage != "spindown" else 0.8,
                    )
            interval = ur_ghast_effect_logic.trap_effect_interval(stage)
            if changed or activeTicks % interval == 0:
                self._broadcast_ghast_trap_effect(trap, stage)
                self._entry_trace(
                    "ur_ghast.trap_pull",
                    position=[
                        round(float(value), 3)
                        for value in trap.get("position", ())
                    ],
                    stage=str(stage),
                    activeTicks=activeTicks,
                    targetCount=len(trap.get("_effectTargets", ())),
                )
            if stage == "active" and activeTicks % 20 == 0:
                self._play_world_sound(
                    "conduit.activate", trap.get("position"), 0.4, 2.0
                )
            if changed or self._ur_ghast_logic_tick % 20 == 0:
                shouldSave = True
        if shouldSave:
            self._save_dark_tower_runtime()

    def _active_ghast_trap(self, entityPosition, dimensionId):
        nearest = None
        nearestDistance = None
        for trap in self._ghast_traps.values():
            if int(trap.get("dimensionId", config.DIMENSION_ID)) != int(dimensionId):
                continue
            if not ur_ghast_logic.trap_affects_entity(trap, entityPosition):
                continue
            distance = _distance_sq(trap.get("position"), entityPosition)
            if nearestDistance is None or distance < nearestDistance:
                nearest = trap
                nearestDistance = distance
        return nearest

    def _mount_goblin_knight(self, lowerId, upperId):
        """Recreate LowerGoblinKnight.finalizeSpawn's paired rider."""
        if lowerId is None or upperId is None:
            return False
        try:
            rideComp = CF.CreateRide(lowerId)
            mounted = rideComp.SetRiderRideEntity(upperId, lowerId, 0)
        except Exception:
            mounted = False
        if mounted is False:
            return False
        lowerState = self._phantom_urghast_mobs.get(str(lowerId))
        upperState = self._phantom_urghast_mobs.get(str(upperId))
        if lowerState is not None:
            lowerState["riderId"] = str(upperId)
        if upperState is not None:
            upperState["mountId"] = str(lowerId)
        return mounted is not False

    def _spawn_broodling_companions(self, position, dimensionId):
        count = phantom_urghast_mob_logic.broodling_companion_count(
            True, random.randrange(2)
        )
        self._pending_broodling_children += count
        for index in range(count):
            offset = -0.55 if index == 0 else 0.55
            childId = self._spawn_ruin_entity(
                TOWER_BROODLING_IDENTIFIER,
                (
                    float(position[0]) + offset,
                    float(position[1]),
                    float(position[2]) - offset * 0.5,
                ),
                random.uniform(0.0, 360.0),
                dimensionId,
            )
            if childId is None:
                self._pending_broodling_children = max(
                    0, self._pending_broodling_children - 1
                )

    def _register_phantom_urghast_mob(
        self, entityId, entityType, dimensionId
    ):
        """Bind source-specific temporal AI that Bedrock goals cannot express."""
        if (
            not self._valid_entity_id(entityId)
            or entityType not in PHANTOM_UR_GHAST_MOB_IDENTIFIERS
        ):
            return None
        key = str(entityId)
        existing = self._phantom_urghast_mobs.get(key)
        if existing is not None:
            return existing
        state = phantom_urghast_mob_logic.create_mob_state(entityType)
        state["dimensionId"] = int(dimensionId)
        state["home"] = self._get_foot_pos(entityId)
        state["lastPosition"] = state["home"]
        self._phantom_urghast_mobs[key] = state
        if entityType in goblin_combat.KINDS:
            self._goblin_combat.restore(entityId, state)
        if entityType == LOWER_GOBLIN_KNIGHT_IDENTIFIER:
            for riderId in self._ride_passengers(entityId):
                if self._get_engine_type(riderId) == UPPER_GOBLIN_KNIGHT_IDENTIFIER:
                    self._register_phantom_urghast_mob(riderId, UPPER_GOBLIN_KNIGHT_IDENTIFIER, dimensionId)
                    self._mount_goblin_knight(entityId, riderId)
                    state["pairSpawned"] = True
                    self._goblin_combat.save(entityId, state)
                    return state
            if state.get("pairSpawned"):
                return state
            state["pairSpawned"] = True
            self._goblin_combat.save(entityId, state)
            position = self._get_foot_pos(entityId)
            if position is not None:
                upperId = self._spawn_ruin_entity(
                    UPPER_GOBLIN_KNIGHT_IDENTIFIER,
                    (position[0], position[1] + 0.2, position[2]),
                    self._get_rotation(entityId)[1],
                    dimensionId,
                )
                if upperId is not None:
                    self._register_phantom_urghast_mob(
                        upperId,
                        UPPER_GOBLIN_KNIGHT_IDENTIFIER,
                        dimensionId,
                    )
                    self._mount_goblin_knight(entityId, upperId)
        elif entityType == TOWER_BROODLING_IDENTIFIER:
            if self._pending_broodling_children > 0:
                self._pending_broodling_children -= 1
            else:
                position = self._get_foot_pos(entityId)
                if position is not None:
                    self._spawn_broodling_companions(
                        position, int(dimensionId)
                    )
        return state

    def _launch_goblin_chain(self, ownerId, state, origin, target):
        """Compatibility entry: queue a source-owned throw for the 20 Hz driver."""
        state["throwing"] = True
        state["chainCooldown"] = 100 + random.randrange(100)
        visuals = state.get("goblinVisuals", [])
        return visuals[0] if visuals else None

    def _land_goblin_spear(self, upperId, state, position, targetId, targetPos):
        return self._goblin_combat.land_spear(upperId, state)

    @staticmethod
    def _borer_scan_offset(scanIndex):
        # Stable first 21 cells of the surrounding 3x3x3 source search.
        index = max(0, min(20, int(scanIndex)))
        return (
            (index % 3) - 1,
            ((index // 3) % 3) - 1,
            ((index // 9) % 3) - 1,
        )

    def _advance_borer_wake(self, entityId, state, position):
        remaining = int(state.get("borerWakeRemaining", 0))
        if remaining <= 0:
            return
        scanIndex = phantom_urghast_mob_logic.BORER_WAKE_STEPS - remaining
        offset = self._borer_scan_offset(scanIndex)
        blockPos = tuple(
            int(math.floor(position[index])) + offset[index]
            for index in range(3)
        )
        blockName = self._block_name(
            self._get_block(blockPos, state["dimensionId"])
        )
        kind = {
            "tf_slice:infested_towerwood": "infested",
            "tf_slice:towerwood": "towerwood",
            "tf_slice:cracked_towerwood": "cracked_towerwood",
        }.get(blockName, "empty")
        events = phantom_urghast_mob_logic.advance_borer_summon(
            state, kind
        )
        if blockName != "tf_slice:infested_towerwood" or not events:
            return
        if self._set_block(
            blockPos, "tf_slice:towerwood", state["dimensionId"]
        ) is False:
            return
        self._spawn_ruin_entity(
            TOWERWOOD_BORER_IDENTIFIER,
            (blockPos[0] + 0.5, blockPos[1] + 0.1, blockPos[2] + 0.5),
            random.uniform(0.0, 360.0),
            state["dimensionId"],
        )

    def _sync_route_ghast_charging(self, entityId, state, charging):
        charging = bool(charging)
        if bool(state.get("visualGhastCharging")) == charging:
            return False
        self._trigger_entity_event(
            entityId,
            (
                "tf_slice:start_charging"
                if charging else "tf_slice:stop_charging"
            ),
        )
        state["visualGhastCharging"] = charging
        return True

    def _route_ghast_can_see(self, entityId, targetId, position, targetPos, dimensionId):
        try:
            return bool(
                CF.CreateGame(LEVEL_ID).CanSee(
                    entityId, targetId, 64.0, True, 360.0, 360.0
                )
            )
        except Exception:
            return self._beetle_can_see(position, targetPos, dimensionId)

    def _player_wearing_ghast_pumpkin(self, playerId):
        try:
            itemPos = serverApi.GetMinecraftEnum().ItemPosType.ARMOR
            armor = CF.CreateItem(playerId).GetPlayerAllItems(
                itemPos, True
            ) or ()
            head = armor[0] if armor else None
            return portal_logic.item_name(head) in (
                "minecraft:carved_pumpkin",
                "minecraft:pumpkin",
            )
        except Exception:
            return False

    def _ghast_player_perception(self, playerId):
        key = str(playerId)
        cached = self._ghast_player_perception_cache.get(key)
        if cached is not None and int(cached.get("tick", -1)) == self._ur_ghast_logic_tick:
            return cached
        cached = {
            "tick": self._ur_ghast_logic_tick,
            "position": self._get_foot_pos(playerId),
            "rotation": self._get_rotation(playerId),
            "wearingPumpkin": self._player_wearing_ghast_pumpkin(playerId),
        }
        self._ghast_player_perception_cache[key] = cached
        if len(self._ghast_player_perception_cache) > 32:
            self._ghast_player_perception_cache = {key: cached}
        return cached

    def _player_look_dot_at_ghast(
        self, playerId, playerPos, ghastPos, ghastHeight, rotation=None
    ):
        pitch, yaw = rotation or self._get_rotation(playerId)
        pitch = math.radians(float(pitch))
        yaw = math.radians(float(yaw))
        look = (
            -math.sin(yaw) * math.cos(pitch),
            -math.sin(pitch),
            math.cos(yaw) * math.cos(pitch),
        )
        offset = (
            float(ghastPos[0]) - float(playerPos[0]),
            float(ghastPos[1]) + float(ghastHeight) / 2.0
            - (float(playerPos[1]) + 0.9),
            float(ghastPos[2]) - float(playerPos[2]),
        )
        length = math.sqrt(sum(value * value for value in offset)) or 1.0
        targetLook = tuple(value / length for value in offset)
        return sum(look[index] * targetLook[index] for index in range(3))

    def _spawn_route_ghast_fireball(self, entityId, state, position, targetPos):
        height = 1.0 if state.get("type") == MINI_GHAST_IDENTIFIER else 2.0
        center = (
            float(position[0]),
            float(position[1]) + height / 2.0 + 0.5,
            float(position[2]),
        )
        targetCenter = (
            float(targetPos[0]),
            float(targetPos[1]) + 0.9,
            float(targetPos[2]),
        )
        delta = tuple(targetCenter[index] - center[index] for index in range(3))
        length = math.sqrt(sum(value * value for value in delta)) or 1.0
        direction = tuple(value / length for value in delta)
        spawnPos = tuple(
            center[index] + direction[index] * 4.0 for index in range(3)
        )
        projectileId = self._spawn_ruin_entity(
            "minecraft:fireball",
            spawnPos,
            self._get_rotation(entityId)[1],
            state.get("dimensionId", config.DIMENSION_ID),
        )
        if projectileId is None:
            return None
        self._set_full_motion(
            projectileId, tuple(value * 0.6 for value in direction)
        )
        return projectileId

    def _drive_route_ghast_attack(self, entityId, state, position):
        if self._ur_ghast_logic_tick >= int(
            state.get("ghastPerceptionNextTick", 0)
        ):
            targetId = self._get_attack_target(entityId)
            perception = (
                self._ghast_player_perception(targetId)
                if targetId is not None else {}
            )
            targetPos = perception.get("position")
            hasTarget = targetId is not None and targetPos is not None
            distanceSq = (
                _distance_sq(position, targetPos)
                if hasTarget else 999999.0
            )
            hasSight = bool(
                hasTarget
                and self._route_ghast_can_see(
                    entityId,
                    targetId,
                    position,
                    targetPos,
                    state.get("dimensionId", config.DIMENSION_ID),
                )
            )
            state["ghastPerceptionTargetId"] = targetId
            state["ghastPerceptionTargetPos"] = (
                list(targetPos) if targetPos is not None else None
            )
            state["ghastPerceptionDistanceSq"] = distanceSq
            state["ghastPerceptionSight"] = hasSight
            state["ghastPerceptionPumpkin"] = bool(
                perception.get("wearingPumpkin", False)
            )
            state["ghastPerceptionLookDot"] = (
                self._player_look_dot_at_ghast(
                    targetId,
                    targetPos,
                    position,
                    1.0,
                    perception.get("rotation"),
                ) if hasTarget else -1.0
            )
            state["ghastPerceptionNextTick"] = (
                self._ur_ghast_logic_tick
                + ur_ghast_logic.GHAST_PERCEPTION_REFRESH_INTERVAL
            )
        else:
            targetId = state.get("ghastPerceptionTargetId")
            targetPos = state.get("ghastPerceptionTargetPos")
        hasTarget = targetId is not None and targetPos is not None
        distanceSq = float(
            state.get("ghastPerceptionDistanceSq", 999999.0)
        )
        hasSight = bool(state.get("ghastPerceptionSight", False))
        attackAllowed = hasTarget
        if attackAllowed and state.get("type") == MINI_GHAST_IDENTIFIER:
            attackAllowed = phantom_urghast_mob_logic.mini_ghast_should_attack(
                math.sqrt(distanceSq),
                float(state.get("ghastPerceptionLookDot", -1.0)),
                hasSight,
                bool(state.get("ghastPerceptionPumpkin", False)),
            )
        step = phantom_urghast_mob_logic.advance_ghast_attack(
            state,
            attackAllowed,
            distanceSq < 4096.0,
            hasSight,
        )
        self._sync_route_ghast_charging(
            entityId, state, step.get("charging")
        )
        if hasTarget:
            self._face_yaw_position(entityId, position, targetPos)
        if step.get("warn"):
            self._play_world_sound("mob.ghast.charge", position, 10.0, 0.5)
        if step.get("fire") and targetPos is not None:
            self._play_world_sound("mob.ghast.fireball", position, 10.0, 0.5)
            self._spawn_route_ghast_fireball(
                entityId, state, position, targetPos
            )
            if random.randrange(6) == 0:
                self._reset_attack_target(entityId)
        return step

    def _drive_phantom_urghast_mobs(self, urGhastLogicStep=True):
        for entityKey in list(self._phantom_urghast_mobs):
            state = self._phantom_urghast_mobs.get(entityKey)
            position = self._get_foot_pos(entityKey)
            if state is None:
                self._phantom_urghast_mobs.pop(entityKey, None)
                continue
            if position is None:
                state["positionFailureTicks"] = int(
                    state.get("positionFailureTicks", 0)
                ) + 1
                if int(state["positionFailureTicks"]) >= 3:
                    self._phantom_urghast_mobs.pop(entityKey, None)
                continue
            state["positionFailureTicks"] = 0
            state["lastPosition"] = list(position)
            kind = state.get("type")
            if kind in (MINI_GHAST_IDENTIFIER, TOWER_GHAST_IDENTIFIER):
                if not urGhastLogicStep:
                    continue
                activeTrap = self._active_ghast_trap(
                    position, state.get("dimensionId", config.DIMENSION_ID)
                )
                if activeTrap is not None:
                    phantom_urghast_mob_logic.advance_ghast_attack(
                        state, False, False, False
                    )
                    self._sync_route_ghast_charging(
                        entityKey, state, False
                    )
                    state["ghastPerceptionNextTick"] = 0
                    state["ghastPerceptionTargetId"] = None
                    state["ghastPerceptionTargetPos"] = None
                    self._reset_attack_target(entityKey)
                    self._record_ghast_trap_effect_target(
                        activeTrap,
                        (
                            float(position[0]),
                            float(position[1]) + 1.0,
                            float(position[2]),
                        ),
                    )
                    event = ur_ghast_logic.apply_active_trap_to_ghast(
                        activeTrap,
                        position,
                        deal_damage=(
                            random.randint(
                                0, ur_ghast_logic.TRAP_DAMAGE_ROLL - 1
                            ) == 0
                        ),
                    )
                    self._set_full_motion(
                        entityKey, event.get("motion", (0.0, 0.0, 0.0))
                    )
                    if event.get("damage", 0.0) > 0.0:
                        self._hurt(entityKey, event["damage"], None)
                    continue
                self._drive_route_ghast_attack(entityKey, state, position)
                continue
            if kind in goblin_combat.KINDS:
                if urGhastLogicStep:
                    self._goblin_combat.tick(entityKey, state, position)
            elif kind == TOWERWOOD_BORER_IDENTIFIER:
                self._advance_borer_wake(entityKey, state, position)

    def _set_entity_offhand_item(self, entityId, item):
        try:
            itemPos = serverApi.GetMinecraftEnum().ItemPosType
            return CF.CreateItem(entityId).SetEntityItem(
                itemPos.OFFHAND, item, 0
            )
        except Exception:
            return False

    def _sync_knight_member_equipment(self, entityId, member):
        role = int(member.get("role", 0)) % 3
        if int(member.get("visualRole", -1)) != role:
            weapon = (
                "tf_slice:knightmetal_sword",
                "tf_slice:knightmetal_axe",
                "tf_slice:knightmetal_pickaxe",
            )[role]
            if self._set_entity_carried_item(
                entityId,
                {
                    "newItemName": weapon,
                    "newAuxValue": 0,
                    "count": 1,
                },
            ) is not False:
                self._trigger_entity_event(
                    entityId,
                    (
                        "tf_slice:set_weapon_role_sword",
                        "tf_slice:set_weapon_role_axe",
                        "tf_slice:set_weapon_role_pickaxe",
                    )[role],
                )
                member["visualRole"] = role
        shieldEquipped = bool(member.get("shieldEquipped", False))
        if bool(member.get("visualShield", False)) != shieldEquipped:
            shield = (
                {
                    "newItemName": "tf_slice:knightmetal_shield",
                    "newAuxValue": 0,
                    "count": 1,
                }
                if shieldEquipped else None
            )
            if self._set_entity_offhand_item(entityId, shield) is not False:
                member["visualShield"] = shieldEquipped

    def _broadcast_knight_phantom_effect(
        self, kind, positions, entityId=None, extra=None
    ):
        payload = {
            "kind": str(kind),
            "dimensionId": config.DIMENSION_ID,
            "entityId": str(entityId) if entityId is not None else None,
            "positions": [list(position) for position in positions if position],
        }
        if isinstance(extra, dict):
            payload.update(extra)
        self.BroadcastToAllClient("KnightPhantomEffect", payload)

    def _drive_knight_member_death(
        self, group, member, entityId, position
    ):
        if member.get("deathRestartPending", False):
            member["deathRestartPending"] = False
            self._trigger_entity_event(entityId, "tf_slice:restart_dying")
        if not member.get("deathVisualStarted", False):
            member["deathVisualStarted"] = True
            self._reset_attack_target(entityId)
            self._trigger_entity_event(entityId, "tf_slice:stop_charging")
            self._trigger_entity_event(entityId, "tf_slice:stop_guarding")
            self._broadcast_knight_phantom_effect(
                "death_start", (position,), entityId
            )
        step = knight_route_logic.advance_member_death(
            member,
            1,
            release=bool(group.get("deathSequenceReleased", False)),
        )
        if step.get("ascent"):
            self._set_full_motion(entityId, (0.0, 0.015, 0.0))
        else:
            self._set_full_motion(entityId, (0.0, 0.0, 0.0))
        if step.get("hide"):
            self._trigger_entity_event(entityId, "tf_slice:hide_dying")
            self._broadcast_knight_phantom_effect(
                "death_poof", (position,), entityId
            )
        if step.get("hold") and self._tick % 10 == 0:
            self._broadcast_knight_phantom_effect(
                "death_hold", (position,), entityId
            )
        trailFraction = step.get("trailFraction")
        if trailFraction is not None:
            self._broadcast_knight_phantom_effect(
                "death_trail",
                (position, group.get("home")),
                entityId,
                {"fraction": float(trailFraction)},
            )
        if not step.get("finish"):
            return False
        sourceId = member.get("deathSourceId")
        death = self._ruin_worldgen.record_knight_member_death(
            entityId,
            sourceId if self._is_online_player(sourceId) else None,
        )
        self._knight_phantoms.pop(str(entityId), None)
        if death.get("final"):
            self._finalize_knight_group(death)
        try:
            self.DestroyEntity(entityId)
        except Exception:
            pass
        return True

    def _reconcile_knight_runtime_members(self, group, encounterActive):
        removed = 0
        for member in list(group.get("members", ())):
            entityId = member.get("entityId")
            present = False
            if self._valid_entity_id(entityId):
                position = self._get_foot_pos(entityId)
                if position is not None:
                    try:
                        present = bool(
                            CF.CreateGame(LEVEL_ID).IsEntityAlive(entityId)
                        )
                    except Exception:
                        present = True
            if not knight_route_logic.runtime_member_stale(
                member, present, encounterActive
            ):
                continue
            if not self._valid_entity_id(entityId):
                continue
            death = self._ruin_worldgen.record_knight_member_death(
                entityId, None
            )
            if not death.get("handled"):
                continue
            self._knight_phantoms.pop(str(entityId), None)
            removed += 1
            if death.get("final"):
                self._finalize_knight_group(death)
        return removed

    def _knight_wall_contact(self, position, dimensionId):
        passable = frozenset((
            "minecraft:air",
            "minecraft:cave_air",
            "minecraft:void_air",
            "minecraft:water",
            "minecraft:flowing_water",
        ))
        offsets = (
            (0.0, 0.0),
            (0.75, 0.0),
            (-0.75, 0.0),
            (0.0, 0.75),
            (0.0, -0.75),
        )
        for height in (0.25, 1.25, 2.25):
            for offsetX, offsetZ in offsets:
                blockPosition = (
                    int(math.floor(float(position[0]) + offsetX)),
                    int(math.floor(float(position[1]) + height)),
                    int(math.floor(float(position[2]) + offsetZ)),
                )
                blockName = portal_logic.block_name(
                    self._get_block(blockPosition, dimensionId)
                )
                if blockName and blockName not in passable:
                    return True
        return False

    def _relocate_knight_from_wall(
        self, entityId, currentPosition, escapeDestination
    ):
        rescuePosition = knight_route_logic.wall_escape_relocation(
            currentPosition, escapeDestination
        )
        if tuple(rescuePosition) == tuple(currentPosition):
            return tuple(currentPosition)
        try:
            if CF.CreatePos(entityId).SetPos(rescuePosition) is False:
                return tuple(currentPosition)
        except Exception:
            return tuple(currentPosition)
        return tuple(rescuePosition)

    def _drive_knight_phantoms(self):
        if self._ruin_worldgen is None:
            return
        try:
            groups = self._ruin_worldgen.active_knight_groups()
        except Exception:
            return
        for group in groups:
            home = group.get("home") or ()
            if len(home) != 3:
                continue
            nearest = self._nearest_player(
                home, config.DIMENSION_ID, knight_route_logic.HOME_RADIUS
            )
            if nearest is None:
                targetId, targetPos = None, None
            else:
                targetId, targetPos = nearest
                knight_route_logic.record_participant(group, targetId)
            self._reconcile_knight_runtime_members(
                group, targetId is not None
            )
            knight_route_logic.renumber_living_members(group)
            knight_route_logic.apply_difficulty_equipment(
                group, self._difficulty()
            )
            repairedSlots = set(
                int(member.get("slot", member.get("number", -1)))
                for member in knight_route_logic.repair_environment_damage(
                    group
                )
            )
            for member in group.get("members", ()):
                entityId = member.get("entityId")
                if not entityId or not member.get("alive", True):
                    continue
                memberSlot = int(
                    member.get("slot", member.get("number", -1))
                )
                if memberSlot in repairedSlots:
                    self._set_health(entityId, knight_route_logic.MEMBER_MAX_HEALTH)
                self._sync_knight_member_equipment(entityId, member)
                memberFormation = str(member.get("formation", "hover"))
                charging = knight_route_logic.member_is_charging(member)
                guarding = knight_route_logic.advance_guard(
                    member, targetId is not None, 1
                )
                if bool(member.get("visualGuarding")) != guarding:
                    self._trigger_entity_event(
                        entityId,
                        (
                            "tf_slice:start_guarding"
                            if guarding else "tf_slice:stop_guarding"
                        ),
                    )
                    member["visualGuarding"] = guarding
                if bool(member.get("visualCharging")) != charging:
                    self._trigger_entity_event(
                        entityId,
                        (
                            "tf_slice:start_charging"
                            if charging else "tf_slice:stop_charging"
                        ),
                    )
                    member["visualCharging"] = charging
                position = self._get_foot_pos(entityId)
                if position is None:
                    continue
                if member.get("dying", False):
                    if member.get("visualNoClip", False):
                        self._trigger_entity_event(
                            entityId, "tf_slice:disable_noclip"
                        )
                        member["visualNoClip"] = False
                    self._drive_knight_member_death(
                        group, member, entityId, position
                    )
                    continue
                member["health"] = self._get_health(
                    entityId, member.get("health", 35.0)
                )
                if memberFormation == "attack_player_start" and targetPos is not None:
                    member["chargePos"] = [
                        int(math.floor(float(targetPos[0]))),
                        int(math.floor(float(targetPos[1]))),
                        int(math.floor(float(targetPos[2]))),
                    ]
                    member["chargeVector"] = knight_route_logic.charge_direction(
                        position, member["chargePos"]
                    )
                destination = knight_route_logic.formation_destination(
                    group,
                    member.get("number", 0),
                    targetPos,
                    current_position=position,
                )
                blockedWall = self._knight_wall_contact(
                    position, config.DIMENSION_ID
                )
                escapeActive = knight_route_logic.advance_wall_escape(
                    member,
                    position,
                    destination,
                    targetId is not None,
                    blocked=blockedWall,
                )
                if escapeActive:
                    destination = knight_route_logic.wall_escape_destination(
                        group, member
                    )
                    if blockedWall:
                        position = self._relocate_knight_from_wall(
                            entityId, position, destination
                        )
                noClip = bool(
                    not member.get("dying", False)
                    and (
                        int(member.get("formationTick", 0)) % 20 != 0
                        or escapeActive
                    )
                )
                if bool(member.get("visualNoClip")) != noClip:
                    self._trigger_entity_event(
                        entityId,
                        (
                            "tf_slice:enable_noclip"
                            if noClip else "tf_slice:disable_noclip"
                        ),
                    )
                    member["visualNoClip"] = noClip
                speed = knight_route_logic.knight_move_speed(
                    charging, escapeActive
                )
                chargeDirection = None
                if (
                    not escapeActive
                    and memberFormation == "attack_player_attack"
                    and int(member.get("role", -1)) == knight_route_logic.ROLE_SWORD
                ):
                    chargeDirection = member.get("chargeVector")
                    if not chargeDirection:
                        chargeDirection = knight_route_logic.charge_direction(
                            group.get("home") or position, destination
                        )
                self._set_full_motion(
                    entityId,
                    knight_route_logic.knight_motion_vector(
                        position,
                        destination,
                        speed,
                        charge_direction=chargeDirection,
                    ),
                )
                self._face_position(entityId, position, targetPos or destination)
                if (
                    charging
                    and int(member.get("formationTick", 0)) % 4 == 0
                ):
                    self._broadcast_knight_phantom_effect(
                        "charge_smoke", (position,), entityId
                    )
                if targetId is not None and charging:
                    self._set_attack_target(entityId, targetId)
                elif targetId is None:
                    self._reset_attack_target(entityId)
                if (
                    targetPos is not None
                    and memberFormation == "attack_player_attack"
                    and int(member.get("formationTick", 0)) % 4 == 0
                ):
                    self._spawn_knight_projectiles(
                        entityId, member, position, targetPos
                    )

    def _orient_knight_projectile(
        self, projectileId, motion, fallbackYaw=0.0
    ):
        yaw = knight_route_logic.projectile_yaw_for_motion(
            motion, fallback_yaw=fallbackYaw
        )
        try:
            CF.CreateRot(projectileId).SetRot((0.0, yaw))
        except Exception:
            pass
        return yaw

    def _discard_knight_projectile_tracking(
        self, projectileKey, state=None, destroy=False
    ):
        tracked = self._knight_projectiles.pop(str(projectileKey), None)
        tracked = tracked or state or {}
        projectileId = tracked.get("entityId", projectileKey)
        if destroy and self._valid_entity_id(projectileId):
            try:
                self.DestroyEntity(projectileId)
            except Exception:
                pass
        return projectileId

    def _trim_knight_projectile_registry(self):
        for projectileKey in knight_route_logic.projectile_registry_overflow_keys(
            self._knight_projectiles
        ):
            self._discard_knight_projectile_tracking(
                projectileKey, destroy=True
            )

    def _drive_knight_projectile_rotations(self):
        self._trim_knight_projectile_registry()
        for projectileKey, state in list(self._knight_projectiles.items()):
            if knight_route_logic.projectile_tracking_expired(
                state.get("spawnTick", self._tick), self._tick
            ):
                self._discard_knight_projectile_tracking(
                    projectileKey, state, destroy=True
                )
                continue
            projectileId = state.get("entityId", projectileKey)
            projectileType = self._get_engine_type(projectileId)
            if projectileType not in (
                KNIGHT_AXE_PROJECTILE,
                KNIGHT_PICKAXE_PROJECTILE,
            ):
                self._discard_knight_projectile_tracking(
                    projectileKey, state
                )
                continue
            motion = self._get_full_motion(projectileId)
            state["yaw"] = self._orient_knight_projectile(
                projectileId, motion, state.get("yaw", 0.0)
            )

    def _spawn_knight_projectiles(self, ownerId, member, origin, target):
        patterns = knight_route_logic.projectile_pattern(
            member.get("role", member.get("number", 0)),
            member.get("formationTick", 0),
        )
        if patterns:
            self._broadcast_knight_phantom_effect(
                (
                    "throw_axe"
                    if patterns[0].get("kind") == "axe"
                    else "throw_pick"
                ),
                (origin,),
                ownerId,
            )
        for pattern in patterns:
            projectileType = (
                KNIGHT_AXE_PROJECTILE
                if pattern.get("kind") == "axe"
                else KNIGHT_PICKAXE_PROJECTILE
            )
            launch = knight_route_logic.projectile_launch(
                origin, target, pattern
            )
            projectileId = self._spawn_ruin_entity(
                projectileType,
                launch["spawn"],
                launch["yaw"],
                config.DIMENSION_ID,
            )
            if projectileId:
                self._knight_projectiles[str(projectileId)] = {
                    "entityId": projectileId,
                    "ownerId": str(ownerId),
                    "kind": str(pattern.get("kind", "")),
                    "spawnTick": int(self._tick),
                    "yaw": float(launch["yaw"]),
                }
                self._set_full_motion(
                    projectileId, launch["motion"]
                )
                self._knight_projectiles[str(projectileId)]["yaw"] = (
                    self._orient_knight_projectile(
                        projectileId, launch["motion"], launch["yaw"]
                    )
                )
        self._trim_knight_projectile_registry()

    @staticmethod
    def _destruction_level(item):
        extraId = str((item or {}).get("extraId", ""))
        for marker in ("tf_destruction:", "tf_slice:destruction:"):
            if marker in extraId:
                try:
                    return max(0, min(3, int(extraId.split(marker, 1)[1].split("|", 1)[0])))
                except (TypeError, ValueError):
                    pass
        enchants = (item or {}).get("enchantData", (item or {}).get("enchants", ()))
        if isinstance(enchants, dict):
            return max(0, min(3, int(enchants.get("tf_slice:destruction", 0))))
        return 0

    def _use_block_and_chain(self, args):
        playerId = args.get("playerId", args.get("entityId"))
        item = args.get("itemDict") or args.get("item") or self._carried_item(playerId) or {}
        if portal_logic.item_name(item) != "tf_slice:block_and_chain":
            return False
        if any(str(value.get("ownerId")) == str(playerId) for value in self._block_chain_projectiles.values()):
            args["cancel"] = True
            return True
        position = self._get_foot_pos(playerId)
        dimensionId = self._get_dimension(playerId)
        if position is None or dimensionId is None:
            return False
        rotation = self._get_rotation(playerId)
        pitch = math.radians(float(rotation[0]))
        yaw = math.radians(float(rotation[1]))
        motion = (
            -math.sin(yaw) * math.cos(pitch) * 1.5,
            -math.sin(pitch) * 1.5,
            math.cos(yaw) * math.cos(pitch) * 1.5,
        )
        ownerEyeHeight = 1.62
        spawnPosition = knight_route_logic.block_chain_spawn_position(
            position, rotation, True, ownerEyeHeight
        )
        projectileId = self._spawn_ruin_entity(
            BLOCK_CHAIN_PROJECTILE,
            spawnPosition,
            0.0,
            dimensionId,
        )
        if not projectileId:
            return False
        self._set_full_motion(projectileId, motion)
        chainState = {
            "ownerId": playerId,
            "launchedTick": self._tick,
            "returning": False,
            "destructionLevel": self._destruction_level(item),
            "dimensionId": dimensionId,
            "blocksSmashed": 0,
            "baseMotion": motion,
            "returnAgeOffset": 0,
            "mainHand": True,
            "ownerEyeHeight": ownerEyeHeight,
        }
        self._block_chain_projectiles[str(projectileId)] = chainState
        self._sync_block_chain_visual(
            projectileId, chainState, position, spawnPosition
        )
        args["cancel"] = True
        args["ret"] = True
        self._play_world_sound("random.bow", position, 0.5, 0.9)
        self._entry_trace(
            "knight.block_chain_launched",
            playerId=str(playerId),
            projectileId=str(projectileId),
            position=position,
            motion=motion,
        )
        return True

    def _sync_block_chain_visual(
        self, projectileId, state, ownerPos, projectilePos
    ):
        # Only association crosses the network. Render endpoints are sampled
        # together on each client, including observers in third person.
        if self._tick >= int(state.get("visualRefreshTick", -1)):
            self.BroadcastToAllClient("BlockChainVisual", {
                "projectileId": str(projectileId),
                "ownerId": str(state.get("ownerId")),
                "mainHand": state.get("mainHand", True),
            })
            state["visualRefreshTick"] = self._tick + 15
        return True

    def _instant_remove_chain_entity(self, entityId):
        if not self._valid_entity_id(entityId):
            return False
        self.BroadcastToAllClient("BlockChainVisual", {
            "projectileId": str(entityId), "removed": True,
        })
        if self._trigger_entity_event(
            entityId, "tf_slice:instant_remove"
        ) is not False:
            return True
        try:
            return self.DestroyEntity(entityId) is not False
        except Exception:
            return False

    def _damage_block_and_chain(self, playerId, amount):
        try:
            itemComp = CF.CreateItem(playerId)
            itemPos = serverApi.GetMinecraftEnum().ItemPosType
            for posType in (itemPos.CARRIED, itemPos.OFFHAND):
                item = itemComp.GetPlayerItem(posType, 0, True) or {}
                if portal_logic.item_name(item) != "tf_slice:block_and_chain":
                    continue
                durability = int(itemComp.GetItemDurability(posType, 0))
                return itemComp.SetItemDurability(
                    posType, 0, max(0, durability - max(0, int(amount)))
                ) is not False
        except Exception:
            pass
        return False

    def _drive_block_chain_projectiles(self):
        for projectileId in list(self._block_chain_projectiles):
            state = self._block_chain_projectiles.get(projectileId) or {}
            ownerId = state.get("ownerId")
            position = self._get_foot_pos(projectileId)
            ownerPos = self._get_foot_pos(ownerId)
            if position is None or ownerPos is None:
                ownerState = self._phantom_urghast_mobs.get(str(ownerId))
                if ownerState is not None:
                    ownerState["chainProjectileId"] = None
                self._stop_using_item(ownerId)
                self._block_chain_projectiles.pop(projectileId, None)
                if position is not None:
                    self._instant_remove_chain_entity(projectileId)
                continue
            ownerEye = (
                float(ownerPos[0]),
                float(ownerPos[1])
                + float(state.get("ownerEyeHeight", 1.62)),
                float(ownerPos[2]),
            )
            dx = ownerEye[0] - float(position[0])
            dy = ownerEye[1] - float(position[1])
            dz = ownerEye[2] - float(position[2])
            distance = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
            ageTicks = self._tick - int(
                state.get("launchedTick", self._tick)
            )
            if state.get("mobOwned"):
                state["returning"] = bool(
                    state.get("returning", False) or ageTicks >= 15
                )
            else:
                state["returning"] = (
                    knight_route_logic.block_chain_should_return(
                        state.get("returning", False), distance, ageTicks
                    )
                )
            if not state.get("returning"):
                self._sync_block_chain_visual(
                    projectileId, state, ownerPos, position
                )
                continue
            if distance <= 2.0:
                ownerState = self._phantom_urghast_mobs.get(str(ownerId))
                if ownerState is not None:
                    ownerState["chainProjectileId"] = None
                blockCost = min(
                    int(state.get("blocksSmashed", 0)),
                    knight_route_logic.BLOCK_CHAIN_MAX_BLOCK_DURABILITY_COST,
                )
                if blockCost > 0:
                    self._damage_block_and_chain(ownerId, blockCost)
                self._stop_using_item(ownerId)
                self._block_chain_projectiles.pop(projectileId, None)
                self._instant_remove_chain_entity(projectileId)
                continue
            baseMotion = state.get("baseMotion")
            if baseMotion is None:
                baseMotion = self._get_full_motion(projectileId) or (0, 0, 0)
                state["baseMotion"] = baseMotion
            returnMotion = knight_route_logic.block_chain_return_motion(
                baseMotion,
                ownerEye,
                position,
                ageTicks + int(state.get("returnAgeOffset", 0)),
            )
            self._set_full_motion(
                projectileId,
                returnMotion,
            )
            self._sync_block_chain_visual(
                projectileId, state, ownerPos, position
            )

    def _break_block_chain_impact(self, args, state):
        level = int(state.get("destructionLevel", 0))
        if level <= 0 or str(args.get("hitTargetType", "")).upper() != "BLOCK":
            return
        allowance = knight_route_logic.block_chain_smash_allowance(
            state.get("blocksSmashed", 0)
        )
        if allowance <= 0:
            return
        target = (
            int(args.get("blockPosX", math.floor(args.get("x", 0)))),
            int(args.get("blockPosY", math.floor(args.get("y", 0)))),
            int(args.get("blockPosZ", math.floor(args.get("z", 0)))),
        )
        dimensionId = int(state.get("dimensionId", config.DIMENSION_ID))
        blockName = self._block_name(self._get_block(target, dimensionId))
        if blockName in PROTECTED_BLOCKS or blockName.startswith("tf_slice:"):
            return
        if self._set_block(target, "minecraft:air", dimensionId) is not False:
            state["blocksSmashed"] = int(
                state.get("blocksSmashed", 0)
            ) + 1

    def _save_ur_ghast_state(self, entityId, state):
        serializable = copy.deepcopy(state)
        for transientField in (
            "targetId",
            "visualCharging",
            "visualTracking",
            "engineEntityId",
            "requestedEngineMotion",
            "actualEngineMotion",
            "lastEnginePosition",
            "motionFailureTicks",
            "motionMovingTicks",
            "positionFailureTicks",
            "nextDriverTraceTick",
            "nextDuplicateRegistrationTraceTick",
            "lastSetMotionResult",
            "motionOwner",
        ):
            serializable.pop(transientField, None)
        try:
            return bool(
                CF.CreateExtraData(entityId).SetExtraData(
                    UR_GHAST_STATE_EXTRA_KEY, serializable, False
                )
            )
        except Exception as error:
            print "[TwilightBossSlice] Ur-Ghast state save failed:", error
            return False

    def _ur_ghast_trap_block_valid(self, position, dimensionId):
        if position is None or len(position) != 3:
            return False
        blockPosition = tuple(int(math.floor(value)) for value in position)
        return self._block_name(
            self._get_block(blockPosition, int(dimensionId))
        ) == "tf_slice:ghast_trap"

    def _ur_ghast_route_trap_points(self, state, includeRegistered=True):
        home = state.get("home") or ()
        if len(home) != 3:
            return []
        dimensionId = int(state.get("dimensionId", config.DIMENSION_ID))
        candidates = list(state.get("trapPoints", ()))
        if includeRegistered:
            for trap in self._ghast_traps.values():
                if int(trap.get("dimensionId", config.DIMENSION_ID)) != dimensionId:
                    continue
                candidates.append(trap.get("position"))
        unique = {}
        for position in candidates:
            if position is None or len(position) != 3:
                continue
            point = [float(value) for value in position]
            if _distance_sq(home, point) > ur_ghast_logic.HOME_RADIUS ** 2:
                continue
            if not self._ur_ghast_trap_block_valid(point, dimensionId):
                continue
            key = tuple(int(math.floor(value)) for value in point)
            unique[key] = [float(value) for value in key]
        return sorted(
            unique.values(),
            key=lambda point: (_distance_sq(home, point), tuple(point)),
        )

    def _refresh_ur_ghast_route(
        self, bossId, state, includeRegistered=True, force=False
    ):
        points = self._ur_ghast_route_trap_points(
            state, includeRegistered=includeRegistered
        )
        current = [list(point) for point in state.get("trapPoints", ())]
        if not force and current == points:
            return False
        routeCount = len(points) if points else 5
        routeOrder = list(range(routeCount))
        random.shuffle(routeOrder)
        ur_ghast_logic.refresh_flight_route(state, points, routeOrder)
        self._entry_trace(
            "ur_ghast.route_refreshed",
            bossId=str(bossId),
            trapCount=len(points),
            homeBound=bool(state.get("homeBound", False)),
            waypoints=copy.deepcopy(state.get("waypoints", ())),
            logicTick=int(self._ur_ghast_logic_tick),
        )
        return True

    def _tick_ur_ghast_trap_route(self, bossId, state):
        discovery = int(state.get("trapDiscoveryTicks", 0)) + 1
        prune = int(state.get("trapPruneTicks", 0)) + 1
        includeRegistered = False
        due = False
        if prune >= ur_ghast_logic.TRAP_PRUNE_INTERVAL:
            prune = 0
            due = True
        if discovery >= ur_ghast_logic.TRAP_DISCOVERY_INTERVAL:
            discovery = 0
            includeRegistered = True
            due = True
        state["trapDiscoveryTicks"] = discovery
        state["trapPruneTicks"] = prune
        if not due:
            return False
        return self._refresh_ur_ghast_route(
            bossId,
            state,
            includeRegistered=includeRegistered,
            force=False,
        )

    def _register_ur_ghast(self, entityId, dimensionId):
        if not self._valid_entity_id(entityId):
            return None
        existingKey = entity_registry_logic.matching_entity_key(
            self._ur_ghasts, entityId
        )
        if existingKey is not None:
            existingState = self._ur_ghasts[existingKey]
            existingState["actorLoaded"] = True
            existingState["engineEntityId"] = entityId
            existingState["dimensionId"] = int(dimensionId)
            currentTick = int(getattr(self, "_tick", 0))
            if currentTick >= int(
                existingState.get("nextDuplicateRegistrationTraceTick", 0)
            ):
                existingState["nextDuplicateRegistrationTraceTick"] = (
                    currentTick + 30
                )
                self._entry_trace(
                    "ur_ghast.duplicate_registration_ignored",
                    bossId=str(existingKey),
                    engineEntityId=str(entityId),
                    phase=str(existingState.get("phase", "normal")),
                    wantedWaypoint=existingState.get("wantedWaypoint"),
                    motionOwner=str(
                        existingState.get("motionOwner", "idle")
                    ),
                    attackTimer=int(existingState.get("attackTimer", 0)),
                )
            return existingState
        try:
            stored = CF.CreateExtraData(entityId).GetExtraData(
                UR_GHAST_STATE_EXTRA_KEY
            )
        except Exception:
            stored = None
        position = self._get_foot_pos(entityId)
        context = (
            self._ruin_worldgen.ur_ghast_context(position)
            if self._ruin_worldgen is not None
            else None
        ) or {}
        if isinstance(stored, dict):
            try:
                state = ur_ghast_logic.load_state(stored)
            except ValueError:
                state = None
        else:
            state = None
        homeBound = bool(
            context.get("ledgerKey") is not None
            or context.get("home") is not None
            or (
                state is not None
                and state.get("ledgerKey") is not None
            )
        )
        if state is None:
            home = context.get("home") or position or (0, 0, 0)
            routeCount = len(context.get("trapPoints", ())) or 5
            routeOrder = list(range(routeCount))
            random.shuffle(routeOrder)
            state = ur_ghast_logic.create_state(
                home,
                context.get("trapPoints", ()),
                home_bound=homeBound,
                route_order=routeOrder,
            )
        previousHomeBound = bool(state.get("homeBound", False))
        state["homeBound"] = bool(previousHomeBound or homeBound)
        state["dimensionId"] = int(dimensionId)
        state["ledgerKey"] = context.get(
            "ledgerKey", state.get("ledgerKey")
        )
        state["targetId"] = None
        state["visualCharging"] = False
        state["visualTracking"] = False
        state["visualTrapPitch"] = 0.0
        state["visualPitch"] = 0.0
        state["hurtActive"] = False
        state["hurtUntil"] = 0
        state["hurtUntilLogicTick"] = 0
        state.setdefault("wantedWaypoint", None)
        state["engineEntityId"] = entityId
        state["requestedEngineMotion"] = [0.0, 0.0, 0.0]
        state["actualEngineMotion"] = [0.0, 0.0, 0.0]
        state["lastEnginePosition"] = None
        state["motionFailureTicks"] = 0
        state["motionMovingTicks"] = 0
        state["positionFailureTicks"] = 0
        state["nextDriverTraceTick"] = 0
        state["nextFlightTraceTick"] = 0
        state["nextYawTraceTick"] = 0
        state["visualAttackApplied"] = -1.0
        if state.get("motionAuthority") not in (
            "source_accumulator", "direct_compat"
        ):
            state["motionAuthority"] = "source_accumulator"
        state["motionOwner"] = "idle"
        self._ur_ghasts[str(entityId)] = state
        for trap_position in list(state.get("trapPoints", ())) + list(
            context.get("trapPoints", ())
        ):
            key = self._tower_position_key(trap_position)
            trap = self._ghast_traps.setdefault(
                key, ur_ghast_logic.create_trap_state(trap_position)
            )
            trap["dimensionId"] = int(
                state.get("dimensionId", config.DIMENSION_ID)
            )
        self._refresh_ur_ghast_route(
            entityId,
            state,
            includeRegistered=True,
            force=previousHomeBound != bool(state.get("homeBound", False)),
        )
        try:
            CF.CreateAttr(entityId).SetEntityOnFire(0, 0)
        except Exception:
            pass
        self._set_ur_ghast_engine_health(
            entityId,
            state,
            ur_ghast_logic.authoritative_engine_health(state),
        )
        self._save_ur_ghast_state(entityId, state)
        self._save_dark_tower_runtime()
        return state

    def _ur_ghast_player_candidate(self, position, dimensionId, playerId):
        try:
            gameType = int(
                CF.CreateGame(LEVEL_ID).GetPlayerGameType(playerId)
            )
        except Exception:
            gameType = 0
        if gameType in (1, 3) or self._get_dimension(playerId) != dimensionId:
            return None
        playerPos = self._get_foot_pos(playerId)
        if playerPos is None:
            return None
        distanceSq = _distance_sq(position, playerPos)
        if distanceSq >= ur_ghast_logic.TRACKING_RANGE ** 2:
            return None
        return (distanceSq, playerId, playerPos)

    def _ur_ghast_target(self, position, state):
        dimensionId = int(state.get("dimensionId", config.DIMENSION_ID))
        preferredId = state.get("targetId")
        candidates = []
        for playerId in self._get_online_players():
            candidate = self._ur_ghast_player_candidate(
                position, dimensionId, playerId
            )
            if candidate is None:
                continue
            if preferredId is not None and str(playerId) == str(preferredId):
                return (candidate[1], candidate[2])
            candidates.append(candidate)
        if not candidates:
            return (None, None)
        unusedDistance, playerId, playerPos = min(candidates)
        return (playerId, playerPos)

    def _ur_ghast_can_see(self, bossId, targetId):
        if bossId is None or targetId is None:
            return False
        try:
            return bool(
                CF.CreateGame(LEVEL_ID).CanSee(
                    bossId,
                    targetId,
                    ur_ghast_logic.ATTACK_RANGE,
                    True,
                    360.0,
                    360.0,
                )
            )
        except Exception:
            pass
        origin = self._get_foot_pos(bossId)
        target = self._get_foot_pos(targetId)
        dimensionId = self._get_dimension(bossId)
        if origin is None or target is None or dimensionId is None:
            return False
        start = (
            origin[0],
            origin[1] + ur_ghast_logic.BOSS_HEIGHT / 2.0,
            origin[2],
        )
        end = (target[0], target[1] + 0.9, target[2])
        for blockPos in quest_ram_logic.ray_samples(start, end):
            blockName = self._block_name(
                self._get_block(blockPos, dimensionId)
            )
            if blockName and blockName not in SIGHT_PASSABLE_BLOCKS:
                return False
        return True

    def _sync_ur_ghast_visual(self, bossId, state, visualState):
        visualState = max(0.0, min(2.0, float(visualState)))
        attackTimer = max(
            -40.0,
            min(
                20.0,
                float(
                    state.get(
                        "visualAttackTimer",
                        state.get("attackTimer", 0.0),
                    )
                ),
            ),
        )
        timerResult = self._set_entity_property(
            bossId, "tf_slice:attack_timer", attackTimer
        )
        chargingValue = 1.0 if visualState > 1.5 else 0.0
        if abs(float(state.get("visualAttackApplied", -1.0)) - visualState) <= 0.001:
            return timerResult is not False
        eventName = {
            0: "tf_slice:attack_normal",
            1: "tf_slice:attack_tracking",
            2: "tf_slice:attack_charging",
        }[int(round(visualState))]
        eventResult = self._trigger_entity_event(bossId, eventName)
        propertyResult = self._set_entity_property(
            bossId, "tf_slice:attack_state", visualState
        )
        applied = (
            eventResult is True
            or propertyResult is not False
        )
        if applied:
            state["visualAttackApplied"] = visualState
        self._entry_trace(
            "ur_ghast.attack_visual",
            bossId=str(bossId),
            visualState=visualState,
            attackTimer=attackTimer,
            charging=bool(chargingValue > 0.5),
            chargingValue=chargingValue,
            entityEvent=eventName,
            applied=bool(applied),
        )
        return applied

    def _set_ur_ghast_logical_yaw(
        self, bossId, state, logicalYaw, reason
    ):
        logicalYaw = float(logicalYaw)
        renderYaw = ur_ghast_logic.render_yaw(logicalYaw)
        try:
            result = CF.CreateRot(bossId).SetRot((0.0, renderYaw))
        except Exception:
            result = False
        state["lastValidYaw"] = logicalYaw
        if (
            result is False
            or self._ur_ghast_logic_tick
            >= int(state.get("nextYawTraceTick", 0))
        ):
            state["nextYawTraceTick"] = self._ur_ghast_logic_tick + 20
            actual = self._get_rotation(bossId)
            self._entry_trace(
                "ur_ghast.yaw",
                bossId=str(bossId),
                reason=str(reason),
                logicalYaw=round(logicalYaw, 3),
                renderYaw=round(renderYaw, 3),
                actualYaw=round(float(actual[1]), 3),
                applied=result is not False,
            )
        return result is not False

    def _sync_ur_ghast_visual_pitch(self, bossId, state, value, reason):
        limit = float(ur_ghast_logic.VISUAL_PITCH_LIMIT)
        value = max(-limit, min(limit, float(value)))
        previous = float(state.get("visualPitch", 0.0))
        if abs(previous - value) <= 0.25:
            return False
        if abs(value) <= 0.25:
            self._trigger_entity_event(bossId, "tf_slice:visual_pitch_reset")
        applied = self._set_entity_property(
            bossId, "tf_slice:visual_pitch", value
        ) is not False
        if applied:
            state["visualPitch"] = value
            self._entry_trace(
                "ur_ghast.visual_pitch",
                bossId=str(bossId),
                pitch=round(value, 3),
                reason=str(reason),
            )
        return applied

    def _begin_ur_ghast_hurt_feedback(self, bossId, state):
        state["hurtUntilLogicTick"] = (
            self._ur_ghast_logic_tick
            + ur_ghast_logic.HURT_FEEDBACK_TICKS
        )
        if not state.get("hurtActive"):
            self._trigger_entity_event(bossId, "tf_slice:hurt_on")
            self._set_entity_property(
                bossId, "tf_slice:hurt_flash", 1.0
            )
            state["hurtActive"] = True
        self._play_world_sound(
            "mob.ghast.scream",
            self._get_foot_pos(bossId),
            1.0,
            0.5,
        )

    def _tick_ur_ghast_hurt_feedback(self, bossId, state):
        if (
            not state.get("hurtActive")
            or self._ur_ghast_logic_tick
            < int(state.get("hurtUntilLogicTick", 0))
        ):
            return False
        self._trigger_entity_event(bossId, "tf_slice:hurt_off")
        self._set_entity_property(
            bossId, "tf_slice:hurt_flash", 0.0
        )
        state["hurtActive"] = False
        return True

    def _broadcast_ur_ghast_effect(
        self, state, kind, positions, bossId=None
    ):
        cleaned = []
        for position in positions or ():
            if position is None or len(position) != 3:
                continue
            cleaned.append([float(value) for value in position])
        if not cleaned:
            return
        payload = {
            "dimensionId": int(
                state.get("dimensionId", config.DIMENSION_ID)
            ),
            "kind": str(kind),
            "positions": cleaned,
        }
        if bossId is not None:
            payload["bossId"] = str(bossId)
        self.BroadcastToAllClient("UrGhastEffect", payload)

    def _spawn_ur_ghast_volley(
        self, bossId, origin, target, facingYaw=None
    ):
        targetCenter = (
            float(target[0]),
            float(target[1]) + 0.9,
            float(target[2]),
        )
        spreadOffsets = tuple(
            (
                (random.random() - random.random()) * 8.0,
                (random.random() - random.random()) * 8.0,
            )
            for unusedIndex in range(2)
        )
        if facingYaw is None:
            facingYaw = float(self._get_rotation(bossId)[1])
        launchEffectSent = False
        for shot in ur_ghast_logic.fireball_volley(
            origin,
            targetCenter,
            spreadOffsets,
            facing_yaw=float(facingYaw),
        ):
            shotOrigin = shot["origin"]
            shotTarget = shot["target"]
            projectileId = self._spawn_ruin_entity(
                UR_GHAST_FIREBALL_IDENTIFIER,
                shotOrigin,
                0.0,
                self._get_dimension(bossId) or config.DIMENSION_ID,
            )
            if projectileId is None:
                continue
            projectileState = ur_ghast_logic.create_fireball_motion(
                shotOrigin, shotTarget, bossId, bossId
            )
            projectileState.update({
                "dimensionId": self._get_dimension(bossId) or config.DIMENSION_ID,
                "generation": int(self._tick),
                "spawnLogicTick": int(self._ur_ghast_logic_tick),
                "removed": False,
                "ignoreOwnerUntil": (
                    self._tick + ur_ghast_logic.FIREBALL_OWNER_IGNORE_TICKS
                ),
                "nextMotionTraceTick": int(self._ur_ghast_logic_tick),
            })
            self._ur_ghast_projectiles[str(projectileId)] = projectileState
            self._set_full_motion(projectileId, (0.0, 0.0, 0.0))
            self._entry_trace(
                "ur_ghast.fireball_spawned",
                bossId=str(bossId),
                projectileId=str(projectileId),
                origin=[round(float(value), 3) for value in shotOrigin],
                target=[round(float(value), 3) for value in shotTarget],
                logicTick=int(self._ur_ghast_logic_tick),
            )
            if not launchEffectSent:
                self._broadcast_ur_ghast_effect(
                    self._ur_ghasts.get(str(bossId), {}),
                    "fireball_launch",
                    (shotOrigin,),
                    bossId,
                )
                launchEffectSent = True

    def _reflect_ur_ghast_fireball(
        self, projectileId, playerId, reason="player_attack"
    ):
        projectileKey = entity_registry_logic.matching_entity_key(
            self._ur_ghast_projectiles, projectileId
        )
        if projectileKey is None or playerId is None:
            return False
        pitch, yaw = self._get_rotation(playerId)
        pitch = math.radians(float(pitch))
        yaw = math.radians(float(yaw))
        look = (
            -math.sin(yaw) * math.cos(pitch),
            -math.sin(pitch),
            math.cos(yaw) * math.cos(pitch),
        )
        projectile = self._ur_ghast_projectiles[projectileKey]
        if (
            int(projectile.get("lastReflectionTick", -1)) == self._tick
            and str(projectile.get("lastReflectionOwner")) == str(playerId)
        ):
            return True
        event = ur_ghast_logic.reflect_fireball(
            projectile, playerId, look
        )
        projectile["lastReflectionTick"] = int(self._tick)
        projectile["lastReflectionOwner"] = str(playerId)
        projectile["ignoreOwnerUntil"] = (
            self._tick + int(event.get("ignoreOwnerTicks", 0))
        )
        projectile["ignoreWorldUntil"] = (
            self._tick
            + int(event.get("worldCollisionGraceTicks", 0))
        )
        engineMotion = ur_ghast_logic.source_motion_to_engine(event["motion"])
        self._set_full_motion(projectileId, engineMotion)
        self._entry_trace(
            "ur_ghast.fireball_reflected",
            projectileId=str(projectileId),
            bossId=projectile.get("bossId"),
            ownerId=str(playerId),
            reason=str(reason),
            sourceMotion=[round(float(value), 4) for value in event["motion"]],
            engineMotion=[round(float(value), 4) for value in engineMotion],
            ignoreWorldUntil=int(projectile["ignoreWorldUntil"]),
        )
        self._play_world_sound(
            "random.orb", self._get_foot_pos(projectileId), 0.8, 1.8
        )
        return True

    def _drive_ur_ghast_projectiles(self):
        for projectileKey in list(self._ur_ghast_projectiles):
            projectile = self._ur_ghast_projectiles.get(projectileKey) or {}
            if projectile.get("removed") or projectile.get("settled"):
                continue
            if not projectile.get("acceleration"):
                continue
            if not self._valid_entity_id(projectileKey):
                self._ur_ghast_projectiles.pop(projectileKey, None)
                continue
            if not projectile.get("reflected"):
                expectedMotion = ur_ghast_logic.source_motion_to_engine(
                    projectile.get("velocity", (0.0, 0.0, 0.0))
                )
                actualMotion = self._get_full_motion(projectileKey)
                expectedLength = math.sqrt(sum(
                    float(value) * float(value)
                    for value in expectedMotion
                ))
                actualLength = math.sqrt(sum(
                    float(value) * float(value)
                    for value in actualMotion
                ))
                reversedDot = sum(
                    float(expectedMotion[index])
                    * float(actualMotion[index])
                    for index in range(3)
                )
                position = self._get_foot_pos(projectileKey)
                nearby = (
                    self._nearest_route_attackable_player(
                        position,
                        projectile.get("dimensionId", config.DIMENSION_ID),
                        2.5,
                    )
                    if position is not None else None
                )
                if (
                    nearby is not None
                    and expectedLength > 0.05
                    and actualLength > 0.05
                    and reversedDot
                    < -0.2 * expectedLength * actualLength
                ):
                    self._reflect_ur_ghast_fireball(
                        projectileKey,
                        nearby[0],
                        reason="native_motion_reversal",
                    )
            step = ur_ghast_logic.advance_fireball_motion(projectile)
            engineMotion = ur_ghast_logic.source_motion_to_engine(
                step["motion"]
            )
            self._set_full_motion(projectileKey, engineMotion)
            if self._ur_ghast_logic_tick >= int(
                projectile.get("nextMotionTraceTick", 0)
            ):
                projectile["nextMotionTraceTick"] = (
                    self._ur_ghast_logic_tick + 20
                )
                self._entry_trace(
                    "ur_ghast.fireball_motion",
                    projectileId=str(projectileKey),
                    ownerId=projectile.get("ownerId"),
                    reflected=bool(projectile.get("reflected", False)),
                    sourceMotion=[
                        round(float(value), 4) for value in step["motion"]
                    ],
                    engineMotion=[
                        round(float(value), 4) for value in engineMotion
                    ],
                )

    def _spawn_ur_ghast_tantrum_minions(
        self, state, force=False, bossId=None
    ):
        trapOrder = list(range(len(state.get("trapPoints", ()))))
        random.shuffle(trapOrder)
        plans = (
            ur_ghast_logic.minion_spawn_plans(state, trapOrder)
            if force else
            ur_ghast_logic.tantrum_minion_spawns(state, trapOrder)
        )
        for plan in plans:
            trapPosition = plan["position"]
            self._broadcast_ur_ghast_effect(
                state, "minion_spawn", (trapPosition,), bossId
            )
            self._play_world_sound(
                "ambient.weather.thunder", trapPosition, 1.0, 1.0
            )
            spawned = 0
            for unusedAttempt in range(int(plan.get("tries", 0))):
                if spawned >= int(plan.get("count", 0)):
                    break
                radius = float(plan.get("horizontalRadius", 4.0))
                verticalRange = float(plan.get("verticalRange", 8.0))
                position = (
                    float(trapPosition[0])
                    + (random.random() - random.random()) * radius,
                    float(trapPosition[1]) + random.random() * verticalRange,
                    float(trapPosition[2])
                    + (random.random() - random.random()) * radius,
                )
                entityId = self._spawn_ruin_entity(
                    MINI_GHAST_IDENTIFIER,
                    position,
                    random.uniform(0.0, 360.0),
                    state.get("dimensionId", config.DIMENSION_ID),
                )
                if entityId is not None:
                    minionState = self._register_phantom_urghast_mob(
                        entityId,
                        MINI_GHAST_IDENTIFIER,
                        state.get("dimensionId", config.DIMENSION_ID),
                    )
                    if minionState is not None:
                        minionState["bossMinion"] = True
                        minionState["home"] = list(trapPosition)
                    self._trigger_entity_event(
                        entityId, "tf_slice:make_boss_minion"
                    )
                    self._set_health_cap(
                        entityId,
                        phantom_urghast_mob_logic.BOSS_MINION_HEALTH,
                    )
                    spawned += 1

    def _begin_ur_ghast_tantrum(self, bossId, state):
        position = self._get_foot_pos(bossId) or state.get("home")
        self._update_ur_ghast_native_weather(force=True)
        self._broadcast_ur_ghast_effect(
            state, "tantrum_start", (position,), bossId
        )
        self._play_world_sound(
            "ambient.weather.thunder", position, 1.5, 0.8
        )
        self._spawn_ur_ghast_tantrum_minions(
            state, bossId=bossId
        )

    def _ur_ghast_absorb_nearby_minions(self, bossId, state, position):
        halfWidth = ur_ghast_logic.BOSS_WIDTH / 2.0 + 1.0
        consumedPositions = []
        healthBefore = float(state.get("health", 0.0))
        for entityId, minionState in list(
            self._phantom_urghast_mobs.items()
        ):
            if minionState.get("type") != MINI_GHAST_IDENTIFIER:
                continue
            if int(minionState.get(
                "dimensionId", config.DIMENSION_ID
            )) != int(state.get("dimensionId", config.DIMENSION_ID)):
                continue
            consumedPosition = minionState.get("lastPosition")
            if consumedPosition is None or len(consumedPosition) != 3:
                continue
            if not (
                abs(float(consumedPosition[0]) - float(position[0]))
                <= halfWidth
                and float(position[1]) - 1.0
                <= float(consumedPosition[1])
                <= float(position[1]) + ur_ghast_logic.BOSS_HEIGHT + 1.0
                and abs(float(consumedPosition[2]) - float(position[2]))
                <= halfWidth
            ):
                continue
            try:
                self.DestroyEntity(entityId)
            except Exception:
                continue
            consumedPositions.append(consumedPosition)
            self._phantom_urghast_mobs.pop(str(entityId), None)
        if not consumedPositions:
            return 0
        result = ur_ghast_logic.absorb_nearby_minions(
            state, len(consumedPositions)
        )
        self._set_ur_ghast_engine_health(
            bossId,
            state,
            ur_ghast_logic.authoritative_engine_health(state),
        )
        self._boss_sync_dirty = True
        self._broadcast_ur_ghast_effect(
            state,
            "absorb_minion",
            tuple(consumedPositions) + (position,),
            bossId,
        )
        self._entry_trace(
            "ur_ghast.minion_absorb",
            bossId=str(bossId),
            count=len(consumedPositions),
            healthBefore=round(healthBefore, 4),
            healthAfter=round(float(result.get("health", healthBefore)), 4),
            healed=round(float(result.get("healed", 0.0)), 4),
        )
        return len(consumedPositions)

    def _ur_ghast_traps_have_minions(self, state):
        dimensionId = int(state.get("dimensionId", config.DIMENSION_ID))
        for trapPosition in state.get("trapPoints", ()):
            start = (
                trapPosition[0] - 8.0,
                trapPosition[1] - 16.0,
                trapPosition[2] - 8.0,
            )
            end = (
                trapPosition[0] + 9.0,
                trapPosition[1] + 17.0,
                trapPosition[2] + 9.0,
            )
            try:
                candidates = CF.CreateGame(LEVEL_ID).GetEntitiesInSquareArea(
                    None, start, end, dimensionId
                ) or ()
            except Exception:
                continue
            count = sum(
                1 for entityId in candidates
                if self._get_engine_type(entityId) == MINI_GHAST_IDENTIFIER
            )
            if count >= ur_ghast_logic.MINIONS_REQUIRED_AT_TRAP:
                return True
        return False

    def _ur_ghast_sky_exposed(self, position, dimensionId):
        top = self._get_top_block_height(
            (position[0], position[2]), dimensionId
        )
        return top is not None and float(top) <= float(position[1]) + 1.0

    def _apply_ur_ghast_tantrum_damage(self, bossId, state, position):
        halfWidth = ur_ghast_logic.BOSS_WIDTH / 2.0
        start = (
            position[0] - halfWidth,
            position[1] - 32.0,
            position[2] - halfWidth,
        )
        end = (
            position[0] + halfWidth,
            position[1] + ur_ghast_logic.BOSS_HEIGHT,
            position[2] + halfWidth,
        )
        dimensionId = int(state.get("dimensionId", config.DIMENSION_ID))
        try:
            candidates = CF.CreateGame(LEVEL_ID).GetEntitiesInSquareArea(
                None, start, end, dimensionId
            ) or ()
        except Exception:
            return {"playerHits": 0, "minionLifts": 0}
        playerHits = 0
        minionLifts = 0
        for entityId in candidates:
            if self._get_engine_type(entityId) == MINI_GHAST_IDENTIFIER:
                try:
                    motionComp = CF.CreateActorMotion(entityId)
                    current = motionComp.GetMotion() or (0.0, 0.0, 0.0)
                    motionComp.SetMotion(
                        ur_ghast_logic.tantrum_minion_lift_motion(current)
                    )
                    minionLifts += 1
                except Exception:
                    pass
                continue
            if not self._is_online_player(entityId):
                continue
            playerPosition = self._get_foot_pos(entityId)
            if playerPosition is not None and self._ur_ghast_sky_exposed(
                playerPosition, dimensionId
            ):
                self._hurt(
                    entityId,
                    ur_ghast_logic.TANTRUM_TEAR_DAMAGE,
                    bossId,
                )
                playerHits += 1
        self._entry_trace(
            "ur_ghast.tear_pulse",
            bossId=str(bossId),
            playerHits=playerHits,
            minionLifts=minionLifts,
            volumeStart=[round(float(value), 3) for value in start],
            volumeEnd=[round(float(value), 3) for value in end],
        )
        return {
            "playerHits": playerHits,
            "minionLifts": minionLifts,
        }

    def _apply_ur_ghast_engine_motion(self):
        for bossKey in list(self._ur_ghasts):
            state = self._ur_ghasts.get(bossKey) or {}
            engineEntityId = state.get("engineEntityId", bossKey)
            if not self._valid_entity_id(engineEntityId):
                state["positionFailureTicks"] = int(
                    state.get("positionFailureTicks", 0)
                ) + 1
                continue
            position = self._get_foot_pos(engineEntityId)
            if position is None:
                state["positionFailureTicks"] = int(
                    state.get("positionFailureTicks", 0)
                ) + 1
                if int(state["positionFailureTicks"]) >= 3:
                    try:
                        resolvedId = int(bossKey)
                    except (TypeError, ValueError):
                        resolvedId = bossKey
                    state["engineEntityId"] = resolvedId
                continue
            state["positionFailureTicks"] = 0
            previousPosition = state.get("lastEnginePosition")
            actualDisplacement = 0.0
            if previousPosition is not None and len(previousPosition) == 3:
                actualDisplacement = math.sqrt(sum(
                    (
                        float(position[index])
                        - float(previousPosition[index])
                    ) ** 2
                    for index in range(3)
                ))
            state["lastEnginePosition"] = [
                float(value) for value in position
            ]
            requestedMotion = tuple(
                float(value) for value in state.get(
                    "requestedEngineMotion", (0.0, 0.0, 0.0)
                )
            )
            wanted = state.get("wantedWaypoint")
            targetVector = (
                tuple(
                    float(wanted[index]) - float(position[index])
                    for index in range(3)
                )
                if wanted is not None and len(wanted) == 3
                else (0.0, 0.0, 0.0)
            )
            motionOwner = str(state.get("motionOwner", "flight"))
            if motionOwner == "flight":
                adapterState = {
                    "mode": state.get(
                        "motionAuthority", "source_accumulator"
                    ),
                    "failureFrames": int(
                        state.get("motionFailureTicks", 0)
                    ),
                    "movingFrames": int(
                        state.get("motionMovingTicks", 0)
                    ),
                }
                decision = ur_ghast_logic.advance_engine_motion_adapter(
                    adapterState,
                    requestedMotion,
                    actualDisplacement,
                    state.get("lastSetMotionResult", True),
                    targetVector,
                )
                motion = decision["motion"]
                state["motionAuthority"] = decision["mode"]
                state["motionFailureTicks"] = decision["failureFrames"]
                state["motionMovingTicks"] = decision["movingFrames"]
            else:
                motion = requestedMotion
                state["motionFailureTicks"] = 0
                state["motionMovingTicks"] = 0
            setMotionResult = self._set_full_motion(
                engineEntityId, motion
            )
            actualMotion = self._get_full_motion(engineEntityId)
            state["lastSetMotionResult"] = setMotionResult is not False
            state["actualEngineMotion"] = list(actualMotion)
            if self._tick >= int(state.get("nextDriverTraceTick", 0)):
                state["nextDriverTraceTick"] = self._tick + 30
                self._entry_trace(
                    "ur_ghast.driver_sample",
                    bossId=str(bossKey),
                    engineEntityId=str(engineEntityId),
                    engineIdType=type(engineEntityId).__name__,
                    positionSuccess=True,
                    position=[round(float(value), 3) for value in position],
                    phase=str(state.get("phase", "normal")),
                    targetId=state.get("targetId"),
                    wantedWaypoint=wanted,
                    waypointDistance=round(
                        math.sqrt(sum(value * value for value in targetVector)),
                        4,
                    ),
                    sourceMotion=[
                        round(float(value), 4)
                        for value in state.get(
                            "sourceFlightVelocity", (0.0, 0.0, 0.0)
                        )
                    ],
                    requestedEngineMotion=[
                        round(float(value), 4) for value in requestedMotion
                    ],
                    appliedEngineMotion=[
                        round(float(value), 4) for value in motion
                    ],
                    actualMotion=[
                        round(float(value), 4) for value in actualMotion
                    ],
                    actualDisplacement=round(actualDisplacement, 4),
                    setMotionResult=setMotionResult is not False,
                    motionOwner=motionOwner,
                    motionAuthority=state.get("motionAuthority"),
                    motionFailureTicks=int(
                        state.get("motionFailureTicks", 0)
                    ),
                    positionFailureTicks=int(
                        state.get("positionFailureTicks", 0)
                    ),
                )

    def _drive_ur_ghasts(self):
        for bossKey in list(self._ur_ghasts):
            state = self._ur_ghasts.get(bossKey)
            engineBossId = (
                state.get("engineEntityId", bossKey)
                if state is not None else bossKey
            )
            position = self._get_foot_pos(engineBossId)
            if state is None or position is None:
                continue
            state["lastPosition"] = [float(value) for value in position]
            state["lastRotation"] = list(self._get_rotation(bossKey))
            self._reconcile_ur_ghast_engine_health(bossKey, state)
            self._tick_ur_ghast_hurt_feedback(bossKey, state)
            if self._ur_ghast_logic_tick % 4 == 0:
                self._separate_players_from_ur_ghast_head(
                    bossKey, state, position
                )
            if state.get("dying"):
                if not state.get("stormStopped"):
                    self._broadcast_ur_ghast_effect(
                        state, "storm_stop", (position,), bossKey
                    )
                    state["stormStopped"] = True
                self._sync_ur_ghast_visual_pitch(
                    bossKey, state, 0.0, "death"
                )
                state["requestedEngineMotion"] = [0.0, 0.0, 0.0]
                state["motionOwner"] = "death"
                death = ur_ghast_logic.advance_death_sequence(state, 1)
                deathTicks = int(death.get("deathTicks", 0))
                if deathTicks == 1:
                    self._play_world_sound(
                        "mob.ghast.death", position, 16.0, 0.5
                    )
                if death.get("stage") == "burst":
                    self._broadcast_ur_ghast_effect(
                        state, "death_burst", (position,), bossKey
                    )
                elif death.get("stage") == "trail":
                    trailPosition = ur_ghast_logic.death_trail_position(
                        (
                            float(position[0]),
                            float(position[1])
                            + ur_ghast_logic.BOSS_HEIGHT / 2.0,
                            float(position[2]),
                        ),
                        state.get("home", position),
                        deathTicks,
                    )
                    self._broadcast_ur_ghast_effect(
                        state, "death_trail", (trailPosition,), bossKey
                    )
                if death.get("complete"):
                    self._broadcast_ur_ghast_effect(
                        state, "death_poof", (position,), bossKey
                    )
                    self._finalize_ur_ghast(bossKey, state)
                elif deathTicks % 20 == 0:
                    self._save_ur_ghast_state(bossKey, state)
                continue
            if self._tick_ur_ghast_trap_route(bossKey, state):
                self._save_ur_ghast_state(bossKey, state)
            self._ur_ghast_absorb_nearby_minions(
                bossKey, state, position
            )
            activeTrap = self._active_ghast_trap(
                position,
                state.get("dimensionId", config.DIMENSION_ID),
            )
            if activeTrap is not None:
                wasTantrum = state.get("phase") == "tantrum"
                state["targetId"] = None
                self._reset_attack_target(bossKey)
                self._sync_ur_ghast_visual_pitch(
                    bossKey, state, 90.0, "trap_pull"
                )
                trapAttack = ur_ghast_logic.advance_attack(
                    state, False, 0.0, False
                )
                event = ur_ghast_logic.apply_active_trap_to_ur_ghast(
                    activeTrap,
                    state,
                    position,
                    deal_damage=(
                        random.randint(0, ur_ghast_logic.TRAP_DAMAGE_ROLL - 1)
                        == 0
                    ),
                )
                self._record_ghast_trap_effect_target(
                    activeTrap,
                    (
                        float(position[0]),
                        float(position[1]) + ur_ghast_logic.BOSS_HEIGHT / 2.0,
                        float(position[2]),
                    ),
                )
                if wasTantrum:
                    self._broadcast_ur_ghast_effect(
                        state, "storm_stop", (position,), bossKey
                    )
                    self._boss_sync_dirty = True
                trapMotion = event.get("motion", (0.0, 0.0, 0.0))
                state["sourceFlightVelocity"] = [0.0, 0.0, 0.0]
                state["requestedEngineMotion"] = list(trapMotion)
                state["motionOwner"] = "trap"
                trapYaw = ur_ghast_logic.yaw_for_motion(
                    trapMotion, state.get("lastValidYaw", 0.0)
                )
                self._set_ur_ghast_logical_yaw(
                    bossKey, state, trapYaw, "trap_pull"
                )
                self._sync_ur_ghast_visual(
                    bossKey,
                    state,
                    trapAttack.get("visualState", 0.0),
                )
                if event.get("damage", 0.0) > 0.0:
                    self._set_ur_ghast_engine_health(
                        bossKey,
                        state,
                        ur_ghast_logic.authoritative_engine_health(state),
                    )
                    self._boss_sync_dirty = True
                if (
                    event.get("damage", 0.0) > 0.0
                    or self._ur_ghast_logic_tick % 20 == 0
                ):
                    self._save_ur_ghast_state(bossKey, state)
                continue
            suppressTarget = int(state.get("inTrapTicks", 0)) > 0
            if suppressTarget:
                state["inTrapTicks"] = int(state["inTrapTicks"]) - 1
                self._sync_ur_ghast_visual_pitch(
                    bossKey,
                    state,
                    float(state["inTrapTicks"]) / 20.0 * 90.0,
                    "trap_release",
                )
                state["targetId"] = None
                self._reset_attack_target(bossKey)
                targetId, targetPos = None, None
            else:
                targetId, targetPos = self._ur_ghast_target(
                    position, state
                )
            if targetId is not None:
                state["targetId"] = targetId
            else:
                state["targetId"] = None
            # Commit a legal route and engine motion before combat perception.
            # NetEase can abort a component-heavy combat branch without a
            # Python traceback; flight must not remain idle when that happens.
            wanted = state.get("wantedWaypoint")
            if ur_ghast_logic.waypoint_needs_refresh(position, wanted):
                selection = ur_ghast_logic.select_next_waypoint(state)
                wanted = selection["point"]
                state["wantedWaypoint"] = wanted
                self._entry_trace(
                    "ur_ghast.flight_target",
                    bossId=str(bossKey),
                    reason="route",
                    target=[round(float(value), 3) for value in wanted],
                    altitudeBounds=[
                        round(float(value), 3)
                        for value in ur_ghast_logic.flight_altitude_bounds(
                            state
                        )
                    ],
                    logicTick=int(self._ur_ghast_logic_tick),
                )
                if (
                    selection.get("cycleCompleted")
                    and not self._ur_ghast_traps_have_minions(state)
                ):
                    self._spawn_ur_ghast_tantrum_minions(
                        state, force=True, bossId=bossKey
                    )
            flight = ur_ghast_logic.advance_flight_motion(
                state,
                position,
                wanted,
                state.get("sourceFlightVelocity", (0.0, 0.0, 0.0)),
                random.randrange(
                    ur_ghast_logic.FLIGHT_COURSE_COOLDOWN_SPREAD
                ),
            )
            state["sourceFlightVelocity"] = list(flight["motion"])
            state["requestedEngineMotion"] = list(
                ur_ghast_logic.source_motion_to_engine(flight["motion"])
            )
            state["motionOwner"] = "flight"
            motionYaw = ur_ghast_logic.yaw_for_motion(
                flight.get("motion", (0.0, 0.0, 0.0)),
                state.get("lastValidYaw", 0.0),
            )
            self._set_ur_ghast_logical_yaw(
                bossKey, state, motionYaw, "flight_motion"
            )
            if self._ur_ghast_logic_tick >= int(
                state.get("nextFlightTraceTick", 0)
            ):
                state["nextFlightTraceTick"] = (
                    self._ur_ghast_logic_tick + 20
                )
                sampledMotion = flight.get(
                    "motion", (0.0, 0.0, 0.0)
                )
                self._entry_trace(
                    "ur_ghast.flight_sample",
                    bossId=str(bossKey),
                    position=[
                        round(float(value), 3) for value in position
                    ],
                    motion=[
                        round(float(value), 4)
                        for value in sampledMotion
                    ],
                    speed=round(
                        math.sqrt(sum(
                            float(value) * float(value)
                            for value in sampledMotion
                        )),
                        4,
                    ),
                    waypointDistance=round(
                        math.sqrt(_distance_sq(position, wanted)), 3
                    ),
                    stallTicks=int(state.get("flightStallTicks", 0)),
                )
            cryRoll = (
                random.randrange(ur_ghast_logic.TANTRUM_CRY_SPREAD)
                if (
                    state.get("phase") == "tantrum"
                    and int(state.get("nextTantrumCry", 0)) <= 1
                ) else 0
            )
            tantrum = ur_ghast_logic.advance_tantrum(
                state, self._ur_ghast_logic_tick, cryRoll
            )
            if tantrum.get("clearTarget"):
                targetId, targetPos = None, None
                state["targetId"] = None
                self._reset_attack_target(bossKey)
            if tantrum.get("cry"):
                self._play_world_sound(
                    "mob.ghast.scream", position, 16.0, 0.5
                )
            if (
                state.get("phase") == "tantrum"
                and self._ur_ghast_logic_tick % 20 == 0
            ):
                self._broadcast_ur_ghast_effect(
                    state, "storm_keepalive", (position,), bossKey
                )
            if tantrum.get("tearDamage"):
                self._apply_ur_ghast_tantrum_damage(
                    bossKey, state, position
                )
                self._broadcast_ur_ghast_effect(
                    state, "tear", (position,), bossKey
                )
            distanceSq = (
                _distance_sq(position, targetPos)
                if targetPos is not None else 0.0
            )
            hasSight = bool(
                targetId is not None
                and self._ur_ghast_can_see(bossKey, targetId)
            )
            attack = ur_ghast_logic.advance_attack(
                state,
                targetId is not None,
                distanceSq,
                hasSight,
            )
            faceAttackTarget = bool(
                targetPos is not None
                and state.get("phase") != "tantrum"
                and distanceSq < ur_ghast_logic.ATTACK_RANGE_SQ
            )
            if faceAttackTarget:
                targetYaw = ur_ghast_logic.yaw_for_motion(
                    (
                        float(targetPos[0]) - float(position[0]),
                        0.0,
                        float(targetPos[2]) - float(position[2]),
                    ),
                    state.get("lastValidYaw", 0.0),
                )
                state["lastValidYaw"] = targetYaw
                self._set_ur_ghast_logical_yaw(
                    bossKey, state, targetYaw, "attack_target"
                )
                mouthPosition = (
                    float(position[0]),
                    float(position[1]) + ur_ghast_logic.BOSS_HEIGHT / 2.0,
                    float(position[2]),
                )
                targetCenter = (
                    float(targetPos[0]),
                    float(targetPos[1]) + 0.9,
                    float(targetPos[2]),
                )
                self._sync_ur_ghast_visual_pitch(
                    bossKey,
                    state,
                    ur_ghast_logic.visual_pitch_degrees(
                        mouthPosition, targetCenter
                    ),
                    "attack_target",
                )
            elif not suppressTarget:
                self._sync_ur_ghast_visual_pitch(
                    bossKey, state, 0.0, "flight_motion"
                )
            if attack.get("warn"):
                self._play_world_sound(
                    "mob.ghast.charge", position, 10.0, 0.5
                )
            if attack.get("fire") and targetPos is not None:
                self._play_world_sound(
                    "mob.ghast.fireball", position, 10.0, 0.5
                )
                self._spawn_ur_ghast_volley(
                    bossKey,
                    position,
                    targetPos,
                    facingYaw=state.get("lastValidYaw", 0.0),
                )
            self._sync_ur_ghast_visual(
                bossKey, state, attack.get("visualState", 0.0)
            )
            if flight.get("reselectWaypoint"):
                self._entry_trace(
                    "ur_ghast.flight_target",
                    bossId=str(bossKey),
                    reason="stall_recovery",
                    target=flight.get("recoveryWaypoint"),
                    logicTick=int(self._ur_ghast_logic_tick),
                )
            if self._ur_ghast_logic_tick % 20 == 0:
                self._save_ur_ghast_state(bossKey, state)

    def _place_ur_ghast_reward(self, state):
        return self._queue_loot_reward(
            state, "ur_ghast", state.get("home"),
            "loot_tables/chests/tf_slice/ur_ghast_reward.json",
            reward_delivery.bonus_items("ur_ghast", state.get("lastLootingLevel", 0), random),
        )

    def _finalize_ur_ghast(self, bossId, state):
        if self._ruin_worldgen is not None:
            self._ruin_worldgen.mark_boss_defeated(
                state.get("home"), "ur_ghast"
            )
            rewardAllowed = self._ruin_worldgen.claim_boss_reward(
                state.get("home"), "ur_ghast"
            )
        else:
            rewardAllowed = True
        if rewardAllowed and ur_ghast_logic.claim_reward(state):
            self._place_ur_ghast_reward(state)
            self._spawn_route_boss_experience(
                ur_ghast_logic.XP_REWARD,
                state.get("home"),
            )
        for playerId in ur_ghast_logic.final_progress_players(state):
            if self._is_online_player(playerId):
                self._grant_progress(playerId, "tf_ur_ghast_defeated")
        self._save_ur_ghast_state(bossId, state)
        try:
            self.DestroyEntity(bossId)
        except Exception:
            pass
        self._ur_ghasts.pop(str(bossId), None)
        return True

    def _load_hydra_state(self, entityId):
        try:
            value = CF.CreateExtraData(entityId).GetExtraData(
                config.HYDRA_STATE_EXTRA_KEY
            )
        except Exception:
            value = None
        if not isinstance(value, dict):
            return None
        try:
            version = int(value.get("version", 1))
            engineBodyYaw = self._get_rotation(entityId)[1]
            bodyYaw = float(value.get("bodyYaw", engineBodyYaw))
            rawHeads = list(value.get("heads", ()))[:HYDRA_HEAD_COUNT]
            heads = []
            for index in range(HYDRA_HEAD_COUNT):
                raw = rawHeads[index] if index < len(rawHeads) else {}
                if version < 2:
                    lifecycle = hydra_logic.initial_head_state(index)
                    alive = lifecycle["alive"]
                    stateName = lifecycle["state"]
                    deadTicks = lifecycle["dead_ticks"]
                else:
                    alive = bool(raw.get("alive", index < 3))
                    stateName = str(raw.get("state", "idle"))
                    deadTicks = max(-1, int(raw.get("deadTicks", -1)))
                if version >= 3:
                    respawnTicks = max(-1, int(raw.get("respawnTicks", -1)))
                elif alive:
                    respawnTicks = -1
                elif deadTicks >= 0:
                    # v2 used one elapsed-death timer. Preserve the nearest
                    # locked-JAR timing when migrating an in-flight death.
                    respawnTicks = (
                        max(1, 170 - deadTicks)
                        if stateName == "dead"
                        else hydra_logic.HEAD_RESPAWN_TICKS
                    )
                else:
                    respawnTicks = -1
                headYaw = (
                    bodyYaw
                    if version < 4
                    else float(raw.get("yaw", bodyYaw))
                )
                heads.append(
                    {
                        "entityId": None,
                        "neckIds": [None] * HYDRA_NECK_COUNT,
                        "alive": alive,
                        "damage": max(0.0, float(raw.get("damage", 0.0))),
                        "deadTicks": deadTicks,
                        "respawnTicks": respawnTicks,
                        "state": stateName,
                        "previousState": str(
                            raw.get("previousState", stateName)
                        ),
                        "ticks": max(0, int(raw.get("ticks", 0))),
                        "yaw": headYaw,
                        "pitch": float(raw.get("pitch", 0.0)),
                        "name": str(raw.get("name", "")),
                        "targetId": None,
                        "secondary": False,
                        "aimPos": None,
                        "biteVictims": set(),
                    }
                )
            return {
                "dimensionId": int(value.get("dimensionId", config.DIMENSION_ID)),
                "home": tuple(float(v) for v in value.get("home", (0, 64, 0))),
                "health": max(0.0, float(value.get("health", hydra_logic.MAX_HEALTH))),
                "bodyYaw": bodyYaw,
                "entityYaw": float(value.get("entityYaw", bodyYaw)),
                "partIds": {
                    "body": None,
                    "left_leg": None,
                    "right_leg": None,
                    "tail": None,
                },
                "heads": heads,
                "targetId": None,
                "targetUntil": 0,
                "randomYawVelocity": float(
                    value.get("randomYawVelocity", 0.0)
                ),
                "lastLootingLevel": max(
                    0, int(value.get("lastLootingLevel", 0))
                ),
                # The locked Java Hydra does not persist this combat-idle
                # counter.  A loaded entity must earn the full 1000-tick
                # no-damage delay again before natural healing can start.
                "ticksSinceDamage": 0,
                "participants": set(str(v) for v in value.get("participants", ())),
                "dying": bool(value.get("dying", False)),
                "deathTicks": max(0, int(value.get("deathTicks", 0))),
                "rewarded": bool(value.get("rewarded", False)),
                "dead": bool(value.get("dead", False)),
                "ensureAfter": self._tick + 5,
                "lastPartDamageTick": None,
                "lastPartDamageSource": None,
                "lastHurtAmount": 0.0,
                "hurtWindowStartTick": None,
                "hurtUntil": 0,
                "hurtActive": False,
            }
        except (TypeError, ValueError):
            return None

    def _save_hydra_state(self, entityId, state):
        if entityId is None or state is None:
            return False
        value = {
            "version": 6,
            "dimensionId": int(state["dimensionId"]),
            "home": list(state["home"]),
            "health": float(state["health"]),
            "bodyYaw": float(state.get("bodyYaw", 0.0)),
            "entityYaw": float(state.get("entityYaw", 0.0)),
            "randomYawVelocity": float(
                state.get("randomYawVelocity", 0.0)
            ),
            "lastLootingLevel": max(
                0, int(state.get("lastLootingLevel", 0))
            ),
            "participants": sorted(str(v) for v in state.get("participants", ())),
            "dying": bool(state.get("dying", False)),
            "deathTicks": int(state.get("deathTicks", 0)),
            "rewarded": bool(state.get("rewarded", False)),
            "dead": bool(state.get("dead", False)),
            "heads": [
                {
                    "alive": bool(head.get("alive", False)),
                    "damage": float(head.get("damage", 0.0)),
                    "deadTicks": int(head.get("deadTicks", 0)),
                    "respawnTicks": int(head.get("respawnTicks", -1)),
                    "state": str(head.get("state", "idle")),
                    "previousState": str(
                        head.get("previousState", head.get("state", "idle"))
                    ),
                    "ticks": int(head.get("ticks", 0)),
                    "yaw": float(head.get("yaw", 0.0)),
                    "pitch": float(head.get("pitch", 0.0)),
                    "name": str(head.get("name", "")),
                }
                for head in state.get("heads", ())
            ],
        }
        try:
            extra = CF.CreateExtraData(entityId)
            extra.SetExtraData(config.HYDRA_STATE_EXTRA_KEY, value, False)
            return bool(extra.SaveExtraData())
        except Exception as error:
            print "[TwilightBossSlice] Hydra state save failed:", error
            return False

    def _new_hydra_state(self, entityId, dimensionId):
        home = self._get_foot_pos(entityId) or (0.0, 64.0, 0.0)
        bodyYaw = self._get_rotation(entityId)[1]
        state = {
            "dimensionId": int(dimensionId),
            "home": tuple(home),
            "health": hydra_logic.MAX_HEALTH,
            "bodyYaw": bodyYaw,
            "entityYaw": bodyYaw,
            "partIds": {
                "body": None,
                "left_leg": None,
                "right_leg": None,
                "tail": None,
            },
            "heads": [],
            "targetId": None,
            "targetUntil": 0,
            "randomYawVelocity": 0.0,
            "lastLootingLevel": 0,
            "ticksSinceDamage": 0,
            "participants": set(),
            "dying": False,
            "deathTicks": 0,
            "rewarded": False,
            "generation": 0,
            "dead": False,
            "ensureAfter": self._tick,
            "lastPartDamageTick": None,
            "lastPartDamageSource": None,
            "lastHurtAmount": 0.0,
            "hurtWindowStartTick": None,
            "hurtUntil": 0,
            "hurtActive": False,
        }
        for index in range(HYDRA_HEAD_COUNT):
            lifecycle = hydra_logic.initial_head_state(index)
            state["heads"].append(
                {
                    "entityId": None,
                    "neckIds": [None] * HYDRA_NECK_COUNT,
                    "alive": lifecycle["alive"],
                    "damage": 0.0,
                    "deadTicks": lifecycle["dead_ticks"],
                    "respawnTicks": -1,
                    "state": lifecycle["state"],
                    "previousState": lifecycle["state"],
                    "ticks": 0,
                    "yaw": bodyYaw,
                    "pitch": 0.0,
                    "name": "",
                    "targetId": None,
                    "secondary": False,
                    "aimPos": None,
                    "biteVictims": set(),
                }
            )
        self._set_health_cap(entityId, hydra_logic.MAX_HEALTH)
        return state

    def _register_hydra(self, entityId, dimensionId):
        key = entity_registry_logic.matching_entity_key(self._hydras, entityId)
        if key is not None:
            state = self._hydras[key]
            state["actorLoaded"] = True
            state["dimensionId"] = int(dimensionId)
            return state
        state = self._load_hydra_state(entityId)
        if state is None:
            state = self._new_hydra_state(entityId, dimensionId)
        state["actorLoaded"] = True
        self._hydras[entityId] = state
        self._set_health_max(entityId, hydra_logic.MAX_HEALTH)
        self._set_health(entityId, max(1.0, state["health"]))
        self._save_hydra_state(entityId, state)
        return state

    def _hydra_body_part_positions(self, hydraId, state):
        bodyPos = self._get_foot_pos(hydraId)
        if bodyPos is None:
            return None
        bodyYaw = float(state.get("bodyYaw", self._get_rotation(hydraId)[1]))
        look = hydra_logic.look_vector(0.0, bodyYaw)
        return {
            "body": (
                float(bodyPos[0]) - look[0] * 3.0,
                float(bodyPos[1]) + 0.1,
                float(bodyPos[2]) - look[2] * 3.0,
            ),
            "left_leg": tuple(float(value) for value in bodyPos),
            "right_leg": tuple(float(value) for value in bodyPos),
            "tail": (
                float(bodyPos[0]) - look[0] * 10.5,
                float(bodyPos[1]) + 0.1,
                float(bodyPos[2]) - look[2] * 10.5,
            ),
        }

    def _bind_hydra_part(self, partId, hydraId, partKind):
        self._hydra_parts[partId] = (hydraId, str(partKind))
        try:
            extra = CF.CreateExtraData(partId)
            extra.SetExtraData(
                "tf_slice:hydra_part_owner_v1",
                {"ownerId": str(hydraId), "part": str(partKind)},
                False,
            )
            extra.SaveExtraData()
        except Exception:
            pass

    def _restore_hydra_part_owner(self, partId):
        try:
            value = CF.CreateExtraData(partId).GetExtraData(
                "tf_slice:hydra_part_owner_v1"
            )
        except Exception:
            return False
        if not isinstance(value, dict):
            return False
        ownerKey = entity_registry_logic.matching_entity_key(
            self._hydras, value.get("ownerId")
        )
        partKind = str(value.get("part", ""))
        if ownerKey is None or partKind not in (
            "body", "left_leg", "right_leg", "tail"
        ):
            return False
        state = self._hydras[ownerKey]
        state.setdefault("partIds", {})[partKind] = partId
        self._bind_hydra_part(partId, ownerKey, partKind)
        return True

    def _ensure_hydra_body_parts(self, hydraId, state):
        positions = self._hydra_body_part_positions(hydraId, state)
        if positions is None:
            return
        partIds = state.setdefault("partIds", {})
        for partKind, position in positions.items():
            partId = partIds.get(partKind)
            if partId is None:
                partId = self._spawn_ruin_entity(
                    HYDRA_PART_PROXY_IDENTIFIER,
                    position,
                    state.get("bodyYaw", 0.0),
                    state["dimensionId"],
                )
                if partId is None:
                    continue
                partIds[partKind] = partId
                self._set_health_cap(
                    partId, hydra_logic.PART_ACTOR_HEALTH
                )
                self._bind_hydra_part(partId, hydraId, partKind)
                eventKind = "leg" if partKind.endswith("leg") else partKind
                self._trigger_entity_event(
                    partId, "tf_slice:set_%s" % eventKind
                )
                if state.get("hurtActive"):
                    self._trigger_entity_event(partId, "tf_slice:hurt_on")
            try:
                if CF.CreatePos(partId).SetPos(position) is False:
                    self._hydra_parts.pop(partId, None)
                    partIds[partKind] = None
                    continue
                if self._set_full_motion(
                    partId, (0.0, 0.0, 0.0)
                ) is False:
                    self._hydra_parts.pop(partId, None)
                    partIds[partKind] = None
                    continue
                if self._set_health(
                    partId, hydra_logic.PART_ACTOR_HEALTH
                ) is False:
                    self._hydra_parts.pop(partId, None)
                    partIds[partKind] = None
            except Exception:
                self._hydra_parts.pop(partId, None)
                partIds[partKind] = None

    def _remove_hydra_body_parts(self, state):
        partIds = dict(state.get("partIds") or {})
        state["partIds"] = dict(
            (kind, None)
            for kind in ("body", "left_leg", "right_leg", "tail")
        )
        for partId in partIds.values():
            if partId is None:
                continue
            self._hydra_parts.pop(partId, None)
            try:
                self.DestroyEntity(partId)
            except Exception:
                pass

    @staticmethod
    def _hydra_head_offset(index, head=None, tick=0):
        if not isinstance(head, dict):
            return hydra_logic.rest_head_offset(index)
        pose = hydra_logic.interpolated_head_pose(
            head.get("previousState", head.get("state", "idle")),
            head.get("state", "idle"),
            index,
            head.get("ticks", 0),
        )
        pose = hydra_logic.animated_head_pose(
            pose,
            index,
            tick,
            str(head.get("state", "idle")) != "dead",
        )
        return hydra_logic.head_offset_for_pose(pose)

    @staticmethod
    def _hydra_world_offset(bodyPos, yawDegrees, offset):
        yaw = math.radians(float(yawDegrees))
        ox, oy, oz = offset
        return (
            bodyPos[0] + ox * math.cos(yaw) - oz * math.sin(yaw),
            bodyPos[1] + oy,
            bodyPos[2] + ox * math.sin(yaw) + oz * math.cos(yaw),
        )

    def _hydra_head_position(
        self, hydraId, index, head=None, bodyYaw=None
    ):
        bodyPos = self._get_foot_pos(hydraId)
        if bodyPos is None:
            return None
        if bodyYaw is None:
            bodyYaw = self._get_rotation(hydraId)[1]
        return self._hydra_world_offset(
            bodyPos,
            bodyYaw,
            self._hydra_head_offset(index, head, self._tick),
        )

    def _compute_hydra_chain_frame(
        self, hydraId, state, index, head
    ):
        bodyPos = self._get_foot_pos(hydraId)
        if bodyPos is None:
            return None
        headState = str(head.get("state", "idle"))
        lockIdleChain = hydra_logic.lock_idle_chain_for_state(headState)
        return hydra_logic.head_chain_frame(
            index=index,
            previous_state=head.get(
                "previousState", head.get("state", "idle")
            ),
            state=head.get("state", "idle"),
            state_ticks=head.get("ticks", 0),
            world_tick=self._tick,
            body_position=bodyPos,
            body_yaw=state.get("bodyYaw", self._get_rotation(hydraId)[1]),
            head_yaw=head.get("yaw", state.get("bodyYaw", 0.0)),
            head_pitch=head.get("pitch", 0.0),
            lock_idle_chain=lockIdleChain,
        )

    def _apply_hydra_chain_frame(
        self, hydraId, state, index, head, frame
    ):
        if frame is None:
            return False
        headId = head.get("entityId")
        if headId is None:
            return False
        try:
            if CF.CreatePos(headId).SetPos(frame["head_position"]) is False:
                return False
            if CF.CreateRot(headId).SetRot(
                (float(frame["facing"][1]), float(frame["facing"][0]))
            ) is False:
                return False
            if self._set_full_motion(headId, (0.0, 0.0, 0.0)) is False:
                return False
            if self._set_health(
                headId, hydra_logic.PART_ACTOR_HEALTH
            ) is False:
                return False
            if self._set_entity_property(
                headId, "tf_slice:mouth_open", frame["mouth"]
            ) is False:
                return False
        except Exception:
            return False
        self._ensure_hydra_necks(
            hydraId, state, index, head, frame=frame
        )
        visualParts = [
            {
                "entityId": headId,
                "position": tuple(frame["head_position"]),
                "rotation": (
                    float(frame["facing"][1]),
                    float(frame["facing"][0]),
                ),
            }
        ]
        neckIds = list(head.get("neckIds") or ())
        for segmentIndex, (position, rotation) in enumerate(frame["necks"]):
            neckId = (
                neckIds[segmentIndex]
                if segmentIndex < len(neckIds)
                else None
            )
            if neckId is None:
                continue
            visualParts.append(
                {
                    "entityId": neckId,
                    "position": tuple(position),
                    "rotation": hydra_logic.neck_visual_rotation(rotation),
                }
            )
        self.BroadcastToAllClient(
            "HydraActorFrame",
            {
                "id": str(hydraId),
                "index": int(index),
                "dimensionId": int(state["dimensionId"]),
                "serverTick": int(self._tick),
                "parts": visualParts,
            },
        )
        return True

    def _hydra_neck_transforms(
        self, hydraId, index, head, bodyYaw=None
    ):
        bodyPos = self._get_foot_pos(hydraId)
        if bodyPos is None:
            return None
        if bodyYaw is None:
            bodyYaw = self._get_rotation(hydraId)[1]
        start = self._hydra_world_offset(
            bodyPos, bodyYaw, hydra_logic.neck_root_offset(index)
        )
        end = self._hydra_head_position(
            hydraId, index, head, bodyYaw=bodyYaw
        )
        if end is None:
            return None
        end = (float(end[0]), float(end[1]) - 0.5, float(end[2]))
        endPitch = float(head.get("pitch", 0.0))
        endYaw = float(head.get("yaw", bodyYaw))
        return hydra_logic.neck_segment_transforms(
            start, end, bodyYaw, endYaw, endPitch
        )

    def _bind_hydra_head(self, headId, hydraId, index):
        self._hydra_heads[headId] = (hydraId, int(index))
        try:
            extra = CF.CreateExtraData(headId)
            extra.SetExtraData(
                "tf_slice:hydra_head_owner_v1",
                {"ownerId": str(hydraId), "index": int(index)},
                False,
            )
            extra.SaveExtraData()
        except Exception:
            pass

    def _restore_hydra_head_owner(self, headId):
        try:
            value = CF.CreateExtraData(headId).GetExtraData(
                "tf_slice:hydra_head_owner_v1"
            )
        except Exception:
            return False
        if not isinstance(value, dict):
            return False
        ownerKey = entity_registry_logic.matching_entity_key(
            self._hydras, value.get("ownerId")
        )
        try:
            index = int(value.get("index"))
        except (TypeError, ValueError):
            return False
        if ownerKey is None or not (0 <= index < HYDRA_HEAD_COUNT):
            return False
        head = self._hydras[ownerKey]["heads"][index]
        oldId = head.get("entityId")
        if oldId not in (None, headId):
            self.DestroyEntity(oldId)
            self._hydra_heads.pop(oldId, None)
        if not head.get("alive") and int(head.get("deadTicks", -1)) < 0:
            try:
                self.DestroyEntity(headId)
            except Exception:
                pass
            return False
        head["entityId"] = headId
        self._bind_hydra_head(headId, ownerKey, index)
        return True

    def _ensure_hydra_heads(self, hydraId, state):
        if self._tick < int(state.get("ensureAfter", 0)):
            return
        for index, head in enumerate(state["heads"]):
            if not head.get("alive"):
                if int(head.get("deadTicks", -1)) < 0:
                    self._remove_hydra_head_actor(head)
                continue
            if head.get("entityId") is None:
                pos = self._hydra_head_position(
                    hydraId,
                    index,
                    head,
                    bodyYaw=state.get("bodyYaw"),
                )
                if pos is None:
                    continue
                headId = self._spawn_ruin_entity(
                    HYDRA_HEAD_IDENTIFIER,
                    pos,
                    state.get("bodyYaw", 0.0),
                    state["dimensionId"],
                )
                if headId:
                    head["entityId"] = headId
                    self._set_health_cap(headId, hydra_logic.PART_ACTOR_HEALTH)
                    self._set_full_motion(headId, (0.0, 0.0, 0.0))
                    self._bind_hydra_head(headId, hydraId, index)
                    if head.get("name"):
                        try:
                            CF.CreateName(headId).SetName(head["name"])
                        except Exception:
                            pass
                    if state.get("hurtActive"):
                        self._trigger_entity_event(headId, "tf_slice:hurt_on")
            if head.get("entityId") is not None:
                neckIds = list(head.get("neckIds") or ())
                if (
                    len(neckIds) < HYDRA_NECK_COUNT
                    or any(neckId is None for neckId in neckIds)
                ):
                    self._ensure_hydra_necks(hydraId, state, index, head)

    def _ensure_hydra_necks(
        self, hydraId, state, index, head, frame=None
    ):
        transforms = (
            frame.get("necks")
            if isinstance(frame, dict)
            else self._hydra_neck_transforms(
                hydraId,
                index,
                head,
                bodyYaw=state.get("bodyYaw"),
            )
        )
        if transforms is None:
            return
        neckIds = list(head.get("neckIds") or ())[:HYDRA_NECK_COUNT]
        while len(neckIds) < HYDRA_NECK_COUNT:
            neckIds.append(None)
        for segmentIndex, (position, rotation) in enumerate(transforms):
            visualRotation = hydra_logic.neck_visual_rotation(rotation)
            neckId = neckIds[segmentIndex]
            if neckId is None:
                neckId = self._spawn_ruin_entity(
                    HYDRA_NECK_IDENTIFIER,
                    position,
                    visualRotation[1],
                    state["dimensionId"],
                )
                if neckId:
                    neckIds[segmentIndex] = neckId
                    self._set_health_cap(
                        neckId, hydra_logic.PART_ACTOR_HEALTH
                    )
                    self._set_full_motion(neckId, (0.0, 0.0, 0.0))
                    self._hydra_necks[neckId] = (
                        hydraId,
                        int(index),
                        int(segmentIndex),
                    )
                    if state.get("hurtActive"):
                        self._trigger_entity_event(neckId, "tf_slice:hurt_on")
                    try:
                        CF.CreateRot(neckId).SetRot(visualRotation)
                    except Exception:
                        pass
            else:
                try:
                    if CF.CreatePos(neckId).SetPos(position) is False:
                        self._hydra_necks.pop(neckId, None)
                        neckIds[segmentIndex] = None
                        continue
                    if CF.CreateRot(neckId).SetRot(visualRotation) is False:
                        self._hydra_necks.pop(neckId, None)
                        neckIds[segmentIndex] = None
                        continue
                    if self._set_full_motion(
                        neckId, (0.0, 0.0, 0.0)
                    ) is False:
                        self._hydra_necks.pop(neckId, None)
                        neckIds[segmentIndex] = None
                except Exception:
                    self._hydra_necks.pop(neckId, None)
                    neckIds[segmentIndex] = None
        head["neckIds"] = neckIds

    def _remove_hydra_neck_actors(self, head):
        neckIds = list(head.get("neckIds") or ())
        head["neckIds"] = [None] * HYDRA_NECK_COUNT
        for neckId in neckIds:
            if neckId is None:
                continue
            self._hydra_necks.pop(neckId, None)
            try:
                self.DestroyEntity(neckId)
            except Exception:
                pass

    def _remove_hydra_head_actor(self, head):
        self._remove_hydra_neck_actors(head)
        headId = head.get("entityId")
        head["entityId"] = None
        if headId is None:
            return
        self._hydra_heads.pop(headId, None)
        try:
            self.DestroyEntity(headId)
        except Exception:
            pass

    def _remove_hydra_head_only(self, head):
        headId = head.get("entityId")
        head["entityId"] = None
        if headId is None:
            return
        self._hydra_heads.pop(headId, None)
        try:
            self.DestroyEntity(headId)
        except Exception:
            pass

    def _remove_hydra_neck_segment(self, head, segmentIndex):
        neckIds = list(head.get("neckIds") or ())
        if segmentIndex < 0 or segmentIndex >= len(neckIds):
            return
        neckId = neckIds[segmentIndex]
        neckIds[segmentIndex] = None
        head["neckIds"] = neckIds
        if neckId is None:
            return
        self._hydra_necks.pop(neckId, None)
        try:
            self.DestroyEntity(neckId)
        except Exception:
            pass

    def _broadcast_hydra_part_death(self, position, dimensionId, size):
        if position is None:
            return
        self.BroadcastToAllClient(
            "HydraRouteEffect",
            {
                "kind": "hydra_part_death",
                "dimensionId": dimensionId,
                "position": position,
                "size": tuple(size),
            },
        )

    @staticmethod
    def _hydra_part_actor_ids(state, aliveOnly=False):
        actorIds = [
            partId
            for partId in (state.get("partIds") or {}).values()
            if partId is not None
        ]
        for head in state.get("heads", ()):
            if aliveOnly and not head.get("alive"):
                continue
            headId = head.get("entityId")
            if headId is not None:
                actorIds.append(headId)
            actorIds.extend(
                neckId
                for neckId in head.get("neckIds", ())
                if neckId is not None
            )
        return actorIds

    def _begin_hydra_hurt_feedback(self, hydraId, state, hitPosition):
        state["hurtUntil"] = self._tick + 10
        state["hurtActive"] = True
        self._trigger_entity_event(hydraId, "tf_slice:hurt_on")
        for actorId in self._hydra_part_actor_ids(state):
            self._trigger_entity_event(actorId, "tf_slice:hurt_on")
        position = hitPosition or self._get_foot_pos(hydraId)
        if position is not None:
            self.BroadcastToAllClient(
                "HydraRouteEffect",
                {
                    "kind": "hydra_hurt",
                    "dimensionId": state["dimensionId"],
                    "position": position,
                },
            )
            self._play_world_sound(
                "tf_slice.hydra.hurt", position, 1.0, 1.0
            )

    def _tick_hydra_hurt_feedback(self, hydraId, state):
        if not state.get("hurtActive"):
            return
        if self._tick < int(state.get("hurtUntil", 0)):
            return
        state["hurtActive"] = False
        self._trigger_entity_event(hydraId, "tf_slice:hurt_off")
        # A severed head stays red through its death/explosion sequence. Only
        # actors that remain alive are restored when the flash expires.
        for actorId in self._hydra_part_actor_ids(state, aliveOnly=True):
            self._trigger_entity_event(actorId, "tf_slice:hurt_off")

    def _tick_hydra_head_death_parts(self, state, head):
        deathTick = int(head.get("deadTicks", -1))
        schedule = [("head", -1, 1, head.get("entityId"), (4.0, 4.0))]
        for segmentIndex, neckId in enumerate(head.get("neckIds") or ()):
            schedule.append(
                ("neck", segmentIndex, 10 + segmentIndex * 10, neckId, (2.0, 2.0))
            )
        for kind, segmentIndex, startTick, actorId, size in schedule:
            age = deathTick - startTick
            if actorId is not None and 0 <= age < 20:
                self._broadcast_hydra_part_death(
                    self._get_foot_pos(actorId), state["dimensionId"], size
                )
            if actorId is None or age != 20:
                continue
            if kind == "head":
                self._remove_hydra_head_only(head)
            else:
                self._remove_hydra_neck_segment(head, segmentIndex)

    def _broadcast_hydra_head(self, hydraId, index, head):
        mouth = hydra_logic.interpolated_head_pose(
            head.get("previousState", head.get("state", "idle")),
            head.get("state", "idle"),
            index,
            head.get("ticks", 0),
        )[3]
        self.BroadcastToAllClient(
            "HydraHeadSync",
            {
                "id": str(hydraId),
                "index": int(index),
                "serverTick": int(self._tick),
                "head": {
                    "state": str(head.get("state", "idle")),
                    "ticks": int(head.get("ticks", 0)),
                    "yaw": float(head.get("yaw", 0.0)),
                    "pitch": float(head.get("pitch", 0.0)),
                    "alive": bool(head.get("alive", False)),
                    "mouth": float(mouth),
                },
            },
        )

    def _sync_hydra_head_pose(self, hydraId, index, head):
        headId = head.get("entityId")
        if headId is None:
            return
        pose = hydra_logic.interpolated_head_pose(
            head.get("previousState", head.get("state", "idle")),
            head.get("state", "idle"),
            index,
            head.get("ticks", 0),
        )
        # HydraHeadContainer writes its interpolated mouth openness every tick.
        # Sending five discrete entity events made the BORN -> ROAR -> IDLE
        # curve snap between large jaw angles, which looked like repeated
        # opening/closing on newly regrown heads.
        self._set_entity_property(
            headId, "tf_slice:mouth_open", pose[3]
        )

    def _kill_hydra_head(self, hydraId, state, index):
        head = state["heads"][index]
        if not head.get("alive"):
            return
        head["alive"] = False
        head["damage"] = 0.0
        head["name"] = ""
        head["deadTicks"] = 0
        head["respawnTicks"] = hydra_logic.HEAD_RESPAWN_TICKS
        head["previousState"] = head.get("state", "idle")
        head["state"] = "dying"
        head["ticks"] = 0
        dormant = [
            candidateIndex
            for candidateIndex, candidate in enumerate(state["heads"])
            if candidateIndex != int(index)
            and not candidate.get("alive")
            and str(candidate.get("state", "dead")) == "dead"
            and int(candidate.get("respawnTicks", -1)) < 0
        ]
        if dormant:
            extraIndex = random.choice(dormant)
            state["heads"][extraIndex]["respawnTicks"] = (
                hydra_logic.HEAD_RESPAWN_TICKS
            )
        self._broadcast_hydra_head(hydraId, index, head)

    def _birth_hydra_head(self, hydraId, state, index):
        head = state["heads"][int(index)]
        bodyHealth = max(0.0, float(state.get(
            "health", hydra_logic.MAX_HEALTH
        )))
        bodyYaw = self._get_rotation(hydraId)[1]
        state["bodyYaw"] = bodyYaw
        head.update(
            {
                "alive": True,
                "damage": 0.0,
                "deadTicks": -1,
                "respawnTicks": -1,
                "previousState": head.get("state", "dead"),
                "state": "born",
                "ticks": 0,
                "yaw": bodyYaw,
                "pitch": 0.0,
                "targetId": None,
                "secondary": False,
                "aimPos": None,
                "biteVictims": set(),
            }
        )
        self._broadcast_hydra_head(hydraId, index, head)
        state["ensureAfter"] = self._tick
        self._ensure_hydra_heads(hydraId, state)
        # Creating the head and its five high-health proxy actors must never
        # alter the owner's authoritative health.  Re-pin both stores before
        # the next driver tick reads the engine attribute back into state.
        state["health"] = bodyHealth
        self._set_health(hydraId, bodyHealth)

    def _spawn_hydra_mortar(self, hydraId, state, head, targetId, mega):
        headPos = self._get_foot_pos(head.get("entityId"))
        if headPos is None:
            return None
        look = hydra_logic.look_vector(
            head.get("pitch", 0.0), head.get("yaw", 0.0)
        )
        origin = (
            float(headPos[0]) + look[0] * 3.5,
            float(headPos[1]) + 1.0 + look[1] * 3.5,
            float(headPos[2]) + look[2] * 3.5,
        )
        mortarId = self._spawn_ruin_entity(
            HYDRA_MORTAR_IDENTIFIER, origin, head.get("yaw", 0.0), state["dimensionId"]
        )
        if not mortarId:
            return None
        launch = hydra_logic.mortar_launch_motion(
            head.get("pitch", 0.0),
            head.get("yaw", 0.0),
            tuple(
                random.random() - random.random()
                for unusedAxis in range(3)
            ),
        )
        self._set_full_motion(mortarId, launch)
        self._set_entity_on_fire(mortarId, 3600)
        self._hydra_mortars[mortarId] = {
            "ownerId": hydraId,
            "mega": bool(mega),
            "fuse": 80,
            "landed": False,
            "reflected": False,
            "dimensionId": state["dimensionId"],
        }
        self._play_world_sound("mob.ghast.fireball", origin, 10.0, 1.0)
        return mortarId

    def _nearest_hydra_player(self, pos, dimensionId, maxDistance=48.0):
        best = None
        bestDistance = float(maxDistance) * float(maxDistance)
        for playerId in list(self._known_players):
            try:
                gameType = int(
                    CF.CreateGame(LEVEL_ID).GetPlayerGameType(playerId)
                )
            except Exception:
                gameType = 0
            if gameType in (1, 3, 6):
                continue
            if self._get_dimension(playerId) != dimensionId:
                continue
            playerPos = self._get_foot_pos(playerId)
            if playerPos is None:
                continue
            distance = _distance_sq(pos, playerPos)
            if distance >= bestDistance:
                continue
            best = (playerId, playerPos)
            bestDistance = distance
        return best

    def _hydra_primary_target(self, hydraId, state, bodyPos):
        if hydra_logic.should_acquire_target(random.random()):
            candidate = self._nearest_hydra_player(
                bodyPos, state["dimensionId"], 48.0
            )
            if candidate is not None:
                state["targetId"] = candidate[0]
                state["targetUntil"] = hydra_logic.target_expiry_tick(
                    self._tick, random.randrange(20)
                )
            else:
                state["randomYawVelocity"] = (
                    random.random() - 0.5
                ) * 20.0
        retainedId = state.get("targetId")
        if retainedId is not None:
            retainedPos = self._get_foot_pos(retainedId)
            try:
                gameType = int(
                    CF.CreateGame(LEVEL_ID).GetPlayerGameType(retainedId)
                )
            except Exception:
                gameType = 0
            retainedAlive = (
                retainedPos is not None and gameType not in (1, 3, 6)
            )
            retainedDistance = (
                _distance_sq(bodyPos, retainedPos)
                if retainedPos is not None else float("inf")
            )
            if hydra_logic.target_is_retained(
                self._tick,
                state.get("targetUntil", 0),
                retainedAlive,
                retainedDistance,
            ):
                return (retainedId, retainedPos)
        state["targetId"] = None
        state["targetUntil"] = 0
        return None

    def _sync_hydra_head_names(self, state):
        for head in state.get("heads", ()):
            headId = head.get("entityId")
            if headId is None:
                continue
            try:
                nameComp = CF.CreateName(headId)
                currentName = nameComp.GetName() or ""
                storedName = str(head.get("name", ""))
                if currentName and currentName != storedName:
                    head["name"] = currentName
                elif storedName and currentName != storedName:
                    nameComp.SetName(storedName)
            except Exception:
                continue

    def _push_hydra_body_collisions(self, hydraId, state):
        if state.get("hurtActive"):
            return
        positions = self._hydra_body_part_positions(hydraId, state) or {}
        for partKind in ("body", "tail"):
            center = positions.get(partKind)
            if center is None:
                continue
            partId = (state.get("partIds") or {}).get(partKind)
            if partId is None:
                continue
            filters = {
                "any_of": [
                    {
                        "test": "is_family",
                        "subject": "other",
                        "value": "mob",
                    },
                    {
                        "test": "is_family",
                        "subject": "other",
                        "value": "player",
                    },
                ]
            }
            try:
                entities = CF.CreateGame(LEVEL_ID).GetEntitiesAround(
                    partId, 4.5, filters
                ) or ()
            except Exception:
                entities = ()
            for entityId in entities:
                if self._hydra_owned_damage_source(entityId, hydraId):
                    continue
                if self._is_online_player(entityId) and self._is_creative(
                    entityId
                ):
                    continue
                position = self._get_foot_pos(entityId)
                if position is None:
                    continue
                dx = float(position[0]) - float(center[0])
                dz = float(position[2]) - float(center[2])
                distanceSq = max(dx * dx + dz * dz, 0.1)
                self._add_entity_motion(
                    entityId,
                    dx / distanceSq * 8.0,
                    0.2,
                    dz / distanceSq * 8.0,
                )

    def _hydra_can_see(self, bodyPos, targetPos, dimensionId):
        """Match Hydra.getSensing() despite the tiny Bedrock root proxy."""
        if bodyPos is None or targetPos is None or dimensionId is None:
            return False
        start = hydra_logic.hydra_eye_position(bodyPos)
        end = (targetPos[0], targetPos[1] + 0.8, targetPos[2])
        for blockPos in quest_ram_logic.ray_samples(start, end):
            blockName = self._block_name(
                self._get_block(blockPos, dimensionId)
            )
            if blockName and blockName not in SIGHT_PASSABLE_BLOCKS:
                return False
        return True

    def _hydra_secondary_target(self, hydraId, state, primary):
        primaryId = primary[0] if primary is not None else None
        filters = {
            "any_of": [
                {"test": "is_family", "subject": "other", "value": "mob"},
                {"test": "is_family", "subject": "other", "value": "player"},
            ]
        }
        try:
            candidates = CF.CreateGame(LEVEL_ID).GetEntitiesAround(
                hydraId, 20.0, filters
            ) or []
        except Exception:
            candidates = []
        bodyPos = self._get_foot_pos(hydraId)
        occupied = set(
            str(head.get("targetId"))
            for head in state.get("heads", ())
            if head.get("targetId") is not None
        )
        best = None
        bestDistance = 400.0
        for targetId in candidates:
            if str(targetId) == str(primaryId) or str(targetId) in occupied:
                continue
            if self._get_engine_type(targetId) == HYDRA_IDENTIFIER:
                continue
            if self._hydra_owned_damage_source(targetId, hydraId):
                continue
            if self._is_online_player(targetId):
                try:
                    gameType = int(
                        CF.CreateGame(LEVEL_ID).GetPlayerGameType(targetId)
                    )
                except Exception:
                    gameType = 0
                if gameType in (1, 3, 6):
                    continue
            targetPos = self._get_foot_pos(targetId)
            if targetPos is None or bodyPos is None:
                continue
            distance = _distance_sq(bodyPos, targetPos)
            if distance >= bestDistance:
                continue
            if not self._hydra_can_see(
                bodyPos, targetPos, state["dimensionId"]
            ):
                continue
            best = (targetId, targetPos)
            bestDistance = distance
        return best

    def _track_hydra_head(
        self,
        headId,
        head,
        origin,
        target,
        targetYOffset=0.8,
        turnSpeed=5.0,
        pitchTurnSpeed=None,
    ):
        dx = float(target[0]) - float(origin[0])
        dy = float(target[1]) + float(targetYOffset) - float(origin[1])
        dz = float(target[2]) - float(origin[2])
        horizontal = math.sqrt(dx * dx + dz * dz)
        wantedYaw = math.degrees(math.atan2(-dx, dz))
        wantedPitch = -math.degrees(
            math.atan2(dy, max(0.001, horizontal))
        )
        currentPitch = float(head.get("pitch", 0.0))
        currentYaw = float(head.get("yaw", 0.0))
        pitchStep = (
            float(turnSpeed)
            if pitchTurnSpeed is None
            else float(pitchTurnSpeed)
        )
        pitch = hydra_logic.approach_angle(
            currentPitch, wantedPitch, pitchStep
        )
        yaw = hydra_logic.approach_angle(currentYaw, wantedYaw, turnSpeed)
        head["pitch"] = pitch
        head["yaw"] = yaw
        try:
            CF.CreateRot(headId).SetRot((pitch, yaw))
        except Exception:
            pass

    def _face_hydra_head_state(
        self,
        hydraId,
        state,
        index,
        head,
        headId,
        headPos,
        activeState,
        targetPos,
    ):
        if headPos is None:
            return
        bodyYaw = float(state.get("bodyYaw", 0.0))
        if targetPos is None:
            bodyPos = self._get_foot_pos(hydraId)
            if bodyPos is None:
                return
            entityYaw = float(state.get("entityYaw", bodyYaw))
            if hydra_logic.lock_idle_chain_for_state(activeState):
                visualIdleYaw = hydra_logic.mobile_idle_head_yaw(
                    bodyYaw, index, self._tick
                )
            else:
                visualIdleYaw = entityYaw
            idleTarget = hydra_logic.idle_face_target(
                bodyPos, visualIdleYaw
            )
            self._track_hydra_head(
                headId,
                head,
                headPos,
                idleTarget,
                targetYOffset=-1.0,
                turnSpeed=1.5,
                pitchTurnSpeed=hydra_logic.HYDRA_MAX_HEAD_X_ROT,
            )
            return
        if activeState in ("flame_begin", "flaming"):
            aimPos = head.get("aimPos") or tuple(targetPos)
            trackingSpeed = 0.1 if self._difficulty() >= 3 else 0.04
            aimPos = hydra_logic.approach_point(
                aimPos, targetPos, trackingSpeed
            )
            head["aimPos"] = aimPos
            self._track_hydra_head(
                headId,
                head,
                headPos,
                aimPos,
                targetYOffset=0.0,
                turnSpeed=5.0,
                pitchTurnSpeed=hydra_logic.HYDRA_MAX_HEAD_X_ROT,
            )
            return
        if activeState == "roar":
            aimPos = head.get("aimPos") or tuple(targetPos)
            head["aimPos"] = aimPos
            self._track_hydra_head(
                headId,
                head,
                headPos,
                aimPos,
                targetYOffset=0.0,
                turnSpeed=10.0,
                pitchTurnSpeed=hydra_logic.HYDRA_MAX_HEAD_X_ROT,
            )
            return
        self._track_hydra_head(
            headId,
            head,
            headPos,
            targetPos,
            turnSpeed=5.0,
            pitchTurnSpeed=hydra_logic.HYDRA_MAX_HEAD_X_ROT,
        )
        if activeState == "bite_ready":
            head["yaw"] = hydra_logic.clamp_bite_yaw(
                index, bodyYaw, head.get("yaw", bodyYaw)
            )
            look = hydra_logic.look_vector(
                head.get("pitch", 0.0), head["yaw"]
            )
            head["aimPos"] = (
                float(headPos[0]) + look[0] * 16.0,
                float(headPos[1]) + 1.5 + look[1] * 16.0,
                float(headPos[2]) + look[2] * 16.0,
            )
        elif activeState in ("biting", "bite_end"):
            head["pitch"] = hydra_logic.bite_pitch_degrees(
                head.get("pitch", 0.0)
            )
        try:
            CF.CreateRot(headId).SetRot(
                (float(head.get("pitch", 0.0)), float(head.get("yaw", 0.0)))
            )
        except Exception:
            pass

    @staticmethod
    def _hydra_head_direction(head):
        return hydra_logic.look_vector(
            head.get("pitch", 0.0), head.get("yaw", 0.0)
        )

    def _hydra_flame_target(
        self,
        hydraId,
        state,
        headId,
        headPos,
        direction,
        preferredTargetId=None,
    ):
        filters = {
            "any_of": [
                {"test": "is_family", "subject": "other", "value": "mob"},
                {"test": "is_family", "subject": "other", "value": "player"},
            ]
        }
        try:
            entityIds = CF.CreateGame(LEVEL_ID).GetEntitiesAround(
                headId, 30.0, filters
            ) or []
        except Exception:
            entityIds = []
        entityIds = hydra_logic.merge_flame_candidate_ids(
            entityIds,
            preferredTargetId,
            self._get_online_players(),
        )
        origin = (float(headPos[0]), float(headPos[1]) + 1.0, float(headPos[2]))
        candidates = []
        positions = {}
        for targetId in entityIds:
            if self._hydra_owned_damage_source(targetId, hydraId):
                continue
            targetPos = self._get_foot_pos(targetId)
            if targetPos is None:
                continue
            width, height = self._collision_size(targetId, (0.6, 1.8))
            center = (
                float(targetPos[0]),
                float(targetPos[1]) + height * 0.5,
                float(targetPos[2]),
            )
            positions[str(targetId)] = center
            candidates.append((targetId, center, max(width, height) * 0.5))
        targetId = hydra_logic.flame_ray_target(origin, direction, candidates)
        if targetId is None:
            return None
        targetPos = positions.get(str(targetId))
        if targetPos is None or not self._beetle_can_see(
            origin, targetPos, state["dimensionId"]
        ):
            return None
        return targetId

    def _hydra_bite_targets(self, hydraId, headId):
        headPos = self._get_foot_pos(headId)
        dimensionId = self._get_dimension(headId)
        if headPos is None or dimensionId is None:
            return []
        halfWidth = hydra_logic.PART_COLLISIONS["head"][0] * 0.5
        height = hydra_logic.PART_COLLISIONS["head"][1]
        start = (
            float(headPos[0]) - halfWidth,
            float(headPos[1]) - 1.0,
            float(headPos[2]) - halfWidth,
        )
        end = (
            float(headPos[0]) + halfWidth,
            float(headPos[1]) + height + 1.0,
            float(headPos[2]) + halfWidth,
        )
        try:
            candidates = CF.CreateGame(LEVEL_ID).GetEntitiesInSquareArea(
                None, start, end, int(dimensionId)
            ) or []
        except Exception:
            candidates = []
        result = []
        for targetId in candidates:
            if self._hydra_owned_damage_source(targetId, hydraId):
                continue
            result.append(targetId)
        return result

    def _advance_hydra_head_brain(self, head):
        before = str(head.get("state", "idle"))
        brain = hydra_logic.HydraHeadBrain(before, head.get("ticks", 0))
        activeState = brain.tick()
        # Locked advanceHeadState assigns prevState on every completed period,
        # including IDLE -> IDLE.  Missing the same-name rollover leaves a
        # newborn's previousState at ROAR forever and replays its jaw close
        # curve every ten ticks.
        if brain.rolled_over:
            head["previousState"] = before
        if head.get("secondary") and brain.state == "cooldown":
            brain.state = "idle"
            brain.ticks = 0
            head["secondary"] = False
            head["targetId"] = None
        head["state"] = brain.state
        head["ticks"] = brain.ticks
        return brain.state

    def _hydra_head_attack_tick(
        self,
        hydraId,
        state,
        index,
        head,
        target,
        secondaryTarget=None,
        primaryVisible=True,
    ):
        headId = head.get("entityId")
        if headId is None:
            return
        attackStates = (
            "bite_begin", "bite_ready", "biting", "bite_end",
            "flame_begin", "flaming", "flame_end",
            "mortar_begin", "mortar_shoot", "mortar_end",
        )
        if (
            head.get("targetId") is not None
            and str(head.get("state", "idle")) in attackStates
        ):
            targetId = head.get("targetId")
            targetPos = self._get_foot_pos(targetId)
            target = (targetId, targetPos) if targetPos is not None else None
        targetId, targetPos = target if target is not None else (None, None)
        previousState = str(head.get("state", "idle"))
        activeState = self._advance_hydra_head_brain(head)
        headPos = self._hydra_head_position(
            hydraId,
            index,
            head,
            bodyYaw=state.get("bodyYaw"),
        ) or self._get_foot_pos(headId)
        self._face_hydra_head_state(
            hydraId,
            state,
            index,
            head,
            headId,
            headPos,
            activeState,
            targetPos,
        )
        brain = hydra_logic.HydraHeadBrain(head["state"], head["ticks"])
        if activeState == "biting" and previousState != "biting":
            head["biteVictims"] = set()
        if activeState == "idle" and headPos is not None:
            attack = None
            states = [
                other.get("state", "idle")
                for otherIndex, other in enumerate(state["heads"])
                if otherIndex != index and other.get("alive")
            ]
            activeHeads = sum(
                1 for other in state["heads"] if other.get("alive")
            )
            if primaryVisible and targetId is not None and targetPos is not None:
                bodyPos = self._get_foot_pos(hydraId) or headPos
                distance = math.sqrt(_distance_sq(bodyPos, targetPos))
                difficultyFactor = 0.5 if self._difficulty() >= 3 else 0.3
                attack = hydra_logic.choose_primary_attack(
                    index,
                    distance,
                    float(targetPos[1])
                    > float(bodyPos[1]) + hydra_logic.ROOT_COLLISION_HEIGHT,
                    activeHeads,
                    hydra_logic.attack_weight(states),
                    random.randrange(10),
                    random.randrange(100),
                    random.randrange(160),
                    difficultyFactor,
                    any(
                        name in (
                            "bite_begin", "bite_ready", "biting"
                        )
                        for name in states
                    ),
                )
            if attack is not None:
                head["previousState"] = head.get("state", "idle")
                head["secondary"] = False
                head["targetId"] = targetId
                head["aimPos"] = tuple(targetPos) if targetPos is not None else None
                head["biteVictims"] = set()
                brain.begin(attack)
                head["state"] = brain.state
                head["ticks"] = brain.ticks
            elif secondaryTarget is not None and index > 0:
                secondaryId, secondaryPos = secondaryTarget
                bodyPos = self._get_foot_pos(hydraId)
                bodyDistance = math.sqrt(
                    _distance_sq(bodyPos or headPos, secondaryPos)
                )
                onSide = (
                    bodyPos is not None
                    and (
                        (float(headPos[0]) - float(secondaryPos[0])) ** 2
                        + (float(headPos[2]) - float(secondaryPos[2])) ** 2
                    )
                    < (
                        (float(bodyPos[0]) - float(secondaryPos[0])) ** 2
                        + (float(bodyPos[2]) - float(secondaryPos[2])) ** 2
                    )
                )
                attack = hydra_logic.choose_secondary_attack(
                    index,
                    bodyDistance,
                    onSide,
                    random.randrange(10),
                    random.randrange(16),
                )
                if attack is not None:
                    head["previousState"] = head.get("state", "idle")
                    head["secondary"] = True
                    head["targetId"] = secondaryId
                    head["aimPos"] = tuple(secondaryPos)
                    head["biteVictims"] = set()
                    brain.begin(attack)
                    head["state"] = brain.state
                    head["ticks"] = brain.ticks
        elif activeState == "biting" and targetId is not None:
            victims = head.setdefault("biteVictims", set())
            for bittenId in self._hydra_bite_targets(hydraId, headId):
                if not hydra_logic.register_attack_victim(victims, bittenId):
                    continue
                biteDamage = hydra_logic.difficulty_scaled_damage(
                    hydra_logic.BITE_DAMAGE, self._difficulty()
                )
                self._hurt(
                    bittenId,
                    biteDamage,
                    hydraId,
                    causeName="EntityAttack",
                )
                blocking = (
                    self._is_online_player(bittenId)
                    and self._is_blocking(bittenId)
                )
                if blocking:
                    self._damage_shield(bittenId, 112)
                    self._shield_cooldowns[bittenId] = self._tick + 200
                    self._stop_using_item(bittenId)
                    self._play_shield_break_sound(bittenId)
                self._set_full_motion(
                    bittenId,
                    hydra_logic.bite_throw_motion(
                        head.get("yaw", 0.0), blocking
                    ),
                )
        elif activeState == "flaming" and headPos is not None:
            direction = self._hydra_head_direction(head)
            burnedId = self._hydra_flame_target(
                hydraId,
                state,
                headId,
                headPos,
                direction,
                preferredTargetId=head.get("targetId"),
            )
            flameDamage = hydra_logic.difficulty_scaled_damage(
                hydra_logic.FLAME_DAMAGE, self._difficulty()
            )
            if burnedId is not None and self._hurt(
                burnedId,
                flameDamage,
                hydraId,
                causeName="Fire",
            ):
                self._set_entity_on_fire(burnedId, 3)
            if self._tick % 5 == 0:
                self._play_world_sound(
                    "mob.ghast.fireball", headPos, 0.8, random.uniform(0.3, 1.0)
                )
        elif activeState == "mortar_shoot" and headPos is not None:
            if hydra_logic.mortar_shot_ticks(head.get("ticks", 0)):
                hidden = bool(
                    targetPos is not None
                    and not self._beetle_can_see(
                        headPos, targetPos, state["dimensionId"]
                    )
                )
                self._spawn_hydra_mortar(hydraId, state, head, targetId, hidden)
        effectKind = {
            "flame_begin": "hydra_flame_charge",
            "flaming": "hydra_flame",
            "mortar_begin": "hydra_mortar_charge",
            "bite_begin": "hydra_bite_charge",
            "bite_ready": "hydra_bite_charge",
        }.get(activeState)
        if effectKind is not None and headPos is not None:
            direction = self._hydra_head_direction(head)
            self.BroadcastToAllClient(
                "HydraRouteEffect",
                {
                    "kind": effectKind,
                    "dimensionId": state["dimensionId"],
                    "position": headPos,
                    "direction": direction,
                },
            )
        if str(head.get("state")) != previousState:
            if head.get("state") == "roar":
                self._play_world_sound(
                    "tf_slice.hydra.roar", headPos, 1.25, 0.85
                )
            self._broadcast_hydra_head(hydraId, index, head)
        if activeState == "bite_ready" and int(head.get("ticks", 0)) == 60:
            self._play_world_sound(
                "tf_slice.hydra.warn", headPos, 2.0, 0.85
            )

    def _begin_hydra_death(self, hydraId, state):
        if state.get("dying") or state.get("dead"):
            return
        state["dying"] = True
        state["deathTicks"] = 0
        state["health"] = 0.0
        self._set_health(hydraId, 1.0)
        for index, head in enumerate(state["heads"]):
            head["previousState"] = head.get("state", "idle")
            head["state"] = "idle" if head.get("alive") else "dead"
            head["ticks"] = 0
            head["respawnTicks"] = -1
            self._broadcast_hydra_head(hydraId, index, head)
        self._play_world_sound(
            "tf_slice.hydra.death", self._get_foot_pos(hydraId), 2.0, 1.0
        )
        self._save_hydra_state(hydraId, state)

    def _spawn_route_boss_experience(self, amount, position):
        if position is None:
            return False
        try:
            return CF.CreateExp(LEVEL_ID).CreateExperienceOrb(
                int(amount),
                tuple(float(value) for value in position),
                False,
            ) is not False
        except Exception as error:
            print "[TwilightBossSlice] route boss experience spawn failed:", error
            return False

    def _hydra_looting_level(self, playerId):
        if playerId is None or not self._is_online_player(playerId):
            return 0
        item = self._carried_item(playerId) or {}
        enchants = item.get("enchantData", item.get("enchants", ()))
        if isinstance(enchants, dict):
            for key in ("minecraft:looting", "looting", 14, "14"):
                if key in enchants:
                    try:
                        return max(0, int(enchants[key]))
                    except (TypeError, ValueError):
                        return 0
        for enchant in enchants if isinstance(enchants, (list, tuple)) else ():
            if isinstance(enchant, dict):
                name = enchant.get("id", enchant.get("name"))
                level = enchant.get("level", enchant.get("lvl", 0))
            elif isinstance(enchant, (list, tuple)) and len(enchant) >= 2:
                name, level = enchant[0], enchant[1]
            else:
                continue
            if str(name) in ("14", "looting", "minecraft:looting"):
                try:
                    return max(0, int(level))
                except (TypeError, ValueError):
                    return 0
        return 0

    def _spawn_hydra_loot_item(
        self, itemName, count, dimensionId, position
    ):
        if int(count) <= 0:
            return False
        try:
            self.CreateEngineItemEntity(
                {
                    "newItemName": itemName,
                    "newAuxValue": 0,
                    "count": int(count),
                },
                dimensionId,
                position,
            )
            return True
        except Exception as error:
            print "[TwilightBossSlice] Hydra loot spawn failed:", error
            return False

    def _place_hydra_loot_chest(self, hydraId, state):
        position = self._get_foot_pos(hydraId) or state.get("home")
        if position is None:
            return False
        chestPos = (
            int(math.floor(position[0])),
            int(math.floor(position[1])),
            int(math.floor(position[2])),
        )
        dimensionId = int(state["dimensionId"])
        lootingLevel = max(0, int(state.get("lastLootingLevel", 0)))
        baseChops = random.randint(5, 35)
        baseBlood = random.randint(7, 10)
        loot = hydra_logic.hydra_loot_counts(
            base_chops=baseChops,
            base_blood=baseBlood,
            looting_level=lootingLevel,
            chop_roll=random.uniform(0.0, 1.0),
            blood_roll=random.uniform(0.0, 2.0),
        )
        dropPos = (
            float(chestPos[0]) + 0.5,
            float(chestPos[1]) + 0.8,
            float(chestPos[2]) + 0.5,
        )
        if self._set_block(
            chestPos, "minecraft:chest", dimensionId
        ) is not False:
            try:
                result = self._block_comp.SetChestLootTable(
                    chestPos,
                    dimensionId,
                    config.HYDRA_LOOT_TABLE,
                )
                if result is not False:
                    self._spawn_hydra_loot_item(
                        "tf_slice:hydra_chop",
                        loot["hydra_chop"] - baseChops,
                        dimensionId,
                        dropPos,
                    )
                    self._spawn_hydra_loot_item(
                        "tf_slice:fiery_blood",
                        loot["fiery_blood"] - baseBlood,
                        dimensionId,
                        dropPos,
                    )
                    return True
            except Exception as error:
                print "[TwilightBossSlice] Hydra chest loot failed:", error
        for itemName, count in (
            ("tf_slice:fiery_blood", loot["fiery_blood"]),
            ("tf_slice:hydra_chop", loot["hydra_chop"]),
            ("tf_slice:hydra_trophy_item", 1),
        ):
            self._spawn_hydra_loot_item(
                itemName, count, dimensionId, dropPos
            )
        return False

    def _award_hydra_once(self, hydraId, state):
        if state.get("rewarded"):
            return False
        rewardAllowed = True
        if self._ruin_worldgen is not None:
            managed = self._ruin_worldgen.mark_boss_defeated(
                state.get("home"), "hydra"
            )
            if managed:
                rewardAllowed = self._ruin_worldgen.claim_boss_reward(
                    state.get("home"), "hydra"
                )
        state["rewarded"] = True
        participants = sorted(state.get("participants", ()))
        for playerId in participants:
            self._grant_progress(playerId, "tf_hydra_defeated")
        if rewardAllowed:
            position = self._get_foot_pos(hydraId) or state.get("home")
            self._spawn_route_boss_experience(hydra_logic.XP_REWARD, position)
            self._place_hydra_loot_chest(hydraId, state)
        self._save_hydra_state(hydraId, state)
        return True

    def _clear_hydra_block_volume(self, hydraId, state):
        if not self._mob_griefing():
            return 0
        bodyPos = self._get_foot_pos(hydraId)
        if bodyPos is None:
            return 0
        partPositions = self._hydra_body_part_positions(hydraId, state) or {}
        centers = []
        if partPositions.get("body") is not None:
            centers.append((partPositions["body"], 3, 0, 6))
        if partPositions.get("tail") is not None:
            centers.append((partPositions["tail"], 3, 0, 2))
        for index, head in enumerate(state.get("heads", ())):
            if not head.get("alive"):
                continue
            headPos = self._get_foot_pos(head.get("entityId"))
            if headPos is not None:
                centers.append((headPos, 2, 0, 4))
        if self._tick % 20 == 0:
            solid = 0
            total = 0
            baseY = int(math.floor(bodyPos[1])) - 1
            for xOffset in range(-3, 4):
                for zOffset in range(-3, 4):
                    total += 1
                    blockName = self._block_name(
                        self._get_block(
                            (
                                int(math.floor(bodyPos[0])) + xOffset,
                                baseY,
                                int(math.floor(bodyPos[2])) + zOffset,
                            ),
                            state["dimensionId"],
                        )
                    )
                    if blockName not in (
                        "minecraft:air",
                        "minecraft:cave_air",
                        "minecraft:void_air",
                        "minecraft:water",
                        "minecraft:flowing_water",
                    ):
                        solid += 1
            if total and float(solid) / float(total) < 0.6:
                centers.append((bodyPos, 3, -1, -1))
        removed = 0
        limit = min(64, int(getattr(config, "MAX_BLOCKS_PER_CLEAR", 64)))
        for center, radius, minYOffset, maxYOffset in centers:
            baseX = int(math.floor(center[0]))
            baseY = int(math.floor(center[1]))
            baseZ = int(math.floor(center[2]))
            for yOffset in range(minYOffset, maxYOffset + 1):
                for xOffset in range(-radius, radius + 1):
                    for zOffset in range(-radius, radius + 1):
                        pos = (
                            baseX + xOffset,
                            baseY + yOffset,
                            baseZ + zOffset,
                        )
                        blockName = self._block_name(
                            self._get_block(pos, state["dimensionId"])
                        )
                        if not self._can_destroy(blockName):
                            continue
                        if self._set_block(
                            pos, "minecraft:air", state["dimensionId"]
                        ) is False:
                            continue
                        removed += 1
                        if removed >= limit:
                            return removed
        return removed

    def _discard_hydra(self, hydraId, state, restoreSpawner=False):
        self._remove_hydra_body_parts(state)
        for head in state.get("heads", ()):
            self._remove_hydra_head_actor(head)
        for mortarId, mortar in list(self._hydra_mortars.items()):
            if str(mortar.get("ownerId")) != str(hydraId):
                continue
            self._hydra_mortars.pop(mortarId, None)
            try:
                self.DestroyEntity(mortarId)
            except Exception:
                pass
        if restoreSpawner and self._ruin_worldgen is not None:
            self._ruin_worldgen.mark_boss_missing(
                state.get("home"), hydraId, "hydra"
            )
        self._hydras.pop(hydraId, None)
        try:
            self.DestroyEntity(hydraId)
        except Exception:
            pass

    def _drive_hydras(self):
        for hydraId, state in list(self._hydras.items()):
            if state.get("dead"):
                continue
            if self._difficulty() == 0 and not state.get("dying"):
                self._discard_hydra(hydraId, state, restoreSpawner=True)
                continue
            if state.get("dying"):
                state["deathTicks"] += 1
                deathPos = self._get_foot_pos(hydraId) or state.get("home")
                if deathPos is not None:
                    self.BroadcastToAllClient(
                        "HydraRouteEffect",
                        {
                            "kind": "hydra_death_body",
                            "dimensionId": state["dimensionId"],
                            "position": deathPos,
                        },
                    )
                event = hydra_logic.death_event(state["deathTicks"])
                if event.get("head_explosion"):
                    headIndex = int(state["deathTicks"] / 20) - 1
                    if 0 <= headIndex < len(state["heads"]):
                        head = state["heads"][headIndex]
                        if head.get("alive"):
                            head["alive"] = False
                            head["previousState"] = head.get(
                                "state", "idle"
                            )
                            head["state"] = "dying"
                            head["ticks"] = 0
                            head["deadTicks"] = 0
                            head["respawnTicks"] = -1
                            self._broadcast_hydra_head(
                                hydraId, headIndex, head
                            )
                for headIndex, head in enumerate(state["heads"]):
                    if int(head.get("deadTicks", -1)) < 0:
                        continue
                    head["deadTicks"] = hydra_logic.next_dead_ticks(
                        head["deadTicks"]
                    )
                    self._advance_hydra_head_brain(head)
                    self._tick_hydra_head_death_parts(state, head)
                    if head.get("entityId") is not None:
                        frame = self._compute_hydra_chain_frame(
                            hydraId, state, headIndex, head
                        )
                        if not self._apply_hydra_chain_frame(
                            hydraId, state, headIndex, head, frame
                        ):
                            self._remove_hydra_head_actor(head)
                if event.get("settle") or state["deathTicks"] > hydra_logic.DEATH_TICKS:
                    if not self._award_hydra_once(hydraId, state) and not state.get("rewarded"):
                        continue
                    state["dead"] = True
                    self._save_hydra_state(hydraId, state)
                    self._discard_hydra(hydraId, state, restoreSpawner=False)
                continue
            self._ensure_hydra_body_parts(hydraId, state)
            self._ensure_hydra_heads(hydraId, state)
            self._tick_hydra_hurt_feedback(hydraId, state)
            engineHealth = self._get_health(hydraId, state["health"])
            if engineHealth <= 0.0 < float(state.get("health", 0.0)):
                self._set_health(hydraId, state["health"])
            else:
                state["health"] = engineHealth
            state["ticksSinceDamage"] += 1
            heal = hydra_logic.heal_amount(state["ticksSinceDamage"])
            if heal and state["health"] < hydra_logic.MAX_HEALTH:
                state["health"] = min(hydra_logic.MAX_HEALTH, state["health"] + heal)
                self._set_health(hydraId, state["health"])
            bodyPos = self._get_foot_pos(hydraId)
            target = (
                self._hydra_primary_target(hydraId, state, bodyPos)
                if bodyPos
                else None
            )
            primaryVisible = bool(
                target is not None
                and self._hydra_can_see(
                    bodyPos, target[1], state["dimensionId"]
                )
            )
            if target is not None:
                targetPos = target[1]
                dx = float(targetPos[0]) - float(bodyPos[0])
                dz = float(targetPos[2]) - float(bodyPos[2])
                wantedYaw = math.degrees(math.atan2(-dx, dz))
                bodyPitch, engineBodyYaw = self._get_rotation(hydraId)
                bodyYaw = float(state.get("bodyYaw", engineBodyYaw))
                entityYaw = float(state.get("entityYaw", engineBodyYaw))
                entityYaw = hydra_logic.approach_angle(
                    entityYaw, wantedYaw, 10.0
                )
                headStates = [
                    head.get("state", "idle")
                    for head in state.get("heads", ())
                    if head.get("alive")
                ]
                if hydra_logic.combat_body_turn_active(headStates):
                    bodyYaw = hydra_logic.body_yaw_after_head_turn(
                        bodyYaw, bodyYaw, entityYaw
                    )
                else:
                    bodyYaw = hydra_logic.locked_idle_body_yaw(
                        bodyYaw, entityYaw
                    )
                state["entityYaw"] = entityYaw
                state["bodyYaw"] = bodyYaw
                try:
                    CF.CreateRot(hydraId).SetRot((bodyPitch, bodyYaw))
                except Exception:
                    pass
            else:
                bodyPitch, engineBodyYaw = self._get_rotation(hydraId)
                bodyYaw = float(state.get("bodyYaw", engineBodyYaw))
                entityYaw = float(state.get("entityYaw", engineBodyYaw))
                reroll = random.random() < 0.05
                entityYaw, velocity = hydra_logic.idle_body_yaw(
                    entityYaw,
                    state.get("randomYawVelocity", 0.0),
                    reroll,
                    (random.random() - 0.5) * 20.0,
                )
                bodyYaw = hydra_logic.locked_idle_body_yaw(
                    bodyYaw, entityYaw
                )
                state["entityYaw"] = entityYaw
                state["bodyYaw"] = bodyYaw
                state["randomYawVelocity"] = velocity
                try:
                    CF.CreateRot(hydraId).SetRot((bodyPitch, bodyYaw))
                except Exception:
                    pass
            self._ensure_hydra_body_parts(hydraId, state)
            self._push_hydra_body_collisions(hydraId, state)
            self._clear_hydra_block_volume(hydraId, state)
            try:
                CF.CreateAttr(hydraId).SetEntityOnFire(0, 0)
            except Exception:
                pass
            secondaryTarget = self._hydra_secondary_target(
                hydraId, state, target
            )
            for index, head in enumerate(state["heads"]):
                if not head.get("alive"):
                    respawnTicks, shouldBirth = (
                        hydra_logic.advance_respawn_counter(
                            head.get("state", "dead"),
                            head.get("respawnTicks", -1),
                        )
                    )
                    head["respawnTicks"] = respawnTicks
                    if shouldBirth:
                        self._birth_hydra_head(hydraId, state, index)
                        continue
                    if int(head.get("deadTicks", -1)) >= 0:
                        head["deadTicks"] = hydra_logic.next_dead_ticks(
                            head["deadTicks"]
                        )
                        self._advance_hydra_head_brain(head)
                        self._tick_hydra_head_death_parts(state, head)
                        if head.get("entityId") is not None:
                            frame = self._compute_hydra_chain_frame(
                                hydraId, state, index, head
                            )
                            if not self._apply_hydra_chain_frame(
                                hydraId, state, index, head, frame
                            ):
                                self._remove_hydra_head_actor(head)
                    continue
                self._hydra_head_attack_tick(
                    hydraId,
                    state,
                    index,
                    head,
                    target,
                    secondaryTarget,
                    primaryVisible,
                )
                if head.get("entityId") is not None:
                    frame = self._compute_hydra_chain_frame(
                        hydraId, state, index, head
                    )
                    if not self._apply_hydra_chain_frame(
                        hydraId, state, index, head, frame
                    ):
                        self._remove_hydra_head_actor(head)
            if self._tick % 20 == 0:
                self._sync_hydra_head_names(state)
                self._save_hydra_state(hydraId, state)

    def _sync_hydra_mortar_fuse(self, mortarId, fuse):
        fuse = max(0, min(100, int(fuse)))
        return self._trigger_entity_event(
            mortarId, "tf_slice:mortar_fuse_%d" % fuse
        )

    def _reflect_hydra_mortar(self, mortarId, attackerId):
        mortarKey = entity_registry_logic.matching_entity_key(
            self._hydra_mortars, mortarId
        )
        if mortarKey is None or attackerId is None:
            return False
        mortar = self._hydra_mortars[mortarKey]
        if (
            int(mortar.get("lastReflectTick", -100)) == self._tick
            and str(mortar.get("ownerId")) == str(attackerId)
        ):
            return True
        rotation = self._get_rotation(attackerId)
        pitch = math.radians(float(rotation[0]))
        yaw = math.radians(float(rotation[1]))
        look = (
            -math.sin(yaw) * math.cos(pitch),
            -math.sin(pitch),
            math.cos(yaw) * math.cos(pitch),
        )
        reflected = hydra_logic.reflect_mortar(
            mortar.get("ownerId"), attackerId, look
        )
        mortar["ownerId"] = reflected["owner"]
        mortar["reflected"] = True
        mortar["fuse"] = (
            int(mortar.get("fuse", 0)) + reflected["added_fuse"]
        )
        mortar["landed"] = False
        mortar["lastReflectTick"] = self._tick
        self._sync_hydra_mortar_fuse(mortarId, mortar["fuse"])
        self._trigger_entity_event(mortarId, "tf_slice:launched")
        self._set_full_motion(mortarId, reflected["motion"])
        return True

    def _update_hydra_mortars(self):
        for mortarId, state in list(self._hydra_mortars.items()):
            previousFuse = int(state.get("fuse", 80))
            state["fuse"] = hydra_logic.mortar_fuse_after_tick(
                previousFuse, state.get("landed", False)
            )
            if int(state["fuse"]) != previousFuse:
                self._sync_hydra_mortar_fuse(mortarId, state["fuse"])
            if state["fuse"] > 0:
                continue
            self._detonate_hydra_mortar(mortarId)

    def _detonate_hydra_mortar(self, mortarId):
        mortarKey = entity_registry_logic.matching_entity_key(
            self._hydra_mortars, mortarId
        )
        if mortarKey is None:
            return False
        state = self._hydra_mortars[mortarKey]
        mortarPos = self._get_foot_pos(mortarId)
        filters = {
            "any_of": [
                {"test": "is_family", "subject": "other", "value": "mob"},
                {"test": "is_family", "subject": "other", "value": "player"},
            ]
        }
        try:
            nearby = CF.CreateGame(LEVEL_ID).GetEntitiesAround(
                mortarId, 1.5, filters
            ) or []
        except Exception:
            nearby = []
        for targetId in nearby:
            if str(targetId) == str(mortarId):
                continue
            if (
                not state.get("reflected")
                and self._hydra_owned_damage_source(
                    targetId, state.get("ownerId")
                )
            ):
                continue
            mortarDamage = hydra_logic.difficulty_scaled_damage(
                hydra_logic.MORTAR_DAMAGE, self._difficulty()
            )
            if self._hurt(
                targetId,
                mortarDamage,
                mortarId,
                causeName="Fire",
            ):
                self._set_entity_on_fire(targetId, 5)
        self._hydra_mortars.pop(mortarKey, None)
        if (
            state.get("mega")
            and mortarPos is not None
            and self._mob_griefing()
        ):
            center = tuple(int(math.floor(value)) for value in mortarPos)
            for dx in range(-4, 5):
                for dy in range(-4, 5):
                    for dz in range(-4, 5):
                        if dx * dx + dy * dy + dz * dz > 16:
                            continue
                        blockPos = (
                            center[0] + dx,
                            center[1] + dy,
                            center[2] + dz,
                        )
                        blockName = self._block_name(
                            self._get_block(
                                blockPos,
                                state.get(
                                    "dimensionId", config.DIMENSION_ID
                                ),
                            )
                        )
                        if not self._can_destroy(blockName):
                            continue
                        self._set_block(
                            blockPos,
                            "minecraft:air",
                            state.get(
                                "dimensionId", config.DIMENSION_ID
                            ),
                        )
        self._trigger_entity_event(
            mortarId,
            "tf_slice:explode_mega" if state.get("mega") else "tf_slice:explode",
        )
        return True

    def _load_minoshroom_state(self, entityId):
        try:
            value = CF.CreateExtraData(entityId).GetExtraData(
                MINOSHROOM_STATE_EXTRA_KEY
            )
        except Exception:
            value = None
        if not isinstance(value, dict):
            return None
        try:
            home = value.get("home")
            if home is None or len(home) != 3:
                return None
            charge = value.get("charge")
            if isinstance(charge, dict):
                charge = dict(charge)
                destination = charge.get("destination")
                if destination is not None and len(destination) == 3:
                    charge["destination"] = tuple(
                        float(component) for component in destination
                    )
                charge["navigation_done"] = False
            else:
                charge = None
            slam = value.get("slam")
            if isinstance(slam, dict):
                slam = dict(slam)
            else:
                slam = None
            return {
                "dimensionId": int(value.get("dimensionId", config.DIMENSION_ID)),
                "home": tuple(float(component) for component in home),
                "health": max(
                    0.0,
                    min(
                        minotaur_logic.MINOSHROOM_HEALTH,
                        float(value.get("health", minotaur_logic.MINOSHROOM_HEALTH)),
                    ),
                ),
                "lastLootingLevel": max(0, int(value.get("lastLootingLevel", 0))),
                "lootDeliveryKey": value.get("lootDeliveryKey"),
                "participants": set(
                    str(playerId) for playerId in value.get("participants", ())
                ),
                "rewarded": bool(value.get("rewarded", False)),
                "charge": charge,
                "slam": slam,
                "slamCooldown": max(
                    0,
                    int(
                        value.get(
                            "slamCooldown",
                            value.get("nextSlamDelay", 0),
                        )
                    ),
                ),
            }
        except (TypeError, ValueError):
            return None

    def _save_minoshroom_state(self, entityId, state):
        if entityId is None or state is None or state.get("home") is None:
            return False
        charge = state.get("charge")
        if isinstance(charge, dict):
            charge = dict(charge)
            destination = charge.get("destination")
            if destination is not None:
                charge["destination"] = [
                    float(component) for component in destination
                ]
            charge.pop("navigation_done", None)
            charge.pop("navigation_issued", None)
        slam = state.get("slam")
        if isinstance(slam, dict):
            slam = dict(slam)
        value = {
            "version": 2,
            "dimensionId": int(state.get("dimensionId", config.DIMENSION_ID)),
            "home": [float(component) for component in state["home"]],
            "health": self._get_health(
                entityId, minotaur_logic.MINOSHROOM_HEALTH
            ),
            "lastLootingLevel": max(0, int(state.get("lastLootingLevel", 0))),
            "lootDeliveryKey": state.get("lootDeliveryKey"),
            "participants": sorted(
                str(playerId) for playerId in state.get("participants", ())
            ),
            "rewarded": bool(state.get("rewarded", False)),
            "charge": charge,
            "slam": slam,
            "slamCooldown": max(0, int(state.get("slamCooldown", 0))),
        }
        try:
            extra = CF.CreateExtraData(entityId)
            extra.SetExtraData(MINOSHROOM_STATE_EXTRA_KEY, value, False)
            return bool(extra.SaveExtraData())
        except Exception as error:
            print "[TwilightBossSlice] Minoshroom state save failed:", error
            return False

    def _register_route_mob(self, entityId, entityType, dimensionId):
        persistent = (
            self._load_minoshroom_state(entityId)
            if entityType == MINOSHROOM_IDENTIFIER
            else None
        )
        self._route_mobs[entityId] = {
            "type": entityType,
            "dimensionId": int(
                persistent.get("dimensionId", dimensionId)
                if persistent
                else dimensionId
            ),
            "charge": persistent.get("charge") if persistent else None,
            "slam": persistent.get("slam") if persistent else None,
            "targetId": None,
            "meleeCooldown": 0,
            "slamRecoveryTicks": 0,
            "slamCooldown": (
                persistent.get("slamCooldown", 0) if persistent else 0
            ),
            "lastLootingLevel": int(persistent.get("lastLootingLevel", 0)) if persistent else 0,
            "lootDeliveryKey": persistent.get("lootDeliveryKey") if persistent else None,
            "participants": set(
                persistent.get("participants", ()) if persistent else ()
            ),
            "rewarded": bool(persistent and persistent.get("rewarded", False)),
            "size": 4,
            "home": (
                persistent.get("home")
                if persistent
                else self._get_foot_pos(entityId)
            ),
            "actorLoaded": True,
        }
        if entityType in (MINOTAUR_IDENTIFIER, MINOSHROOM_IDENTIFIER):
            self._ensure_route_weapon(entityId, entityType)
        if entityType == MINOSHROOM_IDENTIFIER:
            self._set_health_cap(entityId, minotaur_logic.MINOSHROOM_HEALTH)
            if persistent:
                self._set_health(entityId, max(1.0, persistent["health"]))
                if persistent.get("slam"):
                    self._set_entity_property(
                        entityId,
                        "tf_slice:slam_duration",
                        max(
                            1,
                            min(
                                59,
                                int(
                                    persistent["slam"].get(
                                        "ticks_remaining", 30
                                    )
                                ),
                            ),
                        ),
                    )
                    self._trigger_entity_event(
                        entityId, "tf_slice:start_ground_attack"
                    )
                elif persistent.get("charge"):
                    self._trigger_entity_event(
                        entityId, "tf_slice:start_charging"
                    )
            self._save_minoshroom_state(entityId, self._route_mobs[entityId])
        elif entityType == MINOTAUR_IDENTIFIER:
            self._set_health_cap(entityId, minotaur_logic.MINOTAUR_HEALTH)
        elif entityType == MAZE_SLIME_IDENTIFIER:
            size = self._pending_maze_slime_sizes.pop(entityId, None)
            if size is None:
                difficulty = self._difficulty()
                specialMultiplier = max(
                    0.0, min(1.0, (float(difficulty) - 1.0) / 2.0)
                )
                size = maze_slime_logic.spawn_size(
                    random.randrange(3),
                    random.random(),
                    specialMultiplier,
                )
            self._set_maze_slime_size(entityId, self._route_mobs[entityId], size)

    def _ensure_route_weapon(self, entityId, entityType):
        """Keep the equipment table as a fallback, but repair an empty hand.

        NetEase may create the scripted entity before its equipment table has
        populated the carried slot.  The Java entities are never unarmed, so
        the server adapter owns a second, source-valid assignment here.
        """
        isMinoshroom = entityType == MINOSHROOM_IDENTIFIER
        allowed = (
            minotaur_logic.MINOSHROOM_WEAPONS
            if isMinoshroom
            else minotaur_logic.MINOTAUR_WEAPONS
        )
        carried = self._entity_carried_item(entityId)
        if portal_logic.item_name(carried) in allowed:
            return True
        weaponName = minotaur_logic.spawn_weapon(
            isMinoshroom,
            random.randrange(10),
            self._difficulty(),
        )
        return self._set_entity_carried_item(
            entityId,
            {
                "newItemName": weaponName,
                "newAuxValue": 0,
                "count": 1,
            },
        )

    def _set_maze_slime_size(self, entityId, state, size):
        size = maze_slime_logic.normalize_size(size)
        stats = maze_slime_logic.size_stats(size)
        state["size"] = size
        self._trigger_entity_event(entityId, "tf_slice:set_size_%d" % size)
        self._set_health_max(entityId, stats["health"])
        self._set_health(entityId, stats["health"])
        return size

    def _stop_route_charge(self, entityId, state):
        if state.get("charge") is None:
            return
        state["charge"] = minotaur_logic.cancel_charge(state["charge"])
        state["charge"] = None
        self._trigger_entity_event(entityId, "tf_slice:stop_charging")
        self._set_motion(entityId, 0.0, 0.0)
        targetId = state.get("targetId")
        if self._route_attackable_player_position(
            targetId, state["dimensionId"]
        ) is not None:
            self._set_attack_target(entityId, targetId)
        else:
            state["targetId"] = None

    def _stop_route_slam(self, entityId, state, recover=False):
        slam = state.get("slam")
        if slam is None:
            return
        state["slamCooldown"] = max(
            int(state.get("slamCooldown", 0)),
            int(slam.get("cooldown_ticks", 0)),
        )
        state["slam"] = minotaur_logic.cancel_slam(slam)
        state["slam"] = None
        if recover:
            state["slamRecoveryTicks"] = minotaur_logic.SLAM_RECOVERY_TICKS
            self._trigger_entity_event(
                entityId, "tf_slice:impact_ground_attack"
            )
        else:
            state["slamRecoveryTicks"] = 0
            self._trigger_entity_event(entityId, "tf_slice:stop_ground_attack")
        targetId = state.get("targetId")
        if self._route_attackable_player_position(
            targetId, state["dimensionId"]
        ) is not None:
            self._set_attack_target(entityId, targetId)
        else:
            state["targetId"] = None

    def _tick_route_slam_recovery(self, entityId, state):
        remaining, shouldClear = minotaur_logic.advance_slam_recovery(
            state.get("slamRecoveryTicks", 0)
        )
        state["slamRecoveryTicks"] = remaining
        if shouldClear:
            self._trigger_entity_event(
                entityId, "tf_slice:finish_ground_recovery"
            )

    def _start_route_charge_navigation(self, entityId, state):
        charge = state.get("charge")
        if charge is None or charge.get("navigation_issued"):
            return
        destination = charge.get("destination")
        if destination is None:
            charge["navigation_done"] = True
            return
        charge["navigation_issued"] = True
        charge.setdefault("navigation_token", "%s:%s" % (entityId, self._tick))
        navigationToken = charge["navigation_token"]

        def callback(callbackEntityId, result):
            routeKey = entity_registry_logic.matching_entity_key(
                self._route_mobs, callbackEntityId
            )
            if routeKey is None:
                return
            active = self._route_mobs[routeKey].get("charge")
            if (
                active is not None
                and active.get("phase") == "moving"
                and active.get("navigation_token") == navigationToken
            ):
                active["navigation_done"] = True

        try:
            CF.CreateMoveTo(entityId).SetMoveSetting(
                tuple(destination),
                minotaur_logic.CHARGE_SPEED,
                config.NAVIGATION_MAX_ITERATIONS,
                callback,
            )
        except Exception:
            charge["navigation_done"] = True

    def _add_entity_motion(self, entityId, x, y, z):
        try:
            motionComp = CF.CreateActorMotion(entityId)
            current = motionComp.GetMotion() or (0.0, 0.0, 0.0)
            return motionComp.SetMotion(
                (
                    float(current[0]) + float(x),
                    float(current[1]) + float(y),
                    float(current[2]) + float(z),
                )
            )
        except Exception:
            return False

    def _route_charge_hit(self, entityId, state, targetId, pos, targetPos):
        damage = minotaur_logic.melee_damage(
            state.get("type") == MINOSHROOM_IDENTIFIER
        )
        accepted = self._hurt(targetId, damage, entityId)
        if accepted:
            pushX, pushZ = _normalized_xz(pos, targetPos)
            self._add_entity_motion(targetId, pushX, 0.35, pushZ)

    def _break_minoshroom_charge_blocks(self, entityId, state, pos):
        if not self._mob_griefing():
            return
        width, height = self._collision_size(entityId, (1.49, 2.9))
        radius = width * 0.5 + 0.75
        minimum = (
            int(math.floor(pos[0] - radius)),
            int(math.floor(pos[1])),
            int(math.floor(pos[2] - radius)),
        )
        maximum = (
            int(math.floor(pos[0] + radius)),
            int(math.floor(pos[1] + height + 0.15)),
            int(math.floor(pos[2] + radius)),
        )
        for x in range(minimum[0], maximum[0] + 1):
            for y in range(minimum[1], maximum[1] + 1):
                for z in range(minimum[2], maximum[2] + 1):
                    blockPos = (x, y, z)
                    blockName = self._block_name(
                        self._get_block(blockPos, state["dimensionId"])
                    )
                    if self._can_destroy(blockName):
                        self._set_block(
                            blockPos, "minecraft:air", state["dimensionId"]
                        )

    def _minoshroom_slam_impact(self, entityId, state, pos):
        for playerId in list(self._known_players):
            if self._get_dimension(playerId) != state["dimensionId"]:
                continue
            playerPos = self._get_foot_pos(playerId)
            if (
                playerPos is None
                or not minotaur_logic.in_ground_attack_bounds(pos, playerPos)
                or not self._is_landable_below(
                    playerPos, state["dimensionId"]
                )
            ):
                continue
            self._add_entity_motion(
                playerId,
                0.0,
                minotaur_logic.ground_attack_knockup(True),
                0.0,
            )
            self._hurt(
                playerId,
                minotaur_logic.ground_attack_damage(
                    minotaur_logic.MINOSHROOM_MELEE_DAMAGE, True
                ),
                entityId,
            )
        self.BroadcastToAllClient(
            "HydraRouteEffect",
            {
                "kind": "minoshroom_slam",
                "dimensionId": state["dimensionId"],
                "position": pos,
            },
        )

    def _drive_route_charge(self, entityId, state, pos):
        charge = state.get("charge")
        targetId = charge.get("target_id") if charge else None
        targetPos = self._route_attackable_player_position(
            targetId, state["dimensionId"]
        )
        if charge is None or targetPos is None:
            self._stop_route_charge(entityId, state)
            return
        destination = charge.get("destination")
        navigationDone = bool(charge.get("navigation_done"))
        if destination is not None and _distance_sq(pos, destination) <= 0.75 ** 2:
            navigationDone = True
        reachSq = 5.0 if state.get("type") == MINOSHROOM_IDENTIFIER else 2.56
        charge, actions = minotaur_logic.advance_charge(
            charge,
            navigation_done=navigationDone,
            target_in_range=_distance_sq(pos, targetPos) <= reachSq,
        )
        state["charge"] = charge
        self._look_along(
            entityId,
            destination[0] - pos[0],
            destination[2] - pos[2],
        )
        if actions["navigate"]:
            self._start_route_charge_navigation(entityId, state)
        if charge.get("phase") == "moving":
            self._start_route_charge_navigation(entityId, state)
            if state.get("type") == MINOSHROOM_IDENTIFIER:
                self._break_minoshroom_charge_blocks(entityId, state, pos)
        if actions["attack"]:
            self._route_charge_hit(
                entityId, state, targetId, pos, targetPos
            )
        if actions["clear_charging"]:
            self._stop_route_charge(entityId, state)

    def _drive_minoshroom_slam(self, entityId, state, pos):
        slam = state.get("slam")
        if slam is None:
            return
        targetId = slam.get("target_id")
        if self._route_attackable_player_position(
            targetId, state["dimensionId"]
        ) is None:
            self._stop_route_slam(entityId, state)
            return
        self._set_motion(entityId, 0.0, 0.0)
        slam, actions = minotaur_logic.advance_slam(slam)
        state["slam"] = slam
        if actions["impact"]:
            self._minoshroom_slam_impact(entityId, state, pos)
        if actions["clear_ground_attack"]:
            self._stop_route_slam(
                entityId, state, recover=bool(actions["impact"])
            )

    def _route_attackable_player_position(self, playerId, dimensionId):
        if playerId in (None, "", -1, "-1"):
            return None
        try:
            gameComp = CF.CreateGame(LEVEL_ID)
            if not minotaur_logic.can_target_player(
                gameComp.GetPlayerGameType(playerId),
                gameComp.IsEntityAlive(playerId),
                self._get_dimension(playerId) == dimensionId,
            ):
                return None
        except Exception:
            return None
        return self._get_foot_pos(playerId)

    def _nearest_route_attackable_player(self, pos, dimensionId, maxDistance):
        best = None
        bestDistance = float(maxDistance) * float(maxDistance)
        for playerId in list(self._known_players):
            playerPos = self._route_attackable_player_position(
                playerId, dimensionId
            )
            if playerPos is None:
                continue
            distance = _distance_sq(pos, playerPos)
            if distance < bestDistance:
                best = (playerId, playerPos)
                bestDistance = distance
        return best

    def _drive_route_melee(self, entityId, state, pos, targetId, targetPos):
        isMinoshroom = state.get("type") == MINOSHROOM_IDENTIFIER
        fallbackSize = (1.4, 2.8) if isMinoshroom else (0.7, 2.4)
        attackerWidth, unusedHeight = self._collision_size(
            entityId, fallbackSize
        )
        targetWidth, unusedTargetHeight = self._collision_size(
            targetId, (0.6, 1.8)
        )
        reachSq = minotaur_logic.melee_attack_reach_sq(
            attackerWidth, targetWidth
        )
        cooldown, shouldAttack = minotaur_logic.advance_melee(
            state.get("meleeCooldown", 0),
            has_target=True,
            target_in_range=_distance_sq(pos, targetPos) <= reachSq,
            special_active=bool(state.get("charge") or state.get("slam")),
        )
        state["meleeCooldown"] = cooldown
        if str(self._get_attack_target(entityId)) != str(targetId):
            self._set_attack_target(entityId, targetId)
        if shouldAttack:
            self._hurt(
                targetId,
                minotaur_logic.melee_damage(isMinoshroom),
                entityId,
            )

    def _drive_route_mobs(self):
        for entityId, state in list(self._route_mobs.items()):
            kind = state.get("type")
            if kind == MAZE_SLIME_IDENTIFIER:
                continue
            if kind not in (MINOTAUR_IDENTIFIER, MINOSHROOM_IDENTIFIER):
                continue
            if kind == MINOSHROOM_IDENTIFIER:
                self._tick_route_slam_recovery(entityId, state)
            pos = self._get_foot_pos(entityId)
            if pos is None:
                continue
            if kind == MINOSHROOM_IDENTIFIER and self._tick % 20 == 0:
                self._save_minoshroom_state(entityId, state)
            if (
                kind == MINOSHROOM_IDENTIFIER
                and minotaur_logic.outside_home(pos, state.get("home"))
            ):
                self._stop_route_slam(entityId, state)
                self._stop_route_charge(entityId, state)
                home = state.get("home")
                dx, dz = _normalized_xz(pos, home)
                self._set_motion(entityId, dx * 0.35, dz * 0.35)
                self._reset_attack_target(entityId)
                state["targetId"] = None
                continue
            if state.get("slam") is not None:
                self._drive_minoshroom_slam(entityId, state, pos)
                continue
            if kind == MINOSHROOM_IDENTIFIER:
                state["slamCooldown"] = max(
                    0, int(state.get("slamCooldown", 0)) - 1
                )
            if state.get("charge") is not None:
                self._drive_route_charge(entityId, state, pos)
                continue
            target = self._nearest_route_attackable_player(
                pos, state["dimensionId"], 24.0
            )
            if target is None:
                if state.get("targetId") is not None:
                    self._reset_attack_target(entityId)
                state["targetId"] = None
                state["meleeCooldown"], unusedAttack = (
                    minotaur_logic.advance_melee(
                        state.get("meleeCooldown", 0),
                        has_target=False,
                        target_in_range=False,
                        special_active=False,
                    )
                )
                continue
            targetId, targetPos = target
            state["targetId"] = targetId
            distanceSq = _distance_sq(pos, targetPos)
            onGround = self._is_landable_below(pos, state["dimensionId"])
            hasSight = self._beetle_can_see(
                pos, targetPos, state["dimensionId"]
            )
            if kind == MINOSHROOM_IDENTIFIER and minotaur_logic.can_start_slam(
                distanceSq,
                onGround,
                hasSight,
                random.randrange(
                    minotaur_logic.SLAM_VISIBLE_FREQUENCY
                    if hasSight
                    else minotaur_logic.SLAM_HIDDEN_FREQUENCY
                ),
                state.get("slamCooldown", 0),
            ):
                self._stop_route_charge(entityId, state)
                state["slam"] = minotaur_logic.start_slam(
                    random.randrange(200), random.randrange(30), targetId
                )
                self._set_entity_property(
                    entityId,
                    "tf_slice:slam_duration",
                    max(
                        1,
                        min(
                            59,
                            int(state["slam"].get("ticks_remaining", 30)),
                        ),
                    ),
                )
                self._reset_attack_target(entityId)
                self._trigger_entity_event(
                    entityId, "tf_slice:start_ground_attack"
                )
                continue
            if minotaur_logic.can_start_charge(
                distanceSq,
                kind == MINOSHROOM_IDENTIFIER,
                onGround,
                hasSight,
                random.randrange(minotaur_logic.CHARGE_FREQUENCY),
            ):
                destination = minotaur_logic.charge_destination(pos, targetPos)
                state["charge"] = minotaur_logic.start_charge(
                    random.randrange(30), destination, targetId
                )
                state["charge"]["navigation_token"] = "%s:%s" % (
                    entityId, self._tick
                )
                self._reset_attack_target(entityId)
                self._trigger_entity_event(entityId, "tf_slice:start_charging")
                continue
            self._drive_route_melee(
                entityId, state, pos, targetId, targetPos
            )

    def _active_boss_count(self):
        return sum(
            1 for state in self._bosses.values() if not state.get("dead")
        ) + sum(
            1
            for state in self._lich_bosses.values()
            if not state.get("dead")
        ) + sum(
            1 for state in self._hydras.values() if not state.get("dead")
        ) + sum(
            1
            for state in self._route_mobs.values()
            if state.get("type") == MINOSHROOM_IDENTIFIER
        ) + len(
            self._ruin_worldgen.active_knight_groups()
            if self._ruin_worldgen is not None else ()
        ) + sum(
            1 for state in self._ur_ghasts.values()
            if not state.get("rewardClaimed")
        )

    def _lich_key(self, entityId):
        return entity_registry_logic.matching_entity_key(
            self._lich_bosses,
            entityId,
        )

    def _lich_state(self, entityId):
        key = self._lich_key(entityId)
        if key is None:
            return None
        return self._lich_bosses.get(key)

    def _load_lich_state(self, entityId):
        try:
            extra = CF.CreateExtraData(entityId)
            value = extra.GetExtraData(LICH_STATE_EXTRA_KEY)
            if isinstance(value, dict):
                return lich_logic.restore_persistent_state(value)
        except Exception:
            pass
        return None

    def _save_lich_state(self, entityId, state):
        if entityId is None or state is None:
            return False
        try:
            extra = CF.CreateExtraData(entityId)
            extra.SetExtraData(
                LICH_STATE_EXTRA_KEY,
                lich_logic.serialize_persistent_state(state),
                False,
            )
            saved = extra.SaveExtraData()
            state["lastPersistentTick"] = self._tick
            return saved
        except Exception as error:
            print "[TwilightBossSlice] Lich state save failed:", error
            return False

    def _load_lich_dependent_state(self, entityId):
        try:
            value = CF.CreateExtraData(entityId).GetExtraData(
                LICH_DEPENDENT_EXTRA_KEY
            )
            return value if isinstance(value, dict) else None
        except Exception:
            return None

    def _save_lich_dependent_state(self, entityId, kind, state):
        if entityId is None or state is None:
            return False
        value = {
            "kind": str(kind),
            "ownerId": state.get("ownerId"),
            "attackCooldown": int(state.get("attackCooldown", 0)),
            "nextAttackType": int(state.get("nextAttackType", 0)),
        }
        try:
            extra = CF.CreateExtraData(entityId)
            extra.SetExtraData(LICH_DEPENDENT_EXTRA_KEY, value, False)
            return extra.SaveExtraData()
        except Exception:
            return False

    def _sync_lich_presentation(self, entityId, state, force=False):
        """Mirror authoritative phase state into Bedrock visual properties."""
        if state.get("dying") or state.get("dead"):
            self._stop_lich_death_combat(entityId, state, force)
            return
        shieldStrength = max(
            0, min(lich_logic.INITIAL_SHIELDS,
                   int(state.get("shieldStrength", 0)))
        )
        if (
            force
            or int(state.get("visualShieldStrength", -1))
            != shieldStrength
        ):
            self._trigger_entity_event(
                entityId, "tf_slice:set_shield_%d" % shieldStrength
            )
            state["visualShieldStrength"] = shieldStrength

        phase = lich_logic.refresh_phase(state)
        if force or int(state.get("visualPhase", 0)) != int(phase):
            self._trigger_entity_event(
                entityId,
                (
                    "tf_slice:set_phase_melee"
                    if phase == lich_logic.PHASE_MELEE
                    else "tf_slice:set_phase_ranged"
                ),
            )
            state["visualPhase"] = int(phase)
        if state.get("castKind"):
            weaponName = "tf_slice:lifedrain_scepter"
        elif phase == lich_logic.PHASE_SHADOW:
            weaponName = "tf_slice:twilight_scepter"
        elif phase == lich_logic.PHASE_MINION:
            weaponName = "tf_slice:zombie_scepter"
        else:
            weaponName = "minecraft:golden_sword"
        if force or state.get("visualWeapon") != weaponName:
            equipped = self._set_entity_carried_item(
                entityId,
                {
                    "newItemName": weaponName,
                    "newAuxValue": 0,
                    "count": 1,
                },
            )
            self._entry_trace(
                "lich.equipment", entityId=str(entityId), phase=phase,
                weapon=weaponName, result=equipped,
                shields=shieldStrength,
                remaining=int(state.get("minionsRemaining", 0)),
                active=int(state.get("activeMinions", 0)),
            )
            if equipped is True:
                state["visualWeapon"] = weaponName
                state["goldSwordEquipped"] = phase == lich_logic.PHASE_MELEE

    def _register_lich(
        self, entityId, dimensionId, home, spawnerSpawned=False
    ):
        existing = self._lich_state(entityId)
        if existing is not None:
            existing["actorLoaded"] = True
            existing["missingActorTicks"] = 0
            return existing
        if self._active_boss_count() >= config.MAX_ACTIVE_BOSSES:
            return None
        logic_state = self._load_lich_state(entityId)
        restored = logic_state is not None
        if logic_state is None:
            logic_state = lich_logic.new_lich_state(spawnerSpawned)
        storedHome = logic_state.get("home")
        storedDimension = logic_state.get("dimensionId")
        resolvedHome = storedHome if storedHome is not None else home
        if resolvedHome is None:
            return None
        logic_state.update(
            {
                "dimensionId": int(
                    storedDimension
                    if storedDimension is not None
                    else dimensionId
                ),
                "home": tuple(resolvedHome),
                "targetId": logic_state.get("targetId"),
                "participants": set(logic_state.get("participants", set())),
                "cloneIds": set(),
                "minionIds": set(),
                "dead": bool(logic_state.get("dead", False)),
                "lootAwarded": bool(logic_state.get("lootAwarded", False)),
                "dying": bool(logic_state.get("dying", False)),
                "deathTime": max(0, int(logic_state.get("deathTime", 0))),
                "missingActorTicks": 0,
                "lastAttackerId": None,
                "lastPhase": int(logic_state.get("phase", 1)),
                "meleeNavTarget": None,
                "meleeNavTick": -20,
                "homeNavTick": -20,
                "candleScanIndex": None,
                "lastPersistentTick": self._tick,
                "relationRecoveryUntil": self._tick + (40 if restored else 0),
                "worldgenManaged": bool(
                    logic_state.get("worldgenManaged", False)
                ),
                "actorLoaded": True,
            }
        )
        self._lich_bosses[entityId] = logic_state
        self._set_health_cap(entityId, lich_logic.MAX_HEALTH)
        if restored:
            self._set_health(
                entityId,
                1.0 if logic_state.get("dying") else logic_state["health"],
            )
        self._sync_lich_presentation(entityId, logic_state, True)
        self._save_lich_state(entityId, logic_state)
        return logic_state

    def _spawn_courtyard_naga(self, identifier, pos, yaw, dimensionId):
        identifier = str(identifier)
        if identifier not in (config.BOSS_IDENTIFIER, LICH_IDENTIFIER):
            return self._spawn_ruin_entity(
                identifier,
                pos,
                yaw,
                dimensionId,
            )
        if (
            self._active_boss_count() >= config.MAX_ACTIVE_BOSSES
            or self._home_conflicts(pos, dimensionId)
            or self._pending_home_conflicts(pos, dimensionId)
            or self._pending_courtyard_home_conflicts(pos, dimensionId)
        ):
            return None
        pending = {
            "entityId": None,
            "identifier": identifier,
            "home": tuple(pos),
            "dimensionId": int(dimensionId),
            "stableTicks": 0,
            "expires": (
                self._tick
                + config.COURTYARD_BOSS_PENDING_TIMEOUT_TICKS
            ),
        }
        self._pending_courtyard_nagas.append(pending)
        try:
            bossId = self.CreateEngineEntityByTypeStr(
                identifier,
                tuple(pos),
                (0.0, float(yaw)),
                int(dimensionId),
                False,
                False,
            )
        except Exception as error:
            print "[TwilightBossSlice] landmark boss spawn failed:", error
            bossId = None
        if not bossId:
            if pending in self._pending_courtyard_nagas:
                self._pending_courtyard_nagas.remove(pending)
            return None
        pending["entityId"] = bossId
        return bossId

    def _confirm_courtyard_naga(self, entityId, expectedIdentifier):
        expectedIdentifier = str(expectedIdentifier)
        pending = self._pending_courtyard_naga(
            entityId,
            expectedIdentifier=expectedIdentifier,
        )
        if pending is None:
            return None
        if pending["expires"] < self._tick:
            self._pending_courtyard_nagas.remove(pending)
            self._remove_excess_boss(pending.get("entityId"))
            return None
        resolvedEntityId = pending.get("entityId")
        if resolvedEntityId is None:
            resolvedEntityId = entityId
        identifier = self._get_engine_type(resolvedEntityId)
        position = self._get_foot_pos(resolvedEntityId)
        dimensionId = self._get_dimension(resolvedEntityId)
        if (
            identifier != expectedIdentifier
            or position is None
            or dimensionId is None
            or int(dimensionId) != int(pending["dimensionId"])
        ):
            pending["stableTicks"] = 0
            return None
        pending["stableTicks"] = int(pending.get("stableTicks", 0)) + 1
        if (
            pending["stableTicks"]
            < config.COURTYARD_BOSS_STABLE_CONFIRM_TICKS
        ):
            return None
        if identifier == LICH_IDENTIFIER:
            state = self._register_lich(
                resolvedEntityId,
                pending["dimensionId"],
                pending["home"],
                spawnerSpawned=True,
            )
            if state is not None:
                state["worldgenManaged"] = True
                self._save_lich_state(resolvedEntityId, state)
        else:
            state = self._register_boss(
                resolvedEntityId,
                pending["dimensionId"],
                pending["home"],
            )
            if state is not None:
                state["worldgenManaged"] = True
                self._save_naga_state(resolvedEntityId, state)
        self._pending_courtyard_nagas.remove(pending)
        if state is None:
            self._remove_excess_boss(resolvedEntityId)
            return None
        if identifier == config.BOSS_IDENTIFIER:
            self._pending_naga_spawns = [
                spawn
                for spawn in self._pending_naga_spawns
                if not (
                    spawn["dimensionId"] == pending["dimensionId"]
                    and naga_logic.courtyards_overlap(
                        spawn["home"],
                        pending["home"],
                    )
                )
            ]
        return identifier

    def _destroy_segment(self, state, index):
        segmentId = state["segmentIds"][index]
        if segmentId is None:
            return (True, None)
        position = self._get_foot_pos(segmentId)
        try:
            result = self.DestroyEntity(segmentId)
        except Exception as exc:
            print "[TwilightBossSlice] Naga segment removal failed:", exc
            return (False, position)
        if result is False:
            print "[TwilightBossSlice] Naga segment removal returned false:", index
            return (False, position)
        self._segment_owners.pop(segmentId, None)
        if state["segmentIds"][index] == segmentId:
            state["segmentIds"][index] = None
        return (True, position)

    def _destroy_all_segments(self, state):
        for index in range(naga_logic.MAX_SEGMENTS):
            removed, _position = self._destroy_segment(state, index)
            if not removed:
                state["segmentBurstTicks"][index] = (
                    self._tick + config.SEGMENT_REMOVAL_RETRY_TICKS
                )
                continue
            state.get("segmentBurstTicks", {}).pop(index, None)

    def _mark_boss_dead(self, bossId, state):
        if state.get("dead"):
            return
        state["dead"] = True
        state["health"] = 0.0
        state["targetId"] = None
        state["waypoint"] = None
        state["bodyContactReadyTicks"].clear()
        self._schedule_segment_count(state, state["segments"], 0)
        state["segments"] = 0

    def _apply_boss_health_state(self, bossId, state, health):
        if state.get("dead") or state.get("dying"):
            return False
        try:
            health = max(
                0.0, min(float(health), float(state["maxHealth"]))
            )
        except (TypeError, ValueError):
            return False
        previousHealth = float(state.get("health", health))
        state["health"] = health
        if health <= 0.0:
            self._begin_naga_death(bossId, state)
            return False
        segments = naga_logic.segment_count(health, state["maxHealth"])
        if segments != state["segments"]:
            previousSegments = state["segments"]
            state["segments"] = segments
            self._schedule_segment_count(
                state, previousSegments, segments
            )
        if abs(previousHealth - health) > 0.0001:
            self._save_naga_state(bossId, state)
        return True

    def _schedule_segment_count(self, state, previousSegments, segments):
        if segments < previousSegments:
            for index, delay in naga_logic.segment_destruction_schedule(
                previousSegments, segments
            ):
                state["segmentBurstTicks"][index] = self._tick + delay
            return
        for index in range(segments):
            state["segmentBurstTicks"].pop(index, None)

    def _segment_is_in_wall(self, segmentPos, dimensionId):
        blockPos = (
            int(math.floor(float(segmentPos[0]))),
            int(math.floor(float(segmentPos[1]) + 1.0)),
            int(math.floor(float(segmentPos[2]))),
        )
        blockName = self._block_name(
            self._get_block(blockPos, dimensionId)
        )
        return naga_logic.is_segment_support_block(blockName)

    def _capture_naga_segment_pose(
        self, bossId, state, holdTicks=0
    ):
        headPos = self._get_foot_pos(bossId)
        if headPos is None:
            return False
        positions = []
        rotations = []
        for segmentId in state.get("segmentIds", ()):
            if segmentId is None:
                positions.append(None)
                rotations.append(None)
                continue
            positions.append(self._get_foot_pos(segmentId))
            rotations.append(self._get_rotation(segmentId))
        state["segmentPoseOffsets"] = naga_logic.segment_pose_offsets(
            headPos, positions
        )
        state["segmentPoseRotations"] = rotations
        state["segmentPoseUntilTick"] = (
            self._tick + max(0, int(holdTicks))
        )
        return any(offset is not None for offset in state["segmentPoseOffsets"])

    def _apply_naga_segment_pose(self, bossId, state):
        offsets = state.get("segmentPoseOffsets")
        if offsets is None:
            return False
        headPos = self._get_foot_pos(bossId)
        if headPos is None:
            return False
        positions = naga_logic.segment_pose_positions(headPos, offsets)
        rotations = state.get("segmentPoseRotations") or ()
        applied = False
        for index, segmentId in enumerate(state.get("segmentIds", ())):
            if segmentId is None or positions[index] is None:
                continue
            try:
                CF.CreatePos(segmentId).SetPos(positions[index])
                if index < len(rotations) and rotations[index] is not None:
                    CF.CreateRot(segmentId).SetRot(rotations[index])
                applied = True
            except Exception as exc:
                print "[TwilightBossSlice] Naga pose freeze failed:", exc
        return applied

    def _naga_segment_pose_is_held(self, state):
        return self._tick < int(state.get("segmentPoseUntilTick", 0))

    def _clear_naga_segment_pose(self, state):
        state["segmentPoseOffsets"] = None
        state["segmentPoseRotations"] = None
        state["segmentPoseUntilTick"] = 0

    def _ensure_segment_chain(self, bossId, state):
        leaderPos = self._get_foot_pos(bossId)
        if leaderPos is None:
            return
        _, leaderYaw = self._get_rotation(bossId)
        activeCount = int(state["segments"])
        if naga_logic.short_chain_should_hold(
            activeCount,
            state.get("lastSegmentHeadPos"),
            leaderPos,
            state["brain"].state,
        ):
            return
        state["lastSegmentHeadPos"] = tuple(leaderPos)
        burstTicks = state["segmentBurstTicks"]
        for index in range(naga_logic.MAX_SEGMENTS):
            shouldExist = index < activeCount or index in burstTicks
            segmentId = state["segmentIds"][index]
            if shouldExist and segmentId is None:
                spawnPos = naga_logic.segment_spawn_position(
                    leaderPos, leaderYaw
                )
                segmentId = self._spawn_segment(
                    bossId, state, index, spawnPos, leaderYaw
                )
            if segmentId is None:
                continue
            segmentPos = self._get_foot_pos(segmentId)
            if segmentPos is None:
                self._segment_owners.pop(segmentId, None)
                state["segmentIds"][index] = None
                continue
            destination, segmentYaw, segmentPitch = naga_logic.follow_segment(
                leader_pos=leaderPos,
                leader_yaw=leaderYaw,
                segment_pos=segmentPos,
                segment_index=index,
                on_ground=self._segment_is_in_wall(
                    segmentPos, state["dimensionId"]
                ),
                alive=state["health"] > 0.0,
            )
            try:
                CF.CreatePos(segmentId).SetPos(destination)
                CF.CreateRot(segmentId).SetRot(
                    (float(segmentPitch), float(segmentYaw))
                )
            except Exception as exc:
                print "[TwilightBossSlice] Naga segment move failed:", exc
            leaderPos = destination
            leaderYaw = segmentYaw

    def _update_boss_segments(self):
        finished = []
        for bossId, state in list(self._bosses.items()):
            burstPositions = []
            for index, burstTick in list(
                state["segmentBurstTicks"].items()
            ):
                if self._tick < burstTick:
                    continue
                removed, position = self._destroy_segment(state, index)
                if not removed:
                    state["segmentBurstTicks"][index] = (
                        self._tick + config.SEGMENT_REMOVAL_RETRY_TICKS
                    )
                    continue
                state["segmentBurstTicks"].pop(index, None)
                if position is not None:
                    burstPositions.append(position)
            self._broadcast_segment_bursts(
                bossId, state["dimensionId"], burstPositions
            )
            if state["health"] > 0.0:
                if self._naga_segment_pose_is_held(state):
                    if not self._apply_naga_segment_pose(bossId, state):
                        self._ensure_segment_chain(bossId, state)
                else:
                    self._clear_naga_segment_pose(state)
                    self._ensure_segment_chain(bossId, state)
                cindercoil_visuals.refresh_segments(
                    state["segmentIds"], state["segments"],
                    state.setdefault("cindercoilVisualRoles", {}),
                    self._trigger_entity_event,
                )
            elif (
                not state["segmentBurstTicks"]
                and not any(state["segmentIds"])
                and not state.get("dying")
            ):
                finished.append(bossId)
        for bossId in finished:
            self._bosses.pop(bossId, None)

    def _remove_excess_boss(self, entityId):
        if entityId is None:
            return
        try:
            self.DestroyEntity(entityId)
        except Exception as exc:
            print "[TwilightBossSlice] excess Naga removal failed:", exc

    def _ensure_boss_home(self, bossId, state):
        if state.get("home") is not None:
            return True
        home = self._get_foot_pos(bossId)
        if home is None:
            return False
        state["home"] = tuple(home)
        if state.get("dimensionId") is None:
            state["dimensionId"] = self._get_dimension(bossId)
        self._save_naga_state(bossId, state)
        print "[TwilightBossSlice] Naga home bound:", bossId, state["home"]
        return True

    def _get_attack_target(self, bossId):
        try:
            comp = CF.CreateAction(bossId)
            targetId = comp.GetAttackTarget()
            if not self._valid_entity_id(targetId):
                return None
            return targetId
        except Exception:
            return None

    def _set_attack_target(self, bossId, targetId):
        try:
            return CF.CreateAction(bossId).SetAttackTarget(targetId)
        except Exception as exc:
            print "[TwilightBossSlice] SetAttackTarget failed:", bossId, exc
            return False

    def _reset_attack_target(self, bossId):
        try:
            return CF.CreateAction(bossId).ResetAttackTarget()
        except Exception:
            return False

    def _set_motion(self, entityId, x, z):
        try:
            motionComp = CF.CreateActorMotion(entityId)
            current = motionComp.GetMotion()
            y = float(current[1]) if current else 0.0
            return motionComp.SetMotion((float(x), y, float(z)))
        except Exception as exc:
            print "[TwilightBossSlice] SetMotion failed:", entityId, exc
            return False

    def _set_full_motion(self, entityId, motion):
        if not self._valid_entity_id(entityId):
            return False
        try:
            return CF.CreateActorMotion(entityId).SetMotion(
                tuple(float(value) for value in motion)
            )
        except Exception:
            return False

    def _get_full_motion(self, entityId):
        if not self._valid_entity_id(entityId):
            return (0.0, 0.0, 0.0)
        try:
            motion = CF.CreateActorMotion(entityId).GetMotion()
            if motion is not None:
                return tuple(float(value) for value in motion)
        except Exception:
            pass
        return (0.0, 0.0, 0.0)

    def _set_player_motion(self, playerId, motion):
        try:
            motionComp = CF.CreateActorMotion(playerId)
            return motionComp.SetPlayerMotion(
                tuple(float(value) for value in motion)
            )
        except Exception as exc:
            print "[TwilightBossSlice] SetPlayerMotion failed:", playerId, exc
            return False

    def _face_position(self, entityId, origin, target):
        dx = float(target[0]) - float(origin[0])
        dy = float(target[1]) - float(origin[1])
        dz = float(target[2]) - float(origin[2])
        horizontal = math.sqrt(dx * dx + dz * dz)
        yaw = math.degrees(math.atan2(-dx, dz))
        pitch = -math.degrees(math.atan2(dy, max(0.001, horizontal)))
        try:
            return CF.CreateRot(entityId).SetRot((pitch, yaw))
        except Exception:
            return False

    def _face_yaw_position(self, entityId, origin, target):
        dx = float(target[0]) - float(origin[0])
        dz = float(target[2]) - float(origin[2])
        targetYaw = math.degrees(math.atan2(-dx, dz))
        try:
            return CF.CreateRot(entityId).SetRot((0.0, targetYaw))
        except Exception:
            return False

    def _separate_players_from_ur_ghast_head(
        self, bossId, state, bossPosition
    ):
        dimensionId = int(
            state.get("dimensionId", config.DIMENSION_ID)
        )
        separated = 0
        for playerId in self._get_online_players():
            if self._get_dimension(playerId) != dimensionId:
                continue
            playerPosition = self._get_foot_pos(playerId)
            destination = ur_ghast_logic.player_head_separation(
                bossPosition, playerPosition
            )
            if destination is None:
                continue
            try:
                if CF.CreatePos(playerId).SetPos(destination) is not False:
                    separated += 1
            except Exception:
                continue
        if separated:
            self._entry_trace(
                "ur_ghast.player_separation",
                bossId=str(bossId),
                count=int(separated),
                position=[
                    round(float(value), 3) for value in bossPosition
                ],
            )
        return separated

    def _beetle_can_see(self, origin, target, dimensionId):
        start = (origin[0], origin[1] + 0.35, origin[2])
        end = (target[0], target[1] + 0.8, target[2])
        for blockPos in quest_ram_logic.ray_samples(start, end):
            blockName = self._block_name(
                self._get_block(blockPos, dimensionId)
            )
            if blockName and blockName not in SIGHT_PASSABLE_BLOCKS:
                return False
        return True

    def _beetle_target_eye(self, targetId, targetPos):
        collisionHeight = self._collision_size(targetId, (0.6, 1.8))[1]
        return (
            float(targetPos[0]),
            float(targetPos[1])
            + beetle_combat_logic.fire_target_eye_height(
                collisionHeight, self._is_online_player(targetId)
            ),
            float(targetPos[2]),
        )

    def _beetle_target(self, entityId):
        targetId = self._get_attack_target(entityId)
        if targetId is None:
            return (None, None)
        return (targetId, self._get_foot_pos(targetId))

    def _set_entity_on_fire(self, entityId, seconds, burnDamage=1):
        try:
            return CF.CreateAttr(entityId).SetEntityOnFire(
                int(seconds), int(burnDamage)
            )
        except Exception:
            return False

    def _ride_passengers(self, entityId):
        try:
            raw = CF.CreateRide(entityId).GetRiders() or []
        except Exception:
            return []
        riders = []
        for item in raw:
            if isinstance(item, dict):
                riderId = item.get("entityId", item.get("riderId"))
            else:
                riderId = item
            if riderId is not None:
                riders.append(riderId)
        return riders

    def _release_rider(self, riderId):
        try:
            return CF.CreateRide(riderId).StopEntityRiding()
        except Exception:
            return False

    def _grab_pinch_target(self, entityId, targetId, dealDamage=True):
        self._release_rider(targetId)
        try:
            rideComp = CF.CreateRide(entityId)
            if not rideComp.SetRiderRideEntity(targetId, entityId, 0):
                return False
            try:
                rideComp.SetEntityLockRider(True)
            except Exception:
                pass
        except Exception:
            return False
        self._trigger_entity_event(entityId, "tf_slice:start_carrying")
        if dealDamage:
            self._hurt(targetId, 4.0, entityId)
        self._set_attack_target(entityId, targetId)
        return True

    def _play_world_sound(self, soundName, pos, volume=1.0, pitch=1.0):
        if pos is None:
            return False
        try:
            command = "/playsound %s @a %s %s %s %s %s" % (
                soundName,
                float(pos[0]),
                float(pos[1]),
                float(pos[2]),
                float(volume),
                float(pitch),
            )
            return CF.CreateCommand(LEVEL_ID).SetCommand(command)
        except Exception:
            return False

    def _entity_carried_item(self, entityId):
        try:
            itemPos = serverApi.GetMinecraftEnum().ItemPosType
            return CF.CreateItem(entityId).GetEntityItem(
                itemPos.CARRIED, 0, True
            )
        except Exception:
            return None

    def _set_entity_carried_item(self, entityId, item):
        try:
            itemPos = serverApi.GetMinecraftEnum().ItemPosType
            return CF.CreateItem(entityId).SetEntityItem(
                itemPos.CARRIED, item, 0
            )
        except Exception:
            return False

    def _spawn_swarm_companions(self, entityId, pos, dimensionId):
        """Reproduce SwarmSpider.finalizeSpawn's one-to-two companions."""
        if pos is None or dimensionId is None:
            return
        count = random.randint(1, 2)
        self._pending_swarm_children += count
        for index in range(count):
            offset = (
                float(pos[0]) + (-0.55 if index == 0 else 0.55),
                float(pos[1]),
                float(pos[2]) + (0.45 if index == 0 else -0.45),
            )
            try:
                childId = self.CreateEngineEntityByTypeStr(
                    "tf_slice:swarm_spider",
                    offset,
                    (0.0, random.uniform(0.0, 360.0)),
                    int(dimensionId),
                    False,
                    False,
                )
            except Exception:
                childId = None
            if not childId:
                self._pending_swarm_children = max(
                    0, self._pending_swarm_children - 1
                )

    def _maybe_spawn_spider_jockey(
        self, spiderId, spiderType, spiderPos, dimensionId
    ):
        """Use the source-specific King/Swarm Skeleton Druid rider rules."""
        difficulty = self._difficulty()
        if spiderPos is None or not spider_logic.druid_jockey_is_allowed(
            spiderType, difficulty, random.randrange(20)
        ):
            return None
        try:
            druidId = self.CreateEngineEntityByTypeStr(
                "tf_slice:skeleton_druid",
                tuple(spiderPos),
                (0.0, random.uniform(0.0, 360.0)),
                int(dimensionId),
                False,
                False,
            )
        except Exception:
            druidId = None
        if not druidId:
            return None
        if spider_logic.druid_jockey_is_baby(spiderType):
            self._trigger_entity_event(druidId, "tf_slice:make_baby")
        try:
            rideComp = CF.CreateRide(spiderId)
            if not rideComp.SetRiderRideEntity(
                druidId, spiderId, 0
            ):
                self.DestroyEntity(druidId)
                return None
            try:
                rideComp.SetEntityLockRider(True)
            except Exception:
                pass
        except Exception:
            try:
                self.DestroyEntity(druidId)
            except Exception:
                pass
            return None
        return druidId

    def _swarm_attack_is_allowed(self, sourceId):
        key = entity_registry_logic.matching_entity_key(
            self._ruin_mobs, sourceId
        )
        state = self._ruin_mobs.get(key) if key is not None else None
        if state is None:
            key = entity_registry_logic.matching_entity_key(
                self._phantom_urghast_mobs, sourceId
            )
            state = (
                self._phantom_urghast_mobs.get(key)
                if key is not None else None
            )
        entityType = state.get("type") if state is not None else None
        return spider_logic.swarm_attack_is_allowed(
            entityType, random.randrange(4)
        )

    def _panic_nearby_kobolds(self, deadPos, dimensionId):
        """Kobolds flee for 40 ticks when a nearby flock member dies."""
        if deadPos is None:
            return
        for entityId, state in list(self._ruin_mobs.items()):
            if state.get("type") != "tf_slice:kobold":
                continue
            if state.get("dimensionId") != dimensionId:
                continue
            pos = self._get_foot_pos(entityId)
            if pos is None:
                continue
            if (
                abs(float(pos[0]) - float(deadPos[0])) <= 4.0
                and abs(float(pos[1]) - float(deadPos[1])) <= 2.0
                and abs(float(pos[2]) - float(deadPos[2])) <= 4.0
            ):
                self._trigger_entity_event(entityId, "tf_slice:panic")
                awayX = float(pos[0]) - float(deadPos[0])
                awayZ = float(pos[2]) - float(deadPos[2])
                length = math.sqrt(awayX * awayX + awayZ * awayZ)
                if length > 0.001:
                    self._set_motion(
                        entityId,
                        awayX / length * 0.28,
                        awayZ / length * 0.28,
                    )

    def _target_is_looking_at(self, targetId, mobPos):
        targetPos = self._get_foot_pos(targetId)
        if targetPos is None or mobPos is None:
            return False
        unusedPitch, yaw = self._get_rotation(targetId)
        radians = math.radians(float(yaw))
        lookX = -math.sin(radians)
        lookZ = math.cos(radians)
        toMobX = float(mobPos[0]) - float(targetPos[0])
        toMobZ = float(mobPos[2]) - float(targetPos[2])
        length = math.sqrt(toMobX * toMobX + toMobZ * toMobZ)
        if length < 0.001:
            return True
        return (
            lookX * toMobX / length + lookZ * toMobZ / length
        ) > 0.5

    def _redcap_tnt_blocks(self, pos, dimensionId):
        # One native region read, rather than thousands of GetBlockNew calls.
        # Include air so palette-local coordinates keep the requested origin.
        origin = tuple(int(math.floor(v)) - 8 for v in pos)
        end = tuple(v + 16 for v in origin)
        try:
            palette = CF.CreateBlock(LEVEL_ID).GetBlockPaletteBetweenPos(
                dimensionId, origin, end, False
            )
            return [tuple(origin[i] + p[i] for i in range(3))
                    for p in palette.GetLocalPosListOfBlocks("minecraft:tnt")]
        except Exception:
            # Unknown terrain is not evidence that planting is safe.
            return None

    def _redcap_player_hurt(self, state, attackerType, damage):
        if (state is not None
                and state.get("type") in ("tf_slice:redcap", "tf_slice:redcap_sapper")
                and attackerType == "minecraft:player" and damage > 0.0):
            # Java's 100 source ticks = five seconds = 150 NetEase Updates.
            state["redcapShyUntilTick"] = self._tick + 150

    def _redcap_lit_tnt(self, entityId, radius):
        pos = self._get_foot_pos(entityId)
        if pos is None:
            return None
        vertical = max(3, radius)
        start = (int(math.floor(pos[0] - radius - 0.45)),
                 int(math.floor(pos[1] - vertical)),
                 int(math.floor(pos[2] - radius - 0.45)))
        end = (int(math.ceil(pos[0] + radius + 0.45)),
               int(math.ceil(pos[1] + vertical + 1.4)),
               int(math.ceil(pos[2] + radius + 0.45)))
        try:
            # TNT is not a living mob. Scan actors, then check the engine
            # identifier, matching Java's PrimedTnt class query.
            entities = CF.CreateGame(LEVEL_ID).GetEntitiesInSquareArea(
                None, start, end, self._get_dimension(entityId)
            ) or []
            result = []
            for candidate in entities:
                if self._get_engine_type(candidate) != "minecraft:tnt":
                    continue
                p = self._get_foot_pos(candidate)
                if (p is not None and abs(p[0] - pos[0]) <= radius + 0.45
                        and abs(p[2] - pos[2]) <= radius + 0.45
                        and pos[1] - vertical <= p[1] <= pos[1] + vertical + 1.4):
                    result.append(candidate)
            return result
        except Exception:
            return None

    def _redcap_goal(self, entityId, state, goal):
        old = state.get("redcapGoal")
        if old == goal:
            return
        state["redcapNavGeneration"] = state.get("redcapNavGeneration", 0) + 1
        state["redcapDestination"] = None
        state["redcapNavRetryTick"] = 0
        if old in ("shy", "light", "evade"):
            self._cancel_move_to_path(entityId)
        self._trigger_entity_event(
            entityId, "tf_slice:redcap_special" if goal in ("shy", "light", "evade")
            else "tf_slice:redcap_normal"
        )
        state["redcapGoal"] = goal
        if goal != "light" and old == "light":
            state["redcapLightAfterTick"] = self._tick + 30
        if goal != "plant":
            item = "minecraft:flint_and_steel" if goal == "light" else (
                "tf_slice:ironwood_pickaxe" if state.get("type") == "tf_slice:redcap_sapper"
                else "minecraft:iron_pickaxe"
            )
            self._set_entity_carried_item(entityId, {"newItemName": item, "count": 1, "newAuxValue": 0})

    def _redcap_navigate(self, entityId, state, destination, speed=1.0):
        if self._tick < state.get("redcapNavRetryTick", 0):
            return
        active = state.get("redcapDestination")
        if (active is not None and _distance_sq(active, destination) < 1.0
                and state.get("redcapNavSpeed", 1.0) == speed):
            # Reissuing a live MoveTo interrupts it (SDK result 3). Wait for
            # completion; six seconds is only a lost-callback watchdog.
            if self._tick - state.get("redcapNavTick", 0) < 180:
                return
        generation = state.get("redcapNavGeneration", 0) + 1
        state["redcapNavGeneration"] = generation
        state["redcapDestination"] = destination
        state["redcapNavTick"] = self._tick
        state["redcapNavSpeed"] = speed

        def finished(unusedEntityId, result):
            if state.get("redcapNavGeneration") == generation:
                state["redcapDestination"] = None
                state["redcapNavResult"] = result
                state["redcapNavRetryTick"] = self._tick + (15 if result != 0 else 0)
                if result != 0 and state.get("redcapGoal") == "evade":
                    state["redcapEscapeAttempt"] = state.get("redcapEscapeAttempt", 0) + 1
                    print("[TwilightBossSlice][RedcapAI] escape path result=%s entity=%s" % (result, entityId))

        try:
            result = CF.CreateMoveTo(entityId).SetMoveSetting(destination, speed, 200, finished)
            if result is False:
                finished(entityId, -1)
        except Exception:
            finished(entityId, -1)

    def _redcap_escape_destination(self, pos, threats, dimensionId, attempt, sign):
        nearest = min(threats, key=lambda p: _distance_sq(pos, p))
        dx, dz = pos[0] - nearest[0], pos[2] - nearest[2]
        if abs(dx) + abs(dz) < 0.001:
            dx, dz = sign, 0.0
        angle = math.atan2(dz, dx)
        offsets = (0.0, 0.6, -0.6, 1.2, -1.2)
        offsets = offsets[attempt % len(offsets):] + offsets[:attempt % len(offsets)]
        # Java searches up to 16 horizontally / 7 vertically. Native MoveTo
        # still determines the traversable route; these checks reject unsafe
        # endpoints before issuing it (including another TNT's blast area).
        for distance in (8.0, 12.0, 16.0):
            for offset in offsets:
                x = pos[0] + math.cos(angle + offset) * distance
                z = pos[2] + math.sin(angle + offset) * distance
                for dy in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7):
                    feet = (int(math.floor(x)), int(math.floor(pos[1])) + dy, int(math.floor(z)))
                    destination = (feet[0] + 0.5, float(feet[1]), feet[2] + 0.5)
                    if min(_distance_sq(destination, p) for p in threats) <= 64.0:
                        continue
                    body = self._get_block(feet, dimensionId) or {}
                    if body.get("name") != "minecraft:air":
                        continue
                    head = self._get_block((feet[0], feet[1] + 1, feet[2]), dimensionId) or {}
                    ground = self._get_block((feet[0], feet[1] - 1, feet[2]), dimensionId) or {}
                    if head.get("name") != "minecraft:air":
                        continue
                    if ground.get("name", "") in ("", "minecraft:air", "minecraft:water", "minecraft:flowing_water",
                                                   "minecraft:lava", "minecraft:flowing_lava", "minecraft:fire",
                                                   "minecraft:cactus", "minecraft:magma", "minecraft:tnt"):
                        continue
                    return destination
        return None

    def _redcap_escape(self, entityId, state, pos, tntIds):
        threats = [self._get_foot_pos(eid) for eid in (tntIds or [])]
        threats = [p for p in threats if p is not None]
        if threats:
            state["redcapEscapeThreats"] = threats
        else:
            threats = state.get("redcapEscapeThreats", [])
        if not threats:
            return
        destination = state.get("redcapDestination")
        if destination is None:
            if self._tick < state.get("redcapNavRetryTick", 0):
                return
            destination = self._redcap_escape_destination(
                pos, threats, state.get("dimensionId"),
                state.get("redcapEscapeAttempt", 0), state.get("circleSign", 1.0)
            )
            if destination is None:
                state["redcapNavRetryTick"] = self._tick + 15
                if state.get("redcapEscapeIssue") != "no_safe_endpoint":
                    print("[TwilightBossSlice][RedcapAI] no safe escape endpoint entity=%s" % entityId)
                state["redcapEscapeIssue"] = "no_safe_endpoint"
                return
        state["redcapEscapeIssue"] = None
        speed = 2.0 if min(_distance_sq(pos, p) for p in threats) < 49.0 else 1.0
        self._redcap_navigate(entityId, state, destination, speed)

    def _redcap_ignite(self, entityId, state, blockPos):
        dimensionId = state.get("dimensionId")
        block = self._get_block(blockPos, dimensionId) or {}
        if block.get("name") != "minecraft:tnt":
            return False
        # Use the dimension-aware entity API; /summon from LEVEL_ID can target
        # the overworld even when the redcap is in the Twilight dimension.
        try:
            primedId = self.CreateEngineEntityByTypeStr(
                "minecraft:tnt", (blockPos[0] + 0.5, blockPos[1], blockPos[2] + 0.5),
                (0, 0), dimensionId,
            )
        except Exception:
            return False
        if primedId in (None, "", "-1", -1):
            return False
        if not self._set_block(blockPos, "minecraft:air", dimensionId):
            self.DestroyEntity(primedId)
            return False
        self._play_world_sound("random.fuse", blockPos, 1.0, 1.0)
        state["redcapLightAfterTick"] = self._tick + 30
        return True

    def _update_redcap(self, entityId, state, pos):
        targetId = self._get_attack_target(entityId)
        targetPos = self._get_foot_pos(targetId) if targetId is not None else None
        distanceSq = _distance_sq(pos, targetPos) if targetPos is not None else None
        watched = targetPos is not None and self._target_is_looking_at(targetId, pos)

        # AvoidAnyEntityGoal equivalent: take ownership and actually flee.
        closeLit = self._redcap_lit_tnt(entityId, 2)
        if closeLit:
            self._redcap_goal(entityId, state, "evade")
            state["redcapEvadeUntilTick"] = self._tick + 150
            self._redcap_escape(entityId, state, pos, self._redcap_lit_tnt(entityId, 8) or closeLit)
            return
        if state.get("redcapGoal") == "evade":
            nearbyLit = self._redcap_lit_tnt(entityId, 8)
            if nearbyLit or state.get("redcapDestination") is not None:
                self._redcap_escape(entityId, state, pos, nearbyLit)
                return
            if nearbyLit is None and self._tick < state.get("redcapEvadeUntilTick", 0):
                return
            self._redcap_goal(entityId, state, "normal")

        # Priority 2: a five-block circle destination, using native pathfinding.
        # Java lastHurtByPlayerTime suppresses shyness for five seconds.
        if (distanceSq is not None and 9.0 <= distanceSq <= 36.0 and watched
                and self._tick >= state.get("redcapShyUntilTick", 0)):
            self._redcap_goal(entityId, state, "shy")
            destination = state.get("redcapDestination")
            if destination is None:
                angle = math.atan2(pos[2] - targetPos[2], pos[0] - targetPos[0])
                angle += state.get("circleSign", 1.0)
                destination = (targetPos[0] + math.cos(angle) * 5.0,
                               pos[1], targetPos[2] + math.sin(angle) * 5.0)
            self._redcap_navigate(entityId, state, destination)
            # Native look_at_target owns head tracking; forcing SetRot here
            # fights the navigation/body controller and creates sideways snaps.
            return

        if not self._mob_griefing():
            self._redcap_goal(entityId, state, "normal")
            return

        # Priority 3: both variants seek TNT even without an attack target.
        blocks = self._redcap_tnt_blocks(pos, state.get("dimensionId"))
        if blocks and self._tick >= state.get("redcapLightAfterTick", 0):
            blockPos = min(blocks, key=lambda p: _distance_sq(pos, p))
            self._redcap_goal(entityId, state, "light")
            if _distance_sq(pos, blockPos) < 2.4 * 2.4:
                if self._redcap_ignite(entityId, state, blockPos):
                    self._redcap_goal(entityId, state, "evade")
                    state["redcapEscapeThreats"] = [(blockPos[0] + 0.5, blockPos[1], blockPos[2] + 0.5)]
                    state["redcapEvadeUntilTick"] = self._tick + 150
                    # The new TNT may not appear in the engine query until
                    # the next tick. Its known ignition position is enough.
                    self._redcap_escape(entityId, state, pos, [])
            else:
                self._redcap_navigate(entityId, state, tuple(float(v) for v in blockPos))
            return

        self._redcap_goal(entityId, state, "normal")
        # Priority 4: place an unlit block only in air, with no TNT within five
        # blocks and no primed TNT within eight. Failed writes cost no charge.
        nearbyLit = self._redcap_lit_tnt(entityId, 8)
        if (state.get("type") != "tf_slice:redcap_sapper" or state.get("tntLeft", 0) <= 0
                or distanceSq is None or distanceSq >= 25.0 or watched
                or blocks is None or nearbyLit is None or nearbyLit):
            return
        feet = tuple(int(math.floor(v)) for v in pos)
        if any(all(abs(p[i] - feet[i]) <= 5 for i in range(3)) for p in blocks):
            return
        block = self._get_block(feet, state.get("dimensionId")) or {}
        if block.get("name") != "minecraft:air":
            return
        if self._set_block(feet, "minecraft:tnt", state.get("dimensionId")):
            state["tntLeft"] -= 1
            state["redcapGoal"] = "plant"
            self._set_entity_carried_item(entityId, {"newItemName": "minecraft:tnt", "count": 1, "newAuxValue": 0})


    def _nearest_player(self, pos, dimensionId, maxDistance):
        best = None
        bestDistance = float(maxDistance) * float(maxDistance)
        for playerId in list(self._known_players):
            if self._get_dimension(playerId) != dimensionId:
                continue
            playerPos = self._get_foot_pos(playerId)
            if playerPos is None:
                continue
            distance = _distance_sq(pos, playerPos)
            if distance < bestDistance:
                best = (playerId, playerPos)
                bestDistance = distance
        return best

    def _update_kobold(self, entityId, state, pos):
        item = self._entity_carried_item(entityId) or {}
        itemName = item.get("itemName", item.get("newItemName", ""))
        if itemName == "minecraft:bread":
            self._reset_attack_target(entityId)
            nearest = self._nearest_player(
                pos, state.get("dimensionId"), 8.0
            )
            if nearest is not None:
                unusedPlayerId, playerPos = nearest
                dx = float(pos[0]) - float(playerPos[0])
                dz = float(pos[2]) - float(playerPos[2])
                length = math.sqrt(dx * dx + dz * dz)
                if length > 0.001:
                    self._set_motion(
                        entityId, dx / length * 0.18, dz / length * 0.18
                    )
            if state.get("breadEatTick") is None:
                difficulty = self._difficulty()
                baseTicks = {1: 400, 2: 200, 3: 100}.get(
                    difficulty, 200
                )
                state["breadEatTick"] = (
                    self._tick + baseTicks + random.randint(0, 599)
                )
            if self._tick % 20 == 0 and random.randrange(10) == 0:
                self._play_world_sound(
                    "tf_slice.kobold.munch", pos, 0.8, 1.0
                )
            if self._tick >= state["breadEatTick"]:
                remaining = max(0, int(item.get("count", 1)) - 1)
                if remaining:
                    item["count"] = remaining
                    self._set_entity_carried_item(entityId, item)
                else:
                    self._set_entity_carried_item(entityId, None)
                state["breadEatTick"] = None
            return

        state["breadEatTick"] = None
        if self._tick % 40 != 0:
            return
        flock = []
        for otherId, otherState in self._ruin_mobs.items():
            if otherState.get("type") != "tf_slice:kobold":
                continue
            if otherState.get("dimensionId") != state.get("dimensionId"):
                continue
            otherPos = self._get_foot_pos(otherId)
            if otherPos is None:
                continue
            if (
                abs(float(otherPos[1]) - float(pos[1])) <= 4.0
                and _distance_sq(pos, otherPos) <= 16.0 * 16.0
            ):
                flock.append(otherPos)
        if not flock or len(flock) > 5:
            return
        center = (
            sum(other[0] for other in flock) / float(len(flock)),
            sum(other[1] for other in flock) / float(len(flock)),
            sum(other[2] for other in flock) / float(len(flock)),
        )
        if _distance_sq(pos, center) < 25.0:
            return
        direction = _normalized_xz(pos, center)
        self._set_motion(entityId, direction[0] * 0.12, direction[1] * 0.12)

    def _freeze_rising_zombie(self, entityId, state):
        """Match RisingZombie.tick(): zero velocity and preserve spawn yaw."""
        try:
            CF.CreateActorMotion(entityId).SetMotion((0.0, 0.0, 0.0))
        except Exception:
            pass

        rotation = state.get("risingRotation")
        if rotation is None:
            try:
                rotation = CF.CreateRot(entityId).GetRot()
                if rotation is not None:
                    rotation = tuple(rotation)
                    state["risingRotation"] = rotation
            except Exception:
                rotation = None
        if rotation is not None:
            try:
                CF.CreateRot(entityId).SetRot(rotation)
            except Exception:
                pass

    def _stop_fire_breath(self, entityId, state):
        targetId = state.get("beetleTarget")
        state["beetlePhase"] = None
        state["beetleTarget"] = None
        state["breathAim"] = None
        state["fireNextCheckTick"] = (
            self._tick + beetle_combat_logic.FIRE_GOAL_CHECK_INTERVAL_TICKS
        )
        self._trigger_entity_event(entityId, "tf_slice:stop_breathing")
        if targetId is not None:
            self._set_attack_target(entityId, targetId)

    def _update_fire_beetle(self, entityId, state, pos):
        phase = state.get("beetlePhase")
        if phase == "breathing":
            targetId = state.get("beetleTarget")
            targetPos = self._get_foot_pos(targetId)
            aim = state.get("breathAim")
            elapsed = self._tick - int(state.get("phaseStartTick", self._tick))
            targetValid = (
                targetPos is not None
                and (
                    not self._is_online_player(targetId)
                    or not self._is_invulnerable_player(targetId)
                )
            )
            valid = (
                targetValid
                and aim is not None
                and _distance_sq(pos, targetPos)
                <= beetle_combat_logic.FIRE_RANGE_SQ
                and self._beetle_can_see(
                    pos, targetPos, state.get("dimensionId")
                )
                and elapsed < beetle_combat_logic.FIRE_DURATION_TICKS
            )
            if not valid:
                self._stop_fire_breath(entityId, state)
                return
            self._set_full_motion(entityId, (0.0, 0.0, 0.0))
            self._face_position(entityId, pos, aim)
            start = (pos[0], pos[1] + 0.25, pos[2])
            if beetle_combat_logic.fire_is_damaging(elapsed):
                targetCenter = self._beetle_target_eye(targetId, targetPos)
                if beetle_combat_logic.beam_hit(
                    start, aim, targetCenter
                ):
                    if self._hurt(
                        targetId,
                        beetle_combat_logic.FIRE_DAMAGE,
                        entityId,
                    ):
                        self._set_entity_on_fire(
                            targetId, beetle_combat_logic.FIRE_SECONDS
                        )
            points = beetle_combat_logic.fire_breath_visual_points(
                start,
                aim,
                (
                    random.uniform(0.0, 0.55),
                    random.uniform(0.55, 1.35),
                ),
            )
            self._broadcast_beetle_effect(
                state.get("dimensionId"), "fire_breath", points
            )
            self._play_world_sound(
                "mob.ghast.fireball",
                start,
                random.uniform(0.05, 0.5),
                random.uniform(0.25, 0.5),
            )
            return

        if not beetle_combat_logic.fire_goal_check_ready(
            self._tick, state.get("fireNextCheckTick", 0)
        ):
            return
        state["fireNextCheckTick"] = (
            self._tick + beetle_combat_logic.FIRE_GOAL_CHECK_INTERVAL_TICKS
        )
        targetId = state.get("lastHurtById")
        targetPos = self._get_foot_pos(targetId)
        targetValid = (
            targetPos is not None
            and (
                not self._is_online_player(targetId)
                or not self._is_invulnerable_player(targetId)
            )
        )
        if not targetValid:
            return
        visible = self._beetle_can_see(
            pos, targetPos, state.get("dimensionId")
        )
        if not beetle_combat_logic.fire_can_start(
            _distance_sq(pos, targetPos), visible, True, random.random()
        ):
            return
        state["beetlePhase"] = "breathing"
        state["beetleTarget"] = targetId
        state["phaseStartTick"] = self._tick
        state["breathAim"] = self._beetle_target_eye(
            targetId, targetPos
        )
        # Suspend movement goals through the component group, keeping the
        # combat target available when normal navigation resumes.
        self._trigger_entity_event(entityId, "tf_slice:start_breathing")

    def _drive_slime_projectiles(self):
        for projectileId in list(self._slime_projectiles):
            position = self._get_foot_pos(projectileId)
            if position is None:
                self._slime_projectiles.pop(projectileId, None)
                continue
            trail = []
            for unusedIndex in range(2):
                trail.append(
                    (
                        float(position[0])
                        + 0.5 * (random.random() - random.random()),
                        float(position[1])
                        + 0.5 * (random.random() - random.random()),
                        float(position[2])
                        + 0.5 * (random.random() - random.random()),
                    )
                )
            state = self._slime_projectiles.get(projectileId) or {}
            self._broadcast_beetle_effect(
                state.get("dimensionId"), "slime_trail", trail
            )

    def _start_pinch_charge_navigation(self, entityId, state, destination):
        generation = int(state.get("chargeNavGeneration", 0)) + 1
        state["chargeNavGeneration"] = generation
        state["chargeNavDone"] = False
        state["chargeNavResult"] = None

        def callback(_entityId, result, expectedGeneration=generation):
            if int(state.get("chargeNavGeneration", 0)) != expectedGeneration:
                return
            state["chargeNavDone"] = True
            try:
                state["chargeNavResult"] = int(result)
            except (TypeError, ValueError):
                state["chargeNavResult"] = result

        try:
            started = CF.CreateMoveTo(entityId).SetMoveSetting(
                tuple(float(value) for value in destination),
                beetle_combat_logic.PINCH_CHARGE_SPEED,
                config.NAVIGATION_MAX_ITERATIONS,
                callback,
            )
        except Exception as exc:
            print "[TwilightBossSlice] pinch charge navigation failed:", entityId, exc
            started = False
        if started is False:
            state["chargeNavDone"] = True
            state["chargeNavResult"] = -1
            return False
        return True

    def _stop_pinch_charge(self, entityId, state, restoreTarget=True):
        targetId = state.get("beetleTarget")
        state["chargeNavGeneration"] = int(
            state.get("chargeNavGeneration", 0)
        ) + 1
        state["chargeNavDone"] = True
        state["chargeNavResult"] = None
        state["beetlePhase"] = None
        state["beetleTarget"] = None
        state["chargeDestination"] = None
        self._trigger_entity_event(entityId, "tf_slice:stop_charging")
        self._set_full_motion(entityId, (0.0, 0.0, 0.0))
        if restoreTarget and targetId is not None:
            self._set_attack_target(entityId, targetId)

    def _update_pinch_beetle(self, entityId, state, pos):
        riders = self._ride_passengers(entityId)
        if riders:
            riderId = riders[0]
            if self._is_invulnerable_player(riderId):
                self._release_rider(riderId)
                self._trigger_entity_event(entityId, "tf_slice:stop_carrying")
                self._reset_attack_target(entityId)
            else:
                self._set_attack_target(entityId, riderId)
            return
        if state.get("carrying"):
            state["carrying"] = False
            self._trigger_entity_event(entityId, "tf_slice:stop_carrying")

        phase = state.get("beetlePhase")
        targetId = state.get("beetleTarget")
        targetPos = self._get_foot_pos(targetId)
        if phase == "windup":
            destination = state.get("chargeDestination")
            if targetPos is None or destination is None:
                self._stop_pinch_charge(entityId, state, False)
                return
            self._set_full_motion(entityId, (0.0, 0.0, 0.0))
            self._face_position(entityId, pos, destination)
            if self._tick < int(state.get("windupEndTick", self._tick)):
                return
            state["beetlePhase"] = "charging"
            state["chargeEndTick"] = self._tick + 80
            if not self._start_pinch_charge_navigation(
                entityId, state, destination
            ):
                self._stop_pinch_charge(entityId, state)
                return
            phase = "charging"

        if phase == "charging":
            destination = state.get("chargeDestination")
            if destination is None or targetPos is None:
                self._stop_pinch_charge(entityId, state, False)
                return
            if _distance_sq(
                pos, targetPos
            ) <= beetle_combat_logic.pinch_attack_reach_sq(1.2, 0.6):
                if self._grab_pinch_target(entityId, targetId):
                    state["carrying"] = True
                self._stop_pinch_charge(entityId, state, False)
            elif (
                self._tick >= int(state.get("chargeEndTick", self._tick))
                or not beetle_combat_logic.pinch_charge_should_continue(
                    0, state.get("chargeNavDone")
                )
            ):
                self._stop_pinch_charge(entityId, state)
            return

        targetId, targetPos = self._beetle_target(entityId)
        if targetPos is None:
            return
        try:
            motion = CF.CreateActorMotion(entityId).GetMotion() or (0, 0, 0)
            onGround = abs(float(motion[1])) < 0.08
        except Exception:
            onGround = True
        visible = self._beetle_can_see(
            pos, targetPos, state.get("dimensionId")
        )
        if not beetle_combat_logic.pinch_can_start(
            _distance_sq(pos, targetPos),
            onGround,
            visible,
            random.random(),
        ):
            return
        state["beetlePhase"] = "windup"
        state["beetleTarget"] = targetId
        state["phaseStartTick"] = self._tick
        state["chargeNavDone"] = False
        state["chargeNavResult"] = None
        state["chargeDestination"] = (
            beetle_combat_logic.pinch_charge_destination(pos, targetPos)
        )
        state["windupEndTick"] = (
            self._tick
            + beetle_combat_logic.pinch_windup_ticks(
                random.randrange(
                    beetle_combat_logic.PINCH_WINDUP_RANDOM_TICKS
                )
            )
        )
        self._trigger_entity_event(entityId, "tf_slice:start_charging")
        self._reset_attack_target(entityId)

    def _update_ruin_mobs(self):
        for entityId, state in list(self._ruin_mobs.items()):
            pos = self._get_foot_pos(entityId)
            if pos is None:
                self._ruin_mobs.pop(entityId, None)
                continue
            mobType = state.get("type")
            if mobType == "tf_slice:fire_beetle":
                self._update_fire_beetle(entityId, state, pos)
                continue
            if mobType == "tf_slice:pinch_beetle":
                self._update_pinch_beetle(entityId, state, pos)
                continue
            if self._tick % 4 != 0:
                continue
            if mobType in ("tf_slice:redcap", "tf_slice:redcap_sapper"):
                self._update_redcap(entityId, state, pos)
            elif mobType == "tf_slice:kobold":
                self._update_kobold(entityId, state, pos)
            elif mobType == "tf_slice:rising_zombie":
                self._freeze_rising_zombie(entityId, state)
            elif mobType == "tf_slice:hostile_wolf":
                targetId = self._get_attack_target(entityId)
                if targetId is not None and targetId != state.get("lastTarget"):
                    self._play_world_sound(
                        "tf_slice.hostile_wolf.target", pos, 1.0, 1.0
                    )
                state["lastTarget"] = targetId

    def _on_navigation_result(self, entityId, result, generation):
        state = self._boss_state(entityId)
        if state is None or state.get("navGeneration") != generation:
            return
        try:
            state["navResult"] = int(result)
        except (TypeError, ValueError):
            state["navResult"] = result
        state["navDestination"] = None

    def _navigate_to(self, entityId, state, destination, speed):
        destination = tuple(float(value) for value in destination)
        active = state.get("navDestination")
        if active is not None:
            sameDestination = _distance_sq(active, destination) <= 1.0
            stillFresh = (
                self._tick - int(state.get("navIssuedTick", 0))
                < config.NAVIGATION_REISSUE_TICKS
            )
            if sameDestination and stillFresh:
                return True
        generation = int(state.get("navGeneration", 0)) + 1
        state["navGeneration"] = generation
        state["navDestination"] = destination
        state["navIssuedTick"] = self._tick
        state["navResult"] = None

        def callback(callbackEntityId, result, expectedGeneration=generation):
            self._on_navigation_result(
                callbackEntityId, result, expectedGeneration
            )

        try:
            moveComp = CF.CreateMoveTo(entityId)
            moveComp.SetMoveSetting(
                destination,
                float(speed),
                config.NAVIGATION_MAX_ITERATIONS,
                callback,
            )
            return True
        except Exception as exc:
            state["navDestination"] = None
            state["navResult"] = -1
            print "[TwilightBossSlice] SetMoveSetting failed:", entityId, exc
            return False

    def _cancel_move_to_path(self, entityId):
        position = self._get_foot_pos(entityId)
        if position is None:
            return False

        def callback(_entityId, _result):
            return None

        try:
            moveComp = CF.CreateMoveTo(entityId)
            return moveComp.SetMoveSetting(
                tuple(float(value) for value in position),
                1.0,
                config.NAVIGATION_CANCEL_MAX_ITERATIONS,
                callback,
            )
        except Exception as exc:
            print "[TwilightBossSlice] navigation cancel failed:", entityId, exc
            return False

    def _stop_navigation(self, entityId, state):
        state["navGeneration"] = int(state.get("navGeneration", 0)) + 1
        state["navDestination"] = None
        state["navResult"] = None
        self._cancel_move_to_path(entityId)
        return self._set_motion(entityId, 0.0, 0.0)

    def _look_along(self, entityId, x, z):
        if abs(x) + abs(z) < 0.0001:
            return
        try:
            targetYaw = math.degrees(
                math.atan2(-float(x), float(z))
            )
            rotComp = CF.CreateRot(entityId)
            current = rotComp.GetRot() or (0.0, targetYaw)
            yaw = naga_logic.step_yaw(current[1], targetYaw)
            rotComp.SetRot((0.0, yaw))
        except Exception:
            pass

    def _apply_head_slither(
        self, entityId, state, forward, minimumForward=None
    ):
        brain = state["brain"]
        strafe = naga_logic.slither_strafe(
            self._tick, brain.state, state.get("headStrafe", 0.0)
        )
        state["headStrafe"] = strafe
        try:
            motionComp = CF.CreateActorMotion(entityId)
            current = motionComp.GetMotion() or (0.0, 0.0, 0.0)
            if minimumForward is None:
                minimumForward = 0.12 if brain.state in (
                    naga_logic.CHARGE,
                    naga_logic.STUNLESS_CHARGE,
                ) else 0.075
            return motionComp.SetMotion(
                naga_logic.slither_motion(
                    current,
                    forward,
                    strafe,
                    minimum_forward=minimumForward,
                    lateral_scale=0.085,
                )
            )
        except Exception as exc:
            print "[TwilightBossSlice] Naga slither motion failed:", exc
            return False

    def _drive_intimidate(self, entityId, state, forward):
        strafe = naga_logic.slither_strafe(
            self._tick,
            naga_logic.INTIMIDATE,
            state.get("headStrafe", 0.0),
        )
        state["headStrafe"] = strafe
        lateralX = -float(forward[1])
        lateralZ = float(forward[0])
        try:
            motionComp = CF.CreateActorMotion(entityId)
            current = motionComp.GetMotion() or (0.0, 0.0, 0.0)
            return motionComp.SetMotion(
                (
                    float(forward[0]) * 0.052 + lateralX * strafe * 0.085,
                    float(current[1]),
                    float(forward[1]) * 0.052 + lateralZ * strafe * 0.085,
                )
            )
        except Exception:
            return False

    def _target_is_valid(self, bossId, state, targetId):
        if targetId in (None, "", -1, "-1"):
            return False
        bossPos = self._get_foot_pos(bossId)
        targetPos = self._get_foot_pos(targetId)
        if bossPos is None or targetPos is None:
            return False
        try:
            if not CF.CreateGame(LEVEL_ID).IsEntityAlive(targetId):
                return False
        except Exception:
            pass
        if self._is_online_player(targetId):
            try:
                gameType = int(
                    CF.CreateGame(LEVEL_ID).GetPlayerGameType(targetId)
                )
                if gameType in (1, 3, 6):
                    return False
            except Exception:
                pass
        if self._get_dimension(targetId) != state["dimensionId"]:
            return False
        if state.get("home") is None:
            return False
        if not naga_logic.inside_home(targetPos, state["home"]):
            return False
        if _distance_sq(bossPos, targetPos) > 80.0 * 80.0:
            return False
        return True

    def _get_online_players(self):
        players = set(self._known_players)
        try:
            players.update(serverApi.GetPlayerList() or [])
        except Exception:
            pass
        self._known_players.update(players)
        return list(players)

    def _find_nearest_player(self, bossId, state, playerIds):
        bossPos = self._get_foot_pos(bossId)
        if bossPos is None:
            return None
        candidates = []
        gameComp = CF.CreateGame(LEVEL_ID)
        for playerId in playerIds:
            try:
                if not gameComp.IsEntityAlive(playerId):
                    continue
                if int(gameComp.GetPlayerGameType(playerId)) in (1, 3, 6):
                    continue
            except Exception:
                continue
            if self._get_dimension(playerId) != state["dimensionId"]:
                continue
            playerPos = self._get_foot_pos(playerId)
            if (
                playerPos is not None
                and state.get("home") is not None
                and naga_logic.inside_home(playerPos, state["home"])
            ):
                candidates.append((playerId, playerPos))
        return naga_logic.nearest_target(bossPos, candidates, 80.0)

    def _loaded_actors(self):
        try:
            actors = serverApi.GetEngineActor() or {}
        except Exception:
            actors = {}
        if isinstance(actors, dict):
            return list(actors.items())
        return [(entityId, {}) for entityId in actors]

    def _cleanup_orphan_segments(self, loadedActors):
        for entityId, actor in loadedActors:
            identifier = (
                actor.get("identifier")
                if isinstance(actor, dict)
                else None
            )
            if identifier is None:
                identifier = self._get_engine_type(entityId)
            if identifier != SEGMENT_IDENTIFIER:
                continue
            if entityId in self._segment_owners:
                continue
            try:
                self.DestroyEntity(entityId)
            except Exception as exc:
                print "[TwilightBossSlice] orphan segment cleanup failed:", exc

    def _forget_missing_bosses(self, loadedActors):
        loaded = dict(loadedActors)
        missing = []
        for bossId, state in list(self._bosses.items()):
            if state.get("dead"):
                continue
            loadedBossKey = entity_registry_logic.matching_entity_key(
                loaded,
                bossId,
            )
            if (
                loadedBossKey is not None
                and self._get_foot_pos(loadedBossKey) is not None
            ):
                state["missingActorTicks"] = 0
                state["actorLoaded"] = True
                continue
            if not self._boss_home_is_observed(state):
                if state.get("actorLoaded", True):
                    self._on_boss_actor_removed(self._bosses, bossId)
                    print (
                        "[TwilightBossSlice] detached unloaded Naga:",
                        bossId,
                    )
                state["missingActorTicks"] = 0
                continue
            state["missingActorTicks"] = int(
                state.get("missingActorTicks", 0)
            ) + config.BOSS_DISCOVERY_INTERVAL_TICKS
            if (
                state["missingActorTicks"]
                >= config.BOSS_MISSING_ACTOR_GRACE_TICKS
            ):
                missing.append((bossId, state))
        for bossId, state in missing:
            self._destroy_all_segments(state)
            self._bosses.pop(bossId, None)
            if self._ruin_worldgen is not None:
                self._ruin_worldgen.mark_naga_missing(
                    state.get("home"),
                    bossId,
                )
            print "[TwilightBossSlice] rearmed missing Naga:", bossId

    def _discover_bosses(self):
        if self._tick % config.BOSS_DISCOVERY_INTERVAL_TICKS != 0:
            return
        loadedActors = self._loaded_actors()
        self._forget_missing_bosses(loadedActors)
        for entityId, actor in loadedActors:
            identifier = (
                actor.get("identifier")
                if isinstance(actor, dict)
                else None
            )
            if identifier is None:
                identifier = self._get_engine_type(entityId)
            if identifier != config.BOSS_IDENTIFIER:
                continue
            if self._pending_courtyard_naga(entityId) is not None:
                continue
            if self._boss_state(entityId) is not None:
                continue
            state = self._register_boss(
                entityId, self._get_dimension(entityId)
            )
            if state is None:
                self._remove_excess_boss(entityId)
        self._cleanup_orphan_segments(loadedActors)

        players = self._get_online_players()
        if not players:
            return
        filters = {
            "any_of": [
                {
                    "test": "is_family",
                    "subject": "other",
                    "value": "tf_slice_boss",
                }
            ]
        }
        gameComp = CF.CreateGame(LEVEL_ID)
        for playerId in players:
            try:
                nearby = gameComp.GetEntitiesAround(
                    playerId, config.BOSS_DISCOVERY_RADIUS, filters
                )
            except Exception:
                nearby = []
            for entityId in nearby or []:
                if self._boss_state(entityId) is not None:
                    continue
                if self._get_engine_type(entityId) != config.BOSS_IDENTIFIER:
                    continue
                if self._pending_courtyard_naga(entityId) is not None:
                    continue
                state = self._register_boss(
                    entityId, self._get_dimension(entityId)
                )
                if state is None:
                    self._remove_excess_boss(entityId)

    def _select_attack_target(self, bossId, state, playerIds):
        previousTarget = state.get("targetId")
        if self._target_is_valid(bossId, state, previousTarget):
            return previousTarget
        nativeTarget = self._get_attack_target(bossId)
        if self._target_is_valid(bossId, state, nativeTarget):
            return nativeTarget
        targetId = self._find_nearest_player(bossId, state, playerIds)
        if targetId is not None:
            self._set_attack_target(bossId, targetId)
            return targetId
        if nativeTarget not in (None, "", -1, "-1"):
            self._reset_attack_target(bossId)
        return None

    def _recover_boss_below_home(self, bossId, state, bossPos):
        if (
            state.get("home") is None
            or self._tick % 20 != 0
            or not bossPos[1] < state["home"][1] - 5.0
        ):
            return bossPos
        try:
            CF.CreatePos(bossId).SetPos(state["home"])
            self._stop_navigation(bossId, state)
            return state["home"]
        except Exception as exc:
            print "[TwilightBossSlice] Naga home recovery failed:", exc
            return bossPos

    def _drive_home(self, bossId, state, bossPos):
        home = state.get("home")
        if home is None:
            self._stop_navigation(bossId, state)
            return
        if (
            _distance_sq(bossPos, home)
            <= config.WAYPOINT_REACHED_DISTANCE ** 2
        ):
            self._stop_navigation(bossId, state)
            if state.get("combatStarted"):
                self._reset_encounter(bossId, state)
            state["returningHome"] = False
            return
        directionX, directionZ = _normalized_xz(bossPos, home)
        self._navigate_to(
            bossId, state, home, config.NAVIGATION_SPEED
        )
        self._look_along(bossId, directionX, directionZ)

    def _drive_idle_patrol(self, bossId, state, bossPos):
        navigationResult = state.get("navResult")
        navigationComplete = naga_logic.navigation_succeeded(
            navigationResult
        )
        if naga_logic.navigation_failed(navigationResult):
            state["navResult"] = None
            state["idleWaypointIndex"] = (
                int(state.get("idleWaypointIndex", 0)) + 1
            ) % naga_logic.IDLE_PATROL_POINT_COUNT
            state["idlePauseUntilTick"] = (
                self._tick + naga_logic.IDLE_PATROL_PAUSE_TICKS
            )
            self._stop_navigation(bossId, state)
            return
        if navigationResult is not None:
            state["navResult"] = None
        (
            state["idleWaypointIndex"],
            state["idlePauseUntilTick"],
            destination,
            shouldStop,
        ) = naga_logic.idle_patrol_step(
            bossPos,
            state.get("home"),
            state.get("idleWaypointIndex", 0),
            self._tick,
            state.get("idlePauseUntilTick", 0),
            navigation_complete=navigationComplete,
        )
        if shouldStop:
            self._stop_navigation(bossId, state)
            return
        if destination is None:
            return
        direction = _normalized_xz(bossPos, destination)
        speed = naga_logic.scaled_navigation_speed(
            config.NAVIGATION_SPEED, state["segments"]
        )
        self._navigate_to(
            bossId,
            state,
            destination,
            speed,
        )
        self._look_along(bossId, direction[0], direction[1])
        self._apply_head_slither(bossId, state, direction)

    def _reset_encounter(self, bossId, state):
        state["bodyContactReadyTicks"].clear()
        rng = state["brain"].rng
        state["brain"] = naga_logic.NagaBrain(rng)
        state["targetId"] = None
        state["waypoint"] = None
        state["contactReadyTick"] = 0
        state["headStrafe"] = 0.0
        state["combatStarted"] = False
        state["idleWaypointIndex"] = 0
        state["idlePauseUntilTick"] = 0
        state["lastSegmentHeadPos"] = None
        self._clear_naga_segment_pose(state)
        state["noTargetTicks"] = 0
        state["waypointBestDistance"] = None
        state["stuckTicks"] = 0
        self._reset_attack_target(bossId)
        self._push_state_property(bossId, naga_logic.CIRCLE)

    def _on_state_changed(self, bossId, state, previousState):
        brain = state["brain"]
        if previousState == brain.state:
            return
        state["waypoint"] = None
        if brain.state == naga_logic.INTIMIDATE:
            state["difficulty"] = self._difficulty()
            state["stunless"] = naga_logic.choose_stunless(
                state["health"],
                state["maxHealth"],
                state["difficulty"],
                brain.rng,
            )
        elif brain.state == naga_logic.CIRCLE:
            state["stunless"] = False
        self._push_state_property(bossId, brain.state)
        if brain.state in (
            naga_logic.INTIMIDATE,
            naga_logic.DAZE,
            naga_logic.STUNLESS_CHARGE,
        ):
            self._broadcast_combat_effect(
                state["dimensionId"],
                self._get_foot_pos(bossId),
                (
                    "rattle"
                    if brain.state == naga_logic.INTIMIDATE
                    else brain.state
                ),
            )

    def _advance_timed_states(self):
        for bossId, state in self._bosses.items():
            targetId = state.get("targetId")
            if not self._target_is_valid(bossId, state, targetId):
                continue
            bossPos = self._get_foot_pos(bossId)
            targetPos = self._get_foot_pos(targetId)
            if bossPos is None or targetPos is None:
                continue
            brain = state["brain"]
            previous = brain.state
            targetAbove = naga_logic.target_is_above_naga(
                bossPos[1], targetPos[1]
            )
            brain.advance_timed_state(
                target_above=targetAbove,
                use_stunless=state.get("stunless", False),
            )
            self._on_state_changed(bossId, state, previous)

    def _make_waypoint(self, bossPos, targetPos, brain):
        if brain.state == naga_logic.CIRCLE:
            radius, rotation = brain.orbit_parameters()
            return naga_logic.circle_point(
                bossPos,
                targetPos,
                brain.clockwise,
                radius,
                rotation,
            )
        if brain.state in (
            naga_logic.CHARGE,
            naga_logic.STUNLESS_CHARGE,
        ):
            return naga_logic.circle_point(
                bossPos, targetPos, brain.clockwise, 5.0, math.pi
            )
        return None

    def _drive_path_state(self, bossId, state, bossPos, targetPos):
        brain = state["brain"]
        waypoint = state.get("waypoint")
        navigationResult = state.get("navResult")
        if navigationResult is not None:
            state["navResult"] = None
            if naga_logic.navigation_succeeded(navigationResult):
                previous = brain.state
                targetAbove = naga_logic.target_is_above_naga(
                    bossPos[1], targetPos[1]
                )
                brain.complete_path_step(
                    target_above=targetAbove,
                    use_stunless=state.get("stunless", False),
                )
                state["waypoint"] = None
                state["waypointBestDistance"] = None
                state["stuckTicks"] = 0
                self._on_state_changed(bossId, state, previous)
                self._stop_navigation(bossId, state)
                return
            if naga_logic.navigation_failed(navigationResult):
                state["stuckTicks"] = int(
                    state.get("stuckTicks", 0)
                ) + config.NAVIGATION_REISSUE_TICKS

        if waypoint is not None:
            (
                state["waypointBestDistance"],
                state["stuckTicks"],
            ) = naga_logic.update_navigation_progress(
                state.get("waypointBestDistance"),
                _distance_xz(bossPos, waypoint),
                state.get("stuckTicks", 0),
                config.AI_INTERVAL_TICKS,
                config.NAVIGATION_MIN_PROGRESS,
            )
        if (
            waypoint is not None
            and state["stuckTicks"] >= config.NAVIGATION_STUCK_TICKS
        ):
            direction = _normalized_xz(bossPos, waypoint)
            self._clear_head_volume(
                state,
                bossPos,
                outsideHome=not naga_logic.inside_home(
                    bossPos, state["home"]
                ),
            )
            state["waypoint"] = None
            lateralSign = (
                -1.0
                if int(state.get("navGeneration", 0)) % 2
                else 1.0
            )
            waypoint = (
                float(bossPos[0])
                + direction[0] * 4.0
                - direction[1] * lateralSign * 2.0,
                float(bossPos[1]),
                float(bossPos[2])
                + direction[1] * 4.0
                + direction[0] * lateralSign * 2.0,
            )
            state["waypoint"] = waypoint
            state["navDestination"] = None
            state["navGeneration"] += 1
            state["waypointBestDistance"] = _distance_xz(
                bossPos, waypoint
            )
            state["stuckTicks"] = 0
        if waypoint is None:
            waypoint = self._make_waypoint(bossPos, targetPos, brain)
            state["waypoint"] = waypoint
            state["waypointBestDistance"] = (
                _distance_xz(bossPos, waypoint)
                if waypoint is not None
                else None
            )
            state["stuckTicks"] = 0
        if waypoint is None:
            self._stop_navigation(bossId, state)
            return
        if naga_logic.combat_waypoint_reached(
            _distance_xz(bossPos, waypoint)
        ):
            previous = brain.state
            targetAbove = naga_logic.target_is_above_naga(
                bossPos[1], targetPos[1]
            )
            brain.complete_path_step(
                target_above=targetAbove,
                use_stunless=state.get("stunless", False),
            )
            state["waypoint"] = None
            state["waypointBestDistance"] = None
            self._on_state_changed(bossId, state, previous)
            self._stop_navigation(bossId, state)
            return
        directionX, directionZ = _normalized_xz(bossPos, waypoint)
        speed = config.NAVIGATION_SPEED
        if brain.state in (
            naga_logic.CHARGE,
            naga_logic.STUNLESS_CHARGE,
        ):
            speed = config.NAVIGATION_CHARGE_SPEED
        speed = naga_logic.scaled_navigation_speed(
            speed, state["segments"]
        )
        self._navigate_to(bossId, state, waypoint, speed)
        if brain.state not in (
            naga_logic.CHARGE,
            naga_logic.STUNLESS_CHARGE,
        ):
            self._apply_head_slither(
                bossId, state, (directionX, directionZ)
            )
        self._look_along(bossId, directionX, directionZ)

    def _can_destroy(self, blockName):
        if not blockName or blockName in PROTECTED_BLOCKS:
            return False
        if "portal" in blockName or "command_block" in blockName:
            return False
        return True

    def _destroy_block(
        self,
        dimensionId,
        pos,
        brainState,
        outsideHome=False,
        knownBlockName=None,
        mobGriefing=None,
        targetedCrumble=False,
    ):
        if mobGriefing is None:
            mobGriefing = self._mob_griefing()
        try:
            comp = CF.CreateBlockInfo(LEVEL_ID)
            blockName = knownBlockName
            if blockName is None:
                block = comp.GetBlockNew(pos, dimensionId)
                blockName = block.get("name") if block else None
            protected = not self._can_destroy(blockName)
            if not naga_logic.should_destroy_block(
                blockName,
                brainState,
                mobGriefing,
                outside_home=outsideHome,
                protected=protected,
                targeted_crumble=targetedCrumble,
            ):
                return False
            oldBlockHandling = 0 if "leaves" in str(blockName).lower() else 1
            return comp.SetBlockNew(
                pos,
                {"name": "minecraft:air", "aux": 0},
                oldBlockHandling,
                dimensionId,
                True,
                False,
            )
        except Exception:
            return False

    def _crumble_below_target(self, state, bossPos, targetPos):
        rng = state["brain"].rng
        floorY = int(bossPos[1])
        targetY = int(targetPos[1])
        if targetY <= floorY:
            return
        for radius in (2, 3):
            x = int(targetPos[0]) + rng.randint(0, radius - 1)
            x -= rng.randint(0, radius - 1)
            z = int(targetPos[2]) + rng.randint(0, radius - 1)
            z -= rng.randint(0, radius - 1)
            y = targetY - rng.randint(0, radius - 1)
            y += rng.randint(0, radius - 2 if radius > 1 else radius - 1)
            if y <= floorY:
                y = targetY
            self._destroy_block(
                state["dimensionId"],
                (x, y, z),
                state["brain"].state,
                targetedCrumble=True,
            )

    def _clear_head_volume(self, state, bossPos, outsideHome=False):
        mobGriefing = self._mob_griefing()
        if not mobGriefing:
            return
        destroyAll = bool(
            outsideHome
            or state["brain"].state
            in (naga_logic.CHARGE, naga_logic.STUNLESS_CHARGE)
        )
        destroyState = (
            state["brain"].state if destroyAll else naga_logic.CIRCLE
        )
        positions = naga_logic.head_clear_positions(
            bossPos,
            destroy_all=destroyAll,
            max_blocks=config.MAX_BLOCKS_PER_CLEAR,
        )
        for pos in positions:
            self._destroy_block(
                state["dimensionId"],
                pos,
                destroyState,
                outsideHome=outsideHome,
                mobGriefing=mobGriefing,
            )

    def _drive_bosses(self):
        playerIds = self._get_online_players()
        for bossId, state in self._bosses.items():
            if state.get("dead"):
                continue
            if state.get("dying"):
                self._update_naga_death(bossId, state)
                continue
            health = self._get_health(bossId, state["health"])
            if not self._apply_boss_health_state(bossId, state, health):
                continue
            if not self._ensure_boss_home(bossId, state):
                self._stop_navigation(bossId, state)
                continue
            bossPos = self._get_foot_pos(bossId)
            if bossPos is None:
                continue
            bossPos = self._recover_boss_below_home(
                bossId, state, bossPos
            )
            state["ticksSinceDamaged"] += config.AI_INTERVAL_TICKS
            heal = naga_logic.heal_amount(state["ticksSinceDamaged"])
            if heal > 0.0 and health < state["maxHealth"]:
                health = min(state["maxHealth"], health + heal)
                self._set_health(bossId, health)
                self._apply_boss_health_state(bossId, state, health)
            outsideHome = not naga_logic.inside_home(
                bossPos, state["home"]
            )
            if self._tick % config.BLOCK_CLEAR_INTERVAL_TICKS == 0:
                self._clear_head_volume(
                    state,
                    bossPos,
                    outsideHome=outsideHome,
                )
            if outsideHome:
                state["targetId"] = None
                state["waypoint"] = None
                state["returningHome"] = True
                self._set_naga_idle_ai(bossId, state, False)
                self._drive_home(bossId, state, bossPos)
                continue
            state["returningHome"] = False
            targetId = self._select_attack_target(
                bossId, state, playerIds
            )
            state["targetId"] = targetId
            self._resolve_segment_collisions(bossId, state, targetId)
            if not self._target_is_valid(bossId, state, targetId):
                state["targetId"] = None
                state["waypoint"] = None
                if state.get("combatStarted"):
                    self._stop_navigation(bossId, state)
                    self._reset_encounter(bossId, state)
                self._set_naga_idle_ai(bossId, state, False)
                self._drive_idle_patrol(bossId, state, bossPos)
                continue
            self._set_naga_idle_ai(bossId, state, False)
            if not state.get("combatStarted"):
                self._stop_navigation(bossId, state)
                state["idleWaypointIndex"] = 0
                state["idlePauseUntilTick"] = 0
            state["combatStarted"] = True
            state["noTargetTicks"] = 0
            targetPos = self._get_foot_pos(targetId)
            if targetPos is None:
                continue
            brain = state["brain"]
            if brain.state in (
                naga_logic.CIRCLE,
                naga_logic.CHARGE,
                naga_logic.STUNLESS_CHARGE,
            ):
                self._drive_path_state(
                    bossId, state, bossPos, targetPos
                )
            else:
                if brain.state == naga_logic.DAZE:
                    if naga_logic.daze_recoil_finished(
                        self._tick,
                        state.get("dazeRecoilStopTick", 0),
                    ):
                        self._stop_navigation(bossId, state)
                        self._set_motion(bossId, 0.0, 0.0)
                else:
                    self._stop_navigation(bossId, state)
                    direction = _normalized_xz(bossPos, targetPos)
                    self._look_along(
                        bossId, direction[0], direction[1]
                    )
                    if brain.state == naga_logic.INTIMIDATE:
                        self._drive_intimidate(
                            bossId, state, direction
                        )
                    elif brain.state == naga_logic.CRUMBLE:
                        self._crumble_below_target(
                            state, bossPos, targetPos
                        )
            self._resolve_contact(bossId, state, targetId)

    def _is_blocking(self, playerId):
        if self._shield_cooldowns.get(playerId, 0) > self._tick:
            return False
        knightmetalShield = self._held_knightmetal_shield(playerId)
        playerKey = str(playerId)
        if knightmetalShield is not None:
            startedTick = self._knightmetal_shield_users.get(playerKey)
            if startedTick is None:
                return False
            return knight_route_logic.player_shield_blocks(
                True,
                self._tick - int(startedTick),
                True,
                "",
            )
        self._knightmetal_shield_users.pop(playerKey, None)
        try:
            return bool(CF.CreatePlayer(playerId).GetIsBlocking())
        except Exception:
            return False

    def _held_knightmetal_shield(self, playerId):
        try:
            itemComp = CF.CreateItem(playerId)
            itemPos = serverApi.GetMinecraftEnum().ItemPosType
            for posType in (itemPos.CARRIED, itemPos.OFFHAND):
                item = itemComp.GetPlayerItem(posType, 0, True) or {}
                if portal_logic.item_name(item) == "tf_slice:knightmetal_shield":
                    return (itemComp, posType, 0)
        except Exception:
            pass
        return None

    def _begin_knightmetal_shield_use(self, args):
        playerId = args.get("playerId", args.get("entityId"))
        item = args.get("itemDict") or args.get("item") or {}
        if (
            playerId is None
            or portal_logic.item_name(item) != "tf_slice:knightmetal_shield"
        ):
            return False
        self._knightmetal_shield_users[str(playerId)] = int(self._tick)
        return True

    def _knightmetal_attack_is_from_front(self, playerId, sourceId):
        playerPos = self._get_foot_pos(playerId)
        sourcePos = self._get_foot_pos(sourceId)
        if playerPos is None or sourcePos is None:
            return False
        yaw = math.radians(self._get_rotation(playerId)[1])
        dx = float(sourcePos[0]) - float(playerPos[0])
        dz = float(sourcePos[2]) - float(playerPos[2])
        length = math.sqrt(dx * dx + dz * dz) or 1.0
        return (
            (-math.sin(yaw)) * (dx / length)
            + math.cos(yaw) * (dz / length)
        ) >= 0.0

    def _try_block_knightmetal_damage(self, args, playerId, sourceId):
        heldShield = self._held_knightmetal_shield(playerId)
        startedTick = self._knightmetal_shield_users.get(str(playerId))
        if heldShield is None or startedTick is None:
            return False
        cause = str(args.get("cause", args.get("damageCause", "")))
        if not knight_route_logic.player_shield_blocks(
            True,
            self._tick - int(startedTick),
            self._knightmetal_attack_is_from_front(playerId, sourceId),
            cause,
        ):
            return False
        try:
            fromValue = float(args.get("from", args.get("fromValue", 0.0)))
            toValue = float(args.get("to", args.get("toValue", fromValue)))
        except (TypeError, ValueError):
            return False
        shieldDamage = max(1, int(math.floor(max(0.0, fromValue - toValue))) + 1)
        itemComp, posType, slot = heldShield
        try:
            durability = int(itemComp.GetItemDurability(posType, slot))
            itemComp.SetItemDurability(
                posType, slot, max(0, durability - shieldDamage)
            )
        except Exception:
            pass
        args["cancel"] = True
        self._set_health(playerId, fromValue)
        self._play_world_sound(
            "item.shield.block", self._get_foot_pos(playerId), 1.0, 1.0
        )
        return True

    def _shield_slot(self, playerId):
        try:
            itemComp = CF.CreateItem(playerId)
            itemPos = serverApi.GetMinecraftEnum().ItemPosType
            candidates = (
                (itemPos.CARRIED, 0),
                (itemPos.OFFHAND, 0),
                (itemPos.INVENTORY, -1),
            )
            for posType, slot in candidates:
                item = itemComp.GetPlayerItem(posType, slot, True)
                name = item.get("itemName", "") if item else ""
                if name == "minecraft:shield" or name.endswith("_shield"):
                    return (itemComp, posType, slot)
        except Exception:
            pass
        return None

    def _damage_shield(self, playerId, amount):
        shield = self._shield_slot(playerId)
        if shield is None:
            return False
        itemComp, posType, slot = shield
        try:
            durability = int(itemComp.GetItemDurability(posType, slot))
            return itemComp.SetItemDurability(
                posType, slot, max(0, durability - int(amount))
            )
        except Exception:
            return False

    def _stop_using_item(self, playerId):
        try:
            return CF.CreateItem(playerId).StopUsingItem() is not False
        except Exception:
            try:
                return CF.CreatePlayer(playerId).StopUsingItem() is not False
            except Exception:
                current = self._carried_item(playerId)
                return bool(
                    current
                    and self._set_carried_item(playerId, current) is not False
                )

    def _play_shield_break_sound(self, playerId):
        position = self._get_foot_pos(playerId)
        if position is None:
            return False
        return self._play_world_sound(
            "random.break", position, 1.0, 0.9
        )

    def _hurt(
        self, entityId, amount, attackerId, causeName="EntityAttack"
    ):
        try:
            causes = serverApi.GetMinecraftEnum().ActorDamageCause
            cause = getattr(causes, str(causeName), causes.EntityAttack)
            hurtComp = CF.CreateHurt(entityId)
            return hurtComp.Hurt(
                float(amount), cause, attackerId, None, False
            )
        except Exception as exc:
            print "[TwilightBossSlice] Hurt failed:", entityId, exc
            return False

    def _knockback(self, entityId, fromPos, power):
        targetPos = self._get_foot_pos(entityId)
        if targetPos is None:
            return
        x, z = _normalized_xz(fromPos, targetPos)
        try:
            CF.CreateAction(entityId).SetMobKnockback(
                x, z, float(power), 0.2, 0.45
            )
        except Exception:
            self._set_motion(entityId, x * power * 0.18, z * power * 0.18)

    def _collision_size(self, entityId, fallback):
        try:
            size = CF.CreateCollisionBox(entityId).GetSize()
            scale = CF.CreateScale(entityId).GetEntityScale()
            if scale is None:
                scale = 1.0
            return (
                max(0.0, float(size[0]) * float(scale)),
                max(0.0, float(size[1]) * float(scale)),
            )
        except Exception:
            return tuple(float(value) for value in fallback)

    def _naga_target_overlaps_body(self, bossId, state, targetId):
        targetPos = self._get_foot_pos(targetId)
        if targetPos is None:
            return False
        targetSize = self._collision_size(targetId, (0.6, 1.8))
        headPos = self._get_foot_pos(bossId)
        if (
            headPos is not None
            and naga_logic.collision_boxes_overlap(
                headPos, (2.0, 3.0), targetPos, targetSize
            )
        ):
            return True
        for segmentId in state.get("segmentIds", ()):
            if segmentId is None:
                continue
            segmentPos = self._get_foot_pos(segmentId)
            if (
                segmentPos is not None
                and naga_logic.collision_boxes_overlap(
                    segmentPos,
                    (2.0, 2.0),
                    targetPos,
                    targetSize,
                )
            ):
                return True
        return False

    def _separate_naga_shield_contact(
        self,
        bossId,
        state,
        targetId,
        chargeMotion=None,
    ):
        bossPos = self._get_foot_pos(bossId)
        targetPos = self._get_foot_pos(targetId)
        if bossPos is None or targetPos is None:
            return (0.0, 1.0)
        fallback = (0.0, 0.0)
        if chargeMotion is not None:
            try:
                fallback = (
                    float(chargeMotion[0]),
                    float(chargeMotion[2]),
                )
            except (TypeError, ValueError, IndexError):
                pass
        if abs(fallback[0]) + abs(fallback[1]) < 0.0001:
            yaw = math.radians(self._get_rotation(bossId)[1])
            fallback = (-math.sin(yaw), math.cos(yaw))
        direction = fallback
        for separation in (2.25, 3.75, 5.25):
            playerPos, direction = naga_logic.shield_separation_position(
                bossPos,
                targetPos,
                distance=separation,
                fallback_direction=fallback,
            )
            try:
                CF.CreatePos(targetId).SetPos(playerPos)
            except Exception:
                break
            if not self._naga_target_overlaps_body(
                bossId, state, targetId
            ):
                break
        return direction

    def _shield_charge_recoil(
        self, bossId, playerId, chargeMotion=None
    ):
        try:
            bossMotion = chargeMotion
            if bossMotion is None:
                bossMotion = CF.CreateActorMotion(bossId).GetMotion()
            if bossMotion is None:
                return False
            bossMotion = tuple(float(value) for value in bossMotion)
            targetMotion = (
                CF.CreateActorMotion(playerId).GetMotion()
                or (0.0, 0.0, 0.0)
            )
            playerMotion, nagaMotion = naga_logic.shield_recoil_motions(
                bossMotion, targetMotion
            )
            playerApplied = self._set_player_motion(playerId, playerMotion)
            nagaApplied = self._set_full_motion(bossId, nagaMotion)
            return playerApplied is not False and nagaApplied is not False
        except Exception:
            return False

    def _naga_melee_knockback(self, bossId, targetId):
        try:
            yaw = self._get_rotation(bossId)[1]
            pushX, pushZ = naga_logic.melee_push_vector(yaw)
            current = (
                CF.CreateActorMotion(targetId).GetMotion()
                or (0.0, 0.0, 0.0)
            )
            return self._set_full_motion(
                targetId,
                (
                    float(current[0]) + pushX,
                    float(current[1]) + 0.4,
                    float(current[2]) + pushZ,
                ),
            )
        except Exception:
            return False

    def _resolve_segment_collisions(self, bossId, state, targetId):
        if state["brain"].state == naga_logic.DAZE or state.get("dead"):
            return
        segmentPositions = []
        for segmentId in state.get("segmentIds", ()):
            if segmentId is None:
                continue
            segmentPos = self._get_foot_pos(segmentId)
            if segmentPos is None:
                continue
            segmentPositions.append(segmentPos)
        if not segmentPositions:
            return

        gameComp = CF.CreateGame(LEVEL_ID)
        livingFilters = {
            "any_of": [
                {
                    "test": "is_family",
                    "subject": "other",
                    "value": "mob",
                },
                {
                    "test": "is_family",
                    "subject": "other",
                    "value": "player",
                },
            ]
        }
        animalFilters = {
            "any_of": [
                {
                    "test": "is_family",
                    "subject": "other",
                    "value": "animal",
                }
            ]
        }
        try:
            livingEntities = gameComp.GetEntitiesAround(
                bossId,
                config.SEGMENT_COLLISION_SCAN_RADIUS,
                livingFilters,
            ) or []
            animals = set(
                gameComp.GetEntitiesAround(
                    bossId,
                    config.SEGMENT_COLLISION_SCAN_RADIUS,
                    animalFilters,
                ) or []
            )
        except Exception as exc:
            print "[TwilightBossSlice] Naga body collision scan failed:", exc
            return

        excluded = set(self._bosses.keys())
        excluded.update(self._segment_owners.keys())
        excluded.add(bossId)

        for entityId in livingEntities:
            if entityId in excluded:
                continue
            entityPos = self._get_foot_pos(entityId)
            if entityPos is None:
                continue
            entitySize = self._collision_size(entityId, (0.6, 1.8))
            contactPos = None
            for segmentPos in segmentPositions:
                if naga_logic.collision_boxes_overlap(
                    segmentPos,
                    (2.0, 2.0),
                    entityPos,
                    entitySize,
                ):
                    contactPos = segmentPos
                    break
            if contactPos is None:
                continue
            damage = naga_logic.segment_collision_damage(
                entityId in animals
            )
            if self._hurt(entityId, damage, bossId) is False:
                continue
            self._knockback(entityId, contactPos, 0.4)

    def _resolve_contact(self, bossId, state, targetId):
        if self._tick < state["contactReadyTick"]:
            return
        bossPos = self._get_foot_pos(bossId)
        targetPos = self._get_foot_pos(targetId)
        if bossPos is None or targetPos is None:
            return
        targetSize = self._collision_size(targetId, (0.6, 1.8))
        targetWidth = targetSize[0]
        if _distance_sq(bossPos, targetPos) > naga_logic.attack_reach_squared(
            2.0, targetWidth
        ):
            return
        brain = state["brain"]
        previous = brain.state
        charging = brain.state in (
            naga_logic.CHARGE,
            naga_logic.STUNLESS_CHARGE,
        )
        headContact = naga_logic.collision_boxes_overlap(
            bossPos,
            (2.0, 3.0),
            targetPos,
            targetSize,
        )
        if charging and not headContact:
            return
        chargeMotion = None
        if brain.state == naga_logic.CHARGE:
            try:
                chargeMotion = CF.CreateActorMotion(bossId).GetMotion()
            except Exception:
                pass
        state["difficulty"] = self._difficulty()
        result = brain.resolve_contact(
            self._is_blocking(targetId),
            naga_logic.head_damage_for_difficulty(state["difficulty"]),
        )
        if result["kind"] == "none":
            return
        state["contactReadyTick"] = (
            self._tick + config.CONTACT_COOLDOWN_TICKS
        )
        if result["shield_damage"]:
            self._damage_shield(targetId, result["shield_damage"])
        if result["shield_cooldown"]:
            self._shield_cooldowns[targetId] = (
                self._tick + result["shield_cooldown"]
            )
        if result["self_damage"] > 0.0:
            state["suppressDamageEvents"] += 1
            self._hurt(bossId, result["self_damage"], targetId)
        if result["target_damage"] > 0.0:
            self._hurt(targetId, result["target_damage"], bossId)
        if (
            previous in (
                naga_logic.CHARGE,
                naga_logic.STUNLESS_CHARGE,
            )
            and brain.state == naga_logic.CIRCLE
        ):
            self._stop_navigation(bossId, state)
            self._capture_naga_segment_pose(
                bossId,
                state,
                naga_logic.CHARGE_CONTACT_HOLD_TICKS,
            )
        if result["kind"] == "shield_daze":
            self._stop_navigation(bossId, state)
            self._capture_naga_segment_pose(
                bossId,
                state,
                naga_logic.DAZE_RECOIL_TICKS,
            )
            self._shield_charge_recoil(
                bossId, targetId, chargeMotion
            )
            state["dazeRecoilStopTick"] = (
                self._tick + naga_logic.DAZE_RECOIL_TICKS
            )
        elif result["knockback"] > 0.0:
            self._naga_melee_knockback(bossId, targetId)
        self._broadcast_combat_effect(
            state["dimensionId"],
            bossPos,
            result["kind"],
        )
        self._on_state_changed(bossId, state, previous)

    def _change_dimension(self, playerId, dimensionId, pos):
        try:
            self._entry_trace(
                "dimension.component.create.call",
                playerId=playerId,
            )
            component = CF.CreateDimension(playerId)
            self._entry_trace(
                "dimension.component.create.return",
                playerId=playerId,
                componentType=type(component).__name__,
            )
            self._entry_trace(
                "dimension.native_change.call",
                playerId=playerId,
                dimensionId=dimensionId,
                position=pos,
            )
            result = component.ChangePlayerDimension(
                dimensionId,
                pos,
            )
            self._entry_trace(
                "dimension.native_change.return",
                playerId=playerId,
                result=result,
            )
            return result
        except Exception as exc:
            self._entry_trace(
                "dimension.native_change.exception",
                playerId=playerId,
                error=repr(exc),
            )
            print "[TwilightBossSlice] dimension change failed:", exc
            return False

    def _queue_portal_background_preload(
        self,
        playerId,
        destinationExit,
    ):
        try:
            yaw = self._get_rotation(playerId)[1]
        except Exception:
            yaw = 0.0
        positions = portal_logic.background_preload_chunk_positions(
            destinationExit,
            view_yaw=yaw,
        )
        queue = getattr(
            self,
            "_portal_background_preload_queue",
            None,
        )
        if queue is None:
            queue = []
            self._portal_background_preload_queue = queue
        keys = getattr(
            self,
            "_portal_background_preload_keys",
            None,
        )
        if keys is None:
            keys = set()
            self._portal_background_preload_keys = keys
        added = 0
        for chunkPosition in positions:
            key = (
                config.DIMENSION_ID,
                int(chunkPosition[0]),
                int(chunkPosition[1]),
            )
            if key in keys:
                continue
            keys.add(key)
            queue.append(
                {
                    "key": key,
                    "playerId": playerId,
                    "dimensionId": config.DIMENSION_ID,
                    "chunkPosition": tuple(chunkPosition),
                }
            )
            added += 1
        if added:
            self._worldgen_perf_increment(
                "backgroundPreloadQueued",
                added,
            )
            self._entry_trace(
                "entry.background_preload.queued",
                playerId=playerId,
                chunkCount=added,
                chunkRadius=(
                    portal_logic.PORTAL_BACKGROUND_PRELOAD_CHUNK_RADIUS
                ),
                yaw=round(float(yaw), 3),
            )
        return added

    def _on_portal_background_chunk_ready(self, key, result=None):
        inflight = getattr(
            self,
            "_portal_background_preload_inflight",
            None,
        )
        if not isinstance(inflight, dict) or inflight.get("key") != key:
            return
        inflight.update({"done": True, "result": result is not False})

    def _complete_portal_background_preload(self, success):
        inflight = getattr(
            self,
            "_portal_background_preload_inflight",
            None,
        )
        if inflight is None:
            return
        keys = getattr(
            self,
            "_portal_background_preload_keys",
            set(),
        )
        keys.discard(inflight.get("key"))
        self._portal_background_preload_inflight = None
        self._worldgen_perf_increment(
            (
                "backgroundPreloadCompleted"
                if success
                else "backgroundPreloadFailed"
            )
        )

    def _process_portal_background_preloads(self):
        inflight = getattr(
            self,
            "_portal_background_preload_inflight",
            None,
        )
        if inflight is not None:
            if inflight.get("done"):
                self._complete_portal_background_preload(
                    bool(inflight.get("result"))
                )
            elif self._tick >= inflight.get(
                "deadlineTick",
                self._tick + 1,
            ):
                self._complete_portal_background_preload(False)
            else:
                return

        queue = getattr(
            self,
            "_portal_background_preload_queue",
            None,
        )
        if not queue:
            return
        item = queue.pop(0)
        dimensionId = item["dimensionId"]
        chunkX, chunkZ = item["chunkPosition"]
        chunkCenter = (chunkX * 16 + 8, 64, chunkZ * 16 + 8)
        checker = getattr(self._chunk_comp, "CheckChunkState", None)
        if callable(checker):
            try:
                if checker(dimensionId, chunkCenter):
                    getattr(
                        self,
                        "_portal_background_preload_keys",
                        set(),
                    ).discard(item["key"])
                    self._worldgen_perf_increment(
                        "backgroundPreloadSkipped"
                    )
                    return
            except Exception:
                pass
        worker = getattr(self._chunk_comp, "DoTaskOnChunkAsync", None)
        bounds = portal_logic.chunk_block_bounds(item["chunkPosition"])
        if not callable(worker) or bounds is None:
            getattr(
                self,
                "_portal_background_preload_keys",
                set(),
            ).discard(item["key"])
            self._worldgen_perf_increment("backgroundPreloadFailed")
            return
        item["done"] = False
        item["result"] = False
        item["deadlineTick"] = (
            self._tick + PORTAL_BACKGROUND_PRELOAD_TIMEOUT_TICKS
        )
        self._portal_background_preload_inflight = item
        key = item["key"]

        def onReady(result=None, expectedKey=key):
            self._on_portal_background_chunk_ready(
                expectedKey,
                result,
            )

        try:
            result = worker(
                dimensionId,
                bounds[0],
                bounds[1],
                onReady,
            )
        except Exception:
            result = False
        if result is False:
            self._complete_portal_background_preload(False)
            return
        self._worldgen_perf_increment("backgroundPreloadSubmitted")

    def _finish_portal_arrival(self, playerId, request):
        if self._pending_portal_entries.get(playerId) is not request:
            return False
        if self._get_dimension(playerId) != config.DIMENSION_ID:
            return False

        origin = request["destinationOrigin"]
        destinationSurface = self._portal_surface(
            origin, config.DIMENSION_ID
        )
        destinationExit = self._portal_exit(
            destinationSurface, config.DIMENSION_ID
        )
        if not destinationSurface or destinationExit is None:
            return False

        # A staged entry has already been moved to this verified exit. Login
        # recovery only needs to rebuild and link the return portal.

        self._store_return_point(
            playerId,
            request["returnPoint"],
            portal_origin=origin,
        )
        storedPoint = (
            self._return_point_for_player(playerId)
            or request["returnPoint"]
        )
        self._remember_portal_link(
            destinationSurface,
            config.DIMENSION_ID,
            storedPoint,
        )
        self._portal_cooldowns[playerId] = (
            self._tick + config.PORTAL_COOLDOWN_TICKS
        )
        self._release_staged_portal_hold(playerId, request)
        self._pending_portal_entries.pop(playerId, None)
        self._release_portal_area(request)
        self._queue_portal_background_preload(
            playerId,
            destinationExit,
        )
        completedAt = self._portal_now_seconds()
        nativeStartedAt = request.get("nativeChangeStartedAt")
        nativeFinishedAt = request.get(
            "nativeChangeFinishedAt",
            completedAt,
        )
        nativeDimensionMs = None
        if nativeStartedAt is not None:
            nativeDimensionMs = round(
                max(
                    0.0,
                    float(nativeFinishedAt) - float(nativeStartedAt),
                )
                * 1000.0,
                3,
            )
        perfDelta = self._worldgen_perf_delta(
            request.get("worldgenPerfStart")
        )
        self._entry_trace(
            "entry.worldgen.summary",
            playerId=playerId,
            totalMs=round(
                max(
                    0.0,
                    completedAt
                    - float(request.get("entryStartedAt", completedAt)),
                )
                * 1000.0,
                3,
            ),
            nativeDimensionMs=nativeDimensionMs,
            counters=perfDelta["counters"],
            structures=perfDelta["structures"],
        )
        self.NotifyToClient(
            playerId,
            "PortalArrivalFinished",
            {"cancelled": False},
        )
        self._notify(
            playerId,
            u"\u5df2\u8fdb\u5165\u66ae\u8272\u7ef4\u5ea6\uff0c\u56de\u7a0b\u95e8\u5df2\u5728\u5bf9\u5e94\u4f4d\u70b9\u5efa\u597d\u3002",
        )
        print (
            "[TwilightBossSlice] portal arrival complete:",
            playerId,
            origin,
            storedPoint["dimensionId"],
            storedPoint["pos"],
        )
        return True

    def _process_portal_arrivals(self):
        for playerId, request in list(
            self._pending_portal_entries.items()
        ):
            currentDimension = self._get_dimension(playerId)
            if self._portal_request_expired(request):
                if (
                    currentDimension == config.DIMENSION_ID
                    and (
                        not request.get("recovery")
                        or request.get("stagedRelocationPending")
                        or request.get("clientReadyPending")
                    )
                ):
                    self._release_staged_portal_hold(playerId, request)
                    self._change_dimension(
                        playerId,
                        request["sourceDimensionId"],
                        portal_logic.player_position_from_foot(
                            request["returnPoint"]["pos"]
                        ),
                    )
                self._drop_portal_arrival(
                    playerId,
                    request,
                    u"\u5bf9\u5e94\u56de\u7a0b\u95e8\u51c6\u5907\u8d85\u65f6\uff0c\u8bf7\u91cd\u8bd5\u3002",
                )
                continue

            if request.get("state") == "changing_dimension":
                continue
            if (
                request.get("recovery")
                and currentDimension != config.DIMENSION_ID
            ):
                self._drop_portal_arrival(
                    playerId,
                    request,
                    u"\u5df2\u79bb\u5f00\u66ae\u8272\u7ef4\u5ea6\uff0c\u5df2\u53d6\u6d88\u8fd4\u7a0b\u95e8\u6062\u590d\u3002",
                )
                continue
            if (
                not request.get("recovery")
                and currentDimension != request["sourceDimensionId"]
            ):
                self._drop_portal_arrival(
                    playerId,
                    request,
                    u"\u4f20\u9001\u8d77\u70b9\u5df2\u6539\u53d8\uff0c\u5df2\u53d6\u6d88\u8fdb\u5165\u3002",
                )
                continue
            if (
                request.get("stagedRelocationPending")
                or request.get("clientReadyPending")
                or request.get("clientReady")
            ):
                self._hold_staged_portal_entry(playerId, request)
            if self._tick < request.get("nextAttemptTick", 0):
                continue
            if not request.get("recovery"):
                # Never touch target-dimension chunk/block components before
                # the engine has moved the player there. Even a read-only
                # CheckChunkState call can terminate the NetEase 3.8 native
                # process when a custom dimension has no LevelChunk yet.
                # ChangePlayerDimension must own first-chunk creation; all
                # readiness probes and portal writes happen only in recovery
                # after DimensionChangeFinish confirms arrival.
                self._bootstrap_portal_entry(playerId, request)
                continue
            if request.get("state") == "awaiting_engine_ready":
                if not request.get("clientEngineReady"):
                    if self._tick < request.get(
                        "clientEngineReadyFallbackTick",
                        self._tick + 1,
                    ):
                        continue
                    request["clientEngineReadyPending"] = False
                    request["clientEngineReady"] = True
                    request["clientEngineReadyFallback"] = True
                    request["nextAttemptTick"] = self._tick + 1
                    self._entry_trace(
                        "entry.direct.engine_ready.fallback_scheduled",
                        playerId=playerId,
                        position=request.get("preparedExit"),
                        relocateAtTick=request["nextAttemptTick"],
                    )
                    continue
                if not self._relocate_staged_portal_entry(
                    playerId,
                    request,
                    request.get("preparedExit"),
                ):
                    request["nextAttemptTick"] = (
                        self._tick + config.PORTAL_BUILD_RETRY_TICKS
                    )
                continue
            if request.get("state") == "client_loading":
                if not request.get("clientReady"):
                    if (
                        self._tick >= request.get(
                            "clientReadyDeadlineTick", self._tick + 1
                        )
                        and not request.get("clientReadyTimeoutLogged")
                    ):
                        request["clientReadyTimeoutLogged"] = True
                        self._entry_trace(
                            "entry.bootstrap.client_ready.timeout_release_scheduled",
                            playerId=playerId,
                            position=request.get("relocationFootPos"),
                            releaseAtTick=self._schedule_portal_client_release(
                                request,
                                fallback=True,
                            ),
                        )
                    # The server already verified the portal and its 3x3
                    # safety core before relocation. A missing client ACK must
                    # not turn that safety hold into a 60-second soft lock.
                    continue
                if self._tick < request.get(
                    "clientReadyReleaseTick", self._tick
                ):
                    continue
                if not self._finish_portal_arrival(playerId, request):
                    request["nextAttemptTick"] = (
                        self._tick + config.PORTAL_BUILD_RETRY_TICKS
                    )
                continue
            if request.get("state") == "staging_arrived":
                if not self._start_portal_area(request):
                    request["nextAttemptTick"] = (
                        self._tick + config.PORTAL_BUILD_RETRY_TICKS
                    )
                continue
            if not self._portal_target_chunks_ready(request):
                request["nextAttemptTick"] = (
                    self._tick + config.PORTAL_BUILD_RETRY_TICKS
                )
                continue
            if not request.get("serverSafeCoreReadyLogged"):
                request["serverSafeCoreReadyLogged"] = True
                self._entry_trace(
                    "entry.bootstrap.server_safe_core.ready",
                    playerId=playerId,
                    chunkRadius=portal_logic.PORTAL_SERVER_SAFE_CHUNK_RADIUS,
                    chunkCount=(
                        2 * portal_logic.PORTAL_SERVER_SAFE_CHUNK_RADIUS
                        + 1
                    )
                    ** 2,
                    backgroundPreloadRadius=(
                        portal_logic.PORTAL_BACKGROUND_PRELOAD_CHUNK_RADIUS
                    ),
                )

            destinationX, destinationZ = request["destinationXZ"]
            surfaceY = portal_logic.find_portal_surface_y(
                destinationX,
                destinationZ,
                lambda xz: self._get_top_block_height(
                    xz,
                    config.DIMENSION_ID,
                ),
                self._portal_block_getter(config.DIMENSION_ID),
            )
            if surfaceY is None:
                request["nextAttemptTick"] = (
                    self._tick + config.PORTAL_BUILD_RETRY_TICKS
                )
                continue
            destinationOrigin = portal_logic.paired_portal_origin(
                request["sourceSurface"],
                surfaceY,
            )
            request["destinationOrigin"] = destinationOrigin
            if not self._make_return_portal(
                destinationOrigin,
                config.DIMENSION_ID,
            ):
                request["nextAttemptTick"] = (
                    self._tick + config.PORTAL_BUILD_RETRY_TICKS
                )
                continue
            destinationSurface = self._portal_surface(
                destinationOrigin,
                config.DIMENSION_ID,
            )
            destinationExit = self._portal_exit(
                destinationSurface,
                config.DIMENSION_ID,
            )
            if not destinationSurface or destinationExit is None:
                request["nextAttemptTick"] = (
                    self._tick + config.PORTAL_BUILD_RETRY_TICKS
                )
                continue
            request["destinationSurface"] = tuple(destinationSurface)
            request["destinationExit"] = tuple(destinationExit)
            if request.get("stagedRelocationPending"):
                if request.get("directEntry"):
                    prepared = self._prepare_portal_client_relocation(
                        playerId,
                        request,
                        destinationExit,
                    )
                else:
                    prepared = self._relocate_staged_portal_entry(
                        playerId,
                        request,
                        destinationExit,
                    )
                if not prepared:
                    request["nextAttemptTick"] = (
                        self._tick + config.PORTAL_BUILD_RETRY_TICKS
                    )
                    continue
                continue
            if not self._finish_portal_arrival(playerId, request):
                request["nextAttemptTick"] = (
                    self._tick + config.PORTAL_BUILD_RETRY_TICKS
                )

    def _enter_slice(self, playerId, returnPoint=None, sourceSurface=None):
        self._entry_trace(
            "enter.begin",
            playerId=playerId,
            hasReturnPoint=returnPoint is not None,
            sourceSurface=sourceSurface,
        )
        self._entry_trace("enter.dimension.call", playerId=playerId)
        currentDimension = self._get_dimension(playerId)
        self._entry_trace(
            "enter.dimension.result",
            playerId=playerId,
            dimensionId=currentDimension,
        )
        self._entry_trace("enter.position.call", playerId=playerId)
        currentPos = self._get_foot_pos(playerId)
        self._entry_trace(
            "enter.position.result",
            playerId=playerId,
            position=currentPos,
        )
        if currentDimension == config.DIMENSION_ID:
            self._entry_trace(
                "enter.rejected",
                playerId=playerId,
                reason="already_in_twilight",
            )
            self._notify(playerId, u"\u4f60\u5df2\u5728\u66ae\u8272\u7ef4\u5ea6\u3002", "YELLOW")
            return
        if currentDimension is None or currentPos is None:
            self._entry_trace(
                "enter.rejected",
                playerId=playerId,
                reason="missing_source_state",
            )
            self._notify(playerId, u"\u65e0\u6cd5\u8bfb\u53d6\u5f53\u524d\u4f4d\u7f6e\u3002", "RED")
            return
        if playerId in self._pending_portal_entries:
            self._entry_trace(
                "enter.rejected",
                playerId=playerId,
                reason="already_pending",
            )
            return

        point = returnPoint or {
            "dimensionId": currentDimension,
            "pos": currentPos,
        }
        self._store_return_point(playerId, point)
        print (
            "[TwilightBossSlice] portal source captured:",
            playerId,
            point["dimensionId"],
            point["pos"],
        )
        if not sourceSurface:
            blockX = int(math.floor(currentPos[0]))
            blockY = int(math.floor(currentPos[1] - 1.0))
            blockZ = int(math.floor(currentPos[2]))
            sourceSurface = (
                (blockX, blockY, blockZ),
                (blockX + 1, blockY, blockZ),
                (blockX, blockY, blockZ + 1),
                (blockX + 1, blockY, blockZ + 1),
            )
        destinationXZ = (
            int(min(pos[0] for pos in sourceSurface)),
            int(min(pos[2] for pos in sourceSurface)),
        )
        entryStartedAt = self._portal_now_seconds()
        request = {
            "sourceDimensionId": currentDimension,
            "sourceSurface": tuple(sourceSurface),
            "returnPoint": copy.deepcopy(point),
            "destinationXZ": destinationXZ,
            "entryStartedAt": entryStartedAt,
            "worldgenPerfStart": self._worldgen_perf_snapshot(),
            "state": "queued",
            "nextAttemptTick": self._tick,
            "expires": (
                self._tick + config.PORTAL_ARRIVAL_TIMEOUT_TICKS
            ),
            "expiresAt": (
                entryStartedAt
                + config.PORTAL_ARRIVAL_TIMEOUT_SECONDS
            ),
            "bootstrapAtTick": (
                self._tick + config.PORTAL_ENTRY_BOOTSTRAP_TICKS
            ),
            "bootstrapAt": (
                entryStartedAt
                + config.PORTAL_ENTRY_BOOTSTRAP_SECONDS
            ),
        }
        self._pending_portal_entries[playerId] = request
        self._entry_trace(
            "enter.queued",
            playerId=playerId,
            destinationXZ=destinationXZ,
            bootstrapAtTick=request["bootstrapAtTick"],
            bootstrapAt=request["bootstrapAt"],
        )
        self._portal_cooldowns[playerId] = (
            self._tick + config.PORTAL_COOLDOWN_TICKS
        )
        self._notify(
            playerId,
            u"\u6b63\u5728\u51c6\u5907\u66ae\u8272\u7ef4\u5ea6\u5bf9\u5e94\u4f4d\u70b9\u548c\u56de\u7a0b\u95e8\u2026\u2026",
            "AQUA",
        )

    def _return_from_slice(self, playerId, linkedPoint=None):
        point = linkedPoint or self._return_point_for_player(playerId)
        if point is None:
            self._notify(
                playerId,
                u"\u8be5\u56de\u7a0b\u95e8\u6ca1\u6709\u53ef\u7528\u7684\u539f\u7ef4\u5ea6\u8fde\u63a5\u3002",
                "RED",
            )
            return
        self._portal_cooldowns[playerId] = (
            self._tick + config.PORTAL_COOLDOWN_TICKS
        )
        result = self._change_dimension(
            playerId,
            point["dimensionId"],
            portal_logic.player_position_from_foot(point["pos"]),
        )
        if result is False:
            self._notify(playerId, u"\u8fd4\u56de\u5931\u8d25\u3002", "RED")
        else:
            self._notify(playerId, u"\u5df2\u8fd4\u56de\u539f\u7ef4\u5ea6\u3002")

    def _spawn_boss(self, playerId):
        if self._get_dimension(playerId) != config.DIMENSION_ID:
            self._notify(playerId, u"\u8bf7\u5148\u8f93\u5165 !slice enter\u3002", "YELLOW")
            return None
        if len(self._bosses) >= config.MAX_ACTIVE_BOSSES:
            self._notify(playerId, u"Boss \u6570\u91cf\u5df2\u8fbe\u624b\u673a\u6027\u80fd\u4e0a\u9650\u3002", "RED")
            return None
        playerPos = self._get_foot_pos(playerId)
        if playerPos is None:
            return None
        spawnPos = (playerPos[0] + 8.0, playerPos[1] + 1.0, playerPos[2])
        try:
            bossId = self.CreateEngineEntityByTypeStr(
                config.BOSS_IDENTIFIER,
                spawnPos,
                (0.0, 180.0),
                config.DIMENSION_ID,
                False,
                False,
            )
        except Exception as exc:
            print "[TwilightBossSlice] spawn failed:", exc
            bossId = None
        if not bossId:
            self._notify(playerId, u"\u5a1c\u8fe6\u751f\u6210\u5931\u8d25\u3002", "RED")
            return None
        state = self._register_boss(
            bossId, config.DIMENSION_ID, spawnPos
        )
        if state is None:
            self._remove_excess_boss(bossId)
            self._notify(
                playerId,
                u"Boss \u6570\u91cf\u5df2\u8fbe\u624b\u673a\u6027\u80fd\u4e0a\u9650\u3002",
                "RED",
            )
            return None
        self._notify(playerId, u"\u5a1c\u8fe6\u5df2\u751f\u6210\u3002")
        return bossId

    def _burst(self, playerId, requested):
        count = max(1, min(int(requested), config.MAX_ACTIVE_BOSSES))
        spawned = 0
        while spawned < count and len(self._bosses) < config.MAX_ACTIVE_BOSSES:
            if self._spawn_boss(playerId) is None:
                break
            spawned += 1
        self._notify(
            playerId,
            u"\u538b\u529b\u6d4b\u8bd5\uff1a\u751f\u6210 %d\uff0c\u6d3b\u52a8 %d\u3002"
            % (spawned, len(self._bosses)),
            "AQUA",
        )

    def _naga_death_chest_position(self, state):
        home = state.get("home")
        if home is None:
            return None
        return (
            float(math.floor(home[0])) + 0.5,
            float(math.floor(home[1])) + 0.15,
            float(math.floor(home[2])) + 0.5,
        )

    def _begin_naga_death(self, bossId, state, attackerId=None):
        if state.get("dead") or state.get("dying"):
            return False
        if self._is_online_player(attackerId):
            state["participants"].add(str(attackerId))
            state["lastLootingLevel"] = self._hydra_looting_level(attackerId)
        state["dying"] = True
        state["deathTime"] = 0
        state["health"] = 0.0
        state["targetId"] = None
        state["waypoint"] = None
        state["returningHome"] = False
        state["bodyContactReadyTicks"].clear()
        self._reset_attack_target(bossId)
        self._stop_navigation(bossId, state)
        self._schedule_segment_count(state, state["segments"], 0)
        state["segments"] = 0
        self._set_health(bossId, 1.0)
        self._push_state_property(bossId, naga_logic.CHARGE)
        self._save_naga_state(bossId, state)
        return True

    def _spawn_naga_experience(self, state, position):
        if position is None:
            return False
        try:
            return CF.CreateExp(LEVEL_ID).CreateExperienceOrb(
                naga_logic.XP_REWARD,
                tuple(float(value) for value in position),
                False,
            ) is not False
        except Exception as error:
            print "[TwilightBossSlice] Naga experience spawn failed:", error
            return False

    def _finalize_naga_death(self, bossId, state, destroyActor=True):
        if state.get("dead"):
            return False
        position = self._get_foot_pos(bossId) or state.get("home")
        if not state.get("lootAwarded"):
            rewardAllowed = not bool(state.get("worldgenManaged", False))
            if self._ruin_worldgen is not None:
                self._ruin_worldgen.mark_naga_defeated(state.get("home"))
                if state.get("worldgenManaged"):
                    rewardAllowed = self._ruin_worldgen.claim_boss_reward(
                        state.get("home"), "naga"
                    )
            if rewardAllowed:
                self._place_naga_loot_chest(state)
                self._spawn_naga_experience(state, position)
            self._award_naga_progress(state)
            state["lootAwarded"] = True
        state["dying"] = False
        state["deathTime"] = naga_logic.DEATH_TICKS
        state["health"] = 0.0
        state["dead"] = True
        self._destroy_all_segments(state)
        self._broadcast_naga_death_effect(
            state.get("dimensionId"), "finish", (position,), bossId
        )
        self._save_naga_state(bossId, state)
        if destroyActor:
            try:
                self.DestroyEntity(bossId)
            except Exception:
                return False
        return True

    def _update_naga_death(self, bossId, state):
        state["deathTime"] = max(
            0, int(state.get("deathTime", 0))
        ) + 1
        deathTime = int(state["deathTime"])
        position = self._get_foot_pos(bossId) or state.get("home")
        self._set_health(bossId, 1.0)
        if position is not None:
            if deathTime == naga_logic.DEATH_ANIMATION_TICKS:
                self._broadcast_naga_death_effect(
                    state.get("dimensionId"),
                    "start",
                    (position,),
                    bossId,
                )
            start = (
                float(position[0]),
                float(position[1]) + 1.5,
                float(position[2]),
            )
            destination = self._naga_death_chest_position(state)
            trail = naga_logic.death_trail_positions(
                start, destination, deathTime
            ) if destination is not None else []
            if trail:
                self._broadcast_naga_death_effect(
                    state.get("dimensionId"),
                    "trail",
                    trail,
                    bossId,
                )
            burst = naga_logic.death_burst_positions(
                destination,
                deathTime,
                state["brain"].rng,
            ) if destination is not None else []
            if burst:
                self._broadcast_naga_death_effect(
                    state.get("dimensionId"),
                    "burst",
                    burst,
                    bossId,
                )
        if deathTime >= naga_logic.DEATH_TICKS:
            return self._finalize_naga_death(bossId, state)
        if deathTime % 20 == 0:
            self._save_naga_state(bossId, state)
        return True

    def _place_naga_loot_chest(self, state):
        return self._queue_loot_reward(
            state, "naga", state.get("home"), config.NAGA_LOOT_TABLE,
            reward_delivery.bonus_items("naga", state.get("lastLootingLevel", 0), random),
        )

    def _award_naga_progress(self, state):
        home = state.get("home")
        if home is None:
            return
        participantIds = set(
            str(value) for value in state.get("participants", ())
        )
        for playerId in self._get_online_players():
            if str(playerId) not in participantIds:
                continue
            if self._grant_progress(playerId, "tf_naga_defeated"):
                self._notify(
                    playerId,
                    u"\u8fdb\u5ea6\u5df2\u89e3\u9501\uff1a\u5a1c\u8fe6\u730e\u624b",
                    "GOLD",
                )

    def _lich_player_candidate(self, bossPos, state, playerId):
        try:
            gameType = int(
                CF.CreateGame(LEVEL_ID).GetPlayerGameType(playerId)
            )
        except Exception:
            gameType = 0
        if gameType in (1, 3):
            return None
        if self._get_dimension(playerId) != state.get("dimensionId"):
            return None
        playerPos = self._get_foot_pos(playerId)
        if playerPos is None:
            return None
        distanceSq = _distance_sq(playerPos, bossPos)
        if distanceSq > lich_logic.TARGET_RANGE * lich_logic.TARGET_RANGE:
            return None
        return (distanceSq, playerId, playerPos)

    def _lich_retaliation_candidate(self, bossPos, state, preferredId):
        if preferredId is None:
            return None
        entityType = self._get_engine_type(preferredId)
        if entityType is None or entityType in (
            LICH_IDENTIFIER,
            LICH_CLONE_IDENTIFIER,
        ):
            return None
        if self._get_dimension(preferredId) != state.get("dimensionId"):
            return None
        position = self._get_foot_pos(preferredId)
        if position is None:
            return None
        if _distance_sq(position, bossPos) > (
            lich_logic.TARGET_RANGE * lich_logic.TARGET_RANGE
        ):
            return None
        return (preferredId, position)

    def _lich_target(self, bossId, state):
        home = state.get("home")
        if home is None:
            return None
        bossPos = self._get_foot_pos(bossId)
        if bossPos is None:
            return None
        online = list(self._get_online_players())

        def resolve_preferred(preferredId):
            if preferredId is None:
                return None
            for playerId in online:
                if str(playerId) != str(preferredId):
                    continue
                candidate = self._lich_player_candidate(
                    bossPos, state, playerId
                )
                if candidate is not None:
                    return (candidate[1], candidate[2])
                return None
            return self._lich_retaliation_candidate(
                bossPos, state, preferredId
            )

        preferred = resolve_preferred(state.get("lastAttackerId"))
        if preferred is not None:
            return preferred
        preferred = resolve_preferred(state.get("targetId"))
        if preferred is not None:
            return preferred
        candidates = []
        for playerId in online:
            candidate = self._lich_player_candidate(
                bossPos, state, playerId
            )
            if candidate is not None:
                candidates.append(candidate)
        if not candidates:
            return None
        _distance, playerId, playerPos = min(candidates)
        return (playerId, playerPos)

    def _lich_can_see(self, fromId, targetId):
        if fromId is None or targetId is None:
            return False
        try:
            return bool(
                CF.CreateGame(LEVEL_ID).CanSee(
                    fromId,
                    targetId,
                    lich_logic.TARGET_RANGE,
                    True,
                    360.0,
                    360.0,
                )
            )
        except Exception:
            pass
        origin = self._get_foot_pos(fromId)
        target = self._get_foot_pos(targetId)
        dimensionId = self._get_dimension(fromId)
        if origin is None or target is None or dimensionId is None:
            return False
        return self._lich_positions_can_see(origin, target, dimensionId)

    def _lich_positions_can_see(self, origin, target, dimensionId):
        """Ray-test two world positions without passing tuples to CanSee."""
        if origin is None or target is None or dimensionId is None:
            return False
        start = (origin[0], origin[1] + 1.72, origin[2])
        end = (target[0], target[1] + 0.9, target[2])
        for blockPos in quest_ram_logic.ray_samples(start, end):
            blockName = self._block_name(
                self._get_block(blockPos, dimensionId)
            )
            if blockName and blockName not in SIGHT_PASSABLE_BLOCKS:
                return False
        return True

    def _lich_space_is_clear(self, destination, dimensionId):
        x, y, z = destination
        blockY = int(math.floor(y))
        below = self._block_name(
            self._get_block(
                (int(math.floor(x)), blockY - 1, int(math.floor(z))),
                dimensionId,
            )
        )
        if not below or below in SIGHT_PASSABLE_BLOCKS:
            return False
        for offsetX in (-0.55, 0.55):
            for offsetZ in (-0.55, 0.55):
                blockX = int(math.floor(x + offsetX))
                blockZ = int(math.floor(z + offsetZ))
                for offsetY in (0, 1, 2):
                    blockName = self._block_name(
                        self._get_block(
                            (blockX, blockY + offsetY, blockZ),
                            dimensionId,
                        )
                    )
                    if blockName and blockName not in SIGHT_PASSABLE_BLOCKS:
                        return False
        return True

    def _safe_lich_destination(
        self, candidate, targetPos, dimensionId
    ):
        for yOffset in (4, 3, 2, 1, 0, -1, -2, -3, -4, -5, -6, -7, -8):
            destination = (
                float(candidate[0]),
                float(candidate[1]) + float(yOffset),
                float(candidate[2]),
            )
            if not self._lich_space_is_clear(destination, dimensionId):
                continue
            if self._lich_positions_can_see(
                destination, targetPos, dimensionId
            ):
                return destination
        return None

    def _find_lich_destination(self, state, targetPos):
        if targetPos is None:
            return None
        dimensionId = state.get("dimensionId")
        for _unused in range(100):
            candidate = lich_logic.teleport_candidate(targetPos, random)
            destination = self._safe_lich_destination(
                candidate, targetPos, dimensionId
            )
            if destination is not None:
                return destination
        return None

    def _spawn_lich_projectile(
        self,
        projectile_type,
        ownerId,
        targetId,
        speed=lich_logic.SOURCE_PROJECTILE_SPEED,
        inaccuracy=lich_logic.SOURCE_PROJECTILE_INACCURACY,
    ):
        ownerPos = self._get_foot_pos(ownerId)
        targetPos = self._get_foot_pos(targetId)
        dimensionId = self._get_dimension(ownerId)
        if ownerPos is None or targetPos is None or dimensionId is None:
            return None
        rotation = self._get_rotation(ownerId)
        bodyAngle = math.radians(float(rotation[1]))
        spawnPos = (
            float(ownerPos[0]) + math.cos(bodyAngle) * 0.65,
            float(ownerPos[1]) + 1.72,
            float(ownerPos[2]) + math.sin(bodyAngle) * 0.65,
        )
        dx = float(targetPos[0]) - spawnPos[0]
        dy = (
            float(targetPos[1]) + 0.9
            - (float(ownerPos[1]) + 1.05)
        )
        dz = float(targetPos[2]) - spawnPos[2]
        if dx * dx + dy * dy + dz * dz <= 0.00000001:
            return None
        projectileId = self._spawn_ruin_entity(
            projectile_type,
            spawnPos,
            rotation[1],
            dimensionId,
        )
        if not projectileId:
            return None
        velocity = lich_logic.aim_projectile_velocity(
            (dx, dy, dz),
            speed,
            inaccuracy,
            random,
        )
        try:
            CF.CreateActorMotion(projectileId).SetMotion(velocity)
        except Exception:
            pass
        projectileState = lich_logic.new_projectile_state(
            projectile_type, ownerId, self._tick, velocity
        )
        projectileState["inaccuracy"] = float(inaccuracy)
        projectileState["velocity"] = velocity
        self._lich_projectiles[projectileId] = projectileState
        self._play_world_sound("mob.ghast.fireball", spawnPos, 1.0, 1.0)
        self._broadcast_lich_effect(
            dimensionId,
            "projectile_launch",
            (spawnPos,),
            projectileId,
            style=str(projectile_type),
        )
        return projectileId

    def _teleport_lich(self, entityId, state, targetPos=None):
        source = self._get_foot_pos(entityId)
        if source is None or targetPos is None:
            return False
        destination = self._find_lich_destination(state, targetPos)
        if destination is None:
            return False
        try:
            if CF.CreatePos(entityId).SetPos(destination) is False:
                return False
            actual = self._get_foot_pos(entityId) or destination
            if not self._lich_positions_can_see(
                actual, targetPos, state.get("dimensionId")
            ):
                CF.CreatePos(entityId).SetPos(source)
                return False
            self._face_position(entityId, actual, targetPos)
            self._play_world_sound(
                "mob.chorusfruit.teleport", source, 1.0, 1.0
            )
            self._play_world_sound(
                "mob.chorusfruit.teleport", destination, 1.0, 1.0
            )
            self._broadcast_lich_effect(
                state.get("dimensionId"),
                "teleport",
                (source, destination),
                entityId,
            )
            return True
        except Exception:
            try:
                CF.CreatePos(entityId).SetPos(source)
            except Exception:
                pass
            return False

    def _find_lich_master(self, entityId, dimensionId, kind):
        position = self._get_foot_pos(entityId)
        if position is None:
            return None
        candidates = []
        for bossId, state in self._lich_bosses.items():
            if state.get("dead") or state.get("dimensionId") != dimensionId:
                continue
            bossPos = self._get_foot_pos(bossId)
            if bossPos is None:
                continue
            if not self._inside_lich_search_box(position, bossPos):
                continue
            if kind == "clone" and (
                lich_logic.refresh_phase(state) != lich_logic.PHASE_SHADOW
                or len(state.get("cloneIds", ()))
                >= lich_logic.MAX_SHADOW_CLONES
            ):
                continue
            if kind == "minion" and len(state.get("minionIds", ())) >= lich_logic.MAX_ACTIVE_MINIONS:
                continue
            candidates.append((_distance_sq(position, bossPos), bossId))
        return min(candidates)[1] if candidates else None

    def _inside_lich_search_box(self, first, second):
        return bool(
            first is not None
            and second is not None
            and abs(float(first[0]) - float(second[0])) <= 32.0
            and abs(float(first[1]) - float(second[1])) <= 16.0
            and abs(float(first[2]) - float(second[2])) <= 32.0
        )

    def _attach_lich_dependent(self, entityId, state, kind):
        ownerId = state.get("ownerId")
        ownerState = self._lich_state(ownerId)
        if ownerState is None or ownerState.get("dead"):
            ownerId = self._find_lich_master(
                entityId, state.get("dimensionId"), kind
            )
            ownerState = self._lich_state(ownerId)
        if ownerState is None or ownerState.get("dead"):
            return None
        state["ownerId"] = ownerId
        state["orphanTicks"] = 0
        if kind == "clone":
            ownerState["cloneIds"].add(entityId)
            ownerState["cloneCount"] = len(ownerState["cloneIds"])
        else:
            ownerState["minionIds"].add(entityId)
            ownerState["activeMinions"] = len(ownerState["minionIds"])
        self._save_lich_dependent_state(entityId, kind, state)
        return ownerState

    def _register_lich_clone(self, entityId, dimensionId):
        saved = self._load_lich_dependent_state(entityId) or {}
        state = lich_logic.new_clone_state(
            saved.get("ownerId"), saved.get("attackCooldown", 60)
        )
        state.update(
            {
                "dimensionId": int(dimensionId),
                "nextAttackType": int(saved.get("nextAttackType", 0)),
            }
        )
        self._lich_clones[entityId] = state
        self._attach_lich_dependent(entityId, state, "clone")
        self._set_entity_carried_item(
            entityId,
            {
                "newItemName": "tf_slice:twilight_scepter",
                "newAuxValue": 0,
                "count": 1,
            },
        )
        return state

    def _register_lich_minion(self, entityId, dimensionId):
        saved = self._load_lich_dependent_state(entityId) or {}
        state = {
            "ownerId": saved.get("ownerId"),
            "dimensionId": int(dimensionId),
            "orphanTicks": 0,
            "strengthUntil": 0,
        }
        self._lich_minions[entityId] = state
        self._attach_lich_dependent(entityId, state, "minion")
        return state

    def _spawn_lich_clone(self, bossId, state):
        targetPos = self._get_foot_pos(state.get("targetId"))
        destination = self._find_lich_destination(state, targetPos)
        if destination is None:
            state["cloneCount"] = max(0, int(state["cloneCount"]) - 1)
            return None
        cloneId = self._spawn_ruin_entity(
            LICH_CLONE_IDENTIFIER,
            destination,
            random.uniform(0.0, 360.0),
            state["dimensionId"],
        )
        if not cloneId:
            state["cloneCount"] = max(0, int(state["cloneCount"]) - 1)
            return None
        cloneState = lich_logic.new_clone_state(
            bossId,
            60 + random.randrange(3) - random.randrange(3),
        )
        cloneState["dimensionId"] = state["dimensionId"]
        self._lich_clones[cloneId] = cloneState
        state["cloneIds"].add(cloneId)
        state["cloneCount"] = len(state["cloneIds"])
        self._save_lich_dependent_state(cloneId, "clone", cloneState)
        self._set_attack_target(cloneId, state.get("targetId"))
        self._set_entity_carried_item(
            cloneId,
            {
                "newItemName": "tf_slice:twilight_scepter",
                "newAuxValue": 0,
                "count": 1,
            },
        )
        self._broadcast_lich_effect(
            state.get("dimensionId"),
            "clone_spawn",
            (self._get_foot_pos(bossId), destination),
            cloneId,
        )
        return cloneId

    def _lich_minion_floor_clear(self, destination, dimensionId):
        x, y, z = destination
        y = int(math.floor(y))
        air = ("minecraft:air", "minecraft:cave_air", "minecraft:void_air")
        hazards = air + ("minecraft:water", "minecraft:flowing_water",
                         "minecraft:lava", "minecraft:flowing_lava",
                         "minecraft:fire", "minecraft:magma")
        for dx, dz in ((0, 0), (-0.31, -0.31), (-0.31, 0.31),
                       (0.31, -0.31), (0.31, 0.31)):
            bx, bz = int(math.floor(x + dx)), int(math.floor(z + dz))
            below = self._block_name(self._get_block((bx, y - 1, bz), dimensionId))
            if not below or below in hazards:
                return False
            for height in (0, 1):
                block = self._block_name(self._get_block((bx, y + height, bz), dimensionId))
                if block not in air:
                    return False
        return True

    def _find_lich_minion_destination(self, state):
        # User-requested arena rule: home is persisted and cannot follow a
        # player/minion down the tower. Never search lower floors.
        home = state.get("home")
        if home is None:
            return None
        floorY = int(math.floor(float(home[1])))
        offsets = [(dx * radius, dz * radius)
                   for radius in (2, 4, 6, 8)
                   for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1),
                                  (1, 1), (-1, 1), (1, -1), (-1, -1))]
        random.shuffle(offsets)
        for dx, dz in offsets:
            destination = (float(home[0]) + dx, float(floorY), float(home[2]) + dz)
            if (self._lich_minion_floor_clear(destination, state.get("dimensionId"))
                    and self._lich_positions_can_see(destination, home, state.get("dimensionId"))):
                return destination
        return None

    def _lich_minion_target_on_floor(self, targetId, state):
        home = state.get("home")
        target = self._get_foot_pos(targetId) if targetId is not None else None
        return bool(home is not None and target is not None
                    and -0.5 <= float(target[1]) - math.floor(float(home[1])) <= 2.5)

    def _keep_lich_minion_on_floor(self, entityId, minion, state):
        if self._tick < int(minion.get("floorCheckAfter", 0)):
            return
        minion["floorCheckAfter"] = self._tick + 5
        home, position = state.get("home"), self._get_foot_pos(entityId)
        if home is None or position is None:
            return
        if float(position[1]) >= math.floor(float(home[1])) - 0.5:
            return
        minion["floorCheckAfter"] = self._tick + 20
        destination = self._find_lich_minion_destination(state)
        if destination is None:
            return
        self._reset_attack_target(entityId)
        try:
            moved = CF.CreatePos(entityId).SetFootPos(destination)
        except Exception:
            moved = False
        if moved is True:
            self._set_full_motion(entityId, (0.0, 0.0, 0.0))
            self._broadcast_lich_effect(state.get("dimensionId"), "teleport",
                                        (position, destination), entityId)
            self._entry_trace("lich.minion_return", entityId=str(entityId),
                              destination=destination)

    def _spawn_lich_minion(self, bossId, state, targetId):
        destination = self._find_lich_minion_destination(state)
        if destination is None:
            state["activeMinions"] = max(
                0, int(state["activeMinions"]) - 1
            )
            state["minionsRemaining"] += 1
            return None
        minionId = self._spawn_ruin_entity(
            LICH_MINION_IDENTIFIER,
            destination,
            random.uniform(0.0, 360.0),
            state["dimensionId"],
        )
        if not minionId:
            state["activeMinions"] = max(
                0, int(state["activeMinions"]) - 1
            )
            state["minionsRemaining"] += 1
            return None
        minionState = {
            "ownerId": bossId,
            "dimensionId": state["dimensionId"],
            "orphanTicks": 0,
            "strengthUntil": 0,
        }
        state["minionIds"].add(minionId)
        state["activeMinions"] = len(state["minionIds"])
        self._lich_minions[minionId] = minionState
        self._save_lich_dependent_state(minionId, "minion", minionState)
        self._set_attack_target(minionId, targetId)
        self._play_world_sound("random.pop", destination, 1.0, 2.0)
        self._broadcast_lich_effect(
            state.get("dimensionId"),
            "minion_summon",
            (self._get_foot_pos(bossId), destination),
            minionId,
        )
        return minionId

    def _lich_pop_targets(self, bossId, state, bossPos, ignoreReadiness=False):
        if not ignoreReadiness and (
            float(state.get("health", lich_logic.MAX_HEALTH))
            >= float(state.get("maxHealth", lich_logic.MAX_HEALTH))
            or int(state.get("popCooldown", 0)) > 0
        ):
            return []
        try:
            filters = {
                "any_of": [
                    {"test": "is_family", "subject": "other", "value": "mob"}
                ]
            }
            entityIds = CF.CreateGame(LEVEL_ID).GetEntitiesAround(
                bossId, 48, filters
            ) or []
        except Exception:
            entityIds = []
        candidates = []
        for entityId in entityIds:
            if self._get_engine_type(entityId) not in LICH_POPPABLE_IDENTIFIERS:
                continue
            position = self._get_foot_pos(entityId)
            if position is None:
                continue
            if not self._inside_lich_search_box(position, bossPos):
                continue
            if not self._lich_positions_can_see(
                bossPos, position, state.get("dimensionId")
            ):
                continue
            candidates.append(
                (
                    _distance_sq(bossPos, position),
                    entityId,
                    self._get_health(entityId, 20.0),
                )
            )
        candidates.sort(key=lambda value: (value[0], str(value[1])))
        return [
            {"id": entityId, "health": health}
            for _distance, entityId, health in candidates
        ]

    def _lich_pop_target(self, bossId, state, bossPos):
        targets = self._lich_pop_targets(bossId, state, bossPos)
        return targets[0] if targets else None

    def _lich_minion_cast_target(self, state, bossPos):
        if (
            float(state.get("health", lich_logic.MAX_HEALTH))
            >= float(state.get("maxHealth", lich_logic.MAX_HEALTH)) / 2.0
        ):
            return None
        for minionId in list(state.get("minionIds", set())):
            minionKey = entity_registry_logic.matching_entity_key(
                self._lich_minions, minionId
            )
            if minionKey is None:
                continue
            position = self._get_foot_pos(minionKey)
            if position is None:
                continue
            if not self._inside_lich_search_box(position, bossPos):
                continue
            return {
                "id": minionKey,
                "health": self._get_health(minionKey, 20.0),
            }
        return None

    def _lich_cast_target_is_valid(self, bossId, state, bossPos):
        targetId = state.get("castTargetId")
        if targetId is None:
            return False
        if state.get("castKind") == "absorb":
            if float(state.get("health", 0.0)) >= float(
                state.get("maxHealth", lich_logic.MAX_HEALTH)
            ) / 2.0:
                return False
            minionKey = entity_registry_logic.matching_entity_key(
                self._lich_minions, targetId
            )
            minionPos = self._get_foot_pos(minionKey)
            if (
                minionKey is not None
                and self._inside_lich_search_box(minionPos, bossPos)
            ):
                state["castTargetHealth"] = self._get_health(
                    minionKey, state.get("castTargetHealth", 20.0)
                )
                return True
            return False
        if state.get("castKind") == "pop":
            if (
                float(state.get("health", 0.0))
                >= float(state.get("maxHealth", lich_logic.MAX_HEALTH))
                or int(state.get("popCooldown", 0)) > 0
            ):
                return False
            targetPos = self._get_foot_pos(targetId)
            if (
                self._get_engine_type(targetId) in LICH_POPPABLE_IDENTIFIERS
                and self._inside_lich_search_box(targetPos, bossPos)
                and self._lich_positions_can_see(
                    bossPos, targetPos, state.get("dimensionId")
                )
            ):
                return True
        return False

    def _navigate_lich_melee(self, entityId, state, targetId, targetPos):
        if targetPos is None:
            return False
        if (
            str(state.get("meleeNavTarget")) == str(targetId)
            and self._tick - int(state.get("meleeNavTick", -20)) < 10
        ):
            return True
        state["meleeNavTarget"] = targetId
        state["meleeNavTick"] = self._tick

        def callback(_entityId, _result):
            return None

        try:
            CF.CreateMoveTo(entityId).SetMoveSetting(
                tuple(float(value) for value in targetPos),
                0.75,
                config.NAVIGATION_MAX_ITERATIONS,
                callback,
            )
            return True
        except Exception:
            origin = self._get_foot_pos(entityId)
            if origin is None:
                return False
            direction = _normalized_xz(origin, targetPos)
            return self._set_motion(
                entityId, direction[0] * 0.22, direction[1] * 0.22
            )

    def _return_lich_home(self, entityId, state):
        """Run the source restriction goal while no combat goal owns movement."""
        home = state.get("home")
        position = self._get_foot_pos(entityId)
        if home is None or position is None:
            return False
        distance = math.sqrt(_distance_sq(position, home))
        if not lich_logic.should_return_home(distance):
            return False
        if self._tick - int(state.get("homeNavTick", -20)) < 10:
            return True
        state["homeNavTick"] = self._tick

        def callback(_entityId, _result):
            return None

        try:
            CF.CreateMoveTo(entityId).SetMoveSetting(
                tuple(float(value) for value in home),
                lich_logic.RETURN_HOME_SPEED,
                config.NAVIGATION_MAX_ITERATIONS,
                callback,
            )
            return True
        except Exception:
            direction = _normalized_xz(position, home)
            return self._set_motion(
                entityId,
                direction[0] * 0.32,
                direction[1] * 0.32,
            )

    def _stop_lich_navigation(self, entityId, state):
        if state.get("meleeNavTarget") is None:
            return
        state["meleeNavTarget"] = None
        state["meleeNavTick"] = -20
        self._set_motion(entityId, 0.0, 0.0)

    def _discard_lich_clones(self, state):
        cloneIds = list(state.get("cloneIds", set()))
        state["cloneIds"] = set()
        state["cloneCount"] = 0
        for cloneId in cloneIds:
            cloneKey = entity_registry_logic.matching_entity_key(
                self._lich_clones, cloneId
            )
            if cloneKey is not None:
                self._lich_clones.pop(cloneKey, None)
            try:
                self.DestroyEntity(cloneId)
            except Exception:
                pass

    def _restore_lich_spawner(self, bossId, state):
        home = state.get("home")
        dimensionId = state.get("dimensionId")
        if home is None or dimensionId is None:
            return False
        blockPos = tuple(int(math.floor(float(value))) for value in home)
        restored = self._set_block(
            blockPos, LICH_SPAWNER_BLOCK, dimensionId
        )
        if restored is False:
            return False
        state["peacefulRestore"] = True
        try:
            self.DestroyEntity(bossId)
        except Exception:
            return False
        return True

    def _queue_lich_candle_scan(self, state, origin):
        state["candleScanIndex"] = 0
        state["candleScanOrigin"] = tuple(origin)

    def _update_lich_candle_scan(self, state):
        index = state.get("candleScanIndex")
        origin = state.get("candleScanOrigin")
        if index is None or origin is None:
            return
        dimensionId = state.get("dimensionId")
        total = 21 * 21 * 21
        changedPositions = []
        for current in range(int(index), total):
            offsetX = current % 21 - 10
            offsetZ = (current // 21) % 21 - 10
            offsetY = current // (21 * 21) - 10
            blockPos = (
                int(math.floor(origin[0])) + offsetX,
                int(math.floor(origin[1])) + offsetY,
                int(math.floor(origin[2])) + offsetZ,
            )
            block = self._get_block(blockPos, dimensionId)
            blockName = self._block_name(block)
            if not isinstance(block, dict):
                continue
            replacement = dict(block)
            replaced = False
            states = replacement.get("states") or replacement.get("blockStates")
            states = dict(states) if isinstance(states, dict) else {}
            lightingKeys = (
                "lighting",
                "tf_slice:lighting",
                "twilightforest:lighting",
            )
            isLightable = any(key in states for key in lightingKeys)
            if "candle" not in blockName and not isLightable:
                continue
            if "candle" in blockName:
                try:
                    aux = int(replacement.get("aux", 0))
                    if aux & 4:
                        replacement["aux"] = aux & 3
                        replaced = True
                except (TypeError, ValueError):
                    pass
            if isinstance(states, dict):
                for key in ("lit", "lit_bit", "minecraft:lit"):
                    if states.get(key):
                        states[key] = False
                        replaced = True
                for key in lightingKeys:
                    value = str(states.get(key, "")).lower()
                    if value == "normal":
                        states[key] = "ominous"
                        replaced = True
                if "states" in replacement:
                    replacement["states"] = states
                else:
                    replacement["blockStates"] = states
            if not replaced:
                continue
            try:
                self._block_comp.SetBlockNew(
                    blockPos,
                    replacement,
                    0,
                    dimensionId,
                    True,
                    False,
                )
                changedPositions.append(blockPos)
            except Exception:
                pass
        state["candleScanIndex"] = total
        if int(state["candleScanIndex"]) >= total:
            state["candleScanIndex"] = None
            state.pop("candleScanOrigin", None)
        if changedPositions:
            for blockPos in changedPositions:
                self._play_world_sound(
                    "random.fizz", blockPos, 2.0, 1.0
                )
            self._broadcast_lich_effect(
                dimensionId,
                "extinguish_candles",
                changedPositions,
            )

    def _broadcast_lich_effect(
        self, dimensionId, kind, positions, entityId=None, style=None
    ):
        cleaned = []
        for position in positions or ():
            if position is None:
                continue
            cleaned.append(tuple(float(value) for value in position[:3]))
        self.BroadcastToAllClient(
            "LichCombatEffect",
            {
                "dimensionId": int(dimensionId or 0),
                "kind": str(kind),
                "entityId": str(entityId or ""),
                "style": str(style or ""),
                "positions": cleaned,
            },
        )

    def _execute_lich_action(
        self, bossId, state, targetId, targetPos, action
    ):
        if state.get("dying") or state.get("dead"):
            return
        actionType = action.get("type")
        if actionType == "spawn_clone":
            self._spawn_lich_clone(bossId, state)
        elif actionType == "spawn_minion":
            self._spawn_lich_minion(bossId, state, targetId)
        elif actionType == "teleport":
            self._stop_lich_navigation(bossId, state)
            self._teleport_lich(bossId, state, targetPos)
        elif actionType == "shoot_bolt":
            self._spawn_lich_projectile(
                LICH_BOLT_IDENTIFIER, bossId, targetId
            )
        elif actionType == "shoot_bomb":
            self._spawn_lich_projectile(
                LICH_BOMB_IDENTIFIER, bossId, targetId
            )
        elif actionType == "melee":
            self._hurt(targetId, float(action.get("damage", 3.0)), bossId)
        elif actionType == "chase":
            self._navigate_lich_melee(
                bossId, state, targetId, targetPos
            )
        elif actionType in ("start_pop", "start_absorb"):
            self._stop_lich_navigation(bossId, state)
            self._broadcast_lich_effect(
                state.get("dimensionId"),
                "scepter_charge",
                (self._get_foot_pos(bossId),),
                bossId,
            )
        elif actionType in ("pop_mob", "absorb_minion"):
            consumedId = action.get("targetId")
            consumedIds = [consumedId] if consumedId is not None else []
            if actionType == "absorb_minion":
                minionKey = entity_registry_logic.matching_entity_key(
                    self._lich_minions, consumedId
                )
                if minionKey is not None:
                    self._lich_minions.pop(minionKey, None)
                state.get("minionIds", set()).discard(consumedId)
                state["activeMinions"] = len(state.get("minionIds", set()))
            consumedPositions = []
            for currentId in consumedIds:
                consumedPos = self._get_foot_pos(currentId)
                if consumedPos is not None:
                    consumedPositions.append(consumedPos)
                try:
                    self.DestroyEntity(currentId)
                except Exception:
                    pass
                self._play_world_sound(
                    "mob.chicken.plop",
                    consumedPos or self._get_foot_pos(bossId),
                    3.0,
                    0.5,
                )
            self._set_health(bossId, state["health"])
            self._broadcast_lich_effect(
                state.get("dimensionId"),
                actionType,
                tuple(consumedPositions) + (self._get_foot_pos(bossId),),
                bossId,
            )
        elif actionType == "extinguish_candles":
            origin = self._get_foot_pos(bossId)
            if origin is not None:
                self._queue_lich_candle_scan(state, origin)

    def _refresh_lich_minions(self, bossId, state):
        # MobDie precedes actor removal. Only confirmed dead minions may be
        # pruned; an unavailable/unloaded actor is not proof of death.
        for entityId in list(state.get("minionIds", set())):
            try:
                alive = CF.CreateGame(LEVEL_ID).IsEntityAlive(entityId)
            except Exception:
                alive = None
            if alive is False:
                state["minionIds"].discard(entityId)
                key = entity_registry_logic.matching_entity_key(
                    self._lich_minions, entityId
                )
                self._lich_minions.pop(key, None)
        if self._tick >= int(state.get("relationRecoveryUntil", 0)):
            state["activeMinions"] = len(state.get("minionIds", set()))

    def _drive_lich_bosses(self):
        for bossId, state in list(self._lich_bosses.items()):
            if state.get("dead"):
                continue
            if state.get("dying"):
                self._update_lich_death(bossId, state)
                continue
            if self._difficulty() == 0:
                self._discard_lich_clones(state)
                self._restore_lich_spawner(bossId, state)
                continue
            position = self._get_foot_pos(bossId)
            if position is None:
                state["missingActorTicks"] += 1
                continue
            state["missingActorTicks"] = 0
            self._refresh_lich_minions(bossId, state)
            if self._tick % 60 == 0:
                self._entry_trace(
                    "lich.phase_sample", entityId=str(bossId),
                    health=state.get("health"),
                    shields=state.get("shieldStrength"),
                    remaining=state.get("minionsRemaining"),
                    active=state.get("activeMinions"),
                    phase=lich_logic.refresh_phase(state),
                )
            engine_health = self._get_health(bossId, state["health"])
            if int(state.get("shieldStrength", 0)) <= 0:
                state["health"] = engine_health
            previousPhase = lich_logic.refresh_phase(state)
            if state.get("castKind") and not self._lich_cast_target_is_valid(
                bossId, state, position
            ):
                lich_logic.cancel_scepter_cast(state)
            popTarget = None
            minionTarget = None
            if not state.get("castKind"):
                popTarget = self._lich_pop_target(
                    bossId, state, position
                )
                if popTarget is None:
                    minionTarget = self._lich_minion_cast_target(
                        state, position
                    )
            target = self._lich_target(bossId, state)
            if target is None:
                state["targetId"] = None
                self._reset_attack_target(bossId)
                self._stop_lich_navigation(bossId, state)
                actions = lich_logic.advance_combat_tick(
                    state,
                    0.0,
                    False,
                    random,
                    pop_target=popTarget,
                    minion_target=minionTarget,
                    has_target=False,
                )
                for action in actions:
                    self._execute_lich_action(
                        bossId, state, None, None, action
                    )
                if not actions:
                    self._return_lich_home(bossId, state)
                self._sync_lich_presentation(bossId, state)
                self._update_lich_candle_scan(state)
                if self._tick % 20 == 0:
                    self._save_lich_state(bossId, state)
                continue
            targetId, targetPos = target
            state["targetId"] = targetId
            self._set_attack_target(bossId, targetId)
            hasLineOfSight = self._lich_can_see(bossId, targetId)
            actions = lich_logic.advance_combat_tick(
                state,
                math.sqrt(_distance_sq(position, targetPos)),
                hasLineOfSight,
                random,
                pop_target=popTarget,
                minion_target=minionTarget,
            )
            for action in actions:
                self._execute_lich_action(
                    bossId, state, targetId, targetPos, action
                )
            currentPhase = lich_logic.refresh_phase(state)
            if (
                previousPhase == lich_logic.PHASE_SHADOW
                and currentPhase != lich_logic.PHASE_SHADOW
            ):
                self._discard_lich_clones(state)
            if currentPhase != lich_logic.PHASE_MELEE:
                self._stop_lich_navigation(bossId, state)
            self._sync_lich_presentation(bossId, state)
            self._update_lich_candle_scan(state)
            if actions or self._tick % 20 == 0:
                self._save_lich_state(bossId, state)

    def _loyal_zombie_target(self, zombieId, ownerId):
        try:
            filters = {
                "any_of": [
                    {"test": "is_family", "subject": "other", "value": "monster"}
                ]
            }
            entities = CF.CreateGame(LEVEL_ID).GetEntitiesAround(
                ownerId, 16, filters
            ) or []
        except Exception:
            entities = []
        zombiePos = self._get_foot_pos(zombieId)
        candidates = []
        for entityId in entities:
            if entityId == zombieId or entityId == ownerId:
                continue
            if entity_registry_logic.matching_entity_key(
                self._loyal_zombies, entityId
            ) is not None:
                continue
            position = self._get_foot_pos(entityId)
            if position is not None and zombiePos is not None:
                candidates.append((_distance_sq(zombiePos, position), entityId))
        return min(candidates)[1] if candidates else None

    def _update_lich_dependents(self):
        for cloneId, cloneState in list(self._lich_clones.items()):
            state = self._lich_state(cloneState.get("ownerId"))
            if state is None or state.get("dead"):
                state = self._attach_lich_dependent(
                    cloneId, cloneState, "clone"
                )
            if state is None:
                cloneState["orphanTicks"] = int(
                    cloneState.get("orphanTicks", 0)
                ) + 1
                if cloneState["orphanTicks"] > 1:
                    self._lich_clones.pop(cloneId, None)
                    self.DestroyEntity(cloneId)
                continue
            if (
                state.get("dead")
                or lich_logic.refresh_phase(state)
                != lich_logic.PHASE_SHADOW
            ):
                self._lich_clones.pop(cloneId, None)
                state.get("cloneIds", set()).discard(cloneId)
                state["cloneCount"] = len(state.get("cloneIds", set()))
                self.DestroyEntity(cloneId)
                continue
            targetId = state.get("targetId")
            targetPos = self._get_foot_pos(targetId)
            clonePos = self._get_foot_pos(cloneId)
            if targetId is None or targetPos is None or clonePos is None:
                if int(cloneState.get("attackCooldown", 0)) > 0:
                    cloneState["attackCooldown"] -= 1
                continue
            cloneState["targetId"] = targetId
            self._set_attack_target(cloneId, targetId)
            hasLineOfSight = self._lich_can_see(cloneId, targetId)
            actions = lich_logic.advance_clone_tick(
                cloneState,
                math.sqrt(_distance_sq(clonePos, targetPos)),
                hasLineOfSight,
                random,
            )
            for action in actions:
                actionType = action.get("type")
                if actionType == "teleport":
                    self._teleport_lich(cloneId, cloneState, targetPos)
                elif actionType == "shoot_bolt":
                    self._spawn_lich_projectile(
                        LICH_BOLT_IDENTIFIER, cloneId, targetId
                    )
                elif actionType == "shoot_bomb":
                    self._spawn_lich_projectile(
                        LICH_BOMB_IDENTIFIER, cloneId, targetId
                    )
            if actions or self._tick % 20 == 0:
                self._save_lich_dependent_state(
                    cloneId, "clone", cloneState
                )
        for minionId, minionState in list(self._lich_minions.items()):
            state = self._lich_state(minionState.get("ownerId"))
            if state is None or state.get("dead"):
                state = self._attach_lich_dependent(
                    minionId, minionState, "minion"
                )
            if state is None:
                minionState["orphanTicks"] = int(
                    minionState.get("orphanTicks", 0)
                ) + 1
                if minionState["orphanTicks"] > 1:
                    self._lich_minions.pop(minionId, None)
                    self.DestroyEntity(minionId)
                continue
            if state.get("dead"):
                self._lich_minions.pop(minionId, None)
                state.get("minionIds", set()).discard(minionId)
                state["activeMinions"] = len(state.get("minionIds", set()))
                self.DestroyEntity(minionId)
                continue
            self._keep_lich_minion_on_floor(minionId, minionState, state)
            if self._lich_minion_target_on_floor(state.get("targetId"), state):
                self._set_attack_target(minionId, state["targetId"])
            else:
                self._reset_attack_target(minionId)
            if (
                int(minionState.get("strengthUntil", 0)) > 0
                and self._tick >= int(minionState["strengthUntil"])
            ):
                minionState["strengthUntil"] = 0
                self._trigger_entity_event(
                    minionId, "tf_slice:clear_strengthened"
                )
        for zombieId, loyal in list(self._loyal_zombies.items()):
            if self._tick >= int(loyal.get("expires", 0)):
                self.DestroyEntity(zombieId)
                continue
            ownerPos = self._get_foot_pos(loyal.get("ownerId"))
            zombiePos = self._get_foot_pos(zombieId)
            if ownerPos is None or zombiePos is None:
                continue
            targetId = self._loyal_zombie_target(
                zombieId, loyal.get("ownerId")
            )
            if targetId is not None:
                self._set_attack_target(zombieId, targetId)
            if _distance_sq(ownerPos, zombiePos) > 36.0:
                direction = _normalized_xz(zombiePos, ownerPos)
                self._set_motion(
                    zombieId, direction[0] * 0.22, direction[1] * 0.22
                )
        for targetId, hit in list(self._recent_lich_projectile_hits.items()):
            if self._tick > int(hit.get("expires", 0)):
                self._recent_lich_projectile_hits.pop(targetId, None)
        for targetId, hit in list(self._recent_lich_effect_damage.items()):
            if self._tick > int(hit.get("expires", 0)):
                self._recent_lich_effect_damage.pop(targetId, None)
        for bossId, state in list(self._lich_bosses.items()):
            if state.get("dead") or self._tick < int(
                state.get("relationRecoveryUntil", 0)
            ):
                continue
            cloneCount = len(state.get("cloneIds", set()))
            minionCount = len(state.get("minionIds", set()))
            if (
                int(state.get("cloneCount", 0)) != cloneCount
                or int(state.get("activeMinions", 0)) != minionCount
            ):
                state["cloneCount"] = cloneCount
                state["activeMinions"] = minionCount
                lich_logic.refresh_phase(state)
                self._save_lich_state(bossId, state)

    def _update_lich_projectiles(self):
        expectedTypes = set(
            (
                LICH_BOLT_IDENTIFIER,
                LICH_BOMB_IDENTIFIER,
                TOME_BOLT_IDENTIFIER,
                TWILIGHT_WAND_BOLT_IDENTIFIER,
            )
        )
        for projectileId, state in list(self._lich_projectiles.items()):
            entityType = self._get_engine_type(projectileId)
            exists = entityType in expectedTypes
            motion = self._get_full_motion(projectileId) if exists else None
            action = lich_logic.projectile_lifecycle_action(
                state, self._tick, exists, motion
            )
            if action == "keep":
                continue
            self._lich_projectiles.pop(projectileId, None)
            if action == "destroy":
                try:
                    self.DestroyEntity(projectileId)
                except Exception:
                    pass

    def _clear_player_fortification(self, playerId):
        # SDK lifecycle events can expose the same entity as int or str.
        for states in (self._player_fortification, self._fortification_cooldowns):
            key = entity_registry_logic.matching_entity_key(states, playerId)
            if key is not None:
                states.pop(key, None)
        key = entity_registry_logic.matching_entity_key(
            self._fortification_visuals, playerId
        )
        if key is not None:
            self._destroy_fortification_visual(key)

    def _destroy_fortification_visual(self, playerId):
        visual = self._fortification_visuals.pop(playerId, None) or {}
        if not visual:
            return False
        self._broadcast_lich_effect(
            visual.get("dimensionId"),
            "fortification_visual_remove",
            (),
            playerId,
            style="0",
        )
        return True

    def _sync_fortification_visual(self, playerId, shield):
        shieldCount = min(
            5,
            int(shield.get("temporary", 0))
            + int(shield.get("permanent", 0)),
        )
        if shieldCount <= 0:
            self._destroy_fortification_visual(playerId)
            return None
        dimensionId = self._get_dimension(playerId)
        if dimensionId is None:
            return None
        visual = self._fortification_visuals.get(playerId) or {}
        if visual.get("dimensionId") != dimensionId:
            self._destroy_fortification_visual(playerId)
            visual = {
                "dimensionId": dimensionId,
                "count": None,
                "lastClientSync": -1000,
            }
            self._fortification_visuals[playerId] = visual
        countChanged = visual.get("count") != shieldCount
        if countChanged:
            visual["count"] = shieldCount
        if (
            countChanged
            or self._tick - int(visual.get("lastClientSync", -1000)) >= 20
        ):
            self._broadcast_lich_effect(
                dimensionId,
                "fortification_visual_sync",
                (),
                playerId,
                style=str(shieldCount),
            )
            visual["lastClientSync"] = self._tick
        return playerId

    def _update_fortification_shields(self):
        for playerId, shield in list(self._player_fortification.items()):
            if not self._is_online_player(playerId):
                self._clear_player_fortification(playerId)
                continue
            before = int(shield.get("temporary", 0))
            scepter_logic.tick_shields(
                shield, 1, self._is_creative(playerId)
            )
            if int(shield.get("temporary", 0)) < before:
                position = self._get_foot_pos(playerId)
                dimensionId = self._get_dimension(playerId)
                if position is not None and dimensionId is not None:
                    self._broadcast_lich_effect(
                        dimensionId, "fortification_expire", (position,), playerId
                    )
                    self._play_world_sound("random.fizz", position, 0.25, 1.4)
            if not scepter_logic.has_shield(shield):
                self._player_fortification.pop(playerId, None)
                self._destroy_fortification_visual(playerId)
                continue
            self._sync_fortification_visual(playerId, shield)

    def _consume_carried_charge(self, playerId):
        try:
            itemComp = CF.CreateItem(playerId)
            posType = serverApi.GetMinecraftEnum().ItemPosType.CARRIED
            remaining = int(itemComp.GetItemDurability(posType, 0))
            if remaining <= 0:
                return False
            return itemComp.SetItemDurability(
                posType, 0, remaining - 1
            ) is not False
        except Exception:
            return False

    def _lifedrain_target(self, playerId):
        try:
            filters = {
                "any_of": [
                    {"test": "is_family", "subject": "other", "value": "mob"}
                ]
            }
            entities = CF.CreateGame(LEVEL_ID).GetEntitiesAround(
                playerId, 20, filters
            ) or []
        except Exception:
            entities = []
        playerPos = self._get_foot_pos(playerId)
        if playerPos is None:
            return None
        rotation = self._get_rotation(playerId)
        pitch = math.radians(float(rotation[0]))
        yaw = math.radians(float(rotation[1]))
        look = (
            -math.sin(yaw) * math.cos(pitch),
            -math.sin(pitch),
            math.cos(yaw) * math.cos(pitch),
        )
        origin = (
            float(playerPos[0]),
            float(playerPos[1]) + scepter_logic.PLAYER_PROJECTILE_EYE_HEIGHT,
            float(playerPos[2]),
        )
        candidates = []
        for entityId in entities:
            if entityId == playerId:
                continue
            position = self._get_foot_pos(entityId)
            if position is None:
                continue
            try:
                visible = CF.CreateGame(LEVEL_ID).CanSee(
                    playerId, entityId, 20.0, True, 360.0, 360.0
                )
            except Exception:
                visible = False
            if not visible:
                continue
            candidates.append(
                (
                    entityId,
                    (
                        float(position[0]),
                        float(position[1]) + 0.75,
                        float(position[2]),
                    ),
                )
            )
        return scepter_logic.select_aimed_target(
            origin, look, candidates, 20.0
        )

    def _update_lifedrain_users(self):
        for playerId, state in list(self._lifedrain_users.items()):
            item = self._carried_item(playerId) or {}
            if portal_logic.item_name(item) != "tf_slice:lifedrain_scepter":
                self._lifedrain_users.pop(playerId, None)
                continue
            state["ticks"] = int(state.get("ticks", 0)) + 1
            targetId = self._lifedrain_target(playerId)
            if targetId is None:
                state["missTicks"] = int(state.get("missTicks", 0)) + 1
                if (
                    state["missTicks"]
                    >= scepter_logic.LIFEDRAIN_TARGET_LOSS_GRACE_TICKS
                ):
                    self._end_lifedrain(playerId, True)
                continue
            state["missTicks"] = 0
            if int(state["scepter"].get("charges", 0)) <= 0:
                self._end_lifedrain(playerId, True)
                continue
            result = scepter_logic.lifedrain_tick(
                state["scepter"], state["ticks"], True
            )
            if not result.get("used"):
                continue
            if not self._consume_carried_charge(playerId):
                self._end_lifedrain(playerId, True)
                continue
            self._recent_lifedrain_hits[targetId] = {
                "sourceId": playerId,
                "expires": self._tick + 1,
            }
            self._hurt(targetId, result["damage"], playerId)
            sourcePosition = self._get_foot_pos(playerId)
            targetPosition = self._get_foot_pos(targetId)
            dimensionId = self._get_dimension(playerId)
            if (
                sourcePosition is not None
                and targetPosition is not None
                and dimensionId is not None
            ):
                self._broadcast_lich_effect(
                    dimensionId,
                    "lifedrain_link",
                    (
                        (
                            sourcePosition[0],
                            sourcePosition[1] + 1.35,
                            sourcePosition[2],
                        ),
                        (
                            targetPosition[0],
                            targetPosition[1] + 0.75,
                            targetPosition[2],
                        ),
                    ),
                )
            if result.get("healing", 0.0) > 0.0:
                current = self._get_health(playerId, 20.0)
                self._set_health(playerId, min(20.0, current + result["healing"]))
                try:
                    CF.CreateCommand(LEVEL_ID).SetCommand(
                        "/effect @a[name=\"%s\"] saturation 1 0 true"
                        % str(playerId)
                    )
                except Exception:
                    pass
            try:
                CF.CreateEffect(targetId).AddEffectToEntity(
                    "slowness", 1, 2, True
                )
            except Exception:
                pass
        for targetId, hit in list(self._recent_lifedrain_hits.items()):
            if self._tick > int(hit.get("expires", -1)):
                self._recent_lifedrain_hits.pop(targetId, None)

    def _stop_lich_death_combat(self, bossId, state, force=False):
        """The 1-HP death actor must not retain Bedrock combat goals."""
        if force or not state.get("deathAiStopped"):
            stopped = self._trigger_entity_event(bossId, "tf_slice:begin_dying")
            state["deathAiStopped"] = stopped is True
        state["targetId"] = None
        state["meleeNavTarget"] = None
        state["meleeNavTick"] = -20
        self._reset_attack_target(bossId)
        # Native navigation can be active without a script navigation target.
        self._set_motion(bossId, 0.0, 0.0)

    def _begin_lich_death(self, bossId, state):
        if state.get("dead") or state.get("dying"):
            return False
        state["dying"] = True
        state["deathTime"] = 0
        state["health"] = 0.0
        state["targetId"] = None
        state["shieldStrength"] = 0
        lich_logic.cancel_scepter_cast(state)
        self._stop_lich_death_combat(bossId, state, True)
        self._discard_lich_clones(state)
        for minionId in list(state.get("minionIds", set())):
            minionKey = entity_registry_logic.matching_entity_key(
                self._lich_minions, minionId
            )
            if minionKey is not None:
                self._lich_minions.pop(minionKey, None)
            try:
                self.DestroyEntity(minionId)
            except Exception:
                pass
        state["minionIds"] = set()
        state["activeMinions"] = 0
        self._set_health(bossId, 1.0)
        position = self._get_foot_pos(bossId) or state.get("home")
        self._broadcast_lich_effect(
            state.get("dimensionId"), "death_start", (position,), bossId
        )
        self._save_lich_state(bossId, state)
        return True

    def _spawn_lich_experience(self, state, position):
        if position is None:
            return False
        try:
            return CF.CreateExp(LEVEL_ID).CreateExperienceOrb(
                lich_logic.XP_REWARD,
                tuple(float(value) for value in position),
                False,
            ) is not False
        except Exception as error:
            print "[TwilightBossSlice] Lich experience spawn failed:", error
            return False

    def _finalize_lich_death(self, bossId, state, destroyActor=True):
        if state.get("dead"):
            return False
        position = self._get_foot_pos(bossId) or state.get("home")
        if not state.get("lootAwarded"):
            landmarkDeath = lich_logic.landmark_death_is_authoritative(state)
            rewardAllowed = not landmarkDeath
            if self._ruin_worldgen is not None and landmarkDeath:
                self._ruin_worldgen.mark_boss_defeated(
                    state.get("home"), "lich"
                )
                rewardAllowed = self._ruin_worldgen.claim_boss_reward(
                    state.get("home"), "lich"
                )
            if rewardAllowed:
                self._place_lich_loot_chest(state)
                self._spawn_lich_experience(state, position)
            self._award_lich_progress(state)
            state["lootAwarded"] = True
        state["dying"] = False
        state["deathTime"] = lich_logic.DEATH_TICKS
        state["health"] = 0.0
        state["dead"] = True
        self._broadcast_lich_effect(
            state.get("dimensionId"), "death_burst", (position,), bossId
        )
        self._save_lich_state(bossId, state)
        if destroyActor:
            try:
                self.DestroyEntity(bossId)
            except Exception:
                return False
        return True

    def _lich_death_soul_position(self, state, position, deathTime):
        home = state.get("home")
        if position is None or home is None or int(deathTime) <= 70:
            return position
        source = (
            float(position[0]),
            float(position[1]) + 0.45,
            float(position[2]),
        )
        chest = (
            float(math.floor(home[0])),
            float(math.floor(home[1]) - 1),
            float(math.floor(home[2])),
        )
        progress = max(0.0, float(int(deathTime) - 70))
        fraction = min(progress / 70.0 * 1.25, 1.0)
        return tuple(
            source[index] + (chest[index] - source[index]) * fraction
            for index in range(3)
        )

    def _update_lich_death(self, bossId, state):
        self._stop_lich_death_combat(bossId, state)
        state["deathTime"] = max(0, int(state.get("deathTime", 0))) + 1
        deathTime = int(state["deathTime"])
        position = self._get_foot_pos(bossId) or state.get("home")
        self._set_health(bossId, 1.0)
        if deathTime <= 50:
            self._broadcast_lich_effect(
                state.get("dimensionId"),
                "death_smoke",
                (position,),
                bossId,
            )
            if deathTime % 17 == 0:
                self._broadcast_lich_effect(
                    state.get("dimensionId"),
                    "death_bone_burst",
                    (position,),
                    bossId,
                )
            if deathTime == 50:
                self._play_world_sound(
                    "mob.blaze.death", position, 1.0, 1.0
                )
                self._broadcast_lich_effect(
                    state.get("dimensionId"),
                    "death_first_burst",
                    (position,),
                    bossId,
                )
        elif deathTime == 70:
            self._broadcast_lich_effect(
                state.get("dimensionId"),
                "death_mid_burst",
                (position,),
                bossId,
            )
        elif deathTime > 70:
            soulPosition = self._lich_death_soul_position(
                state, position, deathTime
            )
            self._broadcast_lich_effect(
                state.get("dimensionId"),
                "death_flame",
                (soulPosition,),
                bossId,
            )
        if deathTime >= lich_logic.DEATH_TICKS:
            return self._finalize_lich_death(bossId, state)
        if deathTime % 20 == 0:
            self._save_lich_state(bossId, state)
        return True

    def _place_lich_loot_chest(self, state):
        home = state.get("home")
        if home is None:
            return False
        position = (home[0], math.floor(home[1]) - 1, home[2])
        return self._queue_loot_reward(
            state, "lich", position, config.LICH_LOOT_TABLE,
            reward_delivery.bonus_items("lich", state.get("lastLootingLevel", 0), random),
        )

    def _award_lich_progress(self, state):
        home = state.get("home")
        if home is None:
            return
        participantIds = set(str(value) for value in state.get("participants", ()))
        for playerId in self._get_online_players():
            if str(playerId) not in participantIds:
                continue
            if self._grant_progress(playerId, "tf_lich_defeated"):
                self._notify(
                    playerId,
                    u"\u8fdb\u5ea6\u5df2\u89e3\u9501\uff1a\u5de8\u5854\u5deb\u5996",
                    "GOLD",
                )

    def _make_sync_packet(self, playerId=None):
        bosses = []
        viewerPosition = (
            self._get_foot_pos(playerId) if playerId is not None else None
        )
        viewerDimension = (
            self._get_dimension(playerId) if playerId is not None else None
        )
        def _append_boss(
            payload,
            position,
            visibilityPositions=None,
            maxDistance=None,
        ):
            syncPosition = None
            if position is not None:
                try:
                    syncPosition = [
                        float(position[index]) for index in range(3)
                    ]
                except (IndexError, TypeError, ValueError):
                    syncPosition = None
            anchors = list(visibilityPositions or (syncPosition,))
            decisions = [
                boss_hud_logic.server_visibility_decision(
                    anchor,
                    payload.get("dimensionId"),
                    viewerPosition,
                    viewerDimension,
                    (
                        config.BOSS_HUD_RANGE
                        if maxDistance is None else maxDistance
                    ),
                )
                for anchor in anchors
            ]
            visibleDistances = [
                distance
                for visible, distance in decisions
                if visible is True and distance is not None
            ]
            knownDistances = [
                distance
                for unusedVisible, distance in decisions
                if distance is not None
            ]
            if visibleDistances:
                hudVisible = True
                distanceSquared = min(visibleDistances)
                visibilityReason = "encounter_range"
            elif decisions and all(
                visible is False for visible, unusedDistance in decisions
            ):
                hudVisible = False
                distanceSquared = (
                    min(knownDistances) if knownDistances else None
                )
                visibilityReason = "dimension_or_range"
            else:
                hudVisible = None
                distanceSquared = (
                    min(knownDistances) if knownDistances else None
                )
                visibilityReason = "viewer_context_unavailable"
            payload["position"] = syncPosition
            payload["hudVisible"] = hudVisible
            payload["hudDistanceSquared"] = distanceSquared
            payload["hudVisibilityReason"] = visibilityReason
            bosses.append(payload)

        for bossId, state in self._bosses.items():
            if state.get("dead"):
                continue
            position = self._get_foot_pos(bossId)
            if position is not None:
                try:
                    position = [float(position[index]) for index in range(3)]
                except (IndexError, TypeError, ValueError):
                    position = None
            _append_boss(
                {
                    "id": str(bossId),
                    "kind": "naga",
                    "name": u"\u5a1c\u8fe6",
                    "health": round(
                        0.0 if state.get("dying") else float(state["health"]),
                        2,
                    ),
                    "maxHealth": float(state["maxHealth"]),
                    "state": STATE_IDS.get(state["brain"].state, 0),
                    "segments": int(state["segments"]),
                    "dying": bool(state.get("dying")),
                    "deathTime": int(state.get("deathTime", 0)),
                    "dimensionId": int(state["dimensionId"]),
                    "position": position,
                },
                position,
            )
        for bossId, state in self._lich_bosses.items():
            if state.get("dead"):
                continue
            position = self._get_foot_pos(bossId)
            if position is not None:
                try:
                    position = [float(position[index]) for index in range(3)]
                except (IndexError, TypeError, ValueError):
                    position = None
            _append_boss(
                {
                    "id": str(bossId),
                    "kind": "lich",
                    "name": self._lich_display_name(bossId),
                    "health": round(float(state["health"]), 2),
                    "maxHealth": float(state["maxHealth"]),
                    "phase": int(state.get("phase", 1)),
                    "shieldStrength": int(
                        state.get("shieldStrength", 0)
                    ),
                    "minionsRemaining": int(
                        state.get("minionsRemaining", 0)
                    ),
                    "attackCooldown": int(
                        state.get("attackCooldown", 0)
                    ),
                    "nextAttackType": int(
                        state.get("nextAttackType", 0)
                    ),
                    "dimensionId": int(state["dimensionId"]),
                    "position": position,
                },
                position,
            )
        for hydraId, state in self._hydras.items():
            if state.get("dead"):
                continue
            position = self._get_foot_pos(hydraId)
            _append_boss(
                {
                    "id": str(hydraId),
                    "kind": "hydra",
                    "name": u"\u4e5d\u5934\u86c7",
                    "health": round(float(state.get("health", 0.0)), 2),
                    "maxHealth": hydra_logic.MAX_HEALTH,
                    "dying": bool(state.get("dying")),
                    "deathTime": int(state.get("deathTicks", 0)),
                    "dimensionId": int(state["dimensionId"]),
                    "position": position,
                    "heads": [
                        {
                            "state": str(head.get("state", "dead")),
                            "ticks": int(head.get("ticks", 0)),
                            "yaw": round(float(head.get("yaw", 0.0)), 2),
                            "pitch": round(float(head.get("pitch", 0.0)), 2),
                            "alive": bool(head.get("alive", False)),
                        }
                        for head in state.get("heads", ())
                    ],
                },
                position,
            )
        knightGroups = (
            self._ruin_worldgen.active_knight_groups()
            if self._ruin_worldgen is not None else ()
        )
        for group in knightGroups:
            if not knight_route_logic.boss_bar_visible(group):
                continue
            home = group.get("home") or None
            _append_boss(
                {
                    "id": "knight_group:%s" % group.get("groupId", ""),
                    "kind": "knight_phantoms",
                    "name": u"\u5e7b\u5f71\u9a91\u58eb",
                    "health": round(knight_route_logic.combined_health(group), 2),
                    "maxHealth": knight_route_logic.combined_max_health(group),
                    "membersAlive": knight_route_logic.combat_member_count(group),
                    "dimensionId": config.DIMENSION_ID,
                    "position": home,
                },
                home,
            )
        for bossId, state in self._ur_ghasts.items():
            if state.get("rewardClaimed"):
                continue
            position = self._get_foot_pos(bossId) or state.get("home")
            _append_boss(
                {
                    "id": str(bossId),
                    "kind": "ur_ghast",
                    "name": u"\u66ae\u8272\u6076\u9b42",
                    "health": round(
                        0.0
                        if state.get("dying")
                        else max(1.0, float(state.get("health", 1.0))),
                        2,
                    ),
                    "maxHealth": ur_ghast_logic.MAX_HEALTH,
                    "phaseName": str(state.get("phase", "normal")),
                    "dying": bool(state.get("dying")),
                    "deathTime": int(state.get("deathTicks", 0)),
                    "dimensionId": int(state.get("dimensionId", config.DIMENSION_ID)),
                    "position": position,
                },
                position,
                (position, state.get("home")),
                config.UR_GHAST_HUD_RANGE,
            )
        for bossId, state in self._route_mobs.items():
            if state.get("type") != MINOSHROOM_IDENTIFIER:
                continue
            position = self._get_foot_pos(bossId)
            if position is None:
                continue
            _append_boss(
                {
                    "id": str(bossId),
                    "kind": "minoshroom",
                    "name": u"\u7c73\u8bfa\u83c7",
                    "health": round(
                        self._get_health(bossId, minotaur_logic.MINOSHROOM_HEALTH), 2
                    ),
                    "maxHealth": minotaur_logic.MINOSHROOM_HEALTH,
                    "dimensionId": int(state["dimensionId"]),
                    "position": position,
                },
                position,
            )
        bosses.sort(key=lambda item: item["id"])
        return {
            "seq": self._sequence,
            "serverTick": self._tick,
            "urGhastLogicTick": self._ur_ghast_logic_tick,
            "bosses": bosses,
        }

    def _broadcast_sync(self):
        self._sequence += 1
        for playerId in self._get_online_players():
            self.NotifyToClient(
                playerId,
                "BossSync",
                self._make_sync_packet(playerId),
            )

    def _make_perf_packet(self):
        clients = {}
        for playerId, ack in self._client_acks.items():
            clients[str(playerId)] = {
                "seq": int(ack.get("seq", 0)),
                "ackLagTicks": max(
                    0, self._tick - int(ack.get("serverTick", 0))
                ),
            }
        return {
            "serverTick": self._tick,
            "activeBosses": self._active_boss_count(),
            "targetedBosses": sum(
                1 for state in self._bosses.values()
                if state.get("targetId") is not None
            ),
            "navigatingBosses": sum(
                1 for state in self._bosses.values()
                if state.get("navDestination") is not None
            ),
            "navigationResults": dict(
                (
                    str(bossId),
                    state.get("navResult"),
                )
                for bossId, state in self._bosses.items()
            ),
            "avgMs": self._last_perf["avgMs"],
            "maxMs": self._last_perf["maxMs"],
            "p95Ms": self._last_perf.get("p95Ms", 0.0),
            "p99Ms": self._last_perf.get("p99Ms", 0.0),
            "sampleCount": self._last_perf["sampleCount"],
            "urGhastLogicTick": self._ur_ghast_logic_tick,
            "urGhastCount": len(self._ur_ghasts),
            "urGhastProjectileCount": len(self._ur_ghast_projectiles),
            "activeGhastTrapCount": sum(
                1 for trap in self._ghast_traps.values()
                if trap.get("active")
            ),
            "bossMiniGhastCount": sum(
                1 for state in self._phantom_urghast_mobs.values()
                if state.get("type") == MINI_GHAST_IDENTIFIER
                and state.get("bossMinion")
            ),
            "aiIntervalTicks": config.AI_INTERVAL_TICKS,
            "syncIntervalTicks": config.SYNC_INTERVAL_TICKS,
            "clients": clients,
        }

    def _finish_perf_window(self):
        if self._samples_ms:
            orderedSamples = sorted(self._samples_ms)
            sampleCount = len(orderedSamples)
            p95Index = max(0, int(math.ceil(sampleCount * 0.95)) - 1)
            p99Index = max(0, int(math.ceil(sampleCount * 0.99)) - 1)
            self._last_perf = {
                "avgMs": round(
                    sum(self._samples_ms) / len(self._samples_ms), 4
                ),
                "maxMs": round(max(self._samples_ms), 4),
                "p95Ms": round(orderedSamples[p95Index], 4),
                "p99Ms": round(orderedSamples[p99Index], 4),
                "sampleCount": sampleCount,
            }
        self._samples_ms = []
        self.BroadcastToAllClient("PerfSync", self._make_perf_packet())

    def Update(self):
        started = time.time()
        self._tick += 1
        self._item_effects.tick()
        self._flush_reward_deliveries()
        self._purge_orphaned_ur_ghast_trophy_visuals()
        sourceClock = ur_ghast_logic.advance_source_clock(
            self._ur_ghast_logic_clock_remainder
        )
        self._ur_ghast_logic_clock_remainder = sourceClock["remainder"]
        self._ur_ghast_logic_step = bool(sourceClock["steps"])
        if self._ur_ghast_logic_step:
            self._ur_ghast_logic_tick += int(sourceClock["steps"])
        self._purge_pending_naga_spawns()
        self._process_leaf_decay_queue()
        self._discover_small_entity_runtime()
        self._process_portal_catalysts()
        self._process_quest_ram_offerings()
        self._update_tiny_birds()
        self._update_penguins()
        self._process_portal_fire_cleanups()
        self._process_portal_recovery_players()
        self._process_portal_arrivals()
        self._process_portal_background_preloads()
        self._update_ruin_mobs()
        self._drive_slime_projectiles()
        self._drive_route_mobs()
        if self._ur_ghast_logic_step:
            for trap in self._ghast_traps.values():
                trap["_effectTargets"] = []
        self._drive_phantom_urghast_mobs(self._ur_ghast_logic_step)
        self._drive_hydras()
        self._drive_knight_phantoms()
        self._drive_knight_projectile_rotations()
        self._drive_block_chain_projectiles()
        if self._ur_ghast_logic_step:
            try:
                self._drive_ur_ghasts()
            except Exception as error:
                self._entry_trace(
                    "ur_ghast.source_tick_error",
                    errorType=type(error).__name__,
                    errorMessage=str(error),
                    logicTick=int(self._ur_ghast_logic_tick),
                    bossCount=len(self._ur_ghasts),
                )
            finally:
                self._update_ur_ghast_native_weather()
            self._drive_ur_ghast_projectiles()
            self._update_ghast_traps()
        self._apply_ur_ghast_engine_motion()
        self._update_hydra_mortars()
        self._update_fire_swamp_devices()
        self._update_dark_tower_mechanisms()
        self._update_route_progression_penalties()
        self._drive_lich_bosses()
        self._update_lich_dependents()
        self._update_lich_projectiles()
        self._update_fortification_shields()
        self._update_lifedrain_users()
        if (
            self._lily_pad_worldgen is not None
            and not self._dimension_change_in_progress
        ):
            self._lily_pad_worldgen.tick()
        if (
            self._ruin_worldgen is not None
            or self._mushroom_worldgen is not None
            or self._enchanted_tree_worldgen is not None
        ):
            ruinPlayers = self._ruin_player_snapshots()
            if self._ruin_worldgen is not None:
                self._ruin_worldgen.tick(
                    self._tick,
                    ruinPlayers,
                    boss_spawning_enabled=(self._difficulty() > 0),
                )
                for playerId in self._ruin_worldgen.blocked_lich_activators(
                    ruinPlayers
                ):
                    if (
                        playerId is not None
                        and self._progress_notice_cooldowns.get(playerId, 0)
                        <= self._tick
                    ):
                        self._progress_notice_cooldowns[playerId] = (
                            self._tick + 100
                        )
                        self._notify(
                            playerId,
                            u"\u5deb\u5996\u62d2\u7edd\u4e86\u4f60\u7684\u6311\u6218\uff1a\u8bf7\u5148\u51fb\u8d25\u5a1c\u8fe6\u3002",
                            "PURPLE",
                        )
            if self._mushroom_worldgen is not None:
                self._mushroom_worldgen.tick(self._tick, ruinPlayers)
            if self._enchanted_tree_worldgen is not None:
                self._enchanted_tree_worldgen.tick(self._tick, ruinPlayers)
        if self._tick % config.MAGIC_MAP_SCAN_INTERVAL_TICKS == 0:
            self._tick_cached_magic_map_discovery()
        if (
            self._tick
            % config.MAGIC_MAP_ITEM_RECONCILE_INTERVAL_TICKS
            == 0
        ):
            self._scan_carried_magic_maps()
        if (
            self._magic_map_dirty
            and self._tick % config.MAGIC_MAP_SAVE_INTERVAL_TICKS == 0
        ):
            self._persist_magic_map_records()
        if (
            self._maze_map_dirty
            and self._tick % config.MAGIC_MAP_SAVE_INTERVAL_TICKS == 0
        ):
            self._persist_maze_map_records()
        if (
            self._leaf_decay_state_dirty
            and self._tick % config.LEAF_DECAY_SAVE_INTERVAL_TICKS == 0
        ):
            self._persist_leaf_decay_state()
        self._discover_bosses()
        self._advance_timed_states()
        if self._tick % config.AI_INTERVAL_TICKS == 0:
            self._drive_bosses()
        self._update_boss_segments()
        if (
            self._boss_sync_dirty
            or self._tick % config.SYNC_INTERVAL_TICKS == 0
        ):
            self._boss_sync_dirty = False
            self._broadcast_sync()
        elapsedMs = (time.time() - started) * 1000.0
        self._samples_ms.append(elapsedMs)
        if len(self._samples_ms) > config.MAX_SAMPLE_COUNT:
            self._samples_ms.pop(0)
        if self._tick % config.PERF_INTERVAL_TICKS == 0:
            self._finish_perf_window()

    def OnServerChatEvent(self, args):
        playerId = args.get("playerId")
        self._entry_trace(
            "chat.received",
            playerId=playerId,
            rawMessage=args.get("message", ""),
            messageType=type(args.get("message", "")).__name__,
        )
        message = str(args.get("message", "")).strip()
        if not message.startswith("!slice"):
            return
        args["cancel"] = True
        parts = message.split()
        command = parts[1].lower() if len(parts) > 1 else "help"
        self._entry_trace(
            "chat.slice_command",
            playerId=playerId,
            command=command,
            parts=parts,
        )
        if command == "enter":
            self._enter_slice(playerId)
        elif command == "return":
            self._return_from_slice(playerId)
        elif command == "boss":
            self._spawn_boss(playerId)
        elif command == "burst":
            requested = 4
            if len(parts) > 2:
                try:
                    requested = int(parts[2])
                except ValueError:
                    requested = 4
            self._burst(playerId, requested)
        elif command == "perf":
            self._notify(
                playerId, "Slice perf: %s" % self._make_perf_packet(), "AQUA"
            )
        elif command == "ruin":
            # Developer surface:
            # list | locate <id> [radius] | place | status | failed | near
            # | grid
            subcommand = parts[2].lower() if len(parts) > 2 else "status"
            if self._ruin_worldgen is None:
                self._notify(
                    playerId,
                    "Ruin worldgen is unavailable; check the server log.",
                    "RED",
                )
            elif subcommand == "list":
                # !slice ruin list
                self._notify_lines(
                    playerId,
                    chat_command_logic.paginate_catalog(
                        "Ruins",
                        self._ruin_worldgen.debug_list(),
                    ),
                    "AQUA",
                )
            elif subcommand == "status":
                # !slice ruin status
                self._notify(
                    playerId,
                    "Ruin status: %s" % self._ruin_worldgen.debug_status(),
                    "AQUA",
                )
            elif subcommand == "failed":
                # !slice ruin failed
                self._notify(
                    playerId,
                    "Failed ruins: %s"
                    % self._ruin_worldgen.debug_status().get(
                        "failedJobs",
                        [],
                    ),
                    "YELLOW",
                )
            elif subcommand == "near":
                # !slice ruin near [radius]
                position = self._get_foot_pos(playerId)
                radius = parts[3] if len(parts) > 3 else 256
                self._notify(
                    playerId,
                    "Nearby ruins: %s"
                    % self._ruin_worldgen.debug_near(position, radius),
                    "YELLOW",
                )
            elif subcommand == "grid":
                # !slice ruin grid
                position = self._get_foot_pos(playerId)
                self._notify(
                    playerId,
                    "Landmark grid: %s"
                    % self._ruin_worldgen.debug_grid(position),
                    "YELLOW",
                )
            elif subcommand == "locate" and len(parts) > 3:
                # !slice ruin locate <id> [radius]
                position = self._get_foot_pos(playerId)
                if (
                    position is None
                    or self._get_dimension(playerId) != config.DIMENSION_ID
                ):
                    self._notify(
                        playerId,
                        "Enter the Twilight dimension before locating a ruin.",
                        "YELLOW",
                    )
                else:
                    radius = (
                        parts[4]
                        if len(parts) > 4
                        else DEFAULT_LOCATE_RADIUS
                    )
                    succeeded, detail = chat_command_logic.safe_debug_locate(
                        self._ruin_worldgen.debug_locate,
                        parts[3].lower(),
                        position,
                        radius,
                    )
                    if succeeded:
                        target = detail["position"]
                        self._notify(
                            playerId,
                            (
                                "Ruin located: %s at %d %d %d "
                                "(%d blocks, %s)"
                            )
                            % (
                                detail["id"],
                                target[0],
                                target[1],
                                target[2],
                                detail["distance"],
                                detail["source"],
                            ),
                            "GREEN",
                        )
                    else:
                        self._notify(
                            playerId,
                            "Ruin locate: %s" % detail,
                            "YELLOW",
                        )
            elif subcommand == "place" and len(parts) > 3:
                # !slice ruin place <id>
                position = self._get_foot_pos(playerId)
                if (
                    position is None
                    or self._get_dimension(playerId) != config.DIMENSION_ID
                ):
                    self._notify(
                        playerId,
                        "Enter the Twilight dimension before placing a ruin.",
                        "YELLOW",
                    )
                else:
                    succeeded, detail = self._ruin_worldgen.debug_place(
                        parts[3].lower(),
                        position,
                    )
                    self._notify(
                        playerId,
                        "Ruin placement: %s" % detail,
                        "GREEN" if succeeded else "RED",
                    )
            else:
                self._notify(
                    playerId,
                    (
                        "!slice ruin list | locate <id> [radius] | "
                        "place <id> | status"
                    ),
                    "YELLOW",
                )
        else:
            self._notify(
                playerId,
                "!slice enter | boss | burst 4 | perf | return | ruin",
                "YELLOW",
            )

    def OnPlaceNeteaseStructureFeatureEvent(self, args):
        try:
            dimensionId = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            dimensionId = -1
        structureName = args.get(
            "structureName",
            args.get("featureName", args.get("identifier")),
        )
        if dimensionId == config.DIMENSION_ID:
            self._worldgen_perf_record_structure(structureName)
        transitioningPlayers = getattr(
            self,
            "_dimension_change_in_progress",
            set(),
        )
        directEntryActive = any(
            bool(
                getattr(self, "_pending_portal_entries", {}).get(
                    transitioningPlayer,
                    {},
                ).get("directEntry")
            )
            for transitioningPlayer in transitioningPlayers
        )
        if (
            dimensionId == config.DIMENSION_ID
            and transitioningPlayers
            and not directEntryActive
        ):
            # The staging-area feature rules prevent this path during a normal
            # entry. If an engine build still reports one, do not mutate the
            # worker-owned event dictionary: cancelling here was observed to
            # terminate the native process before Python could report a crash.
            structureEvents = getattr(
                self,
                "_entry_diag_structure_events",
                0,
            )
            if structureEvents < 16:
                self._entry_diag_structure_events = structureEvents + 1
                self._entry_trace(
                    "structure_feature.bypassed",
                    dimensionId=dimensionId,
                    structureName=args.get(
                        "structureName",
                        args.get(
                            "featureName",
                            args.get("identifier"),
                        ),
                    ),
                    position=args.get("position", args.get("pos")),
                    chunkPos=args.get("chunkPos"),
                )
            return
        structureName = str(structureName or "")
        if structureName == LILY_PAD_CANDIDATE:
            if self._lily_pad_worldgen is not None:
                self._lily_pad_worldgen.on_structure_feature_event(args)
            return
        if structureName.startswith("tf_slice:mushroom/canopy_trigger/"):
            if self._mushroom_worldgen is not None:
                self._mushroom_worldgen.on_structure_feature_event(args)
            return
        if structureName.startswith("tf_slice:enchanted/tree_trigger/"):
            if self._enchanted_tree_worldgen is not None:
                self._enchanted_tree_worldgen.on_structure_feature_event(
                    args
                )
            return
        if self._ruin_worldgen is not None:
            self._ruin_worldgen.on_structure_feature_event(args)

    def _ruin_player_snapshots(self):
        players = []
        for playerId in self._get_online_players():
            if playerId in getattr(
                self,
                "_dimension_change_in_progress",
                set(),
            ):
                continue
            position = self._get_foot_pos(playerId)
            dimensionId = self._get_dimension(playerId)
            if position is None or dimensionId is None:
                continue
            readyTick = getattr(
                self,
                "_dimension_worldgen_ready_ticks",
                {},
            ).get(playerId)
            if (
                dimensionId == config.DIMENSION_ID
                and readyTick is not None
                and self._tick < readyTick
            ):
                continue
            players.append(
                {
                    "playerId": playerId,
                    "position": position,
                    "dimensionId": dimensionId,
                    "progress": copy.deepcopy(
                        self._progress_for_player(playerId)
                    ),
                }
            )
        return players

    def _ur_ghast_trophy_visual_ids(self, position, dimensionId):
        start = (
            float(position[0]) - 0.25,
            float(position[1]) - 1.0,
            float(position[2]) - 0.25,
        )
        end = (
            float(position[0]) + 1.25,
            float(position[1]) + 2.0,
            float(position[2]) + 1.25,
        )
        try:
            candidates = CF.CreateGame(LEVEL_ID).GetEntitiesInSquareArea(
                None, start, end, int(dimensionId)
            ) or ()
        except Exception:
            candidates = ()
        return [
            entityId
            for entityId in candidates
            if self._is_ur_ghast_trophy_visual(entityId)
        ]

    def _is_ur_ghast_trophy_visual(self, entityId):
        if self._get_engine_type(entityId) == UR_GHAST_TROPHY_VISUAL:
            return True
        try:
            families = CF.CreateAttr(entityId).GetTypeFamily() or ()
            return "ur_ghast_trophy_visual" in families
        except Exception:
            return False

    @staticmethod
    def _ur_ghast_trophy_visual_yaw(blockName, states):
        if blockName.endswith("_wall_trophy"):
            return public_block_logic.ur_ghast_trophy_entity_yaw(
                public_block_logic.wall_trophy_visual_yaw(
                    public_block_logic.effective_trophy_facing(states)
                )
            )
        return public_block_logic.ur_ghast_trophy_entity_yaw(
            public_block_logic.floor_trophy_visual_yaw(
                public_block_logic.effective_trophy_rotation(states)
            )
        )

    def _ensure_ur_ghast_trophy_visual(self, args):
        blockName = str(args.get("blockName", args.get("fullName", "")))
        if blockName not in UR_GHAST_TROPHY_BLOCKS:
            return False
        position = self._block_event_position(args)
        if position is None:
            return False
        dimensionId = int(
            args.get("dimensionId", args.get("dimension", config.DIMENSION_ID))
        )
        key = (int(dimensionId),) + tuple(position)
        visualId = self._ur_ghast_trophy_visuals.get(key)
        if not self._valid_entity_id(visualId) or self._get_foot_pos(visualId) is None:
            visualIds = self._ur_ghast_trophy_visual_ids(position, dimensionId)
            visualId = visualIds[0] if visualIds else None
            for duplicateId in visualIds[1:]:
                self.DestroyEntity(duplicateId)
        states = {}
        try:
            if self._block_state_comp is not None:
                states = self._block_state_comp.GetBlockStates(
                    position, dimensionId
                ) or {}
        except Exception:
            states = {}
        yaw = self._ur_ghast_trophy_visual_yaw(blockName, states)
        if visualId is None:
            visualId = self._spawn_ruin_entity(
                UR_GHAST_TROPHY_VISUAL,
                (
                    float(position[0]) + 0.5,
                    float(position[1]),
                    float(position[2]) + 0.5,
                ),
                yaw,
                dimensionId,
            )
            if visualId is None:
                return False
        self._ur_ghast_trophy_visuals[key] = visualId
        try:
            CF.CreateRot(visualId).SetRot((0.0, yaw))
        except Exception:
            pass
        return True

    def _register_ur_ghast_trophy_visual(self, entityId, dimensionId):
        position = self._get_foot_pos(entityId)
        if position is None:
            self.DestroyEntity(entityId)
            return False
        blockPosition = tuple(int(math.floor(value)) for value in position)
        blockName = self._block_name(
            self._get_block(blockPosition, int(dimensionId))
        )
        if blockName not in UR_GHAST_TROPHY_BLOCKS:
            self.DestroyEntity(entityId)
            return False
        key = (int(dimensionId),) + blockPosition
        existingId = self._ur_ghast_trophy_visuals.get(key)
        if (
            self._valid_entity_id(existingId)
            and existingId != entityId
            and self._get_foot_pos(existingId) is not None
        ):
            self.DestroyEntity(entityId)
            return False
        self._ur_ghast_trophy_visuals[key] = entityId
        return True

    def _remove_ur_ghast_trophy_visuals(self, position, dimensionId):
        key = (int(dimensionId),) + tuple(position)
        visualIds = set(self._ur_ghast_trophy_visual_ids(position, dimensionId))
        cached = self._ur_ghast_trophy_visuals.pop(key, None)
        if cached is not None:
            visualIds.add(cached)
        for visualId in visualIds:
            try:
                self.DestroyEntity(visualId)
            except Exception:
                pass
        return len(visualIds)

    def _broadcast_trophy_break_effect(self, position, dimensionId):
        self.BroadcastToAllClient(
            "TrophyBreakEffect",
            {
                "x": int(position[0]),
                "y": int(position[1]),
                "z": int(position[2]),
                "dimensionId": int(dimensionId),
            },
        )
        self._play_world_sound("dig.stone", position, 0.8, 1.2)

    def _purge_orphaned_ur_ghast_trophy_visuals(self):
        if self._tick % 10:
            return 0
        removed = 0
        for key, visualId in list(self._ur_ghast_trophy_visuals.items()):
            dimensionId, xValue, yValue, zValue = key
            blockName = self._block_name(
                self._get_block(
                    (xValue, yValue, zValue),
                    int(dimensionId),
                )
            )
            if (
                blockName in UR_GHAST_TROPHY_BLOCKS
                and self._valid_entity_id(visualId)
                and self._get_foot_pos(visualId) is not None
            ):
                continue
            self._ur_ghast_trophy_visuals.pop(key, None)
            if visualId is not None:
                try:
                    self.DestroyEntity(visualId)
                except Exception:
                    pass
            removed += 1
        return removed

    def OnNagaSpawnerBlockEntityTick(self, args):
        if self._ensure_ur_ghast_trophy_visual(args):
            return
        self._tick_dark_tower_block_entity(args)
        if self._ruin_worldgen is None:
            return
        if self._difficulty() <= 0:
            return
        self._ruin_worldgen.on_courtyard_spawner_tick(
            args,
            self._ruin_player_snapshots(),
            self._tick,
        )

    def OnChunkGeneratedServerEvent(self, args):
        try:
            dimensionId = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            dimensionId = -1
        if dimensionId == config.DIMENSION_ID:
            self._worldgen_perf_increment("chunkGenerated")
        if self._ruin_worldgen is not None:
            self._ruin_worldgen.on_chunk_generated_event(args)

    def OnChunkLoadedServerEvent(self, args):
        try:
            dimensionId = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            dimensionId = -1
        if dimensionId == config.DIMENSION_ID:
            self._worldgen_perf_increment("chunkLoaded")
        if self._ruin_worldgen is not None:
            self._ruin_worldgen.on_chunk_loaded_event(args)

    def _remember_ur_ghast_projectile_hit(self, args):
        targetId = args.get("targetId")
        if entity_registry_logic.matching_entity_key(
            self._ur_ghasts, targetId
        ) is None:
            return False
        for key in (
            "ownerId",
            "shooterId",
            "sourceId",
            "srcId",
            "attackerId",
        ):
            ownerId = args.get(key)
            if not self._is_online_player(ownerId):
                continue
            remembered = self._remember_ur_ghast_player_attack(
                targetId, ownerId
            )
            self._entry_trace(
                "ur_ghast.ranged_contact",
                bossId=str(targetId),
                playerId=str(ownerId),
                ownerField=key,
                projectileId=args.get("id"),
                remembered=bool(remembered),
            )
            return remembered
        return False

    def _recover_ur_ghast_fireball_reflector(self, projectileId):
        projectileKey = entity_registry_logic.matching_entity_key(
            self._ur_ghast_projectiles, projectileId
        )
        projectile = self._ur_ghast_projectiles.get(projectileKey) or {}
        projectilePosition = self._get_foot_pos(projectileKey)
        projectileMotion = projectile.get("velocity")
        projectileDimension = self._get_dimension(projectileKey)
        if (
            projectilePosition is None
            or projectileMotion is None
            or projectileDimension is None
        ):
            return None
        bestScore = 0.0
        bestPlayerId = None
        for playerId in self._get_online_players():
            if self._get_dimension(playerId) != projectileDimension:
                continue
            playerPosition = self._get_foot_pos(playerId)
            if playerPosition is None:
                continue
            playerEye = (
                float(playerPosition[0]),
                float(playerPosition[1]) + 1.62,
                float(playerPosition[2]),
            )
            pitch, yaw = self._get_rotation(playerId)
            pitch = math.radians(float(pitch))
            yaw = math.radians(float(yaw))
            playerLook = (
                -math.sin(yaw) * math.cos(pitch),
                -math.sin(pitch),
                math.cos(yaw) * math.cos(pitch),
            )
            score = ur_ghast_logic.reflection_recovery_score(
                projectilePosition,
                projectileMotion,
                playerEye,
                playerLook,
            )
            if score is None or (bestPlayerId is not None and score <= bestScore):
                continue
            bestScore = float(score)
            bestPlayerId = playerId
        if bestPlayerId is None:
            return None
        self._entry_trace(
            "ur_ghast.fireball_reflector_recovered",
            projectileId=str(projectileKey),
            playerId=str(bestPlayerId),
            score=round(bestScore, 4),
        )
        return bestPlayerId

    def _protect_ur_ghast_fireball_health(self, args, entityId):
        projectileKey = entity_registry_logic.matching_entity_key(
            self._ur_ghast_projectiles, entityId
        )
        if projectileKey is None:
            return False
        try:
            fromValue = float(args.get("from", args.get("fromValue", 1.0)))
            toValue = float(args.get("to", args.get("toValue", fromValue)))
        except (TypeError, ValueError):
            fromValue, toValue = 1.0, 0.0
        if toValue >= fromValue:
            return False
        sourceId = args.get(
            "sourceId",
            args.get("srcId", args.get("attackerId")),
        )
        if self._is_online_player(sourceId):
            self._reflect_ur_ghast_fireball(
                entityId, sourceId, reason="health_change"
            )
        else:
            sourceId = self._recover_ur_ghast_fireball_reflector(entityId)
            if self._is_online_player(sourceId):
                self._reflect_ur_ghast_fireball(
                    entityId,
                    sourceId,
                    reason="health_change_recovered",
                )
        args["cancel"] = True
        self._set_health(projectileKey, ur_ghast_logic.FIREBALL_HEALTH)
        self._entry_trace(
            "ur_ghast.fireball_damage_ignored",
            projectileId=str(projectileKey),
            fromValue=fromValue,
            toValue=toValue,
            sourceId=(str(sourceId) if sourceId is not None else None),
        )
        return True

    def OnProjectileDoHitEffectEvent(self, args):
        self._remember_ur_ghast_projectile_hit(args)
        projectileId = args.get("id")
        projectileType = (
            args.get("engineTypeStr") or self._get_engine_type(projectileId)
        )
        if projectileType in (
            KNIGHT_AXE_PROJECTILE,
            KNIGHT_PICKAXE_PROJECTILE,
        ):
            projectileKey = entity_registry_logic.matching_entity_key(
                self._knight_projectiles, projectileId
            )
            targetId = args.get("targetId")
            targetType = (
                self._get_engine_type(targetId)
                if targetId is not None else None
            )
            friendlyHit = targetType == KNIGHT_PHANTOM_IDENTIFIER
            if friendlyHit:
                args["cancel"] = True
            if projectileKey is not None:
                self._discard_knight_projectile_tracking(
                    projectileKey, destroy=friendlyHit
                )
            elif friendlyHit:
                try:
                    self.DestroyEntity(projectileId)
                except Exception:
                    pass
            return
        if projectileType == UR_GHAST_FIREBALL_IDENTIFIER:
            projectileKey = entity_registry_logic.matching_entity_key(
                self._ur_ghast_projectiles, projectileId
            )
            if projectileKey is None:
                args["cancel"] = True
                self._entry_trace(
                    "ur_ghast.fireball_rejected",
                    projectileId=str(projectileId),
                    reason="missing_owner_record",
                )
                try:
                    self.DestroyEntity(projectileId)
                except Exception:
                    pass
                return
            projectile = self._ur_ghast_projectiles.get(projectileKey) or {}
            if projectile.get("removed"):
                args["cancel"] = True
                return
            targetId = args.get("targetId")
            targetType = (
                self._get_engine_type(targetId)
                if targetId is not None else None
            )
            targetProjectileKey = entity_registry_logic.matching_entity_key(
                self._ur_ghast_projectiles, targetId
            )
            targetIsProjectile = bool(
                targetProjectileKey is not None
                or targetType in (
                    UR_GHAST_FIREBALL_IDENTIFIER,
                    "minecraft:fireball",
                    "minecraft:small_fireball",
                )
            )
            decision = ur_ghast_logic.fireball_collision_decision(
                projectile, targetId, targetIsProjectile, self._tick
            )
            if decision != "impact":
                args["cancel"] = True
                contactKey = "%s:%s" % (decision, str(targetId))
                ignoredContacts = projectile.setdefault(
                    "ignoredContacts", []
                )
                if contactKey not in ignoredContacts:
                    ignoredContacts.append(contactKey)
                    self._entry_trace(
                        "ur_ghast.fireball_contact",
                        projectileId=str(projectileId),
                        targetId=(
                            str(targetId) if targetId is not None else None
                        ),
                        targetType=targetType,
                        ownerId=projectile.get("ownerId"),
                        bossId=projectile.get("bossId"),
                        reflected=bool(projectile.get("reflected", False)),
                        decision=decision,
                    )
                return
            args["cancel"] = True
            projectile["removed"] = True
            projectile["impactTick"] = int(self._tick)
            projectile["impactPosition"] = self._get_foot_pos(projectileId)
            if (
                str(args.get("hitTargetType", "")).upper() == "ENTITY"
                and targetId is not None
                and (
                    targetType not in (
                        UR_GHAST_IDENTIFIER,
                        MINI_GHAST_IDENTIFIER,
                        TOWER_GHAST_IDENTIFIER,
                    )
                    or (
                        targetType == UR_GHAST_IDENTIFIER
                        and projectile.get("reflected")
                    )
                )
            ):
                self._hurt(
                    targetId,
                    ur_ghast_logic.FIREBALL_DIRECT_DAMAGE,
                    projectile.get("ownerId"),
                )
            self._entry_trace(
                "ur_ghast.fireball_impact",
                projectileId=str(projectileId),
                targetId=(str(targetId) if targetId is not None else None),
                targetType=targetType,
                ownerId=projectile.get("ownerId"),
                bossId=projectile.get("bossId"),
                reflected=bool(projectile.get("reflected", False)),
                position=projectile.get("impactPosition"),
            )
            originalBossKey = entity_registry_logic.matching_entity_key(
                self._ur_ghasts, projectile.get("bossId")
            )
            if (
                originalBossKey is not None
                and projectile.get("impactPosition") is not None
            ):
                self._broadcast_ur_ghast_effect(
                    self._ur_ghasts[originalBossKey],
                    "fireball_impact",
                    (projectile["impactPosition"],),
                    originalBossKey,
                )
            if self._get_foot_pos(projectileId) is None:
                self._ur_ghast_projectiles.pop(projectileKey, None)
                return
            self._trigger_entity_event(projectileId, "tf_slice:explode")
            return
        chainKey = entity_registry_logic.matching_entity_key(
            self._block_chain_projectiles, projectileId
        )
        if chainKey is not None or projectileType == BLOCK_CHAIN_PROJECTILE:
            state = self._block_chain_projectiles.get(chainKey) or {}
            hitTargetType = str(args.get("hitTargetType", "")).upper()
            targetId = args.get("targetId")
            ownerId = state.get("ownerId")
            targetType = self._get_engine_type(targetId)
            canHitTarget = knight_route_logic.block_chain_can_hit_target(
                targetId, ownerId, targetType
            )
            if hitTargetType == "ENTITY" and not canHitTarget:
                args["cancel"] = True
                return
            self._break_block_chain_impact(args, state)
            if hitTargetType == "BLOCK":
                currentMotion = self._get_full_motion(projectileId)
                if currentMotion is None:
                    currentMotion = state.get("baseMotion", (0, 0, 0))
                bouncedMotion = knight_route_logic.block_chain_bounce_motion(
                    currentMotion,
                    args.get("hitFace", args.get("face", "")),
                )
                state["baseMotion"] = bouncedMotion
                self._set_full_motion(projectileId, bouncedMotion)
            elif hitTargetType == "ENTITY":
                state["returnAgeOffset"] = 60
            if (
                hitTargetType == "ENTITY"
                and canHitTarget
            ):
                if self._is_online_player(targetId) and self._is_blocking(
                    targetId
                ):
                    self._damage_shield(
                        targetId,
                        knight_route_logic.BLOCK_CHAIN_SHIELD_DAMAGE,
                    )
                    self._shield_cooldowns[targetId] = (
                        self._tick
                        + knight_route_logic.BLOCK_CHAIN_SHIELD_DISABLE_TICKS
                    )
                    self._stop_using_item(targetId)
                    self._knightmetal_shield_users.pop(str(targetId), None)
                    self._play_world_sound(
                        "item.shield.block",
                        self._get_foot_pos(targetId),
                        1.0,
                        1.0,
                    )
                self._hurt(
                    targetId,
                    knight_route_logic.BLOCK_CHAIN_DAMAGE,
                    ownerId,
                    "EntityAttack",
                )
                self._damage_block_and_chain(
                    ownerId,
                    knight_route_logic.BLOCK_CHAIN_ENTITY_DURABILITY_COST,
                )
            state["returning"] = True
            args["cancel"] = True
            return
        if projectileType == HYDRA_MORTAR_IDENTIFIER:
            mortarKey = entity_registry_logic.matching_entity_key(
                self._hydra_mortars, projectileId
            )
            mortar = self._hydra_mortars.get(mortarKey) or {}
            hitType = str(args.get("hitTargetType", "")).upper()
            targetId = args.get("targetId")
            if (
                hitType == "ENTITY"
                and self._hydra_owned_damage_source(
                    targetId, mortar.get("ownerId")
                )
                and not mortar.get("reflected")
            ):
                args["cancel"] = True
                return
            if hitType == "BLOCK" and not mortar.get("mega"):
                try:
                    motion = CF.CreateActorMotion(projectileId).GetMotion()
                except Exception:
                    motion = None
                if motion is None:
                    motion = (0.0, 0.0, 0.0)
                face = str(
                    args.get("hitFace", args.get("face", ""))
                ).upper()
                landing = face in ("1", "UP")
                if motion:
                    landing = landing or (
                        float(motion[1]) <= 0.0
                        and abs(float(motion[1]))
                        >= max(abs(float(motion[0])), abs(float(motion[2])))
                    )
                if landing:
                    args["cancel"] = True
                    mortar["landed"] = True
                    self._set_full_motion(
                        projectileId,
                        (float(motion[0]), 0.0, float(motion[2])),
                    )
                    self._trigger_entity_event(projectileId, "tf_slice:landed")
                    return
            self._detonate_hydra_mortar(projectileId)
            return
        if projectileType in (
            LICH_BOLT_IDENTIFIER,
            LICH_BOMB_IDENTIFIER,
            TOME_BOLT_IDENTIFIER,
            TWILIGHT_WAND_BOLT_IDENTIFIER,
        ):
            targetId = args.get("targetId")
            hitType = str(args.get("hitTargetType", "")).upper()
            projectileKey = entity_registry_logic.matching_entity_key(
                self._lich_projectiles, projectileId
            )
            projectile = self._lich_projectiles.get(projectileKey) or {}
            if hitType == "ENTITY" and targetId is not None:
                self._recent_lich_projectile_hits[targetId] = {
                    "projectileId": (
                        projectileKey
                        if projectileKey is not None
                        else projectileId
                    ),
                    "projectile": dict(projectile),
                    "expires": self._tick + 2,
                }
            if (
                hitType == "ENTITY"
                and projectileType in (
                    LICH_BOLT_IDENTIFIER,
                    LICH_BOMB_IDENTIFIER,
                )
                and targetId is not None
            ):
                targetType = self._get_engine_type(targetId)
                if (
                    projectileType == LICH_BOLT_IDENTIFIER
                    and targetType in (
                        LICH_CLONE_IDENTIFIER,
                        LICH_BOLT_IDENTIFIER,
                        LICH_BOMB_IDENTIFIER,
                    )
                ):
                    args["cancel"] = True
                elif (
                    projectileType == LICH_BOMB_IDENTIFIER
                    and targetType in (
                        LICH_IDENTIFIER,
                        LICH_CLONE_IDENTIFIER,
                        LICH_BOLT_IDENTIFIER,
                        LICH_BOMB_IDENTIFIER,
                    )
                ):
                    args["cancel"] = True
            if (
                projectileType == LICH_BOMB_IDENTIFIER
                and not args.get("cancel")
            ):
                # Some engine versions skip the JSON definition_event, so the
                # server mirrors the source bomb's immediate explosion here.
                self._trigger_entity_event(projectileId, "tf_slice:explode")
            if hitType == "ENTITY" and projectileType == TOME_BOLT_IDENTIFIER:
                slowTicks = lich_logic.death_tome_slow_ticks(
                    self._difficulty()
                )
                if targetId is not None and slowTicks > 0:
                    try:
                        CF.CreateEffect(targetId).AddEffectToEntity(
                            "slowness", int(math.ceil(slowTicks / 20.0)), 1, True
                        )
                    except Exception:
                        pass
            if (
                hitType == "ENTITY"
                and projectileType == TWILIGHT_WAND_BOLT_IDENTIFIER
            ):
                ownerId = projectile.get("ownerId")
                loyalKey = entity_registry_logic.matching_entity_key(
                    self._loyal_zombies, targetId
                )
                loyal = self._loyal_zombies.get(loyalKey) or {}
                if (
                    str(targetId) == str(ownerId)
                    or str(loyal.get("ownerId")) == str(ownerId)
                ):
                    args["cancel"] = True
            if args.get("cancel"):
                velocity = projectile.get("velocity")
                if velocity is not None:
                    try:
                        CF.CreateActorMotion(projectileId).SetMotion(
                            tuple(velocity)
                        )
                        projectile["stalledSince"] = None
                    except Exception:
                        pass
            elif projectileKey is not None:
                projectile["impactTick"] = int(self._tick)
                projectile["expires"] = min(
                    int(
                        projectile.get(
                            "expires",
                            self._tick + lich_logic.PROJECTILE_TTL_TICKS,
                        )
                    ),
                    self._tick + 2,
                )
            return
        slimeKey = entity_registry_logic.matching_entity_key(
            self._slime_projectiles, projectileId
        )
        if slimeKey is not None or projectileType == SLIME_BLOB_IDENTIFIER:
            projectile = self._slime_projectiles.pop(slimeKey, None) or {}
            position = (
                float(args.get("x", args.get("blockPosX", 0.0))),
                float(args.get("y", args.get("blockPosY", 0.0))),
                float(args.get("z", args.get("blockPosZ", 0.0))),
            )
            dimensionId = projectile.get("dimensionId")
            if dimensionId is None:
                dimensionId = self._get_dimension(projectileId)
            if dimensionId is None:
                dimensionId = config.DIMENSION_ID
            impact = []
            for unusedIndex in range(8):
                impact.append(
                    (
                        position[0] + random.gauss(0.0, 0.05),
                        position[1] + random.random() * 0.2,
                        position[2] + random.gauss(0.0, 0.05),
                    )
                )
            self._broadcast_beetle_effect(
                dimensionId, "slime_impact", impact
            )
            self._play_world_sound(
                "mob.slime.squish", position, 0.8, 1.1
            )
            return
        if projectileType != NATURE_BOLT_IDENTIFIER:
            return
        hitType = str(args.get("hitTargetType", "")).upper()
        if hitType == "ENTITY":
            targetId = args.get("targetId")
            if targetId is None or self._difficulty() == 0:
                return
            poisonSeconds = 7 if self._difficulty() == 3 else 3
            try:
                CF.CreateEffect(targetId).AddEffectToEntity(
                    "poison", poisonSeconds, 0, True
                )
            except Exception as error:
                print "[TwilightBossSlice] nature poison failed:", error
            return
        if hitType != "BLOCK" or not self._mob_griefing():
            return
        blockPos = (
            int(args.get("blockPosX", math.floor(args.get("x", 0)))),
            int(args.get("blockPosY", math.floor(args.get("y", 0)))),
            int(args.get("blockPosZ", math.floor(args.get("z", 0)))),
        )
        dimensionId = self._get_dimension(projectileId)
        if dimensionId is None:
            dimensionId = config.DIMENSION_ID
        block = self._get_block(blockPos, dimensionId) or {}
        if isinstance(block, dict):
            blockName = block.get("name", "")
            aux = int(block.get("aux", 0))
        else:
            blockName = block[0] if block else ""
            aux = int(block[1]) if len(block) > 1 else 0

        # Bedrock has no generic BonemealableBlock interface, so reproduce the
        # deterministic crop growth cases and the upstream leaf replacement.
        cropMax = {
            "minecraft:wheat": 7,
            "minecraft:carrots": 7,
            "minecraft:potatoes": 7,
            "minecraft:beetroot": 3,
        }
        if blockName in cropMax and aux < cropMax[blockName]:
            try:
                self._block_comp.SetBlockNew(
                    blockPos,
                    {
                        "name": blockName,
                        "aux": min(cropMax[blockName], aux + 2),
                    },
                    0,
                    dimensionId,
                    True,
                    False,
                )
            except Exception:
                pass
        elif "leaves" in blockName:
            self._set_block(blockPos, "minecraft:oak_leaves", dimensionId)

    def OnServerSpawnMob(self, args):
        biome_identifier = None
        try:
            biome_identifier = self._biome_comp.GetBiomeName(
                (
                    int(float(args.get("x", 0))),
                    int(float(args.get("y", 64))),
                    int(float(args.get("z", 0))),
                ),
                int(args.get("dimensionId", 0)),
            )
        except Exception:
            biome_identifier = None
        if spawn_policy.should_cancel_twilight_spawn(
            args,
            config.DIMENSION_ID,
            biome_identifier=biome_identifier,
        ):
            args["cancel"] = True
            return
        identifier = args.get("realIdentifier") or args.get("identifier")
        if identifier != config.BOSS_IDENTIFIER:
            if identifier != LICH_IDENTIFIER:
                return
        home = (
            float(args.get("x", 0.0)),
            float(args.get("y", 0.0)),
            float(args.get("z", 0.0)),
        )
        dimensionId = args.get("dimensionId", config.DIMENSION_ID)
        self._purge_pending_naga_spawns()
        if (
            self._active_boss_count() >= config.MAX_ACTIVE_BOSSES
            or (
                identifier == config.BOSS_IDENTIFIER
                and (
                    self._home_conflicts(home, dimensionId)
                    or self._pending_home_conflicts(home, dimensionId)
                )
            )
        ):
            args["cancel"] = True
            return
        if identifier == LICH_IDENTIFIER:
            return
        self._pending_naga_spawns.append(
            {
                "home": home,
                "dimensionId": dimensionId,
                "expires": self._tick + 5,
            }
        )

    def OnAddEntity(self, args):
        entityType = args.get("engineTypeStr")
        entityId = args.get("id", args.get("entityId"))
        dimensionId = args.get("dimensionId", config.DIMENSION_ID)
        if not entityType and entityId is not None:
            entityType = self._get_engine_type(entityId)
        if entityType == UR_GHAST_TROPHY_VISUAL:
            self._register_ur_ghast_trophy_visual(entityId, dimensionId)
            return
        if entityType in PHANTOM_UR_GHAST_MOB_IDENTIFIERS:
            self._register_phantom_urghast_mob(
                entityId, entityType, dimensionId
            )
            return
        if entityType == UR_GHAST_IDENTIFIER:
            self._register_ur_ghast(entityId, dimensionId)
            return
        if entityType == UR_GHAST_FIREBALL_IDENTIFIER:
            self._ur_ghast_projectiles.setdefault(
                str(entityId),
                {"ownerId": None, "dimensionId": int(dimensionId)},
            )
            return
        if entityType == SLIME_BLOB_IDENTIFIER:
            try:
                ownerId = CF.CreateBulletAttributes(
                    entityId
                ).GetSourceEntityId()
            except Exception:
                ownerId = None
            self._slime_projectiles[str(entityId)] = {
                "ownerId": str(ownerId) if ownerId is not None else None,
                "dimensionId": int(dimensionId),
            }
            position = self._get_foot_pos(entityId)
            if position is not None:
                self._play_world_sound(
                    "mob.slime.squish",
                    position,
                    1.0,
                    1.0 / (random.random() * 0.4 + 0.8),
                )
            return
        if entityType == KNIGHT_PHANTOM_IDENTIFIER:
            identity = (
                self._ruin_worldgen.bind_knight_member(entityId)
                if self._ruin_worldgen is not None
                else None
            )
            if identity is not None:
                self._knight_phantoms[str(entityId)] = identity
            role = int((identity or {}).get("number", 0)) % 3
            weapon = (
                "tf_slice:knightmetal_sword",
                "tf_slice:knightmetal_axe",
                "tf_slice:knightmetal_pickaxe",
            )[role]
            self._set_entity_carried_item(
                entityId,
                {
                    "newItemName": weapon,
                    "newAuxValue": 0,
                    "count": 1,
                },
            )
            return
        if entityType == HYDRA_IDENTIFIER:
            self._register_hydra(entityId, dimensionId)
            return
        if entityType == HYDRA_HEAD_IDENTIFIER:
            self._restore_hydra_head_owner(entityId)
            return
        if entityType == HYDRA_NECK_IDENTIFIER:
            return
        if entityType == HYDRA_PART_PROXY_IDENTIFIER:
            self._restore_hydra_part_owner(entityId)
            return
        if entityType == HYDRA_MORTAR_IDENTIFIER:
            self._set_entity_on_fire(entityId, 3600)
            self._hydra_mortars.setdefault(
                entityId,
                {
                    "ownerId": None,
                    "mega": False,
                    "fuse": 80,
                    "landed": False,
                    "reflected": False,
                    "dimensionId": int(dimensionId),
                },
            )
            return
        if entityType in (
            MINOTAUR_IDENTIFIER,
            MINOSHROOM_IDENTIFIER,
            MAZE_SLIME_IDENTIFIER,
        ):
            self._register_route_mob(entityId, entityType, dimensionId)
            return
        if entityType == TINY_BIRD_IDENTIFIER:
            self._register_tiny_bird(entityId, dimensionId)
        elif entityType == PENGUIN_IDENTIFIER:
            self._penguins.add(entityId)
        elif entityType in ITEM_ENTITY_IDENTIFIERS:
            self._pending_quest_offerings[entityId] = {
                "playerId": None,
                "expires": None,
            }
        if entityType in RUIN_MOB_IDENTIFIERS:
            state = {
                "type": entityType,
                "dimensionId": dimensionId,
                "circleSign": random.choice((-1.0, 1.0)),
                "lastTarget": None,
                "tntLeft": 3 if entityType == "tf_slice:redcap_sapper" else 0,
                "breadEatTick": None,
                "risingRotation": None,
                "beetlePhase": None,
                "beetleTarget": None,
                "lastHurtById": None,
                "phaseStartTick": 0,
                "breathAim": None,
                "fireNextCheckTick": self._tick,
                "windupEndTick": 0,
                "chargeDestination": None,
                "chargeEndTick": 0,
                "chargeNavGeneration": 0,
                "chargeNavDone": True,
                "chargeNavResult": None,
                "carrying": False,
            }
            self._ruin_mobs[entityId] = state
            if entityType == "tf_slice:swarm_spider":
                isSwarmChild = self._pending_swarm_children > 0
                if self._pending_swarm_children > 0:
                    self._pending_swarm_children -= 1
                else:
                    self._spawn_swarm_companions(
                        entityId,
                        self._get_foot_pos(entityId),
                        dimensionId,
                    )
                if not isSwarmChild:
                    self._maybe_spawn_spider_jockey(
                        entityId,
                        entityType,
                        self._get_foot_pos(entityId),
                        dimensionId,
                    )
            elif entityType == "tf_slice:king_spider":
                self._maybe_spawn_spider_jockey(
                    entityId,
                    entityType,
                    self._get_foot_pos(entityId),
                    dimensionId,
                )
            return
        if entityType == LICH_CLONE_IDENTIFIER:
            self._register_lich_clone(entityId, dimensionId)
            return
        if entityType == LICH_MINION_IDENTIFIER:
            self._register_lich_minion(entityId, dimensionId)
            return
        if entityType in (LICH_IDENTIFIER, config.BOSS_IDENTIFIER):
            home = self._get_foot_pos(entityId)
            pendingCourtyard = self._pending_courtyard_naga(
                entityId,
                dimensionId,
                home,
                entityType,
            )
            if pendingCourtyard is not None:
                pendingCourtyard["entityId"] = entityId
                return
        if entityType == LICH_IDENTIFIER:
            home = self._get_foot_pos(entityId)
            state = self._register_lich(entityId, dimensionId, home)
            if state is None:
                self._remove_excess_boss(entityId)
            return
        if entityType in (
            LICH_BOLT_IDENTIFIER,
            LICH_BOMB_IDENTIFIER,
            TOME_BOLT_IDENTIFIER,
            TWILIGHT_WAND_BOLT_IDENTIFIER,
        ):
            motion = self._get_full_motion(entityId)
            self._lich_projectiles.setdefault(
                entityId,
                lich_logic.new_projectile_state(
                    entityType, None, self._tick, motion
                ),
            )
            return
        if entityType != config.BOSS_IDENTIFIER:
            return
        home = self._get_foot_pos(entityId)
        self._pending_naga_spawns = [
            pending
            for pending in self._pending_naga_spawns
            if not (
                pending["dimensionId"] == dimensionId
                and naga_logic.courtyards_overlap(
                    home, pending["home"]
                )
            )
        ]
        state = self._register_boss(
            entityId, dimensionId, home
        )
        if state is None:
            self._remove_excess_boss(entityId)

    def OnRemoveEntity(self, args):
        entityId = args.get("id", args.get("entityId"))
        knightProjectileKey = entity_registry_logic.matching_entity_key(
            self._knight_projectiles, entityId
        )
        if knightProjectileKey is not None:
            self._knight_projectiles.pop(knightProjectileKey, None)
        mobKey = entity_registry_logic.matching_entity_key(
            self._phantom_urghast_mobs, entityId
        )
        if mobKey is not None:
            mobState = self._phantom_urghast_mobs.pop(mobKey, None) or {}
            if mobState.get("type") in goblin_combat.KINDS:
                self._goblin_combat.remove(str(entityId), mobState)
            mountId = mobState.get("mountId")
            riderId = mobState.get("riderId")
            linked = self._phantom_urghast_mobs.get(
                str(mountId if mountId is not None else riderId)
            )
            if linked is not None:
                linked["riderId"] = None
                linked["mountId"] = None
        chainKey = entity_registry_logic.matching_entity_key(
            self._block_chain_projectiles, entityId
        )
        if chainKey is not None:
            chainState = self._block_chain_projectiles.pop(chainKey, None) or {}
            self.BroadcastToAllClient("BlockChainVisual", {
                "projectileId": str(entityId), "removed": True,
            })
            self._stop_using_item(chainState.get("ownerId"))
            ownerState = self._phantom_urghast_mobs.get(
                str(chainState.get("ownerId"))
            )
            if ownerState is not None:
                ownerState["chainProjectileId"] = None
        mortarKey = entity_registry_logic.matching_entity_key(
            self._hydra_mortars, entityId
        )
        if mortarKey is not None:
            self._hydra_mortars.pop(mortarKey, None)
        urProjectileKey = entity_registry_logic.matching_entity_key(
            self._ur_ghast_projectiles, entityId
        )
        if urProjectileKey is not None:
            projectile = self._ur_ghast_projectiles.pop(
                urProjectileKey, None
            ) or {}
            projectile["expires"] = self._tick + 10
            self._ur_ghast_projectile_tombstones[
                str(urProjectileKey)
            ] = projectile
        urBossKey = entity_registry_logic.matching_entity_key(
            self._ur_ghasts, entityId
        )
        if urBossKey is not None:
            unusedKey, urBossState, terminal = (
                self._on_boss_actor_removed(
                    self._ur_ghasts,
                    entityId,
                    ("rewardClaimed",),
                )
            )
            urBossState = urBossState or {}
            self._pending_ur_ghast_player_attacks.pop(
                str(urBossKey), None
            )
            if not terminal:
                urBossState["engineEntityId"] = None
                urBossState["requestedEngineMotion"] = (0.0, 0.0, 0.0)
                urBossState["actualEngineMotion"] = (0.0, 0.0, 0.0)
            self._boss_sync_dirty = True
        partKey = entity_registry_logic.matching_entity_key(
            self._hydra_parts, entityId
        )
        if partKey is not None:
            hydraId, partKind = self._hydra_parts.pop(partKey)
            hydraKey = entity_registry_logic.matching_entity_key(
                self._hydras, hydraId
            )
            if hydraKey is not None:
                self._hydras[hydraKey].setdefault(
                    "partIds", {}
                )[partKind] = None
                self._hydras[hydraKey]["ensureAfter"] = self._tick + 5
        neckKey = entity_registry_logic.matching_entity_key(
            self._hydra_necks, entityId
        )
        if neckKey is not None:
            hydraId, index, segmentIndex = self._hydra_necks.pop(neckKey)
            hydraKey = entity_registry_logic.matching_entity_key(
                self._hydras, hydraId
            )
            if hydraKey is not None:
                head = self._hydras[hydraKey]["heads"][index]
                neckIds = head.get("neckIds") or []
                if segmentIndex < len(neckIds):
                    neckIds[segmentIndex] = None
                self._hydras[hydraKey]["ensureAfter"] = self._tick + 5
        headKey = entity_registry_logic.matching_entity_key(
            self._hydra_heads, entityId
        )
        if headKey is not None:
            hydraId, index = self._hydra_heads.pop(headKey)
            hydraKey = entity_registry_logic.matching_entity_key(
                self._hydras, hydraId
            )
            if hydraKey is not None:
                head = self._hydras[hydraKey]["heads"][index]
                if str(head.get("entityId")) == str(entityId):
                    head["entityId"] = None
                    self._hydras[hydraKey]["ensureAfter"] = self._tick + 5
        routeKey = entity_registry_logic.matching_entity_key(
            self._route_mobs, entityId
        )
        if routeKey is not None:
            routeState = self._route_mobs.get(routeKey)
            if (
                routeState is not None
                and routeState.get("type") == MINOSHROOM_IDENTIFIER
            ):
                self._on_boss_actor_removed(
                    self._route_mobs,
                    entityId,
                    ("rewarded",),
                )
                self._boss_sync_dirty = True
            else:
                self._route_mobs.pop(routeKey, None)
        hydraKey = entity_registry_logic.matching_entity_key(
            self._hydras, entityId
        )
        if hydraKey is not None:
            unusedKey, hydraState, terminal = self._on_boss_actor_removed(
                self._hydras,
                entityId,
                ("dead",),
            )
            if hydraState is not None:
                if terminal:
                    self._remove_hydra_body_parts(hydraState)
                    for head in hydraState.get("heads", ()):
                        self._remove_hydra_head_actor(head)
                else:
                    for partKind in list(
                        hydraState.setdefault("partIds", {}).keys()
                    ):
                        hydraState["partIds"][partKind] = None
                    for head in hydraState.get("heads", ()):
                        head["entityId"] = None
                        head["neckIds"] = [None] * HYDRA_NECK_COUNT
                    hydraState["ensureAfter"] = self._tick + 1
                self._boss_sync_dirty = True
        self._pending_courtyard_nagas = [
            pending
            for pending in self._pending_courtyard_nagas
            if str(pending.get("entityId")) != str(entityId)
        ]
        projectileKey = entity_registry_logic.matching_entity_key(
            self._lich_projectiles, entityId
        )
        if projectileKey is not None:
            self._lich_projectiles.pop(projectileKey, None)
        self._lifedrain_users.pop(entityId, None)
        self._clear_player_fortification(entityId)
        loyal = self._loyal_zombies.pop(entityId, None)
        cloneKey = entity_registry_logic.matching_entity_key(
            self._lich_clones, entityId
        )
        cloneInfo = (
            self._lich_clones.pop(cloneKey, None)
            if cloneKey is not None
            else None
        )
        if cloneInfo is not None:
            ownerKey = self._lich_key(cloneInfo.get("ownerId"))
            ownerState = (
                self._lich_bosses.get(ownerKey)
                if ownerKey is not None
                else None
            )
            if ownerState is not None:
                ownerState["cloneIds"] = set(
                    value
                    for value in ownerState.get("cloneIds", set())
                    if str(value) != str(entityId)
                )
                ownerState["cloneCount"] = len(ownerState["cloneIds"])
                self._save_lich_state(ownerKey, ownerState)
        minionKey = entity_registry_logic.matching_entity_key(
            self._lich_minions, entityId
        )
        minionInfo = (
            self._lich_minions.pop(minionKey, None)
            if minionKey is not None
            else None
        )
        if minionInfo is not None:
            ownerKey = self._lich_key(minionInfo.get("ownerId"))
            ownerState = (
                self._lich_bosses.get(ownerKey)
                if ownerKey is not None
                else None
            )
            if ownerState is not None:
                ownerState["minionIds"] = set(
                    value
                    for value in ownerState.get("minionIds", set())
                    if str(value) != str(entityId)
                )
                ownerState["activeMinions"] = len(ownerState["minionIds"])
                lich_logic.refresh_phase(ownerState)
                self._save_lich_state(ownerKey, ownerState)
        lichKey = self._lich_key(entityId)
        lichState = (
            self._lich_bosses.get(lichKey) if lichKey is not None else None
        )
        if lichState is not None:
            self._on_boss_actor_removed(
                self._lich_bosses,
                entityId,
                ("dead",),
            )
            self._boss_sync_dirty = True
        self._ruin_mobs.pop(entityId, None)
        self._tiny_birds.pop(entityId, None)
        self._penguins.discard(entityId)
        owner = self._segment_owners.pop(entityId, None)
        if owner is not None:
            bossId, index = owner
            state = self._boss_state(bossId)
            if state is not None and state["segmentIds"][index] == entityId:
                state["segmentIds"][index] = None
        bossKey = self._boss_key(entityId)
        state = self._bosses.get(bossKey) if bossKey is not None else None
        if state is not None:
            self._on_boss_actor_removed(
                self._bosses,
                entityId,
                ("dead",),
            )
            self._boss_sync_dirty = True
        self._pending_catalysts.pop(entityId, None)
        self._pending_quest_offerings.pop(entityId, None)
        request = self._pending_portal_entries.pop(entityId, None)
        if request is not None:
            self._release_portal_area(request)
        self._pending_portal_recovery_players.discard(entityId)
        self._known_players.discard(entityId)
        getattr(self, "_pending_trophy_equips", {}).pop(entityId, None)
        getattr(self, "_trophy_block_use_ticks", {}).pop(entityId, None)
        getattr(self, "_pending_trophy_stack_refresh", set()).discard(entityId)
        getattr(self, "_trophy_stack_snapshots", {}).pop(entityId, None)
        self._dimension_change_in_progress.discard(entityId)
        self._dimension_worldgen_ready_ticks.pop(entityId, None)
        self._magic_map_use_cooldowns.pop(entityId, None)
        self._magic_map_held_states.pop(entityId, None)
        self._magic_map_delta_states.pop(entityId, None)
        self._magic_map_discovery_frontiers.pop(entityId, None)
        self._pending_magic_map_clone_sources.pop(entityId, None)
        self._pending_maze_slime_sizes.pop(entityId, None)

    def _place_knight_group_reward_chest(self, home):
        # This method is entered only after the structure's one-shot claim.
        state = {"dimensionId": config.DIMENSION_ID}
        return self._queue_loot_reward(
            state, "knight_phantom", home,
            "loot_tables/chests/tf_slice/stronghold_boss.json", [],
        )

    def _finalize_knight_group(self, death):
        home = death.get("home")
        if self._ruin_worldgen is None:
            return False
        if not self._ruin_worldgen.claim_knight_group_reward(home):
            return False
        self._place_knight_group_reward_chest(home)
        for playerId in sorted(set(death.get("participants", ()))):
            if not self._is_online_player(playerId):
                continue
            if self._grant_progress(
                playerId, "tf_knight_phantoms_defeated"
            ):
                self._notify(
                    playerId,
                    u"\u8fdb\u5ea6\u5df2\u89e3\u9501\uff1a\u9a91\u58eb\u7684\u5e7d\u7075",
                    "GOLD",
                )
        return True

    def _recover_premature_ur_ghast_death(self, bossId, state, args):
        state["prematureDeathRecoveries"] = int(
            state.get("prematureDeathRecoveries", 0)
        ) + 1
        state["dying"] = False
        state["deathTicks"] = 0
        position = (
            state.get("lastPosition")
            or args.get("position", args.get("pos"))
            or state.get("home")
        )
        rotation = state.get("lastRotation") or (0.0, 0.0)
        self._entry_trace(
            "ur_ghast.premature_death",
            bossId=str(bossId),
            authoritativeHealth=round(
                float(state.get("health", 0.0)), 4
            ),
            position=position,
            recoveryCount=int(state["prematureDeathRecoveries"]),
        )
        if self._get_foot_pos(bossId) is not None:
            self._set_ur_ghast_engine_health(
                bossId,
                state,
                ur_ghast_logic.authoritative_engine_health(state),
            )
            self._save_ur_ghast_state(bossId, state)
            self._boss_sync_dirty = True
            return bossId
        if position is None or len(position) != 3:
            return None
        replacementId = self._spawn_ruin_entity(
            UR_GHAST_IDENTIFIER,
            position,
            float(rotation[1]) if len(rotation) > 1 else 0.0,
            int(state.get("dimensionId", config.DIMENSION_ID)),
        )
        if replacementId is None:
            return None
        self._ur_ghasts.pop(str(bossId), None)
        state["targetId"] = None
        state["visualCharging"] = False
        state["visualTracking"] = False
        self._ur_ghasts[str(replacementId)] = state
        self._set_ur_ghast_engine_health(
            replacementId,
            state,
            ur_ghast_logic.authoritative_engine_health(state),
        )
        self._save_ur_ghast_state(replacementId, state)
        self._boss_sync_dirty = True
        return replacementId

    def OnMobDie(self, args):
        entityId = args.get("id", args.get("entityId"))
        if self._ruin_worldgen is not None:
            killerId = args.get(
                "killerId", args.get("attackerId", args.get("srcId"))
            )
            knightDeath = self._ruin_worldgen.record_knight_member_death(
                entityId,
                killerId if self._is_online_player(killerId) else None,
            )
            if knightDeath.get("handled"):
                self._knight_phantoms.pop(str(entityId), None)
                if knightDeath.get("final"):
                    self._finalize_knight_group(knightDeath)
                return
        trackedState = self._phantom_urghast_mobs.get(str(entityId)) or {}
        entityType = ur_ghast_logic.resolve_death_entity_type(
            args.get("engineTypeStr"),
            self._get_engine_type(entityId),
            trackedState,
        )
        if entityType == MINI_GHAST_IDENTIFIER:
            state = trackedState
            eventPos = args.get("position", args.get("pos"))
            if eventPos is None:
                coordinateKeys = (
                    ("x", "y", "z"),
                    ("posX", "posY", "posZ"),
                )
                for keys in coordinateKeys:
                    if all(key in args for key in keys):
                        eventPos = tuple(args[key] for key in keys)
                        break
            deathPos = ur_ghast_logic.resolve_death_position(
                self._get_foot_pos(entityId) or eventPos,
                state.get("lastPosition"),
            )
            matchingTraps = []
            if deathPos is not None:
                for unusedKey, trap in self._ghast_traps.items():
                    trapPos = trap.get("position") or ()
                    if len(trapPos) != 3:
                        continue
                    if int(trap.get("dimensionId", args.get("dimensionId", config.DIMENSION_ID))) != int(
                        args.get("dimensionId", config.DIMENSION_ID)
                    ):
                        continue
                    if not ur_ghast_logic.trap_accepts_mini_ghast_death(
                        trap, deathPos
                    ):
                        continue
                    matchingTraps.append(trap)
            updatedTraps = ur_ghast_logic.record_mini_ghast_death_for_traps(
                matchingTraps, entityId, deathPos
            ) if deathPos is not None else []
            for trap in updatedTraps:
                self._broadcast_ghast_trap_effect(
                    trap, "charge", deathPos
                )
                self._entry_trace(
                    "ur_ghast.trap_charge",
                    trapPosition=[
                        round(float(value), 3)
                        for value in trap.get("position", ())
                    ],
                    deathPosition=[
                        round(float(value), 3) for value in deathPos
                    ],
                    deathCount=int(trap.get("deathCount", 0)),
                    charged=bool(trap.get("charged", False)),
                    minionId=str(entityId),
                )
            if updatedTraps:
                self._save_dark_tower_runtime()
            self._phantom_urghast_mobs.pop(str(entityId), None)
            return
        urKey = entity_registry_logic.matching_entity_key(
            self._ur_ghasts, entityId
        )
        if urKey is not None:
            state = self._ur_ghasts[urKey]
            if float(state.get("health", 0.0)) > 0.0:
                self._recover_premature_ur_ghast_death(
                    urKey, state, args
                )
                return
            if not state.get("dying"):
                state["dying"] = True
                state["deathTicks"] = 0
            self._save_ur_ghast_state(urKey, state)
            return
        partKey = entity_registry_logic.matching_entity_key(
            self._hydra_parts, entityId
        )
        if partKey is not None:
            hydraId, partKind = self._hydra_parts.pop(partKey)
            ownerKey = entity_registry_logic.matching_entity_key(
                self._hydras, hydraId
            )
            if ownerKey is not None:
                self._hydras[ownerKey].setdefault(
                    "partIds", {}
                )[partKind] = None
                self._hydras[ownerKey]["ensureAfter"] = self._tick + 1
            return
        headKey = entity_registry_logic.matching_entity_key(
            self._hydra_heads, entityId
        )
        if headKey is not None:
            hydraId, index = self._hydra_heads.pop(headKey)
            ownerKey = entity_registry_logic.matching_entity_key(
                self._hydras, hydraId
            )
            if ownerKey is not None:
                head = self._hydras[ownerKey]["heads"][index]
                if str(head.get("entityId")) == str(entityId):
                    head["entityId"] = None
                    self._hydras[ownerKey]["ensureAfter"] = self._tick + 1
            return
        neckKey = entity_registry_logic.matching_entity_key(
            self._hydra_necks, entityId
        )
        if neckKey is not None:
            hydraId, index, segmentIndex = self._hydra_necks.pop(neckKey)
            ownerKey = entity_registry_logic.matching_entity_key(
                self._hydras, hydraId
            )
            if ownerKey is not None:
                head = self._hydras[ownerKey]["heads"][index]
                neckIds = head.get("neckIds") or []
                if segmentIndex < len(neckIds):
                    neckIds[segmentIndex] = None
                self._hydras[ownerKey]["ensureAfter"] = self._tick + 1
            return
        hydraKey = entity_registry_logic.matching_entity_key(
            self._hydras, entityId
        )
        if hydraKey is not None:
            state = self._hydras[hydraKey]
            if not state.get("dying") and not state.get("dead"):
                self._begin_hydra_death(hydraKey, state)
            return
        routeKey = entity_registry_logic.matching_entity_key(
            self._route_mobs, entityId
        )
        if routeKey is not None:
            routeState = self._route_mobs.get(routeKey) or {}
            if routeState.get("type") == MAZE_SLIME_IDENTIFIER:
                position = self._get_foot_pos(routeKey)
                childSizes = maze_slime_logic.split_plan(
                    routeState.get("size", 4), random.randrange(3)
                )
                if position is not None:
                    for index, childSize in enumerate(childSizes):
                        childId = self._spawn_ruin_entity(
                            MAZE_SLIME_IDENTIFIER,
                            (
                                position[0] + (index % 2) * 0.5,
                                position[1],
                                position[2] + (index // 2) * 0.5,
                            ),
                            random.uniform(0.0, 360.0),
                            routeState.get("dimensionId", config.DIMENSION_ID),
                        )
                        childKey = entity_registry_logic.matching_entity_key(
                            self._route_mobs, childId
                        )
                        if childKey is not None:
                            self._set_maze_slime_size(
                                childKey,
                                self._route_mobs[childKey],
                                childSize,
                            )
                        elif childId is not None:
                            self._pending_maze_slime_sizes[childId] = childSize
            if (
                routeState.get("type") == MINOSHROOM_IDENTIFIER
                and not routeState.get("rewarded")
            ):
                rewardAllowed = True
                if self._ruin_worldgen is not None:
                    managed = self._ruin_worldgen.mark_boss_defeated(
                        routeState.get("home"), "minoshroom"
                    )
                    if managed:
                        rewardAllowed = self._ruin_worldgen.claim_boss_reward(
                            routeState.get("home"), "minoshroom"
                        )
                routeState["rewarded"] = True
                killerId = args.get(
                    "killerId", args.get("attackerId", args.get("srcId"))
                )
                participants = set(routeState.get("participants", ()))
                if self._is_online_player(killerId):
                    participants.add(str(killerId))
                for playerId in sorted(participants):
                    self._grant_progress(playerId, "tf_minoshroom_defeated")
                if rewardAllowed:
                    self._spawn_route_boss_experience(
                        minotaur_logic.MINOSHROOM_XP_REWARD,
                        self._get_foot_pos(routeKey) or routeState.get("home"),
                    )
                    if self._is_online_player(killerId):
                        routeState["lastLootingLevel"] = self._hydra_looting_level(killerId)
                    self._award_minoshroom_items(routeKey, routeState)
            self._route_mobs.pop(routeKey, None)
        lichState = self._lich_state(entityId)
        if lichState is not None:
            # HealthChangeBefore normally starts the 175-tick sequence.  This
            # remains a lossless fallback for engine-side kills that bypass it.
            self._finalize_lich_death(
                entityId, lichState, destroyActor=False
            )
            return
        ruinState = self._ruin_mobs.get(entityId)
        if (
            ruinState is not None
            and ruinState.get("type") == "tf_slice:kobold"
        ):
            self._panic_nearby_kobolds(
                self._get_foot_pos(entityId),
                ruinState.get("dimensionId"),
            )
        state = self._boss_state(entityId)
        if state is not None:
            # Lethal health changes normally enter the 144-tick sequence.
            # This is the lossless fallback for engine-side kills that bypass
            # HealthChangeBeforeServerEvent.
            self._finalize_naga_death(
                entityId, state, destroyActor=False
            )

    def _lich_damage_projectile(self, entityId, sourceId, args):
        candidateIds = [
            args.get("projectileId"),
            args.get("directEntityId"),
            args.get("childId"),
            sourceId,
        ]
        recentKey = entity_registry_logic.matching_entity_key(
            self._recent_lich_projectile_hits, entityId
        )
        recent = self._recent_lich_projectile_hits.get(recentKey) or {}
        for candidateId in candidateIds:
            key = entity_registry_logic.matching_entity_key(
                self._lich_projectiles, candidateId
            )
            if key is not None:
                return key, self._lich_projectiles.get(key) or {}
            engineType = self._get_engine_type(candidateId)
            if engineType in (
                LICH_BOLT_IDENTIFIER,
                LICH_BOMB_IDENTIFIER,
                TOME_BOLT_IDENTIFIER,
                TWILIGHT_WAND_BOLT_IDENTIFIER,
            ):
                return candidateId, {
                    "type": engineType,
                    "ownerId": sourceId,
                    "reflected": False,
                }
        if self._tick <= int(recent.get("expires", -1)):
            recentProjectileId = recent.get("projectileId")
            recentProjectileKey = entity_registry_logic.matching_entity_key(
                self._lich_projectiles, recentProjectileId
            )
            if recentProjectileKey is not None:
                return recentProjectileKey, (
                    self._lich_projectiles.get(recentProjectileKey) or {}
                )
            projectile = recent.get("projectile")
            if isinstance(projectile, dict):
                return recent.get("projectileId"), projectile
        return None, {}

    def _lich_damage_source(self, entityId, sourceId, args):
        cause = str(
            args.get("cause", args.get("damageCause", ""))
        ).lower().replace(" ", "_")
        if any(value in cause for value in LICH_BYPASS_DAMAGE_CAUSES):
            return "bypass", sourceId, {}
        projectileId, projectile = self._lich_damage_projectile(
            entityId, sourceId, args
        )
        ownerId = projectile.get("ownerId", sourceId)
        projectileType = projectile.get("type")
        ownerCloneKey = entity_registry_logic.matching_entity_key(
            self._lich_clones, ownerId
        )
        if projectileType == LICH_BOLT_IDENTIFIER:
            sourceKind = lich_logic.lich_bolt_source_kind(
                projectile.get("reflected"),
                self._lich_state(ownerId) is not None
                or ownerCloneKey is not None,
            )
            return sourceKind, ownerId, projectile
        if projectileType == TWILIGHT_WAND_BOLT_IDENTIFIER:
            return "twilight_scepter", ownerId, projectile
        if projectileType == LICH_BOMB_IDENTIFIER:
            return "normal", ownerId, projectile
        if self._lich_state(ownerId) is not None or ownerCloneKey is not None:
            if "explosion" in cause:
                return "normal", ownerId, projectile
            return "lich_owned", ownerId, projectile
        lifedrainKey = entity_registry_logic.matching_entity_key(
            self._recent_lifedrain_hits, entityId
        )
        lifedrainHit = self._recent_lifedrain_hits.get(lifedrainKey) or {}
        if (
            self._tick <= int(lifedrainHit.get("expires", -1))
            and str(lifedrainHit.get("sourceId")) == str(sourceId)
        ):
            return "twilight_scepter", sourceId, projectile
        if "sonic" in cause:
            return "sonic_boom", ownerId, projectile
        if "indirect" in cause and "magic" in cause:
            return "indirect_magic", ownerId, projectile
        if "magic" in cause:
            return "magic", ownerId, projectile
        return "normal", ownerId, projectile

    def _is_online_player(self, entityId):
        if entityId is None:
            return False
        return any(
            str(playerId) == str(entityId)
            for playerId in self._get_online_players()
        )

    def _damage_entity_inside_home(self, entityId, state):
        if entityId in (None, "", -1, "-1"):
            return None
        position = self._get_foot_pos(entityId)
        if position is None or state.get("home") is None:
            return None
        dimensionId = self._get_dimension(entityId)
        if dimensionId is not None and dimensionId != state["dimensionId"]:
            return False
        return naga_logic.inside_home(position, state["home"])

    def _route_progress_value(self, playerId):
        return route_progression_logic.migrate_progress(
            self._progress_for_player(playerId)
        )

    def _update_route_progression_penalties(self):
        if self._tick % 60 != 0:
            return
        for playerId in self._get_online_players():
            if self._get_dimension(playerId) != config.DIMENSION_ID:
                continue
            pos = self._get_foot_pos(playerId)
            if pos is None:
                continue
            try:
                identifier = self._biome_comp.GetBiomeName(
                    int(pos[0]), int(pos[2]), config.DIMENSION_ID
                )
            except Exception:
                continue
            biome = BIOMES_BY_IDENTIFIER.get(str(identifier))
            if biome is None and ":" in str(identifier):
                biome = BIOMES_BY_IDENTIFIER.get(str(identifier).split(":", 1)[1])
            biomeKey = biome.get("key") if biome else None
            runtime = self._route_penalty_ticks.setdefault(
                playerId, {"hungerAmplifier": -1}
            )
            penalty = route_progression_logic.biome_penalty(
                biomeKey,
                self._route_progress_value(playerId),
                runtime.get("hungerAmplifier", -1),
            )
            if penalty is None:
                runtime["hungerAmplifier"] = -1
                continue
            if penalty["effect"] == "hunger":
                runtime["hungerAmplifier"] = min(20, int(penalty["amplifier"]))
                try:
                    CF.CreateEffect(playerId).AddEffectToEntity(
                        "hunger", 5, runtime["hungerAmplifier"], False
                    )
                except Exception:
                    pass
            elif penalty["effect"] == "fire":
                self._set_entity_on_fire(playerId, penalty["seconds"])
            elif penalty["effect"] == "darkness":
                try:
                    CF.CreateEffect(playerId).AddEffectToEntity(
                        "darkness",
                        max(1, int(penalty.get("duration", 100)) // 20),
                        max(0, int(penalty.get("amplifier", 0))),
                        False,
                    )
                except Exception:
                    pass

    @staticmethod
    def _route_item_name(item):
        return portal_logic.item_name(item or {})

    def OnHydraRouteItemTryUseEvent(self, args):
        playerId = args.get("playerId", args.get("entityId"))
        item = args.get("itemDict") or args.get("item") or {}
        if playerId is None:
            return
        itemName = self._route_item_name(item)
        if itemName in (
            config.MAZE_MAP_ITEM,
            config.FILLED_MAZE_MAP_ITEM,
        ):
            if self._magic_map_use_cooldowns.get(playerId, 0) > self._tick:
                return
            self._magic_map_use_cooldowns[playerId] = self._tick + 5
            hand, held = self._maze_map_hand_item(playerId, item)
            held = held or item
            position = self._get_foot_pos(playerId)
            if (
                hand is None
                or position is None
                or self._get_dimension(playerId) != config.DIMENSION_ID
            ):
                self._notify(
                    playerId,
                    u"迷宫地图只能在暮色维度中使用。",
                    "RED",
                )
                return
            if itemName == config.MAZE_MAP_ITEM:
                self._create_maze_map(playerId, hand, held, position)
            else:
                self._send_maze_map_snapshot(
                    playerId,
                    held.get("extraId"),
                    position,
                )
            args["cancel"] = True
            args["ret"] = True
            return

    def _keeping_inventory_entries(self, playerId):
        itemComp = CF.CreateItem(playerId)
        itemPos = serverApi.GetMinecraftEnum().ItemPosType
        entries = []
        for name in ("INVENTORY", "ARMOR", "OFFHAND", "CARRIED"):
            if not hasattr(itemPos, name):
                continue
            posType = getattr(itemPos, name)
            try:
                items = itemComp.GetPlayerAllItems(posType, True) or ()
            except Exception:
                items = ()
            for slot, item in enumerate(items):
                if item:
                    entries.append(
                        {"posType": int(posType), "slot": int(slot), "item": copy.deepcopy(item)}
                    )
        return entries

    @staticmethod
    def _keeping_tier(item):
        name = portal_logic.item_name(item or {})
        for tier in (1, 2, 3):
            if name == "tf_slice:charm_of_keeping_%d" % tier:
                return tier
        return 0

    def _keep_inventory_rule(self):
        try:
            rules = CF.CreateGame(LEVEL_ID).GetGameRulesInfoServer() or {}
            cheats = rules.get("cheat_info", {})
            return bool(cheats.get("keep_inventory", cheats.get("keepInventory", False)))
        except Exception:
            return False

    def OnRoutePlayerDie(self, args):
        playerId = args.get("playerId", args.get("id", args.get("entityId")))
        if playerId is None:
            return
        self._clear_player_fortification(playerId)
        try:
            gameType = int(CF.CreateGame(LEVEL_ID).GetPlayerGameType(playerId))
        except Exception:
            gameType = 0
        if self._keep_inventory_rule() or gameType in (1, 3, 6):
            return
        try:
            entries = self._keeping_inventory_entries(playerId)
        except Exception:
            return
        charmEntries = [entry for entry in entries if self._keeping_tier(entry["item"]) > 0]
        tier = max([self._keeping_tier(entry["item"]) for entry in charmEntries] or [0])
        consumed = next((entry for entry in charmEntries if self._keeping_tier(entry["item"]) == tier), None)
        kept = []
        for entry in entries:
            posType = int(entry["posType"])
            slot = int(entry["slot"])
            try:
                itemPos = serverApi.GetMinecraftEnum().ItemPosType
                isArmor = posType == int(itemPos.ARMOR)
                isOffhand = posType == int(itemPos.OFFHAND)
                isCarried = posType == int(itemPos.CARRIED)
                isInventory = posType == int(itemPos.INVENTORY)
            except Exception:
                continue
            intrinsicKeep = portal_logic.item_name(entry["item"]) in (
                "tf_slice:phantom_helmet", "tf_slice:phantom_chestplate", "tf_slice:tower_key"
            )
            # CARRIED is the selected INVENTORY slot, not a second item.
            if intrinsicKeep and isCarried:
                continue
            retain = intrinsicKeep or (tier > 0 and (isArmor or isOffhand)) or (tier == 1 and isCarried)
            retain = retain or (tier == 2 and isInventory and slot < 9)
            retain = retain or (tier == 3 and isInventory)
            isConsumedCharm = (
                consumed is not None and posType == int(consumed["posType"])
                and slot == int(consumed["slot"])
            )
            if retain and not isConsumedCharm:
                kept.append(copy.deepcopy(entry))
        if not kept and consumed is None:
            return
        # Persist before clearing. A crash between death and respawn therefore
        # replays the same snapshot instead of losing or duplicating it.
        snapshot = {"version": 1, "tier": tier, "entries": kept, "restored": False}
        self._keeping_snapshots[str(playerId)] = snapshot
        self._persist_keeping_snapshots()
        updates = {}
        for entry in kept:
            updates[(entry["posType"], entry["slot"])] = None
        if consumed is not None:
            charmItem = copy.deepcopy(consumed["item"])
            charmItem["count"] = max(0, int(charmItem.get("count", 1)) - 1)
            updates[(consumed["posType"], consumed["slot"])] = charmItem if charmItem["count"] else None
        try:
            CF.CreateItem(playerId).SetPlayerAllItems(updates)
        except Exception:
            pass

    def OnRoutePlayerRespawn(self, args):
        playerId = args.get("playerId", args.get("id", args.get("entityId")))
        if playerId is None:
            return
        self.NotifyToClient(playerId, "BossHudReset", {})
        self._sequence += 1
        self.NotifyToClient(
            playerId,
            "BossSync",
            self._make_sync_packet(playerId),
        )
        snapshot = self._keeping_snapshots.get(str(playerId))
        if not isinstance(snapshot, dict) or snapshot.get("restored"):
            return
        updates = {}
        for entry in snapshot.get("entries", ()):
            try:
                updates[(int(entry["posType"]), int(entry["slot"]))] = copy.deepcopy(entry["item"])
            except (KeyError, TypeError, ValueError):
                continue
        if not updates:
            snapshot["restored"] = True
            self._persist_keeping_snapshots()
            return
        try:
            result = CF.CreateItem(playerId).SetPlayerAllItems(updates)
            restored = all(bool(value) for value in result.values())
        except Exception:
            restored = False
        if restored:
            snapshot["restored"] = True
            self._persist_keeping_snapshots()

    @staticmethod
    def _fire_react_level(item):
        extraId = str((item or {}).get("extraId", ""))
        marker = "tf_fire_react:"
        if marker not in extraId:
            return 0
        try:
            return max(0, min(3, int(extraId.split(marker, 1)[1].split("|", 1)[0])))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _fire_react_book_level(itemName):
        prefix = "tf_slice:fire_react_book_"
        if not str(itemName).startswith(prefix):
            return 0
        try:
            return max(0, min(3, int(str(itemName)[len(prefix):])))
        except (TypeError, ValueError):
            return 0

    def _fire_react_book_hand(self, playerId, itemName):
        for hand, current in (
            ("carried", self._carried_item(playerId) or {}),
            ("offhand", self._offhand_item(playerId) or {}),
        ):
            if portal_logic.item_name(current) == itemName:
                return hand, current
        return None, None

    def _fire_react_armor_choices(self, playerId):
        try:
            itemPos = serverApi.GetMinecraftEnum().ItemPosType
            armor = CF.CreateItem(playerId).GetPlayerAllItems(
                itemPos.ARMOR, True
            ) or ()
        except Exception:
            return None, (), []
        choices = []
        for slot, armorItem in enumerate(armor):
            if not armorItem:
                continue
            enchants = armorItem.get(
                "enchantData", armorItem.get("enchants", {})
            )
            if not route_progression_logic.can_apply_fire_react(enchants):
                continue
            choices.append(
                {
                    "slot": int(slot),
                    "itemName": portal_logic.item_name(armorItem),
                }
            )
        return itemPos, armor, choices

    def _open_fire_react_ui(self, playerId, itemName, level, args):
        hand, current = self._fire_react_book_hand(playerId, itemName)
        itemPos, _armor, choices = self._fire_react_armor_choices(playerId)
        if hand is None or itemPos is None:
            return False
        if not choices:
            self._notify(
                playerId,
                u"没有可应用的非荆棘护甲。",
                "RED",
            )
            return False
        self._fire_react_sessions[playerId] = {
            "expires": self._tick + 200,
            "itemName": str(itemName),
            "level": int(level),
            "hand": str(hand),
            "slots": set(int(choice["slot"]) for choice in choices),
        }
        self.NotifyToClient(
            playerId,
            "FireReactOpen",
            {
                "schemaVersion": 1,
                "level": int(level),
                "choices": choices,
            },
        )
        args["cancel"] = True
        args["ret"] = False
        return True

    def OnFireReactApplyRequest(self, args):
        playerId = args.get("__id__")
        if playerId is None:
            return
        session = self._fire_react_sessions.pop(playerId, None)
        if not isinstance(session, dict):
            return
        try:
            slot = int(args.get("slot"))
            level = int(session.get("level", 0))
            expires = int(session.get("expires", 0))
        except (TypeError, ValueError):
            return
        if (
            self._tick > expires
            or level < 1
            or level > 3
            or slot not in session.get("slots", set())
        ):
            return

        itemName = str(session.get("itemName", ""))
        if self._fire_react_book_level(itemName) != level:
            return
        hand, book = self._fire_react_book_hand(playerId, itemName)
        if hand != session.get("hand") or not book:
            return
        itemPos, armor, choices = self._fire_react_armor_choices(playerId)
        allowedSlots = set(int(choice["slot"]) for choice in choices)
        if itemPos is None or slot not in allowedSlots or slot >= len(armor):
            return

        originalArmor = armor[slot]
        armorItem = copy.deepcopy(originalArmor)
        extraId = str(armorItem.get("extraId", ""))
        extraId = extraId.split("|tf_fire_react:", 1)[0]
        armorItem["extraId"] = (
            (extraId + "|") if extraId else ""
        ) + "tf_fire_react:%d" % level
        replacementBook = copy.deepcopy(book)
        replacementBook["count"] = max(
            0, int(replacementBook.get("count", 1)) - 1
        )
        handPos = self._hand_pos_type(hand)
        updates = {
            (itemPos.ARMOR, slot): armorItem,
            (handPos, 0): replacementBook if replacementBook["count"] else None,
        }
        try:
            result = CF.CreateItem(playerId).SetPlayerAllItems(updates)
            applied = isinstance(result, dict) and all(
                bool(result.get(key, False)) for key in updates
            )
        except Exception:
            applied = False
        if not applied:
            self._notify(playerId, u"火焰反击应用失败，物品未消耗。", "RED")
            return
        try:
            playerName = CF.CreateName(playerId).GetName()
        except Exception:
            playerName = str(playerId)
        try:
            CF.CreateCommand(LEVEL_ID).SetCommand(
                "/xp -%dL @a[name=\"%s\"]"
                % (level * 3, str(playerName).replace('"', ''))
            )
        except Exception:
            pass
        self._notify(
            playerId,
            u"火焰反击 %d 已应用。" % level,
            "GOLD",
        )

    def OnHydraRouteItemUseOnEvent(self, args):
        playerId = args.get("playerId", args.get("entityId"))
        item = args.get("itemDict") or args.get("item") or {}
        itemName = self._route_item_name(item)
        if itemName in (
            config.MAZE_MAP_ITEM,
            config.FILLED_MAZE_MAP_ITEM,
        ):
            self.OnHydraRouteItemTryUseEvent(args)
            return
        if itemName in (
            "tf_slice:mangrove_boat",
            "tf_slice:mangrove_chest_boat",
            "tf_slice:dark_boat",
            "tf_slice:dark_chest_boat",
        ):
            self._place_mangrove_boat(playerId, itemName, args)
            return
        if playerId is None or not itemName.startswith("tf_slice:fire_react_book_"):
            return
        blockName = str(args.get("blockName", args.get("fullName", "")))
        if blockName not in ("minecraft:anvil", "minecraft:chipped_anvil", "minecraft:damaged_anvil"):
            return
        if not bool(args.get("isSneaking", args.get("sneaking", True))):
            return
        level = self._fire_react_book_level(itemName)
        if level:
            self._open_fire_react_ui(
                playerId, itemName, level, args
            )

    def _place_mangrove_boat(self, playerId, itemName, args):
        if playerId is None:
            return False
        blockName = str(args.get("blockName", args.get("fullName", "")))
        if blockName not in WATER_BLOCKS:
            return False
        position = (
            float(args.get("x", args.get("blockX", 0))) + 0.5,
            float(args.get("y", args.get("blockY", 0))) + 1.0,
            float(args.get("z", args.get("blockZ", 0))) + 0.5,
        )
        dimensionId = int(
            args.get("dimensionId", self._get_dimension(playerId) or 0)
        )
        carrier = (
            "minecraft:chest_boat"
            if itemName in (
                "tf_slice:mangrove_chest_boat",
                "tf_slice:dark_chest_boat",
            )
            else "minecraft:boat"
        )
        entityId = self._spawn_ruin_entity(
            carrier,
            position,
            self._get_rotation(playerId)[1],
            dimensionId,
        )
        if not entityId:
            return False
        if not self._is_creative(playerId):
            for hand, current in (
                ("carried", self._carried_item(playerId) or {}),
                ("offhand", self._offhand_item(playerId) or {}),
            ):
                if portal_logic.item_name(current) != itemName:
                    continue
                replacement = copy.deepcopy(current)
                replacement["count"] = max(0, int(current.get("count", 1)) - 1)
                self._set_hand_item(
                    playerId,
                    hand,
                    replacement if replacement["count"] else None,
                )
                break
        args["cancel"] = True
        args["ret"] = True
        return True

    def _hydra_owned_damage_source(self, sourceId, hydraId):
        if sourceId is None:
            return False
        if str(sourceId) == str(hydraId):
            return True
        headKey = entity_registry_logic.matching_entity_key(
            self._hydra_heads, sourceId
        )
        if headKey is not None:
            return str(self._hydra_heads[headKey][0]) == str(hydraId)
        neckKey = entity_registry_logic.matching_entity_key(
            self._hydra_necks, sourceId
        )
        if neckKey is not None:
            return str(self._hydra_necks[neckKey][0]) == str(hydraId)
        partKey = entity_registry_logic.matching_entity_key(
            self._hydra_parts, sourceId
        )
        if partKey is not None:
            return str(self._hydra_parts[partKey][0]) == str(hydraId)
        mortarKey = entity_registry_logic.matching_entity_key(
            self._hydra_mortars, sourceId
        )
        if mortarKey is not None:
            mortar = self._hydra_mortars.get(mortarKey) or {}
            return str(mortar.get("ownerId")) == str(hydraId)
        return False

    def _remember_hydra_player_attack(self, targetId, playerId):
        if targetId is None or playerId is None:
            return False
        isHydraTarget = (
            entity_registry_logic.matching_entity_key(
                self._hydras, targetId
            ) is not None
            or entity_registry_logic.matching_entity_key(
                self._hydra_heads, targetId
            ) is not None
            or entity_registry_logic.matching_entity_key(
                self._hydra_necks, targetId
            ) is not None
            or entity_registry_logic.matching_entity_key(
                self._hydra_parts, targetId
            ) is not None
        )
        if not isHydraTarget:
            return False
        for key, pending in list(self._pending_hydra_player_attacks.items()):
            if self._tick - int(pending.get("tick", -100)) > 4:
                self._pending_hydra_player_attacks.pop(key, None)
        self._pending_hydra_player_attacks[str(targetId)] = {
            "sourceId": playerId,
            "tick": self._tick,
        }
        return True

    def _resolve_hydra_damage(self, args, incomingDamage, sourceId):
        entityId = args.get("entityId")
        headOwner = entity_registry_logic.matching_entity_key(
            self._hydra_heads, entityId
        )
        neckOwner = entity_registry_logic.matching_entity_key(
            self._hydra_necks, entityId
        )
        partOwner = entity_registry_logic.matching_entity_key(
            self._hydra_parts, entityId
        )
        hydraKey = entity_registry_logic.matching_entity_key(self._hydras, entityId)
        if (
            headOwner is None
            and neckOwner is None
            and partOwner is None
            and hydraKey is None
        ):
            return False
        # Script-authoritative health restoration and body-health settlement
        # must be allowed through. Re-consuming those callbacks either cancels
        # our own write or makes one hit recurse through the Hydra resolver.
        if args.get("byScript"):
            return True
        if not incomingDamage:
            return False
        if sourceId is None:
            pending = self._pending_hydra_player_attacks.pop(
                str(entityId), None
            )
            if pending is not None and (
                self._tick - int(pending.get("tick", -100)) <= 2
            ):
                sourceId = pending.get("sourceId")
        try:
            fromValue = float(args.get("from", args.get("fromValue", 0.0)))
            toValue = float(args.get("to", args.get("toValue", fromValue)))
            rawDamage = max(0.0, fromValue - toValue)
        except (TypeError, ValueError):
            rawDamage = max(0.0, float(args.get("damage", 0.0)))
        args["cancel"] = True
        if headOwner is not None:
            ownerId, unusedIndex = self._hydra_heads[headOwner]
            hydraKey = entity_registry_logic.matching_entity_key(
                self._hydras, ownerId
            )
        elif neckOwner is not None:
            ownerId, unusedIndex, unusedSegment = self._hydra_necks[neckOwner]
            hydraKey = entity_registry_logic.matching_entity_key(
                self._hydras, ownerId
            )
        elif partOwner is not None:
            ownerId, unusedPartKind = self._hydra_parts[partOwner]
            hydraKey = entity_registry_logic.matching_entity_key(
                self._hydras, ownerId
            )
        if hydraKey is None:
            return True
        state = self._hydras[hydraKey]
        isPartActor = (
            headOwner is not None
            or neckOwner is not None
            or partOwner is not None
        )
        restoreHealth = (
            hydra_logic.PART_ACTOR_HEALTH
            if isPartActor
            else max(1.0, float(state.get("health", hydra_logic.MAX_HEALTH)))
        )
        cause = str(args.get("cause", args.get("damageCause", ""))).lower()
        if cause in (
            "fall", "fire", "fire_tick", "lava", "in_wall",
            "suffocation", "drowning",
        ):
            if cause in ("in_wall", "suffocation"):
                self._clear_hydra_block_volume(hydraKey, state)
            self._set_health(entityId, restoreHealth)
            self._set_health(hydraKey, max(1.0, state["health"]))
            return True
        if self._hydra_owned_damage_source(sourceId, hydraKey):
            self._set_health(entityId, restoreHealth)
            return True
        effectiveSource = args.get(
            "attackerId", args.get("srcId", args.get("sourceId", sourceId))
        )
        if effectiveSource is None:
            effectiveSource = sourceId
        sourceLimit = 400.0
        directSource = args.get("projectileId", sourceId)
        mortarKey = entity_registry_logic.matching_entity_key(
            self._hydra_mortars, directSource
        )
        if mortarKey is not None:
            mortar = self._hydra_mortars.get(mortarKey) or {}
            effectiveSource = mortar.get("ownerId")
            if mortar.get("reflected"):
                sourceLimit = 600.0
        sourcePos = self._get_foot_pos(effectiveSource)
        hydraPos = self._get_foot_pos(hydraKey)
        if (
            sourcePos is not None
            and hydraPos is not None
            and _distance_sq(sourcePos, hydraPos) > sourceLimit
        ):
            self._set_health(entityId, restoreHealth)
            return True
        if not hydra_logic.can_settle_part_impact(
            state.get("lastPartDamageTick"),
            state.get("lastPartDamageSource"),
            self._tick,
            effectiveSource,
        ):
            self._set_health(entityId, restoreHealth)
            return True
        state["lastPartDamageTick"] = self._tick
        state["lastPartDamageSource"] = effectiveSource
        if headOwner is not None:
            hydraId, index = self._hydra_heads[headOwner]
            head = state["heads"][index]
            if not head.get("alive"):
                self._set_health(
                    entityId, hydra_logic.PART_ACTOR_HEALTH
                )
                return True
            mouthOpen = hydra_logic.interpolated_head_pose(
                head.get("previousState", head.get("state", "idle")),
                head.get("state", "idle"),
                index,
                head.get("ticks", 0),
            )[3] > 0.5
            accepted = hydra_logic.accepted_multipart_damage(
                rawDamage, "head", mouthOpen, True, False
            )
            head["damage"] += hydra_logic.head_damage_credit(accepted)
            self._set_health(entityId, hydra_logic.PART_ACTOR_HEALTH)
            if head["damage"] > hydra_logic.HEAD_DAMAGE_THRESHOLD:
                self._kill_hydra_head(hydraKey, state, index)
        elif neckOwner is not None:
            unusedHydra, index, unusedSegment = self._hydra_necks[neckOwner]
            if not state["heads"][index].get("alive"):
                self._set_health(
                    entityId, hydra_logic.PART_ACTOR_HEALTH
                )
                return True
            accepted = hydra_logic.accepted_multipart_damage(
                rawDamage, "neck", False, True, False
            )
            self._set_health(entityId, hydra_logic.PART_ACTOR_HEALTH)
        elif partOwner is not None:
            unusedHydra, partKind = self._hydra_parts[partOwner]
            accepted = hydra_logic.accepted_multipart_damage(
                rawDamage, partKind, False, True, False
            )
            self._set_health(entityId, hydra_logic.PART_ACTOR_HEALTH)
        else:
            accepted = hydra_logic.accepted_multipart_damage(
                rawDamage, "root", False, True, False
            )
        healthDamage = 0.0
        if accepted > 0.0:
            hurt = hydra_logic.shared_hurt_resolution(
                accepted,
                state.get("lastHurtAmount", 0.0),
                state.get("hurtWindowStartTick"),
                self._tick,
            )
            state["lastHurtAmount"] = hurt["lastHurtAmount"]
            state["hurtWindowStartTick"] = hurt["windowStartTick"]
            healthDamage = hurt["healthDamage"]
        if healthDamage > 0.0:
            state["ticksSinceDamage"] = 0
            if self._is_online_player(effectiveSource):
                state["participants"].add(str(effectiveSource))
                state["lastLootingLevel"] = self._hydra_looting_level(
                    effectiveSource
                )
            state["health"] = max(
                0.0, float(state["health"]) - healthDamage
            )
            self._begin_hydra_hurt_feedback(
                hydraKey, state, self._get_foot_pos(entityId)
            )
            if state["health"] <= 0.0:
                self._begin_hydra_death(hydraKey, state)
            else:
                self._set_health(hydraKey, state["health"])
                self._save_hydra_state(hydraKey, state)
            # Health-change callbacks run before the engine commits the event.
            # Defer the UI packet to the next completed server tick, coalescing
            # multiple same-tick impacts without waiting for the 10-tick poll.
            self._boss_sync_dirty = True
        return True

    def _remember_ur_ghast_player_attack(self, targetId, playerId):
        if targetId is None or playerId is None:
            return False
        if entity_registry_logic.matching_entity_key(
            self._ur_ghasts, targetId
        ) is None:
            return False
        for key, pending in list(
            self._pending_ur_ghast_player_attacks.items()
        ):
            if self._tick - int(pending.get("tick", -100)) > 4:
                self._pending_ur_ghast_player_attacks.pop(key, None)
        self._pending_ur_ghast_player_attacks[str(targetId)] = {
            "sourceId": playerId,
            "tick": self._tick,
        }
        return True

    def _set_ur_ghast_engine_health(self, bossId, state, value):
        bossKey = str(bossId)
        value = max(1.0, float(value))
        self._ur_ghast_internal_health_writes[bossKey] = {
            "expires": self._tick + 2,
            "value": value,
        }
        state["engineHealthMirror"] = value
        return self._set_health(bossId, value)

    def _ur_ghast_internal_health_write(self, bossId, args=None):
        key = str(bossId)
        marker = self._ur_ghast_internal_health_writes.get(key)
        if not isinstance(marker, dict):
            return False
        expires = int(marker.get("expires", -1))
        if expires < self._tick:
            self._ur_ghast_internal_health_writes.pop(key, None)
            return False
        if not isinstance(args, dict):
            return False
        try:
            toValue = float(
                args.get("to", args.get("toValue", float("nan")))
            )
            expected = float(marker.get("value"))
        except (TypeError, ValueError):
            return False
        if abs(toValue - expected) > 0.001:
            return False
        self._ur_ghast_internal_health_writes.pop(key, None)
        return True

    def _reconcile_ur_ghast_engine_health(self, bossId, state):
        expected = ur_ghast_logic.authoritative_engine_health(state)
        actual = self._get_health(bossId, expected)
        if abs(float(actual) - float(expected)) <= 0.01:
            state["engineHealthMirror"] = float(actual)
            return False
        self._entry_trace(
            "ur_ghast.health_reconcile",
            bossId=str(bossId),
            engineHealthBefore=round(float(actual), 4),
            engineHealthAfter=round(float(expected), 4),
            scriptHealth=round(float(state.get("health", 0.0)), 4),
            dying=bool(state.get("dying", False)),
        )
        self._set_ur_ghast_engine_health(
            bossId, state, expected
        )
        return True

    def _ur_ghast_owned_damage_source(self, bossId, sourceId, args):
        for key, projectile in list(
            self._ur_ghast_projectile_tombstones.items()
        ):
            if int(projectile.get("expires", -1)) < self._tick:
                self._ur_ghast_projectile_tombstones.pop(key, None)
        candidates = (
            sourceId,
            args.get("projectileId"),
            args.get("directEntityId"),
        )
        for projectileId in candidates:
            for registry in (
                self._ur_ghast_projectiles,
                self._ur_ghast_projectile_tombstones,
            ):
                projectileKey = entity_registry_logic.matching_entity_key(
                    registry, projectileId
                )
                if projectileKey is None:
                    continue
                projectile = registry.get(projectileKey) or {}
                if (
                    not projectile.get("reflected")
                    and str(projectile.get("ownerId")) == str(bossId)
                ):
                    return True
        if sourceId in (None, "", -1, "-1"):
            for registry in (
                self._ur_ghast_projectiles,
                self._ur_ghast_projectile_tombstones,
            ):
                for projectile in registry.values():
                    if (
                        not projectile.get("reflected")
                        and str(projectile.get("bossId")) == str(bossId)
                        and self._tick
                        - int(projectile.get("impactTick", -100)) <= 2
                    ):
                        return True
        return False

    def _ur_ghast_damage_owner(self, entityId, sourceId, args):
        if self._is_online_player(sourceId):
            return (sourceId, "health_event")
        possibleProjectileIds = (
            sourceId,
            args.get("projectileId"),
            args.get("directEntityId"),
        )
        for projectileId in possibleProjectileIds:
            for registry in (
                self._ur_ghast_projectiles,
                self._ur_ghast_projectile_tombstones,
            ):
                projectileKey = entity_registry_logic.matching_entity_key(
                    registry, projectileId
                )
                if projectileKey is None:
                    continue
                ownerId = registry[projectileKey].get("ownerId")
                if self._is_online_player(ownerId):
                    return (ownerId, "reflected_projectile")
        if sourceId not in (None, "", -1, "-1"):
            return (None, "unattributed_nonplayer_source")
        pending = self._pending_ur_ghast_player_attacks.pop(
            str(entityId), None
        )
        if pending is not None and (
            self._tick - int(pending.get("tick", -100)) <= 2
        ):
            ownerId = pending.get("sourceId")
            if self._is_online_player(ownerId):
                return (ownerId, "player_attack_correlation")
        return (None, "unattributed")

    def _resolve_ur_ghast_damage(self, args, entityId, sourceId):
        bossKey = entity_registry_logic.matching_entity_key(
            self._ur_ghasts, entityId
        )
        if bossKey is None:
            return False
        state = self._ur_ghasts[bossKey]
        if args.get("byScript") or self._ur_ghast_internal_health_write(
            bossKey, args
        ):
            return True
        if state.get("dying"):
            args["cancel"] = True
            self._set_ur_ghast_engine_health(bossKey, state, 1.0)
            return True
        try:
            fromValue = float(args.get("from", args.get("fromValue", state["health"])))
            toValue = float(args.get("to", args.get("toValue", fromValue)))
        except (TypeError, ValueError):
            return False
        if toValue >= fromValue:
            return False
        args["cancel"] = True
        engineHealthBefore = self._get_health(bossKey, fromValue)
        cause = args.get(
            "cause",
            args.get("damageCause", args.get("causeName")),
        )
        selfOwned = self._ur_ghast_owned_damage_source(
            bossKey, sourceId, args
        )
        if selfOwned:
            engineHealth = ur_ghast_logic.authoritative_engine_health(state)
            self._set_ur_ghast_engine_health(
                bossKey, state, engineHealth
            )
            self._entry_trace(
                "ur_ghast.damage_rejected",
                bossId=str(bossKey),
                reason="self_owned_projectile",
                sourceId=(
                    str(sourceId) if sourceId is not None else None
                ),
                projectileId=args.get("projectileId"),
                cause=cause,
                engineHealthBefore=round(float(engineHealthBefore), 4),
                engineHealthAfter=round(float(engineHealth), 4),
                scriptHealth=round(float(state.get("health", 0.0)), 4),
            )
            return True
        playerId, attribution = self._ur_ghast_damage_owner(
            entityId, sourceId, args
        )
        rawDamage = fromValue - toValue
        scriptHealthBefore = float(state.get("health", 0.0))
        result = ur_ghast_logic.apply_damage(
            state,
            rawDamage,
            playerId,
            track_phase=int(state.get("inTrapTicks", 0)) <= 0,
        )
        if result.get("accepted"):
            self._begin_ur_ghast_hurt_feedback(bossKey, state)
        self._entry_trace(
            "ur_ghast.damage",
            bossId=str(bossKey),
            sourceId=str(sourceId) if sourceId is not None else None,
            resolvedPlayerId=(
                str(playerId) if playerId is not None else None
            ),
            attribution=attribution,
            cause=cause,
            directEntityId=args.get("directEntityId"),
            projectileId=args.get("projectileId"),
            selfOwned=False,
            rawDamage=round(rawDamage, 4),
            effectiveDamage=round(
                float(result.get("effectiveDamage", 0.0)), 4
            ),
            damageUntilNextPhase=round(
                float(state.get("damageUntilNextPhase", 0.0)), 4
            ),
            phase=str(result.get("phase", state.get("phase", "normal"))),
            phaseToggled=bool(result.get("phaseToggled", False)),
            phaseReason=result.get("phaseReason"),
            health=round(float(state.get("health", 0.0)), 4),
            scriptHealthBefore=round(scriptHealthBefore, 4),
            scriptHealthAfter=round(float(state.get("health", 0.0)), 4),
            engineHealthBefore=round(float(engineHealthBefore), 4),
            engineHealthAfter=round(
                float(ur_ghast_logic.authoritative_engine_health(state)),
                4,
            ),
        )
        if result.get("phaseToggled") and result.get("phase") == "tantrum":
            self._begin_ur_ghast_tantrum(bossKey, state)
        elif result.get("phaseToggled"):
            self._broadcast_ur_ghast_effect(
                state,
                "storm_stop",
                (self._get_foot_pos(bossKey) or state.get("home"),),
                bossKey,
            )
        engineHealth = ur_ghast_logic.authoritative_engine_health(state)
        self._set_ur_ghast_engine_health(bossKey, state, engineHealth)
        if result.get("accepted"):
            state["lastLootingLevel"] = self._hydra_looting_level(playerId)
        self._save_ur_ghast_state(bossKey, state)
        self._boss_sync_dirty = True
        return True

    def _consume_life_charm_1(self, playerId):
        try:
            entries = self._keeping_inventory_entries(playerId)
        except Exception:
            return False
        for entry in entries:
            if portal_logic.item_name(entry.get("item") or {}) != "tf_slice:charm_of_life_1":
                continue
            replacement = copy.deepcopy(entry["item"])
            replacement["count"] = max(0, int(replacement.get("count", 1)) - 1)
            updates = {
                (entry["posType"], entry["slot"]): replacement if replacement["count"] else None
            }
            try:
                return CF.CreateItem(playerId).SetPlayerAllItems(updates) is not False
            except Exception:
                return False
        return False

    def _knight_projectile_damage_source(self, args, sourceId):
        candidates = (
            sourceId,
            args.get("projectileId"),
            args.get("directEntityId"),
            args.get("childId"),
        )
        for candidate in candidates:
            if candidate is None:
                continue
            key = entity_registry_logic.matching_entity_key(
                self._knight_projectiles, candidate
            )
            if key is not None:
                return True
            if self._get_engine_type(candidate) in (
                KNIGHT_AXE_PROJECTILE,
                KNIGHT_PICKAXE_PROJECTILE,
            ):
                return True
        return False

    def _record_lich_effect_damage(
        self, entityId, amount, sourceKind, handled, origin
    ):
        key = entity_registry_logic.matching_entity_key(
            self._recent_lich_effect_damage, entityId
        )
        if key is None:
            key = entityId
        self._recent_lich_effect_damage[key] = {
            "amount": max(0.0, float(amount)),
            "sourceKind": str(sourceKind),
            "handled": bool(handled),
            "origin": str(origin),
            "expires": self._tick + 1,
        }

    def _consume_lich_effect_damage(self, entityId, amount, expectedOrigin):
        key = entity_registry_logic.matching_entity_key(
            self._recent_lich_effect_damage, entityId
        )
        if key is None:
            return None
        marker = self._recent_lich_effect_damage.get(key) or {}
        if self._tick > int(marker.get("expires", -1)):
            self._recent_lich_effect_damage.pop(key, None)
            return None
        if str(marker.get("origin")) != str(expectedOrigin):
            return None
        try:
            matches = abs(
                float(marker.get("amount", -1.0)) - float(amount)
            ) <= 0.01
        except (TypeError, ValueError):
            matches = False
        if not matches:
            return None
        return self._recent_lich_effect_damage.pop(key, None)

    def OnGoblinDamageEvent(self, args):
        self._goblin_combat.on_damage(args)

    def OnActorHurtServerEvent(self, args):
        # Observational only: potion damage/recovery is owned by the effect
        # event. Applying it here too double-counts a single potion.
        try:
            damage = float(args.get("damage", 0.0))
        except (TypeError, ValueError):
            return
        if damage <= 0.0 or damage != damage or damage == float("inf"):
            return
        if self._lich_state(args.get("entityId")) is not None:
            self._entry_trace("lich.actor_hurt", **dict(args))

    def OnLichEffectDamage(self, args):
        entityId = args.get("entityId")
        state = self._lich_state(entityId)
        if state is None or state.get("dead") or state.get("dying"):
            return
        self._entry_trace("lich.effect_damage", **dict(args))
        try:
            raw = float(args.get("damage", 0.0))
            buff = int(args.get("attributeBuffType", -1))
        except (TypeError, ValueError):
            return
        if raw != raw or abs(raw) == float("inf"):
            return
        # Healing is damage to undead. Some custom actor runtimes report it
        # as ordinary recovery (4/8); convert to undead damage (6/12).
        # Harming is recovery for undead and must never remove a shield.
        sourceKind = lich_logic.effect_damage_source_kind(args.get("cause"), buff)
        zeroHealingContact = bool(buff == 3 and "damage" in args
                                  and raw == 0.0 and args.get("isInstantaneous", False))
        if buff == 3 and args.get("isInstantaneous", False):
            if raw > 0.0:
                amount = raw
            elif raw < 0.0:
                amount = -raw * 1.5
            else:
                amount = (
                    lich_logic.BASE_UNDEAD_HEALING_DAMAGE
                    if zeroHealingContact else 0.0
                )
        elif buff == 5 and sourceKind is not None and raw > 0.0:
            amount = raw
        else:
            return
        if amount <= 0.0:
            return
        existing = self._consume_lich_effect_damage(entityId, abs(raw), "health")
        if existing is not None and existing.get("handled"):
            return
        before = int(state["shieldStrength"])
        result = lich_logic.resolve_incoming_damage(state, "magic", amount)
        self._record_lich_effect_damage(entityId, abs(raw), "magic", True, "actor")
        self._set_health(entityId, state["health"])
        self._sync_lich_presentation(entityId, state)
        position = self._get_foot_pos(entityId)
        self._play_world_sound("random.break", position, 1.0, 1.0)
        self._broadcast_lich_effect(
            state.get("dimensionId"),
            "shield_break" if result.get("shieldDamage") else "shield_blocked",
            (position,), entityId,
        )
        self._entry_trace(
            "lich.effect_shield", entityId=str(entityId), raw=raw,
            resolved=amount, before=before, after=state["shieldStrength"],
            zeroHealingContact=zeroHealingContact,
        )
        self._save_lich_state(entityId, state)

    def OnHealthChangeBefore(self, args):
        entityId = args.get("entityId")
        lich = self._lich_state(entityId)
        if lich is not None:
            if args.get("byScript"):
                return
            # Shielded recovery is handled by EntityEffectDamage, including
            # the engine's non-undead interpretation of instant healing.
            if float(args.get("to", 0)) > float(args.get("from", 0)):
                if int(lich.get("shieldStrength", 0)) > 0:
                    args["cancel"] = True
                    return
                marker = self._consume_lich_effect_damage(
                    entityId, float(args["to"]) - float(args["from"]), "actor"
                )
                if marker is not None:
                    args["cancel"] = True
                    return
        sourceId = args.get(
            "sourceId",
            args.get(
                "srcId",
                args.get("attackerId", args.get("projectileId")),
            ),
        )
        try:
            incomingDamage = float(
                args.get("from", args.get("fromValue", 0.0))
            ) > float(args.get("to", args.get("toValue", 0.0)))
        except (TypeError, ValueError):
            incomingDamage = False
        if incomingDamage and self._protect_ur_ghast_fireball_health(
            args, entityId
        ):
            return
        if (
            incomingDamage
            and self._is_online_player(entityId)
            and self._try_block_knightmetal_damage(
                args, entityId, sourceId
            )
        ):
            return
        knightContext = (
            self._ruin_worldgen.knight_member_context(entityId)
            if incomingDamage and self._ruin_worldgen is not None else None
        )
        if isinstance(knightContext, dict):
            member = knightContext["member"]
            group = knightContext["group"]
            if member.get("dying", False):
                args["cancel"] = True
                self._set_health(entityId, 1.0)
                return
            try:
                fromValue = float(args.get("from", args.get("fromValue", member.get("health", 35.0))))
                toValue = float(args.get("to", args.get("toValue", fromValue)))
            except (TypeError, ValueError):
                fromValue, toValue = 35.0, 35.0
            damageCause = args.get(
                "cause", args.get("damageCause", "")
            )
            if knight_route_logic.ignores_environmental_damage(
                damageCause
            ):
                args["cancel"] = True
                member["health"] = fromValue
                self._set_health(entityId, fromValue)
                return
            if self._knight_projectile_damage_source(args, sourceId):
                args["cancel"] = True
                member["health"] = fromValue
                self._set_health(entityId, fromValue)
                return
            defenderPos = self._get_foot_pos(entityId)
            attackerPos = self._get_foot_pos(sourceId)
            fromFront = False
            if defenderPos is not None and attackerPos is not None:
                yaw = math.radians(self._get_rotation(entityId)[1])
                dx = float(attackerPos[0]) - float(defenderPos[0])
                dz = float(attackerPos[2]) - float(defenderPos[2])
                length = math.sqrt(dx * dx + dz * dz) or 1.0
                fromFront = (
                    (-math.sin(yaw)) * (dx / length)
                    + math.cos(yaw) * (dz / length)
                ) >= 0.0
            cause = str(
                args.get("cause", args.get("damageCause", ""))
            ).lower()
            shieldBypass = any(
                marker in cause for marker in (
                    "void", "suicide", "magic", "wither", "starve",
                    "drown", "fire", "lava", "fall", "suffocation",
                    "in_wall",
                )
            )
            if knight_route_logic.shield_blocks(
                member, fromFront, shieldBypass
            ):
                args["cancel"] = True
                self._set_health(entityId, fromValue)
                self._play_world_sound(
                    "item.shield.block", defenderPos, 1.0, 1.0
                )
                self._broadcast_knight_phantom_effect(
                    "shield_block", (defenderPos,), entityId
                )
                return
            multiplier = max(1.0, float(member.get("armorMultiplier", 5.0)))
            resolved = max(0.0, fromValue - max(0.0, fromValue - toValue) / multiplier)
            if self._is_online_player(sourceId):
                knight_route_logic.record_participant(group, sourceId)
            if resolved <= 0.0:
                slot = member.get("slot", member.get("number"))
                if knight_route_logic.begin_member_death(
                    group, slot, sourceId
                ):
                    args["cancel"] = True
                    self._set_health(entityId, 1.0)
                return
            member["health"] = resolved
            if "to" in args:
                args["to"] = resolved
            if "toValue" in args:
                args["toValue"] = resolved
        if incomingDamage and self._resolve_ur_ghast_damage(
            args, entityId, sourceId
        ):
            return
        if incomingDamage and self._is_online_player(entityId):
            try:
                fromValue = float(args.get("from", args.get("fromValue", 0.0)))
                toValue = float(args.get("to", args.get("toValue", fromValue)))
            except (TypeError, ValueError):
                fromValue, toValue = 0.0, 1.0
            charm = dark_tower_logic.consume_life_charm_1(
                toValue, fromValue, True
            )
            if charm.get("consumed") and self._consume_life_charm_1(entityId):
                if "to" in args:
                    args["to"] = float(charm["health"])
                if "toValue" in args:
                    args["toValue"] = float(charm["health"])
                self._set_health(entityId, float(charm["health"]))
                try:
                    CF.CreateEffect(entityId).AddEffectToEntity(
                        "regeneration", 5, 0, False
                    )
                except Exception:
                    pass
                return
        if self._resolve_hydra_damage(args, incomingDamage, sourceId):
            return
        loyalKey = entity_registry_logic.matching_entity_key(
            self._loyal_zombies, sourceId
        )
        targetLoyalKey = entity_registry_logic.matching_entity_key(
            self._loyal_zombies, entityId
        )
        if incomingDamage and loyalKey is not None:
            loyal = self._loyal_zombies.get(loyalKey) or {}
            targetLoyal = self._loyal_zombies.get(targetLoyalKey) or {}
            if (
                str(entityId) == str(loyal.get("ownerId"))
                or (
                    targetLoyalKey is not None
                    and str(targetLoyal.get("ownerId"))
                    == str(loyal.get("ownerId"))
                )
            ):
                args["cancel"] = True
                return
        shieldKey = entity_registry_logic.matching_entity_key(
            self._player_fortification, entityId
        )
        if incomingDamage and shieldKey is not None:
            shield = self._player_fortification[shieldKey]
            if scepter_logic.has_shield(shield):
                args["cancel"] = True
                shieldBroken = scepter_logic.break_shield(shield)
                if not shieldBroken:
                    return
                self._sync_fortification_visual(shieldKey, shield)
                position = self._get_foot_pos(entityId)
                dimensionId = self._get_dimension(entityId)
                if position is not None and dimensionId is not None:
                    self._play_world_sound(
                        "item.shield.block", position, 1.0, 1.0
                    )
                    self._broadcast_lich_effect(
                        dimensionId,
                        "fortification_block",
                        (position,),
                        entityId,
                    )
                return
        if (
            incomingDamage
            and sourceId is not None
            and not self._swarm_attack_is_allowed(sourceId)
        ):
            args["cancel"] = True
            return
        cloneKey = entity_registry_logic.matching_entity_key(
            self._lich_clones, entityId
        )
        if cloneKey is not None and incomingDamage:
            sourceKind, _ownerId, _projectile = self._lich_damage_source(
                entityId, sourceId, args
            )
            if lich_logic.clone_damage_is_blocked(sourceKind == "bypass"):
                args["cancel"] = True
                self._set_health(cloneKey, lich_logic.MAX_HEALTH)
                position = self._get_foot_pos(cloneKey)
                cloneState = self._lich_clones.get(cloneKey) or {}
                self._play_world_sound("random.fizz", position, 1.0, 2.0)
                self._broadcast_lich_effect(
                    cloneState.get("dimensionId"),
                    "clone_hurt",
                    (position,),
                    cloneKey,
                )
                return
        lichState = self._lich_state(entityId)
        if lichState is not None and incomingDamage:
            if lichState.get("dying") or lichState.get("dead"):
                args["cancel"] = True
                if lichState.get("dying"):
                    self._set_health(entityId, 1.0)
                return
            try:
                fromValue = float(
                    args.get(
                        "from", args.get("fromValue", lichState["health"])
                    )
                )
                toValue = float(
                    args.get("to", args.get("toValue", fromValue))
                )
            except (TypeError, ValueError):
                return
            amount = max(0.0, fromValue - toValue)
            effectMarker = self._consume_lich_effect_damage(
                entityId, amount, "actor"
            )
            if effectMarker is not None and effectMarker.get("handled"):
                args["cancel"] = True
                self._set_health(entityId, lichState["health"])
                self._save_lich_state(entityId, lichState)
                return
            sourceKind, ownerId, projectile = self._lich_damage_source(
                entityId, sourceId, args
            )
            cause = str(
                args.get("cause", args.get("damageCause", ""))
            ).lower()
            if "in_wall" in cause or "suffocation" in cause:
                targetPos = self._get_foot_pos(lichState.get("targetId"))
                if targetPos is not None:
                    self._teleport_lich(entityId, lichState, targetPos)
            result = lich_logic.resolve_incoming_damage(
                lichState, sourceKind, amount
            )
            if sourceKind in ("magic", "indirect_magic"):
                self._record_lich_effect_damage(
                    entityId, amount, sourceKind, True, "health"
                )
            ownerType = self._get_engine_type(ownerId)
            if (
                ownerId is not None
                and not result.get("shieldDamage")
                and (
                    self._is_online_player(ownerId)
                    or ownerType is not None
                )
            ):
                lichState["lastAttackerId"] = ownerId
            if self._is_online_player(ownerId) and result.get("healthDamage"):
                lichState["participants"].add(str(ownerId))
            if not result.get("accepted") or result.get("shieldDamage"):
                args["cancel"] = True
                self._set_health(entityId, lichState["health"])
            if result.get("shieldContact"):
                lichState["lastShieldContactTick"] = self._tick
                self._sync_lich_presentation(entityId, lichState)
                position = self._get_foot_pos(entityId)
                self._play_world_sound(
                    "random.break", position, 1.0, 1.0
                )
                self._broadcast_lich_effect(
                    lichState.get("dimensionId"),
                    (
                        "shield_break"
                        if result.get("shieldDamage")
                        else "shield_blocked"
                    ),
                    (position,),
                    entityId,
                )
            if result.get("healthDamage"):
                lichState["lastLootingLevel"] = self._hydra_looting_level(ownerId)
                lichState["lastAcceptedDamageTick"] = self._tick
                if float(lichState.get("health", 0.0)) <= 0.0:
                    args["cancel"] = True
                    self._set_health(entityId, 1.0)
                    self._begin_lich_death(entityId, lichState)
                    return
            self._save_lich_state(entityId, lichState)
            return
        if (
            incomingDamage
            and self._get_engine_type(entityId) == DEATH_TOME_IDENTIFIER
        ):
            cause = str(
                args.get("cause", args.get("damageCause", ""))
            ).lower()
            if "fire" in cause or "lava" in cause:
                try:
                    fromValue = float(
                        args.get("from", args.get("fromValue", 30.0))
                    )
                    toValue = float(
                        args.get("to", args.get("toValue", fromValue))
                    )
                    doubled = max(
                        0.0,
                        fromValue
                        - lich_logic.death_tome_incoming_damage(
                            fromValue - toValue, True
                        ),
                    )
                    if "to" in args:
                        args["to"] = doubled
                    if "toValue" in args:
                        args["toValue"] = doubled
                except (TypeError, ValueError):
                    pass
        segmentOwner = self._segment_owners.get(entityId)
        if incomingDamage and segmentOwner is not None:
            parentState = self._boss_state(segmentOwner[0])
            if parentState is not None:
                directId = args.get(
                    "directEntityId",
                    args.get("projectileId", args.get("childId")),
                )
                cause = args.get("cause", args.get("damageCause", ""))
                if naga_logic.naga_damage_is_blocked(
                    cause,
                    attacker_inside=self._damage_entity_inside_home(
                        sourceId, parentState
                    ),
                    direct_inside=self._damage_entity_inside_home(
                        directId, parentState
                    ),
                ):
                    args["cancel"] = True
                    return
        state = self._boss_state(entityId)
        if state is None:
            return
        if state.get("dead") or state.get("dying"):
            args["cancel"] = True
            if state.get("dying"):
                self._set_health(entityId, 1.0)
            return
        try:
            fromValue = float(
                args.get("from", args.get("fromValue", state["health"]))
            )
            toValue = float(args.get("to", args.get("toValue", fromValue)))
        except (TypeError, ValueError):
            return
        directId = args.get(
            "directEntityId",
            args.get("projectileId", args.get("childId")),
        )
        cause = args.get("cause", args.get("damageCause", ""))
        if toValue < fromValue and naga_logic.naga_damage_is_blocked(
            cause,
            attacker_inside=self._damage_entity_inside_home(
                sourceId, state
            ),
            direct_inside=self._damage_entity_inside_home(
                directId, state
            ),
        ):
            args["cancel"] = True
            return
        if toValue < fromValue:
            state["lastLootingLevel"] = self._hydra_looting_level(sourceId)
        if toValue <= 0.0 < fromValue:
            args["cancel"] = True
            self._set_health(entityId, 1.0)
            self._begin_naga_death(entityId, state, sourceId)
            return
        self._apply_boss_health_state(entityId, state, toValue)

    def OnActuallyHurtServerEvent(self, args):
        entityId = args.get("entityId")
        self._queue_flying_hurt_stabilization(entityId)
        attackerId = args.get(
            "srcId", args.get("sourceId", args.get("attackerId"))
        )
        ruinMobKey = entity_registry_logic.matching_entity_key(
            self._ruin_mobs, entityId
        )
        ruinMobState = (
            self._ruin_mobs.get(ruinMobKey)
            if ruinMobKey is not None else None
        )
        if (
            ruinMobState is not None
            and ruinMobState.get("type") == "tf_slice:fire_beetle"
            and attackerId is not None
            and str(attackerId) != str(entityId)
        ):
            ruinMobState["lastHurtById"] = str(attackerId)
        attackerType = self._get_engine_type(attackerId)
        attackerRuinKey = entity_registry_logic.matching_entity_key(
            self._ruin_mobs, attackerId
        )
        attackerRuinState = (
            self._ruin_mobs.get(attackerRuinKey)
            if attackerRuinKey is not None else None
        )
        try:
            dealtDamage = float(args.get("damage", 0.0)) > 0.0
        except (TypeError, ValueError):
            dealtDamage = False
        self._redcap_player_hurt(ruinMobState, attackerType, dealtDamage)
        if (
            dealtDamage
            and entityId is not None
            and attackerRuinState is not None
            and attackerRuinState.get("type") == "tf_slice:pinch_beetle"
        ):
            try:
                riddenEntityId = CF.CreateRide(entityId).GetEntityRider()
            except Exception:
                riddenEntityId = None
            riddenEntityType = (
                self._get_engine_type(riddenEntityId)
                if riddenEntityId not in (None, "", "-1") else None
            )
            if beetle_combat_logic.pinch_melee_can_grab(
                bool(self._ride_passengers(attackerId)), riddenEntityType
            ):
                self._grab_pinch_target(attackerId, entityId, False)
        if mosquito_swarm_logic.should_apply_hunger(
            attackerType, args.get("damage", 0.0)
        ):
            try:
                hungerSeconds = mosquito_swarm_logic.hunger_seconds(
                    self._difficulty()
                )
                CF.CreateEffect(entityId).AddEffectToEntity(
                    "hunger", hungerSeconds, 0, True
                )
            except Exception as error:
                print "[TwilightBossSlice] mosquito hunger failed:", error
        mortarKey = entity_registry_logic.matching_entity_key(
            self._hydra_mortars, entityId
        )
        if mortarKey is not None and attackerId is not None:
            self._reflect_hydra_mortar(entityId, attackerId)
            args["cancel"] = True
            return
        hurtMobKey = entity_registry_logic.matching_entity_key(
            self._phantom_urghast_mobs, entityId
        )
        hurtMobState = (
            self._phantom_urghast_mobs.get(hurtMobKey)
            if hurtMobKey is not None else None
        )
        if (
            hurtMobState is not None
            and hurtMobState.get("type") == TOWERWOOD_BORER_IDENTIFIER
        ):
            phantom_urghast_mob_logic.notify_borer_hurt(hurtMobState)
        attackerMobKey = entity_registry_logic.matching_entity_key(
            self._phantom_urghast_mobs, attackerId
        )
        attackerMobState = (
            self._phantom_urghast_mobs.get(attackerMobKey)
            if attackerMobKey is not None else None
        )
        if (
            attackerMobState is not None
            and attackerMobState.get("type") == CARMINITE_GOLEM_IDENTIFIER
            and entityId is not None
        ):
            hitResult = phantom_urghast_mob_logic.carminite_golem_hit_result()
            attackerMobState["attackTimer"] = int(hitResult["attackTimer"])
            self._add_entity_motion(
                entityId, 0.0, hitResult["verticalMotion"], 0.0
            )
        if dealtDamage and attackerId is not None and self._is_online_player(entityId):
            try:
                itemPos = serverApi.GetMinecraftEnum().ItemPosType
                armor = CF.CreateItem(entityId).GetPlayerAllItems(
                    itemPos.ARMOR, True
                ) or ()
            except Exception:
                armor = ()
            totalLevel = min(3, sum(self._fire_react_level(item) for item in armor))
            if totalLevel and random.random() < route_progression_logic.fire_react_chance(totalLevel):
                seconds = route_progression_logic.fire_react_seconds(
                    totalLevel, random.randint(0, totalLevel - 1)
                )
                self._set_entity_on_fire(attackerId, seconds)
        routeKey = entity_registry_logic.matching_entity_key(
            self._route_mobs, entityId
        )
        if routeKey is not None and self._is_online_player(attackerId):
            self._route_mobs[routeKey].setdefault("participants", set()).add(
                str(attackerId)
            )
            if self._route_mobs[routeKey].get("type") == MINOSHROOM_IDENTIFIER:
                self._route_mobs[routeKey]["lastLootingLevel"] = self._hydra_looting_level(attackerId)
                self._save_minoshroom_state(
                    routeKey, self._route_mobs[routeKey]
                )
        projectileKey = entity_registry_logic.matching_entity_key(
            self._lich_projectiles, entityId
        )
        if projectileKey is not None and attackerId is not None:
            projectile = self._lich_projectiles[projectileKey]
            if projectile.get("type") == LICH_BOMB_IDENTIFIER:
                self._trigger_entity_event(entityId, "tf_slice:explode")
            elif projectile.get("type") == LICH_BOLT_IDENTIFIER:
                rotation = self._get_rotation(attackerId)
                pitch = math.radians(float(rotation[0]))
                yaw = math.radians(float(rotation[1]))
                look = (
                    -math.sin(yaw) * math.cos(pitch),
                    -math.sin(pitch),
                    math.cos(yaw) * math.cos(pitch),
                )
                reflected = lich_logic.reflect_bolt(
                    attackerId, look, random
                )
                projectile["ownerId"] = attackerId
                projectile["reflected"] = True
                projectile["velocity"] = reflected["velocity"]
                try:
                    CF.CreateActorMotion(entityId).SetMotion(
                        reflected["velocity"]
                    )
                except Exception:
                    pass
            return
        minionKey = entity_registry_logic.matching_entity_key(
            self._lich_minions, entityId
        )
        attackerCloneKey = entity_registry_logic.matching_entity_key(
            self._lich_clones, attackerId
        )
        if (
            minionKey is not None
            and (
                self._lich_state(attackerId) is not None
                or attackerCloneKey is not None
            )
        ):
            _projectileId, damageProjectile = self._lich_damage_projectile(
                entityId, attackerId, args
            )
            if not damageProjectile:
                try:
                    effect = CF.CreateEffect(entityId)
                    effect.AddEffectToEntity("speed", 10, 4, True)
                    effect.AddEffectToEntity("strength", 10, 1, True)
                except Exception:
                    pass
                minionState = self._lich_minions.get(minionKey)
                if minionState is not None:
                    minionState["strengthUntil"] = self._tick + 200
                self._trigger_entity_event(
                    entityId, "tf_slice:set_strengthened"
                )
        tinyBird = self._tiny_birds.get(entityId)
        if tinyBird is not None:
            tinyBird["spookedUntil"] = self._tick + 100
        lichState = self._lich_state(entityId)
        if (
            lichState is not None
            and not lichState.get("dead")
            and not lichState.get("dying")
        ):
            lichState["health"] = self._get_health(
                entityId, lichState["health"]
            )
            acceptedRecently = (
                self._tick
                - int(lichState.get("lastAcceptedDamageTick", -100))
                <= 1
            )
            if acceptedRecently and lich_logic.should_teleport_after_hurt(
                lichState.get("phase", 1), random
            ):
                self._teleport_lich(
                    entityId,
                    lichState,
                    self._get_foot_pos(lichState.get("targetId"))
                    or self._get_foot_pos(attackerId),
                )
            self._save_lich_state(entityId, lichState)
            return
        owner = self._segment_owners.get(entityId)
        if owner is not None:
            bossId, _ = owner
            state = self._boss_state(bossId)
            if state is None or state.get("dead") or state.get("dying"):
                return
            try:
                damage = max(0.0, float(args.get("damage", 0.0)))
            except (TypeError, ValueError):
                return
            self._set_health(entityId, 1000.0)
            attackerId = args.get(
                "srcId", args.get("sourceId", args.get("attackerId"))
            )
            if damage > 0.0 and self._is_online_player(attackerId):
                state["participants"].add(str(attackerId))
                self._save_naga_state(bossId, state)
            self._hurt(bossId, damage * (2.0 / 3.0), attackerId)
            return
        state = self._boss_state(entityId)
        if state is None or state.get("dead") or state.get("dying"):
            return
        if state["suppressDamageEvents"] > 0:
            state["suppressDamageEvents"] -= 1
            state["ticksSinceDamaged"] = 0
            self._apply_boss_health_state(
                entityId,
                state,
                self._get_health(entityId, state["health"]),
            )
            self._save_naga_state(entityId, state)
            return
        try:
            damage = max(0.0, float(args.get("damage", 0.0)))
        except (TypeError, ValueError):
            return
        if damage > 0.0 and self._is_online_player(attackerId):
            state["participants"].add(str(attackerId))
        state["ticksSinceDamaged"] = 0
        previous = state["brain"].state
        state["brain"].record_damage(damage)
        self._on_state_changed(entityId, state, previous)
        self._apply_boss_health_state(
            entityId,
            state,
            self._get_health(entityId, state["health"]),
        )
        self._save_naga_state(entityId, state)

    def _queue_flying_hurt_stabilization(self, entityId):
        if entityId is None or not flight_logic.requires_hurt_stabilization(
            self._get_engine_type(entityId)
        ):
            return False
        data = {"entityId": entityId}
        try:
            # Run after the engine has committed its hurt-knockback velocity.
            CF.CreateGame(LEVEL_ID).AddTimer(
                0.05, self._stabilize_flying_hurt, data
            )
            return True
        except Exception:
            return self._stabilize_flying_hurt(data)

    def _stabilize_flying_hurt(self, data):
        entityId = data.get("entityId") if isinstance(data, dict) else data
        if entityId is None or not flight_logic.requires_hurt_stabilization(
            self._get_engine_type(entityId)
        ):
            return False
        try:
            motion = CF.CreateActorMotion(entityId).GetMotion()
            if motion is None:
                return False
            return self._set_full_motion(
                entityId, flight_logic.stabilized_hurt_motion(motion)
            ) is not False
        except Exception:
            return False

    def OnMobHitBlock(self, args):
        entityId = args.get("entityId")
        state = self._boss_state(entityId)
        if state is None or state.get("dead"):
            return
        pos = (
            int(args.get("posX", args.get("x", 0))),
            int(args.get("posY", args.get("y", 0))),
            int(args.get("posZ", args.get("z", 0))),
        )
        bossPos = self._get_foot_pos(entityId)
        outsideHome = bool(
            bossPos is not None
            and state.get("home") is not None
            and not naga_logic.inside_home(bossPos, state["home"])
        )
        blockName = args.get("blockName", args.get("blockId"))
        self._destroy_block(
            args.get("dimensionId", state["dimensionId"]),
            pos,
            state["brain"].state,
            outsideHome=outsideHome,
            knownBlockName=blockName,
        )

    def _refresh_trophy_stack_sizes(self, playerId):
        getattr(self, "_pending_trophy_stack_refresh", set()).discard(playerId)
        try:
            itemPos = serverApi.GetMinecraftEnum().ItemPosType
            comp = CF.CreateItem(playerId)
            inventory = comp.GetPlayerAllItems(itemPos.INVENTORY, True) or ()
            if not hasattr(self, "_trophy_stack_snapshots"):
                self._trophy_stack_snapshots = {}
            confirmed = self._trophy_stack_snapshots.setdefault(playerId, {})
            occupied = set()
            updates = {}
            for slot, item in enumerate(inventory):
                if portal_logic.item_name(item or {}) not in public_block_logic.TROPHY_ITEM_NAMES:
                    continue
                occupied.add(slot)
                if confirmed.get(slot) == item:
                    continue
                adjusted = copy.deepcopy(item)
                # Native head-slot eligibility forces the type's default to
                # one. NetEase's persisted per-stack override keeps 64 without
                # moving anything into armor or touching another item type.
                if not comp.SetMaxStackSize(adjusted, 64):
                    print("[TwilightBossSlice] trophy stack override failed", playerId, slot)
                    continue
                # The SDK can update backing item data without changing the
                # Python dictionary. A successful setter still needs writeback.
                updates[(itemPos.INVENTORY, slot)] = adjusted
            for slot in list(confirmed):
                if slot not in occupied:
                    confirmed.pop(slot, None)
            if updates:
                result = comp.SetPlayerAllItems(updates)
                if not isinstance(result, dict) or not all(result.get(key, False) for key in updates):
                    print("[TwilightBossSlice] trophy stack refresh incomplete", playerId)
                committed = 0
                for key, updated in updates.items():
                    if not isinstance(result, dict) or not result.get(key, False):
                        confirmed.pop(key[1], None)
                        continue
                    current = comp.GetPlayerItem(key[0], key[1], True) or {}
                    if (portal_logic.item_name(current) == portal_logic.item_name(updated)
                            and current.get("count") == updated.get("count")):
                        confirmed[key[1]] = copy.deepcopy(current)
                        committed += 1
                    else:
                        confirmed.pop(key[1], None)
                if committed:
                    print("[TwilightBossSlice] trophy stack writeback", playerId, committed, "slots", "requested_limit=64")
        except Exception as error:
            print("[TwilightBossSlice] trophy stack refresh failed", playerId, error)

    def _queue_trophy_stack_refresh(self, playerId):
        if playerId is None:
            return
        if not hasattr(self, "_pending_trophy_stack_refresh"):
            self._pending_trophy_stack_refresh = set()
        if playerId in self._pending_trophy_stack_refresh:
            return
        self._pending_trophy_stack_refresh.add(playerId)
        try:
            CF.CreateGame(LEVEL_ID).AddTimer(0.05, self._refresh_trophy_stack_sizes, playerId)
        except Exception as error:
            self._pending_trophy_stack_refresh.discard(playerId)
            print("[TwilightBossSlice] trophy stack timer failed", playerId, error)

    def OnTrophyStackItemEvent(self, args):
        items = (args.get("itemDict"), args.get("newItemDict"))
        if any(portal_logic.item_name(item or {}) in public_block_logic.TROPHY_ITEM_NAMES for item in items):
            playerId = args.get("playerId", args.get("actor"))
            # A newly acquired, identical stack can reuse an inventory slot.
            # Holding the same stack, however, must not start a write loop.
            if args.get("actor") is not None:
                getattr(self, "_trophy_stack_snapshots", {}).pop(playerId, None)
            self._queue_trophy_stack_refresh(playerId)

    def _try_equip_trophy(self, args):
        requested = args.get("itemDict") or args.get("item") or {}
        itemName = portal_logic.item_name(requested)
        if itemName not in public_block_logic.TROPHY_ITEM_NAMES:
            return False
        if args.get("cancel"):
            return True
        args["cancel"] = True
        playerId = args.get("playerId")
        if playerId is None:
            return True
        try:
            itemPos = serverApi.GetMinecraftEnum().ItemPosType
            itemComp = CF.CreateItem(playerId)
            carried = itemComp.GetPlayerItem(itemPos.CARRIED, 0, True) or {}
            # A delayed click must never consume a newly selected/replaced stack.
            if portal_logic.item_name(carried) != itemName:
                return True
            for key in ("count", "extraId"):
                if key in requested and requested[key] != carried.get(key):
                    return True
            head = itemComp.GetPlayerItem(itemPos.ARMOR, 0, True) or {}
            if portal_logic.item_name(head) in ("", "minecraft:air"):
                head = None
            split = public_block_logic.split_trophy_for_head(carried, head)
            if split is None:
                return True
            remaining, equipped = split
            updates = {
                (itemPos.CARRIED, 0): remaining,
                (itemPos.ARMOR, 0): equipped,
            }
            before = {(itemPos.CARRIED, 0): carried, (itemPos.ARMOR, 0): head}
            try:
                result = itemComp.SetPlayerAllItems(updates)
            except Exception:
                result = None
            if not isinstance(result, dict) or not all(result.get(key, False) for key in updates):
                # The SDK reports success per slot. Undo only successful writes
                # so a failed armor-slot update cannot consume an item.
                if isinstance(result, dict):
                    rollback = {key: before[key] for key in updates if result.get(key, False)}
                else:
                    rollback = {
                        key: before[key] for key in updates
                        if (itemComp.GetPlayerItem(key[0], key[1], True) or None) == updates[key]
                    }
                if rollback:
                    restored = itemComp.SetPlayerAllItems(rollback)
                    if not isinstance(restored, dict) or not all(restored.get(key, False) for key in rollback):
                        print("[TwilightBossSlice] trophy equip rollback failed", playerId)
        except Exception as error:
            print("[TwilightBossSlice] trophy equip failed", playerId, error)
        return True

    def _queue_trophy_equip(self, args):
        item = args.get("itemDict") or args.get("item") or {}
        if portal_logic.item_name(item) not in public_block_logic.TROPHY_ITEM_NAMES:
            return False
        if args.get("cancel"):
            return True
        args["cancel"] = True
        playerId = args.get("playerId")
        if playerId is None:
            return True
        if not hasattr(self, "_pending_trophy_equips"):
            self._pending_trophy_equips = {}
        if playerId in self._pending_trophy_equips:
            return True
        request = {"playerId": playerId, "itemDict": copy.deepcopy(item), "tick": self._tick}
        self._pending_trophy_equips[playerId] = request
        try:
            # Defer until the same click's block-placement event has completed.
            CF.CreateGame(LEVEL_ID).AddTimer(0.05, self._finish_trophy_equip, request)
        except Exception as error:
            self._pending_trophy_equips.pop(playerId, None)
            print("[TwilightBossSlice] trophy equip timer failed", playerId, error)
        return True

    def _finish_trophy_equip(self, request):
        playerId = request["playerId"]
        if self._pending_trophy_equips.pop(playerId, None) is not request:
            return
        blockTick = getattr(self, "_trophy_block_use_ticks", {}).get(playerId, -10)
        if blockTick >= request["tick"] - 1:
            return
        self._try_equip_trophy(request)

    def _mark_trophy_block_use(self, args, itemName):
        if itemName not in public_block_logic.TROPHY_ITEM_NAMES:
            return False
        if not hasattr(self, "_trophy_block_use_ticks"):
            self._trophy_block_use_ticks = {}
        playerId = args.get("playerId", args.get("entityId"))
        self._trophy_block_use_ticks[playerId] = self._tick
        return True

    def OnClientReady(self, args):
        playerId = args.get("playerId")
        if playerId is not None:
            getattr(self, "_trophy_stack_snapshots", {}).pop(playerId, None)
            self._queue_trophy_stack_refresh(playerId)
            self._known_players.add(playerId)
            self.NotifyToClient(
                playerId, "BossSync", self._make_sync_packet(playerId)
            )
            self.NotifyToClient(
                playerId, "PerfSync", self._make_perf_packet()
            )
            if self._get_dimension(playerId) == config.DIMENSION_ID:
                self._delay_fire_swamp_discovery(playerId)
                if not self._queue_portal_recovery(playerId):
                    self._pending_portal_recovery_players.add(playerId)

    def OnDimensionChangeServerEvent(self, args):
        playerId = args.get("playerId")
        self._entry_trace(
            "dimension.event.start",
            playerId=playerId,
            fromDimensionId=args.get("fromDimensionId"),
            toDimensionId=args.get("toDimensionId"),
            fromPos=(
                args.get("fromX"),
                args.get("fromY"),
                args.get("fromZ"),
            ),
        )
        if playerId is None:
            return
        if not hasattr(self, "_dimension_change_in_progress"):
            self._dimension_change_in_progress = set()
        if not hasattr(self, "_dimension_worldgen_ready_ticks"):
            self._dimension_worldgen_ready_ticks = {}
        self._dimension_change_in_progress.add(playerId)
        self._dimension_worldgen_ready_ticks.pop(playerId, None)
        if (
            args.get("toDimensionId") != config.DIMENSION_ID
            or args.get("fromDimensionId") == config.DIMENSION_ID
        ):
            return
        request = self._pending_portal_entries.get(playerId)
        point = request.get("returnPoint") if request is not None else None
        if point is None:
            try:
                point = {
                    "dimensionId": int(args.get("fromDimensionId")),
                    "pos": portal_logic.player_foot_from_position(
                        (
                            float(args.get("fromX")),
                            float(args.get("fromY")),
                            float(args.get("fromZ")),
                        )
                    ),
                }
            except (TypeError, ValueError):
                return
        self._store_return_point(playerId, point)
        print (
            "[TwilightBossSlice] portal source captured from dimension event:",
            playerId,
            point["dimensionId"],
            point["pos"],
        )

    def OnDimensionChangeFinish(self, args):
        playerId = args.get("playerId")
        self._entry_trace(
            "dimension.event.finish",
            playerId=playerId,
            fromDimensionId=args.get("fromDimensionId"),
            toDimensionId=args.get("toDimensionId"),
            toPos=args.get("toPos"),
        )
        if playerId is not None:
            self._known_players.add(playerId)
        arrivedInTwilight = (
            args.get("toDimensionId") == config.DIMENSION_ID
            or self._get_dimension(playerId) == config.DIMENSION_ID
        )
        if not hasattr(self, "_dimension_change_in_progress"):
            self._dimension_change_in_progress = set()
        if not hasattr(self, "_dimension_worldgen_ready_ticks"):
            self._dimension_worldgen_ready_ticks = {}
        self._dimension_change_in_progress.discard(playerId)
        if arrivedInTwilight and playerId is not None:
            self._dimension_worldgen_ready_ticks[playerId] = (
                self._tick + DIMENSION_NATIVE_COMPONENT_GRACE_TICKS
            )
        else:
            self._dimension_worldgen_ready_ticks.pop(playerId, None)
        if arrivedInTwilight:
            self._delay_fire_swamp_discovery(playerId)
            self._configure_twilight_time()
        elif playerId is not None:
            self._fire_swamp_discovery_ready_ticks.pop(playerId, None)
            self._fire_swamp_discovery_queue = []
        request = self._pending_portal_entries.get(playerId)
        if request is None:
            if arrivedInTwilight:
                targetPos = portal_logic.player_foot_from_position(
                    args.get("toPos")
                )
                if not self._queue_portal_recovery(
                    playerId,
                    targetPos=targetPos,
                ):
                    self._pending_portal_recovery_players.add(playerId)
            return
        if not arrivedInTwilight:
            return
        request["nativeChangeFinishedAt"] = self._portal_now_seconds()
        if request.get("bootstrapEntry"):
            if request.get("directEntry"):
                prepared = self._prepare_direct_portal_arrival(
                    playerId,
                    request,
                )
            else:
                prepared = self._prepare_staged_portal_relocation(
                    playerId,
                    request,
                )
            if not prepared:
                self._pending_portal_entries.pop(playerId, None)
                self._pending_portal_recovery_players.add(playerId)
            return
        self._finish_portal_arrival(playerId, request)

    def OnPlayerDropItem(self, args):
        playerId = args.get("playerId")
        itemEntityId = args.get("itemEntityId")
        if playerId is None or itemEntityId is None:
            return
        self._known_players.add(playerId)
        if len(self._pending_catalysts) >= config.MAX_PENDING_CATALYSTS:
            oldest = sorted(
                self._pending_catalysts.items(),
                key=lambda entry: entry[1]["expires"],
            )[0][0]
            self._pending_catalysts.pop(oldest, None)
        self._pending_catalysts[itemEntityId] = {
            "playerId": playerId,
            "dimensionId": self._get_dimension(playerId),
            "pos": self._get_foot_pos(playerId),
            "expires": self._tick + config.PORTAL_CATALYST_TIMEOUT_TICKS,
        }
        self._pending_quest_offerings[itemEntityId] = {
            "playerId": playerId,
            "expires": None,
        }

    def _consume_one_carried_item(self, playerId):
        if self._is_creative(playerId):
            return (True, None)
        current = self._carried_item(playerId)
        if not current:
            return (False, None)
        replacement = copy.deepcopy(current)
        replacement["count"] = max(0, int(current.get("count", 1)) - 1)
        return (self._set_carried_item(playerId, replacement), current)

    def _try_transformation_powder(self, args):
        playerId = args.get("playerId")
        targetId = args.get(
            "interactEntityId",
            args.get("victimId", args.get("entityId")),
        )
        if playerId is None or targetId is None:
            return False
        item = args.get("itemDict") or self._carried_item(playerId) or {}
        if portal_logic.item_name(item) != "tf_slice:transformation_powder":
            return False
        try:
            if not CF.CreateGame(LEVEL_ID).IsEntityAlive(targetId):
                return False
        except Exception:
            return False
        targetName = self._get_engine_type(targetId)
        replacementName = transformation_logic.target_for_entity(targetName)
        if replacementName is None:
            return False
        ownerId = None
        if targetName in transformation_logic.OWNABLE_TRANSFORMATION_SOURCES:
            try:
                ownerId = CF.CreateTame(targetId).GetOwnerId()
            except Exception:
                ownerId = None
        if not transformation_logic.owner_allows_transform(
            targetName, ownerId, playerId
        ):
            return False
        position = self._get_foot_pos(targetId)
        dimensionId = self._get_dimension(targetId)
        if position is None or dimensionId is None:
            return False
        try:
            rotation = CF.CreateRot(targetId).GetRot() or (0.0, 0.0)
        except Exception:
            rotation = (0.0, 0.0)

        consumed, original = self._consume_one_carried_item(playerId)
        if not consumed:
            return False
        try:
            replacementId = self.CreateEngineEntityByTypeStr(
                str(replacementName),
                tuple(position),
                tuple(rotation),
                int(dimensionId),
                False,
                False,
            )
        except Exception as error:
            replacementId = None
            print "[TwilightBossSlice] transformation spawn failed:", error
        if not self._valid_entity_id(replacementId):
            if original is not None:
                self._set_carried_item(playerId, original)
            return False
        try:
            removed = self.DestroyEntity(targetId)
        except Exception as error:
            removed = False
            print "[TwilightBossSlice] transformation removal failed:", error
        if removed is False:
            try:
                self.DestroyEntity(replacementId)
            except Exception:
                pass
            if original is not None:
                self._set_carried_item(playerId, original)
            return False

        args["cancel"] = True
        args["ret"] = True
        self._play_world_sound("random.fizz", position, 0.8, 1.2)
        return True

    def OnPlayerDoInteractServerEvent(self, args):
        if self._try_transformation_powder(args):
            return
        playerId = args.get("playerId")
        ramId = args.get(
            "interactEntityId",
            args.get("victimId", args.get("entityId")),
        )
        if (
            playerId is None
            or ramId is None
            or self._get_engine_type(ramId) != QUEST_RAM_IDENTIFIER
        ):
            return
        item = args.get("itemDict") or self._carried_item(playerId) or {}
        itemName = portal_logic.item_name(item)
        color = quest_ram_logic.WOOL_ITEMS.get(itemName)
        if color is None:
            return
        state = self._quest_ram_state(ramId)
        result = quest_ram_logic.feed_wool(
            state["mask"],
            state["rewarded"],
            color,
        )
        if not result["accepted"]:
            return
        consumed, original = self._consume_one_carried_item(playerId)
        if not consumed:
            return
        if not self._save_quest_ram_state(ramId, result):
            if original is not None:
                self._set_carried_item(playerId, original)
            return
        if result["reward_due"]:
            self._drop_quest_ram_rewards(ramId)
        self._notify_quest_ram_progress(playerId, result)
        args["cancel"] = True

    @staticmethod
    def _valid_magic_map_clone_source(item):
        if not isinstance(item, dict):
            return False
        if portal_logic.item_name(item) == config.FILLED_MAZE_MAP_ITEM:
            return maze_map_logic.decode_identity(item.get("extraId")) is not None
        return (
            portal_logic.item_name(item) == config.FILLED_MAGIC_MAP_ITEM
            and magic_map_logic.decode_map_identity(item.get("extraId"))
            is not None
        )

    def OnMagicMapCraftingInputChanged(self, args):
        playerId = args.get("playerId")
        if playerId is None:
            return
        try:
            slot = int(args.get("slot"))
            uiSlot = serverApi.GetMinecraftEnum().PlayerUISlot
            craftingSlots = set(
                range(
                    int(uiSlot.Crafting2x2Input1),
                    int(uiSlot.Crafting2x2Input4) + 1,
                )
            )
            craftingSlots.update(
                range(
                    int(uiSlot.Crafting3x3Input1),
                    int(uiSlot.Crafting3x3Input9) + 1,
                )
            )
            if slot not in craftingSlots:
                return
        except (TypeError, ValueError):
            return
        for item in (
            args.get("newItemDict"),
            args.get("oldItemDict"),
        ):
            if self._valid_magic_map_clone_source(item):
                self._pending_magic_map_clone_sources[playerId] = {
                    "item": copy.deepcopy(item),
                    "expires": self._tick + 40,
                }
                return

    def OnMagicMapCrafted(self, args):
        playerId = args.get("playerId")
        result = args.get("itemDict") or {}
        if (
            playerId is None
            or portal_logic.item_name(result)
            not in (config.FILLED_MAGIC_MAP_ITEM, config.FILLED_MAZE_MAP_ITEM)
            or self._valid_magic_map_clone_source(result)
        ):
            return
        pending = self._pending_magic_map_clone_sources.get(playerId)
        if (
            not isinstance(pending, dict)
            or int(pending.get("expires", 0)) < self._tick
            or not self._valid_magic_map_clone_source(pending.get("item"))
            or portal_logic.item_name(pending.get("item")) != portal_logic.item_name(result)
        ):
            return
        try:
            outputCount = int(result.get("count", 0))
            cloned = magic_map_logic.clone_magic_map_stack(
                pending["item"],
                outputCount - 1,
            )
        except (TypeError, ValueError):
            return
        # Some engine builds honor the mutated event item immediately.  The
        # timer below repairs cursor/shift-click outputs on builds that copy it.
        args["itemDict"] = copy.deepcopy(cloned)
        self._pending_magic_map_clone_sources.pop(playerId, None)
        try:
            CF.CreateGame(LEVEL_ID).AddTimer(
                0.05,
                self._repair_cloned_magic_map,
                {"playerId": playerId, "item": cloned},
            )
        except Exception:
            self._repair_cloned_magic_map(
                {"playerId": playerId, "item": cloned}
            )

    def _repair_cloned_magic_map(self, data):
        playerId = data.get("playerId")
        source = data.get("item")
        if playerId is None or not self._valid_magic_map_clone_source(source):
            return False
        expectedCount = max(2, int(source.get("count", 2)))
        itemComp = CF.CreateItem(playerId)
        try:
            cursorSlot = serverApi.GetMinecraftEnum().PlayerUISlot.CursorSelected
            cursor = itemComp.GetPlayerUIItem(
                playerId,
                cursorSlot,
                True,
            )
            if (
                portal_logic.item_name(cursor)
                == portal_logic.item_name(source)
                and not self._valid_magic_map_clone_source(cursor)
                and int((cursor or {}).get("count", 0)) == expectedCount
            ):
                replacement = copy.deepcopy(source)
                replacement["count"] = expectedCount
                if itemComp.SetPlayerUIItem(
                    playerId,
                    cursorSlot,
                    replacement,
                    False,
                ):
                    return True
        except Exception:
            pass
        try:
            itemPos = serverApi.GetMinecraftEnum().ItemPosType
            updates = {}
            for posType in (
                itemPos.CARRIED,
                itemPos.OFFHAND,
                itemPos.INVENTORY,
            ):
                items = itemComp.GetPlayerAllItems(posType, True) or ()
                for slot, item in enumerate(items):
                    if (
                        portal_logic.item_name(item)
                        == portal_logic.item_name(source)
                        and not self._valid_magic_map_clone_source(item)
                        and int((item or {}).get("count", 0))
                        == expectedCount
                    ):
                        replacement = copy.deepcopy(source)
                        replacement["count"] = expectedCount
                        updates[(posType, slot)] = replacement
                        break
                if updates:
                    break
            if not updates:
                return False
            result = itemComp.SetPlayerAllItems(updates)
            return all(bool(value) for value in result.values())
        except Exception as error:
            print "[TwilightBossSlice] magic map clone repair failed:", error
            return False

    def _carried_charge(self, playerId):
        try:
            itemComp = CF.CreateItem(playerId)
            posType = serverApi.GetMinecraftEnum().ItemPosType.CARRIED
            return max(0, int(itemComp.GetItemDurability(posType, 0)))
        except Exception:
            return 0

    def _spawn_player_projectile(self, projectileType, playerId, speed):
        position = self._get_foot_pos(playerId)
        dimensionId = self._get_dimension(playerId)
        if position is None or dimensionId is None:
            return None
        rotation = self._get_rotation(playerId)
        pitch = math.radians(float(rotation[0]))
        yaw = math.radians(float(rotation[1]))
        look = (
            -math.sin(yaw) * math.cos(pitch),
            -math.sin(pitch),
            math.cos(yaw) * math.cos(pitch),
        )
        spawnPosition = scepter_logic.player_projectile_spawn_position(position, look)
        projectileId = self._spawn_ruin_entity(
            projectileType,
            spawnPosition,
            rotation[1],
            dimensionId,
        )
        if not projectileId:
            return None
        velocity = tuple(float(value) * float(speed) for value in look)
        try:
            CF.CreateActorMotion(projectileId).SetMotion(velocity)
        except Exception:
            pass
        self._lich_projectiles[projectileId] = (
            lich_logic.new_projectile_state(
                projectileType,
                playerId,
                self._tick,
                velocity,
                projectileType == LICH_BOLT_IDENTIFIER,
            )
        )
        self._play_world_sound("mob.ghast.fireball", position, 1.0, 1.0)
        self._broadcast_lich_effect(
            dimensionId,
            "projectile_launch",
            (spawnPosition,),
            projectileId,
            style=str(projectileType),
        )
        return projectileId

    def _use_lich_scepter(self, playerId, itemName):
        kind = str(itemName).split(":", 1)[-1]
        charges = self._carried_charge(playerId)
        if charges <= 0:
            self._notify(playerId, u"\u6743\u6756\u5df2\u7ecf\u8017\u5c3d\u3002", "RED")
            return True
        scepterState = scepter_logic.new_scepter_state(kind, charges)
        if kind == "twilight_scepter":
            result = scepter_logic.use_twilight_scepter(scepterState)
            if result.get("used"):
                projectileId = self._spawn_player_projectile(
                    result["projectile"], playerId, result["speed"]
                )
                if projectileId and not self._consume_carried_charge(playerId):
                    self._lich_projectiles.pop(projectileId, None)
                    self.DestroyEntity(projectileId)
            return True
        if kind == "lifedrain_scepter":
            self._lifedrain_users[playerId] = {
                "ticks": 0,
                "missTicks": 0,
                "scepter": scepterState,
            }
            return True
        if kind == "zombie_scepter":
            result = scepter_logic.use_zombie_scepter(
                scepterState, playerId
            )
            if not result.get("used"):
                return True
            position = self._get_foot_pos(playerId)
            dimensionId = self._get_dimension(playerId)
            if position is None or dimensionId is None:
                return True
            rotation = self._get_rotation(playerId)
            pitch = math.radians(float(rotation[0]))
            yaw = math.radians(float(rotation[1]))
            look = (
                -math.sin(yaw) * math.cos(pitch),
                -math.sin(pitch),
                math.cos(yaw) * math.cos(pitch),
            )
            origin = (
                float(position[0]),
                float(position[1])
                + scepter_logic.PLAYER_PROJECTILE_EYE_HEIGHT,
                float(position[2]),
            )
            spawnPosition = scepter_logic.raycast_spawn_position(
                origin,
                look,
                lambda blockPos: self._block_name(
                    self._get_block(blockPos, dimensionId)
                ),
            )
            if spawnPosition is None:
                self._notify(
                    playerId,
                    u"请瞄准 20 格内可放置僵尸的方块。",
                    "RED",
                )
                return True
            zombieId = self._spawn_ruin_entity(
                result["entity"],
                spawnPosition,
                self._get_rotation(playerId)[1],
                dimensionId,
            )
            if zombieId:
                if not self._consume_carried_charge(playerId):
                    self.DestroyEntity(zombieId)
                    return True
                self._loyal_zombies[zombieId] = {
                    "ownerId": playerId,
                    "expires": self._tick + int(result["lifeTicks"]),
                }
                try:
                    CF.CreateEffect(zombieId).AddEffectToEntity(
                        "strength",
                        int(math.ceil(result["strengthTicks"] / 20.0)),
                        int(result["strengthAmplifier"]),
                        True,
                    )
                except Exception:
                    pass
            return True
        if kind == "fortification_scepter":
            if (
                not self._is_creative(playerId)
                and self._fortification_cooldowns.get(playerId, 0)
                > self._tick
            ):
                remaining = int(
                    math.ceil(
                        (
                            self._fortification_cooldowns[playerId]
                            - self._tick
                        )
                        / 20.0
                    )
                )
                self._notify(
                    playerId,
                    u"堡垒权杖冷却中：%s 秒" % remaining,
                    "RED",
                )
                return True
            if not self._consume_carried_charge(playerId):
                return True
            shield = self._player_fortification.setdefault(
                playerId, scepter_logic.new_shield_state()
            )
            result = scepter_logic.use_fortification_scepter(
                scepterState, shield
            )
            if result.get("used"):
                self._sync_fortification_visual(playerId, shield)
                if not self._is_creative(playerId):
                    self._fortification_cooldowns[playerId] = (
                        self._tick + int(result["cooldown"])
                    )
                position = self._get_foot_pos(playerId)
                dimensionId = self._get_dimension(playerId)
                if position is not None and dimensionId is not None:
                    self._broadcast_lich_effect(
                        dimensionId,
                        "fortification_activate",
                        (position,),
                        playerId,
                    )
                    self._play_world_sound(
                        "random.orb", position, 1.0, 0.8
                    )
                self._notify(playerId, u"堡垒护盾：5 层", "GREEN")
            return True
        return False

    def _end_lifedrain(self, playerId, stopUsing=False):
        if playerId is None:
            return False
        active = self._lifedrain_users.pop(playerId, None) is not None
        if stopUsing:
            self._stop_using_item(playerId)
        return active

    def OnItemReleaseUsingServerEvent(self, args):
        playerId = args.get("playerId", args.get("entityId"))
        self._end_lifedrain(playerId)
        self._knightmetal_shield_users.pop(str(playerId), None)

    def OnLifedrainReleaseRequest(self, args):
        self._end_lifedrain(args.get("__id__"), True)

    def OnKnightItemUseRequest(self, args):
        playerId = args.get("__id__")
        itemName = str(args.get("itemName", ""))
        if playerId is None:
            return
        self._entry_trace(
            "knight.item_use_request",
            playerId=str(playerId),
            itemName=itemName,
            active=bool(args.get("active", True)),
        )
        if itemName == "tf_slice:block_and_chain":
            carried = self._carried_item(playerId) or {}
            if portal_logic.item_name(carried) != itemName:
                return
            self._use_block_and_chain(
                {"playerId": playerId, "itemDict": carried}
            )
            return
        if itemName != "tf_slice:knightmetal_shield":
            return
        playerKey = str(playerId)
        if not bool(args.get("active", True)):
            self._knightmetal_shield_users.pop(playerKey, None)
            return
        if self._held_knightmetal_shield(playerId) is not None:
            self._knightmetal_shield_users[playerKey] = int(self._tick)

    def OnPlayerAttackEntityEvent(self, args):
        targetId = args.get("victimId", args.get("targetId"))
        playerId = args.get("playerId", args.get("attackerId"))
        if self._remember_hydra_player_attack(targetId, playerId):
            args["isKnockBack"] = False
        if self._remember_ur_ghast_player_attack(targetId, playerId):
            args["isKnockBack"] = False
        urFireballKey = entity_registry_logic.matching_entity_key(
            self._ur_ghast_projectiles, targetId
        )
        if urFireballKey is not None and playerId is not None:
            if self._reflect_ur_ghast_fireball(targetId, playerId):
                args["cancel"] = True
                args["isKnockBack"] = False
            return
        mortarKey = entity_registry_logic.matching_entity_key(
            self._hydra_mortars, targetId
        )
        if mortarKey is not None and playerId is not None:
            self._reflect_hydra_mortar(targetId, playerId)
            args["cancel"] = True
            return
        projectileKey = entity_registry_logic.matching_entity_key(
            self._lich_projectiles, targetId
        )
        if projectileKey is None or playerId is None:
            return
        projectile = self._lich_projectiles[projectileKey]
        projectileType = projectile.get("type")
        if projectileType == LICH_BOMB_IDENTIFIER:
            self._trigger_entity_event(targetId, "tf_slice:explode")
            args["cancel"] = True
        elif projectileType == LICH_BOLT_IDENTIFIER:
            self.OnActuallyHurtServerEvent(
                {"entityId": targetId, "attackerId": playerId, "damage": 0}
            )
            args["cancel"] = True

    def _protect_locked_lich_tower(self, args):
        playerId = args.get("playerId", args.get("entityId"))
        if (
            playerId is None
            or self._ruin_worldgen is None
            or self._has_progress(playerId, "tf_naga_defeated")
        ):
            return False
        position = (
            int(args.get("x", args.get("blockX", args.get("posX", 0)))),
            int(args.get("y", args.get("blockY", args.get("posY", 0)))),
            int(args.get("z", args.get("blockZ", args.get("posZ", 0)))),
        )
        if not self._ruin_worldgen.is_locked_lich_tower_position(position):
            return False
        args["cancel"] = True
        args["ret"] = False
        if self._progress_notice_cooldowns.get(playerId, 0) <= self._tick:
            self._progress_notice_cooldowns[playerId] = self._tick + 60
            self._notify(
                playerId,
                u"\u9ed1\u6697\u7ed3\u754c\u963b\u6321\u4e86\u4f60\uff1a\u8bf7\u5148\u51fb\u8d25\u5a1c\u8fe6\u3002",
                "PURPLE",
            )
        return True

    def _protect_locked_route_landmark(self, args, core_only=False):
        playerId = args.get("playerId", args.get("entityId"))
        if playerId is None or self._ruin_worldgen is None:
            return False
        position = (
            int(args.get("x", args.get("blockX", args.get("posX", 0)))),
            int(args.get("y", args.get("blockY", args.get("posY", 0)))),
            int(args.get("z", args.get("blockZ", args.get("posZ", 0)))),
        )
        kind = self._ruin_worldgen.route_landmark_kind_at_position(position)
        if kind is None:
            return False
        if core_only:
            blockName = str(args.get("blockName", args.get("fullName", "")))
            if blockName not in (
                "tf_slice:mazestone_mosaic",
                "tf_slice:mazestone_border",
                "tf_slice:fiery_block",
                "tf_slice:underbrick",
                "tf_slice:underbrick_floor",
                "tf_slice:stronghold_shield",
                "tf_slice:towerwood",
                "tf_slice:encased_towerwood",
                "tf_slice:tower_key_door",
                "tf_slice:ghast_trap",
                "minecraft:chest",
                "minecraft:trapped_chest",
            ):
                return False
        progress = self._route_progress_value(playerId)
        if kind == "labyrinth":
            allowed = route_progression_logic.can_enter_swamp(progress)
        elif kind == "hydra_lair":
            allowed = route_progression_logic.can_enter_fire_swamp(progress)
        elif kind == "knight_stronghold":
            allowed = route_progression_logic.can_enter_knight_stronghold(
                progress
            )
        else:
            allowed = route_progression_logic.can_enter_dark_tower(progress)
        if allowed:
            return False
        args["cancel"] = True
        args["ret"] = False
        if self._progress_notice_cooldowns.get(playerId, 0) <= self._tick:
            self._progress_notice_cooldowns[playerId] = self._tick + 60
            self._notify(
                playerId,
                {
                    "labyrinth": u"\u5deb\u5996\u7684\u7ed3\u754c\u4ecd\u5728\u5c01\u9501\u8ff7\u5bab\u3002",
                    "hydra_lair": u"\u7c73\u8bfa\u9676\u70a3\u8089\u7684\u529b\u91cf\u624d\u80fd\u62b5\u5fa1\u706b\u7130\u6cbc\u6cfd\u3002",
                    "knight_stronghold": u"\u5956\u676f\u57fa\u5ea7\u5c1a\u672a\u89e3\u9664\u9a91\u58eb\u8981\u585e\u7684\u5c01\u9501\u3002",
                    "dark_tower": u"\u516d\u540d\u5e7b\u5f71\u9a91\u58eb\u4ecd\u5b88\u62a4\u7740\u9ed1\u6697\u9ad8\u5854\u3002",
                }.get(kind, u"\u9ed1\u6697\u7ed3\u754c\u963b\u6321\u4e86\u4f60\u3002"),
                "PURPLE",
            )
        return True

    def OnServerPlayerTryDestroyBlockEvent(self, args):
        if self._protect_locked_lich_tower(args):
            return
        if self._protect_locked_route_landmark(args, core_only=True):
            return
        blockName = str(args.get("blockName", args.get("fullName", "")))
        trophyPosition = self._block_event_position(args)
        if trophyPosition is not None:
            blockName = public_block_logic.trophy_event_block_name(
                blockName,
                self._block_name(
                    self._get_block(
                        trophyPosition,
                        int(
                            args.get(
                                "dimensionId",
                                args.get("dimension", 0),
                            )
                        ),
                    )
                ),
            )
        if blockName in UR_GHAST_TROPHY_BLOCKS:
            return
        if self._break_huge_lily_pad(args, blockName):
            return
        if blockName not in MAZESTONE_BLOCKS:
            return
        playerId = args.get("playerId", args.get("entityId"))
        carried = self._carried_item(playerId) or {}
        itemName = portal_logic.item_name(carried)
        if itemName != "tf_slice:mazebreaker_pickaxe":
            # Mazestone wears ordinary picks one extra point per block.
            if itemName.endswith("_pickaxe") and not self._is_creative(playerId):
                self._consume_carried_charge(playerId)
            return
        position = (
            int(args.get("x", args.get("blockX", args.get("posX", 0)))),
            int(args.get("y", args.get("blockY", args.get("posY", 0)))),
            int(args.get("z", args.get("blockZ", args.get("posZ", 0)))),
        )
        dimensionId = int(
            args.get("dimensionId", self._get_dimension(playerId) or 0)
        )
        if self._set_block(position, "minecraft:air", dimensionId) is False:
            return
        if not self._is_creative(playerId):
            self._consume_carried_charge(playerId)
            self._deliver_item(
                playerId,
                {"itemName": blockName, "count": 1, "auxValue": 0},
            )
        args["cancel"] = True
        args["ret"] = False

    def OnBlockRemoveServerEvent(self, args):
        blockName = str(args.get("fullName", args.get("blockName", "")))
        position = (
            int(args.get("x", args.get("posX", 0))),
            int(args.get("y", args.get("posY", 0))),
            int(args.get("z", args.get("posZ", 0))),
        )
        dimensionId = int(
            args.get("dimension", args.get("dimensionId", 0))
        )
        visualKey = (int(dimensionId),) + tuple(position)
        if (
            blockName in UR_GHAST_TROPHY_BLOCKS
            or visualKey in self._ur_ghast_trophy_visuals
        ):
            self._broadcast_trophy_break_effect(position, dimensionId)
            self._remove_ur_ghast_trophy_visuals(position, dimensionId)
            return
        if leaf_decay_logic.is_connecting_leaf(blockName):
            self._discard_persistent_leaf(dimensionId, position)
        if leaf_decay_logic.is_support_log(blockName):
            self._leaf_decay_bridge_propagated.clear()
            self._queue_neighbor_leaf_decay(position, dimensionId)
        elif leaf_decay_logic.is_connecting_leaf(blockName):
            self._queue_neighbor_leaf_decay(position, dimensionId)

    def _plant_support_status(self, blockName, position, dimensionId, facing=None):
        if blockName == plant_support_logic.FIREFLY:
            return True
        supportPos = plant_support_logic.support_position(blockName, position, facing)
        if supportPos is None:
            return None
        supportBlock = self._get_block(supportPos, dimensionId)
        supportName = self._block_name(supportBlock)
        if not supportName:
            return None
        supported = plant_support_logic.named_support(blockName, supportName)
        if supported is not None:
            return supported
        try:
            collision = self._block_comp.GetBlockCollision(supportPos, dimensionId)
        except Exception:
            return None
        return plant_support_logic.collision_support(blockName, collision, facing)

    def _check_plant_support(self, blockName, position, dimensionId):
        if blockName not in plant_support_logic.SUPPORTED_BLOCKS:
            return False
        # Events can arrive after replacement, including our own removal updates.
        if self._block_name(self._get_block(position, dimensionId)) != blockName:
            return False
        if self._plant_support_status(blockName, position, dimensionId) is not False:
            return False
        try:
            # The general bulk-write helper suppresses neighbor updates. Plants
            # must notify neighbors so a detached root chain falls as a whole.
            changed = self._block_comp.SetBlockNew(
                position, {"name": "minecraft:air", "aux": 0},
                0, int(dimensionId), True, True,
            )
        except Exception:
            return False
        if changed is not True:
            return False
        item = plant_support_logic.support_drop(blockName, random.randint(1, 3))
        if item is not None:
            try:
                self.CreateEngineItemEntity(
                    item, int(dimensionId),
                    tuple(float(value) + 0.5 for value in position),
                )
            except Exception:
                pass
        return True

    def OnBlockRandomTickServerEvent(self, args):
        blockName = str(args.get("fullName", args.get("blockName", "")))
        if blockName in plant_support_logic.SUPPORTED_BLOCKS:
            position = self._block_event_position(args)
            if position is not None:
                self._check_plant_support(
                    blockName, position,
                    int(args.get("dimensionId", args.get("dimension", 0))),
                )
            return
        if leaf_decay_logic.sapling_feature(blockName) is None:
            return
        if not leaf_decay_logic.should_grow_sapling(
            args.get("brightness", 0), random.randrange(7)
        ):
            return
        position = (
            int(args.get("posX", args.get("x", 0))),
            int(args.get("posY", args.get("y", 0))),
            int(args.get("posZ", args.get("z", 0))),
        )
        dimensionId = int(args.get("dimensionId", args.get("dimension", 0)))
        self._advance_twilight_sapling(blockName, position, dimensionId)

    def OnEntityPlaceBlockAfterServerEvent(self, args):
        blockName = str(args.get("fullName", args.get("blockName", "")))
        if blockName == plant_support_logic.FIREFLY:
            self._initialize_placed_firefly(args)
            return
        if banister_logic.is_banister(blockName):
            self._initialize_placed_banister(args)
            return
        if not leaf_decay_logic.is_decayable_leaf(blockName):
            return
        position = (
            int(args.get("x", args.get("posX", 0))),
            int(args.get("y", args.get("posY", 0))),
            int(args.get("z", args.get("posZ", 0))),
        )
        dimensionId = int(args.get("dimensionId", args.get("dimension", 0)))
        self._register_persistent_leaf_position(
            position, dimensionId, blockName
        )

    def _initialize_placed_firefly(self, args):
        position = self._block_event_position(args)
        facing = plant_support_logic.firefly_facing(args.get("face"))
        if position is None or facing is None or self._block_state_comp is None:
            return False
        dimensionId = int(args.get("dimensionId", args.get("dimension", 0)))
        if self._block_name(self._get_block(position, dimensionId)) != plant_support_logic.FIREFLY:
            return False
        try:
            states = self._block_state_comp.GetBlockStates(position, dimensionId) or {}
            states["tf_slice:facing"] = facing
            states["tf_slice:attachment_verified"] = 1
            return self._block_state_comp.SetBlockStates(position, states, dimensionId) is not False
        except Exception:
            return False

    def _initialize_placed_banister(self, args):
        blockName = str(args.get("fullName", args.get("blockName", "")))
        if not banister_logic.is_banister(blockName):
            return False
        position = (
            int(args.get("x", args.get("posX", 0))),
            int(args.get("y", args.get("posY", 0))),
            int(args.get("z", args.get("posZ", 0))),
        )
        dimensionId = int(args.get("dimensionId", args.get("dimension", 0)))
        aboveName = self._block_name(
            self._get_block(
                (position[0], position[1] + 1, position[2]), dimensionId
            )
        )
        states = banister_logic.placement_states(aboveName)
        if self._block_state_comp is None:
            return False
        try:
            current = self._block_state_comp.GetBlockStates(
                position, dimensionId
            ) or {}
            current.update(states)
            return self._block_state_comp.SetBlockStates(
                position, current, dimensionId
            ) is not False
        except Exception:
            return False

    def _refresh_banister_connection(self, position, dimensionId):
        position = tuple(int(value) for value in position)
        dimensionId = int(dimensionId)
        blockName = self._block_name(
            self._get_block(position, dimensionId)
        )
        if (
            not banister_logic.is_banister(blockName)
            or self._block_state_comp is None
        ):
            return False
        aboveName = self._block_name(
            self._get_block(
                (position[0], position[1] + 1, position[2]), dimensionId
            )
        )
        try:
            states = self._block_state_comp.GetBlockStates(
                position, dimensionId
            ) or {}
            nextStates = banister_logic.connection_states(
                states, aboveName
            )
            if nextStates == states:
                return True
            return self._block_state_comp.SetBlockStates(
                position, nextStates, dimensionId
            ) is not False
        except Exception:
            return False

    def OnServerEntityTryPlaceBlockEvent(self, args):
        if self._protect_locked_lich_tower(args):
            return
        blockName = str(args.get("blockName", args.get("fullName", "")))
        trophyBlock = public_block_logic.trophy_block_for_face(
            blockName, args.get("face")
        )
        if trophyBlock is not None:
            args["fullName"] = trophyBlock
            args["blockName"] = trophyBlock
            blockName = trophyBlock
        playerId = args.get("playerId", args.get("entityId"))
        position = (
            int(args.get("x", args.get("blockX", 0))),
            int(args.get("y", args.get("blockY", 0))),
            int(args.get("z", args.get("blockZ", 0))),
        )
        dimensionId = int(
            args.get(
                "dimensionId",
                self._get_dimension(playerId) or 0,
            )
        )
        if blockName == plant_support_logic.FIREFLY:
            return
        if blockName in plant_support_logic.PLANTS:
            if self._plant_support_status(blockName, position, dimensionId) is not True:
                args["cancel"] = True
                args["ret"] = False
                return
        if blockName == HUGE_LILY_PAD_BLOCK:
            if not self._huge_lily_single_footprint_is_available(
                position,
                dimensionId,
            ):
                args["cancel"] = True
                args["ret"] = False
                self._notify(
                    playerId,
                    u"\u5de8\u578b\u7761\u83b2\u53f6\u9700\u8981\u5b8c\u6574\u4e14\u65e0\u5360\u7528\u7684 3x3 \u6c34\u9762\u3002",
                    "RED",
                )
            return
        if blockName in TROPHY_BLOCKS:
            trophyData = {
                "position": position,
                "dimensionId": dimensionId,
                "block": blockName,
                "playerId": playerId,
                "yaw": self._get_rotation(playerId)[1],
            }
            try:
                game = CF.CreateGame(LEVEL_ID)
                for delay in (0.05, 0.15, 0.3):
                    game.AddTimer(
                        delay,
                        self._orient_placed_trophy,
                        trophyData,
                    )
                game.AddTimer(
                    0.1,
                    self._activate_placed_trophy,
                    trophyData,
                )
            except Exception:
                pass
        if blockName in fire_swamp_logic.DEVICE_BLOCKS:
            try:
                CF.CreateGame(LEVEL_ID).AddTimer(
                    0.05,
                    self._register_placed_fire_swamp_device,
                    {
                        "position": position,
                        "dimensionId": dimensionId,
                        "block": blockName,
                    },
                )
            except Exception:
                pass
        vanilla_block_adapter_logic.adapt_placement_event(args)

    def _orient_placed_trophy(self, data):
        position = tuple(data.get("position", ()))
        if len(position) != 3 or self._block_state_comp is None:
            return False
        dimensionId = int(data.get("dimensionId", 0))
        blockName = self._block_name(self._get_block(position, dimensionId))
        if blockName != str(data.get("block", "")):
            return False
        yaw = float(data.get("yaw", 0.0))
        states = self._fire_swamp_block_states(position, dimensionId)
        if blockName.endswith("_wall_trophy"):
            states["tf_slice:facing"] = public_block_logic.facing_towards_player(
                yaw
            )
        else:
            states["tf_slice:rotation"] = (
                public_block_logic.trophy_rotation_from_yaw(yaw)
            )
        try:
            return self._block_state_comp.SetBlockStates(
                position, states, dimensionId
            ) is not False
        except Exception:
            return False

    def _activate_placed_trophy(self, data):
        position = tuple(data.get("position", ()))
        if len(position) != 3 or self._ruin_worldgen is None:
            return False
        dimensionId = int(data.get("dimensionId", 0))
        if dimensionId != config.DIMENSION_ID:
            return False
        trophyName = self._block_name(self._get_block(position, dimensionId))
        if (
            trophyName != str(data.get("block", ""))
            or trophyName not in knight_route_logic.ACCEPTED_TROPHIES
        ):
            return False
        pedestalPosition = (
            position[0],
            position[1] - 1,
            position[2],
        )
        if (
            self._block_name(self._get_block(pedestalPosition, dimensionId))
            != "tf_slice:trophy_pedestal"
        ):
            return False
        return self._activate_stronghold_pedestal_at(
            trophyName,
            data.get("playerId"),
            pedestalPosition,
        )

    def _decrement_carried_stack(self, playerId):
        if playerId is None or self._is_creative(playerId):
            return True
        item = copy.deepcopy(self._carried_item(playerId) or {})
        count = int(item.get("count", 0))
        if count <= 0:
            return False
        if count == 1:
            item = {}
        else:
            item["count"] = count - 1
        return self._set_carried_item(playerId, item)

    def _lily_position_is_available(self, position, dimensionId):
        current = self._block_name(self._get_block(position, dimensionId))
        if current in WATER_BLOCKS:
            return True
        if current not in (
            "",
            "minecraft:air",
            "minecraft:cave_air",
            "minecraft:void_air",
            HUGE_LILY_PAD_BLOCK,
        ):
            return False
        below = (position[0], position[1] - 1, position[2])
        return self._block_name(self._get_block(below, dimensionId)) in WATER_BLOCKS

    def _huge_lily_single_footprint_is_available(
        self,
        position,
        dimensionId,
    ):
        for target in public_block_logic.huge_lily_single_clearance_positions(
            position
        ):
            current = self._block_name(self._get_block(target, dimensionId))
            if current in WATER_BLOCKS:
                continue
            if current not in (
                "",
                "minecraft:air",
                "minecraft:cave_air",
                "minecraft:void_air",
            ):
                return False
            below = (target[0], target[1] - 1, target[2])
            if self._block_name(
                self._get_block(below, dimensionId)
            ) not in WATER_BLOCKS:
                return False
        return True

    def _place_huge_lily_pad(self, position, dimensionId, playerId):
        facing = public_block_logic.facing_towards_player(
            self._get_rotation(playerId)[1] if playerId is not None else 0.0
        )
        layout = public_block_logic.huge_lily_layout(position, facing)
        if not all(
            self._lily_position_is_available(target, dimensionId)
            for target in layout
        ):
            return False
        previous = dict(
            (target, self._block_name(self._get_block(target, dimensionId)))
            for target in layout
        )
        placed = []
        failed = False
        for target, entry in layout.items():
            if self._set_block(target, entry["block"], dimensionId) is False:
                failed = True
                break
            placed.append(target)
            if self._block_state_comp is not None:
                states = self._fire_swamp_block_states(target, dimensionId)
                states["tf_slice:facing"] = facing
                try:
                    if self._block_state_comp.SetBlockStates(
                        target, states, dimensionId
                    ) is False:
                        failed = True
                        break
                except Exception:
                    failed = True
                    break
        if failed or len(placed) != 4:
            for target in placed:
                self._set_block(
                    target,
                    previous.get(target) or "minecraft:air",
                    dimensionId,
                )
            return False
        if not self._decrement_carried_stack(playerId):
            for target in placed:
                self._set_block(
                    target,
                    previous.get(target) or "minecraft:air",
                    dimensionId,
                )
            return False
        return True

    def _break_huge_lily_pad(self, args, blockName):
        if blockName not in HUGE_LILY_QUADRANTS:
            return False
        playerId = args.get("playerId", args.get("entityId"))
        position = (
            int(args.get("x", args.get("blockX", args.get("posX", 0)))),
            int(args.get("y", args.get("blockY", args.get("posY", 0)))),
            int(args.get("z", args.get("blockZ", args.get("posZ", 0)))),
        )
        dimensionId = int(
            args.get("dimensionId", self._get_dimension(playerId) or 0)
        )
        states = self._fire_swamp_block_states(position, dimensionId)
        facing = str(states.get("tf_slice:facing", "north"))
        quadrant = blockName.rsplit("_", 1)[-1]
        anchor = public_block_logic.huge_lily_anchor(
            position, quadrant, facing
        )
        layout = public_block_logic.huge_lily_layout(anchor, facing)
        for target, entry in layout.items():
            if self._block_name(self._get_block(target, dimensionId)) != entry["block"]:
                return False
        removed = []
        for target in layout:
            if self._set_block(target, "minecraft:air", dimensionId) is False:
                for restored in removed:
                    entry = layout[restored]
                    self._set_block(restored, entry["block"], dimensionId)
                    if self._block_state_comp is not None:
                        restoredStates = self._fire_swamp_block_states(
                            restored, dimensionId
                        )
                        restoredStates["tf_slice:facing"] = facing
                        try:
                            self._block_state_comp.SetBlockStates(
                                restored, restoredStates, dimensionId
                            )
                        except Exception:
                            pass
                return False
            removed.append(target)
        if not self._is_creative(playerId):
            self._deliver_item(
                playerId,
                {"itemName": HUGE_LILY_PAD_BLOCK, "count": 1, "auxValue": 0},
            )
        args["cancel"] = True
        args["ret"] = False
        return True

    def _register_placed_fire_swamp_device(self, data):
        position = tuple(data.get("position", ()))
        if len(position) != 3:
            return False
        dimensionId = int(data.get("dimensionId", 0))
        blockName = self._block_name(
            self._get_block(position, dimensionId)
        )
        if blockName != str(data.get("block", "")):
            return False
        self._register_fire_swamp_device(
            blockName, position, dimensionId
        )
        return True

    def OnLichScepterTryUseEvent(self, args):
        playerId = args.get("playerId")
        if playerId is None:
            return
        preferredItem = args.get("itemDict") or args.get("item")
        preferredItem = preferredItem or self._carried_item(playerId) or {}
        preferredName = portal_logic.item_name(preferredItem)
        if preferredName == "tf_slice:lifedrain_scepter":
            self._use_lich_scepter(playerId, preferredName)
            return
        if preferredName in (
            "tf_slice:twilight_scepter",
            "tf_slice:zombie_scepter",
            "tf_slice:fortification_scepter",
        ):
            args["cancel"] = True
            self._use_lich_scepter(playerId, preferredName)
            return

    def OnServerItemTryUseEvent(self, args):
        playerId = args.get("playerId")
        if playerId is None:
            return
        if self._queue_trophy_equip(args):
            return
        preferredItem = args.get("itemDict") or args.get("item")
        if self._begin_knightmetal_shield_use(args):
            return
        if self._use_block_and_chain(args):
            return
        hand, item = self._magic_map_hand_item(
            playerId,
            include_blank=True,
            preferred_item=preferredItem,
        )
        item = item or {}
        itemName = portal_logic.item_name(item)
        if (
            itemName != config.MAGIC_MAP_ITEM
            and not self._is_magic_map_stack(item)
        ):
            return
        if self._magic_map_use_cooldowns.get(playerId, 0) > self._tick:
            return
        self._magic_map_use_cooldowns[playerId] = self._tick + 5
        self._known_players.add(playerId)
        dimensionId = self._get_dimension(playerId)
        position = self._get_foot_pos(playerId)
        if dimensionId != config.DIMENSION_ID or position is None:
            self._notify(
                playerId,
                "魔法地图只能在暮色森林中绘制和展开。",
                "RED",
            )
            return
        if itemName == config.MAGIC_MAP_ITEM:
            self._queue_blank_magic_map_use(playerId, hand)
            return
        self._queue_filled_magic_map_open(playerId, hand)

    def OnMagicMapOpenRequest(self, args):
        playerId = args.get("__id__")
        if playerId is not None:
            hand, item = self._held_map_hand_item(playerId)
            if self._is_maze_map_stack(item):
                self._send_maze_map_snapshot(
                    playerId, item.get("extraId"),
                    openScreen=bool(args.get("openScreen", False)),
                )
                return
            self._send_magic_map_snapshot(
                playerId,
                bool(args.get("openScreen", False)),
                hand=hand,
            )

    def OnServerItemUseOnEvent(self, args):
        item = args.get("itemDict") or args.get("item") or {}
        itemName = portal_logic.item_name(item)
        if not itemName:
            itemName = str(args.get("itemName", ""))
        if itemName in (config.MAZE_MAP_ITEM, config.FILLED_MAZE_MAP_ITEM):
            self.OnHydraRouteItemTryUseEvent(args)
            return
        if self._mark_trophy_block_use(args, itemName):
            return
        if self._try_bonemeal_twilight_sapling(args, itemName):
            return
        if itemName == "tf_slice:knightmetal_shield":
            self._begin_knightmetal_shield_use(args)
            return
        if itemName == "tf_slice:block_and_chain":
            args["ret"] = True
            playerId = args.get("playerId", args.get("entityId"))
            args["playerId"] = playerId
            self._use_block_and_chain(args)
            return
        if (
            itemName == config.MAGIC_MAP_ITEM
            or self._is_magic_map_stack(item)
        ):
            args["ret"] = True
            playerId = args.get("playerId", args.get("entityId"))
            args["playerId"] = playerId
            self.OnServerItemTryUseEvent(args)
            return
        if itemName != "tf_slice:crumble_horn":
            return
        blockName = str(args.get("blockName", ""))
        replacement = quest_ram_logic.CRUMBLE_RECIPES.get(blockName)
        if replacement is None:
            return
        dimensionId = int(
            args.get(
                "dimensionId",
                self._get_dimension(args.get("playerId")) or 0,
            )
        )
        pos = (
            int(args.get("x", args.get("blockX", 0))),
            int(args.get("y", args.get("blockY", 0))),
            int(args.get("z", args.get("blockZ", 0))),
        )
        if self._set_block(pos, replacement, dimensionId) is False:
            return
        playerId = args.get("playerId")
        try:
            itemComp = CF.CreateItem(playerId)
            posType = serverApi.GetMinecraftEnum().ItemPosType.CARRIED
            durability = int(itemComp.GetItemDurability(posType, 0))
            itemComp.SetItemDurability(
                posType,
                0,
                max(0, durability - 1),
            )
        except Exception:
            pass
        args["cancel"] = True

    def _activate_ghast_trap(self, args):
        if str(args.get("blockName", args.get("fullName", ""))) != "tf_slice:ghast_trap":
            return False
        position = self._block_event_position(args)
        if position is None:
            return False
        key = self._tower_position_key(position)
        trap = self._ghast_traps.setdefault(
            key, ur_ghast_logic.create_trap_state(position)
        )
        trap["dimensionId"] = int(
            args.get("dimensionId", config.DIMENSION_ID)
        )
        playerId = args.get("playerId", args.get("entityId"))
        args["cancel"] = True
        args["ret"] = False
        if not trap.get("charged"):
            self._entry_trace(
                "ur_ghast.trap_activation",
                position=list(position),
                activated=False,
                reason="not_charged",
                deathCount=int(trap.get("deathCount", 0)),
                powered=bool(trap.get("redstonePowered", False)),
            )
            if playerId is not None:
                self._notify(
                    playerId,
                    u"\u6076\u9b42\u9677\u9631\u9700\u8981\u4e09\u53ea\u6076\u9b42\u5e7c\u4f53\u7684\u80fd\u91cf\u3002",
                    "PURPLE",
                )
            return True
        event = ur_ghast_logic.activate_trap(trap)
        if not event.get("activated"):
            self._entry_trace(
                "ur_ghast.trap_activation",
                position=list(position),
                activated=False,
                reason="already_active",
                deathCount=int(trap.get("deathCount", 0)),
                powered=bool(trap.get("redstonePowered", False)),
            )
            return True
        self._set_ghast_trap_active_state(trap, True)
        self._broadcast_ghast_trap_effect(trap, "warmup")
        self._play_world_sound(
            "beacon.activate", trap.get("position"), 1.0, 2.0
        )
        if playerId is not None:
            self._grant_progress(playerId, "tf_ghast_trap_activated")
        self._save_dark_tower_runtime()
        self._entry_trace(
            "ur_ghast.trap_activation",
            position=list(position),
            activated=True,
            reason="charged_rising_edge",
            activationCount=int(trap.get("activationCount", 0)),
            powered=bool(trap.get("redstonePowered", False)),
        )
        args["ret"] = True
        return True

    def _dark_tower_connected_mechanism_blocks(
        self, origin, dimensionId, allowedNames
    ):
        """Discover one bounded connected vanishing wall through world reads."""
        origin = tuple(int(value) for value in origin)
        allowedNames = set(str(value) for value in allowedNames)
        blockNames = {
            origin: self._block_name(self._get_block(origin, dimensionId))
        }
        pending = [origin]
        scanned = set((origin,))
        while pending and len(blockNames) <= dark_tower_logic.VANISHING_CHAIN_LIMIT * 7:
            current = pending.pop(0)
            for delta in (
                (-1, 0, 0), (1, 0, 0),
                (0, -1, 0), (0, 1, 0),
                (0, 0, -1), (0, 0, 1),
            ):
                neighbor = tuple(
                    current[index] + delta[index] for index in range(3)
                )
                if neighbor in scanned:
                    continue
                scanned.add(neighbor)
                name = self._block_name(
                    self._get_block(neighbor, dimensionId)
                )
                blockNames[neighbor] = name
                if (
                    name in allowedNames
                    and len(pending) < dark_tower_logic.VANISHING_CHAIN_LIMIT
                ):
                    pending.append(neighbor)
        return dark_tower_logic.connected_block_component(
            blockNames,
            origin,
            allowedNames,
            dark_tower_logic.VANISHING_CHAIN_LIMIT,
        )

    def _activate_dark_tower_vanishing(self, position, dimensionId, blockName):
        if blockName == "tf_slice:reappearing_block":
            allowed = ("tf_slice:reappearing_block",)
        else:
            allowed = (
                "tf_slice:vanishing_block",
                "tf_slice:unbreakable_vanishing_block",
                "tf_slice:tower_key_door",
            )
            doorNetwork = self._dark_tower_connected_mechanism_blocks(
                position,
                dimensionId,
                allowed + tuple(dark_tower_logic.LOCKED_DOOR_BLOCKS),
            )
            doorLocked = False
            for current in doorNetwork:
                currentName = self._block_name(
                    self._get_block(current, dimensionId)
                )
                if currentName == "tf_slice:locked_vanishing_block":
                    doorLocked = True
                    break
                if (
                    currentName == "tf_slice:tower_key_door"
                    and self._tower_key_lock_is_locked(
                        current, dimensionId
                    )
                ):
                    doorLocked = True
                    break
            if doorLocked:
                # Clicking the unbreakable center of a 3x3 key door must not
                # bypass the four locked corners.
                return 0
        connected = self._dark_tower_connected_mechanism_blocks(
            position, dimensionId, allowed
        )
        if blockName == "tf_slice:reappearing_block":
            wave = dark_tower_logic.build_reappearing_wave(
                connected,
                position,
                self._tick,
                delay_for=lambda _parent, _current: random.randint(2, 6),
            )
        else:
            wave = dark_tower_logic.build_vanishing_wave(
                connected,
                position,
                self._tick,
                delay_for=lambda _parent, _current: random.randint(2, 6),
            )
        scheduled = 0
        for current, record in wave.items():
            currentName = self._block_name(
                self._get_block(current, dimensionId)
            )
            key = self._tower_position_key(current)
            if currentName not in allowed or key in self._dark_tower_mechanisms:
                continue
            record["dimensionId"] = int(dimensionId)
            self._dark_tower_mechanisms[key] = record
            scheduled += 1
        if scheduled:
            self._save_dark_tower_runtime()
        return scheduled

    def _tower_key_lock_is_locked(self, position, dimensionId):
        blockName = self._block_name(
            self._get_block(position, dimensionId)
        )
        if blockName == "tf_slice:locked_vanishing_block":
            return True
        if blockName != "tf_slice:tower_key_door":
            return False
        states = self._fire_swamp_block_states(position, dimensionId)
        return bool(states.get("tf_slice:locked", True))

    def _set_tower_key_lock_state(
        self, position, dimensionId, locked
    ):
        if self._block_state_comp is None:
            return False
        if self._block_name(
            self._get_block(position, dimensionId)
        ) != "tf_slice:tower_key_door":
            return False
        states = self._fire_swamp_block_states(position, dimensionId)
        states["tf_slice:locked"] = bool(locked)
        try:
            return self._block_state_comp.SetBlockStates(
                tuple(position), states, int(dimensionId)
            ) is not False
        except Exception:
            return False

    def _schedule_unlocked_key_door_open(
        self, doorBlocks, origin, dimensionId
    ):
        doorBlocks = [tuple(value) for value in doorBlocks]
        origin = tuple(origin)
        if origin not in doorBlocks:
            return 0
        wave = dark_tower_logic.build_vanishing_wave(
            doorBlocks,
            origin,
            self._tick,
            delay_for=lambda _parent, _current: random.randint(2, 6),
        )
        allowed = (
            "tf_slice:tower_key_door",
            "tf_slice:locked_vanishing_block",
            "tf_slice:unbreakable_vanishing_block",
        )
        scheduled = 0
        for current, record in wave.items():
            currentName = self._block_name(
                self._get_block(current, dimensionId)
            )
            key = self._tower_position_key(current)
            if currentName not in allowed or key in self._dark_tower_mechanisms:
                continue
            record["dimensionId"] = int(dimensionId)
            self._dark_tower_mechanisms[key] = record
            scheduled += 1
        if scheduled:
            self._save_dark_tower_runtime()
        return scheduled

    def _use_dark_tower_mechanism(self, args):
        blockName = str(args.get("blockName", args.get("fullName", "")))
        supported = (
            "tf_slice:tower_key_door",
            "tf_slice:vanishing_block",
            "tf_slice:unbreakable_vanishing_block",
            "tf_slice:locked_vanishing_block",
            "tf_slice:reappearing_block",
            "tf_slice:experiment_115",
        )
        if blockName not in supported:
            return False
        playerId = args.get("playerId", args.get("entityId"))
        position = self._dark_tower_event_position(args)
        dimensionId = int(args.get("dimensionId", config.DIMENSION_ID))
        item = args.get("itemDict") or args.get("item") or self._carried_item(playerId) or {}
        itemName = portal_logic.item_name(item)
        args["cancel"] = True
        args["ret"] = False
        keyDoorInteraction = blockName in (
            "tf_slice:tower_key_door",
            "tf_slice:locked_vanishing_block",
        ) or (
            itemName == "tf_slice:tower_key"
            and blockName == "tf_slice:unbreakable_vanishing_block"
        )
        if keyDoorInteraction:
            lockBlocks = []
            lockedBlocks = []
            doorBlocks = []
            for dx in range(-2, 3):
                for dy in range(-4, 5):
                    for dz in range(-2, 3):
                        current = (
                            position[0] + dx,
                            position[1] + dy,
                            position[2] + dz,
                        )
                        name = self._block_name(
                            self._get_block(current, dimensionId)
                        )
                        if name in (
                            "tf_slice:tower_key_door",
                            "tf_slice:locked_vanishing_block",
                        ):
                            lockBlocks.append(current)
                            if self._tower_key_lock_is_locked(
                                current, dimensionId
                            ):
                                lockedBlocks.append(current)
                        if name in (
                            "tf_slice:tower_key_door",
                            "tf_slice:locked_vanishing_block",
                            "tf_slice:unbreakable_vanishing_block",
                        ):
                            doorBlocks.append(current)
            result = dark_tower_logic.unlock_key_door(
                int(item.get("count", 1)) if itemName == "tf_slice:tower_key" else 0,
                len(lockedBlocks),
            )
            if not result.get("unlocked"):
                return True
            consumed, original = self._consume_one_carried_item(playerId)
            if not consumed:
                return True
            target = (
                position if position in lockedBlocks else lockedBlocks[0]
            )
            targetName = self._block_name(
                self._get_block(target, dimensionId)
            )
            if targetName == "tf_slice:locked_vanishing_block":
                if self._set_block(
                    target, "tf_slice:tower_key_door", dimensionId
                ) is False:
                    if original is not None:
                        self._set_carried_item(playerId, original)
                    return True
            unlocked = self._set_tower_key_lock_state(
                target, dimensionId, False
            )
            scheduled = 0
            if unlocked and result.get("doorOpened"):
                scheduled = self._schedule_unlocked_key_door_open(
                    doorBlocks, target, dimensionId
                )
            if (
                not unlocked
                or (result.get("doorOpened") and scheduled <= 0)
            ):
                if unlocked:
                    self._set_tower_key_lock_state(
                        target, dimensionId, True
                    )
                if original is not None:
                    self._set_carried_item(playerId, original)
                return True
            args["ret"] = True
            return True
        if blockName in (
            "tf_slice:vanishing_block",
            "tf_slice:unbreakable_vanishing_block",
            "tf_slice:reappearing_block",
        ):
            args["ret"] = bool(
                self._activate_dark_tower_vanishing(
                    position, dimensionId, blockName
                )
            )
            return True
        if blockName == "tf_slice:experiment_115":
            key = self._tower_position_key(position)
            record = self._dark_tower_mechanisms.setdefault(
                key,
                {"kind": "experiment_115", "position": list(position), "state": dark_tower_logic.create_experiment_115_state()},
            )
            state = record["state"]
            if itemName == "minecraft:redstone":
                if dark_tower_logic.redstone_regenerate_experiment_115(state):
                    self._consume_one_carried_item(playerId)
                    args["ret"] = True
            elif dark_tower_logic.eat_experiment_115(state):
                try:
                    CF.CreateHunger(playerId).AddHunger(4.0)
                except Exception:
                    pass
                args["ret"] = True
                if int(state.get("servings", 0)) <= 0:
                    self._set_block(position, "minecraft:air", dimensionId)
            self._save_dark_tower_runtime()
            return True
        return False

    def _allow_dark_tower_lever_use(self, args):
        if self._ruin_worldgen is None:
            return False
        blockName = str(args.get("blockName", args.get("fullName", "")))
        position = self._dark_tower_event_position(args)
        landmarkKind = self._ruin_worldgen.route_landmark_kind_at_position(
            position
        )
        return dark_tower_logic.is_authored_dark_tower_lever(
            blockName, landmarkKind
        )

    def _activate_stronghold_pedestal(self, args):
        if (
            str(args.get("blockName", args.get("fullName", "")))
            != "tf_slice:trophy_pedestal"
            or self._ruin_worldgen is None
        ):
            return False
        playerId = args.get("playerId", args.get("entityId"))
        item = args.get("itemDict") or args.get("item") or self._carried_item(playerId) or {}
        itemName = portal_logic.item_name(item) or str(args.get("itemName", ""))
        itemName = public_block_logic.TROPHY_ITEM_TO_BLOCK.get(
            itemName, itemName
        )
        if itemName not in knight_route_logic.ACCEPTED_TROPHIES:
            return False
        position = (
            int(args.get("x", args.get("blockX", 0))),
            int(args.get("y", args.get("blockY", 0))),
            int(args.get("z", args.get("blockZ", 0))),
        )
        args["cancel"] = True
        args["ret"] = self._activate_stronghold_pedestal_at(
            itemName,
            playerId,
            position,
        )
        return True

    def _activate_stronghold_pedestal_at(
        self, trophyName, playerId, position
    ):
        if self._ruin_worldgen is None:
            return False
        nearby = []
        for candidateId in self._get_online_players():
            candidatePos = self._get_foot_pos(candidateId)
            if (
                candidatePos is None
                or self._get_dimension(candidateId) != config.DIMENSION_ID
            ):
                continue
            dx = float(candidatePos[0]) - float(position[0])
            dy = float(candidatePos[1]) - float(position[1])
            dz = float(candidatePos[2]) - float(position[2])
            nearby.append(
                {
                    "id": str(candidateId),
                    "distance": math.sqrt(dx * dx + dy * dy + dz * dz),
                    "progress": self._route_progress_value(candidateId),
                    "creative": self._is_creative(candidateId),
                }
            )
        activation = knight_route_logic.activate_trophy_pedestal(
            trophyName, nearby, 16
        )
        if not activation.get("creditedPlayers"):
            self._notify(
                playerId,
                u"\u5956\u676f\u57fa\u5ea7\u53ea\u4f1a\u54cd\u5e94\u5df2\u51fb\u8d25\u5deb\u5996\u7684\u73a9\u5bb6\u3002",
                "PURPLE",
            )
            return False
        if not self._ruin_worldgen.activate_trophy_pedestal(position):
            return False
        for candidateId in activation["creditedPlayers"]:
            self._grant_progress(candidateId, "tf_trophy_pedestal_activated")
        return True

    def OnServerBlockUseEvent(self, args):
        if self._activate_stronghold_pedestal(args):
            return
        # Tower mechanisms are part of the authored traversal route.  Let the
        # clicked door/floor handle its own lock semantics before the landmark
        # boundary guard considers generic block interaction.
        if self._use_dark_tower_mechanism(args):
            return
        if self._activate_ghast_trap(args):
            return
        # Vanilla levers must be allowed to toggle before the route boundary
        # guard evaluates generic interactions. Builder block entities poll
        # their resulting powered state and activate on the rising edge.
        if self._allow_dark_tower_lever_use(args):
            return
        if self._protect_locked_route_landmark(args, core_only=False):
            return
        if self._cycle_banister(args):
            return
        harvest = cave_plant_logic.torchberry_harvest(
            args.get("blockName")
        )
        if harvest is None:
            return
        args["cancel"] = True
        position = (
            int(args.get("x", 0)),
            int(args.get("y", 0)),
            int(args.get("z", 0)),
        )
        dimensionId = int(args.get("dimensionId", 0))
        if self._set_block(
            position,
            harvest["replacement"],
            dimensionId,
        ) is False:
            return
        self._deliver_item(args.get("playerId"), harvest["item"])

    def _cycle_banister(self, args):
        blockName = str(args.get("blockName", args.get("fullName", "")))
        if not banister_logic.is_banister(blockName):
            return False
        playerId = args.get("playerId", args.get("entityId"))
        item = (
            args.get("itemDict")
            or args.get("item")
            or self._carried_item(playerId)
            or {}
        )
        itemName = portal_logic.item_name(item) or str(
            args.get("itemName", "")
        )
        if not banister_logic.is_axe(itemName):
            return False
        position = (
            int(args.get("x", args.get("blockX", 0))),
            int(args.get("y", args.get("blockY", 0))),
            int(args.get("z", args.get("blockZ", 0))),
        )
        dimensionId = int(args.get("dimensionId", args.get("dimension", 0)))
        if self._block_state_comp is None:
            return False
        try:
            states = self._block_state_comp.GetBlockStates(
                position, dimensionId
            ) or {}
            nextStates = banister_logic.cycle_states(states)
            changed = self._block_state_comp.SetBlockStates(
                position, nextStates, dimensionId
            ) is not False
        except Exception:
            return False
        if not changed:
            return False
        args["cancel"] = True
        args["ret"] = True
        self._play_world_sound("use.wood", position, 1.0, 1.0)
        return True

    def OnEntityInsideBlock(self, args):
        if args.get("blockName") == "tf_slice:knightmetal_block":
            entityId = args.get("entityId")
            key = str(entityId)
            if self._knightmetal_contact_cooldowns.get(key, 0) <= self._tick:
                self._knightmetal_contact_cooldowns[key] = self._tick + 10
                self._hurt(entityId, 4.0, None)
            return
        if args.get("blockName") != config.PORTAL_IDENTIFIER:
            return
        entityId = args.get("entityId")
        self._entry_trace(
            "portal.inside.begin",
            playerId=entityId,
            blockPosition=(
                args.get("blockX"),
                args.get("blockY"),
                args.get("blockZ"),
            ),
        )
        if entityId not in self._known_players:
            self._entry_trace(
                "portal.inside.rejected",
                playerId=entityId,
                reason="unknown_player",
            )
            return
        if self._portal_cooldowns.get(entityId, 0) > self._tick:
            self._entry_trace(
                "portal.inside.rejected",
                playerId=entityId,
                reason="cooldown",
            )
            return
        self._entry_trace("portal.dimension.call", playerId=entityId)
        dimensionId = self._get_dimension(entityId)
        self._entry_trace(
            "portal.dimension.result",
            playerId=entityId,
            dimensionId=dimensionId,
        )
        if dimensionId is None:
            return
        pos = (
            int(args.get("blockX", 0)),
            int(args.get("blockY", 0)),
            int(args.get("blockZ", 0)),
        )
        self._entry_trace(
            "portal.surface.call",
            playerId=entityId,
            dimensionId=dimensionId,
            position=pos,
        )
        surface = self._portal_surface(pos, dimensionId)
        self._entry_trace(
            "portal.surface.result",
            playerId=entityId,
            cellCount=len(surface or ()),
        )
        if not surface:
            return
        self._portal_cooldowns[entityId] = (
            self._tick + config.PORTAL_COOLDOWN_TICKS
        )
        if dimensionId == config.DIMENSION_ID:
            self._return_from_slice(
                entityId, self._portal_link(surface, dimensionId)
            )
            return
        self._entry_trace(
            "portal.exit.call",
            playerId=entityId,
            dimensionId=dimensionId,
        )
        exitPos = self._portal_exit(surface, dimensionId)
        self._entry_trace(
            "portal.exit.result",
            playerId=entityId,
            exitPos=exitPos,
        )
        if exitPos is None:
            return
        self._enter_slice(
            entityId,
            {"dimensionId": dimensionId, "pos": exitPos},
            surface,
        )

    def OnBlockNeighborChanged(self, args):
        blockName = str(args.get("blockName", args.get("fullName", "")))
        dimensionId = args.get("dimensionId")
        if dimensionId is None:
            return
        pos = self._block_event_position(args)
        if pos is None:
            return
        if blockName in plant_support_logic.SUPPORTED_BLOCKS:
            self._check_plant_support(blockName, pos, int(dimensionId))
            return
        if banister_logic.is_banister(blockName):
            self._refresh_banister_connection(pos, dimensionId)
            return
        if blockName == "tf_slice:carminite_builder":
            synthetic = copy.deepcopy(args)
            synthetic["_builderNeighborChanged"] = True
            synthetic.setdefault("blockName", blockName)
            self._tick_dark_tower_block_entity(synthetic)
            return
        if blockName == "tf_slice:ghast_trap":
            key = self._tower_position_key(pos)
            trap = self._ghast_traps.setdefault(
                key, ur_ghast_logic.create_trap_state(pos)
            )
            trap["dimensionId"] = int(dimensionId)
            previousPowered = bool(trap.get("redstonePowered", False))
            powered = self._ghast_trap_powered(pos, int(dimensionId))
            trap["redstonePowered"] = powered
            if powered and not previousPowered:
                synthetic = copy.deepcopy(args)
                synthetic["position"] = pos
                synthetic["blockName"] = blockName
                self._activate_ghast_trap(synthetic)
            if powered != previousPowered:
                self._save_dark_tower_runtime()
            return
        if blockName in (
            "tf_slice:vanishing_block",
            "tf_slice:unbreakable_vanishing_block",
            "tf_slice:reappearing_block",
            "tf_slice:carminite_reactor",
        ):
            powered = self._fire_swamp_device_powered(
                pos, int(dimensionId)
            )
            if not powered:
                return
            if blockName == "tf_slice:carminite_reactor":
                self._tick_dark_tower_block_entity(args)
                return
            self._activate_dark_tower_vanishing(
                pos, int(dimensionId), blockName
            )
            return
        if blockName in fire_swamp_logic.DEVICE_BLOCKS:
            state = self._register_fire_swamp_device(
                blockName, pos, int(dimensionId)
            )
            if state is not None and blockName in (
                fire_swamp_logic.ENCASED_SMOKER,
                fire_swamp_logic.ENCASED_FIRE_JET,
            ):
                before = (
                    state.get("phase"), bool(state.get("active"))
                )
                state, effects = fire_swamp_logic.apply_power(
                    state,
                    self._fire_swamp_device_powered(
                        pos, int(dimensionId)
                    ),
                )
                key = self._fire_swamp_device_key(pos, dimensionId)
                state["position"] = pos
                state["dimensionId"] = int(dimensionId)
                self._fire_swamp_devices[key] = state
                after = (
                    state.get("phase"), bool(state.get("active"))
                )
                if before != after:
                    self._set_fire_swamp_device_visual(
                        pos, dimensionId, state
                    )
                for effect in effects:
                    self._send_fire_swamp_device_effect(state, effect)
            return
        if blockName != config.PORTAL_IDENTIFIER:
            return
        getter = self._portal_block_getter(dimensionId)
        connected = portal_logic.collect_connected_surface(
            pos,
            getter,
            set((config.PORTAL_IDENTIFIER,)),
            config.PORTAL_MAX_SIZE,
        )
        if not connected:
            return
        valid = portal_logic.collect_stable_portal(
            pos,
            getter,
            config.PORTAL_IDENTIFIER,
            1,
            config.PORTAL_MAX_SIZE,
        )
        if valid:
            return
        for portalPos in connected:
            self._set_block(portalPos, "minecraft:water", dimensionId)

    def OnBossSyncAck(self, args):
        playerId = args.get("__id__")
        if playerId is None:
            return
        try:
            sequence = max(0, int(args.get("seq", 0)))
            serverTick = max(0, int(args.get("serverTick", 0)))
        except (TypeError, ValueError):
            return
        if sequence > self._sequence:
            return
        self._client_acks[playerId] = {
            "seq": sequence,
            "serverTick": min(serverTick, self._tick),
        }

    def OnPortalArrivalClientReady(self, args):
        playerId = args.get("__id__")
        request = self._pending_portal_entries.get(playerId)
        if (
            request is None
            or request.get("state") != "client_loading"
            or request.get("clientReady")
            or str(args.get("token", ""))
            != str(request.get("clientReadyToken", ""))
        ):
            return
        releaseAtTick = self._schedule_portal_client_release(request)
        self._entry_trace(
            "entry.bootstrap.client_ready.ack",
            playerId=playerId,
            position=request.get("relocationFootPos"),
            releaseAtTick=releaseAtTick,
        )

    def OnPortalArrivalEngineReady(self, args):
        playerId = args.get("__id__")
        request = self._pending_portal_entries.get(playerId)
        if (
            request is None
            or request.get("state") != "awaiting_engine_ready"
            or request.get("clientEngineReady")
            or str(args.get("token", ""))
            != str(request.get("clientEngineReadyToken", ""))
        ):
            return
        request["clientEngineReadyPending"] = False
        request["clientEngineReady"] = True
        request["nextAttemptTick"] = self._tick + 1
        self._entry_trace(
            "entry.direct.engine_ready.ack",
            playerId=playerId,
            position=request.get("preparedExit"),
            relocateAtTick=request["nextAttemptTick"],
        )
