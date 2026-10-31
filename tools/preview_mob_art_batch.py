"""Actual geometry/UV before-after gallery; offline and explicitly not client proof."""
import argparse,copy,html,json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
try:
    import render_entity_geo_preview as renderer
except ImportError:
    from tools import render_entity_geo_preview as renderer
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
FONT=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)


def framed(bones,other,texture):
    points=[]
    for model in [bones,other]:
        lookup={b['name']:b for b in model}
        for b in model:
            for c in b.get('cubes',[]):
                points.extend(renderer.transformed_point(p,b['name'],lookup,{}) for p in renderer.cube_vertices(c))
    lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
    # An extra transparent texel and framing cube exist only in the preview.
    padded=Image.new('RGBA',(texture.width+1,texture.height));padded.paste(texture,(0,0))
    anchor={'name':'preview_frame','pivot':[0,0,0],'cubes':[{'origin':lo,'size':[hi[i]-lo[i] for i in range(3)],'uv':{f:{'uv':[texture.width,0],'uv_size':[1,1]} for f in ['north','south','east','west','up','down']}}]}
    return copy.deepcopy(bones)+[anchor],padded


def pair(old,new,textures,title,yaw=35,pitch=-15,width=900,height=470):
    board=Image.new('RGBA',(width,height),(23,27,33,255));draw=ImageDraw.Draw(board);draw.font=FONT
    draw.text((12,8),title+'  |  Original / Art draft',fill='white')
    for col,(bones,other,texture) in enumerate([(old,new,textures[0]),(new,old,textures[1])]):
        framed_bones,padded=framed(bones,other,texture)
        renderer.render_view(draw,(8+col*(width//2),37,(col+1)*(width//2)-8,height-8),'Original' if col==0 else 'Art draft',framed_bones,{},yaw,pitch,padded,max_texture_samples=32)
    return board


def run(task,draft=False):
    task=Path(task);rp=ROOT/'TwilightBossSliceR';bank=ROOT/'resource_art/entity_beautification/v1';sources=read(bank/'mob_batch_sources.json')
    out=task/('model-review' if draft else 'gallery');out.mkdir(exist_ok=True)
    registry=read(bank/'manifest.json')['entities'];cards=[];thumbs=[]
    for name,entry in sources['entities'].items():
        identifier=entry['geometry_sources']['default'];old=read(bank/sources['geometries'][identifier]['baseline'])['minecraft:geometry'][0]
        new=read(task/'model-drafts'/(name+'_default.json')) if draft else read(rp/registry['tf_slice:'+name]['geometry_paths']['default'])['minecraft:geometry'][0]
        key=next(iter(entry['texture_keys'].values()));original=Image.open(bank/sources['textures'][key]['baseline']).convert('RGBA')
        new_texture=task/'exports'/(key+'.png')
        enhanced=Image.open(new_texture).convert('RGBA') if not draft and new_texture.exists() else original
        board=pair(old['bones'],new['bones'],[original,enhanced],name);board.save(out/(name+'.png'))
        thumbs.append(board.resize((450,235)))
        if not draft:
            views=Image.new('RGBA',(1350,810),(23,27,33,255))
            for index,(label,yaw,pitch) in enumerate([('front',0,-10),('back',180,-10),('left',90,-10),('right',-90,-10),('top',0,-90),('three-quarter',35,-15)]):
                panel=pair(old['bones'],new['bones'],[original,enhanced],label,yaw,pitch,450,405)
                views.paste(panel,((index%3)*450,(index//3)*405))
            views.save(out/(name+'-views.png'))
        cards.append('<article><h2>'+html.escape(name)+'</h2><img loading="lazy" src="'+name+'.png"><details><summary>Six views / 六视图</summary><img loading="lazy" src="'+name+'-views.png"></details></article>')
    for start in range(0,len(thumbs),8):
        page=Image.new('RGBA',(900,4*235),(23,27,33,255))
        for i,thumb in enumerate(thumbs[start:start+8]):page.paste(thumb,((i%2)*450,(i//2)*235))
        page.save(out/('overview-%02d.png'%(start//8+1)))
    page='<!doctype html><meta charset="utf-8"><title>暮色生物美术对比</title><style>body{background:#151920;color:#edf2f6;font:16px system-ui;margin:32px}main{max-width:1200px;margin:auto}article{margin:32px 0;padding:18px;background:#232b35;border-radius:12px}img{max-width:100%;height:auto}summary{cursor:pointer}h1{font-size:28px}p{color:#b9c5d1}</style><main><h1>暮色森林 · 生物美术对比</h1><p>左原稿，右美化稿；实际模型和原尺寸贴图，使用相同镜头与尺度。以下为离线预览，游戏内效果待验收。</p>'+''.join(cards)+'</main>'
    (out/'index.html').write_text(page,encoding='utf-8');print(str(out/'index.html'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--task',type=Path,required=True);p.add_argument('--draft',action='store_true');args=p.parse_args();run(args.task,args.draft)
