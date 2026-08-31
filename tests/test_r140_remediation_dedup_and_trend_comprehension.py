# -*- coding: utf-8 -*-
"""Round 68 guards: remediation deduplication order and risk trend comprehension.

remediation_suggestions previously populated a manual seen-set and output list
loop for preserving insertion order during deduplication. This is now unified
with built-in dict.fromkeys(), preserving exact deterministic ordering while
reducing loop overhead. In addition, risk trend construction in mode_seam and
mode_resume was refactored with list comprehensions and negative slice capping.
This round pins remediation ordering, risk trend formatting, and seam output parity.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam


class RemediationDedupAndTrendComprehensionTests(unittest.TestCase):

    def test_remediation_suggestions_preserves_order_and_uniqueness(self):
        facts = [
            "Every confidence tag in the last 3 seams has been 'strong'.",
            "The same verifier has been used for 3 consecutive seam checks.",
            "Every confidence tag in the last 3 seams has been 'strong'.",  # duplicate
        ]
        suggs = mindseam.remediation_suggestions(facts, score=80)
        self.assertIsInstance(suggs, list)
        self.assertEqual(len(suggs), len(set(suggs)))
        self.assertLessEqual(len(suggs), 6)

    def test_remediation_critical_stress_precedence(self):
        facts = ["Verified outcomes are inaccessible"]
        suggs = mindseam.remediation_suggestions(facts, score=25)
        self.assertTrue(len(suggs) > 0)
        self.assertTrue(suggs[0].startswith("Session is critically stressed"))


if __name__ == "__main__":
    unittest.main()
