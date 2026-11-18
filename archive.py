import sqlite3
from pathlib import Path

from calibration.catalog import get_curve, register_curve
from calibration.frozen import DirectCurve
from calibration.records import ensure_curve_schema
from clocks.catalog import register_clock
from clocks.export import export_clock_report
from clocks.plans import build_clock_report
from clocks.reader import read_clock_report
from clocks.records import ensure_clock_schema
from clocks.storage import ensure_clock_report_schema
from observations.intake import put_batch
from observations.revisions import BatchRevision, RevisionRef, get_current_revision, get_revision
from observations.storage import ensure_observation_schema
from processing.plans import build_report
from reports.export import export_report
from reports.reader import read_report
from reports.storage import ReportSnapshot, ensure_report_schema
from review.assessment import Assessment, assess_report


class Archive:
    def __init__(self, path: str | Path = ':memory:') -> None:
        self._connection = sqlite3.connect(path, isolation_level=None)
        try:
            self._connection.execute('PRAGMA foreign_keys = ON')
            self.initialize()
        except BaseException:
            self._connection.close()
            raise

    def __enter__(self) -> 'Archive':
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def initialize(self) -> None:
        self._connection.execute('BEGIN IMMEDIATE')
        with self._connection:
            ensure_curve_schema(self._connection)
            ensure_observation_schema(self._connection)
            ensure_report_schema(self._connection)
            ensure_clock_schema(self._connection)
            ensure_clock_report_schema(self._connection)

    def register_curve(self, curve_id: str, source: str, target: str, knots: object) -> DirectCurve:
        return register_curve(self._connection, curve_id, source, target, knots)

    def get_curve(self, curve_id: str) -> DirectCurve:
        return get_curve(self._connection, curve_id)

    def put_batch(self, batch_id: str, scale: str, samples: object) -> RevisionRef:
        return put_batch(self._connection, batch_id, scale, samples)

    def get_revision(self, ref: RevisionRef) -> BatchRevision:
        return get_revision(self._connection, ref)

    def get_current_revision(self, batch_id: str) -> BatchRevision:
        return get_current_revision(self._connection, batch_id)

    def build_report(self, report_id: str, batch_revision: RevisionRef, curve_id: str,
                     target: str, window: object) -> ReportSnapshot:
        return build_report(self._connection, report_id, batch_revision, curve_id, target, window)

    def read_report(self, report_id: str) -> ReportSnapshot:
        return read_report(self._connection, report_id)

    def export_report(self, report_id: str) -> str:
        return export_report(self._connection, report_id)

    def assess_report(self, report_id: str, minimum_coverage: object,
                      minimum_integral: object, maximum_integral: object) -> Assessment:
        return assess_report(
            self._connection, report_id, minimum_coverage, minimum_integral, maximum_integral,
        )

    def register_clock(self, clock_id: str, batch_revision: RevisionRef, device_log: object,
                       reference_log: object, rate_range: object) -> dict:
        return register_clock(
            self._connection, clock_id, batch_revision, device_log, reference_log, rate_range,
        )

    def build_clock_report(self, report_id: str, clock_id: str, curve_id: str,
                           target: str, window: object) -> dict:
        return build_clock_report(self._connection, report_id, clock_id, curve_id, target, window)

    def read_clock_report(self, report_id: str) -> dict:
        return read_clock_report(self._connection, report_id)

    def export_clock_report(self, report_id: str) -> str:
        return export_clock_report(self._connection, report_id)
