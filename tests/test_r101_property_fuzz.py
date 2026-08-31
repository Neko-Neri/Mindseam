# -*- coding: utf-8 -*-
"""Round 63 guards: randomised histories must not break any surface.

The first hundred rounds fixed defects one surface at a time. This
property test cross-examines every surface at once over randomised
histories drawn from the full eleven-field schema space (including
out-of-vocabulary values like "medium" confidence and free-text
markers, which the CLI permits and history repair preserves):

  * session_health_score stays in 0..100 with unique reason lines;
  * observations produces unique fact lines;
  * heal_actions produces unique lines and asks-for-data when short;
  * assess_risk returns a valid level with unique reasons;
  * grade maps every reachable score into {A,B,C,D,F};
  * the ship text scanner terminates on arbitrary input.

The seed is fixed for reproducibility; shrinking a failure is a matter
of re-running with the printed trial number.
"""

import contextlib
import io
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

BOOKS = (
    None,
    {"Goal": ["g"], "Core": ["c — f"], "Verified": [],
     "Open": ["?01 q — settled by: t"], "Next": ["dom: act"]},
    {"Goal": [], "Core": [], "Verified": [], "Open": [], "Next": []},
)

SHIP_BOOK = {"Goal": ["g"], "Core": [], "Verified": [], "Open": [],
             "Next": ["n"]}


def random_history(rng):
    n = rng.randint(0, 12)
    return [{
        "t": 1000 + i * rng.choice([0, 60, 600]),
        "next": rng.choice(["dom: act", "dom: act", "", "todo", "x",
                            "dom%d: step %d" % (i % 5, i)]),
        "verified": rng.choice([0, 0, 1, 2, 5]),
        "open": rng.randint(0, 4),
        "marker": rng.choice(["OPEN", "DONE", "PHEW", "STEP", "",
                              "GAAAH"]),
        "confidence": rng.choice(["strong", "thin", "shaky", "",
                                  "medium"]),
        "verifier": rng.choice(["v", "", "pytest tests -q exits 0",
                                "v%d" % (i % 2)]),
        "risk": rng.choice(["low", "medium", "high", ""]),
        "error": rng.choice(["", "", "db: down", "e: fail %d" % i,
                             "short"]),
        "outcome": rng.choice(["", "ok", "failed", ""]),
        "extra_steps": rng.choice([0, 0, 1, 9]),
    } for i in range(n)]


class PropertyFuzzTests(unittest.TestCase):

    def test_random_histories_preserve_every_invariant(self):
        rng = random.Random(20260823)
        for trial in range(300):
            hist = random_history(rng)
            for book in BOOKS:
                result = mindseam.session_health_score(hist, book=book)
                self.assertTrue(0 <= result.score <= 100,
                                "trial %d: score %r" % (trial, result.score))
                self.assertEqual(len(result.reasons),
                                 len(set(result.reasons)),
                                 "trial %d: %r" % (trial, result.reasons))
                self.assertIn(mindseam.grade(result.score), "ABCDF")
                facts = mindseam.observations(hist, book=book)
                self.assertEqual(len(facts), len(set(facts)),
                                 "trial %d: %r" % (trial, facts))
                heal = mindseam.heal_actions(hist, book=book)
                self.assertEqual(len(heal), len(set(heal)))
                if len(hist) < mindseam.STALL_RUN and heal:
                    self.assertEqual(len(heal), 1, heal)
                level, reasons = mindseam.assess_risk(hist)
                self.assertIn(level, ("low", "medium", "high"))
                self.assertEqual(len(reasons), len(set(reasons)))

    def test_ship_scanner_terminates_on_arbitrary_text(self):
        rng = random.Random(99)
        words = ["verified", "coverage", "|", "```", "---", "#", "⇒",
                 "PHEW", "…", "a", "line", "", "结果", "已经验证"]
        for _ in range(100):
            text = "\n".join(
                " ".join(rng.choices(words, k=rng.randint(0, 6)))
                for _ in range(rng.randint(0, 8)))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = mindseam.mode_ship(dict(SHIP_BOOK), text)
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
