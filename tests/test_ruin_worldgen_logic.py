import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_ROOT = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
sys.path.insert(0, str(MODULE_ROOT))

import ruin_worldgen_logic as logic


class JavaCompatibilityTests(unittest.TestCase):
    def test_weighted_variant_slots_preserve_source_height_ratio(self):
        weights = [2, 2, 2, 2, 1, 1, 1, 1]
        selected = [
            logic.weighted_variant_index(weights, roll)
            for roll in range(sum(weights))
        ]

        self.assertEqual(
            [0, 0, 1, 1, 2, 2, 3, 3, 4, 5, 6, 7],
            selected,
        )

    def test_layout_and_surface_tile_selection_emit_sparse_diagnostics(self):
        class FakeDiagnostics(object):
            def __init__(self):
                self.events = []

            def write_worldgen_event(self, event, **fields):
                self.events.append((event, fields))
                return True

        diagnostics = FakeDiagnostics()
        original = logic._entry_diagnostics
        logic._entry_diagnostics = diagnostics
        try:
            selected = logic.landmark_stream_index(
                419629795777861470,
                8,
                8,
                "hedge_maze",
                "layout",
                7,
            )
            reference = logic.surface_native_tile_reference(
                "tf_slice/ruins/surface_native/hedge_maze/v04",
                "8,8",
                -3,
                2,
            )
        finally:
            logic._entry_diagnostics = original

        self.assertEqual(2, len(diagnostics.events))
        layout_event, layout_fields = diagnostics.events[0]
        self.assertEqual("worldgen.landmark.layout", layout_event)
        self.assertEqual(selected, layout_fields["selectedIndex"])
        self.assertEqual("hedge_maze", layout_fields["landmarkKind"])
        tile_event, tile_fields = diagnostics.events[1]
        self.assertEqual("worldgen.surface.tile", tile_event)
        self.assertEqual(reference, tile_fields["reference"])
        self.assertEqual([-3, 2], tile_fields["delta"])

    def test_repeated_layout_selection_reuses_the_deterministic_result(self):
        class FakeDiagnostics(object):
            def __init__(self):
                self.events = []

            def write_worldgen_event(self, event, **fields):
                self.events.append((event, fields))
                return True

        diagnostics = FakeDiagnostics()
        original = logic._entry_diagnostics
        logic._entry_diagnostics = diagnostics
        try:
            first = logic.landmark_stream_index(
                918273645,
                -503,
                264,
                "large_hill",
                "layout",
                8,
            )
            second = logic.landmark_stream_index(
                918273645,
                -503,
                264,
                "large_hill",
                "layout",
                8,
            )
        finally:
            logic._entry_diagnostics = original

        self.assertEqual(first, second)
        self.assertEqual(
            ["worldgen.landmark.layout"],
            [event for event, _fields in diagnostics.events],
        )

    def test_landmark_random_streams_are_deterministic_and_isolated(self):
        layout_seed = logic.landmark_stream_seed(
            123456789,
            264,
            -247,
            "naga_courtyard",
            "layout",
        )
        self.assertEqual(
            layout_seed,
            logic.landmark_stream_seed(
                123456789,
                264,
                -247,
                "naga_courtyard",
                "layout",
            ),
        )
        self.assertNotEqual(
            layout_seed,
            logic.landmark_stream_seed(
                123456789,
                264,
                -247,
                "naga_courtyard",
                "terrain",
            ),
        )
        self.assertNotEqual(
            layout_seed,
            logic.landmark_stream_seed(
                123456789,
                264,
                -247,
                "hedge_maze",
                "layout",
            ),
        )

    def test_landmark_stream_index_is_bounded_at_negative_coordinates(self):
        indexes = {
            logic.landmark_stream_index(
                987654321,
                -247,
                -503,
                "large_hill",
                "layout",
                8,
                salt,
            )
            for salt in range(32)
        }
        self.assertTrue(indexes)
        self.assertTrue(all(0 <= index < 8 for index in indexes))
        self.assertGreater(len(indexes), 1)

    def test_hollow_hill_terrain_detail_is_bounded_and_fades_at_edge(self):
        center = logic.hollow_hill_terrain_detail(
            0x48494C4C,
            56,
            56,
            56,
            2,
        )
        edge = logic.hollow_hill_terrain_detail(
            0x48494C4C,
            0,
            56,
            56,
            2,
        )
        self.assertGreaterEqual(center, -2)
        self.assertLessEqual(center, 2)
        self.assertEqual(0, edge)
        self.assertEqual(
            center,
            logic.hollow_hill_terrain_detail(
                0x48494C4C,
                56,
                56,
                56,
                2,
            ),
        )

    def test_hollow_hill_surface_target_never_lowers_existing_terrain(self):
        self.assertEqual(
            16,
            logic.hollow_hill_surface_target(16, 12, 1),
        )
        self.assertGreater(
            logic.hollow_hill_surface_target(16, 12, 16),
            16,
        )

    def test_java_random_matches_known_openjdk_sequence(self):
        random = logic.JavaRandom(0)
        self.assertEqual(
            [random.next_int(16) for _ in range(8)],
            [11, 13, 3, 9, 10, 4, 8, 1],
        )

    def test_landmark_centers_match_legacy_positive_and_negative_coordinates(self):
        self.assertEqual(logic.nearest_landmark_center(0, 0), (8, 8))
        self.assertEqual(logic.nearest_landmark_center(15, 15), (264, 264))
        self.assertEqual(logic.nearest_landmark_center(-16, -16), (-247, -247))

    def test_route_centers_use_nominal_grid_without_changing_legacy_jitter(self):
        differing = None
        for chunk_x in range(-64, 65, 16):
            for chunk_z in range(-64, 65, 16):
                legacy = logic.nearest_landmark_center(chunk_x, chunk_z)
                nominal = logic.nearest_route_landmark_center(
                    chunk_x,
                    chunk_z,
                )
                self.assertEqual((8, 8), (nominal[0] % 256, nominal[1] % 256))
                self.assertEqual(
                    legacy,
                    logic.legacy_landmark_center_for_nominal(*nominal),
                )
                if legacy != nominal and differing is None:
                    differing = (chunk_x, chunk_z, legacy, nominal)
        self.assertIsNotNone(differing)
        chunk_x, chunk_z, legacy, nominal = differing
        self.assertEqual(legacy, logic.nearest_landmark_center(chunk_x, chunk_z))
        self.assertNotEqual(legacy, nominal)

    def test_route_candidate_centers_are_nominal_and_region_complete(self):
        candidates = logic.route_landmark_center_candidates(17, 8)

        self.assertEqual(9, len(candidates))
        self.assertEqual(len(candidates), len(set(candidates)))
        self.assertTrue(
            all((x % 256, z % 256) == (8, 8) for x, z in candidates)
        )

    def test_boundary_chunk_considers_neighboring_landmark_centers(self):
        candidates = logic.landmark_center_candidates(17, 8)

        self.assertEqual((280, 56), candidates[0])
        self.assertIn((264, 264), candidates)
        self.assertEqual(9, len(candidates))
        self.assertEqual(len(candidates), len(set(candidates)))

    def test_variety_selection_keeps_upstream_lich_slots_but_resolves_them(self):
        supported = {
            "small_hill",
            "medium_hill",
            "large_hill",
            "hedge_maze",
            "naga_courtyard",
        }
        outcomes = {
            logic.pick_variety_landmark(chunk_x, chunk_z, 123456789)
            for chunk_x in range(-64, 65, 16)
            for chunk_z in range(-64, 65, 16)
        }
        self.assertTrue({"small_hill", "medium_hill", "large_hill", "hedge_maze"} <= outcomes)
        self.assertTrue({"naga_courtyard", "lich_tower"} <= outcomes)
        self.assertEqual(
            logic.ported_landmark("naga_courtyard", supported),
            "naga_courtyard",
        )
        self.assertIsNone(logic.ported_landmark("lich_tower", supported))
        self.assertEqual(logic.ported_landmark("hedge_maze", supported), "hedge_maze")
        resolved = {
            logic.resolve_variety_landmark(
                chunk_x,
                chunk_z,
                123456789,
                supported,
            )
            for chunk_x in range(-64, 65, 16)
            for chunk_z in range(-64, 65, 16)
        }
        self.assertNotIn(None, resolved)
        self.assertNotIn("lich_tower", resolved)
        self.assertTrue(
            {"naga_courtyard", "large_hill"} <= resolved
        )

    def test_raw_selection_matches_upstream_and_resolved_slots_remain_populated(self):
        raw_outcomes = [
            logic.pick_variety_landmark(chunk_x, chunk_z, 123456789)
            for chunk_x in range(-2048, 2048, 16)
            for chunk_z in range(-2048, 2048, 16)
        ]
        outcomes = [
            logic.resolve_variety_landmark(
                chunk_x,
                chunk_z,
                123456789,
                {
                    "small_hill",
                    "medium_hill",
                    "large_hill",
                    "hedge_maze",
                    "naga_courtyard",
                },
            )
            for chunk_x in range(-2048, 2048, 16)
            for chunk_z in range(-2048, 2048, 16)
        ]
        total = float(len(raw_outcomes))
        raw_lich_share = raw_outcomes.count("lich_tower") / total
        naga_share = outcomes.count("naga_courtyard") / total
        hollow_hill_share = sum(
            outcomes.count(kind)
            for kind in ("small_hill", "medium_hill", "large_hill")
        ) / total
        lich_share = outcomes.count("lich_tower") / total

        self.assertGreater(raw_lich_share, 0.14)
        self.assertLess(raw_lich_share, 0.17)
        self.assertGreater(naga_share, 0.21)
        self.assertLess(naga_share, 0.24)
        self.assertGreater(hollow_hill_share, 0.64)
        self.assertLess(hollow_hill_share, 0.68)
        self.assertEqual(0.0, lich_share)
        self.assertNotIn(None, outcomes)

    def test_dense_mushroom_can_reuse_only_unported_slots_for_towers(self):
        supported = {
            "small_hill",
            "medium_hill",
            "large_hill",
            "hedge_maze",
            "naga_courtyard",
        }
        tower_seen = False
        generic_seen = False
        for chunk_x in range(-256, 257, 16):
            for chunk_z in range(-256, 257, 16):
                raw = logic.pick_variety_landmark(
                    chunk_x,
                    chunk_z,
                    123456789,
                )
                resolved = logic.resolve_variety_landmark(
                    chunk_x,
                    chunk_z,
                    123456789,
                    supported,
                    "mushroom_tower",
                )
                if raw == "lich_tower":
                    tower_seen = True
                    self.assertEqual("mushroom_tower", resolved)
                else:
                    generic_seen = True
                    self.assertEqual(raw, resolved)
        self.assertTrue(tower_seen)
        self.assertTrue(generic_seen)

    def test_small_ruin_clearance_matches_selected_landmark_radius(self):
        radii = {
            "small_hill": 1,
            "medium_hill": 2,
            "large_hill": 3,
            "hedge_maze": 2,
        }
        supported = set(radii)
        self.assertTrue(
            logic.is_inside_landmark_clearance(
                39, 8, 123456789, supported, radii
            )
        )
        self.assertFalse(
            logic.is_inside_landmark_clearance(
                40, 8, 123456789, supported, radii
            )
        )
        self.assertFalse(
            logic.is_inside_landmark_clearance(8, 8, 256, supported, radii)
        )

    def test_landmark_centers_in_radius_are_unique_nearest_first(self):
        centers = logic.landmark_centers_in_radius(0, 0, 600)

        self.assertTrue(centers)
        self.assertEqual(len(centers), len(set(centers)))
        self.assertEqual((8, 8), centers[0])
        distances = [
            center_x * center_x + center_z * center_z
            for center_x, center_z in centers
        ]
        self.assertEqual(distances, sorted(distances))
        self.assertTrue(
            all(distance <= 600 * 600 for distance in distances)
        )

    def test_only_the_actual_landmark_center_chunk_claims_generation(self):
        self.assertTrue(logic.is_landmark_center_chunk(0, 0))
        self.assertTrue(logic.is_landmark_center_chunk(-16, 0))
        self.assertFalse(logic.is_landmark_center_chunk(1, 0))
        self.assertFalse(logic.is_landmark_center_chunk(-15, 0))

    def test_courtyard_surface_is_flat_then_blends_back_to_terrain(self):
        self.assertEqual(
            64,
            logic.blended_surface_height(72, 64, 48.0, 48.0, 8.0),
        )
        self.assertEqual(
            68,
            logic.blended_surface_height(72, 64, 52.0, 48.0, 8.0),
        )
        self.assertEqual(
            72,
            logic.blended_surface_height(72, 64, 56.0, 48.0, 8.0),
        )
        self.assertEqual(
            65,
            logic.blended_surface_height(72, 64, 50.0, 48.0, 8.0),
        )

    def test_hollow_hill_profile_has_a_shell_and_a_real_cavity(self):
        center = logic.hollow_hill_profile(100, 0.0)
        shoulder = logic.hollow_hill_profile(100, 25.0)
        edge = logic.hollow_hill_profile(100, 56.0)

        self.assertEqual(37, center["surface"])
        self.assertEqual(1, center["cavityFloor"])
        self.assertGreater(center["cavityCeiling"], center["cavityFloor"])
        self.assertGreater(center["surface"], shoulder["surface"])
        self.assertEqual(0, edge["surface"])
        self.assertIsNone(logic.hollow_hill_profile(100, 56.1))

    def test_hollow_hill_controlled_spawn_tables_match_432508(self):
        self.assertEqual(
            ("minecraft:spider", "minecraft:zombie", "tf_slice:redcap",
             "tf_slice:swarm_spider", "tf_slice:kobold"),
            tuple(
                entry[0]
                for entry in logic.HOLLOW_HILL_CONTROLLED_SPAWNS[
                    "small_hill"
                ]
            ),
        )
        medium = logic.HOLLOW_HILL_CONTROLLED_SPAWNS["medium_hill"]
        large = logic.HOLLOW_HILL_CONTROLLED_SPAWNS["large_hill"]
        self.assertIn(("tf_slice:redcap_sapper", 1, 1, 2), medium)
        self.assertIn(("tf_slice:fire_beetle", 5, 1, 1), medium)
        self.assertIn(("minecraft:enderman", 1, 1, 1), large)
        self.assertIn(("tf_slice:wraith", 2, 1, 2), large)
        self.assertIn(("tf_slice:pinch_beetle", 10, 1, 2), large)

    def test_hollow_hill_spawn_choice_is_weighted_and_deterministic(self):
        first = logic.hollow_hill_spawn_choice("large_hill", 12345)
        second = logic.hollow_hill_spawn_choice("large_hill", 12345)

        self.assertEqual(first, second)
        self.assertIn(
            first["identifier"],
            logic.HOLLOW_HILL_CONTROLLED_MOBS,
        )
        self.assertGreaterEqual(first["count"], 1)
        self.assertIsNone(
            logic.hollow_hill_spawn_choice("naga_courtyard", 12345)
        )

    def test_controlled_hill_custom_mobs_have_both_entity_definitions(self):
        behavior_entities = ROOT / "TwilightBossSliceB" / "entities"
        resource_entities = ROOT / "TwilightBossSliceR" / "entity"
        for identifier in logic.HOLLOW_HILL_CONTROLLED_MOBS:
            if not identifier.startswith("tf_slice:"):
                continue
            mob_name = identifier.split(":", 1)[1]
            self.assertTrue(
                (behavior_entities / ("%s.entity.json" % mob_name)).is_file(),
                identifier,
            )
            self.assertTrue(
                (resource_entities / ("%s.entity.json" % mob_name)).is_file(),
                identifier,
            )

    def test_hollow_hill_spawn_region_requires_a_completed_physical_cavity(self):
        job = logic.create_landmark_job(
            "small_hill",
            (0, 64, 0),
            0,
            [],
            [0, 60, 0, 47, 80, 47],
        )
        job["state"] = "complete"
        cavity = logic.hollow_hill_cavity_range(job, 23.5, 23.5)
        player = {
            "dimensionId": 33027004,
            "position": (23.5, cavity[0], 23.5),
        }

        self.assertTrue(
            logic.player_inside_completed_hollow_hill(
                job,
                player,
                33027004,
            )
        )
        player["position"] = (0.5, cavity[0], 0.5)
        self.assertFalse(
            logic.player_inside_completed_hollow_hill(
                job,
                player,
                33027004,
            )
        )
        player["dimensionId"] = 0
        self.assertFalse(
            logic.player_inside_completed_hollow_hill(
                job,
                player,
                33027004,
            )
        )

    def test_generated_hollow_hill_cavity_includes_tapered_edge(self):
        job = {
            "kind": "small_hill",
            "anchor": [0, 64, 0],
        }
        self.assertIsNone(logic.hollow_hill_cavity_range(job, 6, 23))
        self.assertIsNotNone(
            logic.hollow_hill_generated_cavity_range(job, 6, 23)
        )

    def test_hollow_hill_spawn_candidates_stay_on_the_cavity_floor(self):
        job = logic.create_landmark_job(
            "medium_hill",
            (100, 70, 200),
            0,
            [],
            [100, 65, 200, 179, 96, 279],
        )
        job["state"] = "complete"
        candidates = logic.hollow_hill_spawn_candidates(
            job,
            (139.5, 68.0, 239.5),
            987654321,
            8,
        )

        self.assertEqual(8, len(candidates))
        for position, yaw in candidates:
            cavity = logic.hollow_hill_cavity_range(
                job,
                position[0],
                position[2],
            )
            self.assertEqual(float(cavity[0]), position[1])
            self.assertGreaterEqual(yaw, 0.0)
            self.assertLess(yaw, 360.0)


class LandmarkJobTests(unittest.TestCase):
    def test_minoshroom_activation_has_source_upper_height_limit_without_progress_gate(self):
        job = logic.create_landmark_job(
            "labyrinth",
            (100, 64, 200),
            0,
            [],
        )
        job["state"] = "complete"
        job["bossSpawner"] = {
            "offset": [7, 2, 7],
            "activationRadius": 9,
            "spawnYOffset": -1.5,
            "maxPlayerYOffset": 3.5,
        }
        allowed = [
            {
                "dimensionId": 33027004,
                "position": (107.5, 65.0, 207.5),
                "progress": {},
            }
        ]
        too_high = [
            {
                "dimensionId": 33027004,
                "position": (107.5, 71.0, 207.5),
                "progress": {},
            }
        ]

        self.assertEqual(
            (107.5, 65.0, 207.5),
            logic.boss_activation_position(job, allowed, 33027004),
        )
        self.assertIsNone(
            logic.boss_activation_position(job, too_high, 33027004)
        )

    def test_completed_courtyard_activates_once_a_player_enters_range(self):
        job = logic.create_landmark_job(
            "naga_courtyard",
            (100, 64, 200),
            0,
            [{"structure": "tf_slice/ruins/naga_courtyard/x000_z000", "offset": [0, 0, 0]}],
        )
        job["state"] = "complete"
        job["bossSpawner"] = {
            "offset": [48, 1, 48],
            "activationRadius": 32,
        }
        far_players = [
            {"dimensionId": 33027004, "position": (200.0, 65.0, 300.0)}
        ]
        near_players = [
            {"dimensionId": 33027004, "position": (148.5, 65.0, 275.0)}
        ]

        self.assertIsNone(
            logic.courtyard_activation_position(job, far_players, 33027004)
        )
        self.assertEqual(
            (148.5, 66.0, 248.5),
            logic.courtyard_activation_position(
                job,
                near_players,
                33027004,
            ),
        )

        job["bossSpawned"] = True
        self.assertIsNone(
            logic.courtyard_activation_position(job, near_players, 33027004)
        )

    def test_courtyard_activates_when_spawner_piece_is_ready(self):
        job = logic.create_landmark_job(
            "naga_courtyard",
            (100, 64, 200),
            0,
            [
                {
                    "structure": (
                        "tf_slice/ruins/naga_courtyard/x000_z000"
                    ),
                    "offset": [0, 0, 0],
                }
            ],
        )
        job["state"] = "placing"
        job["bossSpawner"] = {
            "offset": [8, 1, 8],
            "activationRadius": 32,
        }
        players = [
            {"dimensionId": 33027004, "position": (108.5, 65.0, 208.5)}
        ]

        self.assertIsNone(
            logic.courtyard_activation_position(job, players, 33027004)
        )

        job["bossSpawnerReady"] = True
        self.assertEqual(
            (108.5, 66.0, 208.5),
            logic.courtyard_activation_position(job, players, 33027004),
        )

    def test_courtyard_activates_when_player_reaches_the_outer_wall(self):
        job = logic.create_landmark_job(
            "naga_courtyard",
            (100, 64, 200),
            0,
            [],
        )
        job["state"] = "complete"
        job["bossSpawner"] = {
            "offset": [52, 1, 52],
            "activationRadius": 64,
        }
        job["bossSpawnerReady"] = True
        players = [
            {
                "dimensionId": 33027004,
                "position": (204.5, 65.0, 252.5),
            }
        ]

        self.assertEqual(
            (152.5, 66.0, 252.5),
            logic.courtyard_activation_position(job, players, 33027004),
        )

    def test_piece_queue_is_deterministic_and_one_piece_can_be_claimed(self):
        pieces = [
            {"structure": "tf_slice/ruins/hedge/0_0", "offset": [0, 0, 0]},
            {"structure": "tf_slice/ruins/hedge/1_0", "offset": [16, 0, 0]},
        ]
        job = logic.create_landmark_job("hedge_maze", (8, 64, 8), 7, pieces)
        self.assertEqual(job["state"], "planned")
        self.assertEqual(job["nextPiece"], 0)

        claimed = logic.claim_next_pieces(job, 1)
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0]["structure"], pieces[0]["structure"])
        self.assertEqual(job["nextPiece"], 1)
        self.assertEqual(job["state"], "placing")

    def test_piece_queue_preserves_structure_placement_controls(self):
        job = logic.create_landmark_job(
            "small_hill",
            (0, 64, 0),
            0,
            [
                {
                    "structure": "shell",
                    "offset": [0, -4, 0],
                    "layer": "shell",
                    "removeBlock": True,
                    "rotation": 90,
                    "mirror": 1,
                }
            ],
        )

        self.assertEqual("shell", job["pieces"][0]["layer"])
        self.assertTrue(job["pieces"][0]["removeBlock"])
        self.assertEqual(90, job["pieces"][0]["rotation"])
        self.assertEqual(1, job["pieces"][0]["mirror"])

    def test_jobs_complete_idempotently_and_stop_after_three_failures(self):
        job = logic.create_landmark_job(
            "hollow_hill_small",
            (8, 64, 8),
            3,
            [{"structure": "tf_slice/ruins/hill/0_0", "offset": [0, 0, 0]}],
        )
        logic.claim_next_pieces(job, 1)
        self.assertTrue(logic.complete_if_finished(job))
        self.assertEqual(job["state"], "complete")
        self.assertEqual(logic.claim_next_pieces(job, 1), [])

        failed = logic.create_landmark_job("hedge_maze", (8, 64, 8), 1, [])
        for _ in range(3):
            logic.record_job_failure(failed)
        self.assertEqual(failed["state"], "failed")
        self.assertEqual(failed["retries"], 3)

    def test_overlapping_landmark_bounds_are_rejected(self):
        first = {"bounds": [0, 0, 0, 50, 20, 50], "state": "complete"}
        touching = {"bounds": [49, 0, 49, 80, 20, 80], "state": "planned"}
        separate = {"bounds": [51, 0, 51, 80, 20, 80], "state": "planned"}
        self.assertTrue(logic.bounds_overlap(first["bounds"], touching["bounds"]))
        self.assertFalse(logic.bounds_overlap(first["bounds"], separate["bounds"]))


if __name__ == "__main__":
    unittest.main()
