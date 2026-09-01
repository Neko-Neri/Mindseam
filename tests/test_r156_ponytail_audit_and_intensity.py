# -*- coding: utf-8 -*-
"""Round 156 guards: the ponytail audit and the intensity ladder.

Borrowed from DietrichGebert/ponytail (MIT): a read-only audit that
emits tagged one-line findings ranked biggest first and closes with
"Lean already. Ship." when there is nothing to cut, plus a verbosity
ladder resolved as flag > MINDSEAM_INTENSITY > full. Ponytail audits
code for over-engineering; the seam audit applies the same shape to
the ledger. The guards pin the tag set, the report-only exit contract,
the lean verdict, the strict gate, the lite cap with its held-back
line, the off refusal, and the JSON face carrying the full list under
every intensity.
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


class AuditBase(unittest.TestCase):

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

    def _ledger(self, core=(), verified=(), open_=()):
        ledger_dir = Path(self.workspace) / ".mindseam"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        path = ledger_dir / "WORKSPACE.md"
        text = ["# Mindseam Workspace Ledger", ""]
        text += ["## Goal", "audit demo", ""]
        text += ["## Core"] + list(core) + [""]
        text += ["## Verified"] + list(verified) + [""]
        text += ["## Open"] + list(open_) + [""]
        text += ["## Next", "dom: work", ""]
        path.write_text("\n".join(text), encoding="utf-8")


class IntensityResolutionTests(unittest.TestCase):

    def test_default_is_full(self):
        self.assertEqual(mindseam.resolve_intensity(None), "full")

    def test_blank_env_falls_through_to_full(self):
        self.assertEqual(mindseam.resolve_intensity("  "), "full")

    def test_flag_beats_environment(self):
        self.assertEqual(
            mindseam.resolve_intensity("lite"), "lite")
        os.environ["MINDSEAM_INTENSITY"] = "off"
        try:
            self.assertEqual(
                mindseam.resolve_intensity("lite"), "lite",
                "the flag must beat the environment variable")
        finally:
            os.environ.pop("MINDSEAM_INTENSITY", None)

    def test_environment_variable_is_honoured(self):
        os.environ["MINDSEAM_INTENSITY"] = "lite"
        try:
            self.assertEqual(mindseam.resolve_intensity(None), "lite")
        finally:
            os.environ.pop("MINDSEAM_INTENSITY", None)


class AuditFindingTests(AuditBase):

    def test_clean_ledger_is_lean(self):
        self._open()
        r = _invoke(["audit"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Lean already. Ship.", r.stdout)
        self.assertNotIn("delete", r.stdout)

    def test_duplicate_open_is_a_delete_finding(self):
        self._ledger(open_=("?01 same question — settled by: test a",
                            "?02 same question — settled by: test a"))
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), [])
        self.assertEqual(len(findings), 1, findings)
        self.assertEqual(findings[0]["tag"], "delete")
        self.assertIn("repeats", findings[0]["what"])

    def test_duplicate_verified_is_a_stdlib_finding(self):
        self._ledger(verified=("✓01 first check — verified by: brute force",
                               "✓02 first check — verified by: brute force"))
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), [])
        self.assertEqual([f["tag"] for f in findings], ["stdlib"], findings)

    def test_parked_core_is_yagni(self):
        self._ledger(core=("c1 — one", "c2 — two", "c3 — three"))
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), [])
        self.assertEqual([f["tag"] for f in findings], ["yagni"], findings)

    def test_blank_history_nexts_are_shrink(self):
        self._open()
        findings = mindseam.audit_findings(
            mindseam.read_ledger(),
            [{"next": "", "verified": 0, "open": 0}])
        self.assertEqual([f["tag"] for f in findings], ["shrink"], findings)

    def test_tags_rank_delete_before_stdlib_before_yagni(self):
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            verified=("✓01 first check — verified by: brute force",
                      "✓02 first check — verified by: brute force"),
            open_=("?01 same question — settled by: test a",
                   "?02 same question — settled by: test a"))
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), [])
        self.assertEqual(
            [f["tag"] for f in findings],
            ["delete", "stdlib", "yagni"], findings)


class AuditReportContractTests(AuditBase):

    def test_report_only_never_gates_by_default(self):
        self._ledger(open_=("?01 same question — settled by: test a",
                            "?02 same question — settled by: test a"))
        r = _invoke(["audit"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("delete", r.stdout)
        self.assertIn("Net: 1 item removable.", r.stdout)

    def test_strict_turns_findings_into_a_gate(self):
        self._ledger(open_=("?01 same question — settled by: test a",
                            "?02 same question — settled by: test a"))
        r = _invoke(["audit", "--strict"], cwd=self.workspace)
        self.assertEqual(r.returncode, 1, r.stderr)

    def test_strict_clean_still_exits_zero(self):
        self._open()
        r = _invoke(["audit", "--strict"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Lean already. Ship.", r.stdout)

    def test_finding_line_shape_matches_ponytail(self):
        self._ledger(open_=("?01 same question — settled by: test a",
                            "?02 same question — settled by: test a"))
        r = _invoke(["audit"], cwd=self.workspace)
        line = next(l for l in r.stdout.splitlines() if l.startswith("delete"))
        # <tag> <what to cut>. <replacement>.
        self.assertRegex(line, r"^delete .+\. .+\.$")


class AuditIntensityTests(AuditBase):

    def _wasteful(self):
        self._ledger(open_=("?01 same question — settled by: test a",
                            "?02 same question — settled by: test a"))

    def test_full_prints_every_finding(self):
        self._wasteful()
        r = _invoke(["audit", "--intensity", "full"], cwd=self.workspace)
        self.assertNotIn("more finding", r.stdout)

    def test_lite_caps_at_three_and_says_how_many_were_held_back(self):
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three",
                  "c4 — four", "c5 — five"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same question — settled by: test a",
                   "?02 same question — settled by: test a"))
        # One parked-core finding plus two duplicates is three; a
        # blank-next history row adds the fourth so the cap actually
        # holds something back.
        hist_dir = Path(self.workspace) / ".mindseam"
        (hist_dir / "history.json").write_text(
            json.dumps([{"t": 1, "next": "", "verified": 0, "open": 0}]),
            encoding="utf-8")
        r = _invoke(["audit", "--intensity", "lite"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        body = [l for l in r.stdout.splitlines()
                if l.startswith(("delete", "stdlib", "yagni", "shrink"))]
        self.assertEqual(len(body), 3, r.stdout)
        self.assertIn("+1 more finding", r.stdout)

    def test_off_refuses_to_run(self):
        self._wasteful()
        r = _invoke(["audit", "--intensity", "off"], cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("audit intensity is off", r.stdout)

    def test_environment_variable_sets_the_level(self):
        self._wasteful()
        r = _invoke(["audit"], cwd=self.workspace,
                    env={"MINDSEAM_INTENSITY": "lite"})
        self.assertIn("Net: 1 item removable.", r.stdout)
        full = _invoke(["audit", "--intensity", "full"], cwd=self.workspace)
        self.assertNotIn("more finding", full.stdout)

    def test_flag_beats_environment_on_the_cli(self):
        self._wasteful()
        r = _invoke(["audit", "--intensity", "full"],
                    cwd=self.workspace, env={"MINDSEAM_INTENSITY": "lite"})
        self.assertNotIn("more finding", r.stdout)

    def test_json_face_carries_the_full_list_under_lite(self):
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three",
                  "c4 — four", "c5 — five"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same question — settled by: test a",
                   "?02 same question — settled by: test a"))
        (Path(self.workspace) / ".mindseam" / "history.json").write_text(
            json.dumps([{"t": 1, "next": "", "verified": 0, "open": 0}]),
            encoding="utf-8")
        r = _invoke(["audit", "--json", "--intensity", "lite"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertFalse(payload["lean"])
        self.assertEqual(payload["net"], len(payload["findings"]))
        self.assertEqual(payload["intensity"], "lite")
        # The dial trims prose, not data: JSON carries the full list.
        self.assertEqual(payload["net"], 4, payload)

    def test_json_lean_payload(self):
        self._open()
        r = _invoke(["audit", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["lean"])
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["intensity"], "full")


class AuditSurfaceTests(AuditBase):

    def test_audit_writes_nothing(self):
        self._open()
        before = {
            p.name: p.read_text(encoding="utf-8")
            for p in (Path(self.workspace) / ".mindseam").iterdir()
        }
        _invoke(["audit"], cwd=self.workspace)
        after = {
            p.name: p.read_text(encoding="utf-8")
            for p in (Path(self.workspace) / ".mindseam").iterdir()
        }
        self.assertEqual(before, after)

    def test_audit_is_a_registered_subcommand(self):
        r = _invoke(["--help"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("audit", r.stdout)


if __name__ == "__main__":
    unittest.main()
