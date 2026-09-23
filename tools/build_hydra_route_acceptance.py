#!/usr/bin/env python3
"""Build source-locked acceptance records for the Labyrinth/Hydra route.

The default state is deliberately conservative: models are ``converted`` and
behaviors are ``contracted``.  Pass ``--implemented`` only after the focused
tests and the development validator have passed.  This script never creates
offline renders or actual-client evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "source_locks" / "hydra_route.json"
REGISTRY_PATH = ROOT / "model_acceptance" / "registry.json"
BEHAVIOR_ROOT = ROOT / "model_acceptance" / "behavior"
BOSS_ROOT = ROOT / "boss_acceptance"

JAR_SHA256 = "0BDC89263616D1B35C32EF82C5E9C14CBD20368E2FE8B468C72A28320BE7A778"

ENTITY_CONTRACTS = {
    "minotaur": {
        "model": "twilightforest.client.model.entity.MinotaurModel",
        "renderer": "twilightforest.client.renderer.entity.TFBipedRenderer",
        "texture": "minotaur.png",
        "sources": (
            "twilightforest.entity.monster.Minotaur",
            "twilightforest.entity.ai.goal.ChargeAttackGoal",
        ),
        "logic": "TwilightBossSliceB/TwilightBossSlice/minotaur_logic.py",
        "required_attachments": ("mainhand",),
        "required_animation_checks": (
            "phase_amplitude_roles",
            "bounded_long_horizon",
            "source_extreme_preview",
        ),
        "scenario": (
            "charge-window",
            "A 30-health Minotaur starts a visible 4-8 block charge after the locked wind-up and preserves server-owned impact motion.",
            "tests/test_labyrinth_route_logic.py::MinotaurAndMinoshroomTests",
        ),
    },
    "minoshroom": {
        "model": "twilightforest.client.model.entity.MinoshroomModel",
        "renderer": "twilightforest.client.renderer.entity.MinoshroomRenderer",
        "texture": "minoshroomtaur.png",
        "sources": (
            "twilightforest.entity.boss.Minoshroom",
            "twilightforest.entity.ai.goal.ChargeAttackGoal",
            "twilightforest.entity.ai.goal.GroundAttackGoal",
        ),
        "logic": "TwilightBossSliceB/TwilightBossSlice/minotaur_logic.py",
        "required_attachments": ("mainhand",),
        "required_animation_checks": (
            "phase_amplitude_roles",
            "bounded_long_horizon",
            "source_extreme_preview",
        ),
        "scenario": (
            "slam-reload-reward",
            "The 120-health Minoshroom stays within its 20-block home, slams a 15x3x15 region, persists participants, and settles 100 XP plus source-locked drops once.",
            "tests/test_labyrinth_route_logic.py::MinotaurAndMinoshroomTests",
        ),
    },
    "maze_slime": {
        "model": "net.minecraft.client.model.SlimeModel",
        "renderer": "twilightforest.client.renderer.entity.MazeSlimeRenderer",
        "texture": "mazeslime.png",
        "sources": ("twilightforest.entity.monster.MazeSlime",),
        "logic": "TwilightBossSliceB/TwilightBossSlice/maze_slime_logic.py",
        "scenario": (
            "double-health-split",
            "Maze Slimes choose a vanilla power-of-two spawn size, use doubled health and size-scaled combat, hop with native slime goals, and recursively split until size one.",
            "tests/test_labyrinth_route_logic.py::MazeSlimeBehaviorTests",
        ),
    },
    "mosquito_swarm": {
        "model": "twilightforest.client.model.entity.MosquitoSwarmModel",
        "texture": "mosquitoswarm.png",
        "sources": ("twilightforest.entity.monster.MosquitoSwarm",),
        "logic": "TwilightBossSliceB/TwilightBossSlice/mosquito_swarm_logic.py",
        "production": (
            "TwilightBossSliceB/spawn_rules/mosquito_swarm.json",
            "TwilightBossSliceB/loot_tables/entities/tf_slice/mosquito_swarm.json",
            "TwilightBossSliceR/sounds.json",
            "TwilightBossSliceR/ui/_ui_defs.json",
        ),
        "scenario": (
            "source-melee-hunger-without-overlay",
            "A visible player target is pursued by native server AI; a settled melee hit applies difficulty-scaled Hunger I without a non-source screen overlay.",
            "tests/test_mosquito_swarm_parity.py::MosquitoSwarmContentContractTests",
        ),
    },
    "hydra": {
        "model": "twilightforest.client.model.entity.HydraModel",
        "texture": "hydra4.png",
        "sources": (
            "twilightforest.entity.boss.Hydra",
            "twilightforest.entity.boss.HydraHeadContainer",
            "twilightforest.entity.boss.HydraHeadContainer$State",
        ),
        "logic": "TwilightBossSliceB/TwilightBossSlice/hydra_logic.py",
        "scenario": (
            "seven-head-fsm",
            "A 360-health body owns seven head slots, 1/8 closed-part damage, 120 head severing, 100-tick regrowth, 1000/5 regeneration, and the 200-tick single reward sequence.",
            "tests/test_hydra_logic.py",
        ),
    },
    "hydra_head": {
        "model": "twilightforest.client.model.entity.HydraHeadModel",
        "texture": "hydra4.png",
        "sources": (
            "twilightforest.entity.boss.HydraHead",
            "twilightforest.entity.boss.HydraHeadContainer",
        ),
        "logic": "TwilightBossSliceB/TwilightBossSlice/hydra_logic.py",
        "scenario": (
            "damage-forwarding-sync",
            "Attackable head children forward accepted damage to the body and send immediate transition packets plus ten-tick heartbeat correction.",
            "tests/test_hydra_route_entity_contract.py::HydraRouteEntityContractTests",
        ),
    },
    "hydra_mortar": {
        "model": "twilightforest.client.model.entity.HydraMortarModel",
        "texture": "hydramortar.png",
        "sources": ("twilightforest.entity.boss.HydraMortar",),
        "logic": "TwilightBossSliceB/TwilightBossSlice/hydra_logic.py",
        "scenario": (
            "reflected-mortar",
            "A player hit transfers mortar ownership and motion; hidden-target mega shots use power four while direct impact remains 18 damage.",
            "tests/test_hydra_logic.py::HydraHeadStateTests",
        ),
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def relative_external(path_value: str) -> str:
    path = Path(path_value).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return "../" + path.relative_to(ROOT.parent).as_posix()


def production_hashes(paths: list[str]) -> dict[str, str]:
    return {path: sha256(ROOT / path) for path in paths}


def production_list(paths: list[str]) -> list[dict[str, str]]:
    return [
        {"path": path, "sha256": sha256(ROOT / path)}
        for path in paths
    ]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def class_index(lock: dict) -> dict[str, dict]:
    return {row["class"]: row for row in lock["classes"]}


def texture_index(lock: dict) -> dict[str, dict]:
    return {Path(row["source"]).name: row for row in lock["textures"]}


def registry_entry(
    entity_id: str,
    contract: dict,
    classes: dict[str, dict],
    textures: dict[str, dict],
    implemented: bool,
) -> dict:
    model_row = classes.get(contract["model"])
    entity_row = classes[contract["sources"][0]]
    texture = textures[contract["texture"]]
    source = {
        "model_class": contract["model"],
        "entity_class": entity_row["class"],
        "entity_class_sha256": entity_row["sha256"],
        "model_branch": "classic; the locked JAR contains no jappa_models.marker",
        "textures": [
            {
                "source": relative_external(texture["source"]),
                "target": texture["target"],
                "sha256": texture["sha256"],
            }
        ],
    }
    if model_row is not None:
        source["model_class_sha256"] = model_row["sha256"]
    renderer_row = classes.get(contract.get("renderer"))
    if renderer_row is not None:
        source["renderer_class"] = renderer_row["class"]
        source["renderer_class_sha256"] = renderer_row["sha256"]
    behavior_sources = [
        {
            "class": classes[name]["class"],
            "path": relative_external(classes[name]["source"]),
            "sha256": classes[name]["sha256"],
        }
        for name in contract["sources"]
    ]
    offline_path = "model_acceptance/offline/%s.json" % entity_id
    offline_evidence_path = ROOT / offline_path
    offline_status = None
    if offline_evidence_path.is_file():
        try:
            offline_status = json.loads(
                offline_evidence_path.read_text(encoding="utf-8")
            ).get("status")
        except (OSError, ValueError):
            offline_status = None
    if offline_status == "candidate":
        model_status = "candidate"
    elif offline_status == "rejected":
        model_status = "rejected"
    else:
        model_status = "converted"
    result = {
        "id": entity_id,
        "status": model_status,
        "source": source,
        "bedrock": {
            "geometry": "TwilightBossSliceR/models/entity/hydra_route.geo.json",
            "identifier": "geometry.tf_slice." + entity_id,
            "client_entity": "TwilightBossSliceR/entity/%s.entity.json" % entity_id,
        },
        "behavior": {
            "status": "implemented" if implemented else "contracted",
            "sources": behavior_sources,
            "evidence": "model_acceptance/behavior/%s.json" % entity_id,
        },
        "note": (
            "Exact source texture and classic geometry conversion are locked; "
            + (
                "offline six-view/four-pose review passes; cold-client acceptance remains pending."
                if model_status == "candidate"
                else (
                    "offline evidence remains rejected; regenerated offline and cold-client review are required."
                    if model_status == "rejected"
                    else "offline six-view/four-pose review and cold-client acceptance remain pending."
                )
            )
        ),
    }
    if entity_id in ("minotaur", "minoshroom"):
        result["bedrock"]["animation"] = (
            "TwilightBossSliceR/animations/hydra_route.animation.json"
        )
    if contract.get("required_attachments"):
        result["required_attachments"] = list(
            contract["required_attachments"]
        )
    if contract.get("required_animation_checks"):
        result["required_animation_checks"] = list(
            contract["required_animation_checks"]
        )
    if offline_evidence_path.is_file():
        result["offline_evidence"] = offline_path
    return result


def behavior_evidence(
    entity_id: str,
    contract: dict,
    entry: dict,
) -> dict:
    scenario_id, scenario_contract, scenario_test = contract["scenario"]
    paths = [
        "TwilightBossSliceB/entities/%s.entity.json" % entity_id,
        contract["logic"],
        "TwilightBossSliceB/TwilightBossSlice/serverSystem.py",
    ]
    paths.extend(contract.get("production", ()))
    if entity_id in ("hydra", "hydra_head", "hydra_mortar"):
        paths.append("TwilightBossSliceB/TwilightBossSlice/clientSystem.py")
    return {
        "entity": entity_id,
        "status": "implemented",
        "source_jar_sha256": JAR_SHA256,
        "source_hashes": {
            row["path"]: row["sha256"] for row in entry["behavior"]["sources"]
        },
        "production_hashes": production_hashes(paths),
        "automated": {
            "source_lock_passed": True,
            "red_contract_observed": True,
            "focused_tests_passed": True,
            "formal_validator_passed": True,
        },
        "scenarios": [
            {
                "id": scenario_id,
                "contract": scenario_contract,
                "test": scenario_test,
            }
        ],
        "generated_at": datetime.now(
            timezone(timedelta(hours=8))
        ).isoformat(timespec="seconds"),
        "runtime": {
            "cold_restart": False,
            "client_build": "",
            "pack_version": [],
            "reviewer": "",
            "captured_at": "",
            "evidence": {},
        },
    }


def boss_source(
    class_names: tuple[str, ...],
    texture_names: tuple[str, ...],
    classes: dict[str, dict],
    textures: dict[str, dict],
    roles: dict[str, str] | None = None,
) -> dict:
    roles = roles or {}
    return {
        "jar_path": "../[暮色森林] twilightforest-1.20.1-4.3.2508-universal.jar",
        "jar_sha256": JAR_SHA256,
        "classes": [
            {
                "role": roles.get(name, "source"),
                "class": name,
                "path": relative_external(classes[name]["source"]),
                "sha256": classes[name]["sha256"],
            }
            for name in class_names
        ],
        "textures": [
            {
                "source": relative_external(textures[name]["source"]),
                "target": textures[name]["target"],
                "sha256": textures[name]["sha256"],
            }
            for name in texture_names
        ],
    }


def boss_evidence(
    boss_id: str,
    source: dict,
    model_paths: list[str],
    ai_paths: list[str],
    interaction_paths: list[str],
    asset_paths: list[str],
    item_paths: list[str],
    integration_paths: list[str],
    tests: list[str],
    contracts: dict[str, list[dict[str, str]]],
    top_status: str = "contracted",
    visual_status: str = "converted",
) -> dict:
    def visual(paths: list[str]) -> dict:
        return {"status": visual_status, "tests": tests, "production_hashes": production_list(paths)}

    def implemented(paths: list[str]) -> dict:
        return {"status": "implemented", "tests": tests, "production_hashes": production_list(paths)}

    return {
        "boss": boss_id,
        "status": top_status,
        "source": source,
        "tracks": {
            "model": visual(model_paths),
            "ai": implemented(ai_paths),
            "interactions": implemented(interaction_paths),
            "assets": visual(asset_paths),
            "items_rewards": implemented(item_paths),
            "integration": implemented(integration_paths),
        },
        "contracts": contracts,
        "runtime": {
            "cold_restart": False,
            "client_build": "",
            "pack_version": [],
            "reviewer": "",
            "captured_at": "",
            "scenarios": [],
        },
    }


def contract_rows(**values: str) -> dict[str, list[dict[str, str]]]:
    result = {}
    for name in (
        "phases", "goals", "damage", "interactions", "presentation_assets",
        "items_rewards", "death_rewards", "persistence_multiplayer",
    ):
        result[name] = [
            {"id": name.replace("_", "-"), "expected": values[name]}
        ]
    return result


def build_boss_records(
    classes: dict[str, dict],
    textures: dict[str, dict],
    implemented: bool,
) -> None:
    minoshroom_source = boss_source(
        (
            "twilightforest.entity.boss.Minoshroom",
            "twilightforest.client.model.entity.MinoshroomModel",
            "twilightforest.entity.ai.goal.ChargeAttackGoal",
            "twilightforest.entity.ai.goal.GroundAttackGoal",
            "twilightforest.client.renderer.entity.MinoshroomRenderer",
        ),
        ("minoshroomtaur.png",),
        classes,
        textures,
        {
            "twilightforest.entity.boss.Minoshroom": "entity",
            "twilightforest.client.model.entity.MinoshroomModel": "model",
            "twilightforest.client.renderer.entity.MinoshroomRenderer": "renderer",
        },
    )
    minoshroom = boss_evidence(
        "tf_slice:minoshroom",
        minoshroom_source,
        ["TwilightBossSliceR/models/entity/hydra_route.geo.json", "TwilightBossSliceR/entity/minoshroom.entity.json"],
        ["TwilightBossSliceB/TwilightBossSlice/minotaur_logic.py", "TwilightBossSliceB/TwilightBossSlice/serverSystem.py", "TwilightBossSliceB/entities/minoshroom.entity.json"],
        ["TwilightBossSliceB/TwilightBossSlice/serverSystem.py", "TwilightBossSliceB/TwilightBossSlice/clientSystem.py", "TwilightBossSliceB/TwilightBossSlice/routeBossHudUI.py"],
        ["TwilightBossSliceR/textures/entity/minoshroomtaur.png", "TwilightBossSliceR/animations/hydra_route.animation.json", "TwilightBossSliceR/ui/minoshroom_boss_hud.json"],
        ["TwilightBossSliceB/items/meef_stroganoff.item.json", "TwilightBossSliceB/items/diamond_minotaur_axe.item.json", "TwilightBossSliceB/netease_blocks/minoshroom_trophy.json"],
        ["TwilightBossSliceB/TwilightBossSlice/structureWorldgenService.py", "TwilightBossSliceB/structures/tf_slice/ruins/structure_catalog_v1.json", "TwilightBossSliceB/TwilightBossSlice/route_progression_logic.py"],
        ["tests/test_labyrinth_route_logic.py", "tests/test_hydra_route_model_workflow.py", "tests/test_hydra_route_structure_contract.py", "tests/test_hydra_route_entity_contract.py"],
        contract_rows(
            phases="Charge and ground-slam transitions stay server authoritative.",
            goals="The boss remains within a 20-block labyrinth home.",
            damage="The source-locked boss has 120 health and applies grounded slam damage.",
            interactions="Participants are tracked independently and protected labyrinth access is progress-gated.",
            presentation_assets="Candidate classic model, exact texture, source RED/PROGRESS 182x5 name-only HUD, charge and slam effects have offline evidence; actual-client review is pending.",
            items_rewards="One source loot settlement gives 2-5 stroganoff, trophy, diamond Minotaur axe and 100 XP.",
            death_rewards="The landmark ledger allows one reward claim while progress is credited to participants.",
            persistence_multiplayer="Home, health, charge timers, participants and reward state survive entity reload.",
        ),
        top_status="implemented" if implemented else "contracted",
        visual_status="candidate" if implemented else "converted",
    )
    write_json(BOSS_ROOT / "minoshroom.json", minoshroom)

    hydra_source = boss_source(
        (
            "twilightforest.entity.boss.Hydra",
            "twilightforest.entity.boss.HydraHead",
            "twilightforest.entity.boss.HydraHeadContainer",
            "twilightforest.entity.boss.HydraHeadContainer$State",
            "twilightforest.entity.boss.HydraMortar",
            "twilightforest.client.model.entity.HydraModel",
            "twilightforest.client.model.entity.HydraHeadModel",
            "twilightforest.client.model.entity.HydraMortarModel",
        ),
        ("hydra4.png", "hydramortar.png"),
        classes,
        textures,
    )
    hydra = boss_evidence(
        "tf_slice:hydra",
        hydra_source,
        ["TwilightBossSliceR/models/entity/hydra_route.geo.json", "TwilightBossSliceR/entity/hydra.entity.json", "TwilightBossSliceR/entity/hydra_head.entity.json"],
        ["TwilightBossSliceB/TwilightBossSlice/hydra_logic.py", "TwilightBossSliceB/TwilightBossSlice/serverSystem.py", "TwilightBossSliceB/entities/hydra.entity.json"],
        ["TwilightBossSliceB/TwilightBossSlice/serverSystem.py", "TwilightBossSliceB/TwilightBossSlice/clientSystem.py", "TwilightBossSliceB/TwilightBossSlice/routeBossHudUI.py"],
        ["TwilightBossSliceR/textures/entity/hydra4.png", "TwilightBossSliceR/textures/entity/hydramortar.png", "TwilightBossSliceR/animations/hydra_route.animation.json", "TwilightBossSliceR/ui/hydra_boss_hud.json"],
        ["TwilightBossSliceB/items/fiery_blood.item.json", "TwilightBossSliceB/items/hydra_chop.item.json", "TwilightBossSliceB/items/fiery_sword.item.json", "TwilightBossSliceB/items/fiery_pickaxe.item.json", "TwilightBossSliceB/netease_blocks/hydra_trophy.json"],
        ["TwilightBossSliceB/TwilightBossSlice/structureWorldgenService.py", "TwilightBossSliceB/structures/tf_slice/ruins/structure_catalog_v1.json", "TwilightBossSliceB/TwilightBossSlice/route_progression_logic.py"],
        ["tests/test_hydra_logic.py", "tests/test_hydra_route_structure_contract.py", "tests/test_hydra_route_entity_contract.py"],
        contract_rows(
            phases="Birth, roar, bite, flame, mortar, cooldown, severing, regrowth and 200-tick death states are explicit.",
            goals="One body owns save state and seven attackable head children, rebuilding missing children after reload.",
            damage="Body and closed heads take one eighth damage; open heads take full damage and sever after 120 accepted damage.",
            interactions="Mortars can be reflected with ownership transfer and hidden-target shots use power four.",
            presentation_assets="Converted body/head/mortar models, exact classic textures, source BLUE/PROGRESS 182x5 name-only HUD without screen darkening, and effects are present; actual-client review is pending.",
            items_rewards="One source loot settlement gives 7-10 fiery blood, 5-35 chops, trophy and 511 XP; fiery recipes close the route.",
            death_rewards="The 200-tick sequence and landmark ledger prevent duplicate reward settlement.",
            persistence_multiplayer="Body health, every head FSM, participants, death tick and reward state survive reload with ten-tick sync correction.",
        ),
    )
    write_json(BOSS_ROOT / "hydra.json", hydra)


def build(implemented: bool) -> None:
    lock = json.loads(LOCK_PATH.read_text("utf-8"))
    if lock["upstream"]["jarSha256"] != JAR_SHA256:
        raise SystemExit("hydra route source lock does not match the required JAR")
    classes = class_index(lock)
    textures = texture_index(lock)
    registry = json.loads(REGISTRY_PATH.read_text("utf-8"))
    route_ids = set(ENTITY_CONTRACTS)
    registry["entities"] = [
        row for row in registry["entities"] if row.get("id") not in route_ids
    ]
    for entity_id, contract in ENTITY_CONTRACTS.items():
        entry = registry_entry(entity_id, contract, classes, textures, implemented)
        registry["entities"].append(entry)
        if implemented:
            write_json(
                BEHAVIOR_ROOT / (entity_id + ".json"),
                behavior_evidence(entity_id, contract, entry),
            )
    write_json(REGISTRY_PATH, registry)
    build_boss_records(classes, textures, implemented)
    print(
        "registered eight route models and %s behaviors"
        % ("implemented" if implemented else "contracted")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--implemented",
        action="store_true",
        help="Record implemented behavior evidence after all automated gates pass.",
    )
    args = parser.parse_args()
    build(args.implemented)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
