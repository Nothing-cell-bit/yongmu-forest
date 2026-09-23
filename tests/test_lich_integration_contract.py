# -*- coding: utf-8 -*-
import pathlib
import json
import unittest

from tests.test_structure_worldgen_handoff import FakeFactory, SERVICE


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = (
    ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "serverSystem.py"
).read_text(encoding="utf-8")
CLIENT = (
    ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "clientSystem.py"
).read_text(encoding="utf-8")
LICH_ENTITY = json.loads(
    (ROOT / "TwilightBossSliceB" / "entities" / "lich.entity.json").read_text(
        encoding="utf-8"
    )
)["minecraft:entity"]
LICH_CLIENT = json.loads(
    (ROOT / "TwilightBossSliceR" / "entity" / "lich.entity.json").read_text(
        encoding="utf-8"
    )
)["minecraft:client_entity"]["description"]
LICH_CLONE_CLIENT = json.loads(
    (
        ROOT
        / "TwilightBossSliceR"
        / "entity"
        / "lich_shadow_clone.entity.json"
    ).read_text(encoding="utf-8")
)["minecraft:client_entity"]["description"]
LICH_ANIMATIONS = {}
for animation_file in (
    "lich.animation.json",
    "zombie.animation.json",
    "death_tome.animation.json",
    "fortification_shields.animation.json",
):
    LICH_ANIMATIONS.update(
        json.loads(
            (
                ROOT / "TwilightBossSliceR" / "animations" / animation_file
            ).read_text(encoding="utf-8")
        )["animations"]
    )
LICH_CLONE_ENTITY = json.loads(
    (ROOT / "TwilightBossSliceB" / "entities" / "lich_shadow_clone.entity.json").read_text(
        encoding="utf-8"
    )
)["minecraft:entity"]
LICH_MINION_ENTITY = json.loads(
    (ROOT / "TwilightBossSliceB" / "entities" / "lich_minion.entity.json").read_text(
        encoding="utf-8"
    )
)["minecraft:entity"]
LICH_BOLT_ENTITY = json.loads(
    (ROOT / "TwilightBossSliceB" / "entities" / "lich_bolt.entity.json").read_text(
        encoding="utf-8"
    )
)["minecraft:entity"]
LICH_BOMB_ENTITY = json.loads(
    (ROOT / "TwilightBossSliceB" / "entities" / "lich_bomb.entity.json").read_text(
        encoding="utf-8"
    )
)["minecraft:entity"]
LICH_BOLT_CLIENT = json.loads(
    (ROOT / "TwilightBossSliceR" / "entity" / "lich_bolt.entity.json").read_text(
        encoding="utf-8"
    )
)["minecraft:client_entity"]["description"]
LICH_BOMB_CLIENT = json.loads(
    (ROOT / "TwilightBossSliceR" / "entity" / "lich_bomb.entity.json").read_text(
        encoding="utf-8"
    )
)["minecraft:client_entity"]["description"]


class LichServerIntegrationContractTests(unittest.TestCase):
    def test_potion_magic_is_correlated_before_shield_resolution(self):
        self.assertIn('"ActorHurtServerEvent"', SERVER)
        self.assertIn("def OnActorHurtServerEvent", SERVER)
        self.assertIn("self._recent_lich_effect_damage = {}", SERVER)
        self.assertIn("lich_logic.effect_damage_source_kind(", SERVER)
        self.assertIn("def _consume_lich_effect_damage", SERVER)

    def test_retaliation_accepts_non_player_living_attackers(self):
        target = SERVER[
            SERVER.index("    def _lich_player_candidate") : SERVER.index(
                "    def _lich_can_see"
            )
        ]
        self.assertIn("def _lich_retaliation_candidate", target)
        self.assertIn("self._get_engine_type(preferredId)", target)
        self.assertIn("LICH_CLONE_IDENTIFIER", target)

    def test_invalid_cast_target_restarts_the_source_windup(self):
        validation = SERVER[
            SERVER.index("    def _lich_cast_target_is_valid") : SERVER.index(
                "    def _navigate_lich_melee"
            )
        ]
        self.assertNotIn('state["castTargetId"] = replacement.get("id")', validation)
        self.assertNotIn("replacement =", validation)
        drive = SERVER[
            SERVER.index("    def _drive_lich_bosses") : SERVER.index(
                "    def _loyal_zombie_target"
            )
        ]
        self.assertIn("lich_logic.cancel_scepter_cast(state)", drive)
        self.assertIn("popTarget = self._lich_pop_target(", drive)

    def test_hurt_teleport_requires_accepted_life_damage(self):
        health = SERVER[
            SERVER.index("    def OnHealthChangeBefore") : SERVER.index(
                "    def OnActuallyHurtServerEvent"
            )
        ]
        hurt = SERVER[
            SERVER.index("    def OnActuallyHurtServerEvent") : SERVER.index(
                "    def OnMobHitBlock"
            )
        ]
        self.assertIn('lichState["lastAcceptedDamageTick"] = self._tick', health)
        self.assertIn('lichState.get("lastAcceptedDamageTick", -100)', hurt)

    def test_lich_projectiles_have_server_lifecycle_and_impact_fallbacks(self):
        spawn = SERVER[
            SERVER.index("    def _spawn_lich_projectile") : SERVER.index(
                "    def _teleport_lich"
            )
        ]
        self.assertIn("lich_logic.new_projectile_state(", spawn)
        self.assertIn('projectileState["velocity"] = velocity', spawn)
        self.assertIn("def _update_lich_projectiles", SERVER)
        self.assertIn("lich_logic.projectile_lifecycle_action(", SERVER)
        self.assertIn("self._update_lich_projectiles()", SERVER)

    def test_server_owns_lich_and_scepter_state_machines(self):
        self.assertIn("import TwilightBossSlice.lich_logic", SERVER)
        self.assertIn("import TwilightBossSlice.scepter_logic", SERVER)
        self.assertIn("def _drive_lich_bosses(", SERVER)
        self.assertIn("lich_logic.advance_combat_tick(", SERVER)
        self.assertIn("def _use_lich_scepter(", SERVER)
        self.assertIn("scepter_logic.use_fortification_scepter(", SERVER)

    def test_player_projectiles_use_camera_safe_muzzle_position(self):
        self.assertIn(
            "scepter_logic.player_projectile_spawn_position(position, look)",
            SERVER,
        )
        self.assertIn("spawnPosition,", SERVER)

    def test_twilight_scepter_consumes_only_after_projectile_spawn(self):
        use = SERVER[
            SERVER.index("        if kind == \"twilight_scepter\"") :
            SERVER.index("        if kind == \"lifedrain_scepter\"")
        ]
        self.assertIn("projectileId = self._spawn_player_projectile(", use)
        self.assertIn("if projectileId", use)
        self.assertLess(
            use.index("_spawn_player_projectile"),
            use.index("_consume_carried_charge"),
        )

    def test_lifedrain_hold_release_uses_the_engine_release_lifecycle(self):
        self.assertIn('"ItemReleaseUsingServerEvent"', SERVER)
        self.assertNotIn('"ServerItemReleaseUsingEvent"', SERVER)

        use = SERVER[
            SERVER.index("    def OnLichScepterTryUseEvent") : SERVER.index(
                "    def OnServerItemTryUseEvent"
            )
        ]
        self.assertIn(
            'if preferredName == "tf_slice:lifedrain_scepter":\n'
            "            self._use_lich_scepter(playerId, preferredName)\n"
            "            return",
            use,
        )

        release = SERVER[
            SERVER.index("    def OnItemReleaseUsingServerEvent") : SERVER.index(
                "    def OnPlayerAttackEntityEvent"
            )
        ]
        self.assertIn("self._end_lifedrain(playerId)", release)

    def test_lifedrain_has_a_client_release_fallback_and_aimed_targeting(self):
        self.assertIn('"TapOrHoldReleaseClientEvent"', CLIENT)
        self.assertIn('self.NotifyToServer("LifedrainReleaseRequest", {})', CLIENT)
        self.assertIn('"LifedrainReleaseRequest"', SERVER)
        self.assertIn("def OnLifedrainReleaseRequest", SERVER)

        target = SERVER[
            SERVER.index("    def _lifedrain_target") : SERVER.index(
                "    def _update_lifedrain_users"
            )
        ]
        self.assertIn("scepter_logic.select_aimed_target(", target)
        self.assertIn(".CanSee(", target)
        self.assertNotIn("return min(candidates)", target)

    def test_lifedrain_broadcasts_a_red_tether_on_successful_pulses(self):
        update = SERVER[
            SERVER.index("    def _update_lifedrain_users") : SERVER.index(
                "    def _begin_lich_death"
            )
        ]
        self.assertIn('"lifedrain_link"', update)
        self.assertIn('if kind == "lifedrain_link"', CLIENT)
        self.assertIn('"tf_slice:lifedrain_beam"', CLIENT)

    def test_lifedrain_stops_after_target_loss_or_charge_exhaustion(self):
        update = SERVER[
            SERVER.index("    def _update_lifedrain_users") : SERVER.index(
                "    def _begin_lich_death"
            )
        ]
        self.assertIn('state["missTicks"]', update)
        self.assertIn("LIFEDRAIN_TARGET_LOSS_GRACE_TICKS", update)
        self.assertIn("state[\"scepter\"].get(\"charges\", 0)", update)
        self.assertIn("self._end_lifedrain(playerId, True)", update)

    def test_fortification_reports_activation_blocks_and_enforces_cooldown(self):
        self.assertIn("self._fortification_cooldowns = {}", SERVER)
        use = SERVER[
            SERVER.index("        if kind == \"fortification_scepter\"") :
            SERVER.index("        return False", SERVER.index("        if kind == \"fortification_scepter\""))
        ]
        self.assertIn("self._fortification_cooldowns", use)
        self.assertIn('"fortification_activate"', use)
        self.assertIn("result[\"cooldown\"]", use)

        damage = SERVER[
            SERVER.index("        shieldKey =") : SERVER.index(
                "        if (", SERVER.index("        shieldKey =")
            )
        ]
        self.assertIn('"fortification_block"', damage)
        self.assertIn('if kind in ("fortification_activate", "fortification_block")', CLIENT)

    def test_fortification_reuses_lich_shields_and_always_blocks_while_present(self):
        self.assertIn("self._fortification_visuals = {}", SERVER)
        self.assertIn("def _sync_fortification_visual", SERVER)
        visual_sync = SERVER[
            SERVER.index("    def _sync_fortification_visual") : SERVER.index(
                "    def _update_fortification_shields"
            )
        ]
        self.assertNotIn("_spawn_ruin_entity", visual_sync)
        self.assertNotIn("CreateEntityDefinitions", visual_sync)
        self.assertIn('"fortification_visual_sync"', visual_sync)

        damage = SERVER[
            SERVER.index("        shieldKey =") : SERVER.index(
                "        if (", SERVER.index("        shieldKey =")
            )
        ]
        self.assertIn("scepter_logic.has_shield(shield)", damage)
        self.assertIn('args["cancel"] = True', damage)

    def test_fortification_visual_uses_one_bound_lich_shield_model(self):
        self.assertIn('"fortification_visual_sync"', SERVER)
        self.assertIn('"fortification_visual_remove"', SERVER)
        self.assertIn("self._fortification_visuals = {}", CLIENT)
        self.assertIn("def _update_fortification_visuals", CLIENT)
        visual_helpers = CLIENT[
            CLIENT.index("    def _clear_fortification_visuals") :
            CLIENT.index("    def _update_lich_state_effects")
        ]
        self.assertIn("self.CreateClientEntityByTypeStr(", visual_helpers)
        self.assertIn(
            'FORTIFICATION_VISUAL_IDENTIFIER = "tf_slice:fortification_shield_visual"',
            CLIENT,
        )
        self.assertIn("FORTIFICATION_VISUAL_IDENTIFIER", visual_helpers)
        self.assertIn("CF.CreatePos(ownerId).GetFootPos()", visual_helpers)
        self.assertNotIn("BindEntityToEntity", visual_helpers)
        self.assertNotIn("SetModelOffset", visual_helpers)
        self.assertIn("GetBonePositionFromMinecraftObject", visual_helpers)
        self.assertIn('"GameRenderTickEvent", self, self.OnFortificationRender', CLIENT)
        self.assertIn("CF.CreateQueryVariable(LEVEL_ID).Register(", visual_helpers)
        # Query writes and error handling are exercised by lifecycle runtime tests.
        self.assertIn("self.DestroyClientEntity(visualId)", visual_helpers)
        self.assertNotIn("_fortification_particle_comp", visual_helpers)
        self.assertNotIn("SetPos(", visual_helpers)
        self.assertNotIn("CreateBindEntityNew", visual_helpers)
        self.assertNotIn("CF.CreateActorRender", visual_helpers)
        self.assertNotIn("AddPlayer", visual_helpers)
        self.assertNotIn("RemovePlayer", visual_helpers)
        self.assertNotIn("RebuildPlayerRender", visual_helpers)
        self.assertIn('if kind == "fortification_visual_sync"', CLIENT)
        self.assertIn('if kind == "fortification_visual_remove"', CLIENT)
        skin_update = CLIENT[
            CLIENT.index("    def OnUpdatePlayerSkinClientEvent") :
            CLIENT.index("    def _ensure_magic_map_player_pose")
        ]
        self.assertNotIn("fortification", skin_update.lower())
        dimension_change = CLIENT[
            CLIENT.index("    def OnDimensionChangeClientEvent") :
            CLIENT.index("    def OnDimensionChangeFinishClientEvent")
        ]
        self.assertIn("self._clear_fortification_visuals()", dimension_change)

    def test_zombie_scepter_uses_aimed_open_cell_and_consumes_after_spawn(self):
        use = SERVER[
            SERVER.index("        if kind == \"zombie_scepter\"") :
            SERVER.index("        if kind == \"fortification_scepter\"")
        ]
        self.assertIn("scepter_logic.raycast_spawn_position(", use)
        self.assertNotIn("position[0] + 1.0", use)
        self.assertLess(use.index("if zombieId:"), use.index("_consume_carried_charge"))

    def test_player_twilight_projectile_uses_a_dedicated_light_trail(self):
        trail = CLIENT[
            CLIENT.index("        for entityId, trail") : CLIENT.index(
                "    def _is_local_dimension_event"
            )
        ]
        self.assertIn('style == "tf_slice:twilight_wand_bolt"', trail)
        self.assertIn('"tf_slice:twilight_scepter_trail"', trail)
        self.assertIn("self._lich_effect_tick % 4", trail)

        launch = CLIENT[
            CLIENT.index('        if kind == "projectile_launch"') :
            CLIENT.index('        if kind == "lifedrain_link"')
        ]
        self.assertIn('style == "tf_slice:twilight_wand_bolt"', launch)
        self.assertIn('"tf_slice:twilight_scepter_trail"', launch)
        self.assertIn("return", launch)

    def test_only_lifedrain_uses_a_continuous_bow_animation(self):
        item_root = ROOT / "TwilightBossSliceB" / "items"
        for name in (
            "twilight_scepter",
            "zombie_scepter",
            "fortification_scepter",
        ):
            components = json.loads(
                (item_root / (name + ".item.json")).read_text(encoding="utf-8")
            )["minecraft:item"]["components"]
            self.assertNotIn("minecraft:use_animation", components)
            self.assertNotIn("minecraft:use_duration", components)

        lifedrain = json.loads(
            (item_root / "lifedrain_scepter.item.json").read_text(encoding="utf-8")
        )["minecraft:item"]["components"]
        self.assertEqual("bow", lifedrain["minecraft:use_animation"])
        self.assertNotIn("minecraft:use_duration", lifedrain)
        self.assertEqual(
            3600.0,
            lifedrain["minecraft:use_modifiers"]["use_duration"],
        )
        self.assertEqual(
            0.2,
            lifedrain["minecraft:use_modifiers"]["movement_modifier"],
        )

    def test_server_uses_real_visibility_safe_teleport_and_melee_navigation(self):
        self.assertIn("def _lich_can_see(", SERVER)
        self.assertIn(".CanSee(", SERVER)
        self.assertIn(
            "self._lich_can_see(bossId, targetId)",
            SERVER,
        )
        self.assertIn(
            "self._lich_can_see(cloneId, targetId)",
            SERVER,
        )
        self.assertIn("def _safe_lich_destination(", SERVER)
        self.assertIn("for _unused in range(100):", SERVER)
        self.assertIn("def _navigate_lich_melee(", SERVER)
        self.assertNotIn(
            "math.sqrt(_distance_sq(position, targetPos)),\n                True,",
            SERVER,
        )

    def test_targeting_uses_source_follow_range_not_home_restriction(self):
        target = LICH_ENTITY["component_groups"]["tf_slice:combat_targeting"][
            "minecraft:behavior.nearest_attackable_target"
        ]
        self.assertEqual(35, target["within_radius"])
        self.assertEqual(35, target["entity_types"][0]["max_dist"])
        candidate = SERVER[
            SERVER.index("    def _lich_player_candidate") : SERVER.index(
                "    def _lich_target"
            )
        ]
        self.assertIn("lich_logic.TARGET_RANGE", candidate)
        self.assertNotIn("HOME_RADIUS", candidate)

    def test_server_persists_and_recovers_boss_clone_and_minion_relations(self):
        for text in (
            "def _load_lich_state(",
            "def _save_lich_state(",
            "def _register_lich_clone(",
            "def _register_lich_minion(",
            "LICH_CLONE_IDENTIFIER",
            "LICH_MINION_IDENTIFIER",
        ):
            self.assertIn(text, SERVER)

    def test_landmark_lich_uses_naga_style_stable_spawn_confirmation(self):
        spawn = SERVER[
            SERVER.index("    def _spawn_courtyard_naga") : SERVER.index(
                "    def _confirm_courtyard_naga"
            )
        ]
        confirm = SERVER[
            SERVER.index("    def _confirm_courtyard_naga") : SERVER.index(
                "    def _destroy_segment"
            )
        ]
        self.assertNotIn("self._register_lich(", spawn)
        self.assertIn('"identifier": identifier', spawn)
        self.assertIn("LICH_IDENTIFIER", confirm)
        self.assertIn("self._register_lich(", confirm)

        on_add = SERVER[
            SERVER.index("    def OnAddEntity") : SERVER.index(
                "    def OnRemoveEntity"
            )
        ]
        pending_check = on_add.index("self._pending_courtyard_naga(")
        direct_lich_registration = on_add.index(
            "if entityType == LICH_IDENTIFIER:"
        )
        self.assertLess(pending_check, direct_lich_registration)

    def test_manual_lich_death_cannot_mark_a_nearby_tower_defeated(self):
        finalize = SERVER[
            SERVER.index("    def _finalize_lich_death") : SERVER.index(
                "    def _lich_death_soul_position"
            )
        ]
        self.assertIn("lich_logic.landmark_death_is_authoritative(state)", finalize)

    def test_server_ports_pop_mobs_peaceful_restore_and_bomb_attack(self):
        self.assertIn("LICH_POPPABLE_IDENTIFIERS", SERVER)
        self.assertIn("def _lich_pop_target(", SERVER)
        self.assertIn("def _restore_lich_spawner(", SERVER)
        self.assertIn('"tf_slice:explode"', SERVER)

    def test_reflection_progress_and_tower_protection_are_event_bound(self):
        for event_name in (
            "PlayerAttackEntityEvent",
            "ServerPlayerTryDestroyBlockEvent",
            "ServerEntityTryPlaceBlockEvent",
        ):
            self.assertIn('"%s"' % event_name, SERVER)
        self.assertIn("lich_logic.reflect_bolt(", SERVER)
        self.assertIn('self._grant_progress(playerId, "tf_lich_defeated")', SERVER)
        self.assertIn("is_locked_lich_tower_position", SERVER)

    def test_sync_extension_is_additive_and_client_read_only(self):
        for field in (
            '"kind": "lich"',
            '"phase"',
            '"shieldStrength"',
            '"minionsRemaining"',
        ):
            self.assertIn(field, SERVER)
            self.assertIn(field.split(":", 1)[0], CLIENT)
        self.assertIn("Read-only client replica", CLIENT)
        self.assertNotIn("resolve_incoming_damage", CLIENT)

    def test_shared_boss_cap_counts_naga_and_lich(self):
        active = SERVER[SERVER.index("    def _active_boss_count") : SERVER.index(
            "    def _lich_key"
        )]
        self.assertIn("self._bosses.values()", active)
        self.assertIn("self._lich_bosses.values()", active)
        self.assertIn("config.MAX_ACTIVE_BOSSES", SERVER)

    def test_lich_uses_custom_boss_bar_and_six_synced_visual_shield_states(self):
        components = LICH_ENTITY["components"]
        self.assertNotIn("minecraft:boss", components)
        self.assertEqual(6, components["minecraft:variant"]["value"])
        for count in range(7):
            group = "tf_slice:shield_%d" % count
            event = "tf_slice:set_shield_%d" % count
            self.assertEqual(
                count,
                LICH_ENTITY["component_groups"][group][
                    "minecraft:variant"
                ]["value"],
            )
            self.assertIn(event, LICH_ENTITY["events"])

    def test_locked_source_entity_stats_and_projectile_physics_are_preserved(self):
        lich_components = LICH_ENTITY["components"]
        self.assertEqual(0.45, lich_components["minecraft:movement"]["value"])
        self.assertEqual(0, lich_components["minecraft:attack"]["damage"])
        melee = LICH_ENTITY["component_groups"]["tf_slice:melee_phase"]
        self.assertEqual(0, melee["minecraft:attack"]["damage"])
        self.assertEqual(
            0.75,
            melee["minecraft:behavior.melee_attack"]["speed_multiplier"],
        )
        self.assertTrue(
            melee["minecraft:behavior.melee_attack"]["track_target"]
        )
        self.assertIn("tf_slice:set_phase_melee", LICH_ENTITY["events"])
        self.assertIn("tf_slice:set_phase_ranged", LICH_ENTITY["events"])
        self.assertEqual(
            {"width": 1.1, "height": 2.1},
            lich_components["minecraft:collision_box"],
        )
        clone_components = LICH_CLONE_ENTITY["components"]
        self.assertEqual(0.45, clone_components["minecraft:movement"]["value"])
        self.assertEqual(
            {"width": 1.1, "height": 2.1},
            clone_components["minecraft:collision_box"],
        )
        minion_components = LICH_MINION_ENTITY["components"]
        self.assertEqual(0.23, minion_components["minecraft:movement"]["value"])
        self.assertEqual(3, minion_components["minecraft:attack"]["damage"])
        self.assertEqual(2, minion_components["minecraft:armor"]["value"])
        for entity in (LICH_BOLT_ENTITY, LICH_BOMB_ENTITY):
            components = entity["components"]
            self.assertEqual(
                {"width": 0.25, "height": 0.25},
                components["minecraft:collision_box"],
            )
            self.assertEqual(0.001, components["minecraft:projectile"]["gravity"])
            self.assertEqual(1.0, components["minecraft:projectile"]["uncertainty_base"])
            self.assertEqual(0.5, components["minecraft:projectile"]["power"])

    def test_lich_client_renders_shield_layers_and_server_equips_phase_weapon(self):
        self.assertEqual(
            "geometry.tf_slice.lich_shields",
            LICH_CLIENT["geometry"]["shields"],
        )
        self.assertIn(
            "controller.render.tf_slice.lich_shield_fill",
            LICH_CLIENT["render_controllers"],
        )
        self.assertIn(
            "controller.render.tf_slice.lich_shield_frame",
            LICH_CLIENT["render_controllers"],
        )
        self.assertIn('"tf_slice:twilight_scepter"', SERVER)
        self.assertIn('"minecraft:golden_sword"', SERVER)
        self.assertIn("def _sync_lich_presentation(", SERVER)
        self.assertIn('"tf_slice:set_shield_%d"', SERVER)

    def test_shadow_clone_reuses_the_locked_source_cast_pose(self):
        self.assertEqual(
            "geometry.tf_slice.lich_shadow_clone",
            LICH_CLONE_CLIENT["geometry"]["default"],
        )
        self.assertEqual(
            "animation.tf_slice.lich.source_pose",
            LICH_CLONE_CLIENT["animations"]["source_pose"],
        )
        clone_animate = LICH_CLONE_CLIENT["scripts"]["animate"]
        self.assertEqual(["move", "source_pose"], clone_animate[:2])
        helper_aliases = clone_animate[2:]
        self.assertTrue(helper_aliases)
        for entry in helper_aliases:
            self.assertIsInstance(entry, dict)
            self.assertEqual(1, len(entry))
            alias, weight = next(iter(entry.items()))
            self.assertTrue(alias.startswith("checker_compat_"))
            self.assertIn("math.clamp", weight)
            self.assertTrue(
                LICH_CLONE_CLIENT["animations"][alias].startswith(
                    "animation.tf_slice.compat.lich_"
                )
            )
        pose = LICH_ANIMATIONS["animation.tf_slice.lich.source_pose"]["bones"]
        self.assertEqual(
            {"head", "hat", "rightArm", "leftArm"},
            set(pose),
        )
        helper_weights = [
            weight
            for entry in clone_animate
            if isinstance(entry, dict)
            for alias, weight in entry.items()
            if alias.startswith("checker_compat_lich_source_pose_")
        ]
        self.assertTrue(any("-90" in value for value in helper_weights))
        self.assertTrue(any("-180" in value for value in helper_weights))


class LichLedgerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.factory = FakeFactory()
        self.service = SERVICE.StructureWorldgenService(
            self.factory, "level", 33027004
        )
        self.job = {
            "kind": "lich_tower",
            "entryId": "lich_tower",
            "state": "complete",
            "anchor": [100, 64, 200],
            "bounds": [100, 64, 200, 154, 144, 254],
            "bossKind": "lich",
            "bossSpawner": {
                "kind": "lich",
                "offset": [27, 67, 27],
            },
            "bossSpawned": True,
            "bossDefeated": False,
            "rewardClaimed": False,
        }
        self.service._ledger = {"128,228": self.job}
        self.service._rebuild_runtime_job_indexes()

    def test_reward_claim_is_atomic_and_idempotent(self):
        home = (127.5, 131.5, 227.5)
        self.assertTrue(self.service.mark_boss_defeated(home, "lich"))
        self.assertTrue(self.service.claim_boss_reward(home, "lich"))
        self.assertFalse(self.service.claim_boss_reward(home, "lich"))
        self.assertTrue(self.job["bossDefeated"])
        self.assertTrue(self.job["rewardClaimed"])

    def test_progress_protection_is_released_only_after_defeat(self):
        self.assertTrue(
            self.service.is_locked_lich_tower_position((127, 90, 227))
        )
        self.job["bossDefeated"] = True
        self.assertFalse(
            self.service.is_locked_lich_tower_position((127, 90, 227))
        )


if __name__ == "__main__":
    unittest.main()
