"""Source ChainBlock positions: H - (H - P) * .05/.25/.45/.65/.85.

Only distribution is restored here; the adapter's existing hand/head anchor
selection is not a full port of Java's hand pose or vertical offsets.
"""
import json
import tempfile
import unittest
from pathlib import Path
from tests.test_chain_detached_visual import Engine, visual


class SourceSpacingTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.client = visual.ChainVisuals(self.engine, 'level', clock=lambda:0,
            create_visual=self.engine.spawn, destroy_visual=self.engine.destroy)
        self.client.receive({'projectileId':'head','ownerId':'player'})

    def test_all_five_links_follow_source_fraction_and_equal_spacing(self):
        hand=(1,2,3)
        for head in ((5,2,3),(1,10,3),(-7,2,15),(1,2,3)):
            self.engine.bones['head']['chain_origin']=head
            self.client.render(); self.client.render()
            points=self.engine.draw()
            self.assertEqual(5,len(points))
            for point,t in zip(points,(.05,.25,.45,.65,.85)):
                for i in range(3): self.assertAlmostEqual(hand[i]+(head[i]-hand[i])*t,point[i],places=6)
            for i in range(1,5):
                for axis in range(3):
                    self.assertAlmostEqual((head[axis]-hand[axis])*.2,points[i][axis]-points[i-1][axis],places=6)

    def test_adapter_and_animation_use_the_same_source_fractions(self):
        self.assertEqual((.95,.75,.55,.35,.15),visual.LINK_FRACTIONS)

    def test_diagnostics_do_not_report_the_source_five_percent_gap_as_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.jsonl'; self.client.trace_path=str(path)
            self.client.render(); self.client.render(); self.engine.draw()
            self.client.next_trace=0
            self.client.render()
            rows=list(self.client.trace_records)
            self.client.clear()
            self.assertFalse(path.exists())
            last=[r for r in rows if 'actualTail' in r][-1]
            self.assertEqual((1,2,3),last['targetHand'])
            for a,b in zip([.95,1.9,2.85],last['targetTail']): self.assertAlmostEqual(a,b)
            self.assertAlmostEqual(0,last['errorToCurrent'],places=6)
            self.assertAlmostEqual(0,last['errorToPrevious'],places=6)


if __name__ == '__main__': unittest.main()
