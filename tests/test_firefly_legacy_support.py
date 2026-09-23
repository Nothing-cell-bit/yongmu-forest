"""Read shipped structures and replay their old firefly states through runtime."""
import ast
import io
import json
import struct
import unittest

import test_plant_support as base


def shipped_fireflies(folder):
    # Extract only the existing read-only NBT reader; no generator imports/runs.
    tree = ast.parse((base.ROOT / 'tools/build_ruin_structures.py').read_text(encoding='utf-8'))
    nodes = [node for node in tree.body if (
        isinstance(node, ast.FunctionDef) and node.name in (
            '_read_exact', '_read_number', '_read_string', '_read_payload')
    ) or (
        isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id.startswith('TAG_') for target in node.targets)
    )]
    namespace = {'struct': struct}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'nbt_reader', 'exec'), namespace)
    offsets = {'north': (0, 0, 1), 'south': (0, 0, -1), 'west': (1, 0, 0), 'east': (-1, 0, 0)}
    for path in (base.ROOT / 'TwilightBossSliceB/structures/tf_slice' / folder).rglob('*.mcstructure'):
        raw = path.read_bytes()
        if b'tf_slice:firefly' not in raw:
            continue
        stream = io.BytesIO(raw)
        stream.read(1)
        namespace['_read_string'](stream, '<')
        document = namespace['_read_payload'](stream, 10, '<')
        size = document['size']
        data = document['structure']
        palette = data['palette']['default']['block_palette']
        indices = data['block_indices'][0]
        def block_at(pos):
            if any(value < 0 or value >= size[i] for i, value in enumerate(pos)):
                return None
            index = indices[pos[0] * size[1] * size[2] + pos[1] * size[2] + pos[2]]
            return palette[index]['name'] if index >= 0 else 'minecraft:air'
        for index, palette_index in enumerate(indices):
            if palette_index < 0 or palette[palette_index]['name'] != 'tf_slice:firefly':
                continue
            pos = (index // (size[1] * size[2]), index // size[2] % size[1], index % size[2])
            facing = palette[palette_index]['states']['tf_slice:facing']
            offset = offsets[facing]
            front = tuple(pos[i] + offset[i] for i in range(3))
            back = tuple(pos[i] - offset[i] for i in range(3))
            yield path, pos, facing, front, block_at(front), back, block_at(back)


class FireflyLegacyTests(unittest.TestCase):
    def setUp(self):
        self.h = base.PlantRuntimeTests()
        self.h.setUp()

    def test_shipped_canopy_and_hedge_fireflies_survive_first_random_tick(self):
        tested = {'swamp/trees/canopy': 0, 'ruins/hedge_maze': 0}
        for folder in tested:
            for path, pos, facing, front, front_name, back, back_name in shipped_fireflies(folder):
                if front_name is None or back_name is None:
                    continue  # Another piece owns this support; not evidence of air.
                with self.subTest(template=str(path), position=pos):
                    h = self.h
                    h.world = {pos: {'name': 'tf_slice:firefly'}, front: {'name': front_name}, back: {'name': back_name}}
                    h.states = {'tf_slice:facing': facing}
                    h.writes.clear()
                    h.drops.clear()
                    h.system.OnBlockRandomTickServerEvent(dict(fullName='tf_slice:firefly', position=pos, dimensionId=7))
                    self.assertFalse(h.writes)
                    self.assertFalse(h.drops)
                    self.assertEqual({'tf_slice:facing': facing}, h.states)
                    self.assertEqual('tf_slice:firefly', h.world[pos]['name'])
                    tested[folder] += 1
        self.assertEqual(8, tested['swamp/trees/canopy'])
        self.assertGreaterEqual(tested['ruins/hedge_maze'], 160)

    def test_legacy_orientation_and_wall_removal_are_left_alone(self):
        h = self.h
        h.world = {h.pos: {'name': 'tf_slice:firefly'}, (10, 65, 19): {'name': 'minecraft:log'}}
        h.system.OnBlockNeighborChanged(h.event('firefly'))
        self.assertFalse(h.drops)
        self.assertEqual('north', h.states['tf_slice:facing'])
        h.world[(10, 65, 19)] = {'name': 'minecraft:air'}
        h.world[(10, 65, 21)] = {'name': 'minecraft:stone'}
        h.system.OnBlockNeighborChanged(h.event('firefly'))
        self.assertFalse(h.drops)

    def test_airborne_firefly_never_drops_on_events_or_direct_cleanup(self):
        h = self.h
        for verified in (0, 1):
            h.world = {h.pos: {'name': 'tf_slice:firefly'}}
            h.states = {'tf_slice:facing': 'north', 'tf_slice:attachment_verified': verified}
            h.system.OnBlockRandomTickServerEvent(h.event('firefly'))
            h.system.OnBlockNeighborChanged(h.event('firefly'))
            h.system._check_plant_support('tf_slice:firefly', h.pos, 7)
            self.assertFalse(h.writes)
            self.assertFalse(h.drops)

    def test_firefly_has_no_support_tick_subscription_or_support_drop(self):
        h = self.h
        block = json.loads((base.ROOT / 'TwilightBossSliceB/netease_blocks/firefly.json').read_text(encoding='utf-8'))
        components = block['minecraft:block']['components']
        self.assertNotIn('netease:neighborchanged_sendto_script', components)
        self.assertNotIn('netease:random_tick', components)
        self.assertNotIn('tf_slice:firefly', h.logic.SUPPORTED_BLOCKS)
        self.assertIsNone(h.logic.support_drop('tf_slice:firefly'))

    def test_unknown_opposite_chunk_defers_cleanup(self):
        h = self.h
        h.world = {h.pos: {'name': 'tf_slice:firefly'}, (10, 65, 19): None}
        h.system.OnBlockNeighborChanged(h.event('firefly'))
        self.assertFalse(h.drops)
        self.assertFalse(h.writes)

    def test_failed_orientation_write_does_not_destroy_the_bug(self):
        h = self.h
        h.world = {h.pos: {'name': 'tf_slice:firefly'}, (10, 65, 19): {'name': 'minecraft:log'}}
        h.system._block_state_comp.SetBlockStates = lambda *args: False
        h.system.OnBlockNeighborChanged(h.event('firefly'))
        self.assertFalse(h.drops)
        self.assertFalse(h.writes)

    def test_player_placement_marks_the_attachment_verified(self):
        h = self.h
        h.world[h.pos] = {'name': 'tf_slice:firefly'}
        args = h.event('firefly')
        args['face'] = 3
        h.system.OnEntityPlaceBlockAfterServerEvent(args)
        self.assertEqual(1, h.states.get('tf_slice:attachment_verified'))

    def test_firefly_pack_has_persistent_migration_state(self):
        block = json.loads((base.ROOT / 'TwilightBossSliceB/netease_blocks/firefly.json').read_text(encoding='utf-8'))
        self.assertEqual([0, 1], block['minecraft:block']['description']['states'].get('tf_slice:attachment_verified'))


if __name__ == '__main__':
    unittest.main()
