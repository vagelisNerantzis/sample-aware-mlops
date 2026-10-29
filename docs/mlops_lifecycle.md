# MLOps lifecycle

The lifecycle is explicit:

```text
REGISTERED -> VALIDATED -> CANDIDATE -> APPROVED -> DEPLOYED -> MONITORED
Any pre-deployment state -> REJECTED (terminal)
```

`VALIDATING` is a recorded orchestration event, not another lifecycle enum value.
`REJECTED` is terminal. Monitoring can append evidence to a monitored run, but
re-evaluation requires a new execution rather than resetting a deployed run.

## States

| State | Meaning |
| --- | --- |
| `REGISTERED` | Immutable experiment and dataset identities exist in the registry. |
| `VALIDATED` | Required leakage, provenance, and input-reproducibility evidence passes. |
| `CANDIDATE` | Execution and evaluation are recorded; configured quality and strict result-replay requirements pass. |
| `APPROVED` | An explicit review decision approves this candidate. |
| `DEPLOYED` | Simulation deployment metadata is recorded; no service is launched. |
| `MONITORED` | At least one valid monitoring record is attached after deployment. |
| `REJECTED` | A pre-deployment run is rejected with a recorded reason. |

## Transition contract

| Source -> destination | Required gates / evidence | Required metadata | Failure behavior |
| --- | --- | --- | --- |
| `REGISTERED -> VALIDATED` | Passing `LeakageGate`, `ProvenanceGate`, `ReproducibilityGate`; current split and provenance rechecks | Input hashes, run identity, code revision, seed, package version | Reject transition if evidence is missing, stale, inconsistent, or leaking. |
| `VALIDATED -> CANDIDATE` | All validation gates plus passing `QualityGate`; strict mode also requires matching actual output replay | Metrics with evaluation-sample coverage; deterministic result fingerprint | Reject transition on missing required metrics, threshold violation, or failed result replay. |
| `CANDIDATE -> APPROVED` | Validation and quality requirements remain satisfied | Explicit approval decision and logical review ID | Reject absent / invalid approval or invalid current evidence. |
| `APPROVED -> DEPLOYED` | Validation and quality requirements remain satisfied | Logical deployment ID and `mode: simulation` | Reject absent / invalid metadata or invalid current evidence. |
| `DEPLOYED -> MONITORED` | Existing promotion evidence remains valid | At least one valid sample-aware monitoring result | Reject transition without monitoring evidence. An alert itself does not require rejection. |
| Any pre-deployment state -> `REJECTED` | Rejection is allowed without passing gates | Nonempty reason | Record rejection; future promotion is prohibited. |

A failed transition raises an informative exception and does not advance the
registry state. The orchestration pipeline catches expected gate failures,
records their evidence, and rejects the run. Invalid API use remains an error.
Direct jumps such as `REGISTERED -> DEPLOYED` and resurrection such as
`REJECTED -> APPROVED` are prohibited.

## Evidence rules

A gate result carries the full run fingerprint to which it applies. Results from
another run cannot be attached as promotion evidence. A known leakage failure is
sticky: supplying a later passing result cannot erase evidence that physical
sample independence was violated.

Failed `ERROR` outcomes block aggregate validation. Failed `WARNING` outcomes
remain diagnostics, but lifecycle-required gates must actually pass. Changing
severity does not waive a required gate. Duplicate gate names are rejected by
aggregation so contradictory outcomes are not silently overwritten.

Quality thresholds are inclusive. A configured minimum accuracy requires a
supplied finite accuracy at or above the threshold. Configured maximum ECE or
failure rate requires its metric at or below the threshold. Unconfigured optional
metrics are not invented. Requiring calibration makes missing ECE blocking.

Promotion evaluates the validation cohort declared by the experiment. Test
sample metrics are not used to select or approve a candidate. The pipeline
records a blocking `EvaluationPolicyGate` for non-validation cohorts before
ML stages run; candidate and later promotions recheck this policy. Each metric's
physical sample coverage must match the permitted evaluation cohort.

Before `CANDIDATE`, replacing metrics clears stale quality and strict result-
reproducibility evidence. From `CANDIDATE` onward metrics are frozen. Promotion
rechecks current provenance, membership, and quality instead of trusting an
unbound boolean pass flag.

## Explicit review and simulation deployment

The registry transition API accepts review and deployment records:

```python
from sample_centric_ml.lifecycle.states import LifecycleState

registry.transition(
    run_id,
    LifecycleState.APPROVED,
    approval={"decision": "approve", "review_id": "review-001"},
)
registry.transition(
    run_id,
    LifecycleState.DEPLOYED,
    deployment={"deployment_id": "deployment-001", "mode": "simulation"},
)
```

Review IDs and deployment IDs are logical references, not filesystem locations. These records
make intent explicit, but they do not authenticate a human reviewer or deploy a
production endpoint.

## Monitoring and the next evaluation

After deployment, monitoring records can be attached and the run can enter
`MONITORED`. Current and reference physical sample IDs must belong to the run's
manifest. Unseen samples require explicit lineage registration through a new
manifest and run; live production-data ingestion is not implemented. A threshold
crossing records an advisory alert. It does not alter metrics, undo an approval,
or skip the gates for another experiment.

For a changed configuration, dataset manifest, seed, or code revision, create a
new deterministic run identity and repeat validation. The same inputs produce
the same identity; duplicate execution registration is explicit rather than a
silent overwrite.
