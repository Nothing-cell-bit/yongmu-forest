"""Combat-level contracts for the locked 4.3.2508 goblins."""
import sys
import json
import re
import ast
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'TwilightBossSliceB/TwilightBossSlice'))
import phantom_urghast_mob_logic as legacy
try:
    import goblin_combat as g
except ImportError:
    g=None


class SourceRegression(unittest.TestCase):
    def test_one_strong_hit_does_not_destroy_shield(self):
        self.assertFalse(legacy.shield_hit_result(11,True,True)['breakShield'])


class Host:
    def __init__(self):
        self._phantom_urghast_mobs={}
        self.pos={'lower':(0,64,0),'upper':(0,65.1,0),'player':(0,64,2),'chain':(0,64,0)}
        self.types={'lower':g.LOWER,'upper':g.UPPER,'chain':g.CHAIN,'player':'minecraft:player'}
        self.targets={'lower':'player','upper':'player','chain':'player'}
        self.events=[];self.damage=[];self.props={};self.motion=[];self._tick=0;self.armor={}
        self._ur_ghast_logic_tick=0;self.rng=0;self.item='minecraft:iron_sword'
        self.visual_serial=0
    def _get_foot_pos(self,e):return self.pos.get(e)
    def _get_engine_type(self,e):return self.types.get(e)
    def _get_attack_target(self,e):return self.targets.get(e)
    def _set_attack_target(self,e,t):self.targets[e]=t
    def _get_rotation(self,e):return (0,0)
    def _trigger_entity_event(self,e,v):self.events.append((e,v));return True
    def _set_entity_property(self,e,k,v):self.props[e,k]=v;return True
    def _cancel_move_to_path(self,e):return True
    def _set_motion(self,*args):self.motion.append(args)
    def _add_entity_motion(self,*args):self.motion.append(args)
    def _hurt(self,e,n,a,*args):self.damage.append((e,n,a));return True
    def _entity_carried_item(self,e):return {'newItemName':self.item}
    def _beetle_can_see(self,*args):return True
    def _is_invulnerable_player(self,e):return False
    def _get_health(self,e,fallback):return 20 if self.types.get(e) not in (g.SPIKE,g.LINK,'minecraft:item','minecraft:tnt') else 0
    def _get_block(self,p,d):return {'name':'minecraft:air'}
    def _play_world_sound(self,*args):pass
    def _spawn_ruin_entity(self,kind,p,y,d):
        self.visual_serial+=1
        e='visual'+str(self.visual_serial);self.pos[e]=p;self.types[e]=kind;return e
    def _instant_remove_chain_entity(self,e):self.pos.pop(e,None)
    def _redcap_lit_tnt(self,*args):return []


class CombatTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(g,'Dedicated goblin combat implementation is required')
        self.h=Host()
        self.cf=types.SimpleNamespace(
            CreateGame=lambda _:types.SimpleNamespace(GetEntitiesInSquareArea=lambda *a:list(self.h.pos)),
            CreatePos=lambda e:types.SimpleNamespace(SetPos=lambda p:self.h.pos.__setitem__(e,p)),
            CreateRot=lambda e:types.SimpleNamespace(SetRot=lambda p:True),
            CreateAttr=lambda e:types.SimpleNamespace(
                SetAttrValue=lambda attr,value:self.h.armor.__setitem__(e,value) is None,
                GetAttrValue=lambda attr:self.h.armor.get(e,0)),
        )
        self.c=g.GoblinCombat(self.h,self.cf,'level',randrange=lambda n:self.h.rng%n)
        for e in ['lower','upper','chain']:
            s=legacy.create_mob_state(self.h.types[e]);s['dimensionId']=7
            self.h._phantom_urghast_mobs[e]=s;self.c.restore(e,s)
        self.lower=self.h._phantom_urghast_mobs['lower'];self.upper=self.h._phantom_urghast_mobs['upper']
        self.lower['riderId']='upper';self.upper['mountId']='lower'
    def attack(self,src='lower',target='player',amount=8):
        args={'srcId':src,'entityId':target,'damage':amount,'cause':'EntityAttack'}
        self.c.on_damage(args);return args
    def test_heavy_spear_replaces_hit_and_suppresses_followups(self):
        self.assertEqual(0,self.attack()['damage'])
        self.assertEqual(60,self.upper['heavySpearTimer'])
        self.assertEqual(0,self.attack(src='lower')['damage'])
        self.assertIn(('lower','tf_slice:goblin_hold'),self.h.events)
    def test_regular_branch_relays_lower_attack_to_rider(self):
        self.h.rng=1
        self.assertEqual(0,self.attack(src='lower',amount=4)['damage'])
        self.assertIn(('player',8,'upper'),self.h.damage)
        self.assertEqual(0,self.upper['heavySpearTimer'])
    def test_spear_lands_in_front_and_hits_multiple_entities(self):
        self.h.pos.update({'a':(0,64,1.25),'b':(1,64,1.25),'behind':(0,64,-3)})
        self.c.land_spear('upper',self.upper)
        hit={x[0] for x in self.h.damage}
        self.assertTrue({'a','b'}.issubset(hit));self.assertNotIn('lower',hit);self.assertNotIn('behind',hit)
    def test_shield_three_hits_and_axe_timeout(self):
        for i in range(3):
            self.attack(src='player',target='upper',amount=11)
            self.assertEqual(i<2,self.upper['shield'])
        self.upper['shield']=True;self.h.item='minecraft:iron_axe'
        self.assertEqual(0,self.attack(src='player',target='upper')['damage'])
        self.assertEqual(100,self.upper['shieldDisabledTicks'])
        self.assertGreater(self.attack(src='player',target='upper')['damage'],0)
    def test_front_shield_protects_mount(self):
        self.assertEqual(0,self.attack(src='player',target='lower')['damage'])
    def test_rear_hit_breaks_armor(self):
        self.h.pos['player']=(0,64,-2)
        self.attack(src='player',target='lower')
        self.assertFalse(self.lower['hasArmor'])
        self.assertIn(('lower','tf_slice:goblin_break_armor'),self.h.events)

    def test_native_armor_attribute_is_applied_and_removed_on_rear_hit(self):
        self.assertEqual({'lower':17,'upper':20,'chain':11},self.h.armor)
        self.h.pos['player']=(0,64,-2)
        self.attack(src='player',target='lower')
        self.assertEqual(0,self.h.armor['lower'])

    def test_failed_armor_clear_is_not_cached_as_success(self):
        self.upper['hasArmor']=False
        self.cf.CreateAttr=lambda e:types.SimpleNamespace(SetAttrValue=lambda *args:True,GetAttrValue=lambda attr:20)
        self.assertFalse(self.c.sync_armor('upper',self.upper))
        self.assertEqual(20,self.upper['nativeArmor'])
    def test_dismounted_upper_breaks_shield(self):
        self.upper['mountId']=None
        self.c.tick('upper',self.upper,self.h.pos['upper'])
        self.assertFalse(self.upper['shield'])

    def test_native_ride_link_rebinds_then_drops_shield_when_released(self):
        self.upper['mountId']=None
        self.cf.CreateRide=lambda e:types.SimpleNamespace(GetEntityRider=lambda:'lower')
        self.c.tick('upper',self.upper,self.h.pos['upper'])
        self.assertEqual('lower',self.upper['mountId']);self.assertTrue(self.upper['shield'])
        self.cf.CreateRide=lambda e:types.SimpleNamespace(GetEntityRider=lambda:None)
        self.c.tick('upper',self.upper,self.h.pos['upper']);self.assertFalse(self.upper['shield'])
    def test_spear_timer_advances_on_source_ticks_only(self):
        self.attack()
        for i in range(90):
            if (i+1)*20//30>i*20//30:
                self.c.tick('upper',self.upper,self.h.pos['upper'])
        self.assertEqual(0,self.upper['heavySpearTimer'])
        self.assertEqual(1,sum(e=='player' and n==20 for e,n,_ in self.h.damage))
    def test_chain_extension_retraction_and_recoil(self):
        s=self.h._phantom_urghast_mobs['chain'];s['throwing']=True
        self.h.pos.pop('lower');self.h.pos.pop('upper');self.h.pos['player']=(0,64,20)
        for _ in range(12):self.c.tick('chain',s,self.h.pos['chain'])
        self.assertEqual(6,s['chainMoveLength'])
        self.assertFalse(s['throwing'])
        for _ in range(4):self.c.tick('chain',s,self.h.pos['chain'])
        self.assertEqual(0,s['chainMoveLength'])
    def test_chain_collision_uses_eight_damage_and_recoil(self):
        s=self.h._phantom_urghast_mobs['chain']
        self.c.chain_collisions('chain',s,(0,65,2))
        self.assertIn(('player',8,'chain'),self.h.damage)
        self.assertEqual(40,s['recoilCounter'])
        self.assertIn(('player',0,0.4,0),self.h.motion)

    def test_mounted_upper_cannot_deliver_a_second_independent_melee_hit(self):
        self.h.rng=1
        self.assertEqual(0,self.attack(src='upper')['damage'])
        self.assertEqual([],self.h.damage)

    def test_dead_upper_does_not_steal_the_lowers_attack_before_remove_event(self):
        self.h._get_health=lambda e,fallback:0 if e=='upper' else 20
        self.assertEqual(4,self.attack(src='lower',amount=4)['damage'])
        self.upper['heavySpearTimer']=30
        self.c.tick('lower',self.lower,self.h.pos['lower'])
        self.assertEqual('fight',self.lower['goblinMode'])

    def test_no_attacker_and_unrelated_mob_damage_is_unchanged(self):
        args={'entityId':'player','srcId':'zombie','damage':5,'cause':'EntityAttack'}
        self.c.on_damage(args);self.assertEqual(5,args['damage'])
        self.assertEqual(8,self.attack(src=None,target='upper')['damage'])

    def test_disabled_shield_recovers_without_becoming_a_new_shield(self):
        self.h.item='minecraft:iron_axe';self.attack(src='player',target='upper')
        self.upper['shieldHits']=2
        for _ in range(100):self.c.tick('upper',self.upper,self.h.pos['upper'])
        self.assertEqual(0,self.upper['shieldDisabledTicks'])
        self.assertEqual(2,self.upper['shieldHits'])
        self.h.item='minecraft:iron_sword'
        self.assertEqual(0,self.attack(src='player',target='upper',amount=5)['damage'])

    def test_shield_does_not_block_sides_and_rear(self):
        self.h.rng=1
        for pos in [(2,64,0),(0,64,-2),(-2,64,0)]:
            self.h.pos['player']=pos
            self.assertEqual(8,self.attack(src='player',target='upper')['damage'])

    def test_authored_spear_hit_does_not_reenter_attack_selection(self):
        def damage(victim,amount,owner,*args):
            event={'srcId':owner,'entityId':victim,'damage':amount,'cause':'EntityAttack'}
            self.c.on_damage(event);self.h.damage.append((victim,event['damage'],owner));return True
        self.h._hurt=damage
        self.c.deal('upper','player',20)
        self.assertEqual([('player',20,'upper')],self.h.damage)
        self.assertEqual(0,self.upper['heavySpearTimer'])

    def test_deferred_authored_hit_survives_after_hurt_call_returns(self):
        self.c.deal('upper','player',20)
        self.h._tick=1
        args={'srcId':'upper','entityId':'player','damage':20,'cause':'entity_attack'}
        self.c.on_damage(args)
        self.assertEqual(20,args['damage'])
        self.assertEqual(0,self.upper['heavySpearTimer'])
        again=dict(args)
        self.c.on_damage(again)
        self.assertEqual(0,again['damage'], 'A pending authored hit may only be consumed once')

    def test_standalone_upper_has_the_same_half_chance_to_prepare_spear(self):
        self.upper['mountId']=None
        self.assertEqual(0,self.attack(src='upper')['damage'])
        self.assertEqual(60,self.upper['heavySpearTimer'])

    def test_pair_target_and_orientation_follow_the_mount(self):
        self.h.targets['upper']=None
        self.c.tick('lower',self.lower,self.h.pos['lower'])
        self.assertEqual('player',self.h.targets['upper'])

    def test_chain_parts_are_recreated_and_removed_with_owner(self):
        s=self.h._phantom_urghast_mobs['chain'];self.h.rng=1
        self.c.tick('chain',s,self.h.pos['chain'])
        self.assertEqual(4,len(s['goblinVisuals']))
        old=s['goblinVisuals'][0];self.h.pos.pop(old)
        self.c.tick('chain',s,self.h.pos['chain'])
        self.assertNotEqual(old,s['goblinVisuals'][0])
        self.c.remove('chain',s)
        self.assertTrue(all(e not in self.h.pos for e in s['goblinVisuals']))

    def test_failed_visual_position_does_not_enable_invisible_chain_damage(self):
        state=self.h._phantom_urghast_mobs['chain']
        self.cf.CreatePos=lambda e:types.SimpleNamespace(SetPos=lambda p:False)
        self.assertFalse(self.c.chain_visual('chain',state,self.h.pos['chain'],(1,65,0)))
        self.assertFalse(self.h.props['chain','tf_slice:chain_external'])
        self.assertFalse(state['goblinVisuals'])
        self.assertFalse(any(e in self.h.pos for e,k in self.h.types.items() if k==g.SPIKE))

    def test_partial_chain_spawn_failure_removes_head_before_restoring_model(self):
        state=self.h._phantom_urghast_mobs['chain']
        spawn=self.h._spawn_ruin_entity
        self.h._spawn_ruin_entity=lambda kind,*args: None if kind==g.LINK else spawn(kind,*args)
        write=self.h._set_entity_property
        def checked_write(e,k,v):
            if k=='tf_slice:chain_external' and v is False:
                self.assertFalse(any(x in self.h.pos for x,t in self.h.types.items() if t==g.SPIKE))
            return write(e,k,v)
        self.h._set_entity_property=checked_write
        self.assertFalse(self.c.chain_visual('chain',state,self.h.pos['chain'],(1,65,0)))
        self.assertEqual([],state['goblinVisuals'])

    def test_rejected_model_hide_removes_external_weapon_and_disables_damage(self):
        state=self.h._phantom_urghast_mobs['chain']
        self.h._set_entity_property=lambda *args:False
        self.assertFalse(self.c.chain_visual('chain',state,self.h.pos['chain'],(1,65,0)))
        self.assertEqual([],state['goblinVisuals'])
        self.assertFalse(state.get('chainExternal'))

    def test_replaced_visual_is_explicitly_removed_even_if_position_is_unavailable(self):
        state=self.h._phantom_urghast_mobs['chain']
        self.c.chain_visual('chain',state,self.h.pos['chain'],(1,65,0))
        old=state['goblinVisuals'][0];getpos=self.h._get_foot_pos
        self.h._get_foot_pos=lambda e:None if e==old else getpos(e)
        removed=[];remove=self.h._instant_remove_chain_entity
        def record_remove(e):
            removed.append(e);remove(e)
        self.h._instant_remove_chain_entity=record_remove
        self.c.chain_visual('chain',state,self.h.pos['chain'],(1,65,0))
        self.assertIn(old,removed)

    def test_chain_cooldown_does_not_count_down_during_the_throw(self):
        s=self.h._phantom_urghast_mobs['chain'];s['throwing']=True;s['chainCooldown']=123
        self.h.pos={'chain':(0,64,0),'player':(0,64,20)}
        for _ in range(16):self.c.tick('chain',s,self.h.pos['chain'])
        self.assertEqual(123,s['chainCooldown'])
        self.c.tick('chain',s,self.h.pos['chain']);self.assertEqual(123,s['chainCooldown'])
        self.c.tick('chain',s,self.h.pos['chain']);self.assertEqual(122,s['chainCooldown'])

    def test_chain_hits_wall_then_retracts_without_breaking_blocks(self):
        s=self.h._phantom_urghast_mobs['chain'];s['throwing']=True
        self.h._get_block=lambda *args:{'name':'minecraft:stone'}
        self.c.tick('chain',s,self.h.pos['chain'])
        self.assertFalse(s['throwing'])

    def test_tnt_escape_issues_a_path_without_equipping_a_redcap_pickaxe(self):
        s=self.h._phantom_urghast_mobs['chain'];calls=[]
        self.h._redcap_lit_tnt=lambda *args:['tnt']
        self.h._redcap_escape=lambda *args:calls.append(args)
        self.c.tick('chain',s,self.h.pos['chain'])
        self.assertTrue(calls);self.assertEqual('evade',s['redcapGoal'])
        self.assertFalse(any(call[0]=='chain' for call in self.h.motion), 'Escape navigation must not be cancelled by a zero-velocity freeze')

    def test_tnt_escape_does_not_freeze_the_existing_chain_motion(self):
        s=self.h._phantom_urghast_mobs['chain'];s.update(throwing=True,chainMoveLength=2.0,recoilCounter=10)
        self.h.pos['player']=(0,64,20)
        self.h._redcap_lit_tnt=lambda *args:['tnt']
        self.h._redcap_escape=lambda *args:None
        self.c.tick('chain',s,self.h.pos['chain'])
        self.assertEqual(2.5,s['chainMoveLength'])
        self.assertEqual(9,s['recoilCounter'])

    def test_only_durable_armor_and_shield_state_is_saved(self):
        data={}
        self.cf.CreateExtraData=lambda e:types.SimpleNamespace(GetExtraData=lambda k:data.get(k),SetExtraData=lambda k,v:data.__setitem__(k,v))
        self.upper.update(hasArmor=False,shield=False,shieldHits=2,shieldDisabledTicks=40)
        self.c.save('upper',self.upper)
        fresh=legacy.create_mob_state(g.UPPER);self.c.restore('upper',fresh)
        self.assertFalse(fresh['hasArmor']);self.assertFalse(fresh['shield'])
        self.assertEqual(0,fresh['shieldHits']);self.assertEqual(0,fresh['shieldDisabledTicks'])

    def test_loading_an_existing_pair_records_that_the_upper_was_already_created(self):
        source=(ROOT/'TwilightBossSliceB/TwilightBossSlice/serverSystem.py').read_text(encoding='utf-8')
        start=source.index('    def _register_phantom_urghast_mob(')
        end=source.index('    def ',start+8)
        ns={'phantom_urghast_mob_logic':legacy,'goblin_combat':g,
            'PHANTOM_UR_GHAST_MOB_IDENTIFIERS':g.KINDS,
            'LOWER_GOBLIN_KNIGHT_IDENTIFIER':g.LOWER,'UPPER_GOBLIN_KNIGHT_IDENTIFIER':g.UPPER}
        exec('class Adapter:\n'+source[start:end],ns)
        self.h._register_phantom_urghast_mob=types.MethodType(ns['Adapter']._register_phantom_urghast_mob,self.h)
        self.h._valid_entity_id=lambda e:True
        self.h._ride_passengers=lambda e:['upper']
        self.h._mount_goblin_knight=lambda *args:True
        self.h._goblin_combat=self.c
        self.h._phantom_urghast_mobs.pop('lower')
        state=self.h._register_phantom_urghast_mob('lower',g.LOWER,7)
        self.assertTrue(state['pairSpawned'])


class ResourceIntegration(unittest.TestCase):
    def test_real_property_adapter_preserves_boolean_type(self):
        from lib2to3.refactor import RefactoringTool
        import textwrap
        source=(ROOT/'TwilightBossSliceB/TwilightBossSlice/serverSystem.py').read_text(encoding='utf-8')
        start=source.index('    def _set_entity_property(')
        end=source.index('\n    def ',start+5)
        method=str(RefactoringTool(['lib2to3.fixes.fix_print']).refactor_string(textwrap.dedent(source[start:end])+'\n','adapter'))
        received=[]
        factory=types.SimpleNamespace(CreateQueryVariable=lambda e:types.SimpleNamespace(
            SetPropertyValue=lambda k,v:received.append((k,v)) or True))
        ns={'CF':factory};exec(method,ns)
        for value in (True,False,25,0,0.5,'query.property(\'tf_slice:x\')'):
            self.assertTrue(ns['_set_entity_property'](None,'chain','tf_slice:chain_external',value))
            actual=received[-1][1]
            if isinstance(value,bool):
                self.assertIs(type(actual),bool,'Boolean entity properties must not become Molang strings')
                self.assertIs(actual,value)
            else:self.assertEqual(str(value),actual)

    def test_host_calls_match_real_server_method_signatures(self):
        from lib2to3.refactor import RefactoringTool
        source=(ROOT/'TwilightBossSliceB/TwilightBossSlice/serverSystem.py').read_text(encoding='utf-8')
        tree=ast.parse(str(RefactoringTool(['lib2to3.fixes.fix_print']).refactor_string(source,'serverSystem.py')))
        server=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ServerSystem')
        methods={n.name:n for n in server.body if isinstance(n,ast.FunctionDef)}
        module=ast.parse((ROOT/'TwilightBossSliceB/TwilightBossSlice/goblin_combat.py').read_text())
        for call in ast.walk(module):
            if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute):continue
            obj=call.func.value
            if not (isinstance(obj,ast.Attribute) and obj.attr=='h' and isinstance(obj.value,ast.Name) and obj.value.id=='self'):continue
            method=methods[call.func.attr]
            positional=len(method.args.args)-1
            required=positional-len(method.args.defaults)
            self.assertGreaterEqual(len(call.args),required,call.func.attr)
            if method.args.vararg is None:self.assertLessEqual(len(call.args),positional,call.func.attr)

    def test_attack_hold_removes_native_movement_and_melee(self):
        for name,armor in [('block_chain_goblin',11),('lower_goblin_knight',17),('upper_goblin_knight',20)]:
            e=json.loads((ROOT/('TwilightBossSliceB/entities/'+name+'.entity.json')).read_text())['minecraft:entity']
            self.assertNotIn('minecraft:behavior.melee_attack',e['components'])
            self.assertIn('minecraft:behavior.melee_attack',e['component_groups']['tf_slice:goblin_normal'])
            self.assertNotIn('minecraft:armor',e['components'],'Use the supported NetEase ARMOR attribute API')
            self.assertEqual(['tf_slice:goblin_normal'],e['events']['tf_slice:goblin_hold']['remove']['component_groups'])
            if name=='lower_goblin_knight':
                self.assertEqual([0,1.0,0],e['components']['minecraft:rideable']['seats']['position'])

    def test_driver_is_invoked_only_on_source_tick_and_damage_is_intercepted_before_health(self):
        s=(ROOT/'TwilightBossSliceB/TwilightBossSlice/serverSystem.py').read_text(encoding='utf-8')
        self.assertIn('self._listen_engine("DamageEvent", self.OnGoblinDamageEvent)',s)
        self.assertIn('if urGhastLogicStep:\n                    self._goblin_combat.tick',s)
        handler=s[s.index('    def OnActuallyHurtServerEvent('):]
        self.assertNotIn('phantom_urghast_mob_logic.start_heavy_spear(',handler)
        self.assertNotIn('phantom_urghast_mob_logic.shield_hit_result(',s)

    def test_visual_parts_are_non_damageable_and_have_a_cleanup_lease(self):
        for name in ['goblin_spike','goblin_chain_link']:
            e=json.loads((ROOT/('TwilightBossSliceB/entities/'+name+'.entity.json')).read_text())['minecraft:entity']
            self.assertFalse(e['components']['minecraft:physics']['has_collision'])
            self.assertIn('tf_slice:visual_lease',e['component_groups'])
            self.assertFalse(e['components']['minecraft:damage_sensor']['triggers'][0]['deals_damage'])

    def test_legacy_entrypoints_cannot_restore_player_weapon_or_single_target_spear(self):
        s=(ROOT/'TwilightBossSliceB/TwilightBossSlice/serverSystem.py').read_text(encoding='utf-8')
        section=s[s.index('    def _launch_goblin_chain('):s.index('    @staticmethod\n    def _borer_scan_offset')]
        self.assertNotIn('BLOCK_CHAIN_PROJECTILE',section)
        self.assertIn('self._goblin_combat.land_spear',section)


if __name__=='__main__':unittest.main()
