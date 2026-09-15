from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "source" / "windows" / "app.py"
NAS = ROOT / "source" / "windows" / "pzrevize" / "nas_sync.py"

nas = NAS.read_text(encoding="utf-8")

needle = '''def create_complete_local_backup(db, prefix: str = "before_nas_pull") -> Path:\n'''
helper = '''def _is_pristine_user_database(db) -> bool:\n    """Return True when this PC has no user/job data worth preserving."""\n    for table in ("revisions", "customers", "objects", "jobs"):\n        try:\n            row = db.fetchone(f"SELECT COUNT(*) AS n FROM {table}")\n        except Exception:\n            return False\n        if int((row or {"n": 0})["n"] or 0) != 0:\n            return False\n    return True\n\n\n'''
if helper not in nas:
    if needle not in nas:
        raise SystemExit("NAS helper insertion point not found")
    nas = nas.replace(needle, helper + needle, 1)

old = '''            relation = compare_database_states(db.path, db_in)\n            if relation["relation"] not in ("remote_superset", "equal"):\n                raise NasConflictError(\n                    "Stažení z NAS zablokováno: v tomto PC jsou změny, které NAS neobsahuje. "\n                    "Lokální revize zůstaly zachovány; před stažením je nutné konflikt vyřešit."\n                )\n'''
new = '''            relation = compare_database_states(db.path, db_in)\n            initial_pull = _is_pristine_user_database(db)\n            if relation["relation"] not in ("remote_superset", "equal") and not initial_pull:\n                raise NasConflictError(\n                    "Stažení z NAS zablokováno: v tomto PC jsou změny, které NAS neobsahuje. "\n                    "Lokální revize zůstaly zachovány; před stažením je nutné konflikt vyřešit."\n                )\n'''
if old in nas:
    nas = nas.replace(old, new, 1)

old2 = '''    relation = compare_with_nas(db, base_url, token)\n    rel = relation["relation"]\n    remote_generation = int(relation.get("generation") or server_generation)\n'''
new2 = '''    # If this PC has not changed since its last successful synchronization,\n    # a newer NAS generation is a safe sequential update: pull the current\n    # shared snapshot instead of classifying unrelated local metadata as a conflict.\n    if server_generation > local_generation and last_signature and local_signature == last_signature:\n        if not allow_pull or (can_pull is not None and not can_pull()):\n            return {\n                "ok": True, "action": "deferred_pull", "generation": server_generation,\n                "message": "NAS obsahuje nový stav; stažení je odloženo, protože je otevřená revize.",\n            }\n        result = pull_from_nas(db, base_url, token, can_pull=can_pull)\n        return {\n            "ok": True, "action": "pull", "generation": result.get("generation"),\n            "message": "Lokální PC nebylo změněno; nový stav byl bezpečně stažen z NAS.",\n            "detail": result,\n        }\n\n    # First sync on a new PC: NAS is authoritative for the initial working data.\n    if _is_pristine_user_database(db):\n        result = pull_from_nas(db, base_url, token, can_pull=can_pull)\n        return {\n            "ok": True, "action": "pull", "generation": result.get("generation"),\n            "message": "První databáze byla bezpečně převzata z NAS.", "detail": result,\n        }\n\n    relation = compare_with_nas(db, base_url, token)\n    rel = relation["relation"]\n    remote_generation = int(relation.get("generation") or server_generation)\n'''
if old2 not in nas:
    raise SystemExit("NAS safe-sync comparison block not found")
nas = nas.replace(old2, new2, 1)

NAS.write_text(nas, encoding="utf-8")

app = APP.read_text(encoding="utf-8")
if 'VERSION = "0.4.42"' not in app:
    raise SystemExit("Expected Windows 0.4.42 version marker not found")
app = app.replace('VERSION = "0.4.42"', 'VERSION = "0.4.43"', 1)
APP.write_text(app, encoding="utf-8")

print("Applied Windows 0.4.43 NAS sequential-sync fix")
