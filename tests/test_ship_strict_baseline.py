"""Test the ``ship --strict`` gate borrowed from the ESLint
``--max-warnings`` / RuboCop / myPy ``--strict`` family.

``ship`` is a report, not a gate: a leak is printed and the exit code
stays zero so a human can read the report without breaking their
tooling. The r80 exit-code contract scoped ``--strict`` to the
completion gate alone — findings stay non-zero-exit observations (the
gate is what CI is allowed to enforce), so under ``--strict`` a
finding still reports and still exits 0, while a gate failure exits 2.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"


def _ship(args, text):
    return subprocess.run(
        [sys.executable, str(MINDSEAM), "ship", *args, "-"],
        input=text, capture_output=True, text=True, encoding="utf-8",
    )


class ShipStrictFlagTests(unittest.TestCase):

    def test_clean_text_exits_zero_with_or_without_strict(self):
        text = "This text is free of register leaks and claims.\n"
        for args in ([], ["--strict"]):
            r = _ship(args, text)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("clean", r.stdout)

    def test_non_strict_reports_but_does_not_fail_build(self):
        text = "Note ⇒ the inner register leaked here.\n"
        r = _ship([], text)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("── mindseam ─ ship", r.stdout)

    def test_strict_fails_build_on_inner_register_leak(self):
        text = "Note ⇒ the inner register leaked here.\n"
        r = _ship(["--strict"], text)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("── mindseam ─ ship", r.stdout)

    def test_strict_fails_build_on_state_marker(self):
        text = "Calling PHEW to settle this thread.\n"
        r = _ship(["--strict"], text)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("state markers", r.stdout)

    def test_strict_fails_build_on_uncovered_claim(self):
        text = "This is verified beyond doubt.\n"
        r = _ship(["--strict"], text)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("verified", r.stdout)

    def test_strict_fails_build_on_repetition_loop(self):
        text = "same line\nsame line\nsame line\n"
        r = _ship(["--strict"], text)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("repetition loop", r.stdout)

    def test_strict_fails_build_on_char_run(self):
        text = "before " + ("." * 30) + " after\n"
        r = _ship(["--strict"], text)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("character run", r.stdout)


if __name__ == "__main__":
    unittest.main()
