# -*- coding: utf-8 -*-
"""Round 56 guards: the CLI rejects what it cannot honour.

argparse guards the shape of every invocation before any state is
touched: core slots are the choices (1, 2), --close and --extra-steps
must be integers, ship requires a file argument, and a subcommand is
mandatory. Every rejection exits 2 (argparse's convention) and —
critically — happens before the ledger or history is read or written.
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


class ArgparseSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)

    def tearDown(self):
        os.chdir(self.cwd)

    def test_core_slot_choices_are_enforced(self):
        self.assertEqual(
            run_controller(self.ws, "note", "--core", "a — b",
                           "--core-slot", "3").returncode, 2)
        self.assertEqual(
            run_controller(self.ws, "note", "--core", "a — b",
                           "--core-slot", "0").returncode, 2)
        self.assertEqual(
            run_controller(self.ws, "note", "--core", "a — b",
                           "--core-slot", "two").returncode, 2)

    def test_integer_flags_reject_text(self):
        self.assertEqual(
            run_controller(self.ws, "note", "--close", "one").returncode, 2)
        self.assertEqual(
            run_controller(self.ws, "note", "--extra-steps", "many")
            .returncode, 2)

    def test_ship_requires_a_file(self):
        self.assertEqual(run_controller(self.ws, "ship").returncode, 2)

    def test_a_subcommand_is_required(self):
        self.assertEqual(run_controller(self.ws).returncode, 2)

    def test_rejection_leaves_no_state_behind(self):
        run_controller(self.ws, "note", "--core", "a — b",
                       "--core-slot", "9")
        run_controller(self.ws, "note", "--close", "one")
        self.assertFalse(
            (Path(self.ws) / ".mindseam").exists(),
            "a rejected invocation must not create .mindseam state")


if __name__ == "__main__":
    unittest.main()
