# -*- coding: utf-8 -*-
import json
import pathlib
import random
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import build_ruin_structures as structure_builder


BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
CATALOG = (
    BP
    / "structures"
    / "tf_slice"
    / "ruins"
    / "structure_catalog_v1.json"
)
BUILDER = ROOT / "tools" / "build_ruin_structures.py"
SERVICE = BP / "TwilightBossSlice" / "structureWorldgenService.py"
SERVER = BP / "TwilightBossSlice" / "serverSystem.py"

COURTYARD_BLOCKS = (
    "nagastone",
    "etched_nagastone",
    "nagastone_pillar",
    "nagastone_head",
    "nagastone_stairs_left",
    "nagastone_stairs_right",
    "mossy_etched_nagastone",
    "cracked_etched_nagastone",
    "mossy_nagastone_pillar",
    "cracked_nagastone_pillar",
    "mossy_nagastone_stairs_left",
    "cracked_nagastone_stairs_left",
    "mossy_nagastone_stairs_right",
    "cracked_nagastone_stairs_right",
    "spiral_bricks",
    "mazestone_mosaic",
    "naga_boss_spawner",
)

SOURCE_TEMPLATES = (
    "courtyard_wall",
    "courtyard_wall_corner",
    "courtyard_wall_corner_decayed",
    "courtyard_wall_corner_inner",
    "courtyard_wall_corner_inner_decayed",
    "courtyard_wall_decayed",
    "courtyard_wall_padding",
    "courtyard_wall_padding_decayed",
    "hedge_between",
    "hedge_between_big",
    "hedge_corner",
    "hedge_corner_big",
    "hedge_end",
    "hedge_end_big",
    "hedge_end_pillar",
    "hedge_end_pillar_big",
    "hedge_intersection",
    "hedge_intersection_big",
    "hedge_line",
    "hedge_line_big",
    "hedge_t",
    "hedge_t_big",
    "hydra_statue",
    "pathway",
    "terrace_duct",
    "terrace_fire",
    "terrace_statue",
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class NagaCourtyardStructureContractTests(unittest.TestCase):
    def setUp(self):
        catalog = read_json(CATALOG)
        self.entry = {
            entry["id"]: entry for entry in catalog["structures"]
        }.get("naga_courtyard")

    def test_catalog_ports_the_source_landmark_and_boss_spawner(self):
        self.assertIsNotNone(self.entry)
        self.assertEqual("4.3.2508", self.entry["sourceVersion"])
        self.assertEqual("landmark_service", self.entry["strategy"])
        self.assertEqual("naga_courtyard", self.entry["landmarkKind"])
        self.assertGreaterEqual(self.entry["bounds"][3] + 1, 88)
        self.assertGreaterEqual(self.entry["bounds"][5] + 1, 88)
        self.assertGreaterEqual(self.entry["bounds"][4] + 1, 10)
        self.assertEqual(
            "tf_slice:forest_wyrm",
            self.entry["bossSpawner"]["entity"],
        )
        self.assertEqual(50, self.entry["bossSpawner"]["activationRadius"])

    def test_all_source_templates_are_declared_by_the_builder(self):
        builder = BUILDER.read_text(encoding="utf-8")
        for template_name in SOURCE_TEMPLATES:
            self.assertIn('"%s.nbt"' % template_name, builder)
        self.assertIn("COURTYARD_ROW_OF_CELLS = 8", builder)
        self.assertIn("COURTYARD_CELL_SIZE = 12", builder)
        self.assertIn("COURTYARD_HEDGE_FLOOF = 0.5", builder)
        self.assertIn("COURTYARD_WALL_INTEGRITY = 0.95", builder)
        self.assertIn("COURTYARD_WALL_DECAY = 0.1", builder)

    def test_generated_tiles_use_custom_stone_and_one_boss_marker(self):
        self.assertIsNotNone(self.entry)
        for variant in self.entry["variants"]:
            payload = b"".join(
                (
                    BP / "structures" / (piece["structure"] + ".mcstructure")
                ).read_bytes()
                for piece in variant["pieces"]
            )
            self.assertIn(b"tf_slice:nagastone", payload)
            self.assertIn(b"tf_slice:etched_nagastone", payload)
            self.assertIn(b"tf_slice:twilight_oak_leaves", payload)
            self.assertEqual(1, payload.count(b"tf_slice:naga_boss_spawner"))
            for piece in variant["pieces"]:
                self.assertLessEqual(piece["size"][0], 16)
                self.assertLessEqual(piece["size"][2], 16)

    def test_rotated_templates_keep_the_upstream_structure_origin(self):
        class Template(object):
            size = (3, 1, 5)
            blocks = {
                (0, 0, 0): ("minecraft:stone", {}, None),
                (2, 0, 4): ("minecraft:stone", {}, None),
            }

        result = structure_builder.SparseStructure(
            (32, 1, 32),
            "rotation_origin_contract",
        )

        structure_builder._place_courtyard_template(
            result,
            Template(),
            (10, 0, 10),
            1,
            random.Random(1),
        )

        self.assertEqual(
            {(10, 0, 10), (6, 0, 12)},
            set(result.blocks),
        )

    def test_native_courtyard_does_not_serialize_a_tall_air_canopy(self):
        structure = structure_builder.SparseStructure(
            (1, 12, 1),
            "naga_courtyard",
        )

        envelope = structure_builder._surface_native_envelope(
            structure,
            "naga_courtyard",
        )

        authored_core_height = (
            structure_builder.SURFACE_NATIVE_GROUND_Y
            + structure.size[1]
            + structure_builder.COURTYARD_PIECE_VERTICAL_OFFSET
        )
        self.assertGreaterEqual(envelope.size[1], authored_core_height)
        self.assertLess(
            envelope.size[1],
            authored_core_height + 48,
        )

    def test_maze_restores_adjacent_zero_cells_from_the_source_connectome(self):
        maze, _clips = structure_builder._generate_courtyard_maze(
            random.Random(0x4E414741 + 1)
        )

        self.assertEqual(0b0100, maze[4][1] & 0b0100)
        self.assertEqual(0b0001, maze[3][1] & 0b0001)

    def test_every_internal_maze_connection_is_reciprocal(self):
        directions = (
            (0b0001, 0b0100, 1, 0),
            (0b0100, 0b0001, -1, 0),
            (0b0010, 0b1000, 0, 1),
            (0b1000, 0b0010, 0, -1),
        )
        for layout_seed in structure_builder.COURTYARD_VARIANT_SEEDS:
            maze, _clips = structure_builder._generate_courtyard_maze(
                random.Random(0x4E414741 + layout_seed)
            )
            for x in range(7):
                for z in range(7):
                    for bit, opposite, dx, dz in directions:
                        neighbor_x = x + dx
                        neighbor_z = z + dz
                        if not (
                            maze[x][z] & bit
                            and 0 <= neighbor_x < 7
                            and 0 <= neighbor_z < 7
                        ):
                            continue
                        self.assertTrue(
                            maze[neighbor_x][neighbor_z] & opposite,
                            (layout_seed, x, z, neighbor_x, neighbor_z),
                        )

    def test_finite_variant_bank_keeps_water_without_duplicate_statue_body(self):
        self.assertEqual(
            structure_builder.NAGA_COURTYARD_VARIANT_COUNT,
            len(structure_builder.COURTYARD_VARIANT_SEEDS),
        )
        for layout_seed in structure_builder.COURTYARD_VARIANT_SEEDS:
            names = [
                block[0]
                for block in structure_builder.naga_courtyard(
                    layout_seed
                ).blocks.values()
            ]
            self.assertIn("minecraft:water", names, layout_seed)
            self.assertNotIn("minecraft:hopper", names, layout_seed)

    def test_terrace_processor_removes_source_sandstone_placeholders(self):
        for layout_seed in structure_builder.COURTYARD_VARIANT_SEEDS:
            names = {
                block[0]
                for block in structure_builder.naga_courtyard(
                    layout_seed
                ).blocks.values()
            }
            self.assertNotIn(
                "minecraft:sandstone_slab",
                names,
                layout_seed,
            )

    def test_walkway_and_recessed_terrace_keep_upstream_vertical_offsets(self):
        self.assertEqual(2, structure_builder.COURTYARD_WALKWAY_Y)
        self.assertEqual(0, structure_builder.COURTYARD_TERRACE_ORIGIN_Y)
        self.assertEqual(
            -2,
            structure_builder.COURTYARD_PIECE_VERTICAL_OFFSET,
        )

        structure = structure_builder.naga_courtyard(0)
        water_levels = {
            position[1]
            for position, block in structure.blocks.items()
            if block[0] == "minecraft:water"
        }
        self.assertEqual({1}, water_levels)

    def test_inner_connector_padding_only_extends_into_unclipped_neighbors(self):
        self.assertTrue(
            structure_builder._courtyard_needs_inner_padding(0b0010)
        )
        self.assertFalse(
            structure_builder._courtyard_needs_inner_padding(0b10000)
        )

    def test_terrace_selection_matches_the_4_3_2508_three_way_policy(self):
        class SequenceRandom(object):
            def __init__(self, values):
                self.values = list(values)

            def randrange(self, bound):
                value = self.values.pop(0)
                self.assertion = (value, bound)
                return value

        self.assertEqual(
            "statue",
            structure_builder._courtyard_terrace_kind(SequenceRandom([0])),
        )
        self.assertEqual(
            "fire",
            structure_builder._courtyard_terrace_kind(
                SequenceRandom([1, 0])
            ),
        )
        self.assertEqual(
            "duct",
            structure_builder._courtyard_terrace_kind(
                SequenceRandom([1, 1])
            ),
        )

    def test_boss_marker_uses_the_source_local_height(self):
        structure = structure_builder.naga_courtyard(0)
        center = (
            structure_builder.COURTYARD_MARGIN
            + structure_builder.COURTYARD_RADIUS
        )

        self.assertEqual(
            "tf_slice:naga_boss_spawner",
            structure.blocks[(center, 5, center)][0],
        )
        self.assertNotEqual(
            "tf_slice:naga_boss_spawner",
            structure.blocks.get((center, 1, center), (None,))[0],
        )


class NagaCourtyardBlockContractTests(unittest.TestCase):
    def test_boss_spawner_uses_supported_modern_block_components(self):
        server = read_json(
            BP / "netease_blocks" / "naga_boss_spawner.json"
        )
        block = server["minecraft:block"]
        components = block["components"]

        self.assertEqual("1.20.60", server["format_version"])
        self.assertFalse(components["minecraft:destructible_by_mining"])
        self.assertFalse(components["minecraft:destructible_by_explosion"])
        self.assertEqual(0, components["minecraft:light_dampening"])
        self.assertNotIn("minecraft:destroy_time", components)
        self.assertNotIn("minecraft:explosion_resistance", components)
        self.assertNotIn("minecraft:block_light_absorption", components)
        self.assertEqual(
            {"tick": True, "movable": False},
            components["netease:block_entity"],
        )

    def test_courtyard_blocks_have_server_client_and_texture_definitions(self):
        blocks = read_json(RP / "blocks.json")
        atlas = read_json(RP / "textures" / "terrain_texture.json")[
            "texture_data"
        ]
        for block_name in COURTYARD_BLOCKS:
            identifier = "tf_slice:%s" % block_name
            server = read_json(
                BP / "netease_blocks" / ("%s.json" % block_name)
            )
            self.assertEqual(
                identifier,
                server["minecraft:block"]["description"]["identifier"],
            )
            self.assertIn(identifier, blocks)
            texture = blocks[identifier]["textures"]
            texture_keys = (
                set(texture.values())
                if isinstance(texture, dict)
                else {texture}
            )
            for key in texture_keys:
                self.assertIn(key, atlas)
                paths = atlas[key]["textures"]
                if isinstance(paths, str):
                    paths = [paths]
                for path in paths:
                    if isinstance(path, dict):
                        path = path["path"]
                    self.assertTrue(
                        (RP / (path + ".png")).is_file(),
                        path,
                    )

    def test_courtyard_blocks_share_the_twilight_creative_group(self):
        catalog = read_json(
            BP / "item_catalog" / "crafting_item_catalog.json"
        )
        creative_items = {
            identifier
            for category in catalog["minecraft:crafting_items_catalog"]["categories"]
            for group in category.get("groups", [])
            for identifier in group.get("items", [])
        }
        for block_name in set(COURTYARD_BLOCKS) - {"naga_boss_spawner"}:
            self.assertIn("tf_slice:%s" % block_name, creative_items)
        self.assertNotIn("tf_slice:naga_boss_spawner", creative_items)

    def test_directional_courtyard_blocks_use_states_and_geometry(self):
        expectations = {
            "etched_nagastone": {"tf_slice:facing"},
            "nagastone_pillar": {
                "tf_slice:axis",
                "tf_slice:reversed",
            },
            "nagastone_head": {"tf_slice:facing"},
            "nagastone_stairs_left": {
                "tf_slice:facing",
                "tf_slice:half",
                "tf_slice:shape",
            },
            "nagastone_stairs_right": {
                "tf_slice:facing",
                "tf_slice:half",
                "tf_slice:shape",
            },
        }
        for block_name, expected_states in expectations.items():
            server = read_json(
                BP / "netease_blocks" / ("%s.json" % block_name)
            )
            block = server["minecraft:block"]
            self.assertEqual("1.20.60", server["format_version"])
            self.assertEqual(
                expected_states,
                set(block["description"]["states"]),
                block_name,
            )
            self.assertIn(
                "minecraft:geometry",
                block["components"],
                block_name,
            )


class NagaCourtyardRuntimeContractTests(unittest.TestCase):
    def test_landmark_service_activates_and_persists_the_courtyard_boss(self):
        service = SERVICE.read_text(encoding="utf-8")
        server = SERVER.read_text(encoding="utf-8")
        self.assertIn('"naga_courtyard"', service)
        self.assertIn("courtyard_activation_position", service)
        self.assertIn("bossSpawner", service)
        self.assertIn("bossSpawned", service)
        self.assertIn("mark_naga_defeated", service)
        self.assertIn("_spawn_courtyard_naga", server)
        self.assertIn("self._ruin_worldgen.mark_naga_defeated", server)

    def test_server_routes_spawner_block_entity_ticks_to_worldgen(self):
        server = SERVER.read_text(encoding="utf-8")

        self.assertIn(
            'self._listen_engine(\n            "ServerBlockEntityTickEvent",',
            server,
        )
        self.assertIn("def OnNagaSpawnerBlockEntityTick", server)
        self.assertIn("on_courtyard_spawner_tick", server)

    def test_server_uses_entity_event_component_and_stable_spawn_confirmation(self):
        server = SERVER.read_text(encoding="utf-8")

        self.assertIn("CF.CreateEntityEvent(entityId)", server)
        self.assertNotIn("CF.CreateEntityDefinitions(entityId)", server)
        self.assertIn("def _confirm_courtyard_naga", server)
        self.assertIn("self._pending_courtyard_nagas", server)
        spawn_method = server.split(
            "def _spawn_courtyard_naga", 1
        )[1].split("def _confirm_courtyard_naga", 1)[0]
        self.assertNotIn("self._register_boss(", spawn_method)


if __name__ == "__main__":
    unittest.main()
