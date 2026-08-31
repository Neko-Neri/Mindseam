import sys, pathlib, unittest
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent / "mindseam" / "scripts"))
import mindseam


def _step(i, nxt="alpha:step", marker="OPEN", verified=0, confidence="thin",
          risk="low", error="", verifier="", extra_steps=0, outcome=""):
    return dict(t=1000 + i, next=nxt, marker=marker, verified=verified,
                confidence=confidence, risk=risk, error=error,
                verifier=verifier, extra_steps=extra_steps,
                outcome=outcome)


def _steps(count, **kw):
    return [_step(i, **kw) for i in range(count)]


class R38StepEconomyTests(unittest.TestCase):

    def test_empty_history(self):
        self.assertEqual(mindseam.step_economy([]), 100)

    def test_short_history(self):
        h = _steps(mindseam.STALL_RUN)
        self.assertEqual(mindseam.step_economy(h), 100)

    def test_below_sla(self):
        h = _steps(mindseam.STALL_RUN + 1, extra_steps=mindseam.STALL_RUN + 1)
        self.assertEqual(mindseam.step_economy(h), 100)

    def test_over_sla_reduces_score(self):
        h = _steps(mindseam.STALL_RUN + 1, extra_steps=mindseam.STALL_RUN + 3)
        score = mindseam.step_economy(h)
        self.assertLess(score, 100)
        self.assertGreaterEqual(score, 0)

    def test_all_over_sla(self):
        h = _steps(mindseam.STALL_RUN + 1, extra_steps=999)
        self.assertEqual(mindseam.step_economy(h), 0)

    def test_partial_over_sla(self):
        h = []
        for i in range(mindseam.STALL_RUN + 1):
            h.append(_step(i, extra_steps=999 if i % 2 == 0 else 0))
        score = mindseam.step_economy(h)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_custom_sla(self):
        h = _steps(mindseam.STALL_RUN + 1, extra_steps=5)
        score_custom = mindseam.step_economy(h, step_sla=3)
        score_default = mindseam.step_economy(h)
        self.assertLess(score_custom, score_default)

    def test_window_cutoff(self):
        h = _steps(20, extra_steps=0)
        h[-1] = _step(19, extra_steps=999)
        score = mindseam.step_economy(h)
        self.assertLess(score, 100)


class R38BookThreadAlignmentTests(unittest.TestCase):

    def test_no_book(self):
        h = _step(0, nxt="alpha:x")
        self.assertEqual(mindseam.book_thread_alignment(h, None), 100)

    def test_empty_open(self):
        book = {"Open": []}
        h = _step(0, nxt="alpha:x")
        self.assertEqual(mindseam.book_thread_alignment(h, book), 100)

    def test_empty_open_row(self):
        book = {"Open": [""]}
        h = _step(0, nxt="alpha:x")
        self.assertEqual(mindseam.book_thread_alignment(h, book), 100)

    def test_domain_match(self):
        book = {"Open": ["alpha:task1", "beta:task2"]}
        h = _step(0, nxt="beta:next_item")
        self.assertEqual(mindseam.book_thread_alignment(h, book), 100)

    def test_domain_mismatch(self):
        book = {"Open": ["alpha:x"]}
        h = _step(0, nxt="beta:y")
        self.assertEqual(mindseam.book_thread_alignment(h, book), 0)

    def test_prefix_only_matters(self):
        book = {"Open": ["alpha:very long task name"]}
        h = _step(0, nxt="alpha:short")
        self.assertEqual(mindseam.book_thread_alignment(h, book), 100)

    def test_case_insensitive(self):
        book = {"Open": ["ALPHA:x"]}
        h = _step(0, nxt="alpha:y")
        self.assertEqual(mindseam.book_thread_alignment(h, book), 100)

    def test_whitespace_ignored(self):
        book = {"Open": ["  alpha:task  "]}
        h = _step(0, nxt=" alpha : next ")
        self.assertEqual(mindseam.book_thread_alignment(h, book), 100)

    def test_last_entry_only(self):
        book = {"Open": ["alpha:x", "beta:y"]}
        h = [_step(i, nxt="alpha:ignored") for i in range(3)]
        h[-1] = _step(2, nxt="beta:matches")
        self.assertEqual(mindseam.book_thread_alignment(h, book), 100)

    def test_empty_next_returns_0(self):
        book = {"Open": ["alpha:x"]}
        h = _step(0, nxt="")
        self.assertEqual(mindseam.book_thread_alignment(h, book), 0)


class R38VerifierIndependenceTests(unittest.TestCase):

    def test_empty_history(self):
        self.assertEqual(mindseam.verifier_independence([]), 100)

    def test_short_history(self):
        h = _steps(mindseam.STALL_RUN - 1, verifier="v1")
        self.assertGreaterEqual(mindseam.verifier_independence(h), 80)

    def test_no_verifier_fields(self):
        h = _steps(mindseam.STALL_RUN)
        self.assertGreaterEqual(mindseam.verifier_independence(h), 80)

    def test_all_different(self):
        vs = ["v1", "v2", "v3", "v4", "v5"]
        h = [_step(i, verifier=vs[i % len(vs)]) for i in range(mindseam.STALL_RUN)]
        self.assertGreaterEqual(mindseam.verifier_independence(h), 80)

    def test_two_of_three(self):
        h = _steps(mindseam.STALL_RUN, verifier="v1")
        h[-1] = _step(mindseam.STALL_RUN - 1, verifier="v2")
        score = mindseam.verifier_independence(h)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_uniform_verifier(self):
        h = _steps(mindseam.STALL_RUN + 5, verifier="v1")
        score = mindseam.verifier_independence(h)
        self.assertLessEqual(score, 33)
        self.assertGreaterEqual(score, 0)

    def test_window_cutoff(self):
        vs = ["v1", "v2"]
        h = [_step(i, verifier=vs[i % 2]) for i in range(20)]
        score = mindseam.verifier_independence(h)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_missing_verifier_ignored(self):
        h = [_step(0, verifier="v1"), _step(1, verifier=""), _step(2, verifier="v1")]
        score = mindseam.verifier_independence(h)
        self.assertLess(score, 100)


class R38OutputStubRatioTests(unittest.TestCase):

    def test_empty_history(self):
        self.assertEqual(mindseam.output_stub_ratio([]), 100)

    def test_short_history(self):
        h = _steps(mindseam.STALL_RUN - 1)
        self.assertEqual(mindseam.output_stub_ratio(h), 100)

    def test_all_substantive(self):
        h = _steps(mindseam.STALL_RUN, nxt="alpha:implement_feature")
        self.assertEqual(mindseam.output_stub_ratio(h), 100)

    def test_all_empty(self):
        h = _steps(mindseam.STALL_RUN, nxt="")
        self.assertEqual(mindseam.output_stub_ratio(h), 0)

    def test_all_generic(self):
        generics = ["todo: fix", "next step", "continue work"]
        h = [_steps(1, nxt=g)[0] for g in generics]
        self.assertEqual(mindseam.output_stub_ratio(h), 0)

    def test_length_3_stub(self):
        h = _steps(mindseam.STALL_RUN, nxt="abc")
        self.assertEqual(mindseam.output_stub_ratio(h), 0)

    def test_length_4_passes(self):
        h = _steps(mindseam.STALL_RUN, nxt="abcd")
        self.assertEqual(mindseam.output_stub_ratio(h), 100)

    def test_whitespace_only(self):
        h = _steps(mindseam.STALL_RUN, nxt="   ")
        self.assertEqual(mindseam.output_stub_ratio(h), 0)

    def test_mixed(self):
        h = [_steps(1, nxt="")[0], _steps(1, nxt="alpha:real_task")[0], _steps(1, nxt="todo:x")[0]]
        score = mindseam.output_stub_ratio(h)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_window_cutoff(self):
        h = _steps(20, nxt="alpha:real_task")
        h[-1] = _step(19, nxt="todo:x")
        h[-2] = _step(18, nxt="")
        score = mindseam.output_stub_ratio(h)
        self.assertLess(score, 100)


class R38ObservationsWiringTests(unittest.TestCase):

    def test_step_economy_fact(self):
        h = _steps(mindseam.STALL_RUN + 1, extra_steps=999)
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("step economy poor" in f.lower() for f in facts))

    def test_book_thread_alignment_fact(self):
        book = {'Open': ['alpha:x']}
        h = _steps(mindseam.STALL_RUN, nxt='beta:y')
        score = mindseam.book_thread_alignment(h, book)
        self.assertEqual(score, 0)

    def test_verifier_independence_fact(self):
        h = _steps(mindseam.STALL_RUN + 5, verifier="v1")
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("verifier concentration" in f.lower() for f in facts))

    def test_output_stub_ratio_fact(self):
        h = _steps(mindseam.STALL_RUN, nxt="")
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("output stub score is low" in f.lower() for f in facts))

    def test_no_false_positives_no_book(self):
        h = _steps(mindseam.STALL_RUN + 1, nxt="alpha:good", verifier="v1")
        facts = mindseam.observations(h, book=None)
        self.assertFalse(any("book thread alignment failed" in f.lower() for f in facts))


class R38ShsWiringTests(unittest.TestCase):

    def test_step_economy_penalty(self):
        h = _steps(mindseam.STALL_RUN + 1, extra_steps=999)
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertLessEqual(score, 95)
        self.assertTrue(any("step economy" in r for r in reasons))

    def test_step_economy_bonus(self):
        # Evidenced, distinct work: named verifiers with outcomes so the
        # lean-refinement bonus rests on real measurement (round-12
        # sentinel gates removed the phantom padding).
        h = [_step(i, nxt="alpha:step%d" % i,
                   extra_steps=0, confidence="strong",
                   marker=["STEP", "OPEN", "DONE", "STEP"][i],
                   verified=1 if i % 2 == 0 else 0,
                   verifier=("v1" if i % 2 == 0 else ""),
                   outcome="ok" if i % 2 == 0 else "")
             for i in range(mindseam.STALL_RUN + 1)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertGreaterEqual(score, 60)
        self.assertTrue(any("lean refinement" in r for r in reasons))

    def test_verifier_independence_penalty(self):
        h = _steps(mindseam.STALL_RUN + 5, verifier="v1")
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("verifier concentration" in r for r in reasons))

    def test_verifier_independence_bonus(self):
        vs = ["v1", "v2", "v3"]
        h = [_step(i, verifier=vs[i % len(vs)]) for i in range(mindseam.STALL_RUN)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("verifier diversity" in r for r in reasons))

    def test_thread_abandonment_penalty(self):
        h = []
        for i in range(mindseam.STALL_RUN + 1):
            err = 1 if i < 3 else 0
            h.append(_step(i, nxt="alpha:same", error="err" if err else "", extra_steps=2 if err else 0))
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("thread abandonment" in r for r in reasons))

    def test_output_stub_penalty(self):
        h = _steps(mindseam.STALL_RUN, nxt="")
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any("output stub ratio" in r for r in reasons))


if __name__ == "__main__":
    unittest.main()
