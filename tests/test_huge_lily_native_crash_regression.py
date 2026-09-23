"""Prevent the native structure transaction that crashed Streaming Pool."""
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_swamp_features as swamp
import worldgen_probe_repairs as repair


def test_huge_lily_generator_uses_block_feature_after_clearance_checks():
    documents, clearances = swamp.huge_lily_pad_clearance_documents(
        ["minecraft:water", "minecraft:flowing_water"]
    )
    assert len(clearances) == 9
    assert "huge_lily_pad_clearance_block_feature.json" in documents
    sequence = swamp.huge_lily_pad_single_sequence_document(
        "huge_lily_pad_2x2_feature", clearances
    )["minecraft:sequence_feature"]["features"]
    assert sequence == ["tf_slice:" + name for name in clearances] + [
        "tf_slice:huge_lily_pad_feature"
    ]
    lily = json.loads(
        (ROOT / "TwilightBossSliceB/netease_features/huge_lily_pad_feature.json")
        .read_text(encoding="utf-8")
    )
    assert "minecraft:single_block_feature" in lily
    assert "netease:structure_feature" not in lily


def test_scoped_repair_cannot_reintroduce_lily_structure_handoff():
    files = repair.feature_documents()
    assert not any("huge_lily_pad" in name for name in files)
    assert repair.removed_features() == []
    source = (ROOT / "tools/worldgen_probe_repairs.py").read_text(encoding="utf-8")
    assert "huge_lily_pad_candidate" not in source
    assert "TOKEN_PATH" not in source


def test_only_the_bounded_lily_clearance_predicate_may_replace_air_with_air():
    broken = {
        "minecraft:single_block_feature": {
            "places_block": [{"block": "minecraft:air"}],
            "may_replace": ["minecraft:air"],
        }
    }
    assert repair.air_to_air_probes({"unrelated.json": broken}) == [
        "unrelated.json"
    ]
    assert repair.air_to_air_probes(
        {"huge_lily_pad_clearance_block_feature.json": broken}
    ) == []


def test_validator_rejects_transactional_huge_lily_structure():
    validator = (ROOT / "tools/validate_slice.py").read_text(encoding="utf-8")
    assert "huge_lily_pad_feature.json" in validator
    assert "netease:structure_feature" in validator
    assert "tf_slice:swamp/huge_lily_pad/candidate" in validator
