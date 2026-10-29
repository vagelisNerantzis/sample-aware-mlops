"""Deterministic synthetic lifecycle and mandatory fail-closed governance checks."""
from dataclasses import replace
from sample_aware_mlops.samples.registry import ObservationRecord, SampleRecord, SampleRegistry
from sample_aware_mlops.samples.manifest import DatasetManifest
from sample_aware_mlops.experiments.spec import ExperimentSpec
from sample_aware_mlops.registry.run_registry import RunRegistry, create_run_record
from sample_aware_mlops.orchestration.pipeline import run_pipeline
from sample_aware_mlops.gates.leakage import LeakageGate
from sample_aware_mlops.gates.provenance import ProvenanceGate
from sample_aware_mlops.gates.reproducibility import ReproducibilityGate
from sample_aware_mlops.lifecycle.states import LifecycleState
from sample_aware_mlops.monitoring.signals import missing_modality_rate, confidence_drift, cost_drift
from sample_aware_mlops.monitoring.drift import ThresholdDriftRule
from sample_aware_mlops.reporting.summary import format_summary


def synthetic_inputs() -> tuple[DatasetManifest, ExperimentSpec]:
    """Build named synthetic physical entities before any model-stage execution."""
    registry=SampleRegistry()
    splits=('train','train','train','train','validation','validation','test','test')
    for i,split in enumerate(splits):
        sample_id=f'synthetic_{i:03d}';label=i%2
        vector=[3. if coordinate==label else 0. for coordinate in range(2)]
        observations=tuple(ObservationRecord(f'{sample_id}_{name}',sample_id,name,{'features':vector})
                           for name in ('view_a','view_b'))
        registry.add_sample(SampleRecord(sample_id,f'class_{label}',split,observations,
                            acquisition_metadata={'costs':{'view_a':1.,'view_b':2.}}))
    manifest=DatasetManifest('synthetic_scml','1.0.0',registry.list_samples(),('view_a','view_b'))
    spec=ExperimentSpec('synthetic_sample_aware_v1',42,'1.0.0',
          representation={'embedding_dim':8,'adapter':'synthetic-vector-v1'},fusion={'method':'mean'},
          acquisition={'enabled':True,'policy':'greedy','budget':10.},
          evaluation={'split':'validation','require_calibration':True,'class_labels':['class_0','class_1']},
          promotion={'minimum_accuracy':.8,'maximum_ece':.1,'maximum_failure_rate':.1})
    return manifest,spec


def _validation_gates(record, split_ids=None):
    """Build initial actual gate evidence for a single explicitly bound run."""
    return (LeakageGate().evaluate(record.split_ids if split_ids is None else split_ids,fingerprint=record.full_fingerprint),
            ProvenanceGate().evaluate(record.provenance,fingerprint=record.full_fingerprint,expected_identity=record.identity),
            ReproducibilityGate().evaluate(record.identity.to_dict(),record.identity.to_dict(),fingerprint=record.full_fingerprint))


def negative_checks(manifest: DatasetManifest, spec: ExperimentSpec) -> dict[str,bool]:
    """Execute four mandatory negative paths without terminating the successful demo."""
    outcomes={}
    record=create_run_record(spec,manifest,'negative-leakage-v1')
    registry=RunRegistry();registry.add(record)
    splits=dict(record.split_ids);splits['test']=splits['test']+(splits['train'][0],)
    registry.attach_gate_results(record.run_id,_validation_gates(record,splits))
    try:
        registry.transition(record.run_id,LifecycleState.VALIDATED)
    except ValueError:
        outcomes['physical_sample_leakage_blocked']=True
    record=create_run_record(spec,manifest,'negative-provenance-v1',provenance={})
    registry=RunRegistry();registry.add(record)
    registry.attach_gate_results(record.run_id,_validation_gates(record))
    try:
        registry.transition(record.run_id,LifecycleState.VALIDATED)
    except ValueError:
        outcomes['missing_provenance_blocked']=True
    record=create_run_record(spec,manifest,'negative-skip-v1')
    registry=RunRegistry();registry.add(record)
    try:
        registry.transition(record.run_id,LifecycleState.DEPLOYED,
                            deployment={'deployment_id':'simulated-invalid-skip','mode':'simulation'})
    except ValueError:
        outcomes['invalid_lifecycle_jump_blocked']=True
    poor_spec=replace(spec,promotion={'minimum_accuracy':.8,'maximum_ece':0.})
    registry=RunRegistry()
    poor=run_pipeline(manifest,poor_spec,'negative-quality-v1',registry=registry)
    try:
        registry.transition(poor.run_id,LifecycleState.CANDIDATE)
    except ValueError:
        outcomes['poor_quality_blocked']=poor.state==LifecycleState.REJECTED and any(g.name=='QualityGate' and not g.passed for g in poor.gate_results)
    expected={'physical_sample_leakage_blocked','missing_provenance_blocked','invalid_lifecycle_jump_blocked','poor_quality_blocked'}
    assert set(outcomes)==expected and all(outcomes.values()),outcomes
    return outcomes


def main() -> None:
    """Execute the lifecycle, record drift, and print the scientific audit summary."""
    manifest,spec=synthetic_inputs();registry=RunRegistry()
    candidate=run_pipeline(manifest,spec,'synthetic-adapters-v1',registry=registry)
    assert candidate.state==LifecycleState.CANDIDATE
    registry.transition(candidate.run_id,LifecycleState.APPROVED,
                        approval={'decision':'approve','review_id':'synthetic-review-v1'})
    registry.transition(candidate.run_id,LifecycleState.DEPLOYED,
                        deployment={'deployment_id':'local-simulation-v1','mode':'simulation'})
    ids=candidate.evaluation_sample_ids
    expected={sample_id:('view_a','view_b') for sample_id in ids}
    observed={sample_id:('view_a',) if i==0 else ('view_a','view_b') for i,sample_id in enumerate(ids)}
    missing=missing_modality_rate(expected,observed)
    confidence=confidence_drift({sample_id:.95 for sample_id in ids},{sample_id:.75 for sample_id in ids})
    costs=cost_drift({sample_id:1. for sample_id in ids},{sample_id:2. for sample_id in ids})
    for signal,threshold in ((missing,.20),(confidence,.10),(costs,1.5)):
        registry.attach_monitoring(candidate.run_id,ThresholdDriftRule(threshold).evaluate(signal))
    final=registry.transition(candidate.run_id,LifecycleState.MONITORED)
    print('Synthetic control-plane demonstration; deployment is metadata-only simulation.')
    print(format_summary(final))
    print('Intentional negative checks (all must be blocked):')
    for name,passed in sorted(negative_checks(manifest,spec).items()):
        print(f'  {name}: {passed}')
    print('No external data, deployed service, remote write or real model performance claim.')


if __name__=='__main__':
    main()
