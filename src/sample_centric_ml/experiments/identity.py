"""Deterministic run IDs preserve the full experiment fingerprint."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..provenance.hashes import sha256
from ..samples.manifest import DatasetManifest
from ..validation.inputs import hash_string, identifier, integer
from .spec import ExperimentSpec


@dataclass(frozen=True)
class RunIdentity:
    """A short readable ID plus full hashes for collision-safe registration."""

    run_id: str
    full_fingerprint: str
    config_hash: str
    manifest_hash: str
    code_revision: str
    seed: int

    def __post_init__(self) -> None:
        identifier(self.run_id, "run_id")
        for name in ("full_fingerprint", "config_hash", "manifest_hash"):
            hash_string(getattr(self, name), name)
        identifier(self.code_revision, "code_revision")
        object.__setattr__(self, "seed", integer(self.seed, "seed", minimum=0))
        if self.run_id != "run-" + self.full_fingerprint[:16]:
            raise ValueError("run_id must match the first 16 characters of full_fingerprint")

    def to_dict(self) -> dict[str, Any]:
        """Return the complete reproducible run identity."""
        return {"run_id": self.run_id, "full_fingerprint": self.full_fingerprint,
                "config_hash": self.config_hash, "manifest_hash": self.manifest_hash,
                "code_revision": self.code_revision, "seed": self.seed}


def build_run_identity(spec: ExperimentSpec, manifest: DatasetManifest,
                       code_revision: str) -> RunIdentity:
    """Bind a seeded specification, dataset membership and logical code revision."""
    if not isinstance(spec, ExperimentSpec) or not isinstance(manifest, DatasetManifest):
        raise TypeError("spec and manifest must be ExperimentSpec and DatasetManifest values")
    identifier(code_revision, "code_revision")
    if spec.dataset_version != manifest.dataset_version:
        raise ValueError("experiment and manifest dataset_version must match")
    fingerprint = sha256({"spec": spec.to_dict(), "manifest_hash": manifest.manifest_hash,
                          "code_revision": code_revision})
    return RunIdentity("run-" + fingerprint[:16], fingerprint, spec.config_hash,
                       manifest.manifest_hash, code_revision, spec.seed)
