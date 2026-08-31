# -*- coding: utf-8 -*-
"""Round 12 guards: sentinel-100 residue in the fusion bonus face.

Round 11 (test_r51) gated the two ledger-dependent detectors. This
round extends the measurement-presence audit to the rest of the bonus
face: twelve factor blocks consumed a sentinel 100 that several
detectors return when the quantity they measure was never observed
(zero errors, zero verifications, no escalations, no DONE steps, no
effort or delivery). A clean minimal session collected up to 25
phantom praise lines — unmeasured absence read as perfection.

Fix convention (same as the goal_set / ledger-plan gates): each factor
is gated on whether the quantity was actually observed, mirroring the
exact window and counting rule of its detector. Silence contract: no
bonus and no penalty from an unmeasured factor. Liveness contract: a
real measurement still earns its bonus.

Detectors counting the ABSENCE of bad events (verification_regression,
step_retry_rate, verification_freshness) are design-accepted: zero bad
events is itself evidence, their 100 is a real measurement.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def seam(i, nxt=None, verifier=None, verified=0, error="", marker="OPEN"):
    if verifier is None:
        verifier = "v%d" % i
    return {"t": 1000000 + i * 600,
            "next": nxt if nxt is not None else "task%d:act" % i,
            "verified": verified, "open": 1, "marker": marker,
            "confidence": "strong", "verifier": verifier, "risk": "low",
            "error": error, "outcome": "", "extra_steps": 0}


ERROR_BONUS_LABELS = (
    "fast error recovery",
    "high error diversity",
    "errors spread across domains",
    "high error focus",
    "thread recovery",
)

VERIFICATION_BONUS_LABELS = (
    "complete verification",
    "even verification distribution",
    "verify-then-act",
    "verifier consensus",
)


class ZeroEventSilenceTests(unittest.TestCase):
    """An event-free history must not be praised for event quality."""

    def test_zero_error_history_stays_silent_on_error_bonuses(self):
        h = [seam(i) for i in range(mindseam.STALL_RUN * 2)]
        _, reasons = mindseam.session_health_score(h)
        for label in ERROR_BONUS_LABELS:
            self.assertFalse(any(label in r for r in reasons),
                             "%s emitted on a zero-error history: %s"
                             % (label, reasons))

    def test_short_history_stays_silent_on_all_gated_factors(self):
        # Below every detector's minimum window the flags must stay shut;
        # the short-window sentinel 100 may not leak through an open gate.
        h = [seam(i) for i in range(mindseam.STALL_RUN - 1)]
        _, reasons = mindseam.session_health_score(h)
        for label in ERROR_BONUS_LABELS + VERIFICATION_BONUS_LABELS:
            self.assertFalse(any(label in r for r in reasons),
                             "%s emitted on a %d-seam history: %s"
                             % (label, len(h), reasons))


class VerificationFaceGatingTests(unittest.TestCase):
    """Zero-verification history: verification face silent, error face live."""

    def _history(self):
        # Real, mutually distinct error events, but never any verification:
        # opens the error-lens gates while keeping the verification lens
        # unmeasured, proving the gates are per-factor rather than global.
        return [seam(i, error="e%d:err" % i)
                for i in range(mindseam.STALL_RUN * 2)]

    def test_zero_verification_history_stays_silent_on_verification_bonuses(self):
        _, reasons = mindseam.session_health_score(self._history())
        for label in VERIFICATION_BONUS_LABELS:
            self.assertFalse(any(label in r for r in reasons),
                             "%s emitted on a zero-verification history: %s"
                             % (label, reasons))

    def test_error_face_bonuses_still_live_under_real_errors(self):
        _, reasons = mindseam.session_health_score(self._history())
        self.assertTrue(any("high error diversity" in r for r in reasons),
                        reasons)
        self.assertTrue(
            any("errors spread across domains" in r for r in reasons), reasons)


class RealMeasurementStillEarnsBonusesTests(unittest.TestCase):
    """The gates mute absence, never accomplishment."""

    def test_delivered_work_earns_completion_convergence_lean_bonuses(self):
        h = [seam(i, verified=1, marker="DONE")
             for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("complete verification" in r for r in reasons),
                        reasons)
        self.assertTrue(any("late convergence" in r for r in reasons), reasons)
        self.assertTrue(any("lean effective reasoning" in r for r in reasons),
                        reasons)

    def test_rising_verified_window_earns_distribution_and_consensus(self):
        # A single named verifier across the window is what makes agreement
        # measurable at all (each name needs >= 2 entries); the rising
        # cumulative count then measures stable confirmation.
        h = [seam(i, verified=i, verifier="vx")
             for i in range(mindseam.STALL_RUN * 2)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("even verification distribution" in r for r in reasons),
            reasons)
        self.assertTrue(any("verifier consensus" in r for r in reasons),
                        reasons)

    def test_escalation_response_and_verify_lead_time_stay_measurable(self):
        h = [{"t": 2000000 + i * 600,
              "next": "dom%d:step" % i,
              "verified": 1, "open": 1, "marker": "OPEN",
              "confidence": "strong",
              "verifier": "va" if i % 2 == 0 else "vb",
              "risk": "high" if i >= 1 else "low",
              "error": "", "outcome": "ok", "extra_steps": 0}
             for i in range(mindseam.STALL_RUN * 2)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("adaptive risk response" in r for r in reasons),
                        reasons)
        self.assertTrue(any("verify-then-act" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
