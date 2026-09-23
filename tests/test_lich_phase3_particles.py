"""Exercise the third-phase emitter and reject the observed log flood."""
import json
import os
import random
import re
from pathlib import Path
from types import SimpleNamespace
from tests.test_lich_effect_runtime import harness

ROOT=Path(__file__).resolve().parents[1]


def test_third_phase_emits_twenty_self_contained_particles_per_second():
    path=Path(os.environ.get('LICH_TEST_CLIENT',str(ROOT/'TwilightBossSliceB/TwilightBossSlice/clientSystem.py')))
    text=path.read_text('utf-8')
    method=re.search(r'^    def _update_lich_state_effects\(.*?(?=^    def |\Z)',text,re.M|re.S).group()
    ns=dict(random=random,LEVEL_ID='level',CF=SimpleNamespace(
        CreateGame=lambda _:SimpleNamespace(GetCurrentDimension=lambda:0),
        CreatePos=lambda _:SimpleNamespace(GetFootPos=lambda:(0,64,0))))
    exec('class Client:\n'+method,ns)
    client=ns['Client']();client._lich_effect_tick=0
    client._update_fortification_visuals=lambda _:None
    client._lich_projectile_trails={}
    client._bosses={'boss':dict(kind='lich',dimensionId=0,phase=3,attackCooldown=0)}
    emitted=[]
    client._spawn_naga_state_particle=lambda name,*a:emitted.append(name)
    for _ in range(30):client._update_lich_state_effects()
    assert emitted==['tf_slice:lich_angry']*20
    client._bosses['boss']['phase']=2
    for _ in range(30):client._update_lich_state_effects()
    assert len(emitted)==20


def test_angry_emitter_is_bounded_and_needs_no_engine_variables():
    p=ROOT/'TwilightBossSliceR/particles/lich_angry.json'
    d=json.loads(p.read_text('utf-8'))['particle_effect']
    assert d['description']['identifier']=='tf_slice:lich_angry'
    c=d['components']
    assert c['minecraft:emitter_rate_instant']['num_particles']==1
    assert 0<c['minecraft:emitter_lifetime_once']['active_time']<=0.1
    assert c['minecraft:particle_lifetime_expression']['max_lifetime']<=1.5
    assert c['minecraft:emitter_shape_point']['direction']==[0,0.1,0]
    assert 'variable.direction' not in json.dumps(d)
    assert c['minecraft:particle_appearance_billboard']['uv']['uv']==[8,40]


def test_zero_damage_flood_never_writes_diagnostics():
    host,state=harness();writes=[]
    host._entry_trace=lambda *a,**kw:writes.append(a)
    for _ in range(3600):
        host.OnActorHurtServerEvent(dict(entityId='boss',damage=0,cause='none'))
    assert not writes
    assert state['shieldStrength']==6
    host.OnActorHurtServerEvent(dict(entityId='boss',damage=3,cause='entity_attack'))
    assert len(writes)==1


def test_source_projectile_trails_keep_motion_readable_without_particle_wall():
    path=Path(os.environ.get('LICH_TEST_CLIENT',str(ROOT/'TwilightBossSliceB/TwilightBossSlice/clientSystem.py')))
    text=path.read_text('utf-8')
    method=re.search(r'^    def _update_lich_state_effects\(.*?(?=^    def |\Z)',text,re.M|re.S).group()
    ns=dict(random=random,LEVEL_ID='level',CF=SimpleNamespace(
        CreateGame=lambda _:SimpleNamespace(GetCurrentDimension=lambda:0),
        CreatePos=lambda _:SimpleNamespace(GetFootPos=lambda:(0,64,0))))
    exec('class Client:\n'+method,ns)
    client=ns['Client']();client._lich_effect_tick=0
    client._update_fortification_visuals=lambda _:None
    client._bosses={}
    emitted=[]
    client._spawn_naga_state_particle=lambda name,*a:emitted.append(name)
    client._lich_projectile_trails={
        'bolt':dict(expires=100,missing=0,style='tf_slice:lich_bolt'),
        'bomb':dict(expires=100,missing=0,style='tf_slice:lich_bomb')}
    for _ in range(30):client._update_lich_state_effects()
    assert emitted.count('tf_slice:lich_ominous_flame') == 30
