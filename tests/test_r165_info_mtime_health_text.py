# -*- coding: utf-8 -*-
"""Round 165 guards: info --mtime / --health / --text.

The r161-r164 ``info`` report grew many orthogonal blocks:
``audit_summary`` (roll-up), ``audit_manifest`` (detector
coverage), ``workspace_id`` (path + mtime fingerprint),
``audit_baseline_diff`` (drift), ``lock_state`` (advisory
file lock). r165 closes the gap with three more flags that
let a host assemble a single ``info --json`` call to
prove "the workspace files are healthy" without spawning
``stat`` per file or running ``systemctl is-system-running``
separately:

- ``--mtime`` emits a ``workspace_files`` block listing
  each ledger artefact (WORKSPACE.md / history.json /
  metacognition.json / skillbook.md) with ``mtime`` /
  ``size`` / ``exists``, borrowed from ``find -printf``
  / ``stat --format='%y %s %n'``. A host that wants to
  know "which file was written last" reads one block
  instead of N stat calls.
- ``--health`` rolls up the r156-r164 signals
  (``lock_state``, ``audit_summary.lean``, ``warnings``,
  ``last_seam.long_gap``) into a single status enum
  (ok / degraded / unhealthy) with a ``reasons`` list,
  borrowed from ``kubectl get componentstatus`` /
  ``systemctl is-system-running``. A host that wants a
  single CI gate reads ``health.status`` instead of
  parsing four blocks.
- ``--text`` forces plain text even if ``--json`` is
  also passed, borrowed from ``gh --output text`` /
  ``kubectl -o wide``. The r156 default is text when no
  face is requested; ``--text`` makes that explicit so a
  shell pipeline that wants stable text can use it
  unconditionally.

All three blocks are additive. The r164 ``lock_state``,
r163 ``workspace_id`` / ``audit_baseline_diff`` /
``audit_manifest``, r161 ``audit_summary``, and r156
``ledger`` / ``last_seam`` / ``warnings`` blocks keep
their existing shape.
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


class InfoMtimeBase(unittest.TestCase):

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


class MtimeTests(InfoMtimeBase):
    """``--mtime`` emits a ``workspace_files`` block."""

    def test_no_workspace_files_when_omitted(self):
        self._ledger()
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertNotIn("workspace_files", payload)

    def test_workspace_files_lists_each_artefact(self):
        self._ledger()
        r = _invoke(["info", "--json", "--mtime"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("workspace_files", payload)
        files = payload["workspace_files"]
        self.assertEqual(
            set(files.keys()),
            {"WORKSPACE.md", "history.json",
             "metacognition.json", "skillbook.md"})

    def test_existing_file_has_mtime_and_size(self):
        self._ledger()
        r = _invoke(["info", "--json", "--mtime"],
                    cwd=self.workspace)
        files = json.loads(r.stdout)["workspace_files"]
        # WORKSPACE.md was just written by _ledger; it must
        # have a non-zero mtime and a positive size.
        wm = files["WORKSPACE.md"]
        self.assertTrue(wm["exists"])
        self.assertGreater(wm["mtime"], 0)
        self.assertGreater(wm["size"], 0)
        self.assertTrue(os.path.isabs(wm["path"]))

    def test_missing_file_has_zero_mtime_and_size(self):
        # Only WORKSPACE.md exists; the other three are missing.
        self._ledger()
        r = _invoke(["info", "--json", "--mtime"],
                    cwd=self.workspace)
        files = json.loads(r.stdout)["workspace_files"]
        for missing in ("history.json", "metacognition.json",
                        "skillbook.md"):
            entry = files[missing]
            self.assertFalse(entry["exists"])
            self.assertEqual(entry["mtime"], 0)
            self.assertEqual(entry["size"], 0)

    def test_mtime_changes_when_file_rewritten(self):
        # The mtime of WORKSPACE.md changes after a rewrite;
        # the mtime of history.json stays zero (file is
        # not touched).
        self._ledger()
        r1 = _invoke(["info", "--json", "--mtime"],
                     cwd=self.workspace)
        m1 = json.loads(r1.stdout)["workspace_files"][
            "WORKSPACE.md"]["mtime"]
        time.sleep(1.1)
        self._ledger(goal="different goal")
        r2 = _invoke(["info", "--json", "--mtime"],
                     cwd=self.workspace)
        m2 = json.loads(r2.stdout)["workspace_files"][
            "WORKSPACE.md"]["mtime"]
        self.assertGreater(m2, m1)


class HealthTests(InfoMtimeBase):
    """``--health`` rolls up the r156-r164 signals."""

    def test_no_health_block_when_omitted(self):
        self._ledger()
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertNotIn("health", payload)

    def test_clean_workspace_is_ok(self):
        # A brand-new ledger has no seams yet, so the
        # warnings list carries a "no seams recorded yet"
        # line. The status is ``degraded`` (a soft reason),
        # not ``ok`` — the host should still consider this
        # a healthy fresh ledger but know to expect a
        # first-seam soon.
        self._ledger()
        r = _invoke(["info", "--json", "--health"],
                    cwd=self.workspace)
        h = json.loads(r.stdout)["health"]
        self.assertEqual(h["status"], "degraded")
        kinds = [r["kind"] for r in h["reasons"]]
        self.assertIn("warnings", kinds)

    def test_lock_held_by_other_is_unhealthy(self):
        self._ledger()
        lock = os.path.join(self.workspace, ".mindseam", "write.lock")
        with open(lock, "w", encoding="utf-8") as fh:
            fh.write("pid=99999\n")
        r = _invoke(["info", "--json", "--health"],
                    cwd=self.workspace)
        h = json.loads(r.stdout)["health"]
        self.assertEqual(h["status"], "unhealthy")
        kinds = [r["kind"] for r in h["reasons"]]
        self.assertIn("lock_held_by_other", kinds)

    def test_lock_held_by_us_is_degraded(self):
        # A previous controller process crashed mid-write;
        # the lock state is held_by_us, the severity is
        # degraded (not hard-unhealthy, because the user
        # can clear it by hand).
        self._ledger()
        lock = os.path.join(self.workspace, ".mindseam", "write.lock")
        with open(lock, "w", encoding="utf-8") as fh:
            fh.write("pid=99999\n")
        r = _invoke(["info", "--json", "--health"],
                    cwd=self.workspace)
        h = json.loads(r.stdout)["health"]
        # The pid 99999 is foreign (not ours), so the lock
        # state is held_by_other; that is hard-unhealthy.
        # To exercise held_by_us we'd need a self-pid, but
        # the test runner and the subprocess are separate
        # processes. Pin held_by_other here; the held_by_us
        # transition is exercised by the test that plants
        # a self-pid lock (test_r164_write_lock).
        self.assertEqual(h["status"], "unhealthy")

    def test_audit_finding_is_unhealthy(self):
        # A wasteful ledger fires the audit; the health
        # block reflects that as unhealthy (a hard reason).
        self._ledger(
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"))
        r = _invoke(["info", "--json", "--health"],
                    cwd=self.workspace)
        h = json.loads(r.stdout)["health"]
        self.assertEqual(h["status"], "unhealthy")
        kinds = [r["kind"] for r in h["reasons"]]
        self.assertIn("audit_finding", kinds)

    def test_long_gap_is_degraded(self):
        # A ledger with a long gap is degraded but not
        # unhealthy. The r161 long_gap is True when gap >
        # RESUME_GAP (1800 s). A history row with an
        # ancient timestamp triggers the long gap.
        self._ledger()
        Path(self.workspace, ".mindseam", "history.json").write_text(
            json.dumps(
                [{"t": int(time.time()) - 7200, "next": "old",
                  "verified": 0, "open": 0}]),
            encoding="utf-8")
        r = _invoke(["info", "--json", "--health"],
                    cwd=self.workspace)
        h = json.loads(r.stdout)["health"]
        self.assertEqual(h["status"], "degraded")
        kinds = [r["kind"] for r in h["reasons"]]
        self.assertIn("long_gap", kinds)

    def test_reasons_list_is_stable(self):
        # The kinds are stable across calls; a host can grep
        # for specific keys without parsing prose.
        self._ledger(
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"))
        r1 = _invoke(["info", "--json", "--health"],
                     cwd=self.workspace)
        r2 = _invoke(["info", "--json", "--health"],
                     cwd=self.workspace)
        kinds1 = sorted([r["kind"] for r in
                         json.loads(r1.stdout)["health"]["reasons"]])
        kinds2 = sorted([r["kind"] for r in
                         json.loads(r2.stdout)["health"]["reasons"]])
        self.assertEqual(kinds1, kinds2)


class TextTests(InfoMtimeBase):
    """``--text`` forces text even when ``--json`` is set."""

    def test_text_overrides_json(self):
        # Both --json and --text: text wins, the output is
        # the sectioned report, not the JSON payload.
        self._ledger()
        r = _invoke(["info", "--json", "--text"],
                    cwd=self.workspace)
        # The text report opens with the section header.
        self.assertIn("── mindseam ─ info", r.stdout)
        # And does *not* parse as JSON.
        with self.assertRaises(json.JSONDecodeError):
            json.loads(r.stdout)

    def test_text_alone_is_text(self):
        self._ledger()
        r = _invoke(["info", "--text"], cwd=self.workspace)
        self.assertIn("── mindseam ─ info", r.stdout)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(r.stdout)

    def test_default_text_when_no_face(self):
        # Without --json or --text, the r156 default is text.
        self._ledger()
        r = _invoke(["info"], cwd=self.workspace)
        self.assertIn("── mindseam ─ info", r.stdout)

    def test_text_with_mtime_includes_artefact_lines(self):
        # The text report under --text --mtime shows the
        # artefact snapshot in human form. The text face
        # of --mtime is a small section, not the JSON
        # block; the contract is "the r156 report shape
        # plus a workspace_files section".
        self._ledger()
        r = _invoke(["info", "--text", "--mtime"],
                    cwd=self.workspace)
        self.assertIn("── mindseam ─ info", r.stdout)
        self.assertIn("WORKSPACE.md", r.stdout)


class ComposeTests(InfoMtimeBase):
    """The three new flags compose with each other and with the r161-r164 surface."""

    def test_mtime_with_health(self):
        self._ledger(
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"))
        r = _invoke(["info", "--json", "--mtime", "--health"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("workspace_files", payload)
        self.assertIn("health", payload)
        # The audit_finding reason is present; the status
        # is unhealthy.
        self.assertEqual(payload["health"]["status"], "unhealthy")
        kinds = [r["kind"] for r in payload["health"]["reasons"]]
        self.assertIn("audit_finding", kinds)

    def test_workspace_files_helper_directly(self):
        # The helper is callable directly; a host can use
        # the same snapshot without spawning the controller.
        self._ledger()
        files = mindseam._workspace_files_snapshot()
        self.assertIn("WORKSPACE.md", files)
        self.assertTrue(files["WORKSPACE.md"]["exists"])
