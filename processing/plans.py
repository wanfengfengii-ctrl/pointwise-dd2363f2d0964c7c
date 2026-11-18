import sqlite3
from dataclasses import dataclass

from calibration.catalog import get_curve
from calibration.frozen import OrientedCurve
from calibration.inverse import orient_curve
from observations.revisions import RevisionRef, get_revision
from observations.windows import ObservationWindow, select_window, validate_window
from processing.contributions import close_ledger, make_contribution
from processing.intervals import split_direct_span
from processing.spans import iter_clipped_spans
from quantities import require_name
from reports.bindings import ReportBinding
from reports.publication import find_replay, publish_report
from reports.storage import ReportSnapshot


@dataclass(frozen=True, slots=True)
class ProcessingPlan:
    binding: ReportBinding
    curve: OrientedCurve
    observations: ObservationWindow


def bind_plan(connection: sqlite3.Connection, binding: ReportBinding) -> ProcessingPlan:
    revision = get_revision(connection, binding.revision)
    direct_curve = get_curve(connection, binding.curve_id)
    curve = orient_curve(direct_curve, revision.scale, binding.target)
    return ProcessingPlan(binding, curve, select_window(revision, binding.window))


def build_report(connection: sqlite3.Connection, report_id: str, batch_revision: RevisionRef,
                 curve_id: str, target: str, window: object) -> ReportSnapshot:
    require_name(report_id, 'report ID')
    require_name(curve_id, 'curve ID')
    require_name(target, 'target scale')
    if not isinstance(batch_revision, RevisionRef):
        raise ValueError('an explicit RevisionRef is required')
    binding = ReportBinding(batch_revision, curve_id, target, validate_window(window))
    existing = find_replay(connection, report_id, binding)
    if existing is not None:
        return existing
    plan = bind_plan(connection, binding)
    items = (
        make_contribution(interval)
        for span in iter_clipped_spans(plan.observations)
        for interval in split_direct_span(span, plan.curve)
    )
    ledger = close_ledger(items, plan.observations.intersection)
    return publish_report(connection, report_id, plan.binding, plan.curve.source, ledger)
