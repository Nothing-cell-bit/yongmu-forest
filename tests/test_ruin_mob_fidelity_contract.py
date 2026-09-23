# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
PACKAGE = BP / "TwilightBossSlice"
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

EXPECTED_STATS = {
    "raven": (10, 0),
    "skeleton_druid": (20, 2),
    "swarm_spider": (3, 1),
    "hedge_spider": (16, 2),
    "hostile_wolf": (20, 2),
    "wraith": (20, 5),
    "rising_zombie": (20, 0),
    "redcap": (20, 2),
    "redcap_sapper": (30, 2),
    "kobold": (13, 4),
}

EXPECTED_GEOMETRIES = {
    "raven": "geometry.tf_slice.raven",
    "skeleton_druid": "geometry.tf_slice.skeleton_druid",
    "hostile_wolf": "geometry.tf_slice.hostile_wolf",
    "wraith": "geometry.tf_slice.wraith",
    "rising_zombie": "geometry.tf_slice.rising_zombie",
    "redcap": "geometry.tf_slice.redcap",
    "redcap_sapper": "geometry.tf_slice.redcap",
    "kobold": "geometry.tf_slice.kobold",
}

EXPECTED_DROPS = {
    "raven": {"tf_slice:raven_feather"},
    "skeleton_druid": {"minecraft:bone", "tf_slice:torchberries"},
    "swarm_spider": {"minecraft:string", "minecraft:spider_eye"},
    "hedge_spider": {"minecraft:string", "minecraft:spider_eye"},
    "hostile_wolf": set(),
    "wraith": {"minecraft:glowstone_dust"},
    "rising_zombie": {"minecraft:rotten_flesh"},
    "redcap": {"minecraft:coal"},
    "redcap_sapper": {"minecraft:coal"},
    "kobold": {"minecraft:wheat", "minecraft:gold_nugget"},
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def behavior(name):
    return read_json(BP / "entities" / ("%s.entity.json" % name))[
        "minecraft:entity"
    ]


def client(name):
    return read_json(RP / "entity" / ("%s.entity.json" % name))[
        "minecraft:client_entity"
    ]["description"]


class RuinMobModelAndAnimationContractTests(unittest.TestCase):
    def _geometries(self):
        return {
            entry["description"]["identifier"]: entry
            for entry in read_json(
                RP / "models" / "entity" / "ruin_mobs.geo.json"
            )["minecraft:geometry"]
        }

    def _bones(self, geometry_id):
        return {
            bone["name"]: bone
            for bone in self._geometries()[geometry_id]["bones"]
        }

    def test_upstream_4_3_2508_stats_are_not_generic_placeholders(self):
        for name, (health, attack) in EXPECTED_STATS.items():
            components = behavior(name)["components"]
            self.assertEqual(
                health, components["minecraft:health"]["max"], name
            )
            if attack:
                self.assertEqual(
                    attack, components["minecraft:attack"]["damage"], name
                )
            else:
                self.assertNotIn("minecraft:attack", components, name)

    def test_distinct_upstream_silhouettes_have_distinct_geometries(self):
        geometries = {
            entry["description"]["identifier"]: entry
            for entry in read_json(
                RP / "models" / "entity" / "ruin_mobs.geo.json"
            )["minecraft:geometry"]
        }
        for name, geometry_id in EXPECTED_GEOMETRIES.items():
            self.assertEqual(geometry_id, client(name)["geometry"]["default"])
            self.assertIn(geometry_id, geometries)

        required_bones = {
            "geometry.tf_slice.raven": {
                "head",
                "upper_beak",
                "lower_beak",
                "right_wing",
                "left_wing",
                "right_foot",
                "left_foot",
                "tail",
            },
            "geometry.tf_slice.redcap": {
                "hat",
                "rightArm",
                "leftArm",
                "rightItem",
                "leftItem",
                "rightLeg",
                "leftLeg",
            },
            "geometry.tf_slice.kobold": {
                "rightEar",
                "leftEar",
                "snout",
                "jaw",
                "rightArm",
                "leftArm",
                "rightItem",
            },
            "geometry.tf_slice.skeleton_druid": {
                "rightArm",
                "leftArm",
                "rightItem",
                "leftItem",
                "dress",
            },
            "geometry.tf_slice.wraith": {
                "rightArm",
                "leftArm",
                "dress",
            },
            "geometry.tf_slice.hostile_wolf": {
                "head",
                "body",
                "upperBody",
                "tail",
                "leg0",
                "leg1",
                "leg2",
                "leg3",
            },
        }
        for geometry_id, expected in required_bones.items():
            names = {bone["name"] for bone in geometries[geometry_id]["bones"]}
            self.assertTrue(expected.issubset(names), geometry_id)

    def test_equipment_carriers_enable_attachables_and_have_hand_bones(self):
        for name in ("skeleton_druid", "redcap", "redcap_sapper", "kobold"):
            self.assertTrue(client(name).get("enable_attachables"), name)

        geometries = {
            entry["description"]["identifier"]: entry
            for entry in read_json(
                RP / "models" / "entity" / "ruin_mobs.geo.json"
            )["minecraft:geometry"]
        }
        for name in ("redcap", "kobold", "skeleton_druid"):
            bones = {
                bone["name"]: bone
                for bone in geometries[EXPECTED_GEOMETRIES[name]]["bones"]
            }
            for bone_name in ("rightItem", "leftItem"):
                self.assertTrue(bones[bone_name]["neverRender"])
                self.assertNotIn("rotation", bones[bone_name])

        equipment = {
            "skeleton_druid": "minecraft:golden_hoe",
            "redcap": "minecraft:iron_pickaxe",
            "redcap_sapper": "tf_slice:ironwood_pickaxe",
        }
        for name, item_id in equipment.items():
            entity = behavior(name)
            table = entity["components"]["minecraft:equipment"]["table"]
            self.assertIn(item_id, json.dumps(read_json(BP / table)))

    def test_raven_has_ground_takeoff_and_flight_states(self):
        raven = client("raven")
        controller_id = raven["animations"]["flight_controller"]
        self.assertEqual(
            "controller.animation.tf_slice.raven.flight", controller_id
        )
        controllers = read_json(
            RP / "animation_controllers" / "ruin_mobs.controller.json"
        )["animation_controllers"]
        states = controllers[controller_id]["states"]
        self.assertTrue({"grounded", "takeoff", "flying"}.issubset(states))
        self.assertIn("takeoff", raven["sound_effects"])

        animations = read_json(
            RP / "animations" / "ruin_mobs.animation.json"
        )["animations"]
        self.assertIn("animation.tf_slice.raven.takeoff", animations)
        self.assertIn("animation.tf_slice.raven.fly", animations)
        self.assertIn(
            "sound_effects",
            animations["animation.tf_slice.raven.takeoff"],
        )

    def test_redcap_uses_converted_java_part_pivots_and_uv_origins(self):
        bones = self._bones("geometry.tf_slice.redcap")
        expected = {
            "head": ([0, 16, 0], [-3.5, 17, -3.5], [0, 0]),
            # FixedHumanoidModel.setupAnim ends with hat.copyFrom(head), so
            # the rendered pivot/origin differ from the create-layer pose.
            "hat": ([0, 16, 0], [-2, 19.5, -3], [32, 0]),
            "body": ([0, 19, 0], [-4, 9, -2], [12, 19]),
            "rightArm": ([-4, 17, 0], [-7, 6, -1.5], [36, 17]),
            "leftArm": ([4, 17, 0], [4, 6, -1.5], [36, 17]),
            "rightLeg": ([-2.5, 9, 0], [-4, 0, -1.5], [0, 20]),
            "leftLeg": ([2.5, 9, 0], [1, 0, -1.5], [0, 20]),
        }
        for name, (pivot, origin, uv) in expected.items():
            self.assertEqual(pivot, bones[name]["pivot"], name)
            self.assertEqual(origin, bones[name]["cubes"][0]["origin"], name)
            self.assertEqual(uv, bones[name]["cubes"][0]["uv"], name)
            self.assertEqual("root", bones[name]["parent"], name)

    def test_hostile_wolf_matches_upstream_part_pose_conversion(self):
        bones = self._bones("geometry.tf_slice.hostile_wolf")
        self.assertEqual([-3, 3, -1], bones["body"]["cubes"][0]["origin"])
        self.assertEqual([90, 0, 0], bones["body"]["rotation"])
        self.assertEqual([-4, 7, -6], bones["upperBody"]["cubes"][0]["origin"])
        self.assertEqual([90, 0, 0], bones["upperBody"]["rotation"])
        self.assertEqual(
            [-1.5, 7.5, -12],
            bones["head"]["cubes"][1]["origin"],
        )
        self.assertEqual([-3, 13.5, -7], bones["head"]["cubes"][2]["origin"])

        animation = read_json(
            RP / "animations" / "ruin_mobs.animation.json"
        )["animations"]["animation.tf_slice.wolf.walk"]
        tail_x = animation["bones"]["tail"]["rotation"][0]
        self.assertIsInstance(tail_x, str)
        self.assertIn("query.has_target", tail_x)
        self.assertNotIn("36", tail_x)

    def test_rising_zombie_is_frozen_and_uses_the_two_stage_java_pose(self):
        rising = behavior("rising_zombie")
        self.assertNotIn("minecraft:attack", rising["components"])
        group = rising["component_groups"]["tf_slice:rising"]
        self.assertEqual(0.0, group["minecraft:movement"]["value"])
        self.assertEqual(
            1.0,
            group["minecraft:knockback_resistance"]["value"],
        )

        bones = self._bones("geometry.tf_slice.rising_zombie")
        self.assertEqual("risePivot", bones["waist"]["parent"])
        self.assertEqual([0, 16, 0], bones["risePivot"]["pivot"])
        self.assertEqual([16, 16], bones["body"]["cubes"][0]["uv"])

        animation = read_json(
            RP / "animations" / "ruin_mobs.animation.json"
        )["animations"]["animation.tf_slice.rising_zombie.rise"]
        root = animation["bones"]["root"]
        self.assertEqual([0, -32, 0], root["position"]["0.0"])
        self.assertEqual([0, -16, 0], root["position"]["4.0"])
        self.assertEqual(
            [-90, 0, 0],
            animation["bones"]["risePivot"]["rotation"]["0.0"],
        )
        self.assertEqual(
            [30, 0, 0],
            animation["bones"]["risePivot"]["rotation"]["4.0"],
        )
        self.assertNotIn("rightArm", animation["bones"])
        self.assertNotIn("leftArm", animation["bones"])

        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _freeze_rising_zombie", source)
        self.assertIn('mobType == "tf_slice:rising_zombie"', source)

    def test_model_porting_rules_record_the_failed_assumptions(self):
        guide = ROOT / "docs" / "model_porting_rules.md"
        self.assertTrue(guide.is_file())
        text = guide.read_text(encoding="utf-8")
        for phrase in (
            "看到模型能显示，就误判几何和父子变换正确",
            "源码锁定",
            "离线候选",
            "客户端验收",
            "冷启动",
        ):
            self.assertIn(phrase, text)


class RuinMobLootSoundAndAIContractTests(unittest.TestCase):
    def test_every_mob_has_an_upstream_equivalent_loot_table(self):
        for name, expected_items in EXPECTED_DROPS.items():
            table = behavior(name)["components"]["minecraft:loot"]["table"]
            loot = read_json(BP / table)
            inherited = {"swarm_spider": "spider", "hedge_spider": "spider", "rising_zombie": "zombie"}
            if name in inherited:
                self.assertEqual(
                    [{"type": "loot_table", "name": "loot_tables/entities/%s.json" % inherited[name]}],
                    loot["pools"][0]["entries"],
                )
                continue
            actual_items = {
                entry["name"]
                for pool in loot["pools"]
                for entry in pool.get("entries", [])
                if entry.get("type") == "item"
            }
            self.assertTrue(expected_items.issubset(actual_items), name)
            if not expected_items:
                self.assertEqual(set(), actual_items, name)

    def test_original_sound_banks_and_entity_sound_routes_exist(self):
        definitions = read_json(
            RP / "sounds" / "sound_definitions.json"
        )["sound_definitions"]
        entity_sounds = read_json(RP / "sounds.json")["entity_sounds"][
            "entities"
        ]
        expected_custom = {
            "raven": ("ambient", "hurt", "death", "takeoff"),
            "redcap": ("ambient", "hurt", "death"),
            "redcap_sapper": ("ambient", "hurt", "death"),
            "kobold": ("ambient", "hurt", "death", "munch"),
            "hostile_wolf": ("ambient", "hurt", "death", "target"),
            "wraith": ("ambient", "hurt", "death"),
        }
        for name, events in expected_custom.items():
            self.assertIn("tf_slice:%s" % name, entity_sounds)
            for event in events:
                self.assertIn("tf_slice.%s.%s" % (name, event), definitions)

        expected_files = (
            "raven/caw1.ogg",
            "raven/squawk1.ogg",
            "redcap/redcap1.ogg",
            "redcap/hurt1.ogg",
            "redcap/die1.ogg",
            "kobold/ambient1.ogg",
            "kobold/hurt1.ogg",
            "kobold/death1.ogg",
            "hostile_wolf/idle1.ogg",
            "hostile_wolf/hurt1.ogg",
            "hostile_wolf/target.ogg",
            "wraith/wraith1.ogg",
        )
        for relative in expected_files:
            self.assertTrue(
                (RP / "sounds" / "mob" / relative).is_file(), relative
            )

    def test_special_ai_is_not_reduced_to_generic_melee(self):
        raven = behavior("raven")["components"]
        self.assertIn("minecraft:behavior.tempt", raven)
        self.assertIn("minecraft:navigation.fly", raven)

        druid = behavior("skeleton_druid")["components"]
        self.assertIn("minecraft:behavior.ranged_attack", druid)
        self.assertEqual(
            "tf_slice:nature_bolt",
            druid["minecraft:shooter"]["def"],
        )
        projectile = behavior("nature_bolt")["components"][
            "minecraft:projectile"
        ]
        self.assertEqual(2, projectile["on_hit"]["impact_damage"]["damage"])

        swarm = behavior("swarm_spider")["components"]
        self.assertEqual(3, swarm["minecraft:health"]["max"])
        self.assertEqual(1, swarm["minecraft:attack"]["damage"])
        self.assertEqual(0.3, swarm["minecraft:movement"]["value"])
        self.assertTrue(
            swarm["minecraft:behavior.nearest_attackable_target"]["must_see"]
        )
        self.assertEqual(
            16,
            swarm["minecraft:behavior.nearest_attackable_target"]
            ["entity_types"][0]["max_dist"],
        )
        self.assertEqual(
            1.0,
            swarm["minecraft:behavior.melee_attack"]["speed_multiplier"],
        )
        self.assertEqual(
            0.8,
            swarm["minecraft:behavior.random_stroll"]["speed_multiplier"],
        )
        self.assertEqual(
            0.4,
            swarm["minecraft:behavior.leap_at_target"]["yd"],
        )
        self.assertIn("minecraft:rideable", swarm)

        hedge = behavior("hedge_spider")["components"]
        self.assertEqual(16, hedge["minecraft:health"]["max"])
        self.assertEqual(2, hedge["minecraft:attack"]["damage"])
        self.assertEqual(0.3, hedge["minecraft:movement"]["value"])
        self.assertTrue(
            hedge["minecraft:behavior.nearest_attackable_target"]["must_see"]
        )
        self.assertEqual(
            16,
            hedge["minecraft:behavior.nearest_attackable_target"]
            ["entity_types"][0]["max_dist"],
        )
        self.assertEqual(
            1.0,
            hedge["minecraft:behavior.melee_attack"]["speed_multiplier"],
        )
        self.assertEqual(
            0.8,
            hedge["minecraft:behavior.random_stroll"]["speed_multiplier"],
        )
        self.assertEqual(
            0.4,
            hedge["minecraft:behavior.leap_at_target"]["yd"],
        )
        self.assertIn("minecraft:rideable", hedge)

        druid_entity = behavior("skeleton_druid")
        self.assertIn("tf_slice:baby", druid_entity["component_groups"])
        self.assertIn("tf_slice:make_baby", druid_entity["events"])

        wolf = behavior("hostile_wolf")["components"]
        self.assertIn("minecraft:behavior.leap_at_target", wolf)

        wraith = behavior("wraith")["components"]
        self.assertFalse(wraith["minecraft:physics"]["has_gravity"])
        self.assertFalse(wraith["minecraft:physics"]["has_collision"])
        self.assertFalse(wraith["minecraft:pushable"]["is_pushable"])
        self.assertFalse(
            wraith["minecraft:behavior.nearest_attackable_target"]["must_see"]
        )
        self.assertEqual(
            ["controller.render.tf_slice.wraith"],
            client("wraith")["render_controllers"],
        )
        render_controller = read_json(
            RP / "render_controllers" / "ruin_mobs.render.json"
        )["render_controllers"]["controller.render.tf_slice.wraith"]
        self.assertEqual(0.6, render_controller["color"]["a"])

        self.assertEqual(
            {"width": 0.8, "height": 0.4},
            swarm["minecraft:collision_box"],
        )
        self.assertEqual(
            {"width": 1.4, "height": 0.9},
            hedge["minecraft:collision_box"],
        )

        spider_animations = {
            "default_leg_pose": "animation.spider.default_leg_pose",
            "look_at_target": "animation.spider.look_at_target",
            "walk": "animation.spider.walk",
        }
        self.assertEqual(spider_animations, client("swarm_spider")["animations"])
        self.assertEqual(spider_animations, client("hedge_spider")["animations"])
        self.assertEqual("0.5", client("swarm_spider")["scripts"]["scale"])

        rising = behavior("rising_zombie")
        self.assertIn("tf_slice:rising", rising["component_groups"])
        self.assertIn(
            "minecraft:transformation",
            rising["events"]["tf_slice:finish_rising"]["add"][
                "component_groups"
            ]
            and rising["component_groups"]["tf_slice:transform"],
        )

        kobold = behavior("kobold")
        self.assertIn(
            "minecraft:behavior.pickup_items", kobold["components"]
        )
        self.assertIn("tf_slice:panic", kobold["events"])

    def test_python_closes_the_behaviors_bedrock_cannot_express(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "ProjectileDoHitEffectEvent",
            "AddEffectToEntity",
            "poison",
            "_update_ruin_mobs",
            "_panic_nearby_kobolds",
            "_spawn_swarm_companions",
            "_update_redcap",
            "_maybe_spawn_spider_jockey",
            "SetRiderRideEntity",
            "_swarm_attack_is_allowed",
        ):
            self.assertIn(marker, source)

    def test_unloaded_ruin_mobs_are_pruned_after_first_missing_position(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        start = source.index("    def _update_ruin_mobs(self):")
        handler = source[
            start:source.index("    def _on_navigation_result(", start)
        ]
        missing_start = handler.index("            if pos is None:")
        missing_branch = handler[
            missing_start:handler.index("            mobType =", missing_start)
        ]

        self.assertIn(
            "self._ruin_mobs.pop(entityId, None)",
            missing_branch,
        )

    def test_twilight_druid_jockey_rules_are_spider_specific(self):
        import spider_logic

        self.assertTrue(
            spider_logic.druid_jockey_is_allowed(
                "tf_slice:king_spider", 0, 19
            )
        )
        self.assertFalse(
            spider_logic.druid_jockey_is_allowed(
                "tf_slice:hedge_spider", 3, 0
            )
        )
        self.assertTrue(
            spider_logic.druid_jockey_is_allowed(
                "tf_slice:swarm_spider", 2, 2
            )
        )
        self.assertFalse(
            spider_logic.druid_jockey_is_allowed(
                "tf_slice:swarm_spider", 2, 3
            )
        )
        self.assertTrue(
            spider_logic.druid_jockey_is_baby("tf_slice:swarm_spider")
        )
        self.assertFalse(
            spider_logic.druid_jockey_is_baby("tf_slice:king_spider")
        )

    def test_ruin_dependency_items_exist(self):
        for name in (
            "raven_feather",
            "torchberries",
            "ironwood_pickaxe",
            "ironwood_boots",
        ):
            item = read_json(BP / "items" / ("%s.item.json" % name))[
                "minecraft:item"
            ]
            self.assertEqual(
                "tf_slice:%s" % name, item["description"]["identifier"]
            )
            self.assertTrue(
                (RP / "textures" / "items" / ("%s.png" % name)).is_file()
            )


if __name__ == "__main__":
    unittest.main()
