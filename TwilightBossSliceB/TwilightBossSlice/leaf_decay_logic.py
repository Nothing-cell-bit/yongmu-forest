# -*- coding: utf-8 -*-
"""Pure source-parity rules for bounded Twilight leaf decay.

The Java source stores a distance from logs on every ``LeavesBlock``.  NetEase
custom blocks do not inherit that state machine, so the server adapter computes
the same six-block support distance only for leaves affected by a removal.
"""


NEIGHBOR_OFFSETS = (
    (1, 0, 0),
    (-1, 0, 0),
    (0, 1, 0),
    (0, -1, 0),
    (0, 0, 1),
    (0, 0, -1),
)
MAX_SUPPORT_DISTANCE = 6

BASE_DECAYABLE_LEAVES = frozenset(
    (
        "tf_slice:twilight_oak_leaves",
        "tf_slice:canopy_leaves",
        "tf_slice:mangrove_leaves",
        "tf_slice:rainbow_oak_leaves",
        "tf_slice:enchanted_twilight_oak_leaves",
        "tf_slice:enchanted_canopy_leaves",
        "tf_slice:spooky_twilight_oak_leaves",
    )
)
NON_DECAYING_CONNECTING_LEAVES = frozenset(("tf_slice:dark_leaves",))
VANILLA_CONNECTING_LEAVES = frozenset(
    (
        "minecraft:leaves",
        "minecraft:leaves2",
        "minecraft:oak_leaves",
        "minecraft:spruce_leaves",
        "minecraft:birch_leaves",
        "minecraft:jungle_leaves",
        "minecraft:acacia_leaves",
        "minecraft:dark_oak_leaves",
        "minecraft:mangrove_leaves",
        "minecraft:cherry_leaves",
        "minecraft:pale_oak_leaves",
        "minecraft:azalea_leaves",
        "minecraft:azalea_leaves_flowered",
        "minecraft:flowering_azalea_leaves",
    )
)
NON_CONNECTING_LEAVES = frozenset(
    (
        "tf_slice:hardened_dark_leaves",
        "tf_slice:hardened_dark_leaves_center",
        "tf_slice:fallen_leaves",
    )
)

TWILIGHT_SUPPORT_LOGS = frozenset(
    (
        "tf_slice:twilight_oak_log",
        "tf_slice:canopy_log",
        "tf_slice:mangrove_log",
        "tf_slice:stripped_mangrove_log",
        "tf_slice:mangrove_wood",
        "tf_slice:stripped_mangrove_wood",
        "tf_slice:dark_log",
        "tf_slice:stripped_dark_log",
        "tf_slice:dark_wood",
        "tf_slice:stripped_dark_wood",
    )
)

VANILLA_WOOD_FAMILIES = (
    "oak",
    "spruce",
    "birch",
    "jungle",
    "acacia",
    "dark_oak",
    "mangrove",
    "cherry",
    "pale_oak",
)
VANILLA_SUPPORT_LOGS = frozenset(
    "minecraft:%s_%s" % (prefix, suffix)
    for prefix in VANILLA_WOOD_FAMILIES
    for suffix in ("log", "wood")
).union(
    frozenset(
        "minecraft:stripped_%s_%s" % (prefix, suffix)
        for prefix in VANILLA_WOOD_FAMILIES
        for suffix in ("log", "wood")
    ),
    frozenset(
        (
            "minecraft:crimson_stem",
            "minecraft:crimson_hyphae",
            "minecraft:stripped_crimson_stem",
            "minecraft:stripped_crimson_hyphae",
            "minecraft:warped_stem",
            "minecraft:warped_hyphae",
            "minecraft:stripped_warped_stem",
            "minecraft:stripped_warped_hyphae",
        )
    ),
)
SUPPORT_LOGS = TWILIGHT_SUPPORT_LOGS.union(VANILLA_SUPPORT_LOGS)

SAPLING_BY_LEAF = {
    "tf_slice:twilight_oak_leaves": "tf_slice:twilight_oak_sapling",
    "tf_slice:canopy_leaves": "tf_slice:canopy_sapling",
    "tf_slice:mangrove_leaves": "tf_slice:mangrove_sapling",
    "tf_slice:rainbow_oak_leaves": "tf_slice:rainbow_oak_sapling",
    "tf_slice:enchanted_twilight_oak_leaves": "tf_slice:twilight_oak_sapling",
    "tf_slice:enchanted_canopy_leaves": "tf_slice:canopy_sapling",
    "tf_slice:spooky_twilight_oak_leaves": "tf_slice:twilight_oak_sapling",
}

SAPLING_FEATURES = {
    "tf_slice:twilight_oak_sapling": "tf_slice:twilight_oak_tree_feature",
    "tf_slice:canopy_sapling": "tf_slice:canopy_tree_feature",
    "tf_slice:rainbow_oak_sapling": "tf_slice:rainbow_oak_tree_feature",
    "tf_slice:darkwood_sapling": "tf_slice:darkwood_tree_feature",
    "tf_slice:mangrove_sapling": "tf_slice:twilight_mangrove_tree_feature",
}

SAPLING_FALLBACK_FEATURES = {
    "tf_slice:rainbow_oak_sapling": (
        "tf_slice:rainbow_oak_tree_fallback_feature",
    ),
}

RAINBOW_SAPLING_STRUCTURE_COUNT = 16
RAINBOW_SAPLING_STRUCTURE_CENTER = (7, 5, 7)
RAINBOW_SAPLING_CLEARANCE_RADIUS = 2
RAINBOW_SAPLING_CLEARANCE_HEIGHT = 9


def block_name(block):
    if isinstance(block, dict):
        return str(block.get("name", ""))
    if isinstance(block, (tuple, list)) and block:
        return str(block[0])
    if isinstance(block, str):
        return block
    return ""


def canonical_leaf_name(name):
    name = str(name or "")
    prefix = "tf_slice:rainbow_oak_leaves_"
    if name.startswith(prefix):
        suffix = name[len(prefix):]
        if len(suffix) == 2 and suffix.isdigit():
            return "tf_slice:rainbow_oak_leaves"
    return name


def is_decayable_leaf(name):
    return canonical_leaf_name(name) in BASE_DECAYABLE_LEAVES


def is_connecting_leaf(name):
    name = canonical_leaf_name(name)
    return (
        name in BASE_DECAYABLE_LEAVES
        or name in NON_DECAYING_CONNECTING_LEAVES
        or name in VANILLA_CONNECTING_LEAVES
    )


def is_support_log(name):
    return str(name or "") in SUPPORT_LOGS


def orthogonal_neighbors(position):
    x, y, z = (int(value) for value in position)
    return tuple(
        (x + dx, y + dy, z + dz)
        for dx, dy, dz in NEIGHBOR_OFFSETS
    )


def is_leaf_supported(position, get_block, max_distance=MAX_SUPPORT_DISTANCE):
    """Return True/False, or None when the needed block view is unavailable."""
    max_distance = max(1, int(max_distance))
    start = tuple(int(value) for value in position)
    frontier = [(start, 0)]
    visited = set((start,))
    saw_unloaded = False
    index = 0
    while index < len(frontier):
        current, depth = frontier[index]
        index += 1
        for neighbor in orthogonal_neighbors(current):
            block = get_block(neighbor)
            if block is None:
                saw_unloaded = True
                continue
            name = block_name(block)
            if is_support_log(name):
                return True
            if (
                depth + 1 < max_distance
                and neighbor not in visited
                and is_connecting_leaf(name)
            ):
                visited.add(neighbor)
                frontier.append((neighbor, depth + 1))
    if saw_unloaded:
        return None
    return False


def position_key(dimension_id, position):
    return "%d:%d:%d:%d" % (
        int(dimension_id),
        int(position[0]),
        int(position[1]),
        int(position[2]),
    )


def parse_position_key(key):
    try:
        dimension_id, x, y, z = (int(part) for part in str(key).split(":"))
    except (TypeError, ValueError):
        return None
    return dimension_id, (x, y, z)


def enqueue_candidate(queue, dimension_id, position, due_tick):
    key = position_key(dimension_id, position)
    due_tick = int(due_tick)
    previous = queue.get(key)
    if previous is None or due_tick < int(previous):
        queue[key] = due_tick
        return True
    return False


def pop_due_candidates(queue, current_tick, limit):
    current_tick = int(current_tick)
    limit = max(0, int(limit))
    if limit == 0:
        return []
    due = sorted(
        (int(due_tick), key)
        for key, due_tick in queue.items()
        if int(due_tick) <= current_tick
    )[:limit]
    result = []
    for _due_tick, key in due:
        queue.pop(key, None)
        parsed = parse_position_key(key)
        if parsed is not None:
            result.append(parsed)
    return result


def is_decay_processing_tick(current_tick, interval_ticks):
    try:
        interval_ticks = int(interval_ticks)
        return interval_ticks > 0 and int(current_tick) % interval_ticks == 0
    except (TypeError, ValueError):
        return False


def leaf_block_ids():
    values = set(BASE_DECAYABLE_LEAVES)
    values.update(
        "tf_slice:rainbow_oak_leaves_%02d" % index
        for index in range(16)
    )
    return tuple(sorted(values))


def listener_block_ids():
    values = set(SUPPORT_LOGS)
    values.update(leaf_block_ids())
    values.update(NON_DECAYING_CONNECTING_LEAVES)
    values.update(VANILLA_CONNECTING_LEAVES)
    return tuple(sorted(values))


def sapling_feature(block_name_value):
    return SAPLING_FEATURES.get(str(block_name_value or ""))


def sapling_feature_attempts(block_name_value):
    block_name_value = str(block_name_value or "")
    primary = sapling_feature(block_name_value)
    if primary is None:
        return ()
    return (primary,) + tuple(
        SAPLING_FALLBACK_FEATURES.get(block_name_value, ())
    )


def rainbow_sapling_structure(variant_index):
    try:
        variant_index = int(variant_index) % RAINBOW_SAPLING_STRUCTURE_COUNT
    except (TypeError, ValueError):
        return None
    return (
        "tf_slice:enchanted/runtime/regular_rainbow/"
        "v%02d/x00_z00" % variant_index
    )


def rainbow_sapling_structure_origin(root_position):
    try:
        return tuple(
            int(root_position[index]) - RAINBOW_SAPLING_STRUCTURE_CENTER[index]
            for index in range(3)
        )
    except (TypeError, ValueError, IndexError):
        return None


def rainbow_sapling_clearance_positions(root_position):
    try:
        root_x, root_y, root_z = (int(value) for value in root_position)
    except (TypeError, ValueError):
        return ()
    radius = RAINBOW_SAPLING_CLEARANCE_RADIUS
    return tuple(
        (root_x + offset_x, root_y + offset_y, root_z + offset_z)
        for offset_y in range(RAINBOW_SAPLING_CLEARANCE_HEIGHT)
        for offset_x in range(-radius, radius + 1)
        for offset_z in range(-radius, radius + 1)
    )


def rainbow_sapling_can_replace(block_name_value):
    block_name_value = str(block_name_value or "")
    return (
        block_name_value in (
            "minecraft:air",
            "minecraft:cave_air",
            "minecraft:void_air",
            "minecraft:tallgrass",
            "minecraft:double_plant",
            "tf_slice:fallen_leaves",
            "tf_slice:rainbow_oak_sapling",
        )
        or is_connecting_leaf(block_name_value)
    )


def rainbow_sapling_has_grown(block_name_value):
    return str(block_name_value or "") == "tf_slice:twilight_oak_log"


def should_grow_sapling(brightness, random_roll):
    try:
        return int(brightness) >= 9 and int(random_roll) % 7 == 0
    except (TypeError, ValueError):
        return False


def bonemeal_growth_succeeds(random_roll):
    try:
        return float(random_roll) < 0.45
    except (TypeError, ValueError):
        return False


def sapling_growth_action(stage):
    try:
        return "grow" if int(stage) >= 1 else "advance"
    except (TypeError, ValueError):
        return "advance"


def decay_drops(
    leaf_name,
    sapling_roll,
    stick_roll,
    stick_count_roll,
):
    canonical = canonical_leaf_name(leaf_name)
    sapling = SAPLING_BY_LEAF.get(canonical)
    drops = []
    sapling_chance = 0.025 if canonical == "tf_slice:rainbow_oak_leaves" else 0.05
    if sapling is not None and float(sapling_roll) < sapling_chance:
        drops.append(
            {"itemName": sapling, "count": 1, "auxValue": 0}
        )
    if float(stick_roll) < 0.02:
        drops.append(
            {
                "itemName": "minecraft:stick",
                "count": 1 if float(stick_count_roll) < 0.5 else 2,
                "auxValue": 0,
            }
        )
    return drops
