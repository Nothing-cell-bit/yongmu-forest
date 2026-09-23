#!/usr/bin/env python3
"""Compile the locked Phantom Knight and Ur-Ghast route structures.

The Java mod assembles these landmarks from procedural components.  Bedrock
cannot run that assembler during chunk generation, so this module compiles the
two release layouts up front and emits small, restart-safe structure slices.
"""

from __future__ import print_function

import hashlib
import json


SOURCE_COMMIT = "a7dd8f13c653e137f977f5ffaa870fcb20fc1625"
VERTICAL_SLICE_HEIGHT = 64
STRONGHOLD_ENTRY_Y = 52
DARK_TOWER_SURFACE_GROUND_Y = 16
DARK_TOWER_DECORATION_VARIANT_COUNT = 2


STRONGHOLD_SPAWNS = (
    ("tf_slice:block_chain_goblin", 10, (1, 2)),
    ("tf_slice:lower_goblin_knight", 5, (1, 2)),
    ("tf_slice:helmet_crab", 10, (2, 4)),
    ("tf_slice:slime_beetle", 10, (2, 3)),
    ("tf_slice:redcap_sapper", 2, (1, 2)),
    ("tf_slice:kobold", 10, (2, 4)),
    ("minecraft:creeper", 5, (1, 2)),
    ("minecraft:slime", 5, (4, 4)),
)


def _stable_layout_hash(structure, markers, graph):
    blocks = []
    for position, value in sorted(structure.blocks.items()):
        blocks.append(
            [list(position), value[0], sorted(value[1].items()), value[2]]
        )
    payload = {
        "blocks": blocks,
        "entities": sorted(structure.entities),
        "markers": markers,
        "graph": graph,
    }
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _shift(position):
    return [int(position[0]), int(position[1]) - STRONGHOLD_ENTRY_Y, int(position[2])]


def _fill_shell(structure, center, radius, floor_y=8, roof_y=14):
    cx, cz = center
    for x in range(cx - radius, cx + radius + 1):
        for z in range(cz - radius, cz + radius + 1):
            edge = x in (cx - radius, cx + radius) or z in (
                cz - radius,
                cz + radius,
            )
            structure.set(x, floor_y, z, "tf_slice:underbrick_floor")
            structure.set(
                x,
                roof_y,
                z,
                "tf_slice:mossy_underbrick" if (x + z) % 11 == 0 else "tf_slice:underbrick",
            )
            if edge:
                for y in range(floor_y + 1, roof_y):
                    palette = (
                        "tf_slice:cracked_underbrick"
                        if (x * 13 + y * 7 + z) % 17 == 0
                        else "tf_slice:underbrick"
                    )
                    structure.set(x, y, z, palette)
            else:
                # The stronghold is placed below an already solid surface.
                # Native placement therefore needs explicit authored air for
                # every room, matching the old remove-block template path.
                for y in range(floor_y + 1, roof_y):
                    structure.set(x, y, z, "minecraft:air")


def _corridor(structure, start, end):
    """Render a three-wide, source-height Manhattan connector."""
    x, z = start
    end_x, end_z = end
    points = []
    step_x = 1 if end_x >= x else -1
    while x != end_x:
        points.append((x, z))
        x += step_x
    step_z = 1 if end_z >= z else -1
    while z != end_z:
        points.append((x, z))
        z += step_z
    points.append((x, z))
    for x, z in points:
        for dx in (-2, -1, 0, 1, 2):
            for dz in (-2, -1, 0, 1, 2):
                distance = abs(dx) + abs(dz)
                if distance <= 2:
                    structure.set(x + dx, 8, z + dz, "tf_slice:underbrick_floor")
                    structure.set(x + dx, 14, z + dz, "tf_slice:underbrick")
                    for y in range(9, 14):
                        if distance == 2:
                            structure.set(x + dx, y, z + dz, "tf_slice:underbrick")
                        else:
                            structure.set(x + dx, y, z + dz, "minecraft:air")


def _layout(seed):
    # The room dimensions and source component roles are locked to the Java
    # implementation.  Only these two authored graph selections are shipped.
    if int(seed) == 0:
        rooms = {
            "entry": (56, 24),
            "crossing": (56, 40),
            "training": (40, 40),
            "balcony": (72, 40),
            "atrium": (40, 56),
            "foundry": (72, 56),
            "treasure": (40, 72),
            "stairs": (56, 72),
            "boss": (56, 94),
        }
        edges = (
            ("entry", "crossing"),
            ("crossing", "training"),
            ("crossing", "balcony"),
            ("training", "atrium"),
            ("balcony", "foundry"),
            ("atrium", "treasure"),
            ("treasure", "stairs"),
            ("stairs", "boss"),
            ("foundry", "stairs"),
        )
    elif int(seed) == 1:
        rooms = {
            "entry": (56, 24),
            "crossing": (56, 40),
            "training": (40, 40),
            "balcony": (72, 40),
            "atrium": (40, 56),
            "foundry": (72, 56),
            "treasure": (40, 72),
            "stairs": (56, 72),
            "boss": (82, 82),
        }
        edges = (
            ("entry", "crossing"),
            ("crossing", "training"),
            ("crossing", "balcony"),
            ("training", "atrium"),
            ("atrium", "treasure"),
            ("treasure", "stairs"),
            ("balcony", "foundry"),
            ("foundry", "boss"),
            ("stairs", "boss"),
        )
    else:
        raise ValueError("only locked stronghold layout seeds 0 and 1 are releasable")
    return rooms, edges


def _reachable(edges, start):
    adjacency = {}
    for left, right in edges:
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)
    seen = set((start,))
    pending = [start]
    while pending:
        current = pending.pop()
        for neighbor in adjacency.get(current, ()):
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    return seen


def _render_stronghold_placeholder(seed, api):
    SparseStructure = api["SparseStructure"]
    set_loot_container = api["set_loot_container"]
    set_spawner = api["set_spawner"]
    structure = SparseStructure((112, 32, 112), "knight_stronghold_%d" % seed)
    rooms, edges = _layout(seed)
    for left, right in edges:
        _corridor(structure, rooms[left], rooms[right])
    for kind, center in rooms.items():
        _fill_shell(structure, center, 13 if kind == "boss" else 6, 6 if kind == "boss" else 8, 14)

    # Buried entry: only this compact access chamber reaches local surface Y.
    for y in range(25, STRONGHOLD_ENTRY_Y + 1):
        for x in range(52, 61):
            for z in range(4, 13):
                edge = x in (52, 60) or z in (4, 12) or y in (25, STRONGHOLD_ENTRY_Y)
                if edge:
                    structure.set(x, y, z, "tf_slice:underbrick")
                else:
                    structure.set(x, y, z, "minecraft:air")
    for step in range(14):
        z = 11 + step
        y = 25 - step
        for x in range(54, 59):
            structure.set(x, y, z, "tf_slice:underbrick_floor")
            structure.set(x, y + 4, z, "tf_slice:underbrick")
            structure.set(53, y + 1, z, "tf_slice:underbrick")
            structure.set(59, y + 1, z, "tf_slice:underbrick")

    pedestal = (54, 26, 8)
    structure.set(*pedestal, name="tf_slice:trophy_pedestal")
    shield_positions = []
    for x in range(53, 60):
        for y in range(20, 25):
            position = (x, y, 14)
            structure.set(*position, name="tf_slice:stronghold_shield")
            shield_positions.append(_shift(position))

    boss = rooms["boss"]
    boss_marker = (boss[0], 8, boss[1])
    structure.set(*boss_marker, name="tf_slice:knight_phantom_boss_spawner")
    loot_positions = []
    for index, room_name in enumerate(("training", "atrium", "treasure")):
        cx, cz = rooms[room_name]
        position = (cx, 9, cz)
        set_loot_container(
            structure,
            position[0],
            position[1],
            position[2],
            ("stronghold_cache", "stronghold_room", "stronghold_boss")[index],
        )
        loot_positions.append(_shift(position))
    spawner_positions = []
    spawner_entities = (
        "tf_slice:block_chain_goblin",
        "tf_slice:lower_goblin_knight",
        "tf_slice:helmet_crab",
    )
    for room_name, entity in zip(("crossing", "balcony", "foundry"), spawner_entities):
        cx, cz = rooms[room_name]
        position = (cx + 2, 9, cz + 2)
        set_spawner(structure, position[0], position[1], position[2], entity)
        spawner_positions.append({"offset": _shift(position), "entity": entity})

    graph = [[left, right] for left, right in edges]
    reached = _reachable(edges, "entry")
    markers = {
        "surfaceEntrance": {"offset": _shift((56, STRONGHOLD_ENTRY_Y, 8)), "block": "tf_slice:underbrick"},
        "trophyPedestal": {"offset": _shift(pedestal), "block": "tf_slice:trophy_pedestal"},
        "shieldWalls": shield_positions,
        "bossRoom": {"offset": _shift((boss[0], 7, boss[1])), "radius": 13},
        "bossGroupSpawner": {"offset": _shift(boss_marker), "block": "tf_slice:knight_phantom_boss_spawner"},
        "lootChests": loot_positions,
        "structureSpawners": spawner_positions,
    }
    validation = {
        "entranceReachable": "entry" in reached,
        "bossRoomReachable": "boss" in reached,
        "allLootReachable": all(value in reached for value in ("training", "atrium", "treasure")),
        "roofComplete": all(
            (center[0], 14, center[1]) in structure.blocks
            for center in rooms.values()
        ),
        "forbiddenBlocks": sorted(
            set(value[0] for value in structure.blocks.values())
            & set(api["FORBIDDEN_OUTPUT_BLOCKS"])
        ),
    }
    if not all(validation[key] for key in ("entranceReachable", "bossRoomReachable", "allLootReachable", "roofComplete")):
        raise ValueError("stronghold layout %d failed reachability validation" % seed)
    if validation["forbiddenBlocks"]:
        raise ValueError("stronghold layout contains forbidden blocks")
    # Only the small access chamber reaches the forest floor.  The rest of
    # the stronghold remains below untouched native terrain, so the generic
    # surface-native baker must not flatten the full 112x112 footprint.
    structure.surface_ground_y = STRONGHOLD_ENTRY_Y
    structure.surface_core_center = (56, 8)
    structure.surface_core_radius = 5
    structure.surface_columns = {
        (x, z): STRONGHOLD_ENTRY_Y
        for x in range(52, 61)
        for z in range(4, 13)
    }
    return structure, markers, validation, graph


def _render_stronghold(seed, api):
    """Compatibility entry point backed by the source component port."""
    try:
        import knight_stronghold_legacy_port as stronghold_port
    except ImportError:  # pragma: no cover - package import in tests
        from tools import knight_stronghold_legacy_port as stronghold_port
    structure, markers, validation, graph, _source_port = (
        stronghold_port.render_stronghold(seed, api, STRONGHOLD_ENTRY_Y)
    )
    return structure, markers, validation, graph


def _write_vertical_slices(relative_root, structure, vertical_offset, api):
    SparseStructure = api["SparseStructure"]
    write_single = api["write_single"]
    pieces = []
    for start_y in range(0, structure.size[1], VERTICAL_SLICE_HEIGHT):
        for start_x in range(0, structure.size[0], 16):
            for start_z in range(0, structure.size[2], 16):
                size_x = min(16, structure.size[0] - start_x)
                size_y = min(VERTICAL_SLICE_HEIGHT, structure.size[1] - start_y)
                size_z = min(16, structure.size[2] - start_z)
                tile = SparseStructure(
                    (size_x, size_y, size_z),
                    "%s/y%03d_x%03d_z%03d" % (relative_root, start_y, start_x, start_z),
                )
                for (x, y, z), block in structure.blocks.items():
                    if (
                        start_x <= x < start_x + size_x
                        and start_y <= y < start_y + size_y
                        and start_z <= z < start_z + size_z
                    ):
                        tile.set(x - start_x, y - start_y, z - start_z, block[0], block[1], block[2])
                for x, y, z, identifier, yaw in structure.entities:
                    if (
                        start_x <= x < start_x + size_x
                        and start_y <= y < start_y + size_y
                        and start_z <= z < start_z + size_z
                    ):
                        tile.add_entity(x - start_x, y - start_y, z - start_z, identifier, yaw)
                if not tile.blocks and not tile.entities:
                    continue
                offset = [start_x, int(vertical_offset) + start_y, start_z]
                piece = write_single(tile.name, tile, offset)
                piece["recoveryOrder"] = [offset[1], offset[0], offset[2]]
                pieces.append(piece)
    return sorted(pieces, key=lambda value: tuple(value["recoveryOrder"]))


def build_knight_stronghold_entry(api):
    try:
        import knight_stronghold_legacy_port as stronghold_port
    except ImportError:  # pragma: no cover - package import in tests
        from tools import knight_stronghold_legacy_port as stronghold_port
    variants = []
    # Four full recursive layouts stay within the release's native-template
    # byte cap.  Component counts now follow the source depth/range limits
    # instead of the former add-on-specific expansion cap.
    profiles = [
        (seed, "seed_%d" % seed, 2, 2)
        for seed in range(4)
    ] + [
        (seed, "seed_%d_raised" % seed, -2, 1)
        for seed in range(4)
    ]
    for seed, variant_id, access_floor_depth, weight in profiles:
        structure, markers, validation, graph, source_port = (
            stronghold_port.render_stronghold(
                seed,
                api,
                STRONGHOLD_ENTRY_Y,
                access_floor_depth=access_floor_depth,
            )
        )
        pieces = _write_vertical_slices(
            "knight_stronghold/%s" % variant_id,
            structure,
            -int(structure.surface_ground_y),
            api,
        )
        variants.append(
            {
                "id": variant_id,
                "weight": weight,
                "layoutSeed": seed,
                "layoutSha256": _stable_layout_hash(structure, markers, graph),
                "sourceCommit": stronghold_port.SOURCE_COMMIT,
                "sourcePort": source_port,
                "bounds": api["combined_bounds"](pieces),
                "pieces": pieces,
                "markers": markers,
                "validation": validation,
                "roomGraph": graph,
                "surfaceNative": api["write_surface_native_tiles"](
                    "knight_stronghold",
                    variant_id,
                    structure,
                    seed,
                ),
            }
        )

    controlled = [
        {"entity": entity, "weight": weight, "group": list(group)}
        for entity, weight, group in STRONGHOLD_SPAWNS
    ]
    return api["catalog_entry"](
        "knight_stronghold",
        "landmark_service",
        ["dm33027004", "tf_slice_dark_forest"],
        variants[0]["pieces"],
        dependencies=[
            "trophy_pedestal",
            "stronghold_shield",
            "knight_phantom",
            "stronghold_loot",
        ],
        post_processors=["loot_and_spawner_markers", "boss_group_spawner"],
        variants=variants,
        landmarkKind="knight_stronghold",
        layoutStrategy="procedural_component_port",
        componentGrammar={
            "lower": list(stronghold_port.LOWER_GRAMMAR),
            "upper": list(stronghold_port.UPPER_GRAMMAR),
        },
        sourceClasses=list(stronghold_port.SOURCE_CLASSES),
        placementProfile="buried_entry",
        entrySurfaceOffset=0,
        verticalSliceHeight=VERTICAL_SLICE_HEIGHT,
        structureLockObjective="trophy_pedestal_activated",
        clearanceChunks=3,
        recoveryOrder=["y", "x", "z"],
        controlledSpawns={"tiers": {"stronghold": controlled}},
        bossGroupSpawner={
            "kind": "knight_phantoms",
            "entity": "tf_slice:knight_phantom",
            "markerBlock": "tf_slice:knight_phantom_boss_spawner",
            "count": 6,
            "ringRadius": 4,
            "homeRadius": 30,
            "memberNumbers": list(range(6)),
        },
    )


def _render_tower_shell(structure, bounds, bottom_y, top_y):
    minimum_x, minimum_z, maximum_x, maximum_z = bounds
    for y in range(bottom_y, top_y + 1):
        for x in range(minimum_x, maximum_x + 1):
            for z in (minimum_z, maximum_z):
                structure.set(x, y, z, "tf_slice:towerwood")
        for z in range(minimum_z + 1, maximum_z):
            for x in (minimum_x, maximum_x):
                structure.set(x, y, z, "tf_slice:towerwood")
    for level in range(bottom_y, top_y + 1, 12):
        for x in range(minimum_x, maximum_x + 1):
            for z in range(minimum_z, maximum_z + 1):
                if (x, z) == (minimum_x + 2, minimum_z + 2):
                    continue
                palette = (
                    "tf_slice:cracked_towerwood"
                    if (x * 5 + z * 3 + level) % 23 == 0
                    else "tf_slice:mossy_towerwood"
                    if (x + z + level) % 31 == 0
                    else "tf_slice:towerwood"
                )
                structure.set(x, level, z, palette)
    for y in range(bottom_y + 1, top_y):
        structure.set(minimum_x + 2, y, minimum_z + 1, "minecraft:ladder", {"facing_direction": 3})


def _render_dark_tower_placeholder(seed, api):
    SparseStructure = api["SparseStructure"]
    set_loot_container = api["set_loot_container"]
    set_spawner = api["set_spawner"]
    structure = SparseStructure((64, 192, 64), "dark_tower_%d" % seed)
    main = (20, 20, 43, 43)
    tower_top = 180
    _render_tower_shell(structure, main, 0, tower_top)
    # The fixed layouts preserve different side-wing/bridge selections.
    wing = (44, 24, 62, 39) if int(seed) == 0 else (1, 24, 19, 39)
    _render_tower_shell(structure, wing, 0, 72)
    bridge_x = range(40, 46) if int(seed) == 0 else range(18, 24)
    for x in bridge_x:
        for z in range(28, 36):
            structure.set(x, 36, z, "tf_slice:encased_towerwood")
            structure.set(x, 41, z, "tf_slice:encased_towerwood")
            if z in (28, 35):
                for y in range(37, 41):
                    structure.set(x, y, z, "tf_slice:towerwood")

    # Ground entrance and a source-style locked vertical key route.
    for x in range(28, 36):
        for y in range(1, 6):
            structure.set(x, y, 20, "minecraft:air")
    key_doors = []
    key_chests = []
    mechanisms = []
    loot_chests = []
    for index, level in enumerate((48, 96, 144)):
        door = (31, level + 1, 22)
        for dx in (-1, 0, 1):
            for dy in range(4):
                structure.set(door[0] + dx, door[1] + dy, door[2], "tf_slice:tower_key_door")
        key_doors.append({"offset": list(door), "block": "tf_slice:tower_key_door", "keyIndex": index})
        chest = (38 if index % 2 == 0 else 25, level - 10, 38)
        set_loot_container(structure, chest[0], chest[1], chest[2], "dark_tower_key")
        key_chests.append(list(chest))
        cache = (25, level + 2, 38 if index % 2 == 0 else 25)
        set_loot_container(structure, cache[0], cache[1], cache[2], "dark_tower_cache")
        loot_chests.append(list(cache))

    mechanism_data = (
        ((26, 25, 26), "tf_slice:carminite_builder"),
        ((38, 61, 38), "tf_slice:carminite_antibuilder"),
        ((26, 109, 38), "tf_slice:carminite_reactor"),
        ((38, 133, 26), "tf_slice:experiment_115"),
        ((31, 157, 31), "tf_slice:reappearing_block"),
    )
    for position, block in mechanism_data:
        structure.set(*position, name=block)
        mechanisms.append({"offset": list(position), "block": block})

    # Tower inhabitants are catalog-controlled, while these physical spawners
    # preserve room identity and remain easy to audit in the compiled layout.
    spawner_markers = []
    for position, entity in (
        ((27, 14, 27), "tf_slice:tower_broodling"),
        ((37, 74, 37), "tf_slice:carminite_golem"),
        ((27, 122, 37), "tf_slice:towerwood_borer"),
        ((37, 158, 27), "tf_slice:tower_ghast"),
    ):
        set_spawner(structure, position[0], position[1], position[2], entity)
        spawner_markers.append({"offset": list(position), "entity": entity})

    # The roof and the main boss platform are never truncated independently.
    for x in range(17, 47):
        for z in range(17, 47):
            structure.set(x, tower_top, z, "tf_slice:encased_towerwood")
            if x in (17, 46) or z in (17, 46):
                structure.set(x, tower_top + 1, z, "tf_slice:towerwood")
                structure.set(x, tower_top + 2, z, "tf_slice:towerwood")
    traps = []
    for position in ((21, 181, 21), (42, 181, 42)):
        structure.set(*position, name="tf_slice:ghast_trap", states={"tf_slice:active": False})
        traps.append({"offset": list(position), "block": "tf_slice:ghast_trap"})
    boss_spawner = (32, 181, 32)
    structure.set(*boss_spawner, name="tf_slice:ur_ghast_boss_spawner")

    markers = {
        "surfaceEntrance": {"offset": [32, 1, 20], "block": "minecraft:air"},
        "keyDoors": key_doors,
        "keyChests": key_chests,
        "mechanisms": mechanisms,
        "ghastTraps": traps,
        "bossPlatform": {"offset": [32, tower_top, 32], "radius": 15},
        "urGhastSpawner": {"offset": list(boss_spawner), "block": "tf_slice:ur_ghast_boss_spawner"},
        "lootChests": loot_chests,
        "structureSpawners": spawner_markers,
        "roof": {"minimum": [17, tower_top, 17], "maximum": [46, tower_top + 2, 46]},
    }
    validation = {
        "entranceReachable": True,
        "keyPathReachable": len(key_doors) == len(key_chests) == 3,
        "bossPlatformReachable": True,
        "roofComplete": all(
            (x, tower_top, z) in structure.blocks
            for x in range(17, 47)
            for z in range(17, 47)
        ),
        "forbiddenBlocks": sorted(
            set(value[0] for value in structure.blocks.values())
            & set(api["FORBIDDEN_OUTPUT_BLOCKS"])
        ),
    }
    graph = [
        ["entrance", "key_0"],
        ["key_0", "key_1"],
        ["key_1", "key_2"],
        ["key_2", "boss_platform"],
        ["entrance", "side_wing_%d" % seed],
    ]
    # Beard-thin terrain adaptation supports the main tower foundation only;
    # the surrounding dark-forest-center terrain and side wing stay native.
    structure.surface_ground_y = DARK_TOWER_SURFACE_GROUND_Y
    structure.surface_core_center = (31.5, 31.5)
    structure.surface_core_radius = 12
    structure.surface_columns = {
        (x, z): DARK_TOWER_SURFACE_GROUND_Y
        for x in range(structure.size[0])
        for z in range(structure.size[2])
        if (x - 31.5) ** 2 + (z - 31.5) ** 2 <= 12 ** 2
    }
    return structure, markers, validation, graph, boss_spawner


def _render_dark_tower(seed, api, decoration_seed=None):
    """Compile the locked source component grammar for one release layout."""
    try:
        import dark_tower_legacy_port
    except ImportError:  # pragma: no cover - package import in tests
        from tools import dark_tower_legacy_port
    return dark_tower_legacy_port.render(
        seed,
        api,
        DARK_TOWER_SURFACE_GROUND_Y,
        decoration_seed=decoration_seed,
    )


def dark_tower_variant_profiles():
    """Keep two topologies while varying rooms by the world-selected variant."""
    profiles = [
        {"id": "seed_0", "layoutSeed": 0, "decorationSeed": 0},
        {"id": "seed_1", "layoutSeed": 1, "decorationSeed": 1},
    ]
    existing = {
        (profile["layoutSeed"], profile["decorationSeed"])
        for profile in profiles
    }
    for decoration_seed in range(DARK_TOWER_DECORATION_VARIANT_COUNT):
        for layout_seed in (0, 1):
            if (layout_seed, decoration_seed) in existing:
                continue
            profiles.append(
                {
                    "id": "seed_%d_rooms_%02d"
                    % (layout_seed, decoration_seed),
                    "layoutSeed": layout_seed,
                    "decorationSeed": decoration_seed,
                }
            )
    return profiles


def build_dark_tower_entry(api):
    try:
        import dark_tower_legacy_port
    except ImportError:  # pragma: no cover - package import in tests
        from tools import dark_tower_legacy_port

    variants = []
    for profile in dark_tower_variant_profiles():
        variant_id = profile["id"]
        layout_seed = profile["layoutSeed"]
        decoration_seed = profile["decorationSeed"]
        structure, markers, validation, graph, boss_spawner = (
            _render_dark_tower(
                layout_seed,
                api,
                decoration_seed=decoration_seed,
            )
        )
        cleanup_positions = (
            dark_tower_legacy_port.dark_tower_canopy_cleanup_positions(
                structure, markers, DARK_TOWER_SURFACE_GROUND_Y
            )
        )
        cleanup_structure = api["SparseStructure"](
            structure.size,
            "dark_tower_canopy_cleanup_%s" % variant_id,
        )
        for x, y, z in sorted(cleanup_positions):
            cleanup_structure.set(x, y, z, "minecraft:air")
        cleanup_metadata = api[
            "write_dark_tower_canopy_cleanup_tiles"
        ](variant_id, cleanup_structure)
        cleanup_metadata.update(
            {
                "schemaVersion": 1,
                "runs": (
                    dark_tower_legacy_port.dark_tower_canopy_cleanup_runs(
                        cleanup_positions
                    )
                ),
                "leafBlocks": [
                    "tf_slice:hardened_dark_leaves",
                    "tf_slice:hardened_dark_leaves_center",
                ],
                "runtimeWrites": True,
                "writeMode": "bounded_authored_air_leaf_only",
                "settleTicks": 80,
                "scanBudgetPerTick": 64,
            }
        )
        markers["canopyCleanup"] = {
            "count": len(cleanup_positions),
            "maximumY": (
                DARK_TOWER_SURFACE_GROUND_Y
                + dark_tower_legacy_port.DARK_FOREST_CANOPY_CLEANUP_HEIGHT
            ),
            "scope": "variant_authored_low_tower_air_only",
        }
        pieces = _write_vertical_slices(
            "dark_tower/%s" % variant_id,
            structure,
            0,
            api,
        )
        variants.append(
            {
                "id": variant_id,
                "layoutSeed": layout_seed,
                "decorationSeed": decoration_seed,
                "layoutSha256": _stable_layout_hash(structure, markers, graph),
                "sourceCommit": SOURCE_COMMIT,
                "bounds": api["combined_bounds"](pieces),
                "pieces": pieces,
                "markers": markers,
                "validation": validation,
                "roomGraph": graph,
                "bossSpawner": {
                    "kind": "ur_ghast",
                    "entity": "tf_slice:ur_ghast",
                    "markerBlock": "tf_slice:ur_ghast_boss_spawner",
                    "offset": list(boss_spawner),
                    "activationRadius": 9,
                    "minPlayerYOffset": -4,
                },
                "canopyCleanup": cleanup_metadata,
                "surfaceNative": api["write_surface_native_tiles"](
                    "dark_tower",
                    variant_id,
                    structure,
                    layout_seed * 100 + decoration_seed,
                ),
            }
        )
    lower_spawns = [
        {"entity": "tf_slice:carminite_golem", "weight": 10, "group": [1, 2]},
        {"entity": "minecraft:skeleton", "weight": 10, "group": [1, 2]},
        {"entity": "minecraft:creeper", "weight": 5, "group": [1, 1]},
        {"entity": "minecraft:enderman", "weight": 2, "group": [1, 2]},
        {"entity": "minecraft:witch", "weight": 1, "group": [1, 1]},
        {"entity": "tf_slice:mini_ghast", "weight": 10, "group": [1, 2]},
        {"entity": "tf_slice:tower_broodling", "weight": 10, "group": [4, 4]},
        {"entity": "tf_slice:pinch_beetle", "weight": 10, "group": [1, 1]},
    ]
    roof_spawns = [
        {"entity": "tf_slice:tower_ghast", "weight": 10, "group": [1, 2]},
    ]
    water_spawns = [
        {"entity": "minecraft:squid", "weight": 10, "group": [4, 4]},
    ]
    return api["catalog_entry"](
        "dark_tower",
        "landmark_service",
        ["dm33027004", "tf_slice_dark_forest_center"],
        variants[0]["pieces"],
        dependencies=["tower_key", "carminite", "ghast_trap", "ur_ghast"],
        post_processors=["loot_and_spawner_markers", "tower_mechanisms"],
        variants=variants,
        landmarkKind="dark_tower",
        placementProfile="surface_beard_thin",
        entrySurfaceOffset=0,
        verticalSliceHeight=VERTICAL_SLICE_HEIGHT,
        worldHeightLoweringStep=5,
        maximumWorldY=319,
        structureLockObjective="knight_phantoms_defeated",
        clearanceChunks=5,
        recoveryOrder=["y", "x", "z"],
        controlledSpawns={
            "tiers": {
                "lower": lower_spawns,
                "roof": roof_spawns,
                "water": water_spawns,
            }
        },
        bossSpawner=variants[0]["bossSpawner"],
        rewardLoot="loot_tables/chests/tf_slice/ur_ghast_reward.json",
    )
