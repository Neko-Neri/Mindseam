# -*- coding: utf-8 -*-
"""Round 78 guards: pattern_persistence set comprehension and chronic pattern contracts.

pattern_persistence classifies whether detected cognitive anomalies (stalls, frozen
progress, high risk, weak confidence) represent chronic failure modes or transient noise.
The issue extraction helper and window comparison loop have been refactored with clean
set comprehensions and generator expression sums, removing manual flag variables and
nested accumulators. This round pins chronic persistence detection across historical
windows, transient noise classification, and clean session contracts.
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


class PatternPersistenceComprehensionTests(unittest.TestCase):

    def test_pattern_persistence_clean_history_returns_none(self):
        # Diverse next actions, advancing verifications, low risk, strong confidence
        hist = [
            {"verified": 1, "risk": "low", "confidence": "strong", "next": "step 1"},
            {"verified": 2, "risk": "low", "confidence": "strong", "next": "step 2"},
            {"verified": 3, "risk": "low", "confidence": "strong", "next": "step 3"},
        ]
        self.assertEqual(mindseam.pattern_persistence(hist), "none")

    def test_pattern_persistence_transient_single_window(self):
        # Clean early history, but a stall issue in the latest window
        hist = [
            {"verified": 1, "risk": "low", "confidence": "strong", "next": "step 1"},
            {"verified": 2, "risk": "low", "confidence": "strong", "next": "step 2"},
            {"verified": 3, "risk": "low", "confidence": "strong", "next": "step 3"},
            {"verified": 3, "risk": "low", "confidence": "strong", "next": "stalled"},
            {"verified": 3, "risk": "low", "confidence": "strong", "next": "stalled"},
            {"verified": 3, "risk": "low", "confidence": "strong", "next": "stalled"},
        ]
        self.assertEqual(mindseam.pattern_persistence(hist), "transient")

    def test_pattern_persistence_chronic_across_multiple_windows(self):
        # Repeated stall across multiple historical windows
        hist = [
            {"verified": 0, "risk": "high", "confidence": "shaky", "next": "stalled"},
            {"verified": 0, "risk": "high", "confidence": "shaky", "next": "stalled"},
            {"verified": 0, "risk": "high", "confidence": "shaky", "next": "stalled"},
            {"verified": 0, "risk": "high", "confidence": "shaky", "next": "stalled"},
            {"verified": 0, "risk": "high", "confidence": "shaky", "next": "stalled"},
            {"verified": 0, "risk": "high", "confidence": "shaky", "next": "stalled"},
        ]
        self.assertEqual(mindseam.pattern_persistence(hist), "chronic")


if __name__ == "__main__":
    unittest.main()
