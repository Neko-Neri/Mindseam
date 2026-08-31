# -*- coding: utf-8 -*-
"""Round 23 guards: contradiction_detection fired on coherent pairs.

The detector's second clause counted ``thin`` (or missing) confidence on
high risk as a "risk-confidence contradiction" — but that pair is risk
awareness, both halves agreeing the step is shaky ground. Meanwhile the
inverse contradiction the docstring promised ("or vice versa") — ``shaky``
confidence carried on ``low`` risk — never fired at all, and the rank
table carried a "weak" key that no confidence command can produce.

A contradiction is now an opposite-valence pair: strong+high
(overconfidence) or shaky+low (unsupported doubt). Coherent cautious
pairs and unlabelled entries never count.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def rows(pairs):
    return [{"t": 1000 + i, "next": "dom: act %d" % i, "verified": 0,
             "open": 0, "marker": "OPEN", "confidence": c,
             "verifier": "v", "risk": r, "error": "", "outcome": "",
             "extra_steps": 0}
            for i, (c, r) in enumerate(pairs)]


class ContradictionTests(unittest.TestCase):

    def test_overconfidence_still_fires(self):
        facts = mindseam.contradiction_detection(
            rows([("strong", "high")] * 3))
        self.assertTrue(facts, facts)

    def test_unsupported_doubt_now_fires(self):
        facts = mindseam.contradiction_detection(
            rows([("shaky", "low")] * 3))
        self.assertTrue(facts, facts)

    def test_cautious_pair_is_not_a_contradiction(self):
        facts = mindseam.contradiction_detection(
            rows([("thin", "high")] * 3))
        self.assertEqual(facts, [])

    def test_missing_label_is_not_a_contradiction(self):
        facts = mindseam.contradiction_detection(
            rows([("", "high")] * 3))
        self.assertEqual(facts, [])

    def test_aligned_assessment_is_not_a_contradiction(self):
        facts = mindseam.contradiction_detection(
            rows([("strong", "low")] * 3))
        self.assertEqual(facts, [])

    def test_single_occurrence_stays_below_threshold(self):
        facts = mindseam.contradiction_detection(
            rows([("strong", "low"), ("strong", "high"), ("thin", "low")]))
        self.assertEqual(facts, [])

    def test_fusion_penalty_follows_the_detector(self):
        h = rows([("shaky", "low")] * 3)
        score, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("risk-confidence contradiction" in r for r in reasons),
            reasons)


if __name__ == "__main__":
    unittest.main()
