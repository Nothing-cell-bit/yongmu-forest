"""Exercise map caching with a reduced embedded-Python hash implementation."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from TwilightBossSlice import magic_map_bitmap_cache as bitmap


def test_maze_cache_does_not_depend_on_sha256(tmp_path, monkeypatch):
    import hashlib
    def unavailable(*args, **kwargs):
        raise ValueError('unsupported hash type sha256')
    monkeypatch.setattr(hashlib, 'sha256', unavailable)
    cache = bitmap.MagicMapBitmapCache(str(tmp_path), session_token='embedded')
    first = cache.render('tfmz:v1:264,520:266:35:522', {0: 'unknown', 1: 'clearing'})
    second = cache.render('tfmz:v1:264,520:266:42:522', {0: 'clearing'})
    assert first and second and first != second
    assert Path(first).is_file() and Path(second).is_file()
    assert cache.render('tfmz:v1:264,520:266:35:522', {0: 'unknown', 1: 'clearing'}) == first


def test_maze_write_error_is_available_in_memory_without_file_diagnostics(tmp_path, monkeypatch):
    cache = bitmap.MagicMapBitmapCache(str(tmp_path), session_token='error')
    def fail(*args):
        raise IOError('test texture write failure')
    monkeypatch.setattr(cache, '_write_bitmap', fail)
    for _ in range(50):
        assert cache.render('tfmz:v1:264,520:266:35:522', {0: 'unknown'}) is None
    log = tmp_path / 'maze_map_diagnostics.jsonl'
    assert not log.exists()
    assert 'test texture write failure' in cache.last_error
