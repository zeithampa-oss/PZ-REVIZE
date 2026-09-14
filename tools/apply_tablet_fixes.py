from pathlib import Path
import runpy
import json

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "source/android/app/src/main/java/cz/pzrevize/mobile/MainActivity.java"
DB = ROOT / "source/android/app/src/main/java/cz/pzrevize/mobile/Db.java"
CAT = ROOT / "source/android/app/src/main/java/cz/pzrevize/mobile/InfluenceCatalog.java"
VV_PY = ROOT / "source/windows/pzrevize/external_influences.py"


def replace_once(text, old, new, label):
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Patch not found: {label}")
    return text.replace(old, new, 1)


def java_string(s):
    s = "" if s is None else str(s)
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\r', '').replace('\n', '\\n')

# Build Android VV checklist from the audited Windows catalog so both clients use one source.
ns = runpy.run_path(str(VV_PY))
meta = ns.get("INFLUENCE_META", {})
catalog = None
for value in ns.values():
    if isinstance(value, dict) and value:
        vals = list(value.values())
        if all(isinstance(v, list) for v in vals):
            sample = next((x for v in vals for x in v if isinstance(x, dict) and "code" in x), None)
            if sample:
                catalog = value
                break
if not catalog:
    raise SystemExit("VV catalog not found")

entries = []
for prefix, rows in catalog.items():
    title = meta.get(prefix, {}).get("name", prefix) if isinstance(meta, dict) else prefix
    for r in rows:
        if not isinstance(r, dict) or not r.get("code"):
            continue
        entries.append((str(prefix), str(title), str(r.get("code", "")), str(r.get("label", "")), str(r.get("requirement", ""))))

lines = [
    "package cz.pzrevize.mobile;",
    "",
    "final class InfluenceCatalog {",
    "    private InfluenceCatalog() {}",
    "    static final String[][] ITEMS = new String[][] {",
]
for prefix, title, code, label, req in entries:
    lines.append(f'        {{"{java_string(prefix)}", "{java_string(title)}", "{java_string(code)}", "{java_string(label)}", "{java_string(req)}"}},')
lines += ["    };", "}", ""]
CAT.write_text("\n".join(lines), encoding="utf-8")

# Database: automatic document numbering.
db = DB.read_text(encoding="utf-8")
old = '''    public long addRevision(long customerId, String no, String type, String objectName, String objectAddress) {
        ContentValues v = new ContentValues();
        v.put("customer_id", customerId); v.put("revision_no", no); v.put("revision_type", type); v.put("object_name", objectName); v.put("object_address", objectAddress); v.put("status", "Rozpracovaná"); v.put("updated_at", now());
        long id = getWritableDatabase().insert("revisions", null, v);
        return id;
    }
'''
new = '''    public String nextRevisionNumber(String type) {
        String prefix = "VNEJSI".equalsIgnoreCase(type) ? "VV" : "RZ";
        String year = new SimpleDateFormat("yyyy", Locale.getDefault()).format(new Date());
        int max = 0;
        Cursor c = getReadableDatabase().rawQuery("SELECT revision_no FROM revisions WHERE revision_no IS NOT NULL AND revision_no<>''", null);
        while (c.moveToNext()) {
            String no = c.getString(0);
            if (no == null) continue;
            String normalized = no.trim().toUpperCase(Locale.ROOT);
            if (!normalized.startsWith(prefix + "-" + year + "-")) continue;
            int pos = normalized.lastIndexOf('-');
            if (pos >= 0 && pos + 1 < normalized.length()) {
                try { max = Math.max(max, Integer.parseInt(normalized.substring(pos + 1))); } catch (Exception ignored) { }
            }
        }
        c.close();
        return String.format(Locale.ROOT, "%s-%s-%03d", prefix, year, max + 1);
    }

    public long addRevision(long customerId, String no, String type, String objectName, String objectAddress) {
        if (no == null || no.trim().isEmpty()) no = nextRevisionNumber(type);
        ContentValues v = new ContentValues();
        v.put("customer_id", customerId); v.put("revision_no", no); v.put("revision_type", type); v.put("object_name", objectName); v.put("object_address", objectAddress); v.put("status", "Rozpracovaná"); v.put("updated_at", now());
        long id = getWritableDatabase().insert("revisions", null, v);
        return id;
    }
'''
db = replace_once(db, old, new, "automatic numbering")
DB.write_text(db, encoding="utf-8")

src = JAVA.read_text(encoding="utf-8")

# Tablet detection must work in portrait too.
src = replace_once(src, '''        return config.orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE
                && config.screenWidthDp >= 840;''', '''        return config.screenWidthDp >= 720;''', "tablet detection")

# Slightly narrower rail gives measurements more useful width.
src = src.replace('workspace.addView(railScroll, new LinearLayout.LayoutParams(dp(204), ViewGroup.LayoutParams.MATCH_PARENT));',
                  'workspace.addView(railScroll, new LinearLayout.LayoutParams(dp(176), ViewGroup.LayoutParams.MATCH_PARENT));')

# Create revision/VV without manual number entry.
src = replace_once(src,
'''        EditText no = field(l, vv ? "Číslo protokolu VV" : "Číslo revize", "");
        Spinner type = vv ? null : spinner(l, "Typ revize", new String[]{"ELEKTRO", "STROJ", "LPS"}, 0);''',
'''        TextView autoNo = text("Číslo bude přiděleno automaticky při založení.", 13, C_GREEN, true);
        autoNo.setPadding(dp(2), dp(6), 0, dp(8));
        l.addView(autoNo);
        Spinner type = vv ? null : spinner(l, "Typ revize", new String[]{"ELEKTRO", "STROJ", "LPS"}, 0);''',
"revision number field")
src = src.replace('revisionId = db.addRevision(customerId, s(no), selectedType, s(obj), s(addr));',
                  'revisionId = db.addRevision(customerId, "", selectedType, s(obj), s(addr));')

# Replace manual VV code entry with a real checklist.
src = replace_once(src,
'        detail.addView(smallButton("＋ PŘIDAT KÓD VLIVU", C_ORANGE, C_TEXT, v -> influenceItemDialog(room.id(), null)), marginBottom(dp(12)));',
'        detail.addView(smallButton("☑ VYBRAT VNĚJŠÍ VLIVY", C_ORANGE, C_TEXT, v -> influenceChecklistDialog(room.id())), marginBottom(dp(12)));',
"VV add button")

marker = '    private void influenceItemDialog(long roomId, Db.Row row) {'
if 'private void influenceChecklistDialog(long roomId)' not in src:
    method = '''    private void influenceChecklistDialog(long roomId) {
        List<Db.Row> existing = db.influenceItems(roomId);
        Map<String, Db.Row> byCode = new LinkedHashMap<>();
        for (Db.Row r : existing) byCode.put(r.get("code").toUpperCase(Locale.ROOT), r);

        String[] labels = new String[InfluenceCatalog.ITEMS.length];
        boolean[] checked = new boolean[InfluenceCatalog.ITEMS.length];
        for (int i = 0; i < InfluenceCatalog.ITEMS.length; i++) {
            String[] x = InfluenceCatalog.ITEMS[i];
            labels[i] = x[2] + "  •  " + x[3];
            checked[i] = byCode.containsKey(x[2].toUpperCase(Locale.ROOT));
        }

        AlertDialog dlg = new AlertDialog.Builder(this)
                .setTitle("Vnější vlivy – checklist")
                .setMultiChoiceItems(labels, checked, (d, which, isChecked) -> checked[which] = isChecked)
                .setNegativeButton("Zrušit", null)
                .setPositiveButton("Uložit výběr", null)
                .create();
        dlg.setOnShowListener(x -> dlg.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            Set<String> selected = new HashSet<>();
            for (int i = 0; i < InfluenceCatalog.ITEMS.length; i++) {
                String[] item = InfluenceCatalog.ITEMS[i];
                String code = item[2].toUpperCase(Locale.ROOT);
                if (checked[i]) {
                    selected.add(code);
                    Db.Row old = byCode.get(code);
                    db.saveInfluenceItem(roomId, old == null ? 0 : old.id(), item[2], item[3], item[4]);
                }
            }
            for (Db.Row old : existing) {
                String code = old.get("code").toUpperCase(Locale.ROOT);
                boolean catalogCode = false;
                for (String[] item : InfluenceCatalog.ITEMS) if (item[2].equalsIgnoreCase(code)) { catalogCode = true; break; }
                if (catalogCode && !selected.contains(code)) db.deleteInfluenceItem(roomId, old.id());
            }
            dlg.dismiss();
            showInfluences(false);
        }));
        dlg.show();
    }

'''
    src = src.replace(marker, method + marker, 1)

# Keep manual edit only for an already selected influence, not for entering codes from scratch.
src = src.replace('new AlertDialog.Builder(this).setTitle(row == null ? "Vnější vliv" : "Upravit vnější vliv")',
                  'new AlertDialog.Builder(this).setTitle(row == null ? "Vnější vliv – ruční doplnění" : "Upravit vnější vliv")')

# Compact tablet measurement rows.
src = src.replace('new LinearLayout.LayoutParams(0, dp(46), 4)', 'new LinearLayout.LayoutParams(0, dp(40), 4)')
src = src.replace('new LinearLayout.LayoutParams(0, dp(46), 2)', 'new LinearLayout.LayoutParams(0, dp(40), 2)')
src = src.replace('new LinearLayout.LayoutParams(0, dp(46), 1)', 'new LinearLayout.LayoutParams(0, dp(40), 1)')
src = src.replace('row.setPadding(dp(8), dp(6), dp(8), dp(6));', 'row.setPadding(dp(7), dp(3), dp(7), dp(3));')

# Sync failure: explicit escape, retry and settings. Automatic sync remains non-modal.
old_sync = '''                AlertDialog.Builder dialog = new AlertDialog.Builder(this)
                        .setTitle(r.ok ? (r.conflicts > 0 ? "Synchronizace s konfliktem" : "Synchronizace dokončena") : "Synchronizace selhala")
                        .setMessage(r.message + ((r.ok && r.conflicts == 0) ? "" : "\\n\\nPráce může pokračovat offline. Neodeslané změny zůstávají v tabletu a další synchronizace je zkusí znovu."))
                        .setPositiveButton("Pokračovat offline", null);
                if (!r.ok || r.conflicts > 0) dialog.setNeutralButton("Nastavení NAS", (d,w) -> syncSettingsDialog());
                dialog.show();'''
new_sync = '''                AlertDialog.Builder dialog = new AlertDialog.Builder(this)
                        .setTitle(r.ok ? (r.conflicts > 0 ? "Synchronizace s konfliktem" : "Synchronizace dokončena") : "Synchronizace selhala")
                        .setMessage(r.message + ((r.ok && r.conflicts == 0) ? "" : "\\n\\nMůžeš ihned pokračovat offline. Lokální data se nemažou."))
                        .setPositiveButton("Zavřít a pokračovat", null)
                        .setCancelable(true);
                if (!r.ok || r.conflicts > 0) {
                    dialog.setNeutralButton("Nastavení NAS", (d,w) -> syncSettingsDialog());
                    dialog.setNegativeButton("Zkusit znovu", (d,w) -> startSync(true, false));
                }
                dialog.show();'''
src = replace_once(src, old_sync, new_sync, "sync escape")

# Add direct offline action to sync menu.
src = replace_once(src,
'''                "Nastavení NAS",
                "Záloha / přenos dat"
        };''',
'''                "Nastavení NAS",
                "Pracovat offline – vypnout automatický sync",
                "Záloha / přenos dat"
        };''',
"sync menu offline")
src = replace_once(src,
'''            else if (which == 2) syncSettingsDialog();
            else backupMenu();''',
'''            else if (which == 2) syncSettingsDialog();
            else if (which == 3) {
                SyncClient.prefs(this).edit().putBoolean("auto_sync", false).apply();
                Toast.makeText(this, "Automatická synchronizace vypnuta. Práce pokračuje offline.", Toast.LENGTH_LONG).show();
                if ("home".equals(screen)) showHome(false);
            } else backupMenu();''',
"sync menu handler")

# Ensure Locale is available for checklist normalization.
if 'import java.util.Locale;' not in src:
    src = src.replace('import java.util.List;\n', 'import java.util.List;\nimport java.util.Locale;\n')

JAVA.write_text(src, encoding="utf-8")
print(f"Patched Android; generated {len(entries)} VV checklist entries")
