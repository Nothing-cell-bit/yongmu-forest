# -*- coding: utf-8 -*-
"""4.3.2508 goblin combat. tick() is called only on the 20 Hz source clock.

Engine effects are injected through the host/factory so complete damage and
state-transition sequences can be exercised without pretending to run Minecraft.
"""
from __future__ import division
import math
import random

CHAIN = 'tf_slice:block_chain_goblin'
LOWER = 'tf_slice:lower_goblin_knight'
UPPER = 'tf_slice:upper_goblin_knight'
KINDS = (CHAIN, LOWER, UPPER)
SPIKE = 'tf_slice:goblin_spike'
LINK = 'tf_slice:goblin_chain_link'


def distance_sq(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3))


def direction(yaw, pitch=0):
    y, p = math.radians(yaw), math.radians(pitch)
    return (-math.sin(y) * math.cos(p), -math.sin(p), math.cos(y) * math.cos(p))


def incoming_angle(position, attacker, yaw):
    # Preserve Java's asymmetric 150..230 front interval and modulo handling.
    angle = math.degrees(math.atan2(position[2]-attacker[2], position[0]-attacker[0])) - 90
    return abs(math.fmod(yaw - angle, 360))


class GoblinCombat(object):
    def __init__(self, host, factory, level, randrange=None, armor_attribute=12):
        self.h, self.cf, self.level = host, factory, level
        self.roll = randrange or random.randrange
        self.pending_hits = []
        # NetEase AttrType.ARMOR; this is an engine attribute, not a vanilla
        # Bedrock entity component named minecraft:armor.
        self.armor_attribute=armor_attribute

    def state(self, entity):
        return self.h._phantom_urghast_mobs.get(str(entity))

    def restore(self, entity, state):
        defaults = dict(hasArmor=state['type'] in (LOWER, UPPER), shieldHits=0,
                        shieldDisabledTicks=0, chainAngle=0.0, chainMoveLength=0.0,
                        recoilCounter=0, throwing=False, pairSpawned=False)
        for key,value in defaults.items():state.setdefault(key,value)
        try:
            saved=self.cf.CreateExtraData(entity).GetExtraData('tf_slice:goblin_combat')
            if isinstance(saved,dict):
                for key in ('hasArmor','shield','pairSpawned'):
                    if key in saved:state[key]=saved[key]
        except Exception:
            pass
        if state['type'] in (LOWER,UPPER):
            self.h._trigger_entity_event(entity,'tf_slice:goblin_armor' if state['hasArmor'] else 'tf_slice:goblin_break_armor')
        self.sync_armor(entity,state)
        self.presentation(entity,state)

    def sync_armor(self, entity, state):
        value=11 if state['type']==CHAIN else ((17 if state['type']==LOWER else 20) if state.get('hasArmor') else 0)
        if state.get('nativeArmor')==value:return True
        try:
            attr=self.cf.CreateAttr(entity)
            if attr.SetAttrValue(self.armor_attribute,value) is False:
                raise ValueError('armor write rejected')
            if abs(float(attr.GetAttrValue(self.armor_attribute))-value)>0.001:
                raise ValueError('armor readback differs from requested value')
            state['nativeArmor']=value;state.pop('armorError',None)
            return True
        except Exception as error:
            if state.get('armorError')!=str(error):
                print('[TwilightBossSlice][GoblinCombat] armor attribute failed entity=%s: %s' % (entity,error))
            state['armorError']=str(error)
            return False

    def save(self, entity, state):
        data={key:state.get(key) for key in ('hasArmor','shield','pairSpawned')}
        try:self.cf.CreateExtraData(entity).SetExtraData('tf_slice:goblin_combat',data)
        except Exception:pass

    def presentation(self, entity, state):
        if state['type']==UPPER:
            values={'tf_slice:has_shield':bool(state.get('shield')),
                    'tf_slice:shield_disabled':state.get('shieldDisabledTicks',0)>0,
                    'tf_slice:spear_timer':int(state.get('heavySpearTimer',0)),
                    'tf_slice:heavy_spear':state.get('heavySpearTimer',0)>0}
        else:values={}
        if state['type'] in (LOWER,UPPER):values['tf_slice:has_armor']=bool(state.get('hasArmor'))
        for key,value in values.items():
            cache=state.setdefault('goblinProperties',{})
            if cache.get(key)!=value:
                if self.h._set_entity_property(entity,key,value) is not False:cache[key]=value

    def control(self, entity, state, hold, freeze=True):
        mode='hold' if hold else 'fight'
        if state.get('goblinMode')!=mode:
            self.h._trigger_entity_event(entity,'tf_slice:goblin_'+mode)
            if hold:self.h._cancel_move_to_path(entity)
            state['goblinMode']=mode
        if hold and freeze:self.h._set_motion(entity,0.0,0.0)

    def break_shield(self, entity, state):
        if state.get('shield'):
            state['shield']=False
            self.h._play_world_sound('item.shield.break',self.h._get_foot_pos(entity),1,1)
            self.presentation(entity,state);self.save(entity,state)

    def shield_damage(self, entity, state):
        state['shieldHits']=int(state.get('shieldHits',0))+1
        if state['shieldHits']>=3:self.break_shield(entity,state)
        self.save(entity,state)

    def shield_block(self, entity, state, amount, attacker):
        if not state.get('shield') or state.get('shieldDisabledTicks',0)>0:return False
        item=self.h._entity_carried_item(attacker) or {}
        if str(item.get('newItemName',item.get('itemName',''))).endswith('_axe'):
            state['shieldDisabledTicks']=100
        elif amount>10:self.shield_damage(entity,state)
        self.h._play_world_sound('item.shield.block',self.h._get_foot_pos(entity),1,1)
        self.h._set_attack_target(entity,attacker)
        self.presentation(entity,state);self.save(entity,state)
        return True

    @staticmethod
    def cancel(args):
        args['damage']=0;args['knock']=False;args['ignite']=False

    def deal(self, owner, victim, amount):
        # Some Hurt callbacks arrive after the API call returns. A bounded,
        # single-use ticket works for both synchronous and deferred delivery.
        self.pending_hits=[x for x in self.pending_hits if x['expires']>=self.h._tick][-255:]
        ticket={'owner':str(owner),'victim':str(victim),'amount':float(amount),'expires':self.h._tick+2}
        self.pending_hits.append(ticket)
        result=self.h._hurt(victim,amount,owner)
        if result is False and ticket in self.pending_hits:self.pending_hits.remove(ticket)
        return result

    def on_damage(self, args):
        victim=args.get('entityId');attacker=args.get('srcId',args.get('sourceId'))
        try:amount=float(args.get('damage',0))
        except (TypeError,ValueError):return
        if amount<=0:return
        a=self.state(attacker);v=self.state(victim)
        self.pending_hits=[x for x in self.pending_hits if x['expires']>=self.h._tick]
        authored=False
        # Only melee can initiate a spear; environmental/projectile events must
        # not turn into free extra attacks. A mounted upper uses the lower's
        # attack attempt, preventing two independent melee controllers.
        melee=str(args.get('cause','')).lower() in ('entityattack','entity_attack','2')
        if melee:
            for ticket in self.pending_hits:
                if ticket['owner']==str(attacker) and ticket['victim']==str(victim) and abs(ticket['amount']-amount)<0.001:
                    authored=True;self.pending_hits.remove(ticket);break
        if a and a['type'] in (LOWER,UPPER) and not authored and melee:
            owner=str(attacker);upper=a
            if a['type']==LOWER:
                rider=self.state(a.get('riderId'))
                if rider and rider['type']==UPPER and self.h._get_health(str(a['riderId']),0)>0:
                    owner=str(a['riderId']);upper=rider
            if upper['type']==UPPER:
                if upper.get('heavySpearTimer',0)>0 or (a['type']==UPPER and a.get('mountId')):
                    self.cancel(args);return
                upper['targetId']=str(victim)
                if self.roll(2)==0:
                    upper['heavySpearTimer']=60;upper['heavySpearLanded']=False
                    self.control(owner,upper,True)
                    mount=self.state(upper.get('mountId'))
                    if mount:self.control(str(upper['mountId']),mount,True)
                    self.presentation(owner,upper);self.cancel(args);return
                if owner!=str(attacker):
                    self.cancel(args);self.deal(owner,victim,8);return
        if not v or v['type'] not in (LOWER,UPPER):return
        if v['type']==UPPER and v.get('mountId') and str(args.get('cause','')).lower() in ('suffocation','inwall'):
            self.cancel(args);return
        position=self.h._get_foot_pos(victim);source=self.h._get_foot_pos(attacker)
        if position is None or source is None:return
        angle=incoming_angle(position,source,self.h._get_rotation(victim)[1])
        front=150<angle<230
        shield_owner=str(victim);shield_state=v
        if v['type']==LOWER:
            shield_owner=str(v.get('riderId'));shield_state=self.state(shield_owner)
        if front and shield_state and self.shield_block(shield_owner,shield_state,amount,attacker):
            self.cancel(args);return
        if v['type']==UPPER and not front and v.get('shield') and self.roll(2)==0:
            self.shield_damage(str(victim),v)
        if v.get('hasArmor') and (angle>300 or angle<60):
            v['hasArmor']=False
            self.sync_armor(victim,v)
            self.h._trigger_entity_event(victim,'tf_slice:goblin_break_armor')
            self.h._play_world_sound('random.break',position,1,1)
            self.presentation(victim,v);self.save(victim,v)

    def area(self, center, radius, dimension):
        lo=tuple(int(math.floor(v-radius)) for v in center)
        hi=tuple(int(math.ceil(v+radius)) for v in center)
        try:return self.cf.CreateGame(self.level).GetEntitiesInSquareArea(None,lo,hi,dimension) or []
        except Exception:return []

    def intersects(self, entity, center, radius, vertical=None):
        p=self.h._get_foot_pos(entity)
        if p is None:return False
        width,height=0.6,1.8
        try:
            box=self.cf.CreateCollisionBox(entity).GetSize()
            if box:width,height=float(box[0]),float(box[1])
        except Exception:pass
        vertical=radius if vertical is None else vertical
        return (abs(p[0]-center[0])<=radius+width/2 and abs(p[2]-center[2])<=radius+width/2
                and p[1]<=center[1]+vertical and p[1]+height>=center[1]-vertical)

    def land_spear(self, entity, state):
        pos=self.h._get_foot_pos(entity)
        if pos is None:return
        pitch,yaw=self.h._get_rotation(entity);vec=direction(yaw,pitch)
        center=(pos[0]+vec[0]*1.25,pos[1]-(0.75 if state.get('mountId') else 0),pos[2]+vec[2]*1.25)
        for other in self.area(center,2.5,state['dimensionId']):
            if str(other) in (str(entity),str(state.get('mountId'))):continue
            if self.h._get_engine_type(other) in (SPIKE,LINK,'minecraft:item','minecraft:tnt'):continue
            if not self.h._get_health(other,0):continue
            if self.intersects(other,center,1.5):self.deal(entity,other,20)
        self.h._play_world_sound('random.explode',center,0.5,1.3)

    def chain_collisions(self, entity, state, center):
        if state.get('recoilCounter',0)>0:return
        for other in self.area(center,1.75,state['dimensionId']):
            if str(other)==str(entity) or self.h._get_engine_type(other) in (SPIKE,LINK,'minecraft:item','minecraft:tnt'):continue
            if not self.h._get_health(other,0):continue
            box_center=(center[0],center[1]+0.375,center[2])
            if self.intersects(other,box_center,0.575,0.375) and self.deal(entity,other,8) is not False:
                self.h._add_entity_motion(other,0,0.4,0)
                state['recoilCounter']=40;state['throwing']=False
                self.h._play_world_sound('tf_slice.block_chain_goblin.hurt',center,1,1)
                break

    def reset_chain_visual(self, entity, state):
        # Retire every partial external part before showing the model weapon.
        for visual in state.get('goblinVisuals',[]):
            self.h._instant_remove_chain_entity(visual)
        state['goblinVisuals']=[]
        self.h._set_entity_property(entity,'tf_slice:chain_external',False)
        state['chainExternal']=False
        return False

    def chain_visual(self, entity, state, pos, head):
        visuals=state.setdefault('goblinVisuals',[])
        state['visualAge']=state.get('visualAge',0)+1
        kinds=(SPIKE,LINK,LINK,LINK)
        for i,kind in enumerate(kinds):
            if i>=len(visuals) or self.h._get_foot_pos(visuals[i]) is None:
                if i<len(visuals):
                    # Missing position data does not prove the old actor died.
                    self.h._instant_remove_chain_entity(visuals[i])
                new=self.h._spawn_ruin_entity(kind,head,0,state['dimensionId'])
                if new is None:
                    return self.reset_chain_visual(entity,state)
                if i>=len(visuals):visuals.append(str(new))
                else:visuals[i]=str(new)
            if state['visualAge']%20==0:self.h._trigger_entity_event(visuals[i],'tf_slice:keep_alive')
            origin=(pos[0],pos[1]+1.3,pos[2])
            f=1.0 if i==0 else i/4.0
            point=tuple(origin[j]+(head[j]-origin[j])*f for j in range(3))
            try:
                if self.cf.CreatePos(visuals[i]).SetPos(point) is False:
                    raise ValueError('visual position rejected')
                self.cf.CreateRot(visuals[i]).SetRot((0,state['chainAngle']))
            except Exception:
                return self.reset_chain_visual(entity,state)
        if not state.get('chainExternal'):
            if self.h._set_entity_property(entity,'tf_slice:chain_external',True) is False:
                return self.reset_chain_visual(entity,state)
            state['chainExternal']=True
        return True

    def tick_chain(self, entity, state, pos):
        target=self.h._get_attack_target(entity);targetpos=self.h._get_foot_pos(target)
        close=self.h._redcap_lit_tnt(entity,2)
        if close or state.get('chainEvading'):
            threats=close or self.h._redcap_lit_tnt(entity,8)
            if threats or state.get('redcapDestination') is not None:
                state['chainEvading']=True;state['redcapGoal']='evade'
                self.control(entity,state,True,freeze=False)
                self.h._redcap_escape(entity,state,pos,threats)
                state['chainAngle']=(state.get('chainAngle',0)+16)%360
                state['recoilCounter']=max(0,state.get('recoilCounter',0)-1)
                length=max(0,min(6,state.get('chainMoveLength',0)+(0.5 if state.get('throwing') else -1.5)))
                state['chainMoveLength']=length
                if length>=6:state['throwing']=False
                if length:
                    pitch,yaw=self.h._get_rotation(entity);vec=direction(yaw,pitch)
                    head=(pos[0]+vec[0]*length,pos[1]+1.342,pos[2]+vec[2]*length)
                else:
                    radius=0.9 if targetpos is not None and state['recoilCounter']==0 else 0.3
                    a=math.radians(state['chainAngle']);head=(pos[0]+math.cos(a)*radius,pos[1]+1.5-radius/4,pos[2]+math.sin(a)*radius)
                if self.chain_visual(entity,state,pos,head) and targetpos is not None:
                    self.chain_collisions(entity,state,head)
                return
            state['chainEvading']=False;state['redcapGoal']=None
        state['recoilCounter']=max(0,state.get('recoilCounter',0)-1)
        state['chainAngle']=(state.get('chainAngle',0)+16)%360
        # Mojang 1.20.1 Mob.serverAiStep invokes the full GoalSelector only
        # every other source tick. Movement/recoil remain 20 Hz.
        state['goalProbePhase']=(state.get('goalProbePhase',0)+1)%2
        length=state.get('chainMoveLength',0)
        active=length>0 or state.get('throwing',False)
        if not active and state['goalProbePhase']==0:
            cooldown=state.get('chainCooldown',0)
            state['chainCooldown']=max(0,cooldown-1)
            if (cooldown<=0 and targetpos is not None
                    and not self.h._is_invulnerable_player(target)
                    and distance_sq(pos,targetpos)<=42 and self.h._beetle_can_see(pos,targetpos,state['dimensionId'])
                    and self.roll(56)==0):
                state['throwing']=True;state['chainCooldown']=100+self.roll(100)
        length=max(0,min(6,length+(0.5 if state.get('throwing') else -1.5)))
        state['chainMoveLength']=length
        if length>=6:state['throwing']=False
        self.control(entity,state,length>0)
        if length>0:
            pitch,yaw=self.h._get_rotation(entity);vec=direction(yaw,pitch)
            head=(pos[0]+vec[0]*length,pos[1]+1.4*0.78+0.25,pos[2]+vec[2]*length)
            try:
                block=self.h._get_block(tuple(int(math.floor(v)) for v in head),state['dimensionId']) or {}
                if block.get('name') not in (None,'minecraft:air','minecraft:water','minecraft:flowing_water'):
                    state['throwing']=False
            except Exception:pass
        else:
            radius=0.9 if targetpos is not None and state['recoilCounter']==0 else 0.3
            a=math.radians(state['chainAngle']);head=(pos[0]+math.cos(a)*radius,pos[1]+1.5-radius/4,pos[2]+math.sin(a)*radius)
        visible=self.chain_visual(entity,state,pos,head)
        if visible and (length>0 or (targetpos is not None and state['recoilCounter']==0)):
            self.chain_collisions(entity,state,head)

    def tick(self, entity, state, pos):
        self.sync_armor(entity,state)
        if state['type']==CHAIN:self.tick_chain(entity,state,pos);return
        if state['type']==LOWER:
            upper=self.state(state.get('riderId'))
            if upper and self.h._get_health(str(state['riderId']),0)<=0:
                upper=None;state['riderId']=None
            if upper:
                target=self.h._get_attack_target(entity)
                if target and self.h._get_attack_target(str(state['riderId'])) is None:
                    self.h._set_attack_target(str(state['riderId']),target)
                try:self.cf.CreateRot(str(state['riderId'])).SetRot(self.h._get_rotation(entity))
                except Exception:pass
            self.control(entity,state,bool(upper and upper.get('heavySpearTimer',0)>0))
            self.presentation(entity,state);return
        try:
            mount=self.cf.CreateRide(entity).GetEntityRider()
            if self.h._get_engine_type(mount)==LOWER:
                state['mountId']=str(mount)
                lower=self.state(mount)
                if lower:lower['riderId']=str(entity)
            else:state['mountId']=None
        except Exception:pass
        if not state.get('mountId'):self.break_shield(entity,state)
        if state.get('shieldDisabledTicks',0)>0:
            state['shieldDisabledTicks']-=1
            if state['shieldDisabledTicks']==0:self.save(entity,state)
        timer=state.get('heavySpearTimer',0)
        if timer>0:
            state['heavySpearTimer']=timer-1
            target=state.get('targetId') or self.h._get_attack_target(entity)
            if timer-1==25 and target and self.h._get_foot_pos(target) is not None:
                if not self.h._is_invulnerable_player(target):self.land_spear(entity,state)
        self.control(entity,state,bool(state.get('mountId') or state.get('heavySpearTimer',0)>0))
        self.presentation(entity,state)

    def remove(self, entity, state):
        for visual in state.get('goblinVisuals',[]):self.h._instant_remove_chain_entity(visual)
        self.save(entity,state)
