#!/usr/bin/env python3
"""Build the fail-closed source inventory for the Phantom/Ur-Ghast route."""

from __future__ import print_function

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
)
OUTPUT = ROOT / "source_locks" / "phantom_urghast_route.json"
EXPECTED_JAR_SHA256 = (
    "0BDC89263616D1B35C32EF82C5E9C14C"
    "BD20368E2FE8B468C72A28320BE7A778"
)
SOURCE_COMMIT = "a7dd8f13c653e137f977f5ffaa870fcb20fc1625"


# Each category owns an independent, reviewable set of exact JAR members.
# Globs are only expanded inside the locked extraction and empty categories
# fail the build. Overlap is intentional where one upstream asset serves two
# public contracts (for example an item model and its block model).
SELECTORS = {
    "structures": (
        "twilightforest/world/components/structures/stronghold/*.class",
        "twilightforest/world/components/structures/darktower/*.class",
        "twilightforest/world/components/structures/type/KnightStrongholdStructure.class",
        "twilightforest/world/components/structures/type/DarkTowerStructure.class",
        "data/twilightforest/worldgen/structure/knight_stronghold.json",
        "data/twilightforest/worldgen/structure/dark_tower.json",
        "data/twilightforest/worldgen/structure_set/knight_stronghold.json",
        "data/twilightforest/worldgen/structure_set/dark_tower.json",
    ),
    "entities": (
        "twilightforest/entity/boss/KnightPhantom*.class",
        "twilightforest/entity/boss/UrGhast*.class",
        "twilightforest/entity/monster/BlockChainGoblin*.class",
        "twilightforest/entity/monster/LowerGoblinKnight*.class",
        "twilightforest/entity/monster/UpperGoblinKnight*.class",
        "twilightforest/entity/monster/HelmetCrab*.class",
        "twilightforest/entity/monster/MistWolf*.class",
        "twilightforest/entity/monster/KingSpider*.class",
        "twilightforest/entity/monster/Carminite*.class",
        "twilightforest/entity/monster/TowerwoodBorer*.class",
        "twilightforest/entity/projectile/UrGhastFireball*.class",
        "twilightforest/entity/projectile/ThrownWep*.class",
        "twilightforest/entity/ChainBlock*.class",
        "twilightforest/entity/ai/goal/UrGhastFlightGoal*.class",
        "twilightforest/entity/ai/goal/ThrowSpikeBlockGoal*.class",
        "twilightforest/entity/ai/goal/ThrowRiderGoal*.class",
        "twilightforest/entity/ai/goal/RiderSpearAttackGoal*.class",
        "twilightforest/entity/ai/goal/GhastguardAttackGoal*.class",
        "twilightforest/entity/ai/goal/GhastguardRandomFlyGoal*.class",
        "twilightforest/entity/ai/goal/GhastguardHomedFlightGoal*.class",
        "twilightforest/entity/ai/goal/PhantomWatchAndAttackGoal*.class",
        "twilightforest/entity/ai/goal/PhantomUpdateFormationAndMoveGoal*.class",
        "twilightforest/entity/ai/goal/PhantomThrowWeaponGoal*.class",
        "twilightforest/entity/ai/goal/PhantomAttackStartGoal*.class",
    ),
    "blocks": (
        "twilightforest/block/TrophyPedestalBlock.class",
        "twilightforest/block/StrongholdShieldBlock.class",
        "twilightforest/block/KnightmetalBlock.class",
        "twilightforest/block/CarminiteReactorBlock.class",
        "twilightforest/block/CarminiteBlock.class",
        "twilightforest/block/BuilderBlock.class",
        "twilightforest/block/AntibuilderBlock.class",
        "twilightforest/block/InfestedTowerwoodBlock.class",
        "twilightforest/block/GhastTrapBlock.class",
        "twilightforest/block/Experiment115Block.class",
        "twilightforest/block/VanishingBlock.class",
        "twilightforest/block/ReappearingBlock.class",
        "twilightforest/block/LockedVanishingBlock.class",
        "twilightforest/block/entity/*GhastTrap*.class",
        "twilightforest/block/entity/*Carminite*.class",
        "twilightforest/block/entity/AntibuilderBlockEntity.class",
        "twilightforest/block/entity/spawner/KnightPhantomSpawnerBlockEntity.class",
        "twilightforest/block/entity/spawner/UrGhastSpawnerBlockEntity.class",
        "assets/twilightforest/blockstates/*underbrick*.json",
        "assets/twilightforest/blockstates/*towerwood*.json",
        "assets/twilightforest/blockstates/*vanishing*.json",
        "assets/twilightforest/blockstates/*carminite*.json",
        "assets/twilightforest/blockstates/experiment_115.json",
    ),
    "items": (
        "twilightforest/item/Knightmetal*.class",
        "twilightforest/item/ChainBlockItem.class",
        "twilightforest/item/Experiment115Item.class",
        "assets/twilightforest/textures/item/armor_shard*.png",
        "assets/twilightforest/textures/item/knightmetal*.png",
        "assets/twilightforest/textures/item/phantom_*.png",
        "assets/twilightforest/textures/item/tower_key.png",
        "assets/twilightforest/textures/item/borer_essence.png",
        "assets/twilightforest/textures/item/carminite.png",
        "assets/twilightforest/textures/item/fiery_tears.png",
        "assets/twilightforest/textures/item/charm_of_life_1.png",
        "assets/twilightforest/textures/item/experiment_115.png",
    ),
    "recipes": (
        "data/twilightforest/recipes/equipment/knightmetal*.json",
        "data/twilightforest/recipes/material/*knightmetal*.json",
        "data/twilightforest/recipes/compressed_blocks/*knightmetal*.json",
        "data/twilightforest/recipes/compressed_blocks/reversed/*knightmetal*.json",
        "data/twilightforest/recipes/stonecutting/towerwood/*.json",
        "data/twilightforest/recipes/*/*armor_shard*.json",
        "data/twilightforest/recipes/**/*experiment_115*.json",
    ),
    "lootTables": (
        "data/twilightforest/loot_tables/chests/stronghold*.json",
        "data/twilightforest/loot_tables/chests/darktower*.json",
        "data/twilightforest/loot_tables/entities/knight_phantom.json",
        "data/twilightforest/loot_tables/entities/ur_ghast.json",
        "data/twilightforest/loot_tables/entities/blockchain_goblin.json",
        "data/twilightforest/loot_tables/entities/*goblin_knight.json",
        "data/twilightforest/loot_tables/entities/helmet_crab.json",
        "data/twilightforest/loot_tables/entities/carminite*.json",
        "data/twilightforest/loot_tables/entities/towerwood_borer.json",
    ),
    "sounds": (
        "assets/twilightforest/sounds.json",
        "assets/twilightforest/sounds/**/*phantom*.ogg",
        "assets/twilightforest/sounds/**/*ur_ghast*.ogg",
        "assets/twilightforest/sounds/**/*urghast*.ogg",
        "assets/twilightforest/sounds/**/*carminite*.ogg",
        "assets/twilightforest/sounds/**/*tower*.ogg",
    ),
    "effects": (
        "twilightforest/client/renderer/TFWeatherRenderer.class",
        "twilightforest/client/particle/GhastTrapParticle.class",
        "twilightforest/block/entity/GhastTrapBlockEntity.class",
        "assets/twilightforest/particles/boss_tear.json",
        "assets/twilightforest/particles/ghast_trap.json",
        "assets/twilightforest/textures/environment/bigrain.png",
    ),
    "models": (
        "twilightforest/client/model/entity/KnightPhantomModel.class",
        "twilightforest/client/model/entity/UrGhastModel.class",
        "twilightforest/client/model/entity/Carminite*.class",
        "twilightforest/client/model/entity/*GoblinKnight*.class",
        "twilightforest/client/model/entity/BlockChainGoblinModel.class",
        "twilightforest/client/model/entity/HelmetCrabModel.class",
        "twilightforest/client/renderer/entity/KnightPhantomRenderer.class",
        "twilightforest/client/renderer/entity/UrGhastRenderer.class",
        "assets/twilightforest/textures/model/knightphantom.png",
        "assets/twilightforest/textures/model/towerboss*.png",
        "assets/twilightforest/textures/model/carminite*.png",
        "assets/twilightforest/textures/model/helmetcrab.png",
        "assets/twilightforest/models/item/knight_phantom*.json",
        "assets/twilightforest/models/item/ur_ghast*.json",
        "assets/twilightforest/models/item/knightmetal*.json",
        "assets/twilightforest/models/block/*towerwood*.json",
        "assets/twilightforest/models/block/*underbrick*.json",
    ),
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def find_jar():
    matches = sorted(
        ROOT.parent.glob("*twilightforest-1.20.1-4.3.2508-universal.jar")
    )
    if len(matches) != 1:
        raise SystemExit("expected exactly one locked Twilight Forest JAR")
    return matches[0]


def expand_category(category, selectors):
    paths = set()
    unmatched = []
    for selector in selectors:
        matches = [path for path in UPSTREAM.glob(selector) if path.is_file()]
        if not matches and "*" not in selector:
            unmatched.append(selector)
        paths.update(matches)
    if unmatched:
        raise SystemExit(
            "%s missing exact sources: %s" % (category, ", ".join(unmatched))
        )
    if not paths:
        raise SystemExit("%s source inventory is empty" % category)
    return [
        {
            "path": path.relative_to(UPSTREAM).as_posix(),
            "sha256": sha256(path),
        }
        for path in sorted(paths, key=lambda value: value.as_posix())
    ]


def build_document():
    jar = find_jar()
    actual_jar_hash = sha256(jar)
    if actual_jar_hash != EXPECTED_JAR_SHA256:
        raise SystemExit(
            "locked JAR mismatch: expected %s, got %s"
            % (EXPECTED_JAR_SHA256, actual_jar_hash)
        )
    return {
        "schemaVersion": 3,
        "route": "phantom_knights_ur_ghast",
        "source": {
            "version": "1.20.1-4.3.2508",
            "jar": jar.name,
            "jarSha256": actual_jar_hash,
            "sourceCommit": SOURCE_COMMIT,
            "authority": "JAR bytecode, bundled JSON and resource hashes override source prose",
        },
        "inventories": {
            category: expand_category(category, selectors)
            for category, selectors in sorted(SELECTORS.items())
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build_document(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("phantom/ur-ghast source lock is stale")
        print("phantom/ur-ghast source lock verified")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print("wrote", OUTPUT)


if __name__ == "__main__":
    main()
