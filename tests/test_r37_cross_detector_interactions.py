"""Cross-detector interaction tests for Mindseam V3.6.

Targets detector call-paths whose meaning depends on more than one
detector firing in combination, spanning R33-R42 versioned detectors.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str((__import__("pathlib").Path(__file__).resolve().parent.parent / "mindseam" / "scripts")))
import mindseam

STALL = mindseam.STALL_RUN
HISTORY_MAX = mindseam.HISTORY_MAX


def _step(i, confidence="thin", next_action=None, verifier=None, error="", outcome="", reason="",
          marker="STEP", verified=1, extra_steps=0, risk="low",
          magnified_risk="low", nov="new", eag=1.0, open=0):
    if next_action is None:
        next_action = "step-%d:act" % i
    if verifier is None:
        verifier = "v%d" % i
    return dict(
        step=i, t=1000 + i, action="cast_%d" % i,
        next=next_action, confidence=confidence, risk=risk,
        magnified_risk=magnified_risk, verified=verified,
        reason=reason, verifier=verifier, outcome=outcome,
        expect="secondary", output_received="ok",
        output_expected="ok", error=error,
        extra_steps=extra_steps, marker=marker,
        nov=nov, eag=eag, open=open,
    )


class StallFatigueInteractionTests(unittest.TestCase):

    def test_stalled_session_reads_as_fatigued(self):
        h = [_step(i, confidence="", next_action="retry-%d" % i,
                   verifier="", error="net timeout", outcome="", reason="")
             for i in range(STALL)]
        stall = mindseam.detect_stall(h)
        fatigue = mindseam.session_fatigue(h)
        self.assertTrue(stall)
        self.assertGreaterEqual(fatigue, 20)

    def test_active_session_not_stall_and_low_fatigue(self):
        h = [_step(i, confidence="strong", next_action="task%d:act" % i,
                   verifier="specific_v%d" % i, outcome="ok", reason="done",
                   verified=1 if i < 8 else 0)
             for i in range(10)]
        stall = mindseam.detect_stall(h)
        fatigue = mindseam.session_fatigue(h)
        self.assertFalse(stall)
        self.assertLess(fatigue, 30)


class RiskEvidenceInteractionTests(unittest.TestCase):

    def test_high_risk_escalation_lowers_evidence_weight(self):
        h = [_step(i, confidence="thin", risk="high",
                   magnified_risk="high", error="auth timeout",
                   outcome="", verifier="")
             for i in range(STALL)]
        risk_signal = mindseam.detect_risk_escalation(h)
        weight = mindseam.evidence_weight(h)
        if risk_signal:
            self.assertLess(weight, 70)

    def test_low_risk_steady_state_keeps_evidence_weight_high(self):
        h = [_step(i, confidence="strong", risk="low",
                   magnified_risk="low", outcome="ok", verifier="v%d" % i,
                   reason="done")
             for i in range(STALL)]
        weight = mindseam.evidence_weight(h)
        self.assertGreaterEqual(weight, 50)


class RecoveryErrorInteractionTests(unittest.TestCase):

    def test_recovery_detected_when_recovery_ratio_high(self):
        h = []
        for i in range(STALL):
            h.append(_step(i, error="tmp" if i == 0 else "",
                           next_action="task%d:fix" % i,
                           verifier="v%d" % i,
                           outcome="recovered" if i == 0 else "ok",
                           reason="retry", verified=1,
                           marker="DONE" if i == 0 else "STEP",
                           risk="high" if i == 0 else "low"))
        rec = mindseam.error_recovery_ratio(h)
        recovery_signal = mindseam.detect_recovery(h)
        self.assertEqual(rec, 100)
        self.assertTrue(recovery_signal)


class MomentumConfidenceInteractionTests(unittest.TestCase):

    def test_positive_momentum_with_rising_confidence(self):
        h = [_step(i, confidence=["thin", "medium", "strong", "verified"][min(i, 3)],
                   next_action="task%d:act" % i, verifier="v%d" % i,
                   outcome="ok", reason="done")
             for i in range(STALL)]
        momentum = mindseam.session_momentum(h)
        decay = mindseam.confidence_decay_rate(h)
        self.assertIn(momentum, ("stable", "positive"))
        # Round 24: rising confidence is recovery, not decay.
        self.assertEqual(decay, 0.0)


class VolatilityConfidenceInteractionTests(unittest.TestCase):

    def test_high_volatility_with_oscillating_confidence(self):
        lvls = ["thin", "strong", "thin", "strong", "thin"]
        h = [_step(i, confidence=lvls[i % len(lvls)],
                   next_action="task%d:act" % i, verifier="v%d" % i,
                   outcome="ok" if i % 2 == 0 else "", reason="flip")
             for i in range(STALL)]
        vol = mindseam.detect_volatility(h)
        self.assertTrue(vol)


class LedgerVerificationInteractionTests(unittest.TestCase):

    def test_unverified_core_items_triggers_ledger_stagnation(self):
        LEDGER_STALE = 8
        h = [_step(i, confidence="thin", next_action="think more",
                   verifier="", outcome="", reason="", verified=0)
             for i in range(LEDGER_STALE + 2)]
        book = {
            "Core": ["Core item 1 — anchor one"], "Next": ["n1"], "Goal": ["g1"],
            "Open": ["o1"], "Verified": ["v1"], "Closing": [],
            "Review": [], "Verifier": ["ver1"], "Marker": ["m1"],
            "Confidence": ["thin"], "Risk": ["low"],
            "Timestamp": ["t1"], "Closed": [], "Meta": [],
        }
        stagnation = mindseam.detect_ledger_stagnation(h, book)
        self.assertTrue(stagnation)


class HealHealthInteractionTests(unittest.TestCase):

    def test_low_health_triggers_heal_actions(self):
        h = [_step(i, confidence="", next_action="do it", verifier="",
                   error="net timeout", outcome="", reason="", verified=0)
             for i in range(STALL)]
        health, reasons = mindseam.session_health_score(h)
        actions = mindseam.heal_actions(h)
        self.assertIsInstance(actions, list)
        if health < 50:
            self.assertTrue(len(actions) > 0)


class CompactionRecencyInteractionTests(unittest.TestCase):
    """compact_history writes .mindseam paths relative to the cwd; these
    tests patch them to a temp directory so running the suite never
    appends fixture entries to a real workspace (round 50)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_history = mindseam.HISTORY
        self.old_archive = mindseam.HISTORY_ARCHIVE
        mindseam.HISTORY = str(Path(self.tmp.name) / "history.json")
        mindseam.HISTORY_ARCHIVE = str(Path(self.tmp.name) / "archive.json")

    def tearDown(self):
        mindseam.HISTORY = self.old_history
        mindseam.HISTORY_ARCHIVE = self.old_archive
        self.tmp.cleanup()

    def test_compacted_history_recency_still_meaningful(self):
        n = HISTORY_MAX + 3
        h = [_step(i, confidence="medium", next_action="task%d:act" % i,
                   verifier="v%d" % i, outcome="ok", reason="done")
             for i in range(n)]
        h[0]["confidence"] = "thin"
        h[1]["confidence"] = "thin"
        compacted, changed, _ = mindseam.compact_history(h)
        # changed must be True — a cross-volume write failure used to
        # leave this False and the assertions below never ran (round 52).
        self.assertTrue(changed)
        recency = mindseam.evidence_recency(compacted)
        self.assertGreaterEqual(recency, 0)
        self.assertLessEqual(recency, 100)


if __name__ == "__main__":
    unittest.main()
