package cz.pzrevize.mobile;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class Db extends SQLiteOpenHelper {
    private static final int DB_VERSION = 6;

    public Db(Context c) {
        super(c, "pzrevize_mobile.db", null, DB_VERSION);
    }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE customers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, ico TEXT, address TEXT, contact TEXT, note TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, uuid TEXT, server_id INTEGER DEFAULT 0, server_hash TEXT DEFAULT '', dirty INTEGER DEFAULT 1)");
        db.execSQL("CREATE TABLE revisions(id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL, revision_no TEXT, revision_type TEXT DEFAULT 'ELEKTRO', object_name TEXT, object_address TEXT, status TEXT DEFAULT 'Rozpracovaná', note TEXT, source_revision_id INTEGER, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, uuid TEXT, server_id INTEGER DEFAULT 0, server_hash TEXT DEFAULT '', dirty INTEGER DEFAULT 1)");
        db.execSQL("CREATE TABLE measurements(id INTEGER PRIMARY KEY AUTOINCREMENT, revision_id INTEGER NOT NULL, element TEXT, measure_type TEXT, row_type TEXT DEFAULT '', item_key TEXT DEFAULT '', parent_key TEXT DEFAULT '', v1 TEXT, v2 TEXT, v3 TEXT, v4 TEXT, unit1 TEXT, unit2 TEXT, unit3 TEXT, unit4 TEXT, note TEXT, done INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, remote_kind TEXT DEFAULT '', uuid TEXT, server_id INTEGER DEFAULT 0, server_hash TEXT DEFAULT '', dirty INTEGER DEFAULT 1)");
        db.execSQL("CREATE TABLE checklist(id INTEGER PRIMARY KEY AUTOINCREMENT, revision_id INTEGER NOT NULL, catalog_id INTEGER DEFAULT 0, group_name TEXT DEFAULT '', source_ref TEXT DEFAULT '', label TEXT NOT NULL, result TEXT DEFAULT '', note TEXT, done INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, uuid TEXT, server_id INTEGER DEFAULT 0, server_hash TEXT DEFAULT '', dirty INTEGER DEFAULT 1)");
        db.execSQL("CREATE TABLE photos(id INTEGER PRIMARY KEY AUTOINCREMENT, revision_id INTEGER NOT NULL, kind TEXT DEFAULT 'working', uri TEXT NOT NULL, title TEXT, note TEXT, defect_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, uuid TEXT, server_id INTEGER DEFAULT 0, server_hash TEXT DEFAULT '', dirty INTEGER DEFAULT 1)");
        db.execSQL("CREATE TABLE defects(id INTEGER PRIMARY KEY AUTOINCREMENT, revision_id INTEGER NOT NULL, text TEXT NOT NULL, severity TEXT, status TEXT DEFAULT 'Neodstraněna', note TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, uuid TEXT, server_id INTEGER DEFAULT 0, server_hash TEXT DEFAULT '', dirty INTEGER DEFAULT 1)");
        db.execSQL("CREATE TABLE defect_photos(id INTEGER PRIMARY KEY AUTOINCREMENT, defect_id INTEGER NOT NULL, photo_id INTEGER NOT NULL, UNIQUE(defect_id,photo_id))");
        db.execSQL("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)");
        db.execSQL("CREATE TABLE sync_deletions(entity TEXT NOT NULL, uuid TEXT, server_id INTEGER, server_hash TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)");
        db.execSQL("CREATE TABLE inspection_catalog(id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT NOT NULL, label TEXT NOT NULL, source_ref TEXT DEFAULT '', note TEXT DEFAULT '', active INTEGER DEFAULT 1, UNIQUE(group_name,label))");
        createInfluenceTables(db);
        seedInspectionCatalog(db);
        createSyncTriggers(db);
        createIndexes(db);
        createSyncIndexes(db);
    }

    @Override public void onUpgrade(SQLiteDatabase db, int oldV, int newV) {
        if (oldV < 2) {
            db.execSQL("CREATE TABLE IF NOT EXISTS defect_photos(id INTEGER PRIMARY KEY AUTOINCREMENT, defect_id INTEGER NOT NULL, photo_id INTEGER NOT NULL, UNIQUE(defect_id,photo_id))");
        }
        if (oldV < 3) {
            createIndexes(db);
        }
        if (oldV < 4) {
            String[] syncTables = {"customers", "revisions", "measurements", "checklist", "photos", "defects"};
            for (String t : syncTables) {
                addColumnIfMissing(db, t, "uuid", "TEXT");
                addColumnIfMissing(db, t, "server_id", "INTEGER DEFAULT 0");
                addColumnIfMissing(db, t, "server_hash", "TEXT DEFAULT ''");
                addColumnIfMissing(db, t, "dirty", "INTEGER DEFAULT 1");
            }
            addColumnIfMissing(db, "measurements", "remote_kind", "TEXT DEFAULT ''");
            addColumnIfMissing(db, "photos", "updated_at", "TEXT");
            db.execSQL("CREATE TABLE IF NOT EXISTS sync_deletions(entity TEXT NOT NULL, uuid TEXT, server_id INTEGER, server_hash TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)");
            for (String t : syncTables) db.execSQL("UPDATE " + t + " SET uuid=lower(hex(randomblob(16))) WHERE uuid IS NULL OR uuid='' ");
            createSyncTriggers(db);
            createIndexes(db);
            createSyncIndexes(db);
        }
        if (oldV < 5) {
            addColumnIfMissing(db, "measurements", "row_type", "TEXT DEFAULT ''");
            addColumnIfMissing(db, "measurements", "item_key", "TEXT DEFAULT ''");
            addColumnIfMissing(db, "measurements", "parent_key", "TEXT DEFAULT ''");
            addColumnIfMissing(db, "checklist", "catalog_id", "INTEGER DEFAULT 0");
            addColumnIfMissing(db, "checklist", "group_name", "TEXT DEFAULT ''");
            addColumnIfMissing(db, "checklist", "source_ref", "TEXT DEFAULT ''");
            db.execSQL("CREATE TABLE IF NOT EXISTS inspection_catalog(id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT NOT NULL, label TEXT NOT NULL, source_ref TEXT DEFAULT '', note TEXT DEFAULT '', active INTEGER DEFAULT 1, UNIQUE(group_name,label))");
            db.execSQL("UPDATE measurements SET row_type=CASE " +
                    "WHEN UPPER(measure_type) IN ('CIRCUIT','POINT','CONTINUITY','RCD','RCBO','GROUP','FUNCTION','NOTE','BLANK','MEASUREMENT') THEN UPPER(measure_type) " +
                    "WHEN remote_kind='CIRCUIT' THEN 'CIRCUIT' WHEN remote_kind='MACHINE' THEN 'MEASUREMENT' ELSE 'MEASUREMENT' END " +
                    "WHERE row_type IS NULL OR row_type=''");
            seedInspectionCatalog(db);
        }
        if (oldV < 6) createInfluenceTables(db);
    }

    private void createInfluenceTables(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS influence_rooms(id INTEGER PRIMARY KEY AUTOINCREMENT, revision_id INTEGER NOT NULL, name TEXT NOT NULL, description TEXT DEFAULT '', updated_at TEXT DEFAULT CURRENT_TIMESTAMP)");
        db.execSQL("CREATE TABLE IF NOT EXISTS influence_items(id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER NOT NULL, code TEXT NOT NULL, description TEXT DEFAULT '', measure TEXT DEFAULT '', updated_at TEXT DEFAULT CURRENT_TIMESTAMP)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_influence_rooms_revision ON influence_rooms(revision_id)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_influence_items_room ON influence_items(room_id)");
    }

    public List<Row> influenceRooms(long revisionId) {
        List<Row> result = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery("SELECT id,name,description FROM influence_rooms WHERE revision_id=? ORDER BY id", new String[]{String.valueOf(revisionId)});
        while (c.moveToNext()) { Row r = new Row(); r.put("id", String.valueOf(c.getLong(0))); r.put("name", c.getString(1)); r.put("description", c.getString(2)); result.add(r); }
        c.close(); return result;
    }

    public long saveInfluenceRoom(long revisionId, long id, String name, String description) {
        ContentValues v = new ContentValues(); v.put("revision_id", revisionId); v.put("name", name); v.put("description", description); v.put("updated_at", now());
        if (id > 0) { getWritableDatabase().update("influence_rooms", v, "id=? AND revision_id=?", new String[]{String.valueOf(id), String.valueOf(revisionId)}); return id; }
        return getWritableDatabase().insert("influence_rooms", null, v);
    }

    public List<Row> influenceItems(long roomId) {
        List<Row> result = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery("SELECT id,code,description,measure FROM influence_items WHERE room_id=? ORDER BY code,id", new String[]{String.valueOf(roomId)});
        while (c.moveToNext()) { Row r = new Row(); r.put("id", String.valueOf(c.getLong(0))); r.put("code", c.getString(1)); r.put("description", c.getString(2)); r.put("measure", c.getString(3)); result.add(r); }
        c.close(); return result;
    }

    public long saveInfluenceItem(long roomId, long id, String code, String description, String measure) {
        ContentValues v = new ContentValues(); v.put("room_id", roomId); v.put("code", code); v.put("description", description); v.put("measure", measure); v.put("updated_at", now());
        if (id > 0) { getWritableDatabase().update("influence_items", v, "id=? AND room_id=?", new String[]{String.valueOf(id), String.valueOf(roomId)}); return id; }
        return getWritableDatabase().insert("influence_items", null, v);
    }

    public void deleteInfluenceItem(long roomId, long id) {
        getWritableDatabase().delete("influence_items", "room_id=? AND id=?", new String[]{String.valueOf(roomId), String.valueOf(id)});
    }

    public void deleteInfluenceRoom(long revisionId, long id) {
        SQLiteDatabase db = getWritableDatabase(); db.beginTransaction();
        try {
            db.delete("influence_items", "room_id=? AND EXISTS (SELECT 1 FROM influence_rooms WHERE id=? AND revision_id=?)", new String[]{String.valueOf(id), String.valueOf(id), String.valueOf(revisionId)});
            db.delete("influence_rooms", "revision_id=? AND id=?", new String[]{String.valueOf(revisionId), String.valueOf(id)});
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    private void addColumnIfMissing(SQLiteDatabase db, String table, String name, String type) {
        Cursor c = db.rawQuery("PRAGMA table_info(" + table + ")", null);
        boolean found = false;
        while (c.moveToNext()) if (name.equals(c.getString(1))) { found = true; break; }
        c.close();
        if (!found) db.execSQL("ALTER TABLE " + table + " ADD COLUMN " + name + " " + type);
    }


    private void seedInspectionCatalog(SQLiteDatabase db) {
        String[][] rows = new String[][] {
            {"Všeobecně","Zařízení je používáno jen k účelu, pro který bylo určeno","ČSN 33 2000-6 ed. 2 čl. 6.4.2",""},
            {"Všeobecně","Odborné provedení práce a použití vhodného materiálu","ČSN 33 2000-6 ed. 2 čl. 6.4.2",""},
            {"Všeobecně","Elektrické zařízení a instalace jsou udržovány v odpovídajícím stavu","ČSN 33 2000-6 ed. 2 čl. 6.4.2",""},
            {"Všeobecně","Elektrické a neelektrické zařízení se vzájemně nepřípustně neovlivňují","ČSN 33 2000-6 ed. 2 čl. 6.4.2",""},
            {"Všeobecně","Zařízení odpovídá určeným vnějším vlivům a mechanickým namáháním","ČSN 33 2000-6 ed. 2 čl. 6.4.2; ČSN 33 2000-5-51",""},
            {"Ochrana před úrazem","Základní izolace živých částí je nepoškozená a účinná","ČSN 33 2000-4-41 ed. 3 příloha A čl. A.1",""},
            {"Ochrana před úrazem","Ochranné přepážky a kryty odpovídají prostoru a požadovanému krytí","ČSN 33 2000-4-41 ed. 3 příloha A čl. A.2",""},
            {"Ochrana před úrazem","Zábrany a ochrana polohou jsou provedeny v předepsaných vzdálenostech","ČSN 33 2000-4-41 ed. 3 příloha B čl. B.2, B.3",""},
            {"Ochrana před úrazem","Ochranné pospojování je provedeno v požadovaném rozsahu","ČSN 33 2000-4-41 ed. 3 čl. 411.3.1.2; ČSN 33 2000-5-54 ed. 3",""},
            {"Ochrana před úrazem","Doplňující ochranné pospojování je provedeno tam, kde je požadováno","ČSN 33 2000-4-41 ed. 3 čl. 415.2",""},
            {"Ochrana před úrazem","SELV/PELV - zdroj, oddělení obvodů a provedení odpovídají požadavkům","ČSN 33 2000-4-41 ed. 3 čl. 414",""},
            {"Ochrana před úrazem","FELV je použito pouze tam, kde je tento způsob přípustný","ČSN 33 2000-4-41 ed. 3 čl. 411.7",""},
            {"Ochrana před úrazem","Proudové chrániče jsou instalovány všude, kde jsou požadovány","ČSN 33 2000-4-41 ed. 3; příslušné části ČSN 33 2000",""},
            {"Ochrana před úrazem","Neživé části jsou spojeny s ochranným vodičem a odpovídající uzemňovací soustavou","ČSN 33 2000-4-41 ed. 3 čl. 411.3.1.1",""},
            {"Požární a tepelné účinky","Protipožární přepážky a těsnicí výplně jsou provedeny v požadovaných místech","ČSN 33 2000-6 ed. 2 čl. 6.4.2; ČSN 33 2000-5-52",""},
            {"Požární a tepelné účinky","Elektrická zařízení nevykazují známky nepřípustného přehřátí","ČSN 33 2000-6 ed. 2 čl. 6.4.2",""},
            {"Vedení a kabelové trasy","Vodiče a kabely nejsou mechanicky poškozeny","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Vedení a kabelové trasy","Vedení je provedeno přehledným způsobem a v odpovídajících instalačních zónách","ČSN 33 2130 ed. 4; ČSN 33 2000-5-52",""},
            {"Vedení a kabelové trasy","Vedení je řádně upevněno a chráněno před mechanickým poškozením","ČSN 33 2000-5-52",""},
            {"Vedení a kabelové trasy","Druhy, typy a průřezy vodičů odpovídají proudovému zatížení a způsobu uložení","ČSN 33 2000-5-52 ed. 2",""},
            {"Vedení a kabelové trasy","Vedení odpovídá vnějším vlivům, teplotám, chemickým a slunečním vlivům","ČSN 33 2000-5-51 ed. 3; ČSN 33 2000-5-52",""},
            {"Vedení a kabelové trasy","Silové a ostatní systémy jsou odděleny v požadovaném rozsahu","ČSN 33 2000-5-52",""},
            {"Vedení a kabelové trasy","Spoje a zakončení vodičů a kabelů jsou mechanicky a elektricky spolehlivé","ČSN 33 2000-5-52 ed. 2 kap. 526",""},
            {"Označení","Střední a ochranné vodiče jsou správně a nezaměnitelně označeny","ČSN 33 0165 ed. 2; ČSN EN IEC 60445",""},
            {"Označení","Obvody, jistící prvky, spínače a svorky jsou trvale a funkčně označeny","ČSN 33 2000-5-51 ed. 3 čl. 514",""},
            {"Označení","Jsou k dispozici požadovaná schémata, výstražné nápisy a další informace","ČSN 33 2000-5-51 ed. 3 čl. 514.5",""},
            {"Rozváděče","Výrobní štítek, dokumentace a prohlášení rozváděče jsou k dispozici","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Rozváděče","Rozváděč má odpovídající pracovní prostor a je bezpečně přístupný","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Rozváděče","Rozváděč je bezpečně upevněn a jeho kryty nejsou poškozeny","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Rozváděče","Stav krytu a IP kód odpovídají prostředí a použití","ČSN 33 2000-6 ed. 2 příloha F; ČSN EN 60529",""},
            {"Rozváděče","Hlavní vypínač je přítomen, vhodně označen a funkční","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Rozváděče","Ruční ovládání jističů a proudových chráničů je funkční","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Rozváděče","Vestavěné zkušební tlačítko RCD/AFDD vyvolá vybavení","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Rozváděče","SPD je instalována tam, kde je určeno, a indikace potvrzuje provozuschopný stav","ČSN 33 2000-6 ed. 2 příloha F; ČSN 33 2000-5-53",""},
            {"Rozváděče","Použité ochranné přístroje mají správný typ a jmenovité hodnoty","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Rozváděče","Připojení vodičů a přípojnic je řádně provedeno a zajištěno","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Odpojování a spínání","Odpojovače a prostředky pro nouzové odpojení jsou přítomny a v odpovídajícím stavu","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Odpojování a spínání","Odpojovací přístroje lze tam, kde je to požadováno, zajistit ve vypnuté poloze","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Odpojování a spínání","Odpojovací a spínací přístroje jsou jednoznačně identifikovány","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Odpojování a spínání","Prostředky nouzového odpojení jsou snadno přístupné a funkční","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Koncové obvody","Jednopólové spínací a ochranné přístroje jsou zapojeny pouze ve fázových/krajních vodičích","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Koncové obvody","Použité ochranné vodiče jsou vhodné pro charakter a provedení obvodu","ČSN 33 2000-6 ed. 2 příloha F; ČSN 33 2000-5-54",""},
            {"Koncové obvody","Je zajištěna koordinace mezi vodiči a ochranou před přetížením","ČSN 33 2000-6 ed. 2 příloha F",""},
            {"Koncové obvody","Zásuvkové a venkovní obvody mají doplňkovou ochranu RCD tam, kde je požadována","ČSN 33 2000-4-41 ed. 3; ČSN 33 2130 ed. 4",""},
            {"Uzemnění a pospojování","Uzemňovací přívod a jeho připojení jsou přítomny a přístupné","ČSN 33 2000-6 ed. 2 příloha F; ČSN 33 2000-5-54",""},
            {"Uzemnění a pospojování","Hlavní ochranná přípojnice/MET je provedena a přístupná","ČSN 33 2000-5-54 ed. 3",""},
            {"Uzemnění a pospojování","Vodiče hlavního ochranného pospojování mají odpovídající průřez a spoje","ČSN 33 2000-5-54 ed. 3",""},
            {"Ochranné a kontrolní přístroje","Volba, seřízení, selektivita a koordinace ochranných přístrojů odpovídá instalaci","ČSN 33 2000-5-53",""},
            {"Ochranné a kontrolní přístroje","Volba a umístění SPD odpovídá požadované koordinaci ochrany před přepětím","ČSN 33 2000-5-53; ČSN EN 62305-4",""},
            {"EMC","Provedení omezuje vznik nepřípustných elektromagnetických vlivů a velkých vodivých smyček","ČSN 33 2000-4-44 kap. 444",""},
            {"Provoz a údržba","Zařízení je přístupné pro bezpečné ovládání, značení, prohlídku a údržbu","ČSN 33 2000-5-51 ed. 3",""},
            {"Provoz a údržba","Nouzové STOP/bezpečnostní vypnutí je instalováno tam, kde je vyžadováno","ČSN 33 2000-6 ed. 2 čl. 6.4.2",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","a) Způsob, popřípadě stav ochrany před úrazem elektrickým proudem včetně měření vzdáleností, pokud jde zejména o ochranu přepážkami nebo kryty, zábranami nebo polohou","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","b) Použití protipožárních přepážek nebo jiných bezpečnostních opatření proti šíření ohně a ochrana před tepelnými účinky","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","c) Volba vodičů s ohledem na proudovou zatížitelnost a úbytek napětí","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","d) Volba, seřízení a stav ukazatelů ochranných a kontrolních prvků","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","e) Použití odpovídajících, vhodně umístěných a dostatečně oddělujících spínacích prvků","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","f) Volba elektrických zařízení a ochranných opatření s ohledem na vnější vlivy, oprávněnost zatřídění a označení prostorů z hlediska vnějších vlivů","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","g) Označení středních a ochranných vodičů","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","h) Vybavení schématy, varovnými nápisy a jinými podobnými informacemi požadovanými jinými právními předpisy nebo technickými normami","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","i) Označení obvodů, pojistek, spínačů, svorek","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","j) Odpovídající způsob spojení vodičů","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"NV 190/2022 Sb. – příloha č. 1, část A","k) Přístupnost z hlediska provozu a údržby","NV č. 190/2022 Sb., příloha č. 1, část A",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","a) Způsob ochrany před úrazem elektrickým proudem","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","b) Použití protipožárních přepážek a jiných opatření na ochranu před šířením ohně a před tepelnými účinky","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","c) Volba vodičů s ohledem na proudovou zatížitelnost a úbytek napětí","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","d) Volba, seřízení, selektivita a koordinace ochranných a kontrolních (monitorovacích) přístrojů","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","e) Výběr, umístění a instalace vhodných přepěťových ochran (SPD), kde je to určeno","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","f) Volba, umístění a instalace vhodných odpojovacích a spínacích přístrojů","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","g) Volba zařízení a ochranných opatření přiměřených k vnějším vlivům a mechanickým namáháním","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","h) Označení nulových a ochranných vodičů","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","i) Vybavení schématy, výstražnými nápisy nebo dalšími podobnými informacemi","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","j) Označení obvodů, nadproudových ochranných přístrojů, spínačů, svorek atd.","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","k) Odpovídající způsob zakončování a spojování kabelů a vodičů","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","l) Volba a instalace uzemnění, ochranných vodičů a jejich připojování","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","m) Přístupnost zařízení z hlediska jeho ovládání, značení a údržby","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","n) Opatření proti elektromagnetickému rušení","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","o) Zda neživé části jsou spojeny s uzemněním","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""},
            {"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F","p) Volba stavu elektrických vedení","ČSN 33 2000-6 ed. 2, čl. 6.4.2 / příloha F",""}
        };
        for (String[] r : rows) {
            ContentValues v = new ContentValues();
            v.put("group_name", r[0]); v.put("label", r[1]); v.put("source_ref", r[2]); v.put("note", r[3]); v.put("active", 1);
            db.insertWithOnConflict("inspection_catalog", null, v, SQLiteDatabase.CONFLICT_IGNORE);
        }
    }

    private void createSyncTriggers(SQLiteDatabase db) {
        String[] tables = {"customers", "revisions", "measurements", "checklist", "photos", "defects"};
        for (String t : tables) {
            db.execSQL("CREATE TRIGGER IF NOT EXISTS trg_" + t + "_sync_ins AFTER INSERT ON " + t +
                    " WHEN COALESCE((SELECT value FROM meta WHERE key='sync_import'),'0')<>'1' BEGIN " +
                    "UPDATE " + t + " SET uuid=COALESCE(NULLIF(uuid,''),lower(hex(randomblob(16)))), dirty=1 WHERE id=NEW.id; END");
            db.execSQL("CREATE TRIGGER IF NOT EXISTS trg_" + t + "_sync_upd AFTER UPDATE ON " + t +
                    " WHEN COALESCE((SELECT value FROM meta WHERE key='sync_import'),'0')<>'1' AND NEW.dirty=OLD.dirty BEGIN " +
                    "UPDATE " + t + " SET uuid=COALESCE(NULLIF(uuid,''),lower(hex(randomblob(16)))), dirty=1 WHERE id=NEW.id; END");
        }
        db.execSQL("CREATE TRIGGER IF NOT EXISTS trg_measurements_sync_del BEFORE DELETE ON measurements " +
                "WHEN OLD.server_id>0 AND COALESCE((SELECT value FROM meta WHERE key='sync_import'),'0')<>'1' BEGIN " +
                "INSERT INTO sync_deletions(entity,uuid,server_id,server_hash) VALUES('measurement',OLD.uuid,OLD.server_id,OLD.server_hash); END");
        db.execSQL("CREATE TRIGGER IF NOT EXISTS trg_defect_photos_sync_ins AFTER INSERT ON defect_photos " +
                "WHEN COALESCE((SELECT value FROM meta WHERE key='sync_import'),'0')<>'1' BEGIN UPDATE photos SET dirty=1 WHERE id=NEW.photo_id; END");
        db.execSQL("CREATE TRIGGER IF NOT EXISTS trg_defect_photos_sync_del AFTER DELETE ON defect_photos " +
                "WHEN COALESCE((SELECT value FROM meta WHERE key='sync_import'),'0')<>'1' BEGIN UPDATE photos SET dirty=1 WHERE id=OLD.photo_id; END");
    }

    private void createIndexes(SQLiteDatabase db) {
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_revisions_customer ON revisions(customer_id)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_measurements_revision ON measurements(revision_id)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_checklist_revision ON checklist(revision_id)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_photos_revision ON photos(revision_id)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_defects_revision ON defects(revision_id)");

    }

    private void createSyncIndexes(SQLiteDatabase db) {
        db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_server ON customers(server_id) WHERE server_id>0");
        db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS idx_revisions_server ON revisions(server_id) WHERE server_id>0");
        db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS idx_measurements_server ON measurements(remote_kind,server_id) WHERE server_id>0");
        db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS idx_checklist_server ON checklist(server_id) WHERE server_id>0");
        db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS idx_defects_server ON defects(server_id) WHERE server_id>0");
        db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_server ON photos(server_id) WHERE server_id>0");
    }

    private String now() {
        return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.ROOT).format(new Date());
    }

    public int countCustomers() { return scalarInt("SELECT COUNT(*) FROM customers", null); }
    public int countOpenRevisions() { return scalarInt("SELECT COUNT(*) FROM revisions WHERE status='Rozpracovaná'", null); }
    public int countMeasurements(long revisionId) { return scalarInt("SELECT COUNT(*) FROM measurements WHERE revision_id=?", new String[]{String.valueOf(revisionId)}); }
    public int countMeasurementsDone(long revisionId) { return scalarInt("SELECT COUNT(*) FROM measurements WHERE revision_id=? AND done=1", new String[]{String.valueOf(revisionId)}); }
    public int countChecklist(long revisionId) { return scalarInt("SELECT COUNT(*) FROM checklist WHERE revision_id=?", new String[]{String.valueOf(revisionId)}); }
    public int countChecklistDone(long revisionId) { return scalarInt("SELECT COUNT(*) FROM checklist WHERE revision_id=? AND done=1", new String[]{String.valueOf(revisionId)}); }
    public int countPhotos(long revisionId) { return scalarInt("SELECT COUNT(*) FROM photos WHERE revision_id=? AND kind='working'", new String[]{String.valueOf(revisionId)}); }
    public int countDefects(long revisionId) { return scalarInt("SELECT COUNT(*) FROM defects WHERE revision_id=?", new String[]{String.valueOf(revisionId)}); }
    public int defectPhotoCount(long defectId) { return scalarInt("SELECT COUNT(*) FROM defect_photos WHERE defect_id=?", new String[]{String.valueOf(defectId)}); }

    private int scalarInt(String sql, String[] args) {
        Cursor c = getReadableDatabase().rawQuery(sql, args);
        int n = c.moveToFirst() ? c.getInt(0) : 0;
        c.close();
        return n;
    }

    public long addCustomer(String name, String ico, String address, String contact, String note) {
        ContentValues v = new ContentValues();
        v.put("name", name); v.put("ico", ico); v.put("address", address); v.put("contact", contact); v.put("note", note); v.put("updated_at", now());
        return getWritableDatabase().insert("customers", null, v);
    }

    public void updateCustomer(long id, String name, String ico, String address, String contact, String note) {
        ContentValues v = new ContentValues();
        v.put("name", name); v.put("ico", ico); v.put("address", address); v.put("contact", contact); v.put("note", note); v.put("updated_at", now());
        getWritableDatabase().update("customers", v, "id=?", new String[]{String.valueOf(id)});
    }

    public List<Row> customers(String q) {
        List<Row> out = new ArrayList<>();
        String like = "%" + (q == null ? "" : q.trim()) + "%";
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT id,name,ico,address,contact,note FROM customers WHERE name LIKE ? OR ico LIKE ? OR address LIKE ? OR contact LIKE ? ORDER BY name COLLATE NOCASE",
                new String[]{like, like, like, like});
        while (c.moveToNext()) out.add(Row.customer(c));
        c.close();
        return out;
    }

    public Row customer(long id) {
        Cursor c = getReadableDatabase().rawQuery("SELECT id,name,ico,address,contact,note FROM customers WHERE id=?", new String[]{String.valueOf(id)});
        Row r = c.moveToFirst() ? Row.customer(c) : null;
        c.close();
        return r;
    }

    public long addRevision(long customerId, String no, String type, String objectName, String objectAddress) {
        ContentValues v = new ContentValues();
        v.put("customer_id", customerId); v.put("revision_no", no); v.put("revision_type", type); v.put("object_name", objectName); v.put("object_address", objectAddress); v.put("status", "Rozpracovaná"); v.put("updated_at", now());
        long id = getWritableDatabase().insert("revisions", null, v);
        return id;
    }

    public List<Row> revisions(long customerId) {
        List<Row> out = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery("SELECT id,revision_no,revision_type,object_name,object_address,status,note FROM revisions WHERE customer_id=? ORDER BY id DESC", new String[]{String.valueOf(customerId)});
        while (c.moveToNext()) out.add(Row.revision(c));
        c.close();
        return out;
    }

    public List<Row> openRevisions() {
        List<Row> out = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT r.id,r.revision_no,r.revision_type,r.object_name,r.object_address,r.status,r.note,r.customer_id,c.name FROM revisions r JOIN customers c ON c.id=r.customer_id WHERE r.status='Rozpracovaná' ORDER BY r.id DESC LIMIT 30", null);
        while (c.moveToNext()) out.add(Row.openRevision(c));
        c.close();
        return out;
    }

    public Row revision(long id) {
        Cursor c = getReadableDatabase().rawQuery("SELECT id,revision_no,revision_type,object_name,object_address,status,note,customer_id,source_revision_id FROM revisions WHERE id=?", new String[]{String.valueOf(id)});
        Row r = c.moveToFirst() ? Row.revisionFull(c) : null;
        c.close();
        return r;
    }

    public void updateRevision(long id, String no, String type, String obj, String addr, String status, String note) {
        ContentValues v = new ContentValues();
        v.put("revision_no", no); v.put("revision_type", type); v.put("object_name", obj); v.put("object_address", addr); v.put("status", status); v.put("note", note); v.put("updated_at", now());
        getWritableDatabase().update("revisions", v, "id=?", new String[]{String.valueOf(id)});
    }

    public long cloneRevision(long sourceId) {
        Row src = revision(sourceId);
        if (src == null) return -1;
        String no = src.get("revision_no");
        if (no == null) no = "";
        ContentValues rv = new ContentValues();
        rv.put("customer_id", src.longVal("customer_id"));
        rv.put("revision_no", no.isEmpty() ? "" : no + " - kopie");
        rv.put("revision_type", src.get("revision_type"));
        rv.put("object_name", src.get("object_name"));
        rv.put("object_address", src.get("object_address"));
        rv.put("status", "Rozpracovaná");
        rv.put("note", src.get("note"));
        rv.put("source_revision_id", sourceId);
        rv.put("updated_at", now());

        SQLiteDatabase db = getWritableDatabase();
        long dst = db.insert("revisions", null, rv);
        db.execSQL("INSERT INTO measurements(revision_id,element,measure_type,row_type,item_key,parent_key,v1,v2,v3,v4,unit1,unit2,unit3,unit4,note,done,sort_order,updated_at) SELECT ?,element,measure_type,row_type,'','',v1,v2,v3,v4,unit1,unit2,unit3,unit4,note,0,sort_order,datetime('now') FROM measurements WHERE revision_id=?", new Object[]{dst, sourceId});
        db.execSQL("INSERT INTO checklist(revision_id,catalog_id,group_name,source_ref,label,result,note,done,sort_order,updated_at) SELECT ?,catalog_id,group_name,source_ref,label,'',note,0,sort_order,datetime('now') FROM checklist WHERE revision_id=?", new Object[]{dst, sourceId});
        Cursor rooms = db.rawQuery("SELECT id,name,description FROM influence_rooms WHERE revision_id=?", new String[]{String.valueOf(sourceId)});
        while (rooms.moveToNext()) {
            ContentValues room = new ContentValues(); room.put("revision_id", dst); room.put("name", rooms.getString(1)); room.put("description", rooms.getString(2));
            long newRoom = db.insert("influence_rooms", null, room);
            db.execSQL("INSERT INTO influence_items(room_id,code,description,measure) SELECT ?,code,description,measure FROM influence_items WHERE room_id=?", new Object[]{newRoom, rooms.getLong(0)});
        }
        rooms.close();
        return dst;
    }

    private void seedChecklist(long revisionId, String type) {
        String[] generic = {
                "Identifikace zařízení a rozsahu revize",
                "Ochrana před úrazem elektrickým proudem",
                "Jištění, ochranné a spínací přístroje",
                "Vodiče, spoje a ochranné vodiče",
                "Označení obvodů, přístrojů a výstrahy",
                "Přístupnost, mechanický stav a krytí",
                "Dokumentace a návody",
                "Funkční ověření zařízení"
        };
        String[] electrical = {
                "NV 190/2022 A-a) Způsob / stav ochrany před úrazem elektrickým proudem včetně potřebných vzdáleností",
                "NV 190/2022 A-b) Protipožární přepážky a další opatření proti šíření ohně a tepelným účinkům",
                "NV 190/2022 A-c) Volba vodičů s ohledem na proudovou zatížitelnost a úbytek napětí",
                "NV 190/2022 A-d) Volba, seřízení a stav ochranných a kontrolních prvků",
                "NV 190/2022 A-e) Odpovídající spínací a oddělovací prvky",
                "NV 190/2022 A-f) Volba zařízení a ochranných opatření s ohledem na vnější vlivy",
                "NV 190/2022 A-g) Označení středních a ochranných vodičů",
                "NV 190/2022 A-h) Schémata, varovné nápisy a další požadované informace",
                "NV 190/2022 A-i) Označení obvodů, pojistek, spínačů a svorek",
                "NV 190/2022 A-j) Odpovídající způsob spojení vodičů",
                "NV 190/2022 A-k) Přístupnost z hlediska provozu a údržby",
                "ČSN 33 2000-6 6.4.2-a) Způsob ochrany před úrazem elektrickým proudem",
                "ČSN 33 2000-6 6.4.2-b) Protipožární přepážky a ochrana před šířením ohně a tepelnými účinky",
                "ČSN 33 2000-6 6.4.2-c) Volba vodičů s ohledem na proudovou zatížitelnost a úbytek napětí",
                "ČSN 33 2000-6 6.4.2-d) Volba, seřízení, selektivita a koordinace ochranných a kontrolních přístrojů",
                "ČSN 33 2000-6 6.4.2-e) Přepěťové ochrany SPD, kde jsou určeny",
                "ČSN 33 2000-6 6.4.2-f) Odpojovací a spínací přístroje",
                "ČSN 33 2000-6 6.4.2-g) Zařízení a ochranná opatření přiměřená vnějším vlivům a mechanickému namáhání",
                "ČSN 33 2000-6 6.4.2-h) Označení nulových a ochranných vodičů",
                "ČSN 33 2000-6 6.4.2-i) Schémata, výstražné nápisy a další informace",
                "ČSN 33 2000-6 6.4.2-j) Označení obvodů, nadproudových ochran, spínačů a svorek",
                "ČSN 33 2000-6 6.4.2-k) Zakončování a spojování kabelů a vodičů",
                "ČSN 33 2000-6 6.4.2-l) Uzemnění, ochranné vodiče a jejich připojování",
                "ČSN 33 2000-6 6.4.2-m) Přístupnost zařízení pro ovládání, značení a údržbu",
                "ČSN 33 2000-6 6.4.2-n) Opatření proti elektromagnetickému rušení",
                "ČSN 33 2000-6 6.4.2-o) Spojení neživých částí s uzemněním",
                "ČSN 33 2000-6 6.4.2-p) Volba a stav elektrických vedení"
        };
        String[] items = "ELEKTRO".equals(type) ? electrical : generic;
        SQLiteDatabase db = getWritableDatabase();
        for (int i = 0; i < items.length; i++) {
            ContentValues v = new ContentValues();
            v.put("revision_id", revisionId); v.put("label", items[i]); v.put("sort_order", i); v.put("updated_at", now());
            db.insert("checklist", null, v);
        }
    }

    public List<Row> measurements(long revisionId) {
        List<Row> out = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery("SELECT id,element,measure_type,row_type,item_key,parent_key,v1,v2,v3,v4,unit1,unit2,unit3,unit4,note,done,remote_kind,sort_order FROM measurements WHERE revision_id=? ORDER BY sort_order,id", new String[]{String.valueOf(revisionId)});
        while (c.moveToNext()) out.add(Row.measurement(c));
        c.close();
        return out;
    }

    public String ensureMeasurementKey(long id) {
        Cursor c = getReadableDatabase().rawQuery("SELECT item_key FROM measurements WHERE id=?", new String[]{String.valueOf(id)});
        String key = c.moveToFirst() && !c.isNull(0) ? c.getString(0) : "";
        c.close();
        if (key == null || key.trim().isEmpty()) {
            key = "mobile-" + java.util.UUID.randomUUID().toString();
            ContentValues v = new ContentValues(); v.put("item_key", key); v.put("updated_at", now());
            getWritableDatabase().update("measurements", v, "id=?", new String[]{String.valueOf(id)});
        }
        return key;
    }

    public long saveMeasurement(long revisionId, long id, String element, String type, String rowType, String parentKey, String[] values, String[] units, String note, boolean done) {
        ContentValues v = new ContentValues();
        v.put("revision_id", revisionId); v.put("element", element); v.put("measure_type", type);
        v.put("row_type", rowType == null ? "" : rowType); v.put("parent_key", parentKey == null ? "" : parentKey);
        for (int i = 0; i < 4; i++) { v.put("v" + (i + 1), values[i]); v.put("unit" + (i + 1), units[i]); }
        v.put("note", note); v.put("done", done ? 1 : 0); v.put("updated_at", now());
        if (id > 0) { getWritableDatabase().update("measurements", v, "id=?", new String[]{String.valueOf(id)}); ensureMeasurementKey(id); return id; }
        v.put("item_key", "mobile-" + java.util.UUID.randomUUID().toString());
        int pos = scalarInt("SELECT COALESCE(MAX(sort_order),0)+1 FROM measurements WHERE revision_id=?", new String[]{String.valueOf(revisionId)});
        v.put("sort_order", pos);
        return getWritableDatabase().insert("measurements", null, v);
    }

    public void setMeasurementDone(long id, boolean done) {
        ContentValues v = new ContentValues(); v.put("done", done ? 1 : 0); v.put("updated_at", now());
        getWritableDatabase().update("measurements", v, "id=?", new String[]{String.valueOf(id)});
    }

    public void bulkMeasurement(List<Long> ids, String[] values, String note, Boolean done) {
        SQLiteDatabase db = getWritableDatabase();
        for (long id : ids) {
            ContentValues v = new ContentValues();
            for (int i = 0; i < 4; i++) if (values[i] != null && !values[i].isEmpty()) v.put("v" + (i + 1), values[i]);
            if (note != null && !note.isEmpty()) v.put("note", note);
            if (done != null) v.put("done", done ? 1 : 0);
            v.put("updated_at", now());
            db.update("measurements", v, "id=?", new String[]{String.valueOf(id)});
        }
    }

    public void deleteMeasurement(long id) { getWritableDatabase().delete("measurements", "id=?", new String[]{String.valueOf(id)}); }

    public List<Row> checklist(long revisionId) {
        List<Row> out = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery("SELECT id,label,result,note,done,catalog_id,group_name,source_ref,sort_order FROM checklist WHERE revision_id=? ORDER BY group_name,sort_order,id", new String[]{String.valueOf(revisionId)});
        while (c.moveToNext()) out.add(Row.checklist(c));
        c.close();
        return out;
    }

    public void updateChecklist(long id, boolean done, String result, String note) {
        ContentValues v = new ContentValues();
        v.put("done", done ? 1 : 0); v.put("result", result); v.put("note", note); v.put("updated_at", now());
        getWritableDatabase().update("checklist", v, "id=?", new String[]{String.valueOf(id)});
    }

    public void addChecklist(long revisionId, String label) {
        ContentValues v = new ContentValues(); v.put("revision_id", revisionId); v.put("label", label); v.put("group_name", "Vlastní"); v.put("updated_at", now());
        v.put("sort_order", scalarInt("SELECT COALESCE(MAX(sort_order),0)+1 FROM checklist WHERE revision_id=?", new String[]{String.valueOf(revisionId)}));
        getWritableDatabase().insert("checklist", null, v);
    }

    public List<Row> inspectionCatalog(String query) {
        List<Row> out = new ArrayList<>();
        String q = "%" + (query == null ? "" : query.trim()) + "%";
        Cursor c = getReadableDatabase().rawQuery("SELECT id,group_name,label,source_ref,note FROM inspection_catalog WHERE active=1 AND (group_name LIKE ? OR label LIKE ? OR source_ref LIKE ?) ORDER BY group_name,id LIMIT 250", new String[]{q,q,q});
        while (c.moveToNext()) out.add(Row.catalog(c));
        c.close();
        return out;
    }

    public boolean checklistHasCatalog(long revisionId, long catalogId) {
        if (catalogId <= 0) return false;
        return scalarInt("SELECT COUNT(*) FROM checklist WHERE revision_id=? AND catalog_id=?", new String[]{String.valueOf(revisionId),String.valueOf(catalogId)}) > 0;
    }

    public long addChecklistFromCatalog(long revisionId, long catalogId) {
        Cursor c = getReadableDatabase().rawQuery("SELECT group_name,label,source_ref,note FROM inspection_catalog WHERE id=? AND active=1", new String[]{String.valueOf(catalogId)});
        if (!c.moveToFirst()) { c.close(); return -1; }
        String group=c.getString(0), label=c.getString(1), source=c.getString(2), note=c.getString(3); c.close();
        if (checklistHasCatalog(revisionId,catalogId)) return 0;
        ContentValues v=new ContentValues(); v.put("revision_id",revisionId);v.put("catalog_id",catalogId);v.put("group_name",group);v.put("source_ref",source);v.put("label",label);v.put("note",note);v.put("result","NEPROVEDENO");v.put("done",0);v.put("updated_at",now());
        v.put("sort_order",scalarInt("SELECT COALESCE(MAX(sort_order),0)+1 FROM checklist WHERE revision_id=?",new String[]{String.valueOf(revisionId)}));
        return getWritableDatabase().insert("checklist",null,v);
    }

    public int addChecklistGroup(long revisionId, String groupName) {
        int added=0; Cursor c=getReadableDatabase().rawQuery("SELECT id FROM inspection_catalog WHERE active=1 AND group_name=? ORDER BY id",new String[]{groupName});
        while(c.moveToNext()) if(addChecklistFromCatalog(revisionId,c.getLong(0))>0) added++;
        c.close(); return added;
    }

    public long addPhoto(long revisionId, String uri, String title, String note) {
        ContentValues v = new ContentValues();
        v.put("revision_id", revisionId); v.put("kind", "working"); v.put("uri", uri); v.put("title", title); v.put("note", note); v.put("updated_at", now());
        return getWritableDatabase().insert("photos", null, v);
    }

    public List<Row> photos(long revisionId) {
        List<Row> out = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery("SELECT id,uri,title,note,kind,defect_id FROM photos WHERE revision_id=? AND kind='working' ORDER BY id DESC", new String[]{String.valueOf(revisionId)});
        while (c.moveToNext()) out.add(Row.photo(c));
        c.close();
        return out;
    }

    public void updatePhoto(long id, String title, String note) {
        ContentValues v = new ContentValues(); v.put("title", title); v.put("note", note); v.put("updated_at", now());
        getWritableDatabase().update("photos", v, "id=?", new String[]{String.valueOf(id)});
    }

    public void linkPhotoToDefect(long photoId, long defectId) {
        ContentValues v = new ContentValues(); v.put("defect_id", defectId); v.put("photo_id", photoId);
        getWritableDatabase().insertWithOnConflict("defect_photos", null, v, SQLiteDatabase.CONFLICT_IGNORE);
    }

    public int linkedDefectCount(long photoId) { return scalarInt("SELECT COUNT(*) FROM defect_photos WHERE photo_id=?", new String[]{String.valueOf(photoId)}); }

    public long addDefect(long revisionId, String text, String severity, String status, String note) {
        ContentValues v = new ContentValues();
        v.put("revision_id", revisionId); v.put("text", text); v.put("severity", severity); v.put("status", status); v.put("note", note); v.put("updated_at", now());
        return getWritableDatabase().insert("defects", null, v);
    }

    public void updateDefect(long id, String text, String severity, String status, String note) {
        ContentValues v = new ContentValues();
        v.put("text", text); v.put("severity", severity); v.put("status", status); v.put("note", note); v.put("updated_at", now());
        getWritableDatabase().update("defects", v, "id=?", new String[]{String.valueOf(id)});
    }

    public List<Row> defects(long revisionId) {
        List<Row> out = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery("SELECT id,text,severity,status,note FROM defects WHERE revision_id=? ORDER BY id", new String[]{String.valueOf(revisionId)});
        while (c.moveToNext()) out.add(Row.defect(c));
        c.close();
        return out;
    }

    public JSONObject exportAll() throws Exception {
        JSONObject root = new JSONObject();
        root.put("format", "PZ-REVIZE-Mobile"); root.put("version", 3);
        root.put("customers", tableToJson("SELECT * FROM customers"));
        root.put("revisions", tableToJson("SELECT * FROM revisions"));
        root.put("measurements", tableToJson("SELECT * FROM measurements"));
        root.put("checklist", tableToJson("SELECT * FROM checklist"));
        root.put("photos", tableToJson("SELECT * FROM photos"));
        root.put("defects", tableToJson("SELECT * FROM defects"));
        root.put("defect_photos", tableToJson("SELECT * FROM defect_photos"));
        root.put("influence_rooms", tableToJson("SELECT * FROM influence_rooms"));
        root.put("influence_items", tableToJson("SELECT * FROM influence_items"));
        return root;
    }

    private JSONArray tableToJson(String sql) throws Exception {
        JSONArray arr = new JSONArray();
        Cursor c = getReadableDatabase().rawQuery(sql, null);
        while (c.moveToNext()) {
            JSONObject o = new JSONObject();
            for (int i = 0; i < c.getColumnCount(); i++) {
                String n = c.getColumnName(i);
                if (c.isNull(i)) o.put(n, JSONObject.NULL);
                else if (c.getType(i) == Cursor.FIELD_TYPE_INTEGER) o.put(n, c.getLong(i));
                else o.put(n, c.getString(i));
            }
            arr.put(o);
        }
        c.close();
        return arr;
    }

    public void replaceAll(JSONObject root) throws Exception {
        if (!"PZ-REVIZE-Mobile".equals(root.optString("format"))) throw new IllegalArgumentException("Soubor není záloha PZ-REVIZE Mobile.");
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            ContentValues syncFlag = new ContentValues(); syncFlag.put("key", "sync_import"); syncFlag.put("value", "1");
            db.insertWithOnConflict("meta", null, syncFlag, SQLiteDatabase.CONFLICT_REPLACE);
            db.delete("sync_deletions", null, null);
            String[] tables = {"influence_items", "influence_rooms", "defect_photos", "photos", "defects", "checklist", "measurements", "revisions", "customers"};
            for (String t : tables) db.delete(t, null, null);
            importArray(db, "customers", root.optJSONArray("customers"));
            importArray(db, "revisions", root.optJSONArray("revisions"));
            importArray(db, "measurements", root.optJSONArray("measurements"));
            importArray(db, "checklist", root.optJSONArray("checklist"));
            importArray(db, "defects", root.optJSONArray("defects"));
            importArray(db, "photos", root.optJSONArray("photos"));
            importArray(db, "defect_photos", root.optJSONArray("defect_photos"));
            importArray(db, "influence_rooms", root.optJSONArray("influence_rooms"));
            importArray(db, "influence_items", root.optJSONArray("influence_items"));
            ContentValues syncFlagOff = new ContentValues(); syncFlagOff.put("key", "sync_import"); syncFlagOff.put("value", "0");
            db.insertWithOnConflict("meta", null, syncFlagOff, SQLiteDatabase.CONFLICT_REPLACE);
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
    }

    private void importArray(SQLiteDatabase db, String table, JSONArray a) throws Exception {
        if (a == null) return;
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.getJSONObject(i);
            ContentValues v = new ContentValues();
            java.util.Iterator<String> it = o.keys();
            while (it.hasNext()) {
                String k = it.next();
                if (o.isNull(k)) v.putNull(k);
                else {
                    Object x = o.get(k);
                    if (x instanceof Number) v.put(k, ((Number) x).longValue()); else v.put(k, String.valueOf(x));
                }
            }
            db.insertOrThrow(table, null, v);
        }
    }

    public static class Row extends java.util.HashMap<String, String> {
        long id;
        public long id() { return id; }
        public long longVal(String k) { try { return Long.parseLong(get(k)); } catch (Exception e) { return 0; } }
        public boolean bool(String k) { return "1".equals(get(k)); }

        static Row from(Cursor c, String[] cols) {
            Row r = new Row(); r.id = c.getLong(0);
            for (int i = 1; i < cols.length; i++) r.put(cols[i], c.isNull(i) ? "" : c.getString(i));
            return r;
        }

        static Row customer(Cursor c) { return from(c, new String[]{"id", "name", "ico", "address", "contact", "note"}); }
        static Row revision(Cursor c) { return from(c, new String[]{"id", "revision_no", "revision_type", "object_name", "object_address", "status", "note"}); }
        static Row revisionFull(Cursor c) { return from(c, new String[]{"id", "revision_no", "revision_type", "object_name", "object_address", "status", "note", "customer_id", "source_revision_id"}); }
        static Row openRevision(Cursor c) { return from(c, new String[]{"id", "revision_no", "revision_type", "object_name", "object_address", "status", "note", "customer_id", "customer_name"}); }
        static Row measurement(Cursor c) { return from(c, new String[]{"id", "element", "measure_type", "row_type", "item_key", "parent_key", "v1", "v2", "v3", "v4", "unit1", "unit2", "unit3", "unit4", "note", "done", "remote_kind", "sort_order"}); }
        static Row checklist(Cursor c) { return from(c, new String[]{"id", "label", "result", "note", "done", "catalog_id", "group_name", "source_ref", "sort_order"}); }
        static Row photo(Cursor c) { return from(c, new String[]{"id", "uri", "title", "note", "kind", "defect_id"}); }
        static Row defect(Cursor c) { return from(c, new String[]{"id", "text", "severity", "status", "note"}); }
        static Row catalog(Cursor c) { return from(c, new String[]{"id", "group_name", "label", "source_ref", "note"}); }
    }
}
