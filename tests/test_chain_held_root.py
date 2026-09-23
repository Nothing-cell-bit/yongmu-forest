"""Restore the empirically visible root mesh; preserve the composed v6 pose.

This checks the compatibility boundary and affine composition, NOT live rendering.
"""
import json
import sys
import unittest
from tests.test_chain_source_alignment import RP, product, translate, rotate, scale


class HeldRootTests(unittest.TestCase):
    def test_generator_keeps_both_restored_resource_files(self):
        sys.path.insert(0,str(RP.parent/'tools'))
        import build_knight_stronghold_content as builder
        for path,value in (
            ('models/entity/block_and_chain_held.geo.json',builder._block_and_chain_held_geometry()),
            ('animations/block_and_chain_held.animation.json',builder._block_and_chain_held_animation())):
            self.assertEqual(value,json.loads((RP/path).read_text()))

    def test_both_states_put_mesh_directly_on_the_native_held_root(self):
        geos=json.loads((RP/'models/entity/block_and_chain_held.geo.json').read_text())['minecraft:geometry']
        self.assertEqual(2,len(geos))
        for geo,texture in zip(geos,('default','thrown')):
            self.assertEqual(1,len(geo['bones']))
            root=geo['bones'][0]
            self.assertEqual('rightitem',root['name'])
            self.assertNotIn('parent',root)
            self.assertEqual(texture,root['texture_meshes'][0]['texture'])
            self.assertEqual([6,0,6],root['texture_meshes'][0]['local_pivot'])
            self.assertEqual([2,1,-2],root['texture_meshes'][0]['position'])
            self.assertEqual([0,-135,90],root['texture_meshes'][0]['rotation'])

    def test_flat_root_preserves_previous_first_and_composed_third_person(self):
        bones=json.loads((RP/'animations/block_and_chain_held.animation.json').read_text())['animations']['animation.tf_slice.block_and_chain.grip']['bones']
        self.assertEqual({'rightitem'},set(bones))
        def matrix(node,first):
            def v(key,default):
                return [float(s.split('?')[1].split(':')[0] if first else s.split(':')[1]) for s in node.get(key,default)]
            r=v('rotation',[]); r[0]=-r[0]
            return product(translate(v('position',[])),rotate(r),scale(v('scale',['c.is_first_person ? 1 : 1']*3)[0]))
        for first in (True,False):
            old_parent=product(translate([-5.5,-3,-3] if first else [.5,-2.5,1]),
                               rotate([-38,-120,-63] if first else [0,0,0]))
            old_child=translate([0,0,0]) if first else product(
                translate([-3.084032362,3.57263356,-5.651442985]),
                rotate([-16.384463419,-5.969980099,3.774393805]),scale(.9444444444444444))
            expected=product(old_parent,old_child)
            actual=matrix(bones['rightitem'],first)
            for i in range(4):
                for j in range(4): self.assertAlmostEqual(expected[i][j],actual[i][j],places=7)

    def test_thrown_selection_still_controls_both_geometry_and_texture(self):
        controller=json.loads((RP/'render_controllers/block_and_chain.render_controllers.json').read_text())['render_controllers']['controller.render.tf_slice.block_and_chain']
        self.assertEqual('query.mod.tf_chain_active ? Geometry.thrown : Geometry.default',controller['geometry'])
        self.assertEqual('query.mod.tf_chain_active ? Texture.thrown : Texture.default',controller['textures'][0])


if __name__ == '__main__': unittest.main()
