"""Record-safe synchronization guard for PZ-REVIZE 0.4.44.

This module provides conservative merge primitives used by the Windows client:
never replace a non-empty local database with a remote snapshot unless the
local database is unchanged since its last successful synchronization.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


META_TABLE = "pz_sync_meta"


def ensure_meta(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {META_TABLE} ("
        "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    ensure_meta(conn)
    row = conn.execute(f"SELECT value FROM {META_TABLE} WHERE key=?", (key,)).fetchone()
    return default if row is None else str(row[0])


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    ensure_meta(conn)
    conn.execute(
        f"INSERT INTO {META_TABLE}(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(r[1]) for r in conn.execute(f'PRAGMA table_info("{table}")')}
    except sqlite3.Error:
        return set()


def stable_key_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cols = table_columns(conn, table)
    for candidate in (("uuid",), ("id",), ("ev_cislo",), ("number",)):
        if set(candidate) <= cols:
            return list(candidate)
    return []


def changed_row_keys(conn: sqlite3.Connection, table: str) -> set[tuple]:
    """Return stable keys for rows that can be identified safely.

    The function is intentionally conservative: tables without a stable key
    are not treated as mergeable and therefore must never be blindly merged.
    """
    keys = stable_key_columns(conn, table)
    if not keys:
        return set()
    quoted = ",".join(f'"{c}"' for c in keys)
    return {tuple(r) for r in conn.execute(f'SELECT {quoted} FROM "{table}"')}


def is_safe_initial_pull(conn: sqlite3.Connection) -> bool:
    """Only an actually empty application DB may be replaced by NAS data."""
    for table in ("revisions", "customers", "objects", "jobs"):
        if table in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}: 
            if conn.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone() is not None:
                return False
    return True


def backup_before_sync(db_path: str | Path, backup_path: str | Path) -> None:
    """Create a SQLite-consistent backup before any destructive sync step."""
    src = sqlite3.connect(str(db_path))
    try:
        dst = sqlite3.connect(str(backup_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
