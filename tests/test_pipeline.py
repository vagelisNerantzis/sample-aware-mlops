"""Deterministic synthetic orchestration and adapter boundary checks."""
from dataclasses import replace

import pytest

import sample_centric_ml
from sample_centric_ml.adapters.interfaces import SampleOutput, StageOutput
from sample_centric_ml.adapters.synthetic import synthetic_adapters
from sample_centric_ml.lifecycle.states import LifecycleState
from sample_centric_ml.orchestration.pipeline import run_pipeline
from sample_centric_ml.reporting.summary import format_summary


def test_public_package_version():
    assert sample_centric_ml.__version__ == "0.1.0"


def test_repeated_synthetic_pipeline_has_identical_identity_and_results(manifest, spec):
    first = run_pipeline(manifest, spec, "synthetic-revision")
    second = run_pipeline(manifest, spec, "synthetic-revision")
    assert first.run_id == second.run_id
    assert first.result_fingerprint == second.result_fingerprint
    assert first.metrics == second.metrics
    assert first.to_dict() == second.to_dict()


def test_pipeline_stops_at_candidate_with_validation_sample_evidence(manifest, spec):
    result = run_pipeline(manifest, spec, "synthetic-revision")
    assert result.state == LifecycleState.CANDIDATE
    assert set(result.metric_sample_ids) == set(manifest.split_ids["validation"])
    assert set(result.metric_sample_ids).isdisjoint(manifest.split_ids["test"])
    assert {"LeakageGate", "ProvenanceGate", "ReproducibilityGate", "QualityGate"} <= {gate.name for gate in result.gate_results if gate.passed}
    assert all(gate.evidence_fingerprint == result.full_fingerprint for gate in result.gate_results)
    assert result.approval is None or not result.approval
    assert result.deployment is None or not result.deployment


def test_optional_acquisition_is_explicit_and_replayed(manifest, spec):
    calls = []
    adapters = synthetic_adapters()
    acquisition = adapters["acquisition"]

    def tracked(context):
        calls.append(context.run_id)
        return acquisition(context)

    adapters["acquisition"] = tracked
    assert run_pipeline(manifest, spec, "synthetic-revision", adapters=adapters).state == LifecycleState.CANDIDATE
    assert calls == []
    enabled = replace(spec, acquisition={"enabled": True})
    assert run_pipeline(manifest, enabled, "synthetic-revision", adapters=adapters).state == LifecycleState.CANDIDATE
    assert len(calls) >= 2  # The strict mode executes the real adapter again.


def test_mismatched_reference_result_blocks_pipeline(manifest, spec):
    result = run_pipeline(manifest, spec, "synthetic-revision", reference_fingerprint="f" * 64)
    assert result.state == LifecycleState.REJECTED
    assert any(gate.name == "ReproducibilityGate" and not gate.passed for gate in result.gate_results)


def test_strict_replay_detects_nondeterministic_adapter_output(manifest, spec):
    adapters = synthetic_adapters()
    evaluate = adapters["evaluation"]
    counter = 0

    def nondeterministic(context):
        nonlocal counter
        counter += 1
        output = evaluate(context)
        records = tuple(SampleOutput(record.sample_id, {**record.values, "replay_counter": counter}) for record in output.records)
        return replace(output, records=records)

    adapters["evaluation"] = nondeterministic
    result = run_pipeline(manifest, spec, "synthetic-revision", adapters=adapters)
    assert counter >= 2
    assert result.state == LifecycleState.REJECTED
    assert any(gate.name == "ReproducibilityGate" and not gate.passed for gate in result.gate_results)


def test_required_adapter_cannot_be_omitted_silently(manifest, spec):
    adapters = synthetic_adapters()
    del adapters["evaluation"]
    try:
        result = run_pipeline(manifest, spec, "synthetic-revision", adapters=adapters)
    except (ValueError, KeyError):
        return
    assert result.state == LifecycleState.REJECTED


def test_stage_output_rejects_duplicate_physical_sample_records():
    record = SampleOutput("sample", {"value": 1.0})
    with pytest.raises(ValueError):
        StageOutput("representation", (record, record))


def test_adapter_outputs_are_immutable_and_order_independent():
    values = {"embedding": [0.1, 0.2]}
    first = SampleOutput("a", values)
    values["embedding"].append(0.3)
    second = SampleOutput("b", {"embedding": [0.3, 0.4]})
    left = StageOutput("representation", (first, second))
    right = StageOutput("representation", (second, first))
    assert left.fingerprint == right.fingerprint
    assert tuple(first.values["embedding"]) == (0.1, 0.2)
    with pytest.raises(TypeError):
        first.values["new"] = 1


def test_human_summary_identifies_run_state_and_gate_evidence(manifest, spec):
    result = run_pipeline(manifest, spec, "synthetic-revision")
    summary = format_summary(result)
    assert result.run_id in summary
    assert "CANDIDATE" in summary
    assert "LeakageGate" in summary
    assert "QualityGate" in summary


@pytest.mark.parametrize("split", ["train", "test"])
def test_promotion_pipeline_blocks_nonvalidation_before_adapters_execute(split, manifest, spec):
    calls = []

    def forbidden_adapter(context):
        calls.append(context.run_id)
        raise AssertionError("A nonvalidation promotion run must not execute model adapters")

    adapters = {name: forbidden_adapter for name in synthetic_adapters()}
    nonvalidation = replace(spec, evaluation={"split": split, "require_calibration": True})
    result = run_pipeline(manifest, nonvalidation, "synthetic-revision", adapters=adapters)
    assert calls == []
    assert result.state == LifecycleState.REJECTED
    assert any(gate.name == "EvaluationPolicyGate" and not gate.passed for gate in result.gate_results)
