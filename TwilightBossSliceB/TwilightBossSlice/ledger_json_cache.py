# -*- coding: utf-8 -*-
"""Reuse JSON for unchanged plain-data ledger records; never skip a save."""
import json


class LedgerJsonCache(object):
    def __init__(self, max_records=256, max_characters=4 * 1024 * 1024):
        self.max_records = max_records
        self.max_characters = max_characters
        self.records = {}

    def encode(self, ledger):
        options = {"ensure_ascii": True, "separators": (",", ":"),
                   "sort_keys": True}
        if not all(isinstance(key, (str, type(u""))) for key in ledger):
            self.records = {}
            return json.dumps(ledger, **options)
        retained = {}
        characters = 0
        parts = []
        for key in sorted(ledger):
            value = ledger[key]
            # Ledger values contain only built-in JSON data. repr walks these
            # containers in native code on the target Python 2 runtime. It
            # detects nested edits and distinguishes True, 1 and 1.0, unlike
            # equality against a deep copy. Dict reordering only causes a miss.
            signature = repr(value)
            cached = self.records.get(key)
            if cached is not None and cached[0] == signature:
                encoded_key, encoded_value = cached[1:]
            else:
                encoded_key = json.dumps(key, **options)
                encoded_value = json.dumps(value, **options)
            parts.append(encoded_key + ":" + encoded_value)
            weight = len(signature) + len(encoded_key) + len(encoded_value)
            if (len(retained) < self.max_records
                    and characters + weight <= self.max_characters):
                retained[key] = (signature, encoded_key, encoded_value)
                characters += weight
        # Deleted records and entries exceeding the cap cannot accumulate.
        self.records = retained
        return "{" + ",".join(parts) + "}"
