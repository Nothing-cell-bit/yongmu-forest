# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "TwilightBossSliceB"
    / "TwilightBossSlice"
)
sys.path.insert(0, str(PACKAGE_ROOT))

import portal_logic


PORTAL = "tf_slice:twilight_portal"

VANILLA_FLOWERS = (
    "minecraft:dandelion",
    "minecraft:poppy",
    "minecraft:blue_orchid",
    "minecraft:allium",
    "minecraft:azure_bluet",
    "minecraft:red_tulip",
    "minecraft:orange_tulip",
    "minecraft:white_tulip",
    "minecraft:pink_tulip",
    "minecraft:oxeye_daisy",
    "minecraft:cornflower",
    "minecraft:lily_of_the_valley",
    "minecraft:flowering_azalea",
    "minecraft:wither_rose",
    "minecraft:sunflower",
    "minecraft:lilac",
    "minecraft:rose_bush",
    "minecraft:peony",
    "minecraft:torchflower",
    "minecraft:pitcher_plant",
    "minecraft:pink_petals",
    "minecraft:spore_blossom",
    "minecraft:closed_eyeblossom",
    "minecraft:open_eyeblossom",
    "minecraft:cactus_flower",
    "minecraft:wildflowers",
    "minecraft:yellow_flower",
    "minecraft:red_flower",
    "minecraft:double_plant",
)


class GridWorld(object):
    def __init__(self):
        self.blocks = {}

    def set(self, pos, name):
        self.blocks[pos] = {"name": name, "aux": 0}

    def get(self, pos):
        return self.blocks.get(pos, {"name": "minecraft:air", "aux": 0})

    def make_pool(self, decoration="minecraft:blue_orchid"):
        pool = ((0, 10, 0), (1, 10, 0), (0, 10, 1), (1, 10, 1))
        for pos in pool:
            self.set(pos, "minecraft:water")
            self.set((pos[0], pos[1] - 1, pos[2]), "minecraft:dirt")
        edges = (
            (-1, 10, 0),
            (-1, 10, 1),
            (0, 10, -1),
            (1, 10, -1),
            (2, 10, 0),
            (2, 10, 1),
            (0, 10, 2),
            (1, 10, 2),
        )
        for pos in edges:
            self.set(pos, "minecraft:grass")
            self.set((pos[0], pos[1] + 1, pos[2]), decoration)
        return pool, edges


class PortalPoolValidationTests(unittest.TestCase):
    def test_paired_portal_origin_keeps_the_source_portal_xz(self):
        source_surface = (
            (35, 70, 62),
            (36, 70, 62),
            (35, 70, 63),
            (36, 70, 63),
        )

        self.assertEqual(
            (35, 65, 62),
            portal_logic.paired_portal_origin(source_surface, 65),
        )

    def test_portal_surface_y_ignores_trees_and_uses_the_ground(self):
        column = {
            78: "minecraft:twilight_oak_leaves",
            77: "minecraft:twilight_oak_log",
            76: "minecraft:twilight_oak_log",
            65: "minecraft:short_grass",
            64: "minecraft:grass_block",
            63: "minecraft:dirt",
        }

        result = portal_logic.find_portal_surface_y(
            35,
            62,
            lambda pos: 78,
            lambda pos: {"name": column.get(pos[1], "minecraft:air")},
        )

        self.assertEqual(65, result)

    def test_portal_surface_y_waits_when_the_chunk_is_not_loaded(self):
        self.assertIsNone(
            portal_logic.find_portal_surface_y(
                35,
                62,
                lambda pos: None,
                lambda pos: {"name": "minecraft:air"},
            )
        )

    def test_portal_surface_y_rejects_unloaded_height_sentinel(self):
        sampled = []

        result = portal_logic.find_portal_surface_y(
            35,
            62,
            lambda pos: 32767,
            lambda pos: sampled.append(pos) or {"name": "minecraft:air"},
        )

        self.assertIsNone(result)
        self.assertEqual([], sampled)

    def test_all_vanilla_flowers_are_valid_portal_decorations(self):
        for flower in VANILLA_FLOWERS:
            with self.subTest(flower=flower):
                self.assertTrue(portal_logic.is_decoration(flower))

    def test_pool_accepts_mixed_flowers_around_one_frame(self):
        world = GridWorld()
        pool, edges = world.make_pool()
        mixed_flowers = VANILLA_FLOWERS[: len(edges)]
        for edge, flower in zip(edges, mixed_flowers):
            world.set((edge[0], edge[1] + 1, edge[2]), flower)

        result = portal_logic.collect_enclosed_surface(
            pool[0],
            world.get,
            portal_logic.WATER_BLOCKS,
            PORTAL,
        )

        self.assertEqual(sorted(pool), result)

    def test_canonical_two_by_two_pool_is_valid(self):
        world = GridWorld()
        pool, _ = world.make_pool()
        result = portal_logic.collect_enclosed_surface(
            pool[0],
            world.get,
            portal_logic.WATER_BLOCKS,
            PORTAL,
        )
        self.assertEqual(sorted(pool), result)

    def test_activated_portal_stays_valid_after_all_flowers_are_removed(self):
        world = GridWorld()
        pool, edges = world.make_pool()
        for pos in pool:
            world.set(pos, PORTAL)
        for edge in edges:
            world.set(
                (edge[0], edge[1] + 1, edge[2]),
                "minecraft:air",
            )

        result = portal_logic.collect_stable_portal(
            pool[0],
            world.get,
            PORTAL,
        )

        self.assertEqual(sorted(pool), result)

    def test_activated_portal_still_breaks_when_its_ground_frame_is_removed(self):
        world = GridWorld()
        pool, edges = world.make_pool()
        for pos in pool:
            world.set(pos, PORTAL)
        world.set(edges[0], "minecraft:air")

        self.assertIsNone(
            portal_logic.collect_stable_portal(
                pool[0],
                world.get,
                PORTAL,
            )
        )

    def test_pool_requires_at_least_four_water_blocks(self):
        world = GridWorld()
        pool, _ = world.make_pool()
        world.set(pool[-1], "minecraft:grass")
        world.set((pool[-1][0], pool[-1][1] + 1, pool[-1][2]), "minecraft:fern")
        self.assertIsNone(
            portal_logic.collect_enclosed_surface(
                pool[0],
                world.get,
                portal_logic.WATER_BLOCKS,
                PORTAL,
            )
        )

    def test_pool_rejects_missing_natural_decoration(self):
        world = GridWorld()
        pool, edges = world.make_pool()
        edge = edges[0]
        world.set((edge[0], edge[1] + 1, edge[2]), "minecraft:stone")
        self.assertIsNone(
            portal_logic.collect_enclosed_surface(
                pool[0],
                world.get,
                portal_logic.WATER_BLOCKS,
                PORTAL,
            )
        )

    def test_pool_rejects_unsupported_water(self):
        world = GridWorld()
        pool, _ = world.make_pool()
        world.set((pool[0][0], pool[0][1] - 1, pool[0][2]), "minecraft:air")
        self.assertIsNone(
            portal_logic.collect_enclosed_surface(
                pool[0],
                world.get,
                portal_logic.WATER_BLOCKS,
                PORTAL,
            )
        )

    def test_activated_portal_has_safe_edge_exit(self):
        world = GridWorld()
        pool, _ = world.make_pool()
        for pos in pool:
            world.set(pos, PORTAL)
        surface = portal_logic.collect_portal(pool[0], world.get, PORTAL)
        self.assertEqual(sorted(pool), surface)
        self.assertEqual(
            (-0.5, 11.0, 0.5),
            portal_logic.find_exit(surface, world.get, PORTAL),
        )

    def test_exit_rejects_edges_blocked_at_feet_or_head_height(self):
        world = GridWorld()
        pool, edges = world.make_pool()
        for pos in pool:
            world.set(pos, PORTAL)
        for edge in edges:
            world.set((edge[0], edge[1] + 1, edge[2]), "minecraft:dirt")
            world.set((edge[0], edge[1] + 2, edge[2]), "minecraft:dirt")

        self.assertIsNone(
            portal_logic.find_exit(pool, world.get, PORTAL)
        )

    def test_connected_surface_can_be_collected_after_frame_breaks(self):
        world = GridWorld()
        pool, edges = world.make_pool()
        for pos in pool:
            world.set(pos, PORTAL)
        broken_edge = edges[0]
        world.set(broken_edge, "minecraft:air")
        self.assertEqual(
            sorted(pool),
            portal_logic.collect_connected_surface(
                pool[0], world.get, set((PORTAL,))
            ),
        )
        self.assertIsNone(
            portal_logic.collect_portal(pool[0], world.get, PORTAL)
        )


class PortalItemTests(unittest.TestCase):
    def test_item_name_accepts_old_and_new_item_dictionary_keys(self):
        self.assertEqual(
            "minecraft:diamond",
            portal_logic.item_name({"newItemName": "minecraft:diamond"}),
        )
        self.assertEqual(
            "minecraft:diamond",
            portal_logic.item_name({"itemName": "minecraft:diamond"}),
        )


class PlayerPositionTests(unittest.TestCase):
    def test_engine_position_is_one_point_six_two_above_foot_position(self):
        self.assertEqual(
            (35.5, 72.62, 62.5),
            portal_logic.player_position_from_foot(
                (35.5, 71.0, 62.5)
            ),
        )

    def test_engine_position_round_trips_to_foot_position(self):
        engine_position = portal_logic.player_position_from_foot(
            (35.5, 71.0, 62.5)
        )

        self.assertEqual(
            (35.5, 71.0, 62.5),
            portal_logic.player_foot_from_position(engine_position),
        )


class PortalClientReadinessTests(unittest.TestCase):
    def test_background_prewarm_excludes_safe_core_and_prioritizes_view(self):
        positions = portal_logic.background_preload_chunk_positions(
            (34.5, 66.0, 62.5),
            view_yaw=0.0,
        )

        self.assertEqual(72, len(positions))
        self.assertEqual(72, len(set(positions)))
        self.assertEqual((2, 5), positions[0])
        self.assertTrue(
            all(
                max(abs(chunk_x - 2), abs(chunk_z - 3)) > 1
                for chunk_x, chunk_z in positions
            )
        )

    def test_background_prewarm_yaw_ninety_prioritizes_negative_x(self):
        positions = portal_logic.background_preload_chunk_positions(
            (34.5, 66.0, 62.5),
            view_yaw=90.0,
        )

        self.assertEqual((0, 3), positions[0])

    def test_chunk_block_bounds_are_inclusive_and_support_negative_chunks(self):
        self.assertEqual(
            ((32, 0, 80), (47, 255, 95)),
            portal_logic.chunk_block_bounds((2, 5)),
        )
        self.assertEqual(
            ((-16, 0, -32), (-1, 255, -17)),
            portal_logic.chunk_block_bounds((-1, -2)),
        )

    def test_default_render_probe_covers_nine_by_nine_chunks(self):
        positions = portal_logic.client_render_chunk_sample_positions(
            (34.5, 66.0, 62.5)
        )

        self.assertEqual(81, len(positions))
        self.assertEqual((40, 56), positions[0])
        self.assertEqual(81, len(set(positions)))

    def test_required_client_events_cover_three_by_three_chunks(self):
        positions = portal_logic.client_required_chunk_positions(
            (34.5, 66.0, 62.5),
            chunk_radius=portal_logic.PORTAL_CLIENT_READY_CHUNK_RADIUS,
        )

        self.assertEqual(9, len(positions))
        self.assertEqual(
            {
                (chunk_x, chunk_z)
                for chunk_x in (1, 2, 3)
                for chunk_z in (2, 3, 4)
            },
            set(positions),
        )

    def test_client_chunk_event_gate_requires_every_target_chunk(self):
        required = {(1, 2), (2, 2), (3, 2)}

        self.assertFalse(
            portal_logic.client_required_chunks_loaded(
                required,
                {(1, 2), (2, 2)},
            )
        )
        self.assertTrue(
            portal_logic.client_required_chunks_loaded(
                required,
                {(1, 2), (2, 2), (3, 2), (20, 20)},
            )
        )

    def test_client_anchor_ready_needs_player_and_non_air_support(self):
        destination = (34.5, 66.0, 62.5)

        self.assertTrue(
            portal_logic.client_destination_anchor_ready(
                destination,
                destination,
                ("minecraft:grass_block", 0),
            )
        )
        self.assertFalse(
            portal_logic.client_destination_anchor_ready(
                destination,
                destination,
                ("minecraft:air", 0),
            )
        )

    def test_render_probe_covers_the_destination_three_by_three_chunks(self):
        positions = portal_logic.client_render_chunk_sample_positions(
            (34.5, 66.0, 62.5),
            chunk_radius=1,
        )

        self.assertEqual(9, len(positions))
        self.assertEqual(
            {
                (x, z)
                for x in (24, 40, 56)
                for z in (40, 56, 72)
            },
            set(positions),
        )

    def test_render_probe_uses_floor_chunks_at_negative_coordinates(self):
        positions = portal_logic.client_render_chunk_sample_positions(
            (-0.5, 66.0, -0.5),
            chunk_radius=1,
        )

        self.assertIn((-8, -8), positions)
        self.assertEqual(9, len(set(positions)))

    def test_render_probes_are_batched_without_skipping_chunks(self):
        positions = portal_logic.client_render_chunk_sample_positions(
            (34.5, 66.0, 62.5)
        )
        observed = []
        next_index = 0
        pass_complete = False

        while not pass_complete:
            batch, next_index, pass_complete = (
                portal_logic.client_render_probe_batch(
                    positions,
                    next_index,
                    max_probes=12,
                )
            )
            self.assertLessEqual(len(batch), 12)
            observed.extend(batch)

        self.assertEqual(positions, observed)
        self.assertEqual(0, next_index)

    def test_destination_is_ready_only_after_player_and_support_arrive(self):
        destination = (34.5, 66.0, 62.5)

        self.assertTrue(
            portal_logic.client_destination_render_ready(
                destination,
                destination,
                78,
                ("minecraft:grass_block", 0),
                [78] * 9,
            )
        )
        self.assertFalse(
            portal_logic.client_destination_render_ready(
                (8192.5, 97.0, 8192.5),
                destination,
                78,
                ("minecraft:grass_block", 0),
                [78] * 9,
            )
        )

    def test_destination_rejects_unloaded_or_air_support(self):
        destination = (34.5, 66.0, 62.5)

        for top_height, support in (
            (None, ("minecraft:grass_block", 0)),
            (78, None),
            (78, ("minecraft:air", 0)),
        ):
            self.assertFalse(
                portal_logic.client_destination_render_ready(
                    destination,
                    destination,
                    top_height,
                    support,
                    [78] * 9,
                )
            )

    def test_destination_waits_for_every_surrounding_render_chunk(self):
        destination = (34.5, 66.0, 62.5)
        ready_heights = [78] * 9

        self.assertTrue(
            portal_logic.client_destination_render_ready(
                destination,
                destination,
                78,
                ("minecraft:grass_block", 0),
                ready_heights,
            )
        )
        for missing_height in (None, -1, 32767):
            heights = list(ready_heights)
            heights[-1] = missing_height
            self.assertFalse(
                portal_logic.client_destination_render_ready(
                    destination,
                    destination,
                    78,
                    ("minecraft:grass_block", 0),
                    heights,
                )
            )


if __name__ == "__main__":
    unittest.main()
