import sys, pathlib, unittest
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent / "mindseam" / "scripts"))
import mindseam


def _step(i, nxt="alpha:step", marker="OPEN", verified=0, confidence="thin",
          risk="low", error="", verifier="", extra_steps=0):
    return dict(t=1000 + i, next=nxt, marker=marker, verified=verified,
                confidence=confidence, risk=risk, error=error,
                verifier=verifier, extra_steps=extra_steps)


def _steps(count, **kw):
    return [_step(i, **kw) for i in range(count)]


class R39NextActionRedundancyTests(unittest.TestCase):

    def test_empty_history(self):
        self.assertEqual(mindseam.next_action_redundancy([]), 100)

    def test_single_entry(self):
        self.assertEqual(mindseam.next_action_redundancy([_step(0)]), 100)

    def test_window_cutoff(self):
        self.assertEqual(mindseam.next_action_redundancy(_steps(mindseam.STALL_RUN - 1)), 100)

    def test_penalty_two_repeat_pairs(self):
        h = [_step(0, nxt="a:x"), _step(1, nxt="a:x"), _step(2, nxt="b:y")]
        self.assertEqual(mindseam.next_action_redundancy(h), 50)

    def test_full_redundancy(self):
        h = _steps(mindseam.STALL_RUN, nxt="same:action")
        self.assertEqual(mindseam.next_action_redundancy(h), 0)

    def test_severity_half_redundant(self):
        h = [_step(0, nxt="a:x"), _step(1, nxt="a:x"),
             _step(2, nxt="b:y")]
        score = mindseam.next_action_redundancy(h)
        self.assertGreaterEqual(score, 50)
        self.assertLessEqual(score, 70)

    def test_severity_one_repeat_pair(self):
        h = [_step(0, nxt="a:x"), _step(1, nxt="a:x"),
             _step(2, nxt="b:y"), _step(3, nxt="c:z"), _step(4, nxt="d:w")]
        score = mindseam.next_action_redundancy(h)
        self.assertGreaterEqual(score, 75)

    def test_severity_no_repeats(self):
        h = [_step(0, nxt="a:x"), _step(1, nxt="b:y"), _step(2, nxt="c:z")]
        self.assertGreaterEqual(mindseam.next_action_redundancy(h), 80)
        self.assertLessEqual(mindseam.next_action_redundancy(h), 100)

    def test_bonus_all_different(self):
        h = [_step(i, nxt="a%d:step" % i) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.next_action_redundancy(h), 100)

    def test_reason_substring(self):
        h = _steps(mindseam.STALL_RUN, nxt="same:action")
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("redundancy" in f.lower() or "repeats" in f.lower() for f in facts))

    def test_no_false_positive_in_long_run(self):
        h = [_step(i, nxt="alpha%d:step" % i) for i in range(mindseam.STALL_RUN)]
        facts = mindseam.observations(h, book=None)
        self.assertFalse(any("redundancy" in f for f in facts))

    def test_long_history_window_clipping(self):
        h = [_step(i, nxt="same:action") for i in range(mindseam.STALL_RUN * 2)]
        self.assertEqual(mindseam.next_action_redundancy(h), 0)

    def test_mixed_case(self):
        h = [_step(0, nxt="Alpha:Step"), _step(1, nxt="alpha:step"),
             _step(2, nxt="alpha:step")]
        score = mindseam.next_action_redundancy(h)
        self.assertLess(score, 30)

    def test_empty_next_action(self):
        h = [_step(0, nxt=""), _step(1, nxt=""), _step(2, nxt="")]
        score = mindseam.next_action_redundancy(h)
        self.assertEqual(score, 100)

    def test_single_repeat_at_window_edge(self):
        h = [_step(0, nxt="a:x"), _step(1, nxt="b:y"), _step(2, nxt="b:y")]
        score = mindseam.next_action_redundancy(h)
        self.assertLessEqual(score, 70)

    def test_shs_penalty(self):
        h = _steps(mindseam.STALL_RUN + 1, nxt="same:action")
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("action redundancy" in r for r in reasons))

    def test_shs_bonus(self):
        h = [_step(i, nxt="alpha%d:step" % i) for i in range(mindseam.STALL_RUN)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("action diversity" in r for r in reasons))

    def test_observation_fact_present(self):
        h = _steps(mindseam.STALL_RUN, nxt="same:action")
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("redundancy" in f for f in facts))

    def test_observations_fact_count(self):
        h = [_step(0, nxt="same:action")] * mindseam.STALL_RUN
        facts = mindseam.observations(h, book=None)
        target_facts = [f for f in facts if "redundancy" in f or "repeats" in f]
        self.assertGreater(len(target_facts), 0)


class R39ErrorConvergenceTests(unittest.TestCase):

    def test_no_errors(self):
        self.assertEqual(mindseam.error_convergence(_steps(mindseam.STALL_RUN)), 100)

    def test_single_error(self):
        h = [_step(0, error="x:e"), _step(1, error="y:e"), _step(2, error="z:e")]
        self.assertEqual(mindseam.error_convergence(h), 100)

    def test_window_cutoff(self):
        h = _steps(mindseam.STALL_RUN - 1, error="x:e")
        self.assertEqual(mindseam.error_convergence(h), 100)

    def test_same_domain(self):
        h = _steps(mindseam.STALL_RUN, error="type1:err")
        score = mindseam.error_convergence(h)
        self.assertEqual(score, 0)

    def test_mixed_domains(self):
        h = [_step(i, error=["t1:err", "t2:err", "t3:err"][i % mindseam.STALL_RUN]) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.error_convergence(h), 100)

    def test_severity_two_domains(self):
        h = [_step(i, error="alpha:err" if i < 4 else "beta:err") for i in range(6)]
        score = mindseam.error_convergence(h)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_severity_half_same(self):
        h = [_step(i, error=["alpha:err", "beta:err"][i % 2]) for i in range(mindseam.STALL_RUN)]
        score = mindseam.error_convergence(h)
        self.assertGreaterEqual(score, 30)

    def test_bonus_all_different(self):
        h = [_step(i, error="e%d:err" % i) for i in range(mindseam.STALL_RUN)]
        self.assertGreaterEqual(mindseam.error_convergence(h), 80)

    def test_empty_error_field(self):
        h = [_step(0, error=""), _step(1, error=""), _step(2, error="x:e")]
        score = mindseam.error_convergence(h)
        self.assertGreater(score, 0)

    def test_domain_extraction(self):
        h = [_step(0, error="network:timeout"), _step(1, error="network:dns"),
             _step(2, error="storage:full")]
        score = mindseam.error_convergence(h)
        self.assertGreaterEqual(score, 50)

    def test_reason_substring_same(self):
        h = _steps(mindseam.STALL_RUN, error="type1:err")
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("error convergence" in f.lower() or "cluster" in f.lower() for f in facts))

    def test_observations_no_false_positive(self):
        h = _steps(mindseam.STALL_RUN)
        facts = mindseam.observations(h, book=None)
        self.assertFalse(any("error convergence" in f.lower() for f in facts))

    def test_longer_window(self):
        h = [_step(i, error="alpha:err") for i in range(mindseam.STALL_RUN * 2)]
        score = mindseam.error_convergence(h)
        self.assertEqual(score, 0)
        self.assertLess(score, 100)

    def test_case_insensitive(self):
        h = _steps(mindseam.STALL_RUN, error="TYPE1:err")
        score = mindseam.error_convergence(h)
        self.assertEqual(score, 0)

    def test_shs_penalty(self):
        h = _steps(mindseam.STALL_RUN + 1, error="same:error")
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("error clustering" in r for r in reasons))

    def test_trailing_colon_stripped(self):
        h = _steps(mindseam.STALL_RUN, error="alpha:")
        score = mindseam.error_convergence(h)
        self.assertEqual(score, 0)

    def test_observation_fact_count(self):
        h = [_step(0, error="same:err"), _step(1, error="same:err"), _step(2, error="same:err")]
        facts = mindseam.observations(h, book=None)
        convergence_facts = [f for f in facts if "error convergence" in f.lower() or "cluster" in f.lower()]
        self.assertGreaterEqual(len(convergence_facts), 1)

    def test_score_capped(self):
        h = _steps(mindseam.STALL_RUN, error="type1:err")
        score = mindseam.error_convergence(h)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_single_window(self):
        h = _steps(mindseam.STALL_RUN - 1, error="alpha:err")
        self.assertEqual(mindseam.error_convergence(h), 100)


class R39MarkerProgressionTests(unittest.TestCase):

    def test_no_markers(self):
        self.assertEqual(mindseam.marker_progression([_step(0), _step(1)]), 100)

    def test_single_marker(self):
        self.assertEqual(mindseam.marker_progression([_step(0, marker="OPEN")]), 100)

    def test_window_cutoff(self):
        self.assertEqual(mindseam.marker_progression(_steps(mindseam.STALL_RUN - 1, marker="OPEN")), 100)

    def test_repeated_open(self):
        h = _steps(mindseam.STALL_RUN, marker="OPEN")
        self.assertEqual(mindseam.marker_progression(h), 0)

    def test_progression_open_to_done(self):
        h = [_step(0, marker="OPEN"), _step(1, marker="STEP"), _step(2, marker="DONE")]
        self.assertGreaterEqual(mindseam.marker_progression(h), 70)

    def test_severity_one_terminal(self):
        h = [_step(0, marker="OPEN"), _step(1, marker="STEP"), _step(2, marker="DONE"),
             _step(3, marker="OPEN"), _step(4, marker="STEP")]
        score = mindseam.marker_progression(h)
        self.assertGreater(score, 30)
        self.assertLess(score, 80)

    def test_severity_two_terminal(self):
        h = [_step(0, marker="OPEN"), _step(1, marker="DONE"), _step(2, marker="OPEN"),
             _step(3, marker="DONE"), _step(4, marker="OPEN")]
        score = mindseam.marker_progression(h)
        self.assertGreater(score, 50)

    def test_oscillating_markers(self):
        h = [_step(0, marker="OPEN"), _step(1, marker="DONE"), _step(2, marker="OPEN"),
             _step(3, marker="STEP"), _step(4, marker="DONE"), _step(5, marker="OPEN")]
        score = mindseam.marker_progression(h)
        self.assertGreaterEqual(score, 50)

    def test_bonus_linear_progression(self):
        h = [_step(i, marker=["OPEN", "STEP", "DONE"][i % 3]) for i in range(mindseam.STALL_RUN)]
        self.assertGreaterEqual(mindseam.marker_progression(h), 60)

    def test_all_terminal(self):
        h = _steps(mindseam.STALL_RUN, marker="DONE")
        self.assertEqual(mindseam.marker_progression(h), 0)

    def test_reason_substring(self):
        h = _steps(mindseam.STALL_RUN, marker="OPEN")
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("marker" in f.lower() for f in facts))

    def test_observations_no_false_positive(self):
        h = [_step(i, marker=["OPEN", "STEP", "DONE"][i % mindseam.STALL_RUN]) for i in range(mindseam.STALL_RUN * 2)]
        facts = mindseam.observations(h, book=None)
        self.assertFalse(any("marker progression" in f.lower() for f in facts))

    def test_case_insensitive(self):
        h = [_step(0, marker="open"), _step(1, marker="done")]
        score = mindseam.marker_progression(h)
        self.assertGreater(score, 30)

    def test_long_history(self):
        h = [_step(i, marker="OPEN") for i in range(mindseam.STALL_RUN * 2)]
        self.assertEqual(mindseam.marker_progression(h), 0)

    def test_mixed_terminal_nonterminal(self):
        h = [_step(0, marker="OPEN"), _step(1, marker="DONE"), _step(2, marker="STEP")]
        score = mindseam.marker_progression(h)
        self.assertGreaterEqual(score, 50)

    def test_shs_penalty(self):
        h = _steps(mindseam.STALL_RUN, marker="OPEN")
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("marker stall" in r for r in reasons))

    def test_shs_bonus(self):
        h = [_step(i, marker=["OPEN", "STEP", "DONE"][i % 3]) for i in range(mindseam.STALL_RUN)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("marker progress" in r for r in reasons))


class R39VerificationFreshnessTests(unittest.TestCase):

    def test_all_verified(self):
        h = [_step(i, verifier="v1", verified=1) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.verification_freshness(h), 100)

    def test_no_verification(self):
        h = _steps(mindseam.STALL_RUN)
        self.assertEqual(mindseam.verification_freshness(h), 0)

    def test_half_verified(self):
        alternating = [_step(i, verifier="v1") if i % 2 == 0 else _step(i) for i in range(mindseam.STALL_RUN)]
        score = mindseam.verification_freshness(alternating)
        self.assertGreaterEqual(score, 60)
        self.assertLessEqual(score, 80)

    def test_window_cutoff(self):
        h = _steps(mindseam.STALL_RUN - 1)
        self.assertEqual(mindseam.verification_freshness(h), 100)

    def test_recently_stale_long_history(self):
        h = [_step(i, verifier="v1") for i in range(mindseam.STALL_RUN + 5)]
        h[-1]["verifier"] = ""
        h[-1]["verified"] = 0
        score = mindseam.verification_freshness(h)
        self.assertGreaterEqual(score, 60)
        self.assertLessEqual(score, 85)

    def test_bonus_all_fresh(self):
        h = [_step(i, verifier="v1", verified=1) for i in range(mindseam.STALL_RUN)]
        self.assertGreaterEqual(mindseam.verification_freshness(h), 80)

    def test_mixed_with_and_without_verifier(self):
        h = [_step(i, verifier="v1") if i < 2 else _step(i) for i in range(mindseam.STALL_RUN)]
        score = mindseam.verification_freshness(h)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_empty_history(self):
        self.assertEqual(mindseam.verification_freshness([]), 100)

    def test_reason_substring(self):
        h = _steps(mindseam.STALL_RUN)
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("verification" in f.lower() for f in facts))

    def test_observations_no_false_positive(self):
        h = [_step(i, verifier="v1", verified=1) for i in range(mindseam.STALL_RUN)]
        facts = mindseam.observations(h, book=None)
        self.assertFalse(any("freshness" in f.lower() for f in facts))

    def test_score_capped(self):
        h = _steps(mindseam.STALL_RUN)
        score = mindseam.verification_freshness(h)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_single_stale(self):
        h = [_step(0, verifier="v1"), _step(1, verifier="v1"), _step(2, verifier="")]
        score = mindseam.verification_freshness(h)
        self.assertGreaterEqual(score, 60)
        self.assertLessEqual(score, 80)

    def test_long_history_fully_stale(self):
        h = [_step(i) for i in range(mindseam.STALL_RUN * 2)]
        self.assertEqual(mindseam.verification_freshness(h), 0)

    def test_shs_penalty(self):
        h = _steps(mindseam.STALL_RUN + 1)
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("stale verification" in r for r in reasons))

    def test_shs_bonus(self):
        h = [_step(i, verifier="v1", verified=1) for i in range(mindseam.STALL_RUN)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("fresh verification" in r for r in reasons))

    def test_case_insensitive(self):
        h = [_step(0, verifier="V1"), _step(1, verifier="")]
        score = mindseam.verification_freshness(h)
        self.assertGreaterEqual(score, 30)

    def test_all_verified_long(self):
        h = [_step(i, verifier="v%d" % (i % 3 + 1), verified=1) for i in range(mindseam.STALL_RUN * 2)]
        self.assertEqual(mindseam.verification_freshness(h), 100)

    def test_no_header(self):
        h = [_step(i, verifier="") for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.verification_freshness(h), 0)

    def test_alternating_verified(self):
        h = [_step(i, verifier="v1") if i % 2 == 0 else _step(i, verified=1) for i in range(mindseam.STALL_RUN)]
        score = mindseam.verification_freshness(h)
        self.assertEqual(score, 100)


if __name__ == "__main__":
    unittest.main()
