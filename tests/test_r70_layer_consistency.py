# -*- coding: utf-8 -*-
"""Round 30 guards: the fact layer and the score layer agree on absence.

Round 14 silenced assumption_diversity in session_health_score when no
confidence tag was ever recorded — absence is confidence_presence's
signal to report, not a spread measurement to punish. The observations()
copy of the same detector stayed ungated, so a never-labelled session
read "Assumption diversity is low" in its facts while its score reasons
stayed silent: two layers, two verdicts, one input. The fact now
carries the same presence gate.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def row(i, conf="strong"):
    return {"t": 1000 + i, "next": "dom: act %d" % i, "verified": i,
            "open": 0, "marker": "OPEN", "confidence": conf,
            "verifier": "v%d" % i, "risk": "low", "error": "",
            "outcome": "ok", "extra_steps": 0}


class LayerConsistencyTests(unittest.TestCase):

    def test_label_free_history_is_silent_in_both_layers(self):
        h = [row(i, conf="") for i in range(3)]
        facts = mindseam.observations(h)
        score, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("Assumption diversity" in f for f in facts), facts)
        self.assertFalse(
            any("assumption diversity" in r.lower() for r in reasons))

    def test_uniform_labels_still_report_in_both_layers(self):
        h = [row(i, conf="thin") for i in range(3)]
        facts = mindseam.observations(h)
        score, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("Assumption diversity is low" in f for f in facts), facts)
        self.assertTrue(
            any("low assumption diversity" in r for r in reasons), reasons)

    def test_balanced_labels_are_quiet_in_both_layers(self):
        h = [row(i, conf=["strong", "thin", "shaky"][i]) for i in range(3)]
        facts = mindseam.observations(h)
        score, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("Assumption diversity" in f for f in facts), facts)
        self.assertFalse(
            any("low assumption diversity" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
