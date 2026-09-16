from __future__ import annotations
import json, sqlite3, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .core import Change, ChangeKind, SyncEngine

DB_PATH = Path(__file__).with_name("sync_test_server.sqlite3")
SCHEMA = """
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, change_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency(change_id TEXT PRIMARY KEY, result TEXT NOT NULL);
"""
class Store:
    def __init__(self, path):
        self.path, self.lock = path, threading.RLock()
        with sqlite3.connect(path) as db: db.executescript(SCHEMA)
    def batch(self, body):
        device_id = str(body.get("device_id") or "")
        if not device_id: return {"accepted":[],"already_applied":[],"conflicts":[],"invalid":[{"error":"missing device_id"}],"events":[],"cursor":0}
        cursor=max(0,int(body.get("cursor",0))); changes=body.get("changes") or []
        with self.lock, sqlite3.connect(self.path) as db:
            db.row_factory=sqlite3.Row
            engine=SyncEngine("NAS")
            for row in db.execute("SELECT payload FROM events ORDER BY seq"):
                d=json.loads(row[0]); engine.apply(Change(d["entity"],d["entity_id"],ChangeKind(d["kind"]),d.get("fields",{}),int(d.get("base_version",0)),d["change_id"],d.get("device_id",""),float(d.get("created_at",0))))
            accepted=[]; already=[]; conflicts=[]; invalid=[]
            for raw in changes:
                cid=str(raw.get("change_id") or "")
                if not cid: invalid.append({"error":"missing change_id"}); continue
                idem=db.execute("SELECT result FROM idempotency WHERE change_id=?",(cid,)).fetchone()
                if idem:
                    old=json.loads(idem[0]); (already if old.get("status")=="accepted" else conflicts).append(cid if old.get("status")=="accepted" else old["conflict"]); continue
                try:
                    ch=Change(str(raw["entity"]),str(raw["entity_id"]),ChangeKind(str(raw["kind"])),dict(raw.get("fields") or {}),int(raw.get("base_version",0)),cid,device_id,float(raw.get("created_at",0)))
                    status=engine.apply(ch)
                    if status=="applied":
                        db.execute("INSERT INTO events(change_id,payload) VALUES(?,?)",(cid,json.dumps(ch.canonical(),ensure_ascii=False))); accepted.append(cid); result={"status":"accepted"}
                    elif status=="already_applied": already.append(cid); result={"status":"accepted"}
                    else: conflict=engine.conflicts[-1]; conflicts.append(conflict); result={"status":"conflict","conflict":conflict}
                    db.execute("INSERT INTO idempotency(change_id,result) VALUES(?,?)",(cid,json.dumps(result,ensure_ascii=False)))
                except Exception as exc: invalid.append({"change_id":cid,"error":str(exc)})
            events=[json.loads(r[0]) for r in db.execute("SELECT payload FROM events WHERE seq>? ORDER BY seq",(cursor,))]
            new_cursor=int(db.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]); db.commit()
            return {"accepted":accepted,"already_applied":already,"conflicts":conflicts,"invalid":invalid,"events":events,"cursor":new_cursor}
STORE=Store(DB_PATH)
class Handler(BaseHTTPRequestHandler):
    def _send(self,status,payload):
        data=json.dumps(payload,ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self): self._send(200,{"ok":True,"sync_v2":True}) if urlparse(self.path).path=="/api/status" else self._send(404,{"detail":"not found"})
    def do_POST(self):
        if urlparse(self.path).path!="/sync/v2/batch": return self._send(404,{"detail":"not found"})
        try: self._send(200,STORE.batch(json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))).decode())))
        except Exception as exc: self._send(400,{"detail":str(exc)})
    def log_message(self,fmt,*args): print(fmt%args)
if __name__=="__main__":
    print("PZ-REVIZE SYNC 2.0 test server: http://0.0.0.0:8765")
    ThreadingHTTPServer(("0.0.0.0",8765),Handler).serve_forever()
