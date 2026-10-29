"""Small sample-aware stage contracts; no dependency on other portfolio packages."""
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Callable
from ..samples.manifest import DatasetManifest
from ..experiments.spec import ExperimentSpec
from ..provenance.hashes import freeze_json, thaw_json, sha256
from ..registry.artifacts import ArtifactMetadata
from ..validation.inputs import identifier, unique_names, finite_number


@dataclass(frozen=True)
class SampleOutput:
    """One physical sample's stage values; row offsets never replace its ID."""
    sample_id: str
    values: Mapping[str,object]

    def __post_init__(self) -> None:
        identifier(self.sample_id,name='physical sample ID')
        if not isinstance(self.values,Mapping):
            raise TypeError('Sample output values must be a mapping')
        object.__setattr__(self,'values',freeze_json(self.values))

    def to_dict(self) -> dict[str,object]:
        """Serialize explicit identity alongside stage values."""
        return {'sample_id':self.sample_id,'values':thaw_json(self.values)}


@dataclass(frozen=True)
class StageOutput:
    """Canonical physical-sample records plus explicitly covered aggregate metrics."""
    stage: str
    records: tuple[SampleOutput,...]
    metrics: Mapping[str,float] = field(default_factory=dict)
    artifacts: tuple[ArtifactMetadata,...] = ()

    def __post_init__(self) -> None:
        identifier(self.stage,name='stage')
        records=tuple(self.records)
        if not records or any(not isinstance(r,SampleOutput) for r in records):
            raise ValueError('Stage requires nonempty explicit physical sample records')
        unique_names(tuple(r.sample_id for r in records),name='stage physical sample IDs')
        if any(not isinstance(a,ArtifactMetadata) for a in self.artifacts):
            raise TypeError('Stage artifacts must be metadata references')
        object.__setattr__(self,'records',tuple(sorted(records,key=lambda r:r.sample_id)))
        object.__setattr__(self,'metrics',freeze_json({identifier(k,name='metric'):finite_number(v,name=k) for k,v in self.metrics.items()}))
        object.__setattr__(self,'artifacts',tuple(sorted(self.artifacts,key=lambda a:a.artifact_id)))

    @property
    def sample_ids(self) -> tuple[str,...]:
        """Ordered physical identities covered by this stage and its metrics."""
        return tuple(r.sample_id for r in self.records)

    @property
    def fingerprint(self) -> str:
        """Hash values, metrics and metadata references independent of sample row order."""
        return sha256(self.to_dict())

    def to_dict(self) -> dict[str,object]:
        """Export canonical sample-aware adapter output."""
        return {'stage':self.stage,'records':[r.to_dict() for r in self.records],
                'metrics':thaw_json(self.metrics),'artifacts':[a.to_dict() for a in self.artifacts]}


@dataclass(frozen=True)
class StageContext:
    """Immutable inputs and prior outputs for the selected evaluation cohort."""
    manifest: DatasetManifest
    spec: ExperimentSpec
    run_id: str
    sample_ids: tuple[str,...]
    prior_outputs: Mapping[str,StageOutput]

    def __post_init__(self) -> None:
        identifier(self.run_id,name='run ID')
        ids=tuple(sorted(unique_names(self.sample_ids,name='stage context sample IDs')))
        if not set(ids).issubset(s.sample_id for s in self.manifest.samples):
            raise ValueError('Stage context contains unmanifested sample IDs')
        object.__setattr__(self,'sample_ids',ids)
        from types import MappingProxyType
        object.__setattr__(self,'prior_outputs',MappingProxyType(dict(self.prior_outputs)))


StageAdapter = Callable[[StageContext], StageOutput]
