import sqlite3
from dataclasses import dataclass
from fractions import Fraction

from reports.reader import read_report
from review.coverage import CoverageCheck, check_coverage
from review.findings import Finding, collect_findings
from review.limits import IntegralLimits, make_integral_limits


@dataclass(frozen=True, slots=True)
class Assessment:
    report_id: str
    coverage: CoverageCheck
    limits: IntegralLimits
    total: Fraction
    findings: tuple[Finding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings


def assess_report(connection: sqlite3.Connection, report_id: str, minimum_coverage: object,
                  minimum_integral: object, maximum_integral: object) -> Assessment:
    report = read_report(connection, report_id)
    coverage = check_coverage(report.coverage, minimum_coverage)
    limits = make_integral_limits(minimum_integral, maximum_integral)
    findings = collect_findings(report, coverage, limits)
    return Assessment(report_id, coverage, limits, report.total, findings)
