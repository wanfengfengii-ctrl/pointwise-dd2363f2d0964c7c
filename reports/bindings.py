from dataclasses import dataclass

from observations.revisions import RevisionRef


@dataclass(frozen=True, slots=True)
class ReportBinding:
    revision: RevisionRef
    curve_id: str
    target: str
    window: tuple[int, int]


def require_same_binding(report_id: str, stored: ReportBinding, requested: ReportBinding) -> None:
    if stored != requested:
        raise ValueError(f'report {report_id!r} has a different fixed binding')
