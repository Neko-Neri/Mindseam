# -*- coding: utf-8 -*-
"""Round 10 guards: fusion reason attribution.

The +/- symmetry audit of session_health_score found no double- or
miss-counting between the bonus and penalty faces (overlapping lenses
such as error_convergence vs error_diversity are granularity, not
duplication). What it did find were two reason-label collisions that
made printed numbers unattributable to their detector:

- error_convergence's healthy side emitted "error diversity N/100 +3",
  borrowing the name of the unrelated error_diversity detector whose
  own healthy line prints right next to it with a different number;
- verification_completion_ratio emitted "incomplete verification",
  the exact label incomplete_verification uses on its own heavier
  (-5 vs -3) penalty, so a reader could not tell which detector
  produced the number.

These tests pin unique attribution: every reason number must be
traceable to exactly one detector vocabulary.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def seam(i, nxt=None, verifier=None, verified=0, error=""):
    if verifier is None:
        verifier = "v%d" % i
    return {"t": 1000000 + i * 600,
            "next": nxt if nxt is not None else "task%d:act" % i,
            "verified": verified, "open": 1, "marker": "OPEN",
            "confidence": "thin", "verifier": verifier, "risk": "low",
            "error": error, "outcome": "", "extra_steps": 0}


class R50ReasonAttributionTests(unittest.TestCase):
    """One label, one detector — printed numbers must be attributable."""

    def test_error_convergence_bonus_keeps_its_own_name(self):
        # Real, mutually distinct error events: both error-lens bonuses
        # are earned by measurement (round-12 sentinel gates silence the
        # zero-error phantom that used to carry this assertion).
        h = [seam(i, error="e%d:err" % i)
             for i in range(mindseam.STALL_RUN + 1)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(any("errors spread across domains" in r for r in reasons))
        diversity_lines = [r for r in reasons if "error diversity" in r]
        self.assertEqual(len(diversity_lines), 1)
        self.assertIn("+5", diversity_lines[0])

    def _mixed_history(self):
        """iv fires on verified>0 seams lacking outcomes; vcr fires on
        verifier-set seams with verified==0. Two started-but-unconcluded
        verifications plus one concluded-but-unreported step put both
        detectors below threshold together."""
        return [seam(0, verified=0, verifier="a0"),
                seam(1, verified=0, verifier="a1"),
                seam(2, verified=1, verifier="")]

    def test_completion_ratio_no_longer_shares_incomplete_label(self):
        score, reasons = mindseam.session_health_score(self._mixed_history())
        self.assertTrue(any("verifications left open" in r for r in reasons),
                        reasons)
        incomplete_lines = [r for r in reasons if "incomplete verification" in r]
        self.assertEqual(len(incomplete_lines), 1)
        self.assertIn("-5", incomplete_lines[0])

    def test_both_detectors_can_fire_without_label_merge(self):
        # The fusion face may clamp back to 100 via unrelated bonuses
        # (recorded saturation design, ledger ✓28); the contract here is
        # attribution, so pin each label's own number and weight.
        _, reasons = mindseam.session_health_score(self._mixed_history())
        labels = " | ".join(reasons)
        self.assertIn("incomplete verification 0/100 -5", labels)
        self.assertIn("verifications left open 0/100 -3", labels)


if __name__ == "__main__":
    unittest.main()
