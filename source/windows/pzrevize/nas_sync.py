from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from .database import app_data_dir

SYNC_FORMAT = "PZ-REVIZE-SYNC-1"
STATE_TABLE = "pz_sync_revision_state"
PATH_FIELDS = [("revision_attachments", "stored_path"),("revision_documents", "stored_path"),("revision_photos", "stored_path"),("revision_defects", "photo_path")]

class NasSyncError(RuntimeError): pass
class NasConflictError(NasSyncError):
    def __init__(self, message: str, server_generation: int | None = None):
        super().__init__(message); self.server_generation = server_generation

def _setting(db,key,default=""):
    row=db.fetchone("SELECT value FROM settings WHERE key=?",(key,)); return str(row["value"]) if row and row["value"] is not None else default

def set_setting(db,key,value):
    db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,value))

def get_sync_settings(db):
    lan=_setting(db,"nas_url_lan",_setting(db,"nas_url","http://ADRESA_NAS:8767")); vpn=_setting(db,"nas_url_vpn",""); mode=_setting(db,"nas_connection_mode","auto")
    return {"url":lan,"lan_url":lan,"vpn_url":vpn,"mode":mode,"token":_setting(db,"nas_api_token",""),"generation":int(_setting(db,"nas_generation","0") or 0),"last_sync":_setting(db,"nas_last_sync",""),"last_transport":_setting(db,"nas_last_transport",""),"last_signature":_setting(db,"nas_last_signature",""),"last_sync_result":_setting(db,"nas_last_sync_result",""),"last_sync_error":_setting(db,"nas_last_sync_error","")}

def save_sync_settings(db,url,token,vpn_url=None,mode=None):
    lan=str(url or "").strip().rstrip("/"); vpn=str(vpn_url or "").strip().rstrip("/"); mode=(mode or _setting(db,"nas_connection_mode","auto")).lower(); mode=mode if mode in ("auto","lan","vpn") else "auto"
    for k,v in (("nas_url",lan),("nas_url_lan",lan),("nas_url_vpn",vpn),("nas_connection_mode",mode),("nas_api_token",str(token or "").strip())): set_setting(db,k,v)

def endpoint_candidates(settings):
    mode=settings.get("mode","auto"); out=[]
    if mode in ("auto","lan") and settings.get("lan_url") and "ADRESA_NAS" not in settings["lan_url"]: out.append((settings["lan_url"],"LAN"))
    if mode in ("auto","vpn") and settings.get("vpn_url") and "ADRESA_NAS" not in settings["vpn_url"]: out.append((settings["vpn_url"],"VPN"))
    return out

def _request(base,path,token,method="GET",body=None,headers=None,timeout=60):
    h={"X-API-Key":token,"Accept":"application/json"}; h.update(headers or {}); req=urllib.request.Request(base.rstrip("/")+path,data=body,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,r.headers,r.read()
    except urllib.error.HTTPError as e:
        raw=e.read().decode("utf-8","replace")
        try:detail=json.loads(raw).get("detail",raw)
        except Exception:detail=raw
        if e.code==409:raise NasConflictError(str(detail))
        raise NasSyncError(f"NAS odpověděl HTTP {e.code}: {detail}") from e
    except Exception as e:raise NasSyncError(f"Nelze se spojit s NAS: {e}") from e

def get_status(base_url,token,timeout=30):
    if not base_url or "ADRESA_NAS" in base_url:raise NasSyncError("Nejdřív zadej skutečnou adresu NAS serveru.")
    if not token:raise NasSyncError("Není zadaný API klíč.")
    _,_,raw=_request(base_url,"/api/status",token,timeout=timeout); return json.loads(raw.decode("utf-8"))

def resolve_endpoint(settings,timeout=6):
    if not settings.get("token"):raise NasSyncError("Není zadaný API klíč.")
    errors=[]
    for url,transport in endpoint_candidates(settings):
        try:return url,transport,get_status(url,settings["token"],timeout)
        except Exception as e:errors.append(f"{transport}: {e}")
    raise NasSyncError("NAS není dostupný přes žádné nastavené připojení. "+" | ".join(errors))

def _ensure_schema(db):
    with db.connect() as con:
        cols={r[1] for r in con.execute("PRAGMA table_info(revisions)")}
        if "sync_uid" not in cols:con.execute("ALTER TABLE revisions ADD COLUMN sync_uid TEXT")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_revisions_sync_uid ON revisions(sync_uid)")
        con.execute(f"CREATE TABLE IF NOT EXISTS {STATE_TABLE}(revision_uid TEXT PRIMARY KEY,revision_no TEXT,last_hash TEXT NOT NULL,last_sync_at TEXT,last_error TEXT DEFAULT '')")
        for r in con.execute("SELECT id FROM revisions WHERE sync_uid IS NULL OR TRIM(sync_uid)='' ").fetchall():con.execute("UPDATE revisions SET sync_uid=? WHERE id=?",(str(uuid.uuid4()),r[0]))

def _sha_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def _norm(v,col):
    if v is None:return None
    if col=="id" or col.endswith("_id") or col in ("created_at","updated_at","last_used","usage_count"):return None
    if "path" in col.lower() and isinstance(v,str):
        p=Path(v)
        if p.is_file():return "FILE:"+_sha_file(p)
        return Path(v).name
    return v

def _tables(con):return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]

def _logical_hash(con,rid):
    rev=con.execute("SELECT * FROM revisions WHERE id=?",(rid,)).fetchone()
    if not rev:return ""
    payload={"revision":{k:_norm(rev[k],k) for k in rev.keys()},"children":{}}
    for t in _tables(con):
        if t in ("settings",STATE_TABLE,"revisions"):continue
        cols={r[1] for r in con.execute(f'PRAGMA table_info("{t}")')}
        if "revision_id" not in cols:continue
        vals=[{k:_norm(row[k],k) for k in row.keys()} for row in con.execute(f'SELECT * FROM "{t}" WHERE revision_id=?',(rid,)).fetchall()]
        vals.sort(key=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,default=str)); payload["children"][t]=vals
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()

def _attachment_sources(con,rid):
    out=[]
    for table,col in PATH_FIELDS:
        try:rows=con.execute(f'SELECT {col} FROM "{table}" WHERE revision_id=?',(rid,)).fetchall()
        except sqlite3.Error:continue
        for r in rows:
            raw=str(r[0] or ""); p=Path(raw)
            if raw.startswith("attachments/") and not p.is_file():p=app_data_dir()/raw
            if p.is_file():out.append(p)
    return list(dict.fromkeys(out))

def _direct_parent_rows(con,rev):
    result={}
    for table,col,val in (("customers","id",rev["customer_id"]),("objects","id",rev["object_id"]),("jobs","id",rev["job_id"])):
        if val is None:continue
        try:r=con.execute(f'SELECT * FROM {table} WHERE id=?',(val,)).fetchone()
        except sqlite3.Error:r=None
        if r:result[table]=[dict(r)]
    return result

def _make_bundle(db,rid,dest):
    con=sqlite3.connect(db.path);con.row_factory=sqlite3.Row
    try:
        rev=con.execute("SELECT * FROM revisions WHERE id=?",(rid,)).fetchone()
        if not rev:raise NasSyncError("Revize neexistuje.")
        payload={"format":SYNC_FORMAT,"revision_uid":str(rev["sync_uid"]),"revision_no":str(rev["revision_no"] or ""),"hash":_logical_hash(con,rid),"created_at":datetime.now().isoformat(timespec="seconds"),"tables":{},"parents":_direct_parent_rows(con,rev),"attachments":[]}
        payload["tables"]["revisions"]=[dict(rev)]
        for t in _tables(con):
            if t in ("revisions","settings",STATE_TABLE):continue
            cols={r[1] for r in con.execute(f'PRAGMA table_info("{t}")')}
            if "revision_id" in cols:payload["tables"][t]=[dict(r) for r in con.execute(f'SELECT * FROM "{t}" WHERE revision_id=?',(rid,)).fetchall()]
        for p in _attachment_sources(con,rid):
            name=f"{_sha_file(p)[:16]}_{p.name.replace(chr(92),'_').replace('/','_')}";payload["attachments"].append({"name":name,"source":str(p)})
        root=Path(tempfile.mkdtemp(prefix="pzsync1_"))
        try:
            (root/"payload.json").write_text(json.dumps(payload,ensure_ascii=False,default=str),encoding="utf-8");att=root/"attachments";att.mkdir()
            for a in payload["attachments"]:shutil.copy2(a["source"],att/a["name"])
            with zipfile.ZipFile(dest,"w",zipfile.ZIP_DEFLATED) as z:
                z.write(root/"payload.json","payload.json")
                for p in att.iterdir():z.write(p,"attachments/"+p.name)
            return payload
        finally:shutil.rmtree(root,ignore_errors=True)
    finally:con.close()

def _all_local_revisions(db):
    _ensure_schema(db);con=sqlite3.connect(db.path);con.row_factory=sqlite3.Row
    try:return [dict(r) for r in con.execute("SELECT id,revision_no,sync_uid FROM revisions ORDER BY revision_no,id").fetchall()]
    finally:con.close()

def _local_state(db,uid):
    row=db.fetchone(f"SELECT last_hash FROM {STATE_TABLE} WHERE revision_uid=?",(uid,));return str(row["last_hash"]) if row else ""

def _save_state(db,uid,rev_no,h,error=""):
    db.execute(f"INSERT INTO {STATE_TABLE}(revision_uid,revision_no,last_hash,last_sync_at,last_error) VALUES(?,?,?,?,?) ON CONFLICT(revision_uid) DO UPDATE SET revision_no=excluded.revision_no,last_hash=excluded.last_hash,last_sync_at=excluded.last_sync_at,last_error=excluded.last_error",(uid,rev_no,h,datetime.now().isoformat(timespec="seconds"),error))

def _multipart(fields):
    boundary="----PZSYNC1"+uuid.uuid4().hex;chunks=[]
    for k,v in fields.items():chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"bundle\"; filename=\"revision.zip\"\r\nContent-Type: application/zip\r\n\r\n".encode())
    return boundary,b"".join(chunks),f"\r\n--{boundary}--\r\n".encode()

def _push_revision(base,token,bundle,payload,client_name):
    boundary,pre,post=_multipart({"revision_uid":payload["revision_uid"],"revision_no":payload["revision_no"],"content_hash":payload["hash"],"client_name":client_name})
    import http.client,urllib.parse
    u=urllib.parse.urlparse(base);c=(http.client.HTTPSConnection if u.scheme=="https" else http.client.HTTPConnection)(u.hostname,u.port or (443 if u.scheme=="https" else 80),timeout=180)
    try:
        endpoint=(u.path.rstrip("/")+"/api/sync/v1/revisions") or "/api/sync/v1/revisions";c.putrequest("POST",endpoint);c.putheader("X-API-Key",token);c.putheader("Content-Type",f"multipart/form-data; boundary={boundary}");c.putheader("Content-Length",str(len(pre)+bundle.stat().st_size+len(post)));c.endheaders();c.send(pre)
        with open(bundle,"rb") as f:
            for ch in iter(lambda:f.read(1024*1024),b""):c.send(ch)
        c.send(post);r=c.getresponse();raw=r.read().decode("utf-8","replace")
        if r.status==409:raise NasConflictError(raw)
        if not 200<=r.status<300:raise NasSyncError(f"Odeslání revize selhalo HTTP {r.status}: {raw}")
        return json.loads(raw or "{}")
    finally:c.close()

def _manifest(base,token):_,_,raw=_request(base,"/api/sync/v1/manifest",token,timeout=60);return json.loads(raw.decode())
def _download_revision(base,token,uid,dest):_,_,raw=_request(base,"/api/sync/v1/revisions/"+uid,token,timeout=180);Path(dest).write_bytes(raw)

def _import_bundle(db,bundle):
    root=Path(tempfile.mkdtemp(prefix="pzimport1_"))
    try:
        with zipfile.ZipFile(bundle) as z:z.extractall(root)
        payload=json.loads((root/"payload.json").read_text(encoding="utf-8"));
        if payload.get("format")!=SYNC_FORMAT:raise NasSyncError("Nepodporovaný balík synchronizace.")
        uid=payload["revision_uid"]
        if db.fetchone("SELECT id FROM revisions WHERE sync_uid=?",(uid,)):return False,payload
        with db.connect() as con:
            idmap={}
            for table in ("customers","objects","jobs"):
                for row in payload.get("parents",{}).get(table,[]):
                    old=row["id"];found=None
                    try:
                        if table=="customers":found=con.execute("SELECT id FROM customers WHERE name=? AND COALESCE(address,'')=COALESCE(?, '')",(row.get("name"),row.get("address"))).fetchone()
                        elif table=="objects":found=con.execute("SELECT id FROM objects WHERE name=? AND COALESCE(address,'')=COALESCE(?, '')",(row.get("name"),row.get("address"))).fetchone()
                        elif table=="jobs" and row.get("job_no"):found=con.execute("SELECT id FROM jobs WHERE job_no=?",(row.get("job_no"),)).fetchone()
                    except sqlite3.Error:pass
                    if found:idmap[(table,old)]=found[0]
                    else:
                        cols=[c for c in row if c!="id"];vals=[row[c] for c in cols]
                        try:cur=con.execute(f'INSERT INTO {table} ({",".join(cols)}) VALUES ({",".join("?" for _ in vals)})');idmap[(table,old)]=cur.lastrowid
                        except sqlite3.Error:pass
            rev=payload["tables"]["revisions"][0];cols=[c for c in rev if c!="id"];vals=[]
            for c in cols:
                v=rev[c]
                if c=="customer_id":v=idmap.get(("customers",v),v)
                elif c=="object_id":v=idmap.get(("objects",v),v)
                elif c=="job_id":v=idmap.get(("jobs",v),v)
                vals.append(v)
            cur=con.execute(f'INSERT INTO revisions ({",".join(cols)}) VALUES ({",".join("?" for _ in vals)})',vals);newrid=cur.lastrowid
            for table,rows in payload["tables"].items():
                if table=="revisions":continue
                try:existing_cols={r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
                except sqlite3.Error:continue
                for row in rows:
                    cols=[c for c in row if c in existing_cols and c!="id"];vals=[]
                    for c in cols:
                        v=row[c]
                        if c=="revision_id":v=newrid
                        elif c.endswith("_id") and c!="revision_id":
                            if c=="instrument_id":
                                try:v=con.execute("SELECT id FROM instruments WHERE id=?",(v,)).fetchone()[0]
                                except Exception:v=None
                            else:v=None
                        vals.append(v)
                    try:con.execute(f'INSERT INTO "{table}" ({",".join(cols)}) VALUES ({",".join("?" for _ in vals)})',vals)
                    except sqlite3.IntegrityError:pass
            attdir=app_data_dir()/"attachments";attdir.mkdir(exist_ok=True)
            for a in payload.get("attachments",[]):
                src=root/"attachments"/a["name"];dst=attdir/a["name"]
                if src.exists():shutil.copy2(src,dst)
            con.commit()
        _save_state(db,uid,payload.get("revision_no",""),payload["hash"]);return True,payload
    finally:shutil.rmtree(root,ignore_errors=True)

def push_to_nas(db,base_url,token,client_version,client_name="PZ-REVIZE PC",expected_generation=None):
    _ensure_schema(db);pushed=[];conflicts=[]
    for r in _all_local_revisions(db):
        con=sqlite3.connect(db.path);con.row_factory=sqlite3.Row
        try:h=_logical_hash(con,r["id"])
        finally:con.close()
        if _local_state(db,r["sync_uid"])==h:continue
        tmp=Path(tempfile.mktemp(suffix=".zip"))
        try:
            p=_make_bundle(db,r["id"],tmp)
            try:_push_revision(base_url,token,tmp,p,client_name);pushed.append(r["revision_no"]);_save_state(db,r["sync_uid"],r["revision_no"],p["hash"])
            except NasConflictError:conflicts.append(r["revision_no"])
        finally:
            try:tmp.unlink()
            except OSError:pass
    if conflicts:raise NasConflictError("Konflikt revizí: "+", ".join(map(str,conflicts)))
    set_setting(db,"nas_last_sync_result","push" if pushed else "equal");set_setting(db,"nas_last_sync",datetime.now().isoformat(timespec="seconds"));set_setting(db,"nas_last_sync_error","")
    return {"ok":True,"pushed_revisions":pushed,"generation":int(get_status(base_url,token).get("generation") or 0)}

def pull_from_nas(db,base_url,token,can_pull=None):
    _ensure_schema(db);m=_manifest(base_url,token);pulled=[];conflicts=[]
    for r in m.get("revisions",[]):
        uid=r["revision_uid"];local=db.fetchone("SELECT id FROM revisions WHERE sync_uid=?",(uid,))
        if local:
            con=sqlite3.connect(db.path);con.row_factory=sqlite3.Row
            try:lh=_logical_hash(con,local["id"])
            finally:con.close()
            if lh==r["content_hash"]:_save_state(db,uid,r.get("revision_no",""),r["content_hash"]);continue
            conflicts.append(r.get("revision_no",uid));continue
        tmp=Path(tempfile.mktemp(suffix=".zip"))
        try:_download_revision(base_url,token,uid,tmp);changed,p=_import_bundle(db,tmp);pulled.append(p.get("revision_no",uid)) if changed else None
        finally:
            try:tmp.unlink()
            except OSError:pass
    if conflicts:raise NasConflictError("Konflikt revizí: "+", ".join(map(str,conflicts)))
    set_setting(db,"nas_last_sync_result","pull" if pulled else "equal");set_setting(db,"nas_last_sync",datetime.now().isoformat(timespec="seconds"));set_setting(db,"nas_last_sync_error","")
    return {"ok":True,"pulled_revisions":pulled,"generation":int(m.get("generation") or 0)}

def safe_sync_once(db,base_url,token,client_version,client_name="PZ-REVIZE PC",allow_pull=True,can_pull=None):
    _ensure_schema(db);pushed=[];pulled=[];conflicts=[]
    try:pushed=push_to_nas(db,base_url,token,client_version,client_name).get("pushed_revisions",[])
    except NasConflictError as e:conflicts.append(str(e))
    if allow_pull:
        try:pulled=pull_from_nas(db,base_url,token,can_pull=can_pull).get("pulled_revisions",[])
        except NasConflictError as e:conflicts.append(str(e))
    if conflicts:set_setting(db,"nas_last_sync_result","conflict");set_setting(db,"nas_last_sync_error"," | ".join(conflicts));raise NasConflictError("; ".join(conflicts))
    return {"ok":True,"pushed_revisions":pushed,"pulled_revisions":pulled,"generation":int(get_status(base_url,token).get("generation") or 0)}

def create_complete_local_backup(db,prefix="before_nas_pull"):
    dest=app_data_dir()/"backups"/f"pz_revize_{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db";dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(db.path,dest);return dest
