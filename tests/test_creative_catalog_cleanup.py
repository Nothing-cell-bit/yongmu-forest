# -*- coding: utf-8 -*-
"""Creative inventory cleanup and obsolete wood-shell contracts."""

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
sys.path.insert(0, str(ROOT / "tools"))


def catalog_categories():
    document = json.loads(
        (BP / "item_catalog" / "crafting_item_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    return {
        category["category_name"]: [
            identifier
            for group in category.get("groups", [])
            for identifier in group.get("items", [])
        ]
        for category in document["minecraft:crafting_items_catalog"][
            "categories"
        ]
    }


class CreativeCatalogCleanupTests(unittest.TestCase):
    def test_only_real_custom_banisters_survive_the_old_wood_shells(self):
        from tools import build_creative_catalog as builder

        self.assertEqual(26, len(builder.OBSOLETE_WOOD_BLOCK_IDS))
        self.assertEqual(
            {"tf_slice:dark_banister", "tf_slice:mangrove_banister"},
            set(builder.PUBLIC_WOOD_SHAPE_IDS),
        )
        categories = catalog_categories()
        catalog_ids = {
            identifier
            for identifiers in categories.values()
            for identifier in identifiers
        }
        self.assertTrue(
            set(builder.OBSOLETE_WOOD_BLOCK_IDS).isdisjoint(catalog_ids)
        )
        self.assertTrue(set(builder.PUBLIC_WOOD_SHAPE_IDS) <= catalog_ids)

    def test_obsolete_wood_behavior_models_icons_and_client_entries_are_gone(self):
        from tools import build_creative_catalog as builder

        client_blocks = json.loads(
            (RP / "blocks.json").read_text(encoding="utf-8")
        )
        atlas = json.loads(
            (RP / "textures" / "terrain_texture.json").read_text(
                encoding="utf-8"
            )
        )["texture_data"]
        for identifier in builder.OBSOLETE_WOOD_BLOCK_IDS:
            name = identifier.split(":", 1)[1]
            self.assertFalse(
                (BP / "netease_blocks" / (name + ".json")).exists(), name
            )
            self.assertFalse(
                (
                    RP
                    / "models"
                    / "netease_block"
                    / ("tf_slice_public_%s.json" % name)
                ).exists(),
                name,
            )
            self.assertFalse(
                (RP / "textures" / "blocks" / "item_icons" / (name + ".png")).exists(),
                name,
            )
            self.assertNotIn(identifier, client_blocks)
            self.assertNotIn(identifier, atlas)
            self.assertNotIn(identifier + "_item", atlas)

    def test_unused_banister_netease_models_and_icons_are_removed(self):
        for family in ("dark", "mangrove"):
            name = family + "_banister"
            self.assertFalse(
                (
                    RP
                    / "models"
                    / "netease_block"
                    / ("tf_slice_public_%s.json" % name)
                ).exists()
            )
            self.assertFalse(
                (RP / "textures" / "blocks" / "item_icons" / (name + ".png")).exists()
            )

    def test_categories_are_semantic_and_identifiers_are_unique(self):
        categories = catalog_categories()
        self.assertEqual(
            ["nature", "equipment", "construction", "items"],
            list(categories),
        )
        all_items = [
            identifier
            for identifiers in categories.values()
            for identifier in identifiers
        ]
        self.assertEqual(len(all_items), len(set(all_items)))
        self.assertIn("tf_slice:forest_wyrm_spawn_egg", categories["nature"])
        self.assertIn("tf_slice:darkwood_sapling", categories["nature"])
        self.assertIn("tf_slice:ironwood_pickaxe", categories["equipment"])
        self.assertIn("tf_slice:naga_chestplate", categories["equipment"])
        self.assertIn("tf_slice:dark_planks", categories["construction"])
        self.assertIn("tf_slice:mangrove_banister", categories["construction"])
        self.assertIn("tf_slice:raven_feather", categories["items"])
        self.assertIn("tf_slice:meef_stroganoff", categories["items"])
        self.assertNotIn("tf_slice:ironwood_pickaxe", categories["nature"])

    def test_construction_families_have_stable_readable_order(self):
        construction = catalog_categories()["construction"]
        anchors = [
            "tf_slice:dark_log",
            "tf_slice:towerwood",
            "tf_slice:mazestone",
            "tf_slice:mangrove_log",
            "tf_slice:underbrick",
            "tf_slice:nagastone",
        ]
        positions = [construction.index(identifier) for identifier in anchors]
        self.assertEqual(sorted(positions), positions)

    def test_explicit_catalog_is_the_only_automatic_registration_path(self):
        catalog_ids = {
            identifier
            for identifiers in catalog_categories().values()
            for identifier in identifiers
        }
        for path in (BP / "items").glob("*.json"):
            item = json.loads(path.read_text(encoding="utf-8"))[
                "minecraft:item"
            ]
            description = item["description"]
            if description.get("identifier") in catalog_ids:
                self.assertNotIn("menu_category", description, path.name)
        for folder in ("blocks", "netease_blocks"):
            for path in (BP / folder).glob("*.json"):
                block = json.loads(path.read_text(encoding="utf-8"))[
                    "minecraft:block"
                ]
                description = block["description"]
                if description.get("identifier") in catalog_ids:
                    self.assertFalse(
                        description.get("register_to_creative_menu", True),
                        path.name,
                    )

    def test_dynamic_filled_maps_stay_out_of_creative_and_generators(self):
        from tools import build_creative_catalog
        from tools import build_hydra_route_content

        catalog_ids = {
            identifier
            for identifiers in catalog_categories().values()
            for identifier in identifiers
        }
        self.assertTrue(
            {
                "tf_slice:magic_map",
                "tf_slice:maze_map",
            }
            <= catalog_ids
        )
        self.assertTrue(
            {
                "tf_slice:filled_magic_map",
                "tf_slice:filled_maze_map",
            }.isdisjoint(catalog_ids)
        )
        self.assertEqual(
            {
                "tf_slice:filled_magic_map",
                "tf_slice:filled_maze_map",
            },
            set(build_creative_catalog.HIDDEN_DYNAMIC_ITEM_IDS),
        )
        self.assertEqual(
            ["maze_map", "maze_map_focus"],
            build_hydra_route_content.creative_item_identifiers(
                ["maze_map", "filled_maze_map", "maze_map_focus"]
            ),
        )

    def test_catalog_normalizer_removes_dynamic_maps_but_keeps_definitions(self):
        from tools import build_creative_catalog

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bp = root / "TwilightBossSliceB"
            items = bp / "items"
            catalog_path = bp / "item_catalog" / "crafting_item_catalog.json"
            items.mkdir(parents=True)
            catalog_path.parent.mkdir(parents=True)
            identifiers = (
                "tf_slice:magic_map",
                "tf_slice:filled_magic_map",
                "tf_slice:maze_map",
                "tf_slice:filled_maze_map",
            )
            for identifier in identifiers:
                (items / (identifier.split(":", 1)[1] + ".json")).write_text(
                    json.dumps(
                        {
                            "format_version": "1.21.60",
                            "minecraft:item": {
                                "description": {"identifier": identifier},
                                "components": {},
                            },
                        }
                    ),
                    encoding="utf-8",
                )
            catalog_path.write_text(
                json.dumps(
                    {
                        "format_version": "1.21.60",
                        "minecraft:crafting_items_catalog": {
                            "categories": [
                                {
                                    "category_name": "items",
                                    "groups": [
                                        {
                                            "group_identifier": {
                                                "icon": "tf_slice:magic_map",
                                                "name": "test:maps",
                                            },
                                            "items": list(identifiers),
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            build_creative_catalog.normalize_creative_catalog(root)

            normalized = json.loads(catalog_path.read_text(encoding="utf-8"))
            encoded = json.dumps(normalized)
            self.assertIn("tf_slice:magic_map", encoded)
            self.assertIn("tf_slice:maze_map", encoded)
            self.assertNotIn("tf_slice:filled_magic_map", encoded)
            self.assertNotIn("tf_slice:filled_maze_map", encoded)
            self.assertTrue(
                all(
                    (items / (identifier.split(":", 1)[1] + ".json")).is_file()
                    for identifier in identifiers
                )
            )


if __name__ == "__main__":
    unittest.main()
