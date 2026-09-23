"""Pure, scoped resource definitions for the 4.3.2508 goblin combat driver."""
import copy

KINDS=('block_chain_goblin','lower_goblin_knight','upper_goblin_knight')


def configure_entity(name,document):
    if name not in KINDS:return document
    d=copy.deepcopy(document);e=d['minecraft:entity'];c=e['components'];props=e['description'].setdefault('properties',{})
    c['minecraft:movement']['value']=0.28
    c['minecraft:behavior.melee_attack'].update(priority=5 if name==KINDS[0] else 3,speed_multiplier=1.0,track_target=False)
    c['minecraft:behavior.random_stroll']['speed_multiplier']=1.0
    c['minecraft:behavior.random_look_around']['priority']=7
    c['minecraft:behavior.float']['priority']=0 if name==KINDS[0] else 1
    c['minecraft:behavior.nearest_attackable_target']['must_see']=name==KINDS[0]
    c.pop('minecraft:armor',None)
    if name==KINDS[1]:c['minecraft:rideable']['seats']['position']=[0,1.0,0]
    groups=e.setdefault('component_groups',{});events=e.setdefault('events',{})
    normal={}
    for k in list(c):
        if k.startswith('minecraft:behavior.') and k not in ('minecraft:behavior.hurt_by_target','minecraft:behavior.nearest_attackable_target'):
            if name==KINDS[0] and k=='minecraft:behavior.float':continue
            normal[k]=c.pop(k)
    groups['tf_slice:goblin_normal']=normal
    events['tf_slice:goblin_hold']={'remove':{'component_groups':['tf_slice:goblin_normal']}}
    events['tf_slice:goblin_fight']={'add':{'component_groups':['tf_slice:goblin_normal']}}
    initial=['tf_slice:goblin_normal']
    if name==KINDS[0]:
        props['tf_slice:chain_external']={'type':'bool','default':False,'client_sync':True}
    else:
        props['tf_slice:has_armor']={'type':'bool','default':True,'client_sync':True}
        events['tf_slice:goblin_armor']={'set_property':{'tf_slice:has_armor':True}}
        events['tf_slice:goblin_break_armor']={'set_property':{'tf_slice:has_armor':False}}
        if name==KINDS[2]:
            props['tf_slice:has_shield']={'type':'bool','default':True,'client_sync':True}
            props['tf_slice:spear_timer']={'type':'int','range':[0,60],'default':0,'client_sync':True}
    events['minecraft:entity_spawned']={'add':{'component_groups':initial}}
    return d


def configure_client(name,document):
    if name not in KINDS:return document
    d=copy.deepcopy(document)
    if name in KINDS[1:]:d['minecraft:client_entity']['description']['render_controllers']=['controller.render.tf_slice.'+name]
    return d


def render_controllers():
    result={}
    for name,armor in [(KINDS[1],'tunic'),(KINDS[2],'breastplate')]:
        visible=[{armor:"query.property('tf_slice:has_armor')"}]
        if name==KINDS[2]:visible.append({'shield':"query.property('tf_slice:has_shield')"})
        result['controller.render.tf_slice.'+name]={'geometry':'Geometry.default','materials':[{'*':'Material.default'}],'textures':['Texture.default'],'part_visibility':visible}
    return {'format_version':'1.8.0','render_controllers':result}


def configure_animations(document):
    d=copy.deepcopy(document);a=d['animations']
    a['animation.tf_slice.block_chain_goblin.move']['bones']['chain_0']['scale']="query.property('tf_slice:chain_external') ? 0.0 : 1.0"
    upper=a['animation.tf_slice.upper_goblin_knight.move']['bones']
    t="(60.0 - query.property('tf_slice:spear_timer'))"
    arm="(%s <= 10 ? %s : (%s <= 30 ? 10 : (%s <= 33 ? (%s - 30) * -8 + 10 : (%s <= 50 ? -15 : (60 - %s) * -1.5))))" % ((t,)*7)
    pitch="(%s <= 10 ? %s * 3 : (%s <= 30 ? 30 : (%s <= 33 ? (%s - 30) * -25 + 30 : (%s <= 50 ? -45 : (60 - %s) * -4.5))))" % ((t,)*7)
    walk="math.cos(query.modified_distance_moved * 38.1709) * query.modified_move_speed"
    upper['root']={'rotation':[pitch,0,0]}
    upper['right_arm']={'rotation':["-136.8 - (query.is_riding ? 18 : 0) - %s * 28.6479 - %s + math.sin(query.life_time * 76.7763) * 2.8648"%(walk,arm),0,"math.cos(query.life_time * 103.1324) * 2.8648 + 2.8648"]}
    left="math.cos(query.modified_distance_moved * 38.1709) * (query.property('tf_slice:has_shield') ? 0.2 : query.modified_move_speed) * 57.2958 - (query.is_riding ? 36 : 0)"
    upper['left_arm']={'rotation':[left,0,"query.property('tf_slice:shield_disabled') ? 22.9183 - math.cos(query.life_time * 3724.2257) * 1.2566 : math.cos(query.life_time * 103.1324) * 2.8648 + 2.8648"]}
    # The geometry has a baked 90-degree shield pitch; subtract it so the
    # total world pitch cancels the arm instead of double-rotating the shield.
    upper['shield']={'rotation':["270 - (%s)"%left,0,0]}
    for leg in ('right_leg','left_leg'):
        expr=upper[leg]['rotation'][0];upper[leg]['rotation'][0]='query.is_riding ? 0 : (%s)'%expr
    return d


def visual_documents(spike_geometry):
    result={}
    for kind in ('goblin_spike','goblin_chain_link'):
        ident='tf_slice:'+kind
        result['TwilightBossSliceB/entities/'+kind+'.entity.json']={'format_version':'1.20.60','minecraft:entity':{
            'description':{'identifier':ident,'is_spawnable':False,'is_summonable':False,'is_experimental':False},
            'components':{'minecraft:type_family':{'family':['goblin_visual']},'minecraft:collision_box':{'width':0.01,'height':0.01},'minecraft:physics':{'has_gravity':False,'has_collision':False},'minecraft:damage_sensor':{'triggers':[{'cause':'all','deals_damage':False}]},'minecraft:pushable':{'is_pushable':False,'is_pushable_by_piston':False}},
            'component_groups':{'tf_slice:instant_remove':{'minecraft:instant_despawn':{}},'tf_slice:visual_lease':{'minecraft:timer':{'time':3.0,'looping':False,'time_down_event':{'event':'tf_slice:instant_remove','target':'self'}}}},
            'events':{'tf_slice:instant_remove':{'add':{'component_groups':['tf_slice:instant_remove']}},'tf_slice:keep_alive':{'add':{'component_groups':['tf_slice:visual_lease']}},'minecraft:entity_spawned':{'add':{'component_groups':['tf_slice:visual_lease']}}}}}
        result['TwilightBossSliceR/entity/'+kind+'.entity.json']={'format_version':'1.10.0','minecraft:client_entity':{'description':{
            'identifier':ident,'materials':{'default':'entity_alphatest'},'textures':{'default':'textures/entity/tf_slice/block_chain_goblin'},'geometry':{'default':'geometry.tf_slice.'+kind},'render_controllers':['controller.render.default']}}}
    spike=[]
    for b in spike_geometry['bones']:
        if b['name']=='flail' or b.get('parent')=='flail':
            for cube in b.get('cubes',[]):
                c=copy.deepcopy(cube);c['origin']=[c['origin'][0],c['origin'][1]-14,c['origin'][2]+16];spike.append(c)
    entries=[]
    for kind,cubes in [('goblin_spike',spike),('goblin_chain_link',[{'origin':[-0.5,-0.5,-2],'size':[1,1,4],'uv':[0,0]}])]:
        entries.append({'description':{'identifier':'geometry.tf_slice.'+kind,'texture_width':64,'texture_height':32,'visible_bounds_width':2,'visible_bounds_height':2,'visible_bounds_offset':[0,0,0]},'bones':[{'name':'root','pivot':[0,0,0],'cubes':cubes}]})
    result['TwilightBossSliceR/models/entity/goblin_parts.geo.json']={'format_version':'1.12.0','minecraft:geometry':entries}
    result['TwilightBossSliceR/render_controllers/goblin_combat.render.json']=render_controllers()
    return result
