# -*- coding: utf-8 -*-
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
R = ROOT / "TwilightBossSliceR"


class FireReactUiContractTests(unittest.TestCase):
    def test_ui_is_registered_and_packaged(self):
        config = (B / "config.py").read_text(encoding="utf-8")
        client = (B / "clientSystem.py").read_text(encoding="utf-8")
        ui_defs = json.loads((R / "ui" / "_ui_defs.json").read_text(encoding="utf-8"))

        self.assertIn('FIRE_REACT_UI_NAME = "FireReactUI"', config)
        self.assertIn("TwilightBossSlice.fireReactUI.FireReactUI", client)
        self.assertIn("ui/fire_react.json", ui_defs["ui_defs"])

    def test_screen_offers_four_explicit_armor_choices(self):
        layout = json.loads((R / "ui" / "fire_react.json").read_text(encoding="utf-8"))
        self.assertIn("main", layout)
        encoded = json.dumps(layout, ensure_ascii=False)
        for index in range(4):
            self.assertIn("armor_%d" % index, encoded)

        module = (B / "fireReactUI.py").read_text(encoding="utf-8")
        self.assertIn("SetButtonTouchUpCallback", module)
        self.assertIn("set_submit_callback", module)

    def test_open_and_apply_are_separate_server_authoritative_events(self):
        server = (B / "serverSystem.py").read_text(encoding="utf-8")
        client = (B / "clientSystem.py").read_text(encoding="utf-8")

        self.assertIn('"FireReactOpen"', server)
        self.assertIn('"FireReactApplyRequest"', server)
        self.assertIn("def OnFireReactApplyRequest", server)
        self.assertIn('"FireReactOpen"', client)
        self.assertIn('NotifyToServer("FireReactApplyRequest"', client)
        self.assertIn("_fire_react_sessions", server)


if __name__ == "__main__":
    unittest.main()
