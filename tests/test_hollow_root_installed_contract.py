"""Validate the selected pack's template origin together with its rules."""
import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import build_ruin_structures as builder
import check_hollow_root_placement as check


def fixture(root, tree_offset=10, stump_offset=9):
    for kind, offset in (("hollow_tree", tree_offset), ("hollow_stump", stump_offset)):
        shape = builder.SparseStructure((2, 11, 2), kind)
        for y in range(5, 9):
            shape.set(0, y, 0, "tf_slice:root_block")
        for y in range(9, 11):
            shape.set(0, y, 0, "tf_slice:twilight_oak_log")
        filename = "v00/x000_z000.mcstructure" if kind == "hollow_tree" else "v00.mcstructure"
        builder.write_mcstructure(root / "structures/tf_slice/ruins" / kind / filename, shape)
        path = root / "netease_feature_rules" / (kind + "_feature_rule.json")
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(json.dumps({"minecraft:feature_rules": {
            "conditions": {"placement_pass": "after_surface_pass"},
            "distribution": {"y": "query.get_height_at(0, 0) - %d" % offset}}}))


def test_rejects_old_rules_with_new_root_geometry(tmp_path):
    fixture(tmp_path, 1, 1)
    result = check.inspect(tmp_path)
    assert len(result["issues"]) == 2
    assert {r["requiredOffset"] for r in result["families"]} == {9, 10}


def test_accepts_embedded_roots_and_never_writes_input(tmp_path):
    fixture(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert check.inspect(tmp_path)["issues"] == []
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_missing_templates_fail_closed(tmp_path):
    result = check.inspect(tmp_path)
    assert len(result["issues"]) == 2
