"""Execute production server methods with a controllable NetEase boundary."""
import math
import random
import sys
import types
import uuid
from pathlib import Path
from test_fortification_lifecycle_runtime import load_methods
from test_reward_delivery import Engine

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'TwilightBossSliceB/TwilightBossSlice'))
import reward_delivery
import quest_ram_logic


def host():
    names=['_queue_loot_reward','_place_naga_loot_chest','_place_lich_loot_chest',
        '_place_ur_ghast_reward','_place_knight_group_reward_chest',
        '_award_minoshroom_items','_drop_quest_ram_rewards']
    cls=load_methods('serverSystem.py',names,{'math':math,'random':random,
        'uuid':uuid,'reward_delivery':reward_delivery,'quest_ram_logic':quest_ram_logic,
        'config':types.SimpleNamespace(DIMENSION_ID=7,NAGA_LOOT_TABLE='naga.json',
            LICH_LOOT_TABLE='lich.json')})
    e=Engine();h=cls();q=e.queue();h._reward_queue=lambda:q
    h._get_foot_pos=lambda _: (1,2,3);h._get_dimension=lambda _:7
    h._quest_ram_state=lambda _: {'mask':65535,'rewarded':True}
    h._save_quest_ram_state=lambda *args:True
    return h,e,q


def test_naga_chest_retries_and_keeps_looting_bonus():
    h,e,q=host();e.chest_ok=False
    state={'home':(1,2,3),'dimensionId':7,'lastLootingLevel':3}
    assert h._place_naga_loot_chest(state)
    assert len(q.records)==1
    e.chest_ok=True;q.flush()
    assert len(e.chests)==1
    h._place_naga_loot_chest(state)
    assert len(e.chests)==1


def test_lich_queue_preserves_enchanted_table_even_when_chest_fails():
    h,e,q=host();e.chest_ok=False
    assert h._place_lich_loot_chest({'home':(1,3,3),'dimensionId':7,'lastLootingLevel':2})
    assert not e.items
    assert next(iter(q.records.values()))['table']=='lich.json'


def test_ur_ghast_uses_its_actual_dimension():
    h,e,q=host()
    assert h._place_ur_ghast_reward({'home':(1,2,3),'dimensionId':9,'lastLootingLevel':0})
    assert e.chests[0][1]==9


def test_minoshroom_chest_reward_needs_no_online_participant():
    h,e,q=host()
    assert h._award_minoshroom_items('boss',{'home':(1,2,3),'dimensionId':7,'participants':set()})
    q.flush(limit=30)
    assert len(e.chests)==1 and not e.items
    assert {row['newItemName'] for row in e.slots.values()}=={
        'tf_slice:meef_stroganoff','tf_slice:diamond_minotaur_axe','tf_slice:minoshroom_trophy_item'}


def test_minoshroom_chest_failure_and_repeated_death_do_not_double_reward():
    h,e,q=host();e.chest_ok=False
    state={'home':(1,2,3),'dimensionId':7,'lastLootingLevel':3}
    assert h._award_minoshroom_items('boss',state)
    assert not e.items and not e.slots
    e.chest_ok=True;q.flush(limit=30)
    delivered=dict(e.slots)
    h._award_minoshroom_items('boss',state);q.flush(limit=30)
    assert e.slots==delivered and len(e.chests)==1


def test_native_empty_chest_and_slot_write_use_correct_engine_arguments():
    calls=[]
    factory=types.SimpleNamespace(CreateItem=lambda level:types.SimpleNamespace(
        SpawnItemToContainer=lambda *args:calls.append((level,args)) or True))
    cls=load_methods('serverSystem.py',['_fill_reward_chest','_put_reward_chest_item'],
        {'CF':factory,'LEVEL_ID':'world'})
    h=cls();h._set_block=lambda *args:True
    # Empty itemized chests do not need a SetChestLootTable call.
    assert h._fill_reward_chest((1,2,3),7,'')
    soup={'newItemName':'tf_slice:meef_stroganoff','count':1}
    assert h._put_reward_chest_item(soup,7,(1,2,3),4)
    assert calls==[('world',(soup,4,(1,2,3),7))]
    h._set_block=lambda *args:False
    assert not h._fill_reward_chest((1,2,3),7,'')


def test_quest_uses_current_item_ids_and_retries_partial_failure():
    h,e,q=host();e.item_ok=False
    assert h._drop_quest_ram_rewards('ram')
    e.item_ok=True;q.flush(limit=20)
    assert {row[0]['newItemName'] for row in e.items}==set(quest_ram_logic.REWARD_ITEMS)


def test_looting_is_serialized_across_delayed_boss_death():
    import lich_logic
    state=lich_logic.new_lich_state();state['lastLootingLevel']=3
    assert lich_logic.restore_persistent_state(lich_logic.serialize_persistent_state(state))['lastLootingLevel']==3
