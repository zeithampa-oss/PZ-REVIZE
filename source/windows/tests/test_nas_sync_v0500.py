import sqlite3
import tempfile
import unittest
from pathlib import Path

from pzrevize.database import Database
from pzrevize.nas_sync import _pz0500_copy_revision, compare_database_states


class NewSyncMergeTests(unittest.TestCase):
    def _db(self, root, name):
        return Database(root / name)

    def _revision(self, db, number, title):
        with db.connect() as con:
            cur = con.execute(
                "INSERT INTO revisions(revision_no,revision_type,subject,status) VALUES(?,?,?,?)",
                (number, "REVIZE", title, "Rozpracovaná"),
            )
            rid = cur.lastrowid
            con.execute(
                "INSERT INTO circuits(revision_id,designation,name,result) VALUES(?,?,?,?)",
                (rid, "Q1", title, "VYHOVUJE"),
            )
            return rid

    def test_independent_revisions_are_unioned_both_directions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = self._db(root, "a.db")
            b = self._db(root, "b.db")
            self._revision(a, "A", "Revize A")
            self._revision(b, "B", "Revize B")

            # A receives B without losing A.
            with sqlite3.connect(b.path) as cb:
                pass
            self.assertTrue(_pz0500_copy_revision(a.path, b.path, "B"))
            with sqlite3.connect(a.path) as ca:
                self.assertEqual({r[0] for r in ca.execute("SELECT revision_no FROM revisions")}, {"A", "B"})

            # B receives A without losing B.
            self.assertTrue(_pz0500_copy_revision(b.path, a.path, "A"))
            with sqlite3.connect(b.path) as cb:
                self.assertEqual({r[0] for r in cb.execute("SELECT revision_no FROM revisions")}, {"A", "B"})

    def test_same_revision_is_not_copied_over_existing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = self._db(root, "a.db")
            b = self._db(root, "b.db")
            self._revision(a, "A", "Local")
            self._revision(b, "A", "Remote")
            self.assertFalse(_pz0500_copy_revision(a.path, b.path, "A"))
            with sqlite3.connect(a.path) as ca:
                self.assertEqual(ca.execute("SELECT subject FROM revisions WHERE revision_no='A'").fetchone()[0], "Local")

    def test_compare_detects_independent_revisions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = self._db(root, "a.db")
            b = self._db(root, "b.db")
            self._revision(a, "A", "A")
            self._revision(b, "B", "B")
            result = compare_database_states(a.path, b.path)
            self.assertEqual(set(result["local_only_revisions"]), {"A"})
            self.assertEqual(set(result["remote_only_revisions"]), {"B"})
