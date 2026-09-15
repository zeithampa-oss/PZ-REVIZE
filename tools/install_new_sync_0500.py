from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAS = ROOT / "source" / "windows" / "pzrevize" / "nas_sync.py"
APP = ROOT / "source" / "windows" / "app.py"

s = NAS.read_text(encoding="utf-8")

# Remove the 0.4.44 wrapper if the build workflow applied it before this script.
if "def _pz0444_merge_remote_revisions" in s and "def _pz0444_legacy_safe_sync_once" in s:
    start = s.index("\ndef _pz0444_merge_remote_revisions")
    legacy = s.index("\ndef _pz0444_legacy_safe_sync_once", start)
    # Keep the legacy implementation available only until the next marker, then
    # replace the complete 0.4.44 wrapper with the clean 0.5.0 implementation.
    # The helper block and wrapper are contiguous in the generated 0.4.44 file.
    # Find the original safe_sync body boundary by locating the next function.
    next_def = s.find("\ndef ", legacy + 10)
    if next_def < 0:
        next_def = len(s)
    s = s[:start] + s[legacy:next_def] + s[next_def:]

# Rename the currently active safe_sync_once exactly once.
if "def _pz0500_legacy_safe_sync_once" not in s:
    marker = "\ndef safe_sync_once("
    if marker not in s:
        raise SystemExit("safe_sync_once marker not found")
    s = s.replace(marker, "\n\ndef _pz0500_legacy_safe_sync_once(", 1)

helpers = r'''

# ---------------------------------------------------------------------------
# PZ-REVIZE 0.5.0 — clean multi-PC synchronization
# ---------------------------------------------------------------------------
# This implementation never treats the whole SQLite file as the unit of work.
# The unit of synchronization is a revision.  A remote revision which does not
# exist locally is copied into the local database; a local-only revision is kept
# and sent back to NAS.  The same revision changed on both sides is a conflict.

_PZ0500_CHILD_TABLES = (
    "circuits", "varistor_measurements", "lps_measurements", "machine_measurements",
    "external_influences", "revision_defects", "revision_instruments",
    "revision_attachments", "revision_documents", "revision_standards",
    "revision_networks", "revision_supplies", "revision_conclusion_blocks",
    "revision_protection_measures", "revision_photos", "revision_inspection_items",
)
_PZ0500_PATH_COLUMNS = {"stored_path", "photo_path", "logo_path", "stamp_path", "signature_path"}


def _pz0500_row_key(row, ignore=("id", "created_at", "updated_at", "usage_count")):
    return json.dumps({k: row[k] for k in row.keys() if k not in ignore}, ensure_ascii=False, sort_keys=True, default=str)


def _pz0500_table_columns(con, table):
    return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]


def _pz0500_merge_simple_table(src, dst, table):
    if not _table_exists(src, table) or not _table_exists(dst, table):
        return {}
    scols = _pz0500_table_columns(src, table)
    dcols = _pz0500_table_columns(dst, table)
    if "id" not in scols or "id" not in dcols:
        return {}
    src_rows = src.execute(f'SELECT * FROM "{table}"').fetchall()
    dst_rows = dst.execute(f'SELECT * FROM "{table}"').fetchall()
    by_key = {_pz0500_row_key(r): r["id"] for r in dst_rows}
    mapping = {}
    insert_cols = [c for c in scols if c != "id" and c in dcols]
    for row in src_rows:
        key = _pz0500_row_key(row)
        if key in by_key:
            mapping[row["id"]] = by_key[key]
            continue
        vals = [row[c] for c in insert_cols]
        marks = ",".join("?" for _ in insert_cols)
        cols = ",".join('"'+c+'"' for c in insert_cols)
        try:
            cur = dst.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({marks})', vals)
            mapping[row["id"]] = cur.lastrowid
            by_key[key] = cur.lastrowid
        except sqlite3.IntegrityError:
            # If a UNIQUE constraint has a different representation, use the
            # existing row where possible; otherwise leave the reference NULL.
            pass
    return mapping


def _pz0500_copy_revision(db_path, remote_path, remote_rev_no, attachment_stage=None):
    local = sqlite3.connect(db_path)
    remote = sqlite3.connect(remote_path)
    local.row_factory = sqlite3.Row
    remote.row_factory = sqlite3.Row
    local.execute("PRAGMA foreign_keys=ON")
    try:
        rr = remote.execute("SELECT * FROM revisions WHERE revision_no=?", (remote_rev_no,)).fetchone()
        if rr is None:
            return False
        if local.execute("SELECT 1 FROM revisions WHERE revision_no=?", (remote_rev_no,)).fetchone():
            return False

        # Merge referenced master data first and build ID maps.
        customer_map = _pz0500_merge_simple_table(remote, local, "customers")
        object_map = _pz0500_merge_simple_table(remote, local, "objects")
        job_map = _pz0500_merge_simple_table(remote, local, "jobs")
        instrument_map = _pz0500_merge_simple_table(remote, local, "instruments")

        rev_cols = [c for c in _pz0500_table_columns(remote, "revisions") if c != "id" and c in _pz0500_table_columns(local, "revisions")]
        vals = [rr[c] for c in rev_cols]
        for fk, mp in (("customer_id", customer_map), ("object_id", object_map), ("job_id", job_map)):
            if fk in rev_cols and vals[rev_cols.index(fk)] is not None:
                vals[rev_cols.index(fk)] = mp.get(vals[rev_cols.index(fk)])
        cols = ",".join('"'+c+'"' for c in rev_cols)
        marks = ",".join("?" for _ in rev_cols)
        cur = local.execute(f'INSERT INTO revisions ({cols}) VALUES ({marks})', vals)
        new_rid = cur.lastrowid
        old_rid = rr["id"]
        defect_map = {}

        for table in _PZ0500_CHILD_TABLES:
            if not _table_exists(remote, table) or not _table_exists(local, table):
                continue
            cols_remote = _pz0500_table_columns(remote, table)
            cols_local = _pz0500_table_columns(local, table)
            if "revision_id" not in cols_remote or "revision_id" not in cols_local:
                continue
            rows = remote.execute(f'SELECT * FROM "{table}" WHERE revision_id=?', (old_rid,)).fetchall()
            insert_cols = [c for c in cols_remote if c != "id" and c in cols_local]
            for row in rows:
                vals = [row[c] for c in insert_cols]
                if "revision_id" in insert_cols:
                    vals[insert_cols.index("revision_id")] = new_rid
                if table == "revision_instruments" and "instrument_id" in insert_cols:
                    vals[insert_cols.index("instrument_id")] = instrument_map.get(row["instrument_id"])
                    if vals[insert_cols.index("instrument_id")] is None:
                        continue
                if table in {"revision_defects", "revision_standards", "revision_protection_measures", "revision_inspection_items"}:
                    for fk in ("catalog_id", "standard_id"):
                        if fk in insert_cols:
                            vals[insert_cols.index(fk)] = None
                if table == "revision_photos" and "defect_id" in insert_cols:
                    vals[insert_cols.index("defect_id")] = defect_map.get(row["defect_id"])
                for col in _PZ0500_PATH_COLUMNS.intersection(insert_cols):
                    value = vals[insert_cols.index(col)]
                    if isinstance(value, str) and value.replace("\\", "/").startswith("attachments/") and attachment_stage:
                        local_file = Path(app_data_dir()) / "attachments" / Path(value).name
                        vals[insert_cols.index(col)] = str(local_file)
                cols = ",".join('"'+c+'"' for c in insert_cols)
                marks = ",".join("?" for _ in insert_cols)
                try:
                    nc = local.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({marks})', vals)
                    if table == "revision_defects":
                        defect_map[row["id"]] = nc.lastrowid
                except sqlite3.IntegrityError:
                    # Idempotence / legacy unique indexes must never abort the
                    # complete revision merge.
                    continue
        local.commit()
        return True
    finally:
        remote.close()
        local.close()


def _pz0500_merge_remote_bundle(db, bundle_path):
    stage = Path(tempfile.mkdtemp(prefix="pzrev_v0500_merge_"))
    try:
        with zipfile.ZipFile(bundle_path) as z:
            for info in z.infolist():
                if not _safe_member(info.filename):
                    raise NasSyncError("NAS balík obsahuje neplatnou cestu.")
            z.extractall(stage)
        remote_db = stage / "pz_revize.db"
        manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
        db._validate_database_file(remote_db)
        cmp = compare_database_states(db.path, remote_db)
        if cmp.get("changed_revisions"):
            raise NasConflictError("Stejná revize byla změněna na obou PC. Synchronizace byla zastavena bez přepsání dat.")

        # Copy attachment payloads before DB rows reference them.
        incoming = stage / "attachments"
        local_att = app_data_dir() / "attachments"
        local_att.mkdir(parents=True, exist_ok=True)
        if incoming.exists():
            for p in incoming.rglob("*"):
                if p.is_file():
                    dest = local_att / p.name
                    if not dest.exists():
                        shutil.copy2(p, dest)

        merged = 0
        for rev_no in cmp.get("remote_only_revisions") or []:
            if _pz0500_copy_revision(db.path, remote_db, rev_no, incoming):
                merged += 1
        return {"merged": merged, "generation": int(manifest.get("generation") or 0), "comparison": cmp}
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _pz0500_sync(db, base_url, token, client_version, client_name="PZ-REVIZE PC", allow_pull=True, can_pull=None):
    """Revision-based sync with optimistic generation and retry.

    Every pass first reads the NAS snapshot. Independent revisions are merged
    locally, then the complete union is pushed. A simultaneous NAS change causes
    a retry from the newest NAS snapshot instead of replacing local data.
    """
    for attempt in range(3):
        status = get_status(base_url, token, timeout=8)
        server_generation = int(status.get("generation") or 0)

        if not allow_pull or (can_pull is not None and not can_pull()):
            # We can still push when our local generation is current.
            cfg = get_sync_settings(db)
            if int(cfg.get("generation") or 0) != server_generation:
                return {"ok": True, "action": "deferred", "generation": server_generation,
                        "message": "Synchronizace odložena, protože je otevřená revize."}

        # Empty NAS: first client publishes its local database.
        if server_generation == 0:
            count = int((db.fetchone("SELECT COUNT(*) AS n FROM revisions") or {"n": 0})["n"])
            if count == 0:
                set_setting(db, "nas_generation", "0")
                set_setting(db, "nas_last_signature", database_logical_signature(db.path))
                return {"ok": True, "action": "equal", "generation": 0, "message": "Beze změn."}
            try:
                pushed = push_to_nas(db, base_url, token, client_version, client_name, expected_generation=0)
                return {"ok": True, "action": "push", "generation": pushed.get("generation"), "message": "První data byla odeslána na NAS."}
            except NasConflictError:
                continue

        bundle = _new_temp_path("PZ_REVIZE_V0500_", ".zip")
        try:
            generation = _download_bundle(base_url, token, bundle)
            merged = _pz0500_merge_remote_bundle(db, bundle)
            remote_generation = int(merged.get("generation") or generation or server_generation)

            # If the local DB had no changes except the merge, this push still
            # publishes the union and advances the generation. If it had local
            # revisions, they remain in the DB and are published too.
            pushed = push_to_nas(db, base_url, token, client_version, client_name,
                                 expected_generation=remote_generation)
            return {
                "ok": True,
                "action": "merge_push",
                "generation": pushed.get("generation"),
                "merged_revisions": merged.get("merged", 0),
                "message": f"Synchronizace dokončena. Sloučeno nových revizí: {merged.get('merged', 0)}.",
            }
        except NasConflictError:
            if attempt == 2:
                raise
            continue
        finally:
            try:
                bundle.unlink()
            except OSError:
                pass
    raise NasSyncError("Synchronizaci se nepodařilo dokončit po třech pokusech.")

'''

# Insert the clean implementation immediately before the legacy function.
legacy_marker = "\n\ndef _pz0500_legacy_safe_sync_once("
if legacy_marker not in s:
    raise SystemExit("legacy safe_sync marker missing")
s = s.replace(legacy_marker, helpers + "\n\ndef safe_sync_once(db, base_url, token, client_version, client_name=\"PZ-REVIZE PC\", allow_pull=True, can_pull=None):\n    return _pz0500_sync(db, base_url, token, client_version, client_name, allow_pull, can_pull)\n" + legacy_marker, 1)

NAS.write_text(s, encoding="utf-8")
app = APP.read_text(encoding="utf-8")
app = app.replace('VERSION = "0.4.35"', 'VERSION = "0.5.0"').replace('VERSION = "0.4.43"', 'VERSION = "0.5.0"').replace('VERSION = "0.4.44"', 'VERSION = "0.5.0"')
APP.write_text(app, encoding="utf-8")
print("Installed clean PZ-REVIZE 0.5.0 synchronization")
