"""Regression tests for the fusion-layer defects found in round 44.

All five were scoring defects inside `session_health_score` and the detectors
it consumes, and all five survived because no test ever fed a detector the
shape that `append_history` actually writes:

  5. A 21-line block of the fusion table was duplicated verbatim, so
     confidence_verification_alignment, incomplete_verification and error_focus
     were each scored twice with identical thresholds and identical messages.
  6. verifier_independence was scored at two separate places, so a
     concentrated verifier was penalised -10 instead of -5.
  7. verification_regression counted any *change* in `verified` as instability.
     But `verified` is `len(book["Verified"])` -- a cumulative count. Healthy
     progress 10,11,12 scored 0 (maximum penalty) while a frozen session
     12,12,12 scored 100. The detector rewarded verifying nothing.
  8. tension_resolution read `h.get("recovery")`, a key nothing in the project
     ever writes (invariant 2, an unplugged monitor), and its `stall_free` flag
     was set False precisely when a step *did* name a next action -- the
     opposite of its name.
  9. verifier_agreement shared defect 7's misreading: a verifier that confirmed
     new ground at every seam read as one flipping its verdict.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _step(i, **kw):
    d = {
        "t": 1000 + i * 60,
        "next": "analyze: inspect input %d" % i,
        "verified": i,
        "open": 0,
        "marker": ["STEP", "CHECK", "OPEN"][i % 3],
        "confidence": "strong",
        "verifier": "pytest tests -q exits 0",
        "risk": "low",
        "error": "",
        "outcome": "ok",
        "extra_steps": 0,
    }
    d.update(kw)
    return d


def _run(vals, key="verified", **kw):
    return [_step(i, **dict(kw, **{key: v})) for i, v in enumerate(vals, 1)]


class R44NoDoubleScoringTests(unittest.TestCase):
    """Defects 5 and 6: the same signal must not be scored twice."""

    def _degraded(self):
        return [_step(i, confidence="strong", error="boom", outcome="",
                      verifier="v1", verified=1)
                for i in range(mindseam.STALL_RUN * 2)]

    def test_no_reason_line_is_emitted_twice(self):
        score, reasons = mindseam.session_health_score(self._degraded())
        dupes = sorted(r for r in set(reasons) if reasons.count(r) > 1)
        self.assertEqual(dupes, [], "duplicated reason lines: %s" % dupes)

    def test_verifier_independence_is_scored_once(self):
        hist = self._degraded()
        self.assertLess(mindseam.verifier_independence(hist), 30)
        score, reasons = mindseam.session_health_score(hist)
        hits = [r for r in reasons if "verifier independence" in r
                or "verifier concentration" in r]
        self.assertEqual(len(hits), 1, reasons)


class R44VerificationRegressionTests(unittest.TestCase):
    """Defect 7: `verified` is a cumulative count, not a boolean flag."""

    def test_monotonic_progress_is_not_a_regression(self):
        self.assertEqual(mindseam.verification_regression(_run([10, 11, 12])), 100)

    def test_long_climb_is_not_a_regression(self):
        self.assertEqual(
            mindseam.verification_regression(_run([1, 2, 3, 4, 5, 6])), 100)

    def test_plateau_is_not_a_regression(self):
        self.assertEqual(mindseam.verification_regression(_run([12, 12, 12])), 100)

    def test_real_loss_scores_zero(self):
        self.assertEqual(mindseam.verification_regression(_run([12, 11, 10])), 0)

    def test_loss_then_hold_scores_between(self):
        score = mindseam.verification_regression(_run([12, 0, 0]))
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_churn_scores_below_a_single_loss(self):
        churn = mindseam.verification_regression(_run([12, 0, 12]))
        single = mindseam.verification_regression(_run([12, 0, 0]))
        self.assertLess(churn, single)

    def test_healthy_progress_earns_the_fusion_bonus(self):
        score, reasons = mindseam.session_health_score(_run([10, 11, 12]))
        self.assertTrue(any("stable verification" in r for r in reasons), reasons)
        self.assertFalse(
            any("verification regression" in r for r in reasons), reasons)

    def test_real_loss_earns_the_fusion_penalty(self):
        score, reasons = mindseam.session_health_score(_run([12, 11, 10]))
        self.assertTrue(
            any("verification regression" in r for r in reasons), reasons)

    def test_real_loss_reaches_observations(self):
        facts = mindseam.observations(_run([12, 11, 10]))
        self.assertTrue(
            any("verification regression" in f.lower() for f in facts), facts)

    def test_healthy_progress_stays_out_of_observations(self):
        facts = mindseam.observations(_run([10, 11, 12]))
        self.assertFalse(
            any("verification regression" in f.lower() for f in facts), facts)


class R44TensionResolutionTests(unittest.TestCase):
    """Defect 8: a dead `recovery` branch and an inverted `stall_free`."""

    def test_no_tension_needs_no_resolution(self):
        hist = _run([0, 0, 0], key="open")
        self.assertEqual(mindseam.tension_resolution(hist), 100)

    def test_naming_a_next_action_is_not_a_stall(self):
        moving = _run([3, 2, 1], key="open")
        stalled = [_step(i, open=o, next="analyze: inspect input 1", verified=7)
                   for i, o in enumerate([3, 2, 1], 1)]
        self.assertGreater(mindseam.tension_resolution(moving),
                           mindseam.tension_resolution(stalled))
        self.assertGreaterEqual(mindseam.tension_resolution(moving), 50)

    def test_recovery_comes_from_the_risk_trace_not_a_phantom_key(self):
        self.assertEqual(
            [n for n in dir(mindseam) if n == "recovery"], [],
            "tension_resolution must read risk via detect_recovery")
        hist = [_step(1, open=2, risk="high"), _step(2, open=2, risk="medium"),
                _step(3, open=2, risk="low")]
        with_recovery = mindseam.tension_resolution(hist)
        flat = [_step(1, open=2, risk="high"), _step(2, open=2, risk="high"),
                _step(3, open=2, risk="high")]
        self.assertGreater(with_recovery, mindseam.tension_resolution(flat))

    def test_growing_tension_scores_low(self):
        hist = _run([1, 2, 3], key="open")
        self.assertLess(mindseam.tension_resolution(hist), 50)

    def test_healthy_session_takes_no_tension_penalty(self):
        score, reasons = mindseam.session_health_score(_run([0, 0, 0], key="open"))
        self.assertFalse(
            any("low tension resolution" in r for r in reasons), reasons)


class R44VerifierAgreementTests(unittest.TestCase):
    """Defect 9: confirming new ground is not a flipped verdict."""

    def test_climbing_verifier_agrees_with_itself(self):
        hist = _run([1, 2, 3, 4, 5, 6], verifier="v1")
        self.assertEqual(mindseam.verifier_agreement(hist), 100)

    def test_frozen_verifier_still_agrees(self):
        hist = _run([3, 3, 3, 3, 3, 3], verifier="v1")
        self.assertEqual(mindseam.verifier_agreement(hist), 100)

    def test_flipping_verifier_scores_low(self):
        hist = _run([1, 2, 1, 2, 1, 2], verifier="v1")
        self.assertLessEqual(mindseam.verifier_agreement(hist), 30)

    def test_healthy_session_takes_no_disagreement_penalty(self):
        score, reasons = mindseam.session_health_score(
            _run([1, 2, 3, 4, 5, 6], verifier="v1"))
        self.assertFalse(
            any("verifier disagreement" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
