#!/usr/bin/env python3
"""Build complete English and Simplified Chinese public name tables.

Names are discovered from the behavior pack, but every Chinese display name
must be explicit.  Regeneration therefore cannot silently fall back to an
English title or expose an untranslated identifier in the client.
"""

from __future__ import print_function

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

NATIVE_WOOD_NAME_OVERRIDES = (
    ("tile.dark_oak_stairs.name", "Darkwood Stairs", "黑木楼梯"),
    ("tile.wooden_slab.big_oak.name", "Darkwood Slab", "黑木台阶"),
    ("tile.dark_oak_button.name", "Darkwood Button", "黑木按钮"),
    ("tile.darkOakFence.name", "Darkwood Fence", "黑木栅栏"),
    ("tile.dark_oak_fence_gate.name", "Darkwood Fence Gate", "黑木栅栏门"),
    ("tile.dark_oak_pressure_plate.name", "Darkwood Pressure Plate", "黑木压力板"),
    ("item.dark_oak_door.name", "Darkwood Door", "黑木门"),
    ("tile.dark_oak_trapdoor.name", "Darkwood Trapdoor", "黑木活板门"),
    ("item.darkoak_sign.name", "Darkwood Sign", "黑木告示牌"),
    ("item.dark_oak_hanging_sign.name", "Darkwood Hanging Sign", "黑木悬挂告示牌"),
    ("tile.mangrove_stairs.name", "Mangrove Stairs", "红树林木楼梯"),
    ("tile.mangrove_slab.name", "Mangrove Slab", "红树林木台阶"),
    ("tile.mangrove_button.name", "Mangrove Button", "红树林木按钮"),
    ("tile.mangrove_fence.name", "Mangrove Fence", "红树林木栅栏"),
    ("tile.mangrove_fence_gate.name", "Mangrove Fence Gate", "红树林木栅栏门"),
    ("tile.mangrove_pressure_plate.name", "Mangrove Pressure Plate", "红树林木压力板"),
    ("item.mangrove_door.name", "Mangrove Door", "红树林木门"),
    ("tile.mangrove_trapdoor.name", "Mangrove Trapdoor", "红树林木活板门"),
    ("item.mangrove_sign.name", "Mangrove Sign", "红树林木告示牌"),
    ("item.mangrove_hanging_sign.name", "Mangrove Hanging Sign", "红树林木悬挂告示牌"),
    ("tile.cherry_stairs.name", "Canopy Stairs", "苍穹木楼梯"),
    ("tile.cherry_slab.name", "Canopy Slab", "苍穹木台阶"),
    ("tile.cherry_button.name", "Canopy Button", "苍穹木按钮"),
    ("tile.cherry_fence.name", "Canopy Fence", "苍穹木栅栏"),
    ("tile.cherry_fence_gate.name", "Canopy Fence Gate", "苍穹木栅栏门"),
    ("tile.cherry_pressure_plate.name", "Canopy Pressure Plate", "苍穹木压力板"),
    ("item.cherry_door.name", "Canopy Door", "苍穹木门"),
    ("tile.cherry_trapdoor.name", "Canopy Trapdoor", "苍穹木活板门"),
)


ENTITY_ZH = {
    "bighorn_sheep": "大角羊",
    "block_chain_goblin": "链锤地精",
    "block_chain_projectile": "链锤弹体",
    "boar": "暮色野猪",
    "carminite_golem": "卡米奈特傀儡",
    "death_tome": "死亡之书",
    "deer": "暮色鹿",
    "dwarf_rabbit": "侏儒兔",
    "fire_beetle": "喷火甲虫",
    "fire_breath": "九头蛇火焰",
    "forest_wyrm": "娜迦",
    "forest_wyrm_segment": "娜迦躯体",
    "hedge_spider": "树篱蜘蛛",
    "helmet_crab": "头盔蟹",
    "hostile_wolf": "敌对狼",
    "hydra": "九头蛇",
    "hydra_head": "九头蛇头颅",
    "hydra_mortar": "九头蛇火焰弹",
    "hydra_neck": "九头蛇颈部",
    "hydra_part_proxy": "九头蛇部件代理",
    "king_spider": "国王蜘蛛",
    "knight_axe_projectile": "幻影战斧",
    "knight_phantom": "幻影骑士",
    "knight_pickaxe_projectile": "幻影战镐",
    "kobold": "狗头人",
    "lich": "暮色巫妖",
    "lich_bolt": "巫妖魔弹",
    "lich_bomb": "巫妖炸弹",
    "lich_minion": "巫妖仆从",
    "lich_shadow_clone": "巫妖幻影",
    "lower_goblin_knight": "下层哥布林骑士",
    "loyal_zombie": "忠诚僵尸",
    "maze_slime": "迷宫史莱姆",
    "mini_ghast": "恶魂幼体",
    "minoshroom": "米诺菇",
    "minotaur": "牛头人",
    "mist_wolf": "迷雾狼",
    "mosquito_swarm": "蚊群",
    "nature_bolt": "自然魔弹",
    "penguin": "企鹅",
    "pinch_beetle": "夹虫",
    "quest_ram": "谜题羊",
    "raven": "乌鸦",
    "redcap": "红帽地精",
    "redcap_sapper": "红帽地精工兵",
    "rising_zombie": "复生僵尸",
    "skeleton_druid": "骷髅德鲁伊",
    "slime_beetle": "黏液甲虫",
    "slime_blob": "黏液团",
    "squirrel": "暮色松鼠",
    "swarm_spider": "群聚蜘蛛",
    "tiny_bird": "小鸟",
    "tome_bolt": "死亡之书魔弹",
    "tower_broodling": "幼年蜘蛛",
    "tower_ghast": "恶魂守卫",
    "towerwood_borer": "塔木蛀虫",
    "twilight_wand_bolt": "暮色权杖魔弹",
    "upper_goblin_knight": "上层哥布林骑士",
    "ur_ghast": "暮色恶魂",
    "ur_ghast_fireball": "暮色恶魂火球",
    "wraith": "幽灵",
}


ITEM_ZH = {
    "knight_phantom_trophy": "\u5e7b\u5f71\u9a91\u58eb\u6218\u5229\u54c1",
    "armor_shard": "盔甲碎片",
    "armor_shard_cluster": "盔甲碎片簇",
    "block_and_chain": "方块链锤",
    "carminite": "卡米奈特",
    "charm_of_keeping_1": "保管护符 I",
    "charm_of_keeping_2": "保管护符 II",
    "charm_of_keeping_3": "保管护符 III",
    "charm_of_life_1": "生命护符 I",
    "cooked_meef": "熟牛头人肉",
    "cooked_venison": "熟鹿肉",
    "crumble_horn": "瓦解号角",
    "dark_boat": "黑木船",
    "dark_chest_boat": "黑木运输船",
    "diamond_minotaur_axe": "钻石牛头人战斧",
    "fiery_blood": "炽热之血",
    "fiery_boots": "炽铁靴子",
    "fiery_chestplate": "炽铁胸甲",
    "fiery_helmet": "炽铁头盔",
    "fiery_ingot": "炽铁锭",
    "fiery_leggings": "炽铁护腿",
    "fiery_pickaxe": "炽铁镐",
    "fiery_sword": "炽铁剑",
    "fiery_tears": "火焰之泪",
    "filled_magic_map": "魔法地图",
    "filled_maze_map": "迷宫地图",
    "fire_react_book_1": "火焰反应 I 附魔书",
    "fire_react_book_2": "火焰反应 II 附魔书",
    "fire_react_book_3": "火焰反应 III 附魔书",
    "fortification_scepter": "堡垒权杖",
    "gold_minotaur_axe": "黄金牛头人战斧",
    "hydra_banner": "九头蛇旗帜",
    "hydra_chop": "九头蛇肉排",
    "ironwood_axe": "铁木斧",
    "ironwood_boots": "铁木靴子",
    "ironwood_chestplate": "铁木胸甲",
    "ironwood_helmet": "铁木头盔",
    "ironwood_hoe": "铁木锄",
    "ironwood_ingot": "铁木锭",
    "liveroot": "活根",
    "raw_ironwood": "粗铁木",
    "ironwood_leggings": "铁木护腿",
    "ironwood_pickaxe": "铁木镐",
    "ironwood_shovel": "铁木锹",
    "ironwood_sword": "铁木剑",
    "knightmetal_axe": "骑士金属斧",
    "knightmetal_boots": "骑士金属靴子",
    "knightmetal_chestplate": "骑士金属胸甲",
    "knightmetal_helmet": "骑士金属头盔",
    "knightmetal_ingot": "骑士金属锭",
    "knightmetal_leggings": "骑士金属护腿",
    "knightmetal_pickaxe": "骑士金属镐",
    "knightmetal_ring": "骑士金属环",
    "knightmetal_shield": "骑士金属盾",
    "knightmetal_sword": "骑士金属剑",
    "lifedrain_scepter": "吸血权杖",
    "magic_map": "空白魔法地图",
    "magic_map_focus": "魔法地图核心",
    "mangrove_boat": "红树林木船",
    "mangrove_chest_boat": "红树林木运输船",
    "maze_map": "空白迷宫地图",
    "maze_map_focus": "迷宫地图核心",
    "maze_wafer": "迷宫薄饼",
    "mazebreaker_pickaxe": "迷宫破坏者镐",
    "meef_stroganoff": "牛头人烩肉",
    "minoshroom_banner": "米诺菇旗帜",
    "naga_chestplate": "娜迦鳞甲",
    "naga_leggings": "娜迦鳞片护腿",
    "naga_scale": "娜迦鳞片",
    "naga_trophy": "娜迦战利品",
    "phantom_chestplate": "幻影骑士胸甲",
    "phantom_helmet": "幻影骑士头盔",
    "raven_feather": "乌鸦羽毛",
    "raw_meef": "生牛头人肉",
    "raw_venison": "生鹿肉",
    "red_thread": "红线",
    "steeleaf_axe": "钢叶斧",
    "steeleaf_boots": "钢叶靴子",
    "steeleaf_chestplate": "钢叶胸甲",
    "steeleaf_helmet": "钢叶头盔",
    "steeleaf_hoe": "钢叶锄",
    "steeleaf_ingot": "钢叶锭",
    "cicada": "蝉",
    "transformation_powder": "转换粉",
    "steeleaf_leggings": "钢叶护腿",
    "steeleaf_pickaxe": "钢叶镐",
    "steeleaf_shovel": "钢叶锹",
    "steeleaf_sword": "钢叶剑",
    "torchberries": "火炬浆果",
    "tower_key": "塔钥匙",
    "twilight_scepter": "暮色权杖",
    "ur_ghast_banner": "暮色恶魂旗帜",
    "ur_ghast_trophy": "暮色恶魂战利品",
    "zombie_scepter": "僵尸权杖",
}


BLOCK_ZH = {
    "canopy_banister": "苍穹木栏杆",
    "canopy_bookshelf": "苍穹木书架",
    "canopy_button": "苍穹木按钮",
    "canopy_chest": "苍穹木箱子",
    "canopy_door": "苍穹木门",
    "canopy_fence": "苍穹木栅栏",
    "canopy_fence_gate": "苍穹木栅栏门",
    "canopy_planks": "苍穹木板",
    "canopy_pressure_plate": "苍穹木压力板",
    "canopy_leaves": "苍穹树叶",
    "canopy_log": "苍穹树原木",
    "canopy_sapling": "苍穹树苗",
    "canopy_log_x": "横向苍穹树原木",
    "canopy_log_z": "纵向苍穹树原木",
    "canopy_slab": "苍穹木台阶",
    "canopy_stairs": "苍穹木楼梯",
    "canopy_trapdoor": "苍穹木活板门",
    "canopy_wood": "苍穹木",
    "carminite_antibuilder": "卡米奈特反建造器",
    "carminite_block": "卡米奈特块",
    "carminite_builder": "卡米奈特建造器",
    "carminite_reactor": "卡米奈特反应堆",
    "cicada_jar": "蝉罐",
    "cracked_etched_nagastone": "裂纹蚀刻娜迦石",
    "cracked_mazestone": "裂纹迷宫石砖",
    "cracked_nagastone_pillar": "裂纹娜迦石柱",
    "cracked_nagastone_stairs_left": "裂纹左侧娜迦石阶",
    "cracked_nagastone_stairs_right": "裂纹右侧娜迦石阶",
    "cracked_towerwood": "裂纹塔木",
    "cracked_underbrick": "裂纹地下砖",
    "cut_mazestone": "切制迷宫石",
    "decorative_mazestone": "装饰迷宫石",
    "encased_fire_jet": "封装火焰喷口",
    "encased_smoker": "封装烟雾发生器",
    "encased_towerwood": "封装塔木",
    "enchanted_canopy_leaves": "魔法苍穹树叶",
    "enchanted_twilight_oak_leaves": "魔法暮色橡树叶",
    "etched_nagastone": "蚀刻娜迦石",
    "experiment_115": "实验品 115",
    "fake_diamond": "伪钻石块",
    "fake_gold": "伪金块",
    "fallen_leaves": "落叶堆",
    "fiddlehead": "蕨芽",
    "stripped_canopy_log": "去皮苍穹原木",
    "stripped_canopy_wood": "去皮苍穹木",
    "fiery_block": "炽铁块",
    "fire_jet": "火焰喷口",
    "firefly": "萤火虫",
    "firefly_jar": "萤火虫罐",
    "ghast_trap": "恶魂陷阱",
    "hedge": "树篱",
    "huge_lily_pad": "巨型睡莲叶",
    "huge_lily_pad_ne": "巨型睡莲叶（东北片）",
    "huge_lily_pad_nw": "巨型睡莲叶（西北片）",
    "huge_lily_pad_se": "巨型睡莲叶（东南片）",
    "huge_lily_pad_sw": "巨型睡莲叶（西南片）",
    "huge_water_lily": "巨型睡莲花",
    "hydra_boss_spawner": "九头蛇生成标记",
    "hydra_trophy": "九头蛇战利品",
    "hydra_wall_trophy": "墙上九头蛇战利品",
    "infested_towerwood": "虫蚀塔木",
    "knight_phantom_boss_spawner": "幻影骑士生成标记",
    "knight_phantom_trophy": "幻影骑士战利品",
    "knight_phantom_wall_trophy": "墙上幻影骑士战利品",
    "knightmetal_block": "骑士金属块",
    "steeleaf_block": "钢叶块",
    "landmark_protected_grass": "地标保护草方块",
    "lich_boss_spawner": "巫妖生成标记",
    "lich_trophy": "巫妖战利品",
    "lich_wall_trophy": "墙上巫妖战利品",
    "liveroot_block": "活根块",
    "locked_vanishing_block": "上锁消失方块",
    "mayapple": "五月苹果草",
    "maze_slime_block": "迷宫史莱姆块",
    "mazestone": "迷宫石",
    "mazestone_border": "迷宫石边框",
    "mazestone_brick": "迷宫石砖",
    "mazestone_mosaic": "迷宫石马赛克",
    "minoshroom_boss_spawner": "米诺菇生成标记",
    "minoshroom_trophy": "米诺菇战利品",
    "minoshroom_wall_trophy": "墙上米诺菇战利品",
    "mossy_etched_nagastone": "苔藓蚀刻娜迦石",
    "mossy_mazestone": "苔藓迷宫石砖",
    "mossy_nagastone_pillar": "苔藓娜迦石柱",
    "mossy_nagastone_stairs_left": "苔藓左侧娜迦石阶",
    "mossy_nagastone_stairs_right": "苔藓右侧娜迦石阶",
    "mossy_towerwood": "苔藓塔木",
    "mossy_underbrick": "苔藓地下砖",
    "mushgloom": "幽光蘑菇",
    "naga_boss_spawner": "娜迦生成标记",
    "naga_trophy": "娜迦战利品",
    "naga_wall_trophy": "墙上娜迦战利品",
    "nagastone": "娜迦石",
    "nagastone_head": "娜迦石首",
    "nagastone_pillar": "娜迦石柱",
    "nagastone_stairs_left": "左侧娜迦石阶",
    "nagastone_stairs_right": "右侧娜迦石阶",
    "quest_ram_trophy": "谜题羊战利品",
    "quest_ram_wall_trophy": "墙上谜题羊战利品",
    "rainbow_oak_leaves": "彩虹橡树叶",
    "rainbow_oak_sapling": "彩虹橡树苗",
    "reactor_debris": "反应堆碎屑",
    "reappearing_block": "重现方块",
    "restored_block": "恢复方块",
    "root_block": "根块",
    "root_strand": "根须",
    "smoker": "烟雾发生器",
    "spiral_bricks": "螺旋石砖",
    "spooky_twilight_oak_leaves": "阴森暮色橡树叶",
    "stronghold_shield": "要塞盾墙",
    "temporary_builder_block": "临时建造块",
    "torchberry_plant": "火炬浆果丛",
    "torchberry_plant_empty": "空火炬浆果丛",
    "tower_key_door": "塔钥匙门",
    "towerwood": "塔木",
    "trophy_pedestal": "奖杯基座",
    "twilight_oak_leaves": "暮色橡树叶",
    "twilight_oak_log": "暮色橡树原木",
    "twilight_oak_sapling": "暮色橡树苗",
    "twilight_oak_log_x": "横向暮色橡树原木",
    "twilight_oak_log_z": "纵向暮色橡树原木",
    "twilight_portal": "暮色森林传送门",
    "unbreakable_vanishing_block": "不可破坏消失方块",
    "underbrick": "地下砖",
    "underbrick_floor": "地下砖地板",
    "ur_ghast_trophy": "暮色恶魂战利品",
    "ur_ghast_wall_trophy": "墙上暮色恶魂战利品",
    "ur_ghast_boss_spawner": "暮色恶魂生成标记",
    "vanishing_block": "消失方块",
}


def _wood_family(prefix, label):
    return {
        prefix + "_banister": label + "栏杆",
        prefix + "_leaves": label + "树叶",
        prefix + "_log": label + "原木",
        prefix + "_log_x": "横向" + label + "原木",
        prefix + "_log_z": "纵向" + label + "原木",
        prefix + "_planks": label + "木板",
        prefix + "_root": label + "根",
        prefix + "_sapling": label + "树苗",
        prefix + "_wood": label + "木",
    }


BLOCK_ZH.update(_wood_family("mangrove", "红树林木"))
BLOCK_ZH.update(
    {
        "stripped_mangrove_log": "去皮红树林木原木",
        "stripped_mangrove_wood": "去皮红树林木",
        "hollow_mangrove_log_horizontal": "横向中空红树林木原木",
        "hollow_mangrove_log_vertical": "竖向中空红树林木原木",
        "hollow_mangrove_log_climbable": "可攀爬中空红树林木原木",
        "dark_banister": "黑木栏杆",
        "dark_leaves": "黑木树叶",
        "dark_log": "黑木原木",
        "dark_log_vertical": "生成用竖直黑木原木",
        "dark_planks": "黑木木板",
        "dark_wood": "黑木",
        "darkwood_sapling": "黑木树苗",
        "hardened_dark_leaves": "硬化黑木树叶",
        "hardened_dark_leaves_center": "黑森林中心硬化树叶",
        "stripped_dark_log": "去皮黑木原木",
        "stripped_dark_wood": "去皮黑木",
        "hollow_dark_log_horizontal": "横向中空黑木原木",
        "hollow_dark_log_vertical": "竖向中空黑木原木",
        "hollow_dark_log_climbable": "可攀爬中空黑木原木",
    }
)
for index in range(16):
    BLOCK_ZH["rainbow_oak_leaves_%02d" % index] = "彩虹橡树叶"


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_language(path):
    if not path.is_file():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def _title(identifier):
    return identifier.replace("_", " ").title()


def _write_language(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join("%s=%s" % item for item in sorted(values.items())) + "\n",
        encoding="utf-8",
    )


def write_native_wood_name_overrides(root=ROOT):
    """Update only native wood display names for a scoped wood rebuild."""
    root = Path(root)
    rp = root / "TwilightBossSliceR"
    english_path = rp / "texts" / "en_US.lang"
    chinese_path = rp / "texts" / "zh_CN.lang"
    english = _load_language(english_path)
    chinese = _load_language(chinese_path)
    for key, english_name, chinese_name in NATIVE_WOOD_NAME_OVERRIDES:
        english[key] = english_name
        chinese[key] = chinese_name
    _write_language(english_path, english)
    _write_language(chinese_path, chinese)
    return len(NATIVE_WOOD_NAME_OVERRIDES)


def build_localization(root=ROOT):
    root = Path(root)
    bp = root / "TwilightBossSliceB"
    rp = root / "TwilightBossSliceR"
    old_english = _load_language(rp / "texts" / "en_US.lang")
    english = {"tf_slice:itemGroup.name.twilight_forest": "Twilight Forest"}
    chinese = {"tf_slice:itemGroup.name.twilight_forest": "暮色森林"}
    missing = []

    for path in sorted((bp / "entities").glob("*.json")):
        entity = _load_json(path).get("minecraft:entity", {})
        description = entity.get("description", {})
        full_identifier = description.get("identifier", "")
        if not full_identifier.startswith("tf_slice:"):
            continue
        identifier = full_identifier.split(":", 1)[1]
        translated = ENTITY_ZH.get(identifier)
        if translated is None:
            missing.append("entity:" + identifier)
            continue
        key = "entity.%s.name" % full_identifier
        english[key] = old_english.get(key, _title(identifier))
        chinese[key] = translated
        if description.get("is_spawnable"):
            egg_key = "item.spawn_egg.entity.%s.name" % full_identifier
            english[egg_key] = "Spawn " + english[key]
            chinese[egg_key] = "生成 " + translated

    for path in sorted((bp / "items").glob("*.json")):
        item = _load_json(path).get("minecraft:item", {})
        description = item.get("description", {})
        full_identifier = description.get("identifier", "")
        if not full_identifier.startswith("tf_slice:"):
            continue
        identifier = full_identifier.split(":", 1)[1]
        translated = ITEM_ZH.get(identifier)
        if translated is None:
            missing.append("item:" + identifier)
            continue
        key = item.get("components", {}).get(
            "minecraft:display_name", {}
        ).get("value", "item.%s.name" % full_identifier)
        english[key] = old_english.get(key, _title(identifier))
        chinese[key] = translated

    block_identifiers = set()
    for folder in ("blocks", "netease_blocks"):
        for path in sorted((bp / folder).glob("*.json")):
            block = _load_json(path).get("minecraft:block", {})
            full_identifier = block.get("description", {}).get(
                "identifier", ""
            )
            if not full_identifier.startswith("tf_slice:"):
                continue
            identifier = full_identifier.split(":", 1)[1]
            if identifier in block_identifiers:
                continue
            block_identifiers.add(identifier)
            translated = BLOCK_ZH.get(identifier)
            if translated is None:
                missing.append("block:" + identifier)
                continue
            key = "tile.%s.name" % full_identifier
            english[key] = old_english.get(key, _title(identifier))
            chinese[key] = translated

    for key, english_name, chinese_name in NATIVE_WOOD_NAME_OVERRIDES:
        english[key] = english_name
        chinese[key] = chinese_name

    if missing:
        raise ValueError(
            "missing explicit Simplified Chinese names: " + ", ".join(missing)
        )
    _write_language(rp / "texts" / "en_US.lang", english)
    _write_language(rp / "texts" / "zh_CN.lang", chinese)
    return {"en_US": len(english), "zh_CN": len(chinese)}


if __name__ == "__main__":
    counts = build_localization()
    print(
        "generated complete localization: en_US=%d zh_CN=%d"
        % (counts["en_US"], counts["zh_CN"])
    )
