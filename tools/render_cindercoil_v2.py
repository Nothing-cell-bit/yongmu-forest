"""Offline full-resolution views of actual Cindercoil geometry and UV files."""
import argparse
import copy
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw
import render_entity_geo_preview as base


def load(root):
    rp=Path(root)/'TwilightBossSliceR'
    head=json.loads((rp/'models/entity/forest_wyrm.geo.json').read_text())['minecraft:geometry']
    segment=json.loads((rp/'models/entity/forest_wyrm_segment.geo.json').read_text())['minecraft:geometry']
    textures=[Image.open(rp/'textures/entity'/name).convert('RGBA') for name in
              ('nagahead.png','nagasegment.png','nagahead_dazed.png','nagahead_charging.png')]
    return head,segment,textures


def render(root,output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    head,segment,tex=load(root)
    sheet=Image.new('RGB',(1800,1180),(18,20,25)); draw=ImageDraw.Draw(sheet)
    views=[((8,8,600,580),'FRONT',head[0]['bones'],0,0,tex[0],None),
           ((604,8,1792,580),'HEAD / THREE QUARTER',head[0]['bones'],38,-16,tex[0],None),
           ((8,588,600,1172),'SIDE',head[0]['bones'],-90,0,tex[0],None),
           ((604,588,1194,1172),'DAZED / EYELIDS',head[0]['bones'],28,-10,tex[0],[(head[1]['bones'],{},tex[2])]),
           ((1200,588,1792,1172),'BODY / OCTAGONAL RING',segment[0]['bones'],32,-19,tex[1],None)]
    for panel,label,bones,yaw,pitch,texture,overlay in views:
        base.render_view(draw,panel,label,bones,{},yaw,pitch,texture,overlay_layers=overlay,max_texture_samples=32)
    sheet.save(output/'model_details.png')
    # Illustrative chain pose using ONLY packaged meshes, no AI render or extra tail.
    chain=[]
    points=[(0,0,0)]
    for i in range(1,10):
        previous=points[-1]; tangent=math.radians(48*math.sin((i-1)*.62))
        points.append((previous[0]+16*math.sin(tangent),0,previous[2]+16*math.cos(tangent)))
    for i,(x,y,z) in enumerate(points[1:]):
        role=2 if i==8 else 1 if i==7 else 0
        bones=copy.deepcopy(segment[role]['bones']); prefix='s%d_'%i
        for b in bones:
            b['name']=prefix+b['name']
            b['parent']=prefix+b['parent'] if b.get('parent') else prefix+'pose'
        # The local +Z axis points away from the preceding segment.
        # Derive its yaw from the same displacement used to place this segment.
        previous=points[i]
        yaw=math.degrees(math.atan2(x-previous[0],z-previous[2]))
        bones.insert(0,{'name':prefix+'pose','pivot':[0,0,0]})
        pose={prefix+'pose':{'rotation':[0,yaw,0],'position':[x,y,z]}}
        chain.append((bones,pose,tex[1]))
    image=Image.new('RGB',(2000,780),(18,20,25))
    base.render_view(ImageDraw.Draw(image),(8,8,1992,772),'CINDERCOIL / ACTUAL BEDROCK MESH / ASSEMBLED POSE',
                     head[0]['bones'],{},65,-24,tex[0],overlay_layers=chain,max_texture_samples=24)
    image.save(output/'full_model.png')


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();render(args.root,args.output)
