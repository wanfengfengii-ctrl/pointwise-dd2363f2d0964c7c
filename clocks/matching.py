from fractions import Fraction

from quantities import exact_fraction, integer_seconds, iter_pairs, require_name, require_pair

PulseLog = tuple[tuple[int, str], ...]
Match = tuple[int, int, str]


def normalize_log(records: object, label: str) -> PulseLog:
    events = []
    for raw_time, raw_mark in iter_pairs(records, label):
        time_s = integer_seconds(raw_time, f'{label} time')
        mark = require_name(raw_mark, f'{label} mark')
        if events and time_s <= events[-1][0]:
            raise ValueError(f'{label} times must be strictly increasing')
        events.append((time_s, mark))
    return tuple(events)


def normalize_rate_range(value: object) -> tuple[Fraction, Fraction]:
    low, high = require_pair(value, 'rate range')
    minimum = exact_fraction(low, 'rate range minimum')
    maximum = exact_fraction(high, 'rate range maximum')
    if minimum <= 0 or maximum <= 0:
        raise ValueError('rate range endpoints must be positive')
    if minimum > maximum:
        raise ValueError('rate range minimum must not exceed its maximum')
    return minimum, maximum


def solve_mapping(device_log: PulseLog, reference_log: PulseLog,
                  rate_range: tuple[Fraction, Fraction]) -> tuple[Fraction, Fraction, tuple[Match, ...]]:
    minimum, maximum = rate_range
    pairs = [
        (device_time, reference_time, mark)
        for device_time, mark in device_log
        for reference_time, reference_mark in reference_log
        if mark == reference_mark
    ]
    candidates = set()
    for first in range(len(pairs)):
        first_device, first_reference, _ = pairs[first]
        for second in range(first + 1, len(pairs)):
            second_device, second_reference, _ = pairs[second]
            if first_device == second_device:
                continue
            rate = Fraction(second_reference - first_reference, second_device - first_device)
            if minimum <= rate <= maximum:
                candidates.add((rate, first_reference - rate * first_device))
    best = None
    tied = False
    for rate, offset in candidates:
        matches = tuple(
            (device_time, reference_time, mark)
            for device_time, reference_time, mark in pairs
            if reference_time == rate * device_time + offset
        )
        if best is None or len(matches) > len(best[2]):
            best = (rate, offset, matches)
            tied = False
        elif len(matches) == len(best[2]):
            tied = True
    if best is None or tied or len(best[2]) < 2:
        raise ValueError('pulse logs do not determine a unique clock mapping')
    return best
