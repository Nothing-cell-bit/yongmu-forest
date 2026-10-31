"""Source-owned, explicitly registered artwork routing for block resources.

Keep locked originals intact. A separate immutable asset bank supplies approved
artwork; only Twilight aliases get private copies of engine-owned materials.
This module never launches clients, deploys packs, or rebuilds structures.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from PIL import Image

ART_RELATIVE = Path('resource_art/block_beautification/v1')
PREFIX = 'textures/tf_beautified/'


def registry(project_root):
    bank = Path(project_root) / ART_RELATIVE
    path = bank / 'manifest.json'
    if not path.is_file():
        return bank, {'enabled':False,'entries':[]}
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema_version') != 1 or not isinstance(value.get('entries'),list):
        raise ValueError('Invalid block artwork registry: '+str(path))
    return bank, value


def _mapping(project_root):
    bank, data = registry(project_root)
    project = {}
    external = {}
    if not data.get('enabled'):
        return bank, project, external
    for entry in data['entries']:
        relative = Path(entry['output_relative'])
        if relative.is_absolute() or '..' in relative.parts or relative.suffix != '.png':
            raise ValueError('Artwork must use a relative PNG path')
        target = PREFIX + relative.as_posix()[:-4]
        collection = external if entry['source_kind'] == 'builtin-base' else project
        key = entry['source_runtime_path']
        if key in collection and collection[key] != target:
            raise ValueError('Ambiguous artwork route: '+key)
        collection[key] = target
    return bank, project, external


def _rewrite(value, mapping):
    if isinstance(value,str):
        return mapping.get(value,value)
    if isinstance(value,list):
        return [_rewrite(item,mapping) for item in value]
    if isinstance(value,dict):
        return {key:_rewrite(item,mapping) for key,item in value.items()}
    return value


def normalize_resource_document(path, value):
    path = Path(path)
    rp = next((parent for parent in path.parents if parent.name == 'TwilightBossSliceR'),None)
    if rp is None:
        try:
            from build_creative_catalog import normalize_catalog_owned_description
            from block_mining_contract import normalize as normalize_mining
        except ImportError:
            from tools.build_creative_catalog import normalize_catalog_owned_description
            from tools.block_mining_contract import normalize as normalize_mining
        return normalize_catalog_owned_description(path, normalize_mining(path, value))
    try:
        from entity_visual_overrides import apply_entity_visual_overrides
        from remaining_visual_overrides import apply_remaining_visual_overrides
    except ImportError:
        from tools.entity_visual_overrides import apply_entity_visual_overrides
        from tools.remaining_visual_overrides import apply_remaining_visual_overrides
    value = apply_remaining_visual_overrides(path, value)
    _, project, external = _mapping(rp.parent)
    if not project and not external:
        return apply_entity_visual_overrides(path, value)
    result = _rewrite(value,project)
    if path.relative_to(rp).as_posix() in (
        'textures/terrain_texture.json', 'textures/item_texture.json'
    ):
        result = copy.deepcopy(result)
        for alias, entry in result.get('texture_data',{}).items():
            if alias.startswith('tf_slice:') and isinstance(entry,dict):
                entry['textures'] = _rewrite(entry.get('textures'),external)
    return apply_entity_visual_overrides(path, result)


def resolve_source_texture(path, project_root):
    """Supply approved material pixels to an existing model renderer."""
    path = Path(path)
    try:
        from retired_runtime_pngs import original_texture
    except ImportError:
        from tools.retired_runtime_pngs import original_texture
    path = original_texture(path, project_root)
    bank, data = registry(project_root)
    if not data.get('enabled'):
        return path
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    pixel_key = None
    for entry in data['entries']:
        if entry.get('derived_icon'):
            continue
        if entry.get('source_sha256') == digest:
            return bank / 'assets' / entry['output_relative']
    # Different PNG encodings may carry the same original source pixels.
    with Image.open(path) as image:
        pixel_key = [list(image.size),hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest()]
    for entry in data['entries']:
        if not entry.get('derived_icon') and entry.get('source_pixel_key') == pixel_key:
            return bank / 'assets' / entry['output_relative']
    return path
