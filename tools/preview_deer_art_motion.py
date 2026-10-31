"""Offline mesh motion from live deer animation expressions, never client proof."""
import argparse
import ast
import copy
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
try:
    import render_entity_geo_preview as renderer
except ImportError:
    from tools import render_entity_geo_preview as renderer

ROOT = Path(__file__).resolve().parents[1]


def evaluate_rotation(rotation, life_time, distance, speed):
    """Independent reader of the limited math/query subset used by this draft."""
    queries = {"life_time":life_time,"modified_distance_moved":distance,"modified_move_speed":speed}
    functions = {"sin":lambda x:math.sin(math.radians(x)),
                 "cos":lambda x:math.cos(math.radians(x)), "pow":pow,
                 "max":max, "clamp":lambda x,a,b:min(max(x,a),b)}

    def evaluate(node):
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)):
            return node.value
        if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id == "query":
            return queries[node.attr]
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):
            return -evaluate(node.operand)
        if isinstance(node,ast.BinOp):
            a,b=evaluate(node.left),evaluate(node.right)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id == "math" and not node.keywords:
            return functions[node.func.attr](*(evaluate(arg) for arg in node.args))
        raise ValueError("Unsupported preview expression: "+ast.dump(node))

    return [evaluate(ast.parse(value,mode="eval").body) if isinstance(value,str) else value for value in rotation]


def sample_keyframes(channel, time, length):
    if not isinstance(channel,dict) or length <= 0:
        raise ValueError("Offline playback requires explicit numeric keyframes and duration")
    frames=sorted((float(t),value) for t,value in channel.items())
    if any(len(value)!=3 or any(not isinstance(v,(int,float)) for v in value) for _,value in frames):
        raise ValueError("Keyframe transforms must be numeric")
    t=time % length
    for (start,a),(end,b) in zip(frames,frames[1:]):
        if start <= t <= end:
            weight=(t-start)/(end-start)
            return [x+(y-x)*weight for x,y in zip(a,b)]
    raise ValueError("Keyframes do not cover animation time")


def sample_bound_animations(document, client, time, distance, speed):
    pose={}
    for entry in client["scripts"]["animate"]:
        alias,weight=(entry,1) if isinstance(entry,str) else next(iter(entry.items()))
        animation_id=client["animations"][alias]
        if animation_id not in document["animations"]:
            continue  # Native walk/look are independently supplied by vanilla.
        amount=evaluate_rotation([weight],time,distance,speed)[0]
        animation=document["animations"][animation_id]
        for name,bone in animation["bones"].items():
            delta=sample_keyframes(bone["rotation"],time,animation["animation_length"])
            current=pose.setdefault(name,[0,0,0])
            for axis in range(3):current[axis]+=delta[axis]*amount
    return pose


def framing_anchor(bones, poses):
    lookup={b["name"]:b for b in bones}
    points=[renderer.transformed_point(p,b["name"],lookup,pose)
            for pose in poses for b in bones for c in b.get("cubes",[]) for p in renderer.cube_vertices(c)]
    lo=[min(p[a] for p in points) for a in range(3)]
    hi=[max(p[a] for p in points) for a in range(3)]
    return {"name":"preview_only","pivot":[0,0,0],"cubes":[{"origin":lo,"size":[hi[a]-lo[a] for a in range(3)],
        "uv":{face:{"uv":[0,0],"uv_size":[1,1]} for face in ["north","south","east","west","up","down"]}}]}


def render(output, seconds=12, fps=6):
    rp=ROOT/"TwilightBossSliceR"
    read=lambda p:json.loads(p.read_text(encoding="utf-8"))
    client=read(rp/"entity/deer.entity.json")["minecraft:client_entity"]["description"]
    geometry=read(rp/"models/entity/art/deer_v1.geo.json")["minecraft:geometry"][0]
    assert client["geometry"]["default"] == geometry["description"]["identifier"]
    animation=read(rp/"animations/deer_art.animation.json")
    assert "art_details" in client["scripts"]["animate"]
    texture=Image.open(rp/(client["textures"]["default"]+".png")).convert("RGBA")
    assert texture.getpixel((0,0))[3] == 0
    samples=[]
    # Six complete native gait cycles over 12 seconds; continuous query phase.
    rate=180/38.17
    for index in range(round(seconds*fps)):
        t=index/fps
        for speed in [0,.25]:
            distance=t*rate if speed else 0
            pose=sample_bound_animations(animation,client,t,distance,speed)
            amplitude=80*speed*math.cos(math.radians(distance*38.17))
            pose.update({name:[sign*amplitude,0,0] for name,sign in {"leg0":1,"leg1":-1,"leg2":-1,"leg3":1}.items()})
            samples.append({"time":t,"speed":speed,"distance":distance,"pose":pose})
    bones=copy.deepcopy(geometry["bones"])
    bones.append(framing_anchor(bones,[s["pose"] for s in samples]))
    frames=[]
    font=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",16)
    for index in range(round(seconds*fps)):
        frame=Image.new("RGBA",(860,840),(18,21,27,255));d=ImageDraw.Draw(frame)
        d.text((12,9),"暮色鹿 · 耳朵轻摆 / 尾根摆动 · 离线动画预览",font=font,fill="white")
        for col,label in enumerate(["静止：耳朵偶尔轻摆，尾巴轻摇","行走：尾巴增加小幅摆动"]):
            d.text((12+430*col,40),label,font=font,fill=(166,185,207))
            # Geometry, rest rotations, pivots and UVs come from pack files.
            for row,yaw in enumerate([35,145]):
                renderer.render_view(d,(6+430*col,67+380*row,424+430*col,445+380*row),"",bones,samples[index*2+col]["pose"],yaw,-12,texture,max_texture_samples=24)
        frames.append(frame.convert("RGB"))
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    frames[0].save(output,save_all=True,append_images=frames[1:],duration=round(1000/fps),loop=0,disposal=2)
    frames[6].save(output.with_suffix(".png"))
    output.with_suffix(".inputs.json").write_text(json.dumps({"fps":fps,"seconds":seconds,"samples":samples,
        "scope":"offline numeric keyframe and client weight sampling; not client evidence","animation":str(rp/"animations/deer_art.animation.json")},indent=2),encoding="utf-8")
    return str(output)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print(render(args.output))
