"""Physical samples own observations; derived observations never define splits."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from ..provenance.hashes import canonical_json, freeze_json, thaw_json
from ..validation.inputs import SPLITS, identifier


def _metadata(value: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return freeze_json(value)


@dataclass(frozen=True)
class ObservationRecord:
    """One observation carrying an explicit physical-sample owner."""

    observation_id: str
    sample_id: str
    modality: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        identifier(self.observation_id, "observation_id")
        identifier(self.sample_id, "sample_id")
        identifier(self.modality, "modality")
        object.__setattr__(self, "metadata", _metadata(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible independent snapshot."""
        return {"observation_id": self.observation_id, "sample_id": self.sample_id,
                "modality": self.modality, "metadata": thaw_json(self.metadata)}


@dataclass(frozen=True)
class SampleRecord:
    """A physical sample with one fixed split and immutable observations."""

    sample_id: str
    label: str | None
    split: str
    observations: tuple[ObservationRecord, ...] = ()
    source_id: str | None = None
    acquisition_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        identifier(self.sample_id, "sample_id")
        if self.label is not None:
            identifier(self.label, "label")
        if self.split not in SPLITS:
            raise ValueError(f"split must be one of {SPLITS}")
        if self.source_id is not None:
            identifier(self.source_id, "source_id")
        if not isinstance(self.observations, (list, tuple)):
            raise TypeError("observations must be a sequence of ObservationRecord values")
        observations = tuple(self.observations)
        seen: set[str] = set()
        for observation in observations:
            if not isinstance(observation, ObservationRecord):
                raise TypeError("observations must contain ObservationRecord values")
            if observation.sample_id != self.sample_id:
                raise ValueError("observation sample_id must match its owning physical sample")
            if observation.observation_id in seen:
                raise ValueError("duplicate observation_id within physical sample")
            seen.add(observation.observation_id)
        object.__setattr__(self, "observations", tuple(sorted(
            observations, key=lambda observation: observation.observation_id)))
        object.__setattr__(self, "acquisition_metadata", _metadata(
            self.acquisition_metadata, "acquisition_metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a stable physical-sample snapshot, ordered by observation ID."""
        return {"sample_id": self.sample_id, "label": self.label, "split": self.split,
                "observations": [observation.to_dict() for observation in self.observations],
                "source_id": self.source_id,
                "acquisition_metadata": thaw_json(self.acquisition_metadata)}


class SampleRegistry:
    """Append samples and observations without overwriting physical identity."""

    def __init__(self) -> None:
        self._samples: dict[str, SampleRecord] = {}
        self._observation_ids: set[str] = set()

    def add_sample(self, sample: SampleRecord) -> SampleRecord:
        """Register a new sample; sample and observation IDs are globally unique."""
        if not isinstance(sample, SampleRecord):
            raise TypeError("sample must be a SampleRecord")
        if sample.sample_id in self._samples:
            raise ValueError(f"physical sample already registered: {sample.sample_id}")
        new_ids = {observation.observation_id for observation in sample.observations}
        if self._observation_ids.intersection(new_ids):
            raise ValueError("observation_id already registered to a physical sample")
        self._samples[sample.sample_id] = sample
        self._observation_ids.update(new_ids)
        return sample

    def add_observation(self, sample_id: str, observation: ObservationRecord) -> SampleRecord:
        """Append one new observation and return the replacement immutable sample."""
        sample = self.get(sample_id)
        if not isinstance(observation, ObservationRecord):
            raise TypeError("observation must be an ObservationRecord")
        if observation.sample_id != sample_id:
            raise ValueError("observation sample_id must match its owning physical sample")
        if observation.observation_id in self._observation_ids:
            raise ValueError("observation_id already registered to a physical sample")
        updated = replace(sample, observations=sample.observations + (observation,))
        self._samples[sample_id] = updated
        self._observation_ids.add(observation.observation_id)
        return updated

    def get(self, sample_id: str) -> SampleRecord:
        """Look up a sample by its physical ID; unknown IDs raise KeyError."""
        identifier(sample_id, "sample_id")
        return self._samples[sample_id]

    def list_samples(self) -> tuple[SampleRecord, ...]:
        """Return registered samples in stable physical-ID order."""
        return tuple(self._samples[key] for key in sorted(self._samples))

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible registry snapshot."""
        return {"samples": [sample.to_dict() for sample in self.list_samples()]}

    def to_json(self) -> str:
        """Return deterministic compact JSON."""
        return canonical_json(self.to_dict())
