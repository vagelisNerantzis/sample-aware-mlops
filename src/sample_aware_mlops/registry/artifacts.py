"""Content-addressed artifact metadata; no binary storage or filesystem paths."""
from dataclasses import dataclass
from ..provenance.hashes import sha256
from ..validation.inputs import identifier, hash_string, unique_names


@dataclass(frozen=True)
class ArtifactMetadata:
    """A logical artifact with its producer run and contributing physical IDs."""
    artifact_id: str
    artifact_type: str
    logical_name: str
    content_hash: str
    producer_stage: str
    run_id: str
    sample_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for key in ('artifact_id','artifact_type','logical_name','producer_stage','run_id'):
            identifier(getattr(self,key), name=key)
        hash_string(self.content_hash, name='artifact content hash')
        object.__setattr__(self, 'sample_ids', tuple(sorted(unique_names(self.sample_ids,name='artifact physical sample IDs'))))

    @property
    def fingerprint(self) -> str:
        """Hash metadata as well as the supplied artifact content reference."""
        return sha256(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """Return metadata only, retaining physical-sample lineage."""
        return {'artifact_id':self.artifact_id,'artifact_type':self.artifact_type,
                'logical_name':self.logical_name,'content_hash':self.content_hash,
                'producer_stage':self.producer_stage,'run_id':self.run_id,'sample_ids':list(self.sample_ids)}
