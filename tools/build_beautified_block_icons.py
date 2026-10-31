"""Bake the eight existing inventory models with approved block-art materials.

Output must be explicitly supplied; this tool never rebuilds gameplay blocks,
structures, or installed packs.
"""
from pathlib import Path
import hashlib
import json
import argparse
from PIL import Image

try:
    import build_public_block_shapes as blocks
    import block_texture_beautification as art
except ImportError:
    from tools import build_public_block_shapes as blocks,block_texture_beautification as art

ROOT=Path(__file__).resolve().parents[1]
NAMES=('canopy_bookshelf','canopy_chest','hollow_dark_log_horizontal','hollow_dark_log_vertical','hollow_dark_log_climbable','hollow_mangrove_log_horizontal','hollow_mangrove_log_vertical','hollow_mangrove_log_climbable')


def build(project_root, output_root):
    bank,registry=art.registry(project_root)
    output_root=Path(output_root)
    output_root.mkdir(parents=True,exist_ok=True)
    receipts=[]
    for name in NAMES:
        target=output_root/(name+'.png')
        original=ROOT/'TwilightBossSliceR/textures/blocks/item_icons'/(name+'.png')
        try:
            from retired_runtime_pngs import original_texture
        except ImportError:
            from tools.retired_runtime_pngs import original_texture
        original=original_texture(original,project_root)
        if name.startswith('canopy_'):
            rendered=blocks._render_java_item_model_icon(name,target,texture_resolver=lambda p:art.resolve_source_texture(p,project_root))
            if not rendered:
                suffix=name.split('_',1)[1]
                blocks._render_geometry_item_icon(blocks.canopy_world_geometry(suffix),bank/'assets/blocks/canopy_planks.png',target)
        else:
            family='dark' if '_dark_' in name else 'mangrove'
            kind=name.rsplit('_',1)[1]
            blocks._render_geometry_item_icon(blocks._geometry_by_identifier('geometry.tf_slice.hollow_log_'+kind),bank/'assets/blocks'/(family+'_log.png'),target)
        with Image.open(original) as old,Image.open(target) as image:
            if image.size!=old.size or image.size!=(64,64) or image.getchannel('A').getbbox() is None:
                raise ValueError('Incorrect derived icon dimensions or empty geometry: '+name)
        receipts.append({'name':name,'path':target.as_posix(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'size':[64,64]})
    return receipts


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--project-root',type=Path,required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.project_root,args.output_root),indent=2))
