import json
import sys
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from archive import Archive

EXAMPLES = Path(__file__).resolve().parent / 'examples'
DEVICE = ((1, 'left'), (3, 'right'))
REFERENCE = ((2, 'left'), (5, 'right'))
REPORT = ('sheet', 'fit', 'probe', 'B', (1, 2))


def seed(archive):
    curve = json.loads((EXAMPLES / 'direct-curve.json').read_text(encoding='utf-8'))
    batch = json.loads((EXAMPLES / 'tide-batch.json').read_text(encoding='utf-8'))
    archive.register_curve(**curve)
    revision = archive.put_batch(batch['batch_id'], batch['scale'], batch['initial'])
    old = archive.build_report('sheet', revision, 'probe', 'B', (0, 1))
    assert (old.coverage, old.total) == (1, Fraction(3, 8))
    return revision, batch


def check_base():
    with Archive() as archive:
        revision, _ = seed(archive)
        unshifted = archive.build_report('unshifted', revision, 'probe', 'B', (1, 2))
        assert (unshifted.coverage, unshifted.total, unshifted.contributions) == (0, 0, ())
        print(archive.export_report('sheet'))


def expect_error(kind, call, *args):
    try:
        call(*args)
    except kind:
        return
    raise AssertionError(f'{call.__name__} should raise {kind.__name__}')


def check_pulses(archive, revision):
    device = [[t, 'same'] for t in (0, 1, 2)]
    reference = [[t, 'same'] for t in (10, 11, 12, 20, 21, 22)]
    expect_error(ValueError, archive.register_clock, 'pulse', revision, device, reference, (1, 1))
    expect_error(KeyError, archive.build_clock_report, 'before', 'pulse', 'probe', 'B', (10, 11))
    device.append([3, 'extra'])
    reference.insert(3, [13, 'extra'])
    clock = archive.register_clock('pulse', revision, device, reference, (1, 1))
    assert clock['rate'] == [1, 1] and clock['offset'] == [10, 1]
    assert clock['matches'] == [[0, 10, 'same'], [1, 11, 'same'], [2, 12, 'same'], [3, 13, 'extra']]
    assert (clock['device_log'], clock['reference_log']) == (device, reference)
    reference.pop(3)
    assert clock['reference_log'][3] == [13, 'extra']
    expect_error(ValueError, archive.register_clock, 'pulse', revision, device, reference, (1, 1))
    return clock


def check_export(payload):
    assert payload['format_version'] == 2 and payload['report_id'] == 'sheet'
    binding = payload['binding']
    assert (binding['batch_id'], binding['revision'], binding['window']) == ('morning-tide', 1, [1, 2])
    clock = payload['clock']
    assert clock == {'clock_id': 'fit', 'rate': [3, 2], 'offset': [1, 2],
                     'matches': [[1, 2, 'left'], [3, 5, 'right']]}
    a, b = Fraction(*clock['rate']), Fraction(*clock['offset'])
    items = payload['contributions']
    expected = [(Fraction(1), Fraction(5, 4), 0, Fraction(5, 96)),
                (Fraction(5, 4), Fraction(2), 1, Fraction(15, 32))]
    assert len(items) == len(expected)
    coverage = total = Fraction(0)
    for part, expected_part in zip(items, expected):
        left, right = Fraction(*part['start_s']), Fraction(*part['end_s'])
        area = Fraction(*part['integral'])
        assert (left, right, part['segment_index'], area) == expected_part
        assert part['samples'] == [{'time_s': 0, 'reading': [0, 1]}, {'time_s': 1, 'reading': [1, 1]}]
        # In this example the reading equals device time. The two known
        # calibration branches give a hand-derived reference for this case.
        x0, x1 = (left - b) / a, (right - b) / a
        if part['segment_index'] == 0:
            heights = (x0 / 2, x1 / 2)
        else:
            heights = ((3 * x0 - 1) / 2, (3 * x1 - 1) / 2)
        recomputed = (right - left) * sum(heights) / 2
        assert recomputed == area
        coverage += right - left
        total += recomputed
    assert coverage == Fraction(*payload['coverage']) == 1
    assert total == Fraction(*payload['total']) == Fraction(25, 48)


def check_clock(show):
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'meter.sqlite'
        with Archive(path) as archive:
            revision, batch = seed(archive)
            pulse = check_pulses(archive, revision)
            fit = archive.register_clock('fit', revision, DEVICE, REFERENCE, (1, 2))
            report = archive.build_clock_report(*REPORT)
            saved = archive.export_clock_report('sheet')
            assert report == json.loads(saved)
            report['contributions'].clear()
            archive.put_batch(batch['batch_id'], batch['scale'], batch['corrected'])
        with Archive(path) as archive:
            assert archive.register_clock('fit', revision, DEVICE, REFERENCE, ('1', '2')) == fit
            assert archive.build_clock_report(*REPORT) == archive.read_clock_report('sheet') == json.loads(saved)
            assert archive.export_clock_report('sheet') == saved
            assert archive.read_report('sheet').total == Fraction(3, 8)
            expect_error(ValueError, archive.build_clock_report, *REPORT[:-1], (1, 3))
            empty = archive.build_clock_report('empty', 'fit', 'probe', 'B', (2, 3))
            assert (empty['coverage'], empty['total'], empty['contributions']) == ([0, 1], [0, 1], [])
    check_export(json.loads(saved))
    if show:
        print(json.dumps(pulse, ensure_ascii=False))
        print(saved)


def main():
    if sys.argv[1:] == ['base']:
        check_base()
    elif sys.argv[1:] in (['verify'], ['demo']):
        check_clock(show=sys.argv[1] == 'demo')
    else:
        raise SystemExit('usage: python3 -B clock_cases.py {base,verify,demo}')


if __name__ == '__main__':
    main()
