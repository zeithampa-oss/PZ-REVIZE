import tempfile
import unittest
from pathlib import Path

from pzrevize.database import Database


class MeasurementNoteTests(unittest.TestCase):
    def test_circuits_support_note_rows_without_schema_change(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / 'test.db')
            cols = {r[1] for r in db.fetchall('PRAGMA table_info(circuits)')}
            self.assertIn('row_type', cols)
            self.assertIn('note', cols)
            rid = db.execute("INSERT INTO revisions(revision_no,revision_type) VALUES(?,?)", ('T-NOTE', 'ELEKTRO'))
            db.execute("INSERT INTO circuits(revision_id,row_type,item_key,parent_key,sort_order,note) VALUES(?,?,?,?,?,?)",
                       (rid, 'NOTE', 'note-1', '', 1, 'Měření provedeno při provozním stavu zařízení.'))
            row = db.fetchone("SELECT row_type,note FROM circuits WHERE revision_id=?", (rid,))
            self.assertEqual(row['row_type'], 'NOTE')
            self.assertIn('provozním stavu', row['note'])

    def test_clone_preserves_only_structural_note_text(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / 'test.db')
            rid = db.execute("INSERT INTO revisions(revision_no,revision_type) VALUES(?,?)", ('T-NOTE', 'ELEKTRO'))
            db.execute("INSERT INTO circuits(revision_id,designation,row_type,item_key,parent_key,sort_order,note,zs) VALUES(?,?,?,?,?,?,?,?)",
                       (rid, '', 'NOTE', 'note-1', '', 1, 'Poznámka k metodě měření.', ''))
            db.execute("INSERT INTO circuits(revision_id,designation,row_type,item_key,parent_key,sort_order,note,zs) VALUES(?,?,?,?,?,?,?,?)",
                       (rid, 'Q1', 'CIRCUIT', 'c-1', '', 2, 'Jednorázová poznámka k hodnotě', '0.35'))
            new_id = db.clone_revision(rid, 'periodic')
            note = db.fetchone("SELECT note FROM circuits WHERE revision_id=? AND row_type='NOTE'", (new_id,))
            circuit = db.fetchone("SELECT note,zs FROM circuits WHERE revision_id=? AND row_type='CIRCUIT'", (new_id,))
            self.assertEqual(note['note'], 'Poznámka k metodě měření.')
            self.assertEqual(circuit['note'], '')
            self.assertEqual(circuit['zs'], '')

    def test_machine_clone_preserves_note_row(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / 'test.db')
            rid = db.execute("INSERT INTO revisions(revision_no,revision_type) VALUES(?,?)", ('M-NOTE', 'STROJ'))
            db.execute("INSERT INTO machine_measurements(revision_id,row_type,item_key,parent_key,sort_order,note) VALUES(?,?,?,?,?,?)",
                       (rid, 'NOTE', 'mnote-1', '', 1, 'Textová poznámka ve strojním měření.'))
            new_id = db.clone_revision(rid, 'periodic')
            row = db.fetchone("SELECT row_type,note FROM machine_measurements WHERE revision_id=?", (new_id,))
            self.assertEqual(row['row_type'], 'NOTE')
            self.assertEqual(row['note'], 'Textová poznámka ve strojním měření.')


if __name__ == '__main__':
    unittest.main()
