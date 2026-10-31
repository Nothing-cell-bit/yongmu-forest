"""Source-derived constraints for the opt-in block artwork layer."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from tools import block_texture_beautification as art


class ArtworkRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rp = self.root / 'TwilightBossSliceR'
        self.bank = self.root / 'resource_art/block_beautification/v1'
        self.bank.mkdir(parents=True)
        self.registry = {'schema_version':1,'enabled':True,'entries':[
            {'source_runtime_path':'textures/blocks/canopy_planks','source_kind':'project','output_relative':'blocks/canopy_planks.png'},
            {'source_runtime_path':'textures/blocks/leaves_spruce','source_kind':'builtin-base','output_relative':'base/leaves_spruce.png'},
        ]}
        (self.bank/'manifest.json').write_text(json.dumps(self.registry),encoding='utf-8')

    def test_only_twilight_external_terrain_reference_is_retargeted(self):
        value={'texture_data':{
            'tf_slice:canopy_leaves':{'textures':[{'path':'textures/blocks/leaves_spruce','tint_color':'#5BA059'}]},
            'leaves_spruce':{'textures':'textures/blocks/leaves_spruce'},
            'tf_slice:canopy_planks':{'textures':'textures/blocks/canopy_planks'},
            'door_upper':{'textures':['textures/blocks/door_wood_upper','textures/blocks/door_iron_upper']},
        }}
        result=art.normalize_resource_document(self.rp/'textures/terrain_texture.json',value)
        self.assertEqual('textures/tf_beautified/base/leaves_spruce',result['texture_data']['tf_slice:canopy_leaves']['textures'][0]['path'])
        self.assertEqual('#5BA059',result['texture_data']['tf_slice:canopy_leaves']['textures'][0]['tint_color'])
        self.assertEqual('textures/blocks/leaves_spruce',result['texture_data']['leaves_spruce']['textures'])
        self.assertEqual(value['texture_data']['door_upper'],result['texture_data']['door_upper'])
        self.assertEqual('textures/tf_beautified/blocks/canopy_planks',result['texture_data']['tf_slice:canopy_planks']['textures'])
        self.assertEqual('textures/blocks/canopy_planks',value['texture_data']['tf_slice:canopy_planks']['textures'])

    def test_behavior_and_unrelated_entity_resources_are_unchanged(self):
        value={'texture':'textures/blocks/leaves_spruce','other':'textures/entity/hydra4'}
        self.assertEqual(value,art.normalize_resource_document(self.root/'TwilightBossSliceB/netease_blocks/x.json',value))
        self.assertEqual(value,art.normalize_resource_document(self.rp/'entity/slime_blob.entity.json',value))

    def test_writer_routes_real_atlas_without_running_full_generator(self):
        from tools import build_public_block_shapes as builder
        target=self.rp/'textures/terrain_texture.json'
        builder.write_json(target,{'texture_data':{'tf_slice:canopy_planks':{'textures':'textures/blocks/canopy_planks'}}})
        result=json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual('textures/tf_beautified/blocks/canopy_planks',result['texture_data']['tf_slice:canopy_planks']['textures'])

    def test_knight_item_writer_keeps_registered_enhanced_icon_route(self):
        import importlib
        import sys
        from unittest import mock
        self.registry['entries'].append({
            'source_runtime_path':'textures/items/knightmetal_ingot',
            'source_kind':'project-item','output_relative':'items/knightmetal_ingot.png',
        })
        (self.bank/'manifest.json').write_text(json.dumps(self.registry),encoding='utf-8')
        project=Path(__file__).resolve().parents[1]
        with mock.patch.object(sys,'path',[str(project/'tools')]+sys.path):
            builder=importlib.import_module('tools.build_knight_stronghold_content')
        target=self.rp/'textures/item_texture.json'
        target.parent.mkdir(parents=True)
        builder._write(target,{'texture_data':{
            'tf_slice:knightmetal_ingot':{'textures':'textures/items/knightmetal_ingot'},
            'minecraft:iron_ingot':{'textures':'textures/items/iron_ingot'},
        }})
        result=json.loads(target.read_text(encoding='utf-8'))['texture_data']
        self.assertEqual('textures/tf_beautified/items/knightmetal_ingot',result['tf_slice:knightmetal_ingot']['textures'])
        self.assertEqual('textures/items/iron_ingot',result['minecraft:iron_ingot']['textures'])

    def test_missing_asset_bank_preserves_locked_original_output(self):
        value={'texture':'textures/blocks/canopy_planks'}
        self.assertEqual(value,art.normalize_resource_document(self.root/'isolated/TwilightBossSliceR/blocks.json',value))

    def test_engine_book_art_is_private_to_twilight_item_aliases(self):
        self.registry['entries'].append({
            'source_runtime_path':'textures/items/book_enchanted',
            'source_kind':'builtin-base','output_relative':'base/book_enchanted.png',
        })
        (self.bank/'manifest.json').write_text(json.dumps(self.registry),encoding='utf-8')
        value={'texture_data':{
            'tf_slice:fire_react_book_1':{'textures':'textures/items/book_enchanted'},
            'book_enchanted':{'textures':'textures/items/book_enchanted'},
        }}
        result=art.normalize_resource_document(self.rp/'textures/item_texture.json',value)
        self.assertEqual('textures/tf_beautified/base/book_enchanted',result['texture_data']['tf_slice:fire_react_book_1']['textures'])
        self.assertEqual('textures/items/book_enchanted',result['texture_data']['book_enchanted']['textures'])
        entity={'textures':{'default':'textures/items/book_enchanted'}}
        self.assertEqual(entity,art.normalize_resource_document(self.rp/'entity/unrelated.json',entity))

    def test_remaining_item_generators_keep_art_routes_and_behavior_documents(self):
        import importlib
        import sys
        from unittest import mock
        self.registry['entries'].append({
            'source_runtime_path':'textures/items/raven_feather',
            'source_kind':'project-item','output_relative':'items/raven_feather.png',
        })
        (self.bank/'manifest.json').write_text(json.dumps(self.registry),encoding='utf-8')
        project=Path(__file__).resolve().parents[1]
        value={'texture_data':{'tf_slice:raven_feather':{'textures':'textures/items/raven_feather'}}}
        for module_name,method in [
            ('build_dark_forest_content','write'),
            ('build_dark_tower_content','write'),
            ('build_ruin_dependencies','write_json'),
        ]:
            with self.subTest(generator=module_name):
                with mock.patch.object(sys,'path',[str(project/'tools')]+sys.path):
                    module=importlib.import_module('tools.'+module_name)
                writer=getattr(module,method)
                target=self.rp/'textures/item_texture.json'
                writer(target,value)
                result=json.loads(target.read_text(encoding='utf-8'))
                self.assertEqual('textures/tf_beautified/items/raven_feather',result['texture_data']['tf_slice:raven_feather']['textures'])
                behavior=self.root/'TwilightBossSliceB/items/test.json'
                writer(behavior,value)
                self.assertEqual(value,json.loads(behavior.read_text(encoding='utf-8')))

    def test_native_sign_client_overrides_use_engine_registered_block_ids(self):
        from tools import build_public_block_shapes as builder
        blocks={}
        builder.ensure_vanilla_adapter_client_blocks(blocks)
        for obsolete in ['dark_oak_sign','dark_oak_wall_sign','dark_oak_wall_hanging_sign','mangrove_sign','mangrove_wall_hanging_sign']:
            self.assertNotIn(obsolete,blocks)
        self.assertEqual('tf_slice:dark_planks',blocks['darkoak_standing_sign']['textures'])
        self.assertEqual('tf_slice:dark_planks',blocks['darkoak_wall_sign']['textures'])
        self.assertEqual('tf_slice:mangrove_planks',blocks['mangrove_standing_sign']['textures'])
        self.assertIn('dark_oak_hanging_sign',blocks)
        self.assertIn('mangrove_hanging_sign',blocks)

    def test_actual_asset_bank_preserves_source_dimensions_and_masks(self):
        project=Path(__file__).resolve().parents[1]
        bank,registered=art.registry(project)
        self.assertTrue(registered['enabled'])
        self.assertGreater(len(registered['entries']),0)
        for entry in registered['entries']:
            with Image.open(bank/'assets'/entry['output_relative']) as candidate, Image.open(bank/'source_baselines'/entry['output_relative']) as source:
                self.assertEqual(source.size,candidate.size,entry['output_relative'])
                if not entry.get('derived_icon'):
                    self.assertEqual(source.convert('RGBA').getchannel('A').tobytes(),candidate.convert('RGBA').getchannel('A').tobytes(),entry['output_relative'])
        with Image.open(bank/'assets/base/portal.png') as portal:
            self.assertEqual((16,512),portal.size)

    def test_model_baker_uses_overridden_material_without_changing_silhouette(self):
        from tools import build_public_block_shapes as builder
        red=self.root/'red.png';blue=self.root/'blue.png'
        Image.new('RGBA',(16,16),(220,20,20,255)).save(red)
        Image.new('RGBA',(16,16),(20,20,220,255)).save(blue)
        a=self.root/'a.png';b=self.root/'b.png'
        self.assertTrue(builder._render_java_item_model_icon('canopy_bookshelf',a,texture_resolver=lambda path:red))
        self.assertTrue(builder._render_java_item_model_icon('canopy_bookshelf',b,texture_resolver=lambda path:blue))
        with Image.open(a) as first,Image.open(b) as second:
            self.assertEqual((64,64),first.size)
            self.assertEqual(first.getchannel('A').tobytes(),second.getchannel('A').tobytes())
            self.assertNotEqual(first.convert('RGB').tobytes(),second.convert('RGB').tobytes())


if __name__ == '__main__':
    unittest.main()
