"""Canonical identity and immutable physical-sample lineage guarantees."""
import json
from dataclasses import replace

import pytest

from sample_aware_mlops.experiments.identity import build_run_identity
from sample_aware_mlops.experiments.spec import ExperimentSpec
from sample_aware_mlops.provenance.hashes import canonical_json, freeze_json, sha256, thaw_json
from sample_aware_mlops.provenance.record import ProvenanceRecord, build_provenance
from sample_aware_mlops.samples.manifest import DatasetManifest
from sample_aware_mlops.samples.registry import ObservationRecord, SampleRecord, SampleRegistry


def test_canonical_dictionary_order_does_not_change_hash():
    assert canonical_json({"b": [2, 3], "a": 1}) == canonical_json({"a": 1, "b": (2, 3)})
    assert sha256({"b": 2, "a": 1}) == sha256({"a": 1, "b": 2})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_json_is_rejected(value):
    with pytest.raises((ValueError, TypeError)):
        freeze_json({"value": value})


def test_json_snapshot_has_no_mutable_aliases():
    source = {"nested": [{"value": 3}]}
    frozen = freeze_json(source)
    source["nested"][0]["value"] = 9
    assert thaw_json(frozen) == {"nested": [{"value": 3}]}
    with pytest.raises(TypeError):
        frozen["nested"][0]["value"] = 4


@pytest.mark.parametrize("value", [{1: "bad"}, object()])
def test_nonjson_data_has_no_repr_fallback(value):
    with pytest.raises((ValueError, TypeError)):
        canonical_json(value)


@pytest.mark.parametrize("field", ["observation_id", "sample_id", "modality"])
def test_observation_identifiers_cannot_be_empty(field):
    values = {"observation_id": "obs", "sample_id": "sample", "modality": "image"}
    values[field] = ""
    with pytest.raises(ValueError):
        ObservationRecord(**values)


@pytest.mark.parametrize("split", ["validation-and-test", "", "TRAIN"])
def test_sample_rejects_unknown_split(split):
    with pytest.raises(ValueError):
        SampleRecord("sample", "class-a", split)


def test_observation_cannot_claim_another_parent_sample():
    with pytest.raises(ValueError):
        SampleRecord("sample", "class-a", "train", (ObservationRecord("obs", "other", "image"),))


def test_registry_rejects_duplicate_physical_sample(samples):
    registry = SampleRegistry()
    registry.add_sample(samples[0])
    with pytest.raises(ValueError):
        registry.add_sample(samples[0])


def test_registry_rejects_globally_duplicate_observation(samples):
    registry = SampleRegistry()
    registry.add_sample(samples[0])
    registry.add_sample(SampleRecord("new-sample", "class-a", "train"))
    with pytest.raises(ValueError):
        registry.add_observation("new-sample", ObservationRecord(samples[0].observations[0].observation_id, "new-sample", "image"))


def test_registry_add_observation_preserves_previous_snapshot():
    registry = SampleRegistry()
    initial = SampleRecord("sample", "class-a", "train")
    registry.add_sample(initial)
    registry.add_observation("sample", ObservationRecord("obs", "sample", "nir"))
    assert initial.observations == ()
    assert len(registry.get("sample").observations) == 1
    assert json.loads(registry.to_json()) == registry.to_dict()


def test_registry_unknown_sample_cannot_receive_observations():
    with pytest.raises((ValueError, KeyError)):
        SampleRegistry().add_observation("unknown", ObservationRecord("obs", "unknown", "nir"))


def test_manifest_hash_ignores_sample_and_observation_order(manifest, samples):
    reordered = tuple(replace(sample, observations=tuple(reversed(sample.observations))) for sample in reversed(samples))
    other = DatasetManifest("synthetic", "synthetic-v1", reordered, ("nir", "image"))
    assert manifest.manifest_hash == other.manifest_hash
    assert json.loads(manifest.to_json()) == manifest.to_dict()


def test_manifest_contains_exact_physical_split_membership(manifest):
    assert manifest.split_ids == {
        "train": ("sample-1", "sample-2"),
        "validation": ("sample-3", "sample-4"),
        "test": ("sample-5", "sample-6"),
    }


def test_changed_split_changes_manifest_and_run_identity(manifest, samples, spec):
    changed = DatasetManifest("synthetic", "synthetic-v1", (replace(samples[0], split="validation"),) + samples[1:], ("image", "nir"))
    assert changed.manifest_hash != manifest.manifest_hash
    assert build_run_identity(spec, changed, "revision").run_id != build_run_identity(spec, manifest, "revision").run_id


def test_manifest_rejects_duplicate_physical_sample(samples):
    with pytest.raises(ValueError):
        DatasetManifest("synthetic", "v1", samples + (replace(samples[0], split="test"),), ("image", "nir"))


def test_manifest_rejects_undeclared_modality(samples):
    with pytest.raises(ValueError):
        DatasetManifest("synthetic", "v1", samples, ("image",))


def test_manifest_metadata_is_frozen(samples):
    metadata = {"protocol": {"revision": 1}}
    manifest = DatasetManifest("synthetic", "v1", samples, ("image", "nir"), metadata)
    before = manifest.manifest_hash
    metadata["protocol"]["revision"] = 2
    assert manifest.manifest_hash == before


def test_spec_hash_ignores_configuration_dictionary_order():
    left = ExperimentSpec("exp", 1, "v1", representation={"width": 8, "layers": 2})
    right = ExperimentSpec("exp", 1, "v1", representation={"layers": 2, "width": 8})
    assert left.config_hash == right.config_hash
    assert json.loads(left.to_json()) == left.to_dict()


@pytest.mark.parametrize("seed", [-1, True, 1.5])
def test_spec_seed_requires_nonnegative_integer(seed):
    with pytest.raises((ValueError, TypeError)):
        ExperimentSpec("exp", seed, "v1")


def test_spec_rejects_observation_level_split():
    with pytest.raises(ValueError):
        ExperimentSpec("exp", 1, "v1", split_strategy="observation")


def test_spec_rejects_unknown_promotion_requirement():
    with pytest.raises(ValueError):
        ExperimentSpec("exp", 1, "v1", promotion={"unrecognized_metric": 0.5})


def test_spec_does_not_alias_mutable_configuration():
    settings = {"nested": [1, 2]}
    spec = ExperimentSpec("exp", 1, "v1", representation=settings)
    before = spec.config_hash
    settings["nested"].append(3)
    assert spec.config_hash == before


@pytest.mark.parametrize("change", ["seed", "revision", "configuration"])
def test_run_identity_tracks_scientific_inputs(change, manifest, spec):
    baseline = build_run_identity(spec, manifest, "revision-1")
    changed_spec = replace(spec, seed=spec.seed + 1) if change == "seed" else spec
    if change == "configuration":
        changed_spec = replace(spec, fusion={"strategy": "late"})
    revision = "revision-2" if change == "revision" else "revision-1"
    assert build_run_identity(changed_spec, manifest, revision).full_fingerprint != baseline.full_fingerprint


def test_run_identity_rejects_dataset_version_mismatch(manifest):
    with pytest.raises(ValueError):
        build_run_identity(ExperimentSpec("exp", 1, "different-version"), manifest, "revision")


def test_provenance_records_required_identity_without_machine_details(manifest, spec):
    identity = build_run_identity(spec, manifest, "revision")
    provenance = build_provenance(identity)
    data = provenance.to_dict()
    for key in ("config_hash", "manifest_hash", "code_revision", "seed", "run_id", "full_fingerprint"):
        assert data[key] == identity.to_dict()[key]
    assert data["package_version"] == "0.1.0"
    assert not ({"hostname", "username", "working_directory", "dataset_path"} & data.keys())


def test_provenance_is_an_immutable_json_snapshot():
    source = {"seed": 1, "nested": {"value": 2}}
    record = ProvenanceRecord(source)
    before = record.fingerprint
    source["nested"]["value"] = 3
    assert record.fingerprint == before
    assert json.loads(record.to_json()) == record.to_dict()


def test_provenance_accepts_a_safe_explicit_version_summary(manifest, spec):
    identity = build_run_identity(spec, manifest, "revision")
    provenance = build_provenance(identity, environment={"python_version": "3.12.8", "package_version": "0.1.0"})
    assert provenance.to_dict()["environment"] == {"python_version": "3.12.8", "package_version": "0.1.0"}


@pytest.mark.parametrize("environment", [
    {"hostname": "node"},
    {"python_version": "workstation"},
    {"package_version": "0.0.0"},
])
def test_provenance_environment_rejects_machine_details_or_wrong_version(environment, manifest, spec):
    identity = build_run_identity(spec, manifest, "revision")
    with pytest.raises((ValueError, TypeError)):
        build_provenance(identity, environment=environment)
