# PZ-REVIZE SYNC 2.0

SYNC 2.0 replaces snapshot/whole-database synchronization with an append-only change protocol.

## Rules

1. Every device has a permanent `device_id`.
2. Every write receives a client-generated `change_id` (UUID) before any network request.
3. The NAS stores changes as immutable events and keeps tombstones for deletes.
4. A retry with the same `change_id` is idempotent and returns the original result.
5. Clients never replace their working SQLite database with a NAS snapshot during normal sync.
6. Pull is cursor based: `GET changes after cursor`.
7. Push is batch based, but each change is processed independently.
8. A bad record, timeout, duplicate request or conflict cannot cancel unrelated records in the same batch.
9. Changes to different fields of the same entity are merged by three-way comparison.
10. A change to the same field from divergent bases becomes a stored conflict; it does not overwrite either side and does not stop synchronization.
11. Deletes are tombstones. A stale device cannot silently resurrect a deleted entity.
12. Local outbox entries remain until the NAS acknowledges them as `accepted` or `already_applied`.
13. Conflicts have their own queue and can be resolved later without blocking normal synchronization.
14. Server responses contain the new cursor so a client can continue from the last confirmed position.

## Device flow

`local save -> durable outbox -> PUSH -> acknowledge -> PULL -> apply remote events -> advance cursor`

There is no automatic `PULL -> replace DB -> PUSH` cycle.

## Concurrent devices

Example: PC edits customer phone number while tablet edits customer email. Both changes have the same base version but different fields. The server applies both.

If PC and tablet edit the same field from the same base, the server stores one conflict record with both values. The rest of the queue continues normally.

## Required durable client tables

- `sync_device(device_id, created_at)`
- `sync_outbox(change_id, entity, entity_id, payload_json, created_at, retry_count, state)`
- `sync_cursor(stream, cursor)`
- `sync_conflict(conflict_id, change_id, entity, entity_id, fields_json, status)`

## Required NAS tables

- `sync_events(sequence, change_id UNIQUE, device_id, entity, entity_id, kind, payload_json, created_at)`
- `sync_idempotency(change_id PRIMARY KEY, result_json)`
- `sync_tombstones(entity, entity_id, version)`
- `sync_conflicts(conflict_id PRIMARY KEY, change_id, payload_json, status)`

## Error semantics

HTTP/network errors are retryable and do not alter local data.

A conflict is a successful synchronization transport result with a conflict item, not a failed synchronization session.

A malformed record is isolated and reported as `invalid`; other records in the same batch continue.
