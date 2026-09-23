# -*- coding: utf-8 -*-
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import biome_catalog
from TwilightBossSlice import quest_ram_logic


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class QuestRamLogicTests(unittest.TestCase):
    def test_all_sixteen_wool_colors_are_required_once(self):
        self.assertEqual(16, len(quest_ram_logic.WOOL_COLORS))
        mask = 0
        for color in quest_ram_logic.WOOL_COLORS:
            result = quest_ram_logic.feed_wool(mask, False, color)
            self.assertTrue(result["accepted"])
            mask = result["mask"]
        self.assertEqual(quest_ram_logic.COMPLETE_MASK, mask)
        self.assertTrue(result["reward_due"])

        duplicate = quest_ram_logic.feed_wool(mask, True, "white")
        self.assertFalse(duplicate["accepted"])
        self.assertFalse(duplicate["reward_due"])
        self.assertEqual(mask, duplicate["mask"])

    def test_crumble_horn_only_uses_supported_vanilla_conversions(self):
        self.assertEqual(
            "minecraft:cobblestone",
            quest_ram_logic.CRUMBLE_RECIPES["minecraft:stone"],
        )
        self.assertEqual(
            "minecraft:gravel",
            quest_ram_logic.CRUMBLE_RECIPES["minecraft:cobblestone"],
        )
        self.assertEqual(
            "minecraft:air",
            quest_ram_logic.CRUMBLE_RECIPES["minecraft:gravel"],
        )
        self.assertNotIn("twilightforest:", json.dumps(
            quest_ram_logic.CRUMBLE_RECIPES
        ))


class QuestGroveContentContractTests(unittest.TestCase):
    def test_quest_ram_entity_matches_upstream_core_attributes(self):
        entity = read_json(BP / "entities" / "quest_ram.entity.json")[
            "minecraft:entity"
        ]
        components = entity["components"]
        self.assertEqual(70, components["minecraft:health"]["max"])
        self.assertEqual(0.23, components["minecraft:movement"]["value"])
        self.assertIn("minecraft:persistent", components)
        client = read_json(RP / "entity" / "quest_ram.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertTrue(
            (RP / ("%s.png" % client["textures"]["default"])).is_file()
        )

    def test_quest_ram_model_has_connected_source_rig_and_uvs(self):
        entity = read_json(BP / "entities" / "quest_ram.entity.json")[
            "minecraft:entity"
        ]
        self.assertLessEqual(
            entity["components"]["minecraft:scale"]["value"],
            1.0,
        )

        model = read_json(
            RP / "models" / "entity" / "quest_ram.geo.json"
        )["minecraft:geometry"][0]
        self.assertEqual(
            "geometry.tf_slice.quest_ram",
            model["description"]["identifier"],
        )
        self.assertEqual(128, model["description"]["texture_width"])
        self.assertEqual(128, model["description"]["texture_height"])

        bones = {bone["name"]: bone for bone in model["bones"]}
        self.assertTrue(
            {
                "body",
                "neck",
                "back_body",
                "head",
                "face",
                "leg0",
                "leg1",
                "leg2",
                "leg3",
            }.issubset(bones)
        )
        self.assertEqual([18, 15, 15], bones["body"]["cubes"][0]["size"])
        self.assertEqual("body", bones["neck"]["parent"])
        self.assertEqual("body", bones["head"]["parent"])
        self.assertEqual("head", bones["face"]["parent"])
        self.assertEqual(15, len(bones["head"]["cubes"]))
        self.assertEqual(1, len(bones["face"]["cubes"]))
        for leg_name in ("leg0", "leg1", "leg2", "leg3"):
            self.assertEqual(2, len(bones[leg_name]["cubes"]))

        def cube_axis_bounds(cubes, axis):
            return (
                min(cube["origin"][axis] for cube in cubes),
                max(
                    cube["origin"][axis] + cube["size"][axis]
                    for cube in cubes
                ),
            )

        neck_y = cube_axis_bounds(bones["neck"]["cubes"], 1)
        main_head_y = cube_axis_bounds(bones["head"]["cubes"][:1], 1)
        neck_head_y_overlap = min(neck_y[1], main_head_y[1]) - max(
            neck_y[0],
            main_head_y[0],
        )
        self.assertGreaterEqual(neck_head_y_overlap, 6)
        self.assertLessEqual(
            cube_axis_bounds(
                bones["head"]["cubes"] + bones["face"]["cubes"],
                1,
            )[1],
            50,
        )

        cubes = [
            cube
            for bone in model["bones"]
            for cube in bone.get("cubes", [])
        ]
        self.assertEqual(0, min(cube["origin"][1] for cube in cubes))
        for bone in model["bones"]:
            for cube in bone.get("cubes", []):
                uv = cube["uv"]
                size_x, size_y, size_z = cube["size"]
                self.assertLessEqual(
                    uv[0] + (2 * (size_x + size_z)),
                    128,
                    bone["name"],
                )
                self.assertLessEqual(
                    uv[1] + size_z + size_y,
                    128,
                    bone["name"],
                )

    def test_quest_ram_leg_pivots_are_on_the_attached_leg_cubes(self):
        model = read_json(
            RP / "models" / "entity" / "quest_ram.geo.json"
        )["minecraft:geometry"][0]
        bones = {bone["name"]: bone for bone in model["bones"]}

        for leg_name in ("leg0", "leg1", "leg2", "leg3"):
            leg = bones[leg_name]
            lower_leg = min(
                leg["cubes"],
                key=lambda cube: cube["origin"][1],
            )
            expected_pivot = [
                lower_leg["origin"][0] + lower_leg["size"][0] / 2.0,
                max(
                    cube["origin"][1] + cube["size"][1]
                    for cube in leg["cubes"]
                ),
                lower_leg["origin"][2] + lower_leg["size"][2] / 2.0,
            ]
            self.assertEqual(expected_pivot, leg["pivot"], leg_name)

    def test_quest_ram_uses_classic_segmented_horns_instead_of_slabs(self):
        model = read_json(
            RP / "models" / "entity" / "quest_ram.geo.json"
        )["minecraft:geometry"][0]
        bones = {bone["name"]: bone for bone in model["bones"]}
        head_cubes = bones["head"]["cubes"]
        horn_cubes = head_cubes[1:]

        self.assertEqual(14, len(horn_cubes))
        self.assertEqual([0, 70], head_cubes[0]["uv"])
        self.assertLessEqual(
            max(max(cube["size"]) for cube in horn_cubes),
            6,
        )

    def test_quest_ram_uses_one_coherent_classic_model_uv_layout(self):
        model = read_json(
            RP / "models" / "entity" / "quest_ram.geo.json"
        )["minecraft:geometry"][0]
        bones = {bone["name"]: bone for bone in model["bones"]}

        expected_cubes = {
            "body": [([18, 15, 15], [0, 0])],
            "back_body": [([18, 15, 15], [0, 30])],
            "neck": [([11, 14, 12], [66, 37])],
            "face": [([11, 9, 12], [54, 73])],
            "leg0": [
                ([6, 12, 6], [66, 0]),
                ([7, 10, 10], [90, 0]),
            ],
            "leg1": [
                ([6, 12, 6], [66, 0]),
                ([7, 10, 10], [90, 0]),
            ],
            "leg2": [
                ([6, 13, 6], [66, 18]),
                ([7, 10, 7], [90, 20]),
            ],
            "leg3": [
                ([6, 13, 6], [66, 18]),
                ([7, 10, 7], [90, 20]),
            ],
        }
        for bone_name, expected in expected_cubes.items():
            actual = [
                (cube["size"], cube["uv"])
                for cube in bones[bone_name]["cubes"]
            ]
            self.assertEqual(expected, actual, bone_name)

        classic_head = bones["head"]["cubes"]
        self.assertEqual([12, 9, 15], classic_head[0]["size"])
        self.assertEqual([0, 70], classic_head[0]["uv"])
        self.assertEqual(
            [
                [0, 94],
                [20, 96],
                [34, 95],
                [46, 98],
                [58, 95],
                [76, 95],
                [88, 97],
            ]
            * 2,
            [cube["uv"] for cube in classic_head[1:]],
        )

    def test_quest_ram_preview_samples_the_real_texture_atlas(self):
        renderer = ROOT / "tools" / "render_entity_geo_preview.py"
        geometry = RP / "models" / "entity" / "quest_ram.geo.json"
        texture = (
            RP
            / "textures"
            / "entity"
            / "tf_slice"
            / "quest_ram.png"
        )

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            real_output = directory / "real.png"
            probe_texture = directory / "probe.png"
            probe_output = directory / "probe-output.png"
            Image.new("RGB", (128, 128), (255, 0, 255)).save(
                probe_texture
            )

            for selected_texture, output in (
                (texture, real_output),
                (probe_texture, probe_output),
            ):
                subprocess.run(
                    [
                        sys.executable,
                        str(renderer),
                        str(geometry),
                        str(output),
                        "--texture",
                        str(selected_texture),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )

            self.assertNotEqual(
                real_output.read_bytes(),
                probe_output.read_bytes(),
            )
            with Image.open(probe_output) as rendered:
                magenta_pixels = sum(
                    red > 150 and green < 100 and blue > 150
                    for red, green, blue
                    in rendered.convert("RGB").get_flattened_data()
                )
            self.assertGreater(magenta_pixels, 5000)

    def test_quest_ram_nose_uses_the_bedrock_x_rotation_direction(self):
        model = read_json(
            RP / "models" / "entity" / "quest_ram.geo.json"
        )["minecraft:geometry"][0]
        bones = {bone["name"]: bone for bone in model["bones"]}
        self.assertEqual([30, 0, 0], bones["face"]["rotation"])

        tools_path = ROOT / "tools"
        if str(tools_path) not in sys.path:
            sys.path.insert(0, str(tools_path))
        import render_entity_geo_preview

        rotated = render_entity_geo_preview.apply_rotation(
            (0, 1, 0),
            (90, 0, 0),
            (0, 0, 0),
        )
        self.assertAlmostEqual(0, rotated[1], places=6)
        self.assertAlmostEqual(-1, rotated[2], places=6)

        head_vertices = [
            render_entity_geo_preview.transformed_point(
                point,
                "head",
                bones,
                {},
            )
            for point in render_entity_geo_preview.cube_vertices(
                bones["head"]["cubes"][0]
            )
        ]
        nose_vertices = [
            render_entity_geo_preview.transformed_point(
                point,
                "face",
                bones,
                {},
            )
            for point in render_entity_geo_preview.cube_vertices(
                bones["face"]["cubes"][0]
            )
        ]
        for axis, minimum_overlap in ((1, 6), (2, 10)):
            overlap = min(
                max(point[axis] for point in head_vertices),
                max(point[axis] for point in nose_vertices),
            ) - max(
                min(point[axis] for point in head_vertices),
                min(point[axis] for point in nose_vertices),
            )
            self.assertGreaterEqual(overlap, minimum_overlap)

    def test_quest_ram_uses_bounded_source_shaped_walk_and_look_animation(self):
        client = read_json(RP / "entity" / "quest_ram.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertEqual(
            "animation.tf_slice.quest_ram.walk",
            client["animations"]["walk"],
        )
        self.assertEqual(
            "animation.tf_slice.quest_ram.look",
            client["animations"]["look_at_target"],
        )

        animations = read_json(
            RP / "animations" / "quest_ram.animation.json"
        )["animations"]
        walk = animations["animation.tf_slice.quest_ram.walk"]["bones"]
        self.assertEqual(
            {"leg0", "leg1", "leg2", "leg3"},
            set(walk),
        )
        encoded_walk = json.dumps(walk)
        self.assertIn("math.min(query.modified_move_speed, 0.4)", encoded_walk)
        self.assertNotIn("80.22", encoded_walk)

        look = animations["animation.tf_slice.quest_ram.look"]["bones"]
        self.assertEqual({"head"}, set(look))
        encoded_look = json.dumps(look)
        self.assertIn("math.clamp(query.target_x_rotation", encoded_look)
        self.assertIn("math.clamp(query.target_y_rotation", encoded_look)

    def test_rewards_include_horn_trophy_and_locked_seven_resource_blocks(self):
        loot = read_json(
            BP / "loot_tables" / "entities" / "questing_ram_rewards.json"
        )
        encoded = json.dumps(loot)
        for item in (
            "tf_slice:crumble_horn",
            "tf_slice:quest_ram_trophy_item",
            "minecraft:coal_block",
            "minecraft:iron_block",
            "minecraft:copper_block",
            "minecraft:lapis_block",
            "minecraft:gold_block",
            "minecraft:diamond_block",
            "minecraft:emerald_block",
        ):
            self.assertIn(item, encoded)

    def test_quest_grove_is_an_enchanted_forest_landmark(self):
        catalog = read_json(
            BP
            / "structures"
            / "tf_slice"
            / "ruins"
            / "structure_catalog_v1.json"
        )
        entry = next(
            value
            for value in catalog["structures"]
            if value["id"] == "quest_grove"
        )
        self.assertEqual("landmark_service", entry["strategy"])
        self.assertIn("tf_slice_biome_enchanted_forest", entry["biomeTags"])
        self.assertIn("quest_ram", entry["dependencies"])
        self.assertEqual([0, 0, 0, 26, 9, 26], entry["bounds"])
        self.assertTrue(entry["pieces"])
        for piece in entry["pieces"]:
            self.assertLessEqual(piece["size"][0], 16)
            self.assertLessEqual(piece["size"][2], 16)
            self.assertTrue(
                (
                    BP
                    / "structures"
                    / ("%s.mcstructure" % piece["structure"])
                ).is_file()
            )

    def test_service_routes_enchanted_forest_to_quest_grove(self):
        source = (
            BP / "TwilightBossSlice" / "structureWorldgenService.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "biome_catalog.SPECIAL_LANDMARK_BY_BIOME",
            source,
        )
        self.assertEqual(
            biome_catalog.SPECIAL_LANDMARK_BY_BIOME[
                "dm33027004_birch_forest_mutated"
            ],
            "quest_grove",
        )
        self.assertIn(
            'if landmark_kind == "quest_grove":',
            source,
        )

    def test_server_processes_dropped_wool_and_crumble_horn_use(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_process_quest_ram_offerings()", source)
        self.assertIn("quest_ram_logic.feed_wool", source)
        self.assertIn('"ServerItemUseOnEvent"', source)
        self.assertIn("quest_ram_logic.CRUMBLE_RECIPES", source)


if __name__ == "__main__":
    unittest.main()
