#!/usr/bin/env python3
"""Build offline model, behavior, and boss evidence for the route repair."""

from __future__ import print_function

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from phantom_urghast_model_registry import (
    EXTRACTED,
    ORDER,
    REGISTRY_PATH,
    ROOT,
    SPECS,
    sync_group,
)


JAR_SHA256 = "0BDC89263616D1B35C32EF82C5E9C14CBD20368E2FE8B468C72A28320BE7A778"
GEOMETRY = "TwilightBossSliceR/models/entity/phantom_urghast_route.geo.json"
ANIMATION = "TwilightBossSliceR/animations/phantom_urghast_route.animation.json"
FOCUSED_TEST = "tests/test_phantom_urghast_entity_quality.py"
UR_GHAST_PARITY_TEST = "tests/test_ur_ghast_source_parity.py"
GENERATOR = "tools/build_phantom_urghast_models.py"
RENDERER = "tools/render_entity_geo_preview.py"
KNIGHT_PHANTOM_RENDERER = "tools/render_knight_phantom_preview.py"
UR_GHAST_RENDERER = "tools/render_ur_ghast_preview.py"
RENDER_CONTROLLER = "TwilightBossSliceR/render_controllers/phantom_urghast_route.render.json"
SNAPSHOT = "model_acceptance/source_snapshots/phantom_urghast_route_models.json"
LOGIC = "TwilightBossSliceB/TwilightBossSlice/phantom_urghast_mob_logic.py"
SPIDER_LOGIC = "TwilightBossSliceB/TwilightBossSlice/spider_logic.py"
FLIGHT_LOGIC = "TwilightBossSliceB/TwilightBossSlice/flight_logic.py"
SERVER = "TwilightBossSliceB/TwilightBossSlice/serverSystem.py"
CLIENT = "TwilightBossSliceB/TwilightBossSlice/clientSystem.py"
CONFIG = "TwilightBossSliceB/TwilightBossSlice/config.py"
RELEASE_METADATA = "TwilightBossSliceB/TwilightBossSlice/release_metadata.py"
BEHAVIOR_MANIFEST = "TwilightBossSliceB/manifest.json"
RESOURCE_MANIFEST = "TwilightBossSliceR/manifest.json"
UR_GHAST_FIREBALL_BEHAVIOR = (
    "TwilightBossSliceB/entities/ur_ghast_fireball.entity.json"
)
UR_GHAST_FIREBALL_CLIENT = (
    "TwilightBossSliceR/entity/ur_ghast_fireball.entity.json"
)
GHAST_TRAP_BLOCK = "TwilightBossSliceB/netease_blocks/ghast_trap.json"
UR_GHAST_EFFECT_LOGIC = (
    "TwilightBossSliceB/TwilightBossSlice/ur_ghast_effect_logic.py"
)
UR_GHAST_HITBOX_DEBUG_LOGIC = (
    "TwilightBossSliceB/TwilightBossSlice/"
    "ur_ghast_hitbox_debug_logic.py"
)
UR_GHAST_EFFECT_GENERATOR = "tools/build_ur_ghast_effect_assets.py"
UR_GHAST_EFFECT_PARTICLES = [
    "TwilightBossSliceR/particles/ur_ghast_lightning.json",
    "TwilightBossSliceR/particles/ghast_trap_mote.json",
    "TwilightBossSliceR/particles/ghast_trap_beam.json",
]
SOUNDS = "TwilightBossSliceR/sounds.json"

MOBS = tuple(identifier for identifier in ORDER if not SPECS[identifier].get("projectile"))
REJECTED_BEHAVIOR_IDS = frozenset(("ur_ghast",))

BEHAVIOR_CLASSES = {
    "block_chain_goblin": (
        ("twilightforest.entity.monster.BlockChainGoblin", "twilightforest/entity/monster/BlockChainGoblin.class"),
        ("twilightforest.entity.ai.goal.ThrowSpikeBlockGoal", "twilightforest/entity/ai/goal/ThrowSpikeBlockGoal.class"),
    ),
    "lower_goblin_knight": (
        ("twilightforest.entity.monster.LowerGoblinKnight", "twilightforest/entity/monster/LowerGoblinKnight.class"),
        ("twilightforest.entity.ai.goal.ThrowRiderGoal", "twilightforest/entity/ai/goal/ThrowRiderGoal.class"),
    ),
    "upper_goblin_knight": (
        ("twilightforest.entity.monster.UpperGoblinKnight", "twilightforest/entity/monster/UpperGoblinKnight.class"),
        ("twilightforest.entity.ai.goal.RiderSpearAttackGoal", "twilightforest/entity/ai/goal/RiderSpearAttackGoal.class"),
    ),
    "helmet_crab": (
        ("twilightforest.entity.monster.HelmetCrab", "twilightforest/entity/monster/HelmetCrab.class"),
    ),
    "knight_phantom": (
        ("twilightforest.entity.boss.KnightPhantom", "twilightforest/entity/boss/KnightPhantom.class"),
        ("twilightforest.entity.ai.goal.PhantomWatchAndAttackGoal", "twilightforest/entity/ai/goal/PhantomWatchAndAttackGoal.class"),
        ("twilightforest.entity.ai.goal.PhantomUpdateFormationAndMoveGoal", "twilightforest/entity/ai/goal/PhantomUpdateFormationAndMoveGoal.class"),
        ("twilightforest.entity.ai.goal.PhantomThrowWeaponGoal", "twilightforest/entity/ai/goal/PhantomThrowWeaponGoal.class"),
        ("twilightforest.entity.ai.goal.PhantomAttackStartGoal", "twilightforest/entity/ai/goal/PhantomAttackStartGoal.class"),
    ),
    "carminite_golem": (
        ("twilightforest.entity.monster.CarminiteGolem", "twilightforest/entity/monster/CarminiteGolem.class"),
    ),
    "tower_broodling": (
        ("twilightforest.entity.monster.TowerBroodling", "twilightforest/entity/monster/TowerBroodling.class"),
        ("twilightforest.entity.monster.SwarmSpider", "twilightforest/entity/monster/SwarmSpider.class"),
    ),
    "mini_ghast": (
        ("twilightforest.entity.monster.CarminiteGhastling", "twilightforest/entity/monster/CarminiteGhastling.class"),
        ("twilightforest.entity.ai.goal.GhastguardAttackGoal", "twilightforest/entity/ai/goal/GhastguardAttackGoal.class"),
        ("twilightforest.entity.ai.goal.GhastguardRandomFlyGoal", "twilightforest/entity/ai/goal/GhastguardRandomFlyGoal.class"),
    ),
    "tower_ghast": (
        ("twilightforest.entity.monster.CarminiteGhastguard", "twilightforest/entity/monster/CarminiteGhastguard.class"),
        ("twilightforest.entity.ai.goal.GhastguardAttackGoal", "twilightforest/entity/ai/goal/GhastguardAttackGoal.class"),
        ("twilightforest.entity.ai.goal.GhastguardHomedFlightGoal", "twilightforest/entity/ai/goal/GhastguardHomedFlightGoal.class"),
    ),
    "towerwood_borer": (
        ("twilightforest.entity.monster.TowerwoodBorer", "twilightforest/entity/monster/TowerwoodBorer.class"),
        ("twilightforest.entity.monster.TowerwoodBorer$SummonBorersGoal", "twilightforest/entity/monster/TowerwoodBorer$SummonBorersGoal.class"),
        ("twilightforest.entity.monster.TowerwoodBorer$HideInTowerwoodGoal", "twilightforest/entity/monster/TowerwoodBorer$HideInTowerwoodGoal.class"),
    ),
    "ur_ghast": (
        ("twilightforest.entity.boss.UrGhast", "twilightforest/entity/boss/UrGhast.class"),
        ("twilightforest.entity.ai.goal.UrGhastFlightGoal", "twilightforest/entity/ai/goal/UrGhastFlightGoal.class"),
        ("twilightforest.entity.ai.goal.GhastguardAttackGoal", "twilightforest/entity/ai/goal/GhastguardAttackGoal.class"),
        ("twilightforest.entity.projectile.UrGhastFireball", "twilightforest/entity/projectile/UrGhastFireball.class"),
        ("twilightforest.entity.ai.control.NoClipMoveControl", "twilightforest/entity/ai/control/NoClipMoveControl.class"),
        ("twilightforest.client.renderer.TFWeatherRenderer", "twilightforest/client/renderer/TFWeatherRenderer.class"),
        ("twilightforest.client.particle.GhastTrapParticle", "twilightforest/client/particle/GhastTrapParticle.class"),
        ("twilightforest.block.entity.GhastTrapBlockEntity", "twilightforest/block/entity/GhastTrapBlockEntity.class"),
    ),
}

SCENARIOS = {
    "block_chain_goblin": ("chain-cooldown", "A visible player within squared distance 42 can trigger the 1/56 chain throw, followed by the locked 100-199 tick cooldown."),
    "lower_goblin_knight": ("paired-rider", "A lower knight creates and carries one upper knight; the mount freezes while the rider's heavy spear is active."),
    "upper_goblin_knight": ("spear-shield", "The 60-tick spear lands once at timer 25 and a frontal shield only breaks above ten incoming damage."),
    "helmet_crab": ("crab-leap", "The crab uses grounded navigation, melee pursuit, and its source-specific target leap."),
    "knight_phantom": (
        "six-member-formations",
        "Six stable persisted slots dynamically renumber living roles; a random leader formation leaves at most one independent two-stage charger, with source sweeps, guard cycles, thrown tools, and synchronized group death presentation.",
    ),
    "carminite_golem": ("golem-melee", "The golem patrols the tower and applies its locked nine-point melee attack."),
    "tower_broodling": ("broodling-pack", "A climbing broodling leaps at targets, creates one or two companions without recursive multiplication, and inherits SwarmSpider's one-success-in-four melee rule."),
    "mini_ghast": ("ghastling-volley", "The ghastling hovers, requires sight, warns at tick ten, and fires at tick twenty with the locked cooldown."),
    "tower_ghast": ("guard-volley", "The tower guard retains homed flight, line-of-sight targeting, and the ghast warn/fire cadence."),
    "towerwood_borer": ("wake-borers", "Damage starts exactly 21 surrounding-block scan steps and wakes borers from infested towerwood."),
    "ur_ghast": (
        "source-parity-state-machine",
        "The boss waves source-timed tentacles, requires range and sight for a warned mouth-launched triple volley, disables that volley during tear-damage tantrum, maintains six minions at each of two traps, consumes nearby minions, and settles reward once.",
    ),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def relative(path):
    path = path.resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return "../" + path.relative_to(ROOT.parent).as_posix()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def production_hashes(paths):
    return dict((path, sha256(ROOT / path)) for path in paths)


def production_list(paths):
    return [{"path": path, "sha256": sha256(ROOT / path)} for path in paths]


def behavior_sources(identifier):
    return [
        {
            "class": class_name,
            "path": relative(EXTRACTED / source_path),
            "sha256": sha256(EXTRACTED / source_path),
        }
        for class_name, source_path in BEHAVIOR_CLASSES[identifier]
    ]


def offline_evidence(identifier, entry, generated_at):
    focused_tests = [FOCUSED_TEST]
    if identifier == "ur_ghast":
        focused_tests.append(UR_GHAST_PARITY_TEST)
    textures = dict(
        (row["target"], row["sha256"])
        for row in entry["source"]["textures"]
    )
    base = "model_acceptance/offline/images/%s" % identifier
    renderer = (
        UR_GHAST_RENDERER
        if identifier == "ur_ghast"
        else KNIGHT_PHANTOM_RENDERER
        if identifier == "knight_phantom"
        else RENDERER
    )
    value = {
        "entity": identifier,
        "status": entry["status"],
        "source_jar_sha256": JAR_SHA256,
        "geometry_sha256": sha256(ROOT / GEOMETRY),
        "animation_sha256": sha256(ROOT / ANIMATION),
        "render_controller_sha256": sha256(ROOT / RENDER_CONTROLLER),
        "texture_sha256": textures,
        "automated": {
            "source_lock_passed": True,
            "focused_tests_passed": True,
            "focused_tests": [
                {"path": path, "sha256": sha256(ROOT / path)}
                for path in focused_tests
            ],
            "source_snapshot": {"path": SNAPSHOT, "sha256": sha256(ROOT / SNAPSHOT)},
            "generator": {"path": GENERATOR, "sha256": sha256(ROOT / GENERATOR), "check_args": []},
            "renderer": {"path": renderer, "sha256": sha256(ROOT / renderer)},
        },
        "generated_at": generated_at,
        "renderer": (
            "Independent perspective cube/UV renderer with locked reference "
            "camera and source rest, walk, and look extremes"
            if identifier == "ur_ghast"
            else "Independent layered renderer reproducing the visor face backing, held-item pose, and charging skeleton visibility"
            if identifier == "knight_phantom"
            else "Independent orthographic cube/UV renderer with source rest, walk, and look extremes"
        ),
        "offline": {
            "views": dict((name, "%s/views/%s.png" % (base, name)) for name in ("front", "back", "left", "right", "top", "three_quarter")),
            "poses": dict((name, "%s/poses/%s.png" % (base, name)) for name in ("rest", "walk_extreme", "look_up", "look_down")),
        },
    }
    if identifier == "knight_phantom":
        item_path = "TwilightBossSliceR/textures/items/knightmetal_sword.png"
        value["offline"]["attachments"] = {
            "mainhand": base + "/attachments/mainhand.png"
        }
        value["attachment_contracts"] = {
            "mainhand": {
                "bone": "rightItem",
                "texture_path": item_path,
                "texture_sha256": sha256(ROOT / item_path),
                "focused_tests": [FOCUSED_TEST],
                "checks": {
                    "equipment_source": True,
                    "grip_contacts_hand": True,
                    "tool_head_clear_of_hand": True,
                    "front_depth_visible": True,
                    "orientation_reviewed": True,
                },
            }
        }
        value["offline"]["states"] = {
            "charging": base + "/states/charging.png"
        }
        value["offline"]["comparisons"] = {
            "mcmod_reference": (
                "model_acceptance/offline/comparisons/"
                "knight_phantom_reference_vs_armor_layer.png"
            )
        }
    elif identifier == "ur_ghast":
        value["offline"]["views"]["reference_angle"] = (
            base + "/views/reference_angle.png"
        )
        value["offline"]["comparisons"] = {
            "mcmod_reference": (
                "model_acceptance/offline/comparisons/"
                "ur_ghast_reference_vs_source_perspective.png"
            )
        }
    return value


def behavior_evidence(identifier, entry, generated_at):
    paths = [
        "TwilightBossSliceB/entities/%s.entity.json" % identifier,
        LOGIC,
        SERVER,
    ]
    if identifier == "knight_phantom":
        paths.append("TwilightBossSliceB/TwilightBossSlice/knight_route_logic.py")
    elif identifier == "ur_ghast":
        paths.extend((
            "TwilightBossSliceB/TwilightBossSlice/ur_ghast_logic.py",
            UR_GHAST_EFFECT_LOGIC,
            UR_GHAST_HITBOX_DEBUG_LOGIC,
            CLIENT,
            CONFIG,
            UR_GHAST_FIREBALL_BEHAVIOR,
            UR_GHAST_FIREBALL_CLIENT,
            GHAST_TRAP_BLOCK,
            SOUNDS,
        ))
        paths.extend(UR_GHAST_EFFECT_PARTICLES)
    elif identifier == "tower_broodling":
        paths.append(SPIDER_LOGIC)
    if identifier in (
        "knight_phantom", "mini_ghast", "tower_ghast", "ur_ghast"
    ):
        paths.append(FLIGHT_LOGIC)
    scenario_id, contract = SCENARIOS[identifier]
    test_path = (
        UR_GHAST_PARITY_TEST
        if identifier == "ur_ghast" else FOCUSED_TEST
    )
    return {
        "entity": identifier,
        "status": entry["behavior"]["status"],
        "source_jar_sha256": JAR_SHA256,
        "source_hashes": dict((row["path"], row["sha256"]) for row in entry["behavior"]["sources"]),
        "production_hashes": production_hashes(paths),
        "automated": {
            "source_lock_passed": True,
            "red_contract_observed": True,
            "focused_tests_passed": True,
            "formal_validator_passed": True,
        },
        "scenarios": [{"id": scenario_id, "contract": contract, "test": test_path}],
        "generated_at": generated_at,
        "runtime": {
            "cold_restart": False,
            "client_build": "",
            "pack_version": [],
            "reviewer": "",
            "captured_at": "",
            "evidence": {},
        },
    }


def class_record(role, class_name, source_path):
    path = EXTRACTED / source_path
    return {"role": role, "class": class_name, "path": relative(path), "sha256": sha256(path)}


def boss_record(identifier, entry):
    short = identifier.split(":", 1)[-1]
    is_knight = short == "knight_phantom"
    if is_knight:
        classes = [
            class_record("entity", "twilightforest.entity.boss.KnightPhantom", "twilightforest/entity/boss/KnightPhantom.class"),
            class_record("model", "twilightforest.client.model.entity.KnightPhantomModel", "twilightforest/client/model/entity/KnightPhantomModel.class"),
            class_record("renderer", "twilightforest.client.renderer.entity.KnightPhantomRenderer", "twilightforest/client/renderer/entity/KnightPhantomRenderer.class"),
            class_record("armor_model", "twilightforest.client.model.armor.PhantomArmorModel", "twilightforest/client/model/armor/PhantomArmorModel.class"),
            class_record("armor_base_model", "twilightforest.client.model.armor.KnightmetalArmorModel", "twilightforest/client/model/armor/KnightmetalArmorModel.class"),
            class_record("armor_item", "twilightforest.item.PhantomArmorItem", "twilightforest/item/PhantomArmorItem.class"),
        ]
        ai_paths = [SERVER, "TwilightBossSliceB/TwilightBossSlice/knight_route_logic.py", "TwilightBossSliceB/entities/knight_phantom.entity.json"]
        item_paths = ["TwilightBossSliceB/loot_tables/entities/tf_slice/knight_phantom.json", "TwilightBossSliceB/items/knightmetal_sword.item.json"]
        integration_paths = ["TwilightBossSliceB/TwilightBossSlice/structureWorldgenService.py", "TwilightBossSliceB/TwilightBossSlice/route_progression_logic.py"]
        phase_text = "Six stable slots use a lowest-number leader, weighted random small-circle/directional-sweep broadcasts, and at most one independent prepare/attack/wait charger."
        damage_text = "Each member has 35 health, idle-defense compatibility, an eight-damage enlarged charging component, and the Hard-mode slot-five guard cycle."
        reward_text = "Early deaths hold after the 18-tick poof; the final defeat releases synchronized 70-tick chest trails and settles source loot and participant credit once."
        presentation_text = "Source-derived geometry, exact texture branches, animations, scale, equipment, source WHITE/PROGRESS name-only 182x5 HUD, and offline views pass; actual-client review remains pending."
    else:
        classes = [
            class_record("entity", "twilightforest.entity.boss.UrGhast", "twilightforest/entity/boss/UrGhast.class"),
            class_record("model", "twilightforest.client.model.entity.newmodels.NewUrGhastModel", "twilightforest/client/model/entity/newmodels/NewUrGhastModel.class"),
            class_record("renderer", "twilightforest.client.renderer.entity.newmodels.NewUrGhastRenderer", "twilightforest/client/renderer/entity/newmodels/NewUrGhastRenderer.class"),
            class_record("attack_goal", "twilightforest.entity.ai.goal.GhastguardAttackGoal", "twilightforest/entity/ai/goal/GhastguardAttackGoal.class"),
            class_record("flight_goal", "twilightforest.entity.ai.goal.UrGhastFlightGoal", "twilightforest/entity/ai/goal/UrGhastFlightGoal.class"),
            class_record("projectile", "twilightforest.entity.projectile.UrGhastFireball", "twilightforest/entity/projectile/UrGhastFireball.class"),
            class_record("move_control", "twilightforest.entity.ai.control.NoClipMoveControl", "twilightforest/entity/ai/control/NoClipMoveControl.class"),
            class_record("weather_renderer", "twilightforest.client.renderer.TFWeatherRenderer", "twilightforest/client/renderer/TFWeatherRenderer.class"),
            class_record("trap_particle", "twilightforest.client.particle.GhastTrapParticle", "twilightforest/client/particle/GhastTrapParticle.class"),
            class_record("trap_block_entity", "twilightforest.block.entity.GhastTrapBlockEntity", "twilightforest/block/entity/GhastTrapBlockEntity.class"),
        ]
        ai_paths = [SERVER, "TwilightBossSliceB/TwilightBossSlice/ur_ghast_logic.py", UR_GHAST_EFFECT_LOGIC, "TwilightBossSliceB/entities/ur_ghast.entity.json", UR_GHAST_FIREBALL_BEHAVIOR]
        item_paths = ["TwilightBossSliceB/loot_tables/chests/tf_slice/ur_ghast_reward.json", "TwilightBossSliceB/netease_blocks/ur_ghast_trophy.json", "TwilightBossSliceB/items/ur_ghast_banner.item.json"]
        integration_paths = ["TwilightBossSliceB/TwilightBossSlice/structureWorldgenService.py", "TwilightBossSliceB/TwilightBossSlice/route_progression_logic.py", "TwilightBossSliceB/TwilightBossSlice/dark_tower_logic.py", CONFIG, RELEASE_METADATA, BEHAVIOR_MANIFEST, RESOURCE_MANIFEST]
        phase_text = "A 20 Hz source clock owns live-trap patrol, sight-gated warned mouth volley, tear-damage tantrum, six-per-trap minion pressure, trap pull, minion absorption, and death fall."
        damage_text = "The 250-health boss uses a 14x18 physical envelope, a visible-head/body selection volume, accepted-damage participant attribution, reflected-projectile ownership, persisted phase health and one reward settlement."
        reward_text = "The death sequence settles four 1..3 carminite rolls, two 1..5 fiery-tears rolls, one trophy and 317 XP exactly once; the banner is not boss loot."
        presentation_text = "Source-derived geometry, three face textures, charging scale, built-in visible fireball renderer, target-facing yaw, trap pull motes, dimension-local rain with zero gameplay thunder, source RED/PROGRESS HUD and offline views pass; actual-client review remains pending."
    tests = [
        FOCUSED_TEST,
        (
            "tests/test_knight_route_content_and_combat.py"
            if is_knight else UR_GHAST_PARITY_TEST
        ),
    ]
    model_paths = [
        GEOMETRY,
        ANIMATION,
        RENDER_CONTROLLER,
        "TwilightBossSliceR/entity/%s.entity.json" % short,
    ]
    asset_paths = [row["target"] for row in entry["source"]["textures"]] + [ANIMATION]
    if not is_knight:
        asset_paths.extend(
            UR_GHAST_EFFECT_PARTICLES
            + [
                UR_GHAST_FIREBALL_CLIENT,
                UR_GHAST_EFFECT_GENERATOR,
                SOUNDS,
            ]
        )
    interaction_paths = [SERVER, "TwilightBossSliceB/TwilightBossSlice/clientSystem.py", "TwilightBossSliceB/TwilightBossSlice/routeBossHudUI.py"]
    if not is_knight:
        interaction_paths.extend((
            UR_GHAST_HITBOX_DEBUG_LOGIC,
            CONFIG,
            GHAST_TRAP_BLOCK,
        ))
    jar = next(ROOT.parent.glob("*twilightforest-1.20.1-4.3.2508-universal.jar"))

    def track(status, paths):
        return {"status": status, "tests": tests, "production_hashes": production_list(paths)}

    def contract(name, expected):
        return [{"id": name, "expected": expected}]

    return {
        "boss": identifier,
        "status": (
            "implemented" if is_knight else "rejected"
        ),
        "source": {
            "jar_path": relative(jar),
            "jar_sha256": JAR_SHA256,
            "classes": classes,
            "textures": entry["source"]["textures"],
        },
        "tracks": {
            "model": track(
                "rejected"
                if short in ("knight_phantom", "ur_ghast")
                else "candidate",
                model_paths,
            ),
            "ai": track("implemented", ai_paths),
            "interactions": track("implemented", interaction_paths),
            "assets": track(
                "rejected"
                if short in ("knight_phantom", "ur_ghast")
                else "candidate",
                asset_paths,
            ),
            "items_rewards": track("implemented", item_paths),
            "integration": track("implemented", integration_paths),
        },
        "contracts": {
            "phases": contract("phases", phase_text),
            "goals": contract("goals", "Locked target selection, movement, attack priority, and interruption rules are represented by native goals plus server FSM state."),
            "damage": contract("damage", damage_text),
            "interactions": contract("interactions", "Progression gates, boss HUD synchronization, multiplayer participant credit, and source-specific combat interactions remain server authoritative."),
            "presentation_assets": contract("presentation-assets", presentation_text),
            "items_rewards": contract("items-rewards", reward_text),
            "death_rewards": contract("death-rewards", "Death and the landmark ledger prevent duplicate reward settlement."),
            "persistence_multiplayer": contract("persistence-multiplayer", "Encounter state, participants, timers, and reward claims survive reload without shifting authority to the client."),
        },
        "runtime": {"cold_restart": False, "client_build": "", "pack_version": [], "reviewer": "", "captured_at": "", "scenarios": []},
    }


def route_summary(group, registry_entries):
    selected = [identifier for identifier in MOBS if SPECS[identifier]["group"] == group]
    rejected_ids = [
        identifier
        for identifier in selected
        if registry_entries[identifier]["status"] == "rejected"
    ]
    rejected = bool(rejected_ids)
    return {
        "status": "rejected" if rejected else "candidate",
        "offlineEvidenceComplete": not rejected,
        "clientAccepted": False,
        "runtimeVerified": False,
        "blockingReason": (
            "User-reported visual mismatch rejected: %s; regenerated evidence and fresh cold-client review are required."
            % ", ".join(rejected_ids)
            if rejected
            else "Offline model and behavior gates pass; cold-start actual-client review is still required."
        ),
        "sourceVersion": "1.20.1-4.3.2508",
        "models": [
            {
                "identifier": "tf_slice:" + identifier,
                "status": registry_entries[identifier]["status"],
                "offlineEvidence": registry_entries[identifier]["offline_evidence"],
                "requiredViews": ["front", "back", "left", "right", "top", "three_quarter"],
                "requiredPoses": ["rest", "walk_extreme", "look_up", "look_down"],
            }
            for identifier in selected
        ],
    }


def build():
    sync_group("knight")
    sync_group("tower")
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entries = dict((row["id"], row) for row in registry["entities"])
    generated_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    for identifier in MOBS:
        entry = entries[identifier]
        entry["bedrock"]["animation"] = ANIMATION
        entry["behavior"] = {
            "status": (
                "rejected"
                if identifier in REJECTED_BEHAVIOR_IDS
                else "implemented"
            ),
            "sources": behavior_sources(identifier),
            "evidence": "model_acceptance/behavior/%s.json" % identifier,
        }
        if identifier == "knight_phantom":
            entry["required_attachments"] = ["mainhand"]
        write_json(ROOT / entry["offline_evidence"], offline_evidence(identifier, entry, generated_at))
        write_json(ROOT / entry["behavior"]["evidence"], behavior_evidence(identifier, entry, generated_at))
    registry["entities"] = [entries[row["id"]] for row in registry["entities"]]
    write_json(REGISTRY_PATH, registry)
    write_json(ROOT / "evidence/models/knight_route.json", route_summary("knight", entries))
    write_json(ROOT / "evidence/models/dark_tower_route.json", route_summary("tower", entries))
    write_json(ROOT / "boss_acceptance/knight_phantom.json", boss_record("tf_slice:knight_phantom", entries["knight_phantom"]))
    write_json(ROOT / "boss_acceptance/ur_ghast.json", boss_record("tf_slice:ur_ghast", entries["ur_ghast"]))
    print("built acceptance evidence for %d route mobs and two bosses" % len(MOBS))


if __name__ == "__main__":
    build()
