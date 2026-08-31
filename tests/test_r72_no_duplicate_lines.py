# -*- coding: utf-8 -*-
"""Round 32 guards: no reason or fact line is ever emitted twice.

The top-of-score confidence loop appended one identical line per shaky
(or thin) step, so a window with two shaky steps printed "shaky
confidence (-15)" twice (round 18 fixed this family for
verifier_independence; this was the last per-row emitter). The lines now
aggregate with a count, keeping the arithmetic identical. The sweep test
generalises the family: across a battery of diverse fixtures, no score
reason and no observation fact may appear more than once.
"""

import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def row(i, **kw):
    base = {"t": 1000 + i, "next": "dom: step %d" % i, "verified": i + 1,
            "open": 1, "marker": ["OPEN", "STEP", "DONE"][i % 3],
            "confidence": ["strong", "thin", "shaky"][i % 3],
            "verifier": "v%d" % (i % 2),
            "risk": ["low", "medium", "high"][i % 3],
            "error": "e: fail" if i % 2 else "",
            "outcome": "ok" if i % 2 else "", "extra_steps": i % 2}
    base.update(kw)
    return base

FIXTURES = {
    "mixed": [row(i) for i in range(8)],
    "degraded": [row(i, verified=0, error="db: down", risk="high",
                     confidence="shaky", next="same: x")
                 for i in range(8)],
    "sparse": [dict(row(i), marker="", confidence="", verifier="",
                    error="", outcome="", extra_steps=0)
               for i in range(8)],
    "oscillating": [row(i, confidence=["strong", "shaky"][i % 2])
                    for i in range(8)],
    "all_shaky_tail": [row(i, confidence="shaky") for i in range(8)],
    "all_thin_tail": [row(i, confidence="thin") for i in range(8)],
}


class ConfidenceAggregationTests(unittest.TestCase):

    def test_two_shaky_steps_print_one_aggregated_line(self):
        s, reasons = mindseam.session_health_score(
            [row(i, confidence="shaky") for i in range(3)])
        self.assertEqual(
            Counter(reasons)["shaky confidence x3 (-45)"], 1, reasons)

    def test_aggregation_keeps_the_arithmetic(self):
        h = [row(i, confidence="thin") for i in range(3)]
        s, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("thin confidence x3 (-15)" in r for r in reasons))

    def test_single_hit_keeps_a_simple_line(self):
        h = [row(0, confidence="strong"), row(1, confidence="thin"),
             row(2, confidence="strong")]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("thin confidence x1 (-5)" in r for r in reasons))


class NoDuplicateLineTests(unittest.TestCase):

    def test_no_score_reason_line_repeats(self):
        for name, hist in FIXTURES.items():
            _, reasons = mindseam.session_health_score(hist)
            repeats = [l for l, c in Counter(reasons).items() if c > 1]
            self.assertEqual(
                repeats, [], "%s fixture repeats reason lines: %s"
                % (name, repeats))

    def test_no_fact_line_repeats(self):
        for name, hist in FIXTURES.items():
            facts = mindseam.observations(hist)
            repeats = [l for l, c in Counter(facts).items() if c > 1]
            self.assertEqual(
                repeats, [], "%s fixture repeats fact lines: %s"
                % (name, repeats))


if __name__ == "__main__":
    unittest.main()
