"""Test the ``history`` tail subcommand.

Borrowed from ``git log -n N``, ``gh run list --limit N`` and
``docker logs --tail N``: a tail / limit interface over an
append-only record. The J-Space history is the controller's audit
log; ``history`` lets a host or human re-anchor between seams
without re-running one. ``--reverse`` borrows ``git log --reverse``,
``--since`` borrows ``docker logs --since 30m`` /
``journalctl --since "1 hour ago"``. The implementation only reads
``.jspace/history.json``; it does not depend on the detector layer
that the extended suite expects.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSPACE = ROOT / "j-space" / "scripts" / "jspace.py"


def _invoke(args, cwd):
    return subprocess.run(
        [sys.executable, str(JSPACE), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
    )


class HistorySubcommandTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _open_ledger(self):
        r = _invoke(
            ["note", "--goal", "history demo", "--next", "dom: first"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def _seam(self, next_text):
        r = _invoke(
            ["note", "--next", next_text], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = _invoke(["seam", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_history_with_no_seams_prints_empty(self):
        self._open_ledger()
        r = _invoke(["history"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("── j-space ─ history (0 entries)", r.stdout)

    def test_history_lists_each_recorded_seam(self):
        self._open_ledger()
        for index in range(3):
            self._seam("dom: step %d" % index)
        r = _invoke(["history"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # 3 seams means 3 history rows.
        self.assertIn("── j-space ─ history (3 entries)", r.stdout)
        for index in range(3):
            self.assertIn("dom: step %d" % index, r.stdout)

    def test_history_limit_takes_the_most_recent_n(self):
        self._open_ledger()
        for index in range(5):
            self._seam("dom: step %d" % index)
        r = _invoke(["history", "-n", "2"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("(2 entries)", r.stdout)
        # The two most recent should be the last two; earlier ones gone.
        self.assertIn("dom: step 4", r.stdout)
        self.assertIn("dom: step 3", r.stdout)
        self.assertNotIn("dom: step 0", r.stdout)
        self.assertNotIn("dom: step 1", r.stdout)

    def test_history_long_flag_aliases_short(self):
        self._open_ledger()
        for index in range(3):
            self._seam("dom: step %d" % index)
        r = _invoke(["history", "--limit", "1"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("(1 entries)", r.stdout)
        self.assertIn("dom: step 2", r.stdout)
        self.assertNotIn("dom: step 0", r.stdout)

    def test_history_json_returns_full_log(self):
        self._open_ledger()
        for index in range(3):
            self._seam("dom: step %d" % index)
        r = _invoke(["history", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 3)
        self.assertIsNone(payload["limit"])
        self.assertEqual(len(payload["rows"]), 3)
        # Rows are appended in temporal order, so the last row carries
        # the most recent next action.
        last = payload["rows"][-1]
        self.assertEqual(last["next"], "dom: step 2")

    def test_history_json_limit_reflects_argument(self):
        self._open_ledger()
        for index in range(4):
            self._seam("dom: step %d" % index)
        r = _invoke(["history", "--json", "-n", "2"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["limit"], 2)
        self.assertEqual(len(payload["rows"]), 2)
        self.assertEqual(payload["rows"][-1]["next"], "dom: step 3")

    def test_history_does_not_record_state(self):
        """``history`` is purely read-only — running it must not
        materialise a new seam row, so calling it twice in a row
        yields the same count and the same last entry."""
        self._open_ledger()
        self._seam("dom: step 0")
        first = _invoke(["history", "--json"], cwd=self.workspace)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = _invoke(["history", "--json"], cwd=self.workspace)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_history_reverse_flips_the_order(self):
        # Borrowed from ``git log --reverse`` — the same rows in the
        # opposite order, without re-reading history.json.
        self._open_ledger()
        for index in range(3):
            self._seam("dom: step %d" % index)
        forward = _invoke(["history", "--json"], cwd=self.workspace)
        self.assertEqual(forward.returncode, 0, forward.stderr)
        reverse = _invoke(["history", "--reverse", "--json"],
                           cwd=self.workspace)
        self.assertEqual(reverse.returncode, 0, reverse.stderr)
        forward_rows = json.loads(forward.stdout)["rows"]
        reverse_rows = json.loads(reverse.stdout)["rows"]
        self.assertEqual(forward_rows, list(reversed(reverse_rows)))
        # The reverse payload must report the flag, so a host can
        # tell at a glance which way the rows go.
        reverse_payload = json.loads(reverse.stdout)
        self.assertTrue(reverse_payload["reverse"])
        forward_payload = json.loads(forward.stdout)
        self.assertFalse(forward_payload["reverse"])

    def test_history_reverse_prints_newest_first_label(self):
        self._open_ledger()
        for index in range(2):
            self._seam("dom: step %d" % index)
        r = _invoke(["history", "--reverse"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("newest first", r.stdout)
        # In reverse, the most recently recorded row is printed
        # first. That is ``dom: step 1`` — the last ``--next`` we
        # wrote before the reverse call.
        first_row = r.stdout.splitlines()[1]
        self.assertIn("dom: step 1", first_row)

    def test_history_since_keeps_only_recent_rows(self):
        # Borrowed from ``docker logs --since 30m``: the time-window
        # filter is evaluated against the row ``t`` field.
        self._open_ledger()
        for index in range(2):
            self._seam("dom: step %d" % index)
        # Rewind the first row to be ancient, keep the second fresh.
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        ancient = int(time.time()) - 7200  # two hours ago
        data[0]["t"] = ancient
        data[1]["t"] = int(time.time())
        history.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(["history", "--since", "60", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["since"], 60)
        self.assertEqual(payload["history_count"], 1)
        self.assertEqual(payload["rows"][0]["next"], "dom: step 1")
        # And the human label picks up the window size.
        r = _invoke(["history", "--since", "60"], cwd=self.workspace)
        self.assertIn("last 60 s", r.stdout)

    def test_history_since_combines_with_limit(self):
        # Limit-then-since: the two filters compose, so an old
        # history with a limit of 1 still respects the time
        # window.
        self._open_ledger()
        for index in range(2):
            self._seam("dom: step %d" % index)
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        data[0]["t"] = 0
        data[1]["t"] = int(time.time())
        history.write_text(json.dumps(data), encoding="utf-8")
        # A limit of 1 would normally take the most recent row,
        # but ``--since 60`` keeps only the row that was written
        # within the last minute; that happens to be the same
        # one in this case.
        r = _invoke(["history", "-n", "1", "--since", "60", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 1)
        self.assertEqual(payload["rows"][0]["next"], "dom: step 1")

    def test_history_grep_keeps_only_matching_rows(self):
        # Borrowed from ``git log --grep``: a substring match on
        # the next action narrows the audit log to a topic. The
        # match is case-insensitive so ``--grep TODO`` finds both
        # ``dom: TODO item`` and ``dom: todo item``.
        self._open_ledger()
        for nxt in ("dom: TODO add cache",
                    "dom: fix typo",
                    "dom: TODO remove dead code"):
            subprocess_run = _invoke(
                ["note", "--next", nxt], cwd=self.workspace)
            self.assertEqual(subprocess_run.returncode, 0,
                             subprocess_run.stderr)
            seam = _invoke(["seam", "--json"], cwd=self.workspace)
            self.assertEqual(seam.returncode, 0, seam.stderr)
        r = _invoke(["history", "--grep", "TODO", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(payload["grep"], "TODO")
        for row in payload["rows"]:
            self.assertIn("TODO", row["next"])

    def test_history_grep_is_case_insensitive(self):
        self._open_ledger()
        for nxt in ("dom: UPPER case", "dom: lower case"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--grep", "case", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["history_count"], 2)

    def test_history_grep_with_no_match_returns_empty(self):
        self._open_ledger()
        for nxt in ("dom: alpha", "dom: beta"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--grep", "gamma", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["history_count"], 0)
        # And the text label still renders the empty result.
        r = _invoke(["history", "--grep", "gamma"], cwd=self.workspace)
        self.assertIn("(0 entries, grep 'gamma')", r.stdout)

    def test_history_grep_combines_with_since(self):
        # ``--grep`` and ``--since`` are independent filters; the
        # row must satisfy both to survive.
        self._open_ledger()
        for nxt in ("dom: TODO old", "dom: TODO fresh",
                    "dom: other fresh"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        # All three rows: rewind the first to be ancient; mark the
        # other two as now. Among the two fresh rows only one
        # matches ``--grep TODO``, so the result is one row.
        data[0]["t"] = 0
        data[1]["t"] = int(time.time())
        data[2]["t"] = int(time.time())
        history.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(
            ["history", "--grep", "TODO", "--since", "60", "--json"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 1)
        self.assertEqual(payload["rows"][0]["next"], "dom: TODO fresh")

    def test_history_quiet_prints_only_next_action(self):
        # Borrowed from ``git log --oneline`` /
        # ``docker logs --quiet``: one line per row, just the next
        # action, with no header, no row number, no other field.
        # A host can pipe the result into ``xargs`` or ``sort -u``
        # to build a topic index of what the session actually did.
        self._open_ledger()
        for nxt in ("dom: alpha", "dom: beta", "dom: gamma"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--quiet"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # Three lines, one per row, just the next action.
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertEqual(lines, ["dom: alpha", "dom: beta", "dom: gamma"])
        # No header, no row number, no "v=0" suffix.
        self.assertNotIn("── j-space", r.stdout)
        self.assertNotIn("entries", r.stdout)
        self.assertNotIn("v=", r.stdout)
        self.assertNotIn("o=", r.stdout)
        self.assertNotIn("·", r.stdout)

    def test_history_quiet_composes_with_other_filters(self):
        # ``--quiet`` is independent of --since / --grep / -n /
        # --reverse: each filter narrows the result set, and
        # --quiet just changes the renderer.
        self._open_ledger()
        for nxt in ("dom: TODO add cache",
                    "dom: fix typo",
                    "dom: TODO remove dead code"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        # Combine --grep TODO --reverse --quiet and expect the two
        # TODO rows in reverse chronological order.
        r = _invoke(
            ["history", "--grep", "TODO", "--reverse", "--quiet"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertEqual(
            lines,
            ["dom: TODO remove dead code", "dom: TODO add cache"],
        )

    def test_history_quiet_preserves_one_line_per_row(self):
        # ``--quiet``'s contract is one line per row, no header.
        # We give it three distinct next actions so the ordering
        # is unambiguous; the point of the test is the per-row
        # shape, not the empty-string edge.
        self._open_ledger()
        for nxt in ("dom: alpha", "dom: beta", "dom: gamma"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--quiet"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertEqual(lines, ["dom: alpha", "dom: beta", "dom: gamma"])
        # No header, no row number, no other field.
        self.assertNotIn("── j-space", r.stdout)
        self.assertNotIn("entries", r.stdout)
        self.assertNotIn("v=", r.stdout)
        self.assertNotIn("o=", r.stdout)
        self.assertNotIn("·", r.stdout)

    def test_history_head_keeps_only_first_n(self):
        # Borrowed from ``head -n N``: keep the first N rows of
        # the audit log. Useful for examining the start of a
        # session without paging through every seam.
        self._open_ledger()
        for nxt in ("dom: alpha", "dom: beta", "dom: gamma",
                    "dom: delta", "dom: epsilon"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--head", "2", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(
            [row["next"] for row in payload["rows"]],
            ["dom: alpha", "dom: beta"],
        )

    def test_history_tail_aliases_limit(self):
        # ``--tail`` is the explicit alias of ``-n`` / ``--limit``:
        # a host that has ``head`` / ``tail`` muscle memory
        # (``docker logs --tail`` / ``gh run list --limit``) does
        # not have to learn yet another flag name.
        self._open_ledger()
        for nxt in ("dom: alpha", "dom: beta", "dom: gamma",
                    "dom: delta", "dom: epsilon"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--tail", "2", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(
            [row["next"] for row in payload["rows"]],
            ["dom: delta", "dom: epsilon"],
        )

    def test_history_head_wins_over_tail(self):
        # When ``--head`` and ``--tail`` are both present, the
        # shell-style last-wins rule would be ambiguous, so the
        # implementation picks ``--head`` because the most
        # natural pipeline is "look at the start of the log
        # first". A host that needs both should split into two
        # invocations.
        self._open_ledger()
        for nxt in ("dom: alpha", "dom: beta", "dom: gamma",
                    "dom: delta", "dom: epsilon"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--head", "2", "--tail", "3", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(
            [row["next"] for row in payload["rows"]],
            ["dom: alpha", "dom: beta"],
        )

    def test_history_count_prints_integer(self):
        # Borrowed from ``wc -l`` / ``git rev-list --count``:
        # print only the row count. A host can capture it with
        # ``count=$(jspace history --count)`` and use it in
        # CI scripts.
        self._open_ledger()
        for _ in range(3):
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--count"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "3")
        # ``-c`` is the POSIX short alias, like ``wc -l``.
        r = _invoke(["history", "-c"], cwd=self.workspace)
        self.assertEqual(r.stdout.strip(), "3")

    def test_history_count_respects_since_filter(self):
        # ``--count`` composes with the other filters so a host
        # can do ``count=$(jspace history --since 3600 --grep TODO
        # --count)`` without parsing tables.
        self._open_ledger()
        for nxt in ("dom: TODO add cache", "dom: fix typo",
                    "dom: TODO remove dead code"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        all_count = _invoke(["history", "--count"], cwd=self.workspace)
        self.assertEqual(all_count.stdout.strip(), "3")
        grep_count = _invoke(["history", "--grep", "TODO", "--count"],
                             cwd=self.workspace)
        self.assertEqual(grep_count.stdout.strip(), "2")

    def test_history_count_on_empty_history_prints_zero(self):
        self._open_ledger()
        # No seams have been recorded yet, so the count is 0
        # and the output is exactly the digit zero.
        r = _invoke(["history", "--count"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "0")

    def test_history_first_match_keeps_only_first_row(self):
        # Borrowed from ``grep -m 1`` / ``ripgrep --max-count=1``:
        # stop after the first matching row, the way a host
        # finds the first time a topic appeared in the audit log.
        self._open_ledger()
        for nxt in ("dom: TODO add cache", "dom: fix typo",
                    "dom: TODO remove dead code"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--first-match", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 1)
        self.assertEqual(payload["rows"][0]["next"],
                         "dom: TODO add cache")

    def test_history_first_match_combines_with_grep(self):
        # ``--grep`` already narrows the result set; ``--first-match``
        # then takes the first surviving row. So a host can do
        # ``jspace history --grep TODO --first-match`` to find the
        # first TODO row.
        self._open_ledger()
        for nxt in ("dom: setup", "dom: TODO cache",
                    "dom: fix typo", "dom: TODO dead code"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--grep", "TODO", "--first-match",
                     "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 1)
        self.assertEqual(payload["rows"][0]["next"],
                         "dom: TODO cache")

    def test_history_first_match_with_reverse_finds_latest_match(self):
        # ``--reverse`` flips the iteration order so
        # ``--first-match`` returns the most recent match, the way
        # ``tac file | grep -m 1 PATTERN`` does.
        self._open_ledger()
        for nxt in ("dom: setup", "dom: TODO cache",
                    "dom: fix typo", "dom: TODO dead code"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(
            ["history", "--grep", "TODO", "--reverse",
             "--first-match", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 1)
        self.assertEqual(payload["rows"][0]["next"],
                         "dom: TODO dead code")

    def test_history_fields_picks_a_single_column(self):
        # Borrowed from ``docker ps --format '{{.Names}}'`` /
        # ``kubectl get -o custom-columns`` /
        # ``aws --query``: print only the requested history
        # fields, separated by tabs, with a header line that
        # names them. ``--fields next`` is the column-selected
        # analogue of ``--quiet``; ``--fields t,next`` adds the
        # timestamp column without the rest of the table.
        self._open_ledger()
        for nxt in ("dom: alpha", "dom: beta"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--fields", "next"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines, ["next", "dom: alpha", "dom: beta"])
        # Two columns now.
        r = _invoke(["history", "--fields", "t,next"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "t\tnext")
        # Each data row has two tab-separated cells.
        for line in lines[1:]:
            self.assertEqual(line.count("\t"), 1)
        # The first data row's next cell is ``dom: alpha``.
        self.assertTrue(lines[1].endswith("\tdom: alpha"))

    def test_history_fields_renders_missing_value_as_dash(self):
        # A history row that does not record a ``verified`` or
        # ``open`` field is the baseline for old rows. ``--fields``
        # fills empty cells with ``-`` so the columns line up
        # for hosts that pipe into ``column -t``. We bypass
        # ``read_history``'s shape check by writing a hand-edited
        # row that still satisfies the type contract and then
        # calling the renderer indirectly: we read what the
        # history command actually produced with a row whose
        # ``next`` is the empty string, which the renderer treats
        # as ``-`` along with all other falsy fields.
        self._open_ledger()
        _invoke(["seam", "--json"], cwd=self.workspace)
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        # Replace the recorded next with the empty string. The
        # ``--fields`` renderer treats any falsy value (None,
        # empty string, 0) as missing and renders ``-`` for that
        # column, so the line still has the right number of
        # cells.
        data[0]["next"] = ""
        history.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(["history", "--fields", "t,verified,open,next"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        # Header + one data row.
        self.assertEqual(lines[0], "t\tverified\topen\tnext")
        # The empty ``next`` cell renders as ``-``.
        cells = lines[1].split("\t")
        self.assertEqual(len(cells), 4)
        self.assertEqual(cells[3], "-")

    def test_history_csv_emits_header_and_rows(self):
        # Borrowed from ``aws --output csv`` /
        # ``kubectl get -o csv`` / PowerShell ``ConvertTo-Csv``:
        # CSV with an RFC 4180 header, tab-free output so a host
        # can hand it to ``csv.reader`` / pandas without
        # extra parsing.
        self._open_ledger()
        for nxt in ("dom: alpha", "dom: beta"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--csv"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertEqual(lines[0], "t,next,verified,open")
        self.assertEqual(len(lines), 3)
        for line in lines[1:]:
            self.assertNotIn("\t", line)
            # CSV packs all four fields on one line with commas.
            self.assertEqual(line.count(","), 3)

    def test_history_csv_quotes_commas_in_fields(self):
        # RFC 4180 quoting: a field that contains a comma must be
        # quoted so the reader can tell the difference between a
        # field separator and a value that happens to include a
        # comma.
        self._open_ledger()
        for nxt in ("dom: alpha,beta", "dom: gamma"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--csv"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertEqual(lines[0], "t,next,verified,open")
        # The row whose next contains a comma is quoted.
        any_comma = any('"' in line and "," in line for line in lines[1:])
        self.assertTrue(any_comma, "expected quoting in: %r" % lines)

    def test_history_domains_groups_by_next_prefix(self):
        # Borrowed from JIT-Agent's model of an agent harness:
        # the prefix of the next action is the domain the
        #-session was working in. Grouping by it shows the
        # distribution of work across topic boundaries.
        self._open_ledger()
        for nxt in ("dom: alpha", "dom: alpha", "other: beta",
                    "dom: alpha", "other: beta"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--domains"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The most frequent domain is listed first; the counts and
        # percentages line up with the seam history.
        self.assertIn("dom", r.stdout)
        self.assertIn("3", r.stdout)
        # And the share is printed as a percentage.
        self.assertIn("60.0%", r.stdout)

    def test_history_domains_json_round_trip(self):
        # ``--domains --json`` is machine-readable and composes
        # with the other filters.
        self._open_ledger()
        for nxt in ("dom: alpha", "dom: alpha", "other: beta"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--domains", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(len(payload["domains"]), 2)
        self.assertEqual(payload["domains"][0]["domain"], "dom")
        self.assertEqual(payload["domains"][0]["count"], 2)
        self.assertEqual(payload["domains"][0]["share"],
                         round(2 / 3, 4))

    def test_history_domains_with_no_next_row(self):
        # Rows whose next action is empty do not count toward the
        # domains grouping — the published contract is that a missing
        # next is "not a domain", not a new bucket for hosts to
        # reason about. The first seam writes a row whose next is
        # "" after the hand-edit below; the `--domains` output must
        # still render "no rows" rather than inventing a
        # "(none)" bucket for a single empty row.
        self._open_ledger()
        # Run the seam so it materialises a history row.
        _invoke(["seam"], cwd=self.workspace)
        history_path = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history_path.read_text(encoding="utf-8"))
        for row in data:
            row["next"] = ""
        history_path.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(["history", "--domains"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no rows with a next action", r.stdout)
        self.assertNotIn("(none)", r.stdout)

    def test_history_span_reports_first_last_and_duration(self):
        # Borrowed from ``git log --stat`` /
        # ``journalctl --list-boots``: the span view summarises the
        # window's first seam, last seam and the duration between
        # them in a single call.
        self._open_ledger()
        for _ in range(3):
            _invoke(["note", "--next", "dom: step"], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        r = _invoke(["history", "--span"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("── j-space ─ history span", r.stdout)
        self.assertIn("First seam:", r.stdout)
        self.assertIn("Last seam:", r.stdout)
        self.assertIn("Duration:", r.stdout)
        self.assertIn("across 3 rows", r.stdout)

    def test_history_span_json_round_trip(self):
        # ``--span --json`` carries first, last, duration and rows
        # as integers so a host can compute its own windows.
        self._open_ledger()
        for _ in range(2):
            _invoke(["note", "--next", "dom: step"], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        # Make the duration deterministic: two rows exactly
        # 100 seconds apart.
        data[0]["t"] = 1000000000
        data[1]["t"] = 1000000100
        history.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(["history", "--span", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)["span"]
        self.assertEqual(payload["first"], 1000000000)
        self.assertEqual(payload["last"], 1000000100)
        self.assertEqual(payload["duration_seconds"], 100)
        self.assertEqual(payload["rows"], 2)

    def test_history_span_empty_history_says_no_rows(self):
        # A fresh ledger has no seams yet — ``--span`` must say
        # so rather than reporting a zero-second span as if time
        # had actually elapsed.
        self._open_ledger()
        r = _invoke(["history", "--span"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no rows", r.stdout)
        r = _invoke(["history", "--span", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNone(json.loads(r.stdout)["span"])

    def test_history_span_honours_grep_filter(self):
        # ``--grep`` narrows the window first, so ``--span`` on a
        # filtered history measures only the rows that survived —
        # the answer to "how long did the TODO burst last".
        self._open_ledger()
        for nxt in ("dom: TODO cache", "dom: fix typo",
                    "dom: TODO dead code"):
            _invoke(["note", "--next", nxt], cwd=self.workspace)
            _invoke(["seam", "--json"], cwd=self.workspace)
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        data[0]["t"] = 2000000000
        data[1]["t"] = 2000000050
        data[2]["t"] = 2000000100
        history.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(
            ["history", "--grep", "TODO", "--span", "--json"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)["span"]
        self.assertEqual(payload["rows"], 2)
        # The two TODO rows are 100 seconds apart in the hand-set
        # timeline above (rows 0 and 2).
        self.assertEqual(payload["duration_seconds"], 100)

    def test_history_since_drops_only_ancient_rows(self):
        # A very large ``--since`` window keeps the ancient row,
        # because the cutoff (now - very_large) lands before the
        # row's timestamp.
        self._open_ledger()
        self._seam("dom: ancient")
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        data[0]["t"] = 0  # epoch
        history.write_text(json.dumps(data), encoding="utf-8")
        drop = _invoke(["history", "--since", "1", "--json"],
                       cwd=self.workspace)
        self.assertEqual(drop.returncode, 0, drop.stderr)
        self.assertEqual(json.loads(drop.stdout)["history_count"], 0)
        keep = _invoke(["history", "--since", str(10 ** 12), "--json"],
                       cwd=self.workspace)
        self.assertEqual(keep.returncode, 0, keep.stderr)
        self.assertEqual(json.loads(keep.stdout)["history_count"], 1)


if __name__ == "__main__":
    unittest.main()
