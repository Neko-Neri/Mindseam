# -*- coding: utf-8 -*-
"""Round 42 guards: the exit-code contract, end to end.

The module docstring publishes one contract: 0 means it did what you
asked, 2 means it could not — and it never exits non-zero to stop you
from working. The matrix pins every path: happy flows exit 0; refused
edits, unreadable inputs and unknown subcommands exit 2; ship findings
without --strict never change the exit code; with --strict only the
completion gate does.
"""

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

from _controller_helper import run_controller


class ExitCodeMatrixTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def test_happy_flows_exit_zero(self):
        self.assertEqual(
            run_controller(self.ws, "note", "--goal", "g", "--next", "n")
            .returncode, 0)
        self.assertEqual(
            run_controller(self.ws, "note", "--check", "it holds",
                           "--by", "n <= 6 including empty and maximum")
            .returncode, 0)
        self.assertEqual(run_controller(self.ws, "seam").returncode, 0)
        self.assertEqual(run_controller(self.ws, "resume").returncode, 0)

    def test_refused_edits_exit_two(self):
        self.assertEqual(
            run_controller(self.ws, "note", "--next", "n").returncode, 2)
        run_controller(self.ws, "note", "--goal", "g", "--next", "n")
        self.assertEqual(
            run_controller(self.ws, "note", "--check", "x", "--by", "vague")
            .returncode, 2)
        self.assertEqual(
            run_controller(self.ws, "note", "--confidence", "sure")
            .returncode, 2)

    def test_unknown_subcommand_exits_two(self):
        self.assertEqual(
            run_controller(self.ws, "teleport").returncode, 2)
        self.assertEqual(
            run_controller(self.ws, "note", "--mystery").returncode, 2)

    def test_ship_unreadable_input_exits_two(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "n")
        self.assertEqual(
            run_controller(self.ws, "ship", "no-such-file.md").returncode, 2)

    def test_ship_findings_do_not_change_the_exit_code(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "n")
        target = Path(self.ws) / "leaky.md"
        target.write_text(
            "The result is verified.\n" * 3, encoding="utf-8")
        result = run_controller(self.ws, "ship", str(target))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_ship_strict_only_enforces_the_completion_gate(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "n")
        target = Path(self.ws) / "leaky.md"
        target.write_text(
            "The result is verified.\n" * 3, encoding="utf-8")
        self.assertEqual(
            run_controller(self.ws, "ship", str(target), "--strict")
            .returncode, 0)


if __name__ == "__main__":
    unittest.main()
