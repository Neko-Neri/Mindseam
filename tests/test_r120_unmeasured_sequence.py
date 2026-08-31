# -*- coding: utf-8 -*-
"""Round 48 guards: a sequence nobody wrote is not stagnant.

The differential sweep (rounds 45-47 removed three phantom bonuses;
this round asked the mirror question again on a fresh axis) fed the
fusion table a healthy session and single-dimension absence variants
and compared net deltas. The no-marker variant scored 16 points above
the healthy baseline. Two faces were responsible, and one was a real
defect:

  marker_transition_diversity built its transitions from raw marker
  strings, so an unmarked window produced zero transitions and returned
  0 — absence read as the worst score. The fusion layer printed
  "marker sequence stagnant 0/100 -3" and heal_actions prescribed the
  OPEN→DONE→PHEW ladder for a sequence that was never written, the
  round-14 absence-punishment class in two more layers. Blank-to-marked
  pairs were also counted as transitions, so one marker plus gaps read
  as progression (100). The detector now reads recorded markers only:
  fewer than two return the unmeasured sentinel 100, identical recorded
  markers are genuine stagnation, and the penalty face carries the
  marker_pair_in_run presence flag the bonus face already uses.

Not defects, settled by the same sweep: "repeated marker -10" and
"marker stall" fire only on markers actually written twice in a row
(uniform recorded phases are the designed signal), and verify-then-act
credit for blank-marker windows is a real measurement because an
unmarked seam is open work by default.
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
           "verified": i + 1, "open": 0, "marker": "",
           "confidence": "strong", "verifier": "pytest -q exits 0 #%d" % i,
           "risk": "low", "error": "", "outcome": "ok",
           "extra_steps": 0}
    row.update(kw)
    return row


class UnmeasuredSequenceTests(unittest.TestCase):

    def test_unmarked_window_is_unmeasured(self):
        h = [seam(i) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.marker_transition_diversity(h), 100)

    def test_unmarked_session_takes_no_stagnation_penalty(self):
        h = [seam(i) for i in range(mindseam.STALL_RUN * 2)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("marker sequence stagnant" in r for r in reasons), reasons)

    def test_unmarked_session_gets_no_marker_heal_line(self):
        h = [seam(i) for i in range(mindseam.STALL_RUN)]
        actions = mindseam.heal_actions(h, book=None)
        self.assertFalse(
            any("No marker transitions" in a for a in actions), actions)

    def test_one_marker_plus_gaps_is_not_progression(self):
        # Blank-to-marked pairs are not transitions: one recorded marker
        # with gaps is an unmeasured sequence, not a diverse one.
        h = [seam(0, marker="OPEN"), seam(1), seam(2)]
        self.assertEqual(mindseam.marker_transition_diversity(h), 100)

    def test_repeated_recorded_marker_is_stagnant(self):
        h = [seam(i, marker="OPEN") for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.marker_transition_diversity(h), 0)
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("marker sequence stagnant" in r for r in reasons), reasons)
        actions = mindseam.heal_actions(h, book=None)
        self.assertTrue(
            any("No marker transitions" in a for a in actions), actions)

    def test_repeated_marker_with_gap_stays_stagnant(self):
        # OPEN, blank, OPEN: the recorded sequence never changed.
        h = [seam(0, marker="OPEN"), seam(1), seam(2, marker="OPEN")]
        self.assertEqual(mindseam.marker_transition_diversity(h), 0)

    def test_real_transitions_still_score_full(self):
        h = [seam(0, marker="OPEN"), seam(1, marker="CHECKPOINT"),
             seam(2, marker="DONE")]
        self.assertEqual(mindseam.marker_transition_diversity(h), 100)

    def test_recording_markers_no_longer_scores_below_not_recording(self):
        # The sweep's inversion: canonical transitions must not score
        # below the same session with markers erased.
        def net(reasons):
            total = 100
            import re
            for line in reasons:
                total += sum(int(x) for x in re.findall(r"([+-]\d+)", line))
            return total
        marked = [seam(0, marker="OPEN"), seam(1), seam(2, marker="CHECKPOINT"),
                  seam(3), seam(4), seam(5, marker="DONE")]
        unmarked = [dict(m, marker="") for m in marked]
        net_marked = net(mindseam.session_health_score(marked).reasons)
        net_unmarked = net(mindseam.session_health_score(unmarked).reasons)
        self.assertGreaterEqual(net_marked, net_unmarked)


if __name__ == "__main__":
    unittest.main()
