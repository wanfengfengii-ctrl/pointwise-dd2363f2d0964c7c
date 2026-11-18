import sqlite3

from clocks.frozen import ClockReportBinding
from clocks.storage import (
    insert_clock_report,
    load_clock_report,
    load_clock_report_binding,
)
from processing.contributions import ContributionLedger


def find_clock_replay(connection: sqlite3.Connection, report_id: str,
                      binding: ClockReportBinding) -> dict | None:
    stored = load_clock_report_binding(connection, report_id)
    if stored is None:
        return None
    if stored != binding:
        raise ValueError(f'report {report_id!r} has a different fixed binding')
    return load_clock_report(connection, report_id)


def publish_clock_report(connection: sqlite3.Connection, report_id: str,
                         binding: ClockReportBinding, source: str,
                         ledger: ContributionLedger) -> dict:
    connection.execute('BEGIN IMMEDIATE')
    with connection:
        existing = find_clock_replay(connection, report_id, binding)
        if existing is not None:
            return existing
        insert_clock_report(connection, report_id, binding, source, ledger)
        return load_clock_report(connection, report_id)
