# -*- coding: utf-8 -*-
"""Round 19 guards: heal wording accuracy and fact-staleness semantics.

  1. The confidence-presence HEAL line claimed "No confidence tags
     recorded" at any score below its floor, including windows where most
     steps were tagged — the same partial-versus-total wording defect the
     observations fact had. The line now says tags are missing on some
     steps.

  2. fact_age_seconds measured the history's total span (oldest seam to
     newest seam), so "Facts are aging ... decay 100%" printed for an
     active session whose last seam was seconds ago, merely because the
     session was long. Staleness is now measured from the freshest entry:
     an old history with a current seam is fresh; a short history whose
     last seam is stale decays.
"""

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def step(i, conf="strong", t=None):
    return {"t": t if t is not None else 1000 + i,
            "next": "dom: act %d" % i, "verified": 0, "open": 0,
            "marker": "OPEN", "confidence": conf, "verifier": "v",
            "risk": "low", "error": "", "outcome": "", "extra_steps": 0}


class HealWordingTests(unittest.TestCase):

    def test_partial_tags_do_not_claim_total_absence(self):
        h = [step(0, conf=""), step(1, conf=""), step(2, conf="strong")]
        actions = mindseam.heal_actions(h)
        line = next((a for a in actions if "confidence tags" in a.lower()),
                    None)
        self.assertIsNotNone(line, actions)
        self.assertIn("missing on some steps", line)
        self.assertNotIn("No confidence tags", line)

    def test_absence_still_earns_the_heal_line(self):
        h = [step(i, conf="") for i in range(3)]
        actions = mindseam.heal_actions(h)
        self.assertTrue(any("confidence tags" in a.lower() for a in actions),
                        actions)


class FactStalenessTests(unittest.TestCase):

    def test_fresh_seam_keeps_long_history_fresh(self):
        now = int(time.time())
        h = [step(i, t=now - 7200 + i * 3600) for i in range(3)]
        # Oldest entry is two hours back, but the newest is current.
        self.assertLess(mindseam.fact_age_seconds(h), 60)
        facts = mindseam.observations(h)
        self.assertFalse(any("aging" in f for f in facts), facts)

    def test_stale_seam_decays_even_in_short_history(self):
        now = int(time.time())
        h = [step(i, t=now - 14400 + i * 3600) for i in range(3)]
        self.assertGreater(mindseam.fact_age_seconds(h), 3600)
        facts = mindseam.observations(h)
        self.assertTrue(any("aging" in f for f in facts), facts)

    def test_just_recorded_history_has_zero_age(self):
        now = int(time.time())
        h = [step(i, t=now) for i in range(3)]
        self.assertEqual(mindseam.fact_age_seconds(h), 0)

    def test_empty_history_has_zero_age(self):
        self.assertEqual(mindseam.fact_age_seconds([]), 0)


if __name__ == "__main__":
    unittest.main()
