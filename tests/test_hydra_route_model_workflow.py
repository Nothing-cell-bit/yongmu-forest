# -*- coding: utf-8 -*-
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from tools import render_entity_geo_preview
from tools import render_hydra_composite_preview
from tools import build_hydra_route_acceptance


ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
SNAPSHOT = ROOT / "model_acceptance" / "source_snapshots" / "hydra_route_models.json"
LABYRINTH_SOURCE = (
    ROOT / "model_acceptance" / "source_snapshots" / "labyrinth_entity_models.json"
)
GEOMETRY = RP / "models" / "entity" / "hydra_route.geo.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class HydraRouteModelWorkflowTests(unittest.TestCase):
    def geometries(self):
        document = json.loads(GEOMETRY.read_text("utf-8"))
        return {
            entry["description"]["identifier"]: entry
            for entry in document["minecraft:geometry"]
        }

    def test_snapshot_locks_eight_models_and_classic_texture_branch(self):
        snapshot = json.loads(SNAPSHOT.read_text("utf-8"))
        self.assertEqual("classic", snapshot["modelBranch"])
        self.assertEqual(
            {
                "minotaur", "minoshroom", "maze_slime", "mosquito_swarm",
                "hydra", "hydra_head", "hydra_neck", "hydra_mortar",
                "hydra_part_proxy",
            },
            set(snapshot["models"]),
        )

    def test_geometry_preserves_standalone_hydra_head_and_neck_models(self):
        document = json.loads(GEOMETRY.read_text("utf-8"))
        geometries = {
            entry["description"]["identifier"]: entry
            for entry in document["minecraft:geometry"]
        }
        expected = {"geometry.tf_slice." + name for name in (
            "minotaur", "minoshroom", "maze_slime", "mosquito_swarm",
            "hydra", "hydra_head", "hydra_neck", "hydra_mortar",
            "hydra_part_proxy",
        )}
        self.assertEqual(expected, set(geometries))

        head_bones = {bone["name"]: bone for bone in geometries["geometry.tf_slice.hydra_head"]["bones"]}
        self.assertEqual({"root", "head", "jaw", "frill"}, set(head_bones))
        self.assertEqual(9, len(head_bones["head"]["cubes"]))
        self.assertEqual(
            {"origin": [-16, 14, -32], "size": [32, 24, 32], "uv": [272, 0]},
            head_bones["head"]["cubes"][0],
        )
        self.assertEqual("head", head_bones["jaw"]["parent"])
        self.assertEqual([0, 14, -20], head_bones["jaw"]["pivot"])
        self.assertEqual(6, len(head_bones["jaw"]["cubes"]))
        self.assertEqual([-30, 0, 0], head_bones["frill"]["rotation"])

        neck_bones = {bone["name"]: bone for bone in geometries["geometry.tf_slice.hydra_neck"]["bones"]}
        self.assertEqual({"root", "neck"}, set(neck_bones))
        self.assertEqual([0, 24, 0], neck_bones["neck"]["pivot"])
        self.assertEqual(
            [
                {"origin": [-16, 8, -16], "size": [32, 32, 32], "uv": [128, 136]},
                {"origin": [-2, 23, 0], "size": [4, 24, 24], "uv": [128, 200]},
            ],
            neck_bones["neck"]["cubes"],
        )

    def test_hydra_body_keeps_source_rotation_and_tail_parent_graph(self):
        document = json.loads(GEOMETRY.read_text("utf-8"))
        hydra = next(
            entry for entry in document["minecraft:geometry"]
            if entry["description"]["identifier"] == "geometry.tf_slice.hydra"
        )
        bones = {bone["name"]: bone for bone in hydra["bones"]}
        self.assertEqual([70, 0, 0], bones["body"]["rotation"])
        self.assertEqual("tail_1", bones["tail_2"]["parent"])
        self.assertEqual("tail_2", bones["tail_3"]["parent"])
        self.assertEqual("tail_3", bones["tail_4"]["parent"])

    def test_hydra_tail_root_overlaps_the_rotated_body_rear(self):
        hydra = self.geometries()["geometry.tf_slice.hydra"]
        bones = {bone["name"]: bone for bone in hydra["bones"]}

        def z_extent(bone_name, cube_index):
            cube = bones[bone_name]["cubes"][cube_index]
            transformed = [
                render_entity_geo_preview.transformed_point(
                    point, bone_name, bones, {}
                )
                for point in render_entity_geo_preview.cube_vertices(cube)
            ]
            return min(point[2] for point in transformed), max(
                point[2] for point in transformed
            )

        body_min, body_max = z_extent("body", 0)
        tail_min, tail_max = z_extent("tail_1", 0)
        overlap = min(body_max, tail_max) - max(body_min, tail_min)
        self.assertGreaterEqual(overlap, 0.0)

    def test_hydra_renderer_front_axis_is_owned_by_the_bedrock_actor(self):
        geometries = self.geometries()
        for identifier in (
            "geometry.tf_slice.hydra",
            "geometry.tf_slice.hydra_head",
            "geometry.tf_slice.hydra_neck",
        ):
            bones = {bone["name"]: bone for bone in geometries[identifier]["bones"]}
            self.assertNotIn("rotation", bones["root"], identifier)

        self.assertEqual(
            [0, 3.0, 3.5],
            geometries["geometry.tf_slice.hydra"]["description"][
                "visible_bounds_offset"
            ],
        )

    def test_standalone_actor_animations_do_not_reapply_actor_rotation(self):
        animations = json.loads(
            (RP / "animations" / "hydra_route.animation.json").read_text("utf-8")
        )["animations"]
        head_rotation = animations["animation.tf_slice.hydra_head.state"][
            "bones"
        ]["head"]["rotation"]
        neck_rotation = animations["animation.tf_slice.hydra_neck.pose"][
            "bones"
        ]["neck"]["rotation"]
        self.assertEqual(0, head_rotation[1])
        self.assertNotIn("query.target_x_rotation", str(head_rotation))
        self.assertEqual([0, 0, 0], neck_rotation)

    def test_composite_preview_does_not_duplicate_actor_axis_adapters(self):
        document = json.loads(GEOMETRY.read_text("utf-8"))
        bones = {
            bone["name"]: bone
            for bone in render_hydra_composite_preview.build_composite_bones(
                document, active_heads=(0,)
            )
        }
        self.assertEqual(0.0, bones["head0_head"]["rotation"][1])
        self.assertEqual(0.0, bones["head0_neck0_neck"]["rotation"][1])

    def test_snapshot_locks_renderer_axis_adapters(self):
        snapshot = json.loads(SNAPSHOT.read_text("utf-8"))
        adapters = snapshot["rendererAdapters"]
        self.assertEqual(
            "3AEFD5EA59B83AC121B2E8CABDC44124BD92C074A4411CC43E0117E13B64A320",
            adapters["hydra"]["sha256"],
        )
        self.assertEqual(-180, adapters["hydra_head"]["java_pre_yaw_degrees"])
        self.assertEqual(
            "-(interpolated_entity_yaw + 180)",
            adapters["hydra_neck"]["java_matrix_yaw"],
        )
        for adapter in adapters.values():
            self.assertEqual(
                "engine_actor_transform",
                adapter["bedrock_axis_owner"],
            )
            self.assertEqual([0, 0, 0], adapter["bedrock_root_rotation"])

    def test_labyrinth_models_use_a_java_local_source_snapshot(self):
        source = json.loads(LABYRINTH_SOURCE.read_text("utf-8"))
        self.assertEqual(
            "0BDC89263616D1B35C32EF82C5E9C14CBD20368E2FE8B468C72A28320BE7A778",
            source["upstream"]["jar_sha256"],
        )
        self.assertEqual(
            {"minotaur", "minoshroom", "maze_slime"},
            set(source["models"]),
        )
        minoshroom = {
            part["name"]: part for part in source["models"]["minoshroom"]["parts"]
        }
        self.assertEqual([0, 5, 2], minoshroom["cow_body"]["pivot"])
        self.assertEqual([90, 0, 0], minoshroom["cow_body"]["rotation_degrees"])
        self.assertEqual("root", minoshroom["cow_body"]["parent"])
        slime = source["models"]["maze_slime"]
        self.assertEqual(
            [8, 8, 8],
            slime["layers"]["outer"]["parts"][0]["cubes"][0]["size"],
        )
        self.assertEqual(
            [6, 6, 6],
            slime["layers"]["inner"]["parts"][0]["cubes"][0]["size"],
        )
        self.assertEqual(
            {
                "phase_query": "query.modified_distance_moved",
                "amplitude_query": "query.modified_move_speed",
                "phase_radians_per_unit": 0.6662,
                "humanoid_arm_amplitude_radians": 1.0,
                "humanoid_leg_amplitude_radians": 1.4,
                "minoshroom_leg_amplitude_radians": 1.4,
            },
            source["animation_semantics"],
        )
        outer = slime["layers"]["outer"]["parts"][0]
        inner = {
            part["name"]: part
            for part in slime["layers"]["inner"]["parts"]
        }
        self.assertEqual([0, 0, 0], outer["pivot"])
        self.assertEqual([-4, 16, -4], outer["cubes"][0]["origin"])
        self.assertEqual([-3, 17, -3], inner["cube"]["cubes"][0]["origin"])
        self.assertEqual([-3.25, 18, -3.5], inner["right_eye"]["cubes"][0]["origin"])
        self.assertEqual([0, 21, -3.5], inner["mouth"]["cubes"][0]["origin"])

    def test_minotaur_preserves_root_siblings_and_source_horn_rotations(self):
        geometry = self.geometries()["geometry.tf_slice.minotaur"]
        bones = {bone["name"]: bone for bone in geometry["bones"]}
        for name in ("head", "body", "rightArm", "leftArm", "rightLeg", "leftLeg"):
            self.assertEqual("root", bones[name]["parent"], name)
        self.assertEqual([0, -25, 10], bones["right_horn_1"]["rotation"])
        self.assertEqual([0, -15, 45], bones["right_horn_2"]["rotation"])
        self.assertEqual([0, 25, -10], bones["left_horn_1"]["rotation"])
        self.assertEqual([0, 15, -45], bones["left_horn_2"]["rotation"])
        self.assertEqual("rightArm", bones["rightItem"]["parent"])
        self.assertEqual([-6, 15, 1], bones["rightItem"]["pivot"])

    def test_minoshroom_preserves_source_hierarchy_and_quadruped_rotation(self):
        geometry = self.geometries()["geometry.tf_slice.minoshroom"]
        bones = {bone["name"]: bone for bone in geometry["bones"]}
        for name in (
            "head", "body", "rightArm", "leftArm", "cow_body", "udders",
            "leg_1", "leg_2", "leg_3", "leg_4",
        ):
            self.assertEqual("root", bones[name]["parent"], name)
        self.assertEqual([90, 0, 0], bones["cow_body"]["rotation"])
        self.assertEqual([90, 0, 0], bones["udders"]["rotation"])
        self.assertEqual("rightArm", bones["rightItem"]["parent"])
        self.assertEqual([-6, 21, -8], bones["rightItem"]["pivot"])

    def test_labyrinth_walk_uses_distance_as_phase_and_speed_as_bounded_amplitude(self):
        animations = json.loads(
            (RP / "animations" / "hydra_route.animation.json").read_text(
                "utf-8"
            )
        )["animations"]
        arm_walk = (
            "math.cos(query.modified_distance_moved * 38.1709)"
            " * query.modified_move_speed * 57.2958"
        )
        leg_walk = (
            "math.cos(query.modified_distance_moved * 38.1709)"
            " * query.modified_move_speed * 80.2141"
        )

        minotaur = animations["animation.tf_slice.minotaur.move"]["bones"]
        self.assertEqual("-(%s)" % arm_walk, minotaur["rightArm"]["rotation"][0])
        self.assertEqual(arm_walk, minotaur["leftArm"]["rotation"][0])
        self.assertEqual(leg_walk, minotaur["rightLeg"]["rotation"][0])
        self.assertEqual("-(%s)" % leg_walk, minotaur["leftLeg"]["rotation"][0])

        minoshroom = animations["animation.tf_slice.minoshroom.move"]["bones"]
        self.assertEqual("-(%s)" % arm_walk, minoshroom["rightArm"]["rotation"][0])
        self.assertEqual(arm_walk, minoshroom["leftArm"]["rotation"][0])
        for name, expected in {
            "leg_1": leg_walk,
            "leg_2": "-(%s)" % leg_walk,
            "leg_3": "-(%s)" % leg_walk,
            "leg_4": leg_walk,
        }.items():
            self.assertEqual(expected, minoshroom[name]["rotation"][0], name)

        self.assertNotIn(
            "tf_slice:charging",
            json.dumps({"minotaur": minotaur, "minoshroom": minoshroom}),
        )

    def test_labyrinth_walk_remains_bounded_over_long_travel_distances(self):
        for distance in (0.0, 1.0, 1_000.0, 1_000_000.0):
            for speed in (0.0, 0.25, 1.0):
                phase = math.cos(distance * 0.6662)
                arm_degrees = phase * speed * 57.2958
                leg_degrees = phase * speed * 80.2141
                self.assertLessEqual(abs(arm_degrees), 57.2958)
                self.assertLessEqual(abs(leg_degrees), 80.2141)

    def test_minotaur_family_layers_source_attack_time_over_locomotion(self):
        animations = json.loads(
            (RP / "animations" / "hydra_route.animation.json").read_text(
                "utf-8"
            )
        )["animations"]
        for identifier in ("minotaur", "minoshroom"):
            attack = animations[
                "animation.tf_slice.%s.attack" % identifier
            ]
            encoded = json.dumps(attack)
            self.assertIn("variable.attack_time", encoded, identifier)
            self.assertIn("math.sqrt", encoded, identifier)
            self.assertEqual(
                {"body", "rightArm", "leftArm"},
                set(attack["bones"]),
                identifier,
            )

            client = json.loads(
                (RP / "entity" / (identifier + ".entity.json")).read_text(
                    "utf-8"
                )
            )["minecraft:client_entity"]["description"]
            self.assertEqual(
                "animation.tf_slice.%s.attack" % identifier,
                client["animations"]["attack"],
            )
            self.assertIn("attack", client["scripts"]["animate"])

    def test_minoshroom_slam_uses_duration_scaled_charge_and_recovery(self):
        animations = json.loads(
            (RP / "animations" / "hydra_route.animation.json").read_text(
                "utf-8"
            )
        )["animations"]
        charge = animations["animation.tf_slice.minoshroom.slam"]
        charge_payload = json.dumps(charge)
        self.assertIn("query.delta_time", charge["anim_time_update"])
        self.assertIn("tf_slice:slam_duration", charge["anim_time_update"])
        self.assertIn("query.anim_time * query.anim_time", charge_payload)
        self.assertNotIn("tf_slice:ground_attack", charge_payload)

        recovery = animations["animation.tf_slice.minoshroom.slam_recover"]
        self.assertAlmostEqual(0.3, recovery["animation_length"])
        self.assertIn(
            "1.0 - query.anim_time / 0.3",
            json.dumps(recovery),
        )

        move = animations["animation.tf_slice.minoshroom.move"]["bones"]
        self.assertEqual([0, 0, 1], move["leg_3"]["position"])
        self.assertEqual([0, 0, 1], move["leg_4"]["position"])

        client = json.loads(
            (RP / "entity" / "minoshroom.entity.json").read_text("utf-8")
        )["minecraft:client_entity"]["description"]
        self.assertEqual(
            "animation.tf_slice.minoshroom.slam_recover",
            client["animations"]["slam_recover"],
        )
        self.assertIn(
            {"slam": "query.property('tf_slice:ground_attack')"},
            client["scripts"]["animate"],
        )
        self.assertIn(
            {
                "slam_recover": (
                    "query.property('tf_slice:ground_attack_recovering')"
                )
            },
            client["scripts"]["animate"],
        )

    def test_hydra_walk_uses_source_phase_and_bounded_leg_amplitude(self):
        animations = json.loads(
            (RP / "animations" / "hydra_route.animation.json").read_text(
                "utf-8"
            )
        )["animations"]
        legs = animations["animation.tf_slice.hydra.move"]["bones"]
        hydra_walk = (
            "math.cos(query.modified_distance_moved * 38.1709)"
            " * query.modified_move_speed * 80.2141"
        )
        self.assertEqual(hydra_walk, legs["leg_1"]["rotation"][0])
        self.assertEqual("-(%s)" % hydra_walk, legs["leg_2"]["rotation"][0])
        self.assertEqual({"leg_1", "leg_2"}, set(legs))

    def test_offline_walk_extremes_exercise_the_source_limb_limits(self):
        minotaur = self.geometries()["geometry.tf_slice.minotaur"]
        self.assertEqual(
            {
                "rightArm": [-57.2958, 0, 0],
                "leftArm": [57.2958, 0, 0],
                "rightLeg": [80.2141, 0, 0],
                "leftLeg": [-80.2141, 0, 0],
            },
            render_entity_geo_preview.walk_extreme_pose(minotaur["bones"]),
        )

        minoshroom = self.geometries()["geometry.tf_slice.minoshroom"]
        self.assertEqual(
            {
                "rightArm": [-57.2958, 0, 0],
                "leftArm": [57.2958, 0, 0],
                "leg_1": [80.2141, 0, 0],
                "leg_2": [-80.2141, 0, 0],
                "leg_3": [-80.2141, 0, 0],
                "leg_4": [80.2141, 0, 0],
            },
            render_entity_geo_preview.walk_extreme_pose(minoshroom["bones"]),
        )

    def test_weapon_bearing_previews_render_and_record_mainhand_attachments(self):
        self.assertEqual(
            (0, -15),
            render_entity_geo_preview.MAINHAND_EVIDENCE_CAMERA,
        )
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "render_entity_geo_preview.py"),
                "--help",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("--held-item-texture", result.stdout)

        item_textures = {
            "minotaur": "TwilightBossSliceR/textures/items/gold_minotaur_axe.png",
            "minoshroom": "TwilightBossSliceR/textures/items/diamond_minotaur_axe.png",
        }
        for identifier in ("minotaur", "minoshroom"):
            geometry = self.geometries()["geometry.tf_slice." + identifier]
            self.assertEqual(
                ["root", "rightArm", "rightItem"],
                [
                    bone["name"]
                    for bone in render_entity_geo_preview.attachment_focus_bones(
                        geometry["bones"], "rightItem"
                    )
                ],
            )
            item_bones = render_entity_geo_preview.held_item_bones(
                geometry["bones"]
            )
            item_cube = next(
                bone for bone in item_bones if bone["name"] == "rightItem"
            )["cubes"][0]
            right_arm_cube = next(
                bone for bone in geometry["bones"] if bone["name"] == "rightArm"
            )["cubes"][0]
            self.assertLess(
                item_cube["origin"][2],
                right_arm_cube["origin"][2],
                "mainhand evidence must render in front of the arm so the grip remains visible",
            )
            self.assertEqual(
                {"uv": [16, 0], "uv_size": [-16, 16]},
                item_cube["uv"]["north"],
            )
            self.assertEqual(
                {"uv": [16, 0], "uv_size": [-16, 16]},
                item_cube["uv"]["south"],
            )
            evidence = json.loads(
                (
                    ROOT
                    / "model_acceptance"
                    / "offline"
                    / (identifier + ".json")
                ).read_text("utf-8")
            )
            mainhand = evidence["offline"]["attachments"]["mainhand"]
            self.assertTrue((ROOT / mainhand).is_file(), identifier)
            attachment = evidence["attachment_contracts"]["mainhand"]
            self.assertEqual("rightItem", attachment["bone"])
            self.assertEqual(item_textures[identifier], attachment["texture_path"])
            self.assertEqual(
                sha256(ROOT / item_textures[identifier]),
                attachment["texture_sha256"],
            )
            self.assertTrue(all(attachment["checks"].values()), identifier)
            self.assertTrue(
                all(evidence["animation_contract"]["checks"].values()),
                identifier,
            )

    def test_maze_slime_uses_vanilla_inner_outer_layers_at_source_scale(self):
        geometry = self.geometries()["geometry.tf_slice.maze_slime"]
        bones = {bone["name"]: bone for bone in geometry["bones"]}
        self.assertEqual([8, 8, 8], bones["outer"]["cubes"][0]["size"])
        self.assertEqual([6, 6, 6], bones["cube"]["cubes"][0]["size"])
        self.assertEqual([2, 2, 2], bones["right_eye"]["cubes"][0]["size"])
        self.assertEqual([2, 2, 2], bones["left_eye"]["cubes"][0]["size"])
        self.assertEqual([1, 1, 1], bones["mouth"]["cubes"][0]["size"])
        self.assertEqual([-4, 0, -4], bones["outer"]["cubes"][0]["origin"])
        self.assertEqual([-3, 1, -3], bones["cube"]["cubes"][0]["origin"])
        self.assertEqual([-3.25, 4, -3.5], bones["right_eye"]["cubes"][0]["origin"])
        self.assertEqual([0, 2, -3.5], bones["mouth"]["cubes"][0]["origin"])

    def test_locked_textures_are_byte_identical_to_source(self):
        lock = json.loads((ROOT / "source_locks" / "hydra_route.json").read_text("utf-8"))
        for entry in lock["textures"]:
            target = ROOT / entry["target"]
            self.assertTrue(target.is_file())
            self.assertEqual(entry["sha256"], sha256(target))

    def test_model_build_is_reproducible(self):
        before = sha256(GEOMETRY)
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build_hydra_route_models.py")],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(before, sha256(GEOMETRY))

    def test_rejected_offline_evidence_cannot_be_promoted_to_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            offline = temporary_root / "model_acceptance" / "offline"
            offline.mkdir(parents=True)
            (offline / "minotaur.json").write_text(
                json.dumps({"entity": "minotaur", "status": "rejected"}),
                encoding="utf-8",
            )
            source_path = temporary_root / "Minotaur.class"
            source_path.write_bytes(b"source")
            texture_path = temporary_root / "minotaur.png"
            texture_path.write_bytes(b"texture")
            contract = {
                "model": "Model",
                "sources": ("Entity",),
                "texture": "minotaur.png",
            }
            classes = {
                "Model": {
                    "class": "Model",
                    "source": source_path,
                    "sha256": "A" * 64,
                },
                "Entity": {
                    "class": "Entity",
                    "source": source_path,
                    "sha256": "B" * 64,
                },
            }
            textures = {
                "minotaur.png": {
                    "source": texture_path,
                    "target": "TwilightBossSliceR/textures/entity/minotaur.png",
                    "sha256": "C" * 64,
                }
            }
            original_root = build_hydra_route_acceptance.ROOT
            build_hydra_route_acceptance.ROOT = temporary_root
            try:
                entry = build_hydra_route_acceptance.registry_entry(
                    "minotaur",
                    contract,
                    classes,
                    textures,
                    implemented=True,
                )
            finally:
                build_hydra_route_acceptance.ROOT = original_root

        self.assertEqual("rejected", entry["status"])
        self.assertIn("rejected", entry["note"])


if __name__ == "__main__":
    unittest.main()
