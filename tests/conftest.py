"""Small synthetic physical samples shared by the governance tests."""
import pytest

from sample_centric_ml.experiments.spec import ExperimentSpec
from sample_centric_ml.registry.run_registry import create_run_record
from sample_centric_ml.samples.manifest import DatasetManifest
from sample_centric_ml.samples.registry import ObservationRecord, SampleRecord


@pytest.fixture
def samples():
    return tuple(
        SampleRecord(
            sample_id=f"sample-{index}",
            label="class-a" if index % 2 else "class-b",
            split=split,
            observations=tuple(
                ObservationRecord(
                    f"obs-{index}-{modality}", f"sample-{index}", modality,
                    metadata={"features": [3.0, 0.0] if index % 2 else [0.0, 3.0]},
                )
                for modality in ("image", "nir")
            ),
        )
        for index, split in enumerate(
            ("train", "train", "validation", "validation", "test", "test"), 1
        )
    )


@pytest.fixture
def manifest(samples):
    return DatasetManifest("synthetic", "synthetic-v1", samples, ("image", "nir"))


@pytest.fixture
def spec():
    return ExperimentSpec(
        "synthetic-experiment", 7, "synthetic-v1",
        evaluation={"split": "validation", "require_calibration": True},
        promotion={
            "minimum_accuracy": 0.5,
            "maximum_ece": 0.5,
            "maximum_failure_rate": 0.25,
        },
    )


@pytest.fixture
def record(spec, manifest):
    return create_run_record(spec, manifest, "synthetic-revision")
