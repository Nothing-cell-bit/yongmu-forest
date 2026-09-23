# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import enchanted_tree_worldgen_logic as logic
from TwilightBossSlice.enchantedTreeWorldgenService import (
    EnchantedTreeWorldgenService,
)
from tests.test_mushroom_worldgen_service import FakeFactory


class EnchantedTreeWorldgenServiceTests(unittest.TestCase):
    def setUp(self):
        self.factory = FakeFactory()
        self.factory.biome.name = logic.ENCHANTED_BIOME
        self.service = EnchantedTreeWorldgenService(
            self.factory, "level", 7
        )
        self.player = {
            "dimensionId": 7,
            "position": (100.5, 70.0, 200.5),
        }
        self.factory.block.blocks[(100, 90, 200)] = {
            "name": "tf_slice:enchanted_canopy_leaves",
            "aux": 0,
        }
        self.factory.block.blocks[(100, 89, 200)] = {
            "name": "tf_slice:twilight_oak_log",
            "aux": 0,
        }
        self.factory.block.blocks[(100, 64, 200)] = {
            "name": "minecraft:grass_block",
            "aux": 0,
        }

    def _event(self, kind="regular_rainbow"):
        event = {
            "structureName": logic.TRIGGER_STRUCTURES[kind],
            "dimensionId": 7,
            "x": 100,
            "y": 91,
            "z": 200,
            "biomeName": logic.ENCHANTED_BIOME,
        }
        self.service.on_structure_feature_event(event)
        return event

    def test_worker_event_uses_noop_and_only_queues_data(self):
        before = dict(self.factory.extra.values)
        event = self._event()

        self.assertFalse(event.get("cancel", False))
        self.assertEqual("tf_slice:ruin_landmark_noop", event["structureName"])
        self.assertEqual(before, self.factory.extra.values)
        self.assertEqual(1, len(self.service._handoffs))
        self.assertEqual(
            set(logic.TRIGGER_STRUCTURES.values())
            | {"tf_slice:ruin_landmark_noop"},
            set(self.factory.feature.added),
        )

    def test_canopy_top_is_ignored_and_regular_tree_reanchors_to_ground(self):
        self._event()
        self.service.tick(1, [self.player])

        job = list(self.service._ledger.values())[0]
        self.assertEqual([100, 65, 200], job["root"])
        self.assertEqual([93, 60, 193], job["origin"])
        self.assertEqual(1, len(self.factory.game.placements))

    def test_landmark_radius_does_not_blank_ordinary_grass_surface(self):
        self.service._inside_landmark_clearance = (
            lambda _x, _z, _biome: True
        )
        self._event()
        self.service.tick(1, [self.player])

        job = list(self.service._ledger.values())[0]
        self.assertIn(job["state"], ("placing", "complete"))
        self.assertEqual([100, 65, 200], job["root"])
        self.assertGreater(len(self.factory.game.placements), 0)

    def test_protected_landmark_grass_still_rejects_deferred_tree(self):
        self.factory.block.blocks[(100, 64, 200)] = {
            "name": "tf_slice:landmark_protected_grass",
            "aux": 0,
        }
        self._event()
        self.service.tick(1, [self.player])

        job = list(self.service._ledger.values())[0]
        self.assertEqual("skipped", job["state"])
        self.assertEqual("unsupported_ground", job["reason"])
        self.assertEqual([], self.factory.game.placements)

    def test_large_tree_uses_its_own_center_and_waits_for_all_chunks(self):
        self.factory.chunk.ready = False
        self._event("large_rainbow")
        self.service.tick(1, [self.player])

        job = list(self.service._ledger.values())[0]
        self.assertEqual("planned", job["state"])
        self.assertEqual([], self.factory.game.placements)
        self.assertEqual([], self.factory.block.height_queries)
        self.assertGreater(len(self.factory.chunk.checks), 0)

        self.factory.chunk.ready = True
        self.service.tick(2, [self.player])
        self.assertEqual([88, 60, 188], job["origin"])
        self.assertEqual(1, len(self.factory.game.placements))

    def test_unreadable_root_chunk_never_reaches_native_height_query(self):
        self.factory.block.readable = False
        self._event()

        self.service.tick(1, [self.player])

        job = list(self.service._ledger.values())[0]
        self.assertEqual("planned", job["state"])
        self.assertEqual([], self.factory.block.height_queries)
        self.assertEqual([], self.factory.game.placements)

    def test_water_and_solid_clearance_are_rejected(self):
        self.factory.block.blocks[(100, 64, 200)] = {
            "name": "minecraft:water",
            "aux": 0,
        }
        self._event()
        self.service.tick(1, [self.player])
        job = list(self.service._ledger.values())[0]
        self.assertEqual("unsupported_ground", job["reason"])

        factory = FakeFactory()
        factory.biome.name = logic.ENCHANTED_BIOME
        factory.block.top_y = 64
        factory.block.blocks[(100, 64, 200)] = {
            "name": "minecraft:grass_block",
            "aux": 0,
        }
        factory.block.blocks[(100, 65, 200)] = {
            "name": "minecraft:stone",
            "aux": 0,
        }
        service = EnchantedTreeWorldgenService(factory, "level-2", 7)
        event = {
            "structureName": logic.TRIGGER_STRUCTURES["regular_rainbow"],
            "dimensionId": 7,
            "x": 100,
            "y": 65,
            "z": 200,
            "biomeName": logic.ENCHANTED_BIOME,
        }
        service.on_structure_feature_event(event)
        service.tick(1, [self.player])
        blocked = list(service._ledger.values())[0]
        self.assertEqual("blocked_clearance", blocked["reason"])
        self.assertEqual([], factory.game.placements)


if __name__ == "__main__":
    unittest.main()
