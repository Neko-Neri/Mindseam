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
    }


GEN_BOOK = {
    "Core": ["c1"], "Next": ["n1"], "Goal": ["g1"], "Open": ["o1"],
    "Verified": ["v1"], "Closing": [], "Review": [], "Verifier": ["ver1"],
    "Marker": ["m1"], "Confidence": ["thin"], "Risk": ["low"],
    "Timestamp": ["t1"], "Closed": [], "Meta": [],
}


class R41ErrorSilenceRatioTests(unittest.TestCase):
    def test_no_errors(self):
        h = [_step(i, nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.error_silence_ratio(h), 100)

    def test_all_long_errors(self):
        h = [_step(i, error="detailed:%d_err_message" % i, nxt="task%d:act" % i)
             for i in range(5)]
        self.assertEqual(mindseam.error_silence_ratio(h), 100)

    def test_all_short_errors(self):
        h = [_step(i, error="e:d", nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.error_silence_ratio(h), 0)

    def test_mixed_errors(self):
        half = mindseam.STALL_RUN // 2
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append(_step(i, error="short" if i < half else "detailed:error_%d" % i,
                           nxt="task%d:act" % i))
        score = mindseam.error_silence_ratio(h)
        self.assertTrue(0 < score < 100)

    def test_short_history(self):
        h = [_step(i, error="short") for i in range(2)]
        self.assertEqual(mindseam.error_silence_ratio(h), 100)

    def test_observations_trigger(self):
        h = [_step(i, error="e:%d" % i, marker=["OPEN", "CLOSED"][i % 2],
                   nxt="t%d:work" % i, confidence=["thin", "weak", "shaky"][i % 3])
             for i in range(5)]
        facts = mindseam.observations(h, book=GEN_BOOK.copy())
        self.assertTrue(any("error description score is low" in f.lower() for f in facts))


class R41VerifierSpecificityTests(unittest.TestCase):
    def test_no_verifiers(self):
        h = [_step(i, nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.verifier_specificity(h), 100)

    def test_all_specific_verifiers(self):
        h = [_step(i, verifier="unit_test_suite_%d" % i, nxt="task%d:act" % i)
             for i in range(5)]
        self.assertEqual(mindseam.verifier_specificity(h), 100)

    def test_all_generic_verifiers(self):
        h = [_step(i, verifier="v%d" % i, nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.verifier_specificity(h), 0)

    def test_mixed_verifiers(self):
        half = mindseam.STALL_RUN // 2
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append(_step(i, verifier="specific_test_%d" % i if i < half else "v%d" % i,
                           nxt="task%d:act" % i))
        score = mindseam.verifier_specificity(h)
        self.assertTrue(0 < score < 100)

    def test_short_history(self):
        h = [_step(0, verifier="v1"), _step(1, verifier="v2")]
        self.assertEqual(mindseam.verifier_specificity(h), 100)

    def test_observations_trigger(self):
        h = [_step(i, verifier="v%d" % i, marker=["OPEN", "DONE"][i % 2],
                   nxt="task%d:act" % i, confidence="thin", error="")
             for i in range(5)]
        facts = mindseam.observations(h, book=GEN_BOOK.copy())
        self.assertTrue(any("verifier specificity" in f.lower() for f in facts))


class R41NextActionSpecificityTests(unittest.TestCase):
    def test_all_specific(self):
        h = [_step(i, nxt="implement auth module with JWT token support") for i in range(5)]
        self.assertEqual(mindseam.next_action_specificity(h), 100)

    def test_all_vague(self):
        h = [_step(i, nxt="think about it") for i in range(5)]
        self.assertEqual(mindseam.next_action_specificity(h), 0)

    def test_mixed_specificity(self):
        half = mindseam.STALL_RUN // 2
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append(_step(i, nxt="implement feature X with tests" if i < half else "try again",
                           confidence="thin", error="", verifier=""))
        score = mindseam.next_action_specificity(h)
        self.assertTrue(0 < score < 100)

    def test_short_history(self):
        h = [_step(0, nxt="alpha"), _step(1, nxt="beta")]
        self.assertEqual(mindseam.next_action_specificity(h), 100)

    def test_empty_next(self):
        h = [_step(i, nxt="") for i in range(5)]
        self.assertEqual(mindseam.next_action_specificity(h), 0)

    def test_observations_trigger(self):
        h = [_step(i, nxt="think more" if i % 2 == 0 else "thinking",
                   marker=["OPEN", "CLOSED"][i % 2], confidence="thin", error="",
                   verifier="", verified=1)
             for i in range(5)]
        facts = mindseam.observations(h, book=GEN_BOOK.copy())
        self.assertTrue(any("next-action specificity" in f.lower() for f in facts))


class R41ConfidencePresenceTests(unittest.TestCase):
    def test_all_present(self):
        h = [_step(i, confidence="thin", nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.confidence_presence(h), 100)

    def test_all_missing(self):
        h = [_step(i, confidence="", nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.confidence_presence(h), 0)

    def test_mixed_presence(self):
        half = mindseam.STALL_RUN // 2
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append(_step(i, confidence="thin" if i < half else "",
                           nxt="task%d:act" % i))
        score = mindseam.confidence_presence(h)
        self.assertTrue(0 < score < 100)

    def test_short_history(self):
        h = [_step(0, confidence="thin"), _step(1)]
        self.assertEqual(mindseam.confidence_presence(h), 100)

    def test_dict_input(self):
        self.assertEqual(mindseam.confidence_presence({}), 100)

    def test_observations_trigger(self):
        h = [_step(i, confidence="", marker=["OPEN", "STEP", "DONE", "CLOSED", "OPEN"][i],
                   nxt="t%d:work" % i, verified=1, verifier="ok%d" % i, error="")
             for i in range(5)]
        facts = mindseam.observations(h, book=GEN_BOOK.copy())
        self.assertTrue(any("confidence presence" in f.lower() for f in facts))


class R41DetectorsSHSTests(unittest.TestCase):
    def test_verifier_specificity_shs_fact(self):
        h = [_step(i, verifier="v%d" % i, nxt="task%d:act" % i,
                   confidence="thin", marker="STEP", error="", verified=1)
             for i in range(5)]
        score, reasons = mindseam.session_health_score(h, book=GEN_BOOK.copy())
        self.assertTrue(any("verifier specificity low" in r for r in reasons))

    def test_next_action_specificity_shs_fact(self):
        h = [_step(i, nxt="think more", confidence="thin", marker="STEP",
                   error="", verifier="spec%d" % i, verified=0)
             for i in range(5)]
        score, reasons = mindseam.session_health_score(h, book=GEN_BOOK.copy())
        self.assertTrue(any("next-action specificity low" in r for r in reasons))

    def test_confidence_presence_shs_fact(self):
        h = [_step(i, confidence="", nxt="task%d:act" % i, marker="STEP",
                   error="", verifier="v%d" % i, verified=0)
             for i in range(5)]
        score, reasons = mindseam.session_health_score(h, book=GEN_BOOK.copy())
        self.assertTrue(any("confidence presence low" in r for r in reasons))

    def test_error_silence_ratio_shs_fact(self):
        h = [_step(i, error="e:d" if i < 3 else "", nxt="task%d:act" % i,
                   confidence="thin", marker="STEP", verifier="v%d" % i, verified=1)
             for i in range(5)]
        score, reasons = mindseam.session_health_score(h, book=GEN_BOOK.copy())
        self.assertTrue(any("error description too short" in r for r in reasons))


if __name__ == "__main__":
    unittest.main()
