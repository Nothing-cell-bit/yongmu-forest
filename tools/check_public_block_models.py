"""Validate declared NetEase block model cells and item aliases, source or ZIP."""
import argparse
import json
from pathlib import Path
import zipfile


def inspect_documents(documents):
    clients = documents.get('blocks.json', {})
    atlas = documents.get('textures/terrain_texture.json', {}).get('texture_data', {})
    models = {}
    issues = []
    for name, document in documents.items():
        if not name.startswith('models/netease_block/'):
            continue
        model = document.get('netease:block_geometry', {})
        identifier = model.get('description', {}).get('identifier')
        if identifier in models:
            issues.append({'id': identifier, 'reason': 'duplicate NetEase block model identifier'})
        models[identifier] = model
    referenced = {v['netease_model'] for v in clients.values()
                  if isinstance(v, dict) and 'netease_model' in v}
    for identifier in sorted(referenced):
        if identifier not in models:
            issues.append({'id': identifier, 'reason': 'referenced NetEase block model is missing'})
    for identifier, model in models.items():
        description = model.get('description', {})
        alias = description.get('item_texture')
        if alias is not None and alias not in atlas:
            issues.append({'id': identifier, 'reason': 'item_texture must resolve to a terrain atlas alias', 'actual': alias})
        for bone in model.get('bones', []):
            for cube in bone.get('cubes', []):
                origin, size = cube.get('origin', []), cube.get('size', [])
                if len(origin) != 3 or len(size) != 3 or any(type(v) not in (int, float) for v in origin + size):
                    issues.append({'id': identifier, 'reason': 'invalid cube coordinates'})
                    continue
                # The public NetEase exporters use one block cell. Standard
                # minecraft:geometry and independent entity models are separate.
                if not (-16 <= origin[0] <= origin[0] + size[0] <= 0
                        and 0 <= origin[1] <= origin[1] + size[1] <= 16
                        and 0 <= origin[2] <= origin[2] + size[2] <= 16):
                    issues.append({'id': identifier, 'reason': 'NetEase model is outside its block cell', 'origin': origin, 'size': size})
    return {'status': 'public_model_contract_pass' if not issues else 'needs_attention',
            'models': len(models), 'referenced_models': len(referenced), 'issues': issues,
            'scope': 'Declared single-cell NetEase models and item aliases; runtime visibility and rotations need client acceptance.'}


def check(path):
    path = Path(path)
    documents = {}
    if path.is_dir():
        rp = path / 'TwilightBossSliceR' if (path / 'TwilightBossSliceR').is_dir() else path
        for relative in ('blocks.json', 'textures/terrain_texture.json'):
            if (rp / relative).is_file():
                documents[relative] = json.loads((rp / relative).read_text('utf-8-sig'))
        for model in (rp / 'models/netease_block').glob('*.json'):
            documents[model.relative_to(rp).as_posix()] = json.loads(model.read_text('utf-8-sig'))
    else:
        with zipfile.ZipFile(path) as bundle:
            names = bundle.namelist()
            prefix = 'resource_pack/' if 'resource_pack/manifest.json' in names else 'TwilightBossSliceR/'
            for name in names:
                if not name.startswith(prefix):
                    continue
                relative = name[len(prefix):]
                if relative in ('blocks.json', 'textures/terrain_texture.json') or (relative.startswith('models/netease_block/') and relative.endswith('.json')):
                    if relative in documents:
                        raise ValueError('Duplicate resource JSON member: ' + relative)
                    documents[relative] = json.loads(bundle.read(name))
    return dict(inspect_documents(documents), input=str(path.resolve()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = check(args.input)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(output + '\n', encoding='utf8')
    print(output)
    raise SystemExit(0 if not result['issues'] else 2)
