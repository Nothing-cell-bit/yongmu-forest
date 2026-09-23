"""Startup regression: client-only actors need not expose Model bone positions.

These are adapter fault-injection tests, not evidence of NetEase rendering.
The fixed zero-yaw basis is taken from the recorded native zero-yaw sample.
"""
import json
import tempfile
import unittest
from pathlib import Path
from tests.test_chain_detached_visual import Engine, ROOT, RP, TRACE, visual


class ClientOnlyEngine(Engine):
    def __init__(self):
        super(ClientOnlyEngine, self).__init__()
        self.matrix_calls = []

    def spawn(self, identifier, pos, rot):
        entity = super(ClientOnlyEngine, self).spawn(identifier, pos, rot)
        if entity:
            row = TRACE[0]
            self.axes = tuple(tuple(p[i]-row['origin'][i] for i in range(3)) for p in row['probes'])
            for bone, axis in zip(visual.PROBES, self.axes):
                self.bones[entity][bone] = tuple(pos[i]+axis[i] for i in range(3))
        return entity

    def CreateModel(self, entity):
        if str(entity).startswith('visual-'):
            class UnsupportedClientModel(object):
                def GetBonePositionFromMinecraftObject(self, bone): return None
            return UnsupportedClientModel()
        return super(ClientOnlyEngine, self).CreateModel(entity)

    def CreateActorRender(self, entity):
        engine = self
        class ActorRender(object):
            def GetQueryableBoneOrientation(self, bone, isClientEntity=False):
                engine.matrix_calls.append((entity,bone,isClientEntity))
                return None  # optional diagnostics must not gate display
        return ActorRender()


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.engine = ClientOnlyEngine()
        self.now = [0]
        self.client = visual.ChainVisuals(self.engine, 'level', clock=lambda:self.now[0],
            create_visual=self.engine.spawn, destroy_visual=self.engine.destroy)
        self.client.receive({'projectileId':'head','ownerId':'player'})

    def ready(self):
        return self.engine.values.get((self.engine.carrier,visual.PREFIX+'ready'),0)

    def test_missing_client_bone_readback_does_not_permanently_hide_chain(self):
        self.client.render()
        self.assertEqual(0,self.ready())
        self.client.render()
        self.assertEqual(1,self.ready())
        for point,fraction in zip(self.engine.draw(),(.95,.75,.55,.35,.15)):
            for actual,target in zip(point,(fraction,2*fraction,3*fraction)):
                self.assertAlmostEqual(actual,target)
        self.engine.bones['head']['chain_origin']=(8,1,-2)
        self.client.render()
        for a,b in zip((1.35,1.95,2.75),self.engine.draw()[0]): self.assertAlmostEqual(a,b)

    def test_visible_head_bone_can_supply_origin_when_empty_probe_is_unavailable(self):
        self.engine.bones['head'].pop('chain_origin')
        self.engine.bones['head']['block']=(0,0,0)
        self.client.render(); self.client.render()
        self.assertEqual(1,self.ready())

    def test_hidden_links_do_not_hide_probe_bones(self):
        controller=json.loads((RP/'render_controllers/block_chain_link.render_controllers.json').read_text())
        parts=controller['render_controllers']['controller.render.tf_slice.block_chain_link']['part_visibility']
        self.assertNotIn('*',{key for entry in parts for key in entry})
        self.assertEqual({'chain_%d'%i for i in range(5)},{key for entry in parts for key in entry})

    def test_failed_creation_is_reported_with_projectile_and_owner(self):
        self.engine.fail_create=True
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.jsonl'; self.client.trace_path=str(path)
            for _ in range(30): self.client.render()
            rows=list(self.client.trace_records)
            self.client.clear()
            self.assertFalse(path.exists())
            failures=[r for r in rows if r.get('stage')=='create_failed']
            self.assertEqual(1,len(failures))
            self.assertEqual('head',failures[0]['projectile'])
            self.assertEqual('player',failures[0]['owner'])

    def test_readback_explicitly_uses_client_entity_matrix_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.client.trace_path=str(Path(tmp)/'trace.jsonl')
            self.client.render(); self.client.render()
            self.assertTrue(self.engine.matrix_calls)
            self.assertTrue(all(call[2] is True for call in self.engine.matrix_calls))
            self.client.clear()

    def test_unavailable_endpoints_log_raw_values_not_one_ambiguous_message(self):
        self.engine.bones['head']={}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.jsonl'; self.client.trace_path=str(path)
            self.client.render()
            rows=list(self.client.trace_records)
            self.client.clear()
            self.assertFalse(path.exists())
            failures=[r for r in rows if r.get('stage')=='endpoints_unavailable']
            self.assertTrue(failures)
            self.assertIsNone(failures[0]['head'])
            self.assertEqual([1,2,3],failures[0]['hand'])


if __name__ == '__main__': unittest.main()
