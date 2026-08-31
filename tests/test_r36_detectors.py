# Copyright (c) 2025 0xnq (jieecode) <mail@0xnq.cc>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

import sys, pathlib, unittest
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent / "mindseam" / "scripts"))

import mindseam


def _step(i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low", error="", verifier=""):
    return dict(t=1000 + i, next=next, marker=marker, verified=verified,
                confidence=confidence, risk=risk, error=error, verifier=verifier)


def _steps(count, **kw):
    return [_step(i, **kw) for i in range(count)]


def _risked_escalation(adapt):
    """count=STALL_RUN*2, half low→high transitions, specify adapt or not."""
    half = mindseam.STALL_RUN
    h = []
    for i in range(half):
        h.append(_step(i, risk="low", next="alpha:x"))
    for i in range(half, half * 2):
        h.append(_step(i, risk="high", next="beta:y" if adapt else "alpha:x"))
    return h


class R36RiskEscalationResponseTests(unittest.TestCase):
    def test_empty_history(self):
        self.assertEqual(mindseam.risk_escalation_response([]), 100)

    def test_short_history(self):
        self.assertEqual(mindseam.risk_escalation_response(_steps(mindseam.STALL_RUN)), 100)

    def test_no_escalation(self):
        h = _steps(mindseam.STALL_RUN * 2, risk="low")
        self.assertEqual(mindseam.risk_escalation_response(h), 100)

    def test_all_escalation_not_adapted(self):
        h = _risked_escalation(adapt=False)
        self.assertEqual(mindseam.risk_escalation_response(h), 0)

    def test_all_escalation_adapted(self):
        h = _risked_escalation(adapt=True)
        result = mindseam.risk_escalation_response(h)
        # All 3 transitions adapted = 100
        self.assertEqual(result, 100)

    def test_mixed_escalation(self):
        h = _risked_escalation(adapt=True)
        h[mindseam.STALL_RUN]["next"] = "alpha:x"
        score = mindseam.risk_escalation_response(h)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 80)


class R36VerificationLeadTimeTests(unittest.TestCase):
    def test_short_history(self):
        self.assertEqual(mindseam.verification_lead_time(_steps(mindseam.STALL_RUN)), 100)

    def test_empty_history(self):
        self.assertEqual(mindseam.verification_lead_time([]), 100)

    def test_verify_then_act(self):
        h = [_step(i, marker="DONE", verified=1) for i in range(3)]
        h.extend([_step(i, marker="OPEN", verified=0) for i in range(3, 6)])
        score = mindseam.verification_lead_time(h)
        self.assertGreaterEqual(score, 80)

    def test_act_then_verify(self):
        h = [_step(i, marker="OPEN", verified=0) for i in range(3)]
        h.extend([_step(i, marker="DONE", verified=1) for i in range(3, 6)])
        score = mindseam.verification_lead_time(h)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_mixed(self):
        h = _steps(mindseam.STALL_RUN * 2)
        score = mindseam.verification_lead_time(h)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_no_transitions(self):
        h = _steps(mindseam.STALL_RUN * 2, marker="DONE", verified=1)
        self.assertEqual(mindseam.verification_lead_time(h), 100)


class R36VerifierAgreementTests(unittest.TestCase):
    def test_short_history(self):
        self.assertEqual(mindseam.verifier_agreement(_steps(mindseam.STALL_RUN)), 100)

    def test_empty_history(self):
        self.assertEqual(mindseam.verifier_agreement([]), 100)

    def test_no_verifier(self):
        h = _step(0, verified=1, verifier="", marker="DONE")
        h2 = _step(1, verified=0, verifier="")
        h3 = _step(2, verified=1)
        h4 = _step(3, verified=0)
        self.assertEqual(mindseam.verifier_agreement([h, h2, h3, h4] + _steps(2)), 100)

    def test_single_verifier_consistent(self):
        h = _steps(mindseam.STALL_RUN * 2, verifier="v1", verified=1, marker="DONE")
        self.assertEqual(mindseam.verifier_agreement(h), 100)

    def test_single_verifier_flips(self):
        h = _steps(mindseam.STALL_RUN * 2, verifier="v1", marker="DONE")
        for i in range(len(h)):
            h[i]["verified"] = 1 if i % 2 == 0 else 2
        score = mindseam.verifier_agreement(h)
        self.assertLessEqual(score, 30)

    def test_single_verifier_climbs(self):
        h = _steps(mindseam.STALL_RUN * 2, verifier="v1", marker="DONE")
        for i in range(len(h)):
            h[i]["verified"] = i + 1
        self.assertEqual(mindseam.verifier_agreement(h), 100)

    def test_multiple_verifiers(self):
        h1 = _steps(mindseam.STALL_RUN, verifier="vA", verified=1, marker="DONE")
        h2 = _steps(mindseam.STALL_RUN, verifier="vB", verified=0, marker="OPEN")
        score = mindseam.verifier_agreement(h1 + h2)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


class R36ConfidenceOutcomeTrackingTests(unittest.TestCase):
    def test_short_history(self):
        self.assertEqual(mindseam.confidence_outcome_tracking(_steps(mindseam.STALL_RUN)), 100)

    def test_empty_history(self):
        self.assertEqual(mindseam.confidence_outcome_tracking([]), 100)

    def test_no_confidence(self):
        h = _steps(mindseam.STALL_RUN, next="A")
        self.assertEqual(mindseam.confidence_outcome_tracking(h), 100)

    def test_all_aligned(self):
        h = _steps(mindseam.STALL_RUN, confidence="strong", verified=1, marker="DONE")
        self.assertEqual(mindseam.confidence_outcome_tracking(h), 100)

    def test_strong_misaligned(self):
        h = _steps(mindseam.STALL_RUN, confidence="strong", error="fail", marker="DONE")
        score = mindseam.confidence_outcome_tracking(h)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 30)

    def test_shaky_aligned(self):
        h = _steps(mindseam.STALL_RUN, confidence="shaky", error="fail", marker="OPEN")
        score = mindseam.confidence_outcome_tracking(h)
        self.assertGreater(score, 0)

    def test_mixed_alignment(self):
        h = _steps(mindseam.STALL_RUN, confidence="strong", verified=1, marker="DONE", error="")
        h.extend(_steps(mindseam.STALL_RUN, confidence="shaky", error="e", marker="OPEN"))
        score = mindseam.confidence_outcome_tracking(h)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)


class R36ObservationsWiringTests(unittest.TestCase):
    def test_risk_escalation_not_adapted(self):
        h = _risked_escalation(adapt=False)
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("Risk escalation is not adapted" in f for f in facts))

    def test_verification_lead_time_follows_action(self):
        h = _mismatched_leads(mindseam.STALL_RUN * 2)
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("Verification follows action" in f for f in facts))

    def test_verifier_disagreement(self):
        h = _steps(mindseam.STALL_RUN * 2, verifier="v1", verified=1, marker="DONE")
        for i in range(len(h) - 1):
            h[i]["verified"] = i % 2
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("Verifier disagreement" in f for f in facts))

    def test_confidence_outcome_misalignment(self):
        h = _steps(mindseam.STALL_RUN, confidence="strong", error="fail", marker="DONE")
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("Confidence-outcome misalignment" in f for f in facts))


class R36ShsWiringTests(unittest.TestCase):
    def test_risk_escalation_penalty(self):
        h = _risked_escalation(adapt=False)
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("risk escalation not adapted" in r for r in reasons))

    def test_verification_lead_time_penalty(self):
        h = _mismatched_leads(mindseam.STALL_RUN * 2)
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("act-then-verify" in r for r in reasons))

    def test_verifier_agreement_penalty(self):
        h = _steps(mindseam.STALL_RUN * 2, verifier="v1", verified=1, marker="DONE")
        for i in range(len(h)):
            h[i]["verified"] = 1 if i % 2 == 0 else 2
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("verifier disagreement" in r for r in reasons))

    def test_confidence_outcome_penalty(self):
        h = _steps(mindseam.STALL_RUN, confidence="strong", error="fail", marker="DONE")
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("confidence-outcome misalignment" in r for r in reasons))


def _mismatched_leads(count):
    return [_step(i, marker="OPEN", verified=0) for i in range(count * 3 // 4)] + \
           [_step(i, marker="DONE", verified=1) for i in range(count * 3 // 4, count)]
