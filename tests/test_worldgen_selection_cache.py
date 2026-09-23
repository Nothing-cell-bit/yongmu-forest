"""Selection equivalence and work budgets for native worldgen callbacks."""

import hashlib
import json
import pathlib
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from tests.test_structure_worldgen_handoff import FakeFactory, SERVICE


ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGIC_PATH = ROOT / "TwilightBossSliceB/TwilightBossSlice/ruin_worldgen_logic.py"
BASELINE_PATH = ROOT / "tests/worldgen_selection_baseline.json"


def fresh_logic():
    module = types.ModuleType("worldgen_selection_under_test")
    exec(compile(LOGIC_PATH.read_text(encoding="utf-8"), str(LOGIC_PATH), "exec"),
         module.__dict__)
    module._entry_diagnostics = None
    return module


def generation_digest(logic):
    """Hash full placement/ledger records, including edge tiles and event Y."""
    digest = hashlib.sha256()
    counts = {"surface": 0, "hollow_tree": 0, "rejected": 0}
    coordinates = list(range(-9, 10)) + [-129, -128, -127, -41, -40, -39, 39, 40, 41, 127, 128, 129]
    with mock.patch.object(SERVICE, "ruin_logic", logic):
        service = SERVICE.StructureWorldgenService(FakeFactory(), "level", 33027004)
        for seed in (0, -987654321, 16909743948298389873):
            service._world_seed = seed
            for mode in sorted(SERVICE.SURFACE_LANDMARK_TRIGGER_BY_MODE):
                for x in coordinates:
                    for z in coordinates:
                        y = 32 if (x + z) % 2 else 87
                        result = service._surface_native_tile(mode, x, z, y)
                        counts["surface" if result else "rejected"] += 1
                        digest.update(json.dumps([seed, mode, x, z, y, result],
                                      sort_keys=True, separators=(",", ":")).encode("utf-8"))
            for x in range(-32, 32):
                for z in range(-16, 16):
                    y = 44 + ((x + z) % 5)
                    result = service._hollow_tree_native_tile(x, z, y)
                    counts["hollow_tree" if result else "rejected"] += 1
                    digest.update(json.dumps([seed, "tree", x, z, y, result],
                                  sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {"sha256": digest.hexdigest(), "counts": counts}


class WorldgenSelectionCacheTests(unittest.TestCase):
    def setUp(self):
        self.logic = fresh_logic()

    def test_full_native_records_match_preoptimization_baseline(self):
        expected = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(expected, generation_digest(self.logic))

    def test_same_legacy_region_reuses_center_math(self):
        original = self.logic.java_long
        with mock.patch.object(self.logic, "java_long", wraps=original) as arithmetic:
            first = self.logic.nearest_landmark_center(-24, 8)
            cold_calls = arithmetic.call_count
            for x in range(-24, -8):
                for z in range(8, 24):
                    self.assertEqual(first, self.logic.nearest_landmark_center(x, z))
            self.assertGreater(cold_calls, 0)
            self.assertEqual(cold_calls, arithmetic.call_count)

    def test_same_region_reuses_variety_roll(self):
        original = self.logic.JavaRandom.next_int
        calls = []

        def count_roll(generator, bound):
            calls.append(bound)
            return original(generator, bound)

        with mock.patch.object(self.logic.JavaRandom, "next_int", count_roll):
            first = self.logic.pick_variety_landmark(32, 32, 87654321)
            for x in range(24, 40):
                for z in range(24, 40):
                    self.assertEqual(first, self.logic.pick_variety_landmark(x, z, 87654321))
        self.assertEqual([16], calls)

    def test_four_tree_tiles_share_presence_and_variant_rolls(self):
        for accepted in (False, True):
            logic = fresh_logic()
            cell = next((x, 20) for x in range(-80, 80, 2)
                        if bool(logic.hollow_tree_chunk_tile(x, 20, 17, 5)) == accepted)
            logic = fresh_logic()
            original = logic.landmark_stream_index
            with mock.patch.object(logic, "landmark_stream_index", wraps=original) as rolls:
                results = [logic.hollow_tree_chunk_tile(cell[0] + dx, cell[1] + dz, 17, 5)
                           for dx in (0, 1) for dz in (0, 1)]
                self.assertEqual(2 if accepted else 1, rolls.call_count)
            if accepted:
                self.assertEqual(4, len({(r["tileX"], r["tileZ"]) for r in results}))
                self.assertEqual(1, len({r["variant"] for r in results}))
            else:
                self.assertEqual([None] * 4, results)

    def test_outside_all_clearance_radii_skips_type_resolution(self):
        original = self.logic.resolve_variety_landmark
        with mock.patch.object(self.logic, "resolve_variety_landmark", wraps=original) as resolve:
            self.assertFalse(self.logic.is_inside_landmark_clearance(
                119, 119, 17, SERVICE.SUPPORTED_VARIETY, {"small_hill": 1, "large_hill": 2}))
            self.assertEqual(0, resolve.call_count)

    def test_clearance_strict_boundary_and_live_policy(self):
        logic = self.logic
        supported = set(SERVICE.SUPPORTED_VARIETY)
        kind = logic.resolve_variety_landmark(0, 0, 17, supported)
        radii = {kind: 2}
        self.assertTrue(logic.is_inside_landmark_clearance(39, 8, 17, supported, radii))
        self.assertFalse(logic.is_inside_landmark_clearance(40, 8, 17, supported, radii))
        radii[kind] = 3
        self.assertTrue(logic.is_inside_landmark_clearance(40, 8, 17, supported, radii))
        self.assertFalse(logic.is_inside_landmark_clearance(8, 8, 17, set(), radii))

    def test_supported_and_fallback_are_not_cached_with_raw_type(self):
        logic = self.logic
        self.assertEqual("lich_tower", logic.resolve_variety_landmark(0, 16, 1, {"lich_tower"}))
        self.assertIsNone(logic.resolve_variety_landmark(0, 16, 1, set()))
        self.assertEqual("mushroom_tower", logic.resolve_variety_landmark(
            0, 16, 1, {"lich_tower"}, "mushroom_tower"))

    def test_clearance_empty_negative_and_unused_invalid_radii(self):
        logic = self.logic
        supported = SERVICE.SUPPORTED_VARIETY
        kind = logic.resolve_variety_landmark(0, 0, 17, supported)
        for radii in ({}, {kind: -1}, {kind: 0}):
            self.assertFalse(logic.is_inside_landmark_clearance(8, 8, 17, supported, radii))
        self.assertTrue(logic.is_inside_landmark_clearance(
            8, 8, 17, supported, {kind: 2, "unused_kind": "invalid"}))

    def test_fifo_eviction_is_bounded_and_preserves_results(self):
        logic = self.logic
        first = (logic.nearest_landmark_center(-8, -8),
                 logic.pick_variety_landmark(-8, -8, 17),
                 logic.hollow_tree_chunk_tile(-8, -8, 17, 5))
        for index in range(logic.WORLDGEN_SELECTION_CACHE_MAX * 3):
            logic.nearest_landmark_center(index * 16, 0)
            logic.pick_variety_landmark(index * 16, 0, index)
            logic.hollow_tree_chunk_tile(index * 2, 0, index, 5)
        for cache in (logic._LANDMARK_CENTER_CACHE, logic._LANDMARK_VARIETY_CACHE,
                      logic._HOLLOW_TREE_CELL_CACHE):
            self.assertLessEqual(len(cache._values), logic.WORLDGEN_SELECTION_CACHE_MAX)
        self.assertEqual(first, (logic.nearest_landmark_center(-8, -8),
                                logic.pick_variety_landmark(-8, -8, 17),
                                logic.hollow_tree_chunk_tile(-8, -8, 17, 5)))

    def test_concurrent_duplicate_cache_fills_do_not_evict_extra_entries(self):
        cache = self.logic._SelectionCache(2)
        cache.put("empty", None)
        cache.put("hit", (1, 2))
        with ThreadPoolExecutor(max_workers=8) as workers:
            list(workers.map(lambda unused: cache.put("hit", (1, 2)), range(100)))
        self.assertIsNone(cache.get("empty"))
        self.assertEqual((1, 2), cache.get("hit"))
        cache.put("new", "result")
        self.assertIs(self.logic._SELECTION_CACHE_MISS, cache.get("empty"))
        self.assertEqual(2, len(cache._values))

    def test_tree_results_are_fresh_and_still_emit_each_tile_trace(self):
        logic = self.logic
        cell = next((x, 20) for x in range(-80, 80, 2)
                    if logic.hollow_tree_chunk_tile(x, 20, 17, 5))
        with mock.patch.object(logic, "_trace_worldgen") as trace:
            first = logic.hollow_tree_chunk_tile(cell[0], cell[1], 17, 5)
            expected = dict(first)
            first["variant"] = 9999
            first["tileX"] = 9999
            self.assertEqual(expected, logic.hollow_tree_chunk_tile(cell[0], cell[1], 17, 5))
            self.assertEqual(2, trace.call_count)

    def test_seed_variant_count_and_probability_remain_inputs(self):
        logic = self.logic
        expected = fresh_logic()
        for seed in (0, 17, -1, (1 << 64) - 1):
            for count in (1, 3, 7):
                for x in range(-6, 6):
                    self.assertEqual(expected.hollow_tree_chunk_tile(x, -2, seed, count),
                                     logic.hollow_tree_chunk_tile(x, -2, seed, count))
        logic.HOLLOW_TREE_CELL_CHANCE_NUMERATOR = 35
        self.assertTrue(all(logic.hollow_tree_chunk_tile(x, -2, 0, 3) for x in range(-6, 6)))
        with self.assertRaises(ValueError):
            logic.hollow_tree_chunk_tile(0, 0, 17, 0)

    def test_concurrent_chunk_callbacks_match_serial_results(self):
        arguments = [(x, z, seed, 5) for seed in (-1, 17)
                     for x in range(-24, 24) for z in range(-8, 8)]
        expected = [self.logic.hollow_tree_chunk_tile(*args) for args in arguments]
        logic = fresh_logic()
        with ThreadPoolExecutor(max_workers=8) as workers:
            actual = list(workers.map(lambda args: logic.hollow_tree_chunk_tile(*args), arguments))
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
