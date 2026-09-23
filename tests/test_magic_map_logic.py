# -*- coding: utf-8 -*-
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_ROOT = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
sys.path.insert(0, str(MODULE_ROOT))

import magic_map_logic as logic
import biome_catalog


class MagicMapHudLayoutTests(unittest.TestCase):
    def test_canvas_size_rejects_collapsed_native_hud_measurement(self):
        self.assertEqual(
            (128.0, 128.0),
            logic.resolve_canvas_size((1.0, 1.0), 128),
        )
        self.assertEqual(
            (192.0, 160.0),
            logic.resolve_canvas_size((192.0, 160.0), 128),
        )

    def test_pending_snapshot_accumulates_biome_delta_runs(self):
        snapshot = {
            "schemaVersion": 3,
            "mapId": 7,
            "gridSize": 128,
            "biomeRuns": [[0, 0, 2, "forest"]],
        }
        delta = {
            "schemaVersion": 3,
            "mapId": 7,
            "biomeRuns": [[0, 2, 4, "lake"]],
            "player": [16, 16],
        }

        merged = logic.merge_map_delta(snapshot, delta)

        self.assertEqual(
            [
                [0, 0, 2, "forest"],
                [0, 2, 4, "lake"],
            ],
            merged["biomeRuns"],
        )
        self.assertEqual([16, 16], merged["player"])

    def test_held_map_transition_requests_snapshot_when_map_id_changes(self):
        first = logic.held_map_transition(None, True, 7)
        unchanged = logic.held_map_transition(first["state"], True, 7)
        switched = logic.held_map_transition(first["state"], True, 9)

        self.assertTrue(first["heldChanged"])
        self.assertTrue(first["snapshotNeeded"])
        self.assertFalse(unchanged["heldChanged"])
        self.assertFalse(unchanged["mapChanged"])
        self.assertFalse(unchanged["snapshotNeeded"])
        self.assertFalse(switched["heldChanged"])
        self.assertTrue(switched["mapChanged"])
        self.assertTrue(switched["snapshotNeeded"])

    def test_held_map_transition_reports_release_without_snapshot(self):
        released = logic.held_map_transition((True, 7), False, None)

        self.assertEqual((False, None), released["state"])
        self.assertTrue(released["heldChanged"])
        self.assertFalse(released["mapChanged"])
        self.assertFalse(released["snapshotNeeded"])

    def test_held_map_transition_recovers_legacy_boolean_hot_reload_state(self):
        transition = logic.held_map_transition(True, True, 7)

        self.assertFalse(transition["heldChanged"])
        self.assertTrue(transition["mapChanged"])
        self.assertTrue(transition["snapshotNeeded"])


class MagicMapCoordinateTests(unittest.TestCase):
    def test_pixel_grid_matches_the_original_magic_map_resolution(self):
        self.assertEqual(128, logic.MAP_GRID_SIZE)
        self.assertEqual(16, logic.MAP_CELL_BLOCKS)
        self.assertEqual(
            logic.MAP_SIZE_BLOCKS,
            logic.MAP_GRID_SIZE * logic.MAP_CELL_BLOCKS,
        )

    def test_held_item_selection_supports_offhand_and_preferred_hand(self):
        carried = {"itemName": "minecraft:stick"}
        offhand = {"itemName": "tf_slice:filled_magic_map", "extraId": "b"}
        is_map = lambda item: (
            isinstance(item, dict)
            and item.get("itemName") == "tf_slice:filled_magic_map"
        )

        self.assertEqual(
            ("offhand", offhand),
            logic.select_held_item(carried, offhand, is_map),
        )

        carried_map = {
            "itemName": "tf_slice:filled_magic_map",
            "extraId": "a",
        }
        self.assertEqual(
            ("offhand", offhand),
            logic.select_held_item(
                carried_map,
                offhand,
                is_map,
                preferred_item=offhand,
            ),
        )

    def test_player_marker_direction_matches_held_map_surface(self):
        self.assertEqual("v", logic.player_marker_text(0.0))
        self.assertEqual("<", logic.player_marker_text(90.0))
        self.assertEqual("^", logic.player_marker_text(180.0))
        self.assertEqual(">", logic.player_marker_text(-90.0))
        self.assertEqual("o", logic.player_marker_text(0.0, "off_map"))

    def test_player_marker_direction_selects_image_sprite(self):
        self.assertEqual("south", logic.player_marker_direction(0.0))
        self.assertEqual("west", logic.player_marker_direction(90.0))
        self.assertEqual("north", logic.player_marker_direction(180.0))
        self.assertEqual("east", logic.player_marker_direction(-90.0))
        self.assertEqual(
            "off_map",
            logic.player_marker_direction(0.0, "off_map"),
        )
        self.assertEqual(
            "off_map",
            logic.player_marker_direction(0.0, "off_limits"),
        )

    def test_held_map_projection_keeps_upstream_world_orientation(self):
        bounds = logic.map_bounds(1024, 1024)
        north_west = logic.map_marker_position(
            bounds[0], bounds[1], bounds, 128, 128
        )
        south_east = logic.map_marker_position(
            bounds[2], bounds[3], bounds, 128, 128
        )

        self.assertEqual((0.0, 0.0), north_west[:2])
        self.assertGreater(south_east[0], 127.0)
        self.assertGreater(south_east[1], 127.0)

    def test_player_marker_distinguishes_inside_off_map_and_off_limits(self):
        bounds = logic.map_bounds(1024, 1024)
        inside = logic.map_marker_position(1024, 1024, bounds, 128, 128, 3)
        off_map = logic.map_marker_position(2048, 1024, bounds, 128, 128, 3)
        off_limits = logic.map_marker_position(
            1024 + logic.MAP_OFF_LIMIT_BLOCKS,
            1024,
            bounds,
            128,
            128,
            3,
        )

        self.assertEqual("inside", inside[2])
        self.assertEqual("off_map", off_map[2])
        self.assertEqual(125.0, off_map[0])
        self.assertEqual("off_limits", off_limits[2])

    def test_map_center_matches_upstream_positive_and_negative_boundaries(self):
        cases = {
            -3073: -3072,
            -3072: -3072,
            -2049: -3072,
            -2048: -1024,
            -1025: -1024,
            -1024: -1024,
            -1: -1024,
            0: 1024,
            1023: 1024,
            1024: 1024,
            2047: 1024,
            2048: 3072,
        }
        for coordinate, expected in cases.items():
            self.assertEqual(expected, logic.map_center_coordinate(coordinate))

    def test_bounds_are_inclusive_and_do_not_overlap_adjacent_maps(self):
        self.assertEqual(
            (0, 0, 2047, 2047),
            logic.map_bounds(1024, 1024),
        )
        self.assertTrue(logic.is_inside_map(2047, 2047, 1024, 1024))
        self.assertFalse(logic.is_inside_map(2048, 2047, 1024, 1024))
        self.assertEqual(
            (2048, 0, 4095, 2047),
            logic.map_bounds(3072, 1024),
        )


class MagicMapIdentityTests(unittest.TestCase):
    def test_extra_id_round_trips_and_rejects_noncanonical_data(self):
        extra_id = logic.encode_extra_id(-1024, 3072)
        self.assertEqual("tfmm:v1:-1024:3072", extra_id)
        self.assertEqual((-1024, 3072), logic.decode_extra_id(extra_id))

        for invalid in (
            None,
            "",
            "tfmm:v2:-1024:3072",
            "tfmm:v1:0:0",
            "tfmm:v1:1024",
            "tfmm:v1:1024:abc",
            " tfmm:v1:1024:1024",
        ):
            self.assertIsNone(logic.decode_extra_id(invalid))

    def test_v3_identity_keeps_copies_on_one_unique_map_record(self):
        extra_id = logic.encode_extra_id(-1024, 3072, map_id=41)
        self.assertEqual("tfmm:v3:41:-1024:3072", extra_id)
        self.assertEqual(
            (41, -1024, 3072),
            logic.decode_map_identity(extra_id),
        )
        self.assertEqual(3, logic.extra_id_version(extra_id))
        self.assertEqual(
            (41, -1024, 3072),
            logic.decode_map_identity("tfmm:v2:41:-1024:3072"),
        )
        self.assertEqual(
            2,
            logic.extra_id_version("tfmm:v2:41:-1024:3072"),
        )
        self.assertEqual(
            (None, -1024, 3072),
            logic.decode_map_identity("tfmm:v1:-1024:3072"),
        )
        for invalid in (
            "tfmm:v2:0:-1024:3072",
            "tfmm:v2:-1:-1024:3072",
            "tfmm:v2:abc:-1024:3072",
            "tfmm:v2:41:0:0",
        ):
            self.assertIsNone(logic.decode_map_identity(invalid))

    def test_sector_key_and_marker_keys_are_stable(self):
        self.assertEqual("-1024,3072", logic.sector_key(-1024, 3072))
        self.assertEqual(
            "naga_courtyard:264,-247",
            logic.landmark_key("naga_courtyard", 264, -247),
        )

    def test_cloned_stacks_keep_the_same_map_identity(self):
        source = {
            "itemName": "tf_slice:filled_magic_map",
            "count": 1,
            "auxValue": 0,
            "extraId": logic.encode_extra_id(1024, -1024, map_id=41),
        }
        clone = logic.clone_magic_map_stack(source, 8)

        self.assertEqual(9, clone["count"])
        self.assertEqual(source["extraId"], clone["extraId"])
        self.assertEqual(
            logic.decode_map_identity(source["extraId"]),
            logic.decode_map_identity(clone["extraId"]),
        )
        self.assertEqual(1, source["count"])


class MagicMapDiscoveryTests(unittest.TestCase):
    def test_biome_cells_merge_into_solid_rectangles(self):
        cells = {
            0: "forest",
            1: "forest",
            4: "forest",
            5: "forest",
            7: "lake",
        }

        self.assertEqual(
            [
                [0, 0, 2, 2, "forest"],
                [1, 3, 2, 4, "lake"],
            ],
            logic.biome_rectangles(cells, grid_size=4),
        )

    def test_biome_rectangles_preserve_every_filled_pixel(self):
        cells = {}
        for row in range(33):
            for column in range(78):
                if row + column < 96:
                    cells[row * 128 + column] = (
                        "forest" if column < 40 else "firefly_forest"
                    )

        rectangles = logic.biome_rectangles(cells)
        reconstructed = {}
        for row_start, column_start, row_end, column_end, biome_key in rectangles:
            for row in range(row_start, row_end):
                for column in range(column_start, column_end):
                    reconstructed[row * 128 + column] = biome_key

        self.assertEqual(cells, reconstructed)
        self.assertLess(len(rectangles), 1024)

    def test_unknown_biomes_use_a_persisted_fallback_pixel(self):
        self.assertIn(logic.UNKNOWN_BIOME_KEY, logic.TWILIGHT_BIOME_KEYS)
        cells = logic.normalize_biome_cells({"4096": logic.UNKNOWN_BIOME_KEY})
        self.assertEqual({"4096": logic.UNKNOWN_BIOME_KEY}, cells)
        self.assertEqual(
            cells,
            logic.decode_biome_pixels(logic.encode_biome_pixels(cells)),
        )

    def test_discovery_cells_are_fixed_to_the_map_and_radius(self):
        samples = logic.discovery_cell_samples(
            player_x=1024,
            player_z=1024,
            center_x=1024,
            center_z=1024,
        )
        self.assertGreater(len(samples), 0)
        self.assertEqual(
            sorted(
                (sample[1] - 1024) ** 2 + (sample[2] - 1024) ** 2
                for sample in samples
            ),
            [
                (sample[1] - 1024) ** 2 + (sample[2] - 1024) ** 2
                for sample in samples
            ],
        )
        self.assertEqual(
            len(samples),
            len(set(sample[0] for sample in samples)),
        )
        for index, block_x, block_z in samples:
            self.assertGreaterEqual(index, 0)
            self.assertLess(index, logic.MAP_GRID_SIZE ** 2)
            self.assertTrue(
                logic.is_inside_map(
                    block_x,
                    block_z,
                    1024,
                    1024,
                )
            )
            self.assertLessEqual(
                (block_x - 1024) ** 2 + (block_z - 1024) ** 2,
                logic.DISCOVERY_RADIUS ** 2,
            )

        known = [sample[0] for sample in samples[:3]]
        missing = logic.discovery_cell_samples(
            player_x=1024,
            player_z=1024,
            center_x=1024,
            center_z=1024,
            known_indexes=known,
        )
        self.assertTrue(set(known).isdisjoint(sample[0] for sample in missing))

        string_known = [str(index) for index in known]
        missing_from_persisted_keys = logic.discovery_cell_samples(
            player_x=1024,
            player_z=1024,
            center_x=1024,
            center_z=1024,
            known_indexes=string_known,
        )
        self.assertTrue(
            set(known).isdisjoint(
                sample[0] for sample in missing_from_persisted_keys
            )
        )

    def test_discovery_scan_is_bounded_to_the_reveal_window(self):
        bounds = logic.discovery_candidate_bounds(
            player_x=1024,
            player_z=1024,
            center_x=1024,
            center_z=1024,
        )

        self.assertEqual((33, 31, 96, 96), bounds)
        self.assertLessEqual(
            (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]),
            4095,
        )

    def test_unchanged_biome_rectangles_require_no_pool_updates(self):
        cells = {
            "0": "forest",
            "1": "forest",
            "128": "forest",
            "129": "forest",
        }
        initial, updates, hidden = logic.rectangle_pool_delta((), cells, 128)
        self.assertEqual(1, len(initial))
        self.assertEqual([(0, initial[0])], updates)
        self.assertEqual([], hidden)

        current, updates, hidden = logic.rectangle_pool_delta(
            initial,
            cells,
            128,
        )
        self.assertEqual(initial, current)
        self.assertEqual([], updates)
        self.assertEqual([], hidden)

    def test_rectangle_changes_keep_unchanged_regions_when_prefix_is_added(self):
        grid_size = 8
        original_cells = {
            2 * grid_size + 2: "forest",
            4 * grid_size + 4: "lake",
            6 * grid_size + 6: "stream",
        }
        original = logic.biome_rectangles(original_cells, grid_size)
        updated_cells = dict(original_cells)
        updated_cells[0] = "clearing"

        current, added, removed = logic.biome_rectangle_changes(
            original,
            updated_cells,
            grid_size,
        )

        self.assertEqual(4, len(current))
        self.assertEqual(1, len(added))
        self.assertEqual([], removed)
        self.assertTrue(
            set(tuple(rectangle) for rectangle in original).issubset(
                set(tuple(rectangle) for rectangle in current)
            )
        )

    def test_rectangle_changes_preserve_exact_checkerboard_pixels(self):
        grid_size = 40
        cells = {
            row * grid_size + column: (
                "forest" if (row + column) % 2 == 0 else "lake"
            )
            for row in range(grid_size)
            for column in range(grid_size)
        }

        current, added, removed = logic.biome_rectangle_changes(
            (),
            cells,
            grid_size,
        )

        self.assertEqual(grid_size * grid_size, len(current))
        self.assertEqual(grid_size * grid_size, len(added))
        self.assertEqual([], removed)

    def test_rectangle_pool_coarsens_instead_of_dropping_explored_extent(self):
        grid_size = 8
        cells = {
            row * grid_size + column: (
                "forest" if (row + column) % 2 == 0 else "lake"
            )
            for row in range(grid_size)
            for column in range(grid_size)
        }

        current, _, _ = logic.rectangle_pool_delta(
            (),
            cells,
            grid_size,
            max_slots=4,
        )

        self.assertLessEqual(len(current), 4)
        for index in cells:
            row, column = divmod(index, grid_size)
            self.assertTrue(
                any(
                    row_start <= row < row_end
                    and column_start <= column < column_end
                    for (
                        row_start,
                        column_start,
                        row_end,
                        column_end,
                        _,
                    ) in current
                ),
                "explored pixel %s was dropped by the HUD budget" % index,
            )
        self.assertEqual(grid_size, max(rectangle[2] for rectangle in current))
        self.assertEqual(grid_size, max(rectangle[3] for rectangle in current))

    def test_rectangle_pool_preserves_priority_biome_during_coarsening(self):
        grid_size = 4
        cells = {
            row * grid_size + column: "forest"
            for row in range(grid_size)
            for column in range(grid_size)
        }
        cells[0] = "stream"

        current = logic.budgeted_biome_rectangles(
            cells,
            grid_size,
            max_rectangles=1,
        )

        self.assertEqual([[0, 0, 4, 4, "stream"]], current)

    def test_discovery_frontier_consumes_cached_candidates_with_a_cursor(self):
        candidates = [
            (10, 0, 0),
            (11, 16, 0),
            (12, 32, 0),
            (13, 48, 0),
        ]

        batch, cursor = logic.discovery_frontier_batch(
            candidates,
            known_indexes=(10, 12),
            cursor=0,
            max_samples=2,
        )

        self.assertEqual([(11, 16, 0), (13, 48, 0)], batch)
        self.assertEqual(4, cursor)
        empty, cursor = logic.discovery_frontier_batch(
            candidates,
            known_indexes=(10, 11, 12, 13),
            cursor=cursor,
            max_samples=2,
        )
        self.assertEqual([], empty)
        self.assertEqual(4, cursor)

    def test_discovery_pixels_match_upstream_membership_and_sample_origins(self):
        samples = logic.discovery_cell_samples(
            player_x=1024,
            player_z=1024,
            center_x=1024,
            center_z=1024,
        )
        actual = set(sample[0] for sample in samples)
        expected = set()
        viewer_column = viewer_row = logic.MAP_GRID_SIZE // 2
        radius_pixels = logic.DISCOVERY_RADIUS // logic.MAP_CELL_BLOCKS
        for column in range(
            viewer_column - radius_pixels + 1,
            viewer_column + radius_pixels,
        ):
            for row in range(
                viewer_row - radius_pixels - 1,
                viewer_row + radius_pixels,
            ):
                dx = column - viewer_column
                dz = row - viewer_row
                distance_squared = dx * dx + dz * dz
                fuzzy = distance_squared > (radius_pixels - 2) ** 2
                if (
                    distance_squared < radius_pixels ** 2
                    and (not fuzzy or (column + row) & 1)
                ):
                    expected.add(row * logic.MAP_GRID_SIZE + column)

        self.assertEqual(3025, len(actual))
        self.assertEqual(expected, actual)
        center_index = (
            viewer_row * logic.MAP_GRID_SIZE + viewer_column
        )
        center_sample = dict(
            (index, (block_x, block_z))
            for index, block_x, block_z in samples
        )[center_index]
        self.assertEqual((1024, 1024), center_sample)

    def test_discovery_work_is_budgeted_and_has_a_fuzzy_outer_edge(self):
        samples = logic.discovery_cell_samples(
            player_x=1024,
            player_z=1024,
            center_x=1024,
            center_z=1024,
            max_samples=96,
        )
        self.assertEqual(96, len(samples))
        first_batch = samples[:64]
        self.assertLess(min(sample[1] for sample in first_batch), 1024)
        self.assertGreater(max(sample[1] for sample in first_batch), 1024)
        self.assertLess(min(sample[2] for sample in first_batch), 1024)
        self.assertGreater(max(sample[2] for sample in first_batch), 1024)
        self.assertTrue(
            all(
                (index % logic.MAP_GRID_SIZE)
                + (index // logic.MAP_GRID_SIZE)
                != 0
                for index, _, _ in samples
            )
        )

        min_x, min_z, _, _ = logic.map_bounds(1024, 1024)
        edge_column = (
            1024 + logic.DISCOVERY_RADIUS - logic.MAP_CELL_BLOCKS // 2
            - min_x
        ) // logic.MAP_CELL_BLOCKS
        edge_row = (
            1024 - logic.MAP_CELL_BLOCKS // 2 - min_z
        ) // logic.MAP_CELL_BLOCKS
        self.assertFalse(
            logic.should_reveal_pixel(
                edge_column,
                edge_row,
                1024,
                1024,
                1024,
                1024,
            )
        )
        self.assertTrue(
            logic.should_reveal_pixel(
                edge_column,
                edge_row + 1,
                1024,
                1024,
                1024,
                1024,
            )
        )

    def test_biome_pixels_round_trip_through_bounded_palette_storage(self):
        persisted = {
            str(index): (
                "stream" if index % 13 == 0 else "dense_forest"
            )
            for index in range(logic.MAP_GRID_SIZE ** 2)
        }
        encoded = logic.encode_biome_pixels(persisted)
        self.assertIsInstance(encoded, str)
        self.assertLessEqual(len(encoded), 11000)
        self.assertEqual(
            logic.normalize_biome_cells(persisted),
            logic.decode_biome_pixels(encoded),
        )
        self.assertEqual({}, logic.decode_biome_pixels("not-base64"))

    def test_biome_palette_covers_catalog_without_reindexing_old_maps(self):
        legacy_palette = (
            None,
            "forest",
            "dense_forest",
            "oak_savannah",
            "mushroom_forest",
            "firefly_forest",
            "stream",
            "dense_mushroom_forest",
            "lake",
            "enchanted_forest",
            "clearing",
            "spooky_forest",
            "unknown",
        )
        self.assertEqual(
            legacy_palette,
            logic.TWILIGHT_BIOME_PALETTE[:len(legacy_palette)],
        )
        self.assertEqual(
            ("swamp", "fire_swamp", "dark_forest", "dark_forest_center"),
            logic.TWILIGHT_BIOME_PALETTE[len(legacy_palette):],
        )
        self.assertLessEqual(len(logic.TWILIGHT_BIOME_PALETTE), 32)
        self.assertEqual(
            set(biome_catalog.BIOMES_BY_KEY) | {logic.UNKNOWN_BIOME_KEY},
            set(logic.TWILIGHT_BIOME_KEYS),
        )

        cells = {
            "12": "swamp",
            "13": "fire_swamp",
            "14": "unknown",
            "15": "dark_forest",
            "16": "dark_forest_center",
        }
        self.assertEqual(
            cells,
            logic.decode_biome_pixels(logic.encode_biome_pixels(cells)),
        )

    def test_dark_forest_storage_still_reads_legacy_four_bit_maps(self):
        import base64
        import struct

        total_bytes = logic.MAP_GRID_SIZE * logic.MAP_GRID_SIZE // 2
        packed = [0] * total_bytes
        packed[0] = 13 | (14 << 4)
        legacy = base64.b64encode(
            struct.pack("%dB" % total_bytes, *packed)
        ).decode("ascii")
        self.assertEqual(
            {"0": "swamp", "1": "fire_swamp"},
            logic.decode_biome_pixels(legacy),
        )

    def test_all_432508_magic_map_landmarks_have_icons(self):
        self.assertEqual(
            {
                "small_hill",
                "medium_hill",
                "large_hill",
                "hedge_maze",
                "naga_courtyard",
                "lich_tower",
                "ice_tower",
                "quest_grove",
                "hydra_lair",
                "labyrinth",
                "dark_tower",
                "knight_stronghold",
                "yeti_cave",
                "troll_cave",
                "final_castle",
            },
            set(logic.LANDMARK_ICONS),
        )
        self.assertIsNone(logic.icon_for_landmark("mushroom_tower"))
        self.assertEqual("lich_tower", logic.icon_for_landmark("lich_tower"))

    def test_new_landmark_kind_replaces_stale_kind_at_same_position(self):
        merged = logic.merge_landmarks(
            {
                "small_hill:8,8": {
                    "kind": "small_hill",
                    "position": [8, 8],
                }
            },
            [{"kind": "lich_tower", "position": [8, 8]}],
        )
        self.assertEqual(["lich_tower:8,8"], sorted(merged))

    def test_discovery_filters_radius_sector_and_duplicates(self):
        candidates = [
            {"kind": "small_hill", "position": [8, 8]},
            {"kind": "small_hill", "position": [8, 8]},
            {"kind": "naga_courtyard", "position": [500, 0]},
            {"kind": "hedge_maze", "position": [513, 0]},
            {"kind": "lich_tower", "position": [16, 16]},
            {"kind": "quest_grove", "position": [1200, 0]},
        ]
        discovered = logic.discover_landmarks(
            candidates,
            player_x=0,
            player_z=0,
            center_x=1024,
            center_z=1024,
            radius=512,
        )
        self.assertEqual(
            [
                "small_hill:8,8",
                "lich_tower:16,16",
                "naga_courtyard:500,0",
            ],
            [entry["key"] for entry in discovered],
        )
        self.assertEqual(
            [
                "small_hill",
                "lich_tower",
                "naga_courtyard",
            ],
            [entry["kind"] for entry in discovered],
        )

    def test_432508_keeps_conquest_in_storage_but_not_map_packets(self):
        self.assertEqual(
            "twilightforest:1.20.1-4.3.2508",
            logic.MAGIC_MAP_RULESET,
        )
        discovered = logic.discover_landmarks(
            [
                {
                    "kind": "naga_courtyard",
                    "position": [264, -247],
                    "conquered": True,
                }
            ],
            player_x=264,
            player_z=-247,
            center_x=1024,
            center_z=-1024,
        )
        self.assertTrue(discovered[0]["conquered"])
        persisted = logic.merge_landmarks({}, discovered)
        self.assertTrue(
            persisted["naga_courtyard:264,-247"]["conquered"]
        )
        snapshot = logic.build_snapshot(
            1024,
            -1024,
            264,
            -247,
            33027004,
            persisted,
        )
        self.assertNotIn("conquered", snapshot["landmarks"][0])
        self.assertEqual(logic.MAGIC_MAP_RULESET, snapshot["ruleset"])

    def test_snapshot_is_bounded_and_sorted(self):
        persisted = {
            "naga_courtyard:500,0": {
                "kind": "naga_courtyard",
                "position": [500, 0],
            },
            "small_hill:8,8": {
                "kind": "small_hill",
                "position": [8, 8],
            },
            "invalid:4,4": {
                "kind": "lich_tower",
                "position": [4, 4],
            },
        }
        snapshot = logic.build_snapshot(
            center_x=1024,
            center_z=1024,
            player_x=12,
            player_z=34,
            dimension_id=33027004,
            persisted_landmarks=persisted,
            persisted_biomes={
                "33": "dense_forest",
                "0": "forest",
                "broken": "forest",
                "1024": "lake",
                "2": "not_a_twilight_biome",
            },
        )
        self.assertEqual(3, snapshot["schemaVersion"])
        self.assertEqual(128, snapshot["gridSize"])
        self.assertEqual(16, snapshot["cellBlocks"])
        self.assertEqual([1024, 1024], snapshot["center"])
        self.assertEqual([0, 0, 2047, 2047], snapshot["bounds"])
        self.assertEqual([12, 34], snapshot["player"])
        self.assertEqual(
            [
                [0, 0, 1, "forest"],
                [0, 33, 34, "dense_forest"],
                [8, 0, 1, "lake"],
            ],
            snapshot["biomeRuns"],
        )
        self.assertEqual(
            ["naga_courtyard:500,0", "small_hill:8,8"],
            [entry["key"] for entry in snapshot["landmarks"]],
        )

    def test_snapshot_carries_other_players_sharing_the_same_map(self):
        snapshot = logic.build_snapshot(
            1024,
            1024,
            1024,
            1024,
            33027004,
            {},
            {},
            41,
            players=[
                {"id": "other", "position": [1100, 900], "yaw": 90.0},
                {"id": "bad", "position": [1], "yaw": "bad"},
            ],
        )

        self.assertEqual(
            [
                {
                    "id": "other",
                    "position": [1100, 900],
                    "yaw": 90.0,
                }
            ],
            snapshot["players"],
        )


if __name__ == "__main__":
    unittest.main()
