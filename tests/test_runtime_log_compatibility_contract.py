import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class RuntimeLogCompatibilityContractTests(unittest.TestCase):
    def test_engine_compatibility_does_not_pad_the_canonical_biome_registry(self):
        identifier = "dm33027004_cherry_grove"
        server_path = (
            BP
            / "netease_biomes"
            / "dm33027004"
            / (identifier + ".json")
        )
        client_path = RP / "biomes" / (identifier + ".client_biome.json")
        dimension = load_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]

        self.assertFalse(server_path.exists())
        self.assertFalse(client_path.exists())
        self.assertNotIn(identifier, dimension["netease:spawn_biomes"])

    def test_single_block_features_only_reference_registered_netease_air(self):
        affected = (
            "cave_hanging_roots_single_feature.json",
            "cave_torchberry_plant_single_feature.json",
            "cave_root_strand_single_feature.json",
        )
        for file_name in affected:
            feature = load_json(BP / "netease_features" / file_name)
            may_replace = feature["minecraft:single_block_feature"][
                "may_replace"
            ]
            self.assertEqual(["minecraft:air"], may_replace, file_name)

    def test_every_declared_twilight_biome_is_referenced_by_dimension(self):
        dimension_path = BP / "netease_dimension" / "dm33027004.json"
        dimension_text = dimension_path.read_text(encoding="utf-8")
        declared = set()
        biome_root = BP / "netease_biomes" / "dm33027004"
        for path in biome_root.glob("*.json"):
            declared.add(
                load_json(path)["minecraft:biome"]["description"][
                    "identifier"
                ]
            )
        unreferenced = sorted(
            biome for biome in declared if '"%s"' % biome not in dimension_text
        )
        self.assertEqual([], unreferenced)

    def test_lich_entity_sound_table_uses_only_level_sound_events(self):
        sounds = load_json(RP / "sounds.json")
        events = sounds["entity_sounds"]["entities"]["tf_slice:lich"][
            "events"
        ]
        self.assertNotIn("pop_mob", events)
        server_source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"mob.chicken.plop"', server_source)


if __name__ == "__main__":
    unittest.main()
