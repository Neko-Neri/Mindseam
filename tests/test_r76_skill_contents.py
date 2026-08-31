# -*- coding: utf-8 -*-
"""Round 37 guards: the shipped skill directory contains what it claims.

debug_r39.py — a debug probe with a hardcoded absolute Windows path from
the round-39 session — was still sitting in mindseam/scripts/, which is
the directory the README tells users to copy wholesale into their
Skills folder. Anything in scripts/ ships to every user. The guard pins
the exact file set the skill documents: the controller, the verifier,
and the ledger template.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "mindseam" / "scripts"

EXPECTED = {
    "mindseam.py",
    "verify_suite.py",
    "workspace-ledger.md",
}


class SkillContentsTests(unittest.TestCase):

    def test_scripts_directory_is_exactly_the_documented_set(self):
        present = {p.name for p in SCRIPTS.iterdir()
                   if p.name != "__pycache__"}
        self.assertEqual(
            present, EXPECTED,
            "unexpected files in mindseam/scripts/: %s / missing: %s"
            % (present - EXPECTED, EXPECTED - present))

    def test_no_absolute_paths_hardcoded_in_shipped_scripts(self):
        for name in sorted(EXPECTED):
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            self.assertNotIn(
                r"d:\\", text.lower(),
                "%s hardcodes a machine-local path" % name)
            self.assertNotIn(
                r"c:\users", text.lower(),
                "%s hardcodes a user-local path" % name)


if __name__ == "__main__":
    unittest.main()
