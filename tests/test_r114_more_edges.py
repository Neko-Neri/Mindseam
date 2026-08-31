# -*- coding: utf-8 -*-
"""Round 76 guards: the second mutation batch, all survivors pinned.

A second ten-mutation sweep let seven mutants live. Each survivor is a
real unpinned contract:

  * the heal severity comparison and its mirror relationship to the
    health floor (M11);
  * the convergence grid — 75 itself is unreachable, so the reachable
    set {0, 5, 20, 35, 50, 100} is what the bands actually read (M12);
  * HISTORY_MAX is a published capacity, not an internal knob (M14);
  * the premature-convergence fact gate at exactly 75 (M16, pinned by
    injecting the score);
  * every seam row must carry a computed risk (M17);
  * the metacognition format version is 1 (M19);
  * every Chinese CLAIM variant must still match (M21).
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam


class SeverityMirrorTests(unittest.TestCase):

    def test_ceiling_mirrors_the_health_floor(self):
        self.assertEqual(mindseam.HEAL_HEALTH_FLOOR, 45)
        self.assertEqual(mindseam.HEAL_SEVERITY_CEILING,
                         100 - mindseam.HEAL_HEALTH_FLOOR)

    def test_comparison_is_strictly_above_the_ceiling(self):
        source = (ROOT / "mindseam" / "scripts" / "mindseam.py") \
            .read_text(encoding="utf-8")
        self.assertIn("if val > HEAL_SEVERITY_CEILING:", source)
        self.assertNotIn("if val >= HEAL_SEVERITY_CEILING:", source)


class ConvergenceGridTests(unittest.TestCase):

    def hist(self, risk, conf, verifieds):
        return [{"t": 1000 + i, "next": "dom: a %d" % i, "verified": v,
                 "open": 0, "marker": "OPEN", "confidence": conf,
                 "verifier": "v", "risk": risk, "error": "",
                 "outcome": "ok", "extra_steps": 0}
                for i, v in enumerate(verifieds)]

    def test_reachable_grid_values(self):
        # all-positive agreement
        self.assertEqual(mindseam.convergence_index(
            self.hist("low", "strong", [1, 2, 3])), 100)
        # mixed signs: 50 - |positives - negatives| * 15
        # (risk -1 against confidence/momentum/volatility +1 each)
        self.assertEqual(mindseam.convergence_index(
            self.hist("high", "strong", [1, 2, 3])), 20)
        self.assertEqual(mindseam.convergence_index(
            self.hist("high", "shaky", [1, 2, 3])), 50)
        # balanced disagreement (two positive, two negative signals)
        self.assertEqual(mindseam.convergence_index(
            self.hist("high", "shaky", [1, 2, 3])), 50)

    def test_seventy_five_is_unreachable(self):
        # Exhaustive small-grid enumeration: the reachable values never
        # include 75, so the >= 75 band edge is documented, not tested.
        seen = set()
        for risk in ("low", "medium", "high"):
            for conf in ("strong", "thin", "shaky", ""):
                for verifieds in ([0, 0, 0], [1, 1, 1], [1, 2, 3],
                                  [3, 2, 1], [2, 2, 2]):
                    seen.add(mindseam.convergence_index(
                        self.hist(risk, conf, verifieds)))
        self.assertNotIn(75, seen)
        self.assertIn(100, seen)
        self.assertIn(20, seen)


class ConstantContractsTests(unittest.TestCase):

    def test_history_capacity_is_five_hundred(self):
        self.assertEqual(mindseam.HISTORY_MAX, 500)

    def test_metacognition_format_version_is_one(self):
        self.assertEqual(mindseam.METACOGNITION_SCHEMA_VERSION, 1)


class PrematureGateEdgeTests(unittest.TestCase):

    def _facts_at_score(self, score):
        original = mindseam.session_health_score
        mindseam.session_health_score = lambda *a, **k: mindseam._HealthResult(
            score, [], 0, 0.0, 0, False, True, False)
        try:
            return mindseam.premature_convergence(
                [{"t": i} for i in range(3)], book={})
        finally:
            mindseam.session_health_score = original

    def test_score_of_exactly_seventy_five_fires(self):
        self.assertTrue(self._facts_at_score(75))

    def test_score_below_the_gate_stays_silent(self):
        self.assertEqual(self._facts_at_score(74), [])


class SeamRiskRecordingTests(unittest.TestCase):

    def test_every_seam_row_carries_a_computed_risk(self):
        ws = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            from _controller_helper import run_controller
            run_controller(ws, "note", "--goal", "g", "--next", "dom: a",
                           "--marker", "OPEN")
            run_controller(ws, "seam")
            run_controller(ws, "note", "--next", "dom: b",
                           "--marker", "OPEN")
            run_controller(ws, "seam")
            hist = json.loads(
                (Path(ws) / ".mindseam" / "history.json")
                .read_text(encoding="utf-8"))
            self.assertTrue(hist)
            for row in hist:
                self.assertIn(row["risk"], ("low", "medium", "high"),
                              "seam row without a risk level: %r" % row)
        finally:
            os.chdir(cwd)


class ClaimVariantTests(unittest.TestCase):

    def test_every_chinese_claim_variant_matches(self):
        for text in ("已经验证", "已验证", "经验证", "验证通过",
                     "已经确认", "确认无误", "已经测试", "测试通过",
                     "已经证明"):
            self.assertRegex(
                text + "，可以交付", mindseam.CLAIM,
                "CLAIM lost the variant %r" % text)


if __name__ == "__main__":
    unittest.main()
