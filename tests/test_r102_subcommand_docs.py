# -*- coding: utf-8 -*-
"""Round 64 guards: documented subcommands are real subcommands.

The round-69 drift guard checks that every documented CLI flag exists
in the parser; it never checked the subcommands themselves. A doc edit
that renamed or invented a subcommand (seam, note, ship, resume) would
have shipped unverified. The guard extracts every `mindseam.py <word>`
invocation from SKILL.md and both READMEs and requires each one to be
a subcommand argparse actually defines.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

SOURCE = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(encoding="utf-8")

DOCS = {
    "SKILL.md": (ROOT / "mindseam" / "SKILL.md").read_text(encoding="utf-8"),
    "README.md": (ROOT / "README.md").read_text(encoding="utf-8"),
    "README.zh-CN.md": (ROOT / "README.zh-CN.md")
        .read_text(encoding="utf-8"),
}


def parser_subcommands():
    block = re.search(r"sub = p\.add_subparsers\(.*?\)\n(.*?)\n    args =",
                      SOURCE, re.S)
    names = set(re.findall(r'sub\.add_parser\("([a-z]+)"',
                           block.group(0) if block else SOURCE))
    if not names:  # fallback: scan the whole file
        names = set(re.findall(r'sub\.add_parser\("([a-z]+)"', SOURCE))
    return names


class SubcommandDocsTests(unittest.TestCase):

    def test_the_parser_defines_the_expected_set(self):
        self.assertEqual(parser_subcommands(),
                         {"seam", "resume", "note", "ship", "skillbook", "info", "discover",
                          "history", "audit"})

    def test_every_documented_invocation_uses_a_real_subcommand(self):
        subs = parser_subcommands()
        for doc_name, text in DOCS.items():
            invocations = set()
            for match in re.finditer(r"scripts/mindseam\.py ([a-z]+)", text):
                invocations.add(match.group(1))
            unknown = invocations - subs
            self.assertFalse(
                unknown,
                "%s documents subcommands the parser does not "
                "define: %s" % (doc_name, unknown))

    def test_all_subcommands_are_documented_in_skill(self):
        skill = DOCS["SKILL.md"]
        for sub in ("seam", "note", "ship", "resume", "skillbook", "info",
                    "discover", "history", "audit"):
            self.assertIn("mindseam.py %s" % sub, skill)


if __name__ == "__main__":
    unittest.main()
