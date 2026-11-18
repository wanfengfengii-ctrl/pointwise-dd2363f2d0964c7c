import sqlite3

from clocks.storage import load_clock_report
from quantities import require_name


def read_clock_report(connection: sqlite3.Connection, report_id: str) -> dict:
    require_name(report_id, 'report ID')
    payload = load_clock_report(connection, report_id)
    if payload is None:
        raise KeyError(report_id)
    return payload
