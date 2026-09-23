# -*- coding: utf-8 -*-
"""Build deterministic classic-branch models for the Labyrinth/Hydra route."""

from __future__ import print_function

import json
import math
import random
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
UPSTREAM = ROOT.parent / "twilightforest-1.20.1-4.3.2508-extracted" / "00_original_tree"
MODEL_TEXTURES = UPSTREAM / "assets" / "twilightforest" / "textures" / "model"
SNAPSHOT = ROOT / "model_acceptance" / "source_snapshots" / "hydra_route_models.json"
LABYRINTH_SOURCE = (
    ROOT / "model_acceptance" / "source_snapshots" / "labyrinth_entity_models.json"
)
GEOMETRY = RP / "models" / "entity" / "hydra_route.geo.json"
ANIMATIONS = RP / "animations" / "hydra_route.animation.json"
RENDER_CONTROLLERS = RP / "render_controllers" / "hydra_route.render.json"

JAR_SHA256 = "0BDC89263616D1B35C32EF82C5E9C14CBD20368E2FE8B468C72A28320BE7A778"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_json_mapping(path, keys, values):
    document = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    target = document
    for key in keys:
        target = target.setdefault(key, {})
    target.update(values)
    write_json(path, document)


def cube(origin, size, uv, mirror=False, inflate=None):
    result = {"origin": origin, "size": size, "uv": uv}
    if mirror:
        result["mirror"] = True
    if inflate is not None:
        result["inflate"] = inflate
    return result


def java_part(name, pivot, cubes=None, parent="root", rotation=None):
    """Locked Java ModelPart record before the Bedrock coordinate transform."""
    return {
        "name": name,
        "parent": parent,
        "pivot": list(pivot),
        "cubes": list(cubes or ()),
        "rotation": list(rotation or (0.0, 0.0, 0.0)),
    }


def clean_number(value):
    value = float(value)
    nearest = round(value)
    if abs(value - nearest) < 0.001:
        return int(nearest)
    return round(value, 6)


def convert_java_parts(parts):
    """Convert local Java pivots/cubes into Bedrock global pivots/cubes.

    Java uses Y-down ModelPart coordinates around the render origin. Bedrock
    uses Y-up geometry around the conventional 24-pixel entity baseline.
    Parent rotations remain hierarchical; only the unrotated pivot positions
    are accumulated here.
    """
    java_world_pivots = {"root": [0.0, 0.0, 0.0]}
    converted = []
    for part in parts:
        parent = part["parent"]
        parent_pivot = java_world_pivots[parent]
        world_pivot = [
            parent_pivot[axis] + float(part["pivot"][axis])
            for axis in range(3)
        ]
        java_world_pivots[part["name"]] = world_pivot
        bedrock_cubes = []
        for source in part["cubes"]:
            local_origin = source["origin"]
            size = source["size"]
            java_origin = [
                world_pivot[axis] + float(local_origin[axis])
                for axis in range(3)
            ]
            converted_cube = cube(
                [
                    clean_number(java_origin[0]),
                    clean_number(24.0 - (java_origin[1] + float(size[1]))),
                    clean_number(java_origin[2]),
                ],
                [clean_number(value) for value in size],
                list(source["uv"]),
                bool(source.get("mirror", False)),
                source.get("inflate"),
            )
            bedrock_cubes.append(converted_cube)
        java_rotation = part["rotation"]
        bedrock_rotation = [
            # Bedrock entity-bone pitch is opposite the right-handed helper
            # used for Java ModelPart matrices.  The Y-axis cube reflection
            # flips Java X rotation once; the engine convention flips it back,
            # so the stored X angle keeps the Java sign.
            clean_number(math.degrees(float(java_rotation[0]))),
            clean_number(math.degrees(float(java_rotation[1]))),
            clean_number(-math.degrees(float(java_rotation[2]))),
        ]
        converted.append(
            bone(
                part["name"],
                [
                    clean_number(world_pivot[0]),
                    clean_number(24.0 - world_pivot[1]),
                    clean_number(world_pivot[2]),
                ],
                bedrock_cubes,
                parent,
                bedrock_rotation if any(bedrock_rotation) else None,
            )
        )
    return converted


def _source_world_pivots(parts):
    by_name = dict((part["name"], part) for part in parts)
    resolved = {"root": [0.0, 0.0, 0.0]}

    def resolve(name):
        if name in resolved:
            return resolved[name]
        part = by_name[name]
        parent = resolve(part["parent"])
        resolved[name] = [
            parent[axis] + float(part["pivot"][axis])
            for axis in range(3)
        ]
        return resolved[name]

    for part in parts:
        resolve(part["name"])
    return resolved


def convert_locked_source_parts(parts):
    """Convert the hand-checked Java-local snapshot without sign guessing."""
    world_pivots = _source_world_pivots(parts)
    result = []
    for part in parts:
        world_pivot = world_pivots[part["name"]]
        cubes = []
        for source in part.get("cubes", ()):
            local = source["origin"]
            size = source["size"]
            converted = cube(
                [
                    clean_number(world_pivot[0] + float(local[0])),
                    clean_number(
                        24.0
                        - (
                            world_pivot[1]
                            + float(local[1])
                            + float(size[1])
                        )
                    ),
                    clean_number(world_pivot[2] + float(local[2])),
                ],
                [clean_number(value) for value in size],
                list(source["uv"]),
                bool(source.get("mirror", False)),
                source.get("inflate"),
            )
            cubes.append(converted)
        rotation = [
            clean_number(value)
            for value in part.get("rotation_degrees", (0, 0, 0))
        ]
        result.append(
            bone(
                part["name"],
                [
                    clean_number(world_pivot[0]),
                    clean_number(24.0 - world_pivot[1]),
                    clean_number(world_pivot[2]),
                ],
                cubes,
                part["parent"],
                rotation if any(rotation) else None,
            )
        )
    return result


def load_labyrinth_source():
    return json.loads(LABYRINTH_SOURCE.read_text(encoding="utf-8"))["models"]


def geometry_from_locked_source(identifier, extra_bones=()):
    source = load_labyrinth_source()[identifier]
    parts = source.get("parts")
    if parts is None:
        parts = []
        for layer_name in ("outer", "inner"):
            parts.extend(source["layers"][layer_name]["parts"])
    width, height = source["texture_size"]
    return geometry(
        identifier,
        width,
        height,
        convert_locked_source_parts(parts) + list(extra_bones),
        source["visible_bounds"],
    )


def bone(name, pivot, cubes=None, parent="root", rotation=None):
    result = {"name": name, "parent": parent, "pivot": pivot}
    if cubes:
        result["cubes"] = cubes
    if rotation:
        result["rotation"] = rotation
    return result


def geometry(identifier, width, height, bones, bounds, root_rotation=None):
    root = {"name": "root", "pivot": [0, 0, 0]}
    if root_rotation:
        root["rotation"] = list(root_rotation)
    return {
        "description": {
            "identifier": "geometry.tf_slice." + identifier,
            "texture_width": width,
            "texture_height": height,
            "visible_bounds_width": bounds[0],
            "visible_bounds_height": bounds[1],
            "visible_bounds_offset": bounds[2],
        },
        "bones": [root] + bones,
    }


def minotaur_geometry():
    return geometry_from_locked_source(
        "minotaur",
        ({
            "name": "rightItem",
            "parent": "rightArm",
            "pivot": [-6, 15, 1],
            "neverRender": True,
        },),
    )


def minoshroom_geometry():
    return geometry_from_locked_source(
        "minoshroom",
        ({
            "name": "rightItem",
            "parent": "rightArm",
            "pivot": [-6, 21, -8],
            "neverRender": True,
        },),
    )


def maze_slime_geometry():
    return geometry_from_locked_source("maze_slime")


def mosquito_geometry():
    rng = random.Random(0x4D4F5351)
    bones = [bone("core", [0, 16, 0], [cube([-0.5, 15.5, -0.5], [1, 1, 1], [0, 0])])]
    directions = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    for group_index, direction in enumerate(directions, 1):
        group_name = "group_%d" % group_index
        bones.append(bone(group_name, [direction[0] * 11, 16 + direction[1] * 11, direction[2] * 11], parent="core"))
        for bug_index in range(16):
            x = round((rng.random() - rng.random()) * 16, 4)
            y = round(16 + (rng.random() - rng.random()) * 16, 4)
            z = round((rng.random() - rng.random()) * 16, 4)
            bones.append(bone("bug_%d" % ((group_index - 1) * 16 + bug_index), [x, y, z], [cube([x - .5, y - .5, z - .5], [1, 1, 1], [rng.randrange(28), rng.randrange(28)])], group_name))
    return geometry("mosquito_swarm", 64, 64, bones, (3.5, 3.5, [0, 1.2, 0]))


def hydra_geometry():
    right_leg_cubes = [
        cube([-16, 0, -16], [32, 48, 32], [0, 136]),
        cube([-20, 40, -20], [8, 8, 8], [184, 200]),
        cube([-4, 40, -22], [8, 8, 8], [184, 200]),
        cube([12, 40, -20], [8, 8, 8], [184, 200]),
    ]
    left_leg_cubes = [
        cube(entry["origin"], entry["size"], entry["uv"], True)
        for entry in right_leg_cubes
    ]
    tail_cubes = [
        cube([-16, -16, -16], [32, 32, 32], [128, 136]),
        cube([-2, -28, -11], [4, 24, 24], [128, 200]),
    ]
    parts = [
        java_part(
            "body", [0, -12, 0],
            [cube([-48, 0, 0], [96, 96, 40], [0, 0])],
            rotation=[1.22173, 0, 0],
        ),
        java_part("leg_1", [48, -24, 0], right_leg_cubes),
        java_part("leg_2", [-48, -24, 0], left_leg_cubes),
        java_part("tail_1", [0, 6, 108], tail_cubes),
        java_part("tail_2", [0, 0, 32], tail_cubes, "tail_1"),
        java_part("tail_3", [0, 0, 32], tail_cubes, "tail_2"),
        java_part("tail_4", [0, 0, 32], tail_cubes, "tail_3"),
    ]
    bones = convert_java_parts(parts)
    return geometry(
        "hydra", 512, 256, bones,
        (15.0, 11.0, [0, 3.0, 3.5]),
    )


def hydra_head_geometry():
    parts = [
        java_part("head", [0, 0, 0], [
            cube([-16, -14, -32], [32, 24, 32], [272, 0]),
            cube([-15, -2, -56], [30, 12, 24], [272, 56]),
            cube([-15, 10, -20], [30, 8, 16], [272, 132]),
            cube([-2, -30, -12], [4, 24, 24], [128, 200]),
            cube([-12, 10, -49], [2, 5, 2], [272, 156]),
            cube([10, 10, -49], [2, 5, 2], [272, 156]),
            cube([-8, 9, -49], [16, 2, 2], [280, 156]),
            cube([-10, 9, -45], [2, 2, 16], [280, 160]),
            cube([8, 9, -45], [2, 2, 16], [280, 160]),
        ]),
        java_part("jaw", [0, 10, -20], [
            cube([-15, 0, -32], [30, 8, 32], [272, 92]),
            cube([-10, -5, -29], [2, 5, 2], [272, 156]),
            cube([8, -5, -29], [2, 5, 2], [272, 156]),
            cube([-8, -1, -29], [16, 2, 2], [280, 156]),
            cube([-10, -1, -25], [2, 2, 16], [280, 160]),
            cube([8, -1, -25], [2, 2, 16], [280, 160]),
        ], "head"),
        java_part(
            "frill", [0, 0, -14],
            [cube([-24, -40, 0], [48, 48, 4], [272, 200])],
            "head", [-0.5235988, 0, 0],
        ),
    ]
    bones = convert_java_parts(parts)
    return geometry(
        "hydra_head", 512, 256, bones,
        (8.0, 7.0, [0, 2.5, 2.0]),
    )


def hydra_neck_geometry():
    parts = [
        java_part("neck", [0, 0, 0], [
            cube([-16, -16, -16], [32, 32, 32], [128, 136]),
            cube([-2, -23, 0], [4, 24, 24], [128, 200]),
        ])
    ]
    return geometry(
        "hydra_neck", 512, 256, convert_java_parts(parts),
        (3.0, 3.0, [0, 1.5, 0]),
    )


def mortar_geometry():
    return geometry("hydra_mortar", 32, 32, [bone("mortar", [0, 8, 0], [cube([-4, 0, -4], [8, 8, 8], [0, 0])])], (1.2, 1.2, [0, .5, 0]))


def hydra_part_proxy_geometry():
    # Produces the intentionally cube-free geometry.tf_slice.hydra_part_proxy.
    return geometry(
        "hydra_part_proxy", 16, 16, [], (6.0, 6.0, [0, 3.0, 0])
    )


def build_geometries():
    return {
        "minotaur": minotaur_geometry(),
        "minoshroom": minoshroom_geometry(),
        "maze_slime": maze_slime_geometry(),
        "mosquito_swarm": mosquito_geometry(),
        "hydra": hydra_geometry(),
        "hydra_head": hydra_head_geometry(),
        "hydra_neck": hydra_neck_geometry(),
        "hydra_mortar": mortar_geometry(),
        "hydra_part_proxy": hydra_part_proxy_geometry(),
    }


def build_animations():
    # Java setupAnim uses limbSwing (cumulative distance) as the cosine phase
    # and limbSwingAmount (bounded move speed) as the amplitude.  Swapping the
    # Bedrock queries makes the amplitude grow forever and flips limbs through
    # 180 degrees after the actor has travelled far enough.
    walk_phase = "math.cos(query.modified_distance_moved * 38.1709)"
    arm_walk = "%s * query.modified_move_speed * 57.2958" % walk_phase
    leg_walk = "%s * query.modified_move_speed * 80.2141" % walk_phase
    hydra_walk = "%s * query.modified_move_speed * 80.2141" % walk_phase
    attack_time = "math.clamp(variable.attack_time, 0.0, 1.0)"
    attack_body_yaw = (
        "math.sin(math.sqrt(%s) * 360.0) * 11.4592" % attack_time
    )
    attack_eased = (
        "1.0 - (1.0 - %s) * (1.0 - %s) * (1.0 - %s) * (1.0 - %s)"
        % ((attack_time,) * 4)
    )
    attack_pitch = (
        "-math.sin((%s) * 180.0) * 68.7549"
        " + math.sin(%s * 180.0)"
        " * (query.target_x_rotation - 40.1070) * 0.75"
        % (attack_eased, attack_time)
    )
    attack_roll = "-math.sin(%s * 180.0) * 22.9183" % attack_time
    attack_arm_x = "5.0 * (1.0 - math.cos(%s))" % attack_body_yaw
    attack_arm_z = "math.sin(%s) * 5.0" % attack_body_yaw

    def attack_bones():
        return {
            "body": {"rotation": [0, attack_body_yaw, 0]},
            "rightArm": {
                "position": [attack_arm_x, 0, attack_arm_z],
                "rotation": [attack_pitch, "(%s) * 3.0" % attack_body_yaw, attack_roll],
            },
            "leftArm": {
                "position": ["-(%s)" % attack_arm_x, 0, "-(%s)" % attack_arm_z],
                "rotation": [attack_body_yaw, attack_body_yaw, 0],
            },
        }

    def slam_bones(progress):
        return {
            "leg_3": {
                "position": [0, "%s * 7" % progress, "%s * -5.8" % progress],
                "rotation": ["%s * -54" % progress, 0, 0],
            },
            "leg_4": {
                "position": [0, "%s * 7" % progress, "%s * -5.8" % progress],
                "rotation": ["%s * -54" % progress, 0, 0],
            },
            "body": {"position": [0, "%s * 3" % progress, 0]},
            "rightArm": {
                "position": [0, progress, progress],
                "rotation": [
                    "%s * -103.1324" % progress,
                    0,
                    "%s * -11.4592" % progress,
                ],
            },
            "leftArm": {"position": [0, progress, progress]},
            "cow_body": {"rotation": ["%s * -36" % progress, 0, 0]},
        }

    slam_charge = "query.anim_time * query.anim_time"
    slam_recover_linear = (
        "math.clamp(1.0 - query.anim_time / 0.3, 0.0, 1.0)"
    )
    slam_recover = "(%s) * (%s)" % (
        slam_recover_linear,
        slam_recover_linear,
    )
    slime_size = "query.property('tf_slice:slime_size')"
    mortar_fuse = "query.property('tf_slice:mortar_fuse')"
    mortar_swell = (
        "math.clamp(1.0 - ((%s + 1.0) / 10.0), 0.0, 1.0)"
        % mortar_fuse
    )
    mortar_scale = "1.0 + (%s) * (%s) * (%s) * (%s) * 0.3" % (
        mortar_swell,
        mortar_swell,
        mortar_swell,
        mortar_swell,
    )
    slime_pulse = (
        "math.sin(query.life_time * 720)"
        " * math.clamp(query.modified_move_speed * 8, 0, 1)"
    )
    return {
        "format_version": "1.8.0",
        "animations": {
            "animation.tf_slice.minotaur.move": {"loop": True, "bones": {"rightArm": {"rotation": ["-(%s)" % arm_walk, 0, 0]}, "leftArm": {"rotation": [arm_walk, 0, 0]}, "rightLeg": {"rotation": [leg_walk, 0, 0]}, "leftLeg": {"rotation": ["-(%s)" % leg_walk, 0, 0]}, "head": {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0]}}},
            "animation.tf_slice.minotaur.attack": {"loop": True, "bones": attack_bones()},
            "animation.tf_slice.minoshroom.move": {"loop": True, "bones": {"rightArm": {"rotation": ["-(%s)" % arm_walk, 0, 0]}, "leftArm": {"rotation": [arm_walk, 0, 0]}, "leg_1": {"rotation": [leg_walk, 0, 0]}, "leg_2": {"rotation": ["-(%s)" % leg_walk, 0, 0]}, "leg_3": {"position": [0, 0, 1], "rotation": ["-(%s)" % leg_walk, 0, 0]}, "leg_4": {"position": [0, 0, 1], "rotation": [leg_walk, 0, 0]}, "head": {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0]}}},
            "animation.tf_slice.minoshroom.attack": {"loop": True, "bones": attack_bones()},
            "animation.tf_slice.minoshroom.slam": {
                "animation_length": 1.0,
                "anim_time_update": "math.min(query.anim_time + query.delta_time * 20.0 / math.max(query.property('tf_slice:slam_duration'), 1.0), 1.0)",
                "bones": slam_bones(slam_charge),
            },
            "animation.tf_slice.minoshroom.slam_recover": {
                "animation_length": 0.3,
                "bones": slam_bones(slam_recover),
            },
            "animation.tf_slice.maze_slime.squash": {"loop": True, "bones": {"root": {"scale": ["%s * (1 + (%s) * 0.05)" % (slime_size, slime_pulse), "%s * (1 - (%s) * 0.08)" % (slime_size, slime_pulse), "%s * (1 + (%s) * 0.05)" % (slime_size, slime_pulse)]}}},
            "animation.tf_slice.mosquito_swarm.spin": {"loop": True, "bones": {"core": {"rotation": ["math.sin(query.life_time * 229.183) * 14.3239", "query.life_time * 229.183", "math.cos(query.life_time * 229.183) * 14.3239"]}, **dict(("group_%d" % i, {"rotation": ["query.life_time * %d" % (80 + i * 31), "query.life_time * %d" % (120 + i * 19), "query.life_time * %d" % (60 + i * 37)]}) for i in range(1, 7))}},
            "animation.tf_slice.hydra.move": {"loop": True, "bones": {"leg_1": {"rotation": [hydra_walk, 0, 0]}, "leg_2": {"rotation": ["-(%s)" % hydra_walk, 0, 0]}}},
            "animation.tf_slice.hydra_head.state": {"loop": True, "bones": {"head": {"rotation": ["-variable.hydra_mouth_render * 15", 0, 0]}, "jaw": {"rotation": ["variable.hydra_mouth_render * 60", 0, 0]}}},
            "animation.tf_slice.hydra_neck.pose": {"loop": True, "bones": {"neck": {"rotation": [0, 0, 0]}}},
            "animation.tf_slice.hydra_mortar.fuse": {"loop": True, "bones": {"mortar": {"scale": [mortar_scale, mortar_scale, mortar_scale]}}},
        },
    }


def behavior_entity(
    identifier,
    health,
    movement,
    attack,
    collision,
    persistent=False,
    spawnable=True,
    pushable=True,
):
    components = {
        "minecraft:type_family": {"family": [identifier, "monster", "mob"]},
        "minecraft:nameable": {},
        "minecraft:health": {"value": health, "max": health},
        "minecraft:movement": {"value": movement},
        "minecraft:collision_box": {"width": collision[0], "height": collision[1]},
        "minecraft:physics": {},
        "minecraft:pushable": {
            "is_pushable": pushable,
            "is_pushable_by_piston": pushable,
        },
    }
    if persistent:
        components["minecraft:persistent"] = {}
    if attack:
        components.update({
            "minecraft:attack": {"damage": attack},
            "minecraft:movement.basic": {},
            "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_water": True},
            "minecraft:jump.static": {},
            "minecraft:behavior.float": {"priority": 0},
            "minecraft:behavior.hurt_by_target": {"priority": 1},
            "minecraft:behavior.nearest_attackable_target": {"priority": 2, "must_see": False, "entity_types": [{"filters": {"test": "is_family", "subject": "other", "value": "player"}, "max_dist": 24}]},
            "minecraft:behavior.melee_attack": {"priority": 3, "speed_multiplier": 1.0, "track_target": True},
            "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 1.0},
        })
    return {
        "format_version": "1.20.60",
        "minecraft:entity": {
            "description": {
                "identifier": "tf_slice:" + identifier,
                "is_spawnable": spawnable,
                "is_summonable": True,
                "is_experimental": False,
            },
            "components": components,
        },
    }


def mosquito_swarm_behavior():
    document = behavior_entity(
        "mosquito_swarm", 12, .23, 3, (0.7, 1.9)
    )
    components = document["minecraft:entity"]["components"]
    components["minecraft:despawn"] = {"despawn_from_distance": {}}
    components["minecraft:loot"] = {
        "table": "loot_tables/entities/tf_slice/mosquito_swarm.json"
    }
    components["minecraft:ambient_sound_interval"] = {
        "value": 4.0,
        "range": 8.0,
        "event_name": "ambient",
    }
    components["minecraft:follow_range"] = {"value": 16, "max": 16}
    components["minecraft:navigation.walk"]["avoid_damage_blocks"] = True
    target = components["minecraft:behavior.nearest_attackable_target"]
    target["must_see"] = True
    target["reselect_targets"] = True
    target["entity_types"][0]["max_dist"] = 16
    return document


def normal_combat_group():
    return {
        "minecraft:movement.basic": {},
        "minecraft:navigation.walk": {
            "can_path_over_water": True,
            "avoid_water": True,
            "avoid_damage_blocks": True,
        },
        "minecraft:jump.static": {},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 2,
            "must_see": False,
            "reselect_targets": True,
            "entity_types": [{
                "filters": {
                    "test": "is_family",
                    "subject": "other",
                    "value": "player",
                },
                "max_dist": 24,
            }],
        },
        "minecraft:behavior.melee_attack": {
            "priority": 3,
            "speed_multiplier": 1.0,
            "cooldown_time": 1.0,
            "track_target": True,
        },
        "minecraft:behavior.random_stroll": {
            "priority": 6,
            "speed_multiplier": 1.0,
        },
        "minecraft:behavior.look_at_player": {
            "priority": 7,
            "look_distance": 8,
        },
        "minecraft:behavior.random_look_around": {"priority": 7},
    }


def configure_charger(document, identifier, equipment_table, minoshroom=False):
    entity = document["minecraft:entity"]
    components = entity["components"]
    for name in tuple(normal_combat_group()):
        components.pop(name, None)
    # Native melee remains the pursuit/swing adapter.  Damage is zero here so
    # the server-owned 20-tick melee loop cannot stack with an engine hit.
    components["minecraft:attack"] = {"damage": 0}
    components["minecraft:equipment"] = {
        "table": equipment_table,
        "slot_drop_chance": [{
            "slot": "slot.weapon.mainhand",
            "drop_chance": 0.0 if minoshroom else 0.025,
        }],
    }
    if minoshroom:
        components["minecraft:knockback_resistance"] = {"value": 0.5}
    else:
        components["minecraft:despawn"] = {"despawn_from_distance": {}}
    properties = {
        "tf_slice:charging": {
            "type": "bool",
            "default": False,
            "client_sync": True,
        }
    }
    if minoshroom:
        properties["tf_slice:ground_attack"] = {
            "type": "bool",
            "default": False,
            "client_sync": True,
        }
        properties["tf_slice:ground_attack_recovering"] = {
            "type": "bool",
            "default": False,
            "client_sync": True,
        }
        properties["tf_slice:slam_duration"] = {
            "type": "int",
            "range": [1, 59],
            "default": 30,
            "client_sync": True,
        }
    entity["description"]["properties"] = properties
    entity["component_groups"] = {"tf_slice:normal_ai": normal_combat_group()}
    entity["events"] = {
        "minecraft:entity_spawned": {
            "add": {"component_groups": ["tf_slice:normal_ai"]}
        },
        "tf_slice:start_charging": {
            "remove": {"component_groups": ["tf_slice:normal_ai"]},
            "set_property": {"tf_slice:charging": True},
        },
        "tf_slice:stop_charging": {
            "add": {"component_groups": ["tf_slice:normal_ai"]},
            "set_property": {"tf_slice:charging": False},
        },
    }
    if minoshroom:
        entity["events"].update({
            "tf_slice:start_ground_attack": {
                "remove": {"component_groups": ["tf_slice:normal_ai"]},
                "set_property": {
                    "tf_slice:charging": False,
                    "tf_slice:ground_attack": True,
                    "tf_slice:ground_attack_recovering": False,
                },
            },
            "tf_slice:stop_ground_attack": {
                "add": {"component_groups": ["tf_slice:normal_ai"]},
                "set_property": {
                    "tf_slice:ground_attack": False,
                    "tf_slice:ground_attack_recovering": False,
                },
            },
            "tf_slice:impact_ground_attack": {
                "add": {"component_groups": ["tf_slice:normal_ai"]},
                "set_property": {
                    "tf_slice:ground_attack": False,
                    "tf_slice:ground_attack_recovering": True,
                },
            },
            "tf_slice:finish_ground_recovery": {
                "set_property": {
                    "tf_slice:ground_attack_recovering": False,
                },
            },
        })
    return document


def maze_slime_size_group(size):
    health = 2 * size * size
    width = round(0.52 * size, 2)
    return {
        "minecraft:health": {"value": health, "max": health},
        "minecraft:attack": {"damage": size},
        "minecraft:collision_box": {"width": width, "height": width},
        "minecraft:experience_reward": {"on_death": size + 3},
    }


def maze_slime_behavior():
    groups = dict(
        ("tf_slice:size_%d" % size, maze_slime_size_group(size))
        for size in (1, 2, 4)
    )
    events = {}
    all_groups = sorted(groups)
    for size in (1, 2, 4):
        group = "tf_slice:size_%d" % size
        events["tf_slice:set_size_%d" % size] = {
            "remove": {"component_groups": all_groups},
            "add": {"component_groups": [group]},
            "set_property": {"tf_slice:slime_size": size},
        }
    events["minecraft:entity_spawned"] = events["tf_slice:set_size_4"]
    return {
        "format_version": "1.20.60",
        "minecraft:entity": {
            "description": {
                "identifier": "tf_slice:maze_slime",
                "is_spawnable": True,
                "is_summonable": True,
                "is_experimental": False,
                "properties": {
                    "tf_slice:slime_size": {
                        "type": "int",
                        "range": [1, 4],
                        "default": 4,
                        "client_sync": True,
                    }
                },
            },
            "component_groups": groups,
            "components": {
                "minecraft:type_family": {
                    "family": ["maze_slime", "slime", "monster", "mob"]
                },
                "minecraft:nameable": {},
                "minecraft:despawn": {"despawn_from_distance": {}},
                "minecraft:movement": {"value": 0.3},
                "minecraft:physics": {},
                "minecraft:pushable": {
                    "is_pushable": True,
                    "is_pushable_by_piston": True,
                },
                "minecraft:loot": {"table": "loot_tables/entities/maze_slime.json"},
                "minecraft:movement.jump": {"jump_delay": [8, 12]},
                "minecraft:navigation.walk": {
                    "can_path_over_water": True,
                    "avoid_water": True,
                },
                "minecraft:jump.static": {},
                "minecraft:behavior.slime_float": {
                    "priority": 1,
                    "jump_chance_percentage": 0.8,
                    "speed_multiplier": 1.2,
                },
                "minecraft:behavior.slime_attack": {"priority": 1},
                "minecraft:behavior.slime_random_direction": {
                    "priority": 3,
                    "add_random_time_range": 3,
                    "turn_range": 360,
                    "min_change_direction_time": 2.0,
                },
                "minecraft:behavior.slime_keep_on_jumping": {
                    "priority": 5,
                    "speed_multiplier": 1.0,
                },
            },
            "events": events,
        },
    }


def client_entity(identifier, texture, egg=None, material="entity_alphatest"):
    animation = {
        "minotaur": "animation.tf_slice.minotaur.move",
        "minoshroom": "animation.tf_slice.minoshroom.move",
        "maze_slime": "animation.tf_slice.maze_slime.squash",
        "mosquito_swarm": "animation.tf_slice.mosquito_swarm.spin",
        "hydra": "animation.tf_slice.hydra.move",
        "hydra_head": "animation.tf_slice.hydra_head.state",
        "hydra_neck": "animation.tf_slice.hydra_neck.pose",
        "hydra_mortar": "animation.tf_slice.hydra_mortar.fuse",
        "hydra_part_proxy": None,
    }[identifier]
    description = {
        "identifier": "tf_slice:" + identifier,
        "materials": {"default": material},
        "textures": {"default": "textures/entity/" + texture[:-4]},
        "geometry": {"default": "geometry.tf_slice." + identifier},
        "render_controllers": ["controller.render.default"],
    }
    if animation is not None:
        description["animations"] = {"main": animation}
        description["scripts"] = {"animate": ["main"]}
    if identifier in ("minotaur", "minoshroom"):
        description["animations"]["attack"] = (
            "animation.tf_slice.%s.attack" % identifier
        )
        description["scripts"]["animate"].append("attack")
    if identifier == "minoshroom":
        description["animations"]["slam"] = "animation.tf_slice.minoshroom.slam"
        description["animations"]["slam_recover"] = (
            "animation.tf_slice.minoshroom.slam_recover"
        )
        description["scripts"]["animate"].append(
            {"slam": "query.property('tf_slice:ground_attack')"}
        )
        description["scripts"]["animate"].append({
            "slam_recover": (
                "query.property('tf_slice:ground_attack_recovering')"
            )
        })
    if identifier in ("minotaur", "minoshroom"):
        description["enable_attachables"] = True
    if identifier == "maze_slime":
        description["materials"] = {
            "inner": "entity_alphatest",
            "outer": "slime_outer",
        }
        description["render_controllers"] = [
            "controller.render.tf_slice.maze_slime"
        ]
    if identifier in ("hydra", "hydra_head", "hydra_neck"):
        description["render_controllers"] = [
            "controller.render.tf_slice.hydra_hurt"
        ]
    if identifier == "hydra_head":
        description["scripts"]["initialize"] = [
            "variable.hydra_mouth_render = 0.0;"
        ]
        description["scripts"]["pre_animation"] = [
            (
                "variable.hydra_mouth_render = math.lerp("
                "variable.hydra_mouth_render, "
                "query.property('tf_slice:mouth_open'), "
                "math.clamp(query.delta_time * 20.0, 0.0, 1.0));"
            )
        ]
    if identifier == "hydra_mortar":
        description["render_controllers"] = [
            "controller.render.tf_slice.hydra_mortar"
        ]
    if egg:
        description["spawn_egg"] = {"base_color": egg[0], "overlay_color": egg[1]}
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": description}}


def hud(namespace, title, color, precise_fill=False):
    fill_image = {
        "type": "image",
        "anchor_from": "left_middle",
        "anchor_to": "left_middle",
        "offset": [0, 0],
        "size": [182, 5],
        "texture": "textures/ui/filled_progress_bar",
        "color": color,
        "keep_ratio": False,
        "layer": 302,
    }
    if precise_fill:
        fill_control = {
            "bar_fill_clip": {
                "type": "panel",
                "anchor_from": "left_middle",
                "anchor_to": "left_middle",
                "offset": [0, 0],
                "size": [182, 5],
                "clips_children": True,
                "layer": 302,
                "controls": [{"bar_fill": fill_image}],
            }
        }
    else:
        fill_image["clip_direction"] = "left"
        fill_image["clip_ratio"] = 1.0
        fill_control = {"bar_fill": fill_image}
    controls = [{
        "boss_root": {
            "type": "panel",
            "anchor_from": "top_middle",
            "anchor_to": "top_middle",
            "offset": [0, 0],
            "size": [182, 20],
            "layer": 300,
            "visible": False,
            "controls": [
                {
                    "title": {
                        "type": "label",
                        "anchor_from": "top_middle",
                        "anchor_to": "top_middle",
                        "size": [182, 10],
                        "text": title,
                        "color": [1.0, 1.0, 1.0],
                        "text_alignment": "center",
                        "shadow": True,
                        "layer": 303,
                    }
                },
                {
                    "bar_frame": {
                        "type": "panel",
                        "anchor_from": "top_middle",
                        "anchor_to": "top_middle",
                        "offset": [0, 10],
                        "size": [182, 5],
                        "layer": 301,
                        "controls": [
                            {
                                "bar_empty": {
                                    "type": "image",
                                    "anchor_from": "center",
                                    "anchor_to": "center",
                                    "size": [182, 5],
                                    "texture": "textures/ui/empty_progress_bar",
                                    "keep_ratio": False,
                                    "layer": 301,
                                }
                            },
                            fill_control,
                        ],
                    }
                },
            ],
        }
    }]
    return {
        "namespace": namespace,
        "main": {"type": "screen", "render_game_behind": True, "is_showing_menu": False, "absorbs_input": False, "controls": controls},
    }


def main():
    models = build_geometries()
    snapshot = {
        "schemaVersion": 1,
        "sourceJarSha256": JAR_SHA256,
        "modelBranch": "classic",
        "coordinateTransform": "Bedrock X=Java X, Y=24-(Java pivot/local cube Y), Z=Java Z; entity-bone X rotation keeps the Java sign because Bedrock pitch convention cancels the Y-reflection sign flip, Y keeps its sign, and Z is negated.",
        "rendererAdapters": {
            "hydra": {
                "class": "twilightforest.client.renderer.entity.HydraRenderer",
                "sha256": "3AEFD5EA59B83AC121B2E8CABDC44124BD92C074A4411CC43E0117E13B64A320",
                "java_inherited_matrix_yaw": "180 - interpolated_body_yaw",
                "bedrock_axis_owner": "engine_actor_transform",
                "bedrock_root_rotation": [0, 0, 0],
            },
            "hydra_head": {
                "class": "twilightforest.client.renderer.entity.HydraHeadRenderer",
                "sha256": "EB084CBBF882C48F65850A2306728A6379D0A17A7A919BC3C6617AC9165CFAC3",
                "java_pre_yaw_degrees": -180,
                "bedrock_axis_owner": "engine_actor_transform",
                "bedrock_root_rotation": [0, 0, 0],
            },
            "hydra_neck": {
                "class": "twilightforest.client.renderer.entity.HydraNeckRenderer",
                "sha256": "7C084B3316506BA8269C60215F4D6D62EB28434E7FD425044411EC47936F4B1A",
                "java_matrix_yaw": "-(interpolated_entity_yaw + 180)",
                "java_model_yaw": "interpolated_entity_yaw",
                "bedrock_axis_owner": "engine_actor_transform",
                "bedrock_root_rotation": [0, 0, 0],
                "bedrock_actor_yaw": "interpolated_segment_yaw",
            },
        },
        "models": dict((key, {"identifier": value["description"]["identifier"], "parts": value["bones"]}) for key, value in models.items()),
    }
    write_json(SNAPSHOT, snapshot)
    write_json(GEOMETRY, {"format_version": "1.12.0", "minecraft:geometry": list(models.values())})
    write_json(ANIMATIONS, build_animations())
    write_json(
        RENDER_CONTROLLERS,
        {
            "format_version": "1.8.0",
            "render_controllers": {
                "controller.render.tf_slice.maze_slime": {
                    "geometry": "Geometry.default",
                    "materials": [
                        {"*": "Material.inner"},
                        {"outer": "Material.outer"},
                    ],
                    "textures": ["Texture.default"],
                },
                "controller.render.tf_slice.hydra_hurt": {
                    "geometry": "Geometry.default",
                    "materials": [{"*": "Material.default"}],
                    "textures": ["Texture.default"],
                    "color": {
                        "r": 1.0,
                        "g": "query.property('tf_slice:hurt_flash') > 0.5 ? 0.25 : 1.0",
                        "b": "query.property('tf_slice:hurt_flash') > 0.5 ? 0.25 : 1.0",
                        "a": 1.0,
                    },
                },
                "controller.render.tf_slice.hydra_mortar": {
                    "geometry": "Geometry.default",
                    "materials": [{"*": "Material.default"}],
                    "textures": ["Texture.default"],
                    "color": {
                        "r": 1.0,
                        "g": 1.0,
                        "b": 1.0,
                        "a": (
                            "0.075 + query.property('tf_slice:mortar_flash')"
                            " * (1.0 - ((query.property('tf_slice:mortar_fuse')"
                            " + 1.0) / 100.0)) * 0.8"
                        ),
                    },
                },
            },
        },
    )

    texture_names = ("minotaur.png", "minoshroomtaur.png", "mazeslime.png", "mosquitoswarm.png", "hydra4.png", "hydramortar.png")
    for name in texture_names:
        shutil.copy2(str(MODEL_TEXTURES / name), str(RP / "textures" / "entity" / name))

    behaviors = {
        "minotaur": configure_charger(
            behavior_entity("minotaur", 30, .25, 0, (0.7, 2.4)),
            "minotaur",
            "loot_tables/equipment/tf_slice/minotaur.json",
        ),
        "minoshroom": configure_charger(
            behavior_entity("minoshroom", 120, .25, 0, (1.4, 2.8), True),
            "minoshroom",
            "loot_tables/equipment/tf_slice/minoshroom.json",
            True,
        ),
        "maze_slime": maze_slime_behavior(),
        "mosquito_swarm": mosquito_swarm_behavior(),
        "hydra": behavior_entity(
            "hydra", 360, .28, 0, (0.1, 0.1),
            persistent=True, spawnable=True, pushable=False,
        ),
        "hydra_head": behavior_entity(
            "hydra_head", 1000000, 0, 0, (4.0, 4.0),
            persistent=True, spawnable=False, pushable=False,
        ),
        "hydra_neck": behavior_entity(
            "hydra_neck", 1000000, 0, 0, (2.0, 2.0),
            spawnable=False, pushable=False,
        ),
        "hydra_part_proxy": behavior_entity(
            "hydra_part_proxy", 1000000, 0, 0, (0.1, 0.1),
            persistent=False, spawnable=False, pushable=False,
        ),
    }
    hydra_components = behaviors["hydra"]["minecraft:entity"]["components"]
    hurt_flash_property = {
        "type": "float",
        "range": [0.0, 1.0],
        "default": 0.0,
        "client_sync": True,
    }
    hurt_events = {
        "tf_slice:hurt_on": {
            "set_property": {"tf_slice:hurt_flash": 1.0}
        },
        "tf_slice:hurt_off": {
            "set_property": {"tf_slice:hurt_flash": 0.0}
        },
    }
    hydra_entity = behaviors["hydra"]["minecraft:entity"]
    hydra_entity["description"]["properties"] = {
        "tf_slice:hurt_flash": dict(hurt_flash_property)
    }
    hydra_entity["events"] = dict(hurt_events)
    hydra_components["minecraft:fire_immune"] = {}
    hydra_components["minecraft:ambient_sound_interval"] = {
        "value": 4.0,
        "range": 8.0,
        "event_name": "ambient",
    }
    head_entity = behaviors["hydra_head"]["minecraft:entity"]
    head_entity["description"]["properties"] = {
        "tf_slice:mouth_open": {
            "type": "float",
            "range": [0.0, 1.0],
            "default": 0.0,
            "client_sync": True,
        },
        "tf_slice:hurt_flash": dict(hurt_flash_property),
    }
    head_entity["events"] = {}
    head_entity["events"].update(hurt_events)
    head_entity["components"]["minecraft:physics"] = {
        "has_gravity": False,
        "has_collision": False,
    }
    neck_components = behaviors["hydra_neck"]["minecraft:entity"]["components"]
    neck_entity = behaviors["hydra_neck"]["minecraft:entity"]
    neck_entity["description"]["properties"] = {
        "tf_slice:hurt_flash": dict(hurt_flash_property)
    }
    neck_entity["events"] = dict(hurt_events)
    neck_components["minecraft:physics"] = {
        "has_gravity": False,
        "has_collision": False,
    }
    proxy_entity = behaviors["hydra_part_proxy"]["minecraft:entity"]
    proxy_entity["component_groups"] = {
        "tf_slice:body": {
            "minecraft:collision_box": {"width": 6.0, "height": 6.0}
        },
        "tf_slice:leg": {
            "minecraft:collision_box": {"width": 2.0, "height": 3.0}
        },
        "tf_slice:tail": {
            "minecraft:collision_box": {"width": 6.0, "height": 2.0}
        },
    }
    proxy_entity["events"] = dict(
        (
            "tf_slice:set_%s" % name,
            {"add": {"component_groups": ["tf_slice:%s" % name]}},
        )
        for name in ("body", "leg", "tail")
    )
    proxy_entity["components"]["minecraft:physics"] = {
        "has_gravity": False,
        "has_collision": False,
    }
    behaviors["minotaur"]["minecraft:entity"]["components"]["minecraft:loot"] = {
        "table": "loot_tables/entities/minotaur.json"
    }
    write_json(
        BP / "loot_tables" / "equipment" / "tf_slice" / "minotaur.json",
        {
            "pools": [{
                "rolls": 1,
                "entries": [
                    {
                        "type": "item",
                        "name": "tf_slice:gold_minotaur_axe",
                        "weight": 3,
                    },
                    {
                        "type": "item",
                        "name": "minecraft:golden_axe",
                        "weight": 7,
                    },
                ],
            }]
        },
    )
    write_json(
        BP / "loot_tables" / "equipment" / "tf_slice" / "minoshroom.json",
        {
            "pools": [{
                "rolls": 1,
                "entries": [{
                    "type": "item",
                    "name": "tf_slice:diamond_minotaur_axe",
                    "weight": 1,
                }],
            }]
        },
    )
    write_json(
        BP / "loot_tables" / "entities" / "tf_slice" / "mosquito_swarm.json",
        {"pools": []},
    )
    mortar = behavior_entity(
        "hydra_mortar", 1, 0, 0, (.5, .5),
        spawnable=False, pushable=False,
    )
    mortar_components = mortar["minecraft:entity"]["components"]
    mortar_components["minecraft:fire_immune"] = {}
    mortar_components["minecraft:physics"] = {"has_gravity": True}
    mortar_components["minecraft:projectile"] = {"power": .5, "gravity": .05, "uncertainty_base": 1.0, "anchor": 1, "on_hit": {"impact_damage": {"damage": 0, "knockback": False, "semi_random_diff_damage": False}}}
    mortar_entity = mortar["minecraft:entity"]
    mortar_entity["description"]["properties"] = {
        "tf_slice:mortar_fuse": {
            "type": "int",
            "range": [0, 100],
            "default": 80,
            "client_sync": True,
        },
        "tf_slice:mortar_flash": {
            "type": "float",
            "range": [0.0, 1.0],
            "default": 1.0,
            "client_sync": True,
        },
    }
    mortar_entity["component_groups"] = {
        "tf_slice:landed": {
            "minecraft:physics": {"has_gravity": False, "has_collision": True}
        },
        "tf_slice:normal_explosion": {
            "minecraft:explode": {"fuse_length": 0.0, "fuse_lit": True, "power": 0.1, "breaks_blocks": False}
        },
        "tf_slice:mega_explosion": {
            "minecraft:explode": {"fuse_length": 0.0, "fuse_lit": True, "power": 4.0, "breaks_blocks": True}
        },
    }
    mortar_entity["events"] = {
        "tf_slice:landed": {"add": {"component_groups": ["tf_slice:landed"]}},
        "tf_slice:launched": {"remove": {"component_groups": ["tf_slice:landed"]}},
        "tf_slice:explode": {"add": {"component_groups": ["tf_slice:normal_explosion"]}},
        "tf_slice:explode_mega": {"add": {"component_groups": ["tf_slice:mega_explosion"]}},
    }
    for fuse in range(101):
        mortar_entity["events"]["tf_slice:mortar_fuse_%d" % fuse] = {
            "set_property": {
                "tf_slice:mortar_fuse": fuse,
                "tf_slice:mortar_flash": (
                    1.0 if (fuse // 5) % 2 == 0 else 0.0
                ),
            }
        }
    behaviors["hydra_mortar"] = mortar
    for identifier, document in behaviors.items():
        write_json(BP / "entities" / (identifier + ".entity.json"), document)

    clients = {
        "minotaur": client_entity("minotaur", "minotaur.png", ("#6A452B", "#D0B05A")),
        "minoshroom": client_entity("minoshroom", "minoshroomtaur.png", ("#8B1818", "#E7D8B4")),
        "maze_slime": client_entity("maze_slime", "mazeslime.png", ("#2D5139", "#A68A58")),
        "mosquito_swarm": client_entity("mosquito_swarm", "mosquitoswarm.png", ("#17110D", "#7C2D22"), "entity_alphatest"),
        "hydra": client_entity("hydra", "hydra4.png", ("#36150C", "#D07B18")),
        "hydra_head": client_entity("hydra_head", "hydra4.png"),
        "hydra_neck": client_entity("hydra_neck", "hydra4.png"),
        "hydra_mortar": client_entity("hydra_mortar", "hydramortar.png", material="entity_alphablend"),
        "hydra_part_proxy": client_entity("hydra_part_proxy", "hydra4.png"),
    }
    for identifier, document in clients.items():
        write_json(RP / "entity" / (identifier + ".entity.json"), document)

    target_sounds = RP / "sounds" / "mob" / "hydra"
    required_sounds = (
        "death.ogg", "growl1.ogg", "growl2.ogg", "growl3.ogg",
        "hurt1.ogg", "hurt2.ogg", "hurt3.ogg", "hurt4.ogg",
        "roar1.ogg", "roar2.ogg", "warn.ogg",
    )
    missing_sounds = [name for name in required_sounds if not (target_sounds / name).is_file()]
    if missing_sounds:
        raise FileNotFoundError(
            "generate the cleared Hydra sound bank before building models: %s"
            % ", ".join(missing_sounds)
        )
    merge_json_mapping(
        RP / "sounds" / "sound_definitions.json",
        ("sound_definitions",),
        {
            "tf_slice.hydra.ambient": {
                "category": "hostile",
                "sounds": ["sounds/mob/hydra/growl%d" % i for i in range(1, 4)],
            },
            "tf_slice.hydra.hurt": {
                "category": "hostile",
                "sounds": ["sounds/mob/hydra/hurt%d" % i for i in range(1, 5)],
            },
            "tf_slice.hydra.death": {
                "category": "hostile",
                "sounds": ["sounds/mob/hydra/death"],
            },
            "tf_slice.hydra.roar": {
                "category": "hostile",
                "sounds": ["sounds/mob/hydra/roar1", "sounds/mob/hydra/roar2"],
            },
            "tf_slice.hydra.warn": {
                "category": "hostile",
                "sounds": ["sounds/mob/hydra/warn"],
            },
        },
    )
    merge_json_mapping(
        RP / "sounds.json",
        ("entity_sounds", "entities"),
        {
            "tf_slice:mosquito_swarm": {
                "volume": 0.8,
                "pitch": [1.35, 1.55],
                "events": {"ambient": "mob.silverfish.say"},
            },
            "tf_slice:hydra": {
                "volume": 1.5,
                "pitch": [0.95, 1.05],
                "events": {
                    "ambient": "tf_slice.hydra.ambient",
                    "hurt": "tf_slice.hydra.hurt",
                    "death": "tf_slice.hydra.death",
                    "step": "",
                },
            }
        },
    )

    write_json(RP / "ui" / "minoshroom_boss_hud.json", hud("minoshroom_boss_hud", "米诺菇", [1.0, 0.0, 0.0], precise_fill=True))
    write_json(RP / "ui" / "hydra_boss_hud.json", hud("hydra_boss_hud", "九头蛇", [0.0, 0.35, 1.0], precise_fill=True))
    ui_defs = json.loads((RP / "ui" / "_ui_defs.json").read_text(encoding="utf-8"))
    for path in ("ui/minoshroom_boss_hud.json", "ui/hydra_boss_hud.json"):
        if path not in ui_defs["ui_defs"]:
            ui_defs["ui_defs"].append(path)
    write_json(RP / "ui" / "_ui_defs.json", ui_defs)

    names = {"minotaur": ("Minotaur", "牛头人"), "minoshroom": ("Minoshroom", "米诺菇"), "maze_slime": ("Maze Slime", "迷宫史莱姆"), "mosquito_swarm": ("Mosquito Swarm", "蚊群"), "hydra": ("Hydra", "九头蛇"), "hydra_part_proxy": ("Hydra Part", "九头蛇分件")}
    for language, index in (("en_US.lang", 0), ("zh_CN.lang", 1)):
        path = RP / "texts" / language
        lines = path.read_text(encoding="utf-8").splitlines()
        existing = set(line.split("=", 1)[0] for line in lines if "=" in line)
        for identifier, values in names.items():
            for key, value in (("entity.tf_slice:%s.name" % identifier, values[index]), ("item.spawn_egg.entity.tf_slice:%s.name" % identifier, ("Spawn " if index == 0 else "生成 ") + values[index])):
                if key not in existing:
                    lines.append(key + "=" + value)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Overwrite any legacy-code-page labels with deterministic UTF-8 values.
    write_json(
        RP / "ui" / "minoshroom_boss_hud.json",
        hud(
            "minoshroom_boss_hud",
            u"\u7c73\u8bfa\u83c7",
            [1.0, 0.0, 0.0],
            precise_fill=True,
        ),
    )
    write_json(
        RP / "ui" / "hydra_boss_hud.json",
        hud(
            "hydra_boss_hud",
            u"\u4e5d\u5934\u86c7",
            [0.0, 0.35, 1.0],
            precise_fill=True,
        ),
    )
    clean_names = {
        "minotaur": ("Minotaur", u"\u725b\u5934\u4eba"),
        "minoshroom": ("Minoshroom", u"\u7c73\u8bfa\u83c7"),
        "maze_slime": ("Maze Slime", u"\u8ff7\u5bab\u53f2\u83b1\u59c6"),
        "mosquito_swarm": ("Mosquito Swarm", u"\u868a\u7fa4"),
        "hydra": ("Hydra", u"\u4e5d\u5934\u86c7"),
        "hydra_part_proxy": (
            "Hydra Part", u"\u4e5d\u5934\u86c7\u5206\u4ef6"
        ),
    }
    for language, index in (("en_US.lang", 0), ("zh_CN.lang", 1)):
        path = RP / "texts" / language
        lines = path.read_text(encoding="utf-8").splitlines()
        key_lines = dict(
            (line.split("=", 1)[0], line_index)
            for line_index, line in enumerate(lines)
            if "=" in line
        )
        for identifier, values in clean_names.items():
            labels = (
                ("entity.tf_slice:%s.name" % identifier, values[index]),
                (
                    "item.spawn_egg.entity.tf_slice:%s.name" % identifier,
                    ("Spawn " if index == 0 else u"\u751f\u6210 ")
                    + values[index],
                ),
            )
            for key, translated in labels:
                value = key + "=" + translated
                if key in key_lines:
                    lines[key_lines[key]] = value
                else:
                    key_lines[key] = len(lines)
                    lines.append(value)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    creative_path = BP / "item_catalog" / "crafting_item_catalog.json"
    creative = json.loads(creative_path.read_text(encoding="utf-8"))
    creative_items = creative["minecraft:crafting_items_catalog"][
        "categories"
    ][0]["groups"][0]["items"]
    hydra_egg = "tf_slice:hydra_spawn_egg"
    if hydra_egg not in creative_items:
        marker = "tf_slice:naga_boss_spawner"
        insertion = (
            creative_items.index(marker) + 1
            if marker in creative_items
            else len(creative_items)
        )
        creative_items.insert(insertion, hydra_egg)
    write_json(creative_path, creative)
    print("built eight route models and server/client entity shells")


if __name__ == "__main__":
    main()
