# -*- coding: utf-8 -*-
"""Round 51 guards: taught markers are scanned markers, in both directions.

Round 69 verified the leak scanner's vocabulary is taught vocabulary —
no MARKERS entry without a documented origin. It checked one direction
only, and the other direction had a hole: markers.md's marker→move
table teaches `blocked?! WRONG.` (bound move `Fix:`), the only canonical
marker the scanner did not list. A session quoting that pair in a
deliverable — every other taught marker would be flagged as inner-
register leakage — passed the ship check unnoticed. The entry is now
"blocked?!" (prefix style, matching "GRRR" for "GRRR."), and this round
pins the full bidirectional contract:

  * forward: every scanner entry appears in markers.md (round 69);
  * reverse: every table-taught marker contains some scanner entry
    case-insensitively, so no new marker row can ship unsanned.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

MARKERS_MD = ROOT / "mindseam" / "modules" / "markers.md"


def taught_table_markers():
    """Marker names from the marker→move table in markers.md."""
    text = MARKERS_MD.read_text(encoding="utf-8")
    names = []
    for line in text.splitlines():
        row = re.match(r"\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|", line)
        if row:
            names.append(row.group(1))
    return names


class TaughtMarkerCoverageTests(unittest.TestCase):

    def test_the_doctrine_table_is_found(self):
        names = taught_table_markers()
        self.assertGreaterEqual(len(names), 5, names)
        self.assertTrue(any("blocked" in n.lower() for n in names), names)

    def test_every_taught_marker_is_scanned(self):
        gaps = []
        for taught in taught_table_markers():
            covered = any(entry.lower() in taught.lower()
                          for entry in mindseam.MARKERS)
            if not covered:
                gaps.append(taught)
        self.assertEqual(
            gaps, [],
            "markers.md teaches these markers the scanner never flags: %s"
            % gaps)

    def test_blocked_wrong_is_flagged_as_leakage(self):
        import tempfile
        import os
        import contextlib
        import io
        with tempfile.NamedTemporaryFile(
                "w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write("blocked?! WRONG. Fix: the existing item adds no load\n")
            path = fh.name
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                try:
                    mindseam.main(["ship", path])
                except SystemExit:
                    pass
        finally:
            os.unlink(path)
        self.assertIn("blocked?!", buf.getvalue())

    def test_plain_blocked_passes(self):
        # The entry is the doubting interjection, not the plain word.
        self.assertIn("blocked?!", mindseam.MARKERS)
        self.assertNotIn("blocked", mindseam.MARKERS)


if __name__ == "__main__":
    unittest.main()
