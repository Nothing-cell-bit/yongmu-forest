#!/usr/bin/env python3
"""Build the Knight Stronghold block and loot prerequisites."""

from __future__ import print_function

import json
import hashlib
import shutil
from pathlib import Path

from build_phantom_urghast_models import build as build_route_models
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

SOLID_BLOCKS = {
    "underbrick": "block/underbrick.png",
    "cracked_underbrick": "block/cracked_underbrick.png",
    "mossy_underbrick": "block/mossy_underbrick.png",
    "underbrick_floor": "block/underbrick_floor.png",
    "knightmetal_block": "block/knightmetal_block.png",
    "stronghold_shield": "block/shield_outside.png",
    "trophy_pedestal": "block/underbrick_floor.png",
    "knight_phantom_boss_spawner": "block/boss_spawner.png",
}
PEDESTAL_TEXTURES = {
    "north_latent": "block/pedestal/naga_latent.png",
    "south_latent": "block/pedestal/lich_latent.png",
    "east_latent": "block/pedestal/ur-ghast_latent.png",
    "west_latent": "block/pedestal/hydra_latent.png",
    "north_active": "block/pedestal/naga.png",
    "south_active": "block/pedestal/lich.png",
    "east_active": "block/pedestal/ur-ghast.png",
    "west_active": "block/pedestal/hydra.png",
    "top_latent": "block/pedestal/top.png",
    "top_active": "block/pedestal/top_glow.png",
}

ITEMS = {
    "armor_shard": (64, None, None),
    "armor_shard_cluster": (64, None, None),
    "knightmetal_ingot": (64, None, None),
    "knightmetal_ring": (64, None, None),
    "knightmetal_sword": (1, 7, 512),
    "knightmetal_pickaxe": (1, 5, 512),
    "knightmetal_axe": (1, 9, 512),
    "block_and_chain": (1, None, 99),
    "knightmetal_shield": (1, None, 1024),
    "phantom_helmet": (1, None, 363),
    "phantom_chestplate": (1, None, 528),
}
ARMOR = {
    "knightmetal_helmet": ("slot.armor.head", 3, 330),
    "knightmetal_chestplate": ("slot.armor.chest", 8, 480),
    "knightmetal_leggings": ("slot.armor.legs", 6, 450),
    "knightmetal_boots": ("slot.armor.feet", 3, 390),
}
ENTITY_STATS = {
    "block_chain_goblin": (20, 8, 0.28, 0.9, 1.4, "model/blockgoblin.png"),
    "lower_goblin_knight": (20, 4, 0.25, 0.9, 1.4, "model/doublegoblin.png"),
    "upper_goblin_knight": (30, 8, 0.25, 0.9, 1.4, "model/doublegoblin.png"),
    "helmet_crab": (13, 3, 0.28, 1.0, 0.8, "model/helmetcrab.png"),
    "knight_phantom": (35, 1, 0.3, 1.25, 2.5, "model/knightphantom.png"),
}
PROJECTILES = {
    "knight_axe_projectile": (0, "knightmetal_axe"),
    "knight_pickaxe_projectile": (3, "knightmetal_pickaxe"),
    "block_chain_projectile": (0, "block_and_chain_thrown"),
}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _pedestal_materials(active=False):
    suffix = "active" if active else "latent"
    return dict(
        (
            face,
            {
                "texture": "tf_slice:trophy_pedestal_%s_%s"
                % (face, suffix),
                "render_method": "opaque",
            },
        )
        for face in ("north", "south", "east", "west")
    ) | {
        "top": {
            "texture": "tf_slice:trophy_pedestal_top_%s" % suffix,
            "render_method": "opaque",
        },
        "bottom": {
            "texture": "tf_slice:trophy_pedestal_top_%s" % suffix,
            "render_method": "opaque",
        },
    }


def _pedestal_geometry():
    face_uv = {
        face: {
            "uv": [0, 0],
            "uv_size": [16, 16],
            "material_instance": face,
        }
        for face in ("north", "south", "east", "west", "up", "down")
    }
    face_uv["up"]["material_instance"] = "top"
    face_uv["down"]["material_instance"] = "bottom"

    def cube(origin, size):
        return {
            "origin": list(origin),
            "size": list(size),
            "uv": dict((face, dict(value)) for face, value in face_uv.items()),
        }

    cubes = [
        cube((-7, 0, -7), (14, 3, 14)),
        cube((-6, 3, -6), (12, 10, 12)),
        cube((-7, 13, -7), (14, 3, 14)),
        cube((-7, 12, -7), (3, 1, 3)),
        cube((4, 12, -7), (3, 1, 3)),
        cube((-7, 12, 4), (3, 1, 3)),
        cube((4, 12, 4), (3, 1, 3)),
    ]
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": "geometry.tf_slice.trophy_pedestal",
                    "texture_width": 16,
                    "texture_height": 16,
                    "visible_bounds_width": 2,
                    "visible_bounds_height": 1,
                    "visible_bounds_offset": [0, 0.5, 0],
                },
                "bones": [
                    {
                        "name": "block",
                        "pivot": [0, 0, 0],
                        "cubes": cubes,
                    }
                ],
            }
        ],
    }


def _block(identifier):
    unbreakable = identifier in (
        "stronghold_shield",
        "knight_phantom_boss_spawner",
    )
    components = {
        "minecraft:geometry": "geometry.tf_slice.courtyard_cube",
        "minecraft:material_instances": {
            "*": {
                "texture": "tf_slice:%s" % identifier,
                "render_method": "opaque",
            }
        },
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
    if identifier == "trophy_pedestal":
        components["minecraft:geometry"] = "geometry.tf_slice.trophy_pedestal"
        components["minecraft:material_instances"] = _pedestal_materials(False)
        components["netease:aabb"] = {
            "collision": {
                "min": [0.0625, 0.0, 0.0625],
                "max": [0.9375, 1.0, 0.9375],
            },
            "clip": {
                "min": [0.0625, 0.0, 0.0625],
                "max": [0.9375, 1.0, 0.9375],
            },
        }
    if unbreakable:
        components["minecraft:destructible_by_mining"] = False
        components["minecraft:destructible_by_explosion"] = False
    else:
        components["minecraft:destructible_by_mining"] = {
            "seconds_to_destroy": 1.5 if "underbrick" in identifier else 5.0
        }
        components["minecraft:destructible_by_explosion"] = {
            "explosion_resistance": 100.0 if "underbrick" in identifier else 6.0
        }
    if identifier in ("trophy_pedestal", "knight_phantom_boss_spawner"):
        components["netease:block_entity"] = {"tick": True, "movable": False}
    description = {
        "identifier": "tf_slice:%s" % identifier,
        "register_to_creative_menu": True,
    }
    if identifier == "trophy_pedestal":
        description["states"] = {"tf_slice:active": [False, True]}
    block = {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": description,
            "components": components,
        },
    }
    if identifier == "trophy_pedestal":
        block["minecraft:block"]["permutations"] = [
            {
                "condition": (
                    "query.block_state('tf_slice:active') == true"
                ),
                "components": {
                    "minecraft:light_emission": 10,
                    "minecraft:material_instances": _pedestal_materials(True),
                },
            }
        ]
    return block


def _loot(entries, minimum=2, maximum=4):
    return {
        "pools": [
            {
                "rolls": {"min": minimum, "max": maximum},
                "entries": entries,
            }
        ]
    }


def _counted(name, minimum, maximum, weight=None):
    value = {
        "type": "item",
        "name": name,
        "functions": [
            {
                "function": "set_count",
                "count": {"min": int(minimum), "max": int(maximum)},
            }
        ],
    }
    if weight is not None:
        value["weight"] = int(weight)
    return value


def _pool(rolls, entries):
    return {"rolls": int(rolls), "entries": list(entries)}


def _stronghold_loot_tables():
    """Bedrock-safe mapping of the locked release's three Java tables."""
    cache = {
        "pools": [
            _pool(4, [
                _counted("minecraft:stick", 1, 12),
                _counted("minecraft:coal", 1, 12),
                _counted("minecraft:arrow", 1, 12),
                _counted("tf_slice:maze_wafer", 1, 9),
                {"type": "item", "name": "minecraft:blue_wool"},
                _counted("minecraft:iron_ingot", 1, 2),
            ]),
            _pool(2, [
                {"type": "item", "name": "minecraft:bucket"},
                _counted("minecraft:iron_ingot", 1, 6),
                _counted("tf_slice:ironwood_ingot", 1, 6),
                # The slice has no placeable firefly item; glowstone dust is
                # the closest functional light-material substitute.
                _counted("minecraft:glowstone_dust", 1, 5),
                {"type": "item", "name": "tf_slice:charm_of_keeping_1"},
                _counted("tf_slice:armor_shard", 1, 3),
            ]),
            _pool(1, [
                _counted("tf_slice:knightmetal_ingot", 1, 8, 75),
                {"type": "item", "name": "minecraft:bow", "weight": 75},
                {"type": "item", "name": "minecraft:iron_sword", "weight": 75},
                {"type": "item", "name": "tf_slice:ironwood_sword", "weight": 75},
                {"type": "item", "name": "tf_slice:steeleaf_sword", "weight": 75},
                {"type": "item", "name": "minecraft:enchanted_book", "weight": 25},
            ]),
        ]
    }
    room = {
        "pools": [
            _pool(4, [
                _counted("minecraft:iron_ingot", 1, 4, 75),
                _counted("minecraft:gunpowder", 1, 4, 75),
                {"type": "item", "name": "minecraft:milk_bucket", "weight": 75},
                _counted("tf_slice:maze_wafer", 1, 12, 75),
                _counted("tf_slice:ironwood_ingot", 1, 4, 75),
                _counted("minecraft:glowstone_dust", 1, 5, 75),
            ]),
            _pool(2, [
                _counted("tf_slice:steeleaf_ingot", 1, 6),
                {"type": "item", "name": "tf_slice:charm_of_life_1"},
                {"type": "item", "name": "tf_slice:steeleaf_helmet"},
                {"type": "item", "name": "tf_slice:steeleaf_chestplate"},
                {"type": "item", "name": "tf_slice:steeleaf_leggings"},
                {"type": "item", "name": "tf_slice:steeleaf_boots"},
                {"type": "item", "name": "tf_slice:steeleaf_pickaxe"},
                {"type": "item", "name": "tf_slice:ironwood_chestplate"},
                {"type": "item", "name": "tf_slice:ironwood_sword"},
            ]),
            _pool(1, [
                {"type": "item", "name": "tf_slice:ironwood_sword"},
                {"type": "item", "name": "tf_slice:steeleaf_sword"},
                {"type": "item", "name": "minecraft:iron_sword"},
                {"type": "item", "name": "minecraft:bow"},
                {"type": "item", "name": "minecraft:diamond_sword"},
                {"type": "item", "name": "minecraft:enchanted_book"},
                {"type": "item", "name": "tf_slice:maze_map_focus"},
            ]),
        ]
    }
    boss = {
        "pools": [
            _pool(4, [
                {"type": "item", "name": "tf_slice:knightmetal_sword"},
                {"type": "item", "name": "tf_slice:knightmetal_pickaxe"},
                {"type": "item", "name": "tf_slice:knightmetal_axe"},
            ]),
            _pool(2, [
                {"type": "item", "name": "tf_slice:phantom_helmet"},
                {"type": "item", "name": "tf_slice:phantom_chestplate"},
            ]),
            _pool(1, [
                {"type": "item", "name": "tf_slice:phantom_helmet"},
                {"type": "item", "name": "tf_slice:phantom_chestplate"},
            ]),
            _pool(1, [
                {"type": "item", "name": "tf_slice:knight_phantom_trophy"},
            ]),
        ]
    }
    return {"stronghold_cache": cache, "stronghold_room": room, "stronghold_boss": boss}


def _item(identifier, stack_size, damage, durability):
    components = {
        "minecraft:display_name": {
            "value": "item.tf_slice:%s.name" % identifier
        },
        "minecraft:icon": {
            "textures": {"default": "tf_slice:%s" % identifier}
        },
        "minecraft:max_stack_size": int(stack_size),
    }
    if damage is not None:
        components["minecraft:hand_equipped"] = True
        components["minecraft:damage"] = int(damage)
        role = identifier.rsplit("_", 1)[-1]
        if role in ("sword", "axe", "pickaxe"):
            components["minecraft:enchantable"] = {"slot": role, "value": 9}
    if durability is not None:
        components["minecraft:durability"] = {
            "max_durability": int(durability)
        }
    if identifier == "block_and_chain":
        # Locked Java source uses item/handheld, not a custom entity model.
        components["minecraft:hand_equipped"] = True
    elif identifier == "knightmetal_shield":
        components["minecraft:allow_off_hand"] = True
        components["minecraft:use_animation"] = "block"
    return {
        "format_version": "1.21.60",
        "minecraft:item": {
            "description": {
                "identifier": "tf_slice:%s" % identifier,
                "menu_category": {"category": "equipment"},
            },
            "components": components,
        },
    }


def _knightmetal_shield_attachable():
    return {
        "format_version": "1.20.30",
        "minecraft:attachable": {
            "description": {
                "identifier": "tf_slice:knightmetal_shield",
                "item": {
                    "tf_slice:knightmetal_shield": (
                        "query.is_owner_identifier_any('minecraft:player')"
                    )
                },
                "materials": {
                    "default": "entity_alphatest",
                    "enchanted": "entity_alphatest_glint",
                },
                "textures": {
                    "default": "textures/items/knightmetal_shield",
                    "enchanted": "textures/misc/enchanted_item_glint",
                },
                "geometry": {
                    "default": "geometry.tf_slice.knightmetal_shield"
                },
                "animations": {
                    "wield": "controller.animation.shield.wield",
                    "wield_main_hand_first_person": (
                        "animation.shield.wield_main_hand_first_person"
                    ),
                    "wield_off_hand_first_person": (
                        "animation.shield.wield_off_hand_first_person"
                    ),
                    "wield_first_person_block": (
                        "animation.shield.wield_first_person_blocking"
                    ),
                    "wield_main_hand_first_person_block": (
                        "animation.shield.wield_main_hand_first_person_blocking"
                    ),
                    "wield_off_hand_first_person_block": (
                        "animation.shield.wield_off_hand_first_person_blocking"
                    ),
                    "wield_third_person": (
                        "animation.shield.wield_third_person"
                    ),
                },
                "scripts": {
                    "initialize": [
                        "variable.main_hand_first_person_pos_x = 5.3;",
                        "variable.main_hand_first_person_pos_y = 26.0;",
                        "variable.main_hand_first_person_pos_z = 0.4;",
                        "variable.main_hand_first_person_rot_x = 91.0;",
                        "variable.main_hand_first_person_rot_y = 65.0;",
                        "variable.main_hand_first_person_rot_z = -43.0;",
                        "variable.off_hand_first_person_pos_x = -13.5;",
                        "variable.off_hand_first_person_pos_y = -5.8;",
                        "variable.off_hand_first_person_pos_z = 5.1;",
                        (
                            "variable.off_hand_first_person_with_bow_pos_z "
                            "= -25.0;"
                        ),
                        "variable.off_hand_first_person_rot_x = 1.0;",
                        "variable.off_hand_first_person_rot_y = 176.0;",
                        "variable.off_hand_first_person_rot_z = -2.5;",
                    ],
                    "pre_animation": [
                        (
                            "variable.is_blocking_main_hand = query.blocking "
                            "&& !query.is_item_name_any('slot.weapon.offhand', "
                            "'tf_slice:knightmetal_shield') && "
                            "query.is_item_name_any('slot.weapon.mainhand', "
                            "'tf_slice:knightmetal_shield');"
                        ),
                        (
                            "variable.is_blocking_off_hand = query.blocking && "
                            "query.is_item_name_any('slot.weapon.offhand', "
                            "'tf_slice:knightmetal_shield');"
                        ),
                        (
                            "variable.is_using_bow = "
                            "(query.get_equipped_item_name == 'bow') && "
                            "(query.main_hand_item_use_duration > 0.0f);"
                        ),
                    ],
                    "animate": ["wield"],
                },
                "render_controllers": ["controller.render.item_default"],
            }
        },
    }


def _knightmetal_shield_geometry():
    return {
        "format_version": "1.16.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": "geometry.tf_slice.knightmetal_shield",
                    "texture_width": 64,
                    "texture_height": 32,
                },
                "bones": [
                    {
                        "name": "shield",
                        "binding": "q.item_slot_to_bone_name(c.item_slot)",
                        "pivot": [1.0, 15.5, 3.0],
                        "cubes": [
                            {
                                "origin": [0.0, 25.0, 0.0],
                                "size": [2.0, 6.0, 6.0],
                                "uv": [26, 0],
                            },
                            {
                                "origin": [-5.0, 17.0, -1.0],
                                "size": [12.0, 22.0, 1.0],
                                "uv": [0, 0],
                            },
                        ],
                    }
                ],
            }
        ],
    }


def _block_and_chain_attachable():
    return {"format_version": "1.20.30", "minecraft:attachable": {
        "description": {
            "identifier": "tf_slice:block_and_chain",
            "item": {"tf_slice:block_and_chain": "query.is_owner_identifier_any('minecraft:player')"},
            "materials": {"default": "entity_alphatest", "enchanted": "entity_alphatest_glint"},
            "textures": {"default": "textures/items/block_and_chain",
                         "thrown": "textures/items/block_and_chain_thrown",
                         "enchanted": "textures/misc/enchanted_item_glint"},
            "geometry": {"default": "geometry.tf_slice.block_and_chain_held",
                         "thrown": "geometry.tf_slice.block_and_chain_held_thrown"},
            "animations": {"grip": "animation.tf_slice.block_and_chain.grip"},
            "scripts": {"animate": ["grip"]},
            "render_controllers": ["controller.render.tf_slice.block_and_chain"],
        }
    }}


def _block_and_chain_held_animation():
    # Java bow and handheld have IDENTICAL first-person display transforms.
    # Preserve that calibrated native baseline; correct third-person only.
    # C = B J^-1 BowJava^-1 HandheldJava J B^-1, with sprite XZ -> Java XY.
    # Flatten parent * correction onto the known-visible rightitem root.
    # The native third-person parent has identity rotation/scale, so its
    # translation adds to C; first person retains the exact native baseline.
    # Do not move texture_meshes onto an unverified child bone again.
    return {"format_version": "1.10.0", "animations": {
        "animation.tf_slice.block_and_chain.grip": {
            "loop": True, "bones": {"rightitem": {
                "position": ["c.is_first_person ? -5.5 : -2.584032362",
                             "c.is_first_person ? -3.0 : 1.07263356",
                             "c.is_first_person ? -3.0 : -4.651442985"],
                "rotation": ["c.is_first_person ? 38.0 : 16.384463419",
                             "c.is_first_person ? -120.0 : -5.969980099",
                             "c.is_first_person ? -63.0 : 3.774393805"],
                "scale": ["c.is_first_person ? 1 : 0.9444444444444444"] * 3,
            }}
        }
    }}


def _block_and_chain_render_controller():
    return {"format_version": "1.8.0", "render_controllers": {
        "controller.render.tf_slice.block_and_chain": {
            "geometry": "query.mod.tf_chain_active ? Geometry.thrown : Geometry.default",
            "materials": [{"*": "query.is_enchanted ? Material.enchanted : Material.default"}],
            "textures": ["query.mod.tf_chain_active ? Texture.thrown : Texture.default",
                         "Texture.enchanted"],
        }
    }}


def _block_and_chain_held_geometry():
    # Bundled bow_standby texture_meshes format preserves sprite silhouette and
    # edge extrusion. Distinct meshes are needed when the thrown alpha differs.
    geometries = []
    for texture, suffix in (("default", ""), ("thrown", "_thrown")):
        geometries.append({
            "description": {"identifier": "geometry.tf_slice.block_and_chain_held" + suffix,
                            "texture_width": 16, "texture_height": 16},
            "bones": [{"name": "rightitem", "texture_meshes": [{
                "local_pivot": [6.0, 0.0, 6.0], "position": [2.0, 1.0, -2.0],
                "rotation": [0.0, -135.0, 90.0], "texture": texture,
            }]}],
        })
    return {"format_version": "1.16.0", "minecraft:geometry": geometries}


def _armor(identifier, slot, protection, durability):
    value = _item(identifier, 1, None, durability)
    value["minecraft:item"]["components"]["minecraft:wearable"] = {
        "slot": slot,
        "protection": protection,
    }
    value["minecraft:item"]["components"]["minecraft:enchantable"] = {
        "slot": {
            "slot.armor.head": "armor_head",
            "slot.armor.chest": "armor_torso",
            "slot.armor.legs": "armor_legs",
            "slot.armor.feet": "armor_feet",
        }[slot],
        "value": 9,
    }
    return value


def _hostile_entity(identifier, stats):
    health, damage, movement, width, height, _texture = stats
    flying = identifier == "knight_phantom"
    navigation = "minecraft:navigation.fly" if flying else "minecraft:navigation.walk"
    movement_component = "minecraft:movement.fly" if flying else "minecraft:movement.basic"
    description = {
        "identifier": "tf_slice:%s" % identifier,
        "is_spawnable": True,
        "is_summonable": True,
        "is_experimental": False,
    }
    if identifier == "upper_goblin_knight":
        description["properties"] = {
            "tf_slice:heavy_spear": {
                "type": "bool", "default": False, "client_sync": True,
            },
            "tf_slice:shield_disabled": {
                "type": "bool", "default": False, "client_sync": True,
            },
        }
    elif identifier == "knight_phantom":
        description["properties"] = {
            "tf_slice:charging": {
                "type": "bool", "default": False, "client_sync": True,
            }
        }
    components = {
        "minecraft:type_family": {
            "family": [identifier, "knight_stronghold", "monster", "mob"]
        },
        "minecraft:nameable": {},
        "minecraft:health": {"value": health, "max": health},
        "minecraft:attack": {"damage": damage},
        "minecraft:movement": {"value": movement},
        "minecraft:collision_box": {"width": width, "height": height},
        "minecraft:physics": {"has_gravity": not flying},
        "minecraft:pushable": {
            "is_pushable": not flying,
            "is_pushable_by_piston": False,
        },
        movement_component: {},
        navigation: {
            "can_path_over_water": True,
            "avoid_water": True,
            "avoid_damage_blocks": True,
        },
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 2,
            "must_see": True,
            "entity_types": [
                {
                    "filters": {
                        "test": "is_family",
                        "subject": "other",
                        "value": "player",
                    },
                    "max_dist": 30 if flying else 24,
                }
            ],
        },
    }
    if identifier == "knight_phantom":
        components["minecraft:persistent"] = {}
    else:
        components["minecraft:despawn"] = {"despawn_from_distance": {}}
    if flying:
        components["minecraft:behavior.random_hover"] = {
            "priority": 7, "xz_dist": 8, "y_dist": 5,
            "y_offset": 1, "interval": 1,
        }
    else:
        components.update({
            "minecraft:jump.static": {},
            "minecraft:behavior.melee_attack": {
                "priority": 4,
                "speed_multiplier": 1.1,
                "track_target": True,
            },
            "minecraft:behavior.random_stroll": {
                "priority": 6, "speed_multiplier": 0.8,
            },
            "minecraft:behavior.look_at_player": {
                "priority": 7, "look_distance": 8.0, "probability": 0.04,
            },
            "minecraft:behavior.random_look_around": {"priority": 8},
        })
    if identifier == "helmet_crab":
        components["minecraft:armor"] = {"value": 6}
        components["minecraft:behavior.melee_attack"]["speed_multiplier"] = 1.0
        components["minecraft:behavior.random_stroll"]["speed_multiplier"] = 1.0
        components["minecraft:behavior.leap_at_target"] = {
            "priority": 3, "yd": 0.28,
        }
    elif identifier == "lower_goblin_knight":
        components["minecraft:rideable"] = {
            "seat_count": 1,
            "family_types": ["upper_goblin_knight"],
            "pull_in_entities": True,
            "controlling_seat": 0,
            "seats": {
                "position": [0, 1.1, 0],
                "min_rider_count": 0,
                "max_rider_count": 1,
            },
        }
    events = {}
    if identifier == "upper_goblin_knight":
        events = {
            "tf_slice:start_heavy_spear": {
                "set_property": {"tf_slice:heavy_spear": True}
            },
            "tf_slice:stop_heavy_spear": {
                "set_property": {"tf_slice:heavy_spear": False}
            },
            "tf_slice:disable_shield": {
                "set_property": {"tf_slice:shield_disabled": True}
            },
        }
    elif identifier == "knight_phantom":
        events = {
            "tf_slice:start_charging": {
                "set_property": {"tf_slice:charging": True}
            },
            "tf_slice:stop_charging": {
                "set_property": {"tf_slice:charging": False}
            },
        }
    try:
        from tools.goblin_assets import configure_entity
    except ImportError:
        from goblin_assets import configure_entity
    return configure_entity(identifier, {
        "format_version": "1.20.60",
        "minecraft:entity": {
            "description": description,
            "components": components,
            "events": events,
        },
    })


def _client_entity(identifier, texture_source):
    # The route model builder owns geometry, animation and texture branches.
    # Keeping this adapter prevents a content rebuild from restoring the old
    # one-cube placeholder client definition.
    from build_phantom_urghast_models import client_entity
    return client_entity(identifier)


def _projectile_entity(identifier, damage):
    document = {
        "format_version": "1.20.60",
        "minecraft:entity": {
            "description": {
                "identifier": "tf_slice:%s" % identifier,
                "is_spawnable": False,
                "is_summonable": True,
                "is_experimental": False,
            },
            "components": {
                "minecraft:type_family": {
                    "family": [identifier, "knight_projectile", "projectile"]
                },
                "minecraft:collision_box": {"width": 0.35, "height": 0.35},
                "minecraft:physics": {"has_gravity": False},
                "minecraft:projectile": {
                    "power": 0.6,
                    "gravity": (
                        0.05
                        if identifier == "block_chain_projectile"
                        else 0.0
                    ),
                    "uncertainty_base": 0.0,
                    "anchor": 1,
                    "on_hit": {
                        "impact_damage": {
                            "damage": int(damage),
                            "knockback": True,
                            "semi_random_diff_damage": False,
                        },
                    },
                },
            },
        },
    }
    if identifier != "block_chain_projectile":
        document["minecraft:entity"]["components"]["minecraft:projectile"][
            "on_hit"
        ]["remove_on_hit"] = {}
    else:
        document["minecraft:entity"]["description"]["properties"] = {
            "tf_slice:chain_%s" % axis: {
                "type": "float",
                "range": [-20.0, 20.0],
                "default": 0.0,
                "client_sync": True,
            }
            for axis in ("x", "y", "z")
        }
        document["minecraft:entity"]["component_groups"] = {
            "tf_slice:instant_remove": {"minecraft:instant_despawn": {}}
        }
        document["minecraft:entity"]["events"] = {
            "tf_slice:instant_remove": {
                "add": {"component_groups": ["tf_slice:instant_remove"]}
            }
        }
    return document


def _block_chain_projectile_geometry():
    # Exact classic ModelTFSpikeBlock layout.  The source model is Y-down;
    # these pivots are recentered around the projectile and reflected to the
    # Bedrock Y-up convention.  Source Z rotations change sign under that
    # reflection, matching the route-model converter used elsewhere.
    spikeTransforms = (
        ((0, 5, 0), (0, 0, 0)),
        ((0, 4, 4), (45, 0, 0)),
        ((4, 4, 4), (-55, 45, 0)),
        ((4, 4, 0), (0, 0, -45)),
        ((4, 4, -4), (-35, -45, 0)),
        ((0, 4, -4), (45, 0, 0)),
        ((-4, 4, -4), (-35, 45, 0)),
        ((-4, 4, 0), (0, 0, -45)),
        ((-4, 4, 4), (-55, -45, 0)),
        ((0, 0, 0), (0, 0, 0)),
        ((0, 0, 4), (0, 0, 0)),
        ((4, 0, 5), (0, 45, 0)),
        ((5, 0, 0), (0, 0, 0)),
        ((4, 0, -4), (0, 45, 0)),
        ((0, 0, -5), (0, 0, 0)),
        ((-4, 0, -4), (0, 45, 0)),
        ((-5, 0, 0), (0, 0, 0)),
        ((-4, 0, 4), (0, 45, 0)),
        ((0, -5, 0), (0, 0, 0)),
        ((0, -4, 4), (45, 0, 0)),
        ((4, -4, 4), (-35, 45, 0)),
        ((4, -4, 0), (0, 0, -45)),
        ((4, -4, -4), (-55, -45, 0)),
        ((0, -4, -4), (45, 0, 0)),
        ((-4, -4, -4), (-55, 45, 0)),
        ((-4, -4, 0), (0, 0, -45)),
        ((-4, -4, 4), (-35, -45, 0)),
    )
    bones = [
        {
            "name": "block",
            "pivot": [0, 0, 0],
            "cubes": [
                {
                    "origin": [-4, -4, -4],
                    "size": [8, 8, 8],
                    "uv": [32, 16],
                }
            ],
        }
    ]
    for index, (pivot, rotation) in enumerate(spikeTransforms):
        bone = {
            "name": "spikes_%d" % index,
            "parent": "block",
            "pivot": list(pivot),
            "cubes": [
                {
                    "origin": [value - 1 for value in pivot],
                    "size": [2, 2, 2],
                    "uv": [56, 16],
                }
            ],
        }
        if any(rotation):
            bone["rotation"] = list(rotation)
        bones.append(bone)
    # Restore the source head's origin: center is four model units above the
    # entity root. Move every visible part together, not just the chain endpoint.
    for visible in bones:
        if visible['name'] != 'block':
            visible['pivot'][1] += 4
        for cube in visible.get('cubes', []):
            cube['origin'][1] += 4
    bones.append({"name": "chain_head", "pivot": [0, 4, 0]})
    bones.append({"name": "chain_root", "pivot": [0, 0, 0]})
    for name, pivot in (("chain_origin", [0, 0, 0]),
                        ("chain_basis_x", [16, 0, 0]),
                        ("chain_basis_y", [0, 16, 0]),
                        ("chain_basis_z", [0, 0, 16])):
        bones.append({"name": name, "pivot": pivot})
    for index in range(5):
        bones.append(
            {
                "name": "chain_%d" % index,
                "parent": "chain_root",
                "pivot": [0, 0, 0],
                "cubes": [
                    {
                        "origin": [-1, -1, -1],
                        "size": [2, 2, 2],
                        "uv": [56, 16],
                    }
                ],
            }
        )
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": "geometry.tf_slice.block_chain_projectile",
                    "texture_width": 64,
                    "texture_height": 32,
                    "visible_bounds_width": 34.0,
                    "visible_bounds_height": 34.0,
                    "visible_bounds_offset": [0, 0, 0],
                },
                "bones": bones,
            }
        ],
    }


def _projectile_client(identifier, texture):
    blockChain = identifier == "block_chain_projectile"
    description = {
        "identifier": "tf_slice:%s" % identifier,
        "materials": {"default": "entity_alphatest"},
        "textures": {
            "default": (
                "textures/entity/tf_slice/block_chain_goblin"
                if blockChain
                else "textures/items/%s" % texture
            )
        },
        "geometry": {
            "default": (
                "geometry.tf_slice.block_chain_projectile"
                if blockChain
                else "geometry.tf_slice.nature_bolt"
            )
        },
        "render_controllers": ["controller.render.default"],
    }
    if blockChain:
        description["animations"] = {
            "chain": "animation.tf_slice.block_chain_projectile.chain"
        }
        description["scripts"] = {
            "animate": ["chain"],
        }
    else:
        description["animations"] = {
            "spin": "animation.tf_slice.nature_bolt.spin"
        }
        description["scripts"] = {"animate": ["spin"]}
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": description
        },
    }


def _block_chain_projectile_animation():
    # The native projectile only renders the spike block. Its moving actor
    # frame must never transform links. A stationary client-only carrier uses
    # two measured local endpoints, so no Euler convention/interpolation enters.
    factors = (0.95, 0.75, 0.55, 0.35, 0.15)
    bones = {}
    for index, factor in enumerate(factors):
        bones["chain_%d" % index] = {
            "position": [
                "query.mod.tf_chain_head_%s * %s + query.mod.tf_chain_hand_%s * %s"
                % (axis, round(1.0-factor, 2), axis, factor)
                for axis in "xyz"
            ],
            "scale": "query.mod.tf_chain_ready",
        }
    return {
        "format_version": "1.10.0",
        "animations": {
            "animation.tf_slice.block_chain_projectile.chain": {
                "loop": True,
                "bones": {"chain_%d" % index: {"scale": 0} for index in range(5)},
            },
            "animation.tf_slice.block_chain_link.chain": {
                "loop": True,
                "bones": bones,
            }
        },
    }


def _block_chain_link_behavior():
    return {
        "format_version": "1.20.60",
        "minecraft:entity": {
            "description": {
                "identifier": "tf_slice:block_chain_link",
                "is_spawnable": False,
                "is_summonable": True,
                "is_experimental": False,
            },
            "component_groups": {
                "tf_slice:instant_remove": {"minecraft:instant_despawn": {}}
            },
            "components": {
                "minecraft:type_family": {
                    "family": ["block_chain_link", "chain_visual"]
                },
                "minecraft:collision_box": {"width": 0.01, "height": 0.01},
                "minecraft:physics": {
                    "has_gravity": False,
                    "has_collision": False,
                },
                "minecraft:damage_sensor": {
                    "triggers": [
                        {"cause": "all", "deals_damage": False}
                    ]
                },
            },
            "events": {
                "tf_slice:instant_remove": {
                    "add": {"component_groups": ["tf_slice:instant_remove"]}
                }
            },
        },
    }


def _block_chain_link_client():
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": "tf_slice:block_chain_link",
                "materials": {"default": "entity_alphatest"},
                "textures": {
                    "default": "textures/entity/tf_slice/block_chain_goblin"
                },
                "geometry": {"default": "geometry.tf_slice.block_chain_link"},
                "animations": {"chain": "animation.tf_slice.block_chain_link.chain"},
                "scripts": {"animate": ["chain"]},
                "render_controllers": ["controller.render.tf_slice.block_chain_link"],
            }
        },
    }


def _block_chain_link_geometry():
    bones = [{"name": "chain_%d" % index, "pivot": [0, 0, 0],
              "cubes": [{"origin": [-1, -1, -1], "size": [2, 2, 2], "uv": [56, 16]}]}
             for index in range(5)]
    for name, pivot in (("chain_origin", [0, 0, 0]),
                        ("chain_basis_x", [16, 0, 0]),
                        ("chain_basis_y", [0, 16, 0]),
                        ("chain_basis_z", [0, 0, 16])):
        bones.append({"name": name, "pivot": pivot})
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": "geometry.tf_slice.block_chain_link",
                    "texture_width": 64,
                    "texture_height": 32,
                    "visible_bounds_width": 66.0,
                    "visible_bounds_height": 66.0,
                    "visible_bounds_offset": [0, 0, 0],
                },
                "bones": bones,
            }
        ],
    }


def _block_chain_link_render_controller():
    return {"format_version": "1.8.0", "render_controllers": {
        "controller.render.tf_slice.block_chain_link": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}],
            "textures": ["Texture.default"],
            "part_visibility": [{"chain_%d" % index: "query.mod.tf_chain_ready > 0.5"}
                                for index in range(5)],
        }
    }}


def _recipe(identifier, ingredients, result, count=1):
    return {
        "format_version": "1.20.10",
        "minecraft:recipe_shapeless": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "tags": ["crafting_table"],
            "ingredients": [{"item": value} for value in ingredients],
            "unlock": {"context": "AlwaysUnlocked"},
            "result": {"item": result, "count": count},
        },
    }


def _append_language(path, lines):
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    existing_lines = [line for line in existing.splitlines() if not any(line.startswith(key + "=") for key in lines)]
    existing_lines.extend("%s=%s" % (key, value) for key, value in lines.items())
    path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


def build():
    terrain = _load(RP / "textures" / "terrain_texture.json")
    legacy_blocks = _load(RP / "blocks.json")
    texture_data = terrain["texture_data"]
    target_texture_dir = RP / "textures" / "blocks"
    for identifier, source in SOLID_BLOCKS.items():
        _write(BP / "netease_blocks" / (identifier + ".json"), _block(identifier))
        if identifier == "trophy_pedestal":
            continue
        target = target_texture_dir / (identifier + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(UPSTREAM / "textures" / source), str(target))
        key = "tf_slice:%s" % identifier
        texture_data[key] = {"textures": "textures/blocks/%s" % identifier}
        legacy_blocks[key] = {
            "textures": key,
            "sound": "metal" if "knightmetal" in identifier else "stone",
        }
    _write(
        RP / "models" / "blocks" / "trophy_pedestal.geo.json",
        _pedestal_geometry(),
    )
    for suffix, source in PEDESTAL_TEXTURES.items():
        target_name = "trophy_pedestal_%s" % suffix
        target = target_texture_dir / (target_name + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(UPSTREAM / "textures" / source), str(target))
        texture_data["tf_slice:%s" % target_name] = {
            "textures": "textures/blocks/%s" % target_name
        }
    legacy_blocks["tf_slice:trophy_pedestal"] = {
        "textures": "tf_slice:trophy_pedestal_top_latent",
        "sound": "stone",
    }
    _write(RP / "textures" / "terrain_texture.json", terrain)
    _write(RP / "blocks.json", legacy_blocks)

    item_atlas = _load(RP / "textures" / "item_texture.json")
    item_texture_data = item_atlas["texture_data"]
    for identifier, values in dict(ITEMS, **dict((key, (1, None, value[2])) for key, value in ARMOR.items())).items():
        if identifier in ARMOR:
            slot, protection, durability = ARMOR[identifier]
            document = _armor(identifier, slot, protection, durability)
        else:
            document = _item(identifier, *values)
        _write(BP / "items" / (identifier + ".item.json"), document)
        source_name = identifier
        source_path = UPSTREAM / "textures" / "item" / (source_name + ".png")
        if identifier == "knightmetal_shield":
            source_path = UPSTREAM / "textures" / "model" / "knightmetal_shield.png"
        elif identifier == "knight_phantom_trophy":
            # Java renders the trophy as a block entity.  The NetEase item
            # atlas needs a flat icon, so reuse the source Phantom helmet art.
            source_path = UPSTREAM / "textures" / "item" / "phantom_helmet.png"
        target = RP / "textures" / "items" / (identifier + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source_path), str(target))
        atlasName = (
            "knightmetal_shield_icon"
            if identifier == "knightmetal_shield"
            else identifier
        )
        item_texture_data["tf_slice:%s" % identifier] = {
            "textures": "textures/items/%s" % atlasName
        }
    _write(
        RP / "attachables" / "knightmetal_shield.attachable.json",
        _knightmetal_shield_attachable(),
    )
    _write(
        RP / "models" / "entity" / "knightmetal_shield.geo.json",
        _knightmetal_shield_geometry(),
    )
    _write(RP / "attachables" / "block_and_chain.attachable.json", _block_and_chain_attachable())
    _write(RP / "models" / "entity" / "block_and_chain_held.geo.json", _block_and_chain_held_geometry())
    _write(RP / "animations" / "block_and_chain_held.animation.json", _block_and_chain_held_animation())
    _write(RP / "render_controllers" / "block_and_chain.render_controllers.json", _block_and_chain_render_controller())
    _write(RP / "textures" / "item_texture.json", item_atlas)

    for identifier, stats in ENTITY_STATS.items():
        _write(BP / "entities" / (identifier + ".entity.json"), _hostile_entity(identifier, stats))
        _write(RP / "entity" / (identifier + ".entity.json"), _client_entity(identifier, stats[-1]))
        source_path = UPSTREAM / "textures" / stats[-1]
        target = RP / "textures" / "entity" / "tf_slice" / (identifier + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source_path), str(target))
        _write(
            BP / "loot_tables" / "entities" / "tf_slice" / (identifier + ".json"),
            _loot(
                [
                    {"type": "item", "name": "tf_slice:armor_shard", "weight": 8},
                    {"type": "item", "name": "tf_slice:knightmetal_ingot", "weight": 1},
                ],
                0,
                2,
            ),
        )

    for identifier, (damage, texture) in PROJECTILES.items():
        _write(
            BP / "entities" / (identifier + ".entity.json"),
            _projectile_entity(identifier, damage),
        )
        _write(
            RP / "entity" / (identifier + ".entity.json"),
            _projectile_client(identifier, texture),
        )
    _write(
        RP / "models" / "entity" / "block_chain_projectile.geo.json",
        _block_chain_projectile_geometry(),
    )
    _write(
        RP / "animations" / "block_chain_projectile.animation.json",
        _block_chain_projectile_animation(),
    )
    _write(
        BP / "entities" / "block_chain_link.entity.json",
        _block_chain_link_behavior(),
    )
    _write(
        RP / "entity" / "block_chain_link.entity.json",
        _block_chain_link_client(),
    )
    _write(
        RP / "models" / "entity" / "block_chain_link.geo.json",
        _block_chain_link_geometry(),
    )
    _write(
        RP / "render_controllers" / "block_chain_link.render_controllers.json",
        _block_chain_link_render_controller(),
    )
    thrown_source = UPSTREAM / "textures" / "item" / "block_and_chain_thrown.png"
    thrown_target = RP / "textures" / "items" / "block_and_chain_thrown.png"
    thrown_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(thrown_source), str(thrown_target))

    _write(
        BP / "enchantments" / "destruction.enchantment.json",
        {
            "format_version": 1,
            "tf_slice:enchantment": {
                "identifier": "tf_slice:destruction",
                "max_level": 3,
                "compatible_items": ["tf_slice:block_and_chain"],
                "effect": "increase_flail_block_break_radius",
            },
        },
    )
    _write(
        BP / "recipes" / "armor_shard_cluster.recipe.json",
        _recipe("armor_shard_cluster", ["tf_slice:armor_shard"] * 9, "tf_slice:armor_shard_cluster"),
    )
    _write(
        BP / "recipes" / "knightmetal_ingot.recipe.json",
        _recipe("knightmetal_ingot", ["tf_slice:armor_shard_cluster"], "tf_slice:knightmetal_ingot"),
    )

    evidence_models = []
    for identifier, stats in ENTITY_STATS.items():
        texture = UPSTREAM / "textures" / stats[-1]
        evidence_models.append(
            {
                "identifier": "tf_slice:%s" % identifier,
                "textureSha256": hashlib.sha256(texture.read_bytes()).hexdigest().upper(),
                "requiredViews": ["front", "back", "left", "right", "top", "three_quarter"],
                "requiredPoses": ["rest", "walk_extreme", "look_up", "look_down"],
                "offlineEvidence": [],
            }
        )
    for identifier, (_damage, texture) in PROJECTILES.items():
        source = UPSTREAM / "textures" / "item" / (texture + ".png")
        evidence_models.append(
            {
                "identifier": "tf_slice:%s" % identifier,
                "textureSha256": hashlib.sha256(source.read_bytes()).hexdigest().upper(),
                "requiredViews": ["front", "back", "left", "right", "top", "three_quarter"],
                "requiredPoses": ["rest", "walk_extreme", "look_up", "look_down"],
                "offlineEvidence": [],
            }
        )
    _write(
        ROOT / "evidence" / "models" / "knight_route.json",
        {
            "status": "rejected",
            "offlineEvidenceComplete": False,
            "clientAccepted": False,
            "runtimeVerified": False,
            "blockingReason": (
                "Source-specific geometry, animations, and rendered six-view/four-pose "
                "PNG evidence have not passed the offline model gate."
            ),
            "sourceVersion": "1.20.1-4.3.2508",
            "models": evidence_models,
        },
    )

    names = {}
    for identifier in list(ITEMS) + list(ARMOR):
        names["item.tf_slice:%s.name" % identifier] = identifier.replace("_", " ").title()
    for identifier in ENTITY_STATS:
        display = identifier.replace("_", " ").title()
        names["entity.tf_slice:%s.name" % identifier] = display
        names["item.spawn_egg.entity.tf_slice:%s.name" % identifier] = display
    _append_language(RP / "texts" / "en_US.lang", names)
    _append_language(RP / "texts" / "zh_CN.lang", names)

    catalog = _load(BP / "item_catalog" / "crafting_item_catalog.json")
    items = catalog["minecraft:crafting_items_catalog"]["categories"][0]["groups"][0]["items"]
    for identifier in list(ITEMS) + list(ARMOR) + list(SOLID_BLOCKS):
        value = "tf_slice:%s" % identifier
        if value not in items:
            items.append(value)
    _write(BP / "item_catalog" / "crafting_item_catalog.json", catalog)

    for loot_id, document in _stronghold_loot_tables().items():
        _write(
            BP / "loot_tables" / "chests" / "tf_slice" / (loot_id + ".json"),
            document,
        )
    build_localization(ROOT)
    normalize_creative_catalog(ROOT)
    build_route_models("knight")
    return {
        "blocks": sorted(SOLID_BLOCKS),
        "items": sorted(set(ITEMS) | set(ARMOR)),
        "entities": sorted(set(ENTITY_STATS) | set(PROJECTILES)),
    }


if __name__ == "__main__":
    result = build()
    print(
        "built %d Knight Stronghold blocks, %d items and %d entities"
        % (len(result["blocks"]), len(result["items"]), len(result["entities"]))
    )
