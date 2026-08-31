# -*- coding: utf-8 -*-
"""Round 79 guards: evidence_weight generator optimization and process verification scoring.

evidence_weight calculates the composite strength of empirical backing across recent
seams (verifier diversity, verified progress, recorded outcomes, error absence). The
accumulation logic was refactored with set comprehensions and generator expression sums,
eliminating manual loop counters while maintaining exact composite scoring weights. This
round pins maximum evidence weighting, error penalty deduction, and short window contracts.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam


class EvidenceWeightGeneratorTests(unittest.TestCase):

    def test_evidence_weight_empty_or_short_history(self):
        self.assertEqual(mindseam.evidence_weight([]), 0)
        self.assertEqual(mindseam.evidence_weight([{"verified": 1}]), 0)

    def test_evidence_weight_with_full_support(self):
        # 3 diverse verifiers, 3 verified items, 3 outcomes, 0 errors
        hist = [
            {"verifier": "pytest", "verified": 1, "outcome": "pass", "error": ""},
            {"verifier": "verify_suite", "verified": 2, "outcome": "pass", "error": ""},
            {"verifier": "hypothesis", "verified": 3, "outcome": "pass", "error": ""},
        ]
        score = mindseam.evidence_weight(hist)
        # 3*10=30 (verifier_set) + 3*8=24 (verified_count) + 3*8=24 (outcome_count) + 15 (no error) = 93
        self.assertEqual(score, 93)

    def test_evidence_weight_with_error_penalty(self):
        # Error present in window -> loses 15 bonus points
        hist = [
            {"verifier": "pytest", "verified": 1, "outcome": "pass", "error": "timeout"},
            {"verifier": "pytest", "verified": 2, "outcome": "pass", "error": ""},
            {"verifier": "pytest", "verified": 3, "outcome": "pass", "error": ""},
        ]
        score = mindseam.evidence_weight(hist)
        # 1*10=10 (verifier_set) + 3*8=24 (verified_count) + 3*8=24 (outcome_count) + 0 (error present) = 58
        self.assertEqual(score, 58)


if __name__ == "__main__":
    unittest.main()
