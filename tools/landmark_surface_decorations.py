#!/usr/bin/env python3
"""Project biome decorators onto surfaces written by landmark structures."""

import json
from pathlib import Path


LANDMARK_SURFACE_RAISE = 64
WRAPPER_SUFFIX = "_landmark_surface_project_feature"
LEGACY_WRAPPER_SUFFIXES = (
    "_landmark_surface_search_feature",
    "_landmark_surface_snap_feature",
)
DIRECT_LARGE_STRUCTURE_RULES = frozenset()
DIRECT_TREE_RULES = frozenset(
    (
        "dark_forest_tree_profile_feature_rule",
        "dark_forest_center_tree_profile_feature_rule",
    )
)
POST_LANDMARK_ENVIRONMENT_RULES = frozenset(
    (
        "enchanted_fallen_log_feature_rule",
        "fallen_hollow_log_feature_rule",
        "hollow_stump_feature_rule",
        "hollow_tree_feature_rule",
        "mushroom_canopy_dense_feature_rule",
        "mushroom_canopy_sparse_feature_rule",
    )
)


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, document):
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _feature_identifier(document):
    for feature_type, body in document.items():
        if not isinstance(body, dict):
            continue
        identifier = body.get("description", {}).get("identifier")
        if identifier:
            return identifier
    return None


def _referenced_features(value, known_identifiers):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "identifier":
                continue
            for reference in _referenced_features(child, known_identifiers):
                yield reference
    elif isinstance(value, list):
        for child in value:
            for reference in _referenced_features(child, known_identifiers):
                yield reference
    elif isinstance(value, str) and value in known_identifiers:
        yield value


def _raised_y(expression):
    expression = str(expression)
    suffix = ") + %d" % LANDMARK_SURFACE_RAISE
    if expression.startswith("(") and expression.endswith(suffix):
        return expression
    return "(%s) + %d" % (expression, LANDMARK_SURFACE_RAISE)


def _unraised_y(expression):
    expression = str(expression)
    suffix = ") + %d" % LANDMARK_SURFACE_RAISE
    if expression.startswith("(") and expression.endswith(suffix):
        return expression[1 : -len(suffix)]
    return expression


def _is_tree_structure_reference(value):
    reference = str(value).lower()
    return bool(
        reference
        and reference != "tf_slice:hollow_tree_chunk_trigger"
        and not reference.startswith("tf_slice:ruins/")
        and "tree" in reference
    )


def normalize_landmark_surface_decorations(root):
    """Make native vegetation follow final structure-written terrain.

    NetEase evaluates ``query.get_height_at`` against the terrain height map
    that existed before a structure feature raised or lowered the column.
    Tree candidates therefore start inside a hollow hill, while projected
    groundcover starts too low to see its new roof. Tree-bearing rules are
    lifted and projected to the final floor before the tree feature is executed
    once; existing projected patches are lifted so their own floor projection
    starts above the final surface. Biome filters, iteration counts, selectors,
    and palettes remain unchanged.
    """
    root = Path(root)
    feature_dir = root / "TwilightBossSliceB" / "netease_features"
    rule_dir = root / "TwilightBossSliceB" / "netease_feature_rules"

    wrapper_paths = set(feature_dir.glob("*%s.json" % WRAPPER_SUFFIX))
    for suffix in LEGACY_WRAPPER_SUFFIXES:
        wrapper_paths.update(feature_dir.glob("*%s.json" % suffix))
    wrapper_paths = sorted(wrapper_paths)
    wrapper_targets = {}
    for path in wrapper_paths:
        document = _load_json(path)
        search = document.get("minecraft:search_feature", {})
        snap = document.get("minecraft:snap_to_surface_feature", {})
        projection = document.get("minecraft:scatter_feature", {})
        wrapper = projection or snap or search
        identifier = wrapper.get("description", {}).get("identifier")
        target = (
            projection.get("places_feature")
            or snap.get("feature_to_snap")
            or search.get("places_feature")
        )
        if identifier and target:
            wrapper_targets[identifier] = target

    rule_paths = sorted(rule_dir.glob("*.json"))
    rule_documents = {}
    for path in rule_paths:
        document = _load_json(path)
        body = document.get("minecraft:feature_rules")
        if body is not None:
            placed = body.get("description", {}).get("places_feature")
            if placed in wrapper_targets:
                body["description"]["places_feature"] = wrapper_targets[placed]
                distribution = body.get("distribution", {})
                if "y" in distribution:
                    distribution["y"] = _unraised_y(distribution["y"])
        rule_documents[path] = document

    for path in wrapper_paths:
        path.unlink()

    feature_documents = {}
    for path in sorted(feature_dir.glob("*.json")):
        document = _load_json(path)
        identifier = _feature_identifier(document)
        if identifier:
            feature_documents[identifier] = document

    known_identifiers = set(feature_documents)
    tree_identifiers = {
        identifier
        for identifier, document in feature_documents.items()
        if "minecraft:tree_feature" in document
        or _is_tree_structure_reference(
            document.get("netease:structure_feature", {}).get(
                "places_structure", ""
            )
        )
    }
    tree_memo = {}
    ruin_structure_identifiers = {
        identifier
        for identifier, document in feature_documents.items()
        if str(
            document.get("netease:structure_feature", {}).get(
                "places_structure", ""
            )
        ).startswith("tf_slice:ruins/")
    }
    ruin_memo = {}

    def reaches_tree(identifier, visiting=None):
        if identifier in tree_identifiers:
            return True
        if identifier in tree_memo:
            return tree_memo[identifier]
        document = feature_documents.get(identifier)
        if document is None:
            return False
        visiting = set(visiting or ())
        if identifier in visiting:
            return False
        visiting.add(identifier)
        result = any(
            reaches_tree(reference, visiting)
            for reference in _referenced_features(document, known_identifiers)
        )
        tree_memo[identifier] = result
        return result

    def reaches_ruin_structure(identifier, visiting=None):
        if identifier in ruin_structure_identifiers:
            return True
        if identifier in ruin_memo:
            return ruin_memo[identifier]
        document = feature_documents.get(identifier)
        if document is None:
            return False
        visiting = set(visiting or ())
        if identifier in visiting:
            return False
        visiting.add(identifier)
        result = any(
            reaches_ruin_structure(reference, visiting)
            for reference in _referenced_features(document, known_identifiers)
        )
        ruin_memo[identifier] = result
        return result

    tree_rules = 0
    projected_patches = 0
    for path, document in rule_documents.items():
        body = document.get("minecraft:feature_rules")
        if body is None or body.get("conditions", {}).get(
            "placement_pass"
        ) not in ("surface_pass", "after_surface_pass"):
            continue
        distribution = body.get("distribution", {})
        y_expression = distribution.get("y")
        if not isinstance(y_expression, str) or "query.get_height_at" not in y_expression:
            continue

        placed = body.get("description", {}).get("places_feature")
        if reaches_ruin_structure(placed):
            body["conditions"]["placement_pass"] = (
                "after_surface_pass"
                if path.stem in POST_LANDMARK_ENVIRONMENT_RULES
                else "surface_pass"
            )
            distribution["y"] = _unraised_y(y_expression)
            _write_json(path, document)
            continue
        if path.stem in DIRECT_LARGE_STRUCTURE_RULES:
            # Large structure selectors stay direct. Even a floor projection
            # would add avoidable native work to a 25x25x25 structure chain.
            search = feature_documents.get(placed, {}).get(
                "minecraft:search_feature"
            )
            if search is not None:
                placed = search.get("places_feature", placed)
                body["description"]["places_feature"] = placed
            snap = feature_documents.get(placed, {}).get(
                "minecraft:snap_to_surface_feature"
            )
            if snap is not None:
                placed = snap.get("feature_to_snap", placed)
                body["description"]["places_feature"] = placed
            projection = feature_documents.get(placed, {}).get(
                "minecraft:scatter_feature"
            )
            if projection is not None and projection.get(
                "project_input_to_floor"
            ):
                placed = projection.get("places_feature", placed)
                body["description"]["places_feature"] = placed
            distribution["y"] = _unraised_y(y_expression)
            body["conditions"]["placement_pass"] = "after_surface_pass"
            _write_json(path, document)
            continue
        if path.stem in DIRECT_TREE_RULES:
            # Dark Forest trees already scatter directly from the feature
            # rule. Re-wrapping them recreates the nested Chunk PP graph that
            # fail-fasts NetEase while the route streams in.
            body["conditions"]["placement_pass"] = "after_surface_pass"
            distribution["y"] = _unraised_y(y_expression)
            _write_json(path, document)
            continue
        if reaches_tree(placed):
            local_name = path.stem
            if local_name.endswith("_feature_rule"):
                local_name = local_name[: -len("_feature_rule")]
            wrapper_local_name = local_name + WRAPPER_SUFFIX
            wrapper_identifier = "tf_slice:%s" % wrapper_local_name
            wrapper = {
                "format_version": "1.21.10",
                "minecraft:scatter_feature": {
                    "description": {"identifier": wrapper_identifier},
                    "places_feature": placed,
                    "project_input_to_floor": True,
                    "distribution": {
                        "iterations": 1,
                        "coordinate_eval_order": "xzy",
                        "x": 0,
                        "y": 0,
                        "z": 0,
                    },
                },
            }
            _write_json(
                feature_dir / (wrapper_local_name + ".json"), wrapper
            )
            body["description"]["places_feature"] = wrapper_identifier
            body["conditions"]["placement_pass"] = "after_surface_pass"
            distribution["y"] = _raised_y(y_expression)
            tree_rules += 1
        else:
            feature = feature_documents.get(placed, {}).get(
                "minecraft:scatter_feature"
            )
            if feature is None or not feature.get("project_input_to_floor"):
                continue
            body["conditions"]["placement_pass"] = "after_surface_pass"
            distribution["y"] = _raised_y(y_expression)
            projected_patches += 1
        _write_json(path, document)

    return {
        "treeRules": tree_rules,
        "projectedPatches": projected_patches,
        "surfaceRaise": LANDMARK_SURFACE_RAISE,
        "projection": "project_input_to_floor",
    }
