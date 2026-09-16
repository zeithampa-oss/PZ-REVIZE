from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple


class ChangeKind(str, Enum):
    UPSERT = "upsert"
    DELETE = "delete"


@dataclass(frozen=True)
class Change:
    """One durable, idempotent change produced by a device.

    The change is scoped to one entity and contains only fields changed by the
    user.  base_version is the entity version observed when editing started.
    """

    entity: str
    entity_id: str
    kind: ChangeKind
    fields: Mapping[str, Any] = field(default_factory=dict)
    base_version: int = 0
    change_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = ""
    created_at: float = field(default_factory=time.time)

    def canonical(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "entity": self.entity,
            "entity_id": self.entity_id,
            "kind": self.kind.value,
            "fields": _canonical(self.fields),
            "base_version": self.base_version,
            "device_id": self.device_id,
            "created_at": self.created_at,
        }


@dataclass
class EntityState:
    fields: Dict[str, Any]
    version: int = 0
    deleted: bool = False


@dataclass
class SyncResult:
    accepted: List[str] = field(default_factory=list)
    already_applied: List[str] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    invalid: List[Dict[str, Any]] = field(default_factory=list)
    cursor: int = 0


class SyncEngine:
    """Conflict-safe state engine used by both the NAS and local clients.

    Important properties:
    - never replaces a whole local database with a server snapshot;
    - every change has a client-generated UUID and is idempotent;
    - independent field edits merge automatically;
    - the same field changed from different base versions becomes a recorded
      conflict instead of failing the complete synchronization batch;
    - deletes are tombstones and therefore cannot resurrect silently;
    - a failed/conflicting change never prevents unrelated changes from syncing.
    """

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.entities: Dict[Tuple[str, str], EntityState] = {}
        self.applied: set[str] = set()
        self.conflicts: List[Dict[str, Any]] = []
        self.events: List[Change] = []

    @staticmethod
    def fingerprint(fields: Mapping[str, Any]) -> str:
        raw = json.dumps(_canonical(fields), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def make_change(
        self,
        entity: str,
        entity_id: str,
        fields: Mapping[str, Any],
        *,
        kind: ChangeKind = ChangeKind.UPSERT,
    ) -> Change:
        state = self.entities.get((entity, entity_id))
        return Change(
            entity=entity,
            entity_id=entity_id,
            kind=kind,
            fields=copy.deepcopy(dict(fields)),
            base_version=state.version if state else 0,
            device_id=self.device_id,
        )

    def apply(self, change: Change) -> str:
        """Apply one change locally.

        Returns: applied | already_applied | conflict
        """
        if change.change_id in self.applied:
            return "already_applied"

        key = (change.entity, change.entity_id)
        current = self.entities.get(key)
        if current is None:
            current = EntityState(fields={}, version=0, deleted=False)
            self.entities[key] = current

        if change.kind == ChangeKind.DELETE:
            if current.version != change.base_version and current.fields:
                return self._conflict(change, current, list(current.fields))
            current.deleted = True
            current.version += 1
            self.applied.add(change.change_id)
            self.events.append(change)
            return "applied"

        if current.deleted and change.base_version != current.version:
            return self._conflict(change, current, list(change.fields))

        conflicting_fields: List[str] = []
        if change.base_version != current.version:
            # Field-level merge: fields absent from the incoming change are
            # untouched. A field is conflicting only when its current value
            # differs from the value that existed at the editor's base.
            # The caller may provide _base_values for exact three-way merge.
            base_values = change.fields.get("_base_values", {}) if isinstance(change.fields, Mapping) else {}
            for name, incoming in change.fields.items():
                if name == "_base_values":
                    continue
                base = base_values.get(name, _MISSING)
                existing = current.fields.get(name, _MISSING)
                if base is _MISSING:
                    # No base value supplied: conservative behavior.
                    if existing is not _MISSING and existing != incoming:
                        conflicting_fields.append(name)
                elif existing != base and existing != incoming:
                    conflicting_fields.append(name)

        if conflicting_fields:
            return self._conflict(change, current, conflicting_fields)

        for name, value in change.fields.items():
            if name != "_base_values":
                current.fields[name] = copy.deepcopy(value)
        current.deleted = False
        current.version += 1
        self.applied.add(change.change_id)
        self.events.append(change)
        return "applied"

    def push(self, changes: Iterable[Change]) -> SyncResult:
        result = SyncResult(cursor=len(self.events))
        for change in changes:
            try:
                status = self.apply(change)
            except Exception as exc:  # one bad record must not abort the batch
                result.invalid.append({"change_id": change.change_id, "error": str(exc)})
                continue
            if status == "applied":
                result.accepted.append(change.change_id)
            elif status == "already_applied":
                result.already_applied.append(change.change_id)
            else:
                result.conflicts.append(self.conflicts[-1])
        result.cursor = len(self.events)
        return result

    def pull(self, cursor: int) -> Tuple[List[Change], int]:
        if cursor < 0:
            cursor = 0
        return list(self.events[cursor:]), len(self.events)

    def _conflict(self, change: Change, current: EntityState, fields: List[str]) -> str:
        record = {
            "conflict_id": str(uuid.uuid4()),
            "change_id": change.change_id,
            "entity": change.entity,
            "entity_id": change.entity_id,
            "fields": fields,
            "local_version": current.version,
            "remote_base_version": change.base_version,
            "incoming": _canonical(change.fields),
            "current": _canonical(current.fields),
            "created_at": time.time(),
            "status": "open",
        }
        self.conflicts.append(record)
        return "conflict"


_MISSING = object()


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value
