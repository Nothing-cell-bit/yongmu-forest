"""User-authored visual overlays for the reviewed living-mob inventory only."""
import argparse,copy,hashlib,json,math,shutil
from pathlib import Path
from PIL import Image
try:
    from entity_visual_overrides import apply_entity_visual_overrides
    import render_entity_geo_preview as preview
except ImportError:
    from tools.entity_visual_overrides import apply_entity_visual_overrides
    from tools import render_entity_geo_preview as preview

ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def swatch(image,geometry,cube,light=False,green=False):
    """Pick an existing opaque atlas texel from this part's mapped material."""
    desc=geometry['description'];sx=image.width/desc['texture_width'];sy=image.height/desc['texture_height']
    choices=[]
    for face in range(6):
        data=preview.face_texture_data(cube,face)
        if data is None:continue
        uv,size,_=data
        for fy in [.25,.5,.75]:
            for fx in [.25,.5,.75]:
                u=int(uv[0]+size[0]*fx);v=int(uv[1]+size[1]*fy)
                x=int(u*sx);y=int(v*sy)
                if not (0<=x<image.width and 0<=y<image.height):continue
                r,g,b,a=image.getpixel((x,y))
                if a>=240 and max(r,g,b)-min(r,g,b)<220 and (not green or (g>r*1.15 and g>b*1.3)):
                    choices.append(((r+g+b)/3,[u,v]))
    if not choices:raise ValueError('No opaque material sample in cube UV')
    choices.sort(key=lambda v:v[0]);return choices[int((len(choices)-1)*(.7 if light else .35))][1]


def box(origin,size,uv):
    return {'origin':[round(v,5) for v in origin],'size':[round(v,5) for v in size],
            'uv':{face:{'uv':list(uv),'uv_size':[1,1]} for face in ['north','south','east','west','up','down']}}


def fit_visible_bounds(geometry,motion):
    """Grow only the art variant's culling box, including numeric pose extrema."""
    poses=[{}]
    times=sorted({float(t) for data in motion.values() for t in data['rotation']})
    if times:
        try:
            from preview_deer_art_motion import sample_keyframes
        except ImportError:
            from tools.preview_deer_art_motion import sample_keyframes
        poses += [{name:sample_keyframes(data['rotation'],t,4) for name,data in motion.items()} for t in times]
    bones=geometry['bones'];lookup={b['name']:b for b in bones}
    points=[preview.transformed_point(p,b['name'],lookup,pose) for pose in poses for b in bones for c in b.get('cubes',[]) for p in preview.cube_vertices(c)]
    d=geometry['description'];center=[v*16 for v in d['visible_bounds_offset']]
    half=[d['visible_bounds_width']*8,d['visible_bounds_height']*8,d['visible_bounds_width']*8]
    if all(all(abs(p[i]-center[i])<=half[i] for i in range(3)) for p in points):return
    horizontal=max(half[0],*(abs(p[i]-center[i])+1 for p in points for i in [0,2]))
    lower=min(center[1]-half[1],min(p[1] for p in points)-1)
    upper=max(center[1]+half[1],max(p[1] for p in points)+1)
    lower=math.floor(lower/4)*4;upper=math.ceil(upper/4)*4
    d['visible_bounds_width']=math.ceil(horizontal/2)/4
    d['visible_bounds_height']=(upper-lower)/16
    d['visible_bounds_offset'][1]=(upper+lower)/32


def make_variant(name,alias,original,image):
    g=copy.deepcopy(original);bones={b['name']:b for b in g['bones']}
    moved=[];motion={};notes=[]
    g['description']['identifier']='geometry.tf_slice.'+name+'_art_v1'+('' if alias=='default' else '_'+alias)
    if name=='forest_wyrm' and alias=='eyelids':
        return g,motion,moved,['locked upstream closed-eye overlay on the classic cube; no artistic changes to state mask']

    def material(bone,light=False,index=0):return swatch(image,g,bones[bone]['cubes'][index],light,name.startswith('forest_wyrm'))
    def append(bone,origin,size,uv=None):
        bones[bone].setdefault('cubes',[]).append(box(origin,size,uv or material(bone)))
    def child(key,parent,pivot,cubes,rotation=None):
        bone={'name':'art_'+key,'parent':parent,'pivot':pivot,'cubes':cubes}
        if rotation:bone['rotation']=rotation
        if bone['name'] in bones:raise ValueError('Duplicate art bone')
        bones[bone['name']]=bone;g['bones'].append(bone);return bone['name']
    def animate(bone,axis,amount,phase=0):
        zero=[0,0,0];a=zero.copy();a[axis]=amount;b=zero.copy();b[axis]=-amount*.45
        motion[bone]={'rotation':{'0.0':zero,'%.2f'%(0.45+phase):zero,'%.2f'%(0.7+phase):a,'%.2f'%(1.0+phase):b,'%.2f'%(1.3+phase):zero,'4.0':zero}}
    def ridge(bone,count=3,height=.55,axis=None):
        c=bones[bone]['cubes'][0];o=c['origin'];s=c['size']
        axis=axis if axis is not None else (2 if abs(bones[bone].get('rotation',[0])[0])>=60 else 1)
        along=1 if axis==2 else 2
        for i in range(count):
            size=[max(.25,s[0]*.36),max(.25,s[1]*.12),max(.25,s[2]*.12)]
            size[axis]=height+.08;size[along]=s[along]*.20
            origin=[o[a]+(s[a]-size[a])*.5 for a in range(3)]
            origin[axis]=o[axis]+s[axis]-.08
            origin[along]=o[along]+s[along]*(.18+(i/max(1,count-1))*.55)-size[along]/2
            append(bone,origin,size,material(bone,i%2==0))
    def trim(bone,depth=.25):
        c=bones[bone]['cubes'][0];x,y,z=c['origin'];w,h,d=c['size'];t=min(.7,w*.12,h*.10)
        for origin,size in [([x+.1,y+.2,z-depth],[w-.2,t,depth+.06]),([x+.1,y+h-t-.2,z-depth],[w-.2,t,depth+.06]),([x+.15,y+.2,z-depth],[t,h-.4,depth+.06]),([x+w-t-.15,y+.2,z-depth],[t,h-.4,depth+.06])]:
            append(bone,origin,size,material(bone,True))
    def cuffs(bone):
        c=bones[bone]['cubes'][0];x,y,z=c['origin'];w,h,d=c['size'];t=min(.8,h*.12)
        append(bone,[x-.12,y+h*.20,z-.12],[w+.24,t,d+.24],material(bone,True))
    def feathers(bone):
        c=bones[bone]['cubes'][0];o=c['origin'];s=c['size'];pivot=bones[bone]['pivot']
        axis=max(range(3),key=lambda a:s[a])
        positive=abs(o[axis]+s[axis]-pivot[axis])>=abs(o[axis]-pivot[axis])
        for i in range(3):
            size=[max(.2,length*(.82-i*.10)) for length in s]
            size[axis]=.45+i*.18
            origin=[o[a]+(s[a]-size[a])/2 for a in range(3)]
            origin[axis]=(o[axis]+s[axis]-.08+i*.22) if positive else (o[axis]+.08-i*.22-size[axis])
            append(bone,origin,size,material(bone,i==1))
    def ears():
        c=bones['head']['cubes'][0];x,y,z=c['origin'];w,h,d=c['size'];length=min(3,w*.34)
        for side in [-1,1]:
            root=x if side<0 else x+w;pivot=[root,y+h-.5,z+d*.65]
            origin=[root-length+.08 if side<0 else root-.08,pivot[1]-.35,pivot[2]-.35]
            key=child('ear_'+('left' if side<0 else 'right'),'head',pivot,[box(origin,[length,.7,.7],material('head'))])
            animate(key,2,-side*14,0 if side<0 else 1.5)
    def split_ears(indices):
        saved=copy.deepcopy(bones['head']['cubes'])
        for order,index in enumerate(indices):
            c=saved[index];o=c['origin'];s=c['size'];pivot=[o[0]+s[0]/2,o[1],o[2]+s[2]/2]
            key=child('ear_'+str(order),'head',pivot,[c]);moved.append({'bone':'head','index':index,'new_bone':key})
            animate(key,2,14 if order==0 else -14,order*1.5)
        bones['head']['cubes']=[c for i,c in enumerate(saved) if i not in indices]
    def short_tail():
        c=bones['body']['cubes'][0];x,y,z=c['origin'];w,h,d=c['size'];length=min(3,h*.22)
        pivot=[x+w/2,y+.05,z+d*.65]
        key=child('tail','body',pivot,[box([pivot[0]-.4,y-length,pivot[2]-.4],[.8,length+.1,.8],material('body',True))]);animate(key,2,20)

    if name in ['bighorn_sheep','boar']:
        ears();short_tail();ridge('body',4,.6 if name=='bighorn_sheep' else 1)
        notes.append('independent ears and short tail; wool tufts' if name=='bighorn_sheep' else 'independent ears and tail; dorsal bristles')
    elif name=='dwarf_rabbit':
        split_ears([1,2]);ridge('body',2,.25)
        notes.append('original ear cubes reparented at their roots; small haunch fur tufts')
    elif name in ['hostile_wolf','mist_wolf']:
        split_ears([2,3]);ridge('upperBody',3,.55);feathers('tail');notes.append('articulated ears, neck ruff and tapered tail fur')
    elif name=='squirrel':
        ridge('fluff_3',2,.45);ridge('body',2,.22);split_ears([1,2]);notes.append('articulated original ears and stepped tail fur following original tail rig')
    elif name in ['tiny_bird','raven']:
        for bone in ['right_wing','left_wing','tail']:feathers(bone)
        ridge('head',1,.25);notes.append('layered wing tips, split tail feathers and small crown feather')
    elif name=='penguin':
        for bone in ['right_arm','left_arm']:feathers(bone)
        c=bones['body']['cubes'][0];x,y,z=c['origin'];w,h,d=c['size']
        key=child('tail','body',[0,y+1,z+d-.1],[box([-.9,y+.5,z+d-.15],[1.8,.6,1.6],material('body'))]);animate(key,1,12)
        notes.append('layered flipper edges and short articulated tail')
    elif name=='quest_ram':
        ridge('body',3,1);ridge('back_body',3,1);ears();notes.append('small wool tufts and articulated ears; quest colors unchanged')
    elif name in ['hedge_spider','king_spider','swarm_spider','tower_broodling']:
        ridge('body1',3,.65);ridge('body0',2,.35);notes.append('low segmented abdominal carapace ridges; original legs retained')
    elif name in ['fire_beetle','pinch_beetle','slime_beetle']:
        main='rear' if 'rear' in bones else 'body';ridge(main,3,.55)
        for bone in ['right_antenna','left_antenna']:
            if bone in bones and bones[bone].get('cubes'):feathers(bone)
        notes.append('chitin ridges and articulated antenna tips following existing rig')
    elif name in ['block_chain_goblin','helmet_crab','upper_goblin_knight']:
        trim('helmet');ridge('helmet',1,.45)
        if name=='upper_goblin_knight':trim('breastplate')
        notes.append('raised helmet rim and armor edging; original equipment and chains untouched')
    elif name=='lower_goblin_knight':
        trim('body');cuffs('right_arm');cuffs('left_arm');notes.append('layered leather armor hem and bracers')
    elif name=='carminite_golem':
        trim('body',.5);cuffs('right_arm');cuffs('left_arm');ridge('hips',2,.4);notes.append('raised plate seams and forearm iron bands')
    elif name=='knight_phantom':
        if alias=='armor':trim('body');cuffs('right_arm');cuffs('left_arm')
        else:trim('skeleton_body',.15)
        notes.append('spectral plate rims and rib edging; weapon locators retained')
    elif name=='kobold':
        ridge('body',2,.25);trim('body',.13);notes.append('shoulder cloth folds and raised tunic hem; original pointed ears retained')
    elif name in ['redcap','redcap_sapper']:
        ridge('hat',1,.45);trim('body',.18);cuffs('rightArm');cuffs('leftArm');notes.append('cap fold, tunic hem and cuffs')
    elif name in ['rising_zombie','lich_minion','loyal_zombie']:
        trim('body',.12);cuffs('rightArm');cuffs('leftArm');notes.append('layered torn shirt seams and sleeve cuffs')
    elif name in ['lich','lich_shadow_clone']:
        trim('body',.18);ridge('head',1,.25);notes.append('raised robe borders and subtle crown base; shield variants unchanged')
    elif name in ['wraith','skeleton_druid']:
        trim('body',.13);feathers('dress');notes.append('robe edge layers and ragged hem; face remains original')
    elif name=='death_tome':
        for bone in ['cover_left','cover_right']:trim(bone,.08)
        notes.append('thin raised book-cover borders following original cover bones')
    elif name in ['mini_ghast','tower_ghast']:
        for i in [0,2,6,8]:
            bone='tentacle_'+str(i);cuffs(bone)
        ridge('body',2,.25);notes.append('subtle crown surface relief and tentacle cuffs; all expression states retained')
    elif name=='minotaur':
        trim('body',.18);cuffs('rightArm');cuffs('leftArm');notes.append('leather harness relief and forearm bands')
    elif name=='minoshroom':
        ridge('cow_body',3,.9);trim('body',.2);notes.append('layered back fur and chest harness relief')
    elif name=='hydra':
        ridge('body',4,4);notes.append('low dorsal armored scutes scaled to the body')
    elif name=='hydra_head':
        ridge('head',3,1.4);notes.append('small crown scutes attached to existing head bone')
    elif name=='hydra_neck':
        ridge('neck',3,1.2);notes.append('neck scales following existing section transforms')
    elif name=='forest_wyrm':
        ridge('head',2,.45);notes.append('fine crown scales; eyelid and expression rigs unchanged')
    elif name=='forest_wyrm_segment':
        bone=next(b['name'] for b in g['bones'] if b.get('cubes'));ridge(bone,2,.4);notes.append('low segment scale relief, including taper and tail states')
    elif name=='maze_slime':
        ridge('cube',2,.2);notes.append('subtle interior masonry ridges; translucent outer surface retained')
    elif name=='towerwood_borer':
        for bone in ['segment_0','segment_2','segment_4']:ridge(bone,1,.25)
        notes.append('segmented dorsal shell plates following existing wriggle bones')
    elif name=='mosquito_swarm':
        for index in [0,8,16,24,32,40,48,56,64,72,80,88]:
            bone='bug_'+str(index);c=bones[bone]['cubes'][0];x,y,z=c['origin'];w,h,d=c['size']
            append(bone,[x-.3,y+h*.6,z],[w+.6,.12,max(.2,d*.5)],material(bone,True))
        notes.append('winglets on twelve existing insects; swarm count and flight rig unchanged')
    else:raise ValueError('Missing reviewed model plan: '+name+'/'+alias)
    fit_visible_bounds(g,motion)
    return g,motion,moved,notes


def build(root,task):
    root=Path(root);task=Path(task);rp=root/'TwilightBossSliceR';bank=root/'resource_art/entity_beautification/v1'
    sources=read(bank/'mob_batch_sources.json');export=read(task/'texture-export.json')
    if 'ur_ghast' in sources['entities']:raise ValueError('Ur-Ghast is explicitly excluded by the user')
    if export['missing'] or export['failures']:raise ValueError('Texture export is incomplete')
    manifest=read(bank/'manifest.json');selected=[]
    for key,source in sources['textures'].items():
        texture=task/'exports'/(key+'.png');assert sha(texture)==export['entries'][key]['output_sha256']
        for target in [rp/'textures/tf_beautified/entities/mobs'/(key+'.png'),bank/'assets/mobs'/(key+'.png')]:
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(texture,target)
        selected.append('TwilightBossSliceR:textures/tf_beautified/entities/mobs/'+key+'.png')
    for name,entry in sources['entities'].items():
        identifier=entry['description']['identifier'];mapping={};paths={};reparented={};notes=[];motion={}
        for alias,source_id in entry['geometry_sources'].items():
            if alias=='shields':continue
            source_geometry=read(bank/sources['geometries'][source_id]['baseline'])['minecraft:geometry'][0]
            texture_key=entry['texture_keys'].get(alias,next(iter(entry['texture_keys'].values())))
            with Image.open(bank/sources['textures'][texture_key]['baseline']).convert('RGBA') as image:
                geometry,animation,moved,detail=make_variant(name,alias,source_geometry,image)
            mapping[alias]=geometry['description']['identifier'];relative='models/entity/art/mobs/'+name+'_'+alias+'.geo.json'
            payload={'format_version':'1.12.0','minecraft:geometry':[geometry]}
            write(rp/relative,payload);write(bank/'geometry/mobs'/(name+'_'+alias+'.json'),payload)
            paths[alias]=relative;reparented[alias]=moved;notes.extend(detail);motion.update(animation)
            selected.append('TwilightBossSliceR:'+relative)
        previous=manifest['entities'].get(identifier,{})
        spec={'client_entity':'entity/'+name+'.entity.json','source_geometries':entry['description']['geometry'],'geometries':mapping,'geometry_paths':paths,
              'source_textures':entry['description']['textures'],'textures':{alias:'textures/tf_beautified/entities/mobs/'+key for alias,key in entry['texture_keys'].items()},
              'reparented':reparented,'design_notes':notes,'scope':'model-only; user-authorized art expansion','status':previous.get('status','draft-runtime-pending'),'behavior':'not_reviewed'}
        for evidence_field in ['runtime_failure_evidence','repair_status']:
            if evidence_field in previous:spec[evidence_field]=previous[evidence_field]
        if motion:
            animation_id='animation.tf_slice.'+name+'_art.details';relative='animations/art/'+name+'.animation.json'
            payload={'format_version':'1.8.0','animations':{animation_id:{'loop':True,'animation_length':4,'bones':motion}}}
            write(rp/relative,payload);write(bank/'animations/mobs'/(name+'.json'),payload)
            spec.update({'animation_path':relative,'animations':{'art_details':animation_id},'animate':['art_details']});selected.append('TwilightBossSliceR:'+relative)
        manifest['entities'][identifier]=spec
    write(bank/'manifest.json',manifest)
    for name,entry in sources['entities'].items():
        path=rp/'entity'/(name+'.entity.json')
        # Start from the locked client document, retaining every gameplay-linked
        # native animation, expression, render controller and equipment binding.
        original=read(task/'before/files/entity'/(name+'.entity.json'))
        write(path,apply_entity_visual_overrides(path,original));selected.append('TwilightBossSliceR:entity/'+name+'.entity.json')
    receipt={'entities':len(sources['entities']),'textures':len(sources['textures']),'include_files':selected,
             'hashes':{s:sha(root/s.split(':',1)[0]/s.split(':',1)[1]) for s in selected},'scope':'model-only','runtime_acceptance':'not_executed','pack_synchronization':'not_executed','behavior':'not_reviewed'}
    write(task/'integration-receipt.json',receipt)
    print(json.dumps({'entities':receipt['entities'],'textures':receipt['textures'],'pack_files':len(selected)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project-root',type=Path,default=ROOT);parser.add_argument('--task',type=Path,required=True)
    args=parser.parse_args();build(args.project_root,args.task)
