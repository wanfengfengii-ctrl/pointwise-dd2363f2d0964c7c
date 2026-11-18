from dataclasses import replace
from fractions import Fraction

from calibration.frozen import OrientedCurve
from observations.revisions import BatchRevision
from observations.windows import ObservationWindow
from processing.contributions import ContributionLedger, close_ledger, make_contribution
from processing.intervals import DirectInterval, split_direct_span
from processing.spans import iter_clipped_spans


def select_clock_window(revision: BatchRevision, rate: Fraction, offset: Fraction,
                        window: tuple[int, int]) -> ObservationWindow:
    device_start = (Fraction(window[0]) - offset) / rate
    device_end = (Fraction(window[1]) - offset) / rate
    samples = revision.series.samples
    start = max(device_start, Fraction(samples[0].time_s))
    end = min(device_end, Fraction(samples[-1].time_s))
    if start >= end:
        return ObservationWindow(None, ())
    pairs = tuple(
        (first, last)
        for first, last in zip(samples, samples[1:])
        if first.time_s < end and last.time_s > start
    )
    return ObservationWindow((start, end), pairs)


def shift_to_reference(interval: DirectInterval, rate: Fraction, offset: Fraction) -> DirectInterval:
    return replace(
        interval,
        start=rate * interval.start + offset,
        end=rate * interval.end + offset,
    )


def build_clocked_ledger(revision: BatchRevision, curve: OrientedCurve, rate: Fraction,
                         offset: Fraction, window: tuple[int, int]) -> ContributionLedger:
    observations = select_clock_window(revision, rate, offset, window)
    items = (
        make_contribution(shift_to_reference(interval, rate, offset))
        for span in iter_clipped_spans(observations)
        for interval in split_direct_span(span, curve)
    )
    intersection = None
    if observations.intersection is not None:
        start, end = observations.intersection
        intersection = (rate * start + offset, rate * end + offset)
    return close_ledger(items, intersection)
