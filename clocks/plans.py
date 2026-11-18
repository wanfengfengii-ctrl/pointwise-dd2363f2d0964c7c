import sqlite3

from calibration.catalog import get_curve
from calibration.inverse import orient_curve
from clocks.catalog import get_clock
from clocks.frozen import ClockReportBinding
from clocks.ledger import build_clocked_ledger
from clocks.publication import find_clock_replay, publish_clock_report
from observations.revisions import get_revision
from observations.windows import validate_window
from quantities import require_name


def build_clock_report(connection: sqlite3.Connection, report_id: str, clock_id: str,
                       curve_id: str, target: str, window: object) -> dict:
    require_name(report_id, 'report ID')
    require_name(clock_id, 'clock ID')
    require_name(curve_id, 'curve ID')
    require_name(target, 'target scale')
    binding = ClockReportBinding(clock_id, curve_id, target, validate_window(window))
    existing = find_clock_replay(connection, report_id, binding)
    if existing is not None:
        return existing
    registration = get_clock(connection, clock_id)
    revision = get_revision(connection, registration.binding.revision)
    curve = orient_curve(get_curve(connection, curve_id), revision.scale, target)
    ledger = build_clocked_ledger(
        revision, curve, registration.rate, registration.offset, binding.window,
    )
    return publish_clock_report(connection, report_id, binding, curve.source, ledger)
