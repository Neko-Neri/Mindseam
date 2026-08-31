# -*- coding: utf-8 -*-
"""Round 40 guards: every relative reference inside the skill resolves.

The skill's selectivity depends on routing: SKILL.md points at modules,
modules hand off to each other and to references, and verify_suite
already checks that every module file is routed. This guard completes
the web in the other direction: every backtick-quoted relative path in
any shipped .md file must point at a file that exists, so a rename can
no longer strand a hand-off.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "mindseam"

REF_PAT = re.compile(
    r"`(\.\./)?(?:modules|references|scripts)/[A-Za-z0-9_./-]+`")


class DocLinkTests(unittest.TestCase):

    def test_every_relative_reference_resolves(self):
        broken = []
        for md in sorted(SKILL.rglob("*.md")):
            text = md.read_text(encoding="utf-8")
            for match in REF_PAT.finditer(text):
                ref = match.group(0).strip("`")
                target = (md.parent / ref).resolve()
                if not target.exists():
                    broken.append("%s -> %s" % (md.name, ref))
        self.assertEqual(
            broken, [], "dangling references: %s" % broken)

    def test_every_module_is_routed_from_skill_md(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        unrouted = [m.name for m in sorted((SKILL / "modules").glob("*.md"))
                    if ("modules/" + m.name) not in skill]
        self.assertEqual(unrouted, [])

    def test_reference_files_are_mentioned_somewhere(self):
        all_text = " ".join(
            md.read_text(encoding="utf-8") for md in SKILL.rglob("*.md"))
        orphaned = [r.name for r in sorted((SKILL / "references").glob("*.md"))
                    if r.name not in all_text]
        self.assertEqual(orphaned, [])


if __name__ == "__main__":
    unittest.main()
