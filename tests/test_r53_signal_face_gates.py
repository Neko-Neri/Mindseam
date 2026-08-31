# -*- coding: utf-8 -*-
"""Round 13 guards: signal-absent sentinels and the honest short window.

Round 12 (test_r52) gated the twelve event-dependent factors. This round
extends the audit to the rest of the bonus face, where the sentinel leaks
were of two kinds:

  1. Signal-absent sentinels on full windows. A detector whose signal was
     simply never asserted returned the same 100 it awards to measured
     perfection: an all-low-risk history collected "good risk outcome
     correlation" forever, a no-confidence history collected "calibrated
     confidence", a next-less history collected "high thread management",
     "action diversity", "stable story", "narrative resolution" and "broad
     domain coverage". Ten bonus branches are now gated on whether their
     signal was actually observed, mirroring each detector's exact window
     and counting rule. Penalty faces stay ungated: every one of them
     already requires the signal to have been observed before it can fire.

  2. The short window was balanced rather than neutral. A 1-seam session
     scored 100 only because roughly +40 of phantom praise offset -50 of
     sentinel penalties. session_health_score now returns the same neutral
     100-with-no-reasons the empty history always returned, matching the
     window guard observations() already applies to its facts.

Silence contract: no praise for a measurement that never happened.
Liveness contract: a real measurement still earns its bonus.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def seam(i, nxt=None, verifier=None, verified=0, confidence="strong",
         marker="OPEN", risk="low", error=""):
    return {"t": 1000000 + i * 600,
            "next": nxt if nxt is not None else "dom%d: act on item %d" % (i % 3, i),
            "verified": verified, "open": 1, "marker": marker,
            "confidence": confidence,
            "verifier": verifier if verifier is not None else "v%d" % i,
            "risk": risk, "error": error, "outcome": "",
            "extra_steps": 0}


SIGNAL_ABSENT_LABELS = (
    # (label, fixture) pairs are built per test below so each silence
    # assertion names the signal whose absence it exercises.
    "good risk outcome correlation",
    "high confidence-verification alignment",
    "verified confidence",
    "calibrated confidence",
    "verifier diversity",
    "marker progress",
    "high thread management",
    "action diversity",
    "stable story",
    "narrative resolution",
    "broad domain coverage",
)


class ShortWindowNeutralityTests(unittest.TestCase):
    """Below STALL_RUN seams the fusion layer must not judge at all."""

    def test_one_seam_history_is_neutral(self):
        result = mindseam.session_health_score([seam(0, risk="high",
                                                   error="db: down")])
        self.assertEqual(result.score, 100)
        self.assertEqual(result.reasons, [])

    def test_two_seam_history_is_neutral(self):
        _, reasons = mindseam.session_health_score(
            [seam(0, risk="high"), seam(1, risk="high")])
        self.assertEqual(reasons, [])

    def test_empty_history_stays_neutral(self):
        result = mindseam.session_health_score([])
        self.assertEqual(result.score, 100)
        self.assertEqual(result.reasons, [])

    def test_neutrality_is_not_a_list_of_praise(self):
        # The old balance printed both phantom praise and sentinel
        # penalties for one seam; neutrality means an empty reason list,
        # not a net score of 100.
        _, reasons = mindseam.session_health_score([seam(0)])
        self.assertFalse(any("+" in r for r in reasons), reasons)
        self.assertFalse(any("-" in r for r in reasons), reasons)


class SignalAbsentSilenceTests(unittest.TestCase):
    """A full window whose signal was never asserted stays silent."""

    def test_all_low_risk_history_gets_no_correlation_praise(self):
        # risk outcome correlation needs both a high and a low prediction
        # to compare; an all-low history never makes the comparison.
        h = [seam(i, risk="low") for i in range(mindseam.STALL_RUN * 2)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("good risk outcome correlation" in r for r in reasons),
            reasons)

    def test_label_free_history_gets_no_confidence_praise(self):
        h = [seam(i, confidence="") for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        for label in ("high confidence-verification alignment",
                      "verified confidence",
                      "calibrated confidence"):
            self.assertFalse(any(label in r for r in reasons),
                             "%s emitted without any confidence label: %s"
                             % (label, reasons))

    def test_verifier_free_history_gets_no_diversity_praise(self):
        h = [seam(i, verifier="", verified=0) for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(any("verifier diversity" in r for r in reasons),
                         reasons)

    def test_marker_free_history_gets_no_progress_praise(self):
        h = [seam(i, marker="") for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(any("marker progress" in r for r in reasons),
                         reasons)

    def test_next_free_history_gets_no_action_praise(self):
        h = [seam(i, nxt="") for i in range(mindseam.STALL_RUN * 2)]
        _, reasons = mindseam.session_health_score(h)
        for label in ("high thread management", "action diversity",
                      "stable story", "narrative resolution",
                      "broad domain coverage"):
            self.assertFalse(any(label in r for r in reasons),
                             "%s emitted without any next action: %s"
                             % (label, reasons))


class MeasuredSignalStillEarnsTests(unittest.TestCase):
    """The gates mute absence, never accomplishment."""

    def test_mixed_risk_history_measures_the_correlation(self):
        # High-risk steps that stayed error-free are the honest version of
        # "risk predictions matched outcomes".
        h = [seam(i, risk="low") for i in range(3)] + \
            [seam(i, risk="high") for i in range(3, 6)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("good risk outcome correlation" in r for r in reasons),
            reasons)

    def test_verified_strong_confidence_earns_alignment_praise(self):
        h = [seam(i, confidence="strong", verified=1)
             for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("high confidence-verification alignment" in r
                for r in reasons), reasons)
        self.assertTrue(any("verified confidence" in r for r in reasons),
                        reasons)
        self.assertTrue(any("calibrated confidence" in r for r in reasons),
                        reasons)

    def test_spread_verifiers_earn_diversity_praise(self):
        h = [seam(i, verifier="v%d" % (i % 3))
             for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("verifier diversity" in r for r in reasons),
                        reasons)

    def test_advancing_markers_earn_progress_praise(self):
        h = [seam(i, marker=["OPEN", "STEP", "DONE"][i % 3])
             for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("marker progress" in r for r in reasons),
                        reasons)

    def test_resolved_threads_earn_management_praise(self):
        h = [seam(i, nxt="dom: resolve item %d" % i, verified=1)
             for i in range(mindseam.STALL_RUN + 1)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("high thread management" in r for r in reasons), reasons)

    def test_distinct_nexts_earn_diversity_and_story_praise(self):
        h = [seam(i, nxt="dom: step %d" % i)
             for i in range(mindseam.STALL_RUN * 2)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("action diversity" in r for r in reasons),
                        reasons)
        self.assertTrue(any("stable story" in r for r in reasons),
                        reasons)
        self.assertTrue(any("narrative resolution" in r for r in reasons),
                        reasons)

    def test_multiple_domains_earn_coverage_praise(self):
        h = [seam(i, nxt="dom%d: step" % (i % 3))
             for i in range(mindseam.STALL_RUN * 2)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("broad domain coverage" in r for r in reasons),
                        reasons)


class PenaltyFacesStayLiveTests(unittest.TestCase):
    """Gating the bonus must not gate the honest penalties."""

    def test_zero_deliverable_window_is_still_penalized(self):
        # cognitive_efficiency counts every entry; zero deliverables is a
        # real measurement, not an absent signal.
        h = [seam(i, verified=0, verifier="") for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("low cognitive efficiency" in r for r in reasons), reasons)

    def test_stub_nexts_are_still_penalized(self):
        # output_stub_ratio counts every entry; all-stub nexts is measured.
        h = [seam(i, nxt="todo") for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("output stub ratio" in r for r in reasons),
                        reasons)

    def test_concentrated_verifier_is_still_penalized(self):
        h = [seam(i, verifier="solo", verified=1)
             for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("verifier concentration" in r for r in reasons),
                        reasons)


if __name__ == "__main__":
    unittest.main()
