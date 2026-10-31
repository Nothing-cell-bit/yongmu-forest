"""Recipe-source coverage and the separate local Farmers Delight page."""
import importlib
import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen, Request
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

class FarmersAtlasTests(unittest.TestCase):
    def test_multi_output_crafting_preserves_returned_glass_bottle(self):
        atlas = importlib.import_module('build_farmers_recipe_atlas')
        rows = atlas.build_catalog()
        recipe = next(row for row in rows if row['id'] == 'fd_port:pie_crust_milk_bottle_001')
        self.assertEqual([(output['id'], output['count']) for output in recipe['outputs']],
                         [('fd_port:pie_crust', 1), ('minecraft:glass_bottle', 1)])

    def test_new_pot_meals_preserve_counts_and_container_rules(self):
        atlas = importlib.import_module('build_farmers_recipe_atlas')
        rows = atlas.build_catalog()
        rolls = next(row for row in rows if row['id'] == 'pot:dumplings')
        self.assertEqual(rolls['outputs'][0]['count'], 2)
        self.assertIn('不需要额外容器', rolls['note'])
        pumpkin = next(row for row in rows if row['id'] == 'pot:stuffed_pumpkin_block')
        self.assertIn('南瓜', pumpkin['note'])

    def test_catalog_covers_pack_and_runtime_processing(self):
        atlas = importlib.import_module('build_farmers_recipe_atlas')
        rows = atlas.build_catalog()
        pack_ids = {json.loads(p.read_text(encoding='utf-8'))[next(k for k in json.loads(p.read_text(encoding='utf-8')) if k.startswith('minecraft:recipe_'))]['description']['identifier'] for p in atlas.BP.joinpath('recipes').glob('*.json')}
        self.assertEqual({r['id'] for r in rows if r['source'].startswith('behavior_pack/recipes/')}, pack_ids)
        self.assertTrue({'shaped', 'shapeless', 'furnace', 'smithing', 'cutting', 'pot', 'stove', 'skillet', 'handheld'} <= {r['kind'] for r in rows})
        cuts = next(r for r in rows if r['id'] == 'cutting:minecraft:chicken')
        self.assertEqual([o['count'] for o in cuts['outputs']], [2, 1])
        pot = next(r for r in rows if r['id'] == 'pot:tomato_sauce')
        self.assertEqual(len(pot['inputs']), 2)
        self.assertIn('碗', pot['note'])
        self.assertEqual(len({r['id'] for r in rows}), len(rows))

    def test_server_serves_separate_page_and_rebuild(self):
        server_module = importlib.import_module('serve_recipe_atlas')
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            server = server_module.create_server(0, Path(tmp) / 'index.html')
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = 'http://127.0.0.1:%d' % server.server_address[1]
                main = urlopen(base).read().decode('utf-8')
                self.assertTrue('farmers-delight.html' in main)
                page = urlopen(base + '/farmers-delight.html').read().decode('utf-8')
                self.assertIn('农夫乐事', page)
                self.assertIn('id="recipe-data"', page)
                response = urlopen(Request(base + '/api/rebuild?mod=farmers-delight', method='POST', headers={'X-Recipe-Atlas-Request':'rebuild'}))
                self.assertGreater(json.load(response)['recipeCount'], 0)
                self.assertTrue((Path(tmp) / 'farmers-delight.html').is_file())
            finally:
                server.shutdown(); server.server_close(); thread.join(5)

if __name__ == '__main__': unittest.main()
