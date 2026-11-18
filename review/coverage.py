from dataclasses import dataclass
from fractions import Fraction

from quantities import exact_fraction


@dataclass(frozen=True, slots=True)
class CoverageCheck:
    actual: Fraction
    minimum: Fraction

    @property
    def passed(self) -> bool:
        return self.actual >= self.minimum


def check_coverage(actual: Fraction, minimum: object) -> CoverageCheck:
    required = exact_fraction(minimum, 'minimum coverage')
    if required < 0:
        raise ValueError('minimum coverage must be nonnegative')
    return CoverageCheck(actual, required)
