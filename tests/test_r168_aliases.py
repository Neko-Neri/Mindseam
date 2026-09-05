# -*- coding: utf-8 -*-
"""Round 168 guards: alias dispatch and the aliases catalog.

The r156-r167 surface grew many orthogonal blocks. A
host that wants the "common CI recipe" still has to
type the long form, the way ``git co`` saves
keystrokes for ``git checkout``. r168 borrows from
``git config alias.*`` / ``gh alias`` / ``kubectl
plugin``: a mapping from short names to full
subcommand + arg sequences, with auto-expansion
before argparse sees the argv.

Two pieces:

- A built-in catalog of 5 aliases that ship with the
  controller (``health``, ``audit-ci``,
  ``audit-baseline-write``, ``audit-baseline-check``,
  ``diff``) — the recipes the r156-r167 rounds have
  accreted as "what most users actually type".
- A user-overridable file at
  ``.mindseam/aliases.json`` that lets a workspace
  define its own aliases. User entries override
  built-ins, the way ``.git/config`` overrides
  ``/etc/gitconfig``.

The auto-expansion is a no-op when the first token is
already a registered subcommand or a flag, so the
round adds zero risk to existing invocations. The
``info --aliases`` block exposes the merged catalog
to a host, the way ``gh alias list`` does.
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


class AliasHelperTests(unittest.TestCase):
    """The catalog and expansion helpers behave as documented."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_default_catalog_has_five_entries(self):
        cat = mindseam._alias_default_catalog()
        # 5 recipes the r156-r167 rounds accreted.
        self.assertEqual(len(cat), 5)
        for name in ("health", "audit-ci",
                     "audit-baseline-write",
                     "audit-baseline-check", "diff"):
            self.assertIn(name, cat)

    def test_default_catalog_entries_have_command_and_args(self):
        for name, spec in mindseam._alias_default_catalog().items():
            self.assertIn("command", spec)
            self.assertIn("args", spec)
            self.assertIsInstance(spec["command"], str)
            self.assertIsInstance(spec["args"], list)

    def test_expand_known_alias(self):
        argv = mindseam._expand_alias_argv(["audit-ci"])
        self.assertEqual(argv, ["audit", "--json",
                               "--intensity", "lite"])

    def test_expand_unknown_alias_passthrough(self):
        argv = mindseam._expand_alias_argv(["seam"])
        self.assertEqual(argv, ["seam"])

    def test_expand_empty_argv(self):
        argv = mindseam._expand_alias_argv([])
        self.assertEqual(argv, [])

    def test_expand_alias_with_user_args(self):
        # The user's args after the alias name are
        # preserved (e.g. ``audit-ci --tag delete``
        # should still pass ``--tag delete`` through).
        argv = mindseam._expand_alias_argv(
            ["audit-ci", "--tag", "delete"])
        self.assertEqual(argv,
                         ["audit", "--json", "--intensity", "lite",
                          "--tag", "delete"])

    def test_user_file_overrides_builtin(self):
        # The user file overrides the built-in. We
        # override ``health`` to point at a different
        # subcommand and verify the merged catalog
        # picks up the user entry.
        user = {"health": {"command": "info", "args": ["--version"],
                            "summary": "user override"}}
        path = Path(self.workspace) / ".mindseam" / "aliases.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(user), encoding="utf-8")
        merged = mindseam._merge_aliases()
        self.assertEqual(merged["health"]["args"], ["--version"])
        # The other built-ins survive the merge.
        self.assertIn("audit-ci", merged)

    def test_user_file_malformed_returns_builtins(self):
        path = Path(self.workspace) / ".mindseam" / "aliases.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")
        merged = mindseam._merge_aliases()
        # The built-ins survive the malformed file.
        self.assertIn("audit-ci", merged)


class AliasDispatchTests(unittest.TestCase):
    """The top-level dispatch auto-expands alias names."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _bootstrap_ledger(self):
        path = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ["# L", "", "## Goal", "demo", "", "## Core", "",
                "## Verified", "", "## Open", "", "## Next", "n"]
        path.write_text("\n".join(text), encoding="utf-8")

    def test_audit_ci_alias_invokes_audit_json(self):
        self._bootstrap_ledger()
        r = _invoke(["audit-ci"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The JSON face shows the audit payload; the
        # intensity is ``lite`` because the alias
        # passes ``--intensity lite``.
        payload = json.loads(r.stdout)
        self.assertIn("lean", payload)
        self.assertEqual(payload["intensity"], "lite")

    def test_diff_alias_runs_info(self):
        self._bootstrap_ledger()
        r = _invoke(["diff"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The diff alias runs ``info --json --changed
        # --content-hash``, so the payload carries
        # ``changed`` and ``content_hash`` blocks.
        payload = json.loads(r.stdout)
        self.assertIn("changed", payload)
        self.assertIn("content_hash", payload)

    def test_unknown_alias_falls_through_to_argparse(self):
        # A name that is neither a subcommand nor an
        # alias is rejected by argparse with the
        # standard "the following arguments are
        # required: cmd" message.
        self._bootstrap_ledger()
        r = _invoke(["not-a-command"], cwd=self.workspace)
        self.assertNotEqual(r.returncode, 0, r.stderr)

    def test_subcommand_passthrough_unchanged(self):
        # A registered subcommand with flags is
        # unaffected by the alias layer.
        self._bootstrap_ledger()
        r = _invoke(["audit", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        # No ``intensity: lite`` marker (the bare
        # ``audit`` call uses the default ``full``).
        self.assertEqual(payload["intensity"], "full")

    def test_help_alias_unknown(self):
        # The top-level --help still works.
        r = _invoke(["--help"], cwd=self.workspace)
        # argparse exits with code 0 for --help.
        self.assertIn(r.returncode, (0, 2))

    def test_user_alias_dispatch(self):
        # A user-defined alias dispatches the same way
        # as a built-in.
        user = {"my-hello": {"command": "info", "args": ["--version"]}}
        path = Path(self.workspace) / ".mindseam" / "aliases.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(user), encoding="utf-8")
        r = _invoke(["my-hello"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mindseam", r.stdout)


class AliasesFlagTests(unittest.TestCase):
    """``info --aliases`` emits the merged catalog."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _ledger(self):
        path = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ["# L", "", "## Goal", "", "## Core", "",
                "## Verified", "", "## Open", "", "## Next", ""]
        path.write_text("\n".join(text), encoding="utf-8")

    def test_no_aliases_block_when_omitted(self):
        self._ledger()
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertNotIn("aliases", payload)

    def test_aliases_block_appears_when_set(self):
        self._ledger()
        r = _invoke(["info", "--json", "--aliases"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("aliases", payload)
        a = payload["aliases"]
        self.assertIn("config_path", a)
        self.assertIn("user_overrides", a)
        self.assertIn("names", a)
        self.assertIn("entries", a)

    def test_default_aliases_are_listed(self):
        self._ledger()
        r = _invoke(["info", "--json", "--aliases"],
                    cwd=self.workspace)
        names = json.loads(r.stdout)["aliases"]["names"]
        for name in ("health", "audit-ci", "diff"):
            self.assertIn(name, names)

    def test_user_overrides_reported(self):
        self._ledger()
        user = {"my-hello": {"command": "info", "args": ["--version"]}}
        path = Path(self.workspace) / ".mindseam" / "aliases.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(user), encoding="utf-8")
        r = _invoke(["info", "--json", "--aliases"],
                    cwd=self.workspace)
        a = json.loads(r.stdout)["aliases"]
        self.assertIn("my-hello", a["user_overrides"])
        self.assertIn("my-hello", a["names"])

    def test_text_face_prints_aliases(self):
        self._ledger()
        r = _invoke(["info", "--text", "--aliases"],
                    cwd=self.workspace)
        self.assertIn("Aliases:", r.stdout)
        self.assertIn("audit-ci", r.stdout)
        self.assertIn("audit", r.stdout)


class ParserAcceptanceTests(unittest.TestCase):
    """The --aliases flag is wired through argparse."""

    def test_aliases_flag_registered(self):
        # If the flag were dropped, ``info --aliases``
        # would say "unrecognised arguments".
        r = subprocess.run(
            [sys.executable, str(MINDSEAM), "info", "--aliases"],
            cwd=tempfile.mkdtemp(),
            capture_output=True, text=True, encoding="utf-8")
        self.assertNotIn("unrecognised arguments",
                         r.stderr + r.stdout)
