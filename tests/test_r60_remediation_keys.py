# -*- coding: utf-8 -*-
"""Round 20 guards: every load-bearing fact has a remediation key.

Round 6 (defect 14) removed remediation keys that could never match an
emitted fact. The mirror gap went unexamined: facts that observations()
emits on every stalled session — the two detect_stall lines, the
inaccessible-outcomes line, the unverified-core line — had no key at all,
so the sessions most in need of advice received none. Four keys now
cover them; the existing keys and the per-fact single-match rule are
unchanged.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


class NewKeyTests(unittest.TestCase):

    def test_frozen_next_action_gets_advice(self):
        out = mindseam.remediation_suggestions(
            ["Next action has not changed for 3 seams."], 80)
        self.assertTrue(any("has not moved" in s for s in out), out)

    def test_frozen_verification_gets_advice(self):
        out = mindseam.remediation_suggestions(
            ["No new verification across the last 3 seams."], 80)
        self.assertTrue(any("--check" in s for s in out), out)

    def test_inaccessible_outcomes_get_advice(self):
        out = mindseam.remediation_suggestions(
            ["Verified outcomes are inaccessible (3/3 entries); results cannot be audited."],
            80)
        self.assertTrue(any("--outcome" in s for s in out), out)

    def test_unverified_core_gets_advice(self):
        out = mindseam.remediation_suggestions(
            ["2 core item(s) have gone unverified across 8 seams."], 80)
        self.assertTrue(any("oldest core item" in s for s in out), out)

    def test_end_to_end_stalled_session_receives_suggestions(self):
        h = [{"t": 1000 + i, "next": "dom: same action", "verified": 0,
              "open": 1, "marker": "OPEN", "confidence": "thin",
              "verifier": "v", "risk": "low", "error": "", "outcome": "",
              "extra_steps": 0}
             for i in range(3)]
        facts = mindseam.observations(h)
        self.assertTrue(facts)
        out = mindseam.remediation_suggestions(facts, 60)
        self.assertTrue(out, "a stalled session must not get an empty list")


class ExistingBehaviourTests(unittest.TestCase):

    def test_escalation_key_still_matches(self):
        out = mindseam.remediation_suggestions(
            ["Risk escalated across recent seams: low -> high."], 80)
        self.assertTrue(any("Risk is climbing" in s for s in out), out)

    def test_one_suggestion_per_fact(self):
        fact = ("Next action has not changed for 3 seams. "
                "Stall severity is high (70/100).")
        out = mindseam.remediation_suggestions([fact], 80)
        self.assertEqual(len(out), 1, out)

    def test_unmatched_fact_yields_nothing(self):
        self.assertEqual(
            mindseam.remediation_suggestions(["Something unrelated."], 80), [])


if __name__ == "__main__":
    unittest.main()
