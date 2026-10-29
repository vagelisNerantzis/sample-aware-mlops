"""Synchronous stage execution with explicit physical-sample coverage checks."""
from collections.abc import Mapping
from ..adapters.interfaces import StageContext, StageOutput, StageAdapter
from ..experiments.spec import ExperimentSpec
from ..samples.manifest import DatasetManifest
from ..registry.run_registry import RunRegistry


def execute_stages(manifest: DatasetManifest, spec: ExperimentSpec, run_id: str,
                   adapters: Mapping[str,StageAdapter], registry: RunRegistry, *, replay: bool = False) -> tuple[StageOutput,...]:
    """Execute ordered stages; each must return exactly the declared evaluation IDs."""
    names=['representation']+(['acquisition'] if spec.acquisition.get('enabled',False) else [])+['inference','evaluation']
    if type(spec.acquisition.get('enabled',False)) is not bool:
        raise TypeError('acquisition.enabled must be a boolean')
    if any(name not in adapters or not callable(adapters[name]) for name in names):
        raise ValueError('Required stage adapter is missing or not callable')
    ids=manifest.split_ids[spec.evaluation.get('split','validation')]
    if not ids:
        raise ValueError('Selected evaluation cohort must not be empty')
    outputs={}
    for name in names:
        registry.record_event(run_id,'stage.start',{'stage':name,'replay':replay,'sample_ids':list(ids)})
        output=adapters[name](StageContext(manifest,spec,run_id,ids,outputs))
        if not isinstance(output,StageOutput) or output.stage!=name or output.sample_ids!=ids:
            raise ValueError('Stage output must preserve the exact physical-sample cohort and stage identity')
        if name!='evaluation' and output.metrics:
            raise ValueError('Only evaluation may supply promotion metrics')
        for artifact in output.artifacts:
            if artifact.producer_stage!=name or artifact.run_id!=run_id or not set(artifact.sample_ids).issubset(ids):
                raise ValueError('Adapter artifact lineage differs from the stage cohort')
        outputs[name]=output
        registry.record_event(run_id,'stage.end',{'stage':name,'replay':replay,
                    'sample_ids':list(ids),'output_fingerprint':output.fingerprint})
    return tuple(outputs.values())
