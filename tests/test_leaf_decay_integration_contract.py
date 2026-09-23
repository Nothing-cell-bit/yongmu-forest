# -*- coding: utf-8 -*-
"""Static integration contract for the NetEase leaf-decay runtime wiring."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = (
    ROOT
    / "TwilightBossSliceB"
    / "TwilightBossSlice"
    / "serverSystem.py"
)


class LeafDecayIntegrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SERVER.read_text(encoding="utf-8")

    def test_server_listens_for_actual_block_removal(self):
        self.assertIn(
            '"BlockRemoveServerEvent", self.OnBlockRemoveServerEvent',
            self.source,
        )
        self.assertIn("ListenOnBlockRemoveEvent(", self.source)
        self.assertIn("leaf_decay_logic.listener_block_ids()", self.source)

    def test_log_removal_queues_neighboring_leaves(self):
        start = self.source.index("    def OnBlockRemoveServerEvent")
        end = self.source.index("\n    def ", start + 5)
        handler = self.source[start:end]
        self.assertIn("leaf_decay_logic.is_support_log(blockName)", handler)
        self.assertIn("self._queue_neighbor_leaf_decay(", handler)

    def test_server_tick_processes_a_bounded_decay_queue(self):
        self.assertIn("self._leaf_decay_queue = {}", self.source)
        self.assertIn("self._process_leaf_decay_queue()", self.source)
        self.assertIn(
            "leaf_decay_logic.pop_due_candidates(", self.source
        )
        self.assertIn("LEAF_DECAY_TICK_BUDGET", self.source)
        start = self.source.index("    def _process_leaf_decay_queue")
        end = self.source.index("\n    def ", start + 5)
        handler = self.source[start:end]
        self.assertIn("leaf_decay_logic.is_decay_processing_tick(", handler)
        self.assertIn("LEAF_DECAY_PROCESS_INTERVAL_TICKS", handler)

    def test_persistent_leaf_still_propagates_support_loss_to_neighbors(self):
        start = self.source.index("    def _process_leaf_decay_queue")
        end = self.source.index("\n    def ", start + 5)
        handler = self.source[start:end]
        branch = handler[handler.index(
            "if key in self._persistent_leaf_positions:"
        ):]
        branch = branch[:branch.index("            supported =")]
        self.assertIn("_leaf_decay_bridge_propagated", branch)
        self.assertIn("self._queue_neighbor_leaf_decay(", branch)

    def test_nondecaying_leaf_bridges_propagate_the_removal_wave_once(self):
        start = self.source.index("    def _queue_neighbor_leaf_decay")
        end = self.source.index("\n    def ", start + 5)
        queue_method = self.source[start:end]
        self.assertIn("leaf_decay_logic.is_connecting_leaf(", queue_method)

        start = self.source.index("    def _process_leaf_decay_queue")
        end = self.source.index("\n    def ", start + 5)
        handler = self.source[start:end]
        self.assertIn("leaf_decay_logic.is_connecting_leaf(blockName)", handler)
        self.assertIn("_leaf_decay_bridge_propagated", handler)

    def test_successfully_placed_leaves_are_registered_as_persistent(self):
        self.assertIn(
            '"EntityPlaceBlockAfterServerEvent",',
            self.source,
        )
        start = self.source.index("    def OnEntityPlaceBlockAfterServerEvent")
        end = self.source.index("\n    def ", start + 5)
        handler = self.source[start:end]
        self.assertIn("_register_persistent_leaf_position", handler)
        self.assertIn("_persistent_leaf_positions", self.source)
        self.assertIn("_persist_leaf_decay_state", self.source)


if __name__ == "__main__":
    unittest.main()
