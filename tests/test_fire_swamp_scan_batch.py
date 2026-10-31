"""The production discovery entry must retain exact cells and use bounded reads."""
from unittest.mock import patch

from tests import test_portal_arrival_runtime as runtime
from tests.test_portal_arrival_runtime import FACTORY, SERVER
from TwilightBossSlice import device_scan


class Palette:
    def __init__(self, origin, end, blocks):
        self.origin, self.end, self.blocks = origin, end, blocks
        self.lookups = []

    def GetLocalPosListOfBlocks(self, name):
        self.lookups.append(name)
        return [tuple(p[i] - self.origin[i] for i in range(3)) for p, block in self.blocks.items()
                if block == name and all(self.origin[i] <= p[i] <= self.end[i] for i in range(3))]


class PaletteComponent:
    def __init__(self, blocks, fail=False):
        self.blocks, self.fail, self.calls = blocks, fail, []

    def GetBlockPaletteBetweenPos(self, dimension, origin, end, eliminate_air):
        self.calls.append((dimension, origin, end, eliminate_air))
        if self.fail:
            raise RuntimeError('SDK unavailable')
        assert eliminate_air is False  # Preserve requested origin even when air.
        return Palette(origin, end, self.blocks)


def scene():
    fixture = runtime.FireSwampDiscoveryRuntimeTests()
    fixture.setUp()
    fixture.system._tick = 2
    fixture.system._fire_swamp_discovery_queue = [(x, 4) for x in reversed(range(-16, 0))]
    FACTORY.block.terrain_ready = True
    FACTORY.block.blocks[(-16, 78, 4)] = 'tf_slice:smoker'
    FACTORY.block.blocks[(-1, 72, 4)] = 'tf_slice:encased_fire_jet'
    FACTORY.block.blocks[(-2, 71, 4)] = 'tf_slice:smoker'  # Below the old scan range.
    FACTORY.block.blocks[(-5, 75, 5)] = 'tf_slice:fire_jet'  # Unselected column.
    return fixture.system


def test_real_discovery_batches_loaded_columns_and_preserves_negative_coordinates():
    system = scene()
    palette = PaletteComponent(FACTORY.block.blocks)
    with patch.object(FACTORY, 'CreateBlock', return_value=palette, create=True):
        system._discover_fire_swamp_devices()
    assert len(palette.calls) == 1
    positions = {tuple(v['position']) for v in system._fire_swamp_devices.values()}
    assert positions == {(-16, 78, 4), (-1, 72, 4)}
    assert len(FACTORY.block.top_queries) == 16


def test_palette_failure_falls_back_to_same_discovery_results():
    system = scene()
    palette = PaletteComponent(FACTORY.block.blocks, fail=True)
    with patch.object(FACTORY, 'CreateBlock', return_value=palette, create=True):
        system._discover_fire_swamp_devices()
    assert len(palette.calls) == 1
    assert {tuple(v['position']) for v in system._fire_swamp_devices.values()} == {(-16, 78, 4), (-1, 72, 4)}


def test_unready_and_transitioning_worlds_do_not_reach_palette_api():
    for transitioning in (False, True):
        system = scene()
        if transitioning:
            system._dimension_change_in_progress = {'player'}
        else:
            FACTORY.chunk.ready = False
        palette = PaletteComponent(FACTORY.block.blocks)
        with patch.object(FACTORY, 'CreateBlock', return_value=palette, create=True):
            system._discover_fire_swamp_devices()
        assert palette.calls == []
        assert system._fire_swamp_devices == {}


def test_sparse_scan_does_not_discover_extra_cells_in_bounding_box():
    blocks = {(0, 30, 0): 'tf_slice:smoker', (1, 30, 1): 'tf_slice:fire_jet',
              (2, 24, 2): 'tf_slice:encased_smoker'}
    component = PaletteComponent(blocks)
    found = device_scan.scan([(0, 0, 30), (2, 2, 30)], 7, component,
                             lambda p: blocks.get(p, 'minecraft:air'))
    assert found == [((0, 30, 0), 'tf_slice:smoker'), ((2, 24, 2), 'tf_slice:encased_smoker')]
    assert len(component.calls) == 1


def test_cross_chunk_and_large_height_spans_remain_bounded():
    columns = [(-17, 0, 30), (-16, 0, 30), (0, 0, 10), (15, 15, 200)]
    component = PaletteComponent({})
    assert device_scan.scan(columns, 7, component, lambda p: 'minecraft:air') == []
    assert len(component.calls) == 4
    for dimension, start, end, eliminate in component.calls:
        assert dimension == 7 and eliminate is False
        assert start[0] >> 4 == end[0] >> 4
        assert start[2] >> 4 == end[2] >> 4
        volume = 1
        for i in range(3):
            volume *= end[i] - start[i] + 1
        assert volume <= device_scan.MAX_PALETTE_VOLUME


def test_absent_or_empty_palette_preserves_scalar_fallback_and_order():
    class EmptyPaletteComponent:
        def GetBlockPaletteBetweenPos(self, *args):
            return None
    for component in (None, EmptyPaletteComponent()):
        visited = []
        def read(position):
            visited.append(position)
            return 'tf_slice:smoker' if position[1] == 5 else 'minecraft:air'
        assert device_scan.scan([(1, 1, 8)], 7, component, read) == [((1, 5, 1), 'tf_slice:smoker')]
        assert visited == [(1, y, 1) for y in range(8, 1, -1)]
    assert device_scan.scan([], 7, None, lambda p: None) == []
