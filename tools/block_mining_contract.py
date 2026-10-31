"""Source-owned mining normalization; no world, structure, or deployment writes."""
from pathlib import Path
import copy
from functools import lru_cache
import json
try:
    from upstream_mining_tags import contract_source_issues
except ImportError:
    from tools.upstream_mining_tags import contract_source_issues

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / 'source_locks/block_mining_contract.json'
EMPTY_LOOT = 'loot_tables/blocks/tf_slice/no_mining_drop.json'


@lru_cache(maxsize=1)
def contract():
    return json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))


def _version(document):
    return tuple(int(v) for v in document.get('format_version', '1.10.0').split('.'))


def _mining_components(components, spec, version):
    hardness = spec['hardness']
    if version >= (1, 19, 20):
        components.pop('minecraft:destroy_time', None)
        components['minecraft:destructible_by_mining'] = False if hardness < 0 else {'seconds_to_destroy': hardness}
    else:
        components.pop('minecraft:destructible_by_mining', None)
        components['minecraft:destroy_time'] = {'value': hardness} if version < (1, 16, 0) else hardness
    if spec['tier'] is not None:
        components['netease:tier'] = copy.deepcopy(spec['tier'])
    else:
        components.pop('netease:tier', None)
    if spec['no_mining_drop']:
        components['minecraft:loot'] = {'table': EMPTY_LOOT} if version < (1, 16, 0) else EMPTY_LOOT


def normalize(path, document):
    """Apply only mining fields; caller keeps all rendering, state and blast data."""
    if not isinstance(document, dict):
        return document
    if 'minecraft:block' not in document and 'minecraft:item' not in document:
        return document
    data = contract()
    block = document.get('minecraft:block')
    if isinstance(block, dict):
        spec = data['blocks'].get(block.get('description', {}).get('identifier'))
        if spec is None:
            return document
        result = copy.deepcopy(document)
        output = result['minecraft:block']
        version = _version(result)
        _mining_components(output.setdefault('components', {}), spec, version)
        for permutation in output.get('permutations', []):
            overrides = permutation.get('components', {})
            if any(k in overrides for k in ('minecraft:destroy_time', 'minecraft:destructible_by_mining', 'netease:tier')):
                _mining_components(overrides, spec, version)
        return result
    item = document.get('minecraft:item')
    if isinstance(item, dict):
        identifier = item.get('description', {}).get('identifier')
        spec = data['items'].get(identifier)
        if spec is None:
            return document
        result = copy.deepcopy(document)
        output = result['minecraft:item']
        output['description']['custom_item_type'] = 'weapon'
        components = output.setdefault('components', {})
        # Existing modern damage remains its sole damage modifier. The SDK
        # weapon component supplies tool classification and harvest tier only.
        components['netease:weapon'] = {
            'type': spec['type'], 'level': spec['level'], 'speed': int(spec['speed']),
            'attack_damage': 0, 'enchantment': components.get('minecraft:enchantable', {}).get('value', 0),
        }
        tags = list(components.get('minecraft:tags', {}).get('tags', []))
        tool = 'axe' if spec['type'] == 'hatchet' else spec['type']
        for tag in ('minecraft:is_tool', 'minecraft:is_' + tool):
            if tag not in tags:
                tags.append(tag)
        components['minecraft:tags'] = {'tags': tags}
        if identifier == 'tf_slice:mazebreaker_pickaxe':
            components['minecraft:digger'] = {
                'use_efficiency': True,
                'destroy_speeds': [{'block': name, 'speed': int(spec['speed'] * 16)}
                                   for name in data['mazebreaker_accelerated'] if name in data['blocks']],
            }
        return result
    return document


def mining_issues(bp):
    """Read actual definitions including every permutation; reject unknown IDs."""
    bp = Path(bp)
    data = contract()
    issues = contract_source_issues(data)
    found = set()
    fields = ('minecraft:destroy_time', 'minecraft:destructible_by_mining', 'netease:tier', 'minecraft:loot')
    for path in sorted((bp / 'netease_blocks').glob('*.json')):
        document = json.loads(path.read_text(encoding='utf-8-sig'))
        body = document['minecraft:block']
        identifier = body['description']['identifier']
        if identifier in found:
            issues.append({'id': identifier, 'reason': 'duplicate block identifier'})
        found.add(identifier)
        if identifier not in data['blocks']:
            issues.append({'id': identifier, 'reason': 'missing independent mining source contract'})
            continue
        expected = normalize(path, document)['minecraft:block']
        for actual, wanted, location in [(body['components'], expected['components'], 'base')] + [
            (p.get('components', {}), e.get('components', {}), 'permutation ' + str(i))
            for i, (p, e) in enumerate(zip(body.get('permutations', []), expected.get('permutations', [])))
        ]:
            for field in ('minecraft:destroy_time', 'minecraft:destructible_by_mining'):
                if field not in actual:
                    continue
                raw = actual[field]
                value = raw.get('value' if field == 'minecraft:destroy_time' else 'seconds_to_destroy') if isinstance(raw, dict) else raw
                unbreakable = field == 'minecraft:destructible_by_mining' and raw is False
                if not unbreakable and type(value) not in (int, float):
                    issues.append({'id': identifier, 'location': location, 'field': field, 'reason': 'hardness must be numeric; boolean is not zero'})
            if 'netease:tier' in actual:
                tier = actual['netease:tier']
                if not isinstance(tier, dict) or type(tier.get('level')) is not int or type(tier.get('destroy_special')) is not bool:
                    issues.append({'id': identifier, 'location': location, 'reason': 'invalid tier field types'})
            for field in fields:
                if actual.get(field) != wanted.get(field):
                    issues.append({'id': identifier, 'location': location, 'field': field,
                                   'actual': actual.get(field), 'expected': wanted.get(field)})
    for identifier in sorted(set(data['blocks']) - found):
        issues.append({'id': identifier, 'reason': 'contracted block missing from pack'})
    found_items = set()
    for path in sorted((bp / 'items').glob('*.json')):
        doc = json.loads(path.read_text(encoding='utf-8-sig'))
        identifier = doc.get('minecraft:item', {}).get('description', {}).get('identifier')
        if identifier in data['items']:
            if identifier in found_items:
                issues.append({'id': identifier, 'reason': 'duplicate tool identifier'})
            found_items.add(identifier)
            if normalize(path, doc) != doc:
                issues.append({'id': identifier, 'reason': 'tool definition violates mining contract'})
            weapon = doc['minecraft:item']['components'].get('netease:weapon', {})
            if any(type(weapon.get(key)) is not int for key in ('level', 'speed', 'attack_damage', 'enchantment')):
                issues.append({'id': identifier, 'reason': 'SDK weapon numeric fields must be integers'})
    for identifier in sorted(set(data['items']) - found_items):
        issues.append({'id': identifier, 'reason': 'contracted tool missing from pack'})
    if not (bp / 'TwilightBossSlice/mining_tool_rules.py').is_file():
        issues.append({'id': 'mining_tool_rules', 'reason': 'fractional-speed runtime missing'})
    loot = bp / EMPTY_LOOT
    if not loot.is_file() or json.loads(loot.read_text(encoding='utf-8-sig')) != {'pools': []}:
        issues.append({'id': EMPTY_LOOT, 'reason': 'missing or nonempty no-drop table'})
    return issues
