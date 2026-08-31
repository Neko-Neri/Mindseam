# -*- coding: utf-8 -*-
"""Round 73 guards: no placeholders ship, links are well-formed.

A shipped skill file carrying a TODO/FIXME/TBD is a promise to finish
work the reader cannot see; a malformed link is a hand-off that cannot
be followed. The sweep found neither today (the one "todo" hit is the
stub-detector's generic-word list, not a placeholder), and both
properties are pinned: no placeholder markers in any shipped file, and
every http(s) URL across the skill parses without spaces or trailing
punctuation.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SHIPPED = ([p for p in (ROOT / "mindseam").rglob("*.md")]
           + [ROOT / "README.md", ROOT / "README.zh-CN.md",
              ROOT / "CONTRIBUTING.md", ROOT / "THIRD_PARTY_NOTICES.md"])

PLACEHOLDER_PAT = re.compile(
    r"TODO|FIXME|XXX|TBD\b|placeholder|待补|待填", re.I)


class NoPlaceholdersTests(unittest.TestCase):

    def test_no_placeholder_markers_in_shipped_files(self):
        hits = []
        for path in SHIPPED:
            text = path.read_text(encoding="utf-8")
            for match in PLACEHOLDER_PAT.finditer(text):
                line = text[:match.start()].count("\n") + 1
                hits.append("%s:%d" % (path.name, line))
        self.assertEqual(hits, [], "placeholder markers shipped: %s" % hits)

    def test_urls_are_well_formed(self):
        bad = []
        for path in SHIPPED:
            text = path.read_text(encoding="utf-8")
            for url in re.findall(r"https?://[^\s)>\]]+", text):
                if " " in url or url.endswith((",", ".", ";")):
                    bad.append((path.name, url))
        self.assertEqual(bad, [], "malformed URLs: %s" % bad)

    def test_the_reference_files_carry_sources(self):
        for name in ("mindseam-science.md", "induction-playbook.md"):
            text = (ROOT / "mindseam" / "references" / name) \
                .read_text(encoding="utf-8")
            self.assertRegex(
                text, r"https?://",
                "%s carries no external source links" % name)


if __name__ == "__main__":
    unittest.main()
