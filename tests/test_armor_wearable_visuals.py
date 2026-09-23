import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP_ITEMS = ROOT / "TwilightBossSliceB" / "items"
RP = ROOT / "TwilightBossSliceR"
UPSTREAM_ARMOR = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
    / "textures"
    / "armor"
)


ARMOR = {
    "fiery_helmet": ("head", 4, 10, "fiery_1"),
    "fiery_chestplate": ("chest", 9, 10, "fiery_1"),
    "fiery_leggings": ("legs", 7, 10, "fiery_2"),
    "fiery_boots": ("feet", 4, 10, "fiery_1"),
    "ironwood_helmet": ("head", 2, 15, "ironwood_1"),
    "ironwood_chestplate": ("chest", 7, 15, "ironwood_1"),
    "ironwood_leggings": ("legs", 5, 15, "ironwood_2"),
    "ironwood_boots": ("feet", 2, 15, "ironwood_1"),
    "steeleaf_helmet": ("head", 3, 9, "steeleaf_1"),
    "steeleaf_chestplate": ("chest", 8, 9, "steeleaf_1"),
    "steeleaf_leggings": ("legs", 6, 9, "steeleaf_2"),
    "steeleaf_boots": ("feet", 3, 9, "steeleaf_1"),
    "knightmetal_helmet": ("head", 3, 9, "knightly_1"),
    "knightmetal_chestplate": ("chest", 8, 9, "knightly_1"),
    "knightmetal_leggings": ("legs", 6, 9, "knightly_2"),
    "knightmetal_boots": ("feet", 3, 9, "knightly_1"),
    "naga_chestplate": ("chest", 7, 15, "naga_scale_1"),
    "naga_leggings": ("legs", 6, 15, "naga_scale_2"),
    "phantom_helmet": ("head", 3, 8, "phantom_1"),
    "phantom_chestplate": ("chest", 8, 8, "phantom_1"),
}

GEOMETRY = {
    "head": "geometry.humanoid.armor.helmet",
    "chest": "geometry.humanoid.armor.chestplate",
    "legs": "geometry.humanoid.armor.leggings",
    "feet": "geometry.humanoid.armor.boots",
}

PARENT_SETUP = {
    "head": "variable.helmet_layer_visible = 0.0;",
    "chest": "variable.chest_layer_visible = 0.0;",
    "legs": "variable.leg_layer_visible = 0.0;",
    "feet": "variable.boot_layer_visible = 0.0;",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


class ArmorWearableVisualTests(unittest.TestCase):
    def test_every_armor_item_is_wearable_in_the_correct_slot(self):
        enchant_slots = {
            "head": "armor_head",
            "chest": "armor_torso",
            "legs": "armor_legs",
            "feet": "armor_feet",
        }
        for name, (slot, protection, enchantability, _texture) in ARMOR.items():
            components = read_json(BP_ITEMS / (name + ".item.json"))[
                "minecraft:item"
            ]["components"]
            self.assertEqual(
                {"slot": "slot.armor." + slot, "protection": protection},
                components.get("minecraft:wearable"),
                name,
            )
            self.assertEqual(
                {"slot": enchant_slots[slot], "value": enchantability},
                components.get("minecraft:enchantable"),
                name,
            )

    def test_every_armor_item_has_a_complete_humanoid_attachable(self):
        for name, (slot, _protection, _enchantability, texture) in ARMOR.items():
            attachable_path = RP / "attachables" / (name + ".attachable.json")
            self.assertTrue(attachable_path.is_file(), name)
            description = read_json(attachable_path)["minecraft:attachable"][
                "description"
            ]
            self.assertEqual("tf_slice:" + name, description["identifier"], name)
            self.assertEqual(
                {"default": "armor", "enchanted": "armor_enchanted"},
                description["materials"],
                name,
            )
            self.assertEqual(
                {
                    "default": "textures/models/tf_slice/armor/" + texture,
                    "enchanted": "textures/misc/enchanted_actor_glint",
                },
                description["textures"],
                name,
            )
            expected_geometry = (
                "geometry.tf_slice.phantom_helmet"
                if name == "phantom_helmet"
                else GEOMETRY[slot]
            )
            self.assertEqual(
                {"default": expected_geometry}, description["geometry"], name
            )
            self.assertEqual(
                {"parent_setup": PARENT_SETUP[slot]},
                description["scripts"],
                name,
            )
            self.assertEqual(
                ["controller.render.armor"],
                description["render_controllers"],
                name,
            )

    def test_wearable_textures_match_the_locked_upstream_armor_layers(self):
        textures = {
            texture
            for _slot, _protection, _enchantability, texture in ARMOR.values()
        }
        self.assertEqual(11, len(textures))
        for texture in textures:
            source = UPSTREAM_ARMOR / (texture + ".png")
            target = (
                RP
                / "textures"
                / "models"
                / "tf_slice"
                / "armor"
                / (texture + ".png")
            )
            self.assertTrue(source.is_file(), texture)
            self.assertTrue(target.is_file(), texture)
            self.assertEqual(source.read_bytes(), target.read_bytes(), texture)

    def test_phantom_helmet_geometry_preserves_both_two_segment_horns(self):
        geometry_path = RP / "models" / "entity" / "phantom_armor.geo.json"
        self.assertTrue(geometry_path.is_file())
        geometries = read_json(geometry_path)["minecraft:geometry"]
        geometry = next(
            value
            for value in geometries
            if value["description"]["identifier"]
            == "geometry.tf_slice.phantom_helmet"
        )
        self.assertEqual(64, geometry["description"]["texture_width"])
        self.assertEqual(32, geometry["description"]["texture_height"])

        bones = {bone["name"]: bone for bone in geometry["bones"]}
        self.assertEqual(
            {
                "head",
                "right_horn_1",
                "right_horn_2",
                "left_horn_1",
                "left_horn_2",
            },
            set(bones),
        )
        self.assertEqual("'head'", bones["head"]["binding"])
        self.assertEqual("head", bones["right_horn_1"]["parent"])
        self.assertEqual("right_horn_1", bones["right_horn_2"]["parent"])
        self.assertEqual("head", bones["left_horn_1"]["parent"])
        self.assertEqual("left_horn_1", bones["left_horn_2"]["parent"])

        self.assertEqual([-4, 30.5, 0], bones["right_horn_1"]["pivot"])
        # Attachable head binding reverses the visible roll handedness used by
        # the standalone entity preview.  Positive right / negative left roll
        # keeps both horn chains curving upward on the equipped player model.
        self.assertEqual([0, -25, 45], bones["right_horn_1"]["rotation"])
        self.assertEqual([0, -15, 45], bones["right_horn_2"]["rotation"])
        self.assertEqual([4, 30.5, 0], bones["left_horn_1"]["pivot"])
        self.assertEqual([0, 25, -45], bones["left_horn_1"]["rotation"])
        self.assertEqual([0, 15, -45], bones["left_horn_2"]["rotation"])
        self.assertEqual([5, 3, 3], bones["right_horn_1"]["cubes"][0]["size"])
        self.assertEqual([3, 2, 2], bones["right_horn_2"]["cubes"][0]["size"])
        self.assertEqual([5, 3, 3], bones["left_horn_1"]["cubes"][0]["size"])
        self.assertEqual([3, 2, 2], bones["left_horn_2"]["cubes"][0]["size"])


if __name__ == "__main__":
    unittest.main()
