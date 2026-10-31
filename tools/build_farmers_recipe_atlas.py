"""Read the local Farmers Delight pack and script recipes into a review page."""
import argparse
import collections
import importlib
import json
import sys
from pathlib import Path

try:
    from build_recipe_atlas import load_json, load_language, data_uri, centered_shaped_slots, VANILLA_NAMES
except ImportError:
    from tools.build_recipe_atlas import load_json, load_language, data_uri, centered_shaped_slots, VANILLA_NAMES

ROOT = Path(__file__).resolve().parents[1]
FD = ROOT.parent / "netease-farmers-delight"
BP, RP = FD / "behavior_pack", FD / "resource_pack"
DEFAULT_OUTPUT = ROOT / "artifacts/recipe-atlas/farmers-delight.html"
KINDS = {"shaped": "有序合成", "shapeless": "无序合成", "furnace": "熔炉 / 烟熏 / 营火",
         "smithing": "锻造台", "cutting": "砧板", "pot": "厨锅", "stove": "炉灶",
         "skillet": "放置煎锅", "handheld": "手持煎锅"}
NAMES = dict(VANILLA_NAMES)
NAMES.update(dict(zip(
    ('wheat', 'egg', 'milk_bucket', 'bucket', 'bowl', 'bamboo', 'flint', 'brick', 'brick_block',
     'water_bucket', 'netherite_ingot', 'netherite_upgrade_smithing_template', 'diamond', 'gold_ingot',
     'carrot', 'potato', 'beetroot', 'pumpkin', 'bone', 'beef', 'chicken', 'porkchop', 'mutton',
     'rabbit', 'cod', 'salmon', 'cooked_beef', 'cooked_chicken', 'cooked_porkchop', 'cooked_mutton',
     'cooked_rabbit', 'cooked_cod', 'cooked_salmon', 'baked_potato', 'ink_sac', 'black_dye',
     'allium', 'azure_bluet', 'blue_orchid', 'cornflower', 'dandelion', 'lily_of_the_valley',
     'orange_tulip', 'oxeye_daisy', 'pink_tulip', 'poppy', 'red_tulip', 'torchflower', 'white_tulip',
     'wither_rose', 'magenta_dye', 'light_gray_dye', 'light_blue_dye', 'blue_dye', 'yellow_dye',
     'white_dye', 'orange_dye', 'pink_dye', 'red_dye'),
    ('小麦', '鸡蛋', '牛奶桶', '桶', '碗', '竹子', '燧石', '红砖', '红砖块',
     '水桶', '下界合金锭', '下界合金升级模板', '钻石', '金锭',
     '胡萝卜', '马铃薯', '甜菜根', '南瓜', '骨头', '生牛肉', '生鸡肉', '生猪排', '生羊肉',
     '生兔肉', '生鳕鱼', '生鲑鱼', '熟牛肉', '熟鸡肉', '熟猪排', '熟羊肉',
     '熟兔肉', '熟鳕鱼', '熟鲑鱼', '烤马铃薯', '墨囊', '黑色染料',
     '绒球葱', '蓝花美耳草', '兰花', '矢车菊', '蒲公英', '铃兰',
     '橙色郁金香', '滨菊', '粉红色郁金香', '虞美人', '红色郁金香', '火把花', '白色郁金香',
     '凋零玫瑰', '品红色染料', '淡灰色染料', '淡蓝色染料', '蓝色染料', '黄色染料',
     '白色染料', '橙色染料', '粉红色染料', '红色染料'))))
NAMES = {key if ':' in key else 'minecraft:' + key: value for key, value in NAMES.items()}
NAMES.update({'fd_port:organic_compost_stage0': '有机肥料', 'fd_port:rich_soil': '沃土',
              'fd_port:rich_soil_farmland': '沃土耕地', 'fd_port:skillet': '旧版煎锅',
              'minecraft:campfire': '营火', 'minecraft:dirt': '泥土', 'minecraft:wooden_shovel': '木锹'})
NAMES.update({'minecraft:bread': '面包', 'minecraft:brown_mushroom': '棕色蘑菇',
              'minecraft:red_mushroom': '红色蘑菇', 'minecraft:crimson_fungus': '绯红菌',
              'minecraft:warped_fungus': '诡异菌', 'minecraft:dried_kelp': '干海带',
              'minecraft:glow_berries': '发光浆果', 'minecraft:sweet_berries': '甜浆果',
              'minecraft:golden_carrot': '金胡萝卜', 'minecraft:honey_bottle': '蜂蜜瓶'})
for wood, label in zip(('oak', 'spruce', 'birch', 'jungle', 'acacia', 'dark_oak', 'mangrove', 'cherry', 'bamboo', 'crimson', 'warped'),
                       ('橡木', '云杉木', '白桦木', '丛林木', '金合欢木', '深色橡木', '红树木', '樱花木', '竹', '绯红木', '诡异木')):
    for suffix, noun in (('planks', '木板'), ('slab', '台阶'), ('trapdoor', '活板门')):
        NAMES['minecraft:' + wood + '_' + suffix] = label + noun
    if wood not in ('bamboo', 'crimson', 'warped'):
        for suffix, noun in (('log', '原木'), ('wood', '木块')):
            NAMES['minecraft:' + wood + '_' + suffix] = label + noun
            NAMES['minecraft:stripped_' + wood + '_' + suffix] = '去皮' + label + noun
    if wood in ('crimson', 'warped'):
        for suffix, noun in (('stem', '菌柄'), ('hyphae', '菌核')):
            NAMES['minecraft:' + wood + '_' + suffix] = label + noun
            NAMES['minecraft:stripped_' + wood + '_' + suffix] = '去皮' + label + noun


def build_catalog():
    sys.path.insert(0, str(BP))
    from FarmersDelightPort import basic_foods, meal_data, recipe_data, cutting_model, stove_model, handheld_skillet
    # A long-lived local server must reread edited script recipes on refresh.
    for module in (basic_foods, meal_data, recipe_data, cutting_model, stove_model, handheld_skillet):
        importlib.reload(module)
    language = load_language(RP / 'texts/zh_CN.lang')
    atlas = {}
    for filename in ('item_texture.json', 'terrain_texture.json'):
        atlas.update(load_json(RP / 'textures' / filename)['texture_data'])
    icons = {}

    def item(identifier, count=1):
        label = language.get('item.' + identifier + '.name') or language.get('tile.' + identifier + '.name') or NAMES.get(identifier, identifier)
        if identifier not in icons:
            texture = atlas.get(identifier, {}).get('textures', '')
            if isinstance(texture, str) and texture:
                path = RP / (texture + '.png')
            else:
                name = identifier.split(':')[-1]
                path = RP / ('textures/blocks/' + name + '_front.png')
                if not path.is_file():
                    path = RP / ('textures/blocks/' + name + '_side.png')
            icons[identifier] = data_uri(path) if path.is_file() else ''
        return {'id': identifier, 'name': label, 'count': count, 'icon': icons[identifier]}

    def ingredient(value):
        if isinstance(value, (tuple, list)):
            options = []
            for choice in value:
                entry = ingredient(choice)
                options.extend(entry.get('options', [entry]))
            options = list({entry['id']: entry for entry in options}.values())
            return {'id': ' | '.join(value), 'name': ' / '.join(o['name'] for o in options),
                    'count': 1, 'icon': '', 'options': options}
        if value.startswith('#'):
            options = [item(identifier) for identifier in recipe_data.TAGS[value[1:]]]
            return {'id': value, 'name': ' / '.join(o['name'] for o in options), 'count': 1, 'icon': '', 'options': options}
        return item(value)

    rows = []

    def add(identifier, kind, inputs, outputs, source, note='', slots=None, raw=None):
        rows.append({'id': identifier, 'kind': kind, 'inputs': inputs, 'outputs': outputs,
                     'source': source, 'note': note, 'slots': slots or [], 'raw': raw})

    for path in sorted((BP / 'recipes').glob('*.json')):
        document = load_json(path)
        root = next(key for key in document if key.startswith('minecraft:recipe_'))
        recipe = document[root]
        identifier = recipe['description']['identifier']
        extra_outputs = []
        if root == 'minecraft:recipe_furnace':
            kind, inputs = 'furnace', [item(recipe['input'])]
            output, count, slots = recipe['output'], 1, []
            note = '设备：' + ' / '.join({'furnace': '熔炉', 'smoker': '烟熏炉', 'campfire': '营火', 'soul_campfire': '灵魂营火'}.get(tag, tag) for tag in recipe.get('tags', [])) + '；加工时长采用客户端默认值。'
        else:
            result = recipe['result']
            if isinstance(result, list):
                if not result:
                    raise ValueError('Recipe has no outputs: ' + identifier)
                extra_outputs = [item(entry['item'], entry.get('count', 1)) for entry in result[1:]]
                result = result[0]
            output, count = (result, 1) if isinstance(result, str) else (result['item'], result.get('count', 1))
            note, slots = '', []
            if root == 'minecraft:recipe_shaped':
                kind = 'shaped'
                slot_ids = centered_shaped_slots(recipe['pattern'], recipe['key'])
                slots = [item(value) if value else None for value in slot_ids]
                totals = collections.Counter(value for value in slot_ids if value)
                inputs = [item(value, amount) for value, amount in totals.items()]
            elif root == 'minecraft:recipe_shapeless':
                kind = 'shapeless'
                totals = collections.Counter(entry['item'] for entry in recipe['ingredients'])
                inputs = [item(value, amount) for value, amount in totals.items()]
            elif root == 'minecraft:recipe_smithing_transform':
                kind = 'smithing'
                inputs = [item(recipe[key]) for key in ('template', 'base', 'addition')]
                note = '按升级模板 → 基础物品 → 添加材料的顺序放入锻造台。'
            else:
                raise ValueError('Unsupported recipe type: ' + root)
        if output == 'fd_port:milk_bottle':
            note += ' 饮用及饮用后的玻璃瓶返还和解除效果尚未实现。牛奶桶的合成剩余物需实机检查。'
        add(identifier, kind, inputs, [item(output, count)] + extra_outputs, 'behavior_pack/recipes/' + path.name, note, slots, document)
    for identifier, outputs in sorted(cutting_model.CUTS.items()):
        note = ('先在砧板放一件原木或木块，再用主手斧头剥皮；六种原版斧头均可，料理刀不适用。生存模式耗损 1 点工具耐久；已去皮木材不能重复产出树皮。'
                if identifier in cutting_model.BARK_CUTS else
                '先在砧板放一件原料，再用主手料理刀切割；五种料理刀均可，刀具作为工具不列入消耗材料。')
        add('cutting:' + identifier, 'cutting', [item(identifier)], [item(name, count) for name, count in outputs],
            'behavior_pack/FarmersDelightPort/cutting_model.py + basic_foods.py',
            note)
    for recipe in recipe_data.RECIPES:
        container = recipe.get('container', 'minecraft:bowl')
        container_note = ('用%s盛出，每份使用 1 个%s。' % (item(container)['name'], item(container)['name'])
                          if container else '不需要额外容器。')
        add('pot:' + recipe['id'], 'pot', [ingredient(value) for value in recipe['ingredients']], [item(recipe['result'], recipe.get('count', 1))],
            'behavior_pack/FarmersDelightPort/recipe_data.py + meal_data.py',
            '底下需要热源；每个列出的材料分别占一个输入槽。%g 秒，经验 %g；' % (recipe['seconds'], recipe['experience'])
            + container_note + '标签或斜线分隔的替代材料任选其一。')
    for identifier, result in sorted(stove_model.COOKABLE.items()):
        for kind, seconds, note in (
            ('stove', stove_model.COOK_SECONDS, '每次放一件，最多六件；炉面被厨锅或煎锅覆盖时不能放入烤料。'),
            ('skillet', 6, '放在热源上，放入一组同类食材，逐件加工。'),
            ('handheld', handheld_skillet.cooking_seconds(0), '另一只手放食材，靠近热源长按使用；抛炒不加速，提前松开返还生食。')):
            add(kind + ':' + identifier, kind, [item(identifier)], [item(result)],
                'behavior_pack/FarmersDelightPort/' + {'stove': 'stove_model.py', 'skillet': 'skillet_model.py', 'handheld': 'handheld_skillet.py'}[kind],
                '每件约 %g 秒。' % seconds + note)
    for row in rows:
        row['search'] = ' '.join([row['id'], KINDS[row['kind']], row['note']] +
                                [item['id'] + ' ' + item['name'] for item in row['inputs'] + row['outputs']]).lower()
    return rows


def build_html(catalog):
    template = Path(__file__).with_name('farmers_recipe_atlas.html').read_text(encoding='utf-8')
    data = json.dumps({'recipes': catalog, 'kinds': KINDS}, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return template.replace('__RECIPE_DATA__', data)


def rebuild(output=DEFAULT_OUTPUT):
    catalog = build_catalog()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.tmp')
    temporary.write_text(build_html(catalog), encoding='utf-8')
    temporary.replace(output)
    return len(catalog)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print('Farmers Delight: %d recipes' % rebuild(args.output))
