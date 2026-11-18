import sqlite3
from fractions import Fraction

from clocks.frozen import ClockReportBinding
from clocks.payload import clock_summary, ratio
from clocks.records import load_clock
from processing.contributions import Contribution, ContributionLedger


def ensure_clock_report_schema(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS clock_reports (
            report_id TEXT PRIMARY KEY NOT NULL,
            clock_id TEXT NOT NULL REFERENCES clocks(clock_id),
            curve_id TEXT NOT NULL REFERENCES curves(curve_id),
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            coverage TEXT NOT NULL,
            total TEXT NOT NULL
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS clock_report_contributions (
            report_id TEXT NOT NULL REFERENCES clock_reports(report_id),
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


def insert_clock_report(connection: sqlite3.Connection, report_id: str,
                        binding: ClockReportBinding, source: str,
                        ledger: ContributionLedger) -> None:
    connection.execute('''
        INSERT INTO clock_reports (
            report_id, clock_id, curve_id, source, target,
            window_start, window_end, coverage, total
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        report_id, binding.clock_id, binding.curve_id, source, binding.target,
        str(binding.window[0]), str(binding.window[1]),
        str(ledger.coverage), str(ledger.total),
    ))
    connection.executemany('''
        INSERT INTO clock_report_contributions (
            report_id, ordinal, start_s, end_s,
            sample_start_s, sample_start_reading, sample_end_s, sample_end_reading,
            direction, segment_index, knot_start_x, knot_start_y, knot_end_x, knot_end_y,
            integral
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        _contribution_row(report_id, ordinal, item)
        for ordinal, item in enumerate(ledger.contributions)
    ))


def load_clock_report_binding(connection: sqlite3.Connection,
                              report_id: str) -> ClockReportBinding | None:
    row = connection.execute('''
        SELECT clock_id, curve_id, target, window_start, window_end
        FROM clock_reports WHERE report_id = ?
    ''', (report_id,)).fetchone()
    if row is None:
        return None
    clock_id, curve_id, target, start, end = row
    return ClockReportBinding(clock_id, curve_id, target, (int(start), int(end)))


def _decode_contribution(curve_id: str, row: tuple) -> dict:
    start, end, t0, v0, t1, v1, direction, segment, x0, y0, x1, y1, integral = row
    return {
        'start_s': ratio(Fraction(start)),
        'end_s': ratio(Fraction(end)),
        'samples': [
            {'time_s': int(t0), 'reading': ratio(Fraction(v0))},
            {'time_s': int(t1), 'reading': ratio(Fraction(v1))},
        ],
        'curve_id': curve_id,
        'direction': direction,
        'segment_index': segment,
        'knots': [
            [ratio(Fraction(x0)), ratio(Fraction(y0))],
            [ratio(Fraction(x1)), ratio(Fraction(y1))],
        ],
        'integral': ratio(Fraction(integral)),
    }


def load_clock_report(connection: sqlite3.Connection, report_id: str) -> dict | None:
    header = connection.execute('''
        SELECT clock_id, curve_id, source, target, window_start, window_end, coverage, total
        FROM clock_reports WHERE report_id = ?
    ''', (report_id,)).fetchone()
    if header is None:
        return None
    clock_id, curve_id, source, target, start, end, coverage, total = header
    registration = load_clock(connection, clock_id)
    contributions = [
        _decode_contribution(curve_id, row)
        for row in connection.execute('''
            SELECT start_s, end_s, sample_start_s, sample_start_reading, sample_end_s,
                   sample_end_reading, direction, segment_index, knot_start_x, knot_start_y,
                   knot_end_x, knot_end_y, integral
            FROM clock_report_contributions WHERE report_id = ? ORDER BY ordinal
        ''', (report_id,))
    ]
    return {
        'format_version': 2,
        'report_id': report_id,
        'binding': {
            'batch_id': registration.binding.revision.batch_id,
            'revision': registration.binding.revision.number,
            'curve_id': curve_id,
            'source': source,
            'target': target,
            'window': [int(start), int(end)],
        },
        'coverage': ratio(Fraction(coverage)),
        'total': ratio(Fraction(total)),
        'contributions': contributions,
        'clock': clock_summary(registration),
    }
