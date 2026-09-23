# -*- coding: utf-8 -*-
"""Regression contract for the Phantom Knight / Ur-Ghast route entities."""

from __future__ import absolute_import

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
PACKAGE = BP / "TwilightBossSlice"
TOOLS = ROOT / "tools"
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


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

REQUIRED_BONES = {
    "block_chain_goblin": {
        "head", "helmet", "body", "right_arm", "left_arm",
        "right_leg", "left_leg", "flail", "chain_0", "chain_1", "chain_2",
    },
    "lower_goblin_knight": {
        "head", "body", "tunic", "right_arm", "left_arm",
        "right_leg", "left_leg",
    },
    "upper_goblin_knight": {
        "helmet", "right_horn_1", "left_horn_1", "body", "breastplate",
        "right_arm", "left_arm", "spear", "shield", "right_leg", "left_leg",
    },
    "helmet_crab": {
        "body", "helmet", "right_horn_1", "left_horn_1", "right_arm",
        "claw_base", "claw_top", "claw_bottom", "leg_1", "leg_2", "leg_3",
        "leg_4", "leg_5",
    },
    "knight_phantom": {
        "head", "hat", "body", "right_arm", "left_arm", "right_leg",
        "left_leg", "rightItem",
    },
    "carminite_golem": {
        "head", "body", "ribs", "right_arm", "left_arm", "hips", "spine",
        "right_leg", "left_leg",
    },
    "tower_broodling": {
        "head", "thorax", "abdomen", "leg_0", "leg_1", "leg_2", "leg_3",
        "leg_4", "leg_5", "leg_6", "leg_7",
    },
    "mini_ghast": {"body"} | {"tentacle_%d" % index for index in range(9)},
    "tower_ghast": {"body"} | {"tentacle_%d" % index for index in range(9)},
    "towerwood_borer": {
        "segment_0", "segment_1", "segment_2", "segment_3", "segment_4",
        "segment_5", "segment_6", "fin_0", "fin_1", "fin_2",
    },
    "ur_ghast": (
        {"body"}
        | {"tentacle_%d" % index for index in range(9)}
        | {"tentacle_%d_extension" % index for index in range(9)}
        | {"tentacle_%d_tip" % index for index in range(9)}
    ),
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class RouteModelQualityTests(unittest.TestCase):
    def setUp(self):
        geometry_path = RP / "models" / "entity" / "phantom_urghast_route.geo.json"
        self.assertTrue(geometry_path.is_file(), geometry_path)
        document = load_json(geometry_path)
        self.geometries = {
            value["description"]["identifier"].rsplit(".", 1)[-1]: value
            for value in document["minecraft:geometry"]
        }

    def test_every_route_mob_has_source_specific_geometry(self):
        self.assertEqual(
            set(MOBS) | {"knight_phantom_armor"},
            set(self.geometries),
        )
        for identifier in MOBS:
            geometry = self.geometries[identifier]
            bones = geometry["bones"]
            names = {bone["name"] for bone in bones}
            self.assertNotIn("source_locked_placeholder", names, identifier)
            self.assertTrue(REQUIRED_BONES[identifier].issubset(names), identifier)
            cube_count = sum(len(bone.get("cubes", ())) for bone in bones)
            self.assertGreaterEqual(cube_count, 7, identifier)

    def test_tower_broodling_uses_spider_model_left_right_rest_pose(self):
        bones = {
            bone["name"]: bone
            for bone in self.geometries["tower_broodling"]["bones"]
        }
        # SpiderModel.setupAnim assigns mirrored yaw to each left/right pair.
        # convert_parts negates the Java roll once for Bedrock.
        expected = {
            "leg_0": [0, 45, 45],
            "leg_1": [0, -45, -45],
            "leg_2": [0, 22.5, 33.3],
            "leg_3": [0, -22.5, -33.3],
            "leg_4": [0, -22.5, 33.3],
            "leg_5": [0, 22.5, -33.3],
            "leg_6": [0, -45, 45],
            "leg_7": [0, 45, -45],
        }
        for name, rotation in expected.items():
            self.assertEqual(rotation, bones[name]["rotation"], name)

    def test_tower_broodling_uses_the_client_proven_native_spider_contract(self):
        # As a player, I want the broodling's visible front to agree with its
        # movement direction.  Reuse the same native Bedrock spider geometry
        # and animations as the already proven swarm spider, retaining only
        # the broodling's source renderer scale and texture.
        broodling = load_json(RP / "entity" / "tower_broodling.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        swarm = load_json(RP / "entity" / "swarm_spider.entity.json")[
            "minecraft:client_entity"
        ]["description"]

        self.assertEqual("geometry.spider.v1.8", broodling["geometry"]["default"])
        self.assertEqual(swarm["animations"], broodling["animations"])
        self.assertEqual(swarm["scripts"]["animate"], broodling["scripts"]["animate"])
        self.assertEqual("0.7", broodling["scripts"]["scale"])

    def test_knight_phantom_ports_the_renderer_owned_phantom_armor_layer(self):
        armor = self.geometries["knight_phantom_armor"]
        bones = {bone["name"]: bone for bone in armor["bones"]}
        self.assertTrue(
            {
                "head",
                "hat",
                "body",
                "right_arm",
                "left_arm",
                "right_horn_1",
                "right_horn_2",
                "left_horn_1",
                "left_horn_2",
                "shoulder_spike_1",
                "shoulder_spike_2",
            }.issubset(bones)
        )

        head = bones["head"]["cubes"][0]
        self.assertEqual([-4, 24, -4], head["origin"])
        self.assertEqual([8, 8, 8], head["size"])
        self.assertEqual([0, 0], head["uv"])
        self.assertEqual(1.0, head["inflate"])

        hat = bones["hat"]["cubes"][0]
        self.assertEqual([32, 0], hat["uv"])
        self.assertEqual(1.5, hat["inflate"])

        body = bones["body"]["cubes"][0]
        self.assertEqual([8, 12, 4], body["size"])
        self.assertEqual([16, 16], body["uv"])
        self.assertEqual(1.0, body["inflate"])

        self.assertEqual([-4.0, 30.5, 0.0], [float(v) for v in bones["right_horn_1"]["pivot"]])
        self.assertEqual([0.0, -25.0, -45.0], [float(v) for v in bones["right_horn_1"]["rotation"]])
        self.assertEqual([4.0, 30.5, 0.0], [float(v) for v in bones["left_horn_1"]["pivot"]])
        self.assertEqual([0.0, 25.0, 45.0], [float(v) for v in bones["left_horn_1"]["rotation"]])
        self.assertEqual("right_arm", bones["shoulder_spike_1"]["parent"])
        self.assertEqual("left_arm", bones["shoulder_spike_2"]["parent"])

        armor_texture = RP / "textures" / "entity" / "tf_slice" / "knight_phantom_armor.png"
        source_texture = (
            ROOT.parent
            / "twilightforest-1.20.1-4.3.2508-extracted"
            / "00_original_tree"
            / "assets"
            / "twilightforest"
            / "textures"
            / "armor"
            / "phantom_1.png"
        )
        self.assertTrue(armor_texture.is_file())
        self.assertEqual(source_texture.read_bytes(), armor_texture.read_bytes())

    def test_knight_phantom_binds_separate_armor_and_charging_skeleton_passes(self):
        client = load_json(RP / "entity" / "knight_phantom.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertEqual(
            {
                "default": "geometry.tf_slice.knight_phantom",
                "armor": "geometry.tf_slice.knight_phantom_armor",
            },
            client["geometry"],
        )
        self.assertEqual(
            "textures/entity/tf_slice/knight_phantom_skeleton",
            client["textures"]["skeleton"],
        )
        self.assertEqual(
            "textures/entity/tf_slice/knight_phantom_armor",
            client["textures"]["armor"],
        )
        self.assertEqual(
            [
                "controller.render.tf_slice.knight_phantom_skeleton",
                "controller.render.tf_slice.knight_phantom_armor",
            ],
            client["render_controllers"],
        )

        controllers = load_json(
            RP
            / "render_controllers"
            / "phantom_urghast_route.render.json"
        )["render_controllers"]
        skeleton = controllers[
            "controller.render.tf_slice.knight_phantom_skeleton"
        ]
        armor = controllers["controller.render.tf_slice.knight_phantom_armor"]
        self.assertEqual("Geometry.default", skeleton["geometry"])
        self.assertEqual(["Texture.skeleton"], skeleton["textures"])
        charging_visibility = {
            next(iter(row)): next(iter(row.values()))
            for row in skeleton["part_visibility"]
        }
        for name in (
            "skeleton_head",
            "skeleton_hat",
            "skeleton_body",
            "skeleton_right_arm",
            "skeleton_left_arm",
            "skeleton_right_leg",
            "skeleton_left_leg",
        ):
            self.assertEqual(
                "query.property('tf_slice:charging')",
                charging_visibility[name],
            )
        self.assertNotIn("rightItem", charging_visibility)

        skeleton_geometry = self.geometries["knight_phantom"]
        skeleton_bones = {
            bone["name"]: bone for bone in skeleton_geometry["bones"]
        }
        for pose_bone in (
            "head",
            "hat",
            "body",
            "right_arm",
            "left_arm",
            "right_leg",
            "left_leg",
        ):
            self.assertFalse(skeleton_bones[pose_bone].get("cubes"), pose_bone)
            display = skeleton_bones["skeleton_" + pose_bone]
            self.assertEqual(pose_bone, display["parent"])
            self.assertTrue(display.get("cubes"), display["name"])
        self.assertEqual("right_arm", skeleton_bones["rightItem"]["parent"])
        self.assertEqual([-6, 15, 1], skeleton_bones["rightItem"]["pivot"])
        self.assertEqual("left_arm", skeleton_bones["leftItem"]["parent"])
        self.assertEqual([6, 15, 1], skeleton_bones["leftItem"]["pivot"])
        self.assertEqual("Geometry.armor", armor["geometry"])
        self.assertEqual(["Texture.armor"], armor["textures"])

    def test_knight_phantom_armor_preview_composes_the_shared_entity_pose(self):
        tools_path = ROOT / "tools"
        if str(tools_path) not in sys.path:
            sys.path.insert(0, str(tools_path))
        import render_entity_geo_preview

        overlay_bones = [
            {"name": "root", "pivot": [0, 0, 0]},
            {"name": "head", "parent": "root", "pivot": [0, 24, 0]},
            {"name": "right_horn_1", "parent": "head", "pivot": [-4, 30.5, 0]},
        ]
        shared_pose = {"head": [20, 35, 0]}
        layers = render_entity_geo_preview.preview_layers(
            [(overlay_bones, {}, None)],
            None,
            shared_pose,
        )
        self.assertEqual([20, 35, 0], layers[0][1]["head"])

    def test_knight_phantom_legs_use_the_source_same_phase_hover_wave(self):
        animation = load_json(
            RP / "animations" / "phantom_urghast_route.animation.json"
        )["animations"]["animation.tf_slice.knight_phantom.move"]["bones"]
        right = animation["right_leg"]["rotation"]
        left = animation["left_leg"]["rotation"]
        self.assertEqual(right, left)
        self.assertEqual(0, right[1])
        self.assertEqual(0, right[2])
        self.assertIn("query.life_time", right[0])
        self.assertNotIn("query.modified_distance_moved", right[0])
        self.assertIn("22.9183", right[0])
        self.assertIn("11.4592", right[0])
        self.assertIn("343.7747", right[0])

    def test_knight_phantom_right_arm_composes_the_source_held_item_pose(self):
        animation = load_json(
            RP / "animations" / "phantom_urghast_route.animation.json"
        )["animations"]["animation.tf_slice.knight_phantom.move"]["bones"]
        right = animation["right_arm"]["rotation"]
        left = animation["left_arm"]["rotation"]
        self.assertIn("-18", right[0])
        self.assertIn("28.6479", right[0])
        self.assertNotIn("57.2958", right[0])
        self.assertIn("76.7764", right[0])
        self.assertIn("103.1324", right[2])
        self.assertIn("57.2958", left[0])
        self.assertIn("76.7764", left[0])
        self.assertIn("103.1324", left[2])
        self.assertIn("tf_slice:guarding", left[0])

    def test_knight_phantom_preview_holds_the_weapon_down_from_the_grip(self):
        tools_path = ROOT / "tools"
        if str(tools_path) not in sys.path:
            sys.path.insert(0, str(tools_path))
        import render_knight_phantom_preview

        bones = self.geometries["knight_phantom"]["bones"]
        face_bones = render_knight_phantom_preview.visor_face_bones(bones)
        visible_cubes = {
            bone["name"]
            for bone in face_bones
            if bone.get("cubes")
        }
        self.assertEqual({"skeleton_head"}, visible_cubes)
        self.assertEqual([-18.0, 0, 5.7296], render_knight_phantom_preview.source_pose()["right_arm"])
        item_bones = render_knight_phantom_preview.source_held_item_bones(bones)
        cube = next(
            bone for bone in item_bones if bone["name"] == "rightItem"
        )["cubes"][0]
        self.assertEqual(
            {"uv": [16, 16], "uv_size": [-16, -16]},
            cube["uv"]["north"],
        )

    def test_every_bone_hierarchy_is_acyclic_and_root_is_parentless(self):
        for identifier, geometry in self.geometries.items():
            bones = {bone["name"]: bone for bone in geometry["bones"]}
            self.assertNotIn("parent", bones["root"], identifier)
            for bone_name in bones:
                seen = set()
                current = bone_name
                while current is not None:
                    self.assertNotIn(current, seen, "%s:%s" % (identifier, bone_name))
                    seen.add(current)
                    parent = bones[current].get("parent")
                    self.assertTrue(parent is None or parent in bones, "%s:%s" % (identifier, bone_name))
                    current = parent

    def test_chain_and_ur_ghast_keep_their_distinctive_part_counts(self):
        chain_names = {
            bone["name"] for bone in self.geometries["block_chain_goblin"]["bones"]
        }
        self.assertEqual(27, len({name for name in chain_names if name.startswith("spikes_")}))
        ur_names = {bone["name"] for bone in self.geometries["ur_ghast"]["bones"]}
        # The official new/JAPPA branch shown by the reference icon uses nine
        # compact three-part tentacles, not the classic four-part chains.
        self.assertEqual(27, len({name for name in ur_names if name.startswith("tentacle_")}))
        self.assertFalse(any(name.endswith("_extension_2") for name in ur_names))

    def test_ur_ghast_side_tentacles_roll_away_from_the_face_in_bedrock(self):
        """Bedrock negates entity-bone roll when applying the stored angle.

        The locked Java model gives the two left side tentacles positive roll
        and the two right side tentacles negative roll.  Storing the opposite
        signs makes all four arms fold inward and cross in front of the face.
        """
        bones = {
            bone["name"]: bone
            for bone in self.geometries["ur_ghast"]["bones"]
        }
        expected_roll = {
            "tentacle_5": 45.0,
            "tentacle_6": 60.0,
            "tentacle_7": -45.0,
            "tentacle_8": -60.0,
        }
        for name, stored_roll in expected_roll.items():
            self.assertAlmostEqual(
                stored_roll,
                float(bones[name]["rotation"][2]),
                places=4,
                msg=name,
            )
            pivot_x = float(bones[name]["pivot"][0])
            # A new-model source tentacle extends 5.333 pixels from its pivot.
            # The Bedrock client applies the negative of the stored Z roll.
            engine_roll = math.radians(-stored_roll)
            end_x = pivot_x - (-5.333 * math.sin(engine_roll))
            if pivot_x < 0:
                self.assertLess(end_x, pivot_x, name)
            else:
                self.assertGreater(end_x, pivot_x, name)

    def test_ur_ghast_keeps_all_official_tentacle_root_positions(self):
        """Lock the converted NewUrGhastModel attachment layout.

        These are absolute Bedrock pivots after converting the Java model's
        body-relative, Y-down offsets.  In particular, the four side limbs
        must stay on the upper/lower side faces instead of drifting under the
        body or crossing the face.
        """
        bones = {
            bone["name"]: bone
            for bone in self.geometries["ur_ghast"]["bones"]
        }
        expected = {
            "tentacle_0": [4.5, 9.0, 4.5],
            "tentacle_1": [-4.5, 9.0, 4.5],
            "tentacle_2": [0.0, 9.0, 0.0],
            "tentacle_3": [5.5, 9.0, -4.5],
            "tentacle_4": [-5.5, 9.0, -4.5],
            "tentacle_5": [-7.5, 12.5, -1.0],
            "tentacle_6": [-7.5, 17.5, 3.5],
            "tentacle_7": [7.5, 12.5, -1.0],
            "tentacle_8": [7.5, 17.5, 3.5],
        }
        for name, pivot in expected.items():
            self.assertEqual(pivot, [float(value) for value in bones[name]["pivot"]])

    def test_ur_ghast_collision_matches_the_locked_fourteen_by_eighteen_envelope(self):
        collision = load_json(BP / "entities" / "ur_ghast.entity.json")[
            "minecraft:entity"
        ]["components"]["minecraft:collision_box"]
        self.assertEqual({"width": 14.0, "height": 18.0}, collision)

    def test_ur_ghast_uses_the_locked_head_and_tentacle_proportions(self):
        client = load_json(RP / "entity" / "ur_ghast.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertEqual("12.5", client["scripts"]["scale"])

        bones = {
            bone["name"]: bone
            for bone in self.geometries["ur_ghast"]["bones"]
        }
        body_cube = bones["body"]["cubes"][0]
        self.assertEqual([-8, 8, -8], body_cube["origin"])
        self.assertEqual([16, 16, 16], body_cube["size"])
        self.assertEqual([0, 0], body_cube["uv"])

        # The official new/JAPPA branch is shorter, thicker and three-part.
        self.assertEqual(
            [3.333, 5.333, 3.333],
            bones["tentacle_0"]["cubes"][0]["size"],
        )
        self.assertEqual(
            [3.333, 6.66, 3.333],
            bones["tentacle_0_extension"]["cubes"][0]["size"],
        )
        self.assertEqual(
            [3.333, 4, 3.333], bones["tentacle_0_tip"]["cubes"][0]["size"]
        )
        self.assertEqual([0, 0], bones["tentacle_0"]["cubes"][0]["uv"])
        self.assertEqual(
            [0, 3], bones["tentacle_0_extension"]["cubes"][0]["uv"]
        )
        self.assertEqual([0, 9], bones["tentacle_0_tip"]["cubes"][0]["uv"])
        self.assertAlmostEqual(16.0 / 3.333, 4.80048, places=4)
        bounds = self.geometries["ur_ghast"]["description"]
        self.assertEqual(18.0, bounds["visible_bounds_width"])
        self.assertEqual(18.0, bounds["visible_bounds_height"])

        animations = load_json(
            RP / "animations" / "phantom_urghast_route.animation.json"
        )["animations"]
        root = animations["animation.tf_slice.ur_ghast.move"]["bones"]["root"]
        self.assertEqual(3, len(root["scale"]))
        self.assertEqual(root["scale"][0], root["scale"][2])
        for expression in root["scale"]:
            self.assertIn("tf_slice:attack_timer", expression)
            self.assertIn("math.clamp", expression)
            self.assertNotIn("tf_slice:attack_state", expression)
        self.assertEqual([0, 16, 0], bones["pose_root"]["pivot"])
        self.assertEqual("pose_root", bones["body"]["parent"])

        # Locked renderer scale makes the source 16px body 12.5 blocks wide;
        # the new-model 3.333px tentacles are about 2.604 blocks thick.
        self.assertAlmostEqual(12.5, 16.0 * 12.5 / 16.0, places=4)
        self.assertAlmostEqual(2.603906, 3.333 * 12.5 / 16.0, places=4)

        snapshot = load_json(
            ROOT
            / "model_acceptance"
            / "source_snapshots"
            / "phantom_urghast_route_models.json"
        )["models"]["ur_ghast"]
        source_body = next(
            part for part in snapshot["parts"] if part["name"] == "body"
        )
        self.assertEqual([16, 16, 16], source_body["cubes"][0]["size"])
        self.assertNotIn("runtime_adaptation", snapshot)

        source_parts = dict((part["name"], part) for part in snapshot["parts"])
        self.assertEqual([0, 0], source_parts["tentacle_5"]["cubes"][0]["uv"])
        self.assertEqual(
            [0, 3], source_parts["tentacle_5_extension"]["cubes"][0]["uv"]
        )
        self.assertNotIn("tentacle_5_extension_2", source_parts)
        self.assertEqual([0, 9], source_parts["tentacle_5_tip"]["cubes"][0]["uv"])
        self.assertEqual(
            "twilightforest.client.model.entity.newmodels.NewUrGhastModel",
            snapshot["model_class"],
        )

    def test_ur_ghast_offline_poses_evaluate_the_locked_animation_owner(self):
        tools_path = ROOT / "tools"
        if str(tools_path) not in sys.path:
            sys.path.insert(0, str(tools_path))
        import render_ur_ghast_preview

        bones = self.geometries["ur_ghast"]["bones"]
        rest = render_ur_ghast_preview.source_rest_pose(bones)
        extreme = render_ur_ghast_preview.walk_extreme_pose(bones)
        for index in range(9):
            for suffix in ("", "_extension", "_tip"):
                self.assertIn("tentacle_%d%s" % (index, suffix), rest)
                self.assertIn("tentacle_%d%s" % (index, suffix), extreme)
        self.assertAlmostEqual(0.0, rest["tentacle_0"][0], places=3)
        self.assertAlmostEqual(0.0, rest["tentacle_0"][1], places=3)
        self.assertAlmostEqual(14.3239, rest["tentacle_0_extension"][0], places=3)
        self.assertAlmostEqual(17.1887, rest["tentacle_0_tip"][0], places=3)
        self.assertAlmostEqual(22.9183, extreme["tentacle_0"][1], places=3)
        self.assertNotEqual(rest, extreme)
        self.assertEqual(
            [20, 35, 0],
            render_ur_ghast_preview.source_look_pose(bones, 20, 35)["body"],
        )

    def test_ur_ghast_reference_preview_uses_perspective_foreshortening(self):
        tools_path = ROOT / "tools"
        if str(tools_path) not in sys.path:
            sys.path.insert(0, str(tools_path))
        import render_entity_geo_preview
        import render_ur_ghast_preview

        near = render_entity_geo_preview.perspective_project(
            (8.0, 0.0, -8.0),
            render_ur_ghast_preview.REFERENCE_PERSPECTIVE_DISTANCE,
        )
        far = render_entity_geo_preview.perspective_project(
            (8.0, 0.0, 8.0),
            render_ur_ghast_preview.REFERENCE_PERSPECTIVE_DISTANCE,
        )
        self.assertGreater(near[0], 8.0)
        self.assertLess(far[0], 8.0)
        self.assertEqual((45.0, -35.0), render_ur_ghast_preview.REFERENCE_CAMERA)
        self.assertEqual(80.0, render_ur_ghast_preview.REFERENCE_AGE_TICKS)
        self.assertEqual(16, render_ur_ghast_preview.REFERENCE_TEXTURE_SAMPLES)

        body = next(
            bone
            for bone in self.geometries["ur_ghast"]["bones"]
            if bone["name"] == "body"
        )["cubes"][0]
        face_origin, face_size, _ = render_entity_geo_preview.face_texture_data(
            body, 0
        )
        self.assertEqual((16, 16), face_origin)
        self.assertEqual((16, 16), face_size)

    def test_clients_bind_production_animation_and_correct_texture_branches(self):
        animation_path = RP / "animations" / "phantom_urghast_route.animation.json"
        self.assertTrue(animation_path.is_file())
        animations = load_json(animation_path)["animations"]
        for identifier in MOBS:
            if identifier == "tower_broodling":
                continue
            client = load_json(RP / "entity" / (identifier + ".entity.json"))[
                "minecraft:client_entity"
            ]["description"]
            self.assertEqual(
                "geometry.tf_slice.%s" % identifier,
                client["geometry"]["default"],
            )
            self.assertIn("move", client.get("animations", {}), identifier)
            self.assertIn("move", client.get("scripts", {}).get("animate", ()), identifier)
            animation_id = client["animations"]["move"]
            self.assertIn(animation_id, animations, identifier)
        phantom = load_json(RP / "entity" / "knight_phantom.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertEqual(
            "textures/entity/tf_slice/knight_phantom_skeleton",
            phantom["textures"]["skeleton"],
        )
        self.assertEqual(
            "textures/entity/tf_slice/knight_phantom_armor",
            phantom["textures"]["armor"],
        )
        self.assertTrue(phantom.get("enable_attachables"))
        ur_ghast = load_json(RP / "entity" / "ur_ghast.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertEqual(
            {"default", "open", "attack"}, set(ur_ghast["textures"])
        )

    def test_model_registry_locks_the_texture_branches_used_by_clients(self):
        registry = load_json(ROOT / "model_acceptance" / "registry.json")
        entries = {entry["id"]: entry for entry in registry["entities"]}
        phantom_texture = entries["knight_phantom"]["source"]["textures"][0]
        self.assertTrue(
            phantom_texture["source"].endswith("/phantomskeleton.png")
        )
        self.assertEqual(
            "TwilightBossSliceR/textures/entity/tf_slice/knight_phantom_skeleton.png",
            phantom_texture["target"],
        )
        phantom_armor = entries["knight_phantom"]["source"]["textures"][1]
        self.assertTrue(phantom_armor["source"].endswith("/armor/phantom_1.png"))
        self.assertEqual(
            "TwilightBossSliceR/textures/entity/tf_slice/knight_phantom_armor.png",
            phantom_armor["target"],
        )
        renderer_layers = {
            row["role"]: row
            for row in entries["knight_phantom"]["source"]["renderer_layers"]
        }
        self.assertEqual(
            "C93F255C38D3F534FB9E4A7C7A894F0BCC8E7BE96BFD81214A807870BD92A313",
            renderer_layers["armor_model"]["sha256"],
        )
        self.assertEqual(
            "5675CAA80001307A98E9F885AB243CFA661089DCEB5B95B488F33B4C8E797C9C",
            renderer_layers["armor_base_model"]["sha256"],
        )
        self.assertEqual(
            "D183B938FEDF199B4A2ADBA320F6B5BDE5F4D3C43E49AB1298EBA620730A5324",
            renderer_layers["armor_item"]["sha256"],
        )
        ur_ghast_texture = entries["ur_ghast"]["source"]["textures"][0]
        self.assertEqual(
            "twilightforest.client.model.entity.newmodels.NewUrGhastModel",
            entries["ur_ghast"]["source"]["model_class"],
        )
        self.assertEqual(
            "7DC356347F08330525C8167EC4D67191173FCED5FDF5F6D8F3DF34E4CC743639",
            entries["ur_ghast"]["source"]["model_class_sha256"],
        )
        self.assertEqual(
            "twilightforest.client.renderer.entity.newmodels.NewUrGhastRenderer",
            entries["ur_ghast"]["source"]["renderer_class"],
        )
        self.assertIn("JAPPA", entries["ur_ghast"]["source"]["model_branch"])
        self.assertTrue(ur_ghast_texture["source"].endswith("/towerboss.png"))
        self.assertEqual(
            "TwilightBossSliceR/textures/entity/tf_slice/ur_ghast.png",
            ur_ghast_texture["target"],
        )


class RouteNativeAIQualityTests(unittest.TestCase):
    def entity_components(self, identifier):
        entity = load_json(BP / "entities" / (identifier + ".entity.json"))[
            "minecraft:entity"
        ]
        return dict(entity["components"], **entity.get("component_groups", {}).get("tf_slice:goblin_normal", {}))

    def test_ground_mobs_have_navigation_idle_and_source_specific_combat(self):
        for identifier in (
            "block_chain_goblin", "lower_goblin_knight", "upper_goblin_knight",
            "helmet_crab", "carminite_golem", "tower_broodling", "towerwood_borer",
        ):
            components = self.entity_components(identifier)
            self.assertIn("minecraft:behavior.random_stroll", components, identifier)
            self.assertIn("minecraft:behavior.look_at_player", components, identifier)
            self.assertIn("minecraft:behavior.random_look_around", components, identifier)
        self.assertIn(
            "minecraft:behavior.leap_at_target",
            self.entity_components("helmet_crab"),
        )
        self.assertIn("minecraft:can_climb", self.entity_components("tower_broodling"))
        broodling = self.entity_components("tower_broodling")
        self.assertEqual(
            16,
            broodling["minecraft:behavior.nearest_attackable_target"]
            ["entity_types"][0]["max_dist"],
        )
        self.assertEqual(
            0.4,
            broodling["minecraft:behavior.leap_at_target"]["yd"],
        )
        self.assertIn("minecraft:rideable", self.entity_components("lower_goblin_knight"))
        self.assertEqual(
            9,
            self.entity_components("carminite_golem")["minecraft:attack"]["damage"],
        )
        golem = self.entity_components("carminite_golem")
        self.assertEqual(2, golem["minecraft:armor"]["value"])
        self.assertEqual(
            1.0,
            golem["minecraft:behavior.random_stroll"]["speed_multiplier"],
        )
        self.assertEqual(
            6.0,
            golem["minecraft:behavior.look_at_player"]["look_distance"],
        )

    def test_tower_ghasts_keep_native_flight_but_script_owns_ranged_attack(self):
        for identifier in ("mini_ghast", "tower_ghast"):
            document = load_json(BP / "entities" / (identifier + ".entity.json"))[
                "minecraft:entity"
            ]
            components = document["components"]
            self.assertIn("minecraft:behavior.random_hover", components, identifier)
            self.assertNotIn("minecraft:behavior.ranged_attack", components, identifier)
            self.assertNotIn("minecraft:shooter", components, identifier)
            self.assertIn("tf_slice:charging", document["description"]["properties"])
            self.assertTrue(
                components["minecraft:behavior.nearest_attackable_target"]["must_see"]
            )

    def test_mini_ghast_flight_targets_are_symmetric_without_skyward_bias(self):
        import build_dark_tower_content as content

        document = content.hostile_entity(
            "mini_ghast", content.ENTITY_STATS["mini_ghast"]
        )["minecraft:entity"]
        self.assertEqual(
            {
                "priority": 7,
                "xz_dist": 4,
                "y_dist": 4,
                "y_offset": 0,
                "interval": 1,
            },
            document["components"]["minecraft:behavior.random_hover"],
        )
        self.assertEqual(
            {
                "priority": 7,
                "xz_dist": 1,
                "y_dist": 1,
                "y_offset": 0,
                "interval": 4,
            },
            document["component_groups"]["tf_slice:boss_minion"]
            ["minecraft:behavior.random_hover"],
        )
        tower = content.hostile_entity(
            "tower_ghast", content.ENTITY_STATS["tower_ghast"]
        )["minecraft:entity"]
        self.assertEqual(
            content.TOWER_GHAST_HOVER,
            tower["components"]["minecraft:behavior.random_hover"],
        )

    def test_mini_ghast_only_generator_writes_one_behavior_artifact(self):
        import build_dark_tower_content as content

        with tempfile.TemporaryDirectory() as temporary:
            original_bp = content.BP
            try:
                content.BP = Path(temporary) / "behavior"
                result = content.build_mini_ghast_behavior()
            finally:
                content.BP = original_bp
            target = (
                Path(temporary)
                / "behavior"
                / "entities"
                / "mini_ghast.entity.json"
            )
            self.assertEqual([target], [Path(path) for path in result["files"]])
            hover = load_json(target)["minecraft:entity"]["components"]
            hover = hover["minecraft:behavior.random_hover"]
            self.assertEqual(0, hover["y_offset"])

    def test_script_owned_ur_ghast_exposes_its_charge_texture_state(self):
        document = load_json(BP / "entities" / "ur_ghast.entity.json")[
            "minecraft:entity"
        ]
        self.assertIn(
            "tf_slice:attack_state", document["description"]["properties"]
        )
        self.assertIn("tf_slice:attack_tracking", document["events"])
        self.assertIn("tf_slice:attack_charging", document["events"])
        client = load_json(RP / "entity" / "ur_ghast.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertIn(
            "controller.render.tf_slice.ur_ghast",
            client["render_controllers"],
        )

    def test_server_wires_custom_route_mob_state_machine(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("phantom_urghast_mob_logic", source)
        self.assertIn("def _register_phantom_urghast_mob", source)
        self.assertIn("def _drive_phantom_urghast_mobs", source)
        self.assertIn(
            "self._drive_phantom_urghast_mobs(self._ur_ghast_logic_step)",
            source,
        )
        self.assertIn("def _launch_goblin_chain", source)
        self.assertIn("def _land_goblin_spear", source)
        self.assertIn("carminite_golem_hit_result", source)


class RouteCustomAIContractTests(unittest.TestCase):
    def test_flying_hurt_recovery_removes_runaway_upward_motion(self):
        import flight_logic as logic

        self.assertEqual(
            (0.25, 0.0, -0.4),
            logic.stabilized_hurt_motion((0.25, 0.42, -0.4)),
        )
        self.assertEqual(
            (0.25, -0.15, -0.4),
            logic.stabilized_hurt_motion((0.25, -0.15, -0.4)),
        )
        for identifier in (
            "tf_slice:wraith",
            "tf_slice:raven",
            "tf_slice:tiny_bird",
            "tf_slice:death_tome",
            "tf_slice:knight_phantom",
            "tf_slice:mini_ghast",
            "tf_slice:tower_ghast",
            "tf_slice:ur_ghast",
        ):
            self.assertTrue(logic.requires_hurt_stabilization(identifier))
        self.assertFalse(
            logic.requires_hurt_stabilization("tf_slice:tower_broodling")
        )

        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("flight_logic.stabilized_hurt_motion", source)
        self.assertIn("def _queue_flying_hurt_stabilization", source)
        self.assertIn("def _stabilize_flying_hurt", source)

    def test_carminite_golem_hit_raises_target_and_drives_ten_tick_swing(self):
        import phantom_urghast_mob_logic as logic

        self.assertEqual(
            {"verticalMotion": 0.4, "attackTimer": 10},
            logic.carminite_golem_hit_result(),
        )

    def test_chain_throw_requires_range_sight_roll_and_cooldown(self):
        import phantom_urghast_mob_logic as logic

        state = logic.create_mob_state("tf_slice:block_chain_goblin")
        blocked = logic.advance_chain_throw(
            state, distance_sq=16.0, has_sight=True, random_roll=0
        )
        self.assertTrue(blocked["launch"])
        self.assertGreaterEqual(state["chainCooldown"], 100)
        self.assertFalse(
            logic.advance_chain_throw(
                state, distance_sq=16.0, has_sight=True, random_roll=0
            )["launch"]
        )
        state["chainCooldown"] = 0
        self.assertFalse(
            logic.advance_chain_throw(
                state, distance_sq=43.0, has_sight=True, random_roll=0
            )["launch"]
        )
        self.assertFalse(
            logic.advance_chain_throw(
                state, distance_sq=16.0, has_sight=False, random_roll=0
            )["launch"]
        )

    def test_heavy_spear_has_one_landing_tick_and_shield_break_threshold(self):
        import phantom_urghast_mob_logic as logic

        state = logic.create_mob_state("tf_slice:upper_goblin_knight")
        logic.start_heavy_spear(state)
        landed = 0
        for _unused in range(logic.HEAVY_SPEAR_TIMER_START):
            landed += int(logic.advance_heavy_spear(state, has_valid_target=True)["land"])
        self.assertEqual(1, landed)
        self.assertFalse(logic.shield_hit_result(10.0, True)["breakShield"])
        self.assertFalse(logic.shield_hit_result(10.01, True)["breakShield"])
        self.assertTrue(logic.shield_hit_result(10.01, True, hit_count=2)["breakShield"])

    def test_borer_hurt_wakes_exactly_twenty_one_scan_steps(self):
        import phantom_urghast_mob_logic as logic

        state = logic.create_mob_state("tf_slice:towerwood_borer")
        logic.notify_borer_hurt(state)
        events = []
        for _unused in range(21):
            events.extend(logic.advance_borer_summon(state, "infested"))
        self.assertEqual(21, len(events))
        self.assertTrue(all(event["kind"] == "wake_borer" for event in events))

    def test_swarm_family_only_lands_one_melee_hit_in_four(self):
        import spider_logic as logic

        for identifier in (
            "tf_slice:swarm_spider",
            "tf_slice:tower_broodling",
        ):
            self.assertTrue(logic.swarm_attack_is_allowed(identifier, 0))
            for roll in (1, 2, 3):
                self.assertFalse(
                    logic.swarm_attack_is_allowed(identifier, roll)
                )
        self.assertTrue(
            logic.swarm_attack_is_allowed("tf_slice:king_spider", 1)
        )

        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("spider_logic.swarm_attack_is_allowed", source)


if __name__ == "__main__":
    unittest.main()
