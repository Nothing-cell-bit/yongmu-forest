# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import mushroom_worldgen_logic as logic
from TwilightBossSlice.mushroomWorldgenService import MushroomWorldgenService


class FakeExtra(object):
    def __init__(self):
        self.values = {"tf_slice:ruin_world_seed_v1": 12345}

    def GetExtraData(self, key):
        return self.values.get(key)

    def SetExtraData(self, key, value, _sync):
        self.values[key] = value
        return True

    def SaveExtraData(self):
        return True


class FakeChunk(object):
    def __init__(self):
        self.ready = True
        self.checks = []

    def CheckChunkState(self, dimension_id, position):
        self.checks.append((dimension_id, position))
        return self.ready


class FakeGame(object):
    def __init__(self):
        self.placements = []

    def PlaceStructure(self, *args):
        self.placements.append(args)
        return True


class FakeBiome(object):
    def __init__(self):
        self.name = "dm33027004_mushroom_island"

    def GetBiomeName(self, _position, _dimension_id):
        return self.name


class FakeBlock(object):
    def __init__(self):
        self.top_y = 90
        self.blocks = {}
        self.readable = True
        self.height_queries = []

    def GetTopBlockHeight(self, _position, _dimension_id):
        self.height_queries.append((tuple(_position), int(_dimension_id)))
        return self.top_y

    def GetBlockNew(self, position, _dimension_id):
        if not self.readable:
            return None
        return self.blocks.get(tuple(position), {"name": "minecraft:air", "aux": 0})


class FakeFeature(object):
    def __init__(self):
        self.added = []
        self.removed = []

    def AddNeteaseFeatureWhiteList(self, structure_name):
        self.added.append(structure_name)
        return True

    def RemoveNeteaseFeatureWhiteList(self, structure_name):
        self.removed.append(structure_name)
        return True


class FakeFactory(object):
    def __init__(self):
        self.extra = FakeExtra()
        self.chunk = FakeChunk()
        self.game = FakeGame()
        self.biome = FakeBiome()
        self.block = FakeBlock()
        self.feature = FakeFeature()

    def CreateExtraData(self, _level_id):
        return self.extra

    def CreateChunkSource(self, _level_id):
        return self.chunk

    def CreateGame(self, _level_id):
        return self.game

    def CreateBiome(self, _level_id):
        return self.biome

    def CreateBlockInfo(self, _level_id):
        return self.block

    def CreateFeature(self, _level_id):
        return self.feature


class MushroomWorldgenServiceTests(unittest.TestCase):
    def setUp(self):
        self.factory = FakeFactory()
        self.service = MushroomWorldgenService(self.factory, "level", 7)
        self.player = {
            "dimensionId": 7,
            "position": (100.5, 70.0, 200.5),
        }
        self.factory.block.blocks[(100, 90, 200)] = {
            "name": "tf_slice:twilight_oak_leaves",
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

    def _event(self, kind="brown"):
        event = {
            "structureName": logic.TRIGGER_STRUCTURES[kind],
            "dimensionId": 7,
            "x": 100,
            "y": 91,
            "z": 200,
            "biomeName": "dm33027004_mushroom_island",
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

    def test_tree_top_trigger_reanchors_stem_to_ground_and_places_pieces(self):
        self._event()
        self.service.tick(1, [self.player])

        job = list(self.service._ledger.values())[0]
        self.assertEqual([100, 65, 200], job["root"])
        self.assertEqual([80, 60, 180], job["origin"])
        self.assertEqual("placing", job["state"])
        self.assertEqual(1, len(self.factory.game.placements))
        first = self.factory.game.placements[0]
        first_piece = self.service._catalog["brown"][job["variant"]][
            "pieces"
        ][0]
        self.assertEqual(
            (
                80 + first_piece["offset"][0],
                60 + first_piece["offset"][1],
                180 + first_piece["offset"][2],
            ),
            first[1],
        )
        self.assertIn("tf_slice:mushroom/runtime/brown/", first[2])

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

    def test_no_piece_is_placed_until_every_intersecting_chunk_is_ready(self):
        self.factory.chunk.ready = False
        self._event()
        self.service.tick(1, [self.player])

        job = list(self.service._ledger.values())[0]
        self.assertEqual("planned", job["state"])
        self.assertEqual([], self.factory.game.placements)
        self.assertEqual([], self.factory.block.height_queries)
        self.assertGreater(len(self.factory.chunk.checks), 0)

    def test_unreadable_root_chunk_never_reaches_native_height_query(self):
        self.factory.block.readable = False
        self._event()

        self.service.tick(1, [self.player])

        job = list(self.service._ledger.values())[0]
        self.assertEqual("planned", job["state"])
        self.assertEqual([], self.factory.block.height_queries)
        self.assertEqual([], self.factory.game.placements)

    def test_water_surface_and_solid_clearance_are_rejected(self):
        self.factory.block.blocks[(100, 64, 200)] = {
            "name": "minecraft:water",
            "aux": 0,
        }
        self._event()
        self.service.tick(1, [self.player])
        job = list(self.service._ledger.values())[0]
        self.assertEqual("skipped", job["state"])
        self.assertEqual("unsupported_ground", job["reason"])
        self.assertEqual([], self.factory.game.placements)

        factory = FakeFactory()
        service = MushroomWorldgenService(factory, "level-2", 7)
        factory.block.top_y = 64
        factory.block.blocks[(100, 64, 200)] = {
            "name": "minecraft:grass_block",
            "aux": 0,
        }
        factory.block.blocks[(100, 65, 200)] = {
            "name": "tf_slice:twilight_oak_log",
            "aux": 0,
        }
        event = {
            "structureName": logic.TRIGGER_STRUCTURES["brown"],
            "dimensionId": 7,
            "x": 100,
            "y": 65,
            "z": 200,
            "biomeName": "dm33027004_mushroom_island",
        }
        service.on_structure_feature_event(event)
        service.tick(1, [self.player])
        blocked = list(service._ledger.values())[0]
        self.assertEqual("skipped", blocked["state"])
        self.assertEqual("blocked_clearance", blocked["reason"])
        self.assertEqual([], factory.game.placements)


if __name__ == "__main__":
    unittest.main()
