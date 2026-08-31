# -*- coding: utf-8 -*-
"""Round 38 guards: the factory check covers the real public surface.

verify_suite's interface list dated from the first packaging (23
functions) while the mechanism rounds added the fact layer, the risk
assessor, the grade band and the remediation map to the controller's
public surface. The list now names 31 functions, and this guard keeps
the list honest in both directions: every named function must exist,
and the newer load-bearing entry points must stay named.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam
import verify_suite

REQUIRED = (
    "session_health_score", "observations", "assess_risk", "grade",
    "heal_actions", "remediation_suggestions", "read_history",
    "append_history", "write_ledger", "read_ledger", "validate_book",
    "compound_pattern_facts", "contradiction_detection",
    "marker_progression", "loop_detection", "compact_history",
    "error_convergence", "verification_regression", "detect_stall",
    "session_fatigue", "detect_risk_escalation", "evidence_weight",
    "detect_recovery", "session_momentum", "confidence_decay_rate",
    "detect_volatility", "error_recovery_ratio", "outcome_reliability",
    "knowledge_retention", "next_action_specificity",
    "detect_ledger_stagnation",
)


class VerifierSurfaceTests(unittest.TestCase):

    def test_every_listed_function_exists(self):
        missing = [f for f in verify_suite.__dict__.get("_INTERFACE", ())
                   if not hasattr(mindseam, f)]
        # verify_suite has no module-level list constant; re-read its
        # check_interface source instead.
        import inspect
        source = inspect.getsource(verify_suite.check_interface)
        import re
        listed = re.findall(r'"([a-z_]+)"', source)
        missing = [f for f in listed if not hasattr(mindseam, f)]
        self.assertEqual(missing, [])

    def test_load_bearing_entry_points_are_listed(self):
        import inspect
        import re
        source = inspect.getsource(verify_suite.check_interface)
        listed = set(re.findall(r'"([a-z_]+)"', source))
        absent = [f for f in REQUIRED if f not in listed]
        self.assertEqual(absent, [],
                         "verify_suite no longer checks: %s" % absent)

    def test_interface_check_passes_against_the_module(self):
        import contextlib
        import io as _io
        out = _io.StringIO()
        failures = []
        real_check = verify_suite.check

        def spy(name, cond):
            if not cond:
                failures.append(name)
            return real_check(name, cond)

        verify_suite.check = spy
        try:
            with contextlib.redirect_stdout(out):
                verify_suite.check_interface(mindseam)
        finally:
            verify_suite.check = real_check
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
