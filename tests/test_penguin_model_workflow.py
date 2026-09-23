# -*- coding: utf-8 -*-
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import forest_animal_logic


TEXTURE_HASH = (
    "DAC97F52CCF021443BDFCEACEAA0641ED84125D2A226BD34A53549162AC16776"
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class PenguinSourceLockTests(unittest.TestCase):
    def test_registry_locks_exact_432508_penguin_source(self):
        registry = read_json(ROOT / "model_acceptance" / "registry.json")
        penguin = next(
            entry
            for entry in registry["entities"]
            if entry["id"] == "penguin"
        )
        self.assertEqual("candidate", penguin["status"])
        self.assertEqual(
            "twilightforest.client.model.entity.PenguinModel",
            penguin["source"]["model_class"],
        )
        self.assertEqual(
            "twilightforest.client.renderer.entity.BirdRenderer",
            penguin["source"]["renderer_class"],
        )
        self.assertEqual(
            "twilightforest.entity.passive.Penguin",
            penguin["source"]["entity_class"],
        )
        self.assertEqual(0.375, penguin["source"]["shadow_radius"])
        self.assertEqual(TEXTURE_HASH, penguin["source"]["textures"][0]["sha256"])
        offline_path = ROOT / penguin["offline_evidence"]
        offline = read_json(offline_path)
        self.assertEqual("candidate", offline["status"])
        for names in (
            offline["offline"]["views"],
            offline["offline"]["poses"],
        ):
            for path in names.values():
                self.assertEqual(
                    b"\x89PNG\r\n\x1a\n",
                    (ROOT / path).read_bytes()[:8],
                )

    def test_original_texture_is_copied_byte_for_byte(self):
        source = (
            ROOT.parent
            / "twilightforest-1.20.1-4.3.2508-extracted"
            / "00_original_tree"
            / "assets"
            / "twilightforest"
            / "textures"
            / "model"
            / "penguin.png"
        )
        target = RP / "textures" / "entity" / "tf_slice" / "penguin.png"
        self.assertEqual(TEXTURE_HASH, sha256(source))
        self.assertEqual(TEXTURE_HASH, sha256(target))


class PenguinGeometryContractTests(unittest.TestCase):
    def setUp(self):
        document = read_json(
            RP / "models" / "entity" / "penguin.geo.json"
        )
        self.model = document["minecraft:geometry"][0]
        self.bones = {
            bone["name"]: bone for bone in self.model["bones"]
        }

    def test_geometry_matches_penguin_model_create_bytecode(self):
        description = self.model["description"]
        self.assertEqual(
            "geometry.tf_slice.penguin",
            description["identifier"],
        )
        self.assertEqual((64, 32), (
            description["texture_width"],
            description["texture_height"],
        ))
        self.assertEqual(
            {
                "body",
                "head",
                "hat",
                "beak",
                "right_arm",
                "left_arm",
                "right_leg",
                "left_leg",
            },
            set(self.bones),
        )
        expected = {
            "body": ([0, 10, 0], [-4, 1, -4], [8, 9, 8], [32, 0]),
            "head": (
                [0, 11, 0],
                [-3.5, 10, -3.5],
                [7, 5, 7],
                [0, 0],
            ),
            "beak": ([0, 12, -4], [-1, 11, -5], [2, 1, 2], [0, 13]),
            "right_arm": (
                [-4, 9, 0],
                [-5, 2, -2],
                [1, 8, 4],
                [34, 18],
            ),
            "left_arm": (
                [4, 9, 0],
                [4, 2, -2],
                [1, 8, 4],
                [24, 18],
            ),
            "right_leg": (
                [-2, 1, 0],
                [-4, 0, -5],
                [4, 1, 8],
                [0, 16],
            ),
            "left_leg": (
                [2, 1, 0],
                [0, 0, -5],
                [4, 1, 8],
                [0, 16],
            ),
        }
        for name, (pivot, origin, size, uv) in expected.items():
            bone = self.bones[name]
            self.assertEqual(pivot, bone["pivot"], name)
            self.assertEqual(1, len(bone["cubes"]), name)
            self.assertEqual(origin, bone["cubes"][0]["origin"], name)
            self.assertEqual(size, bone["cubes"][0]["size"], name)
            self.assertEqual(uv, bone["cubes"][0]["uv"], name)
        self.assertEqual("head", self.bones["beak"]["parent"])
        self.assertNotIn("cubes", self.bones["hat"])

    def test_client_binding_and_source_motion_are_explicit(self):
        description = read_json(
            RP / "entity" / "penguin.entity.json"
        )["minecraft:client_entity"]["description"]
        self.assertEqual("tf_slice:penguin", description["identifier"])
        self.assertEqual(
            "textures/entity/tf_slice/penguin",
            description["textures"]["default"],
        )
        self.assertEqual(
            "geometry.tf_slice.penguin",
            description["geometry"]["default"],
        )
        self.assertEqual(
            "animation.tf_slice.penguin.source_motion",
            description["animations"]["source_motion"],
        )
        self.assertIn(
            {"source_motion": "query.modified_move_speed"},
            description["scripts"]["animate"],
        )
        self.assertIn(
            "look_at_target",
            description["scripts"]["animate"],
        )

        animation = read_json(
            RP / "animations" / "penguin.animation.json"
        )["animations"]["animation.tf_slice.penguin.source_motion"]
        bones = animation["bones"]
        self.assertIn("40.107", bones["right_leg"]["rotation"][0])
        self.assertIn("40.107", bones["left_leg"]["rotation"][0])
        self.assertIn("1145.9156", bones["right_arm"]["rotation"][2])
        self.assertIn("1145.9156", bones["left_arm"]["rotation"][2])


class PenguinAiContractTests(unittest.TestCase):
    def setUp(self):
        self.entity = read_json(
            BP / "entities" / "penguin.entity.json"
        )["minecraft:entity"]
        self.components = self.entity["components"]

    def test_attributes_and_goal_order_match_432508_bytecode(self):
        self.assertEqual(
            {"value": 10, "max": 10},
            self.components["minecraft:health"],
        )
        self.assertEqual(
            {"value": 0.2},
            self.components["minecraft:movement"],
        )
        self.assertEqual(
            {"priority": 0},
            self.components["minecraft:behavior.float"],
        )
        self.assertEqual(
            {"priority": 1, "speed_multiplier": 1.75},
            self.components["minecraft:behavior.panic"],
        )
        self.assertEqual(
            {
                "priority": 3,
                "speed_multiplier": 0.75,
                "items": ["minecraft:cod"],
            },
            self.components["minecraft:behavior.tempt"],
        )
        self.assertEqual(
            {"priority": 5, "speed_multiplier": 1.0},
            self.components["minecraft:behavior.random_stroll"],
        )
        self.assertEqual(
            {
                "priority": 6,
                "look_distance": 6,
                "probability": 0.02,
            },
            self.components["minecraft:behavior.look_at_player"],
        )
        self.assertEqual(
            {"priority": 8},
            self.components["minecraft:behavior.random_look_around"],
        )

    def test_breeding_follow_parent_and_same_species_look_are_preserved(self):
        adult = self.entity["component_groups"]["tf_slice:adult"]
        baby = self.entity["component_groups"]["tf_slice:baby"]
        self.assertEqual(
            {"priority": 2, "speed_multiplier": 1.0},
            adult["minecraft:behavior.breed"],
        )
        self.assertEqual(
            ["minecraft:cod"],
            adult["minecraft:breedable"]["breed_items"],
        )
        self.assertEqual(
            {"priority": 4, "speed_multiplier": 1.15},
            baby["minecraft:behavior.follow_parent"],
        )
        same_species = self.components[
            "minecraft:behavior.look_at_entity"
        ]
        self.assertEqual(7, same_species["priority"])
        self.assertEqual(5, same_species["look_distance"])
        self.assertEqual(0.02, same_species["probability"])
        self.assertIn("penguin", json.dumps(same_species))

    def test_slow_fall_and_fall_immunity_match_bird_and_entity_tags(self):
        self.assertEqual(
            (0.2, -0.6, -0.3),
            forest_animal_logic.penguin_slow_fall(
                (0.2, -1.0, -0.3),
                on_ground=False,
            ),
        )
        self.assertEqual(
            (0.2, -1.0, -0.3),
            forest_animal_logic.penguin_slow_fall(
                (0.2, -1.0, -0.3),
                on_ground=True,
            ),
        )
        self.assertIn(
            "_update_penguins()",
            (
                BP / "TwilightBossSlice" / "serverSystem.py"
            ).read_text(encoding="utf-8"),
        )
        triggers = self.components["minecraft:damage_sensor"]["triggers"]
        self.assertTrue(
            any(
                trigger.get("cause") == "fall"
                and trigger.get("deals_damage") is False
                for trigger in triggers
            )
        )

    def test_source_only_glacier_spawn_is_not_faked_in_missing_biome(self):
        self.assertFalse((BP / "spawn_rules" / "penguin.json").exists())
        self.assertTrue(
            self.entity["description"]["is_spawnable"],
            "spawn egg must remain available for the workflow test world",
        )

    def test_loot_localization_and_creative_spawn_egg_are_closed(self):
        loot = read_json(
            BP / "loot_tables" / "entities" / "tf_slice" / "penguin.json"
        )
        self.assertIn("minecraft:feather", json.dumps(loot))
        catalog = read_json(
            BP / "item_catalog" / "crafting_item_catalog.json"
        )
        self.assertIn(
            "tf_slice:penguin_spawn_egg",
            json.dumps(catalog),
        )
        self.assertIn(
            "entity.tf_slice:penguin.name=企鹅",
            (RP / "texts" / "zh_CN.lang").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "entity.tf_slice:penguin.name=Penguin",
            (RP / "texts" / "en_US.lang").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
