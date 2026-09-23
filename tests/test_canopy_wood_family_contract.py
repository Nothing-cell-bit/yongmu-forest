# -*- coding: utf-8 -*-
"""Contracts for the Canopy family using the native Cherry templates."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools import build_creative_catalog
from tools import build_localization
from tools import build_public_block_shapes as builder
from TwilightBossSliceB.TwilightBossSlice import vanilla_block_adapter_logic


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"


class CanopyWoodFamilyContractTests(unittest.TestCase):
    def test_canopy_shapes_reuse_one_unused_native_family(self):
        self.assertEqual("cherry", builder.CANOPY_NATIVE_TEMPLATE_FAMILY)
        self.assertEqual(
            (
                "stairs",
                "slab",
                "button",
                "fence",
                "fence_gate",
                "pressure_plate",
                "door",
                "trapdoor",
            ),
            builder.CANOPY_NATIVE_SUFFIXES,
        )
        for suffix in builder.CANOPY_NATIVE_SUFFIXES:
            self.assertEqual(
                "minecraft:cherry_" + suffix,
                vanilla_block_adapter_logic.VANILLA_BLOCK_ADAPTERS[
                    "tf_slice:canopy_" + suffix
                ],
            )

    def test_native_shapes_are_not_registered_as_custom_blocks(self):
        for suffix in builder.CANOPY_NATIVE_SUFFIXES:
            name = "canopy_" + suffix
            self.assertNotIn(name, builder.CANOPY_CUSTOM_SUFFIXES)
            self.assertIn(
                "TwilightBossSliceB/netease_blocks/%s.json" % name,
                builder.canopy_removed_artifacts(),
            )
            self.assertIn(
                "TwilightBossSliceR/models/netease_block/"
                "tf_slice_public_%s.json" % name,
                builder.canopy_removed_artifacts(),
            )

    def test_only_non_native_exceptions_remain_custom(self):
        self.assertEqual(
            ("banister", "bookshelf", "chest"),
            builder.CANOPY_CUSTOM_SUFFIXES,
        )
        banister = builder.canopy_shape_document("banister")["minecraft:block"]
        self.assertEqual(24, len(banister["permutations"]))
        for suffix in ("bookshelf", "chest"):
            document = builder.canopy_shape_document(suffix)
            self.assertEqual("1.10.0", document["format_version"])
            self.assertFalse(
                document["minecraft:block"]["description"][
                    "register_to_creative_menu"
                ]
            )

    def test_native_client_entries_use_canopy_textures(self):
        client_blocks = {}
        builder.ensure_vanilla_adapter_client_blocks(client_blocks)
        planks = "tf_slice:canopy_planks"
        for suffix in (
            "stairs",
            "slab",
            "button",
            "fence",
            "fence_gate",
            "pressure_plate",
        ):
            self.assertEqual(
                {"textures": planks, "sound": "wood"},
                client_blocks["cherry_" + suffix],
            )
        self.assertEqual(
            {"textures": "cherry_trapdoor", "sound": "wood"},
            client_blocks["cherry_trapdoor"],
        )
        self.assertEqual(
            {"textures": planks, "sound": "wood"},
            client_blocks["cherry_double_slab"],
        )
        self.assertEqual(
            {
                "textures": {
                    "up": "tf_slice:canopy_door_lower",
                    "down": "tf_slice:canopy_door_lower",
                    "side": "tf_slice:canopy_door_upper",
                },
                "sound": "wood",
            },
            client_blocks["cherry_door"],
        )
        for unsupported in (
            "cherry_sign",
            "cherry_wall_sign",
            "cherry_hanging_sign",
            "cherry_wall_hanging_sign",
        ):
            self.assertNotIn(unsupported, client_blocks)

    def test_native_texture_aliases_are_not_rotated_static_models(self):
        atlas = {}
        builder.ensure_vanilla_adapter_textures(atlas)
        self.assertEqual(
            {"textures": "textures/blocks/canopy_planks"},
            atlas["cherry_planks"],
        )
        self.assertEqual(
            {"textures": "textures/blocks/canopy_trapdoor"},
            atlas["cherry_trapdoor"],
        )
        self.assertEqual(
            {"textures": "textures/blocks/canopy_door_lower"},
            atlas["cherry_door_bottom"],
        )
        self.assertEqual(
            {"textures": "textures/blocks/canopy_door_upper"},
            atlas["cherry_door_top"],
        )

    def test_recipes_output_native_items_like_mangrove(self):
        recipes = builder.canopy_recipe_documents()
        for suffix in builder.CANOPY_NATIVE_SUFFIXES:
            recipe = recipes[suffix]
            value = recipe.get("minecraft:recipe_shaped") or recipe.get(
                "minecraft:recipe_shapeless"
            )
            self.assertEqual(
                "minecraft:cherry_" + suffix,
                value["result"]["item"],
                suffix,
            )
        for suffix in builder.CANOPY_CUSTOM_SUFFIXES:
            recipe = recipes[suffix]
            value = recipe.get("minecraft:recipe_shaped") or recipe.get(
                "minecraft:recipe_shapeless"
            )
            self.assertEqual(
                "tf_slice:canopy_" + suffix,
                value["result"]["item"],
                suffix,
            )

    def test_twilight_catalog_keeps_only_custom_canopy_exceptions(self):
        migrated = {
            "tf_slice:canopy_" + suffix
            for suffix in builder.CANOPY_NATIVE_SUFFIXES
        }
        self.assertTrue(
            migrated.issubset(build_creative_catalog.MIGRATED_WOOD_ALIAS_IDS)
        )
        self.assertTrue(
            migrated.isdisjoint(build_creative_catalog.CANOPY_PUBLIC_IDS)
        )
        self.assertEqual(
            (
                "tf_slice:canopy_log",
                "tf_slice:canopy_wood",
                "tf_slice:stripped_canopy_log",
                "tf_slice:stripped_canopy_wood",
                "tf_slice:canopy_planks",
                "tf_slice:canopy_banister",
                "tf_slice:canopy_bookshelf",
                "tf_slice:canopy_chest",
            ),
            build_creative_catalog.CANOPY_CONSTRUCTION_ORDER,
        )

    def test_native_cherry_names_are_presented_as_canopy(self):
        expected = {
            "tile.cherry_stairs.name": ("Canopy Stairs", "苍穹木楼梯"),
            "tile.cherry_slab.name": ("Canopy Slab", "苍穹木台阶"),
            "tile.cherry_button.name": ("Canopy Button", "苍穹木按钮"),
            "tile.cherry_fence.name": ("Canopy Fence", "苍穹木栅栏"),
            "tile.cherry_fence_gate.name": (
                "Canopy Fence Gate",
                "苍穹木栅栏门",
            ),
            "tile.cherry_pressure_plate.name": (
                "Canopy Pressure Plate",
                "苍穹木压力板",
            ),
            "item.cherry_door.name": ("Canopy Door", "苍穹木门"),
            "tile.cherry_trapdoor.name": (
                "Canopy Trapdoor",
                "苍穹木活板门",
            ),
        }
        self.assertTrue(
            set(expected.items()).issubset(
                {
                    (key, (english, chinese))
                    for key, english, chinese in (
                        build_localization.NATIVE_WOOD_NAME_OVERRIDES
                    )
                }
            )
        )

    def test_generated_catalog_has_no_native_alias_duplicates(self):
        catalog = json.loads(
            (BP / "item_catalog" / "crafting_item_catalog.json").read_text(
                encoding="utf-8"
            )
        )
        items = {
            identifier
            for category in catalog["minecraft:crafting_items_catalog"][
                "categories"
            ]
            for group in category.get("groups", [])
            for identifier in group.get("items", [])
        }
        for suffix in builder.CANOPY_NATIVE_SUFFIXES:
            self.assertNotIn("tf_slice:canopy_" + suffix, items)
            self.assertNotIn("minecraft:cherry_" + suffix, items)

    def test_scoped_rebuild_retires_aliases_and_publishes_native_templates(self):
        with tempfile.TemporaryDirectory(prefix="tf-canopy-native-") as temp:
            root = Path(temp)
            bp = root / "TwilightBossSliceB"
            rp = root / "TwilightBossSliceR"
            for folder in (
                "netease_blocks",
                "recipes",
                "item_catalog",
                "items",
                "entities",
            ):
                source = BP / folder
                if source.is_dir():
                    shutil.copytree(source, bp / folder)
            (rp / "textures").mkdir(parents=True)
            (rp / "texts").mkdir(parents=True)
            shutil.copy2(RP / "blocks.json", rp / "blocks.json")
            for atlas in ("terrain_texture.json", "item_texture.json"):
                shutil.copy2(RP / "textures" / atlas, rp / "textures" / atlas)
            for language in ("en_US.lang", "zh_CN.lang"):
                shutil.copy2(RP / "texts" / language, rp / "texts" / language)

            with mock.patch.object(builder, "ROOT", root), mock.patch.object(
                builder, "BP", bp
            ), mock.patch.object(builder, "RP", rp):
                builder.build_canopy_wood_family()

            client_blocks = json.loads(
                (rp / "blocks.json").read_text(encoding="utf-8")
            )
            catalog = json.loads(
                (bp / "item_catalog" / "crafting_item_catalog.json").read_text(
                    encoding="utf-8"
                )
            )
            items = {
                item
                for category in catalog["minecraft:crafting_items_catalog"][
                    "categories"
                ]
                for group in category.get("groups", [])
                for item in group.get("items", [])
            }
            for suffix in builder.CANOPY_NATIVE_SUFFIXES:
                name = "canopy_" + suffix
                self.assertFalse((bp / "netease_blocks" / (name + ".json")).exists())
                self.assertNotIn("tf_slice:" + name, client_blocks)
                self.assertIn("cherry_" + suffix, client_blocks)
                self.assertNotIn("tf_slice:" + name, items)
                self.assertNotIn("minecraft:cherry_" + suffix, items)
            for unsupported in (
                "cherry_sign",
                "cherry_wall_sign",
                "cherry_hanging_sign",
                "cherry_wall_hanging_sign",
            ):
                self.assertNotIn(unsupported, client_blocks)
            self.assertIn("tile.cherry_stairs.name=Canopy Stairs", (
                rp / "texts" / "en_US.lang"
            ).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
