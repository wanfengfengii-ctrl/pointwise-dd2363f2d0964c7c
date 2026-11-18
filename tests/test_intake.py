import unittest
from fractions import Fraction as F

from archive import Archive, RevisionRef

KNOTS = [(0, 0), ('1/2', '1/4'), (1, 1)]


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.archive = Archive()
        self.addCleanup(self.archive.close)

    def test_fixed_direct_curve_and_batch(self):
        knots = [list(pair) for pair in KNOTS]
        curve = self.archive.register_curve('probe', 'A', 'B', knots)
        knots[1][1] = '3/4'
        self.assertEqual(self.archive.register_curve('probe', 'A', 'B', [
            (0, 0), (F(2, 4), F(2, 8)), (1, 1),
        ]), curve)
        self.assertEqual(self.archive.get_curve('probe').knots, ((0, 0), (F(1, 2), F(1, 4)), (1, 1)))
        original = [[0, '0'], [1, '1']]
        ref = self.archive.put_batch('day', 'A', original)
        original[1][1] = '0'
        self.assertEqual(ref, RevisionRef('day', 1))
        fixed = self.archive.get_revision(ref)
        self.assertEqual((fixed.ref, fixed.scale), (ref, 'A'))
        self.assertEqual([(p.time_s, p.reading) for p in fixed.series.samples], [(0, 0), (1, 1)])
        self.assertEqual(self.archive.get_current_revision('day'), fixed)
        with self.assertRaises(KeyError):
            self.archive.get_curve('missing')
        with self.assertRaises(KeyError):
            self.archive.get_current_revision('missing')

    def test_curve_identity_conflict(self):
        curve = self.archive.register_curve('probe', 'A', 'B', KNOTS)
        for source, target, knots in (
            ('A', 'B', [(0, 0), (1, 1)]),
            ('B', 'A', KNOTS),
        ):
            with self.subTest(source=source, knots=knots), self.assertRaises(ValueError):
                self.archive.register_curve('probe', source, target, knots)
        self.assertEqual(self.archive.get_curve('probe'), curve)
        self.assertEqual(self.archive.register_curve('probe', 'A', 'B', KNOTS), curve)

    def test_reject_noninvertible_curve(self):
        with self.assertRaises(ValueError):
            self.archive.register_curve('probe', 'A', 'B', [(0, 0), ('1/2', 0), (1, 1)])
        with self.assertRaises(KeyError):
            self.archive.get_curve('probe')
        self.assertEqual(self.archive.register_curve('probe', 'A', 'B', KNOTS).knots[1], (F(1, 2), F(1, 4)))

    def test_reject_invalid_curve_geometry_and_scales(self):
        cases = (
            ('A', 'A', KNOTS),
            ('A', 'B', [(0, 0), (0, '1/4'), (1, 1)]),
            ('A', 'B', [(0, 0), ('1/2', '3/4'), ('3/4', '1/2'), (1, 1)]),
            ('A', 'B', [(0, 0), (1, '3/4')]),
        )
        for source, target, knots in cases:
            with self.subTest(knots=knots, target=target), self.assertRaises(ValueError):
                self.archive.register_curve('probe', source, target, knots)
        with self.assertRaises(KeyError):
            self.archive.get_curve('probe')

    def test_bad_correction_keeps_head(self):
        ref = self.archive.put_batch('day', 'A', [(0, 0), (1, 1)])
        previous = self.archive.get_revision(ref)
        with self.assertRaises(ValueError):
            self.archive.put_batch('day', 'A', [(1, 0), (1, 1)])
        self.assertEqual(self.archive.get_current_revision('day'), previous)
        self.assertEqual(self.archive.get_revision(ref), previous)
        with self.assertRaises(KeyError):
            self.archive.get_revision(RevisionRef('day', 2))

    def test_reject_invalid_payload(self):
        ref = self.archive.put_batch('day', 'A', [(0, 0), (1, 1)])
        before = self.archive.get_revision(ref)
        cases = (
            [(0, 0)], [(0, 0), (1, None)], [(0, 0), (1,)], [(0, 0), (1, '4/3')],
            [(0, '-1/3'), (1, 1)], [(1, 0), (0, 1)], [(0, 0), ('1', 1)],
            [(False, 0), (1, 1)], [(0, 0), (1, 0.5)],
        )
        for samples in cases:
            with self.subTest(samples=samples):
                with self.assertRaises(ValueError):
                    self.archive.put_batch('day', 'B', samples)
                self.assertEqual(self.archive.get_current_revision('day'), before)
                self.assertEqual(self.archive.get_revision(ref), before)
        next_ref = self.archive.put_batch('day', 'B', [(0, 0), (1, 1)])
        self.assertEqual(next_ref, RevisionRef('day', 2))
        self.assertEqual(self.archive.get_current_revision('day').scale, 'B')
        self.assertEqual(self.archive.get_revision(ref).scale, 'A')
        again = self.archive.put_batch('day', 'B', [(0, 0), (1, 1)])
        self.assertEqual(again, RevisionRef('day', 3))
