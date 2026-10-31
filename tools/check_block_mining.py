"""Check actual source or ZIP mining definitions without building any assets."""
import argparse
import json
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

try:
    from block_mining_contract import contract, mining_issues
except ImportError:
    from tools.block_mining_contract import contract, mining_issues


def check(path):
    path = Path(path)
    if path.is_dir():
        bp = path if (path / 'netease_blocks').is_dir() else path / 'TwilightBossSliceB'
        issues = mining_issues(bp)
    else:
        with tempfile.TemporaryDirectory() as directory, zipfile.ZipFile(path) as bundle:
            names = bundle.namelist()
            prefix = 'behavior_pack/' if 'behavior_pack/manifest.json' in names else 'TwilightBossSliceB/'
            bp = Path(directory)
            for item in bundle.infolist():
                if not item.filename.startswith(prefix) or item.is_dir():
                    continue
                relative = item.filename[len(prefix):]
                if not (relative.startswith(('netease_blocks/', 'items/')) and relative.endswith('.json')
                        or relative == 'loot_tables/blocks/tf_slice/no_mining_drop.json'
                        or relative == 'TwilightBossSlice/mining_tool_rules.py'):
                    continue
                assert '..' not in PurePosixPath(relative).parts and not PurePosixPath(relative).is_absolute()
                target = bp / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bundle.read(item))
            issues = mining_issues(bp)
    data = contract()
    return {'status': 'mining_contract_pass' if not issues else 'needs_attention',
            'input': str(path.resolve()), 'blocks': len(data['blocks']), 'tools': len(data['items']),
            'issues': issues, 'scope': 'Declared mining/tool/drop contracts only; native crack visibility and actual timing require client acceptance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = check(args.input)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if not result['issues'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
