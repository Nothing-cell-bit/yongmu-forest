#!/usr/bin/env python3
"""Register the source-derived Phantom/Ur-Ghast route model set."""

from __future__ import print_function

import hashlib
import json
from pathlib import Path

from build_phantom_urghast_models import build as build_route_models


ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
EXTRACTED = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
)
GEOMETRY_PATH = RP / "models" / "entity" / "phantom_urghast_route.geo.json"
REGISTRY_PATH = ROOT / "model_acceptance" / "registry.json"


SPECS = {
    "block_chain_goblin": {
        "group": "knight",
        "model": "twilightforest.client.model.entity.BlockChainGoblinModel",
        "modelPath": "twilightforest/client/model/entity/BlockChainGoblinModel.class",
        "entity": "twilightforest.entity.monster.BlockChainGoblin",
        "entityPath": "twilightforest/entity/monster/BlockChainGoblin.class",
        "renderer": "twilightforest.client.renderer.entity.BlockChainGoblinRenderer",
        "rendererPath": "twilightforest/client/renderer/entity/BlockChainGoblinRenderer.class",
        "texture": "assets/twilightforest/textures/model/blockgoblin.png",
    },
    "lower_goblin_knight": {
        "group": "knight",
        "model": "twilightforest.client.model.entity.LowerGoblinKnightModel",
        "modelPath": "twilightforest/client/model/entity/LowerGoblinKnightModel.class",
        "entity": "twilightforest.entity.monster.LowerGoblinKnight",
        "entityPath": "twilightforest/entity/monster/LowerGoblinKnight.class",
        "renderer": "twilightforest.client.renderer.entity.UpperGoblinKnightRenderer",
        "rendererPath": "twilightforest/client/renderer/entity/UpperGoblinKnightRenderer.class",
        "texture": "assets/twilightforest/textures/model/doublegoblin.png",
    },
    "upper_goblin_knight": {
        "group": "knight",
        "model": "twilightforest.client.model.entity.UpperGoblinKnightModel",
        "modelPath": "twilightforest/client/model/entity/UpperGoblinKnightModel.class",
        "entity": "twilightforest.entity.monster.UpperGoblinKnight",
        "entityPath": "twilightforest/entity/monster/UpperGoblinKnight.class",
        "renderer": "twilightforest.client.renderer.entity.UpperGoblinKnightRenderer",
        "rendererPath": "twilightforest/client/renderer/entity/UpperGoblinKnightRenderer.class",
        "texture": "assets/twilightforest/textures/model/doublegoblin.png",
    },
    "helmet_crab": {
        "group": "knight",
        "model": "twilightforest.client.model.entity.HelmetCrabModel",
        "modelPath": "twilightforest/client/model/entity/HelmetCrabModel.class",
        "entity": "twilightforest.entity.monster.HelmetCrab",
        "entityPath": "twilightforest/entity/monster/HelmetCrab.class",
        "texture": "assets/twilightforest/textures/model/helmetcrab.png",
    },
    "knight_phantom": {
        "group": "knight",
        "model": "twilightforest.client.model.entity.KnightPhantomModel",
        "modelPath": "twilightforest/client/model/entity/KnightPhantomModel.class",
        "entity": "twilightforest.entity.boss.KnightPhantom",
        "entityPath": "twilightforest/entity/boss/KnightPhantom.class",
        "renderer": "twilightforest.client.renderer.entity.KnightPhantomRenderer",
        "rendererPath": "twilightforest/client/renderer/entity/KnightPhantomRenderer.class",
        "texture": "assets/twilightforest/textures/model/phantomskeleton.png",
        "target": "TwilightBossSliceR/textures/entity/tf_slice/knight_phantom_skeleton.png",
        "textures": (
            (
                "assets/twilightforest/textures/model/phantomskeleton.png",
                "TwilightBossSliceR/textures/entity/tf_slice/knight_phantom_skeleton.png",
            ),
            (
                "assets/twilightforest/textures/armor/phantom_1.png",
                "TwilightBossSliceR/textures/entity/tf_slice/knight_phantom_armor.png",
            ),
        ),
        "layerClasses": (
            (
                "armor_model",
                "twilightforest.client.model.armor.PhantomArmorModel",
                "twilightforest/client/model/armor/PhantomArmorModel.class",
            ),
            (
                "armor_base_model",
                "twilightforest.client.model.armor.KnightmetalArmorModel",
                "twilightforest/client/model/armor/KnightmetalArmorModel.class",
            ),
            (
                "armor_item",
                "twilightforest.item.PhantomArmorItem",
                "twilightforest/item/PhantomArmorItem.class",
            ),
        ),
    },
    "knight_axe_projectile": {
        "group": "knight",
        "model": "twilightforest.client.renderer.entity.ThrownWepRenderer",
        "modelPath": "twilightforest/client/renderer/entity/ThrownWepRenderer.class",
        "entity": "twilightforest.entity.projectile.ThrownWep",
        "entityPath": "twilightforest/entity/projectile/ThrownWep.class",
        "texture": "assets/twilightforest/textures/item/knightmetal_axe.png",
        "target": "TwilightBossSliceR/textures/items/knightmetal_axe.png",
        "geometry": "TwilightBossSliceR/models/entity/knight_weapon_projectiles.geo.json",
        "geometryId": "geometry.tf_slice.knight_axe_projectile",
        "projectile": True,
    },
    "knight_pickaxe_projectile": {
        "group": "knight",
        "model": "twilightforest.client.renderer.entity.ThrownWepRenderer",
        "modelPath": "twilightforest/client/renderer/entity/ThrownWepRenderer.class",
        "entity": "twilightforest.entity.projectile.ThrownWep",
        "entityPath": "twilightforest/entity/projectile/ThrownWep.class",
        "texture": "assets/twilightforest/textures/item/knightmetal_pickaxe.png",
        "target": "TwilightBossSliceR/textures/items/knightmetal_pickaxe.png",
        "geometry": "TwilightBossSliceR/models/entity/knight_weapon_projectiles.geo.json",
        "geometryId": "geometry.tf_slice.knight_pickaxe_projectile",
        "projectile": True,
    },
    "block_chain_projectile": {
        "group": "knight",
        "model": "twilightforest.client.renderer.entity.BlockChainRenderer",
        "modelPath": "twilightforest/client/renderer/entity/BlockChainRenderer.class",
        "entity": "twilightforest.entity.ChainBlock",
        "entityPath": "twilightforest/entity/ChainBlock.class",
        "texture": "assets/twilightforest/textures/model/blockgoblin.png",
        "target": "TwilightBossSliceR/textures/entity/tf_slice/block_chain_goblin.png",
        "geometry": "TwilightBossSliceR/models/entity/block_chain_projectile.geo.json",
        "geometryId": "geometry.tf_slice.block_chain_projectile",
        "projectile": True,
    },
    "carminite_golem": {
        "group": "tower",
        "model": "twilightforest.client.model.entity.CarminiteGolemModel",
        "modelPath": "twilightforest/client/model/entity/CarminiteGolemModel.class",
        "entity": "twilightforest.entity.monster.CarminiteGolem",
        "entityPath": "twilightforest/entity/monster/CarminiteGolem.class",
        "renderer": "twilightforest.client.renderer.entity.CarminiteGolemRenderer",
        "rendererPath": "twilightforest/client/renderer/entity/CarminiteGolemRenderer.class",
        "texture": "assets/twilightforest/textures/model/carminitegolem.png",
    },
    "tower_broodling": {
        "group": "tower",
        "model": "net.minecraft.client.model.SpiderModel",
        "entity": "twilightforest.entity.monster.TowerBroodling",
        "entityPath": "twilightforest/entity/monster/TowerBroodling.class",
        "renderer": "twilightforest.client.renderer.entity.CarminiteBroodlingRenderer",
        "rendererPath": "twilightforest/client/renderer/entity/CarminiteBroodlingRenderer.class",
        "texture": "assets/twilightforest/textures/model/towerbroodling.png",
        "branch": "classic upstream SpiderModel; native Bedrock spider geometry contract",
        "builtinGeometry": "geometry.spider.v1.8",
    },
    "mini_ghast": {
        "group": "tower",
        "model": "twilightforest.client.model.entity.TFGhastModel",
        "modelPath": "twilightforest/client/model/entity/TFGhastModel.class",
        "entity": "twilightforest.entity.monster.CarminiteGhastling",
        "entityPath": "twilightforest/entity/monster/CarminiteGhastling.class",
        "renderer": "twilightforest.client.renderer.entity.CarminiteGhastRenderer",
        "rendererPath": "twilightforest/client/renderer/entity/CarminiteGhastRenderer.class",
        "texture": "assets/twilightforest/textures/model/towerghast.png",
        "textures": (
            ("assets/twilightforest/textures/model/towerghast.png", "TwilightBossSliceR/textures/entity/tf_slice/mini_ghast.png"),
            ("assets/twilightforest/textures/model/towerghast_openeyes.png", "TwilightBossSliceR/textures/entity/tf_slice/mini_ghast_open.png"),
            ("assets/twilightforest/textures/model/towerghast_fire.png", "TwilightBossSliceR/textures/entity/tf_slice/mini_ghast_attack.png"),
        ),
    },
    "tower_ghast": {
        "group": "tower",
        "model": "twilightforest.client.model.entity.TFGhastModel",
        "modelPath": "twilightforest/client/model/entity/TFGhastModel.class",
        "entity": "twilightforest.entity.monster.CarminiteGhastguard",
        "entityPath": "twilightforest/entity/monster/CarminiteGhastguard.class",
        "renderer": "twilightforest.client.renderer.entity.CarminiteGhastRenderer",
        "rendererPath": "twilightforest/client/renderer/entity/CarminiteGhastRenderer.class",
        "texture": "assets/twilightforest/textures/model/towerghast.png",
        "textures": (
            ("assets/twilightforest/textures/model/towerghast.png", "TwilightBossSliceR/textures/entity/tf_slice/tower_ghast.png"),
            ("assets/twilightforest/textures/model/towerghast_openeyes.png", "TwilightBossSliceR/textures/entity/tf_slice/tower_ghast_open.png"),
            ("assets/twilightforest/textures/model/towerghast_fire.png", "TwilightBossSliceR/textures/entity/tf_slice/tower_ghast_attack.png"),
        ),
    },
    "towerwood_borer": {
        "group": "tower",
        "model": "net.minecraft.client.model.SilverfishModel",
        "entity": "twilightforest.entity.monster.TowerwoodBorer",
        "entityPath": "twilightforest/entity/monster/TowerwoodBorer.class",
        "texture": "assets/twilightforest/textures/model/towertermite.png",
    },
    "ur_ghast": {
        "group": "tower",
        "model": "twilightforest.client.model.entity.newmodels.NewUrGhastModel",
        "modelPath": "twilightforest/client/model/entity/newmodels/NewUrGhastModel.class",
        "entity": "twilightforest.entity.boss.UrGhast",
        "entityPath": "twilightforest/entity/boss/UrGhast.class",
        "renderer": "twilightforest.client.renderer.entity.newmodels.NewUrGhastRenderer",
        "rendererPath": "twilightforest/client/renderer/entity/newmodels/NewUrGhastRenderer.class",
        "branch": "new/JAPPA; source-derived Bedrock conversion",
        # UrGhastRenderer has its own towerboss texture family; towerghast is
        # the smaller ghastling/ghastguard branch.
        "texture": "assets/twilightforest/textures/model/towerboss.png",
        "textures": (
            ("assets/twilightforest/textures/model/towerboss.png", "TwilightBossSliceR/textures/entity/tf_slice/ur_ghast.png"),
            ("assets/twilightforest/textures/model/towerboss_openeyes.png", "TwilightBossSliceR/textures/entity/tf_slice/ur_ghast_open.png"),
            ("assets/twilightforest/textures/model/towerboss_fire.png", "TwilightBossSliceR/textures/entity/tf_slice/ur_ghast_attack.png"),
        ),
    },
}

ORDER = tuple(SPECS)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _source_reference(path):
    return "../" + path.relative_to(ROOT.parent).as_posix()


def _hash_field(document, key, relative_path):
    if not relative_path:
        return
    path = EXTRACTED / relative_path
    if not path.is_file():
        raise SystemExit("missing locked model source: %s" % path)
    document[key] = _sha256(path)


def _registry_entry(identifier, spec):
    source_texture = EXTRACTED / spec["texture"]
    if not source_texture.is_file():
        raise SystemExit("missing locked texture source: %s" % source_texture)
    target = spec.get(
        "target", "TwilightBossSliceR/textures/entity/tf_slice/%s.png" % identifier
    )
    texture_pairs = spec.get("textures", ((spec["texture"], target),))
    source = {
        "model_class": spec["model"],
        "entity_class": spec["entity"],
        "model_branch": spec.get(
            "branch", "classic; source-derived Bedrock conversion"
        ),
        "textures": [
            {
                "source": _source_reference(EXTRACTED / source_name),
                "target": target_name,
                "sha256": _sha256(EXTRACTED / source_name),
            }
            for source_name, target_name in texture_pairs
        ],
    }
    _hash_field(source, "model_class_sha256", spec.get("modelPath"))
    _hash_field(source, "entity_class_sha256", spec.get("entityPath"))
    if spec.get("renderer"):
        source["renderer_class"] = spec["renderer"]
        _hash_field(source, "renderer_class_sha256", spec.get("rendererPath"))
    if spec.get("layerClasses"):
        source["renderer_layers"] = []
        for role, class_name, class_path in spec["layerClasses"]:
            path = EXTRACTED / class_path
            if not path.is_file():
                raise SystemExit("missing locked renderer layer source: %s" % path)
            source["renderer_layers"].append(
                {
                    "role": role,
                    "class": class_name,
                    "path": _source_reference(path),
                    "sha256": _sha256(path),
                }
            )
    builtin_geometry = spec.get("builtinGeometry")
    if spec.get("projectile"):
        geometry = spec.get(
            "geometry",
            "TwilightBossSliceR/models/entity/ruin_mobs.geo.json",
        )
        geometry_id = spec.get(
            "geometryId", "geometry.tf_slice.nature_bolt"
        )
    elif builtin_geometry:
        geometry = None
        geometry_id = builtin_geometry
    else:
        geometry = "TwilightBossSliceR/models/entity/phantom_urghast_route.geo.json"
        geometry_id = "geometry.tf_slice.%s" % identifier
    note = (
        "Exact classic source classes and textures are hash-locked. Source-derived "
        "geometry, animation, and offline six-view/four-pose evidence pass; "
        "cold-client acceptance remains pending."
    )
    if identifier == "ur_ghast":
        note = (
            "The rejected 2026-08-13 client captures are preserved under "
            "model_acceptance/failures. The retry now selects the locked "
            "new/JAPPA branch shown by the supplied original reference: a "
            "16px body with nine thicker, shorter, three-part tentacles, its "
            "source animation owner, exact towerboss textures, 12.5 renderer "
            "scale, 14x18 physical collision, and a 12.5x12.5 selectable "
            "head/body volume centered at Y 12.5. It remains rejected until "
            "a fresh cold-client review passes."
        )
    elif identifier == "knight_phantom":
        note = (
            "The repeated 2026-08-13 visual rejections are preserved under "
            "model_acceptance/failures. The retry now includes the locked "
            "phantom armor layer, a persistent skeleton-face backing behind "
            "the transparent visor, Mojang's [-6, 15, 1] humanoid rightItem "
            "pivot, and the Java held-item arm pose. It remains rejected "
            "until a fresh cold-client review passes."
        )
    elif identifier == "tower_broodling":
        note = (
            "The 2026-08-27 cold-client capture is preserved under "
            "model_acceptance/failures. The retry replaces the visually "
            "ambiguous custom SpiderModel conversion with Bedrock's native "
            "spider geometry and animation contract while retaining the "
            "locked texture and 0.7 renderer scale. It remains rejected "
            "until a fresh cold-client review passes."
        )
    elif identifier in ("mini_ghast", "tower_ghast"):
        note = (
            "The 2026-08-28 combat repair removed whole-body target "
            "pitch/yaw so the render remains aligned with its axis-aligned "
            "damage envelope. Previous look-up/look-down captures are "
            "stale; model remains rejected pending fresh cold-client views."
        )
    bedrock = {
        "identifier": geometry_id,
        "client_entity": "TwilightBossSliceR/entity/%s.entity.json" % identifier,
    }
    if builtin_geometry:
        bedrock["builtin_geometry"] = True
    else:
        bedrock["geometry"] = geometry
    return {
        "id": identifier,
        "status": (
            "converted"
            if spec.get("projectile")
            else "rejected"
            if identifier
            in (
                "knight_phantom",
                "tower_broodling",
                "mini_ghast",
                "tower_ghast",
                "ur_ghast",
            )
            else "candidate"
        ),
        "source": source,
        "bedrock": bedrock,
        "offline_evidence": (
            None
            if spec.get("projectile")
            else "model_acceptance/offline/%s.json" % identifier
        ),
        "evidence": "model_acceptance/evidence/%s.json" % identifier,
        "note": note,
    }


def sync_group(group):
    selected = [identifier for identifier in ORDER if SPECS[identifier]["group"] == group]
    if group not in ("knight", "tower"):
        raise ValueError("unknown route model group: %s" % group)

    build_route_models(group)

    registry = _read(REGISTRY_PATH)
    route_entries = {
        entry["id"]: entry
        for entry in registry["entities"]
        if entry.get("id") in SPECS
    }
    for identifier in selected:
        entry = _registry_entry(identifier, SPECS[identifier])
        if entry.get("offline_evidence") is None:
            entry.pop("offline_evidence", None)
        route_entries[identifier] = entry
    registry["entities"] = [
        entry for entry in registry["entities"] if entry.get("id") not in SPECS
    ] + [route_entries[identifier] for identifier in ORDER if identifier in route_entries]
    _write(REGISTRY_PATH, registry)
