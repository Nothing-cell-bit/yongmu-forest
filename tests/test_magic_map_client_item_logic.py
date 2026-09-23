# -*- coding: utf-8 -*-
import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGIC_PATH = (
    ROOT
    / "TwilightBossSliceB"
    / "TwilightBossSlice"
    / "clientItemLogic.py"
)


def load_logic():
    spec = importlib.util.spec_from_file_location(
        "clientItemLogic",
        str(LOGIC_PATH),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MagicMapClientItemLogicTests(unittest.TestCase):
    def test_recognizes_the_custom_filled_magic_map(self):
        logic = load_logic()
        for item in (
            {"newItemName": "tf_slice:filled_magic_map"},
            {"itemName": "tf_slice:filled_magic_map"},
            {"newItemName": "filled_magic_map"},
            {"itemName": "filled_magic_map"},
        ):
            self.assertTrue(logic.is_filled_magic_map(item), item)

    def test_only_accepts_a_vanilla_map_when_it_has_tf_identity(self):
        logic = load_logic()
        for item in (
            {
                "itemName": "minecraft:filled_map",
                "extraId": "tfmm:v3:41:-1024:3072",
            },
            {
                "newItemName": "filled_map",
                "newItemExtraId": "tfmm:v2:41:-1024:3072",
            },
        ):
            self.assertTrue(logic.is_filled_magic_map(item), item)

        for item in (
            {"itemName": "minecraft:filled_map"},
            {"newItemName": "filled_map", "extraId": ""},
            {"itemName": "minecraft:filled_map", "extraId": "map_uuid:41"},
            {
                "itemName": "minecraft:filled_map",
                "extraId": "not_tfmm:v3:41:-1024:3072",
            },
        ):
            self.assertFalse(logic.is_filled_magic_map(item), item)

    def test_rejects_other_items_and_malformed_payloads(self):
        logic = load_logic()
        for item in (
            None,
            {},
            {"itemName": "tf_slice:magic_map"},
            {"newItemName": "minecraft:empty_map"},
            "tf_slice:filled_magic_map",
        ):
            self.assertFalse(logic.is_filled_magic_map(item), item)

    def test_event_payload_supports_nested_and_flat_item_shapes(self):
        logic = load_logic()
        for args in (
            {"newItemName": "tf_slice:filled_magic_map"},
            {"itemDict": {"itemName": "filled_magic_map"}},
            {"newItemDict": {"newItemName": "tf_slice:filled_magic_map"}},
            {
                "newItemDict": {
                    "itemName": "minecraft:filled_map",
                    "extraId": "tfmm:v3:9:0:0",
                }
            },
        ):
            self.assertTrue(logic.event_holds_filled_magic_map(args), args)

        self.assertFalse(
            logic.event_holds_filled_magic_map(
                {"newItemName": "minecraft:filled_map"}
            )
        )

    def test_signature_changes_when_player_switches_magic_map_identity(self):
        logic = load_logic()
        map_a = {
            "itemName": "tf_slice:filled_magic_map",
            "extraId": "tfmm:v3:7:1024:1024",
        }
        map_b = {
            "itemName": "tf_slice:filled_magic_map",
            "extraId": "tfmm:v3:9:3072:1024",
        }

        self.assertNotEqual(
            logic.filled_magic_map_signature(map_a),
            logic.filled_magic_map_signature(map_b),
        )
        self.assertIsNone(
            logic.filled_magic_map_signature(
                {"itemName": "minecraft:compass"}
            )
        )

    def test_held_map_hud_is_only_shown_in_first_person(self):
        logic = load_logic()

        self.assertTrue(logic.should_show_held_map(True, 0))
        self.assertFalse(logic.should_show_held_map(True, 1))
        self.assertFalse(logic.should_show_held_map(True, 2))
        self.assertFalse(logic.should_show_held_map(False, 0))
        # Preserve the current display when an older client cannot report a
        # perspective instead of making the map disappear completely.
        self.assertTrue(logic.should_show_held_map(True, None))
        self.assertTrue(logic.should_show_held_map(True, "unknown"))

    def test_local_item_observation_overrides_stale_server_held_state(self):
        logic = load_logic()

        self.assertFalse(
            logic.resolve_held_map_state(
                server_held=True,
                observed_items=(),
                observation_succeeded=True,
                event_main_held=False,
            )
        )
        self.assertTrue(
            logic.resolve_held_map_state(
                server_held=False,
                observed_items=(
                    {"itemName": "tf_slice:filled_magic_map"},
                ),
                observation_succeeded=True,
                event_main_held=False,
            )
        )
        self.assertTrue(
            logic.resolve_held_map_state(
                server_held=True,
                observed_items=(),
                observation_succeeded=False,
                event_main_held=None,
            )
        )

    def test_fresh_carried_event_controls_visibility_before_item_polling(self):
        logic = load_logic()

        self.assertTrue(
            logic.resolve_held_map_state(
                server_held=False,
                observed_items=(),
                observation_succeeded=False,
                event_main_held=True,
            )
        )
        self.assertFalse(
            logic.resolve_held_map_state(
                server_held=True,
                observed_items=(),
                observation_succeeded=False,
                event_main_held=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
