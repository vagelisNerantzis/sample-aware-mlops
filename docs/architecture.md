# Architecture

The control plane treats a **physical sample** as the unit of lineage and dataset
independence. An **observation** is a measurement of that sample under a modality;
several observations can share a sample ID. A new image, spectrum, crop, or repeat
measurement does not establish another independent sample.

![Control-plane workflow](../assets/architecture.svg)

## Sample and manifest boundary

`SampleRegistry` maintains unique physical sample IDs and globally unique,
explicit observation IDs. Observations carry their sample ID and modality;
unknown sample references, duplicate observations, and silent replacement are
rejected. Registry export is deterministic and JSON-compatible.

`DatasetManifest` snapshots physical samples, observation lineage, known
modalities, dataset version, and split assignments. It validates unique sample
membership and legal train / validation / test splits. Records freeze nested
JSON values so later caller mutation cannot silently change scientific inputs.
The manifest's canonical representation sorts identity-bearing collections and
mapping keys. SHA-256 therefore ignores insertion order while detecting changes
to content, including a physical sample's split.

A manifest describes membership; it does not discover the physical identity of
an incorrectly labeled source dataset. Correct source IDs and observation-to-
sample mappings remain the caller's responsibility.

## Experiment and identity boundary

`ExperimentSpec` captures name, seed, dataset version, physical sample split
strategy, representation, fusion, acquisition, evaluation, promotion thresholds,
and strict reproducibility mode. Typed validation rejects invalid seeds and
thresholds. Its canonical content produces a configuration hash.

`build_run_identity(spec, manifest, code_revision)` combines the full configuration
and manifest hashes with an explicit code revision. The returned identity retains
a readable `run-...` prefix and the complete SHA-256 fingerprint. A manifest
version mismatch is rejected. A revision is supplied evidence, not a claim that
the framework has authenticated a Git checkout.

## Gates and orchestration

Gates produce structured outcomes: name, pass flag, severity, message,
diagnostics, and the run fingerprint to which evidence applies. Aggregation
collects blocking `ERROR` failures and nonblocking `WARNING` diagnostics.
Required promotion gates must pass independently of severity.

The synchronous pipeline records deterministic start / end events and runs four
callable adapters: representation, optional acquisition, inference, and
evaluation. `StageContext` carries the manifest, specification, run ID, selected
physical sample IDs, and prior stage outputs. `SampleOutput` associates values
with one physical sample. `StageOutput` records per-sample outputs, metrics, and
artifact metadata, and derives a deterministic result fingerprint.

Synthetic adapters use numeric observations and return small illustrative
results. Acquisition selects the cheapest single feasible modality within the
configured budget; it is not a complete adaptive acquisition engine. The adapters
do not train or duplicate the companion projects' models.
Validation samples supply default evaluation and promotion evidence; the pipeline
does not select models using test outcomes. `EvaluationPolicyGate` blocks
non-validation cohorts before pipeline execution, and candidate promotion
rechecks that evaluation remains on validation samples. In strict mode the real
adapter sequence is replayed, and its output fingerprint must match. This checks
the executed synthetic computation rather than comparing configuration with
itself. Handled adapter or governance exceptions produce a blocking
`ExecutionGate` and record the exception type only, avoiding private filesystem
paths in an external exception message.

## Registry, provenance, and artifacts

`RunRegistry` stores immutable snapshots. A record includes input identities,
physical sample coverage, per-metric sample coverage, current state, metrics,
gate results, artifacts, deterministic event indices, provenance, monitoring,
and approval / deployment metadata. Each record also retains the immutable
experiment specification and manifest internally. Construction rechecks that
input identity, split membership, evaluation cohort, and promotion policy agree
with these hashed snapshots. Duplicate run IDs require an explicit,
exact-equivalence idempotent path; replacement is not implicit.

The provenance record retains package version, configuration hash, manifest hash,
code revision, seed, run ID, and full fingerprint. Safe environment collection
permits Python and package versions, without collecting usernames, home paths,
or hostnames. Registry serialization includes lifecycle events and gate evidence.
Free-form caller metadata still requires deliberate privacy review.

Artifacts are references with logical identifiers, type, content hash, producer
stage, run association, and physical sample IDs. Unknown sample references and
wrong run associations are rejected. The registry stores metadata only; it is
not a binary model store or a persistent artifact service.

## Promotion boundary

Lifecycle policy permits only the documented next state or pre-deployment
rejection. `REGISTERED -> VALIDATED` requires leakage, provenance, and input
reproducibility checks. `VALIDATED -> CANDIDATE` adds quality evidence and strict
result replay when configured. Approval needs an explicit review decision;
deployment needs simulation metadata; monitoring needs a valid signal record.

Promotion rechecks current provenance, split membership, configured quality
requirements, and evidence association. Known leakage remains blocking. Changes
to metrics before candidate promotion invalidate earlier quality and result
reproducibility results; metrics cannot change from `CANDIDATE` onward. This
prevents attaching a passing metric once and reusing it after changing the run.
See [the transition contract](mlops_lifecycle.md) for exact requirements.

These are application invariants, not tamper-proof authorization. The in-memory
registry is not a security boundary or a durable audit service.

## Monitoring and re-evaluation

Monitoring values and their reference cohorts retain physical sample IDs. The
registry rejects current or reference IDs not present in the run's manifest.
Unseen physical samples require an explicitly reviewed manifest and new run;
live production-data ingestion is outside v0.1.0.

Missing modality rate counts expected sample-by-modality slots, confidence drift
measures absolute mean-confidence shift, and cost drift measures absolute or
relative mean-cost shift. Input validation rejects invalid IDs, negative costs,
and non-finite values. Relative cost drift is the absolute mean-cost shift
divided by reference mean cost. A zero reference and zero current mean yield
zero; a positive current mean with zero reference is undefined and rejected.
Threshold alerts use strict `>` comparison.

A triggered alert motivates review and a new, explicitly identified evaluation
run. It does not mutate a deployed model or bypass promotion gates. No automatic
retraining, rollback, statistical drift significance, distribution drift,
embedding drift, or calibration drift detector is implemented in v0.1.0.

## Scientific implications and limits

Preserving one identity across measurements makes split overlap testable and
keeps metrics, artifacts, and monitoring traceable to the physical samples that
produced them. Canonical manifests bind a report to the actual sample membership,
while promotion gates prevent missing provenance or poor quality evidence from
being treated as an approved experiment.

The framework cannot repair unknown source identity, establish causality from
monitoring alerts, or guarantee numerical reproducibility of future external
models. Persistent storage, asynchronous jobs, distributed execution, cloud
infrastructure, and authenticated deployment are outside this release.


## Gate execution boundary

`run_gates` can execute explicit zero-argument callables that bind each gate to
its domain inputs, or aggregate already evaluated results. Bound calls execute
in configured order; results are sorted by gate name for canonical summaries.
Run registry storage accepts only evaluated `GateResult` records. No callback
is executed implicitly while evidence is stored or serialized.
