"""Independent native-preset fixture plus minimal-change deployment contract."""
import copy
import json
from pathlib import Path
import subprocess
import sys

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import build_stream_depth_candidate as builder


def stream():
    return {"format_version": "1.14.0", "minecraft:biome": {
        "description": {"identifier": "dm33027004_river", "inherits": "river"},
        "components": {"minecraft:overworld_height": {"noise_params": [-0.1, 0.0]},
                       "minecraft:surface_parameters": {"sea_material": "minecraft:water",
                                                        "sea_floor_depth": 5},
                       "dm33027004": {}, "tf_slice_biome_stream": {},
                       "minecraft:climate": {"temperature": 0.5}}}}


def native():
    return {"minecraft:biome": {"description": {"identifier": "minecraft:river"},
            "components": {"minecraft:overworld_height": {"noise_type": "river"}}}}


def test_removes_shallow_override_and_changes_only_height():
    original = stream()
    frozen = copy.deepcopy(original)
    actual = builder.build_candidate(original, native())
    components = actual["minecraft:biome"]["components"]
    assert components["minecraft:overworld_height"] == {"noise_type": "river"}
    assert "noise_params" not in components["minecraft:overworld_height"]
    components["minecraft:overworld_height"] = {"noise_params": [-0.1, 0.0]}
    assert actual == frozen and original == frozen


def test_rejects_wrong_native_biome_and_unreviewed_source():
    import pytest
    wrong = native()
    wrong["minecraft:biome"]["description"]["identifier"] = "minecraft:ocean"
    with pytest.raises(ValueError):
        builder.build_candidate(stream(), wrong)
    wrong = stream()
    wrong["minecraft:biome"]["components"]["minecraft:overworld_height"]["noise_params"] = [-1.65, 0.25]
    with pytest.raises(ValueError):
        builder.build_candidate(wrong, native())


def test_idempotent_and_cannot_inherit_new_native_components():
    donor = native()
    donor["minecraft:biome"]["components"]["unrelated"] = {"doNotCopy": True}
    first = builder.build_candidate(stream(), donor)
    assert builder.build_candidate(first, donor) == first
    assert "unrelated" not in first["minecraft:biome"]["components"]


def test_cli_emits_only_selected_biome_and_provenance(tmp_path):
    source, donor, output = [tmp_path / name for name in ("source.json", "native.json", "out.json")]
    source.write_text(json.dumps(stream()))
    donor.write_text(json.dumps(native()))
    report = tmp_path / "report.json"
    result = subprocess.run([sys.executable, str(TOOLS / "build_stream_depth_candidate.py"),
                             "--source", str(source), "--native-river", str(donor),
                             "--output", str(output), "--report", str(report)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == builder.build_candidate(stream(), native())
    assert json.loads(report.read_text())["runtimeAcceptance"] == "pending"


def native_ocean():
    donor = native()
    donor["minecraft:biome"]["description"]["identifier"] = "minecraft:ocean"
    donor["minecraft:biome"]["components"]["minecraft:overworld_height"] = {"noise_type": "ocean"}
    donor["minecraft:biome"]["components"]["minecraft:climate"] = {"temperature": -99}
    return donor


def test_explicit_lower_native_profile_changes_only_height_and_keeps_channel():
    original = stream()
    original["minecraft:biome"]["components"]["minecraft:overworld_height"] = {"noise_type": "river"}
    original["minecraft:biome"]["components"]["netease:overworld_surface"] = {
        "adjustments": [{"type": "fill", "min_height": 61, "max_height": 63,
                         "pool": [{"fill_block": "minecraft:water", "weight": 1}]}]}
    before = copy.deepcopy(original)
    actual = builder.build_candidate(original, native_ocean(), preset="ocean")
    expected = copy.deepcopy(before)
    expected["minecraft:biome"]["components"]["minecraft:overworld_height"] = {"noise_type": "ocean"}
    assert actual == expected and original == before
    assert builder.build_candidate(actual, native_ocean(), preset="ocean") == actual


def test_explicit_profile_rejects_wrong_donor_and_unknown_profile():
    import pytest
    with pytest.raises(ValueError):
        builder.build_candidate(stream(), native(), preset="ocean")
    with pytest.raises(ValueError):
        builder.build_candidate(stream(), native_ocean(), preset="deep_ocean")


def test_cli_explicit_profile_preserves_provenance_and_remains_candidate(tmp_path):
    source, donor, output = [tmp_path / n for n in ("source.json", "donor.json", "out.json")]
    source.write_text(json.dumps(stream()))
    donor.write_text(json.dumps(native_ocean()))
    report = tmp_path / "report.json"
    run = subprocess.run([sys.executable, str(TOOLS / "build_stream_depth_candidate.py"),
        "--source", str(source), "--native-biome", str(donor), "--profile", "ocean",
        "--output", str(output), "--report", str(report)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    saved = json.loads(report.read_bytes())
    assert saved["nativePreset"] == "ocean"
    assert saved["fixedWaterDepth"] is None and saved["runtimeAcceptance"] == "pending"
