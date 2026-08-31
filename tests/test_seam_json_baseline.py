"""Test the ``seam --json`` machine-readable output added on top of the
baseline controller.

The baseline Mindseam controller ships with a text-only ``seam`` subcommand.
This test pins the new ``--json`` flag, which borrows the standard
CLI pattern from ``gh --json``, ``cargo --message-format json`` and
``aws --output json``: text and JSON are two faces of the same data,
not two separate products. The JSON face in baseline exposes the
ledger, the recent history summary, the observations facts and the
gap signal — it does not depend on the detector layer that lives in
later rounds.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"


def _invoke(args, cwd):
    return subprocess.run(
        [sys.executable, str(MINDSEAM), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
    )


class SeamJsonFlagTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _open_ledger(self, goal="ship the json seam", nxt="dom: first action"):
        result = _invoke(
            ["note", "--goal", goal, "--next", nxt], cwd=self.workspace)
        self.assertEqual(result.returncode, 0,
                         "stderr=%s" % result.stderr)

    def test_seam_json_emits_valid_json(self):
        self._open_ledger()
        result = _invoke(["seam", "--json"], cwd=self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIsInstance(payload, dict)

    def test_seam_json_section_keys_are_stable(self):
        self._open_ledger()
        result = _invoke(["seam", "--json"], cwd=self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        for key in ("ledger", "history_count", "long_gap",
                    "gap_minutes", "facts", "trend", "warnings"):
            self.assertIn(key, payload)
        self.assertIn("goal", payload["ledger"])
        self.assertIn("next", payload["ledger"])
        self.assertIn("open", payload["ledger"])
        self.assertEqual(payload["ledger"]["goal"], "ship the json seam")
        self.assertEqual(payload["ledger"]["next"],
                         "dom: first action")
        self.assertIsNone(payload["ledger"]["verified_last"])
        self.assertEqual(payload["ledger"]["verified_count"], 0)

    def test_default_seam_output_is_not_json(self):
        self._open_ledger()
        result = _invoke(["seam"], cwd=self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("── mindseam ─ seam", result.stdout)
        self.assertFalse(result.stdout.lstrip().startswith("{"))

    def test_seam_json_history_count_grows(self):
        self._open_ledger()
        for index in range(2):
            result = _invoke(
                ["note", "--next", "dom: step %d" % index], cwd=self.workspace)
            self.assertEqual(result.returncode, 0, result.stderr)
            r = _invoke(["seam", "--json"], cwd=self.workspace)
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assertEqual(payload["history_count"], index + 1)

    def test_seam_json_emits_warning_when_next_missing(self):
        self._open_ledger()
        ledger = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        text = ledger.read_text(encoding="utf-8")
        ledger.write_text(re.sub(r"## Next\n.+", "## Next\n", text),
                          encoding="utf-8")
        r = _invoke(["seam", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["warnings"],
                         ["next action is not set"])
        self.assertIsNone(payload["ledger"]["next"])

    def test_seam_json_still_records_state(self):
        self._open_ledger()
        history = Path(self.workspace) / ".mindseam" / "history.json"
        before = (len(json.loads(history.read_text(encoding="utf-8")))
                  if history.exists() else 0)
        r = _invoke(["seam", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        after = json.loads(history.read_text(encoding="utf-8"))
        self.assertEqual(len(after), before + 1)

    def test_long_gap_json_reports_long_gap_field(self):
        self._open_ledger()
        # A bare `note` does not yet create history.json — the seam is
        # what appends the first row. Run a JSON seam once to materialise
        # the file, then rewind the timestamps to a pre-gap era.
        _invoke(["seam", "--json"], cwd=self.workspace)
        history = Path(self.workspace) / ".mindseam" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        for row in data:
            row["t"] = 0  # ancient, far past RESUME_GAP
        history.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(["seam", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["long_gap"])
        self.assertGreaterEqual(payload["gap_minutes"], 30)


if __name__ == "__main__":
    unittest.main()
