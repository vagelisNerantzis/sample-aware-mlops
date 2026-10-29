"""Physical sample overlap detection; observation-row independence is never assumed."""
from collections.abc import Mapping
from itertools import combinations
from .base import GateResult, Severity
from ..validation.inputs import SPLITS, unique_names


class LeakageGate:
    """Require mutually exclusive train/validation/test physical sample memberships."""
    def evaluate(self, split_ids: Mapping[str, object], *, fingerprint: str = '') -> GateResult:
        """Return diagnostic offending IDs for overlaps, duplicates or malformed splits."""
        try:
            if not isinstance(split_ids, Mapping) or set(split_ids)-set(SPLITS):
                raise ValueError('Unknown split names or invalid split mapping')
            if any(isinstance(value,(str,bytes)) for value in split_ids.values()):
                raise ValueError('Split membership must contain physical ID collections, not strings')
            groups = {split:set(unique_names(tuple(split_ids.get(split, ())), name='physical sample IDs', allow_empty=True)) for split in SPLITS}
            overlaps = {f'{a}:{b}':sorted(groups[a]&groups[b]) for a,b in combinations(SPLITS,2) if groups[a]&groups[b]}
            offending = sorted(set().union(*(set(v) for v in overlaps.values()))) if overlaps else []
            return GateResult('LeakageGate',not overlaps,Severity.ERROR,
                    'Physical-sample memberships are disjoint' if not overlaps else 'Physical-sample leakage across splits',
                    {'overlaps':overlaps,'sample_ids':offending},fingerprint)
        except (TypeError,ValueError) as error:
            return GateResult('LeakageGate',False,Severity.ERROR,'Invalid physical-sample membership',{'error':str(error)},fingerprint)
