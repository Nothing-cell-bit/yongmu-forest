"""Relocate beautified textures in a release copy; preserve image bytes.

This is a compatibility candidate for the reported cloud error 38, not a
reimplementation of NetEase's unavailable cloud packer or a proof of acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

OLD = 'textures/tf_beautified/'
# Longest/specific routes precede general ones; prefixes also cover Python's
# dynamically concatenated map-marker paths.
ROUTES = (
    ('base/book_enchanted', 'items/tf_beautified/base/book_enchanted'),
    ('blocks/item_icons/', 'items/tf_beautified/block_icons/'),
    ('remaining/native/blocks/', 'blocks/tf_beautified/native/'),
    ('remaining/native/items/', 'items/tf_beautified/native/'),
    ('remaining/native/particle/', 'particle/tf_beautified/native/'),
    ('remaining/models/', 'models/tf_beautified/'),
    ('remaining/environment/', 'environment/tf_beautified/'),
    ('remaining/entity/', 'entity/tf_beautified/remaining/'),
    ('remaining/particle/', 'particle/tf_beautified/'),
    ('remaining/ui/', 'ui/tf_beautified/'),
    ('base/', 'blocks/tf_beautified/base/'),
    ('blocks/', 'blocks/tf_beautified/'),
    ('items/', 'items/tf_beautified/'),
    ('entities/', 'entity/tf_beautified/'),
    ('entity/', 'entity/tf_beautified/'),
)
TEXT_SUFFIXES = {'.json', '.py', '.material', '.materials', '.txt', '.lang'}


def rewrite(text):
    for source, target in ROUTES:
        text = text.replace(OLD + source, 'textures/' + target)
    if OLD in text:
        raise ValueError('Unmapped beautified texture path: ' + text[:200])
    return text


def transform(rows, resource_pack):
    """Return new member bytes and a complete relocation/edit manifest."""
    files, directories, seen = {}, set(), set()
    moves, edits = {}, []
    old_root = resource_pack + '/' + OLD
    for name, data in rows:
        if name.endswith('/'):
            if not name.startswith(old_root):
                directories.add(name)
            continue
        target = name
        if name.startswith(old_root):
            if not name.endswith('.png'):
                raise ValueError('Unexpected non-PNG in beautification tree: ' + name)
            target = resource_pack + '/' + rewrite(name[len(resource_pack) + 1:])
            moves[name] = {'to': target, 'sha256': hashlib.sha256(data).hexdigest()}
        elif OLD.encode() in data:
            if Path(name).suffix not in TEXT_SUFFIXES:
                raise ValueError('Unsupported texture-reference file: ' + name)
            changed = rewrite(data.decode('utf-8'))
            if name.endswith('.json'):
                json.loads(changed)
            data = changed.encode('utf-8')
            edits.append(name)
        if target.casefold() in seen:
            raise ValueError('Texture destination collision: ' + target)
        seen.add(target.casefold())
        files[target] = data
    for name in files:
        parent = Path(name).parent
        while str(parent) != '.':
            directories.add(parent.as_posix() + '/')
            parent = parent.parent
    if {n.casefold() for n in files} & {n.rstrip('/').casefold() for n in directories}:
        raise ValueError('File/directory destination collision')
    result = sorted([(n, b'') for n in directories] + list(files.items()))
    report = {'moved_pngs': moves, 'edited_reference_files': edits,
              'moved_png_count': len(moves), 'edited_reference_file_count': len(edits)}
    verify(rows, result, report, resource_pack)
    return result, report


def verify(before, after, report, resource_pack):
    old_files = {n: d for n, d in before if not n.endswith('/')}
    new_files = {n: d for n, d in after if not n.endswith('/')}
    if len(old_files) != len(new_files):
        raise ValueError('File count changed')
    moved = report['moved_pngs']
    edited = set(report['edited_reference_files'])
    for name, data in old_files.items():
        target = moved.get(name, {}).get('to', name)
        expected = rewrite(data.decode('utf-8')).encode('utf-8') if name in edited else data
        if new_files.get(target) != expected:
            raise ValueError('Unexpected file change: ' + name)
    for name, data in after:
        if OLD in name or OLD.encode() in data:
            raise ValueError('Old texture path remains: ' + name)
        if name.endswith('.json'):
            json.loads(data.decode('utf-8-sig'))
    # Check the relocated references (including directory prefixes composed by
    # Python). Unrelated vanilla fallback paths are outside this narrow check.
    pattern = re.compile(r'textures/[a-z_]+/tf_beautified/[a-zA-Z0-9_./-]+')
    checked = set()
    for name, data in after:
        if Path(name).suffix not in TEXT_SUFFIXES:
            continue
        for ref in pattern.findall(data.decode('utf-8-sig')):
            target = resource_pack + '/' + ref
            if ref.endswith('/'):
                exists = any(n.startswith(target) for n in new_files)
            else:
                exists = target in new_files or target + '.png' in new_files
            if not exists:
                raise ValueError('Missing relocated texture: ' + name + ': ' + ref)
            checked.add(ref)
    report['verified_relocated_references'] = len(checked)
    report['all_images_byte_identical'] = True
    report['file_count_preserved'] = len(new_files)


def apply_staging(staging, resource_pack='resource_pack'):
    """Only called for a newly created isolated release staging directory."""
    staging = Path(staging).resolve()
    paths = list(staging.rglob('*'))
    if any(p.is_symlink() or not p.resolve().is_relative_to(staging) for p in paths):
        raise ValueError('Linked staging path')
    before = [(p.relative_to(staging).as_posix() + ('/' if p.is_dir() else ''),
               b'' if p.is_dir() else p.read_bytes()) for p in paths]
    after, report = transform(before, resource_pack)
    for name, data in after:
        path = staging / name
        if name.endswith('/'):
            path.mkdir(parents=True, exist_ok=True)
        elif not path.exists() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    for old, item in report['moved_pngs'].items():
        path = (staging / old).resolve()
        if not path.is_relative_to(staging) or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Staging input changed before retirement: ' + old)
        path.unlink()
    old_tree = staging / resource_pack / OLD
    if old_tree.exists():
        for path in sorted(old_tree.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if path.is_dir():
                path.rmdir()
        old_tree.rmdir()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.report.exists():
        raise ValueError('Use new output/report paths; never overwrite failure evidence')
    if args.report.resolve() in (args.output.resolve(), args.archive.resolve()):
        raise ValueError('Report must be distinct from input and output')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
    import release_audit
    before = release_audit.members(args.archive.resolve())
    resource_pack = 'TwilightBossSliceR'
    after, report = transform(before, resource_pack)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in after:
            z.writestr(name, data)
    readback = release_audit.members(args.output.resolve())
    verify(before, readback, report, resource_pack)
    with zipfile.ZipFile(args.output) as z:
        if z.testzip() is not None:
            raise ValueError('Final archive CRC failure')
    report.update(input=str(args.archive.resolve()), output=str(args.output.resolve()),
                  input_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(),
                  output_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
                  platform_review='not_submitted', runtime_acceptance='not_run',
                  root_cause='Directory-layout incompatibility remains a hypothesis pending cloud verification')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('moved_pngs', 'edited_reference_files')}, indent=2))


if __name__ == '__main__':
    main()
