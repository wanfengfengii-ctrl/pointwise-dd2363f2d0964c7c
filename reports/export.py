import json
import sqlite3
from fractions import Fraction

from processing.contributions import Contribution
from reports.reader import read_report
from reports.storage import ReportSnapshot


def _ratio(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _encode_contribution(item: Contribution) -> dict:
    return {
        'start_s': _ratio(item.start),
        'end_s': _ratio(item.end),
        'samples': [
            {'time_s': sample.time_s, 'reading': _ratio(sample.reading)}
            for sample in item.samples
        ],
        'curve_id': item.curve_id,
        'direction': item.direction,
        'segment_index': item.segment_index,
        'knots': [[_ratio(x), _ratio(y)] for x, y in item.knots],
        'integral': _ratio(item.integral),
    }


def encode_report(report: ReportSnapshot) -> str:
    binding = report.binding
    payload = {
        'format_version': 1,
        'report_id': report.report_id,
        'binding': {
            'batch_id': binding.revision.batch_id,
            'revision': binding.revision.number,
            'curve_id': binding.curve_id,
            'source': report.source,
            'target': binding.target,
            'window': list(binding.window),
        },
        'coverage': _ratio(report.coverage),
        'total': _ratio(report.total),
        'contributions': [_encode_contribution(item) for item in report.contributions],
    }
    return json.dumps(payload, separators=(',', ':'))


def export_report(connection: sqlite3.Connection, report_id: str) -> str:
    return encode_report(read_report(connection, report_id))
