from __future__ import division

import json
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
RP = ROOT / "TwilightBossSliceR"
BP = ROOT / "TwilightBossSliceB"
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

import ur_ghast_logic as logic
import phantom_urghast_mob_logic as route_mob_logic


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class DegreeMath(object):
    @staticmethod
    def sin(value):
        return math.sin(math.radians(value))

    @staticmethod
    def cos(value):
        return math.cos(math.radians(value))


def evaluate_molang(expression, life_time):
    expression = str(expression).replace("query.life_time", repr(float(life_time)))
    return eval(
        expression,
        {"__builtins__": {}},
        {"math": DegreeMath},
    )


class UrGhastSourceParityTests(unittest.TestCase):
    def test_first_phase_uses_ten_damage_then_resets_to_eighteen_without_carry(self):
        state = logic.create_state((0, 200, 0), [(0, 180, 0)])

        first = logic.apply_damage(state, 10.0, "alice")

        self.assertTrue(first["phaseToggled"])
        self.assertEqual("accepted_damage", first["phaseReason"])
        self.assertEqual(
            "accepted_damage", state["lastPhaseTransitionReason"]
        )
        self.assertEqual("tantrum", state["phase"])
        self.assertEqual(18.0, state["damageUntilNextPhase"])

        second = logic.apply_damage(state, 180.0, "alice")

        self.assertTrue(second["phaseToggled"])
        self.assertEqual("normal", state["phase"])
        self.assertEqual(18.0, state["damageUntilNextPhase"])
        self.assertEqual(
            "accepted_damage", state["lastPhaseTransitionReason"]
        )

    def test_attack_goal_requires_range_and_sight_then_warns_fires_and_cools_down(self):
        state = logic.create_state((0, 200, 0), [])
        charging_ticks = 0

        for tick in range(1, 21):
            event = logic.advance_attack(
                state,
                has_target=True,
                distance_sq=4095.0,
                has_sight=True,
            )
            if tick == 10:
                self.assertTrue(event["warn"])
            if tick == 11:
                self.assertTrue(event["charging"])
            charging_ticks += int(bool(event["charging"]))

        self.assertTrue(event["fire"])
        self.assertEqual(-40, event["timer"])
        self.assertEqual(10, charging_ticks)

        blocked = logic.advance_attack(
            state,
            has_target=True,
            distance_sq=4095.0,
            has_sight=False,
        )
        self.assertFalse(blocked["fire"])
        self.assertFalse(blocked["charging"])
        self.assertEqual(-40, blocked["timer"])

        state["phase"] = "tantrum"
        cancelled = logic.advance_attack(
            state,
            has_target=True,
            distance_sq=1.0,
            has_sight=True,
        )
        self.assertTrue(cancelled["clearTarget"])
        self.assertEqual(0, cancelled["timer"])

    def test_positive_warmup_decays_when_line_of_sight_is_lost(self):
        state = logic.create_state((0, 200, 0), [])
        for _unused in range(7):
            logic.advance_attack(state, True, 16.0, True)

        event = logic.advance_attack(state, True, 16.0, False)

        self.assertEqual(6, event["timer"])
        self.assertFalse(event["warn"])
        self.assertFalse(event["fire"])

    def test_volley_spawns_outside_the_collision_box_from_mid_height(self):
        shots = logic.fireball_volley(
            (0.0, 100.0, 0.0),
            (0.0, 109.0, 40.0),
            spread_offsets=((3.0, -2.0), (-4.0, 5.0)),
        )

        self.assertEqual(3, len(shots))
        self.assertEqual([0.0, 111.0, 8.5], shots[0]["origin"])
        self.assertEqual([1.1, 109.0, 8.5], shots[1]["origin"])
        self.assertEqual([-1.1, 109.0, 8.5], shots[2]["origin"])
        for shot in shots:
            self.assertGreater(
                math.sqrt(shot["origin"][0] ** 2 + shot["origin"][2] ** 2),
                logic.BOSS_WIDTH / 2.0,
            )
            self.assertEqual(16.0, shot["directDamage"])
            self.assertEqual(1, shot["explosionPower"])
        self.assertEqual([0.0, 109.0, 40.0], shots[0]["target"])
        self.assertEqual([3.0, 109.0, 38.0], shots[1]["target"])
        self.assertEqual([-4.0, 109.0, 45.0], shots[2]["target"])

    def test_volley_mouth_origin_uses_the_full_downward_aim_vector(self):
        shots = logic.fireball_volley(
            (0.0, 100.0, 0.0),
            (0.0, 89.0, 40.0),
            spread_offsets=((0.0, 0.0), (0.0, 0.0)),
        )

        self.assertLess(shots[0]["origin"][1], 111.0)
        self.assertLess(shots[1]["origin"][1], 109.0)
        self.assertGreater(shots[0]["origin"][2], logic.BOSS_WIDTH / 2.0)

    def test_sibling_separation_exceeds_large_fireball_collision_diameter(self):
        behavior = load_json(
            BP / "entities" / "ur_ghast_fireball.entity.json"
        )["minecraft:entity"]["components"]
        diameter = behavior["minecraft:collision_box"]["width"]

        self.assertGreater(logic.FIREBALL_SIBLING_SEPARATION, diameter)

    def test_central_source_fireball_reaches_a_stationary_open_target(self):
        shot = logic.fireball_volley(
            (0.0, 100.0, 0.0),
            (0.0, 91.0, 32.0),
            spread_offsets=((0.0, 0.0), (0.0, 0.0)),
        )[0]
        projectile = logic.create_fireball_motion(
            shot["origin"], shot["target"], "boss", "boss"
        )
        position = list(shot["origin"])
        closest = float("inf")
        for unused in range(80):
            motion = logic.advance_fireball_motion(projectile)["motion"]
            position = [position[index] + motion[index] for index in range(3)]
            closest = min(closest, math.sqrt(sum(
                (float(position[index]) - float(shot["target"][index])) ** 2
                for index in range(3)
            )))

        self.assertLessEqual(closest, 1.0)

    def test_tantrum_tick_clears_target_cries_and_uses_ten_tick_tear_cadence(self):
        state = logic.create_state((0, 200, 0), [])
        state["phase"] = "tantrum"
        state["nextTantrumCry"] = 1

        event = logic.advance_tantrum(state, tick_count=20, cry_roll=29)

        self.assertTrue(event["clearTarget"])
        self.assertTrue(event["cry"])
        self.assertTrue(event["tearDamage"])
        self.assertEqual(49, state["nextTantrumCry"])

        quiet = logic.advance_tantrum(state, tick_count=21, cry_roll=0)
        self.assertFalse(quiet["cry"])
        self.assertFalse(quiet["tearDamage"])

    def test_tantrum_selects_two_traps_with_six_minions_each(self):
        state = logic.create_state(
            (0, 200, 0),
            [(0, 180, 0), (20, 180, 0), (40, 180, 0)],
        )
        state["phase"] = "tantrum"

        plans = logic.tantrum_minion_spawns(state, trap_order=(2, 0, 1))

        self.assertEqual(2, len(plans))
        self.assertEqual([6, 6], [plan["count"] for plan in plans])
        self.assertEqual([24, 24], [plan["tries"] for plan in plans])
        self.assertEqual([40.0, 180.0, 0.0], plans[0]["position"])
        self.assertEqual([0.0, 180.0, 0.0], plans[1]["position"])

    def test_locked_single_trap_plan_spawns_six_not_legacy_twelve(self):
        state = logic.create_state((0, 200, 0), [(0, 180, 0)])
        state["phase"] = "tantrum"

        plans = logic.tantrum_minion_spawns(state, trap_order=(0,))

        self.assertEqual(1, len(plans))
        self.assertEqual(6, plans[0]["count"])

    def test_reflection_transfers_exactly_one_fireball_owner_and_motion(self):
        projectile = {
            "ownerId": "boss",
            "reflected": False,
            "siblings": ["other-a", "other-b"],
        }

        event = logic.reflect_fireball(
            projectile,
            player_id="alice",
            look_vector=(0.0, 0.0, 4.0),
        )

        self.assertTrue(event["reflected"])
        self.assertEqual("alice", projectile["ownerId"])
        self.assertEqual((0.0, 0.0, 1.0), event["motion"])
        self.assertEqual(event["motion"], projectile["velocity"])
        self.assertEqual((0.0, 0.0, 0.1), event["acceleration"])
        self.assertEqual(event["acceleration"], projectile["acceleration"])
        self.assertEqual(4, projectile["ignoreOwnerTicks"])
        self.assertEqual(4, event["worldCollisionGraceTicks"])
        self.assertEqual(["other-a", "other-b"], projectile["siblings"])

    def test_absorbing_minions_heals_two_each_and_caps_at_max_health(self):
        state = logic.create_state((0, 200, 0), [])
        state["health"] = 247.0

        result = logic.absorb_nearby_minions(state, 3)

        self.assertEqual(3, result["consumed"])
        self.assertEqual(3.0, result["healed"])
        self.assertEqual(250.0, state["health"])

    def test_active_trap_damage_does_not_advance_phase_threshold(self):
        state = logic.create_state((0, 200, 0), [(0, 180, 0)])
        state["phase"] = "tantrum"
        state["damageUntilNextPhase"] = 5.0
        trap = logic.create_trap_state((0, 180, 0))
        trap["active"] = True

        result = logic.apply_active_trap_to_ur_ghast(
            trap, state, (0.5, 200.0, 0.5), deal_damage=True
        )

        self.assertEqual(7.0, result["damage"])
        self.assertEqual("normal", state["phase"])
        self.assertEqual(18.0, state["damageUntilNextPhase"])
        self.assertEqual(
            "active_trap_pull", state["lastPhaseTransitionReason"]
        )

    def test_version_one_state_migrates_phase_progress_and_attack_defaults(self):
        state = logic.load_state({
            "version": 1,
            "home": [0.0, 200.0, 0.0],
            "health": 200.0,
            "phase": "normal",
            "phaseDamage": 4.0,
        })

        self.assertEqual(6, state["version"])
        self.assertEqual(14.0, state["damageUntilNextPhase"])
        self.assertEqual(0, state["attackTimer"])
        self.assertEqual(0, state["inTrapTicks"])
        self.assertFalse(state["homeBound"])
        self.assertIsNone(state["wantedWaypoint"])

    def test_flight_route_uses_real_traps_and_refreshes_only_on_arrival(self):
        state = logic.create_state(
            (0, 200, 0),
            [(12, 180, 0), (-12, 180, 0)],
            home_bound=True,
        )

        self.assertEqual(
            [[12.0, 200.0, 0.0], [-12.0, 200.0, 0.0]],
            state["waypoints"],
        )
        selection = logic.select_next_waypoint(state)
        self.assertEqual([12.0, 200.0, 0.0], selection["point"])
        self.assertFalse(logic.waypoint_needs_refresh(
            (0.0, 200.0, 0.0), selection["point"]
        ))
        self.assertTrue(logic.waypoint_needs_refresh(
            (11.5, 200.0, 0.0), selection["point"]
        ))

    def test_no_trap_flight_route_uses_source_cardinal_fallback(self):
        state = logic.create_state((0, 200, 0), [])

        self.assertEqual(5, len(state["waypoints"]))
        self.assertEqual([20.0, 200.0, 0.0], state["waypoints"][0])
        self.assertEqual([0.0, 200.0, 0.0], state["waypoints"][-1])

    def test_structure_and_manual_routes_use_source_distinct_altitudes(self):
        traps = [(12, 180, 0), (-12, 184, 0)]
        bound = logic.create_state(
            (0, 200, 0), traps, home_bound=True, route_order=(1, 0)
        )
        manual = logic.create_state(
            (0, 200, 0), traps, home_bound=False, route_order=(1, 0)
        )

        self.assertEqual(
            [[-12.0, 204.0, 0.0], [12.0, 200.0, 0.0]],
            bound["waypoints"],
        )
        self.assertEqual(
            [[-12.0, 184.0, 0.0], [12.0, 180.0, 0.0]],
            manual["waypoints"],
        )
        self.assertEqual((192.0, 212.0), logic.flight_altitude_bounds(bound))
        self.assertEqual((172.0, 192.0), logic.flight_altitude_bounds(manual))

    def test_thirty_hz_adapter_emits_exactly_twenty_source_steps(self):
        remainder = 0
        emitted = []
        for unused in range(30):
            step = logic.advance_source_clock(remainder)
            emitted.append(step["steps"])
            remainder = step["remainder"]

        self.assertEqual(20, sum(emitted))
        self.assertEqual([0, 1, 1], emitted[:3])
        self.assertEqual(0, remainder)

    def test_version_two_high_recovery_target_is_removed_without_state_loss(self):
        state = logic.load_state({
            "version": 2,
            "home": [0.0, 200.0, 0.0],
            "health": 211.0,
            "phase": "tantrum",
            "damageUntilNextPhase": 12.6,
            "attackTimer": -17,
            "participants": ["alice"],
            "trapPoints": [[0.0, 180.0, 0.0]],
            "waypoints": [[0.0, 200.0, 0.0]],
            "wantedWaypoint": [0.0, 434.0, 0.0],
            "rewardClaimed": False,
        })

        self.assertEqual(6, state["version"])
        self.assertEqual(211.0, state["health"])
        self.assertEqual("tantrum", state["phase"])
        self.assertEqual(12.6, state["damageUntilNextPhase"])
        self.assertEqual(-17, state["attackTimer"])
        self.assertEqual(["alice"], state["participants"])
        self.assertIsNone(state["wantedWaypoint"])
        self.assertEqual(0, state["flightStallTicks"])
        self.assertEqual(0, state["deathSequenceId"])
        self.assertIsNone(state["settlementId"])

    def test_custom_death_sequence_and_reward_have_one_settlement_id(self):
        state = logic.create_state((0, 200, 0), [])
        result = logic.apply_damage(state, logic.MAX_HEALTH, "alice")
        self.assertTrue(result["accepted"])
        self.assertTrue(state["dying"])
        self.assertEqual(1, state["deathSequenceId"])
        self.assertTrue(logic.claim_reward(state))
        self.assertEqual(1, state["settlementId"])
        self.assertFalse(logic.claim_reward(state))
        self.assertEqual(1, state["settlementId"])


class UrGhastProductionBindingTests(unittest.TestCase):
    def test_molang_converts_java_radian_phase_inside_every_trig_call(self):
        animations = load_json(
            RP / "animations" / "phantom_urghast_route.animation.json"
        )["animations"]
        bones = animations["animation.tf_slice.ur_ghast.move"]["bones"]

        for index in range(9):
            for name in (
                "tentacle_%d" % index,
                "tentacle_%d_extension" % index,
                "tentacle_%d_tip" % index,
            ):
                expression = " ".join(str(value) for value in bones[name]["rotation"])
                self.assertIn("57.2958", expression, name)

    def test_tentacle_motion_reaches_source_bounds_within_five_seconds(self):
        animations = load_json(
            RP / "animations" / "phantom_urghast_route.animation.json"
        )["animations"]
        bones = animations["animation.tf_slice.ur_ghast.move"]["bones"]
        samples = [index / 20.0 for index in range(101)]

        for index in range(9):
            base = [
                evaluate_molang(
                    bones["tentacle_%d" % index]["rotation"][1], value
                )
                for value in samples
            ]
            extension = [
                evaluate_molang(
                    bones["tentacle_%d_extension" % index]["rotation"][0], value
                )
                for value in samples
            ]
            tip = [
                evaluate_molang(
                    bones["tentacle_%d_tip" % index]["rotation"][0], value
                )
                for value in samples
            ]
            self.assertLessEqual(max(abs(value) for value in base), 22.919)
            self.assertGreater(max(base) - min(base), 44.0)
            self.assertGreaterEqual(min(extension), -2.866)
            self.assertLessEqual(max(extension), 14.325)
            self.assertGreater(max(extension) - min(extension), 16.5)
            self.assertGreaterEqual(min(tip), -5.731)
            self.assertLessEqual(max(tip), 17.19)
            self.assertGreater(max(tip) - min(tip), 22.0)

    def test_tracking_texture_branch_and_behavior_property_are_reachable(self):
        behavior = load_json(BP / "entities" / "ur_ghast.entity.json")[
            "minecraft:entity"
        ]
        client = load_json(RP / "entity" / "ur_ghast.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        controllers = load_json(
            RP / "render_controllers" / "phantom_urghast_route.render.json"
        )["render_controllers"]
        texture_expression = controllers[
            "controller.render.tf_slice.ur_ghast"
        ]["textures"][0]

        self.assertIn(
            "tf_slice:attack_state", behavior["description"]["properties"]
        )
        self.assertIn("tf_slice:attack_tracking", behavior["events"])
        self.assertIn("tf_slice:attack_charging", behavior["events"])
        self.assertEqual(
            "textures/entity/tf_slice/ur_ghast_open",
            client["textures"]["open"],
        )
        self.assertIn("tf_slice:attack_state", texture_expression)
        self.assertIn("tf_slice:attack_timer", texture_expression)
        self.assertIn("Array.skins[", texture_expression)
        self.assertNotIn("?", texture_expression)

    def test_server_and_client_wire_source_timeline_and_tantrum_presentation(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")

        for token in (
            "advance_attack",
            "_ur_ghast_can_see",
            "mob.ghast.charge",
            "mob.ghast.fireball",
            "mob.ghast.scream",
            "UrGhastEffect",
            "absorb_nearby_minions",
        ):
            self.assertIn(token, server)
        self.assertIn('"UrGhastEffect"', client)
        self.assertIn("OnUrGhastEffect", client)


class UrGhastEffectAssetTests(unittest.TestCase):
    def test_source_weather_intensity_ramps_fades_and_expires_fail_closed(self):
        import ur_ghast_effect_logic as effects

        intensity = 0.0
        for _unused in range(12):
            intensity = effects.advance_storm_intensity(intensity, True)
        self.assertEqual(1.0, intensity)
        self.assertEqual(100, effects.weather_particle_budget(intensity))

        for _unused in range(50):
            intensity = effects.advance_storm_intensity(intensity, False)
        self.assertEqual(0.0, intensity)
        self.assertEqual(0, effects.weather_particle_budget(intensity))
        self.assertFalse(effects.storm_keepalive_active(80, 40))

    def test_trap_effect_stages_and_six_spiral_vectors_match_source(self):
        import ur_ghast_effect_logic as effects

        self.assertEqual("warmup", effects.trap_effect_stage(0))
        self.assertEqual("warmup", effects.trap_effect_stage(29))
        self.assertEqual("active", effects.trap_effect_stage(30))
        self.assertEqual("active", effects.trap_effect_stage(79))
        self.assertEqual("spindown", effects.trap_effect_stage(80))
        self.assertEqual("spindown", effects.trap_effect_stage(119))
        self.assertEqual("stop", effects.trap_effect_stage(120))

        vectors = effects.trap_spiral_vectors(0)
        self.assertEqual(6, len(vectors))
        self.assertEqual([20.0, 20.0, 10.0, 10.0, 5.0, 5.0], [
            vector[1] for vector in vectors
        ])
        self.assertAlmostEqual(2.5, vectors[0][0], places=6)
        self.assertAlmostEqual(-2.5, vectors[1][0], places=6)
        for stage in ("warmup", "active", "spindown"):
            self.assertEqual(5, effects.trap_effect_interval(stage))

    def test_dedicated_particle_assets_resolve_and_rain_texture_is_source_locked(self):
        expected = {
            "ur_ghast_lightning.json": "tf_slice:ur_ghast_lightning",
            "ghast_trap_mote.json": "tf_slice:ghast_trap_mote",
            "ghast_trap_beam.json": "tf_slice:ghast_trap_beam",
        }
        for file_name, identifier in expected.items():
            document = load_json(RP / "particles" / file_name)
            description = document["particle_effect"]["description"]
            self.assertEqual(identifier, description["identifier"])
            texture = description["basic_render_parameters"]["texture"]
            texture_path = RP / (texture + ".png")
            self.assertTrue(texture_path.is_file(), texture)

    def test_server_client_and_sound_bindings_cover_storm_and_all_trap_stages(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        sounds = load_json(RP / "sounds.json")

        for token in (
            "storm_keepalive",
            "storm_stop",
            "SetDimensionLocalRain",
            "SetDimensionLocalThunder",
            "trap_effect_stage",
            "beacon.activate",
            "conduit.activate",
            "portal.trigger",
            "ambient.weather.thunder",
        ):
            self.assertIn(token, server)
        for token in (
            "minecraft:water_splash_particle_manual",
            "tf_slice:ur_ghast_lightning",
            "tf_slice:ghast_trap_mote",
            "tf_slice:ghast_trap_beam",
        ):
            self.assertIn(token, client)
        events = sounds["entity_sounds"]["entities"]["tf_slice:ur_ghast"]["events"]
        self.assertEqual("mob.ghast.moan", events["ambient"])
        self.assertEqual("mob.ghast.scream", events["hurt"])
        self.assertEqual("mob.ghast.death", events["death"])

        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("textures/environment/bigrain.png", notices)
        self.assertIn("No Ur-Ghast or Ghast Trap audio was copied", notices)


class UrGhastRuntimeRejectionRegressionTests(unittest.TestCase):
    def test_088_p_key_toggle_is_press_edge_triggered(self):
        import ur_ghast_hitbox_debug_logic as hitbox_debug

        state = hitbox_debug.key_transition(False, False, 80, True)
        self.assertEqual(
            {"enabled": True, "keyDown": True, "toggled": True}, state
        )
        held = hitbox_debug.key_transition(
            state["enabled"], state["keyDown"], 80, True
        )
        self.assertEqual(
            {"enabled": True, "keyDown": True, "toggled": False}, held
        )
        released = hitbox_debug.key_transition(
            held["enabled"], held["keyDown"], "80", False
        )
        self.assertEqual(
            {"enabled": True, "keyDown": False, "toggled": False},
            released,
        )
        disabled = hitbox_debug.key_transition(
            released["enabled"], released["keyDown"], "80", "1"
        )
        self.assertEqual(
            {"enabled": False, "keyDown": True, "toggled": True},
            disabled,
        )
        ignored = hitbox_debug.key_transition(False, False, 79, True)
        self.assertEqual(
            {"enabled": False, "keyDown": False, "toggled": False},
            ignored,
        )

    def test_088_hitbox_debug_descriptors_match_production_volumes(self):
        import ur_ghast_hitbox_debug_logic as hitbox_debug

        descriptors = hitbox_debug.box_descriptors((10.0, 20.0, 30.0))
        self.assertEqual(
            ("physical", "attack"),
            tuple(item["name"] for item in descriptors),
        )
        physical, attack = descriptors
        self.assertEqual((10.0, 29.0, 30.0), physical["center"])
        self.assertEqual((14.0, 18.0, 14.0), physical["scale"])
        self.assertEqual((1.0, 0.12, 0.12), physical["color"])
        self.assertEqual((10.0, 32.5, 30.0), attack["center"])
        self.assertEqual((12.5, 12.5, 12.5), attack["scale"])
        self.assertEqual((0.12, 1.0, 0.24), attack["color"])
        self.assertGreater(attack["priority"], physical["priority"])
        self.assertEqual((), hitbox_debug.box_descriptors(None))

    def test_088_client_owns_local_p_key_hitbox_overlay(self):
        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        constructor = client[client.index("def __init__"):]
        constructor = constructor[:constructor.index("\n    def ", 1)]
        self.assertIn('"OnKeyPressInGame"', constructor)
        self.assertIn("CF.CreateDrawing(LEVEL_ID)", constructor)
        self.assertIn("_ur_ghast_hitbox_shapes", constructor)

        key_handler = client[client.index("def OnKeyPressInGame"):]
        key_handler = key_handler[:key_handler.index("\n    def ", 1)]
        self.assertIn("hitbox_debug.key_transition", key_handler)
        self.assertIn("_clear_ur_ghast_hitbox_shapes", key_handler)
        self.assertNotIn("NotifyToServer", key_handler)

        updater = client[client.index("def _update_ur_ghast_hitbox_debug"):]
        updater = updater[:updater.index("\n    def ", 1)]
        self.assertIn('boss.get("kind") != "ur_ghast"', updater)
        self.assertIn("CF.CreatePos(bossId).GetFootPos()", updater)
        self.assertIn("SetPos", updater)
        self.assertIn("_create_ur_ghast_hitbox_shapes", updater)
        creator = client[client.index("def _create_ur_ghast_hitbox_shapes"):]
        creator = creator[:creator.index("\n    def ", 1)]
        self.assertIn("AddBoxShape", creator)
        self.assertIn("SetPriority", creator)
        self.assertIn("Remove", client)

        tick = client[client.index("def OnScriptTickClient"):]
        tick = tick[:tick.index("\n    def ", 1)]
        self.assertIn("_update_ur_ghast_hitbox_debug", tick)
        reset = client[client.index("def OnBossHudReset"):]
        reset = reset[:reset.index("\n    def ", 1)]
        self.assertIn("_clear_ur_ghast_hitbox_shapes", reset)
        dimension = client[client.index("def OnDimensionChangeClientEvent"):]
        dimension = dimension[:dimension.index("\n    def ", 1)]
        self.assertIn("_clear_ur_ghast_hitbox_shapes", dimension)
        destroy = client[client.index("def Destroy(self)"):]
        destroy = destroy[:destroy.index("\n    def ", 1)]
        self.assertIn("_clear_ur_ghast_hitbox_shapes", destroy)
        acceptance_builder = (
            ROOT / "tools" / "build_phantom_urghast_acceptance.py"
        ).read_text(encoding="utf-8")
        self.assertIn("UR_GHAST_HITBOX_DEBUG_LOGIC", acceptance_builder)
        self.assertIn("ur_ghast_hitbox_debug_logic.py", acceptance_builder)

    def test_083_source_attack_scale_is_continuous_and_timer_driven(self):
        neutral = logic.attack_scale(0)
        halfway = logic.attack_scale(10)
        almost_fire = logic.attack_scale(19)
        firing = logic.attack_scale(20)

        self.assertEqual((1.0, 1.0, 1.0), neutral)
        self.assertLess(halfway[1], neutral[1])
        self.assertGreater(almost_fire[0], halfway[0])
        self.assertGreater(firing[0], almost_fire[0])
        self.assertLess(firing[1], almost_fire[1])

        entity = load_json(BP / "entities" / "ur_ghast.entity.json")
        properties = entity["minecraft:entity"]["description"]["properties"]
        self.assertEqual([-40.0, 20.0], properties["tf_slice:attack_timer"]["range"])
        animation = load_json(
            RP / "animations" / "phantom_urghast_route.animation.json"
        )["animations"]["animation.tf_slice.ur_ghast.move"]
        scale = animation["bones"]["root"]["scale"]
        for expression in scale:
            self.assertIn("tf_slice:attack_timer", expression)
            self.assertNotIn("tf_slice:attack_state') > 1.5", expression)
        builder = (
            ROOT / "tools" / "build_phantom_urghast_models.py"
        ).read_text(encoding="utf-8")
        self.assertIn("tf_slice:attack_timer", builder)
        self.assertNotIn(
            'charge = "query.property(\'tf_slice:attack_state\') > 1.5"',
            builder,
        )

    def test_083_fire_tick_preserves_source_visual_peak_before_cooldown(self):
        state = logic.create_state((0.0, 200.0, 0.0), ())
        event = None
        for unused in range(20):
            event = logic.advance_attack(state, True, 100.0, True)

        self.assertTrue(event["fire"])
        self.assertEqual(-40, state["attackTimer"])
        self.assertEqual(20, state["prevAttackTimer"])
        self.assertEqual(20, state["visualAttackTimer"])

    def test_083_tantrum_minion_lift_is_engine_scaled_and_bounded(self):
        motion = (0.2, -0.4, -0.3)
        for unused in range(100):
            motion = logic.tantrum_minion_lift_motion(motion)

        self.assertEqual(0.2, motion[0])
        self.assertEqual(-0.3, motion[2])
        self.assertGreater(motion[1], 0.0)
        self.assertLessEqual(motion[1], logic.TANTRUM_MINION_LIFT_MAX)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        tears = server[server.index("def _apply_ur_ghast_tantrum_damage"):]
        tears = tears[:tears.index("\n    def ", 1)]
        self.assertIn("tantrum_minion_lift_motion", tears)
        self.assertNotIn("current[1] + 1.0", tears)

    def test_084_tear_particles_form_a_bounded_ground_reaching_curtain(self):
        import ur_ghast_effect_logic as effects

        positions = effects.tear_column_positions(
            (10.0, 200.0, 30.0),
            tuple(
                (
                    index / 15.0,
                    (15 - index) / 15.0,
                    ((index * 7) % 16) / 15.0,
                )
                for index in range(16)
            ),
        )

        self.assertEqual(16, effects.TEAR_PARTICLES_PER_PULSE)
        self.assertEqual(16, len(positions))
        self.assertEqual(4.5, effects.TEAR_COLUMN_HALF_WIDTH)
        self.assertEqual(-0.5, effects.TEAR_COLUMN_MIN_Y)
        self.assertEqual(0.5, effects.TEAR_COLUMN_MAX_Y)
        self.assertEqual(199.5, min(point[1] for point in positions))
        self.assertEqual(200.5, max(point[1] for point in positions))
        self.assertTrue(all(5.5 <= point[0] <= 14.5 for point in positions))
        self.assertTrue(all(25.5 <= point[2] <= 34.5 for point in positions))

        # Presentation is narrower than the authoritative source AABB.  The
        # gameplay damage/lift envelope must remain the 14 x 50 x 14 Boss box.
        self.assertEqual(14.0, logic.BOSS_WIDTH)
        self.assertEqual(18.0, logic.BOSS_HEIGHT)
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        tears = server[server.index("def _apply_ur_ghast_tantrum_damage"):]
        tears = tears[:tears.index("\n    def ", 1)]
        self.assertIn("ur_ghast_logic.BOSS_WIDTH / 2.0", tears)
        self.assertIn("position[1] - 32.0", tears)
        self.assertIn("position[1] + ur_ghast_logic.BOSS_HEIGHT", tears)

        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        effect = client[client.index("def OnUrGhastEffect"):]
        effect = effect[:effect.index("\n    def ", 1)]
        self.assertIn("tear_column_positions", effect)
        self.assertNotIn("random.uniform(5.0, 13.0)", effect)

    def test_084_runtime_orientation_combines_yaw_offset_and_positive_pitch(self):
        self.assertEqual(0.0, logic.render_yaw(0.0))
        self.assertEqual(90.0, logic.render_yaw(90.0))
        self.assertEqual(-90.0, logic.render_yaw(-90.0))
        self.assertAlmostEqual(178.53, logic.render_yaw(178.53), places=5)

        animation = load_json(
            RP / "animations" / "phantom_urghast_route.animation.json"
        )["animations"]["animation.tf_slice.ur_ghast.move"]
        pitch_expression = animation["bones"]["pose_root"]["rotation"][0]
        self.assertEqual(
            "query.property('tf_slice:visual_pitch')",
            pitch_expression,
        )

        builder = (
            ROOT / "tools" / "build_phantom_urghast_models.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '"query.property(\'tf_slice:visual_pitch\')", 0, 0',
            builder,
        )
        self.assertNotIn("visual_pitch') * -1.0", builder)

    def test_084_orientation_comparison_uses_one_model_and_one_camera(self):
        from PIL import Image, ImageChops

        script = ROOT / "tools" / "render_ur_ghast_orientation_comparison.py"
        output = (
            ROOT / "model_acceptance" / "offline" / "comparisons"
            / "ur_ghast_orientation_before_after.png"
        )
        self.assertTrue(script.is_file())
        source = script.read_text(encoding="utf-8")
        self.assertIn("BEFORE_YAW_OFFSET = 180.0", source)
        self.assertIn("BEFORE_PITCH_SIGN = 1.0", source)
        self.assertIn("AFTER_YAW_OFFSET = 0.0", source)
        self.assertIn("AFTER_PITCH_SIGN = 1.0", source)
        self.assertIn("SHARED_CAMERA", source)
        self.assertIn("PLAYER_REFERENCE_HEIGHT_BLOCKS = 2.0", source)
        self.assertIn("def _player_reference_layer():", source)
        self.assertIn("player_reference", source)
        self.assertIn("overlay_layers=[player_reference]", source)
        self.assertTrue(output.is_file())
        with Image.open(output) as image:
            self.assertEqual((1400, 760), image.size)
            left = image.crop((20, 80, 690, 740))
            right = image.crop((710, 80, 1380, 740))
            self.assertIsNotNone(ImageChops.difference(left, right).getbbox())

    def test_084_tantrum_render_heading_matches_horizontal_motion(self):
        samples = (
            (-0.0044, 0.0, 0.2757),
            (-0.0047, 0.0, -0.1848),
            (0.3, 0.0, 0.0),
            (-0.3, 0.0, 0.0),
        )
        for motion in samples:
            logical_yaw = logic.yaw_for_motion(motion)
            render_yaw = logic.render_yaw(logical_yaw)
            radians = math.radians(render_yaw)
            facing = (-math.sin(radians), math.cos(radians))
            length = math.sqrt(motion[0] ** 2 + motion[2] ** 2)
            normalized_motion = (motion[0] / length, motion[2] / length)
            alignment = (
                facing[0] * normalized_motion[0]
                + facing[1] * normalized_motion[1]
            )
            self.assertGreater(alignment, 0.999)

    def test_083_core_attack_and_trap_motion_precede_visual_delivery(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        drive = server[server.index("def _drive_ur_ghasts"):]
        drive = drive[:drive.index("\n    def ", 1)]

        trap = drive[drive.index("if activeTrap is not None:"):]
        trap = trap[:trap.index("continue")]
        self.assertLess(
            trap.index('state["motionOwner"] = "trap"'),
            trap.index("self._sync_ur_ghast_visual("),
        )

        combat = drive[drive.index("attack = ur_ghast_logic.advance_attack"):]
        self.assertLess(
            combat.index("self._spawn_ur_ghast_volley("),
            combat.index("self._sync_ur_ghast_visual("),
        )

    def test_082_runtime_route_intent_is_committed_before_combat_perception(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        drive = server[server.index("def _drive_ur_ghasts"):]
        drive = drive[:drive.index("\n    def ", 1)]

        route_index = drive.index("waypoint_needs_refresh")
        motion_index = drive.index('state["motionOwner"] = "flight"')
        perception_index = drive.index("hasSight = bool(")
        self.assertLess(route_index, perception_index)
        self.assertLess(motion_index, perception_index)

    def test_082_weather_refresh_survives_a_failed_source_ai_tick(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        update = server[server.index("def Update(self):"):]
        update = update[:update.index("\n    def ", 1)]
        source_step = update[update.index("if self._ur_ghast_logic_step:"):]
        drive_index = source_step.index("self._drive_ur_ghasts()")
        weather_index = source_step.index(
            "self._update_ur_ghast_native_weather()"
        )
        self.assertIn("try:", source_step[:weather_index])
        self.assertIn("except Exception as error:", source_step[:weather_index])
        self.assertIn("finally:", source_step[:weather_index])
        self.assertLess(drive_index, weather_index)

        tantrum = server[server.index("def _begin_ur_ghast_tantrum"):]
        tantrum = tantrum[:tantrum.index("\n    def ", 1)]
        self.assertIn("_update_ur_ghast_native_weather(force=True)", tantrum)

    def test_082_duplicate_registration_preserves_live_driver_state(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        register = server[server.index("def _register_ur_ghast"):]
        register = register[:register.index("\n    def ", 1)]
        existing_index = register.index("matching_entity_key")
        load_index = register.index("CreateExtraData")
        self.assertLess(existing_index, load_index)
        self.assertIn('existingState["engineEntityId"] = entityId', register)
        self.assertIn("return existingState", register)

    def test_082_minus_one_attack_target_is_normalized_before_perception(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        getter = server[server.index("def _get_attack_target"):]
        getter = getter[:getter.index("\n    def ", 1)]
        self.assertIn("_valid_entity_id", getter)
        self.assertIn("return None", getter)

    def test_081_state_migration_preserves_combat_but_resets_engine_adapter(self):
        migrated = logic.load_state({
            "version": 5,
            "home": [0.0, 200.0, 0.0],
            "health": 211.0,
            "phase": "tantrum",
            "damageUntilNextPhase": 7.5,
            "participants": ["alice"],
            "sourceFlightVelocity": [0.2, 0.0, 0.1],
            "wantedWaypoint": [20.0, 200.0, 0.0],
            "motionAuthority": "direct_compat",
        })

        self.assertEqual(6, logic.STATE_VERSION)
        self.assertEqual(6, migrated["version"])
        self.assertEqual(211.0, migrated["health"])
        self.assertEqual("tantrum", migrated["phase"])
        self.assertEqual(7.5, migrated["damageUntilNextPhase"])
        self.assertEqual(["alice"], migrated["participants"])
        self.assertEqual([0.2, 0.0, 0.1], migrated["sourceFlightVelocity"])
        self.assertEqual("source_accumulator", migrated["motionAuthority"])

    def test_081_engine_adapter_falls_back_after_five_motionless_frames(self):
        state = logic.create_engine_motion_state()
        result = None
        for unused in range(5):
            result = logic.advance_engine_motion_adapter(
                state,
                requested_motion=(0.18, 0.0, 0.0),
                actual_displacement=0.0,
                set_succeeded=True,
                target_vector=(20.0, 0.0, 0.0),
            )

        self.assertEqual("direct_compat", result["mode"])
        self.assertEqual(5, result["failureFrames"])
        self.assertEqual((0.25, 0.0, 0.0), result["motion"])

    def test_081_engine_adapter_recovers_source_mode_after_real_motion(self):
        state = logic.create_engine_motion_state("direct_compat")
        result = None
        for unused in range(20):
            result = logic.advance_engine_motion_adapter(
                state,
                requested_motion=(0.16, 0.0, 0.0),
                actual_displacement=0.12,
                set_succeeded=True,
                target_vector=(20.0, 0.0, 0.0),
            )

        self.assertEqual("source_accumulator", result["mode"])
        self.assertEqual((0.16, 0.0, 0.0), result["motion"])

    def test_081_server_reapplies_motion_on_every_engine_update(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("def _apply_ur_ghast_engine_motion", server)
        update = server[server.index("def Update(self):"):]
        update = update[:update.index("\n    def ", 1)]
        apply_index = update.index("self._apply_ur_ghast_engine_motion()")
        self.assertGreater(
            apply_index,
            update.index("self._update_ghast_traps()") + len("self._update_ghast_traps()"),
        )
        self.assertIn(
            "\n        self._apply_ur_ghast_engine_motion()", update
        )
        self.assertNotIn(
            "\n            self._apply_ur_ghast_engine_motion()", update
        )

        drive = server[server.index("def _drive_ur_ghasts"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertIn('state["requestedEngineMotion"]', drive)
        self.assertNotIn("self._set_full_motion(", drive)

    def test_081_driver_and_weather_failures_are_never_silent(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        register = server[server.index("def _register_ur_ghast"):]
        register = register[:register.index("\n    def ", 1)]
        for field in (
            "engineEntityId",
            "nextDriverTraceTick",
            "motionFailureTicks",
            "positionFailureTicks",
        ):
            self.assertIn(field, register)

        engine = server[server.index("def _apply_ur_ghast_engine_motion"):]
        engine = engine[:engine.index("\n    def ", 1)]
        self.assertIn('"ur_ghast.driver_sample"', engine)
        self.assertIn("setMotionResult", engine)
        self.assertIn("actualMotion", engine)
        self.assertIn("actualDisplacement", engine)

        weather = server[server.index("def _update_ur_ghast_native_weather"):]
        weather = weather[:weather.index("\n    def ", 1)]
        self.assertIn('"ur_ghast.weather_write"', weather)
        for result_name in (
            "localResult",
            "cycleResult",
            "rainResult",
            "thunderResult",
        ):
            self.assertIn(result_name, weather)

    def test_081_client_storm_helpers_have_a_real_tick_consumer(self):
        import ur_ghast_effect_logic as effects

        storms = {
            "boss": {"expires": 40, "dimensionId": 33027004},
        }
        step = effects.storm_presentation_step(
            storms, current_tick=1, dimension_id=33027004, intensity=0.0
        )
        self.assertTrue(step["active"])
        self.assertEqual(0.1, step["intensity"])
        self.assertGreater(step["particleBudget"], 0)

        stopped = effects.storm_presentation_step(
            {}, current_tick=60, dimension_id=33027004, intensity=0.1
        )
        self.assertFalse(stopped["active"])
        self.assertLess(stopped["intensity"], step["intensity"])

        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        self.assertIn("def _tick_ur_ghast_storm_presentation", client)
        tick = client[client.index("def OnScriptTickClient"):]
        tick = tick[:tick.index("\n    def ", 1)]
        self.assertIn("_tick_ur_ghast_storm_presentation", tick)
        presentation = client[
            client.index("def _tick_ur_ghast_storm_presentation"):
        ]
        presentation = presentation[:presentation.index("\n    def ", 1)]
        self.assertIn("storm_presentation_step", presentation)
        self.assertIn("minecraft:water_splash_particle_manual", presentation)

    def test_081_air_and_invalid_actor_inputs_fail_before_engine_calls(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        states = server[server.index("def _fire_swamp_block_states"):]
        states = states[:states.index("\n    def ", 1)]
        self.assertIn("_get_block", states)
        self.assertIn("SIGHT_PASSABLE_BLOCKS", states)
        self.assertLess(states.index("SIGHT_PASSABLE_BLOCKS"), states.index("GetBlockStates"))

        full_motion = server[server.index("def _set_full_motion"):]
        full_motion = full_motion[:full_motion.index("\n    def ", 1)]
        self.assertIn("_valid_entity_id", full_motion)
        self.assertLess(full_motion.index("_valid_entity_id"), full_motion.index("CreateActorMotion"))

    def test_079_state_migration_adds_numeric_visual_and_source_motion(self):
        migrated = logic.load_state({
            "version": 4,
            "home": [0.0, 200.0, 0.0],
            "health": 211.0,
            "phase": "tantrum",
            "damageUntilNextPhase": 7.5,
            "participants": ["alice"],
            "rewardClaimed": False,
        })

        self.assertEqual(6, logic.STATE_VERSION)
        self.assertEqual(6, migrated["version"])
        self.assertEqual(211.0, migrated["health"])
        self.assertEqual("tantrum", migrated["phase"])
        self.assertEqual(7.5, migrated["damageUntilNextPhase"])
        self.assertEqual(["alice"], migrated["participants"])
        self.assertEqual(0.0, migrated["visualAttackState"])
        self.assertEqual(0.0, migrated["visualPitch"])
        self.assertEqual([0.0, 0.0, 0.0], migrated["sourceFlightVelocity"])

    def test_087_attack_texture_index_uses_existing_numeric_properties(self):
        state = logic.create_state((0, 200, 0), [])
        observed = []
        for tick in range(1, 21):
            event = logic.advance_attack(state, True, 16.0, True)
            observed.append(event["visualState"])

        self.assertEqual([1.0] * 10, observed[:10])
        self.assertEqual([2.0] * 10, observed[10:20])
        self.assertTrue(event["fire"])
        self.assertTrue(event["charging"])
        after_fire = logic.advance_attack(state, True, 16.0, True)
        self.assertEqual(1.0, after_fire["visualState"])
        self.assertFalse(after_fire["charging"])

        entity = load_json(BP / "entities" / "ur_ghast.entity.json")[
            "minecraft:entity"
        ]
        properties = entity["description"]["properties"]
        self.assertIn("tf_slice:attack_state", properties)
        self.assertNotIn("tf_slice:tracking", properties)
        self.assertNotIn("tf_slice:charging", properties)
        self.assertEqual("float", properties["tf_slice:attack_state"]["type"])
        self.assertEqual("float", properties["tf_slice:attack_timer"]["type"])
        events = entity["events"]
        for event_name, value in (
            ("tf_slice:attack_normal", 0.0),
            ("tf_slice:attack_tracking", 1.0),
            ("tf_slice:attack_charging", 2.0),
        ):
            self.assertEqual(
                value,
                events[event_name]["set_property"]["tf_slice:attack_state"],
            )
            self.assertNotIn(
                "tf_slice:charging", events[event_name]["set_property"]
            )

        renderer = load_json(
            RP / "render_controllers" / "phantom_urghast_route.render.json"
        )["render_controllers"]["controller.render.tf_slice.ur_ghast"]
        texture_expression = renderer["textures"][0]
        self.assertIn("Array.skins[", texture_expression)
        self.assertIn("tf_slice:attack_state", texture_expression)
        self.assertIn("tf_slice:attack_timer", texture_expression)
        self.assertIn("math.clamp", texture_expression)
        self.assertNotIn("tf_slice:charging", texture_expression)
        self.assertNotIn("?", texture_expression)

        builder = (
            ROOT / "tools" / "build_phantom_urghast_models.py"
        ).read_text(encoding="utf-8")
        ur_renderer = builder[builder.index(
            '"controller.render.tf_slice.ur_ghast"'
        ):]
        ur_renderer = ur_renderer[:ur_renderer.index("\n            },", 1)]
        self.assertIn("Array.skins[", ur_renderer)
        self.assertIn("tf_slice:attack_timer", ur_renderer)
        self.assertNotIn("tf_slice:charging", ur_renderer)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        visual = server[server.index("def _sync_ur_ghast_visual"):]
        visual = visual[:visual.index("\n    def ", 1)]
        self.assertNotIn('"tf_slice:charging"', visual)
        self.assertIn("chargingValue", visual)

    def test_086_combat_pitch_is_oblique_while_trap_pitch_can_face_down(self):
        self.assertEqual(90.0, logic.VISUAL_PITCH_LIMIT)
        self.assertEqual(45.0, logic.COMBAT_VISUAL_PITCH_LIMIT)
        self.assertAlmostEqual(
            45.0,
            logic.visual_pitch_degrees((0, 20, 0), (0, 0, 20)),
            places=5,
        )
        self.assertAlmostEqual(
            -45.0,
            logic.visual_pitch_degrees((0, -20, 0), (0, 0, 20)),
            places=5,
        )
        self.assertAlmostEqual(
            45.0,
            logic.visual_pitch_degrees((0, 20, 0), (0, -100, 0)),
            places=5,
        )
        self.assertAlmostEqual(
            -45.0,
            logic.visual_pitch_degrees((0, -20, 0), (0, 100, 0)),
            places=5,
        )

        geometry = load_json(
            RP / "models" / "entity" / "phantom_urghast_route.geo.json"
        )["minecraft:geometry"]
        ur_geometry = next(
            item for item in geometry
            if item["description"]["identifier"] == "geometry.tf_slice.ur_ghast"
        )
        bones = {bone["name"]: bone for bone in ur_geometry["bones"]}
        self.assertEqual([0, 16, 0], bones["pose_root"]["pivot"])
        self.assertEqual("root", bones["pose_root"]["parent"])
        self.assertEqual("pose_root", bones["body"]["parent"])

        animation = load_json(
            RP / "animations" / "phantom_urghast_route.animation.json"
        )["animations"]["animation.tf_slice.ur_ghast.move"]
        self.assertIn("pose_root", animation["bones"])
        pose = json.dumps(animation["bones"]["pose_root"])
        self.assertIn("tf_slice:visual_pitch", pose)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        sync = server[server.index("def _sync_ur_ghast_visual_pitch"):]
        sync = sync[:sync.index("\n    def ", 1)]
        self.assertIn("ur_ghast_logic.VISUAL_PITCH_LIMIT", sync)
        self.assertNotIn("min(90.0", sync)

    def test_079_source_flight_reference_recovers_five_block_per_second_cruise(self):
        self.assertEqual(0.91, logic.FLIGHT_DRAG)
        state = logic.create_state((0, 200, 0), [])
        position = [0.0, 200.0, 0.0]
        motion = (0.0, 0.0, 0.0)
        speeds = []
        for tick in range(1400):
            event = logic.advance_flight_motion(
                state,
                position=position,
                wanted=(10000.0, 200.0, 0.0),
                current_motion=motion,
                cooldown_roll=tick % logic.FLIGHT_COURSE_COOLDOWN_SPREAD,
            )
            motion = event["motion"]
            position = [position[index] + motion[index] for index in range(3)]
            if tick >= 200:
                speeds.append(math.sqrt(sum(value * value for value in motion)))

        average = sum(speeds) / len(speeds)
        self.assertGreaterEqual(average, 0.24)
        self.assertLessEqual(average, 0.27)

    def test_079_fireball_motion_has_one_authority_and_reflection_does_not_float(self):
        projectile = logic.create_fireball_motion(
            origin=(0.0, 20.0, 0.0),
            target=(0.0, 0.0, 20.0),
            owner_id="boss",
            boss_id="boss",
        )
        reflected = logic.reflect_fireball(
            projectile, "alice", (0.0, 0.0, 1.0)
        )
        self.assertEqual((0.0, 0.0, 1.0), reflected["motion"])
        self.assertEqual((0.0, 0.0, 0.1), reflected["acceleration"])

        previous_z = 0.0
        for unused in range(60):
            step = logic.advance_fireball_motion(projectile)
            self.assertLessEqual(step["motion"][1], 0.0)
            self.assertGreater(step["motion"][2], previous_z)
            previous_z = step["motion"][2]

        engine = logic.source_motion_to_engine(step["motion"])
        self.assertAlmostEqual(
            step["motion"][2] * 2.0 / 3.0, engine[2], places=7
        )

        behavior = load_json(
            BP / "entities" / "ur_ghast_fireball.entity.json"
        )["minecraft:entity"]["components"]
        self.assertEqual(1.0, behavior["minecraft:collision_box"]["width"])
        self.assertEqual(1.0, behavior["minecraft:collision_box"]["height"])
        hitbox = behavior["minecraft:custom_hit_test"]["hitboxes"][0]
        self.assertEqual(2.5, hitbox["width"])
        self.assertEqual(2.5, hitbox["height"])
        self.assertEqual([0, 1.25, 0], hitbox["pivot"])
        self.assertEqual(0.0, behavior["minecraft:projectile"]["power"])

    def test_079_server_drives_projectiles_and_uses_source_hurt_clock(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("def _drive_ur_ghast_projectiles", server)
        update = server[server.index("def Update(self):"):]
        update = update[:update.index("\n    def ", 1)]
        self.assertIn("_drive_ur_ghast_projectiles", update)

        reflection = server[server.index("def _reflect_ur_ghast_fireball"):]
        reflection = reflection[:reflection.index("\n    def ", 1)]
        self.assertIn('"ur_ghast.fireball_reflected"', reflection)
        self.assertIn("source_motion_to_engine", reflection)
        self.assertIn('projectile["ignoreWorldUntil"]', reflection)

        protection = server[
            server.index("def _protect_ur_ghast_fireball_health"):
        ]
        protection = protection[:protection.index("\n    def ", 1)]
        self.assertIn("_reflect_ur_ghast_fireball", protection)
        self.assertIn('reason="health_change"', protection)
        self.assertIn("_recover_ur_ghast_fireball_reflector", protection)
        self.assertIn('reason="health_change_recovered"', protection)

        projectile_drive = server[
            server.index("def _drive_ur_ghast_projectiles"):
        ]
        projectile_drive = projectile_drive[
            :projectile_drive.index("\n    def ", 1)
        ]
        self.assertIn("native_motion_reversal", projectile_drive)

        hurt = server[server.index("def _begin_ur_ghast_hurt_feedback"):]
        hurt = hurt[:hurt.index("\n    def ", 1)]
        self.assertIn("hurtUntilLogicTick", hurt)
        self.assertIn("self._ur_ghast_logic_tick", hurt)
        self.assertIn("HURT_FEEDBACK_TICKS", hurt)

    def test_086_reflection_recovery_uses_melee_ray_not_post_contact_motion(self):
        valid = logic.reflection_recovery_score(
            (0.0, 1.62, 3.0),
            (0.0, 0.0, -1.0),
            (0.0, 1.62, 0.0),
            (0.0, 0.0, 1.0),
        )
        self.assertIsNotNone(valid)
        self.assertGreater(valid, 1.0)
        self.assertIsNone(logic.reflection_recovery_score(
            (0.0, 1.62, 3.0),
            (0.0, 0.0, -1.0),
            (0.0, 1.62, 0.0),
            (0.0, 0.0, -1.0),
        ))
        self.assertIsNotNone(logic.reflection_recovery_score(
            (0.0, 1.62, 3.0),
            (0.0, 0.0, 1.0),
            (0.0, 1.62, 0.0),
            (0.0, 0.0, 1.0),
        ))
        self.assertIsNotNone(logic.reflection_recovery_score(
            (0.0, 1.62, -0.75),
            (0.0, 0.0, -1.0),
            (0.0, 1.62, 0.0),
            (0.0, 0.0, 1.0),
        ))
        self.assertIsNone(logic.reflection_recovery_score(
            (2.0, 1.62, 3.0),
            (0.0, 0.0, -1.0),
            (0.0, 1.62, 0.0),
            (0.0, 0.0, 1.0),
        ))
        self.assertIsNone(logic.reflection_recovery_score(
            (0.0, 1.62, 7.0),
            (0.0, 0.0, -1.0),
            (0.0, 1.62, 0.0),
            (0.0, 0.0, 1.0),
        ))

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        recovery = server[
            server.index("def _recover_ur_ghast_fireball_reflector"):
        ]
        recovery = recovery[:recovery.index("\n    def ", 1)]
        self.assertIn("reflection_recovery_score", recovery)
        self.assertIn("self._get_online_players()", recovery)
        self.assertIn('"ur_ghast.fireball_reflector_recovered"', recovery)

    def test_route_ghast_temporal_helpers_cover_warning_cooldown_and_auxiliary_edges(self):
        state = route_mob_logic.create_mob_state("tf_slice:mini_ghast")
        self.assertEqual(
            0,
            route_mob_logic.advance_ghast_attack(
                state, False, False, False
            )["timer"],
        )
        for tick in range(1, 21):
            step = route_mob_logic.advance_ghast_attack(
                state, True, True, True
            )
            if tick == 10:
                self.assertTrue(step["warn"])
        self.assertTrue(step["fire"])
        self.assertEqual(-40, step["timer"])

        self.assertFalse(route_mob_logic.chain_projectile_phase(14)["returning"])
        self.assertTrue(route_mob_logic.chain_projectile_phase(81)["expired"])
        self.assertFalse(
            route_mob_logic.advance_heavy_spear(state, False)["active"]
        )
        self.assertTrue(
            route_mob_logic.rider_spear_freezes_mount(30, True, True)
        )
        route_mob_logic.notify_borer_hurt(state)
        self.assertEqual(
            "wake_borer",
            route_mob_logic.advance_borer_summon(state, "infested")[0]["kind"],
        )
        self.assertEqual(
            "scan_empty",
            route_mob_logic.advance_borer_summon(state, "empty")[0]["kind"],
        )
        self.assertEqual(0, route_mob_logic.broodling_companion_count(False, 1))
        self.assertEqual(2, route_mob_logic.broodling_companion_count(True, 1))

    def test_trap_lifecycle_death_fallback_and_reward_edges_remain_source_owned(self):
        trap = logic.create_trap_state((0, 100, 0))
        self.assertEqual(
            (1.0, 102.0, 3.0),
            logic.resolve_death_position(None, (1, 102, 3)),
        )
        self.assertEqual(
            "tf_slice:mini_ghast",
            logic.resolve_death_entity_type(
                None, None, {"type": "tf_slice:mini_ghast"}
            ),
        )
        self.assertTrue(logic.trap_accepts_mini_ghast_death(trap, (5, 110, 5)))
        self.assertFalse(logic.trap_accepts_mini_ghast_death(trap, (11, 110, 5)))
        for entity_id in ("a", "b", "c"):
            self.assertTrue(logic.record_mini_ghast_death(trap, entity_id))
        self.assertFalse(logic.record_mini_ghast_death(trap, "c"))
        self.assertTrue(logic.activate_trap(trap)["activated"])
        self.assertFalse(logic.activate_trap(trap)["activated"])

        boss = logic.create_state((0, 120, 0), [(0, 100, 0)])
        boss["phase"] = "tantrum"
        boss_hit = logic.apply_active_trap_to_ur_ghast(
            trap, boss, (0, 110, 0), deal_damage=True
        )
        self.assertTrue(boss_hit["affected"])
        self.assertEqual(7.0, boss_hit["damage"])
        ghast_hit = logic.apply_active_trap_to_ghast(
            trap, (0, 110, 0), deal_damage=True
        )
        self.assertEqual(10.0, ghast_hit["damage"])
        self.assertFalse(
            logic.apply_active_trap_to_ghast(trap, (8, 110, 0))["affected"]
        )
        self.assertFalse(logic.advance_trap(trap, 120)["active"])

        home_before = list(boss["home"])
        death = logic.advance_death_sequence(boss, 2)
        self.assertEqual(2, death["deathTicks"])
        self.assertEqual("burst", death["stage"])
        self.assertEqual(home_before, boss["home"])
        boss["health"] = 0.0
        boss["participants"] = ["bob", "alice", "bob"]
        self.assertTrue(logic.claim_reward(boss))
        self.assertFalse(logic.claim_reward(boss))
        self.assertEqual(["alice", "bob"], logic.final_progress_players(boss))

    def test_flight_control_accelerates_existing_motion_on_source_cooldown(self):
        state = logic.create_state((0, 200, 0), [])

        first = logic.advance_flight_motion(
            state,
            position=(0.0, 200.0, 0.0),
            wanted=(10.0, 200.0, 0.0),
            current_motion=(0.02, 0.0, 0.0),
            cooldown_roll=0,
        )

        self.assertTrue(first["accelerated"])
        self.assertAlmostEqual(
            (0.02 + logic.FLIGHT_ACCELERATION) * logic.FLIGHT_DRAG,
            first["motion"][0],
            places=7,
        )
        self.assertEqual((0.0, 0.0), first["motion"][1:])
        self.assertEqual(2, first["courseChangeCooldown"])

        second = logic.advance_flight_motion(
            state,
            position=(0.0, 200.0, 0.0),
            wanted=(10.0, 200.0, 0.0),
            current_motion=first["motion"],
            cooldown_roll=4,
        )

        self.assertFalse(second["accelerated"])
        self.assertLess(second["motion"][0], first["motion"][0])
        self.assertEqual(1, second["courseChangeCooldown"])

    def test_bedrock_flight_adapter_stays_bounded_for_twelve_hundred_ticks(self):
        state = logic.create_state((0, 200, 0), [])
        position = [0.0, 200.0, 0.0]
        motion = (0.0, 0.0, 0.0)
        wanted = (20.0, 200.0, 0.0)
        peak_speed = 0.0
        reached = False

        for tick in range(1200):
            event = logic.advance_flight_motion(
                state,
                position=position,
                wanted=wanted,
                current_motion=motion,
                cooldown_roll=tick % logic.FLIGHT_COURSE_COOLDOWN_SPREAD,
            )
            motion = event["motion"]
            position = [position[index] + motion[index] for index in range(3)]
            peak_speed = max(
                peak_speed,
                math.sqrt(sum(value * value for value in motion)),
            )
            reached = reached or abs(position[0] - wanted[0]) <= 1.0

        self.assertTrue(reached)
        self.assertLessEqual(
            peak_speed, logic.FLIGHT_CORRUPT_SPEED_LIMIT + 1.0e-9
        )
        self.assertLessEqual(abs(position[0] - wanted[0]), 1.0)
        self.assertEqual((0.0, 0.0, 0.0), motion)

    def test_bedrock_flight_stall_clears_waypoint_after_ten_ticks(self):
        state = logic.create_state((0, 200, 0), [])
        state["wantedWaypoint"] = [20.0, 200.0, 0.0]
        event = None
        for tick in range(logic.FLIGHT_STALL_TICKS + 1):
            event = logic.advance_flight_motion(
                state,
                position=(0.0, 200.0, 0.0),
                wanted=(20.0, 200.0, 0.0),
                current_motion=(0.2, 0.0, 0.0),
                cooldown_roll=tick,
            )

        self.assertTrue(event["reselectWaypoint"])
        self.assertEqual(
            [0.0, 200.0, -20.0],
            event["recoveryWaypoint"],
        )
        self.assertEqual(event["recoveryWaypoint"], state["wantedWaypoint"])
        self.assertEqual((0.0, 0.0, 0.0), event["motion"])

    def test_arrival_resets_stall_without_creating_a_recovery_waypoint(self):
        state = logic.create_state((0, 200, 0), [])
        state["flightStallTicks"] = logic.FLIGHT_STALL_TICKS - 1

        event = logic.advance_flight_motion(
            state,
            position=(19.75, 200.0, 0.0),
            wanted=(20.0, 200.0, 0.0),
            current_motion=(0.0, 0.0, 0.0),
            cooldown_roll=0,
        )

        self.assertTrue(event["arrived"])
        self.assertEqual(0, state["flightStallTicks"])
        self.assertNotIn("recoveryWaypoint", event)

    def test_exhausted_route_recovery_moves_laterally_inside_altitude_band(self):
        state = logic.create_state(
            (0, 200, 0),
            [],
            waypoints=((20, 200, 0), (-20, 200, 0)),
        )
        first = logic.select_recovery_waypoint(
            state, (0, 200, 0), (20, 200, 0)
        )
        second = logic.select_recovery_waypoint(
            state, (0, 200, 0), first
        )

        self.assertEqual([-20.0, 200.0, 0.0], first)
        self.assertEqual([8.0, 200.0, 0.0], second)
        floor_y, ceiling_y = logic.flight_altitude_bounds(state)
        self.assertGreaterEqual(second[1], floor_y)
        self.assertLessEqual(second[1], ceiling_y)

    def test_ghast_render_bodies_stay_upright_and_server_facing_is_yaw_only(self):
        animations = load_json(
            RP / "animations" / "phantom_urghast_route.animation.json"
        )["animations"]
        for identifier in ("mini_ghast", "tower_ghast", "ur_ghast"):
            bones = animations["animation.tf_slice.%s.move" % identifier]["bones"]
            self.assertNotIn("body", bones, identifier)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        drive = server[server.index("def _drive_ur_ghasts"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertIn("_set_ur_ghast_logical_yaw", drive)
        self.assertNotIn("self._face_position(", drive)
        self.assertIn("advance_flight_motion", drive)
        self.assertNotIn("dx / length * 0.25", drive)

    def test_ur_ghast_weather_uses_normal_rain_not_acid_progression_texture(self):
        self.assertFalse((RP / "particles" / "ur_ghast_rain.json").exists())
        tear_path = RP / "particles" / "ur_ghast_tear.json"
        self.assertTrue(tear_path.exists())
        tear = load_json(tear_path)["particle_effect"]
        self.assertEqual(
            "tf_slice:ur_ghast_tear",
            tear["description"]["identifier"],
        )
        self.assertEqual(
            "textures/items/fiery_tears",
            tear["description"]["basic_render_parameters"]["texture"],
        )
        components = tear["components"]
        self.assertEqual(
            [0.4, 0.54],
            components["minecraft:particle_appearance_billboard"]["size"],
        )
        self.assertEqual(
            -1.0,
            components["minecraft:emitter_shape_point"]["direction"][1],
        )
        self.assertEqual(2.0, components["minecraft:particle_initial_speed"])
        self.assertEqual(
            -3.0,
            components["minecraft:particle_motion_dynamic"]
            ["linear_acceleration"][1],
        )
        self.assertEqual(
            0.02,
            components["minecraft:particle_motion_dynamic"]
            ["linear_drag_coefficient"],
        )
        self.assertEqual(
            "Math.random(3.2, 4.0)",
            components["minecraft:particle_lifetime_expression"]
            ["max_lifetime"],
        )
        minimum_fall = 2.0 * 3.2 + 0.5 * 3.0 * 3.2 * 3.2
        self.assertGreaterEqual(minimum_fall, 20.0)
        self.assertLessEqual(16 * 2 * 4.0, 128.0)

        builder = (
            ROOT / "tools" / "build_ur_ghast_effect_assets.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"bigrain.png"', builder)
        self.assertNotIn('"textures/environment/rain"', builder)
        self.assertNotIn("ur_ghast_rain.json", builder)
        self.assertIn("ur_ghast_tear.json", builder)
        self.assertIn("textures/items/fiery_tears", builder)

        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        tick = client[client.index("def OnScriptTickClient"):]
        tick = tick[:tick.index("\n    def ", 1)]
        self.assertNotIn("_update_ur_ghast_weather", tick)
        effect = client[client.index("def OnUrGhastEffect"):]
        effect = effect[:effect.index("\n    def ", 1)]
        tear_branch = effect[effect.index('if kind == "tear"'):]
        tear_branch = tear_branch[:tear_branch.index("            return")]
        self.assertIn("tf_slice:ur_ghast_tear", tear_branch)
        self.assertNotIn("minecraft:water_splash_particle_manual", tear_branch)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        native = server[server.index("def _update_ur_ghast_native_weather"):]
        native = native[:native.index("\n    def ", 1)]
        for api_name in (
            "SetDimensionUseLocalWeather",
            "SetDimensionLocalRain",
            "SetDimensionLocalThunder",
            "SetDimensionLocalDoWeatherCycle",
        ):
            self.assertIn(api_name, native)
        drive = server[server.index("def _drive_ur_ghasts"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertNotIn("_update_ur_ghast_native_weather", drive)
        update = server[server.index("def Update(self):"):]
        update = update[:update.index("\n    def ", 1)]
        self.assertIn("_update_ur_ghast_native_weather", update)

    def test_acceptance_evidence_does_not_pin_removed_weather_particles(self):
        removed = {"TwilightBossSliceR/particles/ur_ghast_rain.json"}
        tear = "TwilightBossSliceR/particles/ur_ghast_tear.json"
        behavior = load_json(
            ROOT / "model_acceptance" / "behavior" / "ur_ghast.json"
        )
        self.assertTrue(
            removed.isdisjoint(behavior.get("production_hashes", {}))
        )
        self.assertIn(tear, behavior.get("production_hashes", {}))

        boss = load_json(ROOT / "boss_acceptance" / "ur_ghast.json")
        recorded_paths = {
            row.get("path")
            for track in boss.get("tracks", {}).values()
            for row in track.get("production_hashes", [])
            if isinstance(row, dict)
        }
        self.assertTrue(removed.isdisjoint(recorded_paths))
        self.assertIn(tear, recorded_paths)
        retired_trophy = (
            "TwilightBossSliceB/items/ur_ghast_trophy.item.json"
        )
        trophy_block = (
            "TwilightBossSliceB/netease_blocks/ur_ghast_trophy.json"
        )
        self.assertNotIn(retired_trophy, recorded_paths)
        self.assertIn(trophy_block, recorded_paths)

        generator = (
            ROOT / "tools" / "build_phantom_urghast_acceptance.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(retired_trophy, generator)
        self.assertIn(trophy_block, generator)

    def test_script_owns_ghastling_attack_and_active_trap_clears_target(self):
        for identifier in ("mini_ghast", "tower_ghast"):
            entity = load_json(BP / "entities" / (identifier + ".entity.json"))[
                "minecraft:entity"
            ]
            components = entity["components"]
            self.assertNotIn("minecraft:shooter", components)
            self.assertNotIn("minecraft:behavior.ranged_attack", components)
            self.assertIn("tf_slice:charging", entity["description"]["properties"])
            self.assertIn("tf_slice:start_charging", entity["events"])
            self.assertIn("tf_slice:stop_charging", entity["events"])

        render = load_json(
            RP / "render_controllers" / "phantom_urghast_route.render.json"
        )["render_controllers"]["controller.render.tf_slice.route_ghast"]
        self.assertIn("query.property('tf_slice:charging')", render["textures"][0])
        self.assertNotIn("query.is_charging", render["textures"][0])

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        drive = server[server.index("def _drive_phantom_urghast_mobs"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertIn("advance_ghast_attack", drive)
        self.assertIn("_reset_attack_target", drive)
        self.assertIn("_drive_route_ghast_attack", drive)
        attack = server[server.index("def _drive_route_ghast_attack"):]
        attack = attack[:attack.index("\n    def ", 1)]
        self.assertIn("_spawn_route_ghast_fireball", attack)

    def test_boss_minion_mode_is_applied_to_tantrum_spawns(self):
        entity = load_json(BP / "entities" / "mini_ghast.entity.json")[
            "minecraft:entity"
        ]
        group = entity["component_groups"]["tf_slice:boss_minion"]
        self.assertEqual(
            {"value": 6, "max": 6}, group["minecraft:health"]
        )
        self.assertIn("tf_slice:make_boss_minion", entity["events"])

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        spawn = server[server.index("def _spawn_ur_ghast_tantrum_minions"):]
        spawn = spawn[:spawn.index("\n    def ", 1)]
        self.assertIn("tf_slice:make_boss_minion", spawn)
        self.assertIn('"bossMinion"', spawn)

    def test_ghastling_gaze_and_pumpkin_gate_match_source_boundaries(self):
        self.assertFalse(
            route_mob_logic.mini_ghast_should_attack(
                distance=2.0,
                look_dot=1.0,
                has_sight=True,
                wearing_pumpkin=True,
            )
        )
        self.assertTrue(
            route_mob_logic.mini_ghast_should_attack(
                distance=3.5,
                look_dot=-1.0,
                has_sight=True,
                wearing_pumpkin=False,
            )
        )
        self.assertFalse(
            route_mob_logic.mini_ghast_should_attack(
                distance=10.0,
                look_dot=0.99,
                has_sight=False,
                wearing_pumpkin=False,
            )
        )
        self.assertTrue(
            route_mob_logic.mini_ghast_should_attack(
                distance=10.0,
                look_dot=0.999,
                has_sight=True,
                wearing_pumpkin=False,
            )
        )

    def test_ur_ghast_volley_uses_owned_non_griefing_custom_projectile(self):
        behavior = load_json(
            BP / "entities" / "ur_ghast_fireball.entity.json"
        )["minecraft:entity"]
        projectile = behavior["components"]["minecraft:projectile"]
        self.assertEqual(
            {
                "value": int(logic.FIREBALL_HEALTH),
                "max": int(logic.FIREBALL_HEALTH),
            },
            behavior["components"]["minecraft:health"],
        )
        self.assertIn(
            "mob",
            behavior["components"]["minecraft:type_family"]["family"],
        )
        self.assertEqual(
            0, projectile["on_hit"]["impact_damage"]["damage"]
        )
        explosion = behavior["component_groups"]["tf_slice:explode"][
            "minecraft:explode"
        ]
        self.assertEqual(1, explosion["power"])
        self.assertFalse(explosion["breaks_blocks"])
        self.assertFalse(explosion["causes_fire"])

        client = load_json(
            RP / "entity" / "ur_ghast_fireball.entity.json"
        )["minecraft:client_entity"]["description"]
        self.assertEqual("fireball", client["materials"]["default"])
        self.assertEqual("textures/items/fireball", client["textures"]["default"])
        self.assertEqual(
            "geometry.fireball",
            client["geometry"]["default"],
        )
        self.assertEqual(
            "animation.actor.billboard", client["animations"]["face_player"]
        )
        self.assertEqual(
            ["controller.render.fireball"],
            client["render_controllers"],
        )

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        volley = server[server.index("def _spawn_ur_ghast_volley"):]
        volley = volley[:volley.index("\n    def ", 1)]
        self.assertIn("UR_GHAST_FIREBALL_IDENTIFIER", volley)
        self.assertNotIn('"minecraft:fireball"', volley)
        self.assertIn("self._ur_ghast_projectiles", volley)
        hit = server[server.index("def OnProjectileDoHitEffectEvent"):]
        hit = hit[:hit.index("\n    def ", 1)]
        self.assertIn("FIREBALL_DIRECT_DAMAGE", hit)
        self.assertIn('"tf_slice:explode"', hit)

        player_attack = server[server.index("def OnPlayerAttackEntityEvent"):]
        player_attack = player_attack[:player_attack.index("\n    def ", 1)]
        self.assertIn("_reflect_ur_ghast_fireball", player_attack)
        self.assertIn("_ur_ghast_projectiles", player_attack)

    def test_trap_fallback_scan_is_throttled_and_absorption_prefers_registry(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        traps = server[server.index("def _update_ghast_traps"):]
        traps = traps[:traps.index("\n    def ", 1)]
        self.assertIn("TRAP_FALLBACK_SCAN_INTERVAL", traps)
        absorb = server[server.index("def _ur_ghast_absorb_nearby_minions"):]
        absorb = absorb[:absorb.index("\n    def ", 1)]
        self.assertIn("self._phantom_urghast_mobs", absorb)
        self.assertNotIn("GetEntitiesInSquareArea", absorb)
        attack = server[server.index("def _drive_route_ghast_attack"):]
        attack = attack[:attack.index("\n    def ", 1)]
        self.assertIn("GHAST_PERCEPTION_REFRESH_INTERVAL", attack)
        self.assertIn("ghastPerceptionNextTick", attack)
        self.assertIn("_ghast_player_perception", attack)

    def test_locked_reward_pools_and_experience_replace_placeholder_banner(self):
        loot = load_json(
            BP / "loot_tables" / "chests" / "tf_slice" / "ur_ghast_reward.json"
        )
        self.assertEqual(3, len(loot["pools"]))
        self.assertEqual([4, 2, 1], [pool["rolls"] for pool in loot["pools"]])
        entries = [pool["entries"][0] for pool in loot["pools"]]
        self.assertEqual(
            [
                "tf_slice:carminite",
                "tf_slice:fiery_tears",
                "tf_slice:ur_ghast_trophy_item",
            ],
            [entry["name"] for entry in entries],
        )
        self.assertNotIn("ur_ghast_banner", json.dumps(loot))
        self.assertEqual(
            {"min": 1, "max": 3}, entries[0]["functions"][0]["count"]
        )
        self.assertEqual(
            {"min": 1, "max": 5}, entries[1]["functions"][0]["count"]
        )
        self.assertEqual(317, logic.XP_REWARD)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        finalizer = server[server.index("def _finalize_ur_ghast"):]
        finalizer = finalizer[:finalizer.index("\n    def ", 1)]
        self.assertIn("_spawn_route_boss_experience", finalizer)
        self.assertIn("ur_ghast_logic.XP_REWARD", finalizer)

    def test_external_melee_and_ranged_hit_test_matches_visible_head_body(self):
        components = load_json(BP / "entities" / "ur_ghast.entity.json")[
            "minecraft:entity"
        ]["components"]

        self.assertEqual(
            {"width": 14.0, "height": 18.0},
            components["minecraft:collision_box"],
        )
        self.assertEqual(
            [{"width": 12.5, "height": 12.5, "pivot": [0, 12.5, 0]}],
            components["minecraft:custom_hit_test"]["hitboxes"],
        )

    def test_zeroed_collision_motion_still_triggers_stall_reselection(self):
        state = logic.create_state((0, 200, 0), [])
        state["wantedWaypoint"] = [20.0, 200.0, 0.0]
        event = None
        for tick in range(logic.FLIGHT_STALL_TICKS + 1):
            event = logic.advance_flight_motion(
                state,
                position=(0.0, 200.0, 0.0),
                wanted=(20.0, 200.0, 0.0),
                current_motion=(0.0, 0.0, 0.0),
                cooldown_roll=tick,
            )

        self.assertTrue(event["reselectWaypoint"])
        self.assertEqual(
            [0.0, 200.0, -20.0],
            event["recoveryWaypoint"],
        )
        self.assertEqual(event["recoveryWaypoint"], state["wantedWaypoint"])

    def test_respawn_invalidates_route_hud_and_pushes_full_boss_snapshot(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        respawn = server[server.index("def OnRoutePlayerRespawn"):]
        respawn = respawn[:respawn.index("\n    def ", 1)]
        self.assertIn('"BossHudReset"', respawn)
        self.assertIn('"BossSync"', respawn)
        self.assertIn("_make_sync_packet(playerId)", respawn)
        self.assertLess(
            respawn.index('"BossHudReset"'),
            respawn.index("snapshot ="),
        )

        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        self.assertIn('"BossHudReset"', client)
        handler = client[client.index("def OnBossHudReset"):]
        handler = handler[:handler.index("\n    def ", 1)]
        self.assertIn("routeBossHudUI.invalidate()", handler)
        self.assertIn("_ur_ghast_boss_hud_node = None", handler)

    def test_native_weather_uses_rain_with_visual_only_thunder(self):
        import ur_ghast_effect_logic as effects

        self.assertEqual(
            {"rain": 1.0, "thunder": 0.0},
            effects.native_weather_levels(True),
        )
        self.assertEqual(
            {"rain": 0.0, "thunder": 0.0},
            effects.native_weather_levels(False),
        )

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        native = server[server.index("def _update_ur_ghast_native_weather"):]
        native = native[:native.index("\n    def ", 1)]
        self.assertIn("native_weather_levels", native)
        self.assertIn('levels["rain"]', native)
        self.assertIn('levels["thunder"]', native)

    def test_boss_is_fire_immune_and_existing_fire_is_cleared_on_register(self):
        components = load_json(BP / "entities" / "ur_ghast.entity.json")[
            "minecraft:entity"
        ]["components"]
        self.assertIn("minecraft:fire_immune", components)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        register = server[server.index("def _register_ur_ghast"):]
        register = register[:register.index("\n    def ", 1)]
        self.assertIn("SetEntityOnFire(0, 0)", register)

    def test_new_volley_grants_owner_contact_grace_before_any_explosion(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        volley = server[server.index("def _spawn_ur_ghast_volley"):]
        volley = volley[:volley.index("\n    def ", 1)]
        self.assertIn(
            "self._tick + ur_ghast_logic.FIREBALL_OWNER_IGNORE_TICKS",
            volley,
        )

        hit = server[server.index("def OnProjectileDoHitEffectEvent"):]
        hit = hit[:hit.index("\n    def ", 1)]
        owner_guard = hit.index("fireball_collision_decision")
        explosion = hit.index('"tf_slice:explode"')
        self.assertLess(owner_guard, explosion)

    def test_every_matching_trap_observes_one_minion_death(self):
        first = logic.create_trap_state((0, 100, 0))
        second = logic.create_trap_state((4, 100, 0))
        outside = logic.create_trap_state((40, 100, 0))

        charged = logic.record_mini_ghast_death_for_traps(
            (first, second, outside),
            "minion-1",
            (2, 102, 0),
        )

        self.assertEqual([first, second], charged)
        self.assertEqual([1, 1, 0], [
            first["deathCount"], second["deathCount"], outside["deathCount"]
        ])
        self.assertEqual([], logic.record_mini_ghast_death_for_traps(
            (first, second), "minion-1", (2, 102, 0)
        ))

    def test_block_griefing_matrix_separates_boss_and_minion_fireballs(self):
        boss_fireball = load_json(
            BP / "entities" / "ur_ghast_fireball.entity.json"
        )["minecraft:entity"]
        explosion = boss_fireball["component_groups"]["tf_slice:explode"][
            "minecraft:explode"
        ]
        self.assertFalse(explosion["breaks_blocks"])
        self.assertFalse(explosion["causes_fire"])

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        minion = server[server.index("def _spawn_route_ghast_fireball"):]
        minion = minion[:minion.index("\n    def ", 1)]
        self.assertIn('"minecraft:fireball"', minion)
        self.assertNotIn("UR_GHAST_FIREBALL_IDENTIFIER", minion)

        trap = load_json(BP / "netease_blocks" / "ghast_trap.json")
        components = trap["minecraft:block"]["components"]
        self.assertIs(False, components["minecraft:destructible_by_explosion"])

    def test_runtime_adapter_owns_source_clock_trap_targets_and_direct_facing(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        update = server[server.index("def Update(self):"):]
        update = update[:update.index("\n    def ", 1)]
        self.assertIn("advance_source_clock", update)
        self.assertIn("_ur_ghast_logic_step", update)
        self.assertLess(
            update.index('trap["_effectTargets"] = []'),
            update.index(
                "_drive_phantom_urghast_mobs(self._ur_ghast_logic_step)"
            ),
        )
        self.assertLess(
            update.index("self._drive_ur_ghasts()"),
            update.index("self._update_ghast_traps()"),
        )

        facing = server[server.index("def _face_yaw_position"):]
        facing = facing[:facing.index("\n    def ", 1)]
        self.assertIn("SetRot((0.0, targetYaw))", facing)
        self.assertNotIn("step_yaw", facing)

        trap_effect = server[server.index("def _broadcast_ghast_trap_effect"):]
        trap_effect = trap_effect[:trap_effect.index("\n    def ", 1)]
        self.assertIn('"targetPositions"', trap_effect)

        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        handler = client[client.index("def OnGhastTrapEffect"):]
        handler = handler[:handler.index("\n    def ", 1)]
        self.assertIn('args.get("targetPositions"', handler)
        self.assertIn("range(6)", handler)

    def test_ur_ghast_damage_attribution_and_hud_use_encounter_scope(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        attack = server[server.index("def OnPlayerAttackEntityEvent"):]
        attack = attack[:attack.index("\n    def ", 1)]
        self.assertIn("_remember_ur_ghast_player_attack", attack)

        resolver = server[server.index("def _resolve_ur_ghast_damage"):]
        resolver = resolver[:resolver.index("\n    def ", 1)]
        self.assertIn("_ur_ghast_damage_owner", resolver)
        self.assertIn("_boss_sync_dirty = True", resolver)

        config = (PACKAGE / "config.py").read_text(encoding="utf-8")
        self.assertIn("UR_GHAST_HUD_RANGE = 128.0", config)
        packet = server[server.index("def _make_sync_packet"):]
        packet = packet[:packet.index("\n    def ", 1)]
        self.assertIn("UR_GHAST_HUD_RANGE", packet)
        self.assertIn('state.get("home")', packet)

        drive = server[server.index("def _drive_ur_ghasts"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertNotIn(
            "ur_ghast_logic.record_participant(state, targetId)", drive
        )

    def test_live_trap_route_refresh_is_bounded_and_source_throttled(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        discovery = server[server.index("def _ur_ghast_route_trap_points"):]
        discovery = discovery[:discovery.index("\n    def ", 1)]
        self.assertIn("ur_ghast_logic.HOME_RADIUS", discovery)
        self.assertIn("_ur_ghast_trap_block_valid", discovery)
        self.assertIn("self._ghast_traps.values()", discovery)

        ticking = server[server.index("def _tick_ur_ghast_trap_route"):]
        ticking = ticking[:ticking.index("\n    def ", 1)]
        self.assertIn("TRAP_PRUNE_INTERVAL", ticking)
        self.assertIn("TRAP_DISCOVERY_INTERVAL", ticking)
        self.assertIn("_refresh_ur_ghast_route", ticking)

    def test_damage_resolution_traces_raw_effective_and_phase_remaining(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        resolver = server[server.index("def _resolve_ur_ghast_damage"):]
        resolver = resolver[:resolver.index("\n    def ", 1)]
        self.assertIn('"ur_ghast.damage"', resolver)
        for field in (
            "rawDamage",
            "effectiveDamage",
            "damageUntilNextPhase",
            "phaseToggled",
        ):
            self.assertIn(field, resolver)

    def test_downward_volley_uses_full_source_view_spawn(self):
        shots = logic.fireball_volley(
            (0.0, 271.0, 0.0),
            (0.0, 251.9, 0.0),
            spread_offsets=((2.0, -3.0), (-4.0, 1.0)),
            facing_yaw=0.0,
        )

        self.assertEqual(3, len(shots))
        self.assertAlmostEqual(272.49, shots[0]["origin"][1], places=2)
        self.assertEqual([1.1, 271.5, 0.0], shots[1]["origin"])
        self.assertEqual([-1.1, 271.5, 0.0], shots[2]["origin"])
        for shot in shots:
            boss_center = (0.0, 280.0, 0.0)
            distance = math.sqrt(
                sum(
                    (shot["origin"][index] - boss_center[index]) ** 2
                    for index in range(3)
                )
            )
            self.assertGreater(
                distance,
                logic.BOSS_WIDTH / 2.0 + logic.FIREBALL_RADIUS,
            )

    def test_projectile_owner_registration_precedes_motion(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        volley = server[server.index("def _spawn_ur_ghast_volley"):]
        volley = volley[:volley.index("\n    def ", 1)]

        self.assertIn("facing_yaw", volley)
        self.assertLess(
            volley.index("self._ur_ghast_projectiles[str(projectileId)]"),
            volley.index("self._set_full_motion("),
        )
        self.assertIn('"fireball_launch"', volley)

        hit = server[server.index("def OnProjectileDoHitEffectEvent"):]
        hit = hit[:hit.index("\n    def ", 1)]
        self.assertIn("projectile.get(\"ownerId\")", hit)
        self.assertIn("impactTick", hit)
        self.assertIn('"fireball_impact"', hit)
        self.assertIn("fireball_collision_decision", hit)
        self.assertIn("UR_GHAST_FIREBALL_IDENTIFIER", hit)

        removed = server[server.index("def OnRemoveEntity"):]
        removed = removed[:removed.index("\n    def ", 1)]
        self.assertIn("_ur_ghast_projectile_tombstones", removed)

    def test_ur_ghast_damage_cancels_native_settlement_before_logic(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        resolver = server[server.index("def _resolve_ur_ghast_damage"):]
        resolver = resolver[:resolver.index("\n    def ", 1)]

        self.assertIn('args["cancel"] = True', resolver)
        self.assertLess(
            resolver.index('args["cancel"] = True'),
            resolver.index("ur_ghast_logic.apply_damage("),
        )
        self.assertIn("_ur_ghast_internal_health_write", resolver)
        self.assertIn("args", resolver)
        self.assertIn("engineHealthBefore", resolver)
        self.assertIn("engineHealthAfter", resolver)
        owned = server[server.index("def _ur_ghast_owned_damage_source"):]
        owned = owned[:owned.index("\n    def ", 1)]
        self.assertIn("_ur_ghast_projectile_tombstones", owned)
        self.assertIn("impactTick", owned)

        absorb = server[server.index("def _ur_ghast_absorb_nearby_minions"):]
        absorb = absorb[:absorb.index("\n    def ", 1)]
        self.assertIn("_set_ur_ghast_engine_health", absorb)
        drive = server[server.index("def _drive_ur_ghasts"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertIn("_set_ur_ghast_engine_health", drive)
        self.assertIn("_reconcile_ur_ghast_engine_health", drive)

    def test_positive_authoritative_health_rejects_premature_mobdie(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        mob_die = server[server.index("def OnMobDie"):]
        mob_die = mob_die[:mob_die.index("\n    def ", 1)]
        ur_branch = mob_die[mob_die.index("if urKey is not None:"):]
        ur_branch = ur_branch[:ur_branch.index("        partKey =", 1)]

        self.assertIn("premature", ur_branch)
        self.assertIn("state.get(\"health\"", ur_branch)
        self.assertIn("_recover_premature_ur_ghast_death", ur_branch)
        self.assertNotIn('state["health"] = 0.0', ur_branch)

        removed = server[server.index("def OnRemoveEntity"):]
        removed = removed[:removed.index("\n    def ", 1)]
        self.assertNotIn("_recover_premature_ur_ghast_death", removed)
        self.assertIn("self._on_boss_actor_removed(", removed)

    def test_ur_ghast_uses_noclip_and_vanilla_fireball_rendering(self):
        components = load_json(BP / "entities" / "ur_ghast.entity.json")[
            "minecraft:entity"
        ]["components"]
        self.assertFalse(components["minecraft:physics"]["has_collision"])

        client = load_json(
            RP / "entity" / "ur_ghast_fireball.entity.json"
        )["minecraft:client_entity"]["description"]
        self.assertEqual(
            "geometry.fireball",
            client["geometry"]["default"],
        )
        self.assertEqual(
            ["controller.render.fireball"],
            client["render_controllers"],
        )
        self.assertEqual(
            "fireball", client["materials"]["default"]
        )

    def test_trap_neighbor_coordinates_and_power_avoid_custom_block_probe(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        adapter = server[server.index("def _block_event_position"):]
        adapter = adapter[:adapter.index("\n    def ", 1)]
        for field in ("blockX", "posX", "position"):
            self.assertIn(field, adapter)

        powered = server[server.index("def _ghast_trap_powered"):]
        powered = powered[:powered.index("\n    def ", 1)]
        self.assertIn("redstone_wire", powered)
        self.assertNotIn("GetBlockPoweredState", powered)

        neighbor = server[server.index("def OnBlockNeighborChanged"):]
        neighbor = neighbor[:neighbor.index("\n    def ", 1)]
        self.assertIn("_block_event_position", neighbor)
        self.assertIn("_ghast_trap_powered", neighbor)

    def test_charge_visual_and_motion_yaw_have_runtime_holds(self):
        state = logic.create_state((0, 200, 0), [])
        visual_ticks = []
        for unused in range(26):
            event = logic.advance_attack(state, True, 16.0, True)
            visual_ticks.append(bool(event.get("visualCharging")))

        self.assertEqual(10, sum(visual_ticks))
        self.assertFalse(visual_ticks[9])
        self.assertTrue(visual_ticks[19])
        self.assertFalse(visual_ticks[20])
        self.assertFalse(visual_ticks[25])

        self.assertEqual(0.0, logic.yaw_for_motion((0.0, 0.0, 1.0), 90.0))
        self.assertEqual(-90.0, logic.yaw_for_motion((1.0, 0.0, 0.0), 0.0))

    def test_player_is_ejected_from_visible_head_not_tentacles(self):
        boss = (0.0, 200.0, 0.0)
        self.assertIsNone(
            logic.player_head_separation(boss, (0.0, 202.0, 0.0))
        )
        separated = logic.player_head_separation(
            boss, (0.0, 207.0, 0.0)
        )
        self.assertIsNotNone(separated)
        self.assertEqual(207.0, separated[1])
        self.assertGreater(
            max(abs(separated[0]), abs(separated[2])),
            logic.BOSS_HEAD_HALF_WIDTH,
        )

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        drive = server[server.index("def _drive_ur_ghasts"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertIn("_separate_players_from_ur_ghast_head", drive)
        self.assertIn("yaw_for_motion", drive)
        self.assertIn("lastValidYaw", drive)

    def test_trap_charge_activation_and_pull_are_diagnostic(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        mob_die = server[server.index("def OnMobDie"):]
        mob_die = mob_die[:mob_die.index("\n    def ", 1)]
        self.assertIn('"ur_ghast.trap_charge"', mob_die)

        activation = server[server.index("def _activate_ghast_trap"):]
        activation = activation[:activation.index("\n    def ", 1)]
        self.assertIn('"ur_ghast.trap_activation"', activation)

        pull = server[server.index("def _update_ghast_traps"):]
        pull = pull[:pull.index("\n    def ", 1)]
        self.assertIn('"ur_ghast.trap_pull"', pull)
        self.assertIn('"charged"', pull)

        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        effect = client[client.index("def OnGhastTrapEffect"):]
        effect = effect[:effect.index("\n    def ", 1)]
        self.assertIn('kind == "charged"', effect)

        ur_effect = client[client.index("def OnUrGhastEffect"):]
        ur_effect = ur_effect[:ur_effect.index("\n    def ", 1)]
        self.assertIn('kind == "fireball_launch"', ur_effect)
        self.assertIn('kind == "fireball_impact"', ur_effect)

    def test_fireball_collision_ignores_siblings_and_original_owner(self):
        projectile = {
            "bossId": "boss",
            "ownerId": "boss",
            "reflected": False,
            "ignoreOwnerUntil": 4,
        }
        self.assertEqual(
            "ignore_projectile",
            logic.fireball_collision_decision(
                projectile, "sibling", True, 100
            ),
        )
        self.assertEqual(
            "ignore_original_boss",
            logic.fireball_collision_decision(
                projectile, "boss", False, 100
            ),
        )
        projectile["ownerId"] = "player"
        projectile["reflected"] = True
        projectile["ignoreOwnerUntil"] = 104
        projectile["ignoreWorldUntil"] = 104
        self.assertEqual(
            "ignore_current_owner",
            logic.fireball_collision_decision(
                projectile, "player", False, 102
            ),
        )
        self.assertEqual(
            "impact",
            logic.fireball_collision_decision(
                projectile, "boss", False, 102
            ),
        )
        self.assertEqual(
            "ignore_reflected_world_grace",
            logic.fireball_collision_decision(
                projectile, -1, False, 102
            ),
        )
        self.assertEqual(
            "impact",
            logic.fireball_collision_decision(
                projectile, -1, False, 105
            ),
        )

    def test_active_trap_rejects_new_charge_and_suppresses_target(self):
        trap = logic.create_trap_state((0, 100, 0))
        trap["active"] = True
        self.assertEqual(
            [],
            logic.record_mini_ghast_death_for_traps(
                (trap,), "late-minion", (0, 101, 0)
            ),
        )
        self.assertEqual(0, trap["deathCount"])

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        drive = server[server.index("def _drive_ur_ghasts"):]
        drive = drive[:drive.index("\n    def ", 1)]
        active = drive[drive.index("if activeTrap is not None:"):]
        active = active[:active.index("            continue", 1)]
        self.assertIn('state["targetId"] = None', active)
        self.assertIn("_reset_attack_target", active)
        self.assertIn("yaw_for_motion", active)
        self.assertIn("_set_ur_ghast_logical_yaw", active)
        self.assertIn("suppressTarget", drive)

    def test_visual_delivery_retries_with_locked_model_forward_axis(self):
        self.assertEqual(0.0, logic.render_yaw(0.0))
        self.assertEqual(90.0, logic.render_yaw(90.0))
        self.assertEqual(-90.0, logic.render_yaw(-90.0))
        self.assertAlmostEqual(178.53, logic.render_yaw(178.53), places=5)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        visual = server[server.index("def _sync_ur_ghast_visual"):]
        visual = visual[:visual.index("\n    def ", 1)]
        self.assertIn("_set_entity_property", visual)
        self.assertIn("tf_slice:attack_state", visual)
        self.assertIn("if applied", visual)

        yaw = server[server.index("def _set_ur_ghast_logical_yaw"):]
        yaw = yaw[:yaw.index("\n    def ", 1)]
        self.assertIn("ur_ghast_logic.render_yaw", yaw)
        self.assertIn("SetRot", yaw)

        typed = server[server.index("def _set_entity_property"):]
        typed = typed[:typed.index("\n    def ", 1)]
        # Bool values must reach the engine without string conversion; the
        # real adapter boundary is covered by test_goblin_combat_runtime.
        self.assertIn("SetPropertyValue(propertyName, encoded)", typed)

    def test_invalid_spawn_ids_and_redstone_polling_fail_closed(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        spawn = server[server.index("def _spawn_ruin_entity"):]
        spawn = spawn[:spawn.index("\n    def ", 1)]
        self.assertIn("_valid_entity_id", spawn)
        self.assertIn("return None", spawn)

        event = server[server.index("def _trigger_entity_event"):]
        event = event[:event.index("\n    def ", 1)]
        self.assertIn("_valid_entity_id", event)

        powered = server[server.index("def _fire_swamp_device_powered"):]
        powered = powered[:powered.index("\n    def ", 1)]
        self.assertNotIn("GetBlockPoweredState", powered)
        self.assertIn("_adjacent_redstone_powered", powered)

    def test_vanilla_projectile_hit_can_restore_ranged_player_owner(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        helper = server[server.index("def _remember_ur_ghast_projectile_hit"):]
        helper = helper[:helper.index("\n    def ", 1)]
        for field in ("ownerId", "shooterId", "sourceId", "srcId"):
            self.assertIn(field, helper)
        self.assertIn("_remember_ur_ghast_player_attack", helper)

        hit = server[server.index("def OnProjectileDoHitEffectEvent"):]
        hit = hit[:hit.index("\n    def ", 1)]
        self.assertIn("_remember_ur_ghast_projectile_hit", hit)

    def test_fireball_is_damage_immune_and_impact_settles_once(self):
        behavior = load_json(
            BP / "entities" / "ur_ghast_fireball.entity.json"
        )["minecraft:entity"]
        components = behavior["components"]
        self.assertNotIn("minecraft:damage_sensor", components)
        self.assertGreaterEqual(components["minecraft:health"]["value"], 32)
        self.assertTrue(components["minecraft:pushable"]["is_pushable"])
        hitboxes = components["minecraft:custom_hit_test"]["hitboxes"]
        self.assertGreaterEqual(hitboxes[0]["width"], 1.5)
        self.assertGreaterEqual(hitboxes[0]["height"], 1.5)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        health = server[server.index("def _protect_ur_ghast_fireball_health"):]
        health = health[:health.index("\n    def ", 1)]
        self.assertIn('args["cancel"] = True', health)
        self.assertIn("_set_health", health)

        hit = server[server.index("def OnProjectileDoHitEffectEvent"):]
        hit = hit[:hit.index("\n    def ", 1)]
        self.assertLess(
            hit.index('if projectile.get("removed")'),
            hit.index("fireball_collision_decision"),
        )
        self.assertLess(
            hit.index('projectile["removed"] = True'),
            hit.index("FIREBALL_DIRECT_DAMAGE"),
        )
        self.assertIn("ignoredContacts", hit)

    def test_hurt_death_trap_pitch_and_compatibility_speed_are_bound(self):
        boss = load_json(BP / "entities" / "ur_ghast.entity.json")[
            "minecraft:entity"
        ]
        properties = boss["description"]["properties"]
        self.assertIn("tf_slice:hurt_flash", properties)
        self.assertIn("tf_slice:visual_pitch", properties)
        self.assertIn("tf_slice:hurt_on", boss["events"])
        self.assertIn("tf_slice:visual_pitch_down", boss["events"])

        renderer = load_json(
            RP / "render_controllers" / "phantom_urghast_route.render.json"
        )["render_controllers"]["controller.render.tf_slice.ur_ghast"]
        self.assertIn("tf_slice:hurt_flash", json.dumps(renderer))

        animation = load_json(
            RP / "animations" / "phantom_urghast_route.animation.json"
        )["animations"]["animation.tf_slice.ur_ghast.move"]
        pose_root = animation["bones"]["pose_root"]
        self.assertIn("tf_slice:visual_pitch", json.dumps(pose_root))

        self.assertEqual(0.91, logic.FLIGHT_DRAG)
        self.assertEqual(1.0, logic.FLIGHT_CORRUPT_SPEED_LIMIT)
        self.assertEqual(90, logic.DEATH_SEQUENCE_TICKS)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        drive = server[server.index("def _drive_ur_ghasts"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertIn("advance_death_sequence", drive)
        self.assertNotIn("advance_death_fall", drive)
        self.assertIn('"death_burst"', drive)
        self.assertIn('"death_trail"', drive)
        self.assertIn("_tick_ur_ghast_hurt_feedback", drive)
        self.assertIn("_sync_ur_ghast_visual_pitch", drive)


if __name__ == "__main__":
    unittest.main()
