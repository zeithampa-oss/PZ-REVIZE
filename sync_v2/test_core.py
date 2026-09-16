import unittest

from sync_v2.core import Change, ChangeKind, SyncEngine


class SyncV2Tests(unittest.TestCase):
    def test_idempotent_retry(self):
        server = SyncEngine("nas")
        change = Change(entity="job", entity_id="J1", kind=ChangeKind.UPSERT, fields={"name": "A"}, device_id="pc")
        first = server.push([change])
        second = server.push([change])
        self.assertEqual(first.accepted, [change.change_id])
        self.assertEqual(second.already_applied, [change.change_id])
        self.assertEqual(server.entities[("job", "J1")].fields["name"], "A")

    def test_unrelated_entities_never_block_each_other(self):
        server = SyncEngine("nas")
        good = Change(entity="job", entity_id="J1", kind=ChangeKind.UPSERT, fields={"name": "A"}, device_id="pc")
        bad = Change(entity="job", entity_id="J1", kind=ChangeKind.UPSERT, fields={"name": "B"}, base_version=0, device_id="tablet")
        other = Change(entity="job", entity_id="J2", kind=ChangeKind.UPSERT, fields={"name": "C"}, device_id="tablet")
        server.push([good])
        result = server.push([bad, other])
        self.assertEqual(result.conflicts[0]["entity_id"], "J1")
        self.assertIn(other.change_id, result.accepted)

    def test_pull_cursor(self):
        server = SyncEngine("nas")
        a = Change(entity="job", entity_id="J1", kind=ChangeKind.UPSERT, fields={"a": 1})
        b = Change(entity="job", entity_id="J2", kind=ChangeKind.UPSERT, fields={"b": 2})
        server.push([a, b])
        events, cursor = server.pull(0)
        self.assertEqual([e.change_id for e in events], [a.change_id, b.change_id])
        self.assertEqual(cursor, 2)

    def test_delete_is_tombstone(self):
        server = SyncEngine("nas")
        create = Change(entity="job", entity_id="J1", kind=ChangeKind.UPSERT, fields={"name": "A"})
        server.push([create])
        delete = Change(entity="job", entity_id="J1", kind=ChangeKind.DELETE, fields={}, base_version=1)
        server.push([delete])
        self.assertTrue(server.entities[("job", "J1")].deleted)
        stale = Change(entity="job", entity_id="J1", kind=ChangeKind.UPSERT, fields={"name": "OLD"}, base_version=1)
        result = server.push([stale])
        self.assertEqual(len(result.conflicts), 1)


if __name__ == "__main__":
    unittest.main()
