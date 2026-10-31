import sys
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import forest_tree_parity as parity

def test_counts_and_selector_match_locked_upstream_resources():
    lock = json.loads((ROOT / 'source_locks/forest_tree_parity_4_3_2508.json').read_text())
    assert lock['jar_sha256'] == '0bdc89263616d1b35c32ef82c5e9c14cbd20368e2fe8b468c72a28320be7a778'
    config = lock['resources']['data/twilightforest/worldgen/configured_feature/tree/selector/firefly_forest_trees.json']['config']
    p1, p2 = [entry['chance'] for entry in config['features']]
    weights = parity.feature_documents()['firefly_canopy_selector_feature.json']['minecraft:weighted_random_feature']['features']
    assert weights[0][1] / sum(x[1] for x in weights) == pytest.approx(p1 + (1 - p1) * p2)
    for biome, placements in parity.TREE_PLACEMENTS.items():
        source_biome = lock['resources']['data/twilightforest/worldgen/biome/' + biome + '.json']
        expected = []
        for name in [f for group in source_biome['features'] for f in group if 'tree/' in f and not f.endswith('hollow_oak')]:
            source = lock['resources']['data/twilightforest/worldgen/placed_feature/' + name.split(':')[1] + '.json']
            count = next((x['count'] for x in source['placement'] if x['type'] == 'minecraft:count'), 1)
            if isinstance(count, dict):
                distribution = count['distribution']
                count = sum(x['data'] * x['weight'] for x in distribution) / sum(x['weight'] for x in distribution)
            expected.append(count)
        assert [base + (0.1 if extra else 0.0) for _, base, extra in placements] == pytest.approx(expected)

def test_dense_forest_has_three_independent_tree_placements():
    assert parity.TREE_PLACEMENTS['dense_forest'] == (
        ('dense_canopy_selector_feature', 5, True),
        ('twilight_tree_mix_selector_feature', 1, False),
        ('forest_canopy_oak_selector_feature', 7, True),
    )

def test_firefly_has_independent_vanilla_and_oak_placements():
    assert parity.TREE_PLACEMENTS['firefly_forest'] == (
        ('firefly_canopy_selector_feature', 3, True),
        ('twilight_tree_mix_selector_feature', 1, False),
        ('twilight_oak_tree_feature', 1, True),
        ('large_twilight_oak_tree_feature', 1, True),
    )

def test_selectors_resolve_sequential_upstream_chances():
    docs = parity.feature_documents()
    assert docs['dense_canopy_selector_feature.json']['minecraft:weighted_random_feature']['features'] == [
        ['tf_slice:canopy_tree_source_shape_feature', 7], ['tf_slice:twilight_oak_tree_feature', 3]]
    assert docs['firefly_canopy_selector_feature.json']['minecraft:weighted_random_feature']['features'] == [
        ['tf_slice:canopy_tree_source_shape_feature', 1263], ['tf_slice:twilight_oak_tree_feature', 737]]

@pytest.mark.parametrize('savannah', [False, True])
@pytest.mark.parametrize('variant', range(4))
def test_canopy_oak_is_two_by_two_and_has_crown_and_branches(savannah, variant):
    structure, center, base = parity.canopy_oak_structure(variant, savannah)
    blocks = structure.blocks
    for x,z in [(center,center),(center+1,center),(center,center+1),(center+1,center+1)]:
        assert (x,base+8,z) in blocks
    assert any(x < center-2 or x > center+3 for x,y,z in blocks if y > base+8)
    assert max(y for x,y,z in blocks) >= base + (16 if savannah else 24)
    assert min(y for x,y,z in blocks) >= 0
    assert len(blocks) > 150

def test_rules_keep_dimension_biome_and_surface_projection():
    rules = parity.rule_documents()
    assert len(rules) == 10
    for name, document in rules.items():
        body = document['minecraft:feature_rules']
        assert body['conditions']['placement_pass'] == 'after_surface_pass'
        filters = body['conditions']['minecraft:biome_filter'][0]['all_of']
        assert filters[0]['value'] == 'dm33027004'
        assert filters[1]['value'].startswith('tf_slice_biome_')
        assert body['description']['places_feature'].endswith('_landmark_surface_project_feature')
        assert body['distribution']['y'].endswith(' + 64')

def test_real_writer_validates_registered_blocks_and_scoped_outputs(tmp_path):
    rules = tmp_path / 'TwilightBossSliceB/netease_feature_rules'
    rules.mkdir(parents=True)
    for name in parity.LEGACY_RULES:
        (rules / name).write_text('{}')
    (rules / 'unrelated.json').write_text('{"keep": true}')
    result = parity.build(tmp_path)
    assert result['structures'] == 8
    assert len(list((tmp_path / 'TwilightBossSliceB/structures').rglob('*.mcstructure'))) == 8
    assert (rules / 'unrelated.json').read_text() == '{"keep": true}'
    assert not any((rules / name).exists() for name in parity.LEGACY_RULES)
