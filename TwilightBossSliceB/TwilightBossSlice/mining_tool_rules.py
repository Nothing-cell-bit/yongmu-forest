# -*- coding: utf-8 -*-
"""Preserve the upstream fractional ironwood speed through the native item API."""
import copy

FRACTIONAL_TOOL_SPEEDS = dict(
    ('tf_slice:ironwood_' + kind, 6.5)
    for kind in ('pickaxe', 'axe', 'shovel', 'hoe')
)

SHEARS_BLOCKS = (
    'tf_slice:canopy_leaves', 'tf_slice:dark_leaves', 'tf_slice:mangrove_leaves',
    'tf_slice:twilight_oak_leaves', 'tf_slice:rainbow_oak_leaves',
    'tf_slice:enchanted_canopy_leaves', 'tf_slice:enchanted_twilight_oak_leaves',
    'tf_slice:spooky_twilight_oak_leaves',
) + tuple('tf_slice:rainbow_oak_leaves_%02d' % index for index in range(16))


def register_shears(component):
    setter = getattr(component, 'SetShearsDestroyBlockSpeed', None)
    if not callable(setter):
        return False
    results = [setter(name, 15.0) for name in SHEARS_BLOCKS]
    return all(results)


def with_fractional_speed(item, component):
    if not isinstance(item, dict):
        return None
    name = item.get('newItemName', item.get('itemName', item.get('name', '')))
    speed = FRACTIONAL_TOOL_SPEEDS.get(name)
    if speed is None:
        return None
    current = (item.get('userData') or {}).get('ModTierSpeed')
    if isinstance(current, dict):
        current = current.get('__value__')
    if current == speed:
        return None
    result = copy.deepcopy(item)
    # SetItemTierSpeed takes a float and writes the engine-owned item data.
    # Do not manufacture NBT fields or replace an inventory slot twice.
    if component.SetItemTierSpeed(result, speed):
        return result
    return None
