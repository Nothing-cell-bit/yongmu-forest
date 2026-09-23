# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import spawn_policy


ANIMALS = {
    "tiny_bird": (15, 4, 8, 4),
    "squirrel": (10, 2, 4, 1),
    "dwarf_rabbit": (10, 4, 5, 3),
    "raven": (10, 1, 2, 1),
}
DIMENSION_ID = 33027004


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class BiomeAnimalsExpansionContractTests(unittest.TestCase):
    def test_animals_have_server_client_spawn_and_texture_contracts(self):
        for name, (weight, herd_min, herd_max, texture_count) in (
            ANIMALS.items()
        ):
            entity = read_json(BP / "entities" / ("%s.entity.json" % name))
            self.assertEqual(
                "tf_slice:%s" % name,
                entity["minecraft:entity"]["description"]["identifier"],
            )
            client = read_json(RP / "entity" / ("%s.entity.json" % name))
            description = client["minecraft:client_entity"]["description"]
            self.assertEqual("tf_slice:%s" % name, description["identifier"])
            self.assertEqual(texture_count, len(description["textures"]))
            for texture in description["textures"].values():
                self.assertTrue((RP / ("%s.png" % texture)).is_file())

            rule = read_json(BP / "spawn_rules" / ("%s.json" % name))[
                "minecraft:spawn_rules"
            ]
            condition = rule["conditions"][0]
            self.assertEqual(weight, condition["minecraft:weight"]["default"])
            self.assertEqual(
                {"min_size": herd_min, "max_size": herd_max},
                condition["minecraft:herd"],
            )
            self.assertIn(
                "tf_slice_default_creatures",
                json.dumps(condition["minecraft:biome_filter"]),
            )

    def test_existing_forest_animals_use_the_non_spooky_creature_tag(self):
        for name in ("bighorn_sheep", "boar", "deer"):
            rule = read_json(BP / "spawn_rules" / ("%s.json" % name))
            encoded = json.dumps(rule)
            self.assertIn("tf_slice_default_creatures", encoded)
            self.assertNotIn(
                '"value": "tf_slice_twilight_forest"',
                encoded,
            )

    def test_small_animals_use_distinct_upstream_shaped_models(self):
        geometry_entries = read_json(
            RP / "models" / "entity" / "biome_animals.geo.json"
        )["minecraft:geometry"]
        geometries = {
            entry["description"]["identifier"]: entry
            for entry in geometry_entries
        }
        expected = {
            "tiny_bird": {
                "geometry": "geometry.tf_slice.tiny_bird",
                "bones": {
                    "body",
                    "head",
                    "beak",
                    "right_wing",
                    "left_wing",
                    "right_leg",
                    "left_leg",
                    "tail",
                },
                "body_size": [3, 3, 3],
                "max_cube_size": 3,
            },
            "squirrel": {
                "geometry": "geometry.tf_slice.squirrel",
                "bones": {
                    "body",
                    "head",
                    "tail",
                    "fluff_1",
                    "fluff_2",
                    "fluff_3",
                    "leg0",
                    "leg1",
                    "leg2",
                    "leg3",
                },
                "body_size": [4, 3, 5],
                "max_cube_size": 5,
            },
            "dwarf_rabbit": {
                "geometry": "geometry.tf_slice.dwarf_rabbit",
                "bones": {
                    "body",
                    "head",
                    "leg0",
                    "leg1",
                    "leg2",
                    "leg3",
                },
                "body_size": [4, 3, 5],
                "max_cube_size": 5,
            },
        }

        for name, spec in expected.items():
            client = read_json(
                RP / "entity" / ("%s.entity.json" % name)
            )["minecraft:client_entity"]["description"]
            self.assertEqual(spec["geometry"], client["geometry"]["default"])
            self.assertIn(spec["geometry"], geometries)

            model = geometries[spec["geometry"]]
            bones = {bone["name"]: bone for bone in model["bones"]}
            self.assertTrue(spec["bones"].issubset(bones), name)
            self.assertEqual(
                spec["body_size"],
                bones["body"]["cubes"][0]["size"],
                name,
            )

            cubes = [
                cube
                for bone in model["bones"]
                for cube in bone.get("cubes", [])
            ]
            self.assertEqual(
                0,
                min(cube["origin"][1] for cube in cubes),
                name,
            )
            self.assertLessEqual(
                max(max(cube["size"]) for cube in cubes),
                spec["max_cube_size"],
                name,
            )
            self._assert_box_uvs_fit_texture(model, name)

        squirrel = geometries["geometry.tf_slice.squirrel"]
        squirrel_parents = {
            bone["name"]: bone.get("parent") for bone in squirrel["bones"]
        }
        self.assertEqual("tail", squirrel_parents["fluff_1"])
        self.assertEqual("fluff_1", squirrel_parents["fluff_2"])
        self.assertEqual("fluff_2", squirrel_parents["fluff_3"])

        rabbit = geometries["geometry.tf_slice.dwarf_rabbit"]
        rabbit_head = next(
            bone for bone in rabbit["bones"] if bone["name"] == "head"
        )
        self.assertEqual(3, len(rabbit_head["cubes"]))
        self.assertEqual(
            [[2, 4, 1], [2, 4, 1]],
            [cube["size"] for cube in rabbit_head["cubes"][1:]],
        )

    def _assert_box_uvs_fit_texture(self, model, name):
        width = model["description"]["texture_width"]
        height = model["description"]["texture_height"]
        for bone in model["bones"]:
            for cube in bone.get("cubes", []):
                uv = cube["uv"]
                size_x, size_y, size_z = cube["size"]
                self.assertLessEqual(
                    uv[0] + (2 * (size_x + size_z)),
                    width,
                    "%s:%s" % (name, bone["name"]),
                )
                self.assertLessEqual(
                    uv[1] + size_z + size_y,
                    height,
                    "%s:%s" % (name, bone["name"]),
                )

    def test_vanilla_passive_mobs_are_only_allowed_in_default_biomes(self):
        forest_args = {
            "identifier": "minecraft:chicken",
            "realIdentifier": "minecraft:chicken",
            "dimensionId": DIMENSION_ID,
        }
        self.assertFalse(
            spawn_policy.should_cancel_twilight_spawn(
                forest_args,
                DIMENSION_ID,
                biome_identifier="dm33027004_plains",
            )
        )
        self.assertTrue(
            spawn_policy.should_cancel_twilight_spawn(
                forest_args,
                DIMENSION_ID,
                biome_identifier="dm33027004_roofed_forest",
            )
        )

    def test_spooky_vanilla_mobs_are_only_allowed_in_spooky_forest(self):
        for identifier in (
            "minecraft:bat",
            "minecraft:spider",
            "minecraft:skeleton",
        ):
            args = {
                "identifier": identifier,
                "realIdentifier": identifier,
                "dimensionId": DIMENSION_ID,
            }
            self.assertFalse(
                spawn_policy.should_cancel_twilight_spawn(
                    args,
                    DIMENSION_ID,
                    biome_identifier="dm33027004_roofed_forest",
                )
            )
            self.assertTrue(
                spawn_policy.should_cancel_twilight_spawn(
                    args,
                    DIMENSION_ID,
                    biome_identifier="dm33027004_plains",
                )
            )

    def test_server_resolves_biome_before_applying_spawn_policy(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        callback = source[source.index("def OnServerSpawnMob") :]
        policy_call = callback.index(
            "spawn_policy.should_cancel_twilight_spawn"
        )
        self.assertIn("biome_identifier", callback[: policy_call + 500])
        self.assertIn("_biome_comp.GetBiomeName", source)


if __name__ == "__main__":
    unittest.main()
