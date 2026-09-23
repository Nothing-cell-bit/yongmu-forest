"""Exercise shipped tree shapes under both aggregate execution orders."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_swamp_features as swamp
import build_spooky_forest as spooky
from test_swamp_tree_placement import FeatureWorld, GROUND


@pytest.fixture(scope="module")
def graphs():
    result = {}
    for kind, count in (("canopy_tree", 4), ("spooky_dead_tree", 16)):
        documents = {}
        for path in (ROOT / "TwilightBossSliceB/netease_features").glob(kind + "*.json"):
            documents[path.name] = json.loads(path.read_text(encoding="utf-8"))
        if kind == "canopy_tree":
            with TemporaryDirectory() as temp:
                bp = Path(temp)
                swamp.build_tree_variants(bp, bp / "netease_features", "canopy",
                                          swamp.canopy_tree_structure, GROUND)
                for path in (bp / "netease_features").glob("*.json"):
                    documents[path.name] = json.loads(path.read_text(encoding="utf-8"))
        else:
            documents[kind + "_anchor_feature.json"] = spooky._dead_tree_anchor_feature()
            for i in range(count):
                prefix = kind + "_v%02d" % i
                documents[prefix + "_sequence_feature.json"] = spooky._dead_tree_sequence_feature(
                    prefix + "_sequence_feature", prefix + "_offset_feature")
            # The builder's additional documents are optional in the RED state.
            if hasattr(spooky, "dead_tree_placement_documents"):
                documents.update(spooky.dead_tree_placement_documents())
        registry = {}
        for doc in documents.values():
            component = next(k for k in doc if k != "format_version")
            body = doc[component]
            registry[body["description"]["identifier"]] = (component, body)
        templates = {}
        for i in range(count):
            if kind == "canopy_tree":
                structure, x, y = swamp.canopy_tree_structure(i)
                center = (x, y, x)
                name = "tf_slice:swamp/trees/canopy/v%02d" % i
            else:
                structure, _ = spooky._dead_tree(0x5F001 + i * 977, "v%02d" % i)
                center = spooky.TREE_CENTER
                name = "tf_slice:spooky/dead_tree/v%02d" % i
            templates[name] = {p: b[0] for p, b in structure.blocks.items()}
        result[kind] = (registry, templates)
    return result


CASES = [(kind, i) for kind, count in (("canopy_tree", 4), ("spooky_dead_tree", 16))
         for i in range(count)]


@pytest.mark.parametrize("kind,variant", CASES)
@pytest.mark.parametrize("reverse", (False, True))
def test_all_shapes_reach_template_on_bare_ground(graphs, kind, variant, reverse):
    world = FeatureWorld(graphs[kind], reverse=reverse)
    assert world.place("tf_slice:%s_v%02d_sequence_feature" % (kind, variant))
    assert world.attempts == 1
    assert len(world.blocks) > 30
    assert world.block((0, 1, 0)) == "tf_slice:canopy_log"
    registry, templates = graphs[kind]
    offset = registry["tf_slice:%s_v%02d_offset_feature" % (kind, variant)][1]
    template = registry[offset["places_feature"]][1]["places_structure"]
    delta = tuple(offset["distribution"][axis] for axis in "xyz")
    expected = {(0, -1, 0): "minecraft:grass"}
    expected.update({tuple(a + b for a, b in zip(pos, delta)): block
                     for pos, block in templates[template].items()})
    assert world.blocks == expected


@pytest.mark.parametrize("kind", ("canopy_tree", "spooky_dead_tree"))
@pytest.mark.parametrize("reverse", (False, True))
def test_rejected_template_has_no_orphan_trunk(graphs, kind, reverse):
    world = FeatureWorld(graphs[kind], reverse=reverse, reject_template=True)
    world.place("tf_slice:%s_v00_sequence_feature" % kind)
    assert world.attempts == 1
    assert world.blocks == {(0, -1, 0): "minecraft:grass"}


@pytest.mark.parametrize("kind", ("canopy_tree", "spooky_dead_tree"))
@pytest.mark.parametrize("ground,cell,above", (
    ("tf_slice:landmark_protected_grass", "minecraft:air", "minecraft:air"),
    ("minecraft:stone", "minecraft:air", "minecraft:air"),
    ("minecraft:grass", "tf_slice:canopy_log", "minecraft:air"),
    ("minecraft:grass", "minecraft:air", "tf_slice:canopy_log"),
))
def test_invalid_candidates_preserve_world(graphs, kind, ground, cell, above):
    world = FeatureWorld(graphs[kind], ground=ground, cell=cell, above=above)
    before = dict(world.blocks)
    assert not world.place("tf_slice:%s_v00_sequence_feature" % kind)
    assert world.attempts == 0
    assert world.blocks == before
