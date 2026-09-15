from pathlib import Path
import json
import runpy
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
NAS = ROOT / "source" / "windows" / "pzrevize" / "nas_sync.py"
APP = ROOT / "source" / "windows" / "app.py"

runpy.run_path(str(ROOT / "tools" / "fix_windows_nas_sync_0444.py"), run_name="__pz0444_install__")
s = NAS.read_text(encoding="utf-8")

if "def _pz0500_copy_revision(" not in s:
    s += r'''


def _pz0500_row_value(row):
    return {k: row[k] for k in row.keys()
            if k != "id" and not k.endswith("_id")
            and k not in {"created_at", "updated_at", "usage_count"}}


def _pz0500_logical_revision_signature(conn, revision_id):
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )]
    data = []
    rev = conn.execute("SELECT * FROM revisions WHERE id=?", (revision_id,)).fetchone()
    if rev is None:
        return ""
    data.append(("revisions", _pz0500_row_value(rev)))
    for table in tables:
        if table in {"revisions", "settings", "pz_sync_meta"}:
            continue
        try:
            cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        except sqlite3.Error:
            continue
        if "revision_id" not in cols:
            continue
        rows = conn.execute(f'SELECT * FROM "{table}" WHERE revision_id=?', (revision_id,)).fetchall()
        vals = [_pz0500_row_value(r) for r in rows]
        vals.sort(key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, default=str))
        data.append((table, vals))
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def _pz0500_revision_map(db_path):
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT id, revision_no FROM revisions ORDER BY revision_no").fetchall()
        return {str(r["revision_no"]): _pz0500_logical_revision_signature(con, r["id"]) for r in rows}
    finally:
        con.close()


def compare_database_states(local_db, remote_db):
    local = _pz0500_revision_map(local_db)
    remote = _pz0500_revision_map(remote_db)
    local_only = sorted(set(local) - set(remote))
    remote_only = sorted(set(remote) - set(local))
    changed = sorted(k for k in set(local) & set(remote) if local[k] != remote[k])
    relation = "conflict" if changed or (local_only and remote_only) else (
        "local_superset" if local_only else "remote_superset" if remote_only else "equal")
    return {"relation": relation, "local_only_revisions": local_only,
            "remote_only_revisions": remote_only, "changed_revisions": changed}


def _pz0500_copy_revision(local_db, remote_db, revision_no):
    con_l = sqlite3.connect(str(local_db))
    con_r = sqlite3.connect(str(remote_db))
    con_l.row_factory = sqlite3.Row
    con_r.row_factory = sqlite3.Row
    try:
        rr = con_r.execute("SELECT * FROM revisions WHERE revision_no=?", (revision_no,)).fetchone()
        if rr is None or con_l.execute("SELECT 1 FROM revisions WHERE revision_no=?", (revision_no,)).fetchone():
            return False
        rev_cols = [r[1] for r in con_l.execute("PRAGMA table_info(revisions)") if r[1] != "id"]
        vals = [rr[c] if c in rr.keys() else None for c in rev_cols]
        cur = con_l.execute(
            f'INSERT INTO revisions ({",".join(chr(34)+c+chr(34) for c in rev_cols)}) VALUES ({",".join("?" for _ in vals)})', vals)
        new_id, old_id = cur.lastrowid, rr["id"]
        tables = [r[0] for r in con_r.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        for table in tables:
            if table in {"revisions", "settings", "pz_sync_meta"}:
                continue
            cols = [r[1] for r in con_r.execute(f'PRAGMA table_info("{table}")')]
            if "revision_id" not in cols:
                continue
            for row in con_r.execute(f'SELECT * FROM "{table}" WHERE revision_id=?', (old_id,)).fetchall():
                out_cols = [c for c in cols if c != "id"]
                out_vals = [row[c] for c in out_cols]
                out_vals[out_cols.index("revision_id")] = new_id
                for idx, col in enumerate(out_cols):
                    if col.endswith("_id") and col != "revision_id" and col in {"catalog_id", "standard_id", "customer_id", "object_id", "instrument_id"}:
                        out_vals[idx] = None
                try:
                    con_l.execute(
                        f'INSERT INTO "{table}" ({",".join(chr(34)+c+chr(34) for c in out_cols)}) VALUES ({",".join("?" for _ in out_cols)})', out_vals)
                except sqlite3.IntegrityError:
                    pass
        con_l.commit()
        return True
    finally:
        con_r.close()
        con_l.close()

'''

app = APP.read_text(encoding="utf-8")
for old in ('0.5.0', '0.4.44', '0.4.43', '0.4.35'):
    app = app.replace(f'VERSION = "{old}"', 'VERSION = "0.5.1"')
APP.write_text(app, encoding="utf-8")
NAS.write_text(s, encoding="utf-8")
print("Installed PZ-REVIZE 0.5.1 new multi-PC synchronization")
