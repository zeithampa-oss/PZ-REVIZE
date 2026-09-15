from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "source" / "windows" / "app.py"
NAS = ROOT / "source" / "windows" / "pzrevize" / "nas_sync.py"

nas = NAS.read_text(encoding="utf-8")

needle = '''def create_complete_local_backup(db, prefix: str = "before_nas_pull") -> Path:\n'''
helper = '''def _is_pristine_user_database(db) -> bool:\n    """Return True when this PC has no user/job data worth preserving.\n\n    A freshly installed second PC can contain local catalog/profile rows that\n    are intentionally not part of the shared job state. Those rows must not\n    prevent the PC from taking its first complete snapshot from NAS.\n    """\n    for table in ("revisions", "customers", "objects", "jobs"):\n        try:\n            row = db.fetchone(f"SELECT COUNT(*) AS n FROM {table}")\n        except Exception:\n            return False\n        if int((row or {"n": 0})["n"] or 0) != 0:\n            return False\n    return True\n\n\n'''
if helper not in nas:
    if needle not in nas:
        raise SystemExit("NAS helper insertion point not found")
    nas = nas.replace(needle, helper + needle, 1)

old = '''            relation = compare_database_states(db.path, db_in)\n            if relation["relation"] not in ("remote_superset", "equal"):\n                raise NasConflictError(\n                    "Stažení z NAS zablokováno: v tomto PC jsou změny, které NAS neobsahuje. "\n                    "Lokální revize zůstaly zachovány; před stažením je nutné konflikt vyřešit."\n                )\n'''
new = '''            relation = compare_database_states(db.path, db_in)\n            # Na zcela novém PC je bezpečné přijmout první kompletní snapshot z NAS.\n            # Lokální katalogy/profil mohou být předinstalované a nejsou důvodem\n            # blokovat první převzetí pracovních dat.\n            initial_pull = _is_pristine_user_database(db)\n            if relation["relation"] not in ("remote_superset", "equal") and not initial_pull:\n                raise NasConflictError(\n                    "Stažení z NAS zablokováno: v tomto PC jsou změny, které NAS neobsahuje. "\n                    "Lokální revize zůstaly zachovány; před stažením je nutné konflikt vyřešit."\n                )\n'''
if old not in nas:
    raise SystemExit("NAS pull guard not found")
nas = nas.replace(old, new, 1)

old2 = '''    relation = compare_with_nas(db, base_url, token)\n    rel = relation["relation"]\n    remote_generation = int(relation.get("generation") or server_generation)\n'''
new2 = '''    # První synchronizace nového PC: pokud na něm nejsou žádná uživatelská\n    # data, NAS je autoritativní zdroj a kompletní snapshot lze bezpečně stáhnout.\n    # Tím se neaktivuje ochranný blok kvůli lokálním katalogům/profilu.\n    if _is_pristine_user_database(db):\n        result = pull_from_nas(db, base_url, token, can_pull=can_pull)\n        return {\n            "ok": True, "action": "pull", "generation": result.get("generation"),\n            "message": "První databáze byla bezpečně převzata z NAS.", "detail": result,\n        }\n\n    relation = compare_with_nas(db, base_url, token)\n    rel = relation["relation"]\n    remote_generation = int(relation.get("generation") or server_generation)\n'''
if old2 not in nas:
    raise SystemExit("NAS safe-sync comparison block not found")
nas = nas.replace(old2, new2, 1)

NAS.write_text(nas, encoding="utf-8")

app = APP.read_text(encoding="utf-8")
old_version = 'VERSION = "0.4.35"'
if old_version not in app:
    raise SystemExit("Windows version marker not found")
app = app.replace(old_version, 'VERSION = "0.4.42"', 1)
APP.write_text(app, encoding="utf-8")

print("Applied Windows 0.4.42 NAS initial-pull fix")
