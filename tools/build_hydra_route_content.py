# -*- coding: utf-8 -*-
"""Generate Hydra-route blocks, items, recipes, atlases and copied visuals.

The catalog in ``docs/hydra_route_content.json`` is the public inventory.  All
copied pixels come from the locked 4.3.2508 JAR tree; Minecraft built-in
textures are referenced only where the Java model does the same.
"""

from __future__ import print_function

import json
import shutil
from pathlib import Path

from PIL import Image

try:
    from build_public_block_shapes import build as build_public_block_shapes
except ImportError:  # pragma: no cover - package import in tests
    from tools.build_public_block_shapes import build as build_public_block_shapes
try:
    from build_creative_catalog import (
        normalize_creative_catalog,
        player_visible_wood_item,
    )
    from build_localization import build_localization
except ImportError:  # pragma: no cover - package import in tests
    from tools.build_creative_catalog import (
        normalize_creative_catalog,
        player_visible_wood_item,
    )
    from tools.build_localization import build_localization
try:
    from build_swamp_features import (
        huge_lily_pad_block,
        huge_water_lily_block,
        swamp_plant_geometry,
    )
except ImportError:  # pragma: no cover - package import in tests
    from tools.build_swamp_features import (
        huge_lily_pad_block,
        huge_water_lily_block,
        swamp_plant_geometry,
    )


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
UPSTREAM = ROOT.parent / "twilightforest-1.20.1-4.3.2508-extracted" / "00_original_tree"
UPSTREAM_TEXTURES = UPSTREAM / "assets" / "twilightforest" / "textures"
UPSTREAM_MODELS = UPSTREAM / "assets" / "twilightforest" / "models" / "block"
CATALOG_PATH = ROOT / "docs" / "hydra_route_content.json"


ITEM_NAMES = {
    "raw_meef": ("Raw Meef", "生米诺陶肉"),
    "cooked_meef": ("Cooked Meef", "熟米诺陶肉"),
    "meef_stroganoff": ("Meef Stroganoff", "米诺陶炖肉"),
    "maze_wafer": ("Maze Wafer", "迷宫薄饼"),
    "hydra_chop": ("Hydra Chop", "九头蛇肉排"),
    "fiery_blood": ("Fiery Blood", "炽热之血"),
    "fiery_ingot": ("Fiery Ingot", "炽铁锭"),
    "ironwood_ingot": ("Ironwood Ingot", "铁木锭"),
    "steeleaf_ingot": ("Steeleaf Ingot", "钢叶锭"),
    "red_thread": ("Red Thread", "红线"),
    "maze_map_focus": ("Maze Map Focus", "迷宫地图核心"),
    "maze_map": ("Blank Maze Map", "空白迷宫地图"),
    "filled_maze_map": ("Maze Map", "迷宫地图"),
    "charm_of_keeping_1": ("Charm of Keeping I", "保管符咒 I"),
    "charm_of_keeping_2": ("Charm of Keeping II", "保管符咒 II"),
    "charm_of_keeping_3": ("Charm of Keeping III", "保管符咒 III"),
    "gold_minotaur_axe": ("Golden Minotaur Axe", "黄金米诺陶战斧"),
    "diamond_minotaur_axe": ("Diamond Minotaur Axe", "钻石米诺陶战斧"),
    "mazebreaker_pickaxe": ("Mazebreaker Pickaxe", "迷宫破坏者镐"),
    "minoshroom_banner": ("Minoshroom Banner", "米诺菇旗帜"),
    "hydra_banner": ("Hydra Banner", "九头蛇旗帜"),
    "mangrove_boat": ("Mangrove Boat", "红树林船"),
    "mangrove_chest_boat": ("Mangrove Chest Boat", "红树林运输船"),
    "fire_react_book_1": ("Fire React I", "火焰反击 I"),
    "fire_react_book_2": ("Fire React II", "火焰反击 II"),
    "fire_react_book_3": ("Fire React III", "火焰反击 III"),
}
NON_CREATIVE_DYNAMIC_ITEMS = frozenset(("filled_maze_map",))


def creative_item_identifiers(identifiers):
    """Keep dynamic, identity-bearing map stacks out of creative output."""
    return [
        identifier
        for identifier in identifiers
        if identifier not in NON_CREATIVE_DYNAMIC_ITEMS
    ]

BLOCK_NAMES = {
    "mazestone": ("Mazestone", "迷宫石"),
    "mazestone_brick": ("Mazestone Brick", "迷宫石砖"),
    "cut_mazestone": ("Cut Mazestone", "切制迷宫石"),
    "decorative_mazestone": ("Decorative Mazestone", "装饰迷宫石"),
    "cracked_mazestone": ("Cracked Mazestone Brick", "裂纹迷宫石砖"),
    "mossy_mazestone": ("Mossy Mazestone Brick", "苔藓迷宫石砖"),
    "mazestone_mosaic": ("Mazestone Mosaic", "迷宫石马赛克"),
    "mazestone_border": ("Mazestone Border", "迷宫石边框"),
    "smoker": ("Smoker", "烟柱"),
    "fire_jet": ("Fire Jet", "火焰喷泉"),
    "encased_towerwood": ("Encased Towerwood Planks", "封装塔木木板"),
    "encased_smoker": ("Encased Smoker", "封装烟柱"),
    "encased_fire_jet": ("Encased Fire Jet", "封装火焰喷泉"),
    "maze_slime_block": ("Maze Slime Block", "迷宫史莱姆块"),
    "fiery_block": ("Fiery Block", "炽铁块"),
    "huge_lily_pad": ("Huge Lily Pad", "巨大睡莲叶"),
    "huge_water_lily": ("Huge Water Lily", "巨大水莲"),
    "minoshroom_trophy": ("Minoshroom Trophy", "米诺菇战利品"),
    "minoshroom_wall_trophy": ("Wall Minoshroom Trophy", "壁挂米诺菇战利品"),
    "hydra_trophy": ("Hydra Trophy", "九头蛇战利品"),
    "hydra_wall_trophy": ("Wall Hydra Trophy", "壁挂九头蛇战利品"),
}

for _name in (
    "ironwood_sword", "ironwood_axe", "ironwood_pickaxe", "ironwood_shovel",
    "ironwood_hoe", "ironwood_helmet", "ironwood_chestplate",
    "ironwood_leggings", "ironwood_boots", "steeleaf_sword",
    "steeleaf_axe", "steeleaf_pickaxe", "steeleaf_shovel", "steeleaf_hoe",
    "steeleaf_helmet", "steeleaf_chestplate", "steeleaf_leggings",
    "steeleaf_boots", "fiery_sword", "fiery_pickaxe", "fiery_helmet",
    "fiery_chestplate", "fiery_leggings", "fiery_boots",
):
    material, kind = _name.split("_", 1)
    material_en = {"ironwood": "Ironwood", "steeleaf": "Steeleaf", "fiery": "Fiery"}[material]
    material_zh = {"ironwood": "铁木", "steeleaf": "钢叶", "fiery": "炽铁"}[material]
    kind_en = {
        "sword": "Sword", "axe": "Axe", "pickaxe": "Pickaxe",
        "shovel": "Shovel", "hoe": "Hoe", "helmet": "Helmet",
        "chestplate": "Chestplate", "leggings": "Leggings", "boots": "Boots",
    }[kind]
    kind_zh = {
        "sword": "剑", "axe": "斧", "pickaxe": "镐", "shovel": "锹",
        "hoe": "锄", "helmet": "头盔", "chestplate": "胸甲",
        "leggings": "护腿", "boots": "靴子",
    }[kind]
    ITEM_NAMES[_name] = (material_en + " " + kind_en, material_zh + kind_zh)

for _name in (
    "mangrove_log", "mangrove_wood", "stripped_mangrove_log",
    "stripped_mangrove_wood", "mangrove_leaves", "mangrove_sapling",
    "mangrove_root", "mangrove_planks", "mangrove_banister",
    "hollow_mangrove_log_horizontal", "hollow_mangrove_log_vertical",
    "hollow_mangrove_log_climbable",
):
    BLOCK_NAMES[_name] = (
        _name.replace("_", " ").title(),
        "红树林" + _name.replace("mangrove_", "").replace("_", " "),
    )

# Keep generated language files UTF-8-clean even when this script is invoked
# through a legacy Windows code page. Unicode escapes are intentional.
ITEM_NAMES.update({
    "raw_meef": ("Raw Meef", u"\u751f\u7c73\u8bfa\u9676\u8089"),
    "cooked_meef": ("Cooked Meef", u"\u719f\u7c73\u8bfa\u9676\u8089"),
    "meef_stroganoff": ("Meef Stroganoff", u"\u7c73\u8bfa\u9676\u7096\u8089"),
    "maze_wafer": ("Maze Wafer", u"\u8ff7\u5bab\u8584\u997c"),
    "hydra_chop": ("Hydra Chop", u"\u4e5d\u5934\u86c7\u8089\u6392"),
    "fiery_blood": ("Fiery Blood", u"\u70bd\u70ed\u4e4b\u8840"),
    "fiery_ingot": ("Fiery Ingot", u"\u70bd\u94c1\u952d"),
    "ironwood_ingot": ("Ironwood Ingot", u"\u94c1\u6728\u952d"),
    "steeleaf_ingot": ("Steeleaf Ingot", u"\u94a2\u53f6\u952d"),
    "red_thread": ("Red Thread", u"\u7ea2\u7ebf"),
    "maze_map_focus": ("Maze Map Focus", u"\u8ff7\u5bab\u5730\u56fe\u6838\u5fc3"),
    "maze_map": ("Blank Maze Map", u"\u7a7a\u767d\u8ff7\u5bab\u5730\u56fe"),
    "filled_maze_map": ("Maze Map", u"\u8ff7\u5bab\u5730\u56fe"),
    "charm_of_keeping_1": ("Charm of Keeping I", u"\u4fdd\u7ba1\u7b26\u5492 I"),
    "charm_of_keeping_2": ("Charm of Keeping II", u"\u4fdd\u7ba1\u7b26\u5492 II"),
    "charm_of_keeping_3": ("Charm of Keeping III", u"\u4fdd\u7ba1\u7b26\u5492 III"),
    "gold_minotaur_axe": ("Golden Minotaur Axe", u"\u9ec4\u91d1\u7c73\u8bfa\u9676\u6218\u65a7"),
    "diamond_minotaur_axe": ("Diamond Minotaur Axe", u"\u94bb\u77f3\u7c73\u8bfa\u9676\u6218\u65a7"),
    "mazebreaker_pickaxe": ("Mazebreaker Pickaxe", u"\u8ff7\u5bab\u7834\u574f\u8005\u9550"),
    "minoshroom_banner": ("Minoshroom Banner", u"\u7c73\u8bfa\u83c7\u65d7\u5e1c"),
    "hydra_banner": ("Hydra Banner", u"\u4e5d\u5934\u86c7\u65d7\u5e1c"),
    "mangrove_boat": ("Mangrove Boat", u"\u7ea2\u6811\u6797\u8239"),
    "mangrove_chest_boat": ("Mangrove Chest Boat", u"\u7ea2\u6811\u6797\u8fd0\u8f93\u8239"),
    "fire_react_book_1": ("Fire React I", u"\u706b\u7130\u53cd\u51fb I"),
    "fire_react_book_2": ("Fire React II", u"\u706b\u7130\u53cd\u51fb II"),
    "fire_react_book_3": ("Fire React III", u"\u706b\u7130\u53cd\u51fb III"),
})
_equipment_material_zh = {
    "ironwood": u"\u94c1\u6728", "steeleaf": u"\u94a2\u53f6", "fiery": u"\u70bd\u94c1",
}
_equipment_kind_zh = {
    "sword": u"\u5251", "axe": u"\u65a7", "pickaxe": u"\u9550",
    "shovel": u"\u94f2", "hoe": u"\u9504", "helmet": u"\u5934\u76d4",
    "chestplate": u"\u80f8\u7532", "leggings": u"\u62a4\u817f", "boots": u"\u9774\u5b50",
}
for _equipment_name in list(ITEM_NAMES):
    _parts = _equipment_name.split("_", 1)
    if (
        len(_parts) == 2
        and _parts[0] in _equipment_material_zh
        and _parts[1] in _equipment_kind_zh
    ):
        ITEM_NAMES[_equipment_name] = (
            ITEM_NAMES[_equipment_name][0],
            _equipment_material_zh[_parts[0]] + _equipment_kind_zh[_parts[1]],
        )

BLOCK_NAMES.update({
    "mazestone": ("Mazestone", u"\u8ff7\u5bab\u77f3"),
    "mazestone_brick": ("Mazestone Brick", u"\u8ff7\u5bab\u77f3\u7816"),
    "cut_mazestone": ("Cut Mazestone", u"\u5207\u5236\u8ff7\u5bab\u77f3"),
    "decorative_mazestone": ("Decorative Mazestone", u"\u88c5\u9970\u8ff7\u5bab\u77f3"),
    "cracked_mazestone": ("Cracked Mazestone Brick", u"\u88c2\u7eb9\u8ff7\u5bab\u77f3\u7816"),
    "mossy_mazestone": ("Mossy Mazestone Brick", u"\u82d4\u85d3\u8ff7\u5bab\u77f3\u7816"),
    "mazestone_mosaic": ("Mazestone Mosaic", u"\u8ff7\u5bab\u77f3\u9a6c\u8d5b\u514b"),
    "mazestone_border": ("Mazestone Border", u"\u8ff7\u5bab\u77f3\u8fb9\u6846"),
    "smoker": ("Smoker", u"\u70df\u67f1"),
    "fire_jet": ("Fire Jet", u"\u706b\u7130\u55b7\u6cc9"),
    "encased_towerwood": (
        "Encased Towerwood Planks",
        u"\u5c01\u88c5\u5854\u6728\u6728\u677f",
    ),
    "encased_smoker": ("Encased Smoker", u"\u5c01\u88c5\u70df\u67f1"),
    "encased_fire_jet": ("Encased Fire Jet", u"\u5c01\u88c5\u706b\u7130\u55b7\u6cc9"),
    "maze_slime_block": ("Maze Slime Block", u"\u8ff7\u5bab\u53f2\u83b1\u59c6\u5757"),
    "fiery_block": ("Fiery Block", u"\u70bd\u94c1\u5757"),
    "huge_lily_pad": ("Huge Lily Pad", u"\u5de8\u5927\u7761\u83b2\u53f6"),
    "huge_water_lily": ("Huge Water Lily", u"\u5de8\u5927\u6c34\u83b2"),
    "minoshroom_trophy": ("Minoshroom Trophy", u"\u7c73\u8bfa\u83c7\u6218\u5229\u54c1"),
    "minoshroom_wall_trophy": ("Wall Minoshroom Trophy", u"\u58c1\u6302\u7c73\u8bfa\u83c7\u6218\u5229\u54c1"),
    "hydra_trophy": ("Hydra Trophy", u"\u4e5d\u5934\u86c7\u6218\u5229\u54c1"),
    "hydra_wall_trophy": ("Wall Hydra Trophy", u"\u58c1\u6302\u4e5d\u5934\u86c7\u6218\u5229\u54c1"),
})
_mangrove_suffix_zh = {
    "mangrove_log": u"\u7ea2\u6811\u539f\u6728", "mangrove_wood": u"\u7ea2\u6811\u6728",
    "stripped_mangrove_log": u"\u53bb\u76ae\u7ea2\u6811\u539f\u6728", "stripped_mangrove_wood": u"\u53bb\u76ae\u7ea2\u6811\u6728",
    "mangrove_leaves": u"\u7ea2\u6811\u6811\u53f6", "mangrove_sapling": u"\u7ea2\u6811\u6811\u82d7",
    "mangrove_root": u"\u7ea2\u6811\u6811\u6839", "mangrove_planks": u"\u7ea2\u6811\u6728\u677f",
    "mangrove_banister": u"\u7ea2\u6811\u6728\u680f\u6746",
    "hollow_mangrove_log_horizontal": u"\u6a2a\u5411\u4e2d\u7a7a\u7ea2\u6811\u539f\u6728", "hollow_mangrove_log_vertical": u"\u7ad6\u5411\u4e2d\u7a7a\u7ea2\u6811\u539f\u6728",
    "hollow_mangrove_log_climbable": u"\u53ef\u6500\u722c\u4e2d\u7a7a\u7ea2\u6811\u539f\u6728",
}
for _block_name, _translated in _mangrove_suffix_zh.items():
    BLOCK_NAMES[_block_name] = (BLOCK_NAMES[_block_name][0], _translated)

FOODS = {
    "raw_meef": (2, 0.3),
    "cooked_meef": (6, 0.6),
    "meef_stroganoff": (8, 0.6),
    "maze_wafer": (4, 0.6),
    "hydra_chop": (18, 2.0),
}

TOOL_STATS = {
    "gold_minotaur_axe": (32, 6),
    "diamond_minotaur_axe": (1561, 9),
    "mazebreaker_pickaxe": (512, 4),
    "ironwood_sword": (512, 5), "ironwood_axe": (512, 8),
    "ironwood_pickaxe": (512, 4), "ironwood_shovel": (512, 3),
    "ironwood_hoe": (512, 2), "steeleaf_sword": (131, 6),
    "steeleaf_axe": (131, 9), "steeleaf_pickaxe": (131, 5),
    "steeleaf_shovel": (131, 4), "steeleaf_hoe": (131, 3),
    "fiery_sword": (1024, 7), "fiery_pickaxe": (1024, 5),
}

ARMOR_STATS = {
    "ironwood_helmet": (220, "slot.armor.head", 2, "armor_head", 15),
    "ironwood_chestplate": (320, "slot.armor.chest", 7, "armor_torso", 15),
    "ironwood_leggings": (300, "slot.armor.legs", 5, "armor_legs", 15),
    "ironwood_boots": (260, "slot.armor.feet", 2, "armor_feet", 15),
    "steeleaf_helmet": (110, "slot.armor.head", 3, "armor_head", 9),
    "steeleaf_chestplate": (160, "slot.armor.chest", 8, "armor_torso", 9),
    "steeleaf_leggings": (150, "slot.armor.legs", 6, "armor_legs", 9),
    "steeleaf_boots": (130, "slot.armor.feet", 3, "armor_feet", 9),
    "fiery_helmet": (275, "slot.armor.head", 4, "armor_head", 10),
    "fiery_chestplate": (400, "slot.armor.chest", 9, "armor_torso", 10),
    "fiery_leggings": (375, "slot.armor.legs", 7, "armor_legs", 10),
    "fiery_boots": (325, "slot.armor.feet", 4, "armor_feet", 10),
}

BLOCK_TEXTURE_SOURCES = {
    "mangrove_planks": "block/wood/planks_mangrove_0.png",
    "mangrove_door": "block/wood/door/mangrove_lower.png",
    "mangrove_trapdoor": "block/wood/trapdoor/mangrove_trapdoor.png",
    "mangrove_leaves": None,
    "maze_slime_block": None,
    "smoker": "block/firejet_side.png",
    "fire_jet": "block/firejet_top.png",
    "encased_towerwood": "block/encased_towerwood.png",
    "encased_smoker": "block/towerdev_smoker_off.png",
    "encased_fire_jet": "block/towerdev_firejet_off.png",
}

ITEM_TEXTURE_ALIASES = {
    "minoshroom_banner": "tf_banner_pattern.png",
    "hydra_banner": "tf_banner_pattern.png",
    "fire_react_book_1": None,
    "fire_react_book_2": None,
    "fire_react_book_3": None,
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_texture(source_relative, target):
    source = UPSTREAM_TEXTURES / source_relative
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(target))


def _material_instance(texture, render_method="opaque"):
    return {
        "texture": texture,
        "render_method": render_method,
        "ambient_occlusion": True,
        "face_dimming": True,
    }


def _fire_swamp_materials(identifier, active=False):
    if identifier in ("smoker", "fire_jet"):
        aliases = {
            "side": "tf_slice:firejet_side",
            "top": "tf_slice:firejet_top",
            "bottom": "tf_slice:firejet_bottom",
        }
    else:
        phase = "on" if active else "off"
        aliases = {
            "side": "tf_slice:%s_side_%s" % (identifier, phase),
            "top": "tf_slice:%s_top_%s" % (identifier, phase),
            "bottom": "tf_slice:encased_towerwood",
        }
    materials = {
        face: _material_instance(texture)
        for face, texture in aliases.items()
    }
    materials["*"] = _material_instance(aliases["side"])
    return materials


def _composite_model_face(model_name, face, target):
    document = load_json(UPSTREAM_MODELS / (model_name + ".json"))
    textures = document["textures"]
    keys = (face, face + "2", face + "3")
    layers = []
    for key in keys:
        reference = textures.get(key)
        if not reference or not reference.startswith("twilightforest:block/"):
            continue
        source = UPSTREAM_TEXTURES / (
            reference[len("twilightforest:") :] + ".png"
        )
        layers.append(Image.open(str(source)).convert("RGBA"))
    if not layers:
        raise ValueError("model face has no Twilight texture: %s %s" % (model_name, face))
    image = layers[0]
    for layer in layers[1:]:
        image = Image.alpha_composite(image, layer)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(target), format="PNG", optimize=False)


def register_fire_swamp_textures(terrain_data):
    copies = {
        "firejet_side": "block/firejet_side.png",
        "firejet_top": "block/firejet_top.png",
    }
    for alias, source in copies.items():
        target = RP / "textures" / "blocks" / (alias + ".png")
        copy_texture(source, target)
        terrain_data["tf_slice:" + alias] = {
            "textures": "textures/blocks/" + alias
        }
    terrain_data["tf_slice:firejet_bottom"] = {
        "textures": "textures/blocks/grass_top"
    }

    model_names = {
        ("encased_smoker", "off"): "encased_smoker",
        ("encased_smoker", "on"): "encased_smoker_on",
        ("encased_fire_jet", "off"): "encased_fire_jet",
        ("encased_fire_jet", "on"): "encased_fire_jet_on",
    }
    for (identifier, phase), model_name in model_names.items():
        for face in ("side", "top"):
            alias = "%s_%s_%s" % (identifier, face, phase)
            target = RP / "textures" / "blocks" / (alias + ".png")
            _composite_model_face(model_name, face, target)
            terrain_data["tf_slice:" + alias] = {
                "textures": "textures/blocks/" + alias
            }


def item_document(identifier):
    components = {
        "minecraft:display_name": {"value": "item.tf_slice:%s.name" % identifier},
        "minecraft:icon": {
            "textures": {"default": "tf_slice:%s" % identifier}
        },
    }
    if identifier in FOODS:
        nutrition, saturation = FOODS[identifier]
        components.update({
            "minecraft:tags": {"tags": ["minecraft:is_food"]},
            "minecraft:use_animation": "eat",
            "minecraft:use_modifiers": {"use_duration": 1.6, "movement_modifier": 0.35},
            "minecraft:food": {"nutrition": nutrition, "saturation_modifier": saturation},
        })
        if identifier == "meef_stroganoff":
            components["minecraft:food"]["can_always_eat"] = True
            components["minecraft:max_stack_size"] = 1
            components["minecraft:food"]["using_converts_to"] = "minecraft:bowl"
    elif identifier in TOOL_STATS:
        role = identifier.rsplit("_", 1)[-1]
        enchant_value = (
            22 if "minotaur" in identifier else
            15 if identifier.startswith("ironwood") else
            10 if identifier.startswith("fiery") or identifier == "mazebreaker_pickaxe" else 9
        )
        components["minecraft:enchantable"] = {"slot": role, "value": enchant_value}
        durability, damage = TOOL_STATS[identifier]
        components.update({
            "minecraft:max_stack_size": 1,
            "minecraft:hand_equipped": True,
            "minecraft:durability": {"max_durability": durability},
            "minecraft:damage": damage,
        })
    elif identifier in ARMOR_STATS:
        durability, slot, protection, enchant_slot, enchant_value = ARMOR_STATS[identifier]
        components.update({
            "minecraft:max_stack_size": 1,
            "minecraft:durability": {"max_durability": durability},
            "minecraft:wearable": {"slot": slot, "protection": protection},
            "minecraft:enchantable": {"slot": enchant_slot, "value": enchant_value},
        })
    elif identifier.startswith("fire_react_book_"):
        components.update({"minecraft:max_stack_size": 1, "minecraft:foil": True})
    elif identifier in ("filled_maze_map",):
        components.update({"minecraft:max_stack_size": 64, "minecraft:allow_off_hand": True})
    if identifier in (
        "fiery_helmet", "fiery_chestplate", "fiery_leggings", "fiery_boots",
        "fiery_sword", "fiery_pickaxe", "fiery_ingot", "hydra_chop", "meef_stroganoff",
    ):
        components["minecraft:fire_resistant"] = {"value": True}
    return {
        "format_version": "1.21.60",
        "minecraft:item": {
            "description": {
                "identifier": "tf_slice:%s" % identifier,
                "menu_category": {"category": "nature"},
            },
            "components": components,
        },
    }


def fire_swamp_machine_block_document(identifier):
    states = {}
    if identifier == "fire_jet":
        states["tf_slice:jet_state"] = ["idle", "popping", "flame"]
    elif identifier == "encased_fire_jet":
        states["tf_slice:jet_state"] = [
            "idle",
            "popping",
            "flame",
            "timeout",
        ]
    elif identifier == "encased_smoker":
        states["tf_slice:active"] = ["off", "on"]

    components = {
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 1.5},
        "minecraft:destructible_by_explosion": {
            "explosion_resistance": 6.0
        },
        "minecraft:geometry": "geometry.tf_slice.courtyard_cube",
        "minecraft:material_instances": _fire_swamp_materials(identifier),
        "netease:aabb": {
            "collision": {
                "min": [0.0, 0.0, 0.0],
                "max": [1.0, 1.0, 1.0],
            },
            "clip": {
                "min": [0.0, 0.0, 0.0],
                "max": [1.0, 1.0, 1.0],
            },
        },
        "netease:render_layer": {"value": "opaque"},
        "netease:solid": {"value": True},
        "netease:pathable": {"value": False},
    }
    description = {
        "identifier": "tf_slice:%s" % identifier,
        "register_to_creative_menu": True,
    }
    if states:
        description["states"] = states

    block = {"description": description, "components": components}
    permutations = []
    if identifier == "encased_smoker":
        permutations.append(
            {
                "condition": (
                    "query.block_state('tf_slice:active') == 'on'"
                ),
                "components": {
                    "minecraft:material_instances": (
                        _fire_swamp_materials(identifier, active=True)
                    ),
                },
            }
        )
    elif identifier == "encased_fire_jet":
        permutations.append(
            {
                "condition": (
                    "query.block_state('tf_slice:jet_state') == 'popping' || "
                    "query.block_state('tf_slice:jet_state') == 'flame'"
                ),
                "components": {
                    "minecraft:material_instances": (
                        _fire_swamp_materials(identifier, active=True)
                    ),
                },
            }
        )
    if identifier in ("fire_jet", "encased_fire_jet"):
        permutations.append(
            {
                "condition": (
                    "query.block_state('tf_slice:jet_state') == 'flame'"
                ),
                "components": {"minecraft:light_emission": 15},
            }
        )
    if permutations:
        block["permutations"] = permutations
    return {"format_version": "1.20.60", "minecraft:block": block}


def encased_towerwood_block_document():
    return {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": {
                "identifier": "tf_slice:encased_towerwood",
                "register_to_creative_menu": True,
            },
            "components": {
                "minecraft:destructible_by_mining": {
                    "seconds_to_destroy": 40.0
                },
                "minecraft:destructible_by_explosion": {
                    "explosion_resistance": 6.0
                },
                "netease:render_layer": {"value": "opaque"},
                "netease:solid": {"value": True},
                "netease:pathable": {"value": False},
            },
        },
    }


def block_document(identifier, translucent=False, no_collision=False):
    if identifier in (
        "smoker",
        "fire_jet",
        "encased_smoker",
        "encased_fire_jet",
    ):
        return fire_swamp_machine_block_document(identifier)
    if identifier == "encased_towerwood":
        return encased_towerwood_block_document()
    components = {
        "minecraft:destroy_time": {"value": 2.0 if "mangrove" in identifier else 1.5},
        "minecraft:explosion_resistance": {"value": 3.0 if "mangrove" in identifier else 100.0},
        "netease:render_layer": {"value": "optionalAlpha" if translucent else "opaque"},
        "netease:solid": {"value": not no_collision},
        "netease:pathable": {"value": identifier == "huge_lily_pad"},
    }
    if identifier == "mangrove_sapling":
        components["netease:random_tick"] = {
            "enable": True,
            "tick_to_script": True,
        }
    if no_collision:
        collision_max = (
            [1.0, 0.125, 1.0]
            if identifier == "huge_lily_pad"
            else [0.0, 0.0, 0.0]
        )
        components["netease:aabb"] = {
            "collision": {
                "min": [0.0, 0.0, 0.0],
                "max": collision_max,
            },
            "clip": {"min": [0.0, 0.0, 0.0], "max": [1.0, 0.125, 1.0]},
        }
    description = {
        "identifier": "tf_slice:%s" % identifier,
        "register_to_creative_menu": True,
    }
    if identifier == "mangrove_sapling":
        description["states"] = {"tf_slice:growth_stage": [0, 1]}
    return {
        "format_version": "1.10.0",
        "minecraft:block": {
            "description": description,
            "components": components,
        },
    }


def shaped(identifier, pattern, keys, count=1, result_item=None):
    return {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "tags": ["crafting_table"], "pattern": pattern,
            "key": dict((key, {"item": value}) for key, value in keys.items()),
            "unlock": {"context": "AlwaysUnlocked"},
            "result": {
                "item": player_visible_wood_item(
                    result_item or ("tf_slice:%s" % identifier)
                ),
                "count": count,
            },
        },
    }


def shapeless(identifier, ingredients, count=1):
    return {
        "format_version": "1.20.10",
        "minecraft:recipe_shapeless": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "tags": ["crafting_table"],
            "ingredients": [{"item": item} for item in ingredients],
            "unlock": {"context": "AlwaysUnlocked"},
            "result": {
                "item": player_visible_wood_item(
                    "tf_slice:%s" % identifier
                ),
                "count": count,
            },
        },
    }


def generate_recipes():
    recipes = {
        "cooked_meef": {
            "format_version": "1.12",
            "minecraft:recipe_furnace": {
                "description": {"identifier": "tf_slice:cooked_meef"},
                "tags": ["furnace", "smoker", "campfire"],
                "input": "tf_slice:raw_meef", "output": "tf_slice:cooked_meef",
            },
        },
        "fiery_ingot": shapeless("fiery_ingot", ["tf_slice:fiery_blood", "minecraft:iron_ingot"]),
        "fiery_block": shaped("fiery_block", ["###", "###", "###"], {"#": "tf_slice:fiery_ingot"}),
        "encased_towerwood_stonecutting": {
            "format_version": "1.20.10",
            "minecraft:recipe_shapeless": {
                "description": {
                    "identifier": "tf_slice:encased_towerwood_stonecutting"
                },
                "tags": ["stonecutter"],
                "ingredients": [{"item": "tf_slice:towerwood"}],
                "unlock": {"context": "AlwaysUnlocked"},
                "result": {
                    "item": "tf_slice:encased_towerwood",
                    "count": 1,
                },
            },
        },
        "encased_smoker": shaped(
            "encased_smoker",
            ["ERE", "RSR", "ERE"],
            {
                "E": "tf_slice:encased_towerwood",
                "R": "minecraft:redstone",
                "S": "tf_slice:smoker",
            },
        ),
        "encased_fire_jet": shaped(
            "encased_fire_jet",
            ["ERE", "RJR", "LLL"],
            {
                "E": "tf_slice:encased_towerwood",
                "R": "minecraft:redstone",
                "J": "tf_slice:fire_jet",
                "L": "minecraft:lava_bucket",
            },
        ),
        "charm_of_keeping_2": shapeless("charm_of_keeping_2", ["tf_slice:charm_of_keeping_1"] * 4),
        "charm_of_keeping_3": shapeless("charm_of_keeping_3", ["tf_slice:charm_of_keeping_2"] * 4),
        "mangrove_planks": shapeless("mangrove_planks", ["tf_slice:mangrove_log"], 4),
        "mangrove_stairs": shaped("mangrove_stairs", ["#  ", "## ", "###"], {"#": "tf_slice:mangrove_planks"}, 4),
        "mangrove_slab": shaped("mangrove_slab", ["###"], {"#": "tf_slice:mangrove_planks"}, 6),
        "mangrove_fence": shaped("mangrove_fence", ["#S#", "#S#"], {"#": "tf_slice:mangrove_planks", "S": "minecraft:stick"}, 3),
        "mangrove_fence_gate": shaped("mangrove_fence_gate", ["S#S", "S#S"], {"#": "tf_slice:mangrove_planks", "S": "minecraft:stick"}),
        "mangrove_banister": shaped(
            "mangrove_banister",
            ["---", "| |"],
            {"-": "minecraft:mangrove_slab", "|": "minecraft:stick"},
            3,
        ),
        "mangrove_door": shaped("mangrove_door", ["##", "##", "##"], {"#": "tf_slice:mangrove_planks"}, 3),
        "mangrove_trapdoor": shaped("mangrove_trapdoor", ["###", "###"], {"#": "tf_slice:mangrove_planks"}, 2),
        "mangrove_boat": shaped("mangrove_boat", ["# #", "###"], {"#": "tf_slice:mangrove_planks"}),
        "mangrove_chest_boat": shapeless("mangrove_chest_boat", ["tf_slice:mangrove_boat", "minecraft:chest"]),
        "maze_map": shaped(
            "maze_map",
            ["PPP", "PFP", "PPP"],
            {"P": "minecraft:paper", "F": "tf_slice:maze_map_focus"},
        ),
        "minoshroom_banner": shapeless("minoshroom_banner", ["minecraft:paper", "tf_slice:minoshroom_trophy"]),
        "hydra_banner": shapeless("hydra_banner", ["minecraft:paper", "tf_slice:hydra_trophy"]),
    }
    armor_patterns = {
        "helmet": ["###", "# #"], "chestplate": ["# #", "###", "###"],
        "leggings": ["###", "# #", "# #"], "boots": ["# #", "# #"],
    }
    for kind, pattern in armor_patterns.items():
        recipes["fiery_" + kind] = shaped("fiery_" + kind, pattern, {"#": "tf_slice:fiery_ingot"})
    recipes["fiery_sword"] = shaped("fiery_sword", ["#", "#", "S"], {"#": "tf_slice:fiery_ingot", "S": "minecraft:blaze_rod"})
    recipes["fiery_pickaxe"] = shaped("fiery_pickaxe", ["###", " S ", " S "], {"#": "tf_slice:fiery_ingot", "S": "minecraft:blaze_rod"})
    for identifier, document in recipes.items():
        write_json(BP / "recipes" / (identifier + ".recipe.json"), document)


def generate_fire_swamp_machine_content():
    """Regenerate the source-locked Fire Swamp device acquisition closure."""
    identifiers = (
        "smoker",
        "fire_jet",
        "encased_towerwood",
        "encased_smoker",
        "encased_fire_jet",
    )
    for identifier in identifiers:
        write_json(
            BP / "netease_blocks" / (identifier + ".json"),
            block_document(
                identifier,
                translucent=identifier in ("smoker", "fire_jet"),
            ),
        )

    terrain = load_json(RP / "textures" / "terrain_texture.json")
    client_blocks = load_json(RP / "blocks.json")
    for identifier in identifiers:
        texture_key = "tf_slice:" + identifier
        copy_texture(
            BLOCK_TEXTURE_SOURCES[identifier],
            RP / "textures" / "blocks" / (identifier + ".png"),
        )
        terrain["texture_data"][texture_key] = {
            "textures": "textures/blocks/%s" % identifier
        }
        client_blocks[texture_key] = {
            "textures": texture_key,
            "sound": "wood",
        }
    register_fire_swamp_textures(terrain["texture_data"])
    write_json(RP / "textures" / "terrain_texture.json", terrain)
    write_json(RP / "blocks.json", client_blocks)

    creative = load_json(BP / "item_catalog" / "crafting_item_catalog.json")
    creative_items = creative["minecraft:crafting_items_catalog"][
        "categories"
    ][0]["groups"][0]["items"]
    for identifier in identifiers:
        full_id = "tf_slice:" + identifier
        if full_id not in creative_items:
            creative_items.append(full_id)
    write_json(BP / "item_catalog" / "crafting_item_catalog.json", creative)

    for language, index in (("en_US.lang", 0), ("zh_CN.lang", 1)):
        path = RP / "texts" / language
        lines = path.read_text(encoding="utf-8").splitlines()
        key_lines = {
            line.split("=", 1)[0]: line_index
            for line_index, line in enumerate(lines)
            if "=" in line
        }
        for identifier in identifiers:
            key = "tile.tf_slice:%s.name" % identifier
            value = key + "=" + BLOCK_NAMES[identifier][index]
            if key in key_lines:
                lines[key_lines[key]] = value
            else:
                key_lines[key] = len(lines)
                lines.append(value)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    generate_recipes()


def main():
    catalog = load_json(CATALOG_PATH)
    all_blocks = catalog["mazestoneBlocks"] + catalog["fireSwampBlocks"] + catalog["mangroveBlocks"]
    for identifier in catalog["items"]:
        write_json(BP / "items" / (identifier + ".item.json"), item_document(identifier))

    terrain = load_json(RP / "textures" / "terrain_texture.json")
    terrain_data = terrain["texture_data"]
    blocks = load_json(RP / "blocks.json")
    specialized_blocks = {
        "huge_lily_pad": huge_lily_pad_block,
        "huge_water_lily": huge_water_lily_block,
    }
    for identifier in all_blocks:
        translucent = identifier in (
            "mangrove_leaves", "mangrove_sapling", "huge_lily_pad",
            "huge_water_lily", "smoker", "fire_jet",
        )
        no_collision = identifier in (
            "mangrove_sapling", "huge_lily_pad", "huge_water_lily",
            "mangrove_sign", "mangrove_wall_sign", "mangrove_hanging_sign",
            "mangrove_wall_hanging_sign",
        )
        document_factory = specialized_blocks.get(identifier)
        write_json(
            BP / "netease_blocks" / (identifier + ".json"),
            document_factory()
            if document_factory is not None
            else block_document(identifier, translucent, no_collision),
        )

        texture_key = "tf_slice:" + identifier
        source_relative = BLOCK_TEXTURE_SOURCES.get(identifier)
        if source_relative is None and identifier not in BLOCK_TEXTURE_SOURCES:
            candidate = "block/%s.png" % identifier
            if (UPSTREAM_TEXTURES / candidate).is_file():
                source_relative = candidate
            elif identifier.startswith("mangrove_") or identifier.startswith("hollow_mangrove"):
                source_relative = "block/wood/planks_mangrove_0.png"
        if identifier == "mangrove_leaves":
            terrain_data[texture_key] = {"textures": [{"path": "textures/blocks/leaves_birch", "tint_color": "#497436"}]}
        elif identifier == "maze_slime_block":
            terrain_data[texture_key] = {"textures": "textures/blocks/slime"}
        elif identifier.endswith("trophy"):
            terrain_data[texture_key] = {"textures": "textures/blocks/mazestone"}
        elif source_relative:
            target_name = identifier + ".png"
            copy_texture(source_relative, RP / "textures" / "blocks" / target_name)
            terrain_data[texture_key] = {"textures": "textures/blocks/%s" % identifier}
        else:
            terrain_data[texture_key] = {"textures": "textures/blocks/mazestone"}
        blocks[texture_key] = {
            "textures": texture_key,
            "sound": (
                "wood"
                if (
                    "mangrove" in identifier
                    or identifier
                    in (
                        "smoker",
                        "fire_jet",
                        "encased_towerwood",
                        "encased_smoker",
                        "encased_fire_jet",
                    )
                )
                else "grass"
                if identifier in ("huge_lily_pad", "huge_water_lily")
                else "stone"
            ),
        }
    register_fire_swamp_textures(terrain_data)
    write_json(RP / "textures" / "terrain_texture.json", terrain)
    write_json(RP / "blocks.json", blocks)

    item_atlas = load_json(RP / "textures" / "item_texture.json")
    item_data = item_atlas["texture_data"]
    for identifier in catalog["items"]:
        alias = ITEM_TEXTURE_ALIASES.get(identifier, identifier + ".png")
        if alias is None:
            item_data["tf_slice:" + identifier] = {"textures": "textures/items/book_enchanted"}
            continue
        source = UPSTREAM_TEXTURES / "item" / alias
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(str(source), str(RP / "textures" / "items" / (identifier + ".png")))
        item_data["tf_slice:" + identifier] = {"textures": "textures/items/%s" % identifier}
    write_json(RP / "textures" / "item_texture.json", item_atlas)
    write_json(
        RP / "models" / "blocks" / "swamp_plants.geo.json",
        swamp_plant_geometry(),
    )

    creative = load_json(BP / "item_catalog" / "crafting_item_catalog.json")
    creative_items = creative["minecraft:crafting_items_catalog"]["categories"][0]["groups"][0]["items"]
    for identifier in creative_item_identifiers(catalog["items"]) + all_blocks:
        full_id = "tf_slice:" + identifier
        if full_id not in creative_items:
            creative_items.append(full_id)
    write_json(BP / "item_catalog" / "crafting_item_catalog.json", creative)

    for language, index in (("en_US.lang", 0), ("zh_CN.lang", 1)):
        path = RP / "texts" / language
        lines = path.read_text(encoding="utf-8").splitlines()
        key_lines = dict(
            (line.split("=", 1)[0], line_index)
            for line_index, line in enumerate(lines)
            if "=" in line
        )
        for identifier in catalog["items"]:
            key = "item.tf_slice:%s.name" % identifier
            value = key + "=" + ITEM_NAMES[identifier][index]
            if key in key_lines:
                lines[key_lines[key]] = value
            else:
                key_lines[key] = len(lines)
                lines.append(value)
        for identifier in all_blocks:
            key = "tile.tf_slice:%s.name" % identifier
            value = key + "=" + BLOCK_NAMES[identifier][index]
            if key in key_lines:
                lines[key_lines[key]] = value
            else:
                key_lines[key] = len(lines)
                lines.append(value)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    generate_recipes()
    build_public_block_shapes()
    build_localization(ROOT)
    normalize_creative_catalog(ROOT)
    print("generated", len(catalog["items"]), "items and", len(all_blocks), "blocks")


if __name__ == "__main__":
    main()
