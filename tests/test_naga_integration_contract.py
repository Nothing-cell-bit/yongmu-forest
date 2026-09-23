# -*- coding: utf-8 -*-
import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEHAVIOR_ENTITY = (
    ROOT / "TwilightBossSliceB" / "entities" / "forest_wyrm.entity.json"
)
SERVER_SYSTEM = (
    ROOT
    / "TwilightBossSliceB"
    / "TwilightBossSlice"
    / "serverSystem.py"
)
CONFIG = (
    ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "config.py"
)
VALIDATOR = ROOT / "tools" / "validate_slice.py"
CLIENT_ENTITY = (
    ROOT / "TwilightBossSliceR" / "entity" / "forest_wyrm.entity.json"
)
SEGMENT_BEHAVIOR_ENTITY = (
    ROOT / "TwilightBossSliceB" / "entities" / "forest_wyrm_segment.entity.json"
)
SEGMENT_CLIENT_ENTITY = (
    ROOT / "TwilightBossSliceR" / "entity" / "forest_wyrm_segment.entity.json"
)
SEGMENT_GEOMETRY = (
    ROOT
    / "TwilightBossSliceR"
    / "models"
    / "entity"
    / "forest_wyrm_segment.geo.json"
)
HEAD_GEOMETRY = (
    ROOT
    / "TwilightBossSliceR"
    / "models"
    / "entity"
    / "forest_wyrm.geo.json"
)
ANIMATION_CONTROLLER = (
    ROOT
    / "TwilightBossSliceR"
    / "animation_controllers"
    / "forest_wyrm.controller.json"
)
ANIMATIONS = (
    ROOT
    / "TwilightBossSliceR"
    / "animations"
    / "forest_wyrm.animation.json"
)
RENDER_CONTROLLER = (
    ROOT
    / "TwilightBossSliceR"
    / "render_controllers"
    / "forest_wyrm.render.json"
)
TEXTURE_DIR = ROOT / "TwilightBossSliceR" / "textures" / "entity"
NAGA_COMPOST_PARTICLE = (
    ROOT / "TwilightBossSliceR" / "particles" / "naga_composter_single.json"
)
NAGA_DEATH_BURST_PARTICLE = (
    ROOT / "TwilightBossSliceR" / "particles" / "naga_death_burst_single.json"
)
ITEM_CATALOG = (
    ROOT
    / "TwilightBossSliceB"
    / "item_catalog"
    / "crafting_item_catalog.json"
)
NAGA_SCALE_ITEM = (
    ROOT / "TwilightBossSliceB" / "items" / "naga_scale.item.json"
)
NAGA_TROPHY_BLOCK = (
    ROOT / "TwilightBossSliceB" / "netease_blocks" / "naga_trophy.json"
)
NAGA_LOOT_TABLE = (
    ROOT
    / "TwilightBossSliceB"
    / "loot_tables"
    / "chests"
    / "naga_courtyard.json"
)
ITEM_TEXTURES = (
    ROOT / "TwilightBossSliceR" / "textures" / "item_texture.json"
)
TERRAIN_TEXTURES = (
    ROOT / "TwilightBossSliceR" / "textures" / "terrain_texture.json"
)
SOUNDS = ROOT / "TwilightBossSliceR" / "sounds.json"
SOUND_DEFINITIONS = (
    ROOT / "TwilightBossSliceR" / "sounds" / "sound_definitions.json"
)
CLIENT_SYSTEM = (
    ROOT
    / "TwilightBossSliceB"
    / "TwilightBossSlice"
    / "clientSystem.py"
)
ZH_CN = ROOT / "TwilightBossSliceR" / "texts" / "zh_CN.lang"
EN_US = ROOT / "TwilightBossSliceR" / "texts" / "en_US.lang"


class NagaBehaviorPackContractTests(unittest.TestCase):
    def setUp(self):
        self.entity = json.loads(BEHAVIOR_ENTITY.read_text(encoding="utf-8"))[
            "minecraft:entity"
        ]

    def test_head_does_not_sync_body_bones_as_custom_properties(self):
        properties = self.entity["description"].get("properties", {})
        self.assertNotIn("tf_slice:segments", properties)

    def test_generic_melee_ai_is_not_allowed_to_compete_with_script(self):
        components = self.entity["components"]
        self.assertNotIn("minecraft:behavior.melee_attack", components)
        self.assertEqual(5, components["minecraft:attack"]["damage"])
        self.assertEqual(200, components["minecraft:health"]["max"])

    def test_random_stroll_is_enabled_only_for_an_idle_naga(self):
        self.assertNotIn(
            "minecraft:behavior.random_stroll",
            self.entity["components"],
        )
        idle = self.entity["component_groups"]["tf_slice:idle_ai"]
        stroll = idle["minecraft:behavior.random_stroll"]
        self.assertEqual(8, stroll["priority"])
        self.assertEqual(1.0, stroll["speed_multiplier"])
        self.assertEqual(1, stroll["interval"])
        events = self.entity["events"]
        self.assertIn("tf_slice:enable_idle_ai", events)
        self.assertIn("tf_slice:disable_idle_ai", events)

    def test_head_ignores_suffocation_without_blanket_environmental_immunity(self):
        triggers = self.entity["components"]["minecraft:damage_sensor"][
            "triggers"
        ]
        self.assertEqual(
            [{"cause": "suffocation", "deals_damage": False}],
            triggers,
        )

    def test_head_cannot_be_pushed_back_into_obstacles(self):
        pushable = self.entity["components"]["minecraft:pushable"]
        self.assertFalse(pushable["is_pushable"])
        self.assertFalse(pushable["is_pushable_by_piston"])

    def test_head_collision_and_knockback_resistance_match_original(self):
        components = self.entity["components"]
        scale = components["minecraft:scale"]["value"]
        collision = components["minecraft:collision_box"]
        self.assertEqual(2.0, collision["width"] * scale)
        self.assertEqual(3.0, collision["height"] * scale)
        self.assertEqual(
            0.25,
            components["minecraft:knockback_resistance"]["value"],
        )

    def test_every_state_uses_builtin_variant_instead_of_custom_synced_data(self):
        events = self.entity["events"]
        for state in range(6):
            event = events["tf_slice:set_state_%d" % state]
            group = event["add"]["component_groups"][0]
            self.assertEqual("tf_slice:state_%d" % state, group)

    def test_body_is_a_real_independent_segment_entity(self):
        self.assertTrue(SEGMENT_BEHAVIOR_ENTITY.is_file())
        segment = json.loads(SEGMENT_BEHAVIOR_ENTITY.read_text(encoding="utf-8"))[
            "minecraft:entity"
        ]
        description = segment["description"]
        self.assertEqual("tf_slice:forest_wyrm_segment", description["identifier"])
        self.assertFalse(description["is_spawnable"])
        self.assertFalse(description["is_summonable"])
        self.assertEqual(
            ["tf_slice_naga_segment", "mob"],
            segment["components"]["minecraft:type_family"]["family"],
        )
        self.assertFalse(
            segment["components"]["minecraft:physics"]["has_collision"]
        )
        scale = segment["components"]["minecraft:scale"]["value"]
        collision = segment["components"]["minecraft:collision_box"]
        self.assertEqual(2.0, collision["width"] * scale)
        self.assertEqual(2.0, collision["height"] * scale)


class NagaServerAdapterContractTests(unittest.TestCase):
    def setUp(self):
        self.source = SERVER_SYSTEM.read_text(encoding="utf-8")

    def test_server_uses_the_pure_naga_brain(self):
        self.assertIn("import TwilightBossSlice.naga_logic as naga_logic", self.source)
        self.assertIn("naga_logic.NagaBrain(", self.source)

    def test_server_owns_motion_targeting_damage_and_shield_resolution(self):
        required_markers = (
            "ActuallyHurtServerEvent",
            "CreateAction(",
            "GetAttackTarget(",
            "CreateMoveTo(",
            "SetMoveSetting(",
            "CreateHurt(",
            ".Hurt(",
            "GetIsBlocking(",
            "SetItemDurability(",
        )
        for marker in required_markers:
            self.assertIn(marker, self.source)

    def test_navigation_advances_only_successful_combat_paths(self):
        handler = self.source[self.source.index("    def _drive_path_state") :]
        handler = handler[: handler.index("    def _can_destroy")]
        self.assertIn('state.get("navResult")', handler)
        self.assertIn("naga_logic.navigation_succeeded(", handler)
        self.assertIn("naga_logic.navigation_failed(", handler)
        self.assertLess(
            handler.index("naga_logic.navigation_succeeded("),
            handler.index("naga_logic.navigation_failed("),
        )
        self.assertIn("brain.complete_path_step(", handler)
        self.assertIn("_apply_head_slither(", handler)
        self.assertIn("if brain.state not in (", handler)
        charge_guard = handler[handler.index("if brain.state not in (") :]
        charge_guard = charge_guard[: charge_guard.index("self._look_along(")]
        self.assertIn("naga_logic.CHARGE", charge_guard)
        self.assertIn("naga_logic.STUNLESS_CHARGE", charge_guard)
        self.assertIn("stuckTicks", self.source)

    def test_scripted_facing_uses_rate_limited_shortest_yaw(self):
        handler = self.source[self.source.index("    def _look_along") :]
        handler = handler[: handler.index("    def _apply_head_slither")]
        self.assertIn("naga_logic.step_yaw(", handler)
        self.assertIn("rotComp = CF.CreateRot(entityId)", handler)
        self.assertIn("current = rotComp.GetRot()", handler)
        self.assertIn("rotComp.SetRot((0.0, yaw))", handler)

    def test_combat_waypoints_do_not_treat_internal_node_range_as_arrival(self):
        handler = self.source[self.source.index("    def _drive_path_state") :]
        handler = handler[: handler.index("    def _can_destroy")]
        self.assertIn("naga_logic.combat_waypoint_reached(", handler)
        self.assertNotIn("naga_logic.path_step_finished(", handler)

    def test_server_owns_no_target_idle_patrol_instead_of_native_random_stroll(self):
        self.assertIn("def _set_naga_idle_ai(", self.source)
        self.assertIn("def _drive_idle_patrol(", self.source)
        self.assertIn('"idleWaypointIndex": 0', self.source)
        self.assertIn('"idlePauseUntilTick": 0', self.source)
        drive = self.source[self.source.index("    def _drive_bosses") :]
        drive = drive[: drive.index("    def _is_blocking")]
        no_target = drive[drive.index("if not self._target_is_valid") :]
        no_target = no_target[: no_target.index("            continue")]
        self.assertIn('state, False', drive)
        self.assertIn("self._drive_idle_patrol(", no_target)
        self.assertNotIn('state, True', no_target)

    def test_first_combat_target_cancels_idle_patrol_before_path_state(self):
        drive = self.source[self.source.index("    def _drive_bosses") :]
        drive = drive[: drive.index("    def _is_blocking")]
        target_branch = drive[drive.index('state["combatStarted"] = True') - 260 :]
        target_branch = target_branch[: target_branch.index("targetPos =")]
        self.assertIn('if not state.get("combatStarted"):', target_branch)
        self.assertIn("self._stop_navigation(bossId, state)", target_branch)
        self.assertIn('state["idleWaypointIndex"] = 0', target_branch)
        self.assertIn('state["idlePauseUntilTick"] = 0', target_branch)
        self.assertLess(
            target_branch.index("self._stop_navigation(bossId, state)"),
            target_branch.index('state["combatStarted"] = True'),
        )

    def test_idle_patrol_reuses_the_complete_circle_speed_pipeline(self):
        config_source = CONFIG.read_text(encoding="utf-8")
        self.assertNotIn("NAGA_IDLE_NAVIGATION_SPEED", config_source)
        self.assertNotIn("NAGA_IDLE_MIN_FORWARD_SPEED", config_source)

        helper = self.source[self.source.index("    def _apply_head_slither") :]
        helper = helper[: helper.index("    def _drive_intimidate")]
        self.assertIn("naga_logic.slither_motion(", helper)
        self.assertIn("minimumForward", helper)

        idle = self.source[self.source.index("    def _drive_idle_patrol") :]
        idle = idle[: idle.index("    def _reset_encounter")]
        self.assertIn("naga_logic.scaled_navigation_speed(", idle)
        self.assertIn("config.NAVIGATION_SPEED", idle)
        self.assertIn('state["segments"]', idle)
        self.assertNotIn("minimumForward=", idle)

        combat = self.source[self.source.index("    def _drive_path_state") :]
        combat = combat[: combat.index("    def _can_destroy")]
        self.assertIn("naga_logic.scaled_navigation_speed(", combat)

    def test_intimidate_keeps_the_original_slow_forward_creep(self):
        self.assertIn("def _drive_intimidate(", self.source)
        drive = self.source[self.source.index("    def _drive_bosses") :]
        drive = drive[: drive.index("    def _is_blocking")]
        self.assertIn("self._drive_intimidate(", drive)

    def test_naga_home_and_health_are_persisted_without_refilling_on_reload(self):
        self.assertIn('NAGA_STATE_EXTRA_KEY = "tf_slice:naga_state_v1"', self.source)
        self.assertIn("def _load_naga_state(", self.source)
        self.assertIn("def _save_naga_state(", self.source)
        register = self.source[self.source.index("    def _register_boss") :]
        register = register[: register.index("    def _ensure_boss_home")]
        self.assertIn("self._load_naga_state(bossId)", register)
        self.assertNotIn("self._set_health_cap(bossId", register)

    def test_losing_a_target_resets_ai_without_restoring_health(self):
        reset = self.source[self.source.index("    def _reset_encounter") :]
        reset = reset[: reset.index("    def _on_state_changed")]
        self.assertIn('state["brain"] = naga_logic.NagaBrain(', reset)
        self.assertNotIn("_set_health", reset)
        self.assertNotIn('state["maxHealth"]', reset)

    def test_targeting_excludes_dead_creative_and_spectator_players(self):
        handler = self.source[self.source.index("    def _find_nearest_player") :]
        handler = handler[: handler.index("    def _select_attack_target")]
        self.assertIn("GetPlayerGameType(playerId)", handler)
        self.assertIn("IsEntityAlive(", handler)
        self.assertIn("naga_logic.nearest_target(", handler)

    def test_naga_teleports_home_when_it_falls_below_the_courtyard(self):
        handler = self.source[
            self.source.index("    def _recover_boss_below_home") :
        ]
        handler = handler[: handler.index("    def _drive_home")]
        self.assertIn('bossPos[1] < state["home"][1] - 5.0', handler)
        self.assertIn("CF.CreatePos(bossId).SetPos(state[\"home\"])", handler)
        drive = self.source[self.source.index("    def _drive_bosses") :]
        drive = drive[: drive.index("    def _is_blocking")]
        self.assertIn("self._recover_boss_below_home(", drive)

    def test_stuck_detection_tracks_waypoint_progress_and_clears_forward(self):
        handler = self.source[self.source.index("    def _drive_path_state") :]
        handler = handler[: handler.index("    def _can_destroy")]
        self.assertIn("naga_logic.update_navigation_progress(", handler)
        self.assertIn('"waypointBestDistance"', self.source)
        self.assertNotIn('state.get("lastBossPos")', handler)

        recovery = handler[
            handler.index('and state["stuckTicks"] >=') :
        ]
        recovery = recovery[: recovery.index("        if waypoint is None:")]
        self.assertIn(
            "direction = _normalized_xz(bossPos, waypoint)",
            recovery,
        )
        self.assertNotIn(
            "direction = _normalized_xz(bossPos, targetPos)",
            recovery,
        )

    def test_navigation_failure_keeps_the_waypoint_until_recovery_runs(self):
        handler = self.source[self.source.index("    def _drive_path_state") :]
        handler = handler[: handler.index("    def _can_destroy")]
        failure = handler[handler.index("if naga_logic.navigation_failed(") :]
        failure = failure[: failure.index("        if waypoint is not None:")]

        self.assertNotIn('state["waypoint"] = None', failure)
        self.assertNotIn('state["waypointBestDistance"] = None', failure)
        self.assertIn('state.get("stuckTicks", 0)', failure)

    def test_every_active_naga_periodically_clears_its_head_volume(self):
        handler = self.source[self.source.index("    def _drive_bosses") :]
        handler = handler[: handler.index("    def _is_blocking")]
        before_target_selection = handler[: handler.index(
            "self._select_attack_target("
        )]

        self.assertIn("self._clear_head_volume(", before_target_selection)
        self.assertIn("config.BLOCK_CLEAR_INTERVAL_TICKS", before_target_selection)
        self.assertIn("naga_logic.head_clear_positions(", self.source)

    def test_spawned_or_reloaded_naga_is_periodically_discovered(self):
        self.assertIn("GetEntitiesAround(", self.source)
        self.assertIn('"tf_slice_boss"', self.source)
        self.assertIn("def _discover_bosses(", self.source)

    def test_segment_loss_destroys_real_entities_and_broadcasts_world_bursts(self):
        client_source = (
            ROOT
            / "TwilightBossSliceB"
            / "TwilightBossSlice"
            / "clientSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn('SEGMENT_IDENTIFIER = "tf_slice:forest_wyrm_segment"', self.source)
        self.assertIn("CreateEngineEntityByTypeStr(", self.source)
        self.assertIn('"segmentIds"', self.source)
        self.assertIn("segment_destruction_schedule(", self.source)
        self.assertIn("self.DestroyEntity(segmentId)", self.source)
        self.assertIn('"NagaSegmentBurst"', self.source)
        self.assertIn('"minecraft:large_explosion"', client_source)
        self.assertIn('"positions"', self.source)
        self.assertNotIn('"tf_slice:forest_wyrm_segment"', client_source)

    def test_health_change_event_immediately_recomputes_visible_segment_count(self):
        handler = self.source[self.source.index("    def OnHealthChangeBefore") :]
        handler = handler[: handler.index("    def OnActuallyHurtServerEvent")]
        self.assertIn(
            "self._apply_boss_health_state(entityId, state, toValue)",
            handler,
        )
        self.assertIn("def _apply_boss_health_state(", self.source)

    def test_failed_segment_removal_keeps_ownership_and_is_retried(self):
        handler = self.source[self.source.index("    def _destroy_segment") :]
        handler = handler[: handler.index("    def _destroy_all_segments")]
        self.assertIn("result = self.DestroyEntity(segmentId)", handler)
        self.assertIn("if result is False:", handler)
        self.assertLess(
            handler.index("if result is False:"),
            handler.index("self._segment_owners.pop(segmentId, None)"),
        )
        update = self.source[self.source.index("    def _update_boss_segments") :]
        update = update[: update.index("    def _remove_excess_boss")]
        self.assertIn("config.SEGMENT_REMOVAL_RETRY_TICKS", update)

    def test_final_death_forces_all_segments_out_before_the_head(self):
        finalizer = self.source[self.source.index("    def _finalize_naga_death") :]
        finalizer = finalizer[: finalizer.index("    def _update_naga_death")]
        self.assertIn("self._destroy_all_segments(state)", finalizer)
        self.assertLess(
            finalizer.index("self._destroy_all_segments(state)"),
            finalizer.index("self.DestroyEntity(bossId)"),
        )
        cleanup = self.source[self.source.index("    def _destroy_all_segments") :]
        cleanup = cleanup[: cleanup.index("    def _mark_boss_dead")]
        self.assertIn("if not removed:", cleanup)
        self.assertIn("config.SEGMENT_REMOVAL_RETRY_TICKS", cleanup)
        self.assertNotIn('state.get("segmentBurstTicks", {}).clear()', cleanup)

    def test_short_body_holds_formation_while_the_head_turns_in_place(self):
        self.assertIn('"lastSegmentHeadPos": None', self.source)
        handler = self.source[self.source.index("    def _ensure_segment_chain") :]
        handler = handler[: handler.index("    def _update_boss_segments")]
        self.assertIn("naga_logic.short_chain_should_hold(", handler)

    def test_segments_damage_colliding_living_entities_including_animals(self):
        self.assertIn("def _resolve_segment_collisions(", self.source)
        handler = self.source[
            self.source.index("    def _resolve_segment_collisions") :
        ]
        handler = handler[: handler.index("    def _resolve_contact")]
        self.assertIn("GetEntitiesAround(", handler)
        self.assertIn('"value": "animal"', handler)
        self.assertIn("naga_logic.segment_collision_damage(", handler)
        self.assertIn("naga_logic.collision_boxes_overlap(", handler)
        self.assertIn(
            "excluded.update(self._segment_owners.keys())",
            handler,
        )
        self.assertNotIn("excluded.add(targetId)", handler)
        self.assertIn("self._resolve_segment_collisions(", self.source)

    def test_original_naga_combat_and_terrain_cadence_runs_each_tick(self):
        config_source = CONFIG.read_text(encoding="utf-8")
        self.assertIn("CONTACT_COOLDOWN_TICKS = 20", config_source)
        self.assertIn("AI_INTERVAL_TICKS = 1", config_source)
        self.assertIn("BLOCK_CLEAR_INTERVAL_TICKS = 1", config_source)
        self.assertIn("MAX_BLOCKS_PER_CLEAR = 125", config_source)
        self.assertIn("NAVIGATION_CHARGE_SPEED = 1.5", config_source)
        validator_source = VALIDATOR.read_text(encoding="utf-8")
        self.assertIn("ai_interval >= 1", validator_source)

    def test_state_is_pushed_but_segments_are_not_custom_synced_properties(self):
        self.assertIn('"tf_slice:set_state_%d"', self.source)
        self.assertNotIn('"tf_slice:set_segments_%d"', self.source)

    def test_targeting_unions_known_players_and_requires_target_inside_home(self):
        self.assertIn("players = set(self._known_players)", self.source)
        self.assertIn(
            "naga_logic.inside_home(targetPos, state[\"home\"])",
            self.source,
        )

    def test_server_moves_each_segment_and_lifts_only_when_in_wall(self):
        self.assertIn("naga_logic.segment_spawn_position(", self.source)
        self.assertIn("naga_logic.follow_segment(", self.source)
        self.assertNotIn("def _segment_is_on_ground(", self.source)
        self.assertNotIn('"segmentOnGround"', self.source)
        self.assertIn("def _segment_is_in_wall(", self.source)
        self.assertIn("on_ground=self._segment_is_in_wall(", self.source)
        self.assertIn("CF.CreatePos(segmentId).SetPos(", self.source)
        self.assertIn("CF.CreateRot(segmentId).SetRot(", self.source)

    def test_shield_blocking_uses_the_player_component(self):
        handler = self.source[self.source.index("    def _is_blocking") :]
        handler = handler[: handler.index("    def _shield_slot")]
        self.assertIn(
            "CF.CreatePlayer(playerId).GetIsBlocking()",
            handler,
        )
        self.assertNotIn("CF.CreateItem(playerId).GetIsBlocking()", handler)
        slot_handler = self.source[self.source.index("    def _shield_slot") :]
        slot_handler = slot_handler[: slot_handler.index("    def _damage_shield")]
        self.assertIn("itemPos.OFFHAND", slot_handler)

    def test_spawn_position_becomes_home_without_entry_position_fallback(self):
        self.assertIn(
            "def _register_boss(self, bossId, dimensionId=None, home=None):",
            self.source,
        )
        self.assertIn("def _ensure_boss_home(", self.source)
        self.assertIn(
            "bossId, config.DIMENSION_ID, spawnPos",
            self.source,
        )
        self.assertNotIn("or config.ENTRY_POS", self.source)

    def test_boss_callbacks_reconcile_engine_id_types_and_rearm_missing_bosses(self):
        self.assertIn(
            "entity_registry_logic.matching_entity_key(",
            self.source,
        )
        self.assertIn("def _boss_state(self, entityId):", self.source)
        self.assertIn("mark_naga_missing(", self.source)
        self.assertIn('"missingActorTicks"', self.source)

    def test_loaded_boss_registry_entries_require_a_live_position(self):
        handler = self.source[
            self.source.index("    def _forget_missing_bosses") :
        ]
        handler = handler[: handler.index("    def _discover_bosses")]

        self.assertIn("loadedBossKey", handler)
        self.assertIn(
            "self._get_foot_pos(loadedBossKey) is not None",
            handler,
        )

    def test_server_falls_back_to_nearest_online_player(self):
        self.assertIn("serverApi.GetPlayerList()", self.source)
        self.assertIn("naga_logic.nearest_target(", self.source)
        self.assertIn("SetAttackTarget(", self.source)
        self.assertIn("def _select_attack_target(", self.source)

    def test_spawn_egg_obeys_the_mobile_boss_limit(self):
        self.assertIn(
            "if len(self._bosses) >= config.MAX_ACTIVE_BOSSES:",
            self.source,
        )
        self.assertIn("def _remove_excess_boss(", self.source)
        self.assertIn("self._remove_excess_boss(entityId)", self.source)

    def test_spawn_is_rejected_before_add_when_a_courtyard_already_has_a_naga(self):
        self.assertIn('"ServerSpawnMobEvent"', self.source)
        self.assertIn("def OnServerSpawnMob(", self.source)
        handler = self.source[self.source.index("    def OnServerSpawnMob") :]
        handler = handler[: handler.index("    def OnAddEntity")]
        self.assertIn("_home_conflicts(", handler)
        self.assertIn("naga_logic.courtyards_overlap(", self.source)
        self.assertIn('args["cancel"] = True', handler)

    def test_recovery_scans_loaded_actors_and_removes_orphan_segments(self):
        self.assertIn("serverApi.GetEngineActor()", self.source)
        self.assertIn("def _cleanup_orphan_segments(", self.source)
        self.assertIn("SEGMENT_IDENTIFIER", self.source)
        self.assertIn("self.DestroyEntity(entityId)", self.source)

    def test_live_difficulty_and_mob_griefing_drive_combat(self):
        self.assertIn("GetGameDiffculty()", self.source)
        self.assertIn("GetGameRulesInfoServer()", self.source)
        self.assertIn("naga_logic.head_damage_for_difficulty(", self.source)
        self.assertIn("naga_logic.segment_collision_damage(", self.source)
        self.assertIn("naga_logic.scaled_navigation_speed(", self.source)

    def test_collision_block_breaking_is_enabled_and_filtered_by_state(self):
        self.assertIn('"OnMobHitBlockServerEvent"', self.source)
        self.assertIn("OpenMobHitBlockDetection(", self.source)
        self.assertIn("def OnMobHitBlock(", self.source)
        self.assertIn("naga_logic.should_destroy_block(", self.source)
        destroy = self.source[self.source.index("    def _destroy_block") :]
        destroy = destroy[: destroy.index("    def _crumble_below_target")]
        self.assertIn('oldBlockHandling = 0 if "leaves" in', destroy)
        self.assertIn("targetedCrumble", destroy)

    def test_damage_immunity_uses_source_position_and_explosion_cause(self):
        self.assertIn('"HealthChangeBeforeServerEvent"', self.source)
        self.assertIn("def OnHealthChangeBefore(", self.source)
        handler = self.source[self.source.index("    def OnHealthChangeBefore") :]
        handler = handler[: handler.index("    def OnActuallyHurtServerEvent")]
        self.assertIn("naga_logic.naga_damage_is_blocked(", handler)
        self.assertIn("_damage_entity_inside_home(", handler)
        self.assertIn("segmentOwner = self._segment_owners.get(entityId)", handler)
        self.assertIn('args["cancel"] = True', handler)

    def test_death_delegates_to_staged_idempotent_finalizer(self):
        handler = self.source[self.source.index("    def OnMobDie") :]
        handler = handler[: handler.index("    def OnHealthChangeBefore")]
        self.assertIn("_finalize_naga_death(", handler)
        finalizer = self.source[
            self.source.index("    def _finalize_naga_death") :
        ]
        finalizer = finalizer[: finalizer.index("    def _update_naga_death")]
        self.assertIn("_place_naga_loot_chest(", finalizer)
        self.assertIn("_award_naga_progress(", finalizer)
        self.assertIn("SetChestLootTable(", self.source)
        self.assertIn("tf_naga_defeated", self.source)


class NagaResourcePackContractTests(unittest.TestCase):
    def test_all_original_head_states_are_declared_and_present(self):
        client = json.loads(CLIENT_ENTITY.read_text(encoding="utf-8"))
        textures = client["minecraft:client_entity"]["description"]["textures"]
        self.assertIn("head", textures)
        self.assertIn("head_charging", textures)
        self.assertIn("head_dazed", textures)
        self.assertTrue((TEXTURE_DIR / "nagahead.png").is_file())
        self.assertTrue((TEXTURE_DIR / "nagahead_charging.png").is_file())
        self.assertTrue((TEXTURE_DIR / "nagahead_dazed.png").is_file())

    def test_head_state_rendering_uses_builtin_variant(self):
        animation_source = ANIMATION_CONTROLLER.read_text(encoding="utf-8")
        render_source = RENDER_CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("query.variant", animation_source)
        self.assertIn("query.variant", render_source)
        self.assertNotIn("tf_slice:segments", render_source)

    def test_daze_uses_the_locked_base_head_and_inflated_eyelid_layer(self):
        client = json.loads(CLIENT_ENTITY.read_text(encoding="utf-8"))[
            "minecraft:client_entity"
        ]["description"]
        controllers = json.loads(RENDER_CONTROLLER.read_text(encoding="utf-8"))[
            "render_controllers"
        ]
        base = controllers["controller.render.tf_slice.forest_wyrm_head"]
        dazed = controllers["controller.render.tf_slice.forest_wyrm_head_dazed"]
        base_visibility = base["part_visibility"][0]["*"]
        dazed_visibility = dazed["part_visibility"][0]["*"]
        self.assertEqual(
            "textures/entity/nagahead_dazed",
            client["textures"]["head_dazed"],
        )
        self.assertEqual(
            "geometry.tf_slice.forest_wyrm_eyelids",
            client["geometry"]["eyelids"],
        )
        self.assertIn("query.variant == 5", base_visibility)
        self.assertEqual("Geometry.eyelids", dazed["geometry"])
        self.assertEqual("Texture.head_dazed", dazed["textures"][0])
        self.assertEqual("query.variant == 5", dazed_visibility)

    def test_eyelid_geometry_uses_two_small_depth_offset_cubes(self):
        geometries = json.loads(HEAD_GEOMETRY.read_text(encoding="utf-8"))[
            "minecraft:geometry"
        ]
        head = next(
            geometry
            for geometry in geometries
            if geometry["description"]["identifier"]
            == "geometry.tf_slice.forest_wyrm"
        )
        eyelids = next(
            geometry
            for geometry in geometries
            if geometry["description"]["identifier"]
            == "geometry.tf_slice.forest_wyrm_eyelids"
        )
        self.assertEqual(head["bones"][0]["pivot"], eyelids["bones"][0]["pivot"])
        cubes = [cube for bone in eyelids["bones"] for cube in bone.get("cubes", [])]
        self.assertEqual(2, len(cubes))
        for cube in cubes:
            self.assertGreater(float(cube["inflate"]), 0.0)
            self.assertLessEqual(float(cube["inflate"]), 0.05)

    def test_head_geometry_preserves_ground_clearance_over_segments(self):
        head_geometries = json.loads(HEAD_GEOMETRY.read_text(encoding="utf-8"))[
            "minecraft:geometry"
        ]
        head = next(
            geometry
            for geometry in head_geometries
            if geometry["description"]["identifier"]
            == "geometry.tf_slice.forest_wyrm"
        )
        head_bone = head["bones"][0]
        head_cube = head_bone["cubes"][0]

        segment = json.loads(SEGMENT_GEOMETRY.read_text(encoding="utf-8"))[
            "minecraft:geometry"
        ][0]
        segment_bone = segment["bones"][0]
        segment_cube = segment_bone["cubes"][0]

        head_scale = json.loads(BEHAVIOR_ENTITY.read_text(encoding="utf-8"))[
            "minecraft:entity"
        ]["components"]["minecraft:scale"]["value"]
        segment_scale = json.loads(
            SEGMENT_BEHAVIOR_ENTITY.read_text(encoding="utf-8")
        )["minecraft:entity"]["components"]["minecraft:scale"]["value"]
        target_head_bottom = head_cube["origin"][1] / 16.0 * head_scale
        target_head_top = (
            (head_cube["origin"][1] + head_cube["size"][1])
            / 16.0
            * head_scale
        )
        target_segment_bottom = (
            segment_cube["origin"][1] / 16.0 * segment_scale
        )
        target_segment_top = (
            (segment_cube["origin"][1] + segment_cube["size"][1])
            / 16.0
            * segment_scale
        )

        self.assertGreaterEqual(target_head_bottom, target_segment_bottom)
        self.assertGreater(target_head_top, target_segment_top)
        self.assertEqual([0, 9, 0], head_bone["pivot"])

    def test_stunless_charge_has_a_distinct_red_render_pass(self):
        client = json.loads(CLIENT_ENTITY.read_text(encoding="utf-8"))[
            "minecraft:client_entity"
        ]["description"]
        controllers = json.loads(RENDER_CONTROLLER.read_text(encoding="utf-8"))[
            "render_controllers"
        ]
        name = "controller.render.tf_slice.forest_wyrm_head_stunless"
        self.assertIn(name, client["render_controllers"])
        stunless = controllers[name]
        self.assertEqual(
            "query.variant == 4",
            stunless["part_visibility"][0]["*"],
        )
        self.assertGreater(stunless["color"]["r"], stunless["color"]["g"])
        self.assertGreater(stunless["color"]["r"], stunless["color"]["b"])

    def test_daze_expression_keeps_the_head_bone_at_rest(self):
        animations = json.loads(ANIMATIONS.read_text(encoding="utf-8"))[
            "animations"
        ]
        daze = animations["animation.tf_slice.forest_wyrm.daze"]
        position = daze["bones"]["head"]["position"]
        self.assertEqual([0, 0, 0], position)
        self.assertEqual([0, 0, 0], daze["bones"]["head"]["rotation"])

    def test_intimidate_uses_yaw_only_without_head_sink_or_side_roll(self):
        animations = json.loads(ANIMATIONS.read_text(encoding="utf-8"))[
            "animations"
        ]
        head = animations[
            "animation.tf_slice.forest_wyrm.intimidate"
        ]["bones"]["head"]
        self.assertEqual([0, 0, 0], head["position"])
        rotation = head["rotation"]
        self.assertEqual(0, rotation[0])
        self.assertEqual(
            "math.sin(query.anim_time * 900.0) * 5.0",
            rotation[1],
        )
        self.assertEqual(0, rotation[2])

    def test_circle_uses_entity_motion_without_source_invented_head_wobble(self):
        animations = json.loads(ANIMATIONS.read_text(encoding="utf-8"))[
            "animations"
        ]
        circle = animations["animation.tf_slice.forest_wyrm.circle"]
        head = circle["bones"]["head"]
        self.assertEqual([0, 0, 0], head["position"])
        self.assertEqual([0, 0, 0], head["rotation"])
        controller = json.loads(
            ANIMATION_CONTROLLER.read_text(encoding="utf-8")
        )["animation_controllers"][
            "controller.animation.tf_slice.forest_wyrm"
        ]
        self.assertEqual(["circle"], controller["states"]["circle"]["animations"])

    def test_charge_animation_uses_texture_and_motion_without_head_wobble(self):
        animations = json.loads(ANIMATIONS.read_text(encoding="utf-8"))[
            "animations"
        ]
        charge = animations["animation.tf_slice.forest_wyrm.charge"]
        self.assertEqual([0, 0, 0], charge["bones"]["head"]["rotation"])

    def test_client_keeps_stunless_particles_without_sustained_daze_spam(self):
        source = CLIENT_SYSTEM.read_text(encoding="utf-8")
        sync = source[source.index("    def OnBossSync") :]
        sync = sync[: sync.index("    def OnPerfSync")]
        self.assertIn('"state": int(boss.get("state", 0))', sync)
        self.assertIn("def _update_naga_state_effects(", source)
        naga_effects = source[
            source.index("    def _update_naga_state_effects") :
        ]
        naga_effects = naga_effects[
            : naga_effects.index("    def _update_lich_state_effects")
        ]
        self.assertIn('"minecraft:villager_angry"', naga_effects)
        self.assertNotIn('"minecraft:critical_hit_emitter"', naga_effects)
        self.assertIn(
            "if state == NAGA_DAZE_STATE:\n                continue",
            naga_effects,
        )
        self.assertNotIn("for _index in range(5)", naga_effects)
        update = source[source.index("    def OnScriptTickClient") :]
        update = update[: update.index("    def _is_local_dimension_event")]
        self.assertIn("self._update_naga_state_effects()", update)

    def test_shield_daze_uses_only_source_recoil_without_player_setpos(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        handler = source[source.index("    def _resolve_contact") :]
        handler = handler[: handler.index("    def _change_dimension")]
        shield = handler[handler.index('result["kind"] == "shield_daze"') :]
        shield = shield[: shield.index("        elif result")]
        self.assertIn("self._stop_navigation(bossId, state)", shield)
        self.assertLess(
            shield.index("self._stop_navigation(bossId, state)"),
            shield.index("self._shield_charge_recoil("),
        )
        self.assertIn('state["dazeRecoilStopTick"]', shield)
        self.assertNotIn("self._separate_naga_shield_contact(", shield)
        drive = source[source.index("    def _drive_bosses") :]
        drive = drive[: drive.index("    def _is_blocking")]
        daze = drive[drive.index("if brain.state == naga_logic.DAZE") :]
        daze = daze[: daze.index("                else:")]
        self.assertNotIn("self._separate_naga_shield_contact(", daze)
        self.assertNotIn("self._naga_target_overlaps_body(", daze)

    def test_shield_recoil_uses_the_server_player_motion_api(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        helper = source[source.index("    def _set_player_motion") :]
        helper = helper[: helper.index("    def _face_position")]
        self.assertIn("CF.CreateActorMotion(playerId)", helper)
        self.assertIn("motionComp.SetPlayerMotion(", helper)
        self.assertNotIn("motionComp.SetMotion(", helper)

        recoil = source[source.index("    def _shield_charge_recoil") :]
        recoil = recoil[: recoil.index("    def _naga_melee_knockback")]
        self.assertIn(
            "playerApplied = self._set_player_motion(playerId, playerMotion)",
            recoil,
        )
        self.assertIn(
            "nagaApplied = self._set_full_motion(bossId, nagaMotion)",
            recoil,
        )
        self.assertNotIn("self._set_full_motion(playerId, playerMotion)", recoil)
        self.assertIn("playerApplied is not False", recoil)
        self.assertIn("nagaApplied is not False", recoil)

    def test_stop_navigation_interrupts_the_engine_moveto_path(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        cancel = source[source.index("    def _cancel_move_to_path") :]
        cancel = cancel[: cancel.index("    def _stop_navigation")]
        self.assertIn("self._get_foot_pos(entityId)", cancel)
        self.assertIn("CF.CreateMoveTo(entityId)", cancel)
        self.assertIn("moveComp.SetMoveSetting(", cancel)
        self.assertIn("config.NAVIGATION_CANCEL_MAX_ITERATIONS", cancel)

        stop = source[source.index("    def _stop_navigation") :]
        stop = stop[: stop.index("    def _look_along")]
        self.assertIn("self._cancel_move_to_path(entityId)", stop)
        self.assertIn("self._set_motion(entityId, 0.0, 0.0)", stop)
        self.assertLess(
            stop.index("self._cancel_move_to_path(entityId)"),
            stop.index("self._set_motion(entityId, 0.0, 0.0)"),
        )
        config_source = CONFIG.read_text(encoding="utf-8")
        self.assertIn("NAVIGATION_CANCEL_MAX_ITERATIONS = 1", config_source)

    def test_shield_daze_moves_the_existing_body_with_the_short_recoil(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        handler = source[source.index("    def _resolve_contact") :]
        handler = handler[: handler.index("    def _change_dimension")]
        shield = handler[handler.index('result["kind"] == "shield_daze"') :]
        shield = shield[: shield.index("        elif result")]
        self.assertIn("self._capture_naga_segment_pose(", shield)
        self.assertIn("naga_logic.DAZE_RECOIL_TICKS", shield)
        self.assertLess(
            shield.index("self._stop_navigation(bossId, state)"),
            shield.index("self._capture_naga_segment_pose("),
        )
        self.assertLess(
            shield.index("self._capture_naga_segment_pose("),
            shield.index("self._shield_charge_recoil("),
        )

    def test_daze_stops_horizontally_but_preserves_vertical_gravity(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        drive = source[source.index("    def _drive_bosses") :]
        drive = drive[: drive.index("    def _is_blocking")]
        self.assertIn("if brain.state == naga_logic.DAZE", drive)
        daze = drive[drive.index("if brain.state == naga_logic.DAZE") :]
        daze = daze[: daze.index("                else:")]
        self.assertIn("naga_logic.daze_recoil_finished(", daze)
        self.assertIn("self._stop_navigation(bossId, state)", daze)
        self.assertIn("self._set_motion(", daze)
        self.assertIn("bossId, 0.0, 0.0", daze)
        self.assertNotIn("self._set_full_motion(", daze)
        self.assertNotIn("self._look_along(", daze)

    def test_daze_hard_stop_lets_the_body_settle_behind_the_head(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        held = source[source.index("    def _naga_segment_pose_is_held") :]
        held = held[: held.index("    def _clear_naga_segment_pose")]
        self.assertNotIn("brain.state == naga_logic.DAZE", held)
        self.assertIn("segmentPoseUntilTick", held)

    def test_head_contact_ends_charge_navigation_before_overshoot(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        handler = source[source.index("    def _resolve_contact") :]
        handler = handler[: handler.index("    def _change_dimension")]
        self.assertIn("previous in (", handler)
        self.assertIn("naga_logic.CHARGE", handler)
        self.assertIn("naga_logic.STUNLESS_CHARGE", handler)
        self.assertIn("self._stop_navigation(bossId, state)", handler)
        self.assertIn("self._capture_naga_segment_pose(", handler)
        self.assertNotIn("self._anchor_naga_segments(", handler)

    def test_charge_resolution_requires_actual_head_aabb_contact(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        handler = source[source.index("    def _resolve_contact") :]
        handler = handler[: handler.index("    def _change_dimension")]
        self.assertIn("naga_logic.collision_boxes_overlap(", handler)
        self.assertIn("if charging and not headContact:", handler)
        self.assertLess(
            handler.index("if charging and not headContact:"),
            handler.index("brain.resolve_contact("),
        )

    def test_daze_hard_stop_does_not_snapshot_a_body_wall(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        drive = source[source.index("    def _drive_bosses") :]
        drive = drive[: drive.index("    def _is_blocking")]
        daze = drive[drive.index("if brain.state == naga_logic.DAZE") :]
        daze = daze[: daze.index("                else:")]
        self.assertIn("self._set_motion(", daze)
        self.assertNotIn("self._set_full_motion(", daze)
        self.assertNotIn("self._capture_naga_segment_pose(", daze)

    def test_daze_has_no_delayed_player_teleport(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        drive = source[source.index("    def _drive_bosses") :]
        drive = drive[: drive.index("    def _is_blocking")]
        daze = drive[drive.index("if brain.state == naga_logic.DAZE") :]
        daze = daze[: daze.index("                else:")]
        self.assertNotIn("self._naga_target_overlaps_body(", daze)
        self.assertNotIn("self._separate_naga_shield_contact(", daze)
        self.assertIn("self._set_motion(", daze)
        self.assertNotIn("self._capture_naga_segment_pose(", daze)

    def test_daze_has_no_sustained_particle_emitter(self):
        source = CLIENT_SYSTEM.read_text(encoding="utf-8")
        effects = source[source.index("    def _update_naga_state_effects") :]
        effects = effects[: effects.index("    def _update_lich_state_effects")]
        self.assertIn(
            "if state == NAGA_DAZE_STATE:\n                continue",
            effects,
        )
        self.assertNotIn("self._naga_effect_tick % 6", effects)

    def test_death_trail_particles_are_single_and_short_lived(self):
        source = CLIENT_SYSTEM.read_text(encoding="utf-8")
        handler = source[source.index("    def OnNagaDeathEffect") :]
        handler = handler[: handler.index("    def OnNagaCombatEffect")]
        self.assertIn('"tf_slice:naga_composter_single"', handler)
        self.assertIn('"tf_slice:naga_death_burst_single"', handler)
        self.assertNotIn('"minecraft:crop_growth_emitter"', handler)
        for path, identifier in (
            (NAGA_COMPOST_PARTICLE, "tf_slice:naga_composter_single"),
            (NAGA_DEATH_BURST_PARTICLE, "tf_slice:naga_death_burst_single"),
        ):
            particle = json.loads(path.read_text(encoding="utf-8"))[
                "particle_effect"
            ]
            self.assertEqual(identifier, particle["description"]["identifier"])
            components = particle["components"]
            self.assertEqual(
                1,
                components["minecraft:emitter_rate_instant"]["num_particles"],
            )
            self.assertLessEqual(
                float(
                    components["minecraft:particle_lifetime_expression"][
                        "max_lifetime"
                    ]
                ),
                0.4,
            )

    def test_body_segment_has_original_core_and_copper_ring_geometry(self):
        self.assertTrue(SEGMENT_CLIENT_ENTITY.is_file())
        segment_client = json.loads(
            SEGMENT_CLIENT_ENTITY.read_text(encoding="utf-8")
        )["minecraft:client_entity"]["description"]
        self.assertEqual(
            "textures/entity/nagasegment",
            segment_client["textures"]["default"],
        )
        geometry = json.loads(
            SEGMENT_GEOMETRY.read_text(encoding="utf-8")
        )
        bones = geometry["minecraft:geometry"][0]["bones"]
        cubes = [cube for bone in bones for cube in bone.get("cubes", [])]
        self.assertGreaterEqual(len(cubes), 5)
        self.assertLessEqual(max(cube['size'][0] for cube in cubes), 16)

    def test_visual_diameter_matches_original_two_block_segment_spacing(self):
        head = json.loads(BEHAVIOR_ENTITY.read_text(encoding="utf-8"))[
            "minecraft:entity"
        ]
        segment = json.loads(
            SEGMENT_BEHAVIOR_ENTITY.read_text(encoding="utf-8")
        )["minecraft:entity"]
        self.assertEqual(2.0, head["components"]["minecraft:scale"]["value"])
        self.assertEqual(
            2.0,
            segment["components"]["minecraft:scale"]["value"],
        )

    def test_segment_geometry_uses_the_new_texture_canvas_dimensions(self):
        geometry = json.loads(SEGMENT_GEOMETRY.read_text(encoding="utf-8"))
        description = geometry["minecraft:geometry"][0]["description"]
        texture_path = TEXTURE_DIR / "nagasegment.png"
        with texture_path.open("rb") as texture:
            self.assertEqual(b"\x89PNG\r\n\x1a\n", texture.read(8))
            chunk_length = struct.unpack(">I", texture.read(4))[0]
            self.assertEqual(b"IHDR", texture.read(4))
            width, height = struct.unpack(">II", texture.read(8))
        self.assertGreaterEqual(chunk_length, 13)
        self.assertEqual(128, width)
        self.assertEqual(128, height)
        self.assertEqual(width, description["texture_width"])
        self.assertEqual(height, description["texture_height"])

    def test_naga_spawn_egg_is_declared_and_named(self):
        client = json.loads(CLIENT_ENTITY.read_text(encoding="utf-8"))
        spawn_egg = client["minecraft:client_entity"]["description"]["spawn_egg"]
        self.assertEqual("#17152C", spawn_egg["base_color"])
        self.assertEqual("#D6762D", spawn_egg["overlay_color"])
        behavior = json.loads(BEHAVIOR_ENTITY.read_text(encoding="utf-8"))
        description = behavior["minecraft:entity"]["description"]
        self.assertTrue(description["is_spawnable"])
        self.assertTrue(description["is_summonable"])
        for language in (ZH_CN, EN_US):
            self.assertIn(
                "item.spawn_egg.entity.tf_slice:forest_wyrm.name=",
                language.read_text(encoding="utf-8"),
            )

    def test_twilight_items_share_category_safe_creative_inventory_groups(self):
        catalog = json.loads(ITEM_CATALOG.read_text(encoding="utf-8"))
        categories = catalog["minecraft:crafting_items_catalog"]["categories"]
        self.assertEqual(
            ["nature", "equipment", "construction", "items"],
            [category["category_name"] for category in categories],
        )
        groups = [
            group
            for category in categories
            for group in category.get("groups", [])
        ]
        self.assertEqual(len(categories), len(groups))
        for group in groups:
            self.assertEqual(
                "tf_slice:itemGroup.name.twilight_forest",
                group["group_identifier"]["name"],
            )
            self.assertEqual(
                "tf_slice:forest_wyrm_spawn_egg",
                group["group_identifier"]["icon"],
            )
        creative_items = {
            identifier
            for group in groups
            for identifier in group.get("items", [])
        }
        self.assertTrue(
            set(
                [
                "tf_slice:forest_wyrm_spawn_egg",
                "tf_slice:bighorn_sheep_spawn_egg",
                "tf_slice:boar_spawn_egg",
                "tf_slice:deer_spawn_egg",
                "tf_slice:fire_beetle_spawn_egg",
                "tf_slice:hedge_spider_spawn_egg",
                "tf_slice:hostile_wolf_spawn_egg",
                "tf_slice:kobold_spawn_egg",
                "tf_slice:pinch_beetle_spawn_egg",
                "tf_slice:raven_spawn_egg",
                "tf_slice:redcap_spawn_egg",
                "tf_slice:redcap_sapper_spawn_egg",
                "tf_slice:rising_zombie_spawn_egg",
                "tf_slice:skeleton_druid_spawn_egg",
                "tf_slice:slime_beetle_spawn_egg",
                "tf_slice:swarm_spider_spawn_egg",
                "tf_slice:wraith_spawn_egg",
                "tf_slice:raven_feather",
                "tf_slice:torchberries",
                "tf_slice:magic_map_focus",
                "tf_slice:magic_map",
                "tf_slice:filled_magic_map",
                "tf_slice:ironwood_pickaxe",
                "tf_slice:ironwood_boots",
                "tf_slice:tiny_bird_spawn_egg",
                "tf_slice:squirrel_spawn_egg",
                "tf_slice:dwarf_rabbit_spawn_egg",
                "tf_slice:quest_ram_spawn_egg",
                "tf_slice:penguin_spawn_egg",
                "tf_slice:crumble_horn",
                "tf_slice:quest_ram_trophy_item",
                "tf_slice:rainbow_oak_leaves",
                "tf_slice:fiddlehead",
                "tf_slice:mushgloom",
                "tf_slice:firefly",
                "tf_slice:firefly_jar",
                "tf_slice:cicada_jar",
                "tf_slice:canopy_fence",
                "tf_slice:fallen_leaves",
                "tf_slice:raw_venison",
                "tf_slice:cooked_venison",
                "tf_slice:naga_scale",
                "tf_slice:naga_chestplate",
                "tf_slice:naga_leggings",
                "tf_slice:naga_trophy_item",
                "tf_slice:twilight_oak_log",
                "tf_slice:twilight_oak_leaves",
                "tf_slice:canopy_log",
                "tf_slice:canopy_leaves",
                "tf_slice:nagastone",
                "tf_slice:etched_nagastone",
                "tf_slice:nagastone_pillar",
                "tf_slice:nagastone_head",
                "tf_slice:nagastone_stairs_left",
                "tf_slice:nagastone_stairs_right",
                "tf_slice:mossy_etched_nagastone",
                "tf_slice:cracked_etched_nagastone",
                "tf_slice:mossy_nagastone_pillar",
                "tf_slice:cracked_nagastone_pillar",
                "tf_slice:mossy_nagastone_stairs_left",
                "tf_slice:cracked_nagastone_stairs_left",
                "tf_slice:mossy_nagastone_stairs_right",
                "tf_slice:cracked_nagastone_stairs_right",
                "tf_slice:spiral_bricks",
                "tf_slice:mazestone_mosaic",
                ]
            ).issubset(creative_items)
        )
        self.assertIn(
            "tf_slice:itemGroup.name.twilight_forest=",
            ZH_CN.read_text(encoding="utf-8"),
        )

    def test_naga_scale_trophy_and_chest_loot_are_declared(self):
        self.assertTrue(NAGA_SCALE_ITEM.is_file())
        self.assertTrue(NAGA_TROPHY_BLOCK.is_file())
        self.assertTrue(NAGA_LOOT_TABLE.is_file())
        scale = json.loads(NAGA_SCALE_ITEM.read_text(encoding="utf-8"))
        trophy = json.loads(NAGA_TROPHY_BLOCK.read_text(encoding="utf-8"))
        self.assertEqual(
            "tf_slice:naga_scale",
            scale["minecraft:item"]["description"]["identifier"],
        )
        self.assertEqual(
            "tf_slice:naga_trophy",
            trophy["minecraft:block"]["description"]["identifier"],
        )
        textures = json.loads(ITEM_TEXTURES.read_text(encoding="utf-8"))[
            "texture_data"
        ]
        self.assertIn("tf_slice:naga_scale", textures)
        terrain = json.loads(TERRAIN_TEXTURES.read_text(encoding="utf-8"))[
            "texture_data"
        ]
        self.assertIn("tf_slice:naga_trophy", terrain)
        self.assertTrue(
            (ROOT / "TwilightBossSliceR" / "textures" / "items" / "naga_scale.png").is_file()
        )
        self.assertTrue(
            (ROOT / "TwilightBossSliceR" / "textures" / "blocks" / "naga_trophy.png").is_file()
        )

    def test_original_naga_sounds_and_combat_effect_event_are_wired(self):
        sounds = json.loads(SOUNDS.read_text(encoding="utf-8"))
        naga_events = sounds["entity_sounds"]["entities"][
            "tf_slice:forest_wyrm"
        ]["events"]
        self.assertEqual("tf_slice.naga.ambient", naga_events["ambient"])
        self.assertEqual("tf_slice.naga.hurt", naga_events["hurt"])
        self.assertEqual("tf_slice.naga.death", naga_events["death"])
        definitions = json.loads(
            SOUND_DEFINITIONS.read_text(encoding="utf-8")
        )["sound_definitions"]
        self.assertIn("tf_slice.naga.ambient", definitions)
        self.assertIn("tf_slice.naga.hurt", definitions)
        self.assertIn("tf_slice.naga.rattle", definitions)
        for sound_name in (
            "hiss1.ogg",
            "hiss2.ogg",
            "hiss3.ogg",
            "hurt1.ogg",
            "hurt2.ogg",
            "hurt3.ogg",
            "rattle1.ogg",
            "rattle2.ogg",
        ):
            self.assertTrue(
                (
                    ROOT
                    / "TwilightBossSliceR"
                    / "sounds"
                    / "mob"
                    / "naga"
                    / sound_name
                ).is_file()
            )
        client_source = CLIENT_SYSTEM.read_text(encoding="utf-8")
        self.assertIn('"NagaCombatEffect"', client_source)
        self.assertIn("def OnNagaCombatEffect(", client_source)
        combat_effect = client_source[
            client_source.index("    def OnNagaCombatEffect(") :
        ]
        self.assertIn(
            'if soundName == "tf_slice.naga.rattle"', combat_effect
        )
        self.assertIn("4.0", combat_effect)


if __name__ == "__main__":
    unittest.main()
