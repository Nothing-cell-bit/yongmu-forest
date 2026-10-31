"""Prepare a review-only export; never alter installed packs or rebuild assets."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent


def _replace_method(text, name, replacement=''):
    match = re.search(r'^    def ' + re.escape(name) + r'\(', text, re.M)
    if match is None:
        return text
    following = re.search(r'^    (?:def |@)', text[match.end():], re.M)
    end = match.end() + following.start() if following else len(text)
    return text[:match.start()] + replacement + text[end:]


def _drop_block(text, first, paired=False):
    lines = text.splitlines(True)
    result = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() != first:
            result.append(line);index += 1;continue
        indent = len(line) - len(line.lstrip())
        index += 1
        if paired:
            if index >= len(lines) or not lines[index].lstrip().startswith('if '):
                raise ValueError('Diagnostic hook layout changed: ' + first)
            index += 1
        while index < len(lines):
            current = lines[index]
            if current.strip() and len(current)-len(current.lstrip()) <= indent:
                break
            index += 1
    return ''.join(result)


DEVELOPMENT_MODULES = frozenset(("chunk_latency_probe.py", "native_world_diagnostics.py"))


def _remove_native_world_diagnostics(text):
    if "native_world_diagnostics" not in text:
        return text
    text = text.replace("import TwilightBossSlice.native_world_diagnostics as native_world_diagnostics\n", "")
    text = re.sub(r'^        self\._native_world_diag = .*\n', '', text, flags=re.M)
    text = _drop_block(text, 'diagnostic = getattr(self, "_native_world_diag", None)', paired=True)
    text = _replace_method(text, "_emit_native_world_diag")
    replacements = (
        ('return native_world_diagnostics.call(self, "water.ready", position, dimension,\n'
         '                self._chunk_comp.CheckChunkState, dimension, position)',
         'return self._chunk_comp.CheckChunkState(dimension, position)'),
        ('return native_world_diagnostics.call(self, "water.write", position, dimension,\n'
         '                self._block_comp.SetBlockNew,',
         'return self._block_comp.SetBlockNew('),
        ('return native_world_diagnostics.call(self, "water.read", position, dimension,\n'
         '                self._get_block, position, dimension)',
         'return self._get_block(position, dimension)'),
    )
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError("Diagnostic wrapper changed; review before stripping: " + old[:60])
        text = text.replace(old, new, 1)
    text = re.sub(r'^        pair = native_world_diagnostics\.record\(.*\n', '', text, flags=re.M)
    text = re.sub(r'^            diagnostic_args = dict\(args\)\n'
                  r'^            diagnostic_args\["pair"\] = pair\n'
                  r'^            native_world_diagnostics\.record\(.*\n', '', text, flags=re.M)
    text = re.sub(r'^        native_world_diagnostics\.record\(.*\n', '', text, flags=re.M)
    if "native_world_diag" in text or "diagnostic_args" in text:
        raise ValueError("Unremoved native world diagnostics")
    return text


def clean_script(name, text):
    if name == "serverSystem.py":
        text = _remove_native_world_diagnostics(text)
    if name in ('clientSystem.py', 'serverSystem.py'):
        text = text.replace('import TwilightBossSlice.chunk_latency_probe as chunk_latency_probe\n', '')
        text = _replace_method(text, '_control_chunk_latency_probe')
        if name == 'serverSystem.py':
            text = _replace_method(text, 'OnServerChatEvent',
                '    def OnServerChatEvent(self, args):\n        # Development chat commands are absent from the release candidate.\n        return\n\n')
        else:
            text = _replace_method(text, 'OnKeyPressInGame',
                '    def OnKeyPressInGame(self, args):\n        # The hitbox-debug hotkey is disabled in the release candidate.\n        return\n\n')
            text = _drop_block(text, 'control = args.get("load_probe")', paired=True)
            text = _drop_block(text, 'if args.get("probe_message"):')
        text = _drop_block(text, 'probe = getattr(self, "_chunk_latency_probe", None)', paired=True)
        if 'chunk_latency_probe' in text or 'load_probe' in text:
            raise ValueError('Unremoved diagnostic reference in ' + name)
    elif name == 'config.py':
        text = re.sub(r'^CHUNK_LATENCY_PROBE_OUTPUT_DIR = .*\n', '', text, flags=re.M)
    elif name == 'release_metadata.py':
        text = re.sub(r'^RELEASE_STAGE = .*$', 'RELEASE_STAGE = "release_review_candidate_runtime_pending"', text, flags=re.M)
    return text


def copy_notices(source, destination):
    """Keep notices in the review export or its separate submission materials."""
    for relative in ('LICENSE_CODE.md', 'THIRD_PARTY_NOTICES.md', 'licenses/LGPL-2.1.txt'):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    asset_license = source / 'licenses/CC-BY-NC-SA-4.0.txt'
    if asset_license.exists():
        target = destination / 'licenses' / asset_license.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset_license, target)


def require_submission_layout(rows):
    """Validate this project's direct two-pack upload contract on real members."""
    names = [name for name, _data in rows]
    roots = {name.split('/', 1)[0] for name in names}
    if roots != {'behavior_pack', 'resource_pack'}:
        raise ValueError('Submission must contain only the two direct pack roots: ' + repr(roots))
    for required in ('behavior_pack/manifest.json', 'resource_pack/manifest.json'):
        if required not in names:
            raise ValueError('Missing submission manifest: ' + required)
    if not any(name.startswith('resource_pack/textures/') and not name.endswith('/') and data
               for name, data in rows):
        raise ValueError('Submission resource pack needs actual texture files')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--staging', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--submission', action='store_true',
                        help='Only the two pack roots enter the component ZIP')
    parser.add_argument('--materials-dir', type=Path,
                        help='Separate, new directory preserving submission notices')
    args = parser.parse_args()
    source, staging = args.source_root.resolve(), args.staging.resolve()
    if staging.exists() or args.archive.exists():
        raise ValueError('Use new staging and archive paths; existing evidence is never overwritten')
    if not staging.is_relative_to(WORKSPACE) or staging.is_relative_to(source):
        raise ValueError('Staging must be isolated within the workspace')
    if args.archive.resolve().is_relative_to(source) or args.archive.resolve().is_relative_to(staging):
        raise ValueError('Archive must be outside source and staging')
    if args.submission != (args.materials_dir is not None):
        raise ValueError('Use --submission and --materials-dir together')
    materials = args.materials_dir.resolve() if args.materials_dir else None
    if materials is not None and (
        materials.exists() or not materials.is_relative_to(WORKSPACE)
        or materials.is_relative_to(source) or materials.is_relative_to(staging)
    ):
        raise ValueError('Submission materials must be a new, isolated workspace directory')
    sys.path.insert(0, str(WORKSPACE/'tools'))
    import release_audit
    from submission_codecheck import check_source, require_clean
    check_source(source / 'TwilightBossSliceB')
    from block_mining_contract import mining_issues
    issues = mining_issues(source / 'TwilightBossSliceB')
    if issues:
        raise ValueError('Mining contract failed before export: ' + repr(issues))
    from check_public_block_models import check as check_models
    model_result = check_models(source / 'TwilightBossSliceR')
    if model_result['issues']:
        raise ValueError('Public block models failed before export: ' + repr(model_result['issues']))
    edits, excluded, hashes = [], [], {}
    for old_pack, pack in [('TwilightBossSliceB','behavior_pack'), ('TwilightBossSliceR','resource_pack')]:
        origin = source/old_pack
        if not (origin/'manifest.json').is_file():
            raise ValueError('Missing source manifest: '+str(origin))
        for path in sorted(origin.rglob('*')):
            if path.is_symlink() or not path.resolve().is_relative_to(origin):
                raise ValueError('Linked source path: '+str(path))
            rel = path.relative_to(origin)
            name = pack+'/'+rel.as_posix()
            residue = release_audit.residue(name)
            if residue == 'remove' or (str(rel).replace('\\', '/').startswith('TwilightBossSlice/')
                                       and path.name in DEVELOPMENT_MODULES):
                excluded.append(name);continue
            if residue == 'review':
                raise ValueError('Unreviewed residue: '+name)
            dest = staging/name
            if path.is_dir():
                dest.mkdir(parents=True, exist_ok=True);continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = path.read_bytes()
            hashes[old_pack+'/'+rel.as_posix()] = hashlib.sha256(data).hexdigest()
            if path.suffix == '.py':
                text = data.decode('utf-8-sig').replace('\r\n','\n')
                cleaned = clean_script(path.name, text)
                if cleaned != text:
                    data = cleaned.encode('utf-8');edits.append(name)
            dest.write_bytes(data)
    if materials is None:
        copy_notices(ROOT, staging)
    else:
        # Required notices still travel with the component; the separate copy
        # is convenient for submission, not a substitute for distribution.
        copy_notices(ROOT, staging / 'behavior_pack')
        copy_notices(ROOT, materials)
    # Only transform this new release copy. Development manifests and image
    # generators keep their canonical paths, while every future release export
    # uses the same conventional texture categories and updated references.
    sys.path.insert(0, str(ROOT/'tools'))
    from release_texture_layout import apply_staging
    texture_layout = apply_staging(staging)
    json_errors=[]
    for path in staging.rglob('*.json'):
        try:json.loads(path.read_text(encoding='utf-8-sig'))
        except Exception as error:json_errors.append({'path':str(path.relative_to(staging)),'error':str(error)})
    if json_errors:raise ValueError('Invalid JSON: '+repr(json_errors))
    forbidden=[]
    for path in (staging/'behavior_pack').rglob('*.py'):
        text=path.read_text(encoding='utf-8-sig')
        if re.search(r'[A-Za-z]:[/\\]|StartProfile|StopProfile|chunk_latency_probe|loadprobe', text):
            forbidden.append(str(path.relative_to(staging)))
    if forbidden:raise ValueError('Development-only code remains: '+repr(forbidden))
    command=[sys.executable,'-X','utf8',str(WORKSPACE/'tools/release_audit.py')]
    results={}
    require_clean(release_audit.members(staging))
    if args.submission:
        require_submission_layout(release_audit.members(staging))
    for label,argv in [('staging',['audit',str(staging)]),('archive_build',['clean',str(staging),'--output',str(args.archive)]),('archive_readback',['audit',str(args.archive)])]:
        completed=subprocess.run(command+argv,capture_output=True,text=True,encoding='utf-8')
        try:results[label]=json.loads(completed.stdout)
        except ValueError:raise RuntimeError(completed.stderr+completed.stdout)
        if completed.returncode:
            args.report.write_text(json.dumps(results,indent=2),encoding='utf-8')
            raise RuntimeError(label+' failed; see '+str(args.report))
    from check_block_mining import check as check_mining
    require_clean(release_audit.members(args.archive.resolve()))
    if args.submission:
        require_submission_layout(release_audit.members(args.archive.resolve()))
        results['submission_layout'] = {'roots': ['behavior_pack', 'resource_pack'], 'issues': []}
    mining_result = check_mining(args.archive)
    if mining_result['issues']:
        raise ValueError('Final ZIP mining contract failed: ' + repr(mining_result['issues']))
    results['mining_archive'] = mining_result
    model_result = check_models(args.archive)
    if model_result['issues']:
        raise ValueError('Final ZIP public block models failed: ' + repr(model_result['issues']))
    results['public_models_archive'] = model_result
    unresolved = ['Final exported candidate not runtime accepted by this exporter',
                  'Non-code asset permissions and complete attribution review',
                  'New-chunk loading performance not measured by this exporter']
    if not (ROOT / 'tools' / 'validate_slice.py').is_file():
        unresolved.append('Missing project validate_slice.py')
    result={'source':str(source),'staging':str(staging),'archive':str(args.archive.resolve()),
            'materials': str(materials) if materials is not None else None,
            'edits':edits,'excluded':excluded,'source_hashes':hashes,'checks':results,
            'texture_layout':texture_layout,
            'status': 'local_submission_checks_passed' if args.submission else 'technical_review_candidate_only',
            'runtime_acceptance':'not_run_by_exporter','platform_review':'not_submitted',
            'unresolved': unresolved}
    args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_hashes','checks')},indent=2))


if __name__ == '__main__':
    main()
