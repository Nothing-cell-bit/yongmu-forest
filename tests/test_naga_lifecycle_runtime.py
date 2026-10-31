"""Run production Naga entry points with SDK-only boundary substitutes."""
from types import SimpleNamespace

import pytest

from tests.test_portal_arrival_runtime import SERVER


def host(monkeypatch, health=200.0):
    system = object.__new__(SERVER.ServerSystem)
    system._tick = 0
    system._bosses = {}
    system._segment_owners = {}
    system._get_foot_pos = lambda entity: (0.0, 64.0, 0.0)
    system._get_engine_type = lambda entity: SERVER.SEGMENT_IDENTIFIER
    attr = SimpleNamespace(GetAttrValue=lambda attr: health)
    game = SimpleNamespace(IsEntityAlive=lambda entity: True)
    monkeypatch.setattr(SERVER, 'CF', SimpleNamespace(
        CreateAttr=lambda entity: attr, CreateGame=lambda level: game))
    monkeypatch.setattr(SERVER.serverApi, 'GetMinecraftEnum', lambda: SimpleNamespace(
        AttrType=SimpleNamespace(HEALTH=0)), raising=False)
    system.DestroyEntity = lambda entity: False
    return system, game, attr


def segments(system, segment='21', health=0.0):
    state = dict(health=health, maxHealth=200.0, segments=0, dimensionId=0, dead=True,
                 dying=False, segmentIds=[segment] + [None] * 11,
                 segmentBurstTicks={0: 0}, bodyContactReadyTicks={},
                 participants=set(), brain=SERVER.naga_logic.NagaBrain())
    system._bosses['20'] = state
    system._segment_owners[segment] = ('20', 0)
    return state


@pytest.mark.parametrize('raw', [-1.0, None, float('nan'), float('inf')])
def test_unavailable_health_is_not_a_lethal_read(monkeypatch, raw):
    system, _, _ = host(monkeypatch, raw)
    assert system._get_health('20', 200.0) == 200.0


@pytest.mark.parametrize('raw', [0.0, 1.0, 137.5])
def test_real_zero_and_damage_remain_authoritative(monkeypatch, raw):
    system, _, _ = host(monkeypatch, raw)
    assert system._get_health('20', 200.0) == raw


def test_destroy_false_for_absent_segment_releases_all_bookkeeping(monkeypatch):
    system, game, _ = host(monkeypatch)
    state = segments(system)
    system._get_foot_pos = lambda entity: None
    system._get_engine_type = lambda entity: None
    game.IsEntityAlive = lambda entity: False
    system._broadcast_segment_bursts = lambda *args: None
    system._update_boss_segments()
    assert state['segmentIds'][0] is None
    assert state['segmentBurstTicks'] == {}
    assert system._segment_owners == {}
    assert system._bosses == {}


def test_live_failed_destroy_keeps_owner_and_backs_off(monkeypatch, capsys):
    system, _, _ = host(monkeypatch)
    state = segments(system)
    calls = []
    system.DestroyEntity = lambda entity: calls.append(system._tick) or False
    system._broadcast_segment_bursts = lambda *args: None
    for tick in range(600):
        system._tick = tick
        system._update_boss_segments()
    assert len(calls) < 15
    assert len(capsys.readouterr().out.splitlines()) <= 2
    assert state['segmentIds'][0] == '21'
    assert system._segment_owners['21'] == ('20', 0)
    system.DestroyEntity = lambda entity: True
    system._tick = state['segmentBurstTicks'][0]
    system._update_boss_segments()
    assert system._bosses == {} and system._segment_owners == {}


def test_unavailable_existence_probe_does_not_discard_an_actor(monkeypatch):
    system, game, _ = host(monkeypatch)
    state = segments(system)
    system._get_foot_pos = lambda entity: None
    system._get_engine_type = lambda entity: None
    def unknown(entity):
        raise RuntimeError('SDK unavailable')
    game.IsEntityAlive = unknown
    assert system._destroy_segment(state, 0)[0] is False
    assert state['segmentIds'][0] == '21'
    assert '21' in system._segment_owners


def test_removal_callback_during_destroy_false_is_success(monkeypatch):
    system, _, _ = host(monkeypatch)
    state = segments(system)
    def destroy(entity):
        # Simulate the SDK delivering its real removal callback inline.
        system.OnRemoveEntity({'id': 21})
        return False
    removal_registries(system)
    system.DestroyEntity = destroy
    assert system._destroy_segment(state, 0)[0] is True
    assert state['segmentIds'][0] is None
    assert system._segment_owners == {}


def removal_registries(system):
    for name in ('_knight_projectiles', '_phantom_urghast_mobs', '_block_chain_projectiles',
                 '_hydra_mortars', '_ur_ghast_projectiles', '_ur_ghasts', '_hydra_parts',
                 '_hydra_necks', '_hydra_heads', '_route_mobs', '_hydras', '_lich_projectiles',
                 '_lifedrain_users', '_loyal_zombies', '_lich_clones', '_lich_minions',
                 '_lich_bosses', '_ruin_mobs', '_tiny_birds', '_pending_catalysts',
                 '_pending_quest_offerings', '_pending_portal_entries',
                 '_dimension_worldgen_ready_ticks', '_magic_map_use_cooldowns',
                 '_magic_map_held_states', '_magic_map_delta_states',
                 '_magic_map_discovery_frontiers', '_pending_magic_map_clone_sources',
                 '_pending_maze_slime_sizes'):
        setattr(system, name, {})
    for name in ('_penguins', '_pending_portal_recovery_players', '_known_players',
                 '_dimension_change_in_progress'):
        setattr(system, name, set())
    system._pending_courtyard_nagas = []
    system._clear_player_fortification = lambda entity: None


def test_orphan_scan_respects_owner_with_mixed_id_types(monkeypatch):
    system, _, _ = host(monkeypatch)
    segments(system)
    destroyed = []
    system.DestroyEntity = lambda entity: destroyed.append(entity)
    system._cleanup_orphan_segments([(21, {'identifier': SERVER.SEGMENT_IDENTIFIER}),
                                    (22, {'identifier': SERVER.SEGMENT_IDENTIFIER})])
    assert destroyed == ['22']


def test_body_contact_never_damages_own_head_or_segments(monkeypatch):
    system, game, _ = host(monkeypatch)
    state = segments(system, health=200.0)
    state['dead'] = False
    state['brain'] = SERVER.naga_logic.NagaBrain()
    # Native queries and script registries can represent the same ID differently.
    game.GetEntitiesAround = lambda entity, radius, filters: [20, 21, 30]
    damaged = []
    def hurt(entity, amount, attacker, *args):
        damaged.append((entity, amount))
        if str(entity) == '20':
            state['health'] -= amount
        return True
    system._hurt = hurt  # SDK damage boundary, real contact selection stays intact.
    system._collision_size = lambda *args: (1.0, 1.5)
    system._knockback = lambda *args: None
    for tick in range(100):
        system._tick = tick
        system._resolve_segment_collisions('20', state, None)
    assert state['health'] == 200.0
    assert damaged and all(str(entity) == '30' for entity, _ in damaged)


def test_unloaded_boss_is_not_polled_for_health_or_advanced_in_death(monkeypatch):
    system, _, _ = host(monkeypatch)
    state = segments(system, health=200.0)
    state.update(dead=False, actorLoaded=False)
    system._get_online_players = lambda: []
    def invalid_poll(*args):
        pytest.fail('unloaded actor entered health/death processing')
    system._get_health = invalid_poll
    system._update_naga_death = invalid_poll
    system._drive_bosses()
    state['dying'] = True
    system._drive_bosses()


def test_leave_unload_and_rebind_never_turns_missing_attribute_into_death(monkeypatch):
    system, _, attr = host(monkeypatch, -1.0)
    state = segments(system, health=137.5)
    state.update(dead=False, actorLoaded=True, home=(0, 64, 0), targetId='player',
                 brain=SERVER.naga_logic.NagaBrain())
    removal_registries(system)
    system._get_online_players = lambda: []
    system.OnRemoveEntity({'id': 20})
    assert system._bosses['20'] is state and state['actorLoaded'] is False
    for tick in range(300):
        system._tick = tick
        system._drive_bosses()
        assert state['health'] == 137.5 and not state['dying'] and not state['dead']
    # Rebind through the same registration entry used by discovery on return.
    extra = SimpleNamespace(GetExtraData=lambda key: None,
                            SetExtraData=lambda *args: True, SaveExtraData=lambda: True)
    SERVER.CF.CreateExtraData = lambda entity: extra
    assert system._register_boss(20, 0, (0, 64, 0)) is state
    assert state['actorLoaded'] is True
    health = system._get_health(20, state['health'])
    assert system._apply_boss_health_state(20, state, health) is True
    assert state['health'] == 137.5 and not state['dying']
    attr.GetAttrValue = lambda key: 100.0
    assert system._apply_boss_health_state(20, state, system._get_health(20, 137.5))
    assert state['health'] == 100.0


def test_dead_head_removal_keeps_body_cleanup_reachable(monkeypatch):
    system, game, _ = host(monkeypatch)
    state = segments(system)
    removal_registries(system)
    system.OnRemoveEntity({'id': 20})
    assert '20' in system._bosses
    assert system._bosses['20'] is state
    system._get_foot_pos = lambda entity: None
    system._get_engine_type = lambda entity: None
    game.IsEntityAlive = lambda entity: False
    system._broadcast_segment_bursts = lambda *args: None
    system._update_boss_segments()
    assert system._bosses == {} and system._segment_owners == {}


def test_destroy_does_not_forget_replacement_created_by_callback(monkeypatch):
    system, _, _ = host(monkeypatch)
    state = segments(system)
    def destroy(entity):
        state['segmentIds'][0] = '22'
        system._segment_owners['22'] = ('20', 0)
        return False
    system.DestroyEntity = destroy
    assert system._destroy_segment(state, 0)[0] is True
    assert state['segmentIds'][0] == '22'
    assert system._segment_owners == {'22': ('20', 0)}


def test_attribute_loss_between_position_and_health_read_is_not_death(monkeypatch):
    system, _, _ = host(monkeypatch, -1.0)
    state = segments(system, health=137.5)
    state.update(dead=False, actorLoaded=True, home=None,
                 segments=SERVER.naga_logic.segment_count(137.5, 200.0),
                 segmentBurstTicks={})
    positions = iter([(0, 64, 0), None])
    system._get_foot_pos = lambda entity: next(positions, None)
    system._get_online_players = lambda: []
    system._drive_bosses()
    assert state['health'] == 137.5 and not state['dying']
    assert state['segmentBurstTicks'] == {}


def test_real_lethal_health_starts_one_death_sequence(monkeypatch):
    system, _, _ = host(monkeypatch)
    state = segments(system, health=200.0)
    state.update(dead=False, dying=False, targetId='player', waypoint=(1, 64, 1),
                 bodyContactReadyTicks={}, participants=set(), segments=1)
    system._is_online_player = lambda entity: False
    system._reset_attack_target = lambda entity: None
    system._stop_navigation = lambda *args: None
    system._set_health = lambda *args: True
    system._push_state_property = lambda *args: None
    system._save_naga_state = lambda *args: True
    assert system._apply_boss_health_state('20', state, 0.0) is False
    assert state['dying'] and state['deathTime'] == 0
    system._tick = 5
    assert system._apply_boss_health_state('20', state, 0.0) is False
    assert state['deathTime'] == 0
