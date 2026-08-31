# -*- coding: utf-8 -*-
"""Round 54 guards: meta carries only keys something reads back.

mode_seam computed a health dict into meta["health"] on every seam,
and write_meta silently dropped it: "health" is not in
METACOGNITION_KEYS, nothing ever read meta["health"] (the trend line
prints from the local variables), no test or document ever saw a
persisted health key, and no such key was ever written to disk. Dead
data plumbing — the meta equivalent of round 38's unplugged monitors.
The assignment is deleted; these tests pin the contract it obscured:

  * a seam persists exactly METACOGNITION_KEYS, never a health blob;
  * the score still reaches the user through the trend line;
  * the temporal detectors' ordering contract, verified while the
    seam flow was under the microscope: ascending regular cadence is
    clean, descending timestamps are a discontinuity, burst recording
    is irregular, and internally consistent future clocks (a skewed
    host) stay clean because cadence, not wall time, is the signal.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam
from _controller_helper import run_controller


def seam(t, **kw):
    row = {"t": t, "next": "dom: act %d" % (t % 97), "verified": 1,
           "open": 0, "marker": "OPEN", "confidence": "strong",
           "verifier": "pytest -q", "risk": "low", "error": "",
           "outcome": "ok", "extra_steps": 0}
    row.update(kw)
    return row


class MetaCarriesOnlyReadKeysTests(unittest.TestCase):

    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def test_seam_persists_only_known_meta_keys(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "dom: a")
        run_controller(self.ws, "seam")
        meta = json.loads(
            (Path(self.ws) / ".mindseam" / "metacognition.json")
            .read_text(encoding="utf-8"))
        # Persisted keys are a subset of the schema — a seam writes only
        # the keys it has values for — and never anything else.
        self.assertLessEqual(
            set(meta), set(mindseam.METACOGNITION_KEYS) | {"schema_version"},
            meta)
        self.assertNotIn("health", meta)

    def test_score_still_prints_in_the_trend_line(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "dom: a")
        result = run_controller(self.ws, "seam")
        self.assertRegex(result.stdout, r"score: \d+/100 \([A-F]\)")


class TemporalOrderingContractTests(unittest.TestCase):

    def setUp(self):
        self.now = int(time.time())

    def test_ascending_regular_cadence_is_clean(self):
        h = [seam(self.now - 3000 + 600 * i) for i in range(6)]
        self.assertEqual(mindseam.temporal_regularity(h), 100)
        self.assertEqual(mindseam.temporal_continuity(h), 100)
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("temporal" in r for r in reasons), reasons)

    def test_descending_timestamps_are_a_discontinuity(self):
        h = [seam(self.now - 600 * i) for i in range(6)]
        self.assertEqual(mindseam.temporal_continuity(h), 0)
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("temporal discontinuity" in r for r in reasons), reasons)

    def test_burst_recording_is_irregular(self):
        now = self.now
        h = [seam(t) for t in
             (now - 5000, now - 4990, now - 100, now - 90, now - 80, now)]
        self.assertLess(mindseam.temporal_regularity(h), 30)

    def test_internally_consistent_future_clock_stays_clean(self):
        # A skewed host clock is regular work; cadence is the signal.
        h = [seam(self.now + 300000 + 600 * i) for i in range(6)]
        self.assertEqual(mindseam.temporal_regularity(h), 100)
        self.assertEqual(mindseam.temporal_continuity(h), 100)


if __name__ == "__main__":
    unittest.main()
