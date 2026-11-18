from dataclasses import dataclass

from observations.revisions import BatchRevision
from observations.series import Sample
from quantities import integer_seconds, require_pair


@dataclass(frozen=True, slots=True)
class ObservationWindow:
    intersection: tuple[int, int] | None
    pairs: tuple[tuple[Sample, Sample], ...]


def validate_window(window: object) -> tuple[int, int]:
    left, right = require_pair(window, 'window')
    start = integer_seconds(left, 'window start')
    end = integer_seconds(right, 'window end')
    if start > end:
        raise ValueError('window start must be at or before its end')
    return start, end


def select_window(revision: BatchRevision, window: tuple[int, int]) -> ObservationWindow:
    samples = revision.series.samples
    start = max(window[0], samples[0].time_s)
    end = min(window[1], samples[-1].time_s)
    if start >= end:
        return ObservationWindow(None, ())
    pairs = tuple(
        (first, last)
        for first, last in zip(samples, samples[1:])
        if first.time_s < end and last.time_s > start
    )
    return ObservationWindow((start, end), pairs)
