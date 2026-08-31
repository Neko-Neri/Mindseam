# -*- coding: utf-8 -*-
"""Round 55 guards: every meta input is normalised, including markers.

note validated its metacognition inputs with three different
disciplines: --confidence had a vocabulary check, --verifier and
--error/--outcome were stripped through clean_scalar, but --marker was
passed through raw. A marker recorded with surrounding whitespace —
easy to paste — silently missed every exact-match consumer downstream:
the PHEW settle recognition, the OPEN phase checks, the completion
gate's settle line. The value looked recorded and matched nothing.
--marker now strips like the other free-text fields, and a marker that
is empty after stripping refuses the note, matching --verifier's
precedent.
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


class MarkerNormalisationTests(unittest.TestCase):

    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def _meta(self):
        return json.loads(
            (Path(self.ws) / ".mindseam" / "metacognition.json")
            .read_text(encoding="utf-8"))

    def test_padded_marker_is_stored_trimmed(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "dom: a")
        result = run_controller(
            self.ws, "note", "--next", "dom: b", "--marker", "  PHEW  ")
        self.assertEqual(result.returncode, 0, result.stdout)
        meta = self._meta()
        self.assertEqual(meta.get("marker"), "PHEW")
        self.assertEqual(meta.get("trend", {}).get("marker"), ["PHEW"])

    def test_trimmed_marker_reaches_history_clean(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "dom: a")
        run_controller(self.ws, "note", "--next", "dom: b",
                       "--marker", " OPEN ")
        run_controller(self.ws, "seam")
        hist = json.loads(
            (Path(self.ws) / ".mindseam" / "history.json")
            .read_text(encoding="utf-8"))
        self.assertTrue(hist)
        self.assertEqual(hist[-1]["marker"], "OPEN")

    def test_whitespace_marker_refuses_the_note(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "dom: a")
        result = run_controller(self.ws, "note", "--next", "dom: b",
                                "--marker", "   ")
        self.assertEqual(result.returncode, 2)
        self.assertIn("NOT RECORDED", result.stdout)

    def test_every_free_text_meta_field_is_normalised(self):
        # error and outcome already stripped; pin all three together so
        # a future field cannot reintroduce the raw pass-through.
        run_controller(self.ws, "note", "--goal", "g", "--next", "dom: a")
        run_controller(self.ws, "note", "--next", "dom: b",
                       "--marker", " OPEN ",
                       "--error", "  net: timeout  ",
                       "--outcome", "  ok  ")
        meta = self._meta()
        self.assertEqual(meta.get("marker"), "OPEN")
        self.assertEqual(meta.get("error"), "net: timeout")
        self.assertEqual(meta.get("outcome"), "ok")


if __name__ == "__main__":
    unittest.main()
