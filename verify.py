import io
import sys
import traceback
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import clock_cases


def run_clock_chain() -> int:
    checks = (
        ('base', clock_cases.check_base),
        ('verify', lambda: clock_cases.check_clock(show=False)),
    )
    for name, check in checks:
        try:
            with redirect_stdout(io.StringIO()):
                check()
        except Exception:
            print(f'clock chain check {name!r} failed', file=sys.stderr)
            traceback.print_exc()
            return 1
        print(f'clock chain check {name!r} passed')
    return 0


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.testsRun:
        print('No regression tests discovered', file=sys.stderr)
        return 1
    if not result.wasSuccessful():
        return 1
    return run_clock_chain()


if __name__ == '__main__':
    raise SystemExit(main())
