"""Finite lifecycle graph; execution stage events are not arbitrary lifecycle jumps."""
from enum import Enum


class LifecycleState(str, Enum):
    """Logical lifecycle only; DEPLOYED records metadata, not an actual deployment."""
    REGISTERED = 'REGISTERED'
    VALIDATED = 'VALIDATED'
    CANDIDATE = 'CANDIDATE'
    APPROVED = 'APPROVED'
    DEPLOYED = 'DEPLOYED'
    MONITORED = 'MONITORED'
    REJECTED = 'REJECTED'


def is_allowed_transition(source: LifecycleState, target: LifecycleState) -> bool:
    """Return whether an edge exists, without bypassing its evidence requirements."""
    source, target = LifecycleState(source), LifecycleState(target)
    edges = {LifecycleState.REGISTERED: {LifecycleState.VALIDATED, LifecycleState.REJECTED},
             LifecycleState.VALIDATED: {LifecycleState.CANDIDATE, LifecycleState.REJECTED},
             LifecycleState.CANDIDATE: {LifecycleState.APPROVED, LifecycleState.REJECTED},
             LifecycleState.APPROVED: {LifecycleState.DEPLOYED, LifecycleState.REJECTED},
             LifecycleState.DEPLOYED: {LifecycleState.MONITORED},
             LifecycleState.MONITORED: set(), LifecycleState.REJECTED: set()}
    return target in edges[source]
