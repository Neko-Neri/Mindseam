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
    marker="OPEN",
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


BASE_BOOK = {
    "Core": ["c1"],
    "Next": ["n1"],
    "Goal": ["g1"],
    "Open": ["o1"],
    "Verified": ["v1"],
    "Closing": [],
    "Review": [],
    "Verifier": ["ver1"],
    "Marker": ["m1"],
    "Confidence": ["thin"],
    "Risk": ["low"],
    "Timestamp": ["t1"],
    "Closed": [],
    "Meta": [],
}


class R40TemporalContinuityTests(unittest.TestCase):

    def test_monotonic(self):
        h = [{"t": i} for i in range(6)]
        self.assertEqual(mindseam.temporal_continuity(h), 100)

    def test_backward_jump(self):
        h = [{"t": i} for i in range(6)]
        h[5]["t"] = 1
        self.assertEqual(mindseam.temporal_continuity(h), 0)

    def test_short_history(self):
        h = [{"t": 0}]
        self.assertEqual(mindseam.temporal_continuity(h), 100)

    def test_dict_input(self):
        h = {"t": 0}
        self.assertEqual(mindseam.temporal_continuity(h), 100)


class R40LedgerVolatilityTests(unittest.TestCase):

    def test_no_changes_same_marker(self):
        h = [_step(i, marker="OPEN") for i in range(7)]
        self.assertEqual(mindseam.ledger_volatility(h, BASE_BOOK), 100)

    def test_high_churn(self):
        h = [_step(i, marker=["OPEN", "CLOSED"][i % 2]) for i in range(7)]
        score = mindseam.ledger_volatility(h, BASE_BOOK)
        self.assertEqual(score, 0)

    def test_short_history(self):
        h = [_step(0, marker="OPEN"), _step(1, marker="STEP")]
        self.assertEqual(mindseam.ledger_volatility(h, BASE_BOOK), 100)

    def test_empty_book(self):
        h = [_step(i, marker="OPEN") for i in range(5)]
        self.assertEqual(mindseam.ledger_volatility(h, {}), 100)

    def test_single_open_thread(self):
        h = [_step(i, marker="OPEN") for i in range(7)]
        score = mindseam.ledger_volatility(h, BASE_BOOK)
        self.assertEqual(score, 100)

    def test_intermediate_score_range(self):
        seq = ["OPEN", "OPEN", "OPEN", "CLOSED", "CLOSED", "CLOSED", "OPEN"]
        h = [_step(i, marker=seq[i]) for i in range(7)]
        score = mindseam.ledger_volatility(h, BASE_BOOK)
        self.assertTrue(0 <= score <= 100)


class R40VerificationCompletionRatioTests(unittest.TestCase):

    def test_make_steps(self):
        count = mindseam.STALL_RUN
        h = [{"t": i, "next": "alpha:step", "marker": "OPEN",
               "confidence": "thin", "eag": 0.5, "risk": "low", "error": "",
               "verified": 1, "verifier": "v1", "extra_steps": 0}
             for i in range(count)]
        for step in h:
            step["verified"] = 1
            step["verifier"] = "v1"
        self.assertEqual(mindseam.verification_completion_ratio(h), 100)

    def test_all_complete(self):
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append({"t": i, "next": "alpha:step", "marker": "OPEN",
                       "confidence": "thin", "eag": 0.5, "risk": "low", "error": "",
                        "verified": 1, "verifier": "v1", "extra_steps": 0})
        self.assertEqual(mindseam.verification_completion_ratio(h), 100)

    def test_all_pending(self):
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append({"t": i, "next": "alpha:step", "marker": "OPEN",
                       "confidence": "thin", "eag": 0.5, "risk": "low", "error": "",
                        "verified": 0, "verifier": "v1", "extra_steps": 0})
        self.assertEqual(mindseam.verification_completion_ratio(h), 0)

    def test_mixed(self):
        h = [_step(0, verifier="v1", verified=1),
             _step(1, verifier="v2", verified=0),
             _step(2, verifier="", verified=0)]
        self.assertEqual(mindseam.verification_completion_ratio(h), 50)

    def test_none_started(self):
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append({"t": i, "next": "alpha:step", "marker": "OPEN",
                       "confidence": "thin", "eag": 0.5, "risk": "low", "error": "",
                        "verified": 0, "verifier": "", "extra_steps": 0})
        self.assertEqual(mindseam.verification_completion_ratio(h), 100)

    def test_short_history(self):
        h = [_step(0, verifier="v1", verified=1)]
        self.assertEqual(mindseam.verification_completion_ratio(h), 100)

    def test_direct_score_zero(self):
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append({"t": 1000 + i, "next": "task%d:act" % i, "marker": "DONE",
                       "confidence": "thin", "eag": 0.5,
                       "risk": ["low", "medium", "high"][i], "error": "",
                        "verified": 0, "verifier": "auto%d" % i, "extra_steps": 0})
        self.assertEqual(mindseam.verification_completion_ratio(h), 0)

    def test_shs_incomplete_verification(self):
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append({"t": 1000 + i, "next": "task%d:act" % i, "marker": "DONE",
                       "confidence": "thin", "eag": 0.5,
                       "risk": ["low", "medium", "high"][i], "error": "",
                        "verified": 0, "verifier": "auto%d" % i, "extra_steps": 0})
        score, reasons = mindseam.session_health_score(h, book=BASE_BOOK.copy())
        self.assertTrue(any("verifications left open" in r for r in reasons))


class R40ErrorRecoveryRatioTests(unittest.TestCase):

    def test_recovery_expected(self):
        h = [_step(i, error="a:err" if i == 0 else "",
                   nxt="task%d:act" % i)
             for i in range(5)]
        score = mindseam.error_recovery_ratio(h)
        self.assertEqual(score, 100)

    def test_no_recovery(self):
        h = [_step(i, error="net:timeout", nxt="task%d:act" % i)
             for i in range(5)]
        score = mindseam.error_recovery_ratio(h)
        self.assertEqual(score, 0)

    def test_no_errors(self):
        h = [_step(i, nxt="task%d:act" % i) for i in range(5)]
        self.assertEqual(mindseam.error_recovery_ratio(h), 100)

    def test_trailing_error(self):
        h = [_step(i, error="sync:fail" if i == 4 else "",
                   nxt="task%d:act" % i)
             for i in range(5)]
        score = mindseam.error_recovery_ratio(h)
        self.assertEqual(score, 100)

    def test_double_error_recovery(self):
        h = [_step(0, error="a:err", nxt="t0:a"),
             _step(1, error="a:err", nxt="t1:a"),
             _step(2, error="", nxt="t2:a"),
             _step(3, error="b:err", nxt="t3:a"),
             _step(4, error="", nxt="t4:a")]
        score = mindseam.error_recovery_ratio(h)
        self.assertEqual(score, 100)

    def test_observations_persistent_errors(self):
        h = []
        for i in range(5):
            h.append({"t": i, "next": "t%d:e" % i, "marker": "STEP",
                       "confidence": "thin", "eag": 0.5,
                       "risk": "low", "error": "persist:err",
                       "verified": 0, "verifier": "e%d" % i, "extra_steps": 0})
        facts = mindseam.observations(h, book=BASE_BOOK.copy())
        self.assertTrue(any("error recovery failure" in f.lower()
                           for f in facts))

    def test_observations_single_error_ok(self):
        h = []
        for i in range(5):
            h.append({"t": i, "next": "t%d:a" % i, "marker": "STEP",
                       "confidence": "thin", "eag": 0.5,
                       "risk": "low", "error": "a:err" if i == 0 else "",
                       "verified": 0, "verifier": "e%d" % i, "extra_steps": 0})
        facts = mindseam.observations(h, book=BASE_BOOK.copy())
        self.assertFalse(any("error recovery failure" in f.lower()
                            for f in facts))

    def test_shs_persistent_error_fact(self):
        h = []
        for i in range(5):
            h.append({"t": i, "next": "t%d:e" % i, "marker": "STEP",
                       "confidence": "thin", "eag": 0.5,
                       "risk": "low", "error": "persist:err",
                       "verified": 0, "verifier": "e%d" % i, "extra_steps": 0})
        score, reasons = mindseam.session_health_score(h, book=BASE_BOOK.copy())
        self.assertTrue(any("error recovery failure" in r for r in reasons))


if __name__ == "__main__":
    unittest.main()