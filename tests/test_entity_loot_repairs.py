"""Drop regressions derived from the locked 4.3.2508 loot resources."""
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / 'TwilightBossSliceB'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def entity(name):
    return read(BP / 'entities' / (name + '.entity.json'))['minecraft:entity']


def loot(name):
    return read(BP / 'loot_tables/entities' / (name + '.json'))


@pytest.mark.parametrize('name', ['tiny_bird', 'dwarf_rabbit', 'block_chain_goblin',
    'helmet_crab', 'lower_goblin_knight', 'upper_goblin_knight', 'carminite_golem',
    'tower_broodling', 'tower_ghast', 'mini_ghast', 'towerwood_borer'])
def test_missing_mobs_have_live_loot_binding(name):
    table = entity(name)['components']['minecraft:loot']['table']
    assert read(BP / table)['pools']


@pytest.mark.parametrize('name,vanilla', [('king_spider','spider'),
    ('hedge_spider','spider'),('swarm_spider','spider'),('tower_broodling','spider'),
    ('fire_beetle','creeper'),('dwarf_rabbit','rabbit'),('rising_zombie','zombie'),
    ('tower_ghast','ghast'),('mini_ghast','ghast')])
def test_vanilla_inheritance_preserves_rare_and_special_kill_pools(name, vanilla):
    table = read(BP / entity(name)['components']['minecraft:loot']['table'])
    assert table == {'pools':[{'rolls':1,'entries':[{'type':'loot_table',
        'name':'loot_tables/entities/' + vanilla + '.json'}]}]}


def test_boss_summoned_ghast_overrides_normal_loot_with_empty_table():
    group = entity('mini_ghast')['component_groups']['tf_slice:boss_minion']
    assert read(BP / group['minecraft:loot']['table']) == {'pools':[]}


@pytest.mark.parametrize('name',['block_chain_goblin','lower_goblin_knight','upper_goblin_knight'])
def test_goblin_shards_not_ingots(name):
    pools = loot('tf_slice/' + name)['pools']
    assert len(pools) == 1
    entry = pools[0]['entries'][0]
    assert entry['name'] == 'tf_slice:armor_shard'
    assert entry['functions'][0]['count'] == {'min':0,'max':2}
    assert entry['functions'][1]['function'] == 'looting_enchant'
    assert len(pools[0]['entries']) == 1


def test_minotaur_rare_focus_does_not_duplicate_equipment_axe():
    pools = loot('minotaur')['pools']
    meat = pools[0]['entries'][0]
    assert meat['functions'][0]['count'] == 1
    assert {f['function'] for f in meat['functions']} == {'set_count','looting_enchant','furnace_smelt'}
    assert pools[1]['entries'][0]['name'] == 'tf_slice:maze_map_focus'
    assert pools[1]['conditions'] == [{'condition':'random_chance_with_looting',
        'chance':0.025,'looting_multiplier':0.01}]


def test_death_tome_has_independent_paper_books_and_rare_focus():
    pools = loot('tf_slice/death_tome')['pools']
    assert len(pools) == 3
    assert pools[0]['entries'][0]['functions'][0]['count'] == 3
    assert {e['name'] for e in pools[1]['entries']} == {'minecraft:writable_book',
        'minecraft:book','loot_tables/entities/tf_slice/death_tome_books.json'}
    assert pools[2]['entries'][0]['name'] == 'tf_slice:magic_map_focus'
    assert {'condition':'killed_by_player'} in pools[2]['conditions']


def test_maze_slime_has_charm_and_single_base_ball():
    pools = loot('maze_slime')['pools']
    assert pools[0]['entries'][0]['functions'][0]['count'] == 1
    assert pools[1]['entries'][0]['name'] == 'tf_slice:charm_of_keeping_1'
    assert pools[1]['conditions'][0]['chance'] == 0.015


def test_knight_rewards_retain_original_enchantment_levels():
    pools = read(BP/'loot_tables/chests/tf_slice/stronghold_boss.json')['pools']
    for pool,level in zip(pools,[20,20,30]):
        for entry in pool['entries']:
            assert entry['functions'] == [{'function':'enchant_with_levels','levels':level,'treasure':False}]


@pytest.mark.parametrize('name',['bighorn_sheep','boar','deer'])
def test_babies_cannot_inherit_adult_death_rewards(name):
    baby = entity(name)['component_groups']['tf_slice:baby']
    assert read(BP / baby['minecraft:loot']['table']) == {'pools':[]}


def test_quest_reward_script_and_table_share_current_ids():
    import sys
    sys.path.insert(0,str(BP/'TwilightBossSlice'))
    import quest_ram_logic
    names = [p['entries'][0]['name'] for p in loot('questing_ram_rewards')['pools']]
    assert list(quest_ram_logic.REWARD_ITEMS) == names
    assert 'tf_slice:quest_ram_trophy_item' in names
    assert 'minecraft:redstone_block' not in names


def test_borer_essence_has_item_icon_and_localized_names():
    item = read(BP/'items/borer_essence.item.json')['minecraft:item']
    assert item['description']['identifier'] == 'tf_slice:borer_essence'
    rp = ROOT/'TwilightBossSliceR'
    atlas = read(rp/'textures/item_texture.json')['texture_data']
    assert (rp/(atlas['tf_slice:borer_essence']['textures']+'.png')).is_file()
    for language in ['en_US','zh_CN']:
        assert 'item.tf_slice:borer_essence.name=' in (rp/'texts'/(language+'.lang')).read_text(encoding='utf-8')


@pytest.mark.parametrize('name,slot',[('knightmetal_sword','sword'),
    ('knightmetal_pickaxe','pickaxe'),('knightmetal_axe','axe')])
def test_knight_weapons_can_receive_the_loot_table_enchantments(name,slot):
    c=read(BP/'items'/(name+'.item.json'))['minecraft:item']['components']
    assert c['minecraft:enchantable']=={'slot':slot,'value':8}


def test_bighorn_colored_and_sheared_wool_rewards():
    e=entity('bighorn_sheep')
    rolls=e['events']['minecraft:entity_spawned']['sequence'][1]['randomize']
    assert sorted(v['weight'] for v in rolls)==[1]*15+[17]
    assert loot('bighorn_sheep')['pools'][0]['entries'][0]['functions']==[
        {'function':'minecraft:set_data_from_color_index'}]
    sheared=e['component_groups']['tf_slice:sheared']['minecraft:loot']['table']
    assert read(BP/sheared)['pools']==loot('bighorn_sheep')['pools'][1:]
    assert 'minecraft:interact' in e['components']
