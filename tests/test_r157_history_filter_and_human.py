# -*- coding: utf-8 -*-
"""Round 157 guards: history --filter key=value and history --human.

``--filter`` borrows the ``docker ps --filter name=value`` /
``kubectl get --field-selector key=value`` family: keep only the rows
whose field equals the value, one pair per flag, all pairs ANDed
together, unknown keys declined instead of silently matching nothing.
``--human`` borrows ``git log``'s relative dates / ``ls -lh``: the text
table renders each row's age as a span, while every machine face
(JSON, CSV, ``--format``) keeps the raw epoch, the way ``info --human``
keeps raw seconds in its payload. The guards pin matching semantics,
declined inputs, composition with the older filter chain, and the
raw-epoch guarantee across the machine faces.
"""

import json
import os
import re
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


def _invoke(args, cwd):
    return subprocess.run(
        [sys.executable, str(MINDSEAM), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
    )


class FilterBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _open(self):
        r = _invoke(["note", "--goal", "filter demo", "--next", "alpha: one"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def _note_and_seam(self, nxt, *extra):
        r = _invoke(["note", "--next", nxt, *extra], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = _invoke(["seam"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def _three_rows(self):
        # Row 1: plain alpha row. Row 2: beta row carrying the OPEN
        # marker, a shaky tag and the msg annotation. Row 3: alpha
        # row with a thin tag — the OPEN marker is a state key, so it
        # persists onto row 3 too, and only the confidence AND-filter
        # tells the two apart.
        self._open()
        r = _invoke(["note", "--next", "beta: two", "--marker", "OPEN",
                     "--confidence", "shaky",
                     "--verifier", "manual run with output"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = _invoke(["seam", "--message", "annotated row"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self._note_and_seam("alpha: three", "--confidence", "thin")


class FilterMatchTests(FilterBase):

    def test_filter_matches_the_field_exact(self):
        self._three_rows()
        r = _invoke(["history", "--filter", "next=beta: two", "--quiet"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), ["beta: two"])

    def test_repeatable_filters_and_together(self):
        self._three_rows()
        r = _invoke(["history", "--filter", "marker=OPEN",
                     "--filter", "confidence=thin", "--quiet"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # Both trailing rows carry the persisted OPEN marker; only the
        # thin-tagged one satisfies both filters.
        self.assertEqual(r.stdout.splitlines(), ["alpha: three"])

    def test_filter_marker_open_matches_both_state_rows(self):
        self._three_rows()
        r = _invoke(["history", "--filter", "marker=OPEN", "--count"],
                    cwd=self.workspace)
        self.assertEqual(r.stdout.strip(), "2")

    def test_no_match_yields_zero_with_clean_exit(self):
        self._three_rows()
        r = _invoke(["history", "--filter", "marker=NOPE", "--count"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "0")

    def test_empty_value_matches_blank_field(self):
        self._three_rows()
        r = _invoke(["history", "--filter", "msg=", "--count"],
                    cwd=self.workspace)
        self.assertEqual(r.stdout.strip(), "1",
                         "only the second row carries no msg annotation")

    def test_numeric_fields_compare_by_string_form(self):
        history = Path(self.workspace) / ".mindseam" / "history.json"
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text(json.dumps([
            {"t": 1, "next": "alpha: a", "verified": 0, "open": 0},
            {"t": 2, "next": "alpha: b", "verified": 1, "open": 0},
        ]), encoding="utf-8")
        r = _invoke(["history", "--filter", "verified=1", "--count"],
                    cwd=self.workspace)
        self.assertEqual(r.stdout.strip(), "1")
        r = _invoke(["history", "--filter", "verified=0", "--count"],
                    cwd=self.workspace)
        self.assertEqual(r.stdout.strip(), "1")

    def test_msg_field_filters_on_the_annotation(self):
        # Exact value, the way docker's --filter matches: --grep is
        # the substring tool, --filter compares whole values.
        self._three_rows()
        r = _invoke(["history", "--filter", "msg=annotated row", "--quiet"],
                    cwd=self.workspace)
        self.assertEqual(r.stdout.splitlines(), ["beta: two"])
        r = _invoke(["history", "--filter", "msg=annotated", "--count"],
                    cwd=self.workspace)
        self.assertEqual(r.stdout.strip(), "0",
                         "a partial value must not match exact filters")

    def test_composes_with_grep(self):
        self._three_rows()
        r = _invoke(["history", "--filter", "marker=OPEN",
                     "--grep", "beta", "--quiet"],
                    cwd=self.workspace)
        self.assertEqual(r.stdout.splitlines(), ["beta: two"])

    def test_composes_with_json_payload(self):
        self._three_rows()
        r = _invoke(["history", "--filter", "next=beta: two", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 1)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0]["next"], "beta: two")


class FilterDeclineTests(FilterBase):

    def setUp(self):
        super().setUp()
        self._open()

    def test_unknown_key_is_declined(self):
        r = _invoke(["history", "--filter", "bogus=x"], cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("is not a history field", r.stderr)
        self.assertIn("marker", r.stderr, "the fix line names the valid fields")

    def test_malformed_pair_is_declined(self):
        r = _invoke(["history", "--filter", "markerOPEN"], cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("expects key=value", r.stderr)

    def test_declined_filter_writes_nothing(self):
        history = Path(self.workspace) / ".mindseam" / "history.json"
        r = _invoke(["history", "--filter", "bogus=x"], cwd=self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertFalse(history.exists())


class HumanFaceTests(FilterBase):

    def _seed_one(self):
        self._open()
        r = _invoke(["seam"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_table_renders_relative_spans(self):
        self._seed_one()
        r = _invoke(["history", "--human"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"\d+ seconds? ago")

    def test_table_without_human_keeps_absolute_time(self):
        self._seed_one()
        r = _invoke(["history"], cwd=self.workspace)
        self.assertRegex(r.stdout, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
        self.assertNotIn("ago", r.stdout)

    def test_json_keeps_the_raw_epoch(self):
        self._seed_one()
        text = _invoke(["history", "--json"], cwd=self.workspace).stdout
        human = _invoke(["history", "--human", "--json"], cwd=self.workspace).stdout
        self.assertEqual(json.loads(text)["rows"], json.loads(human)["rows"])

    def test_csv_keeps_the_raw_epoch(self):
        self._seed_one()
        plain = _invoke(["history", "--csv"], cwd=self.workspace).stdout
        human = _invoke(["history", "--human", "--csv"], cwd=self.workspace).stdout
        self.assertEqual(plain, human)

    def test_format_keeps_the_raw_epoch(self):
        self._seed_one()
        plain = _invoke(["history", "--format", "%t"], cwd=self.workspace).stdout
        human = _invoke(["history", "--human", "--format", "%t"],
                        cwd=self.workspace).stdout
        self.assertEqual(plain, human)

    def test_row_id_honours_human(self):
        self._seed_one()
        r = _invoke(["history", "--row-id", "1", "--human"], cwd=self.workspace)
        self.assertIn("ago", r.stdout)

    def test_future_timestamp_does_not_read_ago(self):
        ts = int(__import__("time").time()) + 3600
        history = Path(self.workspace) / ".mindseam" / "history.json"
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text(json.dumps(
            [{"t": ts, "next": "alpha: one", "verified": 0, "open": 0}]),
            encoding="utf-8")
        r = _invoke(["history", "--human"], cwd=self.workspace)
        self.assertIn("in the future", r.stdout)
        self.assertNotIn("future ago", r.stdout)

    def test_helper_matches_the_published_face(self):
        self.assertEqual(mindseam._history_when(0), "(no timestamp)")
        self.assertEqual(
            mindseam._history_when(int(__import__("time").time()) - 90,
                                   human=True),
            "1 minute ago")


if __name__ == "__main__":
    unittest.main()
