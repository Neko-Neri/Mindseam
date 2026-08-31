"""Test ``seam --quiet``: borrow the ``pytest -q`` / ``cargo --quiet`` /
``npm test --silent`` family of output-silencing flags.

The baseline ``seam`` prints a banner, a ledger echo, telemetry,
trend, remediation, the heal list and a next-empty reminder.
``--quiet`` drops every one of those and prints only the observation
facts, one per line, in the order ``observations`` produced them.
The exit code still follows the baseline contract: 0 on success.
The flag is independent of ``--json`` (a host can ask for either
or both, with no interaction).
"""

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


class SeamQuietFlagTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _open_ledger(self, goal="quiet demo", nxt="dom: first action"):
        r = _invoke(
            ["note", "--goal", goal, "--next", nxt], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def _stale_next(self):
        # The baseline ``observations`` function fires a fact only
        # when ``len({h["next"] for h in run}) == 1 and run[0]["next"]``
        # over the trailing STALL_RUN (=3) rows. ``_open_ledger``
        # calls ``note``, which does not write history; the first
        # real seam is the one that materialises row 0, and the
        # two that follow it give us three trailing rows that
        # share the same next. The dry-run call after them is
        # the one that reads the trailing window; it does not
        # append, so the three real seams before it are what makes
        # the fact fire.
        self._open_ledger()
        for _ in range(3):
            r = _invoke(["seam"], cwd=self.workspace)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_quiet_drops_banner_ledger_telemetry(self):
        self._open_ledger()
        # A fresh ledger with one seam so far does not fire any
        # observations fact — the history is still too short.
        # ``--quiet`` must therefore produce no output at all
        # rather than printing a banner.
        r = _invoke(["seam", "--quiet", "--dry-run"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # No banner, no ledger echo, no telemetry, no trend, no
        # remediation, no next-empty reminder. And no dry-run
        # marker, because that marker is part of the verbose
        # path that --quiet suppresses.
        self.assertNotIn("── mindseam ─ seam", r.stdout)
        self.assertNotIn("Goal:", r.stdout)
        self.assertNotIn("Telemetry:", r.stdout)
        self.assertNotIn("Trend:", r.stdout)
        self.assertNotIn("Remediation:", r.stdout)
        self.assertNotIn("dry-run: history.json was not updated", r.stdout)
        self.assertNotIn("`Next` is never empty", r.stdout)
        # The output is truly empty — quiet at its quietest.
        self.assertEqual(r.stdout, "")

    def test_quiet_prints_only_facts_one_per_line(self):
        self._stale_next()
        r = _invoke(["seam", "--quiet", "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The baseline ``observations`` fires two stalled-window
        # facts once the next has not moved and verification is
        # frozen; ``--quiet`` prints one fact per line, no banner,
        # no per-fact bullet, no follow-up prose.
        self.assertIn("Your next action has been the same", r.stdout)
        self.assertIn("Nothing new has been verified", r.stdout)
        # No banner, no per-fact bullet, no follow-up prose.
        self.assertNotIn("── mindseam ─ seam", r.stdout)
        self.assertNotIn("· ", r.stdout)
        self.assertNotIn("You would not have noticed that", r.stdout)
        # Every line is a fact line; nothing else slipped in.
        for line in r.stdout.splitlines():
            self.assertTrue(
                line.startswith("Your next action has been the same")
                or line.startswith("Nothing new has been verified"),
                "unexpected line in quiet output: %r" % line,
            )

    def test_quiet_still_writes_history_json(self):
        # --quiet is about output, not about side effects: the
        # seam still appends a row, just like the verbose path.
        self._open_ledger()
        r = _invoke(["seam", "--quiet"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        history = Path(self.workspace) / ".mindseam" / "history.json"
        self.assertTrue(history.exists())
        import json
        self.assertEqual(len(json.loads(history.read_text(
            encoding="utf-8"))), 1)

    def test_quiet_and_json_compose(self):
        # ``--quiet`` and ``--json`` are independent flags: ``--quiet``
        # trims the human-readable prose and ``--json`` switches to
        # machine-readable output. The two flags together must
        # still produce a valid JSON payload that the host can
        # consume. The history file does grow between two
        # successive ``seam`` calls — that is the baseline contract
        # for either flag — so the JSON ``history_count`` will
        # differ; we strip it before comparing.
        self._open_ledger()
        verbose = _invoke(["seam", "--json"], cwd=self.workspace)
        self.assertEqual(verbose.returncode, 0, verbose.stderr)
        quiet = _invoke(["seam", "--quiet", "--json"],
                         cwd=self.workspace)
        self.assertEqual(quiet.returncode, 0, quiet.stderr)
        import json
        verbose_payload = json.loads(verbose.stdout)
        quiet_payload = json.loads(quiet.stdout)
        # Same key set: the JSON contract is the same with or
        # without ``--quiet``.
        self.assertEqual(set(verbose_payload.keys()),
                         set(quiet_payload.keys()))
        # And every section except the history count is
        # identical: ``--quiet`` is a presentation flag, not a
        # logic flag.
        for key in verbose_payload:
            if key == "history_count":
                continue
            self.assertEqual(verbose_payload[key], quiet_payload[key],
                             "mismatch in key %r" % key)


if __name__ == "__main__":
    unittest.main()
