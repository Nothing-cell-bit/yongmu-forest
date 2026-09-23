#!/usr/bin/env python3
"""Build the 4.3.2508 ruin-mob dependency closure.

The Java jar is the behavior and asset baseline.  This generator deliberately
keeps each non-vanilla silhouette, its equipment, loot and sound bank explicit
so a later rebuild cannot silently fall back to a zombie-shaped placeholder.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

try:
    from tools.build_courtyard_blocks import build as build_courtyard_blocks
except ImportError:
    from build_courtyard_blocks import build as build_courtyard_blocks
try:
    from tools.build_public_block_shapes import build as build_public_block_shapes
except ImportError:
    from build_public_block_shapes import build as build_public_block_shapes
try:
    from tools.build_creative_catalog import normalize_creative_catalog
    from tools.build_localization import build_localization
except ImportError:
    from build_creative_catalog import normalize_creative_catalog
    from build_localization import build_localization


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
UPSTREAM = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
)
UPSTREAM_MODEL_TEXTURES = UPSTREAM / "textures" / "model"
UPSTREAM_ITEM_TEXTURES = UPSTREAM / "textures" / "item"


MOBS = {
    "raven": {
        "families": ["raven", "animal", "mob"],
        "health": 10,
        "movement": 0.20,
        "attack": 0,
        "box": [0.5, 0.9],
        "geometry": "geometry.tf_slice.raven",
        "texture": "textures/entity/tf_slice/raven",
        "texture_source": "raven.png",
        "profile": "raven",
        "egg": ["#1D1D1D", "#696969"],
    },
    "skeleton_druid": {
        "families": ["skeleton_druid", "skeleton", "undead", "monster", "mob"],
        "health": 20,
        "movement": 0.25,
        "attack": 2,
        "box": [0.6, 1.99],
        "geometry": "geometry.tf_slice.skeleton_druid",
        "texture": "textures/entity/tf_slice/skeleton_druid",
        "texture_source": "skeletondruid.png",
        "profile": "biped",
        "equipment": "skeleton_druid",
        "egg": ["#5F6A52", "#D8D8C4"],
    },
    "swarm_spider": {
        "families": ["swarm_spider", "spider", "monster", "mob"],
        "health": 3,
        "movement": 0.3,
        "attack": 1,
        # Locked TFEntities dimensions; the renderer independently scales 0.5.
        "box": [0.8, 0.4],
        "geometry": "geometry.spider.v1.8",
        "texture": "textures/entity/tf_slice/swarm_spider",
        "texture_source": "swarmspider.png",
        "profile": "spider",
        "scale": 0.5,
        "egg": ["#392D24", "#A64B32"],
    },
    "hedge_spider": {
        "families": ["hedge_spider", "spider", "monster", "mob"],
        "health": 16,
        "movement": 0.3,
        "attack": 2,
        "box": [1.4, 0.9],
        "geometry": "geometry.spider.v1.8",
        "texture": "textures/entity/tf_slice/hedge_spider",
        "texture_source": "hedgespider.png",
        "profile": "spider",
        "egg": ["#35633B", "#9FC45C"],
    },
    "hostile_wolf": {
        "families": ["hostile_wolf", "wolf", "monster", "mob"],
        "health": 20,
        "movement": 0.30,
        "attack": 2,
        "box": [0.8, 0.85],
        "geometry": "geometry.tf_slice.hostile_wolf",
        "texture": "textures/entity/wolf/wolf_angry",
        "profile": "wolf",
        "egg": ["#6B625C", "#B84232"],
    },
    "wraith": {
        "families": ["wraith", "undead", "monster", "mob"],
        "health": 20,
        "movement": 0.50,
        "attack": 5,
        "box": [0.6, 1.8],
        "geometry": "geometry.tf_slice.wraith",
        "texture": "textures/entity/tf_slice/wraith",
        "texture_source": "ghost.png",
        "profile": "wraith",
        "egg": ["#D9E2E2", "#4A5A63"],
    },
    "rising_zombie": {
        "families": ["rising_zombie", "zombie", "undead", "monster", "mob"],
        "health": 20,
        "movement": 0.23,
        "attack": 3,
        "box": [0.6, 1.9],
        "geometry": "geometry.tf_slice.rising_zombie",
        "texture": "textures/entity/zombie/zombie",
        "profile": "rising",
        "egg": ["#315234", "#688A56"],
    },
    "redcap": {
        "families": ["redcap", "monster", "mob"],
        "health": 20,
        "movement": 0.28,
        "attack": 2,
        "box": [0.9, 1.4],
        "geometry": "geometry.tf_slice.redcap",
        "texture": "textures/entity/tf_slice/redcap",
        "texture_source": "redcap.png",
        "profile": "biped",
        "equipment": "redcap",
        "egg": ["#3B3A6C", "#AB1E14"],
    },
    "redcap_sapper": {
        "families": ["redcap_sapper", "redcap", "monster", "mob"],
        "health": 30,
        "movement": 0.28,
        "attack": 2,
        "armor": 2,
        "box": [0.9, 1.4],
        "geometry": "geometry.tf_slice.redcap",
        "texture": "textures/entity/tf_slice/redcap_sapper",
        "texture_source": "redcapsapper.png",
        "profile": "biped",
        "equipment": "redcap_sapper",
        "egg": ["#575D21", "#AB1E14"],
    },
    "kobold": {
        "families": ["kobold", "monster", "mob"],
        "health": 13,
        "movement": 0.28,
        "attack": 4,
        "box": [0.6, 1.3],
        "geometry": "geometry.tf_slice.kobold",
        "texture": "textures/entity/tf_slice/kobold",
        "texture_source": "kobold.png",
        "profile": "kobold",
        "egg": ["#445B69", "#B3C0C8"],
    },
    "slime_beetle": {
        "families": ["slime_beetle", "arthropod", "monster", "mob"],
        "health": 25,
        "movement": 0.23,
        "attack": 4,
        "box": [0.9, 0.5],
        "geometry": "geometry.tf_slice.slime_beetle",
        "texture": "textures/entity/tf_slice/slime_beetle",
        "texture_source": "slimebeetle.png",
        "profile": "beetle",
        "egg": ["#0C1606", "#60A74C"],
    },
    "fire_beetle": {
        "families": ["fire_beetle", "arthropod", "monster", "mob"],
        "health": 25,
        "movement": 0.23,
        "attack": 4,
        "box": [1.1, 0.5],
        "geometry": "geometry.tf_slice.fire_beetle",
        "texture": "textures/entity/tf_slice/fire_beetle",
        "texture_source": "firebeetle.png",
        "profile": "beetle",
        "egg": ["#1D0B00", "#CB6F25"],
    },
    "pinch_beetle": {
        "families": ["pinch_beetle", "arthropod", "monster", "mob"],
        "health": 40,
        "movement": 0.23,
        "attack": 4,
        "armor": 2,
        "box": [1.2, 0.5],
        "geometry": "geometry.tf_slice.pinch_beetle",
        "texture": "textures/entity/tf_slice/pinch_beetle",
        "texture_source": "pinchbeetle.png",
        "profile": "beetle",
        "egg": ["#BC9327", "#241609"],
    },
}


CHEST_LOOT = {
    "well": [
        ("minecraft:bread", 5),
        ("minecraft:torch", 8),
        ("minecraft:iron_ingot", 2),
        ("minecraft:bucket", 1),
    ],
    "foundation_basement": [
        ("minecraft:bread", 4),
        ("minecraft:iron_ingot", 3),
        ("minecraft:gold_ingot", 1),
        ("minecraft:map", 1),
    ],
    "druid_hut": [
        ("minecraft:bone", 8),
        ("minecraft:spider_eye", 4),
        ("minecraft:glow_berries", 4),
        ("minecraft:golden_apple", 1),
    ],
    "tree_cache": [
        ("minecraft:apple", 6),
        ("minecraft:bread", 4),
        ("minecraft:oak_sapling", 3),
        ("tf_slice:cicada", 2),
        ("minecraft:music_disc_13", 1),
    ],
    "graveyard": [
        ("minecraft:bone", 8),
        ("minecraft:rotten_flesh", 6),
        ("minecraft:iron_ingot", 3),
        ("minecraft:ender_pearl", 1),
    ],
    "hedge_maze": [
        ("minecraft:bread", 5),
        ("minecraft:iron_ingot", 3),
        ("minecraft:gold_ingot", 2),
        ("minecraft:diamond", 1),
    ],
    "hollow_hill_small": [
        ("minecraft:iron_ingot", 12),
        ("minecraft:wheat", 12),
        ("minecraft:string", 12),
        ("minecraft:bucket", 12),
        ("minecraft:torch", 8),
        ("minecraft:arrow", 8),
        ("minecraft:gunpowder", 6),
        ("minecraft:bread", 6),
        ("minecraft:gold_ingot", 4),
        ("minecraft:iron_pickaxe", 4),
        ("tf_slice:liveroot", 4),
        ("tf_slice:transformation_powder", 2),
        ("minecraft:diamond", 1),
    ],
    "hollow_hill_medium": [
        ("minecraft:iron_ingot", 12),
        ("minecraft:carrot", 12),
        ("minecraft:ladder", 12),
        ("minecraft:bucket", 12),
        ("minecraft:baked_potato", 8),
        ("minecraft:arrow", 8),
        ("minecraft:torch", 8),
        ("minecraft:diamond", 1),
        ("minecraft:emerald", 1),
    ],
    "hollow_hill_large": [
        ("minecraft:gold_nugget", 12),
        ("minecraft:potato", 12),
        ("minecraft:cod", 12),
        # Upstream hill_3 gives 1-5 torchberries at the same common-food
        # tier. Weight 10 preserves that count under chest_loot_table.
        ("tf_slice:torchberries", 10),
        ("minecraft:torch", 8),
        ("minecraft:arrow", 8),
        ("minecraft:gunpowder", 6),
        ("minecraft:pumpkin_pie", 6),
        ("minecraft:diamond", 2),
        ("minecraft:emerald", 2),
    ],
}

NAMES_ZH = {
    "raven": "乌鸦",
    "skeleton_druid": "骷髅德鲁伊",
    "swarm_spider": "群聚蜘蛛",
    "hedge_spider": "树篱蜘蛛",
    "hostile_wolf": "敌对狼",
    "wraith": "幽灵",
    "rising_zombie": "复生僵尸",
    "redcap": "红帽地精",
    "redcap_sapper": "红帽工兵",
    "kobold": "狗头人",
}

NAMES_ZH.update(
    {
        "slime_beetle": "黏液甲虫",
        "fire_beetle": "喷火甲虫",
        "pinch_beetle": "夹虫",
    }
)

ITEM_NAMES_ZH = {
    "raven_feather": "乌鸦羽毛",
    "torchberries": "火炬浆果",
    "ironwood_pickaxe": "铁木镐",
    "ironwood_boots": "铁木靴子",
}

BIOME_CATALOG_ITEMS = (
    "tf_slice:tiny_bird_spawn_egg",
    "tf_slice:squirrel_spawn_egg",
    "tf_slice:dwarf_rabbit_spawn_egg",
    "tf_slice:quest_ram_spawn_egg",
    "tf_slice:penguin_spawn_egg",
    "tf_slice:crumble_horn",
    "tf_slice:quest_ram_trophy",
    "tf_slice:rainbow_oak_leaves",
    "tf_slice:fiddlehead",
    "tf_slice:mushgloom",
    "tf_slice:firefly",
    "tf_slice:firefly_jar",
    "tf_slice:cicada_jar",
    "tf_slice:canopy_fence",
    "tf_slice:fallen_leaves",
)

BIOME_LOCALIZATION_ZH = (
    ("entity.tf_slice:forest_wyrm.name", "娜迦"),
    ("item.spawn_egg.entity.tf_slice:forest_wyrm.name", "生成 娜迦"),
    ("tf_slice:itemGroup.name.twilight_forest", "暮色森林"),
    ("entity.tf_slice:tiny_bird.name", "小鸟"),
    ("item.spawn_egg.entity.tf_slice:tiny_bird.name", "生成 小鸟"),
    ("entity.tf_slice:squirrel.name", "暮色松鼠"),
    ("item.spawn_egg.entity.tf_slice:squirrel.name", "生成 暮色松鼠"),
    ("entity.tf_slice:dwarf_rabbit.name", "侏儒兔"),
    ("item.spawn_egg.entity.tf_slice:dwarf_rabbit.name", "生成 侏儒兔"),
    ("entity.tf_slice:quest_ram.name", "谜题羊"),
    ("item.spawn_egg.entity.tf_slice:quest_ram.name", "生成 谜题羊"),
    ("entity.tf_slice:penguin.name", "企鹅"),
    ("item.spawn_egg.entity.tf_slice:penguin.name", "生成 企鹅"),
    ("item.tf_slice:crumble_horn.name", "瓦解号角"),
    ("tile.tf_slice:quest_ram_trophy.name", "谜题羊战利品"),
    ("tile.tf_slice:rainbow_oak_leaves.name", "彩虹橡树叶"),
    ("tile.tf_slice:fiddlehead.name", "蕨芽"),
    ("tile.tf_slice:mushgloom.name", "幽光蘑菇"),
    ("tile.tf_slice:firefly.name", "萤火虫"),
    ("tile.tf_slice:firefly_jar.name", "萤火虫罐"),
    ("tile.tf_slice:cicada_jar.name", "蝉罐"),
    ("tile.tf_slice:canopy_fence.name", "苍穹木栅栏"),
    ("tile.tf_slice:fallen_leaves.name", "落叶堆"),
)

BIOME_LOCALIZATION_EN = (
    ("entity.tf_slice:forest_wyrm.name", "Naga"),
    ("item.spawn_egg.entity.tf_slice:forest_wyrm.name", "Spawn Naga"),
    ("tf_slice:itemGroup.name.twilight_forest", "Twilight Forest"),
    ("entity.tf_slice:tiny_bird.name", "Tiny Bird"),
    ("item.spawn_egg.entity.tf_slice:tiny_bird.name", "Spawn Tiny Bird"),
    ("entity.tf_slice:squirrel.name", "Twilight Squirrel"),
    ("item.spawn_egg.entity.tf_slice:squirrel.name", "Spawn Twilight Squirrel"),
    ("entity.tf_slice:dwarf_rabbit.name", "Dwarf Rabbit"),
    ("item.spawn_egg.entity.tf_slice:dwarf_rabbit.name", "Spawn Dwarf Rabbit"),
    ("entity.tf_slice:quest_ram.name", "Quest Ram"),
    ("item.spawn_egg.entity.tf_slice:quest_ram.name", "Spawn Quest Ram"),
    ("entity.tf_slice:penguin.name", "Penguin"),
    ("item.spawn_egg.entity.tf_slice:penguin.name", "Spawn Penguin"),
    ("item.tf_slice:crumble_horn.name", "Crumble Horn"),
    ("tile.tf_slice:quest_ram_trophy.name", "Quest Ram Trophy"),
    ("tile.tf_slice:rainbow_oak_leaves.name", "Rainbow Oak Leaves"),
    ("tile.tf_slice:fiddlehead.name", "Fiddlehead"),
    ("tile.tf_slice:mushgloom.name", "Mushgloom"),
    ("tile.tf_slice:firefly.name", "Firefly"),
    ("tile.tf_slice:firefly_jar.name", "Firefly Jar"),
    ("tile.tf_slice:cicada_jar.name", "Cicada Jar"),
    ("tile.tf_slice:canopy_fence.name", "Canopy Fence"),
    ("tile.tf_slice:fallen_leaves.name", "Fallen Leaves"),
)


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def cube(origin, size, uv, **extra):
    value = {"origin": origin, "size": size, "uv": uv}
    value.update(extra)
    return value


def java_part_pivot(pivot):
    """Convert a Java ModelPart pivot into Bedrock model coordinates."""
    return [pivot[0], 24 - pivot[1], pivot[2]]


def java_part_cube(part_pivot, local_origin, size, uv, **extra):
    """Convert a Java CubeListBuilder cube without guessing its Y origin.

    Java model Y grows down from the head while Bedrock geometry Y grows up
    from the feet.  The Java cube origin is also local to its ModelPart.
    """
    return cube(
        [
            part_pivot[0] + local_origin[0],
            24 - (part_pivot[1] + local_origin[1] + size[1]),
            part_pivot[2] + local_origin[2],
        ],
        size,
        uv,
        **extra
    )


def java_part_bone(name, pivot, cubes, parent="root", rotation=None):
    value = {
        "name": name,
        "parent": parent,
        "pivot": java_part_pivot(pivot),
        "cubes": cubes,
    }
    if rotation is not None:
        value["rotation"] = rotation
    return value


def geometry(identifier, width, height, bones, bounds=(2.5, 3.0, 1.0)):
    return {
        "description": {
            "identifier": identifier,
            "texture_width": width,
            "texture_height": height,
            "visible_bounds_width": bounds[0],
            "visible_bounds_height": bounds[1],
            "visible_bounds_offset": [0, bounds[2], 0],
        },
        "bones": bones,
    }


def item_bones(
    right_parent="rightArm",
    left_parent="leftArm",
    right_pivot=(-5.5, 9, 1),
    left_pivot=(5.5, 9, 1),
):
    return [
        {
            "name": "rightItem",
            "parent": right_parent,
            "pivot": list(right_pivot),
            "neverRender": True,
        },
        {
            "name": "leftItem",
            "parent": left_parent,
            "pivot": list(left_pivot),
            "neverRender": True,
        },
    ]


def raven_geometry():
    return geometry(
        "geometry.tf_slice.raven",
        32,
        32,
        [
            {"name": "root", "pivot": [0, 0, 0]},
            {
                "name": "body",
                "parent": "root",
                "pivot": [0, 7, 1],
                "rotation": [-30, 0, 0],
                "cubes": [cube([-1.5, 3, 0], [3, 4, 6], [0, 6])],
            },
            {
                "name": "head",
                "parent": "root",
                "pivot": [0, 8, -1.5],
                "cubes": [cube([-1.5, 6.5, -4.5], [3, 3, 3], [0, 0])],
            },
            {
                "name": "upper_beak",
                "parent": "head",
                "pivot": [0, 8, -4],
                "rotation": [15, 0, 0],
                "cubes": [cube([-0.5, 7, -6], [1, 1, 2], [12, 0])],
            },
            {
                "name": "lower_beak",
                "parent": "head",
                "pivot": [0, 8, -4],
                "rotation": [-15, 0, 0],
                "cubes": [cube([-0.5, 8, -6], [1, 1, 2], [12, 3])],
            },
            {
                "name": "right_wing",
                "parent": "body",
                "pivot": [-1.5, 7, 1],
                "cubes": [cube([-2.5, 4, 0], [1, 3, 6], [0, 16])],
            },
            {
                "name": "left_wing",
                "parent": "body",
                "pivot": [1.5, 7, 1],
                "cubes": [
                    cube([1.5, 4, 0], [1, 3, 6], [0, 16], mirror=True)
                ],
            },
            {
                "name": "right_leg",
                "parent": "root",
                "pivot": [-1.5, 3, 1],
                "cubes": [cube([-1.5, 1, 0.5], [1, 2, 1], [14, 16])],
            },
            {
                "name": "right_foot",
                "parent": "right_leg",
                "pivot": [-1.5, 1, 1.5],
                "rotation": [30, 0, 0],
                "cubes": [cube([-1.5, 0, 0.5], [1, 1, 2], [14, 20])],
            },
            {
                "name": "left_leg",
                "parent": "root",
                "pivot": [0.5, 3, 1],
                "cubes": [
                    cube([0.5, 1, 0.5], [1, 2, 1], [14, 16], mirror=True)
                ],
            },
            {
                "name": "left_foot",
                "parent": "left_leg",
                "pivot": [0.5, 1, 1.5],
                "rotation": [30, 0, 0],
                "cubes": [
                    cube([0.5, 0, 0.5], [1, 1, 2], [14, 20], mirror=True)
                ],
            },
            {
                "name": "tail",
                "parent": "body",
                "pivot": [0, 4, 5],
                "rotation": [-30, 0, 0],
                "cubes": [cube([-1.5, 3.5, 5], [3, 1, 3], [0, 25])],
            },
        ],
        (1.5, 1.5, 0.45),
    )


def redcap_geometry():
    # Exact classic RedcapModel conversion from the 4.3.2508 jar, including
    # FixedHumanoidModel.setupAnim's runtime `hat.copyFrom(head)`. The layer
    # definition creates the hat at Y=6, but every rendered frame copies the
    # head's Y=8 pivot before drawing it. These remain root siblings: parenting
    # the hat to the head would apply the look transform twice.
    head_pivot = (0, 8, 0)
    hat_pivot = (0, 8, 0)
    body_pivot = (0, 5, 0)
    right_arm_pivot = (-4, 7, 0)
    left_arm_pivot = (4, 7, 0)
    right_leg_pivot = (-2.5, 15, 0)
    left_leg_pivot = (2.5, 15, 0)
    bones = [
        {"name": "root", "pivot": [0, 0, 0]},
        java_part_bone(
            "head",
            head_pivot,
            [
                java_part_cube(
                    head_pivot, (-3.5, -8, -3.5), (7, 7, 7), (0, 0)
                ),
                java_part_cube(
                    head_pivot, (-4.5, -5, -0.5), (1, 2, 1), (0, 0)
                ),
                java_part_cube(
                    head_pivot,
                    (-5.5, -6, -0.5),
                    (1, 2, 1),
                    (0, 0),
                    mirror=True,
                ),
                java_part_cube(
                    head_pivot,
                    (3.5, -5, -0.5),
                    (1, 2, 1),
                    (0, 0),
                    mirror=True,
                ),
                java_part_cube(
                    head_pivot, (4.5, -6, -0.5), (1, 2, 1), (0, 0)
                ),
            ],
        ),
        java_part_bone(
            "hat",
            hat_pivot,
            [
                java_part_cube(
                    hat_pivot, (-2, -8.5, -3), (4, 5, 7), (32, 0)
                )
            ],
        ),
        java_part_bone(
            "body",
            body_pivot,
            [java_part_cube(body_pivot, (-4, 1, -2), (8, 9, 4), (12, 19))],
        ),
        java_part_bone(
            "rightArm",
            right_arm_pivot,
            [
                java_part_cube(
                    right_arm_pivot,
                    (-3, -1, -1.5),
                    (3, 12, 3),
                    (36, 17),
                    mirror=True,
                )
            ],
        ),
        java_part_bone(
            "leftArm",
            left_arm_pivot,
            [
                java_part_cube(
                    left_arm_pivot,
                    (0, -1, -1.5),
                    (3, 12, 3),
                    (36, 17),
                )
            ],
        ),
        java_part_bone(
            "rightLeg",
            right_leg_pivot,
            [
                java_part_cube(
                    right_leg_pivot,
                    (-1.5, 0, -1.5),
                    (3, 9, 3),
                    (0, 20),
                    mirror=True,
                )
            ],
        ),
        java_part_bone(
            "leftLeg",
            left_leg_pivot,
            [
                java_part_cube(
                    left_leg_pivot,
                    (-1.5, 0, -1.5),
                    (3, 9, 3),
                    (0, 20),
                )
            ],
        ),
    ]
    bones.extend(
        item_bones(
            right_pivot=(-5.5, 7, 1),
            left_pivot=(5.5, 7, 1),
        )
    )
    return geometry("geometry.tf_slice.redcap", 64, 32, bones, (2.0, 2.2, 0.9))


def kobold_geometry():
    bones = [
        {"name": "root", "pivot": [0, 0, 0]},
        {
            "name": "body",
            "parent": "root",
            "pivot": [0, 12, 0],
            "cubes": [cube([-3.5, 5, -2], [7, 7, 4], [12, 19])],
        },
        {
            "name": "head",
            "parent": "root",
            "pivot": [0, 18, 0],
            "cubes": [cube([-3.5, 12, -3], [7, 6, 6], [0, 0])],
        },
        {
            "name": "rightEar",
            "parent": "head",
            "pivot": [3.5, 15, -1],
            "rotation": [0, 15, -20],
            "cubes": [cube([3.5, 15, -1], [4, 4, 1], [48, 20])],
        },
        {
            "name": "leftEar",
            "parent": "head",
            "pivot": [-3.5, 15, -1],
            "rotation": [0, -15, 20],
            "cubes": [
                cube([-7.5, 15, -1], [4, 4, 1], [48, 25], mirror=True)
            ],
        },
        {
            "name": "snout",
            "parent": "head",
            "pivot": [0, 16, -3],
            "cubes": [cube([-1.5, 14, -5], [3, 2, 3], [28, 0])],
        },
        {
            "name": "jaw",
            "parent": "head",
            "pivot": [0, 16, -3],
            "rotation": [12, 0, 0],
            "cubes": [cube([-1.5, 13, -5], [3, 1, 3], [28, 5])],
        },
        {
            "name": "rightArm",
            "parent": "body",
            "pivot": [-3.5, 12, 0],
            "rotation": [-27, 0, 0],
            "cubes": [cube([-6.5, 5, -1.5], [3, 7, 3], [36, 17])],
        },
        {
            "name": "leftArm",
            "parent": "body",
            "pivot": [3.5, 12, 0],
            "rotation": [-27, 0, 0],
            "cubes": [
                cube([3.5, 5, -1.5], [3, 7, 3], [36, 17], mirror=True)
            ],
        },
        {
            "name": "rightLeg",
            "parent": "root",
            "pivot": [-2, 5, 0],
            "cubes": [cube([-3.5, 0, -1.5], [3, 5, 3], [0, 20])],
        },
        {
            "name": "leftLeg",
            "parent": "root",
            "pivot": [2, 5, 0],
            "cubes": [
                cube([0.5, 0, -1.5], [3, 5, 3], [0, 20], mirror=True)
            ],
        },
    ]
    bones.extend(item_bones())
    return geometry("geometry.tf_slice.kobold", 64, 32, bones, (2.0, 2.0, 0.75))


def humanoid_geometry(identifier, dress=False, item_slots=False):
    bones = [
        {"name": "root", "pivot": [0, 0, 0]},
        {
            "name": "body",
            "parent": "root",
            "pivot": [0, 24, 0],
            "cubes": [cube([-4, 12, -2], [8, 12, 4], [8, 16])],
        },
        {
            "name": "head",
            "parent": "root",
            "pivot": [0, 24, 0],
            "cubes": [cube([-4, 24, -4], [8, 8, 8], [0, 0])],
        },
        {
            "name": "hat",
            "parent": "head",
            "pivot": [0, 24, 0],
            "cubes": [
                cube(
                    [-4, 24, -4],
                    [8, 8, 8],
                    [32, 0],
                    inflate=0.5,
                )
            ],
        },
        {
            "name": "rightArm",
            "parent": "body",
            "pivot": [-5, 22, 0],
            "cubes": [cube([-6, 10, -1], [2, 12, 2], [0, 16])],
        },
        {
            "name": "leftArm",
            "parent": "body",
            "pivot": [5, 22, 0],
            "cubes": [
                cube([4, 10, -1], [2, 12, 2], [0, 16], mirror=True)
            ],
        },
        {
            "name": "rightLeg",
            "parent": "root",
            "pivot": [-1, 12, 0],
            "cubes": [cube([-2, 0, -1], [2, 12, 2], [0, 16])],
        },
        {
            "name": "leftLeg",
            "parent": "root",
            "pivot": [3, 12, 0],
            "cubes": [
                cube([2, 0, -1], [2, 12, 2], [0, 16], mirror=True)
            ],
        },
    ]
    if dress:
        bones.append(
            {
                "name": "dress",
                "parent": "body",
                "pivot": [0, 12, 0],
                "cubes": [cube([-4, 0, -2], [8, 12, 4], [32, 16])],
            }
        )
    if item_slots:
        bones.extend(
            item_bones(
                right_pivot=(-6, 15, 1),
                left_pivot=(6, 15, 1),
            )
        )
    return geometry(identifier, 64, 32, bones, (2.0, 3.5, 1.3))


def wraith_geometry():
    value = humanoid_geometry("geometry.tf_slice.wraith", dress=True)
    value["bones"] = [
        bone
        for bone in value["bones"]
        if bone["name"] not in ("rightLeg", "leftLeg", "hat")
    ]
    return value


def hostile_wolf_geometry():
    # HostileWolfModel is an old-wolf ModelPart layout.  Convert every cube
    # from its local Java origin; copying Java local Y values directly is what
    # previously detached the body, muzzle and ears.
    head_pivot = (-1, 13.5, -7)
    body_pivot = (0, 14, 2)
    upper_body_pivot = (-1, 14, -3)
    right_hind_pivot = (-2.5, 16, 7)
    left_hind_pivot = (0.5, 16, 7)
    right_front_pivot = (-2.5, 16, -4)
    left_front_pivot = (0.5, 16, -4)
    tail_pivot = (-1, 12, 8)
    return geometry(
        "geometry.tf_slice.hostile_wolf",
        64,
        32,
        [
            {"name": "root", "pivot": [0, 0, 0]},
            java_part_bone(
                "head",
                head_pivot,
                [
                    java_part_cube(
                        head_pivot, (-2, -3, -2), (6, 6, 4), (0, 0)
                    ),
                    java_part_cube(
                        head_pivot, (-0.5, 0, -5), (3, 3, 4), (0, 10)
                    ),
                    java_part_cube(
                        head_pivot, (-2, -5, 0), (2, 2, 1), (16, 14)
                    ),
                    java_part_cube(
                        head_pivot, (2, -5, 0), (2, 2, 1), (16, 14)
                    ),
                ],
            ),
            java_part_bone(
                "body",
                body_pivot,
                [
                    java_part_cube(
                        body_pivot, (-3, -2, -3), (6, 9, 6), (18, 14)
                    )
                ],
                rotation=[90, 0, 0],
            ),
            java_part_bone(
                "upperBody",
                upper_body_pivot,
                [
                    java_part_cube(
                        upper_body_pivot,
                        (-3, -3, -3),
                        (8, 6, 7),
                        (21, 0),
                    )
                ],
                rotation=[90, 0, 0],
            ),
            java_part_bone(
                "leg0",
                right_hind_pivot,
                [
                    java_part_cube(
                        right_hind_pivot, (0, 0, -1), (2, 8, 2), (0, 18)
                    )
                ],
            ),
            java_part_bone(
                "leg1",
                left_hind_pivot,
                [
                    java_part_cube(
                        left_hind_pivot, (0, 0, -1), (2, 8, 2), (0, 18)
                    )
                ],
            ),
            java_part_bone(
                "leg2",
                right_front_pivot,
                [
                    java_part_cube(
                        right_front_pivot, (0, 0, -1), (2, 8, 2), (0, 18)
                    )
                ],
            ),
            java_part_bone(
                "leg3",
                left_front_pivot,
                [
                    java_part_cube(
                        left_front_pivot, (0, 0, -1), (2, 8, 2), (0, 18)
                    )
                ],
            ),
            java_part_bone(
                "tail",
                tail_pivot,
                [
                    java_part_cube(
                        tail_pivot, (0, 0, -1), (2, 8, 2), (9, 18)
                    )
                ],
                rotation=[36, 0, 0],
            ),
        ],
        (2.5, 2.3, 0.75),
    )


def rising_zombie_geometry():
    """Vanilla zombie geometry under the Java renderer's one-block pivot."""
    return geometry(
        "geometry.tf_slice.rising_zombie",
        64,
        32,
        [
            {"name": "root", "pivot": [0, 0, 0]},
            {
                "name": "risePivot",
                "parent": "root",
                "pivot": [0, 16, 0],
                "neverRender": True,
            },
            {
                "name": "waist",
                "parent": "risePivot",
                "pivot": [0, 12, 0],
                "neverRender": True,
            },
            {
                "name": "body",
                "parent": "waist",
                "pivot": [0, 24, 0],
                "cubes": [cube([-4, 12, -2], [8, 12, 4], [16, 16])],
            },
            {
                "name": "head",
                "parent": "body",
                "pivot": [0, 24, 0],
                "cubes": [cube([-4, 24, -4], [8, 8, 8], [0, 0])],
            },
            {
                "name": "hat",
                "parent": "head",
                "pivot": [0, 24, 0],
                "cubes": [
                    cube([-4, 24, -4], [8, 8, 8], [32, 0], inflate=0.5)
                ],
                "neverRender": True,
            },
            {
                "name": "rightArm",
                "parent": "body",
                "pivot": [-5, 22, 0],
                "cubes": [cube([-8, 12, -2], [4, 12, 4], [40, 16])],
            },
            {
                "name": "leftArm",
                "parent": "body",
                "pivot": [5, 22, 0],
                "cubes": [
                    cube([4, 12, -2], [4, 12, 4], [40, 16], mirror=True)
                ],
            },
            {
                "name": "rightLeg",
                "parent": "body",
                "pivot": [-1.9, 12, 0],
                "cubes": [cube([-3.9, 0, -2], [4, 12, 4], [0, 16])],
            },
            {
                "name": "leftLeg",
                "parent": "body",
                "pivot": [1.9, 12, 0],
                "cubes": [
                    cube([-0.1, 0, -2], [4, 12, 4], [0, 16], mirror=True)
                ],
            },
        ],
        (2.0, 3.5, 1.3),
    )


def nature_bolt_geometry():
    return geometry(
        "geometry.tf_slice.nature_bolt",
        16,
        16,
        [
            {"name": "root", "pivot": [0, 0, 0]},
            {
                "name": "bolt",
                "parent": "root",
                "pivot": [0, 0, 0],
                "cubes": [
                    cube([-1.5, -1.5, -1.5], [3, 3, 3], [0, 0], inflate=0.3)
                ],
            },
        ],
        (0.8, 0.8, 0),
    )


def beetle_projectile_geometry(identifier, size):
    half = size / 2.0
    return geometry(
        identifier,
        16,
        16,
        [
            {"name": "root", "pivot": [0, 0, 0]},
            {
                "name": "bolt",
                "parent": "root",
                "pivot": [0, 0, 0],
                "cubes": [
                    cube(
                        [-half, -half, -half],
                        [size, size, size],
                        [0, 0],
                    )
                ],
            },
        ],
        (0.5, 0.5, 0),
    )


def java_model_cube(origin, size, uv, mirror=False):
    value = {"origin": origin, "size": size, "uv": uv}
    if mirror:
        value["mirror"] = True
    return value


def java_model_part(
    name,
    pivot,
    cubes=(),
    parent=None,
    rotation=(0.0, 0.0, 0.0),
):
    return {
        "name": name,
        "parent": parent,
        "pivot": pivot,
        "rotation": rotation,
        "cubes": list(cubes),
    }


def _clean_model_number(value):
    value = round(float(value), 6)
    return 0 if abs(value) < 0.000001 else value


def java_model_geometry(
    identifier,
    texture_width,
    texture_height,
    parts,
    bounds=(2.8, 2.0, 0.6),
):
    """Convert locked Java ModelPart records into Bedrock geometry.

    Java pivots and cube origins use a downward-positive Y axis. Bedrock uses
    upward-positive Y, so a cube's lower Y is `24 - (pivot + origin + size)`.
    Child pivots are accumulated without pre-applying parent rotation because
    both Java ModelPart and Bedrock bones inherit the parent transform.

    Bedrock entity pitch already uses the opposite right-handed X convention,
    so Java X/Y rotations keep their signs while Java Z is inverted by the Y
    reflection.
    """
    absolute_pivots = {}
    bones = []
    for part in parts:
        parent = part["parent"]
        parent_pivot = absolute_pivots.get(parent, (0.0, 0.0, 0.0))
        absolute = tuple(
            _clean_model_number(parent_pivot[index] + part["pivot"][index])
            for index in range(3)
        )
        absolute_pivots[part["name"]] = absolute
        bone = {
            "name": part["name"],
            "pivot": [
                absolute[0],
                _clean_model_number(24.0 - absolute[1]),
                absolute[2],
            ],
        }
        if parent is not None:
            bone["parent"] = parent
        java_rotation = part["rotation"]
        bedrock_rotation = [
            _clean_model_number(java_rotation[0]),
            _clean_model_number(java_rotation[1]),
            _clean_model_number(-java_rotation[2]),
        ]
        if any(bedrock_rotation):
            bone["rotation"] = bedrock_rotation
        converted_cubes = []
        for source_cube in part["cubes"]:
            local_origin = source_cube["origin"]
            size = source_cube["size"]
            converted = cube(
                [
                    _clean_model_number(absolute[0] + local_origin[0]),
                    _clean_model_number(
                        24.0
                        - (
                            absolute[1]
                            + local_origin[1]
                            + size[1]
                        )
                    ),
                    _clean_model_number(absolute[2] + local_origin[2]),
                ],
                size,
                source_cube["uv"],
            )
            if source_cube.get("mirror"):
                converted["mirror"] = True
            converted_cubes.append(converted)
        if converted_cubes:
            bone["cubes"] = converted_cubes
        bones.append(bone)
    return geometry(
        identifier,
        texture_width,
        texture_height,
        bones,
        bounds,
    )


def shared_classic_beetle_parts():
    """Return the locked classic head and six Java leg records."""
    return [
        java_model_part(
            "head",
            (0, 19, -5),
            [java_model_cube((-4, -4, -6), (8, 6, 6), (0, 0))],
        ),
        java_model_part(
            "right_antenna",
            (1, -3, -5),
            [java_model_cube((0, -0.5, -0.5), (10, 1, 1), (42, 4))],
            parent="head",
            rotation=(0, 60, -17),
        ),
        java_model_part(
            "left_antenna",
            (-1, -3, -5),
            [java_model_cube((0, -0.5, -0.5), (10, 1, 1), (42, 4))],
            parent="head",
            rotation=(0, 120, 17),
        ),
        java_model_part(
            "right_eye",
            (-3, -2, -5),
            [java_model_cube((-1.5, -1.5, -1.5), (3, 3, 3), (15, 12))],
            parent="head",
        ),
        java_model_part(
            "left_eye",
            (3, -2, -5),
            [java_model_cube((-1.5, -1.5, -1.5), (3, 3, 3), (15, 12))],
            parent="head",
        ),
        java_model_part(
            "leg_1",
            (-4, 21, 4),
            [java_model_cube((-9, -1, -1), (10, 2, 2), (40, 0), mirror=True)],
            rotation=(0, 40, -20),
        ),
        java_model_part(
            "leg_2",
            (4, 21, 4),
            [java_model_cube((-1, -1, -1), (10, 2, 2), (40, 0))],
            rotation=(0, -40, 20),
        ),
        java_model_part(
            "leg_3",
            (-4, 21, -1),
            [java_model_cube((-9, -1, -1), (10, 2, 2), (40, 0), mirror=True)],
            rotation=(0, 16, -20),
        ),
        java_model_part(
            "leg_4",
            (4, 21, -1),
            [java_model_cube((-1, -1, -1), (10, 2, 2), (40, 0))],
            rotation=(0, -16, 20),
        ),
        java_model_part(
            "leg_5",
            (-4, 21, -4),
            [java_model_cube((-9, -1, -1), (10, 2, 2), (40, 0), mirror=True)],
            rotation=(0, -16, -20),
        ),
        java_model_part(
            "leg_6",
            (4, 21, -4),
            [java_model_cube((-1, -1, -1), (10, 2, 2), (40, 0))],
            rotation=(0, 16, 20),
        ),
    ]


def fire_beetle_geometry():
    parts = shared_classic_beetle_parts()
    parts[5:5] = [
        java_model_part(
            "jaw_1a",
            (-3, 0, -6),
            [java_model_cube((0, 0, -2), (1, 1, 2), (0, 0))],
            parent="head",
            rotation=(20, 0, 0),
        ),
        java_model_part(
            "jaw_1b",
            (0, 0, -2),
            [java_model_cube((0, 0, 0), (1, 1, 2), (0, 0))],
            parent="jaw_1a",
            rotation=(0, 90, 0),
        ),
        java_model_part(
            "jaw_2a",
            (3, 0, -6),
            [java_model_cube((-1, 0, -2), (1, 1, 2), (0, 0))],
            parent="head",
            rotation=(20, 0, 0),
        ),
        java_model_part(
            "jaw_2b",
            (0, 0, -2),
            [java_model_cube((0, 0, -2), (1, 1, 2), (0, 0))],
            parent="jaw_2a",
            rotation=(0, 90, 0),
        ),
        java_model_part(
            "thorax",
            (0, 18, -4.5),
            [java_model_cube((-4.5, -4, 0), (9, 8, 2), (0, 22))],
        ),
        java_model_part(
            "connector_1",
            (0, 18, -3),
            [java_model_cube((-3, -3, 0), (6, 6, 1), (0, 12))],
        ),
        java_model_part(
            "connector_2",
            (0, 18, -4),
            [java_model_cube((-3, -3, -1), (6, 6, 1), (0, 12))],
        ),
        java_model_part(
            "rear",
            (0, 18, 7),
            [java_model_cube((-6, -9, -4), (12, 14, 9), (22, 9))],
            rotation=(90, 0, 0),
        ),
    ]
    return java_model_geometry(
        "geometry.tf_slice.fire_beetle",
        64,
        32,
        parts,
    )


def slime_beetle_geometry():
    parts = [
        java_model_part(
            "head",
            (0, 19, -5),
            [java_model_cube((-4, -4, -6), (8, 6, 6), (0, 0))],
        ),
        java_model_part(
            "left_antenna",
            (1, -3, -5),
            [java_model_cube((0, -0.5, -0.5), (12, 1, 1), (38, 4))],
            parent="head",
            rotation=(0, 60, -17),
        ),
        java_model_part(
            "right_antenna",
            (-1, -3, -5),
            [java_model_cube((0, -0.5, -0.5), (12, 1, 1), (38, 4))],
            parent="head",
            rotation=(0, 120, 17),
        ),
        java_model_part(
            "left_eye",
            (3, -2, -5),
            [java_model_cube((-1.5, -1.5, -1.5), (3, 3, 3), (15, 12))],
            parent="head",
        ),
        java_model_part(
            "right_eye",
            (-3, -2, -5),
            [java_model_cube((-1.5, -1.5, -1.5), (3, 3, 3), (15, 12))],
            parent="head",
        ),
        java_model_part(
            "mouth",
            (0, 1, -6),
            [java_model_cube((-1, -1, -1), (2, 2, 1), (17, 12))],
            parent="head",
        ),
        java_model_part(
            "body",
            (0, 18, 7),
            [java_model_cube((-4, -11, -4), (8, 10, 8), (31, 6))],
            rotation=(90, 0, 0),
        ),
        java_model_part(
            "front_left_leg",
            (2, 21, -4),
            [java_model_cube((-1, -1, -1), (10, 2, 2), (40, 0))],
            rotation=(0, 16, 20),
        ),
        java_model_part(
            "front_right_leg",
            (-2, 21, -4),
            [java_model_cube((-9, -1, -1), (10, 2, 2), (40, 0), mirror=True)],
            rotation=(0, -16, -20),
        ),
        java_model_part(
            "middle_left_leg",
            (2, 21, -1),
            [java_model_cube((-1, -1, -1), (10, 2, 2), (40, 0))],
            rotation=(0, -16, 20),
        ),
        java_model_part(
            "middle_right_leg",
            (-2, 21, -1),
            [java_model_cube((-9, -1, -1), (10, 2, 2), (40, 0), mirror=True)],
            rotation=(0, 16, -20),
        ),
        java_model_part(
            "back_left_leg",
            (2, 21, 4),
            [java_model_cube((-1, -1, -1), (10, 2, 2), (40, 0))],
            rotation=(0, -40, 20),
        ),
        java_model_part(
            "back_right_leg",
            (-2, 21, 4),
            [java_model_cube((-9, -1, -1), (10, 2, 2), (40, 0), mirror=True)],
            rotation=(0, 40, -20),
        ),
        java_model_part(
            "connector",
            (0, 19, -4),
            [java_model_cube((-3, -3, -1), (6, 6, 1), (0, 12))],
        ),
        java_model_part(
            "tail1",
            (0, 19, 9),
            [java_model_cube((-3, -3, -3), (6, 6, 6), (0, 20))],
        ),
        java_model_part(
            "tail2",
            (0, -3, 2),
            [java_model_cube((-3, -6, -3), (6, 6, 6), (0, 20))],
            parent="tail1",
        ),
        java_model_part(
            "slime_center",
            (0, -6, 0),
            [java_model_cube((-4, -10, -7), (8, 8, 8), (32, 24))],
            parent="tail2",
        ),
        java_model_part(
            "slime_cube",
            (0, 0, 0),
            [java_model_cube((-6, -12, -9), (12, 12, 12), (0, 40))],
            parent="slime_center",
        ),
    ]
    return java_model_geometry(
        "geometry.tf_slice.slime_beetle",
        64,
        64,
        parts,
        (2.8, 2.6, 0.9),
    )


def pinch_beetle_geometry():
    parts = shared_classic_beetle_parts()
    parts[5:5] = [
        java_model_part(
            "right_jaw_bottom",
            (-3, 1, -6),
            [java_model_cube((-1, -1, -1.5), (8, 2, 3), (40, 6))],
            parent="head",
            rotation=(0, 151, 0),
        ),
        java_model_part(
            "right_jaw_top",
            (7, 0, 0),
            [java_model_cube((-1, -1, -1), (10, 2, 2), (40, 10))],
            parent="right_jaw_bottom",
            rotation=(0, -60, 0),
        ),
        java_model_part(
            "right_tooth_1",
            (9, 0, 0),
            [java_model_cube((0, -0.5, 0), (2, 1, 1), (0, 0))],
            parent="right_jaw_top",
            rotation=(0, -30, 0),
        ),
        java_model_part(
            "right_tooth_2",
            (6, 0, 0),
            [java_model_cube((0, -0.5, 0), (2, 1, 1), (0, 0))],
            parent="right_jaw_top",
            rotation=(0, 90, 0),
        ),
        java_model_part(
            "right_tooth_3",
            (3, 0, 0),
            [java_model_cube((0, -0.5, 0), (2, 1, 1), (0, 0))],
            parent="right_jaw_top",
            rotation=(0, 90, 0),
        ),
        java_model_part(
            "left_jaw_bottom",
            (3, 1, -6),
            [java_model_cube((-1, -1, -1.5), (8, 2, 3), (40, 6))],
            parent="head",
            rotation=(0, 31, 0),
        ),
        java_model_part(
            "left_jaw_top",
            (7, 0, 0),
            [java_model_cube((-1, -1, -1), (10, 2, 2), (40, 10))],
            parent="left_jaw_bottom",
            rotation=(0, 60, 0),
        ),
        java_model_part(
            "left_tooth_1",
            (8, 0, -1),
            [java_model_cube((0, -0.5, 0), (2, 1, 1), (0, 0))],
            parent="left_jaw_top",
            rotation=(0, 30, 0),
        ),
        java_model_part(
            "left_tooth_2",
            (7, 0, 0),
            [java_model_cube((0, -0.5, 0), (2, 1, 1), (0, 0))],
            parent="left_jaw_top",
            rotation=(0, -90, 0),
        ),
        java_model_part(
            "left_tooth_3",
            (3.5, 0, 0),
            [java_model_cube((0, -0.5, 0), (2, 1, 1), (0, 0))],
            parent="left_jaw_top",
            rotation=(0, -90, 0),
        ),
        java_model_part(
            "thorax",
            (0, 18, -4.5),
            [java_model_cube((-4.5, -4, 0), (9, 8, 2), (0, 22))],
        ),
        java_model_part(
            "connector_1",
            (0, 18, -3),
            [java_model_cube((-3, -3, 0), (6, 6, 1), (0, 12))],
        ),
        java_model_part(
            "connector_2",
            (0, 18, -4),
            [java_model_cube((-3, -3, -1), (6, 6, 1), (0, 12))],
        ),
        java_model_part(
            "rear",
            (0, 18, 7),
            [java_model_cube((-5, -9, -4), (10, 10, 8), (28, 14))],
            rotation=(90, 0, 0),
        ),
    ]
    return java_model_geometry(
        "geometry.tf_slice.pinch_beetle",
        64,
        32,
        parts,
    )


def geometry_document():
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            raven_geometry(),
            redcap_geometry(),
            kobold_geometry(),
            humanoid_geometry(
                "geometry.tf_slice.skeleton_druid",
                dress=True,
                item_slots=True,
            ),
            wraith_geometry(),
            rising_zombie_geometry(),
            hostile_wolf_geometry(),
            nature_bolt_geometry(),
            beetle_projectile_geometry(
                "geometry.tf_slice.fire_breath", 1.0
            ),
            beetle_projectile_geometry(
                "geometry.tf_slice.slime_blob", 2.0
            ),
            slime_beetle_geometry(),
            fire_beetle_geometry(),
            pinch_beetle_geometry(),
        ],
    }


def redcap_boots_geometry():
    # Adapt the Java armor shell (4x12x4, inflation .65) to a 3x9x3 limb.
    # Explicit UV faces retain the full source armor region after this .75
    # fit correction. Use the legacy copied-owner skeleton: the recorded
    # NetEase build rejects the former per-boot binding expressions, leaving
    # boots stationary. Matching names/hierarchy receives the owner's pose.
    uv = {"north": {"uv": [4, 20], "uv_size": [4, 12]},
          "south": {"uv": [12, 20], "uv_size": [4, 12]},
          "west": {"uv": [0, 20], "uv_size": [4, 12]},
          "east": {"uv": [8, 20], "uv_size": [4, 12]},
          "up": {"uv": [4, 16], "uv_size": [4, 4]},
          "down": {"uv": [8, 20], "uv_size": [4, -4]}}
    bones = []
    for owner_bone in redcap_geometry()["bones"]:
        bone = {key: value for key, value in owner_bone.items() if key != "cubes"}
        if bone["name"] in ("rightLeg", "leftLeg"):
            bone["cubes"] = [{
                "origin": list(owner_bone["cubes"][0]["origin"]),
                "size": [3, 9, 3], "uv": uv, "inflate": 0.4875,
            }]
        bones.append(bone)
    return {"format_version": "1.12.0", "minecraft:geometry": [geometry(
        "geometry.tf_slice.redcap.armor.boots", 64, 32, bones, (2.0, 2.2, 0.9)
    )]}


def redcap_boots_attachable(kind):
    namespace = "minecraft" if kind == "iron" else "tf_slice"
    texture = "textures/models/armor/iron_1" if kind == "iron" else "textures/models/tf_slice/armor/ironwood_1"
    return {"format_version": "1.8.0", "minecraft:attachable": {"description": {
        "identifier": "%s:%s_boots" % (namespace, kind),
        "materials": {"default": "armor", "enchanted": "armor_enchanted"},
        "textures": {"default": texture, "enchanted": "textures/misc/enchanted_actor_glint"},
        "geometry": {"default": "geometry.humanoid.armor.boots", "redcap": "geometry.tf_slice.redcap.armor.boots"},
        "scripts": {"parent_setup": "variable.boot_layer_visible = 0.0;"},
        "render_controllers": ["controller.render.tf_slice.redcap_boots"],
    }}}


def redcap_armor_controller():
    return {"format_version": "1.8.0", "render_controllers": {
        "controller.render.tf_slice.redcap_boots": {
            "geometry": "query.is_owner_identifier_any('tf_slice:redcap', 'tf_slice:redcap_sapper') ? Geometry.redcap : Geometry.default",
            "materials": [{"*": "variable.is_enchanted ? Material.enchanted : Material.default"}],
            "textures": ["variable.has_trim ? variable.trim_path : Texture.default", "Texture.enchanted"],
        },
    }}


def redcap_attack_animation():
    # FixedHumanoidModel.setupAttackAnimation, armWidth=3 -> shoulder radius 4.
    progress = "math.clamp(variable.attack_time, 0.0, 1.0)"
    yaw = "math.sin(math.sqrt(%s) * 360.0) * 11.4592" % progress
    eased = "1.0 - (1.0 - %s) * (1.0 - %s) * (1.0 - %s) * (1.0 - %s)" % ((progress,) * 4)
    pitch = ("-math.sin((%s) * 180.0) * 68.7549 + math.sin(%s * 180.0)"
             " * (query.target_x_rotation - 40.1070) * 0.75") % (eased, progress)
    x = "4.0 * (1.0 - math.cos(%s))" % yaw
    z = "math.sin(%s) * 4.0" % yaw
    return {"loop": True, "bones": {
        "body": {"rotation": [0, yaw, 0]},
        "rightArm": {
            "position": [x, 0, z],
            "rotation": [pitch, "(%s) * 3.0" % yaw,
                         "-math.sin(%s * 180.0) * 22.9183" % progress],
        },
        "leftArm": {
            "position": ["-(%s)" % x, 0, "-(%s)" % z],
            "rotation": [yaw, yaw, 0],
        },
    }}


def animation_document():
    walk = "math.cos(query.modified_distance_moved * 38.17) * 35.0 * query.modified_move_speed"
    redcap_phase = "variable.redcap_walk_phase"
    redcap_right_arm_x = (
        "-18.0 - math.cos(%s) * 28.6479 * variable.redcap_walk_amount "
        "+ math.sin(query.life_time * 76.7763) * 2.8648"
        % redcap_phase
    )
    redcap_left_arm_x = (
        "math.cos(%s) * 57.2958 * variable.redcap_walk_amount "
        "- math.sin(query.life_time * 76.7763) * 2.8648"
        % redcap_phase
    )
    redcap_arm_bob = (
        "math.cos(query.life_time * 103.1324) * 2.8648 + 2.8648"
    )
    redcap_leg_x = (
        "math.cos(%s) * 80.2141 * variable.redcap_walk_amount"
        % redcap_phase
    )
    beetle_y_a = (
        "-math.cos(query.modified_distance_moved * 76.34) "
        "* 22.9183 * query.modified_move_speed"
    )
    beetle_y_b = (
        "-math.cos(query.modified_distance_moved * 76.34 + 180) "
        "* 22.9183 * query.modified_move_speed"
    )
    beetle_y_c = (
        "-math.cos(query.modified_distance_moved * 76.34 + 270) "
        "* 22.9183 * query.modified_move_speed"
    )
    beetle_z_a = (
        "math.abs(math.sin(query.modified_distance_moved * 38.17)) "
        "* 22.9183 * query.modified_move_speed"
    )
    beetle_z_b = (
        "math.abs(math.sin(query.modified_distance_moved * 38.17 + 180)) "
        "* 22.9183 * query.modified_move_speed"
    )
    beetle_z_c = (
        "math.abs(math.sin(query.modified_distance_moved * 38.17 + 270)) "
        "* 22.9183 * query.modified_move_speed"
    )

    def classic_beetle_leg_animation():
        # setupAnim resets the six legs to these runtime bases before adding
        # the three phase-shifted pairs. These values are additive deltas from
        # the exact PartPose rotations stored in geometry.
        return {
            "leg_1": {
                "rotation": [
                    0,
                    "5 + (%s)" % beetle_y_a,
                    "-3.636364 - (%s)" % beetle_z_a,
                ]
            },
            "leg_2": {
                "rotation": [
                    0,
                    "-5 - (%s)" % beetle_y_a,
                    "3.636364 + (%s)" % beetle_z_a,
                ]
            },
            "leg_3": {
                "rotation": [
                    0,
                    "6.5 + (%s)" % beetle_y_b,
                    "-7.890909 - (%s)" % beetle_z_b,
                ]
            },
            "leg_4": {
                "rotation": [
                    0,
                    "-6.5 - (%s)" % beetle_y_b,
                    "7.890909 + (%s)" % beetle_z_b,
                ]
            },
            "leg_5": {
                "rotation": [
                    0,
                    "-29 + (%s)" % beetle_y_c,
                    "-3.636364 - (%s)" % beetle_z_c,
                ]
            },
            "leg_6": {
                "rotation": [
                    0,
                    "29 - (%s)" % beetle_y_c,
                    "3.636364 + (%s)" % beetle_z_c,
                ]
            },
        }

    def slime_beetle_leg_animation():
        return {
            "back_right_leg": {
                "rotation": [
                    0,
                    "5 + (%s)" % beetle_y_a,
                    "-3.636364 - (%s)" % beetle_z_a,
                ]
            },
            "back_left_leg": {
                "rotation": [
                    0,
                    "-5 - (%s)" % beetle_y_a,
                    "3.636364 + (%s)" % beetle_z_a,
                ]
            },
            "middle_right_leg": {
                "rotation": [
                    0,
                    "6.5 + (%s)" % beetle_y_b,
                    "-7.890909 - (%s)" % beetle_z_b,
                ]
            },
            "middle_left_leg": {
                "rotation": [
                    0,
                    "-6.5 - (%s)" % beetle_y_b,
                    "7.890909 + (%s)" % beetle_z_b,
                ]
            },
            "front_right_leg": {
                "rotation": [
                    0,
                    "-29 + (%s)" % beetle_y_c,
                    "-3.636364 - (%s)" % beetle_z_c,
                ]
            },
            "front_left_leg": {
                "rotation": [
                    0,
                    "29 - (%s)" % beetle_y_c,
                    "3.636364 + (%s)" % beetle_z_c,
                ]
            },
            "tail1": {
                "rotation": [
                    "math.cos(query.life_time * 382.1713) * 8.594367",
                    0,
                    0,
                ]
            },
            "tail2": {
                "rotation": [
                    "math.cos(query.life_time * 509.3595) * 11.459156",
                    0,
                    0,
                ]
            },
            "slime_center": {
                "rotation": [
                    (
                        "math.cos(query.life_time * 636.5477 + 14.323945) "
                        "* 14.323945"
                    ),
                    0,
                    0,
                ]
            },
        }

    fire_beetle_bones = classic_beetle_leg_animation()
    pinch_beetle_bones = classic_beetle_leg_animation()
    pinch_beetle_bones.update(
        {
            "right_jaw_bottom": {
                "rotation": [0, "query.has_rider ? 19 : -16", 0]
            },
            "left_jaw_bottom": {
                "rotation": [0, "query.has_rider ? -11 : 14", 0]
            },
        }
    )
    return {
        "format_version": "1.8.0",
        "animations": {
            "animation.tf_slice.raven.ground": {
                "loop": True,
                "bones": {
                    "right_leg": {"rotation": [walk, 0, 0]},
                    "left_leg": {"rotation": ["-(%s)" % walk, 0, 0]},
                    "right_wing": {"rotation": [0, 0, -8]},
                    "left_wing": {"rotation": [0, 0, 8]},
                },
            },
            "animation.tf_slice.raven.takeoff": {
                "animation_length": 0.35,
                "bones": {
                    "body": {
                        "position": {
                            "0.0": [0, 0, 0],
                            "0.15": [0, 2, 0],
                            "0.35": [0, 1, 0],
                        }
                    },
                    "right_wing": {
                        "rotation": {
                            "0.0": [0, 0, -8],
                            "0.12": [0, 0, -65],
                            "0.24": [0, 0, 45],
                            "0.35": [0, 0, -35],
                        }
                    },
                    "left_wing": {
                        "rotation": {
                            "0.0": [0, 0, 8],
                            "0.12": [0, 0, 65],
                            "0.24": [0, 0, -45],
                            "0.35": [0, 0, 35],
                        }
                    },
                },
                "sound_effects": {"0.0": {"effect": "takeoff"}},
            },
            "animation.tf_slice.raven.fly": {
                "loop": True,
                "bones": {
                    "body": {"rotation": [-12, 0, 0]},
                    "right_wing": {
                        "rotation": [
                            0,
                            0,
                            "-10 - math.sin(query.life_time * 720) * 55",
                        ]
                    },
                    "left_wing": {
                        "rotation": [
                            0,
                            0,
                            "10 + math.sin(query.life_time * 720) * 55",
                        ]
                    },
                    "right_leg": {"position": [0, 2, 0]},
                    "left_leg": {"position": [0, 2, 0]},
                },
            },
            "animation.tf_slice.biped.move": {
                "loop": True,
                "bones": {
                    "rightArm": {
                        "rotation": [
                            "query.is_riding ? -36 - (%s) : -(%s)" % (walk, walk),
                            0,
                            0,
                        ]
                    },
                    "leftArm": {
                        "rotation": [
                            "query.is_riding ? -36 + (%s) : (%s)" % (walk, walk),
                            0,
                            0,
                        ]
                    },
                    "rightLeg": {
                        "rotation": [
                            "query.is_riding ? -81 : (%s)" % walk,
                            "query.is_riding ? 18 : 0",
                            "query.is_riding ? 4.5 : 0",
                        ]
                    },
                    "leftLeg": {
                        "rotation": [
                            "query.is_riding ? -81 : -(%s)" % walk,
                            "query.is_riding ? -18 : 0",
                            "query.is_riding ? -4.5 : 0",
                        ]
                    },
                },
            },
            "animation.tf_slice.redcap.move": {
                "loop": True,
                "bones": {
                    "rightArm": {
                        "rotation": [
                            redcap_right_arm_x,
                            0,
                            redcap_arm_bob,
                        ]
                    },
                    "leftArm": {
                        "rotation": [
                            redcap_left_arm_x,
                            0,
                            "-(%s)" % redcap_arm_bob,
                        ]
                    },
                    "rightLeg": {"rotation": [redcap_leg_x, 0, 0]},
                    "leftLeg": {
                        "rotation": ["-(%s)" % redcap_leg_x, 0, 0]
                    },
                },
            },
            "animation.tf_slice.redcap.attack": redcap_attack_animation(),
            "animation.tf_slice.redcap.equipment": {
                "loop": True,
                "bones": {
                    "rightItem": {"scale": 0.85},
                    "leftItem": {"scale": 0.85},
                },
            },
            "animation.tf_slice.redcap.look": {
                "loop": True,
                "bones": {
                    "head": {
                        "rotation": [
                            "query.target_x_rotation",
                            "query.target_y_rotation",
                            0,
                        ]
                    },
                    "hat": {
                        "rotation": [
                            "query.target_x_rotation",
                            "query.target_y_rotation",
                            0,
                        ]
                    },
                },
            },
            "animation.tf_slice.kobold.move": {
                "loop": True,
                "bones": {
                    "rightArm": {"rotation": ["-27 - (%s) * 0.35" % walk, 0, 0]},
                    "leftArm": {"rotation": ["-27 + (%s) * 0.35" % walk, 0, 0]},
                    "rightLeg": {"rotation": [walk, 0, 0]},
                    "leftLeg": {"rotation": ["-(%s)" % walk, 0, 0]},
                    "jaw": {
                        "rotation": [
                            "12 + math.abs(math.sin(query.life_time * 180)) * (1 - query.is_on_ground) * 18",
                            0,
                            0,
                        ]
                    },
                },
            },
            "animation.tf_slice.wraith.float": {
                "loop": True,
                "bones": {
                    "root": {
                        "position": [0, "math.sin(query.life_time * 90) * 1.5", 0]
                    },
                    "rightArm": {
                        "rotation": [
                            "-75 + math.sin(query.life_time * 120) * 12",
                            0,
                            8,
                        ]
                    },
                    "leftArm": {
                        "rotation": [
                            "-75 - math.sin(query.life_time * 120) * 12",
                            0,
                            -8,
                        ]
                    },
                },
            },
            "animation.tf_slice.wolf.walk": {
                "loop": True,
                "bones": {
                    "leg0": {
                        "rotation": [
                            "math.cos(query.modified_distance_moved * 38.17) * 80.22 * query.modified_move_speed",
                            0,
                            0,
                        ]
                    },
                    "leg1": {
                        "rotation": [
                            "math.cos(query.modified_distance_moved * 38.17 + 180) * 80.22 * query.modified_move_speed",
                            0,
                            0,
                        ]
                    },
                    "leg2": {
                        "rotation": [
                            "math.cos(query.modified_distance_moved * 38.17 + 180) * 80.22 * query.modified_move_speed",
                            0,
                            0,
                        ]
                    },
                    "leg3": {
                        "rotation": [
                            "math.cos(query.modified_distance_moved * 38.17) * 80.22 * query.modified_move_speed",
                            0,
                            0,
                        ]
                    },
                    "tail": {
                        "rotation": [
                            "query.has_target ? 52.2 : 0.0",
                            "query.has_target ? 0.0 : math.cos(query.modified_distance_moved * 38.17) * query.modified_move_speed * 80.22",
                            0,
                        ]
                    },
                },
            },
            "animation.tf_slice.fire_beetle.move": {
                "loop": True,
                "bones": fire_beetle_bones,
            },
            "animation.tf_slice.slime_beetle.move": {
                "loop": True,
                "bones": slime_beetle_leg_animation(),
            },
            "animation.tf_slice.pinch_beetle.move": {
                "loop": True,
                "bones": pinch_beetle_bones,
            },
            "animation.tf_slice.rising_zombie.rise": {
                "loop": "hold_on_last_frame",
                "animation_length": 6.5,
                "bones": {
                    "root": {
                        "position": {
                            "0.0": [0, -32, 0],
                            "4.0": [0, -16, 0],
                            "6.0": [0, 0, 0],
                            "6.5": [0, 0, 0],
                        },
                    },
                    "risePivot": {
                        "rotation": {
                            "0.0": [-90, 0, 0],
                            "4.0": [30, 0, 0],
                            "6.0": [0, 0, 0],
                            "6.5": [0, 0, 0],
                        },
                    },
                },
            },
            "animation.tf_slice.nature_bolt.spin": {
                "loop": True,
                "bones": {
                    "bolt": {
                        "rotation": [
                            "query.life_time * 420",
                            "query.life_time * 560",
                            "query.life_time * 700",
                        ]
                    }
                },
            },
        },
    }


def animation_controller_document():
    return {
        "format_version": "1.10.0",
        "animation_controllers": {
            "controller.animation.tf_slice.raven.flight": {
                "initial_state": "grounded",
                "states": {
                    "grounded": {
                        "animations": ["ground"],
                        "transitions": [{"takeoff": "!query.is_on_ground"}],
                    },
                    "takeoff": {
                        "animations": ["takeoff"],
                        "transitions": [
                            {"grounded": "query.is_on_ground"},
                            {"flying": "query.all_animations_finished"},
                        ],
                    },
                    "flying": {
                        "animations": ["fly"],
                        "transitions": [{"grounded": "query.is_on_ground"}],
                    },
                },
            }
        },
    }


def nearest_player(must_see=True, distance=24):
    return {
        "priority": 2,
        "must_see": must_see,
        "reselect_targets": True,
        "entity_types": [
            {
                "filters": {
                    "test": "is_family",
                    "subject": "other",
                    "value": "player",
                },
                "max_dist": distance,
            }
        ],
    }


def common_components(spec):
    components = {
        "minecraft:type_family": {"family": spec["families"]},
        "minecraft:nameable": {},
        "minecraft:health": {"value": spec["health"], "max": spec["health"]},
        "minecraft:movement": {"value": spec["movement"]},
        "minecraft:collision_box": {
            "width": spec["box"][0],
            "height": spec["box"][1],
        },
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0},
        "minecraft:physics": {},
        "minecraft:pushable": {
            "is_pushable": True,
            "is_pushable_by_piston": True,
        },
        "minecraft:despawn": {"despawn_from_distance": {}},
        "minecraft:loot": {
            "table": "loot_tables/entities/tf_slice/%s.json" % spec["id"]
        },
        "minecraft:ambient_sound_interval": {
            "value": 4.0,
            "range": 8.0,
            "event_name": "ambient",
        },
    }
    if spec["attack"]:
        components["minecraft:attack"] = {"damage": spec["attack"]}
    if spec.get("armor"):
        components["minecraft:armor"] = {"value": spec["armor"]}
    if spec.get("equipment"):
        components["minecraft:equipment"] = {
            "table": "loot_tables/equipment/tf_slice/%s.json"
            % spec["equipment"],
            "slot_drop_chance": [
                {"slot": "slot.weapon.mainhand", "drop_chance": 0.2},
                {"slot": "slot.armor.feet", "drop_chance": 0.2},
            ],
        }
    return components


def walking_components():
    return {
        "minecraft:movement.basic": {},
        "minecraft:navigation.walk": {
            "can_path_over_water": True,
            "avoid_water": True,
            "avoid_damage_blocks": True,
        },
        "minecraft:jump.static": {},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.random_stroll": {
            "priority": 7,
            "speed_multiplier": 0.9,
        },
        "minecraft:behavior.look_at_player": {
            "priority": 8,
            "look_distance": 8,
            "probability": 0.04,
        },
        "minecraft:behavior.random_look_around": {"priority": 9},
    }


def melee_components(must_see=True, leap=False):
    value = {
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": nearest_player(
            must_see=must_see
        ),
        "minecraft:behavior.melee_attack": {
            "priority": 4,
            "speed_multiplier": 1.15,
            "track_target": True,
        },
    }
    if leap:
        value["minecraft:behavior.leap_at_target"] = {
            "priority": 3,
            "yd": 0.3,
        }
    return value


def server_entity(mob_id, source_spec):
    spec = dict(source_spec)
    spec["id"] = mob_id
    components = common_components(spec)
    groups = {}
    events = {}

    if mob_id == "raven":
        components.update(
            {
                "minecraft:movement.fly": {},
                "minecraft:navigation.fly": {
                    "can_path_from_air": True,
                    "can_path_over_water": True,
                    "can_pass_doors": True,
                },
                "minecraft:can_fly": {},
                "minecraft:behavior.float": {"priority": 0},
                "minecraft:behavior.panic": {
                    "priority": 1,
                    "speed_multiplier": 1.5,
                },
                "minecraft:behavior.tempt": {
                    "priority": 2,
                    "speed_multiplier": 1.0,
                    "items": [
                        "minecraft:wheat_seeds",
                        "minecraft:pumpkin_seeds",
                        "minecraft:melon_seeds",
                        "minecraft:beetroot_seeds",
                    ],
                },
                "minecraft:behavior.random_stroll": {
                    "priority": 5,
                    "speed_multiplier": 1.0,
                },
                "minecraft:behavior.look_at_player": {
                    "priority": 6,
                    "look_distance": 6,
                    "probability": 0.05,
                },
                "minecraft:behavior.random_look_around": {"priority": 7},
            }
        )
    elif mob_id == "skeleton_druid":
        components.update(walking_components())
        components.update(
            {
                "minecraft:burns_in_daylight": {},
                "minecraft:shooter": {"def": "tf_slice:nature_bolt"},
                "minecraft:behavior.hurt_by_target": {"priority": 1},
                "minecraft:behavior.nearest_attackable_target": nearest_player(),
                "minecraft:behavior.ranged_attack": {
                    "priority": 3,
                    "attack_interval_min": 3.0,
                    "attack_interval_max": 3.0,
                    "attack_radius": 5.0,
                    "speed_multiplier": 1.25,
                },
            }
        )
        groups = {
            "tf_slice:baby": {
                "minecraft:is_baby": {},
                "minecraft:scale": {"value": 0.5},
                "minecraft:movement": {"value": 0.375},
                "minecraft:equipment": {
                    "table": (
                        "loot_tables/equipment/tf_slice/"
                        "skeleton_druid_baby.json"
                    )
                },
                "minecraft:shooter": {"def": "minecraft:arrow"},
            }
        }
        events = {
            "tf_slice:make_baby": {
                "add": {"component_groups": ["tf_slice:baby"]}
            }
        }
    elif mob_id in ("swarm_spider", "hedge_spider"):
        components.update(walking_components())
        components.update(melee_components(must_see=True, leap=True))
        components["minecraft:behavior.nearest_attackable_target"] = (
            nearest_player(must_see=True, distance=16)
        )
        components["minecraft:behavior.melee_attack"][
            "speed_multiplier"
        ] = 1.0
        components["minecraft:behavior.leap_at_target"]["yd"] = 0.4
        components["minecraft:behavior.random_stroll"][
            "speed_multiplier"
        ] = 0.8
        components["minecraft:can_climb"] = {}
        components["minecraft:rideable"] = {
            "seat_count": 1,
            "family_types": ["skeleton"],
            "pull_in_entities": False,
            "seats": {
                "position": [0, 0.45, 0],
                "min_rider_count": 0,
                "max_rider_count": 1,
            },
        }
        components["minecraft:ambient_sound_interval"]["value"] = (
            6.0 if mob_id == "swarm_spider" else 8.0
        )
    elif mob_id == "hostile_wolf":
        components.update(walking_components())
        components.update(melee_components(must_see=True, leap=True))
        components["minecraft:behavior.nearest_attackable_target"][
            "within_radius"
        ] = 24
    elif mob_id == "wraith":
        components.update(
            {
                "minecraft:physics": {
                    "has_gravity": False,
                    "has_collision": False,
                },
                "minecraft:movement.fly": {},
                "minecraft:navigation.fly": {
                    "can_path_from_air": True,
                    "can_path_over_water": True,
                    "can_pass_doors": True,
                    "can_open_doors": True,
                },
                "minecraft:can_fly": {},
                "minecraft:behavior.float": {"priority": 0},
                "minecraft:behavior.hurt_by_target": {"priority": 1},
                "minecraft:behavior.nearest_attackable_target": nearest_player(
                    must_see=False, distance=32
                ),
                "minecraft:behavior.melee_attack": {
                    "priority": 3,
                    "speed_multiplier": 0.5,
                    "track_target": True,
                },
                "minecraft:behavior.random_stroll": {
                    "priority": 6,
                    "speed_multiplier": 0.5,
                    "xz_dist": 16,
                    "y_dist": 16,
                },
            }
        )
        components["minecraft:pushable"] = {
            "is_pushable": False,
            "is_pushable_by_piston": False,
        }
    elif mob_id == "rising_zombie":
        # RisingZombie.doHurtTarget() always returns false and its Java tick
        # zeros velocity until replacement, so it must not inherit a usable
        # attack or movement component from the generic monster profile.
        components.pop("minecraft:attack", None)
        components["minecraft:physics"] = {
            "has_gravity": False,
            "has_collision": True,
        }
        groups = {
            "tf_slice:rising": {
                "minecraft:movement": {"value": 0.0},
                "minecraft:knockback_resistance": {"value": 1.0},
                "minecraft:pushable": {
                    "is_pushable": False,
                    "is_pushable_by_piston": False,
                },
                "minecraft:timer": {
                    "looping": False,
                    "time": 6.5,
                    "time_down_event": {
                        "event": "tf_slice:finish_rising",
                        "target": "self",
                    },
                }
            },
            "tf_slice:transform": {
                "minecraft:transformation": {
                    "into": "minecraft:zombie",
                    "keep_level": True,
                    "drop_equipment": False,
                    "drop_inventory": False,
                    "preserve_equipment": True,
                }
            },
        }
        events = {
            "minecraft:entity_spawned": {
                "add": {"component_groups": ["tf_slice:rising"]}
            },
            "tf_slice:finish_rising": {
                "remove": {"component_groups": ["tf_slice:rising"]},
                "add": {"component_groups": ["tf_slice:transform"]},
            },
        }
    elif mob_id in ("slime_beetle", "fire_beetle", "pinch_beetle"):
        components.update(
            {
                "minecraft:movement.basic": {},
                "minecraft:navigation.walk": {
                    "can_path_over_water": True,
                    "avoid_water": True,
                    "avoid_damage_blocks": True,
                },
                "minecraft:jump.static": {},
                "minecraft:behavior.float": {"priority": 0},
                "minecraft:behavior.hurt_by_target": {"priority": 1},
                "minecraft:behavior.nearest_attackable_target": (
                    nearest_player(must_see=True)
                ),
                "minecraft:behavior.random_stroll": {
                    "priority": 6,
                    "speed_multiplier": 1.0,
                },
            }
        )
        if mob_id == "fire_beetle":
            # The Java goal is a 30-tick stateful ray attack, not a generic
            # Bedrock projectile goal. serverSystem owns its chance, warmup,
            # frozen aim and continuous damage; this group freezes locomotion.
            components.update(
                {
                    "minecraft:behavior.melee_attack": {
                        "priority": 3,
                        "speed_multiplier": 1.0,
                        "track_target": True,
                    },
                }
            )
            groups["tf_slice:breathing"] = {
                "minecraft:movement": {"value": 0.0},
                "minecraft:knockback_resistance": {"value": 1.0},
            }
            events.update(
                {
                    "tf_slice:start_breathing": {
                        "add": {"component_groups": ["tf_slice:breathing"]}
                    },
                    "tf_slice:stop_breathing": {
                        "remove": {"component_groups": ["tf_slice:breathing"]}
                    },
                }
            )
        elif mob_id == "slime_beetle":
            # AvoidEntityGoal(Player, 3, 1.25, 2.0) precedes the
            # 30-tick, ten-block ranged attack.
            components.update(
                {
                    "minecraft:behavior.avoid_mob_type": {
                        "priority": 2,
                        "entity_types": [
                            {
                                "filters": {
                                    "test": "is_family",
                                    "subject": "other",
                                    "value": "player",
                                },
                                "max_dist": 3,
                                "walk_speed_multiplier": 1.25,
                                "sprint_speed_multiplier": 2.0,
                            }
                        ],
                    },
                    "minecraft:shooter": {"def": "tf_slice:slime_blob"},
                    "minecraft:behavior.ranged_attack": {
                        "priority": 3,
                        "attack_interval_min": 1.5,
                        "attack_interval_max": 1.5,
                        "attack_radius": 10,
                        "speed_multiplier": 1.0,
                    },
                    "minecraft:behavior.look_at_player": {
                        "priority": 7,
                        "look_distance": 8,
                    },
                    "minecraft:behavior.random_look_around": {
                        "priority": 8
                    },
                }
            )
        else:
            components.update(
                {
                    "minecraft:behavior.melee_attack": {
                        "priority": 4,
                        "speed_multiplier": 1.0,
                        "track_target": True,
                    },
                    "minecraft:behavior.look_at_player": {
                        "priority": 7,
                        "look_distance": 8,
                    },
                    "minecraft:behavior.random_look_around": {
                        "priority": 8
                    },
                }
            )
            # ChargeAttackGoal has a 15..44 tick windup and converts the hit
            # target into a passenger. Those semantics are server scripted.
            components["minecraft:rideable"] = {
                "seat_count": 1,
                "family_types": ["player", "mob"],
                "pull_in_entities": False,
                "seats": {
                    "position": [0, 0.75, 0.75],
                    "min_rider_count": 0,
                    "max_rider_count": 1,
                },
            }
            groups["tf_slice:carrying"] = {
                "minecraft:collision_box": {
                    "width": 2.25,
                    "height": 1.25,
                },
                "minecraft:knockback_resistance": {"value": 1.0},
            }
            events.update(
                {
                    "tf_slice:start_carrying": {
                        "add": {"component_groups": ["tf_slice:carrying"]}
                    },
                    "tf_slice:stop_carrying": {
                        "remove": {"component_groups": ["tf_slice:carrying"]}
                    },
                }
            )
    elif mob_id in ("redcap", "redcap_sapper"):
        components.update(walking_components())
        components.update(melee_components(must_see=True))
        components["minecraft:behavior.look_at_target"] = {
            # Melee (5) owns LOOK as well as MOVE. A priority-2 LOOK goal
            # preempts the entire melee goal, so an untouched mob just stares.
            "priority": 6, "probability": 1.0, "look_distance": 8,
            "control_flags": ["look"],
        }
        components["minecraft:behavior.melee_attack"] = {
            "priority": 5,
            "speed_multiplier": 1.0,
            "track_target": True,
        }
        components["minecraft:behavior.random_stroll"] = {
            "priority": 6,
            "speed_multiplier": 1.0,
        }
        components["minecraft:behavior.look_at_player"] = {
            "priority": 7,
            "look_distance": 8,
        }
        components["minecraft:behavior.random_look_around"] = {
            "priority": 7
        }
        components["minecraft:behavior.avoid_mob_type"] = {
            "priority": 1,
            "entity_types": [
                {
                    "filters": {
                        "test": "is_family",
                        "subject": "other",
                        "value": "tnt",
                    },
                    "max_dist": 2,
                    "walk_speed_multiplier": 1.0,
                    "sprint_speed_multiplier": 2.0,
                }
            ],
        }
        # Scripted shy/light paths must not compete with native chase/stroll.
        # Native avoidance must also yield MOVE to the scripted TNT escape.
        normal = {}
        for name in ("melee_attack", "random_stroll", "look_at_player", "random_look_around", "avoid_mob_type"):
            key = "minecraft:behavior." + name
            normal[key] = components.pop(key)
        groups["tf_slice:redcap_normal"] = normal
        events.update({
            "minecraft:entity_spawned": {"add": {"component_groups": ["tf_slice:redcap_normal"]}},
            "tf_slice:redcap_normal": {"add": {"component_groups": ["tf_slice:redcap_normal"]}},
            "tf_slice:redcap_special": {"remove": {"component_groups": ["tf_slice:redcap_normal"]}},
        })
    elif mob_id == "kobold":
        components.update(walking_components())
        components.update(melee_components(must_see=True, leap=True))
        components.update(
            {
                "minecraft:shareables": {
                    "items": [
                        {
                            "item": "minecraft:bread",
                            "want_amount": 1,
                            "surplus_amount": 0,
                            "priority": 0,
                        }
                    ]
                },
                "minecraft:behavior.pickup_items": {
                    "priority": 2,
                    "max_dist": 8,
                    "goal_radius": 1,
                    "speed_multiplier": 1.2,
                    "pickup_based_on_chance": False,
                    "can_pickup_any_item": False,
                },
            }
        )
        groups = {
            "tf_slice:panicked": {
                "minecraft:movement": {"value": 0.56},
                "minecraft:behavior.random_stroll": {
                    "priority": 0,
                    "speed_multiplier": 2.0,
                    "xz_dist": 10,
                    "y_dist": 3,
                },
                "minecraft:timer": {
                    "looping": False,
                    "time": 2.0,
                    "time_down_event": {
                        "event": "tf_slice:calm_down",
                        "target": "self",
                    },
                },
            }
        }
        events = {
            "tf_slice:panic": {
                "add": {"component_groups": ["tf_slice:panicked"]}
            },
            "tf_slice:calm_down": {
                "remove": {"component_groups": ["tf_slice:panicked"]}
            },
        }

    entity = {
        "description": {
            "identifier": "tf_slice:%s" % mob_id,
            "is_spawnable": True,
            "is_summonable": True,
            "is_experimental": False,
        },
        "components": components,
    }
    if groups:
        entity["component_groups"] = groups
    if events:
        entity["events"] = events
    return {"format_version": "1.20.60", "minecraft:entity": entity}


def nature_bolt_server_entity():
    return {
        "format_version": "1.20.60",
        "minecraft:entity": {
            "description": {
                "identifier": "tf_slice:nature_bolt",
                "is_spawnable": False,
                "is_summonable": True,
                "is_experimental": False,
            },
            "components": {
                "minecraft:type_family": {
                    "family": ["nature_bolt", "projectile"]
                },
                "minecraft:collision_box": {"width": 0.25, "height": 0.25},
                "minecraft:physics": {"has_gravity": False},
                "minecraft:projectile": {
                    "power": 0.6,
                    "gravity": 0.003,
                    "uncertainty_base": 6.0,
                    "anchor": 1,
                    "offset": [0, -0.1, 0],
                    "on_hit": {
                        "impact_damage": {
                            "damage": 2,
                            "knockback": False,
                            "semi_random_diff_damage": False,
                        },
                        "remove_on_hit": {},
                    },
                },
            },
        },
    }


def fire_breath_server_entity():
    return {
        "format_version": "1.20.60",
        "minecraft:entity": {
            "description": {
                "identifier": "tf_slice:fire_breath",
                "is_spawnable": False,
                "is_summonable": True,
                "is_experimental": False,
            },
            "components": {
                "minecraft:type_family": {
                    "family": ["fire_breath", "projectile"]
                },
                "minecraft:collision_box": {"width": 0.1, "height": 0.1},
                "minecraft:physics": {"has_gravity": False},
                "minecraft:projectile": {
                    "power": 0.15,
                    "gravity": 0,
                    "uncertainty_base": 5.0,
                    "anchor": 1,
                    "offset": [0, 0.25, 0],
                    "on_fire_time": 10,
                    "on_hit": {
                        "impact_damage": {
                            "damage": 2,
                            "knockback": False,
                            "semi_random_diff_damage": False,
                        },
                        "remove_on_hit": {},
                    },
                },
            },
        },
    }


def slime_blob_server_entity():
    return {
        "format_version": "1.20.60",
        "minecraft:entity": {
            "description": {
                "identifier": "tf_slice:slime_blob",
                "is_spawnable": False,
                "is_summonable": True,
                "is_experimental": False,
            },
            "components": {
                "minecraft:type_family": {
                    "family": ["slime_blob", "projectile"]
                },
                "minecraft:collision_box": {"width": 0.25, "height": 0.25},
                "minecraft:physics": {"has_gravity": True},
                "minecraft:projectile": {
                    "power": 0.6,
                    "gravity": 0.006,
                    "uncertainty_base": 6.0,
                    "anchor": 1,
                    "offset": [0, -0.1, 0],
                    "on_hit": {
                        "impact_damage": {
                            "damage": 4,
                            "knockback": False,
                            "semi_random_diff_damage": False,
                        },
                        "remove_on_hit": {},
                    },
                },
            },
        },
    }


def client_entity(mob_id, spec):
    profile = spec["profile"]
    description = {
        "identifier": "tf_slice:%s" % mob_id,
        "materials": {
            "default": (
                "entity_alphablend"
                if profile == "wraith" or mob_id == "slime_beetle"
                else "entity_alphatest"
            )
        },
        "textures": {"default": spec["texture"]},
        "geometry": {"default": spec["geometry"]},
        "render_controllers": [
            (
                "controller.render.tf_slice.wraith"
                if profile == "wraith"
                else "controller.render.default"
            )
        ],
        "spawn_egg": {
            "base_color": spec["egg"][0],
            "overlay_color": spec["egg"][1],
        },
    }
    if profile == "spider":
        description["animations"] = {
            "default_leg_pose": "animation.spider.default_leg_pose",
            "look_at_target": "animation.spider.look_at_target",
            "walk": "animation.spider.walk",
        }
        description["scripts"] = {
            "animate": [
                "default_leg_pose",
                {"walk": "query.modified_move_speed"},
                "look_at_target",
            ]
        }
    elif profile == "raven":
        description["animations"] = {
            "ground": "animation.tf_slice.raven.ground",
            "takeoff": "animation.tf_slice.raven.takeoff",
            "fly": "animation.tf_slice.raven.fly",
            "flight_controller": "controller.animation.tf_slice.raven.flight",
            "look": "animation.common.look_at_target",
        }
        description["scripts"] = {"animate": ["flight_controller", "look"]}
        description["sound_effects"] = {
            "takeoff": "tf_slice.raven.takeoff"
        }
    elif profile == "rising":
        # The Java placeholder has no goals and does not track targets while
        # rising.  Playing common.look_at_target here made its head appear to
        # spin even when server motion was zero.
        description["animations"] = {
            "rise": "animation.tf_slice.rising_zombie.rise",
        }
        description["scripts"] = {"animate": ["rise"]}
    else:
        animation = {
            "biped": "animation.tf_slice.biped.move",
            "kobold": "animation.tf_slice.kobold.move",
            "wraith": "animation.tf_slice.wraith.float",
            "wolf": "animation.tf_slice.wolf.walk",
            "beetle": "animation.tf_slice.%s.move" % mob_id,
        }[profile]
        if mob_id in ("redcap", "redcap_sapper"):
            animation = "animation.tf_slice.redcap.move"
        description["animations"] = {
            "move": animation,
            "look": (
                "animation.tf_slice.redcap.look"
                if mob_id in ("redcap", "redcap_sapper")
                else "animation.common.look_at_target"
            ),
        }
        description["scripts"] = {"animate": ["move", "look"]}
        if mob_id in ("redcap", "redcap_sapper"):
            description["animations"]["attack"] = "animation.tf_slice.redcap.attack"
            description["scripts"]["animate"].append("attack")
            description["animations"]["equipment"] = "animation.tf_slice.redcap.equipment"
            description["scripts"]["animate"].append("equipment")
            description["scripts"]["initialize"] = [
                "variable.redcap_walk_amount = 0.0;",
                "variable.redcap_walk_phase = 0.0;",
            ]
            # Ground speed has explicit metres/second units. Java's limb
            # amount targets min(1, horizontal displacement per tick * 4),
            # smoothed by .4 at 20 Hz; convert that to the render frame rate.
            description["scripts"]["pre_animation"] = [" ".join([
                "temp.redcap_dt = math.clamp(query.delta_time, 0.0, 0.1);",
                "temp.redcap_walk_target = math.clamp(query.ground_speed * 0.2, 0.0, 1.0);",
                "temp.redcap_walk_previous = variable.redcap_walk_amount;",
                "variable.redcap_walk_amount = variable.redcap_walk_amount + (temp.redcap_walk_target - variable.redcap_walk_amount) * (1.0 - math.pow(0.6, temp.redcap_dt * 20.0));",
                "variable.redcap_walk_phase = variable.redcap_walk_phase + (temp.redcap_walk_previous + variable.redcap_walk_amount) * 0.5 * temp.redcap_dt * 763.4263;",
                "variable.redcap_walk_phase = variable.redcap_walk_phase - math.floor(variable.redcap_walk_phase / 360.0) * 360.0;",
            ])]
    if spec.get("scale") is not None:
        description.setdefault("scripts", {})["scale"] = str(spec["scale"])
    if spec.get("equipment") or mob_id == "kobold":
        description["enable_attachables"] = True
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {"description": description},
    }


def render_controller_document():
    return {
        "format_version": "1.8.0",
        "render_controllers": {
            "controller.render.tf_slice.wraith": {
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.default"],
                # The Java renderer draws the wraith at 60% opacity.
                "color": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.6},
            }
        },
    }


def nature_bolt_client_entity():
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": "tf_slice:nature_bolt",
                "materials": {"default": "entity_emissive_alpha"},
                "textures": {"default": "textures/blocks/root"},
                "geometry": {"default": "geometry.tf_slice.nature_bolt"},
                "animations": {
                    "spin": "animation.tf_slice.nature_bolt.spin"
                },
                "scripts": {"animate": ["spin"]},
                "render_controllers": ["controller.render.default"],
            }
        },
    }


def beetle_projectile_client_entity(
    identifier,
    geometry_identifier,
    texture,
    material,
):
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": identifier,
                "materials": {"default": material},
                "textures": {"default": texture},
                "geometry": {"default": geometry_identifier},
                "animations": {
                    "spin": "animation.tf_slice.nature_bolt.spin"
                },
                "scripts": {"animate": ["spin"]},
                "render_controllers": ["controller.render.default"],
            }
        },
    }


def count_function(minimum, maximum, looting=False):
    functions = [
        {
            "function": "set_count",
            "count": {"min": minimum, "max": maximum},
        }
    ]
    if looting:
        functions.append(
            {
                "function": "looting_enchant",
                "count": {"min": 0, "max": 1},
            }
        )
    return functions


def loot_pool(item_id, minimum, maximum, looting=False, conditions=None):
    entry = {
        "type": "item",
        "name": item_id,
        "weight": 1,
        "functions": count_function(minimum, maximum, looting),
    }
    if conditions:
        entry["conditions"] = conditions
    return {"rolls": 1, "entries": [entry]}


def entity_loot(name):
    if name == "raven":
        pools = [loot_pool("tf_slice:raven_feather", 0, 2, True)]
    elif name == "skeleton_druid":
        pools = [
            loot_pool("minecraft:bone", 0, 2, True),
            loot_pool("tf_slice:torchberries", 0, 2, True),
        ]
    elif name in ("swarm_spider", "hedge_spider"):
        pools = [
            loot_pool("minecraft:string", 0, 2, True),
            loot_pool(
                "minecraft:spider_eye",
                0,
                1,
                True,
                [{"condition": "killed_by_player"}],
            ),
        ]
    elif name == "hostile_wolf":
        pools = []
    elif name == "wraith":
        pools = [loot_pool("minecraft:glowstone_dust", 0, 2, True)]
    elif name == "rising_zombie":
        pools = [loot_pool("minecraft:rotten_flesh", 0, 2, True)]
    elif name in ("redcap", "redcap_sapper"):
        pools = [loot_pool("minecraft:coal", 0, 1, True)]
    elif name == "kobold":
        pools = [
            loot_pool("minecraft:wheat", 0, 2, True),
            loot_pool(
                "minecraft:gold_nugget",
                0,
                1,
                True,
                [{"condition": "killed_by_player"}],
            ),
        ]
    elif name == "slime_beetle":
        pools = [loot_pool("minecraft:slime_ball", 0, 2, True)]
    elif name == "fire_beetle":
        pools = [loot_pool("minecraft:blaze_powder", 0, 1, True)]
    elif name == "pinch_beetle":
        pools = []
    else:
        raise ValueError(name)
    return {"pools": pools}


def equipment_table(name):
    if name == "skeleton_druid":
        items = [("minecraft:golden_hoe", 1)]
    elif name == "skeleton_druid_baby":
        items = [("minecraft:bow", 1)]
    elif name == "redcap":
        items = [
            ("minecraft:iron_pickaxe", 1),
            ("minecraft:iron_boots", 1),
        ]
    elif name == "redcap_sapper":
        items = [
            ("tf_slice:ironwood_pickaxe", 1),
            ("tf_slice:ironwood_boots", 1),
        ]
    else:
        raise ValueError(name)
    return {
        "pools": [
            {
                "rolls": 1,
                "entries": [
                    {"type": "item", "name": item_id, "weight": weight}
                ],
            }
            for item_id, weight in items
        ]
    }


def chest_loot_table(entries):
    return {
        "pools": [
            {
                "rolls": {"min": 2, "max": 4},
                "entries": [
                    {
                        "type": "item",
                        "name": item,
                        "weight": weight,
                        "functions": [
                            {
                                "function": "set_count",
                                "count": {
                                    "min": 1,
                                    "max": max(1, weight // 2),
                                },
                            }
                        ],
                    }
                    for item, weight in entries
                ],
            }
        ]
    }


def item_document(name):
    components = {
        "minecraft:display_name": {
            "value": "item.tf_slice:%s.name" % name
        },
        "minecraft:icon": {
            "textures": {"default": "tf_slice:%s" % name}
        },
        "minecraft:max_stack_size": (
            1 if name in ("ironwood_pickaxe", "ironwood_boots") else 64
        ),
    }
    if name == "ironwood_pickaxe":
        components.update(
            {
                "minecraft:hand_equipped": True,
                "minecraft:durability": {"max_durability": 512},
                "minecraft:damage": 4,
            }
        )
    elif name == "ironwood_boots":
        components.update(
            {
                "minecraft:durability": {"max_durability": 256},
                "minecraft:wearable": {
                    "slot": "slot.armor.feet",
                    "protection": 2,
                },
            }
        )
    elif name == "torchberries":
        components.update(
            {
                "minecraft:tags": {"tags": ["minecraft:is_food"]},
                "minecraft:use_animation": "eat",
                "minecraft:use_modifiers": {
                    "use_duration": 1.6,
                    "movement_modifier": 0.35,
                },
                "minecraft:food": {
                    "nutrition": 2,
                    "saturation_modifier": 0.1,
                },
            }
        )
    return {
        "format_version": "1.21.60",
        "minecraft:item": {
            "description": {
                "identifier": "tf_slice:%s" % name,
                "menu_category": {"category": "nature"},
            },
            "components": components,
        },
    }


def sound_definition(category, sounds):
    return {
        "category": category,
        "sounds": ["sounds/mob/%s" % sound for sound in sounds],
    }


def weighted_sound_definition(category, sounds):
    return {
        "category": category,
        "sounds": [
            {"name": "sounds/mob/%s" % sound, "weight": weight}
            for sound, weight in sounds
        ],
    }


def ruin_sound_definitions():
    redcap_ambient = weighted_sound_definition(
        "hostile",
        [("redcap/redcap%d" % i, 100) for i in range(1, 7)]
        + [("redcap/redcap7", 1)],
    )
    return {
        "tf_slice.raven.ambient": sound_definition(
            "neutral", ["raven/caw1", "raven/caw2"]
        ),
        "tf_slice.raven.hurt": sound_definition(
            "neutral", ["raven/squawk1", "raven/squawk2"]
        ),
        "tf_slice.raven.death": sound_definition(
            "neutral", ["raven/squawk1", "raven/squawk2"]
        ),
        "tf_slice.raven.takeoff": {
            "category": "neutral",
            "sounds": ["sounds/mob/bat/takeoff"],
        },
        "tf_slice.redcap.ambient": redcap_ambient,
        "tf_slice.redcap.hurt": sound_definition(
            "hostile", ["redcap/hurt%d" % i for i in range(1, 5)]
        ),
        "tf_slice.redcap.death": sound_definition(
            "hostile", ["redcap/die%d" % i for i in range(1, 4)]
        ),
        "tf_slice.redcap_sapper.ambient": redcap_ambient,
        "tf_slice.redcap_sapper.hurt": sound_definition(
            "hostile", ["redcap/hurt%d" % i for i in range(1, 5)]
        ),
        "tf_slice.redcap_sapper.death": sound_definition(
            "hostile", ["redcap/die%d" % i for i in range(1, 4)]
        ),
        "tf_slice.kobold.ambient": sound_definition(
            "hostile", ["kobold/ambient%d" % i for i in range(1, 7)]
        ),
        "tf_slice.kobold.hurt": sound_definition(
            "hostile", ["kobold/hurt%d" % i for i in range(1, 4)]
        ),
        "tf_slice.kobold.death": sound_definition(
            "hostile", ["kobold/death%d" % i for i in range(1, 4)]
        ),
        "tf_slice.kobold.munch": {
            "category": "hostile",
            "sounds": ["sounds/random/eat1", "sounds/random/eat2"],
        },
        "tf_slice.hostile_wolf.ambient": sound_definition(
            "hostile", ["hostile_wolf/idle%d" % i for i in range(1, 4)]
        ),
        "tf_slice.hostile_wolf.hurt": sound_definition(
            "hostile", ["hostile_wolf/hurt1", "hostile_wolf/hurt2"]
        ),
        "tf_slice.hostile_wolf.death": {
            "category": "hostile",
            "sounds": ["sounds/mob/wolf/death"],
        },
        "tf_slice.hostile_wolf.target": sound_definition(
            "hostile", ["hostile_wolf/target"]
        ),
        "tf_slice.wraith.ambient": sound_definition(
            "hostile", ["wraith/wraith%d" % i for i in range(1, 5)]
        ),
        "tf_slice.wraith.hurt": sound_definition(
            "hostile", ["wraith/wraith%d" % i for i in range(1, 5)]
        ),
        "tf_slice.wraith.death": sound_definition(
            "hostile", ["wraith/wraith%d" % i for i in range(1, 5)]
        ),
    }


def ruin_entity_sounds():
    custom = {
        "raven": {
            "ambient": "tf_slice.raven.ambient",
            "hurt": "tf_slice.raven.hurt",
            "death": "tf_slice.raven.death",
            "step": "",
        },
        "skeleton_druid": {
            "ambient": "mob.stray.ambient",
            "hurt": "mob.stray.hurt",
            "death": "mob.stray.death",
            "shoot": "mob.ghast.fireball",
            "step": "mob.skeleton.step",
        },
        "swarm_spider": {
            "ambient": "mob.spider.say",
            "hurt": "mob.spider.say",
            "death": "mob.spider.death",
            "step": "mob.spider.step",
        },
        "hedge_spider": {
            "ambient": "mob.spider.say",
            "hurt": "mob.spider.say",
            "death": "mob.spider.death",
            "step": "mob.spider.step",
        },
        "hostile_wolf": {
            "ambient": "tf_slice.hostile_wolf.ambient",
            "hurt": "tf_slice.hostile_wolf.hurt",
            "death": "tf_slice.hostile_wolf.death",
            "step": "mob.wolf.step",
        },
        "wraith": {
            "ambient": "tf_slice.wraith.ambient",
            "hurt": "tf_slice.wraith.hurt",
            "death": "tf_slice.wraith.death",
            "step": "",
        },
        "rising_zombie": {
            "ambient": "mob.zombie.say",
            "hurt": "mob.zombie.hurt",
            "death": "mob.zombie.death",
            "step": "mob.zombie.step",
        },
        "redcap": {
            "ambient": "tf_slice.redcap.ambient",
            "hurt": "tf_slice.redcap.hurt",
            "death": "tf_slice.redcap.death",
            "step": "mob.zombie.step",
        },
        "redcap_sapper": {
            "ambient": "tf_slice.redcap_sapper.ambient",
            "hurt": "tf_slice.redcap_sapper.hurt",
            "death": "tf_slice.redcap_sapper.death",
            "step": "mob.zombie.step",
        },
        "kobold": {
            "ambient": "tf_slice.kobold.ambient",
            "hurt": "tf_slice.kobold.hurt",
            "death": "tf_slice.kobold.death",
            "step": "mob.zombie.step",
        },
        "slime_beetle": {
            "ambient": "mob.silverfish.say",
            "hurt": "mob.silverfish.hit",
            "death": "mob.silverfish.kill",
            "step": "mob.silverfish.step",
        },
        "fire_beetle": {
            "ambient": "mob.silverfish.say",
            "hurt": "mob.silverfish.hit",
            "death": "mob.silverfish.kill",
            "step": "mob.silverfish.step",
        },
        "pinch_beetle": {
            "ambient": "mob.silverfish.say",
            "hurt": "mob.silverfish.hit",
            "death": "mob.silverfish.kill",
            "step": "mob.silverfish.step",
        },
    }
    return {
        "tf_slice:%s" % name: {
            "volume": 1.0,
            "pitch": [1.3, 1.7] if name == "swarm_spider" else [0.95, 1.05],
            "events": events,
        }
        for name, events in custom.items()
    }


def merge_json_mapping(path, key_path, values):
    document = load_json(path) if path.exists() else {}
    target = document
    for key in key_path:
        target = target.setdefault(key, {})
    target.update(values)
    write_json(path, document)


def add_localization(path, values):
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    replacements = dict(values)
    output = []
    written = set()
    for line in existing.splitlines():
        key = line.split("=", 1)[0] if "=" in line else None
        if key in replacements:
            if key not in written:
                output.append("%s=%s" % (key, replacements[key]))
                written.add(key)
        else:
            output.append(line)
    for key, value in values:
        if key not in written:
            output.append("%s=%s" % (key, value))
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def add_creative_catalog_items(path, values):
    document = load_json(path)
    categories = document["minecraft:crafting_items_catalog"]["categories"]
    twilight_group = None
    for category in categories:
        for group in category.get("groups", []):
            identifier = group.get("group_identifier", {})
            if identifier.get("name") == "tf_slice:itemGroup.name.twilight_forest":
                twilight_group = group
                break
        if twilight_group is not None:
            break
    if twilight_group is None:
        raise ValueError("Twilight Forest creative group is missing")
    items = twilight_group.setdefault("items", [])
    ordered_values = list(values)
    for value_index, value in enumerate(ordered_values):
        if value in items:
            continue

        insertion = None
        for next_value in ordered_values[value_index + 1 :]:
            if next_value in items:
                insertion = items.index(next_value)
                break
        if insertion is None:
            for previous_value in reversed(ordered_values[:value_index]):
                if previous_value in items:
                    insertion = items.index(previous_value) + 1
                    break
        if insertion is None:
            try:
                insertion = items.index("tf_slice:deer_spawn_egg") + 1
            except ValueError:
                insertion = len(items)
        items.insert(insertion, value)
    write_json(path, document)


def copy_asset(source, target):
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def require_cleared_sound_bank(target_name):
    target_dir = RP / "sounds" / "mob" / target_name
    if not target_dir.is_dir() or not any(target_dir.glob("*.ogg")):
        raise FileNotFoundError(
            "generate the cleared %s sound bank before building dependencies"
            % target_name
        )


def build():
    build_courtyard_blocks()
    for mob_id, spec in MOBS.items():
        write_json(
            BP / "entities" / ("%s.entity.json" % mob_id),
            server_entity(mob_id, spec),
        )
        write_json(
            RP / "entity" / ("%s.entity.json" % mob_id),
            client_entity(mob_id, spec),
        )
        if spec.get("texture_source"):
            copy_asset(
                UPSTREAM_MODEL_TEXTURES / spec["texture_source"],
                RP / "textures" / "entity" / "tf_slice" / ("%s.png" % mob_id),
            )
        write_json(
            BP / "loot_tables" / "entities" / "tf_slice" / ("%s.json" % mob_id),
            entity_loot(mob_id),
        )

    write_json(BP / "entities" / "nature_bolt.entity.json", nature_bolt_server_entity())
    write_json(RP / "entity" / "nature_bolt.entity.json", nature_bolt_client_entity())
    write_json(
        BP / "entities" / "fire_breath.entity.json",
        fire_breath_server_entity(),
    )
    write_json(
        BP / "entities" / "slime_blob.entity.json",
        slime_blob_server_entity(),
    )
    write_json(
        RP / "entity" / "fire_breath.entity.json",
        beetle_projectile_client_entity(
            "tf_slice:fire_breath",
            "geometry.tf_slice.fire_breath",
            "textures/blocks/fire_0",
            "entity_emissive_alpha",
        ),
    )
    write_json(
        RP / "entity" / "slime_blob.entity.json",
        beetle_projectile_client_entity(
            "tf_slice:slime_blob",
            "geometry.tf_slice.slime_blob",
            "textures/blocks/slime",
            "entity_alphablend",
        ),
    )
    write_json(RP / "models" / "entity" / "ruin_mobs.geo.json", geometry_document())
    write_json(RP / "animations" / "ruin_mobs.animation.json", animation_document())
    write_json(RP / "models" / "entity" / "redcap_armor.geo.json", redcap_boots_geometry())
    write_json(RP / "render_controllers" / "redcap_armor.render.json", redcap_armor_controller())
    for kind in ("iron", "ironwood"):
        write_json(RP / "attachables" / (kind + "_boots.attachable.json"), redcap_boots_attachable(kind))
    write_json(
        RP / "animation_controllers" / "ruin_mobs.controller.json",
        animation_controller_document(),
    )
    write_json(
        RP / "render_controllers" / "ruin_mobs.render.json",
        render_controller_document(),
    )

    for equipment_id in (
        "skeleton_druid",
        "skeleton_druid_baby",
        "redcap",
        "redcap_sapper",
    ):
        write_json(
            BP
            / "loot_tables"
            / "equipment"
            / "tf_slice"
            / ("%s.json" % equipment_id),
            equipment_table(equipment_id),
        )

    for item_name in ITEM_NAMES_ZH:
        write_json(
            BP / "items" / ("%s.item.json" % item_name),
            item_document(item_name),
        )
        copy_asset(
            UPSTREAM_ITEM_TEXTURES / ("%s.png" % item_name),
            RP / "textures" / "items" / ("%s.png" % item_name),
        )

    merge_json_mapping(
        RP / "textures" / "item_texture.json",
        ("texture_data",),
        {
            "tf_slice:%s" % name: {
                "textures": "textures/items/%s" % name
            }
            for name in ITEM_NAMES_ZH
        },
    )

    require_cleared_sound_bank("raven")
    require_cleared_sound_bank("redcap")
    require_cleared_sound_bank("kobold")
    require_cleared_sound_bank("hostile_wolf")
    require_cleared_sound_bank("wraith")
    merge_json_mapping(
        RP / "sounds" / "sound_definitions.json",
        ("sound_definitions",),
        ruin_sound_definitions(),
    )
    merge_json_mapping(
        RP / "sounds.json",
        ("entity_sounds", "entities"),
        ruin_entity_sounds(),
    )

    catalog_items = [
        "tf_slice:%s_spawn_egg" % mob_id for mob_id in sorted(MOBS)
    ] + ["tf_slice:%s" % name for name in ITEM_NAMES_ZH] + list(
        BIOME_CATALOG_ITEMS
    )
    add_creative_catalog_items(
        BP / "item_catalog" / "crafting_item_catalog.json",
        catalog_items,
    )

    for loot_id, entries in CHEST_LOOT.items():
        write_json(
            BP / "loot_tables" / "chests" / "tf_slice" / ("%s.json" % loot_id),
            chest_loot_table(entries),
        )

    zh_values = []
    en_values = []
    for mob_id in sorted(MOBS):
        zh_values.extend(
            [
                ("entity.tf_slice:%s.name" % mob_id, NAMES_ZH[mob_id]),
                (
                    "item.spawn_egg.entity.tf_slice:%s.name" % mob_id,
                    "生成 %s" % NAMES_ZH[mob_id],
                ),
            ]
        )
        english = mob_id.replace("_", " ").title()
        en_values.extend(
            [
                ("entity.tf_slice:%s.name" % mob_id, english),
                (
                    "item.spawn_egg.entity.tf_slice:%s.name" % mob_id,
                    "Spawn %s" % english,
                ),
            ]
        )
    for item_id, zh_name in ITEM_NAMES_ZH.items():
        zh_values.append(("item.tf_slice:%s.name" % item_id, zh_name))
        en_values.append(
            (
                "item.tf_slice:%s.name" % item_id,
                item_id.replace("_", " ").title(),
            )
        )
    zh_values.extend(BIOME_LOCALIZATION_ZH)
    en_values.extend(BIOME_LOCALIZATION_EN)
    add_localization(RP / "texts" / "zh_CN.lang", zh_values)
    add_localization(RP / "texts" / "en_US.lang", en_values)
    build_public_block_shapes()
    build_localization(ROOT)
    normalize_creative_catalog(ROOT)
    print(
        "built %d ruin mobs, projectile, models, equipment, loot and sound banks"
        % len(MOBS)
    )


if __name__ == "__main__":
    build()
