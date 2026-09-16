"""Standalone PZ-REVIZE SYNC 2.0 test application.

This is intentionally independent from the production application. It lets
Windows testing exercise the new multi-device sync protocol before integration.
Run: python demo_app.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from urllib import request, error

DB = Path(os.environ.get("PZ_REVIZE_SYNC_TEST_DB", Path.home() / "PZ_REVIZE_SYNC_TEST.sqlite3"))
CONFIG = Path(os.environ.get("PZ_REVIZE_SYNC_TEST_CONFIG", Path.home() / "PZ_REVIZE_SYNC_TEST.json"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_outbox (
    change_id TEXT PRIMARY KEY,
    entity TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at REAL NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sync_cursor (stream TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0);
"""


def db():
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)
    c.execute("INSERT OR IGNORE INTO sync_cursor(stream,cursor) VALUES('main',0)")
    c.commit()
    return c


def cfg():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    return {"device_id": str(uuid.uuid4()), "server_url": "http://127.0.0.1:8765"}


def save_cfg(c):
    CONFIG.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")


def queue_change(entity, entity_id, fields, kind="upsert"):
    change_id = str(uuid.uuid4())
    with db() as c:
        c.execute("INSERT INTO sync_outbox VALUES(?,?,?,?,?,?,?,0)", (change_id, entity, entity_id, kind, json.dumps(fields, ensure_ascii=False), time.time(), "pending"))
    return change_id


def post_json(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def sync_once():
    c = cfg()
    with db() as con:
        rows = con.execute("SELECT change_id,entity,entity_id,kind,payload,created_at FROM sync_outbox WHERE state='pending' ORDER BY created_at LIMIT 100").fetchall()
        cursor = con.execute("SELECT cursor FROM sync_cursor WHERE stream='main'").fetchone()[0]
    changes = []
    for row in rows:
        changes.append({"change_id": row[0], "entity": row[1], "entity_id": row[2], "kind": row[3], "fields": json.loads(row[4]), "created_at": row[5], "device_id": c["device_id"]})
    try:
        result = post_json(c["server_url"].rstrip("/") + "/sync/v2/batch", {"device_id": c["device_id"], "cursor": cursor, "changes": changes})
    except (OSError, error.URLError) as exc:
        print(f"OFFLINE: {exc}")
        return
    with db() as con:
        for cid in result.get("accepted", []) + result.get("already_applied", []):
            con.execute("UPDATE sync_outbox SET state='done' WHERE change_id=?", (cid,))
        con.execute("UPDATE sync_cursor SET cursor=? WHERE stream='main'", (int(result.get("cursor", cursor)),))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    c = cfg(); save_cfg(c)
    print("PZ-REVIZE SYNC 2.0 test client")
    print(f"Device: {c['device_id']}")
    print(f"DB: {DB}")
    print(f"Server: {c['server_url']}")
    if len(sys.argv) >= 4 and sys.argv[1] == "add":
        cid = queue_change(sys.argv[2], sys.argv[3], {"test_value": time.strftime("%Y-%m-%d %H:%M:%S")})
        print(f"Queued: {cid}")
    elif len(sys.argv) >= 2 and sys.argv[1] == "sync":
        sync_once()
    else:
        print("Usage: demo_app.py add <entity> <entity_id> | sync")


if __name__ == "__main__":
    main()
