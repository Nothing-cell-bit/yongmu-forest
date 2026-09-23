# -*- coding: utf-8 -*-
"""Equipment effects from Twilight Forest 4.3.2508; Python 2 compatible."""
import copy
import random

from TwilightBossSlice import portal_logic, knight_route_logic


# NetEase EnchantType IDs, matching upstream TFCreativeTabs/enchanted recipes.
DEFAULT_ENCHANTMENTS = {
    'ironwood_helmet': [(8, 1)], 'ironwood_chestplate': [(0, 1)],
    'ironwood_leggings': [(0, 1)], 'ironwood_boots': [(2, 1)],
    'ironwood_sword': [(17, 1)], 'ironwood_shovel': [(17, 1)],
    'ironwood_pickaxe': [(15, 1)], 'ironwood_axe': [(18, 1)],
    'ironwood_hoe': [(15, 1)],
    'steeleaf_helmet': [(4, 2)], 'steeleaf_chestplate': [(3, 2)],
    'steeleaf_leggings': [(1, 2)], 'steeleaf_boots': [(2, 2)],
    'steeleaf_sword': [(14, 2)], 'steeleaf_shovel': [(15, 2)],
    'steeleaf_pickaxe': [(18, 2)], 'steeleaf_axe': [(15, 2)],
    'steeleaf_hoe': [(18, 2)],
    'naga_chestplate': [(1, 3)], 'naga_leggings': [(0, 3)],
    'mazebreaker_pickaxe': [(15, 4), (17, 3), (18, 2)],
}
DEFAULT_MARKER = 'tf_equipment_defaults:1'
FIERY_TOOLS = ('tf_slice:fiery_sword', 'tf_slice:fiery_pickaxe')
MINOTAUR_AXES = ('tf_slice:gold_minotaur_axe', 'tf_slice:diamond_minotaur_axe')
FIERY_ARMOR = tuple('tf_slice:fiery_' + slot for slot in
                    ('helmet', 'chestplate', 'leggings', 'boots'))


def with_default_enchantments(item):
    name = portal_logic.item_name(item or {})
    defaults = DEFAULT_ENCHANTMENTS.get(name[len('tf_slice:'):]) if name.startswith('tf_slice:') else None
    if not defaults or DEFAULT_MARKER in str(item.get('extraId', '')).split('|'):
        return None
    result = copy.deepcopy(item)
    # Existing player enchantments (including incompatible protections) win.
    if not item.get('enchantData', item.get('enchants')):
        result['enchantData'] = list(defaults)
    extra = str(result.get('extraId', ''))
    result['extraId'] = (extra + '|' if extra else '') + DEFAULT_MARKER
    return result


def successful_hit(args, melee=False):
    try:
        damage = float(args.get('damage', 0))
    except (TypeError, ValueError):
        return False
    if args.get('cancel') or not 0 < damage < float('inf'):
        return False
    if melee and (args.get('cause') != 'entity_attack' or
                  args.get('projectileId') not in (None, '', '-1')):
        return False
    return True


def fiery_retaliation(armor, roll):
    coverage = sum(portal_logic.item_name(it or {}) in FIERY_ARMOR for it in armor)
    coverage = min(4, coverage)
    return coverage * 5 // 2 if 0 <= roll < coverage * 5 else 0


def smelted_stack(item, recipes):
    if not item or not recipes:
        return None
    recipe = recipes[0].get('minecraft:recipe_furnace', recipes[0])
    output = recipe.get('output')
    if isinstance(output, dict):
        name = output.get('item', output.get('name', ''))
        aux = int(output.get('data', 0))
        count = int(output.get('count', 1))
    else:
        name, aux, count = output, 0, 1
    if not name or ':' not in name:
        return None
    return {'newItemName': name, 'newAuxValue': aux,
            'count': int(item.get('count', 1)) * count}


class ItemEffects(object):
    def __init__(self, host, factory, api, level_id):
        self.h, self.cf, self.api, self.level = host, factory, api, level_id
        self.recipe_cache = {}
        self.glowing = {}

    def refresh_inventory(self, player):
        comp = self.cf.CreateItem(player)
        positions = self.api.GetMinecraftEnum().ItemPosType
        # CARRIED aliases an inventory slot. Never write that slot twice.
        for pos in (positions.INVENTORY, positions.ARMOR, positions.OFFHAND):
            updates = {}
            for slot, stack in enumerate(comp.GetPlayerAllItems(pos, True) or ()):
                changed = with_default_enchantments(stack)
                if changed is not None:
                    updates[(pos, slot)] = changed
            if updates:
                comp.SetPlayerAllItems(updates)

    def tick(self):
        if self.h._tick % 30 == 0:
            for player in self.h._get_online_players():
                try:
                    self.refresh_inventory(player)
                except Exception as error:
                    print('[TwilightBossSlice] equipment defaults failed', error)
        if self.h._tick % 6 == 0:
            for player, until in list(self.glowing.items()):
                if self.h._tick >= until or not self.h._is_online_player(player):
                    self.glowing.pop(player, None)
                    continue
                pos = self.h._get_foot_pos(player)
                if pos is not None:
                    self.h.BroadcastToAllClient('TorchberryGlow', {
                        'position': pos, 'dimensionId': self.h._get_dimension(player)})

    def on_damage(self, args):
        if not successful_hit(args, melee=True) or args.get('customTag'):
            return
        player = args.get('srcId')
        if not self.h._is_online_player(player):
            return
        name = portal_logic.item_name(self.h._carried_item(player) or {})
        if name in MINOTAUR_AXES:
            try:
                sprint = self.cf.CreateQueryVariable(player).EvalMolangExpression('query.is_sprinting')
            except Exception:
                sprint = {}
            if not sprint.get('error') and sprint.get('value') == 1:
                args['damage'] = float(args['damage']) + 7.0
        role = {'tf_slice:knightmetal_sword': 'sword', 'tf_slice:knightmetal_axe': 'axe',
                'tf_slice:knightmetal_pickaxe': 'pickaxe'}.get(name)
        if role:
            bonus = knight_route_logic.knightmetal_bonus(self.h._target_armor_points(args.get('entityId')))[role]
            args['damage'] = float(args['damage']) + bonus
        if name in FIERY_TOOLS:
            # Ignite before death/loot calculation so kills produce cooked meat.
            args['ignite'] = True

    def on_hurt(self, args):
        if not successful_hit(args, melee=True):
            return
        attacker, victim = args.get('srcId'), args.get('entityId')
        if attacker in (None, '', '-1') or victim in (None, '', '-1') or attacker == victim:
            return
        if self.h._is_online_player(attacker):
            name = portal_logic.item_name(self.h._carried_item(attacker) or {})
            if name in FIERY_TOOLS:
                self.h._set_entity_on_fire(victim, 15)
        if self.h._is_online_player(victim):
            try:
                pos = self.api.GetMinecraftEnum().ItemPosType.ARMOR
                armor = self.cf.CreateItem(victim).GetPlayerAllItems(pos, True) or ()
                seconds = fiery_retaliation(armor, random.randrange(25))
                if seconds:
                    self.h._set_entity_on_fire(attacker, seconds)
            except Exception as error:
                print('[TwilightBossSlice] fiery retaliation failed', error)

    def on_eat(self, args):
        player = args.get('playerId')
        if not self.h._is_online_player(player):
            return
        name = portal_logic.item_name(args.get('itemDict') or {})
        if name == 'tf_slice:hydra_chop':
            self.cf.CreateEffect(player).AddEffectToEntity('regeneration', 5, 0, True)
        elif name == 'tf_slice:meef_stroganoff':
            if self.h._grant_progress(player, 'tf_meef_stroganoff_eaten'):
                self.h._notify(player, u'\u706b\u7130\u6cbc\u6cfd\u5df2\u89e3\u9501\u3002', 'GOLD')
        elif name == 'tf_slice:torchberries' and random.random() < 0.75:
            # Bedrock lacks Java Glowing. Visible gold motes retain its timed
            # reveal cue; this does not claim a through-wall outline.
            self.glowing[player] = self.h._tick + 150

    def on_destroy_block(self, args):
        player = args.get('playerId')
        if portal_logic.item_name(self.h._carried_item(player) or {}) != 'tf_slice:fiery_pickaxe':
            return
        for entity in args.get('dropEntityIds') or ():
            try:
                stack = self.h._dropped_item(entity)
                if not stack:
                    continue
                key = (portal_logic.item_name(stack), int(stack.get('newAuxValue', stack.get('auxValue', 0))))
                if key not in self.recipe_cache:
                    recipes = self.cf.CreateRecipe(self.level).GetRecipesByInput(key[0], 'furnace', key[1], 1)
                    self.recipe_cache[key] = recipes or []
                cooked = smelted_stack(stack, self.recipe_cache[key])
                pos = self.h._get_foot_pos(entity)
                if cooked is None or pos is None:
                    continue
                new_id = self.h.CreateEngineItemEntity(cooked, args['dimensionId'], pos)
                if new_id in (None, False, '', '-1'):
                    continue
                # Keep the original if spawning failed; roll back the new
                # entity if removing the original fails. Never grant inventory.
                try:
                    removed = self.h.DestroyEntity(entity)
                except Exception:
                    removed = False
                if removed is False:
                    self.h.DestroyEntity(new_id)
            except Exception as error:
                print('[TwilightBossSlice] fiery smelting failed', error)
