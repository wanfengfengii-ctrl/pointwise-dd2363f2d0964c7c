import sqlite3
from fractions import Fraction

from observations.series import Sample, SampleSeries


def ensure_observation_schema(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS batch_revisions (
            batch_id TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision > 0),
            scale TEXT NOT NULL,
            PRIMARY KEY (batch_id, revision)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS batch_samples (
            batch_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            ordinal INTEGER NOT NULL,
            time_s TEXT NOT NULL,
            reading TEXT NOT NULL,
            PRIMARY KEY (batch_id, revision, ordinal),
            FOREIGN KEY (batch_id, revision) REFERENCES batch_revisions (batch_id, revision)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS batch_heads (
            batch_id TEXT PRIMARY KEY NOT NULL,
            revision INTEGER NOT NULL,
            FOREIGN KEY (batch_id, revision) REFERENCES batch_revisions (batch_id, revision)
        )
    ''')


def append_revision(connection: sqlite3.Connection, batch_id: str, scale: str,
                    series: SampleSeries) -> int:
    connection.execute('BEGIN IMMEDIATE')
    with connection:
        head = connection.execute(
            'SELECT revision FROM batch_heads WHERE batch_id = ?', (batch_id,)
        ).fetchone()
        number = 1 if head is None else head[0] + 1
        connection.execute(
            'INSERT INTO batch_revisions (batch_id, revision, scale) VALUES (?, ?, ?)',
            (batch_id, number, scale),
        )
        connection.executemany('''
            INSERT INTO batch_samples (batch_id, revision, ordinal, time_s, reading)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            (batch_id, number, index, str(sample.time_s), str(sample.reading))
            for index, sample in enumerate(series.samples)
        ))
        connection.execute('''
            INSERT INTO batch_heads (batch_id, revision) VALUES (?, ?)
            ON CONFLICT (batch_id) DO UPDATE SET revision = excluded.revision
        ''', (batch_id, number))
    return number


def load_revision(connection: sqlite3.Connection, batch_id: str,
                  number: int) -> tuple[str, SampleSeries] | None:
    if number > (1 << 63) - 1:
        return None
    header = connection.execute('''
        SELECT scale FROM batch_revisions WHERE batch_id = ? AND revision = ?
    ''', (batch_id, number)).fetchone()
    if header is None:
        return None
    samples = tuple(
        Sample(int(time_s), Fraction(reading))
        for time_s, reading in connection.execute('''
            SELECT time_s, reading FROM batch_samples
            WHERE batch_id = ? AND revision = ? ORDER BY ordinal
        ''', (batch_id, number))
    )
    return header[0], SampleSeries(samples)


def load_current_revision(connection: sqlite3.Connection, batch_id: str) -> int | None:
    head = connection.execute(
        'SELECT revision FROM batch_heads WHERE batch_id = ?', (batch_id,)
    ).fetchone()
    return None if head is None else head[0]
