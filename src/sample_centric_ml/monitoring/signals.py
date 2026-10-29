"""Synthetic-friendly monitoring signals with explicit physical-sample IDs."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from ..validation.inputs import finite_number, identifier, unique_names


@dataclass(frozen=True)
class MonitoringSignal:
    """A descriptive scalar and the physical samples contributing to it."""

    name: str
    value: float
    sample_ids: tuple[str, ...]
    reference_sample_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identifier(self.name, "name")
        value = finite_number(self.value, "value", minimum=0.0)
        sample_ids = unique_names(self.sample_ids, "sample_ids")
        reference_ids = unique_names(self.reference_sample_ids, "reference_sample_ids", allow_empty=True)
        object.__setattr__(self, "value", float(value))
        object.__setattr__(self, "sample_ids", tuple(sorted(sample_ids)))
        object.__setattr__(self, "reference_sample_ids", tuple(sorted(reference_ids)))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible sample-aware signal snapshot."""
        return {"name": self.name, "value": self.value, "sample_ids": list(self.sample_ids),
                "reference_sample_ids": list(self.reference_sample_ids)}


def _modality_window(values: Mapping[str, Sequence[str]], name: str) -> dict[str, tuple[str, ...]]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must map physical sample IDs to modalities")
    result = {}
    for sample_id, modalities in values.items():
        identifier(sample_id, f"{name} sample_id")
        result[sample_id] = unique_names(modalities, f"{name} modalities", allow_empty=True)
    return result


def missing_modality_rate(expected: Mapping[str, Sequence[str]],
                          observed: Mapping[str, Sequence[str]]) -> MonitoringSignal:
    """Fraction of explicitly expected sample/modality slots that are absent."""
    expected_slots = _modality_window(expected, "expected")
    observed_slots = _modality_window(observed, "observed")
    if set(observed_slots) - set(expected_slots):
        raise ValueError("observed physical sample IDs must be present in expected")
    denominator = sum(len(modalities) for modalities in expected_slots.values())
    if not denominator:
        raise ValueError("expected must contain at least one sample/modality slot")
    missing = 0
    for sample_id, modalities in expected_slots.items():
        actual = set(observed_slots.get(sample_id, ()))
        if actual - set(modalities):
            raise ValueError("observed modalities must be expected for their physical sample")
        missing += len(set(modalities) - actual)
    return MonitoringSignal("missing_modality_rate", missing / denominator,
                            tuple(expected_slots))


def _numeric_window(values: Mapping[str, float], name: str,
                    maximum: float | None = None) -> tuple[tuple[str, ...], float]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must map physical sample IDs to numeric values")
    if not values:
        raise ValueError(f"{name} must contain at least one physical sample")
    numbers = []
    for sample_id, value in values.items():
        identifier(sample_id, f"{name} sample_id")
        numbers.append(float(finite_number(value, name, minimum=0.0, maximum=maximum)))
    # Normalize before summing, then restore scale. Dividing each raw value by
    # n can still round upward and overflow fsum at the largest finite float.
    scale = max(numbers)
    mean = (scale * (math.fsum(value / scale for value in numbers) / len(numbers))
            if scale else 0.0)
    finite_number(mean, f"{name} mean", minimum=0.0)
    return tuple(sorted(values)), mean


def confidence_drift(reference: Mapping[str, float],
                     current: Mapping[str, float]) -> MonitoringSignal:
    """Absolute mean-confidence shift; this makes no significance claim."""
    reference_ids, reference_mean = _numeric_window(reference, "reference", maximum=1.0)
    current_ids, current_mean = _numeric_window(current, "current", maximum=1.0)
    return MonitoringSignal("confidence_drift", abs(current_mean - reference_mean),
                            current_ids, reference_ids)


def cost_drift(reference: Mapping[str, float], current: Mapping[str, float],
               relative: bool = False) -> MonitoringSignal:
    """Absolute mean-cost shift, optionally relative to the reference mean.

    A zero reference and zero current mean produce zero relative drift. A
    positive current mean with a zero reference has no finite relative drift.
    """
    if not isinstance(relative, bool):
        raise TypeError("relative must be a bool")
    reference_ids, reference_mean = _numeric_window(reference, "reference")
    current_ids, current_mean = _numeric_window(current, "current")
    difference = abs(current_mean - reference_mean)
    if relative:
        if reference_mean == 0.0:
            if current_mean != 0.0:
                raise ValueError("relative cost drift is undefined for a zero reference mean")
            difference = 0.0
        else:
            difference /= reference_mean
    finite_number(difference, "cost drift", minimum=0.0)
    return MonitoringSignal("cost_drift", difference, current_ids, reference_ids)
