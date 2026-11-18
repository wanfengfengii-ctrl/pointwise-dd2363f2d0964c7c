from fractions import Fraction

from clocks.frozen import ClockRegistration


def ratio(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def clock_payload(registration: ClockRegistration) -> dict:
    binding = registration.binding
    return {
        'clock_id': registration.clock_id,
        'batch_id': binding.revision.batch_id,
        'revision': binding.revision.number,
        'device_log': [[time_s, mark] for time_s, mark in binding.device_log],
        'reference_log': [[time_s, mark] for time_s, mark in binding.reference_log],
        'rate_range': [ratio(binding.rate_range[0]), ratio(binding.rate_range[1])],
        'rate': ratio(registration.rate),
        'offset': ratio(registration.offset),
        'matches': [
            [device_time, reference_time, mark]
            for device_time, reference_time, mark in registration.matches
        ],
    }


def clock_summary(registration: ClockRegistration) -> dict:
    return {
        'clock_id': registration.clock_id,
        'rate': ratio(registration.rate),
        'offset': ratio(registration.offset),
        'matches': [
            [device_time, reference_time, mark]
            for device_time, reference_time, mark in registration.matches
        ],
    }
