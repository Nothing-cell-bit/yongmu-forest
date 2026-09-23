# -*- coding: utf-8 -*-
import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
ANIMAL_SPECS = {
    "bighorn_sheep": {
        "weight": 12,
        "herd": (4, 4),
        "texture": "bighorn.png",
        "geometry": "geometry.tf_slice.bighorn_sheep",
        "bones": {
            "body",
            "head",
            "left_horn",
            "right_horn",
            "leg0",
            "leg1",
            "leg2",
            "leg3",
        },
        "renderer": "controller.render.tf_slice.bighorn_sheep",
    },
    "boar": {
        "weight": 10,
        "herd": (4, 4),
        "texture": "wildboar.png",
        "geometry": "geometry.tf_slice.boar",
        "bones": {"body", "head", "leg0", "leg1", "leg2", "leg3"},
        "renderer": "controller.render.default",
    },
    "deer": {
        "weight": 15,
        "herd": (4, 5),
        "texture": "wilddeer.png",
        "geometry": "geometry.tf_slice.deer",
        "bones": {
            "body",
            "neck",
            "head",
            "left_antler",
            "right_antler",
            "leg0",
            "leg1",
            "leg2",
            "leg3",
        },
        "renderer": "controller.render.tf_slice.deer",
    },
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def png_dimensions(path):
    data = path.read_bytes()
    return struct.unpack(">II", data[16:24])


class ForestAnimalBehaviorContractTests(unittest.TestCase):
    def test_server_client_and_spawn_rule_identifiers_are_closed(self):
        for name in ANIMAL_SPECS:
            entity_id = "tf_slice:%s" % name
            behavior = read_json(
                BP / "entities" / ("%s.entity.json" % name)
            )["minecraft:entity"]
            client = read_json(
                RP / "entity" / ("%s.entity.json" % name)
            )["minecraft:client_entity"]
            spawn_rule = read_json(
                BP / "spawn_rules" / ("%s.json" % name)
            )["minecraft:spawn_rules"]

            self.assertEqual(
                entity_id, behavior["description"]["identifier"]
            )
            self.assertEqual(
                entity_id, client["description"]["identifier"]
            )
            self.assertEqual(
                entity_id, spawn_rule["description"]["identifier"]
            )

    def test_natural_spawns_match_upstream_groups_and_stay_in_twilight(self):
        for name, spec in ANIMAL_SPECS.items():
            spawn_rule = read_json(
                BP / "spawn_rules" / ("%s.json" % name)
            )["minecraft:spawn_rules"]
            self.assertEqual(
                "animal", spawn_rule["description"]["population_control"]
            )
            condition = spawn_rule["conditions"][0]
            self.assertIn("minecraft:spawns_on_surface", condition)
            self.assertEqual(
                "minecraft:grass",
                condition["minecraft:spawns_on_block_filter"],
            )
            self.assertEqual(
                7, condition["minecraft:brightness_filter"]["min"]
            )
            self.assertEqual(
                spec["weight"], condition["minecraft:weight"]["default"]
            )
            herd = condition["minecraft:herd"]
            self.assertEqual(
                spec["herd"], (herd["min_size"], herd["max_size"])
            )
            self.assertEqual(
                {"surface": 8, "underground": 0},
                condition["minecraft:density_limit"],
            )
            condition_text = json.dumps(condition)
            self.assertIn("dm33027004", condition_text)
            self.assertIn("tf_slice_default_creatures", condition_text)

    def test_animals_are_passive_breedable_and_have_growth_and_loot(self):
        for name in ANIMAL_SPECS:
            entity = read_json(
                BP / "entities" / ("%s.entity.json" % name)
            )["minecraft:entity"]
            families = entity["components"]["minecraft:type_family"][
                "family"
            ]
            self.assertIn("tf_slice_forest_animal", families)
            self.assertIn("animal", families)
            self.assertNotIn("monster", families)
            self.assertNotIn("minecraft:attack", entity["components"])
            self.assertIn("tf_slice:adult", entity["component_groups"])
            self.assertIn("tf_slice:baby", entity["component_groups"])
            self.assertIn("minecraft:entity_born", entity["events"])
            self.assertIn("tf_slice:grow_up", entity["events"])
            breeds_with = entity["component_groups"]["tf_slice:adult"][
                "minecraft:breedable"
            ]["breeds_with"]
            self.assertEqual(
                "tf_slice:%s" % name, breeds_with["mate_type"]
            )
            self.assertEqual(
                "tf_slice:%s" % name, breeds_with["baby_type"]
            )
            self.assertEqual(
                {
                    "event": "minecraft:entity_born",
                    "target": "baby",
                },
                breeds_with["breed_event"],
            )

            loot_path = entity["components"]["minecraft:loot"]["table"]
            loot = read_json(BP / loot_path)
            self.assertTrue(loot["pools"])


class ForestAnimalResourceContractTests(unittest.TestCase):
    def test_models_use_mobile_quadruped_rigs_and_original_textures(self):
        geometry = read_json(
            RP / "models" / "entity" / "forest_animals.geo.json"
        )["minecraft:geometry"]
        geometries = {
            entry["description"]["identifier"]: entry for entry in geometry
        }
        for name, spec in ANIMAL_SPECS.items():
            client = read_json(
                RP / "entity" / ("%s.entity.json" % name)
            )["minecraft:client_entity"]["description"]
            self.assertEqual(
                spec["geometry"], client["geometry"]["default"]
            )
            bones = {
                bone["name"]
                for bone in geometries[spec["geometry"]]["bones"]
            }
            self.assertEqual(spec["bones"], bones)
            self.assertEqual(
                [spec["renderer"]], client["render_controllers"]
            )
            texture_path = RP / "textures" / "entity" / spec["texture"]
            self.assertTrue(texture_path.is_file())
            self.assertEqual((64, 32), png_dimensions(texture_path))
            self.assertTrue(client["spawn_egg"])

        deer_bones = {
            bone["name"]: bone
            for bone in geometries["geometry.tf_slice.deer"]["bones"]
        }
        self.assertIn("cubes", deer_bones["neck"])
        self.assertEqual("body", deer_bones["neck"]["parent"])

    def test_loot_uses_upstream_meat_counts_cooking_and_looting(self):
        expected_meat = {
            "bighorn_sheep": ("minecraft:muttonRaw", 1, 2),
            "boar": ("minecraft:porkchop", 1, 3),
            "deer": ("tf_slice:raw_venison", 1, 3),
        }
        for name, (item_id, minimum, maximum) in expected_meat.items():
            loot = read_json(
                BP / "loot_tables" / "entities" / ("%s.json" % name)
            )
            entries = [
                entry
                for pool in loot["pools"]
                for entry in pool["entries"]
            ]
            meat = next(entry for entry in entries if entry["name"] == item_id)
            functions = meat["functions"]
            count = next(
                item["count"]
                for item in functions
                if item["function"] == "set_count"
            )
            self.assertEqual(
                {"min": minimum, "max": maximum}, count
            )
            self.assertIn(
                "furnace_smelt",
                {item["function"] for item in functions},
            )
            self.assertIn(
                "looting_enchant",
                {item["function"] for item in functions},
            )

    def test_deer_uses_original_sound_bank_and_venison_items(self):
        definitions = read_json(
            RP / "sounds" / "sound_definitions.json"
        )["sound_definitions"]
        self.assertTrue(
            {
                "tf_slice.deer.ambient",
                "tf_slice.deer.hurt",
                "tf_slice.deer.death",
            }.issubset(set(definitions)),
        )
        for filename in (
            "idle1.ogg",
            "idle2.ogg",
            "idle3.ogg",
            "hurt1.ogg",
            "hurt2.ogg",
            "death.ogg",
        ):
            self.assertTrue(
                (RP / "sounds" / "mob" / "deer" / filename).is_file()
            )
        for item_name in ("raw_venison", "cooked_venison"):
            item_document = read_json(
                BP / "items" / ("%s.item.json" % item_name)
            )
            item = item_document["minecraft:item"]
            self.assertEqual("1.21.60", item_document["format_version"])
            self.assertEqual(
                "tf_slice:%s" % item_name,
                item["description"]["identifier"],
            )
            self.assertNotIn("menu_category", item["description"])
            self.assertEqual(
                {
                    "textures": {
                        "default": "tf_slice:%s" % item_name
                    }
                },
                item["components"]["minecraft:icon"],
            )
            self.assertEqual(
                "eat", item["components"]["minecraft:use_animation"]
            )
            self.assertEqual(
                {"use_duration": 1.6, "movement_modifier": 0.35},
                item["components"]["minecraft:use_modifiers"],
            )
            self.assertTrue(
                (RP / "textures" / "items" / ("%s.png" % item_name)).is_file()
            )
        catalog = read_json(
            BP / "item_catalog" / "crafting_item_catalog.json"
        )["minecraft:crafting_items_catalog"]
        item_category = next(
            category
            for category in catalog["categories"]
            if category["category_name"] == "items"
        )
        item_ids = {
            identifier
            for group in item_category.get("groups", [])
            for identifier in group.get("items", [])
        }
        self.assertTrue(
            {"tf_slice:raw_venison", "tf_slice:cooked_venison"} <= item_ids
        )
    def test_spawn_eggs_localization_catalog_and_sounds_are_complete(self):
        catalog = read_json(
            BP / "item_catalog" / "crafting_item_catalog.json"
        )
        catalog_text = json.dumps(catalog)
        sounds = read_json(RP / "sounds.json")["entity_sounds"]["entities"]
        language_text = "\n".join(
            (RP / "texts" / language).read_text(encoding="utf-8")
            for language in ("zh_CN.lang", "en_US.lang")
        )

        for name in ANIMAL_SPECS:
            entity_id = "tf_slice:%s" % name
            self.assertIn(
                "tf_slice:%s_spawn_egg" % name, catalog_text
            )
            self.assertIn(entity_id, sounds)
            self.assertIn("entity.%s.name=" % entity_id, language_text)
            self.assertIn(
                "item.spawn_egg.entity.%s.name=" % entity_id,
                language_text,
            )


if __name__ == "__main__":
    unittest.main()
