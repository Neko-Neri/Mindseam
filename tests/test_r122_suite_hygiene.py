# -*- coding: utf-8 -*-
"""Round 50 guards: the suite must not write the workspace it audits.

The compaction test in round 37's cross-detector module called
compact_history on 503 fixture entries with the module's real relative
paths. Every full-suite run therefore wrote 500 fixture entries into
the repository's own .mindseam/history.json and appended 3 more to
history.archive.json — a workspace that only ever grew, and whose stale
markers then leaked into ship's completion gate for anyone testing in
the repository root (the "marker 'STEP' was not followed by a settle"
line that surfaced during the round 48-49 audits). The compaction test
now patches HISTORY and HISTORY_ARCHIVE into a temp directory, the
round 56 pattern.

This guard pins the hygiene property itself: running the known
history-writing test module from the repository root must leave the
root .mindseam state files byte-identical (or absent, on a fresh clone).
"""

import hashlib
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHED = (".mindseam/history.json", ".mindseam/history.archive.json")


def _digest(path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SuiteHygieneTests(unittest.TestCase):

    def test_history_writing_module_leaves_root_state_untouched(self):
        before = {name: _digest(ROOT / name) for name in WATCHED}
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             str(ROOT / "tests" / "test_r37_cross_detector_interactions.py")],
            cwd=str(ROOT), capture_output=True, timeout=300)
        after = {name: _digest(ROOT / name) for name in WATCHED}
        self.assertEqual(before, after,
                         "a test module modified the repository's own .mindseam: %r"
                         % {k: (before[k], after[k]) for k in before
                            if before[k] != after[k]})

    def test_compaction_test_is_patched(self):
        # Structural backstop: the module must patch the write paths
        # before calling compact_history, so the hermetic pattern cannot
        # silently regress into a repo-relative write.
        source = (ROOT / "tests" / "test_r37_cross_detector_interactions.py")\
            .read_text(encoding="utf-8")
        self.assertIn("mindseam.HISTORY =", source)
        self.assertIn("mindseam.HISTORY_ARCHIVE =", source)


if __name__ == "__main__":
    unittest.main()
