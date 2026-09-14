import tempfile
import unittest
from pathlib import Path

from pzrevize.database import Database


class ElectricalInspectionTemplateTests(unittest.TestCase):
    def test_two_electrical_inspection_groups_are_seeded(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Database(Path(folder)/"test.db")
            nv=db.fetchall("SELECT label FROM inspection_catalog WHERE group_name=? ORDER BY id", ("NV 190/2022 Sb. – příloha č. 1, část A",))
            csn=db.fetchall("SELECT label FROM inspection_catalog WHERE group_name=? ORDER BY id", ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F",))
            self.assertEqual(len(nv), 11)
            self.assertEqual(len(csn), 16)
            self.assertTrue(nv[0][0].startswith("a) "))
            self.assertTrue(nv[-1][0].startswith("k) "))
            self.assertTrue(csn[0][0].startswith("a) "))
            self.assertTrue(csn[-1][0].startswith("p) "))

    def test_seed_is_repeatable(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"test.db"
            db=Database(path)
            first=db.fetchone("SELECT COUNT(*) FROM inspection_catalog")[0]
            Database(path)
            second=db.fetchone("SELECT COUNT(*) FROM inspection_catalog")[0]
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
