import sqlite3
from dataclasses import dataclass

from observations.series import SampleSeries
from observations.storage import append_revision, load_current_revision, load_revision
from quantities import require_name


@dataclass(frozen=True, slots=True)
class RevisionRef:
    batch_id: str
    number: int

    def __post_init__(self) -> None:
        require_name(self.batch_id, 'batch ID')
        if type(self.number) is not int or self.number <= 0:
            raise ValueError('revision number must be a positive integer')


@dataclass(frozen=True, slots=True)
class BatchRevision:
    ref: RevisionRef
    scale: str
    series: SampleSeries


def save_revision(connection: sqlite3.Connection, batch_id: str, scale: str,
                  series: SampleSeries) -> RevisionRef:
    return RevisionRef(batch_id, append_revision(connection, batch_id, scale, series))


def get_revision(connection: sqlite3.Connection, ref: RevisionRef) -> BatchRevision:
    if not isinstance(ref, RevisionRef):
        raise ValueError('an explicit RevisionRef is required')
    stored = load_revision(connection, ref.batch_id, ref.number)
    if stored is None:
        raise KeyError(ref)
    scale, series = stored
    return BatchRevision(ref, scale, series)


def get_current_revision(connection: sqlite3.Connection, batch_id: str) -> BatchRevision:
    require_name(batch_id, 'batch ID')
    number = load_current_revision(connection, batch_id)
    if number is None:
        raise KeyError(batch_id)
    return get_revision(connection, RevisionRef(batch_id, number))
