# -*- coding: utf-8 -*-
"""Round 25 guards: metacognition state migrates instead of vanishing.

read_meta returned {} for any schema-version mismatch, so the moment a
file written by a different suite version appeared, the persisted
trend / marker / risk state was silently wiped on the next seam — and
validate_meta_schema's upgrade machinery (unknown-key filtering, the
legacy "markers" rename, re-signing) was unreachable dead code. A
mismatched payload now flows through the migrator; unreadable files
still restart clean.
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


class MetaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_ledger = mindseam.LEDGER_DIR
        mindseam.LEDGER_DIR = self.tmp.name

    def tearDown(self):
        mindseam.LEDGER_DIR = self.old_ledger
        self.tmp.cleanup()

    def _write_meta(self, payload):
        path = Path(self.tmp.name) / "metacognition.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_future_version_preserves_trend_state(self):
        self._write_meta({
            "schema_version": 999,
            "trend": {"confidence": ["strong", "thin", "shaky"]},
            "risk": {"level": "high", "reasons": ["x"]},
        })
        meta = mindseam.read_meta()
        self.assertEqual(meta.get("trend", {}).get("confidence"),
                         ["strong", "thin", "shaky"])
        self.assertEqual(meta.get("risk", {}).get("level"), "high")

    def test_legacy_markers_key_is_renamed(self):
        self._write_meta({
            "schema_version": 0,
            "markers": "OPEN",
        })
        meta = mindseam.read_meta()
        self.assertEqual(meta.get("marker"), "OPEN")
        self.assertNotIn("markers", meta)

    def test_unknown_keys_are_dropped_but_known_kept(self):
        self._write_meta({
            "schema_version": 999,
            "marker": "DONE",
            "mystery_key": "gone",
        })
        meta = mindseam.read_meta()
        self.assertEqual(meta.get("marker"), "DONE")
        self.assertNotIn("mystery_key", meta)

    def test_current_version_reads_unchanged(self):
        self._write_meta({
            "schema_version": mindseam.METACOGNITION_SCHEMA_VERSION,
            "marker": "OPEN",
            "trend": {"marker": ["OPEN"]},
        })
        meta = mindseam.read_meta()
        self.assertEqual(meta.get("marker"), "OPEN")

    def test_unreadable_file_still_restarts_clean(self):
        path = Path(self.tmp.name) / "metacognition.json"
        path.write_text("{not json", encoding="utf-8")
        self.assertEqual(mindseam.read_meta(), {})

    def test_round_trip_preserves_state(self):
        meta = {"marker": "OPEN", "trend": {"confidence": ["strong"]}}
        self.assertIsNone(mindseam.write_meta(meta))
        self.assertEqual(mindseam.read_meta().get("marker"), "OPEN")


if __name__ == "__main__":
    unittest.main()
