from pathlib import Path


def replace_once(path, old, new, label):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    if old not in s:
        raise SystemExit(f"Nenalezen vzor {label} v {path}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")

# Windows version + lease client imports
replace_once("source/windows/app.py", 'VERSION = "0.4.37"', 'VERSION = "0.4.39"', "Windows verze")
replace_once(
    "source/windows/app.py",
    "    create_complete_local_backup\n)",
    "    create_complete_local_backup, revision_lease_acquire, revision_lease_heartbeat, revision_lease_release\n)",
    "lease importy",
)

# Manual complete restore must really be a forced restore after explicit confirmation.
replace_once(
    "source/windows/app.py",
    '            "Aktuální lokální databáze a přílohy budou předem zazálohovány. "\n            "Pokud je v tomto PC revize nebo jiná změna, která na NAS není, stažení se zastaví a lokální data zůstanou zachována.\\n\\n"\n            "Jinak budou DB, fotografie, přílohy, razítko a podpis nahrazeny stavem z NAS.\\n\\n"',
    '            "Aktuální lokální databáze a přílohy budou předem KOMPLETNĚ zazálohovány.\\n\\n"\n            "PO POTVRZENÍ bude pracovní databáze tohoto PC nahrazena stavem z NAS, i když toto PC obsahuje vlastní neodeslané změny. "\n            "Tyto změny zůstanou pouze v automaticky vytvořené záloze.\\n\\n"\n            "DB, fotografie, přílohy, razítko a podpis budou nahrazeny stavem z NAS.\\n\\n"',
    "text ruční obnovy",
)
replace_once(
    "source/windows/app.py",
    "            result = pull_from_nas(self.db, url, self.token_var.get().strip())",
    "            result = pull_from_nas(self.db, url, self.token_var.get().strip(), force_replace=True)",
    "force pull UI",
)

# Revision editor: lease key + minute autosave + automatic return on close.
replace_once(
    "source/windows/app.py",
    "    def __init__(self, app, revision_type: str, revision_id: int | None = None, initial_job_id: int | None = None):\n        self.app=app; self.db=app.db; self.revision_type=revision_type; self.revision_id=revision_id; self.initial_job_id=initial_job_id",
    "    def __init__(self, app, revision_type: str, revision_id: int | None = None, initial_job_id: int | None = None, lease_key: str | None = None):\n        self.app=app; self.db=app.db; self.revision_type=revision_type; self.revision_id=revision_id; self.initial_job_id=initial_job_id; self._lease_key=lease_key",
    "RevisionEditor init",
)
replace_once(
    "source/windows/app.py",
    "        def mark_closed(event):\n            if event.widget is self:\n                app._active_revision_editors = max(0, app._active_revision_editors - 1)\n",
    "        def mark_closed(event):\n            if event.widget is self:\n                app._active_revision_editors = max(0, app._active_revision_editors - 1)\n                if self._lease_key:\n                    app.return_revision_lease_async(self._lease_key)\n",
    "vrácení lease při zavření",
)
replace_once(
    "source/windows/app.py",
    "        if self.revision_type=='VNEJSI':\n            self.bind('<Control-d>',lambda e:(self.external_duplicate_room(),'break')[1])\n            self.bind('<Control-D>',lambda e:(self.external_duplicate_room(),'break')[1])\n\n    def _maximize_editor(self):",
    "        if self.revision_type=='VNEJSI':\n            self.bind('<Control-d>',lambda e:(self.external_duplicate_room(),'break')[1])\n            self.bind('<Control-D>',lambda e:(self.external_duplicate_room(),'break')[1])\n        if self._lease_key:\n            self.after(60000, self._lease_autosave_tick)\n\n    def _lease_autosave_tick(self):\n        if not self.winfo_exists() or not self._lease_key:\n            return\n        try:\n            if self._has_unsaved_changes():\n                self._persist(close_after=False, show_message=False, confirm_defects=False)\n            self.app.heartbeat_revision_lease_async(self._lease_key)\n        finally:\n            if self.winfo_exists():\n                self.after(60000, self._lease_autosave_tick)\n\n    def _maximize_editor(self):",
    "autosave tick",
)
replace_once(
    "source/windows/app.py",
    "        self._revision_editor_epoch = 0\n        self._active_revision_editors = 0\n        self.title(f\"{APP_TITLE} {VERSION}\")",
    "        self._revision_editor_epoch = 0\n        self._active_revision_editors = 0\n        self._revision_leases = {}\n        self.title(f\"{APP_TITLE} {VERSION}\")",
    "lease registry",
)
replace_once(
    "source/windows/app.py",
    "    def open_revision_editor(self,rtype,rid=None,initial_job_id=None):\n        RevisionEditor(self,rtype,rid,initial_job_id)\n",
    '''    def _nas_client_id(self):
        cfg=get_sync_settings(self.db); cid=str(cfg.get('client_id') or '').strip()
        if not cid:
            cid='pc-'+uuid.uuid4().hex
            nas_set_setting(self.db,'nas_client_id',cid)
        return cid

    def borrow_revision(self, rid):
        row=self.db.fetchone("SELECT id,revision_no FROM revisions WHERE id=?",(rid,))
        if not row:return rid,None
        revision_no=str(row['revision_no'] or '').strip(); key=revision_no or f"ID:{rid}"
        cfg=get_sync_settings(self.db)
        if not cfg.get('token'):
            return rid,None
        try:
            url,transport,_=nas_resolve_endpoint(cfg,timeout=5); cid=self._nas_client_id()
            revision_lease_acquire(url,cfg.get('token',''),key,cid,os.environ.get('COMPUTERNAME') or 'PZ-REVIZE PC')
            result=safe_sync_once(self.db,url,cfg.get('token',''),VERSION,allow_pull=True,can_pull=lambda: self._active_revision_editors==0)
            if not result.get('ok',True) or result.get('action')=='conflict':
                try:revision_lease_release(url,cfg.get('token',''),key,cid)
                except Exception:pass
                raise NasSyncError(result.get('message') or 'Konflikt synchronizace při vypůjčení revize.')
            fresh=self.db.fetchone("SELECT id FROM revisions WHERE revision_no=?",(revision_no,)) if revision_no else None
            self._revision_leases[key]={'url':url,'token':cfg.get('token',''),'client_id':cid,'transport':transport}
            self._set_nas_indicator('online',f'NAS: revize {key} vypůjčena · {transport}')
            return (int(fresh['id']) if fresh else rid),key
        except NasConflictError as exc:
            messagebox.showwarning('Revize je používána',f'Revizi {key} právě upravuje jiné zařízení.\\n\\n{exc}',parent=self)
            return None,None
        except Exception as exc:
            if messagebox.askyesno('NAS není dostupný',f'Nepodařilo se vypůjčit revizi {key} z NAS.\\n\\n{exc}\\n\\nOtevřít lokální kopii offline?',parent=self):
                self._set_nas_indicator('offline',f'NAS: revize {key} otevřena offline')
                return rid,None
            return None,None

    def heartbeat_revision_lease_async(self,key):
        lease=self._revision_leases.get(key)
        if not lease:return
        def worker():
            try:
                revision_lease_heartbeat(lease['url'],lease['token'],key,lease['client_id'])
                self.schedule_auto_sync('automatické uložení otevřené revize')
            except Exception:
                try:self.after(0,lambda:self._set_nas_indicator('offline',f'NAS: {key} čeká na synchronizaci'))
                except Exception:pass
        threading.Thread(target=worker,daemon=True).start()

    def return_revision_lease_async(self,key):
        lease=self._revision_leases.pop(key,None)
        if not lease:return
        def worker():
            try:
                safe_sync_once(self.db,lease['url'],lease['token'],VERSION,allow_pull=False)
                revision_lease_release(lease['url'],lease['token'],key,lease['client_id'])
                try:self.after(0,lambda:self._set_nas_indicator('online',f'NAS: revize {key} vrácena'))
                except Exception:pass
            except Exception as exc:
                try:self.after(0,lambda:self._set_nas_indicator('offline',f'NAS: {key} čeká na synchronizaci'))
                except Exception:pass
                try:nas_set_setting(self.db,'nas_last_sync_error',str(exc))
                except Exception:pass
        threading.Thread(target=worker,daemon=True).start()

    def open_revision_editor(self,rtype,rid=None,initial_job_id=None):
        lease_key=None
        if rid is not None:
            rid,lease_key=self.borrow_revision(rid)
            if rid is None:return
        RevisionEditor(self,rtype,rid,initial_job_id,lease_key=lease_key)
''',
    "borrow revision methods",
)

# Windows sync helpers: private client id, forced restore and lease API.
replace_once(
    "source/windows/pzrevize/nas_sync.py",
    '        "last_sync_error": _setting(db, "nas_last_sync_error", ""),\n    }',
    '        "last_sync_error": _setting(db, "nas_last_sync_error", ""),\n        "client_id": _setting(db, "nas_client_id", ""),\n    }',
    "client id setting",
)
replace_once(
    "source/windows/pzrevize/nas_sync.py",
    "def pull_from_nas(db, base_url: str, token: str, can_pull=None) -> dict:",
    "def pull_from_nas(db, base_url: str, token: str, can_pull=None, force_replace: bool = False) -> dict:",
    "force replace signature",
)
replace_once(
    "source/windows/pzrevize/nas_sync.py",
    '            if relation["relation"] not in ("remote_superset", "equal"):',
    '            if not force_replace and relation["relation"] not in ("remote_superset", "equal"):',
    "force replace guard",
)
replace_once(
    "source/windows/pzrevize/nas_sync.py",
    '            "counts": counts,\n        }',
    '            "counts": counts,\n            "forced_replace": bool(force_replace),\n            "previous_relation": relation.get("relation") if \'relation\' in locals() else None,\n        }',
    "force replace return",
)
replace_once(
    "source/windows/pzrevize/nas_sync.py",
    "def get_status(base_url: str, token: str, timeout: int = 30) -> dict:\n",
    '''def _json_post(base_url: str, path: str, token: str, payload: dict, timeout: int = 15) -> dict:
    url = base_url.rstrip("/") + path
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=raw, method="POST", headers={"X-API-Key": token, "Accept": "application/json", "Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try: detail = json.loads(body).get("detail", body)
        except Exception: detail = body or str(e)
        if e.code == 409: raise NasConflictError(str(detail)) from e
        raise NasSyncError(f"NAS odpověděl HTTP {e.code}: {detail}") from e
    except (NasConflictError, NasSyncError): raise
    except Exception as e: raise NasSyncError(f"Nelze se spojit s NAS: {e}") from e


def revision_lease_acquire(base_url: str, token: str, revision_key: str, client_id: str, client_name: str, ttl_seconds: int = 600) -> dict:
    return _json_post(base_url, "/api/revision-lock/acquire", token, {"revision_key": str(revision_key), "client_id": str(client_id), "client_name": str(client_name), "ttl_seconds": int(ttl_seconds)})


def revision_lease_heartbeat(base_url: str, token: str, revision_key: str, client_id: str, ttl_seconds: int = 600) -> dict:
    return _json_post(base_url, "/api/revision-lock/heartbeat", token, {"revision_key": str(revision_key), "client_id": str(client_id), "ttl_seconds": int(ttl_seconds)})


def revision_lease_release(base_url: str, token: str, revision_key: str, client_id: str) -> dict:
    return _json_post(base_url, "/api/revision-lock/release", token, {"revision_key": str(revision_key), "client_id": str(client_id)})


def get_status(base_url: str, token: str, timeout: int = 30) -> dict:
''',
    "lease client API",
)

replace_once("source/windows/tests/test_standard_catalog.py", "self.assertEqual(VERSION, '0.4.37')", "self.assertEqual(VERSION, '0.4.39')", "version test")

# NAS 1.0.4 lease server.
replace_once("source/nas/server.py", "from datetime import datetime", "from datetime import datetime, timedelta", "timedelta")
replace_once("source/nas/server.py", 'VERSION = "1.0.3"', 'VERSION = "1.0.4"', "NAS version")
replace_once(
    "source/nas/server.py",
    "    def db_ready(self):\n",
    '''    def _active_revision_leases(self):
        leases = self.state_data.setdefault("revision_leases", {})
        now_dt = datetime.now(); changed = False
        for key, item in list(leases.items()):
            try: expires = datetime.fromisoformat(str(item.get("expires_at") or ""))
            except Exception: expires = now_dt - timedelta(seconds=1)
            if expires <= now_dt: leases.pop(key, None); changed = True
        if changed: atomic_write_json(self.state_path, self.state_data)
        return leases

    def acquire_revision_lease(self, revision_key, client_id, client_name, ttl_seconds=600):
        revision_key = str(revision_key or "").strip(); client_id = str(client_id or "").strip()
        if not revision_key or not client_id: raise ValueError("Chybí revision_key nebo client_id.")
        ttl = max(120, min(int(ttl_seconds or 600), 1800))
        with self.lock:
            leases = self._active_revision_leases(); current = leases.get(revision_key)
            if current and current.get("client_id") != client_id: return {"ok": False, "conflict": True, "revision_key": revision_key, "owner": current}
            now_dt = datetime.now(); item = {"revision_key": revision_key, "client_id": client_id, "client_name": str(client_name or client_id), "acquired_at": (current or {}).get("acquired_at") or now_dt.isoformat(timespec="seconds"), "heartbeat_at": now_dt.isoformat(timespec="seconds"), "expires_at": (now_dt + timedelta(seconds=ttl)).isoformat(timespec="seconds")}
            leases[revision_key] = item; atomic_write_json(self.state_path, self.state_data)
            return {"ok": True, "lease": item, "generation": self.generation}

    def heartbeat_revision_lease(self, revision_key, client_id, ttl_seconds=600):
        revision_key = str(revision_key or "").strip(); client_id = str(client_id or "").strip(); ttl = max(120, min(int(ttl_seconds or 600), 1800))
        with self.lock:
            leases = self._active_revision_leases(); current = leases.get(revision_key)
            if not current or current.get("client_id") != client_id: return {"ok": False, "conflict": True, "revision_key": revision_key, "owner": current}
            now_dt = datetime.now(); current["heartbeat_at"] = now_dt.isoformat(timespec="seconds"); current["expires_at"] = (now_dt + timedelta(seconds=ttl)).isoformat(timespec="seconds"); atomic_write_json(self.state_path, self.state_data)
            return {"ok": True, "lease": current, "generation": self.generation}

    def release_revision_lease(self, revision_key, client_id):
        revision_key = str(revision_key or "").strip(); client_id = str(client_id or "").strip()
        with self.lock:
            leases = self._active_revision_leases(); current = leases.get(revision_key)
            if current and current.get("client_id") != client_id: return {"ok": False, "conflict": True, "revision_key": revision_key, "owner": current}
            if current: leases.pop(revision_key, None); atomic_write_json(self.state_path, self.state_data)
            return {"ok": True, "released": bool(current), "revision_key": revision_key, "generation": self.generation}

    def db_ready(self):
''',
    "NAS lease methods",
)
replace_once(
    "source/nas/server.py",
    '            "time": now(),\n        }',
    '            "time": now(),\n            "active_revision_leases": len(self._active_revision_leases()),\n        }',
    "lease count status",
)
replace_once(
    "source/nas/server.py",
    '            if p == "/api/mobile/push":\n',
    '''            if p in ("/api/revision-lock/acquire", "/api/revision-lock/heartbeat", "/api/revision-lock/release"):
                data = json.loads(body.decode("utf-8")) if body else {}
                if p.endswith("/acquire"):
                    result = self.state.acquire_revision_lease(data.get("revision_key"), data.get("client_id"), data.get("client_name"), data.get("ttl_seconds", 600))
                elif p.endswith("/heartbeat"):
                    result = self.state.heartbeat_revision_lease(data.get("revision_key"), data.get("client_id"), data.get("ttl_seconds", 600))
                else:
                    result = self.state.release_revision_lease(data.get("revision_key"), data.get("client_id"))
                if result.get("conflict"): self._json(409, {"detail": result})
                else: self._json(200, result)
                return
            if p == "/api/mobile/push":
''',
    "lease POST routes",
)
replace_once("source/nas/server.py", 'print("Windows API: /api/status, /api/sync/push, /api/sync/pull")', 'print("Windows API: /api/status, /api/sync/push, /api/sync/pull, /api/revision-lock/*")', "NAS API banner")

Path("source/nas/tests/test_revision_leases_104.py").write_text('''import tempfile, unittest\nfrom pathlib import Path\nfrom unittest.mock import patch\nimport server\n\nclass RevisionLease104Tests(unittest.TestCase):\n    def setUp(self):\n        self.tmp=tempfile.TemporaryDirectory(); root=Path(self.tmp.name)\n        self.patches=[patch.object(server,'DB_PATH',root/'data'/'pz_revize_shared.db'),patch.object(server,'ATTACHMENTS_DIR',root/'data'/'attachments'),patch.object(server,'CONFIG_PATH',root/'server_config.json'),patch.object(server,'STATE_PATH',root/'data'/'state.json')]\n        for p in self.patches:p.start()\n        self.state=server.ServerState()\n    def tearDown(self):\n        for p in reversed(self.patches):p.stop()\n        self.tmp.cleanup()\n    def test_single_owner_and_release(self):\n        self.assertTrue(self.state.acquire_revision_lease('26EI0001','pc-a','PC A',600)['ok'])\n        self.assertTrue(self.state.acquire_revision_lease('26EI0001','pc-b','PC B',600)['conflict'])\n        self.assertTrue(self.state.heartbeat_revision_lease('26EI0001','pc-a',600)['ok'])\n        self.assertTrue(self.state.release_revision_lease('26EI0001','pc-a')['released'])\n        self.assertTrue(self.state.acquire_revision_lease('26EI0001','pc-b','PC B',600)['ok'])\n''', encoding="utf-8")
