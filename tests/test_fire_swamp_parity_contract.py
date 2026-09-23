# -*- coding: utf-8 -*-
import importlib
import io
import json
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
PACKAGE_ROOT = BP
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
TOOLS_ROOT = ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

import build_ruin_structures
from native_structure_worldgen_safety import base_iterations


def read_json(path):
    return json.loads(path.read_text("utf-8"))


def read_mcstructure(path):
    stream = io.BytesIO(path.read_bytes())
    root_type = struct.unpack("B", stream.read(1))[0]
    if root_type != build_ruin_structures.TAG_COMPOUND:
        raise ValueError("mcstructure root is not a compound")
    build_ruin_structures._read_string(stream, "<")
    return build_ruin_structures._read_payload(stream, root_type, "<")


class FireSwampDeviceLogicTests(unittest.TestCase):
    def setUp(self):
        self.logic = importlib.import_module(
            "TwilightBossSlice.fire_swamp_logic"
        )

    def test_smoker_matches_four_tick_source_cadence(self):
        state = self.logic.new_device("tf_slice:smoker")
        events = []
        for _tick in range(8):
            state, emitted = self.logic.tick_device(state)
            events.extend(emitted)
        self.assertEqual(["smoke", "smoke"], events)

    def test_natural_fire_jet_matches_source_timing_and_returns_idle(self):
        state = self.logic.new_device("tf_slice:fire_jet")
        state, event = self.logic.ignite_natural_jet(state, True)
        self.assertEqual("consume_lava", event)
        self.assertEqual("popping", state["phase"])

        pop_events = []
        for _tick in range(80):
            state, emitted = self.logic.tick_device(state)
            pop_events.extend(emitted)
        self.assertEqual("flame", state["phase"])
        self.assertEqual(0, state["counter"])
        self.assertEqual(["pop", "pop", "pop"], pop_events)

        flame_events = []
        for _tick in range(61):
            state, emitted = self.logic.tick_device(state)
            flame_events.extend(emitted)
        self.assertEqual("idle", state["phase"])
        self.assertEqual(13, flame_events.count("damage"))
        self.assertEqual(31, flame_events.count("flame"))

    def test_encased_devices_follow_redstone_latch_contract(self):
        jet = self.logic.new_device("tf_slice:encased_fire_jet")
        jet, events = self.logic.apply_power(jet, True)
        self.assertEqual(("jet_start",), events)
        self.assertEqual("popping", jet["phase"])
        for _tick in range(141):
            jet, _events = self.logic.tick_device(jet)
        self.assertEqual("timeout", jet["phase"])
        jet, events = self.logic.apply_power(jet, False)
        self.assertEqual("idle", jet["phase"])
        self.assertEqual((), events)

        smoker = self.logic.new_device("tf_slice:encased_smoker")
        smoker, events = self.logic.apply_power(smoker, True)
        self.assertTrue(smoker["active"])
        self.assertEqual(("smoker_toggle",), events)
        smoker, events = self.logic.apply_power(smoker, False)
        self.assertFalse(smoker["active"])
        self.assertEqual(("smoker_toggle",), events)

    def test_fire_jet_damage_contract_is_source_sized(self):
        self.assertEqual(
            ((8, 64, 18), (12, 68, 22)),
            self.logic.fire_jet_damage_bounds((10, 64, 20)),
        )
        self.assertEqual(2, self.logic.FIRE_JET_DAMAGE)
        self.assertEqual(15, self.logic.FIRE_JET_SECONDS)


class FireSwampBlockContractTests(unittest.TestCase):
    def _block(self, name):
        return read_json(BP / "netease_blocks" / (name + ".json"))[
            "minecraft:block"
        ]

    def test_jets_expose_source_states_and_flame_light(self):
        for name, expected in (
            ("fire_jet", ["idle", "popping", "flame"]),
            (
                "encased_fire_jet",
                ["idle", "popping", "flame", "timeout"],
            ),
        ):
            block = self._block(name)
            self.assertEqual(
                expected,
                block["description"]["states"]["tf_slice:jet_state"],
            )
            flame = next(
                entry
                for entry in block["permutations"]
                if "'flame'" in entry["condition"]
            )
            self.assertEqual(
                15, flame["components"]["minecraft:light_emission"]
            )

    def test_encased_smoker_exposes_power_state(self):
        block = self._block("encased_smoker")
        self.assertEqual(
            ["off", "on"],
            block["description"]["states"]["tf_slice:active"],
        )

    def test_encased_fire_jet_is_dark_until_the_flame_phase(self):
        block = self._block("encased_fire_jet")
        self.assertNotIn("minecraft:light_emission", block["components"])

    def test_fire_swamp_devices_use_source_blast_resistance(self):
        for name in (
            "smoker",
            "fire_jet",
            "encased_smoker",
            "encased_fire_jet",
        ):
            block = self._block(name)
            resistance = block["components"].get(
                "minecraft:destructible_by_explosion"
            )
            if isinstance(resistance, dict):
                resistance = resistance.get("explosion_resistance")
            self.assertEqual(6.0, resistance, name)

    def test_devices_and_recipe_casing_use_default_self_drops(self):
        for name in (
            "smoker",
            "fire_jet",
            "encased_smoker",
            "encased_fire_jet",
            "encased_towerwood",
        ):
            block = self._block(name)
            self.assertNotIn("minecraft:loot", block["components"], name)


class FireSwampWorldgenContractTests(unittest.TestCase):
    def test_smoker_and_fire_jet_restore_four_source_candidates_per_chunk(self):
        for kind in ("smoker", "jet"):
            rule = read_json(
                BP
                / "netease_feature_rules"
                / ("fire_swamp_%s_feature_rule.json" % kind)
            )["minecraft:feature_rules"]
            self.assertEqual(
                "tf_slice:fire_swamp_%s_feature" % kind,
                rule["description"]["places_feature"],
            )
            self.assertEqual(
                4,
                base_iterations(rule["distribution"]["iterations"]),
            )
            self.assertEqual(
                "after_surface_pass", rule["conditions"]["placement_pass"]
            )

    def test_each_candidate_validates_once_then_places_one_atomic_structure(self):
        for kind in ("smoker", "jet"):
            sequence = read_json(
                BP / "netease_features" / ("fire_swamp_%s_feature.json" % kind)
            )["minecraft:sequence_feature"]
            self.assertEqual(
                [
                    "tf_slice:fire_swamp_device_anchor_feature",
                    "tf_slice:fire_swamp_%s_structure_offset_feature" % kind,
                ],
                sequence["features"],
            )

            offset = read_json(
                BP
                / "netease_features"
                / ("fire_swamp_%s_structure_offset_feature.json" % kind)
            )["minecraft:scatter_feature"]
            self.assertEqual(
                "tf_slice:fire_swamp_%s_structure_feature" % kind,
                offset["places_feature"],
            )
            self.assertEqual(
                (-2, -2, -2),
                tuple(offset["distribution"][axis] for axis in "xyz"),
            )

            native = read_json(
                BP
                / "netease_features"
                / ("fire_swamp_%s_structure_feature.json" % kind)
            )["netease:structure_feature"]
            structure_name = {
                "jet": "fire_jet",
                "smoker": "smoker",
            }[kind]
            self.assertEqual(
                "tf_slice:fire_swamp/%s" % structure_name,
                native["places_structure"],
            )

    def test_device_structures_match_the_source_visible_terrain_profile(self):
        for kind in ("smoker", "fire_jet"):
            structure = read_mcstructure(
                BP
                / "structures"
                / "tf_slice"
                / "fire_swamp"
                / (kind + ".mcstructure")
            )
            self.assertEqual([5, 3, 5], structure["size"])
            body = structure["structure"]
            palette = body["palette"]["default"]["block_palette"]
            primary = body["block_indices"][0]
            self.assertNotIn(-1, primary)

            def block_at(x, y, z):
                index = x * 3 * 5 + y * 5 + z
                return palette[primary[index]]["name"]

            for x in range(5):
                for z in range(5):
                    self.assertEqual("minecraft:stone", block_at(x, 0, z))
                    reservoir = (
                        "minecraft:lava"
                        if 1 <= x <= 3 and 1 <= z <= 3
                        else "minecraft:stone"
                    )
                    self.assertEqual(reservoir, block_at(x, 1, z))
                    surface = (
                        "tf_slice:%s" % kind
                        if (x, z) == (2, 2)
                        else "minecraft:grass_block"
                    )
                    self.assertEqual(surface, block_at(x, 2, z))

    def test_lava_lake_surrogate_is_multi_block_at_one_in_ten_rarity(self):
        lake = read_json(
            BP / "netease_features" / "fire_swamp_lava_lake_feature.json"
        )["minecraft:scatter_feature"]
        self.assertEqual(
            "tf_slice:fire_swamp_lava_feature", lake["places_feature"]
        )
        self.assertGreaterEqual(lake["iterations"], 24)

        rule = read_json(
            BP
            / "netease_feature_rules"
            / "fire_swamp_lava_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(
            "tf_slice:fire_swamp_lava_lake_feature",
            rule["description"]["places_feature"],
        )
        self.assertIn("< 0.10", str(rule["distribution"]["iterations"]))

    def test_fire_swamp_restores_ruins_groundcover_and_oak_ecology(self):
        biome = read_json(
            BP
            / "netease_biomes"
            / "dm33027004"
            / "dm33027004_swampland_mutated.json"
        )["minecraft:biome"]["components"]
        self.assertIn("tf_slice_small_ruins", biome)
        self.assertIn("tf_slice_terrestrial_groundcover", biome)

        rule = read_json(
            BP
            / "netease_feature_rules"
            / "fire_swamp_swampy_oak_tree_feature_rule.json"
        )["minecraft:feature_rules"]
        projected = read_json(
            BP
            / "netease_features"
            / (
                "%s.json"
                % rule["description"]["places_feature"].split(":", 1)[1]
            )
        )["minecraft:scatter_feature"]
        self.assertEqual(
            "tf_slice:swampy_oak_tree_feature",
            projected["places_feature"],
        )
        self.assertTrue(projected["project_input_to_floor"])
        self.assertEqual(1, projected["distribution"]["iterations"])

    def test_layout_keeps_a_fire_seed_inside_a_supported_swamp_envelope(self):
        stages = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]["netease:biome_source"]
        base = next(stage for stage in stages if stage["type"] == "random_with_weight")
        base_ids = {entry["biome_type"] for entry in base["pool"]}
        self.assertTrue(
            {
                "dm33027004_mushroom_island",
                "dm33027004_birch_forest_mutated",
                "dm33027004_sunflower_plains",
                "dm33027004_roofed_forest",
            }.issubset(base_ids)
        )
        conditions = [stage for stage in stages if stage["type"] == "condition"]
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        builder = importlib.import_module("tools.build_dark_forest_biomes")
        seed_specs = builder.route_seed_stage_specs()
        self.assertEqual(8, len(conditions))
        self.assertEqual(
            catalog.route_biome_seed_condition(
                seed_specs[0]["geometryByVariant"],
            ),
            conditions[0]["condition"],
        )
        self.assertEqual(["dm33027004_swampland"], conditions[0]["pool"])
        self.assertEqual(
            catalog.route_biome_seed_condition(
                seed_specs[1]["geometryByVariant"],
            ),
            conditions[1]["condition"],
        )
        self.assertEqual(
            ["dm33027004_swampland_mutated"],
            conditions[1]["pool"],
        )
        self.assertFalse(
            any(
                "get_neighborhood_is_biome" in stage["condition"]
                for stage in conditions
            )
        )
        self.assertFalse(any(stage["type"] == "associated" for stage in stages))


class FireSwampAcquisitionContractTests(unittest.TestCase):
    def test_encased_towerwood_is_a_registered_source_visual_block(self):
        catalog = read_json(ROOT / "docs" / "hydra_route_content.json")
        self.assertIn("encased_towerwood", catalog["fireSwampBlocks"])
        adaptation = catalog["platformAdaptations"]["encasedTowerwood"]
        self.assertEqual("twilightforest:towerwood", adaptation["sourceInput"])
        self.assertEqual(
            "tf_slice:towerwood", adaptation["implementedInput"]
        )

        block = read_json(
            BP / "netease_blocks" / "encased_towerwood.json"
        )["minecraft:block"]
        self.assertEqual(
            "tf_slice:encased_towerwood",
            block["description"]["identifier"],
        )
        resistance = block["components"][
            "minecraft:destructible_by_explosion"
        ]["explosion_resistance"]
        self.assertEqual(6.0, resistance)
        self.assertTrue(
            (RP / "textures" / "blocks" / "encased_towerwood.png").is_file()
        )
        terrain = read_json(RP / "textures" / "terrain_texture.json")
        self.assertEqual(
            "textures/blocks/encased_towerwood",
            terrain["texture_data"]["tf_slice:encased_towerwood"]["textures"],
        )

        categories = read_json(
            BP / "item_catalog" / "crafting_item_catalog.json"
        )["minecraft:crafting_items_catalog"]["categories"]
        creative = {
            identifier
            for category in categories
            for group in category.get("groups", [])
            for identifier in group.get("items", [])
        }
        self.assertIn("tf_slice:encased_towerwood", creative)
        for language in ("en_US.lang", "zh_CN.lang"):
            text = (RP / "texts" / language).read_text("utf-8")
            self.assertIn("tile.tf_slice:encased_towerwood.name=", text)

    def test_platform_stonecutter_recipe_uses_the_ported_towerwood_route(self):
        recipe = read_json(
            BP / "recipes" / "encased_towerwood_stonecutting.recipe.json"
        )["minecraft:recipe_shapeless"]
        self.assertEqual(["stonecutter"], recipe["tags"])
        self.assertEqual(
            [{"item": "tf_slice:towerwood"}], recipe["ingredients"]
        )
        self.assertEqual(
            {"item": "tf_slice:encased_towerwood", "count": 1},
            recipe["result"],
        )

    def test_encased_device_recipes_match_the_locked_source_patterns(self):
        cases = {
            "encased_smoker": {
                "pattern": ["ERE", "RSR", "ERE"],
                "center": "tf_slice:smoker",
            },
            "encased_fire_jet": {
                "pattern": ["ERE", "RJR", "LLL"],
                "center": "tf_slice:fire_jet",
            },
        }
        for name, expected in cases.items():
            recipe = read_json(
                BP / "recipes" / (name + ".recipe.json")
            )["minecraft:recipe_shaped"]
            self.assertEqual(expected["pattern"], recipe["pattern"])
            self.assertEqual(
                {"item": "tf_slice:encased_towerwood"}, recipe["key"]["E"]
            )
            self.assertEqual(
                {"item": "minecraft:redstone"}, recipe["key"]["R"]
            )
            center_key = "S" if name == "encased_smoker" else "J"
            self.assertEqual(
                {"item": expected["center"]}, recipe["key"][center_key]
            )
            if name == "encased_fire_jet":
                self.assertEqual(
                    {"item": "minecraft:lava_bucket"}, recipe["key"]["L"]
                )
            self.assertEqual(
                {"item": "tf_slice:%s" % name, "count": 1},
                recipe["result"],
            )


class FireSwampClientContractTests(unittest.TestCase):
    def test_source_water_color_and_non_firefly_ash_texture(self):
        biome = read_json(
            RP / "biomes" / "dm33027004_swampland_mutated.client_biome.json"
        )["minecraft:client_biome"]["components"]
        self.assertEqual(
            "#6C2C2C", biome["minecraft:water_appearance"]["surface_color"]
        )
        ash = read_json(RP / "particles" / "fire_swamp_ash.json")[
            "particle_effect"
        ]
        texture = ash["description"]["basic_render_parameters"]["texture"]
        self.assertNotIn("firefly", texture)

    def test_server_and_client_wire_device_effects_and_dry_climate(self):
        server = (BP / "TwilightBossSlice" / "serverSystem.py").read_text("utf-8")
        client = (BP / "TwilightBossSlice" / "clientSystem.py").read_text("utf-8")
        self.assertIn("fire_swamp_logic", server)
        self.assertIn("_update_fire_swamp_devices()", server)
        self.assertIn('"FireSwampDeviceEffect"', server)
        self.assertIn("SetBiomeInfo", server)
        self.assertIn("_configure_fire_swamp_climate()", server)
        self.assertIn('"FireSwampDeviceEffect"', client)
        self.assertIn("OnFireSwampDeviceEffect", client)


if __name__ == "__main__":
    unittest.main()
