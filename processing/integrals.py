from fractions import Fraction

from calibration.curves import evaluate_segment
from processing.intervals import DirectInterval


def integrate_interval(interval: DirectInterval) -> Fraction:
    start_value = evaluate_segment(interval.segment, interval.start_reading)
    end_value = evaluate_segment(interval.segment, interval.end_reading)
    return (interval.end - interval.start) * (start_value + end_value) / 2
