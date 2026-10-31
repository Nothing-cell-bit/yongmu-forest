"""Upstream fixtures and real generated/packaged definitions, not timing claims."""
from pathlib import Path
import copy
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mining_contract_test', ROOT / 'tools/block_mining_contract.py')
mining = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mining)


def test_current_pack_meets_mining_contract():
    assert mining.mining_issues(ROOT / 'TwilightBossSliceB') == []


def test_independent_locked_source_values_and_aliases():
    rows = mining.contract()['blocks']
    # Literal independent values from locked TFBlocks and Trophy constructors.
    for name in ('mazestone', 'mazestone_brick', 'mossy_mazestone', 'cut_mazestone', 'decorative_mazestone', 'cracked_mazestone', 'mazestone_border', 'mazestone_mosaic'):
        assert rows['tf_slice:' + name]['hardness'] == 100.0
        assert rows['tf_slice:' + name]['tier'] == {'digger': 'pickaxe', 'destroy_special': True, 'level': 3}
    assert rows['tf_slice:canopy_bookshelf']['hardness'] == 1.5
    assert rows['tf_slice:canopy_chest']['hardness'] == 2.5
    assert rows['tf_slice:temporary_builder_block']['hardness'] == 50
    assert rows['tf_slice:temporary_builder_block']['no_mining_drop'] is True
    assert rows['tf_slice:carminite_antibuilder']['upstream'] == 'twilightforest:antibuilder'
    assert rows['tf_slice:tower_key_door']['hardness'] == -1
    assert rows['tf_slice:root_block']['upstream'] == 'twilightforest:root'
    trophies = [r for name, r in rows.items() if name.endswith('_trophy')]
    assert len(trophies) == 14
    assert all(r['hardness'] == 0 and r['cracks'] == 'not_applicable_instant' for r in trophies)


def test_real_writer_fixes_old_values_and_hidden_override_without_render_changes(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / 'tools'))
    import build_public_block_shapes as builder
    original = json.loads((ROOT / 'TwilightBossSliceB/netease_blocks/canopy_bookshelf.json').read_text('utf-8'))
    original['minecraft:block']['components']['minecraft:destroy_time'] = {'value': 2.0}
    original['minecraft:block']['permutations'] = [{'condition': 'query.block_state("tf_slice:test") == 1',
                                                 'components': {'minecraft:destroy_time': {'value': 9},
                                                                'netease:render_layer': {'value': 'opaque'}}}]
    before = copy.deepcopy(original)
    path = tmp_path / 'TwilightBossSliceB/netease_blocks/canopy_bookshelf.json'
    builder.write_json(path, original)
    result = json.loads(path.read_text('utf-8'))['minecraft:block']
    assert result['components']['minecraft:destroy_time'] == {'value': 1.5}
    assert result['components']['netease:tier']['digger'] == 'hatchet'
    assert result['components']['netease:tier']['destroy_special'] is False
    assert result['permutations'][0]['components']['minecraft:destroy_time'] == {'value': 1.5}
    assert result['permutations'][0]['components']['netease:render_layer'] == {'value': 'opaque'}
    assert result['components']['minecraft:explosion_resistance'] == before['minecraft:block']['components']['minecraft:explosion_resistance']
    assert original == before


def test_tools_keep_damage_durability_and_specialize_only_source_tag():
    path = ROOT / 'TwilightBossSliceB/items/mazebreaker_pickaxe.item.json'
    old = json.loads(path.read_text('utf-8'))
    fixed = mining.normalize(path, old)
    components = fixed['minecraft:item']['components']
    assert components['netease:weapon']['level'] == 3
    assert components['netease:weapon']['attack_damage'] == 0
    assert components['minecraft:damage'] == old['minecraft:item']['components']['minecraft:damage']
    assert components['minecraft:durability'] == old['minecraft:item']['components']['minecraft:durability']
    speeds = components['minecraft:digger']['destroy_speeds']
    assert len(speeds) == 8
    assert all(v['speed'] == 128 and 'mazestone' in v['block'] for v in speeds)
    assert components['minecraft:digger']['use_efficiency'] is True


def test_every_sustained_block_uses_an_engine_owned_render_path():
    bp = ROOT / 'TwilightBossSliceB'
    rp = ROOT / 'TwilightBossSliceR'
    clients = json.loads((rp / 'blocks.json').read_text('utf-8'))
    # The engine supplies this built-in cube; it has no pack-owned model JSON.
    geometry = {'minecraft:geometry.full_block'}
    netease = set()
    for path in (rp / 'models').rglob('*.json'):
        doc = json.loads(path.read_text('utf-8'))
        for model in doc.get('minecraft:geometry', []):
            geometry.add(model['description']['identifier'])
        if 'netease:block_geometry' in doc:
            netease.add(doc['netease:block_geometry']['description']['identifier'])
    for path in (bp / 'netease_blocks').glob('*.json'):
        doc = json.loads(path.read_text('utf-8'))['minecraft:block']
        identifier = doc['description']['identifier']
        rule = mining.contract()['blocks'][identifier]
        if rule['hardness'] <= 0:
            continue
        components = doc['components']
        for values in [components] + [{**components, **p.get('components', {})} for p in doc.get('permutations', [])]:
            if 'minecraft:geometry' in values:
                value = values['minecraft:geometry']
                assert (value['identifier'] if isinstance(value, dict) else value) in geometry
        client = clients[identifier]
        if 'netease_model' in client:
            assert client['netease_model'] in netease
        # The only independent visible trophy bodies are now instant-break.
        assert identifier not in ('tf_slice:ur_ghast_trophy', 'tf_slice:ur_ghast_wall_trophy')


def test_all_resolvable_hardness_values_match_locked_java_not_the_writer():
    import re
    import subprocess
    lock = mining.contract()
    text = subprocess.run(['git', '-C', str(ROOT.parent / 'tf-source-1.20.1'), 'show',
                           lock['upstream_commit'] + ':src/main/java/twilightforest/init/TFBlocks.java'],
                          capture_output=True, text=True, check=True).stdout
    symbols, registrations = {}, {}
    for line in text.splitlines():
        symbol = re.search(r'\b([A-Z][A-Z0-9_]*)\s*=', line)
        if symbol:
            symbols[symbol[1]] = line
        name = re.search(r'register\w*\("([a-z0-9_]+)"', line)
        if name:
            registrations[name[1]] = line
    def hardness(line):
        explicit = re.findall(r'\.strength\((-?[0-9.]+)[fF]?', line)
        if explicit:
            return float(explicit[-1])
        if '.instabreak()' in line or 'new TrophyBlock(' in line or 'new TrophyWallBlock(' in line:
            return 0.0
        reference = re.search(r'\.copy\(([A-Z][A-Z0-9_]*)\.get\(\)\)', line)
        if reference:
            return hardness(symbols[reference[1]])
        prop = re.search(r'\b([A-Z][A-Z0-9_]*_PROPS)\b', line.split('=', 1)[-1])
        if prop:
            return hardness(symbols[prop[1]])
        raise AssertionError('Unresolved independent upstream expression: ' + line)
    compared = 0
    for identifier, value in lock['blocks'].items():
        if value['upstream'].startswith('twilightforest:'):
            name = value['upstream'].split(':', 1)[1]
            assert value['hardness'] == hardness(registrations[name]), identifier
            compared += 1
    assert compared == 163
    assert lock['blocks']['tf_slice:landmark_protected_grass']['hardness'] == 0.6
    assert lock['blocks']['tf_slice:maze_slime_block']['hardness'] == 0
    assert lock['blocks']['tf_slice:restored_block']['upstream'].startswith('project:')


def test_archive_checker_rejects_the_actual_old_submission_package():
    import importlib.util
    spec = importlib.util.spec_from_file_location('mining_archive_guard', ROOT / 'tools/check_block_mining.py')
    guard = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, str(ROOT / 'tools'))
    spec.loader.exec_module(guard)
    old = ROOT / 'dist/twilight_forest_0.12.0_new_uuid_20261019_193376d0.zip'
    result = guard.check(old)
    assert result['status'] == 'needs_attention'
    assert any(v.get('id') == 'tf_slice:mazestone' and v.get('field') == 'minecraft:destroy_time'
               for v in result['issues'])
    assert any(v.get('id') == 'mining_tool_rules' for v in result['issues'])


def test_boolean_hardness_and_low_tier_are_rejected_in_real_pack_reader(tmp_path):
    import shutil
    bp = tmp_path / 'TwilightBossSliceB'
    shutil.copytree(ROOT / 'TwilightBossSliceB/netease_blocks', bp / 'netease_blocks')
    shutil.copytree(ROOT / 'TwilightBossSliceB/items', bp / 'items')
    for relative in (mining.EMPTY_LOOT, 'TwilightBossSlice/mining_tool_rules.py'):
        target = bp / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'TwilightBossSliceB' / relative, target)
    path = bp / 'netease_blocks/fallen_leaves.json'
    doc = json.loads(path.read_text('utf-8'))
    doc['minecraft:block']['components']['minecraft:destructible_by_mining']['seconds_to_destroy'] = False
    path.write_text(json.dumps(doc), encoding='utf-8')
    stone = bp / 'netease_blocks/mazestone.json'
    doc = json.loads(stone.read_text('utf-8'))
    doc['minecraft:block']['components']['netease:tier']['level'] = 2
    stone.write_text(json.dumps(doc), encoding='utf-8')
    issues = mining.mining_issues(bp)
    assert any(v.get('id') == 'tf_slice:fallen_leaves' and 'boolean' in v.get('reason', '') for v in issues)
    assert any(v.get('id') == 'tf_slice:mazestone' and v.get('field') == 'netease:tier' for v in issues)
