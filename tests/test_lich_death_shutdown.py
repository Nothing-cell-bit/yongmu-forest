"""Execute death adapters against a minimal native component/event model."""
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.test_lich_effect_runtime import lich_logic, entity_registry_logic

ROOT = Path(__file__).resolve().parents[1]


def harness():
    source = Path(os.environ.get('LICH_TEST_SERVER', str(
        ROOT / 'TwilightBossSliceB/TwilightBossSlice/serverSystem.py'))).read_text('utf-8')
    entity = json.loads(Path(os.environ.get('LICH_TEST_ENTITY', str(
        ROOT / 'TwilightBossSliceB/entities/lich.entity.json'))).read_text('utf-8'))['minecraft:entity']
    names = ('_begin_lich_death', '_update_lich_death', '_stop_lich_death_combat',
             '_stop_lich_navigation', '_sync_lich_presentation', '_execute_lich_action')
    methods = []
    for name in names:
        match = re.search(r'^    def ' + name + r'\(.*?(?=^    def |\Z)', source, re.M | re.S)
        if match:
            methods.append(match.group())
    ns = dict(lich_logic=lich_logic, entity_registry_logic=entity_registry_logic)
    exec('class Host:\n' + ''.join(methods), ns)
    host = ns['Host']()
    native = SimpleNamespace(groups=set(), target='player', velocity=(1, 1),
                             events=[], items=[], damage=[], health=[], effects=[], failed=False)

    def event(_, name):
        native.events.append(name)
        if native.failed:
            return False
        definition = entity['events'][name]
        native.groups.difference_update(definition.get('remove', {}).get('component_groups', []))
        native.groups.update(definition.get('add', {}).get('component_groups', []))
        return True

    def components():
        result = dict(entity['components'])
        for group in sorted(native.groups):
            result.update(entity['component_groups'][group])
        return result

    native.components = components
    host._trigger_entity_event = event
    host._reset_attack_target = lambda _: setattr(native, 'target', None)
    host._set_motion = lambda _, x, z: setattr(native, 'velocity', (x, z))
    host._set_health = lambda _, value: native.health.append(value)
    host._set_entity_carried_item = lambda _, item: native.items.append(item) or True
    host._hurt = lambda *args: native.damage.append(args)
    host._entry_trace = lambda *a, **kw: None
    host._discard_lich_clones = lambda state: state.update(cloneIds=set())
    host._lich_minions = {}
    host._get_foot_pos = lambda _: (0, 64, 0)
    host._broadcast_lich_effect = lambda *args: native.effects.append(args[1])
    host._save_lich_state = lambda *a: None
    host._play_world_sound = lambda *a: None
    host._lich_death_soul_position = lambda state, position, time: position
    host._finalize_lich_death = lambda _, state: state.update(dead=True)
    state = lich_logic.new_lich_state()
    state.update(phase=3, shieldStrength=0, minionsRemaining=0,
                 minionIds=set(), activeMinions=0, meleeNavTarget=None,
                 dimensionId=0, home=(0, 64, 0))
    host._sync_lich_presentation('boss', state, True)
    return host, state, native


def assert_disarmed(native):
    components = native.components()
    assert 'minecraft:behavior.melee_attack' not in components
    assert 'minecraft:behavior.nearest_attackable_target' not in components
    assert components['minecraft:movement']['value'] == 0
    assert native.target is None
    assert native.velocity == (0, 0)


def test_lethal_hit_stops_native_combat_even_without_script_navigation():
    host, state, native = harness()
    assert 'minecraft:behavior.melee_attack' in native.components()
    host._begin_lich_death('boss', state)
    assert state['dying']
    assert native.health[-1] == 1
    assert_disarmed(native)


def test_entire_death_sequence_never_rearms_or_restarts():
    host, state, native = harness()
    host._begin_lich_death('boss', state)
    equipped = len(native.items)
    for _ in range(lich_logic.DEATH_TICKS):
        assert host._begin_lich_death('boss', state) is False
        host._sync_lich_presentation('boss', state, True)
        host._update_lich_death('boss', state)
        assert_disarmed(native)
    assert state['dead']
    assert state['deathTime'] == lich_logic.DEATH_TICKS
    assert native.effects.count('death_start') == 1
    assert len(native.items) == equipped


def test_restored_death_overrides_stale_melee_presentation_cache():
    host, state, native = harness()
    state.update(dying=True, deathTime=60, deathAiStopped=True)
    host._sync_lich_presentation('boss', state, True)
    assert_disarmed(native)


def test_failed_native_shutdown_retries_on_next_death_tick():
    host, state, native = harness()
    native.failed = True
    host._begin_lich_death('boss', state)
    assert not state.get('deathAiStopped')
    native.failed = False
    host._update_lich_death('boss', state)
    assert_disarmed(native)


def test_successful_shutdown_is_not_retriggered_every_tick():
    host, state, native = harness()
    host._begin_lich_death('boss', state)
    for _ in range(lich_logic.DEATH_TICKS):
        host._update_lich_death('boss', state)
    assert native.events.count('tf_slice:begin_dying') == 1
    assert_disarmed(native)


def test_native_spawn_initializes_targeting_before_script_registration():
    host, state, native = harness()
    native.groups.clear()
    host._trigger_entity_event('boss', 'minecraft:entity_spawned')
    assert 'minecraft:behavior.nearest_attackable_target' in native.components()
    assert 'minecraft:behavior.melee_attack' not in native.components()


@pytest.mark.parametrize('flag', ['dying', 'dead'])
def test_late_script_attack_is_rejected(flag):
    host, state, native = harness()
    state[flag] = True
    host._execute_lich_action('boss', state, 'player', (1, 64, 0),
                              {'type': 'melee', 'damage': 6})
    assert not native.damage


def test_phase_switch_keeps_living_targeting_and_removes_melee():
    host, state, native = harness()
    state.update(phase=1, shieldStrength=6)
    host._sync_lich_presentation('boss', state, True)
    assert 'minecraft:behavior.nearest_attackable_target' in native.components()
    assert 'minecraft:behavior.melee_attack' not in native.components()
    assert native.components()['minecraft:movement']['value'] == 0.45
