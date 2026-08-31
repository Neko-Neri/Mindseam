# -*- coding: utf-8 -*-
"""Round 46 guards: stability praise needs stable something.

The round-45 blank-bucket probe re-ran a never-verified session through
the fusion table and one ungated bonus face remained: verification_
regression answers 100 whenever the cumulative verified count never
drops — including when it never rose either, because the detector
deliberately measures temporal stability "rather than its presence or
quality" (its docstring; presence belongs to verification_coverage and
friends). The bonus face printed "stable verification 100/100 +5" for a
window where verification never appeared — praise for stability of
nothing, the phantom-bonus class rounds 12-14 gated everywhere else.
The sibling verification factors already carry the same gate (vtb on
verified6, incomplete_verification on verified_in_run), so the bonus
now requires the same flag: at least one check in the detector's
window. The penalty face stays ungated because a score at or below 25
mathematically requires a drop to exist.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def seam(i, **kw):
    row = {"t": 1000000 + i * 600,
           "next": "dom%d: act on item %d" % (i, i),
           "verified": 0, "open": 0, "marker": "STEP",
           "confidence": "", "verifier": "v%d" % i,
           "risk": "low", "error": "", "outcome": "",
           "extra_steps": 0}
    row.update(kw)
    return row


class StableVerificationGateTests(unittest.TestCase):

    def test_never_verified_window_earns_no_stability_bonus(self):
        h = [seam(i) for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("stable verification" in r for r in reasons), reasons)

    def test_detector_still_calls_the_window_stable(self):
        # The scalar itself is unchanged: no drops is 100, by design.
        h = [seam(i) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.verification_regression(h), 100)

    def test_climbing_checks_keep_the_bonus(self):
        h = [seam(i, verified=10 + i) for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("stable verification" in r for r in reasons), reasons)

    def test_plateau_with_real_checks_keeps_the_bonus(self):
        h = [seam(i, verified=5) for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("stable verification" in r for r in reasons), reasons)

    def test_earlier_checks_then_silence_still_qualify(self):
        # verified is cumulative: a window holding carried-over checks
        # measures real verification even when none were added.
        h = [seam(i, verified=5 if i == 0 else 5)
             for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("stable verification" in r for r in reasons), reasons)

    def test_regression_penalty_needs_no_gate(self):
        h = [seam(0, verified=5), seam(1, verified=2),
             seam(2, verified=6)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("verification regression" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
