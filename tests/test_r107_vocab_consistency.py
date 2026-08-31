# -*- coding: utf-8 -*-
"""Round 69 guards: the leak-scanner vocabulary is taught vocabulary.

ship flags INNER_ONLY symbols and MARKERS phrases as inner-register
leakage. Every one of those entries must be notation the suite actually
teaches somewhere — a scanner entry with no documented origin would
flag text no user was ever told to avoid in public (the dead-key family
again, this time in the leak list). Verified: all INNER_ONLY symbols
appear in shorthand.md or the exemplars reference, all MARKERS phrases
appear in markers.md.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

SKILL_ROOT = ROOT / "mindseam"


def shipped_text():
    return "\n".join(
        p.read_text(encoding="utf-8") for p in SKILL_ROOT.rglob("*.md"))


class VocabularyConsistencyTests(unittest.TestCase):

    def test_every_inner_only_symbol_is_taught(self):
        text = shipped_text()
        untaught = [s for s in mindseam.INNER_ONLY if s not in text]
        self.assertEqual(
            untaught, [],
            "INNER_ONLY entries no shipped document teaches: %s" % untaught)

    def test_every_marker_phrase_is_taught(self):
        markers_md = (SKILL_ROOT / "modules" / "markers.md") \
            .read_text(encoding="utf-8")
        untaught = [m for m in mindseam.MARKERS if m not in markers_md]
        self.assertEqual(
            untaught, [],
            "MARKERS entries markers.md never teaches: %s" % untaught)

    def test_the_scanner_uses_those_exact_lists(self):
        # mode_ship consumes the module-level lists; pin the wiring so a
        # local copy cannot drift from the taught vocabulary.
        import inspect
        source = inspect.getsource(mindseam.mode_ship)
        self.assertIn("INNER_ONLY", source)
        self.assertIn("MARKERS", source)


if __name__ == "__main__":
    unittest.main()
