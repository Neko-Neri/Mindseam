# -*- coding: utf-8 -*-
"""Round 61 guards: the package stays distributable.

The README tells users to copy mindseam/ into their Skills directory and
says the LICENSE and THIRD_PARTY_NOTICES must travel with it; the repo
promises .mindseam/ working state never gets committed. The guards pin
the distribution contract: the legal files exist and are referenced,
the gitignore covers runtime state and Python caches, and the shipped
ledger template's sections are exactly the controller's SECTIONS.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

TEMPLATE = (ROOT / "mindseam" / "scripts" / "workspace-ledger.md") \
    .read_text(encoding="utf-8")


class DistributionTests(unittest.TestCase):

    def test_legal_files_exist_and_are_referenced(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            self.assertTrue((ROOT / name).exists(), name)
            self.assertIn(name, readme)

    def test_gitignore_covers_runtime_state_and_caches(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".mindseam/", text)
        self.assertIn("__pycache__/", text)

    def test_template_sections_match_the_controller(self):
        import re
        sections = re.findall(r"^## (.+)$", TEMPLATE, re.M)
        # The blank shell comes first; the template's own guidance
        # sections follow it.
        self.assertEqual(
            sections[:len(mindseam.SECTIONS)], list(mindseam.SECTIONS),
            "template sections drifted from SECTIONS")

    def test_template_is_copyable_blank(self):
        # The fenced blank shell must contain no pre-filled rows.
        import re
        fence = re.search(r"```markdown\n(.*?)```", TEMPLATE, re.S)
        self.assertIsNotNone(fence)
        blank = fence.group(1)
        for section in mindseam.SECTIONS:
            self.assertIn("## " + section, blank)
        self.assertNotIn("- ", blank)

    def test_citation_file_exists(self):
        self.assertTrue((ROOT / "CITATION.cff").exists())


if __name__ == "__main__":
    unittest.main()
