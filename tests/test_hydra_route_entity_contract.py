# -*- coding: utf-8 -*-
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"


def read(path):
    return json.loads(path.read_text("utf-8"))


class HydraRouteEntityContractTests(unittest.TestCase):
    def test_natural_boss_spawner_does_not_activate_on_peaceful(self):
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        handler = server_source.split(
            "def OnNagaSpawnerBlockEntityTick", 1
        )[1].split("def OnChunkGeneratedServerEvent", 1)[0]
        self.assertIn("if self._difficulty() <= 0:", handler)
        update = server_source.split("def Update(self):", 1)[1].split(
            "def OnNagaSpawnerBlockEntityTick", 1
        )[0]
        self.assertIn(
            "boss_spawning_enabled=(self._difficulty() > 0)",
            update,
        )

    def test_core_health_and_server_authority_contract(self):
        expected_health = {
            "minotaur": 30,
            "minoshroom": 120,
            "mosquito_swarm": 12,
            "hydra": 360,
        }
        for identifier, health in expected_health.items():
            entity = read(BP / "entities" / (identifier + ".entity.json"))["minecraft:entity"]
            self.assertEqual(health, entity["components"]["minecraft:health"]["max"])
            self.assertNotIn("minecraft:behavior.ranged_attack", entity["components"])

    def test_hydra_uses_seven_attackable_heads_and_five_visual_necks_per_head(self):
        self.assertTrue((BP / "entities" / "hydra_head.entity.json").is_file())
        self.assertTrue((BP / "entities" / "hydra_neck.entity.json").is_file())
        self.assertTrue((RP / "entity" / "hydra_neck.entity.json").is_file())
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text("utf-8")
        self.assertIn("HYDRA_HEAD_COUNT = 7", server_source)
        self.assertIn("HYDRA_NECK_COUNT = 5", server_source)
        self.assertIn("_ensure_hydra_heads", server_source)
        self.assertIn("_ensure_hydra_necks", server_source)
        self.assertIn("hydra_logic.neck_segment_transforms", server_source)
        self.assertIn("hydra_logic.neck_visual_rotation", server_source)
        self.assertIn("hydra_logic.accepted_multipart_damage", server_source)

    def test_hydra_parts_are_server_positioned_without_fall_or_collision_damage(self):
        hydra = read(BP / "entities" / "hydra.entity.json")["minecraft:entity"]
        head = read(BP / "entities" / "hydra_head.entity.json")["minecraft:entity"]
        neck = read(BP / "entities" / "hydra_neck.entity.json")["minecraft:entity"]
        self.assertFalse(hydra["components"]["minecraft:pushable"]["is_pushable"])
        self.assertIn("minecraft:fire_immune", hydra["components"])
        self.assertEqual(
            "ambient",
            hydra["components"]["minecraft:ambient_sound_interval"]["event_name"],
        )
        for part in (head, neck):
            self.assertEqual(
                {"has_gravity": False, "has_collision": False},
                part["components"]["minecraft:physics"],
            )
            self.assertFalse(part["components"]["minecraft:pushable"]["is_pushable"])
        self.assertGreater(
            neck["components"]["minecraft:health"]["max"], 120
        )
        self.assertGreater(
            head["components"]["minecraft:health"]["max"], 120
        )
        self.assertNotIn("minecraft:damage_sensor", neck["components"])

    def test_hydra_attacks_use_source_hit_settlement_and_effect_states(self):
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        client_source = (BP / "TwilightBossSlice" / "clientSystem.py").read_text(
            "utf-8"
        )
        self.assertIn("hydra_logic.flame_ray_target", server_source)
        self.assertIn("hydra_logic.register_attack_victim", server_source)
        self.assertIn("primaryVisible=True", server_source)
        self.assertIn('str(head.get("state", "idle")) in attackStates', server_source)
        self.assertIn('"flame_begin": "hydra_flame_charge"', server_source)
        self.assertIn('"mortar_begin": "hydra_mortar_charge"', server_source)
        self.assertIn('"kind": "hydra_part_death"', server_source)
        self.assertIn('if kind == "hydra_part_death":', client_source)
        self.assertNotIn("offsets = (\n            (-3.2, 4.0, 1.0)", client_source)
        self.assertIn('"minecraft:basic_flame_particle"', client_source)
        self.assertNotIn(
            '"tf_slice:hydra_flame"\n                    if state == "flaming"',
            client_source,
        )

    def test_hydra_runtime_hit_wiring_restores_visible_hurt_and_source_identity(self):
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        client_source = (BP / "TwilightBossSlice" / "clientSystem.py").read_text(
            "utf-8"
        )
        attack_handler = server_source.split(
            "def OnPlayerAttackEntityEvent", 1
        )[1].split("def _protect_locked_lich_tower", 1)[0]
        damage_handler = server_source.split(
            "def _resolve_hydra_damage", 1
        )[1].split("def OnHealthChangeBefore", 1)[0]

        self.assertIn("_remember_hydra_player_attack", attack_handler)
        self.assertIn("_pending_hydra_player_attacks", damage_handler)
        self.assertIn('args.get("byScript")', damage_handler)
        self.assertIn('"kind": "hydra_hurt"', server_source)
        self.assertIn('if kind == "hydra_hurt":', client_source)
        self.assertIn('"minecraft:critical_hit_emitter"', client_source)

    def test_hydra_hurt_flash_is_bound_to_body_head_and_neck_renderers(self):
        controller = read(RP / "render_controllers" / "hydra_route.render.json")
        hydra_controller = controller["render_controllers"][
            "controller.render.tf_slice.hydra_hurt"
        ]
        color_text = json.dumps(hydra_controller["color"])
        self.assertIn("tf_slice:hurt_flash", color_text)

        for identifier in ("hydra", "hydra_head", "hydra_neck"):
            behavior = read(BP / "entities" / (identifier + ".entity.json"))[
                "minecraft:entity"
            ]
            properties = behavior["description"]["properties"]
            self.assertTrue(properties["tf_slice:hurt_flash"]["client_sync"])
            self.assertIn("tf_slice:hurt_on", behavior["events"])
            self.assertIn("tf_slice:hurt_off", behavior["events"])

            client = read(RP / "entity" / (identifier + ".entity.json"))[
                "minecraft:client_entity"
            ]["description"]
            self.assertIn(
                "controller.render.tf_slice.hydra_hurt",
                client["render_controllers"],
            )

    def test_hydra_flame_uses_short_lived_world_space_source_samples(self):
        particle = read(RP / "particles" / "hydra_flame.json")["particle_effect"]
        description = particle["description"]
        billboard = particle["components"][
            "minecraft:particle_appearance_billboard"
        ]
        self.assertEqual("tf_slice:hydra_flame", description["identifier"])
        self.assertEqual(
            "textures/particle/particles",
            description["basic_render_parameters"]["texture"],
        )
        self.assertEqual([0, 24], billboard["uv"]["uv"])
        self.assertLessEqual(float(billboard["size"][0]), 0.5)

        client_source = (BP / "TwilightBossSlice" / "clientSystem.py").read_text(
            "utf-8"
        )
        flame_branch = client_source.split(
            'if kind == "hydra_flame_charge":', 1
        )[1].split('if kind == "hydra_mortar_trail":', 1)[0]
        self.assertIn('"minecraft:water_splash_particle_manual"', flame_branch)
        self.assertIn('"tf_slice:hydra_flame"', flame_branch)
        self.assertIn("hydra_logic.flame_particle_position", flame_branch)
        self.assertIn("hydra_logic.flame_visual_sample_ages", flame_branch)
        self.assertNotIn("rotation=particleRotation", flame_branch)
        self.assertNotIn("random.uniform(0.0, 30.0)", flame_branch)
        charge_branch = client_source.split(
            'if kind == "hydra_flame_charge":', 1
        )[1].split('if kind == "hydra_mortar_charge":', 1)[0]
        self.assertNotIn('"minecraft:basic_flame_particle"', charge_branch)
        components = particle["components"]
        self.assertNotIn("minecraft:emitter_local_space", components)
        self.assertEqual(0.0, components["minecraft:particle_initial_speed"])
        self.assertLessEqual(
            float(components["minecraft:particle_lifetime_expression"]["max_lifetime"]),
            0.3,
        )

    def test_hydra_head_and_neck_use_one_authoritative_rotation_stream(self):
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        neck_transform = server_source.split(
            "def _hydra_neck_transforms", 1
        )[1].split("def _bind_hydra_head", 1)[0]
        tracker = server_source.split(
            "def _track_hydra_head", 1
        )[1].split("def _hydra_head_direction", 1)[0]
        flame_tracking = server_source.split(
            'if activeState in ("flame_begin", "flaming"):', 1
        )[1].split("brain =", 1)[0]

        self.assertIn('head.get("pitch", 0.0)', neck_transform)
        self.assertIn('head.get("yaw", bodyYaw)', neck_transform)
        self.assertNotIn("self._get_rotation(headId)", neck_transform)
        self.assertIn('head.get("pitch", 0.0)', tracker)
        self.assertIn('head.get("yaw", 0.0)', tracker)
        self.assertNotIn("self._get_rotation(headId)", tracker)
        self.assertIn("targetYOffset=0.0", flame_tracking)
        self.assertIn("float(end[1]) - 0.5", neck_transform)

        head_position = server_source.split(
            "def _hydra_head_position", 1
        )[1].split("def _hydra_neck_transforms", 1)[0]
        self.assertIn("bodyYaw=None", head_position)
        self.assertIn("state.get(\"bodyYaw\"", server_source)
        self.assertIn("bodyYaw=state.get(\"bodyYaw\")", server_source)

        animations = read(RP / "animations" / "hydra_route.animation.json")[
            "animations"
        ]
        head_animation = json.dumps(
            animations["animation.tf_slice.hydra_head.state"]
        )
        neck_animation = json.dumps(
            animations["animation.tf_slice.hydra_neck.pose"]
        )
        self.assertNotIn("query.target_x_rotation", head_animation)
        self.assertNotIn("query.target_x_rotation", neck_animation)

    def test_hydra_flame_broad_phase_keeps_the_retained_target(self):
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        flame_target = server_source.split(
            "def _hydra_flame_target", 1
        )[1].split("def _hydra_bite_targets", 1)[0]
        flame_attack = server_source.split(
            'elif activeState == "flaming"', 1
        )[1].split('elif activeState == "mortar_shoot"', 1)[0]
        self.assertIn("preferredTargetId", flame_target)
        self.assertIn("self._get_online_players()", flame_target)
        self.assertIn("hydra_logic.merge_flame_candidate_ids", flame_target)
        self.assertIn('head.get("targetId")', flame_attack)

    def test_hydra_updates_head_state_before_one_shared_head_neck_pose(self):
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        driver = server_source.split("def _drive_hydras", 1)[1].split(
            "def _sync_hydra_mortar_fuse", 1
        )[0]
        attack = driver.index("self._hydra_head_attack_tick(")
        frame = driver.index(
            "frame = self._compute_hydra_chain_frame(", attack
        )
        apply_frame = driver.index(
            "self._apply_hydra_chain_frame(", frame
        )
        self.assertLess(attack, frame)
        self.assertLess(frame, apply_frame)

    def test_new_and_regrown_heads_seed_facing_from_current_body_yaw(self):
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        new_state = server_source.split("def _new_hydra_state", 1)[1].split(
            "def _register_hydra", 1
        )[0]
        birth = server_source.split("def _birth_hydra_head", 1)[1].split(
            "def _spawn_hydra_mortar", 1
        )[0]
        self.assertIn("bodyYaw = self._get_rotation(entityId)[1]", new_state)
        self.assertIn('"yaw": bodyYaw', new_state)
        self.assertIn("bodyYaw = self._get_rotation(hydraId)[1]", birth)
        self.assertIn('"yaw": bodyYaw', birth)

    def test_regrown_head_mouth_syncs_one_continuous_interpolated_value(self):
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        broadcast = server_source.split("def _broadcast_hydra_head", 1)[1].split(
            "def _sync_hydra_head_pose", 1
        )[0]
        sync = server_source.split("def _sync_hydra_head_pose", 1)[1].split(
            "def _kill_hydra_head", 1
        )[0]

        self.assertIn("hydra_logic.interpolated_head_pose", broadcast)
        self.assertIn(
            'self._set_entity_property(\n'
            '            headId, "tf_slice:mouth_open", pose[3]\n'
            '        )',
            sync,
        )
        self.assertNotIn("_hydra_mouth_event", sync)
        self.assertNotIn("_trigger_entity_event", sync)

    def test_hydra_mortar_is_static_and_uses_source_fire_and_landing_contract(self):
        mortar = read(BP / "entities" / "hydra_mortar.entity.json")[
            "minecraft:entity"
        ]
        client = read(RP / "entity" / "hydra_mortar.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        animations = read(RP / "animations" / "hydra_route.animation.json")[
            "animations"
        ]
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )

        self.assertIn("minecraft:fire_immune", mortar["components"])
        self.assertEqual(
            "entity_alphablend", client["materials"]["default"]
        )
        self.assertEqual(
            "animation.tf_slice.hydra_mortar.fuse",
            client["animations"]["main"],
        )
        self.assertNotIn("rotation", json.dumps(
            animations["animation.tf_slice.hydra_mortar.fuse"]
        ))
        self.assertNotIn("animation.tf_slice.hydra_mortar.spin", animations)
        self.assertIn("hydra_logic.mortar_launch_motion", server_source)
        self.assertIn("self._set_entity_on_fire(mortarId, 3600)", server_source)
        self.assertIn(
            "self._set_full_motion(\n"
            "                        projectileId,\n"
            "                        (float(motion[0]), 0.0, float(motion[2])),",
            server_source,
        )
        self.assertNotIn('"kind": "hydra_mortar_trail"', server_source)

    def test_hydra_mortar_syncs_locked_fuse_flash_and_swell_renderer(self):
        mortar = read(BP / "entities" / "hydra_mortar.entity.json")[
            "minecraft:entity"
        ]
        properties = mortar["description"]["properties"]
        self.assertEqual(
            [0, 100], properties["tf_slice:mortar_fuse"]["range"]
        )
        self.assertTrue(properties["tf_slice:mortar_fuse"]["client_sync"])
        self.assertTrue(properties["tf_slice:mortar_flash"]["client_sync"])
        self.assertIn("tf_slice:mortar_fuse_80", mortar["events"])
        self.assertIn("tf_slice:mortar_fuse_0", mortar["events"])

        controller = read(
            RP / "render_controllers" / "hydra_route.render.json"
        )["render_controllers"]["controller.render.tf_slice.hydra_mortar"]
        alpha = str(controller["color"]["a"])
        self.assertIn("0.075", alpha)
        self.assertIn("tf_slice:mortar_flash", alpha)
        self.assertIn("tf_slice:mortar_fuse", alpha)

        animation = read(RP / "animations" / "hydra_route.animation.json")[
            "animations"
        ]["animation.tf_slice.hydra_mortar.fuse"]
        scale = json.dumps(animation["bones"]["mortar"]["scale"])
        self.assertIn("tf_slice:mortar_fuse", scale)
        self.assertIn("0.3", scale)

        server_source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text("utf-8")
        self.assertIn("def _sync_hydra_mortar_fuse", server_source)
        update = server_source.split(
            "def _update_hydra_mortars", 1
        )[1].split("def _detonate_hydra_mortar", 1)[0]
        self.assertIn("self._sync_hydra_mortar_fuse", update)

    def test_hydra_body_has_a_creative_spawn_egg_but_internal_parts_do_not(self):
        hydra = read(BP / "entities" / "hydra.entity.json")["minecraft:entity"]
        self.assertTrue(hydra["description"]["is_spawnable"])
        self.assertTrue(hydra["description"]["is_summonable"])
        self.assertFalse(
            hydra["components"]["minecraft:pushable"]["is_pushable"]
        )

        client = read(RP / "entity" / "hydra.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertEqual(
            {"base_color": "#36150C", "overlay_color": "#D07B18"},
            client["spawn_egg"],
        )

        catalog = read(
            BP / "item_catalog" / "crafting_item_catalog.json"
        )
        items = catalog["minecraft:crafting_items_catalog"]["categories"][0][
            "groups"
        ][0]["items"]
        self.assertIn("tf_slice:hydra_spawn_egg", items)

        for language in ("en_US.lang", "zh_CN.lang"):
            text = (RP / "texts" / language).read_text("utf-8")
            self.assertIn(
                "item.spawn_egg.entity.tf_slice:hydra.name=", text
            )

        for identifier in ("hydra_head", "hydra_neck", "hydra_mortar"):
            part = read(BP / "entities" / (identifier + ".entity.json"))[
                "minecraft:entity"
            ]
            self.assertFalse(part["description"]["is_spawnable"])

    def test_hydra_mortar_uses_server_aoe_without_double_impact_damage(self):
        mortar = read(BP / "entities" / "hydra_mortar.entity.json")[
            "minecraft:entity"
        ]
        impact = mortar["components"]["minecraft:projectile"]["on_hit"][
            "impact_damage"
        ]
        self.assertEqual(0, impact["damage"])
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        self.assertIn("def _detonate_hydra_mortar(", server_source)
        self.assertIn("hydra_logic.MORTAR_DAMAGE", server_source)
        self.assertIn("self._set_entity_on_fire(targetId, 5)", server_source)

    def test_hydra_server_preserves_dormant_heads_and_source_combat_guards(self):
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        self.assertIn('"deadTicks": -1', server_source)
        self.assertIn('if int(head.get("deadTicks", -1)) >= 0:', server_source)
        self.assertIn("def _nearest_hydra_player(", server_source)
        self.assertIn("if self._is_creative(playerId):", server_source)
        self.assertIn("def _hydra_owned_damage_source(", server_source)
        self.assertIn("neckOwner = entity_registry_logic.matching_entity_key(", server_source)
        self.assertIn("self._set_full_motion(headId, (0.0, 0.0, 0.0))", server_source)

    def test_hydra_uses_locked_texture_material_and_custom_sound_family(self):
        for identifier in ("hydra", "hydra_head", "hydra_neck"):
            client = read(RP / "entity" / (identifier + ".entity.json"))[
                "minecraft:client_entity"
            ]["description"]
            self.assertEqual("entity_alphatest", client["materials"]["default"])
            self.assertEqual("textures/entity/hydra4", client["textures"]["default"])
        mortar_client = read(RP / "entity" / "hydra_mortar.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertEqual(
            "entity_alphablend", mortar_client["materials"]["default"]
        )
        self.assertEqual(
            "textures/entity/hydramortar", mortar_client["textures"]["default"]
        )
        definitions = read(RP / "sounds" / "sound_definitions.json")[
            "sound_definitions"
        ]
        for event in ("ambient", "hurt", "death", "roar", "warn"):
            self.assertIn("tf_slice.hydra." + event, definitions)
        for name in (
            "death", "growl1", "growl2", "growl3", "hurt1", "hurt2",
            "hurt3", "hurt4", "roar1", "roar2", "warn",
        ):
            self.assertTrue((RP / "sounds" / "mob" / "hydra" / (name + ".ogg")).is_file())

    def test_boss_rewards_include_locked_experience_and_unique_drops(self):
        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text("utf-8")
        self.assertIn("hydra_logic.XP_REWARD", server_source)
        self.assertIn("def _place_hydra_loot_chest", server_source)
        hydra_award = server_source.split("def _award_hydra_once", 1)[1].split(
            "def _clear_hydra_block_volume", 1
        )[0]
        self.assertIn("self._place_hydra_loot_chest(hydraId, state)", hydra_award)
        self.assertNotIn("self._deliver_item(", hydra_award)
        self.assertIn("HYDRA_LOOT_TABLE", (BP / "TwilightBossSlice" / "config.py").read_text("utf-8"))
        hydra_loot = read(BP / "loot_tables" / "chests" / "tf_slice" / "hydra_reward.json")
        self.assertIn('"max": 35', json.dumps(hydra_loot))
        self.assertIn("minotaur_logic.MINOSHROOM_XP_REWARD", server_source)
        self.assertIn("self._award_minoshroom_items(routeKey, routeState)", server_source)
        reward_source = (BP / "TwilightBossSlice" / "reward_delivery.py").read_text("utf-8")
        self.assertIn('"tf_slice:diamond_minotaur_axe"', reward_source)
        self.assertIn("_broadcast_hydra_head", server_source)
        self.assertIn("MINOSHROOM_STATE_EXTRA_KEY", server_source)
        self.assertIn("_save_minoshroom_state", server_source)

    def test_client_entities_bind_locked_geometry_and_textures(self):
        for identifier in (
            "minotaur", "minoshroom", "maze_slime", "mosquito_swarm",
            "hydra", "hydra_head", "hydra_neck", "hydra_mortar",
        ):
            client = read(RP / "entity" / (identifier + ".entity.json"))["minecraft:client_entity"]["description"]
            self.assertEqual("geometry.tf_slice." + identifier, client["geometry"]["default"])
            self.assertIn("default", client["textures"])

    def test_charge_and_slam_states_are_server_driven_and_client_synced(self):
        minotaur = read(BP / "entities" / "minotaur.entity.json")["minecraft:entity"]
        minoshroom = read(BP / "entities" / "minoshroom.entity.json")["minecraft:entity"]
        self.assertTrue(
            minotaur["description"]["properties"]["tf_slice:charging"]["client_sync"]
        )
        self.assertTrue(
            minoshroom["description"]["properties"]["tf_slice:charging"]["client_sync"]
        )
        self.assertTrue(
            minoshroom["description"]["properties"]["tf_slice:ground_attack"]["client_sync"]
        )
        slam_duration = minoshroom["description"]["properties"][
            "tf_slice:slam_duration"
        ]
        self.assertEqual("int", slam_duration["type"])
        # Fresh slams use 30-59 ticks; the lower bound also permits restoring
        # a partially elapsed wind-up after a server reload.
        self.assertEqual([1, 59], slam_duration["range"])
        self.assertEqual(30, slam_duration["default"])
        self.assertTrue(slam_duration["client_sync"])
        self.assertTrue(
            minoshroom["description"]["properties"][
                "tf_slice:ground_attack_recovering"
            ]["client_sync"]
        )
        for entity in (minotaur, minoshroom):
            self.assertIn("tf_slice:normal_ai", entity["component_groups"])
            self.assertIn("tf_slice:start_charging", entity["events"])
            self.assertIn("tf_slice:stop_charging", entity["events"])
            self.assertIn("minecraft:equipment", entity["components"])
        self.assertIn("tf_slice:start_ground_attack", minoshroom["events"])
        self.assertIn("tf_slice:stop_ground_attack", minoshroom["events"])
        self.assertIn("tf_slice:impact_ground_attack", minoshroom["events"])
        self.assertIn("tf_slice:finish_ground_recovery", minoshroom["events"])

        start_properties = minoshroom["events"][
            "tf_slice:start_ground_attack"
        ]["set_property"]
        self.assertTrue(start_properties["tf_slice:ground_attack"])
        self.assertFalse(
            start_properties["tf_slice:ground_attack_recovering"]
        )
        impact_properties = minoshroom["events"][
            "tf_slice:impact_ground_attack"
        ]["set_property"]
        self.assertFalse(impact_properties["tf_slice:ground_attack"])
        self.assertTrue(
            impact_properties["tf_slice:ground_attack_recovering"]
        )

        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        self.assertIn("def _set_entity_property(", server_source)
        self.assertIn("CreateQueryVariable(entityId)", server_source)
        # Native bool preservation is exercised against the real adapter in
        # test_goblin_combat_runtime; string booleans fail in the game engine.
        self.assertIn("else str(value)", server_source)
        self.assertIn(
            "SetPropertyValue(propertyName, encoded)", server_source
        )
        self.assertIn('"tf_slice:slam_duration"', server_source)
        self.assertIn("minotaur_logic.SLAM_RECOVERY_TICKS", server_source)

    def test_minotaurs_have_one_server_authoritative_close_melee_loop(self):
        minotaur = read(BP / "entities" / "minotaur.entity.json")["minecraft:entity"]
        minoshroom = read(BP / "entities" / "minoshroom.entity.json")["minecraft:entity"]
        for entity in (minotaur, minoshroom):
            # Native melee owns pursuit/swinging; the server owns damage so a
            # working native hit cannot stack with the scripted hit.
            self.assertEqual(0, entity["components"]["minecraft:attack"]["damage"])
            melee = entity["component_groups"]["tf_slice:normal_ai"][
                "minecraft:behavior.melee_attack"
            ]
            self.assertEqual(1.0, melee["cooldown_time"])
            self.assertTrue(melee["track_target"])

        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text("utf-8")
        self.assertIn('"targetId": None', server_source)
        self.assertIn('"meleeCooldown": 0', server_source)
        self.assertIn("def _drive_route_melee(", server_source)
        self.assertIn("minotaur_logic.advance_melee(", server_source)
        self.assertIn("self._set_attack_target(entityId, targetId)", server_source)
        self.assertIn("minotaur_logic.melee_attack_reach_sq(", server_source)
        self.assertIn("minotaur_logic.melee_damage(", server_source)

    def test_minotaurs_render_and_repair_their_source_mainhand_weapons(self):
        expected = {
            "minotaur": {
                "tf_slice:gold_minotaur_axe",
                "minecraft:golden_axe",
            },
            "minoshroom": {"tf_slice:diamond_minotaur_axe"},
        }
        geometries = {
            entry["description"]["identifier"]: entry
            for entry in read(
                RP / "models" / "entity" / "hydra_route.geo.json"
            )["minecraft:geometry"]
        }
        item_texture = read(RP / "textures" / "item_texture.json")
        texture_data = item_texture["texture_data"]

        for identifier, allowed_items in expected.items():
            client = read(RP / "entity" / (identifier + ".entity.json"))[
                "minecraft:client_entity"
            ]["description"]
            self.assertTrue(client.get("enable_attachables"), identifier)

            bones = {
                bone["name"]: bone
                for bone in geometries[
                    "geometry.tf_slice." + identifier
                ]["bones"]
            }
            self.assertEqual("rightArm", bones["rightItem"]["parent"])
            self.assertTrue(bones["rightItem"]["neverRender"])

            entity = read(BP / "entities" / (identifier + ".entity.json"))[
                "minecraft:entity"
            ]
            table = BP / entity["components"]["minecraft:equipment"]["table"]
            encoded_table = json.dumps(read(table))
            for item_name in allowed_items:
                self.assertIn(item_name, encoded_table)
                if item_name.startswith("tf_slice:"):
                    short_name = item_name.split(":", 1)[1]
                    item = read(BP / "items" / (short_name + ".item.json"))[
                        "minecraft:item"
                    ]
                    self.assertTrue(
                        item["components"].get("minecraft:hand_equipped")
                    )
                    self.assertIn(item_name, texture_data)

        server_source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            "utf-8"
        )
        self.assertIn("def _ensure_route_weapon(", server_source)
        self.assertIn("self._ensure_route_weapon(entityId, entityType)", server_source)

    def test_maze_slime_uses_size_groups_and_native_slime_hop_ai(self):
        entity = read(BP / "entities" / "maze_slime.entity.json")["minecraft:entity"]
        self.assertEqual(
            {"tf_slice:size_1", "tf_slice:size_2", "tf_slice:size_4"},
            set(entity["component_groups"]),
        )
        expected = {
            "tf_slice:size_1": (2, 1, 0.52),
            "tf_slice:size_2": (8, 2, 1.04),
            "tf_slice:size_4": (32, 4, 2.08),
        }
        for group, (health, damage, width) in expected.items():
            components = entity["component_groups"][group]
            self.assertEqual(health, components["minecraft:health"]["max"])
            self.assertEqual(damage, components["minecraft:attack"]["damage"])
            self.assertAlmostEqual(
                width, components["minecraft:collision_box"]["width"]
            )
        components = entity["components"]
        self.assertIn("minecraft:movement.jump", components)
        self.assertIn("minecraft:behavior.slime_attack", components)
        self.assertIn("minecraft:behavior.slime_random_direction", components)
        self.assertIn("minecraft:behavior.slime_keep_on_jumping", components)
        client = read(RP / "entity" / "maze_slime.entity.json")["minecraft:client_entity"]["description"]
        self.assertEqual("entity_alphatest", client["materials"]["inner"])
        self.assertEqual("slime_outer", client["materials"]["outer"])
        self.assertEqual(
            ["controller.render.tf_slice.maze_slime"],
            client["render_controllers"],
        )

    def test_route_does_not_reference_upstream_restricted_audio(self):
        payload = "\n".join(
            path.read_text("utf-8")
            for path in list((BP / "entities").glob("*.json"))
            + list((RP / "entity").glob("*.json"))
        )
        for forbidden in (
            "twilightforest:hydra", "twilightforest:minotaur",
            "twilightforest:minoshroom", "twilightforest:mosquito",
        ):
            self.assertNotIn(forbidden, payload)


if __name__ == "__main__":
    unittest.main()
