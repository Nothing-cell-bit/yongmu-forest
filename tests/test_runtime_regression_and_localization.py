import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import biome_catalog, release_metadata

from tools.build_creative_catalog import (
    modernize_item_icons,
    normalize_creative_catalog,
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_language(path):
    entries = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            raise AssertionError(
                "%s:%d is not a key=value language entry"
                % (path, line_number)
            )
        entries.append(tuple(line.split("=", 1)))
    counts = Counter(key for key, _value in entries)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    if duplicates:
        raise AssertionError("duplicate language keys: %s" % duplicates)
    return dict(entries)


class RuntimeContentLogRegressionTests(unittest.TestCase):
    def test_patch_version_is_bumped_for_client_cache_invalidation(self):
        self.assertEqual((0, 12, 0), release_metadata.PACK_VERSION)

    def test_knightmetal_armor_uses_slot_specific_enchant_categories(self):
        expected = {
            "knightmetal_helmet": ("slot.armor.head", "armor_head"),
            "knightmetal_chestplate": ("slot.armor.chest", "armor_torso"),
            "knightmetal_leggings": ("slot.armor.legs", "armor_legs"),
            "knightmetal_boots": ("slot.armor.feet", "armor_feet"),
        }
        for identifier, (wearable_slot, enchant_slot) in expected.items():
            item = read_json(
                BP / "items" / (identifier + ".item.json")
            )["minecraft:item"]
            components = item["components"]
            self.assertEqual(
                wearable_slot,
                components["minecraft:wearable"]["slot"],
                identifier,
            )
            self.assertEqual(
                enchant_slot,
                components["minecraft:enchantable"]["slot"],
                identifier,
            )

    def test_maze_slime_random_direction_matches_runtime_schema(self):
        components = read_json(
            BP / "entities" / "maze_slime.entity.json"
        )["minecraft:entity"]["components"]
        behavior = components["minecraft:behavior.slime_random_direction"]
        self.assertEqual(
            {
                "priority",
                "add_random_time_range",
                "turn_range",
                "min_change_direction_time",
            },
            set(behavior),
        )

    def test_custom_biome_suffix_matches_runtime_inheritance(self):
        for entry in biome_catalog.BIOMES:
            self.assertEqual(
                entry["inherits"],
                entry["identifier"].split("dm33027004_", 1)[1],
                entry["key"],
            )

    def test_huge_lily_pad_uses_only_runtime_safe_quadrants(self):
        geometries = read_json(
            RP / "models" / "blocks" / "swamp_plants.geo.json"
        )["minecraft:geometry"]
        identifiers = {
            geometry["description"]["identifier"] for geometry in geometries
        }
        self.assertNotIn("geometry.tf_slice.huge_lily_pad", identifiers)
        self.assertIn(
            "geometry.tf_slice.huge_lily_pad_quadrant", identifiers
        )
        block = read_json(
            BP / "netease_blocks" / "huge_lily_pad.json"
        )["minecraft:block"]
        self.assertEqual(
            "geometry.tf_slice.huge_lily_pad_item",
            block["components"]["minecraft:geometry"],
        )
        search = read_json(
            BP
            / "netease_features"
            / "huge_lily_pad_water_search_feature.json"
        )["minecraft:search_feature"]
        self.assertEqual(
            "tf_slice:huge_lily_pad_rotation_selector_feature",
            search["places_feature"],
        )

    def test_every_custom_client_animation_binding_exists(self):
        declared = set()
        for path in (RP / "animations").glob("*.json"):
            declared.update(read_json(path).get("animations", {}))
        for path in (RP / "entity").glob("*.json"):
            description = read_json(path).get(
                "minecraft:client_entity", {}
            ).get("description", {})
            for animation in description.get("animations", {}).values():
                if animation.startswith("animation.tf_slice."):
                    self.assertIn(animation, declared, path.name)

    def test_knightmetal_armor_icons_are_registered_and_present(self):
        atlas = read_json(
            RP / "textures" / "item_texture.json"
        )["texture_data"]
        for identifier in (
            "knightmetal_helmet",
            "knightmetal_chestplate",
            "knightmetal_leggings",
            "knightmetal_boots",
        ):
            item = read_json(
                BP / "items" / (identifier + ".item.json")
            )["minecraft:item"]
            texture_key = item["components"]["minecraft:icon"][
                "textures"
            ]["default"]
            self.assertIn(texture_key, atlas, identifier)
            texture_path = atlas[texture_key]["textures"] + ".png"
            self.assertTrue((RP / texture_path).is_file(), identifier)

    def test_every_custom_item_uses_runtime_supported_icon_schema(self):
        atlas = read_json(
            RP / "textures" / "item_texture.json"
        )["texture_data"]
        inherited_vanilla_textures = {"textures/items/book_enchanted"}
        item_paths = sorted((BP / "items").glob("*.json"))
        self.assertTrue(item_paths)

        for path in item_paths:
            item = read_json(path).get("minecraft:item", {})
            identifier = item.get("description", {}).get("identifier")
            self.assertTrue(identifier, path.name)
            icon = item.get("components", {}).get("minecraft:icon")
            self.assertIsInstance(icon, dict, path.name)
            self.assertNotIn("texture", icon, path.name)
            self.assertEqual(
                {"textures": {"default": identifier}},
                icon,
                path.name,
            )
            texture_key = icon["textures"]["default"]
            self.assertIn(texture_key, atlas, path.name)
            texture_path = atlas[texture_key]["textures"]
            self.assertTrue(texture_path, path.name)
            self.assertTrue(
                (RP / (texture_path + ".png")).is_file()
                or texture_path in inherited_vanilla_textures,
                path.name,
            )

    def test_icon_schema_migration_is_selective_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            bp = Path(temporary)
            items = bp / "items"
            items.mkdir()
            legacy_path = items / "legacy.item.json"
            modern_path = items / "modern.item.json"
            legacy_path.write_text(
                json.dumps(
                    {
                        "minecraft:item": {
                            "components": {
                                "minecraft:icon": {
                                    "texture": "test:legacy"
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            modern_document = {
                "minecraft:item": {
                    "components": {
                        "minecraft:icon": {
                            "textures": {"default": "test:modern"}
                        }
                    }
                }
            }
            modern_path.write_text(
                json.dumps(modern_document), encoding="utf-8"
            )

            self.assertEqual(1, modernize_item_icons(bp))
            self.assertEqual(
                {
                    "textures": {"default": "test:legacy"}
                },
                read_json(legacy_path)["minecraft:item"]["components"][
                    "minecraft:icon"
                ],
            )
            self.assertEqual(modern_document, read_json(modern_path))
            self.assertEqual(0, modernize_item_icons(bp))

    def test_creative_catalog_normalizer_migrates_and_sorts_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bp = root / "TwilightBossSliceB"
            for folder in ("items", "blocks", "netease_blocks", "item_catalog"):
                (bp / folder).mkdir(parents=True, exist_ok=True)

            legacy_item = {
                "format_version": "1.20.0",
                "minecraft:item": {
                    "description": {
                        "identifier": "test:legacy",
                        "category": "nature",
                    },
                    "components": {
                        "minecraft:icon": {"texture": "test:legacy"}
                    },
                },
            }
            modern_item = {
                "format_version": "1.21.60",
                "minecraft:item": {
                    "description": {
                        "identifier": "test:modern",
                        "menu_category": {"category": "equipment"},
                    },
                    "components": {
                        "minecraft:icon": {
                            "textures": {"default": "test:modern"}
                        }
                    },
                },
            }
            (bp / "items" / "legacy.json").write_text(
                json.dumps(legacy_item), encoding="utf-8"
            )
            (bp / "items" / "modern.json").write_text(
                json.dumps(modern_item), encoding="utf-8"
            )
            for folder, identifier in (
                ("blocks", "test:block"),
                ("netease_blocks", "test:netease_block"),
            ):
                (bp / folder / (identifier.split(":")[1] + ".json")).write_text(
                    json.dumps(
                        {
                            "minecraft:block": {
                                "description": {"identifier": identifier}
                            }
                        }
                    ),
                    encoding="utf-8",
                )

            catalog_path = bp / "item_catalog" / "crafting_item_catalog.json"
            catalog_path.write_text(
                json.dumps(
                    {
                        "minecraft:crafting_items_catalog": {
                            "categories": [
                                {
                                    "category_name": "items",
                                    "groups": [
                                        {
                                            "group_identifier": {
                                                "icon": "test:legacy",
                                                "name": "test:group",
                                            },
                                            "items": [
                                                "test:legacy",
                                                "test:modern",
                                                "test:block",
                                                "test:netease_block",
                                                "test:mob_spawn_egg",
                                                "test:legacy",
                                            ],
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                {"nature": 1, "construction": 2, "items": 2},
                normalize_creative_catalog(root),
            )
            legacy = read_json(bp / "items" / "legacy.json")
            self.assertEqual("1.21.60", legacy["format_version"])
            self.assertNotIn(
                "category", legacy["minecraft:item"]["description"]
            )
            self.assertNotIn(
                "menu_category", legacy["minecraft:item"]["description"]
            )
            self.assertEqual(
                {"textures": {"default": "test:legacy"}},
                legacy["minecraft:item"]["components"]["minecraft:icon"],
            )
            categories = read_json(catalog_path)[
                "minecraft:crafting_items_catalog"
            ]["categories"]
            self.assertEqual(
                ["nature", "construction", "items"],
                [category["category_name"] for category in categories],
            )
            self.assertTrue(
                all(
                    category["groups"][0]["group_identifier"]["name"]
                    == "test:group"
                    for category in categories
                )
            )

            categories[0]["groups"][0]["items"].append("test:missing")
            catalog_path.write_text(
                json.dumps(
                    {"minecraft:crafting_items_catalog": {"categories": categories}}
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "test:missing"):
                normalize_creative_catalog(root)

    def test_custom_geometry_blocks_have_baked_material_data(self):
        for folder in ("blocks", "netease_blocks"):
            for path in (BP / folder).glob("*.json"):
                components = read_json(path).get(
                    "minecraft:block", {}
                ).get("components", {})
                if "minecraft:geometry" in components:
                    self.assertIn(
                        "minecraft:material_instances", components, path.name
                    )

    def test_netease_structure_features_use_namespaced_structure_names(self):
        for path in (BP / "netease_features").glob("*.json"):
            feature = read_json(path).get("netease:structure_feature")
            if feature:
                self.assertTrue(
                    feature["places_structure"].startswith("tf_slice:"),
                    path.name,
                )


class SimplifiedChineseLocalizationTests(unittest.TestCase):
    def test_simplified_chinese_covers_every_english_public_name(self):
        english = read_language(RP / "texts" / "en_US.lang")
        chinese = read_language(RP / "texts" / "zh_CN.lang")
        self.assertEqual(set(english), set(chinese))

    def test_simplified_chinese_contains_no_english_fallback_or_mojibake(self):
        chinese = read_language(RP / "texts" / "zh_CN.lang")
        mojibake_fragments = (
            "锟",
            "烫",
            "鈹",
            "鐢",
            "�",
            "Ã",
            "Â",
        )
        for key, value in chinese.items():
            self.assertTrue(
                any("\u4e00" <= character <= "\u9fff" for character in value),
                "%s still has a non-Chinese fallback: %s" % (key, value),
            )
            self.assertFalse(
                any(fragment in value for fragment in mojibake_fragments),
                "%s contains mojibake: %s" % (key, value),
            )
            if key.startswith("item.spawn_egg.entity."):
                self.assertTrue(value.startswith("生成 "), (key, value))

    def test_every_registered_public_content_has_a_chinese_name(self):
        chinese = read_language(RP / "texts" / "zh_CN.lang")
        expected = set()
        for path in (BP / "items").glob("*.json"):
            item = read_json(path).get("minecraft:item", {})
            if not item:
                continue
            display = item.get("components", {}).get(
                "minecraft:display_name", {}
            ).get("value")
            self.assertTrue(display, path.name)
            expected.add(display)
        for folder in ("blocks", "netease_blocks"):
            for path in (BP / folder).glob("*.json"):
                block = read_json(path).get("minecraft:block", {})
                identifier = block.get("description", {}).get("identifier")
                if identifier and identifier.startswith("tf_slice:"):
                    expected.add(
                        "tile.%s.name" % identifier
                    )
        for path in (BP / "entities").glob("*.json"):
            entity = read_json(path).get("minecraft:entity", {})
            description = entity.get("description", {})
            identifier = description.get("identifier")
            if not identifier or not identifier.startswith("tf_slice:"):
                continue
            expected.add("entity.%s.name" % identifier)
            if description.get("is_spawnable"):
                expected.add("item.spawn_egg.entity.%s.name" % identifier)
        self.assertFalse(sorted(expected - set(chinese)))


class CreativeCatalogRegressionTests(unittest.TestCase):
    def test_catalog_items_disable_automatic_menu_registration(self):
        item_documents = {}
        for path in (BP / "items").glob("*.json"):
            document = read_json(path)
            item = document.get("minecraft:item", {})
            identifier = item.get("description", {}).get("identifier")
            if identifier:
                item_documents[identifier] = (path, document, item)

        catalog = read_json(
            BP / "item_catalog" / "crafting_item_catalog.json"
        )["minecraft:crafting_items_catalog"]
        for category in catalog["categories"]:
            category_name = category["category_name"]
            for group in category.get("groups", []):
                for identifier in group.get("items", []):
                    entry = item_documents.get(identifier)
                    if entry is None:
                        continue
                    path, document, item = entry
                    description = item["description"]
                    self.assertEqual("1.21.60", document["format_version"], path)
                    self.assertNotIn("category", description, path)
                    self.assertNotIn("menu_category", description, path)

    def test_catalog_uses_semantic_categories(self):
        from tools import build_creative_catalog

        expected_category = {}
        for path in (BP / "items").glob("*.json"):
            item = read_json(path).get("minecraft:item", {})
            description = item.get("description", {})
            identifier = description.get("identifier")
            if identifier:
                expected_category[identifier] = description.get(
                    "menu_category", {}
                ).get("category", description.get("category", "items"))
        for folder in ("blocks", "netease_blocks"):
            for path in (BP / folder).glob("*.json"):
                block = read_json(path).get("minecraft:block", {})
                identifier = block.get("description", {}).get("identifier")
                if identifier:
                    expected_category[identifier] = "construction"

        # Entity-defined spawn eggs do not have standalone item JSON files,
        # but the engine registers them in the Nature category.
        catalog_document = read_json(
            BP / "item_catalog" / "crafting_item_catalog.json"
        )["minecraft:crafting_items_catalog"]
        for category in catalog_document["categories"]:
            for group in category.get("groups", []):
                for identifier in group.get("items", []):
                    if identifier.endswith("_spawn_egg"):
                        expected_category.setdefault(identifier, "nature")

        catalog = catalog_document
        seen = set()
        for category in catalog["categories"]:
            category_name = category["category_name"]
            for group in category.get("groups", []):
                for identifier in group.get("items", []):
                    self.assertNotIn(identifier, seen)
                    seen.add(identifier)
                    self.assertEqual(
                        build_creative_catalog._catalog_category(
                            identifier,
                            {
                                key
                                for key, value in expected_category.items()
                                if value == "construction"
                            },
                        ),
                        category_name,
                        identifier,
                    )


if __name__ == "__main__":
    unittest.main()
