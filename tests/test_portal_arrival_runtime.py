import os
import pathlib
import sys
import types
import unittest
import warnings

from lib2to3.refactor import RefactoringTool


ROOT = pathlib.Path(__file__).resolve().parents[1]
BP = pathlib.Path(
    os.environ.get(
        "TF_SLICE_BEHAVIOR_PACK",
        str(ROOT / "TwilightBossSliceB"),
    )
)
SERVER_PATH = BP / "TwilightBossSlice" / "serverSystem.py"
sys.path.insert(0, str(BP))


class FakeBlockInfo(object):
    def __init__(self):
        self.terrain_ready = False
        self.level_chunk_readable = True
        self.writable = False
        self.reject_portal = False
        self.blocks = {}
        self.writes = []
        self.top_queries = []

    def GetTopBlockHeight(self, _position, _dimension_id):
        self.top_queries.append((tuple(_position), int(_dimension_id)))
        return 78 if self.terrain_ready else None

    def GetBlockNew(self, position, _dimension_id):
        if not self.level_chunk_readable:
            return None
        if position in self.blocks:
            return {"name": self.blocks[position], "aux": 0}
        x, y, z = position
        if (x, z) == (35, 62):
            if y == 78:
                return {"name": "tf_slice:twilight_oak_leaves", "aux": 0}
            if y in (76, 77):
                return {"name": "tf_slice:twilight_oak_log", "aux": 0}
            if y == 64:
                return {"name": "minecraft:grass_block", "aux": 0}
            if y < 64:
                return {"name": "minecraft:dirt", "aux": 0}
        return {"name": "minecraft:air", "aux": 0}

    def SetBlockNew(
        self,
        position,
        block,
        _old_block_handling,
        _dimension_id,
        _is_update,
        _send_event,
    ):
        name = block["name"]
        self.writes.append((position, name))
        if not self.writable:
            return False
        if self.reject_portal and name == "tf_slice:twilight_portal":
            # Reproduce the observed ModSDK case: the engine logs a rejected
            # write while the Python API does not reliably return False.
            return None
        self.blocks[position] = name
        return True


class FakeChunkSource(object):
    def __init__(self):
        self.added = []
        self.deleted = []
        self.checked = []
        self.ready = True
        self.async_tasks = []

    def SetAddArea(self, key, dimension_id, minimum, maximum):
        self.added.append((key, dimension_id, minimum, maximum))
        return True

    def DeleteArea(self, key):
        self.deleted.append(key)
        return True

    def CheckChunkState(self, dimension_id, position):
        self.checked.append((dimension_id, tuple(position)))
        return self.ready

    def DoTaskOnChunkAsync(
        self,
        dimension_id,
        minimum,
        maximum,
        callback,
    ):
        self.async_tasks.append(
            (
                dimension_id,
                tuple(minimum),
                tuple(maximum),
                callback,
            )
        )
        return True


class FakePos(object):
    def __init__(self, factory):
        self.factory = factory

    def SetPos(self, position):
        self.factory.positions.append(tuple(position))
        return True


class FakeActorMotion(object):
    def __init__(self, factory):
        self.factory = factory

    def SetMotion(self, motion):
        self.factory.entity_motions.append(tuple(motion))
        return True

    def SetPlayerMotion(self, motion):
        self.factory.motions.append(tuple(motion))
        return True


class FakeGravity(object):
    def __init__(self):
        self.value = 0.0
        self.calls = []

    def GetGravity(self):
        return self.value

    def SetGravity(self, gravity):
        self.value = float(gravity)
        self.calls.append(self.value)
        return True


class FakeCommand(object):
    def __init__(self, factory):
        self.factory = factory

    def SetCommand(self, command):
        self.factory.commands.append(command)
        if command.startswith("/summon lightning_bolt "):
            self.factory.block.blocks[(35, 71, 62)] = "minecraft:fire"
            self.factory.block.blocks[(36, 70, 62)] = "minecraft:fire"
        return True


class FakeExtraData(object):
    def __init__(self):
        self.values = {}
        self.save_count = 0

    def GetExtraData(self, key):
        return self.values.get(key)

    def SetExtraData(self, key, value, _auto_save):
        self.values[key] = value
        return True

    def SaveExtraData(self):
        self.save_count += 1
        return True


class FakeFactory(object):
    def __init__(self):
        self.block = FakeBlockInfo()
        self.chunk = FakeChunkSource()
        self.positions = []
        self.entity_motions = []
        self.motions = []
        self.gravity = FakeGravity()
        self.commands = []
        self.extra = FakeExtraData()

    def CreateBlockInfo(self, _level_id):
        return self.block

    def CreateChunkSource(self, _level_id):
        return self.chunk

    def CreatePos(self, _entity_id):
        return FakePos(self)

    def CreateActorMotion(self, _entity_id):
        return FakeActorMotion(self)

    def CreateGravity(self, _entity_id):
        return self.gravity

    def CreateCommand(self, _level_id):
        return FakeCommand(self)

    def CreateExtraData(self, _level_id):
        return self.extra


FACTORY = FakeFactory()


def load_server_module():
    server_package = types.ModuleType("server")
    server_api = types.ModuleType("server.extraServerApi")
    server_api.GetEngineCompFactory = lambda: FACTORY
    server_api.GetEngineNamespace = lambda: "Minecraft"
    server_api.GetEngineSystemName = lambda: "Server"
    server_api.GetLevelId = lambda: "level"
    server_api.GetServerSystemCls = lambda: object
    server_api.GenerateColor = lambda value: value
    server_package.extraServerApi = server_api

    structure_stub = types.ModuleType(
        "TwilightBossSlice.structureWorldgenService"
    )
    structure_stub.StructureWorldgenService = object
    structure_stub.DEFAULT_LOCATE_RADIUS = 128

    replacements = {
        "server": server_package,
        "server.extraServerApi": server_api,
        "TwilightBossSlice.structureWorldgenService": structure_stub,
    }
    previous = dict(
        (name, sys.modules.get(name)) for name in replacements
    )
    sys.modules.update(replacements)
    try:
        source = SERVER_PATH.read_text(encoding="utf-8")
        if not source.endswith("\n"):
            source += "\n"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            converted = RefactoringTool(
                ["lib2to3.fixes.fix_print"]
            ).refactor_string(source, str(SERVER_PATH))
        module = types.ModuleType("portal_server_under_test")
        module.__file__ = str(SERVER_PATH)
        exec(
            compile(str(converted), str(SERVER_PATH), "exec"),
            module.__dict__,
        )
        return module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


SERVER = load_server_module()


class EngineNotificationRuntimeTests(unittest.TestCase):
    def test_notify_skips_rejected_native_tip_api_and_traces_message(self):
        class FakeGameComponent(object):
            def __init__(self):
                self.calls = []

            def SetNotifyMsg(self, message, color):
                self.calls.append((message, color))
                return True

        component = FakeGameComponent()
        traces = []
        system = object.__new__(SERVER.ServerSystem)
        system.CreateComponent = types.MethodType(
            lambda _system, *_args: component,
            system,
        )
        system._entry_trace = types.MethodType(
            lambda _system, event, **fields: traces.append(
                (event, fields)
            ),
            system,
        )

        system._notify("player", "entry notice", "AQUA")

        self.assertEqual([], component.calls)
        self.assertEqual("notify.native_tip_skipped", traces[0][0])
        self.assertEqual("player", traces[0][1]["playerId"])
        self.assertEqual("AQUA", traces[0][1]["color"])


class FireSwampDiscoveryRuntimeTests(unittest.TestCase):
    def setUp(self):
        FACTORY.block = FakeBlockInfo()
        FACTORY.chunk = FakeChunkSource()
        self.system = object.__new__(SERVER.ServerSystem)
        self.system._tick = 1
        self.system._block_comp = FACTORY.block
        self.system._chunk_comp = FACTORY.chunk
        self.system._block_state_comp = None
        self.system._fire_swamp_devices = {}
        self.system._fire_swamp_discovery_queue = []
        self.system._fire_swamp_discovery_ready_ticks = {"player": 0}
        self.system._get_online_players = types.MethodType(
            lambda _system: ["player"],
            self.system,
        )
        self.system._get_dimension = types.MethodType(
            lambda _system, _player_id: SERVER.config.DIMENSION_ID,
            self.system,
        )
        self.system._get_foot_pos = types.MethodType(
            lambda _system, _player_id: (35.5, 79.0, 62.5),
            self.system,
        )

    def test_unready_chunk_never_reaches_native_height_query(self):
        FACTORY.chunk.ready = False
        FACTORY.block.terrain_ready = True

        self.system._discover_fire_swamp_devices()

        self.assertTrue(FACTORY.chunk.checked)
        self.assertEqual([], FACTORY.block.top_queries)

    def test_chunk_state_true_is_not_enough_for_native_height_query(self):
        FACTORY.chunk.ready = True
        FACTORY.block.terrain_ready = True
        FACTORY.block.level_chunk_readable = False

        self.system._discover_fire_swamp_devices()

        self.assertTrue(FACTORY.chunk.checked)
        self.assertEqual([], FACTORY.block.top_queries)

    def test_new_twilight_arrival_observes_discovery_grace(self):
        FACTORY.block.terrain_ready = True
        self.system._delay_fire_swamp_discovery("player")

        self.system._discover_fire_swamp_devices()

        self.assertEqual([], FACTORY.block.top_queries)
        self.assertEqual(
            self.system._tick + 80,
            self.system._fire_swamp_discovery_ready_ticks["player"],
        )

    def test_ready_scan_is_split_across_ticks(self):
        FACTORY.block.terrain_ready = True

        self.system._discover_fire_swamp_devices()
        first_tick_queries = len(FACTORY.block.top_queries)
        self.system._tick += 1
        self.system._discover_fire_swamp_devices()
        second_tick_queries = (
            len(FACTORY.block.top_queries) - first_tick_queries
        )

        self.assertGreater(first_tick_queries, 0)
        self.assertLessEqual(first_tick_queries, 16)
        self.assertGreater(second_tick_queries, 0)
        self.assertLessEqual(second_tick_queries, 16)


class WorldgenTransitionGuardRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.system = object.__new__(SERVER.ServerSystem)
        self.system._tick = 20
        self.system._dimension_change_in_progress = {"player"}
        self.system._pending_portal_entries = {}
        self.system._dimension_worldgen_ready_ticks = {}
        self.system._get_online_players = types.MethodType(
            lambda _system: ["player"],
            self.system,
        )
        self.system._get_foot_pos = types.MethodType(
            lambda _system, _player_id: (35.5, 79.0, 62.5),
            self.system,
        )
        self.system._get_dimension = types.MethodType(
            lambda _system, _player_id: SERVER.config.DIMENSION_ID,
            self.system,
        )
        self.system._progress_for_player = types.MethodType(
            lambda _system, _player_id: {},
            self.system,
        )

    def test_transitioning_player_is_hidden_from_worldgen_services(self):
        self.assertEqual([], self.system._ruin_player_snapshots())

    def test_finished_player_waits_for_native_component_grace(self):
        self.system._dimension_change_in_progress.clear()
        self.system._dimension_worldgen_ready_ticks["player"] = 100

        self.assertEqual([], self.system._ruin_player_snapshots())

        self.system._tick = 100
        self.assertEqual(1, len(self.system._ruin_player_snapshots()))

    def test_native_structure_events_are_bypassed_without_mutation_during_staged_entry(self):
        calls = []

        class FakeWorldgenService(object):
            def on_structure_feature_event(self, event):
                calls.append(event)

        self.system._ruin_worldgen = FakeWorldgenService()
        self.system._mushroom_worldgen = FakeWorldgenService()
        self.system._enchanted_tree_worldgen = FakeWorldgenService()
        event = {
            "dimensionId": SERVER.config.DIMENSION_ID,
            "structureName": "tf_slice:hollow_tree_chunk_trigger",
            "cancel": False,
        }

        self.system.OnPlaceNeteaseStructureFeatureEvent(event)

        self.assertFalse(event["cancel"])
        self.assertEqual([], calls)

    def test_native_structure_features_resume_after_twilight_entry(self):
        calls = []

        class FakeWorldgenService(object):
            def on_structure_feature_event(self, event):
                calls.append(event["structureName"])

        self.system._dimension_change_in_progress.clear()
        self.system._ruin_worldgen = FakeWorldgenService()
        self.system._mushroom_worldgen = None
        self.system._enchanted_tree_worldgen = None
        event = {
            "dimensionId": SERVER.config.DIMENSION_ID,
            "structureName": "tf_slice:hollow_tree_chunk_trigger",
            "cancel": False,
        }

        self.system.OnPlaceNeteaseStructureFeatureEvent(event)

        self.assertFalse(event["cancel"])
        self.assertEqual(
            ["tf_slice:hollow_tree_chunk_trigger"],
            calls,
        )

    def test_structure_dispatch_calls_only_the_trigger_owner(self):
        calls = []

        class FakeWorldgenService(object):
            def __init__(self, name):
                self.name = name

            def on_structure_feature_event(self, _event):
                calls.append(self.name)

        self.system._dimension_change_in_progress.clear()
        self.system._ruin_worldgen = FakeWorldgenService("ruin")
        self.system._mushroom_worldgen = FakeWorldgenService("mushroom")
        self.system._enchanted_tree_worldgen = FakeWorldgenService("tree")

        self.system.OnPlaceNeteaseStructureFeatureEvent(
            {
                "dimensionId": SERVER.config.DIMENSION_ID,
                "structureName": "tf_slice:mushroom/canopy_trigger/red",
            }
        )

        self.assertEqual(["mushroom"], calls)

    def test_direct_entry_keeps_pure_native_structure_dispatch_enabled(self):
        calls = []

        class FakeWorldgenService(object):
            def on_structure_feature_event(self, event):
                calls.append(event["structureName"])

        self.system._pending_portal_entries["player"] = {
            "directEntry": True,
        }
        self.system._ruin_worldgen = FakeWorldgenService()
        self.system._mushroom_worldgen = None
        self.system._enchanted_tree_worldgen = None
        event = {
            "dimensionId": SERVER.config.DIMENSION_ID,
            "structureName": "tf_slice:hollow_tree_chunk_trigger",
            "cancel": False,
        }

        self.system.OnPlaceNeteaseStructureFeatureEvent(event)

        self.assertFalse(event["cancel"])
        self.assertEqual(
            ["tf_slice:hollow_tree_chunk_trigger"],
            calls,
        )


class PortalArrivalRuntimeTests(unittest.TestCase):
    SOURCE_SURFACE = (
        (35, 70, 62),
        (36, 70, 62),
        (35, 70, 63),
        (36, 70, 63),
    )

    def _direct_entry_foot_pos(self):
        return (
            34.5,
            SERVER.config.WORLDGEN_DIRECT_ENTRY_FOOT_Y,
            62.5,
        )

    def setUp(self):
        FACTORY.block = FakeBlockInfo()
        FACTORY.chunk = FakeChunkSource()
        FACTORY.positions = []
        FACTORY.entity_motions = []
        FACTORY.motions = []
        FACTORY.gravity = FakeGravity()
        FACTORY.commands = []
        FACTORY.extra = FakeExtraData()
        self.dimension_id = 0
        self.dimension_changes = []
        self.notifications = []
        self.client_notifications = []
        self.entry_events = []
        self.now_seconds = 1000.0
        self.system = object.__new__(SERVER.ServerSystem)
        self.system._tick = 0
        self.system._portal_area_sequence = 0
        self.system._pending_portal_entries = {}
        self.system._portal_background_preload_queue = []
        self.system._portal_background_preload_keys = set()
        self.system._portal_background_preload_inflight = None
        self.system._worldgen_perf_counters = {}
        self.system._worldgen_perf_structure_counts = {}
        self.system._portal_links = {}
        self.system._return_points = {}
        self.system._portal_extra = FACTORY.extra
        self.system._pending_portal_recovery_players = set()
        self.system._known_players = set()
        self.system._portal_cooldowns = {}
        self.system._portal_fire_cleanups = []
        self.system._dimension_change_in_progress = set()
        self.system._block_comp = FACTORY.block
        self.system._chunk_comp = FACTORY.chunk

        def entry_trace(_system, event, **fields):
            self.entry_events.append((event, fields))
            return True

        self.system._entry_trace = types.MethodType(
            entry_trace,
            self.system,
        )

        def get_dimension(_system, _player_id):
            return self.dimension_id

        def get_position(_system, _player_id):
            return (35.5, 71.0, 62.5)

        def change_dimension(_system, player_id, dimension_id, position):
            self.dimension_changes.append(
                (player_id, dimension_id, tuple(position))
            )
            self.dimension_id = dimension_id
            return True

        def notify(_system, player_id, message, color="GREEN"):
            self.notifications.append((player_id, message, color))

        self.system._get_dimension = types.MethodType(
            get_dimension,
            self.system,
        )
        self.system._get_foot_pos = types.MethodType(
            get_position,
            self.system,
        )
        self.system._change_dimension = types.MethodType(
            change_dimension,
            self.system,
        )
        self.system._notify = types.MethodType(notify, self.system)
        self.system._configure_twilight_time = types.MethodType(
            lambda _system: None,
            self.system,
        )
        self.system.NotifyToClient = types.MethodType(
            lambda _system, player_id, event, payload: (
                self.client_notifications.append(
                    (player_id, event, dict(payload))
                )
            ),
            self.system,
        )
        self.system._make_sync_packet = types.MethodType(
            lambda _system, _player_id=None: {},
            self.system,
        )
        self.system._make_perf_packet = types.MethodType(
            lambda _system: {},
            self.system,
        )
        self.system._portal_now_seconds = types.MethodType(
            lambda _system: self.now_seconds,
            self.system,
        )
        self.system._get_rotation = types.MethodType(
            lambda _system, _player_id: (0.0, 0.0),
            self.system,
        )

    def _queue_and_start_loading(self):
        self.system._enter_slice(
            "player",
            sourceSurface=self.SOURCE_SURFACE,
        )
        self.assertEqual([], self.dimension_changes)
        self.system._tick = 1
        self.system._process_portal_arrivals()
        self.assertEqual([], FACTORY.chunk.checked)
        self.assertEqual([], FACTORY.chunk.added)
        self.assertEqual([], FACTORY.chunk.deleted)
        self.assertEqual(
            [
                (
                    "player",
                    SERVER.config.DIMENSION_ID,
                    SERVER.portal_logic.player_position_from_foot(
                        self._direct_entry_foot_pos()
                    ),
                )
            ],
            self.dimension_changes,
        )
        self.assertEqual(
            "changing_dimension",
            self.system._pending_portal_entries["player"]["state"],
        )

    def _finish_bootstrap_arrival(self):
        self.system.OnDimensionChangeFinish(
            {
                "playerId": "player",
                "fromDimensionId": 0,
                "toDimensionId": SERVER.config.DIMENSION_ID,
                "toPos": SERVER.portal_logic.player_position_from_foot(
                    self._direct_entry_foot_pos()
                ),
            }
        )
        request = self.system._pending_portal_entries["player"]
        self.assertTrue(request["recovery"])
        self.assertTrue(request["directEntry"])
        self.assertEqual("loading", request["state"])
        self.assertEqual((35, 62), request["destinationXZ"])
        self.assertNotIn("areaKey", request)
        self.assertEqual([], FACTORY.positions)

    def _ack_client_ready(self):
        request = self.system._pending_portal_entries["player"]
        if request.get("state") == "awaiting_engine_ready":
            self._ack_engine_ready()
            request = self.system._pending_portal_entries["player"]
        self.system.OnPortalArrivalClientReady(
            {
                "__id__": "player",
                "token": request["clientReadyToken"],
            }
        )
        self.system._tick = max(
            self.system._tick,
            request.get("nextAttemptTick", self.system._tick),
        )
        self.system._process_portal_arrivals()

    def _ack_engine_ready(self):
        request = self.system._pending_portal_entries["player"]
        self.system.OnPortalArrivalEngineReady(
            {
                "__id__": "player",
                "token": request["clientEngineReadyToken"],
            }
        )
        self.system._process_portal_arrivals()
        self.system._tick = request["nextAttemptTick"]
        self.system._process_portal_arrivals()

    def _advance_to_ready_tick(self, acknowledge_client=True):
        for _unused in range(10):
            request = self.system._pending_portal_entries.get("player")
            if request is None:
                break
            self.system._tick = max(
                self.system._tick,
                request.get("nextAttemptTick", self.system._tick),
                request.get("readyTick", self.system._tick),
            )
            self.system._process_portal_arrivals()
            request = self.system._pending_portal_entries.get("player")
            if (
                acknowledge_client
                and request is not None
                and request.get("state") == "awaiting_engine_ready"
            ):
                self._ack_engine_ready()
                request = self.system._pending_portal_entries.get("player")
            if (
                acknowledge_client
                and request is not None
                and request.get("state") == "client_loading"
            ):
                self._ack_client_ready()

    def test_relocation_waits_for_client_render_ack_before_release(self):
        self._queue_and_start_loading()
        self._finish_bootstrap_arrival()
        FACTORY.block.terrain_ready = True
        FACTORY.block.writable = True

        self._advance_to_ready_tick(acknowledge_client=False)

        request = self.system._pending_portal_entries["player"]
        self.assertEqual("awaiting_engine_ready", request["state"])
        self.assertTrue(request["clientEngineReadyPending"])
        self.assertEqual([], FACTORY.positions)
        self.assertEqual(
            SERVER.config.PORTAL_STAGING_GRAVITY,
            FACTORY.gravity.value,
        )
        self.assertEqual([], FACTORY.chunk.deleted)
        self.assertEqual(
            (
                "player",
                "PortalArrivalPrepared",
                {
                    "position": (34.5, 66.0, 62.5),
                    "token": request["clientEngineReadyToken"],
                },
            ),
            self.client_notifications[-1],
        )

        self.system.OnPortalArrivalEngineReady(
            {"__id__": "player", "token": "wrong"}
        )
        self.system._process_portal_arrivals()
        self.assertEqual([], FACTORY.positions)

        self.system.OnPortalArrivalEngineReady(
            {
                "__id__": "player",
                "token": request["clientEngineReadyToken"],
            }
        )
        self.system._process_portal_arrivals()
        self.assertTrue(request["clientEngineReady"])
        self.assertEqual([], FACTORY.positions)

        self.system._tick = request["nextAttemptTick"]
        self.system._process_portal_arrivals()

        request = self.system._pending_portal_entries["player"]
        self.assertEqual("client_loading", request["state"])
        self.assertTrue(request["clientReadyPending"])
        self.assertEqual([(34.5, 66.0, 62.5)], FACTORY.positions)
        self.assertEqual("PortalArrivalRelocated", self.client_notifications[-1][1])

        self.system.OnPortalArrivalClientReady(
            {
                "__id__": "player",
                "token": request["clientReadyToken"],
            }
        )
        self.system._process_portal_arrivals()

        request = self.system._pending_portal_entries["player"]
        self.assertTrue(request["clientReady"])
        self.assertEqual([], FACTORY.chunk.deleted)
        self.system._tick = request["clientReadyReleaseTick"] - 1
        self.system._process_portal_arrivals()
        self.assertIn("player", self.system._pending_portal_entries)
        self.assertEqual([], FACTORY.chunk.deleted)

        self.system._tick = request["clientReadyReleaseTick"]
        self.system._process_portal_arrivals()

        self.assertNotIn("player", self.system._pending_portal_entries)
        self.assertEqual(0.0, FACTORY.gravity.value)
        self.assertEqual([], FACTORY.chunk.deleted)

    def test_missing_engine_ready_ack_waits_for_safe_fallback_tick(self):
        self._queue_and_start_loading()
        self._finish_bootstrap_arrival()
        FACTORY.block.terrain_ready = True
        FACTORY.block.writable = True
        self._advance_to_ready_tick(acknowledge_client=False)

        request = self.system._pending_portal_entries["player"]
        self.assertEqual("awaiting_engine_ready", request["state"])
        self.system._tick = request["clientEngineReadyFallbackTick"] - 1
        self.system._process_portal_arrivals()
        self.assertEqual([], FACTORY.positions)

        self.system._tick = request["clientEngineReadyFallbackTick"]
        self.system._process_portal_arrivals()
        self.assertTrue(request["clientEngineReadyFallback"])
        self.assertEqual([], FACTORY.positions)

        self.system._tick = request["nextAttemptTick"]
        self.system._process_portal_arrivals()
        self.assertEqual([(34.5, 66.0, 62.5)], FACTORY.positions)
        self.assertEqual(
            "client_loading",
            self.system._pending_portal_entries["player"]["state"],
        )

    def test_server_hard_gate_only_covers_the_three_by_three_safe_core(self):
        request = {"destinationXZ": (35, 62)}
        FACTORY.block.terrain_ready = True

        self.assertTrue(self.system._portal_target_chunks_ready(request))

        checked_positions = {
            position for _dimension_id, position in FACTORY.chunk.checked
        }
        expected_positions = {
            (x, 64, z)
            for x, z in SERVER.portal_logic.client_render_chunk_sample_positions(
                (35.0, 64.0, 62.0),
                SERVER.portal_logic.PORTAL_SERVER_SAFE_CHUNK_RADIUS,
            )
        }
        self.assertEqual(9, len(expected_positions))
        self.assertEqual(expected_positions, checked_positions)

    def test_unready_background_ring_does_not_block_safe_relocation(self):
        request = {"destinationXZ": (35, 62)}
        FACTORY.block.terrain_ready = True
        safe_positions = {
            (x, 64, z)
            for x, z in SERVER.portal_logic.client_render_chunk_sample_positions(
                (35.0, 64.0, 62.0),
                SERVER.portal_logic.PORTAL_SERVER_SAFE_CHUNK_RADIUS,
            )
        }

        def check_chunk_state(_chunk, dimension_id, position):
            FACTORY.chunk.checked.append((dimension_id, tuple(position)))
            return tuple(position) in safe_positions

        FACTORY.chunk.CheckChunkState = types.MethodType(
            check_chunk_state,
            FACTORY.chunk,
        )

        self.assertTrue(self.system._portal_target_chunks_ready(request))
        self.assertEqual(
            safe_positions,
            {
                position
                for _dimension_id, position in FACTORY.chunk.checked
            },
        )

    def test_background_prewarm_is_directional_serial_and_nonblocking(self):
        FACTORY.chunk.ready = False

        queued = self.system._queue_portal_background_preload(
            "player",
            (34.5, 66.0, 62.5),
        )

        self.assertEqual(72, queued)
        self.assertEqual([], FACTORY.chunk.async_tasks)
        self.assertNotIn("player", self.system._pending_portal_entries)

        self.system._process_portal_background_preloads()
        self.assertEqual(1, len(FACTORY.chunk.async_tasks))
        first = FACTORY.chunk.async_tasks[0]
        self.assertEqual(SERVER.config.DIMENSION_ID, first[0])
        self.assertEqual((32, 0, 80), first[1])
        self.assertEqual((47, 255, 95), first[2])

        self.system._process_portal_background_preloads()
        self.assertEqual(1, len(FACTORY.chunk.async_tasks))

        first[3](True)
        self.system._process_portal_background_preloads()
        self.assertEqual(2, len(FACTORY.chunk.async_tasks))
        self.assertEqual(
            1,
            self.system._worldgen_perf_counters[
                "backgroundPreloadCompleted"
            ],
        )

    def test_finished_arrival_queues_prewarm_without_extending_player_hold(self):
        self._queue_and_start_loading()
        self._finish_bootstrap_arrival()
        FACTORY.block.terrain_ready = True
        FACTORY.block.writable = True

        self._advance_to_ready_tick()

        self.assertNotIn("player", self.system._pending_portal_entries)
        self.assertEqual(0.0, FACTORY.gravity.value)
        self.assertEqual(72, len(self.system._portal_background_preload_queue))
        self.assertEqual([], FACTORY.chunk.async_tasks)
        summaries = [
            fields
            for event, fields in self.entry_events
            if event == "entry.worldgen.summary"
        ]
        self.assertEqual(1, len(summaries))
        self.assertIn("totalMs", summaries[0])
        self.assertIn("counters", summaries[0])

    def test_worldgen_callbacks_record_stage_counts_and_landmark_dispatch(self):
        target = {"dimensionId": SERVER.config.DIMENSION_ID}
        self.system._ruin_worldgen = None
        self.system._mushroom_worldgen = None
        self.system._enchanted_tree_worldgen = None

        self.system.OnChunkGeneratedServerEvent(dict(target))
        self.system.OnChunkLoadedServerEvent(dict(target))
        structure = dict(target)
        structure["structureName"] = (
            "tf_slice:ruin_landmark_surface_ordinary"
        )
        self.system.OnPlaceNeteaseStructureFeatureEvent(structure)

        self.assertEqual(
            1,
            self.system._worldgen_perf_counters["chunkGenerated"],
        )
        self.assertEqual(
            1,
            self.system._worldgen_perf_counters["chunkLoaded"],
        )
        self.assertEqual(
            1,
            self.system._worldgen_perf_counters["structureEvents"],
        )
        self.assertEqual(
            1,
            self.system._worldgen_perf_counters[
                "surfaceLandmarkEvents"
            ],
        )
        self.assertEqual(
            1,
            self.system._worldgen_perf_structure_counts[
                "tf_slice:ruin_landmark_surface_ordinary"
            ],
        )

    def test_client_ready_deadline_releases_after_safe_relocation(self):
        self._queue_and_start_loading()
        self._finish_bootstrap_arrival()
        FACTORY.block.terrain_ready = True
        FACTORY.block.writable = True
        self._advance_to_ready_tick(acknowledge_client=False)

        self._ack_engine_ready()

        request = self.system._pending_portal_entries["player"]
        self.system._tick = request["clientReadyDeadlineTick"]
        self.system._process_portal_arrivals()

        request = self.system._pending_portal_entries["player"]
        self.assertEqual("client_loading", request["state"])
        self.assertFalse(request["clientReadyPending"])
        self.assertTrue(request["clientReady"])
        self.assertTrue(request["clientReadyFallback"])
        self.assertEqual(
            SERVER.config.PORTAL_STAGING_GRAVITY,
            FACTORY.gravity.value,
        )
        self.assertEqual([], FACTORY.chunk.deleted)

        self.system._tick = request["clientReadyReleaseTick"]
        self.system._process_portal_arrivals()

        self.assertNotIn("player", self.system._pending_portal_entries)
        self.assertEqual(0.0, FACTORY.gravity.value)
        self.assertEqual([], FACTORY.chunk.deleted)
        self.assertEqual(
            "PortalArrivalFinished",
            self.client_notifications[-1][1],
        )

    def test_fresh_dimension_enters_without_native_forced_area(self):
        """A missing LevelChunk must never be preloaded with SetAddArea."""
        FACTORY.chunk.ready = False
        FACTORY.block.level_chunk_readable = False

        self.system._enter_slice(
            "player",
            sourceSurface=self.SOURCE_SURFACE,
        )
        self.system._tick = 1
        self.system._process_portal_arrivals()

        self.assertEqual([], FACTORY.chunk.checked)
        self.assertEqual([], FACTORY.chunk.added)
        self.assertEqual([], FACTORY.chunk.deleted)
        self.assertEqual(1, len(self.dimension_changes))
        self.assertEqual(
            SERVER.config.DIMENSION_ID,
            self.dimension_changes[0][1],
        )
        self.assertEqual([], FACTORY.block.top_queries)
        self.assertEqual([], FACTORY.block.writes)

    def test_direct_entry_targets_the_final_chunk_on_first_dimension_change(self):
        self._queue_and_start_loading()

        target_position = self.dimension_changes[0][2]
        target_foot = SERVER.portal_logic.player_foot_from_position(
            target_position
        )
        self.assertEqual(self._direct_entry_foot_pos(), target_foot)
        self.assertNotEqual(
            tuple(SERVER.config.WORLDGEN_STAGING_FOOT_POS),
            target_foot,
        )

    def test_entry_guard_is_active_before_native_dimension_change_starts(self):
        self._queue_and_start_loading()

        self.assertIn("player", self.system._dimension_change_in_progress)

    def test_entry_trace_orders_queue_before_native_dimension_change(self):
        self._queue_and_start_loading()

        events = [event for event, _fields in self.entry_events]
        expected = (
            "enter.begin",
            "enter.dimension.call",
            "enter.dimension.result",
            "enter.position.call",
            "enter.position.result",
            "enter.queued",
            "entry.bootstrap.begin",
            "entry.direct.change.call",
            "entry.direct.change.return",
        )
        positions = [events.index(event) for event in expected]
        self.assertEqual(sorted(positions), positions)

    def test_portal_is_built_at_target_ground_after_dimension_finish(self):
        self._queue_and_start_loading()
        self.assertEqual([], FACTORY.block.writes)
        self._finish_bootstrap_arrival()
        FACTORY.block.terrain_ready = True
        FACTORY.block.writable = True

        self._advance_to_ready_tick()

        self.assertEqual(1, len(self.dimension_changes))
        self.assertEqual(
            (
                "player",
                SERVER.config.DIMENSION_ID,
                SERVER.portal_logic.player_position_from_foot(
                    self._direct_entry_foot_pos()
                ),
            ),
            self.dimension_changes[0],
        )
        for position in (
            (35, 65, 62),
            (36, 65, 62),
            (35, 65, 63),
            (36, 65, 63),
        ):
            self.assertEqual(
                "tf_slice:twilight_portal",
                FACTORY.block.blocks[position],
            )
        self.assertNotIn((35, 70, 62), FACTORY.block.blocks)

        self.assertNotIn("player", self.system._pending_portal_entries)
        self.assertEqual([], FACTORY.chunk.added)
        self.assertEqual([], FACTORY.chunk.deleted)
        self.assertTrue(self.system._portal_links)
        self.assertEqual([(34.5, 66.0, 62.5)], FACTORY.positions)
        direct_chunk = (
            int(self._direct_entry_foot_pos()[0]) >> 4,
            int(self._direct_entry_foot_pos()[2]) >> 4,
        )
        exit_chunk = (
            int(FACTORY.positions[0][0]) >> 4,
            int(FACTORY.positions[0][2]) >> 4,
        )
        self.assertEqual(direct_chunk, exit_chunk)
        self.assertEqual(0.0, FACTORY.gravity.value)
        self.assertIn(SERVER.config.PORTAL_STAGING_GRAVITY, FACTORY.gravity.calls)
        self.assertEqual(0.0, FACTORY.gravity.calls[-1])

    def test_direct_entry_player_is_held_until_target_chunks_are_ready(self):
        self._queue_and_start_loading()
        self._finish_bootstrap_arrival()
        FACTORY.chunk.ready = False
        FACTORY.block.terrain_ready = True
        FACTORY.block.writable = True

        request = self.system._pending_portal_entries["player"]
        self.system._tick = request["nextAttemptTick"]
        self.system._process_portal_arrivals()

        self.assertEqual([], FACTORY.positions)
        self.assertIn((0.0, 0.0, 0.0), FACTORY.motions)
        self.assertEqual([], FACTORY.entity_motions)
        self.assertEqual(
            SERVER.config.PORTAL_STAGING_GRAVITY,
            FACTORY.gravity.value,
        )
        self.assertEqual([], FACTORY.chunk.added)
        self.assertEqual(
            "loading",
            self.system._pending_portal_entries["player"]["state"],
        )

        request = self.system._pending_portal_entries["player"]
        FACTORY.chunk.ready = True
        FACTORY.block.level_chunk_readable = False
        self.system._tick = request["nextAttemptTick"]
        self.system._process_portal_arrivals()

        self.assertEqual([], FACTORY.positions)
        self.assertEqual([], FACTORY.block.top_queries)

    def test_dimension_id_change_does_not_finish_before_finish_event(self):
        self._queue_and_start_loading()
        self.assertEqual(SERVER.config.DIMENSION_ID, self.dimension_id)
        self.assertEqual(
            "changing_dimension",
            self.system._pending_portal_entries["player"]["state"],
        )

        self.system._tick += 1
        self.system._process_portal_arrivals()

        self.assertIn("player", self.system._pending_portal_entries)
        self.assertEqual([], FACTORY.positions)
        self.assertEqual([], FACTORY.chunk.deleted)

    def test_failed_portal_write_is_retried_before_relocation(self):
        self._queue_and_start_loading()
        self._finish_bootstrap_arrival()
        FACTORY.block.terrain_ready = True
        FACTORY.block.writable = True
        FACTORY.block.reject_portal = True

        self._advance_to_ready_tick()

        self.assertEqual(1, len(self.dimension_changes))
        self.assertEqual([], FACTORY.positions)
        self.assertIn("player", self.system._pending_portal_entries)

        FACTORY.block.reject_portal = False
        request = self.system._pending_portal_entries["player"]
        self.system._tick = request["nextAttemptTick"]
        self.system._process_portal_arrivals()
        self._ack_client_ready()

        self.assertEqual(1, len(self.dimension_changes))
        portal_origin = tuple(
            self.system._return_points["player"]["portalOrigin"]
        )
        portal_surface = self.system._portal_surface(
            portal_origin,
            SERVER.config.DIMENSION_ID,
        )
        self.assertEqual(
            self.system._portal_exit(
                portal_surface,
                SERVER.config.DIMENSION_ID,
            ),
            FACTORY.positions[0],
        )
        self.assertNotEqual(97.0, FACTORY.positions[0][1])
        self.assertNotIn("player", self.system._pending_portal_entries)

    def test_unready_target_chunks_bootstrap_without_native_writes(self):
        self._queue_and_start_loading()
        self._finish_bootstrap_arrival()
        FACTORY.chunk.ready = False
        FACTORY.block.terrain_ready = True
        FACTORY.block.writable = True

        self._advance_to_ready_tick()

        self.assertTrue(FACTORY.chunk.checked)
        self.assertEqual([], FACTORY.block.writes)
        self.assertEqual(1, len(self.dimension_changes))
        self.assertEqual([], FACTORY.chunk.added)

    def test_unreadable_target_chunks_bootstrap_without_height_query(self):
        self._queue_and_start_loading()
        self._finish_bootstrap_arrival()
        FACTORY.chunk.ready = True
        FACTORY.block.terrain_ready = True
        FACTORY.block.level_chunk_readable = False
        FACTORY.block.writable = True
        top_queries_before = len(FACTORY.block.top_queries)

        self._advance_to_ready_tick()

        self.assertTrue(FACTORY.chunk.checked)
        self.assertEqual(top_queries_before, len(FACTORY.block.top_queries))
        self.assertEqual([], FACTORY.block.writes)
        self.assertEqual(1, len(self.dimension_changes))
        self.assertEqual([], FACTORY.chunk.added)

    def test_unreadable_fresh_dimension_bootstraps_entry_before_timeout(self):
        FACTORY.chunk.ready = True
        FACTORY.block.terrain_ready = True
        FACTORY.block.level_chunk_readable = False
        FACTORY.block.writable = True
        FACTORY.block.top_queries = []
        self._queue_and_start_loading()
        request = self.system._pending_portal_entries["player"]

        self.assertIn("bootstrapAtTick", request)
        self.assertEqual([], FACTORY.chunk.checked)
        self.assertEqual([], FACTORY.block.top_queries)
        self.assertEqual([], FACTORY.block.writes)
        self.assertEqual(1, len(self.dimension_changes))
        self.assertEqual(
            SERVER.config.DIMENSION_ID,
            self.dimension_changes[0][1],
        )
        self.assertTrue(request["bootstrapEntry"])
        self.assertEqual("changing_dimension", request["state"])

    def test_bootstrap_arrival_builds_return_portal_after_dimension_finish(self):
        self._queue_and_start_loading()
        FACTORY.chunk.ready = True
        FACTORY.block.terrain_ready = True
        FACTORY.block.level_chunk_readable = False
        FACTORY.block.writable = True
        FACTORY.block.top_queries = []
        self._finish_bootstrap_arrival()

        request = self.system._pending_portal_entries["player"]
        self.assertTrue(request["recovery"])
        self.assertTrue(request["directEntry"])
        self.assertEqual("loading", request["state"])
        self.assertEqual([], FACTORY.block.top_queries)
        self.assertEqual([], FACTORY.block.writes)

        self.system._tick = request["nextAttemptTick"]
        self.system._process_portal_arrivals()
        FACTORY.block.level_chunk_readable = True
        request = self.system._pending_portal_entries["player"]
        self.system._tick = request["nextAttemptTick"]
        self.system._process_portal_arrivals()
        self._ack_client_ready()

        self.assertNotIn("player", self.system._pending_portal_entries)
        self.assertTrue(self.system._portal_links)
        self.assertEqual([(34.5, 66.0, 62.5)], FACTORY.positions)
        self.assertEqual([], FACTORY.chunk.added)
        self.assertEqual([], FACTORY.chunk.deleted)

    def test_missing_chunk_state_checker_never_reaches_height_query(self):
        self._queue_and_start_loading()
        self._finish_bootstrap_arrival()
        FACTORY.chunk.CheckChunkState = None
        FACTORY.block.terrain_ready = True
        FACTORY.block.writable = True
        FACTORY.block.top_queries = []

        self._advance_to_ready_tick()

        self.assertEqual([], FACTORY.block.top_queries)
        self.assertEqual([], FACTORY.block.writes)
        self.assertEqual(1, len(self.dimension_changes))
        self.assertEqual([], FACTORY.chunk.added)

    def test_terrain_timeout_releases_area_without_transporting_player(self):
        self.system._enter_slice(
            "player",
            sourceSurface=self.SOURCE_SURFACE,
        )
        request = self.system._pending_portal_entries["player"]
        self.now_seconds = request["expiresAt"] + 0.001

        self.system._process_portal_arrivals()

        self.assertEqual([], self.dimension_changes)
        self.assertNotIn("player", self.system._pending_portal_entries)
        self.assertEqual([], FACTORY.chunk.deleted)
        self.assertEqual([], FACTORY.motions)

    def test_direct_entry_timeout_restores_gravity_and_returns_to_source(self):
        self._queue_and_start_loading()
        self._finish_bootstrap_arrival()
        request = self.system._pending_portal_entries["player"]
        self.system._tick = request["nextAttemptTick"]
        self.system._process_portal_arrivals()

        self.assertEqual(
            SERVER.config.PORTAL_STAGING_GRAVITY,
            FACTORY.gravity.value,
        )
        request = self.system._pending_portal_entries["player"]
        self.now_seconds = request["expiresAt"] + 0.001
        self.system._process_portal_arrivals()

        self.assertNotIn("player", self.system._pending_portal_entries)
        self.assertEqual(2, len(self.dimension_changes))
        self.assertEqual(0, self.dimension_changes[-1][1])
        self.assertEqual(0.0, FACTORY.gravity.value)
        self.assertEqual([], FACTORY.chunk.deleted)

    def test_fast_update_loop_cannot_expire_before_wall_clock_deadline(self):
        self._queue_and_start_loading()
        request = self.system._pending_portal_entries["player"]
        self.system._tick = request["expires"] + 1

        self.system._process_portal_arrivals()

        self.assertIn("player", self.system._pending_portal_entries)
        self.assertEqual(1, len(self.dimension_changes))
        self.assertEqual([], FACTORY.block.writes)
        self.assertEqual([], FACTORY.chunk.deleted)

        request = self.system._pending_portal_entries["player"]
        self.now_seconds = request["expiresAt"] + 0.001
        self.system._process_portal_arrivals()

        self.assertNotIn("player", self.system._pending_portal_entries)
        self.assertEqual(2, len(self.dimension_changes))
        self.assertEqual(0, self.dimension_changes[-1][1])
        self.assertEqual([], FACTORY.chunk.deleted)

    def test_activation_keeps_lightning_but_removes_only_new_fire(self):
        FACTORY.block.writable = True
        existing_fire = (34, 70, 62)
        FACTORY.block.blocks[existing_fire] = "minecraft:fire"
        self.system._consume_catalyst = types.MethodType(
            lambda _system, *_args: True,
            self.system,
        )

        activated = self.system._activate_portal(
            "diamond",
            {
                "dimensionId": 0,
                "pos": (35.5, 70.0, 62.5),
                "playerId": "player",
            },
            {"newItemName": "minecraft:diamond", "count": 1},
            self.SOURCE_SURFACE,
        )

        self.assertTrue(activated)
        self.assertEqual(1, len(FACTORY.commands))
        self.assertIn("/summon lightning_bolt ", FACTORY.commands[0])
        self.assertEqual(
            "minecraft:fire",
            FACTORY.block.blocks[(35, 71, 62)],
        )

        self.system._process_portal_fire_cleanups()

        self.assertEqual(
            "minecraft:air",
            FACTORY.block.blocks[(35, 71, 62)],
        )
        self.assertEqual(
            "minecraft:air",
            FACTORY.block.blocks[(36, 70, 62)],
        )
        self.assertEqual(
            "minecraft:fire",
            FACTORY.block.blocks[existing_fire],
        )
        FACTORY.block.blocks[(35, 72, 63)] = "minecraft:fire"
        self.system._tick += 1

        self.system._process_portal_fire_cleanups()

        self.assertEqual(
            "minecraft:air",
            FACTORY.block.blocks[(35, 72, 63)],
        )
        self.assertEqual(1, len(self.system._portal_fire_cleanups))

    def test_command_dimension_change_captures_source_and_builds_return_portal(self):
        self.system.OnDimensionChangeServerEvent(
            {
                "playerId": "player",
                "fromDimensionId": 0,
                "toDimensionId": SERVER.config.DIMENSION_ID,
                "fromX": 35.5,
                "fromY": 72.62,
                "fromZ": 62.5,
                "toX": 35.5,
                "toY": 72.62,
                "toZ": 62.5,
            }
        )
        self.assertEqual(
            {
                "dimensionId": 0,
                "pos": (35.5, 71.0, 62.5),
            },
            self.system._return_points["player"],
        )
        self.assertEqual(1, FACTORY.extra.save_count)

        self.dimension_id = SERVER.config.DIMENSION_ID
        self.system.OnDimensionChangeFinish(
            {
                "playerId": "player",
                "fromDimensionId": 0,
                "toDimensionId": SERVER.config.DIMENSION_ID,
                "toPos": (35.5, 72.62, 62.5),
            }
        )

        request = self.system._pending_portal_entries["player"]
        self.assertTrue(request["recovery"])
        self.assertEqual((35, 62), request["destinationXZ"])
        self._finish_recovery_portal()

        self.assertEqual([], self.dimension_changes)
        self.assertEqual([], FACTORY.positions)
        self.assertNotIn("player", self.system._pending_portal_entries)
        self.assertEqual(
            [35, 65, 62],
            self.system._return_points["player"]["portalOrigin"],
        )

    def test_return_uses_player_position_above_saved_foot_point(self):
        self.dimension_id = SERVER.config.DIMENSION_ID

        self.system._return_from_slice(
            "player",
            {
                "dimensionId": 0,
                "pos": (35.5, 71.0, 62.5),
            },
        )

        self.assertEqual(
            [
                (
                    "player",
                    0,
                    (35.5, 72.62, 62.5),
                )
            ],
            self.dimension_changes,
        )

    def test_rejoining_twilight_queues_missing_return_portal(self):
        self.dimension_id = SERVER.config.DIMENSION_ID
        self.system._return_points["player"] = {
            "dimensionId": 0,
            "pos": (35.5, 71.0, 62.5),
        }

        self.system.OnClientReady({"playerId": "player"})

        request = self.system._pending_portal_entries["player"]
        self.assertTrue(request["recovery"])
        self._finish_recovery_portal()
        self.assertEqual([], self.dimension_changes)
        self.assertTrue(self.system._portal_links)

    def test_return_point_and_portal_origin_survive_restart(self):
        point = {
            "dimensionId": 0,
            "pos": (35.5, 71.0, 62.5),
        }

        saved = self.system._store_return_point(
            "player",
            point,
            portal_origin=(35, 65, 62),
        )

        self.assertTrue(saved)
        restarted = object.__new__(SERVER.ServerSystem)
        restarted._portal_extra = FACTORY.extra
        loaded = restarted._load_portal_return_points()
        self.assertEqual(
            {
                "dimensionId": 0,
                "pos": (35.5, 71.0, 62.5),
                "portalOrigin": [35, 65, 62],
            },
            loaded["player"],
        )

    def test_rejoining_with_existing_portal_restores_link_without_rebuilding(self):
        self.dimension_id = SERVER.config.DIMENSION_ID
        FACTORY.block.writable = True
        origin = (35, 65, 62)
        self.assertTrue(
            self.system._make_return_portal(
                origin,
                SERVER.config.DIMENSION_ID,
            )
        )
        self.system._return_points["player"] = {
            "dimensionId": 0,
            "pos": (35.5, 71.0, 62.5),
            "portalOrigin": [35, 65, 62],
        }
        writes_before_join = len(FACTORY.block.writes)

        self.system.OnClientReady({"playerId": "player"})

        self.assertNotIn("player", self.system._pending_portal_entries)
        self.assertEqual(writes_before_join, len(FACTORY.block.writes))
        self.assertTrue(self.system._portal_links)

    def test_existing_return_portal_repairs_blocked_body_space(self):
        FACTORY.block.writable = True
        origin = (35, 65, 62)
        self.assertTrue(
            self.system._make_return_portal(
                origin,
                SERVER.config.DIMENSION_ID,
            )
        )
        surface = self.system._portal_surface(
            origin,
            SERVER.config.DIMENSION_ID,
        )
        edge_cells = set()
        for pos in surface:
            for dx, dz in SERVER.portal_logic.HORIZONTAL:
                edge = (pos[0] + dx, pos[1], pos[2] + dz)
                if edge not in surface:
                    edge_cells.add(edge)
        for edge in edge_cells:
            FACTORY.block.blocks[
                (edge[0], edge[1] + 1, edge[2])
            ] = "minecraft:dirt"
            FACTORY.block.blocks[
                (edge[0], edge[1] + 2, edge[2])
            ] = "minecraft:dirt"

        self.assertTrue(
            self.system._make_return_portal(
                origin,
                SERVER.config.DIMENSION_ID,
            )
        )
        exit_pos = self.system._portal_exit(
            surface,
            SERVER.config.DIMENSION_ID,
        )

        self.assertIsNotNone(exit_pos)
        block_x = int(exit_pos[0] - 0.5)
        block_y = int(exit_pos[1])
        block_z = int(exit_pos[2] - 0.5)
        self.assertNotEqual(
            "minecraft:dirt",
            FACTORY.block.blocks.get((block_x, block_y, block_z)),
        )
        self.assertNotEqual(
            "minecraft:dirt",
            FACTORY.block.blocks.get((block_x, block_y + 1, block_z)),
        )

    def test_rejoining_repairs_a_blocked_existing_portal_exit(self):
        self.dimension_id = SERVER.config.DIMENSION_ID
        FACTORY.block.writable = True
        origin = (35, 65, 62)
        self.assertTrue(
            self.system._make_return_portal(
                origin,
                SERVER.config.DIMENSION_ID,
            )
        )
        surface = self.system._portal_surface(
            origin,
            SERVER.config.DIMENSION_ID,
        )
        for pos in surface:
            for dx, dz in SERVER.portal_logic.HORIZONTAL:
                edge = (pos[0] + dx, pos[1], pos[2] + dz)
                if edge in surface:
                    continue
                FACTORY.block.blocks[
                    (edge[0], edge[1] + 1, edge[2])
                ] = "minecraft:dirt"
                FACTORY.block.blocks[
                    (edge[0], edge[1] + 2, edge[2])
                ] = "minecraft:dirt"
        self.system._return_points["player"] = {
            "dimensionId": 0,
            "pos": (35.5, 71.0, 62.5),
            "portalOrigin": list(origin),
        }

        self.system.OnClientReady({"playerId": "player"})

        self.assertIsNotNone(
            self.system._portal_exit(
                surface,
                SERVER.config.DIMENSION_ID,
            )
        )
        self.assertNotIn("player", self.system._pending_portal_entries)

    def _finish_recovery_portal(self):
        self.system._tick = 1
        self.system._process_portal_arrivals()
        FACTORY.block.terrain_ready = True
        FACTORY.block.writable = True
        request = self.system._pending_portal_entries["player"]
        self.system._tick = request["nextAttemptTick"]
        self.system._process_portal_arrivals()


class UrGhastRuntimeGuardTests(unittest.TestCase):
    def test_fireball_health_contact_reflects_and_restores_safe_health(self):
        system = object.__new__(SERVER.ServerSystem)
        system._tick = 20
        system._entry_diagnostics = None
        system._ur_ghast_projectiles = {
            "shot": {
                "bossId": "boss",
                "ownerId": "boss",
                "reflected": False,
            }
        }
        reflected = []
        health_writes = []
        system._is_online_player = types.MethodType(
            lambda _system, entity_id: entity_id == "player", system
        )
        system._reflect_ur_ghast_fireball = types.MethodType(
            lambda _system, projectile_id, player_id, reason="": reflected.append(
                (projectile_id, player_id, reason)
            ) or True,
            system,
        )
        system._set_health = types.MethodType(
            lambda _system, entity_id, value: health_writes.append(
                (entity_id, value)
            ) or True,
            system,
        )
        args = {
            "from": 32.0,
            "to": 24.0,
            "sourceId": "player",
        }

        self.assertTrue(
            system._protect_ur_ghast_fireball_health(args, "shot")
        )

        self.assertTrue(args["cancel"])
        self.assertEqual(
            [("shot", "player", "health_change")], reflected
        )
        self.assertEqual(
            [("shot", SERVER.ur_ghast_logic.FIREBALL_HEALTH)],
            health_writes,
        )

    def test_fireball_health_contact_recovers_missing_player_source(self):
        system = object.__new__(SERVER.ServerSystem)
        system._tick = 21
        system._entry_diagnostics = None
        system._ur_ghast_projectiles = {
            "shot": {
                "bossId": "boss",
                "ownerId": "boss",
                "reflected": False,
            }
        }
        reflected = []
        system._is_online_player = types.MethodType(
            lambda _system, entity_id: entity_id == "player", system
        )
        system._recover_ur_ghast_fireball_reflector = types.MethodType(
            lambda _system, projectile_id: "player", system
        )
        system._reflect_ur_ghast_fireball = types.MethodType(
            lambda _system, projectile_id, player_id, reason="": reflected.append(
                (projectile_id, player_id, reason)
            ) or True,
            system,
        )
        system._set_health = types.MethodType(
            lambda _system, entity_id, value: True,
            system,
        )
        args = {"from": 32.0, "to": 24.0}

        self.assertTrue(
            system._protect_ur_ghast_fireball_health(args, "shot")
        )
        self.assertTrue(args["cancel"])
        self.assertEqual(
            [("shot", "player", "health_change_recovered")],
            reflected,
        )

    def _drivable_ur_ghast(self, active_trap=None):
        system = object.__new__(SERVER.ServerSystem)
        state = SERVER.ur_ghast_logic.create_state(
            (0.0, 200.0, 0.0),
            ((20.0, 180.0, 0.0),),
            home_bound=True,
        )
        state["engineEntityId"] = "boss"
        state["dimensionId"] = 33027004
        state["nextFlightTraceTick"] = 99999
        state["nextYawTraceTick"] = 99999
        system._ur_ghasts = {"boss": state}
        system._ur_ghast_logic_tick = 1
        system._tick = 1
        system._entry_diagnostics = None
        system._boss_sync_dirty = False
        system._get_foot_pos = types.MethodType(
            lambda _system, entity_id: {
                "boss": (0.5, 200.0, 0.5),
                "player": (10.0, 190.0, 0.5),
            }.get(entity_id),
            system,
        )
        system._get_rotation = types.MethodType(
            lambda _system, _entity_id: (0.0, 0.0), system
        )
        system._reconcile_ur_ghast_engine_health = types.MethodType(
            lambda *_args: None, system
        )
        system._tick_ur_ghast_hurt_feedback = types.MethodType(
            lambda *_args: None, system
        )
        system._separate_players_from_ur_ghast_head = types.MethodType(
            lambda *_args: None, system
        )
        system._tick_ur_ghast_trap_route = types.MethodType(
            lambda *_args: False, system
        )
        system._ur_ghast_absorb_nearby_minions = types.MethodType(
            lambda *_args: 0, system
        )
        system._active_ghast_trap = types.MethodType(
            lambda *_args: active_trap, system
        )
        system._ur_ghast_target = types.MethodType(
            lambda *_args: ("player", (10.0, 190.0, 0.5)), system
        )
        system._ur_ghast_can_see = types.MethodType(
            lambda *_args: True, system
        )
        system._ur_ghast_traps_have_minions = types.MethodType(
            lambda *_args: True, system
        )
        system._reset_attack_target = types.MethodType(
            lambda *_args: True, system
        )
        system._trigger_entity_event = types.MethodType(
            lambda *_args: True, system
        )
        system._set_entity_property = types.MethodType(
            lambda *_args: True, system
        )
        system._save_ur_ghast_state = types.MethodType(
            lambda *_args: True, system
        )
        system._set_ur_ghast_engine_health = types.MethodType(
            lambda *_args: True, system
        )
        return system, state

    def test_attack_visual_delivery_cannot_raise_trace_keyword_collision(self):
        system = object.__new__(SERVER.ServerSystem)
        system._entry_diagnostics = None
        property_writes = []
        system._trigger_entity_event = types.MethodType(
            lambda *_args: True, system
        )
        system._set_entity_property = types.MethodType(
            lambda _system, entity_id, name, value: property_writes.append(
                (entity_id, name, value)
            ) or True,
            system,
        )
        state = {
            "visualAttackApplied": -1.0,
            "attackTimer": 15,
        }

        self.assertTrue(system._sync_ur_ghast_visual("boss", state, 2.0))

        self.assertEqual(2.0, state["visualAttackApplied"])
        self.assertIn(("boss", "tf_slice:attack_state", 2.0), property_writes)
        self.assertIn(("boss", "tf_slice:attack_timer", 15.0), property_writes)

    def test_normal_source_ticks_face_target_and_reach_one_volley(self):
        system, state = self._drivable_ur_ghast()
        yaw_reasons = []
        volleys = []
        system._set_ur_ghast_logical_yaw = types.MethodType(
            lambda _system, _boss_id, _state, _yaw, reason: yaw_reasons.append(
                reason
            ) or True,
            system,
        )
        system._sync_ur_ghast_visual_pitch = types.MethodType(
            lambda *_args: True, system
        )
        system._play_world_sound = types.MethodType(
            lambda *_args: True, system
        )
        system._spawn_ur_ghast_volley = types.MethodType(
            lambda _system, *args, **kwargs: volleys.append((args, kwargs)),
            system,
        )

        for logic_tick in range(1, 21):
            system._ur_ghast_logic_tick = logic_tick
            system._tick = logic_tick
            system._drive_ur_ghasts()

        self.assertEqual(1, len(volleys))
        self.assertIn("attack_target", yaw_reasons)
        self.assertEqual(-40, state["attackTimer"])
        self.assertEqual(20, state["visualAttackTimer"])

    def test_active_trap_commits_pull_and_exits_tantrum(self):
        trap = SERVER.ur_ghast_logic.create_trap_state((0.0, 180.0, 0.0))
        trap["active"] = True
        trap["activeTicks"] = 1
        system, state = self._drivable_ur_ghast(trap)
        state["phase"] = "tantrum"
        pitch_values = []
        effect_targets = []
        system._sync_ur_ghast_visual_pitch = types.MethodType(
            lambda _system, _boss_id, _state, value, _reason: pitch_values.append(
                value
            ) or True,
            system,
        )
        system._record_ghast_trap_effect_target = types.MethodType(
            lambda _system, _trap, position: effect_targets.append(position)
            or True,
            system,
        )
        system._broadcast_ur_ghast_effect = types.MethodType(
            lambda *_args: True, system
        )
        system._set_ur_ghast_logical_yaw = types.MethodType(
            lambda *_args: True, system
        )

        system._drive_ur_ghasts()

        self.assertEqual("normal", state["phase"])
        self.assertEqual("trap", state["motionOwner"])
        self.assertLess(state["requestedEngineMotion"][1], 0.0)
        self.assertEqual([90.0], pitch_values)
        self.assertEqual(1, len(effect_targets))

    def test_duplicate_registration_keeps_live_ai_state(self):
        system = object.__new__(SERVER.ServerSystem)
        live = SERVER.ur_ghast_logic.create_state(
            (0.0, 200.0, 0.0),
            ((20.0, 180.0, 0.0),),
            home_bound=True,
        )
        live["wantedWaypoint"] = [20.0, 200.0, 0.0]
        live["requestedEngineMotion"] = [0.2, 0.0, 0.0]
        live["attackTimer"] = 13
        system._ur_ghasts = {"boss": live}

        result = system._register_ur_ghast("boss", 33027004)

        self.assertIs(live, result)
        self.assertEqual([20.0, 200.0, 0.0], result["wantedWaypoint"])
        self.assertEqual([0.2, 0.0, 0.0], result["requestedEngineMotion"])
        self.assertEqual(13, result["attackTimer"])

    def test_route_motion_commits_before_combat_component_failure(self):
        system = object.__new__(SERVER.ServerSystem)
        state = SERVER.ur_ghast_logic.create_state(
            (0.0, 200.0, 0.0),
            ((20.0, 180.0, 0.0),),
            home_bound=True,
        )
        state["engineEntityId"] = "boss"
        state["dimensionId"] = 33027004
        state["nextFlightTraceTick"] = 999
        system._ur_ghasts = {"boss": state}
        system._ur_ghast_logic_tick = 1
        system._tick = 1
        system._get_foot_pos = types.MethodType(
            lambda _system, entity_id: {
                "boss": (0.0, 200.0, 0.0),
                "player": (10.0, 200.0, 0.0),
            }.get(entity_id),
            system,
        )
        system._get_rotation = types.MethodType(
            lambda _system, _entity_id: (0.0, 0.0), system
        )
        system._reconcile_ur_ghast_engine_health = types.MethodType(
            lambda *_args: None, system
        )
        system._tick_ur_ghast_hurt_feedback = types.MethodType(
            lambda *_args: None, system
        )
        system._tick_ur_ghast_trap_route = types.MethodType(
            lambda *_args: False, system
        )
        system._ur_ghast_absorb_nearby_minions = types.MethodType(
            lambda *_args: None, system
        )
        system._active_ghast_trap = types.MethodType(
            lambda *_args: None, system
        )
        system._ur_ghast_target = types.MethodType(
            lambda *_args: ("player", (10.0, 200.0, 0.0)), system
        )
        system._ur_ghast_traps_have_minions = types.MethodType(
            lambda *_args: True, system
        )
        system._set_ur_ghast_logical_yaw = types.MethodType(
            lambda *_args: True, system
        )
        system._entry_trace = types.MethodType(
            lambda *_args, **_kwargs: True, system
        )
        system._ur_ghast_can_see = types.MethodType(
            lambda *_args: (_ for _ in ()).throw(RuntimeError("perception")),
            system,
        )

        with self.assertRaisesRegex(RuntimeError, "perception"):
            system._drive_ur_ghasts()

        self.assertEqual([20.0, 200.0, 0.0], state["wantedWaypoint"])
        self.assertEqual("flight", state["motionOwner"])
        self.assertGreater(
            sum(abs(value) for value in state["requestedEngineMotion"]),
            0.0,
        )

    def test_minus_one_native_attack_target_becomes_none(self):
        class FakeAction(object):
            def GetAttackTarget(self):
                return -1

        system = object.__new__(SERVER.ServerSystem)
        previous = getattr(FACTORY, "CreateAction", None)
        FACTORY.CreateAction = lambda _entity_id: FakeAction()
        try:
            self.assertIsNone(system._get_attack_target("mini-ghast"))
        finally:
            if previous is None:
                delattr(FACTORY, "CreateAction")
            else:
                FACTORY.CreateAction = previous


if __name__ == "__main__":
    unittest.main()
