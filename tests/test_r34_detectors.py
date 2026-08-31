# Copyright (c) 2025 0xnq (jieecode) <mail@0xnq.cc>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

import sys, pathlib, unittest
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent / "mindseam" / "scripts"))

import mindseam


class R34StorySwitchTests(unittest.TestCase):
    def test_empty_history(self):
        self.assertEqual(mindseam.story_switch_detection([], book=None), 100)

    def test_short_window_defaults_to_100(self):
        h = [dict(t=1000+i, next="alpha:x", marker="OPEN", verified=0, confidence="thin", risk="low") for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.story_switch_detection(h, book=None), 100)

    def test_stable_domain_returns_high(self):
        h = [dict(t=1000+i, next="alpha:x", marker="OPEN", verified=0, confidence="thin", risk="low") for i in range(mindseam.STALL_RUN * 2)]
        self.assertEqual(mindseam.story_switch_detection(h, book=None), 100)

    def test_domain_shift_penalizes(self):
        stable = [dict(t=1000+i, next="alpha:x", marker="OPEN", verified=0, confidence="thin", risk="low") for i in range(mindseam.STALL_RUN)]
        switch = [dict(t=1000+j, next="beta:y", marker="OPEN", verified=0, confidence="thin", risk="low") for j in range(mindseam.STALL_RUN)]
        h = stable + switch
        score = mindseam.story_switch_detection(h, book=None)
        self.assertLess(score, 100)
        self.assertGreaterEqual(score, 0)

    def test_book_fallback_for_empty_next(self):
        book = {"Next": "gamma:z"}
        h = [dict(t=1000+i, next="", marker="OPEN", verified=0, confidence="thin", risk="low") for i in range(mindseam.STALL_RUN * 2)]
        self.assertEqual(mindseam.story_switch_detection(h, book=book), 100)

    def test_session_health_score_wiring(self):
        h = [dict(t=1000+i, next="alpha:x", marker="DONE", verified=3, confidence="strong", risk="low") for i in range(mindseam.STALL_RUN * 2)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


class R34ComplexityEmissionTests(unittest.TestCase):
    def test_empty_history(self):
        self.assertEqual(mindseam.complexity_emission_ratio([]), 100)

    def test_short_window(self):
        h = [dict(t=1000+i, next="A", marker="DONE", verified=3, confidence="strong", risk="low") for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.complexity_emission_ratio(h), 100)

    def test_extra_without_delivered(self):
        h = [dict(t=1000+i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low", extra_steps=3) for i in range(mindseam.STALL_RUN + 5)]
        self.assertEqual(mindseam.complexity_emission_ratio(h), 0)

    def test_delivered_without_extra(self):
        h = [dict(t=1000+i, next="A", marker="DONE", verified=2, confidence="strong", risk="low", extra_steps=0) for i in range(mindseam.STALL_RUN + 5)]
        self.assertEqual(mindseam.complexity_emission_ratio(h), 100)

    def test_mixed_extra_and_delivered(self):
        h = [dict(t=1000+i, next="A", marker="DONE", verified=1, confidence="strong", risk="low", extra_steps=1) for i in range(mindseam.STALL_RUN + 5)]
        score = mindseam.complexity_emission_ratio(h)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_no_extra_no_delivered(self):
        h = [dict(t=1000+i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low", extra_steps=0) for i in range(mindseam.STALL_RUN + 5)]
        self.assertEqual(mindseam.complexity_emission_ratio(h), 100)

    def test_session_health_score_penalty(self):
        h = [dict(t=1000+i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low", extra_steps=2) for i in range(mindseam.STALL_RUN + 5)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertLessEqual(score, 63)
        self.assertTrue(any("complexity-emission ratio" in r for r in reasons))

    def test_session_health_score_bonus(self):
        # Delivery must be evidenced to count: outcomes recorded, verifiers
        # named (alternating so independence/diversity are measurable),
        # distinct next actions. The round-12 sentinel gates removed the
        # phantom praise that used to pad this score.
        h = [dict(t=1000+i, next="A%d" % i, marker="DONE", verified=2,
                  confidence="strong", risk="low", extra_steps=0,
                  outcome="ok", verifier=("v1" if i % 2 == 0 else "v2"))
             for i in range(mindseam.STALL_RUN + 5)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertGreaterEqual(score, 50)
        self.assertTrue(any("lean effective reasoning" in r for r in reasons))


class R34NarrativeKnotTests(unittest.TestCase):
    def test_short_history(self):
        h = [dict(t=1000+i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low") for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.narrative_knot_detector(h), 100)

    def test_no_retreads(self):
        h = [dict(t=1000+i, next="A%d" % i, marker="OPEN", verified=0, confidence="thin", risk="low") for i in range(mindseam.STALL_RUN * 2)]
        self.assertEqual(mindseam.narrative_knot_detector(h), 100)

    def test_full_retread(self):
        h = []
        for i in range(mindseam.STALL_RUN):
            h.append(dict(t=1000+i, next="retry", marker="OPEN", verified=0, confidence="thin", risk="low"))
        for i in range(mindseam.STALL_RUN):
            h.append(dict(t=1000+i, next="other", marker="OPEN", verified=0, confidence="thin", risk="low"))
        for i in range(mindseam.STALL_RUN):
            h.append(dict(t=1000+i, next="retry", marker="OPEN", verified=0, confidence="thin", risk="low"))
        score = mindseam.narrative_knot_detector(h)
        self.assertLess(score, 100)
        self.assertGreaterEqual(score, 0)

    def test_partial_retread(self):
        h = [dict(t=1000+i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low") for i in range(mindseam.STALL_RUN + 1)]
        last = [dict(t=1000+i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low") for i in range(mindseam.STALL_RUN + 1)]
        h.extend(last)
        score = mindseam.narrative_knot_detector(h)
        expected = max(0, int(100 - (5 * 100 / float(mindseam.STALL_RUN + 1))))
        self.assertEqual(score, expected)

    def test_session_health_score_penalty(self):
        h = [dict(t=1000+i, next="knot", marker="OPEN", verified=0, confidence="thin", risk="low") for i in range(mindseam.STALL_RUN * 2)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertLessEqual(score, 63)
        self.assertTrue(any("narrative knot" in r for r in reasons))

    def test_observations_wiring(self):
        h = [dict(t=1000+i, next="knot", marker="OPEN", verified=0, confidence="thin", risk="low", error="err1") for i in range(mindseam.STALL_RUN * 2)]
        facts = mindseam.observations(h, book=None)
        expected = "Narrative knot detected (%d/100); the session appears to revisit unresolved items repeatedly." % mindseam.narrative_knot_detector(h)
        self.assertIn(expected, facts)


class R34ObservationsWiringTests(unittest.TestCase):
    def test_story_switch_observation(self):
        stable = [dict(t=1000+i, next="alpha:x", marker="DONE", verified=3, confidence="strong", risk="low") for i in range(mindseam.STALL_RUN)]
        switch = [dict(t=1000+j, next="beta:y", marker="OPEN", verified=0, confidence="thin", risk="low") for j in range(mindseam.STALL_RUN)]
        h = stable + switch
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("Story switch detected" in f for f in facts))

    def test_complexity_emission_observation(self):
        h = [dict(t=1000+i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low", extra_steps=3) for i in range(mindseam.STALL_RUN + 5)]
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("Complexity-emission ratio is low" in f for f in facts))

    def test_narrative_knot_observation(self):
        h = [dict(t=1000+i, next="knot", marker="OPEN", verified=0, confidence="thin", risk="low") for i in range(mindseam.STALL_RUN * 2)]
        facts = mindseam.observations(h, book=None)
        self.assertTrue(any("Narrative knot detected" in f for f in facts))


class R34ShsWiringTests(unittest.TestCase):
    def test_session_health_score_story_switch_penalty(self):
        stable = [dict(t=1000+i, next="alpha:x", marker="DONE", verified=3, confidence="strong", risk="low") for i in range(mindseam.STALL_RUN)]
        switch = [dict(t=1000+j, next="beta:y", marker="OPEN", verified=0, confidence="thin", risk="low") for j in range(mindseam.STALL_RUN)]
        h = stable + switch
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertLessEqual(score, 55)
        self.assertTrue(any("story switch" in r for r in reasons))

    def test_session_health_score_complexity_emission_penalty(self):
        h = [dict(t=1000+i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low", extra_steps=2) for i in range(mindseam.STALL_RUN + 5)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertLessEqual(score, 50)
        self.assertTrue(any("complexity-emission ratio" in r for r in reasons))

    def test_session_health_score_narrative_knot_penalty(self):
        h = [dict(t=1000+i, next="A", marker="OPEN", verified=0, confidence="thin", risk="low", error="e") for i in range(mindseam.STALL_RUN * 2)]
        h[-1]["next"] = h[0]["next"]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertLessEqual(score, 70)
        self.assertTrue(any("narrative knot" in r for r in reasons))
