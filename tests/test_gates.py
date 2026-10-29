"""Blocking scientific gates and explicitly nonblocking warning aggregation."""
from dataclasses import replace

import pytest

from sample_centric_ml.experiments.identity import build_run_identity
from sample_centric_ml.gates.base import GateResult, Severity
from sample_centric_ml.gates.leakage import LeakageGate
from sample_centric_ml.gates.provenance import ProvenanceGate
from sample_centric_ml.gates.quality import QualityGate
from sample_centric_ml.gates.reproducibility import ReproducibilityGate
from sample_centric_ml.gates.runner import run_gates
from sample_centric_ml.provenance.record import build_provenance


def test_disjoint_physical_samples_pass_leakage_gate(manifest):
    assert LeakageGate().evaluate(manifest.split_ids).passed


@pytest.mark.parametrize("pair", [("train", "validation"), ("train", "test"), ("validation", "test")])
def test_shared_physical_sample_fails_for_every_split_pair(pair):
    splits = {"train": ["train-only"], "validation": ["val-only"], "test": ["test-only"]}
    for split in pair:
        splits[split].append("same-physical-sample")
    result = LeakageGate().evaluate(splits)
    assert not result.passed
    assert result.severity == Severity.ERROR
    assert "same-physical-sample" in str(result.diagnostics)


def test_complete_bound_provenance_passes(spec, manifest):
    identity = build_run_identity(spec, manifest, "revision")
    result = ProvenanceGate().evaluate(build_provenance(identity), expected_identity=identity)
    assert result.passed


@pytest.mark.parametrize("field", ["manifest_hash", "code_revision", "package_version", "seed", "environment"])
def test_missing_provenance_is_blocking(field, spec, manifest):
    identity = build_run_identity(spec, manifest, "revision")
    fields = build_provenance(identity).to_dict()
    del fields[field]
    result = ProvenanceGate().evaluate(fields)
    assert not result.passed
    assert result.severity == Severity.ERROR


def test_provenance_from_another_run_is_rejected(spec, manifest):
    expected = build_run_identity(spec, manifest, "revision")
    other = build_run_identity(replace(spec, seed=spec.seed + 1), manifest, "revision")
    assert not ProvenanceGate().evaluate(build_provenance(other), expected_identity=expected).passed


def test_reproducible_identity_passes(spec, manifest):
    identity = build_run_identity(spec, manifest, "revision").to_dict()
    assert ReproducibilityGate().evaluate(identity, dict(identity)).passed


@pytest.mark.parametrize("field", ["seed", "manifest_hash", "code_revision"])
def test_changed_reproducibility_binding_fails(field, spec, manifest):
    reference = build_run_identity(spec, manifest, "revision").to_dict()
    current = dict(reference)
    current[field] = 123 if field == "seed" else "different"
    assert not ReproducibilityGate().evaluate(reference, current).passed


def test_strict_reproducibility_requires_actual_result_fingerprint(spec, manifest):
    identity = build_run_identity(spec, manifest, "revision").to_dict()
    assert not ReproducibilityGate().evaluate(identity, identity, require_result=True).passed
    reference = {**identity, "result_fingerprint": "a" * 64}
    assert ReproducibilityGate().evaluate(reference, reference, require_result=True).passed
    current = {**reference, "result_fingerprint": "b" * 64}
    assert not ReproducibilityGate().evaluate(reference, current, require_result=True).passed


def test_quality_thresholds_accept_boundary_values():
    gate = QualityGate(minimum_accuracy=0.8, maximum_ece=0.1, maximum_failure_rate=0.05, require_calibration=True)
    assert gate.evaluate({"accuracy": 0.8, "ece": 0.1, "failure_rate": 0.05}).passed


@pytest.mark.parametrize("metrics", [
    {"accuracy": 0.79, "ece": 0.1, "failure_rate": 0.05},
    {"accuracy": 0.8, "ece": 0.11, "failure_rate": 0.05},
    {"accuracy": 0.8, "ece": 0.1, "failure_rate": 0.06},
])
def test_each_quality_threshold_can_independently_block(metrics):
    gate = QualityGate(minimum_accuracy=0.8, maximum_ece=0.1, maximum_failure_rate=0.05)
    assert not gate.evaluate(metrics).passed


def test_missing_configured_metric_fails_while_unconfigured_metric_skips():
    assert not QualityGate(minimum_accuracy=0.8).evaluate({}).passed
    assert not QualityGate(require_calibration=True).evaluate({"accuracy": 1.0}).passed
    assert QualityGate().evaluate({}).passed


def test_nonfinite_quality_metric_cannot_pass():
    try:
        result = QualityGate(minimum_accuracy=0.8).evaluate({"accuracy": float("nan")})
    except ValueError:
        return
    assert not result.passed


def test_failed_error_blocks_gate_summary():
    failure = GateResult("failure", False, Severity.ERROR, "blocked")
    summary = run_gates([failure])
    assert not summary.passed
    assert summary.blocking_failures
    assert summary.to_dict()


def test_failed_warning_is_visible_but_does_not_block():
    warning = GateResult("advisory", False, Severity.WARNING, "review recommended")
    summary = run_gates([warning])
    assert summary.passed
    assert summary.warnings
    assert not summary.blocking_failures


def test_duplicate_gate_names_are_not_silently_overwritten():
    result = GateResult("same-name", True, Severity.INFO, "okay")
    with pytest.raises(ValueError):
        run_gates([result, result])


def test_gate_aggregation_is_order_independent():
    left = GateResult("a", True, Severity.INFO, "okay")
    right = GateResult("b", False, Severity.WARNING, "advisory")
    assert run_gates([left, right]).to_dict() == run_gates([right, left]).to_dict()


def test_leakage_gate_rejects_a_string_instead_of_sample_membership_sequence():
    result = LeakageGate().evaluate({"train": "sample-a", "validation": ("sample-b",), "test": ()})
    assert not result.passed
    assert result.severity == Severity.ERROR


@pytest.mark.parametrize("field,value", [("seed", True), ("code_revision", ""), ("run_id", "")])
def test_reproducibility_rejects_equal_but_invalid_identity_fields(field, value, spec, manifest):
    invalid = build_run_identity(spec, manifest, "revision").to_dict()
    invalid[field] = value
    result = ReproducibilityGate().evaluate(invalid, dict(invalid))
    assert not result.passed
    assert result.severity == Severity.ERROR


def test_gate_runner_executes_explicit_bindings_without_ambient_context():
    calls = []
    def bound_gate(name):
        calls.append(name)
        return GateResult(name, True, Severity.INFO, "explicit gate passed")
    summary = run_gates([lambda: bound_gate("b"), lambda: bound_gate("a")])
    assert calls == ["b", "a"]
    assert [result.name for result in summary.results] == ["a", "b"]
    assert summary.passed
