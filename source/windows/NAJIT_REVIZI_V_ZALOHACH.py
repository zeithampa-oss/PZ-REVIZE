"""Read-only inventory of revision headers in this PC's PZ-REVIZE backups.

Does not import, restore or alter any source database or archive.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path


def revisions(path: Path):
    uri = path.resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as connection:
        columns = {row[1] for row in connection.execute('PRAGMA table_info(revisions)')}
        if not {'revision_no', 'subject'} <= columns:
            return []
        return connection.execute(
            'SELECT revision_no, subject, COALESCE(updated_at, created_at, \'\') '
            'FROM revisions ORDER BY id DESC'
        ).fetchall()


def scan_zip(path: Path):
    with zipfile.ZipFile(path) as archive:
        db_files = [name for name in archive.namelist() if name.endswith('/pz_revize.db') or name == 'pz_revize.db']
        if not db_files:
            return []
        with tempfile.NamedTemporaryFile(prefix='pzrev_readonly_', suffix='.db', delete=False) as tmp:
            tmp.write(archive.read(db_files[0]))
            temp_path = Path(tmp.name)
    try:
        return revisions(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def main():
    base = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or Path.home()) / 'PZ-REVIZE'
    if not base.exists():
        print(f'Složka programu nebyla nalezena: {base}')
        return 1
    sources = ([base / 'pz_revize.db'] if (base / 'pz_revize.db').exists() else [])
    sources += sorted((base / 'backups').glob('*.db'), reverse=True)
    sources += sorted((base / 'backups').glob('*.zip'), reverse=True)
    print(f'Čtu pouze zálohy z: {base}\n')
    for path in sources:
        try:
            rows = scan_zip(path) if path.suffix.lower() == '.zip' else revisions(path)
            print(f'\n{path}  ({len(rows)} revizí)')
            for number, subject, updated in rows:
                print(f'  {number or "BEZ ČÍSLA"} | {subject or "bez předmětu"} | {updated or "bez data"}')
        except (sqlite3.Error, OSError, zipfile.BadZipFile, RuntimeError) as exc:
            print(f'\n{path}  [NELZE PŘEČÍST: {exc}]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
