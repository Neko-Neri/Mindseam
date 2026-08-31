# -*- coding: utf-8 -*-
"""Round 44 guards: history repair is idempotent and lossless.

read_history repairs malformed rows in place. Two properties pin the
repair contract: (1) a healthy eleven-field history reparses unchanged
— no phantom repairs on clean data; (2) repair is idempotent — the
second read of a repaired history reports no further changes, so a
repairing reader cannot fight itself across seams.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def healthy(i):
    return {"t": 1000 + i, "next": "dom: act %d" % i, "verified": i,
            "open": 0, "marker": "DONE", "confidence": "strong",
            "verifier": "manual run %d" % i, "risk": "low",
            "error": "", "outcome": "ok", "extra_steps": 0}


class HistoryRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_history = mindseam.HISTORY
        self.old_dir = mindseam.LEDGER_DIR
        mindseam.LEDGER_DIR = self.tmp.name
        mindseam.HISTORY = str(Path(self.tmp.name) / "history.json")

    def tearDown(self):
        mindseam.HISTORY = self.old_history
        mindseam.LEDGER_DIR = self.old_dir
        self.tmp.cleanup()

    def _write(self, hist):
        Path(mindseam.HISTORY).write_text(
            json.dumps(hist), encoding="utf-8")

    def test_healthy_history_reparses_unchanged(self):
        hist = [healthy(i) for i in range(4)]
        self._write(hist)
        repaired, changed, reasons = mindseam.read_history()
        self.assertFalse(changed, reasons)
        self.assertEqual(repaired, hist)

    def test_repair_is_idempotent(self):
        self._write([
            dict(healthy(0), marker=7, confidence=None),
            healthy(1),
            "not-an-object",
        ])
        first, changed1, _ = mindseam.read_history()
        self.assertTrue(changed1)
        second, changed2, reasons2 = mindseam.read_history()
        self.assertFalse(changed2, reasons2)
        self.assertEqual(first, second)

    def test_corrupt_rows_are_dropped_not_fatal(self):
        self._write(["junk", 42, healthy(0)])
        repaired, changed, reasons = mindseam.read_history()
        self.assertEqual(len(repaired), 1)
        self.assertTrue(any("was not an object" in r for r in reasons))

    def test_unreadable_history_restarts_empty(self):
        Path(mindseam.HISTORY).write_text("{broken", encoding="utf-8")
        repaired, _, reasons = mindseam.read_history()
        self.assertEqual(repaired, [])
        self.assertTrue(any("unreadable" in r for r in reasons))

    def test_append_history_extends_the_healthy_cycle(self):
        self._write([healthy(i) for i in range(2)])
        book = {"Goal": ["g"], "Core": [], "Verified": ["✓01 x — verified by: y"],
                "Open": [], "Next": ["dom: act 9"]}
        hist, _ = mindseam.append_history(book, meta={"marker": "DONE",
                                                    "confidence": "strong"})
        self.assertEqual(len(hist), 3)
        entry = hist[-1]
        self.assertEqual(entry["marker"], "DONE")
        self.assertEqual(entry["verified"], 1)
        self.assertEqual(entry["verifier"], "y")


if __name__ == "__main__":
    unittest.main()
