import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "TwilightBossSliceB"))


def test_clearance_builder_emits_nine_water_supported_predicates():
    import build_swamp_features as builder
    documents, clearances = builder.huge_lily_pad_clearance_documents(
        ["minecraft:water", "minecraft:flowing_water"])
    assert len(clearances) == 9
    block = documents["huge_lily_pad_clearance_block_feature.json"][
        "minecraft:single_block_feature"
    ]
    assert block["places_block"] == [
        {"block": "minecraft:air", "weight": 1}
    ]
    assert block["may_attach_to"]["bottom"] == [
        "minecraft:water", "minecraft:flowing_water"
    ]


def test_retired_darkwood_structure_generator_cannot_reintroduce_air_probes():
    import build_dark_forest_content as builder
    assert not hasattr(builder, "build_darkwood_tree_variants")


class Features:
    def __init__(self):
        self.names = set()
    def AddNeteaseFeatureWhiteList(self, name):
        self.names.add(name)
        return True
    def RemoveNeteaseFeatureWhiteList(self, name):
        self.names.discard(name)


def pond_service():
    from TwilightBossSlice.lilyPadWorldgenService import LilyPadWorldgenService, OFFSETS, TRIGGER
    blocks = {(x, 63, z): "minecraft:water" for x, z in OFFSETS}
    writes = []
    def read(pos, dim):
        assert dim == 33027004
        return {"name": blocks.get(pos, "minecraft:air")}
    def write(pos, name, dim):
        writes.append((pos, name))
        blocks[pos] = name
        return True
    service = LilyPadWorldgenService(Features(), read, write, 33027004,
                                    lambda pos, dim: True)
    event = {"structureName": TRIGGER, "dimensionId": 33027004,
             "x": 0, "y": 72, "z": 0}
    return service, event, blocks, writes


def test_handoff_only_queues_then_valid_pond_places_one_complete_pad():
    service, event, blocks, writes = pond_service()
    service.on_structure_feature_event(event)
    assert writes == []
    service.tick()
    assert writes == [((0, 64, 0), "tf_slice:huge_lily_pad")]
    service.tick()
    assert len(writes) == 1


@pytest.mark.parametrize("x,z", [(x, z) for x in (-1, 0, 1) for z in (-1, 0, 1)])
@pytest.mark.parametrize("obstruction", ("minecraft:stone", "tf_slice:huge_lily_pad"))
def test_every_footprint_cell_blocks_placement_without_writes(x, z, obstruction):
    service, event, blocks, writes = pond_service()
    blocks[(x, 64, z)] = obstruction
    before = dict(blocks)
    service.on_structure_feature_event(event)
    service.tick()
    assert not writes
    assert blocks == before


@pytest.mark.parametrize("x,z", [(x, z) for x in (-1, 0, 1) for z in (-1, 0, 1)])
def test_every_footprint_cell_requires_water_below(x, z):
    service, event, blocks, writes = pond_service()
    blocks[(x, 63, z)] = "minecraft:dirt"
    service.on_structure_feature_event(event)
    service.tick()
    assert not writes


def test_unloaded_chunks_retry_without_block_reads_or_terrain_writes():
    service, event, blocks, writes = pond_service()
    service.ready = lambda pos, dim: False
    service.read = lambda *args: pytest.fail("must not read unloaded chunks")
    service.on_structure_feature_event(event)
    for _ in range(50):
        service.tick()
    assert not writes
    assert not service.pending


def test_duplicate_wrong_dimension_and_malformed_events_are_harmless():
    service, event, blocks, writes = pond_service()
    service.on_structure_feature_event(dict(event, dimensionId=0))
    service.on_structure_feature_event(dict(event, x="bad"))
    service.on_structure_feature_event(dict(event, structureName="other"))
    assert not service.pending
    service.on_structure_feature_event(dict(event))
    service.on_structure_feature_event(dict(event))
    assert len(service.pending) == 1
    service.tick()
    assert len(writes) == 1
    service.destroy()
    assert not service.pending
    assert not service.feature.names


def test_scoped_tree_repair_does_not_write_lily_files(tmp_path):
    import worldgen_probe_repairs as repair
    lily = tmp_path / repair.FEATURE_PATH / "huge_lily_pad_feature.json"
    lily.parent.mkdir(parents=True)
    lily.write_text('{"preserve": true}')
    assert repair.main(["--write", "--output-root", str(tmp_path)]) == 0
    assert lily.read_text() == '{"preserve": true}'
    assert repair.main(["--check", "--output-root", str(tmp_path)]) == 0
    snapshot = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert repair.main(["--check", "--output-root", str(tmp_path)]) == 0
    assert snapshot == {p: p.read_bytes() for p in snapshot}


def test_scoped_tree_rebuild_preserves_unrelated_features(tmp_path):
    import worldgen_probe_repairs as repair
    directory = tmp_path / repair.FEATURE_PATH
    directory.mkdir(parents=True)
    assert repair.removed_features() == []
    keep = directory / "unrelated_feature.json"
    keep.write_text("{}")
    repair.main(["--write", "--output-root", str(tmp_path)])
    assert keep.read_text() == "{}"
    assert not any((directory / name).exists() for name in repair.removed_features())
    (directory / "canopy_tree_anchor_feature.json").unlink()
    assert repair.main(["--check", "--output-root", str(tmp_path)]) == 1
    with pytest.raises(SystemExit):
        repair.main(["--write", "--output-root", str(ROOT)])


def test_scan_rejects_self_replacing_air_but_allows_real_cleanup():
    from worldgen_probe_repairs import air_to_air_probes
    data = {
        "broken": {"minecraft:single_block_feature": {"places_block": "minecraft:air", "may_replace": ["minecraft:air"]}},
        "cleanup": {"minecraft:single_block_feature": {"places_block": [{"block": "minecraft:air"}], "may_replace": ["tf_slice:canopy_log"]}},
        "list": [], "other": {"format_version": "1.14.0"},
    }
    assert air_to_air_probes(data) == ["broken"]


def test_native_handoff_is_wired_to_real_service_without_worker_block_reads():
    import re
    from types import SimpleNamespace
    from TwilightBossSlice.lilyPadWorldgenService import TRIGGER
    source = (ROOT / "TwilightBossSliceB/TwilightBossSlice/serverSystem.py").read_text(encoding="utf-8")
    # Execute the actual event handler in isolation; this method is Python 3
    # compatible despite the containing module targeting NetEase Python 2.
    match = re.search(r"    def OnPlaceNeteaseStructureFeatureEvent\(self, args\):.*?(?=\n    def )", source, re.S)
    import textwrap
    namespace = {"config": SimpleNamespace(DIMENSION_ID=33027004), "LILY_PAD_CANDIDATE": TRIGGER}
    exec(textwrap.dedent(match.group()), namespace)
    service, event, blocks, writes = pond_service()
    host = SimpleNamespace(_lily_pad_worldgen=service,
                           _worldgen_perf_record_structure=lambda name: None,
                           _dimension_change_in_progress=set())
    namespace["OnPlaceNeteaseStructureFeatureEvent"](host, event)
    assert len(service.pending) == 1
    assert not writes
    service.tick()
    assert len(writes) == 1
    assert "self._lily_pad_worldgen.tick()" in source
    assert "self._lily_pad_worldgen.destroy()" in source


def test_pending_and_tick_budgets_are_bounded():
    from TwilightBossSlice.lilyPadWorldgenService import MAX_PENDING, PER_TICK
    service, event, blocks, writes = pond_service()
    for x in range(MAX_PENDING + 10):
        service.on_structure_feature_event(dict(event, x=x * 16))
    assert len(service.pending) == MAX_PENDING
    service.tick()
    assert len(service.pending) == MAX_PENDING - PER_TICK


def test_missing_blocks_retry_then_recover_and_failed_writes_do_not_spawn_parts():
    service, event, blocks, writes = pond_service()
    original_read = service.read
    service.read = lambda *args: None
    service.on_structure_feature_event(dict(event))
    service.tick()
    assert not writes and len(service.pending) == 1
    service.read = original_read
    service.write = lambda *args: False
    service.tick()
    assert not writes and not service.pending


def test_whitelist_failure_releases_previously_registered_name():
    from TwilightBossSlice.lilyPadWorldgenService import LilyPadWorldgenService, NOOP
    class Broken(Features):
        def AddNeteaseFeatureWhiteList(self, name):
            return False if name == NOOP else super().AddNeteaseFeatureWhiteList(name)
    features = Broken()
    with pytest.raises(RuntimeError):
        LilyPadWorldgenService(features, None, None, 33027004, None)
    assert not features.names


def test_destination_server_patch_is_scoped_idempotent_and_fails_closed():
    from worldgen_probe_repairs import patch_lily_server_hooks
    current = (ROOT / "TwilightBossSliceB/TwilightBossSlice/serverSystem.py").read_text(encoding="utf-8")
    assert patch_lily_server_hooks(current) == current
    assert patch_lily_server_hooks(current + "\n# unrelated destination edit\n").endswith("# unrelated destination edit\n")
    with pytest.raises(ValueError):
        patch_lily_server_hooks("# unknown server layout\n")
