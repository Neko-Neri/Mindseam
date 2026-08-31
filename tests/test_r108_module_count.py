# -*- coding: utf-8 -*-
"""Round 70 guards: stated module counts match the shipped modules.

The persistence and verification-gate modules were added after the
packaging text was written; both READMEs still advertised "nine
selectively loaded modules" while eleven shipped. The guard derives the
true count from modules/ and requires the READMEs to name it, in both
English and Chinese.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODULES = sorted((ROOT / "mindseam" / "modules").glob("*.md"))

EN_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
            6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
            11: "eleven", 12: "twelve"}
ZH_WORDS = {1: "一个", 2: "两个", 3: "三个", 4: "四个", 5: "五个",
            6: "六个", 7: "七个", 8: "八个", 9: "九个", 10: "十个",
            11: "十一个", 12: "十二个"}


class ModuleCountTests(unittest.TestCase):

    def test_readme_states_the_true_module_count(self):
        count = len(MODULES)
        en = (ROOT / "README.md").read_text(encoding="utf-8")
        zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn(
            EN_WORDS[count] + " selectively loaded modules", en,
            "README.md misstates the module count (%d shipped)" % count)
        self.assertIn(
            EN_WORDS[count] + " focused modules", en)
        self.assertIn(ZH_WORDS[count], zh,
                      "README.zh-CN.md misstates the module count")

    def test_the_stale_count_words_are_gone(self):
        en = (ROOT / "README.md").read_text(encoding="utf-8")
        zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        count = len(MODULES)
        for wrong in range(1, 13):
            if wrong == count:
                continue
            self.assertNotIn(
                EN_WORDS[wrong] + " selectively loaded", en)
            self.assertNotIn(EN_WORDS[wrong] + " focused modules", en)
            self.assertNotIn(
                "入口、" + ZH_WORDS[wrong], zh)

    def test_every_module_is_named_in_the_skill_routing(self):
        skill = (ROOT / "mindseam" / "SKILL.md").read_text(encoding="utf-8")
        for module in MODULES:
            self.assertIn("modules/" + module.name, skill)


if __name__ == "__main__":
    unittest.main()
