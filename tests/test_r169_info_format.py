# -*- coding: utf-8 -*-
"""Round 169 guards: info --format dot-path renderer.

The r156-r168 ``info`` report grew many orthogonal
blocks (audit_summary, audit_manifest, workspace_id,
audit_baseline_diff, lock_state, workspace_files,
health, content_hash, changed, features, aliases).
A host that wants *one* field still has to parse
the whole JSON, the way a host that wants
``.State.Running`` from ``docker inspect`` used to
parse the whole JSON before ``--format`` shipped.

r169 borrows from ``docker inspect --format`` /
``kubectl get -o jsonpath`` / Rust's
``serde_json::Value::pointer()`` / ``jq -r
'.foo.bar'``: a single ``--format <path>`` flag
that prints only the values at the given dot-
paths. The path syntax is intentionally narrow
(``foo.bar`` / ``foo[0]`` / ``foo[*]``) so a
host can write the path as a one-liner without
quoting a JSON path expression.

Three pieces:

- ``_resolve_path(payload, path)`` walks the path
  and returns the value, or ``None`` for a missing
  branch. A missing path returns an empty string
  at the rendering layer (not exit 2) so a probe
  can ask "is this feature present?" without
  crashing.
- ``_format_path(payload, path)`` renders one path
  to a string. Scalars render as ``str(value)``;
  bools render as ``true`` / ``false``; lists
  render as one element per line, the way
  ``jq -r '.foo[*]'`` does.
- ``_format_paths(payload, path_spec)`` parses a
  comma-separated list of paths and renders
  them as one block per path, separated by a
  blank line, the way ``kubectl get -o
  jsonpath='{range ...}{end}'`` does.

A host reads one field without parsing the whole
JSON, the way ``docker inspect --format
'{{.State.Running}}'`` does. A CI script that wants
the audit net count reads ``info --format
'audit_summary.net'`` and gets the integer on
stdout, no ``jq`` pipeline needed.
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


class ResolvePathTests(unittest.TestCase):
    """The path resolver walks dot-paths and list indexers."""

    def test_top_level_key(self):
        self.assertEqual(
            mindseam._resolve_path({"a": 5}, "a"), 5)

    def test_dotted_path(self):
        self.assertEqual(
            mindseam._resolve_path({"a": {"b": 5}}, "a.b"), 5)

    def test_deep_dotted_path(self):
        self.assertEqual(
            mindseam._resolve_path(
                {"a": {"b": {"c": {"d": 7}}}}, "a.b.c.d"),
            7)

    def test_list_index_positive(self):
        self.assertEqual(
            mindseam._resolve_path({"a": [10, 20, 30]}, "a[1]"),
            20)

    def test_list_index_negative(self):
        self.assertEqual(
            mindseam._resolve_path({"a": [10, 20, 30]}, "a[-1]"),
            30)

    def test_list_index_out_of_range(self):
        self.assertIsNone(
            mindseam._resolve_path({"a": [1]}, "a[5]"))

    def test_whole_list_indexer(self):
        self.assertEqual(
            mindseam._resolve_path({"a": [10, 20]}, "a[*]"),
            [10, 20])

    def test_whole_list_dot_star_shortcut(self):
        # ``a.*`` is sugar for ``a[*]``.
        self.assertEqual(
            mindseam._resolve_path({"a": [10, 20]}, "a.*"),
            [10, 20])

    def test_missing_key_returns_none(self):
        self.assertIsNone(
            mindseam._resolve_path({"a": 1}, "b.c"))

    def test_dotted_path_through_list_indexer(self):
        self.assertEqual(
            mindseam._resolve_path(
                {"a": [{"b": 11}]}, "a[0].b"),
            11)

    def test_empty_path_returns_none(self):
        self.assertIsNone(mindseam._resolve_path({"a": 1}, ""))

    def test_list_index_on_non_list_returns_none(self):
        self.assertIsNone(
            mindseam._resolve_path({"a": 1}, "a[0]"))


class FormatPathTests(unittest.TestCase):
    """The renderer turns resolved values into strings."""

    def test_scalar_int(self):
        self.assertEqual(
            mindseam._format_path({"a": 5}, "a"), "5")

    def test_scalar_string(self):
        self.assertEqual(
            mindseam._format_path({"a": "hello"}, "a"), "hello")

    def test_bool_true(self):
        self.assertEqual(
            mindseam._format_path({"a": True}, "a"), "true")

    def test_bool_false(self):
        self.assertEqual(
            mindseam._format_path({"a": False}, "a"), "false")

    def test_missing_path_returns_empty(self):
        self.assertEqual(
            mindseam._format_path({"a": 1}, "b.c"), "")

    def test_list_renders_one_per_line(self):
        out = mindseam._format_path({"a": [1, 2, 3]}, "a[*]")
        self.assertEqual(out, "1\n2\n3")

    def test_list_of_dicts(self):
        # ``a[*].id`` walks the list and renders each
        # element's ``id``.
        out = mindseam._format_path(
            {"a": [{"id": "x"}, {"id": "y"}]}, "a[*].id")
        self.assertEqual(out, "x\ny")

    def test_multi_path_renders_separate_blocks(self):
        out = mindseam._format_paths(
            {"a": 1, "b": 2}, "a,b")
        self.assertEqual(out, "1\n2")

    def test_multi_path_with_missing(self):
        # A missing path renders as an empty string;
        # the host can detect the missing value by
        # the empty block.
        out = mindseam._format_paths(
            {"a": 1}, "a,missing.b")
        self.assertEqual(out, "1\n")

    def test_multi_path_strips_whitespace(self):
        # A trailing comma or whitespace is tolerated.
        out = mindseam._format_paths(
            {"a": 1, "b": 2}, " a , b ")
        self.assertEqual(out, "1\n2")

    def test_multi_path_empty_spec_returns_empty(self):
        self.assertEqual(mindseam._format_paths({"a": 1}, ""), "")


class FormatFlagTests(unittest.TestCase):
    """``--format <path>`` prints only the values at the path."""

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

    def test_format_prints_single_value(self):
        self._ledger()
        r = _invoke(
            ["info", "--json", "--workspace-id",
             "--format", "workspace_id.id"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # 16 hex chars.
        self.assertEqual(len(r.stdout.strip()), 16)
        self.assertTrue(
            all(c in "0123456789abcdef" for c in r.stdout.strip()))

    def test_format_prints_multi_path(self):
        self._ledger()
        r = _invoke(
            ["info", "--json", "--workspace-id",
             "--format", "workspace_id.id,lock_state.state"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(len(lines[0]), 16)
        self.assertEqual(lines[1], "free")

    def test_format_missing_path_returns_empty(self):
        self._ledger()
        # A missing path returns an empty string,
        # not an error. The host can probe for
        # ``info-content-hash`` (a known feature)
        # without crashing.
        r = _invoke(
            ["info", "--json",
             "--format", "nonexistent.path.here"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "")

    def test_format_does_not_emit_json_wrapper(self):
        # The output is the bare scalar, not a JSON
        # string. A host that wants the integer
        # ``audit_summary.net`` reads it as a plain
        # integer on stdout.
        self._ledger()
        r = _invoke(
            ["info", "--json", "--manifest",
             "--format", "audit_summary.net"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # No quotes, no brackets, just the integer.
        self.assertEqual(r.stdout.strip(), "0")

    def test_format_composes_with_features(self):
        # --format picks up the ``features`` block,
        # so a host can ask "what's the since round
        # of the first feature?" without parsing
        # JSON.
        self._ledger()
        r = _invoke(
            ["info", "--json", "--features",
             "--format", "features[0].id"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "info-warnings-only")

    def test_format_list_renders_one_per_line(self):
        self._ledger()
        r = _invoke(
            ["info", "--json", "--features",
             "--format", "features[*].id"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The full catalog of 29 entries (28 r156-r167
        # plus the r167 self-reference, plus the r169
        # entry we will add).
        lines = r.stdout.strip().split("\n")
        # ``features[0].id`` and ``features[1].id``
        # cover the first two r156 features.
        self.assertEqual(lines[0], "info-warnings-only")
        self.assertEqual(lines[1], "info-version")

    def test_format_short_circuits_other_outputs(self):
        # ``--format`` short-circuits the JSON /
        # text / section paths. The output is the
        # rendered value, not a JSON wrapper.
        self._ledger()
        r = _invoke(
            ["info", "--format", "lock_state.state"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "free")
        # The output does not contain a JSON opening
        # brace.
        self.assertNotIn("{", r.stdout)
