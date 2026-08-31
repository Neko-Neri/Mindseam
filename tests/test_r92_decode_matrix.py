# -*- coding: utf-8 -*-
"""Round 54 guards: outgoing bytes decode safely or not at all.

decode_outgoing is the single entry point for everything ship reads.
The matrix pins it: plain UTF-8, UTF-8 with BOM, UTF-16 and UTF-32 with
their BOMs all decode to the same text; NUL-bearing bytes that suggest
an unsupported encoding are rejected with a labelled problem instead
of silently mangling; and every rejection returns (None, reason) so
the caller can print CANNOT and exit 2.
"""

import codecs
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

TEXT = "结果 ok — 检查通过 ✓"


class DecodeMatrixTests(unittest.TestCase):

    def test_plain_utf8(self):
        decoded, problem = mindseam.decode_outgoing(TEXT.encode("utf-8"), "f")
        self.assertIsNone(problem)
        self.assertEqual(decoded, TEXT)

    def test_utf8_bom(self):
        decoded, problem = mindseam.decode_outgoing(
            codecs.BOM_UTF8 + TEXT.encode("utf-8"), "f")
        self.assertIsNone(problem)
        self.assertEqual(decoded, TEXT)

    def test_utf16_with_bom(self):
        decoded, problem = mindseam.decode_outgoing(
            TEXT.encode("utf-16"), "f")
        self.assertIsNone(problem)
        self.assertEqual(decoded, TEXT)

    def test_utf32_with_bom(self):
        decoded, problem = mindseam.decode_outgoing(
            TEXT.encode("utf-32"), "f")
        self.assertIsNone(problem)
        self.assertEqual(decoded, TEXT)

    def test_bare_utf16_bytes_are_rejected(self):
        # UTF-16 without a BOM decodes as UTF-8 into NUL-bearing
        # garbage; that must be rejected, not passed through.
        data = TEXT.encode("utf-16-le")
        decoded, problem = mindseam.decode_outgoing(data, "f")
        self.assertIsNone(decoded)
        self.assertIn("cannot decode", problem)

    def test_empty_input_is_fine(self):
        decoded, problem = mindseam.decode_outgoing(b"", "f")
        self.assertIsNone(problem)
        self.assertEqual(decoded, "")


if __name__ == "__main__":
    unittest.main()
