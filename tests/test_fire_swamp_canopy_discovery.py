"""The ground jet below a tree canopy must reach the production device registry."""
from unittest.mock import patch

from tests.test_fire_swamp_scan_batch import scene, PaletteComponent, FACTORY


def test_ground_fire_jet_is_found_when_highest_block_is_tree_canopy():
    system = scene()
    system._fire_swamp_discovery_queue = [(-1, 4)]
    system._fire_swamp_discovery_height_bands = {(-1, 4): {33}}
    system._get_top_block_height = lambda *args: 100
    FACTORY.block.blocks[(-1, 32, 4)] = 'tf_slice:fire_jet'
    palette = PaletteComponent(FACTORY.block.blocks)
    with patch.object(FACTORY, 'CreateBlock', return_value=palette, create=True):
        system._discover_fire_swamp_devices()
    positions = {tuple(s['position']) for s in system._fire_swamp_devices.values()}
    assert (-1, 32, 4) in positions
    assert len(palette.calls) == 1
    assert palette.calls[0][1][1] <= 32 <= palette.calls[0][2][1]
    assert palette.calls[0][2][1] - palette.calls[0][1][1] == 6


def test_queue_captures_nearby_player_height_without_extra_native_reads():
    system = scene()
    system._fire_swamp_discovery_queue = []
    system._fire_swamp_discovery_height_bands = {}
    system._tick = 200
    system._get_online_players = lambda: ['player']
    system._get_dimension = lambda _: 33027004
    system._get_foot_pos = lambda _: (-0.2, 33.8, 4.2)
    system._fire_swamp_discovery_ready_ticks = {'player': 1}
    system._queue_fire_swamp_discovery_columns()
    assert system._fire_swamp_discovery_height_bands[(-1, 4)] == {33}
