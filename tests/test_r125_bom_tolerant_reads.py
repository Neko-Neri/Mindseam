# -*- coding: utf-8 -*-
"""Round 53 guards: state files edited on Windows keep their first section.

The four state readers opened .mindseam files as plain utf-8. A byte-
order mark — what legacy Windows editors prepend to UTF-8 — therefore
landed on the first line of the file: "## Goal" stopped matching the
section prefix and the goal silently vanished from the parsed ledger,
while a marked history.json or metacognition.json failed json.load and
took the "unreadable, restarted" path, losing state that was perfectly
readable one BOM-stripping read away. All four readers now use
utf-8-sig, which reads plain utf-8 identically; nothing the controller
writes changes.
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

import mindseam

LEDGER_TEXT = "# Mindseam Workspace Ledger\n\n## Goal\ndone means probe\n\n## Next\ndom: act now\n"


class BomTolerantReadTests(unittest.TestCase):

    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)
        Path(mindseam.LEDGER_DIR).mkdir(exist_ok=True)

    def tearDown(self):
        os.chdir(self.cwd)
        import shutil
        shutil.rmtree(self.ws, ignore_errors=True)

    def _write(self, name, text):
        Path(mindseam.LEDGER_DIR, name).write_text(
            text, encoding="utf-8-sig", newline="")

    def test_bom_ledger_keeps_every_section(self):
        self._write("WORKSPACE.md", LEDGER_TEXT)
        book = mindseam.read_ledger()
        self.assertEqual(book["Goal"], ["done means probe"])
        self.assertEqual(book["Next"], ["dom: act now"])

    def test_bom_ledger_whose_first_line_is_a_section(self):
        # The h1 normally absorbs the stray first-line mismatch; a
        # hand-trimmed ledger that opens directly with ## Goal is the
        # shape that used to lose it.
        self._write("WORKSPACE.md", "## Goal\ndone means probe\n\n## Next\ndom: act\n")
        book = mindseam.read_ledger()
        self.assertEqual(book["Goal"], ["done means probe"])

    def test_bom_history_loads_instead_of_restarting(self):
        hist = [{"t": 1000, "next": "dom: act", "verified": 1, "open": 0}]
        self._write("history.json", json.dumps(hist))
        loaded, changed, reasons = mindseam.read_history()
        self.assertEqual(loaded, hist)
        self.assertFalse(
            any("unreadable" in r for r in reasons), reasons)

    def test_bom_metacognition_loads(self):
        self._write("metacognition.json",
                    json.dumps({"marker": "OPEN", "schema_version": 1}))
        self.assertEqual(mindseam.read_meta().get("marker"), "OPEN")

    def test_plain_utf8_round_trip_is_unchanged(self):
        # The controller writes plain utf-8; reading it must behave
        # exactly as before the sig-tolerant open.
        Path(mindseam.LEDGER_DIR, "WORKSPACE.md").write_text(
            LEDGER_TEXT, encoding="utf-8", newline="")
        book = mindseam.read_ledger()
        self.assertEqual(book["Goal"], ["done means probe"])


if __name__ == "__main__":
    unittest.main()
