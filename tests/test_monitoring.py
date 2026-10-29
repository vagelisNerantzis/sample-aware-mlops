"""Monitoring operates on explicit physical-sample IDs, without statistical claims."""
import pytest

from sample_aware_mlops.monitoring.drift import ThresholdDriftRule
from sample_aware_mlops.monitoring.signals import confidence_drift, cost_drift, missing_modality_rate


def test_missing_modality_rate_counts_expected_sample_modality_slots():
    signal = missing_modality_rate(
        {"a": ("image", "nir"), "b": ("image", "nir")},
        {"a": ("image", "nir"), "b": ("image",)},
    )
    assert signal.value == pytest.approx(0.25)
    assert set(signal.sample_ids) == {"a", "b"}


def test_all_missing_modalities_and_complete_modalities_have_expected_rates():
    expected = {"a": ("image", "nir")}
    assert missing_modality_rate(expected, {}).value == 1.0
    assert missing_modality_rate(expected, expected).value == 0.0


@pytest.mark.parametrize("observed", [{"unknown": ("image",)}, {"a": ("undeclared",)}])
def test_missing_modality_rate_rejects_unknown_samples_or_modalities(observed):
    with pytest.raises(ValueError):
        missing_modality_rate({"a": ("image",)}, observed)


def test_missing_modality_rate_rejects_empty_denominator():
    with pytest.raises(ValueError):
        missing_modality_rate({}, {})


def test_confidence_drift_reports_absolute_change_and_both_cohorts():
    signal = confidence_drift({"reference": 0.8}, {"current-a": 0.4, "current-b": 0.6})
    assert signal.value == pytest.approx(0.3)
    assert set(signal.sample_ids) == {"current-a", "current-b"}
    assert signal.reference_sample_ids == ("reference",)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan")])
def test_confidence_drift_rejects_invalid_confidences(value):
    with pytest.raises(ValueError):
        confidence_drift({"reference": 0.5}, {"current": value})


def test_cost_drift_can_report_absolute_or_relative_change():
    assert cost_drift({"a": 2.0}, {"b": 3.0}).value == 1.0
    assert cost_drift({"a": 2.0}, {"b": 3.0}, relative=True).value == 0.5


def test_relative_cost_drift_has_explicit_zero_baseline_behavior():
    assert cost_drift({"a": 0.0}, {"b": 0.0}, relative=True).value == 0.0
    with pytest.raises(ValueError):
        cost_drift({"a": 0.0}, {"b": 1.0}, relative=True)


def test_cost_drift_rejects_negative_cost():
    with pytest.raises(ValueError):
        cost_drift({"a": 1.0}, {"b": -0.1})


def test_monitoring_requires_nonempty_comparison_cohorts():
    for calculate in (confidence_drift, cost_drift):
        with pytest.raises(ValueError):
            calculate({}, {"a": 0.5})


def test_threshold_uses_strict_exceedance_and_preserves_lineage():
    signal = confidence_drift({"a": 0.8}, {"b": 0.5})
    assert not ThresholdDriftRule(signal.value).evaluate(signal).triggered
    result = ThresholdDriftRule(0.2).evaluate(signal)
    assert result.triggered
    assert result.sample_ids == signal.sample_ids
    assert result.reference_sample_ids == signal.reference_sample_ids
    assert result.to_dict()["triggered"] is True


def test_threshold_rejects_invalid_limit():
    with pytest.raises(ValueError):
        ThresholdDriftRule(-0.1)


def test_extreme_finite_costs_do_not_overflow_the_mean():
    import math
    import sys

    maximum = sys.float_info.max
    signal = cost_drift({"a": maximum, "b": maximum, "c": maximum}, {"d": maximum})
    assert math.isfinite(signal.value)
    assert signal.value == 0.0
