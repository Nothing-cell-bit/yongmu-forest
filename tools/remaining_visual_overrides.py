"""Source-owned routes for auxiliary artwork; never overrides vanilla globally."""
import json
from pathlib import Path

ART_RELATIVE = Path('resource_art/remaining_visuals/v1')

def _rewrite(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_rewrite(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite(item, mapping) for key, item in value.items()}
    return value

def apply_remaining_visual_overrides(path, value):
    path = Path(path)
    rp = next((p for p in path.parents if p.name == 'TwilightBossSliceR'), None)
    if rp is None:
        return value
    manifest = rp.parent / ART_RELATIVE / 'manifest.json'
    if not manifest.is_file():
        return value
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if not data.get('enabled'):
        return value
    relative = path.relative_to(rp).as_posix()
    if relative in data.get('excluded_documents', []):
        return value
    mapping = {entry['source_runtime_path']: entry['runtime_path'] for entry in data['entries']
               if entry.get('source_kind') != 'builtin-base'
               or relative in entry.get('scoped_documents', [])}
    mapping.update(data.get('scoped_routes', {}).get(relative, {}))
    return _rewrite(value, mapping)
