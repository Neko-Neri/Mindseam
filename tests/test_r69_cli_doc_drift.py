# -*- coding: utf-8 -*-
"""Round 29 guards: every CLI flag is documented where users look.

The mechanism layer (round 4) added --marker / --confidence / --verifier
and the event flags --error / --outcome / --extra-steps to `note`, and
ship gained --strict. The README documented them; SKILL.md — the only
file a host actually loads — still listed the original six commands, so
a user following the entry file could never feed the detectors that
consume those fields. The guard parses the argparse definitions out of
mindseam.py and requires every flag to appear in both SKILL.md and
README.md, so the three artefacts cannot drift apart again.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam  # noqa: F401  (ensures the module parses)

SOURCE = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(encoding="utf-8")
SKILL = (ROOT / "mindseam" / "SKILL.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
README_ZH = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

FLAGS = sorted(set(re.findall(r'add_argument\("(--[a-z-]+)"', SOURCE)))


class CliDocDriftTests(unittest.TestCase):

    def test_flags_were_found(self):
        self.assertGreater(len(FLAGS), 10, FLAGS)

    def test_skill_documents_every_flag(self):
        missing = [f for f in FLAGS if f not in SKILL]
        self.assertEqual(
            missing, [],
            "SKILL.md does not document: %s" % missing)

    def test_readme_documents_every_flag(self):
        missing = [f for f in FLAGS if f not in README]
        self.assertEqual(
            missing, [],
            "README.md does not document: %s" % missing)

    def test_chinese_readme_documents_every_flag(self):
        missing = [f for f in FLAGS if f not in README_ZH]
        self.assertEqual(
            missing, [],
            "README.zh-CN.md does not document: %s" % missing)

    def test_documented_commands_exist_in_the_parser(self):
        # The reverse direction, scoped to the controller command block:
        # nothing it names may be a flag the parser no longer accepts.
        block = SOURCE
        in_block = False
        documented = set()
        for line in SKILL.splitlines():
            if "mindseam.py " in line and "--" in line:
                for flag in re.findall(r"(?<!-) --[a-z][a-z-]+", line + " "):
                    documented.add(flag.strip())
        for flag in sorted(documented):
            self.assertIn(
                'add_argument("%s"' % flag, block,
                "SKILL.md documents a flag the parser does not define: %s"
                % flag)


if __name__ == "__main__":
    unittest.main()
