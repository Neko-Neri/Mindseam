# -*- coding: utf-8 -*-
"""Round 6 guards for defects 13, 14 and 15.

Defect 13 (14 functions): the short-history guard sat INSIDE
``if run is None:``, so any caller passing ``run=`` skipped it and a
1-seam session was judged as if it had STALL_RUN seams (stall severity
70/100, "not changed for 3 seams") while heal_actions correctly asked
for more data. The guard now runs unconditionally before the run
default is filled in.

Defect 14: remediation_suggestions keyed on "swinging", "degrading"
and "bond overhang"; no fact observations() emits contains those
substrings, so genuine confidence degradation never received its
advice. Keys now match emitted facts; dead keys are gone.

Defect 15: ledger_volatility's docstring claimed an Open-thread-count
churn contract complementing ledger_stasis; it actually counts marker
OPEN/CLOSED flips and ignores its run argument.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def step(t, nxt="alpha:step", marker="OPEN", verified=0, confidence="thin",
         risk="low", verifier="", error="", outcome="", extra_steps=0):
    return {"t": 1000 + t * 600, "next": nxt, "verified": verified, "open": 1,
            "marker": marker, "confidence": confidence, "verifier": verifier,
            "risk": risk, "error": error, "outcome": outcome,
            "extra_steps": extra_steps}


BOOK = {"Goal": ["g"], "Core": ["c"], "Verified": [], "Open": ["o"],
        "Next": ["alpha:step"], "Closing": []}


class R46GuardFamilyTests(unittest.TestCase):
    """Defect 13: passing run= must not skip the short-history guard."""

    def test_short_histories_are_refused_even_when_run_is_passed(self):
        for hist in ([step(0)], [step(0), step(1)]):
            win = hist[-mindseam.STALL_RUN:]
            self.assertEqual(mindseam.pattern_persistence(hist, run=win), "none")
            self.assertEqual(mindseam.session_fatigue(hist, run=win), 0)
            self.assertEqual(mindseam.drift_velocity(hist, run=win), 0.0)
            self.assertEqual(mindseam.verification_depth(hist, run=win), 0)
            self.assertEqual(mindseam.premature_convergence(hist, score=True, run=win), 100)
            self.assertEqual(mindseam.cognitive_load_index(hist, run=win), 0)
            self.assertEqual(mindseam.resolution_rate(hist, run=win), 0.0)
            self.assertEqual(mindseam.escalation_likelihood(hist, run=win), 0)
            self.assertEqual(mindseam.detect_risk_escalation(hist, run=win), [])
            self.assertEqual(mindseam.detect_stall(hist, run=win), [])
            self.assertEqual(mindseam.detect_recovery(hist, run=win), [])
            self.assertEqual(mindseam.detect_volatility(hist, run=win), [])
            self.assertEqual(mindseam.stall_score(hist, run=win), 0)

    def test_fuse_run_refuses_short_histories_even_when_run_is_passed(self):
        for hist in ([step(0)], [step(0), step(1)]):
            self.assertEqual(
                mindseam._fuse_run(hist, run=hist[-mindseam.STALL_RUN:]),
                (0, 0.0, 0, False, False, False, None, False, False, False),
            )

    def test_no_detector_claims_three_seams_from_a_one_seam_history(self):
        hist = [step(0)]
        facts = mindseam.detect_stall(hist, run=hist[-mindseam.STALL_RUN:])
        joined = " ".join(facts).lower()
        self.assertNotIn("3 seams", joined)
        self.assertNotIn("three seams", joined)


class R46EndToEndContradictionTests(unittest.TestCase):
    """Defect 13 end to end: heal asks for more data, fusion must agree."""

    def test_one_seam_session_is_not_judged_by_the_fusion_layer(self):
        hist = [step(0)]
        score, reasons = mindseam.session_health_score(hist, book=dict(BOOK))
        self.assertEqual(score, 100)
        for reason in reasons:
            lowered = reason.lower()
            self.assertNotIn("stall", lowered)
            self.assertNotIn("compound pattern", lowered)
            self.assertNotIn("transient", lowered)
        advice = mindseam.heal_actions(hist, book=dict(BOOK))
        self.assertTrue(
            any("Collect at least %d seams" % mindseam.STALL_RUN in a for a in advice),
            "heal_actions should ask for more seams on a 1-seam session",
        )


class R46RemediationKeyTests(unittest.TestCase):
    """Defect 14: keys must match facts observations() actually emits."""

    def test_degradation_fact_receives_confidence_advice(self):
        fact = "Confidence trend shows degradation: strong -> thin -> shaky."
        out = mindseam.remediation_suggestions([fact], 80)
        self.assertIn("Confidence is degrading — revisit the initial premises now.", out)

    def test_removed_keys_never_match_again(self):
        facts = ["Confidence is swinging near the seam.",
                 "Bond overhang exposure is high."]
        self.assertEqual(mindseam.remediation_suggestions(facts, 80), [])

    def test_live_keys_still_match(self):
        out = mindseam.remediation_suggestions(
            ["Risk escalated across seams.", "Stall severity 70/100."], 40)
        self.assertEqual(len(out), 2)


class R46LedgerVolatilityDocTests(unittest.TestCase):
    """Defect 15: the docstring must describe marker-flip churn."""

    def test_docstring_describes_marker_flips_not_thread_count(self):
        doc = mindseam.ledger_volatility.__doc__ or ""
        self.assertIn("marker", doc.lower())
        self.assertIn("open/closed", doc.lower())
        self.assertNotIn("Open thread count changes", doc)
        self.assertNotIn("Complements `ledger_stasis`", doc)

    def test_ignored_run_argument_is_disclosed(self):
        doc = mindseam.ledger_volatility.__doc__ or ""
        self.assertIn("ignored", doc.lower())


if __name__ == "__main__":
    unittest.main()
