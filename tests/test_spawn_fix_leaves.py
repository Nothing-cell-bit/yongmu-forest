"""Production spawn events and script dispatch with only SDK boundaries faked."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.test_portal_arrival_runtime import SERVER
from tests.test_structure_worldgen_handoff import SERVICE, FakeFactory
from tests.test_spawn_rules_audit import locked_json, source_rows

ROOT = Path(__file__).resolve().parents[1]
DIMENSION = 33027004
FOREST = SERVICE.biome_catalog.BIOMES_BY_KEY["forest"]["identifier"]
SPOOKY = SERVICE.biome_catalog.BIOMES_BY_KEY["spooky_forest"]["identifier"]
LEAVES = sorted(json.loads(path.read_text(encoding="utf-8"))["minecraft:block"]["description"]["identifier"]
                for path in (ROOT / "TwilightBossSliceB/netease_blocks").glob("*leaves*.json"))


def service_scene(support="minecraft:stone", biome=SPOOKY, light=0):
    factory = FakeFactory()
    spawned = []
    factory.biome.name = biome
    factory.block.GetBlockLightLevel = lambda pos, dimension: light
    factory.block.GetBlockNew = lambda pos, dimension: {
        "name": support if pos[1] == 63 else "minecraft:air", "aux": 0,
    }

    def create(identifier, position, yaw, dimension):
        spawned.append((identifier, position, dimension))
        return "spawned-%d" % len(spawned)

    service = SERVICE.StructureWorldgenService(factory, "level", DIMENSION, create)
    player = {"playerId": "player", "dimensionId": DIMENSION, "position": [0.5, 64, 0.5]}
    return service, player, spawned, factory


@pytest.mark.parametrize("leaf", LEAVES)
def test_every_declared_leaf_is_rejected_by_both_script_ground_checks(leaf):
    service, _, _, _ = service_scene(leaf)
    assert not service._is_hollow_hill_spawn_position_clear((-8.5, 64, 17.5))
    assert not service._controlled_structure_spawn_position_clear("tf_slice:skeleton_druid", (-8.5, 64, 17.5))


def test_solid_ground_control_and_unknown_support():
    service, _, _, factory = service_scene()
    assert service._is_hollow_hill_spawn_position_clear((-8.5, 64, 17.5))
    factory.block.GetBlockNew = lambda pos, dim: None if pos[1] == 63 else {"name": "minecraft:air"}
    assert not service._is_hollow_hill_spawn_position_clear((-8.5, 64, 17.5))


@pytest.mark.parametrize("leaf", LEAVES)
def test_native_spawn_event_rejects_leaf_support_at_negative_coordinates(leaf):
    system = object.__new__(SERVER.ServerSystem)
    system._block_comp = SimpleNamespace(GetBlockNew=lambda pos, dim: {"name": leaf})
    system._biome_comp = SimpleNamespace(GetBiomeName=lambda pos, dim: FOREST)
    args = {"identifier": "tf_slice:deer", "realIdentifier": "tf_slice:deer", "dimensionId": DIMENSION,
            "x": -8.5, "y": 64, "z": 17.5}
    system.OnServerSpawnMob(args)
    assert args.get("cancel") is True


@pytest.mark.parametrize("key", ["dark_forest", "spooky_forest", "swamp"])
def test_controlled_monster_tables_match_locked_source(key):
    biome = SERVICE.biome_catalog.BIOMES_BY_KEY[key]["identifier"]
    expected = source_rows(locked_json("worldgen/biome/" + key + ".json")["spawners"]["monster"])
    assert sorted(SERVER.spawn_policy.CONTROLLED_MONSTER_POOLS[biome]) == expected


def test_spooky_druid_has_a_real_tick_spawn_route():
    service, player, spawned, _ = service_scene()
    for tick in range(40, 1601, 40):
        service.tick(tick, [player])
    assert any(call[0] == "tf_slice:skeleton_druid" for call in spawned)
    assert set(call[0] for call in spawned) <= {"tf_slice:skeleton_druid", "minecraft:spider", "minecraft:skeleton"}


@pytest.mark.parametrize("support,light,enabled", [("tf_slice:hardened_dark_leaves", 0, True),
                                                   ("minecraft:stone", 15, True),
                                                   ("minecraft:stone", 0, False)])
def test_spooky_spawn_rejects_leaves_bright_light_and_peaceful(support, light, enabled):
    service, player, spawned, _ = service_scene(support=support, light=light)
    for tick in range(40, 401, 40):
        service.tick(tick, [player], boss_spawning_enabled=enabled)
    assert spawned == []


class MobSDK:
    def __init__(self, deferred=False):
        self.deferred = deferred
        self.extra = {}
        self.types = {}
        self.positions = {}
        self.created = []
        self.callbacks = []
        self.fail_save = set()
        self.ready = True
        self.support = "minecraft:stone"
        self.mounts = []

    def CreatePos(self, entity):
        return SimpleNamespace(GetFootPos=lambda: self.positions.get(str(entity)))

    def CreateEngineType(self, entity):
        return SimpleNamespace(GetEngineTypeStr=lambda: self.types.get(str(entity)))

    def CreateExtraData(self, entity):
        owner = str(entity)
        data = self.extra.setdefault(owner, {})

        def set_data(key, value, autoSave=True):
            if owner in self.fail_save:
                return False
            data[key] = copy.deepcopy(value)
            return True

        return SimpleNamespace(GetExtraData=lambda key: copy.deepcopy(data.get(key)), SetExtraData=set_data)

    def CreateGame(self, entity):
        return SimpleNamespace(GetGameDiffculty=lambda: 2)

    def CreateRide(self, entity):
        return SimpleNamespace(SetRiderRideEntity=lambda rider, mount, seat: self.mounts.append((rider, mount)) or True,
                               SetEntityLockRider=lambda locked: True)

    def GetBlockNew(self, position, dimension):
        return {"name": self.support if position[1] == 63 else "minecraft:air"}

    def CheckChunkState(self, dimension, position):
        return self.ready

    def host(self):
        host = object.__new__(SERVER.ServerSystem)
        host._tick = 1
        host._ruin_mobs = {}
        host._phantom_urghast_mobs = {}
        host._pending_swarm_children = host._pending_broodling_children = 0
        host._block_comp = host._chunk_comp = self
        host._biome_comp = SimpleNamespace(GetBiomeName=lambda pos, dim: FOREST)

        def create(identifier, position, rotation, dimension, *flags):
            entity = "child-%d" % len(self.created)
            self.types[entity] = identifier
            self.positions[entity] = tuple(position)
            self.created.append((entity, identifier, tuple(position)))
            if self.deferred:
                self.callbacks.append((host, entity))
            else:
                self.deliver(host, entity)
            return entity

        host.CreateEngineEntityByTypeStr = create
        host.DestroyEntity = lambda entity: self.types.pop(str(entity), None)
        return host

    def deliver(self, host, entity, fresh=True, reversed_order=False):
        args = {"id": entity, "engineTypeStr": self.types[entity], "dimensionId": DIMENSION}
        pos = self.positions[entity]
        spawn = {"entityId": entity, "identifier": "custom", "realIdentifier": self.types[entity],
                 "dimensionId": DIMENSION, "x": pos[0], "y": pos[1], "z": pos[2]}
        if reversed_order:
            host.OnAddEntity(dict(args))
        if fresh:
            host.OnServerSpawnMob(spawn)
        if not reversed_order:
            host.OnAddEntity(dict(args))

    def drain(self):
        pending, self.callbacks = self.callbacks, []
        for host, entity in pending:
            if entity in self.types:
                self.deliver(host, entity)


@pytest.mark.parametrize("kind", ["tf_slice:swarm_spider", "tf_slice:tower_broodling", "tf_slice:king_spider"])
def test_rebinding_old_entities_never_creates_new_companions_or_riders(kind):
    sdk = MobSDK()
    sdk.types["parent"] = kind
    sdk.positions["parent"] = (0.5, 64, 0.5)
    with patch.object(SERVER, "CF", sdk):
        host = sdk.host()
        sdk.deliver(host, "parent", fresh=False)
        sdk.deliver(host, "parent", fresh=False)
    assert sdk.created == []


@pytest.mark.parametrize("deferred,reversed_order", [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("kind", ["tf_slice:swarm_spider", "tf_slice:tower_broodling"])
def test_parent_and_children_stay_initialized_across_event_orders_and_restart(deferred, reversed_order, kind):
    sdk = MobSDK(deferred=deferred)
    sdk.types["parent"] = kind
    sdk.positions["parent"] = (0.5, 64, 0.5)
    with patch.object(SERVER, "CF", sdk), patch.object(SERVER.random, "randint", return_value=2), patch.object(SERVER.random, "randrange", return_value=19):
        host = sdk.host()
        sdk.deliver(host, "parent", reversed_order=reversed_order)
        host._process_initial_mob_spawns()
        sdk.drain()
        host._tick += 1
        host._process_initial_mob_spawns()
        assert len(sdk.created) == 2
        restored = sdk.host()
        for entity in list(sdk.types):
            sdk.deliver(restored, entity)
        restored._process_initial_mob_spawns()
        assert len(sdk.created) == 2


def test_failed_parent_save_defers_side_effects_until_a_successful_claim():
    sdk = MobSDK()
    sdk.types["parent"] = "tf_slice:swarm_spider"
    sdk.positions["parent"] = (0.5, 64, 0.5)
    sdk.fail_save.add("parent")
    with patch.object(SERVER, "CF", sdk), patch.object(SERVER.random, "randint", return_value=1), patch.object(SERVER.random, "randrange", return_value=19):
        host = sdk.host()
        sdk.deliver(host, "parent")
        host._process_initial_mob_spawns()
        assert sdk.created == []
        sdk.fail_save.clear()
        host._tick += 1
        host._process_initial_mob_spawns()
        assert len(sdk.created) == 1


@pytest.mark.parametrize("support,ready", [("tf_slice:rainbow_oak_leaves_15", True), ("minecraft:stone", False)])
def test_companion_attempts_never_create_on_leaves_or_in_unloaded_chunks(support, ready):
    sdk = MobSDK()
    sdk.types["parent"] = "tf_slice:swarm_spider"
    sdk.positions["parent"] = (0.5, 64, 0.5)
    sdk.support = support
    sdk.ready = ready
    with patch.object(SERVER, "CF", sdk), patch.object(SERVER.random, "randrange", return_value=19):
        host = sdk.host()
        sdk.deliver(host, "parent")
        host._process_initial_mob_spawns()
        assert sdk.created == []


def test_failed_child_marker_and_failed_removal_do_not_allow_late_child_expansion():
    sdk = MobSDK(deferred=True)
    sdk.types["parent"] = "tf_slice:swarm_spider"
    sdk.positions["parent"] = (0.5, 64, 0.5)
    sdk.fail_save.add("child-0")
    with patch.object(SERVER, "CF", sdk), patch.object(SERVER.random, "randint", return_value=1), patch.object(SERVER.random, "randrange", return_value=19):
        host = sdk.host()
        host.DestroyEntity = lambda entity: False
        sdk.deliver(host, "parent")
        host._process_initial_mob_spawns()
        sdk.drain()
        sdk.fail_save.clear()
        host._tick += 1
        host._process_initial_mob_spawns()
        assert len(sdk.created) == 1


def test_mod_leaves_are_forbidden_in_other_dimensions_too_with_floor_coordinates():
    system = object.__new__(SERVER.ServerSystem)
    queried = []
    system._block_comp = SimpleNamespace(GetBlockNew=lambda pos, dim: queried.append((pos, dim)) or {"name": "tf_slice:hardened_dark_leaves_center"})
    system._biome_comp = SimpleNamespace(GetBiomeName=lambda pos, dim: FOREST)
    args = {"identifier": "tf_slice:deer", "dimensionId": DIMENSION, "x": -8.5, "y": 74, "z": -0.1}
    system.OnServerSpawnMob(args)
    assert args["cancel"] is True
    assert queried == [((-9, 73, -1), DIMENSION)]
    queried.clear()
    args = dict(args, dimensionId=0, cancel=False)
    system.OnServerSpawnMob(args)
    assert args["cancel"] and queried == [((-9, 73, -1), 0)]
    queried.clear()
    system._block_comp = SimpleNamespace(GetBlockNew=lambda pos, dim: {"name": "minecraft:stone"})
    args = dict(args, cancel=False)
    system.OnServerSpawnMob(args)
    assert not args["cancel"]


def test_cancelled_spawn_never_queues_initialization():
    sdk = MobSDK()
    with patch.object(SERVER, "CF", sdk):
        host = sdk.host()
        host.OnServerSpawnMob({"entityId": "cancelled", "identifier": "custom", "realIdentifier": "tf_slice:swarm_spider",
                               "dimensionId": DIMENSION, "cancel": True})
        assert not getattr(host, "_pending_initial_mob_spawns", {})


def test_unloaded_script_spawn_sites_never_query_support_blocks():
    service, _, _, factory = service_scene()
    factory.chunk.ready = False
    calls = []
    factory.block.GetBlockNew = lambda pos, dim: calls.append(pos) or {"name": "minecraft:stone"}
    assert not service._is_hollow_hill_spawn_position_clear((-0.2, 64, -16.1))
    assert not service._controlled_structure_spawn_position_clear("tf_slice:skeleton_druid", (-0.2, 64, -16.1))
    assert calls == []


def test_structure_leaf_guard_checks_the_actual_negative_coordinate_chunk():
    service, _, _, factory = service_scene()
    factory.chunk.ready_chunks = {(-1, -2)}
    assert service._chunk_position_ready(-0.2, 64, -16.1)
    assert factory.chunk.checked[-1][1] == (-8, 64, -24)


def test_missing_light_reading_defers_a_controlled_monster_spawn():
    service, player, spawned, factory = service_scene()
    factory.block.GetBlockLightLevel = lambda pos, dim: None
    for tick in range(40, 241, 40):
        service.tick(tick, [player])
    assert spawned == []


def test_spooky_native_monsters_are_replaced_but_ambient_bats_are_kept():
    for identifier in ("minecraft:spider", "minecraft:skeleton", "tf_slice:skeleton_druid", "minecraft:bat"):
        cancelled = SERVER.spawn_policy.should_cancel_twilight_spawn(
            {"identifier": identifier, "dimensionId": DIMENSION}, DIMENSION, biome_identifier=SPOOKY)
        assert cancelled == (identifier != "minecraft:bat")


def test_swamp_tick_uses_both_source_species_and_brightness_rules():
    swamp = SERVICE.biome_catalog.BIOMES_BY_KEY["swamp"]["identifier"]
    service, player, spawned, _ = service_scene(biome=swamp, light=0)
    for tick in range(40, 1601, 40):
        service.tick(tick, [player])
    assert {call[0] for call in spawned} == {"minecraft:zombie", "tf_slice:mosquito_swarm"}
    bright, player, spawned, _ = service_scene(biome=swamp, light=15)
    for tick in range(40, 801, 40):
        bright.tick(tick, [player])
    assert spawned and {call[0] for call in spawned} == {"tf_slice:mosquito_swarm"}


def test_group_parents_initialize_once_and_only_parents_receive_jockeys():
    sdk = MobSDK()
    sdk.types["parent"] = "tf_slice:swarm_spider"
    sdk.positions["parent"] = (0.5, 64, 0.5)
    with patch.object(SERVER, "CF", sdk), patch.object(SERVER.random, "randint", return_value=2), patch.object(SERVER.random, "randrange", return_value=0):
        host = sdk.host()
        sdk.deliver(host, "parent")
        host._process_initial_mob_spawns()
        assert [entry[1] for entry in sdk.created].count("tf_slice:swarm_spider") == 2
        assert [entry[1] for entry in sdk.created].count("tf_slice:skeleton_druid") == 1
        assert len(sdk.mounts) == 1 and sdk.mounts[0][1] == "parent"
        sdk.deliver(host, "parent")
        host._process_initial_mob_spawns()
        assert len(sdk.created) == 3 and len(sdk.mounts) == 1


def test_king_spider_receives_one_rider_and_never_repeats_it_after_restart():
    sdk = MobSDK()
    sdk.types["parent"] = "tf_slice:king_spider"
    sdk.positions["parent"] = (0.5, 64, 0.5)
    with patch.object(SERVER, "CF", sdk):
        host = sdk.host()
        sdk.deliver(host, "parent")
        host._process_initial_mob_spawns()
        assert [entry[1] for entry in sdk.created] == ["tf_slice:skeleton_druid"]
        restored = sdk.host()
        sdk.deliver(restored, "parent")
        restored._process_initial_mob_spawns()
        assert len(sdk.created) == 1


def test_initialization_queue_is_bounded_fair_and_expires_missing_actors():
    sdk = MobSDK()
    with patch.object(SERVER, "CF", sdk):
        host = sdk.host()
        for number in range(140):
            host.OnServerSpawnMob({"entityId": "missing-%03d" % number, "identifier": "custom",
                                   "realIdentifier": "tf_slice:swarm_spider", "dimensionId": DIMENSION})
        assert len(host._pending_initial_mob_spawns) == SERVER.MAX_INITIAL_MOB_SPAWNS
        host._process_initial_mob_spawns()
        assert sum(record["lastTried"] == host._tick for record in host._pending_initial_mob_spawns.values()) == SERVER.INITIAL_MOB_SPAWNS_PER_TICK
        host._tick = 1000
        for _ in range(20):
            host._process_initial_mob_spawns()
        assert not host._pending_initial_mob_spawns


def test_update_dispatches_spawn_initialization_from_the_production_tick():
    source = (ROOT / "TwilightBossSliceB/TwilightBossSlice/serverSystem.py").read_text(encoding="utf-8")
    update = source[source.index("    def Update(self):"):]
    update = update[:update.index("\n    def ", 1)]
    assert "self._process_initial_mob_spawns()" in update
