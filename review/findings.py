from dataclasses import dataclass
from fractions import Fraction

from processing.contributions import Contribution
from reports.storage import ReportSnapshot
from review.coverage import CoverageCheck
from review.limits import IntegralLimits, classify_integral


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    actual: Fraction
    threshold: Fraction
    contributions: tuple[Contribution, ...]


def collect_findings(report: ReportSnapshot, coverage: CoverageCheck,
                     limits: IntegralLimits) -> tuple[Finding, ...]:
    findings = []
    if not coverage.passed:
        findings.append(Finding(
            'coverage_insufficient', coverage.actual, coverage.minimum, report.contributions,
        ))
    integral_reason = classify_integral(report.total, limits)
    if integral_reason is not None:
        threshold = limits.minimum if integral_reason == 'integral_below_minimum' else limits.maximum
        findings.append(Finding(integral_reason, report.total, threshold, report.contributions))
    return tuple(findings)
