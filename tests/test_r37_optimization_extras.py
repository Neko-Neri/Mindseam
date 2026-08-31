import sys, pathlib, unittest
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent / "mindseam" / "scripts"))
import mindseam


def _step(i, nxt="alpha:step", marker="OPEN", verified=0, confidence="thin",
          risk="low", error="", verifier="", extra_steps=0, eag=0.5,
          outcome="", reason=""):
    return dict(t=1000 + i, next=nxt, marker=marker, verified=verified,
                confidence=confidence, risk=risk, error=error,
                verifier=verifier, extra_steps=extra_steps, eag=eag,
                outcome=outcome, reason=reason)


class R37UnicodeEdgeCaseTests(unittest.TestCase):

    def test_chinese_error_description(self):
        h = [_step(i, error="网络连接超时:详细错误信息") for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.error_silence_ratio(h), 100)

    def test_unicode_specific_verifier(self):
        h = [_step(i, verifier="验证者%d_详细描述" % i) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.verifier_specificity(h), 100)

    def test_unicode_specific_next_action(self):
        h = [_step(i, nxt="实现JWT认证模块集成与测试方案") for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.next_action_specificity(h), 100)

    def test_empty_string_vs_none_in_error(self):
        h0 = [_step(0, error="")]
        h1 = [_step(0, error=None)]
        self.assertEqual(mindseam.error_silence_ratio(h0), 100)
        self.assertEqual(mindseam.error_silence_ratio(h1), 100)

    def test_unicode_with_emoji_in_next(self):
        h = [_step(i, nxt="fix critical bug in auth system") for i in range(mindseam.STALL_RUN)]
        score = mindseam.next_action_specificity(h)
        self.assertEqual(score, 100)

    def test_unicode_domain_prefix_in_next(self):
        h = [_step(i, nxt="alpha:实现认证功能详细方案") for i in range(mindseam.STALL_RUN)]
        score = mindseam.next_action_specificity(h)
        self.assertGreater(score, 0)


class R37BoundaryThresholdTests(unittest.TestCase):

    def test_error_silence_ratio_below_threshold(self):
        h = [_step(i, error="err%d" % i) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.error_silence_ratio(h), 0)

    def test_error_silence_ratio_at_threshold(self):
        h = [_step(i, error="errmsg_%d" % i) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.error_silence_ratio(h), 100)

    def test_verifier_specificity_below_threshold(self):
        h = [_step(i, verifier="vs%d" % i) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.verifier_specificity(h), 0)

    def test_verifier_specificity_at_threshold(self):
        h = [_step(i, verifier="v_spec_%d" % i) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.verifier_specificity(h), 100)

    def test_next_action_specificity_below_threshold(self):
        h = [_step(i, nxt="alpha:short") for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.next_action_specificity(h), 0)

    def test_next_action_specificity_at_threshold(self):
        h = [_step(i, nxt="alpha:longer1") for i in range(mindseam.STALL_RUN)]
        score = mindseam.next_action_specificity(h)
        self.assertGreaterEqual(score, 50)

    def test_output_stub_ratio_length_3_boundary(self):
        h = [_step(i, nxt="abc") for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.output_stub_ratio(h), 0)

    def test_output_stub_ratio_length_4_boundary(self):
        h = [_step(i, nxt="abcd") for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.output_stub_ratio(h), 100)

    def test_confidence_inflation_all_strong_unverified(self):
        h = [_step(i, confidence="strong", verified=0) for i in range(mindseam.STALL_RUN + 5)]
        self.assertEqual(mindseam.confidence_inflation(h), 0)

    def test_confidence_inflation_all_strong_verified(self):
        h = [_step(i, confidence="strong", verified=1) for i in range(mindseam.STALL_RUN + 5)]
        self.assertEqual(mindseam.confidence_inflation(h), 100)

    def test_confidence_inflation_no_strong(self):
        h = [_step(i, confidence="thin") for i in range(mindseam.STALL_RUN + 5)]
        self.assertEqual(mindseam.confidence_inflation(h), 100)


class R37CrossDetectorInteractionTests(unittest.TestCase):

    def test_heal_multiple_detectors_trigger(self):
        h = [_step(i, confidence="strong", error="x:e", nxt="todo:fix", verifier="v1") for i in range(mindseam.STALL_RUN)]
        changes = mindseam.heal_actions(h)
        self.assertGreaterEqual(len(changes), 2)

    def test_heal_session_health_subscores_not_all_100(self):
        h = []
        for i in range(mindseam.STALL_RUN):
            err = "net:timeout" if i == 0 else ""
            nxt = "alpha:task_%d_with_specific_details" % i
            v = "verifier_specific_method_%d" % i
            h.append(_step(i, error=err, nxt=nxt, verifier=v, verified=1, confidence="thin"))
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertGreater(score, 0)
        self.assertGreaterEqual(len(reasons), 1)

    def test_heal_actions_detects_generic_and_weak_next(self):
        h = [_step(i, confidence="thin", error="detailed_error_%d_info_msg" % i,
                   nxt="todo:x", verifier="v%d" % i, verified=1,
                   outcome="ok", reason="r", marker=["OPEN","STEP","DONE"][i%3])
             for i in range(mindseam.STALL_RUN)]
        changes = mindseam.heal_actions(h)
        ct = " ".join(changes).lower()
        self.assertIn("generic", ct)

    def test_session_health_score_multiple_penalties(self):
        h = [_step(i, confidence="strong", error="x:e", nxt="todo:x") for i in range(mindseam.STALL_RUN + 1)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertLess(score, 45)
        rtext = " ".join(reasons).lower()
        self.assertIn("confidence inflation", rtext)

    def test_output_stub_length3(self):
        h = [_step(i, nxt="abc") for i in range(mindseam.STALL_RUN)]
        stub = mindseam.output_stub_ratio(h)
        specificity = mindseam.next_action_specificity(h)
        self.assertEqual(stub, 0)
        self.assertEqual(specificity, 0)

    def test_error_acknowledgment_partial_coverage(self):
        h = [_step(0, error="port 8080 conflict", nxt="fix port 8080 conflict issue"),
             _step(1, error="db timeout error", nxt="retry db timeout"),
             _step(2, error="memory full disk", nxt="fix memory full disk problem")]
        score = mindseam.error_acknowledgment_ratio(h)
        self.assertEqual(score, 100)

    def test_verification_coverage_all_steps_with_evidence(self):
        h = [_step(0, verified=1, outcome="ok", reason="r", verifier="v", nxt="t0:a"),
             _step(1, verified=1, outcome="ok", reason="r", verifier="v", nxt="t1:a"),
             _step(2, verified=1, outcome="ok", reason="r", verifier="v", nxt="t2:a")]
        score = mindseam.verification_coverage_score(h)
        self.assertEqual(score, 100)

    def test_verification_coverage_one_evidence(self):
        h = [_step(i, verified=1, outcome="ok" if i == 0 else "",
                   reason="", verifier="", nxt="task%d:act" % i) for i in range(mindseam.STALL_RUN)]
        score = mindseam.verification_coverage_score(h)
        self.assertEqual(score, 0)

    def test_stub_specificity_vs_output_stub_ratio(self):
        h = [_step(i, nxt="todo: fix the thing") for i in range(mindseam.STALL_RUN)]
        stub = mindseam.output_stub_ratio(h)
        specificity = mindseam.next_action_specificity(h)
        self.assertEqual(stub, 0)
        self.assertGreaterEqual(specificity, 50)

    def test_error_recovery_with_domain_change(self):
        h = []
        for i in range(mindseam.STALL_RUN):
            err = "net:timeout" if i == 0 else ""
            nxt = "t%d:a" % i
            h.append(_step(i, error=err, nxt=nxt))
        score = mindseam.error_recovery_ratio(h)
        self.assertEqual(score, 100)


class R37StressTests(unittest.TestCase):

    def test_large_history_window_clipping(self):
        h = [_step(i, nxt="alpha:step") for i in range(100)]
        h[-1] = _step(99, nxt="todo:x")
        score = mindseam.output_stub_ratio(h)
        self.assertLess(score, 100)

    def test_large_history_all_good(self):
        h = [_step(i, nxt="implement feature %d with tests" % i) for i in range(100)]
        self.assertEqual(mindseam.output_stub_ratio(h), 100)

    def test_large_history_error_convergence(self):
        h = [_step(i, error="network:timeout") for i in range(100)]
        self.assertEqual(mindseam.error_convergence(h), 0)

    def test_large_history_all_different_errors(self):
        h = [_step(i, error="err_%d:details" % i) for i in range(100)]
        self.assertEqual(mindseam.error_convergence(h), 100)

    def test_next_action_redundancy_large_history(self):
        h = [_step(i, nxt="same:action") for i in range(100)]
        score = mindseam.next_action_redundancy(h)
        self.assertEqual(score, 0)

    def test_confidence_inflation_long_unverified_run(self):
        h = [_step(i, confidence="strong", verified=0) for i in range(50)]
        self.assertEqual(mindseam.confidence_inflation(h), 0)


class R37DeepOptimizationExtras(unittest.TestCase):

    def test_confidence_decay_rate_monotonic(self):
        # Genuine worsening (round 24 fixed the polarity: the old fixture
        # pinned an improving sequence — thin -> strong — at 1.0).
        values = ["strong", "thin", "shaky"]
        h = [_step(i, confidence=values[i]) for i in range(3)]
        decay = mindseam.confidence_decay_rate(h)
        self.assertEqual(decay, 1.0)

    def test_confidence_recovery_is_not_decay(self):
        values = ["shaky", "thin", "strong"]
        h = [_step(i, confidence=values[i]) for i in range(3)]
        self.assertEqual(mindseam.confidence_decay_rate(h), 0.0)

    def test_confidence_decay_rate_flat_returns_zero(self):
        h = [_step(i, confidence="thin") for i in range(5)]
        self.assertEqual(mindseam.confidence_decay_rate(h), 0.0)

    def test_confidence_decay_rate_short_history(self):
        self.assertEqual(mindseam.confidence_decay_rate([]), 0.0)
        self.assertEqual(mindseam.confidence_decay_rate([_step(0)]), 0.0)

    def test_stall_score_stalls_with_repeated_next(self):
        h = [_step(i, nxt="same:action", confidence="thin", error="",
                   verifier="v%d" % i, outcome="ok", reason="r")
             for i in range(mindseam.STALL_RUN)]
        self.assertGreaterEqual(mindseam.stall_score(h), 70)

    def test_stall_score_active_session_low(self):
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append(_step(i, nxt="next-action-%d:detail" % i, confidence="thin",
                          error="msg%d" % i, verifier="verifier%d" % i,
                          verified=1, outcome="ok", reason="r"))
        score = mindseam.stall_score(h)
        self.assertLess(score, 35)

    def test_compact_history_under_max_untouched(self):
        before = [_step(0)]
        after, changed, reasons = mindseam.compact_history(before)
        self.assertIs(after, before)
        self.assertFalse(changed)
        self.assertEqual(reasons, [])

    def test_knowledge_retention_empty_history(self):
        self.assertEqual(mindseam.knowledge_retention([]), 100)

    def test_knowledge_retention_high_with_minimal_eag(self):
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append(_step(i, eag=0.001, outcome="ok", reason="retention"))
        score = mindseam.knowledge_retention(h)
        self.assertGreater(score, 75)

    def test_risk_medium_triggers_heal_cascade(self):
        h = [_step(i, nxt="task-%d" % i, verifier="v%d" % i, outcome="",
                   reason="", error="err%d" % i, confidence="thin")
             for i in range(mindseam.STALL_RUN)]
        actions = mindseam.heal_actions(h)
        combined = " ".join(actions)
        self.assertIn("generic", combined)
        self.assertIn("vague", combined)

    def test_error_convergence_high_collapse_recovery_ratio_low(self):
        h = [_step(i, error="net:timeout", nxt="action%d" % i,
                   verifier="v%d" % i, outcome="ok", reason="r", verified=1)
             for i in range(mindseam.STALL_RUN)]
        conv = mindseam.error_convergence(h)
        rec = mindseam.error_recovery_ratio(h)
        self.assertEqual(conv, 0)
        self.assertEqual(rec, 0)

    def test_session_health_decay_redundancy_combined(self):
        h = [_step(i, nxt="same:action", confidence="thin",
                   error="detailed_error_%d" % i,
                   verifier="specific_verifier_%d" % i,
                   outcome="", reason="",
                   marker=["OPEN", "STEP", "DONE"][i % 3])
             for i in range(mindseam.STALL_RUN)]
        score, reasons = mindseam.session_health_score(h, book=None)
        # Round 26: unresolved trailing errors now score honestly lower
        # (never-recovered used to read the same as one-step recovery),
        # so this mixed-problem floor sits at 30. Round 46: the floor
        # drops to 29 because this never-verified history no longer
        # earns the "stable verification +5" bonus it never measured.
        self.assertGreaterEqual(score, 29)
        rtext = " ".join(reasons).lower()
        self.assertIn("next-action specificity", rtext)

    def test_outcome_completeness_direct(self):
        h = [_step(0, outcome="completed", reason="r")]
        self.assertEqual(mindseam.outcome_completeness(h), 100)

    def test_verifier_independence_direct(self):
        h = [_step(0, verifier="brute force: unique hand-check"),
             _step(1, verifier="smoke: unique regression suite"),
             _step(2, verifier="unit: unique edge case")]
        score = mindseam.verifier_independence(h)
        self.assertGreaterEqual(score, 99)

    def test_coverage_ratio_updated_check_detection(self):
        book = {"Core": ["c — fact"], "Verified": ["v — fact"], "Next": ["n: step"]}
        cr = mindseam.coverage_ratio(book)
        self.assertGreaterEqual(cr, 0.0)
        self.assertLessEqual(cr, 1.0)


if __name__ == "__main__":
    unittest.main()
