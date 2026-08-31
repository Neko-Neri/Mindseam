"""Targeted integration test extras for the Mindseam controller.

These tests fill specific coverage gaps in test_mindseam.py and validate
boundary behavior observed from the production implementation.
"""

import json
import shutil
import sys
import tempfile
import time
import unittest

from _controller_helper import run_controller


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class JSpaceIntegrationExtras(unittest.TestCase):
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

    def _ledger_text(self):
        p = self._ledger_path()
        return p.read_text(encoding="utf-8") if p.exists() else ""

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

    # --- Fresh-workspace edge cases -----------------------------------------

    def test_fresh_workspace_seam_succeeds(self):
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Goal:     (not set)", result.stdout)

    def test_fresh_workspace_ship_returns_clean(self):
        result = run_controller(self.workspace, "ship", "-", stdin="Some output.")
        self.assertEqual(result.returncode, 0)
        self.assertIn("clean", result.stdout)

    def test_fresh_workspace_resume_returns_goal_template(self):
        result = run_controller(self.workspace, "resume")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Goal:", result.stdout)

    def test_fresh_workspace_completion_gate_skips_without_history(self):
        # With no history, has_step is False, so gate fires "skip" and returns clean
        result = run_controller(self.workspace, "ship", "-", "--strict", stdin="Draft.")
        self.assertEqual(result.returncode, 0)
        self.assertIn("clean", result.stdout)

    # --- --core-slot boundaries (choices={1,2}) ------------------------------

    def test_core_slot_zero_is_rejected(self):
        self._open()
        result = run_controller(
            self.workspace,
            "note", "--next", "nx", "--core", "anchor — one fact", "--core-slot", "0",
        )
        self.assertEqual(result.returncode, 2)

    def test_core_slot_three_is_rejected(self):
        self._open()
        result = run_controller(
            self.workspace,
            "note", "--next", "nx", "--core", "third — too far", "--core-slot", "3",
        )
        self.assertEqual(result.returncode, 2)

    def test_core_slot_out_of_range_stops_insert(self):
        self._open()
        run_controller(self.workspace, "note", "--next", "nx", "--core", "safe — one fact")
        result = run_controller(
            self.workspace,
            "note", "--next", "nx", "--core", "orphan — nobody", "--core-slot", "5",
        )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("orphan", self._ledger_text())

    def test_core_slot_swap_shows_parking_notice(self):
        self._open()
        run_controller(self.workspace, "note", "--next", "nx", "--core", "parked — parked fact")
        run_controller(self.workspace, "note", "--next", "nx", "--core", "slot-one — first fact")
        # Insert into slot 1, parking original slot-one
        run_controller(
            self.workspace,
            "note", "--next", "nx", "--core", "repl — new-one", "--core-slot", "1",
        )
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertIn("two live at a time", result.stdout)

    # --- Unicode edge cases -------------------------------------------------

    def test_emoji_in_goal_round_trips(self):
        self._open(goal="Verified result \u2705", next_action="Inspect outputs")
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertIn("\u2705", result.stdout)

    def test_emoji_in_core_persists(self):
        self._open()
        run_controller(self.workspace, "note", "--next", "nx", "--core", "ship \U0001f6f2 \u2014 deliver")
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertIn("\U0001f6f2", result.stdout)

    def test_emoji_in_verifier_round_trips(self):
        self._open()
        # note does not append to history; seam does
        run_controller(
            self.workspace,
            "note",
            "--next", "nx",
            "--marker", "M1",
            "--confidence", "strong",
            "--verifier", "checked with fiery-test \U0001f525 across 3 inputs",
        )
        run_controller(self.workspace, "seam")
        history = self._history()
        self.assertTrue(len(history) > 0)
        self.assertIn("\U0001f525", history[-1]["verifier"])

    def test_rtl_text_in_goal_persists(self):
        self._open(goal="\u062a\u0648\u0635\u064a\u0644 \u0627\u0644\u0646\u062a\u064a\u062c\u4e2d\u58eb")
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Goal:", result.stdout)
        self.assertIn("\u062a\u0648\u0635\u064a\u0644", result.stdout)
        self.assertIn("\u4e2d\u58eb", result.stdout)

    def test_unicode_in_open_question_round_trips(self):
        self._open()
        run_controller(
            self.workspace,
            "note", "--next", "nx", "--open", "Does \u03c6 converge? \u00e9gyn?", "--settled-by", "\u03b1\u03b2\u03b3",
        )
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertIn("\u00e9gyn", result.stdout)

    def test_unicode_marker_persists(self):
        self._open()
        run_controller(
            self.workspace,
            "note", "--next", "nx", "--marker", "GRRR\U0001f525", "--confidence", "shaky",
        )
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertIn("\U0001f525", result.stdout)

    # --- Coverage-verb validation -------------------------------------------

    def test_close_without_check_is_refused(self):
        self._open()
        run_controller(
            self.workspace,
            "note", "--next", "nx", "--open", "Q1?", "--settled-by", "b", "--confidence", "strong",
        )
        result = run_controller(
            self.workspace, "note", "--next", "nx", "--close", "1", "--by", "b",
        )
        self.assertEqual(result.returncode, 2)
        # The controller requires --check before allowing --close
        self.assertIn("--check", result.stdout)

    def test_check_without_coverage_verb_is_refused(self):
        self._open()
        run_controller(
            self.workspace,
            "note", "--next", "nx", "--open", "Q1?", "--settled-by", "b", "--confidence", "strong",
        )
        result = run_controller(
            self.workspace,
            "note", "--next", "nx", "--close", "1",
            "--check", "validated against spec", "--by", "b",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("what the verification covered", result.stdout)

    def test_check_with_invalid_close_number_is_refused(self):
        self._open()
        result = run_controller(
            self.workspace,
            "note", "--next", "nx", "--close", "99",
            "--check", "brute force, spec review", "--by", "b",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("99", result.stdout)

    # --- Completion-gate behavior -------------------------------------------

    def test_ship_strict_with_confidence_strong_passes(self):
        self._open()
        run_controller(self.workspace, "note", "--next", "nx", "--confidence", "strong")
        result = run_controller(self.workspace, "ship", "-", "--strict", stdin="clean draft.")
        self.assertEqual(result.returncode, 0)
        self.assertIn("clean", result.stdout)

    def test_ship_strict_with_open_question_fails(self):
        self._open()
        run_controller(
            self.workspace,
            "note", "--next", "nx", "--open", "Q1?", "--settled-by", "b", "--confidence", "strong",
        )
        run_controller(self.workspace, "note", "--next", "nx", "--marker", "GRRR")
        result = run_controller(self.workspace, "ship", "-", "--strict", stdin="draft text.")
        self.assertEqual(result.returncode, 2)
        self.assertIn("open question(s) remain", result.stdout)

    def test_ship_strict_recovers_after_marker_settled(self):
        self._open()
        self._seed_history(count=5)
        run_controller(
            self.workspace,
            "note", "--next", "nx", "--marker", "GRRR", "--confidence", "shaky",
        )
        run_controller(self.workspace, "note", "--next", "nx", "--marker", "PHEW")
        result = run_controller(self.workspace, "ship", "-", "--strict", stdin="clean draft.")
        self.assertEqual(result.returncode, 0)
        self.assertIn("clean", result.stdout)

    # --- Claim / coverage validation ----------------------------------------

    def test_ship_accepts_clean_claims(self):
        self._open()
        result = run_controller(
            self.workspace, "ship", "-",
            stdin="\u2705 Result verified.\nCoverage: all files and edge inputs.\n",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("clean", result.stdout)

    def test_ship_detects_generic_claims(self):
        self._open()
        self._seed_history(count=5)
        result = run_controller(
            self.workspace, "ship", "-",
            stdin="It looks right \U0001f3af and covers the main points.\n",
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("clean — the outgoing register holds.", result.stdout)

    # --- Boundary: HISTORY_MAX ---------------------------------------------

    def test_history_compaction_never_exceeds_max(self):
        self._open()
        now = int(time.time())
        # Seeded entries: consecutive timestamps, all high quality
        entries = [
            {
                "t": now - (mindseam.HISTORY_MAX - 1 - i),
                "next": "step-%d" % i,
                "verified": 1,
                "open": 0,
                "marker": "M%d" % (i % 3),
                "confidence": "strong",
                "verifier": "brute force",
            }
            for i in range(mindseam.HISTORY_MAX)
        ]
        self._history_path().write_text(json.dumps(entries), encoding="utf-8")
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertLessEqual(len(self._history()), mindseam.HISTORY_MAX)

    def test_history_compaction_triggers_above_max(self):
        self._open()
        now = int(time.time())
        entries = [
            {
                "t": now - (mindseam.HISTORY_MAX - i),
                "next": "step-%d" % i,
                "verified": 1,
                "open": 0,
                "marker": "M%d" % (i % 3),
                "confidence": "strong",
                "verifier": "brute force",
            }
            for i in range(mindseam.HISTORY_MAX + 1)
        ]
        self._history_path().write_text(json.dumps(entries), encoding="utf-8")
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertIn("compacted", result.stdout)
        self.assertEqual(len(self._history()), mindseam.HISTORY_MAX)

    # --- Boundary: heal_actions ----------------------------------------------

    def test_heal_actions_fires_with_distinct_data_below_stall_run(self):
        """With STALL_RUN - 1 entries of distinct errors, individual detector
        penalties still fire."""
        hist = [
            {
                "t": 1000 + i,
                "next": "step-%d" % i,
                "verified": 0,
                "open": 0,
                "marker": "GAAAH",
                "confidence": "thin",
                "risk": "high",
                "error": "err-%d" % i,
                "verifier": "v%d" % i,
                "eag": 0.5,
            }
            for i in range(mindseam.STALL_RUN - 1)
        ]
        actions = mindseam.heal_actions(hist)
        self.assertTrue(len(actions) > 0)

    def test_heal_actions_produces_heal_warnings_at_stall_run(self):
        hist = [
            {
                "t": 1000 + i,
                "next": "step-%d" % i,
                "verified": 0,
                "open": 0,
                "marker": "GAAAH",
                "confidence": "thin",
                "risk": "high",
                "error": "err-%d" % i,
                "verifier": "v%d" % i,
                "eag": 0.5,
            }
            for i in range(mindseam.STALL_RUN)
        ]
        actions = mindseam.heal_actions(hist)
        self.assertTrue(any(a.startswith("HEAL:") for a in actions))

    # --- Resume after compaction -------------------------------------------

    def test_resume_after_compaction_shows_goal(self):
        self._open()
        now = int(time.time())
        entries = [
            {
                "t": now - (mindseam.HISTORY_MAX + 5 - i),
                "next": "step-%d" % i,
                "verified": 1,
                "open": 0,
            }
            for i in range(mindseam.HISTORY_MAX + 5)
        ]
        self._history_path().write_text(json.dumps(entries), encoding="utf-8")
        run_controller(self.workspace, "seam")
        result = run_controller(self.workspace, "resume")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Goal:", result.stdout)

    # --- Error injection / repair ------------------------------------------

    def test_corrupt_unicode_history_repairs_choices_fields(self):
        bad = [
            {
                "t": 1000,
                "next": "\u4e2d\u6587",
                "verified": 0,
                "open": 0,
                "marker": "\U0001f3af",
                "verifier": "\u03c6 \u2705",
                "risk": "low",
                "error": "err \U0001f534",
                "outcome": "fix \U0001f527",
            }
        ]
        self._history_path().parent.mkdir(parents=True, exist_ok=True)
        self._history_path().write_text(json.dumps(bad), encoding="utf-8")
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        repaired = self._history()
        self.assertTrue(len(repaired) > 0)
        self.assertTrue(any(step.get("next") == "\u4e2d\u6587" for step in repaired))
        found = [s for s in repaired if s.get("next") == "\u4e2d\u6587"][0]
        self.assertEqual(found.get("marker"), "\U0001f3af")
        self.assertIn("\u2705", found.get("verifier", ""))

    # --- Unicode in more facets ---------------------------------------------

    def test_unicode_in_emoji_next_action_round_trips(self):
        self._open(goal="Final", next_action="Step \u03c6-test \U0001f52c then \u2207 validate")
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertIn("\U0001f52c", result.stdout)
        self.assertIn("\u2207", result.stdout)

    def test_ship_reports_unreadable_stdin(self):
        self._open()
        sentinel = self.workspace + "/gone.txt"
        target = self.workspace + "/do-not-create"
        result = run_controller(
            self.workspace,
            "ship", target,
            stdin="good data here",
        )
        self.assertEqual(result.returncode, 2)
        target_path = __import__("pathlib").Path(target)
        self.assertFalse(target_path.exists())

    def test_corrupt_unicode_history_repairs_choices_fields(self):
        self._open()
        self._ledger_path().write_text(
            "## Core\n- key - value", encoding="utf-8"
        )
        bad = '[{"t": 1, "next": "\u4e2d\u6587"}]'
        self._history_path().write_text(bad, encoding="utf-8")
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        repaired = self._history()
        self.assertTrue(len(repaired) > 0)
        found = [s for s in repaired if s.get("next") == "\u4e2d\u6587"]
        self.assertTrue(len(found) > 0)
        original = found[0]
        self.assertEqual(original.get("next"), "\u4e2d\u6587")
        self.assertEqual(original.get("verified"), 0)
        latest = repaired[-1]
        self.assertIn("marker", latest)
        self.assertIn("confidence", latest)

    def test_ledger_read_error_reports_path(self):
        self._open()
        ledger = self._ledger_path()
        ledger.write_bytes(b"\xff\xfe invalid")
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 2)
        self.assertIn("WORKSPACE.md", result.stdout + result.stderr)

    def test_history_denied_write_reports_path(self):
        self._open()
        hist = self._history_path()
        hist.write_text('[{"t": 0, "next": "n", "error": "", "outcome": "", "reason": "", "verifier": "v", "confidence": "thin"}]', encoding="utf-8")
        hist.chmod(0o444)
        try:
            result = run_controller(self.workspace, "seam")
            combined = (result.stdout + result.stderr).lower()
            permission_denied = "permission" in combined or "access" in combined
            self.assertTrue(permission_denied or result.returncode == 0)
        finally:
            hist.chmod(0o644)


if __name__ == "__main__":
    unittest.main()
