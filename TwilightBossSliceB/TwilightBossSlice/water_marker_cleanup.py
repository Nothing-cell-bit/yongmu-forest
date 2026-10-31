# -*- coding: utf-8 -*-
"""Bounded cleanup of recorded water-surface no-op markers.

Producer methods only append immutable event data. World APIs are called by
tick on the server thread, after entry and loaded-chunk notifications.
"""
from collections import deque, OrderedDict

NOOP = "tf_slice:ruin_landmark_noop"
VOID = "minecraft:structure_void"
AIR = "minecraft:air"
WATER = ("minecraft:water", "minecraft:flowing_water")
SUPPORT = WATER + ("minecraft:dirt", "minecraft:grass", "minecraft:grass_block",
                   "minecraft:sand", "minecraft:gravel", "minecraft:clay",
                   "minecraft:stone", "minecraft:podzol", "minecraft:mycelium")
INGRESS_LIMIT = 2048
PENDING_LIMIT = 512
READY_LIMIT = 1024
DRAIN_PER_TICK = 64
JOBS_PER_TICK = 2
RETRY_TICKS = 10
MAX_ATTEMPTS = 60
LIFETIME_TICKS = 1800


class WaterMarkerCleanup(object):
    def __init__(self, dimension, surface_y=62):
        self.dimension = int(dimension)
        # Current NetEase overworld generator's observed water surface. Do
        # not infer an arbitrary height by scanning or creating chunk tickets.
        self.surface_y = int(surface_y)
        self._incoming = deque(maxlen=INGRESS_LIMIT)
        self._pending = {}
        self._order = deque()
        self._ready = OrderedDict()
        self._closed = False
        self.counters = {}

    def _count(self, name):
        self.counters[name] = self.counters.get(name, 0) + 1

    @staticmethod
    def _integer(value):
        number = int(value)
        if isinstance(value, bool) or isinstance(value, float) and value != number:
            raise ValueError("Non-integral coordinate")
        return number

    def record_event(self, args, tick):
        if self._closed or not isinstance(args, dict):
            return
        if args.get("structureName") != NOOP or args.get("cancel"):
            return
        try:
            dimension = self._integer(args.get("dimensionId", -1))
            pos = tuple(self._integer(args[axis]) for axis in ("x", "y", "z"))
            if dimension != self.dimension or pos[1] != self.surface_y:
                return
            if abs(pos[0]) > 30000000 or abs(pos[2]) > 30000000 or not 1 <= pos[1] <= 254:
                return
        except (KeyError, TypeError, ValueError, OverflowError):
            return
        self._incoming.append(("marker", pos))

    def observe_loaded(self, args):
        if self._closed or not isinstance(args, dict):
            return
        try:
            dimension = self._integer(args.get("dimension", args.get("dimensionId", -1)))
            chunk = (self._integer(args["chunkPosX"]), self._integer(args["chunkPosZ"]))
            if dimension != self.dimension or max(abs(v) for v in chunk) > 1875000:
                return
        except (KeyError, TypeError, ValueError, OverflowError):
            return
        self._incoming.append(("loaded", chunk))

    def close(self):
        self._closed = True
        self._incoming.clear()
        self._pending.clear()
        self._order.clear()
        self._ready.clear()

    def has_work(self):
        return bool(self._incoming or self._pending)

    def _drain(self, tick):
        for _ in range(min(DRAIN_PER_TICK, len(self._incoming))):
            kind, key = self._incoming.popleft()
            if kind == "loaded":
                self._ready.pop(key, None)
                self._ready[key] = True
                if len(self._ready) > READY_LIMIT:
                    self._ready.popitem(last=False)
            elif key not in self._pending:
                if len(self._pending) >= PENDING_LIMIT:
                    self._count("queueFull")
                    continue
                self._pending[key] = {"due": tick + 2, "expires": tick + LIFETIME_TICKS,
                                      "attempts": 0, "verify": False}
                self._order.append(key)
                self._count("queued")

    @staticmethod
    def _source_water(block):
        return (isinstance(block, dict) and block.get("name") in WATER
                and block.get("aux") in (0, "0"))

    def _inspect(self, pos, job, ready, read, write):
        x, y, z = pos
        if (x // 16, z // 16) not in self._ready:
            return "retry"
        neighbors = [(x - 1, y, z), (x + 1, y, z), (x, y, z - 1), (x, y, z + 1)]
        points = [pos] if job["verify"] else [pos, (x, y + 1, z)] + neighbors + [(x, y - 1, z)]
        checked = set()
        for point in points:
            chunk = (point[0] // 16, point[2] // 16)
            if chunk not in checked:
                if not ready(point, self.dimension):
                    self._count("unloaded")
                    return "retry"
                checked.add(chunk)
        current = read(pos, self.dimension)
        if not isinstance(current, dict):
            return "retry"
        if job["verify"]:
            if current.get("name") in WATER:
                self._count("waterObserved")
            elif current.get("name") == VOID:
                job["verify"] = False
                self._count("writeNotApplied")
                return "retry"
            else:
                self._count("unfilledOrChanged")
            return "done"
        if current.get("name") != VOID:
            self._count("notMarker")
            return "done"
        others = [read(point, self.dimension) for point in points[1:]]
        if any(not isinstance(block, dict) for block in others):
            return "retry"
        above, below = others[0], others[-1]
        if (above.get("name") != AIR or below.get("name") not in SUPPORT
                or sum(self._source_water(block) for block in others[1:5]) < 3):
            self._count("notWaterSurface")
            return "done"
        # Do not erase a player/other system's replacement made since capture.
        current = read(pos, self.dimension)
        if not isinstance(current, dict):
            return "retry"
        if current.get("name") != VOID:
            self._count("changedBeforeWrite")
            return "done"
        self._write_used = True
        self._count("writeAttempts")
        result = write(pos, self.dimension)
        if result is False:
            return "retry"
        self._count("cleared")
        job["verify"] = True
        return "cleared"

    def tick(self, tick, paused, ready, read, write):
        if paused or self._closed:
            return 0
        self._drain(tick)
        writes = 0
        self._write_used = False
        for _ in range(min(JOBS_PER_TICK, len(self._order))):
            pos = self._order.popleft()
            job = self._pending[pos]
            if tick > job["expires"] or job["attempts"] >= MAX_ATTEMPTS:
                del self._pending[pos]
                self._count("expired")
                continue
            if tick < job["due"]:
                self._order.append(pos)
                continue
            job["attempts"] += 1
            try:
                outcome = self._inspect(pos, job, ready, read, write)
            except Exception:
                self._count("apiError")
                outcome = "retry"
            if outcome == "done":
                del self._pending[pos]
            else:
                job["due"] = tick + RETRY_TICKS
                self._order.append(pos)
            if outcome == "cleared":
                writes += 1
            if self._write_used:
                # Bound attempts too, including SDK exceptions/False results.
                break
        return writes
