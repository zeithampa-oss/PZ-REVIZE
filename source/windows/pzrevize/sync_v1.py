# PZ-REVIZE SYNC 1.0
# New revision-oriented synchronization layer. See sync_v1_fixed.py from the delivered source package.
# This module is intentionally isolated from the legacy snapshot synchronizer.

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

SYNC_VERSION = "1.0"

class SyncV1Error(Exception):
    pass

class SyncV1Conflict(SyncV1Error):
    pass

def _canon(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes__": hashlib.sha256(value).hexdigest()}
    if isinstance(value, (dict, list, tuple)):
        if isinstance(value, dict):
            return {str(k): _canon(value[k]) for k in sorted(value)}
        return [_canon(x) for x in value]
    return value

def _logical_row(columns, row):
    out = {}
    for col, value in zip(columns, row):
        name = col.lower()
        if name == "id" or name.endswith("_id") or name in {"created_at", "updated_at", "usage_count"}:
            continue
        out[col] = _canon(value)
    return out

def _revision_signature(conn: sqlite3.Connection, revision_id: int) -> str:
    parts = []
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    for (table,) in tables:
        cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        names = [c[1] for c in cols]
        if "revision_id" not in names:
            continue
        rows = conn.execute(f'SELECT * FROM "{table}" WHERE revision_id=?', (revision_id,)).fetchall()
        logical = [_logical_row(names, r) for r in rows]
        logical.sort(key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False, default=str))
        parts.append((table, logical))
    payload = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def ensure_schema(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(revisions)")}
        if "sync_uid" not in cols:
            conn.execute("ALTER TABLE revisions ADD COLUMN sync_uid TEXT")
        conn.execute("UPDATE revisions SET sync_uid=? WHERE sync_uid IS NULL OR sync_uid=''", (str(uuid.uuid4()),))
        conn.execute("CREATE TABLE IF NOT EXISTS pz_sync_revision_state (sync_uid TEXT PRIMARY KEY, content_hash TEXT NOT NULL, last_sync TEXT)")
        for uid, rid in conn.execute("SELECT sync_uid,id FROM revisions WHERE sync_uid IS NOT NULL"):
            h = _revision_signature(conn, rid)
            conn.execute("INSERT INTO pz_sync_revision_state(sync_uid,content_hash) VALUES(?,?) ON CONFLICT(sync_uid) DO UPDATE SET content_hash=excluded.content_hash", (uid,h))
        conn.commit()

def build_manifest(db_path: str) -> list[dict[str, str]]:
    ensure_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        rows=[]
        for uid, no, rid in conn.execute("SELECT sync_uid, revision_no, id FROM revisions WHERE sync_uid IS NOT NULL"):
            rows.append({"sync_uid":uid,"revision_no":str(no),"content_hash":_revision_signature(conn,rid)})
        return rows

def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)

def export_revision(db_path: str, sync_uid: str, output_zip: str) -> None:
    ensure_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        rev = conn.execute("SELECT * FROM revisions WHERE sync_uid=?", (sync_uid,)).fetchone()
        if not rev: raise SyncV1Error(f"Revision {sync_uid} not found")
        rcols=[c[1] for c in conn.execute("PRAGMA table_info(revisions)")]
        rid=rev[rcols.index("id")]
        tables=[]
        for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            cols=[c[1] for c in conn.execute(f'PRAGMA table_info("{table}")')]
            if table == "revisions" or "revision_id" in cols:
                rows=conn.execute(f'SELECT * FROM "{table}" WHERE ' + ("id=?" if table=="revisions" else "revision_id=?"), (rid,)).fetchall()
                if rows: tables.append({"table":table,"columns":cols,"rows":[list(r) for r in rows]})
        meta={"sync_version":SYNC_VERSION,"sync_uid":sync_uid,"revision_no":str(rev[rcols.index("revision_no")]),"content_hash":_revision_signature(conn,rid),"tables":tables}
    with zipfile.ZipFile(output_zip,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("revision.json", json.dumps(meta, ensure_ascii=False, default=str))

def import_revision(db_path: str, bundle_zip: str) -> None:
    ensure_schema(db_path)
    with zipfile.ZipFile(bundle_zip) as z:
        meta=json.loads(z.read("revision.json").decode("utf-8"))
    uid=meta["sync_uid"]
    with sqlite3.connect(db_path) as conn:
        if conn.execute("SELECT 1 FROM revisions WHERE sync_uid=?",(uid,)).fetchone():
            return
        for item in meta["tables"]:
            table=item["table"]; cols=item["columns"]
            if table != "revisions" and "revision_id" in cols:
                ridx=cols.index("revision_id")
                for row in item["rows"]: row[ridx]=None
            placeholders=",".join("?" for _ in cols)
            existing_cols={r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
            use=[(c,i) for i,c in enumerate(cols) if c in existing_cols and c!="id"]
            if not use: continue
            names=[x[0] for x in use]; idx=[x[1] for x in use]
            for row in item["rows"]:
                vals=[row[i] for i in idx]
                if table != "revisions" and "revision_id" in names:
                    ri=names.index("revision_id")
                    local_rid=conn.execute("SELECT id FROM revisions WHERE sync_uid=?",(uid,)).fetchone()
                    if local_rid: vals[ri]=local_rid[0]
                try:
                    conn.execute(f'INSERT INTO "{table}" ({",".join(names)}) VALUES ({",".join("?" for _ in names)})', vals)
                except sqlite3.IntegrityError:
                    pass
        conn.commit()

def sync_once(db_path: str, server, api_key: str) -> dict:
    ensure_schema(db_path)
    local=build_manifest(db_path)
    remote=server.manifest(api_key)
    rmap={x["sync_uid"]:x for x in remote}
    lmap={x["sync_uid"]:x for x in local}
    conflicts=[]
    for uid, r in rmap.items():
        if uid in lmap and lmap[uid]["content_hash"] != r["content_hash"]:
            conflicts.append(uid)
    if conflicts: raise SyncV1Conflict("Konflikt revizí: " + ", ".join(conflicts))
    with tempfile.TemporaryDirectory() as td:
        for uid in set(lmap)-set(rmap):
            p=os.path.join(td,uid+".zip"); export_revision(db_path,uid,p); server.push(api_key,p,uid,lmap[uid]["content_hash"])
        for uid in set(rmap)-set(lmap):
            p=os.path.join(td,uid+".zip"); server.pull(api_key,uid,p); import_revision(db_path,p)
    return {"uploaded":len(set(lmap)-set(rmap)),"downloaded":len(set(rmap)-set(lmap)),"conflicts":conflicts}
