import unittest
from fractions import Fraction as F

from archive import Archive, RevisionRef


class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.archive = Archive()
        self.addCleanup(self.archive.close)
        self.archive.register_curve('probe', 'A', 'B', [(0, 0), ('1/2', '1/4'), (1, 1)])

    def book(self, samples, window=(0, 1), source='A', target='B', report_id='sheet'):
        revision = self.archive.put_batch('day', source, samples)
        return self.archive.build_report(report_id, revision, 'probe', target, window)

    def assert_ledger(self, report, expected, coverage, total, direction):
        self.assertEqual(
            [(item.start, item.end, item.segment_index, item.integral) for item in report.contributions],
            expected,
        )
        self.assertEqual((report.coverage, report.total), (coverage, total))
        self.assertTrue(all(item.direction == direction for item in report.contributions))
        self.assertTrue(all(isinstance(item.integral, F) for item in report.contributions))

    def test_direct_knot_exact_integral(self):
        report = self.book([(0, 0), (1, 1)])
        self.assert_ledger(report, [(0, F(1, 2), 0, F(1, 16)), (F(1, 2), 1, 1, F(5, 16))],
                           1, F(3, 8), 'forward')
        self.assertEqual(report.binding.revision, RevisionRef('day', 1))
        self.assertEqual(report.binding.window, (0, 1))
        self.assertEqual((report.source, report.binding.target), ('A', 'B'))
        self.assertEqual([item.curve_id for item in report.contributions], ['probe', 'probe'])
        self.assertEqual(report.contributions[0].knots, ((0, 0), (F(1, 2), F(1, 4))))
        self.assertEqual(self.archive.read_report('sheet'), report)

    def test_clipped_pair(self):
        report = self.book([(0, 0), (4, 1)], (1, 3))
        self.assert_ledger(report, [(1, 2, 0, F(3, 16)), (2, 3, 1, F(7, 16))],
                           2, F(5, 8), 'forward')
        for item in report.contributions:
            self.assertEqual([(p.time_s, p.reading) for p in item.samples], [(0, 0), (4, 1)])

    def test_empty_window(self):
        revision = self.archive.put_batch('day', 'A', [(0, 0), (1, 1)])
        for index, window in enumerate(((0, 0), (2, 3), (1, 4), (-2, 0))):
            with self.subTest(window=window):
                report = self.archive.build_report(f'empty-{index}', revision, 'probe', 'B', window)
                self.assertEqual((report.coverage, report.total, report.contributions), (0, 0, ()))
                self.assertEqual(report.binding.window, window)

    def test_invalid_window(self):
        revision = self.archive.put_batch('day', 'A', [(0, 0), (1, 1)])
        for window in ((1, 0), (0, F(1, 2)), (False, 1), (0,), None):
            with self.subTest(window=window):
                with self.assertRaises(ValueError):
                    self.archive.build_report('sheet', revision, 'probe', 'B', window)
                with self.assertRaises(KeyError):
                    self.archive.read_report('sheet')
        self.assertEqual(self.archive.build_report('sheet', revision, 'probe', 'B', (0, 1)).total, F(3, 8))

    def test_descending_order(self):
        report = self.book([(0, 1), (1, 0)])
        self.assert_ledger(report, [(0, F(1, 2), 1, F(5, 16)), (F(1, 2), 1, 0, F(1, 16))],
                           1, F(3, 8), 'forward')

    def test_knot_ownership(self):
        for index, (reading, expected, segment) in enumerate((
            ('1/2', F(1, 4), 1), (1, F(1), 1), (0, F(0), 0),
        )):
            with self.subTest(reading=reading):
                report = self.book([(0, reading), (1, reading)], report_id=f'constant-{index}')
                self.assert_ledger(report, [(0, 1, segment, expected)], 1, expected, 'forward')
        reverse = self.book([(0, '1/4'), (1, '1/4')], source='B', target='A', report_id='reverse-knot')
        self.assert_ledger(reverse, [(0, 1, 1, F(1, 2))], 1, F(1, 2), 'reverse')
        endpoint = self.book([(0, 0), (1, '1/2')], report_id='endpoint')
        self.assert_ledger(endpoint, [(0, 1, 0, F(1, 8))], 1, F(1, 8), 'forward')

    def test_original_pairs_survive_shared_endpoint(self):
        report = self.book([(0, 0), (2, '1/2'), (4, 1)], (1, 3))
        self.assert_ledger(report, [(1, 2, 0, F(3, 16)), (2, 3, 1, F(7, 16))],
                           2, F(5, 8), 'forward')
        self.assertEqual([[p.time_s for p in part.samples] for part in report.contributions], [[0, 2], [2, 4]])

    def test_collinear_original_knot_is_still_evidence(self):
        self.archive.register_curve('identity', 'A', 'B', [(0, 0), ('1/2', '1/2'), (1, 1)])
        revision = self.archive.put_batch('day', 'A', [(0, 0), (1, 1)])
        report = self.archive.build_report('sheet', revision, 'identity', 'B', (0, 1))
        self.assert_ledger(report, [(0, F(1, 2), 0, F(1, 8)), (F(1, 2), 1, 1, F(3, 8))],
                           1, F(1, 2), 'forward')

    def test_wrong_scale_has_no_report(self):
        revision = self.archive.put_batch('day', 'C', [(0, 0), (1, 1)])
        with self.assertRaises(ValueError):
            self.archive.build_report('sheet', revision, 'probe', 'B', (0, 1))
        with self.assertRaises(KeyError):
            self.archive.read_report('sheet')

    def test_missing_reference(self):
        revision = self.archive.put_batch('day', 'A', [(0, 0), (1, 1)])
        for ref, curve in ((RevisionRef('day', 99), 'probe'), (revision, 'missing')):
            with self.subTest(ref=ref, curve=curve):
                with self.assertRaises(KeyError):
                    self.archive.build_report('sheet', ref, curve, 'B', (0, 0))
                with self.assertRaises(KeyError):
                    self.archive.read_report('sheet')
        self.assertEqual(self.archive.build_report('sheet', revision, 'probe', 'B', (0, 1)).total, F(3, 8))

    def test_target_mismatch(self):
        revision = self.archive.put_batch('day', 'A', [(0, 0), (1, 1)])
        for target in ('C', 'A'):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    self.archive.build_report('sheet', revision, 'probe', target, (0, 0))
                with self.assertRaises(KeyError):
                    self.archive.read_report('sheet')
        self.assertEqual(self.archive.build_report('sheet', revision, 'probe', 'B', (0, 1)).total, F(3, 8))

    def test_inverse_direct_curve(self):
        report = self.book([(0, 0), (1, 1)], source='B', target='A')
        self.assert_ledger(report, [(0, F(1, 4), 0, F(1, 16)), (F(1, 4), 1, 1, F(9, 16))],
                           1, F(5, 8), 'reverse')
        self.assertEqual(report.contributions[1].knots, ((F(1, 2), F(1, 4)), (1, 1)))

    def test_reverse_descending_window(self):
        report = self.book([(0, 1), (8, 0)], (1, 7), source='B', target='A')
        self.assert_ledger(report, [(1, 6, 1, F(85, 24)), (6, 7, 0, F(3, 8))],
                           6, F(47, 12), 'reverse')
        for item in report.contributions:
            self.assertEqual([(p.time_s, p.reading) for p in item.samples], [(0, 1), (8, 0)])
        self.assertEqual(self.archive.read_report('sheet'), report)
