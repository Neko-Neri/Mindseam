# -*- coding: utf-8 -*-
"""Round 160 guards: the audit evidence link.

A finding without a pointer is a verdict a host cannot audit.
r160 borrows from ``git blame`` / ``cargo tree -e features`` and
adds an ``evidence`` block to every finding:

- ``delete``     — row, row text, first-seen row + index
- ``stdlib``     — row, row text, canonical row + index
- ``yagni``      — core_total, live_slots, parked count + indices
- ``shrink``     — blank_count, blank_indices, history_total
- ``goal-stale`` — goal text, window, stale 1-based seam indices
- ``next-stall`` — the next, the seam indices, the count + window
- ``core-drift`` — live_next, core_items, direction (next-not-in-core / core-without-next)

The text face inlines a one-line summary at the end of the
finding, the way ``git log --stat`` inlines the diff stat. The
JSON face carries the full evidence block on every finding.
``--tag`` projection keeps the evidence on the projected
findings — the dial trims prose, not data.
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


def _invoke(args, cwd, env=None):
    run_env = os.environ.copy()
    run_env.pop("MINDSEAM_INTENSITY", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, str(MINDSEAM), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        env=run_env,
    )


def _write_history(workspace, rows):
    path = Path(workspace) / ".mindseam" / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


class EvidenceBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _ledger(self, goal="audit demo", core=(), verified=(),
                open_=(), next_="c1 — one"):
        path = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ["# Mindseam Workspace Ledger", ""]
        text += ["## Goal", goal, ""]
        text += ["## Core"] + list(core) + [""]
        text += ["## Verified"] + list(verified) + [""]
        text += ["## Open"] + list(open_) + [""]
        text += ["## Next", next_, ""]
        path.write_text("\n".join(text), encoding="utf-8")

    def _find(self, tag):
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        matches = [f for f in findings if f["tag"] == tag]
        self.assertEqual(len(matches), 1,
                         "expected exactly one %s finding, got %d: %r"
                         % (tag, len(matches), findings))
        return matches[0]


class SurfaceEvidenceTests(EvidenceBase):
    """The four r156 surface tags each carry their own evidence shape."""

    def test_delete_evidence_points_to_first_seen(self):
        self._ledger(open_=("?01 same question — settled by: test a",
                            "?02 same question — settled by: test a"))
        f = self._find("delete")
        ev = f["evidence"]
        self.assertEqual(ev["row"], 2)
        self.assertEqual(ev["first_seen"], "Open #1")
        self.assertEqual(ev["first_seen_index"], 1)
        self.assertIn("same question", ev["row_text"])

    def test_delete_evidence_points_to_answered_by(self):
        # An Open row whose text matches a Verified row — the
        # answered-by branch of the delete detector. The audit
        # normalises the prefix (✓NN / ?NN) and casefolds, so
        # the suffixes must agree exactly.
        self._ledger(
            verified=("✓01 same question — settled by: test a",),
            open_=("?01 same question — settled by: test a",))
        f = self._find("delete")
        ev = f["evidence"]
        self.assertEqual(ev["row"], 1)
        self.assertEqual(ev["answered_by"], "Verified #1")
        self.assertEqual(ev["answered_by_index"], 1)

    def test_stdlib_evidence_points_to_canonical(self):
        self._ledger(verified=("✓01 first — verified by: brute force",
                               "✓02 first — verified by: brute force"))
        f = self._find("stdlib")
        ev = f["evidence"]
        self.assertEqual(ev["row"], 2)
        self.assertEqual(ev["canonical"], "Verified #1")
        self.assertEqual(ev["canonical_index"], 1)
        self.assertIn("first", ev["row_text"])

    def test_yagni_evidence_reports_parked_count_and_total(self):
        self._ledger(core=("c1 — one", "c2 — two", "c3 — three",
                           "c4 — four", "c5 — five"))
        f = self._find("yagni")
        ev = f["evidence"]
        self.assertEqual(ev["core_total"], 5)
        self.assertEqual(ev["live_slots"], 2)
        self.assertEqual(ev["parked"], 3)
        self.assertEqual(ev["parked_indices"], [3, 4, 5])

    def test_shrink_evidence_lists_blank_indices(self):
        self._ledger()
        _write_history(self.workspace, [
            {"t": 1, "next": "a", "verified": 0, "open": 0},
            {"t": 2, "next": "", "verified": 0, "open": 0},
            {"t": 3, "next": "c", "verified": 0, "open": 0},
            {"t": 4, "next": "", "verified": 0, "open": 0},
        ])
        f = self._find("shrink")
        ev = f["evidence"]
        self.assertEqual(ev["blank_count"], 2)
        self.assertEqual(ev["blank_indices"], [2, 4])
        self.assertEqual(ev["history_total"], 4)


class FacetEvidenceTests(EvidenceBase):
    """The three r159 facet tags also carry evidence."""

    def test_goal_stale_evidence_lists_seam_indices(self):
        self._ledger(goal="ship r160")
        # 12 rows, none carrying a goal annotation. The detector
        # looks at the trailing 10; the leading 2 are off-window.
        _write_history(self.workspace, [
            {"t": i, "next": "step %d" % i, "verified": 0, "open": 0}
            for i in range(1, 13)
        ])
        f = self._find("goal-stale")
        ev = f["evidence"]
        self.assertEqual(ev["goal"], "ship r160")
        self.assertEqual(ev["window"], 10)
        self.assertEqual(ev["window_first"], 3)
        self.assertEqual(ev["window_last"], 12)
        # All ten trailing seams are stale; the indices are 1-based
        # and span the trailing window.
        self.assertEqual(ev["stale_indices"],
                         [3, 4, 5, 6, 7, 8, 9, 10, 11, 12])

    def test_next_stall_evidence_lists_seam_indices(self):
        self._ledger()
        _write_history(self.workspace, [
            {"t": 1, "next": "dom: blocked", "verified": 0, "open": 0},
            {"t": 2, "next": "dom: work", "verified": 0, "open": 0},
            {"t": 3, "next": "dom: blocked", "verified": 0, "open": 0},
            {"t": 4, "next": "dom: blocked", "verified": 0, "open": 0},
            {"t": 5, "next": "dom: work", "verified": 0, "open": 0},
        ])
        f = self._find("next-stall")
        ev = f["evidence"]
        self.assertEqual(ev["next"], "dom: blocked")
        self.assertEqual(ev["count"], 3)
        self.assertEqual(ev["window"], 5)
        self.assertEqual(ev["window_first"], 1)
        self.assertEqual(ev["window_last"], 5)
        self.assertEqual(ev["seam_indices"], [1, 3, 4])

    def test_core_drift_evidence_direction_next_not_in_core(self):
        self._ledger(core=("c1 — one", "c2 — review"),
                     next_="c3 — drift")
        f = self._find("core-drift")
        ev = f["evidence"]
        self.assertEqual(ev["live_next"], "c3 — drift")
        self.assertEqual(ev["core_items"], ["c1 — one", "c2 — review"])
        self.assertEqual(ev["direction"], "next-not-in-core")

    def test_core_drift_evidence_direction_core_without_next(self):
        self._ledger(core=("c1 — one", "c2 — review"), next_="")
        f = self._find("core-drift")
        ev = f["evidence"]
        self.assertEqual(ev["live_next"], "")
        self.assertEqual(ev["core_count"], 2)
        self.assertEqual(ev["direction"], "core-without-next")


class EvidenceSummaryTests(EvidenceBase):
    """The text face inlines a one-line evidence summary per finding."""

    def test_delete_summary_in_text_face(self):
        self._ledger(open_=("?01 same question — settled by: test a",
                            "?02 same question — settled by: test a"))
        r = _invoke(["audit"], cwd=self.workspace)
        line = next(l for l in r.stdout.splitlines() if l.startswith("delete"))
        self.assertIn("Open #1", line)
        self.assertIn("row #2", line)
        self.assertIn("evidence:", line)

    def test_stdlib_summary_in_text_face(self):
        self._ledger(verified=("✓01 first — verified by: brute force",
                               "✓02 first — verified by: brute force"))
        r = _invoke(["audit"], cwd=self.workspace)
        line = next(l for l in r.stdout.splitlines() if l.startswith("stdlib"))
        self.assertIn("Verified #1", line)
        self.assertIn("evidence:", line)

    def test_yagni_summary_in_text_face(self):
        self._ledger(core=("c1 — one", "c2 — two", "c3 — three"))
        r = _invoke(["audit"], cwd=self.workspace)
        line = next(l for l in r.stdout.splitlines() if l.startswith("yagni"))
        self.assertIn("parked", line)
        self.assertIn("evidence:", line)

    def test_shrink_summary_in_text_face(self):
        self._ledger()
        _write_history(self.workspace, [
            {"t": 1, "next": "", "verified": 0, "open": 0},
            {"t": 2, "next": "a", "verified": 0, "open": 0},
        ])
        r = _invoke(["audit"], cwd=self.workspace)
        line = next(l for l in r.stdout.splitlines() if l.startswith("shrink"))
        self.assertIn("blank rows", line)
        self.assertIn("evidence:", line)

    def test_goal_stale_summary_in_text_face(self):
        self._ledger(goal="ship r160")
        _write_history(self.workspace, [
            {"t": i, "next": "step %d" % i, "verified": 0, "open": 0}
            for i in range(1, 13)
        ])
        r = _invoke(["audit"], cwd=self.workspace)
        line = next(l for l in r.stdout.splitlines() if l.startswith("goal-stale"))
        self.assertIn("seams", line)
        self.assertIn("evidence:", line)

    def test_next_stall_summary_in_text_face(self):
        self._ledger()
        _write_history(self.workspace, [
            {"t": 1, "next": "dom: blocked", "verified": 0, "open": 0},
            {"t": 2, "next": "dom: work", "verified": 0, "open": 0},
            {"t": 3, "next": "dom: blocked", "verified": 0, "open": 0},
            {"t": 4, "next": "dom: blocked", "verified": 0, "open": 0},
            {"t": 5, "next": "dom: work", "verified": 0, "open": 0},
        ])
        r = _invoke(["audit"], cwd=self.workspace)
        line = next(l for l in r.stdout.splitlines() if l.startswith("next-stall"))
        self.assertIn("seams", line)
        self.assertIn("evidence:", line)

    def test_core_drift_summary_in_text_face(self):
        self._ledger(core=("c1 — one", "c2 — review"),
                     next_="c3 — drift")
        r = _invoke(["audit"], cwd=self.workspace)
        line = next(l for l in r.stdout.splitlines() if l.startswith("core-drift"))
        self.assertIn("next=", line)
        self.assertIn("evidence:", line)

    def test_clean_audit_has_no_evidence_phrase(self):
        # When the audit is clean, no evidence summary is rendered
        # because no finding fires.
        self._ledger()
        r = _invoke(["audit"], cwd=self.workspace)
        self.assertIn("Lean already. Ship.", r.stdout)
        self.assertNotIn("evidence:", r.stdout)


class EvidenceJsonTests(EvidenceBase):
    """The JSON face carries the full evidence block on every finding."""

    def test_every_finding_has_evidence_dict(self):
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same question — settled by: test a",
                   "?02 same question — settled by: test a"),
            next_="dom: drift")
        r = _invoke(["audit", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        for f in payload["findings"]:
            self.assertIn("evidence", f)
            self.assertIsInstance(f["evidence"], dict)
            self.assertNotEqual(
                f["evidence"], {},
                "finding %r has an empty evidence block" % f)

    def test_tag_filter_keeps_evidence(self):
        # Projection trims prose, not data: the evidence block
        # on the projected finding must be intact.
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            next_="dom: drift")
        r = _invoke(["audit", "--json", "--tag", "core-drift"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        f = payload["findings"][0]
        self.assertEqual(f["tag"], "core-drift")
        self.assertEqual(f["evidence"]["live_next"], "dom: drift")
        self.assertEqual(f["evidence"]["core_items"],
                         ["c1 — one", "c2 — two", "c3 — three"])

    def test_strict_under_filter_still_carries_evidence(self):
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            next_="dom: drift")
        r = _invoke(["audit", "--strict", "--json", "--tag", "core-drift"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 1, r.stderr)
        payload = json.loads(r.stdout)
        f = payload["findings"][0]
        self.assertIn("evidence", f)
        self.assertEqual(f["evidence"]["direction"], "next-not-in-core")


class EvidenceSummaryHelperTests(unittest.TestCase):
    """The ``_evidence_summary`` helper is deterministic per tag."""

    def test_summary_is_empty_for_clean_finding(self):
        self.assertEqual(
            mindseam._evidence_summary({"tag": "yagni",
                                         "what": "x",
                                         "replacement": "y"}),
            "")

    def test_summary_for_yagni(self):
        s = mindseam._evidence_summary({
            "tag": "yagni", "what": "x", "replacement": "y",
            "evidence": {"core_total": 5, "live_slots": 2,
                          "parked": 3, "parked_indices": [3, 4, 5]}})
        self.assertIn("3/5 parked", s)

    def test_summary_for_shrink_truncates_long_index_list(self):
        s = mindseam._evidence_summary({
            "tag": "shrink", "what": "x", "replacement": "y",
            "evidence": {"blank_count": 5, "blank_indices": [1, 2, 3, 4, 5],
                          "history_total": 10}})
        self.assertIn("5 blank rows", s)
        self.assertIn("…", s)

    def test_summary_for_core_drift_two_directions(self):
        forward = mindseam._evidence_summary({
            "tag": "core-drift", "what": "x", "replacement": "y",
            "evidence": {"live_next": "c3 — drift",
                          "core_items": ["c1 — one", "c2 — two"],
                          "direction": "next-not-in-core"}})
        self.assertIn("next=", forward)
        self.assertIn("not in core[2]", forward)
        backward = mindseam._evidence_summary({
            "tag": "core-drift", "what": "x", "replacement": "y",
            "evidence": {"live_next": "",
                          "core_items": ["c1 — one", "c2 — two"],
                          "core_count": 2,
                          "direction": "core-without-next"}})
        self.assertIn("core has 2", backward)
        self.assertIn("next empty", backward)
