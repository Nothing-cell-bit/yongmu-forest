import json
import pathlib
import random
import sys
import types
import unittest
import warnings

from lib2to3.refactor import RefactoringTool


ROOT = pathlib.Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
SERVICE_PATH = BP / "TwilightBossSlice" / "structureWorldgenService.py"
sys.path.insert(0, str(BP))
sys.path.insert(0, str(ROOT / "tools"))


def load_service_module():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    if not source.endswith("\n"):
        source += "\n"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        converted = RefactoringTool(
            ["lib2to3.fixes.fix_print"]
        ).refactor_string(source, str(SERVICE_PATH))
    module = types.ModuleType("structure_worldgen_service_under_test")
    module.__file__ = str(SERVICE_PATH)
    exec(compile(str(converted), str(SERVICE_PATH), "exec"), module.__dict__)
    return module


SERVICE = load_service_module()


class FakeExtraData(object):
    def __init__(self):
        self.data = {
            SERVICE.WORLD_SEED_KEY: 123456789,
            SERVICE.LEDGER_KEY: {},
        }
        self.save_count = 0
        self.set_result = True
        self.save_result = True
        self.reject_structured_values = False

    def GetExtraData(self, key):
        return self.data.get(key)

    def SetExtraData(self, key, value, _sync):
        if self.reject_structured_values and isinstance(
            value,
            (dict, list, tuple),
        ):
            return False
        self.data[key] = value
        return self.set_result

    def SaveExtraData(self):
        self.save_count += 1
        return self.save_result


class FakeChunkSource(object):
    def __init__(self):
        self.added = []
        self.deleted = []
        self.ready = True
        self.ready_chunks = None
        self.checked = []

    def SetAddArea(self, key, dimension_id, minimum, maximum):
        self.added.append((key, dimension_id, minimum, maximum))
        return True

    def DeleteArea(self, key):
        self.deleted.append(key)
        return True

    def CheckChunkState(self, dimension_id, position):
        self.checked.append((dimension_id, position))
        if self.ready_chunks is not None:
            return (
                int(position[0]) >> 4,
                int(position[2]) >> 4,
            ) in self.ready_chunks
        return self.ready


class FakeGame(object):
    def __init__(self):
        self.placements = []
        self.entities = []
        self.seed = 987654321

    def PlaceStructure(self, *args):
        self.placements.append(args)
        return True

    def GetSeed(self):
        return self.seed

    def GetEntitiesInSquareArea(
        self,
        _unused_entity_id,
        _minimum,
        _maximum,
        _dimension_id,
    ):
        return list(self.entities)


class FakeEngineType(object):
    def __init__(self, identifier):
        self.identifier = identifier

    def GetEngineTypeStr(self):
        return self.identifier


class FakeBiome(object):
    def __init__(self):
        self.name = "dm33027004_plains"

    def GetBiomeName(self, _position, _dimension_id):
        return self.name


class FakeBlockInfo(object):
    def __init__(self):
        self.blocks = {}
        self.set_blocks = []

    def GetTopBlockHeight(self, _position, _dimension_id):
        return 64

    def GetBlockNew(self, position, _dimension_id):
        return self.blocks.get(
            tuple(position),
            {"name": "minecraft:air", "aux": 0},
        )

    def SetBlockNew(
        self,
        position,
        block,
        old_block_handling=0,
        dimension_id=-1,
        is_legacy=False,
        update_neighbors=True,
    ):
        args = (
            position,
            block,
            old_block_handling,
            dimension_id,
            is_legacy,
            update_neighbors,
        )
        self.set_blocks.append(args)
        position = tuple(position)
        current = self.GetBlockNew(position, dimension_id)
        if (
            current.get("name") == block.get("name")
            and int(current.get("aux", 0)) == int(block.get("aux", 0))
        ):
            return False
        self.blocks[position] = dict(block)
        return True


class FakeBlockState(object):
    def __init__(self):
        self.states = {}

    def GetBlockStates(self, position, _dimension_id):
        return dict(self.states.get(tuple(position), {}))

    def SetBlockStates(self, position, states, _dimension_id):
        self.states[tuple(position)] = dict(states)
        return True


class FakeFeature(object):
    def __init__(self):
        self.whitelist = []

    def AddNeteaseFeatureWhiteList(self, structure_name):
        self.whitelist.append(structure_name)
        return True

    def RemoveNeteaseFeatureWhiteList(self, structure_name):
        self.whitelist.remove(structure_name)
        return True


class FakeFactory(object):
    def __init__(self):
        self.extra = FakeExtraData()
        self.chunk = FakeChunkSource()
        self.game = FakeGame()
        self.biome = FakeBiome()
        self.block = FakeBlockInfo()
        self.block_state = FakeBlockState()
        self.feature = FakeFeature()
        self.entity_types = {}

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

    def CreateBlockState(self, _level_id):
        return self.block_state

    def CreateFeature(self, _level_id):
        return self.feature

    def CreateEngineType(self, entity_id):
        return FakeEngineType(self.entity_types.get(entity_id, ""))


class NativeStructureThreadHandoffTests(unittest.TestCase):
    def setUp(self):
        self.factory = FakeFactory()
        self.service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )

    def _jittered_route_region(self):
        for chunk_x in range(-64, 65, 16):
            for chunk_z in range(-64, 65, 16):
                legacy = SERVICE.ruin_logic.nearest_landmark_center(
                    chunk_x,
                    chunk_z,
                )
                nominal = SERVICE.ruin_logic.nearest_route_landmark_center(
                    chunk_x,
                    chunk_z,
                )
                if legacy != nominal:
                    return legacy, nominal
        self.fail("expected at least one jittered legacy landmark region")

    def test_route_surface_uses_nominal_center_but_ordinary_keeps_jitter(self):
        legacy, nominal = self._jittered_route_region()

        route = self.service._surface_native_tile(
            "fire_swamp",
            nominal[0] >> 4,
            nominal[1] >> 4,
            32,
        )
        ordinary = self.service._surface_native_tile(
            "ordinary",
            legacy[0] >> 4,
            legacy[1] >> 4,
            32,
        )

        self.assertIsNotNone(route)
        self.assertIsNotNone(ordinary)
        self.assertEqual(list(nominal), route[1]["center"])
        self.assertEqual(list(legacy), ordinary[1]["center"])

    def test_dark_tower_runtime_cleanup_only_removes_masked_hardened_leaves(self):
        job = {
            "kind": "dark_tower",
            "state": "complete",
            "anchor": [100, 40, 200],
            "center": [156, 256],
            "bounds": [100, 40, 200, 211, 263, 311],
            "surfaceLastSeenTick": 10,
            "canopyCleanup": {
                "schemaVersion": 1,
                "runs": [
                    [1, 2, 3, 6],
                    [2, 2, 3, 4],
                ],
            },
        }
        self.service._ledger["156,256"] = job
        masked_center_leaf = (101, 43, 202)
        masked_outer_leaf = (101, 44, 202)
        masked_planter_leaf = (101, 45, 202)
        masked_solid = (101, 46, 202)
        second_center_leaf = (102, 43, 202)
        outside_center_leaf = (103, 43, 202)
        self.factory.block.blocks.update(
            {
                masked_center_leaf: {
                    "name": "tf_slice:hardened_dark_leaves_center",
                    "aux": 0,
                },
                masked_outer_leaf: {
                    "name": "tf_slice:hardened_dark_leaves",
                    "aux": 0,
                },
                masked_planter_leaf: {
                    "name": "tf_slice:twilight_oak_leaves",
                    "aux": 0,
                },
                masked_solid: {"name": "tf_slice:towerwood", "aux": 0},
                second_center_leaf: {
                    "name": "tf_slice:hardened_dark_leaves_center",
                    "aux": 0,
                },
                outside_center_leaf: {
                    "name": "tf_slice:hardened_dark_leaves_center",
                    "aux": 0,
                },
            }
        )
        players = [
            {
                "dimensionId": 33027004,
                "position": [156.5, 64.0, 256.5],
            }
        ]

        self.assertFalse(
            self.service._advance_dark_tower_canopy_cleanup(
                20, players
            )
        )
        self.factory.chunk.ready = False
        self.assertFalse(
            self.service._advance_dark_tower_canopy_cleanup(
                200, players
            )
        )
        self.assertEqual([], self.factory.block.set_blocks)
        self.factory.chunk.ready = True
        self.assertTrue(
            self.service._advance_dark_tower_canopy_cleanup(
                220, players
            )
        )

        for position in (
            masked_center_leaf,
            masked_outer_leaf,
            second_center_leaf,
        ):
            self.assertEqual(
                "minecraft:air",
                self.factory.block.blocks[position]["name"],
            )
        self.assertEqual(
            "tf_slice:twilight_oak_leaves",
            self.factory.block.blocks[masked_planter_leaf]["name"],
        )
        self.assertEqual(
            "tf_slice:towerwood",
            self.factory.block.blocks[masked_solid]["name"],
        )
        self.assertEqual(
            "tf_slice:hardened_dark_leaves_center",
            self.factory.block.blocks[outside_center_leaf]["name"],
        )
        state = job["canopyCleanupState"]
        self.assertTrue(state["complete"])
        self.assertEqual(3, state["removed"])
        writes = len(self.factory.block.set_blocks)
        self.assertFalse(
            self.service._advance_dark_tower_canopy_cleanup(
                240, players
            )
        )
        self.assertEqual(writes, len(self.factory.block.set_blocks))

    def test_legacy_route_ledger_blocks_duplicate_nominal_handoff(self):
        legacy, nominal = self._jittered_route_region()
        factory = FakeFactory()
        factory.extra.data[SERVICE.LEDGER_KEY] = {
            "%d,%d" % legacy: {
                "state": "complete",
                "kind": "hydra_lair",
                "surfaceGenerated": True,
                "generationSource": "surface_feature",
                "variant": 0,
                "center": list(legacy),
                "anchor": [legacy[0], 64, legacy[1]],
                "bounds": [legacy[0] - 8, 32, legacy[1] - 8, legacy[0] + 8, 96, legacy[1] + 8],
                "surfaceTiles": ["0,0"],
                "surfaceExpectedTiles": ["0,0"],
            }
        }
        service = SERVICE.StructureWorldgenService(
            factory,
            "level",
            33027004,
        )
        record = {
            "kind": "hydra_lair",
            "center": list(nominal),
            "variant": 0,
            "surfaceTile": [0, 0],
            "surfaceTiles": ["0,0"],
            "surfaceExpectedTiles": ["0,0"],
            "surfaceGenerated": True,
            "generationSource": "surface_feature",
        }

        self.assertFalse(service._enqueue_surface_landmark_handoff(record))

    def test_magic_map_and_route_locate_use_nominal_center_for_legacy_record(self):
        legacy, nominal = self._jittered_route_region()
        factory = FakeFactory()
        factory.extra.data[SERVICE.LEDGER_KEY] = {
            "%d,%d" % legacy: {
                "state": "complete",
                "kind": "hydra_lair",
                "center": list(legacy),
                "anchor": [legacy[0], 64, legacy[1]],
                "bounds": [legacy[0] - 8, 32, legacy[1] - 8, legacy[0] + 8, 96, legacy[1] + 8],
                "bossDefeated": True,
            }
        }
        factory.biome.GetBiomeName = (
            lambda _position, _dimension_id:
            "dm33027004_swampland_mutated"
        )
        service = SERVICE.StructureWorldgenService(
            factory,
            "level",
            33027004,
        )
        landmarks = service.magic_map_landmarks_near(
            [nominal[0], 64, nominal[1]],
            nominal[0],
            nominal[1],
            128,
        )
        hydra = [entry for entry in landmarks if entry["kind"] == "hydra_lair"]

        self.assertEqual(1, len(hydra))
        self.assertEqual(list(nominal), hydra[0]["position"])
        self.assertTrue(hydra[0]["conquered"])

        service._ledger = {}
        service._surface_is_acceptable = (
            lambda _entry, _variant, _x, _z: 64
        )
        located = service._predicted_landmark_location(
            "hydra_lair",
            [nominal[0], 64, nominal[1]],
            128,
        )
        self.assertEqual([nominal[0], 64, nominal[1]], located["position"])

    def test_chunk_state_true_without_block_view_is_not_readable(self):
        self.factory.chunk.ready = True
        self.factory.block.GetBlockNew = lambda _position, _dimension: None

        self.assertFalse(self.service._chunk_position_ready(8, 64, 8))

    def test_lich_tower_group_uses_compiled_interior_spawn_offsets(self):
        spawned = []

        def spawn_entity(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            return "spawned:%d" % len(spawned)

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
            entity_spawner=spawn_entity,
        )
        job = {
            "kind": "lich_tower",
            "anchor": [100, 64, 200],
            "bounds": [100, 64, 200, 150, 150, 250],
            "center": [125, 225],
            "controlledSpawns": {
                "interiorOffsets": [[2, 3, 4]],
            },
        }
        self.factory.block.blocks[(102, 66, 204)] = {
            "name": "minecraft:stone_bricks",
            "aux": 0,
        }

        self.assertEqual(1, service._spawn_lich_tower_group(job, 100))
        self.assertEqual((102.5, 67.0, 204.5), spawned[0][1])

    def test_load_retires_legacy_surface_edge_writer(self):
        factory = FakeFactory()
        factory.extra.data[SERVICE.LEDGER_KEY] = {
            "8,8": {
                "state": "surface_blending",
                "kind": "hedge_maze",
                "surfaceGenerated": True,
                "surfaceTiles": ["0,0"],
                "surfaceExpectedTiles": ["0,0"],
                "edgeBlend": {
                    "width": 16,
                    "nextColumn": 12,
                    "complete": False,
                },
            }
        }

        service = SERVICE.StructureWorldgenService(
            factory,
            "level",
            33027004,
        )

        loaded = service._ledger["8,8"]
        self.assertEqual("complete", loaded["state"])
        self.assertNotIn("edgeBlend", loaded)
        self.assertEqual("surface_pass", loaded["terrainAdaptationStage"])

    def test_route_encounter_is_ready_when_its_boss_tile_is_present(self):
        record = {
            "kind": "labyrinth",
            "state": "surface_pending",
            "surfaceExpectedTiles": ["0,0", "1,0"],
            "surfaceTiles": ["0,0"],
            "surfaceBossTile": "0,0",
            "bossSpawner": {"kind": "minoshroom"},
        }

        self.assertFalse(self.service._refresh_surface_landmark_state(record))
        self.assertEqual("surface_pending", record["state"])
        self.assertTrue(record["bossSpawnerReady"])
        self.assertTrue(record["encounterReady"])

    def test_knight_surface_record_tracks_its_local_boss_tile(self):
        center_x, center_z = (-4103, -4103)
        selected = self.service._surface_native_tile(
            "dark_forest",
            center_x >> 4,
            center_z >> 4,
            32,
        )

        self.assertIsNotNone(selected)
        _reference, record = selected
        self.assertEqual("knight_stronghold", record["kind"])
        nominal_center = SERVICE.ruin_logic.landmark_region_sample(
            center_x,
            center_z,
        )
        self.assertEqual(list(nominal_center), record["center"])
        self.assertIn("bossGroupSpawner", record)
        marker = record["markers"]["bossGroupSpawner"]["offset"]
        marker_x = int(record["anchor"][0]) + int(marker[0])
        marker_z = int(record["anchor"][2]) + int(marker[2])
        expected_tile = self.service._surface_tile_key(
            (marker_x >> 4) - (nominal_center[0] >> 4),
            (marker_z >> 4) - (nominal_center[1] >> 4),
        )
        self.assertEqual(expected_tile, record["surfaceBossTile"])

    def test_knight_encounter_commits_when_its_boss_tile_is_present(self):
        record = {
            "kind": "knight_stronghold",
            "state": "surface_pending",
            "surfaceGenerated": True,
            "surfaceExpectedTiles": ["0,0", "1,0", "2,0"],
            "surfaceTiles": ["1,0"],
            "surfaceBossTile": "1,0",
            "bossGroupSpawner": {
                "kind": "knight_phantoms",
                "memberNumbers": list(range(6)),
            },
        }

        self.assertFalse(self.service._refresh_surface_landmark_state(record))
        self.assertEqual("surface_pending", record["state"])
        self.assertTrue(record["bossSpawnerReady"])
        self.assertTrue(record["encounterReady"])

    def test_surface_ready_knight_group_does_not_wait_for_far_edge_tiles(self):
        spawned = []

        def spawn_entity(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            return "knight-%d" % len(spawned)

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
            entity_spawner=spawn_entity,
        )
        ledger_key = "knight"
        job = {
            "kind": "knight_stronghold",
            "state": "surface_pending",
            "surfaceGenerated": True,
            "encounterReady": True,
            "anchor": [100, 40, 100],
            "markers": {
                "bossGroupSpawner": {"offset": [10, 0, 10]},
            },
            "bossGroupSpawner": {
                "memberNumbers": list(range(6)),
                "homeRadius": 30,
            },
            "bossGroupSpawned": False,
            "bossGroupDefeated": False,
        }
        service._ledger[ledger_key] = job
        service._knight_group_job_keys.add(ledger_key)
        self.factory.block.blocks[(110, 40, 110)] = {
            "name": "tf_slice:knight_phantom_boss_spawner",
            "aux": 0,
        }

        service._activate_knight_groups(
            [
                {
                    "playerId": "player",
                    "dimensionId": 33027004,
                    "position": [110.0, 40.0, 110.0],
                }
            ],
            20,
        )

        self.assertEqual(6, len(spawned))
        self.assertTrue(job["bossGroupSpawned"])

    def test_load_migrates_existing_knight_surface_record_to_local_commit(self):
        entry = self.service._catalog["knight_stronghold"]
        variant = entry["variants"][0]
        center = [-4103, -4103]
        anchor = [-4200, 64, -4200]
        markers = variant["markers"]
        marker = markers["bossGroupSpawner"]["offset"]
        marker_x = anchor[0] + int(marker[0])
        marker_z = anchor[2] + int(marker[2])
        boss_tile = self.service._surface_tile_key(
            (marker_x >> 4) - (center[0] >> 4),
            (marker_z >> 4) - (center[1] >> 4),
        )
        self.factory.extra.data[SERVICE.LEDGER_KEY] = {
            "legacy-knight": {
                "entryId": "knight_stronghold",
                "kind": "knight_stronghold",
                "state": "surface_pending",
                "surfaceGenerated": True,
                "generationSource": "surface_feature",
                "center": center,
                "anchor": anchor,
                "variant": 0,
                "surfaceExpectedTiles": [boss_tile, "99,99"],
                "surfaceTiles": [boss_tile],
                "markers": markers,
                "nextPiece": 0,
            }
        }

        restarted = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )
        restored = restarted._ledger["legacy-knight"]

        self.assertEqual(boss_tile, restored["surfaceBossTile"])
        self.assertIn("bossGroupSpawner", restored)
        self.assertTrue(restored["encounterReady"])
        self.assertIn("legacy-knight", restarted._knight_group_job_keys)

    def test_load_restores_template_controlled_spawn_tables_from_catalog(self):
        self.factory.extra.data[SERVICE.LEDGER_KEY] = {
            "legacy-knight": {
                "entryId": "knight_stronghold",
                "kind": "knight_stronghold",
                "state": "complete",
                "center": [0, 0],
                "anchor": [0, 0, 0],
                "bounds": [0, -52, 0, 127, 2, 165],
                "variant": 0,
                "surfaceGenerated": True,
            },
            "legacy-tower": {
                "entryId": "dark_tower",
                "kind": "dark_tower",
                "state": "complete",
                "center": [256, 256],
                "anchor": [200, 0, 208],
                "bounds": [200, 0, 208, 311, 223, 303],
                "variant": 0,
                "surfaceGenerated": True,
            },
        }

        restarted = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )

        stronghold = restarted._ledger["legacy-knight"]["controlledSpawns"]
        tower = restarted._ledger["legacy-tower"]["controlledSpawns"]
        self.assertIn("stronghold", stronghold["tiers"])
        self.assertIn("lower", tower["tiers"])
        self.assertIn("roof", tower["tiers"])
        self.assertIn("water", tower["tiers"])

    def test_labyrinth_controlled_spawns_do_not_wait_for_outer_empty_tiles(self):
        job = {
            "kind": "labyrinth",
            "state": "surface_pending",
            "encounterReady": True,
            "bounds": [0, 0, 0, 110, 38, 110],
        }
        players = [
            {
                "dimensionId": 33027004,
                "position": [55, 12, 55],
                "progress": {},
            }
        ]

        self.assertIs(players[0], self.service._labyrinth_player(job, players))

    def test_labyrinth_controlled_spawn_can_create_minotaurs_without_progress(self):
        spawned = []

        def spawn_entity(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            return "spawned-%d" % len(spawned)

        self.service._entity_spawner = spawn_entity
        self.factory.block.GetBlockNew = lambda position, _dimension: {
            "name": "tf_slice:mazestone_mosaic"
            if int(position[1]) == 11
            else "minecraft:air",
            "aux": 0,
        }
        job = {
            "kind": "labyrinth",
            "state": "complete",
            "center": [55, 55],
            "anchor": [0, 0, 0],
            "bounds": [0, 0, 0, 110, 53, 110],
            "controlledSpawns": {
                "cap": 18,
                "intervalTicks": 100,
                "weights": [
                    {
                        "entity": "tf_slice:minotaur",
                        "weight": 20,
                        "group": [2, 3],
                    }
                ],
            },
            "markers": {
                "spawnZones": [
                    {"level": 0, "center": [55, 12, 55], "radius": 7}
                ]
            },
        }
        self.service._ledger = {"55,55": job}
        self.service._rebuild_runtime_job_indexes()
        self.service._controlled_spawn_attempt_due = lambda *_args: True
        players = [
            {
                "dimensionId": 33027004,
                "position": [85.5, 12, 55.5],
                "progress": {},
            }
        ]

        self.service._spawn_labyrinth_monsters(100, players)

        self.assertGreaterEqual(len(spawned), 2)
        self.assertTrue(
            all(call[0] == "tf_slice:minotaur" for call in spawned)
        )

    def test_knight_stronghold_consumes_source_controlled_spawn_table(self):
        spawned = []

        def spawn_entity(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            return "spawned-%d" % len(spawned)

        self.service._entity_spawner = spawn_entity
        self.service._controlled_structure_spawn_candidates = (
            lambda _job, _player, _identifier, _seed, _attempts: [
                ((60.5, 31.0, 32.5), 90.0)
            ]
        )
        self.service._ledger = {
            "stronghold": {
                "kind": "knight_stronghold",
                "state": "surface_pending",
                "surfaceGenerated": True,
                "encounterReady": True,
                "center": [32, 32],
                "anchor": [0, 0, 0],
                "bounds": [0, 0, 0, 64, 48, 64],
                "controlledSpawns": {
                    "tiers": {
                        "stronghold": [
                            {
                                "entity": "tf_slice:block_chain_goblin",
                                "weight": 10,
                                "group": [1, 1],
                            }
                        ]
                    }
                },
            }
        }
        players = [
            {
                "playerId": "player",
                "dimensionId": 33027004,
                "position": [32.5, 31.0, 32.5],
            }
        ]

        self.service.tick(99, players, boss_spawning_enabled=False)
        self.assertEqual([], spawned)

        self.service.tick(100, players, boss_spawning_enabled=False)

        self.assertEqual("tf_slice:block_chain_goblin", spawned[0][0])
        self.assertEqual(33027004, spawned[0][3])
        status = self.service.debug_status()
        self.assertEqual(1, status["controlledStructureSpawnGroups"])
        self.assertEqual(1, status["controlledStructureSpawnEntities"])
        self.assertEqual(
            {"knight_stronghold": 1},
            status["controlledStructureSpawnGroupsByKind"],
        )

    def test_dark_tower_roof_uses_source_roof_spawn_tier(self):
        spawned = []

        def spawn_entity(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            return "spawned-%d" % len(spawned)

        self.service._entity_spawner = spawn_entity
        self.service._controlled_structure_spawn_candidates = (
            lambda _job, _player, _identifier, _seed, _attempts: [
                ((22.5, 78.0, 57.5), 180.0)
            ]
        )
        self.service._ledger = {
            "tower": {
                "kind": "dark_tower",
                "state": "surface_pending",
                "surfaceGenerated": True,
                "center": [56, 48],
                "anchor": [0, 0, 0],
                "bounds": [0, 0, 0, 111, 223, 95],
                "markers": {
                    "roofs": [
                        {
                            "tower": "stage_0_support_0",
                            "offset": [22, 77, 57],
                        }
                    ],
                    "wingTowers": [
                        {
                            "id": "stage_0_support_0",
                            "center": [22, 57],
                            "bottomY": 48,
                            "height": 29,
                            "size": 11,
                        }
                    ],
                    "bossPlatform": {"offset": [73, 203, 25], "radius": 8},
                },
                "controlledSpawns": {
                    "tiers": {
                        "lower": [
                            {
                                "entity": "tf_slice:carminite_golem",
                                "weight": 10,
                                "group": [1, 1],
                            }
                        ],
                        "roof": [
                            {
                                "entity": "tf_slice:tower_ghast",
                                "weight": 10,
                                "group": [1, 1],
                            }
                        ],
                        "water": [
                            {
                                "entity": "minecraft:squid",
                                "weight": 10,
                                "group": [1, 1],
                            }
                        ],
                    }
                },
            }
        }
        players = [
            {
                "playerId": "player",
                "dimensionId": 33027004,
                "position": [22.5, 48.0, 57.5],
            }
        ]

        self.service.tick(100, players, boss_spawning_enabled=False)

        self.assertEqual(["tf_slice:tower_ghast"], [row[0] for row in spawned])

    def test_dark_tower_roof_candidates_stay_over_authored_roof(self):
        job = {
            "kind": "dark_tower",
            "bounds": [0, 0, 0, 111, 223, 95],
            "anchor": [0, 0, 0],
            "markers": {
                "roofs": [
                    {
                        "tower": "stage_0_support_0",
                        "offset": [22, 77, 57],
                    }
                ],
                "wingTowers": [
                    {
                        "id": "stage_0_support_0",
                        "center": [22, 57],
                        "bottomY": 48,
                        "height": 29,
                        "size": 11,
                    }
                ],
                "bossPlatform": {"offset": [73, 203, 25], "radius": 8},
            },
        }
        player = {
            "dimensionId": 33027004,
            "position": [22.5, 48.0, 57.5],
        }

        candidates = self.service._controlled_structure_spawn_candidates(
            job,
            player,
            "tf_slice:tower_ghast",
            123456,
            12,
        )

        self.assertTrue(candidates)
        for position, _yaw in candidates:
            self.assertGreaterEqual(position[0], 18.5)
            self.assertLessEqual(position[0], 26.5)
            self.assertGreaterEqual(position[1], 78.0)
            self.assertLessEqual(position[1], 85.0)
            self.assertGreaterEqual(position[2], 53.5)
            self.assertLessEqual(position[2], 61.5)

    def test_controlled_spawn_keeps_twenty_four_blocks_from_every_player(self):
        players = [
            {
                "playerId": "first",
                "dimensionId": 33027004,
                "position": [0.5, 64.0, 0.5],
            },
            {
                "playerId": "second",
                "dimensionId": 33027004,
                "position": [100.5, 64.0, 0.5],
            },
        ]

        self.assertFalse(
            self.service._controlled_spawn_position_allowed(
                {},
                (123.5, 64.0, 0.5),
                players,
            )
        )
        self.assertTrue(
            self.service._controlled_spawn_position_allowed(
                {},
                (124.5, 64.0, 0.5),
                players,
            )
        )

    def test_controlled_spawn_rejects_all_authored_boss_areas(self):
        anchor = [100, 50, 200]
        cases = [
            (
                {
                    "kind": "labyrinth",
                    "anchor": anchor,
                    "markers": {
                        "boss": {"kind": "minoshroom", "offset": [43, 3, 73]},
                        "rooms": [
                            {
                                "kind": "minoshroom",
                                "origin": [36, 0, 66],
                                "size": [16, 5, 16],
                            }
                        ],
                    },
                },
                (143.5, 52.0, 273.5),
            ),
            (
                {
                    "kind": "knight_stronghold",
                    "anchor": anchor,
                    "markers": {
                        "bossRoom": {"offset": [60, -22, 69], "radius": 13}
                    },
                },
                (160.5, 28.0, 269.5),
            ),
            (
                {
                    "kind": "dark_tower",
                    "anchor": anchor,
                    "markers": {
                        "bossPlatform": {"offset": [73, 203, 25], "radius": 8}
                    },
                },
                (173.5, 255.0, 225.5),
            ),
            (
                {
                    "kind": "lich_tower",
                    "anchor": anchor,
                    "bossSpawner": {
                        "offset": [16, 49, 23],
                        "activationRadius": 9,
                    },
                },
                (116.5, 99.0, 223.5),
            ),
        ]

        for job, position in cases:
            self.assertFalse(
                self.service._controlled_spawn_position_allowed(job, position, []),
                job["kind"],
            )

    def test_labyrinth_never_spawns_a_group_beside_the_player(self):
        spawned = []
        self.service._entity_spawner = (
            lambda *args: spawned.append(args) or "spawned-%d" % len(spawned)
        )
        self.factory.block.GetBlockNew = lambda position, _dimension: {
            "name": "tf_slice:mazestone"
            if int(position[1]) == 11
            else "minecraft:air",
            "aux": 0,
        }
        job = {
            "kind": "labyrinth",
            "state": "complete",
            "center": [55, 55],
            "anchor": [0, 0, 0],
            "bounds": [0, 0, 0, 110, 53, 110],
            "controlledSpawns": {
                "cap": 18,
                "weights": [
                    {
                        "entity": "tf_slice:minotaur",
                        "weight": 20,
                        "group": [2, 3],
                    }
                ],
            },
            "markers": {
                "spawnZones": [
                    {"level": 0, "center": [55, 12, 55], "radius": 7}
                ]
            },
        }
        self.service._ledger = {"55,55": job}
        self.service._rebuild_runtime_job_indexes()
        players = [
            {
                "playerId": "player",
                "dimensionId": 33027004,
                "position": [55.5, 12.0, 55.5],
            }
        ]

        self.service._spawn_labyrinth_monsters(100, players)

        self.assertEqual([], spawned)

    def test_stronghold_upper_rider_counts_against_local_monster_cap(self):
        spawned = []
        self.service._entity_spawner = lambda *args: spawned.append(args) or "new"
        self.service._controlled_structure_spawn_candidates = (
            lambda *_args: [((32.5, 31.0, 32.5), 90.0)]
        )
        self.factory.game.entities = ["upper-knight"]
        self.factory.entity_types["upper-knight"] = "tf_slice:upper_goblin_knight"
        self.service._ledger = {
            "stronghold": {
                "kind": "knight_stronghold",
                "state": "complete",
                "center": [32, 32],
                "anchor": [0, 0, 0],
                "bounds": [0, 0, 0, 64, 48, 64],
                "controlledSpawns": {
                    "cap": 1,
                    "tiers": {
                        "stronghold": [
                            {
                                "entity": "tf_slice:lower_goblin_knight",
                                "weight": 5,
                                "group": [1, 1],
                            }
                        ]
                    },
                },
            }
        }
        players = [
            {
                "playerId": "player",
                "dimensionId": 33027004,
                "position": [32.5, 31.0, 32.5],
            }
        ]

        self.service.tick(100, players, boss_spawning_enabled=False)

        self.assertEqual([], spawned)

    def test_structure_cap_counts_the_entire_structure_bounds(self):
        queries = []

        def entities_in_area(_entity_id, minimum, maximum, dimension_id):
            queries.append((minimum, maximum, dimension_id))
            return []

        self.factory.game.GetEntitiesInSquareArea = entities_in_area
        job = {
            "kind": "dark_tower",
            "bounds": [100, 20, 200, 211, 243, 295],
        }
        player = {
            "dimensionId": 33027004,
            "position": [155.5, 40.0, 247.5],
        }

        count = self.service._count_controlled_structure_monsters(
            job,
            player,
            {"tf_slice:carminite_golem"},
            18,
        )

        self.assertEqual(0, count)
        self.assertEqual(
            [
                (
                    (100, 20, 200),
                    (212, 244, 296),
                    33027004,
                )
            ],
            queries,
        )

    def test_labyrinth_count_query_failure_closes_the_full_cap(self):
        def fail_query(*_args):
            raise RuntimeError("query unavailable")

        self.factory.game.GetEntitiesInSquareArea = fail_query

        self.assertEqual(
            18,
            self.service._count_labyrinth_monsters(
                {"bounds": [0, 0, 0, 110, 53, 110]},
                {"tf_slice:minotaur", "tf_slice:maze_slime"},
                18,
            ),
        )

    def test_regular_structure_mobs_despawn_while_bosses_persist(self):
        from tools import build_dark_tower_content
        from tools import build_hydra_route_models
        from tools import build_knight_stronghold_content

        regular = (
            "block_chain_goblin",
            "lower_goblin_knight",
            "upper_goblin_knight",
            "helmet_crab",
            "carminite_golem",
            "tower_broodling",
            "mini_ghast",
            "tower_ghast",
            "towerwood_borer",
            "minotaur",
            "maze_slime",
        )
        for identifier in regular:
            document = json.loads(
                (BP / "entities" / (identifier + ".entity.json")).read_text(
                    encoding="utf-8"
                )
            )
            components = document["minecraft:entity"]["components"]
            self.assertIn("minecraft:despawn", components, identifier)
            self.assertNotIn("minecraft:persistent", components, identifier)

        for identifier in ("knight_phantom", "ur_ghast"):
            document = json.loads(
                (BP / "entities" / (identifier + ".entity.json")).read_text(
                    encoding="utf-8"
                )
            )
            components = document["minecraft:entity"]["components"]
            self.assertIn("minecraft:persistent", components, identifier)
            self.assertNotIn("minecraft:despawn", components, identifier)

        for identifier in (
            "block_chain_goblin",
            "lower_goblin_knight",
            "upper_goblin_knight",
            "helmet_crab",
        ):
            generated = build_knight_stronghold_content._hostile_entity(
                identifier,
                build_knight_stronghold_content.ENTITY_STATS[identifier],
            )["minecraft:entity"]["components"]
            self.assertIn("minecraft:despawn", generated, identifier)
            self.assertNotIn("minecraft:persistent", generated, identifier)
        generated_knight = build_knight_stronghold_content._hostile_entity(
            "knight_phantom",
            build_knight_stronghold_content.ENTITY_STATS["knight_phantom"],
        )["minecraft:entity"]["components"]
        self.assertIn("minecraft:persistent", generated_knight)

        for identifier in (
            "carminite_golem",
            "tower_broodling",
            "mini_ghast",
            "tower_ghast",
            "towerwood_borer",
        ):
            generated = build_dark_tower_content.hostile_entity(
                identifier,
                build_dark_tower_content.ENTITY_STATS[identifier],
            )["minecraft:entity"]["components"]
            self.assertIn("minecraft:despawn", generated, identifier)
            self.assertNotIn("minecraft:persistent", generated, identifier)
        generated_ur_ghast = build_dark_tower_content.hostile_entity(
            "ur_ghast",
            build_dark_tower_content.ENTITY_STATS["ur_ghast"],
        )["minecraft:entity"]["components"]
        self.assertIn("minecraft:persistent", generated_ur_ghast)

        generated_minotaur = build_hydra_route_models.configure_charger(
            build_hydra_route_models.behavior_entity(
                "minotaur", 30, 0.25, 0, (0.7, 2.4)
            ),
            "minotaur",
            "loot_tables/equipment/tf_slice/minotaur.json",
        )["minecraft:entity"]["components"]
        generated_slime = build_hydra_route_models.maze_slime_behavior()[
            "minecraft:entity"
        ]["components"]
        self.assertIn("minecraft:despawn", generated_minotaur)
        self.assertIn("minecraft:despawn", generated_slime)

    def test_structure_spawn_pacing_uses_random_ten_to_twenty_second_cooldown(self):
        job = {
            "kind": "knight_stronghold",
            "center": [128, 256],
        }
        outcomes = set()
        for index in range(24):
            ledger_key = "stronghold-%d" % index
            outcomes.add(
                self.service._controlled_spawn_attempt_due(
                    ledger_key,
                    job,
                    100,
                )
            )
            next_tick = self.service._controlled_spawn_next_ticks[ledger_key]
            self.assertGreaterEqual(next_tick, 300)
            self.assertLessEqual(next_tick, 500)
            self.assertFalse(
                self.service._controlled_spawn_attempt_due(
                    ledger_key,
                    job,
                    next_tick - 1,
                )
            )
        self.assertEqual({False, True}, outcomes)

    def test_every_scripted_structure_scanner_uses_shared_pacing_gate(self):
        source = SERVICE_PATH.read_text(encoding="utf-8")
        scanners = (
            "_spawn_hollow_hill_monsters",
            "_spawn_lich_tower_monsters",
            "_spawn_labyrinth_monsters",
            "_spawn_controlled_structure_monsters",
        )
        for index, name in enumerate(scanners):
            start = source.index("    def %s(" % name)
            end = (
                source.index("    def ", start + 8)
                if index < len(scanners) - 1
                else len(source)
            )
            self.assertIn(
                "_controlled_spawn_attempt_due(",
                source[start:end],
                name,
            )

    def test_dark_tower_player_in_water_uses_source_water_spawn_tier(self):
        self.factory.block.blocks[(20, 40, 20)] = {
            "name": "minecraft:water",
            "aux": 0,
        }
        job = {
            "kind": "dark_tower",
            "controlledSpawns": {
                "tiers": {
                    "lower": [{"entity": "tf_slice:carminite_golem"}],
                    "roof": [{"entity": "tf_slice:tower_ghast"}],
                    "water": [{"entity": "minecraft:squid"}],
                }
            },
        }
        player = {
            "dimensionId": 33027004,
            "position": [20.5, 40.0, 20.5],
        }

        tier, entries = self.service._controlled_structure_spawn_table(
            job,
            player,
        )

        self.assertEqual("water", tier)
        self.assertEqual(["minecraft:squid"], [row["entity"] for row in entries])

    def test_dark_forest_controlled_pool_matches_upstream_weights(self):
        self.assertEqual(
            (
                ("minecraft:enderman", 2, 1, 2),
                ("minecraft:zombie", 5, 1, 2),
                ("minecraft:skeleton", 5, 1, 2),
                ("tf_slice:mist_wolf", 5, 1, 1),
                ("tf_slice:skeleton_druid", 5, 1, 1),
                ("tf_slice:king_spider", 1, 1, 1),
                ("tf_slice:kobold", 10, 1, 3),
                ("minecraft:witch", 2, 1, 1),
            ),
            SERVICE.DARK_FOREST_CONTROLLED_SPAWNS,
        )

    def test_dark_forest_controlled_spawn_bypasses_native_weight_starvation(self):
        spawned = []
        self.service._entity_spawner = (
            lambda *args: spawned.append(args) or "spawned-%d" % len(spawned)
        )
        self.factory.biome.name = SERVICE.biome_catalog.BIOMES_BY_KEY[
            "dark_forest"
        ]["identifier"]
        self.service._dark_forest_spawn_choice = lambda _seed: {
            "entity": "tf_slice:kobold",
            "count": 1,
        }
        self.service._dark_forest_spawn_candidates = (
            lambda _player, _seed, _limit: [((30.5, 64.0, 0.5), 90.0)]
        )
        self.factory.block.GetBlockNew = lambda position, _dimension: {
            "name": "minecraft:stone"
            if int(position[1]) == 63
            else "minecraft:air",
            "aux": 0,
        }
        player = {
            "playerId": "player",
            "dimensionId": 33027004,
            "position": [0.5, 64.0, 0.5],
        }

        self.service.tick(
            SERVICE.DARK_FOREST_SPAWN_INTERVAL_TICKS,
            [player],
            boss_spawning_enabled=True,
        )

        self.assertEqual("tf_slice:kobold", spawned[0][0])
        self.assertEqual((30.5, 64.0, 0.5), spawned[0][1])

    def test_dark_forest_controlled_spawn_respects_cap_and_exact_biome(self):
        spawned = []
        self.service._entity_spawner = (
            lambda *args: spawned.append(args) or "spawned-%d" % len(spawned)
        )
        self.service._dark_forest_spawn_choice = lambda _seed: {
            "entity": "tf_slice:kobold",
            "count": 1,
        }
        self.service._dark_forest_spawn_candidates = (
            lambda _player, _seed, _limit: [((30.5, 64.0, 0.5), 90.0)]
        )
        player = {
            "playerId": "player",
            "dimensionId": 33027004,
            "position": [0.5, 64.0, 0.5],
        }

        self.factory.biome.name = "dm33027004_plains"
        self.service.tick(
            SERVICE.DARK_FOREST_SPAWN_INTERVAL_TICKS,
            [player],
            boss_spawning_enabled=True,
        )
        self.assertEqual([], spawned)

        self.factory.biome.name = SERVICE.biome_catalog.BIOMES_BY_KEY[
            "dark_forest"
        ]["identifier"]
        self.factory.game.entities = [
            "dark-mob-%d" % index
            for index in range(SERVICE.DARK_FOREST_LOCAL_MONSTER_CAP)
        ]
        self.factory.entity_types.update(
            (entity_id, "tf_slice:kobold")
            for entity_id in self.factory.game.entities
        )
        self.service.tick(
            SERVICE.DARK_FOREST_SPAWN_INTERVAL_TICKS * 2,
            [player],
            boss_spawning_enabled=True,
        )
        self.assertEqual([], spawned)

    def test_conquered_structures_disable_source_controlled_spawns(self):
        self.assertTrue(
            self.service._controlled_structure_is_conquered(
                {"kind": "labyrinth", "bossDefeated": True}
            )
        )
        self.assertTrue(
            self.service._controlled_structure_is_conquered(
                {
                    "kind": "knight_stronghold",
                    "bossGroupDefeated": True,
                }
            )
        )
        self.assertTrue(
            self.service._controlled_structure_is_conquered(
                {"kind": "dark_tower", "bossDefeated": True}
            )
        )
        self.assertFalse(
            self.service._controlled_structure_is_conquered(
                {"kind": "dark_tower"}
            )
        )

    def test_load_migrates_labyrinth_spawner_to_source_activation_contract(self):
        self.factory.extra.data[SERVICE.LEDGER_KEY] = {
            "8,8": {
                "entryId": "labyrinth",
                "kind": "labyrinth",
                "state": "complete",
                "center": [8, 8],
                "anchor": [0, 64, 0],
                "bounds": [0, 64, 0, 111, 117, 111],
                "variant": 0,
                "bossSpawner": {
                    "kind": "minoshroom",
                    "entity": "tf_slice:minoshroom",
                    "offset": [40, 2, 40],
                    "markerBlock": "tf_slice:minoshroom_boss_spawner",
                    "spawnYOffset": 1.0,
                    "activationRadius": 20,
                    "progressAll": ["lich_defeated"],
                },
                "bossSpawnerReady": True,
                "bossSpawned": False,
                "bossDefeated": False,
            }
        }

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )
        spawner = service._ledger["8,8"]["bossSpawner"]

        self.assertEqual(9, spawner["activationRadius"])
        self.assertEqual(-1.5, spawner["spawnYOffset"])
        self.assertEqual(3.5, spawner["maxPlayerYOffset"])
        self.assertNotIn("progressAll", spawner)

    @staticmethod
    def accepted_event():
        return {
            "structureName": "tf_slice:ruins/druid_hut/druid_hut",
            "x": 112,
            "y": 52,
            "z": -48,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }

    def test_load_retires_hills_failed_by_old_runtime_carve(self):
        job = SERVICE.ruin_logic.create_landmark_job(
            "small_hill",
            (0, 64, 0),
            0,
            [],
            [0, 60, 0, 47, 80, 47],
        )
        job["state"] = "failed"
        job["retries"] = 3
        job["hollowHillCarve"] = {
            "nextColumn": 12,
            "nextY": 67,
            "blocksCleared": 123,
            "complete": False,
        }
        self.factory.extra.data[SERVICE.LEDGER_KEY] = {"0,0": job}

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )

        loaded = service._ledger["0,0"]
        self.assertEqual("retired", loaded["state"])
        self.assertEqual("runtime_worldgen_disabled", loaded["reason"])
        self.assertEqual(0, loaded["retries"])
        self.assertEqual(123, loaded["hollowHillCarve"]["blocksCleared"])
        self.assertEqual(
            SERVICE.HOLLOW_HILL_CARVE_POLICY_VERSION,
            loaded["hollowHillCarvePolicyVersion"],
        )

    def test_load_retires_old_chunk_assembly_without_repairing_it(self):
        job = SERVICE.ruin_logic.create_landmark_job(
            "naga_courtyard",
            (1, 64, 1),
            0,
            [
                {
                    "structure": (
                        "tf_slice/ruins/naga_courtyard/v00/x000_z000"
                    ),
                    "offset": [0, 0, 0],
                    "size": [16, 12, 16],
                }
            ],
            [1, 64, 1, 16, 75, 16],
        )
        job["state"] = "complete"
        job["nextPiece"] = 1
        job["completedPieces"] = [0]
        job["terrain"] = {
            "mode": "flatten",
            "width": 16,
            "depth": 16,
            "flatRadius": 48.0,
            "blendWidth": 8.0,
            "nextColumn": 256,
            "complete": True,
        }
        job["chunkSlices"] = {
            "0,0": {
                "chunkX": 0,
                "chunkZ": 0,
                "terrainComplete": True,
                "carveComplete": True,
                "pieceIndices": [0],
                "complete": True,
            }
        }
        self.factory.extra.data[SERVICE.LEDGER_KEY] = {"9,9": job}

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )

        loaded = service._ledger["9,9"]
        self.assertEqual("retired", loaded["state"])
        self.assertEqual("runtime_worldgen_disabled", loaded["reason"])
        self.assertEqual([], loaded["completedPieces"])
        self.assertEqual(0, loaded["nextPiece"])
        self.assertEqual(0, loaded["terrain"]["nextColumn"])
        self.assertFalse(loaded["terrain"]["complete"])
        self.assertNotIn("chunkSlices", loaded)
        self.assertEqual(
            SERVICE.CHUNK_ASSEMBLY_POLICY_VERSION,
            loaded["chunkAssemblyPolicyVersion"],
        )

    def test_missing_courtyard_naga_rearms_the_persisted_spawner(self):
        job = SERVICE.ruin_logic.create_landmark_job(
            "naga_courtyard",
            (0, 64, 0),
            0,
            [],
            [0, 64, 0, 15, 75, 15],
        )
        job["state"] = "complete"
        job["bossSpawner"] = {
            "entity": "tf_slice:forest_wyrm",
            "offset": [5, 1, 5],
            "activationRadius": 32,
        }
        job["bossSpawnerReady"] = True
        job["bossSpawned"] = True
        job["bossDefeated"] = False
        job["bossEntityId"] = "-8589934527"
        self.service._ledger["0,0"] = job
        self.service._rebuild_runtime_job_indexes()

        changed = self.service.mark_naga_missing(
            (5.5, 66.0, 5.5),
            -8589934527,
        )

        self.assertTrue(changed)
        self.assertFalse(job["bossSpawned"])
        self.assertFalse(job["bossDefeated"])
        self.assertNotIn("bossEntityId", job)

    def test_load_preserves_an_old_surface_courtyard_without_rebuilding_it(self):
        self.factory.extra.data[SERVICE.LEDGER_KEY] = {
            "8,8": {
                "entryId": "naga_courtyard",
                "kind": "naga_courtyard",
                "state": "complete",
                "center": [8, 8],
                "anchor": [-44, 64, -44],
                "bounds": [-44, 64, -44, 59, 75, 59],
                "variant": 0,
                "surfaceGenerated": True,
                "generationSource": "surface_feature",
                "pieces": [],
                "nextPiece": 0,
                "bossSpawner": {
                    "entity": "tf_slice:forest_wyrm",
                    "offset": [52, 2, 52],
                    "activationRadius": 32,
                },
                "bossSpawned": False,
                "bossDefeated": False,
                "bossSpawnerReady": True,
                "courtyardLayoutPolicyVersion": 2,
            }
        }

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )
        loaded = service._ledger["8,8"]

        self.assertEqual("surface_pending", loaded["state"])
        self.assertNotIn("reason", loaded)
        self.assertEqual([], loaded["pieces"])
        self.assertEqual(0, loaded["nextPiece"])
        self.assertTrue(loaded["surfaceGenerated"])
        self.assertEqual("surface_feature", loaded["generationSource"])
        self.assertNotIn("terrain", loaded)
        self.assertFalse(loaded["bossSpawnerReady"])
        self.assertEqual(
            SERVICE.COURTYARD_LAYOUT_POLICY_VERSION,
            loaded["courtyardLayoutPolicyVersion"],
        )

    def test_native_worldgen_stays_in_engine_and_only_enqueues_plain_data(self):
        event = self.accepted_event()

        self.service.on_structure_feature_event(event)

        self.assertFalse(event["cancel"])
        self.assertEqual(self.factory.game.placements, [])
        self.assertEqual(
            self.service.debug_status()["nativeHandoffs"],
            1,
        )

    def _surface_event_for_supported_region(self, mode="ordinary"):
        for region_x in range(-8, 9):
            for region_z in range(-8, 9):
                center_x, center_z = (
                    SERVICE.ruin_logic.nearest_landmark_center(
                        region_x * 16,
                        region_z * 16,
                    )
                )
                kind = self.service._surface_landmark_kind(
                    mode,
                    center_x,
                    center_z,
                )
                if kind is None:
                    continue
                trigger = SERVICE.SURFACE_LANDMARK_TRIGGER_BY_MODE[mode]
                return {
                    "structureName": trigger,
                    "x": (center_x >> 4) * 16,
                    "y": 32,
                    "z": (center_z >> 4) * 16,
                    "biomeName": "dm33027004_plains",
                    "dimensionId": 33027004,
                    "cancel": False,
                }, kind, (center_x, center_z)
        self.fail("no supported surface landmark region found")

    @staticmethod
    def _naga_surface_event(delta_x=0, delta_z=0):
        # With the fixture world seed, this legacy-grid cell resolves to the
        # Naga courtyard.  Each event represents one independently generated
        # 16x16 surface-native tile.
        center_x, center_z = (-247, 8)
        return {
            "structureName": SERVICE.SURFACE_LANDMARK_TRIGGER_BY_MODE[
                "ordinary"
            ],
            "x": ((center_x >> 4) + int(delta_x)) * 16,
            "y": 32,
            "z": ((center_z >> 4) + int(delta_z)) * 16,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }

    @staticmethod
    def _lich_surface_event(delta_x=0, delta_z=0):
        center_x, center_z = (8, 232)
        return {
            "structureName": (
                SERVICE.SURFACE_LANDMARK_TRIGGER_BY_MODE["ordinary"]
            ),
            "x": ((center_x >> 4) + int(delta_x)) * 16,
            "y": 32,
            "z": ((center_z >> 4) + int(delta_z)) * 16,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }

    def test_single_surface_trigger_routes_naga_before_decorations(self):
        event = self._naga_surface_event()
        self.service.on_structure_feature_event(event)

        self.assertFalse(event["cancel"])
        self.assertTrue(
            event["structureName"].startswith(
                "tf_slice:ruins/surface_native/naga_courtyard/"
            )
        )

    def test_shifted_naga_outer_tile_routes_back_to_neighboring_center(self):
        # This is the 0.10.46 field reproducer.  The courtyard center is three
        # chunks south of its nominal 256-block region origin, so its +5 tile
        # belongs to the next rounded region even though it is still part of
        # the courtyard's declared surface-native envelope.
        self.service._world_seed = -7945468216960165124
        center_x, center_z = (280, 56)
        event = {
            "structureName": SERVICE.SURFACE_LANDMARK_TRIGGER_BY_MODE[
                "ordinary"
            ],
            "x": (center_x >> 4) * 16,
            "y": 32,
            "z": ((center_z >> 4) + 5) * 16,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }

        self.service.on_structure_feature_event(event)

        self.assertEqual(
            (
                "tf_slice:ruins/surface_native/naga_courtyard/v05/"
                "mx08_mz08/xp00_zp05"
            ),
            event["structureName"],
        )

    def test_shifted_naga_routes_every_declared_tile_to_one_center(self):
        self.service._world_seed = -7945468216960165124
        center_x, center_z = (280, 56)
        center_chunk_x = center_x >> 4
        center_chunk_z = center_z >> 4

        for delta_x in range(-5, 6):
            for delta_z in range(-5, 6):
                selected = self.service._surface_native_tile(
                    "ordinary",
                    center_chunk_x + delta_x,
                    center_chunk_z + delta_z,
                    32,
                )
                expected_suffix = "/x%s%02d_z%s%02d" % (
                    "m" if delta_x < 0 else "p",
                    abs(delta_x),
                    "m" if delta_z < 0 else "p",
                    abs(delta_z),
                )

                with self.subTest(delta=(delta_x, delta_z)):
                    self.assertIsNotNone(selected)
                    reference, record = selected
                    self.assertEqual([center_x, center_z], record["center"])
                    self.assertIn("/naga_courtyard/v05/", reference)
                    self.assertTrue(reference.endswith(expected_suffix))

    def test_surface_landmark_event_replaces_trigger_with_real_chunk_tile(self):
        event, kind, center = self._surface_event_for_supported_region()

        self.service.on_structure_feature_event(event)

        self.assertFalse(event["cancel"])
        self.assertTrue(
            event["structureName"].startswith(
                "tf_slice:ruins/surface_native/%s/" % kind
            )
        )
        self.assertEqual([], self.factory.game.placements)
        self.assertEqual([], self.factory.chunk.added)
        self.assertEqual(
            1,
            self.service.debug_status()["surfaceLandmarkHandoffs"],
        )

        self.service.tick(1, [])

        job = self.service._ledger["%d,%d" % center]
        self.assertEqual("surface_pending", job["state"])
        self.assertTrue(job["surfaceGenerated"])
        self.assertEqual(kind, job["kind"])
        self.assertEqual("surface_feature", job["generationSource"])
        self.assertEqual(1, len(job["surfaceTiles"]))
        self.assertGreater(len(job["surfaceExpectedTiles"]), 1)
        self.assertEqual([], self.factory.game.placements)
        self.assertEqual([], self.factory.chunk.added)

    def test_surface_naga_finishes_in_worldgen_without_tick_edge_edits(self):
        first = self._naga_surface_event(-3, -3)
        center = self._naga_surface_event(0, 0)

        self.service.on_structure_feature_event(first)
        self.service.tick(1, [])

        job = self.service._ledger["-247,8"]
        self.assertEqual("surface_pending", job["state"])
        self.assertEqual(["-3,-3"], job["surfaceTiles"])
        self.assertGreater(len(job["surfaceExpectedTiles"]), 1)
        self.assertFalse(job["bossSpawnerReady"])

        self.service.on_structure_feature_event(center)
        self.service.tick(2, [])

        self.assertEqual(2, len(job["surfaceTiles"]))
        self.assertEqual("surface_pending", job["state"])
        self.assertFalse(job["bossSpawnerReady"])

        for tile_key in job["surfaceExpectedTiles"]:
            delta_x, delta_z = [
                int(value) for value in tile_key.split(",", 1)
            ]
            if (delta_x, delta_z) in ((-3, -3), (0, 0)):
                continue
            self.service.on_structure_feature_event(
                self._naga_surface_event(delta_x, delta_z)
            )
        expected_count = len(job["surfaceExpectedTiles"])
        final_tick = 3
        while self.service.debug_status()["surfaceLandmarkHandoffs"]:
            self.service.tick(final_tick, [])
            final_tick += 1

        self.assertEqual(expected_count, len(job["surfaceTiles"]))
        self.assertEqual("complete", job["state"])
        self.assertNotIn("edgeBlend", job)
        self.assertTrue(job["bossSpawnerReady"])
        self.assertEqual([], self.factory.block.set_blocks)

    def test_surface_edge_blend_preserves_native_surface_and_tree_roots(self):
        blend = {
            "width": 16,
            "shape": "rounded_rectangle",
            "coreSize": [16, 6, 16],
            "nextColumn": 0,
            "complete": False,
        }
        job = {
            "kind": "hedge_maze",
            "anchor": [100, 64, 100],
            "edgeBlend": blend,
        }
        # First column immediately west of the core, halfway along its edge.
        column_index = 24 * 48 + 15
        world_x, world_z = 99, 108

        self.factory.block.blocks[(world_x, 60, world_z)] = {
            "name": "minecraft:podzol",
            "aux": 0,
        }
        outer_world_x = 84
        self.factory.block.blocks[(outer_world_x, 60, world_z)] = {
            "name": "minecraft:podzol",
            "aux": 0,
        }
        self.factory.block.GetTopBlockHeight = (
            lambda position, _dimension_id: 60
            if tuple(position)
            in ((world_x, world_z), (outer_world_x, world_z))
            else 64
        )
        column = self.service._prepare_surface_edge_blend_column(
            job,
            blend,
            column_index,
        )
        self.assertIn([64, "minecraft:podzol"], column["changes"])
        self.assertNotIn(
            "minecraft:moss_block",
            [change[1] for change in column["changes"]],
        )
        outer_column = self.service._prepare_surface_edge_blend_column(
            job,
            blend,
            24 * 48,
        )
        self.assertEqual([], outer_column["changes"])

        self.factory.block.blocks[(world_x, 72, world_z)] = {
            "name": "minecraft:grass_block",
            "aux": 0,
        }
        self.factory.block.blocks[(world_x, 73, world_z)] = {
            "name": "tf_slice:canopy_log",
            "aux": 0,
        }
        self.factory.block.GetTopBlockHeight = (
            lambda position, _dimension_id: 73
            if tuple(position) == (world_x, world_z)
            else 64
        )
        column = self.service._prepare_surface_edge_blend_column(
            job,
            blend,
            column_index,
        )
        self.assertTrue(column["skip"])
        self.assertEqual("tree_root", column["reason"])

    def test_surface_edge_blend_preserves_water_above_the_blended_floor(self):
        blend = {
            "width": 16,
            "shape": "rounded_rectangle",
            "coreSize": [16, 6, 16],
            "nextColumn": 0,
            "complete": False,
        }
        job = {
            "kind": "hedge_maze",
            "anchor": [100, 58, 100],
            "edgeBlend": blend,
        }
        column_index = 24 * 48 + 15
        world_x, world_z = 99, 108
        self.factory.block.blocks[(world_x, 60, world_z)] = {
            "name": "minecraft:sand",
            "aux": 0,
        }
        for y in range(61, 65):
            self.factory.block.blocks[(world_x, y, world_z)] = {
                "name": "minecraft:water",
                "aux": 0,
            }
        self.factory.block.GetTopBlockHeight = (
            lambda position, _dimension_id: 64
            if tuple(position) == (world_x, world_z)
            else 64
        )

        column = self.service._prepare_surface_edge_blend_column(
            job,
            blend,
            column_index,
        )

        self.assertIn([58, "minecraft:sand"], column["changes"])
        self.assertIn([64, "minecraft:water"], column["changes"])

    def test_incomplete_surface_naga_stays_pending_near_player(self):
        first = self._naga_surface_event(-3, -3)
        self.service.on_structure_feature_event(first)
        self.service.tick(1, [])

        job = self.service._ledger["-247,8"]
        missing_tile = "3,0"
        for tile_key in job["surfaceExpectedTiles"]:
            if tile_key in ("-3,-3", missing_tile):
                continue
            delta_x, delta_z = [
                int(value) for value in tile_key.split(",", 1)
            ]
            self.service.on_structure_feature_event(
                self._naga_surface_event(delta_x, delta_z)
            )
        current_tick = 2
        while self.service.debug_status()["surfaceLandmarkHandoffs"]:
            self.service.tick(current_tick, [])
            current_tick += 1

        self.assertEqual("surface_pending", job["state"])
        self.assertEqual(
            len(job["surfaceExpectedTiles"]) - 1,
            len(job["surfaceTiles"]),
        )

        self.service.tick(
            job["surfaceLastSeenTick"]
            + SERVICE.SURFACE_TILE_SETTLE_TICKS,
            [
                {
                    "dimensionId": 33027004,
                    "position": (-196.0, 65.0, 8.0),
                }
            ],
        )

        self.assertEqual("surface_feature", job["generationSource"])
        self.assertEqual("surface_pending", job["state"])
        self.assertEqual([], job["pieces"])
        self.assertTrue(job["surfaceGenerated"])
        self.assertNotIn("terrain", job)
        self.assertFalse(job["bossSpawnerReady"])

    def test_incomplete_surface_lich_stays_pending_near_player(self):
        first = self._lich_surface_event(-2, -2)
        self.service.on_structure_feature_event(first)
        self.service.tick(1, [])

        job = self.service._ledger["8,232"]
        missing_tile = job["surfaceBossTile"]
        self.assertNotEqual("-2,-2", missing_tile)
        for tile_key in job["surfaceExpectedTiles"]:
            if tile_key in ("-2,-2", missing_tile):
                continue
            delta_x, delta_z = [
                int(value) for value in tile_key.split(",", 1)
            ]
            self.service.on_structure_feature_event(
                self._lich_surface_event(delta_x, delta_z)
            )
        current_tick = 2
        while self.service.debug_status()["surfaceLandmarkHandoffs"]:
            self.service.tick(current_tick, [])
            current_tick += 1

        self.assertEqual("lich_tower", job["kind"])
        self.assertEqual("surface_pending", job["state"])
        self.assertNotIn(missing_tile, job["surfaceTiles"])
        self.assertFalse(job["bossSpawnerReady"])

        self.service.tick(
            job["surfaceLastSeenTick"]
            + SERVICE.SURFACE_TILE_SETTLE_TICKS,
            [
                {
                    "dimensionId": 33027004,
                    "position": (8.0, 80.0, 232.0),
                }
            ],
        )

        self.assertEqual("lich_tower", job["kind"])
        self.assertEqual("lich_tower", job["entryId"])
        self.assertEqual("lich", job["bossKind"])
        self.assertEqual("surface_feature", job["generationSource"])
        self.assertEqual("surface_pending", job["state"])
        self.assertEqual([], job["pieces"])
        self.assertTrue(job["surfaceGenerated"])
        self.assertNotIn("terrain", job)
        self.assertFalse(job["bossSpawnerReady"])

    def test_surface_landmark_event_uses_noop_outside_selected_landmark(self):
        event, _kind, center = self._surface_event_for_supported_region()
        event["x"] = ((center[0] >> 4) + 7) * 16
        event["z"] = ((center[1] >> 4) + 7) * 16

        self.service.on_structure_feature_event(event)

        self.assertFalse(event["cancel"])
        self.assertEqual("tf_slice:ruin_landmark_noop", event["structureName"])
        self.assertEqual(
            0,
            self.service.debug_status()["surfaceLandmarkHandoffs"],
        )

    def test_surface_landmark_has_no_paired_naga_trigger(self):
        self.assertFalse(
            hasattr(SERVICE, "NAGA_SURFACE_LANDMARK_TRIGGER_BY_MODE")
        )
        self.assertIn(
            SERVICE.LANDMARK_NOOP_STRUCTURE,
            self.service._whitelisted_structures,
        )

    def test_all_surface_biome_modes_select_a_real_native_tile(self):
        for mode in (
            "ordinary",
            "dense_mushroom",
            "enchanted",
            "swamp",
            "fire_swamp",
            "dark_forest",
            "dark_forest_center",
        ):
            event, kind, _center = self._surface_event_for_supported_region(
                mode
            )

            self.service.on_structure_feature_event(event)

            self.assertFalse(event["cancel"], mode)
            self.assertTrue(
                event["structureName"].startswith(
                    "tf_slice:ruins/surface_native/%s/" % kind
                ),
                mode,
            )

    def test_surface_handoff_wins_race_with_loaded_chunk_fallback(self):
        event, kind, center = self._surface_event_for_supported_region()
        self.service.on_structure_feature_event(event)

        self.service.on_chunk_loaded_event(
            {
                "dimension": 33027004,
                "chunkPosX": center[0] >> 4,
                "chunkPosZ": center[1] >> 4,
            }
        )

        status = self.service.debug_status()
        self.assertEqual(1, status["surfaceLandmarkHandoffs"])
        self.assertEqual(0, status["landmarkTriggers"])

        self.service.tick(1, [])

        job = self.service._ledger["%d,%d" % center]
        self.assertEqual(kind, job["kind"])
        self.assertEqual("surface_pending", job["state"])
        self.assertEqual("surface_feature", job["generationSource"])

    def test_real_native_worldgen_is_left_to_engine_and_only_records_location(self):
        event = self.accepted_event()
        event["structureName"] = "tf_slice:ruins/druid_hut/druid_hut"

        self.service.on_structure_feature_event(event)
        self.service.tick(1, [])

        self.assertFalse(event["cancel"])
        self.assertEqual([], self.factory.game.placements)
        self.assertEqual([], self.factory.chunk.added)
        records = [
            job
            for key, job in self.service._ledger.items()
            if key.startswith("native:")
        ]
        self.assertEqual(1, len(records))
        self.assertEqual("complete", records[0]["state"])
        self.assertEqual("druid_hut", records[0]["kind"])
        self.assertEqual(0, self.service.debug_status()["nativeHandoffs"])

    def test_load_drops_legacy_native_backlog_but_keeps_complete_records(self):
        self.factory.extra.data[SERVICE.LEDGER_KEY] = {
            "native:planned": {
                "state": "planned",
                "kind": "druid_hut",
            },
            "native:placing": {
                "state": "placing",
                "kind": "well",
            },
            "native:complete": {
                "state": "complete",
                "kind": "monolith",
                "anchor": [0, 64, 0],
            },
            "24,808": {
                "state": "planned",
                "kind": "naga_courtyard",
                "center": [24, 808],
            },
        }

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )

        self.assertNotIn("native:planned", service._ledger)
        self.assertNotIn("native:placing", service._ledger)
        self.assertIn("native:complete", service._ledger)
        self.assertIn("24,808", service._ledger)

    def test_legacy_landmark_trigger_becomes_noop_without_scheduling_work(self):
        event = {
            "structureName": SERVICE.LANDMARK_TRIGGER_STRUCTURE,
            "x": -247,
            "y": 64,
            "z": 8,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }

        self.service.on_structure_feature_event(event)

        self.assertFalse(event["cancel"])
        self.assertEqual("tf_slice:ruin_landmark_noop", event["structureName"])
        self.assertEqual(
            0,
            self.service.debug_status()["landmarkTriggers"],
        )

    def test_surface_watchdog_becomes_noop_without_scheduling_work(self):
        event = {
            "structureName": "tf_slice:ruin_landmark_surface_watchdog",
            "x": -256,
            "y": 0,
            "z": 0,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }

        self.service.on_structure_feature_event(event)
        self.service.on_structure_feature_event(dict(event))

        self.assertFalse(event["cancel"])
        self.assertEqual("tf_slice:ruin_landmark_noop", event["structureName"])
        self.assertEqual(0, self.service.debug_status()["landmarkTriggers"])

        self.service.tick(1, [])

        self.assertNotIn("-247,8", self.service._ledger)
        self.assertEqual([], self.factory.block.set_blocks)
        self.assertEqual([], self.factory.game.placements)

    def test_automatic_fallback_signals_never_schedule_runtime_worldgen(self):
        watchdog = {
            "structureName": "tf_slice:ruin_landmark_surface_watchdog",
            "x": -256,
            "y": 0,
            "z": 0,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }
        loaded = {
            "dimension": 33027004,
            "chunkPosX": -16,
            "chunkPosZ": 0,
            "blockEntities": [],
        }
        player = {
            "dimensionId": 33027004,
            "position": (-247.0, 65.0, 8.0),
        }

        self.service.on_structure_feature_event(watchdog)
        self.service.on_chunk_loaded_event(loaded)
        self.service.tick(SERVICE.SCAN_INTERVAL_TICKS, [player])

        self.assertFalse(watchdog["cancel"])
        self.assertEqual(
            "tf_slice:ruin_landmark_noop",
            watchdog["structureName"],
        )
        self.assertEqual(0, self.service.debug_status()["landmarkTriggers"])
        self.assertNotIn("-247,8", self.service._ledger)
        self.assertEqual([], self.factory.block.set_blocks)
        self.assertEqual([], self.factory.game.placements)

    def test_incomplete_surface_landmark_never_becomes_a_tick_repair_job(self):
        event = self._naga_surface_event(0, 0)
        self.service.on_structure_feature_event(event)
        self.service.tick(1, [])
        job = self.service._ledger["-247,8"]

        self.service.tick(
            job["surfaceLastSeenTick"] + SERVICE.SURFACE_TILE_SETTLE_TICKS,
            [
                {
                    "dimensionId": 33027004,
                    "position": (-247.0, 65.0, 8.0),
                }
            ],
        )

        self.assertEqual("surface_feature", job["generationSource"])
        self.assertEqual("surface_pending", job["state"])
        self.assertTrue(job["surfaceGenerated"])
        self.assertNotIn("terrain", job)
        self.assertEqual([], self.factory.block.set_blocks)
        self.assertEqual([], self.factory.game.placements)

    def test_surface_watchdog_ignores_non_center_chunks(self):
        event = {
            "structureName": "tf_slice:ruin_landmark_surface_watchdog",
            "x": -240,
            "y": 0,
            "z": 0,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }

        self.service.on_structure_feature_event(event)

        self.assertFalse(event["cancel"])
        self.assertEqual("tf_slice:ruin_landmark_noop", event["structureName"])
        self.assertEqual(
            0,
            self.service.debug_status()["landmarkTriggers"],
        )

    def test_native_surface_record_wins_over_a_queued_watchdog(self):
        watchdog = {
            "structureName": "tf_slice:ruin_landmark_surface_watchdog",
            "x": -256,
            "y": 0,
            "z": 0,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }
        native = {
            "structureName": SERVICE.SURFACE_LANDMARK_TRIGGER_BY_MODE[
                "ordinary"
            ],
            "x": -256,
            "y": 32,
            "z": 0,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }

        self.service.on_structure_feature_event(watchdog)
        self.service.on_structure_feature_event(native)
        self.service.tick(1, [])

        job = self.service._ledger["-247,8"]
        self.assertEqual("surface_feature", job["generationSource"])
        self.assertTrue(job["surfaceGenerated"])

    def test_chunk_generated_event_does_not_schedule_post_generation_work(self):
        event = {
            "dimension": 33027004,
            "chunkPosX": -16,
            "chunkPosZ": 0,
            "blockEntityData": None,
        }

        self.service.on_chunk_generated_event(event)

        self.assertEqual(
            0,
            self.service.debug_status()["landmarkTriggers"],
        )
        self.service.on_chunk_generated_event(dict(event))
        self.assertEqual(
            0,
            self.service.debug_status()["landmarkTriggers"],
        )
        self.service.on_chunk_generated_event(
            {
                "dimension": 33027004,
                "chunkPosX": -15,
                "chunkPosZ": 0,
            }
        )
        self.service.on_chunk_generated_event(
            {
                "dimension": 0,
                "chunkPosX": -16,
                "chunkPosZ": 0,
            }
        )
        self.assertEqual(
            0,
            self.service.debug_status()["landmarkTriggers"],
        )
        self.assertEqual(
            3,
            self.service.debug_status()["chunkGenerationEvents"],
        )

    def test_new_world_uses_real_engine_seed(self):
        self.factory.extra.data.pop(SERVICE.WORLD_SEED_KEY, None)

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )

        self.assertEqual(self.factory.game.seed, service._world_seed)
        self.assertEqual(
            self.factory.game.seed,
            self.factory.extra.data[SERVICE.WORLD_SEED_KEY],
        )

    def test_loaded_center_is_observed_without_backfill(self):
        event = {
            "dimension": 33027004,
            "chunkPosX": -16,
            "chunkPosZ": 0,
            "blockEntities": [],
        }

        self.service.on_chunk_loaded_event(event)
        self.service.on_chunk_loaded_event(dict(event))

        status = self.service.debug_status()
        self.assertEqual(0, status["landmarkTriggers"])
        self.assertEqual(0, status["chunkLoadBackfillEvents"])

        self.service.tick(1, [])

        self.assertNotIn("-247,8", self.service._ledger)
        self.assertEqual([], self.factory.block.set_blocks)
        self.assertEqual([], self.factory.game.placements)

    def test_generated_and_loaded_events_do_not_schedule_backfill(self):
        event = {
            "dimension": 33027004,
            "chunkPosX": -16,
            "chunkPosZ": 0,
        }

        self.service.on_chunk_loaded_event(event)
        self.service.on_chunk_generated_event(event)
        self.service.tick(1, [])

        self.assertNotIn("-247,8", self.service._ledger)
        status = self.service.debug_status()
        self.assertEqual(0, status["chunkLoadBackfillEvents"])
        self.assertEqual(1, status["chunkGenerationEvents"])

    def test_loaded_center_with_existing_ledger_does_not_queue(self):
        self.service._ledger["-247,8"] = {
            "state": "complete",
            "center": [-247, 8],
        }

        self.service.on_chunk_loaded_event(
            {
                "dimension": 33027004,
                "chunkPosX": -16,
                "chunkPosZ": 0,
                "blockEntities": [],
            }
        )

        status = self.service.debug_status()
        self.assertEqual(0, status["landmarkTriggers"])
        self.assertEqual(0, status["chunkLoadBackfillEvents"])

    def test_loaded_event_ignores_foreign_and_non_center_chunks(self):
        self.service.on_chunk_loaded_event(
            {
                "dimension": 0,
                "chunkPosX": -16,
                "chunkPosZ": 0,
            }
        )
        self.service.on_chunk_loaded_event(
            {
                "dimension": 33027004,
                "chunkPosX": -15,
                "chunkPosZ": 0,
            }
        )

        status = self.service.debug_status()
        self.assertEqual(0, status["landmarkTriggers"])
        self.assertEqual(0, status["chunkLoadBackfillEvents"])

    def test_loaded_chunks_do_not_probe_landmark_readiness(self):
        biome_results = [
            None,
            None,
            "dm33027004_plains",
        ]
        biome_calls = []

        def get_biome_name(position, dimension_id):
            biome_calls.append((position, dimension_id))
            return biome_results.pop(0)

        self.factory.biome.GetBiomeName = get_biome_name
        self.service.on_chunk_loaded_event(
            {
                "dimension": 33027004,
                "chunkPosX": -16,
                "chunkPosZ": 0,
            }
        )

        self.service.tick(1, [])
        self.service.tick(2, [])
        self.service.tick(3, [])

        self.assertEqual([], biome_calls)
        self.assertEqual(0, self.service.debug_status()["landmarkTriggers"])
        self.assertNotIn("-247,8", self.service._ledger)

    def test_loaded_center_never_queries_landmark_height(self):
        height_calls = []

        def get_top_block_height(position, dimension_id):
            height_calls.append((position, dimension_id))
            return 64

        self.factory.chunk.ready = False
        self.factory.block.GetTopBlockHeight = get_top_block_height
        self.service.on_chunk_loaded_event(
            {
                "dimension": 33027004,
                "chunkPosX": -16,
                "chunkPosZ": 0,
            }
        )

        self.service.tick(1, [])

        self.assertEqual([], height_calls)
        self.assertEqual(0, self.service.debug_status()["landmarkTriggers"])
        self.assertEqual({}, self.service._ledger)

        self.factory.chunk.ready = True
        self.service.tick(2, [])

        self.assertEqual([], height_calls)
        self.assertNotIn("-247,8", self.service._ledger)
        self.assertEqual(0, self.service.debug_status()["landmarkTriggers"])

    def test_loaded_center_never_creates_a_discovery_failure_record(self):
        self.factory.biome.GetBiomeName = lambda _position, _dimension: None
        self.service.on_chunk_loaded_event(
            {
                "dimension": 33027004,
                "chunkPosX": -16,
                "chunkPosZ": 0,
            }
        )

        for current_tick in range(1, 91):
            self.service.tick(current_tick, [])

        self.assertNotIn("-247,8", self.service._ledger)
        self.assertEqual(0, self.service.debug_status()["landmarkDiscoveryFailures"])

    def test_legacy_discovery_failure_is_not_retried_at_runtime(self):
        self.service._ledger["-247,8"] = {
            "state": "failed",
            "reason": "discovery_not_ready",
            "center": [-247, 8],
            "attempts": SERVICE.MAX_LANDMARK_DISCOVERY_RETRIES,
        }

        accepted = self.service._enqueue_landmark_chunk(
            -16,
            0,
            "player_proximity_backfill",
        )

        self.assertFalse(accepted)
        self.assertIn("-247,8", self.service._ledger)
        self.assertEqual(0, len(self.service._landmark_chunk_handoffs))

        self.service.tick(1, [])

        self.assertEqual(
            "discovery_not_ready",
            self.service._ledger["-247,8"]["reason"],
        )

    def test_locate_can_predict_through_a_transient_discovery_failure(self):
        self.service._ledger["-247,8"] = {
            "state": "failed",
            "reason": "discovery_not_ready",
            "center": [-247, 8],
            "attempts": SERVICE.MAX_LANDMARK_DISCOVERY_RETRIES,
        }

        succeeded, result = self.service.debug_locate(
            "naga_courtyard",
            (-247, 80, 8),
            256,
        )

        self.assertTrue(succeeded)
        self.assertEqual("naga_courtyard", result["id"])
        self.assertIn(result["source"], ("predicted", "grid_predicted"))

    def test_surface_trigger_creates_pending_naga_record_without_terrain_job(self):
        event = {
            "structureName": SERVICE.SURFACE_LANDMARK_TRIGGER_BY_MODE[
                "ordinary"
            ],
            "x": -256,
            "y": 32,
            "z": 0,
            "biomeName": "dm33027004_plains",
            "dimensionId": 33027004,
            "cancel": False,
        }
        self.service.on_structure_feature_event(event)

        self.service.tick(1, [])

        job = self.service._ledger["-247,8"]
        self.assertEqual("naga_courtyard", job["kind"])
        self.assertEqual("surface_feature", job["generationSource"])
        self.assertEqual("surface_pending", job["state"])
        self.assertTrue(job["surfaceGenerated"])
        self.assertEqual(["0,0"], job["surfaceTiles"])
        self.assertGreater(len(job["surfaceExpectedTiles"]), 1)
        self.assertFalse(job["bossSpawnerReady"])
        self.assertNotIn("terrain", job)
        self.assertEqual([], self.factory.game.placements)

    def test_physical_naga_marker_recovers_metadata_without_repair_job(self):
        self.factory.block.GetTopBlockHeight = (
            lambda _position, _dimension_id: 80
        )
        self.factory.block.blocks[(-248, 65, 8)] = {
            "name": "tf_slice:naga_boss_spawner",
            "aux": 0,
        }
        self.factory.block.blocks[(-248, 64, 8)] = {
            "name": "minecraft:moss_block",
            "aux": 0,
        }

        job = self.service.discover_for_generated_chunk(
            -16,
            0,
            "player_proximity_backfill",
        )

        self.assertEqual("naga_courtyard", job["kind"])
        self.assertEqual("physical_marker_recovery", job["generationSource"])
        self.assertEqual("complete", job["state"])
        self.assertEqual(64, job["anchor"][1])
        self.assertEqual([-248, 65, 8], job["physicalBossSpawnerMarker"])
        self.assertEqual([], job["pieces"])
        self.assertNotIn("terrain", job)
        self.assertFalse(job["surfaceGenerated"])
        self.assertTrue(job["bossSpawnerReady"])

    def test_spawner_tick_recovers_a_missing_ledger_and_spawns_immediately(self):
        spawned = []

        def spawn_boss(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            self.factory.entity_types["naga-from-marker"] = identifier
            return "naga-from-marker"

        self.service._boss_spawner = spawn_boss
        self.service._catalog["naga_courtyard"]["bossSpawner"][
            "activationRadius"
        ] = 50
        self.service._catalog["naga_courtyard"]["bossSpawner"][
            "offset"
        ][1] = 3
        marker = (-248, 65, 8)
        self.factory.block.blocks[marker] = {
            "name": "tf_slice:naga_boss_spawner",
            "aux": 0,
        }
        self.factory.block.blocks[(-248, 64, 8)] = {
            "name": "minecraft:moss_block",
            "aux": 0,
        }
        event = {
            "blockName": "tf_slice:naga_boss_spawner",
            "dimension": 33027004,
            "posX": marker[0],
            "posY": marker[1],
            "posZ": marker[2],
        }
        players = [
            {
                "dimensionId": 33027004,
                "position": (-247.5, 70.0, 8.5),
            }
        ]

        self.assertTrue(
            self.service.on_courtyard_spawner_tick(event, players, 1)
        )

        job = self.service._ledger["-247,8"]
        self.assertEqual("physical_marker_recovery", job["generationSource"])
        self.assertEqual("complete", job["state"])
        self.assertEqual([], job["pieces"])
        self.assertNotIn("terrain", job)
        self.assertEqual([marker[0], marker[1], marker[2]], job["physicalBossSpawnerMarker"])
        self.assertTrue(job["bossSpawned"])
        self.assertEqual(1, len(spawned))
        self.assertEqual("minecraft:air", self.factory.block.blocks[marker]["name"])

    def test_minoshroom_marker_spawns_below_it_without_player_progress(self):
        spawned = []

        def spawn_boss(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            self.factory.entity_types["minoshroom-from-marker"] = identifier
            return "minoshroom-from-marker"

        self.service._boss_spawner = spawn_boss
        entry = self.service._catalog["labyrinth"]
        variant = entry["variants"][0]
        spawner = SERVICE.ruin_logic.boss_spawner_for_variant(entry, variant)
        anchor = [0, 64, 0]
        marker = tuple(
            anchor[index] + int(spawner["offset"][index])
            for index in range(3)
        )
        self.factory.block.blocks[marker] = {
            "name": "tf_slice:minoshroom_boss_spawner",
            "aux": 0,
        }
        job = SERVICE.ruin_logic.create_landmark_job(
            "labyrinth",
            anchor,
            0,
            [],
            [0, 64, 0, 111, 117, 111],
        )
        job.update(
            {
                "state": "complete",
                "center": [55, 55],
                "bossSpawner": spawner,
                "bossKind": "minoshroom",
                "physicalBossSpawnerMarker": list(marker),
                "bossSpawnerReady": True,
                "bossSpawned": False,
                "bossDefeated": False,
            }
        )
        self.service._ledger = {"55,55": job}
        self.service._rebuild_runtime_job_indexes()
        event = {
            "blockName": "tf_slice:minoshroom_boss_spawner",
            "dimension": 33027004,
            "posX": marker[0],
            "posY": marker[1],
            "posZ": marker[2],
        }
        players = [
            {
                "playerId": "no-progress-player",
                "dimensionId": 33027004,
                "position": (marker[0] + 0.5, marker[1] + 0.5, marker[2] + 0.5),
                "progress": {},
            }
        ]

        self.assertTrue(
            self.service.on_courtyard_spawner_tick(event, players, 20)
        )
        self.assertEqual(
            [
                (
                    "tf_slice:minoshroom",
                    (marker[0] + 0.5, marker[1] - 1.0, marker[2] + 0.5),
                    180.0,
                    33027004,
                )
            ],
            spawned,
        )
        self.assertTrue(job["bossSpawned"])
        self.assertEqual(
            "minecraft:air", self.factory.block.blocks[marker]["name"]
        )

    def test_lich_spawner_tick_recovers_missing_ledger_after_restart(self):
        spawned = []

        def spawn_boss(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            self.factory.entity_types["lich-from-marker"] = identifier
            return "lich-from-marker"

        self.service._boss_spawner = spawn_boss
        marker = (40, 150, 60)
        self.factory.block.blocks[marker] = {
            "name": "tf_slice:lich_boss_spawner",
            "aux": 0,
        }
        event = {
            "blockName": "tf_slice:lich_boss_spawner",
            "dimension": 33027004,
            "posX": marker[0],
            "posY": marker[1],
            "posZ": marker[2],
        }
        players = [
            {
                "playerId": "eligible-player",
                "dimensionId": 33027004,
                "position": (40.5, 150.5, 60.5),
                "progress": {"tf_naga_defeated": 1},
            }
        ]

        self.assertTrue(
            self.service.on_courtyard_spawner_tick(event, players, 20)
        )

        recovered = [
            job
            for job in self.service._ledger.values()
            if job.get("kind") == "lich_tower"
        ]
        self.assertEqual(1, len(recovered))
        self.assertEqual(
            [40, 150, 60], recovered[0]["physicalBossSpawnerMarker"]
        )
        self.assertTrue(recovered[0]["bossSpawned"])
        self.assertEqual(
            [("tf_slice:lich", (40.5, 151.0, 60.5), 180.0, 33027004)],
            spawned,
        )
        self.assertEqual(
            "minecraft:air", self.factory.block.blocks[marker]["name"]
        )

    def test_lich_spawns_above_its_solid_marker_during_actor_confirmation(self):
        spawned = []
        marker = (42, 150, 62)

        def spawn_boss(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            # NetEase keeps the marker solid until the actor has been
            # confirmed. An actor created inside that block disappears before
            # the two-tick confirmation can complete.
            if float(position[1]) < marker[1] + 1.0:
                return None
            self.factory.entity_types["lich-above-marker"] = identifier
            return "lich-above-marker"

        self.service._boss_spawner = spawn_boss
        self.factory.block.blocks[marker] = {
            "name": "tf_slice:lich_boss_spawner",
            "aux": 0,
        }
        event = {
            "blockName": "tf_slice:lich_boss_spawner",
            "dimension": 33027004,
            "posX": marker[0],
            "posY": marker[1],
            "posZ": marker[2],
        }
        players = [
            {
                "playerId": "eligible-player",
                "dimensionId": 33027004,
                "position": (42.5, 150.5, 62.5),
                "progress": {"tf_naga_defeated": 1},
            }
        ]

        self.assertTrue(
            self.service.on_courtyard_spawner_tick(event, players, 20)
        )

        recovered = next(
            job
            for job in self.service._ledger.values()
            if job.get("kind") == "lich_tower"
        )
        self.assertTrue(recovered["bossSpawned"])
        self.assertEqual(
            [
                (
                    "tf_slice:lich",
                    (42.5, 151.0, 62.5),
                    180.0,
                    33027004,
                )
            ],
            spawned,
        )
        self.assertEqual(
            "minecraft:air", self.factory.block.blocks[marker]["name"]
        )

    def test_lich_spawn_waits_for_a_confirmed_actor_before_committing(self):
        confirmations = []

        def spawn_boss(identifier, position, yaw, dimension_id):
            self.factory.entity_types["lich-pending"] = identifier
            return "lich-pending"

        def confirm_boss(entity_id, expected_identifier):
            confirmations.append((entity_id, expected_identifier))
            if len(confirmations) < 2:
                return None
            return expected_identifier

        self.service._boss_spawner = spawn_boss
        self.service._boss_confirmer = confirm_boss
        marker = (48, 150, 68)
        self.factory.block.blocks[marker] = {
            "name": "tf_slice:lich_boss_spawner",
            "aux": 0,
        }
        event = {
            "blockName": "tf_slice:lich_boss_spawner",
            "dimension": 33027004,
            "posX": marker[0],
            "posY": marker[1],
            "posZ": marker[2],
        }
        players = [
            {
                "playerId": "eligible-player",
                "dimensionId": 33027004,
                "position": (48.5, 150.5, 68.5),
                "progress": {"tf_naga_defeated": 1},
            }
        ]

        self.assertTrue(
            self.service.on_courtyard_spawner_tick(event, players, 20)
        )
        recovered = next(
            job
            for job in self.service._ledger.values()
            if job.get("kind") == "lich_tower"
        )
        self.assertFalse(recovered["bossSpawned"])
        self.assertEqual("lich-pending", recovered["bossSpawnPendingId"])
        self.assertEqual(
            "tf_slice:lich_boss_spawner",
            self.factory.block.blocks[marker]["name"],
        )

        self.service.tick(21, players)

        self.assertTrue(recovered["bossSpawned"])
        self.assertEqual("lich-pending", recovered["bossEntityId"])
        self.assertNotIn("bossSpawnPendingId", recovered)
        self.assertEqual(2, len(confirmations))
        self.assertEqual(
            "minecraft:air", self.factory.block.blocks[marker]["name"]
        )

    def test_recovered_lich_spawner_naturally_spawns_without_naga_progress(self):
        spawned = []

        def spawn_boss(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            self.factory.entity_types["natural-lich"] = identifier
            return "natural-lich"

        self.service._boss_spawner = spawn_boss
        marker = (44, 151, 64)
        self.factory.block.blocks[marker] = {
            "name": "tf_slice:lich_boss_spawner",
            "aux": 0,
        }
        event = {
            "blockName": "tf_slice:lich_boss_spawner",
            "dimension": 33027004,
            "posX": marker[0],
            "posY": marker[1],
            "posZ": marker[2],
        }
        players = [
            {
                "playerId": "blocked-player",
                "dimensionId": 33027004,
                "position": (44.5, 151.5, 64.5),
                "progress": {},
            }
        ]

        self.assertTrue(
            self.service.on_courtyard_spawner_tick(event, players, 20)
        )

        recovered = next(
            job
            for job in self.service._ledger.values()
            if job.get("kind") == "lich_tower"
        )
        self.assertTrue(recovered["bossSpawned"])
        self.assertEqual(
            [("tf_slice:lich", (44.5, 152.0, 64.5), 180.0, 33027004)],
            spawned,
        )
        self.assertEqual(
            "minecraft:air",
            self.factory.block.blocks[marker]["name"],
        )

    def test_stale_false_defeat_with_physical_lich_marker_is_rearmed(self):
        spawned = []
        marker = (24, 100, 46)

        def spawn_boss(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            self.factory.entity_types["rearmed-lich"] = identifier
            return "rearmed-lich"

        self.service._boss_spawner = spawn_boss
        self.factory.block.blocks[marker] = {
            "name": "tf_slice:lich_boss_spawner",
            "aux": 0,
        }
        job = {
            "kind": "lich_tower",
            "entryId": "lich_tower",
            "state": "complete",
            "anchor": [20, 90, 40],
            "bounds": [20, 90, 40, 60, 150, 80],
            "bossKind": "lich",
            "bossSpawner": {
                "kind": "lich",
                "entity": "tf_slice:lich",
                "offset": [4, 10, 6],
                "activationRadius": 9,
                "minPlayerYOffset": -4,
                "spawnYOffset": 0.5,
                "progressObjective": "tf_naga_defeated",
            },
            "physicalBossSpawnerMarker": list(marker),
            "bossSpawnerReady": True,
            "bossSpawned": True,
            "bossDefeated": True,
            "rewardClaimed": False,
        }
        self.service._ledger = {"40,60": job}
        self.service._rebuild_runtime_job_indexes()

        handled = self.service.on_courtyard_spawner_tick(
            {
                "blockName": "tf_slice:lich_boss_spawner",
                "dimension": 33027004,
                "posX": marker[0],
                "posY": marker[1],
                "posZ": marker[2],
            },
            [
                {
                    "playerId": "eligible-player",
                    "dimensionId": 33027004,
                    "position": (24.5, 100.5, 46.5),
                    "progress": {"tf_naga_defeated": 1},
                }
            ],
            20,
        )

        self.assertTrue(handled)
        self.assertFalse(job["bossDefeated"])
        self.assertTrue(job["bossSpawned"])
        self.assertEqual(
            [("tf_slice:lich", (24.5, 101.0, 46.5), 180.0, 33027004)],
            spawned,
        )
        self.assertEqual("minecraft:air", self.factory.block.blocks[marker]["name"])

    def test_replayed_marker_is_consumed_after_boss_was_already_committed(self):
        marker = (-248, 67, 8)
        self.factory.block.blocks[marker] = {
            "name": "tf_slice:naga_boss_spawner",
            "aux": 0,
        }
        job = SERVICE.ruin_logic.create_landmark_job(
            "naga_courtyard",
            (-300, 64, -44),
            0,
            [],
            [-300, 62, -44, -197, 73, 59],
        )
        job.update(
            {
                "center": [-247, 8],
                "state": "complete",
                "bossSpawner": {
                    "entity": "tf_slice:forest_wyrm",
                    "offset": [52, 3, 52],
                    "activationRadius": 50,
                },
                "bossSpawnerReady": True,
                "bossSpawned": True,
                "bossDefeated": False,
            }
        )
        self.service._ledger = {"-247,8": job}
        self.service._rebuild_runtime_job_indexes()

        handled = self.service.on_courtyard_spawner_tick(
            {
                "blockName": "tf_slice:naga_boss_spawner",
                "dimension": 33027004,
                "posX": marker[0],
                "posY": marker[1],
                "posZ": marker[2],
            },
            [],
            20,
        )

        self.assertTrue(handled)
        self.assertEqual(
            "minecraft:air",
            self.factory.block.blocks[marker]["name"],
        )

    def test_spawner_tick_rejects_wrong_dimension_and_respects_fifty_blocks(self):
        spawned = []
        self.service._boss_spawner = lambda *args: spawned.append(args)
        event = {
            "blockName": "tf_slice:naga_boss_spawner",
            "dimension": 0,
            "posX": -248,
            "posY": 65,
            "posZ": 8,
        }
        players = [
            {
                "dimensionId": 33027004,
                "position": (-196.9, 70.0, 8.5),
            }
        ]

        self.assertFalse(
            self.service.on_courtyard_spawner_tick(event, players, 1)
        )
        self.assertEqual({}, self.service._ledger)
        self.assertEqual([], spawned)

        event["dimension"] = 33027004
        self.factory.block.blocks[(-248, 65, 8)] = {
            "name": "tf_slice:naga_boss_spawner",
            "aux": 0,
        }
        self.factory.block.blocks[(-248, 64, 8)] = {
            "name": "minecraft:moss_block",
            "aux": 0,
        }
        self.assertTrue(
            self.service.on_courtyard_spawner_tick(event, players, 2)
        )
        self.assertIn("-247,8", self.service._ledger)
        self.assertFalse(self.service._ledger["-247,8"]["bossSpawned"])
        self.assertEqual([], spawned)

    def test_ledger_persist_reports_both_write_stages(self):
        self.factory.extra.set_result = False
        self.assertFalse(self.service._persist())
        self.assertEqual(1, self.service._ledger_persist_failures)
        self.assertEqual("set_extra_data", self.service._last_ledger_persist_error)

        self.factory.extra.set_result = True
        self.factory.extra.save_result = False
        self.assertFalse(self.service._persist())
        self.assertEqual(2, self.service._ledger_persist_failures)
        self.assertEqual("save_extra_data", self.service._last_ledger_persist_error)

    def test_large_ledger_is_sharded_and_round_trips_without_loss(self):
        expected = {}
        random_source = random.Random(123456789)
        for index in range(400):
            expected["record-%03d" % index] = {
                "kind": "druid_hut",
                "state": "complete",
                "payload": "".join(
                    chr(random_source.randrange(32, 127))
                    for _offset in range(512)
                ),
            }
        self.service._ledger = expected

        self.assertTrue(self.service._persist())

        manifest_raw = self.factory.extra.data[SERVICE.LEDGER_KEY]
        self.assertIsInstance(manifest_raw, str)
        manifest = SERVICE.json.loads(manifest_raw)
        self.assertEqual(
            SERVICE.LEDGER_STORAGE_FORMAT,
            manifest["format"],
        )
        self.assertGreater(manifest["shards"], 1)
        generation = int(manifest["generation"])
        for index in range(int(manifest["shards"])):
            shard = self.factory.extra.data[
                SERVICE._ledger_shard_key(generation, index)
            ]
            self.assertIsInstance(shard, str)
            self.assertLessEqual(
                len(shard),
                SERVICE.LEDGER_SHARD_MAX_WEIGHT,
            )

        restarted = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )
        self.assertEqual(expected, restarted._ledger)

    def test_ledger_persist_uses_level_compatible_scalar_payloads(self):
        expected = {
            "8,232": {
                "kind": "lich_tower",
                "state": "surface_pending",
                "surfaceTiles": ["-3,-3"],
                "bossSpawnerReady": False,
            }
        }
        self.service._ledger = expected
        self.factory.extra.reject_structured_values = True

        self.assertTrue(self.service._persist())

        manifest_raw = self.factory.extra.data[SERVICE.LEDGER_KEY]
        self.assertIsInstance(manifest_raw, str)
        manifest = SERVICE.json.loads(manifest_raw)
        generation = int(manifest["generation"])
        for index in range(int(manifest["shards"])):
            shard = self.factory.extra.data[
                SERVICE._ledger_shard_key(generation, index)
            ]
            self.assertIsInstance(shard, str)

        restarted = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )
        restored = restarted._ledger["8,232"]
        self.assertEqual("lich_tower", restored["kind"])
        self.assertEqual("surface_pending", restored["state"])
        self.assertEqual(["-3,-3"], restored["surfaceTiles"])
        self.assertFalse(restored["bossSpawnerReady"])

    def test_load_accepts_legacy_sharded_dictionary_ledger(self):
        expected = {
            "legacy-record": {
                "kind": "druid_hut",
                "state": "complete",
            }
        }
        generation = 1
        self.factory.extra.data[SERVICE.LEDGER_KEY] = {
            "format": SERVICE.LEGACY_LEDGER_STORAGE_FORMAT,
            "generation": generation,
            "shards": 1,
            "records": 1,
        }
        self.factory.extra.data[
            SERVICE._ledger_shard_key(generation, 0)
        ] = expected

        restarted = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )

        self.assertEqual(expected, restarted._ledger)

    def test_load_migrates_hydra_trigger_without_moving_old_world_marker(self):
        old_marker_offset = [40, 3, 40]
        self.factory.extra.data[SERVICE.LEDGER_KEY] = {
            "40,40": {
                "entryId": "hydra_lair",
                "kind": "hydra_lair",
                "state": "complete",
                "center": [40, 40],
                "anchor": [0, 64, 0],
                "bounds": [0, 64, 0, 79, 106, 79],
                "variant": 0,
                "bossSpawner": {
                    "kind": "hydra",
                    "entity": "tf_slice:hydra",
                    "offset": list(old_marker_offset),
                    "markerBlock": "tf_slice:hydra_boss_spawner",
                    "spawnYOffset": 1.0,
                    "activationRadius": 42,
                    "progressAll": [
                        "lich_defeated",
                        "meef_stroganoff_eaten",
                    ],
                },
                "physicalBossSpawnerMarker": [40, 67, 40],
                "bossSpawnerReady": True,
                "bossSpawned": False,
                "bossDefeated": False,
            }
        }

        restarted = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )
        spawner = restarted._ledger["40,40"]["bossSpawner"]

        self.assertEqual(old_marker_offset, spawner["offset"])
        self.assertEqual(50, spawner["activationRadius"])
        self.assertNotIn("progressAll", spawner)

    def test_load_keeps_legacy_single_tile_surface_courtyard_pending(self):
        self.factory.extra.data[SERVICE.LEDGER_KEY] = {
            "-247,8": {
                "entryId": "naga_courtyard",
                "kind": "naga_courtyard",
                "state": "complete",
                "center": [-247, 8],
                "anchor": [-300, 64, -44],
                "bounds": [-300, 64, -44, -197, 75, 59],
                "variant": 0,
                "surfaceGenerated": True,
                "surfaceTile": [0, 0],
                "generationSource": "surface_feature",
                "pieces": [],
                "nextPiece": 0,
                "bossSpawner": {
                    "entity": "tf_slice:forest_wyrm",
                    "offset": [52, 1, 52],
                    "activationRadius": 32,
                },
                "bossSpawned": False,
                "bossDefeated": False,
                "bossSpawnerReady": True,
                "courtyardLayoutPolicyVersion": (
                    SERVICE.COURTYARD_LAYOUT_POLICY_VERSION
                ),
            }
        }

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )
        job = service._ledger["-247,8"]

        self.assertEqual("surface_feature", job["generationSource"])
        self.assertEqual("surface_pending", job["state"])
        self.assertEqual([], job["pieces"])
        self.assertTrue(job["surfaceGenerated"])
        self.assertNotIn("terrain", job)
        self.assertFalse(job["bossSpawnerReady"])
        self.assertEqual(50, job["bossSpawner"]["activationRadius"])
        self.assertEqual(
            SERVICE.COURTYARD_SURFACE_POLICY_VERSION,
            job["courtyardSurfacePolicyVersion"],
        )

    def test_pending_surface_record_stays_read_only_after_server_restart(self):
        event = self._naga_surface_event(0, 0)
        self.service.on_structure_feature_event(event)
        self.service.tick(1, [])
        self.service._ledger["-247,8"]["surfaceLastSeenTick"] = 9000
        self.assertTrue(self.service._persist())

        restarted = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
        )
        restarted.tick(
            SERVICE.SURFACE_TILE_SETTLE_TICKS,
            [
                {
                    "dimensionId": 33027004,
                    "position": (-196.0, 65.0, 8.0),
                }
            ],
        )

        job = restarted._ledger["-247,8"]
        self.assertEqual("surface_feature", job["generationSource"])
        self.assertEqual("surface_pending", job["state"])
        self.assertNotIn("terrain", job)
        self.assertEqual([], self.factory.block.set_blocks)
        self.assertEqual([], self.factory.game.placements)

    def test_new_chunk_hollow_hill_uses_profiled_dome_terrain(self):
        job = self.service.discover_for_generated_chunk(2, 34)

        self.assertEqual("medium_hill", job["kind"])
        self.assertEqual("new_chunk", job["generationSource"])
        self.assertEqual("hill_base", job["terrain"]["mode"])
        self.assertEqual(68, job["terrain"]["diameter"])
        shell_pieces = [
            piece
            for piece in job["pieces"]
            if piece.get("layer") == "shell"
        ]
        interior_pieces = [
            piece
            for piece in job["pieces"]
            if piece.get("layer") == "interior"
        ]
        self.assertTrue(shell_pieces)
        self.assertTrue(interior_pieces)
        self.assertTrue(
            all(not piece["removeBlock"] for piece in shell_pieces)
        )
        self.assertTrue(
            all(not piece["removeBlock"] for piece in interior_pieces)
        )

    def test_landmark_ground_scan_ignores_tree_canopy_and_trunk(self):
        self.factory.block.GetTopBlockHeight = (
            lambda _position, _dimension_id: 90
        )
        self.factory.block.blocks[(5, 90, 7)] = {
            "name": "tf_slice:canopy_leaves",
            "aux": 0,
        }
        self.factory.block.blocks[(5, 89, 7)] = {
            "name": "tf_slice:canopy_log",
            "aux": 0,
        }
        self.factory.block.blocks[(5, 64, 7)] = {
            "name": "minecraft:grass_block",
            "aux": 0,
        }

        self.assertEqual(64, self.service._terrain_surface_y(5, 7))

    def test_hollow_hill_columns_follow_cosine_dome_not_flat_plateau(self):
        self.factory.block.GetTopBlockHeight = (
            lambda _position, _dimension_id: 90
        )
        terrain = {
            "mode": "hill_base",
            "width": 112,
            "depth": 112,
            "flatRadius": 48.0,
            "blendWidth": 8.0,
            "diameter": 100,
            "terrainDiameter": 112,
        }
        job = {"anchor": [100, 60, 200]}
        local_columns = ((55, 55), (30, 55), (1, 55))
        target_heights = []
        grass_counts = []

        for local_x, local_z in local_columns:
            world_x = job["anchor"][0] + local_x
            world_z = job["anchor"][2] + local_z
            self.factory.block.blocks[(world_x, 90, world_z)] = {
                "name": "tf_slice:canopy_leaves",
                "aux": 0,
            }
            self.factory.block.blocks[(world_x, 89, world_z)] = {
                "name": "tf_slice:canopy_log",
                "aux": 0,
            }
            self.factory.block.blocks[(world_x, 64, world_z)] = {
                "name": "minecraft:grass_block",
                "aux": 0,
            }
            column_index = local_z * terrain["width"] + local_x
            prepared = self.service._prepare_terrain_column(
                job,
                terrain,
                column_index,
            )
            grass_heights = [
                y
                for y, block_name in prepared["changes"]
                if block_name == "minecraft:grass_block"
            ]
            grass_counts.append(len(grass_heights))
            target_heights.append(
                grass_heights[0] if grass_heights else 64
            )

        self.assertEqual([1, 1, 0], grass_counts)
        self.assertGreater(target_heights[0], target_heights[1])
        self.assertGreater(target_heights[1], target_heights[2])
        # The raw +37 cosine profile is compressed by raiseHills after the
        # structure is anchored four blocks below ordinary ground.
        self.assertEqual(92, target_heights[0])
        edge_column = self.service._prepare_terrain_column(
            job,
            terrain,
            local_columns[-1][1] * terrain["width"]
            + local_columns[-1][0],
        )
        self.assertIn([90, "minecraft:air"], edge_column["changes"])
        self.assertIn([89, "minecraft:air"], edge_column["changes"])
        self.assertFalse(
            any(y <= 64 for y, _block_name in edge_column["changes"])
        )

    def test_landmark_variant_index_is_not_used_as_tile_rotation(self):
        job = {"anchor": [10, 60, 20], "variant": 2}
        piece = {
            "structure": "tf_slice/ruins/hollow_hill/large/x000_z016",
            "offset": [0, -6, 16],
        }

        self.assertTrue(self.service._place_piece(job, piece))

        placement = self.factory.game.placements[-1]
        self.assertEqual((10, 54, 36), placement[1])
        self.assertEqual(0, placement[4])
        self.assertFalse(placement[8])

    def test_hollow_hill_variant_uses_the_layout_random_stream(self):
        variants = [
            {"id": "small_v00", "landmarkKind": "small_hill"},
            {"id": "medium_v00", "landmarkKind": "medium_hill"},
            {"id": "small_v01", "landmarkKind": "small_hill"},
            {"id": "small_v02", "landmarkKind": "small_hill"},
        ]
        entry = {"variants": variants}
        candidate_indexes = [0, 2, 3]
        expected_local = SERVICE.ruin_logic.landmark_stream_index(
            self.service._world_seed,
            264,
            -247,
            "small_hill",
            "layout",
            len(candidate_indexes),
        )

        index, variant = self.service._entry_variant(
            entry,
            "small_hill",
            264,
            -247,
        )

        self.assertEqual(candidate_indexes[expected_local], index)
        self.assertIs(variants[index], variant)

    def test_hollow_hill_shell_does_not_clear_the_terrain_roof(self):
        job = {"anchor": [10, 60, 20], "variant": 2}
        shell_piece = {
            "structure": "tf_slice/ruins/hollow_hill/large/x000_z016",
            "offset": [0, -6, 16],
            "layer": "shell",
            "removeBlock": False,
        }

        self.assertTrue(self.service._place_piece(job, shell_piece))

        placement = self.factory.game.placements[-1]
        self.assertFalse(placement[8])

    def test_debug_hollow_hill_keeps_carving_and_controlled_spawn_identity(self):
        accepted, message = self.service.debug_place(
            "hollow_hill",
            (10, 64, 20),
        )

        self.assertTrue(accepted, message)
        self.assertEqual([], self.service._manual_jobs)
        job = self.service._ledger["manual:10,20"]
        self.assertEqual("small_hill", job["kind"])
        shell_pieces = [
            piece
            for piece in job["pieces"]
            if piece.get("layer") == "shell"
        ]
        interior_pieces = [
            piece
            for piece in job["pieces"]
            if piece.get("layer") == "interior"
        ]
        self.assertTrue(shell_pieces)
        self.assertTrue(interior_pieces)
        self.assertTrue(
            all(not piece["removeBlock"] for piece in shell_pieces)
        )
        self.assertTrue(
            all(not piece["removeBlock"] for piece in interior_pieces)
        )
        self.assertGreater(self.factory.extra.save_count, 0)

    def test_debug_lich_tower_is_indexed_for_boss_activation_immediately(self):
        accepted, message = self.service.debug_place(
            "lich_tower",
            (10, 64, 20),
        )

        self.assertTrue(accepted, message)
        manual_key = "manual:10,20"
        self.assertIn(manual_key, self.service._ledger)
        self.assertEqual(
            "lich_tower",
            self.service._ledger[manual_key]["kind"],
        )
        self.assertIn(manual_key, self.service._boss_job_keys)

    def test_completed_hollow_hill_spawns_one_source_weighted_group(self):
        spawned = []

        def spawn_entity(identifier, position, yaw, dimension_id):
            entity_id = "spawned-%d" % len(spawned)
            spawned.append(
                (identifier, position, yaw, dimension_id)
            )
            return entity_id

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
            spawn_entity,
        )
        job = SERVICE.ruin_logic.create_landmark_job(
            "small_hill",
            (0, 64, 0),
            0,
            [],
            [0, 60, 0, 47, 80, 47],
        )
        job["state"] = "complete"
        service._ledger = {"0,0": job}
        service._rebuild_runtime_job_indexes()
        service._is_hollow_hill_spawn_position_clear = (
            lambda _position: True
        )
        cavity = SERVICE.ruin_logic.hollow_hill_cavity_range(
            job,
            25.5,
            7.5,
        )
        player = {
            "playerId": "player",
            "dimensionId": 33027004,
            "position": (25.5, cavity[0], 7.5),
        }

        service.tick(SERVICE.HOLLOW_HILL_SPAWN_INTERVAL_TICKS, [player])

        self.assertGreaterEqual(len(spawned), 4)
        self.assertLessEqual(len(spawned), 8)
        self.assertTrue(
            all(
                call[0]
                in SERVICE.ruin_logic.HOLLOW_HILL_CONTROLLED_MOBS
                for call in spawned
            )
        )
        self.assertTrue(all(call[3] == 33027004 for call in spawned))
        self.assertEqual(1, service.debug_status()["hollowHillSpawnGroups"])
        self.assertEqual(
            len(spawned),
            service.debug_status()["hollowHillSpawnEntities"],
        )

    def test_hollow_hill_controlled_spawns_obey_interval_cap_and_location(self):
        spawned = []

        def spawn_entity(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            return "spawned-%d" % len(spawned)

        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
            spawn_entity,
        )
        job = SERVICE.ruin_logic.create_landmark_job(
            "small_hill",
            (0, 64, 0),
            0,
            [],
            [0, 60, 0, 47, 80, 47],
        )
        job["state"] = "complete"
        service._ledger = {"0,0": job}
        service._rebuild_runtime_job_indexes()
        service._is_hollow_hill_spawn_position_clear = (
            lambda _position: True
        )
        cavity = SERVICE.ruin_logic.hollow_hill_cavity_range(
            job,
            23.5,
            23.5,
        )
        player = {
            "playerId": "player",
            "dimensionId": 33027004,
            "position": (23.5, cavity[0], 23.5),
        }

        service.tick(1, [player])
        self.assertEqual([], spawned)

        self.factory.game.entities = [
            "mob-%d" % index
            for index in range(
                SERVICE.ruin_logic.HOLLOW_HILL_LOCAL_MONSTER_CAPS[
                    "small_hill"
                ]
            )
        ]
        self.factory.entity_types.update(
            (entity_id, "minecraft:zombie")
            for entity_id in self.factory.game.entities
        )
        service.tick(SERVICE.HOLLOW_HILL_SPAWN_INTERVAL_TICKS, [player])
        self.assertEqual([], spawned)

        self.factory.game.entities = []
        player["position"] = (0.5, cavity[0], 0.5)
        service.tick(
            SERVICE.HOLLOW_HILL_SPAWN_INTERVAL_TICKS * 2,
            [player],
        )
        self.assertEqual([], spawned)

    def test_hollow_hill_scan_budget_counts_full_active_hills(self):
        service = SERVICE.StructureWorldgenService(
            self.factory,
            "level",
            33027004,
            lambda *_args: "unused",
        )
        players = []
        for index, anchor_x in enumerate((0, 100, 200)):
            job = SERVICE.ruin_logic.create_landmark_job(
                "small_hill",
                (anchor_x, 64, 0),
                0,
                [],
                [anchor_x, 60, 0, anchor_x + 47, 80, 47],
            )
            job["state"] = "complete"
            service._ledger["%d,0" % index] = job
            cavity = SERVICE.ruin_logic.hollow_hill_cavity_range(
                job,
                anchor_x + 23.5,
                23.5,
            )
            players.append(
                {
                    "playerId": "player-%d" % index,
                    "dimensionId": 33027004,
                    "position": (
                        anchor_x + 23.5,
                        cavity[0],
                        23.5,
                    ),
                }
            )
        service._rebuild_runtime_job_indexes()

        scanned = []
        service._spawn_hollow_hill_group = (
            lambda ledger_key, _job, _player, _tick, _players: (
                scanned.append(ledger_key) or 0
            )
        )

        service._spawn_hollow_hill_monsters(
            SERVICE.HOLLOW_HILL_SPAWN_INTERVAL_TICKS,
            players,
        )

        self.assertEqual(["0,0", "1,0"], scanned)

    def test_hollow_hill_controlled_spawn_requires_ground_and_two_air_blocks(self):
        position = (10.5, 65.0, 20.5)
        self.factory.block.blocks[(10, 64, 20)] = {
            "name": "minecraft:stone",
            "aux": 0,
        }

        self.assertTrue(
            self.service._is_hollow_hill_spawn_position_clear(position)
        )

        self.factory.block.blocks[(10, 66, 20)] = {
            "name": "minecraft:stone",
            "aux": 0,
        }
        self.assertFalse(
            self.service._is_hollow_hill_spawn_position_clear(position)
        )

    def test_terrain_edits_are_bounded_and_finish_before_structure_pieces(self):
        self.factory.block.GetTopBlockHeight = (
            lambda _position, _dimension_id: 200
        )
        self.service._ledger = {
            "manual:terrain": {
                "kind": "naga_courtyard",
                "entryId": "naga_courtyard",
                "anchor": [0, 64, 0],
                "variant": 0,
                "bounds": [0, 64, 0, 0, 200, 0],
                "pieces": [
                    {
                        "structure": (
                            "tf_slice/ruins/naga_courtyard/v00/x000_z000"
                        ),
                        "offset": [0, 0, 0],
                    }
                ],
                "nextPiece": 0,
                "retries": 0,
                "state": "planned",
                "terrain": {
                    "mode": "flatten",
                    "width": 1,
                    "depth": 1,
                    "flatRadius": 0.0,
                    "blendWidth": 0.0,
                    "nextColumn": 0,
                    "complete": False,
                },
            }
        }

        self.service.tick(
            1,
            [
                {
                    "dimensionId": 33027004,
                    "position": (0.0, 70.0, 0.0),
                }
            ],
        )

        self.assertEqual(
            SERVICE.MAX_TERRAIN_BLOCKS_PER_TICK,
            len(self.factory.block.set_blocks),
        )
        self.assertEqual([], self.factory.chunk.added)
        self.assertEqual([], self.factory.game.placements)
        self.assertEqual(
            0,
            self.service._ledger["manual:terrain"]["nextPiece"],
        )

    def test_nearby_player_does_not_backfill_missing_engine_events(self):
        self.service.tick(
            SERVICE.SCAN_INTERVAL_TICKS,
            [
                {
                    "dimensionId": 33027004,
                    "position": (-247.0, 64.0, -247.0),
                }
            ],
        )

        self.assertNotIn("-247,-247", self.service._ledger)
        self.assertEqual(0, self.service.debug_status()["playerProximityBackfillEvents"])
        self.assertEqual([], self.factory.block.set_blocks)
        self.assertEqual([], self.factory.game.placements)

    def test_landmark_backfill_supersedes_overlapping_native_ruin(self):
        naga_center = None
        for chunk_x in range(-64, 65):
            for chunk_z in range(-64, 65):
                if not SERVICE.ruin_logic.is_landmark_center_chunk(
                    chunk_x,
                    chunk_z,
                ):
                    continue
                center = SERVICE.ruin_logic.nearest_landmark_center(
                    chunk_x,
                    chunk_z,
                )
                if SERVICE.ruin_logic.resolve_variety_landmark(
                    chunk_x,
                    chunk_z,
                    self.service._world_seed,
                    SERVICE.SUPPORTED_VARIETY,
                ) == "naga_courtyard":
                    naga_center = center
                    break
            if naga_center is not None:
                break

        center_x, center_z = naga_center
        self.service._ledger["native:test"] = {
            "state": "complete",
            "kind": "monolith",
            "entryId": "monolith",
            "anchor": [center_x, 64, center_z],
            "bounds": [
                center_x - 2,
                64,
                center_z - 2,
                center_x + 2,
                72,
                center_z + 2,
            ],
        }

        job = self.service.discover_for_generated_chunk(
            center_x >> 4,
            center_z >> 4,
            "player_proximity_backfill",
        )

        self.assertEqual("naga_courtyard", job["kind"])
        self.assertEqual("planned", job["state"])

    def test_landmark_backfill_still_rejects_another_major_landmark(self):
        center_x, center_z = (-247, -247)
        self.service._ledger["major:test"] = {
            "state": "complete",
            "kind": "large_hill",
            "entryId": "hollow_hill",
            "anchor": [center_x, 64, center_z],
            "bounds": [
                center_x - 64,
                48,
                center_z - 64,
                center_x + 64,
                96,
                center_z + 64,
            ],
        }

        job = self.service.discover_for_generated_chunk(
            center_x >> 4,
            center_z >> 4,
            "player_proximity_backfill",
        )

        self.assertEqual("skipped", job["state"])
        self.assertEqual("landmark_overlap", job["reason"])
        self.assertEqual(
            SERVICE.LANDMARK_OVERLAP_POLICY_VERSION,
            job["overlapPolicyVersion"],
        )

    def test_scheduler_ignores_all_automatic_landmark_backlog(self):
        self.service._ledger = {
            "native:a": {
                "state": "planned",
                "kind": "druid_hut",
                "entryId": "druid_hut",
                "anchor": [0, 64, 0],
            },
            "-247,-247": {
                "state": "planned",
                "kind": "large_hill",
                "entryId": "hollow_hill",
                "center": [-247, -247],
                "anchor": [-300, 64, -300],
                "pieces": [
                    {
                        "structure": "tf_slice/ruins/hollow_hill/test",
                        "offset": [0, 0, 0],
                    }
                ],
            },
            "24,808": {
                "state": "planned",
                "kind": "naga_courtyard",
                "entryId": "naga_courtyard",
                "center": [24, 808],
                "anchor": [-32, 69, 752],
                "pieces": [
                    {
                        "structure": "tf_slice/ruins/naga_courtyard/test",
                        "offset": [0, 0, 0],
                    }
                ],
            },
            "776,-759": {
                "state": "planned",
                "kind": "naga_courtyard",
                "entryId": "naga_courtyard",
                "center": [776, -759],
                "anchor": [720, 64, -815],
                "pieces": [
                    {
                        "structure": "tf_slice/ruins/naga_courtyard/test",
                        "offset": [0, 0, 0],
                    }
                ],
            },
        }

        key, job, persistent = self.service._next_persistent_job(
            [
                {
                    "dimensionId": 33027004,
                    "position": (24.0, 90.0, 808.0),
                }
            ]
        )

        self.assertIsNone(key)
        self.assertIsNone(job)
        self.assertFalse(persistent)

    def test_scheduler_ignores_non_manual_landmarks_and_native_ruins(self):
        self.service._ledger = {
            "native:a": {
                "state": "planned",
                "kind": "druid_hut",
                "entryId": "druid_hut",
                "anchor": [0, 64, 0],
            },
            "264,264": {
                "state": "planned",
                "kind": "hedge_maze",
                "entryId": "hedge_maze",
                "center": [264, 264],
                "anchor": [232, 64, 232],
                "pieces": [
                    {
                        "structure": "tf_slice/ruins/hedge_maze/test",
                        "offset": [0, 0, 0],
                    }
                ],
            },
        }

        key, job, persistent = self.service._next_persistent_job(
            [
                {
                    "dimensionId": 33027004,
                    "position": (264.0, 80.0, 264.0),
                }
            ]
        )

        self.assertIsNone(key)
        self.assertIsNone(job)
        self.assertFalse(persistent)

    def test_player_movement_never_activates_automatic_backlog(self):
        self.service._ledger = {
            "24,808": {
                "state": "planned",
                "kind": "naga_courtyard",
                "entryId": "naga_courtyard",
                "center": [24, 808],
                "anchor": [-32, 69, 752],
                "pieces": [
                    {
                        "structure": "tf_slice/ruins/naga_courtyard/test",
                        "offset": [0, 0, 0],
                    }
                ],
            },
            "776,-759": {
                "state": "planned",
                "kind": "naga_courtyard",
                "entryId": "naga_courtyard",
                "center": [776, -759],
                "anchor": [720, 64, -815],
                "pieces": [
                    {
                        "structure": "tf_slice/ruins/naga_courtyard/test",
                        "offset": [0, 0, 0],
                    }
                ],
            },
        }

        first_key, _, _ = self.service._next_persistent_job(
            [
                {
                    "dimensionId": 33027004,
                    "position": (24.0, 90.0, 808.0),
                }
            ]
        )
        second_key, _, _ = self.service._next_persistent_job(
            [
                {
                    "dimensionId": 33027004,
                    "position": (776.0, 90.0, -759.0),
                }
            ]
        )

        self.assertIsNone(first_key)
        self.assertIsNone(second_key)

    def test_player_backfill_is_throttled_and_proximity_bounded(self):
        players = [
            {
                "dimensionId": 33027004,
                "position": (8.0, 64.0, 8.0),
            }
        ]

        self.service.tick(SERVICE.SCAN_INTERVAL_TICKS - 1, players)
        self.assertEqual({}, self.service._ledger)

        self.service.tick(
            SERVICE.SCAN_INTERVAL_TICKS,
            [
                {
                    "dimensionId": 0,
                    "position": (8.0, 64.0, 8.0),
                },
                {
                    "dimensionId": 33027004,
                    "position": (80.0, 64.0, 8.0),
                },
            ],
        )

        self.assertEqual({}, self.service._ledger)
        self.assertEqual(
            0,
            self.service.debug_status()["playerProximityBackfillEvents"],
        )

    def test_rejected_and_foreign_events_never_enter_the_server_queue(self):
        forbidden = self.accepted_event()
        forbidden["biomeName"] = "dm33027004_ocean"
        self.service.on_structure_feature_event(forbidden)
        self.assertFalse(forbidden["cancel"])
        self.assertEqual(
            "tf_slice:ruin_landmark_noop",
            forbidden["structureName"],
        )

        wrong_dimension = self.accepted_event()
        wrong_dimension["dimensionId"] = 0
        self.service.on_structure_feature_event(wrong_dimension)
        self.assertFalse(wrong_dimension["cancel"])
        self.assertEqual(
            "tf_slice:ruin_landmark_noop",
            wrong_dimension["structureName"],
        )

        foreign = {
            "structureName": "other_pack:house",
            "dimensionId": 33027004,
            "cancel": False,
        }
        self.service.on_structure_feature_event(foreign)
        self.assertFalse(foreign["cancel"])
        self.assertEqual(
            self.service.debug_status()["nativeHandoffs"],
            0,
        )

    def test_malformed_handoff_event_becomes_noop_without_queueing(self):
        malformed = self.accepted_event()
        malformed["dimensionId"] = None
        malformed["x"] = "not-a-coordinate"

        self.service.on_structure_feature_event(malformed)

        self.assertFalse(malformed["cancel"])
        self.assertEqual(
            "tf_slice:ruin_landmark_noop",
            malformed["structureName"],
        )
        self.assertEqual(
            self.service.debug_status()["nativeHandoffs"],
            0,
        )

    def test_server_tick_only_records_engine_placed_native_structure(self):
        event = self.accepted_event()
        self.service.on_structure_feature_event(event)

        self.service.tick(1, [])
        self.assertEqual(self.factory.game.placements, [])
        self.assertEqual([], self.factory.chunk.added)
        self.assertEqual(1, len(self.service._ledger))
        recorded = list(self.service._ledger.values())[0]
        self.assertEqual("complete", recorded["state"])
        self.assertEqual("druid_hut", recorded["kind"])

    def test_explicit_manual_landmark_uses_loaded_chunk_without_area(self):
        job = SERVICE.ruin_logic.create_landmark_job(
            "hedge_maze",
            (0, 64, 0),
            0,
            [
                {
                    "structure": "tf_slice/ruins/hedge_maze/test",
                    "offset": [0, 0, 0],
                    "size": [16, 8, 16],
                }
            ],
            [0, 64, 0, 15, 71, 15],
        )
        job["center"] = [8, 8]
        self.service._ledger = {"manual:8,8": job}

        self.service.tick(
            1,
            [
                {
                    "dimensionId": 33027004,
                    "position": (8.0, 70.0, 8.0),
                }
            ],
        )

        self.assertEqual([], self.factory.chunk.added)
        self.assertEqual(1, len(self.factory.game.placements))
        self.assertEqual("complete", job["state"])

    def test_automatic_landmark_does_not_progress_without_nearby_player(self):
        job = SERVICE.ruin_logic.create_landmark_job(
            "hedge_maze",
            (0, 64, 0),
            0,
            [
                {
                    "structure": "tf_slice/ruins/hedge_maze/test",
                    "offset": [0, 0, 0],
                    "size": [16, 8, 16],
                }
            ],
            [0, 64, 0, 15, 71, 15],
        )
        job["center"] = [8, 8]
        self.service._ledger = {"8,8": job}

        self.service.tick(1, [])

        self.assertEqual([], self.factory.chunk.added)
        self.assertEqual([], self.factory.game.placements)
        self.assertEqual("planned", job["state"])

    def test_manual_landmark_slice_progresses_when_an_earlier_chunk_is_unloaded(self):
        job = SERVICE.ruin_logic.create_landmark_job(
            "hedge_maze",
            (0, 64, 0),
            0,
            [
                {
                    "structure": "tf_slice/ruins/hedge_maze/left",
                    "offset": [0, 0, 0],
                    "size": [16, 8, 16],
                },
                {
                    "structure": "tf_slice/ruins/hedge_maze/right",
                    "offset": [16, 0, 0],
                    "size": [16, 8, 16],
                },
            ],
            [0, 64, 0, 31, 71, 15],
        )
        job["center"] = [16, 8]
        job["terrain"] = {
            "mode": "flatten",
            "width": 32,
            "depth": 16,
            "flatRadius": 32.0,
            "blendWidth": 8.0,
            "diameter": 0,
            "terrainDiameter": 32,
            "nextColumn": 0,
            "complete": False,
        }
        self.service._ledger = {"manual:16,8": job}
        self.factory.chunk.ready_chunks = {(1, 0)}
        original_columns = SERVICE.MAX_TERRAIN_COLUMNS_PER_TICK
        SERVICE.MAX_TERRAIN_COLUMNS_PER_TICK = 512
        try:
            self.service.tick(
                1,
                [
                    {
                        "dimensionId": 33027004,
                        "position": (24.0, 70.0, 8.0),
                    }
                ],
            )
            self.service.tick(
                2,
                [
                    {
                        "dimensionId": 33027004,
                        "position": (24.0, 70.0, 8.0),
                    }
                ],
            )
        finally:
            SERVICE.MAX_TERRAIN_COLUMNS_PER_TICK = original_columns

        self.assertEqual([], self.factory.chunk.added)
        self.assertEqual(1, len(self.factory.game.placements))
        self.assertEqual(
            "tf_slice:ruins/hedge_maze/right",
            self.factory.game.placements[0][2],
        )
        self.assertIn(1, job["completedPieces"])
        self.assertNotIn(0, job["completedPieces"])
        self.assertFalse(job["terrain"]["complete"])

    def test_piece_waits_for_terrain_in_every_world_chunk_it_overlaps(self):
        job = SERVICE.ruin_logic.create_landmark_job(
            "naga_courtyard",
            (1, 64, 0),
            0,
            [
                {
                    "structure": (
                        "tf_slice/ruins/naga_courtyard/v00/x000_z000"
                    ),
                    "offset": [0, 0, 0],
                    "size": [16, 12, 16],
                }
            ],
            [1, 64, 0, 16, 75, 15],
        )
        job["center"] = [9, 8]
        job["terrain"] = {
            "mode": "flatten",
            "width": 32,
            "depth": 16,
            "flatRadius": 48.0,
            "blendWidth": 8.0,
            "diameter": 0,
            "terrainDiameter": 32,
            "nextColumn": 0,
            "complete": False,
        }
        slices = self.service._ensure_chunk_slices(job)
        slices["0,0"]["terrainComplete"] = True
        slices["1,0"]["terrainComplete"] = False
        self.service._ledger = {"manual:9,8": job}
        self.factory.chunk.ready_chunks = {(0, 0), (1, 0), (2, 0)}
        player = [
            {
                "dimensionId": 33027004,
                "position": (8.0, 70.0, 8.0),
            }
        ]

        self.service.tick(1, player)

        self.assertEqual([], self.factory.game.placements)
        self.assertNotIn(0, job.get("completedPieces", []))

        slices["1,0"]["terrainComplete"] = True
        self.service.tick(2, player)
        self.service.tick(3, player)

        self.assertEqual(1, len(self.factory.game.placements))
        self.assertIn(0, job["completedPieces"])

    def test_naga_activates_after_marker_piece_before_remote_tiles_finish(self):
        spawned = []

        def spawn_boss(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            self.factory.entity_types["naga-test"] = identifier
            return "naga-test"

        self.service._boss_spawner = spawn_boss
        job = SERVICE.ruin_logic.create_landmark_job(
            "naga_courtyard",
            (0, 64, 0),
            0,
            [
                {
                    "structure": (
                        "tf_slice/ruins/naga_courtyard/v00/x000_z000"
                    ),
                    "offset": [0, 0, 0],
                    "size": [16, 12, 16],
                },
                {
                    "structure": (
                        "tf_slice/ruins/naga_courtyard/v00/x032_z000"
                    ),
                    "offset": [32, 0, 0],
                    "size": [16, 12, 16],
                },
            ],
            [0, 64, 0, 47, 75, 15],
        )
        job["center"] = [8, 8]
        job["bossSpawner"] = {
            "entity": "tf_slice:forest_wyrm",
            "offset": [8, 1, 8],
            "activationRadius": 32,
        }
        self.service._ledger = {"manual:8,8": job}
        self.service._rebuild_runtime_job_indexes()
        self.factory.chunk.ready_chunks = {(0, 0)}

        self.service.tick(
            1,
            [
                {
                    "dimensionId": 33027004,
                    "position": (8.5, 65.0, 8.5),
                }
            ],
        )

        self.assertEqual("placing", job["state"])
        self.assertTrue(job["bossSpawnerReady"])
        self.assertTrue(job["bossSpawned"])
        self.assertEqual(
            [
                (
                    "tf_slice:forest_wyrm",
                    (8.5, 64.0, 8.5),
                    180.0,
                    33027004,
                )
            ],
            spawned,
        )

    def test_naga_spawn_waits_for_a_confirmed_actor_before_committing(self):
        spawned = []
        confirmations = []

        def spawn_boss(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            self.factory.entity_types["naga-pending"] = identifier
            return "naga-pending"

        def confirm_boss(entity_id, expected_identifier):
            confirmations.append((entity_id, expected_identifier))
            if len(confirmations) < 2:
                return None
            return expected_identifier

        self.service._boss_spawner = spawn_boss
        self.service._boss_confirmer = confirm_boss
        job = SERVICE.ruin_logic.create_landmark_job(
            "naga_courtyard",
            (0, 64, 0),
            0,
            [],
            [0, 64, 0, 15, 75, 15],
        )
        job["state"] = "complete"
        job["center"] = [8, 8]
        job["bossSpawner"] = {
            "entity": "tf_slice:forest_wyrm",
            "offset": [8, 1, 8],
            "activationRadius": 32,
        }
        job["bossSpawnerReady"] = True
        job["bossSpawned"] = False
        job["bossDefeated"] = False
        self.service._ledger = {"8,8": job}
        self.service._rebuild_runtime_job_indexes()
        player = [
            {
                "dimensionId": 33027004,
                "position": (8.5, 65.0, 8.5),
            }
        ]

        self.service.tick(1, player)

        self.assertFalse(job["bossSpawned"])
        self.assertEqual("naga-pending", job["bossSpawnPendingId"])
        self.assertFalse(
            any(
                call[1].get("name") == "minecraft:air"
                for call in self.factory.block.set_blocks
            )
        )

        self.service.tick(2, player)

        self.assertTrue(job["bossSpawned"])
        self.assertEqual("naga-pending", job["bossEntityId"])
        self.assertNotIn("bossSpawnPendingId", job)
        self.assertEqual(2, len(confirmations))
        self.assertTrue(
            any(
                call[1].get("name") == "minecraft:air"
                for call in self.factory.block.set_blocks
            )
        )

    def test_hydra_spawn_uses_engine_type_confirmation_without_naga_pending_state(self):
        spawned = []
        specialized_confirmations = []

        def spawn_boss(identifier, position, yaw, dimension_id):
            spawned.append((identifier, position, yaw, dimension_id))
            self.factory.entity_types["hydra-actor"] = identifier
            return "hydra-actor"

        def confirm_naga_or_lich(entity_id, expected_identifier):
            specialized_confirmations.append((entity_id, expected_identifier))
            return None

        self.service._boss_spawner = spawn_boss
        self.service._boss_confirmer = confirm_naga_or_lich
        marker = (8, 65, 8)
        self.factory.block.blocks[marker] = {
            "name": "tf_slice:hydra_boss_spawner",
            "aux": 0,
        }
        job = SERVICE.ruin_logic.create_landmark_job(
            "hydra_lair",
            (0, 64, 0),
            0,
            [],
            [0, 64, 0, 15, 79, 15],
        )
        job.update(
            {
                "state": "complete",
                "center": [8, 8],
                "bossSpawner": {
                    "kind": "hydra",
                    "entity": "tf_slice:hydra",
                    "offset": [8, 1, 8],
                    "markerBlock": "tf_slice:hydra_boss_spawner",
                    "spawnYOffset": 1.0,
                    "activationRadius": 50,
                },
                "physicalBossSpawnerMarker": list(marker),
                "bossSpawnerReady": True,
                "bossSpawned": False,
                "bossDefeated": False,
            }
        )
        self.service._ledger = {"8,8": job}
        self.service._rebuild_runtime_job_indexes()

        self.service.tick(
            1,
            [
                {
                    "dimensionId": 33027004,
                    "position": (8.5, 65.5, 8.5),
                    "progress": {},
                }
            ],
        )

        self.assertEqual(
            [("tf_slice:hydra", (8.5, 66.5, 8.5), 180.0, 33027004)],
            spawned,
        )
        self.assertEqual([], specialized_confirmations)
        self.assertTrue(job["bossSpawned"])
        self.assertEqual("hydra-actor", job["bossEntityId"])
        self.assertNotIn("bossSpawnPendingId", job)
        self.assertEqual("minecraft:air", self.factory.block.blocks[marker]["name"])

    def test_disabled_boss_spawning_keeps_hydra_marker_armed(self):
        spawned = []
        self.service._boss_spawner = lambda *args: spawned.append(args)
        marker = (8, 65, 8)
        self.factory.block.blocks[marker] = {
            "name": "tf_slice:hydra_boss_spawner",
            "aux": 0,
        }
        job = SERVICE.ruin_logic.create_landmark_job(
            "hydra_lair",
            (0, 64, 0),
            0,
            [],
            [0, 64, 0, 15, 79, 15],
        )
        job.update(
            {
                "state": "complete",
                "bossSpawner": {
                    "kind": "hydra",
                    "entity": "tf_slice:hydra",
                    "offset": [8, 1, 8],
                    "markerBlock": "tf_slice:hydra_boss_spawner",
                    "spawnYOffset": 1.0,
                    "activationRadius": 50,
                },
                "physicalBossSpawnerMarker": list(marker),
                "bossSpawnerReady": True,
                "bossSpawned": False,
                "bossDefeated": False,
            }
        )
        self.service._ledger = {"8,8": job}
        self.service._rebuild_runtime_job_indexes()

        self.service.tick(
            1,
            [
                {
                    "dimensionId": 33027004,
                    "position": (8.5, 65.5, 8.5),
                    "progress": {},
                }
            ],
            boss_spawning_enabled=False,
        )

        self.assertEqual([], spawned)
        self.assertFalse(job["bossSpawned"])
        self.assertEqual(
            "tf_slice:hydra_boss_spawner",
            self.factory.block.blocks[marker]["name"],
        )

    def test_terrain_cleanup_clears_plant_above_reported_top_height(self):
        self.factory.block.blocks[(0, 65, 0)] = {
            "name": "minecraft:red_flower",
            "aux": 0,
        }
        job = {"anchor": [0, 64, 0]}
        terrain = {
            "mode": "flatten",
            "width": 1,
            "depth": 1,
            "flatRadius": 0.0,
            "blendWidth": 0.0,
        }

        column = self.service._prepare_terrain_column(job, terrain, 0)

        self.assertIn([65, "minecraft:air"], column["changes"])

    def test_courtyard_terrain_cleanup_reaches_tall_tree_canopies(self):
        self.factory.block.blocks[(0, 104, 0)] = {
            "name": "minecraft:leaves",
            "aux": 0,
        }
        job = {
            "anchor": [0, 64, 0],
            "kind": "naga_courtyard",
        }
        terrain = {
            "mode": "flatten",
            "width": 1,
            "depth": 1,
            "flatRadius": 0.0,
            "blendWidth": 0.0,
        }

        column = self.service._prepare_terrain_column(job, terrain, 0)

        self.assertIn([104, "minecraft:air"], column["changes"])

    def test_layout_repair_removes_old_shifted_structure_blocks(self):
        self.factory.block.blocks[(0, 64, 0)] = {
            "name": "tf_slice:nagastone",
            "aux": 0,
        }
        self.factory.block.blocks[(0, 65, 0)] = {
            "name": "tf_slice:etched_nagastone",
            "aux": 0,
        }
        job = {
            "anchor": [0, 64, 0],
            "kind": "naga_courtyard",
            "generationSource": "layout_repair",
        }
        terrain = {
            "mode": "flatten",
            "width": 1,
            "depth": 1,
            "flatRadius": 0.0,
            "blendWidth": 0.0,
            "clearStructure": True,
        }

        column = self.service._prepare_terrain_column(job, terrain, 0)

        self.assertIn([64, "minecraft:grass_block"], column["changes"])
        self.assertIn([65, "minecraft:air"], column["changes"])

    def test_layout_repair_preserves_unknown_and_protected_player_blocks(self):
        self.factory.block.blocks[(0, 65, 0)] = {
            "name": "minecraft:diamond_block",
            "aux": 0,
        }
        self.factory.block.blocks[(0, 66, 0)] = {
            "name": "minecraft:chest",
            "aux": 0,
        }
        job = {
            "anchor": [0, 64, 0],
            "kind": "naga_courtyard",
            "generationSource": "layout_repair",
        }
        terrain = {
            "mode": "flatten",
            "width": 1,
            "depth": 1,
            "flatRadius": 0.0,
            "blendWidth": 0.0,
            "clearStructure": True,
        }

        column = self.service._prepare_terrain_column(job, terrain, 0)

        self.assertNotIn([65, "minecraft:air"], column["changes"])
        self.assertNotIn([66, "minecraft:air"], column["changes"])

    def test_unloaded_nearest_landmark_does_not_block_a_ready_landmark(self):
        blocked = SERVICE.ruin_logic.create_landmark_job(
            "naga_courtyard",
            (0, 64, 0),
            0,
            [
                {
                    "structure": "tf_slice/ruins/naga_courtyard/blocked",
                    "offset": [0, 0, 0],
                    "size": [16, 8, 16],
                }
            ],
            [0, 64, 0, 15, 71, 15],
        )
        blocked["center"] = [8, 8]
        ready = SERVICE.ruin_logic.create_landmark_job(
            "hedge_maze",
            (32, 64, 0),
            0,
            [
                {
                    "structure": "tf_slice/ruins/hedge_maze/ready",
                    "offset": [0, 0, 0],
                    "size": [16, 8, 16],
                }
            ],
            [32, 64, 0, 47, 71, 15],
        )
        ready["center"] = [40, 8]
        self.service._ledger = {
            "manual:8,8": blocked,
            "manual:40,8": ready,
        }
        self.factory.chunk.ready_chunks = {(2, 0)}

        self.service.tick(
            1,
            [
                {
                    "dimensionId": 33027004,
                    "position": (12.0, 70.0, 8.0),
                }
            ],
        )

        self.assertEqual(1, len(self.factory.game.placements))
        self.assertEqual(
            "tf_slice:ruins/hedge_maze/ready",
            self.factory.game.placements[0][2],
        )
        self.assertEqual("planned", blocked["state"])
        self.assertEqual("complete", ready["state"])

    def test_manual_landmark_waits_only_for_its_current_loaded_chunk(self):
        job = SERVICE.ruin_logic.create_landmark_job(
            "small_hill",
            (0, 64, 0),
            0,
            [
                {
                    "structure": "tf_slice/ruins/hollow_hill/test",
                    "offset": [0, -4, 0],
                    "size": [16, 16, 16],
                    "layer": "shell",
                    "removeBlock": False,
                }
            ],
            [0, 60, 0, 47, 80, 47],
        )
        job["hollowHillCarveComplete"] = True
        self.service._ledger = {"manual:0,0": job}
        self.factory.chunk.ready = False
        players = [
            {
                "dimensionId": 33027004,
                "position": (8.0, 70.0, 8.0),
            }
        ]

        self.service.tick(1, players)
        self.assertEqual([], self.factory.chunk.added)
        self.assertEqual([], self.factory.game.placements)

        self.factory.chunk.ready = True
        self.service.tick(2, players)

        self.assertEqual(1, len(self.factory.game.placements))
        self.assertFalse(self.factory.game.placements[0][8])

    def test_hollow_hill_carve_explicitly_writes_every_air_block(self):
        job = SERVICE.ruin_logic.create_landmark_job(
            "small_hill",
            (0, 64, 0),
            0,
            [],
            [0, 60, 0, 47, 80, 47],
        )
        original_limit = SERVICE.MAX_HOLLOW_HILL_CARVE_BLOCKS_PER_TICK
        SERVICE.MAX_HOLLOW_HILL_CARVE_BLOCKS_PER_TICK = 20000
        try:
            complete, failed = self.service._advance_hollow_hill_carve(job)
        finally:
            SERVICE.MAX_HOLLOW_HILL_CARVE_BLOCKS_PER_TICK = original_limit

        self.assertTrue(complete)
        self.assertFalse(failed)
        self.assertTrue(job["hollowHillCarveComplete"])
        self.assertEqual(6596, len(self.factory.block.set_blocks))
        self.assertTrue(
            all(
                call[1]["name"] == "minecraft:air"
                for call in self.factory.block.set_blocks
            )
        )
        status = self.service.debug_status()
        self.assertEqual(1, status["hollowHillCarvesStarted"])
        self.assertEqual(1, status["hollowHillCarvesCompleted"])
        self.assertEqual(6596, status["hollowHillCarveBlocks"])

    def test_hollow_hill_carve_accepts_already_air_as_idempotent_success(self):
        self.factory.block.blocks[(23, 66, 23)] = {
            "name": "minecraft:air",
            "aux": 0,
        }
        self.assertTrue(
            self.service._set_terrain_block(
                23,
                66,
                23,
                "minecraft:air",
            )
        )

    def test_hollow_hill_is_carved_before_first_shell_piece(self):
        job = SERVICE.ruin_logic.create_landmark_job(
            "small_hill",
            (0, 64, 0),
            0,
            [
                {
                    "structure": "tf_slice/ruins/hollow_hill/test",
                    "offset": [0, -4, 0],
                    "layer": "shell",
                    "removeBlock": False,
                }
            ],
            [0, 60, 0, 47, 80, 47],
        )
        job["terrain"] = {
            "mode": "hill_base",
            "width": 48,
            "depth": 48,
            "flatRadius": 16.0,
            "blendWidth": 8.0,
            "diameter": 36,
            "terrainDiameter": 48,
            "nextColumn": 48 * 48,
            "complete": True,
        }
        self.service._ledger = {"manual:0,0": job}

        self.service.tick(
            1,
            [
                {
                    "dimensionId": 33027004,
                    "position": (8.0, 70.0, 8.0),
                }
            ],
        )

        self.assertEqual([], self.factory.game.placements)
        self.assertGreater(
            job["hollowHillCarve"]["blocksCleared"],
            0,
        )
        self.assertEqual(0, job["nextPiece"])

    def test_native_callback_does_not_query_or_rewrite_airspace(self):
        event = self.accepted_event()
        self.factory.block.blocks[(116, 65, -42)] = {
            "name": "tf_slice:canopy_log",
            "aux": 0,
        }
        self.service.on_structure_feature_event(event)

        self.service.tick(1, [])

        self.assertEqual(1, len(self.service._ledger))
        self.assertEqual([], self.factory.game.placements)
        self.assertEqual(
            0,
            self.service.debug_status()["nativeCollisionsRejected"],
        )

    def test_native_template_allows_replaceable_leaves_and_plants(self):
        event = self.accepted_event()
        self.factory.block.blocks[(116, 65, -42)] = {
            "name": "tf_slice:canopy_leaves",
            "aux": 0,
        }
        self.factory.block.blocks[(117, 65, -42)] = {
            "name": "minecraft:tallgrass",
            "aux": 0,
        }
        self.service.on_structure_feature_event(event)

        self.service.tick(1, [])

        self.assertEqual(1, len(self.service._ledger))
        self.assertEqual(
            0,
            self.service.debug_status()["nativeCollisionsRejected"],
        )

    def test_replayed_native_event_is_deduplicated_after_completion(self):
        first = self.accepted_event()
        self.service.on_structure_feature_event(first)
        self.service.tick(1, [])
        self.assertEqual(len(self.factory.game.placements), 0)
        self.assertEqual(1, len(self.service._ledger))

        replay = self.accepted_event()
        self.service.on_structure_feature_event(replay)
        self.service.tick(2, [])

        self.assertFalse(replay["cancel"])
        self.assertEqual(len(self.factory.game.placements), 0)
        self.assertEqual(1, len(self.service._ledger))

    def test_hollow_tree_uses_one_chunk_local_trigger_and_only_tiled_templates(self):
        entry = self.service._catalog["leaf_dungeon"]
        chunk_native = entry["chunkNative"]
        self.assertEqual(
            SERVICE.HOLLOW_TREE_TRIGGER_STRUCTURE,
            chunk_native["triggerStructure"],
        )
        self.assertIn(
            SERVICE.HOLLOW_TREE_TRIGGER_STRUCTURE,
            self.factory.feature.whitelist,
        )
        self.assertFalse(
            any(
                structure_name.startswith("tf_slice:ruins/hollow_tree/")
                for structure_name in self.service._native_structure_index
            )
        )
        variants = entry["variants"]
        self.assertEqual(8, len(variants))
        for variant in variants:
            self.assertNotIn("nativeFeature", variant)
            self.assertEqual(
                {(0, 0), (0, 16), (16, 0), (16, 16)},
                {
                    (piece["offset"][0], piece["offset"][2])
                    for piece in variant["pieces"]
                },
            )
            for piece in variant["pieces"]:
                self.assertLessEqual(piece["size"][0], 16)
                self.assertLessEqual(piece["size"][2], 16)

    def test_hollow_tree_trigger_selects_all_four_tiles_from_one_shared_cell(self):
        variant_count = len(
            self.service._catalog["leaf_dungeon"]["variants"]
        )
        selected_cell = None
        for chunk_x in range(-64, 65, 2):
            for chunk_z in range(-64, 65, 2):
                selection = SERVICE.ruin_logic.hollow_tree_chunk_tile(
                    chunk_x,
                    chunk_z,
                    self.service._world_seed,
                    variant_count,
                )
                if selection is None:
                    continue
                center_x = int(selection["cellChunkX"]) * 16 + 16
                center_z = int(selection["cellChunkZ"]) * 16 + 16
                if SERVICE.ruin_logic.is_inside_landmark_clearance(
                    center_x,
                    center_z,
                    self.service._world_seed,
                    SERVICE.SUPPORTED_VARIETY,
                    SERVICE.HOLLOW_TREE_CLEARANCE_CHUNKS,
                ):
                    continue
                selected_cell = selection
                break
            if selected_cell is not None:
                break
        self.assertIsNotNone(selected_cell)

        selected_names = {}
        cell_chunk_x = selected_cell["cellChunkX"]
        cell_chunk_z = selected_cell["cellChunkZ"]
        for tile_x in range(2):
            for tile_z in range(2):
                event = {
                    "structureName": SERVICE.HOLLOW_TREE_TRIGGER_STRUCTURE,
                    "x": (cell_chunk_x + tile_x) * 16,
                    "y": 64,
                    "z": (cell_chunk_z + tile_z) * 16,
                    "biomeName": "dm33027004_plains",
                    "dimensionId": 33027004,
                    "cancel": False,
                }
                self.service.on_structure_feature_event(event)
                selected_names[(tile_x, tile_z)] = event["structureName"]

        variant_name = "v%02d" % selected_cell["variant"]
        self.assertEqual(
            {
                (tile_x, tile_z): (
                    "tf_slice:ruins/hollow_tree/%s/x%03d_z%03d"
                    % (variant_name, tile_x * 16, tile_z * 16)
                )
                for tile_x in range(2)
                for tile_z in range(2)
            },
            selected_names,
        )
        self.service.tick(1, [])
        tree_records = [
            record
            for key, record in self.service._ledger.items()
            if str(key).startswith("native:hollow_tree:")
        ]
        self.assertEqual(1, len(tree_records))
        self.assertEqual("complete", tree_records[0]["state"])
        self.assertEqual(
            ["0,0", "0,1", "1,0", "1,1"],
            tree_records[0]["treeTiles"],
        )

    def test_locate_returns_the_nearest_tracked_native_ruin(self):
        self.service._ledger = {
            "native:far": {
                "entryId": "druid_hut",
                "kind": "druid_hut",
                "state": "complete",
                "anchor": [500, 61, 500],
                "bounds": [500, 61, 500, 508, 70, 508],
            },
            "native:near": {
                "entryId": "druid_hut",
                "kind": "druid_hut",
                "state": "placing",
                "anchor": [112, 52, -48],
                "bounds": [112, 52, -48, 120, 61, -40],
            },
        }

        succeeded, result = self.service.debug_locate(
            "druid_hut",
            (100, 64, -64),
            1024,
        )

        self.assertTrue(succeeded, result)
        self.assertEqual("druid_hut", result["id"])
        self.assertEqual([116, 52, -44], result["position"])
        self.assertEqual("tracked", result["source"])

    def test_locate_predicts_all_variety_landmarks_without_mutating_ledger(self):
        before = dict(self.service._ledger)

        for ruin_id in ("hedge_maze", "naga_courtyard", "hollow_hill"):
            succeeded, result = self.service.debug_locate(
                ruin_id,
                (0, 64, 0),
                4096,
            )

            self.assertTrue(succeeded)
            self.assertEqual(ruin_id, result["id"])
            self.assertEqual("predicted", result["source"])
            self.assertLessEqual(result["distance"], 4096)
        self.assertEqual(before, self.service._ledger)
        self.assertEqual(0, self.factory.extra.save_count)

    def test_enchanted_forest_keeps_seed_selected_naga_boss(self):
        self.factory.biome.GetBiomeName = (
            lambda _position, _dimension_id:
            "dm33027004_birch_forest_mutated"
        )
        naga_center = None
        quest_center = None
        for chunk_x in range(-64, 65):
            for chunk_z in range(-64, 65):
                if not SERVICE.ruin_logic.is_landmark_center_chunk(
                    chunk_x,
                    chunk_z,
                ):
                    continue
                center = SERVICE.ruin_logic.nearest_landmark_center(
                    chunk_x,
                    chunk_z,
                )
                raw = SERVICE.ruin_logic.resolve_variety_landmark(
                    chunk_x,
                    chunk_z,
                    self.service._world_seed,
                    SERVICE.SUPPORTED_VARIETY,
                )
                if raw == "naga_courtyard" and naga_center is None:
                    naga_center = center
                elif raw != "naga_courtyard" and quest_center is None:
                    quest_center = center
                if naga_center is not None and quest_center is not None:
                    break
            if naga_center is not None and quest_center is not None:
                break

        self.assertEqual(
            "naga_courtyard",
            self.service._landmark_kind_at_center(
                "dm33027004_birch_forest_mutated",
                naga_center[0],
                naga_center[1],
            ),
        )
        self.assertEqual(
            "quest_grove",
            self.service._landmark_kind_at_center(
                "dm33027004_birch_forest_mutated",
                quest_center[0],
                quest_center[1],
            ),
        )

    def test_player_backfill_naga_adapts_existing_terrain(self):
        self.factory.biome.GetBiomeName = (
            lambda _position, _dimension_id:
            "dm33027004_birch_forest_mutated"
        )
        naga_chunk = None
        for chunk_x in range(-64, 65):
            for chunk_z in range(-64, 65):
                if not SERVICE.ruin_logic.is_landmark_center_chunk(
                    chunk_x,
                    chunk_z,
                ):
                    continue
                if SERVICE.ruin_logic.resolve_variety_landmark(
                    chunk_x,
                    chunk_z,
                    self.service._world_seed,
                    SERVICE.SUPPORTED_VARIETY,
                ) == "naga_courtyard":
                    naga_chunk = (chunk_x, chunk_z)
                    break
            if naga_chunk is not None:
                break

        job = self.service.discover_for_generated_chunk(
            naga_chunk[0],
            naga_chunk[1],
            "player_proximity_backfill",
        )

        self.assertEqual("naga_courtyard", job["kind"])
        self.assertEqual("planned", job["state"])
        self.assertEqual("flatten", job["terrain"]["mode"])
        self.assertEqual(48.0, job["terrain"]["flatRadius"])

    def test_locate_uses_seed_grid_when_candidate_biomes_are_unloaded(self):
        self.factory.biome.GetBiomeName = (
            lambda _position, _dimension_id: None
        )

        succeeded, result = self.service.debug_locate(
            "naga_courtyard",
            (0, 80, 0),
            4096,
        )

        self.assertTrue(succeeded)
        self.assertEqual("grid_predicted", result["source"])
        self.assertEqual(80, result["position"][1])
        self.assertLessEqual(result["distance"], 4096)

    def test_locate_falls_back_to_seed_grid_when_live_probe_raises(self):
        def failed_live_probe(_ruin_id, _position, _radius_blocks):
            raise RuntimeError("candidate chunk is not queryable")

        self.service._predicted_landmark_location = failed_live_probe
        succeeded, result = self.service.debug_locate(
            "lich_tower",
            (0, 80, 0),
            4096,
        )

        self.assertTrue(succeeded, result)
        self.assertEqual("grid_predicted", result["source"])
        self.assertEqual("lich_tower", result["id"])
        self.assertLessEqual(result["distance"], 4096)

    def test_large_landmarks_accept_the_adaptive_slope_limits(self):
        def surface_result(entry_id, heights):
            remaining = list(heights)
            self.factory.block.GetTopBlockHeight = (
                lambda _position, _dimension_id: remaining.pop(0)
            )
            entry = self.service._catalog[entry_id]
            return self.service._surface_is_acceptable(
                entry,
                entry["variants"][0],
                8,
                8,
            )

        self.assertEqual(
            63,
            surface_result("naga_courtyard", [63, 56, 68, 62, 64]),
        )
        self.assertIs(
            False,
            surface_result("naga_courtyard", [63, 55, 68, 62, 64]),
        )
        self.assertEqual(
            64,
            surface_result("hollow_hill", [64, 55, 71, 62, 68]),
        )
        self.assertIs(
            False,
            surface_result("hollow_hill", [64, 54, 71, 62, 68]),
        )

    def test_obsolete_policy_rejections_retry_but_observed_slots_remain(self):
        factory = FakeFactory()
        factory.extra.data[SERVICE.LEDGER_KEY] = {
            "legacy": {
                "state": "skipped",
                "reason": "terrain_slope",
                "center": [8, 8],
            },
            "current": {
                "state": "skipped",
                "reason": "terrain_slope",
                "slopePolicyVersion": SERVICE.SLOPE_POLICY_VERSION,
                "center": [264, 264],
            },
            "old_biome": {
                "state": "skipped",
                "reason": "forbidden_biome",
                "center": [392, 392],
            },
            "current_biome": {
                "state": "skipped",
                "reason": "forbidden_biome",
                "biomePolicyVersion": SERVICE.BIOME_POLICY_VERSION,
                "center": [456, 456],
            },
            "old_overlap": {
                "state": "skipped",
                "reason": "landmark_overlap",
                "center": [472, 472],
            },
            "current_overlap": {
                "state": "skipped",
                "reason": "landmark_overlap",
                "overlapPolicyVersion": (
                    SERVICE.LANDMARK_OVERLAP_POLICY_VERSION
                ),
                "center": [488, 488],
            },
            "unported": {
                "state": "skipped",
                "reason": "unported_landmark_slot",
                "center": [520, 520],
            },
            "not_ready": {
                "state": "failed",
                "reason": "discovery_not_ready",
                "center": [776, 776],
            },
            "complete": {
                "state": "complete",
                "kind": "naga_courtyard",
                "center": [1032, 1032],
            },
        }

        service = SERVICE.StructureWorldgenService(
            factory,
            "level",
            33027004,
        )

        self.assertNotIn("legacy", service._ledger)
        self.assertIn("current", service._ledger)
        self.assertNotIn("old_biome", service._ledger)
        self.assertIn("current_biome", service._ledger)
        self.assertNotIn("old_overlap", service._ledger)
        self.assertIn("current_overlap", service._ledger)
        self.assertIn("unported", service._ledger)
        self.assertIn("not_ready", service._ledger)
        self.assertIn("complete", service._ledger)

    def test_dense_mushroom_keeps_generic_landmarks_and_reuses_lich_slots(self):
        self.factory.biome.GetBiomeName = (
            lambda _position, _dimension_id:
            "dm33027004_mushroom_island"
        )

        generic_center = None
        tower_center = None
        for chunk_x in range(-64, 65, 16):
            for chunk_z in range(-64, 65, 16):
                if not SERVICE.ruin_logic.is_landmark_center_chunk(
                    chunk_x,
                    chunk_z,
                ):
                    continue
                raw = SERVICE.ruin_logic.pick_variety_landmark(
                    chunk_x,
                    chunk_z,
                    self.service._world_seed,
                )
                if raw == "lich_tower" and tower_center is None:
                    tower_center = (chunk_x, chunk_z)
                elif raw in SERVICE.SUPPORTED_VARIETY and generic_center is None:
                    generic_center = (chunk_x, chunk_z)

        generic = self.service.discover_for_generated_chunk(
            generic_center[0],
            generic_center[1],
        )
        tower = self.service.discover_for_generated_chunk(
            tower_center[0],
            tower_center[1],
        )

        self.assertIn(generic["kind"], SERVICE.SUPPORTED_VARIETY)
        self.assertEqual("mushroom_tower", tower["kind"])

    def test_ordinary_lich_slot_resolves_to_a_planned_tower_job(self):
        self.factory.biome.GetBiomeName = (
            lambda _position, _dimension_id: "dm33027004_plains"
        )
        tower_center = None
        for chunk_x in range(-64, 65, 16):
            for chunk_z in range(-64, 65, 16):
                if SERVICE.ruin_logic.pick_variety_landmark(
                    chunk_x,
                    chunk_z,
                    self.service._world_seed,
                ) == "lich_tower":
                    tower_center = (chunk_x, chunk_z)
                    break
            if tower_center is not None:
                break

        self.assertIsNotNone(tower_center)
        job = self.service.discover_for_generated_chunk(
            tower_center[0],
            tower_center[1],
        )

        self.assertEqual("lich_tower", job["kind"])
        self.assertEqual("lich_tower", job["entryId"])
        self.assertEqual("planned", job["state"])
        self.assertEqual("lich", job["bossSpawner"]["kind"])
        ledger_key = "%d,%d" % tuple(job["center"])
        self.assertIn(ledger_key, self.service._boss_job_keys)

    def test_magic_map_uses_actual_ledger_landmark_and_hides_failures(self):
        self.factory.biome.GetBiomeName = (
            lambda _position, _dimension_id: "dm33027004_plains"
        )
        lich_center = None
        for chunk_x in range(-64, 65, 16):
            for chunk_z in range(-64, 65, 16):
                if SERVICE.ruin_logic.pick_variety_landmark(
                    chunk_x,
                    chunk_z,
                    self.service._world_seed,
                ) == "lich_tower":
                    lich_center = SERVICE.ruin_logic.nearest_landmark_center(
                        chunk_x,
                        chunk_z,
                    )
                    break
            if lich_center is not None:
                break

        self.assertIsNotNone(lich_center)
        self.assertEqual(
            "lich_tower",
            self.service._magic_map_kind_at_center(*lich_center),
        )
        ledger_key = "%d,%d" % lich_center
        self.service._ledger[ledger_key] = {
            "kind": "lich_tower",
            "state": "skipped",
        }
        self.assertIsNone(
            self.service._magic_map_kind_at_center(*lich_center)
        )
        self.service._ledger[ledger_key] = {
            "kind": "large_hill",
            "state": "complete",
        }
        self.assertEqual(
            "large_hill",
            self.service._magic_map_kind_at_center(*lich_center),
        )

    def test_locate_reports_unknown_and_unseen_native_ruins(self):
        succeeded, detail = self.service.debug_locate(
            "not_a_ruin",
            (0, 64, 0),
        )
        self.assertFalse(succeeded)
        self.assertEqual("unknown ruin id", detail)

        succeeded, detail = self.service.debug_locate(
            "well",
            (0, 64, 0),
            1024,
        )
        self.assertFalse(succeeded)
        self.assertIn("explored chunks", detail)

    def test_stronghold_pedestal_opens_owned_shields_and_persists_visual(self):
        anchor = (100, 50, 100)
        pedestal = (101, 50, 101)
        shield = (102, 50, 101)
        self.factory.block.blocks[pedestal] = {
            "name": "tf_slice:trophy_pedestal",
            "aux": 0,
        }
        self.factory.block.blocks[shield] = {
            "name": "tf_slice:stronghold_shield",
            "aux": 0,
        }
        ledger_key = "stronghold"
        self.service._ledger[ledger_key] = {
            "kind": "knight_stronghold",
            "anchor": list(anchor),
            "markers": {
                "trophyPedestal": {"offset": [1, 0, 1]},
                "shieldWalls": [[2, 0, 1]],
            },
        }
        self.service._knight_group_job_keys.add(ledger_key)

        self.assertTrue(self.service.activate_trophy_pedestal(pedestal))
        self.assertEqual(
            "minecraft:air",
            self.factory.block.blocks[shield]["name"],
        )
        self.assertTrue(
            self.factory.block_state.states[pedestal]["tf_slice:active"]
        )
        self.assertTrue(
            self.service._ledger[ledger_key]["trophyPedestalActivated"]
        )
        self.assertTrue(
            self.service._ledger[ledger_key]["trophyPedestalActiveVisual"]
        )


if __name__ == "__main__":
    unittest.main()
