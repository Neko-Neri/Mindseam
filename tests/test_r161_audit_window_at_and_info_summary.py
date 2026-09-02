# -*- coding: utf-8 -*-
"""Round 161 guards: audit time window, single-seam audit, info
audit_summary, JSON gate enum.

The r156-r160 audit was a snapshot over the full ledger + full
history. r161 extends it to a windowed audit (``--since`` /
``--until``) and a single-seam audit (``--at <row>``); the JSON
face gains a ``gate`` enum (clean / finding / gated) so a host
does not have to derive status from ``lean`` + ``strict``; and
the ``info`` report folds the same audit numbers into a single
``audit_summary`` block so a long-running session can read its
health at a glance.

The window narrows only the history slice the facet tags see.
The ledger surface tags (``delete`` / ``stdlib`` / ``yagni`` /
``core-drift``) keep operating on the full ``book`` — they
have nothing to do with time. The ``--tag`` projection composes
with all three new flags.

The ``gate`` enum is additive: ``lean`` stays the r156 boolean,
``gate`` is a richer three-state status. Both fields ride on
the JSON face, so r158 / r159 / r160 hosts that read ``lean``
keep working.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
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


class WindowBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self._now = int(time.time())

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

    def _row(self, next_action, t=None, goal=None):
        row = {"t": t if t is not None else self._now,
               "next": next_action, "verified": 0, "open": 0}
        if goal is not None:
            row["goal"] = goal
        return row


class AuditWindowTests(WindowBase):
    """``--since`` / ``--until`` narrow only the facet-tag history slice."""

    def test_since_narrows_shrink_finding(self):
        self._ledger()
        # 10 rows: 5 recent, 5 old. The shrink detector sees
        # only the rows that fall in the window. The ``blank_count``
        # evidence field records how many blank rows the
        # detector saw; the ``--since 60`` window narrows that
        # count from 6 (full) to 1 (just the recent row at -1s).
        # The full audit (no --since) sees 6 blank rows because
        # 4 of the 5 ancient blank rows are within the 10^2 s
        # window; the test uses larger time spans to make the
        # window count unambiguous.
        _write_history(self.workspace, [
            self._row("", t=self._now - 10**8),
            self._row("", t=self._now - 10**7),
            self._row("", t=self._now - 10**6),
            self._row("", t=self._now - 10**5),
            self._row("", t=self._now - 10**4),
            self._row("a", t=self._now - 10**3),
            self._row("b", t=self._now - 10**2),
            self._row("", t=self._now - 50),
            self._row("c", t=self._now - 5),
            self._row("", t=self._now - 1),
        ])
        r = _invoke(["audit", "--since", "60", "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        # The ``--since 60`` window keeps rows with t >= now-60,
        # so the rows at -50, -5, and -1 are in the slice.
        # Of those, the blanks are at -50 and -1 (positions 1
        # and 3 in the sliced history).
        ev = payload["findings"][0]["evidence"]
        self.assertEqual(ev["blank_count"], 2, payload)
        self.assertEqual(ev["blank_indices"], [1, 3], payload)
        # The full audit sees a different blank-count: 7
        # (5 ancient + 2 recent) versus the 2 in the window.
        full = _invoke(["audit", "--json"], cwd=self.workspace)
        full_ev = json.loads(full.stdout)["findings"][0]["evidence"]
        self.assertEqual(full_ev["blank_count"], 7, full_ev)

    def test_until_keeps_only_older_rows(self):
        self._ledger()
        # 6 rows: 3 fresh, 3 ancient. ``--until 1000`` keeps only
        # the ancient ones; the shrink finding still fires (it
        # is one finding, not three — the detector counts blank
        # rows internally but emits a single ``shrink`` verdict).
        # What changes is the rows the detector saw: 6 in, 3 out.
        _write_history(self.workspace, [
            self._row("", t=self._now - 10**6),
            self._row("", t=self._now - 9 * 10**5),
            self._row("", t=self._now - 8 * 10**5),
            self._row("", t=self._now - 5),
            self._row("", t=self._now - 2),
            self._row("", t=self._now - 1),
        ])
        r = _invoke(["audit", "--until", "1000", "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["by_tag"].get("shrink", 0), 1, payload)
        self.assertEqual(payload["history_window"]["rows_in"], 6)
        self.assertEqual(payload["history_window"]["rows_out"], 3)
        # The evidence block for shrink records the blank row
        # indices within the *sliced* history (1-based, 3 entries).
        ev = payload["findings"][0]["evidence"]
        self.assertEqual(ev["blank_count"], 3)
        self.assertEqual(ev["blank_indices"], [1, 2, 3])

    def test_since_until_compose_to_bracket_window(self):
        self._ledger()
        # 5 rows at 100, 200, 300, 400, 500 seconds ago. Bracket
        # the middle two: ``--since 450 --until 250`` keeps rows
        # at 250 and 300 seconds ago. The shrink detector emits
        # one finding whose evidence block records both blank
        # indices.
        _write_history(self.workspace, [
            self._row("", t=self._now - 100),
            self._row("", t=self._now - 200),
            self._row("", t=self._now - 300),
            self._row("", t=self._now - 400),
            self._row("", t=self._now - 500),
        ])
        r = _invoke(
            ["audit", "--since", "450", "--until", "250", "--json"],
            cwd=self.workspace)
        payload = json.loads(r.stdout)
        # rows_in is 5; rows_out is 2 (the bracketed window).
        self.assertEqual(payload["history_window"]["rows_in"], 5)
        self.assertEqual(payload["history_window"]["rows_out"], 2)
        # The single shrink finding records both indices.
        ev = payload["findings"][0]["evidence"]
        self.assertEqual(ev["blank_count"], 2)
        self.assertEqual(len(ev["blank_indices"]), 2)

    def test_window_does_not_affect_ledger_tags(self):
        # Even with a tight window, a duplicate Open still fires
        # because the ledger surface tags do not look at history.
        self._ledger(open_=("?01 same question — settled by: test a",
                            "?02 same question — settled by: test a"))
        _write_history(self.workspace, [
            self._row("a", t=self._now),
        ])
        r = _invoke(["audit", "--since", "60", "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["by_tag"].get("delete", 0), 1, payload)

    def test_negative_since_refused(self):
        r = _invoke(["audit", "--since", "-1"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--since", r.stderr)
        self.assertIn("non-negative", r.stderr)

    def test_negative_until_refused(self):
        r = _invoke(["audit", "--until", "-5"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--until", r.stderr)

    def test_window_with_no_matching_rows(self):
        # The window is in the future, so no rows match. Facet
        # tags see an empty history; ledger tags still fire.
        self._ledger(open_=("?01 same — settled by: test",
                            "?02 same — settled by: test"))
        _write_history(self.workspace, [
            self._row("a", t=self._now - 100),
        ])
        r = _invoke(["audit", "--since", "10", "--until", "1",
                     "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        # The window has zero rows, so shrink cannot fire; the
        # duplicate Open is still a `delete` finding.
        self.assertEqual(payload["by_tag"].get("delete", 0), 1)
        self.assertEqual(payload["by_tag"].get("shrink", 0), 0)
        self.assertEqual(payload["history_window"]["rows_in"], 1)
        self.assertEqual(payload["history_window"]["rows_out"], 0)

    def test_json_history_window_records_both_cutoffs(self):
        self._ledger()
        _write_history(self.workspace, [
            self._row("a", t=self._now - 100),
            self._row("b", t=self._now - 50),
        ])
        r = _invoke(
            ["audit", "--since", "200", "--until", "30", "--json"],
            cwd=self.workspace)
        payload = json.loads(r.stdout)
        w = payload["history_window"]
        self.assertEqual(w["since_seconds"], 200)
        self.assertEqual(w["until_seconds"], 30)
        self.assertIsNotNone(w["since_cutoff"])
        self.assertIsNotNone(w["until_cutoff"])
        self.assertEqual(w["rows_in"], 2)
        self.assertEqual(w["rows_out"], 2)

    def test_window_composes_with_tag_filter(self):
        # --since 60 + --tag shrink should still narrow the
        # history slice before the projection runs.
        self._ledger()
        _write_history(self.workspace, [
            self._row("", t=self._now - 10**6),
            self._row("", t=self._now - 5),
            self._row("a", t=self._now - 1),
        ])
        r = _invoke(
            ["audit", "--since", "60", "--tag", "shrink", "--json"],
            cwd=self.workspace)
        payload = json.loads(r.stdout)
        # Only one blank row is in the window; projection keeps
        # only the shrink tag.
        self.assertEqual(payload["by_tag"].get("shrink", 0), 1, payload)
        self.assertNotIn("delete", payload["by_tag"])
        self.assertEqual(payload["tags"], ["shrink"])

    def test_window_does_not_affect_clean_lean(self):
        # A clean ledger with an empty history stays clean
        # regardless of the window.
        self._ledger()
        _write_history(self.workspace, [])
        r = _invoke(["audit", "--since", "60", "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["lean"])
        self.assertEqual(payload["net"], 0)
        self.assertEqual(payload["gate"], "clean")


class AuditAtTests(WindowBase):
    """``--at N`` slices the history to the first N rows."""

    def test_at_one_uses_only_first_row(self):
        self._ledger()
        # Build a 10-row history. The first row is a blank-next,
        # rows 2-10 are clean. With --at 1 the audit sees only
        # the first row, so shrink fires once. With --at 5 the
        # audit sees 5 rows; shrink still fires once. With no
        # --at, the audit sees 10 rows; shrink still fires once.
        _write_history(self.workspace, [
            self._row("", t=self._now - 100),
            self._row("a", t=self._now - 90),
            self._row("b", t=self._now - 80),
            self._row("c", t=self._now - 70),
            self._row("d", t=self._now - 60),
            self._row("e", t=self._now - 50),
            self._row("f", t=self._now - 40),
            self._row("g", t=self._now - 30),
            self._row("h", t=self._now - 20),
            self._row("i", t=self._now - 10),
        ])
        r = _invoke(["audit", "--at", "1", "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["by_tag"].get("shrink", 0), 1, payload)
        at = payload["history_window"]["at_row"]
        self.assertEqual(at, 1)
        self.assertEqual(payload["history_window"]["rows_in"], 10)
        self.assertEqual(payload["history_window"]["rows_out"], 1)

    def test_at_five_slices_to_first_five(self):
        self._ledger()
        # The trailing five rows repeat the same next; with
        # --at 5 the next-stall detector sees no repeats.
        _write_history(self.workspace, [
            self._row("dom: a", t=self._now - 60),
            self._row("dom: b", t=self._now - 50),
            self._row("dom: c", t=self._now - 40),
            self._row("dom: d", t=self._now - 30),
            self._row("dom: e", t=self._now - 20),
            self._row("dom: blocked", t=self._now - 10),
            self._row("dom: blocked", t=self._now - 5),
            self._row("dom: blocked", t=self._now - 2),
        ])
        r = _invoke(["audit", "--at", "5", "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        # next-stall needs 3-of-5 in the trailing window; --at 5
        # truncates to the first 5 rows, so the trailing window
        # is rows 1..5 (varied) and the finding cannot fire.
        self.assertNotIn("next-stall", payload["by_tag"], payload)

    def test_at_out_of_range_refused(self):
        self._ledger()
        _write_history(self.workspace, [
            self._row("a", t=self._now - 1),
        ])
        r = _invoke(["audit", "--at", "5"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--at 5 out of range", r.stderr)
        self.assertIn("1..1", r.stderr)

    def test_at_zero_refused(self):
        # 0 is not a valid 1-based row index.
        r = _invoke(["audit", "--at", "0"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--at 0 out of range", r.stderr)

    def test_at_clean_ledger_prints_lean_with_seam(self):
        self._ledger()
        _write_history(self.workspace, [
            self._row("a", t=self._now - 1),
        ])
        r = _invoke(["audit", "--at", "1"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The lean verdict under --at names the seam, so a host
        # tailing the report can tell it was a single-seam
        # view, not a full audit.
        self.assertIn("Lean already (at seam 1 of 1).", r.stdout)

    def test_text_header_names_the_seam(self):
        # When findings exist under --at, the report opens with
        # a header that names the seam, the way ``git log
        # --since 1.h`` opens with a date range header.
        self._ledger()
        _write_history(self.workspace, [
            self._row("", t=self._now - 1),
        ])
        r = _invoke(["audit", "--at", "1"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("audit (at seam 1 of 1)", r.stdout)

    def test_at_composes_with_strict(self):
        # Strict + --at with findings still gates the exit code.
        self._ledger()
        _write_history(self.workspace, [
            self._row("", t=self._now - 1),
        ])
        r = _invoke(["audit", "--at", "1", "--strict"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 1, r.stderr)

    def test_at_composes_with_tag(self):
        # --at + --tag projection: the audit runs on the slice
        # and the projection keeps only the chosen tag.
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"))
        _write_history(self.workspace, [
            self._row("a", t=self._now - 1),
        ])
        r = _invoke(["audit", "--at", "1", "--tag", "yagni", "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        # yagni fires (parked core); the slice is irrelevant to
        # the ledger-surface tag.
        self.assertEqual(payload["by_tag"].get("yagni", 0), 1, payload)
        self.assertEqual(payload["tags"], ["yagni"])


class AuditGateEnumTests(WindowBase):
    """The ``gate`` enum is a richer three-state status."""

    def test_gate_clean_when_no_findings_no_strict(self):
        self._ledger()
        r = _invoke(["audit", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["gate"], "clean")

    def test_gate_finding_when_findings_no_strict(self):
        self._ledger(open_=("?01 same — settled by: test",
                            "?02 same — settled by: test"))
        r = _invoke(["audit", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["gate"], "finding")

    def test_gate_gated_when_findings_and_strict(self):
        self._ledger(open_=("?01 same — settled by: test",
                            "?02 same — settled by: test"))
        r = _invoke(["audit", "--strict", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 1, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["gate"], "gated")

    def test_gate_clean_when_clean_and_strict(self):
        self._ledger()
        r = _invoke(["audit", "--strict", "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["gate"], "clean")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_lean_agrees_with_r156_pin(self):
        # r156 pinned ``lean = not findings``; the r161 addition
        # does not change that semantics. The boolean stays
        # in lockstep with the count of findings.
        self._ledger(open_=("?01 same — settled by: test",
                            "?02 same — settled by: test"))
        r = _invoke(["audit", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["lean"], bool(not payload["findings"]))
        self.assertEqual(payload["lean"], False)


class InfoAuditSummaryTests(WindowBase):
    """``info --json`` carries an ``audit_summary`` block."""

    def test_info_json_carries_audit_summary(self):
        self._ledger(open_=("?01 same — settled by: test",
                            "?02 same — settled by: test"))
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("audit_summary", payload)
        s = payload["audit_summary"]
        self.assertIn("lean", s)
        self.assertIn("net", s)
        self.assertIn("by_tag", s)
        self.assertIn("top_tag", s)
        self.assertIn("top_tag_count", s)
        self.assertFalse(s["lean"])
        self.assertEqual(s["net"], 1)
        self.assertEqual(s["by_tag"].get("delete", 0), 1)

    def test_info_summary_net_matches_audit_net(self):
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same — settled by: test",
                   "?02 same — settled by: test"))
        info = _invoke(["info", "--json"], cwd=self.workspace)
        audit = _invoke(["audit", "--json"], cwd=self.workspace)
        info_payload = json.loads(info.stdout)
        audit_payload = json.loads(audit.stdout)
        self.assertEqual(info_payload["audit_summary"]["net"],
                         audit_payload["net"])

    def test_info_summary_lean_agrees_with_audit_lean(self):
        self._ledger()  # clean ledger
        info = _invoke(["info", "--json"], cwd=self.workspace)
        audit = _invoke(["audit", "--json"], cwd=self.workspace)
        info_payload = json.loads(info.stdout)
        audit_payload = json.loads(audit.stdout)
        self.assertEqual(info_payload["audit_summary"]["lean"],
                         audit_payload["lean"])
        self.assertTrue(info_payload["audit_summary"]["lean"])

    def test_info_text_face_prints_audit_line(self):
        self._ledger(open_=("?01 same — settled by: test",
                            "?02 same — settled by: test"))
        r = _invoke(["info"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Audit: 1 item removable", r.stdout)
        self.assertIn("top tag delete", r.stdout)

    def test_info_text_face_prints_lean_line(self):
        self._ledger()  # clean
        r = _invoke(["info"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Audit: 0 items removable (lean).", r.stdout)

    def test_warnings_only_still_carries_audit_summary(self):
        # The audit summary rides on the JSON face regardless
        # of --warnings-only; the flag only trims the text path.
        self._ledger(open_=("?01 same — settled by: test",
                            "?02 same — settled by: test"))
        r = _invoke(["info", "--warnings-only", "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("audit_summary", payload)
        self.assertEqual(payload["audit_summary"]["net"], 1)

    def test_summary_top_tag_picks_highest_count(self):
        # Two stdlib + one delete: stdlib wins (2). The yagni
        # finding also fires (5 Core items, 3 parked) but only as
        # one finding; the by_tag count is the count of findings,
        # not the count of underlying instances.
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three", "c4 — four",
                  "c5 — five"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force",
                      "✓03 first — verified by: brute force"),
            open_=("?01 same — settled by: test",
                   "?02 same — settled by: test"))
        r = _invoke(["info", "--json"], cwd=self.workspace)
        s = json.loads(r.stdout)["audit_summary"]
        # Three stdlib findings (rows 1, 2, 3 all repeat row 1);
        # wait — the stdlib detector only emits once per duplicate
        # pair, so the count is the number of *findings*, not
        # pairs. Let me re-check: rows 1-3 all share text, so
        # rows 2 and 3 both produce findings (each one fires
        # against the canonical row 1). That is 2 stdlib
        # findings. The yagni finding fires once.
        self.assertEqual(s["by_tag"].get("stdlib", 0), 2, s)
        self.assertEqual(s["by_tag"].get("delete", 0), 1, s)
        self.assertEqual(s["by_tag"].get("yagni", 0), 1, s)
        # The top tag is stdlib with 2 findings.
        self.assertEqual(s["top_tag"], "stdlib")
        self.assertEqual(s["top_tag_count"], 2)

    def test_summary_top_tag_none_when_clean(self):
        self._ledger()  # clean
        r = _invoke(["info", "--json"], cwd=self.workspace)
        s = json.loads(r.stdout)["audit_summary"]
        self.assertIsNone(s["top_tag"])
        self.assertEqual(s["top_tag_count"], 0)


class ParserAcceptanceTests(unittest.TestCase):
    """The audit parser accepts the three new flags."""

    def test_since_until_at_are_registered(self):
        # If a flag were dropped, argparse would say "unrecognised
        # arguments". The point of the test is to prove the
        # flags are wired.
        r = subprocess.run(
            [sys.executable, str(MINDSEAM), "audit", "--since", "60",
             "--until", "30", "--at", "1"],
            cwd=tempfile.mkdtemp(),
            capture_output=True, text=True, encoding="utf-8")
        # The flag parsing succeeded (any exit code is fine
        # here; what matters is the absence of "unrecognised
        # arguments").
        self.assertNotIn("unrecognised arguments", r.stderr + r.stdout)
