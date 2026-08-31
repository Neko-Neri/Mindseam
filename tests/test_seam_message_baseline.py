"""Test ``seam --message``: borrow the ``git commit -m`` /
``kubectl annotate`` / ``docker commit -m`` family of annotation
flags.

The ``--message`` flag attaches a human-meaningful annotation to
the recorded row, the way ``git commit -m`` attaches a commit
message and ``kubectl annotate`` attaches a string to a resource.
The annotation lands in the new ``msg`` field of the row, the way
``--fields msg`` can surface it later.
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


def _invoke(args, cwd):
    return subprocess.run(
        [sys.executable, str(MINDSEAM), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
    )


class SeamMessageFlagTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _open_ledger(self, goal="message demo", nxt="dom: first action"):
        r = _invoke(
            ["note", "--goal", goal, "--next", nxt], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_message_records_msg_field_on_history_row(self):
        # Borrowed from ``git commit -m``: the recorded row gains
        # a ``msg`` field. The next ``history --fields msg`` call
        # surfaces it.
        self._open_ledger()
        r = _invoke(["seam", "--message", "rolled back the cache"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The verbose path prints a ``Message:`` line so a human
        # can see the annotation in the same report as the
        # observations.
        self.assertIn("Message:   rolled back the cache", r.stdout)
        history = Path(self.workspace) / ".mindseam" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["msg"], "rolled back the cache")
        # And ``--fields msg`` surfaces the new field, the way
        # ``git log --format=%B`` would.
        r = _invoke(["history", "--fields", "next,msg", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0]["msg"],
                         "rolled back the cache")

    def test_message_msg_alias_works(self):
        # ``--msg`` is the conventional short alias the way
        # ``git commit -m`` and ``docker commit -m`` use it; the
        # long form is also accepted.
        self._open_ledger()
        r = _invoke(["seam", "--msg", "short form"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Message:   short form", r.stdout)
        history = Path(self.workspace) / ".mindseam" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        self.assertEqual(data[0]["msg"], "short form")

    def test_message_is_skipped_under_dry_run(self):
        # A dry-run must not commit a row, so the ``msg`` field
        # must also stay unwritten. The dry-run contract wins:
        # the analysis is informative, the ledger is unchanged.
        self._open_ledger()
        r = _invoke(
            ["seam", "--message", "preview only", "--dry-run", "--json"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        history = Path(self.workspace) / ".mindseam" / "history.json"
        # No row was ever written: history.json does not exist.
        self.assertFalse(history.exists())

    def test_message_composes_with_grep(self):
        # ``--grep`` substring-matches the ``msg`` field the way
        # it substring-matches the ``next`` field, so a host
        # can audit a session by searching its annotations.
        self._open_ledger()
        for nxt, msg in [
            ("dom: TODO add cache", "TICKET-101: add cache"),
            ("dom: fix typo", "drive-by fix"),
            ("dom: TODO dead code", "TICKET-102: remove dead code"),
        ]:
            r = _invoke(["note", "--next", nxt], cwd=self.workspace)
            self.assertEqual(r.returncode, 0, r.stderr)
            r = _invoke(["seam", "--message", msg], cwd=self.workspace)
            self.assertEqual(r.returncode, 0, r.stderr)
        r = _invoke(["history", "--grep", "TICKET", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        # Two rows carry the ``TICKET-`` prefix; the drive-by
        # fix does not.
        self.assertEqual(payload["history_count"], 2)
        for row in payload["rows"]:
            self.assertIn("TICKET", row["msg"])

    def test_no_message_does_not_add_msg_field(self):
        # Rows that do not set ``--message`` carry no ``msg``
        # field, the way rows that do not set a committer email
        # do not carry an ``author_email`` field. ``--fields msg``
        # on such a history still renders; the missing field
        # becomes ``-``.
        self._open_ledger()
        r = _invoke(["seam"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        history = Path(self.workspace) / ".mindseam" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        self.assertNotIn("msg", data[0])
        r = _invoke(["history", "--fields", "next,msg"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The ``msg`` cell renders as ``-``, the way the existing
        # ``--fields`` renderer treats any missing field.
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "next\tmsg")
        self.assertEqual(lines[1].split("\t")[1], "-")


if __name__ == "__main__":
    unittest.main()
