# Validation report

Validation date: **2026-10-29**. Package version: **0.1.0**.

## Actual environment and installation

- Python **3.11.15**; pytest **9.1.1**.
- Created an isolated local environment with `python -m venv .venv`, without
  system site packages. The application uses only the Python standard library.
- `python -m pip install -e ".[dev]" --disable-pip-version-check --retries 0
  --timeout 15` passed, exit 0. pytest/build dependencies were installed in that
  environment. No other portfolio package or local-path dependency was installed.
- All environment, bytecode, cache, build and diagnostic products were confined
  to ignored storage inside this repository. Dependency installation can use a
  package index; application stages, tests and examples make no network calls.

## Executed checks

| Check | Observed result |
| --- | --- |
| `python -m compileall src tests examples assets` | Passed, exit 0 |
| `pytest -q` | **123 passed, 0 failed, 0 skipped**, no warnings |
| `python examples/run_sample_centric_mlops.py` | Passed, exit 0; final state MONITORED |
| Repeated demo in a fresh process | Identical complete stdout |
| Standalone negative-check helper | All four required operations blocked |
| Canonical manifest ordering | Same SHA-256 for reversed samples/modalities/metadata ordering |
| Deterministic run identity | Same identity for equivalent inputs; seed, revision or sample reassignment changes it |
| Package/version/import assertion | Project, distribution and import all 0.1.0 |
| `python assets/generate_architecture.py` | Passed, exit 0 |
| `python assets/generate_architecture.py --check` | Passed, exit 0 |
| SVG exact bytes and XML parsing | Passed |
| Full workflow YAML / inline version block | Parsed and locally checked; version code executed successfully |

The test count includes additional regressions for concrete audit findings:
name/version binding to hashed inputs, protected lifecycle event kinds, scalar
split-membership rejection, reproducibility identity scalar validation, required
seed/environment provenance and validation-only promotion. Numeric monitoring
checks include maximum finite costs and subnormal baselines. No test threshold
was relaxed; happy-path fixtures contain explicit synthetic numeric observations
rather than expecting a low-quality constant predictor to pass its quality gate.

A focused execution regression also verifies that the gate runner invokes
explicit zero-argument gate bindings in configured order, then returns a
canonical-name-ordered summary. The registry accepts only evaluated GateResult
snapshots, so storing evidence cannot execute hidden callbacks. The final run
completed all 123 cases with no failures, skips or warnings.

## Explicit fail-closed governance results

The demo's negative helper was also executed as a standalone command using the
same public APIs. Actual results:

```text
physical_sample_leakage_blocked: True
missing_provenance_blocked: True
invalid_lifecycle_jump_blocked: True
poor_quality_blocked: True
```

Lifecycle guards require named gate passes regardless of severity. Tests also
verify that
forged pass names do not hide missing provenance or inconsistent splits, known
leakage cannot be overwritten with a pass, stale metric gates are invalidated,
candidate metrics are frozen, stage records preserve exact physical ID coverage,
strict mode re-executes real adapters, and changing adapter output blocks promotion.
Train- or test-based promotion attempts are rejected before any adapter executes.

## Observed complete synthetic lifecycle

The example contains eight artificial physical samples with two observations
each: four train, two validation, two test. No real sample membership is used.
Only the validation cohort is passed through the execution/promotion pipeline.

- Run: `run-b58abbd4c93403e7`.
- Dataset version: `1.0.0`.
- Dataset hash: `53b10d4dfc29f3386e9662a2c524740ae515184850f0a5d64ebe76ed03992c4d`.
- Config hash: `f9002ce660d0c0c8f61104da3875d73b676607d52206cd7ae95b494f12c3424a`.
- Full input fingerprint: `b58abbd4c93403e72c0bcf468f279d966e1eac128e125e957306ffef9b0ad1cc`.
- Result fingerprint: `7f6d14f7a29c730379012ce6748e3f23e57def468155ac9a86f65072181941c7`.
- Passing gates: EvaluationPolicyGate, LeakageGate, ProvenanceGate,
  ReproducibilityGate and QualityGate.
- Actual synthetic validation metrics: accuracy 1.0, ECE approximately
  0.04742587318, failure rate 0.0. These are computed from constructed adapter
  outputs; they are not real-model performance or held-out research results.
- Four sample-linked artifact metadata records: representation, acquisition,
  inference and evaluation. Each covers exactly two validation physical samples.
- Actual lifecycle: REGISTERED -> VALIDATED -> CANDIDATE -> APPROVED -> DEPLOYED
  -> MONITORED. Approval is explicit logical review metadata; deployment is
  explicitly simulation-only and launches no service.
- Monitoring: missing-modality rate 0.25 (threshold 0.20, triggered);
  confidence drift approximately 0.20 (threshold 0.10, triggered);
  cost drift 1.0 (threshold 1.50, not triggered).
- Re-evaluation recommended: True. No automatic retraining, rollback or new
  deployment was performed.

## Reproducibility and lineage

Sample/observation IDs, manifest records, run inputs, stage outputs, metrics,
artifacts and monitoring retain explicit physical-sample identities. Immutable
experiment and manifest snapshots are retained for binding checks. Canonical
JSON and SHA-256 use sorted mappings and canonical sample/observation order.

An explicit standalone check reproduced the same manifest hash/run identity
with reordered input objects, then verified that moving one artificial sample
between partitions changed both dataset hash and run identity. Seed and logical
code revision changes also changed run identity. The full pipeline is replayed
in strict mode and every stage start/end uses deterministic event indices.

Provenance includes only safe software-version environment fields; arbitrary
usernames, hostnames and path-like IDs are rejected by those interfaces. Required
metadata includes dataset/config hashes, seed, supplied code revision, package
version, run ID/full fingerprint and the safe environment summary. Serialized
run provenance also carries lifecycle events and gate outcomes. Free-form caller
metadata still needs a deliberate privacy audit; the framework is not a general
redaction or authentication system.

## Diagram and CI

SVG SHA-256: `1d92e2e01bac4f6bd1fe2d9260f48acce6721e89e7e8718d835710b5287ed064`.

The generator uses only standard-library SVG construction. It renders the same
bytes repeatedly and matches the version-controlled artifact. `.gitattributes`
pins that generated file to LF to preserve reproduction on Windows checkout.
After staging, the exact CI command `git diff --exit-code -- assets/architecture.svg`
passed after regeneration. A Git checkout-index round trip into ignored local
storage also preserved the exact SVG bytes on Windows.

`.github/workflows/tests.yml` targets main pushes and pull requests on Ubuntu,
Python **3.12**, with official checkout/setup-python major v7. It installs the dev
extra, compiles, runs pytest/the demo, regenerates the SVG, checks its Git diff,
and verifies import/distribution version. Workflow parsing rejected duplicate
YAML keys and checked triggers, runner, named steps and embedded Python syntax.
The exact embedded version check was executed locally.

**GitHub-hosted CI has not run.** These are local Python 3.11.15 results; a hosted
Python 3.12/Ubuntu run must occur after publication. The status badge is dynamic
and not a claim of an existing successful run. No secrets, dataset, GPU or
post-install application network connection are required.

## Public-content and scope audit

Public files were scanned for absolute Windows paths, user-home paths, local
file URLs, credential assignments and private artifact extensions. No actual
credentials, API keys, access tokens, private paths, real datasets, model files,
checkpoints or archives are included. Negative fixtures use synthetic values
only. Private environment/log/build metadata is ignored and not staged.

Data/result/artifact/model ignore rules are root-anchored, preserving source,
tests and assets. Only this new repository was written. The scientific source
project and all four existing portfolio repositories were untouched. No remote
configuration, push, tag or release is part of this task.

## Complete final public repository tree

Ignored environments, caches, build metadata and Git internals are excluded.

```text
.gitattributes
.github/workflows/tests.yml
.gitignore
LICENSE
README.md
assets/README.md
assets/architecture.svg
assets/generate_architecture.py
configs/experiment.example.yaml
docs/architecture.md
docs/mlops_lifecycle.md
docs/portfolio_integration.md
docs/validation_report.md
examples/run_sample_centric_mlops.py
pyproject.toml
src/sample_centric_ml/__init__.py
src/sample_centric_ml/adapters/__init__.py
src/sample_centric_ml/adapters/interfaces.py
src/sample_centric_ml/adapters/synthetic.py
src/sample_centric_ml/experiments/__init__.py
src/sample_centric_ml/experiments/identity.py
src/sample_centric_ml/experiments/spec.py
src/sample_centric_ml/gates/__init__.py
src/sample_centric_ml/gates/base.py
src/sample_centric_ml/gates/leakage.py
src/sample_centric_ml/gates/provenance.py
src/sample_centric_ml/gates/quality.py
src/sample_centric_ml/gates/reproducibility.py
src/sample_centric_ml/gates/runner.py
src/sample_centric_ml/lifecycle/__init__.py
src/sample_centric_ml/lifecycle/promotion.py
src/sample_centric_ml/lifecycle/states.py
src/sample_centric_ml/monitoring/__init__.py
src/sample_centric_ml/monitoring/drift.py
src/sample_centric_ml/monitoring/signals.py
src/sample_centric_ml/orchestration/__init__.py
src/sample_centric_ml/orchestration/pipeline.py
src/sample_centric_ml/orchestration/stages.py
src/sample_centric_ml/provenance/__init__.py
src/sample_centric_ml/provenance/hashes.py
src/sample_centric_ml/provenance/record.py
src/sample_centric_ml/registry/__init__.py
src/sample_centric_ml/registry/artifacts.py
src/sample_centric_ml/registry/run_registry.py
src/sample_centric_ml/reporting/__init__.py
src/sample_centric_ml/reporting/summary.py
src/sample_centric_ml/samples/__init__.py
src/sample_centric_ml/samples/manifest.py
src/sample_centric_ml/samples/registry.py
src/sample_centric_ml/validation/__init__.py
src/sample_centric_ml/validation/inputs.py
tests/conftest.py
tests/test_foundation.py
tests/test_gates.py
tests/test_monitoring.py
tests/test_pipeline.py
tests/test_registry_lifecycle.py
```

## Known limitations

- This is a synchronous, in-memory v0.1.0 control plane, not a production platform.
  Registry persistence, authentication, distributed execution, real deployment
  and external model registries are not implemented.
- Synthetic adapters are deliberately small. Representation averages numeric
  observation metadata; optional acquisition chooses one cheapest feasible view;
  inference uses synthetic softmax scores; evaluation calculates small-cohort
  accuracy, top-label ten-bin ECE and failure rate. No real fitting or scientific
  performance claim is made, and no companion repository implementation is copied.
- The pipeline exposes only the declared evaluation cohort as its output contract,
  but external Python adapters are trusted code, not a sandbox. A new real-data
  integration needs independent lineage/content auditing and verified model code.
- Run hashes establish logical consistency, not authenticity of a supplied code
  revision, artifact content or human review. Hashes reference artifact metadata;
  binary payloads are neither stored nor verified from a filesystem here.
- Monitoring is descriptive thresholding, not statistical drift significance.
  Current/reference IDs must be manifested; unseen production samples require a
  newly audited manifest and run. Alerts do not mutate approved metrics or reverse
  an existing deployment lifecycle.
- Required configured metrics fail when missing. Optional absent metrics are
  not invented. Promotion uses validation, never training or held-out test metrics.
- Equivalent canonical typed inputs have stable identities; arbitrary semantic
  equivalence or bitwise reproducibility of external ML libraries is not claimed.
- The YAML file is illustrative; runtime configuration uses typed Python models.
  No YAML parser, NumPy, PyTorch or cloud dependency is required by the application.

## Local Git handoff

Implementation and validation completed before Git initialization. Inspect the
staged public file list, `git status`, and `git diff --cached --check` before the
single local initial commit. The exact CI SVG Git-diff check is repeated after
staging. The final response records the actual commit hash/status; this report
cannot embed its own commit hash without changing that hash.
