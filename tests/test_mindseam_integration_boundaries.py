"""Command boundary edge-case tests for Mindseam V3.6.

Targets invalid arguments, empty inputs, size boundaries, and missing
workspace behavior that the base integration tests do not exercise.
"""
import json
import os
import shutil
import stat
import tempfile
import time
import unittest

from _controller_helper import run_controller


class CommandBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _ledger_path(self):
        return __import__("pathlib").Path(self.workspace) / ".mindseam" / "WORKSPACE.md"

    def _history_path(self):
        return __import__("pathlib").Path(self.workspace) / ".mindseam" / "history.json"

    def _open(self, goal="Ship verified output", next_action="Inspect inputs"):
        r = run_controller(self.workspace, "note", "--goal", goal, "--next", next_action)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def _history(self):
        p = self._history_path()
        raw = p.read_text(encoding="utf-8") if p.exists() else "[]"
        return json.loads(raw)

    def _seed_history(self, count=5):
        now = int(time.time())
        entries = [
            {
                "t": now - (count - 1 - i),
                "next": "step-%d" % i,
                "verified": i % 3,
                "open": 0,
            }
            for i in range(count)
        ]
        self._history_path().parent.mkdir(parents=True, exist_ok=True)
        self._history_path().write_text(json.dumps(entries), encoding="utf-8")

    # --- cli-level negatives ------------------------------------------------

    def test_no_args_prints_help(self):
        result = run_controller(self.workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout.lower() + result.stderr.lower())

    def test_unknown_subcommand_is_refused(self):
        result = run_controller(self.workspace, "does-not-exist")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout.lower() + result.stderr.lower())

    def test_note_without_next_is_refused(self):
        result = run_controller(self.workspace, "note", "--goal", "only goal")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--next", result.stdout + result.stderr)

    def test_note_close_without_check_is_refused(self):
        self._open()
        result = run_controller(self.workspace, "note", "--close", "1", "--by", "b")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--check", result.stdout + result.stderr)

    def test_note_close_invalid_number_is_refused(self):
        self._open()
        result = run_controller(
            self.workspace,
            "note", "--close", "abc", "--check", "brute", "--by", "b",
        )
        self.assertEqual(result.returncode, 2)

    def test_ship_strict_with_open_question_fails(self):
        self._open()
        run_controller(
            self.workspace,
            "note", "--next", "nx", "--open", "Q1?", "--settled-by", "b", "--confidence", "strong",
        )
        result = run_controller(self.workspace, "ship", "-", "--strict", stdin="draft text.")
        self.assertEqual(result.returncode, 2)
        self.assertIn("open question(s) remain", result.stdout)

    # --- boundary: history/list emptiness -----------------------------------

    def test_seam_with_empty_history_returns_clean(self):
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Goal:", result.stdout)

    def test_resume_with_empty_history_returns_goal_template(self):
        result = run_controller(self.workspace, "resume")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Goal:", result.stdout)

    # --- boundary: ledger write-error reporting -----------------------------

    def test_readonly_ledger_reports_failure(self):
        self._open()
        ledger = self._ledger_path()
        ledger.write_bytes(b"\xff\xfe invalid ledger")
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 2)
        self.assertIn("WORKSPACE.md", result.stdout + result.stderr)

    # --- boundary: core-slot negatives --------------------------------------

    def test_core_slot_zero_is_rejected(self):
        self._open()
        result = run_controller(
            self.workspace,
            "note", "--next", "nx", "--core", "anchor", "--core-slot", "0",
        )
        self.assertEqual(result.returncode, 2)

    def test_core_slot_three_is_rejected(self):
        self._open()
        result = run_controller(
            self.workspace,
            "note", "--next", "nx", "--core", "anchor", "--core-slot", "3",
        )
        self.assertEqual(result.returncode, 2)

if __name__ == "__main__":
    unittest.main()
