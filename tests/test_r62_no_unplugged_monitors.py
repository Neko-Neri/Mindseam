# -*- coding: utf-8 -*-
"""Round 22 guards: no unplugged monitors, no duplicated fact code.

An AST sweep of mindseam.py found four functions with no call site on any
output path — the round-43 defect family ("a detector existed, was
correct, and was never reachable from a real command"):

  - detect_volatility duplicated line for line by an inline copy inside
    observations(); the named detector is now the one that runs.
  - error_recovery_depth never surfaced anywhere; it now reports as an
    observations fact when error exits are single-step.
  - extra_steps_monotonicity rewarded ever-increasing unplanned
    sub-steps — wiring it would have added a harmful signal, so the dead
    detector is deleted instead.
  - book_action_alignment measured the same plan alignment as two live
    detectors and is deleted.

The first test re-runs the sweep so the family cannot quietly return.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

SOURCE_PATH = ROOT / "mindseam" / "scripts" / "mindseam.py"


def step(i, conf="strong", error="", verified=0):
    return {"t": 1000 + i, "next": "dom: act %d" % i, "verified": verified,
            "open": 0, "marker": "OPEN", "confidence": conf,
            "verifier": "v", "risk": "low", "error": error,
            "outcome": "", "extra_steps": 0}


class NoUnpluggedMonitorsTests(unittest.TestCase):

    def test_every_function_has_a_live_call_site(self):
        src = SOURCE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        unplugged = []
        for name in names:
            uses = len(re.findall(r"\b%s\b" % re.escape(name), src)) - 1
            if uses <= 0:
                unplugged.append(name)
        self.assertEqual(
            unplugged, [],
            "functions with no call site (unplugged monitors or dead "
            "code): %s" % unplugged)


class VolatilityWiringTests(unittest.TestCase):

    def test_oscillation_fact_still_emitted_via_the_named_detector(self):
        h = [step(0, conf="strong"), step(1, conf="thin"),
             step(2, conf="shaky")]
        facts = mindseam.observations(h)
        self.assertTrue(
            any("Confidence oscillated" in f for f in facts), facts)

    def test_stable_confidence_emits_nothing(self):
        h = [step(i, conf="strong") for i in range(3)]
        facts = mindseam.observations(h)
        self.assertFalse(
            any("oscillated" in f for f in facts), facts)


class RecoveryDepthWiringTests(unittest.TestCase):

    def test_single_step_error_exit_is_reported(self):
        h = [step(0, error="db: down"), step(1), step(2), step(3),
             step(4), step(5)]
        facts = mindseam.observations(h)
        self.assertTrue(
            any("Error recovery is shallow" in f for f in facts), facts)

    def test_extended_recovery_chain_is_not_reported(self):
        h = [step(0, error="db: down"), step(1, error="db: down"),
             step(2, error="db: down"), step(3), step(4), step(5)]
        facts = mindseam.observations(h)
        self.assertFalse(
            any("Error recovery is shallow" in f for f in facts), facts)


class DeadDetectorsGoneTests(unittest.TestCase):

    def test_removed_detectors_are_gone(self):
        self.assertFalse(hasattr(mindseam, "extra_steps_monotonicity"))
        self.assertFalse(hasattr(mindseam, "book_action_alignment"))


if __name__ == "__main__":
    unittest.main()
