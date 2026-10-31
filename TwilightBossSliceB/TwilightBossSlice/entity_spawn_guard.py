# -*- coding: utf-8 -*-
"""Chunk-safe transient entity creation; no chunk loading or persistent state."""
import math

RETRY_TICKS = 10
MAX_FAILED_POSITIONS = 128


class SpawnGate(object):
    def __init__(self):
        self.retry_after = {}

    @staticmethod
    def _note(record, name):
        if callable(record):
            record(name)

    def create(self, tick, arguments, checker, creator, record=None):
        try:
            identifier, position, rotation, dimension, npc, global_entity = arguments
            block_position = tuple(int(math.floor(float(v))) for v in position)
            if len(block_position) != 3:
                raise ValueError('invalid position')
            dimension = int(dimension)
            key = (str(identifier), dimension) + block_position
        except (TypeError, ValueError, OverflowError):
            self._note(record, 'entitySpawnInvalidRequest')
            return None
        if self.retry_after.get(key, -1) > tick:
            self._note(record, 'entitySpawnDeferredRetry')
            return None
        self.retry_after.pop(key, None)
        try:
            if not callable(checker):
                raise AttributeError('chunk state API unavailable')
            ready = checker(dimension, block_position)
        except Exception:
            self._note(record, 'entitySpawnReadinessError')
            return None
        if not ready:
            self._note(record, 'entitySpawnDeferredUnloaded')
            return None
        try:
            entity_id = creator(*arguments)
        except Exception:
            entity_id = None
        if entity_id in (None, '', -1, '-1', False):
            if len(self.retry_after) >= MAX_FAILED_POSITIONS:
                oldest = min(self.retry_after, key=self.retry_after.get)
                self.retry_after.pop(oldest, None)
            self.retry_after[key] = tick + RETRY_TICKS
            self._note(record, 'entitySpawnNativeFailed')
            return None
        self._note(record, 'entitySpawnNativeSucceeded')
        return entity_id
