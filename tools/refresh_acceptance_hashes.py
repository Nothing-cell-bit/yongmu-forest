#!/usr/bin/env python3
"""Refresh only production-file hashes in existing acceptance evidence.

This helper deliberately leaves statuses, automated claims, source locks and
runtime evidence untouched.  It is intended for the mechanical bookkeeping
step after production files have changed and their tests have passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def refresh_hash_collection(collection: object, evidence_path: Path) -> int:
    refreshed = 0
    if isinstance(collection, dict):
        rows = collection.items()
    elif isinstance(collection, list):
        rows = (
            (row.get("path"), row)
            for row in collection
            if isinstance(row, dict)
        )
    else:
        raise ValueError(
            "%s contains an invalid production_hashes value" % evidence_path
        )

    for relative_path, target in rows:
        if not relative_path:
            continue
        production_path = REPO_ROOT / str(relative_path)
        if not production_path.is_file():
            raise FileNotFoundError(
                "%s references missing production file %s"
                % (evidence_path, production_path)
            )
        digest = sha256(production_path)
        if isinstance(target, dict):
            target["sha256"] = digest
        else:
            collection[relative_path] = digest
        refreshed += 1
    return refreshed


def refresh_node(node: object, evidence_path: Path) -> int:
    refreshed = 0
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "production_hashes":
                refreshed += refresh_hash_collection(value, evidence_path)
            else:
                refreshed += refresh_node(value, evidence_path)
    elif isinstance(node, list):
        for value in node:
            refreshed += refresh_node(value, evidence_path)
    return refreshed


def evidence_paths(include_route: bool) -> list[Path]:
    paths = sorted((REPO_ROOT / "model_acceptance" / "behavior").glob("*.json"))
    paths.extend(sorted((REPO_ROOT / "boss_acceptance").glob("*.json")))
    if include_route:
        return paths
    route_names = {
        "hydra.json",
        "minoshroom.json",
        "minotaur.json",
        "maze_slime.json",
        "mosquito_swarm.json",
        "hydra_head.json",
        "hydra_mortar.json",
    }
    return [path for path in paths if path.name not in route_names]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-route",
        action="store_true",
        help="also refresh generated Hydra-route acceptance files",
    )
    args = parser.parse_args()

    file_count = 0
    hash_count = 0
    for path in evidence_paths(args.include_route):
        payload = json.loads(path.read_text(encoding="utf-8"))
        refreshed = refresh_node(payload, path)
        if not refreshed:
            continue
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        file_count += 1
        hash_count += refreshed

    print("refreshed %d production hashes in %d evidence files" % (hash_count, file_count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
