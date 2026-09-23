"""Maze snapshots must work through the real shared map renderer."""
import json
import re
import sys
import types
import copy
from lib2to3.refactor import RefactoringTool
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "TwilightBossSliceB"))
from TwilightBossSlice import maze_map_logic as maze
from TwilightBossSlice import magic_map_bitmap_cache as bitmap
from TwilightBossSlice import magic_map_logic as magic
from TwilightBossSlice import clientItemLogic as items
from test_magic_map_ui_renderer import load_ui_module


def load_methods(filename, names, namespace):
    source = (ROOT / "TwilightBossSliceB/TwilightBossSlice" / filename).read_text(encoding="utf-8")
    methods = []
    for name in names:
        match = re.search(r"^    (?:@staticmethod\n    )?def " + name + r"\(", source, re.M)
        assert match, name
        end = re.search(r"^    (?:def |@)", source[match.end():], re.M)
        methods.append(source[match.start():match.end() + end.start() if end else len(source)])
    payload = str(RefactoringTool(["lib2to3.fixes.fix_print"]).refactor_string(
        "class UnderTest:\n" + "".join(methods), filename))
    exec(payload, namespace)
    return namespace["UnderTest"]


def server_class(names):
    config = types.SimpleNamespace(
        DIMENSION_ID=7, MAZE_MAP_RECORDS_KEY="maze-records", MAZE_MAP_ITEM="tf_slice:maze_map",
        FILLED_MAZE_MAP_ITEM="tf_slice:filled_maze_map", FILLED_MAGIC_MAP_ITEM="tf_slice:filled_magic_map",
        LEGACY_NATIVE_MAGIC_MAP_ITEM="minecraft:filled_map",
    )
    return load_methods("serverSystem.py", names, {
        "config": config, "maze_map_logic": maze, "magic_map_logic": magic, "copy": copy,
        "portal_logic": types.SimpleNamespace(item_name=items.item_name),
    })


def record(y=8):
    result = maze.create_record("labyrinth:check", (55, y, 55), y)
    result["dimensionId"] = 7
    return result


def snapshot(y=8):
    return maze.build_snapshot(record(y), [[64, 64, 65]], (0, 0), (55, y, 55))


def test_maze_snapshot_renders_and_cache_isolates_floors_and_magic(tmp_path):
    cache = bitmap.MagicMapBitmapCache(str(tmp_path))
    first, second = snapshot(), snapshot(1)
    cells = {0: "unknown", 1: "clearing"}
    paths = [cache.render(s.get("mapId"), cells) for s in (first, second)]
    paths.append(cache.render(1, cells))
    assert all(paths), "Maze snapshot identity must be accepted by the bitmap cache"
    assert len(set(paths)) == 3
    with Image.open(paths[0]) as image:
        assert image.getpixel((0, 0)) == (67, 61, 53, 255)
        assert image.getpixel((1, 0)) == (220, 207, 168, 255)
        assert image.getpixel((2, 0))[3] == 0
    with Image.open(paths[2]) as image:
        assert image.getpixel((0, 0)) == bitmap.MAGIC_MAP_BIOME_RGBA["unknown"]


def test_filled_maze_map_participates_in_held_state_and_switching():
    item = {"itemName": "tf_slice:filled_maze_map", "extraId": maze.encode_identity("a", 0, 8, 0)}
    assert items.is_filled_magic_map(item)
    assert items.resolve_held_map_state(False, [item], True)
    assert not items.is_filled_magic_map({"itemName": "tf_slice:maze_map"})
    state = magic.held_map_transition((True, 1), True, item["extraId"])
    assert state["snapshotNeeded"]
    assert not magic.held_map_transition(state["state"], True, item["extraId"])["snapshotNeeded"]


def test_local_height_refreshes_floor_without_another_server_packet(monkeypatch):
    ui = load_ui_module()
    renderer = object.__new__(ui.MagicMapUI)
    renderer._snapshot = snapshot()
    renderer._live_tick = 2
    renderer._bitmap_pending_slot = None
    renderer._bitmap_dirty = False
    renderer._player_control = None
    factory = types.SimpleNamespace(
        CreatePos=lambda _: types.SimpleNamespace(GetFootPos=lambda: (55, 1, 55)),
        CreateRot=lambda _: types.SimpleNamespace(GetRot=lambda: None),
    )
    monkeypatch.setattr(ui, "CF", factory)
    monkeypatch.setattr(ui.clientApi, "GetLocalPlayerId", lambda: "player", raising=False)
    renderer.Update()
    assert renderer._snapshot["verticalMarker"] == "down"
    assert renderer._snapshot["verticalOffset"] == -7


def test_new_map_starts_unexplored_and_scans_live_blocks_with_a_budget():
    data = record()
    assert not maze.build_snapshot(data, [[64, 64, 65]], (0, 0), (55, 8, 55))["biomeRuns"]
    calls = []
    def block(pos):
        calls.append(pos)
        return {"name": "minecraft:air"}
    assert maze.explore(data, (55, 8, 55), block, budget=4)
    assert len(calls) <= 8
    assert 0 < len(data["exploredCells"]) <= 4
    saved = dict(data["exploredCells"])
    calls[:] = []
    assert not maze.explore(data, (55, 1, 55), block, budget=4)
    assert not calls and saved == data["exploredCells"]


def test_live_scan_revisits_block_changes_and_skips_unloaded_blocks():
    data = record()
    assert maze.explore(data, (55, 8, 55), lambda _: {"name": "minecraft:air"}, budget=1000)
    assert maze.explore(data, (55, 8, 55), lambda _: {"name": "tf_slice:mazestone"}, budget=1000)
    assert set(data["exploredCells"].values()) == {"unknown"}
    saved = dict(data["exploredCells"])
    assert not maze.explore(data, (55, 8, 55), lambda _: None, budget=1000)
    assert saved == data["exploredCells"]


def test_snapshot_replaces_changed_pixels_in_shared_full_screen():
    ui = load_ui_module()
    renderer = object.__new__(ui.MagicMapUI)
    renderer._snapshot = dict(snapshot(), biomeRuns=[[0, 0, 1, "clearing"]])
    renderer._cells = {0: "clearing"}
    renderer._canvas = None
    renderer._player_control = None
    renderer.ApplySnapshot(dict(snapshot(), biomeRuns=[[0, 0, 1, "unknown"]]))
    assert renderer._cells[0] == "unknown"


def test_maze_map_can_be_held_offhand_and_reuses_map_geometry():
    item = json.loads((ROOT / "TwilightBossSliceB/items/filled_maze_map.item.json").read_text())
    components = item["minecraft:item"]["components"]
    assert components.get("minecraft:allow_off_hand") is True
    attachment = ROOT / "TwilightBossSliceR/attachables/filled_maze_map.attachable.json"
    assert attachment.is_file()
    data = json.loads(attachment.read_text())["minecraft:attachable"]["description"]
    assert data["identifier"] == "tf_slice:filled_maze_map"
    assert data["geometry"]["default"] == "geometry.tf_magic_map_carrier"


def test_server_updates_held_maze_and_preserves_exploration_across_reload():
    cls = server_class([
        "_scan_carried_magic_maps", "_send_maze_map_snapshot", "_held_map_hand_item",
        "_is_maze_map_stack", "_is_magic_map_stack", "_persist_maze_map_records", "_load_maze_map_records",
    ])
    server = cls()
    data = record()
    identity = maze.map_identity(data)
    held = {"itemName": "tf_slice:filled_maze_map", "extraId": identity}
    server._known_players = {"player"}
    server._get_dimension = lambda _: 7
    server._carried_item = lambda _: held
    server._offhand_item = lambda _: {"itemName": "tf_slice:filled_magic_map"}
    server._get_foot_pos = lambda _: (55, 8, 55)
    server._get_block = lambda *args: {"name": "minecraft:air"}
    server._magic_map_held_states = {}
    server._magic_map_delta_states = {}
    server._magic_map_discovery_frontiers = {}
    data.update(structureOrigin=[0, 0], passageRuns=[])
    server._maze_map_records = {identity: data}
    sent = []
    server.NotifyToClient = lambda *args: sent.append(args)
    server._scan_carried_magic_maps()
    payload = sent[-1][2]
    assert payload["mapKind"] == "maze" and payload["mapId"] == identity
    assert payload["biomeRuns"] and payload["openScreen"] is False
    assert server._maze_map_dirty
    stored = {}
    server._magic_map_extra = types.SimpleNamespace(
        SetExtraData=lambda key, value, _: stored.update({key: value}),
        SaveExtraData=lambda: True,
        GetExtraData=lambda key: stored.get(key),
    )
    assert server._persist_maze_map_records()
    assert not server._maze_map_dirty
    assert server._load_maze_map_records()[identity]["exploredCells"] == data["exploredCells"]
    before = len(sent)
    server._get_dimension = lambda _: 0
    assert not server._send_maze_map_snapshot("player", identity)
    assert len(sent) == before


def test_maze_clone_keeps_identity_and_shared_exploration():
    cls = server_class(["_valid_magic_map_clone_source"])
    item = {"itemName": "tf_slice:filled_maze_map", "extraId": maze.map_identity(record()), "count": 1}
    assert cls._valid_magic_map_clone_source(item)
    result = magic.clone_magic_map_stack(item, 3)
    assert result["count"] == 4 and result["extraId"] == item["extraId"]
    assert item["count"] == 1


def test_maze_context_rejects_above_ground_and_empty_floor_metadata():
    cls = load_methods("structureWorldgenService.py", ["labyrinth_map_context"], {"copy": copy})
    service = cls()
    job = {"kind": "labyrinth", "bounds": [0, 0, 0, 110, 14, 110], "anchor": [0, 0, 0],
           "markers": {"levels": [1, 8], "mapCenter": [55, 8, 55]}}
    service._ledger = {"a": job}
    service._manual_jobs = []
    assert service.labyrinth_map_context((55, 80, 55)) is None
    assert service.labyrinth_map_context((55, 8, 55))["center"] == [55, 8, 55]
    job["markers"]["levels"] = []
    assert service.labyrinth_map_context((55, 8, 55)) is None


def test_background_maze_snapshot_updates_the_open_full_screen():
    applied = []
    config = types.SimpleNamespace(DIMENSION_ID=7, MAGIC_MAP_HELD_HUD_ENABLED=False)
    cls = load_methods("clientSystem.py", ["OnMagicMapSnapshot"], {
        "config": config, "magicMapUI": types.SimpleNamespace(set_snapshot=applied.append),
    })
    client = cls()
    client._ensure_magic_map_ui = lambda: None
    client.OnMagicMapSnapshot(dict(snapshot(), openScreen=False))
    assert len(applied) == 1


def test_full_screen_switch_clears_old_floor_and_rejects_late_delta():
    ui = load_ui_module()
    renderer = object.__new__(ui.MagicMapUI)
    renderer._snapshot = dict(snapshot(), biomeRuns=[[0, 0, 1, "clearing"]])
    renderer._cells = {0: "clearing"}
    renderer._canvas = None
    renderer._player_control = None
    renderer._dynamic_controls = []
    renderer._biome_bitmap_controls = {}
    renderer.ApplySnapshot(snapshot(1))
    assert renderer._cells == {}
    assert renderer._title_text() == "迷宫地图"
    renderer.ApplyDelta(dict(snapshot(), biomeRuns=[[0, 0, 1, "clearing"]]))
    assert renderer._cells == {}
    renderer.ApplySnapshot({"mapId": 123, "gridSize": 128, "biomeRuns": [[0, 0, 1, "forest"]]})
    assert renderer._title_text() == "魔法地图"
    assert "yCenter" not in renderer._snapshot
    assert renderer._cells == {0: "forest"}


def test_invalid_map_id_never_becomes_a_cache_filename(tmp_path):
    cache = bitmap.MagicMapBitmapCache(str(tmp_path))
    for identity in (None, 0, -1, "tfmz:v1:bad", "../../elsewhere"):
        assert cache.render(identity, {0: "unknown"}) is None
    assert list(tmp_path.iterdir()) == []


def test_saved_cells_are_bounded_and_negative_coordinates_floor_correctly():
    assert maze.normalize_explored_cells({"0": "unknown", "16383": "clearing", "-1": "unknown",
                                          "16384": "unknown", "bad": "unknown", "2": "forest"}) == {
        "0": "unknown", "16383": "clearing"}
    assert maze.normalize_explored_cells(None) == {}
    data = maze.create_record("negative", (-55, -8, -55), -8)
    calls = []
    def block(pos):
        calls.append(pos)
        return {"name": "minecraft:air"}
    maze.explore(data, (-55.5, -8, -55.5), block, budget=1)
    assert calls[0] == (-56, -8, -56)
    calls[:] = []
    assert not maze.explore(data, (1000, -8, 1000), block)
    assert not calls


def test_crafting_event_and_cursor_repair_preserve_maze_identity():
    cls = server_class(["_valid_magic_map_clone_source", "OnMagicMapCrafted", "_repair_cloned_magic_map"])
    source = {"itemName": "tf_slice:filled_maze_map", "extraId": maze.map_identity(record()), "count": 1}
    server = cls()
    server._tick = 1
    server._pending_magic_map_clone_sources = {"player": {"item": source, "expires": 40}}
    # Missing CF in this method harness deliberately exercises its immediate repair fallback.
    repaired = []
    server._repair_cloned_magic_map = repaired.append
    event = {"playerId": "player", "itemDict": {"itemName": "tf_slice:filled_maze_map", "count": 4}}
    server.OnMagicMapCrafted(event)
    assert event["itemDict"]["extraId"] == source["extraId"]
    assert repaired[0]["item"]["count"] == 4
    assert "player" not in server._pending_magic_map_clone_sources


def test_failed_maze_storage_write_does_not_clear_dirty_flag():
    cls = server_class(["_persist_maze_map_records"])
    server = cls()
    server._maze_map_records = {}
    server._maze_map_dirty = True
    server._magic_map_extra = types.SimpleNamespace(SetExtraData=lambda *args: False,
                                                   SaveExtraData=lambda: True)
    assert not server._persist_maze_map_records()
    assert server._maze_map_dirty
