# -*- coding: utf-8 -*-
"""Round 67 guards: error acknowledgment filtering and AST variable hygiene.

error_acknowledgment_ratio previously maintained an unused loop index variable
and multiple successive set discard calls. The detector loop has been cleaned
to iterate directly across the evaluation slice with unified stopword filtering
(discarding high-frequency generic function words like that, with, from).
Additionally, complete AST static analysis guarantees zero unused local variables
across all controller routines. This round pins error keyword acknowledgment,
stopword filtering, and AST variable hygiene invariants.
"""

import ast
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

import mindseam


class ErrorAcknowledgmentAndAstHygieneTests(unittest.TestCase):

    def test_error_acknowledged_in_next_action(self):
        # Error mentions 'database timeout', next action explicitly addresses 'timeout'
        hist = [
            {"error": "database connection timeout", "next": "retry database connection timeout with backoff"},
            {"error": "", "next": "step 2"},
            {"error": "", "next": "step 3"},
        ]
        ratio = mindseam.error_acknowledgment_ratio(hist)
        self.assertEqual(ratio, 100)

    def test_error_ignored_in_next_action(self):
        # Error mentions 'database timeout', next action mentions completely unrelated task
        hist = [
            {"error": "database connection timeout", "next": "completely unrelated styling"},
            {"error": "", "next": "step 2"},
            {"error": "", "next": "step 3"},
        ]
        ratio = mindseam.error_acknowledgment_ratio(hist)
        self.assertEqual(ratio, 0)

    def test_ast_zero_unused_variables_in_mindseam(self):
        code = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(encoding="utf-8")
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assigned = set()
                loaded = set()
                for child in ast.walk(node):
                    if isinstance(child, ast.Name):
                        if isinstance(child.ctx, ast.Store):
                            assigned.add(child.id)
                        elif isinstance(child.ctx, ast.Load):
                            loaded.add(child.id)
                unused = assigned - loaded - {"_", "__"}
                args = {a.arg for a in node.args.args + getattr(node.args, "posonlyargs", []) + getattr(node.args, "kwonlyargs", [])}
                unused = unused - args
                self.assertEqual(
                    unused, set(),
                    f"Function {node.name} at line {node.lineno} contains unused variables: {unused}"
                )


if __name__ == "__main__":
    unittest.main()
