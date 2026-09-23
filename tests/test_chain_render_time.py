import json
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / 'TwilightBossSliceR'


def evaluate(expression, hand, position, yaw):
    for i, axis in enumerate('xyz'):
        expression = expression.replace('query.mod.tf_chain_world_' + axis, repr(hand[i]))
        expression = expression.replace('query.position(%d)' % i, repr(position[i]))
    expression = expression.replace('query.body_y_rotation', repr(yaw))
    expression = expression.replace('math.cos', 'cos').replace('math.sin', 'sin')
    return eval(expression, {'__builtins__': {}}, {
        'cos': lambda a: math.cos(math.radians(a)),
        'sin': lambda a: math.sin(math.radians(a)),
    })


class RenderTimeTests(unittest.TestCase):
    def test_historical_bug_is_explained_by_actual_queries_not_inferred_yaw(self):
        rows = json.loads((ROOT / 'tests/fixtures/chain_render_world_anchor_v2.json').read_text())
        # Preserve the rejected v2 formula as the historical failure oracle.
        dx = '(query.mod.tf_chain_world_x - query.position(0))'
        dz = '(query.mod.tf_chain_world_z - query.position(2))'
        expressions = [dx+' * math.cos(query.body_y_rotation) - '+dz+' * math.sin(query.body_y_rotation)',
                       'query.mod.tf_chain_world_y - query.position(1)',
                       '-'+dx+' * math.sin(query.body_y_rotation) - '+dz+' * math.cos(query.body_y_rotation)']
        for row in rows:
            if row['previousHand'] is None:
                continue
            origin, hand = row['origin'], row['previousHand']
            axes = [[point[i]-origin[i] for i in range(3)] for point in row['probes']]
            sample = row['animationSample']
            local = [evaluate(expr, hand, [sample[k] for k in 'xyz'], sample['yaw']) for expr in expressions]
            actual = [origin[i]+sum(axes[j][i]*local[j] for j in range(3)) for i in range(3)]
            for a,b in zip(actual,row['actualTail']): self.assertAlmostEqual(a,b,places=4)
        self.assertGreater(rows[3]['errorToCurrent'],6)

    def test_throw_visual_uses_per_owner_geometry_and_both_source_textures(self):
        path = RP / 'attachables/block_and_chain.attachable.json'
        self.assertTrue(path.is_file())
        desc = json.loads(path.read_text())['minecraft:attachable']['description']
        self.assertEqual('textures/items/block_and_chain', desc['textures']['default'])
        self.assertEqual('textures/items/block_and_chain_thrown', desc['textures']['thrown'])
        controller = json.loads((RP/'render_controllers/block_and_chain.render_controllers.json').read_text())
        encoded = json.dumps(controller)
        self.assertIn('query.mod.tf_chain_active ? Geometry.thrown : Geometry.default', encoded)
        geometries = json.loads((RP/'models/entity/block_and_chain_held.geo.json').read_text())['minecraft:geometry']
        self.assertEqual({'default','thrown'}, {bone['texture_meshes'][0]['texture']
                         for g in geometries for bone in g['bones'] if 'texture_meshes' in bone})
