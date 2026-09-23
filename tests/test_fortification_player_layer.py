"""Offline API/resource contracts, not proof of native first-person rendering."""
import copy
import json
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from TwilightBossSlice import fortification_player_layer as layer


class Factory:
    def __init__(self):
        self.calls = []
        self.fail = None
        self.values = {}
        self.geometry = {'default': 'geometry.humanoid.custom', 'cape': 'geometry.cape'}
        self.controllers = {'controller.render.player': '1'}
        self.animations = {'root': 'controller.animation.player.root'}

    def call(self, op, *args):
        self.calls.append((op,) + args)
        if self.fail == op:
            return False
        if op == 'Set':
            self.values[args[0], args[1]] = args[2]
        if op == 'AddPlayerGeometry':
            self.geometry[args[0]] = args[1]
        if op == 'AddPlayerRenderController':
            self.controllers[args[0]] = args[1]
        if op == 'AddPlayerAnimation':
            self.animations[args[0]] = args[1]
        return True

    def CreateQueryVariable(self, owner):
        return types.SimpleNamespace(
            Register=lambda *args: self.call('Register', owner, *args),
            Set=lambda *args: self.call('Set', owner, *args))

    def CreateActorRender(self, owner):
        return types.SimpleNamespace(**{
            op: (lambda *args, name=op: self.call(name, *args))
            for op in ('AddPlayerGeometry', 'AddPlayerTexture', 'AddPlayerRenderMaterial',
                       'AddPlayerAnimation', 'AddPlayerRenderController', 'AddPlayerScriptAnimate',
                       'RebuildPlayerRender')})


class PlayerLayerTests(unittest.TestCase):
    def setUp(self):
        self.factory = Factory()
        self.messages = []
        self.layer = layer.PlayerShieldLayer(self.factory, 'level', self.messages.append)

    def test_install_preserves_body_and_uses_private_keys(self):
        self.assertTrue(self.layer.set_count('p', 5, 0))
        self.assertEqual('geometry.humanoid.custom', self.factory.geometry['default'])
        self.assertEqual('geometry.cape', self.factory.geometry['cape'])
        self.assertEqual('1', self.factory.controllers['controller.render.player'])
        self.assertEqual('controller.animation.player.root', self.factory.animations['root'])
        for call in self.factory.calls:
            if call[0] in ('AddPlayerGeometry', 'AddPlayerTexture', 'AddPlayerRenderMaterial', 'AddPlayerAnimation'):
                self.assertTrue(call[1].startswith('tf_fortification_'))
        self.assertEqual(1, sum(call[0] == 'RebuildPlayerRender' for call in self.factory.calls))

    def test_count_changes_and_recast_do_not_reinstall_or_delete(self):
        self.layer.set_count('p', 5, 0)
        installed = len(self.factory.calls)
        for tick, count in enumerate((5, 4, 3, 2, 1, 0, 5)):
            self.assertTrue(self.layer.set_count('p', count, tick + 1))
        changes = self.factory.calls[installed:]
        self.assertTrue(all(call[0] == 'Set' for call in changes))
        self.assertEqual([4, 3, 2, 1, 0, 5], [call[-1] for call in changes])

    def test_unchanged_count_has_no_per_frame_engine_writes(self):
        self.layer.set_count('p', 5, 0)
        calls = list(self.factory.calls)
        for tick in range(1000):
            self.layer.set_count('p', 5, tick)
        self.assertEqual(calls, self.factory.calls)

    def test_zero_before_install_does_not_touch_player_renderer(self):
        self.assertTrue(self.layer.set_count('p', 0, 0))
        self.assertFalse(self.factory.calls)

    def test_every_failed_stage_stays_hidden_and_retries_without_duplicate_successful_steps(self):
        for failure in ('Register', 'Set', 'AddPlayerGeometry', 'AddPlayerTexture',
                        'AddPlayerRenderMaterial', 'AddPlayerAnimation', 'AddPlayerRenderController',
                        'AddPlayerScriptAnimate', 'RebuildPlayerRender'):
            with self.subTest(failure=failure):
                factory = Factory()
                candidate = layer.PlayerShieldLayer(factory, 'level', lambda _: None)
                factory.fail = failure
                self.assertFalse(candidate.set_count('p', 5, 0))
                self.assertNotEqual(5, factory.values.get(('p', layer.COUNT_QUERY)))
                before = len(factory.calls)
                self.assertFalse(candidate.set_count('p', 5, 1))
                self.assertEqual(before, len(factory.calls))
                factory.fail = None
                self.assertTrue(candidate.set_count('p', 5, 30))
                self.assertEqual(5, factory.values['p', layer.COUNT_QUERY])
                self.assertEqual(2 if failure == 'AddPlayerGeometry' else 1,
                                 sum(call[0] == 'AddPlayerGeometry' for call in factory.calls))

    def test_stop_bypasses_pending_positive_count_retry(self):
        self.layer.set_count('p', 5, 0)
        self.factory.fail = 'Set'
        self.assertFalse(self.layer.set_count('p', 3, 1))
        self.factory.fail = None
        self.assertTrue(self.layer.set_count('p', 0, 2))
        self.assertEqual(0, self.factory.values['p', layer.COUNT_QUERY])

    def test_api_exception_remains_hidden_and_recovers(self):
        original = self.factory.CreateActorRender
        def fail(owner):
            raise RuntimeError('renderer unavailable')
        self.factory.CreateActorRender = fail
        self.assertFalse(self.layer.set_count('p', 5, 0))
        self.assertEqual(0, self.factory.values['p', layer.COUNT_QUERY])
        self.factory.CreateActorRender = original
        self.assertTrue(self.layer.set_count('p', 5, 30))

    def test_final_count_write_failure_does_not_repeat_installation(self):
        original = self.factory.call
        def fail(op, *args):
            if op == 'Set' and args[-1] == 5:
                return False
            return original(op, *args)
        self.factory.call = fail
        self.assertFalse(self.layer.set_count('p', 5, 0))
        self.factory.call = original
        self.assertTrue(self.layer.set_count('p', 5, 30))
        self.assertEqual(1, sum(call[0] == 'RebuildPlayerRender' for call in self.factory.calls))

    def test_failed_hide_retries_promptly_without_rebuilding(self):
        self.layer.set_count('p', 5, 0)
        self.factory.fail = 'Set'
        self.assertFalse(self.layer.set_count('p', 0, 1))
        self.factory.fail = None
        self.assertTrue(self.layer.set_count('p', 0, 31))
        self.assertEqual(0, self.factory.values['p', layer.COUNT_QUERY])
        self.assertEqual(1, sum(call[0] == 'RebuildPlayerRender' for call in self.factory.calls))

    def test_cancel_partial_install_does_not_finish_installation(self):
        self.factory.fail = 'AddPlayerAnimation'
        self.assertFalse(self.layer.set_count('p', 5, 0))
        before = list(self.factory.calls)
        self.assertTrue(self.layer.set_count('p', 0, 1))
        self.assertEqual(before, self.factory.calls)
        self.factory.fail = None
        self.assertTrue(self.layer.set_count('p', 5, 30))

    def test_players_are_independent(self):
        self.layer.set_count('p', 5, 0)
        self.layer.set_count('q', 3, 0)
        self.layer.set_count('p', 0, 1)
        self.assertEqual(3, self.factory.values['q', layer.COUNT_QUERY])


class PlayerLayerResources(unittest.TestCase):
    def test_geometry_and_animation_have_no_player_bone_name_collisions(self):
        rp = ROOT / 'TwilightBossSliceR'
        geometry = json.loads((rp / 'models/entity/player_fortification.geo.json').read_text())['minecraft:geometry'][0]
        bones = geometry['bones']
        self.assertTrue(all(b['name'].startswith('tf_fortification_') for b in bones))
        original = json.loads((rp / 'models/entity/lich_entities.geo.json').read_text())['minecraft:geometry']
        original = next(g for g in original if g['description']['identifier'] == 'geometry.tf_slice.lich_shields')
        restored = copy.deepcopy(bones)
        for bone in restored:
            bone['name'] = bone['name'].replace('tf_fortification_', '', 1)
            if 'parent' in bone:
                bone['parent'] = bone['parent'].replace('tf_fortification_', '', 1)
        self.assertEqual(original['bones'], restored)
        animations = json.loads((rp / 'animations/player_fortification.animation.json').read_text())['animations']
        animation = animations['animation.tf_slice.player_fortification']
        self.assertTrue(set(animation['bones']) <= {b['name'] for b in bones})
        serialized = json.dumps(animation)
        self.assertIn('query.life_time', serialized)
        self.assertNotIn('tf_fortification_time', serialized)
        self.assertNotIn('position', serialized)

    def test_controllers_only_target_private_geometry_and_shield_bones(self):
        controllers = json.loads((ROOT / 'TwilightBossSliceR/render_controllers/player_fortification.render_controllers.json').read_text())['render_controllers']
        self.assertEqual(2, len(controllers))
        for controller in controllers.values():
            self.assertEqual('Geometry.tf_fortification_layer', controller['geometry'])
            self.assertTrue(all(next(iter(item)).startswith('tf_fortification_shield_')
                                for item in controller['part_visibility']))


if __name__ == '__main__':
    unittest.main()
