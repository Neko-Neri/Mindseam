"""Test the ``info`` aggregate digest subcommand.

Borrowed from the ``gh repo view`` / ``kubectl cluster-info`` /
``cargo metadata`` pattern: a single read-only subcommand that
exposes controller state in two faces — a human-readable text
section, and a ``--json`` payload that mirrors it for hosts. The
implementation reuses only the baseline ``read_history`` and
``read_ledger`` helpers; it does not depend on the detector layer
that lives in later rounds.
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
JSPACE = ROOT / "j-space" / "scripts" / "jspace.py"


def _invoke(args, cwd):
    return subprocess.run(
        [sys.executable, str(JSPACE), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
    )


class InfoSubcommandTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _open_ledger(self, goal="ship the info subcommand", nxt="dom: first action"):
        r = _invoke(
            ["note", "--goal", goal, "--next", nxt], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_info_text_lists_ledger_counts(self):
        self._open_ledger()
        r = _invoke(["info"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        for label in ("Goal:", "Core:", "Verified:", "Open:",
                      "Next:", "History:"):
            self.assertIn(label, r.stdout)

    def test_info_text_warns_when_no_ledger(self):
        r = _invoke(["info"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Warning: no goal set", r.stdout)
        self.assertIn("Warning: next action is not set", r.stdout)

    def test_info_json_is_valid_and_sectioned(self):
        self._open_ledger()
        r = _invoke(["info", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        for key in ("ledger", "history_count", "last_seam", "warnings"):
            self.assertIn(key, payload)
        ledger = payload["ledger"]
        self.assertEqual(ledger["goal"], "ship the info subcommand")
        self.assertEqual(ledger["next"], "dom: first action")
        self.assertEqual(ledger["core_count"], 0)
        self.assertEqual(ledger["verified_count"], 0)
        self.assertEqual(ledger["open_count"], 0)
        self.assertEqual(payload["history_count"], 0)
        self.assertIsNone(payload["last_seam"]["t"])
        self.assertEqual(payload["last_seam"]["gap_seconds"], None)

    def test_info_text_and_json_share_warnings(self):
        r = _invoke(["info"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        text = r.stdout
        r = _invoke(["info", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        for warning in payload["warnings"]:
            self.assertIn(warning, text)

    def test_info_text_marks_long_gap_after_history_grows(self):
        self._open_ledger()
        # Run a seam to materialise history.json, then rewind every
        # timestamp so the last entry is older than RESUME_GAP. The
        # ``info`` subcommand is read-only and never appends to
        # history, so the rewound state stays put across subsequent
        # invocations.
        _invoke(["seam", "--json"], cwd=self.workspace)
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        for row in data:
            row["t"] = 0
        history.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(["info"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("long gap", r.stdout)
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["last_seam"]["long_gap"])
        self.assertEqual(
            sum(1 for w in payload["warnings"]
                if "older than the resume gap" in w), 1)

    def test_info_warnings_only_prints_only_warnings(self):
        # Borrowed from ``gh run list --state failed``: print
        # only the warning lines, the way a CI hook would when
        # it just wants to know whether the workspace is healthy
        # enough to advance.
        r = _invoke(["info", "--warnings-only"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # No ledger, no history, no long-gap lines — just warnings.
        self.assertNotIn("Ledger:", r.stdout)
        self.assertNotIn("History:", r.stdout)
        self.assertNotIn("── j-space ─ info", r.stdout)
        # But every warning the full path would have shown is
        # still here.
        for warning in ("no goal set", "next action is not set",
                        "no seams recorded yet"):
            self.assertIn(warning, r.stdout)
        # And the warning marker is the "Warning: " prefix the
        # text path uses, so ``grep ^Warning:`` works on a host.
        for line in r.stdout.splitlines():
            self.assertTrue(
                line.startswith("Warning: "),
                "unexpected line in --warnings-only output: %r" % line,
            )

    def test_info_warnings_only_with_ledger_drops_no_goal_warning(self):
        # A populated ledger removes the "no goal set" and
        # "next action is not set" warnings. The
        # ``--warnings-only`` path must respect that, the way
        # the full path does.
        self._open_ledger()
        r = _invoke(["info", "--warnings-only"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("no goal set", r.stdout)
        self.assertNotIn("next action is not set", r.stdout)

    def test_info_warnings_only_composes_with_json(self):
        # ``--warnings-only`` and ``--json`` are independent: the
        # JSON payload still carries every section, with the full
        # ``warnings`` list, and the text mode is the one that
        # shortens to only the warning lines.
        self._open_ledger()
        r = _invoke(
            ["info", "--warnings-only", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        for key in ("ledger", "history_count", "last_seam", "warnings"):
            self.assertIn(key, payload)

    def test_info_version_prints_version_string(self):
        # Borrowed from ``gh --version`` / ``kubectl version`` /
        # ``aws --version``: print the controller's version on its
        # own line so a host can grep, pipe, or capture it.
        r = _invoke(["info", "--version"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The version starts with the program name and a space, the
        # way ``gh 2.40.0 (2024-...`` / ``kubectl version: v1.29`` do.
        self.assertTrue(
            r.stdout.startswith("jspace "),
            "expected version prefix; got: %r" % r.stdout)
        # The rest of the line is the version string, non-empty.
        self.assertTrue(len(r.stdout.strip()) > len("jspace "))

    def test_info_version_json_round_trip(self):
        # ``--json --version`` is the alternative face for the
        # same field, the way the other subcommands expose it.
        r = _invoke(["info", "--version", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("version", payload)
        self.assertTrue(len(payload["version"]) > 0)
        # The version in JSON must match the in-process constant.
        sys.path.insert(0, str(
            Path(__file__).resolve().parent.parent
            / "j-space" / "scripts"))
        import jspace
        self.assertEqual(payload["version"], jspace.__version__)

    def test_info_version_matches_full_output(self):
        # When ``--version`` is not passed, the full info digest
        # still carries a ``Version:`` line so a host that only
        # wants text does not have to remember a second flag.
        self._open_ledger()
        r = _invoke(["info"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Version:", r.stdout)

    def test_info_human_renders_seconds_as_minutes(self):
        # Borrowed from ``df -h`` / ``git log --relative-date``:
        # the text path renders time spans in the most natural
        # unit rather than raw seconds. A 120-second gap shows
        # as ``2 minutes ago`` rather than ``120 seconds ago``.
        self._open_ledger()
        # Materialise one history row and rewind its timestamp so
        # the gap is exactly 120 seconds.
        _invoke(["seam", "--json"], cwd=self.workspace)
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        data[0]["t"] = int(time.time()) - 120
        history.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(["info", "--human"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The text path picks the largest natural unit, ``minutes``
        # in this case, and the value pluralises when the count
        # is not 1.
        self.assertIn("2 minutes ago", r.stdout)
        self.assertNotIn("120 seconds", r.stdout)

    def test_info_human_renders_seconds_when_below_minute(self):
        # A 30-second gap stays in seconds, the way ``df -h``
        # stays in bytes when the value is below 1K.
        self._open_ledger()
        _invoke(["seam", "--json"], cwd=self.workspace)
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        data[0]["t"] = int(time.time()) - 30
        history.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(["info", "--human"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("30 seconds ago", r.stdout)

    def test_info_human_json_round_trip(self):
        # The ``--json`` path exposes both the raw ``gap_seconds``
        # and the human form under ``payload["human"]["gap_human"]``
        # so a host can pick the shape it needs. The text path
        # appends `` ago``; the JSON path stays numeric so a host
        # can compose it as it sees fit.
        self._open_ledger()
        _invoke(["seam", "--json"], cwd=self.workspace)
        history = Path(self.workspace) / ".jspace" / "history.json"
        data = json.loads(history.read_text(encoding="utf-8"))
        data[0]["t"] = int(time.time()) - 3600
        history.write_text(json.dumps(data), encoding="utf-8")
        r = _invoke(["info", "--human", "--json"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["human"]["gap_seconds"], 3600)
        self.assertEqual(payload["human"]["gap_human"], "1 hour")
        # ``last_seam.gap_seconds`` still carries the raw value.
        self.assertEqual(payload["last_seam"]["gap_seconds"], 3600)


if __name__ == "__main__":
    unittest.main()
