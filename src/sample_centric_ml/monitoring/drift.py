"""Auditable threshold rules, without unsupported statistical claims."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..validation.inputs import finite_number, identifier, unique_names
from .signals import MonitoringSignal


@dataclass(frozen=True)
class MonitoringResult:
    """A threshold decision retaining its contributing physical samples."""

    signal: str
    value: float
    threshold: float
    triggered: bool
    message: str
    sample_ids: tuple[str, ...]
    reference_sample_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identifier(self.signal, "signal")
        value = float(finite_number(self.value, "value", minimum=0.0))
        threshold = float(finite_number(self.threshold, "threshold", minimum=0.0))
        if not isinstance(self.triggered, bool):
            raise TypeError("triggered must be a bool")
        if self.triggered != (value > threshold):
            raise ValueError("triggered must equal value > threshold")
        identifier(self.message, "message")
        ids = unique_names(self.sample_ids, "sample_ids")
        reference_ids = unique_names(self.reference_sample_ids, "reference_sample_ids", allow_empty=True)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "threshold", threshold)
        object.__setattr__(self, "sample_ids", tuple(sorted(ids)))
        object.__setattr__(self, "reference_sample_ids", tuple(sorted(reference_ids)))

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible monitoring decision."""
        return {"signal": self.signal, "value": self.value, "threshold": self.threshold,
                "triggered": self.triggered, "message": self.message,
                "sample_ids": list(self.sample_ids),
                "reference_sample_ids": list(self.reference_sample_ids)}


@dataclass(frozen=True)
class ThresholdDriftRule:
    """Trigger when the descriptive signal strictly exceeds its threshold."""

    threshold: float

    def __post_init__(self) -> None:
        value = finite_number(self.threshold, "threshold", minimum=0.0)
        object.__setattr__(self, "threshold", float(value))

    def evaluate(self, signal: MonitoringSignal) -> MonitoringResult:
        """Evaluate one sample-aware signal; equality does not trigger."""
        if not isinstance(signal, MonitoringSignal):
            raise TypeError("signal must be a MonitoringSignal")
        triggered = signal.value > self.threshold
        message = ("Descriptive signal exceeds the configured threshold."
                   if triggered else "Descriptive signal is within the configured threshold.")
        return MonitoringResult(signal.name, signal.value, self.threshold, triggered,
                                message, signal.sample_ids, signal.reference_sample_ids)
