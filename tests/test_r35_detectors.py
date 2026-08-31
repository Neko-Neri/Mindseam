# Copyright (c) 2025 0xnq (jieecode) <mail@0xnq.cc>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

import sys, pathlib, unittest
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent / "mindseam" / "scripts"))

import mindseam


def _step(i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low"):
    return dict(t=1000 + i, next=next, marker=marker, verified=verified,
                confidence=confidence, risk=risk)


def _steps(count, next="A", marker="OPEN", verified=0, confidence="thin", risk="low"):
    return [_step(i, next, marker, verified, confidence, risk) for i in range(count)] 
 
def _alt_verified(count, confidence="strong", flip=1): 
    return [_step(i, verified=(i % 2 == flip), confidence=confidence) for i in range(count)]


class R35ConfidenceInflationTests(unittest.TestCase):
    def test_empty_history(self):
        self.assertEqual(mindseam.confidence_inflation([]), 100)

    def test_short_history(self):
        self.assertEqual(mindseam.confidence_inflation(_steps(mindseam.STALL_RUN)), 100)

    def test_all_strong_verified(self):
        self.assertEqual(mindseam.confidence_inflation(
            _steps(mindseam.STALL_RUN + 5, marker="DONE", verified=1, confidence="strong")), 100)

    def test_all_strong_unverified(self):
        self.assertEqual(mindseam.confidence_inflation(
            _steps(mindseam.STALL_RUN + 5, confidence="strong")), 0)

    def test_mixed_strong_verified_unverified(self):
        h = _alt_verified(mindseam.STALL_RUN + 5, confidence="strong")
        score = mindseam.confidence_inflation(h)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_no_strong_confidence(self):
        self.assertEqual(mindseam.confidence_inflation(
            _steps(mindseam.STALL_RUN + 5, confidence="thin")), 100)

    def test_shaky_confidence_not_inflated(self):
        self.assertEqual(mindseam.confidence_inflation(
            _steps(mindseam.STALL_RUN + 5, confidence="shaky")), 100)

    def test_session_health_score_penalty(self):
        h = _steps(mindseam.STALL_RUN + 5, confidence="strong")
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("confidence inflation" in r for r in reasons))
        self.assertLessEqual(score, 84)


class R35DomainCoverageTests(unittest.TestCase):
    def test_empty_history(self):
        self.assertEqual(mindseam.domain_coverage_score([]), 100)

    def test_short_history(self):
        self.assertEqual(mindseam.domain_coverage_score(
            _steps(mindseam.STALL_RUN * 2, next="alpha:x")), 33)

    def test_single_domain(self):
        h = _steps(mindseam.STALL_RUN * 2, next="alpha:x")
        score = mindseam.domain_coverage_score(h)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_two_domains(self):
        h = _steps(mindseam.STALL_RUN, next="alpha:x")
        h.extend(_steps(mindseam.STALL_RUN, next="beta:y"))
        score = mindseam.domain_coverage_score(h)
        self.assertGreaterEqual(score, 33)
        self.assertLessEqual(score, 100)

    def test_three_domains(self):
        pool = ["alpha:x", "beta:y", "gamma:z"]
        h = [_step(i, next=pool[i % 3]) for i in range(mindseam.STALL_RUN * 2)]
        score = mindseam.domain_coverage_score(h)
        self.assertEqual(score, 100)

    def test_book_fallback(self):
        book = {"Next": ["alpha:x"]}
        h = _steps(mindseam.STALL_RUN * 2, next="")
        result = mindseam.domain_coverage_score(h)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)

    def test_observations_triggers_narrow_coverage(self):
        h = _steps(mindseam.STALL_RUN * 2, next="alpha:x")
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("Domain coverage is narrow" in f for f in facts))

    def test_session_health_score_penalty(self):
        h = _steps(mindseam.STALL_RUN * 2, next="alpha:x")
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("narrow domain coverage" in r for r in reasons))


class R35VerificationTemporalBiasTests(unittest.TestCase):
    def test_short_history(self):
        h = _steps(mindseam.STALL_RUN, marker="DONE", verified=1)
        self.assertEqual(mindseam.verification_temporal_bias(h), 100)

    def test_balanced_verification(self):
        h = _steps(mindseam.STALL_RUN * 2, marker="DONE", verified=1)
        score = mindseam.verification_temporal_bias(h)
        self.assertGreaterEqual(score, 80)
        self.assertLessEqual(score, 100)

    def test_first_half_only(self):
        h = _steps(mindseam.STALL_RUN, marker="DONE", verified=1)
        h.extend(_steps(mindseam.STALL_RUN, marker="OPEN", verified=0))
        score = mindseam.verification_temporal_bias(h)
        self.assertLess(score, 50)

    def test_second_half_only(self):
        h = _steps(mindseam.STALL_RUN, marker="OPEN", verified=0)
        h.extend(_steps(mindseam.STALL_RUN, marker="DONE", verified=1))
        score = mindseam.verification_temporal_bias(h)
        self.assertLess(score, 50)

    def test_no_verification(self):
        h = _steps(mindseam.STALL_RUN * 2)
        self.assertEqual(mindseam.verification_temporal_bias(h), 100)

    def test_observations_triggers_bias(self):
        h = _steps(mindseam.STALL_RUN, marker="DONE", verified=1)
        h.extend(_steps(mindseam.STALL_RUN, marker="OPEN", verified=0))
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("Verification temporal bias" in f for f in facts))

    def test_session_health_score_penalty(self):
        h = _steps(mindseam.STALL_RUN, marker="DONE", verified=1)
        h.extend(_steps(mindseam.STALL_RUN, marker="OPEN", verified=0))
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("verification temporal bias" in r for r in reasons))


class R35LedgerStasisTests(unittest.TestCase):
    def test_no_book(self):
        h = _steps(mindseam.STALL_RUN * 2)
        self.assertEqual(mindseam.ledger_stasis_detector(h, None), 100)

    def test_no_next_in_ledger(self):
        book = {"Next": [""], "Goal": [""], "Core": [], "Verified": [], "Open": []}
        h = _steps(mindseam.STALL_RUN * 2)
        self.assertEqual(mindseam.ledger_stasis_detector(h, book), 100)

    def test_short_history(self):
        book = {"Next": ["A"], "Goal": [""], "Core": [], "Verified": [], "Open": []}
        h = _steps(mindseam.STALL_RUN)
        self.assertEqual(mindseam.ledger_stasis_detector(h, book), 100)

    def test_matching_next(self):
        book = {"Next": ["alpha:work"], "Goal": [""], "Core": [], "Verified": [], "Open": []}
        h = _steps(mindseam.STALL_RUN * 2, next="alpha:work")
        score = mindseam.ledger_stasis_detector(h, book)
        self.assertEqual(score, 100)

    def test_diverging_next(self):
        book = {"Next": ["alpha:work"], "Goal": [""], "Core": [], "Verified": [], "Open": []}
        h = _steps(mindseam.STALL_RUN * 2, next="beta:other")
        score = mindseam.ledger_stasis_detector(h, book)
        self.assertEqual(score, 0)

    def test_partial_match(self):
        book = {"Next": ["alpha:work"], "Goal": [""], "Core": [], "Verified": [], "Open": []}
        h = _steps(mindseam.STALL_RUN, next="alpha:work")
        h.extend(_steps(mindseam.STALL_RUN, next="beta:other"))
        score = mindseam.ledger_stasis_detector(h, book)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertNotEqual(score, 100)

    def test_session_health_score_bonus(self):
        book = {"Next": ["alpha:work"], "Goal": [""], "Core": [], "Verified": [], "Open": []}
        h = _steps(mindseam.STALL_RUN * 2, next="alpha:work")
        score, reasons = mindseam.session_health_score(h, book=book)
        self.assertTrue(any("ledger plan alignment" in r for r in reasons))

    def test_session_health_score_penalty(self):
        book = {"Next": ["alpha:work"], "Goal": [""], "Core": [], "Verified": [], "Open": []}
        h = _steps(mindseam.STALL_RUN * 2, next="beta:other")
        score, reasons = mindseam.session_health_score(h, book=book)
        self.assertTrue(any("ledger plan divergence" in r for r in reasons))
