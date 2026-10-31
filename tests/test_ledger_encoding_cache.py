"""Exercise real ledger persistence, with only the SDK storage boundary faked."""
import base64
import copy
import json
import zlib

from test_structure_worldgen_handoff import SERVICE, FakeFactory


def service():
    factory = FakeFactory()
    result = SERVICE.StructureWorldgenService(factory, "level", 33027004)
    result._ledger = {
        "native:%d" % i: {"state": "complete", "pieces": [
            {"position": [i, j, -j], "done": True} for j in range(40)]}
        for i in range(80)
    }
    return result, factory


def raw_ledger(result):
    return zlib.decompress(base64.b64decode("".join(result._ledger_storage_shards())))


def reference(ledger):
    return json.dumps(ledger, ensure_ascii=True, separators=(",", ":"),
                      sort_keys=True).encode("utf-8")


def test_repeated_save_encodes_only_changed_records(monkeypatch):
    result, factory = service()
    assert result._persist()
    reference_size = len(reference(result._ledger))
    original = SERVICE.json.dumps
    work = []

    def observe(value, *args, **kwargs):
        encoded = original(value, *args, **kwargs)
        work.append(len(encoded))
        return encoded

    monkeypatch.setattr(SERVICE.json, "dumps", observe)
    result._ledger["native:3"]["pieces"][4]["done"] = False
    assert result._persist()
    assert result._persist()
    # A repeated save must not re-encode all 80 mostly unchanged records.
    assert sum(work) < reference_size // 4
    assert factory.extra.save_count == 3
    assert raw_ledger(result) == reference(result._ledger)


def test_payload_bytes_follow_nested_mutation_deletion_and_type_changes():
    result, factory = service()
    for action in range(6):
        if action == 1:
            result._ledger["native:2"]["pieces"][0]["done"] = 1
        elif action == 2:
            result._ledger["native:2"]["pieces"][0]["done"] = 1.0
        elif action == 3:
            del result._ledger["native:1"]
        elif action == 4:
            result._ledger["新记录"] = {"escaped": "\\\"\n", "items": [None, False, -0.0]}
        elif action == 5:
            result._ledger = copy.deepcopy(result._ledger)
        assert raw_ledger(result) == reference(result._ledger)
        assert result._persist()
        restored = SERVICE.StructureWorldgenService(factory, "level", 33027004)
        assert restored._ledger == result._ledger


def test_failed_save_retries_latest_nested_state():
    result, factory = service()
    assert result._persist()
    factory.extra.save_result = False
    result._ledger["native:0"]["pieces"][0]["done"] = False
    assert result._persist() is False
    result._ledger["native:0"]["pieces"].append({"position": [-5, 60, 2]})
    factory.extra.save_result = True
    assert result._persist()
    restored = SERVICE.StructureWorldgenService(factory, "level", 33027004)
    assert restored._ledger == result._ledger


def test_cache_limits_and_non_string_key_fallback():
    from TwilightBossSlice.ledger_json_cache import LedgerJsonCache
    cache = LedgerJsonCache(max_records=2, max_characters=200)
    ledger = {"a": [1], "b": [2], "c": [3]}
    assert cache.encode(ledger).encode("utf-8") == reference(ledger)
    assert len(cache.records) <= 2
    del ledger["a"]
    cache.encode(ledger)
    assert "a" not in cache.records
    ledger["b"] = ["x" * 300]
    assert cache.encode(ledger).encode("utf-8") == reference(ledger)
    assert "b" not in cache.records
    assert cache.encode({1: "one"}).encode("utf-8") == reference({1: "one"})
    assert cache.records == {}
    assert cache.encode({}) == "{}"
