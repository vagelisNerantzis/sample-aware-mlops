"""Immutable experiment configuration with explicit scientific policy."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..provenance.hashes import canonical_json, freeze_json, sha256, thaw_json
from ..validation.inputs import SPLITS, finite_number, identifier, integer


@dataclass(frozen=True)
class ExperimentSpec:
    """A seeded experiment specification independent of insertion order.

    Omitted evaluation policy means validation evaluation with no additional
    calibration requirement. Promotion thresholds are opt-in and named exactly.
    """

    name: str
    seed: int
    dataset_version: str
    split_strategy: str = "physical_sample"
    representation: Mapping[str, Any] = field(default_factory=dict)
    fusion: Mapping[str, Any] = field(default_factory=dict)
    acquisition: Mapping[str, Any] = field(default_factory=dict)
    evaluation: Mapping[str, Any] = field(default_factory=dict)
    promotion: Mapping[str, Any] = field(default_factory=dict)
    strict_reproducibility: bool = True

    def __post_init__(self) -> None:
        identifier(self.name, "name")
        object.__setattr__(self, "seed", integer(self.seed, "seed", minimum=0))
        identifier(self.dataset_version, "dataset_version")
        if self.split_strategy != "physical_sample":
            raise ValueError("split_strategy must be physical_sample")
        if not isinstance(self.strict_reproducibility, bool):
            raise TypeError("strict_reproducibility must be a bool")
        for name in ("representation", "fusion", "acquisition", "evaluation", "promotion"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise TypeError(f"{name} must be a mapping")
            object.__setattr__(self, name, freeze_json(value))
        if self.evaluation.get("split", "validation") not in SPLITS:
            raise ValueError(f"evaluation split must be one of {SPLITS}")
        if not isinstance(self.evaluation.get("require_calibration", False), bool):
            raise TypeError("require_calibration must be a bool")
        allowed = {"minimum_accuracy", "maximum_ece", "maximum_failure_rate"}
        unknown = set(self.promotion) - allowed
        if unknown:
            raise ValueError(f"unknown promotion threshold keys: {sorted(unknown)}")
        for name, value in self.promotion.items():
            finite_number(value, name, minimum=0.0, maximum=1.0)

    @property
    def config_hash(self) -> str:
        """The full SHA-256 identity of the experiment configuration."""
        return sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible configuration snapshot."""
        return {"name": self.name, "seed": self.seed, "dataset_version": self.dataset_version,
                "split_strategy": self.split_strategy,
                "representation": thaw_json(self.representation), "fusion": thaw_json(self.fusion),
                "acquisition": thaw_json(self.acquisition), "evaluation": thaw_json(self.evaluation),
                "promotion": thaw_json(self.promotion),
                "strict_reproducibility": self.strict_reproducibility}

    def to_json(self) -> str:
        """Return deterministic compact JSON."""
        return canonical_json(self.to_dict())
