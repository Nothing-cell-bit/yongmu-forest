# -*- coding: utf-8 -*-
import hashlib
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
PACKAGE = BP / "TwilightBossSlice"
TOOLS = ROOT / "tools"
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def dark_tower_entry():
    document = json.loads(
        (BP / "structures" / "tf_slice" / "ruins" / "structure_catalog_v1.json").read_text(
            encoding="utf-8"
        )
    )
    return next(value for value in document["structures"] if value["id"] == "dark_tower")


def render_dark_tower(seed, decoration_seed=None):
    from tools import build_phantom_urghast_structures as route_builder
    from tools import build_ruin_structures as ruin_builder

    api = {
        "SparseStructure": ruin_builder.SparseStructure,
        "FORBIDDEN_OUTPUT_BLOCKS": ruin_builder.FORBIDDEN_OUTPUT_BLOCKS,
        "set_loot_container": ruin_builder.set_loot_container,
        "set_spawner": ruin_builder.set_spawner,
    }
    if decoration_seed is None:
        return route_builder._render_dark_tower(seed, api)
    return route_builder._render_dark_tower(
        seed,
        api,
        decoration_seed=decoration_seed,
    )


class DarkTowerStructureContractTests(unittest.TestCase):
    def test_two_topologies_each_compile_two_world_selected_room_variants(self):
        from tools import build_phantom_urghast_structures as route_builder

        profiles = route_builder.dark_tower_variant_profiles()
        self.assertEqual(4, len(profiles))
        self.assertEqual(
            [
                {"id": "seed_0", "layoutSeed": 0, "decorationSeed": 0},
                {"id": "seed_1", "layoutSeed": 1, "decorationSeed": 1},
            ],
            profiles[:2],
        )
        self.assertEqual(4, len({profile["id"] for profile in profiles}))
        self.assertEqual(
            {0, 1},
            {profile["layoutSeed"] for profile in profiles},
        )
        for layout_seed in (0, 1):
            matching = [
                profile
                for profile in profiles
                if profile["layoutSeed"] == layout_seed
            ]
            self.assertEqual(2, len(matching))
            self.assertEqual(
                {0, 1},
                {profile["decorationSeed"] for profile in matching},
            )

    def test_room_decoration_seed_changes_rooms_without_changing_topology(self):
        first = render_dark_tower(0, decoration_seed=0)
        second = render_dark_tower(0, decoration_seed=1)
        _first_structure, first_markers, _validation, first_graph, first_boss = first
        _second_structure, second_markers, _validation, second_graph, second_boss = second
        self.assertEqual(first_markers["mainTowers"], second_markers["mainTowers"])
        self.assertEqual(first_markers["wingTowers"], second_markers["wingTowers"])
        self.assertEqual(first_graph, second_graph)
        self.assertEqual(first_boss, second_boss)
        first_rooms = [
            (room["tower"], room["offset"][1], room["type"])
            for room in first_markers["rooms"]
        ]
        second_rooms = [
            (room["tower"], room["offset"][1], room["type"])
            for room in second_markers["rooms"]
        ]
        self.assertNotEqual(first_rooms, second_rooms)

    def test_catalog_builder_serializes_variant_canopy_cleanup_masks(self):
        from unittest import mock

        from tools import build_phantom_urghast_structures as route_builder
        from tools import build_ruin_structures as ruin_builder

        serialized_guard_counts = []
        serialized_cleanup_counts = []

        def capture_slices(_root, structure, _offset, _api):
            serialized_guard_counts.append(
                sum(
                    block[0] == "tf_slice:tower_interior_guard"
                    for block in structure.blocks.values()
                )
            )
            return [
                {
                    "structure": "tf_slice/ruins/test",
                    "offset": [0, 0, 0],
                    "size": [1, 1, 1],
                    "recoveryOrder": [0, 0, 0],
                }
            ]

        def capture_cleanup(variant_id, cleanup_structure):
            cleanup_names = {
                block[0] for block in cleanup_structure.blocks.values()
            }
            self.assertEqual({"minecraft:air"}, cleanup_names)
            count = len(cleanup_structure.blocks)
            serialized_cleanup_counts.append(count)
            return {
                "prefix": (
                    "tf_slice/ruins/dark_tower_canopy_cleanup/"
                    + variant_id
                ),
                "centerAlignments": {"8,8": [-3, -3, 3, 3]},
                "count": count,
            }

        api = {
            "SparseStructure": ruin_builder.SparseStructure,
            "FORBIDDEN_OUTPUT_BLOCKS": ruin_builder.FORBIDDEN_OUTPUT_BLOCKS,
            "set_loot_container": ruin_builder.set_loot_container,
            "set_spawner": ruin_builder.set_spawner,
            "combined_bounds": lambda _pieces: [0, 0, 0, 0, 0, 0],
            "write_surface_native_tiles": (
                lambda _kind, _variant, _structure, _seed: {}
            ),
            "write_dark_tower_canopy_cleanup_tiles": capture_cleanup,
            "catalog_entry": (
                lambda ruin_id, strategy, biome_tags, pieces, **metadata: {
                    "id": ruin_id,
                    "strategy": strategy,
                    "biomeTags": biome_tags,
                    "pieces": pieces,
                    **metadata,
                }
            ),
        }
        with mock.patch.object(
            route_builder,
            "_write_vertical_slices",
            side_effect=capture_slices,
        ):
            entry = route_builder.build_dark_tower_entry(api)

        self.assertEqual(4, len(entry["variants"]))
        self.assertEqual(4, len(serialized_guard_counts))
        self.assertEqual([0, 0, 0, 0], serialized_guard_counts)
        self.assertEqual(4, len(serialized_cleanup_counts))
        self.assertTrue(all(count > 0 for count in serialized_cleanup_counts))
        for variant, count in zip(
            entry["variants"], serialized_cleanup_counts
        ):
            self.assertEqual(
                count,
                variant["markers"]["canopyCleanup"]["count"],
            )
            self.assertEqual(
                count,
                variant["canopyCleanup"]["count"],
            )
            cleanup = variant["canopyCleanup"]
            self.assertEqual(1, cleanup["schemaVersion"])
            self.assertTrue(cleanup["runtimeWrites"])
            self.assertEqual(
                "bounded_authored_air_leaf_only",
                cleanup["writeMode"],
            )
            self.assertEqual(
                count,
                sum(
                    int(maximum_y) - int(minimum_y) + 1
                    for _x, _z, minimum_y, maximum_y
                    in cleanup["runs"]
                ),
            )

    def test_source_topology_is_a_three_stage_tower_complex(self):
        for seed in (0, 1):
            structure, markers, validation, graph, boss_spawner = render_dark_tower(seed)

            main_towers = markers["mainTowers"]
            self.assertEqual(3, len(main_towers))
            self.assertEqual([19, 19, 19], [tower["size"] for tower in main_towers])
            self.assertEqual(
                sorted(tower["bottomY"] for tower in main_towers),
                [tower["bottomY"] for tower in main_towers],
            )
            self.assertEqual(3, len({tuple(tower["center"]) for tower in main_towers}))
            self.assertTrue(all(56 <= tower["height"] <= 86 for tower in main_towers))

            # The first two main components each consume four side-tower keys.
            self.assertEqual(2, len(markers["keyDoors"]))
            for door in markers["keyDoors"]:
                self.assertEqual(4, len(door["locks"]))
                for position in door["locks"]:
                    block = structure.blocks[tuple(position)]
                    self.assertEqual("tf_slice:tower_key_door", block[0])
                    self.assertIs(
                        block[1].get("tf_slice:locked"),
                        True,
                        (seed, door, position, block),
                    )
            self.assertEqual(8, len(markers["keyTowers"]))
            self.assertEqual(8, len(markers["keyChests"]))
            self.assertEqual([0, 0, 0, 0, 1, 1, 1, 1], sorted(
                tower["stage"] for tower in markers["keyTowers"]
            ))

            self.assertEqual(2, len(markers["entranceTowers"]))
            surface_entrance = markers["surfaceEntrance"]
            self.assertEqual(
                "tf_slice:reappearing_block",
                structure.blocks[tuple(surface_entrance["offset"])][0],
            )
            self.assertEqual(4, len(markers["bossTrapTowers"]))
            self.assertEqual(4, len(markers["ghastTraps"]))
            self.assertGreaterEqual(len(markers["balconies"]), 4)
            self.assertGreaterEqual(len(markers["wingTowers"]), 18)
            self.assertGreaterEqual(len(markers["bridges"]), 24)
            for bridge in markers["bridges"]:
                start = bridge["start"]
                end = bridge["end"]
                self.assertTrue(start[0] == end[0] or start[2] == end[2], bridge)
                self.assertIn(tuple(start), structure.blocks)
                self.assertIn(tuple(end), structure.blocks)
            self.assertEqual(list(boss_spawner), markers["urGhastSpawner"]["offset"])
            self.assertTrue(validation["allMainTowersReachable"])
            self.assertTrue(validation["allKeyTowersReachable"])
            self.assertTrue(validation["bossTrapsReachable"])
            self.assertTrue(validation["roomCoverageComplete"])
            self.assertGreater(len(graph), 20)

    def test_entrance_towers_keep_both_source_exterior_reappearing_doors(self):
        for seed in (0, 1):
            structure, markers, _validation, _graph, _boss = (
                render_dark_tower(seed)
            )
            exterior_centers = []
            for tower in markers["entranceTowers"]:
                self.assertEqual(2, len(tower["exteriorDoors"]))
                for door in tower["exteriorDoors"]:
                    center = tuple(door["center"])
                    exterior_centers.append(center)
                    self.assertEqual(
                        "tf_slice:reappearing_block",
                        structure.blocks[center][0],
                        (seed, tower["id"], center),
                    )
                    self.assertEqual(9, len(door["blocks"]))
                    self.assertEqual(16, len(door["frame"]))
                    self.assertTrue(
                        all(
                            structure.blocks[tuple(position)][0]
                            == "tf_slice:reappearing_block"
                            for position in door["blocks"]
                        )
                    )
                    self.assertTrue(
                        all(
                            structure.blocks[tuple(position)][0]
                            == "tf_slice:encased_towerwood"
                            for position in door["frame"]
                        )
                    )
            self.assertEqual(4, len(exterior_centers))
            self.assertIn(
                tuple(markers["surfaceEntrance"]["offset"]),
                exterior_centers,
            )

    def test_final_boss_platform_is_a_bombed_three_quarter_tower_floor(self):
        for seed in (0, 1):
            structure, markers, _validation, _graph, boss_spawner = render_dark_tower(seed)
            boss_main = markers["mainTowers"][2]
            center_x, center_z = boss_main["center"]
            platform_y = markers["bossPlatform"]["offset"][1]
            top_y = boss_main["bottomY"] + boss_main["height"] - 1

            def is_solid(position):
                block = structure.blocks.get(position)
                return block is not None and block[0] != "minecraft:air"

            # The boss loop leaves the last source three-quarter floor empty;
            # the five bursts damage the roof above rather than deleting every
            # block between the landing and the sky.
            for y in range(platform_y + 1, platform_y + 4):
                open_columns = sum(
                    1
                    for x in range(center_x - 4, center_x + 5)
                    for z in range(center_z - 4, center_z + 5)
                    if not is_solid((x, y, z))
                )
                self.assertGreater(open_columns, 60, (seed, y, open_columns))
            self.assertEqual(platform_y + 4, boss_spawner[1])

            roof_blocks = [
                is_solid((x, top_y, z))
                for x in range(center_x - 9, center_x + 10)
                for z in range(center_z - 9, center_z + 10)
            ]
            self.assertTrue(any(roof_blocks))
            self.assertTrue(any(not value for value in roof_blocks))

            # The source's five destruction bursts remove the boss chamber's
            # roof instead of constructing a new netherrack dome in source
            # air.  Most arena columns must therefore remain open all the way
            # to the sky, with netherrack limited to damaged source masonry.
            open_sky_columns = 0
            netherrack_columns = 0
            for x in range(center_x - 8, center_x + 9):
                for z in range(center_z - 8, center_z + 9):
                    blocks_above = {
                        structure.blocks.get((x, y, z), ("minecraft:air",))[0]
                        for y in range(platform_y + 1, top_y + 13)
                    }
                    solid_above = blocks_above - {
                        "minecraft:air",
                        "minecraft:fire",
                    }
                    if not solid_above:
                        open_sky_columns += 1
                    if "minecraft:netherrack" in solid_above:
                        netherrack_columns += 1
            self.assertGreaterEqual(open_sky_columns, 174, seed)
            self.assertLess(netherrack_columns, 97, seed)

            # Keep a visibly bomb-damaged outer rim: neither a missing wall nor
            # the former six-block-tall sealed shell is source-faithful.
            rim = [
                (x, y, z)
                for x in range(center_x - 9, center_x + 10)
                for z in range(center_z - 9, center_z + 10)
                for y in range(platform_y + 1, top_y + 1)
                if abs(x - center_x) == 9 or abs(z - center_z) == 9
            ]
            self.assertTrue(any(is_solid(position) for position in rim))
            self.assertTrue(any(not is_solid(position) for position in rim))

            # All four trap bridges enter through open, three-wide passages at
            # the same floor height; sealed vanishing-block planes would make
            # the otherwise outdoor encounter unusable.
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for across in range(-1, 2):
                    x = center_x + dx * 9 + (across if dz else 0)
                    z = center_z + dz * 9 + (across if dx else 0)
                    for y in range(platform_y + 1, platform_y + 4):
                        self.assertFalse(is_solid((x, y, z)), (seed, x, y, z))

    def test_boss_destruction_does_not_erase_separate_trap_bridge_pieces(self):
        from tools import dark_tower_legacy_port as port

        for seed in (0, 1):
            structure, markers, _validation, _graph, _boss_spawner = (
                render_dark_tower(seed)
            )
            boss_bridges = markers["bridges"][-4:]
            self.assertEqual(4, len(boss_bridges))
            for bridge in boss_bridges:
                start = tuple(bridge["start"])
                end = tuple(bridge["end"])
                along_x = start[0] != end[0]
                for x, y, z in port._bridge_path(start, end):
                    for across in range(-2, 3):
                        position = (
                            x if along_x else x + across,
                            y,
                            z + across if along_x else z,
                        )
                        self.assertEqual(
                            "tf_slice:encased_towerwood",
                            structure.blocks.get(
                                position, ("minecraft:air",)
                            )[0],
                            (seed, bridge, position),
                        )

    def test_boss_main_destruction_is_authored_before_child_trap_bridges(self):
        source = (TOOLS / "dark_tower_legacy_port.py").read_text(
            encoding="utf-8"
        )
        render = source[
            source.index(
                "def render(seed, api, surface_ground_y, decoration_seed=None):"
            ) :
        ]
        self.assertLess(
            render.index("_open_ruined_boss_top("),
            render.index("for index, center in enumerate(trap_centers):"),
        )

    def test_source_room_pool_roofs_and_bomb_damage_are_materialized(self):
        expected_rooms = {
            "bottom_entrance",
            "reappearing_maze",
            "antibuilder_maze",
            "aquarium",
            "botanical",
            "netherwart",
            "lounge",
            "forge",
            "timber_maze",
            "builder_platforms",
            "reappearing_floor",
            "spawner",
            "library",
            "piston_pulser",
            "lamp_experiment",
            "puzzle_chest",
            "small_timber_beams",
            "key_treasure",
            "reactor_experiment",
            "boss_trap",
        }
        rooms = []
        roofs = set()
        palette = Counter()
        breaches = 0
        for seed in (0, 1):
            structure, markers, validation, _graph, _boss_spawner = render_dark_tower(seed)
            rooms.extend(room["type"] for room in markers["rooms"])
            roofs.update(roof["type"] for roof in markers["roofs"])
            breaches += len(markers["bombedBreaches"])
            palette.update(value[0] for value in structure.blocks.values())
            self.assertGreaterEqual(len(markers["rooms"]), 40)
            self.assertTrue(validation["roomCoverageComplete"])

        self.assertTrue(expected_rooms.issubset(set(rooms)))
        self.assertEqual({"antenna", "cactus", "rings", "four_post"}, roofs)
        self.assertGreaterEqual(breaches, 8)
        for block in (
            "tf_slice:reappearing_block",
            "tf_slice:carminite_antibuilder",
            "tf_slice:carminite_builder",
            "tf_slice:carminite_reactor",
            "minecraft:water",
            "minecraft:bookshelf",
            "minecraft:furnace",
            "minecraft:anvil",
            "minecraft:soul_sand",
            "minecraft:nether_wart",
            "minecraft:netherrack",
        ):
            self.assertGreater(palette[block], 0, block)

    def test_reactor_experiment_is_the_complete_source_workshop(self):
        from tools import build_ruin_structures as ruin_builder
        from tools import dark_tower_legacy_port as tower_port

        structure = ruin_builder.SparseStructure(
            (48, 32, 48), "dark_tower_reactor_room"
        )
        markers = {"rooms": [], "mechanisms": []}
        tower_port._decorate_reactor_room(
            structure, markers, "main_2", (24, 24), 8, 0
        )
        palette = Counter(value[0] for value in structure.blocks.values())

        # DarkTowerMainComponent.decorateExperiment contains a crafting alcove,
        # two short and two long piston plungers, and six controls. Experiment
        # 115 is a separate food block and is never placed in this room.
        self.assertEqual(1, palette["minecraft:crafting_table"])
        self.assertEqual(4, palette["minecraft:piston"])
        self.assertEqual(2, palette["minecraft:sticky_piston"])
        self.assertEqual(6, palette["minecraft:lever"])
        self.assertGreaterEqual(palette["minecraft:redstone_block"], 6)
        self.assertEqual(0, palette["tf_slice:experiment_115"])
        self.assertEqual(18, palette["minecraft:frame"])
        displayed_items = Counter(
            block_entity.get("Item", {}).get("Name")
            for block, _states, block_entity in structure.blocks.values()
            if block == "minecraft:frame"
        )
        self.assertEqual(4, displayed_items["tf_slice:borer_essence"])
        self.assertEqual(4, displayed_items["minecraft:redstone"])
        self.assertEqual(1, displayed_items["minecraft:ghast_tear"])
        self.assertEqual(4, displayed_items["tf_slice:encased_towerwood"])
        self.assertEqual(4, displayed_items["tf_slice:towerwood"])
        self.assertEqual(1, displayed_items["tf_slice:carminite"])

    def test_side_tower_spawners_use_dark_tower_mobs_in_framed_rooms(self):
        from tools import build_ruin_structures as ruin_builder
        from tools import dark_tower_legacy_port as tower_port

        structure = ruin_builder.SparseStructure(
            (48, 32, 48), "dark_tower_spawner_room"
        )
        markers = {
            "rooms": [],
            "structureSpawners": [],
            "lootChests": [],
        }
        api = {
            "set_spawner": ruin_builder.set_spawner,
            "set_loot_container": ruin_builder.set_loot_container,
        }
        tower = {"id": "support", "center": [24, 24], "size": 11}
        tower_port._decorate_small_room(
            structure, markers, api, tower, "spawner", 8, 0
        )
        self.assertIn(
            markers["structureSpawners"][0]["entity"],
            {"tf_slice:carminite_golem", "tf_slice:tower_broodling"},
        )
        palette = Counter(value[0] for value in structure.blocks.values())
        self.assertGreaterEqual(palette["tf_slice:encased_towerwood"], 8)

    def test_boss_floor_keeps_source_three_quarter_landing_and_spawner_height(self):
        for seed in (0, 1):
            structure, markers, _validation, _graph, boss_spawner = render_dark_tower(seed)
            boss_main = markers["mainTowers"][2]
            center_x, center_z = boss_main["center"]
            platform_y = markers["bossPlatform"]["offset"][1]
            self.assertEqual(
                boss_main["bottomY"] + boss_main["height"] - 6,
                platform_y,
            )
            self.assertEqual(platform_y + 4, boss_spawner[1])

            floor_blocks = sum(
                1
                for x in range(center_x - 8, center_x + 9)
                for z in range(center_z - 8, center_z + 9)
                if structure.blocks.get((x, platform_y, z), ("minecraft:air",))[0]
                != "minecraft:air"
            )
            self.assertGreater(floor_blocks, 160)
            self.assertLess(floor_blocks, 270)

    def test_boss_roof_is_bombed_and_no_roof_trap_towers_stay_open(self):
        for seed in (0, 1):
            structure, markers, _validation, _graph, _boss = render_dark_tower(seed)
            boss_main = markers["mainTowers"][2]
            center_x, center_z = boss_main["center"]
            roof_y = boss_main["bottomY"] + boss_main["height"] - 1
            boss_roof = [
                structure.blocks.get((x, roof_y, z), ("minecraft:air",))[0]
                for x in range(center_x - 9, center_x + 10)
                for z in range(center_z - 9, center_z + 10)
            ]
            self.assertIn("minecraft:air", boss_roof)
            self.assertTrue(any(block != "minecraft:air" for block in boss_roof))

            for tower in markers["bossTrapTowers"]:
                cx, cz = tower["center"]
                radius = tower["size"] // 2
                trap_roof_y = tower["bottomY"] + tower["height"] - 1
                trap_roof = [
                    structure.blocks.get((x, trap_roof_y, z), ("minecraft:air",))[0]
                    for x in range(cx - radius, cx + radius + 1)
                    for z in range(cz - radius, cz + radius + 1)
                ]
                self.assertIn("minecraft:air", trap_roof)
                # DarkTowerBossTrapComponent.makeARoof is intentionally a
                # no-op.  Its upper shell is then hit by three source bursts,
                # so a completely open top plane is a valid source result.
                self.assertLess(
                    sum(block != "minecraft:air" for block in trap_roof),
                    len(trap_roof) // 2,
                )

    def test_four_surface_adapted_locked_room_variants(self):
        entry = dark_tower_entry()
        self.assertEqual("surface_beard_thin", entry["placementProfile"])
        self.assertEqual("knight_phantoms_defeated", entry["structureLockObjective"])
        self.assertEqual(5, entry["clearanceChunks"])
        self.assertEqual(64, entry["verticalSliceHeight"])
        self.assertEqual(5, entry["worldHeightLoweringStep"])
        self.assertEqual(
            ["seed_0", "seed_1"],
            [value["id"] for value in entry["variants"][:2]],
        )
        self.assertEqual(
            {(0, 0), (0, 1), (1, 0), (1, 1)},
            {
                (value["layoutSeed"], value["decorationSeed"])
                for value in entry["variants"]
            },
        )
        self.assertEqual(4, len({value["layoutSha256"] for value in entry["variants"]}))

    def test_ur_ghast_spawner_uses_the_source_block_entity_trigger(self):
        entry = dark_tower_entry()
        spawners = [entry["bossSpawner"]] + [
            variant["bossSpawner"] for variant in entry["variants"]
        ]

        for spawner in spawners:
            self.assertEqual(9, spawner["activationRadius"])
            self.assertEqual(-4, spawner["minPlayerYOffset"])
            self.assertNotIn("progressAll", spawner)

        service = (
            PACKAGE / "structureWorldgenService.py"
        ).read_text(encoding="utf-8")
        migration = service[
            service.index("            if kind in BOSS_VARIETY_LANDMARKS:") :
            service.index(
                "            if (\n"
                "                copied.get(\"state\") in (\"planned\", \"placing\")"
            )
        ]
        self.assertIn('elif kind == "dark_tower":', migration)
        self.assertIn('copied_spawner.pop("progressAll", None)', migration)
        for value in entry["variants"]:
            self.assertEqual([112, 224, 112], value["surfaceNative"]["sourceSize"])
            self.assertEqual(52, value["surfaceNative"]["groundY"])
            self.assertEqual(-16, value["surfaceNative"]["originOffset"][1])
            self.assertEqual(
                [-3, -3, 3, 3],
                value["surfaceNative"]["centerAlignments"]["8,8"],
            )
            self.assertEqual(
                {"mode": "none", "width": 0},
                {
                    "mode": value["surfaceNative"]["terrainAdaptation"]["mode"],
                    "width": value["surfaceNative"]["terrainAdaptation"]["width"],
                },
            )
            self.assertEqual(3, len(value["markers"]["mainTowers"]))
            self.assertEqual(8, len(value["markers"]["keyTowers"]))
            self.assertEqual(4, len(value["markers"]["bossTrapTowers"]))
            integration = value["surfaceNative"]["environmentIntegration"]
            self.assertEqual(16, integration["protectionRadius"])
            self.assertEqual(0, integration["protectedColumns"])

    def test_controlled_spawns_match_the_locked_4_3_2508_table(self):
        tiers = dark_tower_entry()["controlledSpawns"]["tiers"]
        self.assertEqual(
            [
                {"entity": "tf_slice:carminite_golem", "weight": 10, "group": [1, 2]},
                {"entity": "minecraft:skeleton", "weight": 10, "group": [1, 2]},
                {"entity": "minecraft:creeper", "weight": 5, "group": [1, 1]},
                {"entity": "minecraft:enderman", "weight": 2, "group": [1, 2]},
                {"entity": "minecraft:witch", "weight": 1, "group": [1, 1]},
                {"entity": "tf_slice:mini_ghast", "weight": 10, "group": [1, 2]},
                {"entity": "tf_slice:tower_broodling", "weight": 10, "group": [4, 4]},
                {"entity": "tf_slice:pinch_beetle", "weight": 10, "group": [1, 1]},
            ],
            tiers["lower"],
        )
        self.assertEqual(
            [{"entity": "tf_slice:tower_ghast", "weight": 10, "group": [1, 2]}],
            tiers["roof"],
        )
        self.assertEqual(
            [{"entity": "minecraft:squid", "weight": 10, "group": [4, 4]}],
            tiers["water"],
        )

    def test_tower_slices_and_markers_are_complete(self):
        required = {
            "surfaceEntrance",
            "keyDoors",
            "keyChests",
            "mechanisms",
            "ghastTraps",
            "bossPlatform",
            "urGhastSpawner",
            "lootChests",
            "roof",
        }
        for variant in dark_tower_entry()["variants"]:
            self.assertTrue(required.issubset(variant["markers"]))
            self.assertTrue(variant["validation"]["entranceReachable"])
            self.assertTrue(variant["validation"]["keyPathReachable"])
            self.assertTrue(variant["validation"]["bossPlatformReachable"])
            self.assertTrue(variant["validation"]["roofComplete"])
            self.assertEqual([], variant["validation"]["forbiddenBlocks"])
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
            self.assertEqual(offsets, sorted(offsets, key=lambda p: (p[1], p[0], p[2])))


class DarkTowerInteriorSourceParityTests(unittest.TestCase):
    def setUp(self):
        from tools import build_ruin_structures as ruin_builder
        from tools import dark_tower_legacy_port as tower_port

        self.ruin_builder = ruin_builder
        self.tower_port = tower_port

    def _structure(self, size=(64, 64, 64)):
        return self.ruin_builder.SparseStructure(size, "dark_tower_interior_test")

    def _block(self, structure, center, size, x, y, z, rotation=0):
        world_x, world_z = self.tower_port._local(
            center, size, x, z, rotation
        )
        return structure.blocks.get((world_x, y, world_z))

    def test_surface_envelope_keeps_the_authored_tower_base_on_ground(self):
        structure, markers, _validation, _graph, _boss = render_dark_tower(0)
        prepared = self.ruin_builder._surface_native_envelope(
            structure,
            "dark_tower",
        )
        # Dark Forest has one shared surface feature trigger.  It is authored
        # at the stronghold's Y=52, so the Dark Tower's local ground Y=16 must
        # be shifted by 36 inside the mobile structure template.
        placement_ground_y = self.ruin_builder.route_stronghold_ground_y()
        authored_ground_y = structure.surface_ground_y
        source_offset_y = placement_ground_y - authored_ground_y
        margin = prepared.worldgen_margin
        first = markers["mainTowers"][0]
        center_x, center_z = first["center"]
        base = prepared.blocks[
            (
                center_x + margin,
                first["bottomY"] + source_offset_y,
                center_z + margin,
            )
        ]
        self.assertEqual("tf_slice:towerwood", base[0])
        under_base = prepared.blocks[
            (
                center_x + margin,
                first["bottomY"] + source_offset_y - 1,
                center_z + margin,
            )
        ]
        self.assertEqual("tf_slice:encased_towerwood", under_base[0])
        self.assertEqual(placement_ground_y, prepared.surface_ground_y)
        self.assertEqual(0, prepared.worldgen_margin)
        self.assertEqual(-authored_ground_y, prepared.source_origin_offset_y)

    def test_surface_envelope_does_not_cut_native_terrain_or_trees(self):
        structure, _markers, _validation, _graph, _boss = render_dark_tower(0)
        prepared = self.ruin_builder._surface_native_envelope(
            structure,
            "dark_tower",
        )
        source_offset_y = (
            self.ruin_builder.route_stronghold_ground_y()
            - structure.surface_ground_y
        )
        translated_source = {
            (x, y + source_offset_y, z): block
            for (x, y, z), block in structure.blocks.items()
        }
        self.assertEqual(translated_source, prepared.blocks)
        self.assertEqual(0, prepared.environment_integration["protectedColumns"])

    def test_center_tree_search_is_capped_below_aerial_tower_columns(self):
        from tools import build_dark_forest_content as dark_forest

        air_blocks = {
            "minecraft:air",
            "minecraft:cave_air",
            "minecraft:void_air",
        }
        for seed in (0, 1):
            structure, _markers, _validation, _graph, _boss = (
                render_dark_tower(seed)
            )
            ground_y = int(structure.surface_ground_y)
            columns = {}
            for (x, y, z), block in structure.blocks.items():
                if block[0] in air_blocks:
                    continue
                columns.setdefault((x, z), []).append(int(y))
            aerial_columns = [
                heights
                for heights in columns.values()
                if min(heights) > ground_y + 1
            ]
            self.assertGreater(len(aerial_columns), 3000, seed)
            required_depth = max(
                max(heights) - ground_y for heights in aerial_columns
            )
            self.assertGreater(
                required_depth,
                dark_forest.SAFE_DARK_FOREST_TREE_SEARCH_DEPTH,
            )

        search = json.loads(
            (
                ROOT
                / "TwilightBossSliceB"
                / "netease_features"
                / "dark_forest_center_tree_ground_search_feature.json"
            ).read_text(encoding="utf-8")
        )["minecraft:search_feature"]
        self.assertEqual(
            [0, -dark_forest.SAFE_DARK_FOREST_TREE_SEARCH_DEPTH, 0],
            search["search_volume"]["min"],
        )
        center_rule = json.loads(
            (
                ROOT
                / "TwilightBossSliceB"
                / "netease_feature_rules"
                / "dark_forest_center_tree_profile_feature_rule.json"
            ).read_text(encoding="utf-8")
        )["minecraft:feature_rules"]
        self.assertIn("math.min", center_rule["distribution"]["y"])
        self.assertNotIn("math.abs", str(center_rule["distribution"]))

    def test_main_stair_flight_matches_the_source_double_wide_run(self):
        center = (24, 24)
        size = 19
        floor_y = 10
        # Bedrock's stair state points at the high/back side of the tread.
        # The source flight rises toward local north, then rotates clockwise.
        expected_directions = (3, 0, 2, 1)
        for rotation, expected_direction in enumerate(expected_directions):
            structure = self._structure()
            self.tower_port._render_three_quarter_floor(
                structure, center, floor_y, rotation
            )
            for step in range(5):
                z = size // 2 - step + 4
                stair_y = floor_y + step + 1
                for x in (1, 2):
                    stair = self._block(
                        structure, center, size, x, stair_y, z, rotation
                    )
                    self.assertIsNotNone(stair, (rotation, step, x))
                    self.assertEqual("minecraft:spruce_stairs", stair[0])
                    self.assertEqual(expected_direction, stair[1]["weirdo_direction"])
                    self.assertFalse(stair[1]["upside_down_bit"])
                for x in (1, 2, 3):
                    support = self._block(
                        structure, center, size, x, stair_y, z - 1, rotation
                    )
                    self.assertIsNotNone(support, (rotation, step, x))
                    self.assertNotEqual("minecraft:air", support[0])

            # The first tread turns into the floor; middle treads have rails.
            turn = self._block(
                structure, center, size, 3, floor_y + 1, 13, rotation
            )
            self.assertEqual("minecraft:spruce_stairs", turn[0])
            for step in (1, 2, 3):
                z = size // 2 - step + 4
                for dy in (1, 2):
                    rail = self._block(
                        structure,
                        center,
                        size,
                        3,
                        floor_y + step + 1 + dy,
                        z,
                        rotation,
                    )
                    self.assertEqual("minecraft:oak_fence", rail[0])

    def test_side_tower_stairs_are_supported_clear_and_double_wide_when_large(self):
        center = (20, 20)
        floor_y = 20
        for size, lanes in ((9, (7,)), (11, (9, 8))):
            structure = self._structure()
            self.tower_port._render_small_floor(
                structure, center, size, floor_y, 0
            )
            for lane_z in lanes:
                for step in range(4):
                    x = size - 3 - step
                    stair_y = floor_y - step
                    stair = self._block(
                        structure, center, size, x, stair_y, lane_z
                    )
                    self.assertEqual("minecraft:spruce_stairs", stair[0])
                    # This descending flight has its high side at local east.
                    self.assertEqual(0, stair[1]["weirdo_direction"])
                    support = self._block(
                        structure, center, size, x, stair_y - 1, lane_z
                    )
                    self.assertEqual("tf_slice:encased_towerwood", support[0])
                    for clear_x, clear_y in (
                        (x, stair_y + 1),
                        (x, stair_y + 2),
                        (x - 1, stair_y + 2),
                        (x, stair_y + 3),
                        (x - 1, stair_y + 3),
                    ):
                        headroom = self._block(
                            structure,
                            center,
                            size,
                            clear_x,
                            clear_y,
                            lane_z,
                        )
                        self.assertEqual("minecraft:air", headroom[0])

    def test_complete_side_tower_applies_rooms_before_stairs_and_reaches_roof(self):
        structure = self._structure((80, 96, 80))
        tower = {
            "id": "stage_0_support_test",
            "stage": 0,
            "center": [30, 30],
            "bottomY": 53,
            "height": 29,
            "size": 11,
            "keyTower": False,
        }
        markers = {
            "rooms": [],
            "structureSpawners": [],
            "lootChests": [],
            "keyChests": [],
            "keyTowers": [],
            "mechanisms": [],
            "roofs": [],
        }
        api = {
            "set_spawner": self.ruin_builder.set_spawner,
            "set_loot_container": self.ruin_builder.set_loot_container,
        }
        self.tower_port._render_side_tower(
            structure,
            markers,
            api,
            tower,
            "antenna",
            17,
        )

        rotation = (tower["bottomY"] + 4) % 3
        levels = list(range(
            tower["bottomY"] + 4,
            tower["bottomY"] + tower["height"] - 1,
            4,
        ))
        for floor_y in levels:
            rotation = (rotation + 2) % 4
            for lane_z in (tower["size"] - 2, tower["size"] - 3):
                for step in range(4):
                    x = tower["size"] - 3 - step
                    stair_y = floor_y - step
                    stair = self._block(
                        structure,
                        tuple(tower["center"]),
                        tower["size"],
                        x,
                        stair_y,
                        lane_z,
                        rotation,
                    )
                    self.assertEqual("minecraft:spruce_stairs", stair[0])
                    expected_states = self.tower_port._rotated_states(
                        self.tower_port._stair_states("west"),
                        rotation,
                    )
                    self.assertEqual(expected_states, stair[1])
                    for clear_x, clear_y in (
                        (x, stair_y + 1),
                        (x, stair_y + 2),
                        (x - 1, stair_y + 2),
                        (x, stair_y + 3),
                        (x - 1, stair_y + 3),
                    ):
                        headroom = self._block(
                            structure,
                            tuple(tower["center"]),
                            tower["size"],
                            clear_x,
                            clear_y,
                            lane_z,
                            rotation,
                        )
                        self.assertEqual("minecraft:air", headroom[0])

        # The source rotates once more and creates a final stair from the last
        # full landing onto the roof.  Omitting it makes the top inaccessible.
        roof_rotation = (rotation + 2) % 4
        roof_y = tower["bottomY"] + tower["height"] - 1
        roof_stair = self._block(
            structure,
            tuple(tower["center"]),
            tower["size"],
            tower["size"] - 3,
            roof_y,
            tower["size"] - 2,
            roof_rotation,
        )
        self.assertEqual("minecraft:spruce_stairs", roof_stair[0])

    def test_side_tower_bridges_use_the_source_top_opening_height(self):
        for seed in (0, 1):
            _structure, markers, _validation, _graph, _boss = (
                render_dark_tower(seed)
            )
            supports = [
                tower
                for tower in markers["wingTowers"]
                if "_support_" in tower["id"]
            ]
            self.assertEqual(8, len(supports))
            for tower in supports:
                center_x, center_z = tower["center"]
                radius = tower["size"] // 2
                touching = []
                for bridge in markers["bridges"]:
                    endpoints = (bridge["start"], bridge["end"])
                    if any(
                        (
                            abs(endpoint[0] - center_x) == radius
                            and endpoint[2] == center_z
                        )
                        or (
                            abs(endpoint[2] - center_z) == radius
                            and endpoint[0] == center_x
                        )
                        for endpoint in endpoints
                    ):
                        touching.append(bridge)
                self.assertGreaterEqual(len(touching), 2, (seed, tower))
                expected_y = tower["bottomY"] + tower["height"] - 5
                for bridge in touching:
                    self.assertEqual(
                        expected_y,
                        bridge["start"][1],
                        (seed, tower, bridge),
                    )
                    self.assertEqual(
                        expected_y,
                        bridge["end"][1],
                        (seed, tower, bridge),
                    )

    def test_integrated_builder_ladders_do_not_end_under_solid_landings(self):
        for seed in (0, 1):
            structure, _markers, _validation, _graph, _boss = (
                render_dark_tower(seed)
            )
            ladders = {
                position
                for position, block in structure.blocks.items()
                if block[0] == "minecraft:ladder"
            }
            for position in ladders:
                above = (position[0], position[1] + 1, position[2])
                if above in ladders:
                    continue
                self.assertIn(
                    structure.blocks.get(above, ("minecraft:air",))[0],
                    ("minecraft:air", "minecraft:cave_air"),
                    (seed, position, structure.blocks.get(above)),
                )

    def test_integrated_main_stair_flights_keep_their_top_tread_and_headroom(self):
        for seed in (0, 1):
            structure, markers, _validation, _graph, _boss = (
                render_dark_tower(seed)
            )
            zones = {
                zone["tower"]: zone
                for zone in markers["mainFloorZones"]
            }
            for tower in markers["mainTowers"]:
                zone = zones[tower["id"]]
                flights = [
                    (tower["bottomY"], tower["bottomY"] % 4)
                ]
                rotation = (tower["bottomY"] % 4 - 1) % 4
                for index, floor_y in enumerate(zone["lowerFloors"]):
                    if index < len(zone["lowerFloors"]) - 1:
                        flights.append((floor_y, rotation))
                    rotation = (rotation - 1) % 4
                rotation = zone["topFloorsStart"] % 4
                for index, floor_y in enumerate(zone["upperFloors"]):
                    if index < len(zone["upperFloors"]) - 1:
                        flights.append((floor_y, rotation))
                    rotation = (rotation - 1) % 4

                for floor_y, rotation in flights:
                    if (
                        tower["stage"] == 2
                        and floor_y + 5
                        == markers["bossPlatform"]["offset"][1]
                    ):
                        # The source intentionally lets the final tower's
                        # destruction bursts damage this last arena flight.
                        continue
                    for local_x in (1, 2):
                        top_x, top_z = self.tower_port._local(
                            tuple(tower["center"]),
                            tower["size"],
                            local_x,
                            9,
                            rotation,
                        )
                        top = (top_x, floor_y + 5, top_z)
                        self.assertEqual(
                            "minecraft:spruce_stairs",
                            structure.blocks.get(
                                top, ("minecraft:air",)
                            )[0],
                            (seed, tower["id"], floor_y, rotation, top),
                        )
                        for head_y in (floor_y + 6, floor_y + 7):
                            head = (top_x, head_y, top_z)
                            self.assertIn(
                                structure.blocks.get(
                                    head, ("minecraft:air",)
                                )[0],
                                ("minecraft:air", "minecraft:cave_air"),
                                (
                                    seed,
                                    tower["id"],
                                    floor_y,
                                    rotation,
                                    head,
                                ),
                            )

    def test_main_tower_floor_zones_match_source_without_overlap(self):
        for seed in (0, 1):
            _structure, markers, _validation, _graph, _boss = render_dark_tower(seed)
            zones = {value["tower"]: value for value in markers["mainFloorZones"]}
            for tower in markers["mainTowers"]:
                zone = zones[tower["id"]]
                ordinary = zone["lowerFloors"] + zone["upperFloors"]
                self.assertTrue(ordinary)
                self.assertTrue(all(
                    floor < zone["centerBottom"] or floor >= zone["topFloorsStart"]
                    for floor in ordinary
                ))
                self.assertTrue(all(
                    right - left == 5
                    for left, right in zip(zone["lowerFloors"], zone["lowerFloors"][1:])
                ))
                self.assertTrue(all(
                    right - left == 5
                    for left, right in zip(zone["upperFloors"], zone["upperFloors"][1:])
                ))
                self.assertEqual(tower["bottomY"] + 5, zone["lowerFloors"][0])
                self.assertIn(
                    zone["centerBottom"],
                    {
                        position[1]
                        for position, block in _structure.blocks.items()
                        if block[0] == "tf_slice:twilight_oak_log"
                    }
                    if zone["type"] == "timber_maze"
                    else {zone["centerBottom"]},
                )
                if zone["type"] == "builder_platforms":
                    for rotation in (1, 3):
                        for ladder_y in range(
                            zone["centerBottom"] - 4,
                            zone["centerBottom"],
                        ):
                            ladder = self._block(
                                _structure,
                                tuple(tower["center"]),
                                tower["size"],
                                1,
                                ladder_y,
                                5,
                                rotation,
                            )
                            self.assertEqual(
                                "minecraft:ladder",
                                ladder[0],
                                (tower["id"], rotation, ladder_y),
                            )

    def test_builder_high_room_top_ladder_opens_into_the_upper_room(self):
        for seed in (0, 1):
            structure, markers, _validation, _graph, _boss = (
                render_dark_tower(seed)
            )
            towers = {
                tower["id"]: tower for tower in markers["mainTowers"]
            }
            builder_zones = [
                zone
                for zone in markers["mainFloorZones"]
                if zone["type"] == "builder_platforms"
            ]
            self.assertTrue(builder_zones, seed)
            for zone in builder_zones:
                tower = towers[zone["tower"]]
                center = tuple(tower["center"])
                top = zone["topFloorsStart"]
                rotation = (top + 1) % 4

                for ladder_y in range(top - 4, top):
                    ladder = self._block(
                        structure,
                        center,
                        tower["size"],
                        6,
                        ladder_y,
                        10,
                        rotation,
                    )
                    self.assertEqual(
                        "minecraft:ladder",
                        ladder[0],
                        (seed, tower["id"], ladder_y),
                    )
                floor_opening = self._block(
                    structure,
                    center,
                    tower["size"],
                    6,
                    top,
                    10,
                    rotation,
                )
                self.assertIn(
                    floor_opening[0] if floor_opening else "minecraft:air",
                    ("minecraft:air", "minecraft:cave_air"),
                )
                exit_headroom = self._block(
                    structure,
                    center,
                    tower["size"],
                    6,
                    top + 1,
                    10,
                    rotation,
                )
                self.assertIn(
                    (
                        exit_headroom[0]
                        if exit_headroom else "minecraft:air"
                    ),
                    ("minecraft:air", "minecraft:cave_air"),
                    (seed, tower["id"], top + 1, exit_headroom),
                )
                support_headroom = self._block(
                    structure,
                    center,
                    tower["size"],
                    6,
                    top + 1,
                    9,
                    rotation,
                )
                self.assertIn(
                    (
                        support_headroom[0]
                        if support_headroom else "minecraft:air"
                    ),
                    ("minecraft:air", "minecraft:cave_air"),
                    (seed, tower["id"], top + 1, support_headroom),
                )
                for fence_x in (5, 7):
                    for fence_y in (top, top + 1):
                        fence = self._block(
                            structure,
                            center,
                            tower["size"],
                            fence_x,
                            fence_y,
                            10,
                            rotation,
                        )
                        self.assertEqual(
                            "minecraft:oak_fence",
                            fence[0],
                            (
                                seed,
                                tower["id"],
                                fence_x,
                                fence_y,
                            ),
                        )

    def test_timber_high_room_top_ladder_has_a_real_upper_floor_entry(self):
        for seed in (0, 1):
            structure, markers, _validation, _graph, _boss = (
                render_dark_tower(seed)
            )
            towers = {
                tower["id"]: tower for tower in markers["mainTowers"]
            }
            timber_zones = [
                zone
                for zone in markers["mainFloorZones"]
                if zone["type"] == "timber_maze"
            ]
            self.assertTrue(timber_zones, seed)
            for zone in timber_zones:
                tower = towers[zone["tower"]]
                center = tuple(tower["center"])
                top = zone["topFloorsStart"]
                rotation = (top + 1) % 4

                for ladder_y in range(top - 4, top):
                    ladder = self._block(
                        structure,
                        center,
                        tower["size"],
                        4,
                        ladder_y,
                        10,
                        rotation,
                    )
                    self.assertEqual(
                        "minecraft:ladder",
                        ladder[0],
                        (seed, tower["id"], ladder_y),
                    )
                for opening_y in (top, top + 1, top + 2):
                    opening = self._block(
                        structure,
                        center,
                        tower["size"],
                        4,
                        opening_y,
                        10,
                        rotation,
                    )
                    self.assertIn(
                        opening[0] if opening else "minecraft:air",
                        ("minecraft:air", "minecraft:cave_air"),
                        (seed, tower["id"], opening_y, opening),
                    )
                source_step = self._block(
                    structure,
                    center,
                    tower["size"],
                    4,
                    top,
                    9,
                    rotation,
                )
                self.assertNotIn(
                    source_step[0] if source_step else "minecraft:air",
                    (
                        "minecraft:air",
                        "minecraft:cave_air",
                        "minecraft:ladder",
                        "minecraft:oak_fence",
                    ),
                    (seed, tower["id"], source_step),
                )
                for head_y in (top + 1, top + 2):
                    headroom = self._block(
                        structure,
                        center,
                        tower["size"],
                        4,
                        head_y,
                        9,
                        rotation,
                    )
                    self.assertIn(
                        headroom[0] if headroom else "minecraft:air",
                        ("minecraft:air", "minecraft:cave_air"),
                        (seed, tower["id"], head_y, headroom),
                    )
                for fence_x in (3, 5):
                    for fence_y in (top, top + 1):
                        fence = self._block(
                            structure,
                            center,
                            tower["size"],
                            fence_x,
                            fence_y,
                            10,
                            rotation,
                        )
                        self.assertEqual(
                            "minecraft:oak_fence",
                            fence[0],
                            (
                                seed,
                                tower["id"],
                                fence_x,
                                fence_y,
                            ),
                        )

    def test_builder_high_room_top_ladder_uses_the_source_side_exit(self):
        for seed in (0, 1):
            structure, markers, _validation, _graph, _boss = (
                render_dark_tower(seed)
            )
            towers = {
                tower["id"]: tower for tower in markers["mainTowers"]
            }
            for zone in markers["mainFloorZones"]:
                if zone["type"] != "builder_platforms":
                    continue
                tower = towers[zone["tower"]]
                center = tuple(tower["center"])
                top = zone["topFloorsStart"]
                rotation = (top + 1) % 4
                ladder_top = self._block(
                    structure, center, tower["size"],
                    6, top - 1, 10, rotation,
                )
                self.assertEqual("minecraft:ladder", ladder_top[0])
                exit_cell = self._block(
                    structure, center, tower["size"],
                    6, top, 10, rotation,
                )
                self.assertIn(
                    exit_cell[0] if exit_cell else "minecraft:air",
                    ("minecraft:air", "minecraft:cave_air"),
                    (seed, tower["id"], exit_cell),
                )
                source_step = self._block(
                    structure, center, tower["size"],
                    6, top, 9, rotation,
                )
                self.assertEqual(
                    "tf_slice:encased_towerwood",
                    source_step[0],
                )
                for head_y in (top + 1, top + 2):
                    headroom = self._block(
                        structure, center, tower["size"],
                        6, head_y, 9, rotation,
                    )
                    self.assertIn(
                        headroom[0] if headroom else "minecraft:air",
                        ("minecraft:air", "minecraft:cave_air"),
                    )

                empty = ("minecraft:air", "minecraft:cave_air")
                non_support = empty + (
                    "minecraft:ladder",
                    "minecraft:oak_fence",
                )
                walkable = set()
                for local_x in range(1, 18):
                    for local_z in range(1, 18):
                        support = self._block(
                            structure, center, tower["size"],
                            local_x, top, local_z, rotation,
                        )
                        first = self._block(
                            structure, center, tower["size"],
                            local_x, top + 1, local_z, rotation,
                        )
                        second = self._block(
                            structure, center, tower["size"],
                            local_x, top + 2, local_z, rotation,
                        )
                        if (
                            (support[0] if support else "minecraft:air")
                            not in non_support
                            and (first[0] if first else "minecraft:air")
                            in empty
                            and (second[0] if second else "minecraft:air")
                            in empty
                        ):
                            walkable.add((local_x, local_z))
                reached = {(6, 9)}
                pending = [(6, 9)]
                while pending:
                    local_x, local_z = pending.pop()
                    for neighbor in (
                        (local_x - 1, local_z),
                        (local_x + 1, local_z),
                        (local_x, local_z - 1),
                        (local_x, local_z + 1),
                    ):
                        if neighbor in walkable and neighbor not in reached:
                            reached.add(neighbor)
                            pending.append(neighbor)
                self.assertGreaterEqual(
                    len(reached),
                    20,
                    (seed, tower["id"], sorted(reached)),
                )

    def test_all_authored_ladders_face_their_solid_backing(self):
        support_delta = {
            2: (0, 0, 1),
            3: (0, 0, -1),
            4: (1, 0, 0),
            5: (-1, 0, 0),
        }
        for seed in (0, 1):
            structure, _markers, _validation, _graph, _boss = render_dark_tower(seed)
            ladders = [
                (position, block)
                for position, block in structure.blocks.items()
                if block[0] == "minecraft:ladder"
            ]
            self.assertGreater(len(ladders), 50)
            for position, block in ladders:
                state = block[1]["facing_direction"]
                dx, dy, dz = support_delta[state]
                support = structure.blocks.get(
                    (position[0] + dx, position[1] + dy, position[2] + dz)
                )
                self.assertIsNotNone(support, (seed, position, state))
                self.assertNotIn(
                    support[0],
                    ("minecraft:air", "minecraft:ladder"),
                    (seed, position, state, support),
                )

    def test_all_levers_have_explicit_rotatable_attachment_states(self):
        valid_directions = {
            "down_east_west",
            "east",
            "west",
            "south",
            "north",
            "up_north_south",
            "up_east_west",
            "down_north_south",
        }
        # Bedrock lever_direction is the direction the wall lever faces; its
        # supporting block is behind it on the opposite cardinal side.  The
        # up/down variants identify a lever placed on top/bottom respectively.
        support_delta = {
            "east": (-1, 0, 0),
            "west": (1, 0, 0),
            "south": (0, 0, -1),
            "north": (0, 0, 1),
            "up_north_south": (0, -1, 0),
            "up_east_west": (0, -1, 0),
            "down_north_south": (0, 1, 0),
            "down_east_west": (0, 1, 0),
        }
        unsupported_blocks = {
            "minecraft:air",
            "minecraft:fire",
            "minecraft:lever",
            "minecraft:redstone_wire",
            "minecraft:water",
        }
        for seed in (0, 1):
            structure, _markers, _validation, _graph, _boss = render_dark_tower(seed)
            levers = [
                (position, block)
                for position, block in structure.blocks.items()
                if block[0] == "minecraft:lever"
            ]
            self.assertGreater(len(levers), 10)
            for position, block in levers:
                states = block[1]
                self.assertIn(states.get("lever_direction"), valid_directions)
                self.assertIs(states.get("open_bit"), False)
                delta = support_delta[states["lever_direction"]]
                support_position = tuple(
                    position[index] + delta[index] for index in range(3)
                )
                support = structure.blocks.get(support_position)
                self.assertIsNotNone(
                    support,
                    (seed, position, states["lever_direction"], support_position),
                )
                self.assertNotIn(
                    support[0],
                    unsupported_blocks,
                    (seed, position, states["lever_direction"], support),
                )

    def test_reactor_levers_use_authored_supports_without_synthetic_blocks(self):
        structure = self._structure((40, 20, 40))
        markers = {"rooms": [], "mechanisms": []}
        self.tower_port._decorate_reactor_room(
            structure,
            markers,
            "main",
            (20, 20),
            5,
            0,
        )

        levers = [
            (position, block)
            for position, block in structure.blocks.items()
            if block[0] == "minecraft:lever"
        ]
        self.assertEqual(6, len(levers))
        for position, block in levers:
            delta = self.tower_port.LEVER_SUPPORT_DELTAS[
                block[1]["lever_direction"]
            ]
            support_position = tuple(
                position[index] + delta[index] for index in range(3)
            )
            self.assertEqual(
                "tf_slice:encased_towerwood",
                (structure.blocks.get(support_position) or (None,))[0],
                (position, block[1]["lever_direction"], support_position),
            )

        authored_positions = set(structure.blocks)
        self.tower_port._restore_authored_lever_supports(structure)
        self.assertEqual(authored_positions, set(structure.blocks))

    def test_redstone_driven_tower_blocks_emit_neighbor_change_events(self):
        from tools import build_dark_tower_content as tower_content

        for identifier in (
            "vanishing_block",
            "unbreakable_vanishing_block",
            "reappearing_block",
            "carminite_builder",
            "carminite_reactor",
            "ghast_trap",
        ):
            components = tower_content.block_document(identifier)[
                "minecraft:block"
            ]["components"]
            self.assertEqual(
                {"value": True},
                components.get("netease:neighborchanged_sendto_script"),
                identifier,
            )

    def test_bomb_damage_never_materializes_netherrack_in_source_air(self):
        structure = self._structure((32, 32, 32))
        markers = {"bombedBreaches": []}

        self.tower_port._carve_bombed_breach(
            structure,
            markers,
            (16, 16),
            16,
            5,
            0,
        )

        self.assertEqual({}, structure.blocks)

    def test_upper_main_towers_have_source_beards_below_their_foundations(self):
        for seed in (0, 1):
            structure, markers, _validation, _graph, _boss = render_dark_tower(seed)
            for tower in markers["mainTowers"][1:]:
                center_x, center_z = tower["center"]
                for depth in range(1, 10):
                    block = structure.blocks.get(
                        (center_x, tower["bottomY"] - depth, center_z)
                    )
                    self.assertIsNotNone(block, (seed, tower["id"], depth))
                    self.assertEqual(
                        "tf_slice:encased_towerwood",
                        block[0],
                        (seed, tower["id"], depth, block),
                    )

    def test_tower_graph_never_uses_diagonal_or_bent_tower_bridges(self):
        for seed in (0, 1):
            _structure, markers, _validation, graph, _boss = render_dark_tower(seed)
            tower_centers = {
                tower["id"]: tuple(tower["center"])
                for tower in markers["mainTowers"] + markers["wingTowers"]
            }
            for first_id, second_id in graph:
                if first_id not in tower_centers or second_id not in tower_centers:
                    continue
                first = tower_centers[first_id]
                second = tower_centers[second_id]
                self.assertTrue(
                    first[0] == second[0] or first[1] == second[1],
                    (seed, first_id, first, second_id, second),
                )

    def test_main_room_markers_do_not_overlap_and_boss_upper_floors_are_reactors(self):
        for seed in (0, 1):
            _structure, markers, _validation, _graph, _boss = render_dark_tower(seed)
            declarations = Counter(
                (room["tower"], room["offset"][1]) for room in markers["rooms"]
            )
            self.assertFalse(
                [key for key, count in declarations.items() if count > 1],
                (seed, declarations),
            )
            boss_zone = next(
                zone for zone in markers["mainFloorZones"] if zone["tower"] == "main_2"
            )
            expected_reactors = set(boss_zone["upperFloors"][:-1])
            actual_reactors = {
                room["offset"][1]
                for room in markers["rooms"]
                if room["tower"] == "main_2" and room["type"] == "reactor_experiment"
            }
            self.assertEqual(expected_reactors, actual_reactors)

    def test_main_room_selector_matches_source_floor_branches_and_weights(self):
        select = self.tower_port._select_main_room_type
        self.assertEqual(
            ["aquarium", "botanical", "netherwart"],
            [select(roll, 100, is_top=True) for roll in range(3)],
        )
        self.assertEqual(
            ["aquarium", "botanical", "netherwart", "forge"],
            [select(roll, 100, is_bottom=True) for roll in range(4)],
        )
        self.assertEqual("forge", select(2, 60, is_bottom=True))
        self.assertEqual(
            [
                "reappearing_maze",
                "reappearing_maze",
                "antibuilder_maze",
                "aquarium",
                "botanical",
                "netherwart",
                "lounge",
                "forge",
            ],
            [select(roll, 100) for roll in range(8)],
        )
        self.assertEqual("lounge", select(5, 60))
        source = (ROOT / "tools" / "dark_tower_legacy_port.py").read_text(
            encoding="utf-8"
        )
        renderer = source[
            source.index("def _render_main_tower") :
            source.index("def _render_small_floor")
        ]
        self.assertNotIn("MAIN_ROOM_TYPES[", renderer)

    def test_boss_trap_towers_have_open_roofs_stairs_and_complete_redstone_trigger(self):
        for seed in (0, 1):
            structure, markers, _validation, _graph, _boss = render_dark_tower(seed)
            for tower in markers["bossTrapTowers"]:
                cx, cz = tower["center"]
                bottom = tower["bottomY"]
                radius = tower["size"] // 2
                local_blocks = {
                    position: block
                    for position, block in structure.blocks.items()
                    if abs(position[0] - cx) <= radius
                    and abs(position[2] - cz) <= radius
                    and bottom <= position[1] < bottom + tower["height"]
                }
                palette = Counter(block[0] for block in local_blocks.values())
                self.assertEqual(1, palette["tf_slice:ghast_trap"])
                self.assertGreaterEqual(palette["minecraft:redstone_wire"], 5)
                self.assertGreaterEqual(palette["minecraft:wooden_pressure_plate"], 1)
                # The component authors two double-wide roof/bottom stair runs
                # before its random destruction pass.  A heavily damaged trap
                # tower may lose an entire run, but any surviving tread must
                # still belong to one of those source-authored flights rather
                # than an extra opposed staircase.
                rotation = int(tower["id"].rsplit("_", 1)[1])
                middle_y = bottom + 4
                top_y = bottom + tower["height"] - 1
                authored_stairs = set()
                for stair_rotation, stair_y in (
                    ((rotation + 3) % 4, middle_y),
                    ((rotation + 1) % 4, top_y),
                ):
                    for lane_z in (tower["size"] - 2, tower["size"] - 3):
                        for step in range(4):
                            world_x, world_z = self.tower_port._local(
                                tuple(tower["center"]),
                                tower["size"],
                                tower["size"] - 3 - step,
                                lane_z,
                                stair_rotation,
                            )
                            authored_stairs.add(
                                (world_x, stair_y - step, world_z)
                            )
                surviving_stairs = {
                    position
                    for position, block in local_blocks.items()
                    if block[0] == "minecraft:spruce_stairs"
                }
                self.assertTrue(
                    surviving_stairs.issubset(authored_stairs),
                    (seed, tower["id"], surviving_stairs - authored_stairs),
                )
                roof_y = bottom + tower["height"] - 1
                roof_solid = sum(
                    1
                    for x in range(cx - radius + 1, cx + radius)
                    for z in range(cz - radius + 1, cz + radius)
                    if structure.blocks.get((x, roof_y, z), ("minecraft:air",))[0]
                    != "minecraft:air"
                )
                self.assertLess(
                    roof_solid, (tower["size"] - 2) ** 2 * 3 // 4
                )

    def test_boss_trap_stairs_use_source_rotations_and_connect_to_landings(self):
        from unittest import mock

        for rotation in range(4):
            structure = self._structure((96, 96, 96))
            tower = {
                "id": "boss_trap_rotation_%d" % rotation,
                "stage": 2,
                "center": [40, 40],
                "bottomY": 20,
                "height": 9,
                "size": 11,
            }
            markers = {
                "rooms": [],
                "bombedBreaches": [],
                "ghastTraps": [],
            }
            with mock.patch.object(
                self.tower_port,
                "_carve_bombed_breach",
            ):
                self.tower_port._render_boss_trap_tower(
                    structure,
                    markers,
                    tower,
                    rotation,
                    17,
                )

            middle_y = tower["bottomY"] + 4
            top_y = tower["bottomY"] + tower["height"] - 1
            source_flights = (
                ((rotation + 3) % 4, middle_y),
                ((rotation + 1) % 4, top_y),
            )
            expected_stairs = set()
            for stair_rotation, stair_y in source_flights:
                for lane_z in (tower["size"] - 2, tower["size"] - 3):
                    for step in range(4):
                        world_x, world_z = self.tower_port._local(
                            tuple(tower["center"]),
                            tower["size"],
                            tower["size"] - 3 - step,
                            lane_z,
                            stair_rotation,
                        )
                        expected_stairs.add(
                            (world_x, stair_y - step, world_z)
                        )
            actual_stairs = {
                position
                for position, block in structure.blocks.items()
                if block[0] == "minecraft:spruce_stairs"
            }
            self.assertEqual(expected_stairs, actual_stairs, rotation)

            roof_rotation = (rotation + 1) % 4
            for lane_z in (tower["size"] - 2, tower["size"] - 3):
                # The high side of the top tread joins the authored top shell.
                roof_landing = self._block(
                    structure,
                    tuple(tower["center"]),
                    tower["size"],
                    tower["size"] - 2,
                    top_y,
                    lane_z,
                    roof_rotation,
                )
                self.assertIsNotNone(roof_landing, (rotation, lane_z))
                self.assertNotIn(
                    roof_landing[0],
                    ("minecraft:air", "minecraft:cave_air"),
                )

                # The low side of the bottom tread joins the middle full floor.
                floor_landing = self._block(
                    structure,
                    tuple(tower["center"]),
                    tower["size"],
                    tower["size"] - 7,
                    middle_y,
                    lane_z,
                    roof_rotation,
                )
                self.assertIsNotNone(floor_landing, (rotation, lane_z))
                self.assertNotIn(
                    floor_landing[0],
                    ("minecraft:air", "minecraft:cave_air"),
                )

    def test_boss_trap_destruction_centers_rotate_with_each_side_tower(self):
        from unittest import mock

        structure = self._structure((96, 96, 96))
        tower = {
            "id": "boss_trap_rotation_test",
            "stage": 2,
            "center": [40, 40],
            "bottomY": 20,
            "height": 9,
            "size": 11,
        }
        markers = {
            "rooms": [],
            "bombedBreaches": [],
            "ghastTraps": [],
        }
        rotation = 1
        calls = []

        def capture_breach(_structure, _markers, center, y, radius, salt):
            calls.append((tuple(center), y, radius, salt))

        with mock.patch.object(
            self.tower_port,
            "_carve_bombed_breach",
            side_effect=capture_breach,
        ):
            self.tower_port._render_boss_trap_tower(
                structure,
                markers,
                tower,
                rotation,
                17,
            )

        expected = []
        for local_x, local_y, local_z, amount, salt in (
            (5, tower["height"] + 2, 5, 4, 0),
            (0, tower["height"], 0, 3, 1),
            (0, tower["height"], 8, 4, 2),
            (5, 6, 5, 2, 3),
        ):
            world_x, world_z = self.tower_port._local(
                tuple(tower["center"]),
                tower["size"],
                local_x,
                local_z,
                rotation,
            )
            radius = amount + ((17 + salt * 17) % amount)
            expected.append(
                (
                    (world_x, world_z),
                    tower["bottomY"] + local_y,
                    radius,
                    17 + salt,
                )
            )
        self.assertEqual(expected, calls)

    def test_boss_trap_roof_stairs_are_not_redrawn_after_destruction(self):
        source = (ROOT / "tools" / "dark_tower_legacy_port.py").read_text(
            encoding="utf-8"
        )
        renderer = source[
            source.index("def _render_boss_trap_tower") :
            source.index("def _carve_bombed_breach")
        ]

        self.assertEqual(2, renderer.count("_render_small_stairs_down("))
        self.assertLess(
            renderer.rindex("_render_small_stairs_down("),
            renderer.index("for local_x, local_y, local_z"),
        )

    def test_connection_rejects_diagonal_tower_centers(self):
        structure = self._structure((80, 80, 80))
        with self.assertRaises(ValueError):
            self.tower_port._render_connection(
                structure, (20, 20), 19, (50, 35), 11, 30
            )

    def test_bridge_connection_opens_matching_three_high_doors_at_both_ends(self):
        structure = self._structure((80, 80, 80))
        first_center = (20, 20)
        second_center = (50, 20)
        self.tower_port._render_encased_shell(
            structure, first_center, 19, 10, 60, 1
        )
        self.tower_port._render_encased_shell(
            structure, second_center, 11, 30, 25, 2
        )
        segments = self.tower_port._render_connection(
            structure,
            first_center,
            19,
            second_center,
            11,
            30,
        )
        self.assertTrue(segments)
        start = tuple(segments[0]["start"])
        end = tuple(segments[-1]["end"])
        self.assertEqual(30, start[1])
        self.assertEqual(30, end[1])
        for wall_x, wall_z in ((start[0], start[2]), (end[0], end[2])):
            for across in range(-1, 2):
                for door_y in range(31, 34):
                    block = structure.blocks[(wall_x, door_y, wall_z + across)]
                    self.assertEqual(
                        "tf_slice:unbreakable_vanishing_block",
                        block[0],
                    )

    def test_reappearing_floor_is_a_pressure_plate_crossing_not_a_solid_room(self):
        structure = self._structure()
        tower = {"id": "small", "center": [20, 20], "size": 9}
        markers = {"rooms": [], "structureSpawners": [], "lootChests": []}
        api = {
            "set_spawner": self.ruin_builder.set_spawner,
            "set_loot_container": self.ruin_builder.set_loot_container,
        }
        self.tower_port._decorate_small_room(
            structure, markers, api, tower, "reappearing_floor", 12, 0
        )
        reappearing = [
            position
            for position, block in structure.blocks.items()
            if block[0] == "tf_slice:reappearing_block"
        ]
        plates = [
            position
            for position, block in structure.blocks.items()
            if block[0] == "minecraft:wooden_pressure_plate"
        ]
        self.assertEqual(12, len(reappearing))
        self.assertEqual({12}, {position[1] for position in reappearing})
        self.assertEqual(8, len(plates))
        self.assertEqual({13}, {position[1] for position in plates})

    def test_small_room_devices_and_furniture_have_the_source_working_parts(self):
        expected = {
            "lounge": {
                "minecraft:spruce_stairs",
                "minecraft:spruce_slab",
            },
            "library": {
                "minecraft:spruce_stairs",
                "minecraft:bookshelf",
            },
            "piston_pulser": {
                "minecraft:sticky_piston",
                "minecraft:unpowered_repeater",
                "minecraft:redstone_wire",
                "minecraft:wooden_pressure_plate",
            },
            "lamp_experiment": {
                "minecraft:sticky_piston",
                "minecraft:redstone_lamp",
                "minecraft:lever",
            },
            "puzzle_chest": {
                "minecraft:sticky_piston",
                "minecraft:lever",
                "minecraft:chest",
            },
        }
        tower = {"id": "small", "center": [20, 20], "size": 11}
        api = {
            "set_spawner": self.ruin_builder.set_spawner,
            "set_loot_container": self.ruin_builder.set_loot_container,
        }
        for room_type, required_blocks in expected.items():
            structure = self._structure()
            markers = {
                "rooms": [],
                "structureSpawners": [],
                "lootChests": [],
            }
            self.tower_port._decorate_small_room(
                structure, markers, api, tower, room_type, 12, 0
            )
            palette = {block[0] for block in structure.blocks.values()}
            self.assertTrue(
                required_blocks.issubset(palette),
                (room_type, sorted(required_blocks - palette)),
            )

    def test_main_reappearing_maze_uses_sparse_doors_in_structural_walls(self):
        structure = self._structure()
        markers = {"rooms": [], "lootChests": [], "mechanisms": []}
        api = {
            "set_spawner": self.ruin_builder.set_spawner,
            "set_loot_container": self.ruin_builder.set_loot_container,
        }
        self.tower_port._decorate_main_room(
            structure,
            markers,
            api,
            "main",
            "reappearing_maze",
            (24, 24),
            10,
            0,
        )
        palette = Counter(block[0] for block in structure.blocks.values())
        structural_walls = (
            palette["tf_slice:towerwood"]
            + palette["tf_slice:encased_towerwood"]
        )
        self.assertGreater(structural_walls, palette["tf_slice:reappearing_block"])
        self.assertGreater(palette["tf_slice:reappearing_block"], 0)
        self.assertGreaterEqual(len(markers["lootChests"]), 2)

    def test_antibuilder_maze_keeps_the_source_staggered_machine_heights(self):
        structure = self._structure()
        markers = {"rooms": [], "lootChests": [], "mechanisms": []}
        api = {
            "set_spawner": self.ruin_builder.set_spawner,
            "set_loot_container": self.ruin_builder.set_loot_container,
        }
        center = (24, 24)
        floor_y = 10
        self.tower_port._decorate_main_room(
            structure,
            markers,
            api,
            "main",
            "antibuilder_maze",
            center,
            floor_y,
            0,
        )
        expected = {
            (15, floor_y + 2, 7),
            (11, floor_y + 3, 7),
            (15, floor_y + 2, 13),
            (11, floor_y + 3, 13),
            (5, floor_y + 3, 13),
        }
        actual = {
            (local_x, block_y, local_z)
            for local_x in range(19)
            for block_y in range(floor_y + 1, floor_y + 5)
            for local_z in range(19)
            if (
                self._block(
                    structure, center, 19,
                    local_x, block_y, local_z, 0,
                )
                or (None,)
            )[0] == "tf_slice:carminite_antibuilder"
        }
        self.assertEqual(expected, actual)

    def test_main_lounge_and_forge_restore_source_furniture_shapes(self):
        api = {
            "set_spawner": self.ruin_builder.set_spawner,
            "set_loot_container": self.ruin_builder.set_loot_container,
        }
        expected = {
            "lounge": {
                "minecraft:spruce_stairs",
                "minecraft:dispenser",
                "minecraft:brewing_stand",
                "minecraft:cauldron",
                "minecraft:bookshelf",
                "minecraft:redstone_lamp",
                "minecraft:lever",
            },
            "forge": {
                "minecraft:spruce_stairs",
                "minecraft:furnace",
                "minecraft:anvil",
                "minecraft:netherrack",
                "minecraft:fire",
            },
        }
        for room_type, required in expected.items():
            structure = self._structure()
            markers = {"rooms": [], "lootChests": [], "mechanisms": []}
            self.tower_port._decorate_main_room(
                structure,
                markers,
                api,
                "main",
                room_type,
                (24, 24),
                10,
                0,
            )
            palette = {block[0] for block in structure.blocks.values()}
            self.assertTrue(
                required.issubset(palette),
                (room_type, sorted(required - palette)),
            )

    def test_main_lounge_restores_the_source_tree_planter_and_canopy(self):
        structure = self._structure()
        markers = {"rooms": [], "lootChests": [], "mechanisms": []}
        api = {
            "set_spawner": self.ruin_builder.set_spawner,
            "set_loot_container": self.ruin_builder.set_loot_container,
        }
        center = (24, 24)
        floor_y = 10
        self.tower_port._decorate_main_room(
            structure,
            markers,
            api,
            "main",
            "lounge",
            center,
            floor_y,
            0,
        )

        self.assertEqual(
            "minecraft:coarse_dirt",
            self._block(
                structure, center, 19, 6, floor_y + 1, 12, 0
            )[0],
        )
        rim = {
            self._block(
                structure, center, 19, local_x, floor_y + 1, local_z, 0
            )[0]
            for local_x, local_z in (
                (5, 11),
                (5, 12),
                (5, 13),
                (6, 11),
                (6, 13),
                (7, 11),
                (7, 12),
                (7, 13),
            )
        }
        self.assertIn("tf_slice:encased_towerwood", rim)
        self.assertIn("minecraft:spruce_stairs", rim)

        leaf_positions = {
            (local_x, block_y, local_z)
            for local_x in range(3, 10)
            for block_y in range(floor_y + 2, floor_y + 9)
            for local_z in range(9, 16)
            if (
                self._block(
                    structure,
                    center,
                    19,
                    local_x,
                    block_y,
                    local_z,
                    0,
                )
                or ("minecraft:air",)
            )[0].endswith("_leaves")
        }
        self.assertGreaterEqual(len(leaf_positions), 25)
        self.assertGreaterEqual(
            len({position[1] for position in leaf_positions}),
            3,
        )
        self.assertGreaterEqual(
            max(position[1] for position in leaf_positions),
            floor_y + 6,
        )

    def test_source_height_planter_tree_grows_through_a_floor_opening(self):
        structure = self._structure()
        center = (24, 24)
        floor_y = 10
        opening = {
            self.tower_port._local(center, 19, local_x, local_z, 0)
            for local_x in range(4, 9)
            for local_z in range(10, 15)
        }
        for local_x in range(1, 18):
            for local_z in range(1, 18):
                x, z = self.tower_port._local(
                    center,
                    19,
                    local_x,
                    local_z,
                    0,
                )
                if (x, z) not in opening:
                    structure.set(
                        x,
                        floor_y + 5,
                        z,
                        "tf_slice:towerwood",
                    )

        self.tower_port._render_tree_planter(
            structure,
            "main",
            center,
            floor_y,
            0,
        )

        tree_blocks_above_floor = [
            (position, block)
            for position, block in structure.blocks.items()
            if position[1] > floor_y + 5
            and (
                block[0].endswith("_leaves")
                or block[0].endswith("_log")
            )
        ]
        self.assertGreater(len(tree_blocks_above_floor), 0)
        for x, z in opening:
            self.assertNotEqual(
                "tf_slice:towerwood",
                structure.blocks.get((x, floor_y + 5, z), (None,))[0],
            )
        self.assertEqual(
            "tf_slice:towerwood",
            structure.blocks[(
                self.tower_port._local(center, 19, 1, 1, 0)[0],
                floor_y + 5,
                self.tower_port._local(center, 19, 1, 1, 0)[1],
            )][0],
        )

    def test_compiled_planters_are_full_trees_or_empty_not_cut_stumps(self):
        leaf_names = {
            profile[1]
            for profile in self.tower_port.PLANTER_TREE_PROFILES
        }
        log_names = {
            profile[0]
            for profile in self.tower_port.PLANTER_TREE_PROFILES
        }
        full_tree_count = 0
        planter_count = 0
        for layout_seed, decoration_seed in ((0, 0), (1, 1), (1, 0), (0, 1)):
            structure, _markers, _validation, _graph, _boss = (
                render_dark_tower(
                    layout_seed,
                    decoration_seed=decoration_seed,
                )
            )
            planter_positions = [
                position
                for position, block in structure.blocks.items()
                if block[0] == "minecraft:coarse_dirt"
            ]
            planter_count += len(planter_positions)
            for root_x, soil_y, root_z in planter_positions:
                nearby = [
                    (position, block[0])
                    for position, block in structure.blocks.items()
                    if abs(position[0] - root_x) <= 2
                    and soil_y < position[1] <= soil_y + 10
                    and abs(position[2] - root_z) <= 2
                    and block[0] in leaf_names | log_names
                ]
                if not nearby:
                    continue
                trunk_y = []
                for block_y in range(soil_y + 1, soil_y + 9):
                    block_name = structure.blocks.get(
                        (root_x, block_y, root_z),
                        (None,),
                    )[0]
                    if block_name in log_names:
                        trunk_y.append(block_y)
                    elif trunk_y:
                        break
                leaf_y = {
                    position[1]
                    for position, block_name in nearby
                    if block_name in leaf_names
                    and trunk_y
                    and trunk_y[-1] - 1
                    <= position[1]
                    <= trunk_y[-1] + 1
                }
                self.assertGreaterEqual(len(trunk_y), 3)
                self.assertEqual(
                    list(range(trunk_y[0], trunk_y[-1] + 1)),
                    trunk_y,
                )
                self.assertGreaterEqual(len(leaf_y), 3)
                full_tree_count += 1
        self.assertGreater(planter_count, 0)
        self.assertGreater(full_tree_count, 0)

    def test_botanical_room_uses_the_same_protected_full_tree_planter(self):
        structure = self._structure()
        markers = {"rooms": [], "lootChests": [], "mechanisms": []}
        api = {
            "set_spawner": self.ruin_builder.set_spawner,
            "set_loot_container": self.ruin_builder.set_loot_container,
        }
        center = (24, 24)
        floor_y = 10
        self.tower_port._decorate_main_room(
            structure,
            markers,
            api,
            "main",
            "botanical",
            center,
            floor_y,
            0,
        )
        self.assertEqual(
            "minecraft:coarse_dirt",
            self._block(
                structure, center, 19, 6, floor_y + 1, 12, 0
            )[0],
        )
        leaf_count = sum(
            1
            for block in structure.blocks.values()
            if block[0].endswith("_leaves")
        )
        self.assertGreaterEqual(leaf_count, 25)

    def test_low_tower_cleanup_mask_contains_only_authored_interior_air(self):
        structure = self._structure()
        marker = {
            "id": "ground_tower",
            "center": [20, 20],
            "bottomY": 16,
            "height": 50,
            "size": 9,
        }
        authored_leaf = (20, 24, 20)
        structure.set(
            authored_leaf[0],
            authored_leaf[1],
            authored_leaf[2],
            "tf_slice:twilight_oak_leaves",
        )
        positions = self.tower_port.dark_tower_canopy_cleanup_positions(
            structure,
            {"mainTowers": [marker], "wingTowers": []},
            surface_ground_y=16,
        )

        self.assertGreater(len(positions), 0)
        self.assertEqual(
            "tf_slice:twilight_oak_leaves",
            structure.blocks[authored_leaf][0],
        )
        self.assertNotIn(authored_leaf, positions)
        self.assertIn((21, 24, 20), positions)
        self.assertNotIn((25, 24, 20), positions)
        self.assertNotIn((21, 61, 20), positions)

        for path in (
            TOOLS / "dark_tower_legacy_port.py",
            TOOLS / "build_phantom_urghast_structures.py",
        ):
            self.assertNotIn(
                "tower_interior_guard",
                path.read_text(encoding="utf-8"),
            )
        from tools import build_dark_tower_content as tower_content

        self.assertNotIn(
            "tower_interior_guard",
            tower_content.BLOCK_TEXTURES,
        )

    def test_canopy_cleanup_mask_compresses_to_reversible_vertical_runs(self):
        for seed in (0, 1):
            for decoration_seed in (0, 1):
                structure, markers, _validation, _graph, _boss = (
                    render_dark_tower(seed, decoration_seed)
                )
                positions = self.tower_port.dark_tower_canopy_cleanup_positions(
                    structure,
                    markers,
                    structure.surface_ground_y,
                )
                runs = self.tower_port.dark_tower_canopy_cleanup_runs(
                    positions
                )
                decoded = set()
                for x, z, minimum_y, maximum_y in runs:
                    self.assertLessEqual(minimum_y, maximum_y)
                    self.assertGreaterEqual(
                        minimum_y, int(structure.surface_ground_y) + 1
                    )
                    self.assertLessEqual(
                        maximum_y,
                        int(structure.surface_ground_y)
                        + self.tower_port.DARK_FOREST_CANOPY_CLEANUP_HEIGHT,
                    )
                    for y in range(minimum_y, maximum_y + 1):
                        decoded.add((x, y, z))
                self.assertEqual(positions, decoded)
                self.assertLess(len(runs), len(positions) // 4)

    def test_ground_towers_have_hidden_tree_root_shields(self):
        from tools import dark_tower_legacy_port as tower_port

        for seed in (0, 1):
            for decoration_seed in (0, 1):
                structure, markers, _validation, _graph, _boss = (
                    render_dark_tower(seed, decoration_seed)
                )
                ground_y = int(structure.surface_ground_y)
                expected_columns = set()
                for tower in markers["mainTowers"] + markers["wingTowers"]:
                    if int(tower["bottomY"]) > ground_y:
                        continue
                    center_x, center_z = [
                        int(value) for value in tower["center"]
                    ]
                    radius = int(tower["size"]) // 2
                    for x in range(center_x - radius + 1, center_x + radius):
                        for z in range(
                            center_z - radius + 1,
                            center_z + radius,
                        ):
                            expected_columns.add((x, z))

                marker = markers["treeRootShield"]
                self.assertEqual(len(expected_columns), marker["columns"])
                self.assertEqual(0, marker["minimumY"])
                self.assertEqual(ground_y, marker["maximumY"])
                self.assertEqual(
                    len(expected_columns) * (ground_y + 1),
                    marker["blocks"],
                )
                forbidden_root_blocks = {
                    "minecraft:air",
                    "minecraft:cave_air",
                    "minecraft:void_air",
                    "minecraft:grass",
                    "minecraft:grass_block",
                    "minecraft:dirt",
                    "minecraft:podzol",
                }
                for x, z in expected_columns:
                    for y in range(0, ground_y + 1):
                        self.assertNotIn(
                            structure.blocks[(x, y, z)][0],
                            forbidden_root_blocks,
                            (seed, decoration_seed, x, y, z),
                        )

                shield_positions = {
                    (x, y, z)
                    for x, z in expected_columns
                    for y in range(0, ground_y + 1)
                }
                self.assertEqual(
                    shield_positions,
                    tower_port.dark_tower_tree_root_shield_positions(
                        markers,
                        ground_y,
                        structure_minimum_y=0,
                    ),
                )

                elevated = next(
                    tower
                    for tower in markers["wingTowers"]
                    if int(tower["bottomY"]) > ground_y
                    and tuple(tower["center"])
                    not in expected_columns
                )
                elevated_center = tuple(
                    int(value) for value in elevated["center"]
                )
                self.assertNotIn(
                    (elevated_center[0], 0, elevated_center[1]),
                    shield_positions,
                )

    def test_remaining_main_rooms_use_source_frames_and_functional_contents(self):
        api = {
            "set_spawner": self.ruin_builder.set_spawner,
            "set_loot_container": self.ruin_builder.set_loot_container,
        }
        expected = {
            "bottom_entrance": {
                "minecraft:spruce_stairs",
                "minecraft:netherrack",
                "minecraft:fire",
            },
            "aquarium": {
                "minecraft:spruce_stairs",
                "minecraft:water",
            },
            "botanical": {
                "minecraft:spruce_stairs",
                "minecraft:spruce_slab",
                "minecraft:flower_pot",
                "minecraft:crafting_table",
                "minecraft:chest",
            },
            "netherwart": {
                "minecraft:spruce_stairs",
                "minecraft:soul_sand",
                "minecraft:nether_wart",
                "minecraft:mob_spawner",
            },
        }
        for room_type, required in expected.items():
            structure = self._structure()
            markers = {
                "rooms": [],
                "lootChests": [],
                "mechanisms": [],
                "structureSpawners": [],
            }
            self.tower_port._decorate_main_room(
                structure,
                markers,
                api,
                "main",
                room_type,
                (24, 24),
                10,
                0,
            )
            palette = {block[0] for block in structure.blocks.values()}
            self.assertTrue(
                required.issubset(palette),
                (room_type, sorted(required - palette)),
            )

    def test_antibuilder_maze_has_pillars_and_two_block_passages(self):
        structure = self._structure()
        markers = {"rooms": [], "lootChests": [], "mechanisms": []}
        api = {
            "set_spawner": self.ruin_builder.set_spawner,
            "set_loot_container": self.ruin_builder.set_loot_container,
        }
        self.tower_port._decorate_main_room(
            structure,
            markers,
            api,
            "main",
            "antibuilder_maze",
            (24, 24),
            10,
            0,
        )
        palette = Counter(block[0] for block in structure.blocks.values())
        self.assertGreater(palette["tf_slice:encased_towerwood"], 0)
        self.assertGreaterEqual(palette["minecraft:air"], 12)


class DarkTowerContentContractTests(unittest.TestCase):
    def test_retired_tower_guard_has_a_focused_resource_cleanup(self):
        from unittest import mock

        from tools import build_dark_tower_content as tower_content

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            behavior = root / "TwilightBossSliceB"
            resource = root / "TwilightBossSliceR"
            (resource / "textures").mkdir(parents=True)
            (resource / "textures" / "terrain_texture.json").write_text(
                json.dumps({"texture_data": {}}),
                encoding="utf-8",
            )
            (resource / "blocks.json").write_text(
                json.dumps(
                    {
                        "tf_slice:tower_interior_guard": {
                            "textures": "tf_slice:tower_interior_guard"
                        }
                    }
                ),
                encoding="utf-8",
            )
            guard_block = (
                behavior / "netease_blocks" / "tower_interior_guard.json"
            )
            guard_block.parent.mkdir(parents=True)
            guard_block.write_text("{}", encoding="utf-8")
            guard_texture = (
                resource
                / "textures"
                / "blocks"
                / "tower_interior_guard.png"
            )
            guard_texture.parent.mkdir(parents=True)
            guard_texture.write_bytes(b"retired")
            terrain_path = resource / "textures" / "terrain_texture.json"
            terrain_path.write_text(
                json.dumps(
                    {
                        "texture_data": {
                            "tf_slice:tower_interior_guard": {
                                "textures": (
                                    "textures/blocks/tower_interior_guard"
                                )
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with (
                mock.patch.object(tower_content, "ROOT", root),
                mock.patch.object(tower_content, "BP", behavior),
                mock.patch.object(tower_content, "RP", resource),
            ):
                result = tower_content.remove_tower_interior_guard_resources()

            self.assertEqual(4, len(result["files"]))
            self.assertFalse(guard_block.exists())
            self.assertFalse(guard_texture.exists())
            terrain = json.loads(
                terrain_path.read_text(encoding="utf-8")
            )
            self.assertNotIn(
                "tf_slice:tower_interior_guard",
                terrain["texture_data"],
            )
            legacy = json.loads(
                (resource / "blocks.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("tf_slice:tower_interior_guard", legacy)

    def test_runtime_selects_the_matching_variant_cleanup_tile(self):
        from TwilightBossSlice import ruin_worldgen_logic
        from tests import test_structure_worldgen_handoff as handoff

        service = handoff.SERVICE

        cleanup = {
            "prefix": (
                "tf_slice/ruins/dark_tower_canopy_cleanup/seed_1"
            ),
            "centerAlignments": {"8,8": [-3, -3, 3, 3]},
        }

        class FakeService(object):
            def _surface_native_tile(
                self,
                _mode,
                _chunk_x,
                _chunk_z,
                _event_y,
            ):
                return (
                    "unused",
                    {
                        "kind": "dark_tower",
                        "variant": 1,
                        "surfaceTile": [2, -1],
                    },
                )

            def _entry_for_landmark(self, _kind):
                return {
                    "variants": [
                        {"canopyCleanup": {}},
                        {"canopyCleanup": cleanup},
                    ]
                }

        reference = service.StructureWorldgenService._dark_tower_canopy_cleanup_tile(
            FakeService(),
            34,
            -17,
            70,
        )
        self.assertEqual(
            ruin_worldgen_logic.surface_native_tile_reference(
                cleanup["prefix"],
                "8,8",
                2,
                -1,
            ),
            reference,
        )
        source = (
            PACKAGE / "structureWorldgenService.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "DARK_TOWER_CANOPY_CLEANUP_TRIGGER_STRUCTURE",
            source,
        )

    def test_builder_resources_expose_source_active_timeout_and_built_states(self):
        from tools import build_dark_tower_content as tower_content

        builder = tower_content.block_document("carminite_builder")[
            "minecraft:block"
        ]
        self.assertEqual(
            ["inactive", "active", "timeout"],
            builder["description"]["states"]["tf_slice:builder_state"],
        )
        builder_permutations = {
            value["condition"]: value["components"][
                "minecraft:material_instances"
            ]["*"]["texture"]
            for value in builder["permutations"]
        }
        self.assertEqual(
            "tf_slice:carminite_builder_active",
            builder_permutations[
                "query.block_state('tf_slice:builder_state') == 'active'"
            ],
        )
        self.assertEqual(
            "tf_slice:carminite_builder_timeout",
            builder_permutations[
                "query.block_state('tf_slice:builder_state') == 'timeout'"
            ],
        )

        built = tower_content.block_document("temporary_builder_block")[
            "minecraft:block"
        ]
        self.assertIs(
            built["description"]["register_to_creative_menu"], False
        )
        self.assertEqual(
            [False, True],
            built["description"]["states"]["tf_slice:active"],
        )
        self.assertEqual(
            "blend",
            built["components"]["minecraft:material_instances"]["*"][
                "render_method"
            ],
        )
        self.assertEqual(
            "tf_slice:temporary_builder_block_active",
            built["permutations"][0]["components"][
                "minecraft:material_instances"
            ]["*"]["texture"],
        )

    def test_builder_resource_files_match_the_locked_source_textures(self):
        upstream = (
            ROOT.parent
            / "twilightforest-1.20.1-4.3.2508-extracted"
            / "00_original_tree"
            / "assets"
            / "twilightforest"
            / "textures"
            / "block"
        )
        expected = {
            "carminite_builder_active.png": "towerdev_builder_on.png",
            "carminite_builder_timeout.png": "towerdev_builder_timeout.png",
            "temporary_builder_block.png": "towerdev_built_off.png",
            "temporary_builder_block_active.png": "towerdev_built_on.png",
        }
        for target_name, source_name in expected.items():
            target = BP.parent / "TwilightBossSliceR" / "textures" / "blocks" / target_name
            self.assertTrue(target.is_file(), target_name)
            self.assertEqual(
                hashlib.sha256((upstream / source_name).read_bytes()).hexdigest(),
                hashlib.sha256(target.read_bytes()).hexdigest(),
                target_name,
            )

        terrain = json.loads(
            (
                BP.parent
                / "TwilightBossSliceR"
                / "textures"
                / "terrain_texture.json"
            ).read_text(encoding="utf-8")
        )["texture_data"]
        for identifier in (
            "carminite_builder_active",
            "carminite_builder_timeout",
            "temporary_builder_block_active",
        ):
            self.assertIn("tf_slice:" + identifier, terrain)

    def test_key_door_uses_the_locked_source_lock_texture(self):
        from tools import build_dark_tower_content as tower_content

        self.assertEqual(
            "block/towerdev_lock_on.png",
            tower_content.BLOCK_TEXTURES["tower_key_door"],
        )
        document = tower_content.block_document("tower_key_door")[
            "minecraft:block"
        ]
        self.assertEqual(
            [True, False],
            document["description"]["states"]["tf_slice:locked"],
        )
        unlocked = next(
            value
            for value in document["permutations"]
            if "tf_slice:locked" in value["condition"]
        )
        self.assertEqual(
            "tf_slice:tower_key_door_unlocked",
            unlocked["components"]["minecraft:material_instances"]["*"][
                "texture"
            ],
        )

    def test_dark_forest_center_tree_rule_has_no_spatial_clearance(self):
        from tools import build_dark_forest_content as dark_forest

        iterations = dark_forest.dark_forest_tree_rule_iterations(
            "dark_forest_center"
        )
        self.assertEqual(
            dark_forest.SAFE_DARK_FOREST_TREE_ATTEMPTS,
            iterations,
        )
        source = (TOOLS / "build_dark_forest_content.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("DARK_TOWER_TREE_ROOT_CLEARANCE", source)
        self.assertNotIn("radius_squared", source)
        tree_profile = source[
            source.index("def build_tree_profile") :
            source.index("def remove_legacy_dark_forest_canopy")
        ]
        self.assertIn(
            "dark_forest_tree_rule_iterations(",
            tree_profile,
        )

    def test_tower_model_registry_preserves_the_latest_review_state(self):
        registry = json.loads(
            (ROOT / "model_acceptance" / "registry.json").read_text(
                encoding="utf-8"
            )
        )
        entries = {entry["id"]: entry for entry in registry["entities"]}
        identifiers = {
            "carminite_golem",
            "tower_broodling",
            "mini_ghast",
            "tower_ghast",
            "towerwood_borer",
            "ur_ghast",
        }
        self.assertTrue(identifiers.issubset(entries))
        for identifier in identifiers:
            entry = entries[identifier]
            self.assertEqual(
                (
                    "rejected"
                    if identifier
                    in (
                        "tower_broodling",
                        "mini_ghast",
                        "tower_ghast",
                        "ur_ghast",
                    )
                    else "candidate"
                ),
                entry["status"],
            )
            self.assertEqual(
                "model_acceptance/offline/%s.json" % identifier,
                entry["offline_evidence"],
            )
            self.assertEqual(
                "model_acceptance/evidence/%s.json" % identifier,
                entry["evidence"],
            )
            client = json.loads(
                (BP.parent / "TwilightBossSliceR" / "entity" / (identifier + ".entity.json")).read_text(
                    encoding="utf-8"
                )
            )
            geometry = client["minecraft:client_entity"]["description"]["geometry"]["default"]
            self.assertEqual(
                (
                    "geometry.spider.v1.8"
                    if identifier == "tower_broodling"
                    else "geometry.tf_slice.%s" % identifier
                ),
                geometry,
            )

    def test_required_blocks_items_and_mobs_exist(self):
        blocks = {
            "towerwood", "cracked_towerwood", "mossy_towerwood", "infested_towerwood",
            "encased_towerwood", "vanishing_block", "unbreakable_vanishing_block",
            "locked_vanishing_block", "reappearing_block", "carminite_builder",
            "carminite_antibuilder", "temporary_builder_block", "restored_block",
            "carminite_reactor", "reactor_debris", "fake_gold", "fake_diamond",
            "ghast_trap", "carminite_block", "experiment_115", "tower_key_door",
            "ur_ghast_boss_spawner",
        }
        for name in blocks:
            self.assertTrue((BP / "netease_blocks" / (name + ".json")).is_file(), name)
        for name in ("tower_key", "carminite", "fiery_tears", "charm_of_life_1"):
            self.assertTrue((BP / "items" / (name + ".item.json")).is_file(), name)
        expected_health = {
            "carminite_golem": 40,
            "tower_broodling": 7,
            "mini_ghast": 10,
            "tower_ghast": 30,
            "towerwood_borer": 15,
            "ur_ghast": 250,
        }
        for name, health in expected_health.items():
            document = json.loads((BP / "entities" / (name + ".entity.json")).read_text(encoding="utf-8"))
            self.assertEqual(health, document["minecraft:entity"]["components"]["minecraft:health"]["max"])

    def test_route_blocks_and_items_are_exposed_in_the_creative_catalog(self):
        catalog = json.loads(
            (BP / "item_catalog" / "crafting_item_catalog.json").read_text(
                encoding="utf-8"
            )
        )
        items = {
            identifier
            for category in catalog["minecraft:crafting_items_catalog"]["categories"]
            for group in category.get("groups", [])
            for identifier in group.get("items", [])
        }
        for name in {
            "tower_key", "carminite", "fiery_tears", "charm_of_life_1",
            "ur_ghast_trophy", "ur_ghast_banner",
            "towerwood", "cracked_towerwood", "mossy_towerwood", "infested_towerwood",
            "encased_towerwood", "vanishing_block", "unbreakable_vanishing_block",
            "locked_vanishing_block", "reappearing_block", "carminite_builder",
            "carminite_antibuilder", "carminite_reactor", "ghast_trap",
            "carminite_block", "experiment_115",
        }:
            self.assertIn("tf_slice:" + name, items)

    def test_ur_ghast_marker_uses_the_same_atomic_cleanup_path(self):
        source = (PACKAGE / "structureWorldgenService.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'UR_GHAST_SPAWNER_BLOCK = "tf_slice:ur_ghast_boss_spawner"',
            source,
        )
        cleanup = source[source.index("def _remove_courtyard_marker_at"):]
        cleanup = cleanup[:cleanup.index("def _courtyard_expected_marker_position")]
        self.assertIn("UR_GHAST_SPAWNER_BLOCK", cleanup)

    def test_model_evidence_cannot_skip_the_offline_preview_gate(self):
        evidence = json.loads(
            (ROOT / "evidence" / "models" / "dark_tower_route.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("rejected", evidence["status"])
        self.assertFalse(evidence["offlineEvidenceComplete"])
        self.assertFalse(evidence["clientAccepted"])
        self.assertFalse(evidence["runtimeVerified"])
        for model in evidence["models"]:
            self.assertEqual(
                (
                    "rejected"
                    if model["identifier"] in (
                        "tf_slice:mini_ghast",
                        "tf_slice:tower_ghast",
                        "tf_slice:tower_broodling",
                        "tf_slice:ur_ghast",
                    )
                    else "candidate"
                ),
                model["status"],
            )
            self.assertEqual(
                ["front", "back", "left", "right", "top", "three_quarter"],
                model["requiredViews"],
            )
            self.assertEqual(
                ["rest", "walk_extreme", "look_up", "look_down"],
                model["requiredPoses"],
            )
            self.assertIn("offlineEvidence", model)


class DarkTowerMechanismLogicTests(unittest.TestCase):
    def test_builder_activates_only_on_a_redstone_rising_edge(self):
        import dark_tower_logic as logic

        self.assertFalse(logic.should_activate_builder(False, False))
        self.assertTrue(logic.should_activate_builder(False, True))
        self.assertFalse(logic.should_activate_builder(True, True))
        self.assertFalse(logic.should_activate_builder(True, False))

    def test_only_authored_dark_tower_levers_bypass_the_route_guard(self):
        import dark_tower_logic as logic

        self.assertTrue(
            logic.is_authored_dark_tower_lever(
                "minecraft:lever", "dark_tower"
            )
        )
        self.assertFalse(
            logic.is_authored_dark_tower_lever(
                "minecraft:lever", "knight_stronghold"
            )
        )
        self.assertFalse(
            logic.is_authored_dark_tower_lever(
                "tf_slice:carminite_builder", "dark_tower"
            )
        )

    def test_lever_bypass_and_builder_power_polling_are_wired(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        handler = source[source.index("    def OnServerBlockUseEvent(self, args):") :]
        handler = handler[: handler.index("    def OnEntityInsideBlock")]
        self.assertLess(
            handler.index("self._allow_dark_tower_lever_use(args)"),
            handler.index("self._protect_locked_route_landmark"),
        )

        ticker = source[
            source.index("    def _tick_dark_tower_block_entity") :
            source.index("    def _apply_reactor_event")
        ]
        self.assertIn('"tf_slice:carminite_builder"', ticker)
        self.assertIn("advance_builder", ticker)
        self.assertIn("complete_builder_placement", ticker)
        self.assertIn("_dark_tower_builder_powered", ticker)
        power_helper = source[
            source.index("    def _dark_tower_builder_powered") :
            source.index("    def _tick_dark_tower_block_entity")
        ]
        self.assertIn("_fire_swamp_device_powered", power_helper)

        direct_use = source[
            source.index("    def _use_dark_tower_mechanism") :
            source.index("    def _allow_dark_tower_lever_use")
        ]
        self.assertNotIn(
            'if blockName == "tf_slice:carminite_builder"', direct_use
        )
        neighbor = source[source.index("    def OnBlockNeighborChanged") :]
        self.assertNotIn("_use_dark_tower_mechanism(synthetic)", neighbor)

    def test_builder_uses_the_nearest_players_look_direction(self):
        import dark_tower_logic as logic

        self.assertEqual((0, 1, 0), logic.builder_facing_from_rotation(-70, 0))
        self.assertEqual((0, -1, 0), logic.builder_facing_from_rotation(70, 0))
        self.assertEqual((0, 0, 1), logic.builder_facing_from_rotation(0, 0))
        self.assertEqual((-1, 0, 0), logic.builder_facing_from_rotation(0, 90))
        self.assertEqual((0, 0, -1), logic.builder_facing_from_rotation(0, 180))
        self.assertEqual((1, 0, 0), logic.builder_facing_from_rotation(0, -90))

    def test_builder_waits_then_tracks_the_players_live_look_direction(self):
        import dark_tower_logic as logic

        state = logic.create_builder_state((0, 64, 0))
        started = logic.advance_builder(state, True, (0, -1, 0))
        self.assertEqual("started", started["kind"])
        self.assertEqual(0, state["blocksMade"])

        for _unused in range(logic.BUILDER_STEP_TICKS - 1):
            self.assertIsNone(
                logic.advance_builder(state, True, (0, -1, 0))
            )

        first = logic.advance_builder(state, True, (1, 0, 0))
        self.assertEqual(
            {"kind": "place", "position": (1, 64, 0)},
            first,
        )
        self.assertTrue(
            logic.complete_builder_placement(
                state, first["position"], succeeded=True
            )
        )

        for _unused in range(logic.BUILDER_STEP_TICKS - 1):
            self.assertIsNone(
                logic.advance_builder(state, True, (1, 0, 0))
            )
        second = logic.advance_builder(state, True, (0, 0, 1))
        self.assertEqual(
            {"kind": "place", "position": (1, 64, 1)},
            second,
        )

    def test_builder_keeps_the_full_source_path_then_cleans_from_the_origin(self):
        import dark_tower_logic as logic

        state = logic.create_builder_state((0, 64, 0))
        logic.advance_builder(state, True, (1, 0, 0))
        for index in range(17):
            for _unused in range(logic.BUILDER_STEP_TICKS - 1):
                self.assertIsNone(
                    logic.advance_builder(state, True, (1, 0, 0))
                )
            step = logic.advance_builder(state, True, (1, 0, 0))
            self.assertEqual((index + 1, 64, 0), step["position"])
            self.assertTrue(
                logic.complete_builder_placement(
                    state,
                    step["position"],
                    succeeded=True,
                    restore_block="minecraft:air",
                )
            )
        self.assertEqual(17, state["blocksMade"])
        self.assertEqual("building", state["phase"])

        for _unused in range(logic.BUILDER_STEP_TICKS - 1):
            self.assertIsNone(
                logic.advance_builder(state, True, (1, 0, 0))
            )
        waiting = logic.advance_builder(state, True, (1, 0, 0))
        self.assertEqual("waiting_cleanup", waiting["kind"])
        self.assertEqual("waiting_cleanup", state["phase"])

        for _unused in range(logic.BUILDER_STOP_DELAY_TICKS - 1):
            self.assertIsNone(
                logic.advance_builder(state, True, (1, 0, 0))
            )
        cleanup = logic.advance_builder(state, True, (1, 0, 0))
        self.assertEqual(
            {"kind": "cleanup_started", "builderState": "timeout"},
            cleanup,
        )

        for _unused in range(logic.BUILDER_REMOVE_STEP_TICKS - 1):
            self.assertIsNone(
                logic.advance_builder(state, True, (1, 0, 0))
            )
        removal = logic.advance_builder(state, True, (1, 0, 0))
        self.assertEqual(
            {
                "kind": "remove",
                "position": (1, 64, 0),
                "restoreBlock": "minecraft:air",
            },
            removal,
        )
        self.assertTrue(
            logic.complete_builder_removal(
                state, removal["position"], succeeded=True
            )
        )

    def test_builder_power_loss_starts_cleanup_without_waiting(self):
        import dark_tower_logic as logic

        state = logic.create_builder_state((0, 64, 0))
        logic.advance_builder(state, True, (1, 0, 0))
        for _unused in range(logic.BUILDER_STEP_TICKS - 1):
            logic.advance_builder(state, True, (1, 0, 0))
        step = logic.advance_builder(state, True, (1, 0, 0))
        logic.complete_builder_placement(
            state,
            step["position"],
            succeeded=True,
            restore_block="minecraft:air",
        )

        stopped = logic.advance_builder(state, False, (1, 0, 0))
        self.assertEqual(
            {"kind": "cleanup_started", "builderState": "inactive"},
            stopped,
        )
        self.assertEqual("cleaning", state["phase"])

    def test_idle_builder_power_probes_are_neighbor_driven_and_bounded(self):
        import dark_tower_logic as logic

        state = logic.create_builder_state((0, 64, 0))
        self.assertTrue(logic.builder_power_probe_due(state))
        for _unused in range(logic.BUILDER_IDLE_POWER_POLL_TICKS - 1):
            self.assertFalse(logic.builder_power_probe_due(state))
        self.assertTrue(logic.builder_power_probe_due(state))
        self.assertTrue(
            logic.builder_power_probe_due(state, neighbor_changed=True)
        )

    def test_runtime_uses_compact_builder_paths_and_antibuilder_player_gate(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        ticker = source[
            source.index("    def _tick_dark_tower_block_entity") :
            source.index("    def _apply_reactor_event")
        ]
        builder = ticker[
            ticker.index('if blockName == "tf_slice:carminite_builder"') :
            ticker.index('if blockName == "tf_slice:ghast_trap"')
        ]
        self.assertNotIn('"kind": "temporary"', builder)
        self.assertNotIn('"restoreTick": self._tick + 200', builder)
        self.assertIn("builder_power_probe_due", builder)
        self.assertIn("complete_builder_removal", builder)
        self.assertIn("_set_builder_block_state", builder)
        self.assertIn('"stopped"', builder)

        antibuilder = ticker[
            ticker.index('if blockName == "tf_slice:carminite_antibuilder"') :
            ticker.index('if blockName == "tf_slice:carminite_reactor"')
        ]
        self.assertLess(
            antibuilder.index("_nearest_player"),
            antibuilder.index("_capture_antibuilder_snapshot"),
        )
        self.assertIn("_dark_tower_mechanisms.pop", antibuilder)

        neighbor = source[source.index("    def OnBlockNeighborChanged") :]
        self.assertIn('"tf_slice:carminite_builder"', neighbor)
        self.assertIn("_builderNeighborChanged", neighbor)
        self.assertIn("_tick_dark_tower_block_entity", neighbor)

    def test_antibuilder_snapshots_are_runtime_only_not_globally_persisted(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        persistence = source[
            source.index("    def _load_dark_tower_runtime") :
            source.index("    def _dark_tower_event_position")
        ]
        self.assertIn("_persistent_dark_tower_mechanisms", persistence)
        self.assertIn('record.get("kind") == "antibuilder"', persistence)

        ticker = source[
            source.index("    def _tick_dark_tower_block_entity") :
            source.index("    def _apply_reactor_event")
        ]
        antibuilder = ticker[
            ticker.index('if blockName == "tf_slice:carminite_antibuilder"') :
            ticker.index('if blockName == "tf_slice:carminite_reactor"')
        ]
        self.assertNotIn("_save_dark_tower_runtime", antibuilder)

    def test_antibuilder_uses_the_locked_source_ignore_tag_and_random_restore(self):
        import dark_tower_logic as logic

        source_ignore_blocks = {
            "minecraft:redstone_lamp",
            "minecraft:tnt",
            "minecraft:water",
            "tf_slice:carminite_antibuilder",
            "tf_slice:carminite_builder",
            "tf_slice:temporary_builder_block",
            "tf_slice:reactor_debris",
            "tf_slice:carminite_reactor",
            "tf_slice:reappearing_block",
            "tf_slice:ghast_trap",
            "tf_slice:fake_diamond",
            "tf_slice:fake_gold",
            "tf_slice:ur_ghast_boss_spawner",
            "tf_slice:stronghold_shield",
            "tf_slice:unbreakable_vanishing_block",
        }
        self.assertTrue(
            source_ignore_blocks.issubset(logic.ANTIBUILDER_IGNORED_BLOCKS)
        )

        snapshot = {
            (0, 0, 0): "minecraft:air",
            (1, 0, 0): "tf_slice:temporary_builder_block",
            (2, 0, 0): "minecraft:stone",
            (3, 0, 0): "minecraft:stone",
        }
        current = {
            (0, 0, 0): "tf_slice:temporary_builder_block",
            (1, 0, 0): "minecraft:stone",
            (2, 0, 0): "minecraft:dirt",
            (3, 0, 0): "minecraft:dirt",
        }
        self.assertEqual(
            [{"position": (2, 0, 0), "block": "minecraft:stone"}],
            logic.antibuilder_changes(
                snapshot,
                current,
                roll_for=lambda position: 0 if position == (2, 0, 0) else 1,
            ),
        )

    def test_antibuilder_scan_reports_mismatches_before_random_restore_hits(self):
        import dark_tower_logic as logic

        snapshot = {
            (0, 0, 0): "minecraft:stone",
            (1, 0, 0): "minecraft:air",
        }
        current = {
            (0, 0, 0): "minecraft:dirt",
            (1, 0, 0): "tf_slice:temporary_builder_block",
        }
        missed = logic.antibuilder_scan(
            snapshot,
            current,
            roll_for=lambda _position: 1,
        )
        self.assertTrue(missed["hasRevertableDifferences"])
        self.assertEqual([], missed["changes"])
        self.assertEqual(
            {(1, 0, 0): "tf_slice:temporary_builder_block"},
            missed["snapshotUpdates"],
        )

        hit = logic.antibuilder_scan(
            snapshot,
            current,
            roll_for=lambda _position: 0,
        )
        self.assertEqual(
            [{"position": (0, 0, 0), "block": "minecraft:stone"}],
            hit["changes"],
        )

    def test_runtime_delegates_antibuilder_restores_to_the_pure_filter(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        ticker = source[
            source.index("    def _tick_dark_tower_block_entity") :
            source.index("    def _apply_reactor_event")
        ]
        antibuilder = ticker[
            ticker.index('if blockName == "tf_slice:carminite_antibuilder"') :
            ticker.index('if blockName == "tf_slice:carminite_reactor"')
        ]
        self.assertIn("dark_tower_logic.antibuilder_scan", antibuilder)
        self.assertIn('record["slowScan"]', antibuilder)
        self.assertIn('record["ticksSinceChange"]', antibuilder)
        self.assertNotIn(
            "for positionKey, expected in sorted(record[\"snapshot\"].items())",
            antibuilder,
        )

    def test_ghast_death_position_falls_back_to_the_last_live_sample(self):
        import ur_ghast_logic as logic

        self.assertEqual(
            (1.0, 2.0, 3.0),
            logic.resolve_death_position((1, 2, 3), (7, 8, 9)),
        )
        self.assertEqual(
            (7.0, 8.0, 9.0),
            logic.resolve_death_position(None, (7, 8, 9)),
        )

    def test_mini_ghast_death_identity_survives_actor_removal(self):
        import ur_ghast_logic as logic

        tracked = {"type": "tf_slice:mini_ghast"}
        self.assertEqual(
            "tf_slice:mini_ghast",
            logic.resolve_death_entity_type(None, None, tracked),
        )

        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        death = source[source.index("    def OnMobDie") :]
        self.assertIn("resolve_death_entity_type", death)
        self.assertLess(
            death.index("self._phantom_urghast_mobs.get"),
            death.index("if entityType == MINI_GHAST_IDENTIFIER"),
        )

    def test_active_trap_pulls_and_damages_non_boss_tower_ghasts(self):
        import ur_ghast_logic as logic

        trap = logic.create_trap_state((0, 64, 0))
        trap["active"] = True
        event = logic.apply_active_trap_to_ghast(
            trap, (3, 80, 2), deal_damage=True
        )
        self.assertTrue(event["affected"])
        self.assertNotEqual((0.0, 0.0, 0.0), event["motion"])
        self.assertEqual(logic.TRAP_OTHER_GHAST_DAMAGE, event["damage"])

        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        driver = source[
            source.index("    def _drive_phantom_urghast_mobs") :
            source.index("    def _drive_knight_phantoms")
        ]
        self.assertIn('state["lastPosition"]', driver)
        self.assertIn("apply_active_trap_to_ghast", driver)
        death = source[source.index("    def OnMobDie") :]
        self.assertIn('state.get("lastPosition")', death)

    def test_ghast_trap_charge_and_beam_have_client_feedback(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        self.assertIn('"GhastTrapEffect"', server)
        self.assertIn("record_mini_ghast_death_for_traps", server)
        self.assertIn('trap, "charge", deathPos', server)
        self.assertIn('_broadcast_ghast_trap_effect(trap, stage)', server)
        self.assertIn('"GhastTrapEffect"', client)
        self.assertIn("def OnGhastTrapEffect", client)

    def test_active_trap_scans_loaded_ghasts_outside_registration_cache(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        updater = source[
            source.index("    def _update_ghast_traps") :
            source.index("    def _active_ghast_trap")
        ]
        self.assertIn("_apply_active_trap_to_loaded_ghasts", updater)

        scanner = source[
            source.index("    def _apply_active_trap_to_loaded_ghasts") :
            source.index("    def _update_ghast_traps")
        ]
        self.assertIn("GetEntitiesInSquareArea", scanner)
        self.assertIn("TOWER_GHAST_IDENTIFIER", scanner)
        self.assertIn("MINI_GHAST_IDENTIFIER", scanner)
        self.assertIn("apply_active_trap_to_ghast", scanner)

    def test_builder_and_antibuilder_emit_client_feedback(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        self.assertIn('"DarkTowerMechanismEffect"', server)
        self.assertIn('"DarkTowerMechanismEffect"', client)
        self.assertIn("def OnDarkTowerMechanismEffect", client)

    def test_connected_reappearing_wall_activates_as_one_bounded_wave(self):
        import dark_tower_logic as logic

        blocks = {
            (x, 64, z): "tf_slice:reappearing_block"
            for x in range(3)
            for z in range(3)
        }
        blocks[(8, 64, 8)] = "tf_slice:reappearing_block"
        component = logic.connected_block_component(
            blocks,
            (1, 64, 1),
            {"tf_slice:reappearing_block"},
        )
        self.assertEqual(9, len(component))
        self.assertNotIn((8, 64, 8), component)
        self.assertEqual(512, logic.VANISHING_CHAIN_LIMIT)
        self.assertEqual(80, logic.REAPPEARING_RED_TRACE_TICKS)
        self.assertEqual(15, logic.REAPPEARING_GREEN_TRACE_TICKS)
        self.assertEqual(95, logic.REAPPEARING_RESTORE_TICKS)

    def test_reappearing_component_propagates_then_restores_each_block_after_its_wave(self):
        import dark_tower_logic as logic

        component = [(0, 64, 0), (1, 64, 0), (2, 64, 0), (3, 64, 0)]
        records = logic.build_reappearing_wave(
            component, (0, 64, 0), current_tick=100
        )
        vanish_ticks = [records[position]["vanishTick"] for position in component]
        self.assertEqual(sorted(vanish_ticks), vanish_ticks)
        self.assertGreater(len(set(vanish_ticks)), 1)
        for position in component:
            record = records[position]
            self.assertEqual(
                logic.REAPPEARING_RESTORE_TICKS,
                record["restoreTick"] - record["vanishTick"],
            )
            self.assertEqual(
                logic.REAPPEARING_RED_TRACE_TICKS,
                record["traceActiveTick"] - record["vanishTick"],
            )
            self.assertEqual(
                logic.REAPPEARING_GREEN_TRACE_TICKS,
                record["restoreTick"] - record["traceActiveTick"],
            )
            self.assertEqual("pending_vanish", record["phase"])

    def test_reappearing_runtime_keeps_red_then_green_trace_states(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        updater = source[
            source.index("    def _update_dark_tower_mechanisms") :
            source.index("    def _set_ghast_trap_active_state")
        ]
        self.assertIn("_set_reappearing_visual_state", updater)
        self.assertIn('record["phase"] = "vanished_trace"', updater)
        self.assertIn('record["phase"] = "active_trace"', updater)
        self.assertIn('"traceActiveTick"', updater)
        self.assertIn("False, True", updater)
        self.assertIn("True, True", updater)
        self.assertIn("False, False", updater)

    def test_reappearing_generator_builds_source_trace_geometry_and_states(self):
        import build_dark_tower_content as content

        block = content.block_document("reappearing_block")["minecraft:block"]
        permutations = {
            permutation["condition"]: permutation["components"]
            for permutation in block["permutations"]
        }
        encoded = json.dumps(permutations, sort_keys=True)
        self.assertIn("tf_slice:reappearing_block_active", encoded)
        self.assertIn("tf_slice:reappearing_trace_off", encoded)
        self.assertIn("tf_slice:reappearing_trace_on", encoded)
        self.assertIn("geometry.tf_slice.reappearing_trace", encoded)
        vanished = [
            components
            for condition, components in permutations.items()
            if "vanished') == true" in condition
        ]
        self.assertEqual(2, len(vanished))
        for components in vanished:
            self.assertIs(
                components["minecraft:collision_box"], False
            )
            self.assertFalse(components["netease:solid"]["value"])
            self.assertTrue(components["netease:pathable"]["value"])

        geometry = content.reappearing_trace_geometry_document()
        cube = geometry["minecraft:geometry"][0]["bones"][0]["cubes"][0]
        self.assertEqual([-2, 6, -2], cube["origin"])
        self.assertEqual([4, 4, 4], cube["size"])

    def test_reappearing_only_generator_limits_the_generated_write_set(self):
        import build_dark_tower_content as content

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bp = root / "behavior"
            rp = root / "resource"
            upstream = root / "upstream"
            (rp / "textures").mkdir(parents=True)
            (upstream / "textures" / "block").mkdir(parents=True)
            (rp / "textures" / "terrain_texture.json").write_text(
                json.dumps({"texture_data": {}}), encoding="utf-8"
            )
            (rp / "blocks.json").write_text("{}", encoding="utf-8")
            for name in (
                "towerdev_reappearing_off.png",
                "towerdev_reappearing_on.png",
                "towerdev_reappearing_trace_off.png",
                "towerdev_reappearing_trace_on.png",
            ):
                (upstream / "textures" / "block" / name).write_bytes(
                    name.encode("ascii")
                )
            original = (content.BP, content.RP, content.UPSTREAM)
            try:
                content.BP = bp
                content.RP = rp
                content.UPSTREAM = upstream
                result = content.build_reappearing_block_resources()
            finally:
                content.BP, content.RP, content.UPSTREAM = original

            expected = {
                bp / "netease_blocks" / "reappearing_block.json",
                rp / "textures" / "blocks" / "reappearing_block.png",
                rp / "textures" / "blocks" / "reappearing_block_active.png",
                rp / "textures" / "blocks" / "reappearing_trace_off.png",
                rp / "textures" / "blocks" / "reappearing_trace_on.png",
                rp / "textures" / "terrain_texture.json",
                rp / "blocks.json",
                rp / "models" / "blocks" / "reappearing_trace.geo.json",
            }
            self.assertEqual(expected, {Path(path) for path in result["files"]})

    def test_permanent_vanishing_component_uses_the_same_staggered_neighbor_wave(self):
        import dark_tower_logic as logic

        component = [(x, 64, 0) for x in range(5)]
        records = logic.build_vanishing_wave(
            component, (0, 64, 0), current_tick=200
        )
        vanish_ticks = [records[position]["vanishTick"] for position in component]
        self.assertGreaterEqual(vanish_ticks[0] - 200, 2)
        self.assertLessEqual(vanish_ticks[0] - 200, 6)
        for previous, current in zip(vanish_ticks, vanish_ticks[1:]):
            self.assertGreaterEqual(current - previous, 2)
            self.assertLessEqual(current - previous, 6)
        self.assertEqual(5, len(set(vanish_ticks)))
        for record in records.values():
            self.assertEqual("vanishing", record["kind"])
            self.assertEqual("pending_vanish", record["phase"])
            self.assertNotIn("restoreTick", record)

    def test_key_door_center_cannot_bypass_remaining_corner_locks(self):
        import dark_tower_logic as logic

        names = {
            (0, 0, 0): "tf_slice:unbreakable_vanishing_block",
            (1, 0, 0): "tf_slice:tower_key_door",
        }
        self.assertTrue(logic.has_locked_door_blocks(names.values()))
        self.assertFalse(logic.has_locked_door_blocks((names[(0, 0, 0)],)))

        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        activation = source[
            source.index("    def _activate_dark_tower_vanishing") :
            source.index("    def _use_dark_tower_mechanism")
        ]
        self.assertIn("_tower_key_lock_is_locked", activation)
        self.assertIn("if doorLocked:", activation)

    def test_reappearing_restore_retries_failed_world_writes(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        updater = source[
            source.index("    def _update_dark_tower_mechanisms") :
            source.index("    def _mount_goblin_knight")
        ]
        self.assertIn('phase == "pending_vanish"', updater)
        self.assertIn("writeSucceeded", updater)
        self.assertIn("if not writeSucceeded", updater)

    def test_ghast_trap_uses_redstone_neighbor_updates_before_route_protection(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        neighbor = source[source.index("    def OnBlockNeighborChanged") :]
        self.assertIn('"tf_slice:ghast_trap"', neighbor)
        self.assertIn("self._activate_ghast_trap", neighbor)

        handler = source[source.index("    def OnServerBlockUseEvent") :]
        handler = handler[: handler.index("    def OnEntityInsideBlock")]
        self.assertLess(
            handler.index("self._activate_ghast_trap(args)"),
            handler.index("self._protect_locked_route_landmark"),
        )

    def test_tower_key_door_is_not_mineable_or_explodable(self):
        document = json.loads(
            (BP / "netease_blocks" / "tower_key_door.json").read_text(encoding="utf-8")
        )
        components = document["minecraft:block"]["components"]
        self.assertIs(components["minecraft:destructible_by_mining"], False)
        self.assertIs(components["minecraft:destructible_by_explosion"], False)

    def test_tower_mechanisms_run_before_landmark_interaction_protection(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        handler = source[source.index("    def OnServerBlockUseEvent(self, args):") :]
        handler = handler[: handler.index("    def OnEntityInsideBlock")]
        self.assertLess(
            handler.index("self._use_dark_tower_mechanism(args)"),
            handler.index("self._protect_locked_route_landmark"),
        )
        mechanism = source[
            source.index("    def _dark_tower_connected_mechanism_blocks") :
        ]
        mechanism = mechanism[: mechanism.index("    def _activate_stronghold_pedestal")]
        self.assertIn("connected_block_component", mechanism)
        self.assertIn("build_vanishing_wave", mechanism)
        self.assertIn("build_reappearing_wave", mechanism)

    def test_locked_main_door_consumes_four_keys_before_opening(self):
        import dark_tower_logic as logic

        keys = 4
        locks = 4
        for expected_locks in (3, 2, 1, 0):
            result = logic.unlock_key_door(keys, locks)
            self.assertTrue(result["unlocked"])
            self.assertEqual(expected_locks, result["remainingLocks"])
            self.assertEqual(expected_locks == 0, result["doorOpened"])
            keys = result["remainingKeys"]
            locks = result["remainingLocks"]
        self.assertEqual(0, keys)

    def test_key_door_unlocks_states_then_schedules_the_whole_network(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        mechanism = source[
            source.index("    def _use_dark_tower_mechanism") :
            source.index("    def _allow_dark_tower_lever_use")
        ]
        self.assertIn("_tower_key_lock_is_locked", mechanism)
        self.assertIn("_set_tower_key_lock_state", mechanism)
        self.assertIn("_schedule_unlocked_key_door_open", mechanism)
        self.assertIn('itemName == "tf_slice:tower_key"', mechanism)
        self.assertNotIn(
            'self._set_block(target, "minecraft:air", dimensionId)',
            mechanism,
        )

    def test_builder_and_antibuilder_bounds(self):
        import dark_tower_logic as logic

        path = logic.builder_path((0, 0, 0), (1, 0, 0))
        self.assertEqual(17, len(path))
        self.assertEqual((17, 0, 0), path[-1])
        snapshot = logic.antibuilder_snapshot_positions((0, 0, 0))
        self.assertEqual(729, len(snapshot))
        self.assertIn((-4, -4, -4), snapshot)
        self.assertIn((4, 4, 4), snapshot)

    def test_builder_power_probes_include_the_support_and_adjacent_blocks(self):
        import dark_tower_logic as logic

        self.assertEqual(
            {
                (10, 20, 30),
                (9, 20, 30),
                (11, 20, 30),
                (10, 19, 30),
                (10, 21, 30),
                (10, 20, 29),
                (10, 20, 31),
            },
            set(logic.builder_power_probe_positions((10, 20, 30))),
        )
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        ticker = source[
            source.index("    def _tick_dark_tower_block_entity") :
            source.index("    def _apply_reactor_event")
        ]
        self.assertIn("_dark_tower_builder_powered", ticker)

    def test_reactor_experiment_and_life_charm_state(self):
        import dark_tower_logic as logic

        reactor = logic.create_reactor_state((0, 64, 0))
        events = []
        for _ in range(logic.REACTOR_TOTAL_TICKS):
            events.extend(logic.advance_reactor(reactor, 1))
        self.assertTrue(reactor["exploded"])
        self.assertIn("explode", [event["kind"] for event in events])
        cake = logic.create_experiment_115_state()
        for _ in range(8):
            logic.eat_experiment_115(cake)
        self.assertEqual(0, cake["servings"])
        self.assertTrue(logic.redstone_regenerate_experiment_115(cake))
        self.assertEqual(8, cake["servings"])
        fatal = logic.consume_life_charm_1(0, 20, True)
        self.assertEqual(8, fatal["health"])
        self.assertEqual(100, fatal["regenerationTicks"])
        self.assertTrue(fatal["consumed"])

    def test_reactor_fake_ore_shell_matches_the_source_26_block_pattern(self):
        import dark_tower_logic as logic

        writes = logic.reactor_fake_block_writes((10, 64, 20))
        self.assertEqual(26, len(writes))
        by_position = {
            tuple(write["position"]): write["block"] for write in writes
        }
        expected_positions = {
            (10 + dx, 64 + dy, 20 + dz)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            for dz in (-1, 0, 1)
            if (dx, dy, dz) != (0, 0, 0)
        }
        self.assertEqual(expected_positions, set(by_position))
        for y, expected_counts in (
            (65, Counter({"tf_slice:fake_diamond": 5, "tf_slice:fake_gold": 4})),
            (64, Counter({"tf_slice:fake_diamond": 4, "tf_slice:fake_gold": 4})),
            (63, Counter({"tf_slice:fake_diamond": 5, "tf_slice:fake_gold": 4})),
        ):
            self.assertEqual(
                expected_counts,
                Counter(block for position, block in by_position.items() if position[1] == y),
            )

    def test_reactor_matching_burst_offsets_are_made_fully_opposite(self):
        import dark_tower_logic as logic

        state = logic.create_reactor_state(
            (0, 64, 0), secondary=(3, -3, 3), tertiary=(3, -3, 3)
        )
        self.assertEqual([3, -3, 3], state["secondary"])
        self.assertEqual([-3, 3, -3], state["tertiary"])

    def test_reactor_blob_uses_the_source_fuzzy_shell_geometry(self):
        import dark_tower_logic as logic

        self.assertEqual(
            [
                (10, 20, 32),
                (10, 21, 32),
                (10, 22, 30),
                (10, 22, 31),
                (9, 20, 28),
                (9, 21, 28),
                (9, 22, 30),
                (9, 22, 29),
                (12, 20, 30),
                (12, 20, 31),
                (12, 19, 30),
                (12, 19, 31),
            ],
            logic.reactor_blob_positions((10, 20, 30), radius=2, fuzz=50),
        )
        self.assertEqual([], logic.reactor_blob_positions((0, 0, 0), 0, 0))

    def test_reactor_timeline_keeps_source_event_order_and_offset_centers(self):
        import dark_tower_logic as logic

        state = logic.create_reactor_state(
            (10, 64, 20), secondary=(3, -3, 3), tertiary=(-3, 3, -3)
        )
        state["counter"] = 119
        events = logic.advance_reactor(state, 1)
        world_events = [event for event in events if event["kind"] != "ambient"]
        self.assertEqual(
            ["primary_clear", "primary_debris", "secondary_expand"],
            [event["kind"] for event in world_events],
        )
        self.assertEqual(
            [(10, 64, 20), (10, 64, 20), (13, 61, 23)],
            [tuple(event["center"]) for event in world_events],
        )

        state["counter"] = 129
        events = logic.advance_reactor(state, 1)
        self.assertEqual(
            [
                "primary_clear",
                "primary_debris",
                "secondary_clear",
                "secondary_expand",
            ],
            [event["kind"] for event in events if event["kind"] != "ambient"],
        )

    def test_reactor_runtime_uses_blob_transforms_and_an_immediate_explosion(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        reactor = source[
            source.index("    def _set_reactor_active_state") :
            source.index("    def _update_dark_tower_mechanisms")
        ]
        self.assertIn("reactor_fake_block_writes", reactor)
        self.assertIn("reactor_blob_writes", reactor)
        self.assertIn("_reactor_can_transform", reactor)
        self.assertIn("CreateExplosion", reactor)
        self.assertIn("AddEffectToEntity", reactor)
        self.assertIn('"fire_resistance", 10, 0, False', reactor)
        self.assertNotIn("/summon tnt", reactor)

        ticker = source[
            source.index("    def _tick_dark_tower_block_entity") :
            source.index("    def _set_reactor_active_state")
        ]
        self.assertIn("_set_reactor_active_state", ticker)

    def test_reactor_generator_and_client_include_active_feedback(self):
        import build_dark_tower_content as content

        block = content.block_document("carminite_reactor")["minecraft:block"]
        active = next(
            permutation
            for permutation in block["permutations"]
            if "tf_slice:active" in permutation["condition"]
        )
        texture = active["components"]["minecraft:material_instances"]["*"]["texture"]
        self.assertEqual("tf_slice:carminite_reactor_active", texture)
        item = content.item_document("carminite", 64)["minecraft:item"]
        self.assertEqual("tf_slice:carminite", item["description"]["identifier"])
        self.assertEqual(64, item["components"]["minecraft:max_stack_size"])

        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        self.assertIn('"reactor_ambient"', client)
        self.assertIn('"portal.trigger"', client)

    def test_reactor_only_generator_limits_the_generated_artifact_write_set(self):
        import build_dark_tower_content as content

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bp = root / "behavior"
            rp = root / "resource"
            upstream = root / "upstream"
            (rp / "textures").mkdir(parents=True)
            (upstream / "textures" / "block").mkdir(parents=True)
            (rp / "textures" / "terrain_texture.json").write_text(
                json.dumps({"texture_data": {}}), encoding="utf-8"
            )
            (rp / "blocks.json").write_text("{}", encoding="utf-8")
            for name, payload in (
                ("towerdev_reactor_off.png", b"off"),
                ("towerdev_reactor_on.png", b"on"),
            ):
                (upstream / "textures" / "block" / name).write_bytes(payload)

            original = (content.BP, content.RP, content.UPSTREAM)
            try:
                content.BP = bp
                content.RP = rp
                content.UPSTREAM = upstream
                result = content.build_carminite_reactor_resources()
            finally:
                content.BP, content.RP, content.UPSTREAM = original

            expected = {
                bp / "netease_blocks" / "carminite_reactor.json",
                rp / "textures" / "blocks" / "carminite_reactor.png",
                rp / "textures" / "blocks" / "carminite_reactor_active.png",
                rp / "textures" / "terrain_texture.json",
                rp / "blocks.json",
            }
            self.assertEqual(expected, {Path(path) for path in result["files"]})
            block = json.loads(next(path for path in expected if path.name == "carminite_reactor.json").read_text(encoding="utf-8"))
            self.assertIn("permutations", block["minecraft:block"])
            atlas = json.loads((rp / "textures" / "terrain_texture.json").read_text(encoding="utf-8"))
            self.assertIn(
                "tf_slice:carminite_reactor_active", atlas["texture_data"]
            )


if __name__ == "__main__":
    unittest.main()
