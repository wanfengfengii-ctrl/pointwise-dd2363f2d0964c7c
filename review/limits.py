from dataclasses import dataclass
from fractions import Fraction

from quantities import exact_fraction


@dataclass(frozen=True, slots=True)
class IntegralLimits:
    minimum: Fraction
    maximum: Fraction


def make_integral_limits(minimum: object, maximum: object) -> IntegralLimits:
    lower = exact_fraction(minimum, 'minimum integral')
    upper = exact_fraction(maximum, 'maximum integral')
    if lower > upper:
        raise ValueError('integral limits must be in ascending order')
    return IntegralLimits(lower, upper)


def classify_integral(total: Fraction, limits: IntegralLimits) -> str | None:
    if total < limits.minimum:
        return 'integral_below_minimum'
    if total > limits.maximum:
        return 'integral_above_maximum'
    return None
