# -*- coding: utf-8 -*-
"""Round 74 guards: verifier test harness strict integer invariants and public API surface.

verify_suite.py checks whether STALL_RUN and HISTORY_MAX are valid positive integers.
Because bool is a subclass of int in Python, isinstance(True, int) evaluates to True,
which previously could permit boolean values to slip past smoke test validation.
check_interface has been hardened to explicitly disallow boolean types. This round
pins strict non-boolean integer validation for controller constants and complete
public function interface checking in the test harness.
"""

import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import verify_suite


class VerifierHarnessStrictIntegerTests(unittest.TestCase):

    def test_verify_suite_disallows_boolean_constants(self):
        # Create a dummy module where STALL_RUN is True instead of an integer
        fake_mod = types.ModuleType("fake_mindseam")
        fake_mod.STALL_RUN = True
        fake_mod.HISTORY_MAX = 50

        # Run check_interface and capture output
        old_pass, old_fail = verify_suite.PASS, verify_suite.FAIL
        verify_suite.PASS = 0
        verify_suite.FAIL = 0
        buf = io.StringIO()
        with redirect_stdout(buf):
            verify_suite.check_interface(fake_mod)
        output = buf.getvalue()
        verify_suite.PASS, verify_suite.FAIL = old_pass, old_fail

        self.assertIn("FAIL STALL_RUN is int > 0", output)


if __name__ == "__main__":
    unittest.main()
