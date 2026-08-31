# -*- coding: utf-8 -*-
"""Integration tests for the new skillbook / info / discover subcommands.

Each function is reversible by design — call it, check the output, move on.
No state leaks between tests.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam
from _controller_helper import run_controller


class NewSubcommandTests(unittest.TestCase):

    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def _run(self, *args):
        return run_controller(self.ws, *args)

    # ---- skillbook ----

    def test_skillbook_empty_history_prints_message(self):
        result = self._run("skillbook")
        self.assertEqual(result.returncode, 0)
        self.assertIn("No skillbook yet", result.stdout)

    def test_skillbook_json_empty_history(self):
        result = self._run("skillbook", "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload, [])

    def test_skillbook_recurring_error_surfaced(self):
        # First seam: error appears once (below threshold), then a second
        # note repeats the same error. On the second seam it reaches the
        # minimum recurrence.  No explicit outcome → utility 0 (neutral),
        # which the extractor still surfaces (scores >= 0 pass).
        self._run("note", "--goal", "g", "--next", "dom: task")
        self._run("note", "--next", "dom: b",
                  "--error", "  net: timeout  ")
        self._run("seam")
        self._run("note", "--next", "dom: c",
                  "--error", "  net: timeout  ", "--outcome", "ok")
        self._run("seam")
        result = self._run("skillbook", "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        kinds = [e["kind"] for e in payload]
        self.assertIn("error", kinds)
        net_entries = [e for e in payload
                       if e.get("kind") == "error" and
                       "net: timeout" in e.get("text", "")]
        self.assertTrue(len(net_entries) >= 1,
                        "expected net: timeout in skillbook JSON")
        # The "ok" outcome should have lifted utility above 0.
        if net_entries:
            self.assertGreater(net_entries[0].get("utility", 0), 0)

    def test_skillbook_below_threshold_suppressed(self):
        self._run("note", "--goal", "g", "--next", "dom: task")
        self._run("note", "--next", "dom: b", "--error", "rare: only-once")
        self._run("seam")
        result = self._run("skillbook")
        self.assertEqual(result.returncode, 0)
        # Only one occurrence, below SKILLBOOK_MIN_RECURRENCE=2.
        self.assertIn("No high-utility patterns yet", result.stdout)

    # ---- info ----

    def test_info_plain_shows_history_count(self):
        # seam writes history entries; plain note calls do not.
        self._run("note", "--goal", "g", "--next", "dom: task")
        self._run("note", "--next", "dom: b")
        self._run("seam")
        result = self._run("info")
        self.assertEqual(result.returncode, 0)
        # seam appends one history entry; earlier note calls do not write history.
        self.assertIn("History: 1 entries", result.stdout)

    def test_info_json_is_valid(self):
        self._run("note", "--goal", "g", "--next", "dom: task")
        result = self._run("info", "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertIn("ledger", payload)
        self.assertIn("history_count", payload)
        self.assertIn("skillbook_entries", payload)
        self.assertIn("risk", payload)
        self.assertEqual(payload["risk"], "unknown")
        self.assertIn("meta_keys", payload)

    def test_info_reflects_goal(self):
        self._run("note", "--goal", "my goal", "--next", "dom: task")
        result = self._run("info", "--json")
        payload = json.loads(result.stdout)
        goals = payload["ledger"].get("Goal", [])
        self.assertIn("my goal", goals)

    # ---- discover ----

    def test_discover_empty_history(self):
        result = self._run("discover")
        self.assertEqual(result.returncode, 0)
        self.assertIn("No history yet", result.stdout)

    def test_discover_ranks_by_visit_count(self):
        # Each seam captures the current state as a history entry.
        self._run("note", "--goal", "g", "--next", "alpha: task")
        self._run("seam")
        self._run("note", "--next", "beta: task")
        self._run("seam")
        self._run("note", "--next", "alpha: task")
        self._run("seam")
        result = self._run("discover", "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        domains = {d["name"]: d for d in payload.get("domains", [])}
        self.assertIn("alpha", domains)
        self.assertIn("beta", domains)
        self.assertGreaterEqual(domains["alpha"]["visits"], 2)
        self.assertEqual(domains["beta"]["visits"], 1)

    def test_discover_suggests_most_visited(self):
        self._run("note", "--goal", "g", "--next", "alpha: task")
        for _ in range(4):
            self._run("note", "--next", "alpha: more")
        self._run("seam")
        result = self._run("discover")
        self.assertEqual(result.returncode, 0)
        self.assertIn("alpha", result.stdout)

    # ---- utility-aware skillbook (ACE pattern) ----

    def test_utility_negative_outcome_suppresses_pattern(self):
        # Three calls with --outcome "failed" → utility = -3 → suppressed.
        self._run("note", "--goal", "g", "--next", "dom: task")
        for _ in range(3):
            self._run("note", "--next", "dom: x",
                      "--error", "build: link error",
                      "--outcome", "failed")
            self._run("seam")
        result = self._run("skillbook")
        self.assertEqual(result.returncode, 0)
        self.assertIn("No high-utility patterns yet", result.stdout)

    def test_utility_neutral_outcome_surfaces(self):
        # Two calls with no outcome → utility = 0 (neutral, not negative).
        # Extractor allows utility >= 0, so the pattern surfaces.
        self._run("note", "--goal", "g", "--next", "dom: task")
        self._run("note", "--next", "dom: x",
                  "--error", "lint: unused var")
        self._run("seam")
        self._run("note", "--next", "dom: x",
                  "--error", "lint: unused var")
        self._run("seam")
        result = self._run("skillbook", "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        kinds = [e["kind"] for e in payload]
        self.assertIn("error", kinds)
        # Utility is 0 for a neutral outcome — still surfaced.
        lint_entries = [e for e in payload
                        if e.get("kind") == "error" and
                        "lint: unused var" in e.get("text", "")]
        self.assertTrue(len(lint_entries) >= 1)


if __name__ == "__main__":
    unittest.main()
