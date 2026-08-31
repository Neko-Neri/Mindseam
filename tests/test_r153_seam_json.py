# -*- coding: utf-8 -*-
"""Round 153 guards: `seam --json` mirrors the printed report machine-readably.

The seam is the controller's recurring user-facing surface, and skillbook,
info and discover already carried --json faces; the seam alone printed text
only, so a host that wanted the facts, the health score or the heal lines
had to scrape prose. The JSON face is a contract like the text face: valid
JSON, the same sections under stable keys, a score consistent with its own
grade, and identical state side effects — a seam that renders JSON must
still append history, persist meta and extract the skillbook.
"""

import json
import os
import re
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

from _controller_helper import run_controller

import mindseam


class SeamJsonTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)
        run_controller(self.ws, "note", "--goal", "feed hosts a json seam",
                       "--next", "dom: first action")

    def tearDown(self):
        os.chdir(self.cwd)

    def _note_and_json_seam(self, count):
        payload = None
        for i in range(count):
            run_controller(self.ws, "note", "--next", "dom: action %d" % i,
                           "--marker", "OPEN", "--confidence", "strong",
                           "--verifier", "manual run %d including output" % i)
            r = run_controller(self.ws, "seam", "--json")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            payload = json.loads(r.stdout)
        return payload

    def test_json_is_valid_and_sections_are_stable(self):
        payload = self._note_and_json_seam(3)
        for key in ("ledger", "history_count", "facts", "state_repairs",
                    "telemetry", "trend", "remediation", "heal"):
            self.assertIn(key, payload)
        self.assertIn("goal", payload["ledger"])
        self.assertIn("next", payload["ledger"])
        self.assertIn("score", payload["trend"])
        for key in ("value", "grade", "factors"):
            self.assertIn(key, payload["trend"]["score"])
        self.assertEqual(payload["telemetry"].get("marker"), "OPEN")

    def test_json_score_is_consistent_with_its_grade(self):
        payload = self._note_and_json_seam(3)
        value = payload["trend"]["score"]["value"]
        self.assertIsInstance(value, int)
        self.assertTrue(0 <= value <= 100)
        self.assertEqual(payload["trend"]["score"]["grade"], mindseam.grade(value))

    def test_json_history_count_tracks_the_seam(self):
        payload = self._note_and_json_seam(3)
        self.assertEqual(payload["history_count"], 3)

    def test_json_seam_still_records_state(self):
        history_path = Path(self.ws) / ".mindseam" / "history.json"
        # `note` opens the ledger but appends no history; the file first
        # appears at the seam.
        before = (len(json.loads(history_path.read_text(encoding="utf-8")))
                  if history_path.exists() else 0)
        run_controller(self.ws, "note", "--next", "dom: second action",
                       "--marker", "OPEN", "--confidence", "strong")
        r = run_controller(self.ws, "seam", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        after = len(json.loads(history_path.read_text(encoding="utf-8")))
        self.assertEqual(after, before + 1)
        self.assertTrue((Path(self.ws) / ".mindseam" / "skillbook.md").exists())
        meta = json.loads(
            (Path(self.ws) / ".mindseam" / "metacognition.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(meta.get("marker"), "OPEN")

    def test_default_seam_output_is_not_json(self):
        run_controller(self.ws, "note", "--next", "dom: action 0")
        r = run_controller(self.ws, "seam")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("── mindseam ─ seam", r.stdout)
        self.assertFalse(r.stdout.lstrip().startswith("{"))

    def test_long_gap_json_reports_without_the_reentry_banner(self):
        run_controller(self.ws, "note", "--next", "dom: action 0")
        r0 = run_controller(self.ws, "seam")
        self.assertEqual(r0.returncode, 0, r0.stdout + r0.stderr)
        history_path = Path(self.ws) / ".mindseam" / "history.json"
        hist = json.loads(history_path.read_text(encoding="utf-8"))
        hist[-1]["t"] = int(time.time()) - 2 * mindseam.RESUME_GAP
        history_path.write_text(json.dumps(hist), encoding="utf-8")
        r = run_controller(self.ws, "seam", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["long_gap"])
        self.assertGreaterEqual(payload["gap_minutes"], mindseam.RESUME_GAP // 60)
        self.assertNotIn("── mindseam ─ seam (long gap", r.stdout)

    def test_json_warnings_flag_a_missing_next(self):
        ledger = Path(self.ws) / ".mindseam" / "WORKSPACE.md"
        text = ledger.read_text(encoding="utf-8")
        ledger.write_text(
            re.sub(r"## Next\n.+", "## Next\n", text),
            encoding="utf-8")
        r = run_controller(self.ws, "seam", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload.get("warnings"), ["next action is not set"])
        self.assertIsNone(payload["ledger"]["next"])


if __name__ == "__main__":
    unittest.main()
