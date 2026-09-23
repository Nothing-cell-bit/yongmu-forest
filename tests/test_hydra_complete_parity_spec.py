# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
PACKAGE_ROOT = BP / "TwilightBossSlice"
sys.path.insert(0, str(PACKAGE_ROOT))

import hydra_logic


def read_json(path):
    return json.loads(path.read_text("utf-8"))


class HydraCompleteParityLogicTests(unittest.TestCase):
    def test_source_damage_scaling_matrix(self):
        self.assertEqual(
            (0.0, 25.0, 48.0, 72.0),
            tuple(
                hydra_logic.difficulty_scaled_damage(48.0, difficulty)
                for difficulty in range(4)
            ),
        )
        self.assertEqual(
            (0.0, 10.5, 19.0, 28.5),
            tuple(
                hydra_logic.difficulty_scaled_damage(19.0, difficulty)
                for difficulty in range(4)
            ),
        )
        self.assertEqual(
            (0.0, 10.0, 18.0, 27.0),
            tuple(
                hydra_logic.difficulty_scaled_damage(18.0, difficulty)
                for difficulty in range(4)
            ),
        )

    def test_root_immunity_and_source_multipart_dimensions(self):
        self.assertEqual(
            {
                "body": (6.0, 6.0),
                "left_leg": (2.0, 3.0),
                "right_leg": (2.0, 3.0),
                "tail": (6.0, 2.0),
                "head": (4.0, 4.0),
                "neck": (2.0, 2.0),
            },
            hydra_logic.PART_COLLISIONS,
        )
        self.assertEqual(
            0.0,
            hydra_logic.accepted_multipart_damage(
                48.0, "root", False, True, False
            ),
        )
        self.assertEqual(
            48.0,
            hydra_logic.accepted_multipart_damage(
                48.0, "root", False, True, True
            ),
        )
        self.assertEqual(
            6.0,
            hydra_logic.accepted_multipart_damage(
                48.0, "body", False, True, False
            ),
        )
        self.assertEqual(
            48.0,
            hydra_logic.accepted_multipart_damage(
                48.0, "head", True, True, False
            ),
        )
        self.assertEqual(
            0.0,
            hydra_logic.accepted_multipart_damage(
                48.0, "head", True, False, False
            ),
        )

    def test_one_shared_chain_frame_owns_head_and_five_necks(self):
        frame = hydra_logic.head_chain_frame(
            index=0,
            previous_state="idle",
            state="flame_begin",
            state_ticks=20,
            world_tick=120,
            body_position=(10.0, 64.0, 20.0),
            body_yaw=30.0,
            head_yaw=40.0,
            head_pitch=-10.0,
        )
        self.assertEqual(5, len(frame["necks"]))
        self.assertEqual(frame["head_position"], frame["neck_endpoint"])
        self.assertAlmostEqual(0.375, frame["mouth"], places=6)
        self.assertEqual((40.0, -10.0), frame["facing"])

    def test_newborn_roar_closes_once_after_idle_self_rollover(self):
        previous = "roar"
        state = "idle"
        ticks = 0
        mouths = []
        rollovers = []
        for elapsed in range(31):
            mouths.append(
                hydra_logic.interpolated_head_pose(
                    previous, state, 0, ticks
                )[3]
            )
            brain = hydra_logic.HydraHeadBrain(state, ticks)
            brain.tick()
            if brain.rolled_over:
                previous = state
                rollovers.append(elapsed + 1)
            state = brain.state
            ticks = brain.ticks
        self.assertEqual([10, 20, 30], rollovers)
        self.assertEqual(1.0, mouths[0])
        self.assertAlmostEqual(0.1, mouths[9], places=6)
        self.assertEqual(0.0, mouths[10])
        self.assertEqual([0.0] * 21, mouths[10:])

    def test_real_actor_interpolation_wraps_yaw_and_offsets_in_local_space(self):
        sample = hydra_logic.interpolated_actor_transform(
            previous_position=(0.0, 64.0, 0.0),
            target_position=(2.0, 66.0, 4.0),
            previous_rotation=(10.0, 170.0),
            target_rotation=(20.0, -170.0),
            elapsed_ticks=0.75,
            duration_ticks=1.5,
        )
        self.assertEqual((1.0, 65.0, 2.0), sample["position"])
        self.assertEqual((15.0, 180.0), sample["rotation"])
        self.assertEqual(0.5, sample["factor"])
        local = hydra_logic.world_offset_to_local(
            (1.0, 2.0, 0.0), 90.0
        )
        self.assertAlmostEqual(0.0, local[0], places=6)
        self.assertEqual(2.0, local[1])
        self.assertAlmostEqual(-1.0, local[2], places=6)
        self.assertEqual(1.5, hydra_logic.HYDRA_CLIENT_TWEEN_TICKS)

    def test_camera_virtual_world_helpers_are_not_gameplay_logic(self):
        self.assertFalse(hasattr(hydra_logic, "virtual_model_rotation"))
        self.assertFalse(
            hasattr(hydra_logic, "HYDRA_VISUAL_TWEEN_SECONDS")
        )

    def test_bite_yaw_clamps_and_source_throw_motion(self):
        self.assertEqual(-60.0, hydra_logic.clamp_bite_yaw(0, 0.0, 20.0))
        self.assertEqual(-90.0, hydra_logic.clamp_bite_yaw(1, 0.0, -120.0))
        self.assertEqual(60.0, hydra_logic.clamp_bite_yaw(2, 0.0, -20.0))
        # Locked HydraHeadContainer#setHeadFacing adds the literal PI / 4
        # value to the engine X-rotation field. Preserve the upstream quirk;
        # converting it to 45 degrees makes the whole neck fold violently.
        self.assertAlmostEqual(
            __import__("math").pi / 4.0,
            hydra_logic.bite_pitch_degrees(0.0),
            places=12,
        )
        self.assertAlmostEqual(
            -12.5 + __import__("math").pi / 4.0,
            hydra_logic.bite_pitch_degrees(-12.5),
            places=12,
        )
        self.assertEqual(
            (0.0, 0.1, -0.5),
            hydra_logic.bite_throw_motion(0.0, False),
        )
        self.assertEqual(
            (0.0, 0.15, -0.5),
            hydra_logic.bite_throw_motion(0.0, True),
        )

    def test_target_acquisition_retention_and_idle_yaw(self):
        self.assertTrue(hydra_logic.should_acquire_target(0.699999))
        self.assertFalse(hydra_logic.should_acquire_target(0.7))
        self.assertEqual(200, hydra_logic.target_expiry_tick(100, 0))
        self.assertEqual(219, hydra_logic.target_expiry_tick(100, 19))
        self.assertTrue(
            hydra_logic.target_is_retained(199, 200, True, 48.0 * 48.0)
        )
        self.assertFalse(
            hydra_logic.target_is_retained(200, 200, True, 1.0)
        )
        self.assertEqual(
            (15.0, 5.0),
            hydra_logic.idle_body_yaw(10.0, 2.0, True, 5.0),
        )
        self.assertEqual(
            (12.0, 2.0),
            hydra_logic.idle_body_yaw(10.0, 2.0, False, 0.0),
        )

    def test_source_body_yaw_smooths_entity_yaw_before_multipart_positions(self):
        # LivingEntity.aiStep passes the current yBodyRot as tickHeadTurn's
        # first argument while horizontal movement is zero. Hydra explicitly
        # zeros its movement input, so small raw-yaw rerolls must not rotate
        # the multipart body at all.
        self.assertEqual(
            0.0,
            hydra_logic.body_yaw_after_head_turn(0.0, 0.0, 10.0),
        )
        self.assertAlmostEqual(
            30.0,
            hydra_logic.body_yaw_after_head_turn(0.0, 0.0, 90.0),
            places=6,
        )
        body_yaw = 0.0
        entity_yaw = 0.0
        samples = []
        for velocity in (10.0, -10.0, 10.0, -10.0, 10.0, -10.0):
            entity_yaw += velocity
            body_yaw = hydra_logic.body_yaw_after_head_turn(
                body_yaw, body_yaw, entity_yaw
            )
            samples.append(body_yaw)
        self.assertEqual(
            (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            tuple(round(value, 6) for value in samples),
        )

    def test_idle_facing_target_uses_hydra_root_raw_yaw_and_source_height(self):
        target = hydra_logic.idle_face_target(
            (10.0, 64.0, 20.0), 90.0
        )
        for expected, actual in zip((-20.0, 67.0, 20.0), target):
            self.assertAlmostEqual(expected, actual, places=6)
        self.assertEqual(
            (10.0, 67.0, 50.0),
            hydra_logic.idle_face_target(
                (10.0, 64.0, 20.0), 0.0
            ),
        )
        self.assertEqual(40.0, hydra_logic.HYDRA_MAX_HEAD_X_ROT)

    def test_netease_idle_visual_policy_locks_body_but_not_raw_head_yaw(self):
        for entity_yaw in (-720.0, -90.0, 0.0, 90.0, 720.0):
            self.assertEqual(
                37.5,
                hydra_logic.locked_idle_body_yaw(37.5, entity_yaw),
            )
        self.assertTrue(hydra_logic.HYDRA_IDLE_BODY_LOCKED)

    def test_netease_idle_visual_policy_locks_chain_but_allows_head_facing(self):
        common = {
            "index": 1,
            "previous_state": "idle",
            "state": "idle",
            "state_ticks": 5,
            "body_position": (10.0, 64.0, 20.0),
            "body_yaw": 30.0,
            "head_pitch": 0.0,
            "lock_idle_chain": True,
        }
        first = hydra_logic.head_chain_frame(
            world_tick=0, head_yaw=30.0, **common
        )
        second = hydra_logic.head_chain_frame(
            world_tick=55, head_yaw=90.0, **common
        )
        self.assertEqual(first["head_position"], second["head_position"])
        self.assertEqual(first["necks"], second["necks"])
        self.assertEqual((30.0, 0.0), first["facing"])
        self.assertEqual((90.0, 0.0), second["facing"])
        self.assertTrue(hydra_logic.HYDRA_IDLE_CHAIN_LOCKED)

    def test_mobile_visual_idle_and_combat_state_classification(self):
        self.assertTrue(hydra_logic.lock_idle_chain_for_state("idle"))
        self.assertTrue(hydra_logic.lock_idle_chain_for_state("cooldown"))
        self.assertFalse(hydra_logic.lock_idle_chain_for_state("bite_begin"))
        self.assertFalse(hydra_logic.combat_body_turn_active(["idle", "cooldown"]))
        for state in (
            "bite_begin", "bite_ready", "biting", "bite_end",
            "flame_begin", "flaming", "flame_end",
            "mortar_begin", "mortar_shoot", "mortar_end",
        ):
            self.assertTrue(hydra_logic.combat_body_turn_active(["idle", state]))

    def test_mobile_idle_head_yaw_is_bounded_and_head_specific(self):
        self.assertAlmostEqual(
            35.0,
            hydra_logic.mobile_idle_head_yaw(
                30.0, 0, 10.0 * __import__("math").pi / 2.0
            ),
            places=6,
        )
        self.assertAlmostEqual(
            35.0,
            hydra_logic.mobile_idle_head_yaw(
                30.0, 1, 6.0 * __import__("math").pi / 2.0
            ),
            places=6,
        )
        samples = [
            hydra_logic.mobile_idle_head_yaw(30.0, index, 10.0)
            for index in range(3)
        ]
        self.assertEqual(3, len(set(round(value, 6) for value in samples)))
        for index in range(7):
            for tick in range(400):
                yaw = hydra_logic.mobile_idle_head_yaw(
                    30.0, index, tick
                )
                self.assertLessEqual(abs(yaw - 30.0), 5.0)
        self.assertEqual(5.0, hydra_logic.HYDRA_IDLE_HEAD_SWAY_DEGREES)

    def test_looting_bonus_is_applied_per_level(self):
        self.assertEqual(
            {"hydra_chop": 7, "fiery_blood": 10, "hydra_trophy": 1},
            hydra_logic.hydra_loot_counts(
                base_chops=5,
                base_blood=7,
                looting_level=2,
                chop_roll=1.0,
                blood_roll=1.5,
            ),
        )


class HydraCompleteParityAssetTests(unittest.TestCase):
    def test_head_proxy_is_source_four_by_four(self):
        head = read_json(BP / "entities" / "hydra_head.entity.json")[
            "minecraft:entity"
        ]
        self.assertEqual(
            {"width": 4.0, "height": 4.0},
            head["components"]["minecraft:collision_box"],
        )

    def test_invisible_body_part_proxy_has_source_component_groups(self):
        behavior = read_json(
            BP / "entities" / "hydra_part_proxy.entity.json"
        )["minecraft:entity"]
        groups = behavior["component_groups"]
        self.assertEqual(
            {"width": 6.0, "height": 6.0},
            groups["tf_slice:body"]["minecraft:collision_box"],
        )
        self.assertEqual(
            {"width": 2.0, "height": 3.0},
            groups["tf_slice:leg"]["minecraft:collision_box"],
        )
        self.assertEqual(
            {"width": 6.0, "height": 2.0},
            groups["tf_slice:tail"]["minecraft:collision_box"],
        )
        client = read_json(
            RP / "entity" / "hydra_part_proxy.entity.json"
        )["minecraft:client_entity"]["description"]
        self.assertEqual(
            "geometry.tf_slice.hydra_part_proxy",
            client["geometry"]["default"],
        )
        geometries = read_json(
            RP / "models" / "entity" / "hydra_route.geo.json"
        )["minecraft:geometry"]
        proxy = next(
            value
            for value in geometries
            if value["description"]["identifier"]
            == "geometry.tf_slice.hydra_part_proxy"
        )
        self.assertTrue(all(not bone.get("cubes") for bone in proxy["bones"]))

    def test_head_mouth_uses_render_frame_smoothing(self):
        client = read_json(RP / "entity" / "hydra_head.entity.json")
        description = client["minecraft:client_entity"]["description"]
        pre_animation = " ".join(description["scripts"]["pre_animation"])
        self.assertIn("variable.hydra_mouth_render", pre_animation)
        self.assertIn("query.delta_time", pre_animation)
        animation = read_json(
            RP / "animations" / "hydra_route.animation.json"
        )["animations"]["animation.tf_slice.hydra_head.state"]
        encoded = json.dumps(animation)
        self.assertIn("variable.hydra_mouth_render", encoded)
        self.assertNotIn("query.property('tf_slice:mouth_open') *", encoded)

    def test_real_head_and_neck_reuse_locked_geometry_without_virtual_duplicates(self):
        head = read_json(RP / "entity" / "hydra_head.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        neck = read_json(RP / "entity" / "hydra_neck.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertEqual(
            "geometry.tf_slice.hydra_head", head["geometry"]["default"]
        )
        self.assertEqual(
            "geometry.tf_slice.hydra_neck", neck["geometry"]["default"]
        )
        self.assertFalse(
            (RP / "entity" / "hydra_head_visual.entity.json").exists()
        )
        self.assertFalse(
            (RP / "entity" / "hydra_neck_visual.entity.json").exists()
        )
        self.assertFalse(
            (BP / "entities" / "hydra_head_visual.entity.json").exists()
        )
        self.assertFalse(
            (BP / "entities" / "hydra_neck_visual.entity.json").exists()
        )
        controllers = read_json(
            RP / "render_controllers" / "hydra_route.render.json"
        )["render_controllers"]
        self.assertNotIn(
            "controller.render.tf_slice.hydra_virtual", controllers
        )

    def test_hydra_hud_is_source_like_blue_without_extra_darken_overlay(self):
        hud = read_json(RP / "ui" / "hydra_boss_hud.json")
        controls = hud["main"]["controls"]
        self.assertNotIn("darken", [next(iter(control)) for control in controls])
        root = controls[0]["boss_root"]
        frame = root["controls"][1]["bar_frame"]
        clip = frame["controls"][1]["bar_fill_clip"]
        fill = clip["controls"][0]["bar_fill"]
        self.assertEqual([0.0, 0.35, 1.0], fill["color"])
        self.assertEqual([182, 5], frame["size"])
        self.assertTrue(clip["clips_children"])


class HydraCompleteParityAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = (PACKAGE_ROOT / "serverSystem.py").read_text("utf-8")
        cls.client = (PACKAGE_ROOT / "clientSystem.py").read_text("utf-8")
        cls.generator = (ROOT / "tools" / "build_hydra_route_models.py").read_text(
            "utf-8"
        )

    def test_server_owns_body_parts_and_one_chain_frame(self):
        for marker in (
            'HYDRA_PART_PROXY_IDENTIFIER = "tf_slice:hydra_part_proxy"',
            "self._hydra_parts = {}",
            "def _ensure_hydra_body_parts",
            "def _compute_hydra_chain_frame",
            "def _apply_hydra_chain_frame",
        ):
            self.assertIn(marker, self.server)

    def test_hydra_attack_visibility_uses_its_source_height_not_beetle_feet(self):
        visibility = self.server.split("def _hydra_can_see", 1)[1].split(
            "def _hydra_secondary_target", 1
        )[0]
        self.assertIn("hydra_logic.hydra_eye_position(bodyPos)", visibility)
        self.assertIn("targetPos[1] + 0.8", visibility)
        self.assertIn("quest_ram_logic.ray_samples(start, end)", visibility)

        secondary = self.server.split(
            "def _hydra_secondary_target", 1
        )[1].split("def _track_hydra_head", 1)[0]
        self.assertIn("self._hydra_can_see(", secondary)
        self.assertIn('bodyPos, targetPos, state["dimensionId"]', secondary)
        self.assertNotIn("self._beetle_can_see", secondary)

        driver = self.server.split("def _drive_hydras", 1)[1].split(
            "def _sync_hydra_mortar_fuse", 1
        )[0]
        visible = driver.split("primaryVisible = bool(", 1)[1].split(
            ")\n            if target is not None:", 1
        )[0]
        self.assertIn(
            "self._hydra_can_see(\n                    bodyPos, target[1], state[\"dimensionId\"]",
            visible,
        )
        self.assertNotIn("self._beetle_can_see", visible)

    def test_real_actor_renderer_keeps_exact_proxy_positions(self):
        chain = self.server.split("def _apply_hydra_chain_frame", 1)[1].split(
            "def _hydra_neck_transforms", 1
        )[0]
        self.assertIn('CreatePos(headId).SetPos(frame["head_position"])', chain)
        self.assertNotIn('"HydraVisualFrame"', chain)
        necks = self.server.split("def _ensure_hydra_necks", 1)[1].split(
            "def _remove_hydra_neck_actors", 1
        )[0]
        self.assertIn("CF.CreatePos(neckId).SetPos(position)", necks)
        self.assertNotIn("def _move_hydra_visual_part", self.server)

    def test_missing_hydra_proxy_actors_are_retired_before_health_refresh(self):
        body_parts = self.server.split(
            "def _ensure_hydra_body_parts", 1
        )[1].split("def _remove_hydra_body_parts", 1)[0]
        self.assertIn(
            "if CF.CreatePos(partId).SetPos(position) is False:",
            body_parts,
        )
        self.assertIn(
            "if self._set_health(\n"
            "                    partId, hydra_logic.PART_ACTOR_HEALTH\n"
            "                ) is False:",
            body_parts,
        )
        self.assertIn("partIds[partKind] = None", body_parts)

        chain = self.server.split("def _apply_hydra_chain_frame", 1)[1].split(
            "def _hydra_neck_transforms", 1
        )[0]
        self.assertIn(
            'if CF.CreatePos(headId).SetPos(frame["head_position"]) is False:',
            chain,
        )
        self.assertIn(
            "if self._set_health(\n"
            "                headId, hydra_logic.PART_ACTOR_HEALTH\n"
            "            ) is False:",
            chain,
        )

        necks = self.server.split("def _ensure_hydra_necks", 1)[1].split(
            "def _remove_hydra_neck_actors", 1
        )[0]
        self.assertIn(
            "if CF.CreatePos(neckId).SetPos(position) is False:",
            necks,
        )

        driver = self.server.split("def _drive_hydras", 1)[1].split(
            "def _sync_hydra_mortar_fuse", 1
        )[0]
        death_driver = driver.split('if state.get("dying"):', 1)[1].split(
            "continue\n            self._ensure_hydra_body_parts", 1
        )[0]
        self.assertIn(
            "if not self._apply_hydra_chain_frame(",
            death_driver,
        )
        self.assertIn("self._remove_hydra_head_actor(head)", death_driver)

        for marker in (
            '"HydraVisualFrame"',
            "self.OnHydraVisualFrame",
            "ModelCreateMinecraftObject",
            "ModelMoveTo",
            "ModelRotateTo",
            "ModelUpdateAnimationMolangVariable",
            "HYDRA_MODEL_FALLBACK_OFFSET",
            "def _clear_hydra_virtual_models",
        ):
            self.assertNotIn(marker, self.client)
        driver = self.server.split("def _drive_hydras", 1)[1].split(
            "def _sync_hydra_mortar_fuse", 1
        )[0]
        self.assertIn("frame = self._compute_hydra_chain_frame", driver)
        self.assertIn("self._apply_hydra_chain_frame", driver)

    def test_real_actor_renderer_has_client_tick_interpolation_without_virtual_world(self):
        chain = self.server.split("def _apply_hydra_chain_frame", 1)[1].split(
            "def _hydra_neck_transforms", 1
        )[0]
        self.assertIn('"HydraActorFrame"', chain)
        self.assertIn('"entityId": headId', chain)
        self.assertIn('"parts": visualParts', chain)
        for marker in (
            '"HydraActorFrame"',
            "self.OnHydraActorFrame",
            "self._hydra_actor_visuals = {}",
            "def _update_hydra_actor_visuals",
            "SetModelOffset",
            "CF.CreateRot(entityId).SetRot",
            "hydra_logic.interpolated_actor_transform",
            "hydra_logic.world_offset_to_local",
        ):
            self.assertIn(marker, self.client)
        for forbidden in (
            "CreateVirtualWorld",
            "ModelCreateMinecraftObject",
            "ModelMoveTo",
            "ModelRotateTo",
        ):
            self.assertNotIn(forbidden, self.client)

    def test_server_preserves_same_name_state_rollover(self):
        advance = self.server.split(
            "def _advance_hydra_head_brain", 1
        )[1].split("def _hydra_head_attack_tick", 1)[0]
        self.assertIn("if brain.rolled_over:", advance)
        self.assertIn('head["previousState"] = before', advance)

    def test_regrown_head_birth_cannot_change_authoritative_body_health(self):
        birth = self.server.split("def _birth_hydra_head", 1)[1].split(
            "def _spawn_hydra_mortar", 1
        )[0]
        snapshot = (
            'bodyHealth = max(0.0, float(state.get(\n'
            '            "health", hydra_logic.MAX_HEALTH\n'
            '        )))'
        )
        self.assertIn(snapshot, birth)
        self.assertIn('state["health"] = bodyHealth', birth)
        self.assertIn('self._set_health(hydraId, bodyHealth)', birth)
        self.assertLess(birth.index(snapshot), birth.index("head.update("))
        self.assertLess(
            birth.index("self._ensure_hydra_heads(hydraId, state)"),
            birth.index('state["health"] = bodyHealth'),
        )

    def test_source_heal_timer_does_not_survive_entity_reload(self):
        load = self.server.split("def _load_hydra_state", 1)[1].split(
            "def _save_hydra_state", 1
        )[0]
        save = self.server.split("def _save_hydra_state", 1)[1].split(
            "def _new_hydra_state", 1
        )[0]
        self.assertIn('"ticksSinceDamage": 0', load)
        self.assertNotIn('value.get("ticksSinceDamage"', load)
        self.assertNotIn('"ticksSinceDamage": int(', save)

    def test_accepted_head_damage_defers_one_tick_then_pushes_boss_bar(self):
        resolver = self.server.split("def _resolve_hydra_damage", 1)[1].split(
            "def _resolve_ur_ghast_damage", 1
        )[0]
        accepted = resolver.split("if accepted > 0.0:", 1)[1].split(
            "        return True", 1
        )[0]
        self.assertIn('state["health"] = max(', accepted)
        self.assertIn("self._boss_sync_dirty = True", accepted)
        self.assertNotIn("self._broadcast_sync()", accepted)
        self.assertLess(
            accepted.index('state["health"] = max('),
            accepted.index("self._boss_sync_dirty = True"),
        )
        initializer = self.server.split("def __init__", 1)[1].split(
            "def Destroy", 1
        )[0]
        self.assertIn("self._boss_sync_dirty = False", initializer)
        update = self.server.split("def Update", 1)[1].split(
            "def OnServerChatEvent", 1
        )[0]
        self.assertIn(
            "self._boss_sync_dirty\n"
            "            or self._tick % config.SYNC_INTERVAL_TICKS == 0",
            update,
        )
        self.assertIn("self._boss_sync_dirty = False", update)
        self.assertEqual(1, update.count("self._broadcast_sync()"))

    def test_multipart_health_uses_one_nonpersistent_source_hurt_window(self):
        resolver = self.server.split("def _resolve_hydra_damage", 1)[1].split(
            "def _resolve_ur_ghast_damage", 1
        )[0]
        self.assertIn("hydra_logic.shared_hurt_resolution(", resolver)
        self.assertIn('state.get("lastHurtAmount", 0.0)', resolver)
        self.assertIn('state.get("hurtWindowStartTick")', resolver)
        self.assertIn('state["lastHurtAmount"] = hurt["lastHurtAmount"]', resolver)
        self.assertIn(
            'state["hurtWindowStartTick"] = hurt["windowStartTick"]', resolver
        )
        self.assertIn(
            'state["health"] = max(\n'
            '                0.0, float(state["health"]) - healthDamage\n'
            '            )',
            resolver,
        )
        self.assertLess(
            resolver.index("hydra_logic.head_damage_credit(accepted)"),
            resolver.index("hydra_logic.shared_hurt_resolution("),
        )

        load = self.server.split("def _load_hydra_state", 1)[1].split(
            "def _save_hydra_state", 1
        )[0]
        save = self.server.split("def _save_hydra_state", 1)[1].split(
            "def _new_hydra_state", 1
        )[0]
        new = self.server.split("def _new_hydra_state", 1)[1].split(
            "def _register_hydra", 1
        )[0]
        for block in (load, new):
            self.assertIn('"lastHurtAmount": 0.0', block)
            self.assertIn('"hurtWindowStartTick": None', block)
        self.assertNotIn('"lastHurtAmount"', save)
        self.assertNotIn('"hurtWindowStartTick"', save)

    def test_server_separates_raw_entity_yaw_from_smoothed_body_yaw(self):
        driver = self.server.split("def _drive_hydras", 1)[1].split(
            "def _sync_hydra_mortar_fuse", 1
        )[0]
        for marker in (
            'entityYaw = float(state.get("entityYaw", engineBodyYaw))',
            "hydra_logic.body_yaw_after_head_turn",
            "bodyYaw, bodyYaw, entityYaw",
            'state["entityYaw"] = entityYaw',
            'state["bodyYaw"] = bodyYaw',
        ):
            self.assertIn(marker, driver)
        load = self.server.split("def _load_hydra_state", 1)[1].split(
            "def _save_hydra_state", 1
        )[0]
        save = self.server.split("def _save_hydra_state", 1)[1].split(
            "def _new_hydra_state", 1
        )[0]
        new = self.server.split("def _new_hydra_state", 1)[1].split(
            "def _register_hydra", 1
        )[0]
        self.assertIn('"entityYaw": float(value.get("entityYaw", bodyYaw))', load)
        self.assertIn('"version": 6', save)
        self.assertIn('"entityYaw": float(state.get("entityYaw", 0.0))', save)
        self.assertIn('"entityYaw": bodyYaw', new)

    def test_idle_head_facing_uses_shared_root_target_and_split_turn_limits(self):
        tracking = self.server.split("def _track_hydra_head", 1)[1].split(
            "def _face_hydra_head_state", 1
        )[0]
        self.assertIn("pitchTurnSpeed=None", tracking)
        self.assertIn("pitchStep = (", tracking)
        self.assertIn("currentPitch, wantedPitch, pitchStep", tracking)

        facing = self.server.split("def _face_hydra_head_state", 1)[1].split(
            "@staticmethod\n    def _hydra_head_direction", 1
        )[0]
        for marker in (
            "bodyPos = self._get_foot_pos(hydraId)",
            'entityYaw = float(state.get("entityYaw", bodyYaw))',
            "hydra_logic.idle_face_target(",
            "bodyPos, visualIdleYaw",
            "targetYOffset=-1.0",
            "turnSpeed=1.5",
            "pitchTurnSpeed=hydra_logic.HYDRA_MAX_HEAD_X_ROT",
        ):
            self.assertIn(marker, facing)
        self.assertNotIn("float(headPos[0]) + look[0] * 30.0", facing)
        self.assertEqual(
            4,
            facing.count(
                "pitchTurnSpeed=hydra_logic.HYDRA_MAX_HEAD_X_ROT"
            ),
        )

        idleBlock = facing.split("if targetPos is None:", 1)[1].split(
            '        if activeState in ("flame_begin", "flaming"):', 1
        )[0]
        for marker in (
            "hydra_logic.lock_idle_chain_for_state(activeState)",
            "hydra_logic.mobile_idle_head_yaw(",
            "bodyYaw, index, self._tick",
        ):
            self.assertIn(marker, idleBlock)
        self.assertIn("entityYaw", idleBlock)

    def test_no_target_policy_locks_body_while_combat_still_turns(self):
        driver = self.server.split("def _drive_hydras", 1)[1].split(
            "def _sync_hydra_mortar_fuse", 1
        )[0]
        targetBranch, idleBranch = driver.split(
            "if target is not None:", 1
        )[1].split("            else:", 1)
        idleBranch = idleBranch.split(
            "self._ensure_hydra_body_parts", 1
        )[0]
        self.assertIn("hydra_logic.body_yaw_after_head_turn", targetBranch)
        self.assertIn("hydra_logic.locked_idle_body_yaw", idleBranch)
        self.assertNotIn("hydra_logic.body_yaw_after_head_turn", idleBranch)
        self.assertIn('state["entityYaw"] = entityYaw', idleBranch)
        self.assertIn('state["bodyYaw"] = bodyYaw', idleBranch)

    def test_no_target_policy_locks_head_positions_and_necks_only(self):
        compute = self.server.split(
            "def _compute_hydra_chain_frame", 1
        )[1].split("def _apply_hydra_chain_frame", 1)[0]
        for marker in (
            'headState = str(head.get("state", "idle"))',
            "hydra_logic.lock_idle_chain_for_state(headState)",
            "lock_idle_chain=lockIdleChain",
        ):
            self.assertIn(marker, compute)
        self.assertNotIn('state.get("targetId") is None', compute)
        self.assertNotIn('head.get("targetId") is None', compute)

    def test_selected_target_does_not_turn_body_until_attack_state(self):
        driver = self.server.split("def _drive_hydras", 1)[1].split(
            "def _sync_hydra_mortar_fuse", 1
        )[0]
        targetBranch = driver.split("headStates = [", 1)[1].split(
            'state["entityYaw"] = entityYaw', 1
        )[0]
        for marker in (
            "hydra_logic.combat_body_turn_active",
            "hydra_logic.body_yaw_after_head_turn",
            "hydra_logic.locked_idle_body_yaw",
        ):
            self.assertIn(marker, targetBranch)

    def test_server_applies_difficulty_and_source_damage_causes(self):
        attack = self.server.split("def _hydra_head_attack_tick", 1)[1].split(
            "def _begin_hydra_death", 1
        )[0]
        self.assertIn("hydra_logic.difficulty_scaled_damage", attack)
        self.assertIn('causeName="EntityAttack"', attack)
        self.assertIn('causeName="Fire"', attack)
        resolver = self.server.split("def _resolve_hydra_damage", 1)[1].split(
            "def _resolve_ur_ghast_damage", 1
        )[0]
        self.assertIn('"root"', resolver)
        self.assertIn("accepted_multipart_damage", resolver)

    def test_bite_uses_box_contact_source_throw_and_complete_shield_path(self):
        bite = self.server.split("def _hydra_bite_targets", 1)[1].split(
            "def _advance_hydra_head_brain", 1
        )[0]
        self.assertIn("GetEntitiesInSquareArea", bite)
        attack = self.server.split("def _hydra_head_attack_tick", 1)[1].split(
            "def _begin_hydra_death", 1
        )[0]
        self.assertIn("hydra_logic.bite_throw_motion", attack)
        self.assertIn("self._stop_using_item", attack)
        self.assertIn("self._play_shield_break_sound", attack)

    def test_mortar_reflection_has_one_valid_actor_id(self):
        reflection = self.server.split("def _reflect_hydra_mortar", 1)[1].split(
            "def ", 1
        )[0]
        self.assertIn("mortarId", reflection)
        self.assertNotIn("projectileId", reflection)
        player_attack = self.server.split("def OnPlayerAttackEntityEvent", 1)[1].split(
            "def _protect_locked_lich_tower", 1
        )[0]
        self.assertIn("self._reflect_hydra_mortar", player_attack)
        self.assertNotIn(
            "_sync_hydra_mortar_fuse(projectileId", player_attack
        )

    def test_final_death_settlement_uses_complete_hydra_cleanup(self):
        driver = self.server.split("def _drive_hydras", 1)[1].split(
            "def _sync_hydra_mortar_fuse", 1
        )[0]
        settle = driver.split(
            'if event.get("settle") or state["deathTicks"] '
            '> hydra_logic.DEATH_TICKS:',
            1,
        )[1].split("            self._ensure_hydra_body_parts", 1)[0]
        self.assertIn(
            "self._discard_hydra(hydraId, state, restoreSpawner=False)",
            settle,
        )
        self.assertNotIn("self._remove_hydra_body_parts(state)", settle)
        self.assertNotIn("self.DestroyEntity(hydraId)", settle)

        cleanup = self.server.split("def _discard_hydra", 1)[1].split(
            "def _drive_hydras", 1
        )[0]
        for marker in (
            "self._remove_hydra_body_parts(state)",
            'for head in state.get("heads", ()):',
            "self._remove_hydra_head_actor(head)",
            "self._hydra_mortars.pop(mortarId, None)",
            "self._hydras.pop(hydraId, None)",
            "self.DestroyEntity(hydraId)",
        ):
            self.assertIn(marker, cleanup)

    def test_persistence_names_death_particles_and_looting_are_wired(self):
        for marker in (
            '"name": str(head.get("name", ""))',
            "def _sync_hydra_head_names",
            '"kind": "hydra_death_body"',
            "hydra_logic.hydra_loot_counts",
            "def _hydra_looting_level",
            "def _push_hydra_body_collisions",
        ):
            self.assertIn(marker, self.server)

    def test_generator_owns_every_new_runtime_artifact(self):
        for marker in (
            '"hydra_part_proxy":',
            'geometry.tf_slice.hydra_part_proxy',
            'variable.hydra_mouth_render',
            '"hydra_head", 1000000, 0, 0, (4.0, 4.0)',
            'hud("hydra_boss_hud", "九头蛇", [0.0, 0.35, 1.0]',
        ):
            self.assertIn(marker, self.generator)
        for marker in (
            '"hydra_head_visual"',
            '"hydra_neck_visual"',
            'controller.render.tf_slice.hydra_virtual',
            "def hydra_virtual_client_entity",
        ):
            self.assertNotIn(marker, self.generator)


if __name__ == "__main__":
    unittest.main()
