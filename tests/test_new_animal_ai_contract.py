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

from TwilightBossSlice import forest_animal_logic
from TwilightBossSlice import quest_ram_logic


SEEDS = {
    "minecraft:wheat_seeds",
    "minecraft:pumpkin_seeds",
    "minecraft:melon_seeds",
    "minecraft:beetroot_seeds",
}
RABBIT_FOOD = {
    "minecraft:carrot",
    "minecraft:golden_carrot",
    "minecraft:dandelion",
}
PREDATORS = {"wolf", "cat", "ocelot", "fox"}


def read_entity(name):
    path = BP / "entities" / ("%s.entity.json" % name)
    return json.loads(path.read_text(encoding="utf-8"))["minecraft:entity"]


def avoided_families(component):
    result = {}
    for entry in component["entity_types"]:
        filters = entry["filters"]
        result[filters["value"]] = entry
    return result


class ExactAnimalAiContractTests(unittest.TestCase):
    def test_quest_ram_matches_432508_goals_and_home(self):
        components = read_entity("quest_ram")["components"]
        self.assertEqual(
            {"restriction_radius": 13},
            components["minecraft:home"],
        )
        self.assertEqual(
            {"priority": 1, "speed_multiplier": 1.38},
            components["minecraft:behavior.panic"],
        )
        tempt = components["minecraft:behavior.tempt"]
        self.assertEqual(3, tempt["priority"])
        self.assertEqual(1.0, tempt["speed_multiplier"])
        self.assertEqual(
            set(quest_ram_logic.WOOL_ITEMS),
            set(tempt["items"]),
        )
        self.assertEqual(
            1.0,
            components["minecraft:behavior.random_stroll"][
                "speed_multiplier"
            ],
        )
        self.assertIn("minecraft:interact", components)

    def test_tiny_bird_matches_attributes_goals_and_flight_states(self):
        entity = read_entity("tiny_bird")
        components = entity["components"]
        self.assertEqual(
            {"value": 1, "max": 1},
            components["minecraft:health"],
        )
        self.assertEqual(
            {"value": 0.2},
            components["minecraft:movement"],
        )
        self.assertNotIn("minecraft:despawn", components)
        self.assertFalse(
            components["minecraft:pushable"]["is_pushable"]
        )
        self.assertEqual(
            0, components["minecraft:behavior.panic"]["priority"]
        )
        tempt = components["minecraft:behavior.tempt"]
        self.assertEqual(3, tempt["priority"])
        self.assertEqual(SEEDS, set(tempt["items"]))

        avoid = avoided_families(
            components["minecraft:behavior.avoid_mob_type"]
        )
        self.assertEqual({"cat", "ocelot"}, set(avoid))
        for entry in avoid.values():
            self.assertEqual(8, entry["max_dist"])
            self.assertEqual(1.0, entry["walk_speed_multiplier"])
            self.assertEqual(1.25, entry["sprint_speed_multiplier"])

        landed = entity["component_groups"]["tf_slice:landed"]
        flying = entity["component_groups"]["tf_slice:flying"]
        self.assertIn("minecraft:movement.basic", landed)
        self.assertIn("minecraft:navigation.walk", landed)
        self.assertIn("minecraft:movement.fly", flying)
        self.assertIn("minecraft:navigation.fly", flying)
        self.assertIn("minecraft:can_fly", flying)
        self.assertIn("tf_slice:take_off", entity["events"])
        self.assertIn("tf_slice:land", entity["events"])

    def test_squirrel_matches_attributes_avoidance_and_path_bias(self):
        components = read_entity("squirrel")["components"]
        self.assertEqual(
            {"value": 1, "max": 1},
            components["minecraft:health"],
        )
        self.assertNotIn("minecraft:despawn", components)
        self.assertEqual(
            {"priority": 1, "speed_multiplier": 1.38},
            components["minecraft:behavior.panic"],
        )
        tempt = components["minecraft:behavior.tempt"]
        self.assertEqual(2, tempt["priority"])
        self.assertEqual(1.0, tempt["speed_multiplier"])
        self.assertEqual(SEEDS, set(tempt["items"]))

        avoid = avoided_families(
            components["minecraft:behavior.avoid_mob_type"]
        )
        self.assertEqual(PREDATORS | {"player"}, set(avoid))
        self.assertEqual(2, avoid["player"]["max_dist"])
        for family in PREDATORS:
            self.assertEqual(8, avoid[family]["max_dist"])
        for entry in avoid.values():
            self.assertEqual(0.8, entry["walk_speed_multiplier"])
            self.assertEqual(1.4, entry["sprint_speed_multiplier"])

        preferred = components["minecraft:preferred_path"]
        costs = {
            block: entry["cost"]
            for entry in preferred["preferred_path_blocks"]
            for block in entry["blocks"]
        }
        self.assertLess(costs["minecraft:oak_log"], costs["minecraft:oak_leaves"])
        self.assertLess(
            costs["minecraft:oak_leaves"], costs["minecraft:dirt"]
        )
        self.assertLess(
            costs["minecraft:dirt"], preferred["default_block_cost"]
        )
        self.assertNotIn("minecraft:breedable", components)

    def test_dwarf_rabbit_matches_breeding_avoidance_and_path_bias(self):
        entity = read_entity("dwarf_rabbit")
        components = entity["components"]
        self.assertNotIn("minecraft:despawn", components)
        self.assertEqual(
            {"priority": 1, "speed_multiplier": 2.0},
            components["minecraft:behavior.panic"],
        )
        tempt = components["minecraft:behavior.tempt"]
        self.assertEqual(2, tempt["priority"])
        self.assertEqual(1.0, tempt["speed_multiplier"])
        self.assertEqual(RABBIT_FOOD, set(tempt["items"]))

        adult = entity["component_groups"]["tf_slice:adult"]
        self.assertEqual(
            {"priority": 2, "speed_multiplier": 0.8},
            adult["minecraft:behavior.breed"],
        )
        breedable = adult["minecraft:breedable"]
        self.assertEqual(RABBIT_FOOD, set(breedable["breed_items"]))
        self.assertEqual(
            {"variant": 0.05},
            breedable["mutation_factor"],
        )
        self.assertIn("minecraft:entity_born", entity["events"])
        self.assertIn("tf_slice:grow_up", entity["events"])

        avoid = avoided_families(
            components["minecraft:behavior.avoid_mob_type"]
        )
        self.assertEqual(PREDATORS | {"player"}, set(avoid))
        self.assertEqual(3, avoid["player"]["priority"])
        self.assertEqual(2, avoid["player"]["max_dist"])
        self.assertEqual(1.33, avoid["player"]["sprint_speed_multiplier"])
        for family in PREDATORS:
            self.assertEqual(4, avoid[family]["priority"])
            self.assertEqual(8, avoid[family]["max_dist"])
            self.assertEqual(1.1, avoid[family]["sprint_speed_multiplier"])

        preferred = components["minecraft:preferred_path"]
        costs = {
            block: entry["cost"]
            for entry in preferred["preferred_path_blocks"]
            for block in entry["blocks"]
        }
        self.assertLess(
            costs["minecraft:dirt"], preferred["default_block_cost"]
        )
        self.assertGreater(
            costs["minecraft:oak_leaves"], preferred["default_block_cost"]
        )
        self.assertGreater(
            costs["minecraft:oak_log"], preferred["default_block_cost"]
        )

    def test_runtime_wires_item_navigation_interaction_and_bird_flight(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        for marker in (
            '"PlayerDoInteractServerEvent"',
            "_process_quest_ram_offerings()",
            "_navigate_quest_ram_to_wool",
            "quest_ram_logic.can_consume_wool",
            "_update_tiny_birds()",
            "forest_animal_logic.tiny_bird_motion",
            '"tf_slice:take_off"',
            '"tf_slice:land"',
        ):
            self.assertIn(marker, source)

    def test_unloaded_tiny_birds_are_pruned_after_first_missing_position(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        start = source.index("    def _update_tiny_birds(self):")
        handler = source[
            start:source.index("    def _update_penguins(self):", start)
        ]
        missing_start = handler.index(
            "            if pos is None or dimensionId is None:"
        )
        missing_branch = handler[
            missing_start:handler.index(
                '            state["dimensionId"] = dimensionId',
                missing_start,
            )
        ]

        self.assertIn(
            "self._tiny_birds.pop(entityId, None)",
            missing_branch,
        )

    def test_unloaded_penguins_are_pruned_after_first_missing_position(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        start = source.index("    def _update_penguins(self):")
        handler = source[
            start:source.index("    def _get_health(", start)
        ]
        missing_start = handler.index(
            "            if pos is None or dimensionId is None:"
        )
        missing_branch = handler[
            missing_start:handler.index("            try:", missing_start)
        ]

        self.assertIn(
            "self._penguins.discard(entityId)",
            missing_branch,
        )

    def test_unloaded_quest_offerings_are_pruned_after_missing_item_data(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        start = source.index("    def _process_quest_ram_offerings(self):")
        handler = source[
            start:source.index("    def _register_tiny_bird(", start)
        ]
        missing_start = handler.index("            if not item:")
        missing_branch = handler[
            missing_start:handler.index(
                "            itemName = portal_logic.item_name(item)",
                missing_start,
            )
        ]

        self.assertIn(
            "self._pending_quest_offerings.pop(itemEntityId, None)",
            missing_branch,
        )

    def test_small_animal_sound_contracts_are_closed(self):
        sounds = json.loads(
            (RP / "sounds.json").read_text(encoding="utf-8")
        )["entity_sounds"]["entities"]
        definitions = json.loads(
            (RP / "sounds" / "sound_definitions.json").read_text(
                encoding="utf-8"
            )
        )["sound_definitions"]
        for entity_id in (
            "tf_slice:quest_ram",
            "tf_slice:tiny_bird",
            "tf_slice:dwarf_rabbit",
        ):
            self.assertIn(entity_id, sounds)
        for event in (
            "tf_slice.tiny_bird.chirp",
            "tf_slice.tiny_bird.hurt",
            "tf_slice.tiny_bird.song",
            "tf_slice.tiny_bird.takeoff",
        ):
            self.assertIn(event, definitions)
        for filename in (
            "chirp1.ogg",
            "chirp2.ogg",
            "chirp3.ogg",
            "hurt1.ogg",
            "hurt2.ogg",
            "song1.ogg",
            "song2.ogg",
        ):
            self.assertTrue(
                (RP / "sounds" / "mob" / "tiny_bird" / filename).is_file()
            )


class ExactAnimalAiLogicTests(unittest.TestCase):
    def test_quest_ram_only_eats_settled_visible_wool_in_reach(self):
        self.assertTrue(
            quest_ram_logic.can_consume_wool(6.24, True, True)
        )
        self.assertFalse(
            quest_ram_logic.can_consume_wool(6.25, True, True)
        )
        self.assertFalse(
            quest_ram_logic.can_consume_wool(1.0, False, True)
        )
        self.assertFalse(
            quest_ram_logic.can_consume_wool(1.0, True, False)
        )

    def test_tiny_bird_spook_and_takeoff_match_432508(self):
        self.assertTrue(
            forest_animal_logic.is_tiny_bird_spooked(True, ())
        )
        self.assertTrue(
            forest_animal_logic.is_tiny_bird_spooked(
                False, ("minecraft:stick",)
            )
        )
        self.assertFalse(
            forest_animal_logic.is_tiny_bird_spooked(
                False, ("minecraft:wheat_seeds",)
            )
        )
        self.assertTrue(
            forest_animal_logic.should_tiny_bird_take_off(
                spooked=True,
                in_water=False,
                landable=True,
                random_roll=199,
            )
        )
        self.assertTrue(
            forest_animal_logic.should_tiny_bird_take_off(
                spooked=False,
                in_water=False,
                landable=False,
                random_roll=0,
            )
        )
        self.assertFalse(
            forest_animal_logic.should_tiny_bird_take_off(
                spooked=False,
                in_water=False,
                landable=True,
                random_roll=0,
            )
        )

    def test_tiny_bird_motion_uses_upstream_acceleration_and_gravity(self):
        motion = forest_animal_logic.tiny_bird_motion(
            current_motion=(0.0, -1.0, 0.0),
            position=(0.0, 10.0, 0.0),
            target=(5.0, 12.0, -5.0),
        )
        self.assertAlmostEqual(0.05, motion[0], places=6)
        self.assertAlmostEqual(-0.47, motion[1], places=6)
        self.assertAlmostEqual(-0.05, motion[2], places=6)


if __name__ == "__main__":
    unittest.main()
