import unittest

from scripts.open_vocab_detect import canonical_class, chunked


class OpenVocabDetectTest(unittest.TestCase):
    def test_chunked_preserves_order(self):
        self.assertEqual(list(chunked([1, 2, 3, 4, 5], 2)), [[1, 2], [3, 4], [5]])

    def test_chunked_rejects_non_positive_size(self):
        with self.assertRaises(ValueError):
            list(chunked([1], 0))

    def test_electric_vocabulary_maps_to_project_class(self):
        self.assertEqual(canonical_class("electric scooter"), "electric_bicycle")
        self.assertEqual(canonical_class("electric bicycle"), "electric_bicycle")
        self.assertEqual(canonical_class("motorcycle"), "motorcycle")


if __name__ == "__main__":
    unittest.main()
