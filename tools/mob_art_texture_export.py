"""Extract ImageGen interior pixels while preserving native UV/alpha/face data."""
import argparse
import hashlib
import json
import math
import re
import shutil
from pathlib import Path


def source_baseline(path):
    try:
        from retired_runtime_pngs import original_texture
    except ImportError:
        from tools.retired_runtime_pngs import original_texture
    return original_texture(path, Path(__file__).resolve().parents[1])
import numpy as np
from PIL import Image,ImageFilter


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected_mask(texture, inventory):
    image=np.asarray(Image.open(source_baseline(texture['source'])).convert('RGBA'))
    height,width=image.shape[:2]
    mask=np.zeros((height,width),dtype=bool)
    rgb=image[:,:,:3].astype(int)
    # Pure UV marker colors are debugging/layout data, never material detail.
    mask |= ((rgb.max(2)>=240)&(rgb.min(2)<=12)&((rgb<=12).sum(2)>=2))
    if texture['key'] in ['nagahead','nagahead_charging','tf_slice__mini_ghast','tf_slice__tower_ghast']:
        # These cube-bodied mobs store their face in the body, not a head bone.
        mask[16:32,16:32]=True
        return mask
    for name in texture['entities']:
        entity=inventory['entities'][name]
        for record in entity['geometries'].values():
            geometry=record['geometry'];desc=geometry['description']
            sx=width/desc['texture_width'];sy=height/desc['texture_height']
            for bone in geometry['bones']:
                if not any(token in bone['name'].lower() for token in ['head','eye','beak','snout','mouth','jaw','face']):continue
                for cube in bone.get('cubes',[]):
                    uv=cube.get('uv',[0,0]);rects=[]
                    if isinstance(uv,dict):
                        for face in uv.values():
                            if isinstance(face,dict):
                                u,v=face['uv'];w,h=face.get('uv_size',[1,1]);rects.append((u,v,u+w,v+h))
                    else:
                        u,v=uv;x,y,z=cube['size'];rects=[(u,v,u+2*x+2*z,v+y+z)]
                    for x0,y0,x1,y1 in rects:
                        left=max(0,math.floor(min(x0,x1)*sx));right=min(width,math.ceil(max(x0,x1)*sx))
                        top=max(0,math.floor(min(y0,y1)*sy));bottom=min(height,math.ceil(max(y0,y1)*sy))
                        mask[top:bottom,left:right]=True
    return mask


def extract(source, generated, protected):
    original=np.asarray(source.convert('RGBA'));size=source.size
    candidate=np.asarray(generated.convert('RGBA').resize(size,Image.Resampling.NEAREST))
    interior=np.asarray(source.convert('RGBA').getchannel('A').filter(ImageFilter.MinFilter(3)))==255
    a=original[:,:,:3].astype(float);b=candidate[:,:,:3].astype(float)
    la=a.mean(2);lb=b.mean(2)
    eligible=interior & ~protected & (candidate[:,:,3]>=240) & (la>=12)
    eligible &= (lb>=np.maximum(5,la*.6)) & (lb<=la*1.6+12)
    eligible &= (np.abs(a-b).max(2)<=70)
    # Keep strong color families; allow neutral coat and bone variation.
    chroma=a.max(2)-a.min(2)
    eligible &= ((chroma<35)|(a.argmax(2)==b.argmax(2)))
    result=original.copy();result[eligible,:3]=candidate[eligible,:3]
    changed=(result!=original).any(2)
    if not changed.any():raise ValueError('No valid generated interior detail survives the UV/face locks')
    assert not changed[protected].any()
    assert np.array_equal(result[:,:,3],original[:,:,3])
    return Image.fromarray(result),int(changed.sum()),int(eligible.sum())


def export(task):
    task=Path(task);inventory=read(task/'inventory.json');records={}
    first=task/'generation-01.json'
    if first.exists():records.update(read(first))
    for p in (task/'generation').glob('*.json'):
        value=read(p);records[value['key']]=value
    for p in sorted((task/'generation-retries').glob('*.json')):
        value=read(p);records[value['key']]=value
    output=task/'exports';output.mkdir(exist_ok=True)
    generated_dir=task/'generated';generated_dir.mkdir(exist_ok=True)
    report={};failures={}
    for key,record in records.items():
        if key not in inventory['textures']:continue
        texture=inventory['textures'][key]
        match=re.search(r' as (.+?\.png) by default',record['output_hint'])
        if not match:raise ValueError('Missing generator output path for '+key)
        generated=Path(match.group(1));saved=generated_dir/(key+('-retry' if record.get('retry') else '')+'.png')
        if not saved.exists():shutil.copy2(generated,saved)
        with Image.open(source_baseline(texture['source'])) as original,Image.open(saved) as draft:
            if key=='minoshroomtaur':
                # A 128x32 atlas occupies the upper half of its 128x64 edit canvas.
                draft=draft.crop((0,0,draft.width,draft.height//2))
            try:
                result,changed,eligible=extract(original,draft,protected_mask(texture,inventory))
                result.save(output/(key+'.png'))
                report[key]={'changed_pixels':changed,'eligible_pixels':eligible,'size':list(result.size),'source_sha256':texture['sha256'],'generated_sha256':sha(saved),'output_sha256':sha(output/(key+'.png'))}
            except ValueError as error:failures[key]=str(error)
    # State textures reuse exactly equal source pixels only. Changed expression
    # pixels remain original, so sleeping/open/attack faces cannot be flattened.
    derivatives={
        'nagahead_charging':'nagahead',
        'tf_slice__upper_goblin_knight':'tf_slice__lower_goblin_knight',
        'tf_slice__mini_ghast_open':'tf_slice__mini_ghast','tf_slice__mini_ghast_attack':'tf_slice__mini_ghast',
        'tf_slice__tower_ghast':'tf_slice__mini_ghast','tf_slice__tower_ghast_open':'tf_slice__mini_ghast','tf_slice__tower_ghast_attack':'tf_slice__mini_ghast',
    }
    for key,base in derivatives.items():
        if key not in inventory['textures']:continue
        if base not in report:continue
        source=np.asarray(Image.open(source_baseline(inventory['textures'][key]['source'])).convert('RGBA'))
        baseline=np.asarray(Image.open(source_baseline(inventory['textures'][base]['source'])).convert('RGBA'))
        enhanced=np.asarray(Image.open(output/(base+'.png')).convert('RGBA'))
        same=(source==baseline).all(2);result=source.copy();result[same]=enhanced[same]
        assert np.array_equal(source[:,:,3],result[:,:,3])
        changed=int((source!=result).any(2).sum())
        if not changed:failures[key]='No common generated detail';continue
        Image.fromarray(result).save(output/(key+'.png'))
        report[key]={'derived_from':base,'method':'exact original RGBA equality only; state-specific texels preserved','changed_pixels':changed,'size':list(Image.open(output/(key+'.png')).size),'source_sha256':inventory['textures'][key]['sha256'],'output_sha256':sha(output/(key+'.png'))}
    # The upstream closed-eye overlay is state data, not a coat texture.
    key='nagahead_dazed'
    shutil.copy2(source_baseline(inventory['textures'][key]['source']),output/(key+'.png'))
    report[key]={'preserved_state_overlay':True,'changed_pixels':0,'size':inventory['textures'][key]['size'],'source_sha256':inventory['textures'][key]['sha256'],'output_sha256':sha(output/(key+'.png'))}
    (task/'texture-export.json').write_text(json.dumps({'entries':report,'failures':failures,'missing':sorted(set(inventory['textures'])-set(report))},indent=2),encoding='utf-8')
    print(json.dumps({'exported':len(report),'expected':len(inventory['textures']),'failures':failures,'missing':sorted(set(inventory['textures'])-set(report))}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--task',type=Path,required=True);args=parser.parse_args();export(args.task)
