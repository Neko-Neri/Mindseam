# -*- coding: utf-8 -*-
"""Round 46 guards: the pipeline is Unicode-honest end to end.

The suite ships to CJK users (there is a Chinese README), and the CLAIM
and COVERAGE regexes carry Chinese branches. The guards run a full
note/seam/ship cycle on Chinese text: the ledger keeps the bytes, the
history keeps them, seam output does not crash or mojibake-escape them,
and a Chinese claim without Chinese coverage words is still caught by
ship's coverage gate.
"""

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

from _controller_helper import run_controller


class UnicodePipelineTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)

    def tearDown(self):
        os.chdir(self.cwd)

    def test_full_cycle_on_chinese_state(self):
        r = run_controller(self.ws, "note", "--goal", "交付中文审计",
                           "--next", "审计: 检查输出编码")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for step in range(3):
            run_controller(
                self.ws, "note", "--next", "审计: 第 %d 步" % step,
                "--marker", "OPEN", "--confidence", "strong",
                "--error", "数据库: 连接失败" if step == 1 else "")
        r = run_controller(self.ws, "seam")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("审计: 第 2 步", r.stdout)

    def test_chinese_claim_without_coverage_is_flagged(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "n")
        target = Path(self.ws) / "zh.md"
        target.write_text("结果已经验证，可以直接交付。\n", encoding="utf-8")
        r = run_controller(self.ws, "ship", str(target))
        self.assertIn("verification covered", r.stdout.lower())

    def test_chinese_claim_with_coverage_passes_the_gate(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "n")
        target = Path(self.ws) / "zh-ok.md"
        target.write_text(
            "结果已经验证，覆盖全部输入，包括边界与空集。\n", encoding="utf-8")
        r = run_controller(self.ws, "ship", str(target))
        self.assertNotIn("verification covered", r.stdout.lower())

    def test_utf8_bom_file_is_handled(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "n")
        target = Path(self.ws) / "bom.md"
        target.write_bytes(
            b"\xef\xbb\xbfclean line, nothing to flag\n")
        r = run_controller(self.ws, "ship", str(target))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("clean", r.stdout)


if __name__ == "__main__":
    unittest.main()
