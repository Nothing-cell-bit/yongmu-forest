"""Regressions for the user's displaced shelf and vanilla axe feedback."""
import copy
import json
from pathlib import Path

import pytest

from tools import build_public_block_shapes as builder
from tools import block_mining_contract as mining
from tools import upstream_mining_tags as tags
from tools import check_public_block_models as model_guard

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name', [
    'canopy_log', 'canopy_log_x', 'canopy_log_z', 'canopy_planks', 'canopy_wood',
    'dark_log', 'dark_log_vertical', 'dark_planks', 'dark_wood',
    'mangrove_log', 'mangrove_log_x', 'mangrove_log_z', 'mangrove_planks', 'mangrove_wood',
    'stripped_canopy_log', 'stripped_canopy_wood', 'stripped_dark_log', 'stripped_dark_wood',
    'stripped_mangrove_log', 'stripped_mangrove_wood', 'twilight_oak_log',
    'twilight_oak_log_x', 'twilight_oak_log_z', 'canopy_fence', 'encased_towerwood',
])
def test_vanilla_axe_accelerates_all_sustained_wood_aliases(name):
    # Java 1.20.1 mineable/axe includes logs, planks and wooden_fences;
    # TF contributes these blocks to those vanilla tags, not its axe tag.
    doc = json.loads((ROOT / 'TwilightBossSliceB/netease_blocks' / (name + '.json')).read_text('utf8'))
    body = doc['minecraft:block']
    expected = {'digger': 'hatchet', 'destroy_special': False, 'level': 0}
    assert body['components'].get('netease:tier') == expected
    for permutation in body.get('permutations', []):
        assert {**body['components'], **permutation['components']}['netease:tier'] == expected


def test_exported_bookshelf_matches_the_selected_block_cell():
    doc = builder.canopy_netease_model_document('bookshelf', 'tf_slice:canopy_bookshelf_item')
    model = doc['netease:block_geometry']
    assert model['bones'][0]['pivot'] == [-8, 0, 8]
    assert model['bones'][0]['cubes'][0]['origin'] == [-16, 0, 0]
    assert model['bones'][0]['cubes'][0]['size'] == [16, 16, 16]
    actual = json.loads((ROOT / 'TwilightBossSliceR/models/netease_block/tf_slice_public_canopy_bookshelf.json').read_text('utf8'))
    assert actual == doc


def test_model_conversion_preserves_cube_bone_pivots_and_rotations():
    cube = builder.cube([-6, 2, -4], [4, 7, 3], rotation=[0, 30, 0], pivot=[-4, 3, -2])
    shape = builder.geometry('fixture', [], bones=[{'name': 'block', 'pivot': [1, 4, -2],
                                                  'rotation': [0, 90, 0], 'cubes': [cube]}])
    original = copy.deepcopy(shape)
    result = builder._netease_model_document('fixture', shape, ['fixture'], None)['netease:block_geometry']['bones'][0]
    assert result['pivot'] == [-7, 4, 6]
    assert result['cubes'][0]['origin'] == [-14, 2, 4]
    assert result['cubes'][0]['pivot'] == [-12, 3, 6]
    assert result['rotation'] == [0, 90, 0]
    assert result['cubes'][0]['rotation'] == [0, 30, 0]
    assert shape == original


def test_current_referenced_netease_models_are_in_the_engine_cell():
    rp = ROOT / 'TwilightBossSliceR'
    clients = json.loads((rp / 'blocks.json').read_text('utf8'))
    referenced = {v['netease_model'] for v in clients.values() if isinstance(v, dict) and 'netease_model' in v}
    for path in (rp / 'models/netease_block').glob('*.json'):
        model = json.loads(path.read_text('utf8'))['netease:block_geometry']
        if model['description']['identifier'] not in referenced:
            continue
        for bone in model['bones']:
            for cube in bone.get('cubes', []):
                assert -16 <= cube['origin'][0] <= cube['origin'][0] + cube['size'][0] <= 0, path.name
                assert 0 <= cube['origin'][2] <= cube['origin'][2] + cube['size'][2] <= 16, path.name


def test_source_check_rejects_the_previous_incomplete_contract():
    old = copy.deepcopy(mining.contract())
    old['blocks']['tf_slice:canopy_log_x']['tier'] = None
    issues = tags.contract_source_issues(old)
    assert any(row['id'] == 'tf_slice:canopy_log_x' and row['expected'] == 'hatchet' for row in issues)


def test_source_layers_merge_vanilla_parents_and_mod_children():
    tools, levels = tags.source_profiles()
    for name in ('canopy_log', 'canopy_planks', 'encased_towerwood', 'stripped_dark_wood'):
        assert 'twilightforest:' + name in tools['axe']
    assert 'twilightforest:mazestone' in tools['pickaxe']
    assert 'twilightforest:mazestone' in levels[3]
    assert 'twilightforest:mazestone' not in tools['axe']
    assert 'twilightforest:root_strand' not in tools['axe']


def test_tag_addition_replacement_optional_references_and_cycles():
    def layer(value):
        return {'tags': {'data/minecraft/tags/blocks/logs.json': value}}
    merged = tags.merge_layers([layer({'values': ['minecraft:oak_log']}),
                                layer({'values': ['twilightforest:canopy_log']})])
    assert tags.expand(merged, 'minecraft:logs') == {'minecraft:oak_log', 'twilightforest:canopy_log'}
    replaced = tags.merge_layers([layer({'values': ['old:log']}),
                                  layer({'replace': True, 'values': [{'id': 'new:log'},
                                                                    {'id': '#optional:missing', 'required': False}]})])
    assert tags.expand(replaced, 'minecraft:logs') == {'new:log'}
    with pytest.raises(ValueError, match='Missing required'):
        tags.expand({'root': ['#missing']}, 'root')
    with pytest.raises(ValueError, match='Cyclic'):
        tags.expand({'root': ['#child'], 'child': ['#root']}, 'root')


def test_reference_tampering_fails_closed(monkeypatch, tmp_path):
    path = tmp_path / 'tags.json'
    path.write_text('{}', encoding='utf8')
    tags.source_profiles.cache_clear()
    monkeypatch.setattr(tags, 'REFERENCE', path)
    try:
        with pytest.raises(ValueError, match='hash mismatch'):
            tags.source_profiles()
    finally:
        tags.source_profiles.cache_clear()


def test_source_and_actual_previous_zip_model_guard():
    assert model_guard.check(ROOT)['issues'] == []
    old = ROOT / 'dist/twilight_forest_0.12.1_mining_fixed_20261019_193376d0.zip'
    result = model_guard.check(old)
    assert result['status'] == 'needs_attention'
    assert any(v['id'] == 'tf_slice:public_canopy_bookshelf' and 'block cell' in v['reason'] for v in result['issues'])
    assert any('atlas alias' in v['reason'] for v in result['issues'])


def test_model_guard_rejects_missing_models_bad_alias_and_bad_coordinates():
    document = {'blocks.json': {'tf:fixture': {'netease_model': 'tf:missing'}},
                'models/netease_block/fixture.json': {
                    'netease:block_geometry': {'description': {'identifier': 'tf:fixture', 'item_texture': 'textures/blocks/invalid'},
                                              'bones': [{'cubes': [{'origin': [0, 0], 'size': [16, 16, 16]}]}]}}}
    issues = model_guard.inspect_documents(document)['issues']
    assert any('missing' in v['reason'] for v in issues)
    assert any('atlas alias' in v['reason'] for v in issues)
    assert any('invalid cube' in v['reason'] for v in issues)
