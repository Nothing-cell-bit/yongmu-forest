import unittest

from TwilightBossSliceB.TwilightBossSlice import entity_registry_logic


class EntityRegistryLogicTests(unittest.TestCase):
    def test_matching_key_treats_numeric_and_text_entity_ids_as_the_same_actor(self):
        registry = {-8589934527: {"home": (0.0, 64.0, 0.0)}}

        self.assertEqual(
            -8589934527,
            entity_registry_logic.matching_entity_key(
                registry,
                "-8589934527",
            ),
        )

    def test_matching_key_prefers_the_exact_engine_id(self):
        registry = {
            "actor": {"value": "text"},
            42: {"value": "number"},
        }

        self.assertEqual(
            42,
            entity_registry_logic.matching_entity_key(registry, 42),
        )

    def test_matching_key_returns_none_for_an_unknown_actor(self):
        self.assertIsNone(
            entity_registry_logic.matching_entity_key({1: {}}, 2)
        )


if __name__ == "__main__":
    unittest.main()
