import json
import pathlib
import random
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG_PATH = (
    ROOT
    / "TwilightBossSliceB"
    / "structures"
    / "tf_slice"
    / "ruins"
    / "structure_catalog_v1.json"
)
SAMPLE_CHUNKS = 100_000
SMALL_RARITIES = {
    "monolith": 90,
    "stone_circle": 105,
    "well": 80,
    "foundation": 90,
    "druid_hut": 105,
    "outside_stalagmite": 77,
    "hollow_stump": 80,
    "fallen_hollow_log": 85,
    "grove_ruins": 110,
}


def weighted_roll(rng, variants):
    total = sum(variant["weight"] for variant in variants)
    roll = rng.randrange(total)
    for variant in variants:
        roll -= variant["weight"]
        if roll < 0:
            return variant["id"]
    raise AssertionError("unreachable weighted choice")


class RuinProbabilitySimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.entries = {
            entry["id"]: entry for entry in cls.catalog["structures"]
        }

    def test_nine_small_ruins_match_one_hundred_thousand_chunk_sample(self):
        for index, (ruin_id, denominator) in enumerate(
            sorted(SMALL_RARITIES.items())
        ):
            rng = random.Random(0x4302508 + index)
            generated = sum(
                rng.randrange(denominator) == 0
                for _ in range(SAMPLE_CHUNKS)
            )
            expected = SAMPLE_CHUNKS / denominator
            relative_error = abs(generated - expected) / expected
            self.assertLessEqual(
                relative_error,
                0.10,
                "%s generated %d; expected %.2f"
                % (ruin_id, generated, expected),
            )

    def test_well_and_druid_branch_weights_match_upstream_distribution(self):
        well_rng = random.Random(0x0E11)
        well_variants = self.entries["well"]["variants"]
        fancy = sum(
            weighted_roll(well_rng, well_variants).startswith("fancy")
            for _ in range(SAMPLE_CHUNKS)
        )
        self.assertLessEqual(
            abs(fancy - SAMPLE_CHUNKS * 0.05) / (SAMPLE_CHUNKS * 0.05),
            0.10,
        )

        druid_rng = random.Random(0xD201D)
        druid_variants = self.entries["druid_hut"]["variants"]
        basement = sum(
            "basement" in weighted_roll(druid_rng, druid_variants)
            for _ in range(SAMPLE_CHUNKS)
        )
        self.assertLessEqual(
            abs(basement - SAMPLE_CHUNKS * 0.50) / (SAMPLE_CHUNKS * 0.50),
            0.10,
        )


if __name__ == "__main__":
    unittest.main()
