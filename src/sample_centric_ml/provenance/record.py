"""Immutable provenance snapshots with an explicit safe environment schema."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import platform
import re
from typing import TYPE_CHECKING, Any

from .hashes import canonical_json, freeze_json, sha256, thaw_json

if TYPE_CHECKING:
    from ..experiments.identity import RunIdentity


@dataclass(frozen=True)
class ProvenanceRecord:
    """A safe snapshot; gates separately verify required provenance evidence."""

    fields: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.fields, Mapping):
            raise TypeError("provenance fields must be a mapping")
        object.__setattr__(self, "fields", freeze_json(self.fields))

    @property
    def fingerprint(self) -> str:
        """Return the full SHA-256 identity of the serialized provenance."""
        return sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible provenance snapshot."""
        return thaw_json(self.fields)

    def to_json(self) -> str:
        """Return deterministic compact JSON."""
        return canonical_json(self.to_dict())


def build_provenance(identity: RunIdentity,
                     environment: Mapping[str, str] | None = None) -> ProvenanceRecord:
    """Capture logical identity and safe software versions without host details.

    Only Python and package versions belong in this environment schema. Runtime
    paths, usernames, machine names and arbitrary environment variables are not
    collected or accepted.
    """
    from .. import __version__
    from ..experiments.identity import RunIdentity
    from ..validation.inputs import identifier

    if not isinstance(identity, RunIdentity):
        raise TypeError("identity must be a RunIdentity")
    versions = {"python_version": platform.python_version(), "package_version": __version__}
    if environment is not None:
        if not isinstance(environment, Mapping):
            raise TypeError("environment must be a mapping")
        if set(environment) - set(versions):
            raise ValueError("environment permits only python_version and package_version")
        for name, value in environment.items():
            identifier(value, name)
            if name == "package_version" and value != __version__:
                raise ValueError("environment package_version must match the running package version")
            if name == "python_version" and not re.fullmatch(
                    r"[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:(?:a|b|rc)[0-9]+)?", value):
                raise ValueError("python_version must contain a numeric software version")
            versions[name] = value
    return ProvenanceRecord({**identity.to_dict(), "package_version": __version__,
                             "environment": versions})
