#!/usr/bin/env python3
"""Build Dark Tower mechanisms, route items and tower inhabitants."""

from __future__ import print_function

import hashlib
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from build_phantom_urghast_models import build as build_route_models
from build_creative_catalog import normalize_creative_catalog
from build_localization import build_localization


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
UPSTREAM = ROOT.parent / "twilightforest-1.20.1-4.3.2508-extracted" / "00_original_tree" / "assets" / "twilightforest"

BLOCK_TEXTURES = {
    "towerwood": "block/towerwood.png",
    "cracked_towerwood": "block/cracked_towerwood.png",
    "mossy_towerwood": "block/mossy_towerwood.png",
    "infested_towerwood": "block/infested_towerwood.png",
    "encased_towerwood": "block/encased_towerwood.png",
    "vanishing_block": "block/towerdev_vanish_off.png",
    "unbreakable_vanishing_block": "block/towerdev_vanish_off.png",
    "locked_vanishing_block": "block/towerdev_vanish_on.png",
    "reappearing_block": "block/towerdev_reappearing_off.png",
    "carminite_builder": "block/towerdev_builder_off.png",
    "carminite_antibuilder": "block/towerdev_antibuilder.png",
    "temporary_builder_block": "block/towerdev_built_off.png",
    "restored_block": "block/towerwood.png",
    "carminite_reactor": "block/towerdev_reactor_off.png",
    "reactor_debris": None,
    "fake_gold": None,
    "fake_diamond": None,
    "ghast_trap": "block/towerdev_ghasttrap_off.png",
    "carminite_block": "block/carminite_block.png",
    "experiment_115": "block/experiment115/experiment115_top.png",
    "tower_key_door": "block/towerdev_lock_on.png",
    "ur_ghast_boss_spawner": "block/boss_spawner.png",
}
INTERNAL_BLOCKS = frozenset()
REACTOR_ACTIVE_TEXTURE = "block/towerdev_reactor_on.png"
REAPPEARING_ACTIVE_TEXTURE = "block/towerdev_reappearing_on.png"
REAPPEARING_TRACE_OFF_TEXTURE = (
    "block/towerdev_reappearing_trace_off.png"
)
REAPPEARING_TRACE_ON_TEXTURE = (
    "block/towerdev_reappearing_trace_on.png"
)
BUILDER_ACTIVE_TEXTURE = "block/towerdev_builder_on.png"
BUILDER_TIMEOUT_TEXTURE = "block/towerdev_builder_timeout.png"
BUILT_ACTIVE_TEXTURE = "block/towerdev_built_on.png"
TOWER_KEY_DOOR_UNLOCKED_TEXTURE = "block/towerdev_lock_off.png"
VANILLA_TEXTURES = {
    "fake_gold": "textures/blocks/gold_block",
    "fake_diamond": "textures/blocks/diamond_block",
}
ITEMS = {
    "tower_key": (64, False),
    "carminite": (64, False),
    "fiery_tears": (64, False),
    "charm_of_life_1": (1, False),
    "ur_ghast_banner": (16, False),
}
ENTITY_STATS = {
    "carminite_golem": (40, 9, 0.25, 1.4, 2.7, "model/carminitegolem.png"),
    "tower_broodling": (7, 4, 0.3, 0.7, 0.5, "model/towerbroodling.png"),
    "mini_ghast": (10, 4, 0.25, 1.0, 1.0, "model/towerghast.png"),
    "tower_ghast": (30, 6, 0.25, 2.0, 2.0, "model/towerghast.png"),
    "towerwood_borer": (15, 5, 0.25, 0.6, 0.4, "model/towertermite.png"),
    "ur_ghast": (250, 16, 0.3, 14.0, 18.0, "model/towerghast.png"),
}
MINI_GHAST_HOVER = {
    "priority": 7,
    "xz_dist": 4,
    "y_dist": 4,
    "y_offset": 0,
    "interval": 1,
}
MINI_GHAST_BOSS_MINION_HOVER = {
    "priority": 7,
    "xz_dist": 1,
    "y_dist": 1,
    "y_offset": 0,
    "interval": 4,
}
TOWER_GHAST_HOVER = {
    "priority": 7,
    "xz_dist": 12,
    "y_dist": 8,
    "y_offset": 4,
    "interval": 1,
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reappearing_trace_geometry_document():
    faces = {
        face: {
            "uv": [6, 6],
            "uv_size": [4, 4],
            "material_instance": "*",
        }
        for face in ("north", "south", "east", "west", "up", "down")
    }
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": "geometry.tf_slice.reappearing_trace",
                    "texture_width": 16,
                    "texture_height": 16,
                    "visible_bounds_width": 2,
                    "visible_bounds_height": 2,
                    "visible_bounds_offset": [0, 0.5, 0],
                },
                "bones": [
                    {
                        "name": "block",
                        "pivot": [0, 8, 0],
                        "cubes": [
                            {
                                "origin": [-2, 6, -2],
                                "size": [4, 4, 4],
                                "uv": faces,
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _reappearing_trace_components(texture):
    return {
        "minecraft:geometry": "geometry.tf_slice.reappearing_trace",
        "minecraft:material_instances": {
            "*": {
                "texture": "tf_slice:" + texture,
                "render_method": "alpha_test",
                "ambient_occlusion": False,
                "face_dimming": False,
            }
        },
        "minecraft:collision_box": False,
        "minecraft:selection_box": {
            "origin": [-2, 6, -2],
            "size": [4, 4, 4],
        },
        "minecraft:light_dampening": 0,
        "netease:aabb": {
            "collision": {
                "min": [0.0, 0.0, 0.0],
                "max": [0.0, 0.0, 0.0],
            },
            "clip": {
                "min": [0.375, 0.375, 0.375],
                "max": [0.625, 0.625, 0.625],
            },
        },
        "netease:render_layer": {"value": "optionalAlpha"},
        "netease:no_crop_face_block": {},
        "netease:solid": {"value": False},
        "netease:pathable": {"value": True},
    }


def build_reactor_debris_texture(target):
    """Bake a local, opaque debris texture instead of a missing engine alias."""
    source = UPSTREAM / "textures" / "block" / "towerwood.png"
    image = Image.open(str(source)).convert("RGBA")
    if image.size != (16, 16):
        image = image.resize((16, 16), Image.Resampling.NEAREST)

    pixels = image.load()
    for y_value in range(16):
        for x_value in range(16):
            red, green, blue, alpha = pixels[x_value, y_value]
            noise = ((x_value * 13 + y_value * 7) % 19) - 9
            pixels[x_value, y_value] = (
                max(14, min(255, int(red * 0.52) + 34 + noise)),
                max(10, min(255, int(green * 0.34) + 10 + noise // 2)),
                max(12, min(255, int(blue * 0.38) + 18 + noise // 3)),
                alpha,
            )

    draw = ImageDraw.Draw(image)
    # Deterministic charred fractures remain legible at the native 16 px scale.
    cracks = (
        [(0, 3), (3, 4), (5, 7), (8, 6), (10, 10), (15, 12)],
        [(5, 0), (6, 3), (5, 7), (3, 10), (4, 15)],
        [(15, 2), (12, 4), (10, 7), (8, 9), (7, 15)],
    )
    for points in cracks:
        draw.line(points, fill=(22, 8, 12, 255), width=2)
        draw.line(points, fill=(78, 18, 24, 255), width=1)
    draw.point(((5, 7), (10, 7), (8, 9)), fill=(245, 74, 32, 255))

    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(target), format="PNG", optimize=False)


def block_document(identifier):
    if identifier == "encased_towerwood":
        # This block is shared with the already-shipped Fire Swamp acquisition
        # closure. Dark Tower generation may reuse it but must not change its
        # public mining/explosion contract.
        return {
            "format_version": "1.20.60",
            "minecraft:block": {
                "description": {
                    "identifier": "tf_slice:encased_towerwood",
                    "register_to_creative_menu": True,
                },
                "components": {
                    "minecraft:destructible_by_mining": {"seconds_to_destroy": 40.0},
                    "minecraft:destructible_by_explosion": {"explosion_resistance": 6.0},
                    "netease:render_layer": {"value": "opaque"},
                    "netease:solid": {"value": True},
                    "netease:pathable": {"value": False},
                },
            },
        }
    unbreakable = identifier in (
        "unbreakable_vanishing_block",
        "locked_vanishing_block",
        "temporary_builder_block",
        "tower_key_door",
        "ur_ghast_boss_spawner",
    )
    states = {}
    if identifier in ("vanishing_block", "unbreakable_vanishing_block", "locked_vanishing_block", "reappearing_block"):
        states = {"tf_slice:active": [False, True], "tf_slice:vanished": [False, True]}
    elif identifier == "experiment_115":
        states = {"tf_slice:servings": list(range(1, 9)), "tf_slice:regenerate": [False, True]}
    elif identifier == "carminite_builder":
        # Keep the legacy bool so already-generated blocks remain loadable;
        # the source-equivalent visual lifecycle uses the explicit enum.
        states = {
            "tf_slice:active": [False, True],
            "tf_slice:builder_state": ["inactive", "active", "timeout"],
        }
    elif identifier == "temporary_builder_block":
        states = {"tf_slice:active": [False, True]}
    elif identifier in ("carminite_reactor", "ghast_trap"):
        states = {"tf_slice:active": [False, True]}
    elif identifier == "tower_key_door":
        states = {"tf_slice:locked": [True, False]}
    description = {
        "identifier": "tf_slice:%s" % identifier,
        "register_to_creative_menu": (
            identifier != "temporary_builder_block"
        ),
    }
    if states:
        description["states"] = states
    render_method = "blend" if identifier == "temporary_builder_block" else "opaque"
    components = {
        "minecraft:geometry": "geometry.tf_slice.courtyard_cube",
        "minecraft:material_instances": {
            "*": {
                "texture": "tf_slice:%s" % identifier,
                "render_method": render_method,
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
        "netease:render_layer": {"value": render_method},
        "netease:solid": {"value": True},
        "netease:pathable": {"value": False},
    }
    if unbreakable:
        components["minecraft:destructible_by_mining"] = False
        components["minecraft:destructible_by_explosion"] = False
    else:
        components["minecraft:destructible_by_mining"] = {"seconds_to_destroy": 4.0}
        components["minecraft:destructible_by_explosion"] = {"explosion_resistance": 10.0}
    if identifier == "ghast_trap":
        components["minecraft:destructible_by_explosion"] = False
    if identifier in (
        "vanishing_block", "unbreakable_vanishing_block", "locked_vanishing_block",
        "reappearing_block", "carminite_builder", "carminite_antibuilder",
        "carminite_reactor", "ghast_trap", "experiment_115", "tower_key_door",
        "ur_ghast_boss_spawner",
    ):
        components["netease:block_entity"] = {"tick": True, "movable": False}
    if identifier in (
        "vanishing_block",
        "unbreakable_vanishing_block",
        "reappearing_block",
        "carminite_builder",
        "carminite_reactor",
        "ghast_trap",
    ):
        components["netease:neighborchanged_sendto_script"] = {"value": True}
    block = {"description": description, "components": components}
    if identifier == "reappearing_block":
        block["permutations"] = [
            {
                "condition": (
                    "query.block_state('tf_slice:active') == true && "
                    "query.block_state('tf_slice:vanished') == false"
                ),
                "components": {
                    "minecraft:material_instances": {
                        "*": {
                            "texture": "tf_slice:reappearing_block_active",
                            "render_method": "opaque",
                        }
                    }
                },
            },
            {
                "condition": (
                    "query.block_state('tf_slice:vanished') == true && "
                    "query.block_state('tf_slice:active') == false"
                ),
                "components": _reappearing_trace_components(
                    "reappearing_trace_off"
                ),
            },
            {
                "condition": (
                    "query.block_state('tf_slice:vanished') == true && "
                    "query.block_state('tf_slice:active') == true"
                ),
                "components": _reappearing_trace_components(
                    "reappearing_trace_on"
                ),
            },
        ]
    elif identifier == "carminite_builder":
        block["permutations"] = [
            {
                "condition": (
                    "query.block_state('tf_slice:builder_state') == 'active'"
                ),
                "components": {
                    "minecraft:material_instances": {
                        "*": {
                            "texture": "tf_slice:carminite_builder_active",
                            "render_method": "opaque",
                        }
                    }
                },
            },
            {
                "condition": (
                    "query.block_state('tf_slice:builder_state') == 'timeout'"
                ),
                "components": {
                    "minecraft:material_instances": {
                        "*": {
                            "texture": "tf_slice:carminite_builder_timeout",
                            "render_method": "opaque",
                        }
                    }
                },
            },
        ]
    elif identifier == "temporary_builder_block":
        block["permutations"] = [
            {
                "condition": (
                    "query.block_state('tf_slice:active') == true"
                ),
                "components": {
                    "minecraft:material_instances": {
                        "*": {
                            "texture": "tf_slice:temporary_builder_block_active",
                            "render_method": "blend",
                        }
                    }
                },
            }
        ]
    elif identifier == "carminite_reactor":
        block["permutations"] = [
            {
                "condition": (
                    "query.block_state('tf_slice:active') == true"
                ),
                "components": {
                    "minecraft:material_instances": {
                        "*": {
                            "texture": "tf_slice:carminite_reactor_active",
                            "render_method": "opaque",
                        }
                    }
                },
            }
        ]
    elif identifier == "tower_key_door":
        block["permutations"] = [
            {
                "condition": (
                    "query.block_state('tf_slice:locked') == false"
                ),
                "components": {
                    "minecraft:material_instances": {
                        "*": {
                            "texture": "tf_slice:tower_key_door_unlocked",
                            "render_method": "opaque",
                        }
                    }
                },
            }
        ]
    return {"format_version": "1.20.60", "minecraft:block": block}


def item_document(identifier, stack_size):
    components = {
        "minecraft:display_name": {"value": "item.tf_slice:%s.name" % identifier},
        "minecraft:icon": {
            "textures": {"default": "tf_slice:%s" % identifier}
        },
        "minecraft:max_stack_size": stack_size,
    }
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


def ur_ghast_fireball_document():
    return {
        "format_version": "1.20.60",
        "minecraft:entity": {
            "description": {
                "identifier": "tf_slice:ur_ghast_fireball",
                "is_spawnable": False,
                "is_summonable": True,
                "is_experimental": False,
            },
            "components": {
                "minecraft:type_family": {
                    "family": [
                        "ur_ghast_fireball", "projectile", "monster", "mob"
                    ]
                },
                "minecraft:nameable": {},
                "minecraft:health": {"value": 1, "max": 1},
                "minecraft:damage_sensor": {
                    "triggers": [
                        {"cause": "all", "deals_damage": False}
                    ]
                },
                "minecraft:movement": {"value": 0},
                "minecraft:collision_box": {"width": 1.0, "height": 1.0},
                "minecraft:physics": {"has_gravity": False},
                "minecraft:pushable": {
                    "is_pushable": False,
                    "is_pushable_by_piston": False,
                },
                "minecraft:fire_immune": {},
                "minecraft:projectile": {
                    "power": 0.0,
                    "gravity": 0.0,
                    "uncertainty_base": 0.0,
                    "anchor": 1,
                    "on_hit": {
                        "impact_damage": {
                            "damage": 0,
                            "knockback": False,
                            "semi_random_diff_damage": False,
                        }
                    },
                },
            },
            "component_groups": {
                "tf_slice:explode": {
                    "minecraft:explode": {
                        "fuse_length": 0.0,
                        "fuse_lit": True,
                        "power": 1,
                        "breaks_blocks": False,
                        "causes_fire": False,
                    }
                }
            },
            "events": {
                "tf_slice:explode": {
                    "add": {"component_groups": ["tf_slice:explode"]}
                }
            },
        },
    }


def ur_ghast_fireball_client_document():
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": "tf_slice:ur_ghast_fireball",
                "materials": {"default": "fireball"},
                "textures": {"default": "textures/items/fireball"},
                "geometry": {"default": "geometry.fireball"},
                "animations": {"face_player": "animation.actor.billboard"},
                "scripts": {"animate": ["face_player"], "scale": "2.0"},
                "render_controllers": ["controller.render.fireball"],
            }
        },
    }


def hostile_entity(identifier, stats):
    health, damage, movement, width, height, _texture = stats
    flying = identifier in ("mini_ghast", "tower_ghast", "ur_ghast")
    description = {"identifier": "tf_slice:%s" % identifier, "is_spawnable": True, "is_summonable": True, "is_experimental": False}
    events = {}
    component_groups = {}
    if identifier in ("mini_ghast", "tower_ghast"):
        description["properties"] = {
            "tf_slice:charging": {
                "type": "bool", "default": False, "client_sync": True,
            },
        }
        events = {
            "tf_slice:start_charging": {
                "set_property": {"tf_slice:charging": True}
            },
            "tf_slice:stop_charging": {
                "set_property": {"tf_slice:charging": False}
            },
        }
    if identifier == "ur_ghast":
        description["properties"] = {
            "tf_slice:attack_state": {
                "type": "float", "range": [0.0, 2.0],
                "default": 0.0, "client_sync": True,
            },
            "tf_slice:hurt_flash": {
                "type": "float", "range": [0.0, 1.0],
                "default": 0.0, "client_sync": True,
            },
            "tf_slice:visual_pitch": {
                "type": "float", "range": [-90.0, 90.0],
                "default": 0.0, "client_sync": True,
            },
        }
        events = {
            "tf_slice:attack_normal": {
                "set_property": {"tf_slice:attack_state": 0.0}
            },
            "tf_slice:attack_tracking": {
                "set_property": {"tf_slice:attack_state": 1.0}
            },
            "tf_slice:attack_charging": {
                "set_property": {"tf_slice:attack_state": 2.0}
            },
            "tf_slice:hurt_on": {
                "set_property": {"tf_slice:hurt_flash": 1.0}
            },
            "tf_slice:hurt_off": {
                "set_property": {"tf_slice:hurt_flash": 0.0}
            },
            "tf_slice:visual_pitch_down": {
                "set_property": {"tf_slice:visual_pitch": 90.0}
            },
            "tf_slice:visual_pitch_reset": {
                "set_property": {"tf_slice:visual_pitch": 0.0}
            },
        }
    elif identifier == "mini_ghast":
        description["properties"]["tf_slice:boss_minion"] = {
            "type": "bool", "default": False, "client_sync": True,
        }
        component_groups["tf_slice:boss_minion"] = {
            "minecraft:health": {"value": 6, "max": 6},
            "minecraft:movement": {"value": 0.05},
            "minecraft:behavior.random_hover": dict(
                MINI_GHAST_BOSS_MINION_HOVER
            ),
        }
        events["tf_slice:make_boss_minion"] = {
            "add": {"component_groups": ["tf_slice:boss_minion"]},
            "set_property": {"tf_slice:boss_minion": True},
        }
    components = {
        "minecraft:type_family": {"family": [identifier, "dark_tower", "monster", "mob"]},
        "minecraft:nameable": {},
        "minecraft:health": {"value": health, "max": health},
        "minecraft:attack": {"damage": damage},
        "minecraft:movement": {"value": movement},
        "minecraft:collision_box": {"width": width, "height": height},
        "minecraft:physics": {"has_gravity": not flying},
        "minecraft:pushable": {"is_pushable": not flying, "is_pushable_by_piston": False},
        ("minecraft:movement.fly" if flying else "minecraft:movement.basic"): {},
        ("minecraft:navigation.fly" if flying else "minecraft:navigation.walk"): {
            "can_path_from_air": flying,
            "can_path_over_water": True,
            "avoid_water": True,
            "avoid_damage_blocks": True,
        },
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 2,
            "must_see": True,
            "entity_types": [{"filters": {"test": "is_family", "subject": "other", "value": "player"}, "max_dist": 128 if identifier == "ur_ghast" else (16 if identifier == "tower_broodling" else 64)}],
        },
    }
    if identifier == "ur_ghast":
        components["minecraft:persistent"] = {}
    else:
        components["minecraft:despawn"] = {"despawn_from_distance": {}}
    if identifier == "ur_ghast":
        components.pop("minecraft:behavior.hurt_by_target", None)
        components.pop("minecraft:behavior.nearest_attackable_target", None)
        components["minecraft:physics"]["has_collision"] = False
        components["minecraft:fire_immune"] = {}
        components["minecraft:custom_hit_test"] = {
            "hitboxes": [
                {"width": 12.5, "height": 12.5, "pivot": [0, 12.5, 0]}
            ]
        }
    if not flying:
        components.update({
            "minecraft:jump.static": {},
            "minecraft:behavior.melee_attack": {"priority": 4, "speed_multiplier": 1.0, "track_target": True},
            "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.8},
            "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 8.0, "probability": 0.04},
            "minecraft:behavior.random_look_around": {"priority": 8},
        })
        if identifier == "tower_broodling":
            components["minecraft:behavior.leap_at_target"] = {"priority": 3, "yd": 0.4}
            components["minecraft:can_climb"] = {}
        elif identifier == "carminite_golem":
            components["minecraft:armor"] = {"value": 2}
            components["minecraft:behavior.random_stroll"]["speed_multiplier"] = 1.0
            components["minecraft:behavior.look_at_player"]["look_distance"] = 6.0
    elif identifier == "mini_ghast":
        components.update({
            "minecraft:behavior.random_hover": dict(MINI_GHAST_HOVER),
        })
    elif identifier == "tower_ghast":
        components.update({
            "minecraft:behavior.random_hover": dict(TOWER_GHAST_HOVER),
        })
    entity = {
        "description": description,
        "components": components,
        "events": events,
    }
    if component_groups:
        entity["component_groups"] = component_groups
    return {
        "format_version": "1.20.60",
        "minecraft:entity": entity,
    }


def client_entity(identifier):
    from build_phantom_urghast_models import client_entity as route_client_entity
    return route_client_entity(identifier)


def append_language(path, mapping):
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    lines = [line for line in lines if not any(line.startswith(key + "=") for key in mapping)]
    lines.extend("%s=%s" % item for item in mapping.items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_reappearing_block_resources():
    """Rebuild only the reappearing block's state visuals and atlases."""
    block_path = BP / "netease_blocks" / "reappearing_block.json"
    geometry_path = (
        RP / "models" / "blocks" / "reappearing_trace.geo.json"
    )
    terrain_path = RP / "textures" / "terrain_texture.json"
    legacy_path = RP / "blocks.json"
    texture_sources = {
        "reappearing_block": BLOCK_TEXTURES["reappearing_block"],
        "reappearing_block_active": REAPPEARING_ACTIVE_TEXTURE,
        "reappearing_trace_off": REAPPEARING_TRACE_OFF_TEXTURE,
        "reappearing_trace_on": REAPPEARING_TRACE_ON_TEXTURE,
    }

    write(block_path, block_document("reappearing_block"))
    write(geometry_path, reappearing_trace_geometry_document())
    terrain = load(terrain_path)
    files = [block_path, geometry_path]
    for identifier, source in texture_sources.items():
        target = RP / "textures" / "blocks" / (identifier + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(UPSTREAM / "textures" / source), str(target))
        terrain["texture_data"]["tf_slice:" + identifier] = {
            "textures": "textures/blocks/" + identifier
        }
        files.append(target)
    write(terrain_path, terrain)

    legacy = load(legacy_path)
    legacy["tf_slice:reappearing_block"] = {
        "textures": "tf_slice:reappearing_block",
        "sound": "stone",
    }
    write(legacy_path, legacy)
    files.extend((terrain_path, legacy_path))
    return {"files": files}


def build_mini_ghast_behavior():
    """Rebuild only the mini-ghast behavior document."""
    target = BP / "entities" / "mini_ghast.entity.json"
    write(
        target,
        hostile_entity("mini_ghast", ENTITY_STATS["mini_ghast"]),
    )
    return {"files": [target]}


def build_carminite_reactor_resources():
    """Rebuild only the reactor-owned block, textures, and atlas entries."""
    block_path = BP / "netease_blocks" / "carminite_reactor.json"
    off_texture = RP / "textures" / "blocks" / "carminite_reactor.png"
    active_texture = (
        RP / "textures" / "blocks" / "carminite_reactor_active.png"
    )
    terrain_path = RP / "textures" / "terrain_texture.json"
    legacy_path = RP / "blocks.json"

    write(block_path, block_document("carminite_reactor"))
    off_texture.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        str(UPSTREAM / "textures" / BLOCK_TEXTURES["carminite_reactor"]),
        str(off_texture),
    )
    shutil.copy2(
        str(UPSTREAM / "textures" / REACTOR_ACTIVE_TEXTURE),
        str(active_texture),
    )

    terrain = load(terrain_path)
    terrain["texture_data"]["tf_slice:carminite_reactor"] = {
        "textures": "textures/blocks/carminite_reactor"
    }
    terrain["texture_data"]["tf_slice:carminite_reactor_active"] = {
        "textures": "textures/blocks/carminite_reactor_active"
    }
    write(terrain_path, terrain)

    legacy = load(legacy_path)
    legacy["tf_slice:carminite_reactor"] = {
        "textures": "tf_slice:carminite_reactor",
        "sound": "stone",
    }
    write(legacy_path, legacy)
    return {
        "files": [
            block_path,
            off_texture,
            active_texture,
            terrain_path,
            legacy_path,
        ]
    }


def build_carminite_builder_resources():
    """Rebuild only builder-owned blocks, source textures, and atlas entries."""
    terrain_path = RP / "textures" / "terrain_texture.json"
    legacy_path = RP / "blocks.json"
    terrain = load(terrain_path)
    legacy = load(legacy_path)
    texture_sources = {
        "carminite_builder": BLOCK_TEXTURES["carminite_builder"],
        "carminite_builder_active": BUILDER_ACTIVE_TEXTURE,
        "carminite_builder_timeout": BUILDER_TIMEOUT_TEXTURE,
        "temporary_builder_block": BLOCK_TEXTURES["temporary_builder_block"],
        "temporary_builder_block_active": BUILT_ACTIVE_TEXTURE,
    }
    files = []
    for identifier in ("carminite_builder", "temporary_builder_block"):
        block_path = BP / "netease_blocks" / (identifier + ".json")
        write(block_path, block_document(identifier))
        files.append(block_path)
    for identifier, source in texture_sources.items():
        target = RP / "textures" / "blocks" / (identifier + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            str(UPSTREAM / "textures" / source),
            str(target),
        )
        terrain["texture_data"]["tf_slice:" + identifier] = {
            "textures": "textures/blocks/" + identifier
        }
        files.append(target)
    for identifier in ("carminite_builder", "temporary_builder_block"):
        legacy["tf_slice:" + identifier] = {
            "textures": "tf_slice:" + identifier,
            "sound": "stone",
        }
    write(terrain_path, terrain)
    write(legacy_path, legacy)
    files.extend((terrain_path, legacy_path))
    return {"files": files}


def remove_tower_interior_guard_resources():
    """Remove every generated resource owned by the retired guard block."""
    block_path = BP / "netease_blocks" / "tower_interior_guard.json"
    texture_path = (
        RP / "textures" / "blocks" / "tower_interior_guard.png"
    )
    terrain_path = RP / "textures" / "terrain_texture.json"
    legacy_path = RP / "blocks.json"

    for retired_path in (block_path, texture_path):
        if retired_path.exists():
            retired_path.unlink()

    terrain = load(terrain_path)
    terrain.get("texture_data", {}).pop(
        "tf_slice:tower_interior_guard",
        None,
    )
    write(terrain_path, terrain)

    legacy = load(legacy_path)
    legacy.pop("tf_slice:tower_interior_guard", None)
    write(legacy_path, legacy)
    return {
        "files": [block_path, texture_path, terrain_path, legacy_path]
    }


def build():
    build_reappearing_block_resources()
    terrain = load(RP / "textures" / "terrain_texture.json")
    legacy = load(RP / "blocks.json")
    for identifier, source in BLOCK_TEXTURES.items():
        write(BP / "netease_blocks" / (identifier + ".json"), block_document(identifier))
        key = "tf_slice:%s" % identifier
        if source:
            target = RP / "textures" / "blocks" / (identifier + ".png")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(UPSTREAM / "textures" / source), str(target))
            texture = "textures/blocks/%s" % identifier
            if identifier == "carminite_reactor":
                active_target = (
                    RP
                    / "textures"
                    / "blocks"
                    / "carminite_reactor_active.png"
                )
                shutil.copy2(
                    str(UPSTREAM / "textures" / REACTOR_ACTIVE_TEXTURE),
                    str(active_target),
                )
                terrain["texture_data"][
                    "tf_slice:carminite_reactor_active"
                ] = {
                    "textures": "textures/blocks/carminite_reactor_active"
                }
            elif identifier == "carminite_builder":
                for suffix, source_texture in (
                    ("active", BUILDER_ACTIVE_TEXTURE),
                    ("timeout", BUILDER_TIMEOUT_TEXTURE),
                ):
                    extra_identifier = "carminite_builder_" + suffix
                    extra_target = (
                        RP / "textures" / "blocks" / (extra_identifier + ".png")
                    )
                    shutil.copy2(
                        str(UPSTREAM / "textures" / source_texture),
                        str(extra_target),
                    )
                    terrain["texture_data"]["tf_slice:" + extra_identifier] = {
                        "textures": "textures/blocks/" + extra_identifier
                    }
            elif identifier == "temporary_builder_block":
                active_identifier = "temporary_builder_block_active"
                active_target = (
                    RP / "textures" / "blocks" / (active_identifier + ".png")
                )
                shutil.copy2(
                    str(UPSTREAM / "textures" / BUILT_ACTIVE_TEXTURE),
                    str(active_target),
                )
                terrain["texture_data"]["tf_slice:" + active_identifier] = {
                    "textures": "textures/blocks/" + active_identifier
                }
            elif identifier == "tower_key_door":
                unlocked_identifier = "tower_key_door_unlocked"
                unlocked_target = (
                    RP
                    / "textures"
                    / "blocks"
                    / (unlocked_identifier + ".png")
                )
                shutil.copy2(
                    str(
                        UPSTREAM
                        / "textures"
                        / TOWER_KEY_DOOR_UNLOCKED_TEXTURE
                    ),
                    str(unlocked_target),
                )
                terrain["texture_data"][
                    "tf_slice:" + unlocked_identifier
                ] = {
                    "textures": "textures/blocks/" + unlocked_identifier
                }
        elif identifier == "reactor_debris":
            target = RP / "textures" / "blocks" / "reactor_debris.png"
            build_reactor_debris_texture(target)
            texture = "textures/blocks/reactor_debris"
        else:
            texture = VANILLA_TEXTURES[identifier]
        terrain["texture_data"][key] = {"textures": texture}
        legacy[key] = {"textures": key, "sound": "wood" if "towerwood" in identifier else "stone"}
    write(RP / "textures" / "terrain_texture.json", terrain)
    write(RP / "blocks.json", legacy)

    atlas = load(RP / "textures" / "item_texture.json")
    for identifier, (stack, _unused) in ITEMS.items():
        write(BP / "items" / (identifier + ".item.json"), item_document(identifier, stack))
        source_name = identifier
        source = UPSTREAM / "textures" / "item" / (source_name + ".png")
        if identifier == "ur_ghast_banner":
            source = UPSTREAM / "textures" / "entity" / "banner" / "ur_ghast.png"
        target = RP / "textures" / "items" / (identifier + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(target))
        atlas["texture_data"]["tf_slice:%s" % identifier] = {"textures": "textures/items/%s" % identifier}
    write(RP / "textures" / "item_texture.json", atlas)

    catalog = load(BP / "item_catalog" / "crafting_item_catalog.json")
    catalog_items = catalog["minecraft:crafting_items_catalog"]["categories"][0]["groups"][0]["items"]
    public_blocks = [
        identifier
        for identifier in BLOCK_TEXTURES
        if identifier not in INTERNAL_BLOCKS
    ]
    for identifier in list(ITEMS) + public_blocks:
        value = "tf_slice:%s" % identifier
        if value not in catalog_items:
            catalog_items.append(value)
    write(BP / "item_catalog" / "crafting_item_catalog.json", catalog)

    evidence = []
    for identifier, stats in ENTITY_STATS.items():
        write(BP / "entities" / (identifier + ".entity.json"), hostile_entity(identifier, stats))
        write(RP / "entity" / (identifier + ".entity.json"), client_entity(identifier))
        source = UPSTREAM / "textures" / stats[-1]
        target = RP / "textures" / "entity" / "tf_slice" / (identifier + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(target))
        evidence.append({
            "identifier": "tf_slice:%s" % identifier,
            "status": "rejected" if identifier == "ur_ghast" else "candidate",
            "textureSha256": hashlib.sha256(source.read_bytes()).hexdigest().upper(),
            "requiredViews": [
                "front", "back", "left", "right", "top", "three_quarter",
            ],
            "requiredPoses": [
                "rest", "walk_extreme", "look_up", "look_down",
            ],
            "offlineEvidence": {"status": "missing", "files": []},
        })
    write(
        BP / "entities" / "ur_ghast_fireball.entity.json",
        ur_ghast_fireball_document(),
    )
    write(
        RP / "entity" / "ur_ghast_fireball.entity.json",
        ur_ghast_fireball_client_document(),
    )
    write(ROOT / "evidence" / "models" / "dark_tower_route.json", {
        "status": "rejected", "offlineEvidenceComplete": False,
        "clientAccepted": False, "runtimeVerified": False,
        "blockingReason": (
            "Source-specific geometry, animations, and rendered six-view/four-pose "
            "PNG evidence have not passed the offline model gate."
        ),
        "sourceVersion": "1.20.1-4.3.2508", "models": evidence,
    })

    write(BP / "loot_tables" / "chests" / "tf_slice" / "dark_tower_cache.json", {
        "pools": [{"rolls": {"min": 2, "max": 4}, "entries": [
            {"type": "item", "name": "tf_slice:carminite", "weight": 10},
            {"type": "item", "name": "tf_slice:tower_key", "weight": 4},
            {"type": "item", "name": "tf_slice:charm_of_life_1", "weight": 1},
            {"type": "item", "name": "tf_slice:experiment_115", "weight": 4},
        ]}]})
    write(BP / "loot_tables" / "chests" / "tf_slice" / "dark_tower_key.json", {
        "pools": [{"rolls": 1, "entries": [{"type": "item", "name": "tf_slice:tower_key", "weight": 1}]}]})
    write(BP / "loot_tables" / "chests" / "tf_slice" / "ur_ghast_reward.json", {
        "pools": [{"rolls": 1, "entries": [
            {"type": "item", "name": "tf_slice:carminite", "functions": [{"function": "set_count", "count": {"min": 5, "max": 9}}]},
            {"type": "item", "name": "tf_slice:fiery_tears"},
            {"type": "item", "name": "tf_slice:ur_ghast_trophy"},
            {"type": "item", "name": "tf_slice:ur_ghast_banner"},
        ]}]})
    write(BP / "recipes" / "fiery_ingot_from_tears.recipe.json", {
        "format_version": "1.20.10",
        "minecraft:recipe_shapeless": {
            "description": {"identifier": "tf_slice:fiery_ingot_from_tears"},
            "tags": ["crafting_table"],
            "ingredients": [
                {"item": "tf_slice:fiery_tears"},
                {"item": "minecraft:iron_ingot"},
            ],
            "unlock": {"context": "AlwaysUnlocked"},
            "result": {"item": "tf_slice:fiery_ingot", "count": 1},
        },
    })

    names = {}
    for identifier in ITEMS:
        names["item.tf_slice:%s.name" % identifier] = identifier.replace("_", " ").title()
    for identifier in public_blocks:
        names["tile.tf_slice:%s.name" % identifier] = identifier.replace("_", " ").title()
    for identifier in ENTITY_STATS:
        display = identifier.replace("_", " ").title()
        names["entity.tf_slice:%s.name" % identifier] = display
        names["item.spawn_egg.entity.tf_slice:%s.name" % identifier] = display
    names["entity.tf_slice:ur_ghast_fireball.name"] = "Ur-Ghast Fireball"
    append_language(RP / "texts" / "en_US.lang", names)
    append_language(RP / "texts" / "zh_CN.lang", names)
    build_localization(ROOT)
    normalize_creative_catalog(ROOT)
    build_route_models("tower")
    return {"blocks": sorted(BLOCK_TEXTURES), "items": sorted(ITEMS), "entities": sorted(ENTITY_STATS)}


if __name__ == "__main__":
    if sys.argv[1:] == ["--reactor-only"]:
        result = build_carminite_reactor_resources()
        print("built %d reactor resources" % len(result["files"]))
    elif sys.argv[1:] == ["--reappearing-block-only"]:
        result = build_reappearing_block_resources()
        print(
            "built %d reappearing-block resources"
            % len(result["files"])
        )
    elif sys.argv[1:] == ["--mini-ghast-only"]:
        result = build_mini_ghast_behavior()
        print("built %d mini-ghast behavior resource" % len(result["files"]))
    elif sys.argv[1:] == ["--remove-interior-guard"]:
        result = remove_tower_interior_guard_resources()
        print("removed %d retired tower-guard resources" % len(result["files"]))
    elif sys.argv[1:]:
        raise SystemExit(
            "usage: build_dark_tower_content.py "
            "[--reactor-only|--reappearing-block-only|--mini-ghast-only|"
            "--remove-interior-guard]"
        )
    else:
        result = build()
        print(
            "built %d tower blocks, %d items and %d entities"
            % (
                len(result["blocks"]),
                len(result["items"]),
                len(result["entities"]),
            )
        )
