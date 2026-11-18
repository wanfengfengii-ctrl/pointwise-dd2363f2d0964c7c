import sqlite3

from quantities import require_name
from reports.storage import ReportSnapshot, load_report


def read_report(connection: sqlite3.Connection, report_id: str) -> ReportSnapshot:
    require_name(report_id, 'report ID')
    snapshot = load_report(connection, report_id)
    if snapshot is None:
        raise KeyError(report_id)
    return snapshot
