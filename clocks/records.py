import sqlite3
from fractions import Fraction

from clocks.frozen import ClockLogBinding, ClockRegistration
from observations.revisions import RevisionRef


def ensure_clock_schema(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS clocks (
            clock_id TEXT PRIMARY KEY NOT NULL,
            batch_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            rate_min TEXT NOT NULL,
            rate_max TEXT NOT NULL,
            rate TEXT NOT NULL,
            offset TEXT NOT NULL,
            FOREIGN KEY (batch_id, revision) REFERENCES batch_revisions (batch_id, revision)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS clock_log_events (
            clock_id TEXT NOT NULL REFERENCES clocks(clock_id),
            log TEXT NOT NULL CHECK (log IN ('device', 'reference')),
            ordinal INTEGER NOT NULL,
            time_s TEXT NOT NULL,
            mark TEXT NOT NULL,
            PRIMARY KEY (clock_id, log, ordinal)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS clock_matches (
            clock_id TEXT NOT NULL REFERENCES clocks(clock_id),
            ordinal INTEGER NOT NULL,
            device_time_s TEXT NOT NULL,
            reference_time_s TEXT NOT NULL,
            mark TEXT NOT NULL,
            PRIMARY KEY (clock_id, ordinal)
        )
    ''')


def store_clock(connection: sqlite3.Connection, registration: ClockRegistration) -> None:
    binding = registration.binding
    connection.execute('''
        INSERT INTO clocks (clock_id, batch_id, revision, rate_min, rate_max, rate, offset)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        registration.clock_id, binding.revision.batch_id, binding.revision.number,
        str(binding.rate_range[0]), str(binding.rate_range[1]),
        str(registration.rate), str(registration.offset),
    ))
    connection.executemany('''
        INSERT INTO clock_log_events (clock_id, log, ordinal, time_s, mark)
        VALUES (?, ?, ?, ?, ?)
    ''', [
        *(
            (registration.clock_id, 'device', ordinal, str(time_s), mark)
            for ordinal, (time_s, mark) in enumerate(binding.device_log)
        ),
        *(
            (registration.clock_id, 'reference', ordinal, str(time_s), mark)
            for ordinal, (time_s, mark) in enumerate(binding.reference_log)
        ),
    ])
    connection.executemany('''
        INSERT INTO clock_matches (clock_id, ordinal, device_time_s, reference_time_s, mark)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        (registration.clock_id, ordinal, str(device_time), str(reference_time), mark)
        for ordinal, (device_time, reference_time, mark) in enumerate(registration.matches)
    ))


def load_clock(connection: sqlite3.Connection, clock_id: str) -> ClockRegistration | None:
    header = connection.execute('''
        SELECT batch_id, revision, rate_min, rate_max, rate, offset
        FROM clocks WHERE clock_id = ?
    ''', (clock_id,)).fetchone()
    if header is None:
        return None
    batch_id, number, rate_min, rate_max, rate, offset = header
    events: dict[str, list[tuple[int, str]]] = {'device': [], 'reference': []}
    for log, time_s, mark in connection.execute('''
        SELECT log, time_s, mark FROM clock_log_events
        WHERE clock_id = ? ORDER BY log, ordinal
    ''', (clock_id,)):
        events[log].append((int(time_s), mark))
    matches = tuple(
        (int(device_time), int(reference_time), mark)
        for device_time, reference_time, mark in connection.execute('''
            SELECT device_time_s, reference_time_s, mark FROM clock_matches
            WHERE clock_id = ? ORDER BY ordinal
        ''', (clock_id,))
    )
    binding = ClockLogBinding(
        RevisionRef(batch_id, number), tuple(events['device']), tuple(events['reference']),
        (Fraction(rate_min), Fraction(rate_max)),
    )
    return ClockRegistration(clock_id, binding, Fraction(rate), Fraction(offset), matches)
