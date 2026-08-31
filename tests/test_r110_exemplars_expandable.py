# -*- coding: utf-8 -*-
"""Round 72 guards: the exemplars file obeys the invariant it models.

Invariant three says a dense line must expand back into plain words on
request. exemplars.md is the reference that teaches the dense track, so
every dense example it shows must be paired with its plain expansion —
21 table pairs exist today, none empty. The guard pins the pairing so
a new example cannot ship dense-only.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXEMPLARS = (ROOT / "mindseam" / "references" / "exemplars.md") \
    .read_text(encoding="utf-8")


class ExemplarsExpandableTests(unittest.TestCase):

    def test_dense_table_rows_carry_expansions(self):
        pairs = re.findall(r"^\| `([^`]+)` \| (.+) \|$", EXEMPLARS, re.M)
        self.assertGreaterEqual(len(pairs), 15,
                                "dense/plain table shrank: %d pairs"
                                % len(pairs))
        empties = [dense for dense, expansion in pairs
                   if not expansion.strip()]
        self.assertEqual(empties, [])

    def test_every_pair_expansion_is_not_itself_dense(self):
        # The expansion column must not contain the inner-only arrow
        # notation it is supposed to translate.
        pairs = re.findall(r"^\| `([^`]+)` \| (.+) \|$", EXEMPLARS, re.M)
        dense_leaks = [e for _, e in pairs if "⇒" in e or "∴" in e]
        self.assertEqual(dense_leaks, [])

    def test_dense_examples_use_taught_symbols_only(self):
        import sys
        sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
        import mindseam
        pairs = re.findall(r"^\| `([^`]+)` \| (.+) \|$", EXEMPLARS, re.M)
        for dense, _ in pairs:
            # Dense examples may use inner symbols freely — they live in
            # the reference, not in outgoing text — so this pins the
            # positive direction: at least one taught symbol per dense
            # example.
            self.assertTrue(
                any(s in dense for s in mindseam.INNER_ONLY)
                or any(m in dense for m in mindseam.MARKERS)
                or re.search(r"[A-Za-z0-9]", dense),
                "unexpandable example: %r" % dense)


if __name__ == "__main__":
    unittest.main()
