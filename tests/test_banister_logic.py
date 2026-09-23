# -*- coding: utf-8 -*-
"""Upstream-compatible behavior contracts for player banisters."""

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))


class BanisterLogicTests(unittest.TestCase):
    def test_placement_shape_connects_only_below_a_banister(self):
        from TwilightBossSlice import banister_logic

        self.assertEqual(
            {
                "tf_slice:shape": "tall",
                "tf_slice:extended": False,
            },
            banister_logic.placement_states("minecraft:air"),
        )
        self.assertEqual(
            "connected",
            banister_logic.placement_states("tf_slice:dark_banister")[
                "tf_slice:shape"
            ],
        )

    def test_axe_cycle_matches_upstream_enum_order(self):
        from TwilightBossSlice import banister_logic

        states = banister_logic.placement_states("minecraft:air")
        states = banister_logic.cycle_states(states)
        self.assertEqual(("connected", False), banister_logic.mode(states))
        states = banister_logic.cycle_states(states)
        self.assertEqual(("short", False), banister_logic.mode(states))
        states = banister_logic.cycle_states(states)
        self.assertEqual(("tall", True), banister_logic.mode(states))

    def test_neighbor_updates_connect_and_disconnect_only_automatic_shapes(self):
        from TwilightBossSlice import banister_logic

        tall = {
            "tf_slice:shape": "tall",
            "tf_slice:extended": True,
            "minecraft:cardinal_direction": "west",
        }
        connected = banister_logic.connection_states(
            tall, "tf_slice:mangrove_banister"
        )
        self.assertEqual("connected", connected["tf_slice:shape"])
        self.assertTrue(connected["tf_slice:extended"])
        self.assertEqual("west", connected["minecraft:cardinal_direction"])
        disconnected = banister_logic.connection_states(
            connected, "minecraft:air"
        )
        self.assertEqual("tall", disconnected["tf_slice:shape"])
        short = dict(tall, **{"tf_slice:shape": "short"})
        self.assertEqual(
            "short",
            banister_logic.connection_states(
                short, "tf_slice:dark_banister"
            )["tf_slice:shape"],
        )

    def test_only_axes_activate_manual_shape_cycling(self):
        from TwilightBossSlice import banister_logic

        for item_name in (
            "minecraft:wooden_axe",
            "minecraft:netherite_axe",
            "tf_slice:knightmetal_axe",
            "tf_slice:diamond_minotaur_axe",
        ):
            self.assertTrue(banister_logic.is_axe(item_name), item_name)
        for item_name in (
            "minecraft:stick",
            "minecraft:iron_pickaxe",
            "tf_slice:mazebreaker_pickaxe",
        ):
            self.assertFalse(banister_logic.is_axe(item_name), item_name)

    def test_banisters_remain_custom_blocks_instead_of_fence_adapters(self):
        from TwilightBossSlice import vanilla_block_adapter_logic

        for family in ("dark", "mangrove"):
            name = "tf_slice:%s_banister" % family
            self.assertNotIn(
                name, vanilla_block_adapter_logic.VANILLA_BLOCK_ADAPTERS
            )
            args = {"fullName": name, "blockName": name}
            self.assertIsNone(
                vanilla_block_adapter_logic.adapt_placement_event(args)
            )
            self.assertEqual(name, args["fullName"])

    def test_generated_block_has_all_upstream_modes_and_waterlogging(self):
        from tools import build_public_block_shapes as builder

        document = builder.banister_block_document("mangrove")
        block = document["minecraft:block"]
        self.assertEqual("1.21.60", document["format_version"])
        self.assertEqual(
            {
                "tf_slice:shape": ["tall", "connected", "short"],
                "tf_slice:extended": [False, True],
            },
            block["description"]["states"],
        )
        self.assertEqual(
            {
                "minecraft:placement_direction": {
                    "enabled_states": ["minecraft:cardinal_direction"]
                }
            },
            block["description"]["traits"],
        )
        self.assertEqual(24, len(block["permutations"]))
        self.assertTrue(
            block["components"]["netease:neighborchanged_sendto_script"][
                "value"
            ]
        )
        liquid = block["components"]["minecraft:liquid_detection"]
        self.assertTrue(liquid["detection_rules"][0]["can_contain_liquid"])
        encoded = json.dumps(document)
        for shape in ("tall", "connected", "short"):
            for suffix in ("plain", "extended"):
                self.assertIn(
                    "geometry.tf_slice.wood_banister_%s_%s"
                    % (shape, suffix),
                    encoded,
                )
        self.assertNotIn("netease:connection", encoded)
        self.assertNotIn("netease:face_directional", encoded)
        self.assertIn("minecraft:cardinal_direction", encoded)
        self.assertNotIn("tf_slice:facing", encoded)

    def test_generated_geometry_matches_upstream_rail_and_support_layout(self):
        from tools import build_public_block_shapes as builder

        geometries = {
            entry["description"]["identifier"]: entry
            for entry in builder.banister_geometry_document()[
                "minecraft:geometry"
            ]
        }
        self.assertEqual(6, len(geometries))
        tall = geometries["geometry.tf_slice.wood_banister_tall_plain"]
        tall_cubes = tall["bones"][0]["cubes"]
        self.assertEqual(
            [[-8, 12, -8], [-5.5, 0, -8], [2.5, 0, -8]],
            [cube["origin"] for cube in tall_cubes],
        )
        self.assertEqual(
            {
                "uv": [0, 4],
                "uv_size": [12, 3],
                "uv_rotation": 270,
                "material_instance": "*",
            },
            tall_cubes[1]["uv"]["south"],
        )
        connected = geometries[
            "geometry.tf_slice.wood_banister_connected_plain"
        ]
        self.assertEqual(2, len(connected["bones"][0]["cubes"]))
        extended = geometries[
            "geometry.tf_slice.wood_banister_tall_extended"
        ]
        self.assertEqual(
            -8,
            min(cube["origin"][1] for cube in extended["bones"][0]["cubes"]),
        )

    def test_server_initializes_and_cycles_banister_states(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "banister_logic.placement_states", source
        )
        self.assertIn("def _initialize_placed_banister", source)
        self.assertIn("def _cycle_banister", source)
        self.assertIn("def _refresh_banister_connection", source)
        self.assertIn("CreateBlockUseEventWhiteList", source)
        self.assertIn("AddBlockItemListenForUseEvent", source)
        block_use = source[source.index("    def OnServerBlockUseEvent") :]
        self.assertIn("self._cycle_banister(args)", block_use)
        placement = source[
            source.index("    def _initialize_placed_banister") :
            source.index("    def OnServerEntityTryPlaceBlockEvent")
        ]
        self.assertNotIn("_get_rotation", placement)
        neighbor = source[source.index("    def OnBlockNeighborChanged") :]
        self.assertIn("self._refresh_banister_connection", neighbor)

    def test_survival_recipes_build_three_custom_banisters(self):
        for family, slab in (
            ("dark", "minecraft:dark_oak_slab"),
            ("mangrove", "minecraft:mangrove_slab"),
        ):
            path = BP / "recipes" / (family + "_banister.recipe.json")
            recipe = json.loads(path.read_text(encoding="utf-8"))[
                "minecraft:recipe_shaped"
            ]
            self.assertEqual(["---", "| |"], recipe["pattern"])
            self.assertEqual(slab, recipe["key"]["-"]["item"])
            self.assertEqual("minecraft:stick", recipe["key"]["|"]["item"])
            self.assertEqual(
                {"item": "tf_slice:%s_banister" % family, "count": 3},
                recipe["result"],
            )


if __name__ == "__main__":
    unittest.main()
