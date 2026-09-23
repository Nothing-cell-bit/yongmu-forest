# -*- coding: utf-8 -*-
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_ROOT = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
sys.path.insert(0, str(MODULE_ROOT))

import chat_command_logic


class RuinCommandFeedbackTests(unittest.TestCase):
    def test_long_ruin_catalog_is_split_into_visible_chat_lines(self):
        identifiers = ["long_ruin_identifier_%02d" % index for index in range(30)]
        lines = chat_command_logic.paginate_catalog(
            "Ruins",
            identifiers,
            max_chars=120,
        )
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(line.startswith("Ruins ") for line in lines))
        self.assertTrue(all(len(line) <= 120 for line in lines))
        combined = " ".join(lines)
        for identifier in identifiers:
            self.assertIn(identifier, combined)

    def test_empty_catalog_still_produces_one_feedback_line(self):
        self.assertEqual(
            ["Ruins (0/0): none"],
            chat_command_logic.paginate_catalog("Ruins", [], max_chars=120),
        )

    def test_locate_error_is_safe_and_user_visible(self):
        def failing_locate(*_args):
            raise RuntimeError("biome component unavailable")

        succeeded, detail = chat_command_logic.safe_debug_locate(
            failing_locate,
            "lich_tower",
            (0, 64, 0),
            8192,
        )
        self.assertFalse(succeeded)
        self.assertIn("locate failed", detail)
        self.assertIn("biome component unavailable", detail)


if __name__ == "__main__":
    unittest.main()
