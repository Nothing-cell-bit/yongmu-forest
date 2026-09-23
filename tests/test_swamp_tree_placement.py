"""Contract simulation of feature control flow, not a NetEase runtime test.

Model no-op block writes as failures, and exercise both aggregate orders.
Actual tree blocks come from the existing template builders.
"""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_swamp_features as builder

GROUND = ["minecraft:grass", "minecraft:grass_block", "minecraft:dirt",
          "minecraft:clay", "minecraft:podzol", "minecraft:mycelium"]
KINDS = {"mangrove": builder.mangrove_tree_structure,
         "swampy_oak": builder.swampy_oak_tree_structure}


@pytest.fixture(scope="module")
def generated():
    with TemporaryDirectory() as directory:
        bp = Path(directory)
        features = bp / "netease_features"
        templates = {}
        for kind, factory in KINDS.items():
            builder.build_tree_variants(bp, features, kind, factory, GROUND)
            for variant in range(4):
                relative = Path("structures/tf_slice/swamp/trees") / kind / f"v{variant:02d}.mcstructure"
                assert (bp / relative).read_bytes() == (ROOT / "TwilightBossSliceB" / relative).read_bytes()
                structure, _, _ = factory(variant)
                templates[f"tf_slice:swamp/trees/{kind}/v{variant:02d}"] = {
                    pos: block[0] for pos, block in structure.blocks.items()
                }
        documents = {}
        for path in features.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            feature_type = next(key for key in document if key != "format_version")
            body = document[feature_type]
            documents[body["description"]["identifier"]] = (feature_type, body)
        yield documents, templates


class FeatureWorld:
    def __init__(self, generated, ground="minecraft:grass", cell="minecraft:air",
                 above="minecraft:air", reject_template=False, reverse=False):
        self.documents, self.templates = generated
        self.blocks = {(0, -1, 0): ground}
        if cell != "minecraft:air":
            self.blocks[(0, 0, 0)] = cell
        if above != "minecraft:air":
            self.blocks[(0, 1, 0)] = above
        self.reject_template = reject_template
        self.reverse = reverse
        self.attempts = 0

    def block(self, pos):
        return self.blocks.get(pos, "minecraft:air")

    def place(self, identifier, pos=(0, 0, 0)):
        kind, body = self.documents[identifier]
        if kind == "minecraft:single_block_feature":
            current = self.block(pos)
            target = body["places_block"][0]["block"]
            if current not in body["may_replace"] or current == target:
                return False
            attach = body.get("may_attach_to", {})
            offsets = {"bottom": (0, -1, 0), "top": (0, 1, 0)}
            sides = sum(self.block(tuple(a + b for a, b in zip(pos, delta)))
                        in attach[side] for side, delta in offsets.items()
                        if side in attach)
            if sides < attach.get("min_sides_must_attach", 0):
                return False
            if target == "minecraft:air":
                self.blocks.pop(pos, None)
            else:
                self.blocks[pos] = target
            return True
        if kind == "minecraft:sequence_feature":
            return all(self.place(child, pos) for child in body["features"])
        if kind == "minecraft:aggregate_feature":
            children = list(body["features"])
            if self.reverse:
                children.reverse()
            results = []
            for child in children:
                result = self.place(child, pos)
                results.append(result)
                if body.get("early_out") == "first_success" and result:
                    break
                if body.get("early_out") == "first_failure" and not result:
                    break
            return any(results)
        if kind == "minecraft:scatter_feature":
            dist = body["distribution"]
            assert dist["iterations"] == 1
            offset = tuple(dist[axis] for axis in "xyz")
            return self.place(body["places_feature"],
                              tuple(a + b for a, b in zip(pos, offset)))
        if kind == "netease:structure_feature":
            self.attempts += 1
            if self.reject_template:
                return False
            for local, block in self.templates[body["places_structure"]].items():
                self.blocks[tuple(a + b for a, b in zip(pos, local))] = block
            return True
        raise AssertionError("Unsupported feature in test model: " + kind)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("variant", range(4))
@pytest.mark.parametrize("reverse", (False, True))
def test_bare_ground_places_complete_tree(generated, kind, variant, reverse):
    world = FeatureWorld(generated, reverse=reverse)
    assert world.place(f"tf_slice:{kind}_tree_v{variant:02d}_sequence_feature")
    assert world.attempts == 1
    structure, center, base = KINDS[kind](variant)
    expected = {(x-center, y-base, z-center): block[0]
                for (x, y, z), block in structure.blocks.items()}
    expected[(0, -1, 0)] = "minecraft:grass"
    assert world.blocks == expected


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("cell", ("minecraft:air", "minecraft:water", "minecraft:tallgrass"))
def test_rejected_tree_leaves_no_probe_log(generated, kind, reverse, cell):
    world = FeatureWorld(generated, cell=cell, reject_template=True, reverse=reverse)
    world.place(f"tf_slice:{kind}_tree_v00_sequence_feature")
    assert world.attempts == 1
    assert world.blocks == {(0, -1, 0): "minecraft:grass"}


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("ground,cell,above", (
    ("tf_slice:landmark_protected_grass", "minecraft:air", "minecraft:air"),
    ("minecraft:stone", "minecraft:air", "minecraft:air"),
    ("minecraft:air", "minecraft:air", "minecraft:air"),
    ("minecraft:grass", "tf_slice:mangrove_log", "minecraft:air"),
    ("minecraft:grass", "tf_slice:twilight_oak_log", "minecraft:air"),
    ("minecraft:grass", "minecraft:air", "tf_slice:mangrove_log"),
    ("minecraft:grass", "minecraft:air", "minecraft:stone"),
))
def test_invalid_candidate_does_not_write_or_cleanup(generated, kind, ground, cell, above):
    world = FeatureWorld(generated, ground=ground, cell=cell, above=above)
    before = dict(world.blocks)
    assert not world.place(f"tf_slice:{kind}_tree_v00_sequence_feature")
    assert world.attempts == 0
    assert world.blocks == before


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("ground", GROUND)
@pytest.mark.parametrize("cell", ("minecraft:water", "minecraft:tallgrass"))
def test_existing_swamp_substrates_still_grow_trees(generated, kind, ground, cell):
    world = FeatureWorld(generated, ground=ground, cell=cell, above=cell)
    assert world.place(f"tf_slice:{kind}_tree_v00_sequence_feature")
    assert world.attempts == 1
    assert world.block((0, 0, 0)) != "minecraft:air"
    assert world.block((0, 1, 0)) == world.block((0, 0, 0))


def test_scoped_graph_is_the_same_graph_used_by_full_tree_builder(generated):
    from swamp_tree_placement import all_placement_documents, check_placement_documents
    expected = all_placement_documents()
    assert len(expected) == 20
    documents, _ = generated
    for filename, document in expected.items():
        kind = next(key for key in document if key != "format_version")
        body = document[kind]
        assert documents[body["description"]["identifier"]] == (kind, body), filename
    assert check_placement_documents(expected) == []


def test_graph_checker_rejects_air_probe_or_short_circuit_cleanup():
    from swamp_tree_placement import all_placement_documents, check_placement_documents
    documents = all_placement_documents()
    name = "mangrove_tree_anchor_feature.json"
    documents[name]["minecraft:single_block_feature"]["places_block"][0]["block"] = "minecraft:air"
    assert name in check_placement_documents(documents)
    documents = all_placement_documents()
    name = "swampy_oak_tree_v00_placement_feature.json"
    documents[name]["minecraft:aggregate_feature"]["early_out"] = "first_success"
    assert name in check_placement_documents(documents)


def test_scoped_writer_changes_only_placement_json_and_check_is_read_only(tmp_path):
    from swamp_tree_placement import all_placement_documents, main
    sentinel = tmp_path / "TwilightBossSliceB/structures/tf_slice/swamp/keep.mcstructure"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_bytes(b"do not rebuild structure templates")
    assert main(["--write", "--output-root", str(tmp_path)]) == 0
    snapshot = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert len(snapshot) == 21
    assert main(["--check", "--output-root", str(tmp_path)]) == 0
    assert snapshot == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    feature_dir = tmp_path / "TwilightBossSliceB/netease_features"
    assert {p.name for p in feature_dir.iterdir()} == set(all_placement_documents())
    (feature_dir / "mangrove_tree_anchor_feature.json").unlink()
    assert main(["--check", "--output-root", str(tmp_path)]) == 1
    assert sentinel.read_bytes() == b"do not rebuild structure templates"


def test_scoped_writer_requires_acknowledgment_for_canonical_outputs():
    from swamp_tree_placement import main
    with pytest.raises(SystemExit) as exc:
        main(["--write", "--output-root", str(ROOT)])
    assert exc.value.code == 2
