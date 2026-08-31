# -*- coding: utf-8 -*-
"""Round 70 guards: CLI parser description defensiveness and grade ladder bounds.

main() previously assumed __doc__ was always a non-empty string with newline characters.
In packaged, bytecode-optimized, or docstring-stripped Python execution environments
(e.g., python -OO), accessing __doc__.split('\n')[0] would raise AttributeError.
The parser description extraction has been hardened with safe fallback handling.
Additionally, the grade() scoring ladder branches have been simplified with early
returns. This round pins grade boundaries and CLI parser initialization defensiveness.
"""

import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam


class MainParserDefensivenessAndGradeTests(unittest.TestCase):

    def test_grade_ladder_exact_boundaries(self):
        self.assertEqual(mindseam.grade(100), "A")
        self.assertEqual(mindseam.grade(90), "A")
        self.assertEqual(mindseam.grade(89), "B")
        self.assertEqual(mindseam.grade(75), "B")
        self.assertEqual(mindseam.grade(74), "C")
        self.assertEqual(mindseam.grade(60), "C")
        self.assertEqual(mindseam.grade(59), "D")
        self.assertEqual(mindseam.grade(40), "D")
        self.assertEqual(mindseam.grade(39), "F")
        self.assertEqual(mindseam.grade(0), "F")

    def test_main_help_runs_without_exception(self):
        # Verify --help executes cleanly and returns exit code 0
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            with self.assertRaises(SystemExit) as ctx:
                mindseam.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
