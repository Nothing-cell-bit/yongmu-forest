# -*- coding: utf-8 -*-
"""World-owned login checkpoints, independent of portal return addresses."""
import math
import uuid

from TwilightBossSlice import portal_logic


EXTRA_KEY = "tf_slice:twilight_sessions_v1"
SAVE_INTERVAL_TICKS = 100
RESUME_TIMEOUT_SECONDS = 120.0


def clean_position(value):
    try:
        if not isinstance(value, (tuple, list)) or len(value) != 3:
            return None
        position = tuple(float(v) for v in value)
        if any(math.isnan(v) or math.isinf(v) for v in position):
            return None
        if abs(position[0]) > 30000000 or abs(position[2]) > 30000000:
            return None
        if abs(position[1]) > 4096:
            return None
        return position
    except (TypeError, ValueError, OverflowError):
        return None


class TwilightSession(object):
    def __init__(self, host, dimension_id):
        self.host = host
        self.dimension_id = dimension_id
        self.records = {}
        self.ready = set()
        self.suspended = set()
        self.pending = {}
        self.dirty = False
        self.load_ok = False
        try:
            payload = host._portal_extra.GetExtraData(EXTRA_KEY)
            self.load_ok = True
            if isinstance(payload, dict):
                for player, record in payload.items():
                    position = clean_position(record.get("pos")) if isinstance(record, dict) else None
                    if position is not None:
                        self.records[str(player)] = position
        except Exception as error:
            self.trace("load_failed", error=str(error))

    def trace(self, event, **fields):
        self.host._entry_trace("session." + event, **fields)
        if event in ("load_failed", "save_failed", "resume_cancelled"):
            print("[TwilightBossSlice] session %s: %s" % (event, fields))

    def has_record(self, player):
        return str(player) in self.records

    def flush(self):
        if not self.dirty or not self.load_ok:
            return False
        try:
            payload = dict((player, {"pos": list(pos)}) for player, pos in self.records.items())
            extra = self.host._portal_extra
            if not extra.SetExtraData(EXTRA_KEY, payload, False):
                raise ValueError("SetExtraData rejected session checkpoint")
            if not extra.SaveExtraData():
                raise ValueError("SaveExtraData rejected session checkpoint")
            self.dirty = False
            return True
        except Exception as error:
            self.trace("save_failed", error=str(error))
            return False

    def clear(self, player):
        if self.records.pop(str(player), None) is not None:
            self.dirty = True
            self.flush()

    def capture(self, player):
        if (player not in self.ready or player in self.suspended
                or player in self.pending
                or player in self.host._pending_portal_entries
                or player in self.host._dimension_change_in_progress):
            return
        # Outside positions never overwrite an unresolved login checkpoint.
        if self.host._get_dimension(player) != self.dimension_id:
            return
        position = clean_position(self.host._get_foot_pos(player))
        if position is not None and self.records.get(str(player)) != position:
            self.records[str(player)] = position
            self.dirty = True

    def on_ready(self, player):
        if player in self.ready:
            return
        self.ready.add(player)
        position = self.records.get(str(player))
        current = self.host._get_dimension(player)
        if current == self.dimension_id:
            self.host._portal_cooldowns[player] = self.host._tick + 100
            self.capture(player)
            if position is not None:
                self.host.NotifyToClient(player, "PortalArrivalFinished", {"reused": True})
            return
        if position is None:
            return
        if current != 0:
            # Only the reported overworld login fallback is eligible. Respect
            # legitimate spawns in other dimensions and an unreadable actor.
            self.suspended.add(player)
            return
        if player in self.host._pending_portal_entries:
            self.suspended.add(player)
            return
        request = {"position": position, "token": uuid.uuid4().hex,
                   "state": "changing", "deadline": self.host._portal_now_seconds() + RESUME_TIMEOUT_SECONDS}
        self.pending[player] = request
        self.host._portal_cooldowns[player] = self.host._tick + 100
        self.trace("resume_begin", playerId=player, position=position)
        # Native player tickets load the target. No world query, area ticket,
        # portal construction, or follow-up SetPos is needed at this location.
        result = self.host._change_dimension(
            player, self.dimension_id, portal_logic.player_position_from_foot(position))
        if result is not True:
            self.cancel(player, "native_change_rejected")

    def dimension_start(self, args):
        player = args.get("playerId")
        if player in self.pending and args.get("toDimensionId") == self.dimension_id:
            return True
        if args.get("fromDimensionId") == self.dimension_id and args.get("toDimensionId") != self.dimension_id:
            self.pending.pop(player, None)
            self.clear(player)
        return False

    def dimension_finish(self, args):
        player = args.get("playerId")
        request = self.pending.get(player)
        if request is None:
            return False
        if args.get("toDimensionId") != self.dimension_id:
            self.cancel(player, "unexpected_dimension")
            return True
        request["state"] = "client_ready"
        request["retryTick"] = self.host._tick + 80
        self.send_prepared(player, request)
        return True

    def send_prepared(self, player, request):
        self.host.NotifyToClient(player, "PortalArrivalPrepared", {
            "position": request["position"], "token": request["token"]})

    def acknowledge(self, args):
        player = args.get("__id__")
        request = self.pending.get(player)
        if request is None:
            return False
        if (request["state"] != "client_ready" or args.get("token") != request["token"]
                or self.host._get_dimension(player) != self.dimension_id):
            return True
        self.pending.pop(player, None)
        self.host._portal_cooldowns[player] = self.host._tick + 100
        self.host.NotifyToClient(player, "PortalArrivalFinished", {"cancelled": False, "resumed": True})
        self.trace("resume_ready", playerId=player, position=request["position"])
        return True

    def cancel(self, player, reason):
        self.pending.pop(player, None)
        self.suspended.add(player)
        self.host.NotifyToClient(player, "PortalArrivalFinished", {"cancelled": True})
        self.trace("resume_cancelled", playerId=player, reason=reason)

    def died(self, player):
        if player in self.pending:
            self.cancel(player, "player_died")
        self.suspended.add(player)
        self.clear(player)

    def leave(self, player):
        # The actor may already be missing or in a native fallback dimension.
        # Use the most recent server-tick snapshot, never a teardown query.
        self.flush()
        self.ready.discard(player)
        self.suspended.discard(player)
        self.pending.pop(player, None)

    def tick(self):
        for player, request in list(self.pending.items()):
            if self.host._portal_now_seconds() >= request["deadline"]:
                self.cancel(player, "confirmation_timeout")
            elif request["state"] == "client_ready" and self.host._tick >= request["retryTick"]:
                request["retryTick"] = self.host._tick + 80
                self.send_prepared(player, request)
        for player in list(self.ready):
            self.capture(player)
        if self.host._tick % SAVE_INTERVAL_TICKS == 0:
            self.flush()
