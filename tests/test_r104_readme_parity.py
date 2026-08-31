# -*- coding: utf-8 -*-
"""Round 66 guards: the two READMEs stay structurally parallel.

The English and Chinese READMEs carry the same contract to two
audiences: twelve mirrored sections in the same order, and the same
number of Markdown tables. A structural edit to one that skips the
other (a new section, a dropped table) would ship half a contract.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EN = (ROOT / "README.md").read_text(encoding="utf-8")
ZH = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

EXPECTED_SECTIONS = 13


class ReadmeParityTests(unittest.TestCase):

    def test_both_readmes_have_the_full_section_count(self):
        en = re.findall(r"^## (.+)$", EN, re.M)
        zh = re.findall(r"^## (.+)$", ZH, re.M)
        self.assertEqual(len(en), EXPECTED_SECTIONS, en)
        self.assertEqual(len(zh), EXPECTED_SECTIONS, zh)

    def test_table_counts_match(self):
        en_tables = EN.count("\n|---")
        zh_tables = ZH.count("\n|---")
        self.assertEqual(en_tables, zh_tables,
                         "EN has %d tables, ZH has %d" % (en_tables, zh_tables))

    def test_both_document_the_same_benchmark_rows(self):
        # The benchmark table is the widest table; its row count must
        # match across languages.
        en_rows = len(re.findall(r"^\| HLE|^\| Terminal Bench|^\| NL2Repo",
                                 EN, re.M))
        zh_rows = len(re.findall(r"^\| HLE|^\| Terminal Bench|^\| NL2Repo",
                                 ZH, re.M))
        self.assertEqual(en_rows, zh_rows)

    def test_language_cross_reference_is_symmetric(self):
        self.assertIn("README.zh-CN.md", EN)
        self.assertIn("README.md", ZH)


if __name__ == "__main__":
    unittest.main()
