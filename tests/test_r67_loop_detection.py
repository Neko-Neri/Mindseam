# -*- coding: utf-8 -*-
"""Round 27 guards: absence is not a ping-pong loop.

loop_detection counted the pair ("", "") — two consecutive entries with
no next action — as a repeated action pair, so a next-less window
emitted "Next-action loop detected ( → repeated)" and drew the fusion
layer's loop penalty. Missing actions are absence, not cycling; only
real action pairs count now. (The unused has_next flag went with it.)
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def row(i, nxt):
    return {"t": 1000 + i, "next": nxt, "verified": 0, "open": 0,
            "marker": "OPEN", "confidence": "strong", "verifier": "v",
            "risk": "low", "error": "", "outcome": "", "extra_steps": 0}


class LoopDetectionTests(unittest.TestCase):

    def test_ping_pong_loop_is_detected(self):
        h = [row(0, "a: x"), row(1, "b: y"), row(2, "a: x"),
             row(3, "b: y")]
        facts = mindseam.loop_detection(h)
        self.assertTrue(facts, facts)

    def test_repeated_same_action_is_detected(self):
        h = [row(0, "a: x"), row(1, "a: x"), row(2, "a: x")]
        facts = mindseam.loop_detection(h)
        self.assertTrue(facts, facts)

    def test_missing_nexts_are_not_a_loop(self):
        h = [row(0, ""), row(1, ""), row(2, ""), row(3, "")]
        self.assertEqual(mindseam.loop_detection(h), [])

    def test_missing_nexts_draw_no_loop_penalty(self):
        h = [row(0, ""), row(1, ""), row(2, "")]
        score, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("next-action loop" in r for r in reasons), reasons)

    def test_mixed_missing_and_real_still_detects_real_loops(self):
        h = [row(0, ""), row(1, "a: x"), row(2, ""), row(3, "a: x")]
        self.assertEqual(mindseam.loop_detection(h), [])

    def test_forward_motion_is_not_a_loop(self):
        h = [row(0, "a: 1"), row(1, "b: 2"), row(2, "c: 3"),
             row(3, "d: 4")]
        self.assertEqual(mindseam.loop_detection(h), [])


if __name__ == "__main__":
    unittest.main()
