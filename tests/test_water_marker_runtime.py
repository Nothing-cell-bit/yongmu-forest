"""Real server dispatch and cleanup entry; only engine API edges are faked."""
from tests.test_portal_arrival_runtime import SERVER
from tests.test_structure_worldgen_handoff import SERVICE, FakeFactory
from tests.test_water_marker_cleanup import DIM,POS,World
from TwilightBossSlice.water_marker_cleanup import WaterMarkerCleanup


def host():
    owner=object.__new__(SERVER.ServerSystem)
    owner._water_marker_cleanup=WaterMarkerCleanup(DIM)
    owner._tick=0
    owner._pending_portal_entries={}
    owner._dimension_change_in_progress=set()
    owner._worldgen_perf_counters={}
    owner._ruin_worldgen=SERVICE.StructureWorldgenService(FakeFactory(),'level',DIM)
    return owner


def event():
    return {'structureName':SERVICE.LANDMARK_TRIGGER_STRUCTURE,'dimensionId':DIM,
            'x':POS[0],'y':POS[1],'z':POS[2],'biomeName':'dm33027004_plains','cancel':False}


def test_actual_structure_dispatch_captures_final_noop_without_world_access():
    owner=host();args=event()
    owner.OnPlaceNeteaseStructureFeatureEvent(args)
    assert args['structureName']=='tf_slice:ruin_landmark_noop' and args['cancel'] is False
    assert owner._water_marker_cleanup.has_work(), 'Native noop was not captured for post-load cleanup'


def test_actual_server_cleanup_uses_loaded_events_and_native_neighbor_updates():
    owner=host();world=World();calls=[]
    class Chunk:
        def CheckChunkState(self,dim,pos):return world.ready(pos,dim)
    class Block:
        def GetBlockNew(self,pos,dim):return world.read(pos,dim)
        def SetBlockNew(self,pos,block,handling,dim,legacy,update):
            calls.append((pos,block,handling,dim,legacy,update))
            return world.clear(pos,dim)
    owner._chunk_comp=Chunk();owner._block_comp=Block()
    owner.OnPlaceNeteaseStructureFeatureEvent(event())
    owner.OnChunkLoadedServerEvent({'dimension':DIM,'chunkPosX':-7,'chunkPosZ':14})
    owner._pending_portal_entries={'player':{'state':'awaiting_client_ready'}}
    for t in range(1,100):owner._tick=t;owner._tick_water_marker_cleanup()
    assert world.reads==calls==[]
    owner._pending_portal_entries={}
    for t in range(100,140):owner._tick=t;owner._tick_water_marker_cleanup()
    assert calls==[(POS,{'name':'minecraft:air','aux':0},0,DIM,True,True)]
    assert owner._worldgen_perf_snapshot()['counters']['waterMarker_cleared']==1


def test_server_lifecycle_has_eager_init_tick_and_teardown_hooks():
    # The behavioral tests exercise callback/adapter; this verifies they are
    # also wired into the engine-owned lifecycle rather than left standalone.
    from tests.test_portal_arrival_runtime import SERVER_PATH
    source=SERVER_PATH.read_text('utf-8')
    init=source[source.index('    def __init__('):source.index('    def Destroy(')]
    assert 'self._water_marker_cleanup = water_marker_cleanup.WaterMarkerCleanup' in init
    update=source[source.index('    def Update('):]
    assert 'self._tick_water_marker_cleanup()' in update.split('\n    def ',1)[0]
    destroy=source[source.index('    def Destroy('):].split('\n    def ',1)[0]
    assert 'cleanup.close()' in destroy
