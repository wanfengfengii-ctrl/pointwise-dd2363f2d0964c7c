import sqlite3
from dataclasses import dataclass
from fractions import Fraction

from observations.revisions import RevisionRef
from observations.series import Sample
from processing.contributions import Contribution
from reports.bindings import ReportBinding


@dataclass(frozen=True, slots=True)
class ReportSnapshot:
    report_id: str
    binding: ReportBinding
    source: str
    coverage: Fraction
    total: Fraction
    contributions: tuple[Contribution, ...]


def ensure_report_schema(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id TEXT PRIMARY KEY NOT NULL,
            batch_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            curve_id TEXT NOT NULL REFERENCES curves(curve_id),
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            coverage TEXT NOT NULL,
            total TEXT NOT NULL,
            FOREIGN KEY (batch_id, revision) REFERENCES batch_revisions (batch_id, revision)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS report_contributions (
            report_id TEXT NOT NULL REFERENCES reports(report_id),
            ordinal INTEGER NOT NULL,
            start_s TEXT NOT NULL,
            end_s TEXT NOT NULL,
            sample_start_s TEXT NOT NULL,
            sample_start_reading TEXT NOT NULL,
            sample_end_s TEXT NOT NULL,
            sample_end_reading TEXT NOT NULL,
            direction TEXT NOT NULL CHECK (direction IN ('forward', 'reverse')),
            segment_index INTEGER NOT NULL CHECK (segment_index >= 0),
            knot_start_x TEXT NOT NULL,
            knot_start_y TEXT NOT NULL,
            knot_end_x TEXT NOT NULL,
            knot_end_y TEXT NOT NULL,
            integral TEXT NOT NULL,
            PRIMARY KEY (report_id, ordinal)
        )
    ''')


def _contribution_row(report_id: str, ordinal: int, item: Contribution) -> tuple:
    first, last = item.samples
    (x0, y0), (x1, y1) = item.knots
    return (
        report_id, ordinal, str(item.start), str(item.end),
        str(first.time_s), str(first.reading), str(last.time_s), str(last.reading),
        item.direction, item.segment_index, str(x0), str(y0), str(x1), str(y1),
        str(item.integral),
    )


def insert_report(connection: sqlite3.Connection, report: ReportSnapshot) -> None:
    binding = report.binding
    connection.execute('''
        INSERT INTO reports (
            report_id, batch_id, revision, curve_id, source, target,
            window_start, window_end, coverage, total
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        report.report_id, binding.revision.batch_id, binding.revision.number,
        binding.curve_id, report.source, binding.target, str(binding.window[0]),
        str(binding.window[1]), str(report.coverage), str(report.total),
    ))
    connection.executemany('''
        INSERT INTO report_contributions (
            report_id, ordinal, start_s, end_s,
            sample_start_s, sample_start_reading, sample_end_s, sample_end_reading,
            direction, segment_index, knot_start_x, knot_start_y, knot_end_x, knot_end_y,
            integral
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (_contribution_row(report.report_id, i, item) for i, item in enumerate(report.contributions)))


def _restore_contribution(curve_id: str, row: tuple) -> Contribution:
    start, end, t0, v0, t1, v1, direction, segment, x0, y0, x1, y1, integral = row
    samples = (Sample(int(t0), Fraction(v0)), Sample(int(t1), Fraction(v1)))
    knots = ((Fraction(x0), Fraction(y0)), (Fraction(x1), Fraction(y1)))
    return Contribution(
        Fraction(start), Fraction(end), samples, curve_id, direction, segment, knots,
        Fraction(integral),
    )


def load_report(connection: sqlite3.Connection, report_id: str) -> ReportSnapshot | None:
    header = connection.execute('''
        SELECT batch_id, revision, curve_id, source, target, window_start, window_end,
               coverage, total
        FROM reports WHERE report_id = ?
    ''', (report_id,)).fetchone()
    if header is None:
        return None
    batch_id, revision, curve_id, source, target, start, end, coverage, total = header
    binding = ReportBinding(RevisionRef(batch_id, revision), curve_id, target, (int(start), int(end)))
    rows = connection.execute('''
        SELECT start_s, end_s, sample_start_s, sample_start_reading, sample_end_s,
               sample_end_reading, direction, segment_index, knot_start_x, knot_start_y,
               knot_end_x, knot_end_y, integral
        FROM report_contributions WHERE report_id = ? ORDER BY ordinal
    ''', (report_id,))
    contributions = tuple(_restore_contribution(curve_id, row) for row in rows)
    return ReportSnapshot(report_id, binding, source, Fraction(coverage), Fraction(total), contributions)
