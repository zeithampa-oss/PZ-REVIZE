from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import sqlite3
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from .database import app_data_dir

SNAPSHOT_FORMAT = "PZ-REVIZE-SNAPSHOT-1"

PATH_FIELDS = [
    ("revision_attachments", "stored_path"),
    ("revision_documents", "stored_path"),
    ("revision_photos", "stored_path"),
    ("revision_defects", "photo_path"),
    ("rt_profile", "logo_path"),
    ("rt_profile", "stamp_path"),
    ("rt_profile", "signature_path"),
]


class NasSyncError(RuntimeError):
    pass


class NasConflictError(NasSyncError):
    def __init__(self, message: str, server_generation: int | None = None):
        super().__init__(message)
        self.server_generation = server_generation


def _new_temp_path(prefix: str, suffix: str) -> Path:
    """Create a temporary pathname without leaving the mkstemp handle open.

    Windows locks an open mkstemp file, so the descriptor must be closed before
    ZipFile/open/unlink uses the path.
    """
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)
    return Path(name)


def _clean_url(value: str) -> str:
    return str(value or "").strip().rstrip("/")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _safe_member(name: str) -> bool:
    p = Path(name)
    return not p.is_absolute() and ".." not in p.parts


def _setting(db, key: str, default: str = "") -> str:
    row = db.fetchone("SELECT value FROM settings WHERE key=?", (key,))
    return str(row["value"]) if row and row["value"] is not None else default


def set_setting(db, key: str, value: str) -> None:
    db.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_sync_settings(db) -> dict:
    legacy_url = _setting(db, "nas_url", "")
    lan_url = _setting(db, "nas_url_lan", legacy_url or "http://ADRESA_NAS:8767")
    vpn_url = _setting(db, "nas_url_vpn", "")
    mode = (_setting(db, "nas_connection_mode", "auto") or "auto").lower()
    if mode not in ("auto", "lan", "vpn"):
        mode = "auto"
    return {
        "url": lan_url,  # compatibility with older UI/code
        "lan_url": lan_url,
        "vpn_url": vpn_url,
        "mode": mode,
        "token": _setting(db, "nas_api_token", ""),
        "generation": int(_setting(db, "nas_generation", "0") or 0),
        "last_sync": _setting(db, "nas_last_sync", ""),
        "last_transport": _setting(db, "nas_last_transport", ""),
        "last_signature": _setting(db, "nas_last_signature", ""),
        "last_sync_result": _setting(db, "nas_last_sync_result", ""),
        "last_sync_error": _setting(db, "nas_last_sync_error", ""),
    }


def save_sync_settings(db, url: str, token: str, vpn_url: str | None = None, mode: str | None = None) -> None:
    lan = _clean_url(url)
    vpn = _clean_url(vpn_url or "")
    mode_value = (mode or _setting(db, "nas_connection_mode", "auto") or "auto").lower()
    if mode_value not in ("auto", "lan", "vpn"):
        mode_value = "auto"
    # Keep nas_url for backward compatibility with 0.3.6.
    set_setting(db, "nas_url", lan)
    set_setting(db, "nas_url_lan", lan)
    set_setting(db, "nas_url_vpn", vpn)
    set_setting(db, "nas_connection_mode", mode_value)
    set_setting(db, "nas_api_token", token.strip())


def endpoint_candidates(settings: dict) -> list[tuple[str, str]]:
    mode = (settings.get("mode") or "auto").lower()
    lan = _clean_url(settings.get("lan_url") or settings.get("url") or "")
    vpn = _clean_url(settings.get("vpn_url") or "")
    rows: list[tuple[str, str]] = []
    if mode in ("auto", "lan") and lan and "ADRESA_NAS" not in lan:
        rows.append((lan, "LAN"))
    if mode in ("auto", "vpn") and vpn and "ADRESA_NAS" not in vpn:
        rows.append((vpn, "VPN"))
    return rows


def resolve_endpoint(settings: dict, timeout: int = 6) -> tuple[str, str, dict]:
    token = str(settings.get("token") or "").strip()
    if not token:
        raise NasSyncError("Není zadaný API klíč.")
    candidates = endpoint_candidates(settings)
    if not candidates:
        if (settings.get("mode") or "auto") == "vpn":
            raise NasSyncError("Není zadaná VPN adresa NAS serveru.")
        raise NasSyncError("Nejdřív zadej adresu NAS serveru (LAN nebo VPN).")
    errors = []
    for url, transport in candidates:
        try:
            st = get_status(url, token, timeout=timeout)
            return url, transport, st
        except Exception as exc:
            errors.append(f"{transport}: {exc}")
    raise NasSyncError("NAS není dostupný přes žádné nastavené připojení. " + " | ".join(errors))



def _normalize_db_paths(db_copy: Path, stage_attachments: Path) -> dict:
    """Copy referenced files into bundle attachments and rewrite DB copy to relative paths."""
    stage_attachments.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    missing: list[str] = []
    con = sqlite3.connect(db_copy)
    con.row_factory = sqlite3.Row
    try:
        for table, column in PATH_FIELDS:
            try:
                rows = con.execute(
                    f"SELECT rowid AS _rid, {column} AS _path FROM {table} WHERE {column} IS NOT NULL AND TRIM({column})<>''"
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for row in rows:
                raw = str(row["_path"] or "").strip()
                if not raw:
                    continue
                src = Path(raw)
                if raw.replace("\\", "/").startswith("attachments/"):
                    local_guess = app_data_dir() / raw.replace("\\", "/")
                    if local_guess.exists():
                        src = local_guess
                if not src.exists() or not src.is_file():
                    missing.append(raw)
                    continue
                key = str(src.resolve())
                rel = copied.get(key)
                if not rel:
                    digest = _sha256(src)[:12]
                    safe_name = src.name.replace("/", "_").replace("\\", "_")
                    bundle_name = safe_name if safe_name.startswith(digest + "_") else f"{digest}_{safe_name}"
                    rel = str(Path("attachments") / bundle_name).replace("\\", "/")
                    dest = stage_attachments / Path(rel).name
                    if not dest.exists():
                        shutil.copy2(src, dest)
                    copied[key] = rel
                con.execute(f"UPDATE {table} SET {column}=? WHERE rowid=?", (rel, row["_rid"]))

        # NAS connection data and API key must never be embedded in the shared DB snapshot.
        con.execute("DELETE FROM settings WHERE key LIKE 'nas_%'")
        con.commit()
    finally:
        con.close()
    return {"copied_files": len(copied), "missing_files": missing}


def _rewrite_db_paths_to_local(db_path: Path, local_attachments: Path) -> None:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        for table, column in PATH_FIELDS:
            try:
                rows = con.execute(
                    f"SELECT rowid AS _rid, {column} AS _path FROM {table} WHERE {column} IS NOT NULL AND TRIM({column})<>''"
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for row in rows:
                raw = str(row["_path"] or "").strip().replace("\\", "/")
                if raw.startswith("attachments/"):
                    absolute = local_attachments / Path(raw).name
                    con.execute(f"UPDATE {table} SET {column}=? WHERE rowid=?", (str(absolute), row["_rid"]))
        con.commit()
    finally:
        con.close()


def build_snapshot_bundle(db, client_version: str, dest: Path | None = None) -> tuple[Path, dict]:
    tmp_root = Path(tempfile.mkdtemp(prefix="pzrev_sync_build_"))
    try:
        db_copy = tmp_root / "pz_revize.db"
        db.export_database(db_copy)
        snapshot_signature = database_logical_signature(db_copy)
        stage_att = tmp_root / "attachments"
        files_info = _normalize_db_paths(db_copy, stage_att)
        manifest = {
            "format": SNAPSHOT_FORMAT,
            "client_version": client_version,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "db_sha256": _sha256(db_copy),
            "source_generation": int(_setting(db, "nas_generation", "0") or 0),
            "file_count": files_info["copied_files"],
            "missing_file_count": len(files_info["missing_files"]),
        }
        out = Path(dest) if dest else _new_temp_path("PZ_REVIZE_SYNC_", ".zip")
        if out.exists():
            out.unlink()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.write(db_copy, "pz_revize.db")
            if stage_att.exists():
                for p in stage_att.rglob("*"):
                    if p.is_file():
                        z.write(p, str(Path("attachments") / p.relative_to(stage_att)))
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        return out, {**manifest, "missing_files": files_info["missing_files"], "logical_signature": snapshot_signature}
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def _json_request(base_url: str, path: str, token: str, timeout: int = 30) -> dict:
    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url, headers={"X-API-Key": token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
            detail = json.loads(body).get("detail", body)
        except Exception:
            detail = str(e)
        raise NasSyncError(f"NAS odpověděl HTTP {e.code}: {detail}") from e
    except Exception as e:
        raise NasSyncError(f"Nelze se spojit s NAS: {e}") from e


def get_status(base_url: str, token: str, timeout: int = 30) -> dict:
    if not base_url or "ADRESA_NAS" in base_url:
        raise NasSyncError("Nejdřív zadej skutečnou adresu NAS serveru.")
    if not token:
        raise NasSyncError("Není zadaný API klíč.")
    return _json_request(base_url, "/api/status", token, timeout=timeout)


def _post_bundle(base_url: str, token: str, bundle_path: Path, expected_generation: int, client_name: str) -> dict:
    parsed = urllib.parse.urlparse(base_url.rstrip("/"))
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise NasSyncError("Neplatná adresa NAS serveru.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    base_path = parsed.path.rstrip("/")
    endpoint = (base_path + "/api/sync/push") or "/api/sync/push"
    boundary = "----PZREVIZE" + uuid.uuid4().hex
    crlf = "\r\n"
    fields = [
        ("expected_generation", str(expected_generation)),
        ("client_name", client_name),
    ]
    pre_parts = []
    for name, value in fields:
        pre_parts.append(f"--{boundary}{crlf}Content-Disposition: form-data; name=\"{name}\"{crlf}{crlf}{value}{crlf}".encode("utf-8"))
    pre_parts.append(
        f"--{boundary}{crlf}Content-Disposition: form-data; name=\"bundle\"; filename=\"PZ_REVIZE_SYNC.zip\"{crlf}Content-Type: application/zip{crlf}{crlf}".encode("utf-8")
    )
    pre = b"".join(pre_parts)
    post = f"{crlf}--{boundary}--{crlf}".encode("utf-8")
    content_length = len(pre) + bundle_path.stat().st_size + len(post)

    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.hostname, port, timeout=180)
    try:
        conn.putrequest("POST", endpoint)
        conn.putheader("X-API-Key", token)
        conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        conn.putheader("Content-Length", str(content_length))
        conn.putheader("Accept", "application/json")
        conn.endheaders()
        conn.send(pre)
        with bundle_path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                conn.send(chunk)
        conn.send(post)
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", "replace")
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {"detail": body}
        if resp.status == 409:
            detail = payload.get("detail", {})
            if isinstance(detail, dict):
                gen = detail.get("server_generation")
                msg = detail.get("message") or "Konflikt synchronizace"
            else:
                gen = None
                msg = str(detail)
            raise NasConflictError(msg, int(gen) if gen is not None else None)
        if resp.status < 200 or resp.status >= 300:
            raise NasSyncError(f"NAS odpověděl HTTP {resp.status}: {payload.get('detail', body)}")
        return payload
    except (NasConflictError, NasSyncError):
        raise
    except Exception as e:
        raise NasSyncError(f"Odeslání na NAS selhalo: {e}") from e
    finally:
        conn.close()


def push_to_nas(db, base_url: str, token: str, client_version: str, client_name: str = "PZ-REVIZE PC", expected_generation: int | None = None) -> dict:
    expected = int(_setting(db, "nas_generation", "0") or 0) if expected_generation is None else int(expected_generation)
    bundle, info = build_snapshot_bundle(db, client_version)
    try:
        result = _post_bundle(base_url, token, bundle, expected, client_name)
    finally:
        try:
            bundle.unlink()
        except OSError:
            pass
    generation = int(result.get("generation") or expected)
    set_setting(db, "nas_generation", str(generation))
    set_setting(db, "nas_last_sync", datetime.now().isoformat(timespec="seconds"))
    # Only the exported snapshot is confirmed on NAS. Edits made while it was
    # uploading must remain pending for the next synchronization pass.
    set_setting(db, "nas_last_signature", info["logical_signature"])
    set_setting(db, "nas_last_sync_result", "push")
    set_setting(db, "nas_last_sync_error", "")
    return {**result, "bundle_info": info}


def _download_bundle(base_url: str, token: str, dest: Path) -> int:
    url = base_url.rstrip("/") + "/api/sync/pull"
    req = urllib.request.Request(url, headers={"X-API-Key": token, "Accept": "application/zip"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp, dest.open("wb") as out:
            generation = int(resp.headers.get("X-PZ-Generation", "0") or 0)
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
            return generation
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8", "replace")).get("detail")
        except Exception:
            detail = str(e)
        raise NasSyncError(f"Stažení z NAS selhalo (HTTP {e.code}): {detail}") from e
    except Exception as e:
        raise NasSyncError(f"Stažení z NAS selhalo: {e}") from e


def create_complete_local_backup(db, prefix: str = "before_nas_pull") -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = app_data_dir() / "backups" / f"pz_revize_{prefix}_{stamp}.zip"
    bundle, _ = build_snapshot_bundle(db, "local-backup", dest=dest)
    return bundle


def pull_from_nas(db, base_url: str, token: str, can_pull=None) -> dict:
    sync_before = get_sync_settings(db)
    temp_zip = _new_temp_path("PZ_REVIZE_PULL_", ".zip")
    stage = Path(tempfile.mkdtemp(prefix="pzrev_sync_pull_"))
    backup = create_complete_local_backup(db)
    generation_header = 0
    try:
        generation_header = _download_bundle(base_url, token, temp_zip)
        with zipfile.ZipFile(temp_zip, "r") as z:
            for info in z.infolist():
                if not _safe_member(info.filename):
                    raise NasSyncError("NAS balík obsahuje neplatnou cestu.")
            z.extractall(stage)
        db_in = stage / "pz_revize.db"
        manifest_path = stage / "manifest.json"
        if not db_in.exists() or not manifest_path.exists():
            raise NasSyncError("NAS balík je neúplný.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format") != SNAPSHOT_FORMAT:
            raise NasSyncError("NAS používá nepodporovaný formát synchronizace.")
        db._validate_database_file(db_in)
        if manifest.get("db_sha256") and manifest.get("db_sha256") != _sha256(db_in):
            raise NasSyncError("Kontrolní součet stažené databáze nesouhlasí.")
        if int(manifest.get("missing_file_count") or 0) > 0:
            raise NasSyncError("NAS záloha nemá všechny soubory příloh; lokální stav zůstává zachován.")

        # Serialize the final comparison and replacement with all local writes.
        # This is the last line of defence for BOTH automatic and manual pulls:
        # a revision saved after the earlier comparison must never disappear.
        with db._operation_lock:
            if can_pull is not None and not can_pull():
                raise NasSyncError("Během stahování byla otevřena revize; nahrazení lokální databáze bylo odloženo.")
            relation = compare_database_states(db.path, db_in)
            if relation["relation"] not in ("remote_superset", "equal"):
                raise NasConflictError(
                    "Stažení z NAS zablokováno: v tomto PC jsou změny, které NAS neobsahuje. "
                    "Lokální revize zůstaly zachovány; před stažením je nutné konflikt vyřešit."
                )
            local_att = app_data_dir() / "attachments"
            incoming_att = stage / "attachments"
            new_att = app_data_dir() / "attachments.nas_new"
            old_att = app_data_dir() / "attachments.nas_old"
            shutil.rmtree(new_att, ignore_errors=True)
            shutil.rmtree(old_att, ignore_errors=True)
            new_att.mkdir(parents=True, exist_ok=True)
            if incoming_att.exists():
                for p in incoming_att.rglob("*"):
                    rel = p.relative_to(incoming_att)
                    dest = new_att / rel
                    if p.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, dest)

            # DB must point at the final local attachment location.
            _rewrite_db_paths_to_local(db_in, local_att)
            db.import_database(db_in)

            if local_att.exists():
                os.replace(local_att, old_att)
            os.replace(new_att, local_att)
            shutil.rmtree(old_att, ignore_errors=True)

        # Restore this PC's private NAS configuration after replacing the shared DB.
        save_sync_settings(db, sync_before["lan_url"], sync_before["token"], sync_before.get("vpn_url", ""), sync_before.get("mode", "auto"))
        generation = int(manifest.get("generation") or generation_header or 0)
        set_setting(db, "nas_generation", str(generation))
        set_setting(db, "nas_last_sync", datetime.now().isoformat(timespec="seconds"))
        # Final validation is performed on the actual local working DB.
        db._validate_database_file(db.path)
        set_setting(db, "nas_last_signature", database_logical_signature(db.path))
        set_setting(db, "nas_last_sync_result", "pull")
        set_setting(db, "nas_last_sync_error", "")
        counts = {
            "revisions": int((db.fetchone("SELECT COUNT(*) AS n FROM revisions") or {"n": 0})["n"]),
            "customers": int((db.fetchone("SELECT COUNT(*) AS n FROM customers") or {"n": 0})["n"]),
        }
        return {
            "ok": True,
            "generation": generation,
            "created_at": manifest.get("created_at"),
            "backup": str(backup),
            "local_db": str(db.path),
            "local_attachments": str(local_att),
            "counts": counts,
        }
    finally:
        try:
            temp_zip.unlink()
        except OSError:
            pass
        shutil.rmtree(stage, ignore_errors=True)


# ---------------------------------------------------------------------------
# Safe automatic synchronisation
# ---------------------------------------------------------------------------
# The old workflow required a pull before a push whenever the NAS generation
# was newer.  That is dangerous for an offline-first desktop application:
# local revisions created while the PC was disconnected can then be replaced by
# an older logical dataset from the NAS.  The helpers below compare both
# snapshots first and only perform a destructive pull when the local database is
# demonstrably a subset of the NAS state.

_REVISION_CHILD_TABLES = (
    "circuits", "varistor_measurements", "lps_measurements", "machine_measurements",
    "external_influences", "revision_defects", "revision_instruments",
    "revision_attachments", "revision_documents", "revision_standards",
    "revision_networks", "revision_supplies", "revision_conclusion_blocks",
    "revision_protection_measures", "revision_inspection_items", "revision_photos",
)

_GLOBAL_COMPARE_TABLES = (
    "customers", "objects", "jobs", "defect_catalog", "standards", "standard_catalog_documents", "instruments",
    "protection_catalog", "inspection_catalog", "learned_values", "rt_profile",
    "settings",
)

_VOLATILE_COLUMNS = {"id", "created_at", "updated_at", "usage_count"}


def _normalize_compare_value(column: str, value):
    if value is None:
        return None
    if column.endswith("_path") or column in {"stored_path", "photo_path", "logo_path", "stamp_path", "signature_path"}:
        text = str(value).replace("\\", "/")
        name = text.rsplit("/", 1)[-1] if text else ""
        # A NAS snapshot stores a content-hashed attachment name while this PC
        # may still store the original absolute path. Compare the actual bytes.
        if text.startswith("attachments/"):
            return name
        local = Path(text)
        if local.is_file():
            digest = _sha256(local)[:12]
            if re.match(r"^[0-9a-f]{12}_", name) and name.startswith(digest + "_"):
                return name
            return f"{digest}_{name}"
        return f"MISSING:{name}"
    return value


def _canonical_row(row, extra_drop=()) -> dict:
    drop = _VOLATILE_COLUMNS | set(extra_drop)
    return {
        k: _normalize_compare_value(k, row[k])
        for k in row.keys()
        if k not in drop
    }


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _canonical_table_rows(con: sqlite3.Connection, table: str, where: str = "", params=(), extra_drop=()) -> list[str]:
    if not _table_exists(con, table):
        return []
    sql = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
    rows = con.execute(sql, params).fetchall()
    encoded = [json.dumps(_canonical_row(r, extra_drop), ensure_ascii=False, sort_keys=True, default=str) for r in rows]
    encoded.sort()
    return encoded


def _revision_fingerprints(path: str | Path) -> dict[str, str]:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        if not _table_exists(con, "revisions"):
            return {}
        out = {}
        for rev in con.execute("SELECT * FROM revisions ORDER BY revision_no,id").fetchall():
            no = str(rev["revision_no"] or f"#ID:{rev['id']}")
            payload = {"revision": _canonical_row(rev, {"customer_id", "object_id", "job_id"}), "children": {}}
            rid = rev["id"]
            for table in _REVISION_CHILD_TABLES:
                payload["children"][table] = _canonical_table_rows(con, table, "revision_id=?", (rid,), {"revision_id"})
            raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            out[no] = hashlib.sha256(raw).hexdigest()
        return out
    finally:
        con.close()


def _global_row_sets(path: str | Path) -> dict[str, set[str]]:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        result = {}
        for table in _GLOBAL_COMPARE_TABLES:
            # FK ids are intentionally kept.  Two databases descended from the same
            # generation preserve them, which makes divergent edits visible instead
            # of silently choosing one side.
            where = "key NOT LIKE 'nas_%'" if table == "settings" else ""
            result[table] = set(_canonical_table_rows(con, table, where))
        return result
    finally:
        con.close()


def compare_database_states(local_path: str | Path, remote_path: str | Path) -> dict:
    """Classify two complete snapshots without modifying either side.

    Returns one of: equal, local_superset, remote_superset, conflict.  A superset
    means that every revision/global row from the other side is present unchanged,
    so replacing the smaller snapshot with the larger one cannot delete data.
    """
    local_rev = _revision_fingerprints(local_path)
    remote_rev = _revision_fingerprints(remote_path)
    common = set(local_rev) & set(remote_rev)
    changed = sorted(k for k in common if local_rev[k] != remote_rev[k])
    local_only = sorted(set(local_rev) - set(remote_rev))
    remote_only = sorted(set(remote_rev) - set(local_rev))

    lg = _global_row_sets(local_path)
    rg = _global_row_sets(remote_path)
    global_local_superset = all(rg.get(t, set()) <= lg.get(t, set()) for t in _GLOBAL_COMPARE_TABLES)
    global_remote_superset = all(lg.get(t, set()) <= rg.get(t, set()) for t in _GLOBAL_COMPARE_TABLES)

    if changed:
        relation = "conflict"
    elif not local_only and not remote_only and global_local_superset and global_remote_superset:
        relation = "equal"
    elif not remote_only and global_local_superset:
        relation = "local_superset"
    elif not local_only and global_remote_superset:
        relation = "remote_superset"
    else:
        relation = "conflict"
    return {
        "relation": relation,
        "local_only_revisions": local_only,
        "remote_only_revisions": remote_only,
        "changed_revisions": changed,
        "local_revision_count": len(local_rev),
        "remote_revision_count": len(remote_rev),
    }


def database_logical_signature(path: str | Path) -> str:
    """Stable logical signature used to detect local edits since the last sync."""
    path = Path(path)
    payload = {
        "revisions": _revision_fingerprints(path),
        "globals": {k: sorted(v) for k, v in _global_row_sets(path).items()},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compare_with_nas(db, base_url: str, token: str) -> dict:
    temp_zip = _new_temp_path("PZ_REVIZE_COMPARE_", ".zip")
    stage = Path(tempfile.mkdtemp(prefix="pzrev_sync_compare_"))
    try:
        generation = _download_bundle(base_url, token, temp_zip)
        with zipfile.ZipFile(temp_zip, "r") as z:
            for info in z.infolist():
                if not _safe_member(info.filename):
                    raise NasSyncError("NAS balík obsahuje neplatnou cestu.")
            z.extractall(stage)
        remote_db = stage / "pz_revize.db"
        manifest_path = stage / "manifest.json"
        if not remote_db.exists() or not manifest_path.exists():
            raise NasSyncError("NAS balík je neúplný.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        db._validate_database_file(remote_db)
        result = compare_database_states(db.path, remote_db)
        result["generation"] = int(manifest.get("generation") or generation or 0)
        result["created_at"] = manifest.get("created_at")
        return result
    finally:
        try:
            temp_zip.unlink()
        except OSError:
            pass
        shutil.rmtree(stage, ignore_errors=True)


def safe_sync_once(db, base_url: str, token: str, client_version: str, client_name: str = "PZ-REVIZE PC", allow_pull: bool = True, can_pull=None) -> dict:
    """Perform one loss-resistant synchronization pass.

    Rules:
    * identical generation + local edit -> push;
    * NAS newer + local is unchanged/subset -> pull;
    * local is a strict superset (for example two new offline revisions) -> push
      directly against the current NAS generation, WITHOUT pulling first;
    * divergent edits -> never overwrite either side automatically.
    """
    status = get_status(base_url, token, timeout=8)
    server_generation = int(status.get("generation") or 0)
    cfg = get_sync_settings(db)
    local_generation = int(cfg.get("generation") or 0)
    local_signature = database_logical_signature(db.path)
    last_signature = str(cfg.get("last_signature") or "")
    local_revisions = int((db.fetchone("SELECT COUNT(*) AS n FROM revisions") or {"n": 0})["n"])

    if server_generation == 0:
        if local_revisions == 0:
            set_setting(db, "nas_generation", "0")
            set_setting(db, "nas_last_signature", local_signature)
            set_setting(db, "nas_last_sync", datetime.now().isoformat(timespec="seconds"))
            set_setting(db, "nas_last_sync_result", "equal")
            set_setting(db, "nas_last_sync_error", "")
            return {"ok": True, "action": "equal", "generation": 0, "message": "NAS i lokální databáze jsou prázdné."}
        result = push_to_nas(db, base_url, token, client_version, client_name, expected_generation=0)
        return {"ok": True, "action": "push", "generation": result.get("generation"), "message": "Lokální databáze byla odeslána na prázdný NAS.", "detail": result}

    # Stejná generace znamená, že NAS od posledního známého stavu tohoto PC
    # nebyl změněn.  Po upgradu ze starší verze ještě nemusíme mít uložený
    # logický podpis; v takovém případě je bezpečné lokální snapshot odeslat
    # přímo, protože expected_generation stále chrání proti souběžné změně NAS.
    if server_generation == local_generation:
        if last_signature and local_signature == last_signature:
            set_setting(db, "nas_last_sync", datetime.now().isoformat(timespec="seconds"))
            set_setting(db, "nas_last_sync_result", "equal")
            set_setting(db, "nas_last_sync_error", "")
            return {"ok": True, "action": "equal", "generation": server_generation, "message": "Beze změn."}
        result = push_to_nas(db, base_url, token, client_version, client_name, expected_generation=server_generation)
        return {"ok": True, "action": "push", "generation": result.get("generation"), "message": "Lokální změny byly odeslány na NAS.", "detail": result}

    relation = compare_with_nas(db, base_url, token)
    rel = relation["relation"]
    remote_generation = int(relation.get("generation") or server_generation)

    if rel == "equal":
        set_setting(db, "nas_generation", str(remote_generation))
        set_setting(db, "nas_last_signature", local_signature)
        set_setting(db, "nas_last_sync", datetime.now().isoformat(timespec="seconds"))
        set_setting(db, "nas_last_sync_result", "equal")
        set_setting(db, "nas_last_sync_error", "")
        return {"ok": True, "action": "equal", "generation": remote_generation, "message": "Obsah je shodný; srovnána generace.", "comparison": relation}

    if rel == "local_superset":
        result = push_to_nas(db, base_url, token, client_version, client_name, expected_generation=remote_generation)
        return {
            "ok": True, "action": "push", "generation": result.get("generation"),
            "message": "Lokální databáze obsahovala data navíc; byla bezpečně odeslána bez předchozího stažení NAS.",
            "comparison": relation, "detail": result,
        }

    if rel == "remote_superset":
        if not allow_pull or (can_pull is not None and not can_pull()):
            return {"ok": True, "action": "deferred_pull", "generation": remote_generation, "message": "NAS obsahuje bezpečně novější stav; stažení je odloženo, protože je otevřená revize.", "comparison": relation}
        result = pull_from_nas(db, base_url, token, can_pull=can_pull)
        return {"ok": True, "action": "pull", "generation": result.get("generation"), "message": "Novější úplný stav byl bezpečně stažen z NAS.", "comparison": relation, "detail": result}

    msg = "Synchronizace byla zastavena: lokální PC i NAS obsahují rozdílné změny. Lokální databáze nebyla přepsána."
    set_setting(db, "nas_last_sync_result", "conflict")
    set_setting(db, "nas_last_sync_error", msg)
    return {"ok": False, "action": "conflict", "generation": remote_generation, "message": msg, "comparison": relation}
