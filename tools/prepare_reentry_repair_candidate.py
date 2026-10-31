"""Prepare the bounded 2026-10-22 repair delta; no installed writes or builds.

The installed 0.12.5 component is the comparison baseline. Preserve its manifest,
unrelated server methods and release filtering. Require the complete restored
sky dependency set, native armor classification and all six HUD lifecycle fixes.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from native_armor import ARMOR
from prepare_release_candidate import clean_script

SCRIPT = 'TwilightBossSliceB/TwilightBossSlice/'
CLIENT_METHODS = {
    '__init__', '_reset_boss_hud_session', '_on_boss_hud_ui_ready',
    '_can_attempt_boss_hud', 'Destroy', 'OnBlockChainRender',
    '_begin_portal_loading', '_end_portal_loading', 'OnPortalArrivalFinished',
    'OnDimensionChangeClientEvent', 'OnDimensionChangeFinishClientEvent',
    'OnUiInitFinished', '_ensure_lich_boss_hud', '_ensure_naga_boss_hud',
    '_ensure_route_boss_hud', '_get_twilight_biome_sky_textures',
    '_update_guarded_environment',
}
SERVER_METHODS = {
    '__init__', '_register_hydra', '_restore_hydra_part_owner',
    '_restore_hydra_head_owner', '_bind_hydra_neck', '_restore_hydra_neck_owner',
    '_recover_hydra_attachments', '_ensure_hydra_necks', '_drive_hydras', 'OnAddEntity',
}


def methods(text):
    matches = list(re.finditer(r'^    def (\w+)\(', text, re.M))
    return {m.group(1): text[m.start():matches[i+1].start() if i+1<len(matches) else len(text)]
            for i,m in enumerate(matches)}


def digest(data): return hashlib.sha256(data).hexdigest()


def changed_methods(before, after):
    old, new = methods(before), methods(after)
    return {key for key in set(old)|set(new) if old.get(key)!=new.get(key)}


def prepare(base, output):
    base, output = Path(base).resolve(), Path(output).resolve()
    if output.exists(): raise ValueError('Use a new immutable candidate directory')
    if not output.is_relative_to(ROOT / 'deployment_payloads'):
        raise ValueError('Only local deployment_payloads staging is supported')
    files = {}
    for name, allowed in [('clientSystem.py', CLIENT_METHODS), ('serverSystem.py', SERVER_METHODS)]:
        relative = SCRIPT+name
        before = (base/relative).read_text('utf-8-sig')
        after = clean_script(name, (ROOT/relative).read_text('utf-8-sig'))
        if name == 'serverSystem.py':
            # An unrelated shared-workspace preload change is outside this batch.
            method = '_process_portal_background_preloads'
            old, new = methods(before), methods(after)
            after = after.replace(new[method],old[method],1)
        changed = changed_methods(before,after)
        if not changed <= allowed:
            raise ValueError('Unreviewed methods in '+name+': '+repr(sorted(changed-allowed)))
        # Code above the class cannot gain unrelated imports/constants.
        old_prefix = before.split('    def ',1)[0]
        new_prefix = after.split('    def ',1)[0]
        if name == 'clientSystem.py':
            new_prefix = new_prefix.replace('import TwilightBossSlice.biome_sky as biome_sky\n','')
        if old_prefix != new_prefix:
            raise ValueError('Unreviewed script prefix in '+name)
        files[relative] = after.encode('utf-8')
    relatives = [SCRIPT+name for name in (
        'lichBossHudUI.py','nagaBossHudUI.py','routeBossHudUI.py',
        'biome_sky.py','twilight_environment.py')]
    relatives += ['TwilightBossSliceB/netease_items_beh/'+name+'.item.json' for name in ARMOR]
    relatives += ['TwilightBossSliceR/netease_items_res/'+name+'.item.json' for name in ARMOR]
    relatives += ['TwilightBossSliceB/item_catalog/crafting_item_catalog.json',
                  'TwilightBossSliceR/textures/colormap/grass.png',
                  'TwilightBossSliceR/ui/portal_loading.json']
    relatives += ['TwilightBossSliceR/textures/environment/twilight_stars_alpha/'+name+'.png'
                  for name in ('negative_x','negative_y','negative_z','positive_x','positive_y','positive_z')]
    for relative in relatives: files[relative] = (ROOT/relative).read_bytes()
    # Dependencies intentionally retained from the running component must agree.
    protected = {}
    for relative in [SCRIPT+'config.py', SCRIPT+'biome_catalog.py', SCRIPT+'hydra_logic.py',
                     SCRIPT+'boss_hud_logic.py', 'TwilightBossSliceR/ui/_ui_defs.json']:
        expected = (ROOT/relative).read_bytes()
        if relative.endswith('config.py'):
            expected=clean_script('config.py',expected.decode('utf-8-sig')).encode('utf-8')
        if expected != (base/relative).read_bytes():
            raise ValueError('Base dependency differs: '+relative)
        protected[relative] = digest(expected)
    for pack in ('TwilightBossSliceB','TwilightBossSliceR'):
        relative=pack+'/manifest.json';protected[relative]=digest((base/relative).read_bytes())
    # Every existing Hydra method outside the attachment maintenance set stays
    # byte-identical, including all damage, targeting, hurt and death paths.
    before=methods((base/(SCRIPT+'serverSystem.py')).read_text('utf-8-sig'))
    after=methods(files[SCRIPT+'serverSystem.py'].decode('utf-8'))
    combat={name:digest(body.encode('utf-8')) for name,body in before.items()
            if 'hydra' in name and name not in SERVER_METHODS}
    for name,value in combat.items():
        if digest(after[name].encode('utf-8'))!=value: raise ValueError('Hydra logic changed: '+name)
    receipt=dict(base=str(base), output=str(output), source_hashes={}, files={},
                 protected=protected, unchanged_hydra_methods=combat,
                 runtime_acceptance='not_run', generated_rebuild='not_run')
    for relative,data in sorted(files.items()):
        path=output/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        original=base/relative
        receipt['files'][relative]=dict(sha256=digest(data),
            before=digest(original.read_bytes()) if original.is_file() else None)
        receipt['source_hashes'][relative]=digest((ROOT/relative).read_bytes())
        if path.suffix=='.py' and original.is_file():
            diff=''.join(difflib.unified_diff(original.read_text('utf-8-sig').splitlines(True),
                      data.decode('utf-8').splitlines(True),fromfile='installed/'+relative,tofile='candidate/'+relative))
            target=output.parent/(output.name+'-review')/relative
            target=target.with_suffix(target.suffix+'.diff');target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(diff,'utf-8')
    (output/'candidate-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n','utf-8')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();r=prepare(args.base,args.output)
    print(json.dumps(dict(files=len(r['files']), protected=len(r['protected']),
        unchanged_hydra_methods=len(r['unchanged_hydra_methods']), output=r['output']),indent=2))
