import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from fractions import Fraction as F
from pathlib import Path

from archive import Archive, RevisionRef

KNOTS = [(0, 0), ('1/2', '1/4'), (1, 1)]
DEVICE = ((1, 'left'), (3, 'right'))
REFERENCE = ((2, 'left'), (5, 'right'))
FIT = {
    'clock_id': 'fit',
    'batch_id': 'morning-tide',
    'revision': 1,
    'device_log': [[1, 'left'], [3, 'right']],
    'reference_log': [[2, 'left'], [5, 'right']],
    'rate_range': [[1, 1], [2, 1]],
    'rate': [3, 2],
    'offset': [1, 2],
    'matches': [[1, 2, 'left'], [3, 5, 'right']],
}


class ClockRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.archive = Archive()
        self.addCleanup(self.archive.close)
        self.archive.register_curve('probe', 'A', 'B', KNOTS)
        self.revision = self.archive.put_batch('morning-tide', 'A', [(0, 0), (1, 1)])

    def test_register_and_normalized_replay(self):
        clock = self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, (1, 2))
        self.assertEqual(clock, FIT)
        replay = self.archive.register_clock(
            'fit', RevisionRef('morning-tide', 1),
            [[1, 'left'], [3, 'right']], [[2, 'left'], [5, 'right']], ('1', '2'),
        )
        self.assertEqual(replay, FIT)
        self.assertIsNot(replay, clock)

    def test_conflicting_binding_rejected(self):
        self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, (1, 2))
        other_revision = self.archive.put_batch('morning-tide', 'A', [(0, 0), (1, 1)])
        cases = (
            (other_revision, DEVICE, REFERENCE, (1, 2)),
            (self.revision, ((1, 'left'), (4, 'right')), REFERENCE, (1, 2)),
            (self.revision, DEVICE, ((2, 'left'), (6, 'right')), (1, 2)),
            (self.revision, DEVICE, REFERENCE, (1, 3)),
        )
        for changed in cases:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.archive.register_clock('fit', *changed)
        self.assertEqual(
            self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, (1, 2)), FIT,
        )

    def test_invalid_logs_rejected_and_id_not_consumed(self):
        cases = (
            ([[1, 'left'], [1, 'right']], REFERENCE),
            ([[1, 'left'], [0, 'right']], REFERENCE),
            ([[1, ' '], [3, 'right']], REFERENCE),
            ([[1, 5], [3, 'right']], REFERENCE),
            ([[1.0, 'left'], [3, 'right']], REFERENCE),
            ([[True, 'left'], [3, 'right']], REFERENCE),
            ([[1], [3, 'right']], REFERENCE),
            ('not-a-log', REFERENCE),
            (DEVICE, [[2, 'left'], [5, 'right'], [5, 'again']]),
        )
        for device, reference in cases:
            with self.subTest(device=device, reference=reference), self.assertRaises(ValueError):
                self.archive.register_clock('fit', self.revision, device, reference, (1, 2))
        clock = self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, (1, 2))
        self.assertEqual(clock, FIT)

    def test_invalid_rate_range_rejected(self):
        for rate_range in ((0, 1), (-1, 1), (2, 1), (1, 0.5), (True, 1), (1,), None, (1, 2, 3)):
            with self.subTest(rate_range=rate_range), self.assertRaises(ValueError):
                self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, rate_range)
        self.assertEqual(
            self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, (1, 2)), FIT,
        )

    def test_missing_revision_and_bad_ref(self):
        for ref in (RevisionRef('morning-tide', 99), RevisionRef('missing', 1)):
            with self.subTest(ref=ref), self.assertRaises(KeyError):
                self.archive.register_clock('fit', ref, DEVICE, REFERENCE, (1, 2))
        with self.assertRaises(ValueError):
            self.archive.register_clock('fit', 'morning-tide', DEVICE, REFERENCE, (1, 2))
        self.assertEqual(
            self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, (1, 2)), FIT,
        )

    def test_tied_mapping_rejected_then_unique_wins(self):
        device = [[t, 'same'] for t in (0, 1, 2)]
        reference = [[t, 'same'] for t in (10, 11, 12, 20, 21, 22)]
        with self.assertRaises(ValueError):
            self.archive.register_clock('pulse', self.revision, device, reference, (1, 1))
        device.append([3, 'extra'])
        reference.insert(3, [13, 'extra'])
        clock = self.archive.register_clock('pulse', self.revision, device, reference, (1, 1))
        self.assertEqual((clock['rate'], clock['offset']), ([1, 1], [10, 1]))
        self.assertEqual(
            clock['matches'],
            [[0, 10, 'same'], [1, 11, 'same'], [2, 12, 'same'], [3, 13, 'extra']],
        )

    def test_insufficient_matches_rejected(self):
        with self.assertRaises(ValueError):
            self.archive.register_clock('fit', self.revision, [[1, 'left']], [[2, 'left']], (1, 2))
        with self.assertRaises(ValueError):
            self.archive.register_clock(
                'fit', self.revision, DEVICE, [[2, 'left'], [5, 'other']], (1, 2),
            )
        with self.assertRaises(ValueError):
            self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, (2, 3))
        self.assertEqual(
            self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, (1, 2)), FIT,
        )

    def test_input_and_return_mutation_do_not_stick(self):
        device = [[1, 'left'], [3, 'right']]
        reference = [[2, 'left'], [5, 'right']]
        clock = self.archive.register_clock('fit', self.revision, device, reference, (1, 2))
        device[0][1] = 'tampered'
        reference.append([9, 'late'])
        clock['matches'].clear()
        clock['device_log'][0][1] = 'tampered'
        again = self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, (1, 2))
        self.assertEqual(again, FIT)


class ClockReportTests(unittest.TestCase):
    def setUp(self):
        self.archive = Archive()
        self.addCleanup(self.archive.close)
        self.archive.register_curve('probe', 'A', 'B', KNOTS)
        self.revision = self.archive.put_batch('morning-tide', 'A', [(0, 0), (1, 1)])
        self.clock = self.archive.register_clock('fit', self.revision, DEVICE, REFERENCE, (1, 2))

    def test_hand_computed_ledger(self):
        report = self.archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2))
        self.assertEqual(report['format_version'], 2)
        self.assertEqual(report['report_id'], 'sheet')
        self.assertEqual(report['binding'], {
            'batch_id': 'morning-tide', 'revision': 1, 'curve_id': 'probe',
            'source': 'A', 'target': 'B', 'window': [1, 2],
        })
        self.assertEqual(report['clock'], {
            'clock_id': 'fit', 'rate': [3, 2], 'offset': [1, 2],
            'matches': [[1, 2, 'left'], [3, 5, 'right']],
        })
        self.assertEqual(
            [
                (item['start_s'], item['end_s'], item['segment_index'], item['integral'])
                for item in report['contributions']
            ],
            [([1, 1], [5, 4], 0, [5, 96]), ([5, 4], [2, 1], 1, [15, 32])],
        )
        for item in report['contributions']:
            self.assertEqual(
                item['samples'],
                [{'time_s': 0, 'reading': [0, 1]}, {'time_s': 1, 'reading': [1, 1]}],
            )
            self.assertEqual((item['curve_id'], item['direction']), ('probe', 'forward'))
        self.assertEqual((report['coverage'], report['total']), ([1, 1], [25, 48]))
        self.assertEqual(self.archive.read_clock_report('sheet'), report)
        self.assertEqual(json.loads(self.archive.export_clock_report('sheet')), report)

    def test_reverse_direction_uses_reference_seconds(self):
        self.archive.put_batch('tide-b', 'B', [(0, 1), (8, 0)])
        clock = self.archive.register_clock(
            'back', RevisionRef('tide-b', 1), ((0, 'x'), (1, 'y')), ((1, 'x'), (3, 'y')), (1, 3),
        )
        self.assertEqual((clock['rate'], clock['offset']), ([2, 1], [1, 1]))
        report = self.archive.build_clock_report('reverse', 'back', 'probe', 'A', (3, 13))
        item, = report['contributions']
        self.assertEqual(
            (item['start_s'], item['end_s'], item['segment_index'], item['integral']),
            ([3, 1], [13, 1], 1, [85, 12]),
        )
        self.assertEqual(item['direction'], 'reverse')
        self.assertEqual(item['knots'], [[[1, 2], [1, 4]], [[1, 1], [1, 1]]])
        self.assertEqual(
            item['samples'],
            [{'time_s': 0, 'reading': [1, 1]}, {'time_s': 8, 'reading': [0, 1]}],
        )
        self.assertEqual((report['coverage'], report['total']), ([10, 1], [85, 12]))

    def test_empty_windows_deliver_zero_ledger(self):
        for index, window in enumerate(((1, 1), (2, 3), (-5, -2))):
            with self.subTest(window=window):
                report = self.archive.build_clock_report(f'empty-{index}', 'fit', 'probe', 'B', window)
                self.assertEqual(
                    (report['coverage'], report['total'], report['contributions']),
                    ([0, 1], [0, 1], []),
                )
                self.assertEqual(report['binding']['window'], list(window))

    def test_empty_window_still_validates_references_and_direction(self):
        with self.assertRaises(KeyError):
            self.archive.build_clock_report('sheet', 'missing', 'probe', 'B', (2, 2))
        with self.assertRaises(KeyError):
            self.archive.build_clock_report('sheet', 'fit', 'missing', 'B', (2, 2))
        with self.assertRaises(ValueError):
            self.archive.build_clock_report('sheet', 'fit', 'probe', 'A', (2, 2))
        with self.assertRaises(KeyError):
            self.archive.read_clock_report('sheet')

    def test_report_binding_replay_and_conflict(self):
        self.archive.register_clock(
            'other', self.revision, ((0, 'x'), (1, 'y')), ((0, 'x'), (2, 'y')), (1, 2),
        )
        report = self.archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2))
        for changed in (
            ('sheet', 'other', 'probe', 'B', (1, 2)),
            ('sheet', 'fit', 'probe', 'A', (1, 2)),
            ('sheet', 'fit', 'probe', 'B', (1, 3)),
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.archive.build_clock_report(*changed)
        self.assertEqual(self.archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2)), report)

    def test_invalid_window_rejected(self):
        for window in ((2, 1), (0, F(1, 2)), (False, 1), (1,), None):
            with self.subTest(window=window), self.assertRaises(ValueError):
                self.archive.build_clock_report('sheet', 'fit', 'probe', 'B', window)
            with self.assertRaises(KeyError):
                self.archive.read_clock_report('sheet')

    def test_missing_report(self):
        with self.assertRaises(KeyError):
            self.archive.read_clock_report('missing')
        with self.assertRaises(KeyError):
            self.archive.export_clock_report('missing')

    def test_report_id_namespaces_are_independent(self):
        old = self.archive.build_report('sheet', self.revision, 'probe', 'B', (0, 1))
        report = self.archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2))
        self.assertEqual(self.archive.read_report('sheet'), old)
        self.assertEqual(json.loads(self.archive.export_report('sheet'))['format_version'], 1)
        self.assertEqual(self.archive.read_clock_report('sheet'), report)
        self.assertEqual(json.loads(self.archive.export_clock_report('sheet'))['format_version'], 2)

    def test_correction_and_mutation_keep_published_ledger(self):
        report = self.archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2))
        saved = self.archive.export_clock_report('sheet')
        report['contributions'].clear()
        report['clock']['matches'].clear()
        self.archive.put_batch('morning-tide', 'A', [(0, 0), (1, 0)])
        kept = self.archive.read_clock_report('sheet')
        self.assertEqual(len(kept['contributions']), 2)
        self.assertEqual(kept['clock']['matches'], [[1, 2, 'left'], [3, 5, 'right']])
        self.assertEqual(self.archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2)), kept)
        self.assertEqual(self.archive.export_clock_report('sheet'), saved)

    def test_off_library_recomputation(self):
        self.archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2))
        payload = json.loads(self.archive.export_clock_report('sheet'))
        rate = F(*payload['clock']['rate'])
        offset = F(*payload['clock']['offset'])
        coverage = total = F(0)
        cursor = F(1)
        for item in payload['contributions']:
            start, end = F(*item['start_s']), F(*item['end_s'])
            self.assertEqual(start, cursor)
            cursor = end
            first, last = item['samples']
            low = F(*first['reading'])
            slope = (F(*last['reading']) - low) / (last['time_s'] - first['time_s'])
            readings = [
                low + slope * ((boundary - offset) / rate - first['time_s'])
                for boundary in (start, end)
            ]
            (x0, y0), (x1, y1) = [
                [F(*coordinate) for coordinate in knot] for knot in item['knots']
            ]
            if item['direction'] == 'reverse':
                x0, y0, x1, y1 = y0, x0, y1, x1
            heights = [y0 + (y1 - y0) * (reading - x0) / (x1 - x0) for reading in readings]
            recomputed = (end - start) * sum(heights) / 2
            self.assertEqual(recomputed, F(*item['integral']))
            coverage += end - start
            total += recomputed
        self.assertEqual((coverage, total), (1, F(25, 48)))
        self.assertEqual(coverage, F(*payload['coverage']))
        self.assertEqual(total, F(*payload['total']))


class ClockPersistenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'meter.sqlite'

    def counts(self):
        with closing(sqlite3.connect(self.path)) as connection:
            clocks = connection.execute('SELECT count(*) FROM clocks').fetchone()[0]
            reports = connection.execute('SELECT count(*) FROM clock_reports').fetchone()[0]
            rows = connection.execute(
                'SELECT count(*) FROM clock_report_contributions'
            ).fetchone()[0]
        return clocks, reports, rows

    def test_reopen_keeps_clock_and_report(self):
        with Archive(self.path) as archive:
            archive.register_curve('probe', 'A', 'B', KNOTS)
            revision = archive.put_batch('morning-tide', 'A', [(0, 0), (1, 1)])
            old = archive.build_report('sheet', revision, 'probe', 'B', (0, 1))
            clock = archive.register_clock('fit', revision, DEVICE, REFERENCE, (1, 2))
            report = archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2))
            saved = archive.export_clock_report('sheet')
            archive.put_batch('morning-tide', 'A', [(0, 0), (1, 0)])
        with Archive(self.path) as archive:
            archive.initialize()
            self.assertEqual(
                archive.register_clock('fit', RevisionRef('morning-tide', 1), DEVICE, REFERENCE, ('1', '2')),
                clock,
            )
            self.assertEqual(archive.read_clock_report('sheet'), report)
            self.assertEqual(archive.export_clock_report('sheet'), saved)
            self.assertEqual(archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2)), report)
            self.assertEqual(archive.read_report('sheet'), old)
            self.assertEqual(archive.read_report('sheet').total, F(3, 8))

    def test_report_write_failure_rolls_back(self):
        with Archive(self.path) as archive:
            archive.register_curve('probe', 'A', 'B', KNOTS)
            revision = archive.put_batch('morning-tide', 'A', [(0, 0), (1, 1)])
            archive.register_clock('fit', revision, DEVICE, REFERENCE, (1, 2))
            old = archive.build_clock_report('old', 'fit', 'probe', 'B', (1, 2))
            with closing(sqlite3.connect(self.path)) as connection, connection:
                connection.execute('''
                    CREATE TRIGGER stop_clock_item BEFORE INSERT ON clock_report_contributions
                    WHEN NEW.report_id = 'sheet' AND NEW.ordinal = 1
                    BEGIN
                        SELECT RAISE(ABORT, 'second clock contribution rejected');
                    END
                ''')
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'second clock contribution rejected'):
                archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2))
            with self.assertRaises(KeyError):
                archive.read_clock_report('sheet')
            self.assertEqual(self.counts(), (1, 1, 2))
            self.assertEqual(archive.read_clock_report('old'), old)
        with Archive(self.path) as archive:
            with self.assertRaises(KeyError):
                archive.read_clock_report('sheet')
            with closing(sqlite3.connect(self.path)) as connection, connection:
                connection.execute('DROP TRIGGER stop_clock_item')
            report = archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2))
            self.assertEqual((report['coverage'], report['total']), ([1, 1], [25, 48]))
            self.assertEqual(archive.read_clock_report('sheet'), report)
            self.assertEqual(self.counts(), (1, 2, 4))

    def test_registration_write_failure_rolls_back(self):
        with Archive(self.path) as archive:
            archive.register_curve('probe', 'A', 'B', KNOTS)
            revision = archive.put_batch('morning-tide', 'A', [(0, 0), (1, 1)])
            with closing(sqlite3.connect(self.path)) as connection, connection:
                connection.execute('''
                    CREATE TRIGGER stop_clock_match BEFORE INSERT ON clock_matches
                    WHEN NEW.clock_id = 'fit'
                    BEGIN
                        SELECT RAISE(ABORT, 'clock match rejected');
                    END
                ''')
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'clock match rejected'):
                archive.register_clock('fit', revision, DEVICE, REFERENCE, (1, 2))
            with self.assertRaises(KeyError):
                archive.build_clock_report('sheet', 'fit', 'probe', 'B', (1, 2))
            self.assertEqual(self.counts(), (0, 0, 0))
            with closing(sqlite3.connect(self.path)) as connection, connection:
                connection.execute('DROP TRIGGER stop_clock_match')
            clock = archive.register_clock('fit', revision, DEVICE, REFERENCE, (1, 2))
            self.assertEqual(clock, FIT)
            self.assertEqual(self.counts(), (1, 0, 0))
