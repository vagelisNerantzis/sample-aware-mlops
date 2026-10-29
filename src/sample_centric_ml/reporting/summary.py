"""Human-readable views of recorded evidence, separate from lifecycle decisions."""
from ..registry.run_registry import RunRecord


def format_summary(record: RunRecord) -> str:
    """Render IDs, gates, metrics, artifact lineage, lifecycle and monitoring."""
    lines=[f'Run: {record.run_id}',f'Experiment: {record.experiment_name}',
           f'Dataset version: {record.dataset_version}',f'Dataset hash: {record.manifest_hash}',
           f'Config hash: {record.config_hash}',f'Reproducibility fingerprint: {record.full_fingerprint}',
           f'Result fingerprint: {record.result_fingerprint}',f'Lifecycle state: {record.state.value}',
           'Validation gates:']
    lines += [f'  [{"PASS" if gate.passed else "FAIL"}] {gate.name}: {gate.message}' for gate in record.gate_results]
    lines += ['Metrics:']+[f'  {name}: {value:.10g}' for name,value in sorted(record.metrics.items())]
    lines += ['Artifacts:']+[f'  {a.logical_name}: {a.content_hash} ({len(a.sample_ids)} physical samples)' for a in record.artifacts]
    lifecycle=[str(event.details['state']) for event in record.events if event.kind=='lifecycle']
    lines += ['Lifecycle: '+' -> '.join(lifecycle),'Monitoring:']
    lines += [f'  {v.signal}: {v.value:.10g}; threshold={v.threshold:.10g}; triggered={v.triggered}' for v in record.monitoring]
    lines += [f'Re-evaluation recommended: {any(v.triggered for v in record.monitoring)}']
    return '\n'.join(lines)
