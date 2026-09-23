import hashlib
import json
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
)
GEOMETRY_PATH = (
    ROOT / "TwilightBossSliceR" / "models" / "entity" / "ruin_mobs.geo.json"
)
ANIMATION_PATH = (
    ROOT / "TwilightBossSliceR" / "animations" / "ruin_mobs.animation.json"
)

SOURCE = {
    "jar": "0BDC89263616D1B35C32EF82C5E9C14CBD20368E2FE8B468C72A28320BE7A778",
    "model": "D4DAA225357319159CA71FD6F3AAB786A48F95BD8DE26083F4240E7C8C8D3253",
    "runtime": "DD7A89AEC2AA12CFA2B44C48B054B24177E9BE66340AC04D811BEA1AF6A3D0A3",
    "redcap_entity": "ABD7AAAC7BB94F70EA8F824E8C850165847203D2EFB129EB0283B1C0DD518BC8",
    "sapper_entity": "FA7C13AE44A5CB74F7BBEC7D629B95CBF26BFCD54576C9C8559DA0D3FBC82E73",
    "redcap_texture": "DE14AEC315A71C303BB06786B19F72570A7A8EBBE50268FFA81E35730818387D",
    "sapper_texture": "103F8DC59ECD2290691F3BC35C237BC74FC689A58DA49243C015D0460471A336",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def geometry():
    return next(
        item
        for item in load_json(GEOMETRY_PATH)["minecraft:geometry"]
        if item["description"]["identifier"] == "geometry.tf_slice.redcap"
    )


def bones():
    return {bone["name"]: bone for bone in geometry()["bones"]}


def client(entity_id):
    return load_json(
        ROOT / "TwilightBossSliceR" / "entity" / (entity_id + ".entity.json")
    )["minecraft:client_entity"]["description"]


def behavior(entity_id):
    entity = load_json(
        ROOT / "TwilightBossSliceB" / "entities" / (entity_id + ".entity.json")
    )["minecraft:entity"]
    # Default spawn state includes the normal goal group; scripted goals
    # temporarily remove it while retaining float and TNT avoidance.
    return dict(entity["components"], **entity.get("component_groups", {}).get("tf_slice:redcap_normal", {}))


class RedcapModelWorkflowTests(unittest.TestCase):
    def test_locked_classic_source_and_both_texture_variants(self):
        jar = ROOT.parent / "[暮色森林] twilightforest-1.20.1-4.3.2508-universal.jar"
        self.assertEqual(SOURCE["jar"], sha256(jar))
        with zipfile.ZipFile(jar) as archive:
            self.assertNotIn(
                "assets/twilightforest/jappa_models.marker",
                archive.namelist(),
            )

        paths = {
            "model": (
                UPSTREAM
                / "twilightforest"
                / "client"
                / "model"
                / "entity"
                / "RedcapModel.class"
            ),
            "runtime": (
                UPSTREAM
                / "twilightforest"
                / "client"
                / "model"
                / "entity"
                / "FixedHumanoidModel.class"
            ),
            "redcap_entity": (
                UPSTREAM
                / "twilightforest"
                / "entity"
                / "monster"
                / "Redcap.class"
            ),
            "sapper_entity": (
                UPSTREAM
                / "twilightforest"
                / "entity"
                / "monster"
                / "RedcapSapper.class"
            ),
        }
        for key, path in paths.items():
            self.assertEqual(SOURCE[key], sha256(path), key)

        for entity_id, source_name, expected_hash in (
            ("redcap", "redcap.png", SOURCE["redcap_texture"]),
            (
                "redcap_sapper",
                "redcapsapper.png",
                SOURCE["sapper_texture"],
            ),
        ):
            source = (
                UPSTREAM
                / "assets"
                / "twilightforest"
                / "textures"
                / "model"
                / source_name
            )
            target = (
                ROOT
                / "TwilightBossSliceR"
                / "textures"
                / "entity"
                / "tf_slice"
                / (entity_id + ".png")
            )
            self.assertEqual(expected_hash, sha256(source))
            self.assertEqual(expected_hash, sha256(target))

    def test_runtime_hat_copy_is_baked_into_geometry(self):
        by_name = bones()
        self.assertEqual(10, len(by_name))
        self.assertEqual([0, 16, 0], by_name["head"]["pivot"])
        self.assertEqual([0, 16, 0], by_name["hat"]["pivot"])
        self.assertEqual([-2, 19.5, -3], by_name["hat"]["cubes"][0]["origin"])
        self.assertEqual([4, 5, 7], by_name["hat"]["cubes"][0]["size"])
        self.assertEqual([32, 0], by_name["hat"]["cubes"][0]["uv"])
        for name in (
            "head",
            "hat",
            "body",
            "rightArm",
            "leftArm",
            "rightLeg",
            "leftLeg",
        ):
            self.assertEqual("root", by_name[name].get("parent"), name)

    def test_redcap_has_source_specific_walk_item_and_hat_look_animation(self):
        animations = load_json(ANIMATION_PATH)["animations"]
        move = animations["animation.tf_slice.redcap.move"]["bones"]
        look = animations["animation.tf_slice.redcap.look"]["bones"]

        right_arm = json.dumps(move["rightArm"], sort_keys=True)
        left_arm = json.dumps(move["leftArm"], sort_keys=True)
        legs = json.dumps(
            {"right": move["rightLeg"], "left": move["leftLeg"]},
            sort_keys=True,
        )
        self.assertIn("-18", right_arm)
        self.assertIn("28.6479", right_arm)
        self.assertIn("query.life_time", right_arm)
        self.assertIn("57.2958", left_arm)
        self.assertIn("80.2141", legs)
        self.assertEqual(look["head"], look["hat"])
        self.assertIn("query.target_x_rotation", json.dumps(look["head"]))
        self.assertIn("query.target_y_rotation", json.dumps(look["head"]))

        for entity_id in ("redcap", "redcap_sapper"):
            description = client(entity_id)
            self.assertEqual(
                "geometry.tf_slice.redcap",
                description["geometry"]["default"],
            )
            self.assertEqual(
                "animation.tf_slice.redcap.move",
                description["animations"]["move"],
            )
            self.assertEqual(
                "animation.tf_slice.redcap.look",
                description["animations"]["look"],
            )

    def test_dimensions_spawn_eggs_attributes_and_goal_order_match_source(self):
        expected_eggs = {
            "redcap": ("#3B3A6C", "#AB1E14"),
            "redcap_sapper": ("#575D21", "#AB1E14"),
        }
        for entity_id in ("redcap", "redcap_sapper"):
            components = behavior(entity_id)
            self.assertEqual(
                0.9,
                components["minecraft:collision_box"]["width"],
            )
            self.assertEqual(
                1.4,
                components["minecraft:collision_box"]["height"],
            )
            self.assertEqual(0.28, components["minecraft:movement"]["value"])
            self.assertEqual(2, components["minecraft:attack"]["damage"])
            self.assertEqual(
                expected_eggs[entity_id][0],
                client(entity_id)["spawn_egg"]["base_color"],
            )
            self.assertEqual(
                expected_eggs[entity_id][1],
                client(entity_id)["spawn_egg"]["overlay_color"],
            )

            self.assertEqual(
                0,
                components["minecraft:behavior.float"]["priority"],
            )
            avoid = components["minecraft:behavior.avoid_mob_type"]
            self.assertEqual(1, avoid["priority"])
            avoid_entry = avoid["entity_types"][0]
            self.assertEqual(2, avoid_entry["max_dist"])
            self.assertEqual(1.0, avoid_entry["walk_speed_multiplier"])
            self.assertEqual(2.0, avoid_entry["sprint_speed_multiplier"])
            self.assertEqual(
                5,
                components["minecraft:behavior.melee_attack"]["priority"],
            )
            self.assertEqual(
                1.0,
                components["minecraft:behavior.melee_attack"][
                    "speed_multiplier"
                ],
            )
            self.assertEqual(
                6,
                components["minecraft:behavior.random_stroll"]["priority"],
            )
            self.assertEqual(
                1.0,
                components["minecraft:behavior.random_stroll"][
                    "speed_multiplier"
                ],
            )
            self.assertEqual(
                7,
                components["minecraft:behavior.look_at_player"]["priority"],
            )
            self.assertEqual(
                7,
                components["minecraft:behavior.random_look_around"][
                    "priority"
                ],
            )
            self.assertEqual(
                1,
                components["minecraft:behavior.hurt_by_target"]["priority"],
            )
            self.assertEqual(
                2,
                components["minecraft:behavior.nearest_attackable_target"][
                    "priority"
                ],
            )

        self.assertEqual(20, behavior("redcap")["minecraft:health"]["value"])
        sapper = behavior("redcap_sapper")
        self.assertEqual(30, sapper["minecraft:health"]["value"])
        self.assertEqual(2, sapper["minecraft:armor"]["value"])


if __name__ == "__main__":
    unittest.main()
