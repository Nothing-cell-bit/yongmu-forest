"""Read-only pack inventory, JSON, dependency and resource-reference checks."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
from ruin_structure_dedup import resolve_ruin_structure_reference

ROOT = Path(__file__).resolve().parents[1]
PACKS = ('TwilightBossSliceB', 'TwilightBossSliceR')

def pack_files():
    return {p.relative_to(ROOT).as_posix(): p for name in PACKS
            for p in (ROOT / name).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts
            and p.suffix not in {'.pyc', '.pyo'} and p.name != 'README.md'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-snapshot', action='store_true',
                        help='Check every byte against the published snapshot.')
    args = parser.parse_args()
    files = pack_files()
    errors = []
    documents = {}
    for name, path in files.items():
        if path.is_symlink():
            errors.append(name + ': symlink')
        if path.suffix == '.json':
            try:
                documents[name] = json.loads(path.read_text(encoding='utf-8-sig'))
            except (ValueError, UnicodeError) as exc:
                errors.append(name + ': invalid JSON: ' + str(exc))
    manifests = [documents.get(name + '/manifest.json', {}) for name in PACKS]
    headers = {m.get('header', {}).get('uuid'): m.get('header', {}) for m in manifests}
    for name, manifest in zip(PACKS, manifests):
        if not manifest.get('header') or not manifest.get('modules'):
            errors.append(name + ': missing pack manifest')
        for dep in manifest.get('dependencies', []):
            if dep.get('uuid') not in headers or headers[dep['uuid']].get('version') != dep.get('version'):
                errors.append(name + ': pack dependency mismatch')
    rp = ROOT / PACKS[1]
    sounds = documents.get(PACKS[1] + '/sounds/sound_definitions.json', {}).get('sound_definitions', {})
    sound_refs = 0
    for name, definition in sounds.items():
        for entry in definition.get('sounds', []):
            value = entry if isinstance(entry, str) else entry.get('name', '')
            if value.startswith('sounds/mob/') and value not in {'sounds/mob/bat/takeoff', 'sounds/mob/wolf/death'}:
                sound_refs += 1
                if not (rp / (value + '.ogg')).is_file():
                    errors.append(name + ': missing sound ' + value)
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)
        elif isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
    catalog_name = PACKS[0] + '/structures/tf_slice/ruins/structure_catalog_v1.json'
    catalog = documents.get(catalog_name)
    structure_refs = set()
    def find_structures(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'structure' and isinstance(child, str) and child.startswith('tf_slice/'):
                    structure_refs.add(child)
                find_structures(child)
        elif isinstance(value, list):
            for child in value:
                find_structures(child)
    if not catalog:
        errors.append('Missing structure catalog')
    find_structures(catalog)
    aliases = (catalog or {}).get('structureAliases', {})
    for name in structure_refs:
        try:
            resolved = resolve_ruin_structure_reference(name, aliases)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not (ROOT / PACKS[0] / 'structures' / (resolved + '.mcstructure')).is_file():
            errors.append('Missing structure: ' + name)
    for atlas in ('item_texture.json', 'terrain_texture.json'):
        doc = documents.get(PACKS[1] + '/textures/' + atlas)
        if not doc:
            errors.append('Missing texture atlas: ' + atlas)
            continue
        for value in strings(doc.get('texture_data', {})):
            if value.startswith('textures/') and not any((rp / (value + ext)).is_file() for ext in ('.png', '.tga')):
                # Vanilla textures are supplied by Minecraft; only custom existing
                # namespace prefixes are asserted here.
                if '/tf_slice/' in value:
                    errors.append(atlas + ': missing custom texture ' + value)
    checked_hashes = 0
    if args.verify_snapshot:
        snapshot = json.loads((ROOT / 'PACK_SNAPSHOT.json').read_text(encoding='utf-8'))
        expected = {entry['path']: entry for entry in snapshot['files']}
        for name in sorted(set(files) ^ set(expected)):
            errors.append('Pack inventory mismatch: ' + name)
        for name, entry in expected.items():
            rel = PurePosixPath(name)
            if rel.is_absolute() or '..' in rel.parts or rel.parts[0] not in PACKS:
                errors.append('Unsafe snapshot path: ' + name)
                continue
            if name not in files:
                continue
            raw = files[name].read_bytes()
            checked_hashes += 1
            if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
                errors.append('Pack hash mismatch: ' + name)
    print(json.dumps({'pack_files': len(files), 'json_files': len(documents),
                      'sound_references_checked': sound_refs, 'structure_references_checked': len(structure_refs),
                      'hashes_checked': checked_hashes,
                      'errors': errors}, ensure_ascii=False, indent=2))
    return int(bool(errors))

if __name__ == '__main__':
    raise SystemExit(main())
