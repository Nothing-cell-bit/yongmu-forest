import copy
import json
import pathlib
import subprocess
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import build_river_surface_candidate as builder
import build_ruin_structures as ruins


def baseline():
    return {"minecraft:biome": {"description": {"identifier": "dm33027004_river",
            "inherits": "river"}, "components": {"minecraft:overworld_height": {"noise_type": "river"},
            "dm33027004": {}, "tf_slice_biome_stream": {}}}}


def historical_j():
    # Frozen from the actual J package used in the I/J world comparison.
    return json.loads((pathlib.Path(__file__).parent / "fixtures" /
                       "river_surface_j_20261020.json").read_bytes())


def channel_fill():
    expected = historical_j()
    expected["minecraft:biome"]["components"]["netease:overworld_surface"] = {
        "adjustments": [
            {"type": "fill", "min_height": 63, "max_height": 255,
             "pool": [{"fill_block": "minecraft:air", "weight": 1}]},
            {"type": "fill", "min_height": 61, "max_height": 63,
             "pool": [{"fill_block": "minecraft:water", "weight": 1}]},
        ]}
    return expected


def test_known_failed_j_and_k_are_migrated_without_changing_other_components():
    original = historical_j()
    before = copy.deepcopy(original)
    expected = channel_fill()
    result = builder.river_candidate(original)
    assert result == expected
    assert builder.river_candidate(result) == result
    assert original == before
    k = historical_j()
    for step in k["minecraft:biome"]["components"]["netease:overworld_surface"]["adjustments"]:
        step["to_block_pool"] = step.pop("pool")
    assert builder.river_candidate(k) == expected
    previous_l = copy.deepcopy(expected)
    previous_l["minecraft:biome"]["components"]["netease:overworld_surface"]["adjustments"][1]["max_height"] = 62
    assert builder.river_candidate(previous_l) == expected


def test_channel_nodes_use_shipped_fill_shape_and_strict_fixed_intervals():
    document = builder.river_candidate(baseline())
    steps = document["minecraft:biome"]["components"]["netease:overworld_surface"]["adjustments"]
    reference = json.loads((pathlib.Path(__file__).parent / "fixtures" /
        "netease_editor_fill_reference_20261022.json").read_bytes())
    required = set(reference["component"]["adjustments"][0])
    for step in steps:
        assert step["type"] == "fill"
        assert set(step) == required
        assert type(step["min_height"]) is int and type(step["max_height"]) is int
        assert 0 <= step["min_height"] < step["max_height"] <= 255
        assert step["pool"]
        assert "to_block_pool" not in step and "from_block_pool" not in step
    assert [s["pool"][0]["fill_block"] for s in steps] == [
        "minecraft:air", "minecraft:water"]
    assert [(s["min_height"], s["max_height"]) for s in steps] == [
        (63, 255), (61, 63)]


def test_water_band_includes_the_measured_unfilled_y62_cap():
    evidence = json.loads((pathlib.Path(__file__).parent / "fixtures" /
        "river_fill_endpoint_L_20261022.json").read_bytes())
    assert evidence["observedColumn"]["61"] == "minecraft:water"
    assert evidence["observedColumn"]["62"] == "minecraft:sand"
    step = builder.river_candidate(baseline())["minecraft:biome"]["components"]["netease:overworld_surface"]["adjustments"][1]
    # This measured L result rejects the old inclusive-range model. Test the
    # corrected band against both Y61 and the still-blocked endpoint Y62.
    selected = range(step["min_height"], step["max_height"])
    assert 61 in selected and 62 in selected
    assert 60 not in selected and 63 not in selected
    verified_m = json.loads((pathlib.Path(__file__).parent / "fixtures" /
        "river_fill_endpoint_M_20261022.json").read_bytes())
    assert step == verified_m["waterFillNode"]
    assert verified_m["observedColumn"]["61"] == "minecraft:water"
    assert verified_m["observedColumn"]["62"] == "minecraft:water"
    assert verified_m["observedColumn"]["60"] == "minecraft:sand"
    assert verified_m["observedColumn"]["63"] == "minecraft:air"


def test_observed_river_sand_column_is_still_repaired_by_declared_operations():
    # A configuration-contract calculation, not native-runtime acceptance.
    steps = builder.river_candidate(baseline())["minecraft:biome"]["components"]["netease:overworld_surface"]["adjustments"]
    def apply(column):
        for step in steps:
            for y in range(step["min_height"], step["max_height"]):
                column[y] = step["pool"][0]["fill_block"]
        return column
    sand = {y: "minecraft:sand" for y in range(58, 64)}
    sand[64] = "minecraft:air"
    fixed = apply(sand.copy())
    assert fixed[60] == "minecraft:sand"
    assert fixed[61] == fixed[62] == "minecraft:water"
    assert fixed[63] == "minecraft:air"
    deep = {53: "minecraft:gravel", **{y: "minecraft:water" for y in range(54, 63)}}
    adjusted = apply(deep.copy())
    assert all(adjusted[y] == block for y, block in deep.items())
    assert all(adjusted[y] == "minecraft:water" for y in range(54, 63))
    # These are native pre-feature terrain operations. They do not provide a
    # live-world/container-preservation contract and must never be SDK writes.
    assert "SetBlock" not in pathlib.Path(builder.__file__).read_text(encoding="utf-8")


def test_candidate_preserves_height_and_rejects_other_biomes_or_existing_adjustment():
    import pytest
    original = baseline()
    result = builder.river_candidate(original)
    del result["minecraft:biome"]["components"]["netease:overworld_surface"]
    assert result == original
    wrong = copy.deepcopy(original)
    wrong["minecraft:biome"]["description"]["identifier"] = "dm33027004_plains"
    with pytest.raises(ValueError):
        builder.river_candidate(wrong)
    wrong = historical_j()
    wrong["minecraft:biome"]["components"]["netease:overworld_surface"]["adjustments"][0]["min_height"] = 0
    with pytest.raises(ValueError):
        builder.river_candidate(wrong)
    wrong = baseline()
    wrong["minecraft:biome"]["components"]["minecraft:overworld_height"] = {"noise_params": [-9, 0]}
    with pytest.raises(ValueError):
        builder.river_candidate(wrong)
    wrong = copy.deepcopy(original)
    wrong["minecraft:biome"]["components"]["netease:overworld_surface"] = {"adjustments": []}
    with pytest.raises(ValueError):
        builder.river_candidate(wrong)


def test_channel_rebuild_preserves_explicit_native_depth_calibration():
    original = channel_fill()
    original["minecraft:biome"]["components"]["minecraft:overworld_height"] = {"noise_type": "ocean"}
    assert builder.river_candidate(original) == original


def test_cli_corrects_j_without_rewriting_existing_dry_guards(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    bp = source / "TwilightBossSliceB"
    relative = pathlib.Path("netease_biomes/dm33027004/dm33027004_river.json")
    (bp / relative).parent.mkdir(parents=True)
    (bp / relative).write_text(json.dumps(historical_j()), encoding="utf-8")
    catalog = bp / "structures/tf_slice/ruins/structure_catalog_v1.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({"structures": [
        {"id": kind} for kind in ruins.DRY_GROUND_RUINS]}), encoding="utf-8")
    features = bp / "netease_features"
    features.mkdir()
    for kind in ruins.DRY_GROUND_RUINS:
        document = ruins._scatter_feature("tf_slice:%s_scatter_feature" % kind,
            "tf_slice:%s_structure_selector_feature" % kind, 90, 2, 2)
        (features / (kind + "_scatter_feature.json")).write_text(
            json.dumps(document), encoding="utf-8")
    before = {p: p.read_bytes() for p in bp.rglob("*.json")}
    run = subprocess.run([sys.executable, builder.__file__, "--source-root",
        str(source), "--output-root", str(output)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == [relative.as_posix()]
    actual = json.loads((output / "TwilightBossSliceB" / relative).read_bytes())
    expected = channel_fill()
    assert actual == expected
    assert {p: p.read_bytes() for p in bp.rglob("*.json")} == before
def test_all_land_only_small_ruins_have_guard_but_natural_logs_are_excluded():
    assert set(ruins.DRY_GROUND_RUINS) == {
        "monolith", "stone_circle", "well", "foundation", "druid_hut",
        "outside_stalagmite", "grove_ruins"}
    outer = ruins._scatter_feature("tf_slice:monolith_scatter_feature",
                                   "tf_slice:monolith_structure_selector_feature", 90, 2, 2)
    body = outer["minecraft:scatter_feature"]
    assert body["scatter_chance"]["denominator"] == 90
    assert body["places_feature"] == "tf_slice:monolith_dry_ground_feature"
