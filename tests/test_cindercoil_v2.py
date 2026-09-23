import json
import unittest
import importlib.util
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / 'TwilightBossSliceR'


class CindercoilV2Tests(unittest.TestCase):
    def test_every_visible_face_has_explicit_opaque_uv(self):
        for stem, texture in [('forest_wyrm', 'nagahead'), ('forest_wyrm_segment', 'nagasegment')]:
            geometries = json.loads((RP / 'models/entity' / (stem + '.geo.json')).read_text())['minecraft:geometry']
            if stem == 'forest_wyrm':
                geometries = geometries[:1]
            with Image.open(RP / 'textures/entity' / (texture + '.png')) as atlas:
                for bone in [b for g in geometries for b in g['bones']]:
                    for cube in bone.get('cubes', []):
                        self.assertIsInstance(cube['uv'], dict, bone['name'])
                        for face in cube['uv'].values():
                            x, y = face['uv']; w, h = face['uv_size']
                            self.assertTrue(0 <= x < x + w <= atlas.width)
                            self.assertTrue(0 <= y < y + h <= atlas.height)
                            self.assertEqual((255, 255), atlas.getchannel('A').crop((x,y,x+w,y+h)).getextrema(), bone['name'])

    def test_head_states_gate_all_parts(self):
        controllers = json.loads((RP / 'render_controllers/forest_wyrm.render.json').read_text())['render_controllers']
        for controller in controllers.values():
            self.assertIn('*', controller['part_visibility'][0])

    def test_no_resting_head_parts_penetrate_ground(self):
        from tools.render_entity_geo_preview import cube_vertices, transformed_point
        geometry = json.loads((RP / 'models/entity/forest_wyrm.geo.json').read_text())['minecraft:geometry'][0]
        bones = {b['name']:b for b in geometry['bones']}
        for bone in bones.values():
            for cube in bone['cubes']:
                for point in cube_vertices(cube):
                    self.assertGreaterEqual(transformed_point(point,bone['name'],bones,{})[1], 0, bone['name'])

    def test_eyes_close_with_solid_material(self):
        doc = json.loads((RP / 'models/entity/forest_wyrm.geo.json').read_text())
        with Image.open(RP / 'textures/entity/nagahead_dazed.png') as atlas:
            for bone in doc['minecraft:geometry'][1]['bones']:
                for cube in bone.get('cubes', []):
                    self.assertIsInstance(cube['uv'], dict)
                    uv = cube['uv']['north']; x,y = uv['uv']; w,h = uv['uv_size']
                    self.assertEqual((255,255), atlas.getchannel('A').crop((x,y,x+w,y+h)).getextrema())


class TailVariantTests(unittest.TestCase):
    def test_tail_reassignment_retries_and_does_not_spam_events(self):
        path = ROOT / 'TwilightBossSliceB/TwilightBossSlice/cindercoil_visuals.py'
        spec = importlib.util.spec_from_file_location('cindercoil_visuals', path)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        cache = {}; calls = []
        def trigger(entity, event):
            calls.append((entity,event)); return True
        mod.refresh_segments(['a','b','c'], 3, cache, trigger)
        self.assertEqual(cache, {'a':'body','b':'taper','c':'tail'})
        mod.refresh_segments(['a','b','c'], 3, cache, trigger)
        self.assertEqual(len(calls), 3)
        mod.refresh_segments(['a','b',None], 2, cache, trigger)
        self.assertEqual(cache, {'a':'taper','b':'tail'})
        mod.refresh_segments(['a',None,None], 1, cache, lambda e,v:False)
        self.assertEqual(cache['a'], 'taper')
        mod.refresh_segments(['a',None,None], 1, cache, trigger)
        self.assertEqual(cache, {'a':'tail'})
        def broken(entity, event):
            raise RuntimeError('entity unloaded')
        mod.refresh_segments(['a', 'd', None], 2, cache, broken)
        self.assertEqual(cache, {'a':'tail'})
        mod.refresh_segments([], 0, cache, trigger)
        self.assertEqual(cache, {})

    def test_visual_variants_resolve_to_real_geometry(self):
        bp = ROOT / 'TwilightBossSliceB'
        server = json.loads((bp / 'entities/forest_wyrm_segment.entity.json').read_text())['minecraft:entity']
        client = json.loads((RP / 'entity/forest_wyrm_segment.entity.json').read_text())['minecraft:client_entity']['description']
        geos = json.loads((RP / 'models/entity/forest_wyrm_segment.geo.json').read_text())['minecraft:geometry']
        ids = {g['description']['identifier'] for g in geos}
        for index, role in enumerate(('body','taper','tail')):
            event = 'tf_slice:visual_' + role
            group = server['events'][event]['add']['component_groups'][0]
            self.assertEqual(server['component_groups'][group]['minecraft:variant']['value'], index)
            self.assertIn(client['geometry']['default' if role=='body' else role], ids)


if __name__ == '__main__':
    unittest.main()
