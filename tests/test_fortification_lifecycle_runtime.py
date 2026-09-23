"""Exercise shield lifecycle and rendering API failure handling offline."""
import math
import pathlib
import re
import sys
import types
import time
import unittest
import warnings
from lib2to3.refactor import RefactoringTool

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from TwilightBossSlice import scepter_logic, entity_registry_logic, chain_visual_client, fortification_visual_logic


def load_methods(filename, names, namespace):
    source = (ROOT / 'TwilightBossSliceB/TwilightBossSlice' / filename).read_text(encoding='utf-8')
    methods = []
    for name in names:
        match = re.search(r'^    def ' + name + r'\(', source, re.M)
        if match:
            end = re.search(r'^    (?:def |@)', source[match.end():], re.M)
            methods.append(source[match.start():match.end() + end.start() if end else len(source)])
    payload = 'class UnderTest:\n' + ''.join(methods)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        payload = str(RefactoringTool(['lib2to3.fixes.fix_print']).refactor_string(payload, filename))
    exec(payload, namespace)
    return namespace['UnderTest']


class ClientFactory:
    def __init__(self):
        self.owner_position = (10, 64, 20)
        self.binds = []
        self.registers = []
        self.sets = []
        self.reset_result = True
        self.resets = []
        self.offsets = []
        self.values = {}
        self.anchors = {}

    def set_query(self, entity, name, value):
        self.sets.append((entity, name, value))
        self.values[(entity, name)] = value
        return True

    def bone_position(self, entity, name):
        origin = self.anchors.get(entity, (10.0, 64.0, 20.0))
        if name == 'root':
            return (origin[0] - self.values.get((entity, 'query.mod.tf_fortification_dx'), 0) / 16,
                    origin[1] + 1 + self.values.get((entity, 'query.mod.tf_fortification_dy'), 0) / 16,
                    origin[2] + self.values.get((entity, 'query.mod.tf_fortification_dz'), 0) / 16)
        return {'tf_anchor': origin, 'tf_basis_x': (origin[0] - 1, origin[1], origin[2]),
                'tf_basis_y': (origin[0], origin[1] + 1, origin[2]),
                'tf_basis_z': (origin[0], origin[1], origin[2] + 1)}[name]

    def CreatePos(self, owner_id):
        return types.SimpleNamespace(GetFootPos=lambda: self.owner_position)

    def CreateModel(self, visual_id):
        return types.SimpleNamespace(
            BindEntityToEntity=lambda owner_id: self.binds.append(
                (visual_id, owner_id)
            ) is None,
            ResetBindEntity=lambda: self.resets.append(visual_id) is None and self.reset_result,
            SetModelOffset=lambda offset: self.offsets.append((visual_id, tuple(offset))),
            GetBonePositionFromMinecraftObject=lambda name: self.bone_position(visual_id, name),
        )

    def CreateQueryVariable(self, entity_id):
        return types.SimpleNamespace(
            Register=lambda name, value: self.registers.append(
                (entity_id, name, value)
            ) is None,
            Set=lambda name, value: self.set_query(entity_id, name, value),
        )


class ClientEntityRuntime:
    def __init__(self):
        self.created = []
        self.destroyed = []

    def create(self, identifier, position, rotation):
        visual_id = 'visual-%d' % (len(self.created) + 1)
        self.created.append((visual_id, identifier, tuple(position), tuple(rotation)))
        return visual_id

    def destroy(self, visual_id):
        self.destroyed.append(visual_id)
        return True


class FortificationLifecycleTests(unittest.TestCase):
    def client(self):
        self.factory = ClientFactory()
        cls = load_methods('clientSystem.py', [
            '_clear_fortification_visuals', '_destroy_fortification_client_visual',
            '_remove_fortification_visual_entity',
            '_ensure_fortification_query_registered', '_set_fortification_visual_count',
            '_create_fortification_client_visual', '_update_fortification_visuals',
            'OnFortificationRender',
        ], {
            'CF': self.factory, 'math': math, 'time': time, 'LEVEL_ID': 'level', 'chain_visual_client': chain_visual_client,
            'fortification_visual_logic': fortification_visual_logic,
            'FORTIFICATION_SHIELD_QUERY': 'query.mod.tf_fortification_shields',
            'FORTIFICATION_VISUAL_IDENTIFIER': 'tf_slice:fortification_shield_visual',
            'FORTIFICATION_ANCHOR_CHECK_TICKS': 150,
            'FORTIFICATION_MAX_ANCHOR_DISTANCE_SQ': 64.0,
        })
        client = cls()
        self.render_time = 0.0
        client._fortification_clock = lambda: self.render_time
        client._lich_effect_tick = 200
        client._fortification_query_registered = False
        client._twilight_dimension_switching = False
        client._fortification_visuals = {
            'p': {'count': 5, 'dimensionId': 0, 'entityId': None}
        }
        self.entities = ClientEntityRuntime()
        def create(identifier, position, rotation):
            entity = self.entities.create(identifier, position, rotation)
            self.factory.anchors[entity] = tuple(position)
            return entity
        client.CreateClientEntityByTypeStr = create
        client.DestroyClientEntity = self.entities.destroy
        return client

    def server(self):
        cls = load_methods('serverSystem.py', [
            '_clear_player_fortification', '_destroy_fortification_visual',
            '_update_fortification_shields', 'OnRoutePlayerDie',
        ], {'scepter_logic': scepter_logic, 'entity_registry_logic': entity_registry_logic,
            'CF': types.SimpleNamespace(CreateGame=lambda _: types.SimpleNamespace(GetPlayerGameType=lambda _: 0)), 'LEVEL_ID': 'level'})
        server = cls()
        server._player_fortification = {'42': scepter_logic.new_shield_state(temporary=5)}
        server._fortification_cooldowns = {'42': 1200}
        server._fortification_visuals = {'42': {'dimensionId': 0, 'count': 5}}
        server._is_online_player = lambda _: True
        server._is_creative = lambda _: False
        server._get_dimension = lambda _: 0
        server._get_foot_pos = lambda _: (0, 64, 0)
        server._keep_inventory_rule = lambda: True
        server.events = []
        server._broadcast_lich_effect = lambda dim, kind, pos, owner, **kw: server.events.append(kind)
        server._sync_fortification_visual = lambda owner, shield: None
        server._play_world_sound = lambda *args: True
        return server

    def test_short_heartbeat_gap_does_not_hide_live_owners_shield(self):
        client = self.client()
        client._update_fortification_visuals(0)
        client._lich_effect_tick += 120
        client._update_fortification_visuals(0)
        self.assertEqual(1, len(self.entities.created))
        self.assertIn('p', client._fortification_visuals)

    def test_one_model_receives_count_without_binding_to_player(self):
        client = self.client()
        client._update_fortification_visuals(0)
        self.assertEqual(1, len(self.entities.created))
        self.assertFalse(self.factory.binds)
        self.assertEqual(5.0, self.factory.sets[-1][2])

    def test_player_layer_route_never_creates_a_following_entity(self):
        client = self.client()
        counts = []
        client._fortification_player_layer = types.SimpleNamespace(
            set_count=lambda owner, count, tick: counts.append((owner, count)) is None)
        for step in range(100):
            self.factory.owner_position = (step * 20, 64, 20)
            client._update_fortification_visuals(0)
            client.OnFortificationRender()
        self.assertFalse(self.entities.created)
        self.assertFalse(self.factory.sets)
        self.assertEqual(('p', 5), counts[-1])

    def test_player_layer_end_only_writes_zero_and_retries_failure(self):
        client = self.client()
        counts = []
        succeed = [False]
        def set_count(owner, count, tick):
            counts.append((owner, count))
            return succeed[0]
        client._fortification_player_layer = types.SimpleNamespace(set_count=set_count)
        client._destroy_fortification_client_visual('p')
        self.assertIn('p', client._fortification_visuals)
        succeed[0] = True
        client._update_fortification_visuals(0)
        self.assertNotIn('p', client._fortification_visuals)
        self.assertEqual([('p', 0), ('p', 0)], counts)
        self.assertFalse(self.entities.destroyed)

    def test_new_server_shield_state_supersedes_pending_hide(self):
        client = self.client()
        counts = []
        client._fortification_player_layer = types.SimpleNamespace(
            set_count=lambda owner, count, tick: counts.append(count) is None and count > 0)
        client._destroy_fortification_client_visual('p')
        self.factory.CreateGame = lambda _: types.SimpleNamespace(GetCurrentDimension=lambda: 0)
        event = load_methods('clientSystem.py', ['OnLichCombatEffect'], {'CF': self.factory, 'LEVEL_ID': 'level'})
        event.OnLichCombatEffect(client, dict(kind='fortification_visual_sync', entityId='p', style=5, dimensionId=0))
        client._update_fortification_visuals(0)
        self.assertEqual([0, 5], counts)

    def test_null_entity_creation_is_rate_limited_and_recovers(self):
        client = self.client()
        attempts = []
        client.CreateClientEntityByTypeStr = lambda *args: attempts.append(args)
        for _ in range(30):
            client._update_fortification_visuals(0)
            client._lich_effect_tick += 1
        self.assertEqual(1, len(attempts))
        client.CreateClientEntityByTypeStr = self.entities.create
        client._update_fortification_visuals(0)
        self.assertEqual(1, len(self.entities.created))

    def test_unsupported_binding_is_never_called_and_cannot_destroy_visual(self):
        client = self.client()
        self.factory.CreateModel = lambda _: types.SimpleNamespace(BindEntityToEntity=lambda _: False)
        for _ in range(30):
            client._update_fortification_visuals(0)
            client._lich_effect_tick += 1
        self.assertEqual(1, len(self.entities.created))
        self.assertEqual([], self.entities.destroyed)

    def test_count_reduction_updates_the_model_without_recreating_it(self):
        client = self.client()
        client._update_fortification_visuals(0)
        client._fortification_visuals['p']['count'] = 2
        client._update_fortification_visuals(0)
        self.assertEqual(1, len(self.entities.created))
        self.assertEqual(2.0, self.factory.sets[-1][2])

    def test_shield_end_destroys_only_shield_and_does_not_touch_owner(self):
        client = self.client()
        client._update_fortification_visuals(0)
        def destroy(visual_id):
            self.assertNotEqual('p', visual_id)
            return self.entities.destroy(visual_id)
        client.DestroyClientEntity = destroy
        client._destroy_fortification_client_visual('p')
        self.assertEqual(['visual-1'], self.entities.destroyed)
        self.assertEqual([], self.factory.resets)
        self.assertNotIn('p', client._fortification_visuals)

    def test_failed_unbind_defers_destruction_until_it_succeeds(self):
        client = self.client()
        client._update_fortification_visuals(0)
        # Cleanup remains safe for any legacy bound record.
        client._fortification_visuals['p']['bound'] = True
        self.factory.reset_result = False
        client._destroy_fortification_client_visual('p')
        self.assertEqual([], self.entities.destroyed)
        self.assertIn('p', client._fortification_visuals)
        self.factory.reset_result = True
        client._lich_effect_tick += 30
        client._update_fortification_visuals(0)
        self.assertEqual(['visual-1'], self.entities.destroyed)
        self.assertNotIn('p', client._fortification_visuals)

    def test_factory_returning_owner_id_never_binds_or_destroys_player(self):
        client = self.client()
        client.CreateClientEntityByTypeStr = lambda *args: 'p'
        client._update_fortification_visuals(0)
        client._destroy_fortification_client_visual('p')
        self.assertFalse(self.factory.binds)
        self.assertFalse(self.entities.destroyed)

    def test_missing_owner_can_recover_before_cleanup_grace(self):
        client = self.client()
        self.factory.owner_position = None
        client._update_fortification_visuals(0)
        client._lich_effect_tick += 60
        self.factory.owner_position = (20, 64, 30)
        client._update_fortification_visuals(0)
        self.assertEqual(1, len(self.entities.created))

    def test_missing_owner_and_wrong_dimension_are_cleaned(self):
        client = self.client()
        self.factory.owner_position = None
        client._update_fortification_visuals(0)
        client._lich_effect_tick += 91
        client._update_fortification_visuals(0)
        self.assertFalse(client._fortification_visuals)
        client = self.client()
        client._update_fortification_visuals(0)
        client._update_fortification_visuals(1)
        self.assertEqual(['visual-1'], self.entities.destroyed)

    def test_distant_anchor_is_recreated_on_next_tick(self):
        client = self.client()
        client._update_fortification_visuals(0)
        self.factory.owner_position = (40, 64, 20)
        client._lich_effect_tick += 30
        client._update_fortification_visuals(0)
        self.assertEqual(2, len(self.entities.created))
        self.assertEqual([], self.entities.destroyed)
        client.OnFortificationRender()
        client._lich_effect_tick += 1
        self.render_time += 1 / 30.0
        client.OnFortificationRender()
        self.assertEqual(['visual-1'], self.entities.destroyed)

    def test_fast_movement_reanchors_without_waiting_for_creation_retry(self):
        client = self.client()
        client._update_fortification_visuals(0)
        self.factory.owner_position = (20, 64, 20)
        client._lich_effect_tick += 1
        client._update_fortification_visuals(0)
        self.assertEqual(2, len(self.entities.created))
        self.assertEqual('visual-2', client._fortification_visuals['p']['entityId'])

    def test_small_position_steps_are_smoothed_between_render_frames(self):
        client = self.client()
        client._update_fortification_visuals(0)
        client.OnFortificationRender()
        self.factory.owner_position = (10.2, 64, 20)
        self.render_time += 1 / 60.0
        client.OnFortificationRender()
        first = -self.factory.values[('visual-1', 'query.mod.tf_fortification_dx')] / 16
        self.assertGreater(first, 0)
        self.assertLess(first, 0.2)
        self.render_time += 1 / 60.0
        client.OnFortificationRender()
        second = -self.factory.values[('visual-1', 'query.mod.tf_fortification_dx')] / 16
        self.assertGreater(second, first)
        self.assertLess(second, 0.2)

    def test_rotation_time_survives_anchor_replacement(self):
        client = self.client()
        client._update_fortification_visuals(0)
        client.OnFortificationRender()
        for _ in range(60):
            self.render_time += 1 / 60.0
            client.OnFortificationRender()
        phase = self.factory.values.get(('visual-1', 'query.mod.tf_fortification_time'))
        self.assertIsNotNone(phase)
        self.assertAlmostEqual(1, phase)
        self.factory.owner_position = (20, 64, 20)
        client._update_fortification_visuals(0)
        self.assertAlmostEqual(phase, self.factory.values[('visual-2', 'query.mod.tf_fortification_time')])

    def test_failed_replacement_keeps_existing_shield(self):
        client = self.client()
        client._update_fortification_visuals(0)
        self.factory.owner_position = (20, 64, 20)
        client.CreateClientEntityByTypeStr = lambda *args: None
        client._update_fortification_visuals(0)
        self.assertEqual([], self.entities.destroyed)
        self.assertEqual('visual-1', client._fortification_visuals['p']['entityId'])

    def test_replacement_keeps_old_model_until_new_model_has_rendered(self):
        client = self.client()
        client._update_fortification_visuals(0)
        self.factory.owner_position = (20, 64, 20)
        client._update_fortification_visuals(0)
        self.assertEqual([], self.entities.destroyed)
        client.OnFortificationRender()
        client._lich_effect_tick += 1
        self.render_time += 1 / 30.0
        client.OnFortificationRender()
        self.assertEqual(['visual-1'], self.entities.destroyed)

    def test_expiry_during_handoff_cleans_both_models_only(self):
        client = self.client()
        client._update_fortification_visuals(0)
        self.factory.owner_position = (20, 64, 20)
        client._update_fortification_visuals(0)
        self.assertEqual([], self.entities.destroyed)
        client._destroy_fortification_client_visual('p')
        self.assertCountEqual(['visual-1', 'visual-2'], self.entities.destroyed)
        self.assertNotIn('p', client._fortification_visuals)

    def test_failed_replacement_position_write_retains_old_until_recovery(self):
        client = self.client()
        client._update_fortification_visuals(0)
        original = self.factory.set_query
        self.factory.set_query = lambda entity, name, value: (
            False if entity == 'visual-2' and name.endswith('_dx') else original(entity, name, value))
        self.factory.owner_position = (20, 64, 20)
        client._update_fortification_visuals(0)
        client.OnFortificationRender()
        client._lich_effect_tick += 1
        client.OnFortificationRender()
        self.assertEqual([], self.entities.destroyed)
        self.factory.set_query = original
        client._lich_effect_tick += 30
        self.render_time += 1
        client.OnFortificationRender()
        client._lich_effect_tick += 1
        client.OnFortificationRender()
        self.assertEqual(['visual-1'], self.entities.destroyed)

    def test_failed_replacement_phase_does_not_retire_visible_old_model(self):
        client = self.client()
        client._update_fortification_visuals(0)
        original = self.factory.set_query
        self.factory.set_query = lambda entity, name, value: (
            False if entity == 'visual-2' and name.endswith('_time') else original(entity, name, value))
        self.factory.owner_position = (20, 64, 20)
        for _ in range(35):
            client._update_fortification_visuals(0)
            client.OnFortificationRender()
            client._lich_effect_tick += 1
            self.render_time += 1 / 30.0
        self.assertEqual([], self.entities.destroyed)
        self.assertEqual(2, len(self.entities.created))
        self.factory.set_query = original
        client._lich_effect_tick += 30
        client._update_fortification_visuals(0)
        client.OnFortificationRender()
        client._lich_effect_tick += 1
        client.OnFortificationRender()
        self.assertEqual(['visual-1'], self.entities.destroyed)

    def test_failed_retirement_is_bounded_and_expiry_retries_both_models(self):
        client = self.client()
        client._update_fortification_visuals(0)
        client.DestroyClientEntity = lambda entity: False
        self.factory.owner_position = (20, 64, 20)
        for _ in range(60):
            client._update_fortification_visuals(0)
            client.OnFortificationRender()
            client._lich_effect_tick += 1
            self.render_time += 1 / 30.0
            self.factory.owner_position = (self.factory.owner_position[0] + 0.2, 64, 20)
        self.assertEqual(2, len(self.entities.created))
        client._destroy_fortification_client_visual('p')
        self.assertIn('p', client._fortification_visuals)
        client.DestroyClientEntity = self.entities.destroy
        client._lich_effect_tick += 30
        client._update_fortification_visuals(0)
        self.assertCountEqual(['visual-1', 'visual-2'], self.entities.destroyed)
        self.assertNotIn('p', client._fortification_visuals)

    def test_render_frames_move_one_model_without_recreation_or_player_binding(self):
        client = self.client()
        client._update_fortification_visuals(0)
        for i in range(120):
            self.factory.owner_position = (10 + i / 30.0, 65, 22)
            self.render_time += 1 / 120.0
            client.OnFortificationRender()
        self.assertEqual(1, len(self.entities.created))
        self.assertFalse(self.factory.offsets)
        delta_sets = [s for s in self.factory.sets if s[1].startswith('query.mod.tf_fortification_d')]
        self.assertEqual(360, len(delta_sets))
        lag = 119 / 30.0 + delta_sets[-3][2] / 16
        self.assertGreater(lag, 0)
        self.assertLessEqual(lag, 0.25)
        self.assertEqual((16.0, 32.0), (delta_sets[-2][2], delta_sets[-1][2]))
        self.assertEqual('visual-1', delta_sets[-1][0])
        self.assertFalse(self.factory.binds)

    def test_no_render_movement_during_removal_or_dimension_switch(self):
        client = self.client()
        client._update_fortification_visuals(0)
        self.factory.sets[:] = []
        client._twilight_dimension_switching = True
        client.OnFortificationRender()
        client._twilight_dimension_switching = False
        client._fortification_visuals['p']['removing'] = True
        client.OnFortificationRender()
        self.assertFalse(self.factory.sets)

    def test_stationary_render_skips_duplicate_offset_writes(self):
        client = self.client()
        client._update_fortification_visuals(0)
        for _ in range(120):
            client.OnFortificationRender()
        self.assertEqual(3, len([s for s in self.factory.sets if s[1].startswith('query.mod.tf_fortification_d')]))

    def test_offset_failure_keeps_visual_and_retries_at_bounded_rate(self):
        client = self.client()
        client._update_fortification_visuals(0)
        calls = []
        def offset(*args):
            calls.append(True)
            return False
        self.factory.CreateQueryVariable = lambda _: types.SimpleNamespace(Set=offset)
        for _ in range(120):
            client.OnFortificationRender()
        self.assertEqual(1, len(calls))
        self.assertFalse(self.entities.destroyed)
        client._lich_effect_tick += 30
        client.OnFortificationRender()
        self.assertEqual(2, len(calls))

    def test_follow_readback_is_compared_to_expected_root(self):
        client = self.client()
        client._update_fortification_visuals(0)
        client.OnFortificationRender()
        self.factory.owner_position = (13, 65, 24)
        client._lich_effect_tick += 30
        client.OnFortificationRender()
        client._lich_effect_tick += 30
        client.OnFortificationRender()
        self.assertAlmostEqual(0, client._fortification_visuals['p']['followError'])

    def test_readback_detects_renderer_ignoring_successful_query_writes(self):
        client = self.client()
        client._update_fortification_visuals(0)
        bones = self.factory.bone_position
        self.factory.bone_position = lambda entity, name: (10, 65, 20) if name == 'root' else bones(entity, name)
        self.factory.owner_position = (13, 64, 20)
        client.OnFortificationRender()
        client._lich_effect_tick += 30
        client.OnFortificationRender()
        self.assertAlmostEqual(3, client._fortification_visuals['p']['followError'])

    def test_unavailable_render_bones_do_not_block_follow_position_writes(self):
        client = self.client()
        client._update_fortification_visuals(0)
        self.factory.bone_position = lambda entity, name: None
        self.factory.owner_position = (13, 65, 24)
        client.OnFortificationRender()
        self.assertFalse(self.entities.destroyed)
        self.assertEqual((3.0, 1.0, 4.0), client._fortification_visuals['p']['lastOffset'])
        writes = {name: value for entity, name, value in self.factory.sets}
        self.assertEqual(48.0, writes['query.mod.tf_fortification_dx'])
        self.assertEqual(16.0, writes['query.mod.tf_fortification_dy'])
        self.assertEqual(-64.0, writes['query.mod.tf_fortification_dz'])
        self.factory.owner_position = (14, 65, 24)
        self.render_time += 1 / 60.0
        client.OnFortificationRender()
        delta = self.factory.values[('visual-1', 'query.mod.tf_fortification_dx')] / 16
        self.assertGreaterEqual(delta, 3.75)
        self.assertLess(delta, 4)

    def test_bone_read_exception_does_not_block_follow(self):
        client = self.client()
        client._update_fortification_visuals(0)
        def unavailable(*args):
            raise RuntimeError('bone API unavailable')
        self.factory.bone_position = unavailable
        self.factory.owner_position = (11, 64, 20)
        client.OnFortificationRender()
        self.assertEqual((1.0, 0.0, 0.0), client._fortification_visuals['p']['lastOffset'])

    def test_late_bone_calibration_rewrites_stationary_offset(self):
        client = self.client()
        client._update_fortification_visuals(0)
        bones = self.factory.bone_position
        self.factory.bone_position = lambda entity, name: None
        self.factory.owner_position = (13, 65, 24)
        client.OnFortificationRender()
        self.factory.bone_position = bones
        client._lich_effect_tick += 30
        client.OnFortificationRender()
        self.assertEqual(-48.0, self.factory.values[('visual-1', 'query.mod.tf_fortification_dx')])
        self.assertEqual(64.0, self.factory.values[('visual-1', 'query.mod.tf_fortification_dz')])
        client._lich_effect_tick += 30
        client.OnFortificationRender()
        self.assertAlmostEqual(0, client._fortification_visuals['p']['followError'])

    def test_missing_bones_still_write_every_moving_frame(self):
        client = self.client()
        client._update_fortification_visuals(0)
        calls = []
        self.factory.bone_position = lambda *args: calls.append(args)
        for frame in range(120):
            self.factory.owner_position = (10 + frame / 30.0, 65, 22)
            self.render_time += 1 / 120.0
            client.OnFortificationRender()
        writes = [s for s in self.factory.sets if s[1].startswith('query.mod.tf_fortification_d')]
        self.assertEqual(360, len(writes))
        lag = 119 / 30.0 - writes[-3][2] / 16
        self.assertGreater(lag, 0)
        self.assertLessEqual(lag, 0.25)
        self.assertEqual((16.0, -32.0), (writes[-2][2], writes[-1][2]))
        self.assertLessEqual(len(calls), 5)
        self.assertEqual([], self.entities.destroyed)

    def test_expiry_reports_one_layer_and_clears_last_layer(self):
        server = self.server()
        shield = server._player_fortification['42']
        shield.update(temporary=1, decayTimer=1)
        server._update_fortification_shields()
        self.assertIn('fortification_expire', server.events)
        self.assertIn('fortification_visual_remove', server.events)
        self.assertFalse(server._player_fortification)

    def test_creative_shields_do_not_decay(self):
        server = self.server()
        server._is_creative = lambda _: True
        for _ in range(1201):
            server._update_fortification_shields()
        self.assertEqual(5, server._player_fortification['42']['temporary'])

    def test_survival_shields_expire_in_five_steps(self):
        server = self.server()
        for expected in (4, 3, 2, 1, 0):
            for _ in range(240):
                server._update_fortification_shields()
            self.assertEqual(expected, server._player_fortification.get('42', {}).get('temporary', 0))
        self.assertEqual(5, server.events.count('fortification_expire'))
        self.assertEqual(1, server.events.count('fortification_visual_remove'))

    def test_hit_restarts_decay_and_break_interval_protects_remaining_shields(self):
        shield = scepter_logic.new_shield_state(temporary=5)
        scepter_logic.tick_shields(shield, 239)
        self.assertTrue(scepter_logic.break_shield(shield))
        self.assertFalse(scepter_logic.break_shield(shield))
        scepter_logic.tick_shields(shield, 239)
        self.assertEqual(4, shield['temporary'])
        scepter_logic.tick_shields(shield)
        self.assertEqual(3, shield['temporary'])

    def test_death_clears_shields_even_with_keep_inventory_and_integer_id(self):
        server = self.server()
        server.OnRoutePlayerDie({'playerId': 42})
        self.assertFalse(server._player_fortification)
        self.assertIn('fortification_visual_remove', server.events)

    def test_offline_owner_does_not_keep_broadcasting_shields(self):
        server = self.server()
        server._is_online_player = lambda _: False
        server._update_fortification_shields()
        self.assertFalse(server._player_fortification)


if __name__ == '__main__':
    unittest.main()
