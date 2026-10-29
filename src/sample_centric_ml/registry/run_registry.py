"""In-memory immutable run snapshots; all official state updates are governed."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from ..experiments.identity import RunIdentity, build_run_identity
from ..experiments.spec import ExperimentSpec
from ..samples.manifest import DatasetManifest
from ..provenance.hashes import canonical_json, freeze_json, thaw_json
from ..provenance.record import ProvenanceRecord, build_provenance
from ..validation.inputs import SPLITS, identifier, unique_names, integer, finite_number, hash_string
from ..gates.base import GateResult, run_gates
from ..monitoring.drift import MonitoringResult
from ..lifecycle.states import LifecycleState
from .artifacts import ArtifactMetadata


@dataclass(frozen=True)
class RunEvent:
    """A deterministic local event index, never a timestamp or random UUID."""
    index: int
    kind: str
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        integer(self.index, name='event index', minimum=1)
        identifier(self.kind, name='event kind')
        object.__setattr__(self, 'details', freeze_json(self.details))

    def to_dict(self) -> dict[str, object]:
        """Return event details without collecting machine context."""
        return {'index':self.index,'kind':self.kind,'details':thaw_json(self.details)}


@dataclass(frozen=True)
class RunRecord:
    """Immutable run evidence; hashes identify inputs, result hash identifies outputs."""
    identity: RunIdentity
    experiment_name: str
    dataset_version: str
    sample_ids: tuple[str, ...]
    split_ids: Mapping[str, tuple[str, ...]]
    evaluation_sample_ids: tuple[str, ...]
    provenance: ProvenanceRecord
    promotion_thresholds: Mapping[str, float] = field(default_factory=dict)
    require_calibration: bool = False
    strict_reproducibility: bool = True
    state: LifecycleState = LifecycleState.REGISTERED
    metrics: Mapping[str, float] = field(default_factory=dict)
    metric_sample_ids: tuple[str, ...] = ()
    gate_results: tuple[GateResult, ...] = ()
    artifacts: tuple[ArtifactMetadata, ...] = ()
    events: tuple[RunEvent, ...] = ()
    result_fingerprint: str | None = None
    monitoring: tuple[MonitoringResult, ...] = ()
    approval: Mapping[str, object] = field(default_factory=dict)
    deployment: Mapping[str, object] = field(default_factory=dict)
    specification: ExperimentSpec | None = None
    manifest: DatasetManifest | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, RunIdentity):
            raise TypeError('identity must be a RunIdentity')
        identifier(self.experiment_name,name='experiment name');identifier(self.dataset_version,name='dataset version')
        ids = tuple(sorted(unique_names(self.sample_ids,name='physical sample IDs')))
        evaluation_ids = tuple(sorted(unique_names(self.evaluation_sample_ids,name='evaluation sample IDs',allow_empty=True)))
        if not set(evaluation_ids).issubset(ids):
            raise ValueError('Evaluation IDs must belong to manifested physical samples')
        if not isinstance(self.split_ids,Mapping) or set(self.split_ids)!=set(SPLITS):
            raise ValueError('Run split evidence must explicitly contain train/validation/test')
        groups = {key:tuple(sorted(unique_names(self.split_ids[key],name='split IDs',allow_empty=True))) for key in SPLITS}
        if set().union(*(set(group) for group in groups.values())) != set(ids):
            raise ValueError('Run split IDs must cover exactly the physical sample registry')
        if type(self.require_calibration) is not bool or type(self.strict_reproducibility) is not bool:
            raise TypeError('Run policy flags must be booleans')
        if not isinstance(self.specification,ExperimentSpec) or not isinstance(self.manifest,DatasetManifest):
            raise ValueError('Run must retain its immutable experiment and dataset evidence')
        if self.experiment_name!=self.specification.name or self.dataset_version!=self.manifest.dataset_version:
            raise ValueError('Run names/versions must match the hashed specification and manifest')
        expected = build_run_identity(self.specification,self.manifest,self.code_revision)
        if expected != self.identity or ids != tuple(s.sample_id for s in self.manifest.samples):
            raise ValueError('Run identity or physical IDs differ from immutable input evidence')
        if groups != dict(self.manifest.split_ids) or evaluation_ids != groups[self.specification.evaluation.get('split','validation')]:
            raise ValueError('Run split evidence differs from the hashed manifest/specification')
        if dict(self.promotion_thresholds)!=dict(self.specification.promotion) or self.require_calibration!=self.specification.evaluation.get('require_calibration',False) or self.strict_reproducibility!=self.specification.strict_reproducibility:
            raise ValueError('Run promotion policy differs from its hashed specification')
        metrics = {identifier(key,name='metric'):finite_number(value,name=key) for key,value in self.metrics.items()}
        metric_ids = tuple(sorted(unique_names(self.metric_sample_ids,name='metric sample IDs',allow_empty=True)))
        if not set(metric_ids).issubset(ids) or (metrics and not metric_ids):
            raise ValueError('Metric records require contributing known physical sample IDs')
        if any(not isinstance(g,GateResult) for g in self.gate_results):
            raise TypeError('Stored gate evidence must contain evaluated GateResult records')
        gates = run_gates(self.gate_results).results
        if any(g.evidence_fingerprint!=self.full_fingerprint for g in gates):
            raise ValueError('Gate evidence fingerprint differs from this run')
        if self.result_fingerprint is not None:
            hash_string(self.result_fingerprint,name='result fingerprint')
        provenance = self.provenance if isinstance(self.provenance,ProvenanceRecord) else ProvenanceRecord(self.provenance)
        if any(not isinstance(a,ArtifactMetadata) or a.run_id!=self.run_id or not set(a.sample_ids).issubset(ids) for a in self.artifacts):
            raise ValueError('Artifact lineage must belong to its producing run and physical samples')
        if len({a.artifact_id for a in self.artifacts})!=len(self.artifacts):
            raise ValueError('Duplicate artifact IDs')
        if any(not isinstance(v,MonitoringResult) for v in self.monitoring):
            raise TypeError('monitoring must contain structured MonitoringResult records')
        if any(not set(v.sample_ids).issubset(ids) or not set(v.reference_sample_ids).issubset(ids) for v in self.monitoring):
            raise ValueError('Monitoring IDs must have known manifested physical-sample lineage')
        if any(not isinstance(event,RunEvent) or event.index!=i+1 for i,event in enumerate(self.events)):
            raise ValueError('Event indices must be contiguous and start at one')
        for key,value in [('sample_ids',ids),('evaluation_sample_ids',evaluation_ids),('split_ids',freeze_json(groups)),
                          ('metric_sample_ids',metric_ids),('metrics',freeze_json(metrics)),('gate_results',gates),
                          ('provenance',provenance),('state',LifecycleState(self.state)),('artifacts',tuple(self.artifacts)),
                          ('events',tuple(self.events)),('monitoring',tuple(self.monitoring)),
                          ('promotion_thresholds',freeze_json(self.promotion_thresholds)),
                          ('approval',freeze_json(self.approval)),('deployment',freeze_json(self.deployment))]:
            object.__setattr__(self,key,value)

    @property
    def run_id(self) -> str:
        """Readable deterministic input identity."""
        return self.identity.run_id

    @property
    def full_fingerprint(self) -> str:
        """Full input fingerprint retained to detect readable-prefix collisions."""
        return self.identity.full_fingerprint

    @property
    def config_hash(self) -> str:
        """Canonical experiment configuration hash."""
        return self.identity.config_hash

    @property
    def manifest_hash(self) -> str:
        """Dataset version, lineage and split-membership hash."""
        return self.identity.manifest_hash

    @property
    def code_revision(self) -> str:
        """Explicit supplied code identifier, not an inferred local path."""
        return self.identity.code_revision

    @property
    def seed(self) -> int:
        """Declared experiment seed."""
        return self.identity.seed

    def to_dict(self) -> dict[str, object]:
        """Serialize the run, with lifecycle and gate history also in provenance."""
        provenance = self.provenance.to_dict()
        provenance.update(lifecycle_events=[v.to_dict() for v in self.events],
                          gate_results=[v.to_dict() for v in self.gate_results])
        return {**self.identity.to_dict(),'experiment_name':self.experiment_name,'dataset_version':self.dataset_version,
                'state':self.state.value,'sample_ids':list(self.sample_ids),'split_ids':thaw_json(self.split_ids),
                'evaluation_sample_ids':list(self.evaluation_sample_ids),'metrics':thaw_json(self.metrics),
                'metric_sample_ids':list(self.metric_sample_ids),'gate_results':[g.to_dict() for g in self.gate_results],
                'artifacts':[a.to_dict() for a in self.artifacts],'events':[v.to_dict() for v in self.events],
                'provenance':provenance,'result_fingerprint':self.result_fingerprint,
                'monitoring':[v.to_dict() for v in self.monitoring],
                'approval':thaw_json(self.approval),'deployment':thaw_json(self.deployment),
                'promotion_thresholds':thaw_json(self.promotion_thresholds),
                'strict_reproducibility':self.strict_reproducibility,'require_calibration':self.require_calibration}


def append_event(record: RunRecord, kind: str, details: Mapping[str,object]) -> RunRecord:
    """Return a snapshot with the next deterministic event index."""
    return replace(record,events=record.events+(RunEvent(len(record.events)+1,kind,details),))


def create_run_record(spec: ExperimentSpec, manifest: DatasetManifest, code_revision: str,
                      provenance: ProvenanceRecord | Mapping[str,object] | None = None) -> RunRecord:
    """Construct REGISTERED evidence without registering or promoting it implicitly."""
    identity = build_run_identity(spec,manifest,code_revision)
    return RunRecord(identity,spec.name,manifest.dataset_version,tuple(s.sample_id for s in manifest.samples),
                manifest.split_ids,manifest.split_ids[spec.evaluation.get('split','validation')],
                build_provenance(identity) if provenance is None else provenance,
                promotion_thresholds=spec.promotion,require_calibration=spec.evaluation.get('require_calibration',False),
                strict_reproducibility=spec.strict_reproducibility,
                events=(RunEvent(1,'lifecycle',{'state':'REGISTERED'}),),specification=spec,manifest=manifest)


class RunRegistry:
    """Immutable snapshots with explicit writes and guarded lifecycle transitions."""
    def __init__(self) -> None:
        self._runs: dict[str,RunRecord] = {}

    def add(self, record: RunRecord, *, idempotent: bool = False) -> RunRecord:
        """Register once; exact equivalent repeats require explicit idempotent=True."""
        if not isinstance(record,RunRecord):
            raise TypeError('record must be a RunRecord')
        if record.run_id in self._runs:
            if idempotent and self._runs[record.run_id].to_dict()==record.to_dict():
                return self._runs[record.run_id]
            raise ValueError('Duplicate run ID or readable-prefix collision')
        if record.state!=LifecycleState.REGISTERED:
            raise ValueError('New registry entries must start REGISTERED')
        self._runs[record.run_id]=record
        return record

    def get(self, run_id: str) -> RunRecord:
        """Return a frozen registered snapshot; unknown IDs raise KeyError."""
        return self._runs[identifier(run_id,name='run ID')]

    def list_runs(self) -> tuple[RunRecord, ...]:
        """List snapshots in deterministic run-ID order."""
        return tuple(self._runs[key] for key in sorted(self._runs))

    def record_event(self, run_id: str, kind: str, details: Mapping[str,object]) -> RunRecord:
        """Attach a deterministic stage/audit event without changing lifecycle."""
        if kind in {'lifecycle','gates','metrics','artifact','monitoring'}:
            raise ValueError('Governed event kinds require their dedicated registry operation')
        record=append_event(self.get(run_id),kind,details);self._runs[run_id]=record;return record

    def attach_gate_results(self, run_id: str, results: Sequence[GateResult]) -> RunRecord:
        """Bind gate evidence; a known leakage failure cannot be silently overwritten."""
        record=self.get(run_id)
        if record.state not in (LifecycleState.REGISTERED,LifecycleState.VALIDATED):
            raise ValueError('Gate evidence is frozen after candidate promotion or rejection')
        if any(not isinstance(g,GateResult) for g in results):
            raise TypeError('Registry gate attachment requires evaluated GateResult records')
        supplied=run_gates(results).results
        values={g.name:g for g in record.gate_results}
        for gate in supplied:
            if gate.evidence_fingerprint!=record.full_fingerprint:
                raise ValueError('Gate belongs to a different run fingerprint')
            if gate.name=='LeakageGate' and gate.passed and gate.name in values and not values[gate.name].passed:
                raise ValueError('Known leakage failure requires corrected inputs and a new run')
            values[gate.name]=gate
        updated=replace(record,gate_results=tuple(values.values()))
        updated=append_event(updated,'gates',{'results':[g.to_dict() for g in supplied]})
        self._runs[run_id]=updated;return updated

    def attach_metrics(self, run_id: str, metrics: Mapping[str,float], sample_ids: Sequence[str],
                       result_fingerprint: str | None = None) -> RunRecord:
        """Replace pre-candidate metrics explicitly, invalidating old quality/replay gates."""
        record=self.get(run_id)
        if record.state not in (LifecycleState.REGISTERED,LifecycleState.VALIDATED):
            raise ValueError('Metrics are immutable from CANDIDATE onward')
        ids=tuple(sorted(unique_names(sample_ids,name='metric physical sample IDs')))
        if ids!=record.evaluation_sample_ids:
            raise ValueError('Metric sample IDs must equal the declared evaluation partition')
        gates=tuple(g for g in record.gate_results if g.name not in ('QualityGate','ReproducibilityGate'))
        updated=replace(record,metrics=metrics,metric_sample_ids=ids,result_fingerprint=result_fingerprint,gate_results=gates)
        updated=append_event(updated,'metrics',{'sample_ids':list(ids),'metrics':dict(metrics),'result_fingerprint':result_fingerprint})
        self._runs[run_id]=updated;return updated

    def attach_artifact(self, run_id: str, artifact: ArtifactMetadata) -> RunRecord:
        """Attach metadata with producer-run and physical-sample lineage checks."""
        record=self.get(run_id)
        if record.state not in (LifecycleState.REGISTERED,LifecycleState.VALIDATED):
            raise ValueError('Artifacts are frozen from candidate promotion onward')
        updated=replace(record,artifacts=record.artifacts+(artifact,))
        updated=append_event(updated,'artifact',artifact.to_dict());self._runs[run_id]=updated;return updated

    def transition(self, run_id: str, target: LifecycleState, *, approval: Mapping[str,object] | None = None,
                   deployment: Mapping[str,object] | None = None, reason: str | None = None) -> RunRecord:
        """Use the promotion guard for every official registry lifecycle change."""
        from ..lifecycle.promotion import promote_run
        updated=promote_run(self.get(run_id),target,approval=approval,deployment=deployment,reason=reason)
        self._runs[run_id]=updated;return updated

    def attach_monitoring(self, run_id: str, result: MonitoringResult) -> RunRecord:
        """Attach sample-aware monitoring only to simulated deployed/monitored runs."""
        record=self.get(run_id)
        if record.state not in (LifecycleState.DEPLOYED,LifecycleState.MONITORED):
            raise ValueError('Monitoring requires a deployed run')
        if not isinstance(result,MonitoringResult):
            raise TypeError('result must be a MonitoringResult')
        updated=replace(record,monitoring=record.monitoring+(result,))
        updated=append_event(updated,'monitoring',result.to_dict());self._runs[run_id]=updated;return updated

    def to_dict(self) -> dict[str,object]:
        """Export independent canonical-order run snapshots."""
        return {'runs':[record.to_dict() for record in self.list_runs()]}

    def to_json(self) -> str:
        """Serialize deterministically without filesystem or wall-clock state."""
        return canonical_json(self.to_dict())
