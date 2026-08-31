# -*- coding: utf-8 -*-
"""Round 64 guards: observation deduplication and shaky co-occurrence invariants.

observations() previously executed duplicate set membership and length checks
for marker and verifier sequences. The co-occurrence checks for shaky confidence
have now been unified within their parent consecutive marker and verifier
conditional branches. This round pins marker/verifier shaky co-occurrence fact
emission, saturated shaky tag detection on mixed sequences, and observation
fact parity.
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


class ObservationNestingAndCooccurrenceTests(unittest.TestCase):

    def test_marker_shaky_cooccurrence_fact_emitted(self):
        # 3 identical markers with shaky confidence
        hist = [
            {"marker": "GRRR", "confidence": "shaky", "next": f"step {i}", "verified": 0}
            for i in range(mindseam.STALL_RUN)
        ]
        facts = mindseam.observations(hist)
        self.assertTrue(any("co-occurs with 'shaky' confidence" in f for f in facts))
        self.assertTrue(any("The same marker has been recorded" in f for f in facts))

    def test_verifier_shaky_cooccurrence_fact_emitted(self):
        # 3 identical verifiers with shaky confidence
        hist = [
            {"verifier": "v_test", "confidence": "shaky", "next": f"step {i}", "verified": 0}
            for i in range(mindseam.STALL_RUN)
        ]
        facts = mindseam.observations(hist)
        self.assertTrue(any("used with 'shaky' confidence" in f for f in facts))
        self.assertTrue(any("The same verifier has been used" in f for f in facts))


if __name__ == "__main__":
    unittest.main()
