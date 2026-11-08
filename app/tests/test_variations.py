import unittest

from lib.core.variations import build_variations

# Plain numbers stand in for audio tensors: variations only rely on `+`.
STEMS = {'drums': 1.0, 'bass': 10.0, 'other': 100.0, 'vocals': 1000.0}


class TestVariations(unittest.TestCase):

    def test_op_mini(self):
        variations = build_variations(STEMS, list(STEMS), 'op_mini')
        self.assertEqual(variations, STEMS)

    def test_op_full_adds_complements(self):
        variations = build_variations(STEMS, ['bass', 'vocals'], 'op_full')
        self.assertEqual(variations, {
            'bass': 10.0,
            'vocals': 1000.0,
            'no_bass': 1101.0,
            'no_vocals': 111.0,
        })

    def test_op_extra_adds_pairs(self):
        variations = build_variations(STEMS, list(STEMS), 'op_extra')
        self.assertEqual(len(variations), 4 + 4 + 6)
        self.assertEqual(variations['drums_bass'], 11.0)
        self.assertEqual(variations['other_vocals'], 1100.0)
        self.assertEqual(variations['no_drums'], 1110.0)

    def test_complement_uses_all_stems(self):
        # "no_bass" is the whole mix minus bass, even when only bass is selected.
        variations = build_variations(STEMS, ['bass'], 'op_extra')
        self.assertEqual(variations, {'bass': 10.0, 'no_bass': 1101.0})

    def test_unknown_track(self):
        with self.assertRaises(ValueError):
            build_variations(STEMS, ['guitar'], 'op_mini')

    def test_unknown_operation(self):
        with self.assertRaises(ValueError):
            build_variations(STEMS, ['bass'], 'op_mega')


if __name__ == '__main__':
    unittest.main()
