"""Evidence-based lifecycle transitions, without performing external deployment."""
from collections.abc import Mapping
from dataclasses import replace
from ..gates.base import run_gates
from ..gates.leakage import LeakageGate
from ..gates.provenance import ProvenanceGate
from ..gates.quality import QualityGate
from ..validation.inputs import identifier
from ..registry.run_registry import RunRecord, append_event
from .states import LifecycleState, is_allowed_transition


def promote_run(record: RunRecord, target: LifecycleState, *, approval: Mapping[str,object] | None = None,
                deployment: Mapping[str,object] | None = None, reason: str | None = None) -> RunRecord:
    """Validate one legal edge and return a new auditable snapshot; never skip gates.

    Stored gate names cannot hide actual missing provenance, leakage or poor
    metrics. This is logical governance, not a signature/authentication service.
    """
    if not isinstance(record,RunRecord):
        raise TypeError('record must be a RunRecord')
    target=LifecycleState(target)
    if not is_allowed_transition(record.state,target):
        raise ValueError(f'Invalid lifecycle transition {record.state.value} to {target.value}')
    if target==LifecycleState.REJECTED:
        if reason is None:
            raise ValueError('Rejection requires an explicit reason')
        identifier(reason,name='rejection reason')
        return append_event(replace(record,state=target),'lifecycle',{'state':target.value,'reason':reason})
    gates={g.name:g for g in record.gate_results}
    required={'LeakageGate','ProvenanceGate','ReproducibilityGate'}
    if target!=LifecycleState.VALIDATED:
        required.add('QualityGate')
    if not run_gates(record.gate_results).passed or any(name not in gates or not gates[name].passed for name in required):
        raise ValueError('Required blocking gate evidence is missing or failed')
    if any(gates[name].evidence_fingerprint!=record.full_fingerprint for name in required):
        raise ValueError('Required gates are not bound to this run')
    if not LeakageGate().evaluate(record.split_ids).passed:
        raise ValueError('Known physical-sample leakage blocks promotion')
    if not ProvenanceGate().evaluate(record.provenance,expected_identity=record.identity).passed:
        raise ValueError('Missing or inconsistent provenance blocks promotion')
    if target!=LifecycleState.VALIDATED:
        if record.specification.evaluation.get('split','validation')!='validation':
            raise ValueError('Promotion must be based on validation, not train or held-out test metrics')
        if not record.metrics or record.metric_sample_ids!=record.evaluation_sample_ids:
            raise ValueError('Candidate promotion requires complete declared evaluation evidence')
        if not QualityGate(**dict(record.promotion_thresholds),require_calibration=record.require_calibration).evaluate(record.metrics).passed:
            raise ValueError('Current metrics fail the immutable quality policy')
        if record.strict_reproducibility and (record.result_fingerprint is None or gates['ReproducibilityGate'].diagnostics.get('result_fingerprint')!=record.result_fingerprint):
            raise ValueError('Strict promotion requires a matching actual replay fingerprint')
    updated=record
    if target==LifecycleState.APPROVED:
        if not isinstance(approval,Mapping) or approval.get('decision')!='approve':
            raise ValueError('Approval requires an explicit approve decision')
        identifier(approval.get('review_id'),name='logical review ID')
        updated=replace(updated,approval=approval)
    if target==LifecycleState.DEPLOYED:
        if not record.approval:
            raise ValueError('Deployment requires recorded approval')
        if not isinstance(deployment,Mapping) or deployment.get('mode')!='simulation':
            raise ValueError('Deployment metadata must explicitly describe simulation mode')
        identifier(deployment.get('deployment_id'),name='logical deployment ID')
        updated=replace(updated,deployment=deployment)
    if target==LifecycleState.MONITORED and not record.monitoring:
        raise ValueError('MONITORED requires at least one valid sample-aware monitoring result')
    return append_event(replace(updated,state=target),'lifecycle',{'state':target.value})
