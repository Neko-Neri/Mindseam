import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _step(
    t,
    nxt="alpha:step",
    marker="STEP",
    verified=0,
    confidence="thin",
    risk="low",
    error="",
    verifier="",
    outcome="",
    reason="",
    extra_steps=0,
    eag=0.5,
):
    return {
        "t": t,
        "next": nxt,
        "marker": marker,
        "verified": verified,
        "eag": eag,
        "confidence": confidence,
        "risk": risk,
        "error": error,
        "verifier": verifier,
        "extra_steps": extra_steps,
        "outcome": outcome,
        "reason": reason,
    }


BASE_BOOK = {
    "Core": ["c1"], "Next": ["n1"], "Goal": ["g1"], "Open": ["o1"],
    "Verified": ["v1"], "Closing": [], "Review": [], "Verifier": ["ver1"],
    "Marker": ["m1"], "Confidence": ["thin"], "Risk": ["low"],
    "Timestamp": ["t1"], "Closed": [], "Meta": [],
}


class R42ReasoningDepthRatioTests(unittest.TestCase):
    def test_all_shallow(self):
        h = [_step(i, nxt="") for i in range(5)]
        self.assertEqual(mindseam.reasoning_depth_ratio(h), 0)

    def test_all_deep(self):
        h = [_step(i, nxt="implement because requires validate analyze") for i in range(5)]
        self.assertEqual(mindseam.reasoning_depth_ratio(h), 100)

    def test_moderate_depth(self):
        h = [_step(0, nxt="implement the feature"), _step(1, nxt="proceed forward"),
             _step(2, nxt="configure deployment"), _step(3, nxt="continue"), _step(4, nxt="move")]
        score = mindseam.reasoning_depth_ratio(h)
        self.assertTrue(0 < score < 100)

    def test_short_history(self):
        h = [_step(0, nxt="go"), _step(1, nxt="go")]
        self.assertEqual(mindseam.reasoning_depth_ratio(h), 100)

    def test_no_next(self):
        h = [_step(i, nxt="") for i in range(5)]
        self.assertEqual(mindseam.reasoning_depth_ratio(h), 0)

    def test_dict_input(self):
        self.assertEqual(mindseam.reasoning_depth_ratio({}), 100)

    def test_observations_trigger(self):
        h = [_step(i, nxt="go", marker="STEP", confidence="thin", error="", verifier="ok%d" % i)
             for i in range(5)]
        facts = mindseam.observations(h, book=BASE_BOOK.copy())
        self.assertTrue(any("reasoning depth" in f.lower() for f in facts))


class R42ErrorAcknowledgmentRatioTests(unittest.TestCase):
    def test_no_errors(self):
        h = [_step(i, nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.error_acknowledgment_ratio(h), 100)

    def test_acknowledged(self):
        h = [_step(0, error="port 8080 conflict", nxt="fix port 8080 issue"),
             _step(1, error="", nxt="task1:act"),
             _step(2, error="", nxt="task2:act")]
        score = mindseam.error_acknowledgment_ratio(h)
        self.assertEqual(score, 100)

    def test_ignored_error(self):
        h = [_step(0, nxt="task0:act"),
             _step(1, nxt="task1:act"),
             _step(2, error="port 8080 conflict", nxt="proceed anyway"),
             _step(3, nxt="task3:act"),
             _step(4, nxt="task4:act")]
        score = mindseam.error_acknowledgment_ratio(h)
        self.assertEqual(score, 0)

    def test_mixed_acknowledgment(self):
        h = [_step(0, nxt="task0:act"),
             _step(1, nxt="task1:act"),
             _step(2, error="port 8080 conflict", nxt="proceed anyway"),
             _step(3, error="db connection timeout", nxt="retry db connection"),
             _step(4, nxt="task4:act")]
        score = mindseam.error_acknowledgment_ratio(h)
        self.assertTrue(0 < score < 100)

    def test_short_history(self):
        h = [_step(0, error="err"), _step(1, error="err2")]
        self.assertEqual(mindseam.error_acknowledgment_ratio(h), 100)

    def test_trailing_error_skipped(self):
        h = [_step(0, error="port issue", nxt="fix port issue"),
             _step(1, error="db issue")]
        score = mindseam.error_acknowledgment_ratio(h)
        self.assertTrue(0 <= score <= 100)

    def test_observations_trigger(self):
        h = [_step(i, error="something failed" if i == 2 else "",
                   nxt="ignore continue task" if i == 2 else ("t%d:a" % i),
                   marker="STEP", confidence="thin", verifier="", verified=0)
             for i in range(5)]
        facts = mindseam.observations(h, book=BASE_BOOK.copy())
        self.assertTrue(any("not acknowledged" in f.lower() for f in facts))


class R42VerificationCoverageScoreTests(unittest.TestCase):
    def test_no_verified(self):
        h = [_step(i, nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.verification_coverage_score(h), 100)

    def test_all_fully_covered(self):
        h = [_step(i, verified=1, outcome="ok", reason="checked", verifier="v",
                   nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.verification_coverage_score(h), 100)

    def test_all_bare_verified(self):
        h = [_step(i, verified=1, outcome="", reason="", verifier="",
                   nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.verification_coverage_score(h), 0)

    def test_mixed_coverage(self):
        h = [_step(0, verified=1, outcome="ok", reason="checked", verifier="", nxt="t0"),
             _step(1, verified=1, outcome="", reason="", verifier="v", nxt="t1"),
             _step(2, verified=1, outcome="", reason="", verifier="", nxt="t2")]
        score = mindseam.verification_coverage_score(h)
        self.assertTrue(0 < score < 100)

    def test_partial_verified(self):
        half = mindseam.STALL_RUN // 2
        h = []
        for i in range(5):
            is_verified = i < half
            h.append(_step(i, verified=1 if is_verified else 0,
                           outcome="ok" if is_verified else "", reason="r" if is_verified else "",
                           verifier="v" if is_verified else "", nxt="task%d:act" % i))
        score = mindseam.verification_coverage_score(h)
        self.assertTrue(0 <= score <= 100)

    def test_short_history(self):
        h = [_step(0, verified=1), _step(1, verified=0)]
        self.assertEqual(mindseam.verification_coverage_score(h), 100)

    def test_dict_input(self):
        self.assertEqual(mindseam.verification_coverage_score({}), 100)

    def test_observations_trigger(self):
        h = [_step(i, verified=1, outcome="", reason="", verifier="",
                   nxt="task%d:act" % i, marker="STEP", confidence="thin", error="")
             for i in range(5)]
        facts = mindseam.observations(h, book=BASE_BOOK.copy())
        self.assertTrue(any("coverage" in f.lower() for f in facts))


class R42MarkerTransitionDiversityTests(unittest.TestCase):
    def test_no_transitions(self):
        h = [_step(i, marker="STEP") for i in range(5)]
        self.assertEqual(mindseam.marker_transition_diversity(h), 0)

    def test_with_transitions(self):
        h = [_step(i, marker=["OPEN", "CLOSED", "DONE"][i % 3]) for i in range(5)]
        self.assertEqual(mindseam.marker_transition_diversity(h), 100)

    def test_mixed_transitions(self):
        h = [_step(0, marker="STEP"), _step(1, marker="STEP"), _step(2, marker="OPEN"),
             _step(3, marker="CLOSED"), _step(4, marker="STEP")]
        self.assertEqual(mindseam.marker_transition_diversity(h), 100)

    def test_short_history(self):
        h = [_step(0, marker="STEP"), _step(1, marker="STEP")]
        self.assertEqual(mindseam.marker_transition_diversity(h), 100)

    def test_no_markers_set(self):
        # Round 48: an unmarked window is an unmeasured sequence, not a
        # stagnant one — blanks are absence, not a repeated marker.
        h = [_step(i, marker="") for i in range(5)]
        self.assertEqual(mindseam.marker_transition_diversity(h), 100)

    def test_dict_input(self):
        self.assertEqual(mindseam.marker_transition_diversity({}), 100)


class R42DetectorsSHSTests(unittest.TestCase):
    def test_reasoning_depth_shs_fact(self):
        h = [_step(i, nxt="go", marker="STEP", confidence="thin", error="", verifier="ok%d" % i)
             for i in range(5)]
        score, reasons = mindseam.session_health_score(h, book=BASE_BOOK.copy())
        self.assertTrue(any("reasoning depth" in r.lower() for r in reasons))

    def test_error_acknowledgment_shs_fact(self):
        h = [_step(0, error="", nxt="task0:act"),
             _step(1, error="", nxt="task1:act"),
             _step(2, error="port 8080 conflict", nxt="proceed anyway"),
             _step(3, error="", nxt="task3:act"),
             _step(4, error="", nxt="task4:act")]
        score, reasons = mindseam.session_health_score(h, book=BASE_BOOK.copy())
        self.assertTrue(any("not acknowledged" in r.lower() for r in reasons))

    def test_verification_coverage_shs_fact(self):
        h = [_step(i, verified=1, outcome="", reason="", verifier="",
                   nxt="task%d:act" % i, marker="STEP", confidence="thin", error="")
             for i in range(5)]
        score, reasons = mindseam.session_health_score(h, book=BASE_BOOK.copy())
        self.assertTrue(any("verification coverage" in r.lower() for r in reasons))

    def test_marker_transition_shs_fact(self):
        h = [_step(i, marker="STEP", nxt="task%d:act" % i, confidence="thin",
                   error="", verifier="ok%d" % i) for i in range(5)]
        score, reasons = mindseam.session_health_score(h, book=BASE_BOOK.copy())
        self.assertTrue(any("marker sequence stagnant" in r.lower() for r in reasons))


if __name__ == "__main__":
    unittest.main()
