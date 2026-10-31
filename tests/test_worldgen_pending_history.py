"""Idle worldgen cost must depend on pending work, not completed exploration."""
import copy

import pytest

from tests.test_mushroom_worldgen_service import FakeFactory
from TwilightBossSlice import mushroomWorldgenService as mushrooms
from TwilightBossSlice import enchantedTreeWorldgenService as trees


class ObservedJob(dict):
    state_reads = 0

    def get(self, key, *args):
        if key == 'state':
            type(self).state_reads += 1
        return super(ObservedJob, self).get(key, *args)


@pytest.mark.parametrize('module,service_class', [
    (mushrooms, mushrooms.MushroomWorldgenService),
    (trees, trees.EnchantedTreeWorldgenService),
])
def test_idle_ticks_do_not_rescan_terminal_history(module, service_class):
    factory = FakeFactory()
    history = {str(i): ObservedJob(state=('complete', 'skipped', 'failed')[i % 3], sequence=i)
               for i in range(4096)}
    factory.extra.values[module.LEDGER_KEY] = history
    service = service_class(factory, 'level', 7)
    before = copy.deepcopy(factory.extra.values[module.LEDGER_KEY])
    ObservedJob.state_reads = 0
    for tick in range(40):
        service.tick(tick, [{'dimensionId': 7, 'position': (100, 70, 200)}])
    assert ObservedJob.state_reads == 0
    assert factory.extra.values[module.LEDGER_KEY] == before
    assert factory.game.placements == []
    assert factory.chunk.checks == []


@pytest.mark.parametrize('module,service_class', [
    (mushrooms, mushrooms.MushroomWorldgenService),
    (trees, trees.EnchantedTreeWorldgenService),
])
def test_reload_pending_work_waits_for_chunks_and_remains_eligible(module, service_class):
    factory = FakeFactory()
    factory.chunk.ready = False
    factory.extra.values[module.LEDGER_KEY] = {
        'terminal': ObservedJob(state='complete', sequence=1),
        'pending': {'state': 'placing', 'sequence': 2, 'rootX': 100, 'rootZ': 200, 'eventY': 65,
                    'kind': 'brown' if module is mushrooms else 'regular_rainbow', 'variant': 0},
    }
    service = service_class(factory, 'level', 7)
    ObservedJob.state_reads = 0
    for tick in range(3):
        service.tick(tick, [{'dimensionId': 7, 'position': (100, 70, 200)}])
    assert service._ledger['pending']['state'] == 'planned'
    assert len(factory.chunk.checks) == 3
    assert ObservedJob.state_reads == 0
    assert factory.game.placements == []


@pytest.mark.parametrize('module,service_class', [
    (mushrooms, mushrooms.MushroomWorldgenService),
    (trees, trees.EnchantedTreeWorldgenService),
])
def test_handoff_is_schedulable_even_when_disk_save_fails_and_terminal_is_not_retried(module, service_class):
    factory = FakeFactory()
    factory.extra.SaveExtraData = lambda: False  # SDK storage boundary only.
    factory.chunk.ready = False
    service = service_class(factory, 'level', 7)
    logic = mushrooms.mushroom_logic if module is mushrooms else trees.tree_logic
    kind = 'brown' if module is mushrooms else 'regular_rainbow'
    event = {'structureName': logic.TRIGGER_STRUCTURES[kind], 'dimensionId': 7,
             'x': 100, 'y': 65, 'z': 200}
    player = {'dimensionId': 7, 'position': (100, 70, 200)}
    service.on_structure_feature_event(dict(event))
    service.tick(1, [player])
    service.tick(2, [player])
    assert len(factory.chunk.checks) == 2
    assert len(service._ledger) == 1
    factory.chunk.ready = True
    factory.biome.name = 'minecraft:desert'
    service.tick(3, [player])
    assert list(service._ledger.values())[0]['state'] == 'skipped'
    count = len(factory.chunk.checks)
    for tick in range(4, 12):
        service.on_structure_feature_event(dict(event))
        service.tick(tick, [player])
    assert len(factory.chunk.checks) == count
    assert len(service._ledger) == 1
    assert factory.game.placements == []


@pytest.mark.parametrize('module,service_class', [
    (mushrooms, mushrooms.MushroomWorldgenService),
    (trees, trees.EnchantedTreeWorldgenService),
])
@pytest.mark.parametrize('fail_placement', [False, True])
def test_completion_and_retry_exhaustion_leave_no_pending_work_after_reload(module, service_class, fail_placement):
    factory = FakeFactory()
    logic = mushrooms.mushroom_logic if module is mushrooms else trees.tree_logic
    kind = 'brown' if module is mushrooms else 'regular_rainbow'
    factory.biome.name = 'dm33027004_mushroom_island' if module is mushrooms else logic.ENCHANTED_BIOME
    factory.block.top_y = 64
    factory.block.blocks[(100, 64, 200)] = {'name': 'minecraft:grass_block', 'aux': 0}
    calls = []
    if fail_placement:
        def fail(*args):
            calls.append(args)
            raise RuntimeError('SDK placement failed')
        factory.game.PlaceStructure = fail
    service = service_class(factory, 'level', 7)
    service.on_structure_feature_event({'structureName': logic.TRIGGER_STRUCTURES[kind],
                                       'dimensionId': 7, 'x': 100, 'y': 65, 'z': 200})
    player = {'dimensionId': 7, 'position': (100, 70, 200)}
    for tick in range(40):
        service.tick(tick, [player])
    job = list(service._ledger.values())[0]
    assert job['state'] == ('failed' if fail_placement else 'complete')
    if fail_placement:
        assert len(calls) == mushrooms.MAX_RETRIES
    else:
        assert len(factory.game.placements) == len(service._catalog[kind][job['variant']]['pieces'])
    assert factory.extra.values[module.LEDGER_KEY] == service._ledger
    assert service._pending_jobs == []
    reloaded = service_class(factory, 'level', 7)
    before = len(factory.chunk.checks)
    for tick in range(40, 50):
        reloaded.tick(tick, [player])
    assert len(factory.chunk.checks) == before
    assert reloaded._pending_jobs == []


@pytest.mark.parametrize('module,service_class', [
    (mushrooms, mushrooms.MushroomWorldgenService),
    (trees, trees.EnchantedTreeWorldgenService),
])
def test_pruning_terminal_history_keeps_new_work_and_failed_save_keeps_index(module, service_class):
    factory = FakeFactory()
    factory.chunk.ready = False
    factory.extra.values[module.LEDGER_KEY] = {
        str(i): {'state': 'complete', 'sequence': i} for i in range(4096)
    }
    service = service_class(factory, 'level', 7)
    def broken_save():
        raise OSError('storage unavailable')
    factory.extra.SaveExtraData = broken_save
    logic = mushrooms.mushroom_logic if module is mushrooms else trees.tree_logic
    kind = 'brown' if module is mushrooms else 'regular_rainbow'
    service.on_structure_feature_event({'structureName': logic.TRIGGER_STRUCTURES[kind],
                                       'dimensionId': 7, 'x': 100, 'y': 65, 'z': 200})
    player = {'dimensionId': 7, 'position': (100, 70, 200)}
    service.tick(1, [player])
    assert len(service._ledger) == 4096
    assert '0' not in service._ledger
    assert len(service._pending_jobs) == 1
    assert service._pending_jobs[0][1]['state'] == 'planned'
    service.tick(2, [player])
    assert len(factory.chunk.checks) == 2
