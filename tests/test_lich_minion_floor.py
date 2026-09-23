"""The requested arena-floor rule, independent of upstream spawn behavior."""
import math
import os
import random
import re
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]


def harness():
    source=Path(os.environ.get('LICH_TEST_SERVER', str(ROOT/'TwilightBossSliceB/TwilightBossSlice/serverSystem.py'))).read_text('utf-8')
    names=['_lich_minion_floor_clear','_find_lich_minion_destination',
           '_keep_lich_minion_on_floor','_lich_minion_target_on_floor',
           '_spawn_lich_minion']
    methods=[]
    for name in names:
        m=re.search(r'^    def '+name+r'\(.*?(?=^    def |\Z)',source,re.M|re.S)
        if m: methods.append(m.group())
    writes=[]
    ns=dict(math=math,random=random,LICH_MINION_IDENTIFIER='tf_slice:lich_minion',
        CF=SimpleNamespace(CreatePos=lambda entity:SimpleNamespace(
            SetFootPos=lambda pos:writes.append((entity,pos)) or True)))
    exec('class Host:\n'+''.join(methods),ns)
    host=ns['Host'](); host._tick=100; host._lich_minions={}
    host._block_name=lambda block:block['name'] if block else None
    host._get_block=lambda pos,dim:dict(name='minecraft:glass' if pos[1]==63 else 'minecraft:air')
    host._lich_positions_can_see=lambda *a:True
    host._get_foot_pos=lambda entity: (0.5,64,0.5)
    host._find_lich_destination=lambda state,target:target
    host._set_full_motion=lambda *a:None
    host._reset_attack_target=lambda *a:None
    host._set_attack_target=lambda *a:None
    host._entry_trace=lambda *a,**kw:None
    host._play_world_sound=lambda *a:None
    host._broadcast_lich_effect=lambda *a:None
    host._save_lich_dependent_state=lambda *a:None
    host._spawn_ruin_entity=lambda *a:'spawned'
    state=dict(home=(0.5,64,0.5),dimensionId=0,targetId='player',
               activeMinions=1,minionsRemaining=8,minionIds=set())
    return host,state,writes


def test_spawns_on_arena_floor_even_when_player_is_downstairs():
    host,state,_=harness()
    host._get_foot_pos=lambda _: (0.5,54,0.5)
    spawned=[]
    host._spawn_ruin_entity=lambda kind,pos,*a: spawned.append(pos) or 'spawned'
    host._spawn_lich_minion('boss',state,'player')
    assert spawned and spawned[0][1]==64


def test_full_support_and_empty_headroom_are_required():
    host,_,_=harness()
    pos=(2.9,64,2.9)
    assert host._lich_minion_floor_clear(pos,0)
    for hazard in ['minecraft:air','minecraft:water','minecraft:lava',None]:
        host._get_block=lambda p,d: None if hazard is None else dict(name=(hazard if p[1]==63 and p[0]==3 else 'minecraft:glass' if p[1]==63 else 'minecraft:air'))
        assert not host._lich_minion_floor_clear(pos,0)
    host._get_block=lambda p,d:dict(name='minecraft:stone')
    assert not host._lich_minion_floor_clear(pos,0)


def test_no_safe_upper_floor_never_falls_back_downstairs():
    host,state,_=harness()
    host._get_block=lambda p,d:dict(name='minecraft:stone' if p[1]==53 else 'minecraft:air')
    assert host._find_lich_minion_destination(state) is None
    host._spawn_lich_minion('boss',state,'player')
    assert state['minionsRemaining']==9  # refunded failed reservation
    assert state['activeMinions']==0


def test_fallen_minion_returns_without_replacement_or_budget_change():
    host,state,writes=harness()
    host._get_foot_pos=lambda _: (0.5,59,0.5)
    minion=dict(health=7,ownerId='boss')
    host._keep_lich_minion_on_floor('minion',minion,state)
    assert len(writes)==1 and writes[0][0]=='minion' and writes[0][1][1]==64
    assert minion['health']==7 and state['minionsRemaining']==8


def test_normal_jumps_do_not_trigger_recovery_and_lower_targets_are_ignored():
    host,state,writes=harness()
    host._get_foot_pos=lambda _: (0.5,65,0.5)
    host._keep_lich_minion_on_floor('minion',{},state)
    assert not writes
    assert host._lich_minion_target_on_floor('player',state)
    host._get_foot_pos=lambda _: (0.5,54,0.5)
    assert not host._lich_minion_target_on_floor('player',state)


def test_failed_recovery_is_throttled():
    host,state,writes=harness()
    host._get_foot_pos=lambda _: (0.5,59,0.5)
    attempts=[]
    host._find_lich_minion_destination=lambda _:attempts.append(True)
    minion={}
    for tick in range(100,120):
        host._tick=tick
        host._keep_lich_minion_on_floor('minion',minion,state)
    assert len(attempts)==1 and not writes
