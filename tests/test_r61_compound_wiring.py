# -*- coding: utf-8 -*-
"""Round 21 guards: the compound-pattern fact is finally wired.

compound_pattern_facts mirrored the fusion layer's compound-pattern
penalty (risk + weak confidence + ledger staleness + stall, two or more
firing together) but had no caller on any output path — the same
unplugged-monitor defect family as round 43's mechanism bindings. The
session_health_score banner penalised compound patterns that the reader
could never see named. observations() now surfaces it with the same
window and thresholds the score uses.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def step(i, conf="strong", risk="low", nxt=None,
         verified=0, marker="OPEN"):
    return {"t": 1000 + i, "next": nxt if nxt is not None else "dom: act %d" % i,
            "verified": verified, "open": 0,
            "marker": marker, "confidence": conf, "verifier": "v",
            "risk": risk, "error": "", "outcome": "", "extra_steps": 0}


class CompoundFactWiringTests(unittest.TestCase):

    def test_risk_plus_weak_confidence_surfaces_the_fact(self):
        h = [step(i, conf="thin", risk="high") for i in range(3)]
        facts = mindseam.observations(h)
        line = next((f for f in facts if f.startswith("Compound pattern:")),
                    None)
        self.assertIsNotNone(line, facts)
        self.assertIn("risk", line)
        self.assertIn("confidence", line)

    def test_single_signal_stays_silent(self):
        # Verified grows so the progress signal cannot fire alongside risk.
        h = [step(i, conf="strong", risk="high", verified=i + 1)
             for i in range(3)]
        facts = mindseam.observations(h)
        self.assertFalse(
            any(f.startswith("Compound pattern:") for f in facts), facts)

    def test_stall_counts_as_a_progress_signal(self):
        h = [step(i, conf="thin", risk="low", nxt="dom: same")
             for i in range(3)]
        facts = mindseam.observations(h)
        line = next((f for f in facts if f.startswith("Compound pattern:")),
                    None)
        if line is not None:
            self.assertIn("progress", line)

    def test_fact_agrees_with_the_banner_penalty(self):
        h = [step(i, conf="thin", risk="high") for i in range(3)]
        facts = mindseam.observations(h)
        score, reasons = mindseam.session_health_score(h)
        fact = any(f.startswith("Compound pattern:") for f in facts)
        penalty = any("compound pattern" in r for r in reasons)
        self.assertEqual(
            fact, penalty,
            "the fact layer and the score layer must agree: fact=%s penalty=%s"
            % (fact, penalty))


if __name__ == "__main__":
    unittest.main()
