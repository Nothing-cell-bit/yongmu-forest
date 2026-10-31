"""Read locked Java vanilla + TF tag layers in datapack order, without writes."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

REFERENCE = Path(__file__).resolve().parent / 'references/mining_tags_1_20_1.json'
REFERENCE_SHA256 = '8fd6420a059db054c7e0ea347c6d226db51a52f857d1088d949bc57dc78563ba'


def merge_layers(layers):
    merged = {}
    for layer in layers:
        for path, document in layer['tags'].items():
            namespace = path.split('/')[1]
            name = path.split('/tags/blocks/')[1][:-5]
            tag = namespace + ':' + name
            if document.get('replace', False):
                merged[tag] = []
            merged.setdefault(tag, []).extend(document['values'])
    return merged


def expand(tags, tag, stack=()):
    if tag in stack:
        raise ValueError('Cyclic upstream tag: ' + ' -> '.join(stack + (tag,)))
    if tag not in tags:
        raise ValueError('Missing required upstream tag: ' + tag)
    result = set()
    for entry in tags[tag]:
        required = entry.get('required', True) if isinstance(entry, dict) else True
        value = entry['id'] if isinstance(entry, dict) else entry
        if value.startswith('#'):
            child = value[1:]
            if child not in tags and not required:
                continue
            result.update(expand(tags, child, stack + (tag,)))
        else:
            result.add(value)
    return result


@lru_cache(maxsize=1)
def source_profiles():
    raw = REFERENCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError('Mining tag reference hash mismatch')
    document = json.loads(raw)
    tags = merge_layers(document['layers'])
    tools = {name: expand(tags, 'minecraft:mineable/' + name)
             for name in ('axe', 'pickaxe', 'hoe', 'shovel')}
    levels = {level: expand(tags, name) for level, name in (
        (0, 'forge:needs_wood_tool'), (1, 'minecraft:needs_stone_tool'),
        (2, 'minecraft:needs_iron_tool'), (3, 'minecraft:needs_diamond_tool'))}
    return tools, levels


def source_tier(upstream, hardness):
    tools, levels = source_profiles()
    effective = [name for name, members in tools.items() if upstream in members]
    if len(effective) > 1:
        raise ValueError('Multiple effective tools require explicit adaptation: ' + upstream)
    digger = {'axe': 'hatchet'}.get(effective[0], effective[0]) if effective and hardness >= 0 else None
    minimum = max((level for level, members in levels.items() if upstream in members), default=0)
    return digger, minimum


def contract_source_issues(document):
    issues = []
    for identifier, rule in document['blocks'].items():
        if rule['upstream'].startswith('project:'):
            continue
        digger, minimum = source_tier(rule['upstream'], rule['hardness'])
        actual = rule['tier']
        if (actual or {}).get('digger') != digger:
            issues.append({'id': identifier, 'reason': 'contract omits/misstates effective tool from merged vanilla and mod tags',
                           'expected': digger, 'actual': (actual or {}).get('digger')})
        if actual and actual['destroy_special'] and actual['level'] != minimum:
            issues.append({'id': identifier, 'reason': 'contract harvest level differs from upstream tags',
                           'expected': minimum, 'actual': actual['level']})
    return issues
