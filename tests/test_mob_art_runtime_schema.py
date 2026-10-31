"""Regress the actual client schema error and exercise Naga's production chain."""
import copy,json,re,sys,types,warnings
from pathlib import Path
import numpy as np
import pytest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
RP=ROOT/'TwilightBossSliceR';BP=ROOT/'TwilightBossSliceB'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def test_all_client_entities_omit_empty_optional_animation_nodes():
    for path in (RP/'entity').glob('*.json'):
        d=read(path)['minecraft:client_entity']['description']
        assert d.get('animations')!={},path.name
        assert d.get('scripts',{}).get('animate')!=[],path.name
        assert d.get('scripts')!={},path.name


def test_static_segment_survives_real_art_writer_without_inventing_animation_fields(tmp_path):
    from tools import build_public_block_shapes as writer
    bank=tmp_path/'resource_art/entity_beautification/v1';bank.mkdir(parents=True)
    (bank/'manifest.json').write_text((ROOT/'resource_art/entity_beautification/v1/manifest.json').read_text(encoding='utf-8'),encoding='utf-8')
    original=read(ROOT/'resource_art/entity_beautification/v1/mob_batch_sources.json')['entities']['forest_wyrm_segment']['description']
    doc={'format_version':'1.10.0','minecraft:client_entity':{'description':copy.deepcopy(original)}}
    for damaged in [False,True]:
        value=copy.deepcopy(doc)
        if damaged:value['minecraft:client_entity']['description'].update({'animations':{},'scripts':{'animate':[],'pre_animation':['variable.example = 1;']}})
        path=tmp_path/'TwilightBossSliceR/entity/forest_wyrm_segment.entity.json'
        writer.write_json(path,value)
        d=read(path)['minecraft:client_entity']['description']
        assert 'animations' not in d
        assert 'animate' not in d.get('scripts',{})
        if damaged:assert d['scripts']['pre_animation']==['variable.example = 1;']
        else:assert 'scripts' not in d
        assert d['geometry']['default']=='geometry.tf_slice.forest_wyrm_segment_art_v1'
        assert d['textures']['default']=='textures/tf_beautified/entities/mobs/nagasegment'


def test_all_segment_roles_resolve_to_visible_classic_body_geometry_and_texture():
    spec=read(ROOT/'resource_art/entity_beautification/v1/manifest.json')['entities']['tf_slice:forest_wyrm_segment']
    d=read(RP/spec['client_entity'])['minecraft:client_entity']['description']
    controller=read(RP/'render_controllers/forest_wyrm_segment.render.json')['render_controllers']['controller.render.tf_slice.forest_wyrm_segment']
    assert controller['arrays']['geometries']['Array.body_shapes']==['Geometry.default','Geometry.taper','Geometry.tail']
    assert 'part_visibility' not in controller
    for alias,expected in [('default',16),('taper',14),('tail',12)]:
        g=read(RP/spec['geometry_paths'][alias])['minecraft:geometry'][0]
        assert g['description']['identifier']==d['geometry'][alias]
        assert g['bones'][0]['cubes'][0]['size']==[expected]*3
    image=np.asarray(Image.open(RP/(d['textures']['default']+'.png')).convert('RGBA'))
    assert image.shape==(32,64,4)
    assert (image[16:32,:64,3]==255).all()


def test_real_segment_spawn_and_follow_methods_build_twelve_parts():
    # Only the external engine factory is simulated. The production spawn,
    # chain loop and movement math execute unchanged from their source files.
    from lib2to3.refactor import RefactoringTool
    sys.path.insert(0,str(BP/'TwilightBossSlice'))
    import naga_logic
    source=(BP/'TwilightBossSlice/serverSystem.py').read_text(encoding='utf-8')
    methods=[]
    for name in ['_create_loaded_entity','_spawn_segment','_ensure_segment_chain']:
        match=re.search(r'^    def '+name+r'\(',source,re.M);end=re.search(r'^    (?:def |@)',source[match.end():],re.M)
        methods.append(source[match.start():match.end()+end.start()])
    positions={'head':(0.,64.,0.)};rotations={};creates=[]
    factory=types.SimpleNamespace(
        CreatePos=lambda entity:types.SimpleNamespace(SetPos=lambda pos:positions.__setitem__(entity,tuple(pos))),
        CreateRot=lambda entity:types.SimpleNamespace(SetRot=lambda rot:rotations.__setitem__(entity,tuple(rot))))
    import entity_spawn_guard
    namespace={'CF':factory,'SEGMENT_IDENTIFIER':'tf_slice:forest_wyrm_segment','naga_logic':naga_logic,
               'entity_spawn_guard':entity_spawn_guard}
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',DeprecationWarning)
        payload=str(RefactoringTool(['lib2to3.fixes.fix_print']).refactor_string('class UnderTest:\n'+''.join(methods),'serverSystem.py'))
    exec(payload,namespace);sut=namespace['UnderTest']();sut._segment_owners={}
    sut._chunk_comp=types.SimpleNamespace(CheckChunkState=lambda dimension,position:True)
    def create(identifier,pos,rot,dimension,*flags):
        entity='part-%d'%len(creates);creates.append((identifier,pos,rot,dimension,flags));positions[entity]=tuple(pos);return entity
    sut.CreateEngineEntityByTypeStr=create;sut._get_foot_pos=positions.get;sut._get_rotation=lambda entity:(0.,0.);sut._segment_is_in_wall=lambda pos,dimension:False
    state={'dimensionId':0,'segments':naga_logic.MAX_SEGMENTS,'segmentIds':[None]*naga_logic.MAX_SEGMENTS,'segmentBurstTicks':{},'brain':types.SimpleNamespace(state='circle'),'health':200.}
    sut._ensure_segment_chain('head',state)
    assert naga_logic.MAX_SEGMENTS==12
    assert len(creates)==len(set(state['segmentIds']))==12
    assert all(row[0]=='tf_slice:forest_wyrm_segment' for row in creates)
    assert len(sut._segment_owners)==12
    assert len(rotations)==12 and len({positions[p] for p in state['segmentIds']})==12
    sut._ensure_segment_chain('head',state)
    assert len(creates)==12


def test_use_duration_components_are_supported_and_preserve_declared_time():
    for name,seconds in [('crumble_horn',3600),('magic_map',.05)]:
        item=read(BP/'items'/(name+'.item.json'))['minecraft:item']
        c=item['components'];assert 'minecraft:use_duration' not in c
        assert c['minecraft:use_modifiers']['use_duration']==seconds
        assert c['minecraft:use_animation']=='bow'


def test_utility_schema_migration_preserves_icons_and_rejects_unknown_duration(tmp_path):
    from tools.build_creative_catalog import repair_utility_use_components
    items=tmp_path/'items';items.mkdir()
    for name,ticks in [('crumble_horn',72000),('magic_map',1)]:
        doc=read(BP/'items'/(name+'.item.json'))
        c=doc['minecraft:item']['components'];c.pop('minecraft:use_modifiers');c['minecraft:use_duration']=ticks
        (items/(name+'.json')).write_text(json.dumps(doc),encoding='utf-8')
    assert repair_utility_use_components(tmp_path)==2
    assert repair_utility_use_components(tmp_path)==0
    assert read(items/'magic_map.json')['minecraft:item']['components']['minecraft:icon']==read(BP/'items/magic_map.item.json')['minecraft:item']['components']['minecraft:icon']
    bad=read(items/'magic_map.json');bad['minecraft:item']['components']['minecraft:use_duration']=40
    (items/'magic_map.json').write_text(json.dumps(bad),encoding='utf-8')
    with pytest.raises(ValueError,match='review units'):repair_utility_use_components(tmp_path)


def test_catalog_ownership_is_preserved_at_real_writer_without_altering_mining(tmp_path):
    from tools import build_public_block_shapes as writer
    bp=tmp_path/'TwilightBossSliceB';catalog=bp/'item_catalog/crafting_item_catalog.json';catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({'minecraft:crafting_items_catalog':{'categories':[{'groups':[{'items':['tf_slice:canopy_sapling','tf_slice:naga_trophy_item']}]}]}}),encoding='utf-8')
    block=read(BP/'netease_blocks/canopy_sapling.json');block['minecraft:block']['description']['register_to_creative_menu']=True
    path=bp/'netease_blocks/canopy_sapling.json';writer.write_json(path,block);modified=read(path)
    assert modified['minecraft:block']['description']['register_to_creative_menu'] is False
    modified['minecraft:block']['description']['register_to_creative_menu']=True
    assert modified==block
    item=read(BP/'items/naga_trophy.item.json');item['minecraft:item']['description']['menu_category']={'category':'nature'}
    path=bp/'items/naga_trophy.item.json';writer.write_json(path,item)
    assert 'menu_category' not in read(path)['minecraft:item']['description']
    hidden=copy.deepcopy(block);hidden['minecraft:block']['description']['identifier']='tf_slice:unlisted'
    writer.write_json(bp/'netease_blocks/unlisted.json',hidden)
    assert read(bp/'netease_blocks/unlisted.json')==hidden
