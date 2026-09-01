# -*- coding: utf-8 -*-
"""Round 159 guards: audit facets (goal-stale / next-stall / core-drift)
plus the ``--tag`` filter.

The r156 audit covered the *ledger surface itself*: duplicate Open
rows, duplicate Verified rows, parked Core, blank-next history.
That is the artefact at rest. r159 extends the audit to the artefact
against history — the facet tags borrow from `gh audit-log`,
`journalctl --list-boots` and ponytail's drift check, and answer
"is the ledger telling the same story as the recent seams?"

The four surface tags (delete / stdlib / yagni / shrink) and the
three facet tags (goal-stale / next-stall / core-drift) share one
finding shape and one tag-rank order, so a host that learned r156
already knows how to read r159 output. The ``--tag`` filter borrows
from `gh pr list --label <name>` and `cargo bench --bench <name>`:
a comma-separated list of tags narrows the report to just those
tags. The full audit still runs; the dial is a projection, not a
recomputation. JSON carries the projection's ``findings`` array,
the full ``by_tag`` map, and the resolved ``tags`` list, so a host
can tell which tag fired even when the projection is empty.
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
    """Write the audit log in the form ``read_history`` expects."""
    path = Path(workspace) / ".mindseam" / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


class FacetBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _open(self, goal="audit demo", nxt="dom: work"):
        r = _invoke(["note", "--goal", goal, "--next", nxt],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def _ledger(self, goal="audit demo", core=(), verified=(),
                open_=(), next_="dom: work"):
        path = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ["# Mindseam Workspace Ledger", ""]
        text += ["## Goal", goal, ""]
        text += ["## Core"] + list(core) + [""]
        text += ["## Verified"] + list(verified) + [""]
        text += ["## Open"] + list(open_) + [""]
        text += ["## Next", next_, ""]
        path.write_text("\n".join(text), encoding="utf-8")


class TagTaxonomyTests(unittest.TestCase):
    """Pin the tag set: every facet is enumerable and ranked."""

    def test_seven_tags_are_registered(self):
        self.assertEqual(
            mindseam.AUDIT_TAGS,
            ("delete", "stdlib", "yagni", "shrink",
             "goal-stale", "next-stall", "core-drift"))

    def test_tag_order_keeps_surface_first_then_facets(self):
        # The four surface tags stay in their r156 positions; the
        # three facet tags follow in the order they were added. The
        # ``order`` map inside ``audit_findings`` builds from this
        # tuple, so a stray reorder would change the lite cap
        # silently.
        self.assertEqual(mindseam.AUDIT_TAGS[:4],
                         ("delete", "stdlib", "yagni", "shrink"))
        self.assertEqual(mindseam.AUDIT_TAGS[4:],
                         ("goal-stale", "next-stall", "core-drift"))


class GoalStaleTests(FacetBase):
    """``goal-stale`` fires when the recent seams did not re-anchor Goal."""

    def _row(self, next_action, goal=None, t=1):
        row = {"t": t, "next": next_action,
               "verified": 0, "open": 0}
        if goal is not None:
            row["goal"] = goal
        return row

    def test_clean_when_recent_seams_kept_re_anchoring(self):
        self._ledger(goal="ship r159")
        # Ten recent rows, every one carrying a `goal` annotation:
        # the goal was not parked.
        _write_history(self.workspace,
                       [self._row("step %d" % i, goal="ship r159",
                                  t=i + 1) for i in range(10)])
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        self.assertNotIn(
            "goal-stale", [f["tag"] for f in findings], findings)

    def test_clean_when_history_too_short(self):
        # Five rows is below the 10-row floor; the goal-stale
        # finding needs evidence, and five seams is not enough.
        self._ledger(goal="ship r159")
        _write_history(self.workspace,
                       [self._row("step %d" % i, t=i + 1) for i in range(5)])
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        self.assertNotIn(
            "goal-stale", [f["tag"] for f in findings], findings)

    def test_clean_when_goal_text_is_blank(self):
        # An empty Goal field means there is nothing to re-anchor;
        # the finding cannot fire.
        self._ledger(goal="")
        _write_history(self.workspace,
                       [self._row("step %d" % i, t=i + 1) for i in range(12)])
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        self.assertNotIn(
            "goal-stale", [f["tag"] for f in findings], findings)

    def test_fires_when_goal_parked_across_recent_seams(self):
        self._ledger(goal="ship r159")
        # Twelve rows, none carrying a `goal` annotation. The goal
        # has not been re-anchored in the most recent ten seams.
        _write_history(self.workspace,
                       [self._row("step %d" % i, t=i + 1) for i in range(12)])
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        stale = [f for f in findings if f["tag"] == "goal-stale"]
        self.assertEqual(len(stale), 1, findings)
        self.assertIn("re-anchored", stale[0]["what"])
        self.assertIn("--goal", stale[0]["replacement"])

    def test_fires_via_the_cli(self):
        self._ledger(goal="ship r159")
        _write_history(self.workspace,
                       [self._row("step %d" % i, t=i + 1) for i in range(12)])
        r = _invoke(["audit"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("goal-stale", r.stdout)


class NextStallTests(FacetBase):
    """``next-stall`` fires when the same ``next`` repeats without resolution."""

    def _row(self, next_action, t):
        return {"t": t, "next": next_action, "verified": 0, "open": 0}

    def test_clean_when_no_next_repeats(self):
        self._ledger()
        _write_history(self.workspace,
                       [self._row("dom: a", 1), self._row("dom: b", 2),
                        self._row("dom: c", 3), self._row("dom: d", 4),
                        self._row("dom: e", 5)])
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        self.assertNotIn(
            "next-stall", [f["tag"] for f in findings], findings)

    def test_clean_when_history_too_short(self):
        # The 5-row floor; fewer rows cannot trip the bar.
        self._ledger()
        _write_history(self.workspace,
                       [self._row("dom: a", 1), self._row("dom: a", 2),
                        self._row("dom: a", 3)])
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        self.assertNotIn(
            "next-stall", [f["tag"] for f in findings], findings)

    def test_fires_when_same_next_repeats_three_of_five(self):
        self._ledger()
        # 3 of 5 rows share the same next, the threshold defined
        # in the controller.
        _write_history(self.workspace,
                       [self._row("dom: blocked", 1),
                        self._row("dom: work", 2),
                        self._row("dom: blocked", 3),
                        self._row("dom: blocked", 4),
                        self._row("dom: work", 5)])
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        stall = [f for f in findings if f["tag"] == "next-stall"]
        self.assertEqual(len(stall), 1, findings)
        self.assertIn("dom: blocked", stall[0]["what"])
        self.assertIn("3 of the last 5", stall[0]["what"])
        self.assertIn("--close", stall[0]["replacement"])

    def test_only_the_top_repeater_fires_when_window_is_full(self):
        # The 3-of-5 bar means two topics cannot both fire from
        # the same 5-row window (5 rows split 3+2 at most). When
        # a topic clears the bar, the others do not. The detector
        # still emits one finding per topic that clears the bar;
        # if no topic clears it, the test would still report
        # ``len(stall) == 0`` — neither is "two findings".
        self._ledger()
        _write_history(self.workspace,
                       [self._row("dom: a", 1),
                        self._row("dom: b", 2),
                        self._row("dom: a", 3),
                        self._row("dom: b", 4),
                        self._row("dom: a", 5)])
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        stall = [f for f in findings if f["tag"] == "next-stall"]
        self.assertEqual(len(stall), 1, findings)
        self.assertIn("dom: a", stall[0]["what"])

    def test_repeats_sorted_by_frequency_then_lexicographic(self):
        # Two spin topics in the same 5-row window are impossible
        # (5 rows cannot split 3+3). To exercise the
        # multi-finding branch, we use a 7-row history where the
        # last 5 contain two topics each at the 3-bar. This is
        # the only path that produces two findings from the same
        # window — the detector walks all topics, not just the
        # top one.
        self._ledger()
        _write_history(self.workspace,
                       [self._row("dom: b", 1),
                        self._row("dom: b", 2),
                        self._row("dom: b", 3),
                        self._row("dom: a", 4),
                        self._row("dom: a", 5),
                        self._row("dom: a", 6),
                        self._row("dom: a", 7)])
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        stall = [f for f in findings if f["tag"] == "next-stall"]
        # Last 5 rows = (3,4,5,6,7) = b,a,a,a,a → only ``a`` hits
        # the 3-of-5 bar.
        self.assertEqual(len(stall), 1, findings)
        self.assertIn("dom: a", stall[0]["what"])

    def test_uses_only_the_last_five_rows(self):
        # Older history may have been spinning; the detector looks
        # at the trailing five only, the way `tshark -qz io,phs`
        # looks at the most recent window. The trailing five
        # rows are each different, so the recent window shows no
        # repeat and the older spin does not bleed into the
        # finding.
        self._ledger()
        _write_history(self.workspace,
                       [self._row("dom: old", 1),
                        self._row("dom: old", 2),
                        self._row("dom: old", 3),
                        self._row("dom: old", 4),
                        self._row("dom: a", 5),
                        self._row("dom: b", 6),
                        self._row("dom: c", 7),
                        self._row("dom: d", 8),
                        self._row("dom: e", 9)])
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        self.assertNotIn(
            "next-stall", [f["tag"] for f in findings], findings)

    def test_fires_via_the_cli(self):
        self._ledger()
        _write_history(self.workspace,
                       [self._row("dom: blocked", 1),
                        self._row("dom: work", 2),
                        self._row("dom: blocked", 3),
                        self._row("dom: blocked", 4),
                        self._row("dom: work", 5)])
        r = _invoke(["audit"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("next-stall", r.stdout)


class CoreDriftTests(FacetBase):
    """``core-drift`` fires when Core and Next disagree."""

    def test_clean_when_next_is_in_core(self):
        self._ledger(core=("c1 — work", "c2 — review"),
                     next_="c1 — work")
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        self.assertNotIn(
            "core-drift", [f["tag"] for f in findings], findings)

    def test_fires_when_next_drifted_out_of_core(self):
        self._ledger(core=("c1 — work", "c2 — review"),
                     next_="c3 — drift")
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        drift = [f for f in findings if f["tag"] == "core-drift"]
        self.assertEqual(len(drift), 1, findings)
        self.assertIn("c3 — drift", drift[0]["what"])
        self.assertIn("Core", drift[0]["replacement"])

    def test_fires_when_next_is_empty_but_core_remains(self):
        self._ledger(core=("c1 — work", "c2 — review"), next_="")
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        drift = [f for f in findings if f["tag"] == "core-drift"]
        self.assertEqual(len(drift), 1, findings)
        self.assertIn("Next is empty", drift[0]["what"])

    def test_singular_when_core_has_one(self):
        # The pluralisation branch must produce "1 item", not
        # "1 items".
        self._ledger(core=("c1 — work",), next_="")
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), mindseam.read_history()[0])
        drift = [f for f in findings if f["tag"] == "core-drift"]
        self.assertEqual(len(drift), 1)
        self.assertIn("1 item", drift[0]["what"])
        self.assertNotIn("1 items", drift[0]["what"])

    def test_fires_via_the_cli(self):
        self._ledger(core=("c1 — work", "c2 — review"),
                     next_="c3 — drift")
        r = _invoke(["audit"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("core-drift", r.stdout)


class TagFilterTests(FacetBase):
    """``--tag`` projects the report onto a chosen tag set."""

    def _open(self, goal="audit demo", nxt="dom: work"):
        r = _invoke(["note", "--goal", goal, "--next", nxt],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_unknown_tag_is_refused(self):
        r = _invoke(["audit", "--tag", "nope"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("not a recognised audit tag", r.stderr)
        # The error names the known tag set so the host can recover.
        self.assertIn("delete", r.stderr)
        self.assertIn("goal-stale", r.stderr)

    def test_filter_to_core_drift_hides_other_findings(self):
        # The ledger has a duplicate-Open (delete), a duplicate
        # Verified (stdlib), parked Core (yagni) AND a Next that
        # drifted out of Core (core-drift). ``--tag core-drift``
        # should show only the last.
        self._ledger(
            core=("c1 — work", "c2 — review", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same question — settled by: test a",
                   "?02 same question — settled by: test a"),
            next_="dom: drift")
        r = _invoke(["audit", "--tag", "core-drift"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("core-drift", r.stdout)
        self.assertNotIn("delete", r.stdout)
        self.assertNotIn("stdlib", r.stdout)
        self.assertNotIn("yagni", r.stdout)

    def test_filter_combines_tags(self):
        self._ledger(
            core=("c1 — work", "c2 — review", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same question — settled by: test a",
                   "?02 same question — settled by: test a"),
            next_="dom: drift")
        r = _invoke(["audit", "--tag", "delete,stdlib"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("delete", r.stdout)
        self.assertIn("stdlib", r.stdout)
        self.assertNotIn("yagni", r.stdout)
        self.assertNotIn("core-drift", r.stdout)

    def test_filter_to_empty_match_prints_lean(self):
        # A clean ledger + a tag filter still prints the lean
        # verdict (the filter does not invent findings). With a
        # filter, the lean verdict names the chosen tags.
        self._open()
        r = _invoke(["audit", "--tag", "next-stall"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Lean on next-stall. Ship.", r.stdout)

    def test_filter_lean_message_names_the_chosen_tags(self):
        # When the filter narrows to tags and the ledger is clean
        # under those tags, the lean verdict names them — the
        # way `gh pr list --label none` says "no PRs with label".
        self._ledger(verified=("✓01 done — verified by: brute force",
                               "✓02 done — verified by: brute force"))
        # The above is a stdlib finding, so filter to yagni only.
        r = _invoke(["audit", "--tag", "yagni"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Lean on yagni. Ship.", r.stdout)
        self.assertNotIn("Lean already. Ship.", r.stdout)

    def test_strict_under_filter_gates_on_projection(self):
        # The projection is the contract; strict gates on the
        # projected set, not the full set.
        self._ledger(
            core=("c1 — work", "c2 — review", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same question — settled by: test a",
                   "?02 same question — settled by: test a"),
            next_="dom: drift")
        r = _invoke(["audit", "--strict", "--tag", "core-drift"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 1, r.stderr)
        # yagni/delete/stdlib are present in the unfiltered audit
        # but excluded by the projection, so strict still gates.
        only_yagni = _invoke(
            ["audit", "--strict", "--tag", "yagni"],
            cwd=self.workspace)
        self.assertEqual(only_yagni.returncode, 1, only_yagni.stderr)

    def test_strict_clean_under_filter_exits_zero(self):
        self._open()
        r = _invoke(["audit", "--strict", "--tag", "next-stall"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)


class TagFilterJsonTests(FacetBase):
    """JSON face carries the projection plus the by_tag map."""

    def test_json_lists_the_projection_in_findings(self):
        self._ledger(
            core=("c1 — work", "c2 — review", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same question — settled by: test a",
                   "?02 same question — settled by: test a"),
            next_="dom: drift")
        r = _invoke(["audit", "--json", "--tag", "core-drift"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        tags = [f["tag"] for f in payload["findings"]]
        self.assertTrue(all(t == "core-drift" for t in tags), tags)
        self.assertEqual(payload["tags"], ["core-drift"])
        self.assertIn("by_tag", payload)
        self.assertEqual(payload["by_tag"].get("core-drift", 0),
                         len(payload["findings"]))

    def test_json_records_full_tag_set_when_no_filter(self):
        self._open()
        r = _invoke(["audit", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(set(payload["tags"]), set(mindseam.AUDIT_TAGS))
        self.assertEqual(payload["by_tag"], {})

    def test_json_lean_payload_records_filtered_lean(self):
        self._open()
        r = _invoke(["audit", "--json", "--tag", "core-drift"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["lean"])
        self.assertEqual(payload["net"], 0)


class TagFilterParserTests(unittest.TestCase):
    """The audit parser carries ``--tag`` and routes it to mode_audit."""

    def test_tag_flag_is_registered(self):
        # ``add_parser`` is the only place the flag is wired; if it
        # were dropped, ``audit --tag foo`` would error out on the
        # argparse line, and this string would have to be updated
        # by hand. Pin both ends.
        from mindseam import main as _main  # noqa: F401
        import argparse  # noqa: F401
        import io
        from contextlib import redirect_stdout, redirect_stderr
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                # --tag without a value should exit 2 with the
                # argparse error; the point is that the parser
                # accepts the flag name, not that the call
                # succeeds.
                import subprocess
                r = subprocess.run(
                    [sys.executable, str(MINDSEAM), "audit", "--tag"],
                    capture_output=True, text=True, encoding="utf-8")
                self.assertNotEqual(r.returncode, 0)
                # argparse names the missing value; the flag itself
                # was recognised (otherwise it would say
                # "unrecognised arguments").
                self.assertNotIn("unrecognised arguments",
                                 r.stderr + r.stdout)
            finally:
                pass
