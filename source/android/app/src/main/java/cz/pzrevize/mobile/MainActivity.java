package cz.pzrevize.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentValues;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class MainActivity extends Activity {
    private static final int C_BG = Color.rgb(244, 246, 248);
    private static final int C_TEXT = Color.rgb(27, 35, 45);
    private static final int C_MUTED = Color.rgb(104, 115, 128);
    private static final int C_DARK = Color.rgb(20, 20, 20);
    private static final int C_ORANGE = Color.rgb(245, 158, 11);
    private static final int C_GREEN = Color.rgb(22, 163, 74);
    private static final int C_RED = Color.rgb(185, 28, 28);
    private static final int C_BORDER = Color.rgb(217, 222, 228);

    private static final int REQ_CAMERA = 201;
    private static final int REQ_EXPORT = 202;
    private static final int REQ_IMPORT = 203;
    private static final int REQ_STORAGE = 204;

    private Db db;
    private LinearLayout root;
    private LinearLayout body;
    private TextView headerTitle;
    private TextView headerSub;
    private Button backButton;

    private long customerId = 0;
    private long revisionId = 0;
    private String screen = "home";
    private final ArrayDeque<String> history = new ArrayDeque<>();
    private final Set<Long> selectedMeasurements = new HashSet<>();
    private final Set<String> collapsedMeasurementNodes = new HashSet<>();
    private long selectedChecklistId = 0;
    private long selectedMeasurementId = 0;
    private long selectedRoomId = 0;
    private LinearLayout navigationRail;
    private Uri pendingPhotoUri;
    private Handler syncHandler;
    private boolean syncRunning = false;
    private final Runnable periodicSync = new Runnable() {
        @Override public void run() {
            if (SyncClient.autoSync(MainActivity.this) && SyncClient.configured(MainActivity.this)) startSync(false, false);
            if (syncHandler != null) syncHandler.postDelayed(this, 30000);
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (Build.VERSION.SDK_INT >= 21) {
            getWindow().setStatusBarColor(C_DARK);
            getWindow().setNavigationBarColor(Color.WHITE);
        }
        db = new Db(this);
        syncHandler = new Handler(Looper.getMainLooper());
        if (state != null) {
            customerId = state.getLong("customer_id"); revisionId = state.getLong("revision_id");
            selectedChecklistId = state.getLong("checklist_id"); selectedMeasurementId = state.getLong("measurement_id");
            selectedRoomId = state.getLong("room_id"); screen = state.getString("screen", "home");
        }
        buildShell();
        if (revisionId > 0 && db.revision(revisionId) == null) { revisionId = 0; screen = "home"; }
        renderCurrent();
    }

    @Override protected void onSaveInstanceState(Bundle out) {
        out.putLong("customer_id", customerId); out.putLong("revision_id", revisionId);
        out.putLong("checklist_id", selectedChecklistId); out.putLong("measurement_id", selectedMeasurementId);
        out.putLong("room_id", selectedRoomId); out.putString("screen", screen);
        super.onSaveInstanceState(out);
    }

    @Override protected void onResume() {
        super.onResume();
        if (syncHandler != null) { syncHandler.removeCallbacks(periodicSync); syncHandler.postDelayed(periodicSync, 30000); }
        if (SyncClient.autoSync(this) && SyncClient.configured(this)) startSync(false, false);
    }

    @Override protected void onPause() {
        super.onPause();
        if (SyncClient.autoSync(this) && SyncClient.configured(this)) startSync(false, true);
    }

    @Override protected void onDestroy() {
        if (syncHandler != null) syncHandler.removeCallbacks(periodicSync);
        super.onDestroy();
    }

    @Override public void onBackPressed() {
        if (!history.isEmpty()) {
            goBack();
            return;
        }
        if (!"home".equals(screen)) {
            showHome(true);
            return;
        }
        super.onBackPressed();
    }

    private void buildShell() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(C_BG);
        setContentView(root);

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(10), dp(8), dp(10), dp(8));
        header.setBackgroundColor(C_DARK);

        backButton = makeButton("‹", v -> goBack(), Color.TRANSPARENT, Color.WHITE, false);
        backButton.setTextSize(32);
        backButton.setPadding(0, 0, 0, dp(4));
        header.addView(backButton, new LinearLayout.LayoutParams(dp(48), dp(56)));

        LinearLayout titles = new LinearLayout(this);
        titles.setOrientation(LinearLayout.VERTICAL);
        titles.setGravity(Gravity.CENTER_VERTICAL);
        headerTitle = new TextView(this);
        headerTitle.setTextColor(Color.WHITE);
        headerTitle.setTextSize(18);
        headerTitle.setTypeface(Typeface.DEFAULT_BOLD);
        headerSub = new TextView(this);
        headerSub.setTextColor(Color.rgb(200, 205, 212));
        headerSub.setTextSize(11);
        titles.addView(headerTitle);
        titles.addView(headerSub);
        header.addView(titles, new LinearLayout.LayoutParams(0, dp(56), 1));

        Button data = makeButton("SYNC", v -> syncMenu(), C_ORANGE, Color.BLACK, true);
        header.addView(data, new LinearLayout.LayoutParams(dp(76), dp(42)));
        root.addView(header, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(72)));

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(dp(12), dp(14), dp(12), dp(30));
        scroll.addView(body, new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout workspace = new LinearLayout(this);
        workspace.setOrientation(LinearLayout.HORIZONTAL);
        if (tabletLayout()) {
            ScrollView railScroll = new ScrollView(this);
            navigationRail = new LinearLayout(this);
            navigationRail.setOrientation(LinearLayout.VERTICAL);
            navigationRail.setPadding(dp(10), dp(18), dp(10), dp(10));
            navigationRail.setBackgroundColor(Color.WHITE);
            railScroll.addView(navigationRail);
            workspace.addView(railScroll, new LinearLayout.LayoutParams(dp(204), ViewGroup.LayoutParams.MATCH_PARENT));
        }
        workspace.addView(scroll, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1));
        root.addView(workspace, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
    }

    private boolean tabletLayout() {
        android.content.res.Configuration config = getResources().getConfiguration();
        return config.orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE
                && config.screenWidthDp >= 840;
    }

    private void refreshNavigation() {
        if (navigationRail == null) return;
        navigationRail.removeAllViews();
        navigationRail.addView(text("PZ-REVIZE", 18, C_TEXT, true), marginBottom(dp(20)));
        railLink("Přehled", "home", () -> showHome(true));
        railLink("Zákazníci", "customers", () -> showCustomers(true));
        if (revisionId > 0) {
            navigationRail.addView(text("AKTUÁLNÍ REVIZE", 11, C_MUTED, true), marginBottom(dp(8)));
            railLink("Zakázka", "revision", () -> showRevision(true));
            railLink("Prohlídka", "checklist", () -> showChecklist(true));
            railLink("Měření", "measurements", () -> showMeasurements(true));
            railLink("Vnější vlivy", "influences", () -> showInfluences(true));
            railLink("Závady", "defects", () -> showDefects(true));
            railLink("Fotografie", "photos", () -> showPhotos(true));
        }
    }

    private void railLink(String label, String target, Runnable action) {
        Button b = smallButton(label, screen.equals(target) ? C_ORANGE : Color.WHITE, C_TEXT, v -> action.run());
        b.setGravity(Gravity.CENTER_VERTICAL | Gravity.LEFT);
        navigationRail.addView(b, marginBottom(dp(6)));
    }

    private void setHeader(String title, String sub) {
        headerTitle.setText(title);
        headerSub.setText(sub == null ? "" : sub);
        backButton.setVisibility("home".equals(screen) && history.isEmpty() ? View.INVISIBLE : View.VISIBLE);
    }

    private void clearBody(String title, String sub) {
        body.removeAllViews();
        setHeader(title, sub);
        refreshNavigation();
    }

    private void push(String next) {
        history.push(screen);
        screen = next;
    }

    private void goBack() {
        if (history.isEmpty()) {
            showHome(true);
            return;
        }
        screen = history.pop();
        renderCurrent();
    }

    private void renderCurrent() {
        switch (screen) {
            case "customers": showCustomers(false); break;
            case "open": showOpenRevisions(false); break;
            case "customer": showCustomer(false); break;
            case "revision": showRevision(false); break;
            case "measurements": showMeasurements(false); break;
            case "checklist": showChecklist(false); break;
            case "inspectionCatalog": showInspectionCatalog(false); break;
            case "influences": showInfluences(false); break;
            case "photos": showPhotos(false); break;
            case "defects": showDefects(false); break;
            default: showHome(false); break;
        }
    }

    private void showHome(boolean resetHistory) {
        screen = "home";
        customerId = 0;
        revisionId = 0;
        if (resetHistory) history.clear();
        clearBody("PZ-REVIZE Mobile", "terénní pracovní modul • NAS LAN / VPN / offline");

        LinearLayout hero = card();
        TextView brand = text("PZ-REVIZE", 25, C_TEXT, true);
        hero.addView(brand);
        TextView mobile = text("MOBILE", 15, C_ORANGE, true);
        mobile.setPadding(0, dp(2), 0, dp(8));
        hero.addView(mobile);
        hero.addView(text("Práce v terénu: zákazníci, kopie předchozí zprávy, měření, kontrolní body, pracovní fotografie a závady.", 14, C_MUTED, false));
        boolean syncConfigured = SyncClient.configured(this);
        String lastSync = SyncClient.lastSync(this);
        String syncText = syncConfigured ? (lastSync.isEmpty() ? "SYNC • server nastaven, zatím nesynchronizováno" : "SYNC • naposledy " + lastSync) : "OFFLINE • server zatím není nastaven";
        TextView offline = pill(syncText, syncConfigured ? C_GREEN : C_MUTED, Color.WHITE);
        LinearLayout.LayoutParams op = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(34));
        op.topMargin = dp(12);
        hero.addView(offline, op);
        String lastError = SyncClient.lastError(this);
        if (syncConfigured && !lastError.isEmpty()) {
            TextView error = text("Poslední pokus se nezdařil. Data zůstala bezpečně v tabletu; klepni na Synchronizace NAS pro opravu připojení.", 12, C_RED, true);
            error.setPadding(0, dp(9), 0, 0); hero.addView(error);
        }
        body.addView(hero, marginBottom(dp(12)));

        LinearLayout stats = new LinearLayout(this);
        stats.setOrientation(LinearLayout.HORIZONTAL);
        stats.addView(statBox(String.valueOf(db.countCustomers()), "zákazníků"), new LinearLayout.LayoutParams(0, dp(88), 1));
        LinearLayout.LayoutParams gap = new LinearLayout.LayoutParams(dp(8), dp(1));
        stats.addView(new View(this), gap);
        stats.addView(statBox(String.valueOf(db.countOpenRevisions()), "rozpracovaných"), new LinearLayout.LayoutParams(0, dp(88), 1));
        body.addView(stats, marginBottom(dp(14)));

        body.addView(primaryAction("VYHLEDAT / ZALOŽIT ZÁKAZNÍKA", "Začátek práce v terénu", v -> {
            push("customers"); showCustomers(false);
        }), marginBottom(dp(10)));
        body.addView(secondaryAction("ROZPRACOVANÉ REVIZE", "Rychle se vrátit k rozdělané práci", v -> {
            push("open"); showOpenRevisions(false);
        }), marginBottom(dp(10)));
        body.addView(secondaryAction("SYNCHRONIZACE NAS", SyncClient.configured(this) ? (SyncStore.dirtyCount(db) + " změn čeká na odeslání") : "Nastavit připojení k NAS PZ-REVIZE", v -> syncMenu()), marginBottom(dp(10)));
        body.addView(secondaryAction("ZÁLOHA / PŘENOS DAT", "Export nebo import mobilní databáze", v -> backupMenu()), marginBottom(dp(18)));

        List<Db.Row> open = db.openRevisions();
        sectionTitle("Poslední rozpracované revize");
        if (open.isEmpty()) {
            emptyState("Zatím zde není žádná rozpracovaná revize.", "Založ zákazníka a vytvoř první revizi.", "ZALOŽIT ZÁKAZNÍKA", v -> customerDialog(null));
        } else {
            int limit = Math.min(5, open.size());
            for (int i = 0; i < limit; i++) addOpenRevisionCard(open.get(i));
        }
    }

    private void showOpenRevisions(boolean nav) {
        if (nav) push("open"); else screen = "open";
        clearBody("Rozpracované revize", "rychlé pokračování práce");
        List<Db.Row> rows = db.openRevisions();
        if (rows.isEmpty()) {
            emptyState("Žádná rozpracovaná revize.", "Novou revizi vytvoříš u konkrétního zákazníka.", "ZÁKAZNÍCI", v -> {
                push("customers"); showCustomers(false);
            });
            return;
        }
        for (Db.Row r : rows) addOpenRevisionCard(r);
    }

    private void addOpenRevisionCard(Db.Row r) {
        LinearLayout c = card();
        c.addView(text(r.get("revision_no").isEmpty() ? "Revize bez čísla" : r.get("revision_no"), 17, C_TEXT, true));
        c.addView(text(join(r.get("customer_name"), r.get("object_name")), 14, C_MUTED, false));
        c.addView(text(join(r.get("revision_type"), r.get("object_address")), 13, C_MUTED, false));
        Button open = smallButton("OTEVŘÍT", C_ORANGE, Color.BLACK, v -> {
            customerId = r.longVal("customer_id"); revisionId = r.id(); push("revision"); showRevision(false);
        });
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44));
        bp.topMargin = dp(10);
        c.addView(open, bp);
        body.addView(c, marginBottom(dp(9)));
    }

    private void showCustomers(boolean nav) {
        if (nav) push("customers"); else screen = "customers";
        customerId = 0;
        revisionId = 0;
        clearBody("Zákazníci", "vyhledání nebo založení zákazníka");

        LinearLayout searchRow = new LinearLayout(this);
        searchRow.setOrientation(LinearLayout.HORIZONTAL);
        EditText q = edit("Název, IČO, adresa nebo kontakt");
        q.setSingleLine(true);
        q.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        searchRow.addView(q, new LinearLayout.LayoutParams(0, dp(52), 1));
        LinearLayout.LayoutParams addLp = new LinearLayout.LayoutParams(dp(56), dp(52));
        addLp.leftMargin = dp(8);
        searchRow.addView(smallButton("＋", C_ORANGE, Color.BLACK, v -> customerDialog(null)), addLp);
        body.addView(searchRow, marginBottom(dp(12)));

        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        body.addView(list);

        Runnable refresh = () -> {
            list.removeAllViews();
            List<Db.Row> rows = db.customers(q.getText().toString());
            if (rows.isEmpty()) {
                LinearLayout e = emptyStateView("Žádný zákazník nebyl nalezen.", q.getText().toString().trim().isEmpty() ? "Založ prvního zákazníka." : "Zkus jiné hledání nebo založ nový záznam.", "NOVÝ ZÁKAZNÍK", v -> customerDialog(null));
                list.addView(e);
                return;
            }
            for (Db.Row r : rows) {
                LinearLayout c = card();
                c.setOnClickListener(v -> {
                    customerId = r.id(); push("customer"); showCustomer(false);
                });
                c.setClickable(true);
                c.addView(text(r.get("name"), 17, C_TEXT, true));
                c.addView(text(join(prefix("IČO", r.get("ico")), r.get("address")), 13, C_MUTED, false));
                if (!r.get("contact").isEmpty()) c.addView(text(r.get("contact"), 13, C_MUTED, false));
                TextView hint = text("Klepnutím otevřít zákazníka  ›", 12, C_ORANGE, true);
                hint.setPadding(0, dp(8), 0, 0);
                c.addView(hint);
                list.addView(c, marginBottom(dp(8)));
            }
        };
        q.addTextChangedListener(new SimpleTextWatcher(refresh));
        refresh.run();
    }

    private void customerDialog(Db.Row row) {
        LinearLayout l = form();
        EditText name = field(l, "Název zákazníka", row == null ? "" : row.get("name"));
        EditText ico = field(l, "IČO", row == null ? "" : row.get("ico"));
        EditText addr = field(l, "Adresa", row == null ? "" : row.get("address"));
        EditText contact = field(l, "Kontakt", row == null ? "" : row.get("contact"));
        EditText note = fieldMulti(l, "Poznámka", row == null ? "" : row.get("note"), 3);
        AlertDialog.Builder b = new AlertDialog.Builder(this).setTitle(row == null ? "Nový zákazník" : "Upravit zákazníka").setView(dialogScroll(l)).setNegativeButton("Zrušit", null);
        b.setPositiveButton("Uložit", (d, w) -> {
            if (s(name).isEmpty()) { Toast.makeText(this, "Název zákazníka nesmí být prázdný.", Toast.LENGTH_LONG).show(); return; }
            if (row == null) {
                long id = db.addCustomer(s(name), s(ico), s(addr), s(contact), s(note));
                customerId = id;
                if ("home".equals(screen)) { history.push("home"); screen = "customer"; showCustomer(false); }
                else renderCurrent();
            } else {
                db.updateCustomer(row.id(), s(name), s(ico), s(addr), s(contact), s(note));
                renderCurrent();
            }
        });
        b.show();
    }

    private void showCustomer(boolean nav) {
        if (nav) push("customer"); else screen = "customer";
        Db.Row cst = db.customer(customerId);
        if (cst == null) { showCustomers(false); return; }
        clearBody(cst.get("name"), "zákazník • revize a kopie zpráv");

        LinearLayout info = card();
        info.addView(text(cst.get("name"), 18, C_TEXT, true));
        if (!cst.get("ico").isEmpty()) info.addView(text("IČO: " + cst.get("ico"), 13, C_MUTED, false));
        if (!cst.get("address").isEmpty()) info.addView(text(cst.get("address"), 13, C_MUTED, false));
        if (!cst.get("contact").isEmpty()) info.addView(text(cst.get("contact"), 13, C_MUTED, false));
        LinearLayout editRow = new LinearLayout(this); editRow.setOrientation(LinearLayout.HORIZONTAL);
        Button edit = smallButton("UPRAVIT ZÁKAZNÍKA", Color.WHITE, C_TEXT, v -> customerDialog(cst));
        edit.setBackground(rounded(Color.WHITE, C_BORDER, 12));
        editRow.addView(edit, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)));
        LinearLayout.LayoutParams er = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)); er.topMargin = dp(10);
        info.addView(editRow, er);
        body.addView(info, marginBottom(dp(12)));

        body.addView(primaryAction("＋ NOVÁ REVIZE", "Elektro, stroj nebo LPS", v -> revisionCreateDialog()), marginBottom(dp(9)));
        body.addView(secondaryAction("＋ NOVÝ VV", "Založit nový protokol o určení vnějších vlivů", v -> revisionCreateDialog("VNEJSI")), marginBottom(dp(9)));

        List<Db.Row> revisions = db.revisions(customerId);
        if (!revisions.isEmpty()) {
            body.addView(secondaryAction("PŘEVZÍT KOPII POSLEDNÍ ZPRÁVY", "Převezme strukturu a měřené hodnoty, body se označí jako neprovedené", v -> copyRevisionConfirm(revisions.get(0))), marginBottom(dp(16)));
        }

        sectionTitle("Revizní zprávy zákazníka");
        if (revisions.isEmpty()) {
            emptyState("Zákazník zatím nemá žádnou revizi.", "Můžeš založit novou zprávu.", "NOVÁ REVIZE", v -> revisionCreateDialog());
            return;
        }

        for (Db.Row r : revisions) {
            LinearLayout card = card();
            card.addView(text(r.get("revision_no").isEmpty() ? "Revize bez čísla" : r.get("revision_no"), 17, C_TEXT, true));
            card.addView(text(join(r.get("revision_type"), r.get("object_name")), 13, C_MUTED, false));
            card.addView(text(join(r.get("object_address"), r.get("status")), 12, C_MUTED, false));
            LinearLayout row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL);
            Button open = smallButton("OTEVŘÍT", C_ORANGE, Color.BLACK, v -> { revisionId = r.id(); push("revision"); showRevision(false); });
            Button copy = smallButton("KOPIE", Color.WHITE, C_TEXT, v -> copyRevisionConfirm(r));
            copy.setBackground(rounded(Color.WHITE, C_BORDER, 10));
            row.addView(open, new LinearLayout.LayoutParams(0, dp(44), 1));
            LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(0, dp(44), 1); cp.leftMargin = dp(8); row.addView(copy, cp);
            LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)); rp.topMargin = dp(10); card.addView(row, rp);
            body.addView(card, marginBottom(dp(8)));
        }
    }

    private void copyRevisionConfirm(Db.Row r) {
        String title = r.get("revision_no").isEmpty() ? "vybrané zprávy" : r.get("revision_no");
        new AlertDialog.Builder(this)
                .setTitle("Převzít kopii zprávy")
                .setMessage("Vytvořit novou rozpracovanou revizi jako kopii „" + title + "“?\n\nPřevezmou se měření a jejich hodnoty i kontrolní body. Stav provedení se v nové revizi vynuluje.")
                .setNegativeButton("Zrušit", null)
                .setPositiveButton("Vytvořit kopii", (d, w) -> {
                    long id = db.cloneRevision(r.id());
                    if (id <= 0) { Toast.makeText(this, "Kopii se nepodařilo vytvořit.", Toast.LENGTH_LONG).show(); return; }
                    revisionId = id;
                    Toast.makeText(this, "Kopie zprávy byla vytvořena.", Toast.LENGTH_SHORT).show();
                    push("revision"); showRevision(false);
                }).show();
    }

    private void revisionCreateDialog() { revisionCreateDialog(null); }

    private void revisionCreateDialog(String fixedType) {
        LinearLayout l = form();
        boolean vv = "VNEJSI".equals(fixedType);
        EditText no = field(l, vv ? "Číslo protokolu VV" : "Číslo revize", "");
        Spinner type = vv ? null : spinner(l, "Typ revize", new String[]{"ELEKTRO", "STROJ", "LPS"}, 0);
        EditText obj = field(l, "Objekt / zařízení", "");
        EditText addr = field(l, "Adresa objektu", "");
        new AlertDialog.Builder(this).setTitle(vv ? "Nový VV" : "Nová revize").setView(dialogScroll(l)).setNegativeButton("Zrušit", null).setPositiveButton("Založit", (d, w) -> {
            String selectedType = vv ? "VNEJSI" : String.valueOf(type.getSelectedItem());
            revisionId = db.addRevision(customerId, s(no), selectedType, s(obj), s(addr));
            push("revision"); showRevision(false);
        }).show();
    }

    private void showRevision(boolean nav) {
        if (nav) push("revision"); else screen = "revision";
        Db.Row r = db.revision(revisionId);
        if (r == null) { showCustomer(false); return; }
        boolean vv = "VNEJSI".equals(r.get("revision_type"));
        clearBody(r.get("revision_no").isEmpty() ? (vv ? "Protokol VV" : "Revize") : r.get("revision_no"), join(r.get("revision_type"), r.get("status")));

        LinearLayout info = card();
        info.addView(text(r.get("object_name").isEmpty() ? "Objekt není vyplněn" : r.get("object_name"), 18, C_TEXT, true));
        if (!r.get("object_address").isEmpty()) info.addView(text(r.get("object_address"), 13, C_MUTED, false));
        if (r.longVal("source_revision_id") > 0) info.addView(pill("PŘEVZATÁ KOPIE ZPRÁVY", C_ORANGE, Color.BLACK));
        body.addView(info, marginBottom(dp(12)));

        int mAll = db.countMeasurements(revisionId), mDone = db.countMeasurementsDone(revisionId);
        int cAll = db.countChecklist(revisionId), cDone = db.countChecklistDone(revisionId);
        int photos = db.countPhotos(revisionId), defects = db.countDefects(revisionId);

        sectionTitle(vv ? "Práce na protokolu VV" : "Práce na revizi");
        if (vv) {
            body.addView(moduleButton("1  MÍSTNOSTI A VNĚJŠÍ VLIVY", "Popis, kódy vlivů a opatření", C_ORANGE, v -> { push("influences"); showInfluences(false); }), marginBottom(dp(8)));
            body.addView(moduleButton("2  PRACOVNÍ FOTOGRAFIE", photos + " fotografií", Color.rgb(37, 99, 235), v -> { push("photos"); showPhotos(false); }), marginBottom(dp(14)));
        } else {
            body.addView(moduleButton("1  PROHLÍDKA / KONTROLA", cDone + " / " + cAll + " bodů prošlo • výběr z databáze", C_GREEN, v -> { push("checklist"); showChecklist(false); }), marginBottom(dp(8)));
            body.addView(moduleButton("2  MĚŘENÍ", mDone + " / " + mAll + " provedeno • strom obvodů a bodů", C_ORANGE, v -> { push("measurements"); showMeasurements(false); }), marginBottom(dp(8)));
            body.addView(moduleButton("3  VNĚJŠÍ VLIVY", "Místnosti, kódy vlivů a opatření", C_ORANGE, v -> { push("influences"); showInfluences(false); }), marginBottom(dp(8)));
            body.addView(moduleButton("4  PRACOVNÍ FOTOGRAFIE", photos + " fotografií • lze převést do závady", Color.rgb(37, 99, 235), v -> { push("photos"); showPhotos(false); }), marginBottom(dp(8)));
            body.addView(moduleButton("5  ZÁVADY", defects + " evidovaných závad", C_RED, v -> { push("defects"); showDefects(false); }), marginBottom(dp(14)));
        }
        sectionTitle("Údaje zprávy");
        body.addView(secondaryAction("UPRAVIT ÚDAJE REVIZE", "Číslo, typ, objekt, stav a poznámka", v -> revisionEditDialog(r)), marginBottom(dp(8)));
    }

    private void revisionEditDialog(Db.Row r) {
        LinearLayout l = form();
        EditText no = field(l, "Číslo", r.get("revision_no"));
        String[] types = {"ELEKTRO", "STROJ", "LPS", "VNEJSI"};
        Spinner type = spinner(l, "Typ", types, indexOf(types, r.get("revision_type")));
        EditText obj = field(l, "Objekt / zařízení", r.get("object_name"));
        EditText addr = field(l, "Adresa", r.get("object_address"));
        String[] statuses = {"Rozpracovaná", "Dokončená", "Předaná"};
        Spinner status = spinner(l, "Stav", statuses, indexOf(statuses, r.get("status")));
        EditText note = fieldMulti(l, "Poznámka", r.get("note"), 3);
        new AlertDialog.Builder(this).setTitle("Údaje revize").setView(dialogScroll(l)).setNegativeButton("Zrušit", null).setPositiveButton("Uložit", (d, w) -> {
            db.updateRevision(r.id(), s(no), String.valueOf(type.getSelectedItem()), s(obj), s(addr), String.valueOf(status.getSelectedItem()), s(note));
            showRevision(false);
        }).show();
    }

    private void showMeasurements(boolean nav) {
        if (nav) { push("measurements"); selectedMeasurements.clear(); } else screen = "measurements";
        if (tabletLayout()) { showTabletMeasurements(); return; }
        clearBody("Měření", "stromová struktura • jednotlivě i hromadně");
        addRevisionContext();
        List<Db.Row> rows = db.measurements(revisionId);

        LinearLayout add1 = new LinearLayout(this); add1.setOrientation(LinearLayout.HORIZONTAL);
        add1.addView(smallButton("＋ OBVOD", C_ORANGE, Color.BLACK, v -> measurementDialog(null, "CIRCUIT")), new LinearLayout.LayoutParams(0, dp(46), 1));
        LinearLayout.LayoutParams p1 = new LinearLayout.LayoutParams(0, dp(46), 1); p1.leftMargin = dp(6);
        add1.addView(smallButton("＋ BOD", Color.WHITE, C_TEXT, v -> measurementDialog(null, "POINT")), p1);
        LinearLayout.LayoutParams p2 = new LinearLayout.LayoutParams(0, dp(46), 1); p2.leftMargin = dp(6);
        add1.addView(smallButton("＋ SPOJITOST", Color.WHITE, C_TEXT, v -> measurementDialog(null, "CONTINUITY")), p2);
        body.addView(add1, marginBottom(dp(6)));

        LinearLayout add2 = new LinearLayout(this); add2.setOrientation(LinearLayout.HORIZONTAL);
        Button rcdBtn=smallButton("＋ RCD / RCBO", Color.WHITE, C_TEXT, v -> measurementDialog(null, "RCD")); rcdBtn.setBackground(rounded(Color.WHITE,C_BORDER,10));
        add2.addView(rcdBtn,new LinearLayout.LayoutParams(0,dp(46),1));
        LinearLayout.LayoutParams p3=new LinearLayout.LayoutParams(0,dp(46),1);p3.leftMargin=dp(6);
        Button generic=smallButton("＋ OBECNÉ", Color.WHITE, C_TEXT, v -> measurementDialog(null, "MEASUREMENT"));generic.setBackground(rounded(Color.WHITE,C_BORDER,10));
        add2.addView(generic,p3);
        LinearLayout.LayoutParams p4=new LinearLayout.LayoutParams(0,dp(46),1);p4.leftMargin=dp(6);
        add2.addView(smallButton("HROMADNĚ", C_DARK, Color.WHITE, v -> bulkDialog()),p4);
        body.addView(add2, marginBottom(dp(10)));

        if (!rows.isEmpty()) {
            LinearLayout selRow = new LinearLayout(this); selRow.setOrientation(LinearLayout.HORIZONTAL); selRow.setGravity(Gravity.CENTER_VERTICAL);
            Button all = smallButton(selectedMeasurements.size() == rows.size() ? "ZRUŠIT VÝBĚR" : "VYBRAT VŠE", Color.WHITE, C_TEXT, v -> {
                if (selectedMeasurements.size() == rows.size()) selectedMeasurements.clear(); else { selectedMeasurements.clear(); for (Db.Row x : rows) selectedMeasurements.add(x.id()); }
                showMeasurements(false);
            });
            all.setBackground(rounded(Color.WHITE, C_BORDER, 10));
            selRow.addView(all, new LinearLayout.LayoutParams(0, dp(40), 1));
            TextView selected = text("Vybráno " + selectedMeasurements.size(), 12, C_MUTED, true); selected.setGravity(Gravity.CENTER_VERTICAL | Gravity.RIGHT);
            selRow.addView(selected, new LinearLayout.LayoutParams(0, dp(40), 1));
            body.addView(selRow, marginBottom(dp(8)));
        }

        int done = 0; for (Db.Row r : rows) if (r.bool("done")) done++;
        addProgress(done, rows.size(), "Provedeno " + done + " / " + rows.size());

        if (rows.isEmpty()) {
            emptyState("Měření zatím nemá žádnou strukturu.", "Začni obvodem nebo obecným měřením. Měřicí body a spojitost můžeš podřadit pod konkrétní obvod.", "PŘIDAT OBVOD", v -> measurementDialog(null, "CIRCUIT"));
            return;
        }

        Map<String,Db.Row> byKey=new LinkedHashMap<>();
        for(Db.Row r:rows) byKey.put(nodeKey(r),r);
        Map<String,List<Db.Row>> children=new LinkedHashMap<>();
        List<Db.Row> roots=new ArrayList<>();
        Db.Row inferredParent=null;
        for(Db.Row r:rows){
            String rt=measurementRowType(r);
            String pk=nz(r.get("parent_key"));
            String parentNode="";
            if(!pk.isEmpty()){
                for(Db.Row p:rows) if(pk.equals(nz(p.get("item_key")))){parentNode=nodeKey(p);break;}
            }
            if(parentNode.isEmpty() && isTreeChild(rt) && inferredParent!=null) parentNode=nodeKey(inferredParent);
            if(!parentNode.isEmpty()){
                List<Db.Row> c=children.get(parentNode); if(c==null){c=new ArrayList<>();children.put(parentNode,c);} c.add(r);
            }else{
                roots.add(r);
            }
            if(isTreeParent(rt)) inferredParent=r;
            else if(!isTreeChild(rt) && !"NOTE".equals(rt) && !"BLANK".equals(rt)) inferredParent=null;
        }
        for(Db.Row r:roots) addMeasurementTreeRow(r,0,children);
    }

    private String nodeKey(Db.Row r) {
        String k=nz(r.get("item_key")); return k.isEmpty() ? "id:"+r.id() : k;
    }

    private String measurementRowType(Db.Row r) {
        String rt=nz(r.get("row_type")).trim().toUpperCase();
        if(!rt.isEmpty()) return rt;
        String mt=nz(r.get("measure_type")).trim().toUpperCase();
        if(mt.equals("CIRCUIT")||mt.equals("POINT")||mt.equals("CONTINUITY")||mt.equals("RCD")||mt.equals("RCBO")||mt.equals("GROUP")||mt.equals("FUNCTION")||mt.equals("NOTE")||mt.equals("BLANK")||mt.equals("MEASUREMENT")) return mt;
        if("CIRCUIT".equals(nz(r.get("remote_kind")))) return "CIRCUIT";
        return "MEASUREMENT";
    }

    private boolean isTreeParent(String rt) { return "CIRCUIT".equals(rt)||"RCD".equals(rt)||"RCBO".equals(rt)||"GROUP".equals(rt); }
    private boolean isTreeChild(String rt) { return "POINT".equals(rt)||"CONTINUITY".equals(rt)||"FUNCTION".equals(rt)||"MEASUREMENT".equals(rt)||"NOTE".equals(rt)||"BLANK".equals(rt); }

    private String rowTypeLabel(String rt) {
        switch(rt){
            case "CIRCUIT": return "OBVOD";
            case "POINT": return "MĚŘICÍ BOD";
            case "CONTINUITY": return "SPOJITOST";
            case "RCD": case "RCBO": return "RCD / RCBO";
            case "GROUP": return "SKUPINA";
            case "FUNCTION": return "FUNKČNÍ ZKOUŠKA";
            case "NOTE": return "POZNÁMKA";
            case "BLANK": return "PRÁZDNÝ ŘÁDEK";
            default: return "MĚŘENÍ";
        }
    }

    private int rowTypeColor(String rt) {
        if("CIRCUIT".equals(rt)||"RCD".equals(rt)||"RCBO".equals(rt)) return Color.rgb(37,99,235);
        if("CONTINUITY".equals(rt)) return C_GREEN;
        if("POINT".equals(rt)) return C_ORANGE;
        if("GROUP".equals(rt)) return Color.rgb(79,70,229);
        if("FUNCTION".equals(rt)) return Color.rgb(5,150,105);
        return C_MUTED;
    }

    private void addMeasurementTreeRow(Db.Row r,int depth,Map<String,List<Db.Row>> children){
        String key=nodeKey(r), rt=measurementRowType(r);
        List<Db.Row> kids=children.get(key);
        boolean hasKids=kids!=null&&!kids.isEmpty();
        boolean collapsed=collapsedMeasurementNodes.contains(key);

        LinearLayout outer=new LinearLayout(this);outer.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams op=marginBottom(dp(depth==0?8:5));op.leftMargin=dp(depth*24);body.addView(outer,op);

        LinearLayout c=card();c.setPadding(dp(10),dp(9),dp(10),dp(9));
        LinearLayout head=new LinearLayout(this);head.setOrientation(LinearLayout.HORIZONTAL);head.setGravity(Gravity.CENTER_VERTICAL);
        if(depth>0){TextView branch=text("↳",18,C_MUTED,true);branch.setGravity(Gravity.CENTER);head.addView(branch,new LinearLayout.LayoutParams(dp(28),dp(44)));}
        CheckBox select=new CheckBox(this);select.setChecked(selectedMeasurements.contains(r.id()));
        select.setOnCheckedChangeListener((b,checked)->{if(checked)selectedMeasurements.add(r.id());else selectedMeasurements.remove(r.id());});
        head.addView(select,new LinearLayout.LayoutParams(dp(44),dp(44)));

        LinearLayout titles=new LinearLayout(this);titles.setOrientation(LinearLayout.VERTICAL);
        LinearLayout titleLine=new LinearLayout(this);titleLine.setOrientation(LinearLayout.HORIZONTAL);titleLine.setGravity(Gravity.CENTER_VERTICAL);
        String title=r.get("element").isEmpty()?rowTypeLabel(rt):r.get("element");
        titleLine.addView(text(title,depth==0?16:15,C_TEXT,true),new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        TextView kind=pill(rowTypeLabel(rt),rowTypeColor(rt),Color.WHITE);titleLine.addView(kind,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,dp(28)));
        titles.addView(titleLine);
        String sub=valuesText(r);
        if(sub.isEmpty()) sub=nz(r.get("measure_type"));
        TextView st=text(sub,12,sub.isEmpty()?C_MUTED:C_TEXT,false);st.setMaxLines(2);titles.addView(st);
        head.addView(titles,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));

        if(hasKids){
            Button toggle=smallButton((collapsed?"＋ ":"− ")+kids.size(),Color.WHITE,C_TEXT,v->{if(collapsedMeasurementNodes.contains(key))collapsedMeasurementNodes.remove(key);else collapsedMeasurementNodes.add(key);showMeasurements(false);});
            toggle.setBackground(rounded(Color.WHITE,C_BORDER,10));head.addView(toggle,new LinearLayout.LayoutParams(dp(58),dp(38)));
        }
        Button edit=smallButton("⋮",Color.WHITE,C_TEXT,v->measurementDialog(r,rt));edit.setTextSize(20);edit.setBackground(rounded(Color.WHITE,C_BORDER,10));
        LinearLayout.LayoutParams ep=new LinearLayout.LayoutParams(dp(48),dp(38));ep.leftMargin=dp(5);head.addView(edit,ep);
        c.addView(head);

        LinearLayout foot=new LinearLayout(this);foot.setOrientation(LinearLayout.HORIZONTAL);foot.setGravity(Gravity.CENTER_VERTICAL);
        CheckBox done=new CheckBox(this);done.setText("Hotovo");done.setChecked(r.bool("done"));done.setTextColor(C_MUTED);
        done.setOnCheckedChangeListener((b,checked)->db.setMeasurementDone(r.id(),checked));
        foot.addView(done,new LinearLayout.LayoutParams(0,dp(42),1));
        if(hasKids) foot.addView(text(kids.size()+" podřízených položek",11,C_MUTED,false));
        c.addView(foot);
        outer.addView(c);
        if(hasKids&&!collapsed) for(Db.Row child:kids) addMeasurementTreeRowInto(outer,child,depth+1,children);
    }

    private void addMeasurementTreeRowInto(LinearLayout container,Db.Row r,int depth,Map<String,List<Db.Row>> children){
        String key=nodeKey(r),rt=measurementRowType(r);List<Db.Row> kids=children.get(key);boolean hasKids=kids!=null&&!kids.isEmpty();boolean collapsed=collapsedMeasurementNodes.contains(key);
        LinearLayout c=card();c.setPadding(dp(8),dp(7),dp(8),dp(7));
        LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT);cp.leftMargin=dp(22*depth);cp.topMargin=dp(5);
        LinearLayout head=new LinearLayout(this);head.setOrientation(LinearLayout.HORIZONTAL);head.setGravity(Gravity.CENTER_VERTICAL);
        TextView branch=text("↳",18,C_MUTED,true);branch.setGravity(Gravity.CENTER);head.addView(branch,new LinearLayout.LayoutParams(dp(28),dp(42)));
        CheckBox select=new CheckBox(this);select.setChecked(selectedMeasurements.contains(r.id()));select.setOnCheckedChangeListener((b,checked)->{if(checked)selectedMeasurements.add(r.id());else selectedMeasurements.remove(r.id());});head.addView(select,new LinearLayout.LayoutParams(dp(42),dp(42)));
        LinearLayout tx=new LinearLayout(this);tx.setOrientation(LinearLayout.VERTICAL);tx.addView(text(r.get("element").isEmpty()?rowTypeLabel(rt):r.get("element"),14,C_TEXT,true));
        String vals=valuesText(r);if(vals.isEmpty())vals=nz(r.get("measure_type"));tx.addView(text(vals,12,C_MUTED,false));head.addView(tx,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        TextView tag=pill(rowTypeLabel(rt),rowTypeColor(rt),Color.WHITE);head.addView(tag,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,dp(26)));
        Button edit=smallButton("⋮",Color.WHITE,C_TEXT,v->measurementDialog(r,rt));edit.setTextSize(18);edit.setBackground(rounded(Color.WHITE,C_BORDER,10));LinearLayout.LayoutParams e=new LinearLayout.LayoutParams(dp(44),dp(36));e.leftMargin=dp(4);head.addView(edit,e);
        c.addView(head);
        CheckBox done=new CheckBox(this);done.setText("Hotovo");done.setChecked(r.bool("done"));done.setTextColor(C_MUTED);done.setOnCheckedChangeListener((b,checked)->db.setMeasurementDone(r.id(),checked));c.addView(done);
        container.addView(c,cp);
        if(hasKids&&!collapsed)for(Db.Row x:kids)addMeasurementTreeRowInto(container,x,depth+1,children);
    }

    private String valuesText(Db.Row r) {
        List<String> x = new ArrayList<>();
        for (int i = 1; i <= 4; i++) {
            String v = nz(r.get("v" + i)); String u = nz(r.get("unit" + i));
            if (!v.isEmpty()) x.add(v + (u.isEmpty() ? "" : " " + u));
        }
        String base = joinList(x, "  |  ");
        if (!r.get("note").isEmpty()) base = base.isEmpty() ? r.get("note") : base + " • " + r.get("note");
        return base;
    }

    private int structureIndex(String rt){
        String[] v={"CIRCUIT","POINT","CONTINUITY","RCD","GROUP","MEASUREMENT","FUNCTION","NOTE"};
        for(int i=0;i<v.length;i++)if(v[i].equals(rt))return i;return 5;
    }

    private int defaultTypeForStructure(String rt){
        if("POINT".equals(rt))return 1;
        if("CONTINUITY".equals(rt))return 3;
        if("RCD".equals(rt)||"RCBO".equals(rt))return 4;
        if("FUNCTION".equals(rt))return 7;
        return 0;
    }

    private void measurementDialog(Db.Row r) { measurementDialog(r, r==null?"MEASUREMENT":measurementRowType(r)); }

    private void measurementDialog(Db.Row r,String initialRowType) { measurementDialog(r, initialRowType, null); }

    private void measurementDialog(Db.Row r,String initialRowType,Db.Row defaultParent) {
        LinearLayout l = form();
        String[] structureLabels={"Obvod / jištění","Měřicí bod","Spojitost","RCD / RCBO","Skupina","Obecné měření","Funkční zkouška","Poznámka"};
        String[] structureValues={"CIRCUIT","POINT","CONTINUITY","RCD","GROUP","MEASUREMENT","FUNCTION","NOTE"};
        Spinner structure=spinner(l,"Zařazení ve stromu",structureLabels,structureIndex(initialRowType));
        EditText element = field(l, "Prvek / bod měření", r == null ? "" : r.get("element"));

        List<Db.Row> parents=new ArrayList<>();
        for(Db.Row x:db.measurements(revisionId))if(x.id()!=(r==null?0:r.id())&&isTreeParent(measurementRowType(x)))parents.add(x);
        String[] parentLabels=new String[parents.size()+1];parentLabels[0]="— bez nadřazené položky —";int parentSelected=0;
        String currentParent=r==null?(defaultParent==null?"":db.ensureMeasurementKey(defaultParent.id())):nz(r.get("parent_key"));
        for(int i=0;i<parents.size();i++){
            Db.Row p=parents.get(i);parentLabels[i+1]=rowTypeLabel(measurementRowType(p))+" • "+(p.get("element").isEmpty()?"bez názvu":p.get("element"));
            String pk=nz(p.get("item_key"));if(!currentParent.isEmpty()&&currentParent.equals(pk))parentSelected=i+1;
        }
        Spinner parent=spinner(l,"Nadřazená položka",parentLabels,parentSelected);

        String[] types = {"Klasické", "L-PE / Zs / Ik", "Izolační odpor", "Spojitost", "RCD", "RCBO", "Napětí", "Funkční", "Jiné"};
        int typeIndex=r==null?defaultTypeForStructure(initialRowType):indexOf(types,r.get("measure_type"));
        Spinner type = spinner(l, "Druh měření", types, typeIndex);

        TextView[] captions = new TextView[4];
        EditText[] values = new EditText[4];
        EditText[] units = new EditText[4];
        for (int i = 0; i < 4; i++) {
            captions[i] = text("Hodnota " + (i + 1), 12, C_MUTED, true);
            l.addView(captions[i]);
            LinearLayout pair = new LinearLayout(this); pair.setOrientation(LinearLayout.HORIZONTAL);
            values[i] = edit("hodnota"); units[i] = edit("jednotka");
            if (r != null) { values[i].setText(r.get("v" + (i + 1))); units[i].setText(r.get("unit" + (i + 1))); }
            pair.addView(values[i], new LinearLayout.LayoutParams(0, dp(50), 2));
            LinearLayout.LayoutParams ulp = new LinearLayout.LayoutParams(0, dp(50), 1); ulp.leftMargin = dp(6); pair.addView(units[i], ulp);
            l.addView(pair, marginBottom(dp(7)));
        }
        EditText note = fieldMulti(l, "Poznámka", r == null ? "" : r.get("note"), 2);
        CheckBox done = new CheckBox(this); done.setText("Provedeno / zkontrolováno"); done.setChecked(r != null && r.bool("done")); l.addView(done);

        type.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(android.widget.AdapterView<?> p, View view, int pos, long id) { applyPreset(pos, captions, units, r == null); }
            @Override public void onNothingSelected(android.widget.AdapterView<?> p) { }
        });
        applyPreset(type.getSelectedItemPosition(),captions,units,r==null);

        AlertDialog.Builder b = new AlertDialog.Builder(this).setTitle(r == null ? "Nová položka měření" : "Upravit položku měření").setView(dialogScroll(l)).setNegativeButton("Zrušit", null);
        if (r != null) b.setNeutralButton("Smazat", (d, w) -> { db.deleteMeasurement(r.id()); selectedMeasurements.remove(r.id()); if (selectedMeasurementId == r.id()) selectedMeasurementId = 0; showMeasurements(false); });
        b.setPositiveButton("Uložit", (d, w) -> {
            String rt=structureValues[structure.getSelectedItemPosition()];
            if (s(element).isEmpty() && !"NOTE".equals(rt)) { Toast.makeText(this, "Vyplň prvek nebo bod měření.", Toast.LENGTH_LONG).show(); return; }
            String parentKey="";
            int pi=parent.getSelectedItemPosition();
            if(pi>0&&pi<=parents.size())parentKey=db.ensureMeasurementKey(parents.get(pi-1).id());
            String[] vs = new String[4], us = new String[4];
            for (int i = 0; i < 4; i++) { vs[i] = s(values[i]); us[i] = s(units[i]); }
            selectedMeasurementId = db.saveMeasurement(revisionId, r == null ? 0 : r.id(), s(element), String.valueOf(type.getSelectedItem()), rt, parentKey, vs, us, s(note), done.isChecked());
            showMeasurements(false);
        }).show();
    }

    private void applyPreset(int pos, TextView[] captions, EditText[] units, boolean fillUnits) {
        String[][] labels = {
                {"Hodnota 1", "Hodnota 2", "Hodnota 3", "Hodnota 4"},
                {"Napětí U", "Impedance Zs", "Zkratový proud Ik", "Další hodnota"},
                {"Riso L-PE", "Riso L-N", "Riso N-PE", "Další Riso"},
                {"Odpor spojitosti RPE", "Další bod", "Další bod", "Další bod"},
                {"IΔn", "Vybavovací čas t", "Dotykové napětí", "Další hodnota"},
                {"IΔn", "Vybavovací čas t", "Zs / Ik", "Další hodnota"},
                {"L-N", "L-PE", "N-PE", "L-L"},
                {"Výsledek / hodnota", "Hodnota 2", "Hodnota 3", "Hodnota 4"},
                {"Hodnota 1", "Hodnota 2", "Hodnota 3", "Hodnota 4"}
        };
        String[][] defaultUnits = {
                {"", "", "", ""}, {"V", "Ω", "A", ""}, {"MΩ", "MΩ", "MΩ", "MΩ"}, {"Ω", "Ω", "Ω", "Ω"},
                {"mA", "ms", "V", ""}, {"mA", "ms", "Ω", ""}, {"V", "V", "V", "V"}, {"", "", "", ""}, {"", "", "", ""}
        };
        int p = Math.max(0, Math.min(pos, labels.length - 1));
        for (int i = 0; i < 4; i++) {
            captions[i].setText(labels[p][i]);
            if (fillUnits && units[i].getText().toString().trim().isEmpty()) units[i].setText(defaultUnits[p][i]);
        }
    }

    private void bulkDialog() {
        if (selectedMeasurements.isEmpty()) {
            Toast.makeText(this, "Nejdříve označ měření, která chceš hromadně upravit.", Toast.LENGTH_LONG).show();
            return;
        }
        LinearLayout l = form();
        l.addView(text("Vybráno " + selectedMeasurements.size() + " prvků. Vyplní se pouze neprázdná pole.", 13, C_MUTED, false));
        EditText[] value = new EditText[4];
        for (int i = 0; i < 4; i++) value[i] = field(l, "Nová hodnota " + (i + 1) + " (prázdné = neměnit)", "");
        EditText note = fieldMulti(l, "Poznámka (prázdné = neměnit)", "", 2);
        Spinner state = spinner(l, "Stav", new String[]{"Neměnit", "PROVEDENO", "NEPROVEDENO"}, 0);
        new AlertDialog.Builder(this).setTitle("Hromadná změna").setView(dialogScroll(l)).setNegativeButton("Zrušit", null).setPositiveButton("Použít", (d, w) -> {
            String[] vs = new String[4]; for (int i = 0; i < 4; i++) vs[i] = s(value[i]);
            Boolean done = null; if (state.getSelectedItemPosition() == 1) done = Boolean.TRUE; else if (state.getSelectedItemPosition() == 2) done = Boolean.FALSE;
            db.bulkMeasurement(new ArrayList<>(selectedMeasurements), vs, s(note), done);
            selectedMeasurements.clear(); showMeasurements(false);
        }).show();
    }

    private LinearLayout tabletColumns() {
        LinearLayout columns = new LinearLayout(this);
        columns.setOrientation(LinearLayout.HORIZONTAL);
        columns.setGravity(Gravity.TOP);
        body.addView(columns, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return columns;
    }

    private LinearLayout tabletPanel(LinearLayout columns, int weight) {
        ScrollView scroller = new ScrollView(this);
        scroller.setFillViewport(true);
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(14), dp(14), dp(14), dp(18));
        panel.setBackground(rounded(Color.WHITE, C_BORDER, 14));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, weight);
        if (columns.getChildCount() > 0) lp.leftMargin = dp(12);
        lp.height = dp(Math.max(400, getResources().getConfiguration().screenHeightDp - 196));
        scroller.addView(panel);
        columns.addView(scroller, lp);
        return panel;
    }

    private void showTabletChecklist() {
        clearBody("Prohlídka / kontrola", "Vyber bod vlevo a zapiš výsledek vpravo");
        addRevisionContext();
        List<Db.Row> rows = db.checklist(revisionId);
        int done = 0; for (Db.Row r : rows) if (r.bool("done")) done++;
        addProgress(done, rows.size(), "Posouzeno " + done + " / " + rows.size());
        LinearLayout columns = tabletColumns();
        LinearLayout list = tabletPanel(columns, 5);
        LinearLayout detail = tabletPanel(columns, 6);
        LinearLayout tools = new LinearLayout(this); tools.setOrientation(LinearLayout.HORIZONTAL);
        tools.addView(smallButton("＋ KATALOG", C_ORANGE, C_TEXT, v -> showInspectionCatalog(true)), new LinearLayout.LayoutParams(0, dp(48), 1));
        LinearLayout.LayoutParams addLp = new LinearLayout.LayoutParams(0, dp(48), 1); addLp.leftMargin = dp(8);
        tools.addView(smallButton("＋ VLASTNÍ BOD", C_DARK, Color.WHITE, v -> {
            LinearLayout f = form(); EditText label = fieldMulti(f, "Kontrolní bod", "", 3);
            new AlertDialog.Builder(this).setTitle("Nový kontrolní bod").setView(dialogScroll(f)).setNegativeButton("Zrušit", null)
                    .setPositiveButton("Přidat", (d, w) -> { if (!s(label).isEmpty()) { db.addChecklist(revisionId, s(label)); selectedChecklistId = 0; showChecklist(false); } }).show();
        }), addLp);
        list.addView(tools, marginBottom(dp(12)));
        if (rows.isEmpty()) {
            list.addView(text("Zatím nejsou vybrány žádné kontrolní body.", 15, C_MUTED, false));
            detail.addView(text("Vyber body z katalogu nebo přidej vlastní.", 16, C_MUTED, false));
            return;
        }
        Db.Row active = null;
        for (Db.Row r : rows) if (r.id() == selectedChecklistId) active = r;
        if (active == null) { active = rows.get(0); selectedChecklistId = active.id(); }
        String group = "";
        for (Db.Row r : rows) {
            String next = r.get("group_name").isEmpty() ? "Ostatní" : r.get("group_name");
            if (!group.equals(next)) { group = next; list.addView(text(group, 12, C_MUTED, true), marginBottom(dp(5))); }
            String result = r.get("result");
            String icon = "VYHOVUJE".equals(result) ? "✓  " : "NEVYHOVUJE".equals(result) ? "⚠  " : "NETÝKÁ SE".equals(result) ? "–  " : "○  ";
            Button item = smallButton(icon + r.get("label"), r.id() == selectedChecklistId ? Color.rgb(255, 243, 220) : C_BG, C_TEXT, v -> {
                selectedChecklistId = r.id(); showChecklist(false);
            });
            item.setAllCaps(false); item.setGravity(Gravity.LEFT | Gravity.CENTER_VERTICAL);
            item.setSingleLine(false); item.setMinHeight(dp(52));
            list.addView(item, marginBottom(dp(6)));
        }
        final Db.Row chosen = active;
        detail.addView(text(chosen.get("label"), 20, C_TEXT, true), marginBottom(dp(7)));
        if (!chosen.get("source_ref").isEmpty()) detail.addView(text(chosen.get("source_ref"), 12, C_MUTED, false), marginBottom(dp(18)));
        detail.addView(text("Výsledek prohlídky", 13, C_MUTED, true), marginBottom(dp(8)));
        EditText notes = fieldMulti(detail, "Poznámka / popis zjištění", chosen.get("note"), 5);
        LinearLayout resultButtons = new LinearLayout(this); resultButtons.setOrientation(LinearLayout.HORIZONTAL);
        String[] statuses = {"VYHOVUJE", "NEVYHOVUJE", "NETÝKÁ SE"};
        int[] colors = {C_GREEN, C_RED, C_MUTED};
        for (int i = 0; i < statuses.length; i++) {
            final String status = statuses[i];
            Button choice = smallButton(status, status.equals(chosen.get("result")) ? colors[i] : C_BG,
                    status.equals(chosen.get("result")) ? Color.WHITE : C_TEXT, v -> {
                        db.updateChecklist(chosen.id(), true, status, s(notes)); showChecklist(false);
                    });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(50), 1); if (i > 0) lp.leftMargin = dp(6);
            resultButtons.addView(choice, lp);
        }
        detail.addView(resultButtons, marginBottom(dp(20)));
        detail.addView(smallButton("ULOŽIT POZNÁMKU", C_ORANGE, C_TEXT, v -> {
            db.updateChecklist(chosen.id(), chosen.bool("done"), chosen.get("result"), s(notes)); showChecklist(false);
        }), marginBottom(dp(10)));
        if ("NEVYHOVUJE".equals(chosen.get("result"))) detail.addView(smallButton("＋ VYTVOŘIT ZÁVADU", C_RED, Color.WHITE, v -> defectFromChecklist(chosen, s(notes))), marginBottom(dp(10)));
        detail.addView(text("Fotografie a závady se zapisují v samostatných částech této revize.", 12, C_MUTED, false));
    }

    private void defectFromChecklist(Db.Row point, String finding) {
        LinearLayout f = form();
        EditText description = fieldMulti(f, "Text závady", finding.isEmpty() ? point.get("label") : finding, 4);
        Spinner severity = spinner(f, "Klasifikace", new String[]{"", "C1", "C2", "C3"}, 0);
        new AlertDialog.Builder(this).setTitle("Závada z prohlídky").setView(dialogScroll(f)).setNegativeButton("Zrušit", null)
                .setPositiveButton("Vytvořit", (d, w) -> {
                    if (s(description).isEmpty()) return;
                    db.addDefect(revisionId, s(description), String.valueOf(severity.getSelectedItem()), "Neodstraněna", "Kontrolní bod: " + point.get("label"));
                    showChecklist(false);
                }).show();
    }

    private void showTabletMeasurements() {
        clearBody("Měření", "Prvek → měřicí body, spojitost a chrániče");
        addRevisionContext();
        List<Db.Row> rows = db.measurements(revisionId);
        LinearLayout columns = tabletColumns();
        LinearLayout list = tabletPanel(columns, 5);
        LinearLayout detail = tabletPanel(columns, 6);
        list.addView(smallButton("＋ PŘIDAT OBVOD / ZAŘÍZENÍ", C_ORANGE, C_TEXT, v -> measurementDialog(null, "CIRCUIT")), marginBottom(dp(12)));
        list.addView(tabletMeasurementHeader(), marginBottom(dp(4)));
        if (rows.isEmpty()) {
            detail.addView(text("Založ obvod nebo zařízení. Měření pak přidej přímo k němu.", 17, C_MUTED, false));
            return;
        }
        Db.Row active = null;
        for (Db.Row r : rows) if (r.id() == selectedMeasurementId) active = r;
        if (active == null) { active = rows.get(0); selectedMeasurementId = active.id(); }
        for (Db.Row r : rows) list.addView(tabletMeasurementRow(r), marginBottom(dp(4)));
        final Db.Row chosen = active;
        detail.addView(text(chosen.get("element"), 21, C_TEXT, true), marginBottom(dp(8)));
        detail.addView(text(rowTypeLabel(measurementRowType(chosen)) + "  •  " + chosen.get("measure_type"), 13, C_MUTED, false), marginBottom(dp(14)));
        LinearLayout valueGrid = measurementValueGrid(chosen);
        if (valueGrid.getChildCount() > 0) detail.addView(valueGrid, marginBottom(dp(12)));
        if (!chosen.get("note").isEmpty()) detail.addView(text(chosen.get("note"), 14, C_MUTED, false), marginBottom(dp(12)));
        detail.addView(smallButton("UPRAVIT ÚDAJE A HODNOTY", C_ORANGE, C_TEXT, v -> measurementDialog(chosen)), marginBottom(dp(12)));
        String kind = measurementRowType(chosen);
        Db.Row owner = chosen;
        if (!isTreeParent(kind) && !chosen.get("parent_key").isEmpty()) {
            for (Db.Row r : rows) if (chosen.get("parent_key").equals(r.get("item_key"))) { owner = r; break; }
        }
        if (isTreeParent(measurementRowType(owner))) {
            final Db.Row parent = owner;
            detail.addView(text("Přidat k prvku " + parent.get("element"), 13, C_MUTED, true), marginBottom(dp(7)));
            LinearLayout actions = new LinearLayout(this); actions.setOrientation(LinearLayout.HORIZONTAL);
            String[] labels = {"MĚŘICÍ BOD", "SPOJITOST", "RCD / RCBO"};
            String[] types = {"POINT", "CONTINUITY", "RCD"};
            for (int i = 0; i < labels.length; i++) {
                final String t = types[i];
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(48), 1); if (i > 0) lp.leftMargin = dp(6);
                actions.addView(smallButton("＋ " + labels[i], C_BG, C_TEXT, v -> measurementDialog(null, t, parent)), lp);
            }
            detail.addView(actions, marginBottom(dp(14)));
        }
        String parentKey = chosen.get("item_key");
        if (!parentKey.isEmpty() && isTreeParent(kind)) {
            for (Db.Row r : rows) if (parentKey.equals(r.get("parent_key"))) {
                detail.addView(text("• " + r.get("element") + "   " + valuesText(r), 14, C_TEXT, false), marginBottom(dp(8)));
            }
        }
    }

    private LinearLayout tabletMeasurementHeader() {
        LinearLayout row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); row.setPadding(dp(8), dp(5), dp(8), dp(5));
        row.addView(tableCell("PRVEK / BOD", 11, C_MUTED, true), new LinearLayout.LayoutParams(0, dp(30), 4));
        row.addView(tableCell("TYP", 11, C_MUTED, true), new LinearLayout.LayoutParams(0, dp(30), 2));
        row.addView(tableCell("HODNOTY", 11, C_MUTED, true), new LinearLayout.LayoutParams(0, dp(30), 4));
        row.addView(tableCell("STAV", 11, C_MUTED, true), new LinearLayout.LayoutParams(0, dp(30), 1));
        return row;
    }

    private LinearLayout tabletMeasurementRow(Db.Row r) {
        String kind = measurementRowType(r);
        boolean child = isTreeChild(kind) && !r.get("parent_key").isEmpty();
        LinearLayout row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(8), dp(6), dp(8), dp(6));
        row.setBackground(rounded(r.id() == selectedMeasurementId ? Color.rgb(255, 243, 220) : Color.WHITE, C_BORDER, 8));
        row.setClickable(true); row.setOnClickListener(v -> { selectedMeasurementId = r.id(); showMeasurements(false); });
        String element = (child ? "↳  " : "") + (r.get("element").isEmpty() ? "Bez označení" : r.get("element"));
        row.addView(tableCell(element, 13, C_TEXT, true), new LinearLayout.LayoutParams(0, dp(46), 4));
        row.addView(tableCell(shortRowType(kind), 11, rowTypeColor(kind), true), new LinearLayout.LayoutParams(0, dp(46), 2));
        String values = valuesText(r); if (values.isEmpty()) values = "—";
        row.addView(tableCell(values, 11, C_TEXT, false), new LinearLayout.LayoutParams(0, dp(46), 4));
        row.addView(tableCell(r.bool("done") ? "✓" : "—", 17, r.bool("done") ? C_GREEN : C_MUTED, true), new LinearLayout.LayoutParams(0, dp(46), 1));
        return row;
    }

    private TextView tableCell(String value, int size, int color, boolean bold) {
        TextView t = text(value, size, color, bold); t.setGravity(Gravity.LEFT | Gravity.CENTER_VERTICAL); t.setMaxLines(2); t.setPadding(dp(3), 0, dp(3), 0); return t;
    }

    private String shortRowType(String kind) {
        if ("CONTINUITY".equals(kind)) return "SPOJ.";
        if ("POINT".equals(kind)) return "BOD";
        if ("MEASUREMENT".equals(kind)) return "MĚŘ.";
        if ("FUNCTION".equals(kind)) return "FUNKCE";
        return rowTypeLabel(kind);
    }

    private LinearLayout measurementValueGrid(Db.Row r) {
        LinearLayout grid = new LinearLayout(this); grid.setOrientation(LinearLayout.VERTICAL);
        String[] types = {"Klasické", "L-PE / Zs / Ik", "Izolační odpor", "Spojitost", "RCD", "RCBO", "Napětí", "Funkční", "Jiné"};
        String[][] labels = {
                {"Hodnota 1", "Hodnota 2", "Hodnota 3", "Hodnota 4"},
                {"Napětí U", "Impedance Zs", "Zkratový proud Ik", "Další hodnota"},
                {"Riso L-PE", "Riso L-N", "Riso N-PE", "Další Riso"},
                {"Odpor spojitosti RPE", "Další bod", "Další bod", "Další bod"},
                {"IΔn", "Vybavovací čas t", "Dotykové napětí", "Další hodnota"},
                {"IΔn", "Vybavovací čas t", "Zs / Ik", "Další hodnota"},
                {"L-N", "L-PE", "N-PE", "L-L"},
                {"Výsledek / hodnota", "Hodnota 2", "Hodnota 3", "Hodnota 4"},
                {"Hodnota 1", "Hodnota 2", "Hodnota 3", "Hodnota 4"}
        };
        int preset = indexOf(types, r.get("measure_type"));
        for (int i = 1; i <= 4; i++) {
            String value = nz(r.get("v" + i)); if (value.isEmpty()) continue;
            String unit = nz(r.get("unit" + i));
            LinearLayout line = new LinearLayout(this); line.setOrientation(LinearLayout.HORIZONTAL); line.setPadding(dp(10), dp(7), dp(10), dp(7));
            line.setBackground(rounded(C_BG, C_BORDER, 8));
            line.addView(text(labels[preset][i - 1], 12, C_MUTED, true), new LinearLayout.LayoutParams(0, dp(30), 1));
            TextView val = text(value + (unit.isEmpty() ? "" : " " + unit), 15, C_TEXT, true); val.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL);
            line.addView(val, new LinearLayout.LayoutParams(0, dp(30), 1));
            grid.addView(line, marginBottom(dp(5)));
        }
        return grid;
    }

    private void showInfluences(boolean nav) {
        if (nav) push("influences"); else screen = "influences";
        clearBody("Vnější vlivy", "Popis prostoru, klasifikace a opatření pro každý abnormální vliv");
        addRevisionContext();
        List<Db.Row> rooms = db.influenceRooms(revisionId);
        LinearLayout list, detail;
        if (tabletLayout()) {
            LinearLayout columns = tabletColumns(); list = tabletPanel(columns, 4); detail = tabletPanel(columns, 7);
        } else { list = body; detail = body; }
        list.addView(smallButton("＋ PŘIDAT MÍSTNOST", C_ORANGE, C_TEXT, v -> influenceRoomDialog(null)), marginBottom(dp(12)));
        Db.Row active = null;
        for (Db.Row r : rooms) if (r.id() == selectedRoomId) active = r;
        if (active == null && !rooms.isEmpty()) { active = rooms.get(0); selectedRoomId = active.id(); }
        for (Db.Row r : rooms) {
            Button item = smallButton(r.get("name"), r.id() == selectedRoomId ? Color.rgb(255, 243, 220) : C_BG, C_TEXT,
                    v -> { selectedRoomId = r.id(); showInfluences(false); });
            item.setAllCaps(false); item.setGravity(Gravity.LEFT | Gravity.CENTER_VERTICAL);
            list.addView(item, marginBottom(dp(6)));
        }
        if (active == null) { detail.addView(text("Přidej místnost nebo posuzovaný prostor.", 16, C_MUTED, false)); return; }
        final Db.Row room = active;
        detail.addView(text(room.get("name"), 20, C_TEXT, true), marginBottom(dp(8)));
        if (!room.get("description").isEmpty()) detail.addView(text(room.get("description"), 14, C_MUTED, false), marginBottom(dp(12)));
        detail.addView(smallButton("UPRAVIT POPIS MÍSTNOSTI", C_BG, C_TEXT, v -> influenceRoomDialog(room)), marginBottom(dp(12)));
        detail.addView(smallButton("ODSTRANIT MÍSTNOST", C_BG, C_RED, v -> new AlertDialog.Builder(this)
                .setTitle("Odstranit místnost?").setMessage("Smažou se i všechny její vnější vlivy.")
                .setNegativeButton("Zrušit", null).setPositiveButton("Odstranit", (d, w) -> {
                    db.deleteInfluenceRoom(revisionId, room.id()); selectedRoomId = 0; showInfluences(false);
                }).show()), marginBottom(dp(12)));
        detail.addView(smallButton("＋ PŘIDAT KÓD VLIVU", C_ORANGE, C_TEXT, v -> influenceItemDialog(room.id(), null)), marginBottom(dp(12)));
        for (Db.Row item : db.influenceItems(room.id())) {
            LinearLayout card = card();
            card.addView(text(item.get("code") + "  " + item.get("description"), 16, C_TEXT, true), marginBottom(dp(6)));
            if (!item.get("measure").isEmpty()) card.addView(text("Opatření: " + item.get("measure"), 13, C_MUTED, false));
            card.addView(smallButton("UPRAVIT", C_BG, C_TEXT, v -> influenceItemDialog(room.id(), item)), marginBottom(dp(4)));
            card.addView(smallButton("ODSTRANIT VLIV", C_BG, C_RED, v -> new AlertDialog.Builder(this)
                    .setTitle("Odstranit " + item.get("code") + "?").setNegativeButton("Zrušit", null)
                    .setPositiveButton("Odstranit", (d, w) -> { db.deleteInfluenceItem(room.id(), item.id()); showInfluences(false); }).show()));
            detail.addView(card, marginBottom(dp(8)));
        }
        detail.addView(text("Pracovní záznam vnějších vlivů zůstává v tabletu a v úplné JSON záloze. NAS synchronizace a výstupní protokol zatím tuto část nepřenášejí.", 12, C_MUTED, false));
    }

    private void influenceRoomDialog(Db.Row row) {
        LinearLayout f = form();
        EditText name = field(f, "Místnost / prostor", row == null ? "" : row.get("name"));
        EditText description = fieldMulti(f, "Popis posuzovaného prostoru", row == null ? "" : row.get("description"), 5);
        new AlertDialog.Builder(this).setTitle(row == null ? "Nový prostor" : "Upravit prostor").setView(dialogScroll(f))
                .setNegativeButton("Zrušit", null).setPositiveButton("Uložit", (d, w) -> {
                    if (s(name).isEmpty()) { Toast.makeText(this, "Vyplň název prostoru.", Toast.LENGTH_SHORT).show(); return; }
                    selectedRoomId = db.saveInfluenceRoom(revisionId, row == null ? 0 : row.id(), s(name), s(description));
                    showInfluences(false);
                }).show();
    }

    private void influenceItemDialog(long roomId, Db.Row row) {
        LinearLayout f = form();
        EditText code = field(f, "Kód vlivu (např. BA4)", row == null ? "" : row.get("code"));
        EditText description = fieldMulti(f, "Klasifikace / zdůvodnění", row == null ? "" : row.get("description"), 3);
        EditText measure = fieldMulti(f, "Požadované opatření", row == null ? "" : row.get("measure"), 4);
        new AlertDialog.Builder(this).setTitle(row == null ? "Vnější vliv" : "Upravit vnější vliv").setView(dialogScroll(f))
                .setNegativeButton("Zrušit", null).setPositiveButton("Uložit", (d, w) -> {
                    if (s(code).isEmpty()) { Toast.makeText(this, "Vyplň kód vlivu.", Toast.LENGTH_SHORT).show(); return; }
                    db.saveInfluenceItem(roomId, row == null ? 0 : row.id(), s(code).toUpperCase(), s(description), s(measure));
                    showInfluences(false);
                }).show();
    }

    private void showChecklist(boolean nav) {
        if (nav) push("checklist"); else screen = "checklist";
        if (tabletLayout()) { showTabletChecklist(); return; }
        clearBody("Prohlídka / kontrola", "výběr z databáze • rychlé odškrtnutí • výsledek");
        addRevisionContext();
        List<Db.Row> rows = db.checklist(revisionId);
        int complete = 0; for (Db.Row x : rows) if (x.bool("done")) complete++;
        addProgress(complete, rows.size(), "Prošlo " + complete + " / " + rows.size() + " bodů");

        LinearLayout top=new LinearLayout(this);top.setOrientation(LinearLayout.HORIZONTAL);
        top.addView(smallButton("＋ VYBRAT Z DATABÁZE",C_ORANGE,Color.BLACK,v->{push("inspectionCatalog");showInspectionCatalog(false);}),new LinearLayout.LayoutParams(0,dp(48),2));
        LinearLayout.LayoutParams ownLp=new LinearLayout.LayoutParams(0,dp(48),1);ownLp.leftMargin=dp(7);
        Button own=smallButton("＋ VLASTNÍ",Color.WHITE,C_TEXT,v->{
            LinearLayout f=form();EditText e=fieldMulti(f,"Text kontrolního bodu","",3);
            new AlertDialog.Builder(this).setTitle("Vlastní kontrolní bod").setView(dialogScroll(f)).setNegativeButton("Zrušit",null).setPositiveButton("Přidat",(d,w)->{if(!s(e).isEmpty()){db.addChecklist(revisionId,s(e));showChecklist(false);}}).show();
        });own.setBackground(rounded(Color.WHITE,C_BORDER,10));top.addView(own,ownLp);
        body.addView(top,marginBottom(dp(8)));

        LinearLayout templates=new LinearLayout(this);templates.setOrientation(LinearLayout.HORIZONTAL);
        Button nv=smallButton("NV 190/2022 • 11 bodů",Color.WHITE,C_TEXT,v->{
            int n=db.addChecklistGroup(revisionId,"NV 190/2022 Sb. – příloha č. 1, část A");
            Toast.makeText(this,n>0?"Přidáno "+n+" bodů.":"Body už jsou v revizi.",Toast.LENGTH_SHORT).show();showChecklist(false);
        });nv.setBackground(rounded(Color.WHITE,C_BORDER,10));templates.addView(nv,new LinearLayout.LayoutParams(0,dp(44),1));
        LinearLayout.LayoutParams csLp=new LinearLayout.LayoutParams(0,dp(44),1);csLp.leftMargin=dp(7);
        Button cs=smallButton("ČSN 33 2000-6 • 16 bodů",Color.WHITE,C_TEXT,v->{
            int n=db.addChecklistGroup(revisionId,"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F");
            Toast.makeText(this,n>0?"Přidáno "+n+" bodů.":"Body už jsou v revizi.",Toast.LENGTH_SHORT).show();showChecklist(false);
        });cs.setBackground(rounded(Color.WHITE,C_BORDER,10));templates.addView(cs,csLp);
        body.addView(templates,marginBottom(dp(12)));

        if (rows.isEmpty()) {
            emptyState("Prohlídka zatím nemá vybrané body.", "Vyber body z databáze, vlož standardní sadu nebo přidej vlastní kontrolní bod.", "OTEVŘÍT DATABÁZI", v -> {push("inspectionCatalog");showInspectionCatalog(false);});
            return;
        }

        String lastGroup=null;
        for (Db.Row r : rows) {
            String group=nz(r.get("group_name")).trim();if(group.isEmpty())group="Ostatní / převzaté body";
            if(!group.equals(lastGroup)){
                TextView gh=text(group,14,C_TEXT,true);gh.setPadding(dp(2),dp(8),dp(2),dp(6));body.addView(gh);lastGroup=group;
            }
            LinearLayout c=card();c.setPadding(dp(10),dp(8),dp(10),dp(8));
            LinearLayout row=new LinearLayout(this);row.setOrientation(LinearLayout.HORIZONTAL);row.setGravity(Gravity.TOP);
            CheckBox done=new CheckBox(this);done.setChecked(r.bool("done"));row.addView(done,new LinearLayout.LayoutParams(dp(48),dp(48)));
            LinearLayout tx=new LinearLayout(this);tx.setOrientation(LinearLayout.VERTICAL);
            tx.addView(text(r.get("label"),14,C_TEXT,true));
            String source=nz(r.get("source_ref"));if(!source.isEmpty()){TextView sr=text(source,11,C_MUTED,false);sr.setPadding(0,dp(3),0,0);tx.addView(sr);}
            if(!r.get("note").isEmpty()){TextView note=text(r.get("note"),12,C_MUTED,false);note.setPadding(0,dp(3),0,0);tx.addView(note);}
            row.addView(tx,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
            String res=nz(r.get("result"));if(res.isEmpty())res="NEPROVEDENO";
            TextView chip=pill(res,inspectionResultColor(res),Color.WHITE);row.addView(chip,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,dp(28)));
            Button edit=smallButton("⋮",Color.WHITE,C_TEXT,v->checklistEditDialog(r));edit.setTextSize(19);edit.setBackground(rounded(Color.WHITE,C_BORDER,10));
            LinearLayout.LayoutParams ep=new LinearLayout.LayoutParams(dp(46),dp(38));ep.leftMargin=dp(5);row.addView(edit,ep);
            c.addView(row);
            done.setOnCheckedChangeListener((b,checked)->{
                String result=nz(r.get("result"));
                if(checked && (result.isEmpty()||"NEPROVEDENO".equals(result)))result="VYHOVUJE";
                if(!checked && !"NEVYHOVUJE".equals(result))result="NEPROVEDENO";
                db.updateChecklist(r.id(),checked,result,r.get("note"));
                showChecklist(false);
            });
            body.addView(c,marginBottom(dp(6)));
        }
    }

    private int inspectionResultColor(String result){
        if("VYHOVUJE".equals(result))return C_GREEN;
        if("NEVYHOVUJE".equals(result))return C_RED;
        if("NEPROVEDENO".equals(result))return C_MUTED;
        return C_ORANGE;
    }

    private void checklistEditDialog(Db.Row r){
        LinearLayout l=form();
        TextView label=text(r.get("label"),15,C_TEXT,true);label.setPadding(dp(2),dp(4),dp(2),dp(8));l.addView(label);
        if(!r.get("source_ref").isEmpty())l.addView(text(r.get("source_ref"),12,C_MUTED,false));
        String[] results={"VYHOVUJE","NEVYHOVUJE","NEPROVEDENO"};
        Spinner result=spinner(l,"Výsledek",results,indexOf(results,r.get("result")));
        EditText note=fieldMulti(l,"Poznámka",r.get("note"),3);
        new AlertDialog.Builder(this).setTitle("Výsledek prohlídky").setView(dialogScroll(l)).setNegativeButton("Zrušit",null).setPositiveButton("Uložit",(d,w)->{
            String res=String.valueOf(result.getSelectedItem());boolean done=!"NEPROVEDENO".equals(res);
            db.updateChecklist(r.id(),done,res,s(note));showChecklist(false);
        }).show();
    }

    private void showInspectionCatalog(boolean nav){
        if(nav)push("inspectionCatalog");else screen="inspectionCatalog";
        clearBody("Databáze prohlídek","vyber kontrolní body do této revize");
        addRevisionContext();

        EditText q=edit("Hledat podle skupiny, textu nebo normy");
        q.setSingleLine(true);q.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        body.addView(q,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(52)));

        LinearLayout quick=new LinearLayout(this);quick.setOrientation(LinearLayout.HORIZONTAL);
        Button nv=smallButton("PŘIDAT NV 190/2022",C_ORANGE,Color.BLACK,v->{int n=db.addChecklistGroup(revisionId,"NV 190/2022 Sb. – příloha č. 1, část A");Toast.makeText(this,"Přidáno: "+n,Toast.LENGTH_SHORT).show();showInspectionCatalog(false);});
        quick.addView(nv,new LinearLayout.LayoutParams(0,dp(44),1));
        LinearLayout.LayoutParams qp=new LinearLayout.LayoutParams(0,dp(44),1);qp.leftMargin=dp(7);
        Button cs=smallButton("PŘIDAT ČSN 33 2000-6",Color.WHITE,C_TEXT,v->{int n=db.addChecklistGroup(revisionId,"ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F");Toast.makeText(this,"Přidáno: "+n,Toast.LENGTH_SHORT).show();showInspectionCatalog(false);});cs.setBackground(rounded(Color.WHITE,C_BORDER,10));quick.addView(cs,qp);
        LinearLayout.LayoutParams qlp=marginBottom(dp(10));qlp.topMargin=dp(8);body.addView(quick,qlp);

        LinearLayout list=new LinearLayout(this);list.setOrientation(LinearLayout.VERTICAL);body.addView(list);
        Runnable refresh=()->{
            list.removeAllViews();List<Db.Row> rows=db.inspectionCatalog(q.getText().toString());
            String last=null;
            for(Db.Row r:rows){
                String group=r.get("group_name");
                if(!group.equals(last)){TextView g=text(group,13,C_TEXT,true);g.setPadding(dp(2),dp(9),dp(2),dp(5));list.addView(g);last=group;}
                boolean added=db.checklistHasCatalog(revisionId,r.id());
                LinearLayout c=card();c.setPadding(dp(10),dp(8),dp(10),dp(8));
                LinearLayout rr=new LinearLayout(this);rr.setOrientation(LinearLayout.HORIZONTAL);rr.setGravity(Gravity.CENTER_VERTICAL);
                LinearLayout tx=new LinearLayout(this);tx.setOrientation(LinearLayout.VERTICAL);tx.addView(text(r.get("label"),13,C_TEXT,true));
                if(!r.get("source_ref").isEmpty()){TextView src=text(r.get("source_ref"),11,C_MUTED,false);src.setPadding(0,dp(3),0,0);tx.addView(src);}
                rr.addView(tx,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
                Button add=smallButton(added?"PŘIDÁNO":"PŘIDAT",added?Color.rgb(232,245,236):C_ORANGE,added?C_GREEN:Color.BLACK,v->{if(db.addChecklistFromCatalog(revisionId,r.id())>0){Toast.makeText(this,"Bod přidán.",Toast.LENGTH_SHORT).show();showInspectionCatalog(false);}});
                add.setEnabled(!added);rr.addView(add,new LinearLayout.LayoutParams(dp(92),dp(40)));c.addView(rr);list.addView(c,marginBottom(dp(5)));
            }
            if(rows.isEmpty())list.addView(emptyStateView("V databázi nebyl nalezen žádný bod.","Zkus jiné hledání.","VYMAZAT HLEDÁNÍ",v->{q.setText("");}));
        };
        q.addTextChangedListener(new SimpleTextWatcher(refresh));refresh.run();
    }

    private void showPhotos(boolean nav) {
        if (nav) push("photos"); else screen = "photos";
        clearBody("Pracovní fotografie", "fotografie zůstávají v pracovní složce i po přiřazení k závadě");
        body.addView(primaryAction("VYFOTIT DO PRACOVNÍ SLOŽKY", "Rychlé focení bez nutnosti hned zakládat závadu", v -> takePhoto()), marginBottom(dp(12)));
        List<Db.Row> photos = db.photos(revisionId);
        if (photos.isEmpty()) {
            emptyState("Pracovní složka je prázdná.", "Vyfoť dokumentaci a závady vytřiď až později.", "VYFOTIT", v -> takePhoto());
            return;
        }

        for (Db.Row p : photos) {
            LinearLayout c = card();
            ImageView img = thumbnailView(p.get("uri"));
            if (img != null) {
                img.setOnClickListener(v -> openPhoto(p.get("uri")));
                c.addView(img, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(190)));
            }
            String title = p.get("title").isEmpty() ? "Pracovní fotografie" : p.get("title");
            TextView t = text(title, 16, C_TEXT, true); t.setPadding(0, dp(8), 0, 0); c.addView(t);
            int linked = db.linkedDefectCount(p.id());
            if (linked > 0) c.addView(pill("Použito v závadách: " + linked, C_GREEN, Color.WHITE));
            if (!p.get("note").isEmpty()) c.addView(text(p.get("note"), 13, C_MUTED, false));

            LinearLayout r1 = new LinearLayout(this); r1.setOrientation(LinearLayout.HORIZONTAL);
            Button edit = smallButton("POPIS", Color.WHITE, C_TEXT, v -> photoEditDialog(p)); edit.setBackground(rounded(Color.WHITE, C_BORDER, 10));
            Button defect = smallButton("VYTVOŘIT ZÁVADU", C_RED, Color.WHITE, v -> defectFromPhoto(p));
            r1.addView(edit, new LinearLayout.LayoutParams(0, dp(44), 1));
            LinearLayout.LayoutParams dlp = new LinearLayout.LayoutParams(0, dp(44), 2); dlp.leftMargin = dp(8); r1.addView(defect, dlp);
            LinearLayout.LayoutParams rlp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)); rlp.topMargin = dp(10); c.addView(r1, rlp);
            Button attach = smallButton("KOPÍROVAT DO EXISTUJÍCÍ ZÁVADY", C_DARK, Color.WHITE, v -> attachPhotoDialog(p));
            LinearLayout.LayoutParams alp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)); alp.topMargin = dp(7); c.addView(attach, alp);
            body.addView(c, marginBottom(dp(10)));
        }
    }

    private void takePhoto() {
        if (Build.VERSION.SDK_INT <= 28 && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, REQ_STORAGE);
            return;
        }
        launchCamera();
    }

    private void launchCamera() {
        try {
            ContentValues cv = new ContentValues();
            cv.put(MediaStore.Images.Media.DISPLAY_NAME, "PZ_" + System.currentTimeMillis() + ".jpg");
            cv.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
            if (Build.VERSION.SDK_INT >= 29) cv.put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/PZ-REVIZE");
            pendingPhotoUri = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, cv);
            if (pendingPhotoUri == null) { Toast.makeText(this, "Nelze připravit soubor fotografie.", Toast.LENGTH_LONG).show(); return; }
            Intent i = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
            i.putExtra(MediaStore.EXTRA_OUTPUT, pendingPhotoUri);
            i.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivityForResult(i, REQ_CAMERA);
        } catch (Exception e) {
            if (pendingPhotoUri != null) try { getContentResolver().delete(pendingPhotoUri, null, null); } catch (Exception ignored) { }
            pendingPhotoUri = null;
            Toast.makeText(this, "Fotoaparát není dostupný: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_STORAGE) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) launchCamera();
            else Toast.makeText(this, "Bez oprávnění nelze na tomto Androidu fotografii uložit.", Toast.LENGTH_LONG).show();
        }
    }

    private ImageView thumbnailView(String value) {
        try {
            Uri uri = Uri.parse(value);
            ImageView iv = new ImageView(this);
            iv.setAdjustViewBounds(true);
            iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
            Bitmap b;
            if (Build.VERSION.SDK_INT >= 29) b = getContentResolver().loadThumbnail(uri, new android.util.Size(900, 500), null);
            else try (InputStream in = getContentResolver().openInputStream(uri)) {
                BitmapFactory.Options o = new BitmapFactory.Options(); o.inSampleSize = 4; b = BitmapFactory.decodeStream(in, null, o);
            }
            if (b == null) return null;
            iv.setImageBitmap(b);
            iv.setBackground(rounded(Color.rgb(235, 238, 242), C_BORDER, 10));
            return iv;
        } catch (Exception e) { return null; }
    }

    private void openPhoto(String value) {
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(value));
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(i);
        } catch (Exception e) { Toast.makeText(this, "Fotografii nelze otevřít.", Toast.LENGTH_SHORT).show(); }
    }

    private void photoEditDialog(Db.Row p) {
        LinearLayout l = form();
        EditText title = field(l, "Popis fotografie", p.get("title"));
        EditText note = fieldMulti(l, "Poznámka", p.get("note"), 3);
        new AlertDialog.Builder(this).setTitle("Pracovní fotografie").setView(dialogScroll(l)).setNegativeButton("Zrušit", null).setPositiveButton("Uložit", (d, w) -> { db.updatePhoto(p.id(), s(title), s(note)); showPhotos(false); }).show();
    }

    private void defectFromPhoto(Db.Row p) {
        LinearLayout l = form();
        EditText text = fieldMulti(l, "Text závady", p.get("title"), 3);
        Spinner sev = spinner(l, "Klasifikace", new String[]{"", "C1", "C2", "C3"}, 0);
        EditText note = fieldMulti(l, "Poznámka", p.get("note"), 2);
        new AlertDialog.Builder(this).setTitle("Vytvořit závadu z fotografie").setView(dialogScroll(l)).setNegativeButton("Zrušit", null).setPositiveButton("Vytvořit", (d, w) -> {
            if (s(text).isEmpty()) { Toast.makeText(this, "Doplň text závady.", Toast.LENGTH_LONG).show(); return; }
            long did = db.addDefect(revisionId, s(text), String.valueOf(sev.getSelectedItem()), "Neodstraněna", s(note));
            db.linkPhotoToDefect(p.id(), did);
            Toast.makeText(this, "Závada vytvořena. Fotografie zůstala i v pracovní složce.", Toast.LENGTH_LONG).show();
            showPhotos(false);
        }).show();
    }

    private void attachPhotoDialog(Db.Row p) {
        List<Db.Row> defects = db.defects(revisionId);
        if (defects.isEmpty()) { defectFromPhoto(p); return; }
        String[] labels = new String[defects.size()];
        for (int i = 0; i < defects.size(); i++) labels[i] = (i + 1) + ". " + defects.get(i).get("text");
        new AlertDialog.Builder(this).setTitle("Kopírovat fotografii do závady").setItems(labels, (d, which) -> {
            db.linkPhotoToDefect(p.id(), defects.get(which).id());
            Toast.makeText(this, "Fotografie byla přiřazena k závadě.", Toast.LENGTH_SHORT).show();
            showPhotos(false);
        }).setNegativeButton("Zrušit", null).show();
    }

    private void showDefects(boolean nav) {
        if (nav) push("defects"); else screen = "defects";
        clearBody("Závady", "evidence závad a fotografie");
        body.addView(primaryAction("＋ NOVÁ ZÁVADA", "Založit závadu ručně", v -> defectDialog(null)), marginBottom(dp(12)));
        List<Db.Row> rows = db.defects(revisionId);
        if (rows.isEmpty()) {
            emptyState("Zatím nejsou evidovány žádné závady.", "Závadu můžeš vytvořit ručně nebo přímo z pracovní fotografie.", "NOVÁ ZÁVADA", v -> defectDialog(null));
            return;
        }
        int n = 0;
        for (Db.Row d : rows) {
            n++;
            LinearLayout c = card();
            LinearLayout first = new LinearLayout(this); first.setOrientation(LinearLayout.HORIZONTAL); first.setGravity(Gravity.CENTER_VERTICAL);
            first.addView(text(n + ". " + d.get("text"), 16, C_TEXT, true), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
            if (!d.get("severity").isEmpty()) first.addView(pill(d.get("severity"), severityColor(d.get("severity")), Color.WHITE));
            c.addView(first);
            c.addView(text(join(d.get("status"), d.get("note")), 13, C_MUTED, false));
            int pc = db.defectPhotoCount(d.id());
            if (pc > 0) c.addView(text("Fotografie: " + pc, 12, C_GREEN, true));
            Button edit = smallButton("UPRAVIT ZÁVADU", Color.WHITE, C_TEXT, v -> defectDialog(d)); edit.setBackground(rounded(Color.WHITE, C_BORDER, 10));
            LinearLayout.LayoutParams elp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)); elp.topMargin = dp(8); c.addView(edit, elp);
            body.addView(c, marginBottom(dp(8)));
        }
    }

    private int severityColor(String s) {
        if ("C1".equals(s)) return C_RED;
        if ("C2".equals(s)) return Color.rgb(217, 119, 6);
        if ("C3".equals(s)) return Color.rgb(37, 99, 235);
        return C_MUTED;
    }

    private void defectDialog(Db.Row d) {
        LinearLayout l = form();
        EditText text = fieldMulti(l, "Text závady", d == null ? "" : d.get("text"), 3);
        String[] sevValues = {"", "C1", "C2", "C3"};
        Spinner sev = spinner(l, "Klasifikace", sevValues, d == null ? 0 : indexOf(sevValues, d.get("severity")));
        String[] statuses = {"Neodstraněna", "Odstraněna", "K ověření"};
        Spinner status = spinner(l, "Stav", statuses, d == null ? 0 : indexOf(statuses, d.get("status")));
        EditText note = fieldMulti(l, "Poznámka", d == null ? "" : d.get("note"), 2);
        new AlertDialog.Builder(this).setTitle(d == null ? "Nová závada" : "Upravit závadu").setView(dialogScroll(l)).setNegativeButton("Zrušit", null).setPositiveButton("Uložit", (dlg, w) -> {
            if (s(text).isEmpty()) { Toast.makeText(this, "Doplň text závady.", Toast.LENGTH_LONG).show(); return; }
            if (d == null) db.addDefect(revisionId, s(text), String.valueOf(sev.getSelectedItem()), String.valueOf(status.getSelectedItem()), s(note));
            else db.updateDefect(d.id(), s(text), String.valueOf(sev.getSelectedItem()), String.valueOf(status.getSelectedItem()), s(note));
            showDefects(false);
        }).show();
    }


    private void syncMenu() {
        int pending = SyncStore.dirtyCount(db);
        String last = SyncClient.lastSync(this);
        String error = SyncClient.lastError(this);
        String title = "Synchronizace s NAS";
        String[] items = {
                "Synchronizovat nyní (čeká " + pending + " změn)",
                "Otestovat spojení s NAS",
                "Nastavení NAS",
                "Záloha / přenos dat"
        };
        AlertDialog.Builder b = new AlertDialog.Builder(this).setTitle(title);
        String status = last.isEmpty() ? "" : "Poslední úspěšná synchronizace: " + last;
        if (!error.isEmpty()) status += (status.isEmpty() ? "" : "\n\n") + "Poslední chyba: " + error + "\n\nLokální změny zůstávají zachované a čekají na další pokus.";
        if (!status.isEmpty()) b.setMessage(status);
        b.setItems(items, (d, which) -> {
            if (which == 0) startSync(true, false);
            else if (which == 1) testServer();
            else if (which == 2) syncSettingsDialog();
            else backupMenu();
        }).setNegativeButton("Zavřít", null).show();
    }

    private void syncSettingsDialog() {
        SharedPreferences p = SyncClient.prefs(this);
        LinearLayout l = form();
        String[] modes = {"AUTO", "LAN", "VPN"};
        Spinner mode = spinner(l, "Režim spojení", modes, indexOf(modes, p.getString("mode", "AUTO")));
        EditText lan = field(l, "Adresa NAS v LAN", p.getString("lan_url", "http://192.168.100.198:8767"));
        EditText vpn = field(l, "Adresa NAS přes VPN", p.getString("vpn_url", "http://100.108.171.83:8767"));
        EditText key = field(l, "API klíč", p.getString("api_key", ""));
        CheckBox auto = new CheckBox(this);
        auto.setText("Automaticky synchronizovat při spuštění, během práce a při odchodu z aplikace");
        auto.setChecked(p.getBoolean("auto_sync", true));
        auto.setTextColor(C_TEXT);
        l.addView(auto, marginBottom(dp(8)));
        TextView help = text("AUTO zkusí nejprve LAN adresu NAS a potom VPN adresu. Na NAS musí běžet PZ-REVIZE NAS Server s mobilním API. Pro LAN/VPN testování lze použít HTTP; pro přístup z internetu použij HTTPS/reverse proxy.", 12, C_MUTED, false);
        l.addView(help);
        new AlertDialog.Builder(this).setTitle("PZ-REVIZE NAS").setView(dialogScroll(l)).setNegativeButton("Zrušit", null).setPositiveButton("Uložit", (d,w) -> {
            p.edit().putString("mode", String.valueOf(mode.getSelectedItem())).putString("lan_url", s(lan)).putString("vpn_url", s(vpn)).putString("api_key", s(key)).putBoolean("auto_sync", auto.isChecked()).apply();
            Toast.makeText(this, "Nastavení NAS uloženo.", Toast.LENGTH_SHORT).show();
            if ("home".equals(screen)) showHome(false);
        }).show();
    }

    private void testServer() {
        if (syncRunning) { Toast.makeText(this, "Synchronizace právě probíhá.", Toast.LENGTH_SHORT).show(); return; }
        syncRunning = true;
        Toast.makeText(this, "Testuji spojení s NAS...", Toast.LENGTH_SHORT).show();
        SyncClient.test(this, r -> {
            syncRunning = false;
            new AlertDialog.Builder(this).setTitle(r.ok ? "Spojení s NAS je v pořádku" : "NAS není dostupný").setMessage(r.message).setPositiveButton("OK", null).show();
        });
    }

    private void startSync(boolean showResult, boolean pushOnly) {
        if (syncRunning || !SyncClient.configured(this)) {
            if (showResult && !SyncClient.configured(this)) syncSettingsDialog();
            return;
        }
        syncRunning = true;
        if (showResult) Toast.makeText(this, "Synchronizuji...", Toast.LENGTH_SHORT).show();
        SyncClient.sync(this, db, pushOnly, r -> {
            syncRunning = false;
            if (showResult) {
                AlertDialog.Builder dialog = new AlertDialog.Builder(this)
                        .setTitle(r.ok ? (r.conflicts > 0 ? "Synchronizace s konfliktem" : "Synchronizace dokončena") : "Synchronizace selhala")
                        .setMessage(r.message + ((r.ok && r.conflicts == 0) ? "" : "\n\nPráce může pokračovat offline. Neodeslané změny zůstávají v tabletu a další synchronizace je zkusí znovu."))
                        .setPositiveButton("Pokračovat offline", null);
                if (!r.ok || r.conflicts > 0) dialog.setNeutralButton("Nastavení NAS", (d,w) -> syncSettingsDialog());
                dialog.show();
            }
            if ("home".equals(screen) && !isFinishing()) showHome(false);
        });
    }

    private void backupMenu() {
        new AlertDialog.Builder(this).setTitle("Záloha / přenos dat").setItems(new String[]{
                "Exportovat mobilní databázi do JSON",
                "Importovat JSON – nahradí aktuální mobilní databázi"
        }, (d, which) -> { if (which == 0) startExport(); else startImport(); }).setNegativeButton("Zrušit", null).show();
    }

    private void startExport() {
        Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        i.setType("application/json");
        i.putExtra(Intent.EXTRA_TITLE, "PZ_REVIZE_MOBILE_" + System.currentTimeMillis() + ".json");
        startActivityForResult(i, REQ_EXPORT);
    }

    private void startImport() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.setType("application/json");
        i.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(i, REQ_IMPORT);
    }

    @Override protected void onActivityResult(int req, int result, Intent data) {
        super.onActivityResult(req, result, data);
        if (req == REQ_CAMERA && result != RESULT_OK) {
            if (pendingPhotoUri != null) try { getContentResolver().delete(pendingPhotoUri, null, null); } catch (Exception ignored) { }
            pendingPhotoUri = null;
            return;
        }
        if (result != RESULT_OK) return;
        try {
            if (req == REQ_CAMERA && pendingPhotoUri != null) {
                db.addPhoto(revisionId, pendingPhotoUri.toString(), "", "");
                pendingPhotoUri = null;
                showPhotos(false);
            } else if (req == REQ_EXPORT && data != null && data.getData() != null) {
                JSONObject root = db.exportAll();
                try (OutputStream o = getContentResolver().openOutputStream(data.getData())) {
                    if (o == null) throw new IllegalStateException("Výstupní soubor nelze otevřít.");
                    o.write(root.toString(2).getBytes(StandardCharsets.UTF_8));
                }
                Toast.makeText(this, "Záloha byla uložena.", Toast.LENGTH_LONG).show();
            } else if (req == REQ_IMPORT && data != null && data.getData() != null) {
                StringBuilder sb = new StringBuilder();
                try (BufferedReader br = new BufferedReader(new InputStreamReader(getContentResolver().openInputStream(data.getData()), StandardCharsets.UTF_8))) {
                    String line; while ((line = br.readLine()) != null) sb.append(line);
                }
                confirmImport(new JSONObject(sb.toString()));
            }
        } catch (Exception e) {
            new AlertDialog.Builder(this).setTitle("Chyba").setMessage(e.getMessage()).setPositiveButton("OK", null).show();
        }
    }

    private void confirmImport(JSONObject rootJson) {
        new AlertDialog.Builder(this).setTitle("Import dat").setMessage("Import nahradí aktuální mobilní databázi obsahem souboru. Pokračovat?").setNegativeButton("Ne", null).setPositiveButton("Ano", (d, w) -> {
            try {
                db.replaceAll(rootJson);
                showHome(true);
                Toast.makeText(this, "Import dokončen.", Toast.LENGTH_LONG).show();
            } catch (Exception e) {
                Toast.makeText(this, e.getMessage(), Toast.LENGTH_LONG).show();
            }
        }).show();
    }

    private void addRevisionContext() {
        Db.Row r=db.revision(revisionId);
        if(r==null)return;
        LinearLayout c=new LinearLayout(this);c.setOrientation(LinearLayout.HORIZONTAL);c.setGravity(Gravity.CENTER_VERTICAL);c.setPadding(dp(10),dp(8),dp(10),dp(8));c.setBackground(rounded(Color.rgb(250,250,251),C_BORDER,12));
        LinearLayout tx=new LinearLayout(this);tx.setOrientation(LinearLayout.VERTICAL);
        String no=r.get("revision_no").isEmpty()?"Revize bez čísla":r.get("revision_no");
        tx.addView(text(no,13,C_TEXT,true));
        tx.addView(text(join(r.get("revision_type"),r.get("object_name")),11,C_MUTED,false));
        c.addView(tx,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        TextView status=pill(r.get("status").isEmpty()?"Rozpracovaná":r.get("status"),C_DARK,Color.WHITE);c.addView(status,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,dp(28)));
        body.addView(c,marginBottom(dp(10)));
    }

    private void addProgress(int done, int all, String caption) {
        LinearLayout c = card();
        c.addView(text(caption, 14, C_TEXT, true));
        ProgressBar p = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        p.setMax(Math.max(1, all)); p.setProgress(done);
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(12)); pp.topMargin = dp(8); c.addView(p, pp);
        body.addView(c, marginBottom(dp(10)));
    }

    private LinearLayout moduleButton(String title, String subtitle, int accent, View.OnClickListener l) {
        LinearLayout c = card();
        c.setClickable(true); c.setOnClickListener(l);
        LinearLayout row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); row.setGravity(Gravity.CENTER_VERTICAL);
        View bar = new View(this); bar.setBackgroundColor(accent); row.addView(bar, new LinearLayout.LayoutParams(dp(6), dp(54)));
        LinearLayout tx = new LinearLayout(this); tx.setOrientation(LinearLayout.VERTICAL); tx.setPadding(dp(12), 0, dp(6), 0);
        tx.addView(text(title, 16, C_TEXT, true)); tx.addView(text(subtitle, 13, C_MUTED, false)); row.addView(tx, new LinearLayout.LayoutParams(0, dp(60), 1));
        TextView arrow = text("›", 30, C_MUTED, false); arrow.setGravity(Gravity.CENTER); row.addView(arrow, new LinearLayout.LayoutParams(dp(34), dp(60)));
        c.addView(row);
        return c;
    }

    private LinearLayout primaryAction(String title, String subtitle, View.OnClickListener l) {
        return actionCard(title, subtitle, C_ORANGE, Color.BLACK, l);
    }

    private LinearLayout secondaryAction(String title, String subtitle, View.OnClickListener l) {
        return actionCard(title, subtitle, Color.WHITE, C_TEXT, l);
    }

    private LinearLayout actionCard(String title, String subtitle, int bg, int fg, View.OnClickListener l) {
        LinearLayout c = new LinearLayout(this); c.setOrientation(LinearLayout.HORIZONTAL); c.setGravity(Gravity.CENTER_VERTICAL); c.setPadding(dp(16), dp(10), dp(12), dp(10));
        c.setBackground(rounded(bg, bg == Color.WHITE ? C_BORDER : bg, 14)); c.setClickable(true); c.setOnClickListener(l);
        LinearLayout tx = new LinearLayout(this); tx.setOrientation(LinearLayout.VERTICAL);
        tx.addView(text(title, 15, fg, true)); tx.addView(text(subtitle, 12, bg == Color.WHITE ? C_MUTED : Color.rgb(55, 45, 25), false));
        c.addView(tx, new LinearLayout.LayoutParams(0, dp(56), 1));
        TextView arrow = text("›", 28, fg, false); arrow.setGravity(Gravity.CENTER); c.addView(arrow, new LinearLayout.LayoutParams(dp(30), dp(56)));
        return c;
    }

    private LinearLayout statBox(String value, String caption) {
        LinearLayout c = new LinearLayout(this); c.setOrientation(LinearLayout.VERTICAL); c.setGravity(Gravity.CENTER); c.setBackground(rounded(Color.WHITE, C_BORDER, 14));
        c.addView(text(value, 25, C_TEXT, true)); c.addView(text(caption, 12, C_MUTED, false));
        return c;
    }

    private void sectionTitle(String value) {
        TextView t = text(value, 15, C_TEXT, true); t.setPadding(dp(2), dp(4), dp(2), dp(8)); body.addView(t);
    }

    private void emptyState(String title, String subtitle, String action, View.OnClickListener l) {
        body.addView(emptyStateView(title, subtitle, action, l), marginBottom(dp(10)));
    }

    private LinearLayout emptyStateView(String title, String subtitle, String action, View.OnClickListener l) {
        LinearLayout c = card(); c.setGravity(Gravity.CENTER_HORIZONTAL); c.setPadding(dp(18), dp(24), dp(18), dp(24));
        TextView icon = text("✓", 32, C_ORANGE, true); icon.setGravity(Gravity.CENTER); c.addView(icon);
        TextView a = text(title, 16, C_TEXT, true); a.setGravity(Gravity.CENTER); c.addView(a);
        TextView b = text(subtitle, 13, C_MUTED, false); b.setGravity(Gravity.CENTER); b.setPadding(0, dp(5), 0, dp(14)); c.addView(b);
        c.addView(smallButton(action, C_ORANGE, Color.BLACK, l), new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(46)));
        return c;
    }

    private LinearLayout card() {
        LinearLayout c = new LinearLayout(this); c.setOrientation(LinearLayout.VERTICAL); c.setPadding(dp(14), dp(12), dp(14), dp(12)); c.setBackground(rounded(Color.WHITE, C_BORDER, 14)); return c;
    }

    private GradientDrawable rounded(int fill, int stroke, int radiusDp) {
        GradientDrawable g = new GradientDrawable(); g.setColor(fill); g.setCornerRadius(dp(radiusDp)); g.setStroke(dp(1), stroke); return g;
    }

    private Button makeButton(String label, View.OnClickListener l, int bg, int fg, boolean bold) {
        Button b = new Button(this); b.setText(label); b.setTextColor(fg); b.setTextSize(13); b.setAllCaps(false); b.setPadding(dp(8), 0, dp(8), 0); b.setBackground(rounded(bg, bg, 10)); b.setOnClickListener(l); if (bold) b.setTypeface(Typeface.DEFAULT_BOLD); return b;
    }

    private Button smallButton(String label, int bg, int fg, View.OnClickListener l) { return makeButton(label, l, bg, fg, true); }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView t = new TextView(this); t.setText(value == null ? "" : value); t.setTextSize(size); t.setTextColor(color); t.setLineSpacing(0, 1.08f); if (bold) t.setTypeface(Typeface.DEFAULT_BOLD); return t;
    }

    private TextView pill(String value, int bg, int fg) {
        TextView t = text(value, 11, fg, true); t.setGravity(Gravity.CENTER); t.setPadding(dp(10), 0, dp(10), 0); t.setBackground(rounded(bg, bg, 16)); return t;
    }

    private EditText edit(String hint) {
        EditText e = new EditText(this); e.setHint(hint); e.setTextSize(15); e.setTextColor(C_TEXT); e.setHintTextColor(Color.rgb(145, 153, 162)); e.setPadding(dp(12), dp(8), dp(12), dp(8)); e.setBackground(rounded(Color.WHITE, C_BORDER, 10)); return e;
    }

    private LinearLayout form() {
        LinearLayout l = new LinearLayout(this); l.setOrientation(LinearLayout.VERTICAL); l.setPadding(dp(4), dp(8), dp(4), dp(8)); return l;
    }

    private EditText field(LinearLayout l, String name, String value) {
        TextView lab = text(name, 12, C_MUTED, true); lab.setPadding(dp(2), dp(6), 0, dp(4)); l.addView(lab);
        EditText e = edit(name); e.setSingleLine(true); e.setText(value == null ? "" : value); l.addView(e, marginBottom(dp(7))); return e;
    }

    private EditText fieldMulti(LinearLayout l, String name, String value, int lines) {
        TextView lab = text(name, 12, C_MUTED, true); lab.setPadding(dp(2), dp(6), 0, dp(4)); l.addView(lab);
        EditText e = edit(name); e.setSingleLine(false); e.setMinLines(lines); e.setGravity(Gravity.TOP); e.setText(value == null ? "" : value); l.addView(e, marginBottom(dp(7))); return e;
    }

    private Spinner spinner(LinearLayout l, String name, String[] values, int selected) {
        TextView lab = text(name, 12, C_MUTED, true); lab.setPadding(dp(2), dp(6), 0, dp(4)); l.addView(lab);
        Spinner s = new Spinner(this); s.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, values)); s.setSelection(Math.max(0, Math.min(selected, values.length - 1))); s.setBackground(rounded(Color.WHITE, C_BORDER, 10)); l.addView(s, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(50))); return s;
    }

    private ScrollView dialogScroll(View child) {
        ScrollView s = new ScrollView(this); s.setPadding(dp(10), 0, dp(10), 0); s.addView(child); return s;
    }

    private LinearLayout.LayoutParams marginBottom(int value) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT); p.bottomMargin = value; return p;
    }

    private int dp(int x) { return (int) (x * getResources().getDisplayMetrics().density + 0.5f); }
    private String s(EditText e) { return e.getText().toString().trim(); }
    private String nz(String v) { return v == null ? "" : v; }
    private String prefix(String label, String value) { return value == null || value.trim().isEmpty() ? "" : label + ": " + value.trim(); }
    private int indexOf(String[] a, String s) { if (s == null) return 0; for (int i = 0; i < a.length; i++) if (a[i].equals(s)) return i; return 0; }
    private String join(String... values) { List<String> x = new ArrayList<>(); for (String v : values) if (v != null && !v.trim().isEmpty()) x.add(v.trim()); return joinList(x, " • "); }
    private String joinList(List<String> values, String separator) { StringBuilder b = new StringBuilder(); for (String v : values) { if (b.length() > 0) b.append(separator); b.append(v); } return b.toString(); }

    public static class SimpleTextWatcher implements android.text.TextWatcher {
        private final Runnable r;
        public SimpleTextWatcher(Runnable r) { this.r = r; }
        public void beforeTextChanged(CharSequence s, int st, int c, int a) { }
        public void onTextChanged(CharSequence s, int st, int b, int c) { r.run(); }
        public void afterTextChanged(android.text.Editable e) { }
    }
}
