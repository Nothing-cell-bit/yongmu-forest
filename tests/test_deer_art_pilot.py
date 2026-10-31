"""User-authorized deer art variant: preserve rig, bounded UV and bindings."""
import json
import tempfile
from pathlib import Path
from PIL import Image
from tools import build_public_block_shapes as writer

ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
ART_ID = "geometry.tf_slice.deer_art_v1"
GEOMETRY = RP / "models/entity/art/deer_v1.geo.json"
TEXTURE = RP / "textures/tf_beautified/entities/deer_v1.png"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_active_deer_binding_keeps_animation_and_baby_controller_contract():
    c = read(RP / "entity/deer.entity.json")["minecraft:client_entity"]["description"]
    assert c["geometry"]["default"] == ART_ID
    assert c["textures"]["default"] == "textures/tf_beautified/entities/deer_v1"
    assert c["animations"] == {"walk": "animation.quadruped.walk", "look_at_target": "animation.common.look_at_target", "art_details": "animation.tf_slice.deer_art.details", "art_walk":"animation.tf_slice.deer_art.walk_tail"}
    assert c["scripts"]["animate"] == [{"walk":"query.modified_move_speed"}, "look_at_target", "art_details", {"art_walk":"math.clamp(query.modified_move_speed * 4, 0, 1)"}]
    assert c["render_controllers"] == ["controller.render.tf_slice.deer"]
    parts = read(RP / "render_controllers/forest_animals.render.json")["render_controllers"]["controller.render.tf_slice.deer"]["part_visibility"]
    assert parts == [{"left_antler": "!query.is_baby"}, {"right_antler": "!query.is_baby"}]


def test_original_rig_is_retained_and_art_additions_follow_animated_parents():
    base = next(g for g in read(RP / "models/entity/forest_animals.geo.json")["minecraft:geometry"] if g["description"]["identifier"] == "geometry.tf_slice.deer")
    current = read(GEOMETRY)["minecraft:geometry"][0]
    assert current["description"]["identifier"] == ART_ID
    original = {b["name"]: b for b in base["bones"]}
    bones = {b["name"]: b for b in current["bones"]}
    for name, bone in original.items():
        if name.endswith("antler"):
            assert bones[name]["cubes"][:len(bone["cubes"])] == bone["cubes"]
            assert len(bones[name]["cubes"]) > len(bone["cubes"])
            assert {k:v for k,v in bones[name].items() if k != "cubes"} == {k:v for k,v in bone.items() if k != "cubes"}
        else:
            assert bones[name] == bone
    for name, parent in {"left_ear":"head", "right_ear":"head", "chest_ruff":"neck", "tail":"body"}.items():
        assert bones[name]["parent"] == parent
    assert set(bones) - set(original) == {"left_ear", "right_ear", "chest_ruff", "tail"}
    assert all(b.get("parent") not in ("left_antler", "right_antler") for b in current["bones"])


def test_texture_preserves_original_size_alpha_face_and_uv_markers():
    import numpy as np
    from tools.retired_runtime_pngs import original_texture
    a = np.asarray(Image.open(original_texture(RP / "textures/entity/wilddeer.png", ROOT)).convert("RGBA"))
    b = np.asarray(Image.open(TEXTURE).convert("RGBA"))
    assert a.shape == b.shape == (32,64,4)
    assert (a[:,:,3] == b[:,:,3]).all()
    assert (a[5:17,:20] == b[5:17,:20]).all()
    assert (a[:6,52:64] == b[:6,52:64]).all()
    marker = ((a[:,:,:3] == [255,0,0]).all(2) | (a[:,:,:3] == [0,0,255]).all(2) | (a[:,:,:3] == [0,255,0]).all(2))
    assert (a[marker] == b[marker]).all()
    assert (a != b).any()


def test_real_resource_writer_reapplies_deer_art_without_changing_siblings_or_behavior():
    original = read(RP / "entity/deer.entity.json")
    original["minecraft:client_entity"]["description"]["geometry"]["default"] = "geometry.tf_slice.deer"
    original["minecraft:client_entity"]["description"]["textures"]["default"] = "textures/entity/wilddeer"
    manifest = read(ROOT / "resource_art/entity_beautification/v1/manifest.json")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bank = root / "resource_art/entity_beautification/v1"
        bank.mkdir(parents=True)
        (bank / "manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
        target = root / "TwilightBossSliceR/entity/deer.entity.json"
        writer.write_json(target, original)
        assert read(target)["minecraft:client_entity"]["description"]["geometry"]["default"] == ART_ID
        assert read(target)["minecraft:client_entity"]["description"]["animations"]["art_details"] == "animation.tf_slice.deer_art.details"
        writer.write_json(target, read(target))
        assert read(target)["minecraft:client_entity"]["description"]["scripts"]["animate"].count("art_details") == 1
        sibling = root / "TwilightBossSliceR/entity/boar.entity.json"
        writer.write_json(sibling, original)
        assert read(sibling) == original
        behavior = root / "TwilightBossSliceB/entities/deer.entity.json"
        writer.write_json(behavior, original)
        assert read(behavior) == original
        flipbook = root / "TwilightBossSliceR/textures/flipbook_textures.json"
        value = [{"flipbook_texture":"textures/tf_beautified/base/portal", "atlas_tile":"tf_slice:twilight_portal"}]
        writer.write_json(flipbook, value)
        assert read(flipbook) == value


def test_cosmetic_animation_is_live_bounded_and_rotates_at_the_tail_root():
    import math
    from tools import render_entity_geo_preview as preview
    from tools.preview_deer_art_motion import sample_bound_animations
    animations = read(RP / "animations/deer_art.animation.json")
    client = read(RP / "entity/deer.entity.json")["minecraft:client_entity"]["description"]
    animation = animations["animations"]["animation.tf_slice.deer_art.details"]
    assert animation["loop"] is True
    assert not animation.get("override_previous_animation", False)
    assert set(animation["bones"]) == {"left_ear", "right_ear", "tail"}
    assert all(set(value) == {"rotation"} for value in animation["bones"].values())
    bones = {b["name"]:b for b in read(GEOMETRY)["minecraft:geometry"][0]["bones"]}
    assert bones["tail"]["pivot"] == [0, 12, 1.1]
    observed = {name:[] for name in animation["bones"]}
    for time in [0, .25, .5, .65, 1, 1.7, 2, 3, 4, 10000, 1000000]:
        for distance in [0, 1, 10, 10000, 1000000]:
            for speed in [0, .25, 1, 100]:
                pose = sample_bound_animations(animations,client,time,distance,speed)
                for name, rotation in pose.items():
                    assert rotation[1] == 0
                    assert all(math.isfinite(value) for value in rotation)
                    assert abs(rotation[0]) <= (8 if name == "tail" else 0)
                    assert abs(rotation[2]) <= (26 if name == "tail" else 14) + 1e-8
                    observed[name].append(rotation[2])
                    pivot = bones[name]["pivot"]
                    assert preview.transformed_point(pivot,name,bones,pose) == preview.transformed_point(pivot,name,bones,{})
    assert all(max(values)-min(values) > 1 for values in observed.values())
    assert sample_bound_animations(animations,client,.5,1e6,0)["tail"][2] == 18
    assert sample_bound_animations(animations,client,.65,0,0)["left_ear"][2] == 14
    assert sample_bound_animations(animations,client,3,0,0)["left_ear"][2] == 0
    for name,point,time,min_motion in [("tail",[-.75,6.5,.6],.5,1.4),("left_ear",[-5,25.5,-9.6],.65,.65)]:
        pose=sample_bound_animations(animations,client,time,0,0)
        assert math.dist(preview.transformed_point(point,name,bones,pose),preview.transformed_point(point,name,bones,{})) >= min_motion


def test_details_use_numeric_keyframes_with_explicit_closed_loops():
    definitions=read(RP / "animations/deer_art.animation.json")["animations"]
    assert len(definitions) == 2
    for animation in definitions.values():
        assert animation["loop"] is True
        assert animation["animation_length"] > 0
        for bone in animation["bones"].values():
            rotation=bone["rotation"]
            assert isinstance(rotation,dict)
            assert min(map(float,rotation)) == 0
            assert max(map(float,rotation)) == animation["animation_length"]
            assert list(rotation.values())[0] == list(rotation.values())[-1]
            assert any(frame != list(rotation.values())[0] for frame in rotation.values())
            assert all(isinstance(value,(int,float)) for frame in rotation.values() for value in frame)


def test_added_uv_faces_sample_opaque_native_texels():
    base = next(g for g in read(RP / "models/entity/forest_animals.geo.json")["minecraft:geometry"] if g["description"]["identifier"] == "geometry.tf_slice.deer")
    counts = {b["name"]:len(b.get("cubes",[])) for b in base["bones"]}
    with Image.open(TEXTURE).convert("RGBA") as image:
        for bone in read(GEOMETRY)["minecraft:geometry"][0]["bones"]:
            for cube in bone.get("cubes",[])[counts.get(bone["name"],0):]:
                assert all(value > 0 for value in cube["size"])
                assert set(cube["uv"]) == {"north","south","east","west","up","down"}
                for face in cube["uv"].values():
                    x,y = face["uv"]
                    assert 0 <= x < 64 and 0 <= y < 32
                    assert face["uv_size"] == [1,1]
                    assert image.getpixel((x,y))[3] == 255


def test_model_stays_inside_visible_bounds_at_walk_and_cosmetic_extrema():
    from itertools import product
    from tools import render_entity_geo_preview as preview
    geometry = read(GEOMETRY)["minecraft:geometry"][0]
    bones = {b["name"]:b for b in geometry["bones"]}
    d = geometry["description"]
    half = d["visible_bounds_width"] * 8
    ymid = d["visible_bounds_offset"][1] * 16
    yhalf = d["visible_bounds_height"] * 8
    for walk, head, tail, ear in product([-80,0,80],[-30,0,30],[-26,0,26],[-14,0,14]):
        pose = {"head":[head,0,0],"tail":[8,0,tail],"left_ear":[0,0,ear],"right_ear":[0,0,-ear]}
        pose.update({b:[walk*sign,0,0] for b,sign in {"leg0":1,"leg1":-1,"leg2":-1,"leg3":1}.items()})
        for bone in bones.values():
            for cube in bone.get("cubes",[]):
                for vertex in preview.cube_vertices(cube):
                    x,y,z = preview.transformed_point(vertex,bone["name"],bones,pose)
                    assert -half <= x <= half and -half <= z <= half
                    assert ymid-yhalf <= y <= ymid+yhalf


def test_scoped_builder_reproduces_art_and_leaves_siblings_and_baselines_intact(tmp_path):
    import shutil
    from tools.build_deer_art_pilot import build
    rp = tmp_path / "TwilightBossSliceR"
    for relative in ["models/entity/forest_animals.geo.json","textures/entity/wilddeer.png","entity/deer.entity.json","entity/boar.entity.json"]:
        (rp/relative).parent.mkdir(parents=True,exist_ok=True)
        from tools.retired_runtime_pngs import original_texture
        shutil.copy2(original_texture(RP/relative,ROOT),rp/relative)
    original = {relative:(rp/relative).read_bytes() for relative in ["models/entity/forest_animals.geo.json","textures/entity/wilddeer.png","entity/boar.entity.json"]}
    result = build(tmp_path,TEXTURE)
    assert result["bones"] == 13 and result["cubes"] == 44
    included = ["models/entity/art/deer_v1.geo.json","textures/tf_beautified/entities/deer_v1.png","animations/deer_art.animation.json","entity/deer.entity.json"]
    first = {path:(rp/path).read_bytes() for path in included}
    build(tmp_path,TEXTURE)
    assert first == {path:(rp/path).read_bytes() for path in included}
    assert original == {path:(rp/path).read_bytes() for path in original}
    assert all((rp/path).read_bytes() == (RP/path).read_bytes() for path in included)
