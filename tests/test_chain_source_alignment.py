"""Java-owned endpoints and source-relative held display, independent oracles."""
import json
import math
import unittest
import zipfile
from pathlib import Path
from tests.test_chain_detached_visual import ROOT, RP, Engine, visual


def multiply(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def product(*matrices):
    result=matrices[0]
    for matrix in matrices[1:]: result=multiply(result,matrix)
    return result


def translate(v):
    return [[1,0,0,v[0]],[0,1,0,v[1]],[0,0,1,v[2]],[0,0,0,1]]


def rotate(v):
    x,y,z=map(math.radians,v)
    cx,sx,cy,sy,cz,sz=math.cos(x),math.sin(x),math.cos(y),math.sin(y),math.cos(z),math.sin(z)
    return product([[1,0,0,0],[0,cx,-sx,0],[0,sx,cx,0],[0,0,0,1]],
                   [[cy,0,sy,0],[0,1,0,0],[-sy,0,cy,0],[0,0,0,1]],
                   [[cz,-sz,0,0],[sz,cz,0,0],[0,0,1,0],[0,0,0,1]])


def scale(s):
    return [[s,0,0,0],[0,s,0,0],[0,0,s,0],[0,0,0,1]]


def inverse(m):
    # Inputs are rigid transforms with uniform scale. Independent analytic inverse.
    s2=sum(m[i][0]**2 for i in range(3))
    result=[[m[j][i]/s2 for j in range(3)]+[0] for i in range(3)]+[[0,0,0,1]]
    for i in range(3): result[i][3]=-sum(result[i][j]*m[j][3] for j in range(3))
    return result


class AlignmentTests(unittest.TestCase):
    def test_source_hand_main_offhand_pitch_and_heading(self):
        for f in ((0,0,1),(1,0,0),(0,1,0),(0,-1,0),(.6,.8,0)):
            for main in (True,False):
                angle=-.4 if main else .4
                expected=(10+f[0]*math.cos(angle)+f[2]*math.sin(angle),
                          63+f[1]-.4, -8+f[2]*math.cos(angle)-f[0]*math.sin(angle))
                actual=visual.first_person_grip((10,63,-8),f,70,main)
                for a,b in zip(actual,expected): self.assertAlmostEqual(a,b)
                self.assertEqual(actual,visual.first_person_grip((10,63,-8),f,110,main))

    def test_all_perspectives_use_owner_eye_and_rotation_not_view_camera(self):
        engine=Engine()
        class Pos:
            def GetPos(self): return (10,63,-8)
        class Rot:
            def GetRot(self): return (0,0)
        engine.CreatePos=lambda entity: Pos()
        engine.CreateRot=lambda entity: Rot()
        client=visual.ChainVisuals(engine,'level',local_player=lambda:'player')
        state={'owner':'player','main':True}
        expected=(10-math.sin(.4),62.6,-8+math.cos(.4))
        for perspective in (0,1,2):
            engine.perspective=perspective
            actual=client._hand(state,engine.CreateModel('player'))
            for a,b in zip(actual,expected): self.assertAlmostEqual(a,b)
        client.local_player=lambda:'observer'
        self.assertEqual(actual,client._hand(state,engine.CreateModel('player')))

    def test_head_mesh_center_and_named_endpoint_match_source_height(self):
        geo=json.loads((RP/'models/entity/block_chain_projectile.geo.json').read_text())['minecraft:geometry'][0]
        bones={b['name']:b for b in geo['bones']}
        cube=bones['block']['cubes'][0]
        center=[cube['origin'][i]+cube['size'][i]/2 for i in range(3)]
        self.assertEqual([0,4,0],center)
        self.assertEqual(center,bones['chain_head']['pivot'])
        self.assertEqual([0,9,0],bones['spikes_0']['pivot'])
        self.assertEqual([0,0,0],bones['chain_origin']['pivot'])

    def test_player_pose_eye_height_correction_and_missing_eye(self):
        engine=Engine()
        engine.eyes['player']=(0,1.62,0)
        client=visual.ChainVisuals(engine,'level')
        state={'owner':'player','main':True}
        for flag,expected_height in ((None,1.62),('is_sneaking',1.27),
                                     ('is_swimming',.4),('is_gliding',.4)):
            engine.molang.clear()
            if flag: engine.molang[('player','query.'+flag)]=1
            client._hand(state,engine.CreateModel('player'))
            self.assertAlmostEqual(expected_height,state['eye'][1])
        engine.molang.clear(); engine.molang[('player','query.is_sleeping')]=1
        engine.eyes['player']=(0,.2,0)
        client._hand(state,engine.CreateModel('player'))
        self.assertEqual(.2,state['eye'][1])
        engine.eyes['player']=None
        self.assertIsNone(client._hand(state,engine.CreateModel('player')))

    def test_both_item_states_keep_mesh_on_native_root(self):
        geos=json.loads((RP/'models/entity/block_and_chain_held.geo.json').read_text())['minecraft:geometry']
        self.assertEqual(2,len(geos))
        for geo in geos:
            self.assertEqual(1,len(geo['bones']))
            root=geo['bones'][0]
            self.assertEqual('rightitem',root['name'])
            self.assertIn('texture_meshes',root)
            self.assertNotIn('parent',root)

    def test_missing_head_center_probe_uses_same_explicit_quarter_block_offset(self):
        class Model:
            def GetBonePositionFromMinecraftObject(self,bone):
                return (10,60,20) if bone in ('block','chain_origin') else None
        self.assertEqual((10,60.25,20),visual.head_center(Model()))

    def test_java_first_person_bow_and_handheld_are_identical(self):
        with zipfile.ZipFile(ROOT/'tmp/minecraft_java_1_20_1/client-1.20.1.jar') as z:
            bow=json.loads(z.read('assets/minecraft/models/item/bow.json'))['display']
            held=json.loads(z.read('assets/minecraft/models/item/handheld.json'))['display']
        for hand in ('righthand','lefthand'):
            self.assertEqual(bow['firstperson_'+hand],held['firstperson_'+hand])

    def test_third_person_correction_matches_source_relative_affine_matrix(self):
        with zipfile.ZipFile(ROOT/'tmp/minecraft_java_1_20_1/client-1.20.1.jar') as z:
            bow=json.loads(z.read('assets/minecraft/models/item/bow.json'))['display']['thirdperson_righthand']
            held=json.loads(z.read('assets/minecraft/models/item/handheld.json'))['display']['thirdperson_righthand']
        def display(d): return product(translate(d['translation']),rotate(d['rotation']),scale(d['scale'][0]))
        native=product(translate([2,1,-2]),rotate([0,-135,90]),translate([-6,0,-6]))
        image_axes=product(rotate([-90,0,0]),translate([-8,-.5,-8]))
        correction=product(native,inverse(image_axes),inverse(display(bow)),display(held),image_axes,inverse(native))
        expected=product(translate([.5,-2.5,1]),correction)
        bones=json.loads((RP/'animations/block_and_chain_held.animation.json').read_text())['animations']['animation.tf_slice.block_and_chain.grip']['bones']
        self.assertEqual({'rightitem'},set(bones))
        node=bones['rightitem']
        def values(prop,first):
            return [float(expr.split('?')[1].split(':')[0] if first else expr.split(':')[1]) for expr in node[prop]]
        r=values('rotation',False); r[0]=-r[0]
        actual=product(translate(values('position',False)),rotate(r),scale(values('scale',False)[0]))
        for row in range(4):
            for column in range(4): self.assertAlmostEqual(expected[row][column],actual[row][column],places=5)
        self.assertEqual([-5.5,-3,-3],values('position',True))
        self.assertEqual([38,-120,-63],values('rotation',True))
        self.assertEqual([1,1,1],values('scale',True))
        # Source-relative correction is local calibration, NOT a real client capture.


if __name__ == '__main__': unittest.main()
