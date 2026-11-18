from dataclasses import dataclass
from fractions import Fraction

from quantities import exact_fraction, integer_seconds, iter_pairs


@dataclass(frozen=True, slots=True)
class Sample:
    time_s: int
    reading: Fraction


@dataclass(frozen=True, slots=True)
class SampleSeries:
    samples: tuple[Sample, ...]


def normalize_series(records: object) -> SampleSeries:
    samples = []
    for raw_time, raw_reading in iter_pairs(records, 'sample'):
        time_s = integer_seconds(raw_time, 'sample time')
        reading = exact_fraction(raw_reading, 'sample reading')
        if not 0 <= reading <= 1:
            raise ValueError('sample reading must lie in [0,1]')
        if samples and time_s <= samples[-1].time_s:
            raise ValueError('sample times must be strictly increasing')
        samples.append(Sample(time_s, reading))
    if len(samples) < 2:
        raise ValueError('at least two samples are required')
    return SampleSeries(tuple(samples))
