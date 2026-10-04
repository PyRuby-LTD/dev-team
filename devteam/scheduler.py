"""Inspection-only scheduling boundary for planning records (STORY-001).

Runtime workflow enrollment and explicit Analyse are not implemented yet.
No planning state, body instruction or extension metadata can enable dispatch.
"""
from dataclasses import dataclass
from .backlog import Repository, Snapshot


@dataclass
class Scan:
    snapshot: Snapshot
    blocked: dict
    eligible: tuple = ()


class Scheduler:
    def __init__(self, repository: Repository, engine=None):
        self.repository = repository
        self.engine = engine

    def scan(self):
        snapshot = self.repository.scan()
        blocked = {path: "; ".join(errors) for path, errors in snapshot.errors.items()}
        for path, record in snapshot.records.items():
            reason = "planning record: runtime workflow and explicit customer Analyse required"
            if "manual_edit" in record.metadata:
                reason = "paused for manual editing: validate and resume before managed updates"
            elif record.metadata.get("execution", {}).get("status") in {"failed", "uncertain"}:
                reason = "execution " + record.metadata["execution"]["status"] + "; " + reason
            blocked.setdefault(path, reason)
        return Scan(snapshot, blocked)
