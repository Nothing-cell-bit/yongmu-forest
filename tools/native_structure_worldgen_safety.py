#!/usr/bin/env python3
"""Keep native structures active without overlapping landmark surface work."""

import ast
import json
from pathlib import Path


DISABLED_TAG = "tf_slice_native_structure_worldgen_disabled"
STAGING_BLOCK_X = 8192
STAGING_BLOCK_Z = 8192
STAGING_GUARD_RADIUS = 512
STAGING_GUARD_MARKER = "variable.originx - %d" % STAGING_BLOCK_X
LANDMARK_GRID_BLOCKS = 256
LANDMARK_ENVELOPE_RADIUS = 80
LANDMARK_RULE_PREFIX = "tf_slice:ruin_landmark_surface_"
LANDMARK_GUARD_MARKER = (
    "math.floor((variable.originx + 128) / %d)" % LANDMARK_GRID_BLOCKS
)


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, document):
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _component(document):
    for component_name, body in document.items():
        if component_name == "format_version" or not isinstance(body, dict):
            continue
        identifier = body.get("description", {}).get("identifier")
        if identifier:
            return identifier, component_name, body
    return None, None, None


def _nested_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            for nested in _nested_strings(item):
                yield nested
    elif isinstance(value, dict):
        for key, item in value.items():
            if key == "identifier":
                continue
            for nested in _nested_strings(item):
                yield nested


def _strip_disabled_filter(value):
    if isinstance(value, list):
        cleaned = []
        for item in value:
            item = _strip_disabled_filter(item)
            if item is not None:
                cleaned.append(item)
        return cleaned
    if not isinstance(value, dict):
        return value
    if value.get("value") == DISABLED_TAG:
        return None
    cleaned = {}
    for key, item in value.items():
        item = _strip_disabled_filter(item)
        if item is not None:
            cleaned[key] = item
    return cleaned


def _landmark_envelope_expression():
    center_x = (
        "(math.floor((variable.originx + 128) / %d) * %d)"
        % (LANDMARK_GRID_BLOCKS, LANDMARK_GRID_BLOCKS)
    )
    center_z = (
        "(math.floor((variable.originz + 128) / %d) * %d)"
        % (LANDMARK_GRID_BLOCKS, LANDMARK_GRID_BLOCKS)
    )
    return (
        "(math.abs(variable.originx - %s) <= %d && "
        "math.abs(variable.originz - %s) <= %d)"
        % (
            center_x,
            LANDMARK_ENVELOPE_RADIUS,
            center_z,
            LANDMARK_ENVELOPE_RADIUS,
        )
    )


def _direct_entry_enabled(root):
    """Read the literal entry mode without importing the ModSDK config."""
    config_path = (
        Path(root)
        / "TwilightBossSliceB"
        / "TwilightBossSlice"
        / "config.py"
    )
    module = ast.parse(
        config_path.read_text(encoding="utf-8"),
        filename=str(config_path),
    )
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name)
            and target.id == "PORTAL_DIRECT_ENTRY_ENABLED"
            for target in statement.targets
        ):
            continue
        if isinstance(statement.value, ast.Constant) and isinstance(
            statement.value.value,
            bool,
        ):
            return statement.value.value
        raise ValueError(
            "PORTAL_DIRECT_ENTRY_ENABLED must be a literal bool: %s"
            % config_path
        )
    raise ValueError(
        "PORTAL_DIRECT_ENTRY_ENABLED is missing from %s" % config_path
    )


def _guarded_iterations(
    iterations,
    exclude_landmark_envelope=False,
    exclude_staging_area=True,
):
    base = base_iterations(iterations)
    expression = str(base)
    guarded = False
    if exclude_landmark_envelope:
        expression = "(%s ? 0 : (%s))" % (
            _landmark_envelope_expression(),
            expression,
        )
        guarded = True
    if exclude_staging_area:
        inside_staging = (
            "((variable.originx - %d) >= -%d && "
            "(variable.originx - %d) <= %d && "
            "(variable.originz - %d) >= -%d && "
            "(variable.originz - %d) <= %d)"
            % (
                STAGING_BLOCK_X,
                STAGING_GUARD_RADIUS,
                STAGING_BLOCK_X,
                STAGING_GUARD_RADIUS,
                STAGING_BLOCK_Z,
                STAGING_GUARD_RADIUS,
                STAGING_BLOCK_Z,
                STAGING_GUARD_RADIUS,
            )
        )
        expression = "(%s ? 0 : (%s))" % (inside_staging, expression)
        guarded = True
    return expression if guarded else base


def base_iterations(iterations):
    """Return the unchanged budget nested inside this module's guards."""
    if not isinstance(iterations, str):
        return iterations
    separator = "? 0 : ("
    expression = iterations
    for _index in range(3):
        if separator not in expression or not expression.endswith("))"):
            break
        if not any(
            marker in expression
            for marker in (STAGING_GUARD_MARKER, LANDMARK_GUARD_MARKER)
        ):
            break
        start = expression.find(separator) + len(separator)
        expression = expression[start:-2]
    try:
        parsed = json.loads(expression)
    except (TypeError, ValueError):
        return expression
    return parsed if isinstance(parsed, (int, float)) else expression


def guard_native_structure_rules(root):
    """Apply only the native guards required by the configured entry mode."""
    root = Path(root)
    feature_dir = root / "TwilightBossSliceB" / "netease_features"
    rule_dir = root / "TwilightBossSliceB" / "netease_feature_rules"
    staging_guard_enabled = not _direct_entry_enabled(root)

    features = {}
    feature_types = {}
    for path in sorted(feature_dir.glob("*.json")):
        identifier, component_name, body = _component(_load_json(path))
        if identifier:
            features[identifier] = body
            feature_types[identifier] = component_name

    known = set(features)
    dependencies = {
        identifier: {
            value for value in _nested_strings(body) if value in known
        }
        for identifier, body in features.items()
    }
    memo = {}

    def reaches_native_structure(identifier, visiting=None):
        if feature_types.get(identifier) == "netease:structure_feature":
            return True
        if identifier in memo:
            return memo[identifier]
        visiting = set(visiting or ())
        if identifier in visiting:
            return False
        visiting.add(identifier)
        result = any(
            reaches_native_structure(child, visiting)
            for child in dependencies.get(identifier, ())
        )
        memo[identifier] = result
        return result

    guarded = 0
    updated = 0
    landmark_envelope_guarded = 0
    for path in sorted(rule_dir.glob("*.json")):
        document = _load_json(path)
        rule = document.get("minecraft:feature_rules")
        if not rule or not reaches_native_structure(
            rule.get("description", {}).get("places_feature")
        ):
            continue
        guarded += 1
        before = json.dumps(document, sort_keys=True)
        conditions = rule.setdefault("conditions", {})
        conditions["minecraft:biome_filter"] = _strip_disabled_filter(
            conditions.get("minecraft:biome_filter", [])
        )
        distribution = rule.setdefault("distribution", {})
        identifier = str(rule.get("description", {}).get("identifier", ""))
        exclude_landmark_envelope = (
            conditions.get("placement_pass") == "surface_pass"
            and not identifier.startswith(LANDMARK_RULE_PREFIX)
        )
        if exclude_landmark_envelope:
            landmark_envelope_guarded += 1
        distribution["iterations"] = _guarded_iterations(
            distribution.get("iterations", 1),
            exclude_landmark_envelope=exclude_landmark_envelope,
            exclude_staging_area=staging_guard_enabled,
        )
        if json.dumps(document, sort_keys=True) != before:
            _write_json(path, document)
            updated += 1

    return {
        "guardedRules": guarded,
        "landmarkEnvelopeRules": landmark_envelope_guarded,
        "stagingGuardEnabled": staging_guard_enabled,
        "updatedRules": updated,
    }


if __name__ == "__main__":
    result = guard_native_structure_rules(Path(__file__).resolve().parents[1])
    print(
        "guarded %d native structure rules (%d updated; staging guard %s)"
        % (
            result["guardedRules"],
            result["updatedRules"],
            "enabled" if result["stagingGuardEnabled"] else "disabled",
        )
    )
