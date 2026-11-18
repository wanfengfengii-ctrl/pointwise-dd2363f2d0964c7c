import sqlite3

from clocks.frozen import ClockLogBinding, ClockRegistration
from clocks.matching import normalize_log, normalize_rate_range, solve_mapping
from clocks.payload import clock_payload
from clocks.records import load_clock, store_clock
from observations.revisions import RevisionRef, get_revision
from quantities import require_name


def register_clock(connection: sqlite3.Connection, clock_id: str, batch_revision: RevisionRef,
                   device_log: object, reference_log: object, rate_range: object) -> dict:
    require_name(clock_id, 'clock ID')
    if not isinstance(batch_revision, RevisionRef):
        raise ValueError('an explicit RevisionRef is required')
    proposed = ClockLogBinding(
        batch_revision,
        normalize_log(device_log, 'device log'),
        normalize_log(reference_log, 'reference log'),
        normalize_rate_range(rate_range),
    )
    connection.execute('BEGIN IMMEDIATE')
    with connection:
        existing = load_clock(connection, clock_id)
        if existing is not None:
            if existing.binding != proposed:
                raise ValueError(f'clock {clock_id!r} has a different fixed binding')
            return clock_payload(existing)
        get_revision(connection, batch_revision)
        rate, offset, matches = solve_mapping(
            proposed.device_log, proposed.reference_log, proposed.rate_range,
        )
        registration = ClockRegistration(clock_id, proposed, rate, offset, matches)
        store_clock(connection, registration)
        return clock_payload(registration)


def get_clock(connection: sqlite3.Connection, clock_id: str) -> ClockRegistration:
    require_name(clock_id, 'clock ID')
    registration = load_clock(connection, clock_id)
    if registration is None:
        raise KeyError(clock_id)
    return registration
