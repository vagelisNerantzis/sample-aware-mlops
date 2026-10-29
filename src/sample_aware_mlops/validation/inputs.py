"""Explicit identifiers, numeric bounds and canonical physical-sample schemas."""
from collections.abc import Sequence
from numbers import Real, Integral
import math
import re

SPLITS = ('train', 'validation', 'test')


def identifier(value: str, name: str = 'identifier') -> str:
    """Require a logical ID, not a machine path, URI, blank or control string."""
    if not isinstance(value, str):
        raise TypeError(f'{name} must be a string')
    if not value or value != value.strip() or any(ord(c)<32 for c in value):
        raise ValueError(f'{name} must be nonempty and have no surrounding whitespace/control characters')
    if re.search(r'^[A-Za-z]:', value) or value.startswith(('/', '~', '\\')) or '://' in value:
        raise ValueError(f'{name} must be a logical identifier, not a machine path or URI')
    return value


def unique_names(values: Sequence[str], name: str = 'values', allow_empty: bool = False) -> tuple[str, ...]:
    """Snapshot a sequence of unique logical IDs; caller controls canonical ordering."""
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f'{name} must be a sequence of identifiers')
    result = tuple(identifier(v, name=name) for v in values)
    if not result and not allow_empty:
        raise ValueError(f'{name} must not be empty')
    if len(set(result)) != len(result):
        raise ValueError(f'Duplicate identifiers in {name}')
    return result


def integer(value: int, name: str, minimum: int = 0) -> int:
    """Require an integer, excluding booleans, at or above minimum."""
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f'{name} must be an integer')
    if value < minimum:
        raise ValueError(f'{name} must be >= {minimum}')
    return int(value)


def finite_number(value: float, name: str, minimum: float | None = None, maximum: float | None = None) -> float:
    """Require a finite real value with optional inclusive bounds."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f'{name} must be a real number')
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum) or (maximum is not None and result > maximum):
        raise ValueError(f'{name} must be finite and within its declared bounds')
    return result


def hash_string(value: str, name: str = 'hash') -> str:
    """Require a lowercase 64-character SHA-256 digest."""
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError(f'{name} must be a lowercase SHA-256 digest')
    return value
