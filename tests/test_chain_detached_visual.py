"""Replay real moving actor frames against an independent stationary carrier.

The oracle uses measured basis vectors, NOT a yaw inferred for the code under test.
It deliberately leaves actor query.position ahead of its rendered origin.
"""
import json
import math
import unittest
from pathlib import Path
from tests.test_chain_visual_frame import Factory, visual

ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / 'TwilightBossSliceR'
TRACE = json.loads((ROOT/'tests/fixtures/chain_render_world_anchor_v2.json').read_text())


class Engine(Factory):
    def __init__(self):
        super(Engine, self).__init__()
        self.created = []
        self.destroyed = []
        self.fail_create = False
        self.fail_destroy = False
        self.carrier = None
        self.query_positions = {}

    def spawn(self, identifier, pos, rot):
        self.created.append((identifier, pos, rot))
        if self.fail_create:
            return None
        entity = 'visual-%d' % len(self.created)
        # A fixed nontrivial reflected basis; no assumptions about Euler sign.
        self.axes = ((0.8,0,0.6), (0,1,0), (0.6,0,-0.8))
        self.bones[entity] = {'chain_origin': pos}
        for name, axis in zip(visual.PROBES, self.axes):
            self.bones[entity][name] = tuple(pos[i]+axis[i] for i in range(3))
        self.query_positions[entity] = pos
        self.carrier = entity
        return entity

    def destroy(self, entity):
        self.destroyed.append(entity)
        if self.fail_destroy:
            return False
        self.bones.pop(entity, None)
        return True

    def draw(self):
        """Evaluate the shipped animation, then apply the carrier's fixed matrix."""
        desc = json.loads((RP/'entity/block_chain_link.entity.json').read_text())['minecraft:client_entity']['description']
        name = desc['animations']['chain']
        bones = json.loads((RP/'animations/block_chain_projectile.animation.json').read_text())['animations'][name]['bones']
        origin = self.bones[self.carrier]['chain_origin']
        result = []
        for index in range(5):
            local = []
            for expression in bones['chain_%d' % index]['position']:
                for (entity,key), value in self.values.items():
                    if entity == self.carrier:
                        expression = expression.replace(key, repr(value))
                local.append(eval(expression, {'__builtins__': {}}, {}) / 16)
            point = tuple(origin[i]+sum(self.axes[j][i]*local[j] for j in range(3)) for i in range(3))
            self.bones[self.carrier]['chain_%d' % index] = point
            result.append(point)
        return result


class DetachedTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.now = [0]
        self.client = visual.ChainVisuals(self.engine, 'level', clock=lambda: self.now[0])
        self.client.create_visual = self.engine.spawn
        self.client.destroy_visual = self.engine.destroy
        self.client.receive({'projectileId':'head','ownerId':'player'})

    def ready(self):
        return self.engine.values.get((self.engine.carrier, visual.PREFIX+'ready'), 0)

    def test_real_trace_keeps_tail_at_hand_despite_projectile_yaw_and_position_gap(self):
        for row in TRACE:
            self.engine.bones['head'] = dict(zip(('chain_origin',)+visual.PROBES, [row['origin']]+row['probes']))
            self.engine.set_hand(tuple(row['targetHand']))
            self.engine.query_positions['head'] = tuple(row['animationSample'][k] for k in 'xyz')
            self.client.render()
            self.client.render()  # wait for first carrier matrix, not another server packet
            self.assertEqual(1, len(self.engine.created), 'chain must not inherit moving projectile root')
            self.assertEqual(1, self.ready())
            actual = self.engine.draw()
            for point, fraction in zip(actual, (.95,.75,.55,.35,.15)):
                expected = [row['origin'][i]+(row['targetHand'][i]-row['origin'][i])*fraction for i in range(3)]
                for a,b in zip(point,expected): self.assertAlmostEqual(a,b,places=5)

    def test_first_frame_is_hidden_then_spawn_frame_allows_delayed_readback(self):
        self.client.render()
        self.assertEqual(1,len(self.engine.created))
        self.assertEqual(0,self.ready())
        carrier_bones = self.engine.bones.pop(self.engine.carrier)
        self.client.render()
        self.assertEqual(1,self.ready())
        self.assertEqual('authored_spawn', self.client.entries['head']['basisSource'])
        self.engine.bones[self.engine.carrier] = carrier_bones
        self.client.render()
        self.assertEqual(1,self.ready())
        self.assertEqual('measured', self.client.entries['head']['basisSource'])

    def test_native_actor_links_are_always_hidden_even_with_stale_ready_query(self):
        bones=json.loads((RP/'animations/block_chain_projectile.animation.json').read_text())['animations']['animation.tf_slice.block_chain_projectile.chain']['bones']
        for bone in bones.values(): self.assertEqual(0,bone['scale'])

    def test_partial_update_hides_visual_and_recovers(self):
        self.client.render(); self.client.render()
        self.engine.fail_axis = visual.PREFIX+'hand_y'
        self.client.render()
        self.assertEqual(0,self.ready())
        self.engine.fail_axis = None
        self.client.render()
        self.assertEqual(1,self.ready())

    def test_remove_hides_and_destroys_only_client_carrier(self):
        self.client.render(); self.client.render()
        carrier=self.engine.carrier
        self.engine.fail_destroy=True
        self.client.receive({'projectileId':'head','removed':True})
        self.assertEqual(0,self.ready())
        self.assertNotIn('head',self.engine.destroyed)
        self.assertIn(carrier,self.engine.destroyed)
        self.engine.fail_destroy=False
        self.client.render()
        self.assertNotIn(carrier,self.engine.bones)
        self.assertFalse(self.client.entries)

    def test_timeout_cleans_visual_and_held_state(self):
        self.client.render(); self.client.render()
        self.now[0]=3
        self.client.render()
        self.assertIn(self.engine.carrier,self.engine.destroyed)
        self.assertEqual(0,self.engine.values[('player',visual.PREFIX+'active')])

    def test_creation_failure_retries_without_recreating_each_render_frame(self):
        self.engine.fail_create=True
        for _ in range(20): self.client.render()
        self.assertEqual(1,len(self.engine.created))
        self.engine.fail_create=False
        self.now[0]=1.1
        self.client.render(); self.client.render()
        self.assertEqual(1,self.ready())

    def test_bad_or_far_hand_does_not_flash_at_world_origin(self):
        for hand in ((float('nan'),2,3), (10000,2,3)):
            self.engine.set_hand(hand)
            self.client.render()
            self.assertEqual(0,self.ready())
        self.assertFalse(self.engine.created)

    def test_clear_resets_held_icon_and_removes_carrier(self):
        self.client.render(); self.client.render()
        self.client.clear()
        self.assertIn(self.engine.carrier,self.engine.destroyed)
        self.assertEqual(0,self.engine.values[('player',visual.PREFIX+'active')])

    def test_long_travel_reanchors_when_only_head_leaves_carrier_bounds(self):
        self.client.render(); self.client.render()
        old=self.engine.carrier
        self.engine.set_hand((21,2,3))
        self.engine.bones['head']['chain_origin']=(36,2,3)
        self.now[0]=1.1
        self.client.render()
        self.assertIn(old,self.engine.destroyed)
        self.client.render(); self.client.render()
        self.assertNotEqual(old,self.engine.carrier)
        for a,b in zip(self.engine.draw()[0],(21.75,2,3)): self.assertAlmostEqual(a,b)

    def test_unexpected_carrier_transform_is_not_used_as_a_moving_frame(self):
        self.client.render(); self.client.render()
        old=self.engine.carrier
        self.engine.bones[old]['chain_origin']=(8,2,3)
        self.client.render()
        self.assertIn(old,self.engine.destroyed)

    def test_wrong_factory_return_cannot_destroy_player_or_projectile(self):
        self.client.create_visual=lambda *args: 'player'
        self.client.render(); self.client.clear()
        self.assertFalse(self.engine.destroyed)

    def test_multiplayer_held_states_are_owner_specific(self):
        self.engine.bones['head2']=dict(self.engine.bones['head'])
        self.engine.set_hand((2,3,4),'other')
        self.client.receive({'projectileId':'head2','ownerId':'other'})
        self.client.render(); self.client.render()
        self.client.receive({'projectileId':'head','removed':True})
        self.assertEqual(0,self.engine.values[('player',visual.PREFIX+'active')])
        self.assertEqual(1,self.engine.values[('other',visual.PREFIX+'active')])
        self.client.clear()


if __name__ == '__main__': unittest.main()
