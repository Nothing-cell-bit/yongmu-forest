# -*- coding: utf-8 -*-
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLOCKS = ROOT / "TwilightBossSliceB" / "netease_blocks"
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_courtyard_blocks
import build_dark_forest_content
import build_dark_tower_content
import build_knight_stronghold_content
import build_ruin_structures
from ensure_solid_block_collisions import ensure_solid_block_collisions


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def has_volume(box):
    if isinstance(box, list):
        return any(has_volume(value) for value in box)
    if not isinstance(box, dict):
        return False
    minimum = box.get("min")
    maximum = box.get("max")
    return (
        isinstance(minimum, list)
        and isinstance(maximum, list)
        and len(minimum) == 3
        and len(maximum) == 3
        and all(float(maximum[index]) > float(minimum[index]) for index in range(3))
    )


class SolidBlockCollisionContractTests(unittest.TestCase):
    def assert_has_collision(self, components):
        aabb = components.get("netease:aabb", {})
        self.assertTrue(has_volume(aabb.get("collision")))
        self.assertTrue(has_volume(aabb.get("clip")))

    def test_solid_custom_geometry_blocks_have_explicit_collision_boxes(self):
        missing = []
        empty = []

        for path in sorted(BLOCKS.glob("*.json")):
            block = read_json(path).get("minecraft:block", {})
            components = block.get("components", {})
            if not (
                components.get("minecraft:geometry")
                and components.get("netease:solid", {}).get("value") is True
            ):
                continue

            aabb = components.get("netease:aabb")
            if not isinstance(aabb, dict):
                missing.append(path.name)
                continue
            if not has_volume(aabb.get("collision")):
                empty.append(path.name)

        self.assertEqual([], missing, "solid custom blocks without netease:aabb")
        self.assertEqual([], empty, "solid custom blocks with empty collision boxes")

    def test_all_relevant_generators_emit_explicit_collision_boxes(self):
        generated_components = (
            build_courtyard_blocks.block_components(
                "geometry.tf_slice.courtyard_cube",
                {"*": "tf_slice:nagastone"},
            ),
            build_ruin_structures._courtyard_block_document(
                "tf_slice:nagastone",
                {},
                "geometry.tf_slice.courtyard_cube",
                {},
                [],
            )["minecraft:block"]["components"],
            build_knight_stronghold_content._block("underbrick")[
                "minecraft:block"
            ]["components"],
            build_dark_tower_content.block_document("towerwood")["minecraft:block"][
                "components"
            ],
            build_dark_forest_content.axis_block("dark_log")["minecraft:block"][
                "components"
            ],
            build_dark_forest_content.vertical_log_block()["minecraft:block"][
                "components"
            ],
        )

        for components in generated_components:
            self.assert_has_collision(components)

    def test_collision_normalizer_is_selective_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            solid = root / "solid.json"
            non_solid = root / "non_solid.json"
            solid.write_text(
                json.dumps(
                    {
                        "minecraft:block": {
                            "components": {
                                "minecraft:geometry": "geometry.test",
                                "netease:solid": {"value": True},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            non_solid.write_text(
                json.dumps(
                    {
                        "minecraft:block": {
                            "components": {
                                "minecraft:geometry": "geometry.test",
                                "netease:solid": {"value": False},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual([solid], ensure_solid_block_collisions(root))
            self.assert_has_collision(
                read_json(solid)["minecraft:block"]["components"]
            )
            self.assertNotIn(
                "netease:aabb",
                read_json(non_solid)["minecraft:block"]["components"],
            )
            self.assertEqual([], ensure_solid_block_collisions(root))


if __name__ == "__main__":
    unittest.main()
