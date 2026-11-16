#!/usr/bin/env python3
"""Exercise the numerical oracle with independent pixel/encoding boundary fixtures."""
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.binary = cls.root / "compare"
        subprocess.run(["xcrun", "clang++", "-std=c++17", "-O2",
                        str(Path(__file__).with_name("wavefront-compare.cpp")),
                        "-o", str(cls.binary)], check=True)

    def compare(self, left, right, encoding="linear"):
        a, b = self.root / "a.f32", self.root / "b.f32"
        a.write_bytes(struct.pack("<" + "f" * len(left), *left))
        b.write_bytes(struct.pack("<" + "f" * len(right), *right))
        result = subprocess.run([str(self.binary), str(a), str(b), encoding],
                                capture_output=True, text=True)
        return result.returncode

    def test_identical_rgba(self):
        self.assertEqual(self.compare([0, .18, 4, .5], [0, .18, 4, .5]), 0)

    def test_alpha_must_be_exact(self):
        self.assertNotEqual(self.compare([0, .18, 4, .5], [0, .18, 4, .5000001]), 0)

    def test_linear_threshold(self):
        self.assertEqual(self.compare([0, 0, 0, 1], [0.000009, 0, 0, 1]), 0)
        self.assertNotEqual(self.compare([0, 0, 0, 1], [0.000011, 0, 0, 1]), 0)

    def test_non_finite_never_passes(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                self.assertNotEqual(self.compare([value, 0, 0, 1], [value, 0, 0, 1]), 0)

    def test_encoded_black_roundoff_allowed(self):
        self.assertEqual(self.compare([-.001, 0, 0, 1], [.001, 0, 0, 1], "rec709"), 0)

    def test_encoded_one_code_limit_is_independent(self):
        self.assertNotEqual(self.compare([0, 0, 0, 1], [.004, 0, 0, 1], "rec709"), 0)

    def test_empty_and_size_mismatch_rejected(self):
        self.assertNotEqual(self.compare([], []), 0)
        self.assertNotEqual(self.compare([0, 0, 0, 1], [0, 0, 0, 1] * 2), 0)

    def test_partial_rgba_and_trailing_byte_rejected(self):
        self.assertNotEqual(self.compare([0, 0, 0], [0, 0, 0]), 0)
        self.compare([0, 0, 0, 1], [0, 0, 0, 1])
        for name in ("a.f32", "b.f32"):
            with (self.root / name).open("ab") as output:
                output.write(b"x")
        self.assertNotEqual(subprocess.run([str(self.binary), str(self.root / "a.f32"),
                                            str(self.root / "b.f32"), "linear"]).returncode, 0)

    def test_unknown_encoding_rejected(self):
        self.assertNotEqual(self.compare([0, 0, 0, 1], [0, 0, 0, 1], "unknown"), 0)


if __name__ == "__main__":
    unittest.main()
