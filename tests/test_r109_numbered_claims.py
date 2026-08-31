# -*- coding: utf-8 -*-
"""Round 71 guards: numbered claims in the entry file count true things.

Round 70 caught both READMEs advertising nine modules while eleven
shipped. The same drift risk sits in every other number the docs
assert: SKILL.md's five workspace properties and three registers, and
the READMEs' three supporting references. The guard counts the real
items and requires each stated number to match.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKILL = (ROOT / "mindseam" / "SKILL.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
ZH = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

EN_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
          "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
          "eleven": 11}
ZH_NUM = {"一": 1, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
          "八": 8, "九": 9, "十": 10, "十一": 11}


class NumberedClaimsTests(unittest.TestCase):

    def test_five_workspace_properties_are_five(self):
        m = re.search(r"five documented functional properties", SKILL)
        self.assertIsNotNone(m, "SKILL.md no longer states the count")
        segment = SKILL[SKILL.index("five documented functional properties"):
                       SKILL.index("running alongside all five")]
        bullets = re.findall(r"^- \*\*", segment, re.M)
        arrows = re.findall(r"→ `modules/", segment)
        self.assertEqual(len(bullets), 5, bullets)
        self.assertEqual(len(arrows), 5, arrows)

    def test_three_registers_are_three(self):
        m = re.search(r"You write in three registers", SKILL)
        self.assertIsNotNone(m)
        registers = re.findall(r"^- \*\*(Inner|Ledger|Outer)\*\*", SKILL,
                               re.M)
        self.assertEqual(sorted(registers), ["Inner", "Ledger", "Outer"])

    def test_three_references_are_three(self):
        refs = sorted((ROOT / "mindseam" / "references").glob("*.md"))
        self.assertEqual(len(refs), 3, refs)
        self.assertIn("three supporting references", README)
        self.assertIn("三份支撑资料", ZH)

    def test_reference_files_are_routed_from_skill(self):
        for ref in (ROOT / "mindseam" / "references").glob("*.md"):
            self.assertIn("references/" + ref.name, SKILL)


if __name__ == "__main__":
    unittest.main()
