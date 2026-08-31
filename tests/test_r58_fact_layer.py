# -*- coding: utf-8 -*-
"""Round 18 guards: fact-layer duplicates, narrow patterns and wording.

Four defects in observations(), all familiar families from earlier rounds:

  1. The confidence-trend fact used the same exact-triple pattern match
     that assess_risk used before round 15 — strong -> shaky collapsed
     undetected. Now read as ordered levels, with the remediation-keyed
     prefix kept verbatim.
  2. An all-shaky window emitted the identical line twice ("Every
     confidence tag ... has been 'shaky'"): once from the all-identical
     fact and once from the shaky-saturated fact. The second now stays
     silent when the first already said it.
  3. "no confidence tags recorded" fired at every score below 100,
     claiming total absence when only some steps lacked a tag.
  4. "1 unique verifier" was hard-coded whatever verification_depth
     returned, and error_diversity's trailing clause duplicated
     error_convergence's word for word.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def step(i, conf="strong", marker="OPEN", verifier="v", verified=0,
         nxt="dom: act %d" % 0):
    return {"t": 1000 + i, "next": nxt, "verified": verified, "open": 0,
            "marker": marker, "confidence": conf, "verifier": verifier,
            "risk": "low", "error": "", "outcome": "ok", "extra_steps": 0}


class ConfidenceTrendTests(unittest.TestCase):

    def _facts(self, labels):
        hist = [step(i, conf="strong") for i in range(3)]
        meta = {"trend": {"confidence": labels}}
        return mindseam.observations(hist, meta=meta)

    def test_graded_triple_still_reported(self):
        facts = self._facts(["strong", "thin", "shaky"])
        self.assertIn(
            "Confidence trend shows degradation: strong -> thin -> shaky.",
            facts)

    def test_collapse_pair_is_reported(self):
        facts = self._facts(["strong", "shaky"])
        self.assertIn(
            "Confidence trend shows degradation: strong -> shaky.", facts)

    def test_improving_trend_is_not_degradation(self):
        facts = self._facts(["shaky", "thin", "strong"])
        self.assertFalse(
            any("degradation" in f for f in facts), facts)

    def test_mild_single_drop_is_not_reported(self):
        facts = self._facts(["strong", "thin"])
        self.assertFalse(
            any("degradation" in f for f in facts), facts)

    def test_remediation_still_keys_on_the_prefix(self):
        facts = self._facts(["strong", "shaky"])
        out = mindseam.remediation_suggestions(facts, 80)
        self.assertIn("Confidence is degrading", " ".join(out))


class ShakyDuplicateTests(unittest.TestCase):

    def test_all_shaky_window_emits_the_line_once(self):
        hist = [step(i, conf="shaky") for i in range(3)]
        facts = mindseam.observations(hist)
        line = ("Every confidence tag in the last %d seams has been 'shaky'."
                % mindseam.STALL_RUN)
        self.assertEqual(facts.count(line), 1, facts)

    def test_mixed_window_with_three_shaky_still_reports(self):
        hist = [step(i, conf="shaky" if i >= 2 else "strong")
                for i in range(5)]
        facts = mindseam.observations(hist, run=hist)
        self.assertTrue(
            any("has been 'shaky'" in f for f in facts), facts)


class WordingAccuracyTests(unittest.TestCase):

    def test_partial_confidence_presence_does_not_claim_total_absence(self):
        hist = [step(0, conf=""), step(1, conf=""), step(2, conf="strong")]
        facts = mindseam.observations(hist)
        line = next((f for f in facts if "Confidence presence" in f), None)
        self.assertIsNotNone(line, facts)
        self.assertIn("some steps carry no confidence tag", line)
        self.assertNotIn("no confidence tags recorded", line)

    def test_verification_depth_quotes_its_real_number(self):
        hist = [step(i, verified=1, verifier="") for i in range(3)]
        facts = mindseam.observations(hist)
        line = next((f for f in facts if "Verification depth" in f), None)
        self.assertIsNotNone(line, facts)
        self.assertIn("(0 unique verifier name(s))", line)

    def test_error_diversity_clause_differs_from_convergence(self):
        hist = [step(i, verified=0, verifier="") for i in range(4)]
        for h in hist:
            h["error"] = "same: failure"
        facts = mindseam.observations(hist)
        conv = [f for f in facts if f.startswith("Error convergence")]
        div = [f for f in facts if f.startswith("Error diversity")]
        clauses = {f.split(";", 1)[1] if ";" in f else f
                   for f in conv + div}
        self.assertEqual(len(clauses), len(conv) + len(div),
                         "two detectors share one trailing clause: %s"
                         % (conv + div,))


if __name__ == "__main__":
    unittest.main()
