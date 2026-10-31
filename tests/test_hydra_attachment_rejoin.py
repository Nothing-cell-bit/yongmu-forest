"""Run production AddEntity/reconciliation/ensure against an engine inventory.

Only component storage, inventory and actor creation are substitutes. Persistence
ownership, deduplication, registration and replacement decisions are production.
"""
from pathlib import Path
import sys
import textwrap
import types
import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'TwilightBossSliceB/TwilightBossSlice'
sys.path.insert(0, str(PACKAGE.parent))
from TwilightBossSlice import entity_registry_logic, hydra_logic


def make_host(source=None):
    from lib2to3.refactor import RefactoringTool
    converter = RefactoringTool(['lib2to3.fixes.fix_print'])
    source = source or (PACKAGE / 'serverSystem.py').read_text('utf-8')
    data, actors, destroyed, spawns = {}, {}, [], []
    class Extra:
        def __init__(self, actor): self.actor = str(actor)
        def GetExtraData(self, key):
            if (key == 'fixture:hydra_state' and self.actor in actors
                    and actors[self.actor] == 'HYDRA_IDENTIFIER'
                    and key not in data.get(self.actor, {})):
                data.setdefault(self.actor, {})[key] = dict(
                    version=6, health=137, dimensionId=0, home=[0,64,0],
                    heads=[dict(alive=(i<3),deadTicks=-1,state='idle',damage=17*i)
                           for i in range(7)])
            return data.get(self.actor, {}).get(key)
        def SetExtraData(self, key, value, *args):
            data.setdefault(self.actor, {})[key] = value
        def SaveExtraData(self): return True
    cf = types.SimpleNamespace(CreateExtraData=Extra,
        CreateName=lambda _: types.SimpleNamespace(SetName=lambda _: None))
    ns = dict(CF=cf, entity_registry_logic=entity_registry_logic,
              hydra_logic=hydra_logic, HYDRA_HEAD_COUNT=7, HYDRA_NECK_COUNT=5,
              config=types.SimpleNamespace(DIMENSION_ID=0,HYDRA_STATE_EXTRA_KEY='fixture:hydra_state'),
              PHANTOM_UR_GHAST_MOB_IDENTIFIERS=())
    for constant in ('HYDRA_IDENTIFIER', 'HYDRA_HEAD_IDENTIFIER',
                     'HYDRA_NECK_IDENTIFIER', 'HYDRA_PART_PROXY_IDENTIFIER',
                     'UR_GHAST_TROPHY_VISUAL', 'UR_GHAST_IDENTIFIER',
                     'UR_GHAST_FIREBALL_IDENTIFIER', 'SLIME_BLOB_IDENTIFIER',
                     'KNIGHT_PHANTOM_IDENTIFIER'):
        ns[constant] = constant
    Host = type('Host', (), {})
    for name in ('OnAddEntity', '_register_hydra', '_load_hydra_state',
                 '_save_hydra_state', '_new_hydra_state', '_bind_hydra_head',
                 '_restore_hydra_head_owner', '_bind_hydra_part',
                 '_restore_hydra_part_owner', '_bind_hydra_neck',
                 '_restore_hydra_neck_owner', '_recover_hydra_attachments',
                 '_ensure_hydra_heads', '_ensure_hydra_necks'):
        marker = '    def ' + name + '('
        method = marker + source.split(marker, 1)[1].split('\n    def ', 1)[0]
        method = method.split('\n    @', 1)[0]
        exec(str(converter.refactor_string(textwrap.dedent(method).rstrip()+'\n', name)), ns)
        setattr(Host, name, ns[name])
    host = Host()
    host._hydras, host._hydra_heads, host._hydra_parts, host._hydra_necks = {}, {}, {}, {}
    host._hydra_attachment_rescan = True
    host._hydra_attachment_scan_tick = -20
    host._hydra_legacy_necks = {}
    host._tick = 100
    host._get_rotation = lambda *args: (0,0)
    host._get_foot_pos = lambda *args: (0,64,0)
    host._set_health_max = host._set_health = host._set_health_cap = lambda *args: None
    host._set_full_motion = lambda *args: None
    host._loaded_actors = lambda: [(key, {'identifier': value}) for key, value in actors.items()]
    host._get_engine_type = lambda actor: actors.get(str(actor))
    host._get_dimension = lambda actor: 0
    host._hydra_head_position = lambda *args, **kwargs: (0, 3, 0)
    host._hydra_neck_transforms = lambda *args, **kwargs: None
    host._remove_hydra_head_actor = lambda head: None
    def destroy(actor):
        destroyed.append(str(actor)); actors.pop(str(actor), None)
    def spawn(kind, *args):
        actor = 'new-' + str(len(spawns));spawns.append(actor);actors[actor] = kind
        return actor
    host.DestroyEntity, host._spawn_ruin_entity = destroy, spawn
    def add(actor, kind):
        actors[actor] = kind
        host.OnAddEntity({'id': actor, 'engineTypeStr': kind, 'dimensionId': 0})
    return host, ns, data, actors, destroyed, spawns, add


@pytest.mark.parametrize('head_first', [True, False])
def test_reentry_reuses_saved_heads_before_spawning_replacements(head_first):
    host, ns, data, actors, destroyed, spawns, add = make_host()
    for i in range(3):
        data['head'+str(i)] = {'tf_slice:hydra_head_owner_v1': {'ownerId':'boss', 'index':i}}
    if not head_first: add('boss', ns['HYDRA_IDENTIFIER'])
    for i in range(3): add('head'+str(i), ns['HYDRA_HEAD_IDENTIFIER'])
    if head_first: add('boss', ns['HYDRA_IDENTIFIER'])
    host._recover_hydra_attachments()
    host._tick = 106
    host._ensure_hydra_heads('boss', host._hydras['boss'])
    assert [h['entityId'] for h in host._hydras['boss']['heads'][:3]] == ['head0','head1','head2']
    assert host._hydras['boss']['health'] == 137
    assert host._hydras['boss']['heads'][1]['damage'] == 17
    assert data['boss']['fixture:hydra_state']['health'] == 137
    assert not spawns and not destroyed


def test_inventory_pass_recovers_missing_events_and_deduplicates_only_same_owner_slot():
    host, ns, data, actors, destroyed, spawns, add = make_host()
    actors.update(boss=ns['HYDRA_IDENTIFIER'], other=ns['HYDRA_IDENTIFIER'])
    for actor, owner in [('a','boss'), ('duplicate','boss'), ('b','other')]:
        actors[actor] = ns['HYDRA_HEAD_IDENTIFIER']
        data[actor] = {'tf_slice:hydra_head_owner_v1': {'ownerId':owner, 'index':0}}
    host._recover_hydra_attachments()
    assert destroyed == ['duplicate']
    assert host._hydras['boss']['heads'][0]['entityId'] == 'a'
    assert host._hydras['other']['heads'][0]['entityId'] == 'b'
    host._tick += 20
    host._recover_hydra_attachments()
    assert destroyed == ['duplicate']


def test_necks_and_body_proxies_restore_and_only_legacy_necks_expire():
    host, ns, data, actors, destroyed, spawns, add = make_host()
    add('boss', ns['HYDRA_IDENTIFIER'])
    data['neck'] = {'tf_slice:hydra_neck_owner_v1': {'ownerId':'boss','index':0,'segment':2}}
    data['body'] = {'tf_slice:hydra_part_owner_v1': {'ownerId':'boss','part':'body'}}
    data['waiting'] = {'tf_slice:hydra_neck_owner_v1': {'ownerId':'unloaded','index':0,'segment':2}}
    for actor, kind in [('neck','HYDRA_NECK_IDENTIFIER'),('body','HYDRA_PART_PROXY_IDENTIFIER'),
                        ('legacy','HYDRA_NECK_IDENTIFIER'),('waiting','HYDRA_NECK_IDENTIFIER')]:
        add(actor, ns[kind])
    host._recover_hydra_attachments()
    assert host._hydras['boss']['heads'][0]['neckIds'][2] == 'neck'
    assert host._hydras['boss']['partIds']['body'] == 'body'
    host._tick += 60
    host._recover_hydra_attachments()
    assert destroyed == ['legacy']


def test_dead_head_is_removed_and_missing_owner_is_retained_for_later_load():
    host, ns, data, actors, destroyed, spawns, add = make_host()
    add('boss', ns['HYDRA_IDENTIFIER'])
    for actor, index, owner in [('dead',6,'boss'),('waiting',0,'later')]:
        data[actor] = {'tf_slice:hydra_head_owner_v1': {'ownerId':owner,'index':index}}
        add(actor, ns['HYDRA_HEAD_IDENTIFIER'])
    host._recover_hydra_attachments()
    assert 'dead' in destroyed and 'waiting' not in destroyed
    add('later', ns['HYDRA_IDENTIFIER'])
    host._recover_hydra_attachments()
    assert host._hydras['later']['heads'][0]['entityId'] == 'waiting'


def test_existing_parent_reload_requests_reconciliation_without_resetting_health():
    host, ns, data, actors, destroyed, spawns, add = make_host()
    add('boss', ns['HYDRA_IDENTIFIER'])
    host._hydra_attachment_rescan = False
    state = host._hydras['boss']; state['health'] = 92
    add('boss', ns['HYDRA_IDENTIFIER'])
    assert host._hydra_attachment_rescan
    assert host._hydras['boss'] is state and state['health'] == 92


def test_reconciliation_is_wired_before_combat_ensure():
    source = (PACKAGE/'serverSystem.py').read_text('utf-8')
    drive = source.split('    def _drive_hydras(',1)[1].split('\n    def ',1)[0]
    assert drive.index('self._recover_hydra_attachments()') < drive.index('self._ensure_hydra_heads(')
