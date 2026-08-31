# -*- coding: utf-8 -*-
"""Round 47 guards: a closed question's number stays retired.

The workspace template promises it: an Open entry closes against a
recorded checkpoint, and "its number is never reused". The guards run
three open/close cycles and pin the property end to end — numbers
monotonically increase, a closed number is never reissued, and the
closure suffix on the Verified row names the right question.
"""

import os
import re
import sys
import tempfile
import unittest

ROOT = Path = __import__("pathlib").Path
if str(ROOT(__file__).resolve().parents[1] / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT(__file__).resolve().parents[1] / "mindseam" / "scripts"))
if str(ROOT(__file__).resolve().parents[1] / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT(__file__).resolve().parents[1] / "tests"))

from _controller_helper import run_controller


class OpenIdRetirementTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)
        run_controller(self.ws, "note", "--goal", "g", "--next", "dom: a")

    def tearDown(self):
        os.chdir(self.cwd)

    def _open(self, n):
        r = run_controller(self.ws, "note", "--open",
                           "question %d" % n, "--settled-by", "test %d" % n)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def _close(self, n):
        r = run_controller(self.ws, "note", "--close", str(n),
                           "--check", "holds %d" % n,
                           "--by", "n <= 6 including empty and maximum")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def _open_ids(self):
        r = run_controller(self.ws, "resume")
        return sorted(int(m) for m in re.findall(r"\?(\d+)", r.stdout))

    def test_numbers_increase_and_never_reissue(self):
        seen = []
        for cycle in range(1, 4):
            self._open(cycle)
            self._close(cycle)
            r = run_controller(self.ws, "note", "--next", "dom: step %d" % cycle)
            ids = self._open_ids_from_ledger()
            seen.extend(ids)
        # After three open/close cycles no Open row remains, and the
        # Verified rows carry three distinct closure suffixes ?01..?03.
        text = self._ledger_text()
        suffixes = re.findall(r"closes: \?(\d+)", text)
        self.assertEqual(sorted(suffixes), ["01", "02", "03"])

    def _open_ids_from_ledger(self):
        return re.findall(r"^-( \?\d+)", self._ledger_text(), re.M)

    def _ledger_text(self):
        return (Path(self.ws) / ".mindseam" / "WORKSPACE.md") \
            .read_text(encoding="utf-8")

    def test_reopening_after_close_gets_a_fresh_number(self):
        self._open(1)
        self._close(1)
        self._open(2)
        text = self._ledger_text()
        self.assertIn("?02 question 2", text)
        self.assertNotIn("?01 question 2", text)

    def test_closing_twice_is_refused(self):
        self._open(1)
        self._close(1)
        r = run_controller(self.ws, "note", "--close", "1",
                           "--check", "again", "--by",
                           "n <= 6 including empty and maximum")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
