import json
import unittest
from fractions import Fraction as F

from archive import Archive


def offline_integral(item):
    first, last = item['samples']
    sample_low = F(*first['reading'])
    sample_high = F(*last['reading'])
    reading_slope = (sample_high - sample_low) / (last['time_s'] - first['time_s'])
    (x0, y0), (x1, y1) = tuple(tuple(F(*coordinate) for coordinate in pair) for pair in item['knots'])
    if item['direction'] == 'reverse':
        x0, y0, x1, y1 = y0, x0, y1, x1
    start, end = F(*item['start_s']), F(*item['end_s'])
    mean_reading = sample_low + reading_slope * ((start + end) / 2 - first['time_s'])
    mean_output = y0 + (y1 - y0) / (x1 - x0) * (mean_reading - x0)
    return (end - start) * mean_output


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.archive = Archive()
        self.addCleanup(self.archive.close)
        self.archive.register_curve('probe', 'A', 'B', [(0, 0), ('1/2', '1/4'), (1, 1)])
        self.ref = self.archive.put_batch('day', 'A', [(0, 0), (1, 1)])
        self.report = self.archive.build_report('sheet', self.ref, 'probe', 'B', (0, 1))

    def assert_offline_ledger(self, exported, expected_coverage, expected_total):
        payload = json.loads(exported)
        self.assertEqual(payload['format_version'], 1)
        cursor = None
        coverage, total = F(0), F(0)
        for item in payload['contributions']:
            start, end = F(*item['start_s']), F(*item['end_s'])
            self.assertLess(start, end)
            if cursor is not None:
                self.assertEqual(start, cursor)
            cursor = end
            reconstructed = offline_integral(item)
            self.assertEqual(reconstructed, F(*item['integral']))
            coverage += end - start
            total += reconstructed
        self.assertEqual((coverage, total), (expected_coverage, expected_total))
        self.assertEqual(coverage, F(*payload['coverage']))
        self.assertEqual(total, F(*payload['total']))
        return payload

    def test_review_and_export(self):
        approved = self.archive.assess_report('sheet', 1, '3/8', '3/8')
        self.assertTrue(approved.passed)
        self.assertEqual(approved.findings, ())
        self.assertEqual((approved.coverage.actual, approved.total), (1, F(3, 8)))
        insufficient = self.archive.assess_report('sheet', 2, '3/8', '3/8')
        self.assertFalse(insufficient.passed)
        finding, = insufficient.findings
        self.assertEqual((finding.code, finding.actual, finding.threshold), ('coverage_insufficient', 1, 2))
        self.assertEqual(finding.contributions, self.report.contributions)
        payload = self.assert_offline_ledger(self.archive.export_report('sheet'), 1, F(3, 8))
        self.assertEqual(payload['binding'], {
            'batch_id': 'day', 'revision': 1, 'curve_id': 'probe', 'source': 'A', 'target': 'B',
            'window': [0, 1],
        })
        self.assertEqual(self.archive.read_report('sheet'), self.report)

    def test_empty_coverage(self):
        report = self.archive.build_report('empty', self.ref, 'probe', 'B', (2, 3))
        self.assertEqual((report.coverage, report.total, report.contributions), (0, 0, ()))
        self.assertTrue(self.archive.assess_report('empty', 0, 0, 0).passed)
        failed = self.archive.assess_report('empty', 1, 0, 0)
        finding, = failed.findings
        self.assertFalse(failed.passed)
        self.assertEqual((finding.code, finding.actual, finding.threshold, finding.contributions),
                         ('coverage_insufficient', 0, 1, ()))
        self.assert_offline_ledger(self.archive.export_report('empty'), 0, 0)

    def test_limit_reasons(self):
        low = self.archive.assess_report('sheet', 1, '1/2', 1)
        finding, = low.findings
        self.assertEqual((finding.code, finding.actual, finding.threshold),
                         ('integral_below_minimum', F(3, 8), F(1, 2)))
        high = self.archive.assess_report('sheet', 1, 0, '1/4')
        finding, = high.findings
        self.assertEqual((finding.code, finding.actual, finding.threshold),
                         ('integral_above_maximum', F(3, 8), F(1, 4)))
        combined = self.archive.assess_report('sheet', 2, 0, '1/4')
        self.assertFalse(combined.passed)
        self.assertEqual([item.code for item in combined.findings],
                         ['coverage_insufficient', 'integral_above_maximum'])
        for item in combined.findings:
            self.assertEqual(item.contributions, self.report.contributions)
            self.assertEqual([row.start for row in item.contributions], [0, F(1, 2)])
        self.assertEqual(self.archive.read_report('sheet'), self.report)

    def test_invalid_limits(self):
        for limits in ((-1, 0, 1), (0, 1, 0), (0, None, 1), (0, 0, 0.5)):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                self.archive.assess_report('sheet', *limits)
        self.assertEqual(self.archive.read_report('sheet'), self.report)

    def test_missing_report(self):
        with self.assertRaises(KeyError):
            self.archive.assess_report('missing', 0, 0, 1)
        with self.assertRaises(KeyError):
            self.archive.export_report('missing')
        with self.assertRaises(KeyError):
            self.archive.read_report('missing')

    def test_exact_json(self):
        ref = self.archive.put_batch('constant', 'A', [(0, '1/3'), (1, '1/3')])
        self.archive.build_report('constant', ref, 'probe', 'B', (0, 1))
        self.assertTrue(self.archive.assess_report('constant', 1, '1/6', '1/6').passed)
        exported = self.archive.export_report('constant')
        self.assertEqual(exported, self.archive.export_report('constant'))
        self.archive.close()
        payload = self.assert_offline_ledger(exported, 1, F(1, 6))
        self.assertEqual(payload['total'], [1, 6])
        item, = payload['contributions']
        self.assertEqual(item['integral'], [1, 6])
        self.assertEqual([sample['reading'] for sample in item['samples']], [[1, 3], [1, 3]])

    def test_reverse_offline_reconstruction(self):
        ref = self.archive.put_batch('reverse', 'B', [(0, 1), (8, 0)])
        self.archive.build_report('reverse', ref, 'probe', 'A', (1, 7))
        exported = self.archive.export_report('reverse')
        payload = self.assert_offline_ledger(exported, 6, F(47, 12))
        self.assertEqual([(row['direction'], row['segment_index']) for row in payload['contributions']],
                         [('reverse', 1), ('reverse', 0)])
