from collections.abc import Iterator, Mapping
from fractions import Fraction


def require_name(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a nonblank string')
    return value


def exact_fraction(value: object, label: str) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if type(value) not in (int, str):
        raise ValueError(f'{label} must be an exact rational value')
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f'{label} must be an exact rational value') from error


def integer_seconds(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f'{label} must be an integer number of seconds')
    return value


def require_pair(value: object, label: str) -> tuple[object, object]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(f'{label} must be a two-item pair')
    return value[0], value[1]


def iter_pairs(records: object, label: str) -> Iterator[tuple[object, object]]:
    if isinstance(records, (str, bytes, bytearray, Mapping)):
        raise ValueError(f'{label} must be a sequence of pairs')
    try:
        iterator = iter(records)
    except TypeError as error:
        raise ValueError(f'{label} must be a sequence of pairs') from error
    for record in iterator:
        yield require_pair(record, label)
