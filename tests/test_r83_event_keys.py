# -*- coding: utf-8 -*-
"""Round 45 guards: event keys are consumed exactly once.

error / outcome / extra_steps are event keys: the seam that observes
them records them into history and must clear them from the persisted
metacognition state, or every later seam would re-record the same event
forever (the round-4 mechanism contract). The guards pin the full
lifecycle: note writes them, the next seam consumes them into the new
history row, and the file no longer carries them afterwards.
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

from _controller_helper import run_controller


class EventKeyTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)
        run_controller(self.ws, "note", "--goal", "g", "--next", "dom: a")

    def tearDown(self):
        os.chdir(self.cwd)

    def _meta(self):
        return json.loads(
            (Path(self.ws) / ".mindseam" / "metacognition.json")
            .read_text(encoding="utf-8"))

    def _history(self):
        return json.loads(
            (Path(self.ws) / ".mindseam" / "history.json")
            .read_text(encoding="utf-8"))

    def test_note_records_the_event(self):
        run_controller(self.ws, "note", "--next", "dom: b",
                       "--error", "db: down", "--outcome", "failed",
                       "--extra-steps", "2")
        meta = self._meta()
        self.assertEqual(meta.get("error"), "db: down")
        self.assertEqual(meta.get("outcome"), "failed")
        self.assertEqual(meta.get("extra_steps"), 2)

    def test_seam_consumes_the_event_into_history(self):
        run_controller(self.ws, "note", "--next", "dom: b",
                       "--error", "db: down", "--outcome", "failed",
                       "--extra-steps", "2")
        run_controller(self.ws, "seam")
        entry = self._history()[-1]
        self.assertEqual(entry["error"], "db: down")
        self.assertEqual(entry["outcome"], "failed")
        self.assertEqual(entry["extra_steps"], 2)
        meta = self._meta()
        self.assertNotIn("error", meta)
        self.assertNotIn("outcome", meta)
        self.assertNotIn("extra_steps", meta)

    def test_event_does_not_replay_on_the_next_seam(self):
        run_controller(self.ws, "note", "--next", "dom: b",
                       "--error", "db: down")
        run_controller(self.ws, "seam")
        run_controller(self.ws, "note", "--next", "dom: c")
        run_controller(self.ws, "seam")
        entry = self._history()[-1]
        self.assertEqual(entry.get("error", ""), "")

    def test_state_keys_persist_across_seams(self):
        run_controller(self.ws, "note", "--next", "dom: b",
                       "--marker", "OPEN", "--confidence", "strong")
        run_controller(self.ws, "seam")
        run_controller(self.ws, "note", "--next", "dom: c")
        run_controller(self.ws, "seam")
        meta = self._meta()
        self.assertEqual(meta.get("marker"), "OPEN")
        self.assertEqual(meta.get("confidence"), "strong")


if __name__ == "__main__":
    unittest.main()
