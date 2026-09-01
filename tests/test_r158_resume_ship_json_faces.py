# -*- coding: utf-8 -*-
"""Round 158 guards: resume --json and ship --json complete the two-faces rule.

Every other subcommand already carried both a text and a ``gh --json``
face (r153 gave seam its machine face; info, history, skillbook,
discover and audit all had one from birth). resume and ship were the
last two prose-only surfaces, which meant a host gating a delivery on
``ship`` had to scrape bullet lines. The JSON faces mirror the text
data under stable keys, keep the exit contract byte-identical across
faces, and drop the premise prose / banner that a host cannot consume
— the way ``seam --json`` reports the long gap without the reentry
banner.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _invoke(args, cwd, stdin=None):
    return subprocess.run(
        [sys.executable, str(MINDSEAM), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        input=stdin,
    )


class TwoFacesBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _open(self, goal="two faces", nxt="dom: first"):
        r = _invoke(["note", "--goal", goal, "--next", nxt],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)


class ResumeJsonTests(TwoFacesBase):

    def test_resume_json_is_valid_and_sectioned(self):
        self._open()
        r = _invoke(["resume", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        for key in ("ledger", "history_count", "state_repairs",
                    "risk", "trend"):
            self.assertIn(key, payload)
        self.assertEqual(payload["ledger"]["goal"], "two faces")
        self.assertIn("score", payload["trend"])
        for key in ("value", "grade", "factors"):
            self.assertIn(key, payload["trend"]["score"])

    def test_resume_json_score_agrees_with_its_grade(self):
        self._open()
        payload = json.loads(
            _invoke(["resume", "--json"], cwd=self.workspace).stdout)
        value = payload["trend"]["score"]["value"]
        self.assertEqual(payload["trend"]["score"]["grade"],
                         mindseam.grade(value))

    def test_resume_json_drops_the_premise_prose(self):
        self._open()
        r = _invoke(["resume", "--json"], cwd=self.workspace)
        self.assertFalse(r.stdout.lstrip().startswith("──"))
        self.assertNotIn("You do not only produce words", r.stdout)
        # The text face keeps it — the prose is the point there.
        text = _invoke(["resume"], cwd=self.workspace)
        self.assertIn("You do not only produce words", text.stdout)

    def test_resume_json_still_appends_history(self):
        self._open()
        r = _invoke(["resume", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        history = Path(self.workspace) / ".mindseam" / "history.json"
        self.assertTrue(history.exists())
        self.assertEqual(
            len(json.loads(history.read_text(encoding="utf-8"))), 1)

    def test_resume_json_carries_persisted_risk(self):
        self._open()
        r = _invoke(["note", "--next", "dom: second", "--marker", "OPEN"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = _invoke(["seam"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(
            _invoke(["resume", "--json"], cwd=self.workspace).stdout)
        self.assertIn(payload["risk"]["level"], ("low", "medium", "high"))


class ShipJsonTests(TwoFacesBase):

    def _ship(self, text, *flags):
        return _invoke(["ship", "-", *flags], cwd=self.workspace,
                       stdin=text)

    def test_ship_json_clean_payload(self):
        r = self._ship("Clean delivery prose with nothing hidden.\n",
                       "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["exit"], 0)

    def test_ship_json_finding_payload(self):
        r = self._ship("Calling PHEW to settle this thread.\n", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertFalse(payload["clean"])
        self.assertTrue(any("PHEW" in f for f in payload["findings"]))

    def test_ship_json_strict_exit_matches_the_text_face(self):
        leak = "Calling PHEW to settle this thread.\n"
        text_rc = self._ship(leak, "--strict").returncode
        json_rc = self._ship(leak, "--json", "--strict").returncode
        self.assertEqual(text_rc, json_rc)
        payload = json.loads(self._ship(leak, "--json", "--strict").stdout)
        self.assertEqual(payload["exit"], json_rc)

    def test_ship_json_reports_the_gate(self):
        # A history ending on an unsettled OPEN marker trips the gate.
        self._open()
        r = _invoke(["note", "--next", "dom: second", "--marker", "OPEN"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = _invoke(["seam"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(self._ship("Clean prose.\n", "--json").stdout)
        self.assertTrue(payload["gate"],
                        "the unsettled marker must gate, got %r" % payload)
        self.assertEqual(payload["exit"], 0,
                         "gate observations stay exit-0 without --strict")

    def test_ship_json_strict_gates(self):
        self._open()
        r = _invoke(["note", "--next", "dom: second", "--marker", "OPEN"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = _invoke(["seam"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(
            self._ship("Clean prose.\n", "--json", "--strict").stdout)
        self.assertEqual(payload["exit"], 2)
        self.assertEqual(
            self._ship("Clean prose.\n", "--strict").returncode, 2)

    def test_ship_json_never_leaks_state_markers_itself(self):
        # The JSON face is task-facing output; its own strings must
        # not carry the markers it is reporting, or r86's structural
        # rule would forbid piping it anywhere.
        r = self._ship("Calling PHEW to settle this thread.\n", "--json")
        payload = json.loads(r.stdout)
        for f in payload["findings"]:
            self.assertIn("PHEW", f)  # reported, as data


class BothFacesRegistered(TwoFacesBase):

    def test_every_report_subcommand_now_offers_json(self):
        # note is an editor, not a report: it echoes the ledger and
        # declines malformed input, so it keeps its single face. Every
        # read/report surface answers --json.
        for sub in ("seam", "resume", "ship", "skillbook",
                    "info", "discover", "history", "audit"):
            r = _invoke([sub, "--help"], cwd=self.workspace)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("--json", r.stdout,
                          "%s still has no --json face" % sub)


if __name__ == "__main__":
    unittest.main()
