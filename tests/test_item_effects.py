"""Player-visible equipment and food regressions, without starting Minecraft."""
import copy
import json
import sys
import types
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB/TwilightBossSlice'))
try:
    import item_effects as effects
except ImportError:
    effects = None


def item(name, **values):
    return dict(newItemName='tf_slice:' + name, count=1, **values)


class Host:
    def __init__(self):
        self._tick = 30
        self.held = item('fiery_sword')
        self.fires = []
        self.progress = []
        self.broadcasts = []
    def _carried_item(self, player): return self.held
    def _is_online_player(self, entity): return entity == 'player'
    def _get_online_players(self): return ['player']
    def _target_armor_points(self, entity): return 10
    def _set_entity_on_fire(self, entity, seconds): self.fires.append((entity, seconds))
    def _get_foot_pos(self, entity): return (1, 64, 2)
    def _get_dimension(self, entity): return 0
    def _grant_progress(self, player, key): self.progress.append(key); return True
    def _notify(self, *args): pass
    def BroadcastToAllClient(self, name, data): self.broadcasts.append((name, data))


class EffectsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(effects, 'Equipment effects runtime is missing')
        self.h = Host()
        self.armor = []
        self.slots = {0: [item('steeleaf_sword', durability=31, extraId='owner:abc')], 1: [], 2: []}
        self.writes = []
        self.sprinting = True
        self.cf = types.SimpleNamespace(
            CreateItem=lambda _: types.SimpleNamespace(
                GetPlayerAllItems=lambda pos, *a: self.slots[pos],
                SetPlayerAllItems=lambda updates: self.writes.append(updates) or {k: True for k in updates}),
            CreateQueryVariable=lambda _: types.SimpleNamespace(
                EvalMolangExpression=lambda _: {'value': 1 if self.sprinting else 0}))
        self.api = types.SimpleNamespace(GetMinecraftEnum=lambda: types.SimpleNamespace(
            ItemPosType=types.SimpleNamespace(INVENTORY=0, ARMOR=1, OFFHAND=2)))
        self.e = effects.ItemEffects(self.h, self.cf, self.api, 'level')

    def damage(self, **kw):
        args = dict(entityId='mob', srcId='player', damage=5, cause='entity_attack', projectileId=None)
        args.update(kw)
        self.e.on_damage(args)
        return args

    def test_both_fiery_tools_ignite_successful_melee_for_fifteen_seconds(self):
        for name in ('fiery_sword', 'fiery_pickaxe'):
            self.h.held = item(name)
            self.e.on_hurt(self.damage())
        self.assertEqual([('mob', 15), ('mob', 15)], self.h.fires)

    def test_cancelled_zero_projectile_and_nonfinite_hits_do_not_apply_weapon_effects(self):
        for extra in ({'damage': 0}, {'cancel': True}, {'cause': 'fire_tick'},
                      {'projectileId': 'arrow'}, {'damage': float('nan')}, {'damage': float('inf')}):
            self.e.on_hurt(self.damage(**extra))
        self.assertEqual([], self.h.fires)

    def test_charge_adds_seven_to_same_hit_only_while_sprinting(self):
        for name in ('gold_minotaur_axe', 'diamond_minotaur_axe'):
            self.h.held = item(name)
            self.assertEqual(12, self.damage()['damage'])
        self.sprinting = False
        self.assertEqual(5, self.damage()['damage'])
        self.assertEqual(5, self.damage(cause='projectile')['damage'])

    def test_knightmetal_bonus_uses_same_damage_event(self):
        self.h.held = item('knightmetal_sword')
        self.assertEqual(7, self.damage()['damage'])
        self.h.held = item('knightmetal_axe')
        self.assertEqual(5, self.damage()['damage'])
        self.h._target_armor_points = lambda _: 0
        self.assertEqual(7, self.damage()['damage'])

    def test_fiery_armor_source_probability_and_duration(self):
        for count, seconds in ((1, 2), (2, 5), (3, 7), (4, 10)):
            armor = [item('fiery_' + s) for s in ('helmet', 'chestplate', 'leggings', 'boots')[:count]]
            self.assertEqual(seconds, effects.fiery_retaliation(armor, count * 5 - 1))
            self.assertEqual(0, effects.fiery_retaliation(armor, count * 5))

    def test_equipped_fiery_armor_retaliates_only_after_positive_melee_damage(self):
        self.slots[1] = [item('fiery_chestplate')]
        args = dict(srcId='mob',entityId='player',damage=3,cause='entity_attack')
        with mock.patch.object(effects.random, 'randrange', return_value=0):
            self.e.on_hurt(args)
            self.e.on_hurt(dict(args,damage=0))
            self.e.on_hurt(dict(args,cause='fire_tick'))
        self.assertEqual([('mob',2)],self.h.fires)

    def test_bad_sprint_query_does_not_grant_free_charge_damage(self):
        self.h.held = item('diamond_minotaur_axe')
        self.cf.CreateQueryVariable = lambda _: types.SimpleNamespace(EvalMolangExpression=lambda _: {'error':'unsupported'})
        self.assertEqual(5,self.damage()['damage'])

    def test_inventory_read_failure_is_contained_to_one_player(self):
        self.h._get_online_players = lambda: ['broken','player']
        visited=[]
        def refresh(player):
            visited.append(player)
            if player=='broken':raise RuntimeError('read failure')
        self.e.refresh_inventory=refresh
        with mock.patch('builtins.print'):
            self.e.tick()
        self.assertEqual(['broken','player'],visited)

    def test_default_enchantments_preserve_item_metadata_and_are_applied_once(self):
        old = self.slots[0][0]
        self.e.refresh_inventory('player')
        result = self.writes[-1][(0, 0)]
        self.assertEqual([(14, 2)], result['enchantData'])
        self.assertEqual(31, result['durability'])
        self.assertIn('owner:abc', result['extraId'])
        self.assertNotIn('enchantData', old)
        self.slots[0][0] = result
        self.e.refresh_inventory('player')
        self.assertEqual(1, len(self.writes))
        # A grindstone must not become an infinite re-enchant exploit.
        result['enchantData'] = []
        self.e.refresh_inventory('player')
        self.assertEqual(1, len(self.writes))

    def test_existing_custom_enchantments_are_not_replaced(self):
        old = item('naga_leggings', enchantData=[(0, 4), (17, 3)], userData={'custom': 1})
        fixed = effects.with_default_enchantments(old)
        self.assertEqual(old['enchantData'], fixed['enchantData'])
        self.assertEqual(old['userData'], fixed['userData'])

    def test_all_source_default_enchantment_families_are_present(self):
        expected = {'naga_chestplate': [(1, 3)], 'naga_leggings': [(0, 3)],
                    'ironwood_helmet': [(8, 1)], 'ironwood_sword': [(17, 1)],
                    'steeleaf_chestplate': [(3, 2)], 'steeleaf_leggings': [(1, 2)],
                    'mazebreaker_pickaxe': [(15, 4), (17, 3), (18, 2)]}
        self.assertEqual(21, len(effects.DEFAULT_ENCHANTMENTS))
        for name, enchants in expected.items():
            self.assertEqual(enchants, effects.with_default_enchantments(item(name))['enchantData'])

    def test_only_eating_stroganoff_unlocks_progress(self):
        self.e.on_eat({'playerId': 'player', 'itemDict': item('meef_stroganoff')})
        self.assertEqual(['tf_meef_stroganoff_eaten'], self.h.progress)
        self.e.on_eat({'playerId': 'player', 'itemDict': item('cooked_meef')})
        self.assertEqual(1, len(self.h.progress))

    def test_hydra_chop_applies_regeneration_when_eaten(self):
        calls = []
        self.cf.CreateEffect = lambda player: types.SimpleNamespace(AddEffectToEntity=lambda *a: calls.append((player, a)))
        self.e.on_eat({'playerId': 'player', 'itemDict': item('hydra_chop')})
        self.assertEqual([('player', ('regeneration', 5, 0, True))], calls)

    def test_torchberry_reveal_has_source_chance_and_expires(self):
        with mock.patch.object(effects.random, 'random', return_value=0.74):
            self.e.on_eat({'playerId': 'player', 'itemDict': item('torchberries')})
        self.e.refresh_inventory = lambda _: None
        self.e.tick()
        self.assertEqual('TorchberryGlow', self.h.broadcasts[-1][0])
        self.h._tick = 180
        self.e.tick()
        self.assertEqual({}, self.e.glowing)
        with mock.patch.object(effects.random, 'random', return_value=0.75):
            self.e.on_eat({'playerId': 'player', 'itemDict': item('torchberries')})
        self.assertEqual({}, self.e.glowing)

    def test_smelting_operates_only_on_confirmed_block_drops(self):
        self.h.held = item('fiery_pickaxe')
        self.h._dropped_item = lambda e: {'newItemName':'minecraft:raw_iron','count':3}
        spawned, removed, queries = [], [], []
        def recipes(*args):
            queries.append(args)
            return [{'output':'minecraft:iron_ingot'}]
        self.cf.CreateRecipe = lambda _: types.SimpleNamespace(GetRecipesByInput=recipes)
        self.h.CreateEngineItemEntity = lambda *args: spawned.append(args) or 'cooked'
        self.h.DestroyEntity = lambda e: removed.append(e) or True
        args = dict(playerId='player', dimensionId=0, dropEntityIds=['drop1', 'drop2'])
        self.e.on_destroy_block(args)
        self.assertEqual(1, len(queries))
        self.assertEqual(['drop1', 'drop2'], removed)
        self.assertEqual(3, spawned[0][0]['count'])
        self.assertEqual('minecraft:iron_ingot', spawned[0][0]['newItemName'])
        self.h.CreateEngineItemEntity = lambda *a: None
        self.e.on_destroy_block(args)
        self.assertEqual(['drop1', 'drop2'], removed)
        self.h.held = item('ironwood_pickaxe')
        self.e.on_destroy_block(args)
        self.assertEqual(2, len(spawned))

    def test_failed_original_drop_removal_rolls_back_replacement(self):
        self.h.held = item('fiery_pickaxe')
        self.h._dropped_item = lambda _: {'newItemName':'minecraft:raw_iron','count':1}
        self.cf.CreateRecipe = lambda _: types.SimpleNamespace(GetRecipesByInput=lambda *a: [{'output':'minecraft:iron_ingot'}])
        self.h.CreateEngineItemEntity = lambda *a: 'new'
        removed = []
        self.h.DestroyEntity = lambda e: removed.append(e) or False
        self.e.on_destroy_block(dict(playerId='player',dimensionId=0,dropEntityIds=['old']))
        self.assertEqual(['old','new'], removed)

    def test_smelting_preserves_fortune_drop_count_and_ignores_no_recipe(self):
        original = {'newItemName': 'minecraft:raw_iron', 'count': 3, 'newAuxValue': 0}
        cooked = effects.smelted_stack(original, [{'output': 'minecraft:iron_ingot'}])
        self.assertEqual('minecraft:iron_ingot', cooked['newItemName'])
        self.assertEqual(3, cooked['count'])
        self.assertIsNone(effects.smelted_stack(original, []))
        self.assertEqual('minecraft:raw_iron', original['newItemName'])


class ItemDefinitionsTests(unittest.TestCase):
    def components(self, name):
        return json.loads((ROOT/'TwilightBossSliceB/items'/(name+'.item.json')).read_text(encoding='utf8'))['minecraft:item']['components']

    def test_stroganoff_can_be_eaten_when_full(self):
        self.assertTrue(self.components('meef_stroganoff')['minecraft:food'].get('can_always_eat'))

    def test_food_container_and_effect_fields_use_current_format(self):
        comp=self.components('meef_stroganoff')
        self.assertEqual('minecraft:bowl',comp['minecraft:food']['using_converts_to'])
        self.assertNotIn('minecraft:using_converts_to',comp)
        self.assertNotIn('effects',self.components('hydra_chop')['minecraft:food'])

    def test_fiery_gear_and_boss_food_are_fireproof_as_drops(self):
        for name in ('fiery_sword','fiery_pickaxe','fiery_helmet','fiery_chestplate',
                     'fiery_leggings','fiery_boots','hydra_chop','meef_stroganoff'):
            self.assertTrue(self.components(name)['minecraft:fire_resistant']['value'])

    def test_torchberries_are_zero_nutrition_and_always_edible(self):
        food = self.components('torchberries')['minecraft:food']
        self.assertEqual(0, food['nutrition'])
        self.assertTrue(food.get('can_always_eat'))

    def test_phantom_armor_survives_death_without_a_charm(self):
        import textwrap
        source = (ROOT/'TwilightBossSliceB/TwilightBossSlice/serverSystem.py').read_text(encoding='utf8')
        body = '    def OnRoutePlayerDie(' + source.split('    def OnRoutePlayerDie(',1)[1].split('\n    def ',1)[0]
        pos = types.SimpleNamespace(INVENTORY=0,ARMOR=1,OFFHAND=2,CARRIED=3)
        writes = []
        cf = types.SimpleNamespace(CreateGame=lambda _: types.SimpleNamespace(GetPlayerGameType=lambda _: 0),
                                   CreateItem=lambda _: types.SimpleNamespace(SetPlayerAllItems=lambda x:writes.append(x)))
        api = types.SimpleNamespace(GetMinecraftEnum=lambda:types.SimpleNamespace(ItemPosType=pos))
        ns = dict(CF=cf,serverApi=api,LEVEL_ID='level',copy=copy,portal_logic=effects.portal_logic)
        exec(textwrap.dedent(body),ns)
        entries = [{'posType':1,'slot':0,'item':item('phantom_helmet')},
                   {'posType':0,'slot':2,'item':item('phantom_chestplate')},
                   {'posType':0,'slot':3,'item':item('ironwood_sword')}]
        h = types.SimpleNamespace(_clear_player_fortification=lambda _:None,_keep_inventory_rule=lambda:False,
            _keeping_inventory_entries=lambda _:entries,_keeping_tier=lambda _:0,
            _keeping_snapshots={},_persist_keeping_snapshots=lambda:None)
        ns['OnRoutePlayerDie'](h,{'playerId':'player'})
        self.assertEqual({(1,0):None,(0,2):None},writes[0])
        self.assertEqual(2,len(h._keeping_snapshots['player']['entries']))

    def test_tools_can_receive_their_native_enchantments(self):
        for family in ('ironwood', 'steeleaf'):
            for role in ('sword', 'axe', 'pickaxe', 'shovel', 'hoe'):
                self.assertIn('minecraft:enchantable', self.components(family+'_'+role))

    def test_eating_event_is_registered_and_try_use_does_not_grant_food_progress(self):
        source = (ROOT/'TwilightBossSliceB/TwilightBossSlice/serverSystem.py').read_text(encoding='utf8')
        self.assertTrue('"PlayerEatFoodServerEvent"' in source)
        method = source.split('    def OnHydraRouteItemTryUseEvent(', 1)[1].split('\n    def ', 1)[0]
        self.assertNotIn('tf_meef_stroganoff_eaten', method)


if __name__ == '__main__': unittest.main()
