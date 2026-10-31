import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import build_stream_continuity_candidate as builder
import build_ruin_structures as ruins


def evaluate(expression, grid):
    js = """const [expr,cells]=JSON.parse(process.argv[1]);
const query={get_neighborhood_is_biome:(x,z,...ids)=>ids.includes(cells[x+','+z]??1)};
process.stdout.write(JSON.stringify(Function('query','return '+expr)(query)));"""
    r = subprocess.run(["node", "-e", js, json.dumps([expression, grid])],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_bridges_narrow_break_without_creating_isolated_rivers():
    expr = builder.bank_condition()
    assert evaluate(expr, {"0,0": 1, "-1,0": 7, "1,0": 7}) == 0
    assert evaluate(expr, {"0,0": 21, "0,1": 7}) == 0
    assert evaluate(expr, {"0,0": 1}) == -1
    for protected in (0, 7, 35, 129, 999):
        assert evaluate(expr, {"0,0": protected, "0,1": 7}) == -1


def test_pipeline_keeps_every_existing_stage_and_adds_one_bounded_pass():
    source = {"netease:dimension_info": {"components": {
        "netease:biome_source": [{"type": "kept", "index": n} for n in range(16)] +
        [{"type": "condition", "pool": ["dm33027004_river"], "condition": "old"}],
        "other": {"untouched": True}}}}
    before = copy.deepcopy(source)
    result = builder.build_dimension(source)
    stages = result["netease:dimension_info"]["components"]["netease:biome_source"]
    assert stages[:-1] == before["netease:dimension_info"]["components"]["netease:biome_source"]
    assert len(stages) == 18 and source == before
    assert stages[-1]["condition"].count("query.get_neighborhood_is_biome") == 5


def test_emitted_condition_matches_independent_neighbor_contract_exhaustively():
    js = """const expr=process.argv[1], fn=Function('query','return '+expr);
const types=[0,1,6,7,14,15,21,29,35,129,132,134,155,157,160,999];
const allowed=new Set([1,6,14,15,21,29,132,134,155,157,160]);
let checked=0,changed=0;
for(const c of types)for(const a of types)for(const b of types)
for(const d of types)for(const e of types){
 const cells={'0,0':c,'-1,0':a,'1,0':b,'0,-1':d,'0,1':e};
 const query={get_neighborhood_is_biome:(x,z,...ids)=>{
 if(Math.abs(x)>1||Math.abs(z)>1)throw Error('offset');
 return ids.includes(cells[x+','+z]);}};
 const expected=allowed.has(c)&&[a,b,d,e].includes(7)?0:-1;
 if(fn(query)!==expected)throw Error('wrong classification');
 changed+=expected===0;checked++;}
process.stdout.write(JSON.stringify({checked,changed}));"""
    result = subprocess.run(["node", "-e", js, builder.bank_condition()],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["checked"] == 16 ** 5 and report["changed"] > 0


def test_dry_guard_checks_entire_footprint_and_follows_rarity():
    guard = ruins._dry_footprint_feature("tf_slice:stone_circle_dry_ground_feature",
                                        "tf_slice:stone_circle_structure_selector_feature", 7, 7)
    body = guard["minecraft:scatter_feature"]
    assert body["iterations"].count("query.get_height_at") == 49
    js = """const [expr,bad]=JSON.parse(process.argv[1]);
const variable={originx:0,originz:0};
const query={get_height_at:(x,z)=>(x===bad[0]&&z===bad[1])?63:64};
process.stdout.write(JSON.stringify(Function('query','variable','return '+expr)(query,variable)));"""
    for point, expected in [([-1, -1], 1), ([0, 0], 0), ([3, 4], 0), ([6, 6], 0)]:
        r = subprocess.run(["node", "-e", js, json.dumps([body["iterations"], point])],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout) == expected
    outer = ruins._scatter_feature("tf_slice:stone_circle_scatter_feature",
                                   "tf_slice:stone_circle_structure_selector_feature", 105, 7, 7)
    assert outer["minecraft:scatter_feature"]["scatter_chance"] == {"numerator": 1, "denominator": 105}
    assert outer["minecraft:scatter_feature"]["places_feature"] == "tf_slice:stone_circle_dry_ground_feature"


def test_real_ruin_writer_emits_guard_and_resolves_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(ruins, "BP", tmp_path)
    structure = ruins.SparseStructure((7, 3, 7), "test_stone_circle")
    structure.set(0, 0, 0, "minecraft:stone")
    ruins.write_native_resources("stone_circle", [("v00", structure, 1)], 105,
                                 biome_tag="tf_slice_small_ruins")
    outer = json.loads((tmp_path / "netease_features/stone_circle_scatter_feature.json").read_text())
    target = outer["minecraft:scatter_feature"]["places_feature"].split(":")[1]
    guard = json.loads((tmp_path / "netease_features" / (target + ".json")).read_text())
    guards = [json.loads(p.read_text())["minecraft:scatter_feature"]
              for p in (tmp_path / "netease_features").glob("*dry_ground_feature*.json")]
    assert sum(row["iterations"].count("> 63") for row in guards) == 49
    assert all(row["iterations"].count("> 63") <= 32 for row in guards)
    assert (tmp_path / "netease_features/stone_circle_structure_selector_feature.json").is_file()
