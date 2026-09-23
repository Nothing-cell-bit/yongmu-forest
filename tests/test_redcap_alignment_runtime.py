"""Execute redcap goals against a small world, without starting Minecraft."""
import json
import math
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def runtime_class():
    source = (ROOT / 'TwilightBossSliceB/TwilightBossSlice/serverSystem.py').read_text(encoding='utf-8')
    methods = []
    for match in re.finditer(r'^    def (_redcap_\w+|_update_redcap|_target_is_looking_at|_ignite_nearby_tnt)\(', source, re.M):
        end = re.search(r'^    (?:def |@)', source[match.end():], re.M)
        methods.append(source[match.start():match.end() + end.start() if end else len(source)])
    namespace = {'math': math, '_distance_sq': lambda a, b: sum((x-y)**2 for x, y in zip(a, b)), 'LEVEL_ID': 'level'}
    exec('class Runtime:\n' + ''.join(methods), namespace)
    return namespace['Runtime'], namespace


class RedcapRuntimeTests(unittest.TestCase):
    def setUp(self):
        cls, ns = runtime_class()
        self.mob = cls()
        self.mob._tick = 100
        self.state = {'type': 'tf_slice:redcap_sapper', 'dimensionId': 7, 'tntLeft': 3, 'circleSign': 1.0}
        self.pos = (0.5, 64.0, 0.5)
        self.target = (0.5, 64.0, 4.5)
        self.target_id = 'player'
        self.yaw = 0.0
        self.blocks = {}
        self.primed = []
        self.tnt_positions = {}
        self.writes = []
        self.items = []
        self.commands = []
        self.paths = []
        self.events = []
        self.motion = []
        self.rotations = []
        self.griefing = True
        self.write_ok = True
        self.spawn_ok = True
        self.mob._get_attack_target = lambda _: self.target_id
        self.mob._get_foot_pos = lambda eid: self.pos if eid == 'mob' else self.tnt_positions.get(eid, (1.5, 64.0, 0.5)) if eid in self.primed else self.target
        self.mob._get_dimension = lambda eid: 7
        self.mob._get_rotation = lambda _: (0, self.yaw)
        self.mob._mob_griefing = lambda: self.griefing
        self.mob._get_block = lambda p, d: {'name': self.blocks.get(tuple(p), 'minecraft:stone' if p[1] < 64 else 'minecraft:air')}
        self.mob._set_block = self.set_block
        self.mob._set_entity_carried_item = lambda eid, item: self.items.append(item) is None
        self.mob._set_motion = lambda *args: self.motion.append(args)
        self.mob._trigger_entity_event = lambda eid, event: self.events.append(event) is None
        self.mob._cancel_move_to_path = lambda eid: True
        self.mob._look_along = lambda *args: self.rotations.append(args)
        self.mob._play_world_sound = lambda *args: None
        self.mob._get_engine_type = lambda eid: 'minecraft:tnt' if eid in self.primed else 'minecraft:player'
        self.mob.CreateEngineEntityByTypeStr = self.spawn
        self.mob.DestroyEntity = lambda eid: self.primed.remove(eid)
        ns['CF'] = types.SimpleNamespace(
            CreateCommand=lambda _: types.SimpleNamespace(SetCommand=lambda cmd: self.commands.append(cmd)),
            CreateGame=lambda _: types.SimpleNamespace(GetEntitiesAround=lambda *a: list(self.primed), GetEntitiesInSquareArea=lambda *a: list(self.primed) + ['player']),
            CreateBlock=lambda _: types.SimpleNamespace(GetBlockPaletteBetweenPos=self.palette),
            CreateMoveTo=lambda _: types.SimpleNamespace(SetMoveSetting=lambda *a: self.paths.append(a) is None),
        )

    def palette(self, dimension, start, end, eliminate_air):
        positions = [tuple(p[i]-start[i] for i in range(3)) for p, name in self.blocks.items()
                     if name == 'minecraft:tnt' and all(start[i] <= p[i] <= end[i] for i in range(3))]
        return types.SimpleNamespace(GetLocalPosListOfBlocks=lambda *args: positions)

    def set_block(self, p, name, dimension):
        if not self.write_ok:
            return False
        self.writes.append((tuple(p), name, dimension))
        self.blocks[tuple(p)] = name
        return True

    def spawn(self, kind, pos, rot, dimension):
        if not self.spawn_ok:
            return None
        self.primed.append('tnt')
        self.tnt_positions['tnt'] = pos
        return 'tnt'

    def update(self):
        self.mob._update_redcap('mob', self.state, self.pos)

    def test_sapper_places_unlit_block_and_consumes_one(self):
        self.update()
        self.assertEqual('minecraft:tnt', self.blocks.get((0, 64, 0)))
        self.assertEqual(2, self.state['tntLeft'])
        self.assertFalse(self.primed)
        self.assertFalse(self.commands)

    def test_failed_placement_does_not_consume_inventory(self):
        self.write_ok = False
        self.update()
        self.assertEqual(3, self.state['tntLeft'])

    def test_solid_feet_or_nearby_primed_tnt_prevents_planting(self):
        self.blocks[(0, 64, 0)] = 'minecraft:stone'
        self.update()
        self.assertEqual(3, self.state['tntLeft'])
        self.blocks.clear()
        self.primed.append('lit')
        self.update()
        self.assertEqual(3, self.state['tntLeft'])

    def test_vertical_distance_counts_for_planting(self):
        self.target = (0.5, 74.0, 0.5)
        self.update()
        self.assertEqual(3, self.state['tntLeft'])

    def test_ordinary_redcap_never_plants(self):
        self.state['type'] = 'tf_slice:redcap'
        self.update()
        self.assertFalse(self.writes)
        self.assertFalse(self.commands)

    def test_griefing_disabled_prevents_all_tnt_writes(self):
        self.griefing = False
        self.blocks[(1, 64, 0)] = 'minecraft:tnt'
        self.update()
        self.assertFalse(self.writes)
        self.assertEqual(3, self.state['tntLeft'])

    def test_no_target_still_lights_diagonally_nearby_tnt(self):
        self.target_id = None
        self.blocks[(1, 64, 1)] = 'minecraft:tnt'
        self.update()
        self.assertTrue(self.primed)
        self.assertEqual('minecraft:air', self.blocks[(1, 64, 1)])

    def test_distant_tnt_is_pursued_instead_of_ignited_remotely(self):
        self.blocks[(4, 64, 0)] = 'minecraft:tnt'
        self.update()
        self.assertFalse(self.primed)
        self.assertFalse(self.commands)
        self.assertTrue(self.paths)
        self.assertEqual('minecraft:tnt', self.blocks[(4, 64, 0)])
        self.assertEqual(3, self.state['tntLeft'])
        self.assertIn('minecraft:flint_and_steel', [x['newItemName'] for x in self.items])

    def test_failed_spawn_preserves_tnt_block(self):
        self.spawn_ok = False
        self.blocks[(1, 64, 0)] = 'minecraft:tnt'
        self.update()
        self.assertEqual('minecraft:tnt', self.blocks[(1, 64, 0)])

    def test_watched_redcap_navigates_circle_without_velocity_injection(self):
        self.yaw = 180
        self.update()
        self.assertFalse(self.motion)
        self.assertTrue(self.paths)
        destination = self.paths[-1][0]
        self.assertAlmostEqual(5, math.hypot(destination[0]-self.target[0], destination[2]-self.target[2]))
        self.assertIn('tf_slice:redcap_special', self.events)

    def test_recent_player_hurt_disables_shyness(self):
        self.yaw = 180
        self.state['redcapShyUntilTick'] = 200
        self.update()
        self.assertFalse(self.motion)
        self.assertFalse(self.paths)

    def test_leaving_shy_range_restores_native_combat(self):
        self.yaw = 180
        self.update()
        self.target = (0.5, 64, 1.5)
        self.update()
        self.assertIn('tf_slice:redcap_normal', self.events)

    def test_view_cone_is_120_degrees(self):
        self.yaw = 122
        self.assertTrue(self.mob._target_is_looking_at('player', self.pos))
        self.yaw = 119
        self.assertFalse(self.mob._target_is_looking_at('player', self.pos))

    def test_player_hurt_memory_lasts_five_seconds_at_30hz(self):
        self.mob._redcap_player_hurt(self.state, 'minecraft:player', 1.0)
        self.assertEqual(250, self.state['redcapShyUntilTick'])
        self.mob._tick = 120
        self.mob._redcap_player_hurt(self.state, 'minecraft:zombie', 2.0)
        self.mob._redcap_player_hurt(self.state, 'minecraft:player', 0.0)
        self.assertEqual(250, self.state['redcapShyUntilTick'])

    def test_ignition_retry_delay_is_one_second_at_30hz(self):
        self.blocks[(1, 64, 0)] = 'minecraft:tnt'
        self.update()
        self.assertEqual(130, self.state['redcapLightAfterTick'])

    def test_distant_primed_tnt_blocks_planting_but_not_shyness(self):
        self.yaw = 180
        self.mob._redcap_lit_tnt = lambda eid, radius: ['distant'] if radius >= 8 else []
        self.update()
        self.assertTrue(self.paths)

    def test_unknown_terrain_does_not_allow_planting(self):
        self.mob._redcap_tnt_blocks = lambda *args: None
        self.update()
        self.assertFalse(self.writes)
        self.assertEqual(3, self.state['tntLeft'])

    def test_failed_block_removal_rolls_back_new_primed_tnt(self):
        self.write_ok = False
        self.blocks[(1, 64, 0)] = 'minecraft:tnt'
        self.update()
        self.assertFalse(self.primed)
        self.assertEqual('minecraft:tnt', self.blocks[(1, 64, 0)])

    def test_plant_then_light_then_evade_and_restore_pickaxe(self):
        self.update()
        self.mob._tick += 4
        self.update()
        self.assertTrue(self.primed)
        self.assertEqual('minecraft:air', self.blocks[(0, 64, 0)])
        self.assertEqual('tf_slice:ironwood_pickaxe', self.items[-1]['newItemName'])
        self.mob._tick += 4
        self.update()
        self.assertEqual(2, self.state['tntLeft'])
        self.assertFalse(self.commands)

    def test_own_ignition_starts_escape_before_entity_query_catches_up(self):
        self.mob._redcap_lit_tnt = lambda *args: []
        self.update()
        self.mob._tick += 4
        self.update()
        self.assertTrue(self.primed)
        self.assertEqual('evade', self.state['redcapGoal'])
        self.assertTrue(self.paths)
        self.assertEqual(2.0, self.paths[-1][1])

    def test_shy_navigation_is_not_reissued_every_update(self):
        self.yaw = 180
        self.update()
        for _ in range(4):
            self.mob._tick += 4
            self.update()
        self.assertEqual(1, len(self.paths))

    def test_valid_path_is_not_interrupted_at_one_second(self):
        self.yaw = 180
        self.update()
        for _ in range(22):
            self.mob._tick += 4
            self.update()
        self.assertEqual(1, len(self.paths))

    def test_shy_goal_never_forces_actor_rotation(self):
        self.yaw = 180
        self.update()
        self.assertEqual([], self.rotations)

    def test_failed_navigation_backs_off_before_retrying(self):
        self.yaw = 180
        self.update()
        self.paths[-1][-1]('mob', 3)
        self.mob._tick += 4
        self.update()
        self.assertEqual(1, len(self.paths))
        self.mob._tick += 20
        self.update()
        self.assertEqual(2, len(self.paths))

    def test_evade_keeps_navigation_control_beyond_two_blocks(self):
        self.yaw = 180
        self.primed.append('tnt')
        self.update()
        self.mob._redcap_lit_tnt = lambda eid, radius: ['tnt'] if radius >= 8 else []
        self.mob._tick += 4
        self.update()
        self.assertEqual(1, len(self.paths))
        self.assertEqual('evade', self.state['redcapGoal'])
        self.assertEqual('tf_slice:redcap_special', self.events[-1])
        self.mob._redcap_lit_tnt = lambda *args: []
        self.paths[-1][-1]('mob', 0)
        self.update()
        self.assertEqual('shy', self.state['redcapGoal'])

    def test_both_redcaps_actually_navigate_away_from_primed_tnt(self):
        for kind in ('tf_slice:redcap', 'tf_slice:redcap_sapper'):
            self.setUp()
            self.state['type'] = kind
            self.target_id = None
            self.primed.append('tnt')
            self.update()
            self.assertEqual(1,len(self.paths))
            destination,speed = self.paths[0][:2]
            threat = self.mob._get_foot_pos('tnt')
            self.assertGreater(sum((destination[i]-threat[i])**2 for i in range(3)),64)
            self.assertLess(destination[0],self.pos[0])
            self.assertEqual(2.0,speed)
            self.assertFalse(self.motion, 'Escape must pathfind, not teleport or shove the actor')

    def test_escape_ignores_mob_family_filter_and_finds_nonliving_tnt(self):
        self.primed.append('tnt')
        cls,namespace = runtime_class()
        # Force the family query to miss TNT, reproducing non-mob targeting.
        namespace['CF'] = types.SimpleNamespace(CreateGame=lambda _:types.SimpleNamespace(
            GetEntitiesAround=lambda *a: [], GetEntitiesInSquareArea=lambda *a:['player','tnt']))
        probe = cls()
        probe._get_foot_pos=self.mob._get_foot_pos
        probe._get_dimension=self.mob._get_dimension
        probe._get_engine_type=self.mob._get_engine_type
        self.assertEqual(['tnt'],probe._redcap_lit_tnt('mob',2))

    def test_escape_skips_solid_destination_and_retries_failed_path(self):
        self.primed.append('tnt')
        self.blocks[(-8,64,0)]='minecraft:stone'
        self.blocks[(-8,65,0)]='minecraft:stone'
        self.blocks[(-8,66,0)]='minecraft:stone'
        self.update()
        self.assertTrue(self.paths)
        first = self.paths[-1][0]
        self.assertNotEqual((-7.5,64,0.5),first)
        self.paths[-1][-1]('mob',2)
        self.mob._tick += 16
        self.update()
        self.assertGreater(len(self.paths),1)
        self.assertNotEqual(first,self.paths[-1][0])

    def test_escape_is_not_cancelled_when_tnt_disappears_before_path_finishes(self):
        self.state['type']='tf_slice:redcap'
        self.primed.append('tnt')
        self.update()
        self.assertTrue(self.paths)
        self.primed.clear()
        self.update()
        self.assertEqual('evade',self.state['redcapGoal'])
        self.paths[-1][-1]('mob',0)
        self.update()
        self.assertEqual('normal',self.state['redcapGoal'])

    def test_disappearing_target_restores_combat_group(self):
        self.yaw = 180
        self.update()
        self.target_id = None
        self.update()
        self.assertEqual('tf_slice:redcap_normal', self.events[-1])

    def test_late_navigation_callback_cannot_clear_new_goal(self):
        self.yaw = 180
        self.update()
        old_callback = self.paths[-1][-1]
        self.yaw = 0
        self.blocks[(4, 64, 0)] = 'minecraft:tnt'
        self.update()
        new_destination = self.state['redcapDestination']
        old_callback('mob', 0)
        self.assertEqual(new_destination, self.state['redcapDestination'])


class RedcapRenderTests(unittest.TestCase):
    def test_boots_fit_redcap_limbs_and_copy_owner_skeleton(self):
        path = ROOT / 'TwilightBossSliceR/models/entity/redcap_armor.geo.json'
        self.assertTrue(path.exists(), 'redcaps need their own armor layer')
        geo = json.loads(path.read_text())['minecraft:geometry'][0]
        self.assertEqual((64, 32), (geo['description']['texture_width'], geo['description']['texture_height']))
        by_name={bone['name']:bone for bone in geo['bones']}
        self.assertIn('rightLeg',by_name, 'Boot bones must participate in native owner-pose copying')
        self.assertIn('leftLeg',by_name)
        for bone, pivot, origin in zip([by_name['rightLeg'],by_name['leftLeg']], [[-2.5, 9, 0], [2.5, 9, 0]], [[-4, 0, -1.5], [1, 0, -1.5]]):
            self.assertEqual(pivot, bone['pivot'])
            self.assertNotIn('binding',bone, 'The recorded NetEase build rejects this attachment binding')
            self.assertEqual('root',bone['parent'])
            self.assertEqual(origin, bone['cubes'][0]['origin'])
            self.assertEqual([3, 9, 3], bone['cubes'][0]['size'])
            self.assertAlmostEqual(0.4875, bone['cubes'][0]['inflate'])
            self.assertEqual([4, 12], bone['cubes'][0]['uv']['north']['uv_size'])

    def test_armor_uses_identical_owner_bone_names_parents_and_pivots(self):
        from tools import build_ruin_dependencies as builder
        owner={b['name']:b for b in builder.redcap_geometry()['bones']}
        armor=json.loads((ROOT/'TwilightBossSliceR/models/entity/redcap_armor.geo.json').read_text())['minecraft:geometry'][0]['bones']
        self.assertEqual(set(owner),{b['name'] for b in armor})
        for bone in armor:
            self.assertNotIn('binding',bone)
            self.assertEqual(owner[bone['name']]['pivot'],bone['pivot'])
            self.assertEqual(owner[bone['name']].get('parent'),bone.get('parent'))
            if bone['name'] not in ('rightLeg','leftLeg'):
                self.assertFalse(bone.get('cubes'))

    def test_head_tracking_does_not_claim_movement_control(self):
        for kind in ('redcap', 'redcap_sapper'):
            e = json.loads((ROOT / ('TwilightBossSliceB/entities/' + kind + '.entity.json')).read_text())['minecraft:entity']
            look = e['components'].get('minecraft:behavior.look_at_target')
            self.assertIsNotNone(look)
            self.assertEqual(['look'], look['control_flags'])
            self.assertEqual(1.0, look['probability'])

    def test_normal_combat_can_acquire_look_and_move_before_idle_tracking(self):
        for kind in ('redcap','redcap_sapper'):
            entity=json.loads((ROOT/('TwilightBossSliceB/entities/'+kind+'.entity.json')).read_text())['minecraft:entity']
            look=entity['components']['minecraft:behavior.look_at_target']
            melee=entity['component_groups']['tf_slice:redcap_normal']['minecraft:behavior.melee_attack']
            # Melee owns both MOVE and LOOK. Merely marking the higher-priority
            # tracking goal LOOK-only still blocks melee, including its chase.
            self.assertLess(melee['priority'],look['priority'])
            self.assertEqual(['tf_slice:redcap_normal'],entity['events']['tf_slice:redcap_normal']['add']['component_groups'])

    def test_walk_uses_smoothed_speed_and_per_second_phase(self):
        for kind in ('redcap', 'redcap_sapper'):
            d = json.loads((ROOT / ('TwilightBossSliceR/entity/' + kind + '.entity.json')).read_text())['minecraft:client_entity']['description']
            pre = ' '.join(d['scripts'].get('pre_animation', []))
            self.assertIn('query.ground_speed', pre)
            self.assertIn('query.delta_time', pre)
            self.assertIn('math.pow', pre)
            self.assertIn('variable.redcap_walk_phase', pre)
        a=json.loads((ROOT/'TwilightBossSliceR/animations/ruin_mobs.animation.json').read_text())['animations']
        self.assertIn('variable.redcap_walk_amount', json.dumps(a['animation.tf_slice.redcap.move']))

    def test_walk_frame_rate_independence_and_stop(self):
        d=json.loads((ROOT/'TwilightBossSliceR/entity/redcap.entity.json').read_text())['minecraft:client_entity']['description']
        def sample(fps, stop=False):
            ns={'math': types.SimpleNamespace(clamp=lambda v,lo,hi:min(hi,max(lo,v)),pow=pow,floor=math.floor),
                'variable':types.SimpleNamespace(redcap_walk_amount=0,redcap_walk_phase=0),
                'temp':types.SimpleNamespace(), 'query':types.SimpleNamespace(ground_speed=2.8,delta_time=1.0/fps)}
            for i in range(fps * 3):
                if stop and i >= fps*2:ns['query'].ground_speed=0
                for command in d['scripts']['pre_animation']:
                    exec(command, {'__builtins__':{}}, ns)
            return ns['variable']
        a,b=sample(30),sample(120)
        self.assertAlmostEqual(0.56,a.redcap_walk_amount,places=5)
        self.assertAlmostEqual(a.redcap_walk_amount,b.redcap_walk_amount,places=5)
        self.assertLess(abs(a.redcap_walk_phase-b.redcap_walk_phase),1.0)
        self.assertLess(sample(60,True).redcap_walk_amount,0.001)

    def test_molang_temporaries_do_not_cross_expression_boundaries(self):
        d=json.loads((ROOT/'TwilightBossSliceR/entity/redcap.entity.json').read_text())['minecraft:client_entity']['description']
        for expression in d['scripts']['pre_animation']:
            declared=set()
            for statement in expression.split(';'):
                if '=' not in statement:continue
                lhs,rhs=statement.split('=',1)
                for name in re.findall(r'temp\.\w+',rhs):
                    self.assertIn(name,declared,'Molang temp variables only live within this expression')
                declared.update(re.findall(r'temp\.\w+',lhs))

    def test_held_equipment_has_its_own_scale_without_scaling_the_hand(self):
        a=json.loads((ROOT/'TwilightBossSliceR/animations/ruin_mobs.animation.json').read_text())['animations']
        self.assertIn('animation.tf_slice.redcap.equipment', a)
        bones=a['animation.tf_slice.redcap.equipment']['bones']
        self.assertNotIn('rightArm', bones)
        for name in ('rightItem','leftItem'):
            self.assertEqual(0.85, bones[name]['scale'])

    def test_boot_override_is_limited_to_redcaps_and_preserves_other_wearers(self):
        for kind in ('iron', 'ironwood'):
            path = ROOT / ('TwilightBossSliceR/attachables/' + kind + '_boots.attachable.json')
            self.assertTrue(path.exists())
            desc = json.loads(path.read_text())['minecraft:attachable']['description']
            self.assertEqual('geometry.humanoid.armor.boots', desc['geometry']['default'])
            self.assertEqual('geometry.tf_slice.redcap.armor.boots', desc['geometry'].get('redcap'))
            controllers = desc['render_controllers']
            self.assertIn('controller.render.tf_slice.redcap_boots', json.dumps(controllers))
        path = ROOT / 'TwilightBossSliceR/render_controllers/redcap_armor.render.json'
        controller = json.loads(path.read_text())['render_controllers']['controller.render.tf_slice.redcap_boots']
        self.assertEqual("query.is_owner_identifier_any('tf_slice:redcap', 'tf_slice:redcap_sapper') ? Geometry.redcap : Geometry.default", controller['geometry'])

    def test_attack_samples_match_java_fixed_humanoid_math(self):
        animations = json.loads((ROOT / 'TwilightBossSliceR/animations/ruin_mobs.animation.json').read_text())['animations']
        bones = animations['animation.tf_slice.redcap.attack']['bones']
        for progress in (0.0, 0.1, 0.25, 0.5, 0.8, 1.0):
            for head_pitch in (-30, 0, 30):
                molang = types.SimpleNamespace(
                    sin=lambda a: math.sin(math.radians(a)),
                    cos=lambda a: math.cos(math.radians(a)),
                    sqrt=math.sqrt, clamp=lambda a, lo, hi: min(hi, max(lo, a)))
                ns = {'math': molang, 'variable': types.SimpleNamespace(attack_time=progress),
                      'query': types.SimpleNamespace(target_x_rotation=head_pitch)}
                value = lambda expr: eval(expr, {'__builtins__': {}}, ns) if isinstance(expr, str) else expr
                yaw = math.sin(math.sqrt(progress)*2*math.pi)*0.2
                swing = -math.sin((1-(1-progress)**4)*math.pi)*1.2
                swing += math.sin(progress*math.pi)*(math.radians(head_pitch)-0.7)*0.75
                self.assertAlmostEqual(math.degrees(swing), value(bones['rightArm']['rotation'][0]), delta=0.0002)
                self.assertAlmostEqual(math.degrees(yaw), value(bones['body']['rotation'][1]), delta=0.0002)
                self.assertAlmostEqual(4*(1-math.cos(yaw)), value(bones['rightArm']['position'][0]), delta=0.0002)
                self.assertAlmostEqual(4*math.sin(yaw), value(bones['rightArm']['position'][2]), delta=0.0002)

    def test_source_builder_and_pack_documents_agree(self):
        from tools import build_ruin_dependencies as builder
        for kind in ('redcap', 'redcap_sapper'):
            for folder, factory in [('TwilightBossSliceB/entities', builder.server_entity),
                                    ('TwilightBossSliceR/entity', builder.client_entity)]:
                actual = json.loads((ROOT / folder / (kind + '.entity.json')).read_text())
                self.assertEqual(actual, factory(kind, builder.MOBS[kind]))
        actual = json.loads((ROOT / 'TwilightBossSliceR/animations/ruin_mobs.animation.json').read_text())['animations']
        expected = builder.animation_document()['animations']
        for key in actual:
            if key.startswith('animation.tf_slice.redcap.'):
                self.assertEqual(expected[key], actual[key])

    def test_native_chase_and_scripted_path_are_mutually_exclusive(self):
        for kind in ('redcap', 'redcap_sapper'):
            entity = json.loads((ROOT / ('TwilightBossSliceB/entities/' + kind + '.entity.json')).read_text())['minecraft:entity']
            normal = entity['component_groups']['tf_slice:redcap_normal']
            self.assertIn('minecraft:behavior.melee_attack', normal)
            self.assertNotIn('minecraft:behavior.melee_attack', entity['components'])
            self.assertIn('minecraft:behavior.float', entity['components'])
            self.assertNotIn('minecraft:behavior.avoid_mob_type', entity['components'])
            self.assertIn('minecraft:behavior.avoid_mob_type', normal)
            self.assertEqual(['tf_slice:redcap_normal'], entity['events']['tf_slice:redcap_special']['remove']['component_groups'])

    def test_both_clients_play_attack_pose(self):
        for kind in ('redcap', 'redcap_sapper'):
            d = json.loads((ROOT / ('TwilightBossSliceR/entity/' + kind + '.entity.json')).read_text())['minecraft:client_entity']['description']
            self.assertEqual('animation.tf_slice.redcap.attack', d['animations'].get('attack'))
            self.assertIn('attack', d['scripts']['animate'])

    def test_attack_moves_shoulders_and_swings_pickaxe(self):
        animations = json.loads((ROOT / 'TwilightBossSliceR/animations/ruin_mobs.animation.json').read_text())['animations']
        self.assertIn('animation.tf_slice.redcap.attack', animations)
        bones = animations['animation.tf_slice.redcap.attack']['bones']
        for name in ('body', 'rightArm', 'leftArm'):
            self.assertIn('variable.attack_time', json.dumps(bones[name]))
        self.assertIn('position', bones['rightArm'])
        self.assertIn('position', bones['leftArm'])


if __name__ == '__main__':
    unittest.main()
