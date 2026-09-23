#!/usr/bin/env python3
"""Offline port of the locked 4.3.2508 Knight Stronghold assembler.

The Java release builds this landmark from a weighted recursive component
grammar.  NetEase worldgen cannot execute that Java graph, so a deterministic
bank is compiled here with Java's RNG, source bounding boxes, depth/instance
limits and collision rejection.  Room renderers preserve the gameplay-bearing
features of the original components instead of reducing them to empty shells.
"""

from __future__ import print_function

import collections


SOURCE_COMMIT = "a7dd8f13c653e137f977f5ffaa870fcb20fc1625"
SOURCE_CLASSES = (
    "StrongholdEntranceComponent",
    "StrongholdAccessChamberComponent",
    "StrongholdSmallHallwayComponent",
    "StrongholdLeftTurnComponent",
    "StrongholdCrossingComponent",
    "StrongholdRightTurnComponent",
    "StrongholdDeadEndComponent",
    "StrongholdBalconyRoomComponent",
    "StrongholdTrainingRoomComponent",
    "StrongholdSmallStairsComponent",
    "StrongholdTreasureCorridorComponent",
    "StrongholdAtriumComponent",
    "StrongholdFoundryComponent",
    "StrongholdTreasureRoomComponent",
    "StrongholdBossRoomComponent",
    "StrongholdUpperAscenderComponent",
    "StrongholdUpperCorridorComponent",
    "StrongholdUpperLeftTurnComponent",
    "StrongholdUpperRightTurnComponent",
    "StrongholdUpperTIntersectionComponent",
)

LOWER_GRAMMAR = (
    "small_hallway",
    "left_turn",
    "crossing",
    "right_turn",
    "dead_end",
    "balcony_room",
    "training_room",
    "small_stairs",
    "treasure_corridor",
    "atrium",
    "foundry",
    "treasure_room",
    "boss_room",
)
UPPER_GRAMMAR = (
    "upper_ascender",
    "upper_corridor",
    "upper_left_turn",
    "upper_right_turn",
    "upper_t_intersection",
)
PIECE_RULES = (
    ("small_hallway", 40, 0, 0),
    ("left_turn", 20, 0, 0),
    ("crossing", 10, 4, 0),
    ("right_turn", 20, 0, 0),
    ("dead_end", 5, 0, 0),
    ("balcony_room", 10, 3, 2),
    ("training_room", 10, 2, 0),
    ("small_stairs", 10, 0, 0),
    ("treasure_corridor", 5, 0, 0),
    ("atrium", 5, 2, 3),
    ("foundry", 5, 1, 4),
    ("treasure_room", 5, 1, 4),
    ("boss_room", 15, 1, 4),
)
# NetEase cannot run the Java component grammar during chunk generation, so
# the release ships a deterministic bank.  These source-stream entries sit in
# the interquartile single-boss band (36..55 components, 5..9 route edges)
# instead of selecting rare maximum-sprawl outliers.  Together they exercise
# every one of the twenty upstream component classes.
FIXED_SOURCE_SEED_INDICES = (1907, 2980, 3802, 1911)
FIXED_SOURCE_SEEDS = tuple(
    0x4B4E49474854 + index * 341873128712 + index * index * 132897987541
    for index in FIXED_SOURCE_SEED_INDICES
)

JAVA_MASK = (1 << 48) - 1
JAVA_MULTIPLIER = 0x5DEECE66D
JAVA_ADDEND = 0xB

SOUTH, WEST, NORTH, EAST = range(4)
ROT_NONE, ROT_RIGHT, ROT_BACK, ROT_LEFT = range(4)
AIR = "minecraft:air"
BRICK = "tf_slice:underbrick"
CRACKED = "tf_slice:cracked_underbrick"
MOSSY = "tf_slice:mossy_underbrick"
FLOOR = "tf_slice:underbrick_floor"
LANDMARK_GUARD_GRASS = "tf_slice:landmark_protected_grass"
SURFACE_ROOT_RISK_DEPTH = 6
# StrongholdAccessChamberComponent is generated with its floor two blocks
# below the KnightStructureStart terrain contact.  Aligning local Y=0 directly
# to the surface made the complete 9x5x9 shell and upper graph stand too high.
SOURCE_ACCESS_FLOOR_DEPTH = 2
SURFACE_ACCESS_BURY_DEPTH = 6


def _rotated_states(states, rotation):
    states = dict(states or {})
    stair_clockwise = {0: 2, 2: 1, 1: 3, 3: 0}
    cardinal_clockwise = {
        "north": "east",
        "east": "south",
        "south": "west",
        "west": "north",
    }
    facing_clockwise = {2: 5, 5: 3, 3: 4, 4: 2}
    for _unused in range(int(rotation) & 3):
        if "weirdo_direction" in states:
            states["weirdo_direction"] = stair_clockwise[
                int(states["weirdo_direction"])
            ]
        if "direction" in states:
            states["direction"] = (int(states["direction"]) + 1) & 3
        if states.get("facing_direction") in facing_clockwise:
            states["facing_direction"] = facing_clockwise[
                states["facing_direction"]
            ]
        if states.get("cardinal_direction") in cardinal_clockwise:
            states["cardinal_direction"] = cardinal_clockwise[
                states["cardinal_direction"]
            ]
        if states.get("pillar_axis") in ("x", "z"):
            states["pillar_axis"] = (
                "z" if states["pillar_axis"] == "x" else "x"
            )
    return states


class JavaRandom(object):
    def __init__(self, seed):
        self.seed = (int(seed) ^ JAVA_MULTIPLIER) & JAVA_MASK

    def next_bits(self, bits):
        self.seed = (self.seed * JAVA_MULTIPLIER + JAVA_ADDEND) & JAVA_MASK
        return self.seed >> (48 - bits)

    def next_int(self, bound):
        bound = int(bound)
        if bound <= 0:
            raise ValueError("bound must be positive")
        if bound & (bound - 1) == 0:
            return (bound * self.next_bits(31)) >> 31
        while True:
            bits = self.next_bits(31)
            value = bits % bound
            if bits - value + bound - 1 < (1 << 31):
                return value

    def next_boolean(self):
        return self.next_bits(1) != 0

    def next_float(self):
        return self.next_bits(24) / float(1 << 24)


def _component_box(x, y, z, x_off, y_off, z_off, x_size, y_size, z_size, direction):
    if direction == SOUTH:
        return [
            x + x_off,
            y + y_off,
            z + z_off,
            x + x_size - 1 + x_off,
            y + y_size - 1 + y_off,
            z + z_size - 1 + z_off,
        ]
    if direction == WEST:
        return [
            x - z_size + 1 + z_off,
            y + y_off,
            z + x_off,
            x + z_off,
            y + y_size - 1 + y_off,
            z + x_size - 1 + x_off,
        ]
    if direction == NORTH:
        return [
            x - x_size + 1 - x_off,
            y + y_off,
            z - z_size + 1 + z_off,
            x - x_off,
            y + y_size - 1 + y_off,
            z + z_off,
        ]
    return [
        x + z_off,
        y + y_off,
        z - x_size + 1 - x_off,
        x + z_size - 1 + z_off,
        y + y_size - 1 + y_off,
        z - x_off,
    ]


def _intersects(first, second):
    return not (
        first[3] < second[0]
        or first[0] > second[3]
        or first[4] < second[1]
        or first[1] > second[4]
        or first[5] < second[2]
        or first[2] > second[5]
    )


class Component(object):
    def __init__(self, uid, kind, index, direction, bbox, parent=None):
        self.uid = int(uid)
        self.kind = str(kind)
        self.index = int(index)
        self.direction = int(direction)
        self.bbox = list(int(value) for value in bbox)
        self.parent = parent
        self.doors = []
        self.enter_bottom = True
        self.entrance_level = 1
        self.has_treasure = False
        self.chest_trapped = False
        self.exit_top = True

    @property
    def size(self):
        world_x = self.bbox[3] - self.bbox[0] + 1
        world_y = self.bbox[4] - self.bbox[1] + 1
        world_z = self.bbox[5] - self.bbox[2] + 1
        # StructurePiece stores an axis-aligned world box, but postProcess
        # always iterates the component's authored local axes.  WEST/EAST
        # therefore swap the two horizontal spans.  Treating the world spans
        # as local spans was the source of the detached rectangular rooms.
        if self.direction in (WEST, EAST):
            return (world_z, world_y, world_x)
        return (world_x, world_y, world_z)

    def local_to_world(self, x, y, z):
        x, y, z = int(x), int(y), int(z)
        if self.direction == NORTH:
            return self.bbox[0] + x, self.bbox[1] + y, self.bbox[5] - z
        if self.direction == WEST:
            return self.bbox[3] - z, self.bbox[1] + y, self.bbox[2] + x
        if self.direction == EAST:
            return self.bbox[0] + z, self.bbox[1] + y, self.bbox[2] + x
        return self.bbox[0] + x, self.bbox[1] + y, self.bbox[2] + z

    def contains(self, position):
        x, y, z = position
        return (
            self.bbox[0] <= x <= self.bbox[3]
            and self.bbox[1] <= y <= self.bbox[4]
            and self.bbox[2] <= z <= self.bbox[5]
        )

    def valid_break_in(self, position):
        x, y, z = position
        if not self.contains(position):
            return False
        return (
            (x in (self.bbox[0], self.bbox[3]) and self.bbox[2] < z < self.bbox[5])
            or (z in (self.bbox[2], self.bbox[5]) and self.bbox[0] < x < self.bbox[3])
        )

    def add_world_door(self, position):
        x, y, z = position
        if self.direction == NORTH:
            local = (x - self.bbox[0], y - self.bbox[1], self.bbox[5] - z)
        elif self.direction == WEST:
            local = (z - self.bbox[2], y - self.bbox[1], self.bbox[3] - x)
        elif self.direction == EAST:
            local = (z - self.bbox[2], y - self.bbox[1], x - self.bbox[0])
        else:
            local = (x - self.bbox[0], y - self.bbox[1], z - self.bbox[2])
        if local not in self.doors:
            self.doors.append(local)

    def add_doorway_to(self, x, y, z, rotation):
        """Port KnightStrongholdComponent.addDoorwayTo exactly.

        The child locator is one block beyond the parent's wall.  The source
        moves that locator back onto the parent wall before recording its
        doorway; recording the raw locator silently leaves the wall intact.
        """
        x, y, z = int(x), int(y), int(z)
        rotation = int(rotation) & 3
        if rotation == ROT_NONE:
            door = (x, y, z - 1)
        elif rotation == ROT_RIGHT:
            door = (x + 1, y, z)
        elif rotation == ROT_BACK:
            door = (x, y, z + 1)
        else:
            door = (x - 1, y, z)
        if door not in self.doors:
            self.doors.append(door)


class StrongholdGraph(object):
    MAX_COMPONENTS = 260

    def __init__(self, seed):
        self.seed = int(seed)
        self.random = JavaRandom(seed)
        self.components = []
        self.edges = []
        self.last_piece = None
        self.active_rules = []
        self.spawned = {}
        entrance_box = _component_box(0, 20, 0, -1, -1, 0, 18, 7, 18, SOUTH)
        self.entrance = self._append("entrance", 0, SOUTH, entrance_box, None)
        self._build_entrance()

    def _append(self, kind, index, direction, bbox, parent):
        component = Component(len(self.components), kind, index, direction, bbox, parent)
        self.components.append(component)
        if parent is not None:
            self.edges.append((parent.uid, component.uid))
        return component

    def _first_collision(self, bbox):
        for component in self.components:
            if _intersects(component.bbox, bbox):
                return component
        return None

    def _make(self, kind, index, direction, x, y, z, parent=None):
        params = {
            "small_hallway": (-4, -1, 0, 9, 7, 18),
            "left_turn": (-4, -1, 0, 9, 7, 9),
            "right_turn": (-4, -1, 0, 9, 7, 9),
            "crossing": (-13, -1, 0, 18, 7, 18),
            "dead_end": (-4, -1, 0, 9, 7, 9),
            "training_room": (-13, -1, 0, 18, 7, 18),
            "treasure_corridor": (-4, -1, 0, 9, 7, 27),
            "treasure_room": (-4, -1, 0, 9, 7, 18),
            "boss_room": (-13, -1, 0, 27, 7, 27),
            "upper_corridor": (-2, -1, 0, 5, 5, 9),
            "upper_left_turn": (-2, -1, 0, 5, 5, 5),
            "upper_right_turn": (-2, -1, 0, 5, 5, 5),
            "upper_t_intersection": (-2, -1, 0, 5, 5, 5),
        }
        flags = {}
        if kind in ("balcony_room", "atrium", "small_stairs"):
            relative_y = int(y) - self.entrance.bbox[1]
            enter_bottom = relative_y < -8 or (relative_y <= -2 and (z & 1) == 0)
            # At the normal lower level the source chooses the upper doorway.
            if relative_y >= -1:
                enter_bottom = False
            flags["enter_bottom"] = enter_bottom
            if kind == "balcony_room":
                params[kind] = (-4, -1, 0, 18, 14, 27) if enter_bottom else (-13, -8, 0, 18, 14, 27)
            elif kind == "atrium":
                params[kind] = (-4, -1, 0, 18, 14, 18) if enter_bottom else (-13, -8, 0, 18, 14, 18)
            else:
                params[kind] = (-4, -1, 0, 9, 14, 9) if enter_bottom else (-4, -8, 0, 9, 14, 9)
        elif kind == "foundry":
            relative_y = int(y) - self.entrance.bbox[1]
            level = 3 if relative_y > 5 else 1 if relative_y < -3 else 2
            flags["entrance_level"] = level
            params[kind] = (-4, -20, 0, 18, 26, 18) if level == 3 else (-4, -6, 0, 18, 26, 18) if level == 1 else (-4, -13, 0, 18, 26, 18)
        elif kind == "upper_ascender":
            exit_top = int(y) < 36
            flags["exit_top"] = exit_top
            params[kind] = (-2, -1, 0, 5, 10, 10) if exit_top else (-2, -6, 0, 5, 10, 10)
        bbox = _component_box(x, y, z, *params[kind], direction)
        component = Component(-1, kind, index, direction, bbox, parent)
        for key, value in flags.items():
            setattr(component, key, value)
        return component

    def _prepare_lower(self, remove_boss):
        self.active_rules = [list(rule) for rule in PIECE_RULES if not (remove_boss and rule[0] == "boss_room")]
        self.spawned = dict((rule[0], 0) for rule in self.active_rules)

    def _choose_lower(self, parent, index, direction, x, y, z):
        limited_left = any(limit > 0 and self.spawned[kind] < limit for kind, _weight, limit, _depth in self.active_rules)
        if not limited_left:
            return None
        total = sum(rule[1] for rule in self.active_rules)
        for _attempt in range(5):
            counter = self.random.next_int(total)
            selected = None
            for rule in self.active_rules:
                counter -= rule[1]
                if counter < 0:
                    selected = rule
                    break
            kind, _weight, limit, minimum_depth = selected
            if index <= minimum_depth or kind == self.last_piece:
                continue
            component = self._make(kind, index, direction, x, y, z, parent)
            if self._first_collision(component.bbox) is not None:
                continue
            self.spawned[kind] += 1
            if limit > 0 and self.spawned[kind] >= limit:
                self.active_rules.remove(selected)
            self.last_piece = kind
            return component
        dead_end = self._make("dead_end", index, direction, x, y, z, parent)
        return dead_end if self._first_collision(dead_end.bbox) is None else None

    def _append_candidate(self, component):
        component.uid = len(self.components)
        self.components.append(component)
        self.edges.append((component.parent.uid, component.uid))
        return component

    def _add_lower(self, parent, rotation, x, y, z):
        if len(self.components) >= self.MAX_COMPONENTS or parent.index + 1 > 30:
            return None
        locator = parent.local_to_world(x, y, z)
        if abs(locator[0] - self.entrance.bbox[0]) > 75 or abs(locator[2] - self.entrance.bbox[2]) > 75:
            return None
        for existing in self.components:
            if existing.valid_break_in(locator):
                parent.add_doorway_to(x, y, z, rotation)
                existing.add_world_door(locator)
                if (parent.uid, existing.uid) not in self.edges:
                    self.edges.append((parent.uid, existing.uid))
                return existing
        direction = (parent.direction + int(rotation)) & 3
        child = self._choose_lower(parent, parent.index + 1, direction, *locator)
        if child is None:
            return None
        self._append_candidate(child)
        parent.add_doorway_to(x, y, z, rotation)
        child.add_world_door(locator)
        if child.kind in ("dead_end", "small_stairs"):
            child.chest_trapped = self.random.next_int(3) == 0
        if child.kind == "small_stairs":
            child.has_treasure = self.random.next_boolean()
        self._build_lower_children(child)
        return child

    def _build_lower_children(self, component):
        k = component.kind
        if k == "small_hallway":
            self._add_lower(component, ROT_NONE, 4, 1, 18)
        elif k == "left_turn":
            self._add_lower(component, ROT_LEFT, 9, 1, 4)
        elif k == "right_turn":
            self._add_lower(component, ROT_RIGHT, -1, 1, 4)
        elif k == "crossing":
            self._add_lower(component, ROT_NONE, 4, 1, 18)
            self._add_lower(component, ROT_RIGHT, -1, 1, 13)
            self._add_lower(component, ROT_LEFT, 18, 1, 4)
        elif k == "training_room":
            self._add_lower(component, ROT_NONE, 4, 1, 18)
        elif k == "treasure_corridor":
            self._add_lower(component, ROT_NONE, 4, 1, 27)
        elif k == "small_stairs":
            self._add_lower(component, ROT_NONE, 4, 8 if component.enter_bottom else 1, 9)
        elif k == "atrium":
            if component.enter_bottom:
                self._add_lower(component, ROT_BACK, 13, 8, -1)
            else:
                self._add_lower(component, ROT_BACK, 4, 1, -1)
            self._add_lower(component, ROT_NONE, 13, 1, 18)
            self._add_lower(component, ROT_NONE, 4, 8, 18)
        elif k == "balcony_room":
            exits = (
                (ROT_NONE, 13, 1, 27),
                (ROT_RIGHT, -1, 1, 13),
                (ROT_BACK, 18, 1, 13),
                (ROT_NONE, 4, 8, 27),
                (ROT_RIGHT, -1, 8, 4),
                (ROT_LEFT, 18, 8, 22),
                (ROT_BACK, 13 if component.enter_bottom else 4, 8 if component.enter_bottom else 1, -1),
            )
            for values in exits:
                self._add_lower(component, *values)
        elif k == "foundry":
            exits = {
                1: ((ROT_RIGHT, -1, 13, 13), (ROT_LEFT, 18, 13, 4), (ROT_NONE, 13, 20, 18)),
                2: ((ROT_RIGHT, -1, 6, 13), (ROT_LEFT, 18, 20, 4), (ROT_NONE, 13, 13, 18)),
                3: ((ROT_NONE, 13, 6, 18), (ROT_RIGHT, -1, 13, 13), (ROT_LEFT, 18, 13, 4)),
            }
            for values in exits[component.entrance_level]:
                self._add_lower(component, *values)

    def _add_upper(self, parent, rotation, x, y, z):
        if len(self.components) >= self.MAX_COMPONENTS or parent.index + 1 > 100:
            return None
        locator = parent.local_to_world(x, y, z)
        if abs(locator[0] - self.entrance.bbox[0]) > 48 or abs(locator[2] - self.entrance.bbox[2]) > 48:
            return None
        direction = (parent.direction + int(rotation)) & 3
        kind = UPPER_GRAMMAR[self.random.next_int(5)]
        child = self._make(kind, parent.index + 1, direction, *locator, parent=parent)
        if self._first_collision(child.bbox) is not None:
            return None
        self._append_candidate(child)
        parent.add_doorway_to(x, y, z, rotation)
        child.add_world_door(locator)
        if kind == "upper_corridor":
            self._add_upper(child, ROT_NONE, 2, 1, 9)
        elif kind == "upper_left_turn":
            self._add_upper(child, ROT_LEFT, 5, 1, 2)
        elif kind == "upper_right_turn":
            self._add_upper(child, ROT_RIGHT, -1, 1, 2)
        elif kind == "upper_t_intersection":
            self._add_upper(child, ROT_LEFT, 5, 1, 2)
            self._add_upper(child, ROT_RIGHT, -1, 1, 2)
        elif kind == "upper_ascender":
            self._add_upper(child, ROT_NONE, 2, 6 if child.exit_top else 1, 10)
        return child

    def _build_entrance(self):
        roots = (
            (ROT_NONE, 4, 1, 18),
            (ROT_RIGHT, -1, 1, 13),
            (ROT_BACK, 13, 1, -1),
            (ROT_LEFT, 18, 1, 4),
        )
        for values in roots:
            self._prepare_lower(any(component.kind == "boss_room" for component in self.components))
            self._add_lower(self.entrance, *values)
        access_box = _component_box(
            self.entrance.bbox[0] + 8,
            self.entrance.bbox[1] + 7,
            self.entrance.bbox[2] + 4,
            -4,
            1,
            0,
            9,
            5,
            9,
            self.entrance.direction,
        )
        self.access = self._append("access_chamber", 2, self.entrance.direction, access_box, self.entrance)
        for values in (
            (ROT_NONE, 4, 1, 9),
            (ROT_RIGHT, -1, 1, 4),
            (ROT_BACK, 4, 1, -1),
            (ROT_LEFT, 9, 1, 4),
        ):
            self._add_upper(self.access, *values)


class RenderBuffer(object):
    def __init__(self, api):
        self.api = api
        self.blocks = {}
        self.loot = []
        self.spawners = []
        self.pedestal = None
        self.shields = []
        self.boss = None
        self.boss_spawner = None
        self.ascender_supports = set()

    def set(self, position, name, states=None, block_entity=None):
        self.blocks[tuple(int(value) for value in position)] = (
            str(name),
            dict(states or {}),
            dict(block_entity or {}),
        )

    def local(self, component, x, y, z, name, states=None, block_entity=None):
        self.set(
            component.local_to_world(x, y, z),
            name,
            _rotated_states(states, component.direction),
            block_entity,
        )

    def local_if_air(
        self, component, x, y, z, name, states=None, block_entity=None
    ):
        position = component.local_to_world(x, y, z)
        if self.blocks.get(position, (AIR,))[0] == AIR:
            self.set(
                position,
                name,
                _rotated_states(states, component.direction),
                block_entity,
            )

    @staticmethod
    def rotated_local_position(component, x, y, z, rotation):
        rotation = int(rotation) & 3
        size_x, _size_y, size_z = component.size
        if rotation == ROT_RIGHT:
            return size_z - 1 - int(z), int(y), int(x)
        if rotation == ROT_BACK:
            return size_x - 1 - int(x), int(y), size_z - 1 - int(z)
        if rotation == ROT_LEFT:
            return int(z), int(y), size_x - 1 - int(x)
        return int(x), int(y), int(z)

    def local_rotated(
        self,
        component,
        x,
        y,
        z,
        name,
        rotation,
        states=None,
        block_entity=None,
    ):
        local = self.rotated_local_position(
            component, x, y, z, rotation
        )
        self.local(
            component,
            local[0],
            local[1],
            local[2],
            name,
            _rotated_states(states, rotation),
            block_entity,
        )

    def fill_local(self, component, start, end, name, states=None):
        for x in range(start[0], end[0] + 1):
            for y in range(start[1], end[1] + 1):
                for z in range(start[2], end[2] + 1):
                    self.local(component, x, y, z, name, states)


STAIR_WEIRDO_BY_WORLD_ASCENT_VECTOR = {
    # A functional flight is authored by its final low-to-high geometry.  The
    # Bedrock stair's visible high side follows that world ascent directly.
    (1, 0): 0,
    (-1, 0): 1,
    (0, 1): 2,
    (0, -1): 3,
}
STAIR_WEIRDO_BY_JAVA_FACING_VECTOR = {
    # Decorative Java FACING literals pass through StructurePiece's mirror
    # semantics.  Their Bedrock back edge is the opposite cardinal state; this
    # is intentionally separate from a physical flight's world ascent.
    (1, 0): 1,
    (-1, 0): 0,
    (0, 1): 3,
    (0, -1): 2,
}
FACING_DIRECTION_BY_VECTOR = {
    (0, -1): 2,
    (0, 1): 3,
    (-1, 0): 4,
    (1, 0): 5,
}
LOCAL_DIRECTION_VECTORS = {
    "north": (0, -1),
    "south": (0, 1),
    "west": (-1, 0),
    "east": (1, 0),
}


def _horizontal_unit_vector(start, end):
    delta_x = (int(end[0]) > int(start[0])) - (
        int(end[0]) < int(start[0])
    )
    delta_z = (int(end[2]) > int(start[2])) - (
        int(end[2]) < int(start[2])
    )
    if (delta_x, delta_z) not in STAIR_WEIRDO_BY_WORLD_ASCENT_VECTOR:
        raise ValueError("direction points must differ on exactly one horizontal axis")
    return delta_x, delta_z


def _stair_direction_from_world_ascent(low, high):
    return STAIR_WEIRDO_BY_WORLD_ASCENT_VECTOR[
        _horizontal_unit_vector(low, high)
    ]


def _world_facing_from_local(component, direction, rotation=ROT_NONE):
    delta_x, delta_z = LOCAL_DIRECTION_VECTORS[str(direction)]
    center_x = component.size[0] // 2
    center_z = component.size[2] // 2
    first = RenderBuffer.rotated_local_position(
        component,
        center_x,
        0,
        center_z,
        rotation,
    )
    second = RenderBuffer.rotated_local_position(
        component,
        center_x + delta_x,
        0,
        center_z + delta_z,
        rotation,
    )
    first_world = component.local_to_world(*first)
    second_world = component.local_to_world(*second)
    vector = _horizontal_unit_vector(first_world, second_world)
    return FACING_DIRECTION_BY_VECTOR[vector]


def _chest_states(component, direction, rotation=ROT_NONE):
    return {
        "facing_direction": _world_facing_from_local(
            component,
            direction,
            rotation,
        )
    }


def _rotate_local_direction(direction, rotation):
    delta_x, delta_z = LOCAL_DIRECTION_VECTORS[str(direction)]
    for _unused in range(int(rotation) & 3):
        delta_x, delta_z = -delta_z, delta_x
    for name, vector in LOCAL_DIRECTION_VECTORS.items():
        if vector == (delta_x, delta_z):
            return name
    raise ValueError("invalid rotated local direction")


def _place_local_stair(
    buffer,
    component,
    x,
    y,
    z,
    direction,
    rotation=ROT_NONE,
    upside_down=False,
    block="minecraft:stone_brick_stairs",
):
    local = RenderBuffer.rotated_local_position(
        component,
        x,
        y,
        z,
        rotation,
    )
    world_direction = _world_facing_from_local(
        component,
        direction,
        rotation,
    )
    vector = next(
        vector
        for vector, facing in FACING_DIRECTION_BY_VECTOR.items()
        if facing == world_direction
    )
    buffer.set(
        component.local_to_world(*local),
        block,
        {
            "weirdo_direction": STAIR_WEIRDO_BY_JAVA_FACING_VECTOR[vector],
            "upside_down_bit": bool(upside_down),
        },
    )


def _place_corner_statue(buffer, component, x, y, z, facing):
    offset_x = 1
    offset_z = 1
    stair_x = "east"
    stair_z = "south"
    if facing == 1:
        offset_z = -1
        stair_z = "south"
    elif facing == 2:
        offset_x = -1
        stair_x = "west"
    elif facing == 3:
        offset_x = -1
        offset_z = -1
        stair_x = "west"
        stair_z = "north"

    for delta_y in range(5):
        buffer.local(
            component,
            x,
            y + delta_y,
            z,
            "minecraft:mossy_stone_bricks",
        )
    buffer.local(component, x, y + 4, z + offset_z, "minecraft:oak_fence")
    buffer.local(component, x + offset_x, y + 4, z, "minecraft:oak_fence")
    _place_local_stair(buffer, component, x, y + 3, z + offset_z, stair_z)
    _place_local_stair(buffer, component, x + offset_x, y + 3, z, stair_x)
    _place_local_stair(
        buffer,
        component,
        x,
        y + 2,
        z + offset_z,
        stair_z,
        upside_down=True,
    )
    _place_local_stair(
        buffer,
        component,
        x + offset_x,
        y + 2,
        z,
        stair_x,
        upside_down=True,
    )
    _place_local_stair(
        buffer,
        component,
        x + offset_x,
        y + 2,
        z + offset_z,
        stair_x,
        upside_down=True,
    )
    buffer.local(
        component,
        x + offset_x,
        y,
        z + offset_z,
        "minecraft:cobblestone_wall",
    )
    buffer.local(
        component,
        x + offset_x,
        y + 1,
        z + offset_z,
        "minecraft:cobblestone_wall",
    )
    _place_local_stair(buffer, component, x, y, z + offset_z, stair_z)
    _place_local_stair(buffer, component, x + offset_x, y, z, stair_x)


def _place_wall_statue(buffer, component, x, y, z, facing):
    for delta_y in range(5):
        buffer.local(
            component,
            x,
            y + delta_y,
            z,
            "minecraft:mossy_stone_bricks",
        )

    def stair_direction(extra_rotation):
        return _rotate_local_direction(
            "west",
            (int(facing) + int(extra_rotation)) & 3,
        )

    offset_x = 1
    offset_z = 1
    if facing in (ROT_NONE, ROT_BACK):
        if facing == ROT_BACK:
            offset_x = -1
            offset_z = -1
        buffer.local(component, x - offset_x, y + 4, z, "minecraft:oak_fence")
        buffer.local(component, x + offset_x, y + 4, z, "minecraft:oak_fence")
        for px, pz, direction in (
            (x - offset_x, z, stair_direction(ROT_NONE)),
            (x + offset_x, z, stair_direction(ROT_BACK)),
            (x - offset_x, z - offset_z, stair_direction(ROT_RIGHT)),
            (x + offset_x, z - offset_z, stair_direction(ROT_RIGHT)),
        ):
            _place_local_stair(buffer, component, px, y + 3, pz, direction)
        for px, pz, direction in (
            (x - offset_x, z, stair_direction(ROT_NONE)),
            (x + offset_x, z, stair_direction(ROT_BACK)),
            (x, z - offset_z, stair_direction(ROT_RIGHT)),
            (x - offset_x, z - offset_z, stair_direction(ROT_RIGHT)),
            (x + offset_x, z - offset_z, stair_direction(ROT_RIGHT)),
        ):
            _place_local_stair(
                buffer,
                component,
                px,
                y + 2,
                pz,
                direction,
                upside_down=True,
            )
        buffer.local(component, x, y, z - offset_z, "minecraft:cobblestone_wall")
        buffer.local(component, x, y + 1, z - offset_z, "minecraft:cobblestone_wall")
        _place_local_stair(
            buffer, component, x - offset_x, y, z, stair_direction(ROT_NONE)
        )
        _place_local_stair(
            buffer, component, x + offset_x, y, z, stair_direction(ROT_BACK)
        )
    else:
        if facing == ROT_LEFT:
            offset_x = -1
            offset_z = -1
        buffer.local(component, x, y + 4, z - offset_z, "minecraft:oak_fence")
        buffer.local(component, x, y + 4, z + offset_z, "minecraft:oak_fence")
        for px, pz, direction in (
            (x, z - offset_z, stair_direction(ROT_NONE)),
            (x, z + offset_z, stair_direction(ROT_BACK)),
            (x + offset_x, z - offset_z, stair_direction(ROT_RIGHT)),
            (x + offset_x, z + offset_z, stair_direction(ROT_RIGHT)),
        ):
            _place_local_stair(buffer, component, px, y + 3, pz, direction)
        for px, pz, direction in (
            (x, z - offset_z, stair_direction(ROT_NONE)),
            (x, z + offset_z, stair_direction(ROT_BACK)),
            (x + offset_z, z, stair_direction(ROT_RIGHT)),
            (x + offset_x, z - offset_z, stair_direction(ROT_RIGHT)),
            (x + offset_x, z + offset_z, stair_direction(ROT_RIGHT)),
        ):
            _place_local_stair(
                buffer,
                component,
                px,
                y + 2,
                pz,
                direction,
                upside_down=True,
            )
        buffer.local(component, x + offset_x, y, z, "minecraft:cobblestone_wall")
        buffer.local(component, x + offset_x, y + 1, z, "minecraft:cobblestone_wall")
        _place_local_stair(
            buffer, component, x, y, z - offset_x, stair_direction(ROT_NONE)
        )
        _place_local_stair(
            buffer, component, x, y, z + offset_x, stair_direction(ROT_BACK)
        )


def _wall_block(x, y, z):
    value = (x * 73428767 + y * 912931 + z * 438289) & 63
    return MOSSY if value < 6 else CRACKED if value < 13 else BRICK


def _fill_randomized(buffer, component, start, end):
    for x in range(start[0], end[0] + 1):
        for y in range(start[1], end[1] + 1):
            for z in range(start[2], end[2] + 1):
                world = component.local_to_world(x, y, z)
                buffer.set(world, _wall_block(*world))


def _place_mossy_pillar(buffer, component, x, z, bottom, top):
    for y in range(bottom, top + 1):
        buffer.local(component, x, y, z, "minecraft:mossy_stone_bricks")


def _place_simple_statue(buffer, component, x, y, z):
    """Compact Bedrock rendering of the source stronghold stone statues."""
    buffer.local(component, x, y, z, "minecraft:mossy_stone_bricks")
    buffer.local(component, x, y + 1, z, "minecraft:stone_brick_wall")
    buffer.local(component, x, y + 2, z, "minecraft:chiseled_stone_bricks")


def _render_shell(buffer, component):
    sx, sy, sz = component.size
    for x in range(sx):
        for y in range(sy):
            for z in range(sz):
                boundary = x in (0, sx - 1) or y in (0, sy - 1) or z in (0, sz - 1)
                if boundary:
                    world = component.local_to_world(x, y, z)
                    buffer.set(world, _wall_block(*world))
                else:
                    buffer.local(component, x, y, z, AIR)

    _render_component_doors(buffer, component)


def _render_access_shell(buffer, component, source_surface_y):
    """Port the access chamber's terrain-aware source shell.

    StrongholdAccessChamberComponent calls the Java generateBox overload with
    ``replaceAir`` disabled.  Its hollow shell therefore replaces dirt/stone
    at and below terrain contact, but it never authors a complete roof or
    walls into ambient sky.  A sparse static template cannot query the target
    column, so the shared source contact plane is the deterministic boundary.
    """
    size_x, size_y, size_z = component.size
    for x in range(size_x):
        for y in range(size_y):
            for z in range(size_z):
                world = component.local_to_world(x, y, z)
                if world[1] > int(source_surface_y):
                    continue
                boundary = (
                    x in (0, size_x - 1)
                    or y in (0, size_y - 1)
                    or z in (0, size_z - 1)
                )
                if boundary:
                    buffer.set(world, _wall_block(*world))
                else:
                    buffer.set(world, AIR)

    _render_component_doors(buffer, component)


def _render_component_doors(buffer, component):
    sx, _sy, _sz = component.size
    small_door = component.kind == "access_chamber" or component.kind.startswith(
        "upper_"
    )
    for x, y, z in component.doors:
        if small_door:
            # placeSmallDoorwayAt: one open center with cobblestone-wall trim.
            if x in (0, sx - 1):
                for dz in (-1, 0, 1):
                    for dy in range(2):
                        buffer.local(
                            component, x, y + dy, z + dz,
                            "minecraft:cobblestone_wall",
                        )
            else:
                for dx in (-1, 0, 1):
                    for dy in range(2):
                        buffer.local(
                            component, x + dx, y + dy, z,
                            "minecraft:cobblestone_wall",
                        )
            for dy in range(2):
                buffer.local(component, x, y + dy, z, AIR)
        elif x in (0, sx - 1):
            for dz in range(-2, 3):
                for dy in range(4):
                    buffer.local(
                        component, x, y + dy, z + dz,
                        "minecraft:cobblestone_wall",
                    )
            for dz in (-1, 0, 1):
                for dy in range(4):
                    buffer.local(component, x, y + dy, z + dz, AIR)
        else:
            for dx in range(-2, 3):
                for dy in range(4):
                    buffer.local(
                        component, x + dx, y + dy, z,
                        "minecraft:cobblestone_wall",
                    )
            for dx in (-1, 0, 1):
                for dy in range(4):
                    buffer.local(component, x + dx, y + dy, z, AIR)


def _render_upper_doors(buffer, component, surface_y):
    """Apply source small doorways without inventing wall trim in open sky."""
    size_x, _size_y, _size_z = component.size
    for x, y, z in component.doors:
        trim = []
        if x in (0, size_x - 1):
            trim.extend(
                (x, y + delta_y, z + delta_z)
                for delta_z in (-1, 0, 1)
                for delta_y in range(2)
            )
        else:
            trim.extend(
                (x + delta_x, y + delta_y, z)
                for delta_x in (-1, 0, 1)
                for delta_y in range(2)
            )
        for local in trim:
            world = component.local_to_world(*local)
            if buffer.blocks.get(world, (AIR,))[0] != AIR:
                buffer.set(world, "minecraft:cobblestone_wall")

        for delta_y in range(2):
            world = component.local_to_world(x, y + delta_y, z)
            if world[1] <= int(surface_y):
                buffer.set(world, AIR)
            else:
                # Above the terrain contact, ambient air is already present.
                # Leaving the position unspecified avoids clearing later
                # after-surface vegetation and cannot create an air column.
                buffer.blocks.pop(world, None)


def _render_upper_shell(buffer, component, surface_y):
    """Compile the terrain-aware upper graph as a grounded surface ruin."""
    size_x, size_y, size_z = component.size
    for x in range(size_x):
        for y in range(size_y):
            for z in range(size_z):
                boundary = (
                    x in (0, size_x - 1)
                    or y in (0, size_y - 1)
                    or z in (0, size_z - 1)
                )
                world = component.local_to_world(x, y, z)
                if world[1] <= int(surface_y):
                    # The precompiled NetEase template has no access to the
                    # target column.  Treat the shared contact plane and any
                    # authored depth below it as the source dirt/stone mass.
                    buffer.set(
                        world,
                        _wall_block(*world) if boundary else AIR,
                    )
                    continue
                if not boundary:
                    # Source upper pieces do not carve ambient air.  An
                    # unspecified sparse position preserves the world instead
                    # of baking an above-ground air volume into every tile.
                    continue

                below = (world[0], world[1] - 1, world[2])
                supported = buffer.blocks.get(below, (AIR,))[0] != AIR
                # Java's air branch requires a stronghold block immediately
                # below before its one-in-three extension.  Processing from
                # low to high makes every surviving wall column grounded and
                # prevents the isolated blocks seen above the forest canopy.
                keep = (
                    (world[0] * 31 + world[1] * 17 + world[2] * 13)
                    & 0x7FFFFFFF
                ) % 3 == 0
                if supported and keep:
                    buffer.set(world, _wall_block(*world))
    _render_upper_doors(buffer, component, surface_y)

    # Door carving happens after the supported wall pass.  If it removes the
    # sole block below a one-block lintel remnant, discard that isolated solid
    # instead of leaving a floating speck in the forest canopy.  Connected
    # wall fragments and authored ascender buttresses are preserved.
    for position, block in list(buffer.blocks.items()):
        if (
            position[1] <= int(surface_y)
            or block[0] == AIR
            or not component.contains(position)
        ):
            continue
        x, y, z = position
        neighbors = (
            (x + 1, y, z),
            (x - 1, y, z),
            (x, y + 1, z),
            (x, y - 1, z),
            (x, y, z + 1),
            (x, y, z - 1),
        )
        if not any(
            buffer.blocks.get(neighbor, (AIR,))[0] != AIR
            for neighbor in neighbors
        ):
            buffer.blocks.pop(position, None)


def _render_training(buffer, c):
    _place_corner_statue(buffer, c, 2, 1, 2, 0)
    _place_corner_statue(buffer, c, 15, 1, 15, 3)
    for x0, z0 in ((4, 4), (9, 4), (9, 9)):
        for x in range(x0, x0 + 5):
            for z in range(z0, z0 + 5):
                if (x * 7 + z * 11 + c.uid) % 10 < 7:
                    buffer.local(c, x, 0, z, "minecraft:sand")
    for x, z in ((6, 6), (11, 6), (11, 11)):
        buffer.local(c, x, 1, z, "minecraft:cobblestone_wall")
        buffer.local(c, x, 2, z, "minecraft:birch_planks")
        buffer.local(c, x, 3, z, "minecraft:carved_pumpkin", {"direction": 2})
        buffer.local(c, x - 1, 2, z, "minecraft:oak_fence")
        buffer.local(c, x + 1, 2, z, "minecraft:oak_fence")
    for x in range(5, 8):
        for z in range(10, 13):
            buffer.local(c, x, 0, z, "minecraft:cobblestone")
    buffer.local(c, 6, 1, 11, "minecraft:anvil")


def _render_foundry(buffer, c):
    for x in range(1, 17):
        for z in range(1, 17):
            for y in range(0, 5):
                buffer.local(c, x, y, z, "minecraft:lava")
    for level in (5, 12, 19):
        for x in range(1, 17):
            for z in range(1, 17):
                if x in (1, 16) or z in (1, 16):
                    world = c.local_to_world(x, level, z)
                    buffer.set(world, _wall_block(*world))
    for x, z in (
        (1, 1),
        (1, 2),
        (2, 1),
        (16, 1),
        (16, 2),
        (15, 1),
        (1, 15),
        (1, 16),
        (2, 16),
        (16, 15),
        (16, 16),
        (15, 16),
    ):
        for y in range(1, 25):
            world = c.local_to_world(x, y, z)
            buffer.set(world, _wall_block(*world))

    mass_seed = (
        c.uid * 341873128712
        + c.bbox[0] * 132897987541
        + c.bbox[1] * 42317861
        + c.bbox[2] * 73428767
    )
    rng = JavaRandom(mass_seed)
    base_block = "minecraft:deepslate" if c.bbox[1] < 0 else "minecraft:stone"
    for x in range(4, 14):
        for z in range(4, 14):
            for y in range(8, 23):
                distance = abs(x - 8.5) + abs(z - 8.5) + abs(y - 18.0)
                radius = 5.5 + (rng.next_float() - rng.next_float()) * 3.5
                if distance < radius:
                    buffer.local(c, x, y, z, base_block)

    for _unused in range(400):
        x = rng.next_int(9) + 5
        z = rng.next_int(9) + 5
        y = rng.next_int(13) + 10
        if buffer.blocks.get(c.local_to_world(x, y, z), (AIR,))[0] != AIR:
            for drip in range(3):
                buffer.local(c, x, y - drip, z, base_block)

    ore_specs = (
        ("minecraft:redstone_ore", 8),
        ("minecraft:iron_ore", 8),
        ("minecraft:gold_ore", 6),
        ("minecraft:glowstone", 2),
        ("minecraft:emerald_ore", 2),
        ("minecraft:diamond_ore", 4),
        ("minecraft:copper_ore", 6),
    )
    for ore, count in ore_specs:
        for _unused in range(count):
            for _attempt in range(10):
                x = rng.next_int(9) + 5
                z = rng.next_int(9) + 5
                y = rng.next_int(13) + 10
                position = c.local_to_world(x, y, z)
                if buffer.blocks.get(position, (AIR,))[0] != AIR:
                    buffer.set(position, ore)
                    break


def _render_atrium(buffer, c):
    # Source balcony: a two-block-thick ring at Y=6..7, with the opening cut
    # back out before the cobblestone-wall rail is placed at Y=8.
    _fill_randomized(buffer, c, (1, 6, 1), (16, 7, 16))
    buffer.fill_local(c, (6, 6, 6), (11, 8, 11), AIR)
    for x, z in ((5, 5), (12, 5), (5, 12), (12, 12)):
        _place_mossy_pillar(buffer, c, x, z, 1, 12)
    for x, z in (
        (1, 1), (2, 1), (1, 2),
        (15, 1), (16, 1), (16, 2),
        (1, 15), (1, 16), (2, 16),
        (15, 16), (16, 15), (16, 16),
    ):
        _place_mossy_pillar(buffer, c, x, z, 1, 12)
    for x in range(6, 12):
        for z in range(6, 12):
            guaranteed = 7 <= x <= 10 and 7 <= z <= 10
            if guaranteed or (x * 13 + z * 17 + c.uid) % 2 == 0:
                # The authored Atrium already contains exactly one source tree.
                # A normal grass floor lets the dark-forest tree selector's
                # internal 31-block ground search tunnel through the roof and
                # place a second 37x34x37 tree inside the room.  Use the same
                # visually matched, tree-ineligible grass guard as landmark
                # surfaces so the baked source tree remains the only one.
                buffer.local(c, x, 0, z, LANDMARK_GUARD_GRASS)
    tree_variant = c.uid % 5
    tree_palettes = (
        ("minecraft:oak_log", "minecraft:oak_leaves", {"pillar_axis": "y"}),
        ("minecraft:birch_log", "minecraft:birch_leaves", {"pillar_axis": "y"}),
        ("minecraft:jungle_log", "minecraft:jungle_leaves", {"pillar_axis": "y"}),
        ("tf_slice:twilight_oak_log", "tf_slice:twilight_oak_leaves", {}),
        ("tf_slice:twilight_oak_log", "tf_slice:rainbow_oak_leaves", {}),
    )
    log_block, leaf_block, log_states = tree_palettes[tree_variant]
    trunk_height = 7 if tree_variant == 2 else 6
    for y in range(1, trunk_height + 1):
        buffer.local(c, 8, y, 8, log_block, log_states)
    for x in range(5, 12):
        for y in range(5, 9):
            for z in range(5, 12):
                if abs(x - 8) + abs(z - 8) + abs(y - 6) <= 6:
                    buffer.local_if_air(
                        c,
                        x,
                        y,
                        z,
                        leaf_block,
                        {"persistent_bit": True},
                    )
    for x in range(5, 13):
        for z in range(5, 13):
            if x in (5, 12) or z in (5, 12):
                buffer.local(c, x, 8, z, "minecraft:cobblestone_wall")
    # The configured tree in the Java room supplies a climbable branch route
    # between the lower grass and the upper balcony.  Preserve that gameplay
    # role with a deterministic branch spiral in the compiled template.
    climb = (
        (7, 1, 8),
        (7, 2, 7),
        (8, 3, 7),
        (9, 4, 7),
        (10, 5, 7),
        (10, 6, 8),
        (10, 7, 9),
        (10, 7, 10),
        (10, 7, 11),
    )
    for x, y, z in climb:
        buffer.local(c, x, y, z, leaf_block, {
            "persistent_bit": True,
        })
    for x, y, z in climb:
        buffer.local(c, x, y + 1, z, AIR)
        buffer.local(c, x, y + 2, z, AIR)
    for x, y, z, facing in (
        (2, 8, 2, 0),
        (2, 1, 15, 1),
        (15, 1, 2, 2),
        (15, 8, 15, 3),
    ):
        _place_corner_statue(buffer, c, x, y, z, facing)
    for rotation in (ROT_NONE, ROT_RIGHT, ROT_BACK, ROT_LEFT):
        for x, y, z, direction, upside_down in (
            (5, 1, 6, "south", False),
            (6, 1, 5, "east", False),
            (5, 5, 6, "south", True),
            (6, 5, 5, "east", True),
            (5, 12, 6, "south", True),
            (6, 12, 5, "east", True),
        ):
            _place_local_stair(
                buffer,
                c,
                x,
                y,
                z,
                direction,
                rotation,
                upside_down,
            )


def _render_balcony(buffer, c):
    _fill_randomized(buffer, c, (1, 6, 1), (16, 7, 25))
    buffer.fill_local(c, (5, 6, 5), (12, 8, 21), AIR)
    for x in range(4, 14):
        for z in range(4, 23):
            if x in (4, 13) or z in (4, 22):
                buffer.local(c, x, 8, z, "minecraft:cobblestone_wall")
    for x, z in (
        (4, 4), (13, 4), (13, 8),
        (4, 22), (13, 22), (13, 18),
    ):
        _place_mossy_pillar(buffer, c, x, z, 1, 12)
    for rotation in (ROT_NONE, ROT_BACK):
        for x, y, z, direction, upside_down in (
            (4, 1, 5, "south", False),
            (5, 1, 4, "east", False),
            (4, 5, 5, "south", True),
            (5, 5, 4, "east", True),
            (4, 12, 5, "south", True),
            (5, 12, 4, "east", True),
            (13, 1, 5, "south", False),
            (12, 1, 4, "west", False),
            (13, 5, 5, "south", True),
            (12, 5, 4, "west", True),
            (13, 12, 5, "south", True),
            (12, 12, 4, "west", True),
            (13, 1, 9, "south", False),
            (13, 1, 7, "north", False),
            (12, 1, 8, "west", False),
            (13, 5, 9, "south", True),
            (13, 5, 7, "north", True),
            (13, 12, 9, "south", True),
            (13, 12, 7, "north", True),
            (12, 12, 8, "west", True),
        ):
            _place_local_stair(
                buffer,
                c,
                x,
                y,
                z,
                direction,
                rotation,
                upside_down,
            )
    # StrongholdBalconyRoomComponent places one 3-wide seven-step flight at
    # each end.  These flights are the only physical connection between the
    # room's lower and upper door planes.
    for rotation in (ROT_NONE, ROT_BACK):
        low_local = buffer.rotated_local_position(c, 7, 1, 5, rotation)
        high_local = buffer.rotated_local_position(c, 13, 7, 5, rotation)
        stair_direction = _stair_direction_from_world_ascent(
            c.local_to_world(*low_local),
            c.local_to_world(*high_local),
        )
        for step in range(1, 8):
            for z in range(5, 8):
                buffer.local_rotated(
                    c, step + 6, step + 1, z, AIR, rotation
                )
                stair_local = buffer.rotated_local_position(
                    c, step + 6, step, z, rotation
                )
                buffer.set(
                    c.local_to_world(*stair_local),
                    "minecraft:stone_brick_stairs",
                    {
                        "weirdo_direction": stair_direction,
                        "upside_down_bit": False,
                    },
                )
                buffer.local_rotated(
                    c, step + 6, step - 1, z, BRICK, rotation
                )


def _render_entrance_details(buffer, c):
    for x, z, facing in ((5, 5, 0), (5, 12, 1), (12, 5, 2), (12, 12, 3)):
        _place_corner_statue(buffer, c, x, 1, z, facing)
    for x, z, facing in (
        (9, 16, ROT_NONE),
        (1, 9, ROT_RIGHT),
        (8, 1, ROT_BACK),
        (16, 8, ROT_LEFT),
    ):
        _place_wall_statue(buffer, c, x, 1, z, facing)


def _render_small_hallway_details(buffer, c):
    _place_wall_statue(buffer, c, 1, 1, 9, ROT_RIGHT)
    _place_wall_statue(buffer, c, 7, 1, 9, ROT_LEFT)


def _render_turn_details(buffer, c, left):
    _place_corner_statue(
        buffer,
        c,
        2 if left else 6,
        1,
        6,
        1 if left else 3,
    )


def _render_crossing_details(buffer, c):
    _place_corner_statue(buffer, c, 2, 1, 2, 0)
    _place_corner_statue(buffer, c, 15, 1, 15, 3)
    for x in (8, 9):
        for y in range(1, 6):
            for z in (8, 9):
                buffer.local(c, x, y, z, "minecraft:mossy_stone_bricks")
    for x, z, facing in (
        (8, 7, ROT_NONE),
        (7, 9, ROT_LEFT),
        (9, 10, ROT_BACK),
        (10, 8, ROT_RIGHT),
    ):
        _place_wall_statue(buffer, c, x, 1, z, facing)
    table = (
        (5, 3, "minecraft:oak_stairs", "west", True),
        (5, 4, "minecraft:oak_stairs", "south", True),
        (6, 3, "minecraft:oak_stairs", "north", True),
        (6, 4, "minecraft:oak_stairs", "east", True),
        (5, 2, "minecraft:spruce_stairs", "south", False),
        (7, 3, "minecraft:spruce_stairs", "west", False),
        (6, 5, "minecraft:spruce_stairs", "north", False),
        (4, 4, "minecraft:spruce_stairs", "east", False),
    )
    for rotation in (ROT_NONE, ROT_RIGHT, ROT_BACK, ROT_LEFT):
        for x, z, block, direction, upside_down in table:
            _place_local_stair(
                buffer,
                c,
                x,
                1,
                z,
                direction,
                rotation,
                upside_down,
                block=block,
            )


def _render_upper_ascender(buffer, c, surface_y=None):
    component_floor_y = int(c.bbox[1])
    support_floor_y = (
        component_floor_y
        if surface_y is None
        else min(component_floor_y, int(surface_y))
    )

    def ground_low_center(local_z):
        top = c.local_to_world(2, 0, local_z)
        if support_floor_y >= component_floor_y:
            return

        extension = []
        for world_y in range(component_floor_y - 1, support_floor_y - 1, -1):
            support = (top[0], world_y, top[2])
            existing = buffer.blocks.get(support)
            if existing is not None:
                if existing[0] != AIR:
                    for position in extension:
                        buffer.set(position, _wall_block(*position))
                        buffer.ascender_supports.add(position)
                return
            extension.append(support)
        for position in extension:
            buffer.set(position, _wall_block(*position))
            buffer.ascender_supports.add(position)

    flight = []
    for step in range(1, 6):
        flight.append(
            c.local_to_world(
                1,
                step,
                step + 2 if c.exit_top else 7 - step,
            )
        )
    stair_direction = _stair_direction_from_world_ascent(
        min(flight, key=lambda position: position[1]),
        max(flight, key=lambda position: position[1]),
    )
    for step in range(1, 6):
        y = step
        z = step + 2 if c.exit_top else 7 - step
        for x in range(1, 4):
            support = c.local_to_world(x, y - 1, z)
            buffer.set(support, _wall_block(*support))
            buffer.set(
                c.local_to_world(x, y, z),
                "minecraft:stone_brick_stairs",
                {
                    "weirdo_direction": stair_direction,
                    "upside_down_bit": False,
                },
            )
    ground_low_center(3 if c.exit_top else 6)
    platform_y = 5
    platform_z = 8 if c.exit_top else 1
    for x in range(1, 4):
        buffer.local(c, x, platform_y, platform_z, "minecraft:stone_bricks")


def _render_small_stairs(buffer, c):
    for x in range(1, 8):
        for z in range(1, 8):
            if x in (1, 7) or z in (1, 7):
                buffer.local(
                    c,
                    x,
                    7,
                    z,
                    "minecraft:smooth_stone_slab",
                    {"minecraft:vertical_half": "top"},
                )
            else:
                buffer.local(c, x, 7, z, AIR)
    rotation = ROT_NONE if c.enter_bottom else ROT_BACK
    low_local = buffer.rotated_local_position(c, 3, 1, 1, rotation)
    high_local = buffer.rotated_local_position(c, 3, 7, 7, rotation)
    stair_direction = _stair_direction_from_world_ascent(
        c.local_to_world(*low_local),
        c.local_to_world(*high_local),
    )
    for step in range(1, 8):
        for x in range(3, 6):
            buffer.local_rotated(c, x, step + 1, step, AIR, rotation)
            stair_local = buffer.rotated_local_position(
                c, x, step, step, rotation
            )
            buffer.set(
                c.local_to_world(*stair_local),
                "minecraft:stone_brick_stairs",
                {
                    "weirdo_direction": stair_direction,
                    "upside_down_bit": False,
                },
            )
            buffer.local_rotated(c, x, step - 1, step, BRICK, rotation)
    if c.has_treasure:
        local = buffer.rotated_local_position(c, 4, 1, 6, rotation)
        pos = c.local_to_world(*local)
        buffer.loot.append(
            (
                pos,
                "stronghold_cache",
                _chest_states(c, "north", rotation),
            )
        )
        if c.chest_trapped:
            buffer.local_rotated(c, 4, 0, 6, "minecraft:tnt", rotation)
        for z in range(5, 8):
            _place_local_stair(buffer, c, 3, 1, z, "west", rotation)
            _place_local_stair(buffer, c, 5, 1, z, "east", rotation)
        for x, y, z, direction in (
            (4, 1, 5, "north"),
            (4, 1, 7, "south"),
            (4, 2, 6, "north"),
        ):
            _place_local_stair(buffer, c, x, y, z, direction, rotation)
    _place_wall_statue(
        buffer,
        c,
        4,
        8,
        1 if c.enter_bottom else 7,
        ROT_BACK if c.enter_bottom else ROT_NONE,
    )


def _render_dead_end(buffer, c):
    _place_wall_statue(buffer, c, 1, 1, 4, ROT_RIGHT)
    _place_wall_statue(buffer, c, 7, 1, 4, ROT_LEFT)
    _place_wall_statue(buffer, c, 4, 1, 7, ROT_NONE)
    pos = c.local_to_world(4, 1, 3)
    buffer.loot.append(
        (pos, "stronghold_cache", _chest_states(c, "south"))
    )
    if c.chest_trapped:
        buffer.local(c, 4, 0, 3, "minecraft:tnt")
    for z in range(2, 5):
        _place_local_stair(buffer, c, 3, 1, z, "west")
        _place_local_stair(buffer, c, 5, 1, z, "east")
    for x, y, z, direction in (
        (4, 1, 2, "north"),
        (4, 1, 4, "south"),
        (4, 2, 3, "north"),
    ):
        _place_local_stair(buffer, c, x, y, z, direction)


def _render_treasure_corridor(buffer, c):
    for x, z, facing in (
        (1, 9, ROT_RIGHT),
        (1, 17, ROT_RIGHT),
        (7, 9, ROT_LEFT),
        (7, 17, ROT_LEFT),
    ):
        _place_wall_statue(buffer, c, x, 1, z, facing)
    rotation = ROT_NONE if (c.bbox[0] ^ c.bbox[2]) % 2 == 0 else ROT_BACK
    local = buffer.rotated_local_position(c, 8, 2, 13, rotation)
    buffer.loot.append(
        (
            c.local_to_world(*local),
            "stronghold_cache",
            _chest_states(c, "west", rotation),
        )
    )
    for x, y, z, direction, upside_down in (
        (8, 3, 12, "south", True),
        (8, 3, 13, "west", True),
        (8, 3, 14, "north", True),
        (7, 1, 12, "south", False),
        (7, 1, 13, "west", False),
        (7, 1, 14, "north", False),
    ):
        _place_local_stair(
            buffer, c, x, y, z, direction, rotation, upside_down
        )
    for x, y, z in ((8, 2, 12), (8, 2, 14)):
        buffer.local_rotated(
            c, x, y, z, "minecraft:cobblestone_wall", rotation
        )


def _render_treasure_room(buffer, c):
    for x, z, facing in (
        (1, 4, ROT_RIGHT),
        (1, 13, ROT_RIGHT),
        (7, 4, ROT_LEFT),
        (7, 13, ROT_LEFT),
        (4, 16, ROT_NONE),
    ):
        _place_wall_statue(buffer, c, x, 1, z, facing)
    buffer.fill_local(c, (1, 1, 8), (7, 5, 9), BRICK)
    buffer.fill_local(c, (3, 1, 8), (5, 4, 9), "minecraft:iron_bars")
    for position in (c.local_to_world(4, 1, 4), c.local_to_world(4, 4, 15)):
        buffer.spawners.append((position, "tf_slice:helmet_crab"))
    for position, direction in (
        (c.local_to_world(2, 4, 13), "west"),
        (c.local_to_world(6, 4, 13), "east"),
    ):
        buffer.loot.append(
            (position, "stronghold_room", _chest_states(c, direction))
        )


def _render_sarcophagus(buffer, c, x, z, rng):
    for px, pz in (
        (x - 1, z),
        (x + 1, z),
        (x - 1, z + 3),
        (x + 1, z + 3),
    ):
        buffer.local(c, px, 1, pz, "minecraft:mossy_stone_bricks")
        buffer.local(
            c,
            px,
            2,
            pz,
            "minecraft:torch"
            if rng.next_int(7) == 0
            else "minecraft:cobblestone_wall",
        )
    for px, pz, direction in (
        (x, z, "north"),
        (x, z + 3, "south"),
        (x + 1, z + 1, "east"),
        (x + 1, z + 2, "east"),
        (x - 1, z + 1, "west"),
        (x - 1, z + 2, "west"),
    ):
        _place_local_stair(buffer, c, px, 1, pz, direction)
    for pz in (z + 1, z + 2):
        buffer.local(c, x, 2, pz, "minecraft:smooth_stone_slab", {
            "minecraft:vertical_half": "bottom",
        })


def _render_boss(buffer, c):
    _fill_randomized(buffer, c, (1, 1, 1), (3, 5, 25))
    _fill_randomized(buffer, c, (23, 1, 1), (25, 5, 25))
    _fill_randomized(buffer, c, (4, 1, 1), (22, 5, 3))
    _fill_randomized(buffer, c, (4, 1, 23), (22, 5, 25))
    buffer.fill_local(c, (1, 1, 1), (2, 5, 25), "minecraft:obsidian")
    buffer.fill_local(c, (24, 1, 1), (25, 5, 25), "minecraft:obsidian")
    buffer.fill_local(c, (4, 1, 1), (22, 5, 2), "minecraft:obsidian")
    buffer.fill_local(c, (4, 1, 24), (22, 5, 25), "minecraft:obsidian")
    for start, end in (
        ((4, 1, 4), (4, 5, 7)),
        ((5, 1, 4), (5, 5, 5)),
        ((6, 1, 4), (7, 5, 4)),
        ((4, 1, 19), (4, 5, 22)),
        ((5, 1, 21), (5, 5, 22)),
        ((6, 1, 22), (7, 5, 22)),
        ((22, 1, 4), (22, 5, 7)),
        ((21, 1, 4), (21, 5, 5)),
        ((19, 1, 4), (20, 5, 4)),
        ((22, 1, 19), (22, 5, 22)),
        ((21, 1, 21), (21, 5, 22)),
        ((19, 1, 22), (20, 5, 22)),
    ):
        _fill_randomized(buffer, c, start, end)
    for rotation in (ROT_NONE, ROT_RIGHT, ROT_BACK, ROT_LEFT):
        for x, y, z, direction, upside_down in (
            (4, 1, 8, "south", False),
            (8, 1, 4, "east", False),
            (4, 5, 8, "south", True),
            (8, 5, 4, "east", True),
            (5, 1, 6, "south", False),
            (6, 1, 6, "east", False),
            (6, 1, 5, "east", False),
            (5, 5, 6, "south", True),
            (6, 5, 6, "east", True),
            (6, 5, 5, "east", True),
        ):
            _place_local_stair(
                buffer,
                c,
                x,
                y,
                z,
                direction,
                rotation,
                upside_down,
            )
    sarcophagus_rng = JavaRandom(
        c.uid * 341873128712
        + c.bbox[0] * 132897987541
        + c.bbox[2] * 73428767
    )
    for x in (8, 13, 18):
        for z in (8, 15):
            _render_sarcophagus(buffer, c, x, z, sarcophagus_rng)
    buffer.fill_local(c, (12, 1, 1), (14, 4, 2), AIR)
    buffer.fill_local(c, (12, 1, 3), (14, 4, 3), "minecraft:iron_bars")
    buffer.boss = c.local_to_world(13, 1, 13)
    buffer.boss_spawner = c.local_to_world(13, 2, 13)
    buffer.set(buffer.boss_spawner, "tf_slice:knight_phantom_boss_spawner")


def _render_access(buffer, c):
    # StrongholdAccessChamberComponent is the actual surface entrance.  Its
    # central stairwell is only three blocks deep; the old NetEase port added
    # an unrelated long ladder shaft and a flat 9x9 cap above this component.
    buffer.fill_local(c, (2, -2, 2), (6, 0, 6), "minecraft:mossy_stone_bricks")
    for x in range(3, 6):
        for z in range(3, 6):
            for y in range(-2, 3):
                buffer.local(c, x, y, z, AIR)

    for x, z, direction in (
        *((2, z, "east") for z in range(3, 7)),
        *((6, z, "west") for z in range(2, 7)),
        *((x, 2, "south") for x in range(3, 6)),
        *((x, 6, "north") for x in range(3, 6)),
    ):
        _place_local_stair(buffer, c, x, 0, z, direction)

    # The four source exits are two-block-high small doorways, not the large
    # four-high lower-stronghold arches.
    for x, z, along_x in (
        (4, 8, True),
        (0, 4, False),
        (4, 0, True),
        (8, 4, False),
    ):
        for across in (-1, 0, 1):
            px = x + across if along_x else x
            pz = z if along_x else z + across
            for y in (1, 2):
                buffer.local(c, px, y, pz, "minecraft:cobblestone_wall")
        for y in (1, 2):
            buffer.local(c, x, y, z, AIR)

    buffer.local(c, 2, 0, 2, "minecraft:mossy_stone_bricks")
    buffer.pedestal = c.local_to_world(2, 1, 2)
    buffer.set(buffer.pedestal, "tf_slice:trophy_pedestal")
    for x in range(2, 7):
        for z in range(2, 7):
            position = c.local_to_world(x, -1, z)
            buffer.set(position, "tf_slice:stronghold_shield")
            buffer.shields.append(position)


def _surface_access_chamber(
    access,
    access_floor_depth=SOURCE_ACCESS_FLOOR_DEPTH,
):
    """Return the source access floor and its 9x9 terrain-contact columns."""
    center = access.local_to_world(4, 0, 4)
    columns = {}
    for x in range(9):
        for z in range(9):
            position = access.local_to_world(x, 0, z)
            columns[(position[0], position[2])] = (
                center[1] + int(access_floor_depth)
            )
    return center, columns


def _render_component(
    buffer,
    component,
    source_surface_y,
    render_upper_ascender=True,
):
    if component.kind == "access_chamber":
        _render_access_shell(buffer, component, source_surface_y)
    elif component.kind.startswith("upper_"):
        _render_upper_shell(buffer, component, source_surface_y)
    else:
        _render_shell(buffer, component)
    if component.kind == "entrance":
        _render_entrance_details(buffer, component)
    elif component.kind == "small_hallway":
        _render_small_hallway_details(buffer, component)
    elif component.kind == "left_turn":
        _render_turn_details(buffer, component, True)
    elif component.kind == "right_turn":
        _render_turn_details(buffer, component, False)
    elif component.kind == "crossing":
        _render_crossing_details(buffer, component)
    elif component.kind == "training_room":
        _render_training(buffer, component)
    elif component.kind == "foundry":
        _render_foundry(buffer, component)
    elif component.kind == "atrium":
        _render_atrium(buffer, component)
    elif component.kind == "balcony_room":
        _render_balcony(buffer, component)
    elif component.kind == "small_stairs":
        _render_small_stairs(buffer, component)
    elif component.kind == "dead_end":
        _render_dead_end(buffer, component)
    elif component.kind == "treasure_corridor":
        _render_treasure_corridor(buffer, component)
    elif component.kind == "treasure_room":
        _render_treasure_room(buffer, component)
    elif component.kind == "boss_room":
        _render_boss(buffer, component)
    elif component.kind == "access_chamber":
        _render_access(buffer, component)
    elif component.kind == "upper_ascender" and render_upper_ascender:
        _render_upper_ascender(buffer, component, source_surface_y)


def _upper_ascender_high_landing_supports(graph, buffer, component):
    if component.exit_top:
        high_neighbors = [
            graph.components[right]
            for left, right in graph.edges
            if left == component.uid
        ]
        if len(high_neighbors) != 1:
            return ()
        high_neighbor = high_neighbors[0]
        door_pairs = _adjacent_door_pairs(component, high_neighbor)
        high_index = 1
    else:
        high_neighbor = component.parent
        if high_neighbor is None:
            return ()
        door_pairs = _adjacent_door_pairs(high_neighbor, component)
        high_index = 0
    if len(door_pairs) != 1:
        return ()

    first, second = door_pairs[0]
    if not all(
        buffer.blocks.get(
            (door[0], door[1] + delta_y, door[2]),
            (AIR,),
        )[0]
        == AIR
        for door in (first, second)
        for delta_y in (0, 1)
    ):
        return ()

    high_door = door_pairs[0][high_index]
    low_door = door_pairs[0][1 - high_index]
    inward = (
        high_door[0] - low_door[0],
        high_door[2] - low_door[2],
    )
    return (
        (first[0], first[1] - 1, first[2]),
        (second[0], second[1] - 1, second[2]),
        (
            high_door[0] + inward[0],
            high_door[1] - 1,
            high_door[2] + inward[1],
        ),
    )


def _upper_ascender_high_landing_survived(graph, buffer, component):
    supports = _upper_ascender_high_landing_supports(
        graph,
        buffer,
        component,
    )
    return bool(supports) and all(
        buffer.blocks.get(position, (AIR,))[0] != AIR
        for position in supports
    )


def _compile_selected_buffer(
    graph,
    api,
    predicate,
    access_floor_depth=SOURCE_ACCESS_FLOOR_DEPTH,
):
    buffer = RenderBuffer(api)
    source_surface_y = (
        graph.access.local_to_world(4, 0, 4)[1]
        + int(access_floor_depth)
    )
    selected = [
        component
        for component in graph.components
        if predicate(component)
    ]
    for component in selected:
        _render_component(
            buffer,
            component,
            source_surface_y,
            render_upper_ascender=False,
        )
    for component in selected:
        if (
            component.kind == "upper_ascender"
            and _upper_ascender_high_landing_survived(
                graph,
                buffer,
                component,
            )
        ):
            _render_upper_ascender(
                buffer,
                component,
                source_surface_y,
            )
    return buffer


def _is_surface_component(component):
    return component.kind == "access_chamber" or component.kind.startswith(
        "upper_"
    )


def _compile_buffer(
    graph,
    api,
    access_floor_depth=SOURCE_ACCESS_FLOOR_DEPTH,
):
    buffer = _compile_selected_buffer(
        graph,
        api,
        lambda _component: True,
        access_floor_depth,
    )
    surface_entry, surface_columns = _surface_access_chamber(
        graph.access,
        access_floor_depth,
    )
    return buffer, surface_entry, surface_columns


def _reachable_components(graph):
    adjacency = collections.defaultdict(set)
    for left, right in graph.edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    reached = set((graph.entrance.uid,))
    pending = [graph.entrance.uid]
    while pending:
        current = pending.pop()
        for neighbor in adjacency[current]:
            if neighbor not in reached:
                reached.add(neighbor)
                pending.append(neighbor)
    return reached


def _adjacent_door_pairs(parent, child):
    parent_doors = set(parent.local_to_world(*door) for door in parent.doors)
    child_doors = set(child.local_to_world(*door) for door in child.doors)
    return [
        (parent_door, child_door)
        for parent_door in parent_doors
        for child_door in child_doors
        if parent_door[1] == child_door[1]
        and abs(parent_door[0] - child_door[0])
        + abs(parent_door[2] - child_door[2]) == 1
    ]


def _door_graph_is_physically_open(graph, buffer, relocated_access_gate=False):
    for left, right in graph.edges:
        if (left, right) == (graph.entrance.uid, graph.access.uid):
            # The source buffer keeps its gate below the access chamber.  The
            # final Bedrock template relocates that one gate and its pedestal
            # to the visible surface platform, leaving this vertical edge open.
            center = graph.access.local_to_world(4, -1, 4)
            expected = AIR if relocated_access_gate else "tf_slice:stronghold_shield"
            if buffer.blocks.get(center, (None,))[0] != expected:
                return False
            continue
        pairs = _adjacent_door_pairs(
            graph.components[left], graph.components[right]
        )
        if not any(
            all(
                buffer.blocks.get(
                    (door[0], door[1] + dy, door[2]), (AIR,)
                )[0]
                == AIR
                for door in pair
                for dy in (0, 1)
            )
            for pair in pairs
        ):
            return False
    return True


def _component_roofs_are_complete(graph, buffer):
    source_access_cutout = set(
        graph.access.local_to_world(x, -2, z)
        for x in range(3, 6)
        for z in range(3, 6)
    )
    for component in graph.components:
        if component.kind == "access_chamber" or component.kind.startswith(
            "upper_"
        ):
            # Source access/upper walls are terrain-aware ruins and do not
            # guarantee a complete authored roof above the surface contact.
            continue
        size_x, size_y, size_z = component.size
        for x in range(size_x):
            for z in range(size_z):
                position = component.local_to_world(x, size_y - 1, z)
                if (
                    buffer.blocks.get(position, (AIR,))[0] == AIR
                    and position not in source_access_cutout
                ):
                    return False
    return True


def _small_stair_runs_are_traversable(graph, buffer):
    for component in graph.components:
        if component.kind != "small_stairs":
            continue
        rotation = ROT_NONE if component.enter_bottom else ROT_BACK
        low_local = RenderBuffer.rotated_local_position(
            component, 3, 1, 1, rotation
        )
        high_local = RenderBuffer.rotated_local_position(
            component, 3, 7, 7, rotation
        )
        expected_states = {
            "weirdo_direction": _stair_direction_from_world_ascent(
                component.local_to_world(*low_local),
                component.local_to_world(*high_local),
            ),
            "upside_down_bit": False,
        }
        for lane_x in range(3, 6):
            previous = None
            for step in range(1, 8):
                local = RenderBuffer.rotated_local_position(
                    component,
                    lane_x,
                    step,
                    step,
                    rotation,
                )
                position = component.local_to_world(*local)
                block = buffer.blocks.get(position)
                if (
                    block is None
                    or block[0] != "minecraft:stone_brick_stairs"
                    or block[1] != expected_states
                ):
                    return False

                support_local = RenderBuffer.rotated_local_position(
                    component,
                    lane_x,
                    step - 1,
                    step,
                    rotation,
                )
                support = component.local_to_world(*support_local)
                if buffer.blocks.get(support, (AIR,))[0] == AIR:
                    return False

                clearance_local = RenderBuffer.rotated_local_position(
                    component,
                    lane_x,
                    step + 1,
                    step,
                    rotation,
                )
                clearance = component.local_to_world(*clearance_local)
                if buffer.blocks.get(clearance, (AIR,))[0] != AIR:
                    return False

                if previous is not None:
                    horizontal_step = abs(position[0] - previous[0]) + abs(
                        position[2] - previous[2]
                    )
                    if horizontal_step != 1 or abs(position[1] - previous[1]) != 1:
                        return False
                previous = position
    return True


def _shells_stay_in_source_boxes(graph):
    for component in graph.components:
        shell = RenderBuffer({})
        _render_shell(shell, component)
        if any(not component.contains(position) for position in shell.blocks):
            return False
    return True


def _shortest_component_distance(graph, start_uid, target_uid):
    adjacency = collections.defaultdict(set)
    for left, right in graph.edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    distances = {int(start_uid): 0}
    pending = collections.deque((int(start_uid),))
    while pending:
        current = pending.popleft()
        if current == int(target_uid):
            return distances[current]
        for neighbor in adjacency[current]:
            if neighbor in distances:
                continue
            distances[neighbor] = distances[current] + 1
            pending.append(neighbor)
    return None


def _surface_root_protection_columns(structure):
    shallow_floor = int(structure.surface_ground_y) - SURFACE_ROOT_RISK_DEPTH
    structural_columns = {
        (int(x), int(z))
        for (x, y, z), block in structure.blocks.items()
        if int(y) >= shallow_floor
        and block[0]
        not in (
            AIR,
            "minecraft:cave_air",
            "minecraft:void_air",
            "minecraft:oak_leaves",
            "minecraft:oak_log",
        )
    }
    protected = set()
    radius = SURFACE_ROOT_RISK_DEPTH
    for root_x, root_z in structural_columns:
        for delta_x in range(-radius, radius + 1):
            for delta_z in range(-radius, radius + 1):
                if delta_x * delta_x + delta_z * delta_z > radius * radius:
                    continue
                x = root_x + delta_x
                z = root_z + delta_z
                if 0 <= x < structure.size[0] and 0 <= z < structure.size[2]:
                    protected.add((x, z))
    return protected


def _surface_stair_direction(current, lower):
    # ``lower`` is the next descending support block, so the Java ascent is
    # the vector from it back to ``current``.  Convert that ascent through the
    # same opposite/back-edge table used by every authored stair.
    ascent_x = (int(current[0]) > int(lower[0])) - (
        int(current[0]) < int(lower[0])
    )
    ascent_z = (int(current[1]) > int(lower[1])) - (
        int(current[1]) < int(lower[1])
    )
    if (ascent_x, ascent_z) not in STAIR_WEIRDO_BY_WORLD_ASCENT_VECTOR:
        raise ValueError("surface stair points must be horizontally adjacent")
    return STAIR_WEIRDO_BY_WORLD_ASCENT_VECTOR[(ascent_x, ascent_z)]


def _render_surface_access(structure, access_center, surface_y):
    """Expose the buried chamber through the source pedestal-and-shield gate."""
    center_x, access_y, center_z = (
        int(access_center[0]),
        int(access_center[1]),
        int(access_center[2]),
    )
    surface_y = int(surface_y)
    for delta_x in range(-4, 5):
        for delta_z in range(-4, 5):
            if abs(delta_x) != 4 and abs(delta_z) != 4:
                continue
            world = (center_x + delta_x, surface_y, center_z + delta_z)
            structure.set(
                world[0], world[1], world[2], _wall_block(*world)
            )
            for y in range(access_y + 4, surface_y):
                wall = (world[0], y, world[2])
                structure.set(
                    wall[0], wall[1], wall[2], _wall_block(*wall)
                )

    ring = [
        (0, 0),
        (1, 0),
        (1, 1),
        (0, 1),
        (-1, 1),
        (-1, 0),
        (-1, -1),
        (0, -1),
        (1, -1),
        (2, -1),
        (2, 0),
        (2, 1),
        (2, 2),
        (1, 2),
        (0, 2),
        (-1, 2),
        (-2, 2),
        (-2, 1),
        (-2, 0),
        (-2, -1),
        (-2, -2),
        (-1, -2),
        (0, -2),
        (1, -2),
    ]
    step_count = max(1, surface_y - access_y)
    if step_count > len(ring):
        raise ValueError("surface access chamber is too deep for its stair ring")
    selected = ring[:step_count]
    for index, (delta_x, delta_z) in enumerate(selected):
        y = surface_y - 1 - index
        x = center_x + delta_x
        z = center_z + delta_z
        if len(selected) == 1:
            direction = STAIR_WEIRDO_BY_WORLD_ASCENT_VECTOR[(0, -1)]
        elif index + 1 < len(selected):
            direction = _surface_stair_direction(
                (delta_x, delta_z), selected[index + 1]
            )
        else:
            direction = _surface_stair_direction(
                selected[index - 1], (delta_x, delta_z)
            )
        structure.set(
            x,
            y,
            z,
            "minecraft:stone_brick_stairs",
            {"weirdo_direction": direction, "upside_down_bit": False},
        )
        structure.set(x, y - 1, z, BRICK)
        structure.set(x, y + 1, z, AIR)
        structure.set(x, y + 2, z, AIR)
    # Recreate the visible core of StrongholdAccessChamberComponent at terrain
    # contact: a complete 9x9 underbrick floor, the source four-sided stair
    # ring, a 3x3 opening over the 5x5 removable shield, and the pedestal in
    # its original corner relative to the opening.  The compiled upper graph
    # remains buried, so the compact stair run above continues below the gate.
    for delta_x in range(-4, 5):
        for delta_z in range(-4, 5):
            world = (center_x + delta_x, surface_y, center_z + delta_z)
            structure.set(world[0], world[1], world[2], _wall_block(*world))
            # The access is the only surface footprint this structure owns.
            # Clear two blocks of headroom here, but nowhere across the buried
            # room graph, so trees cannot seal the gate and the forest outside
            # this compact 9x9 opening remains native.
            structure.set(world[0], surface_y + 1, world[2], AIR)
            structure.set(world[0], surface_y + 2, world[2], AIR)
    for delta_x in range(-2, 3):
        for delta_z in range(-2, 3):
            structure.set(
                center_x + delta_x,
                surface_y,
                center_z + delta_z,
                "minecraft:mossy_stone_bricks",
            )
    # The trophy pedestal removes the 5x5 shield layer at surface_y - 1.
    # Keep a 3x3 drop shaft clear through the buried access-chamber roof so
    # the exposed gate reaches the real room instead of ending on solid brick.
    for delta_x in range(-1, 2):
        for delta_z in range(-1, 2):
            for y in range(access_y + 1, surface_y + 2):
                structure.set(
                    center_x + delta_x,
                    y,
                    center_z + delta_z,
                    AIR,
                )

    stair_runs = (
        *((-2, delta_z, 1) for delta_z in range(-1, 3)),
        *((2, delta_z, 0) for delta_z in range(-2, 3)),
        *((delta_x, -2, 3) for delta_x in range(-1, 2)),
        *((delta_x, 2, 2) for delta_x in range(-1, 2)),
    )
    for delta_x, delta_z, direction in stair_runs:
        structure.set(
            center_x + delta_x,
            surface_y,
            center_z + delta_z,
            "minecraft:stone_brick_stairs",
            {"weirdo_direction": direction, "upside_down_bit": False},
        )

    pedestal = (center_x - 2, surface_y + 1, center_z - 2)
    structure.set(
        pedestal[0],
        pedestal[1],
        pedestal[2],
        "tf_slice:trophy_pedestal",
    )
    shields = []
    for delta_x in range(-2, 3):
        for delta_z in range(-2, 3):
            position = (
                center_x + delta_x,
                surface_y - 1,
                center_z + delta_z,
            )
            structure.set(
                position[0],
                position[1],
                position[2],
                "tf_slice:stronghold_shield",
            )
            shields.append(position)
    return {
        "entrance": (center_x, surface_y, center_z),
        "pedestal": pedestal,
        "shields": shields,
    }


def _surface_to_boss_walkable(structure, markers):
    air = set((AIR, "minecraft:cave_air", "minecraft:void_air"))
    unsupported = air | set(
        ("minecraft:lava", "minecraft:water", "minecraft:flowing_water")
    )
    blocks = dict(structure.blocks)
    shield_positions = []
    for position, block in list(blocks.items()):
        if block[0] == "tf_slice:stronghold_shield":
            shield_positions.append(position)
            blocks[position] = (AIR, {}, {})

    def block_name(position):
        return blocks.get(position, ("minecraft:stone",))[0]

    def can_stand(position):
        x, y, z = position
        return (
            block_name(position) in air
            and block_name((x, y + 1, z)) in air
            and block_name((x, y - 1, z)) not in unsupported
        )

    def marker_position(name):
        offset = markers[name]["offset"]
        return (
            int(offset[0]),
            int(offset[1]) + int(structure.surface_ground_y),
            int(offset[2]),
        )

    entrance = marker_position("surfaceEntrance")
    boss = marker_position("bossRoom")
    boss_radius = int(markers["bossRoom"].get("radius", 4))
    starts = set(
        (x, y, z)
        for x in range(entrance[0] - 2, entrance[0] + 3)
        for y in range(entrance[1] - 2, entrance[1] + 3)
        for z in range(entrance[2] - 2, entrance[2] + 3)
        if can_stand((x, y, z))
    )
    # The player stands on the shield before activation, then drops through
    # the newly opened shaft.  Once the validation snapshot removes the
    # shields, that pre-activation standing position no longer has support;
    # seed the search with the first safe landing below each gate column.
    for shield_x, shield_y, shield_z in shield_positions:
        for landing_y in range(shield_y + 1, shield_y - 17, -1):
            landing = (shield_x, landing_y, shield_z)
            if can_stand(landing):
                starts.add(landing)
                break
    goals = set(
        (x, y, z)
        for x in range(boss[0] - boss_radius, boss[0] + boss_radius + 1)
        for y in range(boss[1] - 2, boss[1] + 4)
        for z in range(boss[2] - boss_radius, boss[2] + boss_radius + 1)
        if can_stand((x, y, z))
    )
    reached = set(starts)
    pending = collections.deque(starts)
    while pending:
        current = pending.popleft()
        if current in goals:
            return True
        x, y, z = current
        for delta_x, delta_z in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            moved = False
            for delta_y in (0, 1, -1):
                neighbor = (
                    x + delta_x,
                    y + delta_y,
                    z + delta_z,
                )
                if neighbor in reached or not can_stand(neighbor):
                    continue
                reached.add(neighbor)
                pending.append(neighbor)
                moved = True
                break
            if moved:
                continue
            fall_x = x + delta_x
            fall_z = z + delta_z
            if block_name((fall_x, y, fall_z)) not in air:
                continue
            for fall_y in range(y - 1, y - 17, -1):
                if block_name((fall_x, fall_y, fall_z)) not in air:
                    break
                landing = (fall_x, fall_y, fall_z)
                if landing in reached or not can_stand(landing):
                    continue
                reached.add(landing)
                pending.append(landing)
                break
    return False


def render_stronghold(
    seed_index,
    api,
    surface_local_y=52,
    access_floor_depth=SOURCE_ACCESS_FLOOR_DEPTH,
):
    seed_index = int(seed_index)
    access_floor_depth = int(access_floor_depth)
    if access_floor_depth not in (-2, 2):
        raise ValueError("source access floor depth must be -2 or 2")
    graph = StrongholdGraph(FIXED_SOURCE_SEEDS[seed_index])
    buffer, surface_entry, world_surface_columns = _compile_buffer(
        graph,
        api,
        access_floor_depth,
    )
    surface_buffer = _compile_selected_buffer(
        graph,
        api,
        _is_surface_component,
        access_floor_depth,
    )
    surface_source_positions = set(surface_buffer.blocks)
    lower_buffer = _compile_selected_buffer(
        graph,
        api,
        lambda component: not _is_surface_component(component),
        access_floor_depth,
    )
    surface_source_positions.difference_update(
        surface_buffer.ascender_supports.intersection(lower_buffer.blocks)
    )
    surface_loot_positions = set(entry[0] for entry in surface_buffer.loot)
    surface_spawner_positions = set(
        position for position, _entity in surface_buffer.spawners
    )
    boss_rooms = [component for component in graph.components if component.kind == "boss_room"]
    if len(boss_rooms) != 1 or buffer.boss_spawner is None:
        raise ValueError("source stronghold seed %d did not produce exactly one boss room" % seed_index)

    minimum_x = min(position[0] for position in buffer.blocks) - 2
    minimum_z = min(position[2] for position in buffer.blocks) - 2
    maximum_x = max(position[0] for position in buffer.blocks) + 2
    maximum_z = max(position[2] for position in buffer.blocks) + 2
    # Preserve the complete source surface graph (Access Chamber plus every
    # upper piece) at terrain contact. Only the entrance/lower graph receives
    # the six-block static burial needed to keep its tallest roofs underground.
    surface_y_shift = (
        int(surface_local_y)
        - int(surface_entry[1])
        - access_floor_depth
    )
    # The source has two Access Chamber heights, but the NetEase static split
    # must not raise tall lower rooms into the forest with the exposed branch.
    # Anchor the complete lower graph to the same terrain-relative burial for
    # both variants; only the access/upper graph follows access_floor_depth.
    lower_y_shift = (
        int(surface_local_y)
        - int(surface_entry[1])
        - SOURCE_ACCESS_FLOOR_DEPTH
        - SURFACE_ACCESS_BURY_DEPTH
    )

    def source_y_shift(position):
        return (
            surface_y_shift
            if position in surface_source_positions
            else lower_y_shift
        )

    minimum_y = min(
        int(position[1]) + source_y_shift(position)
        for position in buffer.blocks
    )
    maximum_y = max(
        int(position[1]) + source_y_shift(position)
        for position in buffer.blocks
    )
    if minimum_y < 0:
        raise ValueError("stronghold seed %d exceeds the underground vertical envelope" % seed_index)
    SparseStructure = api["SparseStructure"]
    structure = SparseStructure(
        (
            maximum_x - minimum_x + 1,
            max(
                int(surface_local_y) + 3,
                maximum_y + 1,
            ),
            maximum_z - minimum_z + 1,
        ),
        "knight_stronghold_%d" % seed_index,
    )

    def local_position(position):
        return (
            int(position[0]) - minimum_x,
            int(position[1]) + source_y_shift(position),
            int(position[2]) - minimum_z,
        )

    def lower_local_position(position):
        return (
            int(position[0]) - minimum_x,
            int(position[1]) + lower_y_shift,
            int(position[2]) - minimum_z,
        )

    def surface_local_position(position):
        return (
            int(position[0]) - minimum_x,
            int(position[1]) + surface_y_shift,
            int(position[2]) - minimum_z,
        )

    surface_authored_air_positions = set(
        surface_local_position(position)
        for position, block in surface_buffer.blocks.items()
        if block[0] == AIR
    )

    clipped_positions = []
    structure.source_local_positions = {}
    for position, value in buffer.blocks.items():
        local = local_position(position)
        structure.source_local_positions[position] = local
        if all(0 <= local[axis] < structure.size[axis] for axis in range(3)):
            structure.set(local[0], local[1], local[2], value[0], value[1], value[2])
        else:
            clipped_positions.append(position)
    loot_positions = []
    for position, loot_id, states in buffer.loot:
        local = (
            surface_local_position(position)
            if position in surface_loot_positions
            else lower_local_position(position)
        )
        if not all(0 <= local[axis] < structure.size[axis] for axis in range(3)):
            clipped_positions.append(position)
            continue
        api["set_loot_container"](
            structure,
            local[0],
            local[1],
            local[2],
            loot_id,
            states=states,
        )
        loot_positions.append(position)
    spawner_positions = []
    for position, entity in buffer.spawners:
        local = (
            surface_local_position(position)
            if position in surface_spawner_positions
            else lower_local_position(position)
        )
        if not all(0 <= local[axis] < structure.size[axis] for axis in range(3)):
            clipped_positions.append(position)
            continue
        api["set_spawner"](structure, local[0], local[1], local[2], entity)
        spawner_positions.append((position, entity))

    def offset(position):
        local = lower_local_position(position)
        return [local[0], local[1] - int(surface_local_y), local[2]]

    def surface_offset(position):
        local = surface_local_position(position)
        return [local[0], local[1] - int(surface_local_y), local[2]]

    local_surface = surface_local_position(surface_entry)
    structure.surface_ground_y = int(surface_local_y)
    structure.surface_core_center = (local_surface[0], local_surface[2])
    structure.surface_core_radius = 5
    access_surface_columns = dict(
        ((x - minimum_x, z - minimum_z), int(surface_local_y))
        for (x, z) in world_surface_columns
    )
    structure.surface_access_columns = dict(access_surface_columns)
    structure.surface_columns = dict(access_surface_columns)
    structure.surface_burial_components = []
    structure.surface_entry_overrides = set()

    # Splitting the source graph adds six blocks between the original access
    # shaft and the entrance-room roof. Extend the same 5x5 wall / 3x3 air
    # profile downward so the trophy shield still opens into the real maze.
    blocks_before_connector = dict(structure.blocks)
    entrance_roof_y = int(graph.entrance.bbox[4]) + lower_y_shift
    access_shaft_bottom_y = int(surface_entry[1]) - 2 + surface_y_shift
    center_x, _center_y, center_z = local_surface
    for y in range(entrance_roof_y, access_shaft_bottom_y):
        for delta_x in range(-2, 3):
            for delta_z in range(-2, 3):
                x = int(center_x) + delta_x
                z = int(center_z) + delta_z
                if abs(delta_x) <= 1 and abs(delta_z) <= 1:
                    structure.set(x, y, z, AIR)
                else:
                    structure.set(x, y, z, _wall_block(x, y, z))
    structure.surface_entry_overrides.update(
        position
        for position, previous in blocks_before_connector.items()
        if structure.blocks.get(position) != previous
    )
    # The Java structure uses TerrainAdjustment.BURY and only carves a block
    # when terrain actually occupies that position. A static mcstructure has no
    # target-world query: serializing lower-room ambient air at/above the
    # sampled surface turns tall foundries and balcony rooms into rectangular
    # forest cuts. Preserve the air explicitly authored by the Access Chamber
    # and upper corridor graph, but discard every other surface-air write.
    entrance_columns = set(structure.surface_access_columns)
    for position, value in list(structure.blocks.items()):
        x, y, z = position
        if (
            value[0] == AIR
            and y >= int(surface_local_y)
            and (x, z) not in entrance_columns
            and position not in surface_authored_air_positions
        ):
            structure.blocks.pop(position, None)
            structure.surface_entry_overrides.add(position)
    structure.surface_protection_columns = _surface_root_protection_columns(
        structure
    )
    markers = {
        "surfaceEntrance": {
            "offset": surface_offset(surface_entry),
            "block": AIR,
        },
        "trophyPedestal": {
            "offset": surface_offset(buffer.pedestal),
            "block": "tf_slice:trophy_pedestal",
        },
        "shieldWalls": [surface_offset(position) for position in buffer.shields],
        "bossRoom": {"offset": offset(buffer.boss), "radius": 13},
        "bossGroupSpawner": {"offset": offset(buffer.boss_spawner), "block": "tf_slice:knight_phantom_boss_spawner"},
        "lootChests": [offset(position) for position in loot_positions],
        "structureSpawners": [
            {"offset": offset(position), "entity": entity}
            for position, entity in spawner_positions
        ],
    }
    palette = sorted(set(value[0] for value in structure.blocks.values()))
    counts = collections.Counter(component.kind for component in graph.components)
    reached = _reachable_components(graph)
    boss_room = boss_rooms[0]
    doorways_connected = _door_graph_is_physically_open(graph, buffer)
    roofs_complete = _component_roofs_are_complete(graph, buffer)
    stair_runs_traversable = _small_stair_runs_are_traversable(graph, buffer)
    shells_in_bounds = _shells_stay_in_source_boxes(graph)

    def component_local_position(component, position):
        if _is_surface_component(component):
            return surface_local_position(position)
        return lower_local_position(position)

    final_doorways_connected = True
    for left_uid, right_uid in graph.edges:
        if (left_uid, right_uid) == (graph.entrance.uid, graph.access.uid):
            gate = surface_local_position(
                graph.access.local_to_world(4, -1, 4)
            )
            if structure.blocks.get(gate, (None,))[0] != (
                "tf_slice:stronghold_shield"
            ):
                final_doorways_connected = False
                break
            continue
        left = graph.components[left_uid]
        right = graph.components[right_uid]
        pairs = _adjacent_door_pairs(left, right)
        if not any(
            all(
                structure.blocks.get(
                    component_local_position(
                        component,
                        (door[0], door[1] + delta_y, door[2]),
                    ),
                    (AIR,),
                )[0]
                == AIR
                for component, door in ((left, pair[0]), (right, pair[1]))
                for delta_y in (0, 1)
            )
            for pair in pairs
        ):
            final_doorways_connected = False
            break

    boss_spawner_local = lower_local_position(buffer.boss_spawner)
    boss_spawner_present = (
        structure.blocks.get(boss_spawner_local, (None,))[0]
        == "tf_slice:knight_phantom_boss_spawner"
    )
    boss_route_length = _shortest_component_distance(
        graph, graph.entrance.uid, boss_room.uid
    )
    surface_to_boss_walkable = _surface_to_boss_walkable(
        structure, markers
    )
    source_port = {
        "sourceCommit": SOURCE_COMMIT,
        "sourceClasses": list(SOURCE_CLASSES),
        "componentCount": len(graph.components),
        "componentCounts": dict(sorted(counts.items())),
        "componentTypes": sorted(counts),
        "lowerRootBranches": 4,
        "upperRootBranches": 4,
        "bossRoomCount": counts.get("boss_room", 0),
        "collisionPolicy": "source_bounding_box_rejection",
        "randomPolicy": "java_util_random",
        "sourceSeedStreamIndex": FIXED_SOURCE_SEED_INDICES[seed_index],
        "sourceSeed": FIXED_SOURCE_SEEDS[seed_index],
        "lowerDepthLimit": 30,
        "lowerRangeLimit": 75,
        "coordinateTransform": "minecraft_structure_piece",
        "bossRouteLength": boss_route_length,
        "surfaceRootRiskDepth": SURFACE_ROOT_RISK_DEPTH,
        "surfaceAccessDepth": int(surface_local_y) - int(local_surface[1]),
        "lowerGraphBurialDepth": SURFACE_ACCESS_BURY_DEPTH,
        "surfaceAccessStyle": "source_access_chamber",
        "terrainAdjustment": "split_static_depth_bury",
        "burialComponentCount": len(structure.surface_burial_components),
    }
    validation = {
        "entranceReachable": graph.access.uid in reached,
        "bossRoomReachable": boss_room.uid in reached,
        "allLootReachable": bool(loot_positions)
        and len(reached) == len(graph.components),
        "allComponentsReachable": len(reached) == len(graph.components),
        "doorwaysConnected": doorways_connected,
        "finalDoorwaysConnected": final_doorways_connected,
        "renderBoundsValid": shells_in_bounds,
        # The connector intentionally cuts the entrance-room roof. Source
        # roofs were already checked before that authored vertical extension.
        "roofComplete": roofs_complete,
        "stairRunsTraversable": stair_runs_traversable,
        "bossSpawnerPresent": boss_spawner_present,
        "surfaceToBossWalkable": surface_to_boss_walkable,
        "clippedBlockCount": len(set(clipped_positions)),
        "forbiddenBlocks": sorted(set(palette) & set(api["FORBIDDEN_OUTPUT_BLOCKS"])),
        "authoredBlocks": palette,
    }
    if not all(
        validation[key]
        for key in (
            "entranceReachable",
            "bossRoomReachable",
            "allLootReachable",
            "allComponentsReachable",
            "doorwaysConnected",
            "finalDoorwaysConnected",
            "renderBoundsValid",
            "roofComplete",
            "stairRunsTraversable",
            "bossSpawnerPresent",
            "surfaceToBossWalkable",
        )
    ) or validation["clippedBlockCount"] or validation["forbiddenBlocks"]:
        raise ValueError(
            "stronghold seed %d failed physical topology validation: %r"
            % (seed_index, validation)
        )
    room_graph = [["c%d" % left, "c%d" % right] for left, right in graph.edges]
    return structure, markers, validation, room_graph, source_port
