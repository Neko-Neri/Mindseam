"""Fuzz pattern_persistence: old vs new implementation must agree.

The rolling-accelerator rewrite of pattern_persistence has to remain
semantically identical to the original segment-by-segment re-scan for
every history shape the seam encounters. Fuzz against the original by
treating the original as the oracle; the new implementation is what the
controller actually calls.
"""

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def _original_pattern_persistence(hist, run=None):
    """The pre-round-154 implementation, kept as an oracle for fuzzing."""
    if not hist or len(hist) < mindseam.STALL_RUN:
        return "none"
    if run is None:
        run = hist[-mindseam.STALL_RUN:]

    def window_issues(seg):
        issues = set()
        unique_nexts = {h.get("next") for h in seg if h.get("next")}
        verifieds = {h.get("verified", 0) for h in seg}
        if len(unique_nexts) <= 1 and unique_nexts:
            issues.add("stall")
        if len(verifieds) == 1:
            issues.add("frozen")
        if any(h.get("risk") in ("medium", "high") for h in seg):
            issues.add("risk")
        if any(h.get("confidence") in ("thin", "shaky") for h in seg):
            issues.add("confidence")
        return frozenset(issues)

    current_issues = window_issues(run)
    if not current_issues:
        return "none"
    step = max(1, mindseam.STALL_RUN // 2)
    earlier_segments = [hist[i:i + mindseam.STALL_RUN]
                        for i in range(0, len(hist) - mindseam.STALL_RUN, step)]
    if not earlier_segments:
        return "transient"
    persistent_count = sum(1 for seg in earlier_segments
                          if window_issues(seg) & current_issues)
    ratio = persistent_count / float(len(earlier_segments))
    return "chronic" if ratio >= 0.5 else "transient"


def _random_history(rng, length):
    rows = []
    for _ in range(length):
        rows.append({
            "next": rng.choice(["a: x", "b: y", "c: z", "", "same: s"]),
            "verified": rng.randint(0, 8),
            "open": rng.randint(0, 2),
            "risk": rng.choice(["low", "medium", "high", "", "low"]),
            "confidence": rng.choice(["strong", "thin", "shaky", "", "thin"]),
            "marker": rng.choice(["OPEN", "DONE", "PHEW", ""]),
            "verifier": rng.choice(["pytest exit 0", "", "manual"]),
            "error": rng.choice(["io: x", "", "parse: y"]),
            "outcome": rng.choice(["ok", "", "failed"]),
            "extra_steps": rng.choice([0, 0, 1, 3]),
        })
    return rows


class PatternPersistenceFuzzTests(unittest.TestCase):

    def test_roll_matches_original_on_random_histories(self):
        rng = random.Random(0xC0DE)
        for length in (3, 4, 5, 8, 16, 32, 64, 128, 250, 500, 1000):
            hist = _random_history(rng, length)
            new = mindseam.pattern_persistence(hist)
            old = _original_pattern_persistence(hist)
            self.assertEqual(new, old,
                             "length=%d new=%r old=%r" % (length, new, old))

    def test_roll_matches_original_when_run_is_explicit(self):
        rng = random.Random(0xFEEDBEEF)
        hist = _random_history(rng, 200)
        run = hist[-mindseam.STALL_RUN:]
        self.assertEqual(mindseam.pattern_persistence(hist, run=list(run)),
                         _original_pattern_persistence(hist, run=run))

    def test_roll_matches_original_on_all_chronic_history(self):
        hist = [{"next": "stalled", "verified": 0, "risk": "high",
                 "confidence": "shaky"} for _ in range(40)]
        self.assertEqual(mindseam.pattern_persistence(hist), "chronic")
        self.assertEqual(mindseam.pattern_persistence(hist),
                         _original_pattern_persistence(hist))

    def test_roll_matches_original_on_clean_history(self):
        hist = [{"next": "step %d" % i, "verified": i,
                 "risk": "low", "confidence": "strong"}
                for i in range(40)]
        self.assertEqual(mindseam.pattern_persistence(hist), "none")
        self.assertEqual(mindseam.pattern_persistence(hist),
                         _original_pattern_persistence(hist))

    def test_roll_matches_original_on_boundary_history(self):
        # length exactly at STALL_RUN, at 2 * STALL_RUN, at 2 * STALL_RUN + 1
        for length in (mindseam.STALL_RUN,
                       mindseam.STALL_RUN * 2,
                       mindseam.STALL_RUN * 2 + 1):
            hist = _random_history(random.Random(length), length)
            self.assertEqual(mindseam.pattern_persistence(hist),
                             _original_pattern_persistence(hist),
                             "length=%d" % length)


if __name__ == "__main__":
    unittest.main()
