from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

APP_NAME = "PZ-REVIZE"


def app_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    (d / "backups").mkdir(exist_ok=True)
    (d / "attachments").mkdir(exist_ok=True)
    return d


class Database:
    def __init__(self, path: str | Path | None = None):
        self._operation_lock = threading.RLock()
        self.path = Path(path) if path else app_data_dir() / "pz_revize.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def connect(self):
        with self._operation_lock:
            con = sqlite3.connect(self.path)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("PRAGMA journal_mode=WAL")
            try:
                yield con
                con.commit()
            finally:
                con.close()

    def _init_db(self):
        schema = r'''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ico TEXT,
            dic TEXT,
            address TEXT,
            city TEXT,
            zip TEXT,
            contact TEXT,
            phone TEXT,
            email TEXT,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            zip TEXT,
            object_type TEXT,
            built_year INTEGER,
            reconstruction_year INTEGER,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            object_id INTEGER REFERENCES objects(id) ON DELETE SET NULL,
            job_no TEXT,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'Nová',
            due_date TEXT,
            price REAL,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_no TEXT UNIQUE,
            revision_type TEXT NOT NULL,
            revision_kind TEXT DEFAULT 'Pravidelná',
            customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            object_id INTEGER REFERENCES objects(id) ON DELETE SET NULL,
            job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
            status TEXT DEFAULT 'Rozpracovaná',
            started_on TEXT,
            finished_on TEXT,
            issued_on TEXT,
            next_revision_on TEXT,
            deadline_watch INTEGER NOT NULL DEFAULT 1,
            subject TEXT,
            scope TEXT,
            documentation TEXT,
            protection TEXT,
            supply TEXT,
            network TEXT,
            inspection_text TEXT,
            conclusion TEXT,
            result TEXT DEFAULT 'Nehodnoceno',
            special_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS circuits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            designation TEXT,
            name TEXT,
            board TEXT,
            breaker TEXT,
            breaker_current_a TEXT,
            breaker_characteristic TEXT,
            breaker_ia_a TEXT,
            u0_v TEXT,
            zs_safety_factor TEXT,
            cable TEXT,
            measured_voltage TEXT,
            riso TEXT,
            zs TEXT,
            rcd TEXT,
            pe_continuity TEXT,
            zs_limit TEXT,
            ik TEXT,
            impedance_result TEXT,
            insulation_voltage TEXT,
            riso_l_pe TEXT,
            riso_n_pe TEXT,
            riso_l_n TEXT,
            insulation_result TEXT,
            rcd_designation TEXT,
            rcd_type TEXT,
            rcd_in_a TEXT,
            rcd_idn_ma TEXT,
            rcd_time_05x_ms TEXT,
            rcd_time_1x_pos_ms TEXT,
            rcd_time_1x_neg_ms TEXT,
            rcd_time_5x_ms TEXT,
            rcd_trip_ma TEXT,
            rcd_touch_v TEXT,
            rcd_test_button TEXT,
            rcd_result TEXT,
            pe_result TEXT,
            row_type TEXT DEFAULT 'CIRCUIT',
            item_key TEXT,
            parent_key TEXT,
            sort_order INTEGER DEFAULT 0,
            rcd_device_kind TEXT,
            rcd_delay_type TEXT,
            rcd_poles TEXT,
            rcd_ac_pos_trip_ma TEXT,
            rcd_ac_pos_time_ms TEXT,
            rcd_ac_pos_touch_v TEXT,
            rcd_ac_neg_trip_ma TEXT,
            rcd_ac_neg_time_ms TEXT,
            rcd_ac_neg_touch_v TEXT,
            rcd_a_pos_trip_ma TEXT,
            rcd_a_pos_time_ms TEXT,
            rcd_a_pos_touch_v TEXT,
            rcd_a_neg_trip_ma TEXT,
            rcd_a_neg_time_ms TEXT,
            rcd_a_neg_touch_v TEXT,
            rcd_f_pos_trip_ma TEXT,
            rcd_f_pos_time_ms TEXT,
            rcd_f_pos_touch_v TEXT,
            rcd_f_neg_trip_ma TEXT,
            rcd_f_neg_time_ms TEXT,
            rcd_f_neg_touch_v TEXT,
            rcd_b_pos_trip_ma TEXT,
            rcd_b_pos_time_ms TEXT,
            rcd_b_pos_touch_v TEXT,
            rcd_b_neg_trip_ma TEXT,
            rcd_b_neg_time_ms TEXT,
            rcd_b_neg_touch_v TEXT,
            rcd_no_trip_result TEXT,
            rcd_5x_pos_ms TEXT,
            rcd_5x_neg_ms TEXT,
            result TEXT,
            note TEXT
        );

        CREATE TABLE IF NOT EXISTS varistor_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            designation TEXT,
            board TEXT,
            spd_type TEXT,
            manufacturer TEXT,
            uc_v TEXT,
            up_kv TEXT,
            test_current_ma TEXT,
            uvar_pos_v TEXT,
            uvar_neg_v TEXT,
            status_indicator TEXT,
            result TEXT,
            note TEXT
        );

        CREATE TABLE IF NOT EXISTS lps_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            designation TEXT,
            item_type TEXT,
            continuity TEXT,
            earth_resistance TEXT,
            result TEXT,
            note TEXT
        );

        CREATE TABLE IF NOT EXISTS machine_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            designation TEXT,
            measurement_type TEXT,
            value TEXT,
            unit TEXT,
            limit_value TEXT,
            result TEXT,
            note TEXT
        );

        CREATE TABLE IF NOT EXISTS external_influences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            code TEXT,
            value_code TEXT,
            description TEXT,
            measure TEXT,
            result TEXT,
            note TEXT,
            floor TEXT,
            room_no TEXT,
            room_name TEXT,
            values_json TEXT,
            measure_codes TEXT,
            environment_class TEXT,
            source_sheet TEXT,
            room_description TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS defect_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            defect_class TEXT,
            standard TEXT,
            standard_name TEXT,
            article TEXT,
            norm_refs_json TEXT,
            title TEXT,
            defect_text TEXT,
            requirement_text TEXT,
            severity TEXT,
            valid_status TEXT DEFAULT 'Platná',
            valid_from TEXT,
            valid_to TEXT,
            replaced_by TEXT,
            note TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS revision_defects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            catalog_id INTEGER REFERENCES defect_catalog(id) ON DELETE SET NULL,
            category TEXT,
            defect_class TEXT,
            standard TEXT,
            article TEXT,
            norm_refs_json TEXT,
            defect_text TEXT NOT NULL,
            severity TEXT,
            status TEXT DEFAULT 'Neodstraněna',
            photo_path TEXT,
            note TEXT
        );

        CREATE TABLE IF NOT EXISTS standards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            title TEXT,
            area TEXT,
            document_type TEXT DEFAULT 'ČSN',
            status TEXT DEFAULT 'Neověřena',
            valid_from TEXT,
            valid_to TEXT,
            replaced_by TEXT,
            verified_on TEXT,
            note TEXT,
            family_code TEXT,
            edition TEXT,
            catalog_status TEXT,
            source_url TEXT,
            catalog_key TEXT,
            is_selectable INTEGER NOT NULL DEFAULT 1,
            is_current INTEGER NOT NULL DEFAULT 0,
            historical_only INTEGER NOT NULL DEFAULT 0,
            UNIQUE(code, title)
        );

        CREATE TABLE IF NOT EXISTS standard_catalog_documents (
            catalog_key TEXT PRIMARY KEY,
            designation TEXT NOT NULL,
            edition TEXT,
            component TEXT,
            title TEXT,
            document_type TEXT,
            component_type TEXT,
            area TEXT,
            relevance TEXT,
            catalog_status TEXT,
            official_status TEXT,
            issue_date TEXT,
            effective_date TEXT,
            end_date TEXT,
            program_action TEXT,
            historical_rule TEXT,
            source_file TEXT,
            source_sha256 TEXT,
            duplicate_group TEXT,
            official_url TEXT,
            issues TEXT,
            catalog_version TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS instruments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            manufacturer TEXT,
            model TEXT,
            serial_no TEXT,
            calibration_no TEXT,
            calibration_date TEXT,
            calibration_due TEXT,
            note TEXT,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS revision_instruments (
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            instrument_id INTEGER NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
            PRIMARY KEY (revision_id, instrument_id)
        );

        CREATE TABLE IF NOT EXISTS revision_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            category TEXT,
            title TEXT,
            original_name TEXT,
            stored_path TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );


        CREATE TABLE IF NOT EXISTS learned_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            value TEXT NOT NULL,
            note TEXT,
            usage_count INTEGER NOT NULL DEFAULT 0,
            last_used TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category, value)
        );

        CREATE TABLE IF NOT EXISTS revision_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            doc_type TEXT,
            doc_no TEXT,
            doc_date TEXT,
            author TEXT,
            note TEXT,
            stored_path TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS revision_standards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            standard_id INTEGER REFERENCES standards(id) ON DELETE SET NULL,
            code_snapshot TEXT NOT NULL,
            title_snapshot TEXT,
            status_snapshot TEXT,
            verified_on_snapshot TEXT,
            article_text TEXT,
            note TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS revision_networks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            system_name TEXT NOT NULL,
            voltage TEXT,
            scope_text TEXT,
            note TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS revision_supplies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            supply_type TEXT NOT NULL,
            designation TEXT,
            voltage TEXT,
            backup TEXT,
            note TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS revision_conclusion_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            title TEXT,
            text_snapshot TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS protection_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            label TEXT NOT NULL,
            csn_ref TEXT,
            en_ref TEXT,
            note TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            usage_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(group_name, label, csn_ref, en_ref)
        );

        CREATE TABLE IF NOT EXISTS revision_protection_measures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            catalog_id INTEGER REFERENCES protection_catalog(id) ON DELETE SET NULL,
            group_snapshot TEXT NOT NULL,
            label_snapshot TEXT NOT NULL,
            csn_ref_snapshot TEXT,
            en_ref_snapshot TEXT,
            note TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS revision_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            defect_id INTEGER REFERENCES revision_defects(id) ON DELETE CASCADE,
            kind TEXT NOT NULL DEFAULT 'working',
            title TEXT,
            original_name TEXT,
            stored_path TEXT NOT NULL,
            note TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inspection_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            label TEXT NOT NULL,
            source_ref TEXT,
            note TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            usage_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(group_name, label, source_ref)
        );

        CREATE TABLE IF NOT EXISTS revision_inspection_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
            catalog_id INTEGER REFERENCES inspection_catalog(id) ON DELETE SET NULL,
            group_snapshot TEXT NOT NULL,
            label_snapshot TEXT NOT NULL,
            source_ref_snapshot TEXT,
            result TEXT NOT NULL DEFAULT 'VYHOVUJE',
            note TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS rt_profile (
            id INTEGER PRIMARY KEY CHECK (id=1),
            name TEXT,
            address TEXT,
            city TEXT,
            zip TEXT,
            ico TEXT,
            dic TEXT,
            phone TEXT,
            email TEXT,
            certificate_no TEXT,
            certificate_scope TEXT,
            certificate_valid_to TEXT,
            authorization_no TEXT,
            authorization_scope TEXT,
            business_name TEXT,
            logo_path TEXT,
            stamp_path TEXT,
            signature_path TEXT,
            note TEXT
        );
        INSERT OR IGNORE INTO rt_profile(id) VALUES (1);
        '''
        with self.connect() as con:
            con.executescript(schema)
        self._migrate_schema()
        self.seed_defaults()


    def _migrate_schema(self):
        """Non-destructive migrations for databases created by older builds."""
        circuit_columns = {
            "measured_voltage": "TEXT",
            "zs_limit": "TEXT",
            "ik": "TEXT",
            "impedance_result": "TEXT",
            "insulation_voltage": "TEXT",
            "riso_l_pe": "TEXT",
            "riso_n_pe": "TEXT",
            "riso_l_n": "TEXT",
            "insulation_result": "TEXT",
            "rcd_designation": "TEXT",
            "rcd_type": "TEXT",
            "rcd_in_a": "TEXT",
            "breaker_current_a": "TEXT",
            "breaker_characteristic": "TEXT",
            "breaker_ia_a": "TEXT",
            "u0_v": "TEXT",
            "zs_safety_factor": "TEXT",
            "rcd_idn_ma": "TEXT",
            "rcd_time_05x_ms": "TEXT",
            "rcd_time_1x_pos_ms": "TEXT",
            "rcd_time_1x_neg_ms": "TEXT",
            "rcd_time_5x_ms": "TEXT",
            "rcd_trip_ma": "TEXT",
            "rcd_touch_v": "TEXT",
            "rcd_test_button": "TEXT",
            "rcd_result": "TEXT",
            "pe_result": "TEXT",
            "row_type": "TEXT DEFAULT 'CIRCUIT'",
            "item_key": "TEXT",
            "parent_key": "TEXT",
            "sort_order": "INTEGER DEFAULT 0",
            "rcd_device_kind": "TEXT",
            "rcd_delay_type": "TEXT",
            "rcd_poles": "TEXT",
            "rcd_ac_pos_trip_ma": "TEXT",
            "rcd_ac_pos_time_ms": "TEXT",
            "rcd_ac_pos_touch_v": "TEXT",
            "rcd_ac_neg_trip_ma": "TEXT",
            "rcd_ac_neg_time_ms": "TEXT",
            "rcd_ac_neg_touch_v": "TEXT",
            "rcd_a_pos_trip_ma": "TEXT",
            "rcd_a_pos_time_ms": "TEXT",
            "rcd_a_pos_touch_v": "TEXT",
            "rcd_a_neg_trip_ma": "TEXT",
            "rcd_a_neg_time_ms": "TEXT",
            "rcd_a_neg_touch_v": "TEXT",
            "rcd_f_pos_trip_ma": "TEXT",
            "rcd_f_pos_time_ms": "TEXT",
            "rcd_f_pos_touch_v": "TEXT",
            "rcd_f_neg_trip_ma": "TEXT",
            "rcd_f_neg_time_ms": "TEXT",
            "rcd_f_neg_touch_v": "TEXT",
            "rcd_b_pos_trip_ma": "TEXT",
            "rcd_b_pos_time_ms": "TEXT",
            "rcd_b_pos_touch_v": "TEXT",
            "rcd_b_neg_trip_ma": "TEXT",
            "rcd_b_neg_time_ms": "TEXT",
            "rcd_b_neg_touch_v": "TEXT",
            "rcd_no_trip_result": "TEXT",
            "rcd_5x_pos_ms": "TEXT",
            "rcd_5x_neg_ms": "TEXT",
        }
        with self.connect() as con:
            existing = {row[1] for row in con.execute("PRAGMA table_info(circuits)").fetchall()}
            for name, sql_type in circuit_columns.items():
                if name not in existing:
                    con.execute(f"ALTER TABLE circuits ADD COLUMN {name} {sql_type}")
            # 0.4.33: strojní zařízení může vedle obecných/funkčních zkoušek
            # používat stejné klasické elektrické měření jako modul EI.
            machine_columns = dict(circuit_columns)
            machine_columns.update({
                "name": "TEXT",
                "board": "TEXT",
                "breaker": "TEXT",
                "cable": "TEXT",
                "riso": "TEXT",
                "zs": "TEXT",
                "rcd": "TEXT",
                "pe_continuity": "TEXT",
                "note": "TEXT",
                "row_type": "TEXT DEFAULT 'MEASUREMENT'",
                "item_key": "TEXT",
                "parent_key": "TEXT",
                "sort_order": "INTEGER DEFAULT 0",
            })
            mexisting = {row[1] for row in con.execute("PRAGMA table_info(machine_measurements)").fetchall()}
            for name, sql_type in machine_columns.items():
                if name not in mexisting:
                    con.execute(f"ALTER TABLE machine_measurements ADD COLUMN {name} {sql_type}")
            mrows = con.execute("SELECT id,item_key,sort_order,row_type FROM machine_measurements ORDER BY revision_id,id").fetchall()
            for pos,row in enumerate(mrows,1):
                if not row[1]:con.execute("UPDATE machine_measurements SET item_key=? WHERE id=?", (f"machine-legacy-{row[0]}", row[0]))
                if row[2] in (None,0):con.execute("UPDATE machine_measurements SET sort_order=? WHERE id=?", (pos,row[0]))
                if not row[3]:con.execute("UPDATE machine_measurements SET row_type='MEASUREMENT' WHERE id=?", (row[0],))

            # 0.4.19: vnější vlivy jsou ukládány po místnostech jako kompletní matice AA–CB.
            # Původní sloupce code/value_code/... zůstávají kvůli zpětné kompatibilitě.
            external_columns = {
                "floor": "TEXT",
                "room_no": "TEXT",
                "room_name": "TEXT",
                "values_json": "TEXT",
                "measure_codes": "TEXT",
                "environment_class": "TEXT",
                "source_sheet": "TEXT",
                "room_description": "TEXT",
                "abnormal_measures_json": "TEXT",
                "sort_order": "INTEGER NOT NULL DEFAULT 0",
            }
            eexisting = {row[1] for row in con.execute("PRAGMA table_info(external_influences)").fetchall()}
            for name, sql_type in external_columns.items():
                if name not in eexisting:
                    con.execute(f"ALTER TABLE external_influences ADD COLUMN {name} {sql_type}")
            erows = con.execute("SELECT id,sort_order FROM external_influences ORDER BY revision_id,id").fetchall()
            for pos,row in enumerate(erows,1):
                if row[1] in (None,0):con.execute("UPDATE external_influences SET sort_order=? WHERE id=?", (pos,row[0]))

            revision_columns = {
                "vtz_class": "TEXT DEFAULT 'II'",
                "distribution_text": "TEXT",
                "received_on": "TEXT",
                "object_name_text": "TEXT",
                "object_address_text": "TEXT",
                "object_city_text": "TEXT",
                "object_zip_text": "TEXT",
                "object_parcel_text": "TEXT",
                "object_location_note": "TEXT",
                "source_revision_id": "INTEGER",
                "copy_mode": "TEXT",
                "operator_instruction": "TEXT",
                "deadline_watch": "INTEGER NOT NULL DEFAULT 1",
            }
            rexisting = {row[1] for row in con.execute("PRAGMA table_info(revisions)").fetchall()}
            for name, sql_type in revision_columns.items():
                if name not in rexisting:
                    con.execute(f"ALTER TABLE revisions ADD COLUMN {name} {sql_type}")
            con.execute("UPDATE revisions SET deadline_watch=1 WHERE deadline_watch IS NULL")
            rt_columns = {
                "certificate_scope": "TEXT",
                "certificate_valid_to": "TEXT",
                "authorization_scope": "TEXT",
                "business_name": "TEXT",
            }
            rtexisting = {row[1] for row in con.execute("PRAGMA table_info(rt_profile)").fetchall()}
            for name, sql_type in rt_columns.items():
                if name not in rtexisting:
                    con.execute(f"ALTER TABLE rt_profile ADD COLUMN {name} {sql_type}")
            defect_catalog_existing = {row[1] for row in con.execute("PRAGMA table_info(defect_catalog)").fetchall()}
            if 'defect_class' not in defect_catalog_existing:
                con.execute("ALTER TABLE defect_catalog ADD COLUMN defect_class TEXT")
            if 'norm_refs_json' not in defect_catalog_existing:
                con.execute("ALTER TABLE defect_catalog ADD COLUMN norm_refs_json TEXT")
            revision_defect_existing = {row[1] for row in con.execute("PRAGMA table_info(revision_defects)").fetchall()}
            if 'defect_class' not in revision_defect_existing:
                con.execute("ALTER TABLE revision_defects ADD COLUMN defect_class TEXT")
            if 'norm_refs_json' not in revision_defect_existing:
                con.execute("ALTER TABLE revision_defects ADD COLUMN norm_refs_json TEXT")
            standard_columns = {
                "family_code": "TEXT", "edition": "TEXT", "catalog_status": "TEXT",
                "source_url": "TEXT", "catalog_key": "TEXT",
                "is_selectable": "INTEGER NOT NULL DEFAULT 1",
                "is_current": "INTEGER NOT NULL DEFAULT 0",
                "historical_only": "INTEGER NOT NULL DEFAULT 0",
            }
            sexisting = {row[1] for row in con.execute("PRAGMA table_info(standards)").fetchall()}
            for name, sql_type in standard_columns.items():
                if name not in sexisting:
                    con.execute(f"ALTER TABLE standards ADD COLUMN {name} {sql_type}")
            # 0.4.6: preserve the old single standard/article as the first structured
            # norm reference. Citations remain empty unless the catalogue has a requirement text.
            for table,citation_col in (("defect_catalog","requirement_text"),("revision_defects",None)):
                rows=con.execute(f"SELECT id,standard,article{','+citation_col if citation_col else ''},norm_refs_json FROM {table}").fetchall()
                for row in rows:
                    if (row[-1] or '').strip():continue
                    st=(row[1] or '').strip();art=(row[2] or '').strip();cit=(row[3] or '').strip() if citation_col else ''
                    if st or art or cit:
                        payload=json.dumps([{"standard":st,"article":art,"citation":cit}],ensure_ascii=False)
                        con.execute(f"UPDATE {table} SET norm_refs_json=? WHERE id=?",(payload,row[0]))
            # 0.4.5: C1/C2/C3 is stored as severity. Copy the 0.4.4 class into
            # severity where possible; do not guess mappings from the older textual scale.
            con.execute("""UPDATE defect_catalog SET severity=UPPER(TRIM(defect_class))
                           WHERE UPPER(TRIM(COALESCE(defect_class,''))) IN ('C1','C2','C3')
                             AND UPPER(TRIM(COALESCE(severity,''))) NOT IN ('C1','C2','C3')""")
            con.execute("""UPDATE revision_defects SET severity=UPPER(TRIM(defect_class))
                           WHERE UPPER(TRIM(COALESCE(defect_class,''))) IN ('C1','C2','C3')
                             AND UPPER(TRIM(COALESCE(severity,''))) NOT IN ('C1','C2','C3')""")
            # Backfill keys/order for legacy circuit rows without changing their content.
            rows = con.execute("SELECT id,item_key,sort_order,row_type FROM circuits ORDER BY revision_id,id").fetchall()
            for pos,row in enumerate(rows,1):
                if not row[1]:
                    con.execute("UPDATE circuits SET item_key=? WHERE id=?", (f"legacy-{row[0]}", row[0]))
                if row[2] in (None,0):
                    con.execute("UPDATE circuits SET sort_order=? WHERE id=?", (pos,row[0]))
                if not row[3]:
                    con.execute("UPDATE circuits SET row_type='CIRCUIT' WHERE id=?", (row[0],))
            # 0.3.0: correct a legacy catalogue mapping. ČSN EN 61140 ed. 3 article 5.3.9
            # is "Řízení potenciálu", not the separate C.2 measure from ČSN 33 2000-4-41.
            con.execute(
                """UPDATE protection_catalog
                   SET en_ref='', note='Pouze za podmínek přílohy C; v ČSN EN 61140 ed. 3 není v katalogu vedeno pod čl. 5.3.9.'
                   WHERE group_name='2.3 Prostředky ochrany při poruše'
                     AND label='Neuzemněné místní pospojování'
                     AND en_ref='čl. 5.3.9'"""
            )


    def learn_value(self, category: str, value: str, note: str = ""):
        """Remember a user-entered value and increase its usage score.

        This is intentionally local-only learning: no AI/cloud is involved.
        """
        category=(category or "").strip()
        value=(value or "").strip()
        if not category or not value:
            return
        with self.connect() as con:
            con.execute(
                """INSERT INTO learned_values(category,value,note,usage_count,last_used,active)
                   VALUES(?,?,?,1,CURRENT_TIMESTAMP,1)
                   ON CONFLICT(category,value) DO UPDATE SET
                       usage_count=learned_values.usage_count+1,
                       last_used=CURRENT_TIMESTAMP,
                       active=1,
                       note=CASE WHEN excluded.note<>'' THEN excluded.note ELSE learned_values.note END,
                       updated_at=CURRENT_TIMESTAMP""",
                (category,value,note or "")
            )

    def learned_values(self, category: str, limit: int = 100):
        return self.fetchall(
            "SELECT * FROM learned_values WHERE category=? AND active=1 ORDER BY usage_count DESC, COALESCE(last_used,'') DESC, value COLLATE NOCASE LIMIT ?",
            (category, limit)
        )

    def seed_defaults(self):
        with self.connect() as con:
            n = con.execute("SELECT COUNT(*) FROM standards").fetchone()[0]
            if n == 0:
                rows = [
                    ("250/2021 Sb.", "Zákon o bezpečnosti práce v souvislosti s provozem vyhrazených technických zařízení", "Právní předpisy", "Zákon", "Platný", "2022-07-01", None, None, "2026-09-06", "Základní právní rámec projektu PZ-REVIZE."),
                    ("190/2022 Sb.", "Nařízení vlády o vyhrazených technických elektrických zařízeních a požadavcích na zajištění jejich bezpečnosti", "Právní předpisy", "NV", "Platný", "2022-07-01", None, None, "2026-09-06", "Základní právní rámec projektu PZ-REVIZE."),
                    ("ČSN 33 1500", "Elektrotechnické předpisy - Revize elektrických zařízení", "Revize NN", "ČSN", "Platná", "1991-06-01", None, None, "2026-09-06", "V aplikaci jsou podporovány změny Z1 až Z4 jako součást normativního rámce."),
                    ("ČSN 33 2000-6 ed. 2", "Elektrické instalace nízkého napětí - Část 6: Revize", "Revize NN", "ČSN", "Platná", "2017-04-01", None, None, "2026-09-06", "Jádro pro výchozí a pravidelné revize, prohlídku, zkoušení, měření a zprávu."),
                    ("ČSN 33 2000-5-51 ed. 3+Z1+Z2", "Elektrické instalace nízkého napětí - Výběr a stavba elektrických zařízení - Obecné předpisy", "Vnější vlivy", "ČSN", "Platná", "2022-08-01", None, None, "2026-09-06", "Základ pro vnější vlivy a všeobecné podmínky."),
                    ("ČSN 33 2000-4-41 ed. 3+Z1+Z2", "Ochranná opatření pro zajištění bezpečnosti - Ochrana před úrazem elektrickým proudem", "Ochrana před úrazem", "ČSN", "Platná", "2018-02-01", None, None, "2026-09-06", ""),
                    ("ČSN 33 2000-5-52 ed. 2", "Výběr a stavba elektrických zařízení - Elektrická vedení", "Elektrická vedení", "ČSN", "Platná", "2012-03-01", None, None, "2026-09-06", ""),
                    ("ČSN 33 2000-5-54 ed. 3", "Výběr a stavba elektrických zařízení - Uzemnění a ochranné vodiče", "Uzemnění", "ČSN", "Platná", "2012-03-01", None, None, "2026-09-06", ""),
                    ("ČSN 33 2130 ed. 4", "Elektrické instalace nízkého napětí - Vnitřní elektrické rozvody", "Vnitřní rozvody", "ČSN", "Platná", "2025-01-01", None, None, "2026-09-06", "Nahrazuje ed. 3."),
                    ("ČSN EN IEC 62305-1 ed. 3", "Ochrana před bleskem - Část 1: Obecné principy", "LPS", "ČSN", "Platná", "2025-11-01", None, None, "2026-09-06", ""),
                    ("ČSN EN IEC 62305-2 ed. 3", "Ochrana před bleskem - Část 2: Řízení rizika", "LPS", "ČSN", "Platná", "2025-11-01", None, None, "2026-09-06", ""),
                    ("ČSN EN IEC 62305-3 ed. 3", "Ochrana před bleskem - Část 3: Hmotné škody na stavbách a ohrožení života", "LPS", "ČSN", "Platná", "2026-01-01", None, None, "2026-09-06", ""),
                    ("ČSN EN IEC 62305-4 ed. 3", "Ochrana před bleskem - Část 4: Elektrické a elektronické systémy ve stavbách", "LPS", "ČSN", "Platná", "2026-04-01", None, None, "2026-09-06", ""),
                    ("ČSN 34 1390", "Předpisy pro ochranu před bleskem", "LPS - historie", "ČSN", "Zrušená - historická", "1970-04-01", "2009-02-01", "Soubor ČSN EN 62305", "2026-09-06", "Pro historické posouzení starších zařízení."),
                ]
                con.executemany("""
                    INSERT OR IGNORE INTO standards(code,title,area,document_type,status,valid_from,valid_to,replaced_by,verified_on,note)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                """, rows)

        self.import_bundled_standard_catalog()

    def import_bundled_standard_catalog(self):
        """Import the bundled metadata catalogue without changing revision snapshots.

        Only verified current documents are offered by default. Historical and
        unverified editions stay searchable after the user enables the extended view.
        Duplicate, damaged and non-standard source files are retained solely in the
        provenance table and never become selectable catalogue entries.
        """
        path = Path(__file__).resolve().parent / "resources" / "norm_catalog_2026-09-09.json"
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        version = str(data.get("metadata", {}).get("generated_on") or "2026-09-09")
        records = data.get("records") or []
        excluded = {"Duplicitní soubor", "Vyžaduje opravu", "Mimo katalog norem"}
        components = {"Změna", "Oprava", "Soubor změn", "Studijní materiál", "Protokol"}
        doc_sql = """INSERT OR REPLACE INTO standard_catalog_documents(
            catalog_key,designation,edition,component,title,document_type,component_type,
            area,relevance,catalog_status,official_status,issue_date,effective_date,end_date,
            program_action,historical_rule,source_file,source_sha256,duplicate_group,
            official_url,issues,catalog_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
        grouped = {}
        with self.connect() as con:
            for record in records:
                key = f"{record.get('sha256','')}:{record.get('id','')}"
                con.execute(doc_sql, (
                    key, record.get("designation", ""), record.get("edition", ""),
                    record.get("component", ""), record.get("title", ""),
                    record.get("document_type", ""), record.get("component_type", ""),
                    record.get("area", ""), record.get("relevance", ""),
                    record.get("catalog_status", ""), record.get("official_status", ""),
                    record.get("issue_date", ""), record.get("effective_date", ""),
                    record.get("end_date", ""), record.get("program_action", ""),
                    record.get("historical_rule", ""), record.get("file_name", ""),
                    record.get("sha256", ""), record.get("duplicate_group", ""),
                    record.get("official_url", ""), record.get("issues", ""), version,
                ))
                if record.get("catalog_status") in excluded or record.get("component_type") in components:
                    continue
                designation = (record.get("designation") or "").strip()
                edition = (record.get("edition") or "").strip()
                if not designation:
                    continue
                grouped.setdefault((designation, edition), []).append(record)

            for (designation, edition), items in grouped.items():
                code = " ".join(x for x in (designation, edition) if x).strip()
                verified = [r for r in items if not str(r.get("official_status", "")).startswith("Neověřeno")]
                best = verified[0] if verified else items[0]
                official = best.get("official_status", "")
                if official == "Platná" or official == "Platná TNI":
                    status, current, historical = "Platná", 1, 0
                elif str(official).startswith("Souběžně platná"):
                    status, current, historical = "Platná - souběžná", 1, 0
                elif official in ("Neplatná", "Nahrazena"):
                    status, current, historical = "Zrušená - historická", 0, 1
                else:
                    status, current, historical = "Neověřena", 0, 0
                title = (best.get("title") or "").strip()
                if not title:
                    title = code
                catalog_key = f"{designation}|{edition}"
                note_parts = [best.get("program_action", ""), best.get("historical_rule", "")]
                note = " ".join(x.strip() for x in note_parts if x and x.strip())
                selectable = int(current)
                existing = con.execute("SELECT id FROM standards WHERE catalog_key=?", (catalog_key,)).fetchone()
                values = (code, title, best.get("area", ""), best.get("document_type", "ČSN"),
                          status, best.get("effective_date", ""), best.get("end_date", ""), "",
                          version, note, designation, edition, best.get("catalog_status", ""),
                          best.get("official_url", ""), catalog_key, selectable, current, historical)
                if existing:
                    con.execute("""UPDATE standards SET code=?,title=?,area=?,document_type=?,status=?,
                        valid_from=?,valid_to=?,replaced_by=?,verified_on=?,note=?,family_code=?,edition=?,
                        catalog_status=?,source_url=?,catalog_key=?,is_selectable=?,is_current=?,historical_only=?
                        WHERE id=?""", values + (existing[0],))
                else:
                    con.execute("""INSERT OR IGNORE INTO standards(code,title,area,document_type,status,
                        valid_from,valid_to,replaced_by,verified_on,note,family_code,edition,catalog_status,
                        source_url,catalog_key,is_selectable,is_current,historical_only)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values)

            d = con.execute("SELECT COUNT(*) FROM defect_catalog").fetchone()[0]
            if d == 0:
                con.executemany("""
                    INSERT INTO defect_catalog(category, standard, standard_name, article, title, defect_text, requirement_text, severity, valid_status, note)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                """, [
                    ("Ochrana před úrazem", "ČSN 33 2000-4-41 ed. 3", "Ochrana před úrazem elektrickým proudem", "", "Ochranný vodič", "Ochranný vodič není řádně připojen / jeho spojitost nebyla prokázána.", "Ověřit návaznost na konkrétní článek podle provedení a stáří instalace.", "C2", "Šablona", "Vzorek - upravte podle konkrétního zjištění."),
                    ("Rozvaděč", "", "", "", "Popis rozvaděče", "Rozvaděč nebo jeho obvody nejsou dostatečně a trvale označeny.", "Doplňte přesný normový odkaz podle konkrétního případu.", "C3", "Šablona", "Vzorek - nejedná se o normový text."),
                    ("LPS", "", "", "", "Koroze / mechanické poškození", "Na části LPS bylo zjištěno mechanické poškození nebo koroze vyžadující nápravu.", "Posoudit podle použitelné edice souboru 62305 nebo historického předpisu.", "C3", "Šablona", "Vzorek - nejedná se o normový text."),
                ])

            protection_defaults = [
                ("2.1 Druh ochranného opatření", "Automatické odpojení od zdroje v síti TN (TT, IT)", "čl. 411", "čl. 6.2", ""),
                ("2.1 Druh ochranného opatření", "Dvojitá nebo zesílená izolace", "čl. 412", "čl. 6.3", ""),
                ("2.1 Druh ochranného opatření", "Ochrana ochranným pospojováním", "čl. 411.3.1.2", "čl. 6.4", "Použití podle konkrétního provedení."),
                ("2.1 Druh ochranného opatření", "Elektrické oddělení", "čl. 413", "čl. 6.5", "Pro jeden spotřebič podle obecného ochranného opatření; více spotřebičů viz příloha C."),
                ("2.1 Druh ochranného opatření", "Nevodivé okolí", "Příloha C, čl. C.1", "čl. 6.6", "Pouze za podmínek přílohy C."),
                ("2.1 Druh ochranného opatření", "SELV", "čl. 414", "čl. 6.7", ""),
                ("2.1 Druh ochranného opatření", "PELV", "čl. 414", "čl. 6.8", ""),
                ("2.1 Druh ochranného opatření", "Omezení ustáleného dotykového proudu a náboje", "", "čl. 6.9", "Použití podle konkrétního zařízení a příslušné výrobkové normy."),
                ("2.2 Prostředky základní ochrany", "Základní izolace živých částí", "Příloha A, čl. A.1", "čl. 5.2.2", ""),
                ("2.2 Prostředky základní ochrany", "Ochranné přepážky nebo kryty", "Příloha A, čl. A.2", "čl. 5.2.3", ""),
                ("2.2 Prostředky základní ochrany", "Zábrany", "Příloha B, čl. B.2", "čl. 5.2.4", "Pouze za podmínek přílohy B."),
                ("2.2 Prostředky základní ochrany", "Ochrana polohou - umístění mimo dosah", "Příloha B, čl. B.3", "čl. 5.2.5", "Pouze za podmínek přílohy B."),
                ("2.2 Prostředky základní ochrany", "Omezení napětí", "", "čl. 5.2.6", "Použití dle příslušného ochranného opatření."),
                ("2.2 Prostředky základní ochrany", "Omezení ustáleného dotykového proudu a energie", "", "čl. 5.2.7", "Použití dle příslušného zařízení."),
                ("2.2 Prostředky základní ochrany", "Řízení potenciálu", "", "čl. 5.2.8", "Použití dle konkrétní instalace."),
                ("2.3 Prostředky ochrany při poruše", "Přídavná izolace", "čl. 412.1.1", "čl. 5.3.2", ""),
                ("2.3 Prostředky ochrany při poruše", "Ochranné pospojování", "čl. 411.3.1.2", "čl. 5.3.3", ""),
                ("2.3 Prostředky ochrany při poruše", "Ochranné stínění", "", "čl. 5.3.4", "Použití dle konkrétního zařízení."),
                ("2.3 Prostředky ochrany při poruše", "Automatické odpojení od zdroje - jedna porucha", "čl. 411.3.2", "čl. 5.3.6", ""),
                ("2.3 Prostředky ochrany při poruše", "Jednoduché oddělení obvodů", "čl. 413", "čl. 5.3.7", ""),
                ("2.3 Prostředky ochrany při poruše", "Nevodivé okolí", "Příloha C, čl. C.1", "čl. 5.3.8", "Pouze za podmínek přílohy C."),
                ("2.3 Prostředky ochrany při poruše", "Neuzemněné místní pospojování", "Příloha C, čl. C.2", "", "Pouze za podmínek přílohy C; v ČSN EN 61140 ed. 3 není v katalogu vedeno pod čl. 5.3.9."),
                ("2.3 Prostředky ochrany při poruše", "Řízení potenciálu", "", "čl. 5.3.9", "Použití podle konkrétní instalace."),
                ("2.3 Prostředky ochrany při poruše", "Indikace a odpojení ve VN instalacích a sítích", "", "čl. 5.3.5", "Položka ČSN EN 61140 ed. 3; pro běžnou NN instalaci se zpravidla nepoužije."),
                ("2.3 Prostředky ochrany při poruše", "Elektrické oddělení pro napájení více než jednoho spotřebiče", "Příloha C, čl. C.3", "čl. 6.5", "Pouze za podmínek přílohy C."),
                ("2.4 Doplňková ochrana", "Proudový chránič (RCD) IΔn ≤ 30 mA", "čl. 415.1", "čl. 5.5.1 / 6.10.1", ""),
                ("2.4 Doplňková ochrana", "Doplňující ochranné pospojování", "čl. 415.2", "čl. 5.5.2 / 6.10.2", ""),
                ("2.5 Zařízení podle třídy ochrany", "Zařízení třídy ochrany I", "", "čl. 7.3", ""),
                ("2.5 Zařízení podle třídy ochrany", "Zařízení třídy ochrany II", "čl. 412", "čl. 7.4", ""),
                ("2.5 Zařízení podle třídy ochrany", "Zařízení třídy ochrany III", "čl. 414", "čl. 7.5", ""),
            ]
            con.executemany("""
                INSERT OR IGNORE INTO protection_catalog(group_name,label,csn_ref,en_ref,note) VALUES(?,?,?,?,?)
            """, protection_defaults)

            inspection_defaults = [
                ("Všeobecně", "Zařízení je používáno jen k účelu, pro který bylo určeno", "ČSN 33 2000-6 ed. 2 čl. 6.4.2", ""),
                ("Všeobecně", "Odborné provedení práce a použití vhodného materiálu", "ČSN 33 2000-6 ed. 2 čl. 6.4.2", ""),
                ("Všeobecně", "Elektrické zařízení a instalace jsou udržovány v odpovídajícím stavu", "ČSN 33 2000-6 ed. 2 čl. 6.4.2", ""),
                ("Všeobecně", "Elektrické a neelektrické zařízení se vzájemně nepřípustně neovlivňují", "ČSN 33 2000-6 ed. 2 čl. 6.4.2", ""),
                ("Všeobecně", "Zařízení odpovídá určeným vnějším vlivům a mechanickým namáháním", "ČSN 33 2000-6 ed. 2 čl. 6.4.2; ČSN 33 2000-5-51", ""),
                ("Ochrana před úrazem", "Základní izolace živých částí je nepoškozená a účinná", "ČSN 33 2000-4-41 ed. 3 příloha A čl. A.1", ""),
                ("Ochrana před úrazem", "Ochranné přepážky a kryty odpovídají prostoru a požadovanému krytí", "ČSN 33 2000-4-41 ed. 3 příloha A čl. A.2", ""),
                ("Ochrana před úrazem", "Zábrany a ochrana polohou jsou provedeny v předepsaných vzdálenostech", "ČSN 33 2000-4-41 ed. 3 příloha B čl. B.2, B.3", ""),
                ("Ochrana před úrazem", "Ochranné pospojování je provedeno v požadovaném rozsahu", "ČSN 33 2000-4-41 ed. 3 čl. 411.3.1.2; ČSN 33 2000-5-54 ed. 3", ""),
                ("Ochrana před úrazem", "Doplňující ochranné pospojování je provedeno tam, kde je požadováno", "ČSN 33 2000-4-41 ed. 3 čl. 415.2", ""),
                ("Ochrana před úrazem", "SELV/PELV - zdroj, oddělení obvodů a provedení odpovídají požadavkům", "ČSN 33 2000-4-41 ed. 3 čl. 414", ""),
                ("Ochrana před úrazem", "FELV je použito pouze tam, kde je tento způsob přípustný", "ČSN 33 2000-4-41 ed. 3 čl. 411.7", ""),
                ("Ochrana před úrazem", "Proudové chrániče jsou instalovány všude, kde jsou požadovány", "ČSN 33 2000-4-41 ed. 3; příslušné části ČSN 33 2000", ""),
                ("Ochrana před úrazem", "Neživé části jsou spojeny s ochranným vodičem a odpovídající uzemňovací soustavou", "ČSN 33 2000-4-41 ed. 3 čl. 411.3.1.1", ""),
                ("Požární a tepelné účinky", "Protipožární přepážky a těsnicí výplně jsou provedeny v požadovaných místech", "ČSN 33 2000-6 ed. 2 čl. 6.4.2; ČSN 33 2000-5-52", ""),
                ("Požární a tepelné účinky", "Elektrická zařízení nevykazují známky nepřípustného přehřátí", "ČSN 33 2000-6 ed. 2 čl. 6.4.2", ""),
                ("Vedení a kabelové trasy", "Vodiče a kabely nejsou mechanicky poškozeny", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Vedení a kabelové trasy", "Vedení je provedeno přehledným způsobem a v odpovídajících instalačních zónách", "ČSN 33 2130 ed. 4; ČSN 33 2000-5-52", ""),
                ("Vedení a kabelové trasy", "Vedení je řádně upevněno a chráněno před mechanickým poškozením", "ČSN 33 2000-5-52", ""),
                ("Vedení a kabelové trasy", "Druhy, typy a průřezy vodičů odpovídají proudovému zatížení a způsobu uložení", "ČSN 33 2000-5-52 ed. 2", ""),
                ("Vedení a kabelové trasy", "Vedení odpovídá vnějším vlivům, teplotám, chemickým a slunečním vlivům", "ČSN 33 2000-5-51 ed. 3; ČSN 33 2000-5-52", ""),
                ("Vedení a kabelové trasy", "Silové a ostatní systémy jsou odděleny v požadovaném rozsahu", "ČSN 33 2000-5-52", ""),
                ("Vedení a kabelové trasy", "Spoje a zakončení vodičů a kabelů jsou mechanicky a elektricky spolehlivé", "ČSN 33 2000-5-52 ed. 2 kap. 526", ""),
                ("Označení", "Střední a ochranné vodiče jsou správně a nezaměnitelně označeny", "ČSN 33 0165 ed. 2; ČSN EN IEC 60445", ""),
                ("Označení", "Obvody, jistící prvky, spínače a svorky jsou trvale a funkčně označeny", "ČSN 33 2000-5-51 ed. 3 čl. 514", ""),
                ("Označení", "Jsou k dispozici požadovaná schémata, výstražné nápisy a další informace", "ČSN 33 2000-5-51 ed. 3 čl. 514.5", ""),
                ("Rozváděče", "Výrobní štítek, dokumentace a prohlášení rozváděče jsou k dispozici", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Rozváděče", "Rozváděč má odpovídající pracovní prostor a je bezpečně přístupný", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Rozváděče", "Rozváděč je bezpečně upevněn a jeho kryty nejsou poškozeny", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Rozváděče", "Stav krytu a IP kód odpovídají prostředí a použití", "ČSN 33 2000-6 ed. 2 příloha F; ČSN EN 60529", ""),
                ("Rozváděče", "Hlavní vypínač je přítomen, vhodně označen a funkční", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Rozváděče", "Ruční ovládání jističů a proudových chráničů je funkční", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Rozváděče", "Vestavěné zkušební tlačítko RCD/AFDD vyvolá vybavení", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Rozváděče", "SPD je instalována tam, kde je určeno, a indikace potvrzuje provozuschopný stav", "ČSN 33 2000-6 ed. 2 příloha F; ČSN 33 2000-5-53", ""),
                ("Rozváděče", "Použité ochranné přístroje mají správný typ a jmenovité hodnoty", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Rozváděče", "Připojení vodičů a přípojnic je řádně provedeno a zajištěno", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Odpojování a spínání", "Odpojovače a prostředky pro nouzové odpojení jsou přítomny a v odpovídajícím stavu", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Odpojování a spínání", "Odpojovací přístroje lze tam, kde je to požadováno, zajistit ve vypnuté poloze", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Odpojování a spínání", "Odpojovací a spínací přístroje jsou jednoznačně identifikovány", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Odpojování a spínání", "Prostředky nouzového odpojení jsou snadno přístupné a funkční", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Koncové obvody", "Jednopólové spínací a ochranné přístroje jsou zapojeny pouze ve fázových/krajních vodičích", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Koncové obvody", "Použité ochranné vodiče jsou vhodné pro charakter a provedení obvodu", "ČSN 33 2000-6 ed. 2 příloha F; ČSN 33 2000-5-54", ""),
                ("Koncové obvody", "Je zajištěna koordinace mezi vodiči a ochranou před přetížením", "ČSN 33 2000-6 ed. 2 příloha F", ""),
                ("Koncové obvody", "Zásuvkové a venkovní obvody mají doplňkovou ochranu RCD tam, kde je požadována", "ČSN 33 2000-4-41 ed. 3; ČSN 33 2130 ed. 4", ""),
                ("Uzemnění a pospojování", "Uzemňovací přívod a jeho připojení jsou přítomny a přístupné", "ČSN 33 2000-6 ed. 2 příloha F; ČSN 33 2000-5-54", ""),
                ("Uzemnění a pospojování", "Hlavní ochranná přípojnice/MET je provedena a přístupná", "ČSN 33 2000-5-54 ed. 3", ""),
                ("Uzemnění a pospojování", "Vodiče hlavního ochranného pospojování mají odpovídající průřez a spoje", "ČSN 33 2000-5-54 ed. 3", ""),
                ("Ochranné a kontrolní přístroje", "Volba, seřízení, selektivita a koordinace ochranných přístrojů odpovídá instalaci", "ČSN 33 2000-5-53", ""),
                ("Ochranné a kontrolní přístroje", "Volba a umístění SPD odpovídá požadované koordinaci ochrany před přepětím", "ČSN 33 2000-5-53; ČSN EN 62305-4", ""),
                ("EMC", "Provedení omezuje vznik nepřípustných elektromagnetických vlivů a velkých vodivých smyček", "ČSN 33 2000-4-44 kap. 444", ""),
                ("Provoz a údržba", "Zařízení je přístupné pro bezpečné ovládání, značení, prohlídku a údržbu", "ČSN 33 2000-5-51 ed. 3", ""),
                ("Provoz a údržba", "Nouzové STOP/bezpečnostní vypnutí je instalováno tam, kde je vyžadováno", "ČSN 33 2000-6 ed. 2 čl. 6.4.2", ""),
            ]
            inspection_defaults += [
                # Požadavky na prohlídku převzaté z uživatelem dodané vzorové revizní zprávy.
                ("NV 190/2022 Sb. – příloha č. 1, část A", "a) Způsob, popřípadě stav ochrany před úrazem elektrickým proudem včetně měření vzdáleností, pokud jde zejména o ochranu přepážkami nebo kryty, zábranami nebo polohou", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),
                ("NV 190/2022 Sb. – příloha č. 1, část A", "b) Použití protipožárních přepážek nebo jiných bezpečnostních opatření proti šíření ohně a ochrana před tepelnými účinky", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),
                ("NV 190/2022 Sb. – příloha č. 1, část A", "c) Volba vodičů s ohledem na proudovou zatížitelnost a úbytek napětí", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),
                ("NV 190/2022 Sb. – příloha č. 1, část A", "d) Volba, seřízení a stav ukazatelů ochranných a kontrolních prvků", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),
                ("NV 190/2022 Sb. – příloha č. 1, část A", "e) Použití odpovídajících, vhodně umístěných a dostatečně oddělujících spínacích prvků", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),
                ("NV 190/2022 Sb. – příloha č. 1, část A", "f) Volba elektrických zařízení a ochranných opatření s ohledem na vnější vlivy, oprávněnost zatřídění a označení prostorů z hlediska vnějších vlivů", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),
                ("NV 190/2022 Sb. – příloha č. 1, část A", "g) Označení středních a ochranných vodičů", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),
                ("NV 190/2022 Sb. – příloha č. 1, část A", "h) Vybavení schématy, varovnými nápisy a jinými podobnými informacemi požadovanými jinými právními předpisy nebo technickými normami", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),
                ("NV 190/2022 Sb. – příloha č. 1, část A", "i) Označení obvodů, pojistek, spínačů, svorek", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),
                ("NV 190/2022 Sb. – příloha č. 1, část A", "j) Odpovídající způsob spojení vodičů", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),
                ("NV 190/2022 Sb. – příloha č. 1, část A", "k) Přístupnost z hlediska provozu a údržby", "NV č. 190/2022 Sb., příloha č. 1, část A", ""),

                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "a) Způsob ochrany před úrazem elektrickým proudem", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "b) Použití protipožárních přepážek a jiných opatření na ochranu před šířením ohně a před tepelnými účinky", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "c) Volba vodičů s ohledem na proudovou zatížitelnost a úbytek napětí", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "d) Volba, seřízení, selektivita a koordinace ochranných a kontrolních (monitorovacích) přístrojů", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "e) Výběr, umístění a instalace vhodných přepěťových ochran (SPD), kde je to určeno", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "f) Volba, umístění a instalace vhodných odpojovacích a spínacích přístrojů", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "g) Volba zařízení a ochranných opatření přiměřených k vnějším vlivům a mechanickým namáháním", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "h) Označení nulových a ochranných vodičů", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "i) Vybavení schématy, výstražnými nápisy nebo dalšími podobnými informacemi", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "j) Označení obvodů, nadproudových ochranných přístrojů, spínačů, svorek atd.", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "k) Odpovídající způsob zakončování a spojování kabelů a vodičů", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "l) Volba a instalace uzemnění, ochranných vodičů a jejich připojování", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "m) Přístupnost zařízení z hlediska jeho ovládání, značení a údržby", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "n) Opatření proti elektromagnetickému rušení", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "o) Zda neživé části jsou spojeny s uzemněním", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
                ("ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F", "p) Volba stavu elektrických vedení", "ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F", ""),
            ]
            con.executemany(
                "INSERT OR IGNORE INTO inspection_catalog(group_name,label,source_ref,note) VALUES(?,?,?,?)",
                inspection_defaults
            )

            learned_defaults = {
                "network_system": ["TN-C", "TN-S", "TN-C-S", "TT", "IT", "SELV", "PELV", "FELV"],
                "supply_type": ["Cizí distribuční síť", "Vlastní transformátor / trafostanice", "UPS", "Náhradní zdroj / generátor", "Fotovoltaický zdroj / střídač", "Bateriové úložiště", "Ostrovní zdroj", "Kombinované napájení", "Dočasný / staveništní zdroj", "Mobilní generátor", "DC zdroj", "Oddělovací transformátor"],
                "document_type": ["Projektová dokumentace", "Dokumentace skutečného provedení", "Jednopólové schéma", "Protokol o určení vnějších vlivů", "Předchozí revizní zpráva", "Dokumentace rozváděče", "Prohlášení výrobce rozváděče", "Návod výrobce", "PBŘ", "Dokumentace LPS", "Analýza rizika LPS", "Projekt FVE", "Dokumentace stroje", "Schéma řízení", "Protokol měření", "Cizí revizní zpráva"],
                "document_author": [],
                "document_note": ["Dokumentace odpovídá skutečnému provedení.", "Dokumentace byla předložena při revizi.", "Použito jako podklad pro provedení revize."],
                "machine_scope_template": [
                    "Tato revizní zpráva je dílčím podkladem pro posouzení bezpečnosti zdvihacího stroje jako celku a bude jako podklad předložena reviznímu technikovi zdvihacích zařízení, který provede revizi z hlediska mechanických bezpečnostních prvků zařízení a vypracuje celkovou revizní zprávu, do níž zahrne tuto revizní zprávu elektrického zařízení vypracovanou revizním technikem elektro.",
                    "Tato revizní zpráva je dílčím podkladem pro posouzení bezpečnosti strojního zařízení jako celku a vztahuje se pouze k jeho elektrickému zařízení. Nenahrazuje posouzení mechanických, technologických ani ostatních bezpečnostních částí stroje, pokud nejsou výslovně zahrnuty do rozsahu této revize."
                ],
                "legacy_installation_note": [
                    "Elektrická instalace je provedena před platností souboru norem ČSN 33 2000 a je posuzována podle předpisů a norem platných v době jejího vzniku."
                ],
                "protection_measure": ["Automatické odpojení od zdroje", "Dvojitá nebo zesílená izolace", "SELV", "PELV", "Elektrické oddělení", "Proudový chránič", "Ochranné pospojování", "Základní izolace živých částí", "Ochranné přepážky nebo kryty", "Zábrany", "Ochrana polohou (mimo dosah)", "Nevodivé okolí", "Neuzemněné místní pospojování"],
                "operator_instruction": [
                    "Provozovatel byl seznámen s výsledkem revize a se zjištěnými závadami uvedenými v této zprávě.",
                    "Elektrické zařízení je nutné provozovat, obsluhovat a udržovat v souladu s průvodní a provozní dokumentací a pokyny výrobce.",
                    "Změny, opravy nebo jiné zásahy do revidovaného elektrického zařízení mohou ovlivnit závěry této revizní zprávy a musí být odborně posouzeny.",
                    "Provozovatel zajistí, aby byly osoby provádějící obsluhu a údržbu seznámeny s místními podmínkami, riziky a bezpečnostními opatřeními vztahujícími se k provozu zařízení."
                ],
                "conclusion_block": [
                    "Naměřené hodnoty izolačních odporů jsou ve všech případech větší než 1 MΩ, takže vyhovují ČSN 33 2000-6 ed. 2 čl. 6.4.3.3.",
                    "Naměřená hodnota přechodového odporu pospojovacího vodiče nepřesáhla 0,1 Ω a svým průřezem splňuje požadavky ČSN 33 2000-5-54 ed. 3 čl. 544.2.",
                    "Naměřené hodnoty impedančních smyček uváděné v revizní zprávě jsou v souladu s dimenzemi předřadných jistících přístrojů a zajišťují tak požadavky ochrany automatickým odpojením od zdroje v předepsané době podle ČSN 33 2000-4-41 ed. 3 čl. 411.4.4, a to i při uvažování bezpečnostního součinitele, který je uveden v normě ČSN 33 2000-6 ed. 2 čl. D.6.4.3.7.3.",
                    "Vypínací charakteristiky jistících prvků i průřezy vodičů odpovídají předložené dokumentaci.",
                    "U všech obvodů, které napájí světla, je použita doplňková ochrana proudovými chrániči typu A, se jmenovitým reziduálním proudem do 30 mA. Tím je splněn požadavek ČSN 33 2130 ed. 4 čl. 5.2.9.",
                    "U zásuvkových obvodů je použita doplňková ochrana proudovými chrániči typu X se jmenovitým reziduálním proudem do 30 mA. Změřené dotykové napětí při vybavení chrániče jmenovitým proudem bylo ve všech případech menší než 1 V.",
                    "Proudový chránič není použitý u zásuvkového obvodu lednice, v souladu s ČSN 33 2130 ed. 4 čl. 5.3.13.",
                    "Místnost se sprchou a vanou je provedena v souladu s ČSN 33 2000-7-701 ed. 2.",
                    "V koupelně je provedeno místní doplňující pospojování dle ČSN 33 2000-7-701 ed. 2 čl. 701.415.2 vodiči CY 4 mm² zž.",
                    "Přechodový odpor pospojovacího vodiče byl naměřen XXX Ω.",
                    "Umývací prostor v koupelně a kuchyni je v souladu s ČSN 33 2130 ed. 4 čl. 8.8."
                ],
            }
            for category, values in learned_defaults.items():
                for value in values:
                    con.execute("INSERT OR IGNORE INTO learned_values(category,value,usage_count,active) VALUES(?,?,0,1)", (category,value))

    def fetchall(self, sql: str, params: Iterable[Any] = ()):  # -> list[sqlite3.Row]
        with self.connect() as con:
            return con.execute(sql, tuple(params)).fetchall()

    def fetchone(self, sql: str, params: Iterable[Any] = ()):
        with self.connect() as con:
            return con.execute(sql, tuple(params)).fetchone()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self.connect() as con:
            cur = con.execute(sql, tuple(params))
            return int(cur.lastrowid or 0)

    def executemany(self, sql: str, rows: Iterable[Iterable[Any]]):
        with self.connect() as con:
            con.executemany(sql, rows)

    def next_revision_no(self, revision_type: str) -> str:
        prefix = {
            "ELEKTRO": "EI",
            "LPS": "HR",
            "STROJ": "ST",
            "VNEJSI": "VV",
        }.get(revision_type, "RV")
        year = datetime.now().strftime("%y")
        like = f"{year}{prefix}%"
        row = self.fetchone("SELECT revision_no FROM revisions WHERE revision_no LIKE ? ORDER BY revision_no DESC LIMIT 1", (like,))
        if row and row[0]:
            try:
                num = int(str(row[0])[-4:]) + 1
            except ValueError:
                num = 1
        else:
            num = 1
        return f"{year}{prefix}{num:04d}"

    def backup(self) -> Path:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = app_data_dir() / "backups" / f"pz_revize_{stamp}.db"
        self.export_database(dest)
        return dest

    def export_database(self, dest: str | Path) -> Path:
        """Create a consistent SQLite copy of the complete PZ-REVIZE database.

        SQLite's backup API is used instead of a raw file copy so export also works
        correctly when the source database has an active WAL file. Attachments and
        photos are files outside SQLite and are intentionally not embedded in .db.
        """
        with self._operation_lock:
            return self._export_database_unlocked(dest)

    def _export_database_unlocked(self, dest: str | Path) -> Path:
        dest = Path(dest)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        if dest.resolve() == self.path.resolve():
            raise ValueError("Cílový soubor nesmí být aktuálně používaná databáze.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        src = sqlite3.connect(self.path)
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
            check = dst.execute("PRAGMA integrity_check").fetchone()
            if not check or str(check[0]).lower() != "ok":
                raise RuntimeError("Exportovaná databáze neprošla kontrolou integrity.")
        finally:
            dst.close()
            src.close()
        return dest

    @staticmethod
    def _validate_database_file(path: str | Path):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            check = con.execute("PRAGMA integrity_check").fetchone()
            if not check or str(check[0]).lower() != "ok":
                raise ValueError("Soubor není platná databáze SQLite nebo je poškozený.")
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            required = {"revisions", "customers", "settings"}
            missing = required - tables
            if missing:
                raise ValueError("Soubor není databáze PZ-REVIZE - chybí tabulky: " + ", ".join(sorted(missing)))
        finally:
            con.close()

    def import_database(self, source: str | Path) -> Path:
        """Replace the working database by a selected PZ-REVIZE SQLite database.

        The current database is backed up first. The imported DB is copied using
        SQLite backup into a temporary file and atomically swapped in. The normal
        schema migration then upgrades an older compatible PZ-REVIZE database.
        Returns the path of the automatic pre-import backup.
        """
        with self._operation_lock:
            return self._import_database_unlocked(source)

    def _import_database_unlocked(self, source: str | Path) -> Path:
        source = Path(source)
        if source.resolve() == self.path.resolve():
            raise ValueError("Vybraný soubor je již aktuální databáze PZ-REVIZE.")
        self._validate_database_file(source)
        pre_import_backup = self.backup() if self.path.exists() else None
        tmp = self.path.with_name(self.path.name + ".import.tmp")
        if tmp.exists():
            tmp.unlink()
        src = sqlite3.connect(source)
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
            check = dst.execute("PRAGMA integrity_check").fetchone()
            if not check or str(check[0]).lower() != "ok":
                raise RuntimeError("Importovaná databáze neprošla kontrolou integrity.")
        finally:
            dst.close()
            src.close()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.path) + suffix)
            if sidecar.exists():
                try:
                    sidecar.unlink()
                except OSError:
                    pass
        os.replace(tmp, self.path)
        self._init_db()
        self.seed_defaults()
        return pre_import_backup

    def export_json(self, dest: str | Path):
        tables = [
            "customers", "objects", "jobs", "revisions", "circuits", "lps_measurements",
            "machine_measurements", "external_influences", "defect_catalog", "revision_defects",
            "standards", "instruments", "revision_instruments", "revision_attachments", "revision_documents", "revision_standards", "revision_networks", "revision_supplies", "revision_conclusion_blocks", "protection_catalog", "revision_protection_measures", "inspection_catalog", "revision_inspection_items", "revision_photos", "learned_values", "rt_profile"
        ]
        payload: dict[str, Any] = {"exported_at": datetime.now().isoformat(), "tables": {}}
        with self.connect() as con:
            for t in tables:
                rows = con.execute(f"SELECT * FROM {t}").fetchall()
                payload["tables"][t] = [dict(r) for r in rows]
        Path(dest).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def clone_revision(self, source_revision_id: int, mode: str = "periodic") -> int:
        """Create a fresh revision from an existing one without contaminating the new report.

        mode='periodic': same customer/object and technical structure, but fresh header dates,
        measurements/results, defects, photos, instruments and hand-over fields are cleared.
        mode='template': technical body only; customer/object/header are not copied.
        """
        src = self.fetchone("SELECT * FROM revisions WHERE id=?", (source_revision_id,))
        if not src:
            raise ValueError("Zdrojová revize nebyla nalezena")
        r = dict(src)
        mode = (mode or "periodic").lower()
        keep_header = mode == "periodic"
        new_no = self.next_revision_no(r["revision_type"])
        cols = [x[1] for x in self.fetchall("PRAGMA table_info(revisions)") if x[1] not in ("id","created_at","updated_at")]
        payload = {c: r.get(c) for c in cols}
        payload.update({
            "revision_no": new_no,
            "revision_kind": "Pravidelná" if mode == "periodic" else r.get("revision_kind") or "Pravidelná",
            "status": "Rozpracovaná",
            "started_on": datetime.now().strftime("%Y-%m-%d") if keep_header else "",
            "finished_on": "",
            "issued_on": "",
            "next_revision_on": "",
            "deadline_watch": 1,
            "received_on": "",
            "result": "Nehodnoceno",
            "conclusion": "",
            "source_revision_id": source_revision_id,
            "copy_mode": mode,
        })
        if not keep_header:
            payload.update({
                "customer_id": None, "object_id": None, "job_id": None,
                "object_name_text": "", "object_address_text": "", "object_city_text": "",
                "object_zip_text": "", "object_parcel_text": "", "object_location_note": "",
            })
        names=list(payload)
        q=','.join('?' for _ in names)
        new_id=self.execute(f"INSERT INTO revisions({','.join(names)}) VALUES({q})", [payload[n] for n in names])

        # Static/snapshot child tables that are useful for a repeated revision.
        copy_specs = [
            ("revision_documents", ["doc_type","doc_no","doc_date","author","note","stored_path","sort_order"]),
            ("revision_standards", ["standard_id","code_snapshot","title_snapshot","status_snapshot","verified_on_snapshot","article_text","note","sort_order"]),
            ("revision_networks", ["system_name","voltage","scope_text","note","sort_order"]),
            ("revision_supplies", ["supply_type","designation","voltage","backup","note","sort_order"]),
            ("revision_protection_measures", ["catalog_id","group_snapshot","label_snapshot","csn_ref_snapshot","en_ref_snapshot","note","sort_order"]),
            ("revision_inspection_items", ["catalog_id","group_snapshot","label_snapshot","source_ref_snapshot","result","note","sort_order"]),
        ]
        for table, fields in copy_specs:
            rows=self.fetchall(f"SELECT {','.join(fields)} FROM {table} WHERE revision_id=? ORDER BY sort_order,id",(source_revision_id,))
            for row in rows:
                vals=[row[f] for f in fields]
                # New inspection starts as an unconfirmed checklist; keep selection, reset evaluation.
                if table=="revision_inspection_items":
                    vals[fields.index("result")]="NEPROVEDENO"
                    vals[fields.index("note")]=""
                self.execute(f"INSERT INTO {table}(revision_id,{','.join(fields)}) VALUES({','.join('?' for _ in range(len(fields)+1))})", [new_id]+vals)

        rtype=r["revision_type"]
        if rtype=="ELEKTRO":
            static_fields=["designation","name","board","breaker","cable","zs_limit","insulation_voltage","row_type","item_key","parent_key","sort_order","rcd_designation","rcd_device_kind","rcd_type","rcd_delay_type","rcd_poles","rcd_in_a","rcd_idn_ma"]
            select_fields=static_fields+["note"]
            rows=self.fetchall(f"SELECT {','.join(select_fields)} FROM circuits WHERE revision_id=? ORDER BY id",(source_revision_id,))
            all_fields=[x[1] for x in self.fetchall("PRAGMA table_info(circuits)") if x[1] not in ("id","revision_id")]
            for row in rows:
                data={f:"" for f in all_fields}
                for f in static_fields:data[f]=row[f] or ""
                if str(row["row_type"] or "").upper()=="NOTE":data["note"]=row["note"] or ""
                self.execute(f"INSERT INTO circuits(revision_id,{','.join(all_fields)}) VALUES({','.join('?' for _ in range(len(all_fields)+1))})",[new_id]+[data[f] for f in all_fields])
            for row in self.fetchall("SELECT designation,board,spd_type,manufacturer,uc_v,up_kv,test_current_ma FROM varistor_measurements WHERE revision_id=? ORDER BY id",(source_revision_id,)):
                self.execute("INSERT INTO varistor_measurements(revision_id,designation,board,spd_type,manufacturer,uc_v,up_kv,test_current_ma,uvar_pos_v,uvar_neg_v,status_indicator,result,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (new_id,row["designation"],row["board"],row["spd_type"],row["manufacturer"],row["uc_v"],row["up_kv"],row["test_current_ma"],"","","","",""))
        elif rtype=="LPS":
            for row in self.fetchall("SELECT designation,item_type FROM lps_measurements WHERE revision_id=? ORDER BY id",(source_revision_id,)):
                self.execute("INSERT INTO lps_measurements(revision_id,designation,item_type,continuity,earth_resistance,result,note) VALUES(?,?,?,?,?,?,?)",(new_id,row["designation"],row["item_type"],"","","",""))
        elif rtype=="STROJ":
            all_fields=[x[1] for x in self.fetchall("PRAGMA table_info(machine_measurements)") if x[1] not in ("id","revision_id")]
            static_keep={
                "designation","measurement_type","unit","limit_value","row_type","item_key","parent_key","sort_order",
                "name","board","breaker","breaker_current_a","breaker_characteristic","breaker_ia_a","u0_v",
                "zs_safety_factor","cable","insulation_voltage","rcd_designation","rcd_device_kind","rcd_type",
                "rcd_delay_type","rcd_poles","rcd_in_a","rcd_idn_ma"
            }
            for row in self.fetchall(f"SELECT {','.join(all_fields)} FROM machine_measurements WHERE revision_id=? ORDER BY COALESCE(sort_order,id),id",(source_revision_id,)):
                data={f:"" for f in all_fields}
                typ=str(row["row_type"] or "MEASUREMENT").upper()
                for f in static_keep:
                    if f in all_fields:data[f]=row[f] or ""
                if typ in ("NOTE","GROUP","FUNCTION"):
                    if "note" in all_fields:data["note"]=row["note"] or ""
                if typ=="FUNCTION":
                    data["limit_value"]=row["limit_value"] or ""
                self.execute(f"INSERT INTO machine_measurements(revision_id,{','.join(all_fields)}) VALUES({','.join('?' for _ in range(len(all_fields)+1))})",[new_id]+[data[f] for f in all_fields])
        elif rtype=="VNEJSI" and mode=="periodic":
            # Určené místnosti a jejich klasifikace jsou podkladem pro opakované posouzení.
            # Kopírujeme celý snapshot matice; stav výsledku zůstává k novému ověření.
            fields=[x[1] for x in self.fetchall("PRAGMA table_info(external_influences)") if x[1] not in ("id","revision_id")]
            rows=self.fetchall(f"SELECT {','.join(fields)} FROM external_influences WHERE revision_id=? ORDER BY COALESCE(sort_order,id),id",(source_revision_id,))
            for row in rows:
                data={f:row[f] for f in fields}
                data["result"]="K ověření"
                self.execute(f"INSERT INTO external_influences(revision_id,{','.join(fields)}) VALUES({','.join('?' for _ in range(len(fields)+1))})",[new_id]+[data[f] for f in fields])

        # Intentionally NOT copied: defects, defect/working photos, measurement values/results,
        # selected instruments, attachments, hand-over data and conclusion blocks with measured values.
        return new_id

    def copy_attachment(self, source: str | Path) -> str:
        src = Path(source)
        if not src.exists():
            return ""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dest = app_data_dir() / "attachments" / f"{stamp}_{src.name}"
        shutil.copy2(src, dest)
        return str(dest)
