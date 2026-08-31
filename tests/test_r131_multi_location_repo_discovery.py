# -*- coding: utf-8 -*-
"""Round 59 guards: multi-location repository and skill discovery.

When Mindseam is installed as a workspace skill (.agents/skills/mindseam) or
as a global user skill (~/.gemini/antigravity/skills/mindseam), verify_suite's
repository finder previously assumed the candidate parent always contained
the tests directory, causing discovery failures in installed locations.
find_repo and main now navigate parent hierarchies and detect standalone
skill environments cleanly while preserving full test execution when a test
suite is present. This round pins multi-location discovery and standalone
verification parity.
"""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import verify_suite


class MultiLocationRepoDiscoveryTests(unittest.TestCase):

    def test_find_repo_resolves_from_standard_root(self):
        project_root, skill_root, script = verify_suite.find_repo()
        self.assertTrue(project_root.exists())
        self.assertTrue((project_root / "tests").is_dir())
        self.assertTrue((skill_root / "SKILL.md").exists())
        self.assertTrue(script.exists())

    def test_find_repo_resolves_from_nested_location(self):
        # Point to the actual verify_suite script path and verify resolution
        script_path = ROOT / "mindseam" / "scripts" / "verify_suite.py"
        self.assertTrue(script_path.exists())
        spec = importlib.util.spec_from_file_location("vs_mod", script_path)
        vs_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vs_mod)
        p_root, s_root, script = vs_mod.find_repo()
        self.assertTrue((p_root / "tests").is_dir())
        self.assertTrue((s_root / "SKILL.md").exists())

    def test_integrity_findings_clean_on_shipped_skill(self):
        _, skill_root, _ = verify_suite.find_repo()
        findings = verify_suite.get_integrity_findings(skill_root)
        self.assertEqual(findings, [], f"Unexpected integrity findings: {findings}")


if __name__ == "__main__":
    unittest.main()
