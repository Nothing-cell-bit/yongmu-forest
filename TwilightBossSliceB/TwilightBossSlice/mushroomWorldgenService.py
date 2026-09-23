# -*- coding: utf-8 -*-
"""Deferred, chunk-safe placement for giant canopy mushrooms."""

from __future__ import print_function

import collections
import copy
import json

import TwilightBossSlice.mushroom_catalog_data as mushroom_catalog_data
import TwilightBossSlice.mushroom_worldgen_logic as mushroom_logic


LEDGER_KEY = "tf_slice:mushroom_canopies_v2"
WORLD_SEED_KEY = "tf_slice:ruin_world_seed_v1"
MAX_HANDOFFS = 512
MAX_HANDOFFS_PER_TICK = 12
MAX_SURFACE_SCAN = 96
MAX_LEDGER_RECORDS = 4096
MAX_RETRIES = 3
PLAYER_RADIUS = 256
NOOP_STRUCTURE = "tf_slice:ruin_landmark_noop"
try:
    INTEGER_TYPES = (int, long)
except NameError:  # pragma: no cover - Python 3 test tooling
    INTEGER_TYPES = (int,)


def _load_catalog():
    document = json.loads(mushroom_catalog_data.CATALOG_JSON)
    return document["variants"]


class MushroomWorldgenService(object):
    """Turn empty 1x1 worldgen tokens into validated structure pieces."""

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
        self._catalog = _load_catalog()
        self._world_seed = self._load_world_seed()
        self._ledger = self._load_ledger()
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
        return mushroom_logic.stable_seed(self._level_id)

    def _load_ledger(self):
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
        self._prune_ledger()
        try:
            self._extra.SetExtraData(
                LEDGER_KEY,
                copy.deepcopy(self._ledger),
                False,
            )
            return self._extra.SaveExtraData()
        except Exception as error:
            print(
                "[TwilightBossSlice] mushroom ledger save failed:",
                error,
            )
            return False

    def _prune_ledger(self):
        if len(self._ledger) <= MAX_LEDGER_RECORDS:
            return
        terminal = sorted(
            (
                (int(job.get("sequence", 0)), key)
                for key, job in self._ledger.items()
                if job.get("state") in ("complete", "skipped", "failed")
            )
        )
        remove_count = len(self._ledger) - MAX_LEDGER_RECORDS
        for _sequence, key in terminal[:remove_count]:
            self._ledger.pop(key, None)

    def _register_whitelist(self):
        structure_names = set(mushroom_logic.TRIGGER_KINDS)
        structure_names.add(NOOP_STRUCTURE)
        for structure_name in sorted(structure_names):
            try:
                if self._feature.AddNeteaseFeatureWhiteList(structure_name):
                    self._whitelisted.append(structure_name)
            except Exception as error:
                print (
                    "[TwilightBossSlice] mushroom feature whitelist failed:",
                    structure_name,
                    error,
                )

    def destroy(self):
        for structure_name in self._whitelisted:
            try:
                self._feature.RemoveNeteaseFeatureWhiteList(structure_name)
            except Exception:
                pass
        self._whitelisted = []

    def on_structure_feature_event(self, args):
        """Replace a token with an empty structure and copy only event data."""
        structure_name = str(args.get("structureName", ""))
        kind = mushroom_logic.TRIGGER_KINDS.get(structure_name)
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
        if biome_name and biome_name not in mushroom_logic.MUSHROOM_BIOMES:
            return
        key = mushroom_logic.candidate_key(kind, root_x, root_z)
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
        available = min(len(self._handoffs), MAX_HANDOFFS_PER_TICK)
        for _index in range(available):
            record = self._handoffs.popleft()
            key = record["key"]
            self._handoff_keys.discard(key)
            if key in self._ledger:
                continue
            kind = record["kind"]
            variant_index = mushroom_logic.variant_index(
                kind,
                self._world_seed,
                record["rootX"],
                record["rootZ"],
            )
            self._sequence += 1
            self._ledger[key] = {
                "state": "planned",
                "kind": kind,
                "rootX": int(record["rootX"]),
                "eventY": int(record["eventY"]),
                "rootZ": int(record["rootZ"]),
                "variant": variant_index,
                "nextPiece": 0,
                "retries": 0,
                "sequence": self._sequence,
            }
            changed = True
        if changed:
            self._persist()

    def _block_name(self, x, y, z):
        try:
            block = self._block.GetBlockNew(
                (int(x), int(y), int(z)),
                self._dimension_id,
            )
        except Exception:
            return None
        if isinstance(block, dict):
            value = block.get("name")
            return str(value) if value else None
        if isinstance(block, (tuple, list)) and block:
            return str(block[0])
        return None

    def _surface_y(self, x, z):
        try:
            top_y = self._block.GetTopBlockHeight(
                (int(x), int(z)),
                self._dimension_id,
            )
        except Exception:
            return None
        if top_y is None:
            return None
        top_y = int(top_y)
        minimum_y = max(0, top_y - MAX_SURFACE_SCAN)
        for y in range(top_y, minimum_y - 1, -1):
            block_name = self._block_name(x, y, z)
            if block_name is None:
                continue
            if mushroom_logic.is_surface_decoration(block_name):
                continue
            return y
        return None

    def _biome_name(self, x, z):
        try:
            value = self._biome.GetBiomeName(
                (int(x), 64, int(z)),
                self._dimension_id,
            )
            return str(value) if value else None
        except Exception:
            return None

    def _chunk_ready(self, chunk_x, chunk_z, check_y):
        checker = getattr(self._chunk, "CheckChunkState", None)
        if checker is None:
            return False
        check_position = (
            int(chunk_x) * 16 + 8,
            int(check_y),
            int(chunk_z) * 16 + 8,
        )
        try:
            chunk_ready = bool(
                checker(self._dimension_id, check_position)
            )
        except Exception:
            return False
        if not chunk_ready:
            return False
        try:
            block = self._block.GetBlockNew(
                check_position,
                self._dimension_id,
            )
        except Exception:
            return False
        if isinstance(block, dict):
            return bool(block.get("name"))
        return bool(isinstance(block, (tuple, list)) and block)

    def _all_chunks_ready(self, origin, bounds):
        for chunk_x, chunk_z in mushroom_logic.required_chunks(
            origin, bounds
        ):
            if not self._chunk_ready(chunk_x, chunk_z, origin[1]):
                return False
        return True

    def _near_player(self, job, players):
        radius_squared = PLAYER_RADIUS * PLAYER_RADIUS
        for player in players or []:
            try:
                if int(player.get("dimensionId", -1)) != self._dimension_id:
                    continue
                position = player["position"]
                delta_x = float(position[0]) - int(job["rootX"])
                delta_z = float(position[2]) - int(job["rootZ"])
            except (IndexError, KeyError, TypeError, ValueError):
                continue
            if delta_x * delta_x + delta_z * delta_z <= radius_squared:
                return True
        return False

    def _skip(self, job, reason):
        job["state"] = "skipped"
        job["reason"] = str(reason)
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
        if biome_name not in mushroom_logic.MUSHROOM_BIOMES:
            self._skip(job, "wrong_biome")
            return True
        surface_y = self._surface_y(root_x, root_z)
        if surface_y is None:
            return False
        support_name = self._block_name(root_x, surface_y, root_z)
        if not mushroom_logic.is_ground_support(support_name):
            self._skip(job, "unsupported_ground")
            return True
        root = (root_x, surface_y + 1, root_z)
        origin = mushroom_logic.template_origin(root)
        variants = self._catalog.get(str(job["kind"]), [])
        variant_index = int(job.get("variant", 0))
        if not 0 <= variant_index < len(variants):
            self._skip(job, "missing_variant")
            return True
        variant = variants[variant_index]
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
            if not mushroom_logic.is_canopy_replaceable(block_name):
                self._skip(job, "blocked_clearance")
                return True

        job["root"] = list(root)
        job["origin"] = list(origin)
        job["state"] = "placing"
        job["nextPiece"] = 0
        self._persist()
        return True

    def _place_next_piece(self, job):
        variants = self._catalog.get(str(job["kind"]), [])
        variant_index = int(job.get("variant", 0))
        if not 0 <= variant_index < len(variants):
            self._skip(job, "missing_variant")
            return
        pieces = variants[variant_index]["pieces"]
        next_piece = int(job.get("nextPiece", 0))
        if next_piece >= len(pieces):
            job["state"] = "complete"
            self._persist()
            return
        piece = pieces[next_piece]
        origin = job["origin"]
        offset = piece["offset"]
        position = (
            int(origin[0]) + int(offset[0]),
            int(origin[1]) + int(offset[1]),
            int(origin[2]) + int(offset[2]),
        )
        try:
            result = self._game.PlaceStructure(
                None,
                position,
                str(piece["structure"]),
                self._dimension_id,
                0,
                0,
                0,
                True,
                False,
                0,
                100.0,
                variant_index,
            )
        except Exception as error:
            print(
                "[TwilightBossSlice] mushroom PlaceStructure failed:",
                error,
            )
            result = False
        if result is False:
            job["retries"] = int(job.get("retries", 0)) + 1
            if job["retries"] >= MAX_RETRIES:
                job["state"] = "failed"
                job["reason"] = "place_structure_failed"
            self._persist()
            return
        job["retries"] = 0
        job["nextPiece"] = next_piece + 1
        if job["nextPiece"] >= len(pieces):
            job["state"] = "complete"
        self._persist()

    def tick(self, _current_tick, players):
        self._drain_handoffs()
        jobs = sorted(
            (
                (key, job)
                for key, job in self._ledger.items()
                if job.get("state") in ("planned", "placing")
                and self._near_player(job, players)
            ),
            key=lambda item: (
                0 if item[1].get("state") == "placing" else 1,
                int(item[1].get("sequence", 0)),
            ),
        )
        if not jobs:
            return
        _key, job = jobs[0]
        if job.get("state") == "planned":
            if not self._prepare(job) or job.get("state") != "placing":
                return
        self._place_next_piece(job)

    def debug_status(self):
        counts = {}
        for job in self._ledger.values():
            state = str(job.get("state", "unknown"))
            counts[state] = counts.get(state, 0) + 1
        return {
            "ledger": counts,
            "handoffs": len(self._handoffs),
        }
