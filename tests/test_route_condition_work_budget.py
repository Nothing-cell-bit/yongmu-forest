import json
from pathlib import Path
import subprocess

from tools import build_dark_forest_biomes as builder

ROOT = Path(__file__).resolve().parents[1]


def test_real_emitted_conditions_preserve_old_results_and_skip_unneeded_waves():
    old = json.loads((ROOT / 'tests/fixtures/route_condition_0122.json').read_text('utf8'))['conditions']
    source = builder.dimension_document()['netease:dimension_info']['components']['netease:biome_source']
    new = [v['condition'] for v in source if v['type'] == 'condition']
    assert len(old) == len(new) == 8
    assert old[:4] == new[:4]  # No seed, variant, geometry or zoom policy changes.
    completed = subprocess.run(['node', str(ROOT / 'tests/fixtures/evaluate_route_conditions.js')],
                               input=json.dumps({'before': old, 'after': new}), text=True,
                               capture_output=True, check=True)
    result = json.loads(completed.stdout)
    assert result['checked'] > 900000
    assert result['after_sin_calls'] < result['before_sin_calls'] * 0.2, result


def test_dimension_artifact_matches_generator_and_keeps_all_transition_rules():
    actual = json.loads((ROOT / 'TwilightBossSliceB/netease_dimension/dm33027004.json').read_text('utf8'))
    assert actual == builder.dimension_document()
    stages = actual['netease:dimension_info']['components']['netease:biome_source']
    assert sum(v['type'] == 'transition' for v in stages) == 38
    assert sum(v['type'] == 'condition' for v in stages) == 8
    assert 'get_neighborhood_is_biome' not in json.dumps(stages)
