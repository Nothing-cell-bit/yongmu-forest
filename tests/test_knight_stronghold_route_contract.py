# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
PACKAGE = BP / "TwilightBossSlice"
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

import release_metadata


def stronghold_entry():
    return next(
        value
        for value in catalog()["structures"]
        if value["id"] == "knight_stronghold"
    )


def catalog():
    return json.loads(
        (
            BP
            / "structures"
            / "tf_slice"
            / "ruins"
            / "structure_catalog_v1.json"
        ).read_text(encoding="utf-8")
    )


class KnightStrongholdCatalogContractTests(unittest.TestCase):
    def test_catalog_v3_contains_source_ported_variant_bank(self):
        document = catalog()
        self.assertEqual(3, document["schemaVersion"])
        entry = stronghold_entry()
        self.assertEqual("buried_entry", entry["placementProfile"])
        self.assertEqual(0, entry["entrySurfaceOffset"])
        self.assertEqual(64, entry["verticalSliceHeight"])
        self.assertEqual(
            "trophy_pedestal_activated", entry["structureLockObjective"]
        )
        self.assertEqual(3, entry["clearanceChunks"])
        self.assertEqual(
            list(range(4)) + list(range(4)),
            [variant["layoutSeed"] for variant in entry["variants"]],
        )
        self.assertEqual(
            8, len({variant["layoutSha256"] for variant in entry["variants"]})
        )
        self.assertEqual("procedural_component_port", entry["layoutStrategy"])

    def test_component_grammar_and_four_way_roots_match_upstream(self):
        expected_lower = {
            "small_hallway",
            "left_turn",
            "crossing",
            "right_turn",
            "dead_end",
            "balcony_room",
            "training_room",
            "small_stairs",
            "treasure_corridor",
            "atrium",
            "foundry",
            "treasure_room",
            "boss_room",
        }
        expected_upper = {
            "upper_ascender",
            "upper_corridor",
            "upper_left_turn",
            "upper_right_turn",
            "upper_t_intersection",
        }
        entry = stronghold_entry()
        self.assertEqual(expected_lower, set(entry["componentGrammar"]["lower"]))
        self.assertEqual(expected_upper, set(entry["componentGrammar"]["upper"]))
        for variant in entry["variants"]:
            port = variant["sourcePort"]
            self.assertEqual(4, port["lowerRootBranches"])
            self.assertEqual(4, port["upperRootBranches"])
            self.assertEqual(1, port["bossRoomCount"])
            self.assertGreaterEqual(port["componentCount"], 36)
            self.assertLessEqual(port["componentCount"], 55)
            self.assertGreaterEqual(port["bossRouteLength"], 5)
            self.assertLessEqual(port["bossRouteLength"], 9)
            self.assertEqual(30, port["lowerDepthLimit"])
            self.assertEqual(75, port["lowerRangeLimit"])
            self.assertEqual(
                "minecraft_structure_piece", port["coordinateTransform"]
            )

    def test_authentic_room_features_are_compiled_not_generic_shells(self):
        required = {
            "minecraft:lava",
            "minecraft:anvil",
            "minecraft:carved_pumpkin",
            "minecraft:tnt",
            "minecraft:obsidian",
            "minecraft:iron_bars",
            "tf_slice:landmark_protected_grass",
            "minecraft:diamond_ore",
            "minecraft:gold_ore",
            "minecraft:iron_ore",
        }
        # The source weighted grammar does not force every optional room into
        # every stronghold.  Preserve that variation while requiring the bank
        # to materialize the complete authored feature set.
        authored_union = set()
        for variant in stronghold_entry()["variants"]:
            authored = set(variant["validation"]["authoredBlocks"])
            authored_union.update(authored)
            self.assertIn("tf_slice:underbrick", authored)
            self.assertIn("minecraft:obsidian", authored)
        self.assertTrue(required.issubset(authored_union))

    def test_pedestal_seal_is_a_horizontal_five_by_five_layer(self):
        for variant in stronghold_entry()["variants"]:
            shield = variant["markers"]["shieldWalls"]
            self.assertEqual(25, len(shield))
            self.assertEqual(1, len({offset[1] for offset in shield}))
            self.assertEqual(5, len({offset[0] for offset in shield}))
            self.assertEqual(5, len({offset[2] for offset in shield}))

    def test_all_templates_are_vertical_slices_and_have_recovery_order(self):
        entry = stronghold_entry()
        for variant in entry["variants"]:
            self.assertGreater(len(variant["pieces"]), 1)
            offsets = []
            for piece in variant["pieces"]:
                self.assertLessEqual(piece["size"][0], 16)
                self.assertLessEqual(piece["size"][1], 64)
                self.assertLessEqual(piece["size"][2], 16)
                self.assertEqual(
                    [piece["offset"][1], piece["offset"][0], piece["offset"][2]],
                    piece["recoveryOrder"],
                )
                offsets.append(tuple(piece["offset"]))
                path = BP / "structures" / (piece["structure"] + ".mcstructure")
                self.assertTrue(path.is_file(), path)
                self.assertGreater(path.stat().st_size, 64)
            self.assertEqual(offsets, sorted(offsets, key=lambda value: (value[1], value[0], value[2])))

    def test_compiled_markers_and_reachability_are_fail_closed(self):
        entry = stronghold_entry()
        required = {
            "surfaceEntrance",
            "trophyPedestal",
            "shieldWalls",
            "bossRoom",
            "bossGroupSpawner",
            "lootChests",
            "structureSpawners",
        }
        for variant in entry["variants"]:
            self.assertTrue(required.issubset(variant["markers"]))
            self.assertEqual(
                "minecraft:air",
                variant["markers"]["surfaceEntrance"]["block"],
            )
            validation = variant["validation"]
            self.assertTrue(validation["entranceReachable"])
            self.assertTrue(validation["bossRoomReachable"])
            self.assertTrue(validation["allLootReachable"])
            self.assertTrue(validation["allComponentsReachable"])
            self.assertTrue(validation["doorwaysConnected"])
            self.assertTrue(validation["finalDoorwaysConnected"])
            self.assertTrue(validation["renderBoundsValid"])
            self.assertTrue(validation["roofComplete"])
            self.assertTrue(validation["bossSpawnerPresent"])
            self.assertTrue(validation["surfaceToBossWalkable"])
            self.assertEqual(0, validation["clippedBlockCount"])
            self.assertEqual([], validation["forbiddenBlocks"])
            self.assertEqual(
                0,
                variant["surfaceNative"]["environmentIntegration"][
                    "protectedColumns"
                ],
            )

    def test_spawn_table_and_six_knight_group_match_upstream(self):
        entry = stronghold_entry()
        weights = {
            row["entity"]: (row["weight"], row["group"])
            for row in entry["controlledSpawns"]["tiers"]["stronghold"]
        }
        self.assertEqual(
            {
                "tf_slice:block_chain_goblin": (10, [1, 2]),
                "tf_slice:lower_goblin_knight": (5, [1, 2]),
                "tf_slice:helmet_crab": (10, [2, 4]),
                "tf_slice:slime_beetle": (10, [2, 3]),
                "tf_slice:redcap_sapper": (2, [1, 2]),
                "tf_slice:kobold": (10, [2, 4]),
                "minecraft:creeper": (5, [1, 2]),
                "minecraft:slime": (5, [4, 4]),
            },
            weights,
        )
        group = entry["bossGroupSpawner"]
        self.assertEqual("tf_slice:knight_phantom", group["entity"])
        self.assertEqual(6, group["count"])
        self.assertEqual(4, group["ringRadius"])
        self.assertEqual(30, group["homeRadius"])
        self.assertEqual(list(range(6)), group["memberNumbers"])

    def test_structure_budget_caps_are_encoded_from_the_release_baseline(self):
        budget = catalog()["budget"]
        self.assertEqual(
            release_metadata.STRUCTURE_BASELINE_FILE_COUNT,
            budget["baselineFileCount"],
        )
        self.assertEqual(
            release_metadata.STRUCTURE_BASELINE_UNCOMPRESSED_BYTES,
            budget["baselineUncompressedBytes"],
        )
        self.assertEqual(
            release_metadata.STRUCTURE_FILE_COUNT_LIMIT,
            budget["maxFileCount"],
        )
        self.assertEqual(
            release_metadata.STRUCTURE_UNCOMPRESSED_BYTES_LIMIT,
            budget["maxUncompressedBytes"],
        )


class KnightStrongholdServiceContractTests(unittest.TestCase):
    def test_worldgen_service_supports_buried_stronghold_and_persisted_cursor(self):
        source = (PACKAGE / "structureWorldgenService.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"knight_stronghold"', source)
        self.assertIn('"buried_entry"', source)
        self.assertIn('job["templateCursor"]', source)
        self.assertIn('job["markersVerified"]', source)
        self.assertIn('job["finalCommit"]', source)


if __name__ == "__main__":
    unittest.main()
