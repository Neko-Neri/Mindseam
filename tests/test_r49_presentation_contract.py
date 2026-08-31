# -*- coding: utf-8 -*-
"""Round 9 guards: presentation contract between observations and heal.

Line-by-line comparison of the two presentation surfaces found four
defects, all without any user-visible counterpart being correct:
- three observations fact lines described a HEALTH-scale score with a
  SEVERITY adjective ("Step retry rate is high (16/100)", "Output stub
  ratio high", "Error description too short"), asserting the opposite
  of the number printed next to them;
- the marker_transition_diversity HEAL line taught a ladder through
  STEP, a state no detector vocabulary knows (marker_progression's
  terminal set is {DONE, PHEW, CLOSED, SETTLED, RESOLVED});
- feedback_amplification read h.get("severity", 0), a field nothing
  writes, so the detector returned 100 forever — an unplugged monitor;
- temporal_regularity / feedback_amplification overwrite their run
  parameter without disclosing it (defect-15 precedent).

These tests pin the corrected contract so future edits cannot silently
re-introduce inverted adjectives, ghost states, or silent monitors.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def seam(i, nxt=None, risk="low", marker="OPEN", error="", conf="thin"):
    return {"t": 1000000 + i * 600,
            "next": nxt if nxt is not None else "task%d:act" % i,
            "verified": i + 1, "open": 1, "marker": marker,
            "confidence": conf, "verifier": "v%d" % i, "risk": risk,
            "error": error, "outcome": "ok", "extra_steps": 0}


KNOWN_MARKER_STATES = {"OPEN", "DONE", "PHEW", "CLOSED", "SETTLED", "RESOLVED"}


def fact_number(fact):
    match = re.search(r"(\d+)/100", fact)
    return int(match.group(1)) if match else None


class R49PolarityTests(unittest.TestCase):
    """A health-scale score must never wear a severity adjective."""

    def test_retry_fact_line_is_polarity_consistent(self):
        h = [seam(i, nxt="retry:same") for i in range(mindseam.STALL_RUN * 2)]
        facts = mindseam.observations(h, book=None)
        fact = next(f for f in facts if "Step retry" in f)
        self.assertIn("score is low", fact)
        self.assertLess(fact_number(fact), 30)
        self.assertFalse(any("retry rate is high" in f.lower() for f in facts))

    def test_stub_fact_line_is_polarity_consistent(self):
        h = [seam(i, nxt="todo") for i in range(mindseam.STALL_RUN)]
        facts = mindseam.observations(h, book=None)
        fact = next(f for f in facts if "Output stub" in f)
        self.assertIn("score is low", fact)
        self.assertEqual(fact_number(fact), 0)
        self.assertFalse(any("stub ratio high" in f.lower() for f in facts))

    def test_silence_fact_line_is_polarity_consistent(self):
        h = [seam(i, error="e:%d" % i) for i in range(5)]
        facts = mindseam.observations(h, book=None)
        fact = next(f for f in facts if "Error description" in f)
        self.assertIn("score is low", fact)
        self.assertEqual(fact_number(fact), 0)
        self.assertFalse(any("description too short" in f.lower() for f in facts))


class R49MarkerLadderTests(unittest.TestCase):
    """Every ladder printed to users may only name states detectors know."""

    def _ladder_states(self, text):
        match = re.search(r"([A-Z]+(?:\u2192[A-Z]+)+)", text)
        self.assertIsNotNone(match, text)
        return match.group(1).split("\u2192")

    def test_transition_diversity_heal_names_only_known_states(self):
        h = [seam(i, marker="OPEN") for i in range(mindseam.STALL_RUN)]
        actions = mindseam.heal_actions(h, book=None)
        action = next(a for a in actions if "No marker transitions" in a)
        for state in self._ladder_states(action):
            self.assertIn(state, KNOWN_MARKER_STATES)

    def test_progression_heal_ladder_matches_detector_vocabulary(self):
        h = [seam(i, marker="DONE") for i in range(mindseam.STALL_RUN)]
        actions = mindseam.heal_actions(h, book=None)
        action = next(a for a in actions if "Markers are stalled" in a)
        states = self._ladder_states(action)
        self.assertEqual(states[0], "OPEN")
        for state in states:
            self.assertIn(state, KNOWN_MARKER_STATES)


class R49FeedbackAmplificationTests(unittest.TestCase):
    """The monitor must actually read session severity, not a ghost field."""

    def test_flat_low_risk_is_healthy(self):
        h = [seam(i, risk="low") for i in range(3)]
        self.assertEqual(mindseam.feedback_amplification(h), 100)

    def test_strictly_escalating_risk_scores_zero_and_is_reported(self):
        h = [seam(i, risk=r) for i, r in enumerate(("low", "medium", "high"))]
        self.assertEqual(mindseam.feedback_amplification(h), 0)
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("Feedback amplification detected" in f for f in facts))

    def test_relapse_after_improvement_scores_mixed(self):
        h = [seam(i, risk=r) for i, r in enumerate(("low", "medium", "low"))]
        self.assertEqual(mindseam.feedback_amplification(h), 50)


class R49RunDisclosureTests(unittest.TestCase):
    """Overwriting an accepted run parameter must be disclosed (defect-15 precedent)."""

    def test_run_ignored_is_disclosed_in_docstrings(self):
        for func in (mindseam.temporal_regularity, mindseam.feedback_amplification,
                     mindseam.ledger_volatility):
            self.assertIn("currently ignored", func.__doc__)


if __name__ == "__main__":
    unittest.main()
