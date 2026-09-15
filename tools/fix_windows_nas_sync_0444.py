from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
NAS = ROOT / "source" / "windows" / "pzrevize" / "nas_sync.py"
APP = ROOT / "source" / "windows" / "app.py"

s = NAS.read_text(encoding="utf-8")

if "def _pz0444_merge_remote_revisions" not in s:
    # Preserve the tested implementation for ordinary cases.  0.4.43 still
    # treated two independent new revisions as a conflict; 0.4.44 merges the
    # remote-only revision trees into the local DB, then pushes the union.
    marker = "\n\ndef safe_sync_once"
    if marker not in s:
        raise SystemExit("safe_sync_once marker not found")
    s = s.replace(marker, "\n\n_pz0444_legacy_safe_sync_once = safe_sync_once\n\n" + r'''def _pz0444_merge_remote_revisions(local_db, remote_db, remote_revision_nos):
    """Merge only genuinely remote-only revisions without replacing local data."""
    con_l = sqlite3.connect(local_db)
    con_r = sqlite3.connect(remote_db)
    con_l.row_factory = sqlite3.Row
    con_r.row_factory = sqlite3.Row
    try:
        local_cols = {r[1] for r in con_l.execute("PRAGMA table_info(revisions)")}
        rev_cols = [c for c in local_cols if c != "id"]
        child_tables = [
            "circuits", "varistor_measurements", "lps_measurements", "machine_measurements",
            "external_influences", "revision_defects", "revision_attachments", "revision_documents",
            "revision_standards", "revision_networks", "revision_supplies", "revision_conclusion_blocks",
            "revision_protection_measures", "revision_photos", "revision_inspection_items",
        ]
        for rev_no in remote_revision_nos:
            rr = con_r.execute("SELECT * FROM revisions WHERE revision_no=?", (rev_no,)).fetchone()
            if rr is None:
                continue
            if con_l.execute("SELECT 1 FROM revisions WHERE revision_no=?", (rev_no,)).fetchone():
                continue
            vals = [rr[c] for c in rev_cols]
            q = ",".join('"'+c+'"' for c in rev_cols)
            marks = ",".join("?" for _ in rev_cols)
            cur = con_l.execute(f"INSERT INTO revisions ({q}) VALUES ({marks})", vals)
            new_rev_id = cur.lastrowid
            old_rev_id = rr["id"]
            defect_map = {}
            for table in child_tables:
                try:
                    cols = [r[1] for r in con_r.execute(f'PRAGMA table_info("{table}")')]
                    if "revision_id" not in cols:
                        continue
                    rows = con_r.execute(f'SELECT * FROM "{table}" WHERE revision_id=?', (old_rev_id,)).fetchall()
                except sqlite3.Error:
                    continue
                for row in rows:
                    out_cols = [c for c in cols if c != "id"]
                    vals = [row[c] for c in out_cols]
                    if "revision_id" in out_cols:
                        vals[out_cols.index("revision_id")] = new_rev_id
                    if table == "revision_defects":
                        if "catalog_id" in out_cols:
                            vals[out_cols.index("catalog_id")] = None
                    if table == "revision_standards" and "standard_id" in out_cols:
                        vals[out_cols.index("standard_id")] = None
                    if table == "revision_protection_measures" and "catalog_id" in out_cols:
                        vals[out_cols.index("catalog_id")] = None
                    if table == "revision_inspection_items" and "catalog_id" in out_cols:
                        vals[out_cols.index("catalog_id")] = None
                    if table == "revision_photos" and "defect_id" in out_cols:
                        old_def = row["defect_id"]
                        vals[out_cols.index("defect_id")] = defect_map.get(old_def)
                    q2 = ",".join('"'+c+'"' for c in out_cols)
                    m2 = ",".join("?" for _ in out_cols)
                    try:
                        nc = con_l.execute(f'INSERT INTO "{table}" ({q2}) VALUES ({m2})', vals)
                        if table == "revision_defects":
                            defect_map[row["id"]] = nc.lastrowid
                    except sqlite3.IntegrityError:
                        # A duplicate child row is harmless; never replace the local row.
                        pass
        con_l.commit()
    finally:
        con_r.close(); con_l.close()


def _pz0444_merge_bundle_into_local(db, bundle_path):
    stage = Path(tempfile.mkdtemp(prefix="pzrev_merge_"))
    try:
        with zipfile.ZipFile(bundle_path) as z:
            z.extractall(stage)
        remote_db = stage / "pz_revize.db"
        if not remote_db.exists():
            raise NasSyncError("NAS balíček neobsahuje databázi.")
        cmp = compare_database_states(db.path, remote_db)
        remote_only = list(cmp.get("remote_only_revisions") or [])
        local_only = list(cmp.get("local_only_revisions") or [])
        changed = list(cmp.get("changed_revisions") or [])
        if changed:
            raise NasConflictError("Stejná revize byla změněna na obou PC; změny nebyly sloučeny.")
        if not remote_only:
            return {"merged": 0, "local_only": local_only}
        _pz0444_merge_remote_revisions(db.path, remote_db, remote_only)
        return {"merged": len(remote_only), "local_only": local_only}
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def safe_sync_once(db, base_url, token, client_version, *args, **kwargs):
    # First let the established 0.4.43 logic handle pristine PCs, unchanged
    # clients, local-only changes and real same-record conflicts.
    try:
        server = get_status(base_url, token)
        server_generation = int(server.get("generation") or 0)
        local_generation = int(_setting(db, "nas_generation", "0") or 0)
        comparison = compare_with_nas(db, base_url, token)
        if comparison.get("relation") == "conflict" and not comparison.get("changed_revisions") and comparison.get("local_only_revisions") and comparison.get("remote_only_revisions"):
            allow_pull = kwargs.get("allow_pull", True)
            can_pull = kwargs.get("can_pull")
            if not allow_pull or (can_pull is not None and not can_pull()):
                return {"ok": True, "action": "deferred_merge", "generation": server_generation,
                        "message": "Sloučení změn je odloženo, protože je otevřená revize."}
            bundle = _new_temp_path("PZ_REVIZE_MERGE_", ".zip")
            try:
                _download_bundle(base_url, token, bundle)
                merged = _pz0444_merge_bundle_into_local(db, bundle)
                pushed = push_to_nas(db, base_url, token, client_version,
                                     expected_generation=server_generation)
                return {"ok": True, "action": "merge_push", "generation": pushed.get("generation"),
                        "merged_revisions": merged["merged"], "message": "Nezávislé revize byly sloučeny a odeslány na NAS."}
            finally:
                try: bundle.unlink()
                except OSError: pass
    except NasConflictError:
        raise
    except Exception:
        # Fall back to the proven safety implementation; it must never silently overwrite.
        pass
    return _pz0444_legacy_safe_sync_once(db, base_url, token, client_version, *args, **kwargs)
''', 1)

NAS.write_text(s, encoding="utf-8")
app = APP.read_text(encoding="utf-8")
app = app.replace('VERSION = "0.4.35"', 'VERSION = "0.4.44"').replace('VERSION = "0.4.43"', 'VERSION = "0.4.44"')
APP.write_text(app, encoding="utf-8")

# Update the old regression test so it verifies the required two-PC union.
test = ROOT / "source" / "windows" / "tests" / "test_nas_sync_safety.py"
if test.exists():
    t = test.read_text(encoding="utf-8")
    old = 'self.assertEqual(result[\'action\'], \'conflict\')\n        push.assert_not_called(); pull.assert_not_called()\n        self.assertIsNotNone(self.db.fetchone("SELECT id FROM revisions WHERE revision_no=\'R-PC1\'"))'
    new = 'self.assertEqual(result[\'action\'], \'merge_push\')\n        self.assertEqual(result[\'merged_revisions\'], 1)\n        self.assertIsNotNone(self.db.fetchone("SELECT id FROM revisions WHERE revision_no=\'R-PC1\'"))\n        self.assertIsNotNone(self.db.fetchone("SELECT id FROM revisions WHERE revision_no=\'R-PC2\'"))'
    if old in t:
        t = t.replace(old, new, 1)
        test.write_text(t, encoding="utf-8")
print("Applied Windows 0.4.44 multi-PC merge synchronization")
