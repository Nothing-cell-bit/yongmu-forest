"""Offline publication checks; report locations only, never matched secret text."""
from pathlib import Path
import ast
import argparse
import hashlib
import json
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
PYTHON2_ADAPTERS = {
    'TwilightBossSliceB/TwilightBossSlice/clientSystem.py',
    'TwilightBossSliceB/TwilightBossSlice/serverSystem.py',
    'TwilightBossSliceB/TwilightBossSlice/structureWorldgenService.py',
}
PATTERNS = {
    'github-token': re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b'),
    'api-secret': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b'),
    'aws-access-id': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    # `test` is an existing synthetic fixture, not a workstation user's path.
    'personal-windows-path': re.compile(r'[A-Za-z]:[/\\]{1,2}Users[/\\]{1,2}(?!Public\b|Default\b|test\b)[^/\\\s\"\']+'),
}
ALLOWED_SUFFIXES = {'.py', '.md', '.txt', '.json', '.yml', '.yaml', '.lang'}
IGNORED_PARTS = {'.git', '__pycache__', '.pytest_cache', '.ruff_cache', '.venv', 'dist'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-import', action='store_true', help='Verify the initial copied snapshot; omit for later source edits.')
    args = parser.parse_args()
    asset_file = ROOT / 'ASSET_MANIFEST.json'
    asset_manifest = json.loads(asset_file.read_text(encoding='utf-8')) if asset_file.is_file() else {'included': []}
    assets = {item['path']: item for item in asset_manifest['included']}
    pack_file = ROOT / 'PACK_SNAPSHOT.json'
    pack_manifest = json.loads(pack_file.read_text(encoding='utf-8')) if pack_file.is_file() else {'files': []}
    pack_paths = {item['path'] for item in pack_manifest['files']}
    findings = []
    checked = 0
    python3_parsed = 0
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in rel.parts) or not path.is_file():
            continue
        if path.is_symlink():
            findings.append({'path':rel.as_posix(),'rule':'symlink'})
            continue
        if path.suffix in {'.ogg', '.mcstructure'}:
            if rel.as_posix() not in pack_paths:
                findings.append({'path': rel.as_posix(), 'rule': 'unlisted-pack-binary'})
            raw = path.read_bytes()
            if not raw or (path.suffix == '.ogg' and not raw.startswith(b'OggS')):
                findings.append({'path': rel.as_posix(), 'rule': 'invalid-pack-binary'})
            if len(raw) >= 100_000_000:
                findings.append({'path': rel.as_posix(), 'rule': 'github-file-size-limit'})
            checked += 1
            continue
        if path.suffix == '.png':
            item = assets.get(rel.as_posix())
            if item is None or not rel.as_posix().startswith('TwilightBossSliceR/textures/'):
                findings.append({'path':rel.as_posix(),'rule':'unlisted-image'})
                continue
            raw = path.read_bytes()
            if len(raw) < 24 or raw[:8] != b'\x89PNG\r\n\x1a\n':
                findings.append({'path':rel.as_posix(),'rule':'invalid-png'})
            else:
                dimensions = struct.unpack('>II', raw[16:24])
                if dimensions != (item['width'], item['height']) or max(dimensions) > 8192:
                    findings.append({'path':rel.as_posix(),'rule':'png-dimensions'})
            if hashlib.sha256(raw).hexdigest() != item['sha256'] or len(raw) != item['bytes']:
                findings.append({'path':rel.as_posix(),'rule':'image-hash-mismatch'})
            if item.get('license') != 'CC-BY-NC-SA-4.0' or not item.get('creators') or not item.get('changes'):
                findings.append({'path':rel.as_posix(),'rule':'image-attribution-missing'})
            checked += 1
            continue
        if path.name not in {'LICENSE','ASSET_LICENSE','.gitignore','.gitattributes'} and path.suffix not in ALLOWED_SUFFIXES:
            findings.append({'path':rel.as_posix(),'rule':'unexpected-file-type'})
            continue
        raw = path.read_bytes()
        if len(raw) > 10_000_000:
            findings.append({'path':rel.as_posix(),'rule':'unexpected-large-file'})
        text = raw.decode('utf-8-sig')
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append({'path':rel.as_posix(),'line':text.count('\n',0,match.start())+1,'rule':name})
        if path.suffix == '.py' and rel.as_posix() not in PYTHON2_ADAPTERS:
            try:
                ast.parse(text,filename=rel.as_posix())
                python3_parsed += 1
            except SyntaxError as error:
                findings.append({'path':rel.as_posix(),'line':error.lineno,'rule':'python3-syntax'})
        checked += 1
    for name in assets:
        if '..' in Path(name).parts or not (ROOT/name).is_file():
            findings.append({'path':name,'rule':'asset-path-or-file-missing'})
    hashes_checked = 0
    if args.verify_import:
        manifest = json.loads((ROOT/'SOURCE_SNAPSHOT.json').read_text(encoding='utf-8'))
        for item in manifest['copied_files']:
            path = ROOT/item['path']
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
                findings.append({'path':item['path'],'rule':'source-hash-mismatch'})
            hashes_checked += 1
    print(json.dumps({'checked_files':checked,'python3_parsed':python3_parsed,'python2_adapters_not_parsed':sorted(PYTHON2_ADAPTERS),'snapshot_hashes_checked':hashes_checked,'asset_hashes_checked':len(assets),'findings':findings},ensure_ascii=False,indent=2))
    return int(bool(findings))

if __name__=='__main__':
    raise SystemExit(main())
