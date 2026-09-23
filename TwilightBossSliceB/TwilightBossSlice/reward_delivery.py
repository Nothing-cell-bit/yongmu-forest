# -*- coding: utf-8 -*-
"""Persisted reward retries; engine effects stay behind injected callbacks.

The engine has no transaction spanning world effects and ExtraData. A native
crash between an effect and its checkpoint remains an unavoidable narrow gap.
Ordinary False returns, exceptions, reloads after checkpoints, and duplicate
death callbacks do not discard or repeat acknowledged rewards.
"""
import copy
import math


def item(name, count):
    return {"newItemName": name, "newAuxValue": 0, "count": int(count)}


def _bonus(level, rng):
    return int(math.floor(rng.uniform(0.0, 1.0) * max(0, int(level)) + 0.5))


def bonus_items(kind, level, rng):
    pools = {
        "naga": (("tf_slice:naga_scale", 1),),
        "lich": (("minecraft:ender_pearl", 1), ("minecraft:bone", 1)),
        "ur_ghast": (("tf_slice:carminite", 4), ("tf_slice:fiery_tears", 2)),
    }
    result = []
    for name, rolls in pools[kind]:
        count = sum(_bonus(level, rng) for _ in range(rolls))
        if count > 0:
            result.append(item(name, count))
    return result


def minoshroom_items(level, rng):
    count = sum(1 + _bonus(level, rng) for _ in range(rng.randint(2, 5)))
    return ([item("tf_slice:meef_stroganoff", 1) for _ in range(count)] +
            [item("tf_slice:minoshroom_trophy_item", 1),
             item("tf_slice:diamond_minotaur_axe", 1)])


class RewardDelivery(object):
    def __init__(self, saved, save, chest, spawn, put=None):
        self.records = copy.deepcopy(saved) if isinstance(saved, dict) else {}
        self._save = save
        self._chest = chest
        self._spawn = spawn
        self._put = put
        self._dirty = False
        self._cursor = 0

    def _checkpoint(self):
        try:
            if self._save(copy.deepcopy(self.records)) is False:
                return False
        except Exception:
            return False
        self._dirty = False
        return True

    def submit(self, key, dimension, position, table, items, container_items=False):
        if key not in self.records:
            self.records[key] = {
                "dimension": int(dimension), "position": list(position),
                "table": table, "items": copy.deepcopy(items),
                "chestDone": table is None, "nextItem": 0,
                "complete": False,
                "containerItems": bool(container_items),
            }
            self._dirty = True
        return not self._dirty or self._checkpoint()

    def flush(self, limit=8):
        if self._dirty and not self._checkpoint():
            return
        attempts = 0
        keys = sorted(key for key in self.records if not self.records[key]["complete"])
        if not keys:
            return
        start = self._cursor % len(keys)
        for index in range(len(keys)):
            if attempts >= limit:
                return
            offset = (start + index) % len(keys)
            key = keys[offset]
            self._cursor = (offset + 1) % len(keys)
            record = self.records[key]
            pos = tuple(record["position"])
            dimension = record["dimension"]
            if not record["chestDone"]:
                if attempts >= limit:
                    return
                attempts += 1
                try:
                    ok = self._chest(pos, dimension, record["table"])
                except Exception:
                    ok = False
                if not ok:
                    continue
                record["chestDone"] = True
                self._dirty = True
                if not self._checkpoint():
                    return
            while record["nextItem"] < len(record["items"]):
                if attempts >= limit:
                    return
                attempts += 1
                entry = record["items"][record["nextItem"]]
                drop_pos = (pos[0] + 0.5, pos[1] + 0.8, pos[2] + 0.5)
                try:
                    if record.get("containerItems") and record["nextItem"] < 27:
                        result = self._put(
                            copy.deepcopy(entry), dimension, pos, record["nextItem"],
                        )
                    else:
                        # Preserve overflow from command-created Looting levels.
                        result = self._spawn(copy.deepcopy(entry), dimension, drop_pos)
                except Exception:
                    result = None
                if result in (None, False, "", "-1", -1):
                    break
                record["nextItem"] += 1
                self._dirty = True
                if not self._checkpoint():
                    return
            if record["nextItem"] == len(record["items"]):
                record["complete"] = True
                # Keep the receipt for duplicate death events; payload is no
                # longer needed after every native effect was acknowledged.
                record["items"] = []
                self._dirty = True
                if not self._checkpoint():
                    return
