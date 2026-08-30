"""Test ``seam --from-stdin``: borrow ``kubectl apply -f -`` /
``xargs cmd`` / ``git am --stdin``.

The ``--from-stdin`` flag reads one next action per non-empty
line from standard input, recording a row in ``history.json``
for each. A host that batches several seam calls into one
process invocation gets a single history rotation, the way
``kubectl apply -f -`` reads multiple resources from stdin
and the way ``xargs jspace seam`` would pipe lines into
the command.

The tests import ``jspace`` and call ``main`` directly with a
monkey-patched ``sys.stdin`` to avoid the Windows + Python 3.14
stdin-pipe deadlock that the default ``subprocess.run`` ``input=``
argument hits when the child reads stdin in buffered text mode.
``--from-stdin`` itself uses ``sys.stdin.buffer.read()`` rather
than ``sys.stdin.read()`` so the read is binary-safe on every
platform.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSPACE_DIR = ROOT / "j-space" / "scripts"
if str(JSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(JSPACE_DIR))

import jspace as jspace_module  # noqa: E402


def _run(cwd, args, stdin_text):
    """Run ``jspace.main`` with ``sys.stdin`` monkey-patched.

    The standard ``subprocess.run(input=...)`` path is fragile on
    Windows + Python 3.14: the child reads ``sys.stdin.read()``
    in buffered text mode, and the parent never sends an
    explicit newline, so the child blocks waiting for one. The
    monkey-patch path replaces ``sys.stdin`` with a ``StringIO``
    that already has the data and an immediate EOF, so the
    child's ``read()`` returns immediately.

    The save/restore block falls back to ``sys.__stdin__`` (the
    original real stdin) rather than the current ``sys.stdin``,
    because previous test runs may have left ``sys.stdin``
    pointing at a spent ``StringIO``.

    ``jspace.main`` reads the ledger from ``.jspace/`` relative
    to its current working directory, not to the test's
    workspace, so we ``os.chdir`` into the workspace for the
    duration of the call and restore the original cwd
    afterwards.
    """
    saved_stdin = sys.stdin
    saved_cwd = os.getcwd()
    sys.stdin = io.StringIO(stdin_text)
    os.chdir(cwd)
    try:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = jspace_module.main(args)
            except SystemExit as exc:
                rc = exc.code if isinstance(exc.code, int) else (
                    2 if exc.code else 0)
        return rc, out.getvalue(), err.getvalue()
    finally:
        os.chdir(saved_cwd)
        sys.stdin = saved_stdin


def _open_ledger(cwd):
    """``note --goal ... --next ...`` writes the ledger + a
    first history row; the seam batch then stacks on top of
    that.
    """
    rc, _, _ = _run(cwd,
                    ["note", "--goal", "from-stdin demo",
                     "--next", "dom: first action"],
                    "")
    assert rc == 0, "open_ledger failed"


class SeamFromStdinFlagTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        # ``_open_ledger`` replaces ``sys.stdin`` with an empty
        # ``StringIO`` so the ledger can be opened without a real
        # stdin. Restore the original ``sys.stdin`` after the
        # call so the test's own ``_run`` starts from a clean
        # slate, not whatever the open-ledger helper left behind.
        _open_ledger(self.workspace)
        sys.stdin = sys.__stdin__

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_from_stdin_records_one_row_per_line(self):
        # Borrowed from ``kubectl apply -f -`` / ``xargs``:
        # one next action per non-empty line; the call records
        # one row per line in append order. ``--dry-run`` does
        # not write ``history.json``; the row count is in the
        # ``from-stdin`` warning.
        lines = "dom: alpha\ndom: beta\ndom: gamma\n"
        rc, stdout, _ = _run(self.workspace,
                              ["seam", "--from-stdin",
                               "--dry-run", "--json"],
                              lines)
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        joined = " ".join(payload["warnings"])
        self.assertIn("from-stdin: 3 next actions recorded", joined)

        # Without ``--dry-run`` the rows are committed in order.
        rc, stdout, _ = _run(self.workspace,
                              ["seam", "--from-stdin", "--json"],
                              lines)
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        # ``history_count`` is now the count of from-stdin rows,
        # since the open-ledger ``note`` path did not create a
        # ``history.json`` of its own. ``note`` only writes the
        # ledger; ``seam`` is the path that touches the audit log.
        self.assertEqual(payload["history_count"], 3)

    def test_from_stdin_skips_empty_lines(self):
        # Blank lines between commands are noise, the way they
        # are noise in ``xargs`` / ``docker compose -f -``. The
        # flag records only the non-empty lines.
        lines = "dom: alpha\n\n\ndom: beta\n\n"
        rc, stdout, _ = _run(self.workspace,
                              ["seam", "--from-stdin",
                               "--dry-run", "--json"],
                              lines)
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        joined = " ".join(payload["warnings"])
        self.assertIn("from-stdin: 2 next actions recorded", joined)

    def test_from_stdin_message_attaches_to_every_row(self):
        # ``--message`` applies to every row in the batch, the
        # way ``git commit -m`` attaches a single commit message
        # to a commit that introduces multiple files. Each row
        # in the resulting history carries the same ``msg``.
        lines = "dom: alpha\ndom: beta\n"
        rc, stdout, _ = _run(self.workspace,
                              ["seam", "--from-stdin",
                               "--message", "BATCH-101", "--json"],
                              lines)
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        # Two new rows at the tail carry the batch message.
        self.assertIn("BATCH-101", " ".join(payload["warnings"]))
        # And the rows on disk both carry the message.
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        self.assertEqual(data[-2]["next"], "dom: alpha")
        self.assertEqual(data[-2]["msg"], "BATCH-101")
        self.assertEqual(data[-1]["next"], "dom: beta")
        self.assertEqual(data[-1]["msg"], "BATCH-101")

    def test_from_stdin_with_quiet_prints_only_facts(self):
        # ``--quiet`` composes with ``--from-stdin``: the
        # batch-summary line is suppressed in the quiet path.
        lines = "dom: step\n"
        rc, stdout, _ = _run(self.workspace,
                              ["seam", "--from-stdin", "--quiet"],
                              lines)
        self.assertEqual(rc, 0)
        self.assertNotIn("From stdin", stdout)
        # And the row is still on disk.
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        self.assertEqual(data[-1]["next"], "dom: step")

    def test_from_stdin_with_no_input_writes_no_rows(self):
        # An empty stdin is a no-op, the way ``xargs jspace seam``
        # would pass no arguments. ``--from-stdin`` alone with
        # no input is a legal, empty call.
        rc, stdout, _ = _run(self.workspace,
                              ["seam", "--from-stdin",
                               "--dry-run", "--json"],
                              "")
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        joined = " ".join(payload["warnings"])
        self.assertIn("from-stdin: 0 next actions recorded", joined)
