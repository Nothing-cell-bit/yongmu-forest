"""Scoped forest tree parity candidate; no global ruin/catalog rebuild.

Counts and sequential selector probabilities come from the locked 4.3.2508
placed/configured features. Four bounded structure variants adapt OakCanopy's
2x2 trunk and crown/branch dimensions to the existing NetEase tree pipeline.
They are not a claim of Java RNG or voxel-for-voxel placement parity.
"""
import argparse
import json
import math
import random
from pathlib import Path

TREE_PLACEMENTS = {
    'dense_forest': (
        ('dense_canopy_selector_feature', 5, True),
        ('twilight_tree_mix_selector_feature', 1, False),
        ('forest_canopy_oak_selector_feature', 7, True),
    ),
    'firefly_forest': (
        ('firefly_canopy_selector_feature', 3, True),
        ('twilight_tree_mix_selector_feature', 1, False),
        ('twilight_oak_tree_feature', 1, True),
        ('large_twilight_oak_tree_feature', 1, True),
    ),
    'oak_savannah': (
        ('twilight_oak_tree_feature', 1, True),
        ('large_twilight_oak_tree_feature', 1, True),
        ('savannah_canopy_oak_selector_feature', 0, True),
    ),
}
LEGACY_RULES = tuple(name + '_tree_profile_feature_rule.json' for name in TREE_PLACEMENTS)

def count_expression(base, extra):
    return '%d + (math.random_integer(1, 10) == 1 ? 1 : 0)' % base if extra else base

def feature_documents():
    from build_swamp_features import weighted_selector_feature
    result = {}
    for name, weights in [
        ('dense_canopy_selector_feature', [('canopy_tree_source_shape_feature', 7), ('twilight_oak_tree_feature', 3)]),
        # 0.33 + (1 - 0.33) * 0.45 = 0.6315.
        # Both canopy subtypes currently share the port's firefly-decorated
        # canopy structure bank; retain this explicit visual adaptation.
        ('firefly_canopy_selector_feature', [('canopy_tree_source_shape_feature', 1263), ('twilight_oak_tree_feature', 737)]),
    ]:
        result[name + '.json'] = weighted_selector_feature(name, weights)
    for biome, placements in TREE_PLACEMENTS.items():
        for index, (feature, base, extra) in enumerate(placements):
            name = '%s_parity_tree_%d_landmark_surface_project_feature' % (biome, index)
            result[name + '.json'] = {'format_version': '1.21.10', 'minecraft:scatter_feature': {
                'description': {'identifier': 'tf_slice:' + name},
                'places_feature': 'tf_slice:' + feature,
                'project_input_to_floor': True,
                'distribution': {'iterations': 1, 'coordinate_eval_order': 'xzy', 'x': 0, 'y': 0, 'z': 0},
            }}
    return result

def rule_documents():
    result = {}
    for biome, placements in TREE_PLACEMENTS.items():
        for index, (feature, base, extra) in enumerate(placements):
            name = '%s_parity_tree_%d' % (biome, index)
            result[name + '_rule.json'] = {'format_version': '1.14.0', 'minecraft:feature_rules': {
                'description': {'identifier': 'tf_slice:' + name + '_rule', 'places_feature': 'tf_slice:' + name + '_landmark_surface_project_feature'},
                'conditions': {'placement_pass': 'after_surface_pass', 'minecraft:biome_filter': [{'all_of': [
                    {'test': 'has_biome_tag', 'operator': '==', 'value': 'dm33027004'},
                    {'test': 'has_biome_tag', 'operator': '==', 'value': 'tf_slice_biome_' + biome},
                ]}]},
                'distribution': {'iterations': count_expression(base, extra), 'coordinate_eval_order': 'xzy',
                    'x': {'distribution': 'uniform', 'extent': [0, 15]},
                    'y': '(query.get_height_at(variable.worldx, variable.worldz)) + 64',
                    'z': {'distribution': 'uniform', 'extent': [0, 15]}},
            }}
    return result

def canopy_oak_structure(variant, savannah=False):
    from build_ruin_structures import SparseStructure
    from build_swamp_features import place_log_line, place_leaf_spheroid
    rng = random.Random(43272508 + int(variant) + (100 if savannah else 0))
    minimum = 16 if savannah else 24
    height = minimum + rng.randrange(minimum // 2) + rng.randrange(5)
    center, base = 10, 3
    structure = SparseStructure((23, 52, 23), 'canopy_oak_%d' % variant)
    log = 'tf_slice:twilight_oak_log'
    for dx, dz in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        for y in range(base, base + height):
            structure.set(center + dx, y, center + dz, log)
        structure.set(center + dx, base - 1, center + dz, 'tf_slice:root_block')
    crowns = [(center, base + height, center)]
    angle = rng.random()
    for branch in range(12 + rng.randrange(9)):
        tilt = 0.15 + rng.random() * 0.35
        y = base + height - 10 + branch // 2
        end = (center + round(math.sin(angle * math.tau) * math.sin(tilt * math.pi) * 5),
               y + round(math.cos(tilt * math.pi) * 5),
               center + round(math.cos(angle * math.tau) * math.sin(tilt * math.pi) * 5))
        place_log_line(structure, (center, y, center), end, log, 'tf_slice:twilight_oak_log_x', 'tf_slice:twilight_oak_log_z')
        for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            structure.set(end[0] + dx, end[1], end[2] + dz, log)
        crowns.append(end)
        angle = (angle + rng.random() * 0.4) % 1.0
    for crown in crowns:
        place_leaf_spheroid(structure, crown, 2.5, 2.5, 'tf_slice:twilight_oak_leaves', rng, 0)
    return structure, center, base

def build(root):
    from build_ruin_structures import write_mcstructure
    from build_swamp_features import native_structure_feature, offset_feature, weighted_selector_feature
    from swamp_tree_placement import structure_tree_documents, TREE_GROUND, TREE_REPLACEABLE
    root = Path(root); bp = root / 'TwilightBossSliceB'
    features, rules = bp / 'netease_features', bp / 'netease_feature_rules'
    features.mkdir(parents=True, exist_ok=True); rules.mkdir(parents=True, exist_ok=True)
    documents = feature_documents()
    for kind, savannah in [('forest_canopy_oak', False), ('savannah_canopy_oak', True)]:
        prefix = kind + '_tree'
        documents.update(structure_tree_documents(prefix, 'tf_slice:twilight_oak_log', TREE_GROUND, TREE_REPLACEABLE, 4))
        for variant in range(4):
            structure, center, base = canopy_oak_structure(variant, savannah)
            relative = 'tf_slice/forest_trees/%s/v%02d.mcstructure' % (kind, variant)
            target = bp / 'structures' / relative;target.parent.mkdir(parents=True, exist_ok=True)
            write_mcstructure(target, structure)
            stem = prefix + '_v%02d' % variant
            documents[stem + '_structure_feature.json'] = native_structure_feature(stem + '_structure_feature', relative.removesuffix('.mcstructure').replace('tf_slice/', 'tf_slice:', 1))
            documents[stem + '_offset_feature.json'] = offset_feature(stem + '_offset_feature', stem + '_structure_feature', -center, -base, -center)
        name = kind + '_selector_feature'
        documents[name + '.json'] = weighted_selector_feature(name, [(prefix + '_v%02d_sequence_feature' % i, 1) for i in range(4)])
    for folder, docs in [(features, documents), (rules, rule_documents())]:
        for name, value in docs.items():
            (folder / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    # Retire exactly the combined profiles; keep unrelated features and rules.
    for name in LEGACY_RULES:
        if (rules / name).is_file():
            (rules / name).unlink()
    return {'features': len(documents), 'rules': len(rule_documents()), 'structures': 8, 'retired_rules': list(LEGACY_RULES)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--acknowledge-source-pack-write', action='store_true')
    args = parser.parse_args()
    if args.output_root.resolve() == Path(__file__).resolve().parents[1] and not args.acknowledge_source_pack_write:
        parser.error('canonical generated-artifact writes require explicit acknowledgement')
    print(json.dumps(build(args.output_root)))
