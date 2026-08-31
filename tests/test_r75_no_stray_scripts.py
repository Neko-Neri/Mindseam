# -*- coding: utf-8 -*-
"""Round 36 guards: no one-shot repair scripts ship with the tests.

The round-4 verify_suite repair session left three throwaway files in
tests/ — a string-patcher that rewrote test_mindseam.py in whatever
directory it was run from, a restore helper, and a Windows command
wrapper. Nothing referenced them; running the patcher by accident would
have corrupted the test source. They are deleted; the guard keeps
shell/batch scripts and *_fix*/_restore* patchers out of tests/ for
good.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


class NoStrayScriptsTests(unittest.TestCase):

    def test_no_shell_or_batch_scripts_in_tests(self):
        strays = [p.name for p in TESTS.iterdir()
                  if p.suffix.lower() in (".cmd", ".bat", ".sh", ".ps1")]
        self.assertEqual(strays, [], "stray scripts in tests/: %s" % strays)

    def test_one_shot_patchers_are_gone(self):
        for name in ("_fix_workspace.py", "_restore_helper.py",
                     "_run_fix.cmd"):
            self.assertFalse(
                (TESTS / name).exists(),
                "%s is a one-shot repair script and must not ship" % name)

    def test_only_tests_and_the_helper_remain(self):
        allowed_prefixes = ("test_", "_controller_helper")
        strays = [p.name for p in TESTS.glob("*.py")
                  if not p.name.startswith(allowed_prefixes)]
        self.assertEqual(strays, [], "unexpected files in tests/: %s" % strays)


if __name__ == "__main__":
    unittest.main()
