"""Art overlays preserve original rigs, state textures and native gameplay."""
import copy,json,math
from pathlib import Path
import pytest
from PIL import Image
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BANK=ROOT/'resource_art/entity_beautification/v1'
RP=ROOT/'TwilightBossSliceR'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def test_every_reviewed_mob_and_state_resolves_to_private_art_resources():
    sources=read(BANK/'mob_batch_sources.json')
    registry=read(BANK/'manifest.json')['entities']
    assert len(sources['entities'])==46
    assert 'ur_ghast' not in sources['entities']
    for name,source in sources['entities'].items():
        spec=registry['tf_slice:'+name]
        client=read(RP/spec['client_entity'])['minecraft:client_entity']['description']
        for alias,key in source['texture_keys'].items():
            assert client['textures'][alias]=='textures/tf_beautified/entities/mobs/'+key
            assert (RP/(client['textures'][alias]+'.png')).is_file()
        for alias,identifier in spec['geometries'].items():
            path=RP/spec['geometry_paths'][alias]
            assert read(path)['minecraft:geometry'][0]['description']['identifier']==identifier
        assert client['geometry']['default']!=source['description']['geometry']['default']
        for key in ['materials','render_controllers','spawn_egg']:
            assert client.get(key)==source['description'].get(key)


def test_all_native_textures_and_transparency_survive_and_each_asset_changes():
    source=read(BANK/'mob_batch_sources.json')
    assert len(source['textures'])==54
    for key,spec in source['textures'].items():
        a=np.asarray(Image.open(BANK/spec['baseline']).convert('RGBA'))
        b=np.asarray(Image.open(RP/('textures/tf_beautified/entities/mobs/'+key+'.png')).convert('RGBA'))
        assert a.shape==b.shape
        assert np.array_equal(a[:,:,3],b[:,:,3]),key
        if key=='nagahead_dazed':assert np.array_equal(a,b)
        else:assert (a!=b).any(),key


def test_rig_contract_reparented_parts_stay_at_rest_and_existing_layers_are_kept():
    from tools import render_entity_geo_preview as preview
    sources=read(BANK/'mob_batch_sources.json');registry=read(BANK/'manifest.json')['entities']
    for name,entry in sources['entities'].items():
        spec=registry['tf_slice:'+name];client=read(RP/spec['client_entity'])['minecraft:client_entity']['description']
        for key,value in entry['description'].get('animations',{}).items():assert client['animations'][key]==value
        old_animate=entry['description'].get('scripts',{}).get('animate',[])
        assert client.get('scripts',{}).get('animate',[])[:len(old_animate)]==old_animate
        for alias,path in spec['geometry_paths'].items():
            original=read(BANK/sources['geometries'][entry['geometry_sources'][alias]]['baseline'])['minecraft:geometry'][0]
            modified=read(RP/path)['minecraft:geometry'][0]
            old={b['name']:b for b in original['bones']};new={b['name']:b for b in modified['bones']}
            assert len(new)==len(modified['bones'])
            moved={(r['bone'],r['index']):r['new_bone'] for r in spec['reparented'].get(alias,[])}
            for bone_name,bone in old.items():
                assert {k:v for k,v in new[bone_name].items() if k!='cubes'}=={k:v for k,v in bone.items() if k!='cubes'}
                remaining=[cube for i,cube in enumerate(bone.get('cubes',[])) if (bone_name,i) not in moved]
                assert new[bone_name].get('cubes',[])[:len(remaining)]==remaining
                for i,cube in enumerate(bone.get('cubes',[])):
                    if (bone_name,i) in moved:
                        parent=moved[bone_name,i]
                        assert new[parent]['cubes'][0]==cube
                        for point in preview.cube_vertices(cube):
                            assert np.allclose(preview.transformed_point(point,bone_name,old,{}),preview.transformed_point(point,parent,new,{}))


def test_cosmetic_keyframes_have_bounded_rotation_and_explicit_loops():
    sources=read(BANK/'mob_batch_sources.json');registry=read(BANK/'manifest.json')['entities']
    count=0
    for name in sources['entities']:
        spec=registry['tf_slice:'+name]
        if not spec.get('animation_path'):continue
        definitions=read(RP/spec['animation_path'])['animations']
        for animation in definitions.values():
            count+=1;assert animation['loop'] is True;length=animation['animation_length'];assert length>0
            for bone,channels in animation['bones'].items():
                assert bone.startswith('art_')
                assert set(channels)=={'rotation'}
                frames=channels['rotation'];assert min(map(float,frames))==0 and max(map(float,frames))==length
                assert list(frames.values())[0]==list(frames.values())[-1]
                assert any(v!=list(frames.values())[0] for v in frames.values())
                assert all(isinstance(n,(int,float)) and abs(n)<=24 for v in frames.values() for n in v)
    assert count>=4


def test_naga_uses_classic_upstream_cube_and_expression_masks_remain_exact():
    sources=read(BANK/'mob_batch_sources.json');registry=read(BANK/'manifest.json')['entities']
    spec=registry['tf_slice:forest_wyrm']
    model=read(RP/spec['geometry_paths']['default'])['minecraft:geometry'][0]
    assert model['description']['texture_width']==64
    assert model['description']['texture_height']==32
    assert set(b['name'] for b in model['bones'])=={'head'}
    assert model['bones'][0]['cubes'][0]=={'origin':[-8,0,-8],'size':[16,16,16],'uv':[0,0]}
    assert 'eyelids' in spec['geometry_paths']
    for key in ['nagahead','nagahead_charging','tf_slice__mini_ghast','tf_slice__tower_ghast']:
        a=np.asarray(Image.open(BANK/sources['textures'][key]['baseline']).convert('RGBA'))
        b=np.asarray(Image.open(RP/('textures/tf_beautified/entities/mobs/'+key+'.png')).convert('RGBA'))
        assert np.array_equal(a[16:32,16:32],b[16:32,16:32]),key
    for base,state in [('nagahead','nagahead_charging'),('tf_slice__mini_ghast','tf_slice__mini_ghast_attack'),('tf_slice__mini_ghast','tf_slice__mini_ghast_open')]:
        a=np.asarray(Image.open(BANK/sources['textures'][base]['baseline']).convert('RGBA'))
        s=np.asarray(Image.open(BANK/sources['textures'][state]['baseline']).convert('RGBA'))
        enhanced=np.asarray(Image.open(RP/('textures/tf_beautified/entities/mobs/'+state+'.png')).convert('RGBA'))
        different=(a!=s).any(2)
        assert np.array_equal(enhanced[different],s[different])


def test_multiple_texture_aliases_survive_real_resource_writer(tmp_path):
    from tools import build_public_block_shapes as writer
    sources=read(BANK/'mob_batch_sources.json')
    target_bank=tmp_path/'resource_art/entity_beautification/v1';target_bank.mkdir(parents=True)
    (target_bank/'manifest.json').write_text((BANK/'manifest.json').read_text(encoding='utf-8'),encoding='utf-8')
    for name in ['dwarf_rabbit','tiny_bird','forest_wyrm','knight_phantom']:
        original={'format_version':'1.10.0','minecraft:client_entity':{'description':copy.deepcopy(sources['entities'][name]['description'])}}
        path=tmp_path/'TwilightBossSliceR/entity'/(name+'.entity.json')
        writer.write_json(path,original);result=read(path);writer.write_json(path,result)
        assert read(path)==result
        description=result['minecraft:client_entity']['description']
        for alias in sources['entities'][name]['texture_keys']:
            assert description['textures'][alias].startswith('textures/tf_beautified/entities/mobs/')
        assert set(description['textures'])==set(original['minecraft:client_entity']['description']['textures'])


def test_art_model_visible_bounds_contain_rest_and_cosmetic_motion_vertices():
    from tools import render_entity_geo_preview as renderer
    from tools.preview_deer_art_motion import sample_bound_animations
    sources=read(BANK/'mob_batch_sources.json');registry=read(BANK/'manifest.json')['entities']
    for name in sources['entities']:
        spec=registry['tf_slice:'+name];client=read(RP/spec['client_entity'])['minecraft:client_entity']['description']
        for alias,path in spec['geometry_paths'].items():
            g=read(RP/path)['minecraft:geometry'][0];lookup={b['name']:b for b in g['bones']};d=g['description'];center=[v*16 for v in d['visible_bounds_offset']]
            half=[d['visible_bounds_width']*8,d['visible_bounds_height']*8,d['visible_bounds_width']*8]
            poses=[{}]
            if alias=='default' and spec.get('animation_path'):
                definitions=read(RP/spec['animation_path'])
                poses += [sample_bound_animations(definitions,client,t,0,0) for t in [.7,1,2.2,2.5]]
            for pose in poses:
                for bone in g['bones']:
                    for cube in bone.get('cubes',[]):
                        for point in renderer.cube_vertices(cube):
                            transformed=renderer.transformed_point(point,bone['name'],lookup,pose)
                            assert all(abs(transformed[i]-center[i])<=half[i]+1e-6 for i in range(3)),(name,alias,bone['name'],transformed)


def test_model_recipe_reproduces_reviewed_live_geometry_and_motion():
    from tools.build_mob_art_batch import make_variant
    sources=read(BANK/'mob_batch_sources.json');registry=read(BANK/'manifest.json')['entities']
    for name,entry in sources['entities'].items():
        spec=registry['tf_slice:'+name];motions={}
        for alias,path in spec['geometry_paths'].items():
            original=read(BANK/sources['geometries'][entry['geometry_sources'][alias]]['baseline'])['minecraft:geometry'][0]
            key=entry['texture_keys'].get(alias,next(iter(entry['texture_keys'].values())))
            image=Image.open(BANK/sources['textures'][key]['baseline']).convert('RGBA')
            geometry,motion,moved,notes=make_variant(name,alias,original,image)
            assert geometry==read(RP/path)['minecraft:geometry'][0]
            assert moved==spec['reparented'][alias]
            motions.update(motion)
        if motions:
            assert next(iter(read(RP/spec['animation_path'])['animations'].values()))['bones']==motions


def test_translucent_generator_output_cannot_masquerade_as_opaque_texture_detail():
    from tools.mob_art_texture_export import extract
    source=Image.new('RGBA',(32,32),(30,40,20,255))
    translucent=Image.new('RGBA',(128,128),(35,45,25,160))
    with pytest.raises(ValueError,match='No valid generated interior'):
        extract(source,translucent,np.zeros((32,32),dtype=bool))
