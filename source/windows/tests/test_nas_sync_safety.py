import sqlite3
import tempfile
import unittest
from pathlib import Path

from pzrevize.database import Database
from pzrevize.nas_sync import _pz0500_copy_revision, compare_database_states


class NasSyncSafetyTests(unittest.TestCase):
    def _make_db(self, root, name):
        return Database(root / name)

    def _add_revision(self, db, number, subject):
        with db.connect() as con:
            cur = con.execute(
                "INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)",
                (number, "REVIZE", subject),
            )
            rid = cur.lastrowid
            con.execute(
                "INSERT INTO circuits(revision_id,designation,name,result) VALUES(?,?,?,?)",
                (rid, "Q1", subject, "VYHOVUJE"),
            )

    def test_independent_revisions_are_classified_for_merge(self):
        root = Path(tempfile.mkdtemp(prefix="pz_sync_test_"))
        try:
            a = self._make_db(root, "a.db")
            b = self._make_db(root, "b.db")
            self._add_revision(a, "A", "A")
            self._add_revision(b, "B", "B")
            result = compare_database_states(a.path, b.path)
            self.assertEqual(result["relation"], "conflict")
            self.assertEqual(result["local_only_revisions"], ["A"])
            self.assertEqual(result["remote_only_revisions"], ["B"])
        finally:
            import shutil
            shutil.rmtree(root, ignore_errors=True)

    def test_merge_keeps_both_revisions(self):
        root = Path(tempfile.mkdtemp(prefix="pz_sync_test_"))
        try:
            a = self._make_db(root, "a.db")
            b = self._make_db(root, "b.db")
            self._add_revision(a, "A", "A")
            self._add_revision(b, "B", "B")
            self.assertTrue(_pz0500_copy_revision(a.path, b.path, "B"))
            with sqlite3.connect(a.path) as con:
                self.assertEqual(
                    {r[0] for r in con.execute("SELECT revision_no FROM revisions")},
                    {"A", "B"},
                )
        finally:
            import shutil
            shutil.rmtree(root, ignore_errors=True)

    def test_existing_revision_is_never_overwritten(self):
        root = Path(tempfile.mkdtemp(prefix="pz_sync_test_"))
        try:
            a = self._make_db(root, "a.db")
            b = self._make_db(root, "b.db")
            self._add_revision(a, "A", "LOCAL")
            self._add_revision(b, "A", "REMOTE")
            self.assertFalse(_pz0500_copy_revision(a.path, b.path, "A"))
            with sqlite3.connect(a.path) as con:
                self.assertEqual(
                    con.execute("SELECT subject FROM revisions WHERE revision_no='A'").fetchone()[0],
                    "LOCAL",
                )
        finally:
            import shutil
            shutil.rmtree(root, ignore_errors=True)
