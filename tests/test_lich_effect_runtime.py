"""Execute production adapters with the SDK's real event field shapes."""
import random
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from TwilightBossSlice import lich_logic, entity_registry_logic
if os.environ.get('LICH_TEST_PACKAGE'):
    import importlib.util
    spec=importlib.util.spec_from_file_location('deployed_lich_logic',
        Path(os.environ['LICH_TEST_PACKAGE'])/'TwilightBossSlice/lich_logic.py')
    lich_logic=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lich_logic)


def harness():
    source = Path(os.environ.get('LICH_TEST_SERVER', str(
        ROOT / 'TwilightBossSliceB/TwilightBossSlice/serverSystem.py'))).read_text('utf-8')
    names = ['OnLichEffectDamage', 'OnActorHurtServerEvent',
             '_record_lich_effect_damage', '_consume_lich_effect_damage',
             '_sync_lich_presentation', '_refresh_lich_minions', 'OnHealthChangeBefore']
    methods = []
    for name in names:
        m = re.search(r'^    def '+name+r'\(.*?(?=^    def |\Z)', source, re.M|re.S)
        if m:
            methods.append(m.group())
    alive = {'minion': False}
    ns = dict(lich_logic=lich_logic, entity_registry_logic=entity_registry_logic,
              CF=SimpleNamespace(CreateGame=lambda _: SimpleNamespace(
                  IsEntityAlive=lambda entity: alive.get(entity))), LEVEL_ID='level')
    exec('class Host:\n'+''.join(methods), ns)
    host = ns['Host']()
    state = lich_logic.new_lich_state()
    state.update(minionIds={'minion'}, dimensionId=0)
    host._tick = 100
    host._recent_lich_effect_damage = {}
    host._lich_state = lambda _: state
    host._lich_minions = {'minion': {'ownerId':'boss'}}
    host._entry_trace = lambda *a, **kw: None
    host._get_foot_pos = lambda _: (0,0,0)
    host._play_world_sound = lambda *a: None
    host._broadcast_lich_effect = lambda *a: None
    host._save_lich_state = lambda *a: None
    host._set_health = lambda *a: None
    host._trigger_entity_event = lambda *a: True
    host._set_entity_carried_item = lambda *a: True
    return host, state


def test_healing_reported_as_recovery_breaks_one_shield_only():
    host, state = harness()
    host.OnLichEffectDamage(dict(entityId='boss', damage=-8,
        attributeBuffType=3, isInstantaneous=True, cause='magic'))
    assert state['shieldStrength'] == 5
    assert state['health'] == 100
    host.OnActorHurtServerEvent(dict(entityId='boss', damage=12, cause='magic'))
    assert state['shieldStrength'] == 5


def test_native_undead_healing_damage_and_weak_splash():
    host, state = harness()
    host.OnLichEffectDamage(dict(entityId='boss', damage=6,
        attributeBuffType=3, isInstantaneous=True, cause='magic'))
    assert state['shieldStrength'] == 5
    host.OnLichEffectDamage(dict(entityId='boss', damage=2,
        attributeBuffType=3, isInstantaneous=True, cause='magic'))
    assert state['shieldStrength'] == 5


def test_regeneration_and_harming_do_not_break_undead_shield():
    host, state = harness()
    for buff, amount in [(2,-1),(4,-6),(4,6)]:
        host.OnLichEffectDamage(dict(entityId='boss', damage=amount,
            attributeBuffType=buff, isInstantaneous=True, cause='magic'))
    assert state['shieldStrength'] == 6


def test_dead_minion_does_not_keep_phase_two_alive():
    host, state = harness()
    state.update(shieldStrength=0, minionsRemaining=0, activeMinions=1)
    host._refresh_lich_minions('boss', state)
    assert lich_logic.refresh_phase(state) == 3
    items=[]
    host._set_entity_carried_item=lambda entity,item: items.append(item) or True
    host._sync_lich_presentation('boss',state)
    assert items[-1]['newItemName'] == 'minecraft:golden_sword'
    actions=lich_logic.advance_combat_tick(state,1,True,random.Random(1))
    assert any(a['type']=='melee' for a in actions)


def test_failed_sword_equip_is_retried():
    host,state=harness()
    state.update(shieldStrength=0,minionsRemaining=0,activeMinions=0)
    host._set_entity_carried_item=lambda *a: False
    host._sync_lich_presentation('boss',state)
    assert state.get('visualWeapon') != 'minecraft:golden_sword'
    host._set_entity_carried_item=lambda *a: True
    host._sync_lich_presentation('boss',state)
    assert state['visualWeapon'] == 'minecraft:golden_sword'


def test_six_potions_then_exhausted_minions_reach_sword_stage():
    host,state=harness()
    for expected in range(5,-1,-1):
        host.OnLichEffectDamage(dict(entityId='boss', damage=-8,
            attributeBuffType=3, isInstantaneous=True, cause='magic'))
        assert state['shieldStrength'] == expected
        host._tick += 2
    assert state['phase'] == 2
    assert state['visualWeapon'] == 'tf_slice:zombie_scepter'
    state.update(minionsRemaining=0,activeMinions=1)
    host._refresh_lich_minions('boss',state)
    host._sync_lich_presentation('boss',state)
    assert state['phase'] == 3
    assert state['visualWeapon'] == 'minecraft:golden_sword'


def test_unavailable_minion_is_not_treated_as_dead():
    host,state=harness()
    state.update(minionIds={'unloaded'},activeMinions=1,
                 shieldStrength=0,minionsRemaining=0)
    host._refresh_lich_minions('boss',state)
    assert lich_logic.refresh_phase(state) == 2


def test_source_allows_kill_during_minion_phase():
    state=lich_logic.new_lich_state()
    state.update(shieldStrength=0,health=3,minionsRemaining=1,activeMinions=1)
    result=lich_logic.resolve_incoming_damage(state,'normal',10)
    assert result['healthDamage'] == 10
    assert state['health'] == 0
    assert state['phase'] == 2


def test_last_shield_recovery_does_not_leak_into_health():
    host,state=harness()
    state['shieldStrength']=1
    host.OnLichEffectDamage(dict(entityId='boss', damage=-8,
        attributeBuffType=3, isInstantaneous=True, cause='magic'))
    event=dict(entityId='boss',byScript=False,**{'from':90,'to':98})
    host.OnHealthChangeBefore(event)
    assert event['cancel'] is True
    assert state['shieldStrength']==0
    assert state['health']==100


def test_script_health_write_is_not_a_second_combat_hit():
    host,state=harness()
    event=dict(entityId='boss',byScript=True,**{'from':100,'to':90})
    host.OnHealthChangeBefore(event)
    assert 'cancel' not in event
    assert state['shieldStrength']==6


def test_minions_replenish_to_three_until_nine_successful_attempts():
    state=lich_logic.new_lich_state()
    state['shieldStrength']=0
    rng=random.Random(3)
    summoned=0
    for _ in range(400):
        actions=lich_logic.advance_combat_tick(state,10,True,rng)
        summoned += sum(a['type']=='spawn_minion' for a in actions)
    assert summoned==3 and state['activeMinions']==3
    assert state['minionsRemaining']==6
    # A minion downstairs still counts. Only its death releases a slot.
    for _ in range(6):
        lich_logic.minion_removed(state)
        for tick in range(80):
            actions=lich_logic.advance_combat_tick(state,10,True,rng)
            if any(a['type']=='spawn_minion' for a in actions):
                summoned+=1
                break
        else:
            raise AssertionError('freed minion slot was not replenished')
    assert summoned==9 and state['minionsRemaining']==0
    for _ in range(3):
        lich_logic.minion_removed(state)
    assert state['phase']==3


def test_real_full_health_healing_event_breaks_exactly_one_shield():
    # Actual fields from session 50708-1788606172597, tick 979.
    host,state=harness()
    event=dict(entityId='-4294967281',attributeBuffType=3,cause='magic',
               damage=0.0,duration=0,lifeTimer=0,isInstantaneous=True)
    for expected in range(5,-1,-1):
        host.OnLichEffectDamage(event)
        assert state['shieldStrength']==expected
        assert state['health']==100
        host.OnActorHurtServerEvent(dict(entityId=event['entityId'],damage=0,cause='magic'))
        assert state['shieldStrength']==expected
        host._tick+=20
    assert state['phase']==2
    assert state['minionsRemaining']==9


def test_zero_contact_is_not_inferred_from_other_effects_or_missing_damage():
    host,state=harness()
    for buff,instant in [(2,True),(4,True),(5,True),(3,False)]:
        host.OnLichEffectDamage(dict(entityId='boss',attributeBuffType=buff,
            cause='magic',damage=0,isInstantaneous=instant))
    host.OnLichEffectDamage(dict(entityId='boss',attributeBuffType=3,
        cause='magic',isInstantaneous=True))
    assert state['shieldStrength']==6


def test_healing_potion_damages_unshielded_lich_and_cancels_native_recovery():
    host, state = harness()
    state.update(shieldStrength=0, minionsRemaining=3, activeMinions=0,
                 phase=2, health=100)
    host.OnLichEffectDamage(dict(entityId='boss', damage=-8,
        attributeBuffType=3, isInstantaneous=True, cause='magic'))
    assert state['shieldStrength'] == 0
    assert state['health'] == 88

    native_recovery = dict(entityId='boss', byScript=False,
                           **{'from': 100, 'to': 108})
    host.OnHealthChangeBefore(native_recovery)
    assert native_recovery['cancel'] is True
    assert state['health'] == 88


def test_zero_value_healing_contact_uses_base_undead_damage_without_shields():
    host, state = harness()
    state.update(shieldStrength=0, minionsRemaining=0, activeMinions=0,
                 phase=3, health=100)
    host.OnLichEffectDamage(dict(entityId='boss', damage=0.0,
        attributeBuffType=3, isInstantaneous=True, cause='magic'))
    assert state['shieldStrength'] == 0
    assert state['health'] == 94
