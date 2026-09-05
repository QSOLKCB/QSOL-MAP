import unittest

from qsol_map.canonical import CanonicalizationError, canonical_bytes, domain_sha256


class CanonicalTests(unittest.TestCase):
    def test_key_order_is_canonical(self):
        self.assertEqual(canonical_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}')

    def test_float_rejected(self):
        with self.assertRaises(CanonicalizationError):
            canonical_bytes({"x": 1.25})

    def test_large_integer_requires_string(self):
        with self.assertRaises(CanonicalizationError):
            canonical_bytes({"x": 1 << 60})
        self.assertEqual(canonical_bytes({"x": str(1 << 60)}), b'{"x":"1152921504606846976"}')

    def test_domain_separation(self):
        payload = b"same"
        self.assertNotEqual(domain_sha256("A", payload), domain_sha256("B", payload))


if __name__ == "__main__":
    unittest.main()
