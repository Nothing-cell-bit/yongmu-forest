"""Source-locked armor properties through the actual NetEase registration files."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
BP = ROOT / 'TwilightBossSliceB'
RP = ROOT / 'TwilightBossSliceR'

# Slot, defense, integer toughness (user-approved), durability, enchantability.
EXPECTED = {
    'fiery_helmet': (0, 4, 2, 275, 10),
    'fiery_chestplate': (1, 9, 2, 400, 10),
    'fiery_leggings': (2, 7, 1, 375, 10),
    'fiery_boots': (3, 4, 1, 325, 10),
    'naga_chestplate': (1, 7, 1, 336, 15),
    'naga_leggings': (2, 6, 0, 315, 15),
    'phantom_helmet': (0, 3, 3, 330, 8),
    'phantom_chestplate': (1, 8, 2, 480, 8),
    'knightmetal_helmet': (0, 3, 1, 220, 8),
    'knightmetal_chestplate': (1, 8, 1, 320, 8),
    'knightmetal_leggings': (2, 6, 1, 300, 8),
    'knightmetal_boots': (3, 3, 1, 260, 8),
}


def load(path):
    return json.loads(path.read_text('utf-8-sig'))


class NativeArmorContractTests(unittest.TestCase):
    def test_catalog_rebuild_removes_native_references_without_hiding_native_items(self):
        import build_creative_catalog as builder
        import native_armor
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bp = root / 'TwilightBossSliceB'
            (bp / 'netease_items_beh').mkdir(parents=True)
            for name in EXPECTED:
                (bp / 'netease_items_beh' / (name+'.json')).write_text(
                    json.dumps(native_armor.behavior_document(name)), 'utf-8')
            path = bp / 'item_catalog/crafting_item_catalog.json'
            path.parent.mkdir()
            path.write_text(json.dumps({'minecraft:crafting_items_catalog': {'categories': [
                {'category_name':'equipment', 'groups':[{'items':['tf_slice:'+n for n in EXPECTED]}]}]}}),'utf-8')
            builder.normalize_creative_catalog(root)
            ids = [i for c in load(path)['minecraft:crafting_items_catalog']['categories']
                   for g in c['groups'] for i in g['items']]
            self.assertFalse(set('tf_slice:'+n for n in EXPECTED) & set(ids))
            for name in EXPECTED:
                self.assertEqual('equipment',load(bp/'netease_items_beh'/(name+'.json'))['minecraft:item']['description']['category'])

    def test_localization_rebuild_keeps_native_armor_names(self):
        import build_localization
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'TwilightBossSliceB/netease_items_beh'
            target.mkdir(parents=True)
            for name in EXPECTED:
                shutil.copy2(BP / 'netease_items_beh' / (name + '.item.json'), target)
            build_localization.build_localization(root)
            for language in ('en_US', 'zh_CN'):
                text = (root / 'TwilightBossSliceR/texts' / (language + '.lang')).read_text('utf-8')
                for name in EXPECTED:
                    self.assertIn('item.tf_slice:' + name + '.name=', text)

    def test_content_builder_entries_keep_native_ownership_after_rebuild(self):
        import build_hydra_route_content as hydra
        import build_knight_stronghold_content as knight
        for builder, names in [(hydra, [n for n in EXPECTED if n.startswith('fiery_')]),
                               (knight, [n for n in EXPECTED if n.startswith(('knightmetal_', 'phantom_'))])]:
            with tempfile.TemporaryDirectory() as directory:
                bp, rp = Path(directory) / 'TwilightBossSliceB', Path(directory) / 'TwilightBossSliceR'
                (bp / 'items').mkdir(parents=True)
                with mock.patch.object(builder, 'BP', bp), mock.patch.object(builder, 'RP', rp):
                    for name in names:
                        old = bp / 'items' / (name + '.item.json')
                        old.write_text(json.dumps({'minecraft:item': {'description': {'identifier': 'tf_slice:' + name}}}), 'utf-8')
                        if builder is hydra:
                            builder.write_item_definition(name)
                        else:
                            builder.write_item_definition(name, (1, None, EXPECTED[name][3]))
                        self.assertFalse(old.exists(), name)
                        self.assertEqual(load(BP / 'netease_items_beh' / (name + '.item.json')),
                                         load(bp / 'netease_items_beh' / (name + '.item.json')), name)
                        self.assertEqual(load(RP / 'netease_items_res' / (name + '.item.json')),
                                         load(rp / 'netease_items_res' / (name + '.item.json')), name)

    def test_catalog_resolver_and_normalizer_support_native_registration(self):
        from build_creative_catalog import _registered_categories, normalize_catalog_owned_description
        registered = _registered_categories(BP)
        for name in EXPECTED:
            path = BP / 'netease_items_beh' / (name + '.item.json')
            document = load(path)
            self.assertIn('tf_slice:' + name, registered)
            self.assertEqual(document, normalize_catalog_owned_description(path, document))

    def test_writer_rejects_an_unrelated_obsolete_item_before_any_writes(self):
        import native_armor
        with tempfile.TemporaryDirectory() as directory:
            bp, rp = Path(directory) / 'bp', Path(directory) / 'rp'
            (bp / 'items').mkdir(parents=True)
            old = bp / 'items/fiery_helmet.item.json'
            old.write_text(json.dumps({'minecraft:item': {'description': {'identifier': 'other:helmet'}}}), 'utf-8')
            writer = mock.Mock()
            with self.assertRaises(ValueError):
                native_armor.write_armor(bp, rp, 'fiery_helmet', writer)
            writer.assert_not_called()
            self.assertTrue(old.exists())

    def test_native_registration_properties_and_no_duplicate_modern_owner(self):
        for name, (slot, defense, toughness, durability, enchant) in EXPECTED.items():
            with self.subTest(name=name):
                path = BP / 'netease_items_beh' / (name + '.item.json')
                self.assertTrue(path.is_file(), str(path))
                item = load(path)['minecraft:item']
                self.assertEqual('tf_slice:' + name, item['description']['identifier'])
                self.assertEqual('armor', item['description']['custom_item_type'])
                components = item['components']
                self.assertEqual({'armor_slot': slot, 'defense': defense,
                                  'toughness': toughness, 'enchantment': enchant,
                                  'knockback_resistance': 0.0}, components['netease:armor'])
                self.assertIs(type(components['netease:armor']['toughness']), int)
                self.assertEqual(durability, components['minecraft:max_damage'])
                self.assertEqual(1, components['minecraft:max_stack_size'])
                self.assertNotIn('minecraft:wearable', components)
                self.assertFalse((BP / 'items' / (name + '.item.json')).exists())

    def test_native_resource_binding_preserves_icon_attachable_and_catalog(self):
        catalog = load(BP / 'item_catalog/crafting_item_catalog.json')['minecraft:crafting_items_catalog']
        identifiers = [i for c in catalog['categories'] for g in c['groups'] for i in g['items']]
        atlas = load(RP / 'textures/item_texture.json')['texture_data']
        languages = [(RP / 'texts' / (language + '.lang')).read_text('utf-8-sig')
                     for language in ('zh_CN', 'en_US')]
        for name in EXPECTED:
            with self.subTest(name=name):
                path = RP / 'netease_items_res' / (name + '.item.json')
                self.assertTrue(path.is_file(), str(path))
                item = load(path)['minecraft:item']
                identifier = 'tf_slice:' + name
                self.assertEqual(identifier, item['description']['identifier'])
                self.assertEqual(identifier, item['components']['minecraft:icon'])
                self.assertIn(identifier, atlas)
                for text in languages:
                    self.assertIn('item.' + identifier + '.name=', text)
                self.assertNotIn(identifier, identifiers)
                self.assertEqual('equipment', item['description']['category'])
                behavior = load(BP / 'netease_items_beh' / (name + '.item.json'))
                self.assertEqual('equipment', behavior['minecraft:item']['description']['category'])
                attachable = load(RP / 'attachables' / (name + '.attachable.json'))
                self.assertEqual(identifier, attachable['minecraft:attachable']['description']['identifier'])

    def test_set_totals_and_native_fireproof_items(self):
        for family, total in [('fiery', 6), ('naga', 1), ('phantom', 5), ('knightmetal', 4)]:
            values = [load(BP / 'netease_items_beh' / (n + '.item.json'))['minecraft:item']['components']
                      for n in EXPECTED if n.startswith(family + '_')]
            self.assertEqual(total, sum(c['netease:armor']['toughness'] for c in values))
            if family == 'fiery':
                self.assertTrue(all(c['netease:fire_resistant']['value'] for c in values))

    def test_full_current_defensive_armor_inventory_is_covered(self):
        names = set()
        for folder in ('items', 'netease_items_beh'):
            for path in (BP / folder).glob('*.json'):
                item = load(path).get('minecraft:item', {})
                components = item.get('components', {})
                if (components.get('minecraft:wearable', {}).get('protection', 0) > 0
                        or 'netease:armor' in components):
                    names.add(item['description']['identifier'].split(':')[1])
        unchanged = {f + '_' + s for f in ('ironwood', 'steeleaf')
                     for s in ('helmet', 'chestplate', 'leggings', 'boots')}
        self.assertEqual(set(EXPECTED) | unchanged, names)

    def test_zero_toughness_families_keep_locked_source_attributes(self):
        for family, enchant, durability_factor, defense in [
                ('ironwood', 15, 20, (2, 7, 5, 2)),
                ('steeleaf', 9, 10, (3, 8, 6, 3))]:
            for suffix, slot, base, protection in zip(
                    ('helmet', 'chestplate', 'leggings', 'boots'),
                    ('head', 'chest', 'legs', 'feet'), (11, 16, 15, 13), defense):
                name = family + '_' + suffix
                components = load(BP / 'items' / (name + '.item.json'))['minecraft:item']['components']
                self.assertEqual({'slot': 'slot.armor.' + slot, 'protection': protection},
                                 components['minecraft:wearable'], name)
                self.assertEqual(base * durability_factor, components['minecraft:durability']['max_durability'], name)
                self.assertEqual(enchant, components['minecraft:enchantable']['value'], name)


if __name__ == '__main__':
    unittest.main()
