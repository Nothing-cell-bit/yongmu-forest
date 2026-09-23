# -*- coding: utf-8 -*-
"""Read-only pond preflight followed by one complete lily-pad block write."""
from collections import deque

TRIGGER = "tf_slice:swamp/huge_lily_pad/candidate"
NOOP = "tf_slice:ruin_landmark_noop"
PAD = "tf_slice:huge_lily_pad"
WATER = ("minecraft:water", "minecraft:flowing_water")
AIR = ("minecraft:air", "minecraft:cave_air", "minecraft:void_air")
OFFSETS = tuple((x, z) for x in (-1, 0, 1) for z in (-1, 0, 1))
MAX_PENDING = 512
PER_TICK = 4
MAX_RETRIES = 40


class LilyPadWorldgenService(object):
    def __init__(self, feature, read, write, dimension, ready):
        self.feature = feature
        self.read = read
        self.write = write
        self.dimension = int(dimension)
        self.ready = ready
        self.pending = deque()
        self.keys = set()
        self.registered = []
        try:
            for name in (TRIGGER, NOOP):
                if not feature.AddNeteaseFeatureWhiteList(name):
                    raise RuntimeError("Lily candidate whitelist rejected: " + name)
                self.registered.append(name)
        except Exception:
            self.destroy()
            raise

    def destroy(self):
        for name in self.registered:
            try:
                self.feature.RemoveNeteaseFeatureWhiteList(name)
            except Exception:
                pass
        self.registered = []
        self.pending.clear()
        self.keys.clear()

    def on_structure_feature_event(self, args):
        if args.get("structureName") != TRIGGER:
            return
        # Same native handoff contract as the mushroom/tree services. The
        # candidate template is itself empty, so even unavailable Python
        # handling cannot leave a marker block in the pond.
        args["structureName"] = NOOP
        try:
            if int(args.get("dimensionId", -1)) != self.dimension:
                return
            pos = tuple(int(args[axis]) for axis in ("x", "y", "z"))
        except (KeyError, ValueError, TypeError, OverflowError):
            return
        if not (-64 <= pos[1] <= 320 and abs(pos[0]) <= 30000000 and abs(pos[2]) <= 30000000):
            return
        if pos in self.keys or len(self.pending) >= MAX_PENDING:
            return
        self.keys.add(pos)
        self.pending.append((pos, 0))

    def _name(self, pos):
        block = self.read(pos, self.dimension)
        return block.get("name") if isinstance(block, dict) else None

    def _place(self, pos):
        x, event_y, z = pos
        # The existing projected water search can report up to eight blocks
        # above the actual pond. Bound this correction without loading areas.
        for y in range(min(319, event_y + 2), max(-64, event_y - 16), -1):
            cell = self._name((x, y, z))
            if cell is None:
                return None
            if cell not in AIR + WATER:
                return False
            if cell not in AIR:
                continue
            below = self._name((x, y - 1, z))
            if below is None:
                return None
            if below not in WATER:
                continue
            for dx, dz in OFFSETS:
                current = self._name((x + dx, y, z + dz))
                support = self._name((x + dx, y - 1, z + dz))
                if current is None or support is None:
                    return None
                if current not in AIR or support not in WATER:
                    return False
            target = (x, y, z)
            result = self.write(target, PAD, self.dimension)
            # SetBlockNew(False) can also mean no change; verify the result.
            return result is not False or self._name(target) == PAD
        return False

    def tick(self):
        for _ in range(min(PER_TICK, len(self.pending))):
            pos, retries = self.pending.popleft()
            result = None
            try:
                positions = ((pos[0] + dx, pos[1], pos[2] + dz) for dx, dz in OFFSETS)
                if all(self.ready(point, self.dimension) for point in positions):
                    result = self._place(pos)
            except Exception:
                result = None
            if result is None and retries + 1 < MAX_RETRIES:
                self.pending.append((pos, retries + 1))
            else:
                self.keys.discard(pos)
