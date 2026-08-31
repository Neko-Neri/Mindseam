# -*- coding: utf-8 -*-
"""Round 28 guards: the closure suffix is not part of the verifier's name.

A Verified row closed against an Open question ends with the reserved
" — closes: ?NN" bookkeeping. last_verifier split on " — verified by: "
and returned the whole tail, so the very next seam recorded the verifier
identity as "pytest … — closes: ?01": the same closing verifier read as
a brand-new name for verifier_agreement / verifier_independence, and the
polluted name reached the Telemetry line. The suffix is stripped before
the name is used.
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


class VerifierIdentityTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def test_closed_row_yields_a_clean_verifier_name(self):
        os.chdir(self.ws)
        run_controller(self.ws, "note", "--goal", "g", "--next", "n1")
        run_controller(self.ws, "note", "--open", "q", "--settled-by", "t")
        run_controller(self.ws, "note", "--close", "1", "--check", "it holds",
                       "--by", "pytest tests -q exits 0 including empty")
        book = mindseam.read_ledger()
        self.assertTrue(
            book["Verified"][-1].endswith(" — closes: ?01"),
            book["Verified"][-1])
        self.assertEqual(mindseam.last_verifier(book),
                         "pytest tests -q exits 0 including empty")

    def test_history_verifier_stays_clean_after_a_close(self):
        os.chdir(self.ws)
        run_controller(self.ws, "note", "--goal", "g", "--next", "n1")
        run_controller(self.ws, "note", "--open", "q", "--settled-by", "t")
        run_controller(self.ws, "note", "--close", "1", "--check", "it holds",
                       "--by", "pytest tests -q exits 0 including empty")
        run_controller(self.ws, "note", "--next", "n2")
        run_controller(self.ws, "seam")
        hist = json.loads(
            (Path(self.ws) / ".mindseam" / "history.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(hist[-1]["verifier"],
                         "pytest tests -q exits 0 including empty")

    def test_unclosed_row_is_unchanged(self):
        book = {"Verified": ["✓01 holds — verified by: pytest"], "Open": []}
        self.assertEqual(mindseam.last_verifier(book), "pytest")


if __name__ == "__main__":
    unittest.main()
