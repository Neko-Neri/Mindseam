"""Regression tests for the mechanism-layer bindings added in round 43.

Three defects were all of the same kind: a detector existed, was correct, and was
never reachable from a real command. Invariant 2 calls that an unplugged monitor.
These tests plug the monitor in and keep it plugged:

  1. session_health_score was called without `book` from seam/resume, so every
     ledger-aware factor silently reported its no-evidence default. That is worse
     than a gap: it inverted conclusions (plan divergence read as plan alignment).
  2. heal_actions had 32 detectors and no caller on any output path.
  3. history entries carried no error/outcome/extra_steps, starving the detectors
     that consume them, and `note` had no way to supply them.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam

from _controller_helper import run_controller


DOMAINS = ["analyze", "design", "verify", "persist", "report", "review", "probe", "ship"]
MARKERS = ["STEP", "CHECK", "OPEN"]


def healthy_step(i, now):
    """A step that scores well on every history-only detector.

    ``verified`` is the cumulative size of the ledger's Verified list, so a
    rising run of confirmations is written as 1, 2, 3, ... — the schema the
    detectors consume (a flat run of 1s would read as a verification plateau).
    """
    return {
        "t": now - (8 - i) * 60,
        "next": "%s: inspect input %d" % (DOMAINS[i % len(DOMAINS)], i),
        "verified": i + 1,
        "open": 0,
        "marker": MARKERS[i % len(MARKERS)],
        "confidence": "strong",
        "verifier": "pytest tests -q exits 0",
        "risk": "low",
        "error": "",
        "outcome": "ok",
        "extra_steps": 0,
    }


def middling_step(i, now, cum):
    """A step that is mediocre but not catastrophic.

    The score saturates at 100 and 0, so a fully healthy or fully degraded
    history cannot show what the ledger contributes: both ends clamp. This
    shape keeps the score in the responsive middle band. ``cum`` is the
    cumulative verified count the step froze at.
    """
    return {
        "t": now - (8 - i) * 60,
        "next": "%s: inspect input %d" % (DOMAINS[i % len(DOMAINS)], i),
        "verified": cum,
        "open": 1,
        "marker": MARKERS[i % len(MARKERS)],
        "confidence": "thin",
        "verifier": "pytest tests -q exits 0",
        "risk": "low",
        "error": "persist: write failed",
        "outcome": "failed",
        "extra_steps": 1,
    }


def degraded_step(t, next_action="make it better"):
    """A step shaped to drive the ledger-aware and event-key detectors low."""
    return {
        "t": t,
        "next": next_action,
        "verified": 0,
        "open": 3,
        "marker": "OPEN",
        "confidence": "strong",
        "verifier": "v1",
        "risk": "high",
        "error": "db timeout",
        "outcome": "",
        "extra_steps": 3,
    }


class MechanismBindingBase(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _history_path(self):
        return Path(self.workspace) / ".mindseam" / "history.json"

    def _meta_path(self):
        return Path(self.workspace) / ".mindseam" / "metacognition.json"

    def _open(self, goal="ship it", next_action="analyze: inspect inputs"):
        r = run_controller(self.workspace, "note", "--goal", goal, "--next", next_action)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def _seed(self, entries):
        path = self._history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries), encoding="utf-8")

    def _seed_degraded(self, count=8):
        now = int(time.time())
        self._seed([degraded_step(now - (count - 1 - i)) for i in range(count)])

    def _seed_middling(self):
        """Half healthy, half mediocre — keeps the score off both clamps."""
        now = int(time.time())
        self._seed(
            [healthy_step(i, now) for i in range(4)]
            + [middling_step(i, now, 4) for i in range(4, 8)]
        )

    def _history(self):
        path = self._history_path()
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def _meta(self):
        path = self._meta_path()
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


class LedgerAwareHealthScore(MechanismBindingBase):
    """Defect 1: seam and resume must hand the ledger to the score."""

    def test_book_changes_the_score_and_its_reasons(self):
        self._open()
        self._seed_middling()
        cwd = os.getcwd()
        os.chdir(self.workspace)
        try:
            book = mindseam.read_ledger()
            hist = self._history()
            blind_score, blind_reasons = mindseam.session_health_score(hist)
            aware_score, aware_reasons = mindseam.session_health_score(hist, book=book)
        finally:
            os.chdir(cwd)
        self.assertNotEqual(
            blind_score, aware_score,
            "the ledger must move the score, or passing it is decorative"
        )
        self.assertLess(
            aware_score, blind_score,
            "this fixture diverges from the ledger, so the truth is the lower score"
        )
        self.assertTrue(
            set(aware_reasons) - set(blind_reasons),
            "the ledger must contribute at least one factor of its own"
        )

    def test_ledger_blind_scoring_crosses_a_grade_boundary(self):
        """The gap is not cosmetic: it changes the grade a reader acts on."""
        self._open()
        self._seed_middling()
        cwd = os.getcwd()
        os.chdir(self.workspace)
        try:
            book = mindseam.read_ledger()
            hist = self._history()
            blind_score, _ = mindseam.session_health_score(hist)
            aware_score, _ = mindseam.session_health_score(hist, book=book)
        finally:
            os.chdir(cwd)
        self.assertNotEqual(mindseam.grade(blind_score), mindseam.grade(aware_score))

    def test_ledger_blind_scoring_reports_the_opposite_conclusion(self):
        """This is the reason the fix matters: the default was a false positive."""
        self._open()
        self._seed_middling()
        cwd = os.getcwd()
        os.chdir(self.workspace)
        try:
            book = mindseam.read_ledger()
            hist = self._history()
            _, blind_reasons = mindseam.session_health_score(hist)
            _, aware_reasons = mindseam.session_health_score(hist, book=book)
        finally:
            os.chdir(cwd)
        blind = " ".join(blind_reasons)
        aware = " ".join(aware_reasons)
        # Ledger-dependent factors are silent without a ledger: the
        # sentinel-100 they return when unmeasurable must not be scored as
        # "high goal alignment" / "ledger plan alignment" bonuses.
        self.assertIn("ledger plan divergence", aware)
        self.assertIn("low goal alignment", aware)
        self.assertNotIn("ledger plan divergence", blind)
        self.assertNotIn("ledger plan alignment", blind)
        self.assertNotIn("high goal alignment", blind)
        self.assertNotIn("ledger plan alignment", aware)

    def test_seam_surfaces_ledger_aware_factors(self):
        self._open()
        self._seed_middling()
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ledger plan divergence", result.stdout)
        self.assertNotIn("ledger plan alignment", result.stdout)

    def test_resume_surfaces_ledger_aware_factors(self):
        self._open()
        self._seed_middling()
        result = run_controller(self.workspace, "resume")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ledger plan divergence", result.stdout)
        self.assertNotIn("ledger plan alignment", result.stdout)


class HealActionsReachStdout(MechanismBindingBase):
    """Defect 2: heal_actions had no caller on any output path."""

    def _heal_lines(self, stdout):
        return [
            line.strip() for line in stdout.splitlines()
            if line.strip().startswith("- HEAL:")
        ]

    def test_seam_prints_the_heal_section(self):
        self._open()
        self._seed_degraded()
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Heal (", result.stdout)
        self.assertTrue(self._heal_lines(result.stdout), result.stdout)

    def test_heal_section_is_capped_and_says_how_many_were_held_back(self):
        self._open()
        self._seed_degraded()
        result = run_controller(self.workspace, "seam")
        printed = self._heal_lines(result.stdout)
        self.assertLessEqual(len(printed), mindseam.HEAL_REPORT_MAX)
        cwd = os.getcwd()
        os.chdir(self.workspace)
        try:
            book = mindseam.read_ledger()
            total = len(mindseam.heal_actions(self._history(), book=book))
        finally:
            os.chdir(cwd)
        self.assertGreater(total, mindseam.HEAL_REPORT_MAX, "fixture is no longer degraded enough")
        self.assertIn("more; the ones above are the cheapest to act on.", result.stdout)

    def test_heal_reports_the_full_detector_count_not_the_printed_count(self):
        self._open()
        self._seed_degraded()
        result = run_controller(self.workspace, "seam")
        cwd = os.getcwd()
        os.chdir(self.workspace)
        try:
            book = mindseam.read_ledger()
            total = len(mindseam.heal_actions(self._history(), book=book))
        finally:
            os.chdir(cwd)
        self.assertIn("Heal (%d detectors below threshold):" % total, result.stdout)

    def test_healthy_session_prints_no_heal_section(self):
        self._open()
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("Heal (", result.stdout)

    def test_short_history_suppresses_the_collect_more_seams_hint(self):
        """heal_actions' own early return is noise at a seam that already says it."""
        self._open()
        now = int(time.time())
        self._seed([degraded_step(now - 1)])
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0)
        self.assertLess(len(self._history()), mindseam.STALL_RUN)
        self.assertNotIn("Heal (", result.stdout)
        self.assertNotIn("Collect at least", result.stdout)


class EventFieldsRoundTrip(MechanismBindingBase):
    """Defect 3: note could not supply error/outcome/extra_steps, so 28 detectors starved."""

    def test_note_records_the_three_event_fields(self):
        self._open()
        result = run_controller(
            self.workspace, "note",
            "--error", "persist: write failed",
            "--outcome", "failed",
            "--extra-steps", "2",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        meta = self._meta()
        self.assertEqual(meta.get("error"), "persist: write failed")
        self.assertEqual(meta.get("outcome"), "failed")
        self.assertEqual(meta.get("extra_steps"), 2)

    def test_seam_writes_the_event_fields_into_history(self):
        self._open()
        run_controller(
            self.workspace, "note",
            "--error", "persist: write failed",
            "--outcome", "failed",
            "--extra-steps", "2",
        )
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        entry = self._history()[-1]
        self.assertEqual(entry.get("error"), "persist: write failed")
        self.assertEqual(entry.get("outcome"), "failed")
        self.assertEqual(entry.get("extra_steps"), 2)

    def test_event_keys_are_cleared_so_one_error_is_not_recorded_forever(self):
        self._open()
        run_controller(
            self.workspace, "note",
            "--error", "persist: write failed",
            "--outcome", "failed",
            "--extra-steps", "2",
        )
        run_controller(self.workspace, "seam")
        meta = self._meta()
        for key in mindseam.METACOGNITION_EVENT_KEYS:
            self.assertNotIn(key, meta, "%s persisted past the seam that consumed it" % key)
        run_controller(self.workspace, "seam")
        entry = self._history()[-1]
        self.assertEqual(entry.get("error"), "")
        self.assertEqual(entry.get("outcome"), "")
        self.assertEqual(entry.get("extra_steps"), 0)

    def test_state_keys_survive_the_seam_that_event_keys_do_not(self):
        self._open()
        run_controller(
            self.workspace, "note",
            "--confidence", "thin",
            "--marker", "OPEN",
            "--error", "persist: write failed",
        )
        run_controller(self.workspace, "seam")
        meta = self._meta()
        self.assertEqual(meta.get("confidence"), "thin")
        self.assertEqual(meta.get("marker"), "OPEN")
        self.assertNotIn("error", meta)

    def test_every_appended_entry_carries_the_full_schema(self):
        self._open()
        run_controller(self.workspace, "seam")
        entry = self._history()[-1]
        for key in ("t", "next", "verified", "open", "marker",
                    "confidence", "verifier", "risk",
                    "error", "outcome", "extra_steps"):
            self.assertIn(key, entry, "history entry lost the %s field" % key)


class EventFieldsRefuseBadInput(MechanismBindingBase):
    """A field the detectors trust must not accept values they cannot read."""

    def test_negative_extra_steps_is_refused(self):
        self._open()
        result = run_controller(self.workspace, "note", "--extra-steps", "-1")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("--extra-steps cannot be negative.", result.stdout)
        self.assertNotIn("extra_steps", self._meta())

    def test_multiline_error_is_refused(self):
        self._open()
        result = run_controller(self.workspace, "note", "--error", "line one\nline two")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("--error must be one line.", result.stdout)
        self.assertNotIn("error", self._meta())

    def test_empty_outcome_is_refused(self):
        self._open()
        result = run_controller(self.workspace, "note", "--outcome", "   ")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("--outcome must not be empty.", result.stdout)
        self.assertNotIn("outcome", self._meta())

    def test_a_refused_event_field_does_not_cost_an_accepted_edit(self):
        self._open()
        result = run_controller(
            self.workspace, "note",
            "--outcome", "ok",
            "--extra-steps", "-3",
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self._meta().get("outcome"), "ok")
        self.assertNotIn("extra_steps", self._meta())

    def test_read_history_repairs_wrong_types_in_the_new_fields(self):
        self._open()
        now = int(time.time())
        self._seed([{
            "t": now - 1,
            "next": "analyze: inspect inputs",
            "verified": 0,
            "open": 0,
            "error": 123,
            "outcome": ["failed"],
            "extra_steps": "2",
        }])
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        entry = self._history()[0]
        self.assertEqual(entry["error"], "")
        self.assertEqual(entry["outcome"], "")
        self.assertEqual(entry["extra_steps"], 0)

    def test_read_history_repairs_negative_extra_steps_on_disk(self):
        self._open()
        now = int(time.time())
        self._seed([{
            "t": now - 1,
            "next": "analyze: inspect inputs",
            "verified": 0,
            "open": 0,
            "extra_steps": -5,
        }])
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self._history()[0]["extra_steps"], 0)


class FactPathAgreesWithTheBanner(MechanismBindingBase):
    """Defect 4: a detector that reports a score must report the same score.

    premature_convergence has two modes. Scalar mode is a leaf and takes no
    ledger. Fact mode re-derives the whole health score to decide whether to
    warn -- and it was doing that blind while the seam banner did it
    ledger-aware. One seam then printed two different numbers for the same
    quantity, and the lower one was the true one.

    Worse than the mismatch was the inversion: the message asserts "score is
    high but issues remain", which is the definition of premature convergence.
    At a truthful 68/100 nothing has converged, so the warning was pure noise
    exactly when the session was in trouble.
    """

    def _facts(self):
        cwd = os.getcwd()
        os.chdir(self.workspace)
        try:
            book = mindseam.read_ledger()
            hist = self._history()
            aware, _ = mindseam.session_health_score(hist, book=book)
            return aware, mindseam.premature_convergence(hist, book=book)
        finally:
            os.chdir(cwd)

    def test_fact_mode_quotes_the_ledger_aware_score(self):
        self._open()
        self._seed_middling()
        cwd = os.getcwd()
        os.chdir(self.workspace)
        try:
            book = mindseam.read_ledger()
            hist = self._history()
            blind, _ = mindseam.session_health_score(hist)
            aware, _ = mindseam.session_health_score(hist, book=book)
            facts = mindseam.premature_convergence(hist, book=book)
        finally:
            os.chdir(cwd)
        self.assertNotEqual(
            blind, aware,
            "fixture must separate the two scores or this test proves nothing"
        )
        for fact in facts:
            self.assertNotIn(
                "(%d/100)" % blind, fact,
                "fact mode quoted the ledger-blind score; the banner would "
                "print %d/100 and this line claims %d/100" % (aware, blind)
            )

    def test_fact_mode_does_not_claim_a_mediocre_score_is_high(self):
        self._open()
        self._seed_middling()
        aware, facts = self._facts()
        self.assertLess(aware, 75, "fixture must sit below the high-score gate")
        self.assertEqual(
            facts, [],
            "at %d/100 nothing has converged, so warning about premature "
            "convergence is a false positive" % aware
        )

    def test_fact_mode_still_fires_when_the_score_is_genuinely_high(self):
        """The fix must not silence the detector, only stop it lying.

        The gate is `score >= 75 and (risk_esc or has_stall or compound)`.
        A trailing DONE/unverified step is the wrong lever: it lowers the
        scalar sub-score and clears `compound`, so nothing fires. A late risk
        escalation on an otherwise clean run is the honest shape for this case.
        """
        self._open()
        now = int(time.time())
        hist = [healthy_step(i, now) for i in range(8)]
        hist[-1] = dict(hist[-1], risk="high")
        self._seed(hist)
        aware, facts = self._facts()
        self.assertGreaterEqual(aware, 75, "fixture must clear the high-score gate")
        self.assertTrue(
            facts, "a genuinely high score with active issues must still warn"
        )
        self.assertIn("(%d/100)" % aware, facts[0])

    def test_scalar_mode_needs_no_ledger_and_does_not_recurse(self):
        self._open()
        self._seed_middling()
        cwd = os.getcwd()
        os.chdir(self.workspace)
        try:
            book = mindseam.read_ledger()
            hist = self._history()
            value = mindseam.premature_convergence(hist, book=book, score=True)
        finally:
            os.chdir(cwd)
        self.assertIsInstance(value, int)
        self.assertGreaterEqual(value, 0)
        self.assertLessEqual(value, 100)

    def test_seam_never_prints_two_different_health_numbers(self):
        """The banner and the premature-convergence line must agree.

        Only these two places print the *session health score*. Every other
        `N/100` in a seam is an individual detector reading and is expected to
        differ, so this matches the two exact phrasings rather than all numbers.
        """
        self._open()
        now = int(time.time())
        hist = [healthy_step(i, now) for i in range(8)]
        hist[-1] = dict(hist[-1], risk="high")
        self._seed(hist)
        result = run_controller(self.workspace, "seam")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        banner = re.findall(r"score: (\d+)/100 \(", result.stdout)
        fact = re.findall(r"Health score is high \((\d+)/100\)", result.stdout)
        self.assertTrue(banner, "seam printed no health banner:\n%s" % result.stdout)
        self.assertTrue(fact, "fixture did not trigger the fact line:\n%s" % result.stdout)
        self.assertEqual(
            set(banner), set(fact),
            "one seam reported two different health scores: banner %s vs fact %s\n%s"
            % (sorted(set(banner)), sorted(set(fact)), result.stdout)
        )


if __name__ == "__main__":
    unittest.main()
