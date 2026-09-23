# -*- coding: utf-8 -*-
import hashlib
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
)
GEOMETRY_PATH = (
    ROOT / "TwilightBossSliceR" / "models" / "entity" / "lich_entities.geo.json"
)
PROJECTILE_GEOMETRY_PATH = (
    ROOT
    / "TwilightBossSliceR"
    / "models"
    / "entity"
    / "lich_projectiles.geo.json"
)
SPLIT_GEOMETRY_PATHS = {
    "geometry.tf_slice.lich": (
        ROOT / "TwilightBossSliceR" / "models" / "entity" / "lich.geo.json"
    ),
    "geometry.tf_slice.lich_shadow_clone": (
        ROOT
        / "TwilightBossSliceR"
        / "models"
        / "entity"
        / "lich_shadow_clone.geo.json"
    ),
    "geometry.tf_slice.death_tome": (
        ROOT / "TwilightBossSliceR" / "models" / "entity" / "death_tome.geo.json"
    ),
    "geometry.tf_slice.lich_shields": (
        ROOT / "TwilightBossSliceR" / "models" / "entity" / "lich_shields.geo.json"
    ),
    "geometry.tf_slice.lich_bolt": (
        ROOT / "TwilightBossSliceR" / "models" / "entity" / "lich_bolt.geo.json"
    ),
    "geometry.tf_slice.lich_bomb": (
        ROOT / "TwilightBossSliceR" / "models" / "entity" / "lich_bomb.geo.json"
    ),
}
ANIMATION_PATHS = tuple(
    ROOT / "TwilightBossSliceR" / "animations" / name
    for name in (
        "lich.animation.json",
        "zombie.animation.json",
        "death_tome.animation.json",
        "fortification_shields.animation.json",
    )
)
LICH_TEXTURE_PATH = (
    ROOT
    / "TwilightBossSliceR"
    / "textures"
    / "entity"
    / "tf_slice"
    / "twilightlich64.png"
)
CLONE_TEXTURE_PATH = LICH_TEXTURE_PATH.with_name("twilightlich64_clone.png")
CLONE_CLIENT_PATH = (
    ROOT / "TwilightBossSliceR" / "entity" / "lich_shadow_clone.entity.json"
)
RENDER_CONTROLLER_PATH = (
    ROOT
    / "TwilightBossSliceR"
    / "render_controllers"
    / "lich.render_controllers.json"
)
GENERATOR = ROOT / "tools" / "build_lich_models.py"
SOURCE_SNAPSHOT = (
    ROOT / "model_acceptance" / "source_snapshots" / "lich_models.json"
)


SOURCE_HASHES = {
    "lich_model": "B33D5B71E6428AD6BAAFCDFB22A75CD701B45AE9EDCD8E42E9438450AA570778",
    "death_tome_model": "97FDF1DCC22DB530526749962431B7722A79B5B29ED90EEA8CF4694D33611DCF",
    "shield_layer": "561FC12C3BB01DCE30EFBCA7DE7C6D4425D80559AA26977C42AF2DE7F2FFA2EA",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_animations():
    animations = {}
    for path in ANIMATION_PATHS:
        animations.update(read_json(path)["animations"])
    return animations


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def geometry(identifier, path=None):
    if path is None:
        path = SPLIT_GEOMETRY_PATHS[identifier]
    return next(
        value
        for value in read_json(path)["minecraft:geometry"]
        if value["description"]["identifier"] == identifier
    )


def bones(identifier):
    return {bone["name"]: bone for bone in geometry(identifier)["bones"]}


class LichModelWorkflowTests(unittest.TestCase):
    def test_mixed_geometry_containers_are_replaced_by_single_model_files(self):
        self.assertFalse(GEOMETRY_PATH.exists())
        self.assertFalse(PROJECTILE_GEOMETRY_PATH.exists())
        actual_ids = set()
        for expected_id, path in SPLIT_GEOMETRY_PATHS.items():
            self.assertTrue(path.is_file(), str(path))
            geometries = read_json(path)["minecraft:geometry"]
            self.assertEqual(1, len(geometries), str(path))
            self.assertEqual(expected_id, geometries[0]["description"]["identifier"])
            actual_ids.add(expected_id)
        self.assertEqual(set(SPLIT_GEOMETRY_PATHS), actual_ids)

    def test_locked_model_classes_and_deterministic_source_snapshot_exist(self):
        model_paths = {
            "lich_model": (
                UPSTREAM
                / "twilightforest"
                / "client"
                / "model"
                / "entity"
                / "LichModel.class"
            ),
            "death_tome_model": (
                UPSTREAM
                / "twilightforest"
                / "client"
                / "model"
                / "entity"
                / "DeathTomeModel.class"
            ),
            "shield_layer": (
                UPSTREAM
                / "twilightforest"
                / "client"
                / "renderer"
                / "entity"
                / "ShieldLayer.class"
            ),
        }
        for name, path in model_paths.items():
            self.assertEqual(SOURCE_HASHES[name], sha256(path), name)
        self.assertTrue(SOURCE_SNAPSHOT.is_file())
        self.assertTrue(GENERATOR.is_file())

    def test_lich_geometry_preserves_java_part_offsets_and_root_graph(self):
        by_name = bones("geometry.tf_slice.lich")
        expected = {
            "head": ([0, 28, 0], [-4, 24, -4]),
            "hat": ([0, 28, 0], [-4, 28, -4]),
            "collar": ([0, 27, -1], [-6, 17, -5]),
            "cloak": ([0, 28, 2.5], [-6, 7, 2.5]),
            "body": ([0, 28, 0], [-4, 4, -2]),
            "rightArm": ([-5, 26, 0], [-7, 16, -2]),
            "leftArm": ([5, 22, 0], [4, 12, -2]),
            "rightLeg": ([-2, 12, 0], [-3, 0, -1]),
            "leftLeg": ([2, 12, 0], [1, 0, -1]),
        }
        for name, (pivot, origin) in expected.items():
            with self.subTest(name=name):
                self.assertEqual("root", by_name[name].get("parent"))
                self.assertEqual(pivot, by_name[name]["pivot"])
                self.assertEqual(origin, by_name[name]["cubes"][0]["origin"])
        self.assertEqual([123.999984, 0, 0], by_name["collar"]["rotation"])
        self.assertEqual("rightArm", by_name["rightItem"]["parent"])
        self.assertEqual([-6, 15, 1], by_name["rightItem"]["pivot"])
        self.assertTrue(by_name["rightItem"]["neverRender"])

    def test_lich_mainhand_uses_the_locked_mojang_humanoid_pivot(self):
        source = read_json(SOURCE_SNAPSHOT)
        held_item = source["render_layers"]["held_item"]
        self.assertEqual(
            "56B71336D2B4FDFFD197F56595B0DA93E32A946F78F382A299B8F4B92758BB0F",
            held_item["minecraft_client_jar_sha256"],
        )
        self.assertEqual([-6, 15, 1], held_item["right_item_pivot"])

    def test_death_tome_geometry_keeps_source_axes_and_unanimated_bind_pose(self):
        by_name = bones("geometry.tf_slice.death_tome")
        self.assertEqual([0, 24, 0], by_name["root"]["pivot"])
        self.assertNotIn("rotation", by_name["root"])
        self.assertEqual([0, 24, 0], by_name["book"]["pivot"])

        expected_cubes = {
            "pages_right": ([0, 20, -0.99], [5, 8, 1]),
            "pages_left": ([0, 20, -0.01], [5, 8, 1]),
            "flipping_page_right": ([0, 20, 0], [5, 8, 0.005]),
            "flipping_page_left": ([0, 20, 0], [5, 8, 0.005]),
            "cover_right": ([-6, 19, -1.005], [6, 10, 0.005]),
            "cover_left": ([0, 19, 0.995], [6, 10, 0.005]),
            "book_spine": ([-1, 19, 0], [2, 10, 0.005]),
            "loose_page_0": ([0, 20, -8], [5, 8, 0.005]),
            "loose_page_1": ([0, 20, 9], [5, 8, 0.005]),
            "loose_page_2": ([0, 20, 11], [5, 8, 0.005]),
            "loose_page_3": ([0, 20, 7], [5, 8, 0.005]),
        }
        for name, (origin, size) in expected_cubes.items():
            with self.subTest(name=name):
                cube = by_name[name]["cubes"][0]
                self.assertEqual(origin, cube["origin"])
                self.assertEqual(size, cube["size"])
                if name != "book_spine":
                    self.assertNotIn("rotation", by_name[name])

    def test_visual_animations_keep_source_rotation_axes_and_motion_terms(self):
        animations = read_animations()
        lich = animations["animation.tf_slice.lich.source_pose"]["bones"]
        tome = animations["animation.tf_slice.death_tome.fly"]["bones"]
        lich_animate = read_json(
            ROOT / "TwilightBossSliceR" / "entity" / "lich.entity.json"
        )["minecraft:client_entity"]["description"]["scripts"]["animate"]
        tome_animate = read_json(
            ROOT / "TwilightBossSliceR" / "entity" / "death_tome.entity.json"
        )["minecraft:client_entity"]["description"]["scripts"]["animate"]
        lich_weights = json.dumps(
            [
                weight
                for entry in lich_animate
                if isinstance(entry, dict)
                for alias, weight in entry.items()
                if alias.startswith("checker_compat_lich_source_pose_")
            ]
        )
        tome_weights = json.dumps(
            [
                weight
                for entry in tome_animate
                if isinstance(entry, dict)
                for alias, weight in entry.items()
                if alias.startswith("checker_compat_death_tome_fly_")
            ]
        )

        self.assertIn("variable.attack_time", lich_weights)
        self.assertEqual(lich["head"], lich["hat"])
        self.assertIn("297.9389", lich_weights)
        self.assertIn("191.3679", lich_weights)

        self.assertEqual([0, 90, 0], tome["root"]["rotation"])
        self.assertIn("math.sin(query.life_time * 343.7747)", tome_weights)
        self.assertIn("query.life_time * 20 + 90", tome_weights)
        self.assertEqual([0, -180, 50], tome["paper_storm"]["rotation"])
        for name in (
            "pages_right",
            "pages_left",
            "cover_right",
            "cover_left",
            "flipping_page_right",
            "flipping_page_left",
        ):
            rotation = tome[name]["rotation"]
            self.assertEqual(0, rotation[0], name)
            self.assertEqual(-180, rotation[1], name)
            self.assertEqual(0, rotation[2], name)
        for name in (
            "loose_page_0",
            "loose_page_1",
            "loose_page_2",
            "loose_page_3",
        ):
            self.assertEqual([-180, -180, -180], tome[name]["rotation"], name)

    def test_shadow_clone_uses_stable_dedicated_geometry_and_source_tint(self):
        client = read_json(CLONE_CLIENT_PATH)["minecraft:client_entity"]["description"]
        controller = read_json(RENDER_CONTROLLER_PATH)["render_controllers"][
            "controller.render.tf_slice.lich_clone"
        ]
        self.assertEqual(
            "textures/entity/tf_slice/twilightlich64_clone",
            client["textures"]["default"],
        )
        self.assertEqual("entity_alphatest", client["materials"]["default"])
        self.assertEqual(
            "geometry.tf_slice.lich_shadow_clone",
            client["geometry"]["default"],
        )
        self.assertNotIn("color", controller)
        self.assertNotIn("part_visibility", controller)

        clone_bones = bones("geometry.tf_slice.lich_shadow_clone")
        self.assertNotIn("collar", clone_bones)
        self.assertNotIn("cloak", clone_bones)
        for required in ("head", "hat", "body", "rightArm", "leftArm"):
            self.assertIn(required, clone_bones)

        source = Image.open(LICH_TEXTURE_PATH).convert("RGBA")
        clone = Image.open(CLONE_TEXTURE_PATH).convert("RGBA")
        self.assertEqual(source.size, clone.size)
        expected = [
            tuple(int(round(channel * 0.33)) for channel in pixel[:3])
            + (pixel[3],)
            for pixel in source.get_flattened_data()
        ]
        self.assertEqual(expected, list(clone.get_flattened_data()))

    def test_lich_projectiles_use_half_block_camera_billboards(self):
        clients = {
            "geometry.tf_slice.lich_bolt": read_json(
                ROOT / "TwilightBossSliceR" / "entity" / "lich_bolt.entity.json"
            )["minecraft:client_entity"]["description"],
            "geometry.tf_slice.lich_bomb": read_json(
                ROOT / "TwilightBossSliceR" / "entity" / "lich_bomb.entity.json"
            )["minecraft:client_entity"]["description"],
        }
        for identifier, client in clients.items():
            with self.subTest(identifier=identifier):
                self.assertEqual(identifier, client["geometry"]["default"])
                self.assertEqual(
                    "animation.actor.billboard",
                    client["animations"]["face_player"],
                )
                self.assertEqual(["face_player"], client["scripts"]["animate"])
                model = geometry(identifier)
                planes = [
                    bone["cubes"][0]
                    for bone in model["bones"]
                    if bone["name"].startswith("sprite_")
                ]
                self.assertEqual(1, len(planes))
                for plane in planes:
                    self.assertEqual([8, 8, 0], plane["size"])
                    self.assertNotIn("inflate", plane)

    def test_generated_files_are_reproducible(self):
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_preview_renderer_preserves_subpixel_book_sheets(self):
        from tools import render_entity_geo_preview

        cube = {
            "origin": [-8, 15, -4],
            "size": [5, 8, 0.005],
            "uv": [0, 10],
        }
        for face_index in range(6):
            _, dimensions, _ = render_entity_geo_preview.face_texture_data(
                cube,
                face_index,
            )
            self.assertGreater(dimensions[0], 0)
            self.assertGreater(dimensions[1], 0)
        atlas_origin, dimensions, _ = (
            render_entity_geo_preview.face_texture_data(cube, 0)
        )
        self.assertEqual((0, 10), atlas_origin)
        self.assertEqual((5, 8), dimensions)

        tome_bones = list(bones("geometry.tf_slice.death_tome").values())
        pose = render_entity_geo_preview.source_rest_pose(tome_bones)
        self.assertEqual([0, 90, 0], pose["root"]["rotation"])
        self.assertEqual([0, 0, -50], pose["book"]["rotation"])
        self.assertEqual([0, -8, 0], pose["book"]["position"])
        self.assertAlmostEqual(
            64.45775, pose["pages_right"]["rotation"][1]
        )
        self.assertAlmostEqual(
            -64.45775, pose["pages_left"]["rotation"][1]
        )
        expected_shift = math.sin(math.radians(64.45775))
        self.assertAlmostEqual(
            expected_shift, pose["pages_right"]["position"][0]
        )
        self.assertEqual(
            [0, 90, 50], pose["paper_storm"]["rotation"]
        )

        by_name = dict((bone["name"], bone) for bone in tome_bones)
        book_center = render_entity_geo_preview.transformed_point(
            (0, 24, 0), "book", by_name, pose
        )
        storm_center = render_entity_geo_preview.transformed_point(
            (0, 24, 0), "paper_storm", by_name, pose
        )
        self.assertAlmostEqual(8.0, storm_center[1] - book_center[1])

        lich_bones = list(bones("geometry.tf_slice.lich").values())
        pose = render_entity_geo_preview.source_rest_pose(lich_bones)
        self.assertEqual([-90, -5.7296, 11.4592], pose["rightArm"])
        self.assertEqual([-180, 5.7296, 17.1887], pose["leftArm"])

    def test_preview_renderer_applies_animation_translation_before_parent_pose(self):
        from tools import render_entity_geo_preview

        by_name = {
            "root": {"name": "root", "pivot": [0, 0, 0]},
            "child": {
                "name": "child",
                "parent": "root",
                "pivot": [0, 0, 0],
            },
        }
        pose = {
            "root": {"rotation": [0, 90, 0]},
            "child": {
                "rotation": [0, 0, 0],
                "position": [1, 2, 3],
            },
        }
        transformed = render_entity_geo_preview.transformed_point(
            (0, 0, 0), "child", by_name, pose
        )
        self.assertAlmostEqual(3, transformed[0])
        self.assertAlmostEqual(2, transformed[1])
        self.assertAlmostEqual(-1, transformed[2])

    def test_preview_renderer_supports_per_face_uv_for_flat_shield_layers(self):
        from tools import render_entity_geo_preview

        cube = {
            "origin": [-8, 8, -11.2],
            "size": [16, 16, 0],
            "uv": {
                "north": {"uv": [0, 0], "uv_size": [16, 16]},
                "south": {"uv": [16, 0], "uv_size": [-16, 16]},
            },
        }
        front = render_entity_geo_preview.face_texture_data(cube, 0)
        back = render_entity_geo_preview.face_texture_data(cube, 1)
        self.assertEqual(((0, 0), (16, 16)), front[:2])
        self.assertEqual(((0, 0), (16, 16)), back[:2])
        self.assertIsNone(
            render_entity_geo_preview.face_texture_data(cube, 2)
        )


if __name__ == "__main__":
    unittest.main()
