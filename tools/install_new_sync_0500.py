from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAS = ROOT / "source" / "windows" / "pzrevize" / "nas_sync.py"
APP = ROOT / "source" / "windows" / "app.py"

s = NAS.read_text(encoding="utf-8")

# The 0.5.0 implementation is already installed by the PR workflow.  Patch its
# logical row key so SQLite-generated IDs cannot make an unchanged revision look
# different on two PCs.  IDs are local implementation details; revision content
# and snapshot fields are the synchronisation identity.
old = '''def _pz0500_row_key(row, ignore=("id", "created_at", "updated_at", "usage_count")):\n    return json.dumps({k: row[k] for k in row.keys() if k not in ignore}, ensure_ascii=False, sort_keys=True, default=str)\n'''
new = '''def _pz0500_row_key(row, ignore=("id", "created_at", "updated_at", "usage_count")):\n    # SQLite INTEGER PRIMARY KEY values are different after a revision is copied\n    # between PCs.  They must never participate in the logical revision identity.\n    # The revision_id is also local, and catalog/instrument/defect FKs are local\n    # references whose human-readable snapshot fields are part of the record.\n    keys = set(ignore)\n    for key in row.keys():\n        if key.endswith("_id"):\n            keys.add(key)\n    return json.dumps({k: row[k] for k in row.keys() if k not in keys}, ensure_ascii=False, sort_keys=True, default=str)\n'''
if old not in s:
    raise SystemExit("0.5.0 row-key marker not found")
s = s.replace(old, new, 1)

# Add a direct regression test proving that copied SQLite IDs do not create a
# false "same revision changed" conflict.
TEST = ROOT / "source" / "windows" / "tests" / "test_nas_sync_v0500.py"
t = TEST.read_text(encoding="utf-8")
needle = '''    def test_compare_detects_independent_revisions(self):\n'''
if "test_identical_revision_with_different_sqlite_ids_is_not_conflict" not in t:
    test = '''    def test_identical_revision_with_different_sqlite_ids_is_not_conflict(self):\n        root = Path(tempfile.mkdtemp(prefix="pz_sync_test_"))\n        try:\n            a = self._db(root, "a.db")\n            b = self._db(root, "b.db")\n            self._revision(a, "A", "Same content")\n            self._revision(b, "A", "Same content")\n            # Different local AUTOINCREMENT IDs must not turn equal content into\n            # a false changed-revision conflict.\n            self.assertNotIn("A", compare_database_states(a.path, b.path)["changed_revisions"])\n        finally:\n            import shutil\n            shutil.rmtree(root, ignore_errors=True)\n\n'''
    if needle not in t:
        raise SystemExit("test insertion marker not found")
    t = t.replace(needle, test + needle, 1)
TEST.write_text(t, encoding="utf-8")

app = APP.read_text(encoding="utf-8")
app = app.replace('VERSION = "0.5.0"', 'VERSION = "0.5.1"')
app = app.replace('VERSION = "0.4.44"', 'VERSION = "0.5.1"')
app = app.replace('VERSION = "0.4.35"', 'VERSION = "0.5.1"')
APP.write_text(app, encoding="utf-8")
print("Installed PZ-REVIZE 0.5.1 synchronization identity fix")
