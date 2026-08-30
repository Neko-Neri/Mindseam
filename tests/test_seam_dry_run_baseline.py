"""Test ``seam --dry-run``: borrow the ``kubectl apply --dry-run`` /
``terraform plan`` / ``npm install --dry-run`` family of preview
flags.

The dry-run variant runs the seam's analysis but skips the
``append_history`` call, so ``.jspace/history.json`` does not gain a
row. This lets a CI hook or pre-commit pipeline preview what a seam
would record without committing the row, which is the canonical
use of the dry-run pattern across infra tools.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSPACE = ROOT / "j-space" / "scripts" / "jspace.py"


def _invoke(args, cwd):
    return subprocess.run(
        [sys.executable, str(JSPACE), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
    )


class SeamDryRunFlagTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _open_ledger(self, goal="dry-run demo", nxt="dom: first action"):
        r = _invoke(
            ["note", "--goal", goal, "--next", nxt], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_dry_run_does_not_create_history_json(self):
        self._open_ledger()
        # No prior seam has been recorded, so .jspace/history.json
        # does not exist yet. A regular seam would create it; the
        # dry-run must not.
        r = _invoke(["seam", "--dry-run"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("dry-run: history.json was not updated", r.stdout)
        self.assertFalse(
            (Path(self.workspace) / ".jspace" / "history.json").exists())

    def test_dry_run_does_not_grow_existing_history(self):
        self._open_ledger()
        # Materialise a single history row.
        r = _invoke(["seam", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        history = Path(self.workspace) / ".jspace" / "history.json"
        before = json.loads(history.read_text(encoding="utf-8"))
        self.assertEqual(len(before), 1)

        r = _invoke(["seam", "--dry-run"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        after = json.loads(history.read_text(encoding="utf-8"))
        self.assertEqual(len(after), 1)
        self.assertEqual(after, before)

    def test_dry_run_can_be_repeated_without_growing_state(self):
        self._open_ledger()
        for _ in range(3):
            r = _invoke(["seam", "--dry-run"], cwd=self.workspace)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(
            (Path(self.workspace) / ".jspace" / "history.json").exists())

    def test_dry_run_combined_with_json_still_emits_payload(self):
        self._open_ledger()
        r = _invoke(["seam", "--dry-run", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        # The JSON contract still holds under dry-run: ledger,
        # history_count, facts, trend, warnings are all present.
        for key in ("ledger", "history_count", "facts",
                    "trend", "warnings"):
            self.assertIn(key, payload)
        # And the warning line announces the dry-run state so a host
        # can detect that no row was written.
        self.assertIn(
            "dry-run: history.json was not updated",
            payload.get("warnings", []),
        )

    def test_dry_run_still_runs_observations_facts(self):
        # Build a history with three stalled rows (enough to satisfy
        # STALL_RUN = 3) and confirm the dry-run still surfaces the
        # stalled-next-action fact even though it does not write a
        # new row.
        self._open_ledger()
        for _ in range(3):
            r = _invoke(["note", "--next", "dom: stalled"], cwd=self.workspace)
            self.assertEqual(r.returncode, 0, r.stderr)
            r = _invoke(["seam", "--json"], cwd=self.workspace)
            self.assertEqual(r.returncode, 0, r.stderr)
        r = _invoke(["seam", "--dry-run"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The dry-run text output must surface the same observations
        # that a real seam would, even though no new row is written.
        self.assertIn("dry-run: history.json was not updated", r.stdout)
        self.assertIn("Your next action has been the same", r.stdout)

    def test_dry_run_does_not_emit_dry_run_marker_under_real_seam(self):
        # A real seam must never print the dry-run line; otherwise
        # the side effect is invisible and the report lies.
        self._open_ledger()
        r = _invoke(["seam"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("dry-run: history.json was not updated", r.stdout)


if __name__ == "__main__":
    unittest.main()
