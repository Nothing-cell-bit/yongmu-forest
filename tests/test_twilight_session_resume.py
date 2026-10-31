"""Exercise session persistence through real server event handlers."""
import copy
import ast
from pathlib import Path
import types

import pytest

from tests import test_portal_arrival_runtime as portal

FACTORY, SERVER = portal.FACTORY, portal.SERVER


KEY = "tf_slice:twilight_sessions_v1"
SAVED = (-1234.25, 67.5, 918.75)


@pytest.fixture
def scene():
    case = portal.PortalArrivalRuntimeTests()
    case.setUp()
    return case


def stop_loading(scene):
    scene.system.OnTwilightSessionReady({"__id__": "player"})


def seed(scene, position=SAVED):
    FACTORY.extra.values[KEY] = {"player": {"pos": list(position) if position is not None else None}}


def tick(scene, count=1):
    for _ in range(count):
        scene.system._tick += 1
        scene.system._get_twilight_session().tick()


def test_saved_session_waits_for_native_stop_loading_then_uses_exact_position(scene):
    seed(scene)
    scene.system._return_points["player"] = {"dimensionId": 0, "pos": (35, 71, 62)}
    original_return = copy.deepcopy(scene.system._return_points)
    scene.system.OnClientReady({"playerId": "player"})
    tick(scene, 110)
    assert scene.dimension_changes == []
    stop_loading(scene)
    assert scene.dimension_changes == [(
        "player", SERVER.config.DIMENSION_ID, (-1234.25, 69.12, 918.75))]
    # The ordinary dimension-start handler must not capture login's overworld
    # fallback as the new portal source.
    scene.system.OnDimensionChangeServerEvent({
        "playerId": "player", "fromDimensionId": 0,
        "toDimensionId": SERVER.config.DIMENSION_ID,
        "fromX": 9, "fromY": 80, "fromZ": 10,
    })
    assert scene.system._return_points == original_return
    scene.system.OnDimensionChangeFinish({
        "playerId": "player", "fromDimensionId": 0,
        "toDimensionId": SERVER.config.DIMENSION_ID,
        "toPos": (-1234.25, 69.12, 918.75),
    })
    assert scene.system._pending_portal_entries == {}
    assert FACTORY.positions == []
    assert FACTORY.block.writes == []
    assert FACTORY.chunk.checked == []
    packets = [p for _, e, p in scene.client_notifications if e == "PortalArrivalPrepared"]
    assert packets[-1]["position"] == SAVED
    scene.system.OnPortalArrivalEngineReady({"__id__": "other", "token": packets[-1]["token"]})
    scene.system.OnPortalArrivalEngineReady({"__id__": "player", "token": "stale"})
    assert not any(e == "PortalArrivalFinished" for _, e, _ in scene.client_notifications)
    scene.system.OnPortalArrivalEngineReady({"__id__": "player", "token": packets[-1]["token"]})
    assert any(e == "PortalArrivalFinished" for _, e, _ in scene.client_notifications)
    assert scene.system._return_points == original_return
    stop_loading(scene)
    assert len(scene.dimension_changes) == 1


def test_tick_and_leave_save_latest_position_without_teardown_queries(scene):
    scene.dimension_id = SERVER.config.DIMENSION_ID
    stop_loading(scene)
    scene.system._get_foot_pos = lambda _: SAVED
    tick(scene, 100)
    assert FACTORY.extra.values[KEY]["player"]["pos"] == list(SAVED)
    latest = (-1236.75, 21.25, -10.5)
    scene.system._get_foot_pos = lambda _: latest
    tick(scene)
    scene.system._get_foot_pos = lambda _: pytest.fail("position queried after player removal")
    scene.system.OnTwilightPlayerLeave({"id": "player"})
    assert FACTORY.extra.values[KEY]["player"]["pos"] == list(latest)
    # A new Python system reads the persisted state, with no cached manager.
    del scene.system._twilight_session
    scene.dimension_id = 0
    stop_loading(scene)
    assert scene.dimension_changes[-1][2] == (-1236.75, 22.87, -10.5)


def test_normal_return_clears_resume_marker(scene):
    seed(scene)
    scene.dimension_id = SERVER.config.DIMENSION_ID
    stop_loading(scene)
    scene.system.OnDimensionChangeServerEvent({
        "playerId": "player", "fromDimensionId": SERVER.config.DIMENSION_ID,
        "toDimensionId": 0,
    })
    assert "player" not in FACTORY.extra.values[KEY]
    scene.system.OnTwilightPlayerLeave({"id": "player"})
    del scene.system._twilight_session
    scene.dimension_id = 0
    stop_loading(scene)
    assert scene.dimension_changes == []


def test_already_in_twilight_is_neither_relocated_nor_given_a_new_portal(scene):
    seed(scene)
    scene.dimension_id = SERVER.config.DIMENSION_ID
    scene.system.OnClientReady({"playerId": "player"})
    stop_loading(scene)
    assert scene.dimension_changes == []
    assert scene.system._pending_portal_entries == {}
    assert FACTORY.block.writes == []


@pytest.mark.parametrize("position", [None, [1, 2], [float("nan"), 64, 1], [0, float("inf"), 1], ["bad", 1, 2]])
def test_corrupt_persisted_position_cannot_teleport(scene, position):
    seed(scene, position=position)
    stop_loading(scene)
    assert scene.dimension_changes == []


def test_failed_native_change_is_bounded_and_keeps_saved_record(scene):
    seed(scene)
    calls = []
    scene.system._change_dimension = lambda *args: calls.append(args) or False
    stop_loading(scene)
    stop_loading(scene)
    tick(scene, 3000)
    assert len(calls) == 1
    assert FACTORY.extra.values[KEY]["player"]["pos"] == list(SAVED)


def test_missing_native_finish_times_out_without_setpos_or_another_change(scene):
    seed(scene)
    stop_loading(scene)
    scene.now_seconds += 121
    tick(scene)
    assert len(scene.dimension_changes) == 1
    assert FACTORY.positions == []
    assert any(e == "PortalArrivalFinished" and p.get("cancelled")
               for _, e, p in scene.client_notifications)
    assert FACTORY.extra.values[KEY]["player"]["pos"] == list(SAVED)


def test_death_clears_marker_before_inventory_early_return(scene):
    seed(scene)
    scene.dimension_id = SERVER.config.DIMENSION_ID
    stop_loading(scene)
    scene.system._clear_player_fortification = lambda _: None
    scene.system._keep_inventory_rule = lambda: True
    scene.system.OnRoutePlayerDie({"id": "player"})
    tick(scene, 110)
    assert "player" not in FACTORY.extra.values[KEY]


def test_player_identity_comes_from_transport_and_no_position_from_client(scene):
    seed(scene)
    scene.system.OnTwilightSessionReady({"playerId": "player", "pos": (0, 999, 0)})
    assert scene.dimension_changes == []
    scene.system.OnTwilightSessionReady({"__id__": "player", "pos": (0, 999, 0)})
    assert scene.dimension_changes[0][2] == (-1234.25, 69.12, 918.75)


def test_portal_contact_during_login_cannot_send_player_back(scene):
    seed(scene)
    scene.dimension_id = SERVER.config.DIMENSION_ID
    scene.system.OnClientReady({"playerId": "player"})
    # Contact before the native stop-loading handshake must not even query a
    # portal surface. After starting a resume it remains blocked beyond the
    # ordinary 100-tick cooldown.
    scene.system._portal_surface = lambda *args: pytest.fail("portal activated during login")
    contact = {"entityId": "player", "blockName": SERVER.config.PORTAL_IDENTIFIER}
    scene.system.OnEntityInsideBlock(contact)
    scene.dimension_id = 0
    stop_loading(scene)
    scene.system._tick = 101
    scene.system.OnEntityInsideBlock(contact)


def test_save_rejection_remains_dirty_and_is_retried(scene):
    scene.dimension_id = SERVER.config.DIMENSION_ID
    stop_loading(scene)
    original = FACTORY.extra.SetExtraData
    FACTORY.extra.SetExtraData = lambda *args: False
    tick(scene, 100)
    session = scene.system._get_twilight_session()
    assert session.dirty
    FACTORY.extra.SetExtraData = original
    tick(scene, 100)
    assert not session.dirty
    assert FACTORY.extra.values[KEY]["player"]["pos"] == [35.5, 71, 62.5]


def test_load_error_never_overwrites_unread_records(scene):
    seed(scene)
    saved = copy.deepcopy(FACTORY.extra.values)
    FACTORY.extra.GetExtraData = lambda _: (_ for _ in ()).throw(RuntimeError("unavailable"))
    scene.dimension_id = SERVER.config.DIMENSION_ID
    stop_loading(scene)
    tick(scene, 200)
    scene.system.OnTwilightPlayerLeave({"id": "player"})
    assert FACTORY.extra.values == saved


def test_multi_player_checkpoints_and_death_are_independent(scene):
    seed(scene)
    FACTORY.extra.values[KEY]["other"] = {"pos": [10, 70, -20]}
    scene.system.OnTwilightSessionReady({"__id__": "player"})
    scene.system.OnTwilightSessionReady({"__id__": "other"})
    assert [entry[0] for entry in scene.dimension_changes] == ["player"]
    # Other is already in the target dimension according to the engine boundary
    # fixture; it must keep its own checkpoint, without another native change.
    scene.system._get_twilight_session().died("player")
    assert "player" not in FACTORY.extra.values[KEY]
    assert "other" in FACTORY.extra.values[KEY]


def test_destroy_flushes_cached_position_without_reading_removed_actor(scene):
    scene.dimension_id = SERVER.config.DIMENSION_ID
    stop_loading(scene)
    scene.system._get_foot_pos = lambda _: SAVED
    tick(scene)
    scene.system._get_foot_pos = lambda _: pytest.fail("destroy queried an actor")
    # Empty unrelated subsystems still run their real shutdown/persistence
    # methods; only native weather calls are replaced at the SDK boundary.
    host = scene.system
    host._configure_twilight_weather = lambda: None
    host._magic_map_dirty = False
    host._leaf_decay_state_dirty = False
    host._maze_map_records = {}
    host._magic_map_extra = FACTORY.extra
    host._progress_extra = FACTORY.extra
    host._maze_map_dirty = False
    host._player_progress = {}
    host._keeping_snapshots = {}
    host._hydras = {}
    host._route_mobs = {}
    host._bosses = {}
    for name in ("_ruin_worldgen", "_mushroom_worldgen", "_lily_pad_worldgen", "_enchanted_tree_worldgen"):
        setattr(host, name, None)
    host.Destroy()
    assert FACTORY.extra.values[KEY]["player"]["pos"] == list(SAVED)


def test_real_client_stop_loading_handler_sends_no_client_coordinates():
    from lib2to3.refactor import RefactoringTool
    source = (Path(SERVER.__file__).parent / "clientSystem.py").read_text("utf-8")
    converted = str(RefactoringTool(["lib2to3.fixes.fix_print"]).refactor_string(source, "client"))
    tree = ast.parse(converted)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ClientSystem")
    selected = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name in ("OnTwilightSessionStopLoading", "_is_local_dimension_event")]
    namespace = {"clientApi": types.SimpleNamespace(GetLocalPlayerId=lambda: "player")}
    for method in selected:
        exec(compile(ast.Module(body=[method], type_ignores=[]), "client", "exec"), namespace)
    host = types.SimpleNamespace()
    for method in selected:
        setattr(host, method.name, types.MethodType(namespace[method.name], host))
    sent = []
    host.NotifyToServer = lambda *args: sent.append(args)
    host.OnTwilightSessionStopLoading({"playerId": "other"})
    assert sent == []
    host.OnTwilightSessionStopLoading({"playerId": "player"})
    assert sent == [("TwilightSessionReady", {})]
    # Guard wiring as well as executing the event body.
    constructor = ast.unparse(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"))
    assert "'OnLocalPlayerStopLoading', self, self.OnTwilightSessionStopLoading" in constructor
