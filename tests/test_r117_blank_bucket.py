# -*- coding: utf-8 -*-
"""Round 45 guards: an unrecorded confidence tag is absence, not a level.

The zero-pole audit (audit_r13_zero_pole.py, folded into this round and
deleted) asked three questions about score components that sit at 0 for
clean sessions. Two were the suite's designed verification pressure and
are pinned here as settled; one was a real inversion:

  assumption_diversity built its buckets from ``h.get("confidence",
  "unknown")``, but append_history always writes the key — with the empty
  string when no tag was recorded. The "unknown" default never fired, so
  blanks formed a real bucket. One honest "strong" plus two untagged
  seams scored 91/100 and earned "high assumption diversity +5" — praise
  for a spread that was never recorded, the same phantom-bonus class
  rounds 12-14 eliminated. Blanks are now dropped before the bucket
  count, matching the presence idiom both score-layer and fact-layer
  gates already use.

Settled as designed, not defects:

  * tension_resolution returns 0 for a tension-free window whose verified
    count never moves. Its docstring lists stalls among tension signals,
    and detect_stall reports a flat verified count — so the window does
    carry tension: verification debt. The score-layer penalty is the
    suite's intended push to record checks.
  * adaptability_score stays 0 for a clean session (no risk, no stall,
    no verification growth) because every component needs a problem to
    respond to or a check to grow. A session that records nothing has
    produced no adaptability evidence; the penalty overlaps the
    verification-absence signals by design, like the other pressure
    faces kept live after the round-14 audit.
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


class BlankBucketInversionTests(unittest.TestCase):
    """A missing tag must not inflate the measured spread."""

    def test_one_tag_plus_blanks_is_not_high_diversity(self):
        h = [seam(0, confidence="strong"), seam(1), seam(2)]
        self.assertEqual(mindseam.assumption_diversity(h), 0)

    def test_blanks_never_earn_the_diversity_bonus(self):
        h = [seam(0, confidence="strong"), seam(1), seam(2)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("high assumption diversity" in r for r in reasons), reasons)

    def test_two_same_tags_plus_blank_stay_uniform(self):
        h = [seam(0, confidence="strong"), seam(1, confidence="strong"),
             seam(2)]
        self.assertEqual(mindseam.assumption_diversity(h), 0)

    def test_whitespace_and_missing_keys_read_as_blank(self):
        spaces = [seam(0, confidence="strong"), seam(1, confidence="  "),
                  seam(2)]
        self.assertEqual(mindseam.assumption_diversity(spaces), 0)
        absent = [{"t": 1000 + i, "next": "d: a%d" % i, "verified": 0,
                   "open": 0, "marker": "", "verifier": "", "risk": "low",
                   "error": "", "outcome": "", "extra_steps": 0}
                  for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.assumption_diversity(absent), 0)

    def test_recorded_spreads_keep_their_score(self):
        balanced = [seam(i, confidence=c)
                    for i, c in enumerate(["strong", "thin", "shaky"])]
        two_level = [seam(i, confidence=c)
                     for i, c in enumerate(["strong", "strong", "thin"])]
        self.assertGreaterEqual(mindseam.assumption_diversity(balanced), 80)
        self.assertGreaterEqual(mindseam.assumption_diversity(two_level), 80)

    def test_uniform_recorded_profile_keeps_its_penalty(self):
        h = [seam(i, confidence="thin") for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("low assumption diversity" in r for r in reasons), reasons)


class SettledZeroPolesStayTests(unittest.TestCase):
    """The audit's two non-defects, pinned so they are not re-opened."""

    def test_verification_debt_reads_as_unresolved_tension(self):
        # Docstring contract: stalls are tension signals, and a flat
        # verified count is a stall fact. Moving-but-never-verifying
        # work must not read as resolved.
        h = [seam(i) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.tension_resolution(h), 0)

    def test_verified_growth_reads_as_resolved(self):
        h = [seam(i, verified=i + 1) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.tension_resolution(h), 100)

    def test_clean_session_records_no_adaptability_evidence(self):
        # No risk to descend from, no stall to break out of, no
        # verification growth: every component is unreachable by design.
        h = [seam(i) for i in range(mindseam.STALL_RUN * 2)]
        self.assertEqual(mindseam.adaptability_score(h), 0)

    def test_verification_growth_is_reachable_adaptability(self):
        h = [seam(i, verified=i) for i in range(mindseam.STALL_RUN)]
        self.assertGreater(mindseam.adaptability_score(h), 0)


if __name__ == "__main__":
    unittest.main()
