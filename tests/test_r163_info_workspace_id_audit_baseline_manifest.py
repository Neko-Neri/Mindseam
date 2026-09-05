# -*- coding: utf-8 -*-
"""Round 163 guards: the info environment proof.

The r161 ``info`` report folded the audit roll-up into the
workspace health report. r163 extends the same shape with three
small, orthogonal flags that let a host prove "I am in the
right place", "I am running the same audit baseline", and
"I am running the full detector set":

- ``--workspace-id`` emits a 16-hex SHA-1 fingerprint of the
  absolute workspace path + the ledger mtime. Stable across
  replays of the same audit on the same workspace; changes
  if the path or the ledger is rewritten. Borrowed from
  ``direnv stdlib`` / ``poetry env info`` /
  ``pytest --test-environment``.
- ``--audit-baseline <path>`` emits an ``audit_baseline_diff``
  block with ``fresh`` / ``baselined`` / ``drift`` counts,
  reusing the r162 baseline read so a single ``info --json``
  call can show "how much new debt since the last snapshot",
  the way ``flutter analyze --baseline`` lets a CI script
  detect drift without running the full analysis.
- ``--manifest`` emits an ``audit_manifest`` block listing
  every tag the audit *can* fire, including the tags that
  did not fire (seen-but-clean = 0). A host reading this
  block can tell at a glance whether the audit was actually
  comprehensive on this ledger — a missing tag means the
  detector did not run, not just that the detector found
  nothing.

All three blocks are additive; the r161 ``audit_summary``
block and the r156 ``ledger`` / ``last_seam`` / ``warnings``
blocks keep their existing shape. The three flags compose
freely with each other and with ``--json``.
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


class InfoEnvBase(unittest.TestCase):

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


class WorkspaceIdTests(InfoEnvBase):
    """``--workspace-id`` emits a stable 16-hex fingerprint."""

    def test_default_info_omits_workspace_id(self):
        # The r161 contract is preserved: a plain ``info --json``
        # does not carry the workspace_id block, so a host that
        # does not opt in sees the same shape it saw before.
        self._ledger()
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertNotIn("workspace_id", payload)

    def test_workspace_id_when_requested(self):
        self._ledger()
        r = _invoke(["info", "--json", "--workspace-id"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("workspace_id", payload)
        wid = payload["workspace_id"]
        self.assertIn("id", wid)
        self.assertIn("path", wid)
        self.assertIn("ledger_mtime", wid)
        # The id is a 16-char hex digest.
        self.assertEqual(len(wid["id"]), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in wid["id"]))
        # The path is the absolute workspace path.
        self.assertTrue(os.path.isabs(wid["path"]))
        # The mtime is an int.
        self.assertIsInstance(wid["ledger_mtime"], int)

    def test_workspace_id_stable_across_calls(self):
        self._ledger()
        r1 = _invoke(["info", "--json", "--workspace-id"],
                     cwd=self.workspace)
        r2 = _invoke(["info", "--json", "--workspace-id"],
                     cwd=self.workspace)
        id1 = json.loads(r1.stdout)["workspace_id"]["id"]
        id2 = json.loads(r2.stdout)["workspace_id"]["id"]
        self.assertEqual(id1, id2)

    def test_workspace_id_changes_when_ledger_rewritten(self):
        # Same workspace, same path, different ledger content
        # → different mtime → different id.
        self._ledger()
        r1 = _invoke(["info", "--json", "--workspace-id"],
                     cwd=self.workspace)
        id1 = json.loads(r1.stdout)["workspace_id"]["id"]
        time.sleep(1.1)  # ensure mtime delta
        self._ledger(goal="different goal")
        r2 = _invoke(["info", "--json", "--workspace-id"],
                     cwd=self.workspace)
        id2 = json.loads(r2.stdout)["workspace_id"]["id"]
        self.assertNotEqual(id1, id2)

    def test_workspace_id_changes_across_workspaces(self):
        # Two workspaces, different paths → different ids.
        self._ledger()
        r1 = _invoke(["info", "--json", "--workspace-id"],
                     cwd=self.workspace)
        other = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(other, ".mindseam"), exist_ok=True)
            Path(other, ".mindseam", "WORKSPACE.md").write_text(
                "# L\n\n## Goal\n\n## Core\n\n## Verified\n\n## Open\n\n## Next\n\n",
                encoding="utf-8")
            r2 = _invoke(["info", "--json", "--workspace-id"],
                         cwd=other)
        finally:
            import shutil
            shutil.rmtree(other, ignore_errors=True)
        id1 = json.loads(r1.stdout)["workspace_id"]["id"]
        id2 = json.loads(r2.stdout)["workspace_id"]["id"]
        self.assertNotEqual(id1, id2)

    def test_workspace_id_helper_under_cwd(self):
        # The helper is callable directly: a host can compute
        # the id without spawning the controller.
        self._ledger()
        fp = mindseam._workspace_fingerprint()
        self.assertEqual(len(fp), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in fp))


class AuditBaselineDiffTests(InfoEnvBase):
    """``--audit-baseline`` emits a drift block alongside audit_summary."""

    def test_no_diff_block_when_baseline_omitted(self):
        self._ledger()
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertNotIn("audit_baseline_diff", payload)

    def test_diff_block_when_baseline_provided(self):
        self._ledger(
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"))
        bl = os.path.join(self.workspace, "bl.json")
        _invoke(["audit", "--baseline-write", bl], cwd=self.workspace)
        r = _invoke(["info", "--json", "--audit-baseline", bl],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        diff = payload["audit_baseline_diff"]
        self.assertEqual(diff["fresh"], 0)
        self.assertEqual(diff["baselined"], 1)
        self.assertEqual(diff["drift"], False)
        self.assertEqual(os.path.abspath(bl), diff["baseline_path"])

    def test_diff_drift_flag_when_fresh_appear(self):
        # New debt → drift = True.
        self._ledger(
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"))
        bl = os.path.join(self.workspace, "bl.json")
        _invoke(["audit", "--baseline-write", bl], cwd=self.workspace)
        # Add a yagni finding.
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"))
        r = _invoke(["info", "--json", "--audit-baseline", bl],
                    cwd=self.workspace)
        diff = json.loads(r.stdout)["audit_baseline_diff"]
        self.assertEqual(diff["fresh"], 1)  # yagni is new
        self.assertEqual(diff["baselined"], 1)  # stdlib still baselined
        self.assertEqual(diff["drift"], True)

    def test_diff_agrees_with_audit_baseline_json(self):
        # The diff block uses the same fingerprint logic as
        # ``audit --baseline``; the per-finding ``baselined``
        # count must match.
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same — settled by: test",
                   "?02 same — settled by: test"))
        bl = os.path.join(self.workspace, "bl.json")
        _invoke(["audit", "--baseline-write", bl], cwd=self.workspace)
        info = _invoke(["info", "--json", "--audit-baseline", bl],
                       cwd=self.workspace)
        audit = _invoke(["audit", "--baseline", bl, "--json"],
                        cwd=self.workspace)
        info_diff = json.loads(info.stdout)["audit_baseline_diff"]
        audit_payload = json.loads(audit.stdout)
        # The info diff counts the same baselined total as
        # the audit's `baselined` key.
        self.assertEqual(info_diff["baselined"],
                         audit_payload["baselined"])
        self.assertEqual(info_diff["fresh"], audit_payload["net"])

    def test_diff_with_missing_baseline_treats_everything_fresh(self):
        # A missing baseline file is treated as empty; every
        # finding is therefore fresh. drift = True.
        self._ledger(
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"))
        missing = os.path.join(self.workspace, "absent.json")
        r = _invoke(["info", "--json", "--audit-baseline", missing],
                    cwd=self.workspace)
        diff = json.loads(r.stdout)["audit_baseline_diff"]
        self.assertEqual(diff["baselined"], 0)
        self.assertEqual(diff["fresh"], 1)
        self.assertEqual(diff["drift"], True)


class ManifestTests(InfoEnvBase):
    """``--manifest`` emits the full detector coverage map."""

    def test_no_manifest_block_when_omitted(self):
        self._ledger()
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertNotIn("audit_manifest", payload)

    def test_manifest_lists_every_tag(self):
        self._ledger()
        r = _invoke(["info", "--json", "--manifest"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        m = payload["audit_manifest"]
        self.assertEqual(set(m["by_tag"]), set(mindseam.AUDIT_TAGS))
        self.assertEqual(m["tags_total"], len(mindseam.AUDIT_TAGS))

    def test_manifest_clean_ledger_zero_fired(self):
        self._ledger()  # clean: no findings at all.
        r = _invoke(["info", "--json", "--manifest"],
                    cwd=self.workspace)
        m = json.loads(r.stdout)["audit_manifest"]
        self.assertEqual(m["tags_fired"], 0)
        self.assertEqual(m["tags_clean"], m["tags_total"])
        for count in m["by_tag"].values():
            self.assertEqual(count, 0)

    def test_manifest_wasteful_ledger_counts_fired(self):
        # A ledger with one delete + one stdlib + one yagni.
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same — settled by: test",
                   "?02 same — settled by: test"))
        r = _invoke(["info", "--json", "--manifest"],
                    cwd=self.workspace)
        m = json.loads(r.stdout)["audit_manifest"]
        self.assertEqual(m["by_tag"]["delete"], 1)
        self.assertEqual(m["by_tag"]["stdlib"], 1)
        self.assertEqual(m["by_tag"]["yagni"], 1)
        # Tags that did not fire are still listed (seen-but-clean).
        self.assertEqual(m["by_tag"]["shrink"], 0)
        self.assertEqual(m["by_tag"]["goal-stale"], 0)
        self.assertIn(m["by_tag"]["shrink"], m["by_tag"].values())

    def test_manifest_agrees_with_audit_summary(self):
        # The manifest's fired counts and the audit_summary's
        # by_tag must match exactly; they come from the same
        # ``audit_findings`` call.
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same — settled by: test",
                   "?02 same — settled by: test"))
        r = _invoke(["info", "--json", "--manifest"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        # Only the fired tags appear in audit_summary; the
        # manifest's fired counts match those counts.
        for tag, count in payload["audit_summary"]["by_tag"].items():
            self.assertEqual(payload["audit_manifest"]["by_tag"][tag],
                             count)


class ComposeTests(InfoEnvBase):
    """The three new flags compose with each other and with --json."""

    def test_workspace_id_with_manifest(self):
        self._ledger()
        r = _invoke(["info", "--json", "--workspace-id", "--manifest"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("workspace_id", payload)
        self.assertIn("audit_manifest", payload)
        # The r161 audit_summary is still there.
        self.assertIn("audit_summary", payload)

    def test_workspace_id_with_audit_baseline_and_manifest(self):
        self._ledger(
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"))
        bl = os.path.join(self.workspace, "bl.json")
        _invoke(["audit", "--baseline-write", bl], cwd=self.workspace)
        r = _invoke(
            ["info", "--json", "--workspace-id",
             "--audit-baseline", bl, "--manifest"],
            cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("workspace_id", payload)
        self.assertIn("audit_baseline_diff", payload)
        self.assertIn("audit_manifest", payload)
        # All three blocks coexist; each is independent.

    def test_baseline_diff_omitted_when_baseline_arg_is_none(self):
        # The flag exists; if the user does not pass a value
        # the block stays out of the payload.
        self._ledger()
        r = _invoke(["info", "--json", "--manifest"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("audit_manifest", payload)
        self.assertNotIn("audit_baseline_diff", payload)
