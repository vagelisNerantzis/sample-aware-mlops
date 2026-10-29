"""Declared metric thresholds; absent optional metrics are never fabricated."""
from collections.abc import Mapping
from dataclasses import dataclass
from .base import GateResult, Severity
from ..validation.inputs import finite_number
from ..provenance.hashes import sha256


@dataclass(frozen=True)
class QualityGate:
    """Configured metrics are required; unconfigured metrics are not invented."""
    minimum_accuracy: float | None = None
    maximum_ece: float | None = None
    maximum_failure_rate: float | None = None
    require_calibration: bool = False

    def __post_init__(self) -> None:
        for key in ('minimum_accuracy','maximum_ece','maximum_failure_rate'):
            if getattr(self,key) is not None:
                object.__setattr__(self,key,finite_number(getattr(self,key),name=key,minimum=0,maximum=1))
        if type(self.require_calibration) is not bool:
            raise TypeError('require_calibration must be a boolean')

    def evaluate(self, metrics: Mapping[str,float], *, fingerprint: str = '') -> GateResult:
        """Evaluate supplied bounded metrics and fail explicitly on missing requirements."""
        if not isinstance(metrics,Mapping):
            raise TypeError('metrics must be a mapping')
        requirements = {'accuracy':self.minimum_accuracy,'ece':self.maximum_ece,'failure_rate':self.maximum_failure_rate}
        required = {key for key,value in requirements.items() if value is not None}
        if self.require_calibration:
            required.add('ece')
        missing = sorted(required-set(metrics))
        failed = []
        supplied = {}
        for key in requirements:
            if key in metrics:
                supplied[key] = finite_number(metrics[key],name=key,minimum=0,maximum=1)
                threshold = requirements[key]
                if threshold is not None and ((key=='accuracy' and supplied[key]<threshold) or (key!='accuracy' and supplied[key]>threshold)):
                    failed.append(key)
        passed = not missing and not failed
        return GateResult('QualityGate',passed,Severity.ERROR,
                'Supplied quality metrics meet declared requirements' if passed else 'Quality requirements are missing or failed',
                {'missing':missing,'failed':failed,'observed':supplied,'metrics_hash':sha256(dict(metrics))},fingerprint)
