"""Structured validation results with deterministic, severity-aware aggregation."""
from collections.abc import Mapping, Sequence, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol
from ..provenance.hashes import freeze_json, thaw_json
from ..validation.inputs import identifier, hash_string


class Severity(str, Enum):
    """Only failed ERROR results block the generic gate runner."""
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'


@dataclass(frozen=True)
class GateResult:
    """An auditable result bound to a run fingerprint when attached to a registry."""
    name: str
    passed: bool
    severity: Severity
    message: str
    diagnostics: Mapping[str, object] = field(default_factory=dict)
    evidence_fingerprint: str = ''

    def __post_init__(self) -> None:
        identifier(self.name, name='gate name')
        identifier(self.message, name='gate message')
        if type(self.passed) is not bool:
            raise TypeError('Gate passed must be a boolean')
        object.__setattr__(self, 'severity', Severity(self.severity))
        if self.evidence_fingerprint:
            hash_string(self.evidence_fingerprint, name='gate evidence fingerprint')
        object.__setattr__(self, 'diagnostics', freeze_json(self.diagnostics))

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe gate evidence, without discarding diagnostics or binding."""
        return {'name':self.name,'passed':self.passed,'severity':self.severity.value,
                'message':self.message,'diagnostics':thaw_json(self.diagnostics),
                'evidence_fingerprint':self.evidence_fingerprint}


class Gate(Protocol):
    """A gate consumes explicit domain evidence and returns a GateResult."""
    def evaluate(self, *args: object, **kwargs: object) -> GateResult:
        """Evaluate supplied evidence without mutating the run lifecycle."""
        ...


@dataclass(frozen=True)
class GateSummary:
    """A sorted snapshot of gate results; warnings never replace mandatory passes."""
    results: tuple[GateResult, ...]

    @property
    def blocking_failures(self) -> tuple[GateResult, ...]:
        """Failed ERROR gates that block the generic runner."""
        return tuple(r for r in self.results if not r.passed and r.severity == Severity.ERROR)

    @property
    def warnings(self) -> tuple[GateResult, ...]:
        """All explicitly warning-severity diagnostics."""
        return tuple(r for r in self.results if r.severity == Severity.WARNING)

    @property
    def passed(self) -> bool:
        """True when no ERROR gate fails; lifecycle also checks required named passes."""
        return not self.blocking_failures

    def to_dict(self) -> dict[str, object]:
        """Serialize deterministic aggregate and individual gate outcomes."""
        return {'passed':self.passed,'results':[r.to_dict() for r in self.results],
                'blocking_failures':[r.name for r in self.blocking_failures],
                'warnings':[r.name for r in self.warnings]}


def run_gates(results: Sequence[GateResult | Callable[[], GateResult]]) -> GateSummary:
    """Execute explicit zero-argument gate bindings, then aggregate in name order.

    Already evaluated results are also accepted. Callables execute in supplied
    order and retain their explicit domain inputs; no ambient context is inferred.
    """
    values = tuple(result() if callable(result) else result for result in results)
    if not all(isinstance(r, GateResult) for r in values):
        raise TypeError('All gate results must be GateResult instances')
    if len({r.name for r in values}) != len(values):
        raise ValueError('Duplicate gate names are ambiguous')
    return GateSummary(tuple(sorted(values, key=lambda r:r.name)))
