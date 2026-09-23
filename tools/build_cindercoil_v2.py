"""Code-native Bedrock mesh and UV atlas for the Cindercoil redesign.

All dimensions and pixel patterns are authored here; no upstream asset inputs.
Run --output-root in an isolated directory to review before promotion.
"""
import argparse
import copy
import json
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw

TILE = 32
MATERIALS = {
    'stone': 0, 'scale': 1, 'patina': 2, 'copper': 3,
    'ivory': 4, 'eye': 5, 'lid': 6, 'crack': 7,
    'band': 8, 'seal': 9, 'dark': 10, 'ember': 11,
    'fin': 12, 'belly': 13, 'gold': 14, 'crystal': 15,
}
PALETTES = {
    'stone': (28, 28, 43), 'scale': (36, 36, 53),
    'patina': (49, 98, 92), 'copper': (152, 88, 46),
    'ivory': (218, 204, 168), 'dark': (16, 17, 25),
    'ember': (255, 158, 34), 'gold': (202, 134, 60),
}


def tile_xy(material):
    index = MATERIALS[material]
    return index % 4 * TILE, index // 4 * TILE


def texture_tile(material, charging=False, seed=73):
    base = PALETTES.get(material, PALETTES['stone'])
    if material in ('band', 'seal', 'fin', 'lid'):
        base = PALETTES['patina']
    if material in ('eye', 'crystal'):
        base = PALETTES['ember']
    rng = random.Random(seed + MATERIALS[material] * 381)
    tile = Image.new('RGBA', (TILE, TILE), base + (255,))
    pixels = tile.load()
    for y in range(TILE):
        for x in range(TILE):
            # Quiet stone variation at one texel scale, not giant checkerboards.
            noise = rng.randint(-9, 9)
            pixels[x, y] = tuple(max(0, min(255, c + noise)) for c in base) + (255,)
    d = ImageDraw.Draw(tile)
    if material in ('stone', 'scale', 'crack', 'fin'):
        for row in range(4):
            for col in range(5):
                x = col * 8 - (4 if row % 2 else 0); y = row * 8
                d.line([(x,y+1),(x+6,y+1),(x+7,y+6)], fill=(50,49,65,255))
                d.line([(x,y+7),(x+7,y+7)], fill=(18,20,29,255))
    if material in ('crack', 'crystal'):
        color = (255,224,114,255) if charging else (248,160,44,255)
        path = [(2,7),(6,9),(10,8),(14,12),(19,12),(22,17),(29,18)]
        d.line(path, fill=(117,57,28,255), width=3)
        d.line(path, fill=color, width=1)
        d.line([(14,12),(13,18),(17,23)], fill=color, width=1)
    if material in ('patina', 'band', 'seal', 'fin'):
        for _ in range(35):
            x,y=rng.randrange(30),rng.randrange(30)
            d.rectangle((x,y,x+1,y+1), fill=(74,124,111,255))
        if material in ('band', 'seal', 'fin'):
            d.rectangle((0,0,31,31), outline=(90,55,35,255), width=2)
            d.rectangle((2,2,29,29), outline=(182,111,60,255), width=1)
        if material == 'seal':
            d.rectangle((8,8,23,23), fill=(20,42,43,255), outline=(189,127,68,255), width=2)
            d.rectangle((12,12,19,19), outline=(86,148,131,255), width=2)
        if material == 'band':
            for y in (8,23):
                d.line([(5,y),(26,y)], fill=(30,65,62,255))
            for x,y in ((5,5),(26,5),(5,26),(26,26)):
                d.point((x,y), fill=(228,170,93,255))
    if material == 'ivory':
        for x in range(3,32,5):
            d.line([(x,1),(x-1,15),(x,30)], fill=(179,162,128,255))
    if material == 'eye':
        d.rectangle((0,0,31,31), fill=(86,35,15,255))
        d.polygon([(1,21),(12,8),(30,5),(25,23),(11,27)], fill=(255,168,35,255))
        d.polygon([(7,20),(15,10),(27,8),(21,22)], fill=(255,229,133,255))
        d.rectangle((17,10,19,24), fill=(255,255,220,255) if charging else (54,30,21,255))
    if material == 'lid':
        d.line([(0,17),(12,23),(31,13)], fill=(14,25,29,255), width=3)
        d.line([(0,20),(12,26),(31,16)], fill=(169,106,56,255), width=1)
    if material == 'crystal':
        d.rectangle((0,0,31,31), fill=(211,99,15,255))
        d.polygon([(0,1),(9,8),(31,4),(27,0)], fill=(255,229,136,255))
        d.polygon([(0,1),(9,8),(12,26),(0,31)], fill=(248,163,41,255))
        d.polygon([(9,8),(31,4),(29,20),(12,26)], fill=(255,191,67,255))
        d.line([(0,1),(9,8),(12,26),(31,30)], fill=(255,243,174,255),width=1)
    if material == 'belly':
        for y in range(0,32,8):
            d.line((0,y,31,y), fill=(93,72,50,255), width=2)
    return tile


def build_textures(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    def atlas(charging=False, seed=73):
        image=Image.new('RGBA',(128,128))
        for material in MATERIALS:
            image.paste(texture_tile(material,charging,seed), tile_xy(material))
        return image
    normal=atlas(); charge=atlas(True)
    lids=Image.new('RGBA',(128,128),(0,0,0,0))
    lids.paste(texture_tile('lid'),tile_xy('lid'))
    full=normal.copy(); full.paste(texture_tile('lid'),tile_xy('eye'))
    for name,image in [('nagahead',normal),('nagahead_charging',charge),
                       ('nagahead_dazed',lids),('nagahead_dazed_full',full),
                       ('nagasegment',atlas(seed=149))]:
        image.save(output/(name+'.png'),compress_level=9)


def cube(origin, size, material, faces=None):
    uv={}
    # Match texel density to face dimensions and stay inside one material tile.
    dims={'north':(size[0],size[1]),'south':(size[0],size[1]),
          'east':(size[2],size[1]),'west':(size[2],size[1]),
          'up':(size[0],size[2]),'down':(size[0],size[2])}
    for face,(w,h) in dims.items():
        mat=(faces or {}).get(face,material)
        if mat in ('eye','lid','seal','crack','crystal'):
            w,h=32,32
        else:
            w,h=min(32,max(2,round(w*2))),min(32,max(2,round(h*2)))
        uv[face]={'uv':list(tile_xy(mat)), 'uv_size':[w,h]}
    return {'origin':origin,'size':size,'uv':uv}


def bone(name, cubes=(), parent='head', pivot=(0,9,0), rotation=None):
    item={'name':name,'pivot':list(pivot),'cubes':list(cubes)}
    if parent: item['parent']=parent
    if rotation: item['rotation']=rotation
    return item


def geometry(identifier,bones):
    return {'description':{'identifier':identifier,'texture_width':128,'texture_height':128,
                          'visible_bounds_width':6,'visible_bounds_height':6,
                          'visible_bounds_offset':[0,1.8,0]},'bones':bones}


def head_geometry():
    bones=[bone('head',[
        cube([-6,5,-5],[12,10,12],'scale'),
        cube([-5,4,-8],[10,9,14],'stone'),
        cube([-4.5,3,-12],[9,5.5,8],'stone'),
        cube([-4,3.4,-16],[8,4,6],'scale'),
        cube([-4,1.9,-15.8],[8,1.1,10],'dark'),
        cube([-3.7,1.3,-15.5],[7.4,1,9],'stone'),
        cube([-5.4,2.3,-7],[10.8,1.5,10],'stone'),
    ],parent=None)]
    # Sloped forehead with the metal band following the slope, not floating.
    bones.append(bone('mask',[
        cube([-4.8,12.4,-8],[9.6,2,12],'scale'),
        cube([-1.7,14.4,-8],[3.4,.6,12],'band'),
        cube([-1,15,-3],[2,.4,2],'seal'),
    ],pivot=(0,12.4,3),rotation=[23,0,0]))
    bones.append(bone('nose_crest',[
        cube([-1.4,7.5,-15.7],[2.8,.5,6.4],'band'),
        cube([-2.6,7.1,-15.8],[5.2,.35,1.5],'copper'),
    ]))
    # Cheek planes, almond-shaped eye apertures, heavy brows.
    for side,label in ((1,'left'),(-1,'right')):
        x=side*5.15
        bones.append(bone('cheek_'+label,[cube([x-1.4,5.4,-7.8],[2.8,5.8,9],'crack')],
                          pivot=(x,8,-3),rotation=[0,side*13,side*9]))
        # Eye front sits between snout and cheek, sloping down toward nose.
        eye_x=1.65 if side==1 else -5.05
        bones.append(bone('eye_'+label,[cube([eye_x,8.2,-8.45],[3.4,1.55,.45],'eye')],
                          pivot=(side*3.35,9,-8.3),rotation=[0,side*-16,side*17]))
        bones.append(bone('brow_'+label,[
            cube([eye_x-.35,9.6,-8.8],[4.2,1.25,1.8],'stone'),
            cube([eye_x-.4,10.75,-8.7],[4.3,.25,1.4],'copper'),
        ],pivot=(side*3.35,9,-8.3),rotation=[0,side*-16,side*17]))
        # Tapering backward-curved horns, copper socket and ivory facets.
        hx=side*4.45
        pieces=[cube([hx-1.8,13.4,-1.3],[3.6,1.9,3.6],'band'),
                cube([hx-1.35,15.3,-.9],[2.7,2.8,2.7],'ivory'),
                cube([hx-1.05,17.8,-.3],[2.1,2.6,2.1],'ivory'),
                cube([hx-.7,20,0.2],[1.4,2.1,1.4],'ivory'),
                cube([hx-.35,21.8,0.8],[.7,1.8,.7],'ivory')]
        bones.append(bone('horn_'+label,pieces,pivot=(hx,14,0),rotation=[-15,0,side*-12]))
        # Three swept, stepped mineral fins per side. Tips narrow backward.
        for i in range(3):
            cx=side*5.4; cy=6+i*4.1
            fin=[]
            for j,(height,length) in enumerate(((3.6,9),(2.6,3),(1.6,2),(.7,1.8))):
                z=(0,9,12,14)[j]
                fin.append(cube([cx-.65,cy+(.5*j),z],[1.3,height,length],'scale'))
                fin.append(cube([cx-.7,cy+(.5*j)+height-.18,z],[1.4,.25,length],'copper'))
                fin.append(cube([cx-.72,cy+(.5*j)+.5,z],[.14,max(.3,height-1),length],'patina'))
                fin.append(cube([cx+.58,cy+(.5*j)+.5,z],[.14,max(.3,height-1),length],'patina'))
            bones.append(bone(('fin_'+label) if i==0 else ('fin_'+label+'_'+str(i)),fin,
                              pivot=(cx,cy,0),rotation=[-9+i*3,side*30,side*(-45+i*7)]))
        # Short engraved chin pendants with real supporting attachments.
        px=side*2.65
        bones.append(bone('charm_'+label,[
            cube([px-.55,1.1,-12.8],[1.1,1,1.1],'copper'),
            cube([px-.55,.35,-12.6],[1.1,1.4,.7],'band'),
            cube([px-.65,.2,-12.7],[1.3,.35,.9],'gold'),
        ]))
    # Compact nostrils and copper jaw seam.
    for x in (-2.5,1.65):
        bones.append(bone('nostril_'+str(x),[cube([x,5.7,-16.08],[.85,.5,.18],'dark')]))
    bones.append(bone('jaw_trim',[
        cube([-3.8,2.8,-16.05],[7.6,.25,.18],'copper'),
        cube([-4.08,2.8,-15.9],[.18,.25,8.2],'copper'),
        cube([3.9,2.8,-15.9],[.18,.25,8.2],'copper'),
    ]))
    lids=[bone('head',parent=None)]
    for side,label in ((1,'left'),(-1,'right')):
        eye_x=1.65 if side==1 else -5.05
        c=cube([eye_x,8.2,-8.49],[3.4,1.55,.47],'lid'); c['inflate']=.02
        lids.append(bone('eyelid_'+label,[c],pivot=(side*3.35,9,-8.3),rotation=[0,side*-16,side*17]))
    return {'format_version':'1.12.0','minecraft:geometry':[
        geometry('geometry.tf_slice.forest_wyrm',bones),
        geometry('geometry.tf_slice.forest_wyrm_eyelids',lids)]}


def segment_geometry():
    bones=[bone('segment',[
        cube([-6.9,4,-6.8],[13.8,8,13.6],'stone'),
        cube([-4.8,1.9,-6.8],[9.6,12.2,13.6],'scale'),
        cube([-6,2.8,-6.5],[12,10.4,13],'scale'),
    ],parent=None,pivot=(0,8,0))]
    # Eight chamfer planes create an octagonal body and continuous metal belt.
    for i in range(8):
        angle=i*45
        name='segment_ring' if i==0 else 'segment_ring_'+str(i)
        bones.append(bone(name,[
            cube([-2.95,14.25,-6.3],[5.9,.8,12.6],'crack' if i in (1,3,5) else 'scale'),
            cube([-3.18,14.9,-1.9],[6.36,.75,3.8],'band'),
            cube([-3.22,14.9,-2.1],[6.44,.9,.35],'copper'),
            cube([-3.22,14.9,1.75],[6.44,.9,.35],'copper'),
        ],parent='segment',pivot=(0,8,0),rotation=[0,0,angle]))
    for side in (-1,1):
        bones.append(bone('buckle_'+str(side),[
            cube([-1.45,15.7,-1.4],[2.9,.38,2.8],'seal')
        ],parent='segment',pivot=(0,8,0),rotation=[0,0,90*side]))
    taper=copy.deepcopy(bones)
    for b in taper:
        b['pivot']=[b['pivot'][0]*.76,8+(b['pivot'][1]-8)*.76,b['pivot'][2]]
        for c in b['cubes']:
            c['origin']=[c['origin'][0]*.76,8+(c['origin'][1]-8)*.76,c['origin'][2]]
            c['size']=[c['size'][0]*.76,c['size'][1]*.76,c['size'][2]]
    tail=[bone('segment',[
        cube([-3.6,4.4,-7],[7.2,7.2,7],'scale'),
        cube([-4,4,-4],[8,8,2.2],'band'),
        cube([-3.2,4.8,-.5],[6.4,6.4,5],'crystal'),
        cube([-2.7,5.3,4],[5.4,5.4,4],'crystal'),
        cube([-2,6,7.5],[4,4,3],'crystal'),
        cube([-1.3,6.7,10],[2.6,2.6,2.5],'crystal'),
        cube([-.65,7.35,12],[1.3,1.3,2],'ember'),
        cube([-.25,7.75,13.5],[.5,.5,1.5],'ember'),
    ],parent=None,pivot=(0,8,0))]
    return {'format_version':'1.12.0','minecraft:geometry':[
        geometry('geometry.tf_slice.forest_wyrm_segment',bones),
        geometry('geometry.tf_slice.forest_wyrm_segment_taper',taper),
        geometry('geometry.tf_slice.forest_wyrm_segment_tail',tail)]}


def write_json(path, document):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def build(root):
    rp=Path(root)/'TwilightBossSliceR'
    build_textures(rp/'textures/entity')
    write_json(rp/'models/entity/forest_wyrm.geo.json',head_geometry())
    write_json(rp/'models/entity/forest_wyrm_segment.geo.json',segment_geometry())


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-root',type=Path,required=True)
    build(parser.parse_args().output_root)
