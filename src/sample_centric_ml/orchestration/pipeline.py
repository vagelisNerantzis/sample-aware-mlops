"""A synchronous governance pipeline ending at CANDIDATE, never automatic deployment."""
from collections.abc import Mapping
from ..adapters.interfaces import StageAdapter
from ..adapters.synthetic import synthetic_adapters
from ..experiments.spec import ExperimentSpec
from ..samples.manifest import DatasetManifest
from ..gates.base import GateResult, Severity, run_gates
from ..gates.leakage import LeakageGate
from ..gates.provenance import ProvenanceGate
from ..gates.reproducibility import ReproducibilityGate
from ..gates.quality import QualityGate
from ..registry.run_registry import RunRegistry, RunRecord, create_run_record
from ..registry.artifacts import ArtifactMetadata
from ..lifecycle.states import LifecycleState
from ..provenance.hashes import sha256
from ..validation.inputs import hash_string
from .stages import execute_stages


def run_pipeline(manifest: DatasetManifest, spec: ExperimentSpec, code_revision: str,
                 registry: RunRegistry | None = None, adapters: Mapping[str,StageAdapter] | None = None,
                 reference_fingerprint: str | None = None) -> RunRecord:
    """Register, gate, execute/replay, evaluate and propose a candidate; fail closed.

    No fitting, distributed execution, external deployment or approval occurs.
    Strict mode re-executes every supplied adapter and compares actual outputs.
    """
    registry=RunRegistry() if registry is None else registry
    adapters=synthetic_adapters() if adapters is None else dict(adapters)
    if reference_fingerprint is not None:
        hash_string(reference_fingerprint,name='reference result fingerprint')
    record=create_run_record(spec,manifest,code_revision)
    registry.add(record)
    identity=record.identity.to_dict();fp=record.full_fingerprint
    registry.record_event(record.run_id,'validation.start',{'stage':'VALIDATING','sample_ids':list(record.sample_ids)})
    policy_gate=GateResult('EvaluationPolicyGate',
              spec.evaluation.get('split','validation')=='validation' and bool(record.evaluation_sample_ids),
              Severity.ERROR,'Promotion pipeline requires a nonempty validation cohort',
              {'evaluation_split':spec.evaluation.get('split','validation')},fp)
    gates=run_gates((lambda:policy_gate,
           lambda:LeakageGate().evaluate(record.split_ids,fingerprint=fp),
           lambda:ProvenanceGate().evaluate(record.provenance,fingerprint=fp,expected_identity=record.identity),
           lambda:ReproducibilityGate().evaluate(identity,record.identity.to_dict(),fingerprint=fp))).results
    registry.attach_gate_results(record.run_id,gates)
    registry.record_event(record.run_id,'validation.end',{'passed':run_gates(gates).passed})
    if not run_gates(gates).passed:
        return registry.transition(record.run_id,LifecycleState.REJECTED,reason='Initial scientific validation failed')
    registry.transition(record.run_id,LifecycleState.VALIDATED)
    try:
        outputs=execute_stages(manifest,spec,record.run_id,adapters,registry)
        result_fp=sha256([output.to_dict() for output in outputs])
        evaluation=outputs[-1]
        registry.attach_metrics(record.run_id,evaluation.metrics,evaluation.sample_ids,result_fingerprint=result_fp)
        for output in outputs:
            registry.attach_artifact(record.run_id,ArtifactMetadata(
                f'{record.run_id}:{output.stage}:{output.fingerprint[:12]}',
                'metrics' if output.stage=='evaluation' else 'sample-records',
                f'{output.stage}-records',output.fingerprint,output.stage,record.run_id,output.sample_ids))
            for artifact in output.artifacts:
                registry.attach_artifact(record.run_id,artifact)
        replay_fp=result_fp
        if spec.strict_reproducibility:
            replay=execute_stages(manifest,spec,record.run_id,adapters,registry,replay=True)
            replay_fp=sha256([output.to_dict() for output in replay])
        reference={**identity,'result_fingerprint':replay_fp if reference_fingerprint is None else reference_fingerprint}
        current={**identity,'result_fingerprint':result_fp}
        replay_gate=ReproducibilityGate().evaluate(reference,current,fingerprint=fp,
                        require_result=spec.strict_reproducibility or reference_fingerprint is not None)
        quality_gate=QualityGate(**dict(spec.promotion),require_calibration=spec.evaluation.get('require_calibration',False)).evaluate(evaluation.metrics,fingerprint=fp)
        # An external reference cannot hide a failed actual strict replay.
        if spec.strict_reproducibility and replay_fp!=result_fp:
            replay_gate=GateResult('ReproducibilityGate',False,Severity.ERROR,'Actual strict adapter replay changed results',
                                  {'result_fingerprint':result_fp,'replay_fingerprint':replay_fp},fp)
        registry.attach_gate_results(record.run_id,(replay_gate,quality_gate))
        if not run_gates(registry.get(record.run_id).gate_results).passed:
            return registry.transition(record.run_id,LifecycleState.REJECTED,reason='Replay or quality evidence failed')
        return registry.transition(record.run_id,LifecycleState.CANDIDATE)
    except (ValueError,TypeError,KeyError,ArithmeticError) as error:
        # Error messages from external adapters may contain machine paths. Record
        # only the exception type; re-evaluation requires an explicit corrected run.
        failure=GateResult('ExecutionGate',False,Severity.ERROR,'Stage execution or governance failed',
                           {'error_type':type(error).__name__},fp)
        registry.attach_gate_results(record.run_id,(failure,))
        registry.record_event(record.run_id,'stage.error',{'error_type':type(error).__name__})
        return registry.transition(record.run_id,LifecycleState.REJECTED,reason='Stage execution failed')
