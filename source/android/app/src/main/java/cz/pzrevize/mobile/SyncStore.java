package cz.pzrevize.mobile;

import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

import org.json.JSONArray;
import org.json.JSONObject;

public final class SyncStore {
    private SyncStore() {}

    public static JSONObject exportDirty(Db helper) throws Exception {
        JSONObject root = new JSONObject();
        root.put("format", "PZ-REVIZE-Mobile-Sync");
        root.put("version", 1);
        root.put("customers", query(helper, "SELECT id,uuid,server_id,server_hash,name,ico,address,contact,note,updated_at FROM customers WHERE dirty=1 ORDER BY id"));
        root.put("revisions", query(helper, "SELECT r.id,r.uuid,r.server_id,r.server_hash,r.revision_no,r.revision_type,r.object_name,r.object_address,r.status,r.note,r.updated_at,c.uuid AS customer_uuid,c.server_id AS customer_server_id,COALESCE(s.server_id,0) AS source_server_id FROM revisions r JOIN customers c ON c.id=r.customer_id LEFT JOIN revisions s ON s.id=r.source_revision_id WHERE r.dirty=1 ORDER BY r.id"));
        root.put("measurements", query(helper, "SELECT m.id,m.uuid,m.server_id,m.server_hash,m.remote_kind,m.element,m.measure_type,m.row_type,m.item_key,m.parent_key,m.v1,m.v2,m.v3,m.v4,m.unit1,m.unit2,m.unit3,m.unit4,m.note,m.done,m.sort_order,m.updated_at,r.uuid AS revision_uuid,r.server_id AS revision_server_id,r.revision_type FROM measurements m JOIN revisions r ON r.id=m.revision_id WHERE m.dirty=1 ORDER BY m.id"));
        root.put("checklist", query(helper, "SELECT x.id,x.uuid,x.server_id,x.server_hash,x.catalog_id,x.group_name,x.source_ref,x.label,x.result,x.note,x.done,x.sort_order,x.updated_at,r.uuid AS revision_uuid,r.server_id AS revision_server_id FROM checklist x JOIN revisions r ON r.id=x.revision_id WHERE x.dirty=1 ORDER BY x.id"));
        root.put("defects", query(helper, "SELECT d.id,d.uuid,d.server_id,d.server_hash,d.text,d.severity,d.status,d.note,d.updated_at,r.uuid AS revision_uuid,r.server_id AS revision_server_id FROM defects d JOIN revisions r ON r.id=d.revision_id WHERE d.dirty=1 ORDER BY d.id"));
        JSONArray photos = query(helper, "SELECT p.id,p.uuid,p.server_id,p.server_hash,p.uri,p.title,p.note,p.kind,p.updated_at,r.uuid AS revision_uuid,r.server_id AS revision_server_id FROM photos p JOIN revisions r ON r.id=p.revision_id WHERE p.dirty=1 ORDER BY p.id");
        SQLiteDatabase db = helper.getReadableDatabase();
        for (int i = 0; i < photos.length(); i++) {
            JSONObject o = photos.getJSONObject(i);
            JSONArray links = new JSONArray();
            Cursor c = db.rawQuery("SELECT d.uuid,d.server_id FROM defect_photos x JOIN defects d ON d.id=x.defect_id WHERE x.photo_id=? ORDER BY x.id", new String[]{String.valueOf(o.optLong("id"))});
            while (c.moveToNext()) {
                JSONObject z = new JSONObject(); z.put("uuid", text(c,0)); z.put("server_id", c.getLong(1)); links.put(z);
            }
            c.close();
            o.put("defects", links);
        }
        root.put("photos", photos);
        root.put("deletions", query(helper, "SELECT rowid AS id,entity,uuid,server_id,server_hash FROM sync_deletions ORDER BY rowid"));
        return root;
    }

    private static JSONArray query(Db helper, String sql) throws Exception {
        JSONArray arr = new JSONArray();
        Cursor c = helper.getReadableDatabase().rawQuery(sql, null);
        while (c.moveToNext()) {
            JSONObject o = new JSONObject();
            for (int i=0;i<c.getColumnCount();i++) {
                String n=c.getColumnName(i);
                if (c.isNull(i)) o.put(n, JSONObject.NULL);
                else if (c.getType(i)==Cursor.FIELD_TYPE_INTEGER) o.put(n,c.getLong(i));
                else o.put(n,c.getString(i));
            }
            arr.put(o);
        }
        c.close(); return arr;
    }

    public static int dirtyCount(Db helper) {
        SQLiteDatabase db=helper.getReadableDatabase(); int n=0;
        String[] tables={"customers","revisions","measurements","checklist","defects","photos"};
        for(String t:tables)n+=scalar(db,"SELECT COUNT(*) FROM "+t+" WHERE dirty=1",null);
        n+=scalar(db,"SELECT COUNT(*) FROM sync_deletions",null);
        return n;
    }

    private static int scalar(SQLiteDatabase db,String sql,String[] args){Cursor c=db.rawQuery(sql,args);int n=c.moveToFirst()?c.getInt(0):0;c.close();return n;}
    private static String text(Cursor c,int i){return c.isNull(i)?"":c.getString(i);}

    private static void importFlag(SQLiteDatabase db, boolean on){
        ContentValues v=new ContentValues();v.put("key","sync_import");v.put("value",on?"1":"0");db.insertWithOnConflict("meta",null,v,SQLiteDatabase.CONFLICT_REPLACE);
    }

    private static String tableFor(String entity){
        switch(entity){case "customer":return "customers";case "revision":return "revisions";case "measurement":return "measurements";case "checklist":return "checklist";case "defect":return "defects";case "photo":return "photos";default:return null;}
    }

    private static String sentUpdatedAt(JSONObject sent, String entity, String uuid) throws Exception {
        String array;
        switch (entity) {
            case "customer": array="customers"; break;
            case "revision": array="revisions"; break;
            case "measurement": array="measurements"; break;
            case "checklist": array="checklist"; break;
            case "defect": array="defects"; break;
            case "photo": array="photos"; break;
            default: return "";
        }
        JSONArray rows=sent.optJSONArray(array); if(rows==null)return "";
        for(int i=0;i<rows.length();i++){
            JSONObject row=rows.getJSONObject(i);
            if(uuid.equals(row.optString("uuid")))return row.optString("updated_at");
        }
        return "";
    }

    public static void applyPushResult(Db helper, JSONObject result, JSONObject sent) throws Exception {
        SQLiteDatabase db=helper.getWritableDatabase();importFlag(db,true);
        try{
            JSONArray accepted=result.optJSONArray("accepted");
            if(accepted!=null)for(int i=0;i<accepted.length();i++){
                JSONObject o=accepted.getJSONObject(i);String entity=o.optString("entity");String table=tableFor(entity);String uuid=o.optString("uuid");if(table==null||uuid.isEmpty())continue;
                String snapshotStamp=sentUpdatedAt(sent,entity,uuid);
                ContentValues identity=new ContentValues();identity.put("server_id",o.optLong("server_id"));identity.put("server_hash",o.optString("server_hash"));
                db.update(table,identity,"uuid=?",new String[]{uuid});
                if(!snapshotStamp.isEmpty()){
                    ContentValues clean=new ContentValues();clean.put("dirty",0);
                    db.update(table,clean,"uuid=? AND updated_at=?",new String[]{uuid,snapshotStamp});
                }
            }
            JSONArray deleted=result.optJSONArray("deleted");
            if(deleted!=null)for(int i=0;i<deleted.length();i++){
                JSONObject o=deleted.getJSONObject(i);db.delete("sync_deletions","entity=? AND uuid=?",new String[]{o.optString("entity"),o.optString("uuid")});
            }
        }finally{importFlag(db,false);}
    }

    private static long localIdByServer(SQLiteDatabase db,String table,long serverId){
        if(serverId<=0)return 0;Cursor c=db.rawQuery("SELECT id FROM "+table+" WHERE server_id=?",new String[]{String.valueOf(serverId)});long id=c.moveToFirst()?c.getLong(0):0;c.close();return id;
    }
    private static boolean dirtyServer(SQLiteDatabase db,String table,long serverId){
        if(serverId<=0)return false;Cursor c=db.rawQuery("SELECT dirty FROM "+table+" WHERE server_id=?",new String[]{String.valueOf(serverId)});boolean d=c.moveToFirst()&&c.getInt(0)!=0;c.close();return d;
    }
    private static long upsert(SQLiteDatabase db,String table,String entity,long serverId,ContentValues v){
        if(serverId<=0)return 0;long id=localIdByServer(db,table,serverId);if(id>0&&dirtyServer(db,table,serverId))return id;
        v.put("server_id",serverId);v.put("dirty",0);if(id>0){db.update(table,v,"id=?",new String[]{String.valueOf(id)});return id;}v.put("uuid","server-"+entity+"-"+serverId);return db.insert(table,null,v);
    }

    public static int applyBootstrap(Db helper,JSONObject root)throws Exception{
        SQLiteDatabase db=helper.getWritableDatabase();int n=0;db.beginTransaction();importFlag(db,true);
        try{
            n+=customers(db,root.optJSONArray("customers"));
            n+=revisions(db,root.optJSONArray("revisions"));
            n+=measurements(db,root.optJSONArray("measurements"));
            n+=checklist(db,root.optJSONArray("checklist"));
            n+=defects(db,root.optJSONArray("defects"));
            db.setTransactionSuccessful();
        }finally{importFlag(db,false);db.endTransaction();}
        return n;
    }

    private static int customers(SQLiteDatabase db,JSONArray a)throws Exception{if(a==null)return 0;int n=0;for(int i=0;i<a.length();i++){JSONObject o=a.getJSONObject(i);ContentValues v=new ContentValues();v.put("name",o.optString("name"));v.put("ico",o.optString("ico"));v.put("address",o.optString("address"));v.put("contact",o.optString("contact"));v.put("note",o.optString("note"));v.put("updated_at",o.optString("updated_at"));v.put("server_hash",o.optString("server_hash"));if(upsert(db,"customers","customer",o.optLong("server_id"),v)>0)n++;}return n;}
    private static int revisions(SQLiteDatabase db,JSONArray a)throws Exception{if(a==null)return 0;int n=0;for(int i=0;i<a.length();i++){JSONObject o=a.getJSONObject(i);long cid=localIdByServer(db,"customers",o.optLong("customer_server_id"));if(cid<=0)continue;ContentValues v=new ContentValues();v.put("customer_id",cid);v.put("revision_no",o.optString("revision_no"));v.put("revision_type",o.optString("revision_type"));v.put("object_name",o.optString("object_name"));v.put("object_address",o.optString("object_address"));v.put("status",o.optString("status"));v.put("note",o.optString("note"));v.put("updated_at",o.optString("updated_at"));v.put("server_hash",o.optString("server_hash"));if(upsert(db,"revisions","revision",o.optLong("server_id"),v)>0)n++;}return n;}
    private static int measurements(SQLiteDatabase db, JSONArray a) throws Exception {
        if (a == null) return 0;
        int n = 0;
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.getJSONObject(i);
            long rid = localIdByServer(db, "revisions", o.optLong("revision_server_id"));
            if (rid <= 0) continue;
            String kind = o.optString("remote_kind");
            long sid = o.optLong("server_id");
            Cursor c = db.rawQuery("SELECT id,dirty,row_type,item_key,parent_key FROM measurements WHERE remote_kind=? AND server_id=?", new String[]{kind, String.valueOf(sid)});
            long id = 0; boolean dirty = false; String localRowType = "", localItemKey = "", localParentKey = "";
            if (c.moveToFirst()) {
                id = c.getLong(0); dirty = c.getInt(1) != 0;
                localRowType = c.isNull(2) ? "" : c.getString(2);
                localItemKey = c.isNull(3) ? "" : c.getString(3);
                localParentKey = c.isNull(4) ? "" : c.getString(4);
            }
            c.close();
            if (dirty) continue;

            ContentValues v = new ContentValues();
            v.put("revision_id", rid); v.put("remote_kind", kind);
            v.put("element", o.optString("element")); v.put("measure_type", o.optString("measure_type"));

            String explicitRt = o.optString("row_type");
            String rt = explicitRt;
            if (rt.isEmpty() && !localRowType.isEmpty()) rt = localRowType;
            if (rt.isEmpty()) {
                String mt = o.optString("measure_type").toUpperCase();
                rt = ("CIRCUIT".equals(mt)||"POINT".equals(mt)||"CONTINUITY".equals(mt)||"RCD".equals(mt)||"RCBO".equals(mt)||"GROUP".equals(mt)||"FUNCTION".equals(mt)||"NOTE".equals(mt)||"BLANK".equals(mt))
                        ? mt : ("CIRCUIT".equals(kind) ? "CIRCUIT" : "MEASUREMENT");
            }
            v.put("row_type", rt);
            String ik = o.optString("item_key"); if (ik.isEmpty()) ik = localItemKey; v.put("item_key", ik);
            String pk = o.optString("parent_key"); if (pk.isEmpty()) pk = localParentKey; v.put("parent_key", pk);

            for (int z = 1; z <= 4; z++) { v.put("v"+z, o.optString("v"+z)); v.put("unit"+z, o.optString("unit"+z)); }
            v.put("note", o.optString("note")); v.put("done", o.optInt("done")); v.put("sort_order", o.optInt("sort_order"));
            v.put("updated_at", o.optString("updated_at")); v.put("server_id", sid); v.put("server_hash", o.optString("server_hash")); v.put("dirty", 0);
            if (id > 0) db.update("measurements", v, "id=?", new String[]{String.valueOf(id)});
            else { v.put("uuid", "server-measurement-"+kind+"-"+sid); db.insert("measurements", null, v); }
            n++;
        }
        return n;
    }
    private static int checklist(SQLiteDatabase db, JSONArray a) throws Exception {
        if (a == null) return 0;
        int n = 0;
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.getJSONObject(i);
            long rid = localIdByServer(db, "revisions", o.optLong("revision_server_id"));
            if (rid <= 0) continue;
            long sid = o.optLong("server_id");

            String localGroup = "", localSource = ""; long localCatalog = 0;
            Cursor c = db.rawQuery("SELECT group_name,source_ref,catalog_id FROM checklist WHERE server_id=?", new String[]{String.valueOf(sid)});
            if (c.moveToFirst()) {
                localGroup = c.isNull(0) ? "" : c.getString(0);
                localSource = c.isNull(1) ? "" : c.getString(1);
                localCatalog = c.getLong(2);
            }
            c.close();

            String group = o.optString("group_name"); if (group.isEmpty()) group = localGroup;
            String source = o.optString("source_ref"); if (source.isEmpty()) source = localSource;
            long catalog = o.optLong("catalog_id"); if (catalog <= 0) catalog = localCatalog;

            ContentValues v = new ContentValues();
            v.put("revision_id", rid); v.put("catalog_id", catalog); v.put("group_name", group); v.put("source_ref", source);
            v.put("label", o.optString("label")); v.put("result", o.optString("result")); v.put("note", o.optString("note"));
            v.put("done", o.optInt("done")); v.put("sort_order", o.optInt("sort_order")); v.put("updated_at", o.optString("updated_at"));
            v.put("server_hash", o.optString("server_hash"));
            if (upsert(db, "checklist", "checklist", sid, v) > 0) n++;
        }
        return n;
    }
    private static int defects(SQLiteDatabase db,JSONArray a)throws Exception{if(a==null)return 0;int n=0;for(int i=0;i<a.length();i++){JSONObject o=a.getJSONObject(i);long rid=localIdByServer(db,"revisions",o.optLong("revision_server_id"));if(rid<=0)continue;ContentValues v=new ContentValues();v.put("revision_id",rid);v.put("text",o.optString("text"));v.put("severity",o.optString("severity"));v.put("status",o.optString("status"));v.put("note",o.optString("note"));v.put("updated_at",o.optString("updated_at"));v.put("server_hash",o.optString("server_hash"));if(upsert(db,"defects","defect",o.optLong("server_id"),v)>0)n++;}return n;}
}
