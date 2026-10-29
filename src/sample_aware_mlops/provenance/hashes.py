"""Canonical JSON snapshots and SHA-256 identities without machine metadata."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any


def freeze_json(value: Any) -> Any:
    """Copy a finite JSON value into immutable mappings and tuples.

    Mapping keys must already be strings. Unsupported objects and cyclic input
    are rejected rather than encoded through potentially unstable repr strings.
    Enums and dataclasses use their explicit values or public ``to_dict`` form.
    """
    def visit(item: Any, active: set[int]) -> Any:
        if isinstance(item, Enum):
            return visit(item.value, active)
        if item is None or isinstance(item, (str, bool, int)):
            return item
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("JSON numbers must be finite")
            return item
        if isinstance(item, Mapping):
            marker = id(item)
            if marker in active:
                raise ValueError("JSON values must not contain cycles")
            active.add(marker)
            try:
                copied = {}
                for key, nested in item.items():
                    if not isinstance(key, str):
                        raise TypeError("JSON mapping keys must be strings")
                    copied[key] = visit(nested, active)
                return MappingProxyType(copied)
            finally:
                active.remove(marker)
        if isinstance(item, (list, tuple)):
            marker = id(item)
            if marker in active:
                raise ValueError("JSON values must not contain cycles")
            active.add(marker)
            try:
                return tuple(visit(nested, active) for nested in item)
            finally:
                active.remove(marker)
        if is_dataclass(item) and not isinstance(item, type):
            marker = id(item)
            if marker in active:
                raise ValueError("JSON values must not contain cycles")
            active.add(marker)
            try:
                public = getattr(item, "to_dict", None)
                representation = public() if callable(public) else {
                    field.name: getattr(item, field.name) for field in fields(item)
                }
                return visit(representation, active)
            finally:
                active.remove(marker)
        raise TypeError(f"Unsupported JSON value type: {type(item).__name__}")

    return visit(value, set())


def thaw_json(value: Any) -> Any:
    """Return an independent mutable JSON-compatible copy of a safe value."""
    frozen = freeze_json(value)

    def thaw(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {key: thaw(nested) for key, nested in item.items()}
        if isinstance(item, tuple):
            return [thaw(nested) for nested in item]
        return item

    return thaw(frozen)


def canonical_json(value: Any) -> str:
    """Serialize finite JSON with sorted keys and a stable compact encoding."""
    return json.dumps(thaw_json(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def sha256(value: Any) -> str:
    """Hash the canonical UTF-8 JSON representation of ``value``."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
