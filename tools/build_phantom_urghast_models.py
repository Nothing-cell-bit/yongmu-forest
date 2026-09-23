#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build source-derived classic models for the Phantom/Ur-Ghast route."""

from __future__ import print_function

import json
import math
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
UPSTREAM = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
)
MODEL_TEXTURES = UPSTREAM / "assets" / "twilightforest" / "textures" / "model"
GEOMETRY = RP / "models" / "entity" / "phantom_urghast_route.geo.json"
ANIMATIONS = RP / "animations" / "phantom_urghast_route.animation.json"
RENDER_CONTROLLERS = RP / "render_controllers" / "phantom_urghast_route.render.json"
SNAPSHOT = ROOT / "model_acceptance" / "source_snapshots" / "phantom_urghast_route_models.json"

UPSTREAM_COMMIT = "a7dd8f13c653e137f977f5ffaa870fcb20fc1625"
JAR_SHA256 = "0BDC89263616D1B35C32EF82C5E9C14CBD20368E2FE8B468C72A28320BE7A778"

# The reference silhouette is the locked JAR's official new/JAPPA Ur-Ghast:
# a 16px body, nine compact three-part tentacles, and renderer scale 12.5.
# Do not compensate for branch or pose mismatches by resizing the body.
UR_GHAST_CLIENT_SCALE = 12.5
UR_GHAST_CHARGE_XZ_SCALE = 13.5 / 12.5
UR_GHAST_CHARGE_Y_SCALE = (24.0 + (1.0 / 3.0)) / 2.0 / 12.5

MOBS = (
    "block_chain_goblin",
    "lower_goblin_knight",
    "upper_goblin_knight",
    "helmet_crab",
    "knight_phantom",
    "carminite_golem",
    "tower_broodling",
    "mini_ghast",
    "tower_ghast",
    "towerwood_borer",
    "ur_ghast",
)

SOURCE_CLASSES = {
    "block_chain_goblin": "twilightforest.client.model.entity.BlockChainGoblinModel",
    "lower_goblin_knight": "twilightforest.client.model.entity.LowerGoblinKnightModel",
    "upper_goblin_knight": "twilightforest.client.model.entity.UpperGoblinKnightModel",
    "helmet_crab": "twilightforest.client.model.entity.HelmetCrabModel",
    "knight_phantom": "twilightforest.client.model.entity.KnightPhantomModel",
    "carminite_golem": "twilightforest.client.model.entity.CarminiteGolemModel",
    "tower_broodling": "net.minecraft.client.model.SpiderModel",
    "mini_ghast": "twilightforest.client.model.entity.TFGhastModel",
    "tower_ghast": "twilightforest.client.model.entity.TFGhastModel",
    "towerwood_borer": "net.minecraft.client.model.SilverfishModel",
    "ur_ghast": "twilightforest.client.model.entity.newmodels.NewUrGhastModel",
}

TEXTURE_BRANCHES = {
    "block_chain_goblin": ("blockgoblin.png",),
    "lower_goblin_knight": ("doublegoblin.png",),
    "upper_goblin_knight": ("doublegoblin.png",),
    "helmet_crab": ("helmetcrab.png",),
    "knight_phantom": ("phantomskeleton.png", "../armor/phantom_1.png"),
    "carminite_golem": ("carminitegolem.png",),
    "tower_broodling": ("towerbroodling.png",),
    "mini_ghast": ("towerghast.png", "towerghast_openeyes.png", "towerghast_fire.png"),
    "tower_ghast": ("towerghast.png", "towerghast_openeyes.png", "towerghast_fire.png"),
    "towerwood_borer": ("towertermite.png",),
    "ur_ghast": ("towerboss.png", "towerboss_openeyes.png", "towerboss_fire.png"),
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clean(value):
    value = float(value)
    rounded = round(value)
    return int(rounded) if abs(value - rounded) < 0.000001 else round(value, 6)


def cube(origin, size, uv, mirror=False, inflate=None):
    if isinstance(uv, dict):
        rendered_uv = {
            name: {
                "uv": list(face["uv"]),
                "uv_size": list(face["uv_size"]),
            }
            for name, face in uv.items()
        }
    else:
        rendered_uv = list(uv)
    value = {"origin": list(origin), "size": list(size), "uv": rendered_uv}
    if mirror:
        value["mirror"] = True
    if inflate is not None:
        value["inflate"] = inflate
    return value


def part(name, pivot, cubes=(), parent="root", rotation=(0, 0, 0)):
    return {
        "name": name,
        "parent": parent,
        "pivot": list(pivot),
        "cubes": list(cubes),
        "rotation_degrees": [clean(math.degrees(value)) for value in rotation],
    }


def bone(name, pivot, cubes=(), parent="root", rotation=None, never_render=False):
    value = {"name": name, "pivot": [clean(v) for v in pivot]}
    if parent and parent != name:
        value["parent"] = parent
    if cubes:
        value["cubes"] = list(cubes)
    if rotation and any(float(v) for v in rotation):
        value["rotation"] = [clean(v) for v in rotation]
    if never_render:
        value["neverRender"] = True
    return value


def convert_parts(parts, keep_java_roll=False):
    """Apply the documented Java Y-down to Bedrock Y-up transform.

    Most route records retain the established generic Java-Y reflection.
    Ur-Ghast is the client-proven exception: Bedrock's entity-bone roll
    convention already cancels that reflection, so its source Z angles must be
    stored unchanged.  Negating those four source rolls folds the segmented
    side tentacles inward across the face.
    """
    world_pivots = {"root": [0.0, 0.0, 0.0]}
    converted = []
    for source in parts:
        parent_pivot = world_pivots[source["parent"]]
        pivot = [
            parent_pivot[index] + float(source["pivot"][index])
            for index in range(3)
        ]
        world_pivots[source["name"]] = pivot
        cubes = []
        for source_cube in source.get("cubes", ()):
            local = source_cube["origin"]
            size = source_cube["size"]
            cubes.append(cube(
                [
                    clean(pivot[0] + float(local[0])),
                    clean(24.0 - (pivot[1] + float(local[1]) + float(size[1]))),
                    clean(pivot[2] + float(local[2])),
                ],
                [clean(value) for value in size],
                source_cube["uv"],
                source_cube.get("mirror", False),
                source_cube.get("inflate"),
            ))
        rotation = source.get("rotation_degrees", (0, 0, 0))
        converted.append(bone(
            source["name"],
            [pivot[0], 24.0 - pivot[1], pivot[2]],
            cubes,
            source["parent"],
            [
                rotation[0],
                rotation[1],
                rotation[2] if keep_java_roll else -rotation[2],
            ],
        ))
    return converted


def geometry(identifier, width, height, bones, bounds):
    return {
        "description": {
            "identifier": "geometry.tf_slice." + identifier,
            "texture_width": width,
            "texture_height": height,
            "visible_bounds_width": bounds[0],
            "visible_bounds_height": bounds[1],
            "visible_bounds_offset": bounds[2],
        },
        "bones": [bone("root", (0, 0, 0))] + list(bones),
    }


def humanoid_parts(head=True, hat=True, body=True):
    result = []
    if head:
        result.append(part("head", (0, 0, 0), (cube((-4, -8, -4), (8, 8, 8), (0, 0)),)))
    if hat:
        result.append(part("hat", (0, 0, 0), (cube((-4, -8, -4), (8, 8, 8), (32, 0), inflate=0.5),)))
    if body:
        result.append(part("body", (0, 0, 0), (cube((-4, 0, -2), (8, 12, 4), (16, 16)),)))
    return result


def block_chain_parts():
    parts = [
        part("head", (0, 11, 0)),
        part("hat", (0, 11, 0)),
        part("helmet", (0, 0, 0), (cube((-2.5, -9, -2.5), (5, 9, 5), (24, 0)),), "hat", (0, math.pi / 4, 0)),
        part("body", (0, 11, 0), (cube((-3.5, 0, -2), (7, 7, 4), (0, 21)),)),
        part("right_arm", (-3.5, 12, 0), (cube((-3, -1, -2), (3, 12, 3), (52, 0)),)),
        part("left_arm", (3.5, 12, 0), (cube((0, -1, -1.5), (3, 12, 3), (52, 0)),)),
        part("right_leg", (-2, 18, 0), (cube((-1.5, 0, -1.5), (3, 6, 3), (0, 12)),)),
        part("left_leg", (2, 18, 0), (cube((-1.5, 0, -1.5), (3, 6, 3), (0, 12)),)),
    ]
    return parts


def block_chain_geometry():
    bones = convert_parts(block_chain_parts())
    # The renderer owns three physical chain links and the multipart flail.
    bones.extend((
        bone("chain_0", (0, 13, 0), (cube((-0.5, 12.5, -4), (1, 1, 4), (0, 0)),)),
        bone("chain_1", (0, 13, -4), (cube((-0.5, 12.5, -8), (1, 1, 4), (0, 0)),), "chain_0"),
        bone("chain_2", (0, 13, -8), (cube((-0.5, 12.5, -12), (1, 1, 4), (0, 0)),), "chain_1"),
        bone("flail", (0, 14, -16), (cube((-4, 10, -20), (8, 8, 8), (32, 16)),), "chain_2"),
    ))
    spike_positions = []
    for y in (9, 14, 19):
        for x, z in ((0, -5), (4, -4), (5, 0), (4, 4), (0, 5), (-4, 4), (-5, 0), (-4, -4), (0, 0)):
            spike_positions.append((x, y, z - 16))
    for index, (x, y, z) in enumerate(spike_positions):
        bones.append(bone(
            "spikes_%d" % index,
            (x, y, z),
            (cube((x - 1, y - 1, z - 1), (2, 2, 2), (56, 16)),),
            "flail",
        ))
    return geometry("block_chain_goblin", 64, 32, bones, (4.0, 3.2, [0, 1.3, 0]))


def lower_goblin_parts():
    return [
        part("head", (0, 10, 1), (cube((-2.5, -5, -3.5), (5, 5, 5), (0, 32)),)),
        part("hat", (0, 10, 1)),
        part("body", (0, 8, 0), (cube((-3.5, 0, -2), (7, 8, 4), (16, 48)),)),
        part("tunic", (0, 7.5, 0), (cube((-6, 0, -3), (12, 9, 6), (64, 19)),)),
        part("right_arm", (-3.5, 10, 0), (cube((-2, -2, -1.5), (2, 8, 3), (40, 48)),)),
        part("left_arm", (3.5, 10, 0), (cube((0, -2, -1.5), (2, 8, 3), (40, 48), True),)),
        part("right_leg", (-2.5, 16, 0), (cube((-3, 0, -2), (4, 8, 4), (0, 48)),)),
        part("left_leg", (2.5, 16, 0), (cube((-1, 0, -2), (4, 8, 4), (0, 48), True),)),
    ]


def upper_goblin_parts():
    return [
        part("head", (0, 12, 0)), part("hat", (0, 12, 0)),
        part("helmet", (0, 0, 0), (cube((-3.5, -11, -3.5), (7, 11, 7), (0, 0)),), "hat", (0, math.pi / 4, 0)),
        part("right_horn_1", (-3.5, -9, 0), (cube((-6, -1.5, -1.5), (7, 3, 3), (28, 0)),), "hat", (0, math.radians(15), math.radians(10))),
        part("right_horn_2", (-5.5, 0, 0), (cube((-3, -1, -1), (3, 2, 2), (28, 6)),), "right_horn_1", (0, 0, math.radians(10))),
        part("left_horn_1", (3.5, -9, 0), (cube((-1, -1.5, -1.5), (7, 3, 3), (28, 0), True),), "hat", (0, math.radians(-15), math.radians(-10))),
        part("left_horn_2", (5.5, 0, 0), (cube((0, -1, -1), (3, 2, 2), (28, 6), True),), "left_horn_1", (0, 0, math.radians(-10))),
        part("body", (0, 12, 0), (
            cube((-5.5, 0, -2), (11, 8, 4), (0, 18)),
            cube((-6.5, 0, -2), (1, 4, 4), (30, 24)),
            cube((5.5, 0, -2), (1, 4, 4), (30, 24)),
        )),
        part("breastplate", (0, 11.5, 0), (cube((-6.5, 0, -3), (13, 12, 6), (64, 0)),)),
        part("right_arm", (-6.5, 14, 0), (cube((-4, -2, -2), (4, 12, 4), (44, 16)),)),
        part("spear", (-2, 8.5, 0), (cube((-1, -19, -1), (2, 40, 2), (108, 0)),), "right_arm", (math.pi / 2, 0, 0)),
        part("left_arm", (6.5, 14, 0), (cube((0, -2, -2), (4, 12, 4), (44, 16)),)),
        part("shield", (0, 12, 0), (cube((-6, -6, -2), (12, 20, 2), (63, 36)),), "left_arm", (math.pi / 2, 0, 0)),
        part("right_leg", (-4, 20, 0), (cube((-1.5, 0, -2), (3, 4, 4), (30, 16)),)),
        part("left_leg", (4, 20, 0), (cube((-1.5, 0, -2), (3, 4, 4), (30, 16)),)),
    ]


def helmet_crab_parts():
    return [
        part("body", (0, 19, 0), (cube((-2.5, -2.5, -5), (5, 5, 5), (32, 4)),)),
        part("right_eye", (-1, -1, -4), (cube((-1, -3, -1), (2, 3, 2), (10, 0)),), "body", (math.pi / 4, 0, -math.pi / 4)),
        part("left_eye", (1, -1, -4), (cube((-1, -3, -1), (2, 3, 2), (10, 0)),), "body", (math.pi / 4, 0, math.pi / 4)),
        part("helmet_base", (0, 18, 0), (), "root", (math.radians(-100), math.radians(-30), 0)),
        part("helmet", (0, 0, 0), (cube((-3.5, -11, -3.5), (7, 11, 7), (0, 14)),), "helmet_base", (0, math.pi / 4, 0)),
        part("right_horn_1", (-3.5, -9, 0), (cube((-6, -1.5, -1.5), (7, 3, 3), (28, 14)),), "helmet_base", (0, math.radians(-15), math.radians(10))),
        part("right_horn_2", (-5.5, 0, 0), (cube((-3, -1, -1), (3, 2, 2), (28, 20)),), "right_horn_1", (0, math.radians(-15), math.radians(10))),
        part("left_horn_1", (3.5, -9, 0), (cube((-6, -1.5, -1.5), (7, 3, 3), (28, 14)),), "helmet_base", (0, math.radians(15), math.radians(-10))),
        part("left_horn_2", (5.5, 0, 0), (cube((-3, -1, -1), (3, 2, 2), (28, 20)),), "left_horn_1", (0, math.radians(15), math.radians(-10))),
        part("right_arm", (-3, 20, -3), (cube((-7, -1, -1), (8, 2, 2), (38, 0)),), "root", (0, -1.319531, -0.1919862)),
        part("claw_base", (-6, 0, -0.5), (cube((0, -1.5, -1), (3, 3, 2), (0, 0)),), "right_arm", (0, math.pi / 2, 0)),
        part("claw_bottom", (3, 0, 0), (cube((0, -0.5, -1), (3, 2, 2), (0, 8)),), "claw_base", (0, 0, 0.2602503)),
        part("claw_top", (3, -1, 0), (cube((0, -0.5, -1), (3, 1, 2), (0, 5)),), "claw_base", (0, 0, -0.1858931)),
        part("leg_1", (-3, 20, -1), (cube((-7, -1, -1), (8, 2, 2), (18, 0)),), "root", (0, 0.2792527, -0.1919862)),
        part("leg_2", (3, 20, -1), (cube((-1, -1, -1), (8, 2, 2), (18, 0)),), "root", (0, -0.2792527, 0.1919862)),
        part("leg_3", (-3, 20, -2), (cube((-7, -1, -1), (8, 2, 2), (18, 0)),), "root", (0, -0.2792527, -0.1919862)),
        part("leg_4", (3, 20, -2), (cube((-1, -1, -1), (8, 2, 2), (18, 0)),), "root", (0, 0.2792527, 0.1919862)),
        part("leg_5", (3, 20, -3), (cube((-1, -1, -1), (8, 2, 2), (18, 0)),), "root", (0, 0.5759587, 0.1919862)),
    ]


def knight_phantom_parts():
    return humanoid_parts() + [
        part("right_arm", (-5, 2, 0), (cube((-1, -2, -1), (2, 12, 2), (40, 16)),)),
        part("left_arm", (5, 2, 0), (cube((-1, -2, -1), (2, 12, 2), (40, 16), True),)),
        part("right_leg", (-2, 12, 0), (cube((-1, 0, -1), (2, 12, 2), (0, 16), True),)),
        part("left_leg", (2, 12, 0), (cube((-1, 0, -1), (2, 12, 2), (0, 16), True),)),
    ]


def knight_phantom_armor_parts():
    """Locked outer PhantomArmorModel layer for the default head/chest slots.

    KnightPhantomRenderer delegates equipped armor through HumanoidArmorLayer;
    PhantomArmorItem then replaces the vanilla armor mesh with this model.
    The entity equips only helmet and chestplate, so leg/boot parts are not
    emitted into the Bedrock overlay geometry.
    """
    outer = 1.0
    return [
        part(
            "head",
            (0, 0, 0),
            (cube((-4, -8, -4), (8, 8, 8), (0, 0), inflate=outer),),
        ),
        part(
            "hat",
            (0, 0, 0),
            (cube((-4, -8, -4), (8, 8, 8), (32, 0), inflate=1.5),),
        ),
        part(
            "body",
            (0, 0, 0),
            (cube((-4, 0, -2), (8, 12, 4), (16, 16), inflate=outer),),
        ),
        part(
            "right_arm",
            (-5, 2, 0),
            (cube((-3, -2, -2), (4, 12, 4), (40, 16), inflate=outer),),
        ),
        part(
            "left_arm",
            (5, 2, 0),
            (cube((-1, -2, -2), (4, 12, 4), (40, 16), True, outer),),
        ),
        part(
            "right_horn_1",
            (-4, -6.5, 0),
            (cube((-5.5, -1.5, -1.5), (5, 3, 3), (24, 0), inflate=0.25),),
            "head",
            (0, math.radians(-25), math.radians(45)),
        ),
        part(
            "right_horn_2",
            (-4.5, 0, 0),
            (cube((-3.5, -1, -1), (3, 2, 2), (54, 16), inflate=0.25),),
            "right_horn_1",
            (0, math.radians(-15), math.radians(45)),
        ),
        part(
            "left_horn_1",
            (4, -6.5, 0),
            (cube((0.5, -1.5, -1.5), (5, 3, 3), (24, 0), True, 0.25),),
            "head",
            (0, math.radians(25), math.radians(-45)),
        ),
        part(
            "left_horn_2",
            (4.5, 0, 0),
            (cube((0.5, -1, -1), (3, 2, 2), (54, 16), inflate=0.25),),
            "left_horn_1",
            (0, math.radians(15), math.radians(-45)),
        ),
        part(
            "shoulder_spike_1",
            (-3.75, -2.5, 3),
            (cube((-1, -1, -1), (2, 2, 2), (0, 0), inflate=0.25),),
            "right_arm",
            (math.radians(45), math.radians(10), math.radians(35)),
        ),
        part(
            "shoulder_spike_2",
            (3.75, -2.5, 3),
            (cube((-1, -1, -1), (2, 2, 2), (0, 0), inflate=0.25),),
            "left_arm",
            (math.radians(-45), math.radians(-10), math.radians(55)),
        ),
    ]


def carminite_golem_parts():
    return [
        part("head", (0, -11, -2), (
            cube((-3.5, -10, -3), (7, 8, 6), (0, 0)),
            cube((-4, -6, -3.5), (8, 4, 6), (0, 14)),
        )),
        part("body", (0, -13, 0), (cube((-8, 0, -5), (16, 10, 10), (0, 26)),)),
        part("ribs", (0, -3, 0), (cube((-5, 0, -3), (10, 6, 6), (0, 46)),)),
        part("right_arm", (-8, -12, 0), (
            cube((-5, -2, -1.5), (3, 14, 3), (52, 0)),
            cube((-7, 12, -3), (6, 12, 6), (52, 17)),
            cube((-7, -3, -3.5), (7, 2, 7), (52, 36)),
            cube((-7, -1, -3.5), (7, 5, 2), (52, 45)),
            cube((-7, -1, 1.5), (7, 5, 2), (52, 45)),
            cube((-2, -1, -2), (2, 5, 3), (52, 54)),
        )),
        part("left_arm", (8, -12, 0), (
            cube((2, -2, -1.5), (3, 14, 3), (52, 0), True),
            cube((1, 12, -3), (6, 12, 6), (52, 17), True),
            cube((0, -3, -3.5), (7, 2, 7), (52, 36), True),
            cube((0, -1, -3.5), (7, 5, 2), (52, 45), True),
            cube((0, -1, 1.5), (7, 5, 2), (52, 45), True),
            cube((0, -1, -2), (2, 5, 3), (52, 54), True),
        )),
        part("hips", (0, 1, 0), (cube((-5, 0, -2), (10, 3, 4), (84, 25)),)),
        part("spine", (0, -3, 0), (cube((-1.5, 0, -1.5), (3, 4, 3), (84, 18)),)),
        part("right_leg", (-1, 2, 0), (
            cube((-3, 0, -1.5), (3, 8, 3), (84, 32)),
            cube((-5.5, 8, -4), (6, 14, 7), (84, 43)),
        )),
        part("left_leg", (1, 2, 0), (
            cube((0, 0, -1.5), (3, 8, 3), (84, 32), True),
            cube((-0.5, 8, -4), (6, 14, 7), (84, 43), True),
        )),
    ]


def spider_geometry():
    parts = [
        part("head", (0, 15, -3), (cube((-4, -4, -8), (8, 8, 8), (32, 4)),)),
        part("thorax", (0, 15, 0), (cube((-3, -3, -3), (6, 6, 6), (0, 0)),)),
        part("abdomen", (0, 15, 9), (cube((-5, -4, -6), (10, 8, 12), (0, 12)),)),
    ]
    leg_pivots = ((-4, 15, 2), (4, 15, 2), (-4, 15, 1), (4, 15, 1), (-4, 15, 0), (4, 15, 0), (-4, 15, -1), (4, 15, -1))
    # SpiderModel.setupAnim rest rotations, in hind-to-front part order.
    # Each side has an independent mirrored yaw; pairing both sides to the
    # same yaw makes the silhouette point backwards in the Bedrock client.
    leg_yaws = (45, -45, 22.5, -22.5, -22.5, 22.5, -45, 45)
    leg_rolls = (-45, 45, -33.3, 33.3, -33.3, 33.3, -45, 45)
    for index, pivot in enumerate(leg_pivots):
        left = index % 2 == 0
        parts.append(part(
            "leg_%d" % index,
            pivot,
            (cube((-15 if left else -1, -1, -1), (16, 2, 2), (18, 0)),),
            "root",
            (
                0,
                math.radians(leg_yaws[index]),
                math.radians(leg_rolls[index]),
            ),
        ))
    return geometry("tower_broodling", 64, 32, convert_parts(parts), (2.2, 1.4, [0, 0.6, 0]))


class JavaRandom(object):
    def __init__(self, seed):
        self.seed = (int(seed) ^ 0x5DEECE66D) & ((1 << 48) - 1)

    def next(self, bits):
        self.seed = (self.seed * 0x5DEECE66D + 0xB) & ((1 << 48) - 1)
        return self.seed >> (48 - bits)

    def next_int(self, bound):
        if bound & (bound - 1) == 0:
            return (bound * self.next(31)) >> 31
        while True:
            bits = self.next(31)
            value = bits % bound
            if bits - value + (bound - 1) >= 0:
                return value


def tf_ghast_geometry(identifier):
    parts = [part("body", (0, 8, 0), (cube((-8, -8, -8), (16, 16, 16), (0, 0)),))]
    rng = JavaRandom(1660)
    for index in range(9):
        length = rng.next_int(7) + 8
        x = ((index % 3 - (index / 3.0) % 2 * 0.5 + 0.25) - 1.0) * 5.0
        z = ((index / 3.0) - 1.0) * 5.0
        parts.append(part(
            "tentacle_%d" % index,
            (x, 7, z),
            (cube((-1, 0, -1), (2, length, 2), (0, 0)),),
            "body",
        ))
    return geometry(identifier, 64, 32, convert_parts(parts), (4.0, 4.0, [0, 1.2, 0]))


def silverfish_geometry():
    widths = (3, 4, 6, 3, 2, 2, 1)
    heights = (2, 3, 4, 3, 2, 1, 1)
    lengths = (2, 2, 3, 3, 3, 2, 2)
    uv = ((0, 0), (0, 4), (0, 9), (0, 16), (0, 22), (11, 0), (13, 4))
    parts = []
    z = -3.5
    for index in range(7):
        z += lengths[index] / 2.0
        parts.append(part(
            "segment_%d" % index,
            (0, 22 - heights[index] / 2.0, z),
            (cube((-widths[index] / 2.0, 0, -lengths[index] / 2.0), (widths[index], heights[index], lengths[index]), uv[index]),),
        ))
        z += lengths[index] / 2.0
    parts.extend((
        part("fin_0", (0, 20, 1), (cube((-5, 0, -1), (10, 8, 1), (20, 0)),)),
        part("fin_1", (0, 19, -1.5), (cube((-3, 0, -1), (6, 4, 1), (20, 11)),)),
        part("fin_2", (0, 19, 4), (cube((-3, 0, -1), (6, 5, 1), (20, 18)),)),
    ))
    return geometry("towerwood_borer", 64, 32, convert_parts(parts), (1.2, 0.8, [0, 0.25, 0]))


def ur_ghast_parts():
    # Locked NewUrGhastModel record. The public reference silhouette uses its
    # thicker, shorter, three-part tentacles rather than the classic chains.
    parts = [part("body", (0, 8, 0), (cube((-8, -8, -8), (16, 16, 16), (0, 0)),))]
    positions = (
        (4.5, 7, 4.5, 0), (-4.5, 7, 4.5, 0), (0, 7, 0, 0),
        (5.5, 7, -4.5, 0), (-5.5, 7, -4.5, 0),
        (-7.5, 3.5, -1, math.pi / 4), (-7.5, -1.5, 3.5, math.pi / 3),
        (7.5, 3.5, -1, -math.pi / 4), (7.5, -1.5, 3.5, -math.pi / 3),
    )
    for index, (x, y, z, z_rotation) in enumerate(positions):
        base = "tentacle_%d" % index
        ext = base + "_extension"
        parts.extend((
            part(
                base,
                (x, y, z),
                (cube((-1.5, 0, -1.5), (3.333, 5.333, 3.333), (0, 0)),),
                "body",
                (0, 0, z_rotation),
            ),
            part(
                ext,
                (0, 6.66, 0),
                (cube((-1.5, -1.35, -1.5), (3.333, 6.66, 3.333), (0, 3)),),
                base,
            ),
            part(
                base + "_tip",
                (0, 4, 0),
                (cube((-1.5, 1.3, -1.5), (3.333, 4, 3.333), (0, 9)),),
                ext,
            ),
        ))
    return parts


def ur_ghast_geometry():
    bones = convert_parts(ur_ghast_parts(), keep_java_roll=True)
    for value in bones:
        if value["name"] == "body":
            value["parent"] = "pose_root"
            break
    bones.insert(0, bone("pose_root", (0, 16, 0), parent="root"))
    return geometry("ur_ghast", 64, 32, bones, (18.0, 18.0, [0, 7.0, 0]))


def build_geometries():
    phantom_bones = convert_parts(knight_phantom_parts())
    phantom_display_bones = []
    for phantom_bone in phantom_bones:
        cubes = phantom_bone.pop("cubes", None)
        if cubes:
            phantom_display_bones.append(
                bone(
                    "skeleton_" + phantom_bone["name"],
                    phantom_bone["pivot"],
                    cubes,
                    phantom_bone["name"],
                )
            )
    phantom_bones.extend(phantom_display_bones)
    # Mojang's Bedrock humanoid contract places rightItem one unit outside the
    # arm and seven units below its pivot.  The previous pivot sat at the
    # elbow, which made an equipped sword float beside the forearm.
    phantom_bones.append(bone("rightItem", (-6, 15, 1), (), "right_arm", never_render=True))
    phantom_bones.append(bone("leftItem", (6, 15, 1), (), "left_arm", never_render=True))
    return {
        "block_chain_goblin": block_chain_geometry(),
        "lower_goblin_knight": geometry("lower_goblin_knight", 128, 64, convert_parts(lower_goblin_parts()), (2.0, 2.2, [0, 1, 0])),
        "upper_goblin_knight": geometry("upper_goblin_knight", 128, 64, convert_parts(upper_goblin_parts()), (3.0, 3.2, [0, 1.4, 0])),
        "helmet_crab": geometry("helmet_crab", 64, 32, convert_parts(helmet_crab_parts()), (2.3, 2.0, [0, 0.8, 0])),
        "knight_phantom": geometry("knight_phantom", 64, 32, phantom_bones, (3.2, 4.0, [0, 1.8, 0])),
        "knight_phantom_armor": geometry(
            "knight_phantom_armor",
            64,
            32,
            convert_parts(knight_phantom_armor_parts()),
            (3.2, 4.0, [0, 1.8, 0]),
        ),
        "carminite_golem": geometry("carminite_golem", 128, 64, convert_parts(carminite_golem_parts()), (3.5, 4.5, [0, 2.0, 0])),
        "tower_broodling": spider_geometry(),
        "mini_ghast": tf_ghast_geometry("mini_ghast"),
        "tower_ghast": tf_ghast_geometry("tower_ghast"),
        "towerwood_borer": silverfish_geometry(),
        "ur_ghast": ur_ghast_geometry(),
    }


def humanoid_move(identifier, base_right=0, base_left=0):
    phase = "math.cos(query.modified_distance_moved * 38.1709)"
    arm = "%s * query.modified_move_speed * 57.2958" % phase
    leg = "%s * query.modified_move_speed * 80.2141" % phase
    return {
        "loop": True,
        "bones": {
            "head": {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0]},
            "hat": {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0]},
            "right_arm": {"rotation": ["%s - (%s)" % (base_right, arm), 0, 0]},
            "left_arm": {"rotation": ["%s + (%s)" % (base_left, arm), 0, 0]},
            "right_leg": {"rotation": [leg, 0, 0]},
            "left_leg": {"rotation": ["-(%s)" % leg, 0, 0]},
        },
    }


def build_animations():
    result = {}
    result["animation.tf_slice.lower_goblin_knight.move"] = humanoid_move(
        "lower_goblin_knight"
    )
    phantom = humanoid_move("knight_phantom")
    phantom_arm = "math.cos(query.modified_distance_moved * 38.1709) * query.modified_move_speed"
    # HumanoidModel's ITEM arm pose halves the locomotion swing and then adds
    # -PI/10.  bobModelPart adds the subtle idle pitch/roll after that pose.
    phantom["bones"]["right_arm"] = {
        "rotation": [
            "-18 - (%s * 28.6479) + math.sin(query.life_time * 76.7764) * 2.8648" % phantom_arm,
            0,
            "math.cos(query.life_time * 103.1324) * 2.8648 + 2.8648",
        ]
    }
    phantom["bones"]["left_arm"] = {
        "rotation": [
            "query.property('tf_slice:guarding') ? -72 : (%s * 57.2958 - math.sin(query.life_time * 76.7764) * 2.8648)" % phantom_arm,
            "query.property('tf_slice:guarding') ? 30 : 0",
            "query.property('tf_slice:guarding') ? 0 : -(math.cos(query.life_time * 103.1324) * 2.8648 + 2.8648)",
        ]
    }
    phantom_leg = "22.9183 + math.sin(query.life_time * 343.7747) * 11.4592"
    phantom["bones"]["right_leg"] = {"rotation": [phantom_leg, 0, 0]}
    phantom["bones"]["left_leg"] = {"rotation": [phantom_leg, 0, 0]}
    result["animation.tf_slice.knight_phantom.move"] = phantom
    block = humanoid_move("block_chain_goblin", 180, 180)
    block["bones"]["chain_0"] = {"rotation": ["math.sin(query.life_time * 180) * 18", "query.life_time * 286.4789", 0]}
    result["animation.tf_slice.block_chain_goblin.move"] = block
    upper = humanoid_move("upper_goblin_knight", -137.4, 0)
    upper["bones"]["shield"] = {"rotation": ["137.4 - query.property('tf_slice:heavy_spear') * 45", 0, 0]}
    upper["bones"]["root"] = {"rotation": ["query.property('tf_slice:heavy_spear') * -45", 0, 0]}
    result["animation.tf_slice.upper_goblin_knight.move"] = upper

    crab_bones = {"body": {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0]}}
    for index in range(1, 6):
        phase = (index - 1) * 90
        crab_bones["leg_%d" % index] = {
            "rotation": [0, "math.cos(query.modified_distance_moved * 76.3418 + %d) * query.modified_move_speed * 22.9183" % phase, "math.abs(math.sin(query.modified_distance_moved * 38.1709 + %d)) * query.modified_move_speed * 22.9183" % phase]
        }
    crab_bones["right_arm"] = {"rotation": [0, "-75.603 + math.cos(query.modified_distance_moved * 38.1709 + 180) * query.modified_move_speed * 57.2958", 0]}
    result["animation.tf_slice.helmet_crab.move"] = {"loop": True, "bones": crab_bones}

    golem = humanoid_move("carminite_golem")
    golem["bones"]["right_arm"] = {"rotation": ["variable.attack_time > 0.0 ? -114.5916 : math.cos(query.modified_distance_moved * 14.3239) * query.modified_move_speed * 85.9437", 0, 0]}
    golem["bones"]["left_arm"] = {"rotation": ["variable.attack_time > 0.0 ? -114.5916 : -math.cos(query.modified_distance_moved * 14.3239) * query.modified_move_speed * 85.9437", 0, 0]}
    result["animation.tf_slice.carminite_golem.move"] = golem

    spider_bones = {}
    for index in range(8):
        phase = (index // 2) * 90
        sign = -1 if index % 2 == 0 else 1
        spider_bones["leg_%d" % index] = {
            "rotation": [0, "%s * math.cos(query.modified_distance_moved * 76.3418 + %d) * query.modified_move_speed * 22.9183" % (sign, phase), "%s * math.abs(math.sin(query.modified_distance_moved * 38.1709 + %d)) * query.modified_move_speed * 22.9183" % (sign, phase)]
        }
    result["animation.tf_slice.tower_broodling.move"] = {"loop": True, "bones": spider_bones}

    for identifier in ("mini_ghast", "tower_ghast"):
        # Java Ghasts rotate the entity yaw through look control; their cubic
        # body never pitches/rolls away from the axis-aligned damage envelope.
        bones = {}
        for index in range(9):
            bones["tentacle_%d" % index] = {"rotation": ["math.sin(query.life_time * 108 + %d) * 11.4592 + 22.9183" % (index * 57), 0, 0]}
        result["animation.tf_slice.%s.move" % identifier] = {"loop": True, "bones": bones}

    borer_bones = {}
    for index in range(7):
        borer_bones["segment_%d" % index] = {"rotation": [0, "math.cos(query.life_time * 286.4789 + %d) * %s" % (index * 36, clean((index + 1) * 1.5)), 0]}
    for index in range(3):
        borer_bones["fin_%d" % index] = {"rotation": [0, "math.cos(query.life_time * 286.4789 + %d) * 8" % (index * 65), 0]}
    result["animation.tf_slice.towerwood_borer.move"] = {"loop": True, "bones": borer_bones}

    attack_progress = (
        "(math.clamp(query.property('tf_slice:attack_timer'), "
        "0.0, 20.0) / 20.0)"
    )
    attack_fifth = " * ".join([attack_progress] * 5)
    attack_xz_scale = "1.0 + 0.08 * (%s)" % attack_fifth
    attack_y_scale = (
        "(24.0 + 1.0 / (2.0 * (%s) + 1.0)) / 25.0"
        % attack_fifth
    )
    ur_bones = {
        "root": {
            "scale": [
                attack_xz_scale,
                attack_y_scale,
                attack_xz_scale,
            ],
        },
        "pose_root": {
            "rotation": [
                "query.property('tf_slice:visual_pitch')", 0, 0
            ],
        },
    }
    for index in range(9):
        time = "(query.life_time * 20 + %d) / 2" % (index * 9)
        ur_bones["tentacle_%d" % index] = {
            "rotation": [0, "22.9183 * math.sin((%s) * 0.3 * 57.2958)" % time, 0]
        }
        ur_bones["tentacle_%d_extension" % index] = {
            "rotation": ["5.7296 + math.cos((%s) * 0.3335 * 57.2958) * 8.5944" % time, 0, 0]
        }
        ur_bones["tentacle_%d_tip" % index] = {
            "rotation": ["5.7296 + math.cos((%s) * 0.4445 * 57.2958) * 11.4592" % time, 0, 0]
        }
    result["animation.tf_slice.ur_ghast.move"] = {"loop": True, "bones": ur_bones}
    try:
        from tools.goblin_assets import configure_animations
    except ImportError:
        from goblin_assets import configure_animations
    return configure_animations({"format_version": "1.8.0", "animations": result})


def ghast_render_controller():
    return {
        "format_version": "1.8.0",
        "render_controllers": {
            "controller.render.tf_slice.knight_phantom_skeleton": {
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.skeleton"],
                "part_visibility": [
                ] + [
                    {name: "query.property('tf_slice:charging')"}
                    for name in (
                        "skeleton_head",
                        "skeleton_hat",
                        "skeleton_body",
                        "skeleton_right_arm",
                        "skeleton_left_arm",
                        "skeleton_right_leg",
                        "skeleton_left_leg",
                    )
                ],
            },
            "controller.render.tf_slice.knight_phantom_armor": {
                "geometry": "Geometry.armor",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.armor"],
            },
            "controller.render.tf_slice.route_ghast": {
                "arrays": {"textures": {"Array.skins": ["Texture.default", "Texture.open", "Texture.attack"]}},
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Array.skins[query.property('tf_slice:charging') ? 2 : 0]"],
            },
            "controller.render.tf_slice.ur_ghast": {
                "arrays": {"textures": {"Array.skins": ["Texture.default", "Texture.open", "Texture.attack"]}},
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Array.skins[math.clamp(query.property('tf_slice:attack_state'), 0.0, 1.0) + math.clamp(query.property('tf_slice:attack_timer') - 10.0, 0.0, 1.0)]"],
                "color": {
                    "r": 1.0,
                    "g": "query.property('tf_slice:hurt_flash') > 0.5 ? 0.25 : 1.0",
                    "b": "query.property('tf_slice:hurt_flash') > 0.5 ? 0.25 : 1.0",
                    "a": 1.0,
                },
            },
        },
    }


def client_entity(identifier):
    current_path = RP / "entity" / (identifier + ".entity.json")
    current = json.loads(current_path.read_text(encoding="utf-8"))
    old = current["minecraft:client_entity"]["description"]
    textures = {"default": "textures/entity/tf_slice/" + identifier}
    render_controllers = ["controller.render.default"]
    if identifier == "knight_phantom":
        textures = {
            "skeleton": "textures/entity/tf_slice/knight_phantom_skeleton",
            "armor": "textures/entity/tf_slice/knight_phantom_armor",
        }
        render_controllers = [
            "controller.render.tf_slice.knight_phantom_skeleton",
            "controller.render.tf_slice.knight_phantom_armor",
        ]
    if identifier in ("mini_ghast", "tower_ghast", "ur_ghast"):
        base = identifier
        textures = {
            "default": "textures/entity/tf_slice/" + base,
            "open": "textures/entity/tf_slice/" + base + "_open",
            "attack": "textures/entity/tf_slice/" + base + "_attack",
        }
        render_controllers = ["controller.render.tf_slice.route_ghast"]
        if identifier == "ur_ghast":
            render_controllers = ["controller.render.tf_slice.ur_ghast"]
    description = {
        "identifier": "tf_slice:" + identifier,
        "materials": {"default": "entity_alphatest"},
        "textures": textures,
        "geometry": {"default": "geometry.tf_slice." + identifier},
        "animations": {"move": "animation.tf_slice.%s.move" % identifier},
        "scripts": {"animate": ["move"]},
        "render_controllers": render_controllers,
        "spawn_egg": old.get("spawn_egg", {"base_color": "#3A2529", "overlay_color": "#B3263E"}),
    }
    if identifier == "knight_phantom":
        description["geometry"]["armor"] = (
            "geometry.tf_slice.knight_phantom_armor"
        )
        description["enable_attachables"] = True
        description["scripts"]["scale"] = (
            "query.property('tf_slice:dying_hidden') ? 0.0 : "
            "(query.property('tf_slice:charging') ? 1.8 : 1.2)"
        )
    elif identifier == "tower_broodling":
        # TowerBroodling uses Minecraft's SpiderModel upstream.  Bind it to
        # Bedrock's native spider contract, just like the proven swarm spider,
        # so the engine owns the forward axis and leg pose instead of relying
        # on a visually ambiguous Java-to-Bedrock geometry conversion.
        description["geometry"]["default"] = "geometry.spider.v1.8"
        description["animations"] = {
            "default_leg_pose": "animation.spider.default_leg_pose",
            "look_at_target": "animation.spider.look_at_target",
            "walk": "animation.spider.walk",
        }
        description["scripts"]["animate"] = [
            "default_leg_pose",
            {"walk": "query.modified_move_speed"},
            "look_at_target",
        ]
        description["scripts"]["scale"] = "0.7"
    elif identifier == "tower_ghast":
        description["scripts"]["scale"] = "4.5"
    elif identifier == "ur_ghast":
        description["scripts"]["scale"] = "%.1f" % UR_GHAST_CLIENT_SCALE
    try:
        from tools.goblin_assets import configure_client
    except ImportError:
        from goblin_assets import configure_client
    return configure_client(identifier, {"format_version": "1.10.0", "minecraft:client_entity": {"description": description}})


def copy_textures():
    for identifier, branches in TEXTURE_BRANCHES.items():
        targets = [identifier]
        if len(branches) == 3:
            targets.extend((identifier + "_open", identifier + "_attack"))
        if identifier == "knight_phantom":
            targets = ["knight_phantom_skeleton", "knight_phantom_armor"]
        for source_name, target_name in zip(branches, targets):
            source = MODEL_TEXTURES / source_name
            target = RP / "textures" / "entity" / "tf_slice" / (target_name + ".png")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def source_records():
    return {
        "block_chain_goblin": block_chain_parts(),
        "lower_goblin_knight": lower_goblin_parts(),
        "upper_goblin_knight": upper_goblin_parts(),
        "helmet_crab": helmet_crab_parts(),
        "knight_phantom": knight_phantom_parts(),
        "carminite_golem": carminite_golem_parts(),
        "ur_ghast": ur_ghast_parts(),
    }


def source_model_record(identifier):
    value = {
        "model_class": SOURCE_CLASSES[identifier],
        "texture_branches": list(TEXTURE_BRANCHES[identifier]),
        "parts": source_records().get(identifier, []),
    }
    if identifier == "knight_phantom":
        value["renderer_layers"] = {
            "armor_model_class": (
                "twilightforest.client.model.armor.PhantomArmorModel"
            ),
            "armor_base_class": (
                "twilightforest.client.model.armor.KnightmetalArmorModel"
            ),
            "armor_item_class": "twilightforest.item.PhantomArmorItem",
            "parts": knight_phantom_armor_parts(),
            "visible_slots": ["head", "chest"],
        }
    return value


def build(group=None):
    if group not in (None, "knight", "tower"):
        raise ValueError("unknown model group: %s" % group)
    geometries = build_geometries()
    write_json(GEOMETRY, {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            geometries[name]
            for name in MOBS
        ] + [geometries["knight_phantom_armor"]],
    })
    write_json(ANIMATIONS, build_animations())
    write_json(RENDER_CONTROLLERS, ghast_render_controller())
    try:
        from tools.goblin_assets import visual_documents
    except ImportError:
        from goblin_assets import visual_documents
    for relative, document in visual_documents(geometries["block_chain_goblin"]).items():
        write_json(ROOT / relative, document)
    copy_textures()
    for identifier in MOBS:
        write_json(RP / "entity" / (identifier + ".entity.json"), client_entity(identifier))
    write_json(SNAPSHOT, {
        "upstream": {
            "version": "1.20.1-4.3.2508",
            "source_commit": UPSTREAM_COMMIT,
            "jar_sha256": JAR_SHA256,
            "branch": "classic route models; Ur-Ghast uses official new/JAPPA branch",
            "coordinate_transform": "java (Y-down) -> bedrock (Y-up), y=24-(pivot+origin+size); Ur-Ghast keeps source Z roll because the actual Bedrock entity-bone roll convention already cancels the reflection sign",
        },
        "models": {
            identifier: source_model_record(identifier)
            for identifier in MOBS
        },
    })
    print("built %d Phantom/Ur-Ghast route models" % len(MOBS))


if __name__ == "__main__":
    build()
