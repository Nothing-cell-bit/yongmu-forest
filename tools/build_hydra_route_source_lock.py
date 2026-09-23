# -*- coding: utf-8 -*-
"""Build the reproducible source lock for the Labyrinth/Hydra route."""

from __future__ import print_function

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_ROOT = ROOT.parent / "twilightforest-1.20.1-4.3.2508-extracted" / "00_original_tree"
JAR = ROOT.parent / "[暮色森林] twilightforest-1.20.1-4.3.2508-universal.jar"
OUTPUT = ROOT / "source_locks" / "hydra_route.json"

CLASS_PATHS = (
    "twilightforest/entity/monster/Minotaur.class",
    "twilightforest/entity/boss/Minoshroom.class",
    "twilightforest/entity/monster/MazeSlime.class",
    "twilightforest/entity/monster/MosquitoSwarm.class",
    "twilightforest/entity/ai/goal/ChargeAttackGoal.class",
    "twilightforest/entity/ai/goal/GroundAttackGoal.class",
    "twilightforest/entity/boss/Hydra.class",
    "twilightforest/entity/boss/HydraHead.class",
    "twilightforest/entity/boss/HydraHeadContainer.class",
    "twilightforest/entity/boss/HydraHeadContainer$State.class",
    "twilightforest/entity/boss/HydraMortar.class",
    "twilightforest/entity/boss/HydraNeck.class",
    "twilightforest/entity/boss/HydraPart.class",
    "twilightforest/entity/boss/HydraSmallPart.class",
    "twilightforest/client/model/entity/MinotaurModel.class",
    "twilightforest/client/model/entity/MinoshroomModel.class",
    "twilightforest/client/model/entity/MosquitoSwarmModel.class",
    "twilightforest/client/model/entity/HydraModel.class",
    "twilightforest/client/model/entity/HydraHeadModel.class",
    "twilightforest/client/model/entity/HydraNeckModel.class",
    "twilightforest/client/model/entity/HydraMortarModel.class",
    "twilightforest/client/renderer/entity/MinoshroomRenderer.class",
    "twilightforest/client/renderer/entity/MazeSlimeRenderer.class",
    "twilightforest/client/renderer/entity/MosquitoSwarmRenderer.class",
    "twilightforest/client/renderer/entity/HydraRenderer.class",
    "twilightforest/client/renderer/entity/HydraHeadRenderer.class",
    "twilightforest/client/renderer/entity/HydraNeckRenderer.class",
    "twilightforest/client/renderer/entity/HydraMortarRenderer.class",
    "twilightforest/world/components/structures/type/LabyrinthStructure.class",
    "twilightforest/world/components/structures/minotaurmaze/MinotaurMazeComponent.class",
    "twilightforest/world/components/structures/HydraLairComponent.class",
    "twilightforest/world/components/structures/type/HydraLairStructure.class",
    "twilightforest/block/entity/spawner/MinoshroomSpawnerBlockEntity.class",
    "twilightforest/block/entity/spawner/HydraSpawnerBlockEntity.class",
    "twilightforest/init/custom/Restrictions.class",
    "twilightforest/init/custom/Enforcement.class",
    "twilightforest/enchantment/FireReactEnchantment.class",
    "twilightforest/item/MinotaurAxeItem.class",
    "twilightforest/item/MazebreakerPickItem.class",
    "twilightforest/item/HydraChopItem.class",
    "twilightforest/item/FierySwordItem.class",
    "twilightforest/item/FieryPickItem.class",
    "twilightforest/item/FieryArmorItem.class",
)

TEXTURES = (
    "minotaur.png",
    "minoshroomtaur.png",
    "mazeslime.png",
    "mosquitoswarm.png",
    "hydra4.png",
    "hydramortar.png",
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    missing = [path for path in CLASS_PATHS if not (UPSTREAM_ROOT / path).is_file()]
    if missing:
        raise SystemExit("missing locked classes: " + ", ".join(missing))
    texture_root = UPSTREAM_ROOT / "assets" / "twilightforest" / "textures" / "model"
    document = {
        "schemaVersion": 1,
        "route": "labyrinth_hydra",
        "upstream": {
            "version": "1.20.1-4.3.2508",
            "jar": str(JAR),
            "jarSha256": sha256(JAR),
            "modelBranch": "classic",
        },
        "classes": [
            {
                "class": path[:-6].replace("/", "."),
                "source": str(UPSTREAM_ROOT / path),
                "sha256": sha256(UPSTREAM_ROOT / path),
            }
            for path in CLASS_PATHS
        ],
        "textures": [
            {
                "source": str(texture_root / name),
                "target": "TwilightBossSliceR/textures/entity/" + name,
                "sha256": sha256(texture_root / name),
            }
            for name in TEXTURES
        ],
        "notes": {
            "audio": "No Twilight Forest audio is copied; use Minecraft built-ins or project-authored sounds.",
            "authority": "Class hashes and bundled data from the exact local JAR override prose and later branches.",
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote", OUTPUT)


if __name__ == "__main__":
    main()
