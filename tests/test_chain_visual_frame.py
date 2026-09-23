"""Endpoint tests independent of engine axis conventions and Euler order."""
import math
import sys
import unittest
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'TwilightBossSliceB' / 'TwilightBossSlice'))
import chain_visual_client as visual


class FrameTests(unittest.TestCase):
    def test_camera_grip_is_invariant_in_camera_coordinates(self):
        camera = (10, 63, -20)
        for forward in ((0,0,1),(1,0,0),(0,0,-1),(0,1,0),(0,-1,0)):
            hand = visual.first_person_grip(camera, forward, 70, True, 0)
            self.assertTrue(all(math.isfinite(v) for v in hand))
            self.assertGreater(sum((hand[i]-camera[i])*forward[i] for i in range(3)), 0)
        main = visual.first_person_grip(camera, (0,0,1), 70, True, 0)
        off = visual.first_person_grip(camera, (0,0,1), 70, False, 0)
        self.assertAlmostEqual(camera[0]*2, main[0]+off[0])
        self.assertEqual(main[1:], off[1:])
    def test_endpoint_roundtrip_for_rotated_and_reflected_render_bases(self):
        origin = (140, 63, -257)
        hand = (134, 65, -249)
        for yaw in (-179, -90, 0, 47, 179):
            for pitch in (-80, 0, 65):
                y, p = math.radians(yaw), math.radians(pitch)
                axes = ((math.cos(y), 0, -math.sin(y)),
                        (math.sin(y)*math.sin(p), math.cos(p), math.cos(y)*math.sin(p)),
                        (-math.sin(y)*math.cos(p), math.sin(p), -math.cos(y)*math.cos(p)))
                probes = [tuple(origin[i] + axis[i] for i in range(3)) for axis in axes]
                local = visual.local_endpoint(origin, probes, hand)
                for fraction in visual.LINK_FRACTIONS:
                    actual = [origin[i] + sum(axes[j][i]*local[j]/16 for j in range(3))*fraction for i in range(3)]
                    expected = [origin[i] + (hand[i]-origin[i])*fraction for i in range(3)]
                    for a, e in zip(actual, expected):
                        self.assertAlmostEqual(a, e, places=8)
        self.assertEqual(0.95, max(visual.LINK_FRACTIONS))

    def test_invalid_frame_is_hidden_instead_of_using_world_vector_as_local(self):
        self.assertIsNone(visual.local_endpoint((0,0,0), [(0,0,0)]*3, (1,2,3)))
        self.assertIsNone(visual.local_endpoint((0,0,0), [(1,0,0),(0,1,0),(0,0,1)], (float('nan'),0,0)))

    def test_nonuniform_scale_and_missing_bones(self):
        self.assertEqual((16,32,48), visual.local_endpoint(
            (0,0,0), [(2,0,0),(0,3,0),(0,0,-4)], (2,6,-12)))
        self.assertIsNone(visual.local_endpoint(None, [None]*3, None))
        self.assertIsNone(visual.local_endpoint((0,0,0), [(1,0,0),(0,1,0),(0,0,1)], (1000,0,0)))


class Factory(object):
    def __init__(self):
        self.values = {}
        self.registered = []
        self.bones = {
            'head': dict(zip(('chain_origin',) + visual.PROBES,
                             ((0,0,0),(1,0,0),(0,1,0),(0,0,-1)))),
            'player': {'rightitem': (1,2,3), 'leftitem': (-1,2,3)},
        }
        self.fail_axis = None
        self.perspective = 0
        self.eyes = {}
        self.rotations = {}
        self.molang = {}
        self.set_hand((1,2,3))

    def set_hand(self, point, entity='player'):
        # Existing lifecycle fixtures specify a virtual source hand. Put the
        # mock eye behind it at zero yaw; separate alignment tests use raw eyes.
        self.eyes[entity] = (point[0]+math.sin(.4),point[1]+.4,point[2]-math.cos(.4))
        self.rotations[entity] = (0,0)
        self.bones.setdefault(entity,{})['rightitem'] = point

    def CreatePos(self, entity):
        factory=self
        class Pos(object):
            def GetPos(self): return factory.eyes.get(entity)
        return Pos()

    def CreateRot(self, entity):
        factory=self
        class Rot(object):
            def GetRot(self): return factory.rotations.get(entity)
        return Rot()

    def CreatePlayerView(self, entity):
        factory = self
        class View(object):
            def GetPerspective(self):
                return factory.perspective
        return View()

    def CreateCamera(self, level):
        class Camera(object):
            def GetPosition(self): return (0, 2, 0)
            def GetForward(self): return (0, 0, 1)
            def GetCameraRotation(self): return (0, 0, 0)
            def GetFov(self): return 70
        return Camera()

    def CreateQueryVariable(self, entity):
        factory = self
        class Query(object):
            def GetMolangValue(self, name):
                return factory.molang.get((entity,name),0)
            def Register(self, name, default):
                factory.registered.append(name)
                return True
            def Set(self, name, value):
                if name == factory.fail_axis:
                    return False
                factory.values[(entity, name)] = value
                return True
        return Query()

    def CreateModel(self, entity):
        factory = self
        class Model(object):
            def GetBonePositionFromMinecraftObject(self, bone):
                # Transport fixtures store rendered head centers under their
                # historical chain_origin key; no physical-origin assumption.
                if bone == 'chain_head' and entity.startswith('head'):
                    bone = 'chain_origin'
                return factory.bones.get(entity, {}).get(bone)
        return Model()


class ClientLifecycleTests(unittest.TestCase):
    def test_hard_anchor_is_never_offset_by_previous_tail_or_prediction(self):
        self.client.entries['head']['lastHand'] = (0.8, 2, 3)
        self.factory.bones[self.factory.carrier]['chain_0'] = (0.8, 2, 3)
        self.client.render()
        self.assertEqual((1,2,3), tuple(self.value(a) for a in 'xyz'))
        self.factory.bones[self.factory.carrier]['chain_0'] = (-8, 4, 6)
        self.client.render()
        self.assertEqual((1,2,3), tuple(self.value(a) for a in 'xyz'))

    def test_diagnostics_read_actual_tail_and_preserve_previous_target_on_heartbeat(self):
        with tempfile.TemporaryDirectory() as temp:
            trace_path = Path(temp) / 'chain.jsonl'
            self.client.trace_path = str(trace_path)
            self.factory.bones[self.factory.carrier]['chain_0'] = (1, 2, 4)
            self.client.render()
            self.client.receive({'projectileId': 'head', 'ownerId': 'player'})
            self.now[0] = 0.2
            self.client.render()
            rows = list(self.client.trace_records)
            self.client.clear()
            self.assertFalse(trace_path.exists())
            samples = [row for row in rows if 'actualTail' in row]
            self.assertEqual(2, len(samples))
            self.assertEqual((1, 2, 4), samples[-1]['actualTail'])
            self.assertEqual((1, 2, 3), samples[-1]['previousHand'])
            expected = math.sqrt(.05**2 + .1**2 + 1.15**2)
            self.assertAlmostEqual(expected, samples[-1]['errorToPrevious'])
            self.assertFalse(self.client.trace_records)

    def test_diagnostic_sampling_is_capped(self):
        self.client.trace_path = 'not-written-during-render.jsonl'
        for i in range(130):
            self.now[0] = i * 0.2
            self.client.receive({'projectileId':'head', 'ownerId':'player'})
            self.client.render()
        self.assertEqual(120, self.client.trace_count)

    def test_all_views_keep_source_virtual_hand_independent_of_arm_bob(self):
        self.client.local_player = lambda: 'player'
        self.client.render()
        first = tuple(self.value(a) for a in 'xyz')
        self.factory.bones['player']['rightitem'] = (9, 9, 9)
        self.client.render()
        self.assertEqual(first, tuple(self.value(a) for a in 'xyz'))
        self.factory.perspective = 1
        self.client.render()
        self.assertEqual(first, tuple(self.value(a) for a in 'xyz'))

    def setUp(self):
        from tests.test_chain_detached_visual import Engine
        self.factory = Engine()
        self.now = [0]
        self.client = visual.ChainVisuals(self.factory, 'level', lambda: self.now[0],
                                         create_visual=self.factory.spawn,
                                         destroy_visual=self.factory.destroy)
        self.client.receive({'projectileId': 'head', 'ownerId': 'player'})
        self.client.render()  # creation is hidden; subsequent render reads its matrix

    def value(self, name, entity='head'):
        if name in ('x', 'y', 'z'):
            axis = 'xyz'.index(name)
            # These lifecycle assertions concern the hand anchor. Recover it
            # from the independently rendered source-offset first link.
            tail = self.factory.draw()[0][axis]
            head = self.factory.bones['head']['chain_origin'][axis]
            return round((tail - .05*head)/.95, 8)
        if entity == 'head':
            entity = self.factory.carrier
        return self.factory.values.get((entity, visual.PREFIX + name), 0)

    def test_hand_movement_updates_endpoint_without_a_new_server_packet(self):
        self.client.render()
        self.assertEqual((1,2,3), tuple(self.value(a) for a in 'xyz'))
        self.factory.set_hand((4,2,1))
        self.client.render()
        self.assertEqual((4,2,1), tuple(self.value(a) for a in 'xyz'))
        self.assertEqual(1, self.value('ready'))
        self.assertEqual(1, self.value('active', 'player'))

    def test_remove_and_dimension_clear_reset_held_state(self):
        self.client.render()
        self.client.receive({'projectileId': 'head', 'removed': True})
        self.assertFalse(self.client.entries)
        self.assertEqual(0, self.value('ready'))
        self.assertEqual(0, self.value('active', 'player'))
        self.client.receive({'projectileId':'head', 'ownerId':'player'})
        self.client.render()
        self.client.clear()
        self.assertEqual(0, self.value('active', 'player'))

    def test_missing_frame_recovers_then_times_out(self):
        saved = self.factory.bones.pop('head')
        self.client.render()
        self.assertEqual(0, self.value('ready'))
        self.factory.bones['head'] = saved
        self.client.render()
        self.assertEqual(1, self.value('ready'))
        self.now[0] = 3
        self.client.render()
        self.assertFalse(self.client.entries)
        self.assertEqual(0, self.value('active', 'player'))

    def test_partial_query_failure_does_not_display_mixed_coordinates(self):
        self.factory.fail_axis = visual.PREFIX + 'hand_y'
        self.client.render()
        self.assertEqual(0, self.value('ready'))

    def test_observer_and_offhand_use_owner_not_local_camera(self):
        self.client.receive({'projectileId':'head', 'ownerId':'player', 'mainHand':False})
        self.client.render()
        self.assertAlmostEqual(1+2*math.sin(.4), self.value('x'), places=7)

    def test_malformed_packet_does_not_create_entities(self):
        self.client.clear()
        self.client.receive({})
        self.client.receive({'projectileId':'head'})
        self.assertFalse(self.client.entries)


if __name__ == '__main__':
    unittest.main()
