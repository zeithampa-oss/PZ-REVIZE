from pathlib import Path

ROOT=Path('source/android/app/src/main/java/cz/pzrevize/mobile')
MAIN=ROOT/'MainActivity.java'
DB=ROOT/'Db.java'
main=MAIN.read_text(encoding='utf-8')
db=DB.read_text(encoding='utf-8')
nav_old='''            railLink("Měření", "measurements", () -> showMeasurements(true));\n            railLink("Vnější vlivy", "influences", () -> showInfluences(true));\n            railLink("Závady", "defects", () -> showDefects(true));'''
nav_new='''            railLink("Měření", "measurements", () -> showMeasurements(true));\n            Db.Row current = db.revision(revisionId);\n            if (current != null && "VNEJSI".equalsIgnoreCase(current.get("revision_type"))) {\n                railLink("Vnější vlivy", "influences", () -> showInfluences(true));\n            }\n            if (current == null || !"VNEJSI".equalsIgnoreCase(current.get("revision_type"))) {\n                railLink("Závady", "defects", () -> showDefects(true));\n            }'''
if nav_old in main: main=main.replace(nav_old,nav_new)
start=main.find('    private void showTabletMeasurements() {')
end=main.find('    private LinearLayout cardHint(',start)
if start>=0 and end>start and 'stejná logika jako Windows' not in main[start:end]:
    new_method=r'''    private void showTabletMeasurements() {
        clearBody("Měření", "stejná logika jako Windows • tabulka obvodů a měřicích bodů");
        addRevisionContext();
        List<Db.Row> rows = db.measurements(revisionId);
        LinearLayout toolbar = new LinearLayout(this); toolbar.setOrientation(LinearLayout.HORIZONTAL); toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.addView(smallButton("＋ RCD / RCBO", C_ORANGE, C_TEXT, v -> measurementDialog(null, "RCD")), new LinearLayout.LayoutParams(0, dp(46), 2));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(46), 2); lp.leftMargin = dp(6);
        toolbar.addView(smallButton("＋ OBVOD", C_ORANGE, C_TEXT, v -> measurementDialog(null, "CIRCUIT")), lp);
        lp = new LinearLayout.LayoutParams(0, dp(46), 2); lp.leftMargin = dp(6);
        toolbar.addView(smallButton("＋ MĚŘENÍ", Color.WHITE, C_TEXT, v -> measurementDialog(null, "POINT")), lp);
        lp = new LinearLayout.LayoutParams(0, dp(46), 2); lp.leftMargin = dp(6);
        toolbar.addView(smallButton("＋ SPOJITOST", Color.WHITE, C_TEXT, v -> measurementDialog(null, "CONTINUITY")), lp);
        lp = new LinearLayout.LayoutParams(0, dp(46), 2); lp.leftMargin = dp(6);
        toolbar.addView(smallButton("＋ POZNÁMKA", Color.WHITE, C_TEXT, v -> measurementDialog(null, "NOTE")), lp);
        lp = new LinearLayout.LayoutParams(0, dp(46), 2); lp.leftMargin = dp(6);
        toolbar.addView(smallButton("HROMADNÁ EDITACE", C_DARK, Color.WHITE, v -> windowsBulkEdit()), lp);
        body.addView(toolbar, marginBottom(dp(8)));
        int done=0; for(Db.Row r:rows) if(r.bool("done")) done++;
        addProgress(done, rows.size(), "Provedeno " + done + " / " + rows.size());
        if(rows.isEmpty()){
            emptyState("Tabulka měření je prázdná.", "Nejprve založ obvod / zařízení a potom přidávej měřicí body stejně jako ve Windows.", "PŘIDAT OBVOD", v -> measurementDialog(null,"CIRCUIT"));
            return;
        }
        LinearLayout card = card(); HorizontalScrollView hs = new HorizontalScrollView(this); hs.setFillViewport(false); hs.setHorizontalScrollBarEnabled(true);
        LinearLayout table = new LinearLayout(this); table.setOrientation(LinearLayout.VERTICAL); table.setMinimumWidth(dp(1180));
        LinearLayout header = new LinearLayout(this); header.setOrientation(LinearLayout.HORIZONTAL); header.setBackgroundColor(Color.rgb(238,240,242));
        String[] heads={"OZNAČENÍ","POPIS / TYP","JIŠTĚNÍ","KABEL","U [V]","RISO / RP","ZS / IK","VÝSLEDEK",""}; int[] weights={3,4,3,3,2,3,4,2,1};
        for(int i=0;i<heads.length;i++) header.addView(tableCell(heads[i],11,C_MUTED,true),new LinearLayout.LayoutParams(0,dp(38),weights[i])); table.addView(header, marginBottom(dp(1)));
        Map<String,List<Db.Row>> children=new LinkedHashMap<>(); List<Db.Row> roots=new ArrayList<>();
        for(Db.Row r:rows){ String pk=nz(r.get("parent_key")); Db.Row parent=null; if(!pk.isEmpty()) for(Db.Row x:rows) if(pk.equals(nz(x.get("item_key")))){parent=x;break;} if(parent!=null){List<Db.Row> cc=children.get(nodeKey(parent)); if(cc==null){cc=new ArrayList<>();children.put(nodeKey(parent),cc);} cc.add(r);} else roots.add(r); }
        for(Db.Row r:roots){ addWindowsMeasurementRow(table,r,0,children,weights); appendChildrenWindows(table,r,children,1,weights); }
        hs.addView(table); card.addView(hs,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(520))); body.addView(card, marginBottom(dp(10)));
    }
    private void appendChildrenWindows(LinearLayout table, Db.Row parent, Map<String,List<Db.Row>> children, int depth, int[] weights){ List<Db.Row> kids=children.get(nodeKey(parent)); if(kids==null)return; for(Db.Row r:kids){ addWindowsMeasurementRow(table,r,depth,children,weights); appendChildrenWindows(table,r,children,depth+1,weights); } }
    private void addWindowsMeasurementRow(LinearLayout table, Db.Row r, int depth, Map<String,List<Db.Row>> children, int[] weights){
        String rt=measurementRowType(r); boolean selected=selectedMeasurements.contains(r.id()); int bg=selected?Color.rgb(255,243,220):Color.WHITE; if("RCD".equals(rt)||"RCBO".equals(rt)) bg=Color.rgb(237,244,255); else if("CONTINUITY".equals(rt)) bg=Color.rgb(242,248,243); else if("POINT".equals(rt)) bg=Color.rgb(255,248,232);
        LinearLayout row=new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); row.setGravity(Gravity.CENTER_VERTICAL); row.setPadding(dp(4),dp(3),dp(4),dp(3)); row.setBackgroundColor(bg); CheckBox cb=new CheckBox(this); cb.setChecked(selected); cb.setOnCheckedChangeListener((b,checked)->{ if(checked)selectedMeasurements.add(r.id()); else selectedMeasurements.remove(r.id()); }); row.addView(cb,new LinearLayout.LayoutParams(dp(42),dp(46)));
        String designation=(depth>0?"↳ ":"")+(nz(r.get("element")).isEmpty()?rowTypeLabel(rt):r.get("element")); String desc=nz(r.get("measure_type")); if("CIRCUIT".equals(rt)||"RCD".equals(rt)||"RCBO".equals(rt)) desc=desc.isEmpty()?rowTypeLabel(rt):desc;
        row.addView(tableCell(designation,13,C_TEXT,true),new LinearLayout.LayoutParams(0,dp(46),weights[0])); row.addView(tableCell(desc,12,C_TEXT,false),new LinearLayout.LayoutParams(0,dp(46),weights[1])); row.addView(tableCell(measureValue(r,0),12,C_TEXT,false),new LinearLayout.LayoutParams(0,dp(46),weights[2])); row.addView(tableCell("",12,C_TEXT,false),new LinearLayout.LayoutParams(0,dp(46),weights[3])); row.addView(tableCell(measureValue(r,0),12,C_TEXT,false),new LinearLayout.LayoutParams(0,dp(46),weights[4])); row.addView(tableCell(measureRiso(r),12,C_TEXT,false),new LinearLayout.LayoutParams(0,dp(46),weights[5])); row.addView(tableCell(measureZsIk(r),12,C_TEXT,false),new LinearLayout.LayoutParams(0,dp(46),weights[6])); String result=r.bool("done")?"✓ VYHOVUJE":"—"; TextView rv=tableCell(result,11,r.bool("done")?C_GREEN:C_MUTED,true); rv.setGravity(Gravity.CENTER); row.addView(rv,new LinearLayout.LayoutParams(0,dp(46),weights[7])); Button edit=smallButton("⋮",Color.WHITE,C_TEXT,v->measurementDialog(r,rt)); edit.setTextSize(18); edit.setBackground(rounded(Color.WHITE,C_BORDER,8)); row.addView(edit,new LinearLayout.LayoutParams(dp(48),dp(40))); table.addView(row,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(50)));
    }
    private String measureValue(Db.Row r,int idx){ String v=nz(r.get("v"+(idx+1))); if(v.isEmpty())return ""; String u=nz(r.get("unit"+(idx+1))); return u.isEmpty()?v:v+" "+u; }
    private String measureRiso(Db.Row r){ String a=measureValue(r,1); return a.isEmpty()?measureValue(r,0):a; }
    private String measureZsIk(Db.Row r){ String a=measureValue(r,2), b=measureValue(r,3); return b.isEmpty()?a:(a.isEmpty()?b:a+" / "+b); }

'''
    main=main[:start]+new_method+main[end:]
# Replace old bulk dialog only once.
start=main.find('    private void bulkDialog() {'); end=main.find('    private LinearLayout tabletColumns()',start)
if start>=0 and end>start:
    bulk=r'''    private void windowsBulkEdit(){
        List<Db.Row> rows=db.measurements(revisionId); if(selectedMeasurements.isEmpty()){ Toast.makeText(this,"Nejdříve označ měření, která chceš hromadně upravit.",Toast.LENGTH_LONG).show(); return; }
        ArrayList<Db.Row> chosen=new ArrayList<>(); for(Db.Row r:rows) if(selectedMeasurements.contains(r.id())) chosen.add(r); LinearLayout outer=form(); outer.addView(text("Stejný princip jako Windows: každý řádek lze upravit samostatně.",13,C_MUTED,false),marginBottom(dp(10)));
        LinearLayout wide=new LinearLayout(this); wide.setOrientation(LinearLayout.VERTICAL); wide.setMinimumWidth(dp(980)); String[] h={"BOD","U [V]","RISO / RP","ZS [Ω]","IK [A]","VÝSLEDEK","POZNÁMKA"}; int[] w={3,2,2,2,2,2,3}; LinearLayout hdr=new LinearLayout(this);
        for(int i=0;i<h.length;i++) hdr.addView(tableCell(h[i],10,C_MUTED,true),new LinearLayout.LayoutParams(0,dp(34),w[i])); wide.addView(hdr); ArrayList<EditText[]> editors=new ArrayList<>(); ArrayList<Spinner> states=new ArrayList<>();
        for(Db.Row r:chosen){ LinearLayout line=new LinearLayout(this); line.setOrientation(LinearLayout.HORIZONTAL); line.setPadding(dp(3),dp(3),dp(3),dp(3)); EditText e0=fieldBare(nz(r.get("element"))),e1=fieldBare(nz(r.get("v1"))),e2=fieldBare(nz(r.get("v2"))),e3=fieldBare(nz(r.get("v3"))),e4=fieldBare(nz(r.get("v4"))),note=fieldBare(nz(r.get("note"))); line.addView(e0,new LinearLayout.LayoutParams(0,dp(44),w[0])); line.addView(e1,new LinearLayout.LayoutParams(0,dp(44),w[1])); line.addView(e2,new LinearLayout.LayoutParams(0,dp(44),w[2])); line.addView(e3,new LinearLayout.LayoutParams(0,dp(44),w[3])); line.addView(e4,new LinearLayout.LayoutParams(0,dp(44),w[4])); Spinner st=spinnerBare(new String[]{"Neměnit","Vyhovuje","Nevyhovuje","Nehodnoceno"}); line.addView(st,new LinearLayout.LayoutParams(0,dp(44),w[5])); line.addView(note,new LinearLayout.LayoutParams(0,dp(44),w[6])); editors.add(new EditText[]{e0,e1,e2,e3,e4,note}); states.add(st); wide.addView(line); }
        HorizontalScrollView hs=new HorizontalScrollView(this); hs.addView(wide); outer.addView(hs,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(Math.min(520,120+chosen.size()*54))));
        new AlertDialog.Builder(this).setTitle("Hromadná editace měření").setView(dialogScroll(outer)).setNegativeButton("Zrušit",null).setPositiveButton("Uložit",(d,wnd)->{ for(int i=0;i<chosen.size();i++){ Db.Row r=chosen.get(i); EditText[] es=editors.get(i); String[] vals={s(es[1]),s(es[2]),s(es[3]),s(es[4])}; Boolean done=null; int state=states.get(i).getSelectedItemPosition(); if(state==1)done=true; else if(state>=2)done=false; db.updateMeasurementRow(r.id(),s(es[0]),vals,s(es[5]),done); } selectedMeasurements.clear(); showMeasurements(false); }).show();
    }
    private EditText fieldBare(String value){ EditText e=new EditText(this); e.setText(value); e.setTextSize(12); e.setSingleLine(true); e.setPadding(dp(6),0,dp(6),0); e.setBackground(rounded(Color.WHITE,C_BORDER,6)); return e; }
    private Spinner spinnerBare(String[] values){ Spinner sp=new Spinner(this); sp.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,values)); return sp; }

'''
    main=main[:start]+bulk+main[end:]
old='''                    db.addDefect(revisionId, s(description), String.valueOf(severity.getSelectedItem()), "Neodstraněna", "Kontrolní bod: " + point.get("label"));\n                    showChecklist(false);'''
new='''                    String desc=s(description);\n                    String note="Kontrolní bod: " + point.get("label");\n                    if (!db.hasDuplicateDefect(revisionId, desc, note)) db.addDefect(revisionId, desc, String.valueOf(severity.getSelectedItem()), "Neodstraněna", note);\n                    showChecklist(false);'''
if old in main: main=main.replace(old,new)
MAIN.write_text(main,encoding='utf-8')

if 'updateMeasurementRow' not in db:
    old='    public void deleteMeasurement(long id) { getWritableDatabase().delete("measurements", "id=?", new String[]{String.valueOf(id)}); }'
    db=db.replace(old,old+'\n\n    public void updateMeasurementRow(long id, String element, String[] values, String note, Boolean done) {\n        ContentValues v=new ContentValues(); v.put("element", element==null?"":element);\n        for(int i=0;i<4;i++) v.put("v"+(i+1), values!=null&&values.length>i?values[i]:"");\n        v.put("note", note==null?"":note); v.put("updated_at", now()); if(done!=null) v.put("done",done?1:0);\n        getWritableDatabase().update("measurements",v,"id=?",new String[]{String.valueOf(id)});\n    }')
if 'hasDuplicateDefect' not in db:
    marker='    public long addDefect(long revisionId, String text, String severity, String status, String note) {'
    db=db.replace(marker,'''    public boolean hasDuplicateDefect(long revisionId, String text, String note) {\n        int n=scalarInt("SELECT COUNT(*) FROM defects WHERE revision_id=? AND text=? AND COALESCE(note,'')=?",new String[]{String.valueOf(revisionId),text==null?"":text,note==null?"":note});\n        return n>0;\n    }\n\n'''+marker)
old='''    public void deleteInfluenceRoom(long revisionId, long id) {\n        SQLiteDatabase db = getWritableDatabase(); db.beginTransaction();\n        try {\n            db.delete("influence_items", "room_id=? AND EXISTS (SELECT 1 FROM influence_rooms WHERE id=? AND revision_id=?)", new String[]{String.valueOf(id), String.valueOf(id), String.valueOf(revisionId)});\n            db.delete("influence_rooms", "revision_id=? AND id=?", new String[]{String.valueOf(revisionId), String.valueOf(id)});\n            db.setTransactionSuccessful();\n        } finally { db.endTransaction(); }\n    }'''
if old in db:
    db=db.replace(old,'''    public void deleteInfluenceRoom(long revisionId, long id) {\n        SQLiteDatabase db=getWritableDatabase(); db.beginTransaction();\n        try { Cursor c=db.rawQuery("SELECT id FROM influence_rooms WHERE id=? AND revision_id=?",new String[]{String.valueOf(id),String.valueOf(revisionId)}); boolean exists=c.moveToFirst(); c.close();\n            if(exists){ db.delete("influence_items","room_id=?",new String[]{String.valueOf(id)}); db.delete("influence_rooms","id=? AND revision_id=?",new String[]{String.valueOf(id),String.valueOf(revisionId)}); }\n            db.setTransactionSuccessful();\n        } finally { db.endTransaction(); }\n    }''')
DB.write_text(db,encoding='utf-8')
PY