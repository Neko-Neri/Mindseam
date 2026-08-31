# -*- coding: utf-8 -*-
"""Round 49 guards: mistyped meta values read as absence, not as crashes.

read_history repairs every field type it loads, but the metacognition
side had no equivalent: validate_meta_schema filtered unknown KEYS and
read_meta's same-version fast path skipped even that. A hand-edited
metacognition.json carrying ``marker: 99`` or ``confidence: 123``
flowed through append_history into history.json with its types intact,
and the seam that filled the third window of the scoring run died on
``'int' object has no attribute 'strip'`` — a bare traceback, against
the module's own 0-or-2 exit contract. Three layers now agree:

  * _meta_value_ok types every known key (str fields, dict risk/trend,
    non-negative int extra_steps) and validate_meta_schema drops the
    rest — a mistyped value reads as never recorded;
  * read_meta applies the same check on the same-version fast path, so
    a current-signature file cannot smuggle values past the migrator;
  * append_history coerces at the write, covering direct callers that
    pass hand-built meta.

The legacy "markers" rename additionally requires a string: renaming a
list into ``marker`` would have re-created the same poisoning one key
over.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam
from _controller_helper import run_controller

HOSTILE = {
    "confidence": 123, "risk": ["x"], "marker": 99,
    "verifier": {"k": 1}, "error": 3.14, "outcome": True,
    "extra_steps": "many", "trend": "nope", "schema_version": 1,
}


class HostileMetaValueTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)
        os.makedirs(mindseam.LEDGER_DIR, exist_ok=True)

    def tearDown(self):
        os.chdir(self.cwd)

    def _write_meta(self, payload):
        with open(os.path.join(mindseam.LEDGER_DIR, "metacognition.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_current_signature_drops_mistyped_values(self):
        self._write_meta(HOSTILE)
        self.assertEqual(mindseam.read_meta(), {})

    def test_foreign_signature_drops_them_through_the_migrator(self):
        payload = dict(HOSTILE, schema_version=999)
        self._write_meta(payload)
        self.assertEqual(mindseam.read_meta(), {})

    def test_valid_values_survive_the_same_check(self):
        self._write_meta({
            "schema_version": 1, "marker": "OPEN",
            "confidence": "strong",
            "risk": {"level": "high", "reasons": ["x"]},
            "trend": {"confidence": ["strong"]},
            "extra_steps": 2,
        })
        meta = mindseam.read_meta()
        self.assertEqual(meta.get("marker"), "OPEN")
        self.assertEqual(meta.get("risk", {}).get("level"), "high")
        self.assertEqual(meta.get("extra_steps"), 2)

    def test_migrator_drops_mistyped_known_keys(self):
        cleaned = mindseam.validate_meta_schema(HOSTILE)
        for key in ("confidence", "marker", "verifier", "error",
                    "outcome", "risk", "trend", "extra_steps"):
            self.assertNotIn(key, cleaned)

    def test_legacy_markers_rename_requires_a_string(self):
        cleaned = mindseam.validate_meta_schema(
            {"schema_version": 0, "markers": ["OPEN"]})
        self.assertNotIn("marker", cleaned)

    def test_append_history_coerces_hand_built_meta(self):
        book = {"Goal": ["g"], "Core": [], "Verified": [],
                "Open": [], "Next": ["dom: act"]}
        hist, _ = mindseam.append_history(book, meta=dict(HOSTILE))
        entry = hist[-1]
        for key in ("marker", "confidence", "verifier", "error", "outcome"):
            self.assertIsInstance(entry[key], str, key)
        self.assertIsInstance(entry["extra_steps"], int)


class HostileMetaEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def test_hostile_meta_cannot_crash_the_seam(self):
        meta_path = Path(self.ws) / ".mindseam"
        meta_path.mkdir(parents=True, exist_ok=True)
        (meta_path / "metacognition.json").write_text(
            json.dumps(HOSTILE), encoding="utf-8")
        self.assertEqual(
            run_controller(self.ws, "note", "--goal", "g",
                           "--next", "dom: act").returncode, 0)
        for _ in range(3):
            self.assertEqual(
                run_controller(self.ws, "note", "--next",
                               "dom: act more").returncode, 0)
            result = run_controller(self.ws, "seam")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        hist = json.loads(
            (meta_path / "history.json").read_text(encoding="utf-8"))
        mistyped = [
            (k, type(v).__name__) for e in hist for k, v in e.items()
            if not isinstance(v, (str, int)) or isinstance(v, bool)]
        self.assertEqual(mistyped, [])


class HostileMetaPropertyTests(unittest.TestCase):
    """Randomised garbage values must leave the pipeline well-typed.

    Fixed seed for reproducibility (round 63's convention). Every value
    JSON can express is offered for every known key; whatever survives
    read_meta must match the key's declared type, and append_history
    must write an entry read_history's repair rules would accept
    unchanged.
    """

    SEED = 20260824

    def setUp(self):
        # append_history writes relative to the cwd: run inside a temp
        # workspace so the property loop cannot touch a real .mindseam.
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)

    def tearDown(self):
        os.chdir(self.cwd)

    def test_random_json_values_stay_well_typed(self):
        import random
        rng = random.Random(self.SEED)
        garbage = [None, True, False, 0, 1, -1, 12345, 3.14, "", "OPEN",
                   [], ["x"], {}, {"k": 1}, {"level": "high"},
                   {"confidence": ["strong"]}, "a\nb"]
        for _ in range(200):
            payload = {"schema_version": rng.choice([0, 1, 999])}
            for key in mindseam.METACOGNITION_KEYS:
                if rng.random() < 0.7:
                    payload[key] = rng.choice(garbage)
            cleaned = mindseam.validate_meta_schema(payload)
            for key, value in cleaned.items():
                if key in mindseam.METACOGNITION_KEYS:
                    self.assertTrue(mindseam._meta_value_ok(key, value),
                                    (key, value))
            book = {"Goal": ["g"], "Core": [], "Verified": [],
                    "Open": [], "Next": ["dom: act"]}
            entry = mindseam.append_history(book, meta=cleaned)[0][-1]
            for key in ("marker", "confidence", "verifier", "error",
                        "outcome"):
                self.assertIsInstance(entry[key], str, (key, entry[key]))
            self.assertIsInstance(entry["extra_steps"], int)
            self.assertFalse(isinstance(entry["extra_steps"], bool))


if __name__ == "__main__":
    unittest.main()
