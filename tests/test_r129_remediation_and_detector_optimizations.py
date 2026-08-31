# -*- coding: utf-8 -*-
"""Round 57 guards: remediation map constant and detector clean state.

remediation_suggestions previously allocated and sorted its key dictionary
on every call, and detectors such as verification_freshness, detect_stall,
and stall_score contained unused intermediate variables. REMEDIATION_MAP
is now hoisted as a pre-sorted module-level constant tuple, and all detector
implementations are streamlined to avoid redundant variable allocation and
dead code paths while maintaining exact output parity. This round pins the
remediation lookup contracts and detector calculation accuracy.
"""

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


class RemediationAndDetectorOptimizationsTests(unittest.TestCase):

    def test_remediation_map_constant_integrity(self):
        self.assertTrue(hasattr(mindseam, "REMEDIATION_MAP"))
        self.assertIsInstance(mindseam.REMEDIATION_MAP, tuple)
        self.assertGreaterEqual(len(mindseam.REMEDIATION_MAP), 8)
        # Each item is a (key, advice, priority) triple — the third field
        # was added in round 155 so ``remediation_suggestions`` can sort by
        # severity. The key and advice fields are still non-empty strings.
        for item in mindseam.REMEDIATION_MAP:
            self.assertEqual(len(item), 3)
            key, advice, priority = item
            self.assertIsInstance(key, str)
            self.assertIsInstance(advice, str)
            self.assertIsInstance(priority, int)
            self.assertTrue(key)
            self.assertTrue(advice)
        # Priority values must be unique so the severity ordering is total.
        priorities = [item[2] for item in mindseam.REMEDIATION_MAP]
        self.assertEqual(len(priorities), len(set(priorities)),
                         "duplicate priorities in REMEDIATION_MAP: %s"
                         % priorities)

    def test_remediation_suggestions_matches_all_keys(self):
        for key, expected_advice, _priority in mindseam.REMEDIATION_MAP:
            fact = f"Alert: {key} detected in session."
            suggestions = mindseam.remediation_suggestions([fact], 80)
            self.assertIn(expected_advice, suggestions, f"Key '{key}' failed to match in remediation_suggestions")

    def test_verification_freshness_direct_scoring(self):
        # Empty history
        self.assertEqual(mindseam.verification_freshness([]), 100)

        # Stale run: no verifier and no verified
        stale_run = [{"next": f"step {i}", "verified": 0, "verifier": ""} for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.verification_freshness(stale_run), 0)

        # Fresh run: with verifier
        fresh_run = [{"next": f"step {i}", "verified": 1, "verifier": "v1"} for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.verification_freshness(fresh_run), 100)

    def test_detect_stall_consistency(self):
        # Run where next action doesn't move
        hist = [{"next": "same action", "verified": 1} for _ in range(mindseam.STALL_RUN)]
        facts = mindseam.detect_stall(hist)
        self.assertTrue(any("Next action has not changed" in f for f in facts))
        self.assertTrue(any("No new verification" in f for f in facts))

        # Run with progression
        hist_prog = [{"next": f"action {i}", "verified": i + 1} for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.detect_stall(hist_prog), [])

    def test_stall_score_consistency(self):
        hist_flat = [{"next": "action", "verified": 1} for _ in range(mindseam.STALL_RUN)]
        score = mindseam.stall_score(hist_flat)
        self.assertGreaterEqual(score, 70)

        hist_moving = [{"next": f"action {i}", "verified": i + 1} for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.stall_score(hist_moving), 0)


if __name__ == "__main__":
    unittest.main()
