# -*- coding: utf-8 -*-
"""Round 51 guards: the stall-severity component grid.

stall_score sums three components: frozen next action (+40), frozen
cumulative verification (+30), and confidence decay (+0..30). The grid
test pins each reachable band and the interactions between components —
the severity vocabulary the banner ("elevated" at 30, "high" at 60),
the fusion penalties (−8 at 30, −15 at 60) and heal's ceiling all key
off these exact numbers.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def row(i, nxt="dom: a", verified=0, conf=""):
    return {"t": 1000 + i, "next": nxt, "verified": verified, "open": 0,
            "marker": "OPEN", "confidence": conf, "verifier": "v",
            "risk": "low", "error": "", "outcome": "", "extra_steps": 0}


class StallGridTests(unittest.TestCase):

    def test_progressing_window_scores_zero(self):
        h = [row(0, nxt="a", verified=0, conf="strong"),
             row(1, nxt="b", verified=1, conf="strong"),
             row(2, nxt="c", verified=2, conf="strong")]
        self.assertEqual(mindseam.stall_score(h), 0)

    def test_frozen_next_alone_is_forty(self):
        h = [row(i, nxt="same", verified=i, conf="strong")
             for i in range(3)]
        self.assertEqual(mindseam.stall_score(h), 40)

    def test_frozen_verified_alone_is_thirty(self):
        h = [row(0, nxt="a", verified=1, conf="strong"),
             row(1, nxt="b", verified=1, conf="strong"),
             row(2, nxt="c", verified=1, conf="strong")]
        self.assertEqual(mindseam.stall_score(h), 30)

    def test_both_frozen_reach_seventy(self):
        h = [row(i, nxt="same", verified=1, conf="strong")
             for i in range(3)]
        self.assertEqual(mindseam.stall_score(h), 70)

    def test_decay_alone_adds_thirty(self):
        h = [row(0, nxt="a", verified=0, conf="strong"),
             row(1, nxt="b", verified=1, conf="strong"),
             row(2, nxt="c", verified=2, conf="shaky")]
        self.assertEqual(mindseam.stall_score(h), 30)

    def test_all_three_components_clamp_at_hundred(self):
        h = [row(i, nxt="same", verified=1,
                 conf="strong" if i == 0 else "shaky")
             for i in range(3)]
        self.assertEqual(mindseam.stall_score(h), 100)

    def test_banner_bands_key_off_the_grid(self):
        frozen = [row(i, nxt="same", verified=1, conf="strong")
                  for i in range(3)]
        result = mindseam.session_health_score(frozen)
        self.assertGreaterEqual(result.st_score, 60)
        _, reasons = result
        self.assertTrue(
            any("high stall severity" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
