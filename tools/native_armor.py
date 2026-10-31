"""NetEase armor registration with source-locked, user-approved integer toughness.

Native armor belongs in netease_items_beh, not the modern wearable schema.
The 2026-10-20 integer allocation preserves complete-set toughness; fractional
upstream values cannot be preserved for every mixed set. See docs/armor_parity_20261020.md.
"""
import json
from pathlib import Path


# Slot, protection, native toughness, max durability, enchantability.
# Durability multipliers and attributes: locked TwilightArmorMaterial 4.3.2508.
ARMOR = {
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


def behavior_document(name):
    slot, defense, toughness, durability, enchantment = ARMOR[name]
    components = {
        'minecraft:max_stack_size': 1,
        'minecraft:max_damage': durability,
        'netease:armor': {
            'defense': defense, 'enchantment': enchantment,
            'armor_slot': slot, 'toughness': toughness,
            'knockback_resistance': 0.0,
        },
    }
    if name.startswith('fiery_'):
        components['netease:fire_resistant'] = {'value': True}
    return {'format_version': '1.10', 'minecraft:item': {
        'description': {'identifier': 'tf_slice:' + name,
                        'custom_item_type': 'armor', 'category': 'equipment'},
        'components': components,
    }}


def resource_document(name):
    if name not in ARMOR:
        raise KeyError(name)
    return {'format_version': '1.10', 'minecraft:item': {
        'description': {'identifier': 'tf_slice:' + name, 'category': 'equipment'},
        'components': {'minecraft:icon': 'tf_slice:' + name},
    }}


def write_armor(bp, rp, name, writer):
    """Called only by an authorized content build; tests use isolated folders."""
    bp, rp = Path(bp), Path(rp)
    obsolete = bp / 'items' / (name + '.item.json')
    if obsolete.exists():
        item = json.loads(obsolete.read_text('utf-8-sig'))['minecraft:item']
        if item['description']['identifier'] != 'tf_slice:' + name:
            raise ValueError('Refusing to remove an unrelated item: ' + str(obsolete))
    writer(bp / 'netease_items_beh' / (name + '.item.json'), behavior_document(name))
    writer(rp / 'netease_items_res' / (name + '.item.json'), resource_document(name))
    if obsolete.exists():
        obsolete.unlink()
