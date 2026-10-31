# -*- coding: utf-8 -*-
"""Bounded read-only device discovery over already validated loaded columns."""
from TwilightBossSlice.fire_swamp_logic import DEVICE_BLOCKS

MAX_PALETTE_VOLUME = 4096


def _bounds(columns):
    start = (min(c[0] for c in columns), min(c[2] for c in columns) - 6,
             min(c[1] for c in columns))
    end = (max(c[0] for c in columns), max(c[2] for c in columns),
           max(c[1] for c in columns))
    return start, end


def _positions(columns):
    for x, z, top in columns:
        for y in range(top, top - 7, -1):
            yield (x, y, z)


def scan(columns, dimension_id, component, scalar_read):
    """Preserve discovery order and range, with the existing scalar fallback."""
    if not columns:
        return []
    groups = {}
    for column in columns:
        groups.setdefault((column[0] >> 4, column[1] >> 4), []).append(column)
    found = {}
    reader = getattr(component, 'GetBlockPaletteBetweenPos', None)
    for group in groups.values():
        start, end = _bounds(group)
        volume = (end[0] - start[0] + 1) * (end[1] - start[1] + 1) * (end[2] - start[2] + 1)
        batches = [group] if volume <= MAX_PALETTE_VOLUME else [[column] for column in group]
        for batch in batches:
            start, end = _bounds(batch)
            selected = set(_positions(batch))
            try:
                if not callable(reader):
                    raise AttributeError('block palette unavailable')
                # Keep air so palette local coordinates retain the requested
                # origin. Each request stays inside one checked chunk.
                palette = reader(dimension_id, start, end, False)
                values = {}
                for name in DEVICE_BLOCKS:
                    for local in palette.GetLocalPosListOfBlocks(name):
                        position = tuple(start[i] + int(local[i]) for i in range(3))
                        if position in selected:
                            values[position] = name
                found.update(values)
            except Exception:
                # Missing/failed API must not be mistaken for an empty scan.
                for position in _positions(batch):
                    name = scalar_read(position)
                    if name in DEVICE_BLOCKS:
                        found[position] = name
    return [(position, found[position]) for position in _positions(columns) if position in found]
