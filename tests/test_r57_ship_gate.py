# -*- coding: utf-8 -*-
"""Round 17 guards: the ship repetition detectors and the ship path.

mode_ship scans outgoing text for two repetition signatures: a line
repeated three times or more, and a single character run of 20 or more.
The character-run regex demanded 21 characters before firing while its
message — and its intent — said 20, so a 20-character degenerate run
shipped clean. The ship branch in main() also read the ledger twice;
the second read was dead weight and is gone.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

BOOK = {"Goal": ["g"], "Core": [], "Verified": [], "Open": [],
        "Next": ["n"]}


class CharacterRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_history = mindseam.HISTORY
        self.old_ledger = mindseam.LEDGER_DIR
        mindseam.LEDGER_DIR = self.tmp.name
        mindseam.HISTORY = str(Path(self.tmp.name) / "history.json")

    def tearDown(self):
        mindseam.HISTORY = self.old_history
        mindseam.LEDGER_DIR = self.old_ledger
        self.tmp.cleanup()

    def _ship(self, text):
        import io
        import contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = mindseam.mode_ship(dict(BOOK), text)
        return code, out.getvalue()

    def test_twenty_character_run_is_flagged(self):
        code, out = self._ship("all good except this: " + "…" * 20)
        self.assertIn("character run of 20 or more", out)

    def test_nineteen_character_run_is_not_flagged(self):
        code, out = self._ship("dense but human: " + "-" * 19)
        self.assertNotIn("character run", out)

    def test_twenty_one_still_flagged(self):
        code, out = self._ship("worse: " + "'" * 21)
        self.assertIn("character run of 20 or more", out)

    def test_clean_text_stays_clean(self):
        code, out = self._ship("A normal report with normal density.")
        self.assertIn("clean", out)


class LineRepetitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_history = mindseam.HISTORY
        self.old_ledger = mindseam.LEDGER_DIR
        mindseam.LEDGER_DIR = self.tmp.name
        mindseam.HISTORY = str(Path(self.tmp.name) / "history.json")

    def tearDown(self):
        mindseam.HISTORY = self.old_history
        mindseam.LEDGER_DIR = self.old_ledger
        self.tmp.cleanup()

    def _ship(self, text):
        import io
        import contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            mindseam.mode_ship(dict(BOOK), text)
        return out.getvalue()

    def test_three_identical_lines_are_flagged(self):
        out = self._ship("one\none\none\n")
        self.assertIn("a line repeats three times", out)

    def test_two_identical_lines_are_not_flagged(self):
        out = self._ship("one\none\ntwo\n")
        self.assertNotIn("a line repeats", out)

    def test_fenced_repetition_is_ignored(self):
        out = self._ship("intro\n```\nspam\nspam\nspam\n```\n")
        self.assertNotIn("a line repeats", out)


if __name__ == "__main__":
    unittest.main()
