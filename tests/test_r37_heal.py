import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _step(i, confidence="strong", verified=1, marker="STEP",
          reason="checked", verifier="v1", error="", extra_steps=0, next="verify-result"):
    return dict(
        step=i, t=1000 + i, action="cast_%d" % i,
        next=next, confidence=confidence, risk="low",
        magnified_risk="low", verified=verified, reason=reason,
        verifier=verifier, outcome="ok", expect="secondary",
        output_received="ok", output_expected="ok",
        error=error, extra_steps=extra_steps, marker=marker,
    )


def make_domain_step(i, confidence="strong", verified=1, marker="STEP",
                     reason=None, verifier=None, error="", extra_steps=0, next=None, **kw):
    if reason is None:
        reason = "verified:%d" % i
    if verifier is None:
        verifier = "test_mod_v%d" % i
    if next is None:
        domains = ["analyze", "compute", "experiment", "deploy", "review"]
        next = "%s:step-%d" % (domains[i % len(domains)], i)
    return dict(
        step=i, t=1000 + i, action="cast_%d" % i,
        next=next, confidence=confidence, risk="low",
        magnified_risk="low", verified=verified, reason=reason,
        verifier=verifier, outcome="ok", expect="secondary",
        output_received="ok", output_expected="ok",
        error=error, extra_steps=extra_steps, marker=marker, **kw
    )


class HealActionTests(unittest.TestCase):
    def test_empty_history(self):
        actions = mindseam.heal_actions([])
        self.assertEqual(actions, [])

    def test_short_history_returns_collection_hint(self):
        actions = mindseam.heal_actions([_step(0)])
        self.assertEqual(len(actions), 1)
        self.assertIn("Collect at least %d seams" % mindseam.STALL_RUN, actions[0])

    def test_thin_confidence_triggers_inflation(self):
        h = [make_domain_step(i) for i in range(mindseam.STALL_RUN + 2)]
        for s in h:
            s["confidence"] = "strong"
            s["verified"] = 0
            s["next"] = "make it better"
        actions = mindseam.heal_actions(h)
        self.assertIn(
            "HEAL: Confidence may be inflated — lower confidence labels until verification supports them.",
            actions)

    def test_low_verification_triggers_coverage(self):
        h = [make_domain_step(i) for i in range(mindseam.STALL_RUN + 2)]
        for s in h:
            s["verified"] = 1
            s["reason"] = ""
            s["verifier"] = ""
        actions = mindseam.heal_actions(h)
        self.assertIn(
            "HEAL: Verification is thin — add evidence beyond bare verified/unverified (method + source).",
            actions)

    def test_generic_next_action_triggers_stub(self):
        h = [make_domain_step(i) for i in range(mindseam.STALL_RUN + 2)]
        markers = ["OPEN", "DONE", "PHEW", "DONE", "PHEW"]
        for idx, s in enumerate(h):
            s["next"] = "todo"
            s["marker"] = markers[idx % len(markers)]
        actions = mindseam.heal_actions(h)
        self.assertIn(
            "HEAL: Actions are generic — add domain specifics (targets, thresholds, owners) to next action.",
            actions)

    def test_single_verifier_triggers_independence(self):
        h = [make_domain_step(i) for i in range(mindseam.STALL_RUN + 2)]
        for s in h:
            s["verifier"] = "v1"
            s["marker"] = "DONE"
        actions = mindseam.heal_actions(h)
        self.assertIn(
            "HEAL: Single-verifier concentration — use a different verifier name for the next check.",
            actions)



    def test_error_without_recovery_triggers_recovery(self):
        h = [_step(0, error="", next="task0:setup"),
             _step(1, error="db timeout", next="skip db continue"),
             _step(2, error="", next="task2:act"),
             _step(3, error="port conflict", next="skip and go on"),
             _step(4, error="", next="task4:act")]
        actions = mindseam.heal_actions(h)
        self.assertIn(
            "HEAL: Errors ignored in next action — address each error explicitly in the following step.",
            actions)

    def test_with_book_alignment_action(self):
        h = [make_domain_step(i) for i in range(mindseam.STALL_RUN + 2)]
        for s in h:
            s["next"] = "thread-alpha:step-%d" % s["step"]
        book = {"Open": ["thread-beta:fix-bug"],
                "Done": ["thread-alpha:closed"], "Phew": []}
        actions = mindseam.heal_actions(h, book=book)
        self.assertIn(
            "HEAL: Next action diverges from open ledger thread — re-align with the current Open item.",
            actions)


if __name__ == "__main__":
    unittest.main()
