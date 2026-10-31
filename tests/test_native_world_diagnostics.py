"""Exercise bounded diagnostics through actual server and SDK call boundaries."""
import json
import types
import pytest

from tests.test_portal_arrival_runtime import SERVER, SERVER_PATH
from tests.test_water_marker_runtime import host, event, DIM
from TwilightBossSlice import native_world_diagnostics as diag


@pytest.fixture(autouse=True)
def isolate_diagnostic_sink(monkeypatch):
    # Candidate tests must never mix fixture output with the next game capture.
    monkeypatch.setattr(diag, "OUTPUT_DIRECTORY", "")


def probe():
    now = [100.0]
    return diag.NativeWorldDiagnostics(DIM, True, lambda: now[0]), now


def rows(lines):
    return [json.loads(line[len(diag.PREFIX):]) for line in lines]


def test_disabled_and_other_dimensions_never_arm_or_emit():
    p, now = probe()
    assert p.record("x", {"dimensionId": 0}, 0) is None
    assert p.started is None
    p.enabled = False
    p.record("x", {"dimensionId": DIM}, 0)
    lines = []
    p.close(lines.append)
    assert lines == []


def test_snapshot_is_detached_and_limits_fields_and_text():
    p, now = probe()
    data = {"dimensionId": DIM, "position": [1, 62, 3], "name": "x" * 1000,
            "unrelated": "private"}
    p.record("test", data, 3)
    data["position"][0] = 99
    item = p.queue[0]
    assert item["position"] == [1, 62, 3]
    assert len(item["name"]) == 160
    assert "unrelated" not in item


def test_overload_is_bounded_and_loss_is_visible():
    p, now = probe()
    for i in range(diag.EVENT_LIMIT + 100):
        p.record("x", {"dimensionId": DIM}, i)
    assert p.sequence == diag.EVENT_LIMIT
    assert len(p.queue) == diag.QUEUE_LIMIT
    assert p.dropped == diag.EVENT_LIMIT - diag.QUEUE_LIMIT
    assert p.closed and p.reason == "event_limit"
    lines = []
    p.close(lines.append)
    parsed = rows(lines)
    assert parsed[-1]["phase"] == "stop"
    assert parsed[-1]["dropped"] == p.dropped
    assert all(len(r["events"]) <= diag.BATCH_LIMIT for r in parsed if "events" in r)


def test_wall_clock_timeout_stops_without_new_event_or_manual_command():
    p, now = probe()
    p.record("x", {"dimensionId": DIM}, 1)
    lines = []
    p.flush(lines.append)
    now[0] += diag.DURATION_SECONDS
    p.flush(lines.append)
    assert p.finished and rows(lines)[-1]["reason"] == "time_limit"
    before = list(lines)
    p.record("x", {"dimensionId": DIM}, 2)
    p.flush(lines.append)
    assert lines == before


def test_flush_rate_and_emitter_failure_do_not_escape():
    p, now = probe()
    p.record("x", {"dimensionId": DIM}, 0)
    lines = []
    p.flush(lines.append)
    p.record("x", {"dimensionId": DIM}, 1)
    p.flush(lines.append)
    assert len(p.queue) == 1
    now[0] += diag.FLUSH_SECONDS
    def fail(line):
        raise IOError("sink")
    p.flush(fail)
    assert p.finished and not p.queue and p.reason == "sink_error"


def test_wrapper_preserves_result_identity_arguments_and_exception():
    p, now = probe()
    owner = types.SimpleNamespace(_native_world_diag=p, _tick=8)
    result = {"name": "minecraft:structure_void", "aux": 0}
    calls = []
    def api(*args):
        calls.append(args)
        return result
    assert diag.call(owner, "water.read", (1, 62, 3), DIM, api, 1, False) is result
    assert calls == [(1, False)]
    assert p.queue[1]["pair"] == p.queue[0]["seq"]
    error = RuntimeError("native edge")
    def fail():
        raise error
    try:
        diag.call(owner, "water.write", (1, 62, 3), DIM, fail)
    except RuntimeError as actual:
        assert actual is error
    else:
        assert False, "SDK exception swallowed"
    assert p.queue[-1]["kind"] == "water.write.error"


def test_diagnostic_clock_failure_cannot_suppress_sdk_call():
    p, now = probe()
    def fail():
        raise RuntimeError("clock")
    p.clock = fail
    owner = types.SimpleNamespace(_native_world_diag=p, _tick=0)
    assert diag.call(owner, "water.read", (1, 62, 3), DIM, lambda: 7) == 7
    p.started = 100
    p.flush(lambda line: None)
    assert p.finished and p.reason == "clock_error"


def test_write_checkpoint_is_emitted_before_native_call_can_block():
    p, now = probe()
    order = []
    owner = types.SimpleNamespace(_native_world_diag=p, _tick=0,
                                  _emit_native_world_diag=order.append)
    def api():
        assert rows(order)[0]["event"]["kind"] == "water.write.begin"
        order.append("native-called")
        return False
    assert diag.call(owner, "water.write", (1, 62, 3), DIM, api) is False
    assert order[-1] == "native-called"


def test_diagnostic_records_are_on_disk_before_destroy(tmp_path, monkeypatch):
    monkeypatch.setattr(diag, "OUTPUT_DIRECTORY", str(tmp_path))
    p, now = probe()
    p.record("chunk.loaded", {"dimensionId": DIM}, 1)
    p.flush(lambda line: None)
    files = list(tmp_path.glob("native-world-*.jsonl"))
    assert len(files) == 1
    entries = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert entries[0]["phase"] == "start"
    assert entries[1]["events"][0]["kind"] == "chunk.loaded"
    owner = types.SimpleNamespace(_native_world_diag=p, _tick=2,
                                  _emit_native_world_diag=lambda line: None)
    def api():
        entries = [json.loads(line) for line in files[0].read_text().splitlines()]
        assert entries[-1]["phase"] == "checkpoint"
        return True
    assert diag.call(owner, "water.write", (1, 62, 3), DIM, api) is True


def test_real_structure_entry_records_before_and_final_without_mutating_extra_args():
    owner = host()
    owner._native_world_diag, now = probe()
    args = event()
    original = args["structureName"]
    owner.OnPlaceNeteaseStructureFeatureEvent(args)
    entries = list(owner._native_world_diag.queue)
    assert [e["kind"] for e in entries] == ["structure.begin", "structure.final"]
    assert entries[0]["structureName"] == original
    assert entries[1]["structureName"] == "tf_slice:ruin_landmark_noop"
    assert entries[1]["pair"] == entries[0]["seq"]
    assert "pair" not in args
    assert owner._water_marker_cleanup.has_work()


def test_real_cleanup_entry_emits_read_and_write_pairs_once():
    from tests.test_water_marker_cleanup import World, POS
    owner = host()
    owner._native_world_diag, now = probe()
    world = World()
    class Chunk:
        def CheckChunkState(self, dimension, pos):
            return world.ready(pos, dimension)
    class Block:
        def SetBlockNew(self, pos, block, handling, dimension, legacy, update):
            assert (block, handling, legacy, update) == (
                {"name": "minecraft:air", "aux": 0}, 0, True, True)
            return world.clear(pos, dimension)
        def GetBlockNew(self, pos, dimension):
            return world.read(pos, dimension)
    owner._chunk_comp = Chunk()
    owner._block_comp = Block()
    owner.OnPlaceNeteaseStructureFeatureEvent(event())
    owner.OnChunkLoadedServerEvent(
        {"dimension": DIM, "chunkPosX": -7, "chunkPosZ": 14})
    for tick in range(1, 40):
        owner._tick = tick
        owner._tick_water_marker_cleanup()
    entries = list(owner._native_world_diag.queue)
    assert sum(e["kind"] == "water.write.begin" for e in entries) == 1
    assert sum(e["kind"] == "water.write.end" for e in entries) == 1
    assert any(e.get("name") == "minecraft:structure_void" for e in entries)
    assert any(e["kind"] == "chunk.loaded" for e in entries)


def test_server_automatic_update_and_destroy_are_wired():
    source = SERVER_PATH.read_text(encoding="utf-8")
    init = source.split("    def __init__(", 1)[1].split("    def Destroy(", 1)[0]
    update = source.split("    def Update(", 1)[1].split("\n    def ", 1)[0]
    destroy = source.split("    def Destroy(", 1)[1].split("\n    def ", 1)[0]
    assert "native_world_diagnostics.NativeWorldDiagnostics(config.DIMENSION_ID)" in init
    assert "diagnostic.flush(self._emit_native_world_diag)" in update
    assert "diagnostic.close(self._emit_native_world_diag)" in destroy
