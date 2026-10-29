"""Completeness and run-binding checks for safe experiment provenance."""
from collections.abc import Mapping
import re
from .base import GateResult, Severity
from .. import __version__
from ..validation.inputs import hash_string, identifier, integer


class ProvenanceGate:
    """Require actual metadata, never infer missing provenance from a gate label."""
    def evaluate(self, provenance: object, *, fingerprint: str = '', expected_identity: object | None = None) -> GateResult:
        """Check required fields and optional exact identity binding."""
        data = provenance.to_dict() if callable(getattr(provenance,'to_dict',None)) else provenance
        required = ('manifest_hash','config_hash','code_revision','package_version','seed','run_id','full_fingerprint','environment')
        if not isinstance(data, Mapping):
            data = {}
        missing = [key for key in required if key not in data or data[key] is None or data[key]=='']
        errors = []
        if not missing:
            try:
                for key in ('manifest_hash','config_hash','full_fingerprint'):
                    hash_string(data[key], name=key)
                identifier(data['code_revision'],name='code revision')
                identifier(data['run_id'],name='run ID')
                if data['run_id']!='run-'+data['full_fingerprint'][:16]:
                    errors.append('run ID does not match full fingerprint')
                integer(data['seed'],name='seed')
                if data['package_version'] != __version__:
                    errors.append('package version mismatch')
                environment = data.get('environment',{})
                if not isinstance(environment,Mapping) or set(environment)!={'python_version','package_version'}:
                    errors.append('unsafe environment summary fields')
                else:
                    for value in environment.values():
                        identifier(value,name='safe environment value')
                    if 'package_version' in environment and environment['package_version'] != __version__:
                        errors.append('environment package version mismatch')
                    if 'python_version' in environment and re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:(?:a|b|rc)[0-9]+)?',environment['python_version']) is None:
                        errors.append('environment Python version must contain only version information')
                if expected_identity is not None:
                    for key in ('manifest_hash','config_hash','code_revision','seed','run_id','full_fingerprint'):
                        if data[key] != getattr(expected_identity,key):
                            errors.append(key+' does not match run identity')
            except (ValueError,TypeError,AttributeError) as error:
                errors.append(str(error))
        passed = not missing and not errors
        return GateResult('ProvenanceGate',passed,Severity.ERROR,
                          'Provenance is complete and bound to the run' if passed else 'Required provenance is missing or inconsistent',
                          {'missing':missing,'errors':errors},fingerprint)
