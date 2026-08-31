# -*- coding: utf-8 -*-
"""Round 16 guards: history IO repair gaps and archive compaction loss.

Two defects in the history layer:

  1. read_history validated the numeric and event fields of each row but
     left marker / confidence / verifier / risk unchecked. Detectors call
     .strip() and .lower() on those fields, so one corrupted non-string
     value crashed the whole seam instead of being repaired like every
     other field of the eleven-field schema.

  2. compact_history overwrote history.archive.json with only the newest
     slice each time the history crossed HISTORY_MAX again, silently
     dropping every earlier archived entry. The archive is now merged
     append-only across compactions, with the same defensive repair
     reporting read_history uses.
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


def row(i, **kw):
    base = {"t": 1000 + i, "next": "dom: act %d" % i, "verified": i,
            "open": 0, "marker": "OPEN", "confidence": "strong",
            "verifier": "v", "risk": "low", "error": "", "outcome": "ok",
            "extra_steps": 0}
    base.update(kw)
    return base


class RepairGapTests(unittest.TestCase):
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

    def _write(self, hist):
        Path(mindseam.HISTORY).write_text(json.dumps(hist), encoding="utf-8")

    def test_non_string_signal_fields_are_repaired(self):
        self._write([row(0, marker=123, confidence=["strong"],
                         verifier=None, risk=42)])
        hist, changed, reasons = mindseam.read_history()
        self.assertTrue(changed)
        entry = hist[0]
        self.assertEqual(entry["marker"], "")
        self.assertEqual(entry["confidence"], "")
        self.assertEqual(entry["verifier"], "")
        self.assertEqual(entry["risk"], "")

    def test_repaired_rows_survive_the_detector_suite(self):
        self._write([row(i, marker=123 if i == 1 else "OPEN")
                     for i in range(3)])
        hist, _, _ = mindseam.read_history()
        # Before the repair these calls raised AttributeError.
        self.assertIsInstance(mindseam.marker_progression(hist), int)
        self.assertIsInstance(mindseam.session_health_score(hist).score, int)
        facts = mindseam.observations(hist)
        self.assertIsInstance(facts, list)

    def test_valid_rows_are_left_untouched(self):
        original = [row(i) for i in range(3)]
        self._write(original)
        hist, changed, reasons = mindseam.read_history()
        self.assertFalse(changed)
        self.assertEqual(hist, original)


class ArchiveMergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_history = mindseam.HISTORY
        self.old_archive = mindseam.HISTORY_ARCHIVE
        self.old_ledger = mindseam.LEDGER_DIR
        mindseam.LEDGER_DIR = self.tmp.name
        mindseam.HISTORY = str(Path(self.tmp.name) / "history.json")
        mindseam.HISTORY_ARCHIVE = str(Path(self.tmp.name) / "archive.json")

    def tearDown(self):
        mindseam.HISTORY = self.old_history
        mindseam.HISTORY_ARCHIVE = self.old_archive
        mindseam.LEDGER_DIR = self.old_ledger
        self.tmp.cleanup()

    def _archive_contents(self):
        return json.loads(
            Path(mindseam.HISTORY_ARCHIVE).read_text(encoding="utf-8"))

    def test_second_compaction_preserves_the_first_archive(self):
        # First crossing: entries 0 and 1 leave the history.
        mindseam.compact_history([row(i) for i in range(mindseam.HISTORY_MAX + 2)])
        self.assertEqual(len(self._archive_contents()), 2)
        # Second crossing: one more entry leaves; the earlier two must
        # still be there instead of being replaced by the new slice.
        mindseam.compact_history([row(i) for i in range(1, mindseam.HISTORY_MAX + 2)])
        merged = self._archive_contents()
        self.assertEqual(len(merged), 3)
        self.assertEqual([r["t"] for r in merged], [1000, 1001, 1001])

    def test_unreadable_archive_is_replaced_with_a_reason(self):
        Path(mindseam.HISTORY_ARCHIVE).write_text("{not json",
                                                encoding="utf-8")
        kept, _, reasons = mindseam.compact_history(
            [row(i) for i in range(mindseam.HISTORY_MAX + 1)])
        self.assertEqual(len(kept), mindseam.HISTORY_MAX)
        self.assertTrue(any("unreadable" in r for r in reasons), reasons)
        self.assertEqual(len(self._archive_contents()), 1)

    def test_short_history_never_touches_the_archive(self):
        kept, changed, reasons = mindseam.compact_history([row(i) for i in range(5)])
        self.assertEqual(len(kept), 5)
        self.assertFalse(changed)
        self.assertFalse(Path(mindseam.HISTORY_ARCHIVE).exists())


if __name__ == "__main__":
    unittest.main()
