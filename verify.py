import sys
import unittest
from pathlib import Path


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.testsRun:
        print('No regression tests discovered', file=sys.stderr)
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
