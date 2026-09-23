# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import biome_catalog


class BiomeStructureMatrixContractTests(unittest.TestCase):
    def test_every_structure_biome_has_a_macro_land_region(self):
        active_land_biomes = {
            entry["identifier"]
            for entry in biome_catalog.ACTIVE_LAND_BIOMES
        }
        structure_biomes = (
            biome_catalog.SMALL_RUIN_BIOMES
            | biome_catalog.LARGE_LANDMARK_BIOMES
            | frozenset(biome_catalog.SPECIAL_LANDMARK_BY_BIOME)
        )
        self.assertTrue(structure_biomes.issubset(active_land_biomes))
        self.assertTrue(
            biome_catalog.AQUATIC_BIOMES.isdisjoint(active_land_biomes)
        )

    def test_small_ruin_matrix_matches_upstream_ordinary_biomes(self):
        expected = {
            "forest",
            "dense_forest",
            "oak_savannah",
            "mushroom_forest",
            "firefly_forest",
            "dense_mushroom_forest",
            "enchanted_forest",
            "clearing",
            "swamp",
        }
        actual = {
            biome_catalog.BIOMES_BY_IDENTIFIER[identifier]["key"]
            for identifier in biome_catalog.SMALL_RUIN_BIOMES
        }
        self.assertEqual(expected, actual)

    def test_large_landmark_matrix_excludes_water_and_quest_grove_biome(self):
        expected = {
            "forest",
            "dense_forest",
            "oak_savannah",
            "mushroom_forest",
            "firefly_forest",
            "dense_mushroom_forest",
            "clearing",
            "spooky_forest",
        }
        actual = {
            biome_catalog.BIOMES_BY_IDENTIFIER[identifier]["key"]
            for identifier in biome_catalog.LARGE_LANDMARK_BIOMES
        }
        self.assertEqual(expected, actual)
        self.assertTrue(
            biome_catalog.AQUATIC_BIOMES.isdisjoint(
                biome_catalog.LARGE_LANDMARK_BIOMES
            )
        )

    def test_special_landmarks_and_unported_fallbacks_are_biome_scoped(self):
        self.assertEqual(
            {
                "dm33027004_birch_forest_mutated": "quest_grove",
                "dm33027004_swampland": "labyrinth",
                "dm33027004_swampland_mutated": "hydra_lair",
                "dm33027004_roofed_forest_mutated": "knight_stronghold",
                "dm33027004_redwood_taiga_mutated": "dark_tower",
            },
            biome_catalog.SPECIAL_LANDMARK_BY_BIOME,
        )
        self.assertEqual(
            {
                "dm33027004_mushroom_island": "mushroom_tower",
            },
            biome_catalog.UNPORTED_LANDMARK_FALLBACK_BY_BIOME,
        )

    def test_service_consumes_catalog_matrices_instead_of_local_lists(self):
        source = (
            BP / "TwilightBossSlice" / "structureWorldgenService.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "biome_catalog.SMALL_RUIN_BIOMES",
            source,
        )
        self.assertIn(
            "biome_catalog.LARGE_LANDMARK_BIOMES",
            source,
        )
        self.assertIn(
            "biome_catalog.SPECIAL_LANDMARK_BY_BIOME",
            source,
        )
        self.assertIn(
            "biome_catalog.UNPORTED_LANDMARK_FALLBACK_BY_BIOME",
            source,
        )


if __name__ == "__main__":
    unittest.main()
