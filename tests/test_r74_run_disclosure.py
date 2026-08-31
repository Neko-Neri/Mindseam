# -*- coding: utf-8 -*-
"""Round 34/35 guards: an ignored parameter must say so, accurately.

Ten detectors accepted a ``run`` argument and then overwrote it
unconditionally with their own window - the latent defect family from
rounds 20 and 22 (latent only because no live caller passes run=).
Round 34 added the "currently ignored" disclosure to the ten that
lacked it. Round 35 caught that one disclosure named the wrong window
("full history" over a trailing-6 slice) and upgraded the guard: the
window a docstring names must match the slice the code actually takes.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam  # noqa: F401

SOURCE_PATH = ROOT / "mindseam" / "scripts" / "mindseam.py"


def functions_overwriting_run():
    """Names of functions whose run parameter is overridden unconditionally."""
    src = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    offenders = []
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        if not any(a.arg == "run" for a in fn.args.args):
            continue
        for node in fn.body:
            if (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "run"
                            for t in node.targets)):
                offenders.append(fn.name)
                break
    return offenders


class RunDisclosureTests(unittest.TestCase):

    def test_every_ignored_run_is_disclosed(self):
        src = SOURCE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for name in functions_overwriting_run():
            fn = next(n for n in tree.body
                      if isinstance(n, ast.FunctionDef) and n.name == name)
            doc = ast.get_docstring(fn) or ""
            self.assertIn(
                "currently ignored", doc,
                "%s overwrites its run parameter without disclosing it"
                % name)

    def test_the_family_is_not_empty(self):
        self.assertGreater(len(functions_overwriting_run()), 5)

    def test_disclosed_window_matches_the_actual_slice(self):
        src = SOURCE_PATH.read_text(encoding="utf-8")
        for name in functions_overwriting_run():
            body = re.search(
                r"\ndef " + name + r"\([^)]*\):(.*?)(?=\ndef |\nclass )",
                src, re.S)
            code = body.group(1)
            m = re.search(r"run = hist\[-\(([^)]+)\):", code)
            if not m:
                continue
            expr = m.group(1).replace(" ", "")
            docstring = re.search(
                r"def " + name + r"\([^)]*\):\n(    \x22\x22\x22.*?\x22\x22\x22)",
                src, re.S)
            doc_text = docstring.group(1)
            want = {
                "STALL_RUN*2": "STALL_RUN * 2",
                "STALL_RUN+1": "STALL_RUN + 1",
            }.get(expr, expr)
            self.assertIn(
                want, doc_text,
                "%s slices hist[-(%s):] but its docstring does not name "
                "that window" % (name, expr))


if __name__ == "__main__":
    unittest.main()
