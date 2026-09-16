from __future__ import annotations
import json, os, sqlite3, threading, uuid
from pathlib import Path
from urllib import request
import tkinter as tk
from tkinter import ttk, messagebox

ROOT=Path.home()/"PZ_REVIZE_SYNC2_TEST"; ROOT.mkdir(exist_ok=True)
CFG=ROOT/"config.json"; DB=ROOT/"client.sqlite3"
SCHEMA="CREATE TABLE IF NOT EXISTS outbox(change_id TEXT PRIMARY KEY, entity TEXT, entity_id TEXT, fields TEXT, base_version INTEGER, created REAL); CREATE TABLE IF NOT EXISTS state(entity TEXT, entity_id TEXT, fields TEXT, version INTEGER, deleted INTEGER, PRIMARY KEY(entity,entity_id)); CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT);"
def db():
 c=sqlite3.connect(DB); c.executescript(SCHEMA); return c
def config():
 if CFG.exists(): return json.loads(CFG.read_text(encoding="utf-8"))
 x={"device_id":str(uuid.uuid4()),"server_url":"http://127.0.0.1:8765"}; CFG.write_text(json.dumps(x,indent=2)); return x
def post(url,payload):
 r=request.Request(url.rstrip("/")+"/sync/v2/batch",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
 with request.urlopen(r,timeout=10) as x:return json.loads(x.read().decode())
C=config()
def queue_change():
 entity=entity_var.get().strip() or "revision"; eid=id_var.get().strip(); value=value_var.get()
 if not eid: messagebox.showwarning("SYNC 2.0","Zadej ID záznamu."); return
 with db() as c:
  row=c.execute("SELECT version,fields FROM state WHERE entity=? AND entity_id=?",(entity,eid)).fetchone(); version=int(row[0]) if row else 0
  base=json.loads(row[1]) if row else {}; fields={"value":value,"_base_values":{"value":base.get("value")}}
  cid=str(uuid.uuid4()); c.execute("INSERT INTO outbox VALUES(?,?,?,?,?,strftime('%s','now'))",(cid,entity,eid,json.dumps(fields),version))
 log("Změna uložena offline: "+cid)
def sync():
 def run():
  try:
   with db() as c:
    rows=c.execute("SELECT change_id,entity,entity_id,fields,base_version,created FROM outbox ORDER BY created").fetchall(); cur=int((c.execute("SELECT v FROM meta WHERE k='cursor'").fetchone() or [0])[0])
   changes=[{"change_id":r[0],"entity":r[1],"entity_id":r[2],"kind":"upsert","fields":json.loads(r[3]),"base_version":r[4],"created_at":r[5],"device_id":C["device_id"]} for r in rows]
   result=post(C["server_url"],{"device_id":C["device_id"],"cursor":cur,"changes":changes})
   with db() as c:
    for cid in result.get("accepted",[])+result.get("already_applied",[]): c.execute("DELETE FROM outbox WHERE change_id=?",(cid,))
    for ev in result.get("events",[]):
     f=ev.get("fields",{}); f.pop("_base_values",None); row=c.execute("SELECT fields FROM state WHERE entity=? AND entity_id=?",(ev["entity"],ev["entity_id"])).fetchone(); old=json.loads(row[0]) if row else {}; old.update(f); c.execute("INSERT INTO state(entity,entity_id,fields,version,deleted) VALUES(?,?,?,?,0) ON CONFLICT(entity,entity_id) DO UPDATE SET fields=excluded.fields,version=excluded.version,deleted=0",(ev["entity"],ev["entity_id"],json.dumps(old),int(ev.get("base_version",0))+1))
    c.execute("INSERT INTO meta(k,v) VALUES('cursor',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(str(result.get("cursor",cur)),))
   log("SYNC OK | přeneseno: %d | konflikty: %d | kurzor: %s"%(len(result.get("accepted",[])),len(result.get("conflicts",[])),result.get("cursor")))
   if result.get("conflicts"): messagebox.showwarning("Konflikt",json.dumps(result["conflicts"],ensure_ascii=False,indent=2))
  except Exception as e: log("OFFLINE / CHYBA: "+str(e))
  sync_btn.after(0,lambda:sync_btn.config(state="normal"))
 sync_btn.config(state="disabled"); threading.Thread(target=run,daemon=True).start()
def log(s): txt.after(0,lambda:(txt.insert("end",s+"\n"),txt.see("end")))
root=tk.Tk(); root.title("PZ-REVIZE – SYNC 2.0 TEST"); root.geometry("700x500")
frm=ttk.Frame(root,padding=12); frm.pack(fill="both",expand=True)
ttk.Label(frm,text="PZ-REVIZE – nový SYNC 2.0",font=("Segoe UI",16,"bold")).pack(anchor="w")
ttk.Label(frm,text="Testovací klient – oddělený od produkční databáze").pack(anchor="w",pady=(0,12))
entity_var=tk.StringVar(value="revision"); id_var=tk.StringVar(value="TEST-001"); value_var=tk.StringVar();
for label,var in (("Entita",entity_var),("ID",id_var),("Hodnota",value_var)):
 row=ttk.Frame(frm); row.pack(fill="x",pady=3); ttk.Label(row,text=label,width=12).pack(side="left"); ttk.Entry(row,textvariable=var).pack(side="left",fill="x",expand=True)
btns=ttk.Frame(frm); btns.pack(fill="x",pady=10); ttk.Button(btns,text="Uložit změnu",command=queue_change).pack(side="left",padx=(0,6)); sync_btn=ttk.Button(btns,text="SYNCHRONIZOVAT",command=sync); sync_btn.pack(side="left")
ttk.Label(frm,text="Device ID: "+C["device_id"]).pack(anchor="w"); ttk.Label(frm,text="Server: "+C["server_url"]).pack(anchor="w")
txt=tk.Text(frm,height=18); txt.pack(fill="both",expand=True,pady=(10,0)); log("Připraveno. Spusť nejdříve testovací NAS server.")
root.mainloop()
