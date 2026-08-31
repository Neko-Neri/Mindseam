# -*- coding: utf-8 -*-
"""Round 8 guards: threshold consistency and the dead heal branch.

Exhaustive probe over 108 fixtures (3^3 confidence grids x frozen/
alternating next patterns x frozen/climbing verified counters) proved:
- _fuse_run's inline stall severity equals stall_score() on every
  fixture (0 divergences), so fusion, observations, trend banner and
  heal all read the same number;
- the reachable severity grid is {0,15,30,40,45,55,60,70,85,100}, so
  heal's ``> HEAL_SEVERITY_CEILING`` (55) gate and the ``>= 60``
  fusion/observation tiers never disagree on a reachable value;
- heal_actions' trailing ``Insufficient seams`` branch sat behind the
  early return at the top of the function and could never run.

Defect 17 removes that unreachable branch. These tests pin the
equivalence and the tier ladder so future edits cannot silently
re-introduce a two-severity system or an unreachable line.
"""

import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def step(conf="thin", nxt="alpha", verified=0):
    step.t = getattr(step, "t", 0) + 600
    return {"t": 1000000 + step.t, "next": nxt, "verified": verified, "open": 1,
            "marker": "OPEN", "confidence": conf, "verifier": "v",
            "risk": "low", "error": "", "outcome": "", "extra_steps": 0}


BOOK = {"Goal": ["g"], "Core": ["c"], "Verified": [], "Open": ["o"],
        "Next": ["alpha"], "Closing": []}


def setUpModule():
    step.t = 0


class R48SeverityEquivalenceTests(unittest.TestCase):
    """_fuse_run and stall_score must stay one severity system."""

    def test_fuse_and_detector_agree_over_the_fixture_grid(self):
        for confs in itertools.product(("strong", "thin", "shaky"), repeat=3):
            for pattern in ("frozen", "alternating"):
                for vmode in ("frozen", "climbing"):
                    step.t = 0
                    hist = []
                    for i, c in enumerate(confs):
                        nxt = "alpha" if pattern == "frozen" else ("alpha", "beta")[i % 2]
                        ver = 5 if vmode == "frozen" else i + 1
                        hist.append(step(conf=c, nxt=nxt, verified=ver))
                    _, _, st_fuse, _, _, _, _, _, _, _ = mindseam._fuse_run(hist)
                    self.assertEqual(
                        st_fuse, mindseam.stall_score(hist),
                        "severity divergence at %s" % ((confs, pattern, vmode),))

    def test_reachable_severity_grid_has_no_heal_gap(self):
        reachable = set()
        for confs in itertools.product(("strong", "thin", "shaky"), repeat=2):
            for pattern in ("frozen", "alternating"):
                step.t = 0
                hist = []
                for i, c in enumerate(confs):
                    nxt = "alpha" if pattern == "frozen" else ("alpha", "beta")[i % 2]
                    hist.append(step(conf=c, nxt=nxt, verified=i + 1))
                reachable.add(mindseam.stall_score(hist))
        for sev in reachable:
            heal_fires = sev > mindseam.HEAL_SEVERITY_CEILING
            fusion_flags = sev >= 60
            self.assertEqual(
                heal_fires, fusion_flags,
                "heal and fusion disagree at severity %d" % sev)


class R48TierLadderTests(unittest.TestCase):
    """The elevated/high/HEAL ladder must be monotone and consistent."""

    def _hist_with_severity(self, target):
        """Build a 3-seam history whose stall_score is exactly `target`."""
        if target == 0:
            return [step(conf="strong", nxt="a%d" % i, verified=i + 1) for i in range(3)]
        if target == 40:
            return [step(conf="strong", nxt="alpha", verified=i + 1) for i in range(3)]
        if target == 70:
            return [step(conf="strong", nxt="alpha", verified=5) for _ in range(3)]
        raise ValueError("unsupported target")

    def test_elevated_band_gets_a_fact_line_but_no_heal(self):
        hist = self._hist_with_severity(40)
        facts = mindseam.observations(hist)
        self.assertTrue(any("Stall severity is elevated (40/100)" in f for f in facts))
        actions = [a for a in mindseam.heal_actions(hist, book=dict(BOOK))
                   if "Session is stalled" in a]
        self.assertEqual(actions, [])

    def test_high_band_gets_high_fact_line_and_heal(self):
        hist = self._hist_with_severity(70)
        facts = mindseam.observations(hist)
        self.assertTrue(any("Stall severity is high (70/100)" in f for f in facts))
        self.assertIn(
            "HEAL: Session is stalled — pivot the next action to a different task or approach.",
            mindseam.heal_actions(hist, book=dict(BOOK)))

    def test_zero_severity_gets_neither(self):
        hist = self._hist_with_severity(0)
        facts = mindseam.observations(hist)
        self.assertFalse(any("Stall severity" in f for f in facts))
        actions = [a for a in mindseam.heal_actions(hist, book=dict(BOOK))
                   if "Session is stalled" in a]
        self.assertEqual(actions, [])


class R48DeadBranchTests(unittest.TestCase):
    """Defect 17: the unreachable 'Insufficient seams' heal line."""

    def test_short_history_returns_only_the_collect_more_line(self):
        out = mindseam.heal_actions([step()], book=dict(BOOK))
        self.assertEqual(out, ["HEAL: Collect at least %d seams before judging session health."
                               % mindseam.STALL_RUN])

    def test_insufficient_seams_text_is_gone(self):
        hist = [step(conf="thin", nxt="alpha%d" % i, verified=i + 1) for i in range(3)]
        out = mindseam.heal_actions(hist, book=dict(BOOK))
        for action in out:
            self.assertNotIn("Insufficient seams", action)

    def test_source_has_no_trailing_short_history_branch(self):
        src = Path(mindseam.__file__).read_text(encoding="utf-8")
        self.assertNotIn('"HEAL: Insufficient seams', src)


if __name__ == "__main__":
    unittest.main()
