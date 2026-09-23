# -*- coding: utf-8 -*-
"""Root-anchored, chunk-safe placement for Enchanted Forest trees."""

from __future__ import print_function

import collections
import copy
import json

import TwilightBossSlice.enchanted_tree_catalog_data as catalog_data
import TwilightBossSlice.enchanted_tree_worldgen_logic as tree_logic
from TwilightBossSlice.mushroomWorldgenService import (
    INTEGER_TYPES,
    MushroomWorldgenService,
    WORLD_SEED_KEY,
)


LEDGER_KEY = "tf_slice:enchanted_trees_v1"
MAX_HANDOFFS = 512
MAX_HANDOFFS_PER_TICK = 12
MAX_LEDGER_RECORDS = 4096
NOOP_STRUCTURE = "tf_slice:ruin_landmark_noop"


class EnchantedTreeWorldgenService(MushroomWorldgenService):
    """Replace empty one-block tokens with terrain-anchored trees."""

    def __init__(self, component_factory, level_id, dimension_id):
        self._factory = component_factory
        self._level_id = level_id
        self._dimension_id = int(dimension_id)
        self._extra = component_factory.CreateExtraData(level_id)
        self._chunk = component_factory.CreateChunkSource(level_id)
        self._game = component_factory.CreateGame(level_id)
        self._biome = component_factory.CreateBiome(level_id)
        self._block = component_factory.CreateBlockInfo(level_id)
        self._feature = component_factory.CreateFeature(level_id)
        self._catalog = json.loads(catalog_data.CATALOG_JSON)["variants"]
        self._world_seed = self._load_world_seed()
        self._ledger = self._load_tree_ledger()
        self._handoffs = collections.deque()
        self._handoff_keys = set()
        self._sequence = max(
            [int(job.get("sequence", 0)) for job in self._ledger.values()]
            or [0]
        )
        self._whitelisted = []
        self._register_whitelist()

    def _load_world_seed(self):
        try:
            value = self._extra.GetExtraData(WORLD_SEED_KEY)
        except Exception:
            value = None
        if isinstance(value, INTEGER_TYPES):
            return int(value)
        return tree_logic.stable_seed(self._level_id)

    def _load_tree_ledger(self):
        try:
            value = self._extra.GetExtraData(LEDGER_KEY)
        except Exception:
            value = None
        if not isinstance(value, dict):
            return {}
        result = {}
        for key, job in value.items():
            if not isinstance(job, dict):
                continue
            copied = copy.deepcopy(job)
            if copied.get("state") == "placing":
                copied["state"] = "planned"
            result[str(key)] = copied
        return result

    def _persist(self):
        if len(self._ledger) > MAX_LEDGER_RECORDS:
            terminal = sorted(
                (
                    (int(job.get("sequence", 0)), key)
                    for key, job in self._ledger.items()
                    if job.get("state") in ("complete", "skipped", "failed")
                )
            )
            for _sequence, key in terminal[
                : len(self._ledger) - MAX_LEDGER_RECORDS
            ]:
                self._ledger.pop(key, None)
        try:
            self._extra.SetExtraData(
                LEDGER_KEY, copy.deepcopy(self._ledger), False
            )
            return self._extra.SaveExtraData()
        except Exception as error:
            print("[TwilightBossSlice] enchanted tree save failed:", error)
            return False

    def _register_whitelist(self):
        structure_names = set(tree_logic.TRIGGER_KINDS)
        structure_names.add(NOOP_STRUCTURE)
        for structure_name in sorted(structure_names):
            try:
                if self._feature.AddNeteaseFeatureWhiteList(structure_name):
                    self._whitelisted.append(structure_name)
            except Exception as error:
                print(
                    "[TwilightBossSlice] enchanted tree whitelist failed:",
                    structure_name,
                    error,
                )

    def on_structure_feature_event(self, args):
        structure_name = str(args.get("structureName", ""))
        kind = tree_logic.TRIGGER_KINDS.get(structure_name)
        if kind is None:
            return
        args["structureName"] = NOOP_STRUCTURE
        try:
            dimension_id = int(args.get("dimensionId", -1))
            root_x = int(args.get("x", 0))
            event_y = int(args.get("y", 0))
            root_z = int(args.get("z", 0))
        except (TypeError, ValueError):
            return
        if dimension_id != self._dimension_id:
            return
        biome_name = str(args.get("biomeName", ""))
        if biome_name and biome_name != tree_logic.ENCHANTED_BIOME:
            return
        key = tree_logic.candidate_key(kind, root_x, root_z)
        if (
            key in self._ledger
            or key in self._handoff_keys
            or len(self._handoffs) >= MAX_HANDOFFS
        ):
            return
        self._handoffs.append(
            {
                "key": key,
                "kind": kind,
                "rootX": root_x,
                "eventY": event_y,
                "rootZ": root_z,
            }
        )
        self._handoff_keys.add(key)

    def _drain_handoffs(self):
        changed = False
        for _index in range(
            min(len(self._handoffs), MAX_HANDOFFS_PER_TICK)
        ):
            record = self._handoffs.popleft()
            key = record["key"]
            self._handoff_keys.discard(key)
            if key in self._ledger:
                continue
            self._sequence += 1
            self._ledger[key] = {
                "state": "planned",
                "kind": record["kind"],
                "rootX": int(record["rootX"]),
                "eventY": int(record["eventY"]),
                "rootZ": int(record["rootZ"]),
                "variant": tree_logic.variant_index(
                    record["kind"],
                    self._world_seed,
                    record["rootX"],
                    record["rootZ"],
                ),
                "nextPiece": 0,
                "retries": 0,
                "sequence": self._sequence,
            }
            changed = True
        if changed:
            self._persist()

    def _prepare(self, job):
        root_x = int(job["rootX"])
        root_z = int(job["rootZ"])
        if not self._chunk_ready(
            root_x >> 4,
            root_z >> 4,
            int(job.get("eventY", 64)),
        ):
            return False
        biome_name = self._biome_name(root_x, root_z)
        if biome_name is None:
            return False
        if biome_name != tree_logic.ENCHANTED_BIOME:
            self._skip(job, "wrong_biome")
            return True
        surface_y = self._surface_y(root_x, root_z)
        if surface_y is None:
            return False
        support_name = self._block_name(root_x, surface_y, root_z)
        if not tree_logic.is_ground_support(support_name):
            self._skip(job, "unsupported_ground")
            return True
        variants = self._catalog.get(str(job["kind"]), [])
        variant_index = int(job.get("variant", 0))
        if not 0 <= variant_index < len(variants):
            self._skip(job, "missing_variant")
            return True
        variant = variants[variant_index]
        root = (root_x, surface_y + 1, root_z)
        origin = tree_logic.template_origin(root, variant["center"])
        if not self._all_chunks_ready(origin, variant["bounds"]):
            return False

        for local_x, local_y, local_z in variant["occupied"]:
            block_name = self._block_name(
                origin[0] + int(local_x),
                origin[1] + int(local_y),
                origin[2] + int(local_z),
            )
            if block_name is None:
                return False
            if not tree_logic.is_canopy_replaceable(block_name):
                self._skip(job, "blocked_clearance")
                return True

        job["root"] = list(root)
        job["origin"] = list(origin)
        job["state"] = "placing"
        job["nextPiece"] = 0
        self._persist()
        return True
