import json
import tempfile
from fractions import Fraction
from pathlib import Path

from archive import Archive
from clock_cases import check_clock


def main() -> None:
    examples = Path(__file__).resolve().parent / 'examples'
    curve = json.loads((examples / 'direct-curve.json').read_text(encoding='utf-8'))
    batch = json.loads((examples / 'tide-batch.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'meter.sqlite'
        with Archive(path) as archive:
            fixed_curve = archive.register_curve(**curve)
            first = archive.put_batch(batch['batch_id'], batch['scale'], batch['initial'])
            old = archive.build_report('morning-original', first, fixed_curve.curve_id,
                                       fixed_curve.target, batch['window'])
            assessment = archive.assess_report(old.report_id, 1, '3/8', '3/8')
            old_export = archive.export_report(old.report_id)
            corrected = archive.put_batch(batch['batch_id'], batch['scale'], batch['corrected'])
            new = archive.build_report('morning-corrected', corrected, fixed_curve.curve_id,
                                       fixed_curve.target, batch['window'])
            new_export = archive.export_report(new.report_id)
        with Archive(path) as archive:
            reopened = archive.read_report(old.report_id)
            reopened_new = archive.read_report(new.report_id)
            delivered = archive.export_report(old.report_id)
            delivered_new = archive.export_report(new.report_id)
            if (reopened, reopened_new, delivered, delivered_new) != (old, new, old_export, new_export):
                raise RuntimeError('delivery changed after reopening the archive')
    expected = {
        'coverage': '1', 'total': '3/8',
        'items': [['0', '1/2', 0, '1/16'], ['1/2', '1', 1, '5/16']],
    }
    actual = {
        'coverage': str(old.coverage), 'total': str(old.total),
        'items': [[str(c.start), str(c.end), c.segment_index, str(c.integral)] for c in old.contributions],
    }
    downstream_expected = {
        'approved': True, 'old_revision': 1, 'new_revision': 2,
        'old_export_total': '3/8', 'new_export_total': '0',
    }
    downstream_actual = {
        'approved': assessment.passed,
        'old_revision': reopened.binding.revision.number,
        'new_revision': reopened_new.binding.revision.number,
        'old_export_total': str(Fraction(*json.loads(delivered)['total'])),
        'new_export_total': str(Fraction(*json.loads(delivered_new)['total'])),
    }
    if actual != expected or downstream_actual != downstream_expected:
        raise RuntimeError('published ledger differs from the hand-computed sample')
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': 'v4',
        'input': {'curve': curve, 'batch': batch},
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': [
            'calibration/catalog.py', 'observations/intake.py', 'processing/intervals.py',
            'processing/integrals.py', 'reports/publication.py', 'review/assessment.py',
            'reports/reader.py', 'reports/export.py',
        ],
        'oracle': 'The two half-second trapezoids have endpoint heights 0, 1/4, 1. The corrected reading is zero throughout.',
    }, separators=(',', ':')))
    print(delivered)
    print(delivered_new)
    print('POINTWISE_CLOCK_CHAIN')
    check_clock(show=True)


if __name__ == '__main__':
    main()
