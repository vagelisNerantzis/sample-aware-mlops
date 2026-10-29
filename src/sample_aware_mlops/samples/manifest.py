"""Immutable dataset membership with deterministic physical-sample content hashes."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from ..provenance.hashes import canonical_json, freeze_json, sha256, thaw_json
from ..validation.inputs import SPLITS, identifier, unique_names
from .registry import SampleRecord


@dataclass(frozen=True)
class DatasetManifest:
    """A complete dataset version with fixed sample membership and modalities."""

    dataset_id: str
    dataset_version: str
    samples: tuple[SampleRecord, ...]
    modalities: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        identifier(self.dataset_id, "dataset_id")
        identifier(self.dataset_version, "dataset_version")
        modalities = unique_names(self.modalities, "modalities")
        if not isinstance(self.samples, (list, tuple)):
            raise TypeError("samples must be a sequence of SampleRecord values")
        samples = tuple(self.samples)
        if not samples:
            raise ValueError("manifest must contain at least one physical sample")
        sample_ids: set[str] = set()
        observation_ids: set[str] = set()
        for sample in samples:
            if not isinstance(sample, SampleRecord):
                raise TypeError("samples must contain SampleRecord values")
            if sample.sample_id in sample_ids:
                raise ValueError("duplicate physical sample_id, including across splits")
            sample_ids.add(sample.sample_id)
            for observation in sample.observations:
                if observation.observation_id in observation_ids:
                    raise ValueError("duplicate observation_id across physical samples")
                observation_ids.add(observation.observation_id)
                if observation.modality not in modalities:
                    raise ValueError(f"unknown observation modality: {observation.modality}")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        object.__setattr__(self, "samples", tuple(sorted(samples, key=lambda item: item.sample_id)))
        object.__setattr__(self, "modalities", tuple(sorted(modalities)))
        object.__setattr__(self, "metadata", freeze_json(self.metadata))

    @property
    def split_ids(self) -> Mapping[str, tuple[str, ...]]:
        """Return immutable physical-sample membership for all three splits."""
        return MappingProxyType({split: tuple(sample.sample_id for sample in self.samples
                                              if sample.split == split) for split in SPLITS})

    @property
    def manifest_hash(self) -> str:
        """The full SHA-256 identity of this canonical manifest."""
        return sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        """Return a stable independent JSON-compatible manifest snapshot."""
        return {"dataset_id": self.dataset_id, "dataset_version": self.dataset_version,
                "modalities": list(self.modalities),
                "samples": [sample.to_dict() for sample in self.samples],
                "metadata": thaw_json(self.metadata)}

    def to_json(self) -> str:
        """Return deterministic compact JSON."""
        return canonical_json(self.to_dict())
