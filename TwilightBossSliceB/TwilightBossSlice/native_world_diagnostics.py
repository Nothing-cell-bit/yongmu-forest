# -*- coding: utf-8 -*-
"""Bounded, opt-in breadcrumbs; optional main-thread development log output."""
from collections import deque
import json
import time

ENABLED = False
OUTPUT_DIRECTORY = ""
BUILD = "world-diag-G-20261020"
PREFIX = "[TF_WORLD_DIAG] "
DURATION_SECONDS = 180.0
QUEUE_LIMIT = 512
EVENT_LIMIT = 8192
BATCH_LIMIT = 32
FLUSH_SECONDS = 0.5
FIELDS = ("structureName", "featureName", "identifier", "dimensionId",
          "dimension", "x", "y", "z", "chunkPosX", "chunkPosZ", "cancel",
          "name", "aux", "position", "pair", "result", "error")


def _value(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_value(v) if not isinstance(v, (list, tuple, dict)) else None
                for v in value[:3]]
    try:
        return str(value)[:160]
    except Exception:
        return "<unprintable>"


class NativeWorldDiagnostics(object):
    def __init__(self, dimension, enabled=None, clock=None):
        self.enabled = ENABLED if enabled is None else bool(enabled)
        self.dimension = dimension
        self.clock = clock or time.time
        self.queue = deque(maxlen=QUEUE_LIMIT)
        self.started = None
        self.last_flush = None
        self.sequence = 0
        self.dropped = 0
        self.closed = False
        self.reason = None
        self.announced = False
        self.finished = False

    def record(self, kind, args, tick):
        # Worker callbacks only enqueue scalar snapshots. Never call world APIs.
        if not self.enabled or self.closed or not isinstance(args, dict):
            return None
        if args.get("dimensionId", args.get("dimension")) != self.dimension:
            return None
        now = self.clock()
        if self.started is None:
            self.started = now
        if now - self.started >= DURATION_SECONDS or self.sequence >= EVENT_LIMIT:
            self.stop("time_limit" if now - self.started >= DURATION_SECONDS
                      else "event_limit")
            return None
        self.sequence += 1
        event = {"seq": self.sequence, "at": round(now, 3), "tick": tick,
                 "kind": kind}
        for name in FIELDS:
            if name in args:
                event[name] = _value(args[name])
        if len(self.queue) == QUEUE_LIMIT:
            self.dropped += 1
        self.queue.append(event)
        return event["seq"]

    def stop(self, reason):
        self.closed = True
        if self.reason is None:
            self.reason = reason

    def _emit(self, emit, line):
        # Only the test payload supplies an existing local directory. Worker
        # record() never opens files. Closing each batch flushes Python buffers
        # before the next native call; console routing is not durable evidence.
        if OUTPUT_DIRECTORY:
            path = OUTPUT_DIRECTORY + "/native-world-%d.jsonl" % int(self.started * 1000)
            with open(path, "ab") as handle:
                handle.write((line[len(PREFIX):] + "\n").encode("utf-8"))
        emit(line)

    def flush(self, emit, force=False):
        if not self.enabled or self.finished or self.started is None:
            return
        try:
            now = self.clock()
        except Exception:
            self.stop("clock_error")
            self.queue.clear()
            self.finished = True
            return
        if now - self.started >= DURATION_SECONDS:
            self.stop("time_limit")
        if (not force and self.last_flush is not None
                and now - self.last_flush < FLUSH_SECONDS):
            return
        self.last_flush = now
        try:
            if not self.announced:
                self._emit(emit, PREFIX + json.dumps({"phase": "start", "build": BUILD,
                     "startedAt": self.started, "seconds": DURATION_SECONDS,
                     "eventLimit": EVENT_LIMIT, "queueLimit": QUEUE_LIMIT}))
                self.announced = True
            events = []
            for unused in range(min(BATCH_LIMIT, len(self.queue))):
                events.append(self.queue.popleft())
            if events:
                self._emit(emit, PREFIX + json.dumps({"phase": "events", "build": BUILD,
                     "dropped": self.dropped, "events": events},
                     separators=(",", ":")))
            if self.closed and not self.queue:
                self._emit(emit, PREFIX + json.dumps({"phase": "stop", "build": BUILD,
                     "reason": self.reason, "recorded": self.sequence,
                     "dropped": self.dropped}))
                self.finished = True
        except Exception:
            # Diagnostic failure must not change game behavior or escape Update.
            self.stop("sink_error")
            self.queue.clear()
            self.finished = True

    def close(self, emit):
        self.stop("destroy")
        # Bounded by the fixed queue limit, not by world size.
        for unused in range(QUEUE_LIMIT // BATCH_LIMIT + 1):
            if self.finished:
                break
            self.flush(emit, force=True)

    def checkpoint(self, emit, pair, data, tick):
        # Main-thread write boundary: make the begin record visible even if
        # SetBlockNew blocks inside a native assertion before the next Update.
        if pair is None:
            return
        event = {"seq": pair, "kind": "water.write.begin", "tick": tick}
        event.update({key: _value(value) for key, value in data.items()})
        self._emit(emit, PREFIX + json.dumps({"phase": "checkpoint", "build": BUILD,
                                  "event": event}, separators=(",", ":")))


def record(owner, kind, args):
    try:
        probe = getattr(owner, "_native_world_diag", None)
        if probe is not None:
            return probe.record(kind, args, getattr(owner, "_tick", 0))
    except Exception:
        pass
    return None


def call(owner, kind, position, dimension, function, *args):
    probe = getattr(owner, "_native_world_diag", None)
    if probe is None or not probe.enabled or probe.closed:
        return function(*args)
    data = {"dimensionId": dimension, "position": position}
    pair = record(owner, kind + ".begin", data)
    if kind == "water.write":
        try:
            probe.checkpoint(owner._emit_native_world_diag, pair, data,
                             getattr(owner, "_tick", 0))
        except Exception:
            pass
    try:
        result = function(*args)
    except Exception as error:
        data.update(pair=pair, error=type(error).__name__)
        record(owner, kind + ".error", data)
        raise
    data.update(pair=pair)
    if isinstance(result, dict):
        data.update({k: result[k] for k in ("name", "aux") if k in result})
    else:
        data["result"] = result
    record(owner, kind + ".end", data)
    return result
