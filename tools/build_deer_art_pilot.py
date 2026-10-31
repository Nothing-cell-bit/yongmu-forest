"""Build only the user-authorized deer visual variant, never gameplay/ruins."""
import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART_ID = "geometry.tf_slice.deer_art_v1"
GEO_REL = "models/entity/art/deer_v1.geo.json"
TEX_REL = "textures/tf_beautified/entities/deer_v1.png"
ANIM_REL = "animations/deer_art.animation.json"
ANIM_ID = "animation.tf_slice.deer_art.details"
WALK_ART_ID = "animation.tf_slice.deer_art.walk_tail"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def swatch(uv):
    return {face: {"uv": list(uv), "uv_size": [1, 1]} for face in ("north", "south", "east", "west", "up", "down")}


def box(origin, size, uv):
    return {"origin": list(origin), "size": list(size), "uv": swatch(uv)}


def geometry_document(base):
    result = copy.deepcopy(base)
    result["description"]["identifier"] = ART_ID
    bones = {bone["name"]: bone for bone in result["bones"]}
    # Appending to the original antler bones preserves the existing baby-hide
    # rule for every added tine, without relying on child visibility inheritance.
    tips = [
        box([-6.075,39,-14.075],[.85,1.3,.85],[23,4]),
        box([-7.1,37.5,-9.05],[.8,1.3,.8],[22,2]),
        box([-7.9,34.8,-13.3],[1.2,.8,1.2],[22,2]),
    ]
    bones["left_antler"]["cubes"].extend(tips)
    for cube in tips:
        mirrored = copy.deepcopy(cube)
        mirrored["origin"][0] = -cube["origin"][0] - cube["size"][0]
        bones["right_antler"]["cubes"].append(mirrored)
    result["bones"].extend([
        {"name":"left_ear", "parent":"head", "pivot":[-2,26,-9], "rotation":[0,0,-25], "cubes":[
            box([-5,25.5,-9.6],[3,1,.8],[43,22]),
            box([-4.6,25.72,-9.71],[2.2,.55,.12],[45,22]),
        ]},
        {"name":"right_ear", "parent":"head", "pivot":[2,26,-9], "rotation":[0,0,25], "cubes":[
            box([2,25.5,-9.6],[3,1,.8],[43,22]),
            box([2.4,25.72,-9.71],[2.2,.55,.12],[45,22]),
        ]},
        {"name":"chest_ruff", "parent":"neck", "pivot":[1,19,2], "cubes":[
            box([-1.7,18.5,-9.4],[3.4,3.6,.55],[45,22]),
            box([-1.25,17.6,-9.35],[2.5,.9,.4],[22,2]),
        ]},
        # These are in the original body's pre-rotation coordinates. Its 90°
        # body rotation places the tail behind the rump, never on the belly.
        {"name":"tail", "parent":"body", "pivot":[0,12,1.1], "cubes":[
            box([-.6,8,.5],[1.2,4,1.3],[43,22]),
            box([-.75,6.5,.6],[1.5,2.5,1.25],[23,4]),
        ]},
    ])
    return {"format_version":"1.12.0", "minecraft:geometry":[result]}


def animation_document():
    # User-authored cosmetic design, not an upstream behavior-fidelity claim.
    # Only new bones: native walk and head tracking keep their existing layers.
    return {"format_version":"1.8.0", "animations":{ANIM_ID:{
        "loop":True, "animation_length":4,
        "bones":{
            "left_ear":{"rotation":{"0.0":[0,0,0],"0.45":[0,0,0],"0.65":[0,0,14],"0.85":[0,0,-6],"1.1":[0,0,0],"4.0":[0,0,0]}},
            "right_ear":{"rotation":{"0.0":[0,0,0],"1.5":[0,0,0],"1.7":[0,0,-14],"1.9":[0,0,6],"2.15":[0,0,0],"4.0":[0,0,0]}},
            "tail":{"rotation":{"0.0":[0,0,0],"0.5":[8,0,18],"1.0":[0,0,0],"1.5":[-8,0,-18],"2.0":[0,0,0],"2.5":[8,0,18],"3.0":[0,0,0],"3.5":[-8,0,-18],"4.0":[0,0,0]}},
        },
    }, WALK_ART_ID:{"loop":True,"animation_length":1,
        "bones":{"tail":{"rotation":{"0.0":[0,0,0],"0.25":[0,0,8],"0.5":[0,0,0],"0.75":[0,0,-8],"1.0":[0,0,0]}}},
    }}}


def build(root, texture_candidate):
    root = Path(root)
    rp = root / "TwilightBossSliceR"
    base_path = rp / "models/entity/forest_animals.geo.json"
    base = next(g for g in read(base_path)["minecraft:geometry"] if g["description"]["identifier"] == "geometry.tf_slice.deer")
    original = rp / "textures/entity/wilddeer.png"
    with Image.open(original) as a, Image.open(texture_candidate) as b:
        if a.size != b.size or b.size != (64,32) or a.convert("RGBA").getchannel("A").tobytes() != b.convert("RGBA").getchannel("A").tobytes():
            raise ValueError("Deer texture size or alpha changed")
    bank = root / "resource_art/entity_beautification/v1"
    document = geometry_document(base)
    write(rp / GEO_REL, document)
    animation = animation_document()
    write(rp / ANIM_REL, animation)
    (rp / TEX_REL).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(texture_candidate, rp / TEX_REL)
    for folder, source in [("assets",texture_candidate),("source_baselines",original)]:
        destination = bank / folder / "deer.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source,destination)
    write(bank / "geometry/deer.json",document)
    write(bank / "animations/deer.json",animation)
    registry_path = bank / "manifest.json"
    registry = read(registry_path) if registry_path.exists() else {"schema_version":1,"enabled":True,"entities":{}}
    previous = registry["entities"].get("tf_slice:deer", {})
    registry["entities"]["tf_slice:deer"] = {**previous,
        "client_entity":"entity/deer.entity.json", "source_geometry":"geometry.tf_slice.deer",
        "geometry":ART_ID, "geometry_path":GEO_REL, "source_texture":"textures/entity/wilddeer",
        "texture":TEX_REL[:-4], "native_size":[64,32],
        "source_texture_sha256":hashlib.sha256(original.read_bytes()).hexdigest(),
        "texture_sha256":hashlib.sha256((rp/TEX_REL).read_bytes()).hexdigest(),
        "geometry_sha256":hashlib.sha256((rp/GEO_REL).read_bytes()).hexdigest(),
        "animation_path":ANIM_REL, "animations":{"art_details":ANIM_ID,"art_walk":WALK_ART_ID},
        "animate":["art_details",{"art_walk":"math.clamp(query.modified_move_speed * 4, 0, 1)"}],
        "animation_sha256":hashlib.sha256((rp/ANIM_REL).read_bytes()).hexdigest(),
        "scope":"model-only; user-authorized art expansion", "status":previous.get("status","draft-runtime-pending"),
        "behavior":"not_reviewed",
    }
    write(registry_path,registry)
    try:
        from entity_visual_overrides import apply_entity_visual_overrides
    except ImportError:
        from tools.entity_visual_overrides import apply_entity_visual_overrides
    client = rp / "entity/deer.entity.json"
    write(client,apply_entity_visual_overrides(client,read(client)))
    return {"geometry":str(rp/GEO_REL),"texture":str(rp/TEX_REL),"bones":len(document["minecraft:geometry"][0]["bones"]),"cubes":sum(len(b.get("cubes",[])) for b in document["minecraft:geometry"][0]["bones"])}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root",type=Path,default=ROOT)
    parser.add_argument("--texture-candidate",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.project_root,args.texture_candidate),indent=2))
