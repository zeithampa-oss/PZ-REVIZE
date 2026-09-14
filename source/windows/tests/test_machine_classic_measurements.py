import tempfile
import unittest
from pathlib import Path

from pzrevize.database import Database


class MachineClassicMeasurementSchemaTests(unittest.TestCase):
    def test_machine_table_contains_classic_electrical_fields(self):
        with tempfile.TemporaryDirectory(prefix='pzmachine_') as td:
            db = Database(Path(td) / 'test.db')
            cols = {r[1] for r in db.fetchall('PRAGMA table_info(machine_measurements)')}
            required = {
                'name','board','breaker','breaker_current_a','breaker_characteristic','breaker_ia_a',
                'u0_v','zs_safety_factor','cable','measured_voltage','riso','zs','pe_continuity',
                'zs_limit','ik','impedance_result','insulation_voltage','insulation_result',
                'rcd_designation','rcd_type','rcd_in_a','rcd_idn_ma','rcd_result','pe_result',
                'row_type','item_key','parent_key','sort_order'
            }
            self.assertTrue(required <= cols, required - cols)

    def test_machine_classic_rows_can_be_saved(self):
        with tempfile.TemporaryDirectory(prefix='pzmachine_') as td:
            db = Database(Path(td) / 'test.db')
            rid = db.execute("INSERT INTO revisions(revision_no,revision_type) VALUES(?,?)", ('S-001','STROJ'))
            db.execute(
                "INSERT INTO machine_measurements(revision_id,designation,name,breaker,breaker_current_a,breaker_characteristic,cable,row_type,item_key,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (rid,'QF1','Motor 1','jistič','16','C','CYKY-J 5x2,5','CIRCUIT','c1',1)
            )
            db.execute(
                "INSERT INTO machine_measurements(revision_id,designation,riso,zs,zs_limit,ik,result,row_type,item_key,parent_key,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (rid,'L1–PE','200','0,42','1,15','548','Vyhovuje','POINT','p1','c1',2)
            )
            rows = db.fetchall("SELECT row_type,designation,zs FROM machine_measurements WHERE revision_id=? ORDER BY sort_order", (rid,))
            self.assertEqual([r['row_type'] for r in rows], ['CIRCUIT','POINT'])
            self.assertEqual(rows[1]['zs'], '0,42')


if __name__ == '__main__':
    unittest.main()
