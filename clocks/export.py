import json
import sqlite3

from clocks.reader import read_clock_report


def export_clock_report(connection: sqlite3.Connection, report_id: str) -> str:
    return json.dumps(read_clock_report(connection, report_id), separators=(',', ':'))
