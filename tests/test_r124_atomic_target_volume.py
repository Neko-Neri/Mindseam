# -*- coding: utf-8 -*-
"""Round 52 guards: atomic writes follow the target, not the cwd.

atomic_write_text created its temp file in LEDGER_DIR — a path relative
to the process cwd — and then os.replace'd it onto the target. On any
host where the target lives on another volume than the cwd (a patched
test path on another drive, a relocated .mindseam), the replace failed
with a cross-device move and the write reported a problem instead of
happening. Two follow-on effects made this worse than one broken
helper:

  * round 50's hermetic compaction test patched HISTORY and
    HISTORY_ARCHIVE but not LEDGER_DIR, so on multi-volume hosts every
    write failed silently, compact_history returned changed=False, and
    the test's conditional assertion never ran — a green test that
    verified nothing. Its assertion is now unconditional.
  * round 56's pattern (patch LEDGER_DIR too) worked only because it
    accidentally kept the temp file on the target's volume.

The temp file is now created next to the target — the same-filesystem
requirement os.replace is built on — so patching the target path alone
is sufficient on any volume layout. ensure_dir(), which only existed to
prepare LEDGER_DIR for the old temp location, became dead code and is
deleted (round 38's no-unplugged-monitors rule); atomic_write_text now
creates the target's own directory.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def _other_volume_dir():
    """A directory on a different volume than the cwd, if one exists."""
    cwd_drive = os.path.splitdrive(os.path.abspath(os.getcwd()))[0]
    for candidate in (tempfile.gettempdir(), os.path.expanduser("~"),
                      os.environ.get("SYSTEMDRIVE", "C:") + os.sep):
        drive = os.path.splitdrive(os.path.abspath(candidate))[0]
        if drive and drive != cwd_drive:
            return candidate
    return None


class AtomicTargetVolumeTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_history = mindseam.HISTORY
        self.old_archive = mindseam.HISTORY_ARCHIVE

    def tearDown(self):
        mindseam.HISTORY = self.old_history
        mindseam.HISTORY_ARCHIVE = self.old_archive
        self.tmp.cleanup()

    def test_write_follows_a_patched_target_path(self):
        # Patching only the target path must be enough, whatever volume
        # it lands on: the temp file lives next to the target.
        target = Path(self.tmp.name) / "history.json"
        self.assertIsNone(
            mindseam.atomic_write_text(str(target), "[]"))
        self.assertEqual(target.read_text(encoding="utf-8"), "[]")

    def test_cross_volume_write_succeeds_when_layout_allows(self):
        other = _other_volume_dir()
        if other is None:
            self.skipTest("single-volume host")
        with tempfile.TemporaryDirectory(dir=other) as far:
            target = Path(far) / "probe.json"
            self.assertIsNone(
                mindseam.atomic_write_text(str(target), "payload"))
            self.assertEqual(
                target.read_text(encoding="utf-8"), "payload")

    def test_compaction_with_patched_targets_reports_changed(self):
        # The round 50 hermetic pattern (targets patched, LEDGER_DIR
        # not) must exercise the success path, not the failure path.
        mindseam.HISTORY = str(Path(self.tmp.name) / "history.json")
        mindseam.HISTORY_ARCHIVE = str(Path(self.tmp.name) / "archive.json")
        hist = [{"t": 1000 + i, "next": "dom: act %d" % i, "verified": i,
                 "open": 0, "marker": "STEP", "confidence": "thin",
                 "verifier": "v%d" % i, "risk": "low", "error": "",
                 "outcome": "ok", "extra_steps": 0}
                for i in range(mindseam.HISTORY_MAX + 2)]
        kept, changed, reasons = mindseam.compact_history(hist)
        self.assertTrue(
            changed, "compaction wrote nothing: %s" % reasons)
        self.assertEqual(len(kept), mindseam.HISTORY_MAX)
        self.assertEqual(
            len(json(Path(mindseam.HISTORY_ARCHIVE))), 2)

    def test_temp_files_are_never_left_in_the_target_directory(self):
        target = Path(self.tmp.name) / "clean.md"
        mindseam.atomic_write_text(str(target), "data")
        leftovers = [p.name for p in Path(self.tmp.name).iterdir()
                     if p.name != "clean.md"]
        self.assertEqual(leftovers, [])


def json(path):
    import json as jsonlib
    return jsonlib.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
