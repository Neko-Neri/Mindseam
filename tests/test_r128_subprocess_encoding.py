# -*- coding: utf-8 -*-
"""Round 56 guards: cross-platform subprocess decoding and regex compilation.

verify_suite ran subprocess.run with text=True and default system encoding,
which raised UnicodeDecodeError on Windows systems with non-UTF-8 code pages
such as CP936 or GBK when child output contained multibyte UTF-8 sequences.
Both subprocess invocations in check_main and run_unittest_discover now
enforce UTF-8 decoding with replace error handling. In addition, regexes
in next_open_number and mode_ship are precompiled at module level for
improved performance, and fact_age_seconds is hardened against missing
or falsy timestamp entries. This test pins these contracts across all
supported operating environments.
"""

import ast
import inspect
import json
import os
import re
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
import verify_suite
from _controller_helper import run_controller


class SubprocessEncodingAndOptimizationsTests(unittest.TestCase):

    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def test_verify_suite_subprocess_calls_specify_utf8_encoding(self):
        source = (ROOT / "mindseam" / "scripts" / "verify_suite.py").read_text(encoding="utf-8")
        self.assertIn('encoding="utf-8"', source)
        self.assertIn('errors="replace"', source)
        tree = ast.parse(source)
        subprocess_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "run":
                    if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                        subprocess_calls.append(node)
        self.assertGreaterEqual(len(subprocess_calls), 2)
        for call in subprocess_calls:
            kw_names = {kw.arg for kw in call.keywords}
            self.assertIn("encoding", kw_names, "subprocess.run call missing explicit encoding")
            self.assertIn("errors", kw_names, "subprocess.run call missing explicit error handling")

    def test_verify_suite_has_configure_streams(self):
        self.assertTrue(hasattr(verify_suite, "configure_streams"))
        self.assertTrue(callable(verify_suite.configure_streams))
        verify_suite.configure_streams()

    def test_precompiled_regex_constants_exist_and_match(self):
        self.assertTrue(hasattr(mindseam, "OPEN_ID_RE"))
        self.assertTrue(hasattr(mindseam, "CLOSED_OPEN_ID_RE"))
        self.assertTrue(hasattr(mindseam, "REPETITION_CHAR_RUN"))

        self.assertTrue(mindseam.OPEN_ID_RE.match("?12 What is the goal?"))
        self.assertIsNone(mindseam.OPEN_ID_RE.match("Goal: text"))

        self.assertTrue(mindseam.CLOSED_OPEN_ID_RE.search("Done something — closes: ?5"))
        self.assertIsNone(mindseam.CLOSED_OPEN_ID_RE.search("Done something else"))

        self.assertTrue(mindseam.REPETITION_CHAR_RUN.search("warning" + "." * 25))
        self.assertIsNone(mindseam.REPETITION_CHAR_RUN.search("normal sentence... with ellipsis"))

    def test_next_open_number_scans_and_retires_closed_ids(self):
        book = {
            "Open": ["?1 First question", "?3 Third question"],
            "Verified": ["Solved item — closes: ?2", "Other verified item"],
        }
        self.assertEqual(mindseam.next_open_number(book), 4)
        self.assertEqual(mindseam.next_open_number({}), 1)

    def test_fact_age_seconds_hardened_against_missing_or_falsy_t(self):
        self.assertEqual(mindseam.fact_age_seconds([]), 0)
        hist = [{"next": "step 1", "t": None}, {"next": "step 2"}]
        age = mindseam.fact_age_seconds(hist)
        self.assertGreaterEqual(age, 0)

    def test_mode_ship_flags_repetition_character_runs(self):
        book = {"Goal": ["g"], "Core": [], "Verified": [], "Open": [], "Next": ["n"]}
        text = "This is a run: " + "-" * 25
        result = run_controller(self.ws, "ship", "-", stdin=text)
        self.assertIn("repetition loop: a character run of 20 or more", result.stdout)


if __name__ == "__main__":
    unittest.main()
