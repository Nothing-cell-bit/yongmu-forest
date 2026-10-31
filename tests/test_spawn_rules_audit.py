"""Source-backed spawn eligibility and real service-entry regressions."""
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from tests.test_portal_arrival_runtime import SERVER
from tests.test_structure_worldgen_handoff import SERVICE, FakeFactory


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK = json.loads((ROOT / "source_locks/phantom_urghast_route.json").read_text(encoding="utf-8"))
SOURCE_JAR = ROOT.parent / SOURCE_LOCK["source"]["jar"]
DIMENSION = 33027004
CATALOG = SERVICE.biome_catalog
NATIVE_BIOMES = list(CATALOG.BIOMES_BY_KEY)


def locked_json(path):
    with ZipFile(SOURCE_JAR) as archive:
        return json.loads(archive.read("data/twilightforest/" + path))


@pytest.mark.parametrize("key", NATIVE_BIOMES)
def test_native_vanilla_eligibility_matches_locked_biome_through_server_hook(key):
    source = locked_json("worldgen/biome/" + key + ".json")
    expected = {entry["type"] for entries in source["spawners"].values()
                for entry in entries if entry["type"].startswith("minecraft:")}
    if key in ("dark_forest", "spooky_forest", "swamp"):
        # Monster categories now have an explicit source-checked script pool;
        # ambient bats remain native. Do not allow a second inherited pool.
        expected = {entry["type"] for entry in source["spawners"]["ambient"]}
    biome = CATALOG.BIOMES_BY_KEY[key]["identifier"]
    system = object.__new__(SERVER.ServerSystem)

    class BiomeBoundary:
        def GetBiomeName(self, position, dimension):
            assert position == (-8, 64, 16) and dimension == DIMENSION
            return biome

    system._biome_comp = BiomeBoundary()
    system._block_comp = type("BlockBoundary", (), {"GetBlockNew": lambda self, pos, dim: {"name": "minecraft:stone"}})()
    for identifier in ("minecraft:chicken", "minecraft:wolf", "minecraft:zombie",
                       "minecraft:spider", "minecraft:skeleton", "minecraft:bat",
                       "minecraft:creeper", "minecraft:witch"):
        args = {"identifier": identifier, "realIdentifier": identifier,
                "dimensionId": DIMENSION, "x": -8, "y": 64, "z": 16}
        system.OnServerSpawnMob(args)
        assert args.get("cancel", False) == (identifier not in expected), (key, identifier)


def labyrinth_scene():
    factory = FakeFactory()
    spawned = []

    def create(identifier, position, yaw, dimension):
        spawned.append((identifier, position, yaw, dimension))
        return "spawned-%d" % len(spawned)

    service = SERVICE.StructureWorldgenService(factory, "level", DIMENSION, create)
    factory.block.GetBlockNew = lambda position, dimension: {
        "name": "tf_slice:mazestone_mosaic" if position[1] == 11 else "minecraft:air",
        "aux": 0,
    }
    service._ledger = {"audit-labyrinth": {
        "kind": "labyrinth", "state": "complete", "center": [55, 55],
        "anchor": [0, 0, 0], "bounds": [0, 0, 0, 110, 53, 110],
        "controlledSpawns": {"cap": 18, "intervalTicks": 100, "weights": [
            {"entity": "tf_slice:minotaur", "weight": 20, "group": [2, 3]}]},
        "markers": {"spawnZones": [{"level": 0, "center": [55, 12, 55], "radius": 7}]},
    }}
    service._rebuild_runtime_job_indexes()
    players = [{"dimensionId": DIMENSION, "position": [85.5, 12, 55.5], "progress": {}}]
    return service, players, spawned


def test_peaceful_tick_never_creates_structure_monsters_or_spends_spawn_cooldown():
    service, players, spawned = labyrinth_scene()
    for tick in range(100, 4001, 100):
        service.tick(tick, players, boss_spawning_enabled=False)
    assert spawned == []
    assert service._controlled_spawn_next_ticks == {}


def test_same_structure_can_spawn_after_leaving_peaceful():
    service, players, spawned = labyrinth_scene()
    service.tick(100, players, boss_spawning_enabled=False)
    assert spawned == []
    for tick in range(200, 4201, 100):
        service.tick(tick, players, boss_spawning_enabled=True)
    assert spawned
    assert all(call[0] == "tf_slice:minotaur" and call[3] == DIMENSION for call in spawned)


def test_peaceful_dark_tower_still_spawns_water_creatures_through_tick():
    service, players, spawned = labyrinth_scene()
    service._ledger = {"audit-water": {
        "kind": "dark_tower", "state": "complete", "center": [55, 55],
        "anchor": [0, 0, 0], "bounds": [0, 0, 0, 110, 53, 110],
        "controlledSpawns": {"tiers": {
            "water": [{"entity": "minecraft:squid", "weight": 10, "group": [1, 1]}],
            "lower": [{"entity": "tf_slice:carminite_golem", "weight": 10, "group": [1, 1]}],
        }},
    }}
    service._rebuild_runtime_job_indexes()
    service._factory.block.GetBlockNew = lambda position, dimension: {"name": "minecraft:water", "aux": 0}
    for tick in range(100, 4001, 100):
        service.tick(tick, players, boss_spawning_enabled=False)
    assert spawned
    assert all(call[0] == "minecraft:squid" for call in spawned)


def source_rows(entries):
    aliases = {"blockchain_goblin": "block_chain_goblin", "carminite_ghastling": "mini_ghast",
               "carminite_ghastguard": "tower_ghast", "carminite_broodling": "tower_broodling"}
    rows = []
    for entry in entries:
        namespace, name = entry["type"].split(":", 1)
        identifier = ("tf_slice:" + aliases.get(name, name)
                      if namespace == "twilightforest" else entry["type"])
        rows.append((identifier, entry["weight"], entry["minCount"], entry["maxCount"]))
    return sorted(rows)


@pytest.mark.parametrize("kind,source_name", [
    ("small_hill", "small_hollow_hill"), ("medium_hill", "medium_hollow_hill"),
    ("large_hill", "large_hollow_hill"),
])
def test_hill_spawn_pools_match_locked_jar(kind, source_name):
    source = locked_json("worldgen/structure/" + source_name + ".json")
    assert sorted(SERVICE.ruin_logic.HOLLOW_HILL_CONTROLLED_SPAWNS[kind]) == source_rows(
        source["labelled_monster_spawns"]["0"])


@pytest.mark.parametrize("kind,tiers", [
    ("lich_tower", {"weights": "0"}), ("labyrinth", {"weights": "0"}),
    ("knight_stronghold", {"stronghold": "0"}),
    ("dark_tower", {"lower": "0", "roof": "1", "water": "water"}),
])
def test_structure_catalog_spawn_pools_match_locked_jar(kind, tiers):
    source = locked_json("worldgen/structure/" + kind + ".json")
    target = SERVICE._load_catalog()[kind]["controlledSpawns"]
    for tier, source_key in tiers.items():
        entries = target["weights"] if tier == "weights" else target["tiers"][tier]
        expected = source["water_spawns"] if source_key == "water" else source["labelled_monster_spawns"][source_key]
        assert sorted((e["entity"], e["weight"], e["group"][0], e["group"][1]) for e in entries) == source_rows(expected)


def test_dark_forest_controlled_pool_matches_locked_jar():
    source = locked_json("worldgen/biome/dark_forest.json")
    assert sorted(SERVICE.DARK_FOREST_CONTROLLED_SPAWNS) == source_rows(source["spawners"]["monster"])


@pytest.mark.parametrize("path", sorted((ROOT / "TwilightBossSliceB/spawn_rules").glob("*.json")), ids=lambda p: p.stem)
def test_declared_native_spawn_weights_and_group_sizes_match_locked_biome(path):
    rule = json.loads(path.read_text())["minecraft:spawn_rules"]
    for condition in rule["conditions"]:
        tags = {term.get("value") for term in condition["minecraft:biome_filter"]["all_of"]}
        key = next((key for key in CATALOG.BIOMES_BY_KEY if "tf_slice_biome_" + key in tags), "forest")
        source = locked_json("worldgen/biome/" + key + ".json")
        source_entries = [entry for entries in source["spawners"].values() for entry in entries]
        expected = next(row for row in source_rows(source_entries) if row[0] == rule["description"]["identifier"])
        assert (rule["description"]["identifier"], condition["minecraft:weight"]["default"],
                condition["minecraft:herd"]["min_size"], condition["minecraft:herd"]["max_size"]) == expected
