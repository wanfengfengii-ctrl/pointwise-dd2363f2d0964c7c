import sqlite3

from observations.revisions import RevisionRef, save_revision
from observations.series import normalize_series
from quantities import require_name


def put_batch(connection: sqlite3.Connection, batch_id: str, scale: str,
              samples: object) -> RevisionRef:
    require_name(batch_id, 'batch ID')
    require_name(scale, 'batch scale')
    series = normalize_series(samples)
    return save_revision(connection, batch_id, scale, series)
