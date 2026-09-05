# -*- coding: utf-8 -*-
"""Round 166 guards: info content-hash and changed.

The r161-r165 ``info`` report grew many orthogonal blocks:
``audit_summary`` (roll-up), ``audit_manifest`` (detector
coverage), ``workspace_id`` (path + mtime fingerprint),
``audit_baseline_diff`` (drift), ``lock_state`` (advisory
file lock), ``workspace_files`` (mtime + size per
artefact), ``health`` (ok / degraded / unhealthy
roll-up). r166 closes the gap with two more flags that
let a host detect "which file's content actually
changed" without trusting mtime:

- ``--content-hash`` emits a ``content_hash`` block
  carrying a short SHA-1 of each ledger artefact,
  borrowed from ``git rev-parse --short`` /
  ``sha1sum`` / ``conda list --md5``. The 8-char
  prefix is the same shape as ``git``'s abbreviated
  object names; collision space is 2^32 and the chance
  of a same-day collision on a single workspace is
  negligible.
- ``--changed`` compares the current hashes to the
  last call's persisted hashes (``.mindseam/info-state
  .json``) and emits a per-file ``changed`` block,
  borrowed from ``git status --porcelain`` /
  ``make -n``. A first run (no state file) is treated
  as "all changed", the way ``cargo`` rebuilds the
  registry index when its ``.cargo/lock`` file is
  absent.

The state write goes through the r164 write lock, so
``--changed`` cannot race with a concurrent ``note`` or
``seam``. A locked state file is silently skipped (the
host still gets the ``changed`` map for this call) —
``git status`` reports staged-vs-unstaged even when the
index file is unwritable, the same way.
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


class ContentHashBase(unittest.TestCase):

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


class HashHelperTests(unittest.TestCase):
    """The hash helpers behave as documented."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_file_content_hash_is_8_chars(self):
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            fh.write(b"hello\n")
            tmp = fh.name
        try:
            h = mindseam._file_content_hash(tmp, length=8)
            self.assertEqual(len(h), 8)
            self.assertTrue(all(c in "0123456789abcdef" for c in h))
        finally:
            os.unlink(tmp)

    def test_file_content_hash_stable(self):
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            fh.write(b"hello\n")
            tmp = fh.name
        try:
            a = mindseam._file_content_hash(tmp, 8)
            b = mindseam._file_content_hash(tmp, 8)
            self.assertEqual(a, b)
        finally:
            os.unlink(tmp)

    def test_file_content_hash_changes_with_content(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as fh:
            fh.write("alpha\n")
            tmp = fh.name
        try:
            a = mindseam._file_content_hash(tmp, 8)
            with open(tmp, "w") as fh:
                fh.write("beta\n")
            b = mindseam._file_content_hash(tmp, 8)
            self.assertNotEqual(a, b)
        finally:
            os.unlink(tmp)

    def test_file_content_hash_missing_is_empty(self):
        self.assertEqual(mindseam._file_content_hash("/no/such/path"), "")

    def test_content_hash_snapshot_lists_every_artefact(self):
        snap = mindseam._content_hash_snapshot()
        self.assertEqual(
            set(snap.keys()),
            {"WORKSPACE.md", "history.json",
             "metacognition.json", "skillbook.md"})

    def test_content_hash_snapshot_empty_for_missing(self):
        snap = mindseam._content_hash_snapshot()
        # No files written → every artefact is empty.
        for v in snap.values():
            self.assertEqual(v, "")


class ContentHashFlagTests(ContentHashBase):
    """``--content-hash`` emits a content_hash block."""

    def test_no_block_when_omitted(self):
        self._ledger()
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertNotIn("content_hash", payload)

    def test_block_appears_when_set(self):
        self._ledger()
        r = _invoke(["info", "--json", "--content-hash"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("content_hash", payload)
        h = payload["content_hash"]
        # WORKSPACE.md exists; the hash is 8 hex chars.
        self.assertEqual(len(h["WORKSPACE.md"]), 8)
        # Missing artefacts get empty strings.
        for missing in ("history.json", "metacognition.json",
                        "skillbook.md"):
            self.assertEqual(h[missing], "")

    def test_block_changes_when_file_content_changes(self):
        # Two calls with different ledger content produce
        # different content_hash entries.
        self._ledger(goal="first")
        r1 = _invoke(["info", "--json", "--content-hash"],
                     cwd=self.workspace)
        h1 = json.loads(r1.stdout)["content_hash"]["WORKSPACE.md"]
        time.sleep(0.05)
        self._ledger(goal="second")
        r2 = _invoke(["info", "--json", "--content-hash"],
                     cwd=self.workspace)
        h2 = json.loads(r2.stdout)["content_hash"]["WORKSPACE.md"]
        self.assertNotEqual(h1, h2)

    def test_text_face_prints_hash_column(self):
        self._ledger()
        r = _invoke(["info", "--text", "--content-hash"],
                    cwd=self.workspace)
        self.assertIn("Content hash:", r.stdout)
        self.assertIn("WORKSPACE.md", r.stdout)


class ChangedFlagTests(ContentHashBase):
    """``--changed`` compares to the persisted state file."""

    def test_no_block_when_omitted(self):
        self._ledger()
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertNotIn("changed", payload)

    def test_first_run_marks_everything_changed(self):
        # No state file yet → every artefact is changed,
        # and ``previous_run`` is False (the host can
        # tell the difference between "first run" and
        # "actually changed since last call").
        self._ledger()
        r = _invoke(["info", "--json", "--changed"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("changed", payload)
        c = payload["changed"]
        self.assertEqual(c["files"]["WORKSPACE.md"], True)
        self.assertEqual(c["any_changed"], True)
        self.assertEqual(c["previous_run"], False)

    def test_second_run_with_no_ledger_change_marks_unchanged(self):
        # First call writes the state file. The second
        # call sees no change and marks everything
        # False, with ``previous_run`` True.
        self._ledger()
        _invoke(["info", "--json", "--changed"],
                 cwd=self.workspace)
        r = _invoke(["info", "--json", "--changed"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        c = payload["changed"]
        self.assertEqual(c["files"]["WORKSPACE.md"], False)
        self.assertEqual(c["any_changed"], False)
        self.assertEqual(c["previous_run"], True)

    def test_ledger_rewrite_after_state_marks_only_that_file(self):
        # First call → state file. Rewrite WORKSPACE.md.
        # Second call → only WORKSPACE.md is changed;
        # missing files (history.json etc.) stay False.
        self._ledger()
        _invoke(["info", "--json", "--changed"],
                 cwd=self.workspace)
        time.sleep(0.05)
        self._ledger(goal="different goal")
        r = _invoke(["info", "--json", "--changed"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        c = payload["changed"]
        self.assertEqual(c["files"]["WORKSPACE.md"], True)
        self.assertEqual(c["any_changed"], True)

    def test_state_file_written_on_changed_call(self):
        self._ledger()
        _invoke(["info", "--json", "--changed"],
                 cwd=self.workspace)
        state = Path(self.workspace) / ".mindseam" / "info-state.json"
        self.assertTrue(state.exists())

    def test_state_file_carries_hashes(self):
        self._ledger()
        _invoke(["info", "--json", "--changed"],
                 cwd=self.workspace)
        state = json.loads(
            (Path(self.workspace) / ".mindseam" / "info-state.json")
            .read_text(encoding="utf-8"))
        self.assertIn("hashes", state)
        self.assertEqual(state["version"], 1)
        self.assertIn("WORKSPACE.md", state["hashes"])

    def test_history_file_appearance_marks_it_changed(self):
        # First call sees no history.json → second call
        # sees it → the change is reported.
        self._ledger()
        _invoke(["info", "--json", "--changed"],
                 cwd=self.workspace)
        # Now create history.json.
        hist = Path(self.workspace) / ".mindseam" / "history.json"
        hist.write_text(
            json.dumps([{"t": int(time.time()), "next": "x",
                         "verified": 0, "open": 0}]),
            encoding="utf-8")
        r = _invoke(["info", "--json", "--changed"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        c = payload["changed"]
        self.assertEqual(c["files"]["history.json"], True)
        self.assertEqual(c["any_changed"], True)

    def test_text_face_prints_changed_lines(self):
        self._ledger()
        _invoke(["info", "--text", "--changed"],
                 cwd=self.workspace)
        r2 = _invoke(["info", "--text", "--changed"],
                     cwd=self.workspace)
        self.assertIn("Changed since last call:", r2.stdout)
        self.assertIn("WORKSPACE.md", r2.stdout)
        self.assertIn("any_changed=False", r2.stdout)


class StateFileTests(ContentHashBase):
    """The state file is robust against missing / malformed input."""

    def test_state_missing_returns_empty(self):
        # No state file → _read_info_state returns {}.
        self._ledger()
        self.assertEqual(mindseam._read_info_state(), {})

    def test_state_malformed_returns_empty(self):
        self._ledger()
        state = Path(self.workspace) / ".mindseam" / "info-state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text("not json", encoding="utf-8")
        self.assertEqual(mindseam._read_info_state(), {})

    def test_state_non_dict_returns_empty(self):
        self._ledger()
        state = Path(self.workspace) / ".mindseam" / "info-state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text("[]", encoding="utf-8")
        self.assertEqual(mindseam._read_info_state(), {})

    def test_state_hashes_must_be_dict(self):
        # A state file whose ``hashes`` key is not a dict
        # is treated as empty.
        self._ledger()
        state = Path(self.workspace) / ".mindseam" / "info-state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(
            json.dumps({"version": 1, "hashes": "not a dict"}),
            encoding="utf-8")
        self.assertEqual(mindseam._read_info_state(), {})

    def test_write_state_through_lock(self):
        # The state file write goes through the r164 lock;
        # a foreign lock blocks the write and returns
        # False. The host still gets the ``changed`` map
        # for this call.
        self._ledger()
        lock = os.path.join(self.workspace, ".mindseam", "write.lock")
        with open(lock, "w", encoding="utf-8") as fh:
            fh.write("pid=99999\n")
        r = _invoke(["info", "--json", "--changed"],
                    cwd=self.workspace)
        # The state file is not written (foreign lock),
        # but the changed map is still produced.
        payload = json.loads(r.stdout)
        self.assertIn("changed", payload)
        state = Path(self.workspace) / ".mindseam" / "info-state.json"
        self.assertFalse(state.exists())


class ComposeTests(ContentHashBase):
    """The two new flags compose with each other and the r161-r165 surface."""

    def test_content_hash_with_mtime(self):
        self._ledger()
        r = _invoke(["info", "--json", "--content-hash", "--mtime"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("content_hash", payload)
        self.assertIn("workspace_files", payload)

    def test_content_hash_with_health(self):
        self._ledger(
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"))
        r = _invoke(["info", "--json", "--content-hash", "--health"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("content_hash", payload)
        self.assertEqual(payload["health"]["status"], "unhealthy")
        kinds = [r["kind"] for r in payload["health"]["reasons"]]
        self.assertIn("audit_finding", kinds)

    def test_changed_with_text(self):
        self._ledger()
        _invoke(["info", "--json", "--changed"],
                 cwd=self.workspace)
        r = _invoke(["info", "--text", "--changed"],
                    cwd=self.workspace)
        self.assertIn("Changed since last call:", r.stdout)
        self.assertIn("any_changed=False", r.stdout)
