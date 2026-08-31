# -*- coding: utf-8 -*-
"""Round 14 guards: penalty faces that read absence as the worst score.

The bonus-face sentinel audit (rounds 12-13) asked which detectors award
perfect praise for a measurement that never happened. This round asks the
mirror question for the penalty face: which detectors punish a session for
a signal it never asserted?

Audit result: most penalty detectors are already absence-safe —
outcome_reliability, verifier_specificity, error_silence_ratio,
error_acknowledgment_ratio and verification_coverage_score all return 100
(their "no penalty" value) when the counted quantity is absent, and
next_action_specificity / reasoning_depth_ratio / evidence_weight /
confidence_presence measure every entry or are presence detectors by
design. One detector failed the audit:

  assumption_diversity collapses a never-labelled history into a single
  "unknown" bucket, scores it 0, and the fusion layer printed "low
  assumption diversity -5" — punishing the absence of confidence tags
  under a name that claims a spread was measured. confidence_presence
  already reports that absence as its one designed signal, so the
  factor is now silent without labels, live with them.

Also disclosed in step_retry_rate's docstring: the total<2 branch returns
100 because the recorded schema always carries a next string.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def seam(i, nxt=None, verifier=None, verified=0, confidence="strong",
         marker="OPEN", risk="low", error="", outcome=""):
    return {"t": 1000000 + i * 600,
            "next": nxt if nxt is not None else "dom%d: act on item %d" % (i % 3, i),
            "verified": verified, "open": 1, "marker": marker,
            "confidence": confidence,
            "verifier": verifier if verifier is not None else "v%d" % i,
            "risk": risk, "error": error, "outcome": outcome,
            "extra_steps": 0}


class AbsenceIsNotDiversityTests(unittest.TestCase):
    """A never-labelled history must not be punished for its spread."""

    def test_label_free_history_gets_no_diversity_penalty(self):
        h = [seam(i, confidence="") for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("assumption diversity" in r for r in reasons), reasons)

    def test_absence_is_reported_once_by_the_presence_detector(self):
        # confidence_presence is the designated reporter for missing tags;
        # it stays live while assumption_diversity stays silent.
        h = [seam(i, confidence="") for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("confidence presence low" in r for r in reasons), reasons)

    def test_uniform_labels_are_still_a_measured_profile(self):
        # With labels present, all-strong is a real single-profile
        # observation and keeps its penalty.
        h = [seam(i, confidence="strong")
             for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("low assumption diversity" in r for r in reasons), reasons)

    def test_balanced_labels_earn_no_penalty(self):
        h = [seam(i, confidence=["strong", "thin", "shaky"][i % 3])
             for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("low assumption diversity" in r for r in reasons), reasons)


class AlreadySilentFacesStaySilentTests(unittest.TestCase):
    """Pin the absence-safe contract of the audited penalty detectors."""

    def test_no_claims_no_reliability_penalty(self):
        h = [seam(i, outcome="") for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("outcome reliability" in r for r in reasons), reasons)

    def test_no_verifiers_no_specificity_penalty(self):
        h = [seam(i, verifier="", verified=0)
             for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("verifier specificity" in r for r in reasons), reasons)

    def test_no_errors_no_silence_or_acknowledgment_penalty(self):
        h = [seam(i, error="") for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("error description" in r for r in reasons), reasons)
        self.assertFalse(
            any("error not acknowledged" in r for r in reasons), reasons)

    def test_no_verifications_no_coverage_penalty(self):
        h = [seam(i, verified=0, verifier="") for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("verification coverage" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
