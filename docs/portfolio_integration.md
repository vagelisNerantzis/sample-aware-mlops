# Portfolio integration

Sample-Centric ML supplies the orchestration and governance layer. The companion
repositories describe independently useful scientific components; they are not
installed as dependencies or imported through local paths.

| Repository | Responsibility | Conceptual input | Conceptual output | MLOps role |
| --- | --- | --- | --- | --- |
| [multimodal-representation-learning](https://github.com/vagelisNerantzis/multimodal-representation-learning) | Modality-specific encoders, shared representations, fusion | Sample-linked modality observations and configuration | Sample-linked representations / model metadata | Representation stage adapter |
| [adaptive-modality-acquisition](https://github.com/vagelisNerantzis/adaptive-modality-acquisition) | Cost-aware next-modality selection and stopping | Available modalities, sample representation, costs, budget | Sample-linked acquisition decisions and costs | Optional acquisition stage adapter |
| [multimodal-inference-demo](https://github.com/vagelisNerantzis/multimodal-inference-demo) | Sample-level prediction, uncertainty, reporting | Sample representations / acquired observations | Sample-linked probabilities and inference reports | Inference stage adapter |
| [scientific-ml-benchmarking](https://github.com/vagelisNerantzis/scientific-ml-benchmarking) | Leakage-safe evaluation, calibration, reproducible benchmarking | Physical sample predictions, labels, explicit membership | Metrics, calibration evidence, evaluation provenance | Evaluation stage adapter and evidence producer |
| [sample-centric-ml](https://github.com/vagelisNerantzis/sample-centric-ml) | Lineage, deterministic identity, gates, registry, promotion, monitoring | Manifest, experiment specification, code revision, adapter outputs | Governed run records and sample-aware monitoring reports | Standalone control plane |

## Present adapter contract

A stage receives `StageContext`, which carries the immutable manifest, experiment
specification, run ID, selected physical sample IDs, and prior outputs. It returns
a `StageOutput` containing physical-sample `SampleOutput` records, metrics where
appropriate, and artifact metadata. Logical stage and artifact references retain
the run association and sample coverage.

The v0.1.0 implementation provides small deterministic numeric adapters for
representation, acquisition, inference, and evaluation. Their purpose is to
exercise the orchestration contract and promotion gates on CPU with synthetic
data. The toy acquisition adapter selects the cheapest single feasible modality
within budget. They do not copy encoders, acquisition policies, benchmark
implementations,
or application code from the companion repositories. The illustrative YAML does
not configure or execute those external implementations.

## Requirements for a future integration

A real integration must preserve physical sample and observation IDs through
its input and output boundary. It must declare the model / configuration identity,
report metrics over the authorized evaluation cohort, retain per-metric sample
coverage, and supply content hashes for referenced artifacts. Private paths and
binary artifacts must stay outside public provenance.

An adapter must also define its reproducibility contract. Exact replay is used
for the built-in deterministic adapters. External numerical models may need a
separately specified tolerance-based or statistical check; v0.1.0 does not claim
that these integrations already exist or are bitwise reproducible.

The control plane owns promotion policy and run lineage. The representation,
acquisition, inference, and evaluation components retain their scientific roles.
Neither a companion repository link nor a passing toy demonstration substitutes
for validation of an external model or its dataset.
