"""Read-only dependency and regression check of the actual repair delta."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tools'))
from native_armor import ARMOR, behavior_document, resource_document
from prepare_reentry_repair_candidate import SCRIPT, methods, SERVER_METHODS


def check(candidate, base, run_lifecycle=True):
    candidate,base=Path(candidate),Path(base)
    receipt=json.loads((candidate/'candidate-receipt.json').read_text('utf-8'))
    issues=[]
    def require(value,message):
        if not value: issues.append(message)
    def read(relative):
        p=candidate/relative
        return p if p.is_file() else base/relative
    def load(relative): return json.loads(read(relative).read_text('utf-8-sig'))
    for rel,entry in receipt['files'].items():
        require((candidate/rel).is_file() and hashlib.sha256((candidate/rel).read_bytes()).hexdigest()==entry['sha256'], 'candidate hash: '+rel)
    for rel,value in receipt['protected'].items():
        require(hashlib.sha256((base/rel).read_bytes()).hexdigest()==value,'protected base changed: '+rel)
    catalog=load('TwilightBossSliceB/item_catalog/crafting_item_catalog.json')['minecraft:crafting_items_catalog']
    ids=[i for c in catalog['categories'] for g in c['groups'] for i in g['items']]
    atlas=load('TwilightBossSliceR/textures/item_texture.json')['texture_data']
    for name in ARMOR:
        require(load('TwilightBossSliceB/netease_items_beh/'+name+'.item.json')==behavior_document(name), 'native armor attributes: '+name)
        require(load('TwilightBossSliceR/netease_items_res/'+name+'.item.json')==resource_document(name), 'native armor resource: '+name)
        require('tf_slice:'+name not in ids,'native ID in vanilla catalog: '+name)
        require(not read('TwilightBossSliceB/items/'+name+'.item.json').exists(),'duplicate modern armor: '+name)
        require('tf_slice:'+name in atlas,'missing native icon: '+name)
    defs=load('TwilightBossSliceR/ui/_ui_defs.json')['ui_defs']
    require(isinstance(defs,list),'ui_defs must be a list')
    for name in ('lich_boss_hud','naga_boss_hud','minoshroom_boss_hud','hydra_boss_hud','portal_loading'):
        rel='ui/'+name+'.json'
        require(rel in defs,'UI definition dependency missing: '+name)
        doc=load('TwilightBossSliceR/'+rel)
        require(doc.get('namespace')==name and doc.get('main',{}).get('type')=='screen','UI screen definition: '+name)
    from PIL import Image
    for rel in receipt['files']:
        if rel.endswith('.png'):
            with Image.open(candidate/rel) as image: image.verify()
    grass=read('TwilightBossSliceR/textures/colormap/grass.png').read_bytes()
    require(hashlib.sha256(grass).hexdigest()=='3ce45136618261acca6be7c1b0302d8c11d38e25e47d373cc45a83063a5148fd','grass palette differs from reviewed restoration')
    # Python 2 parse and Python 3 compilation after print-only translation.
    from lib2to3.refactor import RefactoringTool
    converter=RefactoringTool(['lib2to3.fixes.fix_print'])
    for path in candidate.rglob('*.py'):
        source=path.read_text('utf-8-sig')
        try: compile(str(converter.refactor_string(source.rstrip()+'\n',str(path))),str(path),'exec')
        except Exception as error: issues.append('script syntax: '+str(path)+': '+str(error))
    server=methods((candidate/(SCRIPT+'serverSystem.py')).read_text('utf-8-sig'))
    for name,value in receipt['unchanged_hydra_methods'].items():
        require(hashlib.sha256(server[name].encode('utf-8')).hexdigest()==value,'Hydra method changed: '+name)
    require(server['_drive_hydras'].count('self._recover_hydra_attachments()')==1,'attachment reconciliation entry missing')
    lifecycle=[]
    if run_lifecycle and not issues:
        import tests.test_boss_hud_rejoin as hud
        import tests.test_boss_hud_all_kinds_rejoin as all_hud
        import tests.test_hydra_attachment_rejoin as hydra
        package=candidate/SCRIPT
        with mock.patch.object(hud,'PACKAGE',package),mock.patch.object(all_hud,'PACKAGE',package),mock.patch.object(hydra,'PACKAGE',package):
            cases=[('all six HUDs rejoin',all_hud.test_all_six_rejoin_without_healing_or_early_creation),
                   ('HUD registration False',lambda:all_hud.test_failed_registration_is_bounded_and_retried_for_every_kind(False)),
                   ('HUD registration None',lambda:all_hud.test_failed_registration_is_bounded_and_retried_for_every_kind(None)),
                   ('HUD create None',all_hud.test_native_creation_returning_none_rebinds_instead_of_sticking_registered),
                   ('HUD detached during retry',all_hud.test_packets_during_retry_wait_never_write_detached_controls),
                   ('Hydra head first',lambda:hydra.test_reentry_reuses_saved_heads_before_spawning_replacements(True)),
                   ('Hydra parent first',lambda:hydra.test_reentry_reuses_saved_heads_before_spawning_replacements(False)),
                   ('Hydra inventory and duplicates',hydra.test_inventory_pass_recovers_missing_events_and_deduplicates_only_same_owner_slot),
                   ('Hydra neck and body persistence',hydra.test_necks_and_body_proxies_restore_and_only_legacy_necks_expire),
                   ('Hydra dead and delayed owner',hydra.test_dead_head_is_removed_and_missing_owner_is_retained_for_later_load)]
            cases.append(('Hydra existing parent reload',hydra.test_existing_parent_reload_requests_reconciliation_without_resetting_health))
            for name,case in cases:
                try: case();lifecycle.append(dict(name=name,status='passed'))
                except Exception as error: issues.append(name+': '+repr(error))
        # Execute the bundled sky controller and palette, not the workspace copy.
        def module(name):
            spec=importlib.util.spec_from_file_location('candidate_'+name,package/(name+'.py'))
            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
        environment,palette=module('twilight_environment'),module('biome_sky')
        native=mock.Mock()
        native.GetUseSkyColor.return_value=False
        native.GetSkyColor.return_value=(0.2,0.2,0.2,1.0)
        native.GetSkyTextures.side_effect=lambda:palette.STAR_TEXTURES[:]
        native.SetSkyColor.side_effect=lambda value:setattr(native.GetSkyColor,'return_value',value)
        native.SetSkyTextures.side_effect=lambda value:setattr(native.GetUseSkyColor,'return_value',True)
        desired=[palette.textures_for_biome('dm33027004_swampland')]
        sky=environment.GuardedEnvironment(33027004,palette.textures_for_color(palette.DEFAULT_COLOR),lambda:native,
            wait_frames=1,texture_provider=lambda:desired[0],texture_poll_ticks=1,
            texture_transition=palette.SkyTransition(palette.textures_for_color(palette.DEFAULT_COLOR)),
            star_textures=palette.STAR_TEXTURES,color_decoder=palette.rgba_from_textures)
        for session in range(2):
            sky.begin_change();sky.finish_change(33027004);sky.ui_ready();sky.confirm_arrival(True)
            for _ in range(120): sky.render_frame(False);sky.tick(False)
            require(sky.active and tuple(native.GetSkyColor())==palette.rgba_from_textures(desired[0]),'bundled sky reentry color')
        lifecycle.append(dict(name='bundled sky two entries',status='passed' if not issues else 'see issues'))
    return dict(candidate=str(candidate.resolve()),issues=issues, lifecycle=lifecycle,
                files=len(receipt['files']),unchanged_hydra_methods=len(receipt['unchanged_hydra_methods']),
                runtime_acceptance='not_run',status='passed' if not issues else 'failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--base',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    args=p.parse_args();result=check(args.candidate,args.base)
    args.report.write_text(json.dumps(result,indent=2)+'\n','utf-8')
    print(json.dumps(result,indent=2));sys.exit(bool(result['issues']))
