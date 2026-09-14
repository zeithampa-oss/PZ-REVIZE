from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import queue
import re
import urllib.request
import urllib.error
import uuid
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from PIL import Image, ImageDraw, ImageTk

from pzrevize.database import Database, app_data_dir
from pzrevize.excel_io import import_defects, export_defects, create_template, inspect_headers, auto_mapping
from pzrevize.external_influences import (
    STANDARD_CODE as EXTERNAL_STANDARD_CODE, STANDARD_TITLE as EXTERNAL_STANDARD_TITLE,
    DISPLAY_COLUMNS as EXTERNAL_COLUMNS, INFLUENCE_META as EXTERNAL_META,
    GROUP_TITLES as EXTERNAL_GROUP_TITLES, VALUE_OPTIONS as EXTERNAL_VALUE_OPTIONS,
    VALUE_HINTS as EXTERNAL_VALUE_HINTS, PROFILE_LIBRARY as EXTERNAL_PROFILES,
    MEASURE_LIBRARY as EXTERNAL_MEASURES, blank_room as external_blank_room,
    apply_profile as external_apply_profile, parse_values_json as external_parse_values,
    serialize_values as external_serialize_values, normalize_measure_codes as external_normalize_measures,
    measures_text as external_measures_text, suggest_measures as external_suggest_measures,
    room_warnings as external_room_warnings, row_status as external_row_status,
    merge_legacy_rows as external_merge_legacy_rows, import_rooms_xlsx as external_import_rooms_xlsx,
    export_rooms_xlsx as external_export_rooms_xlsx, room_summary as external_room_summary,
    classify_environment as external_classify_environment, abnormal_codes as external_abnormal_codes,
    minimum_ip as external_minimum_ip, CHECKLIST_OPTIONS as EXTERNAL_CHECKLIST_OPTIONS,
    CHECKLIST_MULTISELECT as EXTERNAL_CHECKLIST_MULTISELECT, SOURCE_DATA_NOTE as EXTERNAL_SOURCE_DATA_NOTE,
    checklist_requirement as external_checklist_requirement, checklist_item as external_checklist_item,
    ABNORMAL_VALUES as EXTERNAL_ABNORMAL_VALUES, abnormal_measure_entries as external_abnormal_measure_entries, measure_entries as external_measure_entries,
    parse_abnormal_measures_json as external_parse_abnormal_measures, serialize_abnormal_measures as external_serialize_abnormal_measures,
    GENERAL_PAGE_2_DEFAULT as EXTERNAL_GENERAL_PAGE_2_DEFAULT,
    GENERAL_PAGE_3_DEFAULT as EXTERNAL_GENERAL_PAGE_3_DEFAULT,
    GENERAL_PAGE_4_DEFAULT as EXTERNAL_GENERAL_PAGE_4_DEFAULT,
    GENERAL_PAGE_5_DEFAULT as EXTERNAL_GENERAL_PAGE_5_DEFAULT,
    REFERENCE_STANDARDS as EXTERNAL_REFERENCE_STANDARDS,
)
from pzrevize.reporting import generate_revision_pdf
from pzrevize.nas_sync import (
    NasSyncError, NasConflictError, get_sync_settings, save_sync_settings,
    get_status as nas_get_status, resolve_endpoint as nas_resolve_endpoint,
    set_setting as nas_set_setting, push_to_nas, pull_from_nas, safe_sync_once,
    create_complete_local_backup
)

APP_TITLE = "PZ-REVIZE"
VERSION = "0.4.35"

ELECTRICAL_INSPECTION_TEMPLATE_GROUPS = (
    "NV 190/2022 Sb. – příloha č. 1, část A",
    "ČSN 33 2000-6 ed. 2 – čl. 6.4.2 / příloha F",
)
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
RESOURCE_DIR = BASE_DIR / "pzrevize" / "resources"
BASE_LOGO = RESOURCE_DIR / "logo_transparent.png"
DEFAULT_LOGO = BASE_LOGO

COLORS = {
    "sidebar": "#171717",
    "sidebar2": "#202020",
    "bg": "#F4F5F7",
    "card": "#FFFFFF",
    "text": "#161616",
    "muted": "#6B7280",
    "line": "#E4E7EB",
    "green": "#19B83F",
    "green_dark": "#109230",
    "orange": "#F59E0B",
    "orange_dark": "#D98200",
    "red": "#D64545",
    "blue": "#2F6FED",
}

OPERATOR_INSTRUCTION_TITLES = {
    "ELEKTRO": "Poučení pro provozovatele elektrického zařízení",
    "LPS": "Poučení pro provozovatele LPS / ochrany před bleskem",
    "STROJ": "Poučení pro provozovatele strojního zařízení",
    "VNEJSI": "Upozornění k protokolu o určení vnějších vlivů",
}

OPERATOR_INSTRUCTION_TEMPLATES = {
    "ELEKTRO": """1. Provozovatel elektrického zařízení je povinen zajišťovat jeho bezpečný provoz, údržbu, kontroly a revize v souladu s platnými právními a technickými předpisy, zejména se zákonem č. 250/2021 Sb., zákonem č. 309/2006 Sb., ČSN 33 1500, ČSN 33 2000-1 ed. 2 a ČSN EN 50110-1 ed. 3.

2. Elektrické zařízení musí být pravidelně kontrolováno a udržováno v takovém stavu, aby byla zajištěna jeho správná činnost a byly dodrženy požadavky elektrické a mechanické bezpečnosti. Provozovatel je povinen udržovat svá elektrická zařízení ve stavu odpovídajícím právním předpisům, technickým normám, průvodní dokumentaci a podmínkám provozu.

3. Doporučuje se, aby s funkcí a účelem hlavního vypínače a zařízení nouzového vypínání byly prokazatelným způsobem seznámeny všechny osoby, které příslušné elektrické zařízení obsluhují nebo mohou v naléhavém případě provést jeho vypnutí.

4. Před zahájením práce na elektrickém zařízení nebo v jeho blízkosti musí být vyhodnocena elektrická rizika a stanoven bezpečný pracovní postup. Osoby pracující v prostorách revidovaného zařízení musí být seznámeny s místními riziky a opatřeními tak, aby nemohlo dojít k úrazu elektrickým proudem, poškození zařízení nebo narušení ochrany před bleskem.

5. Instalace, opravy, údržbu a odborné zásahy do vyhrazených elektrických zařízení mohou provádět pouze osoby splňující požadavky zákona č. 250/2021 Sb., NV č. 190/2022 Sb. a NV č. 194/2022 Sb. v rozsahu odpovídajícím prováděné činnosti.

6. Obsluhu elektrických zařízení mohou provádět pouze osoby s odpovídající odbornou způsobilostí nebo osoby prokazatelně poučené podle podmínek NV č. 194/2022 Sb. a místních provozních předpisů.

7. Elektrické zařízení, u něhož se zjistí stav bezprostředně ohrožující život nebo zdraví osob, musí být neprodleně odpojeno od napájení, zajištěno proti opětovnému uvedení do provozu a závada musí být odborně odstraněna.

8. Funkci zkušebního tlačítka proudových chráničů je nutné ověřovat v intervalech stanovených výrobcem a provozní dokumentací. Při stisknutí zkušebního tlačítka musí proudový chránič spolehlivě vybavit; nevyhovující chránič nesmí zůstat bez nápravy v provozu.""",
    "STROJ": """1. Provozovatel strojního zařízení je povinen zajišťovat jeho bezpečný provoz, údržbu, kontroly a revize elektrické části v souladu s platnými právními a technickými předpisy, průvodní dokumentací výrobce a provozní dokumentací. Pro strojní zařízení se přihlíží zejména k NV č. 378/2001 Sb. a NV č. 176/2008 Sb.; pro elektrickou část k ČSN 33 1500, ČSN EN 50110-1 ed. 3 a ČSN EN 60204-1 ed. 3.

2. Strojní zařízení musí být vybaveno provozní dokumentací. Podle § 4 NV č. 378/2001 Sb. musí být následná kontrola prováděna nejméně jednou za 12 měsíců v rozsahu stanoveném místním provozním bezpečnostním předpisem, nestanoví-li zvláštní právní předpis, průvodní dokumentace nebo normové hodnoty rozsah a četnost kontrol jinak. Provozní dokumentace musí být uchovávána po celou dobu provozu zařízení. Revize elektrické části nenahrazuje kontrolu strojního zařízení v plném rozsahu podle NV č. 378/2001 Sb.

3. Zaměstnavatel je povinen zajistit, aby stroje, technická zařízení, přístroje a nářadí byly z hlediska bezpečnosti a ochrany zdraví při práci vhodné pro činnost, při které budou používány, byly vybaveny potřebnými ochrannými zařízeními a byly řádně udržovány, kontrolovány a revidovány.

4. Technická zařízení a činnosti představující zvýšenou míru ohrožení života a zdraví mohou obsluhovat nebo vykonávat pouze osoby zdravotně a odborně způsobilé v rozsahu odpovídajícím dané činnosti.

5. Instalace, opravy, údržbu a odborné zásahy do elektrické části strojního zařízení mohou provádět pouze osoby splňující požadavky zákona č. 250/2021 Sb., NV č. 190/2022 Sb. a NV č. 194/2022 Sb.; při práci se postupuje rovněž podle ČSN EN 50110-1 ed. 3 a pokynů výrobce.

6. Obsluhu elektrických zařízení stroje mohou provádět pouze osoby s odpovídající odbornou způsobilostí nebo osoby prokazatelně poučené podle NV č. 194/2022 Sb. a provozních pokynů výrobce.

7. Před zahájením práce na stroji, jeho elektrickém zařízení nebo v jejich blízkosti musí být vyhodnocena rizika a stanoven bezpečný pracovní postup. Všechny dotčené osoby musí být prokazatelně seznámeny s nebezpečími, nouzovým vypnutím, hlavním vypínačem a dalšími bezpečnostními funkcemi stroje.

8. Opravy, seřizování, úpravy, údržba a čištění zařízení se provádějí při bezpečně odpojených zdrojích energie, pokud to technicky a provozně lze, se zajištěním proti opětovnému spuštění a podle návodu výrobce.

9. Strojní nebo elektrické zařízení, u něhož se zjistí stav bezprostředně ohrožující život nebo zdraví osob, musí být neprodleně odstaveno, odpojeno a zajištěno proti opětovnému uvedení do provozu do odstranění závady.

10. Nedílnou součástí strojního zařízení je průvodní dokumentace výrobce obsahující pokyny pro montáž, manipulaci, uvedení do provozu, obsluhu, údržbu, opravy a bezpečné používání zařízení.

11. Provozní dokumentace strojního zařízení musí obsahovat potřebné záznamy o kontrolách, údržbě, opravách a revizích a musí být vedena tak, aby odpovídala skutečnému stavu zařízení.

12. Zásahy do strojního zařízení nad rámec činností dovolených výrobcem musí být předem odborně posouzeny; podle rozsahu změny je nutné vyhodnotit její vliv na bezpečnostní funkce, dokumentaci, posouzení rizik a případně na shodu stroje.

13. Tato revize elektrického zařízení strojního zařízení posuzuje elektrickou část v rozsahu uvedeném v předmětu a rozsahu revize. Nenahrazuje úplnou kontrolu a ověřování strojního zařízení podle NV č. 378/2001 Sb., dokumentace výrobce a dalších předpisů vztahujících se na konkrétní stroj.""",
    "LPS": """1. Provozovatel systému ochrany před bleskem (LPS) je povinen zajistit jeho pravidelnou kontrolu, údržbu a revize tak, aby systém zůstal po celou dobu provozu účinný a odpovídal dokumentaci, skutečnému provedení stavby a souboru ČSN EN IEC 62305.

2. Dokumentace LPS, záznamy o provedených kontrolách, revizích, opravách a změnách musí být uchovávány a aktualizovány po dobu provozu objektu.

3. Každá změna stavby nebo jejího užívání, zejména změny střechy, fasády, technologických zařízení, antén, fotovoltaiky, kabelových tras nebo kovových konstrukcí, musí být posouzena z hlediska vlivu na LPS, dostatečnou vzdálenost, ochranné pospojování a ochranu před přepětím.

4. Po podezření na přímý úder blesku, po stavebním zásahu do LPS, při zjištění mechanického poškození, koroze, uvolněných spojů nebo jiné podstatné změny je nutné zajistit mimořádnou kontrolu nebo revizi v rozsahu odpovídajícím zjištěnému stavu.

5. Opravy a změny LPS musí provádět odborně způsobilé osoby podle dokumentace a příslušných technických pravidel; nesmí být svévolně měněny trasy jímačů, svodů, zemničů, pospojování ani prvky přepěťové ochrany.

6. Provozovatel musí zajistit, aby byly přístupné kontrolní a zkušební spoje, nebyly zakryty nebo poškozeny části LPS a aby nebyla stavebními nebo provozními zásahy zhoršena ochranná funkce systému.""",
    "VNEJSI": """1. Tento protokol zachycuje určené vnější vlivy podle stavu, způsobu užívání a podkladů známých v době jeho zpracování a slouží jako podklad pro návrh, provedení, provoz a revize elektrické instalace.

2. Při změně užívání prostoru, technologie, stavebního řešení, požárního rizika, skladovaných látek, větrání, vlhkosti, teploty, prašnosti nebo jiných podmínek, které mohou mít vliv na klasifikaci prostoru, musí být určení vnějších vlivů znovu odborně posouzeno.

3. Protokol o určení vnějších vlivů musí být uchováván jako součást dokumentace elektrické instalace a musí být dostupný projektantovi, montážní organizaci, provozovateli a reviznímu technikovi.

4. Provozovatel je povinen zajistit, aby skutečné provozní podmínky nepřekračovaly podmínky předpokládané tímto protokolem; zjištěné odchylky je nutné posoudit a podle potřeby upravit elektrickou instalaci nebo protokol.""",
}

def operator_instruction_template(revision_type: str) -> str:
    return OPERATOR_INSTRUCTION_TEMPLATES.get((revision_type or '').upper(), OPERATOR_INSTRUCTION_TEMPLATES['ELEKTRO']).strip()

def operator_instruction_title(revision_type: str) -> str:
    return OPERATOR_INSTRUCTION_TITLES.get((revision_type or '').upper(), 'Poučení pro provozovatele')

def _enable_windows_dpi_awareness():
    """Avoid shifted/scaled Tk layouts on Windows with 125/150 % display scaling."""
    if os.name != "nt":
        return
    try:
        import ctypes
        # Per-monitor v2 awareness on current Windows. Ignore if a manifest already set it.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


_enable_windows_dpi_awareness()

LEARNING_CATEGORIES = {
    "network_system": "Sítě / soustavy",
    "supply_type": "Způsoby napájení",
    "document_type": "Druhy dokumentace",
    "document_author": "Zpracovatelé dokumentace",
    "document_note": "Poznámky k dokumentaci",
    "protection_measure": "Ochranná opatření",
    "conclusion_block": "Bloky vyhodnocení / závěru",
}


def learned_options(db, category):
    return [r["value"] for r in db.learned_values(category)]


def today() -> str:
    return date.today().isoformat()


def _parse_due_date(s: str | None):
    """Parse a revision due date. Month/year values are treated as due at month end."""
    text=str(s or "").strip()
    if not text:
        return None, False
    # Full ISO date / datetime.
    try:
        return datetime.fromisoformat(text[:10]).date(), False
    except Exception:
        pass
    # Czech full date, e.g. 30.09.2029 or 30. 9. 2029.
    m=re.fullmatch(r"\s*(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})\s*", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))), False
        except ValueError:
            return None, False
    # Month/year is common in revision reports. For monitoring, the deadline is the last day of that month.
    m=re.fullmatch(r"\s*(\d{1,2})\s*[./-]\s*(\d{4})\s*", text)
    if m:
        month, year=int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            import calendar
            return date(year, month, calendar.monthrange(year, month)[1]), True
    # ISO month, e.g. 2029-09.
    m=re.fullmatch(r"\s*(\d{4})-(\d{1,2})\s*", text)
    if m:
        year, month=int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            import calendar
            return date(year, month, calendar.monthrange(year, month)[1]), True
    return None, False


def display_date(s: str | None) -> str:
    if not s:
        return ""
    d, month_only=_parse_due_date(s)
    if d:
        return d.strftime("%m.%Y" if month_only else "%d.%m.%Y")
    return str(s)


def format_value_unit(value, unit: str) -> str:
    """Append a unit to entered measurement values without duplicating an already typed unit."""
    text=str(value or "").strip()
    if not text:
        return ""
    low=text.lower().replace(" ","")
    unit_low=unit.lower().replace(" ","")
    aliases={
        "Ω": ("ω","ohm","ohms"),
        "MΩ": ("mω","mohm","mohms","mΩ".lower()),
        "V": ("v",),
        "A": ("a",),
        "mA": ("ma",),
        "ms": ("ms",),
    }.get(unit,(unit_low,))
    if any(low.endswith(a.lower()) for a in aliases):
        return text
    return f"{text} {unit}"



def _electrical_num(value):
    """Parse an electrical numeric value entered with Czech/English decimal separator and optional symbols."""
    try:
        text=str(value or '').strip().replace('\xa0',' ').replace(',','.')
        text=re.sub(r'^[<>≤≥~≈\s]+','',text)
        m=re.search(r'[-+]?\d+(?:\.\d+)?',text)
        return float(m.group(0)) if m else None
    except Exception:
        return None


def _fmt_calc_number(value, decimals=3):
    if value is None:return ''
    text=f"{float(value):.{decimals}f}".rstrip('0').rstrip('.')
    return text.replace('.',',')


def breaker_ia_a(row):
    """Return Ia used by the automatic Zs check. Manual Ia overrides the B/C/D helper."""
    manual=_electrical_num((row or {}).get('breaker_ia_a'))
    if manual is not None and manual>0:return manual
    current=_electrical_num((row or {}).get('breaker_current_a'))
    char=str((row or {}).get('breaker_characteristic') or '').strip().upper()
    factors={'B':5.0,'C':10.0,'D':20.0}
    if current is None or current<=0 or char not in factors:return None
    return current*factors[char]


def _point_code(value):
    """Normalize a measuring-point designation so L1-L2 and L1–L2 are treated identically."""
    return str(value or '').strip().upper().replace('—','-').replace('–','-').replace(' ','')


def is_phase_phase_point(value):
    return _point_code(value) in {'L1-L2','L2-L3','L1-L3'}


def auto_zs_limit(row, measured_u0=None):
    """Return (limit, Ia, U0, km). Prefer the voltage measured at the measuring point."""
    ia=breaker_ia_a(row)
    if ia is None or ia<=0:return None
    u0=_electrical_num(measured_u0)
    if u0 is None or u0<=0:u0=_electrical_num((row or {}).get('u0_v'))
    if u0 is None or u0<=0:u0=230.0
    km=_electrical_num((row or {}).get('zs_safety_factor'))
    if km is None or km<=0:km=1.5
    return (u0/(km*ia),ia,u0,km)


def breaker_summary(row):
    row=row or {}
    parts=[]
    free=str(row.get('breaker') or '').strip()
    if free:parts.append(free)
    cur=str(row.get('breaker_current_a') or '').strip()
    char=str(row.get('breaker_characteristic') or '').strip()
    rating=' / '.join(x for x in [char, (format_value_unit(cur,'A') if cur else '')] if x)
    if rating:parts.append(rating)
    ia=breaker_ia_a(row)
    if ia is not None and str(row.get('breaker_ia_a') or '').strip():parts.append(f"Ia {format_value_unit(_fmt_calc_number(ia,2),'A')}")
    return '; '.join(parts)

def resource_path(path: Path) -> str:
    return str(path)


def make_app_icon(root: tk.Tk) -> tk.PhotoImage | None:
    """Create the requested program identity at runtime: user's PZ logo + small measuring instrument badge."""
    try:
        img = Image.open(BASE_LOGO).convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(img)
        # Compact multimeter/tester badge in lower-left corner. It stays visually secondary to the original logo.
        x0, y0, x1, y1 = 12, 164, 88, 246
        draw.rounded_rectangle((x0, y0, x1, y1), radius=12, fill=(34, 34, 34, 245), outline=(255,255,255,230), width=4)
        draw.rounded_rectangle((24, 174, 76, 196), radius=4, fill=(225, 235, 225, 255))
        draw.line((31, 186, 42, 181, 55, 188, 69, 178), fill=(25, 184, 63, 255), width=3)
        draw.ellipse((39, 207, 62, 230), fill=(245, 158, 11, 255), outline=(255,255,255,220), width=2)
        draw.line((50, 208, 50, 219), fill=(32,32,32,255), width=3)
        icon = ImageTk.PhotoImage(img)
        root.iconphoto(True, icon)
        return icon
    except Exception:
        return None


class PZStyle:
    @staticmethod
    def configure(root: tk.Tk):
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["card"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=COLORS["card"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI Semibold", 21))
        style.configure("Subtle.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("CardTitle.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=("Segoe UI Semibold", 9))
        style.configure("CardValue.TLabel", background=COLORS["card"], foreground=COLORS["text"], font=("Segoe UI Semibold", 22))
        style.configure("TButton", font=("Segoe UI Semibold", 9), padding=(10, 7))
        style.configure("Accent.TButton", background=COLORS["orange"], foreground="#111111", borderwidth=0)
        style.map("Accent.TButton", background=[("active", COLORS["orange_dark"])])
        style.configure("Success.TButton", background=COLORS["green"], foreground="white", borderwidth=0)
        style.map("Success.TButton", background=[("active", COLORS["green_dark"])])
        style.configure("Danger.TButton", background="#FCE8E8", foreground=COLORS["red"], borderwidth=0)
        style.map("Danger.TButton", background=[("active", "#F7D4D4")])
        style.configure("Treeview", background="white", fieldbackground="white", foreground=COLORS["text"], rowheight=30, bordercolor=COLORS["line"], font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#F0F1F3", foreground="#30343B", relief="flat", font=("Segoe UI Semibold", 9), padding=(6,7))
        style.map("Treeview", background=[("selected", "#EAF6EC")], foreground=[("selected", "#111111")])
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14,8), font=("Segoe UI Semibold", 9))
        style.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", COLORS["green_dark"])])
        style.configure("TEntry", padding=5)
        style.configure("TCombobox", padding=4)


def _mousewheel_steps(event) -> int:
    """Return Tk scroll units for Windows/macOS/X11 wheel events."""
    num=getattr(event,"num",None)
    if num == 4:
        return -3
    if num == 5:
        return 3
    delta=getattr(event,"delta",0) or 0
    if not delta:
        return 0
    # Windows normally sends multiples of 120; touchpads may send smaller values.
    magnitude=max(1,abs(int(delta))//120) if abs(int(delta)) >= 120 else 1
    return -magnitude if delta > 0 else magnitude


def _global_mousewheel_dispatch(event):
    """Scroll the widget under the mouse, or its nearest scrollable parent.

    This makes wheel scrolling consistent across Text, Treeview, Listbox and Canvas based
    forms without changing Combobox/Spinbox values accidentally.
    """
    steps=_mousewheel_steps(event)
    if not steps:
        return None
    try:
        widget=event.widget.winfo_containing(event.x_root,event.y_root) or event.widget
    except Exception:
        widget=getattr(event,'widget',None)
    horizontal=bool(getattr(event,'state',0) & 0x0001)  # Shift + wheel
    # Text/Listbox/Treeview already have reliable native wheel bindings. Let them handle
    # a normal vertical wheel event to avoid double scrolling; the dispatcher is mainly
    # needed for forms/canvases and for wheel events over child controls.
    try:
        direct_class=str(widget.winfo_class()) if widget is not None else ''
    except Exception:
        direct_class=''
    if not horizontal and direct_class in {'Text','Listbox','Treeview'}:
        return None
    seen=set()
    while widget is not None and id(widget) not in seen:
        seen.add(id(widget))
        # Do not use wheel to cycle values in comboboxes/spinboxes; scroll their parent instead.
        try:
            wclass=str(widget.winfo_class())
        except Exception:
            wclass=''
        blocked=wclass in {'TCombobox','Combobox','TSpinbox','Spinbox'}
        method='xview_scroll' if horizontal else 'yview_scroll'
        if not blocked and hasattr(widget,method):
            try:
                getattr(widget,method)(steps,'units')
                return 'break'
            except Exception:
                pass
        widget=getattr(widget,'master',None)
    return None


def install_global_mousewheel(root):
    """Install one global mouse-wheel dispatcher for the whole Tk application."""
    root.bind_all('<MouseWheel>',_global_mousewheel_dispatch,add='+')
    root.bind_all('<Button-4>',_global_mousewheel_dispatch,add='+')
    root.bind_all('<Button-5>',_global_mousewheel_dispatch,add='+')


VV_QUICK_PROFILE_FILE = "vv_quick_profiles.json"


def _vv_quick_profile_path() -> Path:
    return app_data_dir() / VV_QUICK_PROFILE_FILE


def load_vv_quick_profiles() -> dict[str, dict]:
    path=_vv_quick_profile_path()
    try:
        raw=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    except Exception:
        raw={}
    out={}
    if not isinstance(raw,dict):
        return out
    for name,profile in raw.items():
        if not isinstance(profile,dict) or not str(name).strip():
            continue
        values=external_parse_values(profile.get('values') or profile.get('values_json') or {})
        out[str(name).strip()]={
            'values':values,
            'measures':external_normalize_measures(profile.get('measures','')),
            'abnormal_measures':external_parse_abnormal_measures(profile.get('abnormal_measures') or profile.get('abnormal_measures_json') or {}),
            'space_class':str(profile.get('space_class') or external_classify_environment(values)),
            'custom':True,
        }
    return out


def save_vv_quick_profiles(profiles: dict[str, dict]) -> None:
    path=_vv_quick_profile_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    payload={}
    for name,profile in profiles.items():
        if not str(name).strip() or not isinstance(profile,dict):
            continue
        payload[str(name).strip()]={
            'values':external_parse_values(profile.get('values') or {}),
            'measures':external_normalize_measures(profile.get('measures','')),
            'abnormal_measures':external_parse_abnormal_measures(profile.get('abnormal_measures') or {}),
            'space_class':str(profile.get('space_class') or ''),
        }
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)


def vv_profile_library() -> dict[str, dict]:
    result={name:{**dict(profile),'custom':False} for name,profile in EXTERNAL_PROFILES.items()}
    result.update(load_vv_quick_profiles())
    return result


class ScrollFrame(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.inner_id, width=e.width))

    def _wheel(self, event):
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass


def _desktop_work_area(widget):
    """Return usable desktop rectangle, excluding the Windows taskbar when possible.

    Tk's screen height normally includes the taskbar.  Large modal windows could therefore
    end up underneath it on 1366x768 / high-DPI notebooks.
    """
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                return rect.left, rect.top, max(1, rect.right-rect.left), max(1, rect.bottom-rect.top)
    except Exception:
        pass
    return 0, 0, max(1, widget.winfo_screenwidth()), max(1, widget.winfo_screenheight())


class Modal(tk.Toplevel):
    def __init__(self, parent, title: str, width=650, height=600):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.configure(bg=COLORS["bg"])
        self.result = None
        self._modal_fullscreen = False
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<F11>", self._toggle_modal_fullscreen)
        self.after_idle(lambda: self._center_over_parent(parent, width, height))

    def _toggle_modal_fullscreen(self, event=None):
        self._modal_fullscreen = not getattr(self, '_modal_fullscreen', False)
        try:
            self.attributes('-fullscreen', self._modal_fullscreen)
        except Exception:
            pass
        return 'break'

    def _center_over_parent(self, parent, width: int, height: int):
        try:
            self.update_idletasks()
            wx, wy, ww, wh = _desktop_work_area(self)
            pw, ph = max(parent.winfo_width(), 1), max(parent.winfo_height(), 1)
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            margin = 10
            # geometry() udává klientskou plochu; na Windows je nutné ponechat
            # rezervu i na titulkový rám okna, jinak spodní okraj může znovu skončit
            # pod hlavním panelem i když používáme SPI_GETWORKAREA.
            frame_w = 18 if os.name == "nt" else 0
            frame_h = 48 if os.name == "nt" else 0
            usable_w = max(420, ww - 2*margin - frame_w)
            usable_h = max(320, wh - 2*margin - frame_h)
            min_w = min(500, usable_w)
            min_h = min(400, usable_h)
            self.minsize(min_w, min_h)
            w = min(width, max(min_w, usable_w))
            h = min(height, max(min_h, usable_h))
            x = px + max(0, (pw - w) // 2)
            y = py + max(0, (ph - h) // 2)
            x = max(wx + margin, min(x, wx + ww - w - margin))
            y = max(wy + margin, min(y, wy + wh - h - margin))
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass


class FormDialog(Modal):
    def __init__(self, parent, title, fields, values=None, width=650, height=620):
        super().__init__(parent, title, width, height)
        self.fields = fields
        self.values = values or {}
        self.vars = {}
        body = ScrollFrame(self)
        body.pack(fill="both", expand=True, padx=18, pady=(18, 8))
        body.inner.columnconfigure(1, weight=1)
        row = 0
        for fld in fields:
            name, label = fld[0], fld[1]
            kind = fld[2] if len(fld) > 2 else "entry"
            options = fld[3] if len(fld) > 3 else None
            ttk.Label(body.inner, text=label, style="Subtle.TLabel").grid(row=row, column=0, sticky="nw", padx=(0,12), pady=7)
            initial = self.values.get(name, "")
            if kind == "text":
                widget = tk.Text(body.inner, height=5, font=("Segoe UI", 9), wrap="word", relief="solid", bd=1)
                widget.insert("1.0", initial or "")
                widget.grid(row=row, column=1, sticky="ew", pady=5)
                self.vars[name] = widget
            elif kind in ("combo", "combo_edit"):
                var = tk.StringVar(value=initial or (options[0] if (kind == "combo" and options) else ""))
                widget = ttk.Combobox(body.inner, textvariable=var, values=options or [], state="readonly" if kind == "combo" else "normal")
                widget.grid(row=row, column=1, sticky="ew", pady=5)
                self.vars[name] = var
            else:
                var = tk.StringVar(value="" if initial is None else str(initial))
                widget = ttk.Entry(body.inner, textvariable=var)
                widget.grid(row=row, column=1, sticky="ew", pady=5)
                self.vars[name] = var
            row += 1
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=18, pady=(0, 16))
        ttk.Button(footer, text="Zrušit", command=self.destroy).pack(side="right")
        ttk.Button(footer, text="Uložit", style="Success.TButton", command=self._save).pack(side="right", padx=(0,8))

    def _save(self):
        data = {}
        for name, var in self.vars.items():
            if isinstance(var, tk.Text):
                data[name] = var.get("1.0", "end").strip()
            else:
                data[name] = var.get().strip()
        self.result = data
        self.destroy()


class ExternalRoomDialog(Modal):
    """Checklist jedné místnosti pro určení vnějších vlivů."""
    def __init__(self, parent, title, values=None):
        super().__init__(parent, title, 1120, 700)
        self.values = dict(values or external_blank_room())
        self.vars = {
            'floor': tk.StringVar(value=str(self.values.get('floor','') or '')),
            'room_no': tk.StringVar(value=str(self.values.get('room_no','') or '')),
            'room_name': tk.StringVar(value=str(self.values.get('room_name','') or '')),
            'profile': tk.StringVar(value=''),
            'environment_class': tk.StringVar(value=str(self.values.get('environment_class','') or 'URČENO')),
            'measure_codes': tk.StringVar(value=external_normalize_measures(self.values.get('measure_codes',''))),
        }
        self.influence_vars = {c: tk.StringVar(value='') for c in EXTERNAL_COLUMNS}
        self.check_vars = {c: {} for c in EXTERNAL_COLUMNS}
        self.requirement_vars = {c: tk.StringVar(value='') for c in EXTERNAL_COLUMNS}
        self.legacy_values = {}
        self.abnormal_measure_values = external_parse_abnormal_measures(self.values.get('abnormal_measures_json'))

        # Akční tlačítka jsou rezervována dole jako první, takže zůstávají dostupná
        # i na menších displejích / při zvětšeném DPI Windows.
        footer=ttk.Frame(self);footer.pack(side='bottom',fill='x',padx=16,pady=(4,8))
        ttk.Button(footer,text='Celá obrazovka (F11)',command=self._toggle_modal_fullscreen).pack(side='left')
        ttk.Label(footer,text='ESC = zavřít',style='Subtle.TLabel').pack(side='left',padx=(10,0))
        ttk.Button(footer,text='Zrušit',command=self.destroy).pack(side='right')
        ttk.Button(footer,text='Uložit místnost',style='Success.TButton',command=self._save).pack(side='right',padx=(0,8))

        head=ttk.Frame(self);head.pack(fill='x',padx=16,pady=(10,6));head.columnconfigure(1,weight=1);head.columnconfigure(4,weight=1)
        ttk.Label(head,text='Podlaží / celek',style='Subtle.TLabel').grid(row=0,column=0,sticky='w',padx=(0,8),pady=4)
        ttk.Entry(head,textvariable=self.vars['floor'],width=25).grid(row=0,column=1,sticky='ew',pady=4)
        ttk.Label(head,text='Číslo místnosti',style='Subtle.TLabel').grid(row=0,column=2,sticky='w',padx=(18,8),pady=4)
        ttk.Entry(head,textvariable=self.vars['room_no'],width=18).grid(row=0,column=3,sticky='ew',pady=4)
        ttk.Label(head,text='Název místnosti',style='Subtle.TLabel').grid(row=1,column=0,sticky='w',padx=(0,8),pady=4)
        ttk.Entry(head,textvariable=self.vars['room_name']).grid(row=1,column=1,columnspan=4,sticky='ew',pady=4)
        ttk.Label(head,text='Rychlý profil',style='Subtle.TLabel').grid(row=2,column=0,sticky='w',padx=(0,8),pady=4)
        self.profile_library=vv_profile_library()
        self.profile_combo=ttk.Combobox(head,textvariable=self.vars['profile'],values=['']+list(self.profile_library),state='readonly')
        self.profile_combo.grid(row=2,column=1,columnspan=2,sticky='ew',pady=4)
        ttk.Button(head,text='Použít profil',command=self._apply_profile).grid(row=2,column=3,sticky='w',padx=8,pady=4)
        ttk.Label(head,text='Výsledek',style='Subtle.TLabel').grid(row=2,column=4,sticky='e',padx=(10,0),pady=4)
        self.class_label=tk.Label(head,textvariable=self.vars['environment_class'],bg='#F4F5F7',fg=COLORS['blue'],font=('Segoe UI Semibold',10),anchor='e')
        self.class_label.grid(row=2,column=5,sticky='e',padx=(8,0))
        prof_actions=ttk.Frame(head);prof_actions.grid(row=3,column=1,columnspan=3,sticky='w',pady=(0,3))
        ttk.Button(prof_actions,text='Uložit tuto místnost jako profil',command=self._save_current_as_profile).pack(side='left')
        ttk.Button(prof_actions,text='Smazat vlastní profil',command=self._delete_current_profile).pack(side='left',padx=(5,0))
        ttk.Label(head,text='Vlastní profil ukládá VV a opatření, ne název ani popis místnosti.',style='Subtle.TLabel').grid(row=3,column=4,columnspan=2,sticky='e',padx=(10,0),pady=(0,3))

        self.room_nb=ttk.Notebook(self);self.room_nb.pack(fill='both',expand=True,padx=16,pady=4)
        tab_desc=ttk.Frame(self.room_nb);tab_vv=ttk.Frame(self.room_nb)
        self.room_nb.add(tab_desc,text='Popis')
        self.room_nb.add(tab_vv,text='Vnější vlivy')

        desc_wrap=ttk.Frame(tab_desc);desc_wrap.pack(fill='both',expand=True,padx=12,pady=12)
        tools=ttk.Frame(desc_wrap);tools.pack(fill='x',pady=(0,6))
        ttk.Label(tools,text='Popis místnosti / prostoru',font=('Segoe UI Semibold',11)).pack(side='left')
        ttk.Button(tools,text='• Odrážky',command=lambda:self._format_description('bullet')).pack(side='right')
        ttk.Button(tools,text='1. Číslování',command=lambda:self._format_description('number')).pack(side='right',padx=(0,5))
        ttk.Label(desc_wrap,text='Velké textové pole pro popis konkrétního prostoru. Ve výstupu se tento text vytiskne nad tabulkou VV, ne uvnitř tabulky.',style='Subtle.TLabel').pack(anchor='w',pady=(0,6))
        dbod=ttk.Frame(desc_wrap);dbod.pack(fill='both',expand=True)
        self.description_text=tk.Text(dbod,font=('Segoe UI',10),wrap='word',undo=True,relief='solid',bd=1,padx=8,pady=7)
        self.description_text.insert('1.0',self.values.get('room_description','') or self.values.get('note','') or '')
        dsy=ttk.Scrollbar(dbod,orient='vertical',command=self.description_text.yview);self.description_text.configure(yscrollcommand=dsy.set)
        self.description_text.grid(row=0,column=0,sticky='nsew');dsy.grid(row=0,column=1,sticky='ns');dbod.rowconfigure(0,weight=1);dbod.columnconfigure(0,weight=1)

        tab_vv.columnconfigure(0,weight=1);tab_vv.rowconfigure(1,weight=1)
        info=tk.Frame(tab_vv,bg='#F7FAFE',highlightbackground='#C9D8E8',highlightthickness=1);info.grid(row=0,column=0,sticky='ew',padx=8,pady=(8,6))
        tk.Label(info,text=f'CHECKLIST VNĚJŠÍCH VLIVŮ  •  {EXTERNAL_STANDARD_CODE}',bg='#F7FAFE',fg=COLORS['text'],font=('Segoe UI Semibold',9),anchor='w').pack(fill='x',padx=10,pady=(7,2))
        tk.Label(info,text='Zaškrtni skutečnou charakteristiku prostoru. U většiny skupin lze zvolit jednu třídu; u AM a BA lze zvolit více současně. Pod každou skupinou se zobrazí stručný požadavek a zdrojová tabulka.',bg='#F7FAFE',fg=COLORS['muted'],font=('Segoe UI',8),anchor='w',justify='left',wraplength=1120).pack(fill='x',padx=10,pady=(0,2))
        tk.Label(info,text=EXTERNAL_SOURCE_DATA_NOTE,bg='#F7FAFE',fg='#8A5A00',font=('Segoe UI',8),anchor='w',justify='left',wraplength=1120).pack(fill='x',padx=10,pady=(0,3))
        self.external_assessment_var=tk.StringVar(value='')
        tk.Label(info,textvariable=self.external_assessment_var,bg='#F7FAFE',fg=COLORS['blue'],font=('Segoe UI Semibold',8),anchor='w',justify='left',wraplength=1120).pack(fill='x',padx=10,pady=(0,7))

        self.nb=ttk.Notebook(tab_vv);self.nb.grid(row=1,column=0,sticky='nsew',padx=8,pady=(0,4))
        self.group_tabs={}
        for group in ('A','B','C'):
            tab=ScrollFrame(self.nb);self.nb.add(tab,text=EXTERNAL_GROUP_TITLES[group]);self.group_tabs[group]=tab
            tab.inner.columnconfigure(0,weight=1)

        current = external_parse_values(self.values.get('values_json'))
        self._build_checklist(current)
        self._refresh_external_assessment()

        footbox=ttk.Frame(tab_vv);footbox.grid(row=2,column=0,sticky='ew',padx=8,pady=(4,6));footbox.columnconfigure(1,weight=1)
        ttk.Label(footbox,text='Opatření / požadavky pro vybrané VV',style='Subtle.TLabel').grid(row=0,column=0,sticky='nw',padx=(0,8),pady=(0,4))
        mhold=ttk.Frame(footbox);mhold.grid(row=0,column=1,columnspan=2,sticky='ew',pady=(0,5));mhold.columnconfigure(0,weight=1)
        self.abnormal_measure_tree=ttk.Treeview(mhold,columns=('code','name','measure'),show='headings',height=3)
        for k,l,w in [('code','VV',75),('name','Charakteristika',260),('measure','Opatření',650)]:
            self.abnormal_measure_tree.heading(k,text=l,anchor='w');self.abnormal_measure_tree.column(k,width=w,minwidth=60,anchor='w',stretch=(k=='measure'))
        mys=ttk.Scrollbar(mhold,orient='vertical',command=self.abnormal_measure_tree.yview);mxs=ttk.Scrollbar(mhold,orient='horizontal',command=self.abnormal_measure_tree.xview);self.abnormal_measure_tree.configure(yscrollcommand=mys.set,xscrollcommand=mxs.set)
        self.abnormal_measure_tree.grid(row=0,column=0,sticky='ew');mys.grid(row=0,column=1,sticky='ns');mxs.grid(row=1,column=0,sticky='ew')
        self.abnormal_measure_tree.bind('<Double-1>',lambda e:self._edit_abnormal_measure())
        mb=ttk.Frame(footbox);mb.grid(row=1,column=1,columnspan=2,sticky='w',pady=(0,5))
        ttk.Button(mb,text='Upravit opatření',command=self._edit_abnormal_measure).pack(side='left')
        ttk.Button(mb,text='Vrátit normový návrh',command=self._reset_abnormal_measure).pack(side='left',padx=(5,0))
        ttk.Label(footbox,text='Doplňková opatření (katalog D...)',style='Subtle.TLabel').grid(row=2,column=0,sticky='w',padx=(0,8))
        ttk.Entry(footbox,textvariable=self.vars['measure_codes']).grid(row=2,column=1,sticky='ew')
        ttk.Button(footbox,text='Doplnit návrh',command=self._suggest_measures).grid(row=2,column=2,padx=(8,0))
        self.measure_preview=tk.Text(footbox,height=2,font=('Segoe UI',8),wrap='word',state='disabled',bg='#FAFBFC',relief='solid',bd=1)
        self.measure_preview.grid(row=3,column=0,columnspan=3,sticky='ew',pady=(7,0))
        self.vars['measure_codes'].trace_add('write',lambda *a:self._update_measure_preview())
        self._update_measure_preview();self._refresh_abnormal_measure_tree()
        # Po dokončení sestavení obsahu přepnout do maximalizovaného pracovního okna.
        # Volání je záměrně až zde, aby ho následné centrování Modal nepřepsalo.


    def _center_over_parent(self, parent, width: int, height: int):
        super()._center_over_parent(parent, width, height)
        self._maximize_room_window()

    def _maximize_room_window(self):
        """Maximize the room editor inside the usable desktop; F11 is true fullscreen."""
        try:
            if os.name == 'nt':
                self.state('zoomed')
            else:
                wx, wy, ww, wh = _desktop_work_area(self)
                self.geometry(f"{max(700,ww-20)}x{max(520,wh-50)}+{wx+10}+{wy+10}")
        except Exception:
            pass


    def _format_description(self, mode):
        t=self.description_text
        try:
            start=t.index('sel.first');end=t.index('sel.last')
        except tk.TclError:
            start='1.0';end='end-1c'
        text=t.get(start,end)
        lines=text.splitlines();out=[];n=1
        for line in lines:
            if not line.strip():out.append('');continue
            clean=re.sub(r'^\s*(?:[•–-]\s+|\d+[.)]\s+)', '', line).strip()
            if mode=='bullet':out.append('• '+clean)
            else:out.append(f'{n}. {clean}');n+=1
        t.delete(start,end);t.insert(start,'\n'.join(out));t.focus_set()

    @staticmethod
    def _tokens_for(group, value):
        text=str(value or '').strip().upper().replace(' ','')
        if not text:return []
        if group=='AM' and text=='AM1':return ['AM-1-2']
        raw=[x for x in re.split(r'[,;/]+',text) if x]
        out=[]
        for token in raw:
            if token=='---':out.append(token)
            elif token.startswith(group):out.append(token)
            elif re.fullmatch(r'\d+(?:-\d+)?',token):out.append(group+token)
            else:out.append(token)
        return out

    def _build_checklist(self, current):
        group_rows={'A':0,'B':0,'C':0}
        for code,meta in EXTERNAL_META.items():
            holder=self.group_tabs[meta['group']].inner
            frame=tk.LabelFrame(holder,text=f'{code} – {meta["name"]}',bg='white',fg=COLORS['text'],font=('Segoe UI Semibold',9),bd=1,relief='solid',padx=8,pady=6)
            frame.grid(row=group_rows[meta['group']],column=0,sticky='ew',padx=8,pady=5);group_rows[meta['group']]+=1
            for col in range(3):frame.columnconfigure(col,weight=1)
            options=EXTERNAL_CHECKLIST_OPTIONS.get(code,[])
            selected=self._tokens_for(code,current.get(code,''))
            known={item['code'] for item in options}
            unknown=[x for x in selected if x not in known]
            if unknown:self.legacy_values[code]=current.get(code,'')
            cols=2 if code=='AM' else (3 if len(options)>=6 else 2)
            for idx,item in enumerate(options):
                opt=item['code'];bv=tk.BooleanVar(value=opt in selected);self.check_vars[code][opt]=bv
                text=f'{opt}  {item["label"]}'
                cb=ttk.Checkbutton(frame,text=text,variable=bv,command=lambda c=code,o=opt:self._check_clicked(c,o))
                cb.grid(row=idx//cols,column=idx%cols,sticky='w',padx=(2,12),pady=2)
            row=(len(options)+cols-1)//cols
            req=tk.Label(frame,textvariable=self.requirement_vars[code],bg='white',fg=COLORS['muted'],font=('Segoe UI',8),anchor='w',justify='left',wraplength=1050)
            req.grid(row=row,column=0,columnspan=3,sticky='ew',padx=2,pady=(5,0))
            if unknown:
                tk.Label(frame,text=f'Původní hodnota mimo aktuální checklist: {current.get(code,"")}. Po výběru nové položky se nahradí.',bg='#FFF8E8',fg='#8A5A00',font=('Segoe UI',8),anchor='w',justify='left').grid(row=row+1,column=0,columnspan=3,sticky='ew',padx=2,pady=(4,0))
            self._sync_group(code,refresh=False)

    def _check_clicked(self, group, option):
        if group not in EXTERNAL_CHECKLIST_MULTISELECT and self.check_vars[group][option].get():
            for other,var in self.check_vars[group].items():
                if other!=option:var.set(False)
        self.legacy_values.pop(group,None)
        self._sync_group(group)

    def _sync_group(self, group, refresh=True):
        selected=[item['code'] for item in EXTERNAL_CHECKLIST_OPTIONS.get(group,[]) if self.check_vars[group].get(item['code']) and self.check_vars[group][item['code']].get()]
        if selected:
            value=', '.join(selected) if group in EXTERNAL_CHECKLIST_MULTISELECT else selected[0]
        else:
            value=str(self.legacy_values.get(group,'') or '')
        self.influence_vars[group].set(value)
        req=external_checklist_requirement(group,value)
        if value:
            self.requirement_vars[group].set(f'Vybráno: {value}' + (f'  •  {req}' if req else ''))
        else:
            self.requirement_vars[group].set('Nevybráno – doplň charakteristiku prostoru.')
        if refresh:self._refresh_external_assessment()

    def _load_values_into_checklist(self, values):
        self.legacy_values={}
        for group in EXTERNAL_COLUMNS:
            tokens=self._tokens_for(group,values.get(group,''))
            known=set(self.check_vars.get(group,{}))
            unknown=[x for x in tokens if x not in known]
            if unknown:self.legacy_values[group]=values.get(group,'')
            for opt,var in self.check_vars.get(group,{}).items():var.set(opt in tokens)
            self._sync_group(group,refresh=False)
        self._refresh_external_assessment()

    def _current_values(self):
        return {c:v.get().strip() for c,v in self.influence_vars.items()}

    def _refresh_external_assessment(self):
        if not hasattr(self,'external_assessment_var'):return
        values=self._current_values();state=external_classify_environment(values);abnormal=external_abnormal_codes(values)
        self.vars['environment_class'].set(state)
        ad_ip,ae_ip=external_minimum_ip(values)
        parts=[f'Automatické vyhodnocení: {state}']
        if abnormal:parts.append('rozhodující / abnormální: '+', '.join(abnormal))
        ip=[]
        if ad_ip:ip.append('voda '+ad_ip)
        if ae_ip:ip.append('pevná tělesa '+ae_ip)
        if ip:parts.append('orientační min. krytí: '+', '.join(ip))
        self.external_assessment_var.set('  •  '.join(parts))
        self._update_auto_measure_preview()

    def _refresh_profile_combo(self, select_name: str = ''):
        self.profile_library=vv_profile_library()
        if hasattr(self,'profile_combo'):
            self.profile_combo.configure(values=['']+list(self.profile_library))
        if select_name and select_name in self.profile_library:
            self.vars['profile'].set(select_name)
        elif self.vars['profile'].get() not in self.profile_library:
            self.vars['profile'].set('')

    def _apply_profile(self):
        name=self.vars['profile'].get().strip()
        if not name:return
        self._refresh_profile_combo(name)
        profile=self.profile_library.get(name)
        if not profile:return
        if profile.get('custom'):
            vals=external_parse_values(profile.get('values') or {})
            self._load_values_into_checklist(vals)
            self.vars['measure_codes'].set(external_normalize_measures(profile.get('measures','')))
            self.abnormal_measure_values=external_parse_abnormal_measures(profile.get('abnormal_measures') or {})
            self._refresh_abnormal_measure_tree()
            self.values['description']=name
            return
        temp=dict(self.values)
        temp['values_json']=external_serialize_values(self._current_values())
        temp['measure_codes']=self.vars['measure_codes'].get()
        temp=external_apply_profile(temp,name)
        vals=external_parse_values(temp.get('values_json'))
        self.abnormal_measure_values={}
        self._load_values_into_checklist(vals)
        self.values['description']=temp.get('description','') or name
        self.vars['measure_codes'].set(temp.get('measure_codes',''))
        self._refresh_abnormal_measure_tree()

    def _save_current_as_profile(self):
        values=self._current_values()
        missing=[c for c in EXTERNAL_COLUMNS if not values.get(c)]
        if missing:
            if not messagebox.askyesno('Neúplný rychlý profil',
                'Nejsou vyplněny všechny skupiny VV: '+', '.join(missing)+'.\n\nUložit profil i tak?',parent=self):
                return
        suggested=(self.vars['room_name'].get().strip() or 'Vlastní profil')
        d=FormDialog(self,'Uložit rychlý profil',[('name','Název profilu')],{'name':suggested},width=560,height=210)
        self.wait_window(d)
        if not d.result:return
        name=str(d.result.get('name','') or '').strip()
        if not name:return
        if name in EXTERNAL_PROFILES:
            messagebox.showerror('Rychlý profil','Tento název používá vestavěný profil. Zvol jiný název.',parent=self);return
        custom=load_vv_quick_profiles()
        if name in custom and not messagebox.askyesno('Přepsat profil?',f'Vlastní profil „{name}“ už existuje. Přepsat jej?',parent=self):
            return
        # Ulož i aktuálně účinné texty opatření, aby profil odpovídal konkrétní místnosti.
        entries=external_measure_entries(values,self.abnormal_measure_values)
        measure_map={x['code']:x.get('requirement','').strip() for x in entries if x.get('requirement','').strip()}
        custom[name]={
            'values':values,
            'measures':external_normalize_measures(self.vars['measure_codes'].get()),
            'abnormal_measures':measure_map,
            'space_class':external_classify_environment(values),
        }
        try:
            save_vv_quick_profiles(custom)
        except Exception as e:
            messagebox.showerror('Rychlý profil',f'Profil se nepodařilo uložit.\n\n{e}',parent=self);return
        self._refresh_profile_combo(name)
        messagebox.showinfo('Rychlý profil',f'Profil „{name}“ byl uložen. Je dostupný i v dalších protokolech VV.',parent=self)

    def _delete_current_profile(self):
        name=self.vars['profile'].get().strip()
        if not name:
            messagebox.showinfo('Rychlý profil','Vyber vlastní profil, který chceš smazat.',parent=self);return
        if name in EXTERNAL_PROFILES:
            messagebox.showinfo('Rychlý profil','Vestavěné profily nelze smazat.',parent=self);return
        custom=load_vv_quick_profiles()
        if name not in custom:
            self._refresh_profile_combo();return
        if not messagebox.askyesno('Smazat profil?',f'Smazat vlastní rychlý profil „{name}“?',parent=self):return
        custom.pop(name,None)
        try:save_vv_quick_profiles(custom)
        except Exception as e:
            messagebox.showerror('Rychlý profil',f'Profil se nepodařilo smazat.\n\n{e}',parent=self);return
        self._refresh_profile_combo()

    def _suggest_measures(self):
        proposed=external_suggest_measures(self._current_values(),self.vars['room_name'].get())
        current=set(external_normalize_measures(self.vars['measure_codes'].get()).split(',')) if self.vars['measure_codes'].get().strip() else set()
        added=[x for x in proposed if x not in current]
        if not added:
            messagebox.showinfo('Návrh opatření','Program pro zadané hodnoty nenavrhuje další opatření. Odborné posouzení zůstává na zpracovateli protokolu.',parent=self);return
        merged=external_normalize_measures(','.join([x for x in current if x]+added));self.vars['measure_codes'].set(merged)

    def _update_measure_preview(self):
        text=external_measures_text(self.vars['measure_codes'].get()) or 'Bez doplňkového číselného odkazu na opatření.'
        self.measure_preview.configure(state='normal');self.measure_preview.delete('1.0','end');self.measure_preview.insert('1.0',text);self.measure_preview.configure(state='disabled')

    def _refresh_abnormal_measure_tree(self):
        if not hasattr(self,'abnormal_measure_tree'):return
        selected=self.abnormal_measure_tree.selection()
        selected_code=selected[0] if selected else ''
        for iid in self.abnormal_measure_tree.get_children():self.abnormal_measure_tree.delete(iid)
        entries=external_measure_entries(self._current_values(),self.abnormal_measure_values)
        for entry in entries:
            self.abnormal_measure_tree.insert('', 'end', iid=entry['code'], values=(entry['code'],entry.get('label',''),entry.get('requirement','')))
        if selected_code and self.abnormal_measure_tree.exists(selected_code):self.abnormal_measure_tree.selection_set(selected_code)

    def _edit_abnormal_measure(self):
        if not hasattr(self,'abnormal_measure_tree'):return
        sel=self.abnormal_measure_tree.selection()
        if not sel:
            messagebox.showinfo('Opatření','Vyber vnější vliv, pro který chceš nastavit opatření / požadavek.',parent=self);return
        code=sel[0]
        entries={x['code']:x for x in external_measure_entries(self._current_values(),self.abnormal_measure_values)}
        entry=entries.get(code,{})
        fields=[('measure','Opatření / požadavek','text')]
        d=FormDialog(self,f'Opatření pro {code}',fields,{'measure':entry.get('requirement','')},width=820,height=430);self.wait_window(d)
        if d.result is not None:
            self.abnormal_measure_values[code]=d.result.get('measure','').strip()
            self._refresh_abnormal_measure_tree()
            if self.abnormal_measure_tree.exists(code):self.abnormal_measure_tree.selection_set(code);self.abnormal_measure_tree.see(code)

    def _reset_abnormal_measure(self):
        if not hasattr(self,'abnormal_measure_tree'):return
        sel=self.abnormal_measure_tree.selection()
        if not sel:return
        code=sel[0];self.abnormal_measure_values.pop(code,None);self._refresh_abnormal_measure_tree()
        if self.abnormal_measure_tree.exists(code):self.abnormal_measure_tree.selection_set(code)

    def _update_auto_measure_preview(self):
        # Zpětně kompatibilní volání z checklistu; seznam opatření je editovatelný.
        self._refresh_abnormal_measure_tree()

    def _save(self):
        room_no=self.vars['room_no'].get().strip();room_name=self.vars['room_name'].get().strip()
        if not room_name and not messagebox.askyesno('Neúplný prostor','Název místnosti / prostoru není vyplněn. Uložit i tak?',parent=self):return
        result=dict(self.values);values=self._current_values();measures=external_normalize_measures(self.vars['measure_codes'].get());computed_class=external_classify_environment(values)
        active_entries=external_measure_entries(values,self.abnormal_measure_values)
        active_codes={x['code'] for x in active_entries}
        active_measure_map={code:text for code,text in self.abnormal_measure_values.items() if code in active_codes}
        missing=[x['code'] for x in external_measure_entries(values,active_measure_map) if not x.get('complete')]
        if missing and not messagebox.askyesno('Chybí opatření','Pro vlivy '+', '.join(missing)+' není vyplněno konkrétní opatření / požadavek. Uložit prostor jako k doplnění?',parent=self):return
        complete_values=all(values.get(c) for c in EXTERNAL_COLUMNS)
        result.update({
            'floor':self.vars['floor'].get().strip(),'room_no':room_no,'room_name':room_name,
            'values_json':external_serialize_values(values),'measure_codes':measures,'environment_class':computed_class,
            'abnormal_measures_json':external_serialize_abnormal_measures(active_measure_map),
            'measure':external_measures_text(measures),'room_description':self.description_text.get('1.0','end').strip(),
            'result':'Určeno' if complete_values and not missing else 'K doplnění',
            'note':str(self.values.get('note','') or '').strip(),'code':'','value_code':'',
        })
        self.result=result;self.destroy()

class PowerSourceDialog(Modal):
    """Editor jednoho zdroje napájení a jeho napájecí soustavy.

    Ukládá se do stávající tabulky revision_supplies kvůli zpětné kompatibilitě:
    supply_type = druh zdroje, designation = provozovatel/označení, voltage = úplné
    normalizované označení soustavy, backup = rozsah/úloha, note = poznámka.
    """
    SOURCE_TYPES = [
        "", "Cizí distribuční síť", "Vlastní transformátor / trafostanice",
        "UPS", "Náhradní zdroj / generátor", "Fotovoltaický zdroj / střídač",
        "Bateriové úložiště", "Oddělovací transformátor", "DC zdroj",
        "Dočasný / staveništní zdroj", "Jiný zdroj"
    ]
    CONDUCTORS = [
        "", "3/PEN", "3/N/PE", "3/N", "3", "2/N/PE", "2/N", "2/PE", "2",
        "1/N/PE", "1/N", "1/PE", "1", "2/M"
    ]
    VOLTAGES = ["", "230/400 V", "400 V", "230 V", "400/690 V", "690 V", "110 V", "48 V", "24 V", "12 V"]
    SYSTEMS = ["", "TN-C", "TN-S", "TN-C-S", "TT", "IT", "SELV", "PELV", "FELV"]

    def __init__(self, parent, title, values=None):
        super().__init__(parent, title, 820, 720)
        self.values=dict(values or {})
        self.vars={}
        parsed=self._parse_marking(self.values.get('voltage','') or '')
        body=ScrollFrame(self);body.pack(fill='both',expand=True,padx=18,pady=(18,8));body.inner.columnconfigure(1,weight=1)
        fields=[
            ('supply_type','Druh zdroje','combo_edit',self.SOURCE_TYPES,self.values.get('supply_type','')),
            ('designation','Provozovatel / označení zdroje','entry',None,self.values.get('designation','')),
            ('conductors','Vodiče / uspořádání','combo_edit',self.CONDUCTORS,parsed.get('conductors','')),
            ('current_kind','Druh proudu','combo',['AC','DC'],parsed.get('current_kind','AC') or 'AC'),
            ('rated_voltage','Jmenovité napětí','combo_edit',self.VOLTAGES,parsed.get('rated_voltage','')),
            ('frequency','Kmitočet','combo_edit',['','50 Hz','60 Hz'],parsed.get('frequency','50 Hz') if parsed.get('current_kind','AC')!='DC' else ''),
            ('network_system','Druh sítě / ochranné uspořádání','combo_edit',self.SYSTEMS,parsed.get('network_system','')),
            ('backup','Rozsah / úloha zdroje','entry',None,self.values.get('backup','')),
        ]
        row=0
        for key,label,kind,opts,initial in fields:
            ttk.Label(body.inner,text=label,style='Subtle.TLabel').grid(row=row,column=0,sticky='w',padx=(0,12),pady=7)
            v=tk.StringVar(value=str(initial or ''));self.vars[key]=v
            if kind in ('combo','combo_edit'):
                w=ttk.Combobox(body.inner,textvariable=v,values=opts or [],state='readonly' if kind=='combo' else 'normal')
                w.bind('<<ComboboxSelected>>',lambda e:self._update_preview())
                w.bind('<KeyRelease>',lambda e:self._update_preview())
            else:
                w=ttk.Entry(body.inner,textvariable=v);w.bind('<KeyRelease>',lambda e:self._update_preview())
            w.grid(row=row,column=1,sticky='ew',pady=5);row+=1

        help_box=tk.Frame(body.inner,bg='#F7FAFE',highlightbackground='#C9D8E8',highlightthickness=1)
        help_box.grid(row=row,column=0,columnspan=2,sticky='ew',pady=(8,10));row+=1
        tk.Label(help_box,text='Správný zápis napájecí soustavy',bg='#F7FAFE',fg=COLORS['text'],font=('Segoe UI Semibold',9),anchor='w').pack(fill='x',padx=10,pady=(8,2))
        tk.Label(help_box,text='Používáme zápis podle ČSN EN IEC 61293 ed. 2 / IEC 61293: počet krajních vodičů, N/PE/PEN, AC nebo DC, napětí a kmitočet. Druh sítě TN/TT/IT se připojí za lomítko. Např. 3/N/PE AC 230/400 V 50 Hz / TN-S. Písmeno L se za číslo fází nepřidává.',bg='#F7FAFE',fg=COLORS['muted'],font=('Segoe UI',9),anchor='w',justify='left',wraplength=740).pack(fill='x',padx=10,pady=(0,5))
        tk.Label(help_box,text='U TN-C-S záleží na místě popisu: před rozdělením PEN lze uvést 3/PEN … / TN-C-S, za rozdělením 3/N/PE … / TN-C-S. Samotné TN-C-S popisuje, že v části sítě je funkce N a PE sloučená a v části oddělená.',bg='#F7FAFE',fg=COLORS['muted'],font=('Segoe UI',9),anchor='w',justify='left',wraplength=740).pack(fill='x',padx=10,pady=(0,8))

        ttk.Label(body.inner,text='Výsledné označení',style='Subtle.TLabel').grid(row=row,column=0,sticky='nw',padx=(0,12),pady=7)
        self.preview_var=tk.StringVar()
        preview=tk.Entry(body.inner,textvariable=self.preview_var,state='readonly',font=('Segoe UI Semibold',10),relief='solid',bd=1)
        preview.grid(row=row,column=1,sticky='ew',pady=5);row+=1
        ttk.Label(body.inner,text='Poznámka',style='Subtle.TLabel').grid(row=row,column=0,sticky='nw',padx=(0,12),pady=7)
        self.note=tk.Text(body.inner,height=5,font=('Segoe UI',9),wrap='word',relief='solid',bd=1);self.note.insert('1.0',self.values.get('note','') or '');self.note.grid(row=row,column=1,sticky='ew',pady=5)
        self._update_preview()
        footer=ttk.Frame(self);footer.pack(fill='x',padx=18,pady=(0,16));ttk.Button(footer,text='Zrušit',command=self.destroy).pack(side='right');ttk.Button(footer,text='Uložit zdroj',style='Success.TButton',command=self._save).pack(side='right',padx=(0,8))

    @staticmethod
    def _normalize_voltage(v):
        v=(v or '').strip().replace('v','V')
        if not v:return ''
        # Doplnit jednotku pouze tehdy, pokud uživatel zadal jen číslo / poměr čísel.
        if re.fullmatch(r'[0-9]+(?:[.,][0-9]+)?(?:\s*/\s*[0-9]+(?:[.,][0-9]+)?)?',v):
            v=v.replace(' ','')+' V'
        v=re.sub(r'\s*V$', ' V', v, flags=re.I)
        v=re.sub(r'\s*/\s*','/',v)
        return v

    @staticmethod
    def _normalize_frequency(v):
        v=(v or '').strip()
        if not v:return ''
        if re.fullmatch(r'[0-9]+(?:[.,][0-9]+)?',v):v += ' Hz'
        v=re.sub(r'\s*hz$', ' Hz', v, flags=re.I)
        return v

    @classmethod
    def _parse_marking(cls, marking):
        s=' '.join((marking or '').strip().split())
        if not s:return {}
        network_system=''
        # Druh sítě bývá za posledním lomítkem obklopeným mezerami.
        mnet=re.search(r'\s/\s*(TN-C-S|TN-C|TN-S|TT|IT|SELV|PELV|FELV)\s*$',s,re.I)
        if mnet:
            network_system=mnet.group(1).upper();s=s[:mnet.start()].strip()
        m=re.match(r'^(\S+)\s+(AC|DC)\s+(.+)$',s,re.I)
        if not m:return {'rated_voltage':marking}
        conductors,current_kind,rest=m.group(1),m.group(2).upper(),m.group(3).strip()
        frequency=''
        mf=re.search(r'\s+([0-9]+(?:[.,][0-9]+)?\s*Hz)\s*$',rest,re.I)
        if mf:
            frequency=cls._normalize_frequency(mf.group(1));rest=rest[:mf.start()].strip()
        return {'conductors':conductors,'current_kind':current_kind,'rated_voltage':rest,'frequency':frequency,'network_system':network_system}

    def _build_marking(self):
        c=self.vars['conductors'].get().strip()
        kind=self.vars['current_kind'].get().strip().upper()
        voltage=self._normalize_voltage(self.vars['rated_voltage'].get())
        freq=self._normalize_frequency(self.vars['frequency'].get()) if kind=='AC' else ''
        system=self.vars['network_system'].get().strip().upper()
        parts=[x for x in [c,kind,voltage,freq] if x]
        marking=' '.join(parts)
        if system:marking += (' / ' if marking else '') + system
        return marking

    def _update_preview(self):
        if hasattr(self,'preview_var'):self.preview_var.set(self._build_marking())

    def _save(self):
        source=self.vars['supply_type'].get().strip()
        conductors=self.vars['conductors'].get().strip()
        kind=self.vars['current_kind'].get().strip().upper()
        voltage=self._normalize_voltage(self.vars['rated_voltage'].get())
        freq=self._normalize_frequency(self.vars['frequency'].get()) if kind=='AC' else ''
        system=self.vars['network_system'].get().strip().upper()
        if not source:
            messagebox.showwarning('Zdroj napájení','Vyber nebo zadej druh zdroje.',parent=self);return
        if not conductors or not kind or not voltage:
            messagebox.showwarning('Napájecí soustava','Pro standardní označení vyplň uspořádání vodičů, druh proudu a jmenovité napětí.',parent=self);return
        if kind=='AC' and not freq:
            messagebox.showwarning('Napájecí soustava','U střídavé soustavy doplň kmitočet, typicky 50 Hz.',parent=self);return
        if system=='TN-S' and 'PEN' in conductors.upper():
            messagebox.showwarning('Kontrola označení','TN-S má N a PE oddělené v celé síti; kombinace TN-S s vodičem PEN není správná.',parent=self);return
        if system=='TN-C' and ('/N/PE' in conductors.upper() or conductors.upper().endswith('/PE')):
            messagebox.showwarning('Kontrola označení','V TN-C je funkce N a PE sloučena ve vodiči PEN. Pro běžnou trojfázovou TN-C použij 3/PEN.',parent=self);return
        self.vars['rated_voltage'].set(voltage);self.vars['frequency'].set(freq)
        marking=self._build_marking()
        self.result={
            'supply_type':source,
            'designation':self.vars['designation'].get().strip(),
            'voltage':marking,
            'backup':self.vars['backup'].get().strip(),
            'note':self.note.get('1.0','end').strip(),
        }
        self.destroy()




class AresCustomerDialog(Modal):
    """Customer editor with optional ARES lookup by IČO."""
    def __init__(self, parent, title, values=None):
        super().__init__(parent, title, 760, 650)
        values=dict(values or {})
        self.vars={}
        body=ttk.Frame(self);body.pack(fill='both',expand=True,padx=18,pady=18);body.columnconfigure(1,weight=1)
        row=0
        ttk.Label(body,text='IČO',style='Subtle.TLabel').grid(row=row,column=0,sticky='w',padx=(0,10),pady=6)
        self.vars['ico']=tk.StringVar(value=values.get('ico','') or '')
        ttk.Entry(body,textvariable=self.vars['ico']).grid(row=row,column=1,sticky='ew',pady=5)
        ttk.Button(body,text='Načíst z ARES',style='Accent.TButton',command=self.lookup_ares).grid(row=row,column=2,padx=(8,0),pady=5)
        row+=1
        fields=[('name','Název / jméno'),('dic','DIČ'),('address','Adresa / ulice'),('city','Město'),('zip','PSČ'),('contact','Kontaktní osoba'),('phone','Telefon'),('email','E-mail')]
        for key,label in fields:
            ttk.Label(body,text=label,style='Subtle.TLabel').grid(row=row,column=0,sticky='w',padx=(0,10),pady=6)
            self.vars[key]=tk.StringVar(value=values.get(key,'') or '')
            ttk.Entry(body,textvariable=self.vars[key]).grid(row=row,column=1,columnspan=2,sticky='ew',pady=5)
            row+=1
        ttk.Label(body,text='Poznámka',style='Subtle.TLabel').grid(row=row,column=0,sticky='nw',padx=(0,10),pady=6)
        self.note=tk.Text(body,height=6,font=('Segoe UI',9),wrap='word');self.note.insert('1.0',values.get('note','') or '');self.note.grid(row=row,column=1,columnspan=2,sticky='nsew',pady=5);body.rowconfigure(row,weight=1)
        info=tk.Label(self,text='ARES načte veřejné údaje firmy. Kontakty a poznámku doplňuješ lokálně v PZ-REVIZE.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9),justify='left');info.pack(anchor='w',padx=18,pady=(0,8))
        foot=ttk.Frame(self);foot.pack(fill='x',padx=18,pady=(0,16));ttk.Button(foot,text='Zrušit',command=self.destroy).pack(side='right');ttk.Button(foot,text='Uložit',style='Success.TButton',command=self._save).pack(side='right',padx=(0,8))

    def lookup_ares(self):
        ico=''.join(ch for ch in self.vars['ico'].get() if ch.isdigit())
        if len(ico)!=8:
            messagebox.showwarning('ARES','IČO musí mít 8 číslic.');return
        url=f'https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}'
        try:
            req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'PZ-REVIZE/0.3'})
            with urllib.request.urlopen(req,timeout=10) as resp:
                data=json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            messagebox.showerror('ARES',f'ARES vrátil chybu HTTP {e.code}.');return
        except Exception as e:
            messagebox.showerror('ARES',f'Nepodařilo se spojit s ARES:\n{e}');return
        sidlo=data.get('sidlo') or {}
        street=sidlo.get('textovaAdresa') or ''
        if not street:
            parts=[]
            ul=sidlo.get('nazevUlice') or ''
            co=sidlo.get('cisloOrientacni') or ''
            cp=sidlo.get('cisloDomovni') or ''
            if ul:
                num='/'.join(x for x in [str(cp or ''),str(co or '')] if x)
                parts.append((ul+' '+num).strip())
            elif cp:parts.append(f"č.p. {cp}")
            street=', '.join(parts)
        self.vars['ico'].set(data.get('ico') or ico)
        self.vars['name'].set(data.get('obchodniJmeno') or '')
        self.vars['dic'].set(data.get('dic') or '')
        self.vars['address'].set(street)
        self.vars['city'].set(sidlo.get('nazevObce') or sidlo.get('nazevMestskeCastiObvodu') or '')
        self.vars['zip'].set(str(sidlo.get('psc') or ''))
        messagebox.showinfo('ARES','Údaje byly načteny. Před uložením je můžeš upravit.')

    def _save(self):
        result={k:v.get().strip() for k,v in self.vars.items()};result['note']=self.note.get('1.0','end').strip()
        if not result.get('name'):
            messagebox.showwarning('Zákazník','Vyplň název nebo jméno zákazníka.');return
        self.result=result;self.destroy()


class CopyRevisionDialog(Modal):
    def __init__(self,parent,source_no=''):
        super().__init__(parent,'Převzít starou revizi',620,390)
        body=ttk.Frame(self);body.pack(fill='both',expand=True,padx=22,pady=20)
        ttk.Label(body,text=f'Zdrojová revize: {source_no}',font=('Segoe UI Semibold',11)).pack(anchor='w',pady=(0,10))
        tk.Label(body,text='Vyber způsob převzetí. Původní revize zůstane beze změny.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9)).pack(anchor='w',pady=(0,16))
        a=tk.Frame(body,bg='white',highlightbackground=COLORS['line'],highlightthickness=1);a.pack(fill='x',pady=5)
        tk.Label(a,text='Další periodická revize stejného objektu',bg='white',fg=COLORS['text'],font=('Segoe UI Semibold',10)).pack(anchor='w',padx=12,pady=(10,2))
        tk.Label(a,text='Zachová zákazníka, objekt, technickou strukturu, normy, ochrany a vybrané body prohlídky. Vymaže měřené hodnoty, závady, fotografie, přístroje, datum předání a závěr s naměřenými hodnotami.',bg='white',fg=COLORS['muted'],font=('Segoe UI',9),wraplength=540,justify='left').pack(anchor='w',padx=12,pady=(0,8))
        ttk.Button(a,text='Vytvořit další periodickou',style='Success.TButton',command=lambda:self._ok('periodic')).pack(anchor='e',padx=12,pady=(0,10))
        b=tk.Frame(body,bg='white',highlightbackground=COLORS['line'],highlightthickness=1);b.pack(fill='x',pady=8)
        tk.Label(b,text='Technická šablona pro jiného zákazníka / objekt',bg='white',fg=COLORS['text'],font=('Segoe UI Semibold',10)).pack(anchor='w',padx=12,pady=(10,2))
        tk.Label(b,text='Zkopíruje technické tělo zprávy a strukturu obvodů bez zákazníka, revidovaného objektu a původních naměřených hodnot. Vhodné např. pro obdobné elektroměrové rozváděče.',bg='white',fg=COLORS['muted'],font=('Segoe UI',9),wraplength=540,justify='left').pack(anchor='w',padx=12,pady=(0,8))
        ttk.Button(b,text='Vytvořit technickou kopii',style='Accent.TButton',command=lambda:self._ok('template')).pack(anchor='e',padx=12,pady=(0,10))
        ttk.Button(body,text='Zrušit',command=self.destroy).pack(anchor='e',pady=(8,0))
    def _ok(self,mode):self.result=mode;self.destroy()


def _defect_norm_refs(values):
    """Return a normalized list of normative references attached to a defect."""
    values=dict(values or {})
    raw=values.get('_norm_refs')
    if isinstance(raw,list):
        refs=[dict(x) for x in raw if isinstance(x,dict)]
    else:
        refs=[]
        txt=values.get('norm_refs_json') or ''
        if txt:
            try:
                data=json.loads(txt)
                if isinstance(data,list):refs=[dict(x) for x in data if isinstance(x,dict)]
            except Exception:
                refs=[]
    cleaned=[]
    for r in refs:
        rr={
            'standard':str(r.get('standard') or '').strip(),
            'article':str(r.get('article') or '').strip(),
            'citation':str(r.get('citation') or r.get('quote') or '').strip(),
        }
        if any(rr.values()):cleaned.append(rr)
    if not cleaned:
        st=str(values.get('standard') or '').strip();art=str(values.get('article') or '').strip()
        cit=str(values.get('requirement_text') or '').strip()
        if st or art or cit:cleaned.append({'standard':st,'article':art,'citation':cit})
    return cleaned


def _defect_refs_summary(values, include_citation=False):
    refs=_defect_norm_refs(values)
    parts=[]
    for r in refs:
        head=' '.join(x for x in [r.get('standard',''),r.get('article','')] if x).strip()
        if include_citation and r.get('citation'):
            head=(head+(' – ' if head else '')+r.get('citation','')).strip()
        if head:parts.append(head)
    return '; '.join(parts)


class NormReferencesDialog(Modal):
    """Editor for an arbitrary number of standards/articles/citations."""
    def __init__(self,parent,refs=None,title='Normové odkazy závady'):
        super().__init__(parent,title,920,610)
        self.refs=[dict(x) for x in (refs or [])]
        tk.Label(self,text='K jedné závadě lze přiřadit libovolný počet norem, článků a citací / normových požadavků.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9),anchor='w').pack(fill='x',padx=14,pady=(14,6))
        holder=ttk.Frame(self);holder.pack(fill='both',expand=True,padx=14,pady=(0,8))
        self.tree=ttk.Treeview(holder,columns=('standard','article','citation'),show='headings')
        for k,l,w in [('standard','Norma / předpis',220),('article','Článek / ustanovení',150),('citation','Citace / normový požadavek',500)]:
            self.tree.heading(k,text=l);self.tree.column(k,width=w,anchor='w')
        ys=ttk.Scrollbar(holder,orient='vertical',command=self.tree.yview);xs=ttk.Scrollbar(holder,orient='horizontal',command=self.tree.xview);self.tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        self.tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
        self.tree.bind('<Double-1>',lambda e:self.edit_ref())
        bar=ttk.Frame(self);bar.pack(fill='x',padx=14,pady=(0,8))
        ttk.Button(bar,text='Přidat normový odkaz',style='Accent.TButton',command=self.add_ref).pack(side='left')
        ttk.Button(bar,text='Upravit',command=self.edit_ref).pack(side='left',padx=5)
        ttk.Button(bar,text='Odebrat',style='Danger.TButton',command=self.delete_ref).pack(side='left')
        ttk.Button(bar,text='↑',width=3,command=lambda:self.move_ref(-1)).pack(side='left',padx=(12,2));ttk.Button(bar,text='↓',width=3,command=lambda:self.move_ref(1)).pack(side='left')
        foot=ttk.Frame(self);foot.pack(fill='x',padx=14,pady=(0,14));ttk.Button(foot,text='Zrušit',command=self.destroy).pack(side='right');ttk.Button(foot,text='Použít',style='Success.TButton',command=self._save).pack(side='right',padx=(0,8))
        self.refresh()
    def _standard_options(self):
        try:
            db=getattr(self.master,'db',None) or getattr(getattr(self.master,'master',None),'db',None)
            if db:return [r['code'] for r in db.fetchall("SELECT code FROM standards ORDER BY code") if (r['code'] or '').strip()]
        except Exception:pass
        return []
    def _edit_dialog(self,title,values=None):
        fields=[('standard','Norma / předpis','combo_edit',self._standard_options()),('article','Článek / ustanovení'),('citation','Citace / normový požadavek','text')]
        d=FormDialog(self,title,fields,values or {},width=780,height=560);self.wait_window(d);return d.result
    def refresh(self):
        for x in self.tree.get_children():self.tree.delete(x)
        for i,r in enumerate(self.refs):self.tree.insert('','end',iid=str(i),values=(r.get('standard',''),r.get('article',''),r.get('citation','')))
    def add_ref(self):
        r=self._edit_dialog('Přidat normový odkaz')
        if r and any((r.get(k) or '').strip() for k in ('standard','article','citation')):
            self.refs.append({k:(r.get(k) or '').strip() for k in ('standard','article','citation')});self.refresh()
    def edit_ref(self):
        s=self.tree.selection()
        if not s:return
        idx=int(s[0]);r=self._edit_dialog('Upravit normový odkaz',self.refs[idx])
        if r:self.refs[idx]={k:(r.get(k) or '').strip() for k in ('standard','article','citation')};self.refresh()
    def delete_ref(self):
        s=self.tree.selection()
        if s:self.refs.pop(int(s[0]));self.refresh()
    def move_ref(self,delta):
        s=self.tree.selection()
        if not s:return
        i=int(s[0]);j=i+delta
        if j<0 or j>=len(self.refs):return
        self.refs[i],self.refs[j]=self.refs[j],self.refs[i];self.refresh();self.tree.selection_set(str(j));self.tree.see(str(j))
    def _save(self):
        self.result=[dict(x) for x in self.refs];self.destroy()


class DefectDialog(Modal):
    """Defect editor with photos attached at the moment the defect is entered."""
    def __init__(self,parent,title,values=None):
        super().__init__(parent,title,960,840)
        self.values=dict(values or {})
        # 0.4.5: C1/C2/C3 is the actual severity value. Older 0.4.4 records
        # may still keep it in defect_class; prefer that value without guessing
        # a conversion from the former Low/Medium/High/Critical scale.
        sev=(self.values.get('severity') or '').strip().upper()
        legacy_cls=(self.values.get('defect_class') or '').strip().upper()
        if sev not in ('C1','C2','C3') and legacy_cls in ('C1','C2','C3'):
            self.values['severity']=legacy_cls
        elif sev not in ('C1','C2','C3'):
            self.values['severity']=''
        self.vars={};self.photos=[dict(x) for x in self.values.get('_photos',[])];self.text_widgets={};self.norm_refs=_defect_norm_refs(self.values)
        nb=ttk.Notebook(self);nb.pack(fill='both',expand=True,padx=14,pady=14)
        base=ttk.Frame(nb);photos=ttk.Frame(nb);nb.add(base,text='Závada');nb.add(photos,text='Fotografie závady')
        base.columnconfigure(1,weight=1);row=0
        fields=[('category','Oblast / skupina','entry',None),('severity','Závažnost','combo',['','C1','C2','C3']),('status','Stav','combo',['Neodstraněna','Odstraněna při revizi','Doporučení'])]
        for key,label,kind,opts in fields:
            ttk.Label(base,text=label,style='Subtle.TLabel').grid(row=row,column=0,sticky='w',padx=(12,8),pady=7);v=tk.StringVar(value=self.values.get(key,'') or (opts[0] if opts else ''));self.vars[key]=v
            w=ttk.Combobox(base,textvariable=v,values=opts,state='readonly') if kind=='combo' else ttk.Entry(base,textvariable=v);w.grid(row=row,column=1,sticky='ew',padx=(0,12),pady=5);row+=1
        ttk.Label(base,text='C1 – Nebezpečný stav   •   C2 – Potenciálně nebezpečný stav   •   C3 – doporučení',style='Subtle.TLabel').grid(row=row,column=1,sticky='w',padx=(0,12),pady=(0,6));row+=1
        refs=ttk.LabelFrame(base,text='Normy / články / citace');refs.grid(row=row,column=0,columnspan=2,sticky='nsew',padx=12,pady=(4,8));refs.columnconfigure(0,weight=1);refs.rowconfigure(0,weight=1)
        self.norm_tree=ttk.Treeview(refs,columns=('standard','article','citation'),show='headings',height=5)
        for k,l,wid in [('standard','Norma / předpis',190),('article','Článek',120),('citation','Citace / normový požadavek',430)]:self.norm_tree.heading(k,text=l);self.norm_tree.column(k,width=wid,anchor='w')
        self.norm_tree.grid(row=0,column=0,sticky='nsew',padx=(6,0),pady=6);ys=ttk.Scrollbar(refs,orient='vertical',command=self.norm_tree.yview);self.norm_tree.configure(yscrollcommand=ys.set);ys.grid(row=0,column=1,sticky='ns',pady=6)
        rb=ttk.Frame(refs);rb.grid(row=1,column=0,columnspan=2,sticky='ew',padx=6,pady=(0,6));ttk.Button(rb,text='Přidat',style='Accent.TButton',command=self.add_norm_ref).pack(side='left');ttk.Button(rb,text='Upravit',command=self.edit_norm_ref).pack(side='left',padx=5);ttk.Button(rb,text='Odebrat',style='Danger.TButton',command=self.delete_norm_ref).pack(side='left')
        self.norm_tree.bind('<Double-1>',lambda e:self.edit_norm_ref());self.refresh_norm_refs();row+=1
        for key,label in [('defect_text','Text závady'),('note','Poznámka')]:
            ttk.Label(base,text=label,style='Subtle.TLabel').grid(row=row,column=0,sticky='nw',padx=(12,8),pady=7);t=tk.Text(base,height=7 if key=='defect_text' else 4,font=('Segoe UI',9),wrap='word');t.insert('1.0',self.values.get(key,'') or '');t.grid(row=row,column=1,sticky='nsew',padx=(0,12),pady=5);self.text_widgets[key]=t;if_weight=1 if key=='defect_text' else 0;base.rowconfigure(row,weight=if_weight);row+=1
        head=ttk.Frame(photos);head.pack(fill='x',padx=10,pady=10);ttk.Button(head,text='Přidat fotografie',style='Accent.TButton',command=self.add_photos).pack(side='left');ttk.Button(head,text='Otevřít',command=self.open_photo).pack(side='left',padx=5);ttk.Button(head,text='Odebrat',style='Danger.TButton',command=self.remove_photo).pack(side='left')
        self.photo_tree=ttk.Treeview(photos,columns=('file','title','note'),show='headings');
        for k,l,w in [('file','Soubor',300),('title','Popisek',250),('note','Poznámka',260)]:self.photo_tree.heading(k,text=l);self.photo_tree.column(k,width=w,anchor='w')
        self.photo_tree.pack(fill='both',expand=True,padx=10,pady=(0,10));self.photo_tree.bind('<Double-1>',lambda e:self.edit_photo());self.refresh_photos()
        foot=ttk.Frame(self);foot.pack(fill='x',padx=14,pady=(0,14));ttk.Button(foot,text='Zrušit',command=self.destroy).pack(side='right');ttk.Button(foot,text='Uložit závadu',style='Success.TButton',command=self._save).pack(side='right',padx=(0,8))
    def refresh_norm_refs(self):
        for x in self.norm_tree.get_children():self.norm_tree.delete(x)
        for i,r in enumerate(self.norm_refs):self.norm_tree.insert('','end',iid=str(i),values=(r.get('standard',''),r.get('article',''),r.get('citation','')))
    def _norm_standard_options(self):
        try:return [r['code'] for r in self.master.db.fetchall("SELECT code FROM standards ORDER BY code") if (r['code'] or '').strip()]
        except Exception:return []
    def _norm_ref_form(self,title,values=None):
        fields=[('standard','Norma / předpis','combo_edit',self._norm_standard_options()),('article','Článek / ustanovení'),('citation','Citace / normový požadavek','text')]
        d=FormDialog(self,title,fields,values or {},width=780,height=560);self.wait_window(d);return d.result
    def add_norm_ref(self):
        r=self._norm_ref_form('Přidat normový odkaz')
        if r and any((r.get(k) or '').strip() for k in ('standard','article','citation')):
            self.norm_refs.append({k:(r.get(k) or '').strip() for k in ('standard','article','citation')});self.refresh_norm_refs()
    def edit_norm_ref(self):
        sel=self.norm_tree.selection()
        if not sel:return
        idx=int(sel[0]);r=self._norm_ref_form('Upravit normový odkaz',self.norm_refs[idx])
        if r:self.norm_refs[idx]={k:(r.get(k) or '').strip() for k in ('standard','article','citation')};self.refresh_norm_refs();self.norm_tree.selection_set(str(idx))
    def delete_norm_ref(self):
        s=self.norm_tree.selection()
        if s:self.norm_refs.pop(int(s[0]));self.refresh_norm_refs()
    def add_photos(self):
        paths=filedialog.askopenfilenames(title='Fotografie závady',filetypes=[('Obrázky','*.jpg *.jpeg *.png *.webp *.bmp'),('Všechny soubory','*.*')])
        for path in paths:
            self.photos.append({'source_path':path,'stored_path':'','original_name':Path(path).name,'title':'','note':''})
        self.refresh_photos()
    def refresh_photos(self):
        for x in self.photo_tree.get_children():self.photo_tree.delete(x)
        for i,p in enumerate(self.photos):self.photo_tree.insert('','end',iid=str(i),values=(p.get('original_name') or Path(p.get('stored_path') or p.get('source_path') or '').name,p.get('title',''),p.get('note','')))
    def edit_photo(self):
        s=self.photo_tree.selection();
        if not s:return
        idx=int(s[0]);d=FormDialog(self,'Popis fotografie',[('title','Popisek'),('note','Poznámka','text')],self.photos[idx],width=620,height=420);self.wait_window(d)
        if d.result:self.photos[idx].update(d.result);self.refresh_photos()
    def remove_photo(self):
        s=self.photo_tree.selection();
        if s:self.photos.pop(int(s[0]));self.refresh_photos()
    def open_photo(self):
        s=self.photo_tree.selection();
        if not s:return
        p=self.photos[int(s[0])];path=p.get('stored_path') or p.get('source_path')
        if path and Path(path).exists():
            try:
                if os.name=='nt':os.startfile(str(path))
                elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
                else:subprocess.Popen(['xdg-open',str(path)])
            except Exception as e:messagebox.showerror('Fotografie',str(e))
    def _save(self):
        d={k:v.get().strip() for k,v in self.vars.items()};d.update({k:t.get('1.0','end').strip() for k,t in self.text_widgets.items()});d['_photos']=self.photos;d['photo_path']=''
        d['_norm_refs']=[dict(x) for x in self.norm_refs];d['norm_refs_json']=json.dumps(d['_norm_refs'],ensure_ascii=False)
        first=d['_norm_refs'][0] if d['_norm_refs'] else {};d['standard']=first.get('standard','');d['article']=first.get('article','')
        # Keep the legacy column mirrored for backward compatibility with older databases/clients.
        d['defect_class']=d.get('severity','') if d.get('severity','') in ('C1','C2','C3') else ''
        if not d.get('defect_text'):messagebox.showwarning('Závada','Vyplň text závady.');return
        self.result=d;self.destroy()


class OutputOptionsDialog(Modal):
    def __init__(self, parent, title="Výstup revizní zprávy", stamp_available=True, signature_available=True):
        super().__init__(parent, title, 520, 300)
        self.stamp_var=tk.BooleanVar(value=bool(stamp_available))
        self.signature_var=tk.BooleanVar(value=bool(signature_available))
        body=ttk.Frame(self);body.pack(fill='both',expand=True,padx=22,pady=20)
        ttk.Label(body,text="Zvol, co má být ve výsledném PDF / tisku.",style='Subtle.TLabel').pack(anchor='w',pady=(0,14))
        cb1=ttk.Checkbutton(body,text="Zahrnout razítko revizního technika",variable=self.stamp_var);cb1.pack(anchor='w',pady=6)
        cb2=ttk.Checkbutton(body,text="Zahrnout podpis revizního technika",variable=self.signature_var);cb2.pack(anchor='w',pady=6)
        if not stamp_available: cb1.state(['disabled'])
        if not signature_available: cb2.state(['disabled'])
        ttk.Label(body,text="Logo ve zprávě je vždy základní PZ logo bez symbolu měřicího přístroje.",style='Subtle.TLabel').pack(anchor='w',pady=(14,0))
        foot=ttk.Frame(self);foot.pack(fill='x',padx=22,pady=(0,18))
        ttk.Button(foot,text='Zrušit',command=self.destroy).pack(side='right')
        ttk.Button(foot,text='Pokračovat',style='Success.TButton',command=self._ok).pack(side='right',padx=(0,8))
    def _ok(self):
        self.result={'include_stamp':self.stamp_var.get(),'include_signature':self.signature_var.get()}
        self.destroy()


class ElectricalCircuitDialog(Modal):
    """Circuit identification only. Electrical values belong to child measurement points."""
    RESULT_VALUES = ["", "Vyhovuje", "Nevyhovuje", "Nehodnoceno"]

    def __init__(self, parent, title, values=None):
        super().__init__(parent, title, 980, 760)
        self.values = dict(values or {})
        if not str(self.values.get('u0_v') or '').strip():self.values['u0_v']='230'
        if not str(self.values.get('zs_safety_factor') or '').strip():self.values['zs_safety_factor']='1,5'
        self.vars = {}
        self.texts = {}
        note = tk.Label(
            self,
            text="Obvod slouží jako společná hlavička pro jištění a vedení. Pro automatické vyhodnocení Zs zadej jmenovitý proud jističe a charakteristiku B/C/D. U0 se bere přímo z naměřeného napětí U konkrétního měřicího bodu; pokud U chybí, použije se jmenovité 230 V. U jiných ochran můžeš zadat Ia ručně.",
            bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 9), anchor="w", justify="left", wraplength=920
        )
        note.pack(fill="x", padx=16, pady=(14, 8))
        body=ttk.Frame(self);body.pack(fill="both",expand=True,padx=14,pady=8);body.columnconfigure(1,weight=1);body.columnconfigure(3,weight=1)
        self._fields(body, [
            ("designation","Označení obvodu"),("name","Název / účel"),
            ("board","Rozvaděč"),("breaker","Jištění – typ / označení"),
            ("breaker_current_a","Jmenovitý proud In [A]"),("breaker_characteristic","Charakteristika","combo",["","B","C","D","Jiná / dle výrobce"]),
            ("breaker_ia_a","Ia [A] – ruční hodnota / nastavená spoušť"),("zs_safety_factor","Bezpečnostní koeficient km"),
            ("cable","Kabel / vedení"),
            ("note","Poznámka","text",None),
        ])
        current=(self.values.get("result") or "Nehodnoceno").strip()
        status=tk.Frame(self,bg="white",highlightbackground=COLORS["line"],highlightthickness=1)
        status.pack(fill="x",padx=16,pady=(2,10))
        tk.Label(status,text="Automatický výsledek obvodu",bg="white",fg=COLORS["muted"],font=("Segoe UI",9)).pack(side="left",padx=(12,8),pady=9)
        tk.Label(status,text=current,bg="white",fg=COLORS["text"],font=("Segoe UI Semibold",10)).pack(side="left",pady=9)
        tk.Label(status,text="(změní se po uložení / úpravě podřízených měření)",bg="white",fg=COLORS["muted"],font=("Segoe UI",8)).pack(side="left",padx=10,pady=9)
        footer=ttk.Frame(self);footer.pack(fill="x",padx=16,pady=(0,14))
        ttk.Button(footer,text="Zrušit",command=self.destroy).pack(side="right")
        ttk.Button(footer,text="Uložit obvod",style="Success.TButton",command=self._save).pack(side="right",padx=(0,8))

    def _fields(self,parent,fields):
        row=0;colpair=0
        for item in fields:
            key,label=item[0],item[1];kind=item[2] if len(item)>2 else "entry";opts=item[3] if len(item)>3 else None
            if kind=="text":
                ttk.Label(parent,text=label,style="Subtle.TLabel").grid(row=row,column=0,sticky="nw",padx=(14,8),pady=8)
                t=tk.Text(parent,height=5,font=("Segoe UI",9),wrap="word",relief="solid",bd=1);t.insert("1.0",self.values.get(key,"") or "")
                t.grid(row=row,column=1,columnspan=3,sticky="ew",padx=(0,14),pady=6);self.texts[key]=t;row+=1;colpair=0;continue
            cc=0 if colpair==0 else 2
            ttk.Label(parent,text=label,style="Subtle.TLabel").grid(row=row,column=cc,sticky="w",padx=(14 if cc==0 else 10,8),pady=8)
            v=tk.StringVar(value=str(self.values.get(key,"") or ""));self.vars[key]=v
            w=ttk.Combobox(parent,textvariable=v,values=opts or [],state="readonly") if kind=="combo" else ttk.Entry(parent,textvariable=v)
            w.grid(row=row,column=cc+1,sticky="ew",padx=(0,14),pady=6)
            if colpair==0:colpair=1
            else:colpair=0;row+=1

    @staticmethod
    def _first_measurement(*vals):
        for v in vals:
            if str(v or "").strip():return str(v).strip()
        return ""

    def _save(self):
        data=dict(self.values)
        for k,v in self.vars.items():data[k]=v.get().strip()
        for k,t in self.texts.items():data[k]=t.get("1.0","end").strip()
        data["riso"]=self._first_measurement(data.get("riso_l_pe"),data.get("riso_n_pe"),data.get("riso_l_n"),data.get("riso"))
        data["row_type"]="CIRCUIT"
        self.result=data;self.destroy()


class ContinuityMeasurementDialog(Modal):
    RESULT_VALUES=["","Vyhovuje","Nevyhovuje","Nehodnoceno"]
    def __init__(self,parent,title,values=None):
        super().__init__(parent,title,820,560)
        self.values=dict(values or {});self.vars={}
        body=ttk.Frame(self);body.pack(fill='both',expand=True,padx=22,pady=18);body.columnconfigure(1,weight=1)
        fields=[
            ('designation','Bod měření / označení'),('name','Popis místa spojitosti'),('board','Rozvaděč / prostor'),
            ('pe_continuity','Naměřená spojitost / přechodový odpor [Ω]'),('zs_limit','Mez / kritérium [Ω]'),
            ('pe_result','Vyhodnocení','combo',self.RESULT_VALUES),('note','Poznámka')
        ]
        for row,item in enumerate(fields):
            key,label=item[0],item[1];kind=item[2] if len(item)>2 else 'entry';opts=item[3] if len(item)>3 else None
            ttk.Label(body,text=label,style='Subtle.TLabel').grid(row=row,column=0,sticky='w',padx=(0,10),pady=7)
            v=tk.StringVar(value=str(self.values.get(key,'') or ''));self.vars[key]=v
            w=ttk.Combobox(body,textvariable=v,values=opts,state='readonly') if kind=='combo' else ttk.Entry(body,textvariable=v)
            w.grid(row=row,column=1,sticky='ew',pady=7)
        foot=ttk.Frame(self);foot.pack(fill='x',padx=22,pady=(0,18));ttk.Button(foot,text='Zrušit',command=self.destroy).pack(side='right');ttk.Button(foot,text='Uložit měření',style='Success.TButton',command=self._save).pack(side='right',padx=(0,8))
    @staticmethod
    def _num(value):
        try:return float(str(value or '').strip().replace(',','.').replace('≤','').replace('<','').replace('>',''))
        except Exception:return None
    def _save(self):
        d=dict(self.values);d.update({k:v.get().strip() for k,v in self.vars.items()});d['row_type']='CONTINUITY'
        val=self._num(d.get('pe_continuity'));lim=self._num(d.get('zs_limit'))
        if val is not None and lim is not None:d['pe_result']='Vyhovuje' if val<=lim else 'Nevyhovuje'
        d['result']=d.get('pe_result','') or ('Nehodnoceno' if d.get('pe_continuity') else '')
        self.result=d;self.destroy()


class MeasurementPointDialog(Modal):
    """Additional measurement point under one circuit/breaker (e.g. L1–PE, L2–PE, L3–PE)."""
    RESULT_VALUES=["","Vyhovuje","Nevyhovuje","Nehodnoceno"]
    POINTS=["","L1–PE","L2–PE","L3–PE","N–PE","L1–N","L2–N","L3–N","L1–L2","L2–L3","L1–L3","Vlastní"]
    def __init__(self,parent,title,values=None):
        super().__init__(parent,title,900,650)
        self.values=dict(values or {});self.vars={}
        body=ttk.Frame(self);body.pack(fill='both',expand=True,padx=22,pady=18);body.columnconfigure(1,weight=1);body.columnconfigure(3,weight=1)
        fields=[
            ('designation','Měřený vodič / dvojice','combo',self.POINTS),('name','Vlastní popis / místo','entry',None),
            ('measured_voltage','Napětí U [V]','entry',None),('riso','Izolační odpor Riso [MΩ]','entry',None),
            ('insulation_voltage','Zkušební napětí izolace [V]','entry',None),('zs','Impedance poruchové smyčky Zs [Ω]','entry',None),
            ('zs_limit','Max. Zs [Ω] (automaticky z obvodu / ručně)','entry',None),('ik','Vypočtený / měřený zkratový proud Ik [A]','entry',None),
            ('impedance_result','Vyhodnocení impedance','combo',self.RESULT_VALUES),('insulation_result','Vyhodnocení izolace','combo',self.RESULT_VALUES),
            ('note','Poznámka','entry',None),
        ]
        self.widgets={}
        for n,item in enumerate(fields):
            key,label,kind,opts=item;row=n//2;cc=(n%2)*2
            ttk.Label(body,text=label,style='Subtle.TLabel').grid(row=row,column=cc,sticky='w',padx=(0 if cc==0 else 14,8),pady=7)
            v=tk.StringVar(value=str(self.values.get(key,'') or ''));self.vars[key]=v
            w=ttk.Combobox(body,textvariable=v,values=opts or [],state='readonly') if kind=='combo' else ttk.Entry(body,textvariable=v)
            self.widgets[key]=w
            w.grid(row=row,column=cc+1,sticky='ew',pady=7)
        self.vars['designation'].trace_add('write',lambda *_:self._sync_point_fields())
        self._sync_point_fields()
        note=tk.Label(body,text='Každým stiskem + Měření přidáš právě jeden řádek. Měřicí bod je podřízený jednomu obvodu/jističi, takže jištění a kabel se neopakují. Celkový stav bodu i obvodu program skládá automaticky z dílčích výsledků.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9),justify='left',anchor='w',wraplength=820)
        note.grid(row=(len(fields)+1)//2,column=0,columnspan=4,sticky='ew',pady=(10,0))
        foot=ttk.Frame(self);foot.pack(fill='x',padx=22,pady=(0,18));ttk.Button(foot,text='Zrušit',command=self.destroy).pack(side='right');ttk.Button(foot,text='Uložit měřicí bod',style='Success.TButton',command=self._save).pack(side='right',padx=(0,8))
    def _sync_point_fields(self):
        phase_phase=is_phase_phase_point(self.vars.get('designation').get() if self.vars.get('designation') else '')
        # L1-L2 / L2-L3 / L1-L3 are insulation measurements only in this workflow.
        for key in ('measured_voltage','zs','zs_limit','ik','impedance_result'):
            w=self.widgets.get(key)
            if not w:continue
            if phase_phase:
                try:w.configure(state='disabled')
                except Exception:pass
            else:
                try:w.configure(state='readonly' if key=='impedance_result' else 'normal')
                except Exception:pass

    @staticmethod
    def _num(value):
        try:return float(str(value or '').strip().replace(',','.').replace('≤','').replace('<','').replace('>',''))
        except Exception:return None

    def _save(self):
        d=dict(self.values);d.update({k:v.get().strip() for k,v in self.vars.items()});d['row_type']='POINT'
        if is_phase_phase_point(d.get('designation')):
            for key in ('measured_voltage','zs','zs_limit','ik','impedance_result'):d[key]=''
        # Pokud je zadána Zs i její mez, program vyhodnotí impedanci automaticky.
        zs=self._num(d.get('zs'));lim=self._num(d.get('zs_limit'))
        if zs is not None and lim is not None:
            d['impedance_result']='Vyhovuje' if zs<=lim else 'Nevyhovuje'
        active=[]
        if str(d.get('zs') or '').strip() or str(d.get('impedance_result') or '').strip():active.append(d.get('impedance_result',''))
        if str(d.get('riso') or '').strip() or str(d.get('insulation_result') or '').strip():active.append(d.get('insulation_result',''))
        active=[str(x or '').strip() for x in active]
        if any(x=='Nevyhovuje' for x in active):d['result']='Nevyhovuje'
        elif active and all(x=='Vyhovuje' for x in active):d['result']='Vyhovuje'
        elif active:d['result']='Nehodnoceno'
        else:d['result']='Nehodnoceno'
        self.result=d;self.destroy()


class MeasurementEntryModeDialog(Modal):
    """Choose between a single measuring point and bulk multi-phase entry."""
    def __init__(self,parent):
        super().__init__(parent,'Nové měření',620,360)
        self.mode=tk.StringVar(value='single')
        body=ttk.Frame(self);body.pack(fill='both',expand=True,padx=24,pady=20)
        ttk.Label(body,text='Jak chceš zadat měření?',font=('Segoe UI Semibold',12)).pack(anchor='w',pady=(0,12))
        one=tk.Frame(body,bg='white',highlightbackground=COLORS['line'],highlightthickness=1);one.pack(fill='x',pady=5)
        ttk.Radiobutton(one,text='Jedna fáze / jeden měřicí bod',variable=self.mode,value='single').pack(anchor='w',padx=12,pady=(10,2))
        tk.Label(one,text='Otevře běžný formulář pro jeden bod, například L1–N nebo L1–PE.',bg='white',fg=COLORS['muted'],font=('Segoe UI',9)).pack(anchor='w',padx=34,pady=(0,10))
        many=tk.Frame(body,bg='white',highlightbackground=COLORS['line'],highlightthickness=1);many.pack(fill='x',pady=5)
        ttk.Radiobutton(many,text='Více fází – hromadné zadání',variable=self.mode,value='bulk').pack(anchor='w',padx=12,pady=(10,2))
        tk.Label(many,text='Jedna velká tabulka pro L1/L2/L3 vůči PE, N a mezi fázemi. Každý vyplněný řádek se uloží jako samostatné měření pod obvod.',bg='white',fg=COLORS['muted'],font=('Segoe UI',9),wraplength=520,justify='left').pack(anchor='w',padx=34,pady=(0,10))
        foot=ttk.Frame(self);foot.pack(fill='x',padx=24,pady=(0,18))
        ttk.Button(foot,text='Zrušit',command=self.destroy).pack(side='right')
        ttk.Button(foot,text='Pokračovat',style='Success.TButton',command=self._ok).pack(side='right',padx=(0,8))
    def _ok(self):
        self.result=self.mode.get();self.destroy()


class BulkMeasurementDialog(Modal):
    """Bulk editor: one visible row equals one child measurement point."""
    POINTS=('L1–PE','L2–PE','L3–PE','L1–N','L2–N','L3–N','L1–PEN','L2–PEN','L3–PEN','L1–L2','L2–L3','L1–L3')
    RESULT_VALUES=('Vyhovuje','Nevyhovuje','Nehodnoceno')
    def __init__(self,parent,title='Hromadné měření více fází'):
        super().__init__(parent,title,1420,760)
        self.rows=[]
        info=tk.Label(self,text='Kompletní zadání měření pro PE, PEN, N a mezi fázemi. U L–PE, L–PEN a L–N lze zadat U, Riso i Zs. Řádky L1–L2/L2–L3/L1–L3 jsou pouze pro izolační odpor – U, Zs, mez Zs a Ik jsou záměrně vypnuté.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9),anchor='w',justify='left',wraplength=1360)
        info.pack(fill='x',padx=18,pady=(14,7))
        tools=ttk.Frame(self);tools.pack(fill='x',padx=18,pady=(0,6))
        ttk.Button(tools,text='Označit vše',command=lambda:self._set_all(True)).pack(side='left')
        ttk.Button(tools,text='Odznačit vše',command=lambda:self._set_all(False)).pack(side='left',padx=5)
        ttk.Label(tools,text='Hodnoty zadávej bez jednotek nebo s nimi – v přehledu a PDF se jednotky doplní automaticky.',style='Subtle.TLabel').pack(side='left',padx=12)
        holder=ttk.Frame(self);holder.pack(fill='both',expand=True,padx=18,pady=4)
        canvas=tk.Canvas(holder,bg=COLORS['bg'],highlightthickness=0);ys=ttk.Scrollbar(holder,orient='vertical',command=canvas.yview);xs=ttk.Scrollbar(holder,orient='horizontal',command=canvas.xview)
        canvas.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);canvas.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
        grid=tk.Frame(canvas,bg='white');win=canvas.create_window((0,0),window=grid,anchor='nw')
        def sync(_=None):canvas.configure(scrollregion=canvas.bbox('all'))
        grid.bind('<Configure>',sync)
        headers=['Použít','Bod měření','U [V]','Riso [MΩ]','Zs [Ω]','Mez Zs [Ω]','Ik [A]','Výsledek','Poznámka']
        widths=[8,14,12,14,12,14,12,15,24]
        for c,(h,w) in enumerate(zip(headers,widths)):
            tk.Label(grid,text=h,bg='#EEF0F2',fg=COLORS['text'],font=('Segoe UI Semibold',9),bd=1,relief='solid',padx=6,pady=7,width=w,anchor='w').grid(row=0,column=c,sticky='nsew')
        for rr,point in enumerate(self.POINTS,1):
            use=tk.BooleanVar(value=False);des=tk.StringVar(value=point);u=tk.StringVar();riso=tk.StringVar();zs=tk.StringVar();lim=tk.StringVar();ik=tk.StringVar();result=tk.StringVar(value='Vyhovuje');note=tk.StringVar()
            row={'use':use,'designation':des,'measured_voltage':u,'riso':riso,'zs':zs,'zs_limit':lim,'ik':ik,'result':result,'note':note}
            self.rows.append(row)
            ttk.Checkbutton(grid,variable=use).grid(row=rr,column=0,padx=8,pady=5)
            ttk.Entry(grid,textvariable=des,width=14).grid(row=rr,column=1,sticky='ew',padx=3,pady=4)
            phase_phase=is_phase_phase_point(point)
            for c,key,width in [(2,'measured_voltage',12),(3,'riso',14),(4,'zs',12),(5,'zs_limit',14),(6,'ik',12)]:
                ent=ttk.Entry(grid,textvariable=row[key],width=width)
                if phase_phase and key in ('measured_voltage','zs','zs_limit','ik'):ent.configure(state='disabled')
                ent.grid(row=rr,column=c,sticky='ew',padx=3,pady=4)
            ttk.Combobox(grid,textvariable=result,values=self.RESULT_VALUES,state='readonly',width=14).grid(row=rr,column=7,sticky='ew',padx=3,pady=4)
            ttk.Entry(grid,textvariable=note,width=24).grid(row=rr,column=8,sticky='ew',padx=3,pady=4)
            for key in ('measured_voltage','riso','zs','zs_limit','ik','note'):
                row[key].trace_add('write',lambda *a,u=use:u.set(True))
        for c in range(len(headers)):grid.columnconfigure(c,weight=1 if c in (1,8) else 0)
        foot=ttk.Frame(self);foot.pack(fill='x',padx=18,pady=(6,16))
        ttk.Button(foot,text='Zrušit',command=self.destroy).pack(side='right')
        ttk.Button(foot,text='Uložit vybrané řádky',style='Success.TButton',command=self._save).pack(side='right',padx=(0,8))
    @staticmethod
    def _num(value):
        try:return float(str(value or '').strip().replace(',','.').replace('≤','').replace('<','').replace('>',''))
        except Exception:return None
    def _set_all(self,value):
        for row in self.rows:row['use'].set(bool(value))
    def _save(self):
        out=[]
        for row in self.rows:
            if not row['use'].get():continue
            d={k:v.get().strip() for k,v in row.items() if k!='use'}
            if not d.get('designation'):continue
            if is_phase_phase_point(d.get('designation')):
                for key in ('measured_voltage','zs','zs_limit','ik','impedance_result'):d[key]=''
            chosen=d.get('result') or 'Vyhovuje'
            zs=self._num(d.get('zs'));lim=self._num(d.get('zs_limit'))
            if zs is not None and lim is not None:
                chosen='Vyhovuje' if zs<=lim else 'Nevyhovuje'
            d['impedance_result']=chosen if d.get('zs') else ''
            d['insulation_result']=chosen if d.get('riso') else ''
            d['result']=chosen
            d['insulation_voltage']=''
            d['name']=''
            d['row_type']='POINT'
            out.append(d)
        if not out:
            messagebox.showinfo('Hromadné měření','Není označen žádný řádek k uložení.');return
        self.result=out;self.destroy()


class BulkEditElectricalMeasurementsDialog(Modal):
    """Spreadsheet-style editor for existing electrical measuring points and continuity rows."""
    RESULT_VALUES=("","Vyhovuje","Nevyhovuje","Nehodnoceno")
    POINT_FIELDS=(
        ('designation','Bod',14),('name','Popis / místo',20),('measured_voltage','U [V]',10),
        ('riso','Riso [MΩ]',12),('insulation_voltage','Zkuš. U [V]',11),('zs','Zs [Ω]',10),
        ('zs_limit','Mez Zs [Ω]',11),('ik','Ik [A]',10),('impedance_result','Zs výsledek',13),
        ('insulation_result','Riso výsledek',13),('note','Poznámka',22),
    )
    CONT_FIELDS=(
        ('designation','Bod',14),('name','Popis / místo',24),('pe_continuity','Spojitost [Ω]',13),
        ('zs_limit','Mez [Ω]',11),('pe_result','Výsledek',13),('note','Poznámka',28),
    )
    def __init__(self,parent,measurements):
        super().__init__(parent,'Hromadná editace měřených údajů',1500,860)
        self.source=measurements
        self.point_rows=[];self.cont_rows=[]
        info=tk.Label(self,text='Upravuj hodnoty přímo jako v tabulce. Změny se uloží najednou. Při vyplněné Zs a mezi Zs se výsledek impedance dopočítá automaticky; stejně tak spojitost při zadané hodnotě a mezi. RCD a SPD zůstávají v této verzi ve svých specializovaných formulářích.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9),anchor='w',justify='left',wraplength=1440)
        info.pack(fill='x',padx=18,pady=(14,8))
        nb=ttk.Notebook(self);nb.pack(fill='both',expand=True,padx=18,pady=(0,8))
        ptab=ttk.Frame(nb);ctab=ttk.Frame(nb);nb.add(ptab,text='Měřicí body');nb.add(ctab,text='Spojitost')
        keymap={r.get('item_key'):r for r in measurements if r.get('item_key')}
        points=[];cont=[]
        for idx,row in enumerate(measurements):
            typ=(row.get('row_type') or '').upper()
            parent_row=keymap.get(row.get('parent_key'))
            parent_label=''
            if parent_row:
                parent_label=(parent_row.get('designation') or parent_row.get('rcd_designation') or parent_row.get('name') or '').strip()
            if typ=='POINT':points.append((idx,row,parent_label))
            elif typ=='CONTINUITY':cont.append((idx,row,parent_label))
        self._build_grid(ptab,points,self.POINT_FIELDS,self.point_rows,'point')
        self._build_grid(ctab,cont,self.CONT_FIELDS,self.cont_rows,'continuity')
        if not points and not cont:
            tk.Label(ptab,text='V revizi zatím nejsou žádné měřicí body ani měření spojitosti.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',10)).pack(anchor='w',padx=14,pady=18)
        foot=ttk.Frame(self);foot.pack(fill='x',padx=18,pady=(4,16))
        ttk.Button(foot,text='Zrušit',command=self.destroy).pack(side='right')
        ttk.Button(foot,text='Uložit všechny změny',style='Success.TButton',command=self._save).pack(side='right',padx=(0,8))
        ttk.Label(foot,text=f'Měřicí body: {len(points)}   •   Spojitost: {len(cont)}',style='Subtle.TLabel').pack(side='left')

    def _build_grid(self,parent,rows,fields,target,kind):
        holder=ttk.Frame(parent);holder.pack(fill='both',expand=True,padx=6,pady=6)
        canvas=tk.Canvas(holder,bg=COLORS['bg'],highlightthickness=0);ys=ttk.Scrollbar(holder,orient='vertical',command=canvas.yview);xs=ttk.Scrollbar(holder,orient='horizontal',command=canvas.xview)
        canvas.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);canvas.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
        grid=tk.Frame(canvas,bg='white');canvas.create_window((0,0),window=grid,anchor='nw');grid.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        headers=[('Obvod',18)]+[(lab,w) for _,lab,w in fields]
        for c,(lab,w) in enumerate(headers):
            tk.Label(grid,text=lab,bg='#EEF0F2',fg=COLORS['text'],font=('Segoe UI Semibold',9),bd=1,relief='solid',padx=5,pady=7,width=w,anchor='w').grid(row=0,column=c,sticky='nsew')
        result_keys={'impedance_result','insulation_result','pe_result'}
        for rr,(idx,row,parent_label) in enumerate(rows,1):
            tk.Label(grid,text=parent_label,bg='white',fg=COLORS['muted'],font=('Segoe UI Semibold',9),bd=1,relief='solid',padx=5,pady=5,width=18,anchor='w').grid(row=rr,column=0,sticky='nsew')
            vars_={}
            for cc,(key,lab,width) in enumerate(fields,1):
                v=tk.StringVar(value=str(row.get(key,'') or ''));vars_[key]=v
                if key in result_keys:
                    w=ttk.Combobox(grid,textvariable=v,values=self.RESULT_VALUES,state='readonly',width=width)
                else:
                    w=ttk.Entry(grid,textvariable=v,width=width)
                if kind=='point' and is_phase_phase_point(row.get('designation')) and key in ('measured_voltage','zs','zs_limit','ik','impedance_result'):
                    w.configure(state='disabled')
                w.grid(row=rr,column=cc,sticky='nsew',padx=2,pady=2)
            target.append({'index':idx,'kind':kind,'vars':vars_})
        for c in range(len(headers)):grid.columnconfigure(c,weight=1 if c in (1,2,len(headers)-1) else 0)

    @staticmethod
    def _num(value):
        try:return float(str(value or '').strip().replace(',','.').replace('≤','').replace('<','').replace('>',''))
        except Exception:return None

    def _save(self):
        updates=[]
        for entry in self.point_rows+self.cont_rows:
            idx=entry['index'];row=dict(self.source[idx]);d={k:v.get().strip() for k,v in entry['vars'].items()};row.update(d)
            if entry['kind']=='point':
                if is_phase_phase_point(row.get('designation')):
                    for key in ('measured_voltage','zs','zs_limit','ik','impedance_result'):row[key]=''
                zs=self._num(row.get('zs'));lim=self._num(row.get('zs_limit'))
                if zs is not None and lim is not None:row['impedance_result']='Vyhovuje' if zs<=lim else 'Nevyhovuje'
                active=[]
                if str(row.get('zs') or '').strip() or str(row.get('impedance_result') or '').strip():active.append(str(row.get('impedance_result') or '').strip())
                if str(row.get('riso') or '').strip() or str(row.get('insulation_result') or '').strip():active.append(str(row.get('insulation_result') or '').strip())
                if any(x=='Nevyhovuje' for x in active):row['result']='Nevyhovuje'
                elif active and all(x=='Vyhovuje' for x in active):row['result']='Vyhovuje'
                elif active:row['result']='Nehodnoceno'
                else:row['result']='Nehodnoceno'
            else:
                val=self._num(row.get('pe_continuity'));lim=self._num(row.get('zs_limit'))
                if val is not None and lim is not None:row['pe_result']='Vyhovuje' if val<=lim else 'Nevyhovuje'
                row['result']=row.get('pe_result','') or ('Nehodnoceno' if row.get('pe_continuity') else '')
            updates.append((idx,row))
        self.result=updates;self.destroy()


class RCDMeasurementDialog(Modal):
    """RCD is a structural parent row. Visible test waveforms change with the selected RCD type."""
    RESULT_VALUES=["","Vyhovuje","Nevyhovuje","Nehodnoceno"]
    TYPE_TESTS={
        'AC':['ac_pos','ac_neg'],
        'A':['ac_pos','ac_neg','a_pos','a_neg'],
        'F':['ac_pos','ac_neg','a_pos','a_neg','f_pos','f_neg'],
        'B':['ac_pos','ac_neg','a_pos','a_neg','b_pos','b_neg'],
        'B+':['ac_pos','ac_neg','a_pos','a_neg','b_pos','b_neg'],
        'Jiný':['ac_pos','ac_neg','a_pos','a_neg','f_pos','f_neg','b_pos','b_neg'],
    }
    TEST_LABELS={
        'ac_pos':'AC +','ac_neg':'AC −','a_pos':'A + (pulzující DC)','a_neg':'A − (pulzující DC)',
        'f_pos':'F +','f_neg':'F −','b_pos':'B + (hladký DC)','b_neg':'B − (hladký DC)'
    }
    TYPE_DESCRIPTIONS={
        'AC':'Typ AC je určen pro sinusové střídavé reziduální proudy. Program proto nabídne zkoušky AC v obou polaritách / počátečních fázích.',
        'A':'Typ A reaguje na sinusové AC i pulzující stejnosměrné reziduální proudy. Zobrazí se AC a pulzující DC zkoušky v obou polaritách.',
        'F':'Typ F navazuje na typ A a používá se také u obvodů se složenými a frekvenčně ovlivněnými reziduálními proudy, typicky u jednofázových měničových spotřebičů. Zobrazí se AC, A a F zkoušky.',
        'B':'Typ B pokrývá AC, pulzující DC i hladké DC reziduální proudy a další průběhy podle provedení chrániče. Zobrazí se AC, A a B zkoušky.',
        'B+':'Typ B+ je rozšířená varianta typu B. Konkrétní frekvenční rozsah a mezní hodnoty vždy ověř podle výrobce a použité normy; program zobrazí AC, A a B zkoušky.',
        'Jiný':'Nestandardní / jiné provedení. Program zobrazí všechny dostupné skupiny měření; odborný rozsah a limity nastav podle dokumentace výrobce.'
    }
    def __init__(self,parent,title,values=None):
        super().__init__(parent,title,1280,900)
        self.values=dict(values or {});self.vars={};self.test_frames={}
        top=ttk.Frame(self);top.pack(fill='x',padx=18,pady=(14,6));top.columnconfigure(1,weight=1);top.columnconfigure(3,weight=1)
        fields=[
            ('rcd_designation','Označení RCD','entry',None),('board','Rozvaděč / umístění','entry',None),
            ('name','Výrobce / model','entry',None),('rcd_device_kind','Druh přístroje','combo',['','RCCB','RCBO','Jiný']),
            ('rcd_type','Typ citlivosti','combo',['','AC','A','F','B','B+','Jiný']),('rcd_delay_type','Časové provedení','combo',['','Bez zpoždění','G','S','Jiné']),
            ('rcd_poles','Počet pólů','combo',['','1P+N','2P','3P','3P+N','4P']),('rcd_in_a','Jmenovitý proud In [A]','entry',None),
            ('breaker_characteristic','Charakteristika jističe RCBO','combo',['','B','C','D','Jiná / dle výrobce']),('cable','Kabel / vedení','entry',None),
            ('rcd_idn_ma','Jmenovitý reziduální proud IΔn [mA]','entry',None),('rcd_result','Výsledek části RCD','combo',self.RESULT_VALUES),
        ]
        for i,(key,label,kind,opts) in enumerate(fields):
            r=i//2;cc=0 if i%2==0 else 2
            ttk.Label(top,text=label,style='Subtle.TLabel').grid(row=r,column=cc,sticky='w',padx=(0 if cc==0 else 12,8),pady=5)
            v=tk.StringVar(value=str(self.values.get(key,'') or ''));self.vars[key]=v
            if kind=='combo':w=ttk.Combobox(top,textvariable=v,values=opts,state='readonly')
            else:w=ttk.Entry(top,textvariable=v)
            w.grid(row=r,column=cc+1,sticky='ew',pady=5)
            if key=='rcd_type':w.bind('<<ComboboxSelected>>',lambda e:self._refresh_tests())
            if key=='rcd_device_kind':w.bind('<<ComboboxSelected>>',lambda e:self._refresh_device_kind())

        help_box=tk.Frame(self,bg='#F7FAFE',highlightbackground='#C9D8E8',highlightthickness=1)
        help_box.pack(fill='x',padx=18,pady=(4,8))
        tk.Label(help_box,text='Co zvolený typ znamená',bg='#F7FAFE',fg=COLORS['text'],font=('Segoe UI Semibold',9),anchor='w').pack(fill='x',padx=10,pady=(8,2))
        self.rcd_help_var=tk.StringVar(value='Vyber typ citlivosti chrániče. Program podle něj zobrazí odpovídající skupiny zkoušek.')
        tk.Label(help_box,textvariable=self.rcd_help_var,bg='#F7FAFE',fg=COLORS['text'],font=('Segoe UI',9),anchor='w',justify='left',wraplength=1190).pack(fill='x',padx=10,pady=(0,4))
        tk.Label(help_box,text='Sloupce: vybavovací proud = proud při vypnutí; čas = doba vybavení; Uc = dotykové napětí. Označení + / − rozlišuje dvě polarity / počáteční fáze zkoušky. Společné ověření dole zahrnuje nevypnutí pod IΔn, zkoušku 5× IΔn a tlačítko TEST.',bg='#F7FAFE',fg=COLORS['muted'],font=('Segoe UI',8),anchor='w',justify='left',wraplength=1190).pack(fill='x',padx=10,pady=(0,8))
        holder=ttk.Frame(self);holder.pack(fill='both',expand=True,padx=18,pady=(0,8))
        canvas=tk.Canvas(holder,bg=COLORS['bg'],highlightthickness=0);vs=ttk.Scrollbar(holder,orient='vertical',command=canvas.yview);self.tests=ttk.Frame(canvas)
        self.tests.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));self.tests_window=canvas.create_window((0,0),window=self.tests,anchor='nw');canvas.configure(yscrollcommand=vs.set)
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(self.tests_window,width=max(e.width-2,1)))
        canvas.pack(side='left',fill='both',expand=True);vs.pack(side='right',fill='y')

        wave=ttk.LabelFrame(self.tests,text='Měření RCD');wave.pack(fill='x',pady=(0,8),ipadx=6,ipady=5)
        hdr=tk.Frame(wave,bg='#E9EDF2');hdr.pack(fill='x',padx=6,pady=(5,2))
        for txt,w,expand in [('Průběh / zkouška',28,True),('Vybavovací proud IΔ [mA]',21,False),('Čas vybavení [ms]',16,False),('Dotykové napětí Uc [V]',20,False)]:
            tk.Label(hdr,text=txt,bg='#E9EDF2',fg=COLORS['text'],font=('Segoe UI Semibold',9),width=w,anchor='w',padx=5,pady=6).pack(side='left',fill='x',expand=expand)
        self.wave_rows=ttk.Frame(wave);self.wave_rows.pack(fill='x',padx=6,pady=(0,5))
        for key in ['ac_pos','ac_neg','a_pos','a_neg','f_pos','f_neg','b_pos','b_neg']:
            f=ttk.Frame(self.wave_rows);self.test_frames[key]=f
            tk.Label(f,text=self.TEST_LABELS[key],bg='white',fg=COLORS['text'],font=('Segoe UI Semibold',9),width=28,anchor='w',padx=5,pady=5).pack(side='left',fill='x',expand=True)
            for suffix,width in [('trip_ma',21),('time_ms',16),('touch_v',20)]:
                dbkey=f'rcd_{key}_{suffix}';v=tk.StringVar(value=str(self.values.get(dbkey,'') or ''));self.vars[dbkey]=v;ttk.Entry(f,textvariable=v,width=width).pack(side='left',padx=2,pady=3)

        common=ttk.LabelFrame(self.tests,text='Společné ověření');common.pack(fill='x',pady=(4,4),ipadx=8,ipady=6);common.columnconfigure(1,weight=1);common.columnconfigure(3,weight=1)
        cfields=[
            ('rcd_no_trip_result','Nevypnutí při 0,5 × IΔn','combo',['','Vyhovuje','Nevyhovuje','Nezkoušeno']),
            ('rcd_5x_pos_ms','5 × IΔn, AC+ – čas [ms]','entry',None),('rcd_5x_neg_ms','5 × IΔn, AC− – čas [ms]','entry',None),
            ('rcd_test_button','Kontrolní tlačítko TEST','combo',['','Funkční','Nefunkční','Nezkoušeno']),
        ]
        for i,(key,label,kind,opts) in enumerate(cfields):
            r=i//2;cc=0 if i%2==0 else 2;ttk.Label(common,text=label,style='Subtle.TLabel').grid(row=r,column=cc,sticky='w',padx=(8,6),pady=5)
            v=tk.StringVar(value=str(self.values.get(key,'') or ''));self.vars[key]=v
            w=ttk.Combobox(common,textvariable=v,values=opts,state='readonly') if kind=='combo' else ttk.Entry(common,textvariable=v);w.grid(row=r,column=cc+1,sticky='ew',padx=(0,8),pady=5)
        self.rcd_5x_hint=tk.StringVar(value='')
        ttk.Label(common,textvariable=self.rcd_5x_hint,style='Subtle.TLabel').grid(row=2,column=0,columnspan=4,sticky='w',padx=8,pady=(1,4))
        if self.vars.get('rcd_idn_ma'):
            self.vars['rcd_idn_ma'].trace_add('write',lambda *a:self._refresh_5x_hint())
        self._refresh_5x_hint()
        self.rcbo_frame=ttk.LabelFrame(self.tests,text='Měření jističové části kombinovaného chrániče RCBO')
        self.rcbo_rows=[];existing_points={str(x.get('designation') or ''):x for x in self.values.get('_measurement_points',[])}
        headers=['Použít','Bod měření','U [V]','Riso [MΩ]','Zs [Ω]','Mez Zs [Ω]','Ik [A]','Výsledek','Poznámka']
        for c,h in enumerate(headers):tk.Label(self.rcbo_frame,text=h,bg='#EEF0F2',fg=COLORS['text'],font=('Segoe UI Semibold',8),padx=4,pady=5).grid(row=0,column=c,sticky='nsew',padx=1,pady=1)
        for rr,point in enumerate(BulkMeasurementDialog.POINTS,1):
            old=existing_points.get(point,{})
            use=tk.BooleanVar(value=bool(old));des=tk.StringVar(value=point)
            row={'use':use,'designation':des}
            for key in ('measured_voltage','riso','zs','zs_limit','ik','note'):row[key]=tk.StringVar(value=str(old.get(key,'') or ''))
            row['result']=tk.StringVar(value=str(old.get('result','') or 'Vyhovuje'));self.rcbo_rows.append(row)
            ttk.Checkbutton(self.rcbo_frame,variable=use).grid(row=rr,column=0,padx=4,pady=2)
            ttk.Entry(self.rcbo_frame,textvariable=des,width=11).grid(row=rr,column=1,sticky='ew',padx=1,pady=2)
            phase_phase=is_phase_phase_point(point)
            for c,key,width in [(2,'measured_voltage',8),(3,'riso',9),(4,'zs',8),(5,'zs_limit',9),(6,'ik',8)]:
                ent=ttk.Entry(self.rcbo_frame,textvariable=row[key],width=width)
                if phase_phase and key in ('measured_voltage','zs','zs_limit','ik'):ent.configure(state='disabled')
                ent.grid(row=rr,column=c,sticky='ew',padx=1,pady=2)
            ttk.Combobox(self.rcbo_frame,textvariable=row['result'],values=BulkMeasurementDialog.RESULT_VALUES,state='readonly',width=11).grid(row=rr,column=7,sticky='ew',padx=1,pady=2)
            ttk.Entry(self.rcbo_frame,textvariable=row['note'],width=18).grid(row=rr,column=8,sticky='ew',padx=1,pady=2)
            for key in ('measured_voltage','riso','zs','zs_limit','ik','note'):row[key].trace_add('write',lambda *a,u=use:u.set(True))
        self.rcbo_frame.columnconfigure(8,weight=1)
        note_frame=ttk.Frame(self.tests);note_frame.pack(fill='x',pady=(8,0));ttk.Label(note_frame,text='Poznámka',style='Subtle.TLabel').pack(anchor='w');self.note=tk.Text(note_frame,height=4,font=('Segoe UI',9),wrap='word',relief='solid',bd=1);self.note.insert('1.0',self.values.get('note','') or '');self.note.pack(fill='x',pady=(4,0))
        foot=ttk.Frame(self);foot.pack(fill='x',padx=18,pady=(0,14));ttk.Button(foot,text='Zrušit',command=self.destroy).pack(side='right');ttk.Button(foot,text='Uložit chránič',style='Success.TButton',command=self._save).pack(side='right',padx=(0,8))
        self._refresh_tests();self._refresh_device_kind()

    def _refresh_5x_hint(self):
        if not hasattr(self,'rcd_5x_hint'):return
        raw=self.vars.get('rcd_idn_ma').get().strip() if self.vars.get('rcd_idn_ma') else ''
        try:
            val=float(raw.replace(',','.'))
            txt=(f'{5*val:g}').replace('.',',')
            self.rcd_5x_hint.set(f'Pro IΔn = {raw} mA odpovídá zkoušce 5 × IΔn proud {txt} mA.')
        except Exception:
            self.rcd_5x_hint.set('Zadej IΔn [mA]; zkušební proud 5 × IΔn se zobrazí zde.')

    def _refresh_tests(self):
        typ=self.vars.get('rcd_type').get().strip() if self.vars.get('rcd_type') else ''
        active=self.TYPE_TESTS.get(typ,[])
        for key,frame in self.test_frames.items():
            frame.pack_forget()
        for key in active:self.test_frames[key].pack(fill='x',pady=1)
        if hasattr(self,'rcd_help_var'):
            self.rcd_help_var.set(self.TYPE_DESCRIPTIONS.get(typ,'Vyber typ citlivosti chrániče. Program podle něj zobrazí odpovídající skupiny zkoušek.'))

    def _refresh_device_kind(self):
        if not hasattr(self,'rcbo_frame'):return
        if self.vars.get('rcd_device_kind').get().strip()=='RCBO':self.rcbo_frame.pack(fill='x',pady=(8,4),ipadx=5,ipady=5)
        else:self.rcbo_frame.pack_forget()

    def _collect_rcbo_points(self):
        if self.vars.get('rcd_device_kind').get().strip()!='RCBO':return []
        out=[]
        for row in self.rcbo_rows:
            if not row['use'].get():continue
            d={k:v.get().strip() for k,v in row.items() if k!='use'}
            if is_phase_phase_point(d.get('designation')):
                for key in ('measured_voltage','zs','zs_limit','ik'):d[key]=''
            chosen=d.get('result') or 'Vyhovuje';zs=_electrical_num(d.get('zs'));lim=_electrical_num(d.get('zs_limit'))
            if zs is not None and lim is not None:chosen='Vyhovuje' if zs<=lim else 'Nevyhovuje'
            d.update({'row_type':'POINT','impedance_result':chosen if d.get('zs') else '', 'insulation_result':chosen if d.get('riso') else '', 'result':chosen, 'insulation_voltage':'', 'name':''})
            out.append(d)
        return out

    def _save(self):
        d=dict(self.values);d.update({k:v.get().strip() for k,v in self.vars.items()});d['note']=self.note.get('1.0','end').strip();d['row_type']='RCD'
        d['breaker_current_a']=d.get('rcd_in_a','') if d.get('rcd_device_kind')=='RCBO' else ''
        d.setdefault('zs_safety_factor','1,5');d.setdefault('u0_v','230')
        d['_measurement_points']=self._collect_rcbo_points()
        # Compatibility with older output/data fields.
        d['rcd_time_1x_pos_ms']=d.get('rcd_ac_pos_time_ms','');d['rcd_time_1x_neg_ms']=d.get('rcd_ac_neg_time_ms','')
        d['rcd_time_5x_ms']=d.get('rcd_5x_pos_ms','');d['rcd_trip_ma']=d.get('rcd_ac_pos_trip_ma','');d['rcd_touch_v']=d.get('rcd_ac_pos_touch_v','')
        d['rcd']=d.get('rcd_ac_pos_time_ms','') or d.get('rcd_a_pos_time_ms','') or d.get('rcd_b_pos_time_ms','') or ''
        results=[]
        if d.get('rcd_result'):results.append(d.get('rcd_result'))
        results.extend(x.get('result','Nehodnoceno') for x in d['_measurement_points'])
        d['result']='Nevyhovuje' if 'Nevyhovuje' in results else ('Vyhovuje' if results and all(x=='Vyhovuje' for x in results) else 'Nehodnoceno')
        self.result=d;self.destroy()


class JobDetailDialog(Modal):
    def __init__(self, app, job_id: int):
        self.app = app; self.db = app.db; self.job_id = job_id
        super().__init__(app, "Zakázka", 900, 620)
        self.job = self.db.fetchone("""SELECT j.*, c.name customer_name, o.name object_name FROM jobs j
                                     LEFT JOIN customers c ON c.id=j.customer_id LEFT JOIN objects o ON o.id=j.object_id WHERE j.id=?""", (job_id,))
        if not self.job:
            self.destroy(); return
        head = tk.Frame(self, bg="white", highlightbackground=COLORS["line"], highlightthickness=1); head.pack(fill="x", padx=14, pady=(14,8))
        tk.Label(head, text=f"{self.job['job_no'] or 'Zakázka'}  •  {self.job['title']}", bg="white", fg=COLORS["text"], font=("Segoe UI Semibold",14)).pack(anchor="w", padx=14, pady=(12,4))
        tk.Label(head, text=f"{self.job['customer_name'] or ''}  |  {self.job['object_name'] or ''}  |  Stav: {self.job['status'] or ''}", bg="white", fg=COLORS["muted"], font=("Segoe UI",9)).pack(anchor="w", padx=14, pady=(0,12))
        bar = ttk.Frame(self); bar.pack(fill="x", padx=14, pady=6)
        ttk.Button(bar, text="Upravit zakázku", command=self._edit_job).pack(side="left")
        for rtype,label in [("ELEKTRO","+ Elektro"),("LPS","+ LPS"),("STROJ","+ Stroj"),("VNEJSI","+ Vnější vlivy")]:
            ttk.Button(bar, text=label, command=lambda rt=rtype:self._new_revision(rt)).pack(side="right", padx=3)
        tk.Label(self, text="Revize přiřazené k zakázce – dvojklikem otevřít", bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI",9)).pack(anchor="w", padx=16, pady=(8,4))
        cols=[("no","Číslo",130),("type","Typ",150),("kind","Druh",110),("status","Stav",120),("result","Výsledek",130),("date","Vyhotoveno",110)]
        holder=ttk.Frame(self); holder.pack(fill="both", expand=True, padx=14, pady=(0,14))
        self.tree=ttk.Treeview(holder,columns=[x[0] for x in cols],show="headings")
        for k,l,w in cols:self.tree.heading(k,text=l);self.tree.column(k,width=w,anchor="w")
        self.tree.pack(fill="both",expand=True); self.tree.bind("<Double-1>",lambda e:self._open_revision())
        foot=ttk.Frame(self);foot.pack(fill="x",padx=14,pady=(0,14));ttk.Button(foot,text="Otevřít revizi",style="Success.TButton",command=self._open_revision).pack(side="right");ttk.Button(foot,text="Zavřít",command=self.destroy).pack(side="right",padx=6)
        self.refresh()

    def refresh(self):
        if not hasattr(self,"tree"): return
        for x in self.tree.get_children(): self.tree.delete(x)
        rows=self.db.fetchall("SELECT * FROM revisions WHERE job_id=? ORDER BY id DESC",(self.job_id,))
        tmap={"ELEKTRO":"Elektrická instalace","LPS":"LPS","STROJ":"Strojní zařízení","VNEJSI":"Vnější vlivy"}
        for r in rows:self.tree.insert("","end",iid=str(r["id"]),values=(r["revision_no"],tmap.get(r["revision_type"],r["revision_type"]),r["revision_kind"],r["status"],r["result"],display_date(r["issued_on"])))

    def _open_revision(self):
        s=self.tree.selection()
        if not s:return
        rid=int(s[0]);r=self.db.fetchone("SELECT revision_type FROM revisions WHERE id=?",(rid,))
        if r:self.destroy();self.app.open_revision_editor(r["revision_type"],rid)

    def _new_revision(self, rtype):
        self.destroy(); self.app.open_revision_editor(rtype, initial_job_id=self.job_id)

    def _edit_job(self):
        self.destroy(); self.app.show_page("jobs"); page=self.app.pages.get("jobs")
        if page:
            try: page.tree.selection_set(str(self.job_id)); page.tree.focus(str(self.job_id)); page.edit()
            except Exception: pass


class BasePage(ttk.Frame):
    def __init__(self, app, title: str, subtitle: str = ""):
        super().__init__(app.content, style="TFrame")
        self.app = app
        self.db = app.db
        head = ttk.Frame(self)
        head.pack(fill="x", padx=24, pady=(22, 12))
        ttk.Label(head, text=title, style="Title.TLabel").pack(anchor="w")
        if subtitle:
            ttk.Label(head, text=subtitle, style="Subtle.TLabel").pack(anchor="w", pady=(3,0))
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=24, pady=(0, 22))

    def refresh(self):
        pass


class DashboardPage(BasePage):
    def __init__(self, app):
        super().__init__(app, "Přehled", "Rychlý přehled revizí, termínů a přístrojů")
        self.cards = {}
        cards = ttk.Frame(self.body)
        cards.pack(fill="x")
        for i in range(4):
            cards.columnconfigure(i, weight=1)
        specs = [
            ("rev_open", "Revize k dokončení", COLORS["orange"]),
            ("due", "Termíny k řešení (90 dní)", COLORS["green"]),
            ("customers", "Zákazníci", COLORS["blue"]),
            ("cal", "Kalibrace do 60 dní", COLORS["red"]),
        ]
        for col, (key, title, accent) in enumerate(specs):
            card = tk.Frame(cards, bg="white", highlightbackground=COLORS["line"], highlightthickness=1)
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col==0 else 7, 0 if col==3 else 7), pady=(0, 14))
            tk.Frame(card, bg=accent, height=4).pack(fill="x")
            tk.Label(card, text=title, bg="white", fg=COLORS["muted"], font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=14, pady=(12,2))
            val = tk.Label(card, text="0", bg="white", fg=COLORS["text"], font=("Segoe UI Semibold", 24))
            val.pack(anchor="w", padx=14, pady=(0,14))
            self.cards[key] = val

        lower = ttk.Frame(self.body)
        lower.pack(fill="both", expand=True)
        lower.columnconfigure(0, weight=2)
        lower.columnconfigure(1, weight=1)
        lower.rowconfigure(0, weight=1)

        recent_card = tk.Frame(lower, bg="white", highlightbackground=COLORS["line"], highlightthickness=1)
        recent_card.grid(row=0, column=0, sticky="nsew", padx=(0,7))
        tk.Label(recent_card, text="Poslední revize", bg="white", fg=COLORS["text"], font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=14, pady=(12,7))
        self.tree = ttk.Treeview(recent_card, columns=("no","type","obj","status","date"), show="headings", height=12)
        for c,t,w in [("no","Číslo",110),("type","Typ",120),("obj","Revidované zařízení",300),("status","Stav",110),("date","Vyhotoveno",110)]:
            self.tree.heading(c,text=t); self.tree.column(c,width=w,anchor="w")
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0,12))
        self.tree.bind("<Double-1>", self._open_recent_revision)

        info = tk.Frame(lower, bg="white", highlightbackground=COLORS["line"], highlightthickness=1)
        info.grid(row=0, column=1, sticky="nsew", padx=(7,0))
        tk.Label(info, text="PZ-REVIZE", bg="white", fg=COLORS["text"], font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=16, pady=(16,4))
        tk.Label(info, text="Elektrická instalace • LPS • Strojní zařízení • Vnější vlivy", bg="white", fg=COLORS["muted"], font=("Segoe UI", 9), justify="left", wraplength=340).pack(anchor="w", padx=16)
        tk.Label(info, text=f"Verze {VERSION}", bg="#EEF3F7", fg="#46525E", font=("Segoe UI Semibold", 9), padx=8, pady=3).pack(anchor="w", padx=16, pady=(14,6))
        nas_line=tk.Label(info, textvariable=app.nas_status_var, bg="white", fg=COLORS["green_dark"], font=("Segoe UI Semibold", 9), anchor="w", cursor="hand2")
        nas_line.pack(fill="x", padx=16, pady=(2,8)); nas_line.bind('<Button-1>', lambda e: app.open_nas_sync()); app.dashboard_nas_label=nas_line
        txt = (
            "Normativní databáze je navržena jako rozšiřitelná. Další nahrané normy lze doplnit bez změny databázové struktury.\n\n"
            "Program ukládá závady do revize jako historickou kopii - pozdější editace závadovníku starou zprávu nezmění."
        )
        tk.Label(info, text=txt, bg="white", fg=COLORS["text"], font=("Segoe UI", 9), justify="left", wraplength=330).pack(anchor="w", padx=16, pady=(4,12))
        ttk.Button(info, text="Nová revize elektro", style="Accent.TButton", command=lambda: app.open_revision_editor("ELEKTRO")).pack(fill="x", padx=16, pady=4)
        ttk.Button(info, text="Nová revize stroje", command=lambda: app.open_revision_editor("STROJ")).pack(fill="x", padx=16, pady=4)
        ttk.Button(info, text="Nová revize LPS", style="Success.TButton", command=lambda: app.open_revision_editor("LPS")).pack(fill="x", padx=16, pady=4)
        ttk.Button(info, text="Nový VV", command=lambda: app.open_revision_editor("VNEJSI")).pack(fill="x", padx=16, pady=4)
        self.refresh()

    def refresh(self):
        open_count = self.db.fetchone("SELECT COUNT(*) FROM revisions WHERE status<>'Uzavřená'")[0]
        due_rows=self.db.fetchall("""SELECT next_revision_on FROM revisions
            WHERE COALESCE(deadline_watch,1)=1 AND next_revision_on<>''""")
        due=0
        for _r in due_rows:
            _d,_month_only=_parse_due_date(_r['next_revision_on'])
            if _d is not None and (_d-date.today()).days <= 90:
                due += 1
        cust = self.db.fetchone("SELECT COUNT(*) FROM customers")[0]
        cal = self.db.fetchone("SELECT COUNT(*) FROM instruments WHERE calibration_due<>'' AND date(calibration_due) BETWEEN date('now') AND date('now','+60 day')")[0]
        self.cards["rev_open"].config(text=str(open_count)); self.cards["due"].config(text=str(due)); self.cards["customers"].config(text=str(cust)); self.cards["cal"].config(text=str(cal))
        for x in self.tree.get_children(): self.tree.delete(x)
        rows = self.db.fetchall("""
            SELECT r.id,r.revision_no,r.revision_type,r.status,r.issued_on,r.subject object_name
            FROM revisions r ORDER BY r.id DESC LIMIT 12
        """)
        maptype={"ELEKTRO":"Elektrická instalace","LPS":"LPS","STROJ":"Strojní zařízení","VNEJSI":"Vnější vlivy"}
        for r in rows:
            self.tree.insert("", "end", iid=str(r["id"]), values=(r["revision_no"],maptype.get(r["revision_type"],r["revision_type"]),r["object_name"] or "",r["status"],display_date(r["issued_on"])))

    def _open_recent_revision(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        rid = int(sel[0])
        row = self.db.fetchone("SELECT revision_type FROM revisions WHERE id=?", (rid,))
        if row:
            self.app.open_revision_editor(row["revision_type"], rid)


class DeadlinesPage(BasePage):
    """Overview of revision deadlines that are actively monitored."""
    def __init__(self, app):
        super().__init__(app, "Termíny", "Hlídání termínů příštích revizí. U každé revize lze hlídání samostatně vypnout.")
        tb = ttk.Frame(self.body); tb.pack(fill="x", pady=(0,8))
        self.show_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(tb, text="Zobrazit i vypnuté hlídání", variable=self.show_all_var, command=self.refresh).pack(side="left")
        ttk.Button(tb, text="Otevřít revizi", command=self.open_selected).pack(side="right")
        ttk.Button(tb, text="Zapnout / vypnout hlídání", style="Accent.TButton", command=self.toggle_watch).pack(side="right", padx=6)
        holder = tk.Frame(self.body, bg="white", highlightbackground=COLORS["line"], highlightthickness=1)
        holder.pack(fill="both", expand=True)
        cols=[("state","Stav",120),("date","Příští revize",105),("days","Zbývá",90),("no","Číslo",120),("type","Typ",100),("customer","Zákazník",200),("subject","Revidované zařízení",310),("watch","Hlídání",80)]
        self.tree=ttk.Treeview(holder,columns=[x[0] for x in cols],show="headings")
        center_cols={"state","date","days","no","type","watch"}
        for key,label,width in cols:
            self.tree.heading(key,text=label,anchor="center" if key in center_cols else "w")
            self.tree.column(key,width=width,minwidth=width,stretch=False,anchor="center" if key in center_cols else "w")
        xbar=ttk.Scrollbar(holder,orient="horizontal",command=self.tree.xview)
        self.tree.configure(xscrollcommand=xbar.set)
        self.tree.pack(fill="both",expand=True,padx=2,pady=(2,0))
        xbar.pack(fill="x",padx=2,pady=(0,2))
        self.tree.bind("<Double-1>",lambda e:self.open_selected())
        self.tree.tag_configure("overdue", foreground=COLORS["red"])
        self.tree.tag_configure("soon", foreground=COLORS["orange_dark"])
        self.tree.tag_configure("off", foreground=COLORS["muted"])
        self.refresh()

    def selected(self):
        sel=self.tree.selection();return int(sel[0]) if sel else None

    def refresh(self):
        if not hasattr(self,'tree'): return
        for x in self.tree.get_children(): self.tree.delete(x)
        where="next_revision_on<>''"
        if not self.show_all_var.get(): where += " AND COALESCE(deadline_watch,1)=1"
        rows=self.db.fetchall(f"""SELECT r.id,r.revision_no,r.revision_type,r.next_revision_on,r.deadline_watch,
                                      r.subject,c.name customer_name
                               FROM revisions r LEFT JOIN customers c ON c.id=r.customer_id
                               WHERE {where}""")
        rows=sorted(rows,key=lambda r:((_parse_due_date(r['next_revision_on'])[0] or date.max),r['id']))
        maptype={"ELEKTRO":"Elektro","LPS":"LPS","STROJ":"Stroj","VNEJSI":"Vnější vlivy"}
        for r in rows:
            watching=int(r['deadline_watch'] if r['deadline_watch'] is not None else 1)==1
            d,_month_only=_parse_due_date(r['next_revision_on'])
            days=(d-date.today()).days if d else None
            if not watching:
                state="VYPNUTO"; days_txt=""; tag="off"
            elif days is None:
                state="NEPLATNÉ DATUM";days_txt="";tag="soon"
            elif days < 0:
                state="PO TERMÍNU";days_txt=f"{abs(days)} dní po";tag="overdue"
            elif days == 0:
                state="DNES";days_txt="dnes";tag="overdue"
            elif days <= 30:
                state="DO 30 DNÍ";days_txt=f"{days} dní";tag="soon"
            elif days <= 90:
                state="DO 90 DNÍ";days_txt=f"{days} dní";tag="soon"
            else:
                state="NAPLÁNOVÁNO";days_txt=f"{days} dní";tag=""
            self.tree.insert('', 'end', iid=str(r['id']), tags=((tag,) if tag else ()), values=(state,display_date(r['next_revision_on']),days_txt,r['revision_no'],maptype.get(r['revision_type'],r['revision_type']),r['customer_name'] or '',r['subject'] or '',"Ano" if watching else "Vypnuto"))

    def open_selected(self):
        rid=self.selected()
        if not rid:return
        r=self.db.fetchone("SELECT revision_type FROM revisions WHERE id=?",(rid,))
        if r:self.app.open_revision_editor(r['revision_type'],rid)

    def toggle_watch(self):
        rid=self.selected()
        if not rid:return
        r=self.db.fetchone("SELECT COALESCE(deadline_watch,1) watch,next_revision_on FROM revisions WHERE id=?",(rid,))
        if not r:return
        new=0 if int(r['watch']) else 1
        self.db.execute("UPDATE revisions SET deadline_watch=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(new,rid))
        if new and not (r['next_revision_on'] or '').strip():
            messagebox.showinfo("Hlídání termínu","Hlídání je zapnuté, ale termín příští revize zatím není vyplněný.")
        self.app.refresh_all()


class TablePage(BasePage):
    columns = []
    def __init__(self, app, title, subtitle=""):
        super().__init__(app, title, subtitle)
        toolbar = ttk.Frame(self.body); toolbar.pack(fill="x", pady=(0,8)); self.toolbar = toolbar
        self.search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.search_var, width=34).pack(side="left")
        self.search_var.trace_add("write", lambda *a: self.refresh())
        ttk.Button(toolbar, text="Nový", style="Accent.TButton", command=self.add).pack(side="right")
        ttk.Button(toolbar, text="Upravit", command=self.edit).pack(side="right", padx=6)
        ttk.Button(toolbar, text="Smazat", style="Danger.TButton", command=self.delete).pack(side="right")
        holder = tk.Frame(self.body, bg="white", highlightbackground=COLORS["line"], highlightthickness=1)
        holder.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(holder, columns=[c[0] for c in self.columns], show="headings")
        for key,label,width in self.columns:
            self.tree.heading(key,text=label); self.tree.column(key,width=width,anchor="w")
        ys=ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview); xs=ttk.Scrollbar(holder, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0,column=0,sticky="nsew"); ys.grid(row=0,column=1,sticky="ns"); xs.grid(row=1,column=0,sticky="ew")
        holder.rowconfigure(0,weight=1); holder.columnconfigure(0,weight=1)
        self.tree.bind("<Double-1>", lambda e:self.edit())
        self.refresh()

    def selected_id(self):
        s=self.tree.selection(); return int(s[0]) if s else None
    def add(self): pass
    def edit(self): pass
    def delete(self): pass


class CustomersPage(TablePage):
    columns=[("name","Zákazník",260),("ico","IČO",110),("city","Město",170),("contact","Kontakt",180),("phone","Telefon",140),("email","E-mail",220)]
    fields=[("name","Název / jméno"),("ico","IČO"),("dic","DIČ"),("address","Adresa"),("city","Město"),("zip","PSČ"),("contact","Kontaktní osoba"),("phone","Telefon"),("email","E-mail"),("note","Poznámka","text")]
    def __init__(self,app):
        super().__init__(app,"Zákazníci","Evidence zákazníků a provozovatelů • dvojklik otevře revizní zprávy zákazníka")
        ttk.Button(self.toolbar,text="Revizní zprávy",style="Success.TButton",command=self.open_detail).pack(side="right",padx=6)
        self.tree.bind("<Double-1>",lambda e:self.open_detail())
    def refresh(self):
        q=f"%{self.search_var.get().strip()}%" if hasattr(self,'search_var') else "%"
        rows=self.db.fetchall("SELECT * FROM customers WHERE name LIKE ? OR city LIKE ? OR ico LIKE ? ORDER BY name",(q,q,q))
        if hasattr(self,'tree'):
            for x in self.tree.get_children(): self.tree.delete(x)
            for r in rows:self.tree.insert("","end",iid=str(r["id"]),values=(r["name"],r["ico"],r["city"],r["contact"],r["phone"],r["email"]))
    def add(self):
        d=AresCustomerDialog(self.app,"Nový zákazník"); self.wait_window(d)
        if d.result and d.result["name"]:
            keys=['name','ico','dic','address','city','zip','contact','phone','email','note']
            self.db.execute("INSERT INTO customers(name,ico,dic,address,city,zip,contact,phone,email,note) VALUES(?,?,?,?,?,?,?,?,?,?)",tuple(d.result.get(k,'') for k in keys)); self.refresh(); self.app.refresh_all()
    def edit(self):
        i=self.selected_id();
        if not i:return
        r=dict(self.db.fetchone("SELECT * FROM customers WHERE id=?",(i,)))
        d=AresCustomerDialog(self.app,"Upravit zákazníka",r); self.wait_window(d)
        if d.result:
            keys=['name','ico','dic','address','city','zip','contact','phone','email','note']
            vals=[d.result.get(k,'') for k in keys]+[i]
            self.db.execute("UPDATE customers SET name=?,ico=?,dic=?,address=?,city=?,zip=?,contact=?,phone=?,email=?,note=? WHERE id=?",vals); self.refresh(); self.app.refresh_all()
    def delete(self):
        i=self.selected_id();
        if i and messagebox.askyesno("Smazat","Opravdu smazat zákazníka? Revize zůstanou zachovány bez vazby."):
            self.db.execute("DELETE FROM customers WHERE id=?",(i,)); self.refresh(); self.app.refresh_all()

    def open_detail(self):
        i=self.selected_id()
        if i:CustomerDetailDialog(self.app,i)


class CustomerDetailDialog(Modal):
    def __init__(self,app,customer_id):
        self.app=app;self.db=app.db;self.customer_id=customer_id
        c=self.db.fetchone("SELECT * FROM customers WHERE id=?",(customer_id,))
        super().__init__(app,f"Zákazník – {c['name'] if c else ''}",980,680)
        top=tk.Frame(self,bg='white',highlightbackground=COLORS['line'],highlightthickness=1);top.pack(fill='x',padx=12,pady=12)
        if c:
            txt=f"{c['name']}\n{c['address'] or ''}  {c['zip'] or ''} {c['city'] or ''}\nIČO: {c['ico'] or ''}    Kontakt: {c['contact'] or ''}    {c['phone'] or ''}    {c['email'] or ''}"
            tk.Label(top,text=txt,bg='white',fg=COLORS['text'],font=('Segoe UI',10),justify='left').pack(anchor='w',padx=14,pady=12)
        bar=ttk.Frame(self);bar.pack(fill='x',padx=12,pady=(0,8))
        ttk.Button(bar,text='Nový VV',command=lambda:self.new_revision('VNEJSI')).pack(side='right',padx=3)
        ttk.Button(bar,text='Nová revize stroje',command=lambda:self.new_revision('STROJ')).pack(side='right',padx=3)
        ttk.Button(bar,text='Nová LPS',command=lambda:self.new_revision('LPS')).pack(side='right',padx=3)
        ttk.Button(bar,text='Nová revize elektro',style='Accent.TButton',command=lambda:self.new_revision('ELEKTRO')).pack(side='right',padx=3)
        ttk.Button(bar,text='Otevřít revizi',style='Success.TButton',command=self.open_revision).pack(side='left')
        cols=[('no','Číslo revize',140),('type','Typ',120),('kind','Druh',100),('subject','Revidované zařízení',310),('date','Vyhotoveno',100),('result','Výsledek',120),('status','Stav',110)]
        self.tree=ttk.Treeview(self,columns=[x[0] for x in cols],show='headings')
        for k,l,w in cols:self.tree.heading(k,text=l);self.tree.column(k,width=w,anchor='w')
        self.tree.pack(fill='both',expand=True,padx=12,pady=(0,12));self.tree.bind('<Double-1>',lambda e:self.open_revision());self.refresh()
    def refresh(self):
        for x in self.tree.get_children():self.tree.delete(x)
        rows=self.db.fetchall("SELECT * FROM revisions WHERE customer_id=? ORDER BY id DESC",(self.customer_id,))
        names={'ELEKTRO':'Elektro','LPS':'LPS','STROJ':'Stroj','VNEJSI':'Vnější vlivy'}
        for r in rows:self.tree.insert('','end',iid=str(r['id']),values=(r['revision_no'],names.get(r['revision_type'],r['revision_type']),r['revision_kind'],r['subject'],display_date(r['issued_on']),r['result'],r['status']))
    def open_revision(self):
        s=self.tree.selection()
        if not s:return
        r=self.db.fetchone("SELECT revision_type FROM revisions WHERE id=?",(int(s[0]),))
        if r:self.app.open_revision_editor(r['revision_type'],int(s[0]))
    def new_revision(self,rtype):
        w=RevisionEditor(self.app,rtype)
        label=next((k for k,v in w.customer_map.items() if v==self.customer_id),'')
        if label:w.vars['customer'].set(label)


class ObjectsPage(TablePage):
    columns=[("name","Objekt",270),("customer","Zákazník",230),("address","Adresa",260),("type","Typ",160),("year","Rok",70),("recon","Rekonstrukce",100)]
    def __init__(self,app): super().__init__(app,"Objekty","Objekty, provozovny a lokality zákazníků")
    def _fields(self):
        cust=self.db.fetchall("SELECT id,name FROM customers ORDER BY name")
        self.customer_map={f"{r['name']}  [#{r['id']}]":r['id'] for r in cust}
        return [("customer","Zákazník","combo",[""]+list(self.customer_map)),("name","Název objektu"),("address","Adresa"),("city","Město"),("zip","PSČ"),("object_type","Typ objektu"),("built_year","Rok zřízení"),("reconstruction_year","Rok rekonstrukce"),("note","Poznámka","text")]
    def refresh(self):
        q=f"%{self.search_var.get().strip()}%" if hasattr(self,'search_var') else "%"
        rows=self.db.fetchall("""SELECT o.*,c.name customer_name FROM objects o LEFT JOIN customers c ON c.id=o.customer_id WHERE o.name LIKE ? OR o.address LIKE ? OR c.name LIKE ? ORDER BY o.name""",(q,q,q))
        if hasattr(self,'tree'):
            for x in self.tree.get_children(): self.tree.delete(x)
            for r in rows:self.tree.insert("","end",iid=str(r["id"]),values=(r["name"],r["customer_name"],r["address"],r["object_type"],r["built_year"] or "",r["reconstruction_year"] or ""))
    def _values(self,r=None):
        vals=dict(r or {})
        if r and r["customer_id"]:
            label=next((k for k,v in self.customer_map.items() if v==r["customer_id"]),""); vals["customer"]=label
        return vals
    def add(self):
        fields=self._fields(); d=FormDialog(self.app,"Nový objekt",fields); self.wait_window(d)
        if d.result and d.result["name"]:
            cid=self.customer_map.get(d.result.pop("customer"))
            self.db.execute("INSERT INTO objects(customer_id,name,address,city,zip,object_type,built_year,reconstruction_year,note) VALUES(?,?,?,?,?,?,?,?,?)",(cid,d.result['name'],d.result['address'],d.result['city'],d.result['zip'],d.result['object_type'],d.result['built_year'] or None,d.result['reconstruction_year'] or None,d.result['note'])); self.refresh(); self.app.refresh_all()
    def edit(self):
        i=self.selected_id();
        if not i:return
        fields=self._fields(); r=self.db.fetchone("SELECT * FROM objects WHERE id=?",(i,)); vals=self._values(r)
        d=FormDialog(self.app,"Upravit objekt",fields,vals); self.wait_window(d)
        if d.result:
            cid=self.customer_map.get(d.result.pop("customer")); self.db.execute("UPDATE objects SET customer_id=?,name=?,address=?,city=?,zip=?,object_type=?,built_year=?,reconstruction_year=?,note=? WHERE id=?",(cid,d.result['name'],d.result['address'],d.result['city'],d.result['zip'],d.result['object_type'],d.result['built_year'] or None,d.result['reconstruction_year'] or None,d.result['note'],i)); self.refresh(); self.app.refresh_all()
    def delete(self):
        i=self.selected_id();
        if i and messagebox.askyesno("Smazat","Opravdu smazat objekt? Revize zůstanou zachovány bez vazby."):
            self.db.execute("DELETE FROM objects WHERE id=?",(i,)); self.refresh(); self.app.refresh_all()


class JobsPage(TablePage):
    columns=[("no","Zakázka",120),("title","Název",270),("customer","Zákazník",220),("object","Objekt",220),("status","Stav",120),("due","Termín",110)]
    def __init__(self,app):
        super().__init__(app,"Zakázky","Zakázka → objekt → revize → výstup")
        ttk.Button(self.toolbar,text="Otevřít",style="Success.TButton",command=self.open_job).pack(side="right",padx=6)
        self.tree.bind("<Double-1>",lambda e:self.open_job())
    def _fields(self):
        cust=self.db.fetchall("SELECT id,name FROM customers ORDER BY name"); objs=self.db.fetchall("SELECT id,name FROM objects ORDER BY name")
        self.cm={f"{r['name']} [#{r['id']}]":r['id'] for r in cust}; self.om={f"{r['name']} [#{r['id']}]":r['id'] for r in objs}
        return [("job_no","Číslo zakázky"),("title","Název"),("customer","Zákazník","combo",[""]+list(self.cm)),("object","Objekt","combo",[""]+list(self.om)),("status","Stav","combo",["Nová","Naplánovaná","Rozpracovaná","Dokončená","Fakturovaná"]),("due_date","Termín (RRRR-MM-DD)"),("price","Cena"),("note","Poznámka","text")]
    def refresh(self):
        q=f"%{self.search_var.get().strip()}%" if hasattr(self,'search_var') else "%"
        rows=self.db.fetchall("""SELECT j.*,c.name customer_name,o.name object_name FROM jobs j LEFT JOIN customers c ON c.id=j.customer_id LEFT JOIN objects o ON o.id=j.object_id WHERE j.title LIKE ? OR j.job_no LIKE ? OR c.name LIKE ? ORDER BY j.id DESC""",(q,q,q))
        if hasattr(self,'tree'):
            for x in self.tree.get_children():self.tree.delete(x)
            for r in rows:self.tree.insert("","end",iid=str(r['id']),values=(r['job_no'],r['title'],r['customer_name'],r['object_name'],r['status'],display_date(r['due_date'])))
    def _vals(self,r):
        d=dict(r); d['customer']=next((k for k,v in self.cm.items() if v==r['customer_id']),""); d['object']=next((k for k,v in self.om.items() if v==r['object_id']),""); return d
    def add(self):
        f=self._fields(); d=FormDialog(self.app,"Nová zakázka",f); self.wait_window(d)
        if d.result and d.result['title']:
            cid=self.cm.get(d.result.pop('customer')); oid=self.om.get(d.result.pop('object')); price=float(d.result['price'].replace(',','.')) if d.result['price'] else None
            self.db.execute("INSERT INTO jobs(customer_id,object_id,job_no,title,status,due_date,price,note) VALUES(?,?,?,?,?,?,?,?)",(cid,oid,d.result['job_no'],d.result['title'],d.result['status'],d.result['due_date'],price,d.result['note'])); self.refresh(); self.app.refresh_all()
    def edit(self):
        i=self.selected_id();
        if not i:return
        f=self._fields(); r=self.db.fetchone("SELECT * FROM jobs WHERE id=?",(i,)); d=FormDialog(self.app,"Upravit zakázku",f,self._vals(r)); self.wait_window(d)
        if d.result:
            cid=self.cm.get(d.result.pop('customer')); oid=self.om.get(d.result.pop('object')); price=float(d.result['price'].replace(',','.')) if d.result['price'] else None
            self.db.execute("UPDATE jobs SET customer_id=?,object_id=?,job_no=?,title=?,status=?,due_date=?,price=?,note=? WHERE id=?",(cid,oid,d.result['job_no'],d.result['title'],d.result['status'],d.result['due_date'],price,d.result['note'],i)); self.refresh(); self.app.refresh_all()
    def open_job(self):
        i=self.selected_id()
        if not i:return
        JobDetailDialog(self.app,i)
    def delete(self):
        i=self.selected_id();
        if i and messagebox.askyesno("Smazat","Opravdu smazat zakázku?"):
            self.db.execute("DELETE FROM jobs WHERE id=?",(i,)); self.refresh(); self.app.refresh_all()


class InstrumentsPage(TablePage):
    columns=[("name","Přístroj",220),("manufacturer","Výrobce",150),("model","Model",170),("serial","Výrobní číslo",150),("cal","Kalibrační list",150),("due","Platnost do",110)]
    fields=[("name","Název přístroje"),("manufacturer","Výrobce"),("model","Model"),("serial_no","Výrobní číslo"),("calibration_no","Číslo kalibračního protokolu"),("calibration_date","Datum kalibrace (RRRR-MM-DD)"),("calibration_due","Platnost do (RRRR-MM-DD)"),("note","Poznámka","text")]
    def __init__(self,app): super().__init__(app,"Měřicí přístroje","Přístroje a hlídání kalibrace")
    def refresh(self):
        q=f"%{self.search_var.get().strip()}%" if hasattr(self,'search_var') else "%"; rows=self.db.fetchall("SELECT * FROM instruments WHERE name LIKE ? OR model LIKE ? OR serial_no LIKE ? ORDER BY name",(q,q,q))
        if hasattr(self,'tree'):
            for x in self.tree.get_children():self.tree.delete(x)
            for r in rows:self.tree.insert("","end",iid=str(r['id']),values=(r['name'],r['manufacturer'],r['model'],r['serial_no'],r['calibration_no'],display_date(r['calibration_due'])))
    def add(self):
        d=FormDialog(self.app,"Nový měřicí přístroj",self.fields); self.wait_window(d)
        if d.result and d.result['name']:
            self.db.execute("INSERT INTO instruments(name,manufacturer,model,serial_no,calibration_no,calibration_date,calibration_due,note) VALUES(?,?,?,?,?,?,?,?)",tuple(d.result[k] for k,*_ in self.fields)); self.refresh(); self.app.refresh_all()
    def edit(self):
        i=self.selected_id();
        if not i:return
        r=dict(self.db.fetchone("SELECT * FROM instruments WHERE id=?",(i,))); d=FormDialog(self.app,"Upravit přístroj",self.fields,r); self.wait_window(d)
        if d.result:
            self.db.execute("UPDATE instruments SET name=?,manufacturer=?,model=?,serial_no=?,calibration_no=?,calibration_date=?,calibration_due=?,note=? WHERE id=?",[d.result[k] for k,*_ in self.fields]+[i]); self.refresh(); self.app.refresh_all()
    def delete(self):
        i=self.selected_id();
        if i and messagebox.askyesno("Smazat","Opravdu smazat přístroj?"):
            try:self.db.execute("DELETE FROM instruments WHERE id=?",(i,));self.refresh();self.app.refresh_all()
            except Exception as e:messagebox.showerror("Chyba",str(e))


class StandardsPage(TablePage):
    columns=[("code","Předpis / norma",210),("title","Název",420),("area","Oblast",150),("status","Stav",170),("from","Od",100),("to","Do",100),("verified","Ověřeno",100)]
    fields=[("code","Označení"),("title","Název"),("area","Oblast"),("document_type","Typ","combo",["ČSN","TNI","Zákon","NV","Jiný"]),("status","Stav","combo",["Platná","Platný","Platná - souběžná","Zrušená - historická","Nahrazena","Neověřena"]),("valid_from","Platnost od"),("valid_to","Platnost do"),("replaced_by","Nahrazena / nahrazující dokument"),("verified_on","Stav ověřen dne"),("note","Poznámka","text")]
    def __init__(self,app):
        super().__init__(app,"Normy a předpisy","Registr platnosti, náhrad a historických norem")
        self.extended_var=tk.BooleanVar(value=False)
        ttk.Checkbutton(self.toolbar,text="Zobrazit historické a neověřené",variable=self.extended_var,command=self.refresh).pack(side="left",padx=10)
        self.refresh()
    def refresh(self):
        q=f"%{self.search_var.get().strip()}%" if hasattr(self,'search_var') else "%"
        extended=not hasattr(self,'extended_var') or self.extended_var.get()
        extra="" if extended else " AND COALESCE(is_selectable,1)=1"
        rows=self.db.fetchall("SELECT * FROM standards WHERE (code LIKE ? OR title LIKE ? OR area LIKE ?)"+extra+" ORDER BY code",(q,q,q))
        if hasattr(self,'tree'):
            for x in self.tree.get_children():self.tree.delete(x)
            for r in rows:self.tree.insert("","end",iid=str(r['id']),values=(r['code'],r['title'],r['area'],r['status'],display_date(r['valid_from']),display_date(r['valid_to']),display_date(r['verified_on'])))
    def add(self):
        d=FormDialog(self.app,"Nová norma / předpis",self.fields);self.wait_window(d)
        if d.result and d.result['code']:
            self.db.execute("INSERT INTO standards(code,title,area,document_type,status,valid_from,valid_to,replaced_by,verified_on,note) VALUES(?,?,?,?,?,?,?,?,?,?)",tuple(d.result[k] for k,*_ in self.fields));self.refresh()
    def edit(self):
        i=self.selected_id();
        if not i:return
        r=dict(self.db.fetchone("SELECT * FROM standards WHERE id=?",(i,)));d=FormDialog(self.app,"Upravit normu",self.fields,r);self.wait_window(d)
        if d.result:self.db.execute("UPDATE standards SET code=?,title=?,area=?,document_type=?,status=?,valid_from=?,valid_to=?,replaced_by=?,verified_on=?,note=? WHERE id=?",[d.result[k] for k,*_ in self.fields]+[i]);self.refresh()
    def delete(self):
        i=self.selected_id();
        if i and messagebox.askyesno("Smazat","Opravdu odstranit z registru?"):self.db.execute("DELETE FROM standards WHERE id=?",(i,));self.refresh()


class LearningPage(BasePage):
    """Editable local dictionaries learned from user-entered values."""
    def __init__(self, app):
        super().__init__(app, "Číselníky / učení", "Program si ukládá opakovaně používané položky a příště je nabízí přednostně. Vše lze ručně upravit.")
        tb=ttk.Frame(self.body); tb.pack(fill='x',pady=(0,8))
        ttk.Label(tb,text='Kategorie',style='Subtle.TLabel').pack(side='left',padx=(0,6))
        self.category_var=tk.StringVar(value=list(LEARNING_CATEGORIES.values())[0])
        self.category_combo=ttk.Combobox(tb,textvariable=self.category_var,values=list(LEARNING_CATEGORIES.values()),state='readonly',width=30)
        self.category_combo.pack(side='left'); self.category_combo.bind('<<ComboboxSelected>>',lambda e:self.refresh())
        self.search_var=tk.StringVar(); ttk.Entry(tb,textvariable=self.search_var,width=30).pack(side='left',padx=8);self.search_var.trace_add('write',lambda *a:self.refresh())
        ttk.Button(tb,text='Nová položka',style='Accent.TButton',command=self.add).pack(side='right')
        ttk.Button(tb,text='Upravit',command=self.edit).pack(side='right',padx=6)
        ttk.Button(tb,text='Deaktivovat',style='Danger.TButton',command=self.delete).pack(side='right')
        holder=tk.Frame(self.body,bg='white',highlightbackground=COLORS['line'],highlightthickness=1);holder.pack(fill='both',expand=True)
        cols=[('value','Položka',430),('uses','Použití',90),('last','Naposledy použito',160),('note','Poznámka',360)]
        self.tree=ttk.Treeview(holder,columns=[c[0] for c in cols],show='headings')
        for k,l,w in cols:self.tree.heading(k,text=l);self.tree.column(k,width=w,anchor='w')
        ys=ttk.Scrollbar(holder,orient='vertical',command=self.tree.yview);self.tree.configure(yscrollcommand=ys.set)
        self.tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
        self.tree.bind('<Double-1>',lambda e:self.edit());self.refresh()
    def category_key(self):
        label=self.category_var.get();return next((k for k,v in LEARNING_CATEGORIES.items() if v==label),'network_system')
    def selected_id(self):
        s=self.tree.selection();return int(s[0]) if s else None
    def refresh(self):
        if not hasattr(self,'tree'):return
        q=f"%{self.search_var.get().strip()}%"
        rows=self.db.fetchall("SELECT * FROM learned_values WHERE category=? AND active=1 AND value LIKE ? ORDER BY usage_count DESC, COALESCE(last_used,'') DESC, value COLLATE NOCASE",(self.category_key(),q))
        for x in self.tree.get_children():self.tree.delete(x)
        for r in rows:self.tree.insert('','end',iid=str(r['id']),values=(r['value'],r['usage_count'],r['last_used'] or '',r['note'] or ''))
    def add(self):
        fields=[('value','Položka'),('note','Poznámka','text')]
        d=FormDialog(self.app,'Nová naučená položka',fields,width=650,height=430);self.wait_window(d)
        if d.result and d.result['value'].strip():
            try:self.db.execute("INSERT INTO learned_values(category,value,note,usage_count,active) VALUES(?,?,?,0,1)",(self.category_key(),d.result['value'].strip(),d.result['note'].strip()));self.refresh()
            except Exception as e:messagebox.showerror('Číselník',str(e))
    def edit(self):
        i=self.selected_id();
        if not i:return
        r=dict(self.db.fetchone('SELECT * FROM learned_values WHERE id=?',(i,)))
        d=FormDialog(self.app,'Upravit naučenou položku',[('value','Položka'),('note','Poznámka','text')],r,width=650,height=430);self.wait_window(d)
        if d.result and d.result['value'].strip():
            try:self.db.execute('UPDATE learned_values SET value=?,note=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(d.result['value'].strip(),d.result['note'].strip(),i));self.refresh()
            except Exception as e:messagebox.showerror('Číselník',str(e))
    def delete(self):
        i=self.selected_id()
        if i and messagebox.askyesno('Deaktivovat','Položka zůstane v historii, ale přestane se nabízet. Pokračovat?'):
            self.db.execute('UPDATE learned_values SET active=0,updated_at=CURRENT_TIMESTAMP WHERE id=?',(i,));self.refresh()


class DefectsPage(TablePage):
    columns=[("category","Kategorie",180),("standard","Norma",220),("article","Článek",140),("title","Závada",260),("severity","Závažnost",110),("valid","Stav",130)]
    fields=[("category","Kategorie"),("standard","Hlavní norma"),("standard_name","Název hlavní normy"),("article","Hlavní článek"),("title","Krátký název"),("defect_text","Text závady do revize","text"),("requirement_text","Hlavní citace / normový podklad","text"),("severity","Závažnost","combo",["","C1","C2","C3"]),("valid_status","Platnost","combo",["Platná","Neověřena","Historická","Šablona","Nahrazena"]),("valid_from","Platnost od"),("valid_to","Platnost do"),("replaced_by","Nahrazena"),("note","Poznámka","text")]
    def __init__(self,app):
        super().__init__(app,"Závadovník","Plně editovatelná databáze závad • import/export Excel")
        # Extra Excel actions
        top=self.body.winfo_children()[0]
        ttk.Button(top,text="Import Excel",command=self.import_excel).pack(side="left",padx=(8,0))
        ttk.Button(top,text="Export Excel",command=self.export_excel).pack(side="left",padx=5)
        ttk.Button(top,text="Šablona XLSX",command=self.template_excel).pack(side="left")
        ttk.Button(top,text="Normové odkazy",command=self.edit_norm_refs).pack(side="left",padx=5)
    def refresh(self):
        q=f"%{self.search_var.get().strip()}%" if hasattr(self,'search_var') else "%"; rows=self.db.fetchall("SELECT * FROM defect_catalog WHERE active=1 AND (category LIKE ? OR standard LIKE ? OR article LIKE ? OR title LIKE ? OR defect_text LIKE ? OR COALESCE(norm_refs_json,'') LIKE ?) ORDER BY standard,article,id",(q,q,q,q,q,q))
        if hasattr(self,'tree'):
            for x in self.tree.get_children():self.tree.delete(x)
            for r in rows:self.tree.insert("","end",iid=str(r['id']),values=(r['category'],r['standard'],r['article'],r['title'] or r['defect_text'][:55],r['severity'],r['valid_status']))
    def add(self):
        d=FormDialog(self.app,"Nová závada",self.fields,width=760,height=780);self.wait_window(d)
        if d.result and d.result['defect_text']:
            new_id=self.db.execute("INSERT INTO defect_catalog(category,standard,standard_name,article,title,defect_text,requirement_text,severity,valid_status,valid_from,valid_to,replaced_by,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",tuple(d.result[k] for k,*_ in self.fields))
            refs=[{'standard':d.result.get('standard','').strip(),'article':d.result.get('article','').strip(),'citation':d.result.get('requirement_text','').strip()}] if any((d.result.get(k) or '').strip() for k in ('standard','article','requirement_text')) else []
            self.db.execute("UPDATE defect_catalog SET defect_class=?,norm_refs_json=? WHERE id=?",(d.result.get('severity',''),json.dumps(refs,ensure_ascii=False),new_id));self.refresh()
    def edit(self):
        i=self.selected_id();
        if not i:return
        r=dict(self.db.fetchone("SELECT * FROM defect_catalog WHERE id=?",(i,)));d=FormDialog(self.app,"Upravit závadu",self.fields,r,width=760,height=780);self.wait_window(d)
        if d.result:
            refs=_defect_norm_refs(r);primary={'standard':d.result.get('standard','').strip(),'article':d.result.get('article','').strip(),'citation':d.result.get('requirement_text','').strip()}
            if any(primary.values()):
                if refs:refs[0]=primary
                else:refs=[primary]
            elif refs:refs=refs[1:]
            self.db.execute("UPDATE defect_catalog SET category=?,standard=?,standard_name=?,article=?,title=?,defect_text=?,requirement_text=?,severity=?,valid_status=?,valid_from=?,valid_to=?,replaced_by=?,note=?,defect_class=?,norm_refs_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",[d.result[k] for k,*_ in self.fields]+[d.result.get('severity',''),json.dumps(refs,ensure_ascii=False),i]);self.refresh()
    def edit_norm_refs(self):
        i=self.selected_id()
        if not i:
            messagebox.showinfo('Normové odkazy','Nejprve vyber závadu v závadovníku.');return
        r=dict(self.db.fetchone("SELECT * FROM defect_catalog WHERE id=?",(i,)))
        d=NormReferencesDialog(self.app,_defect_norm_refs(r),'Normové odkazy závady v závadovníku');self.wait_window(d)
        if d.result is not None:
            refs=[dict(x) for x in d.result];first=refs[0] if refs else {}
            self.db.execute("UPDATE defect_catalog SET norm_refs_json=?,standard=?,article=?,requirement_text=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(json.dumps(refs,ensure_ascii=False),first.get('standard',''),first.get('article',''),first.get('citation',''),i));self.refresh()
    def delete(self):
        i=self.selected_id();
        if i and messagebox.askyesno("Deaktivovat","Závadu raději deaktivujeme, aby zůstala zachována historie. Pokračovat?"):
            self.db.execute("UPDATE defect_catalog SET active=0 WHERE id=?",(i,));self.refresh()
    def import_excel(self):
        path=filedialog.askopenfilename(title="Import závadovníku",filetypes=[("Excel","*.xlsx")])
        if not path:return
        try:
            headers=inspect_headers(path); mapping=auto_mapping(headers)
            if not mapping:
                messagebox.showerror("Import","Hlavičky nebyly rozpoznány. Použij šablonu PZ-REVIZE nebo soubor se sloupci NORMA, ZÁVADY, ČLÁNEK, POPIS...");return
            mode="skip"
            if messagebox.askyesno("Duplicity","Mají se existující shodné závady aktualizovat?\nAno = aktualizovat, Ne = přeskočit"):
                mode="update"
            res=import_defects(path,self.db,mapping,mode)
            self.refresh();messagebox.showinfo("Import dokončen",f"Importováno: {res['imported']}\nAktualizováno: {res['updated']}\nPřeskočeno: {res['skipped']}\nChyby: {res['errors']}")
        except Exception as e:messagebox.showerror("Import selhal",str(e))
    def export_excel(self):
        path=filedialog.asksaveasfilename(title="Export závadovníku",defaultextension=".xlsx",filetypes=[("Excel","*.xlsx")],initialfile="PZ-REVIZE_zavadovnik.xlsx")
        if path:
            try:export_defects(path,self.db);messagebox.showinfo("Export","Závadovník byl exportován.")
            except Exception as e:messagebox.showerror("Export selhal",str(e))
    def template_excel(self):
        path=filedialog.asksaveasfilename(title="Uložit šablonu",defaultextension=".xlsx",filetypes=[("Excel","*.xlsx")],initialfile="PZ-REVIZE_sablona_zavadovniku.xlsx")
        if path:create_template(path);messagebox.showinfo("Šablona","Šablona byla vytvořena.")


class RTProfilePage(BasePage):
    def __init__(self,app):
        super().__init__(app,"Revizní technik","Údaje RT, razítko a podpis. Základní PZ logo je ve zprávě použito automaticky.")
        card=tk.Frame(self.body,bg="white",highlightbackground=COLORS['line'],highlightthickness=1);card.pack(fill="both",expand=True)
        self.vars={}; fields=[("name","Jméno a příjmení"),("business_name","Firma / obchodní jméno"),("address","Ulice a č.p."),("city","Město"),("zip","PSČ"),("ico","IČO"),("dic","DIČ"),("phone","Telefon"),("email","E-mail"),("certificate_no","Ev. číslo osvědčení RT"),("certificate_scope","Rozsah osvědčení"),("certificate_valid_to","Platnost osvědčení do"),("authorization_no","Ev. číslo oprávnění"),("authorization_scope","Rozsah oprávnění")]
        form=tk.Frame(card,bg="white");form.pack(side="left",fill="both",expand=True,padx=22,pady=22);form.columnconfigure(1,weight=1)
        for row,(key,label) in enumerate(fields):
            tk.Label(form,text=label,bg="white",fg=COLORS['muted'],font=("Segoe UI",9)).grid(row=row,column=0,sticky="w",padx=(0,12),pady=6)
            v=tk.StringVar();ttk.Entry(form,textvariable=v).grid(row=row,column=1,sticky="ew",pady=6);self.vars[key]=v
        ttk.Button(form,text="Uložit údaje RT",style="Success.TButton",command=self.save).grid(row=len(fields),column=1,sticky="e",pady=(14,0))
        assets=tk.Frame(card,bg="#FAFAFA",width=380);assets.pack(side="right",fill="y",padx=0,pady=0);assets.pack_propagate(False)
        tk.Label(assets,text="Grafické prvky",bg="#FAFAFA",fg=COLORS['text'],font=("Segoe UI Semibold",12)).pack(anchor="w",padx=20,pady=(22,10))
        tk.Label(assets,text="Logo zprávy: základní PZ logo (pevné, bez symbolu měřicího přístroje)",bg="#FAFAFA",fg=COLORS['muted'],font=("Segoe UI",8),wraplength=330,justify='left').pack(anchor='w',padx=20,pady=(0,8))
        self.asset_labels={}
        for key,label in [("stamp_path","Razítko"),("signature_path","Podpis")]:
            box=tk.Frame(assets,bg="white",highlightbackground=COLORS['line'],highlightthickness=1);box.pack(fill="x",padx=20,pady=6)
            tk.Label(box,text=label,bg="white",font=("Segoe UI Semibold",9)).pack(anchor="w",padx=10,pady=(9,2))
            lab=tk.Label(box,text="nenastaveno",bg="white",fg=COLORS['muted'],font=("Segoe UI",8),wraplength=300,justify="left");lab.pack(anchor="w",padx=10,pady=(0,6));self.asset_labels[key]=lab
            ttk.Button(box,text="Vybrat soubor",command=lambda k=key:self.choose_asset(k)).pack(anchor="e",padx=10,pady=(0,9))
        self.load()
    def load(self):
        r=self.db.fetchone("SELECT * FROM rt_profile WHERE id=1")
        if not r:return
        for k,v in self.vars.items():v.set(r[k] or "")
        for k,l in self.asset_labels.items():l.config(text=r[k] or "nenastaveno")
    def save(self):
        vals=[v.get().strip() for v in self.vars.values()]
        self.db.execute("UPDATE rt_profile SET name=?,business_name=?,address=?,city=?,zip=?,ico=?,dic=?,phone=?,email=?,certificate_no=?,certificate_scope=?,certificate_valid_to=?,authorization_no=?,authorization_scope=? WHERE id=1",vals);messagebox.showinfo("Uloženo","Údaje revizního technika byly uloženy.")
    def choose_asset(self,key):
        p=filedialog.askopenfilename(title="Vybrat obrázek",filetypes=[("Obrázek","*.png *.jpg *.jpeg *.webp")])
        if not p:return
        try:
            stored=self.db.copy_attachment(p); self.db.execute(f"UPDATE rt_profile SET {key}=? WHERE id=1",(stored,));self.load()
        except Exception as e:messagebox.showerror("Chyba",str(e))


# ---------- REVISION EDITOR ----------
MEASUREMENT_SCHEMAS = {
    "ELEKTRO": [
        ("designation","Obvod"),("name","Název"),("board","Rozvaděč"),("breaker","Jištění"),("cable","Kabel"),
        ("riso","Riso – souhrn"),("zs","Zs [Ω]"),("rcd","RCD – souhrn [ms]"),("pe_continuity","PE [Ω]"),
        ("zs_limit","Mez Zs [Ω]"),("ik","Ik [A]"),("impedance_result","Impedance – výsledek"),
        ("insulation_voltage","Zkušební napětí [V]"),("riso_l_pe","Riso L-PE [MΩ]"),("riso_n_pe","Riso N-PE [MΩ]"),("riso_l_n","Riso L-N [MΩ]"),("insulation_result","Izolace – výsledek"),
        ("rcd_designation","RCD označení"),("rcd_type","RCD typ"),("rcd_in_a","RCD In [A]"),("rcd_idn_ma","RCD IΔn [mA]"),
        ("rcd_time_05x_ms","RCD 0,5x [ms]"),("rcd_time_1x_pos_ms","RCD 1x+ [ms]"),("rcd_time_1x_neg_ms","RCD 1x- [ms]"),("rcd_time_5x_ms","RCD 5x [ms]"),
        ("rcd_trip_ma","RCD vyb. proud [mA]"),("rcd_touch_v","RCD Uc [V]"),("rcd_test_button","RCD TEST"),("rcd_result","RCD – výsledek"),("pe_result","PE – výsledek"),
        ("result","Výsledek"),("note","Poznámka")
    ],
    "LPS": [
        ("designation","Označení svodu / bodu"),("item_type","Typ"),("continuity","Spojitost [Ω]"),("earth_resistance","Zemní odpor [Ω]"),("result","Výsledek","combo",["","Vyhovuje","Nevyhovuje","Nehodnoceno"]),("note","Poznámka","text")
    ],
    "STROJ": [
        ("designation","Označení"),("measurement_type","Měření / zkouška"),("value","Hodnota"),("unit","Jednotka"),("limit_value","Limit / kritérium"),("result","Výsledek","combo",["","Vyhovuje","Nevyhovuje","Nehodnoceno"]),("note","Poznámka","text")
    ],
    "VNEJSI": [
        ("code","Kód vlivu"),("value_code","Stupeň / hodnota"),("description","Popis"),("measure","Požadované opatření","text"),("result","Výsledek","combo",["","Určeno","Nevztahuje se","K doplnění"]),("note","Poznámka","text")
    ]
}

MEASUREMENT_TREE = {
    "ELEKTRO": [("designation","Obvod",90),("name","Název",150),("breaker","Jištění",115),("cable","Kabel",130),("zs","Zs [Ω]",80),("impedance_result","Zs stav",85),("riso","Riso [MΩ]",90),("insulation_result","Izolace",85),("rcd","RCD 1x [ms]",95),("rcd_result","RCD stav",85),("pe_continuity","PE [Ω]",80),("result","Celkem",100)],
    "LPS": [("designation","Označení",120),("item_type","Typ",170),("continuity","Spojitost",110),("earth_resistance","Zemní odpor",120),("result","Výsledek",110),("note","Poznámka",220)],
    "STROJ": [("designation","Označení",120),("measurement_type","Zkouška",240),("value","Hodnota",100),("unit","Jednotka",90),("limit_value","Limit",120),("result","Výsledek",110)],
    "VNEJSI": [("code","Kód",90),("value_code","Stupeň",100),("description","Popis",300),("measure","Opatření",300),("result","Výsledek",120)],
}

VARISTOR_FIELDS = [
    ("designation","Označení SPD / varistoru"),
    ("board","Rozvaděč / umístění"),
    ("spd_type","Typ SPD / varistoru"),
    ("manufacturer","Výrobce / typové označení"),
    ("uc_v","Uc - max. trvalé pracovní napětí [V]"),
    ("up_kv","Up - napěťová ochranná úroveň [kV]"),
    ("test_current_ma","Zkušební proud [mA]"),
    ("uvar_pos_v","Naměřené Uvar + [V]"),
    ("uvar_neg_v","Naměřené Uvar - [V]"),
    ("status_indicator","Signalizace / stav SPD","combo",["","V pořádku","Vybaveno / porucha","Bez indikace","Nezkoušeno"]),
    ("result","Vyhodnocení","combo",["","Vyhovuje","Nevyhovuje","Nehodnoceno"]),
    ("note","Poznámka","text")
]

VARISTOR_TREE = [
    ("designation","Označení",120),("board","Umístění",150),("spd_type","Typ",130),("manufacturer","Výrobce / model",180),
    ("uc_v","Uc [V]",80),("up_kv","Up [kV]",80),("uvar_pos_v","Uvar + [V]",95),("uvar_neg_v","Uvar - [V]",95),
    ("status_indicator","Stav SPD",120),("result","Výsledek",110)
]

SPECIAL_FIELDS = {
    "ELEKTRO": [("main_board","Hlavní rozvaděč"),("meter_board","Elektroměrový rozvaděč"),("earthing","Uzemnění / MET","text"),("spd","SPD / přepěťová ochrana","text"),("special_locations","Zvláštní prostory (koupelna, bazén, sauna...)","text")],
    "LPS": [("lps_class","Třída LPS","combo",["","I","II","III","IV"]),("risk_analysis","Analýza rizika"),("air_termination","Jímací soustava","text"),("down_conductor_count","Počet svodů"),("down_conductors","Svody","text"),("earth_electrode","Zemnič","text"),("spd","Vnitřní ochrana / SPD","text"),("weather","Počasí při měření"),("soil","Druh / stav půdy")],
    "STROJ": [("machine_subtype","Druh zařízení","combo",["","Obecné strojní zařízení","Zdvihací zařízení","Vrata / poháněné dveře","Dopravník","Obráběcí stroj","Jiné"]),("manufacturer","Výrobce"),("machine_type","Typ stroje"),("serial","Výrobní číslo"),("inventory_no","Inventární číslo"),("year","Rok výroby"),("ce_mark","Označení CE","combo",["","Ano","Ne","Neuvedeno"]),("supply_voltage","Napájecí napětí / síť"),("power","Příkon / výkon Pn"),("rated_current","Jmenovitý proud In"),("control_voltage","Napětí řídicích obvodů"),("main_switch","Hlavní vypínač"),("emergency_stop","Nouzové zastavení"),("operating_state","Stav zařízení při revizi","combo",["","V běžném provozním stavu","Odstaveno z provozu","Mimo provoz z důvodu opravy","Jiný stav"]),("changes_since_previous","Změny od předchozí revize","text"),("supply_description","Popis / způsob napojení","text"),("pe_bonding","Ochranné pospojování","text")],
    "VNEJSI": [
        ("revision_seq","Revize č. (pro zápatí protokolu)"),
        ("owner","Majitel"),
        ("operator","Provozovatel"),
        ("chairperson","Předseda komise"),
        ("protocol_title_text","Text pod názvem protokolu","text"),
        ("committee_members","Členové komise – každý na samostatný řádek","text"),
        ("general_text","Obecné – popis celé budovy","text"),
        ("building_description","Popis posuzovaného objektu","text"),
        ("protocol_basis","Podklady pro určení","text"),
        ("premises","Rozsah prostor","text"),
        ("notes","Doplňující údaje","text"),
    ],
}


class RevisionEditor(Modal):
    def __init__(self, app, revision_type: str, revision_id: int | None = None, initial_job_id: int | None = None):
        self.app=app; self.db=app.db; self.revision_type=revision_type; self.revision_id=revision_id; self.initial_job_id=initial_job_id
        labels={"ELEKTRO":"Elektrická instalace","LPS":"LPS / ochrana před bleskem","STROJ":"Strojní zařízení","VNEJSI":"Vnější vlivy"}
        super().__init__(app, f"{labels.get(revision_type,revision_type)} - {'upravit' if revision_id else 'nová'}", 1500, 920)
        app._revision_editor_epoch = getattr(app, '_revision_editor_epoch', 0) + 1
        app._active_revision_editors = getattr(app, '_active_revision_editors', 0) + 1
        def mark_closed(event):
            if event.widget is self:
                app._active_revision_editors = max(0, app._active_revision_editors - 1)
        self.bind('<Destroy>', mark_closed, add='+')
        self.minsize(1200,760)
        self.after(30, self._maximize_editor)
        self.vars={}; self.texts={}; self.special_vars={}; self.measurements=[]; self.varistor_measurements=[]; self.rev_defects=[]; self.instrument_ids=set(); self.attachments=[]; self.documents=[]; self.rev_standards=[]; self.networks=[]; self.supplies=[]; self.conclusion_blocks=[]; self.protection_measures=[]; self.inspection_items=[]; self.working_photos=[]
        self._load_source()
        self._build()
        self._populate()
        if not self.revision_id and self.revision_type=='ELEKTRO':
            self.add_electrical_inspection_template(quiet=True)
        if self.revision_type=='VNEJSI':self._ensure_external_standards()
        self._saved_state=self._state_snapshot()
        self.protocol('WM_DELETE_WINDOW',self._on_close_request)
        self.bind('<Escape>',lambda e:self._on_close_request())
        if self.revision_type=='VNEJSI':
            self.bind('<Control-d>',lambda e:(self.external_duplicate_room(),'break')[1])
            self.bind('<Control-D>',lambda e:(self.external_duplicate_room(),'break')[1])

    def _maximize_editor(self):
        """Open the main revision workspace maximized; F11 switches true fullscreen."""
        try:
            if os.name == "nt":
                self.state("zoomed")
            else:
                self.attributes("-zoomed", True)
        except Exception:
            try:
                sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
                self.geometry(f"{max(1200,sw-50)}x{max(760,sh-80)}+10+10")
            except Exception:
                pass
        self._fs = False
        self.bind("<F11>", self._toggle_editor_fullscreen)

    def _toggle_editor_fullscreen(self, event=None):
        self._fs = not getattr(self, "_fs", False)
        try:
            self.attributes("-fullscreen", self._fs)
        except Exception:
            pass
        return "break"

    def _load_source(self):
        self.rev = dict(self.db.fetchone("SELECT * FROM revisions WHERE id=?",(self.revision_id,))) if self.revision_id else {}
        if not self.revision_id and self.initial_job_id:
            j=self.db.fetchone("SELECT * FROM jobs WHERE id=?",(self.initial_job_id,))
            if j:self.rev={"job_id":j["id"],"customer_id":j["customer_id"],"object_id":j["object_id"]}
        if self.revision_id:
            if self.revision_type=='ELEKTRO':self._recalculate_electrical_results()
            table={"ELEKTRO":"circuits","LPS":"lps_measurements","STROJ":"machine_measurements","VNEJSI":"external_influences"}[self.revision_type]
            order_sql="COALESCE(sort_order,id),id" if self.revision_type in ('ELEKTRO','STROJ','VNEJSI') else "id"
            self.measurements=[dict(r) for r in self.db.fetchall(f"SELECT * FROM {table} WHERE revision_id=? ORDER BY {order_sql}",(self.revision_id,))]
            if self.revision_type=='VNEJSI':
                self.measurements=external_merge_legacy_rows(self.measurements)
            if self.revision_type=="ELEKTRO":
                self.varistor_measurements=[dict(r) for r in self.db.fetchall("SELECT * FROM varistor_measurements WHERE revision_id=? ORDER BY id",(self.revision_id,))]
            self.rev_defects=[dict(r) for r in self.db.fetchall("SELECT * FROM revision_defects WHERE revision_id=? ORDER BY id",(self.revision_id,))]
            self.instrument_ids={r[0] for r in self.db.fetchall("SELECT instrument_id FROM revision_instruments WHERE revision_id=?",(self.revision_id,))}
            self.attachments=[dict(r) for r in self.db.fetchall("SELECT * FROM revision_attachments WHERE revision_id=? ORDER BY id",(self.revision_id,))]
            self.documents=[dict(r) for r in self.db.fetchall("SELECT * FROM revision_documents WHERE revision_id=? ORDER BY sort_order,id",(self.revision_id,))]
            self.rev_standards=[dict(r) for r in self.db.fetchall("SELECT * FROM revision_standards WHERE revision_id=? ORDER BY sort_order,id",(self.revision_id,))]
            self.networks=[dict(r) for r in self.db.fetchall("SELECT * FROM revision_networks WHERE revision_id=? ORDER BY sort_order,id",(self.revision_id,))]
            self.supplies=[dict(r) for r in self.db.fetchall("SELECT * FROM revision_supplies WHERE revision_id=? ORDER BY sort_order,id",(self.revision_id,))]
            self.conclusion_blocks=[dict(r) for r in self.db.fetchall("SELECT * FROM revision_conclusion_blocks WHERE revision_id=? ORDER BY sort_order,id",(self.revision_id,))]
            self.protection_measures=[dict(r) for r in self.db.fetchall("SELECT * FROM revision_protection_measures WHERE revision_id=? ORDER BY sort_order,id",(self.revision_id,))]
            self.inspection_items=[dict(r) for r in self.db.fetchall("SELECT * FROM revision_inspection_items WHERE revision_id=? ORDER BY sort_order,id",(self.revision_id,))]
            self.working_photos=[dict(r) for r in self.db.fetchall("SELECT * FROM revision_photos WHERE revision_id=? AND kind='working' ORDER BY sort_order,id",(self.revision_id,))]
            # attach saved defect photos to in-memory defect records
            for d in self.rev_defects:
                d['_photos']=[dict(x) for x in self.db.fetchall("SELECT * FROM revision_photos WHERE defect_id=? AND kind='defect' ORDER BY sort_order,id",(d.get('id'),))]
            if not self.documents and (self.rev.get('documentation') or '').strip():
                self.documents=[{'doc_type':'Původní text dokumentace','doc_no':'','doc_date':'','author':'','note':self.rev.get('documentation') or '','stored_path':'','sort_order':0}]
            if not self.networks and (self.rev.get('network') or '').strip():
                self.networks=[{'system_name':self.rev.get('network') or '','voltage':'','scope_text':'','note':'','sort_order':0}]
            if not self.supplies and (self.rev.get('supply') or '').strip():
                self.supplies=[{'supply_type':self.rev.get('supply') or '','designation':'','voltage':'','backup':'','note':'','sort_order':0}]
            # 0.4.3: staré samostatné řádky sítí zachováme jako samostatné položky
            # v nové jednotné tabulce. Nepárujeme je se zdroji podle pořadí, protože
            # taková vazba nebyla ve starších datech garantována.
            if self.networks:
                for n in self.networks:
                    marking=' '.join(x for x in [n.get('system_name',''),n.get('voltage','')] if x).strip()
                    self.supplies.append({
                        'supply_type':'Původní záznam sítě / soustavy',
                        'designation':'',
                        'voltage':marking,
                        'backup':n.get('scope_text',''),
                        'note':n.get('note',''),
                        'sort_order':len(self.supplies),
                    })
                self.networks=[]
        self.special=json.loads(self.rev.get('special_json') or '{}') if self.rev else {}

    def _build(self):
        top=tk.Frame(self,bg=COLORS['sidebar']);top.pack(fill="x")
        tk.Label(top,text=f"PZ-REVIZE  •  {'VNĚJŠÍ VLIVY' if self.revision_type=='VNEJSI' else self.revision_type}",bg=COLORS['sidebar'],fg="white",font=("Segoe UI Semibold",13)).pack(side="left",padx=16,pady=11)
        tk.Label(top,text=self.rev.get('revision_no') or "nová revize",bg=COLORS['sidebar'],fg="#C9CDD3",font=("Segoe UI",9)).pack(side="left",padx=4)
        ttk.Button(top,text="Kontrola",command=self.validate_revision).pack(side="right",padx=4,pady=6)
        ttk.Button(top,text="Uložit",style="Success.TButton",command=self.save).pack(side="right",padx=4,pady=6)
        ttk.Button(top,text="Tisk",command=self.print_from_editor).pack(side="right",padx=4,pady=6)
        ttk.Button(top,text="Export PDF",command=self.export_from_editor).pack(side="right",padx=4,pady=6)
        ttk.Button(top,text="Náhled",style="Accent.TButton",command=self.preview_from_editor).pack(side="right",padx=4,pady=6)
        nb=ttk.Notebook(self);nb.pack(fill="both",expand=True,padx=12,pady=12);self.nb=nb
        self.tab_basic=ttk.Frame(nb);self.tab_power=ttk.Frame(nb);self.tab_protection=ttk.Frame(nb);self.tab_special=ttk.Frame(nb);self.tab_docs=ttk.Frame(nb);self.tab_norms=ttk.Frame(nb);self.tab_description=ttk.Frame(nb);self.tab_refs=ttk.Frame(nb);self.tab_inspection=ttk.Frame(nb);self.tab_meas=ttk.Frame(nb);self.tab_defects=ttk.Frame(nb);self.tab_photos=ttk.Frame(nb);self.tab_instr=ttk.Frame(nb);self.tab_operator=ttk.Frame(nb);self.tab_conclusion=ttk.Frame(nb)
        if self.revision_type=="VNEJSI":
            # Protokol o určení VV není revizní zpráva. Zobrazujeme pouze kroky,
            # které jsou pro zpracování protokolu skutečně potřeba.
            nb.add(self.tab_basic,text="Základní údaje")
            nb.add(self.tab_special,text="Obecné")
            nb.add(self.tab_norms,text="Normy / předpisy")
            nb.add(self.tab_description,text="Popis")
            nb.add(self.tab_refs,text="Podklady / přílohy")
            nb.add(self.tab_meas,text="Vnější vlivy")
        else:
            nb.add(self.tab_basic,text="Základní údaje");nb.add(self.tab_power,text="Sítě / napájení");nb.add(self.tab_protection,text="Ochrany");nb.add(self.tab_special,text="Technické údaje");nb.add(self.tab_docs,text="Dokumentace");nb.add(self.tab_norms,text="Normy / předpisy");nb.add(self.tab_refs,text="Podklady / přílohy");nb.add(self.tab_inspection,text="Prohlídka / kontrola");nb.add(self.tab_meas,text="Měření / určení");nb.add(self.tab_defects,text="Závady");nb.add(self.tab_photos,text="Pracovní fotografie");nb.add(self.tab_instr,text="Přístroje");nb.add(self.tab_operator,text="Poučení");nb.add(self.tab_conclusion,text="Závěr")
        # Skryté části se u VV stále sestaví kvůli kompatibilitě starších dat,
        # ale uživateli se nenabízejí jako kroky protokolu.
        self._build_basic();self._build_power();self._build_protection();self._build_special();self._build_external_description();self._build_documentation();self._build_standards();self._build_references();self._build_inspection();self._build_measurements();self._build_defects();self._build_working_photos();self._build_instruments();self._build_operator();self._build_conclusion()

    def _combo_data(self):
        customers=self.db.fetchall("SELECT id,name FROM customers ORDER BY name")
        self.customer_map={f"{r['name']} [#{r['id']}]":r['id'] for r in customers}

    def _build_basic(self):
        if self.revision_type=='VNEJSI':
            return self._build_basic_external()
        self._combo_data(); f=self.tab_basic
        sf=ScrollFrame(f);sf.pack(fill='both',expand=True,padx=4,pady=4);g=sf.inner;g.columnconfigure(1,weight=1);g.columnconfigure(3,weight=1)
        fields=[
            ('revision_no','Číslo revizní zprávy','entry',None),('revision_kind','Druh revize','combo',['Výchozí','Pravidelná','Mimořádná']),
            ('customer','Zákazník / objednatel','combo',['']+list(self.customer_map)),('status','Stav','combo',['Rozpracovaná','Ke kontrole','Uzavřená']),
            ('started_on','Zahájení','entry',None),('finished_on','Ukončení','entry',None),('issued_on','Vyhotovení','entry',None),('next_revision_on','Příští revize','entry',None),
            ('vtz_class','Třída VTZ dle NV 190/2022 Sb. § 4','combo',['','I','II']),('result','Celkový výsledek','combo',['Nehodnoceno','Vyhovuje','Nevyhovuje','Vyhovuje s výhradami']),
            ('distribution_text','Rozdělovník','entry',None),('received_on','Převzal objednavatel dne','entry',None),
        ]
        for idx,(key,label,kind,opts) in enumerate(fields):
            rr=idx//2;cc=(idx%2)*2;ttk.Label(g,text=label,style='Subtle.TLabel').grid(row=rr,column=cc,sticky='w',padx=(10,8),pady=6)
            v=tk.StringVar(value=self._basic_initial(key));self.vars[key]=v
            w=ttk.Combobox(g,textvariable=v,values=opts,state='readonly') if kind=='combo' else ttk.Entry(g,textvariable=v);w.grid(row=rr,column=cc+1,sticky='ew',padx=(0,10),pady=5)
        rr=(len(fields)+1)//2
        # Per-revision deadline monitoring. The date can remain in the report even when monitoring is disabled.
        watchbox=ttk.Frame(g);watchbox.grid(row=rr,column=0,columnspan=4,sticky='ew',padx=10,pady=(2,5))
        initial_watch=True if not self.rev else bool(int(self.rev.get('deadline_watch') if self.rev.get('deadline_watch') is not None else 1))
        self.deadline_watch_var=tk.BooleanVar(value=initial_watch)
        ttk.Checkbutton(watchbox,text='Hlídat termín příští revize',variable=self.deadline_watch_var).pack(side='left')
        ttk.Label(watchbox,text='Vypnutí pouze vyřadí tuto revizi z hlídání termínů; datum ve zprávě zůstane zachováno.',style='Subtle.TLabel').pack(side='left',padx=12)
        rr+=1
        # customer actions
        actions=ttk.Frame(g);actions.grid(row=rr,column=0,columnspan=4,sticky='ew',padx=10,pady=(3,8))
        ttk.Button(actions,text='Nový zákazník / ARES',command=self.create_customer_from_editor).pack(side='left')
        ttk.Button(actions,text='Obnovit seznam zákazníků',command=self.refresh_customer_combo).pack(side='left',padx=5)
        ttk.Button(actions,text='Převzít adresu zákazníka do objektu',command=self.copy_customer_address_to_object).pack(side='right')
        rr+=1
        sep=tk.Label(g,text='REVIDOVANÝ OBJEKT',bg='#E2E2E2',fg=COLORS['text'],font=('Segoe UI Semibold',9),anchor='w',padx=8);sep.grid(row=rr,column=0,columnspan=4,sticky='ew',padx=10,pady=(2,6));rr+=1
        obj_fields=[('object_name_text','Název objektu'),('object_parcel_text','Parcela / katastr'),('object_address_text','Adresa objektu'),('object_city_text','Obec / město'),('object_zip_text','PSČ'),('object_location_note','Upřesnění místa / část objektu')]
        for idx,(key,label) in enumerate(obj_fields):
            r=rr+idx//2;cc=(idx%2)*2;ttk.Label(g,text=label,style='Subtle.TLabel').grid(row=r,column=cc,sticky='w',padx=(10,8),pady=6);v=tk.StringVar(value=self.rev.get(key) or '');self.vars[key]=v;ttk.Entry(g,textvariable=v).grid(row=r,column=cc+1,sticky='ew',padx=(0,10),pady=5)
        rr += (len(obj_fields)+1)//2
        ttk.Label(g,text='Předmět revize',style='Subtle.TLabel').grid(row=rr,column=0,sticky='nw',padx=(10,8),pady=7)
        t=tk.Text(g,height=5,font=('Segoe UI',9),wrap='word');t.grid(row=rr,column=1,columnspan=3,sticky='ew',padx=(0,10),pady=5);self.texts['subject']=t;rr+=1
        ttk.Label(g,text='Revize byla provedena dle:',style='Subtle.TLabel').grid(row=rr,column=0,sticky='nw',padx=(10,8),pady=7)
        normbox=tk.Frame(g,bg='white',highlightbackground=COLORS['line'],highlightthickness=1);normbox.grid(row=rr,column=1,columnspan=3,sticky='ew',padx=(0,10),pady=5)
        self.norm_summary_var=tk.StringVar(value='');tk.Label(normbox,textvariable=self.norm_summary_var,bg='white',fg=COLORS['text'],font=('Segoe UI',9),justify='left',anchor='w',wraplength=760).pack(side='left',fill='x',expand=True,padx=8,pady=6);ttk.Button(normbox,text='Vybrat normy',command=lambda:self.nb.select(self.tab_norms)).pack(side='right',padx=6,pady=6);rr+=1
        ttk.Label(g,text='Rozsah revize',style='Subtle.TLabel').grid(row=rr,column=0,sticky='nw',padx=(10,8),pady=7)
        scopebox=ttk.Frame(g);scopebox.grid(row=rr,column=1,columnspan=3,sticky='ew',padx=(0,10),pady=5);scopebox.columnconfigure(0,weight=1)
        t=tk.Text(scopebox,height=9,font=('Segoe UI',9),wrap='word',undo=True);sy=ttk.Scrollbar(scopebox,orient='vertical',command=t.yview);t.configure(yscrollcommand=sy.set)
        t.grid(row=0,column=0,sticky='ew');sy.grid(row=0,column=1,sticky='ns');self.texts['scope']=t;rr+=1
        if self.revision_type=='STROJ':
            box=ttk.Frame(g);box.grid(row=rr,column=1,columnspan=3,sticky='ew',padx=(0,10),pady=(0,8))
            ttk.Label(box,text='Rychlé texty z databáze:',style='Subtle.TLabel').pack(side='left')
            ttk.Button(box,text='Dílčí podklad - zdvihací zařízení',command=lambda:self.insert_learned_scope_template('machine_scope_template',0)).pack(side='left',padx=5)
            ttk.Button(box,text='Obecné omezení rozsahu stroje',command=lambda:self.insert_learned_scope_template('machine_scope_template',1)).pack(side='left')
        elif self.revision_type=='ELEKTRO':
            box=ttk.Frame(g);box.grid(row=rr,column=1,columnspan=3,sticky='ew',padx=(0,10),pady=(0,8))
            ttk.Label(box,text='Rychlé texty z databáze:',style='Subtle.TLabel').pack(side='left')
            ttk.Button(box,text='Instalace před souborem ČSN 33 2000',command=lambda:self.insert_learned_scope_template('legacy_installation_note',0)).pack(side='left',padx=5)


    def _build_basic_external(self):
        """Zjednodušené základní údaje protokolu VV bez polí určených pro revizní zprávu."""
        self._combo_data(); f=self.tab_basic
        sf=ScrollFrame(f);sf.pack(fill='both',expand=True,padx=4,pady=4);g=sf.inner
        g.columnconfigure(1,weight=1);g.columnconfigure(3,weight=1)
        tk.Label(g,text='PROTOKOL O URČENÍ VNĚJŠÍCH VLIVŮ',bg='#E2E2E2',fg=COLORS['text'],font=('Segoe UI Semibold',10),anchor='w',padx=8).grid(row=0,column=0,columnspan=4,sticky='ew',padx=10,pady=(8,8))
        fields=[
            ('revision_no','Číslo protokolu','entry',None),
            ('issued_on','Datum vypracování','entry',None),
            ('customer','Zákazník / objednatel','combo',['']+list(self.customer_map)),
            ('status','Stav','combo',['Rozpracovaná','Ke kontrole','Uzavřená']),
        ]
        for idx,(key,label,kind,opts) in enumerate(fields):
            rr=1+idx//2;cc=(idx%2)*2
            ttk.Label(g,text=label,style='Subtle.TLabel').grid(row=rr,column=cc,sticky='w',padx=(10,8),pady=6)
            v=tk.StringVar(value=self._basic_initial(key));self.vars[key]=v
            w=ttk.Combobox(g,textvariable=v,values=opts,state='readonly') if kind=='combo' else ttk.Entry(g,textvariable=v)
            w.grid(row=rr,column=cc+1,sticky='ew',padx=(0,10),pady=5)
        rr=3
        actions=ttk.Frame(g);actions.grid(row=rr,column=0,columnspan=4,sticky='ew',padx=10,pady=(3,8))
        ttk.Button(actions,text='Nový zákazník / ARES',command=self.create_customer_from_editor).pack(side='left')
        ttk.Button(actions,text='Obnovit seznam zákazníků',command=self.refresh_customer_combo).pack(side='left',padx=5)
        ttk.Button(actions,text='Převzít adresu zákazníka do objektu',command=self.copy_customer_address_to_object).pack(side='right')
        rr+=1
        tk.Label(g,text='OBJEKT / POSUZOVANÉ PROSTORY',bg='#E2E2E2',fg=COLORS['text'],font=('Segoe UI Semibold',9),anchor='w',padx=8).grid(row=rr,column=0,columnspan=4,sticky='ew',padx=10,pady=(2,6));rr+=1
        obj_fields=[('object_name_text','Název objektu'),('object_address_text','Adresa objektu'),('object_city_text','Obec / město'),('object_zip_text','PSČ'),('object_parcel_text','Parcela / katastr'),('object_location_note','Upřesnění místa / část objektu')]
        for idx,(key,label) in enumerate(obj_fields):
            r=rr+idx//2;cc=(idx%2)*2
            ttk.Label(g,text=label,style='Subtle.TLabel').grid(row=r,column=cc,sticky='w',padx=(10,8),pady=6)
            v=tk.StringVar(value=self.rev.get(key) or '');self.vars[key]=v
            ttk.Entry(g,textvariable=v).grid(row=r,column=cc+1,sticky='ew',padx=(0,10),pady=5)
        rr += (len(obj_fields)+1)//2
        info=tk.LabelFrame(g,text='Postup')
        info.grid(row=rr,column=0,columnspan=4,sticky='ew',padx=10,pady=(8,10))
        tk.Label(info,text='1. Doplň údaje objektu  →  2. Obecné – titulní strana + popis celé budovy  →  3. Normy  →  4. Popis posuzovaného objektu  →  5. Podklady  →  6. Vnější vlivy – místnost má karty Popis a Vnější vlivy.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9),justify='left',anchor='w').pack(fill='x',padx=10,pady=8)

        # Interní pole původního datového modelu. U protokolu VV se nezobrazují,
        # ale zachovávají kompatibilitu s uložením a staršími verzemi.
        defaults={
            'revision_kind':self.rev.get('revision_kind') or 'Výchozí',
            'started_on':self.rev.get('started_on') or self._basic_initial('issued_on'),
            'finished_on':self.rev.get('finished_on') or self._basic_initial('issued_on'),
            'next_revision_on':self.rev.get('next_revision_on') or '',
            'vtz_class':self.rev.get('vtz_class') or '',
            'result':self.rev.get('result') or 'Nehodnoceno',
            'distribution_text':self.rev.get('distribution_text') or '',
            'received_on':self.rev.get('received_on') or '',
        }
        for key,val in defaults.items():self.vars[key]=tk.StringVar(value=val)
        self.deadline_watch_var=tk.BooleanVar(value=False)
        self.texts['subject']=tk.Text(f,height=1);self.texts['scope']=tk.Text(f,height=1)
        self.norm_summary_var=tk.StringVar(value='')

    def insert_learned_scope_template(self,category,index=0):
        rows=self.db.learned_values(category,20)
        if not rows:return
        try:txt=rows[index]['value']
        except Exception:txt=rows[0]['value']
        target=self.texts.get('scope')
        if not target:return
        current=target.get('1.0','end').strip()
        if current:
            target.insert('end','\n\n'+txt)
        else:
            target.insert('1.0',txt)

    def _basic_initial(self,key):
        if key=='revision_no':return self.rev.get(key) or self.db.next_revision_no(self.revision_type)
        if key=='revision_kind':return self.rev.get(key) or ('Pravidelná' if self.revision_type!='VNEJSI' else 'Výchozí')
        if key=='status':return self.rev.get(key) or 'Rozpracovaná'
        if key in ('started_on','finished_on','issued_on'):return self.rev.get(key) if self.rev and key in self.rev and self.rev.get(key) is not None else today()
        if key=='result':return self.rev.get(key) or 'Nehodnoceno'
        if key=='vtz_class':return self.rev.get(key) or 'II'
        if key=='distribution_text':return self.rev.get(key) or '1× revizní technik, 2× provozovatel'
        if key=='received_on':return self.rev.get(key) or ''
        if key=='customer':return next((k for k,v in self.customer_map.items() if v==self.rev.get('customer_id')),'')
        return self.rev.get(key) or ''

    def refresh_customer_combo(self):
        current=self.vars.get('customer').get() if self.vars.get('customer') else ''
        self._combo_data()
        # locate customer combobox by walking widgets linked to same textvariable is awkward; rebuild values by search
        for w in self.tab_basic.winfo_children():
            for c in w.winfo_children() if hasattr(w,'winfo_children') else []:
                pass
        # direct Tk lookup: all comboboxes inside scrollframe
        def walk(widget):
            for ch in widget.winfo_children():
                if isinstance(ch,ttk.Combobox) and str(ch.cget('textvariable'))==str(self.vars['customer']):ch.configure(values=['']+list(self.customer_map))
                walk(ch)
        walk(self.tab_basic)
        if current in self.customer_map:self.vars['customer'].set(current)

    def create_customer_from_editor(self):
        d=AresCustomerDialog(self,'Nový zákazník / ARES');self.wait_window(d)
        if d.result:
            keys=['name','ico','dic','address','city','zip','contact','phone','email','note'];cid=self.db.execute('INSERT INTO customers(name,ico,dic,address,city,zip,contact,phone,email,note) VALUES(?,?,?,?,?,?,?,?,?,?)',tuple(d.result.get(k,'') for k in keys));self.refresh_customer_combo();label=next((k for k,v in self.customer_map.items() if v==cid),'');self.vars['customer'].set(label)

    def copy_customer_address_to_object(self):
        cid=self.customer_map.get(self.vars['customer'].get())
        if not cid:messagebox.showinfo('Revidovaný objekt','Nejprve vyber zákazníka.');return
        c=self.db.fetchone('SELECT * FROM customers WHERE id=?',(cid,))
        if not c:return
        if not self.vars['object_name_text'].get().strip():self.vars['object_name_text'].set(c['name'] or '')
        self.vars['object_address_text'].set(c['address'] or '');self.vars['object_city_text'].set(c['city'] or '');self.vars['object_zip_text'].set(c['zip'] or '')

    def _build_protection(self):
        pan=tk.PanedWindow(self.tab_protection,orient='horizontal',sashwidth=5,bg=COLORS['line']);pan.pack(fill='both',expand=True,padx=10,pady=10)
        left=tk.Frame(pan,bg='white');right=tk.Frame(pan,bg='white');pan.add(left,minsize=540);pan.add(right,minsize=540)
        lh=tk.Frame(left,bg='white');lh.pack(fill='x',padx=8,pady=8);tk.Label(lh,text='Katalog ochranných opatření',bg='white',font=('Segoe UI Semibold',10)).pack(side='left');self.prot_search=tk.StringVar();ttk.Entry(lh,textvariable=self.prot_search,width=24).pack(side='right');self.prot_search.trace_add('write',lambda *a:self.refresh_protection_catalog())
        self.prot_catalog=ttk.Treeview(left,columns=('group','label','csn','en'),show='headings')
        for k,l,w in [('group','Skupina',180),('label','Druh ochrany',300),('csn','ČSN 33 2000-4-41 ed.3',180),('en','ČSN EN 61140 ed.3',150)]:self.prot_catalog.heading(k,text=l);self.prot_catalog.column(k,width=w,anchor='w')
        self.prot_catalog.pack(fill='both',expand=True,padx=8,pady=(0,6));self.prot_catalog.bind('<Double-1>',lambda e:self.add_protection_from_catalog())
        lf=ttk.Frame(left);lf.pack(fill='x',padx=8,pady=(0,8));ttk.Button(lf,text='Nová položka',command=self.new_protection_catalog_item).pack(side='left');ttk.Button(lf,text='Upravit katalog',command=self.edit_protection_catalog_item).pack(side='left',padx=4);ttk.Button(lf,text='Přidat do revize →',style='Accent.TButton',command=self.add_protection_from_catalog).pack(side='right')
        rh=tk.Frame(right,bg='white');rh.pack(fill='x',padx=8,pady=8);tk.Label(rh,text='Použité ochrany v této revizi',bg='white',font=('Segoe UI Semibold',10)).pack(side='left');tk.Label(rh,text='Do zprávy se vytisknou pouze tyto položky',bg='white',fg=COLORS['muted'],font=('Segoe UI',8)).pack(side='right')
        self.prot_selected=ttk.Treeview(right,columns=('group','label','csn','en'),show='headings')
        for k,l,w in [('group','Skupina',170),('label','Druh ochrany',300),('csn','ČSN',170),('en','EN 61140',140)]:self.prot_selected.heading(k,text=l);self.prot_selected.column(k,width=w,anchor='w')
        self.prot_selected.pack(fill='both',expand=True,padx=8,pady=(0,6));self.prot_selected.bind('<Double-1>',lambda e:self.edit_selected_protection())
        rf=ttk.Frame(right);rf.pack(fill='x',padx=8,pady=(0,8));ttk.Button(rf,text='Nahoru',command=lambda:self.move_protection(-1)).pack(side='left');ttk.Button(rf,text='Dolů',command=lambda:self.move_protection(1)).pack(side='left',padx=4);ttk.Button(rf,text='Upravit poznámku',command=self.edit_selected_protection).pack(side='right',padx=4);ttk.Button(rf,text='Odebrat',style='Danger.TButton',command=self.remove_selected_protection).pack(side='right')
        self.refresh_protection_catalog();self.refresh_selected_protections()

    def refresh_protection_catalog(self):
        if not hasattr(self,'prot_catalog'):return
        q=f"%{self.prot_search.get().strip()}%";rows=self.db.fetchall("SELECT * FROM protection_catalog WHERE active=1 AND (group_name LIKE ? OR label LIKE ? OR csn_ref LIKE ? OR en_ref LIKE ?) ORDER BY group_name,id",(q,q,q,q))
        for x in self.prot_catalog.get_children():self.prot_catalog.delete(x)
        for r in rows:self.prot_catalog.insert('','end',iid=str(r['id']),values=(r['group_name'],r['label'],r['csn_ref'],r['en_ref']))

    def refresh_selected_protections(self):
        if not hasattr(self,'prot_selected'):return
        for x in self.prot_selected.get_children():self.prot_selected.delete(x)
        for i,r in enumerate(self.protection_measures):self.prot_selected.insert('','end',iid=str(i),values=(r.get('group_snapshot',''),r.get('label_snapshot',''),r.get('csn_ref_snapshot',''),r.get('en_ref_snapshot','')))

    def add_protection_from_catalog(self):
        s=self.prot_catalog.selection()
        if not s:return
        r=dict(self.db.fetchone('SELECT * FROM protection_catalog WHERE id=?',(int(s[0]),)))
        if any(x.get('catalog_id')==r['id'] or (x.get('group_snapshot')==r['group_name'] and x.get('label_snapshot')==r['label']) for x in self.protection_measures):return
        self.protection_measures.append({'catalog_id':r['id'],'group_snapshot':r['group_name'],'label_snapshot':r['label'],'csn_ref_snapshot':r['csn_ref'],'en_ref_snapshot':r['en_ref'],'note':r['note'] or ''});self.refresh_selected_protections()

    def _protection_fields(self):
        return [('group_name','Skupina','combo_edit',['2.1 Druh ochranného opatření','2.2 Prostředky základní ochrany','2.3 Prostředky ochrany při poruše','2.4 Doplňková ochrana','2.5 Zařízení podle třídy ochrany']),('label','Název ochrany'),('csn_ref','Článek dle ČSN 33 2000-4-41 ed.3'),('en_ref','Článek dle ČSN EN 61140 ed.3'),('note','Poznámka','text')]
    def new_protection_catalog_item(self):
        d=FormDialog(self,'Nová ochrana do katalogu',self._protection_fields(),width=760,height=570);self.wait_window(d)
        if d.result and d.result.get('label','').strip():
            try:self.db.execute('INSERT INTO protection_catalog(group_name,label,csn_ref,en_ref,note,active) VALUES(?,?,?,?,?,1)',(d.result['group_name'] or 'Vlastní',d.result['label'],d.result['csn_ref'],d.result['en_ref'],d.result['note']))
            except Exception as e:messagebox.showerror('Ochrany',str(e))
            self.refresh_protection_catalog()
    def edit_protection_catalog_item(self):
        s=self.prot_catalog.selection()
        if not s:return
        rid=int(s[0]);r=dict(self.db.fetchone('SELECT * FROM protection_catalog WHERE id=?',(rid,)));d=FormDialog(self,'Upravit ochranu v katalogu',self._protection_fields(),r,width=760,height=570);self.wait_window(d)
        if d.result:self.db.execute('UPDATE protection_catalog SET group_name=?,label=?,csn_ref=?,en_ref=?,note=? WHERE id=?',(d.result['group_name'],d.result['label'],d.result['csn_ref'],d.result['en_ref'],d.result['note'],rid));self.refresh_protection_catalog()
    def edit_selected_protection(self):
        s=self.prot_selected.selection()
        if not s:return
        idx=int(s[0]);r=self.protection_measures[idx];fields=[('group_snapshot','Skupina'),('label_snapshot','Druh ochrany'),('csn_ref_snapshot','ČSN 33 2000-4-41 ed.3'),('en_ref_snapshot','ČSN EN 61140 ed.3'),('note','Poznámka','text')];d=FormDialog(self,'Upravit ochranu v této revizi',fields,r,width=760,height=570);self.wait_window(d)
        if d.result:self.protection_measures[idx].update(d.result);self.refresh_selected_protections()
    def remove_selected_protection(self):
        s=self.prot_selected.selection()
        if s:self.protection_measures.pop(int(s[0]));self.refresh_selected_protections()
    def move_protection(self,delta):
        s=self.prot_selected.selection()
        if not s:return
        i=int(s[0]);j=i+delta
        if 0<=j<len(self.protection_measures):self.protection_measures[i],self.protection_measures[j]=self.protection_measures[j],self.protection_measures[i];self.refresh_selected_protections();self.prot_selected.selection_set(str(j))

    def _build_inspection(self):
        pan=tk.PanedWindow(self.tab_inspection,orient='horizontal',sashwidth=5,bg=COLORS['line']);pan.pack(fill='both',expand=True,padx=10,pady=10)
        left=tk.Frame(pan,bg='white');right=tk.Frame(pan,bg='white');pan.add(left,minsize=520);pan.add(right,minsize=560)
        lh=tk.Frame(left,bg='white');lh.pack(fill='x',padx=8,pady=8);tk.Label(lh,text='Katalog prohlídek / kontrol',bg='white',font=('Segoe UI Semibold',10)).pack(side='left');self.insp_search=tk.StringVar();ttk.Entry(lh,textvariable=self.insp_search,width=25).pack(side='right');self.insp_search.trace_add('write',lambda *a:self.refresh_inspection_catalog())
        self.insp_catalog=ttk.Treeview(left,columns=('group','label','source'),show='headings')
        for k,l,w in [('group','Skupina',170),('label','Kontrolovaný bod',390),('source','Podklad',230)]:self.insp_catalog.heading(k,text=l);self.insp_catalog.column(k,width=w,anchor='w')
        self.insp_catalog.pack(fill='both',expand=True,padx=8,pady=(0,6));self.insp_catalog.bind('<Double-1>',lambda e:self.add_inspection_from_catalog())
        lf=ttk.Frame(left);lf.pack(fill='x',padx=8,pady=(0,8));ttk.Button(lf,text='Nový bod',command=self.new_inspection_catalog_item).pack(side='left');ttk.Button(lf,text='Upravit katalog',command=self.edit_inspection_catalog_item).pack(side='left',padx=4)
        if self.revision_type=='ELEKTRO':ttk.Button(lf,text='Doplnit body EI',command=self.add_electrical_inspection_template).pack(side='left',padx=4)
        ttk.Button(lf,text='Přidat do revize →',style='Accent.TButton',command=self.add_inspection_from_catalog).pack(side='right')
        rh=tk.Frame(right,bg='white');rh.pack(fill='x',padx=8,pady=8);tk.Label(rh,text='Prohlídka v této revizi',bg='white',font=('Segoe UI Semibold',10)).pack(side='left');tk.Label(rh,text='Nepoužité / neexistující body se do zprávy nevkládají.',bg='white',fg=COLORS['muted'],font=('Segoe UI',8)).pack(side='right')
        self.insp_selected=ttk.Treeview(right,columns=('group','label','result','note'),show='headings')
        for k,l,w in [('group','Skupina',150),('label','Kontrolovaný bod',370),('result','Výsledek',110),('note','Poznámka',220)]:self.insp_selected.heading(k,text=l);self.insp_selected.column(k,width=w,anchor='w')
        self.insp_selected.pack(fill='both',expand=True,padx=8,pady=(0,6));self.insp_selected.bind('<Double-1>',lambda e:self.edit_inspection_item())
        rf=ttk.Frame(right);rf.pack(fill='x',padx=8,pady=(0,8));ttk.Button(rf,text='VYHOVUJE',style='Success.TButton',command=lambda:self.set_inspection_result('VYHOVUJE')).pack(side='left');ttk.Button(rf,text='NEVYHOVUJE',style='Danger.TButton',command=lambda:self.set_inspection_result('NEVYHOVUJE')).pack(side='left',padx=4);ttk.Button(rf,text='NEPROVEDENO',command=lambda:self.set_inspection_result('NEPROVEDENO')).pack(side='left');ttk.Button(rf,text='+ Závada',command=self.create_defect_from_inspection).pack(side='right',padx=4);ttk.Button(rf,text='Upravit',command=self.edit_inspection_item).pack(side='right',padx=4);ttk.Button(rf,text='Odebrat',command=self.remove_inspection_item).pack(side='right')
        self.refresh_inspection_catalog();self.refresh_inspection_items()

    def refresh_inspection_catalog(self):
        if not hasattr(self,'insp_catalog'):return
        q=f"%{self.insp_search.get().strip()}%";rows=self.db.fetchall("SELECT * FROM inspection_catalog WHERE active=1 AND (group_name LIKE ? OR label LIKE ? OR source_ref LIKE ?) ORDER BY group_name,id",(q,q,q))
        for x in self.insp_catalog.get_children():self.insp_catalog.delete(x)
        for r in rows:self.insp_catalog.insert('','end',iid=str(r['id']),values=(r['group_name'],r['label'],r['source_ref']))
    def refresh_inspection_items(self):
        if not hasattr(self,'insp_selected'):return
        for x in self.insp_selected.get_children():self.insp_selected.delete(x)
        for i,r in enumerate(self.inspection_items):self.insp_selected.insert('','end',iid=str(i),values=(r.get('group_snapshot',''),r.get('label_snapshot',''),r.get('result','VYHOVUJE'),r.get('note','')))
    def add_inspection_from_catalog(self):
        s=self.insp_catalog.selection()
        if not s:return
        r=dict(self.db.fetchone('SELECT * FROM inspection_catalog WHERE id=?',(int(s[0]),)))
        if any(x.get('catalog_id')==r['id'] or (x.get('group_snapshot')==r['group_name'] and x.get('label_snapshot')==r['label']) for x in self.inspection_items):return
        self.inspection_items.append({'catalog_id':r['id'],'group_snapshot':r['group_name'],'label_snapshot':r['label'],'source_ref_snapshot':r['source_ref'],'result':'VYHOVUJE','note':''});self.refresh_inspection_items()
    def add_electrical_inspection_template(self, quiet=False):
        """Doplní standardní body prohlídky EI z dodané vzorové revize.

        Body jsou vedeny ve dvou samostatných skupinách: požadavky NV 190/2022 Sb.
        a kontrolní body ČSN 33 2000-6 ed. 2. Existující položky se neduplikují.
        """
        if self.revision_type!='ELEKTRO':
            return 0
        added=0
        for group in ELECTRICAL_INSPECTION_TEMPLATE_GROUPS:
            rows=self.db.fetchall("SELECT * FROM inspection_catalog WHERE active=1 AND group_name=? ORDER BY id",(group,))
            for row in rows:
                r=dict(row)
                if any(x.get('catalog_id')==r['id'] or (x.get('group_snapshot')==r['group_name'] and x.get('label_snapshot')==r['label']) for x in self.inspection_items):
                    continue
                self.inspection_items.append({
                    'catalog_id':r['id'],
                    'group_snapshot':r['group_name'],
                    'label_snapshot':r['label'],
                    'source_ref_snapshot':r['source_ref'],
                    'result':'VYHOVUJE',
                    'note':r.get('note') or '',
                })
                added+=1
        self.refresh_inspection_items()
        if not quiet:
            if added:
                messagebox.showinfo('Prohlídka EI',f'Doplněno {added} bodů prohlídky. Již vložené body nebyly duplikovány.')
            else:
                messagebox.showinfo('Prohlídka EI','Všechny základní body prohlídky EI už jsou v revizi vloženy.')
        return added

    def _inspection_fields(self):return [('group_name','Skupina'),('label','Kontrolovaný bod','text'),('source_ref','Norma / článek / podklad'),('note','Výchozí poznámka','text')]
    def new_inspection_catalog_item(self):
        d=FormDialog(self,'Nový kontrolní bod',self._inspection_fields(),width=760,height=580);self.wait_window(d)
        if d.result and d.result.get('label','').strip():
            try:self.db.execute('INSERT INTO inspection_catalog(group_name,label,source_ref,note,active) VALUES(?,?,?,?,1)',(d.result['group_name'] or 'Vlastní',d.result['label'],d.result['source_ref'],d.result['note']))
            except Exception as e:messagebox.showerror('Prohlídka',str(e))
            self.refresh_inspection_catalog()
    def edit_inspection_catalog_item(self):
        s=self.insp_catalog.selection()
        if not s:return
        rid=int(s[0]);r=dict(self.db.fetchone('SELECT * FROM inspection_catalog WHERE id=?',(rid,)));d=FormDialog(self,'Upravit kontrolní bod',self._inspection_fields(),r,width=760,height=580);self.wait_window(d)
        if d.result:self.db.execute('UPDATE inspection_catalog SET group_name=?,label=?,source_ref=?,note=? WHERE id=?',(d.result['group_name'],d.result['label'],d.result['source_ref'],d.result['note'],rid));self.refresh_inspection_catalog()
    def edit_inspection_item(self):
        s=self.insp_selected.selection()
        if not s:return
        idx=int(s[0]);fields=[('label_snapshot','Kontrolovaný bod','text'),('source_ref_snapshot','Norma / článek'),('result','Výsledek','combo',['VYHOVUJE','NEVYHOVUJE','NEPROVEDENO']),('note','Poznámka','text')];d=FormDialog(self,'Výsledek prohlídky',fields,self.inspection_items[idx],width=760,height=570);self.wait_window(d)
        if d.result:self.inspection_items[idx].update(d.result);self.refresh_inspection_items()
    def set_inspection_result(self,result):
        for iid in self.insp_selected.selection():self.inspection_items[int(iid)]['result']=result
        self.refresh_inspection_items()
    def remove_inspection_item(self):
        s=self.insp_selected.selection()
        if s:self.inspection_items.pop(int(s[0]));self.refresh_inspection_items()
    def create_defect_from_inspection(self):
        s=self.insp_selected.selection()
        if not s:return
        item=self.inspection_items[int(s[0])]
        initial={'category':'Prohlídka','standard':item.get('source_ref_snapshot',''),'article':'','defect_text':f"Při prohlídce nebyl splněn kontrolní bod: {item.get('label_snapshot','')}",'severity':'Střední','status':'Neodstraněna','note':item.get('note',''),'_photos':[]}
        d=DefectDialog(self,'Závada z prohlídky',initial);self.wait_window(d)
        if d.result:d.result['catalog_id']=None;self.rev_defects.append(d.result);item['result']='NEVYHOVUJE';self.refresh_inspection_items();self.refresh_revision_defects();self.nb.select(self.tab_defects)

    def _build_working_photos(self):
        tk.Label(self.tab_photos,text='Pracovní fotografie zůstávají pouze v aplikaci a standardně se netisknou do revizní zprávy.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9)).pack(anchor='w',padx=12,pady=(12,6))
        bar=ttk.Frame(self.tab_photos);bar.pack(fill='x',padx=12,pady=6);ttk.Button(bar,text='Přidat fotografie',style='Accent.TButton',command=self.add_working_photos).pack(side='left');ttk.Button(bar,text='Upravit popis',command=self.edit_working_photo).pack(side='left',padx=5);ttk.Button(bar,text='Otevřít',command=self.open_working_photo).pack(side='left');ttk.Button(bar,text='Odebrat',style='Danger.TButton',command=self.remove_working_photo).pack(side='left',padx=5)
        self.working_photo_tree=ttk.Treeview(self.tab_photos,columns=('file','title','note'),show='headings');
        for k,l,w in [('file','Soubor',330),('title','Popisek',280),('note','Poznámka',400)]:self.working_photo_tree.heading(k,text=l);self.working_photo_tree.column(k,width=w,anchor='w')
        self.working_photo_tree.pack(fill='both',expand=True,padx=12,pady=(0,12));self.working_photo_tree.bind('<Double-1>',lambda e:self.open_working_photo());self.refresh_working_photos()
    def refresh_working_photos(self):
        if not hasattr(self,'working_photo_tree'):return
        for x in self.working_photo_tree.get_children():self.working_photo_tree.delete(x)
        for i,p in enumerate(self.working_photos):self.working_photo_tree.insert('','end',iid=str(i),values=(p.get('original_name') or Path(p.get('stored_path') or p.get('source_path') or '').name,p.get('title',''),p.get('note','')))
    def add_working_photos(self):
        paths=filedialog.askopenfilenames(title='Pracovní fotografie',filetypes=[('Obrázky','*.jpg *.jpeg *.png *.webp *.bmp'),('Všechny soubory','*.*')])
        for path in paths:self.working_photos.append({'source_path':path,'stored_path':'','original_name':Path(path).name,'title':'','note':'','kind':'working'})
        self.refresh_working_photos()
    def edit_working_photo(self):
        s=self.working_photo_tree.selection()
        if not s:return
        idx=int(s[0]);d=FormDialog(self,'Popis pracovní fotografie',[('title','Popisek'),('note','Poznámka','text')],self.working_photos[idx],width=620,height=420);self.wait_window(d)
        if d.result:self.working_photos[idx].update(d.result);self.refresh_working_photos()
    def open_working_photo(self):
        s=self.working_photo_tree.selection()
        if not s:return
        p=self.working_photos[int(s[0])];path=p.get('stored_path') or p.get('source_path')
        if path and Path(path).exists():
            try:
                if os.name=='nt':os.startfile(str(path))
                elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
                else:subprocess.Popen(['xdg-open',str(path)])
            except Exception as e:messagebox.showerror('Fotografie',str(e))
    def remove_working_photo(self):
        s=self.working_photo_tree.selection()
        if s:self.working_photos.pop(int(s[0]));self.refresh_working_photos()

    @staticmethod
    def _prefix_text_lines(widget, mode='bullet'):
        """Apply or remove bullets/numbering on the selected lines of a Text widget."""
        try:
            start=widget.index('sel.first');end=widget.index('sel.last')
        except tk.TclError:
            line=int(widget.index('insert').split('.')[0]);start=f'{line}.0';end=f'{line}.end'
        start=f"{start.split('.')[0]}.0"
        end_line=int(end.split('.')[0])
        if end.endswith('.0') and end_line>int(start.split('.')[0]):end_line-=1
        end=f'{end_line}.end'
        raw=widget.get(start,end)
        lines=raw.split('\n')
        if mode=='bullet':
            active=bool([x for x in lines if x.strip()]) and all(re.match(r'^\s*•\s+',x) for x in lines if x.strip())
            out=[]
            for line in lines:
                if not line.strip():out.append(line);continue
                clean=re.sub(r'^\s*(?:[•–-]\s+|\d+[.)]\s+)', '', line)
                out.append(clean if active else '• '+clean)
        else:
            out=[];n=1
            for line in lines:
                if not line.strip():out.append(line);continue
                clean=re.sub(r'^\s*(?:[•–-]\s+|\d+[.)]\s+)', '', line)
                out.append(f'{n}. {clean}');n+=1
        widget.delete(start,end);widget.insert(start,'\n'.join(out));widget.focus_set()

    def _external_text_editor(self, parent, key, value='', height=10, help_text='', show_tools=True):
        box=ttk.Frame(parent)
        if show_tools or help_text:
            tools=ttk.Frame(box);tools.pack(fill='x',pady=(0,4))
            if show_tools:
                ttk.Button(tools,text='• Odrážky',command=lambda:self._prefix_text_lines(text,'bullet')).pack(side='left')
                ttk.Button(tools,text='1. Číslování',command=lambda:self._prefix_text_lines(text,'number')).pack(side='left',padx=(5,0))
            if help_text:
                ttk.Label(tools,text=help_text,style='Subtle.TLabel').pack(side='left',padx=(12 if show_tools else 0,0))
        body=ttk.Frame(box);body.pack(fill='both',expand=True)
        text=tk.Text(body,height=height,font=('Segoe UI',10),wrap='word',undo=True,relief='solid',bd=1,padx=7,pady=6)
        text.insert('1.0',value or '')
        ys=ttk.Scrollbar(body,orient='vertical',command=text.yview);text.configure(yscrollcommand=ys.set)
        text.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');body.rowconfigure(0,weight=1);body.columnconfigure(0,weight=1)
        self.special_vars[key]=text
        return box

    def _external_page3_template_text(self):
        # Zachováno pro kompatibilitu starších dat; nová verze má obecný text
        # předvyplněný přímo podle stran 2-5 dodaného vzorového protokolu.
        lines=[]
        if self.documents:
            lines.append('Podklady:')
            for d in self.documents:
                item=' – '.join(x for x in [str(d.get('doc_type') or '').strip(),str(d.get('doc_no') or '').strip(),str(d.get('author') or '').strip(),str(d.get('note') or '').strip()] if x)
                if item:lines.append('• '+item)
            lines.append('')
        if self.rev_standards:
            lines.append('Legislativa / použité normy:')
            for r in self.rev_standards:
                item='  '.join(x for x in [str(r.get('code_snapshot') or '').strip(),str(r.get('title_snapshot') or '').strip()] if x)
                if item:lines.append('• '+item)
        return '\n'.join(lines).strip()

    def _fill_external_page3_template(self):
        target=self.special_vars.get('general_page_3')
        if not isinstance(target,tk.Text):return
        generated=self._external_page3_template_text()
        if not generated:
            messagebox.showinfo('Obecné','Nejsou zadány podklady ani normy, ze kterých by šlo vytvořit návrh.',parent=self);return
        current=target.get('1.0','end').strip()
        if current and not messagebox.askyesno('Obecné','Nahradit současný text strany 3 aktuálními podklady a normami?',parent=self):return
        target.delete('1.0','end');target.insert('1.0',generated)

    def _build_external_special(self):
        """Titulní strana + samostatné obecné textové pole pro popis celé budovy."""
        nb=ttk.Notebook(self.tab_special);nb.pack(fill='both',expand=True,padx=10,pady=10)
        tab_people=ttk.Frame(nb);tab_general=ttk.Frame(nb)
        nb.add(tab_people,text='Titulní strana')
        nb.add(tab_general,text='Obecné')

        form=ttk.Frame(tab_people);form.pack(fill='both',expand=True,padx=14,pady=14);form.columnconfigure(1,weight=1)
        rows=[('revision_seq','Revize č. (pro zápatí protokolu)'),('owner','Majitel'),('operator','Provozovatel'),('premises','Rozsah posuzovaných prostor'),('chairperson','Předseda komise')]
        for r,(key,label) in enumerate(rows):
            ttk.Label(form,text=label,style='Subtle.TLabel').grid(row=r,column=0,sticky='w',padx=(0,12),pady=5)
            v=tk.StringVar(value=self.special.get(key,'') or '');self.special_vars[key]=v
            ttk.Entry(form,textvariable=v).grid(row=r,column=1,sticky='ew',pady=3)
        title_default='o určení vnějších vlivů podle ČSN 33 2000-5-51 ed.3 + Z1+Z2\na určení nebezpečných prostorů dle ČSN 60079-10-2 ed.2\na ČSN EN 60079-10-1 ed.3'
        ttk.Label(form,text='Text pod názvem protokolu',style='Subtle.TLabel').grid(row=5,column=0,sticky='nw',padx=(0,12),pady=5)
        titlebox=self._external_text_editor(form,'protocol_title_text',self.special.get('protocol_title_text','') or title_default,height=4,help_text='Každý řádek se na titulní straně vytiskne jako samostatný řádek názvu.',show_tools=False)
        titlebox.grid(row=5,column=1,sticky='ew',pady=3)
        ttk.Label(form,text='Členové komise',style='Subtle.TLabel').grid(row=6,column=0,sticky='nw',padx=(0,12),pady=5)
        members=self._external_text_editor(form,'committee_members',self.special.get('committee_members',''),height=4,help_text='Každého člena uveď na samostatný řádek. Pole komise je záměrně kompaktní.',show_tools=False)
        members.grid(row=6,column=1,sticky='ew',pady=3)

        outer=ttk.Frame(tab_general);outer.pack(fill='both',expand=True,padx=14,pady=14)
        ttk.Label(outer,text='Popis celé budovy / areálu',font=('Segoe UI Semibold',12)).pack(anchor='w')
        ttk.Label(outer,text='Prázdné velké textové pole. Text si vyplníš podle konkrétního objektu; k dispozici jsou odrážky a číslování.',style='Subtle.TLabel').pack(anchor='w',pady=(2,7))
        ed=self._external_text_editor(outer,'general_text',self.special.get('general_text',''),height=40)
        ed.pack(fill='both',expand=True)

    def _build_external_description(self):
        if self.revision_type!='VNEJSI':
            return
        wrap=ttk.Frame(self.tab_description);wrap.pack(fill='both',expand=True,padx=14,pady=14)
        ttk.Label(wrap,text='Popis posuzovaného objektu',font=('Segoe UI Semibold',12)).pack(anchor='w')
        ttk.Label(wrap,text='Sem patří tvůj vlastní popis konkrétního posuzovaného objektu. Pole je velké a podporuje odrážky i číslování.',style='Subtle.TLabel').pack(anchor='w',pady=(2,7))
        ed=self._external_text_editor(wrap,'building_description',self.special.get('building_description',''),height=38)
        ed.pack(fill='both',expand=True)

    def _build_special(self):
        if self.revision_type=='VNEJSI':
            return self._build_external_special()
        sf=ScrollFrame(self.tab_special);sf.pack(fill='both',expand=True,padx=12,pady=12);sf.inner.columnconfigure(1,weight=1)
        for r,fld in enumerate(SPECIAL_FIELDS[self.revision_type]):
            key,label=fld[0],fld[1];kind=fld[2] if len(fld)>2 else 'entry';opts=fld[3] if len(fld)>3 else None
            ttk.Label(sf.inner,text=label,style="Subtle.TLabel").grid(row=r,column=0,sticky='nw',padx=(0,12),pady=7)
            val=self.special.get(key,'')
            if kind=='text':
                w=tk.Text(sf.inner,height=4,font=("Segoe UI",9),wrap='word');w.insert('1.0',val or '');w.grid(row=r,column=1,sticky='ew',pady=5);self.special_vars[key]=w
            else:
                v=tk.StringVar(value=val or '');self.special_vars[key]=v
                w=ttk.Combobox(sf.inner,textvariable=v,values=opts,state='readonly') if kind=='combo' else ttk.Entry(sf.inner,textvariable=v)
                w.grid(row=r,column=1,sticky='ew',pady=5)

    def _build_power(self):
        # 0.4.3: zdroj a napájecí soustava jsou v jedné položce. Revizní zpráva tak
        # neobsahuje dvě oddělené tabulky, které by uživatel musel mentálně párovat.
        box=tk.Frame(self.tab_power,bg='white');box.pack(fill='both',expand=True,padx=10,pady=10)
        head=tk.Frame(box,bg='white');head.pack(fill='x',padx=10,pady=(10,2))
        tk.Label(head,text='Zdroje napájení / napěťové soustavy',bg='white',font=('Segoe UI Semibold',11)).pack(side='left')
        ttk.Button(head,text='Přidat',style='Accent.TButton',command=self.add_supply).pack(side='right')
        ttk.Button(head,text='Upravit',command=self.edit_supply).pack(side='right',padx=5)
        ttk.Button(head,text='Smazat',style='Danger.TButton',command=self.delete_supply).pack(side='right')
        tk.Label(box,
                 text='Jeden řádek = jeden zdroj a soustava, kterou z něj v dané části revize používáme. Standardní zápis např.: 3/N/PE AC 230/400 V 50 Hz / TN-S. U TN-C-S může být před bodem rozdělení 3/PEN, za bodem rozdělení 3/N/PE.',
                 bg='white',fg=COLORS['muted'],font=('Segoe UI',9),anchor='w',justify='left',wraplength=1350).pack(fill='x',padx=10,pady=(0,6))
        holder=ttk.Frame(box);holder.pack(fill='both',expand=True,padx=10,pady=(0,10))
        cols=[('type','Druh zdroje',205),('designation','Provozovatel / označení',220),('system','Napájecí soustava',365),('scope','Rozsah / úloha',260),('note','Poznámka',360)]
        self.supply_tree=ttk.Treeview(holder,columns=[x[0] for x in cols],show='headings',height=12)
        for k,l,w in cols:self.supply_tree.heading(k,text=l);self.supply_tree.column(k,width=w,anchor='w',stretch=True)
        ys=ttk.Scrollbar(holder,orient='vertical',command=self.supply_tree.yview);xs=ttk.Scrollbar(holder,orient='horizontal',command=self.supply_tree.xview)
        self.supply_tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        self.supply_tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew')
        holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
        self.supply_tree.bind('<Double-1>',lambda e:self.edit_supply())
        self.refresh_power()

    def refresh_power(self):
        if not hasattr(self,'supply_tree'):return
        for x in self.supply_tree.get_children():self.supply_tree.delete(x)
        for i,r in enumerate(self.supplies):
            self.supply_tree.insert('', 'end', iid=str(i), values=(r.get('supply_type',''),r.get('designation',''),r.get('voltage',''),r.get('backup',''),r.get('note','')))

    def add_supply(self):
        d=PowerSourceDialog(self,'Přidat zdroj napájení');self.wait_window(d)
        if d.result:
            self.db.learn_value('supply_type',d.result.get('supply_type',''));self.supplies.append(d.result);self.refresh_power()
    def edit_supply(self):
        s=self.supply_tree.selection()
        if not s:return
        idx=int(s[0]);d=PowerSourceDialog(self,'Upravit zdroj napájení',self.supplies[idx]);self.wait_window(d)
        if d.result:
            self.db.learn_value('supply_type',d.result.get('supply_type',''));self.supplies[idx].update(d.result);self.refresh_power()
    def delete_supply(self):
        s=self.supply_tree.selection()
        if s and messagebox.askyesno('Smazat','Odebrat tento zdroj napájení z revize?'):
            self.supplies.pop(int(s[0]));self.refresh_power()

    def _build_documentation(self):
        top=ttk.Frame(self.tab_docs);top.pack(fill='x',padx=10,pady=10)
        tk.Label(top,text='Předložená dokumentace se zadává položkově. Nové názvy, zpracovatelé a poznámky si program lokálně zapamatuje a příště nabídne.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9),justify='left').pack(side='left',fill='x',expand=True)
        ttk.Button(top,text='Přidat',style='Accent.TButton',command=self.add_document).pack(side='right')
        ttk.Button(top,text='Upravit',command=self.edit_document).pack(side='right',padx=5)
        ttk.Button(top,text='Odebrat',style='Danger.TButton',command=self.delete_document).pack(side='right')
        holder=ttk.Frame(self.tab_docs);holder.pack(fill='both',expand=True,padx=10,pady=(0,10))
        cols=[('type','Druh dokumentace',230),('no','Označení / číslo',150),('date','Datum',100),('author','Zpracovatel',190),('note','Poznámka',360)]
        self.doc_tree=ttk.Treeview(holder,columns=[x[0] for x in cols],show='headings')
        for k,l,w in cols:self.doc_tree.heading(k,text=l);self.doc_tree.column(k,width=w,anchor='w')
        ys=ttk.Scrollbar(holder,orient='vertical',command=self.doc_tree.yview);xs=ttk.Scrollbar(holder,orient='horizontal',command=self.doc_tree.xview);self.doc_tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        self.doc_tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
        self.doc_tree.bind('<Double-1>',lambda e:self.edit_document());self.refresh_documents()

    def _document_fields(self):
        return [('doc_type','Druh dokumentace','combo_edit',learned_options(self.db,'document_type')),('doc_no','Označení / číslo'),('doc_date','Datum dokumentu'),('author','Zpracovatel','combo_edit',learned_options(self.db,'document_author')),('note','Poznámka','combo_edit',learned_options(self.db,'document_note'))]
    def refresh_documents(self):
        if not hasattr(self,'doc_tree'):return
        for x in self.doc_tree.get_children():self.doc_tree.delete(x)
        for i,d in enumerate(self.documents):self.doc_tree.insert('','end',iid=str(i),values=(d.get('doc_type',''),d.get('doc_no',''),display_date(d.get('doc_date','')),d.get('author',''),d.get('note','')))
    def _learn_document(self,d):
        self.db.learn_value('document_type',d.get('doc_type',''));self.db.learn_value('document_author',d.get('author',''));self.db.learn_value('document_note',d.get('note',''))
    def add_document(self):
        d=FormDialog(self,'Přidat dokumentaci',self._document_fields(),width=760,height=600);self.wait_window(d)
        if d.result and d.result['doc_type'].strip():self._learn_document(d.result);self.documents.append(d.result);self.refresh_documents()
    def edit_document(self):
        s=self.doc_tree.selection()
        if not s:return
        idx=int(s[0]);d=FormDialog(self,'Upravit dokumentaci',self._document_fields(),self.documents[idx],width=760,height=600);self.wait_window(d)
        if d.result and d.result['doc_type'].strip():self._learn_document(d.result);self.documents[idx].update(d.result);self.refresh_documents()
    def delete_document(self):
        s=self.doc_tree.selection()
        if s and messagebox.askyesno('Odebrat dokument','Odebrat položku dokumentace z této revize?'):self.documents.pop(int(s[0]));self.refresh_documents()

    def _build_standards(self):
        pan=tk.PanedWindow(self.tab_norms,orient='horizontal',sashwidth=5,bg=COLORS['line']);pan.pack(fill='both',expand=True,padx=10,pady=10)
        left=tk.Frame(pan,bg='white');right=tk.Frame(pan,bg='white');pan.add(left,minsize=470);pan.add(right,minsize=470)
        top=tk.Frame(left,bg='white');top.pack(fill='x',padx=10,pady=10);tk.Label(top,text='Registr norem',bg='white',font=('Segoe UI Semibold',11)).pack(side='left')
        self.std_search=tk.StringVar();ttk.Entry(top,textvariable=self.std_search,width=24).pack(side='right');self.std_search.trace_add('write',lambda *a:self.refresh_standard_catalog())
        self.std_extended=tk.BooleanVar(value=False)
        ttk.Checkbutton(left,text='Zobrazit historické a neověřené',variable=self.std_extended,command=self.refresh_standard_catalog).pack(anchor='w',padx=10,pady=(0,6))
        self.std_catalog=ttk.Treeview(left,columns=('code','title','status'),show='headings')
        for k,l,w in [('code','Norma / předpis',180),('title','Název',280),('status','Stav',130)]:self.std_catalog.heading(k,text=l);self.std_catalog.column(k,width=w,anchor='w')
        self.std_catalog.pack(fill='both',expand=True,padx=10,pady=(0,8));self.std_catalog.bind('<Double-1>',lambda e:self.add_standard_to_revision())
        lf=ttk.Frame(left);lf.pack(fill='x',padx=10,pady=(0,10));ttk.Button(lf,text='Přidat ručně',command=self.add_manual_standard).pack(side='left');ttk.Button(lf,text='Přidat do revize →',style='Accent.TButton',command=self.add_standard_to_revision).pack(side='right')
        top=tk.Frame(right,bg='white');top.pack(fill='x',padx=10,pady=10);tk.Label(top,text='Použité normy / předpisy',bg='white',font=('Segoe UI Semibold',11)).pack(side='left');ttk.Button(top,text='Upravit',command=self.edit_revision_standard).pack(side='right',padx=4);ttk.Button(top,text='Odebrat',style='Danger.TButton',command=self.delete_revision_standard).pack(side='right')
        self.revstd_tree=ttk.Treeview(right,columns=('code','title','status','verified'),show='headings')
        for k,l,w in [('code','Norma / předpis',180),('title','Název',280),('status','Stav při vložení',130),('verified','Ověřeno',100)]:self.revstd_tree.heading(k,text=l);self.revstd_tree.column(k,width=w,anchor='w')
        self.revstd_tree.pack(fill='both',expand=True,padx=10,pady=(0,10));self.refresh_standard_catalog();self.refresh_revision_standards()

    def refresh_standard_catalog(self):
        if not hasattr(self,'std_catalog'):return
        q=f"%{self.std_search.get().strip()}%"
        extra="" if self.std_extended.get() else " AND COALESCE(is_selectable,1)=1"
        rows=self.db.fetchall("SELECT * FROM standards WHERE (code LIKE ? OR title LIKE ? OR area LIKE ?)"+extra+" ORDER BY code",(q,q,q))
        for x in self.std_catalog.get_children():self.std_catalog.delete(x)
        for r in rows:self.std_catalog.insert('','end',iid=str(r['id']),values=(r['code'],r['title'],r['status']))
    def refresh_revision_standards(self):
        if hasattr(self,'revstd_tree'):
            for x in self.revstd_tree.get_children():self.revstd_tree.delete(x)
            for i,r in enumerate(self.rev_standards):self.revstd_tree.insert('','end',iid=str(i),values=(r.get('code_snapshot',''),r.get('title_snapshot',''),r.get('status_snapshot',''),display_date(r.get('verified_on_snapshot',''))))
        if hasattr(self,'norm_summary_var'):
            codes=[(r.get('code_snapshot') or '').strip() for r in self.rev_standards if (r.get('code_snapshot') or '').strip()]
            self.norm_summary_var.set(', '.join(codes) if codes else 'Normy / předpisy nejsou zatím vybrány.')
    def _ensure_external_standards(self):
        """Jednorázově předvyplní všechny normy a předpisy použité ve vzorovém VV protokolu."""
        if str(self.special.get('reference_standards_seeded','') or '')=='1':
            return
        existing={(r.get('code_snapshot') or '').strip().lower() for r in self.rev_standards}
        for code,title in EXTERNAL_REFERENCE_STANDARDS:
            if code.strip().lower() in existing:
                continue
            # Pokus o dohledání katalogového záznamu podle základního označení.
            base=re.sub(r'\s+ed\.?\s*\d+.*$','',code,flags=re.I).strip()
            row=self.db.fetchone("SELECT * FROM standards WHERE code LIKE ? ORDER BY COALESCE(is_current,0) DESC,id DESC LIMIT 1",(base+'%',))
            if row:
                rr=dict(row)
                self.rev_standards.append({
                    'standard_id':rr.get('id'),'code_snapshot':code,'title_snapshot':title or rr.get('title') or '',
                    'status_snapshot':rr.get('status') or 'Převzato ze vzorového protokolu',
                    'verified_on_snapshot':rr.get('verified_on') or '', 'article_text':'',
                    'note':'Předvyplněno podle uživatelem dodaného vzorového protokolu VV; před finálním vydáním ověřit aktuálnost.',
                    'sort_order':len(self.rev_standards),
                })
            else:
                self.rev_standards.append({
                    'standard_id':None,'code_snapshot':code,'title_snapshot':title,
                    'status_snapshot':'Převzato ze vzorového protokolu','verified_on_snapshot':'','article_text':'',
                    'note':'Před finálním vydáním ověřit aktuálnost.','sort_order':len(self.rev_standards),
                })
            existing.add(code.strip().lower())
        self.special['reference_standards_seeded']='1'
        self.refresh_revision_standards()

    def add_standard_to_revision(self):
        s=self.std_catalog.selection()
        if not s:return
        sid=int(s[0]);r=dict(self.db.fetchone('SELECT * FROM standards WHERE id=?',(sid,)))
        if not r.get('is_selectable',1) and not messagebox.askyesno('Historická / neověřená norma',f"{r.get('code','')} není ověřena jako aktuálně platná.\n\nPoužít ji přesto pro tuto revizi?"):
            return
        if any(x.get('standard_id')==sid or x.get('code_snapshot')==r.get('code') for x in self.rev_standards):return
        self.rev_standards.append({'standard_id':sid,'code_snapshot':r.get('code',''),'title_snapshot':r.get('title',''),'status_snapshot':r.get('status',''),'verified_on_snapshot':r.get('verified_on',''),'article_text':'','note':''});self.refresh_revision_standards()
    def add_manual_standard(self):
        fields=[('code_snapshot','Norma / předpis'),('title_snapshot','Název'),('status_snapshot','Stav'),('verified_on_snapshot','Ověřeno dne'),('article_text','Článek / rozsah použití'),('note','Poznámka','text')]
        d=FormDialog(self,'Ručně přidat normu / předpis',fields,{'status_snapshot':'Ručně zadáno'},width=780,height=620);self.wait_window(d)
        if d.result and d.result.get('code_snapshot','').strip():
            d.result['standard_id']=None;self.rev_standards.append(d.result);self.refresh_revision_standards()

    def edit_revision_standard(self):
        s=self.revstd_tree.selection()
        if not s:return
        idx=int(s[0]);r=self.rev_standards[idx]
        fields=[('code_snapshot','Norma / předpis'),('title_snapshot','Název'),('status_snapshot','Stav při vložení'),('verified_on_snapshot','Ověřeno dne'),('article_text','Článek / rozsah použití'),('note','Poznámka','text')]
        d=FormDialog(self,'Upravit normu v této revizi',fields,r,width=780,height=620);self.wait_window(d)
        if d.result:self.rev_standards[idx].update(d.result);self.refresh_revision_standards()

    def delete_revision_standard(self):
        s=self.revstd_tree.selection()
        if s:self.rev_standards.pop(int(s[0]));self.refresh_revision_standards()

    def _build_text_tab(self,parent,key):
        t=tk.Text(parent,font=("Segoe UI",10),wrap='word',undo=True,padx=12,pady=12);t.pack(fill='both',expand=True,padx=8,pady=8);self.texts[key]=t

    def _build_measurements(self):
        if self.revision_type == 'VNEJSI':
            tb=ttk.Frame(self.tab_meas);tb.pack(fill='x',padx=8,pady=(8,4))
            ttk.Button(tb,text='+ Místnost / checklist',style='Accent.TButton',command=self.external_add_room).pack(side='left')
            ttk.Button(tb,text='Upravit',command=self.external_edit_room).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='Kopírovat místnost',command=self.external_duplicate_room).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='Smazat',style='Danger.TButton',command=self.measure_delete).pack(side='left',padx=(8,0))
            ttk.Separator(tb,orient='vertical').pack(side='left',fill='y',padx=9)
            ttk.Button(tb,text='Doplnit doplňková opatření',command=self.external_apply_suggestions).pack(side='left')
            ttk.Separator(tb,orient='vertical').pack(side='left',fill='y',padx=9)
            ttk.Button(tb,text='Import XLSX',command=self.external_import_xlsx).pack(side='left')
            ttk.Button(tb,text='Export XLSX',command=self.external_export_xlsx).pack(side='left',padx=(5,0))
            info=tk.Frame(self.tab_meas,bg='#F7FAFE',highlightbackground='#C9D8E8',highlightthickness=1);info.pack(fill='x',padx=8,pady=(0,5))
            tk.Label(info,text=f'{EXTERNAL_STANDARD_CODE}  •  místnost se zadává checklistem; pod tabulkou je vždy podrobné vysvětlení vybraných vlivů',bg='#F7FAFE',fg=COLORS['text'],font=('Segoe UI Semibold',9),anchor='w').pack(fill='x',padx=9,pady=(6,1))
            tk.Label(info,text='Horní tabulka je přehled místností. Dolní velká tabulka ukazuje kompletní vybrané VV. Opatření lze upravit pro každý abnormální VV; místnost lze kopírovat (Ctrl+D) a její VV uložit jako vlastní rychlý profil.',bg='#F7FAFE',fg=COLORS['muted'],font=('Segoe UI',8),anchor='w',justify='left',wraplength=1400).pack(fill='x',padx=9,pady=(0,6))
            self.external_summary_var=tk.StringVar(value='')
            tk.Label(self.tab_meas,textvariable=self.external_summary_var,bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9),anchor='w').pack(fill='x',padx=10,pady=(0,4))

            pan=tk.PanedWindow(self.tab_meas,orient='vertical',sashwidth=6,bg=COLORS['line']);pan.pack(fill='both',expand=True,padx=8,pady=(0,8))
            upper=tk.Frame(pan,bg='white');lower=tk.Frame(pan,bg='white');pan.add(upper,minsize=210);pan.add(lower,minsize=330)

            cols=[('floor','Podlaží',95),('room_no','Č.m.',90),('room_name','Název místnosti / prostoru',330),('environment_class','Prostředí',135),('abnormal','Rozhodující / abnormální VV',280),('measure_codes','Dopl. opatření',110),('state','Stav',155)]
            self.meas_tree=ttk.Treeview(upper,columns=[x[0] for x in cols],show='headings',height=9)
            for k,l,w in cols:
                self.meas_tree.heading(k,text=l,anchor='w');self.meas_tree.column(k,width=w,minwidth=max(70,min(w,120)),anchor='w',stretch=(k in ('room_name','abnormal')))
            self.meas_tree.tag_configure('warn',background='#FFF4E5');self.meas_tree.tag_configure('missing',background='#FBE6E8')
            ys=ttk.Scrollbar(upper,orient='vertical',command=self.meas_tree.yview);xs=ttk.Scrollbar(upper,orient='horizontal',command=self.meas_tree.xview);self.meas_tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
            self.meas_tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');upper.rowconfigure(0,weight=1);upper.columnconfigure(0,weight=1)
            self.meas_tree.bind('<Double-1>',lambda e:self.external_edit_room());self.meas_tree.bind('<<TreeviewSelect>>',self.refresh_external_detail)

            dh=tk.Frame(lower,bg='white');dh.pack(fill='x',padx=8,pady=(8,4))
            self.external_detail_title_var=tk.StringVar(value='Detail vybraného prostoru')
            tk.Label(dh,textvariable=self.external_detail_title_var,bg='white',fg=COLORS['text'],font=('Segoe UI Semibold',10),anchor='w').pack(side='left')
            tk.Label(dh,text='Výklad je pracovní pomůcka podle nahraného podkladu; rozhodnutí zůstává na zpracovateli protokolu.',bg='white',fg=COLORS['muted'],font=('Segoe UI',8),anchor='e').pack(side='right')
            dcols=[('group','Vnější vliv',205),('characteristic','Popis / charakteristika',360),('code','Označení',100),('normality','Zařazení',115),('requirement','Požadavek / opatření',500),('source','Zdroj',150)]
            dhold=ttk.Frame(lower);dhold.pack(fill='both',expand=True,padx=8,pady=(0,8))
            self.external_detail_tree=ttk.Treeview(dhold,columns=[x[0] for x in dcols],show='headings',height=14)
            for k,l,w in dcols:
                self.external_detail_tree.heading(k,text=l,anchor='w');self.external_detail_tree.column(k,width=w,minwidth=max(80,min(w,150)),anchor='w',stretch=(k in ('characteristic','requirement')))
            self.external_detail_tree.tag_configure('abnormal',background='#FFF4E5');self.external_detail_tree.tag_configure('missing',background='#FBE6E8')
            dys=ttk.Scrollbar(dhold,orient='vertical',command=self.external_detail_tree.yview);dxs=ttk.Scrollbar(dhold,orient='horizontal',command=self.external_detail_tree.xview);self.external_detail_tree.configure(yscrollcommand=dys.set,xscrollcommand=dxs.set)
            self.external_detail_tree.grid(row=0,column=0,sticky='nsew');dys.grid(row=0,column=1,sticky='ns');dxs.grid(row=1,column=0,sticky='ew');dhold.rowconfigure(0,weight=1);dhold.columnconfigure(0,weight=1)
        elif self.revision_type == 'ELEKTRO':
            mnb=ttk.Notebook(self.tab_meas);mnb.pack(fill='both',expand=True,padx=8,pady=8)
            circuits_tab=ttk.Frame(mnb);var_tab=ttk.Frame(mnb)
            mnb.add(circuits_tab,text='Struktura měření')
            mnb.add(var_tab,text='SPD / varistory')
            tb=ttk.Frame(circuits_tab);tb.pack(fill='x',padx=4,pady=6)
            ttk.Button(tb,text='+ RCD / RCBO',style='Accent.TButton',command=self.measure_add_rcd).pack(side='left')
            ttk.Button(tb,text='+ Obvod',style='Accent.TButton',command=self.measure_add).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='+ Měření',command=self.measure_add_point).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='+ Spojitost',command=self.measure_add_continuity).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='+ Poznámka',command=self.measure_add_note).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='+ Prázdný řádek',command=self.measure_add_blank).pack(side='left',padx=(5,0))
            ttk.Separator(tb,orient='vertical').pack(side='left',fill='y',padx=8)
            ttk.Button(tb,text='Upravit',command=self.measure_edit).pack(side='left')
            ttk.Button(tb,text='Hromadná editace',command=self.measure_bulk_edit).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='↑',width=3,command=lambda:self.measure_move(-1)).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='↓',width=3,command=lambda:self.measure_move(1)).pack(side='left',padx=(2,0))
            ttk.Button(tb,text='Smazat',style='Danger.TButton',command=self.measure_delete).pack(side='left',padx=(8,0))
            tk.Label(circuits_tab,text='RCD může tvořit nadřazenou položku. Kombinovaný chránič RCBO eviduje také jištění, impedanci a izolační odpor. Tlačítko + Měření otevře jedno kompletní zadání pro PE, PEN, N a měření mezi fázemi.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9),anchor='w').pack(fill='x',padx=6,pady=(0,5))
            cols=[('designation','Označení',150),('name','Popis / typ',240),('breaker','Jištění',180),('cable','Kabel',160),('u','U',90),('riso','Riso / Rp',130),('zsik','Zs / Ik',260),('result','Výsledek',120)]
            holder=ttk.Frame(circuits_tab);holder.pack(fill='both',expand=True,padx=4,pady=(0,6))
            self.meas_tree=ttk.Treeview(holder,columns=[x[0] for x in cols],show='headings')
            for k,l,w in cols:
                self.meas_tree.heading(k,text=l,anchor='w');self.meas_tree.column(k,width=w,minwidth=w,anchor='w',stretch=False)
            self.meas_tree.tag_configure('RCD',font=('Segoe UI Semibold',9),background='#EDF4FF')
            self.meas_tree.tag_configure('CONTINUITY',font=('Segoe UI Semibold',9),background='#F2F8F3')
            self.meas_tree.tag_configure('POINT',background='#FFF8E8')
            self.meas_tree.tag_configure('NOTE',font=('Segoe UI Semibold',9),background='#F7F7F7')
            self.meas_tree.tag_configure('BLANK',background='#FAFAFA')
            ys=ttk.Scrollbar(holder,orient='vertical',command=self.meas_tree.yview);xs=ttk.Scrollbar(holder,orient='horizontal',command=self.meas_tree.xview);self.meas_tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
            self.meas_tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1);self.meas_tree.bind('<Double-1>',lambda e:self.measure_edit())

            vtb=ttk.Frame(var_tab);vtb.pack(fill='x',padx=4,pady=6)
            tk.Label(vtb,text='Samostatné záznamy měření přepěťových ochran / varistorů. Vyhodnocení zůstává na RT.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9)).pack(side='left')
            ttk.Button(vtb,text='Přidat měření',style='Accent.TButton',command=self.varistor_add).pack(side='right')
            ttk.Button(vtb,text='Upravit',command=self.varistor_edit).pack(side='right',padx=5)
            ttk.Button(vtb,text='Smazat',style='Danger.TButton',command=self.varistor_delete).pack(side='right')
            vh=ttk.Frame(var_tab);vh.pack(fill='both',expand=True,padx=4,pady=(0,6))
            self.var_tree=ttk.Treeview(vh,columns=[x[0] for x in VARISTOR_TREE],show='headings')
            for k,l,w in VARISTOR_TREE:self.var_tree.heading(k,text=l);self.var_tree.column(k,width=w,anchor='w')
            vys=ttk.Scrollbar(vh,orient='vertical',command=self.var_tree.yview);vxs=ttk.Scrollbar(vh,orient='horizontal',command=self.var_tree.xview);self.var_tree.configure(yscrollcommand=vys.set,xscrollcommand=vxs.set)
            self.var_tree.grid(row=0,column=0,sticky='nsew');vys.grid(row=0,column=1,sticky='ns');vxs.grid(row=1,column=0,sticky='ew');vh.rowconfigure(0,weight=1);vh.columnconfigure(0,weight=1);self.var_tree.bind('<Double-1>',lambda e:self.varistor_edit())
        elif self.revision_type=='STROJ':
            tb=ttk.Frame(self.tab_meas);tb.pack(fill='x',padx=8,pady=(8,3))
            ttk.Button(tb,text='+ Skupina',style='Accent.TButton',command=self.machine_add_group).pack(side='left')
            ttk.Button(tb,text='Předvyplnit základní strukturu',command=self.machine_add_default_structure).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='+ Obecné měření',command=lambda:self.machine_add_item('MEASUREMENT')).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='+ Funkční zkouška',command=lambda:self.machine_add_item('FUNCTION')).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='+ Poznámka',command=self.machine_add_note).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='+ Prázdný řádek',command=self.machine_add_blank).pack(side='left',padx=(5,0))
            ttk.Separator(tb,orient='vertical').pack(side='left',fill='y',padx=8)
            ttk.Button(tb,text='Upravit',command=self.measure_edit).pack(side='left')
            ttk.Button(tb,text='↑',width=3,command=lambda:self.measure_move(-1)).pack(side='left',padx=(5,0))
            ttk.Button(tb,text='↓',width=3,command=lambda:self.measure_move(1)).pack(side='left',padx=(2,0))
            ttk.Button(tb,text='Smazat',style='Danger.TButton',command=self.measure_delete).pack(side='left',padx=(8,0))
            classic=ttk.Frame(self.tab_meas);classic.pack(fill='x',padx=8,pady=(0,5))
            ttk.Label(classic,text='Klasické elektrické měření:').pack(side='left',padx=(0,6))
            ttk.Button(classic,text='+ Obvod',style='Accent.TButton',command=self.machine_add_classic_circuit).pack(side='left')
            ttk.Button(classic,text='+ Měřicí bod',command=self.machine_add_classic_point).pack(side='left',padx=(5,0))
            ttk.Button(classic,text='+ Spojitost',command=self.machine_add_classic_continuity).pack(side='left',padx=(5,0))
            ttk.Button(classic,text='+ RCD / RCBO',command=self.machine_add_classic_rcd).pack(side='left',padx=(5,0))
            tk.Label(self.tab_meas,text='Doporučená struktura: Přívod / hlavní vypínač -> rozvaděč -> ochranný obvod -> pohony a řídicí obvody -> funkční zkoušky. K dispozici jsou i klasické obvody, Zs, Riso, spojitost a RCD/RCBO stejně jako u EI.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9),anchor='w').pack(fill='x',padx=10,pady=(0,5))
            cols=MEASUREMENT_TREE['STROJ'];holder=ttk.Frame(self.tab_meas);holder.pack(fill='both',expand=True,padx=8,pady=(0,8))
            self.meas_tree=ttk.Treeview(holder,columns=[x[0] for x in cols],show='tree headings')
            self.meas_tree.heading('#0',text='Struktura');self.meas_tree.column('#0',width=145,anchor='w',stretch=False)
            for k,l,w in cols:self.meas_tree.heading(k,text=l);self.meas_tree.column(k,width=w,anchor='w')
            self.meas_tree.tag_configure('GROUP',font=('Segoe UI Semibold',9),background='#EDF4FF')
            self.meas_tree.tag_configure('FUNCTION',background='#F2F8F3')
            for _tag in ('CIRCUIT','POINT','CONTINUITY','RCD'):self.meas_tree.tag_configure(_tag,background='#F8FBFF')
            self.meas_tree.tag_configure('NOTE',font=('Segoe UI Semibold',9),background='#F7F7F7')
            self.meas_tree.tag_configure('BLANK',background='#FAFAFA')
            ys=ttk.Scrollbar(holder,orient='vertical',command=self.meas_tree.yview);xs=ttk.Scrollbar(holder,orient='horizontal',command=self.meas_tree.xview);self.meas_tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
            self.meas_tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1);self.meas_tree.bind('<Double-1>',lambda e:self.measure_edit())
        else:
            tb=ttk.Frame(self.tab_meas);tb.pack(fill='x',padx=8,pady=8)
            ttk.Button(tb,text="Přidat",style="Accent.TButton",command=self.measure_add).pack(side='left');ttk.Button(tb,text="Upravit",command=self.measure_edit).pack(side='left',padx=5);ttk.Button(tb,text="Smazat",style="Danger.TButton",command=self.measure_delete).pack(side='left')
            cols=MEASUREMENT_TREE[self.revision_type];holder=ttk.Frame(self.tab_meas);holder.pack(fill='both',expand=True,padx=8,pady=(0,8))
            self.meas_tree=ttk.Treeview(holder,columns=[x[0] for x in cols],show='headings')
            for k,l,w in cols:self.meas_tree.heading(k,text=l);self.meas_tree.column(k,width=w,anchor='w')
            ys=ttk.Scrollbar(holder,orient='vertical',command=self.meas_tree.yview);xs=ttk.Scrollbar(holder,orient='horizontal',command=self.meas_tree.xview);self.meas_tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
            self.meas_tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1);self.meas_tree.bind('<Double-1>',lambda e:self.measure_edit())

    def _build_defects(self):
        pan=tk.PanedWindow(self.tab_defects,orient='horizontal',sashwidth=5,bg=COLORS['line']);pan.pack(fill='both',expand=True,padx=8,pady=8)
        left=tk.Frame(pan,bg='white');right=tk.Frame(pan,bg='white');pan.add(left,minsize=450);pan.add(right,minsize=450)
        top=tk.Frame(left,bg='white');top.pack(fill='x',padx=8,pady=8);tk.Label(top,text="Závadovník",bg='white',font=("Segoe UI Semibold",10)).pack(side='left');self.def_search=tk.StringVar();ttk.Entry(top,textvariable=self.def_search,width=24).pack(side='right');self.def_search.trace_add('write',lambda *a:self.refresh_catalog())
        self.catalog_tree=ttk.Treeview(left,columns=('standard','article','title'),show='headings');
        for k,l,w in [('standard','Norma',150),('article','Článek',100),('title','Závada',260)]:self.catalog_tree.heading(k,text=l);self.catalog_tree.column(k,width=w,anchor='w')
        self.catalog_tree.pack(fill='both',expand=True,padx=8,pady=(0,8));self.catalog_tree.bind('<Double-1>',lambda e:self.add_catalog_defect());ttk.Button(left,text="Přidat do revize →",style="Accent.TButton",command=self.add_catalog_defect).pack(anchor='e',padx=8,pady=(0,8))
        top=tk.Frame(right,bg='white');top.pack(fill='x',padx=8,pady=8);tk.Label(top,text="Závady v této revizi",bg='white',font=("Segoe UI Semibold",10)).pack(side='left');ttk.Button(top,text="Vlastní závada + fotografie",command=self.add_custom_defect).pack(side='right')
        self.revdef_tree=ttk.Treeview(right,columns=('defect','norm','severity','status','photos'),show='headings');
        for k,l,w in [('defect','Závada',300),('norm','Norma / čl.',180),('severity','Závažnost',85),('status','Stav',105),('photos','Fotky',55)]:self.revdef_tree.heading(k,text=l);self.revdef_tree.column(k,width=w,anchor='center' if k=='severity' else 'w')
        self.revdef_tree.pack(fill='both',expand=True,padx=8,pady=(0,4));self.revdef_tree.bind('<Double-1>',lambda e:self.edit_revision_defect())
        tk.Label(right,text='C1 – Nebezpečný stav   •   C2 – Potenciálně nebezpečný stav   •   C3 – doporučení',bg='white',fg=COLORS['muted'],font=('Segoe UI',8),anchor='w',justify='left').pack(fill='x',padx=8,pady=(0,8))
        foot=ttk.Frame(right);foot.pack(fill='x',padx=8,pady=(0,8));ttk.Button(foot,text="Upravit / fotografie",command=self.edit_revision_defect).pack(side='right',padx=5);ttk.Button(foot,text="Odebrat",style="Danger.TButton",command=self.delete_revision_defect).pack(side='right')

    def _build_references(self):
        top=ttk.Frame(self.tab_refs);top.pack(fill='x',padx=10,pady=10)
        if self.revision_type=='VNEJSI':
            tk.Label(top,text="K protokolu přilož podklady použité pro určení vnějších vlivů – např. půdorysy, PBŘ, technické zprávy, původní protokol nebo technologické podklady. Soubor se při uložení zkopíruje do dat PZ-REVIZE.",bg=COLORS['bg'],fg=COLORS['muted'],font=("Segoe UI",9),justify='left',wraplength=1150).pack(side='left',fill='x',expand=True)
            ttk.Button(top,text="Přidat podklad / přílohu",style='Accent.TButton',command=lambda:self.add_reference('Podklad protokolu VV')).pack(side='right',padx=4)
        else:
            tk.Label(top,text="K revizi lze přiložit cizí revizní zprávu nebo jiný dokument jako pracovní podklad. Soubor se při uložení zkopíruje do dat PZ-REVIZE.",bg=COLORS['bg'],fg=COLORS['muted'],font=("Segoe UI",9),justify='left').pack(side='left',fill='x',expand=True)
            ttk.Button(top,text="Nahrát cizí revizní zprávu",style='Accent.TButton',command=lambda:self.add_reference('Cizí revizní zpráva')).pack(side='right',padx=4)
            ttk.Button(top,text="Jiný podklad",command=lambda:self.add_reference('Jiný podklad')).pack(side='right',padx=4)
        holder=ttk.Frame(self.tab_refs);holder.pack(fill='both',expand=True,padx=10,pady=(0,8))
        cols=[('category','Typ',170),('title','Název',260),('file','Soubor',300),('note','Poznámka',300)]
        self.ref_tree=ttk.Treeview(holder,columns=[x[0] for x in cols],show='headings')
        for k,l,w in cols:self.ref_tree.heading(k,text=l);self.ref_tree.column(k,width=w,anchor='w')
        ys=ttk.Scrollbar(holder,orient='vertical',command=self.ref_tree.yview);xs=ttk.Scrollbar(holder,orient='horizontal',command=self.ref_tree.xview);self.ref_tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        self.ref_tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
        self.ref_tree.bind('<Double-1>',lambda e:self.open_reference())
        foot=ttk.Frame(self.tab_refs);foot.pack(fill='x',padx=10,pady=(0,10));ttk.Button(foot,text='Otevřít',style='Success.TButton',command=self.open_reference).pack(side='right',padx=4);ttk.Button(foot,text='Odebrat',style='Danger.TButton',command=self.delete_reference).pack(side='right',padx=4)

    def add_reference(self, category):
        path=filedialog.askopenfilename(title='Vybrat podklad',filetypes=[('Podklady','*.pdf *.doc *.docx *.odt *.xls *.xlsx *.jpg *.jpeg *.png *.webp'),('Všechny soubory','*.*')])
        if not path:return
        fields=[('title','Název podkladu'),('note','Poznámka','text')]
        d=FormDialog(self,'Podklad revize',fields,{'title':Path(path).stem},width=620,height=430);self.wait_window(d)
        if not d.result:return
        self.attachments.append({'category':category,'title':d.result['title'] or Path(path).stem,'original_name':Path(path).name,'stored_path':'','source_path':path,'note':d.result['note']})
        self.refresh_references()

    def refresh_references(self):
        if not hasattr(self,'ref_tree'):return
        for x in self.ref_tree.get_children():self.ref_tree.delete(x)
        for i,a in enumerate(self.attachments):self.ref_tree.insert('','end',iid=str(i),values=(a.get('category',''),a.get('title',''),a.get('original_name') or Path(a.get('stored_path') or a.get('source_path') or '').name,a.get('note','')))
        if hasattr(self,'appendix_tree'):self.refresh_appendix_preview()

    def open_reference(self):
        s=self.ref_tree.selection()
        if not s:return
        a=self.attachments[int(s[0])]; path=a.get('stored_path') or a.get('source_path')
        if not path or not Path(path).exists():messagebox.showwarning('Podklad','Soubor nebyl nalezen.');return
        try:
            if os.name=='nt': os.startfile(path)
            elif sys.platform=='darwin': subprocess.Popen(['open',path])
            else: subprocess.Popen(['xdg-open',path])
        except Exception as e:messagebox.showerror('Podklad',str(e))

    def delete_reference(self):
        s=self.ref_tree.selection()
        if s and messagebox.askyesno('Odebrat podklad','Odebrat podklad z této revize? Původní cizí soubor se nemaže.'):
            self.attachments.pop(int(s[0]));self.refresh_references()

    def _build_instruments(self):
        tk.Label(self.tab_instr,text="Vyber měřicí přístroje použité při revizi. Výběr zůstává zachován i po přepnutí na jinou záložku.",bg=COLORS['bg'],fg=COLORS['muted'],font=("Segoe UI",9)).pack(anchor='w',padx=12,pady=(12,6))
        self.instrument_list=tk.Listbox(self.tab_instr,selectmode='multiple',exportselection=False,font=("Segoe UI",10),activestyle='none',height=15);self.instrument_list.pack(fill='both',expand=True,padx=12,pady=6);self.instrument_rows=self.db.fetchall("SELECT * FROM instruments WHERE active=1 ORDER BY name")
        for r in self.instrument_rows:self.instrument_list.insert('end',f"{r['name']}  |  {r['manufacturer'] or ''} {r['model'] or ''}  |  v.č. {r['serial_no'] or ''}  |  kal. do {display_date(r['calibration_due'])}")
        foot=ttk.Frame(self.tab_instr);foot.pack(fill='x',padx=12,pady=(0,12))
        ttk.Button(foot,text="Vybrat vše",command=lambda:self.instrument_list.selection_set(0,'end')).pack(side='left')
        ttk.Button(foot,text="Zrušit výběr",command=lambda:self.instrument_list.selection_clear(0,'end')).pack(side='left',padx=6)
        ttk.Button(foot,text="Spravovat přístroje",command=lambda:self.app.show_page('instruments')).pack(side='right')

    def _build_operator(self):
        top=ttk.Frame(self.tab_operator);top.pack(fill='x',padx=10,pady=(10,5))
        title=operator_instruction_title(self.revision_type)
        tk.Label(top,text=title,bg=COLORS['bg'],fg=COLORS['text'],font=('Segoe UI Semibold',11)).pack(side='left')
        tk.Label(top,text='  -  výchozí text je podle typu revize předvyplněn a v každé revizi jej lze libovolně upravit',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',9)).pack(side='left')
        pan=tk.PanedWindow(self.tab_operator,orient='horizontal',sashwidth=5,bg=COLORS['line']);pan.pack(fill='both',expand=True,padx=10,pady=5)
        left=tk.Frame(pan,bg='white');right=tk.Frame(pan,bg='white');pan.add(left,minsize=390);pan.add(right,minsize=760)

        lh=tk.Frame(left,bg='white');lh.pack(fill='x',padx=8,pady=8)
        tk.Label(lh,text='Šablony poučení',bg='white',font=('Segoe UI Semibold',10)).pack(side='left')
        tk.Label(left,text=f'Výchozí šablona: {title}',bg='white',fg=COLORS['muted'],font=('Segoe UI',8),wraplength=360,justify='left').pack(fill='x',padx=8,pady=(0,6))
        self.operator_library=tk.Listbox(left,selectmode='browse',exportselection=False,font=('Segoe UI',9),activestyle='none');self.operator_library.pack(fill='both',expand=True,padx=8,pady=(0,6));self.operator_library.bind('<Double-1>',lambda e:self.load_selected_operator_template())
        lf=ttk.Frame(left);lf.pack(fill='x',padx=8,pady=(0,8))
        ttk.Button(lf,text='Načíst vybranou šablonu →',style='Accent.TButton',command=self.load_selected_operator_template).pack(side='right')
        ttk.Button(lf,text='Obnovit výchozí',command=self.load_default_operator_instruction).pack(side='left')

        rh=tk.Frame(right,bg='white');rh.pack(fill='x',padx=8,pady=8)
        tk.Label(rh,text='Text poučení v této revizi',bg='white',font=('Segoe UI Semibold',10)).pack(side='left')
        tk.Label(rh,text='Ukládá se přímo k této revizní zprávě.',bg='white',fg=COLORS['muted'],font=('Segoe UI',8)).pack(side='right')
        t=tk.Text(right,height=20,font=('Segoe UI',10),wrap='word',undo=True,padx=12,pady=10);t.pack(fill='both',expand=True,padx=8,pady=(0,6));self.texts['operator_instruction']=t
        rf=ttk.Frame(right);rf.pack(fill='x',padx=8,pady=(0,8))
        ttk.Button(rf,text='Uložit celý text jako vlastní šablonu',command=self.learn_operator_instruction).pack(side='right')
        ttk.Button(rf,text='Vymazat',command=lambda:t.delete('1.0','end')).pack(side='right',padx=5)

        attachments_box=ttk.LabelFrame(self.tab_operator,text='Seznam příloh ve zprávě');attachments_box.pack(fill='x',padx=10,pady=(5,10))
        self.appendix_tree=ttk.Treeview(attachments_box,columns=('n','category','title','file'),show='headings',height=4)
        for k,l,w in [('n','#',45),('category','Druh',180),('title','Název',430),('file','Soubor / počet',360)]:self.appendix_tree.heading(k,text=l);self.appendix_tree.column(k,width=w,anchor='w')
        self.appendix_tree.pack(fill='x',expand=True,padx=6,pady=6)
        foot=ttk.Frame(attachments_box);foot.pack(fill='x',padx=6,pady=(0,6));tk.Label(foot,text='Seznam vzniká automaticky z Podklady / přílohy a z fotodokumentace závad.',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',8)).pack(side='left');ttk.Button(foot,text='Obnovit seznam',command=self.refresh_appendix_preview).pack(side='right')
        self.refresh_operator_library();self.refresh_appendix_preview()

    def _operator_template_category(self):
        return f"operator_instruction_{self.revision_type}"

    def refresh_operator_library(self):
        if not hasattr(self,'operator_library'):return
        self.operator_library.delete(0,'end')
        self.operator_library_rows=[{'value':operator_instruction_template(self.revision_type),'builtin':True,'label':'Výchozí šablona programu'}]
        seen={self.operator_library_rows[0]['value'].strip()}
        for r in self.db.learned_values(self._operator_template_category(),100):
            value=(r['value'] or '').strip()
            if value and value not in seen:
                seen.add(value);self.operator_library_rows.append({'value':value,'builtin':False,'label':'Vlastní uložená šablona'})
        # Backward compatibility: old generic full-text templates remain available.
        for r in self.db.learned_values('operator_instruction',40):
            value=(r['value'] or '').strip()
            if value and '\n' in value and value not in seen:
                seen.add(value);self.operator_library_rows.append({'value':value,'builtin':False,'label':'Starší uložená šablona'})
        for i,r in enumerate(self.operator_library_rows,1):
            value=(r.get('value') or '').strip().replace('\n',' ')
            preview=value if len(value)<=105 else value[:102]+'...'
            self.operator_library.insert('end',f"{r.get('label','Šablona')}  |  {preview}")
        if self.operator_library_rows:self.operator_library.selection_set(0)

    def load_selected_operator_template(self):
        if not hasattr(self,'operator_library'):return
        sel=self.operator_library.curselection()
        if not sel:return
        value=(self.operator_library_rows[sel[0]].get('value') or '').strip()
        if not value:return
        current=self.texts['operator_instruction'].get('1.0','end').strip()
        if current and current!=value and not messagebox.askyesno('Poučení','Nahradit současný text vybranou šablonou?'):return
        self.texts['operator_instruction'].delete('1.0','end');self.texts['operator_instruction'].insert('1.0',value)

    def load_default_operator_instruction(self):
        value=operator_instruction_template(self.revision_type)
        current=self.texts['operator_instruction'].get('1.0','end').strip()
        if current and current!=value and not messagebox.askyesno('Poučení','Obnovit výchozí poučení pro tento typ revizní zprávy? Současný text bude nahrazen.'):return
        self.texts['operator_instruction'].delete('1.0','end');self.texts['operator_instruction'].insert('1.0',value)

    def learn_operator_instruction(self):
        txt=self.texts['operator_instruction'].get('1.0','end').strip()
        if not txt:messagebox.showinfo('Poučení','Text poučení je prázdný.');return
        self.db.learn_value(self._operator_template_category(),txt);self.refresh_operator_library();messagebox.showinfo('Poučení','Text byl uložen jako vlastní šablona pro tento typ revize.')

    def refresh_appendix_preview(self):
        if not hasattr(self,'appendix_tree'):return
        for x in self.appendix_tree.get_children():self.appendix_tree.delete(x)
        rows=[];photo_count=sum(len(d.get('_photos') or []) for d in self.rev_defects)
        if photo_count:rows.append(('Fotodokumentace','Fotodokumentace závad',f'{photo_count} foto'))
        for a in self.attachments:
            rows.append((a.get('category') or 'Příloha',a.get('title') or a.get('original_name') or 'Příloha',a.get('original_name') or Path(a.get('stored_path') or a.get('source_path') or '').name))
        for i,(cat,title,file_text) in enumerate(rows,1):self.appendix_tree.insert('','end',iid=str(i),values=(i,cat,title,file_text))
        if not rows:self.appendix_tree.insert('','end',iid='none',values=('','-','Bez samostatných příloh',''))

    def _build_conclusion(self):
        top=ttk.Frame(self.tab_conclusion);top.pack(fill='x',padx=10,pady=(10,5))
        tk.Label(top,text="Vyhodnocení po jednotlivých bodech",bg=COLORS['bg'],fg=COLORS['text'],font=("Segoe UI Semibold",11)).pack(side='left')
        tk.Label(top,text="  -  bloky jsou editovatelné a nové formulace si program zapamatuje",bg=COLORS['bg'],fg=COLORS['muted'],font=("Segoe UI",9)).pack(side='left')
        pan=tk.PanedWindow(self.tab_conclusion,orient='horizontal',sashwidth=5,bg=COLORS['line']);pan.pack(fill='both',expand=True,padx=10,pady=5)
        left=tk.Frame(pan,bg='white');right=tk.Frame(pan,bg='white');pan.add(left,minsize=430);pan.add(right,minsize=560)
        lh=tk.Frame(left,bg='white');lh.pack(fill='x',padx=8,pady=8);tk.Label(lh,text='Naučené / přednastavené bloky',bg='white',font=('Segoe UI Semibold',10)).pack(side='left')
        self.conclusion_library=tk.Listbox(left,selectmode='extended',exportselection=False,font=('Segoe UI',9),activestyle='none');self.conclusion_library.pack(fill='both',expand=True,padx=8,pady=(0,6))
        self.conclusion_library.bind('<Double-1>',lambda e:self.add_conclusion_from_library())
        lf=ttk.Frame(left);lf.pack(fill='x',padx=8,pady=(0,8));ttk.Button(lf,text='Přidat vybrané →',style='Accent.TButton',command=self.add_conclusion_from_library).pack(side='right');ttk.Button(lf,text='Vlastní nový blok',command=self.add_custom_conclusion).pack(side='right',padx=5)
        rh=tk.Frame(right,bg='white');rh.pack(fill='x',padx=8,pady=8);tk.Label(rh,text='Body vyhodnocení v této revizi',bg='white',font=('Segoe UI Semibold',10)).pack(side='left')
        self.conclusion_tree=ttk.Treeview(right,columns=('n','text'),show='headings');self.conclusion_tree.heading('n',text='#');self.conclusion_tree.column('n',width=45,anchor='center');self.conclusion_tree.heading('text',text='Text bodu');self.conclusion_tree.column('text',width=650,anchor='w');self.conclusion_tree.pack(fill='both',expand=True,padx=8,pady=(0,6));self.conclusion_tree.bind('<Double-1>',lambda e:self.edit_conclusion_block())
        rf=ttk.Frame(right);rf.pack(fill='x',padx=8,pady=(0,8));ttk.Button(rf,text='Nahoru',command=lambda:self.move_conclusion(-1)).pack(side='left');ttk.Button(rf,text='Dolů',command=lambda:self.move_conclusion(1)).pack(side='left',padx=4);ttk.Button(rf,text='Upravit',command=self.edit_conclusion_block).pack(side='right',padx=4);ttk.Button(rf,text='Odebrat',style='Danger.TButton',command=self.delete_conclusion_block).pack(side='right')
        bottom=ttk.LabelFrame(self.tab_conclusion,text='Doplňující volný text závěru (nepovinné)');bottom.pack(fill='x',padx=10,pady=(5,10))
        t=tk.Text(bottom,height=5,font=("Segoe UI",10),wrap='word',undo=True,padx=10,pady=8);t.pack(fill='x',expand=True,padx=6,pady=6);self.texts['conclusion']=t
        fixed=tk.Frame(self.tab_conclusion,bg='#EEF8F0',highlightbackground='#B8DFC0',highlightthickness=1);fixed.pack(fill='x',padx=10,pady=(0,10))
        tk.Label(fixed,text='CELKOVÝ POSUDEK',bg='#EEF8F0',fg=COLORS['green_dark'],font=('Segoe UI Semibold',9)).pack(anchor='w',padx=10,pady=(8,1))
        tk.Label(fixed,text='ELEKTRICKÉ ZAŘÍZENÍ JE Z HLEDISKA BEZPEČNOSTI SCHOPNO PROVOZU',bg='#EEF8F0',fg=COLORS['text'],font=('Segoe UI Semibold',10)).pack(anchor='w',padx=10,pady=(1,8))
        self.refresh_conclusion_library();self.refresh_conclusion_blocks()

    def refresh_conclusion_library(self):
        if not hasattr(self,'conclusion_library'):return
        self.conclusion_library.delete(0,'end')
        self.conclusion_library_rows=[dict(r) for r in self.db.learned_values('conclusion_block',200)]
        for r in self.conclusion_library_rows:
            text=r.get('value','');self.conclusion_library.insert('end',text if len(text)<=150 else text[:147]+'...')

    def refresh_conclusion_blocks(self):
        if not hasattr(self,'conclusion_tree'):return
        for x in self.conclusion_tree.get_children():self.conclusion_tree.delete(x)
        for i,r in enumerate(self.conclusion_blocks):
            txt=r.get('text_snapshot') or r.get('text') or '';self.conclusion_tree.insert('','end',iid=str(i),values=(i+1,txt))

    def add_conclusion_from_library(self):
        if not hasattr(self,'conclusion_library'):return
        for idx in self.conclusion_library.curselection():
            text=self.conclusion_library_rows[idx].get('value','').strip()
            if text and not any((r.get('text_snapshot') or '')==text for r in self.conclusion_blocks):self.conclusion_blocks.append({'title':'','text_snapshot':text})
        self.refresh_conclusion_blocks()

    def add_custom_conclusion(self):
        d=FormDialog(self,'Nový bod vyhodnocení',[('title','Krátký název'),('text_snapshot','Text bodu','text')],width=760,height=480);self.wait_window(d)
        if d.result and d.result.get('text_snapshot','').strip():
            self.conclusion_blocks.append(d.result);self.db.learn_value('conclusion_block',d.result['text_snapshot']);self.refresh_conclusion_library();self.refresh_conclusion_blocks()

    def edit_conclusion_block(self):
        s=self.conclusion_tree.selection()
        if not s:return
        idx=int(s[0]);d=FormDialog(self,'Upravit bod vyhodnocení',[('title','Krátký název'),('text_snapshot','Text bodu','text')],self.conclusion_blocks[idx],width=760,height=480);self.wait_window(d)
        if d.result and d.result.get('text_snapshot','').strip():
            self.conclusion_blocks[idx].update(d.result);self.db.learn_value('conclusion_block',d.result['text_snapshot']);self.refresh_conclusion_library();self.refresh_conclusion_blocks()

    def delete_conclusion_block(self):
        s=self.conclusion_tree.selection()
        if s:self.conclusion_blocks.pop(int(s[0]));self.refresh_conclusion_blocks()

    def move_conclusion(self,delta):
        s=self.conclusion_tree.selection()
        if not s:return
        i=int(s[0]);j=i+delta
        if j<0 or j>=len(self.conclusion_blocks):return
        self.conclusion_blocks[i],self.conclusion_blocks[j]=self.conclusion_blocks[j],self.conclusion_blocks[i];self.refresh_conclusion_blocks();self.conclusion_tree.selection_set(str(j));self.conclusion_tree.see(str(j))

    def _populate(self):
        for key,t in self.texts.items():
            value=self.rev.get(key) or ''
            if key=='operator_instruction' and not value:
                value=operator_instruction_template(self.revision_type)
            t.insert('1.0',value)
        self.refresh_measurements();self.refresh_varistors();self.refresh_catalog();self.refresh_revision_defects();self.refresh_references();self.refresh_documents();self.refresh_revision_standards();self.refresh_power();self.refresh_selected_protections();self.refresh_inspection_items();self.refresh_working_photos();self.refresh_conclusion_blocks();self.refresh_operator_library();self.refresh_appendix_preview()
        for idx,r in enumerate(self.instrument_rows):
            if r['id'] in self.instrument_ids:self.instrument_list.selection_set(idx)

    def _selected_measurement_index(self):
        if not hasattr(self,'meas_tree'):return None
        sel=self.meas_tree.selection()
        if not sel:return None
        iid=sel[0]
        try:return int(iid[1:]) if iid.startswith('m') else int(iid)
        except Exception:return None

    def refresh_external_detail(self, event=None):
        if not hasattr(self,'external_detail_tree'):
            return
        for iid in self.external_detail_tree.get_children():
            self.external_detail_tree.delete(iid)
        sel=self.meas_tree.selection() if hasattr(self,'meas_tree') else ()
        if not sel:
            if hasattr(self,'external_detail_title_var'):
                self.external_detail_title_var.set('Detail vybraného prostoru')
            return
        try:
            idx=int(sel[0]);row=self.measurements[idx]
        except Exception:
            return
        label=' – '.join(x for x in [str(row.get('room_no','')).strip(),str(row.get('room_name','')).strip()] if x) or 'Vybraný prostor'
        if hasattr(self,'external_detail_title_var'):
            self.external_detail_title_var.set(f'Detail: {label}')
        values=external_parse_values(row.get('values_json'))
        custom_measure_by_code={x['code']:x.get('requirement','') for x in external_measure_entries(values,row.get('abnormal_measures_json'))}
        for group in EXTERNAL_COLUMNS:
            meta=EXTERNAL_META.get(group,{})
            group_name=f'{group} – {meta.get("name",group)}'
            tokens=ExternalRoomDialog._tokens_for(group,values.get(group,''))
            if not tokens:
                self.external_detail_tree.insert('','end',values=(group_name,'Nevyplněno','', 'K DOPLNĚNÍ','', ''),tags=('missing',))
                continue
            for token in tokens:
                if token=='---':
                    self.external_detail_tree.insert('','end',values=(group_name,'V daném prostoru se samostatně neuplatňuje','---','informativní','Bez samostatného kódu ve výstupu.','vzorový protokol'))
                    continue
                item=external_checklist_item(token)
                label_text=item.get('label','Hodnota není v pracovním číselníku.')
                abnormal=token in EXTERNAL_ABNORMAL_VALUES.get(group,set())
                requirement=custom_measure_by_code.get(token,item.get('requirement','Ověřit podle zdrojového dokumentu.'))
                source=item.get('source','')
                normality='ABNORMÁLNÍ' if abnormal else 'normální'
                self.external_detail_tree.insert('','end',values=(group_name,label_text,token,normality,requirement,source),tags=(('abnormal',) if abnormal else ()))

    def external_add_room(self):
        if self.revision_type!='VNEJSI':return
        initial=external_blank_room()
        idx=self._selected_measurement_index()
        if idx is not None and 0<=idx<len(self.measurements):
            initial['floor']=self.measurements[idx].get('floor','')
        d=ExternalRoomDialog(self,'Nová místnost – vnější vlivy',initial);self.wait_window(d)
        if d.result:
            d.result['sort_order']=len(self.measurements)+1
            self.measurements.append(d.result);self.refresh_measurements()

    def external_edit_room(self):
        if self.revision_type!='VNEJSI':return
        idx=self._selected_measurement_index()
        if idx is None or idx<0 or idx>=len(self.measurements):return
        old=dict(self.measurements[idx])
        d=ExternalRoomDialog(self,'Upravit místnost – vnější vlivy',old);self.wait_window(d)
        if d.result:
            d.result['sort_order']=old.get('sort_order') or idx+1
            d.result['source_sheet']=old.get('source_sheet','')
            self.measurements[idx]=d.result;self.refresh_measurements()
            if self.meas_tree.exists(str(idx)):self.meas_tree.selection_set(str(idx));self.meas_tree.see(str(idx))

    def external_duplicate_room(self):
        if self.revision_type!='VNEJSI':return
        idx=self._selected_measurement_index()
        if idx is None or idx<0 or idx>=len(self.measurements):return
        initial=dict(self.measurements[idx]);initial['room_no']='';initial['room_name']=(initial.get('room_name') or '')+' – kopie';initial['source_sheet']=''
        d=ExternalRoomDialog(self,'Duplikovat místnost – vnější vlivy',initial);self.wait_window(d)
        if d.result:
            d.result['sort_order']=len(self.measurements)+1;d.result['source_sheet']=''
            self.measurements.append(d.result);self.refresh_measurements()

    def external_apply_suggestions(self):
        if self.revision_type!='VNEJSI':return
        idx=self._selected_measurement_index()
        if idx is None or idx<0 or idx>=len(self.measurements):
            messagebox.showinfo('Vnější vlivy','Vyber místnost, pro kterou chceš doplnit návrh opatření.');return
        row=self.measurements[idx];values=external_parse_values(row.get('values_json'))
        proposed=external_suggest_measures(values,row.get('room_name',''))
        current=[x for x in external_normalize_measures(row.get('measure_codes','')).split(',') if x]
        added=[x for x in proposed if x not in current]
        if not added:
            messagebox.showinfo('Návrh opatření','Pro vybranou místnost není podle pomocných pravidel co doplnit. Odborné posouzení zůstává na zpracovateli protokolu.');return
        descriptions='\n'.join(f"{x}. {EXTERNAL_MEASURES.get(x,{}).get('title','')}" for x in added)
        if not messagebox.askyesno('Doplnit opatření?',f"Program navrhuje doplnit:\n\n{descriptions}\n\nPřidat tato čísla k místnosti?"):return
        row['measure_codes']=external_normalize_measures(','.join(current+added));row['measure']=external_measures_text(row['measure_codes']);self.refresh_measurements()

    def external_import_xlsx(self):
        if self.revision_type!='VNEJSI':return
        path=filedialog.askopenfilename(title='Import tabulky místností – vnější vlivy',filetypes=[('Excel','*.xlsx'),('Všechny soubory','*.*')])
        if not path:return
        try:rooms=external_import_rooms_xlsx(path)
        except Exception as e:messagebox.showerror('Import vnějších vlivů',f'Import se nepodařil.\n\n{e}');return
        if self.measurements:
            answer=messagebox.askyesnocancel('Import vnějších vlivů',f'Načteno {len(rooms)} místností.\n\nANO = nahradit současnou tabulku\nNE = přidat k současným řádkům\nZRUŠIT = nic neměnit')
            if answer is None:return
            if answer:self.measurements=rooms
            else:self.measurements.extend(rooms)
        else:self.measurements=rooms
        for i,r in enumerate(self.measurements,1):r['sort_order']=i
        self.refresh_measurements()
        floors=len({(r.get('floor') or '').strip() for r in rooms})
        messagebox.showinfo('Import vnějších vlivů',f'Import dokončen.\n\nMístnosti: {len(rooms)}\nPodlaží / listy: {floors}')

    def external_export_xlsx(self):
        if self.revision_type!='VNEJSI':return
        if not self.measurements:messagebox.showinfo('Export vnějších vlivů','Tabulka neobsahuje žádné místnosti.');return
        default=(self.vars.get('revision_no').get().strip() if self.vars.get('revision_no') else '') or 'vnejsi_vlivy'
        path=filedialog.asksaveasfilename(title='Export tabulky vnějších vlivů',defaultextension='.xlsx',initialfile=re.sub(r'[^A-Za-z0-9_.-]+','_',default)+'_mistnosti.xlsx',filetypes=[('Excel','*.xlsx')])
        if not path:return
        try:external_export_rooms_xlsx(path,self.measurements)
        except Exception as e:messagebox.showerror('Export vnějších vlivů',f'Export se nepodařil.\n\n{e}');return
        messagebox.showinfo('Export vnějších vlivů',f'Tabulka byla uložena:\n\n{path}')

    def _selected_parent_key_for_new_circuit(self):
        idx=self._selected_measurement_index()
        if idx is None or idx<0 or idx>=len(self.measurements):return ''
        row=self.measurements[idx];rtype=(row.get('row_type') or 'CIRCUIT').upper()
        if rtype=='RCD':return row.get('item_key','')
        if row.get('parent_key'):return row.get('parent_key','')
        return ''

    def _ensure_measurement_meta(self,row,row_type):
        row=dict(row or {});row['row_type']=row_type
        if not row.get('item_key'):row['item_key']=uuid.uuid4().hex
        if row.get('sort_order') in ('',None):row['sort_order']=len(self.measurements)+1
        return row

    @staticmethod
    def _aggregate_measurement_results(values):
        vals=[str(v or '').strip() for v in values if str(v or '').strip()]
        if any(v=='Nevyhovuje' for v in vals):return 'Nevyhovuje'
        if vals and all(v=='Vyhovuje' for v in vals):return 'Vyhovuje'
        return 'Nehodnoceno'

    def _recalculate_electrical_results(self):
        if self.revision_type not in ('ELEKTRO','STROJ'):return
        children={}
        keymap={str(r.get('item_key') or ''):r for r in self.measurements if str(r.get('item_key') or '')}
        for row in self.measurements:
            children.setdefault(row.get('parent_key') or '',[]).append(row)
        for row in self.measurements:
            if (row.get('row_type') or 'CIRCUIT').upper()!='POINT':continue
            if is_phase_phase_point(row.get('designation')):
                # Mezi fázemi v této měřicí sadě evidujeme pouze izolační stav.
                for key in ('measured_voltage','zs','zs_limit','ik','impedance_result'):row[key]=''
                auto=None
            else:
                parent=keymap.get(str(row.get('parent_key') or ''))
                auto=auto_zs_limit(parent,row.get('measured_voltage')) if parent and (parent.get('row_type') or 'CIRCUIT').upper() in ('CIRCUIT','RCD') else None
            if auto:
                lim,ia,u0,km=auto
                row['zs_limit']=_fmt_calc_number(lim,3)
                zs=_electrical_num(row.get('zs'))
                if zs is not None:row['impedance_result']='Vyhovuje' if zs<=lim else 'Nevyhovuje'
            else:
                zs=_electrical_num(row.get('zs'));lim=_electrical_num(row.get('zs_limit'))
                if zs is not None and lim is not None:row['impedance_result']='Vyhovuje' if zs<=lim else 'Nevyhovuje'
            parts=[]
            if str(row.get('zs') or '').strip() or str(row.get('impedance_result') or '').strip():parts.append(row.get('impedance_result',''))
            if str(row.get('riso') or '').strip() or str(row.get('insulation_result') or '').strip():parts.append(row.get('insulation_result',''))
            if parts:row['result']=self._aggregate_measurement_results(parts)
            elif not str(row.get('result') or '').strip():row['result']='Nehodnoceno'
        for row in self.measurements:
            if (row.get('row_type') or '').upper()=='CONTINUITY':
                val=ContinuityMeasurementDialog._num(row.get('pe_continuity'));lim=ContinuityMeasurementDialog._num(row.get('zs_limit'))
                if val is not None and lim is not None:row['pe_result']='Vyhovuje' if val<=lim else 'Nevyhovuje'
                if str(row.get('pe_continuity') or '').strip() and not str(row.get('pe_result') or '').strip():row['pe_result']='Nehodnoceno'
                row['result']=row.get('pe_result') or row.get('result') or 'Nehodnoceno'
            elif (row.get('row_type') or '').upper()=='RCD':
                if row.get('rcd_device_kind')=='RCBO' and not row.get('breaker_current_a'):
                    row['breaker_current_a']=row.get('rcd_in_a','')
                auto=auto_zs_limit(row,row.get('measured_voltage'))
                if auto and not str(row.get('zs_limit') or '').strip():row['zs_limit']=_fmt_calc_number(auto[0],3)
                zs=_electrical_num(row.get('zs'));lim=_electrical_num(row.get('zs_limit'))
                if zs is not None and lim is not None:row['impedance_result']='Vyhovuje' if zs<=lim else 'Nevyhovuje'
                parts=[]
                if row.get('rcd_result'):parts.append(row.get('rcd_result'))
                if str(row.get('zs') or '').strip() or row.get('impedance_result'):parts.append(row.get('impedance_result') or 'Nehodnoceno')
                if str(row.get('riso') or '').strip() or row.get('insulation_result'):parts.append(row.get('insulation_result') or 'Nehodnoceno')
                parts.extend(x.get('result','Nehodnoceno') for x in children.get(row.get('item_key') or '',[]) if (x.get('row_type') or '').upper()=='POINT')
                row['result']=self._aggregate_measurement_results(parts) if parts else 'Nehodnoceno'
        for row in self.measurements:
            if (row.get('row_type') or 'CIRCUIT').upper()!='CIRCUIT':continue
            measured=[c for c in children.get(row.get('item_key') or '',[]) if (c.get('row_type') or '').upper() in ('POINT','CONTINUITY')]
            if measured:
                row['result']=self._aggregate_measurement_results([p.get('result','') or p.get('pe_result','') for p in measured])
            elif not any(str(row.get(k) or '').strip() for k in ('zs','riso','riso_l_pe','riso_n_pe','riso_l_n','impedance_result','insulation_result')):
                row['result']='Nehodnoceno'

    def _selected_machine_parent_key(self):
        idx=self._selected_measurement_index()
        if idx is None or idx<0 or idx>=len(self.measurements):return ''
        r=self.measurements[idx];typ=(r.get('row_type') or 'MEASUREMENT').upper()
        if typ=='GROUP':return r.get('item_key','')
        return r.get('parent_key','')

    def machine_add_default_structure(self):
        if self.revision_type!='STROJ':return
        if self.measurements and not messagebox.askyesno('Strojní zařízení','Doplnit základní strukturu k již existujícím položkám?'):return
        groups=[
            ('PŘÍVOD','Přívod a hlavní vypínač'),
            ('OCHR','Ochranný obvod a ochranné pospojování'),
            ('ISO','Izolační odpor'),
            ('ADS','Ochrana automatickým odpojením'),
            ('CTRL','Řídicí a pomocné obvody'),
            ('DRV','Pohony / motory'),
            ('FUNC','Funkční zkoušky'),
        ]
        existing={(r.get('designation'),r.get('measurement_type')) for r in self.measurements if (r.get('row_type') or '').upper()=='GROUP'}
        func_key=''
        for des,name in groups:
            if (des,name) in existing:
                if des=='FUNC':func_key=next((r.get('item_key','') for r in self.measurements if r.get('designation')==des and r.get('measurement_type')==name),'')
                continue
            row=self._ensure_measurement_meta({'designation':des,'measurement_type':name,'value':'','unit':'','limit_value':'','result':'','note':'','parent_key':''},'GROUP')
            self.measurements.append(row)
            if des=='FUNC':func_key=row['item_key']
        if func_key:
            tests=[
                ('Q0','Hlavní vypínač - funkce a případná uzamykatelnost'),
                ('F1','Nastavení / funkce nadproudových ochran'),
                ('F2','Chování stroje po ztrátě napětí a jeho obnovení'),
                ('F3','Zařízení nouzového zastavení'),
                ('F4','Bezpečnostní a koncové spínače'),
            ]
            existing_tests={r.get('measurement_type') for r in self.measurements if r.get('parent_key')==func_key}
            for des,name in tests:
                if name in existing_tests:continue
                self.measurements.append(self._ensure_measurement_meta({'designation':des,'measurement_type':name,'value':'','unit':'','limit_value':'Funkční / dle dokumentace výrobce','result':'','note':'','parent_key':func_key},'FUNCTION'))
        self._normalize_measurement_order();self.refresh_measurements()

    def machine_add_group(self):
        if self.revision_type!='STROJ':return
        fields=[('designation','Označení skupiny'),('measurement_type','Název skupiny'),('note','Poznámka','text')]
        d=FormDialog(self,'Nová skupina měření',fields,{'measurement_type':'Rozvaděč / část stroje'},width=760,height=500);self.wait_window(d)
        if d.result:
            row=self._ensure_measurement_meta(d.result,'GROUP');row['parent_key']='';self.measurements.append(row);self._normalize_measurement_order();self.refresh_measurements()

    def machine_add_item(self,row_type='MEASUREMENT'):
        if self.revision_type!='STROJ':return
        parent=self._selected_machine_parent_key()
        initial={'measurement_type':'Funkční zkouška' if row_type=='FUNCTION' else 'Měření','result':''}
        d=FormDialog(self,'Nová funkční zkouška' if row_type=='FUNCTION' else 'Nové měření',MEASUREMENT_SCHEMAS['STROJ'],initial,width=760,height=650);self.wait_window(d)
        if d.result:
            row=self._ensure_measurement_meta(d.result,row_type);row['parent_key']=parent;self.measurements.append(row);self._normalize_measurement_order();self.refresh_measurements()

    def _machine_selected_row(self):
        idx=self._selected_measurement_index()
        if idx is None or idx<0 or idx>=len(self.measurements):return None
        return self.measurements[idx]

    def _machine_group_parent_for_new_classic(self):
        row=self._machine_selected_row()
        if not row:return ''
        typ=(row.get('row_type') or 'MEASUREMENT').upper()
        if typ=='GROUP':return row.get('item_key','')
        return row.get('parent_key','')

    def _machine_selected_classic_parent(self,allow_group=False):
        row=self._machine_selected_row()
        if not row:return ''
        typ=(row.get('row_type') or '').upper()
        if typ in ('CIRCUIT','RCD'):return row.get('item_key','')
        if typ in ('POINT','CONTINUITY'):return row.get('parent_key','')
        if allow_group and typ=='GROUP':return row.get('item_key','')
        return ''

    def machine_add_classic_circuit(self):
        if self.revision_type!='STROJ':return
        parent=self._machine_group_parent_for_new_classic()
        d=ElectricalCircuitDialog(self,'Nový klasický obvod – strojní zařízení',{'parent_key':parent,'row_type':'CIRCUIT'});self.wait_window(d)
        if d.result:
            row=self._ensure_measurement_meta(d.result,'CIRCUIT');row['parent_key']=parent
            self.measurements.append(row);self._normalize_measurement_order();self._recalculate_electrical_results();self.refresh_measurements()

    def machine_add_classic_point(self):
        if self.revision_type!='STROJ':return
        parent=self._machine_selected_classic_parent(False)
        if not parent:
            messagebox.showinfo('Klasické měření','Nejprve vyber klasický obvod nebo RCD/RCBO, pod který chceš přidat měřicí bod.')
            return
        d=BulkMeasurementDialog(self,title='Kompletní zadání klasického měření – stroj');self.wait_window(d)
        if d.result:
            for values in d.result:
                row=self._ensure_measurement_meta(values,'POINT');row['parent_key']=parent;self.measurements.append(row)
            self._normalize_measurement_order();self._recalculate_electrical_results();self.refresh_measurements()

    def machine_add_classic_continuity(self):
        if self.revision_type!='STROJ':return
        parent=self._machine_selected_classic_parent(True)
        if not parent:
            messagebox.showinfo('Spojitost','Vyber klasický obvod nebo skupinu stroje, ke které chceš měření spojitosti přiřadit.')
            return
        d=ContinuityMeasurementDialog(self,'Nové měření spojitosti – strojní zařízení');self.wait_window(d)
        if d.result:
            row=self._ensure_measurement_meta(d.result,'CONTINUITY');row['parent_key']=parent;self.measurements.append(row)
            self._normalize_measurement_order();self._recalculate_electrical_results();self.refresh_measurements()

    def machine_add_classic_rcd(self):
        if self.revision_type!='STROJ':return
        parent=self._machine_group_parent_for_new_classic()
        d=RCDMeasurementDialog(self,'Nový RCD / RCBO – strojní zařízení',{});self.wait_window(d)
        if not d.result:return
        points=d.result.pop('_measurement_points',[])
        row=self._ensure_measurement_meta(d.result,'RCD');row['parent_key']=parent;self.measurements.append(row)
        for values in points:
            point=self._ensure_measurement_meta(values,'POINT');point['parent_key']=row['item_key'];self.measurements.append(point)
        self._normalize_measurement_order();self._recalculate_electrical_results();self.refresh_measurements()

    def machine_add_note(self):
        if self.revision_type!='STROJ':return
        parent=self._selected_machine_parent_key()
        d=FormDialog(self,'Nový text / poznámka v tabulce měření',[('note','Text poznámky','text')],width=760,height=430);self.wait_window(d)
        if d.result and str(d.result.get('note') or '').strip():
            row=self._ensure_measurement_meta({'designation':'','measurement_type':'','value':'','unit':'','limit_value':'','result':'','note':d.result.get('note',''),'parent_key':parent},'NOTE')
            self.measurements.append(row);self._normalize_measurement_order();self.refresh_measurements()

    def machine_add_blank(self):
        if self.revision_type!='STROJ':return
        row=self._ensure_measurement_meta({'designation':'','measurement_type':'','value':'','unit':'','limit_value':'','result':'','note':'','parent_key':self._selected_machine_parent_key()},'BLANK')
        self.measurements.append(row);self._normalize_measurement_order();self.refresh_measurements()

    def measure_add(self):
        if self.revision_type=='ELEKTRO':
            parent_key=self._selected_parent_key_for_new_circuit()
            initial={'parent_key':parent_key,'row_type':'CIRCUIT'}
            d=ElectricalCircuitDialog(self,"Nový obvod – impedance / izolace",initial)
        else:
            d=FormDialog(self,"Přidat položku",MEASUREMENT_SCHEMAS[self.revision_type],width=700,height=650)
        self.wait_window(d)
        if d.result:
            row=self._ensure_measurement_meta(d.result,'CIRCUIT' if self.revision_type=='ELEKTRO' else '')
            self.measurements.append(row);self._normalize_measurement_order();self.refresh_measurements()

    def _selected_circuit_key_for_point(self):
        idx=self._selected_measurement_index()
        if idx is None or idx<0 or idx>=len(self.measurements):return ''
        row=self.measurements[idx];rtype=(row.get('row_type') or 'CIRCUIT').upper()
        if rtype=='CIRCUIT':return row.get('item_key','')
        if rtype in ('POINT','CONTINUITY'):return row.get('parent_key','')
        return ''

    def measure_add_point(self):
        if self.revision_type!='ELEKTRO':return
        parent_key=self._selected_circuit_key_for_point()
        if not parent_key:
            messagebox.showinfo('Měření','Nejprve vyber obvod / jistič, pod který chceš přidat nové měření.')
            return
        d=BulkMeasurementDialog(self,title='Kompletní zadání měření');self.wait_window(d)
        if d.result:
            for values in d.result:
                row=self._ensure_measurement_meta(values,'POINT');row['parent_key']=parent_key;self.measurements.append(row)
        self._normalize_measurement_order();self.refresh_measurements()

    def measure_add_three_phase_points(self):
        if self.revision_type!='ELEKTRO':return
        parent_key=self._selected_circuit_key_for_point()
        if not parent_key:
            messagebox.showinfo('Třífázové měření','Nejprve vyber vícefázový obvod / jistič.')
            return
        existing={(r.get('designation') or '').strip() for r in self.measurements if r.get('parent_key')==parent_key and (r.get('row_type') or '').upper()=='POINT'}
        added=0
        for pair in ('L1–PE','L2–PE','L3–PE'):
            if pair in existing:continue
            row=self._ensure_measurement_meta({'designation':pair,'name':'','riso':'','zs':'','zs_limit':'','ik':'','insulation_voltage':'','impedance_result':'','insulation_result':'','result':'','note':'','parent_key':parent_key},'POINT')
            self.measurements.append(row);added+=1
        if added:self._normalize_measurement_order();self.refresh_measurements()

    def measure_add_rcd(self):
        if self.revision_type!='ELEKTRO':return
        d=RCDMeasurementDialog(self,'Nový proudový nebo kombinovaný chránič')
        self.wait_window(d)
        if d.result:
            points=d.result.pop('_measurement_points',[])
            row=self._ensure_measurement_meta(d.result,'RCD');row['parent_key']='';self.measurements.append(row)
            for values in points:
                point=self._ensure_measurement_meta(values,'POINT');point['parent_key']=row['item_key'];self.measurements.append(point)
            self._normalize_measurement_order();self.refresh_measurements()

    def measure_add_continuity(self):
        if self.revision_type!='ELEKTRO':return
        # Vybraný obvod = spojitost se zobrazí přímo pod ním. Bez vybraného obvodu zůstane samostatná.
        parent_key=self._selected_circuit_key_for_point()
        d=ContinuityMeasurementDialog(self,'Nové měření spojitosti',{'pe_result':'Vyhovuje'})
        self.wait_window(d)
        if d.result:
            row=self._ensure_measurement_meta(d.result,'CONTINUITY');row['parent_key']=parent_key or '';self.measurements.append(row);self._normalize_measurement_order();self.refresh_measurements()

    def measure_add_note(self):
        if self.revision_type!='ELEKTRO':return
        idx=self._selected_measurement_index()
        parent_key=''
        if idx is not None and 0 <= idx < len(self.measurements):
            selected=self.measurements[idx];typ=(selected.get('row_type') or 'CIRCUIT').upper()
            if typ in ('RCD','CIRCUIT'):
                parent_key=selected.get('item_key','')
            else:
                parent_key=selected.get('parent_key','') or ''
        d=FormDialog(self,'Nový text / poznámka v tabulce měření',[('note','Text poznámky','text')],width=760,height=430);self.wait_window(d)
        if d.result and str(d.result.get('note') or '').strip():
            row=self._ensure_measurement_meta({'designation':'','name':'','note':d.result.get('note',''),'parent_key':parent_key},'NOTE')
            self.measurements.append(row);self._normalize_measurement_order();self.refresh_measurements()

    def measure_add_blank(self):
        if self.revision_type!='ELEKTRO':return
        row=self._ensure_measurement_meta({'designation':'','name':'','note':'','parent_key':self._selected_parent_key_for_new_circuit()},'BLANK')
        self.measurements.append(row);self._normalize_measurement_order();self.refresh_measurements()

    def measure_edit(self):
        idx=self._selected_measurement_index()
        if idx is None or idx<0 or idx>=len(self.measurements):return
        row=self.measurements[idx];rtype=(row.get('row_type') or ('CIRCUIT' if self.revision_type=='ELEKTRO' else ('MEASUREMENT' if self.revision_type=='STROJ' else ''))).upper()
        if self.revision_type=='ELEKTRO':
            if rtype=='RCD':
                dialog_values=dict(row);dialog_values['_measurement_points']=[dict(x) for x in self.measurements if x.get('parent_key')==row.get('item_key') and (x.get('row_type') or '').upper()=='POINT']
                d=RCDMeasurementDialog(self,'Upravit proudový nebo kombinovaný chránič',dialog_values)
            elif rtype=='CONTINUITY':d=ContinuityMeasurementDialog(self,'Upravit měření spojitosti',row)
            elif rtype=='POINT':d=MeasurementPointDialog(self,'Upravit měřicí bod',row)
            elif rtype=='NOTE':d=FormDialog(self,'Upravit text / poznámku',[('note','Text poznámky','text')],row,width=760,height=430)
            elif rtype=='BLANK':return
            else:d=ElectricalCircuitDialog(self,'Upravit obvod – impedance / izolace',row)
        elif self.revision_type=='STROJ':
            if rtype=='RCD':
                dialog_values=dict(row);dialog_values['_measurement_points']=[dict(x) for x in self.measurements if x.get('parent_key')==row.get('item_key') and (x.get('row_type') or '').upper()=='POINT']
                d=RCDMeasurementDialog(self,'Upravit RCD / RCBO – strojní zařízení',dialog_values)
            elif rtype=='CONTINUITY':d=ContinuityMeasurementDialog(self,'Upravit měření spojitosti – strojní zařízení',row)
            elif rtype=='POINT':d=MeasurementPointDialog(self,'Upravit klasický měřicí bod – strojní zařízení',row)
            elif rtype=='CIRCUIT':d=ElectricalCircuitDialog(self,'Upravit klasický obvod – strojní zařízení',row)
            elif rtype=='GROUP':d=FormDialog(self,'Upravit skupinu měření',[('designation','Označení skupiny'),('measurement_type','Název skupiny'),('note','Poznámka','text')],row,width=760,height=500)
            elif rtype=='NOTE':d=FormDialog(self,'Upravit text / poznámku',[('note','Text poznámky','text')],row,width=760,height=430)
            elif rtype=='BLANK':return
            else:d=FormDialog(self,'Upravit funkční zkoušku' if rtype=='FUNCTION' else 'Upravit měření',MEASUREMENT_SCHEMAS['STROJ'],row,width=760,height=650)
        else:d=FormDialog(self,"Upravit položku",MEASUREMENT_SCHEMAS[self.revision_type],row,width=700,height=650)
        self.wait_window(d)
        if d.result:
            item_key=row.get('item_key') or uuid.uuid4().hex;parent_key=row.get('parent_key','');sort_order=row.get('sort_order',idx+1)
            points=d.result.pop('_measurement_points',None) if rtype=='RCD' else None
            self.measurements[idx]=dict(d.result);self.measurements[idx]['item_key']=item_key;self.measurements[idx]['parent_key']=parent_key;self.measurements[idx]['sort_order']=sort_order;self.measurements[idx]['row_type']=rtype
            if points is not None:
                self.measurements=[x for x in self.measurements if not (x.get('parent_key')==item_key and (x.get('row_type') or '').upper()=='POINT')]
                for values in points:
                    point=self._ensure_measurement_meta(values,'POINT');point['parent_key']=item_key;self.measurements.append(point)
                self._normalize_measurement_order()
            if self.revision_type in ('ELEKTRO','STROJ'):self._recalculate_electrical_results()
            self.refresh_measurements()

    def measure_bulk_edit(self):
        if self.revision_type!='ELEKTRO':return
        editable=[r for r in self.measurements if (r.get('row_type') or '').upper() in ('POINT','CONTINUITY')]
        if not editable:
            messagebox.showinfo('Hromadná editace','Nejsou zde žádné měřicí body ani měření spojitosti k úpravě.')
            return
        d=BulkEditElectricalMeasurementsDialog(self,self.measurements);self.wait_window(d)
        if not d.result:return
        for idx,row in d.result:
            if 0<=idx<len(self.measurements):self.measurements[idx]=row
        self._recalculate_electrical_results();self.refresh_measurements()

    def measure_delete(self):
        idx=self._selected_measurement_index()
        if idx is None:return
        row=self.measurements[idx];rtype=(row.get('row_type') or '').upper();doomed={idx}
        key=row.get('item_key','')
        if key:
            pending=[key]
            while pending:
                pk=pending.pop()
                for i,r in enumerate(self.measurements):
                    if i in doomed:continue
                    if r.get('parent_key')==pk:
                        doomed.add(i)
                        if r.get('item_key'):pending.append(r.get('item_key'))
        msg='Odstranit položku?'
        if len(doomed)>1:msg=f'Odstranit vybranou položku a také {len(doomed)-1} podřízených měření / řádků?'
        if not messagebox.askyesno('Smazat',msg):return
        self.measurements=[r for i,r in enumerate(self.measurements) if i not in doomed];self._normalize_measurement_order();self.refresh_measurements()

    def _normalize_measurement_order(self):
        for i,r in enumerate(self.measurements,1):r['sort_order']=i

    def measure_move(self,delta):
        idx=self._selected_measurement_index()
        if idx is None:return
        row=self.measurements[idx];parent=row.get('parent_key','')
        siblings=[i for i,r in enumerate(self.measurements) if (r.get('parent_key','') or '')==(parent or '')]
        try:pos=siblings.index(idx)
        except ValueError:return
        npos=pos+delta
        if npos<0 or npos>=len(siblings):return
        j=siblings[npos];self.measurements[idx],self.measurements[j]=self.measurements[j],self.measurements[idx];self._normalize_measurement_order();self.refresh_measurements()
        target=self.measurements.index(row) if row in self.measurements else None
        if target is not None:
            iid=f'm{target}'
            if self.meas_tree.exists(iid):self.meas_tree.selection_set(iid);self.meas_tree.see(iid)

    def refresh_measurements(self):
        for x in self.meas_tree.get_children():self.meas_tree.delete(x)
        if self.revision_type=='VNEJSI':
            warning_count=0;missing_count=0
            for i,r in enumerate(self.measurements):
                if not r.get('sort_order'):r['sort_order']=i+1
                values=external_parse_values(r.get('values_json'))
                warnings=external_room_warnings(r);status=external_row_status(r)
                missing=any(x.startswith('chybí') or x.startswith('nevyplněné') for x in warnings)
                tag='missing' if missing else ('warn' if warnings or status=='Ověřit opatření' else '')
                if missing:missing_count+=1
                elif warnings or status=='Ověřit opatření':warning_count+=1
                abnormal=', '.join(external_abnormal_codes(values))
                row_values=[r.get('floor',''),r.get('room_no',''),r.get('room_name',''),external_classify_environment(values),abnormal,external_normalize_measures(r.get('measure_codes','')),status]
                self.meas_tree.insert('','end',iid=str(i),values=row_values,tags=((tag,) if tag else ()))
            if hasattr(self,'external_summary_var'):
                floors=len({str(r.get('floor','') or '').strip() for r in self.measurements if str(r.get('floor','') or '').strip()})
                classes=[external_classify_environment(external_parse_values(r.get('values_json'))) for r in self.measurements]
                normal_count=sum(1 for x in classes if x=='NORMÁLNÍ')
                abnormal_count=sum(1 for x in classes if x=='ABNORMÁLNÍ')
                self.external_summary_var.set(f'Místnosti: {len(self.measurements)}  •  podlaží / celky: {floors}  •  normální: {normal_count}  •  abnormální: {abnormal_count}  •  k doplnění: {missing_count}  •  k ověření: {warning_count}')
            if self.measurements and hasattr(self,'meas_tree') and not self.meas_tree.selection():
                first=self.meas_tree.get_children()
                if first:self.meas_tree.selection_set(first[0]);self.meas_tree.see(first[0])
            self.refresh_external_detail()
            return
        if self.revision_type=='STROJ':
            self._recalculate_electrical_results()
            for i,r in enumerate(self.measurements):
                if not r.get('row_type'):r['row_type']='MEASUREMENT'
                if not r.get('item_key'):r['item_key']=f'machine-{i}-{uuid.uuid4().hex[:8]}'
                if r.get('sort_order') in ('',None,0):r['sort_order']=i+1
            keymap={r.get('item_key'):i for i,r in enumerate(self.measurements) if r.get('item_key')}
            roots=[i for i,r in enumerate(self.measurements) if not r.get('parent_key') or r.get('parent_key') not in keymap]
            children={}
            for j,r in enumerate(self.measurements):children.setdefault(r.get('parent_key') or '',[]).append(j)
            cols=MEASUREMENT_TREE['STROJ']
            def label(r):
                return {
                    'GROUP':'Skupina','FUNCTION':'Funkční zkouška','MEASUREMENT':'Měření',
                    'CIRCUIT':'Klasický obvod','POINT':'Měřicí bod','CONTINUITY':'Spojitost',
                    'RCD':'RCD / RCBO','NOTE':'Poznámka','BLANK':''
                }.get((r.get('row_type') or 'MEASUREMENT').upper(),'Měření')
            def machine_vals(r):
                typ=(r.get('row_type') or 'MEASUREMENT').upper()
                if typ=='NOTE':return ('',r.get('note',''),'','','','')
                if typ=='CIRCUIT':
                    desc='Klasický obvod' + (f" – {r.get('name')}" if r.get('name') else '')
                    value=breaker_summary(r)
                    limit=r.get('cable','') or ''
                    return (r.get('designation',''),desc,value,'',limit,r.get('result',''))
                if typ=='POINT':
                    bits=[]
                    for lab,key,unit in [('U','measured_voltage','V'),('Riso','riso','MΩ'),('Zs','zs','Ω'),('Ik','ik','A')]:
                        if str(r.get(key) or '').strip():bits.append(f"{lab} {format_value_unit(r.get(key),unit)}")
                    lim=(f"Zs ≤ {format_value_unit(r.get('zs_limit'),'Ω')}" if str(r.get('zs_limit') or '').strip() else '')
                    return (r.get('designation',''),r.get('name','') or 'Klasický měřicí bod','; '.join(bits),'',lim,r.get('result',''))
                if typ=='CONTINUITY':
                    return (r.get('designation',''),('Spojitost – '+r.get('name','')).rstrip(' –'),r.get('pe_continuity',''),'Ω',r.get('zs_limit',''),r.get('pe_result','') or r.get('result',''))
                if typ=='RCD':
                    kind=r.get('rcd_device_kind','') or 'RCD';rt=r.get('rcd_type','')
                    desc=' / '.join(x for x in [kind,('typ '+rt if rt else '')] if x)
                    vals=[]
                    if r.get('rcd_idn_ma'):vals.append(f"IΔn {format_value_unit(r.get('rcd_idn_ma'),'mA')}")
                    if r.get('rcd'):vals.append(f"t {format_value_unit(r.get('rcd'),'ms')}")
                    if r.get('rcd_trip_ma'):vals.append(f"IΔ {format_value_unit(r.get('rcd_trip_ma'),'mA')}")
                    if r.get('rcd_touch_v'):vals.append(f"Uc {format_value_unit(r.get('rcd_touch_v'),'V')}")
                    return (r.get('rcd_designation','') or r.get('designation',''),desc,'; '.join(vals),'','',r.get('result','') or r.get('rcd_result',''))
                return tuple(r.get(k,'') for k,_,_ in cols)
            def insert_node(i,parent=''):
                r=self.measurements[i];typ=(r.get('row_type') or 'MEASUREMENT').upper();iid=f'm{i}'
                values=machine_vals(r)
                self.meas_tree.insert(parent,'end',iid=iid,text=label(r),values=values,tags=(typ,))
                for j in children.get(r.get('item_key') or '',[]):
                    if j!=i:insert_node(j,iid)
                if children.get(r.get('item_key') or ''):self.meas_tree.item(iid,open=True)
            for i in roots:insert_node(i,'')
            return
        if self.revision_type!='ELEKTRO':
            cols=MEASUREMENT_TREE[self.revision_type]
            for i,r in enumerate(self.measurements):self.meas_tree.insert('', 'end', iid=str(i), values=tuple(r.get(k,'') for k,_,_ in cols))
            return
        self._recalculate_electrical_results()
        # Migrate legacy in-memory rows to the new structural representation without losing data.
        for i,r in enumerate(self.measurements):
            if not r.get('row_type'):r['row_type']='CIRCUIT'
            if not r.get('item_key'):r['item_key']=f'legacy-{i}-{uuid.uuid4().hex[:8]}'
            if r.get('sort_order') in ('',None,0):r['sort_order']=i+1
        key_to_idx={r.get('item_key'):i for i,r in enumerate(self.measurements) if r.get('item_key')}
        roots=[i for i,r in enumerate(self.measurements) if not r.get('parent_key') or r.get('parent_key') not in key_to_idx]
        def vals(r):
            typ=(r.get('row_type') or 'CIRCUIT').upper()
            if typ=='RCD':
                detail=' '.join(x for x in [r.get('rcd_device_kind',''),('typ '+r.get('rcd_type','') if r.get('rcd_type') else ''),r.get('name','')] if x)
                current=' / '.join(x for x in [format_value_unit(r.get('rcd_in_a'),'A'),format_value_unit(r.get('rcd_idn_ma'),'mA')] if x)
                u=format_value_unit(r.get('measured_voltage'),'V');riso=format_value_unit(r.get('riso'),'MΩ');zs=format_value_unit(r.get('zs'),'Ω');ik=format_value_unit(r.get('ik'),'A')
                zsik='; '.join(x for x in [(('Zs '+zs) if zs else ''),(('Ik '+ik) if ik else '')] if x)
                return (r.get('rcd_designation','') or r.get('designation',''),detail,current,r.get('cable',''),u,riso,zsik,r.get('result','') or r.get('rcd_result',''))
            if typ=='CONTINUITY':
                rp=format_value_unit(r.get('pe_continuity'),'Ω');lim=format_value_unit(r.get('zs_limit'),'Ω')
                if lim:rp=(rp+' / mez '+lim) if rp else ('mez '+lim)
                return (r.get('designation',''),r.get('name',''),'','', '',rp,'',r.get('pe_result','') or r.get('result',''))
            if typ=='POINT':
                u=format_value_unit(r.get('measured_voltage'),'V');riso=format_value_unit(r.get('riso'),'MΩ');zs=format_value_unit(r.get('zs'),'Ω');ik=format_value_unit(r.get('ik'),'A');lim=format_value_unit(r.get('zs_limit'),'Ω')
                zsik='; '.join(x for x in [(('Zs '+zs) if zs else ''),(('mez '+lim) if lim else ''),(('Ik '+ik) if ik else '')] if x)
                return (r.get('designation',''),r.get('name',''),'','',u,riso,zsik,r.get('result',''))
            if typ=='NOTE':return ('Poznámka',r.get('note',''),'','','','','','')
            if typ=='BLANK':return ('','','','','','','','')
            riso=format_value_unit(r.get('riso') or r.get('riso_l_pe'),'MΩ');zs=format_value_unit(r.get('zs'),'Ω');ik=format_value_unit(r.get('ik'),'A');u=format_value_unit(r.get('measured_voltage'),'V')
            zsik='; '.join(x for x in [(('Zs '+zs) if zs else ''),(('Ik '+ik) if ik else '')] if x)
            return (r.get('designation',''),r.get('name',''),breaker_summary(r),r.get('cable',''),u,riso,zsik,r.get('result',''))
        def label(r):
            if (r.get('row_type') or '').upper()=='RCD' and (r.get('rcd_device_kind') or '').upper()=='RCBO':return 'Kombinovaný chránič'
            return {'RCD':'Proudový chránič','CONTINUITY':'Spojitost','POINT':'Měřicí bod','NOTE':'Poznámka','BLANK':'','CIRCUIT':'Obvod'}.get((r.get('row_type') or 'CIRCUIT').upper(),'Položka')
        # Recursive structure: RCD -> circuit -> measuring points. Root circuits may also have points.
        children_by_parent={}
        for j,c in enumerate(self.measurements):
            children_by_parent.setdefault(c.get('parent_key') or '',[]).append(j)
        def insert_node(i,parent='',depth=0):
            r=self.measurements[i];typ=(r.get('row_type') or 'CIRCUIT').upper();iid=f'm{i}'
            shown=list(vals(r));marker=('>'*depth+' ') if depth else ''
            shown[0]=marker+str(shown[0] or label(r))
            self.meas_tree.insert(parent,'end',iid=iid,text='',values=shown,tags=(typ,))
            for j in children_by_parent.get(r.get('item_key') or '',[]):
                if j!=i:insert_node(j,iid,depth+1)
            if children_by_parent.get(r.get('item_key') or ''):self.meas_tree.item(iid,open=True)
        for i in roots:insert_node(i,'',0)

    def varistor_add(self):
        d=FormDialog(self,'Nové měření SPD / varistoru',VARISTOR_FIELDS,{'test_current_ma':'1'},width=900,height=720);self.wait_window(d)
        if d.result:self.varistor_measurements.append(d.result);self.refresh_varistors()

    def varistor_edit(self):
        if not hasattr(self,'var_tree'):return
        s=self.var_tree.selection()
        if not s:return
        idx=int(s[0]);d=FormDialog(self,'Upravit měření SPD / varistoru',VARISTOR_FIELDS,self.varistor_measurements[idx],width=900,height=720);self.wait_window(d)
        if d.result:self.varistor_measurements[idx]=d.result;self.refresh_varistors()

    def varistor_delete(self):
        if not hasattr(self,'var_tree'):return
        s=self.var_tree.selection()
        if s and messagebox.askyesno('Smazat','Odstranit měření SPD / varistoru?'):
            self.varistor_measurements.pop(int(s[0]));self.refresh_varistors()

    def refresh_varistors(self):
        if not hasattr(self,'var_tree'):return
        for x in self.var_tree.get_children():self.var_tree.delete(x)
        for i,r in enumerate(self.varistor_measurements):
            self.var_tree.insert('','end',iid=str(i),values=tuple(r.get(k,'') for k,_,_ in VARISTOR_TREE))

    def refresh_catalog(self):
        if not hasattr(self,'catalog_tree'):return
        q=f"%{self.def_search.get().strip()}%";rows=self.db.fetchall("SELECT * FROM defect_catalog WHERE active=1 AND (standard LIKE ? OR article LIKE ? OR title LIKE ? OR defect_text LIKE ? OR category LIKE ? OR COALESCE(norm_refs_json,'') LIKE ?) ORDER BY standard,article,id LIMIT 500",(q,q,q,q,q,q))
        for x in self.catalog_tree.get_children():self.catalog_tree.delete(x)
        for r in rows:self.catalog_tree.insert('', 'end', iid=str(r['id']), values=(r['standard'],r['article'],r['title'] or r['defect_text'][:75]))
    def add_catalog_defect(self):
        s=self.catalog_tree.selection()
        if not s:return
        r=dict(self.db.fetchone("SELECT * FROM defect_catalog WHERE id=?",(int(s[0]),)))
        cls=(r['defect_class'] if 'defect_class' in r.keys() else '') or ''
        sev=(r['severity'] or '') if 'severity' in r.keys() else ''
        if str(sev).strip().upper() not in ('C1','C2','C3') and str(cls).strip().upper() in ('C1','C2','C3'):sev=str(cls).strip().upper()
        if str(sev).strip().upper() not in ('C1','C2','C3'):sev=''
        initial={'catalog_id':r['id'],'category':r['category'],'standard':r['standard'],'article':r['article'],'requirement_text':r.get('requirement_text',''),'norm_refs_json':r.get('norm_refs_json',''),'defect_text':r['defect_text'],'severity':sev,'status':'Neodstraněna','photo_path':'','note':'','_photos':[]}
        d=DefectDialog(self,'Závada ze závadovníku',initial);self.wait_window(d)
        if d.result:
            d.result['catalog_id']=r['id'];self.rev_defects.append(d.result);self.refresh_revision_defects()

    def add_custom_defect(self):
        d=DefectDialog(self,'Vlastní závada',{'status':'Neodstraněna','_photos':[]});self.wait_window(d)
        if d.result:
            d.result['catalog_id']=None;self.rev_defects.append(d.result);self.refresh_revision_defects()

    def edit_revision_defect(self):
        s=self.revdef_tree.selection()
        if not s:return
        idx=int(s[0]);d=DefectDialog(self,'Upravit závadu / fotografie',self.rev_defects[idx]);self.wait_window(d)
        if d.result:
            catalog_id=self.rev_defects[idx].get('catalog_id');self.rev_defects[idx].update(d.result);self.rev_defects[idx]['catalog_id']=catalog_id;self.refresh_revision_defects()

    def delete_revision_defect(self):
        s=self.revdef_tree.selection()
        if s and messagebox.askyesno("Odebrat","Odebrat závadu z této revize včetně její fotodokumentace?"):self.rev_defects.pop(int(s[0]));self.refresh_revision_defects()

    def refresh_revision_defects(self):
        if not hasattr(self,'revdef_tree'):return
        for x in self.revdef_tree.get_children():self.revdef_tree.delete(x)
        for i,d in enumerate(self.rev_defects):
            photos=len(d.get('_photos') or [])
            sev=(d.get('severity','') or '').strip().upper()
            if sev not in ('C1','C2','C3'):sev=(d.get('defect_class','') or '').strip().upper()
            if sev not in ('C1','C2','C3'):sev=''
            self.revdef_tree.insert('', 'end', iid=str(i), values=(d.get('defect_text','')[:100],_defect_refs_summary(d),sev,d.get('status',''),photos if photos else ''))
        if hasattr(self,'appendix_tree'):self.refresh_appendix_preview()

    def validate_revision(self):
        w=[]
        if self.revision_type=='VNEJSI':
            if not self.vars.get('revision_no') or not self.vars['revision_no'].get().strip():w.append('Není vyplněno číslo protokolu.')
            owner=(self.special_vars.get('owner').get().strip() if self.special_vars.get('owner') and not isinstance(self.special_vars.get('owner'),tk.Text) else '')
            operator=(self.special_vars.get('operator').get().strip() if self.special_vars.get('operator') and not isinstance(self.special_vars.get('operator'),tk.Text) else '')
            if not self.vars['customer'].get().strip() and not (owner or operator):w.append('Není vybrán objednatel ani vyplněn majitel/provozovatel.')
            if not any(self.vars.get(k) and self.vars[k].get().strip() for k in ('object_name_text','object_address_text','object_location_note')):w.append('Není vyplněn posuzovaný objekt / místo.')
            chair=self.special_vars.get('chairperson')
            chair_val=chair.get().strip() if chair is not None and not isinstance(chair,tk.Text) else ''
            if not chair_val:w.append('Není vyplněn předseda komise.')
            if not self.measurements:
                w.append('Protokol neobsahuje žádnou místnost / prostor s určenými vnějšími vlivy.')
            else:
                for idx,row in enumerate(self.measurements,1):
                    warnings=external_room_warnings(row)
                    serious=[x for x in warnings if x.startswith('chybí') or x.startswith('nevyplněné')]
                    label=' / '.join(x for x in [row.get('floor',''),row.get('room_no',''),row.get('room_name','')] if x) or str(idx)
                    if serious:w.append(f'Vnější vlivy {label}: '+ '; '.join(serious)+'.')
            if not any((r.get('code_snapshot') or '').startswith('ČSN 33 2000-5-51') for r in self.rev_standards):w.append(f'V protokolu není vybrána základní norma {EXTERNAL_STANDARD_CODE}.')
            if w:messagebox.showwarning("Kontrola protokolu","Program našel následující body k ověření:\n\n• "+"\n• ".join(w)+"\n\nJde o pomocnou kontrolu. Odborné určení vnějších vlivů zůstává na zpracovateli a komisi.")
            else:messagebox.showinfo("Kontrola protokolu","Základní kontrola neodhalila chybějící údaje nebo logický rozpor.")
            return w
        if not self.vars['customer'].get():w.append('Není vybrán zákazník.')
        if not self.texts['subject'].get('1.0','end').strip():w.append('Není vyplněn předmět revize.')
        if self.revision_type!='VNEJSI' and not any((m.get('row_type') or 'CIRCUIT').upper()!='BLANK' for m in self.measurements):w.append('Revize neobsahuje žádná měření.')
        selected={self.instrument_rows[i]['id'] for i in self.instrument_list.curselection()} if self.instrument_rows else set()
        if not selected and self.revision_type!='VNEJSI':w.append('Není vybrán měřicí přístroj.')
        if self.revision_type=='VNEJSI':
            if not self.measurements:
                w.append('Protokol neobsahuje žádnou místnost / prostor s určenými vnějšími vlivy.')
            else:
                for idx,row in enumerate(self.measurements,1):
                    warnings=external_room_warnings(row)
                    serious=[x for x in warnings if x.startswith('chybí') or x.startswith('nevyplněné')]
                    label=' / '.join(x for x in [row.get('floor',''),row.get('room_no',''),row.get('room_name','')] if x) or str(idx)
                    if serious:w.append(f'Vnější vlivy {label}: '+ '; '.join(serious)+'.')
            if not any((r.get('code_snapshot') or '').startswith('ČSN 33 2000-5-51') for r in self.rev_standards):
                w.append(f'V protokolu není vybrána základní norma {EXTERNAL_STANDARD_CODE}.')
        def _def_sev(d):
            sev=(d.get('severity','') or '').strip().upper()
            if sev not in ('C1','C2','C3'):sev=(d.get('defect_class','') or '').strip().upper()
            return sev if sev in ('C1','C2','C3') else ''
        if self.vars['result'].get()=='Vyhovuje' and any(d.get('status','')=='Neodstraněna' and _def_sev(d)!='C3' for d in self.rev_defects):w.append('Celkový výsledek je „Vyhovuje“, ale revize obsahuje neodstraněnou závadu C1/C2 nebo závadu bez určené závažnosti.')
        if self.revision_type=='ELEKTRO':
            def num(v):
                try:return float(str(v or '').strip().replace(',','.').replace('≤','').replace('<','').replace('>',''))
                except Exception:return None
            rcd_profiles={
                'AC':['ac_pos','ac_neg'],
                'A':['ac_pos','ac_neg','a_pos','a_neg'],
                'F':['ac_pos','ac_neg','a_pos','a_neg','f_pos','f_neg'],
                'B':['ac_pos','ac_neg','a_pos','a_neg','b_pos','b_neg'],
                'B+':['ac_pos','ac_neg','a_pos','a_neg','b_pos','b_neg'],
            }
            for idx,m in enumerate(self.measurements,1):
                rtype=(m.get('row_type') or 'CIRCUIT').upper()
                if rtype=='CIRCUIT':
                    zs=num(m.get('zs'));lim=num(m.get('zs_limit'))
                    if zs is not None and lim is not None and zs>lim:w.append(f"Obvod {m.get('designation') or idx}: Zs {m.get('zs')} Ω je vyšší než zadaná mez {m.get('zs_limit')} Ω.")
                elif rtype=='RCD':
                    typ=(m.get('rcd_type') or '').strip()
                    if not typ:w.append(f"RCD {m.get('rcd_designation') or idx}: není zvolen typ citlivosti chrániče.")
                    for test in rcd_profiles.get(typ,[]):
                        vals=[m.get(f'rcd_{test}_trip_ma'),m.get(f'rcd_{test}_time_ms'),m.get(f'rcd_{test}_touch_v')]
                        if not any(str(v or '').strip() for v in vals):w.append(f"RCD {m.get('rcd_designation') or idx}: chybí měření {RCDMeasurementDialog.TEST_LABELS.get(test,test)} pro typ {typ}.")
                    if m.get('rcd_idn_ma') and not any(str(m.get(k) or '').strip() for k in ('rcd_5x_pos_ms','rcd_5x_neg_ms','rcd_no_trip_result')):
                        w.append(f"RCD {m.get('rcd_designation') or idx}: nejsou vyplněny společné zkoušky 20–50 % / 5× IΔn.")
                    zs=num(m.get('zs'));lim=num(m.get('zs_limit'))
                    if zs is not None and lim is not None and zs>lim:w.append(f"RCD/RCBO {m.get('rcd_designation') or idx}: Zs {m.get('zs')} Ω je vyšší než mez {m.get('zs_limit')} Ω.")
                elif rtype=='POINT' and not (str(m.get('riso') or '').strip() or str(m.get('zs') or '').strip()):
                    w.append(f"Měřicí bod {m.get('designation') or idx}: není zadáno Riso ani Zs.")
                elif rtype=='CONTINUITY' and not str(m.get('pe_continuity') or '').strip():
                    w.append(f"Spojitost {m.get('designation') or idx}: není zadána naměřená hodnota.")
        if self.revision_type=='LPS':
            count=''
            v=self.special_vars.get('down_conductor_count')
            count=v.get().strip() if isinstance(v,tk.StringVar) else ''
            try:
                if count and int(count)!=len(self.measurements):w.append(f"Počet svodů je {count}, ale tabulka měření obsahuje {len(self.measurements)} položek.")
            except ValueError:w.append('Počet svodů není číslo.')
        rt=self.db.fetchone("SELECT * FROM rt_profile WHERE id=1")
        if not rt or not rt['name']:w.append('V Nastavení RT není vyplněno jméno revizního technika.')
        else:
            rt_required=[('address','adresa'),('city','město'),('zip','PSČ'),('phone','telefon'),('email','e-mail'),('certificate_no','číslo osvědčení'),('authorization_no','číslo oprávnění')]
            missing=[label for key,label in rt_required if not str(rt[key] or '').strip()]
            if missing:w.append('Údaje revizního technika nejsou kompletní: chybí '+', '.join(missing)+'.')
        if w:messagebox.showwarning("Kontrola revize","Program našel následující body k ověření:\n\n• "+"\n• ".join(w)+"\n\nJde o pomocnou kontrolu. Odborné posouzení zůstává na RT.")
        else:messagebox.showinfo("Kontrola revize","Základní kontrola neodhalila chybějící údaje nebo logický rozpor.")
        return w

    def _confirm_no_defects(self):
        if self.revision_type=='VNEJSI':return True
        if self.rev_defects:return True
        if messagebox.askyesno("Kontrola závad","V revizi nejsou zadány žádné závady.\n\nOpravdu NEBYLY ZJIŠTĚNY žádné závady?"):
            return True
        self.nb.select(self.tab_defects);return False

    def _state_snapshot(self):
        """Serialize the user-editable state so closing can reliably detect unsaved changes."""
        try:
            special={k:(v.get('1.0','end').strip() if isinstance(v,tk.Text) else v.get()) for k,v in self.special_vars.items()}
            state={
                'vars':{k:v.get() for k,v in self.vars.items()},
                'texts':{k:t.get('1.0','end').strip() for k,t in self.texts.items()},
                'special':special,
                'deadline_watch':bool(self.deadline_watch_var.get()) if hasattr(self,'deadline_watch_var') else False,
                'measurements':self.measurements,
                'varistor_measurements':self.varistor_measurements,
                'rev_defects':self.rev_defects,
                'attachments':self.attachments,
                'documents':self.documents,
                'rev_standards':self.rev_standards,
                'networks':self.networks,
                'supplies':self.supplies,
                'conclusion_blocks':self.conclusion_blocks,
                'protection_measures':self.protection_measures,
                'inspection_items':self.inspection_items,
                'working_photos':self.working_photos,
                'instrument_ids':list(self.instrument_list.curselection()) if hasattr(self,'instrument_list') else [],
            }
            return json.dumps(state,ensure_ascii=False,sort_keys=True,default=str)
        except Exception:
            return ''

    def _has_unsaved_changes(self):
        baseline=getattr(self,'_saved_state',None)
        return baseline is not None and self._state_snapshot()!=baseline

    def _on_close_request(self):
        if not self._has_unsaved_changes():
            self.destroy();return 'break'
        ans=messagebox.askyesnocancel('Neuložené změny','Revize obsahuje neuložené změny.\n\nChceš je před zavřením uložit?',parent=self)
        if ans is None:return 'break'
        if ans is False:
            self.destroy();return 'break'
        self._persist(close_after=True,show_message=True,confirm_defects=True)
        return 'break'

    def _persist(self, close_after=False, show_message=True, confirm_defects=True):
        if confirm_defects and not self._confirm_no_defects():return False
        try:
            special=dict(self.special or {})
            for k,v in self.special_vars.items():special[k]=v.get('1.0','end').strip() if isinstance(v,tk.Text) else v.get().strip()
            data={k:v.get().strip() for k,v in self.vars.items()}
            data.update({k:t.get('1.0','end').strip() for k,t in self.texts.items()})
            customer_label=data.pop('customer','');cid=self.customer_map.get(customer_label);oid=self.rev.get('object_id') if self.rev else None;jid=self.rev.get('job_id') if self.rev else None
            documentation_text='\n'.join(' - '.join(x for x in [d.get('doc_type',''),d.get('doc_no',''),d.get('author',''),d.get('note','')] if x) for d in self.documents)
            network_text=''
            supply_text='; '.join(' – '.join(x for x in [n.get('supply_type',''),n.get('designation',''),n.get('voltage',''),n.get('backup','')] if x) for n in self.supplies)
            protection_text='; '.join((r.get('label_snapshot') or '').strip() for r in self.protection_measures if (r.get('label_snapshot') or '').strip())
            inspection_text='\n'.join(f"{(r.get('label_snapshot') or '').strip()} - {(r.get('result') or 'VYHOVUJE').strip()}" for r in self.inspection_items if (r.get('label_snapshot') or '').strip())
            revision_data={
                'revision_no':data.get('revision_no',''),'revision_type':self.revision_type,'revision_kind':data.get('revision_kind','Pravidelná'),
                'customer_id':cid,'object_id':oid,'job_id':jid,'status':data.get('status','Rozpracovaná'),'started_on':data.get('started_on',''),
                'finished_on':data.get('finished_on',''),'issued_on':data.get('issued_on',''),'next_revision_on':data.get('next_revision_on',''),'deadline_watch':1 if self.deadline_watch_var.get() else 0,
                'subject':data.get('subject',''),'scope':data.get('scope',''),'documentation':documentation_text,'protection':protection_text,
                'supply':supply_text,'network':network_text,'inspection_text':inspection_text,'conclusion':data.get('conclusion',''),'result':data.get('result','Nehodnoceno'),
                'special_json':json.dumps(special,ensure_ascii=False),'vtz_class':data.get('vtz_class',''),'distribution_text':data.get('distribution_text',''),
                'received_on':data.get('received_on',''),'object_name_text':data.get('object_name_text',''),'object_address_text':data.get('object_address_text',''),
                'object_city_text':data.get('object_city_text',''),'object_zip_text':data.get('object_zip_text',''),'object_parcel_text':data.get('object_parcel_text',''),
                'object_location_note':data.get('object_location_note',''),'operator_instruction':data.get('operator_instruction','')
            }
            cols=list(revision_data)
            if self.revision_id:
                assignments=','.join(f"{c}=?" for c in cols)
                self.db.execute(f"UPDATE revisions SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE id=?",[revision_data[c] for c in cols]+[self.revision_id])
            else:
                self.revision_id=self.db.execute(f"INSERT INTO revisions({','.join(cols)}) VALUES({','.join('?' for _ in cols)})",[revision_data[c] for c in cols])
            self.rev.update(revision_data);self.rev['id']=self.revision_id
            if data.get('operator_instruction','').strip():self.db.learn_value(self._operator_template_category(),data.get('operator_instruction','').strip())

            table={"ELEKTRO":"circuits","LPS":"lps_measurements","STROJ":"machine_measurements","VNEJSI":"external_influences"}[self.revision_type]
            self.db.execute(f"DELETE FROM {table} WHERE revision_id=?",(self.revision_id,))
            if self.revision_type=='ELEKTRO':
                fields=[row[1] for row in self.db.fetchall("PRAGMA table_info(circuits)") if row[1] not in ('id','revision_id')]
            elif self.revision_type=='STROJ':
                fields=[row[1] for row in self.db.fetchall("PRAGMA table_info(machine_measurements)") if row[1] not in ('id','revision_id')]
            elif self.revision_type=='VNEJSI':
                fields=[row[1] for row in self.db.fetchall("PRAGMA table_info(external_influences)") if row[1] not in ('id','revision_id')]
            else:
                fields=[f[0] for f in MEASUREMENT_SCHEMAS[self.revision_type]]
            placeholders=','.join('?' for _ in range(len(fields)+1));cols2=','.join(['revision_id']+fields)
            for r in self.measurements:self.db.execute(f"INSERT INTO {table}({cols2}) VALUES({placeholders})",[self.revision_id]+[r.get(k,'') for k in fields])

            if self.revision_type=='ELEKTRO':
                self.db.execute("DELETE FROM varistor_measurements WHERE revision_id=?",(self.revision_id,))
                vfields=[f[0] for f in VARISTOR_FIELDS]
                vcols=','.join(['revision_id']+vfields);vph=','.join('?' for _ in range(len(vfields)+1))
                for r in self.varistor_measurements:
                    self.db.execute(f"INSERT INTO varistor_measurements({vcols}) VALUES({vph})",[self.revision_id]+[r.get(k,'') for k in vfields])

            # Defects are snapshots. Recreate them and their photo appendix links together.
            self.db.execute("DELETE FROM revision_defects WHERE revision_id=?",(self.revision_id,))
            self.db.execute("DELETE FROM revision_photos WHERE revision_id=? AND kind='working'",(self.revision_id,))
            for d in self.rev_defects:
                sev=(d.get('severity','') or '').strip().upper()
                if sev not in ('C1','C2','C3'):sev=(d.get('defect_class','') or '').strip().upper()
                if sev not in ('C1','C2','C3'):sev=''
                refs=_defect_norm_refs(d);first=refs[0] if refs else {};norm_json=json.dumps(refs,ensure_ascii=False)
                defect_id=self.db.execute("INSERT INTO revision_defects(revision_id,catalog_id,category,defect_class,standard,article,norm_refs_json,defect_text,severity,status,photo_path,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(self.revision_id,d.get('catalog_id'),d.get('category',''),sev,first.get('standard',d.get('standard','')),first.get('article',d.get('article','')),norm_json,d.get('defect_text',''),sev,d.get('status',''),' ',d.get('note','')))
                first_path=''
                for pos,photo in enumerate(d.get('_photos') or []):
                    stored=photo.get('stored_path','')
                    if not stored and photo.get('source_path'):stored=self.db.copy_attachment(photo['source_path'])
                    if stored:
                        if not first_path:first_path=stored
                        self.db.execute("INSERT INTO revision_photos(revision_id,defect_id,kind,title,original_name,stored_path,note,sort_order) VALUES(?,?,?,?,?,?,?,?)",(self.revision_id,defect_id,'defect',photo.get('title',''),photo.get('original_name') or Path(stored).name,stored,photo.get('note',''),pos))
                        photo['stored_path']=stored;photo['source_path']=''
                if first_path:self.db.execute("UPDATE revision_defects SET photo_path=? WHERE id=?",(first_path,defect_id))
            for pos,photo in enumerate(self.working_photos):
                stored=photo.get('stored_path','')
                if not stored and photo.get('source_path'):stored=self.db.copy_attachment(photo['source_path'])
                if stored:
                    self.db.execute("INSERT INTO revision_photos(revision_id,defect_id,kind,title,original_name,stored_path,note,sort_order) VALUES(?,NULL,'working',?,?,?,?,?)",(self.revision_id,photo.get('title',''),photo.get('original_name') or Path(stored).name,stored,photo.get('note',''),pos));photo['stored_path']=stored;photo['source_path']=''

            self.db.execute("DELETE FROM revision_instruments WHERE revision_id=?",(self.revision_id,))
            for idx in self.instrument_list.curselection():self.db.execute("INSERT INTO revision_instruments(revision_id,instrument_id) VALUES(?,?)",(self.revision_id,self.instrument_rows[idx]['id']))
            self.db.execute("DELETE FROM revision_attachments WHERE revision_id=?",(self.revision_id,))
            for a in self.attachments:
                stored=a.get('stored_path','')
                if not stored and a.get('source_path'):stored=self.db.copy_attachment(a['source_path'])
                if stored:self.db.execute("INSERT INTO revision_attachments(revision_id,category,title,original_name,stored_path,note) VALUES(?,?,?,?,?,?)",(self.revision_id,a.get('category',''),a.get('title',''),a.get('original_name') or Path(stored).name,stored,a.get('note','')))
            self.db.execute("DELETE FROM revision_documents WHERE revision_id=?",(self.revision_id,))
            for pos,d in enumerate(self.documents):
                self.db.execute("INSERT INTO revision_documents(revision_id,doc_type,doc_no,doc_date,author,note,stored_path,sort_order) VALUES(?,?,?,?,?,?,?,?)",(self.revision_id,d.get('doc_type',''),d.get('doc_no',''),d.get('doc_date',''),d.get('author',''),d.get('note',''),d.get('stored_path',''),pos));self._learn_document(d)
            self.db.execute("DELETE FROM revision_standards WHERE revision_id=?",(self.revision_id,))
            for pos,r in enumerate(self.rev_standards):self.db.execute("INSERT INTO revision_standards(revision_id,standard_id,code_snapshot,title_snapshot,status_snapshot,verified_on_snapshot,article_text,note,sort_order) VALUES(?,?,?,?,?,?,?,?,?)",(self.revision_id,r.get('standard_id'),r.get('code_snapshot',''),r.get('title_snapshot',''),r.get('status_snapshot',''),r.get('verified_on_snapshot',''),r.get('article_text',''),r.get('note',''),pos))
            self.db.execute("DELETE FROM revision_networks WHERE revision_id=?",(self.revision_id,))
            for pos,r in enumerate(self.networks):
                self.db.execute("INSERT INTO revision_networks(revision_id,system_name,voltage,scope_text,note,sort_order) VALUES(?,?,?,?,?,?)",(self.revision_id,r.get('system_name',''),r.get('voltage',''),r.get('scope_text',''),r.get('note',''),pos));self.db.learn_value('network_system',r.get('system_name',''))
            self.db.execute("DELETE FROM revision_supplies WHERE revision_id=?",(self.revision_id,))
            for pos,r in enumerate(self.supplies):
                self.db.execute("INSERT INTO revision_supplies(revision_id,supply_type,designation,voltage,backup,note,sort_order) VALUES(?,?,?,?,?,?,?)",(self.revision_id,r.get('supply_type',''),r.get('designation',''),r.get('voltage',''),r.get('backup',''),r.get('note',''),pos));self.db.learn_value('supply_type',r.get('supply_type',''))
            self.db.execute("DELETE FROM revision_protection_measures WHERE revision_id=?",(self.revision_id,))
            for pos,r in enumerate(self.protection_measures):
                self.db.execute("INSERT INTO revision_protection_measures(revision_id,catalog_id,group_snapshot,label_snapshot,csn_ref_snapshot,en_ref_snapshot,note,sort_order) VALUES(?,?,?,?,?,?,?,?)",(self.revision_id,r.get('catalog_id'),r.get('group_snapshot',''),r.get('label_snapshot',''),r.get('csn_ref_snapshot',''),r.get('en_ref_snapshot',''),r.get('note',''),pos))
                if r.get('catalog_id'):self.db.execute("UPDATE protection_catalog SET usage_count=usage_count+1 WHERE id=?",(r.get('catalog_id'),))
            self.db.execute("DELETE FROM revision_inspection_items WHERE revision_id=?",(self.revision_id,))
            for pos,r in enumerate(self.inspection_items):
                if (r.get('result') or '').upper()=='NEEXISTUJE':continue
                self.db.execute("INSERT INTO revision_inspection_items(revision_id,catalog_id,group_snapshot,label_snapshot,source_ref_snapshot,result,note,sort_order) VALUES(?,?,?,?,?,?,?,?)",(self.revision_id,r.get('catalog_id'),r.get('group_snapshot',''),r.get('label_snapshot',''),r.get('source_ref_snapshot',''),r.get('result','VYHOVUJE'),r.get('note',''),pos))
                if r.get('catalog_id'):self.db.execute("UPDATE inspection_catalog SET usage_count=usage_count+1 WHERE id=?",(r.get('catalog_id'),))
            self.db.execute("DELETE FROM revision_conclusion_blocks WHERE revision_id=?",(self.revision_id,))
            for pos,r in enumerate(self.conclusion_blocks):
                txt=(r.get('text_snapshot') or r.get('text') or '').strip()
                if txt:self.db.execute("INSERT INTO revision_conclusion_blocks(revision_id,title,text_snapshot,sort_order) VALUES(?,?,?,?)",(self.revision_id,r.get('title',''),txt,pos));self.db.learn_value('conclusion_block',txt)
            self.app.refresh_all()
            self._saved_state=self._state_snapshot()
            # Po každém skutečném uložení revize naplánuj rychlou NAS synchronizaci.
            # Běží na pozadí a nikdy kvůli ní nestahujeme DB přes otevřený editor.
            try:self.app.after(350,lambda:self.app.schedule_auto_sync("uložení revize"))
            except Exception:pass
            if show_message:messagebox.showinfo("Uloženo",f"Revize {revision_data['revision_no']} byla uložena.")
            if close_after:self.destroy()
            return True
        except Exception as e:
            messagebox.showerror("Uložení selhalo",str(e));return False

    def save(self):
        return self._persist(close_after=True,show_message=True,confirm_defects=True)

    def _output_options_editor(self,title):
        rt=self.db.fetchone("SELECT stamp_path,signature_path FROM rt_profile WHERE id=1")
        d=OutputOptionsDialog(self,title,bool(rt and rt['stamp_path'] and Path(rt['stamp_path']).exists()),bool(rt and rt['signature_path'] and Path(rt['signature_path']).exists()));self.wait_window(d);return d.result

    def _open_output(self,path):
        try:
            if os.name=='nt':os.startfile(str(path))
            elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
            else:subprocess.Popen(['xdg-open',str(path)])
        except Exception as e:messagebox.showerror('Otevření souboru',str(e))

    def _generate_editor_pdf(self,path,opts):
        return generate_revision_pdf(self.db,self.revision_id,path,str(BASE_LOGO),include_stamp=opts.get('include_stamp',True),include_signature=opts.get('include_signature',True),created_by=f"PZ-REVIZE {VERSION}")

    def preview_from_editor(self):
        opts=self._output_options_editor('Náhled protokolu' if self.revision_type=='VNEJSI' else 'Náhled revizní zprávy')
        if not opts:return
        if not self._persist(close_after=False,show_message=False,confirm_defects=True):return
        try:
            folder=app_data_dir()/'preview';folder.mkdir(exist_ok=True);no=self.vars['revision_no'].get().strip() or 'revize';path=folder/f"{no}_nahled.pdf";self._generate_editor_pdf(path,opts);self._open_output(path)
        except Exception as e:messagebox.showerror('Náhled se nepodařilo vytvořit',str(e))

    def export_from_editor(self):
        opts=self._output_options_editor('Export protokolu' if self.revision_type=='VNEJSI' else 'Export revizní zprávy')
        if not opts:return
        if not self._persist(close_after=False,show_message=False,confirm_defects=True):return
        no=self.vars['revision_no'].get().strip() or 'revize'
        path=filedialog.asksaveasfilename(title=('Export protokolu' if self.revision_type=='VNEJSI' else 'Export revizní zprávy'),defaultextension='.pdf',initialfile=f'{no}.pdf',filetypes=[('PDF','*.pdf')])
        if not path:return
        try:self._generate_editor_pdf(path,opts);messagebox.showinfo('Export',f"{'Protokol' if self.revision_type=='VNEJSI' else 'Revizní zpráva'} byl uložen:\n{path}")
        except Exception as e:messagebox.showerror('Export se nepodařil',str(e))

    def print_from_editor(self):
        opts=self._output_options_editor('Tisk protokolu' if self.revision_type=='VNEJSI' else 'Tisk revizní zprávy')
        if not opts:return
        if not self._persist(close_after=False,show_message=False,confirm_defects=True):return
        try:
            folder=app_data_dir()/'print';folder.mkdir(exist_ok=True);no=self.vars['revision_no'].get().strip() or 'revize';path=folder/f'{no}_tisk.pdf';self._generate_editor_pdf(path,opts)
            if os.name=='nt':os.startfile(str(path),'print')
            else:self._open_output(path)
        except Exception as e:messagebox.showerror('Tisk se nepodařil',str(e))


class RevisionsPage(BasePage):
    def __init__(self,app,revision_type,title,subtitle):
        self.revision_type=revision_type
        super().__init__(app,title,subtitle)
        tb=ttk.Frame(self.body);tb.pack(fill='x',pady=(0,5));self.search_var=tk.StringVar();ttk.Entry(tb,textvariable=self.search_var,width=34).pack(side='left');self.search_var.trace_add('write',lambda *a:self.refresh())
        create_label = "Nový VV" if revision_type == "VNEJSI" else "Nová revize"
        ttk.Button(tb,text=create_label,style="Accent.TButton",command=lambda:app.open_revision_editor(revision_type)).pack(side='right')
        ttk.Button(tb,text="Upravit",command=self.edit).pack(side='right',padx=4)
        ttk.Button(tb,text="Převzít / kopie bez měření",command=self.duplicate).pack(side='right',padx=4)
        ttk.Button(tb,text="Hlídání termínu",command=self.toggle_deadline_watch).pack(side='right',padx=4)
        ttk.Button(tb,text="Smazat",style="Danger.TButton",command=self.delete).pack(side='right',padx=4)
        outbar=ttk.Frame(self.body);outbar.pack(fill='x',pady=(0,8))
        ttk.Button(outbar,text="Import cizí revize / podkladu",command=self.import_reference).pack(side='left')
        ttk.Button(outbar,text="Export PDF",command=self.export_pdf).pack(side='right')
        ttk.Button(outbar,text="Tisk",command=self.print_report).pack(side='right',padx=4)
        ttk.Button(outbar,text="Náhled",style="Success.TButton",command=self.preview).pack(side='right',padx=4)
        holder=tk.Frame(self.body,bg='white',highlightbackground=COLORS['line'],highlightthickness=1);holder.pack(fill='both',expand=True)
        cols=[('no','Číslo',125),('kind','Druh',105),('customer','Zákazník',205),('subject','Revidované zařízení',280),('date','Vyhotoveno',105),('next','Příští revize',105),('watch','Hlídání',80),('result','Výsledek',120),('status','Stav',100)]
        self.tree=ttk.Treeview(holder,columns=[x[0] for x in cols],show='headings');
        for k,l,w in cols:self.tree.heading(k,text=l);self.tree.column(k,width=w,anchor='w')
        self.tree.pack(fill='both',expand=True,padx=2,pady=2);self.tree.bind('<Double-1>',lambda e:self.edit());self.refresh()
    def selected(self):s=self.tree.selection();return int(s[0]) if s else None
    def refresh(self):
        q=f"%{self.search_var.get().strip()}%" if hasattr(self,'search_var') else "%";rows=self.db.fetchall("""SELECT r.*,c.name customer_name FROM revisions r LEFT JOIN customers c ON c.id=r.customer_id WHERE r.revision_type=? AND (r.revision_no LIKE ? OR c.name LIKE ? OR r.subject LIKE ?) ORDER BY r.id DESC""",(self.revision_type,q,q,q))
        if hasattr(self,'tree'):
            for x in self.tree.get_children():self.tree.delete(x)
            for r in rows:self.tree.insert('', 'end', iid=str(r['id']), values=(r['revision_no'],r['revision_kind'],r['customer_name'],r['subject'],display_date(r['issued_on']),display_date(r['next_revision_on']),'Ano' if int(r['deadline_watch'] if r['deadline_watch'] is not None else 1) else 'Vypnuto',r['result'],r['status']))
    def edit(self):
        i=self.selected();
        if i:self.app.open_revision_editor(self.revision_type,i)
    def delete(self):
        i=self.selected();
        if i and messagebox.askyesno("Smazat","Opravdu smazat revizi včetně měření a závad?"):self.db.execute("DELETE FROM revisions WHERE id=?",(i,));self.refresh();self.app.refresh_all()
    def toggle_deadline_watch(self):
        i=self.selected()
        if not i:return
        r=self.db.fetchone("SELECT COALESCE(deadline_watch,1) watch,next_revision_on FROM revisions WHERE id=?",(i,))
        if not r:return
        new=0 if int(r['watch']) else 1
        self.db.execute("UPDATE revisions SET deadline_watch=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(new,i))
        if new and not (r['next_revision_on'] or '').strip():
            messagebox.showinfo("Hlídání termínu","Hlídání je zapnuté, ale termín příští revize zatím není vyplněný.")
        self.refresh();self.app.refresh_all()
    def duplicate(self):
        i=self.selected()
        if not i:return
        src=self.db.fetchone("SELECT revision_no FROM revisions WHERE id=?",(i,))
        d=CopyRevisionDialog(self.app,src['revision_no'] if src else '');self.wait_window(d)
        if not d.result:return
        try:
            new_id=self.db.clone_revision(i,d.result)
            self.refresh();self.app.refresh_all();self.app.open_revision_editor(self.revision_type,new_id)
        except Exception as e:messagebox.showerror("Převzetí revize selhalo",str(e))

    def _output_options(self, title):
        rt=self.db.fetchone("SELECT stamp_path,signature_path FROM rt_profile WHERE id=1")
        d=OutputOptionsDialog(self.app,title,bool(rt and rt['stamp_path'] and Path(rt['stamp_path']).exists()),bool(rt and rt['signature_path'] and Path(rt['signature_path']).exists()))
        self.wait_window(d)
        return d.result

    def _open_file(self,path):
        try:
            if os.name=='nt':os.startfile(str(path))
            elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
            else:subprocess.Popen(['xdg-open',str(path)])
        except Exception as e:messagebox.showerror('Otevření souboru',str(e))

    def _generate_to(self,i,path,opts):
        return generate_revision_pdf(self.db,i,path,str(BASE_LOGO),include_stamp=opts.get('include_stamp',True),include_signature=opts.get('include_signature',True),created_by=f"PZ-REVIZE {VERSION}")

    def preview(self):
        i=self.selected()
        if not i:return
        opts=self._output_options('Náhled revizní zprávy')
        if not opts:return
        try:
            r=self.db.fetchone("SELECT revision_no FROM revisions WHERE id=?",(i,));folder=app_data_dir()/ 'preview';folder.mkdir(exist_ok=True)
            path=folder/f"{r['revision_no'] or 'revize'}_nahled.pdf";self._generate_to(i,path,opts);self._open_file(path)
        except Exception as e:messagebox.showerror('Náhled se nepodařilo vytvořit',str(e))

    def export_pdf(self):
        i=self.selected()
        if not i:return
        opts=self._output_options('Export revizní zprávy')
        if not opts:return
        r=self.db.fetchone("SELECT revision_no FROM revisions WHERE id=?",(i,));path=filedialog.asksaveasfilename(title="Export PDF",defaultextension='.pdf',filetypes=[('PDF','*.pdf')],initialfile=f"{r['revision_no'] or 'revize'}.pdf")
        if path:
            try:self._generate_to(i,path,opts);messagebox.showinfo('Export PDF',f"Revizní zpráva byla vytvořena:\n{path}")
            except Exception as e:messagebox.showerror('Export se nepodařil',str(e))

    def print_report(self):
        i=self.selected()
        if not i:return
        opts=self._output_options('Tisk revizní zprávy')
        if not opts:return
        try:
            r=self.db.fetchone("SELECT revision_no FROM revisions WHERE id=?",(i,));folder=app_data_dir()/ 'print';folder.mkdir(exist_ok=True);path=folder/f"{r['revision_no'] or 'revize'}_tisk.pdf";self._generate_to(i,path,opts)
            if os.name=='nt':
                os.startfile(str(path),'print')
                messagebox.showinfo('Tisk','Dokument byl předán výchozí PDF tiskové aplikaci.')
            elif shutil.which('lp'):
                subprocess.Popen(['lp',str(path)]);messagebox.showinfo('Tisk','Dokument byl odeslán na výchozí tiskárnu.')
            else:
                self._open_file(path);messagebox.showinfo('Tisk','PDF bylo otevřeno. Použij tisk z prohlížeče PDF.')
        except Exception as e:messagebox.showerror('Tisk se nepodařil',str(e))

    def import_reference(self):
        i=self.selected()
        if not i:
            messagebox.showinfo('Import podkladu','Nejprve vyber revizní zprávu.');return
        path=filedialog.askopenfilename(title='Importovat cizí revizní zprávu / podklad',filetypes=[('Dokumenty','*.pdf *.doc *.docx *.odt *.xls *.xlsx *.jpg *.jpeg *.png *.webp'),('Všechny soubory','*.*')])
        if not path:return
        try:
            stored=self.db.copy_attachment(path)
            self.db.execute("INSERT INTO revision_attachments(revision_id,category,title,original_name,stored_path,note) VALUES(?,?,?,?,?,?)",(i,'Cizí revizní zpráva',Path(path).stem,Path(path).name,stored,'Importováno jako podklad revize.'))
            messagebox.showinfo('Import dokončen','Podklad byl uložen k vybrané revizní zprávě.')
        except Exception as e:messagebox.showerror('Import selhal',str(e))

    def pdf(self):
        self.export_pdf()



class NasSyncDialog(Modal):
    MODE_LABELS = {
        "auto": "Automaticky – LAN, potom VPN",
        "lan": "Pouze LAN",
        "vpn": "Pouze VPN",
    }
    LABEL_MODES = {v: k for k, v in MODE_LABELS.items()}

    def __init__(self, app):
        self.app = app
        self.db = app.db
        super().__init__(app, "PZ-REVIZE – NAS synchronizace", 860, 620)
        self.minsize(760, 560)
        cfg = get_sync_settings(self.db)

        head = tk.Frame(self, bg=COLORS["sidebar"])
        head.pack(fill="x")
        top = tk.Frame(head, bg=COLORS["sidebar"])
        top.pack(fill="x", padx=20, pady=(14, 2))
        tk.Label(top, text="NAS synchronizace", bg=COLORS["sidebar"], fg="white", font=("Segoe UI Semibold", 15)).pack(side="left")
        self.live_var = tk.StringVar(value="● stav se načítá…")
        self.live_label = tk.Label(top, textvariable=self.live_var, bg=COLORS["sidebar"], fg="#B8BEC7", font=("Segoe UI Semibold", 9))
        self.live_label.pack(side="right", padx=(12, 0))
        tk.Label(
            head,
            text="PC vždy pracuje s plnou lokální databází. NAS je centrální kopie pro synchronizaci přes LAN i VPN.",
            bg=COLORS["sidebar"], fg="#B8BEC7", font=("Segoe UI", 9)
        ).pack(anchor="w", padx=20, pady=(0, 14))

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="Režim připojení", bg=COLORS["bg"], fg=COLORS["text"], font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.mode_var = tk.StringVar(value=self.MODE_LABELS.get(cfg.get("mode", "auto"), self.MODE_LABELS["auto"]))
        ttk.Combobox(body, textvariable=self.mode_var, values=list(self.MODE_LABELS.values()), state="readonly").grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        tk.Label(body, text="LAN adresa NAS", bg=COLORS["bg"], fg=COLORS["text"], font=("Segoe UI Semibold", 9)).grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.url_var = tk.StringVar(value=cfg.get("lan_url") or cfg.get("url") or "")
        ttk.Entry(body, textvariable=self.url_var).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        tk.Label(body, text="VPN adresa NAS", bg=COLORS["bg"], fg=COLORS["text"], font=("Segoe UI Semibold", 9)).grid(row=4, column=0, sticky="w", pady=(0, 4))
        self.vpn_var = tk.StringVar(value=cfg.get("vpn_url") or "")
        ttk.Entry(body, textvariable=self.vpn_var).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        tk.Label(
            body,
            text="Např. http://100.x.x.x:8767 (Tailscale) nebo adresa NAS dostupná přes WireGuard/OpenVPN. Port 8767 není nutné vystavovat do internetu.",
            wraplength=790, justify="left", bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 8)
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 12))

        tk.Label(body, text="API klíč", bg=COLORS["bg"], fg=COLORS["text"], font=("Segoe UI Semibold", 9)).grid(row=7, column=0, sticky="w", pady=(0, 4))
        self.token_var = tk.StringVar(value=cfg["token"])
        ttk.Entry(body, textvariable=self.token_var, show="•").grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        info = tk.Frame(body, bg="white", highlightbackground=COLORS["line"], highlightthickness=1)
        info.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(2, 14))
        self.state_var = tk.StringVar()
        tk.Label(info, textvariable=self.state_var, bg="white", fg=COLORS["text"], font=("Segoe UI", 9), justify="left", anchor="w", padx=12, pady=10).pack(fill="x")
        self._refresh_state()

        buttons = tk.Frame(body, bg=COLORS["bg"])
        buttons.grid(row=10, column=0, columnspan=2, sticky="ew")
        ttk.Button(buttons, text="Uložit nastavení", command=self._save).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Ověřit NAS", command=self._status).pack(side="left", padx=6)
        ttk.Button(buttons, text="Synchronizovat teď", command=self._push).pack(side="left", padx=6)
        ttk.Button(buttons, text="Stáhnout kompletní DB", style="Success.TButton", command=self._pull).pack(side="left", padx=6)
        ttk.Button(buttons, text="Zavřít", command=self.destroy).pack(side="right")

        note = (
            "Stáhnout kompletní DB je RUČNÍ OBNOVA a nahradí pracovní databázi tohoto PC celým stavem z NAS. "
            "Nepoužívej ji jako běžné řešení konfliktu synchronizace. Běžná synchronizace nyní porovnává oba stavy a lokální revize nikdy automaticky nemaže. "
            "Před ručním nahrazením se vždy vytvoří kompletní lokální záloha."
        )
        tk.Label(body, text=note, wraplength=800, justify="left", bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 8)).grid(row=11, column=0, columnspan=2, sticky="w", pady=(16, 0))
        self.after(200, self._status_silent)

    def _mode_code(self):
        return self.LABEL_MODES.get(self.mode_var.get(), "auto")

    def _save(self):
        save_sync_settings(
            self.db,
            self.url_var.get().strip(),
            self.token_var.get().strip(),
            self.vpn_var.get().strip(),
            self._mode_code(),
        )
        self._refresh_state()
        self.app.refresh_nas_status_now()

    def _refresh_state(self):
        cfg = get_sync_settings(self.db)
        mode = self.MODE_LABELS.get(cfg.get("mode", "auto"), cfg.get("mode", "auto"))
        self.state_var.set(
            f"Lokální DB: {self.db.path}\n"
            f"Lokální generace: {cfg['generation']}    Poslední synchronizace: {cfg['last_sync'] or 'dosud neprovedena'}\n"
            f"Režim: {mode}    Poslední spojení: {cfg.get('last_transport') or '—'}"
        )

    def _current_settings(self):
        return {
            "lan_url": self.url_var.get().strip(),
            "url": self.url_var.get().strip(),
            "vpn_url": self.vpn_var.get().strip(),
            "mode": self._mode_code(),
            "token": self.token_var.get().strip(),
        }

    def _resolve(self, timeout=7):
        return nas_resolve_endpoint(self._current_settings(), timeout=timeout)

    def _set_live(self, ok: bool, text: str, transport: str = ""):
        if ok:
            self.live_var.set(f"● NAS ONLINE · {transport}" if transport else "● NAS ONLINE")
            self.live_label.configure(fg="#65D47B")
        else:
            self.live_var.set("● NAS NEDOSTUPNÝ" if text else "● NAS NENASTAVEN")
            self.live_label.configure(fg="#F59E0B" if text else "#B8BEC7")

    def _status_silent(self):
        self._save()
        if getattr(self, "_probe_running", False):
            return
        self._probe_running = True
        self._probe_queue = queue.Queue()
        def worker():
            try:
                self._probe_queue.put((True, self._resolve(timeout=5)))
            except Exception as e:
                self._probe_queue.put((False, str(e)))
        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll_probe)

    def _poll_probe(self):
        try:
            ok, payload = self._probe_queue.get_nowait()
        except queue.Empty:
            if getattr(self, "_probe_running", False) and self.winfo_exists():
                self.after(100, self._poll_probe)
            return
        self._probe_running = False
        if ok:
            url, transport, st = payload
            self._status_success(url, transport, st, popup=False)
        else:
            self._set_live(False, str(payload))

    def _status_success(self, url, transport, st, popup=True):
        nas_set_setting(self.db, "nas_last_transport", transport)
        self._set_live(True, "", transport)
        self._refresh_state()
        self.app.refresh_nas_status_now()
        if popup:
            counts = st.get("counts") or {}
            msg = (
                f"Připojení: {transport}\n"
                f"Adresa: {url}\n"
                f"Server: {st.get('app')} {st.get('version')}\n"
                f"Generace NAS: {st.get('generation')}\n"
                f"Lokální generace: {get_sync_settings(self.db).get('generation')}\n"
                f"Integrita DB: {st.get('integrity_check')}\n"
                f"Revize: {counts.get('revisions', 0)}    Zákazníci: {counts.get('customers', 0)}\n"
                f"Poslední změna: {st.get('updated_at') or 'bez dat'}"
            )
            messagebox.showinfo("NAS je dostupný", msg, parent=self)

    def _status(self):
        self._save()
        try:
            url, transport, st = self._resolve(timeout=8)
            self._status_success(url, transport, st, popup=True)
        except Exception as e:
            self._set_live(False, str(e))
            self.app.refresh_nas_status_now()
            messagebox.showerror("NAS není dostupný", str(e), parent=self)

    def _push(self):
        self._save()
        try:
            url, transport, _ = self._resolve(timeout=8)
            result = safe_sync_once(self.db, url, self.token_var.get().strip(), VERSION, allow_pull=not bool(self.app._open_revision_editors()))
            nas_set_setting(self.db, "nas_last_transport", transport)
            self._refresh_state(); self.app.refresh_nas_status_now()
            action=result.get('action')
            if action=='pull':
                self.app.refresh_all()
                messagebox.showinfo('Synchronizace dokončena',f"Bezpečně stažen novější stav z NAS.\nGenerace: {result.get('generation')}\nPřipojení: {transport}",parent=self)
            elif action=='push':
                messagebox.showinfo('Synchronizace dokončena',f"Lokální stav byl bezpečně odeslán na NAS.\nGenerace: {result.get('generation')}\nPřipojení: {transport}",parent=self)
            elif action=='equal':
                messagebox.showinfo('Synchronizace',f"PC a NAS jsou synchronní. Generace {result.get('generation')}.",parent=self)
            elif action=='deferred_pull':
                messagebox.showwarning('Synchronizace odložena','NAS obsahuje bezpečně novější stav, ale je otevřené okno revize. Zavři editor revize; synchronizace proběhne automaticky.',parent=self)
            elif action=='conflict':
                comp=result.get('comparison') or {}
                messagebox.showwarning(
                    'Konflikt – nic nebylo přepsáno',
                    'PC i NAS obsahují rozdílné změny. Program z bezpečnostních důvodů NIC nestáhl přes lokální databázi a NIC nepřepsal.\n\n'
                    f"Lokální revize navíc: {len(comp.get('local_only_revisions') or [])}\n"
                    f"NAS revize navíc: {len(comp.get('remote_only_revisions') or [])}\n"
                    f"Změněné společné revize: {len(comp.get('changed_revisions') or [])}\n\n"
                    'Nepoužívej kvůli tomuto konfliktu tlačítko „Stáhnout kompletní DB“ – to je pouze vědomé nahrazení lokální databáze.',
                    parent=self,
                )
            self._refresh_state()
        except Exception as e:
            self.app.refresh_nas_status_now()
            messagebox.showerror("Synchronizace selhala", str(e), parent=self)

    def _pull(self):
        self._save()
        if any(isinstance(w, RevisionEditor) for w in self.app.winfo_children() if isinstance(w, tk.Toplevel)):
            messagebox.showwarning(
                "Otevřená revize",
                "Před stažením kompletní databáze zavři všechna otevřená okna revizí. Jinak by jejich stará data mohla po uložení přepsat právě stažený stav.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Stáhnout kompletní DB z NAS",
            "Stáhnout CELÝ centrální stav z NAS do tohoto počítače?\n\n"
            "Aktuální lokální databáze a přílohy budou předem zazálohovány. "
            "Pokud je v tomto PC revize nebo jiná změna, která na NAS není, stažení se zastaví a lokální data zůstanou zachována.\n\n"
            "Jinak budou DB, fotografie, přílohy, razítko a podpis nahrazeny stavem z NAS.\n\n"
            "Po dokončení bude program pracovat s touto lokální kopií i bez připojení k NAS.",
            parent=self,
        ):
            return
        try:
            url, transport, _ = self._resolve(timeout=8)
            result = pull_from_nas(self.db, url, self.token_var.get().strip())
            nas_set_setting(self.db, "nas_last_transport", transport)
            self.app.refresh_all()
            self._refresh_state()
            self._set_live(True, "", transport)
            self.app.refresh_nas_status_now()
            counts = result.get("counts") or {}
            messagebox.showinfo(
                "Kompletní DB stažena",
                f"Celá databáze NAS je nyní fyzicky uložená v tomto PC.\n\n"
                f"Lokální DB:\n{result.get('local_db')}\n\n"
                f"Generace: {result.get('generation')}    Revize: {counts.get('revisions', 0)}    Zákazníci: {counts.get('customers', 0)}\n"
                f"Připojení: {transport}\n\n"
                f"Záloha původního lokálního stavu:\n{result.get('backup')}",
                parent=self,
            )
        except Exception as e:
            self.app.refresh_nas_status_now()
            messagebox.showerror("Stažení z NAS selhalo", str(e), parent=self)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self._revision_editor_epoch = 0
        self._active_revision_editors = 0
        self.title(f"{APP_TITLE} {VERSION}")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1600, max(1200, sw-80))}x{min(980, max(760, sh-100))}+20+20")
        self.minsize(1180,720)
        self.configure(bg=COLORS['bg'])
        PZStyle.configure(self)
        install_global_mousewheel(self)
        self.db=Database()
        self._nas_result_queue=queue.Queue()
        self._auto_sync_queue=queue.Queue()
        self._auto_sync_running=False
        self._closing=False
        self.icon_ref=make_app_icon(self)
        self.pages={}
        self._build_shell()
        self._build_pages()
        self.show_page('dashboard')
        self.after(30,self._maximize_main)
        self.after(500,self._first_run_hint)
        self.after(1200,self.refresh_nas_status_now)
        self.after(1800,lambda:self.schedule_auto_sync("spuštění"))
        self.after(60000,self._periodic_auto_sync)
        self.bind("<F11>", self._toggle_main_fullscreen)
        self.bind("<Escape>", self._main_escape)
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

    def _maximize_main(self):
        try:
            if os.name=='nt': self.state('zoomed')
            else: self.attributes('-zoomed',True)
        except Exception:
            pass
        self._fullscreen=False

    def _toggle_main_fullscreen(self,event=None):
        self._fullscreen=not getattr(self,'_fullscreen',False)
        try:self.attributes('-fullscreen',self._fullscreen)
        except Exception:pass
        return 'break'

    def _main_escape(self,event=None):
        if getattr(self,'_fullscreen',False):
            self._fullscreen=False
            try:self.attributes('-fullscreen',False)
            except Exception:pass
            return 'break'
        return None

    def _build_shell(self):
        self.sidebar=tk.Frame(self,bg=COLORS['sidebar'],width=232);self.sidebar.pack(side='left',fill='y');self.sidebar.pack_propagate(False)
        brand=tk.Frame(self.sidebar,bg=COLORS['sidebar']);brand.pack(fill='x',padx=16,pady=(18,16))
        try:
            img=Image.open(BASE_LOGO).convert('RGBA');img.thumbnail((64,64));self.logo_ref=ImageTk.PhotoImage(img);tk.Label(brand,image=self.logo_ref,bg=COLORS['sidebar']).pack(side='left')
        except Exception:self.logo_ref=None
        tx=tk.Frame(brand,bg=COLORS['sidebar']);tx.pack(side='left',padx=10);tk.Label(tx,text="PZ-REVIZE",bg=COLORS['sidebar'],fg='white',font=("Segoe UI Semibold",15)).pack(anchor='w');tk.Label(tx,text=VERSION,bg=COLORS['sidebar'],fg='#9DA3AB',font=("Segoe UI",8)).pack(anchor='w')
        nav=tk.Frame(self.sidebar,bg=COLORS['sidebar']);nav.pack(fill='both',expand=True,padx=10)
        self.nav_buttons={}
        items=[
            ('dashboard','Přehled'),('deadlines','Termíny'),('customers','Zákazníci'),
            ('_sep1','REVIZE'),('elektro','Elektrická instalace'),('lps','LPS / hromosvody'),('machine','Strojní zařízení'),('external','Vnější vlivy'),
            ('_sep2','DATABÁZE'),('defects','Závadovník'),('standards','Normy a předpisy'),('learning','Číselníky / učení'),('instruments','Měřicí přístroje'),('rt','Revizní technik')]
        for key,label in items:
            if key.startswith('_sep'):
                tk.Label(nav,text=label,bg=COLORS['sidebar'],fg='#7D838B',font=("Segoe UI Semibold",8)).pack(anchor='w',padx=10,pady=(14,5));continue
            b=tk.Button(nav,text=label,anchor='w',bd=0,relief='flat',bg=COLORS['sidebar'],fg='#E5E7EB',activebackground=COLORS['sidebar2'],activeforeground='white',font=("Segoe UI",10),padx=12,pady=6,command=lambda k=key:self.show_page(k));b.pack(fill='x',pady=1);self.nav_buttons[key]=b
        foot=tk.Frame(self.sidebar,bg=COLORS['sidebar']);foot.pack(fill='x',padx=10,pady=12)
        tk.Button(foot,text="Záloha databáze",anchor='w',bd=0,bg=COLORS['sidebar2'],fg='#D8DBE0',activebackground='#2A2A2A',activeforeground='white',font=("Segoe UI",9),padx=12,pady=5,command=self.backup).pack(fill='x',pady=(0,2))
        tk.Button(foot,text="Export DB",anchor='w',bd=0,bg=COLORS['sidebar2'],fg='#D8DBE0',activebackground='#2A2A2A',activeforeground='white',font=("Segoe UI",9),padx=12,pady=5,command=self.export_database).pack(fill='x',pady=2)
        tk.Button(foot,text="Import DB",anchor='w',bd=0,bg=COLORS['sidebar2'],fg='#D8DBE0',activebackground='#2A2A2A',activeforeground='white',font=("Segoe UI",9),padx=12,pady=5,command=self.import_database).pack(fill='x',pady=2)
        nas_state=tk.Frame(foot,bg=COLORS['sidebar2'],cursor='hand2')
        nas_state.pack(fill='x',pady=(4,2))
        self.nas_dot=tk.Canvas(nas_state,width=14,height=14,bg=COLORS['sidebar2'],highlightthickness=0)
        self.nas_dot.pack(side='left',padx=(10,4),pady=8)
        self.nas_dot_id=self.nas_dot.create_oval(3,3,11,11,fill='#6B7280',outline='')
        self.nas_status_var=tk.StringVar(value='NAS: kontrola…')
        self.nas_status_label=tk.Label(nas_state,textvariable=self.nas_status_var,anchor='w',bg=COLORS['sidebar2'],fg='#D8DBE0',font=("Segoe UI Semibold",8))
        self.nas_status_label.pack(side='left',fill='x',expand=True,padx=(0,6),pady=7)
        for w in (nas_state,self.nas_dot,self.nas_status_label): w.bind('<Button-1>',lambda e:self.open_nas_sync())
        tk.Button(foot,text="NAS synchronizace",anchor='w',bd=0,bg=COLORS['green_dark'],fg='white',activebackground=COLORS['green'],activeforeground='white',font=("Segoe UI Semibold",9),padx=12,pady=5,command=self.open_nas_sync).pack(fill='x',pady=(2,0))
        self.content=ttk.Frame(self);self.content.pack(side='left',fill='both',expand=True)

    def _build_pages(self):
        self.pages['dashboard']=DashboardPage(self);self.pages['deadlines']=DeadlinesPage(self);self.pages['customers']=CustomersPage(self)
        self.pages['elektro']=RevisionsPage(self,'ELEKTRO','Elektrická instalace','Výchozí, pravidelné a mimořádné revize elektrických instalací NN')
        self.pages['lps']=RevisionsPage(self,'LPS','LPS / hromosvody','Revize systémů ochrany před bleskem a uzemnění')
        self.pages['machine']=RevisionsPage(self,'STROJ','Strojní zařízení','Elektrická část strojních zařízení - modul připraven pro další nahrané normy')
        self.pages['external']=RevisionsPage(self,'VNEJSI','Vnější vlivy','Protokoly o určení vnějších vlivů')
        self.pages['defects']=DefectsPage(self);self.pages['standards']=StandardsPage(self);self.pages['learning']=LearningPage(self);self.pages['instruments']=InstrumentsPage(self);self.pages['rt']=RTProfilePage(self)
        for p in self.pages.values():p.place(relx=0,rely=0,relwidth=1,relheight=1)

    def show_page(self,key):
        if key not in self.pages:return
        self.pages[key].tkraise();self.pages[key].refresh()
        for k,b in self.nav_buttons.items():b.configure(bg=COLORS['sidebar2'] if k==key else COLORS['sidebar'],fg='white' if k==key else '#E5E7EB')

    def open_revision_editor(self,rtype,rid=None,initial_job_id=None):
        RevisionEditor(self,rtype,rid,initial_job_id)

    def refresh_all(self):
        for p in self.pages.values():
            try:p.refresh()
            except Exception:pass

    def backup(self):
        try:
            p=self.db.backup();messagebox.showinfo("Záloha",f"Lokální záloha byla vytvořena:\n{p}")
        except Exception as e:messagebox.showerror("Záloha selhala",str(e))

    def export_database(self):
        stamp=datetime.now().strftime('%Y%m%d_%H%M')
        path=filedialog.asksaveasfilename(
            title='Export databáze PZ-REVIZE',
            defaultextension='.db',
            initialfile=f'PZ_REVIZE_{stamp}.db',
            filetypes=[('Databáze PZ-REVIZE','*.db'),('Všechny soubory','*.*')]
        )
        if not path:return
        try:
            out=self.db.export_database(path)
            messagebox.showinfo('Export DB',
                f'Databáze byla exportována:\n{out}\n\n'
                'Poznámka: fotografie a přiložené soubory jsou uloženy mimo SQLite databázi a tento .db soubor je neobsahuje.')
        except Exception as e:messagebox.showerror('Export DB selhal',str(e))

    def import_database(self):
        path=filedialog.askopenfilename(
            title='Import databáze PZ-REVIZE',
            filetypes=[('Databáze PZ-REVIZE','*.db'),('Všechny soubory','*.*')]
        )
        if not path:return
        if not messagebox.askyesno(
            'Import DB',
            'Import nahradí aktuální pracovní databázi vybraným souborem.\n'
            'Před importem program automaticky vytvoří zálohu současné databáze.\n\n'
            'Pokračovat?'
        ):return
        try:
            backup=self.db.import_database(path)
            self.refresh_all()
            msg='Databáze byla načtena a případně převedena na aktuální strukturu programu.'
            if backup:msg+=f'\n\nPředchozí databáze byla zálohována do:\n{backup}'
            msg+='\n\nPokud import pochází z jiného počítače, zkontroluj cesty k přílohám, fotografiím, razítku a podpisu.'
            messagebox.showinfo('Import DB dokončen',msg)
        except Exception as e:messagebox.showerror('Import DB selhal',str(e))

    def _set_nas_indicator(self, state: str, text: str):
        palette={
            'online':('#19B83F','#E7F8EB'),
            'vpn':('#2F6FED','#EAF0FE'),
            'offline':('#D64545','#FCE8E8'),
            'unset':('#6B7280','#ECEFF2'),
            'checking':('#F59E0B','#FFF4D8'),
        }
        dot,_=palette.get(state,palette['unset'])
        try:self.nas_dot.itemconfigure(self.nas_dot_id,fill=dot)
        except Exception:pass
        try:
            if hasattr(self,'dashboard_nas_label'): self.dashboard_nas_label.configure(fg=dot)
        except Exception:pass
        self.nas_status_var.set(text)

    def refresh_nas_status_now(self):
        if getattr(self,'_nas_check_running',False):
            return
        cfg=get_sync_settings(self.db)
        if not cfg.get('token') or not any([cfg.get('lan_url') and 'ADRESA_NAS' not in cfg.get('lan_url',''), cfg.get('vpn_url')]):
            self._set_nas_indicator('unset','NAS: nenastaveno')
            self.after(30000,self.refresh_nas_status_now)
            return
        self._nas_check_running=True
        self._set_nas_indicator('checking','NAS: ověřuji…')
        def worker():
            try:
                url,transport,st=nas_resolve_endpoint(cfg,timeout=4)
                generation=int(st.get('generation') or 0)
                local=int(cfg.get('generation') or 0)
                if generation>local:
                    state='checking'
                    txt=f'NAS: novější DB · {transport} G{generation}'
                elif generation<local:
                    state='checking'
                    txt=f'NAS: lokální novější · {transport} G{generation}'
                else:
                    state='vpn' if transport=='VPN' else 'online'
                    txt=f'NAS: online · {transport} G{generation}'
                self._nas_result_queue.put((state,txt,transport))
            except Exception:
                self._nas_result_queue.put(('offline','NAS: nedostupný',''))
        threading.Thread(target=worker,daemon=True).start()
        self.after(100,self._poll_nas_status_result)

    def _poll_nas_status_result(self):
        try:
            state,text,transport=self._nas_result_queue.get_nowait()
        except queue.Empty:
            if getattr(self,'_nas_check_running',False):
                self.after(100,self._poll_nas_status_result)
            return
        self._finish_nas_check(state,text,transport)

    def _finish_nas_check(self,state,text,transport):
        self._nas_check_running=False
        self._set_nas_indicator(state,text)
        if transport:
            try:nas_set_setting(self.db,'nas_last_transport',transport)
            except Exception:pass
        self.after(30000,self.refresh_nas_status_now)

    def _open_revision_editors(self):
        return [w for w in self.winfo_children() if isinstance(w, RevisionEditor) and isinstance(w, tk.Toplevel) and w.winfo_exists()]

    def _periodic_auto_sync(self):
        if not getattr(self,'_closing',False):
            self.schedule_auto_sync('průběžná synchronizace')
            self.after(60000,self._periodic_auto_sync)

    def schedule_auto_sync(self, reason='průběžná synchronizace'):
        """Run a conservative NAS sync in a worker thread.

        Pull is never allowed while a revision editor is open.  A saved local
        superset is still allowed to push, which is the important offline use
        case: newly created revisions are not destroyed just because NAS has a
        higher generation number.
        """
        if getattr(self,'_closing',False) or getattr(self,'_auto_sync_running',False):
            return
        cfg=get_sync_settings(self.db)
        if not cfg.get('token') or not any([cfg.get('lan_url') and 'ADRESA_NAS' not in cfg.get('lan_url',''), cfg.get('vpn_url')]):
            return
        allow_pull=self._active_revision_editors == 0
        editor_epoch=self._revision_editor_epoch
        can_pull=lambda: self._active_revision_editors == 0 and self._revision_editor_epoch == editor_epoch
        self._auto_sync_running=True
        self._set_nas_indicator('checking',f'NAS: synchronizuji · {reason}')
        def worker():
            try:
                url,transport,_=nas_resolve_endpoint(cfg,timeout=5)
                result=safe_sync_once(self.db,url,cfg.get('token',''),VERSION,allow_pull=allow_pull,can_pull=can_pull)
                self._auto_sync_queue.put((True,result,transport,reason))
            except Exception as exc:
                self._auto_sync_queue.put((False,str(exc),'',reason))
        threading.Thread(target=worker,daemon=True).start()
        self.after(120,self._poll_auto_sync_result)

    def _poll_auto_sync_result(self):
        try:
            ok,payload,transport,reason=self._auto_sync_queue.get_nowait()
        except queue.Empty:
            if getattr(self,'_auto_sync_running',False) and self.winfo_exists():
                self.after(120,self._poll_auto_sync_result)
            return
        self._auto_sync_running=False
        if not ok:
            self._set_nas_indicator('offline','NAS: synchronizace odložena · data zůstala lokálně')
            try:nas_set_setting(self.db,'nas_last_sync_error',str(payload))
            except Exception:pass
            return
        result=payload or {};action=result.get('action');generation=result.get('generation','?')
        if transport:
            try:nas_set_setting(self.db,'nas_last_transport',transport)
            except Exception:pass
        if action=='pull':
            self.refresh_all()
            self._set_nas_indicator('vpn' if transport=='VPN' else 'online',f'NAS: staženo · {transport} G{generation}')
        elif action=='push':
            self._set_nas_indicator('vpn' if transport=='VPN' else 'online',f'NAS: odesláno · {transport} G{generation}')
        elif action=='equal':
            self._set_nas_indicator('vpn' if transport=='VPN' else 'online',f'NAS: synchronní · {transport} G{generation}')
        elif action=='deferred_pull':
            self._set_nas_indicator('checking',f'NAS: novější stav čeká na zavření revize · G{generation}')
        elif action=='conflict':
            comp=result.get('comparison') or {}
            lo=len(comp.get('local_only_revisions') or []);ro=len(comp.get('remote_only_revisions') or []);ch=len(comp.get('changed_revisions') or [])
            self._set_nas_indicator('checking',f'NAS: KONFLIKT – lokální data zachována ({lo}/{ro}/{ch})')
            if reason in ('spuštění','ručně') and getattr(self,'_last_sync_conflict_notice','')!=str(comp):
                self._last_sync_conflict_notice=str(comp)
                messagebox.showwarning('NAS synchronizace',
                    'NAS i tento počítač obsahují rozdílné změny. Automatická synchronizace nic nepřepsala.\n\n'
                    'Lokální data zůstávají beze změny. Otevři NAS synchronizaci pro kontrolu stavu.')
        else:
            self._set_nas_indicator('checking',f'NAS: {result.get("message") or "stav ověřen"}')

    def _on_app_close(self):
        if getattr(self,'_closing',False):
            return 'break'
        # Nejprve bezpečně uzavři editory. Každý si sám vyžádá uložení
        # neuložených změn; zrušení zavření kteréhokoli editoru zruší i konec programu.
        for ed in list(self._open_revision_editors()):
            if not ed.winfo_exists():continue
            if ed._has_unsaved_changes():
                ed._on_close_request()
                try:self.update_idletasks()
                except Exception:pass
                if ed.winfo_exists():
                    return 'break'
            else:
                ed.destroy()
        self._closing=True
        if getattr(self,'_auto_sync_running',False):
            self._set_nas_indicator('checking','NAS: dokončuji synchronizaci před ukončením…')
            self.after(150,self._wait_for_sync_before_close)
            return 'break'
        self._final_sync_and_close()
        return 'break'

    def _wait_for_sync_before_close(self):
        if not getattr(self,'_closing',False):return
        if getattr(self,'_auto_sync_running',False):
            self.after(150,self._wait_for_sync_before_close);return
        self._final_sync_and_close()

    def _final_sync_and_close(self):
        cfg=get_sync_settings(self.db)
        configured=bool(cfg.get('token')) and any([cfg.get('lan_url') and 'ADRESA_NAS' not in cfg.get('lan_url',''),cfg.get('vpn_url')])
        if not configured:
            self.destroy();return
        self._set_nas_indicator('checking','NAS: poslední synchronizace před ukončením…')
        try:self.update_idletasks()
        except Exception:pass
        try:
            url,transport,_=nas_resolve_endpoint(cfg,timeout=6)
            result=safe_sync_once(self.db,url,cfg.get('token',''),VERSION,allow_pull=True)
            action=result.get('action')
            if action=='conflict' or not result.get('ok',True):
                backup=create_complete_local_backup(self.db,prefix='sync_conflict_close')
                comp=result.get('comparison') or {}
                msg=(
                    'Synchronizaci nelze bezpečně dokončit, protože NAS i tento počítač obsahují rozdílné změny.\n\n'
                    'DŮLEŽITÉ: lokální databáze nebyla stažena ani přepsána. Revize v tomto PC zůstaly zachovány.\n'
                    f'Bezpečnostní záloha:\n{backup}\n\n'
                    f'Lokální revize navíc: {len(comp.get("local_only_revisions") or [])}, NAS revize navíc: {len(comp.get("remote_only_revisions") or [])}, změněné společné revize: {len(comp.get("changed_revisions") or [])}.\n\n'
                    'Zavřít program i bez dokončené synchronizace?'
                )
                if not messagebox.askyesno('Konflikt synchronizace – data zachována',msg,parent=self):
                    self._closing=False;self.refresh_nas_status_now();return
            self.destroy()
        except Exception as exc:
            try:backup=create_complete_local_backup(self.db,prefix='sync_offline_close')
            except Exception:backup='zálohu se nepodařilo vytvořit'
            msg=(
                'NAS není dostupný nebo synchronizace selhala.\n\n'
                'Lokální databáze nebyla přepsána. Program vytvořil bezpečnostní kopii a při příštím spuštění synchronizaci zkusí znovu.\n\n'
                f'Záloha: {backup}\n\nChyba: {exc}\n\nZavřít program i tak?'
            )
            if messagebox.askyesno('NAS synchronizace',msg,parent=self):self.destroy()
            else:
                self._closing=False;self.refresh_nas_status_now()

    def open_nas_sync(self):
        NasSyncDialog(self)

    def _first_run_hint(self):
        rt=self.db.fetchone("SELECT name FROM rt_profile WHERE id=1")
        if not rt or not rt['name']:
            messagebox.showinfo("PZ-REVIZE","Program je připraven. Jako první doporučuji vyplnit Revizní technik a Měřicí přístroje.\n\nZávadovník lze rovnou importovat z Excelu (včetně struktury NORMA / ZÁVADY / ČLÁNEK / POPIS).")


if __name__ == '__main__':
    app=App();app.mainloop()
