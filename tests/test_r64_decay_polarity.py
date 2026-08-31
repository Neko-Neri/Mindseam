# -*- coding: utf-8 -*-
"""Round 24 guards: recovery is not decay.

Confidence decay was computed as abs(end - start) in both _fuse_run and
confidence_decay_rate, so a recovering window — shaky rising back to
strong — produced the same "confidence decay 100%" as a collapsing one.
The seam banner then printed "WARNING: confidence decay 100%" for the
sessions that were getting better, and the fusion layer penalised them
for it. Decay now fires only when confidence actually worsens; two
round-37 anchors that pinned improvement at 1.0 (using labels outside
the strong/thin/shaky vocabulary) were updated to the corrected
contract.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def step(i, conf):
    return {"t": 1000 + i, "next": "dom: act %d" % i, "verified": i + 1,
            "open": 0, "marker": "OPEN", "confidence": conf,
            "verifier": "v%d" % i, "risk": "low", "error": "",
            "outcome": "ok", "extra_steps": 0}


class DecayPolarityTests(unittest.TestCase):

    def test_worsening_is_full_decay(self):
        h = [step(0, "strong"), step(1, "thin"), step(2, "shaky")]
        self.assertEqual(mindseam.confidence_decay_rate(h), 1.0)

    def test_recovery_is_zero_decay(self):
        h = [step(0, "shaky"), step(1, "thin"), step(2, "strong")]
        self.assertEqual(mindseam.confidence_decay_rate(h), 0.0)

    def test_flat_is_zero_decay(self):
        h = [step(i, "thin") for i in range(3)]
        self.assertEqual(mindseam.confidence_decay_rate(h), 0.0)

    def test_partial_worsening_is_full_decay_by_span(self):
        # The rate is normalised by the worst level reached (span), so a
        # strong -> thin step decays fully relative to that span.
        h = [step(0, "strong"), step(1, "thin")]
        self.assertEqual(mindseam.confidence_decay_rate(h), 1.0)

    def test_two_step_worsening_from_midpoint(self):
        h = [step(0, "thin"), step(1, "shaky")]
        self.assertAlmostEqual(mindseam.confidence_decay_rate(h), 0.5)


class FuseRunPolarityTests(unittest.TestCase):

    def test_fuse_run_does_not_read_recovery_as_decay(self):
        h = [step(0, "shaky"), step(1, "thin"), step(2, "strong")]
        vol, decay, st_score, has_stall, _, _, _, _, _, _ = mindseam._fuse_run(h)
        # Round 113: this assertion used to read result[2] — the stall
        # component, always zero here — so it passed vacuously; decay
        # is the second field.
        self.assertEqual(decay, 0.0)

    def test_fuse_run_decay_is_never_negative(self):
        h = [step(0, "shaky"), step(1, "thin"), step(2, "strong")]
        vol, decay, st_score, has_stall, _, _, _, _, _, _ = mindseam._fuse_run(h)
        self.assertGreaterEqual(decay, 0.0)

    def test_fuse_run_still_reads_collapse_as_decay(self):
        h = [step(0, "strong"), step(1, "thin"), step(2, "shaky")]
        vol, decay, st, has_stall, _, _, _, _, _, _ = mindseam._fuse_run(h)
        self.assertEqual(decay, 1.0)

    def test_recovering_session_gets_no_decay_penalty(self):
        h = [step(0, "shaky"), step(1, "thin"), step(2, "strong")]
        score, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("confidence decay" in r for r in reasons), reasons)

    def test_collapsing_session_still_gets_the_decay_penalty(self):
        h = [step(0, "strong"), step(1, "thin"), step(2, "shaky")]
        score, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("confidence decay" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
