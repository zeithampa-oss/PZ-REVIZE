from __future__ import annotations
import hashlib, json, os, threading
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import FileResponse

APP = FastAPI(title="PZ-REVIZE NAS SYNC 1.0")
ROOT = Path(os.environ.get("PZ_REVIZE_SYNC_ROOT", "/volume1/web/PZ_REVIZE_NAS_SERVER"))
DATA = ROOT / "sync_v1"
BUNDLES = DATA / "revisions"
MANIFEST = DATA / "manifest.json"
CONFIG = ROOT / "server_config.json"
LOCK = threading.RLock()


def _load_config():
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"api_key": os.environ.get("PZ_REVIZE_API_KEY", "")}


def _auth(key):
    expected = str(_load_config().get("api_key") or "")
    if not expected or key != expected:
        raise HTTPException(401, "Neplatný API klíč.")


def _load():
    DATA.mkdir(parents=True, exist_ok=True)
    BUNDLES.mkdir(parents=True, exist_ok=True)
    if not MANIFEST.exists():
        MANIFEST.write_text(json.dumps({"format":"PZ-REVIZE-SYNC-1","generation":0,"updated_at":None,"revisions":[]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _save(obj):
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, MANIFEST)


@APP.get("/api/status")
def status(x_api_key: str = Header(default="")):
    _auth(x_api_key)
    with LOCK:
        m = _load()
        return {"ok":True,"service":"PZ-REVIZE NAS SYNC 1.0","generation":m["generation"],"revision_count":len(m["revisions"]),"updated_at":m.get("updated_at")}


@APP.get("/api/sync/v1/manifest")
def manifest(x_api_key: str = Header(default="")):
    _auth(x_api_key)
    with LOCK:
        m = _load()
        return m


@APP.get("/api/sync/v1/revisions/{revision_uid}")
def pull_revision(revision_uid: str, x_api_key: str = Header(default="")):
    _auth(x_api_key)
    path = BUNDLES / f"{revision_uid}.zip"
    if not path.exists():
        raise HTTPException(404, "Revize na NAS není.")
    return FileResponse(path, media_type="application/zip", filename=path.name)


@APP.post("/api/sync/v1/revisions")
async def push_revision(
    revision_uid: str = Form(...),
    revision_no: str = Form(""),
    content_hash: str = Form(...),
    client_name: str = Form("PZ-REVIZE PC"),
    bundle: UploadFile = File(...),
    x_api_key: str = Header(default="")
):
    _auth(x_api_key)
    if len(revision_uid) > 100 or len(content_hash) != 64:
        raise HTTPException(400, "Neplatný identifikátor revize.")
    data = await bundle.read()
    if not data:
        raise HTTPException(400, "Prázdný balík.")
    # Bundle hash is transport integrity; logical revision hash is content_hash.
    transport_hash = hashlib.sha256(data).hexdigest()
    with LOCK:
        m = _load()
        existing = next((r for r in m["revisions"] if r["revision_uid"] == revision_uid), None)
        if existing:
            if existing["content_hash"] == content_hash:
                return {"ok":True,"stored":False,"generation":m["generation"],"revision_uid":revision_uid}
            raise HTTPException(409, detail={"message":"Stejná revize má na NAS jiný obsah.","revision_uid":revision_uid,"revision_no":revision_no,"server_hash":existing["content_hash"]})
        path = BUNDLES / f"{revision_uid}.zip"
        path.write_bytes(data)
        now = datetime.now().isoformat(timespec="seconds")
        m["generation"] += 1
        m["updated_at"] = now
        m["revisions"].append({"revision_uid":revision_uid,"revision_no":revision_no,"content_hash":content_hash,"transport_sha256":transport_hash,"size":len(data),"client_name":client_name,"updated_at":now})
        _save(m)
        return {"ok":True,"stored":True,"generation":m["generation"],"revision_uid":revision_uid}
