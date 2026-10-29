"""Deterministic identity/replay comparisons, not a universal external-model guarantee."""
from collections.abc import Mapping
from .base import GateResult, Severity
from ..validation.inputs import hash_string, identifier, integer


class ReproducibilityGate:
    """Compare required run inputs and, when requested, actual replay result hashes."""
    def evaluate(self, reference: Mapping[str,object], current: Mapping[str,object], *,
                 fingerprint: str = '', require_result: bool = False) -> GateResult:
        """Missing fields fail even when both records omit the same information."""
        keys = ['run_id','full_fingerprint','config_hash','manifest_hash','code_revision','seed']
        if require_result:
            keys.append('result_fingerprint')
        missing = [key for key in keys if key not in reference or key not in current or reference.get(key) is None or current.get(key) is None]
        changed = [key for key in keys if key not in missing and reference[key] != current[key]]
        for key in ('full_fingerprint','config_hash','manifest_hash',*(['result_fingerprint'] if require_result else [])):
            if key not in missing:
                try:
                    hash_string(reference[key],name=key);hash_string(current[key],name=key)
                except (ValueError,TypeError):
                    changed.append(key)
        if not missing:
            for data in (reference,current):
                try:
                    integer(data['seed'],name='seed')
                    identifier(data['code_revision'],name='code revision')
                    identifier(data['run_id'],name='run ID')
                    if data['run_id']!='run-'+data['full_fingerprint'][:16]:
                        changed.append('run_id')
                except (TypeError,ValueError):
                    changed.append('invalid_identity')
        passed = not missing and not changed
        return GateResult('ReproducibilityGate',passed,Severity.ERROR,
                'Required reproducibility fingerprints match' if passed else 'Reproducibility evidence differs or is incomplete',
                {'missing':missing,'changed':sorted(set(changed)),
                 'result_fingerprint':current.get('result_fingerprint')},fingerprint)
