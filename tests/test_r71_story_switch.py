# -*- coding: utf-8 -*-
"""Round 31 guards: a phantom switch needs a stand to switch from.

story_switch_detection compared the max-count domain of the short window
against the max-count domain of the long window. When every entry sits on
a different domain — normal for multi-domain work — max() picks
arbitrarily among singletons, the two arbitrary picks differ, and the
detector reported "narrative stands have recently changed" (25/100 and a
fusion penalty) for sessions that never held a stand at all. A stand now
requires a repeated domain (count >= 2) in both windows before a switch
between them can be reported.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def row(i, nxt):
    return {"t": 1000 + i, "next": nxt, "verified": 0, "open": 0,
            "marker": "OPEN", "confidence": "", "verifier": "",
            "risk": "low", "error": "", "outcome": "", "extra_steps": 0}


class StorySwitchTests(unittest.TestCase):

    def test_all_distinct_domains_report_instability_not_a_switch(self):
        # A mixed short window is documented instability (0/100), but it
        # must no longer be compounded by the phantom long-window switch
        # (25) the arbitrary max-pick comparison used to add.
        h = [row(i, "dom%d: step %d" % (i, i)) for i in range(6)]
        self.assertEqual(mindseam.story_switch_detection(h, book=None), 0)

    def test_real_shift_between_dominant_domains_is_a_switch(self):
        h = ([row(i, "old: step %d" % i) for i in range(3)]
             + [row(i, "new: step %d" % i) for i in range(3, 6)])
        self.assertEqual(mindseam.story_switch_detection(h, book=None), 25)

    def test_stable_dominant_domain_is_not_a_switch(self):
        h = [row(i, "dom: step %d" % i) for i in range(6)]
        self.assertEqual(mindseam.story_switch_detection(h, book=None), 100)

    def test_phantom_switch_fact_is_gone(self):
        # Before the fix this exact history also printed the stronger
        # "stands have recently changed" story (25) on top of the
        # instability reading; the fact now reports only what measured.
        h = [row(i, "dom%d: step %d" % (i, i)) for i in range(6)]
        facts = mindseam.observations(h)
        line = next((f for f in facts if "Story switch" in f), None)
        self.assertIsNotNone(line, facts)
        self.assertIn("(0/100)", line)
        h2 = ([row(i, "old: step %d" % i) for i in range(3)]
              + [row(i, "new: step %d" % i) for i in range(3, 6)])
        facts2 = mindseam.observations(h2)
        line2 = next((f for f in facts2 if "Story switch" in f), None)
        self.assertIsNotNone(line2, facts2)
        self.assertIn("(25/100)", line2)

    def test_short_window_dominant_but_long_flat_reads_stable(self):
        # Dominant short domain, no dominant long domain: nothing to
        # compare against, so no switch is claimed.
        h = ([row(i, "dom%d: step %d" % (i, i)) for i in range(3)]
             + [row(i, "dom: step %d" % i) for i in range(3, 6)])
        self.assertEqual(mindseam.story_switch_detection(h, book=None), 100)


if __name__ == "__main__":
    unittest.main()
