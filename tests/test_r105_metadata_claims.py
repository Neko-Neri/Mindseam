# -*- coding: utf-8 -*-
"""Round 67 guards: repository metadata claims cross-check.

Files that reference each other drift silently: THIRD_PARTY_NOTICES
names four arXiv identifiers and says they appear in the science
reference; CITATION.cff and README.md both publish the version DOI and
the all-releases concept DOI; the CITATION version string must equal
the suite version the README title carries. All four cross-references
verified true today and are pinned here.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

README = (ROOT / "README.md").read_text(encoding="utf-8")
CFF = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
NOTICES = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
SCIENCE = (ROOT / "mindseam" / "references" / "mindseam-science.md") \
    .read_text(encoding="utf-8")

ARXIV_IDS = ("2510.27338", "2509.15541", "2501.12948", "1704.06960")


class MetadataClaimsTests(unittest.TestCase):

    def test_notices_arxiv_ids_appear_in_the_science_reference(self):
        for aid in ARXIV_IDS:
            self.assertIn(aid, SCIENCE, aid)
            self.assertIn(aid, NOTICES, aid)

    def test_version_doi_matches_between_citation_and_readme(self):
        dois = re.findall(r"10\.5281/zenodo\.\d+", CFF)
        self.assertGreaterEqual(len(set(dois)), 2)
        for doi in set(dois):
            self.assertIn(doi, README, doi)

    def test_citation_version_matches_the_readme_title(self):
        version = re.search(r'^version: "(.+)"', CFF, re.M).group(1)
        self.assertIn("V%s" % version, README)

    def test_notices_referenced_from_readme(self):
        self.assertIn("THIRD_PARTY_NOTICES.md", README)

    def test_contributing_mentions_both_verification_commands(self):
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("integrity check", contributing)
        self.assertIn("test suite", contributing)


if __name__ == "__main__":
    unittest.main()
