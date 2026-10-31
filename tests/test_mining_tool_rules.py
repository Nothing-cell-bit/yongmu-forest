import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from TwilightBossSlice import mining_tool_rules
from TwilightBossSlice import item_effects


class ItemBoundary:
    def __init__(self, items):
        self.items = items
        self.writes = []

    def GetPlayerAllItems(self, position, extra):
        return self.items if position == 0 else []

    def SetItemTierSpeed(self, stack, speed):
        stack.setdefault('userData', {})['ModTierSpeed'] = {'__type__': 5, '__value__': speed}
        return True

    def SetPlayerAllItems(self, updates):
        self.writes.append(updates)


def test_fractional_speed_preserves_every_existing_stack_field():
    original = {'newItemName': 'tf_slice:ironwood_pickaxe', 'count': 1, 'durability': 219,
                'enchantData': [(15, 4)], 'extraId': 'owner:abc',
                'userData': {'custom': {'__type__': 8, '__value__': 'kept'}}}
    before = copy.deepcopy(original)
    result = mining_tool_rules.with_fractional_speed(original, ItemBoundary([]))
    assert original == before
    assert result['userData']['ModTierSpeed']['__value__'] == 6.5
    result['userData'].pop('ModTierSpeed')
    assert result == original


def test_real_inventory_refresh_merges_enchantments_and_speed_in_one_slot_write():
    from types import SimpleNamespace
    boundary = ItemBoundary([{'newItemName': 'tf_slice:ironwood_pickaxe', 'count': 1,
                              'durability': 219, 'extraId': 'owner:abc'}])
    host = SimpleNamespace()
    factory = SimpleNamespace(CreateItem=lambda player: boundary)
    api = SimpleNamespace(GetMinecraftEnum=lambda: SimpleNamespace(ItemPosType=SimpleNamespace(INVENTORY=0, ARMOR=1, OFFHAND=2)))
    runtime = item_effects.ItemEffects(host, factory, api, 'level')
    runtime.refresh_inventory('player')
    assert len(boundary.writes) == 1
    assert set(boundary.writes[0]) == {(0, 0)}
    stack = boundary.writes[0][(0, 0)]
    assert stack['durability'] == 219
    assert stack['enchantData']
    assert stack['userData']['ModTierSpeed']['__value__'] == 6.5
    boundary.items = [stack]
    runtime.refresh_inventory('player')
    assert len(boundary.writes) == 1


def test_native_speed_failure_never_replaces_a_stack():
    class Failure:
        def SetItemTierSpeed(self, item, speed):
            return False
    assert mining_tool_rules.with_fractional_speed({'itemName': 'tf_slice:ironwood_axe'}, Failure()) is None
    assert mining_tool_rules.with_fractional_speed({'itemName': 'minecraft:diamond_pickaxe'}, Failure()) is None


def test_real_tick_registers_native_shears_for_all_locked_leaf_aliases_once():
    from types import SimpleNamespace
    calls = []
    boundary = SimpleNamespace(SetShearsDestroyBlockSpeed=lambda name, speed: calls.append((name, speed)) or True)
    host = SimpleNamespace(_tick=30, _get_online_players=lambda: [])
    runtime = item_effects.ItemEffects(host, SimpleNamespace(CreateItem=lambda level: boundary), None, 'level')
    runtime.tick()
    assert runtime._mining_tools_registered is True
    assert len(calls) == len(set(mining_tool_rules.SHEARS_BLOCKS)) == 24
    assert all(speed == 15.0 for name, speed in calls)
    host._tick = 60
    runtime.tick()
    assert len(calls) == 24


def test_fractional_and_shears_runtime_tables_match_frozen_upstream_evidence():
    import json
    data = json.loads((ROOT / 'source_locks/block_mining_contract.json').read_text('utf-8'))
    assert set(mining_tool_rules.SHEARS_BLOCKS) == set(data['shears_speeds'])
    assert mining_tool_rules.FRACTIONAL_TOOL_SPEEDS == {
        name: spec['speed'] for name, spec in data['items'].items() if spec['speed'] != int(spec['speed'])}
