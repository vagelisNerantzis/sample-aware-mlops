"""Lifecycle transitions require current, bound scientific evidence."""
import json
from dataclasses import replace

import pytest

from sample_centric_ml.experiments.identity import build_run_identity
from sample_centric_ml.gates.base import GateResult, Severity
from sample_centric_ml.gates.leakage import LeakageGate
from sample_centric_ml.gates.provenance import ProvenanceGate
from sample_centric_ml.gates.quality import QualityGate
from sample_centric_ml.gates.reproducibility import ReproducibilityGate
from sample_centric_ml.lifecycle.states import LifecycleState, is_allowed_transition
from sample_centric_ml.monitoring.drift import ThresholdDriftRule
from sample_centric_ml.monitoring.signals import confidence_drift
from sample_centric_ml.orchestration.pipeline import run_pipeline
from sample_centric_ml.provenance.record import ProvenanceRecord
from sample_centric_ml.registry.artifacts import ArtifactMetadata
from sample_centric_ml.registry.run_registry import RunRegistry, create_run_record


def _initial_gates(record, spec, manifest):
    identity = build_run_identity(spec, manifest, record.code_revision)
    return (
        LeakageGate().evaluate(record.split_ids, fingerprint=record.full_fingerprint),
        ProvenanceGate().evaluate(record.provenance, fingerprint=record.full_fingerprint, expected_identity=identity),
        ReproducibilityGate().evaluate(identity.to_dict(), identity.to_dict(), fingerprint=record.full_fingerprint),
    )


def _validated_registry(record, spec, manifest):
    registry = RunRegistry()
    registry.add(record)
    registry.attach_gate_results(record.run_id, _initial_gates(record, spec, manifest))
    registry.transition(record.run_id, LifecycleState.VALIDATED)
    return registry


def _candidate_registry(spec, manifest):
    registry = RunRegistry()
    candidate = run_pipeline(manifest, spec, "synthetic-revision", registry=registry)
    assert candidate.state == LifecycleState.CANDIDATE
    return registry, candidate


def _deployed_registry(spec, manifest):
    registry, candidate = _candidate_registry(spec, manifest)
    registry.transition(candidate.run_id, LifecycleState.APPROVED, approval={"decision": "approve", "review_id": "review-1"})
    registry.transition(candidate.run_id, LifecycleState.DEPLOYED, deployment={"deployment_id": "simulation-1", "mode": "simulation"})
    return registry, registry.get(candidate.run_id)


def test_initial_run_is_registered_and_bound_to_manifest(record, manifest):
    assert record.state == LifecycleState.REGISTERED
    assert record.manifest_hash == manifest.manifest_hash
    assert record.evaluation_sample_ids == manifest.split_ids["validation"]
    assert record.to_dict()["run_id"] == record.run_id


def test_registry_duplicate_requires_explicit_idempotence(record):
    registry = RunRegistry()
    registry.add(record)
    with pytest.raises(ValueError):
        registry.add(record)
    registry.add(record, idempotent=True)
    assert len(registry.list_runs()) == 1
    assert json.loads(registry.to_json()) == registry.to_dict()


def test_registry_cannot_insert_an_already_promoted_record(record):
    with pytest.raises(ValueError):
        RunRegistry().add(replace(record, state=LifecycleState.CANDIDATE))


def test_gate_evidence_from_another_run_is_rejected(record):
    registry = RunRegistry()
    registry.add(record)
    result = GateResult("LeakageGate", True, Severity.INFO, "looks okay", evidence_fingerprint="f" * 64)
    with pytest.raises(ValueError):
        registry.attach_gate_results(record.run_id, [result])


def test_known_leakage_failure_cannot_be_replaced_with_a_pass(record):
    registry = RunRegistry()
    registry.add(record)
    failed = GateResult("LeakageGate", False, Severity.ERROR, "known physical-sample leakage", evidence_fingerprint=record.full_fingerprint)
    registry.attach_gate_results(record.run_id, [failed])
    with pytest.raises(ValueError):
        registry.attach_gate_results(record.run_id, [replace(failed, passed=True)])


@pytest.mark.parametrize("sample_ids", [("unknown",), ("sample-5",)])
def test_metrics_reject_unknown_or_wrong_split_sample_ids(sample_ids, record):
    registry = RunRegistry()
    registry.add(record)
    with pytest.raises(ValueError):
        registry.attach_metrics(record.run_id, {"accuracy": 1.0}, sample_ids)


def test_new_metrics_invalidate_stale_quality_and_reproducibility(record):
    registry = RunRegistry()
    registry.add(record)
    previous = (
        GateResult("QualityGate", True, Severity.INFO, "previous", evidence_fingerprint=record.full_fingerprint),
        GateResult("ReproducibilityGate", True, Severity.INFO, "previous", evidence_fingerprint=record.full_fingerprint),
    )
    registry.attach_gate_results(record.run_id, previous)
    registry.attach_metrics(record.run_id, {"accuracy": 1.0, "ece": 0.1, "failure_rate": 0.0}, record.evaluation_sample_ids, result_fingerprint="a" * 64)
    assert not {gate.name for gate in registry.get(record.run_id).gate_results} & {"QualityGate", "ReproducibilityGate"}


def test_candidate_metrics_are_frozen(spec, manifest):
    registry, candidate = _candidate_registry(spec, manifest)
    with pytest.raises(ValueError):
        registry.attach_metrics(candidate.run_id, {"accuracy": 0.0}, candidate.evaluation_sample_ids)


def test_artifacts_bind_run_and_known_physical_sample_ids(record):
    registry = RunRegistry()
    registry.add(record)
    artifact = ArtifactMetadata("artifact-1", "report", "synthetic-report", "a" * 64, "evaluation", record.run_id, record.evaluation_sample_ids)
    registry.attach_artifact(record.run_id, artifact)
    assert len(registry.get(record.run_id).artifacts) == 1
    with pytest.raises(ValueError):
        registry.attach_artifact(record.run_id, replace(artifact, artifact_id="artifact-2", run_id="another-run"))
    with pytest.raises(ValueError):
        registry.attach_artifact(record.run_id, replace(artifact, artifact_id="artifact-3", sample_ids=("unknown",)))


def test_registry_events_preserve_a_serializable_trace(record):
    registry = RunRegistry()
    registry.add(record)
    before = len(registry.get(record.run_id).events)
    registry.record_event(record.run_id, "review-requested", {"review_id": "review-1"})
    assert len(registry.get(record.run_id).events) == before + 1
    assert "review-requested" in registry.to_json()


def test_registered_run_cannot_skip_directly_to_deployed(record):
    registry = RunRegistry()
    registry.add(record)
    assert not is_allowed_transition(LifecycleState.REGISTERED, LifecycleState.DEPLOYED)
    with pytest.raises(ValueError):
        registry.transition(record.run_id, LifecycleState.DEPLOYED, deployment={"deployment_id": "simulation-1", "mode": "simulation"})


def test_missing_provenance_blocks_validation_even_with_forged_passes(spec, manifest):
    record = create_run_record(spec, manifest, "synthetic-revision", provenance=ProvenanceRecord({"seed": spec.seed}))
    registry = RunRegistry()
    registry.add(record)
    forged = [GateResult(name, True, Severity.INFO, "untrusted pass", evidence_fingerprint=record.full_fingerprint) for name in ("LeakageGate", "ProvenanceGate", "ReproducibilityGate")]
    registry.attach_gate_results(record.run_id, forged)
    with pytest.raises(ValueError):
        registry.transition(record.run_id, LifecycleState.VALIDATED)


def test_leakage_cannot_be_hidden_behind_forged_passes(record, spec, manifest):
    splits = dict(record.split_ids)
    splits["test"] = splits["test"] + (splits["train"][0],)
    with pytest.raises(ValueError):
        altered = replace(record, split_ids=splits)
        registry = RunRegistry()
        registry.add(altered)
        forged = [GateResult(name, True, Severity.INFO, "untrusted pass", evidence_fingerprint=record.full_fingerprint) for name in ("LeakageGate", "ProvenanceGate", "ReproducibilityGate")]
        registry.attach_gate_results(record.run_id, forged)
        registry.transition(record.run_id, LifecycleState.VALIDATED)


def test_quality_failure_blocks_candidate(record, spec, manifest):
    registry = _validated_registry(record, spec, manifest)
    metrics = {"accuracy": 0.0, "ece": 1.0, "failure_rate": 1.0}
    registry.attach_metrics(record.run_id, metrics, record.evaluation_sample_ids, result_fingerprint="a" * 64)
    failure = QualityGate(minimum_accuracy=0.5).evaluate(metrics, fingerprint=record.full_fingerprint)
    registry.attach_gate_results(record.run_id, [failure])
    with pytest.raises(ValueError):
        registry.transition(record.run_id, LifecycleState.CANDIDATE)


def test_candidate_requires_explicit_review_metadata(spec, manifest):
    registry, candidate = _candidate_registry(spec, manifest)
    with pytest.raises(ValueError):
        registry.transition(candidate.run_id, LifecycleState.APPROVED)
    registry.transition(candidate.run_id, LifecycleState.APPROVED, approval={"decision": "approve", "review_id": "review-1"})
    assert registry.get(candidate.run_id).state == LifecycleState.APPROVED


def test_deployment_requires_explicit_simulation_metadata(spec, manifest):
    registry, candidate = _candidate_registry(spec, manifest)
    registry.transition(candidate.run_id, LifecycleState.APPROVED, approval={"decision": "approve", "review_id": "review-1"})
    with pytest.raises(ValueError):
        registry.transition(candidate.run_id, LifecycleState.DEPLOYED)
    registry.transition(candidate.run_id, LifecycleState.DEPLOYED, deployment={"deployment_id": "simulation-1", "mode": "simulation"})
    assert registry.get(candidate.run_id).state == LifecycleState.DEPLOYED


def test_monitoring_cannot_precede_deployment(record):
    registry = RunRegistry()
    registry.add(record)
    result = ThresholdDriftRule(0.1).evaluate(confidence_drift({"sample-3": 0.9}, {"sample-4": 0.5}))
    with pytest.raises(ValueError):
        registry.attach_monitoring(record.run_id, result)


def test_deployed_monitoring_rejects_unknown_sample_ids(spec, manifest):
    registry, deployed = _deployed_registry(spec, manifest)
    result = ThresholdDriftRule(0.1).evaluate(confidence_drift({"sample-3": 0.9}, {"unknown": 0.5}))
    with pytest.raises(ValueError):
        registry.attach_monitoring(deployed.run_id, result)


def test_monitored_transition_requires_recorded_sample_aware_signal(spec, manifest):
    registry, deployed = _deployed_registry(spec, manifest)
    with pytest.raises(ValueError):
        registry.transition(deployed.run_id, LifecycleState.MONITORED)
    result = ThresholdDriftRule(0.1).evaluate(confidence_drift({"sample-3": 0.9}, {"sample-4": 0.5}))
    registry.attach_monitoring(deployed.run_id, result)
    registry.transition(deployed.run_id, LifecycleState.MONITORED)
    assert registry.get(deployed.run_id).state == LifecycleState.MONITORED


def test_rejection_is_reasoned_and_terminal(record):
    registry = RunRegistry()
    registry.add(record)
    with pytest.raises(ValueError):
        registry.transition(record.run_id, LifecycleState.REJECTED)
    registry.transition(record.run_id, LifecycleState.REJECTED, reason="scientific evidence failed")
    assert registry.get(record.run_id).state == LifecycleState.REJECTED
    with pytest.raises(ValueError):
        registry.transition(record.run_id, LifecycleState.VALIDATED)


def test_record_display_fields_remain_bound_to_hashed_inputs(record):
    with pytest.raises(ValueError):
        replace(record, experiment_name="another-experiment")
    with pytest.raises(ValueError):
        replace(record, dataset_version="another-version")


def test_public_event_writer_cannot_forge_lifecycle_history(record):
    registry = RunRegistry()
    registry.add(record)
    with pytest.raises(ValueError):
        registry.record_event(record.run_id, "lifecycle", {"state": "DEPLOYED"})
    assert registry.get(record.run_id).state == LifecycleState.REGISTERED
