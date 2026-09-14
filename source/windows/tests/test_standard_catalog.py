import sqlite3
import tempfile
import unittest
from pathlib import Path

from pzrevize.database import Database
from app import BulkMeasurementDialog
from app import VERSION


class StandardCatalogTests(unittest.TestCase):
    def test_release_version(self):
        self.assertEqual(VERSION, '0.4.35')
    def test_complete_measurement_contains_pen_points(self):
        self.assertTrue({'L1–PEN','L2–PEN','L3–PEN'}.issubset(set(BulkMeasurementDialog.POINTS)))

    def test_complete_measurement_point_order(self):
        self.assertEqual(BulkMeasurementDialog.POINTS, (
            'L1–PE','L2–PE','L3–PE',
            'L1–N','L2–N','L3–N',
            'L1–PEN','L2–PEN','L3–PEN',
            'L1–L2','L2–L3','L1–L3',
        ))
    def test_catalog_import_is_repeatable_and_filters_bad_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.db"
            db = Database(path)
            first = db.fetchone("SELECT COUNT(*) FROM standards")[0]
            Database(path)
            second = db.fetchone("SELECT COUNT(*) FROM standards")[0]
            self.assertEqual(first, second)
            self.assertEqual(db.fetchone("SELECT COUNT(*) FROM standard_catalog_documents")[0], 194)
            self.assertEqual(db.fetchone("""SELECT COUNT(*) FROM standards
                WHERE catalog_status IN ('Duplicitní soubor','Vyžaduje opravu','Mimo katalog norem')""")[0], 0)

    def test_current_and_historical_editions_are_distinguished(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "test.db")
            current = db.fetchone("SELECT * FROM standards WHERE code='ČSN EN 50110-1 ed. 4'")
            historical = db.fetchone("SELECT * FROM standards WHERE code='ČSN EN 50110-1 ed. 3'")
            self.assertEqual((current["status"], current["is_selectable"]), ("Platná", 1))
            self.assertEqual((historical["status"], historical["historical_only"]), ("Zrušená - historická", 1))

    def test_existing_revision_snapshot_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.db"
            db = Database(path)
            revision_id = db.execute("INSERT INTO revisions(revision_no,revision_type) VALUES(?,?)", ("TEST-1", "ELEKTRO"))
            db.execute("""INSERT INTO revision_standards(revision_id,code_snapshot,title_snapshot,status_snapshot)
                VALUES(?,?,?,?)""", (revision_id, "Historická vlastní norma", "Původní text", "Ručně zadáno"))
            Database(path)
            row = db.fetchone("SELECT * FROM revision_standards WHERE revision_id=?", (revision_id,))
            self.assertEqual(row["code_snapshot"], "Historická vlastní norma")
            self.assertEqual(row["title_snapshot"], "Původní text")


if __name__ == "__main__":
    unittest.main()
