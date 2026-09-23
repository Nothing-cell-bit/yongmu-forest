#!/usr/bin/env python3
"""Offline port of the 4.3.2508 programmatic Lich Tower component graph.

The locked release predates the template-driven tower revamp.  Its tower is a
recursive graph of ``TowerMainComponent``, ``TowerWingComponent``, bridges,
outbuildings, beards and several roof classes.  This module keeps that graph
and its Java RNG decisions offline so the Bedrock pack never copies a later
rights-reserved structure template.
"""

from __future__ import print_function

import collections


SOURCE_COMMIT = "a7dd8f13c653e137f977f5ffaa870fcb20fc1625"
SOURCE_CLASSES = (
    "TowerMainComponent",
    "TowerWingComponent",
    "TowerBridgeComponent",
    "TowerOutbuildingComponent",
    "TowerBeardComponent",
    "TowerBeardAttachedComponent",
    "TowerRoofPointyOverhangComponent",
    "TowerRoofStairsOverhangComponent",
    "TowerRoofStairsComponent",
    "TowerRoofSlabComponent",
    "TowerRoofGableForwardsComponent",
    "TowerRoofSlabForwardsComponent",
    "TowerRoofAttachedSlabComponent",
    "TowerRoofFenceComponent",
)
FIXED_SOURCE_SEEDS = tuple(
    0x4C494348 + index * 341873128712 + index * index * 132897987541
    for index in range(8)
)

JAVA_MASK = (1 << 48) - 1
JAVA_MULTIPLIER = 0x5DEECE66D
JAVA_ADDEND = 0xB

# Direction order follows Rotation.values() when the root faces south:
# NONE, CLOCKWISE_90, CLOCKWISE_180, COUNTERCLOCKWISE_90.
SOUTH, WEST, NORTH, EAST = range(4)
ROTATIONS = (0, 1, 2, 3)


class JavaRandom(object):
    def __init__(self, seed):
        self.seed = (int(seed) ^ JAVA_MULTIPLIER) & JAVA_MASK

    def next_bits(self, bits):
        self.seed = (
            self.seed * JAVA_MULTIPLIER + JAVA_ADDEND
        ) & JAVA_MASK
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
            if bits - value + (bound - 1) < (1 << 31):
                return value

    def next_boolean(self):
        return self.next_bits(1) != 0


def _rotate_direction(direction, rotation):
    return (int(direction) + int(rotation)) & 3


def _bbox_from_locator(x, y, z, size, height, direction):
    span = int(size) - 1
    if direction == WEST:
        return [x - span, y, z, x, y + height - 1, z + span]
    if direction == NORTH:
        return [x - span, y, z - span, x, y + height - 1, z]
    if direction == EAST:
        return [x, y, z - span, x + span, y + height - 1, z]
    return [x, y, z, x + span, y + height - 1, z + span]


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
    def __init__(
        self,
        kind,
        x,
        y,
        z,
        size,
        height,
        direction=SOUTH,
        parent=None,
        bbox=None,
    ):
        self.kind = str(kind)
        self.locator = (int(x), int(y), int(z))
        self.size = int(size)
        self.height = int(height)
        self.direction = int(direction)
        self.parent = parent
        self.bbox = list(
            bbox
            if bbox is not None
            else _bbox_from_locator(x, y, z, size, height, direction)
        )
        self.openings = []
        self.opening_towards = [False, False, True, False]
        self.highest_opening = 0
        self.roof_kind = None

    def local_to_world(self, x, y, z):
        x, y, z = int(x), int(y), int(z)
        if self.direction == NORTH:
            return self.bbox[0] + x, self.bbox[1] + y, self.bbox[5] - z
        if self.direction == WEST:
            return self.bbox[3] - z, self.bbox[1] + y, self.bbox[2] + x
        if self.direction == EAST:
            return self.bbox[0] + z, self.bbox[1] + y, self.bbox[2] + x
        return self.bbox[0] + x, self.bbox[1] + y, self.bbox[2] + z


class ComponentGraph(object):
    MAX_COMPONENTS = 320

    def __init__(self, seed):
        self.seed = int(seed)
        self.random = JavaRandom(seed)
        self.components = []
        self.main = Component(
            "main",
            0,
            1,
            0,
            15,
            55 + self.random.next_int(32),
            SOUTH,
        )
        self.components.append(self.main)
        self._add_main_children()

    def _first_collision(self, bbox):
        for component in self.components:
            if _intersects(component.bbox, bbox):
                return component
        return None

    @staticmethod
    def _add_opening(component, x, y, z, rotation):
        rotation = int(rotation) & 3
        component.openings.append((int(x), int(y), int(z)))
        component.opening_towards[rotation] = True
        component.highest_opening = max(component.highest_opening, int(y))

    @staticmethod
    def _attached_overhang_bbox(wing, roof_height):
        box = wing.bbox
        if wing.direction == SOUTH:
            return [box[0], box[4], box[2] - 1, box[3] + 1, box[4] + roof_height - 1, box[5] + 1]
        if wing.direction == WEST:
            return [box[0] - 1, box[4], box[2], box[3] + 1, box[4] + roof_height - 1, box[5] + 1]
        if wing.direction == EAST:
            return [box[0] - 1, box[4], box[2] - 1, box[3], box[4] + roof_height - 1, box[5] + 1]
        return [box[0] - 1, box[4], box[2] - 1, box[3] + 1, box[4] + roof_height - 1, box[5]]

    def _roof_candidate(self, wing, kind):
        if kind in ("roof_pointy_overhang", "roof_stairs_overhang"):
            size = wing.size + 2
            height = size if kind == "roof_pointy_overhang" else size // 2
            box = [
                wing.bbox[0] - 1,
                wing.bbox[4],
                wing.bbox[2] - 1,
                wing.bbox[3] + 1,
                wing.bbox[4] + height - 1,
                wing.bbox[5] + 1,
            ]
        elif kind in ("roof_gable_forwards", "roof_slab_forwards"):
            size = wing.size + 2
            height = size if kind == "roof_gable_forwards" else size // 2
            box = self._attached_overhang_bbox(wing, height)
        else:
            size = wing.size
            if kind == "roof_stairs":
                height = size // 2
            elif kind in ("roof_slab", "roof_attached_slab"):
                height = size // 2
            else:
                height = 1
            box = [
                wing.bbox[0],
                wing.bbox[4],
                wing.bbox[2],
                wing.bbox[3],
                wing.bbox[4] + height,
                wing.bbox[5],
            ]
        return Component(
            kind,
            box[0],
            box[1],
            box[2],
            size,
            height,
            wing.direction,
            wing,
            box,
        )

    def _try_roof(self, wing, kind):
        roof = self._roof_candidate(wing, kind)
        if self._first_collision(roof.bbox) is wing:
            self.components.append(roof)
            wing.roof_kind = kind
            return True
        return False

    def _add_roof(self, wing, parent):
        attached = parent.bbox[4] > wing.bbox[4]
        if attached:
            choices = []
            if self.random.next_int(32) != 0:
                choices.append("roof_gable_forwards")
            if self.random.next_int(8) != 0:
                choices.append("roof_slab_forwards")
            if self.random.next_int(32) != 0:
                choices.append("roof_attached_slab")
            choices.append("roof_fence")
        else:
            choices = []
            if self.random.next_int(8) != 0:
                choices.append("roof_pointy_overhang")
            choices.extend(("roof_stairs_overhang", "roof_stairs"))
            if self.random.next_int(53) != 0:
                choices.append("roof_slab")
            choices.append("roof_fence")
        for kind in choices:
            if self._try_roof(wing, kind):
                return
        # The source's fence is the collision-safe last resort.  Keep the same
        # invariant even if a malformed graph makes every normal fit fail.
        roof = self._roof_candidate(wing, "roof_fence")
        self.components.append(roof)
        wing.roof_kind = "roof_fence"

    def _add_beard(self, wing, parent):
        size = wing.size - 2
        height = size // 2
        attached = parent.bbox[1] < wing.bbox[1]
        if attached:
            box = [
                wing.bbox[0],
                wing.bbox[1] - height - 1,
                wing.bbox[2],
                wing.bbox[3],
                wing.bbox[4] - 1,
                wing.bbox[5],
            ]
            kind = "beard_attached"
        else:
            box = [
                wing.bbox[0] + 1,
                wing.bbox[1] - height - 1,
                wing.bbox[2] + 1,
                wing.bbox[3] - 1,
                wing.bbox[1] - 1,
                wing.bbox[5] - 1,
            ]
            kind = "beard"
        self.components.append(
            Component(kind, box[0], box[1], box[2], size, height + 1, wing.direction, wing, box)
        )

    @staticmethod
    def _offset_tower_coords(parent, x, y, z, tower_size, direction):
        dx, dy, dz = parent.local_to_world(x, y, z)
        if direction == SOUTH:
            return dx + 1, dy - 1, dz - tower_size // 2
        if direction == WEST:
            return dx + tower_size // 2, dy - 1, dz + 1
        if direction == NORTH:
            return dx - 1, dy - 1, dz + tower_size // 2
        return dx - tower_size // 2, dy - 1, dz - 1

    def _get_y_by_stairs(self, component, axis, rotation):
        size = component.size
        rise = 1
        base = 0
        if size == 15:
            rise = 10
            base = 23 if rotation in (0, 2) else 28
        elif size == 9:
            rise = 6
            base = 2 if rotation in (0, 2) else 5
        elif size == 7:
            rise = 4
            base = 2 if rotation in (0, 2) else 4
        elif size == 5:
            rise = 4
            base = (3, 2, 5, 4)[rotation]
        flights = ((component.height - 6 - base) // rise) + 1
        if base <= 0 or flights <= 0:
            return 0
        dy = self.random.next_int(flights) * rise + base
        if size == 15:
            delta = (axis - 2) // 2 if rotation in (0, 3) else (size - axis - 3) // 2
        else:
            delta = (axis - 1) // 2 if rotation in (0, 3) else (size - axis - 2) // 2
        return max(1, dy - delta)

    def _valid_opening(self, component, rotation):
        wall_length = component.size - 2
        offset = 1
        if component.size == 15:
            wall_length = 11
            offset = 2
        if rotation in (0, 2):
            x = component.size - 1 if rotation == 0 else 0
            z = offset + self.random.next_int(wall_length)
            y = self._get_y_by_stairs(component, z, rotation)
        else:
            x = offset + self.random.next_int(wall_length)
            z = component.size - 1 if rotation == 1 else 0
            y = self._get_y_by_stairs(component, x, rotation)
        return x, y, z

    def _outbuilding_opening(self, component, rotation):
        if rotation == 0:
            return component.size - 1, 1, 6 + self.random.next_int(8)
        if rotation == 1:
            return 1 + self.random.next_int(11), 1, component.size - 1
        if rotation == 2:
            return 0, 1, 1 + self.random.next_int(8)
        return 3 + self.random.next_int(11), 1, 0

    def _add_direct_wing(self, parent, x, y, z, size, height, rotation, kind="wing"):
        if height < 6 or len(self.components) >= self.MAX_COMPONENTS:
            return False
        direction = _rotate_direction(parent.direction, rotation)
        locator = self._offset_tower_coords(parent, x, y, z, size, direction)
        wing = Component(kind, locator[0], locator[1], locator[2], size, height, direction, parent)
        collision = self._first_collision(wing.bbox)
        if collision is not None and collision is not parent:
            return False
        self.components.append(wing)
        self._add_opening(parent, x, y, z, rotation)
        self._add_wing_children(wing, parent)
        return True

    def _add_bridge(self, parent, x, y, z, size, height, rotation):
        if height < 6 or len(self.components) >= self.MAX_COMPONENTS:
            return False
        direction = _rotate_direction(parent.direction, rotation)
        locator = self._offset_tower_coords(parent, x, y, z, 3, direction)
        bridge = Component("bridge", locator[0], locator[1], locator[2], 3, 3, direction, parent)
        collision = self._first_collision(bridge.bbox)
        if collision is not None and collision is not parent:
            return False
        child_locator = self._offset_tower_coords(bridge, 2, 1, 1, size, direction)
        child = Component("wing", child_locator[0], child_locator[1], child_locator[2], size, height, direction, bridge)
        collision = self._first_collision(child.bbox)
        if collision is not None and collision is not parent:
            return False
        self.components.append(bridge)
        self._add_opening(parent, x, y, z, rotation)
        self.components.append(child)
        self._add_wing_children(child, bridge)
        return True

    def _make_wing(self, parent, x, y, z, size, height, rotation):
        if height < 6:
            return False
        if size == 3 and height > 10:
            height = 6 + self.random.next_int(5)
        if self.random.next_int(6) == 0:
            return self._add_bridge(parent, x, y, z, size, height, rotation)
        if self._add_direct_wing(parent, x, y, z, size, height, rotation):
            return True
        if self.random.next_int(3) > 0:
            return self._add_bridge(parent, x, y, z, size, height, rotation)
        return False

    def _add_wing_children(self, wing, parent):
        self._add_opening(wing, 0, 1, wing.size // 2, 2)
        self._add_roof(wing, parent)
        if wing.kind != "outbuilding":
            self._add_beard(wing, parent)
        if wing.size <= 4:
            return
        for rotation in ROTATIONS:
            if rotation == 2:
                continue
            x, y, z = self._valid_opening(wing, rotation)
            if wing.kind == "outbuilding" and y <= 7:
                continue
            if not self._make_wing(
                wing,
                x,
                y,
                z,
                wing.size - 2,
                wing.height - 4,
                rotation,
            ) and wing.size > 8:
                if not self._make_wing(
                    wing,
                    x,
                    y,
                    z,
                    wing.size - 4,
                    wing.height - 6,
                    rotation,
                ):
                    self._make_wing(
                        wing,
                        x,
                        y,
                        z,
                        wing.size - 6,
                        wing.height - 12,
                        rotation,
                    )

    def _make_outbuilding(self, x, y, z, size, height, rotation):
        direction = _rotate_direction(self.main.direction, rotation)
        locator = self._offset_tower_coords(self.main, x, y, z, size, direction)
        building = Component("outbuilding", locator[0], locator[1], locator[2], size, height, direction, self.main)
        if self._first_collision(building.bbox) is not None:
            return False
        self.components.append(building)
        self._add_opening(self.main, x, y, z, rotation)
        self._add_wing_children(building, self.main)
        return True

    def _add_main_children(self):
        main = self.main
        self._add_roof(main, main)
        for rotation in ROTATIONS:
            x, y, z = self._valid_opening(main, rotation)
            if y < main.height // 2:
                y += 20
            child_height = min(21 + self.random.next_int(10), main.height - y - 3)
            if not self._make_wing(main, x, y, z, 9, child_height, rotation):
                self._make_wing(main, x, y, z, 7, child_height, rotation)
        for rotation in ROTATIONS:
            x, y, z = self._valid_opening(main, rotation)
            if y < main.height // 2:
                y += 10
            child_height = min(21 + self.random.next_int(10), main.height - y - 3)
            if not self._make_wing(main, x, y, z, 9, child_height, rotation):
                self._make_wing(main, x, y, z, 7, child_height, rotation)
        for rotation in ROTATIONS:
            x, y, z = self._valid_opening(main, rotation)
            child_height = min(7 + self.random.next_int(6), main.height - y - 3)
            if not self._make_wing(main, x, y, z, 5, child_height, rotation):
                self._make_wing(main, x, y, z, 3, child_height, rotation)
        for rotation in ROTATIONS:
            x, y, z = self._outbuilding_opening(main, rotation)
            self._make_outbuilding(
                x,
                y,
                z,
                7 + self.random.next_int(2) * 2,
                11 + self.random.next_int(10),
                rotation,
            )
        for _attempt in range(4):
            for rotation in ROTATIONS:
                x, y, z = self._valid_opening(main, rotation)
                child_height = 6 + self.random.next_int(5)
                if self.random.next_int(3) == 0 or not self._make_wing(
                    main, x, y, z, 5, child_height, rotation
                ):
                    self._make_wing(main, x, y, z, 3, child_height, rotation)


class BlockBuffer(object):
    def __init__(self, seed):
        self.seed = int(seed)
        self.blocks = {}
        self.loot = []
        self.spawners = []
        self.room_serial = 0

    def set(self, position, name, states=None):
        self.blocks[tuple(int(value) for value in position)] = (
            str(name),
            dict(states or {}),
        )

    def set_local(self, component, x, y, z, name, states=None):
        self.set(component.local_to_world(x, y, z), name, states)

    def fill_local(self, component, start, end, name, states=None):
        for x in range(start[0], end[0] + 1):
            for y in range(start[1], end[1] + 1):
                for z in range(start[2], end[2] + 1):
                    self.set_local(component, x, y, z, name, states)

    def palette(self, x, y, z, salt=0):
        value = (
            int(x) * 73428767
            ^ int(y) * 912931
            ^ int(z) * 438289
            ^ self.seed * 19349663
            ^ int(salt)
        ) & 0x7FFFFFFF
        # StrongholdStones from the locked Java source: 20% cracked, 30%
        # mossy, 5% infested and 45% normal stone bricks.  A coordinate hash
        # keeps the offline variants deterministic without replacing the
        # source palette with the much rougher cobblestone facade.
        value %= 100
        if value < 20:
            return "minecraft:cracked_stone_bricks"
        if value < 50:
            return "minecraft:mossy_stone_bricks"
        if value < 55:
            return "minecraft:infested_stone_bricks"
        return "minecraft:stone_bricks"


def _rotated_local(size, x, z, rotation):
    rotation &= 3
    if rotation == 1:
        return size - 1 - z, x
    if rotation == 2:
        return size - 1 - x, size - 1 - z
    if rotation == 3:
        return z, size - 1 - x
    return x, z


def _render_shell(buffer, component):
    size = component.size
    height = component.height
    for y in range(height):
        for x in range(size):
            for z in range(size):
                boundary = x in (0, size - 1) or z in (0, size - 1) or y in (0, height - 1)
                if boundary:
                    wx, wy, wz = component.local_to_world(x, y, z)
                    buffer.set((wx, wy, wz), buffer.palette(wx, wy, wz, size))
                else:
                    buffer.set_local(component, x, y, z, "minecraft:air")


def _render_roof(buffer, roof):
    box = roof.bbox
    width = box[3] - box[0] + 1
    depth = box[5] - box[2] + 1
    height = box[4] - box[1] + 1
    kind = roof.kind
    if kind == "roof_fence":
        y = box[1] + 1
        for x in range(box[0], box[3] + 1):
            for z in range(box[2], box[5] + 1):
                if x in (box[0], box[3]) or z in (box[2], box[5]):
                    buffer.set((x, y, z), "minecraft:oak_fence")
        return

    if kind in ("roof_stairs", "roof_stairs_overhang"):
        stair_states = {
            # Java stair facing names the ascent direction; Bedrock's legacy
            # state names the opposite high/back edge.
            "west": {"weirdo_direction": 0, "upside_down_bit": False},
            "east": {"weirdo_direction": 1, "upside_down_bit": False},
            "north": {"weirdo_direction": 2, "upside_down_bit": False},
            "south": {"weirdo_direction": 3, "upside_down_bit": False},
        }
        roof_size = roof.size
        for layer in range(roof_size // 2 + 1):
            minimum = layer
            maximum = roof_size - layer - 1
            if minimum > maximum:
                continue
            for local_x in range(minimum, maximum + 1):
                for local_z in range(minimum, maximum + 1):
                    x = box[0] + local_x
                    z = box[2] + local_z
                    y = box[1] + layer
                    if local_x == minimum:
                        if local_z in (minimum, maximum):
                            buffer.set((x, y, z), "minecraft:birch_slab")
                        else:
                            buffer.set(
                                (x, y, z),
                                "minecraft:birch_stairs",
                                stair_states["west"],
                            )
                    elif local_x == maximum:
                        if local_z in (minimum, maximum):
                            buffer.set((x, y, z), "minecraft:birch_slab")
                        else:
                            buffer.set(
                                (x, y, z),
                                "minecraft:birch_stairs",
                                stair_states["east"],
                            )
                    elif local_z == maximum:
                        buffer.set(
                            (x, y, z),
                            "minecraft:birch_stairs",
                            stair_states["south"],
                        )
                    elif local_z == minimum:
                        buffer.set(
                            (x, y, z),
                            "minecraft:birch_stairs",
                            stair_states["north"],
                        )
                    else:
                        buffer.set((x, y, z), "minecraft:birch_planks")
        return

    roof_size = min(width, depth)
    for layer in range(height):
        if kind in ("roof_slab", "roof_attached_slab", "roof_slab_forwards"):
            inset = layer * 2
        elif kind == "roof_gable_forwards":
            slope = 3 if roof_size > 10 else 2 if roof_size > 6 else 1
            inset = layer if layer < slope else (layer + slope) // 2
        else:
            slope = 3 if roof_size > 10 else 2 if roof_size > 6 else 1
            inset = layer if kind == "roof_stairs_overhang" or kind == "roof_stairs" else (
                layer if layer < slope else (layer + slope) // 2
            )
        min_x = box[0] + (0 if kind in ("roof_gable_forwards", "roof_slab_forwards") else inset)
        max_x = box[3] - inset
        min_z = box[2] + inset
        max_z = box[5] - inset
        if min_x > max_x or min_z > max_z:
            continue
        for x in range(min_x, max_x + 1):
            for z in range(min_z, max_z + 1):
                edge = x in (min_x, max_x) or z in (min_z, max_z)
                if kind in ("roof_slab", "roof_attached_slab", "roof_slab_forwards") and edge:
                    name = "minecraft:birch_slab"
                else:
                    name = "minecraft:birch_planks"
                buffer.set((x, box[1] + layer, z), name)
        # Pointy roofs use slab ornaments at corners and midpoints.
        if kind == "roof_pointy_overhang":
            for x, z in ((min_x, min_z), (min_x, max_z), (max_x, min_z), (max_x, max_z)):
                buffer.set((x, box[1] + layer + 1, z), "minecraft:birch_slab")


def _render_beard(buffer, beard):
    box = beard.bbox
    height = beard.height
    if beard.kind == "beard_attached":
        # TowerBeardAttachedComponent deliberately keeps a tall collision box,
        # but only draws the source component's short one-sided stone wedge.
        # Using the bounding-box height here would fill most of the child tower.
        source_height = height - 1
        for slope in range(source_height + 1):
            minimum = slope + 1
            maximum = beard.size - slope
            for x in range(0, maximum + 1):
                for z in range(minimum, maximum + 1):
                    wx, wy, wz = beard.local_to_world(
                        x, source_height - slope, z
                    )
                    buffer.set((wx, wy, wz), buffer.palette(wx, wy, wz, 91))
        return
    for layer in range(height):
        inset = height - layer - 1
        min_x = min(box[3], box[0] + inset)
        max_x = max(box[0], box[3] - inset)
        min_z = min(box[5], box[2] + inset)
        max_z = max(box[2], box[5] - inset)
        for x in range(min_x, max_x + 1):
            for z in range(min_z, max_z + 1):
                buffer.set((x, box[1] + layer, z), buffer.palette(x, box[1] + layer, z, 91))


def _render_bridge(buffer, bridge):
    for x in range(3):
        for z in range(3):
            buffer.set_local(bridge, x, 0, z, "minecraft:stone_bricks")
        for z in (0, 2):
            buffer.set_local(bridge, x, 1, z, "minecraft:stone_bricks")
            buffer.set_local(bridge, x, 2, z, "minecraft:oak_fence")
        buffer.set_local(bridge, x, 1, 1, "minecraft:air")
        buffer.set_local(bridge, x, 2, 1, "minecraft:air")


def _render_ladder(buffer, component, floor_bottom, floor_top, rotation):
    size = component.size
    center = size // 2
    ladder_and_support = (
        ((size - 2, center - 1), (size - 1, center - 1)),
        ((center + 1, size - 2), (center + 1, size - 1)),
        ((1, center + 1), (0, center + 1)),
        ((center - 1, 1), (center - 1, 0)),
    )
    # Bedrock ladders validate their backing block from facing_direction as
    # soon as a structure tile is placed.  A stateless ladder defaults to a
    # direction that is wrong for three of these four walls and immediately
    # breaks into an item entity.
    rotation &= 3
    (x, z), (support_x, support_z) = ladder_and_support[rotation]

    # A child-tower doorway can occupy the preferred backing column.  Move
    # the complete ladder one column along the same wall instead of letting
    # makeOpenings remove its support after the ladder has been serialized.
    for offset in (0, -1, 1, -2, 2):
        candidate_x = x + (offset if rotation in (1, 3) else 0)
        candidate_z = z + (offset if rotation in (0, 2) else 0)
        candidate_support_x = support_x + (
            offset if rotation in (1, 3) else 0
        )
        candidate_support_z = support_z + (
            offset if rotation in (0, 2) else 0
        )
        if not (
            1 <= candidate_x <= size - 2
            and 1 <= candidate_z <= size - 2
        ):
            continue
        blocked = False
        for opening_x, opening_y, opening_z in component.openings:
            if (
                opening_x == candidate_support_x
                and opening_z == candidate_support_z
                and opening_y <= floor_top - 1
                and opening_y + 1 >= floor_bottom
            ):
                blocked = True
                break
        if not blocked:
            x, z = candidate_x, candidate_z
            support_x, support_z = (
                candidate_support_x,
                candidate_support_z,
            )
            break

    ladder_world = component.local_to_world(x, floor_bottom, z)
    support_world = component.local_to_world(
        support_x,
        floor_bottom,
        support_z,
    )
    support_delta = (
        support_world[0] - ladder_world[0],
        support_world[2] - ladder_world[2],
    )
    facing_direction = {
        (0, 1): 2,
        (0, -1): 3,
        (1, 0): 4,
        (-1, 0): 5,
    }[support_delta]
    for y in range(floor_bottom, floor_top):
        buffer.set_local(
            component,
            x,
            y,
            z,
            "minecraft:ladder",
            {"facing_direction": facing_direction},
        )


ROOM_POOL = (
    "well",
    "skeleton",
    "zombie",
    "cactus",
    "treasure",
    "webs",
    "tnt",
    "full_library",
    "library",
)


def _decorate_room(buffer, component, bottom, top, ladder_up, ladder_down):
    size = component.size
    center = size // 2
    room_kind = ROOM_POOL[(buffer.room_serial + buffer.seed) % len(ROOM_POOL)]
    buffer.room_serial += 1
    if room_kind == "well":
        for x in range(center - 1, center + 2):
            for z in range(center - 1, center + 2):
                buffer.set_local(component, x, bottom, z, "minecraft:stone_bricks")
        buffer.set_local(component, center, bottom, center, "minecraft:water")
        buffer.set_local(component, center, bottom - 1, center, "minecraft:water")
    elif room_kind in ("skeleton", "zombie"):
        world_pos = component.local_to_world(center, bottom + 2, center)
        buffer.spawners.append((world_pos, "minecraft:%s" % room_kind))
        for x in range(2, size - 2, 2):
            buffer.set_local(component, x, bottom, center, "minecraft:iron_bars")
            buffer.set_local(component, x, bottom + 1, center, "minecraft:soul_sand")
    elif room_kind == "cactus":
        for x in range(1, size - 1):
            for z in range(1, size - 1):
                buffer.set_local(component, x, bottom - 1, z, "minecraft:sand")
        for x, z in ((2, 2), (size - 3, size - 3), (2, size - 3)):
            for y in range(bottom, min(top, bottom + 3)):
                buffer.set_local(component, x, y, z, "minecraft:cactus")
    elif room_kind == "treasure":
        buffer.loot.append((component.local_to_world(center, bottom + 1, center), "lich_tower_room"))
        for y in range(bottom, top):
            for x, z in ((center - 1, center - 1), (center + 1, center - 1), (center - 1, center + 1), (center + 1, center + 1)):
                buffer.set_local(component, x, y, z, "minecraft:stone_bricks")
    elif room_kind == "webs":
        for y in range(bottom, top):
            for x in range(1, size - 1):
                for z in range(1, size - 1):
                    if (x * 5 + y * 3 + z * 7 + buffer.seed) % max(2, top - y + 1) == 0:
                        buffer.set_local(component, x, y, z, "minecraft:web")
    elif room_kind == "tnt":
        for x, z in ((center, center), (center + 1, center), (center, center + 1)):
            buffer.set_local(component, x, bottom - 1, z, "minecraft:tnt")
        buffer.set_local(component, center, bottom, center, "minecraft:stone_pressure_plate")
    else:
        full = room_kind == "full_library"
        for x in range(1, size - 1):
            for z in range(1, size - 1):
                edge = x in (1, size - 2) or z in (1, size - 2)
                ring = full and (x % 2 == 1 or z % 2 == 1)
                if not edge and not ring:
                    continue
                for y in range(bottom, top - 1):
                    buffer.set_local(component, x, y, z, "minecraft:bookshelf")
        if size > 5:
            buffer.loot.append((component.local_to_world(1, top - 2, size - 3), "lich_tower_room"))
            buffer.set_local(component, center, bottom, center, "minecraft:oak_fence")
            # NetEase retains the legacy oak pressure-plate identifier. The
            # modern Java name is not registered and crashes async structure
            # decoding while Twilight chunks are generated.
            buffer.set_local(component, center, bottom + 1, center, "minecraft:wooden_pressure_plate")


def _render_wing_interior(buffer, component):
    floors = max(1, (component.height - 1) // 5)
    floor_height = max(4, component.height // floors)
    for index in range(1, floors):
        y = index * floor_height
        for x in range(1, component.size - 1):
            for z in range(1, component.size - 1):
                buffer.set_local(component, x, y, z, "minecraft:birch_planks")
    ladder_rotation = 3
    for index in range(floors):
        bottom = 1 if index == 0 else index * floor_height + 1
        top = component.height - 1 if index == floors - 1 else (index + 1) * floor_height
        next_rotation = (ladder_rotation + 1) & 3
        if index < floors - 1:
            _render_ladder(buffer, component, bottom, top, next_rotation)
        if index > 0:
            _render_ladder(buffer, component, bottom - 1, min(top, bottom + 2), ladder_rotation)
        _decorate_room(
            buffer,
            component,
            bottom,
            top,
            next_rotation if index < floors - 1 else None,
            ladder_rotation if index > 0 else None,
        )
        ladder_rotation = next_rotation


def _render_windows(buffer, component):
    """Render the legacy tower's four lower and optional upper window bays."""
    size = component.size
    center = size // 2
    window_rows = [(2, 3, 1)]
    if component.height > 8:
        window_rows.append((component.height - 3, component.height - 4, component.height - 5))

    for rotation in ROTATIONS:
        real_windows = size < 4 and not component.opening_towards[rotation]
        window_x, window_z = _rotated_local(size, size - 1, center, rotation)
        inside_x, inside_z = _rotated_local(size, size - 2, center, rotation)
        outside_x, outside_z = _rotated_local(size, size, center, rotation)
        for first_y, second_y, base_y in window_rows:
            for y in (first_y, second_y):
                inside = buffer.blocks.get(component.local_to_world(inside_x, y, inside_z))
                outside = buffer.blocks.get(component.local_to_world(outside_x, y, outside_z))
                inside_air = inside is None or inside[0] == "minecraft:air"
                outside_air = outside is None or outside[0] == "minecraft:air"
                block = (
                    "minecraft:glass_pane"
                    if real_windows and inside_air and outside_air
                    else "minecraft:cobblestone"
                )
                buffer.set_local(component, window_x, y, window_z, block)
            buffer.set_local(
                component,
                window_x,
                base_y,
                window_z,
                "minecraft:smooth_stone",
            )


BOTTOM_SLAB = {"top_slot_bit": False}
TOP_SLAB = {"top_slot_bit": True}


def _set_rotated_main(
    buffer,
    main,
    x,
    y,
    z,
    rotation,
    name,
    states=None,
):
    rotated_x, rotated_z = _rotated_local(15, x, z, rotation)
    buffer.set_local(main, rotated_x, y, rotated_z, name, states)


def _maybe_set_rotated_main(
    buffer,
    main,
    x,
    y,
    z,
    rotation,
    name,
    states=None,
    salt=0,
):
    # The Java component uses maybeGenerateBlock(..., 0.9F).  Keep the same
    # deterministic erosion rate without tying the offline compiler to the
    # runtime chunk iteration order used by StructurePiece.postProcess.
    value = (
        int(x) * 73428767
        ^ int(y) * 912931
        ^ int(z) * 438289
        ^ int(rotation) * 19349663
        ^ int(buffer.seed)
        ^ int(salt)
    ) & 1023
    if value < 922:
        _set_rotated_main(
            buffer,
            main,
            x,
            y,
            z,
            rotation,
            name,
            states,
        )


def _render_main_stair_foot(buffer, main):
    birch_slab = "minecraft:birch_slab"
    birch_planks = "minecraft:birch_planks"
    stone_slab = "minecraft:stone_slab"
    double_stone = "minecraft:smooth_stone"
    fence = "minecraft:oak_fence"

    for x, y, z, name, states in (
        (1, 1, 9, birch_slab, BOTTOM_SLAB),
        (2, 1, 9, birch_slab, BOTTOM_SLAB),
        (1, 1, 10, birch_planks, None),
        (2, 1, 10, birch_planks, None),
        (1, 2, 11, birch_slab, BOTTOM_SLAB),
        (2, 2, 11, birch_slab, BOTTOM_SLAB),
        (1, 2, 12, birch_planks, None),
        (2, 2, 12, birch_planks, None),
        (1, 2, 13, birch_planks, None),
        (2, 2, 13, birch_planks, None),
        (3, 2, 11, birch_planks, None),
        (3, 3, 11, fence, None),
        (3, 4, 11, fence, None),
        (3, 1, 10, birch_planks, None),
        (3, 2, 10, fence, None),
        (3, 3, 10, fence, None),
        (3, 1, 9, birch_planks, None),
        (3, 2, 9, fence, None),
        (13, 1, 5, stone_slab, BOTTOM_SLAB),
        (12, 1, 5, stone_slab, BOTTOM_SLAB),
        (13, 1, 4, double_stone, None),
        (12, 1, 4, double_stone, None),
        (13, 2, 3, stone_slab, BOTTOM_SLAB),
        (12, 2, 3, stone_slab, BOTTOM_SLAB),
        (13, 2, 2, double_stone, None),
        (12, 2, 2, double_stone, None),
        (13, 2, 1, double_stone, None),
        (12, 2, 1, double_stone, None),
        (11, 2, 3, double_stone, None),
        (11, 3, 3, fence, None),
        (11, 4, 3, fence, None),
        (11, 1, 4, double_stone, None),
        (11, 2, 4, fence, None),
        (11, 3, 4, fence, None),
        (11, 1, 5, double_stone, None),
        (11, 2, 5, fence, None),
    ):
        buffer.set_local(main, x, y, z, name, states)


def _render_main_stair_flight(buffer, main, height, rotation, use_birch):
    slab = "minecraft:birch_slab" if use_birch else "minecraft:stone_slab"
    double = "minecraft:birch_planks" if use_birch else "minecraft:smooth_stone"
    fence = "minecraft:oak_fence"

    mandatory = (
        (3, 1, 13, slab, BOTTOM_SLAB),
        (5, 2, 13, slab, BOTTOM_SLAB),
        (6, 2, 13, slab, TOP_SLAB),
        (7, 3, 13, slab, BOTTOM_SLAB),
        (8, 3, 13, slab, TOP_SLAB),
        (9, 4, 13, slab, BOTTOM_SLAB),
        (12, 5, 13, slab, TOP_SLAB),
        (13, 5, 13, slab, TOP_SLAB),
        (4, 1, 12, slab, TOP_SLAB),
        (5, 2, 12, slab, BOTTOM_SLAB),
        (6, 2, 12, slab, TOP_SLAB),
        (8, 3, 12, slab, TOP_SLAB),
        (9, 4, 12, slab, BOTTOM_SLAB),
        (11, 5, 12, slab, BOTTOM_SLAB),
        (12, 5, 12, slab, TOP_SLAB),
        (13, 5, 12, slab, TOP_SLAB),
        (4, 1, 11, double, None),
        (5, 2, 11, double, None),
        (7, 3, 11, double, None),
        (9, 4, 11, double, None),
        (10, 4, 11, slab, TOP_SLAB),
        (11, 5, 11, double, None),
        (4, 2, 11, fence, None),
        (5, 3, 11, fence, None),
        (6, 3, 11, fence, None),
        (7, 4, 11, fence, None),
        (8, 4, 11, fence, None),
        (9, 5, 11, fence, None),
        (10, 5, 11, fence, None),
        (11, 6, 11, fence, None),
        (4, 3, 11, fence, None),
        (6, 4, 11, fence, None),
        (8, 5, 11, fence, None),
        (10, 6, 11, fence, None),
        (11, 7, 11, fence, None),
    )
    optional = (
        (4, 1, 13, slab, TOP_SLAB),
        (10, 4, 13, slab, TOP_SLAB),
        (11, 5, 13, slab, BOTTOM_SLAB),
        (3, 1, 12, slab, BOTTOM_SLAB),
        (7, 3, 12, slab, BOTTOM_SLAB),
        (10, 4, 12, slab, TOP_SLAB),
        (6, 2, 11, slab, TOP_SLAB),
        (8, 3, 11, slab, TOP_SLAB),
    )
    for x, relative_y, z, name, states in mandatory:
        _set_rotated_main(
            buffer,
            main,
            x,
            relative_y + height,
            z,
            rotation,
            name,
            states,
        )
    for index, (x, relative_y, z, name, states) in enumerate(optional):
        _maybe_set_rotated_main(
            buffer,
            main,
            x,
            relative_y + height,
            z,
            rotation,
            name,
            states,
            0x15F100 + index,
        )


def _render_main_stairs(buffer, main):
    # TowerMainComponent applies this correction before makeStairs15.
    if main.height - main.highest_opening > 15:
        main.highest_opening = main.height - 15
    _render_main_stair_foot(buffer, main)
    for flight in range(max(1, main.highest_opening // 5)):
        height = 2 + flight * 5
        rotation = (flight * 3) & 3
        _render_main_stair_flight(
            buffer,
            main,
            height,
            rotation,
            True,
        )
        _render_main_stair_flight(
            buffer,
            main,
            height,
            (rotation + 2) & 3,
            False,
        )


def _render_main_crossings(buffer, main):
    random = JavaRandom(buffer.seed ^ 0x43524F5353494E47)
    flights = (main.highest_opening // 5) - 2
    flight = 2 + random.next_int(2)
    while flight < flights:
        rotation = 1 if flight % 2 == 0 else 0
        floor_y = flight * 5
        floor_name = (
            "minecraft:smooth_stone"
            if random.next_boolean()
            else "minecraft:birch_planks"
        )
        for x in range(6, 9):
            for z in range(4, 11):
                _set_rotated_main(
                    buffer, main, x, floor_y, z, rotation, floor_name
                )
        for z in range(3, 12):
            _set_rotated_main(
                buffer,
                main,
                6,
                floor_y + 1,
                z,
                rotation,
                "minecraft:oak_fence",
            )
            _set_rotated_main(
                buffer,
                main,
                7,
                floor_y + 1,
                z,
                rotation,
                "minecraft:air",
            )
            _set_rotated_main(
                buffer,
                main,
                8,
                floor_y + 1,
                z,
                rotation,
                "minecraft:oak_fence",
            )
        for x, y, z, name in (
            (6, floor_y, 11, floor_name),
            (8, floor_y, 3, floor_name),
            (5, floor_y + 1, 11, "minecraft:oak_fence"),
            (9, floor_y + 1, 3, "minecraft:oak_fence"),
            (6, floor_y + 2, 7, "minecraft:oak_fence"),
            (8, floor_y + 2, 7, "minecraft:oak_fence"),
            (6, floor_y + 3, 7, "minecraft:oak_fence"),
            (8, floor_y + 3, 7, "minecraft:oak_fence"),
        ):
            _set_rotated_main(
                buffer, main, x, y, z, rotation, name
            )
        spawner_x, spawner_z = _rotated_local(15, 7, 7, rotation)
        mob_roll = random.next_int(4)
        mob = "minecraft:zombie" if mob_roll == 2 else "minecraft:skeleton"
        buffer.spawners.append(
            (main.local_to_world(spawner_x, floor_y + 3, spawner_z), mob)
        )
        flight += 1 + random.next_int(5)


def _render_lich_room(buffer, main):
    floor = 2 + (main.highest_opening // 5) * 5
    rotation = 0 if (main.highest_opening // 5) % 2 == 0 else 1
    for x in range(1, 14):
        for z in range(1, 14):
            rx, rz = _rotated_local(15, x, z, rotation)
            if x in (1, 2) and 6 <= z <= 12:
                at_stair_lip = z == 6
                if at_stair_lip:
                    buffer.set_local(
                        main,
                        rx,
                        floor,
                        rz,
                        "minecraft:birch_slab",
                        TOP_SLAB,
                    )
                else:
                    buffer.set_local(main, rx, floor, rz, "minecraft:air")
            elif x in (12, 13) and 3 <= z <= 8:
                # Keep the paired spiral throughout the tower, but terminate
                # its stone branch below the boss arena.  Only the birch
                # branch above may pierce this floor.
                buffer.set_local(
                    main, rx, floor, rz, "minecraft:birch_planks"
                )
            elif 4 <= x <= 10 and 4 <= z <= 10 and (x, z) not in ((4, 4), (10, 10)):
                buffer.set_local(main, rx, floor, rz, "minecraft:glass")
            elif (x in (2, 3) and z in (2, 3)) or (x in (11, 12) and z in (11, 12)):
                buffer.set_local(main, rx, floor, rz, "minecraft:glass")
            else:
                buffer.set_local(main, rx, floor, rz, "minecraft:birch_planks")
    for x, y, z in (
        (3, floor + 1, 11),
        (3, floor + 1, 10),
        (3, floor + 2, 11),
        (11, floor + 1, 3),
        (11, floor + 1, 4),
        (11, floor + 2, 3),
    ):
        rx, rz = _rotated_local(15, x, z, rotation)
        buffer.set_local(main, rx, y, rz, "minecraft:air")
    center = 7
    buffer.set_local(main, center, floor + 2, center, "tf_slice:lich_boss_spawner")
    # Keep the source twelve-arm silhouette, but hang it in the upper arena.
    # The Java layout's floor+4 placement intersects the much taller Bedrock
    # boss while the NetEase marker waits for stable actor confirmation.
    chandelier_y = max(floor + 7, main.height - 6)
    arms = ((1, 0), (2, 0), (1, 1), (0, 1), (0, 2), (-1, 1), (-1, 0), (-2, 0), (-1, -1), (0, -1), (0, -2), (1, -1))
    for dx, dz in arms:
        buffer.set_local(main, center + dx, chandelier_y, center + dz, "minecraft:oak_fence")
        buffer.set_local(main, center + dx, chandelier_y + 1, center + dz, "minecraft:torch")
    for y in range(chandelier_y + 1, main.height - 1):
        buffer.set_local(main, center, y, center, "minecraft:oak_fence")
    return main.local_to_world(center, floor + 2, center)


def _render_openings(buffer, component):
    for x, y, z in component.openings:
        buffer.set_local(component, x, y, z, "minecraft:air")
        buffer.set_local(component, x, y + 1, z, "minecraft:air")
        buffer.set_local(component, x, y + 2, z, "minecraft:stone_slab")


def _repair_ladder_supports(
    buffer,
    normalized_offset=(0, 0),
    structure_size=None,
):
    """Resolve supports after overlapping source components and doors."""
    support_offsets = {
        2: (0, 0, 1),
        3: (0, 0, -1),
        4: (1, 0, 0),
        5: (-1, 0, 0),
    }
    non_supporting = {
        "minecraft:air",
        "minecraft:ladder",
        "minecraft:torch",
        "minecraft:water",
        "minecraft:web",
    }

    def support_is_in_same_tiles(position, support_position):
        if structure_size is None:
            return True
        position_x = position[0] + int(normalized_offset[0])
        position_z = position[2] + int(normalized_offset[1])
        support_x = support_position[0] + int(normalized_offset[0])
        support_z = support_position[2] + int(normalized_offset[1])
        if (
            position_x // 16 != support_x // 16
            or position_z // 16 != support_z // 16
        ):
            return False
        native_position_x = (
            8 - int(structure_size[0]) // 2 + position_x
        )
        native_position_z = (
            8 - int(structure_size[1]) // 2 + position_z
        )
        native_support_x = (
            8 - int(structure_size[0]) // 2 + support_x
        )
        native_support_z = (
            8 - int(structure_size[1]) // 2 + support_z
        )
        return (
            native_position_x // 16 == native_support_x // 16
            and native_position_z // 16 == native_support_z // 16
        )

    for position, block in list(buffer.blocks.items()):
        if block[0] != "minecraft:ladder":
            continue
        preferred = block[1].get("facing_direction")
        facings = [preferred] if preferred in support_offsets else []
        facings.extend(
            facing for facing in (2, 3, 4, 5) if facing != preferred
        )
        repaired_facing = None
        for facing in facings:
            dx, dy, dz = support_offsets[facing]
            support_position = (
                position[0] + dx,
                position[1] + dy,
                position[2] + dz,
            )
            support = buffer.blocks.get(support_position)
            if (
                support is not None
                and support[0] not in non_supporting
                and support_is_in_same_tiles(position, support_position)
            ):
                repaired_facing = facing
                break
        if repaired_facing is None:
            # Serializing an unsupported ladder creates a dropped item during
            # tile placement.  An explicit air cell is deterministic and safe.
            buffer.set(position, "minecraft:air")
        elif repaired_facing != preferred:
            buffer.set(
                position,
                "minecraft:ladder",
                {"facing_direction": repaired_facing},
            )


def _compile_controlled_spawn_offsets(buffer, towers, shift, limit=256):
    """Compile floor-supported, two-block-high air cells inside tower shells."""
    safe_floors = frozenset(
        (
            "minecraft:stone_bricks",
            "minecraft:cracked_stone_bricks",
            "minecraft:mossy_stone_bricks",
            "minecraft:infested_stone_bricks",
            "minecraft:cobblestone",
            "minecraft:smooth_stone",
            "minecraft:stone_slab",
            "minecraft:birch_planks",
            "minecraft:birch_slab",
            "minecraft:sand",
        )
    )
    occupied_markers = set(position for position, _loot in buffer.loot)
    occupied_markers.update(position for position, _entity in buffer.spawners)
    candidates = set()
    for component in towers:
        maximum_y = component.height - 2
        if component.kind == "main":
            boss_floor = 2 + (component.highest_opening // 5) * 5
            maximum_y = min(maximum_y, boss_floor - 1)
        for y in range(1, maximum_y + 1):
            for x in range(1, component.size - 1):
                for z in range(1, component.size - 1):
                    feet = component.local_to_world(x, y, z)
                    head = component.local_to_world(x, y + 1, z)
                    floor = component.local_to_world(x, y - 1, z)
                    feet_block = buffer.blocks.get(feet)
                    head_block = buffer.blocks.get(head)
                    floor_block = buffer.blocks.get(floor)
                    if feet in occupied_markers or head in occupied_markers:
                        continue
                    if feet_block is None or feet_block[0] != "minecraft:air":
                        continue
                    if head_block is None or head_block[0] != "minecraft:air":
                        continue
                    if floor_block is None or floor_block[0] not in safe_floors:
                        continue
                    candidates.add(
                        (
                            feet[0] + shift[0],
                            feet[1] + shift[1],
                            feet[2] + shift[2],
                        )
                    )

    ordered = sorted(candidates, key=lambda value: (value[1], value[0], value[2]))
    limit = max(1, int(limit))
    if len(ordered) > limit:
        total = len(ordered)
        ordered = [ordered[(index * total) // limit] for index in range(limit)]
    return [list(position) for position in ordered]


def build_lich_tower(seed, structure_factory, set_loot_container, set_spawner):
    variant_index = int(seed)
    source_seed = FIXED_SOURCE_SEEDS[variant_index % len(FIXED_SOURCE_SEEDS)]
    graph = ComponentGraph(source_seed)
    buffer = BlockBuffer(source_seed)
    towers = [
        component
        for component in graph.components
        if component.kind in ("main", "wing", "outbuilding")
    ]
    roofs = [component for component in graph.components if component.kind.startswith("roof_")]

    for component in graph.components:
        if component.kind in ("main", "wing", "outbuilding"):
            _render_shell(buffer, component)
        elif component.kind.startswith("roof_"):
            _render_roof(buffer, component)
        elif component.kind.startswith("beard"):
            _render_beard(buffer, component)
        elif component.kind == "bridge":
            _render_bridge(buffer, component)

    for component in towers:
        if component.kind == "main":
            _render_main_stairs(buffer, component)
        else:
            _render_wing_interior(buffer, component)
    for component in towers:
        _render_windows(buffer, component)
    # Source ordering matters: door openings cut the flights first, then the
    # crossings and Lich floor remove/replace only their intended rail cells.
    for component in towers:
        _render_openings(buffer, component)
    _render_main_crossings(buffer, graph.main)
    boss_world = _render_lich_room(buffer, graph.main)

    # The locked vertical-slice contract requires these room families in every
    # compiled seed.  Recursive source rooms normally provide them; these
    # concealed main-tower accents keep a rare RNG sequence from erasing a
    # whole gameplay system from one of only eight offline variants.
    required = collections.Counter(block[0] for block in buffer.blocks.values())
    if not required["minecraft:bookshelf"]:
        for y in range(2, 5):
            buffer.set_local(graph.main, 2, y, 2, "minecraft:bookshelf")
    if not required["minecraft:web"]:
        for x in range(3, 7):
            buffer.set_local(graph.main, x, 8, 2, "minecraft:web")
    if not required["minecraft:tnt"]:
        buffer.set_local(graph.main, 3, 1, 3, "minecraft:tnt")

    all_positions = list(buffer.blocks)
    all_positions.extend(position for position, _loot in buffer.loot)
    all_positions.extend(position for position, _entity in buffer.spawners)
    minimum_x = min(position[0] for position in all_positions)
    minimum_y = min(position[1] for position in all_positions)
    minimum_z = min(position[2] for position in all_positions)
    maximum_x = max(position[0] for position in all_positions)
    maximum_y = max(position[1] for position in all_positions)
    maximum_z = max(position[2] for position in all_positions)
    shift = (-minimum_x, -minimum_y, -minimum_z)
    result_size = (
        max(47, maximum_x - minimum_x + 1),
        maximum_y - minimum_y + 1,
        max(47, maximum_z - minimum_z + 1),
    )
    _repair_ladder_supports(
        buffer,
        (shift[0], shift[2]),
        (result_size[0], result_size[2]),
    )
    controlled_spawn_offsets = _compile_controlled_spawn_offsets(
        buffer,
        towers,
        shift,
    )
    result = structure_factory(
        result_size,
        "lich_tower_v%02d" % int(seed),
    )
    for (x, y, z), (name, states) in buffer.blocks.items():
        result.set(x + shift[0], y + shift[1], z + shift[2], name, states)
    for (position, loot_id) in buffer.loot:
        set_loot_container(
            result,
            position[0] + shift[0],
            position[1] + shift[1],
            position[2] + shift[2],
            loot_id,
        )
    for (position, entity_id) in buffer.spawners:
        set_spawner(
            result,
            position[0] + shift[0],
            position[1] + shift[1],
            position[2] + shift[2],
            entity_id,
        )
    boss_offset = [
        boss_world[0] + shift[0],
        boss_world[1] + shift[1],
        boss_world[2] + shift[2],
    ]
    result.lich_tower_metadata = {
        "sourceCommit": SOURCE_COMMIT,
        "sourceClasses": list(SOURCE_CLASSES),
        "mainSize": 15,
        "layoutSeed": source_seed,
        "mainHeight": graph.main.height,
        "towerCount": len(towers),
        "roofCount": len(roofs),
        "componentCount": len(graph.components),
        "componentKinds": sorted(set(component.kind for component in graph.components)),
        "bossSpawnerOffset": boss_offset,
        "controlledSpawnOffsets": controlled_spawn_offsets,
        "sourceBounds": [minimum_x, minimum_y, minimum_z, maximum_x, maximum_y, maximum_z],
    }
    return result
