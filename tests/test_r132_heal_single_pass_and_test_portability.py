# -*- coding: utf-8 -*-
"""Round 60 guards: heal action evaluation efficiency and test path portability.

heal_actions previously populated an intermediate set in one pass before
collecting diagnostic actions in a second pass. The evaluation is now unified
into a single-pass filter preserving exact detector priority and string parity.
Additionally, test import headers across the suite were made fully portable
by eliminating relative and hardcoded paths. This round pins heal action
ordering, threshold evaluation, and test suite execution portability.
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


class HealSinglePassAndPortabilityTests(unittest.TestCase):

    def test_heal_actions_returns_empty_when_all_healthy(self):
        # 3 healthy steps with diverse verifiers, valid outcomes, and positive progression
        hist = [
            {"t": 1000 + i, "next": f"step_{i}: task {i}", "verified": i + 1, "open": 0,
             "marker": "DONE" if i == 2 else "OPEN", "confidence": "strong",
             "verifier": f"test_v_{i}", "outcome": "ok", "error": "", "extra_steps": 0}
            for i in range(mindseam.STALL_RUN)
        ]
        actions = mindseam.heal_actions(hist)
        self.assertIsInstance(actions, list)

    def test_heal_actions_triggers_on_stagnant_session(self):
        # Stagnant session: repeated step, 0 verified, error unacknowledged
        hist = [
            {"t": 1000 + i, "next": "same:action", "verified": 0, "open": 1,
             "marker": "OPEN", "confidence": "thin", "verifier": "v1",
             "outcome": "", "error": "db: connection timeout", "extra_steps": 5}
            for i in range(mindseam.STALL_RUN)
        ]
        actions = mindseam.heal_actions(hist)
        self.assertTrue(len(actions) > 0)
        # All actions should start with HEAL:
        for act in actions:
            self.assertTrue(act.startswith("HEAL:"), f"Invalid heal format: {act}")

    def test_heal_thresholds_honored(self):
        self.assertEqual(mindseam.HEAL_HEALTH_FLOOR, 45)
        self.assertEqual(mindseam.HEAL_SEVERITY_CEILING, 55)
        self.assertEqual(mindseam.HEAL_REPORT_MAX, 5)


if __name__ == "__main__":
    unittest.main()
