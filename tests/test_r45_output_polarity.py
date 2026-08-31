"""Regression tests for the output-layer defects found in round 45.

All three were defects of the *reported* text rather than of the numbers, and
all three survived because every existing test asserted that a HEAL line or a
fact string could appear, never that it appeared on the right session:

  10. `heal_actions` gated all 32 detectors with one comparison, `val < 45`.
      Thirty-one of them are HEALTH scores (higher is better) but `stall_score`
      is a SEVERITY score (higher is worse), so the stall advice was printed for
      sessions with stall_score 0 and withheld from sessions at 70 -- exactly
      backwards.
  11. `ledger_stasis_detector` measures whether recent `next` values match the
      ledger `Next`: 0 means the plan and the work have diverged, 100 means they
      agree. The fusion layer labels it correctly ("ledger plan divergence"),
      but the HEAL text read "Ledger is stagnant -- close completed threads",
      which is the opposite diagnosis: it fired on the session whose plan was
      moving and stayed silent on the frozen one.
  12. `observations` called `verifier_independence` twice, at two thresholds
      (< 30 and < 100), and both branches ended in the same clause "checks
      concentrated in one name". Any session below 30 got the same score and the
      same conclusion printed on two consecutive fact lines.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


LEDGER_NEXT = "analyze: inspect the tokenizer boundary cases"

BOOK = {
    "Goal": ["ship the parser"],
    "Core": [],
    "Verified": [],
    "Open": [],
    "Next": [LEDGER_NEXT],
}


def _step(i, **kw):
    d = {
        "t": 1000 + i * 60,
        "next": "analyze: inspect module %d for boundary handling" % i,
        "verified": i,
        "open": 0,
        "marker": ["OPEN", "STEP", "DONE", "PHEW"][i % 4],
        "confidence": "strong",
        "verifier": "pytest tests/test_%d.py -q exits 0" % i,
        "risk": "low",
        "error": "",
        "outcome": "ok",
        "extra_steps": 0,
    }
    d.update(kw)
    return d


def _advancing():
    """A healthy session: the next action moves every seam, verified climbs."""
    return [_step(i) for i in range(1, 9)]


def _frozen():
    """A stalled session: one next action forever, verified never moves."""
    return [_step(i, next=LEDGER_NEXT, verified=3, marker="OPEN")
            for i in range(1, 9)]


STALL_TEXT = "HEAL: Session is stalled"


class R45StallSeverityPolarityTests(unittest.TestCase):
    """Defect 10: the heal gate must read severity scales upside down."""

    def test_stall_score_is_a_severity_scale(self):
        self.assertEqual(mindseam.stall_score(_advancing()), 0)
        self.assertGreaterEqual(mindseam.stall_score(_frozen()), 70)

    def test_stalled_session_is_told_it_is_stalled(self):
        actions = mindseam.heal_actions(_frozen(), book=BOOK)
        self.assertTrue(any(a.startswith(STALL_TEXT) for a in actions),
                        "stall_score is %d yet no stall advice was emitted: %s"
                        % (mindseam.stall_score(_frozen()), actions))

    def test_advancing_session_is_not_told_it_is_stalled(self):
        actions = mindseam.heal_actions(_advancing(), book=BOOK)
        self.assertFalse(any(a.startswith(STALL_TEXT) for a in actions),
                         "stall_score is %d yet stall advice was emitted: %s"
                         % (mindseam.stall_score(_advancing()), actions))

    def test_severity_registry_names_a_real_detector(self):
        self.assertIn("stall_score", mindseam.HEAL_SEVERITY_DETECTORS)
        for name in mindseam.HEAL_SEVERITY_DETECTORS:
            self.assertTrue(callable(getattr(mindseam, name, None)),
                            "%s is registered as a severity detector but is "
                            "not a function in this module" % name)

    def test_severity_ceiling_mirrors_the_health_floor(self):
        self.assertEqual(mindseam.HEAL_SEVERITY_CEILING,
                         100 - mindseam.HEAL_HEALTH_FLOOR)


class R45LedgerStasisTextTests(unittest.TestCase):
    """Defect 11: the heal text must describe what the detector measures."""

    def _ledger_action(self, hist):
        for a in mindseam.heal_actions(hist, book=BOOK):
            low = a.lower()
            if "ledger plan" in low or "ledger is stagnant" in low:
                return a
        return None

    def test_detector_polarity_is_unchanged(self):
        self.assertEqual(mindseam.ledger_stasis_detector(_advancing(), BOOK), 0)
        self.assertEqual(mindseam.ledger_stasis_detector(_frozen(), BOOK), 100)

    def test_diverging_session_is_told_about_divergence(self):
        action = self._ledger_action(_advancing())
        self.assertIsNotNone(action, "ledger_stasis is 0 yet no advice fired")
        self.assertIn("diverge", action.lower())
        self.assertNotIn("stagnant", action.lower())

    def test_aligned_session_gets_no_ledger_advice(self):
        self.assertIsNone(self._ledger_action(_frozen()))

    def test_heal_text_agrees_with_the_fusion_label(self):
        """Both output paths must name the same condition for the same score."""
        _, reasons = mindseam.session_health_score(_advancing(), book=BOOK)
        self.assertTrue(any("ledger plan divergence" in r for r in reasons))
        action = self._ledger_action(_advancing())
        self.assertIn("ledger plan", action.lower())


class R45ObservationsSingleEmissionTests(unittest.TestCase):
    """Defect 12: one detector, one conclusion, one fact line."""

    def _concentrated(self):
        return [_step(i, verifier="v1") for i in range(1, 9)]

    def test_verifier_concentration_is_reported_once(self):
        hist = self._concentrated()
        self.assertLess(mindseam.verifier_independence(hist), 30)
        facts = mindseam.observations(hist, book=None)
        hits = [f for f in facts if "concentrated in one name" in f.lower()]
        self.assertEqual(len(hits), 1,
                         "the same conclusion was emitted %d times: %s"
                         % (len(hits), hits))

    def test_surviving_line_keeps_the_established_wording(self):
        facts = mindseam.observations(self._concentrated(), book=None)
        self.assertTrue(any("verifier concentration" in f.lower()
                            for f in facts))

    def test_no_fact_line_is_emitted_twice(self):
        facts = mindseam.observations(self._concentrated(), book=BOOK)
        dupes = sorted(f for f in set(facts) if facts.count(f) > 1)
        self.assertEqual(dupes, [], "duplicated fact lines: %s" % dupes)


if __name__ == "__main__":
    unittest.main()
