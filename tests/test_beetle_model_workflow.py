import hashlib
import json
import math
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT.parent / "twilightforest-1.20.1-4.3.2508-extracted" / "00_original_tree"
GEOMETRY_PATH = ROOT / "TwilightBossSliceR" / "models" / "entity" / "ruin_mobs.geo.json"
ANIMATION_PATH = ROOT / "TwilightBossSliceR" / "animations" / "ruin_mobs.animation.json"

BEETLES = {
    "fire_beetle": {
        "model_class": "twilightforest.client.model.entity.FireBeetleModel",
        "model_hash": "41C4A5C2C1D8D9BB74931034A485FBF9B5083C95C7B0EB9DC55D660B8F8C2954",
        "entity_hash": "F6CE6248694EF4835D36D433A26C108AA2C0B2A7CAAAD658E74D03CE7D278C58",
        "texture": "firebeetle.png",
        "texture_hash": "8F958C7EF43EE7B2CA0E3D67969A99B8A167585F385E8A6CDD52D10C63A0E388",
        "texture_size": (64, 32),
        "bone_count": 19,
        "collision": (1.1, 0.5),
        "health": 25,
        "attack": 4,
        "armor": None,
    },
    "slime_beetle": {
        "model_class": "twilightforest.client.model.entity.SlimeBeetleModel",
        "model_hash": "4617868C71E3F818162D09C8B50B210334FD1E711F6CBAD3C6409A09A8602D7B",
        "entity_hash": "3DDA0ECD6DD7CD9349F2EEA7F241A1658C04F235F5A53EFC1E4350C7E3D1D4CF",
        "texture": "slimebeetle.png",
        "texture_hash": "E2D313D7269DCCD6A37546A86ED26D1470DFE3DD33EB1BA9D2EE782058A992E8",
        "texture_size": (64, 64),
        "bone_count": 18,
        "collision": (0.9, 0.5),
        "health": 25,
        "attack": 4,
        "armor": None,
    },
    "pinch_beetle": {
        "model_class": "twilightforest.client.model.entity.PinchBeetleModel",
        "model_hash": "237D74018C5EF24C6B2EB1612EA8746692AFDF941372412D04EFF492D40C234B",
        "entity_hash": "50F8A287F171A61B5897B4CACEC8A89FC5DDBB01F10302C8F93D43C350BCE59B",
        "texture": "pinchbeetle.png",
        "texture_hash": "EB5338F7E5105CBA121E833B8D44E889DB982282333E5FE0C4D5CE0873373013",
        "texture_size": (64, 32),
        "bone_count": 25,
        "collision": (1.2, 0.5),
        "health": 40,
        "attack": 4,
        "armor": 2,
    },
}


def load_json(path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def png_size(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("%s is not a PNG" % path)
    return (
        int.from_bytes(data[16:20], "big"),
        int.from_bytes(data[20:24], "big"),
    )


def geometry(identifier):
    document = load_json(GEOMETRY_PATH)
    return next(
        item
        for item in document["minecraft:geometry"]
        if item["description"]["identifier"] == identifier
    )


def bones(identifier):
    return {bone["name"]: bone for bone in geometry(identifier)["bones"]}


def assert_vector(testcase, expected, actual, message):
    testcase.assertEqual(len(expected), len(actual), message)
    for expected_value, actual_value in zip(expected, actual):
        testcase.assertAlmostEqual(
            float(expected_value), float(actual_value), places=4, msg=message
        )


class BeetleModelWorkflowTests(unittest.TestCase):
    def test_locked_classic_sources_and_texture_hashes(self):
        registry = load_json(ROOT / "model_acceptance" / "registry.json")
        entries = {entry["id"]: entry for entry in registry["entities"]}
        jar = ROOT.parent / "[暮色森林] twilightforest-1.20.1-4.3.2508-universal.jar"
        with zipfile.ZipFile(jar) as archive:
            self.assertNotIn("assets/twilightforest/jappa_models.marker", archive.namelist())

        for entity_id, expected in BEETLES.items():
            entry = entries[entity_id]
            self.assertEqual("candidate", entry["status"])
            self.assertEqual(expected["model_class"], entry["source"]["model_class"])
            self.assertIn("classic", entry["source"]["model_branch"])

            model_path = UPSTREAM / (
                expected["model_class"].replace(".", "/") + ".class"
            )
            entity_path = UPSTREAM / (
                "twilightforest/entity/monster/"
                + "".join(part.title() for part in entity_id.split("_"))
                + ".class"
            )
            source_texture = (
                UPSTREAM
                / "assets"
                / "twilightforest"
                / "textures"
                / "model"
                / expected["texture"]
            )
            target_texture = (
                ROOT
                / "TwilightBossSliceR"
                / "textures"
                / "entity"
                / "tf_slice"
                / (entity_id + ".png")
            )
            self.assertEqual(expected["model_hash"], sha256(model_path))
            self.assertEqual(expected["entity_hash"], sha256(entity_path))
            self.assertEqual(expected["texture_hash"], sha256(source_texture))
            self.assertEqual(expected["texture_hash"], sha256(target_texture))
            self.assertEqual(expected["texture_size"], png_size(target_texture))

    def test_fire_beetle_geometry_matches_classic_source(self):
        model = geometry("geometry.tf_slice.fire_beetle")
        self.assertEqual(64, model["description"]["texture_width"])
        self.assertEqual(32, model["description"]["texture_height"])
        by_name = bones("geometry.tf_slice.fire_beetle")
        self.assertEqual(BEETLES["fire_beetle"]["bone_count"], len(by_name))

        expected = {
            "head": (None, [0, 5, -5], [-4, 3, -11], [8, 6, 6], [0, 0], None),
            "right_antenna": (
                "head", [1, 8, -10], [1, 7.5, -10.5], [10, 1, 1], [42, 4],
                [0, 60, 17],
            ),
            "jaw_1b": (
                "jaw_1a", [-3, 5, -13], [-3, 4, -13], [1, 1, 2], [0, 0],
                [0, 90, 0],
            ),
            "rear": (
                None, [0, 6, 7], [-6, 1, 3], [12, 14, 9], [22, 9],
                [90, 0, 0],
            ),
            "leg_1": (
                None, [-4, 3, 4], [-13, 2, 3], [10, 2, 2], [40, 0],
                [0, 40, 20],
            ),
        }
        self._assert_bones(by_name, expected)

    def test_slime_beetle_geometry_preserves_tail_hierarchy(self):
        model = geometry("geometry.tf_slice.slime_beetle")
        self.assertEqual(64, model["description"]["texture_width"])
        self.assertEqual(64, model["description"]["texture_height"])
        by_name = bones("geometry.tf_slice.slime_beetle")
        self.assertEqual(BEETLES["slime_beetle"]["bone_count"], len(by_name))

        expected = {
            "body": (
                None, [0, 6, 7], [-4, 7, 3], [8, 10, 8], [31, 6],
                [90, 0, 0],
            ),
            "tail1": (None, [0, 5, 9], [-3, 2, 6], [6, 6, 6], [0, 20], None),
            "tail2": (
                "tail1", [0, 8, 11], [-3, 8, 8], [6, 6, 6], [0, 20], None,
            ),
            "slime_center": (
                "tail2", [0, 14, 11], [-4, 16, 4], [8, 8, 8], [32, 24], None,
            ),
            "slime_cube": (
                "slime_center", [0, 14, 11], [-6, 14, 2], [12, 12, 12],
                [0, 40], None,
            ),
            "front_right_leg": (
                None, [-2, 3, -4], [-11, 2, -5], [10, 2, 2], [40, 0],
                [0, -16, 20],
            ),
        }
        self._assert_bones(by_name, expected)

    def test_pinch_beetle_geometry_preserves_articulated_jaws(self):
        by_name = bones("geometry.tf_slice.pinch_beetle")
        self.assertEqual(BEETLES["pinch_beetle"]["bone_count"], len(by_name))
        expected = {
            "right_jaw_bottom": (
                "head", [-3, 4, -11], [-4, 3, -12.5], [8, 2, 3], [40, 6],
                [0, 151, 0],
            ),
            "right_jaw_top": (
                "right_jaw_bottom", [4, 4, -11], [3, 3, -12], [10, 2, 2],
                [40, 10], [0, -60, 0],
            ),
            "right_tooth_1": (
                "right_jaw_top", [13, 4, -11], [13, 3.5, -11], [2, 1, 1],
                [0, 0], [0, -30, 0],
            ),
            "left_jaw_bottom": (
                "head", [3, 4, -11], [2, 3, -12.5], [8, 2, 3], [40, 6],
                [0, 31, 0],
            ),
            "left_tooth_3": (
                "left_jaw_top", [13.5, 4, -11], [13.5, 3.5, -11], [2, 1, 1],
                [0, 0], [0, -90, 0],
            ),
            "rear": (
                None, [0, 6, 7], [-5, 5, 3], [10, 10, 8], [28, 14],
                [90, 0, 0],
            ),
        }
        self._assert_bones(by_name, expected)

    def _assert_bones(self, by_name, expected):
        for name, (parent, pivot, origin, size, uv, rotation) in expected.items():
            bone = by_name[name]
            if parent is None:
                self.assertNotIn("parent", bone, name)
            else:
                self.assertEqual(parent, bone.get("parent"), name)
            assert_vector(self, pivot, bone["pivot"], name + " pivot")
            cube = bone["cubes"][0]
            assert_vector(self, origin, cube["origin"], name + " origin")
            assert_vector(self, size, cube["size"], name + " size")
            assert_vector(self, uv, cube["uv"], name + " uv")
            if rotation is None:
                self.assertNotIn("rotation", bone, name)
            else:
                assert_vector(self, rotation, bone["rotation"], name + " rotation")

    def test_client_bindings_and_source_specific_animations(self):
        expected_materials = {
            "fire_beetle": "entity_alphatest",
            "slime_beetle": "entity_alphablend",
            "pinch_beetle": "entity_alphatest",
        }
        animations = load_json(ANIMATION_PATH)["animations"]
        for entity_id, material in expected_materials.items():
            client = load_json(
                ROOT / "TwilightBossSliceR" / "entity" / (entity_id + ".entity.json")
            )["minecraft:client_entity"]["description"]
            self.assertEqual(material, client["materials"]["default"])
            self.assertEqual(
                "geometry.tf_slice." + entity_id, client["geometry"]["default"]
            )
            move_id = "animation.tf_slice.%s.move" % entity_id
            self.assertEqual(move_id, client["animations"]["move"])
            self.assertIn(move_id, animations)

        slime = animations["animation.tf_slice.slime_beetle.move"]["bones"]
        self.assertIn("tail1", slime)
        self.assertIn("tail2", slime)
        self.assertIn("slime_center", slime)
        pinch = animations["animation.tf_slice.pinch_beetle.move"]["bones"]
        self.assertIn("right_jaw_bottom", pinch)
        self.assertIn("query.has_rider", str(pinch["right_jaw_bottom"]))

    def test_server_attributes_collision_and_goal_order_match_source(self):
        for entity_id, expected in BEETLES.items():
            entity = load_json(
                ROOT / "TwilightBossSliceB" / "entities" / (entity_id + ".entity.json")
            )["minecraft:entity"]
            components = entity["components"]
            self.assertEqual(expected["health"], components["minecraft:health"]["value"])
            self.assertEqual(0.23, components["minecraft:movement"]["value"])
            self.assertEqual(expected["attack"], components["minecraft:attack"]["damage"])
            self.assertEqual(
                expected["collision"][0], components["minecraft:collision_box"]["width"]
            )
            self.assertEqual(
                expected["collision"][1], components["minecraft:collision_box"]["height"]
            )
            if expected["armor"] is None:
                self.assertNotIn("minecraft:armor", components)
            else:
                self.assertEqual(
                    expected["armor"], components["minecraft:armor"]["value"]
                )
            self.assertEqual(0, components["minecraft:behavior.float"]["priority"])
            self.assertEqual(
                1, components["minecraft:behavior.hurt_by_target"]["priority"]
            )
            self.assertEqual(
                2,
                components["minecraft:behavior.nearest_attackable_target"]["priority"],
            )
            movement_goals = components
            if entity_id in ("pinch_beetle", "fire_beetle"):
                movement_goals = entity["component_groups"]["tf_slice:normal_ai"]
            self.assertEqual(
                6, movement_goals["minecraft:behavior.random_stroll"]["priority"]
            )
            self.assertEqual(
                1.0,
                movement_goals["minecraft:behavior.random_stroll"]["speed_multiplier"],
            )

        fire = load_json(
            ROOT / "TwilightBossSliceB" / "entities" / "fire_beetle.entity.json"
        )["minecraft:entity"]
        self.assertNotIn("minecraft:behavior.ranged_attack", fire["components"])
        self.assertNotIn("minecraft:shooter", fire["components"])
        self.assertEqual(
            3,
            fire["component_groups"]["tf_slice:normal_ai"]
            ["minecraft:behavior.melee_attack"]["priority"],
        )
        self.assertIn("tf_slice:breathing", fire["component_groups"])

        slime = load_json(
            ROOT / "TwilightBossSliceB" / "entities" / "slime_beetle.entity.json"
        )["minecraft:entity"]["components"]
        self.assertEqual(2, slime["minecraft:behavior.avoid_mob_type"]["priority"])
        self.assertEqual(3, slime["minecraft:behavior.ranged_attack"]["priority"])
        self.assertEqual(10, slime["minecraft:behavior.ranged_attack"]["attack_radius"])
        self.assertEqual("tf_slice:slime_blob", slime["minecraft:shooter"]["def"])
        self.assertNotIn("minecraft:behavior.melee_attack", slime)

        pinch = load_json(
            ROOT / "TwilightBossSliceB" / "entities" / "pinch_beetle.entity.json"
        )["minecraft:entity"]
        self.assertNotIn(
            "minecraft:behavior.charge_attack", pinch["components"]
        )
        self.assertIn("minecraft:rideable", pinch["components"])
        self.assertEqual(
            4,
            pinch["component_groups"]["tf_slice:normal_ai"]
            ["minecraft:behavior.melee_attack"]["priority"],
        )

    def test_projectile_contracts_exist(self):
        fire = load_json(
            ROOT / "TwilightBossSliceB" / "entities" / "fire_breath.entity.json"
        )["minecraft:entity"]["components"]["minecraft:projectile"]
        self.assertEqual(2, fire["on_hit"]["impact_damage"]["damage"])
        self.assertEqual(10, fire["on_fire_time"])
        self.assertEqual(0, fire["gravity"])

        slime = load_json(
            ROOT / "TwilightBossSliceB" / "entities" / "slime_blob.entity.json"
        )["minecraft:entity"]["components"]
        self.assertFalse(slime["minecraft:physics"]["has_gravity"])
        slime = slime["minecraft:projectile"]
        self.assertEqual(4, slime["on_hit"]["impact_damage"]["damage"])
        self.assertAlmostEqual(0.006, slime["gravity"], places=6)
        self.assertEqual(6.0, slime["uncertainty_base"])


if __name__ == "__main__":
    unittest.main()
