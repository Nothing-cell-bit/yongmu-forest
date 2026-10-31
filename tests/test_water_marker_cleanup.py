"""World API boundary model; does not pretend to simulate native water flow."""
import pathlib
import sys
import pytest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'TwilightBossSliceB'))
from TwilightBossSlice.water_marker_cleanup import WaterMarkerCleanup

DIM=33027004
POS=(-112,62,224)


class World:
    def __init__(self):
        self.cells={POS:{'name':'minecraft:structure_void','aux':0}}
        x,y,z=POS
        for dx,dz in ((-1,0),(1,0),(0,-1),(0,1)):
            self.cells[(x+dx,y,z+dz)]={'name':'minecraft:water','aux':0}
        self.cells[(x,y-1,z)]={'name':'minecraft:dirt','aux':0}
        self.reads=[];self.writes=[];self.unready=set()

    def ready(self,pos,dim):
        assert dim==DIM
        return (pos[0]//16,pos[2]//16) not in self.unready

    def read(self,pos,dim):
        assert self.ready(pos,dim),'Read touched an unloaded neighbor'
        self.reads.append(pos)
        return self.cells.get(pos,{'name':'minecraft:air','aux':0})

    def clear(self,pos,dim):
        assert dim==DIM
        self.writes.append(pos)
        self.cells[pos]={'name':'minecraft:air','aux':0}
        return True


def enqueue(cleaner,pos=POS,tick=0):
    cleaner.record_event({'dimensionId':DIM,'structureName':'tf_slice:ruin_landmark_noop',
                          'x':pos[0],'y':pos[1],'z':pos[2]},tick)
    cleaner.observe_loaded({'dimension':DIM,'chunkPosX':pos[0]//16,'chunkPosZ':pos[2]//16})


def advance(cleaner,world,start=1,end=40,paused=False):
    for tick in range(start,end):
        cleaner.tick(tick,paused,world.ready,world.read,world.clear)


def test_recorded_loaded_water_marker_is_cleared_once_without_bulk_fill():
    cleaner=WaterMarkerCleanup(DIM);world=World();enqueue(cleaner)
    advance(cleaner,world)
    assert world.writes==[POS]
    assert world.cells[POS]['name']=='minecraft:air'


def test_entry_pause_does_not_touch_world():
    cleaner=WaterMarkerCleanup(DIM);world=World();enqueue(cleaner)
    advance(cleaner,world,end=500,paused=True)
    assert world.reads==world.writes==[]
    advance(cleaner,world,start=500,end=550)
    assert world.writes==[POS]


def test_cross_chunk_neighbors_are_ready_before_any_reads():
    cleaner=WaterMarkerCleanup(DIM);world=World();enqueue(cleaner)
    world.unready.add((-8,14))
    advance(cleaner,world)
    assert world.reads==world.writes==[]
    world.unready.clear()
    advance(cleaner,world,start=40,end=80)
    assert world.writes==[POS]


def test_loaded_notification_can_arrive_after_marker():
    cleaner=WaterMarkerCleanup(DIM);world=World()
    cleaner.record_event({'dimensionId':DIM,'structureName':'tf_slice:ruin_landmark_noop','x':-112,'y':62,'z':224},0)
    advance(cleaner,world)
    assert world.reads==world.writes==[]
    cleaner.observe_loaded({'dimensionId':DIM,'chunkPosX':-7,'chunkPosZ':14})
    advance(cleaner,world,start=40,end=80)
    assert world.writes==[POS]


@pytest.mark.parametrize('change', ['player_block','above_block','no_support','two_sources','flowing'])
def test_uncertain_or_changed_cells_are_not_cleared(change):
    cleaner=WaterMarkerCleanup(DIM);world=World();enqueue(cleaner)
    x,y,z=POS
    if change=='player_block':world.cells[POS]={'name':'minecraft:stone','aux':0}
    if change=='above_block':world.cells[(x,y+1,z)]={'name':'minecraft:stone','aux':0}
    if change=='no_support':world.cells[(x,y-1,z)]={'name':'minecraft:air','aux':0}
    if change=='two_sources':
        for dx in (-1,1):world.cells[(x+dx,y,z)]={'name':'minecraft:air','aux':0}
    if change=='flowing':
        for dx,dz in ((-1,0),(1,0),(0,-1),(0,1)):world.cells[(x+dx,y,z+dz)]['aux']=3
    advance(cleaner,world)
    assert world.writes==[]


def test_event_snapshot_deduplicates_and_ignores_unowned_records():
    cleaner=WaterMarkerCleanup(DIM);world=World()
    args={'dimensionId':DIM,'structureName':'tf_slice:ruin_landmark_noop','x':-112,'y':62,'z':224}
    for _ in range(20):cleaner.record_event(args,0)
    args['x']=1000
    for update in ({'dimensionId':0},{'cancel':True},{'structureName':'tf_slice:real_building'},
                   {'y':63},{'x':float('nan')},{'x':.5},{'x':True},{'x':30000001}):
        bad=dict(args);bad.update(update);cleaner.record_event(bad,0)
    cleaner.observe_loaded({'dimension':DIM,'chunkPosX':-7,'chunkPosZ':14})
    advance(cleaner,world)
    assert world.writes==[POS]
    assert cleaner.counters['queued']==1


def test_native_water_recovery_is_observed_but_never_faked():
    cleaner=WaterMarkerCleanup(DIM);world=World();enqueue(cleaner)
    advance(cleaner,world,end=5)
    assert world.cells[POS]['name']=='minecraft:air'
    # This simulates a later SDK read result only, not water physics.
    world.cells[POS]={'name':'minecraft:water','aux':0}
    advance(cleaner,world,start=5,end=30)
    assert cleaner.counters['waterObserved']==1
    assert world.writes==[POS]


def test_player_replacement_during_inspection_is_preserved():
    cleaner=WaterMarkerCleanup(DIM);world=World();enqueue(cleaner)
    calls=[0]
    def read(pos,dim):
        if pos==POS:
            calls[0]+=1
            if calls[0]==2:world.cells[POS]={'name':'minecraft:stone','aux':0}
        return world.read(pos,dim)
    for t in range(1,40):cleaner.tick(t,False,world.ready,read,world.clear)
    assert world.writes==[]


def test_failed_sdk_calls_have_finite_retry_and_per_tick_attempt_budget():
    cleaner=WaterMarkerCleanup(DIM);world=World();enqueue(cleaner)
    attempts=[]
    def fail(pos,dim):attempts.append(pos);raise RuntimeError('SDK unavailable')
    for t in range(1,1000):
        before=len(attempts);cleaner.tick(t,False,world.ready,world.read,fail)
        assert len(attempts)-before<=1
    assert len(attempts)<=60 and not cleaner.has_work()


def test_false_write_and_unreadable_block_retry_without_forcing_water():
    cleaner=WaterMarkerCleanup(DIM);world=World();enqueue(cleaner)
    for t in range(1,20):cleaner.tick(t,False,world.ready,lambda p,d:None,world.clear)
    assert world.writes==[]
    for t in range(20,40):cleaner.tick(t,False,world.ready,world.read,lambda p,d:False)
    assert world.writes==[]
    advance(cleaner,world,start=40,end=80)
    assert world.writes==[POS]
    assert world.cells[POS]['name']=='minecraft:air'


def test_memory_and_world_work_are_bounded_and_close_discards_work():
    from TwilightBossSlice.water_marker_cleanup import INGRESS_LIMIT,PENDING_LIMIT
    cleaner=WaterMarkerCleanup(DIM);world=World()
    for x in range(5000):enqueue(cleaner,(x,62,0))
    assert len(cleaner._incoming)<=INGRESS_LIMIT
    for t in range(1,100):
        reads=len(world.reads);writes=len(world.writes)
        cleaner.tick(t,False,world.ready,world.read,world.clear)
        assert len(world.reads)-reads<=16
        assert len(world.writes)-writes<=1
        assert len(cleaner._pending)<=PENDING_LIMIT
    cleaner.close();enqueue(cleaner)
    before=len(world.reads);advance(cleaner,world)
    assert len(world.reads)==before and not cleaner.has_work()
