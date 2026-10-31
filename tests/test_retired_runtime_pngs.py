import json
from pathlib import Path

import pytest
from PIL import Image

from tools import retired_runtime_pngs as cleanup


def fixture(root, reference=None, source_kind="project-item"):
    rp = root / "TwilightBossSliceR"
    (root / "TwilightBossSliceB").mkdir()
    old = rp / "textures/items/test.png"
    new = rp / "textures/tf_beautified/items/test.png"
    old.parent.mkdir(parents=True)
    new.parent.mkdir(parents=True)
    Image.new("RGBA", (16, 16), (20, 30, 40, 255)).save(old)
    Image.new("RGBA", (16, 16), (50, 60, 70, 255)).save(new)
    bank = root / "resource_art/block_beautification/v1"
    bank.mkdir(parents=True)
    (bank / "assets/items").mkdir(parents=True)
    (bank / "assets/items/test.png").write_bytes(new.read_bytes())
    (bank / "manifest.json").write_text(json.dumps({"schema_version": 1, "enabled": True, "entries": [{"source_kind": source_kind, "source_runtime_path": "textures/items/test", "source_sha256": cleanup.digest(old), "output_relative": "items/test.png"}]}))
    if reference is not None:
        (rp / "binding.json").write_text(json.dumps({"texture": reference}))
    return old, new


def test_real_cleanup_archives_and_removes_only_unreferenced_replaced_png(tmp_path):
    old, new = fixture(tmp_path, "textures/tf_beautified/items/test")
    original = old.read_bytes()
    enhanced = new.read_bytes()
    proposed = cleanup.plan(tmp_path)
    assert len(proposed["files"]) == 1
    cleanup.apply(tmp_path, proposed)
    assert not old.exists()
    assert new.read_bytes() == enhanced
    assert cleanup.original_texture(old, tmp_path).read_bytes() == original
    assert cleanup.check(tmp_path) == []


@pytest.mark.parametrize("reference", ["textures/items/test", "textures/items/%s", "textures/items/"])
def test_exact_and_dynamic_paths_protect_original(tmp_path, reference):
    old, unused = fixture(tmp_path, reference)
    assert not cleanup.plan(tmp_path)["files"]
    assert old.exists()


def test_unknown_or_missing_replacement_is_not_removed(tmp_path):
    old, new = fixture(tmp_path)
    new.unlink()
    assert not cleanup.plan(tmp_path)["files"]
    assert old.exists()


def test_changed_inputs_fail_closed_before_any_deletion(tmp_path):
    old, unused = fixture(tmp_path)
    proposed = cleanup.plan(tmp_path)
    old.write_bytes(b"changed")
    with pytest.raises((ValueError, OSError)):
        cleanup.apply(tmp_path, proposed)
    assert old.read_bytes() == b"changed"


def test_runtime_reintroduction_and_changed_archive_are_rejected(tmp_path):
    old, unused = fixture(tmp_path)
    cleanup.apply(tmp_path, cleanup.plan(tmp_path))
    baseline = cleanup.original_texture(old, tmp_path)
    old.write_bytes(baseline.read_bytes())
    assert cleanup.check(tmp_path)
    old.unlink()
    baseline.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        cleanup.original_texture(old, tmp_path)


def test_invalid_runtime_json_blocks_removal(tmp_path):
    old, unused = fixture(tmp_path)
    (old.parents[2] / "bad.json").write_text("not JSON")
    proposed = cleanup.plan(tmp_path)
    assert proposed["errors"]
    with pytest.raises(ValueError):
        cleanup.apply(tmp_path, proposed)
    assert old.exists()


def test_native_asset_is_not_a_pack_deletion_candidate(tmp_path):
    old, unused = fixture(tmp_path, source_kind="builtin-base")
    assert cleanup.plan(tmp_path)["files"] == {}
    assert old.exists()


def test_real_copy_writer_does_not_restore_retired_png_and_baker_resolves_archive(tmp_path, monkeypatch):
    from tools import build_public_block_shapes as blocks
    from tools.block_texture_beautification import resolve_source_texture
    old, new = fixture(tmp_path)
    cleanup.apply(tmp_path, cleanup.plan(tmp_path))
    baseline = cleanup.original_texture(old, tmp_path)
    monkeypatch.setattr(blocks, "ROOT", tmp_path)
    blocks.copy_texture(baseline, old)
    assert not old.exists()
    material = resolve_source_texture(old, tmp_path)
    assert material.read_bytes() == new.read_bytes()
    assert cleanup.check(tmp_path) == []


def test_reviewed_legacy_orphan_is_hash_locked_and_references_still_protect_it(tmp_path, monkeypatch):
    old, unused = fixture(tmp_path)
    manifest = tmp_path / "resource_art/block_beautification/v1/manifest.json"
    manifest.unlink()
    monkeypatch.setattr(cleanup, "LEGACY_ORPHANS", {"textures/items/test.png": cleanup.digest(old)})
    (tmp_path / "TwilightBossSliceR/binding.json").write_text(json.dumps({"texture": "textures/items/test"}))
    assert cleanup.plan(tmp_path)["files"] == {}
    (tmp_path / "TwilightBossSliceR/binding.json").unlink()
    proposed = cleanup.plan(tmp_path)
    assert len(proposed["files"]) == 1
    cleanup.apply(tmp_path, proposed)
    assert not old.exists()
    assert cleanup.original_texture(old, tmp_path).is_file()
