import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

from archive import Archive

KNOTS = [(0, 0), ('1/2', '1/4'), (1, 1)]


class PublicationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'meter.sqlite'

    def counts(self):
        with closing(sqlite3.connect(self.path)) as connection:
            reports = connection.execute('SELECT count(*) FROM reports').fetchone()[0]
            rows = connection.execute('SELECT count(*) FROM report_contributions').fetchone()[0]
        return reports, rows

    def test_write_failure_rolls_back(self):
        with Archive(self.path) as archive:
            archive.register_curve('probe', 'A', 'B', KNOTS)
            revision = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            with closing(sqlite3.connect(self.path)) as connection, connection:
                connection.execute('''
                    CREATE TRIGGER stop_second_item BEFORE INSERT ON report_contributions
                    WHEN NEW.report_id = 'sheet' AND NEW.ordinal = 1
                    BEGIN
                        SELECT RAISE(ABORT, 'second contribution rejected');
                    END
                ''')
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'second contribution rejected'):
                archive.build_report('sheet', revision, 'probe', 'B', (0, 1))
            with self.assertRaises(KeyError):
                archive.read_report('sheet')
            self.assertEqual(self.counts(), (0, 0))
        with Archive(self.path) as archive:
            with self.assertRaises(KeyError):
                archive.read_report('sheet')
            self.assertEqual(self.counts(), (0, 0))
            with closing(sqlite3.connect(self.path)) as connection, connection:
                connection.execute('DROP TRIGGER stop_second_item')
            report = archive.build_report('sheet', revision, 'probe', 'B', (0, 1))
            self.assertEqual(report.binding.revision, revision)
            self.assertEqual((report.coverage, report.total), (1, F(3, 8)))
            self.assertEqual([item.integral for item in report.contributions], [F(1, 16), F(5, 16)])
            self.assertEqual(archive.read_report('sheet'), report)
            self.assertEqual(self.counts(), (1, 2))

    def test_binding_replay(self):
        with Archive(self.path) as archive:
            archive.register_curve('probe', 'A', 'B', KNOTS)
            archive.register_curve('alternate', 'A', 'B', KNOTS)
            old = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            new = archive.put_batch('day', 'A', [(0, 0), (1, 0)])
            another_batch = archive.put_batch('second', 'A', [(0, 0), (1, 1)])
            request = ('sheet', old, 'probe', 'B', (0, 1))
            report = archive.build_report(*request)
            for changed in (
                (old, 'probe', 'B', (0, 2)),
                (old, 'alternate', 'B', (0, 1)),
                (old, 'probe', 'C', (0, 1)),
                (new, 'probe', 'B', (0, 1)),
                (another_batch, 'probe', 'B', (0, 1)),
            ):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    archive.build_report('sheet', *changed)
            self.assertEqual(archive.build_report(*request), report)
            self.assertEqual(archive.read_report('sheet'), report)
            self.assertEqual(self.counts(), (1, 2))

    def test_reopen_after_correction(self):
        with Archive(self.path) as archive:
            archive.register_curve('probe', 'A', 'B', KNOTS)
            old = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            old_report = archive.build_report('old', old, 'probe', 'B', (0, 1))
            old_json = archive.export_report('old')
            new = archive.put_batch('day', 'A', [(0, 0), (1, 0)])
            new_report = archive.build_report('new', new, 'probe', 'B', (0, 1))
            new_json = archive.export_report('new')
        with Archive(self.path) as archive:
            self.assertEqual(archive.read_report('old'), old_report)
            self.assertEqual(archive.read_report('new'), new_report)
            self.assertEqual(archive.export_report('old'), old_json)
            self.assertEqual(archive.export_report('new'), new_json)
            self.assertEqual(archive.get_current_revision('day').ref, new)
            self.assertEqual(old_report.binding.revision, old)
            self.assertEqual(new_report.binding.revision, new)
            self.assertEqual((old_report.total, new_report.total), (F(3, 8), 0))
            self.assertEqual(json.loads(old_json)['total'], [3, 8])
            self.assertEqual(json.loads(new_json)['total'], [0, 1])
            changed_item = replace(old_report.contributions[0], integral=F(99))
            changed = replace(old_report, contributions=(changed_item,), total=F(99))
            self.assertNotEqual(changed, archive.read_report('old'))
            self.assertEqual(archive.read_report('old'), old_report)

    def test_pinned_revision_after_correction(self):
        with Archive(self.path) as archive:
            archive.register_curve('probe', 'A', 'B', KNOTS)
            old = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            new = archive.put_batch('day', 'A', [(0, 0), (1, 0)])
            archive.build_report('old', old, 'probe', 'B', (0, 1))
            archive.build_report('new', new, 'probe', 'B', (0, 1))
        with Archive(self.path) as archive:
            old_report = archive.read_report('old')
            new_report = archive.read_report('new')
            self.assertEqual((old_report.binding.revision, new_report.binding.revision), (old, new))
            self.assertEqual([item.samples[-1].reading for item in old_report.contributions], [1, 1])
            self.assertEqual([item.samples[-1].reading for item in new_report.contributions], [0])
            self.assertEqual([item.integral for item in old_report.contributions], [F(1, 16), F(5, 16)])
            self.assertEqual((old_report.total, new_report.total), (F(3, 8), 0))
            self.assertEqual(json.loads(archive.export_report('old'))['total'], [3, 8])
            self.assertEqual(json.loads(archive.export_report('new'))['total'], [0, 1])

    def test_reinitialize_keeps_user_data(self):
        with Archive(self.path) as archive:
            curve = archive.register_curve('field-device', 'A', 'B', KNOTS)
            old = archive.put_batch('my-data', 'A', [(0, 0), (2, 1)])
            first = archive.build_report('first', old, 'field-device', 'B', (0, 2))
            new = archive.put_batch('my-data', 'A', [(0, 0), (2, 0)])
            second = archive.build_report('second', new, 'field-device', 'B', (0, 2))
            revisions = (archive.get_revision(old), archive.get_revision(new))
            exports = (archive.export_report('first'), archive.export_report('second'))
        with Archive(self.path) as archive:
            archive.initialize()
            archive.initialize()
            self.assertEqual(archive.get_curve('field-device'), curve)
            self.assertEqual((archive.get_revision(old), archive.get_revision(new)), revisions)
            self.assertEqual(archive.get_current_revision('my-data'), revisions[1])
            self.assertEqual((archive.read_report('first'), archive.read_report('second')), (first, second))
            self.assertEqual((archive.export_report('first'), archive.export_report('second')), exports)
            self.assertEqual((first.total, second.total), (F(3, 4), 0))
            self.assertEqual(self.counts(), (2, 3))
