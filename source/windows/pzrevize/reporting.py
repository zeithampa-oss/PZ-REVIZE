from __future__ import annotations

import os
import re
import json
from collections import defaultdict, OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.graphics.barcode import code128
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
    KeepTogether, KeepInFrame, HRFlowable, Flowable
)

from .external_influences import (
    STANDARD_CODE as EXTERNAL_STANDARD_CODE, DISPLAY_COLUMNS as EXTERNAL_COLUMNS,
    MEASURE_LIBRARY as EXTERNAL_MEASURES, parse_values_json as external_parse_values,
    normalize_measure_codes as external_normalize_measures, measure_codes_list as external_measure_codes_list,
    merge_legacy_rows as external_merge_legacy_rows, room_warnings as external_room_warnings,
    classify_environment as external_classify_environment, abnormal_codes as external_abnormal_codes,
    INFLUENCE_META as EXTERNAL_META, GROUP_TITLES as EXTERNAL_GROUP_TITLES,
    CHECKLIST_OPTIONS as EXTERNAL_CHECKLIST_OPTIONS, ABNORMAL_VALUES as EXTERNAL_ABNORMAL_VALUES,
    abnormal_measure_entries as external_abnormal_measure_entries, measure_entries as external_measure_entries,
    parse_abnormal_measures_json as external_parse_abnormal_measures,
    PROFILE_LIBRARY as EXTERNAL_PROFILES, checklist_item as external_checklist_item,
    GENERAL_PAGE_2_DEFAULT as EXTERNAL_GENERAL_PAGE_2_DEFAULT,
    GENERAL_PAGE_3_DEFAULT as EXTERNAL_GENERAL_PAGE_3_DEFAULT,
    GENERAL_PAGE_4_DEFAULT as EXTERNAL_GENERAL_PAGE_4_DEFAULT,
    GENERAL_PAGE_5_DEFAULT as EXTERNAL_GENERAL_PAGE_5_DEFAULT,
)


def _font_candidates():
    if os.name == "nt":
        w = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        return [
            (w / "arial.ttf", w / "arialbd.ttf"),
            (w / "calibri.ttf", w / "calibrib.ttf"),
            (w / "segoeui.ttf", w / "segoeuib.ttf"),
        ]
    return [
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
    ]


def setup_fonts() -> tuple[str, str]:
    for regular, bold in _font_candidates():
        if regular.exists() and bold.exists():
            try:
                pdfmetrics.registerFont(TTFont("PZSans", str(regular)))
                pdfmetrics.registerFont(TTFont("PZSansBold", str(bold)))
                return "PZSans", "PZSansBold"
            except Exception:
                pass
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = setup_fonts()
LIGHT = colors.HexColor("#E9EDF1")
ROW_ALT = colors.HexColor("#FAFBFC")
MID = colors.HexColor("#B7BEC7")
DARK = colors.HexColor("#202428")
MUTED = colors.HexColor("#626A73")
WHITE = colors.white
GREEN_SOFT = colors.HexColor("#E4F4E8")
RED_SOFT = colors.HexColor("#FBE6E8")
GREEN_STRONG = colors.HexColor("#2E7D32")
RED_STRONG = colors.HexColor("#B3261E")
BLUE_SOFT = colors.HexColor("#EEF4FB")
CONTENT_W = 190*mm


def _numbered_canvas_factory(created_by: str, report_no: str):
    """Return a ReportLab Canvas class that can print `Strana X / Y` reliably."""
    class NumberedCanvas(pdfcanvas.Canvas):
        def __init__(self, *args, **kwargs):
            pdfcanvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_footer(total)
                pdfcanvas.Canvas.showPage(self)
            pdfcanvas.Canvas.save(self)

        def _draw_footer(self, total):
            page_no = self._pageNumber
            self.saveState()
            self.setFont(FONT, 6.6)
            self.setFillColor(MUTED)
            self.drawString(10*mm, 7.5*mm, f"Vytvořeno v {created_by}")
            self.drawCentredString(A4[0]/2, 7.5*mm, str(report_no or ""))
            self.drawRightString(A4[0]-10*mm, 7.5*mm, f"Strana {page_no} / {total}")
            self.restoreState()

    return NumberedCanvas


def esc(text: Any) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def fmt_date(value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    try:
        return datetime.fromisoformat(s[:10]).strftime("%d.%m.%Y")
    except Exception:
        return s


def _electrical_num(value):
    try:
        text=str(value or '').strip().replace('\xa0',' ').replace(',','.')
        text=re.sub(r'^[<>≤≥~≈\s]+','',text)
        m=re.search(r'[-+]?\d+(?:\.\d+)?',text)
        return float(m.group(0)) if m else None
    except Exception:
        return None


def _breaker_ia_a(row):
    manual=_electrical_num(row['breaker_ia_a'] if 'breaker_ia_a' in row.keys() else '')
    if manual is not None and manual>0:return manual
    current=_electrical_num(row['breaker_current_a'] if 'breaker_current_a' in row.keys() else '')
    char=str(row['breaker_characteristic'] if 'breaker_characteristic' in row.keys() else '').strip().upper()
    factors={'B':5.0,'C':10.0,'D':20.0}
    if current is None or current<=0 or char not in factors:return None
    return current*factors[char]


def _fmt_calc_number(value, decimals=3):
    if value is None:return ''
    text=f"{float(value):.{decimals}f}".rstrip('0').rstrip('.')
    return text.replace('.',',')


def _breaker_summary(row):
    parts=[]
    free=str(row['breaker'] or '').strip() if 'breaker' in row.keys() else ''
    if free:parts.append(free)
    cur=str(row['breaker_current_a'] or '').strip() if 'breaker_current_a' in row.keys() else ''
    char=str(row['breaker_characteristic'] or '').strip() if 'breaker_characteristic' in row.keys() else ''
    if char or cur:
        rating=' / '.join(x for x in [char, (cur+' A' if cur else '')] if x)
        parts.append(rating)
    manual=str(row['breaker_ia_a'] or '').strip() if 'breaker_ia_a' in row.keys() else ''
    ia=_breaker_ia_a(row)
    if manual and ia is not None:parts.append(f"Ia {_fmt_calc_number(ia,2)} A")
    return '; '.join(parts)


def _safe_img(path: str | None, width: float, height: float):
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        im = Image(str(p))
        im._restrictSize(width, height)
        return im
    except Exception:
        return None


def revision_title(rev: Any) -> str:
    rt = rev["revision_type"]
    raw_kind = (rev["revision_kind"] or "").strip()
    kind_map = {
        "pravidelná": "PRAVIDELNÉ",
        "pravidelna": "PRAVIDELNÉ",
        "výchozí": "VÝCHOZÍ",
        "vychozi": "VÝCHOZÍ",
        "mimořádná": "MIMOŘÁDNÉ",
        "mimoradna": "MIMOŘÁDNÉ",
    }
    kind = kind_map.get(raw_kind.lower(), raw_kind.upper())
    if rt == "ELEKTRO":
        return f"ZPRÁVA O {kind} REVIZI ELEKTRICKÉ INSTALACE" if kind else "ZPRÁVA O REVIZI ELEKTRICKÉ INSTALACE"
    if rt == "LPS":
        return f"ZPRÁVA O {kind} REVIZI ZAŘÍZENÍ PRO OCHRANU PŘED ÚČINKY ATMOSFÉRICKÉ ELEKTŘINY" if kind else "ZPRÁVA O REVIZI LPS"
    if rt == "STROJ":
        return f"ZPRÁVA O {kind} REVIZI ELEKTRICKÉHO ZAŘÍZENÍ STROJE" if kind else "ZPRÁVA O REVIZI STROJE"
    if rt == "VNEJSI":
        return "PROTOKOL O URČENÍ VNĚJŠÍCH VLIVŮ"
    return "REVIZNÍ ZPRÁVA"


class RoundedParagraphBox(Flowable):
    """Small rounded technical block used for section headers and key results."""
    def __init__(self, text, width, style, fill=LIGHT, stroke=MID, radius=4, padding=5, align='left'):
        Flowable.__init__(self)
        self.text=text;self.req_width=width;self.style=style;self.fill=fill;self.stroke=stroke;self.radius=radius;self.padding=padding;self.align=align
        self.p=Paragraph(text,style);self.w=width;self.h=0
    def wrap(self,availWidth,availHeight):
        self.w=min(self.req_width,availWidth)
        pw,ph=self.p.wrap(max(1,self.w-2*self.padding),availHeight)
        self.ph=ph;self.h=ph+2*self.padding
        return self.w,self.h
    def draw(self):
        c=self.canv;c.saveState();c.setFillColor(self.fill);c.setStrokeColor(self.stroke);c.setLineWidth(.55)
        c.roundRect(0,0,self.w,self.h,self.radius,stroke=1,fill=1)
        self.p.drawOn(c,self.padding,self.padding)
        c.restoreState()


def _table_style(header=True, font_size=7.4, grid=0.28):
    cmds = [
        ("BOX", (0, 0), (-1, -1), .5, MID),
        ("INNERGRID", (0, 0), (-1, -1), grid, colors.HexColor('#CDD2D8')),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
    ]
    if header:
        cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor('#DDE2E7')),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("LINEBELOW", (0, 0), (-1, 0), .65, colors.HexColor('#8F98A3')),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ]
    return TableStyle(cmds)


def _gray_label(text: str, width=CONTENT_W, font_size=9):
    st=ParagraphStyle("graybar",fontName=FONT_BOLD,fontSize=font_size,leading=font_size+2,textColor=DARK)
    return RoundedParagraphBox(esc(text),width,st,fill=colors.HexColor('#E5E9ED'),stroke=colors.HexColor('#AEB6BF'),radius=5,padding=5)


def _object_name(rev: Any) -> str:
    name = (rev["object_name_text"] or "").strip() if "object_name_text" in rev.keys() else ""
    return name or (rev["subject"] or "").strip()


def _object_location(rev: Any) -> str:
    vals = []
    if "object_address_text" in rev.keys() and rev["object_address_text"]:
        vals.append(str(rev["object_address_text"]).strip())
    city = " ".join(x for x in [str(rev["object_zip_text"] or "").strip() if "object_zip_text" in rev.keys() else "", str(rev["object_city_text"] or "").strip() if "object_city_text" in rev.keys() else ""] if x)
    if city:
        vals.append(city)
    parcel = (rev["object_parcel_text"] or "").strip() if "object_parcel_text" in rev.keys() else ""
    if parcel:
        vals.append(f"parcela / katastr: {parcel}")
    loc = (rev["object_location_note"] or "").strip() if "object_location_note" in rev.keys() else ""
    if loc:
        vals.append(loc)
    return ", ".join(vals)


def _standards_line(rows) -> str:
    vals=[]
    for r in rows:
        code=(r["code_snapshot"] or "").strip()
        if code:
            vals.append(code)
    return ", ".join(vals)


def _para(text, style):
    return Paragraph(esc(text), style)


def _defect_norm_refs(row):
    refs=[]
    try:
        txt=row["norm_refs_json"] if "norm_refs_json" in row.keys() else ""
        data=json.loads(txt or "[]")
        if isinstance(data,list):
            for x in data:
                if isinstance(x,dict):
                    r={"standard":str(x.get("standard") or "").strip(),"article":str(x.get("article") or "").strip(),"citation":str(x.get("citation") or x.get("quote") or "").strip()}
                    if any(r.values()):refs.append(r)
    except Exception:
        refs=[]
    if not refs:
        st=str(row["standard"] or "") if "standard" in row.keys() else "";art=str(row["article"] or "") if "article" in row.keys() else ""
        if st.strip() or art.strip():refs=[{"standard":st.strip(),"article":art.strip(),"citation":""}]
    return refs


def _defect_refs_paragraph(row, style):
    chunks=[]
    for r in _defect_norm_refs(row):
        head=" ".join(x for x in [r.get("standard",""),r.get("article","")] if x).strip()
        line=f"<b>{esc(head)}</b>" if head else ""
        if r.get("citation"):
            cit=esc(r.get("citation"))
            line+=("<br/>" if line else "")+f"<i>{cit}</i>"
        if line:chunks.append(line)
    return Paragraph("<br/><br/>".join(chunks) if chunks else "",style)


class _RotatedHeader(Flowable):
    """Compact vertical label used by the full AA-CB matrix header."""
    def __init__(self, text: str, width=5.4*mm, height=48*mm, font_name=FONT, max_font_size=4.7):
        super().__init__()
        self.text=str(text or '')
        self.width=width
        self.height=height
        self.font_name=font_name
        self.max_font_size=max_font_size

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c=self.canv
        max_len=max(8*mm, self.height-3*mm)
        fs=float(self.max_font_size)
        while fs>3.0 and pdfmetrics.stringWidth(self.text,self.font_name,fs)>max_len:
            fs-=0.1
        c.saveState()
        c.translate(self.width*0.63, 1.5*mm)
        c.rotate(90)
        c.setFont(self.font_name,fs)
        c.drawString(0,-fs*0.34,self.text)
        c.restoreState()


def _external_protocol_canvas_factory(report_no: str, prepared_on: str, revision_seq: str, appendix_count: int):
    """Canvas pro protokol VV ve stylu dodaného vzoru – hlavička nahoře, tabulka dole."""
    class ExternalProtocolCanvas(pdfcanvas.Canvas):
        def __init__(self, *args, **kwargs):
            pdfcanvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states=[]

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total=len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_protocol_frame(total)
                pdfcanvas.Canvas.showPage(self)
            pdfcanvas.Canvas.save(self)

        def _draw_protocol_frame(self,total):
            self.saveState()
            w,h=A4
            self.setStrokeColor(colors.HexColor('#555555'))
            self.setFillColor(DARK)
            self.setFont(FONT_BOLD,6.8)
            y=h-8.2*mm
            self.drawString(10*mm,y,'Souhrnný protokol o určení vnějších vlivů')
            self.drawRightString(w-10*mm,y,f'Č.{report_no or ""}')
            self.setLineWidth(.5);self.line(10*mm,y-2.1*mm,w-10*mm,y-2.1*mm)

            x0=10*mm;y0=4.5*mm;tw=190*mm;rh1=3.5*mm;rh2=4.2*mm
            widths=[48*mm,48*mm,47*mm,47*mm]
            labels=['Datum vypracování:','Revize č.','strana','Počet příloh:']
            values=[prepared_on or '',revision_seq or '0',str(self._pageNumber),str(appendix_count)]
            x=x0
            self.setLineWidth(.45)
            self.rect(x0,y0,tw,rh1+rh2,stroke=1,fill=0)
            for ww in widths[:-1]:
                x+=ww;self.line(x,y0,x,y0+rh1+rh2)
            self.line(x0,y0+rh2,x0+tw,y0+rh2)
            x=x0
            for i,ww in enumerate(widths):
                self.setFont(FONT_BOLD,5.4);self.drawCentredString(x+ww/2,y0+rh2+1.0*mm,labels[i])
                self.setFont(FONT,5.8);self.drawCentredString(x+ww/2,y0+1.25*mm,values[i])
                x+=ww
            self.restoreState()
    return ExternalProtocolCanvas


def _external_value_tokens(group: str, value: Any) -> list[str]:
    text=str(value or '').strip().upper().replace(' ','')
    if not text:
        return []
    if group=='AM' and text=='AM1':
        return ['AM-1-2']
    out=[]
    for token in [x for x in re.split(r'[,;/]+',text) if x]:
        if token=='---':out.append(token)
        elif token.startswith(group):out.append(token)
        elif re.fullmatch(r'\d+(?:-\d+)?',token):out.append(group+token)
        else:out.append(token)
    return out


def _external_profile_name(values: dict[str, str]) -> str:
    for name,profile in EXTERNAL_PROFILES.items():
        pvals=profile.get('values') or {}
        if all(str(values.get(c,'') or '').strip()==str(pvals.get(c,'') or '').strip() for c in EXTERNAL_COLUMNS):
            return name
    return ''


def _external_profile_groups(rows):
    groups=OrderedDict()
    for row in rows:
        vals=external_parse_values(row.get('values_json'))
        mc=external_normalize_measures(row.get('measure_codes',''))
        am=json.dumps(external_parse_abnormal_measures(row.get('abnormal_measures_json')),ensure_ascii=False,sort_keys=True)
        key=(tuple((c,vals.get(c,'')) for c in EXTERNAL_COLUMNS),mc,am)
        groups.setdefault(key,[]).append(row)
    return list(groups.values())


def _external_fixed_info_row(code: str):
    if code=='AJ':
        return ('AJ – Ostatní mechanické namáhání','Zvažuje se; bez samostatné třídy v tabulce ZA.1.','AJ','','','Bez samostatné třídy v pracovním checklistu.','tab. ZA.1, s. 24')
    if code=='BB':
        return ('BB – Elektrický odpor lidského těla','Zvažuje se; bez samostatné třídy v tabulce ZA.1.','BB','','','Bez samostatné třídy v pracovním checklistu.','tab. ZA.1, s. 28')
    return None


def _external_free_text_flowables(text: str, base_style: ParagraphStyle) -> list:
    """Render plain editable text while preserving blank lines, bullets and numbering."""
    bullet_style=ParagraphStyle('vv_free_bullet',parent=base_style,leftIndent=7*mm,firstLineIndent=-4*mm,spaceAfter=1.2)
    number_style=ParagraphStyle('vv_free_number',parent=base_style,leftIndent=7*mm,firstLineIndent=-5*mm,spaceAfter=1.2)
    normal_style=ParagraphStyle('vv_free_normal',parent=base_style,spaceAfter=1.6)
    heading_style=ParagraphStyle('vv_free_heading',parent=normal_style,fontName=FONT_BOLD,spaceBefore=2.0,spaceAfter=2.0)
    formula_style=ParagraphStyle('vv_free_formula',parent=normal_style,fontName=FONT_BOLD,fontSize=max(base_style.fontSize+0.8,9),leading=max(base_style.leading+1.2,11),alignment=TA_CENTER,spaceBefore=2.5,spaceAfter=3.0)
    out=[]
    for raw in str(text or '').splitlines():
        line=raw.rstrip()
        if not line.strip():
            out.append(Spacer(1,2.0*mm))
            continue
        s=line.strip()
        m=re.match(r'^([•\-–])\s+(.*)$',s)
        if m:
            out.append(Paragraph('• '+esc(m.group(2)),bullet_style))
            continue
        m=re.match(r'^(\d+[.)])\s+(.*)$',s)
        if m:
            out.append(Paragraph(esc(m.group(1)+' '+m.group(2)),number_style))
            continue
        if re.match(r'^(?:\(dV/dt\)min\s*=|LEL\s*\(kg/m|Vz\s*=|C\s*=|t\s*=)',s,re.I):
            out.append(Paragraph(esc(s),formula_style))
            continue
        if len(s)<=100 and (s.endswith(':') or s in {'Vzorce použité pro výpočet','Odhad teoretického objemu Vz','Odhad doby přetrvávání výbušné atmosféry t'}):
            out.append(Paragraph(esc(s),heading_style))
            continue
        out.append(Paragraph(esc(s),normal_style))
    return out or [Spacer(1,1)]


def _external_page3_fallback(documents, standards, special) -> str:
    """Backward-compatible page 3 if the new free page has not been saved yet."""
    lines=[]
    premises=str(special.get('premises') or '').strip()
    basis=str(special.get('protocol_basis') or '').strip()
    if premises:
        lines += ['Rozsah posuzovaných prostor:',premises,'']
    if basis:
        lines.append('Podklady:')
        for raw in basis.splitlines():
            item=raw.strip().lstrip('•-– ').strip()
            if item:
                lines.append('• '+item)
        lines.append('')
    if documents:
        if not basis:
            lines.append('Podklady:')
        for d in documents:
            item=' – '.join(x for x in [str(d['doc_type'] or '').strip(),str(d['doc_no'] or '').strip(),str(d['author'] or '').strip(),str(d['note'] or '').strip()] if x)
            if item:
                lines.append('• '+item)
        lines.append('')
    if standards:
        lines.append('Legislativa / použité normy:')
        for row in standards:
            item='  '.join(x for x in [str(row['code_snapshot'] or '').strip(),str(row['title_snapshot'] or '').strip()] if x)
            if item:
                lines.append('• '+item)
    return '\n'.join(lines).strip()


def _external_full_text_page(story: list, text: str, base_style: ParagraphStyle, heading: str = ''):
    """Fill one protocol page. Content shrinks only if it would otherwise spill onto another page."""
    content=[]
    if heading:
        h=ParagraphStyle('vv_full_heading',parent=base_style,fontName=FONT_BOLD,fontSize=10.0,leading=12,spaceAfter=5)
        content.append(Paragraph(esc(heading),h))
    content.extend(_external_free_text_flowables(text,base_style))
    story.append(KeepInFrame(190*mm,247*mm,content,mode='shrink'))


def _generate_external_influences_pdf(db, rev, rt, documents, standards, attachments, special,
                                      output_path, default_logo=None, created_by='PZ-REVIZE'):
    """Samostatný výstup protokolu VV – titulní strana podle vzoru + tabulky prostorů."""
    raw_rows=db.fetchall("SELECT * FROM external_influences WHERE revision_id=? ORDER BY COALESCE(sort_order,id),id",(rev['id'],))
    rows=external_merge_legacy_rows(raw_rows)
    out=Path(output_path);out.parent.mkdir(parents=True,exist_ok=True)
    report_no=str(rev['revision_no'] or '').strip()
    prepared=fmt_date(rev['issued_on'] or rev['finished_on'] or rev['started_on'])
    revision_seq=str(special.get('revision_seq','0') or '0')
    appendix_count=len(attachments)
    doc=SimpleDocTemplate(str(out),pagesize=A4,rightMargin=10*mm,leftMargin=10*mm,topMargin=18*mm,bottomMargin=15*mm,
                          title=f'Souhrnný protokol {report_no}',author=(rt['name'] if rt else created_by))
    styles=getSampleStyleSheet()
    base=ParagraphStyle('vv_base',parent=styles['BodyText'],fontName=FONT,fontSize=8.2,leading=10.4,textColor=DARK,spaceAfter=2)
    small=ParagraphStyle('vv_small',parent=base,fontSize=7.2,leading=8.8)
    tiny=ParagraphStyle('vv_tiny',parent=base,fontSize=6.2,leading=7.3)
    center=ParagraphStyle('vv_center',parent=base,alignment=TA_CENTER)
    cover_title=ParagraphStyle('vv_cover_title',parent=base,fontName=FONT_BOLD,fontSize=13.0,leading=15.0,alignment=TA_CENTER,spaceAfter=2)
    cover_sub=ParagraphStyle('vv_cover_sub',parent=base,fontName=FONT_BOLD,fontSize=9.5,leading=11.0,alignment=TA_CENTER,spaceAfter=1)
    section=ParagraphStyle('vv_section',parent=base,fontName=FONT_BOLD,fontSize=10.0,leading=12,spaceBefore=2,spaceAfter=5)
    story=[]

    # --- 1. strana podle dodaného vzoru ---
    story.append(Spacer(1,8*mm))
    logo=_safe_img(default_logo,48*mm,32*mm)
    if logo:
        logo.hAlign='CENTER';story += [logo,Spacer(1,5*mm)]
    else:
        story.append(Spacer(1,25*mm))
    story.append(Paragraph(f'Souhrnný protokol č. {esc(report_no)}',cover_title))
    default_title_text='o určení vnějších vlivů podle ČSN 33 2000-5-51 ed.3 + Z1+Z2\na určení nebezpečných prostorů dle ČSN 60079-10-2 ed.2\na ČSN EN 60079-10-1 ed.3'
    title_text=str(special.get('protocol_title_text') or '').strip() or default_title_text
    for line in [x.strip() for x in title_text.splitlines() if x.strip()]:
        story.append(Paragraph(esc(line),cover_sub))
    story.append(Spacer(1,10*mm))

    customer_addr=' '.join(x for x in [rev['customer_address'],rev['customer_zip'],rev['customer_city']] if x)
    customer_full=', '.join(x for x in [rev['customer_name'],customer_addr] if x)
    owner=str(special.get('owner') or '').strip() or customer_full
    operator=str(special.get('operator') or '').strip() or customer_full
    obj_name=_object_name(rev);obj_loc=_object_location(rev)
    obj=', '.join(x for x in [obj_name,obj_loc] if x)
    cover_rows=[
        [Paragraph('<b>Majitel:</b>',base),Paragraph(esc(owner),base)],
        [Paragraph('<b>Provozovatel:</b>',base),Paragraph(esc(operator),base)],
        [Paragraph('<b>Objekt:</b>',base),Paragraph(esc(obj),base)],
    ]
    ct=Table(cover_rows,colWidths=[31*mm,148*mm],hAlign='CENTER')
    ct.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    story += [ct,Spacer(1,9*mm)]

    old_committee=[x.strip() for x in str(special.get('committee') or '').splitlines() if x.strip()]
    chair=str(special.get('chairperson') or '').strip() or (old_committee[0] if old_committee else '')
    members=[x.strip() for x in str(special.get('committee_members') or '').splitlines() if x.strip()]
    if not members and len(old_committee)>1:members=old_committee[1:]
    committee_rows=[[Paragraph('<b>Předseda:</b>',base),Paragraph(esc(chair),base),Paragraph('................................................',base)]]
    if members:
        for i,name in enumerate(members):committee_rows.append([Paragraph('<b>Členové:</b>' if i==0 else '',base),Paragraph(esc(name),base),Paragraph('................................................',base)])
    else:
        for i in range(3):committee_rows.append([Paragraph('<b>Členové:</b>' if i==0 else '',base),Paragraph('',base),Paragraph('................................................',base)])
    com=Table(committee_rows,colWidths=[31*mm,94*mm,54*mm],hAlign='CENTER')
    com.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
    story.append(com)
    story.append(PageBreak())

    # --- Obecné: samostatný uživatelský popis celé budovy / areálu ---
    general_text=str(special.get('general_text') or '').strip()
    if general_text:
        story.append(Paragraph('Obecné',section))
        story.extend(_external_free_text_flowables(general_text,base))
        story.append(PageBreak())

    # Normy vybrané na kartě Normy / předpisy se vždy propíší do výsledného protokolu.
    story.append(Paragraph('Použité normy / předpisy',section))
    if standards:
        std_style=ParagraphStyle('vv_std',parent=base,fontSize=7.7,leading=9.5,spaceAfter=3)
        for r in standards:
            rr=dict(r)
            code=str(rr.get('code_snapshot') or '').strip()
            title=str(rr.get('title_snapshot') or '').strip()
            article=str(rr.get('article_text') or '').strip()
            text=(f'<b>{esc(code)}</b>' if code else '<b>Neuvedené označení</b>')
            if title:text += ' – '+esc(title)
            if article:text += '<br/><font size="6.8">Rozsah / článek: '+esc(article)+'</font>'
            story.append(Paragraph('• '+text,std_style))
    else:
        story.append(Paragraph('Nebyly vybrány žádné normy / předpisy.',base))
    story.append(PageBreak())

    # Samostatný vlastní popis posuzovaného objektu. Může přetékat přes více stran.
    building=str(special.get('building_description') or '').strip()
    if not building:
        building='\n'.join(x for x in [str(rev['subject'] or '').strip(),str(rev['scope'] or '').strip(),str(special.get('notes') or '').strip()] if x)
    story.append(Paragraph('Popis posuzovaného objektu',section))
    story.extend(_external_free_text_flowables(building,base))
    story.append(PageBreak())

    # Každý abnormální VV a vybrané třídy s explicitním provozním požadavkem mají vlastní editovatelné opatření. Stejné VV se stejným
    # textem opatření sdílí číslo; pokud je pro stejný kód v jiné místnosti
    # nastaven jiný text, dostane samostatné číslo.
    auto_measure_catalog=OrderedDict()
    room_measure_keys={}
    for rr in rows:
        vals0=external_parse_values(rr.get('values_json'))
        entries0=external_measure_entries(vals0,rr.get('abnormal_measures_json'))
        keys=[]
        for entry in entries0:
            key=(entry['code'],str(entry.get('requirement') or '').strip(),str(entry.get('source') or '').strip())
            auto_measure_catalog.setdefault(key,entry)
            keys.append(key)
        room_measure_keys[id(rr)]=keys
    auto_measure_no={key:str(i+1) for i,key in enumerate(auto_measure_catalog)}

    def _measure_refs_for_room(room):
        return [auto_measure_no[k] for k in room_measure_keys.get(id(room),[]) if k in auto_measure_no]

    def _measure_ref_for_entry(room,entry):
        key=(entry['code'],str(entry.get('requirement') or '').strip(),str(entry.get('source') or '').strip())
        return auto_measure_no.get(key,'')

    story.append(Paragraph('Určení vnějších vlivů',section))
    used_measures=set();room_notes=[]
    if rows:
        detail=ParagraphStyle('vv_detail',parent=small,fontSize=6.45,leading=7.7,spaceAfter=0)
        detail_center=ParagraphStyle('vv_detail_center',parent=detail,alignment=TA_CENTER)
        detail_head=ParagraphStyle('vv_detail_head',parent=detail,fontName=FONT_BOLD,alignment=TA_CENTER)
        detail_group=ParagraphStyle('vv_detail_group',parent=detail,fontName=FONT_BOLD)
        profile_groups=_external_profile_groups(rows)
        for pidx,prows in enumerate(profile_groups,1):
            sample=prows[0];vals=external_parse_values(sample.get('values_json'))
            mc=external_normalize_measures(sample.get('measure_codes',''));used_measures.update(external_measure_codes_list(mc));mc_display=', '.join('D'+x for x in external_measure_codes_list(mc))
            saved_name=str(sample.get('description') or '').strip()
            profile_name=saved_name or _external_profile_name(vals) or f'Vlastní kombinace vnějších vlivů {pidx}'
            env=external_classify_environment(vals)
            abnormal_entries=external_abnormal_measure_entries(vals,sample.get('abnormal_measures_json'))
            measure_entries=external_measure_entries(vals,sample.get('abnormal_measures_json'))
            abnormal=', '.join(x['code'] for x in abnormal_entries) or 'bez rozhodujících abnormálních vlivů'
            auto_refs=', '.join(_measure_refs_for_room(sample)) or '—' 
            rooms_text=[]
            for r in prows:
                floor=str(r.get('floor') or '').strip();no=str(r.get('room_no') or '').strip();name=str(r.get('room_name') or '').strip()
                label=' – '.join(x for x in [no,name] if x)
                if floor:label=f'{floor}: {label}' if label else floor
                if label:rooms_text.append(label)
                if str(r.get('note') or '').strip() and str(r.get('note') or '').strip()!=str(r.get('room_description') or '').strip():room_notes.append((r.get('room_no',''),r.get('room_name',''),r.get('note','')))
            for rr in prows:
                rdesc=str(rr.get('room_description') or '').strip()
                if rdesc:
                    rlabel=' – '.join(x for x in [str(rr.get('room_no') or '').strip(),str(rr.get('room_name') or '').strip()] if x)
                    if rlabel:
                        story.append(Paragraph(f'<b>Popis prostoru {esc(rlabel)}</b>',small))
                    story.extend(_external_free_text_flowables(rdesc,small))
                    story.append(Spacer(1,1.5*mm))
            story.append(KeepTogether([
                Paragraph(esc(profile_name),ParagraphStyle('vv_profile_title',parent=section,fontSize=10.5,leading=12.5,spaceBefore=5,spaceAfter=3)),
                Table([
                    [Paragraph('<b>Objekt / místnosti:</b>',small),Paragraph(esc('; '.join(rooms_text) if rooms_text else 'neuvedeno'),small)],
                    [Paragraph('<b>Prostředí:</b>',small),Paragraph(esc(env),small)],
                    [Paragraph('<b>Rozhodující vlivy:</b>',small),Paragraph(esc(abnormal),small)],
                    [Paragraph('<b>Opatření / požadavky:</b>',small),Paragraph(esc(auto_refs),small)],
                    [Paragraph('<b>Doplňková opatření:</b>',small),Paragraph(esc(mc_display or '—'),small)],
                ],colWidths=[34*mm,156*mm],style=TableStyle([
                    ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
                    ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),('BOX',(0,0),(-1,-1),.35,colors.HexColor('#B7BDC5')),
                    ('INNERGRID',(0,0),(-1,-1),.25,colors.HexColor('#D5D9DE')),
                ])),Spacer(1,2.5*mm)
            ]))

            data=[[Paragraph('<b>Vnější vliv</b>',detail_head),Paragraph('<b>Popis / charakteristika</b>',detail_head),Paragraph('<b>Označení</b>',detail_head),Paragraph('<b>Norm.</b>',detail_head),Paragraph('<b>Abnorm.</b>',detail_head),Paragraph('<b>Opatření</b>',detail_head)]]
            spans=[];row_no=1
            for sec in ('A','B','C'):
                data.append([Paragraph(esc(EXTERNAL_GROUP_TITLES[sec]),detail_group),'','','','','',''])
                spans.append(('SPAN',(0,row_no),(-1,row_no)));row_no+=1
                for group in [c for c in EXTERNAL_COLUMNS if EXTERNAL_META.get(c,{}).get('group')==sec]:
                    if group=='AK' and sec=='A':
                        fixed=_external_fixed_info_row('AJ')
                        if fixed:
                            data.append([Paragraph(esc(fixed[0]),detail),Paragraph(esc(fixed[1]),detail),Paragraph(esc(fixed[2]),detail_center),Paragraph('',detail_center),Paragraph('',detail_center),Paragraph('',detail_center)]);row_no+=1
                    if group=='BC' and sec=='B':
                        fixed=_external_fixed_info_row('BB')
                        if fixed:
                            data.append([Paragraph(esc(fixed[0]),detail),Paragraph(esc(fixed[1]),detail),Paragraph(esc(fixed[2]),detail_center),Paragraph('',detail_center),Paragraph('',detail_center),Paragraph('',detail_center)]);row_no+=1
                    meta=EXTERNAL_META.get(group,{})
                    tokens=_external_value_tokens(group,vals.get(group,''))
                    if not tokens:
                        data.append([Paragraph(esc(f'{group} – {meta.get("name",group)}'),detail),Paragraph('Nevyplněno',detail),Paragraph('',detail_center),Paragraph('',detail_center),Paragraph('',detail_center),Paragraph('',detail_center)]);row_no+=1
                        continue
                    for tidx,token in enumerate(tokens):
                        if token=='---':
                            label='V daném prostoru se samostatně neuplatňuje / ve vzoru neuvedeno';is_abnormal=False
                        else:
                            item=external_checklist_item(token);label=item.get('label','Hodnota není v pracovním číselníku.');is_abnormal=token in EXTERNAL_ABNORMAL_VALUES.get(group,set())
                        influence=f'{group} – {meta.get("name",group)}' if tidx==0 else ''
                        measure_ref=''
                        entry=next((x for x in measure_entries if x.get('code')==token),None)
                        if entry:measure_ref=_measure_ref_for_entry(sample,entry)
                        data.append([
                            Paragraph(esc(influence),detail),Paragraph(esc(label),detail),Paragraph(esc(token),detail_center),
                            Paragraph('X' if not is_abnormal and token!='---' else '',detail_center),Paragraph('X' if is_abnormal else '',detail_center),
                            Paragraph(esc(measure_ref),detail_center)
                        ]);row_no+=1
            widths=[35*mm,82*mm,19*mm,13*mm,18*mm,17*mm]  # 184 mm; safety gutter on A4
            table=Table(data,colWidths=widths,repeatRows=1,hAlign='CENTER')
            st=_table_style(header=True,font_size=6.35,grid=.25)
            st.add('VALIGN',(0,0),(-1,-1),'TOP');st.add('LEFTPADDING',(0,0),(-1,-1),2.0);st.add('RIGHTPADDING',(0,0),(-1,-1),2.0);st.add('TOPPADDING',(0,0),(-1,-1),2.2);st.add('BOTTOMPADDING',(0,0),(-1,-1),2.2)
            for _,a,b in spans:
                st.add('SPAN',a,b);st.add('BACKGROUND',a,b,colors.HexColor('#E9EDF2'));st.add('FONTNAME',a,b,FONT_BOLD)
            table.setStyle(st);story += [table,Spacer(1,4*mm)]

        story.append(PageBreak())
        floors=OrderedDict()
        for rr in rows:
            floors.setdefault(str(rr.get('floor') or 'Bez podlaží'),[]).append(rr)

        matrix_style=ParagraphStyle('vv_matrix',parent=tiny,fontSize=5.05,leading=5.7,spaceAfter=0,alignment=TA_CENTER)
        matrix_left=ParagraphStyle('vv_matrix_left',parent=matrix_style,alignment=TA_LEFT)
        matrix_room=ParagraphStyle('vv_matrix_room',parent=matrix_left,fontName=FONT_BOLD)
        matrix_value_emph=ParagraphStyle('vv_matrix_value_emph',parent=matrix_style,fontName=FONT_BOLD)
        matrix_head=ParagraphStyle('vv_matrix_head',parent=matrix_style,fontName=FONT_BOLD,fontSize=5.1,leading=5.7)
        matrix_title=ParagraphStyle('vv_matrix_title',parent=matrix_head,fontSize=5.5,leading=6.2)

        for fidx,(floor,frows) in enumerate(floors.items()):
            if fidx:
                story.append(PageBreak())
            story.append(Paragraph('Přehled posuzovaných prostorů - kompletní tabulka VV',section))

            # Třířádkové záhlaví podle dodaného vzoru: název vlivu přímo v tabulce,
            # pod ním normový kód. Tím není potřeba oddělená legenda nad tabulkou.
            # Držíme tabulku bezpečně UVNITŘ tiskové šířky.  Předchozí verze měla
            # přesně 190 mm (shodně s doc.width), což některé PDF prohlížeče / tiskové
            # ovladače zobrazily o vlas za pravým okrajem.
            matrix_total_width=max(160*mm, doc.width-4*mm)
            matrix_no_w=13*mm
            matrix_name_w=39*mm
            matrix_measure_w=14*mm
            matrix_code_w=(matrix_total_width-matrix_no_w-matrix_name_w-matrix_measure_w)/len(EXTERNAL_COLUMNS)
            header0=[Paragraph('<b>Č.m.</b>',matrix_head),Paragraph('<b>Název místnosti</b>',matrix_head),
                     Paragraph(f'<b>Vnější vlivy dle {esc(EXTERNAL_STANDARD_CODE)}</b>',matrix_title)] + ['']*(len(EXTERNAL_COLUMNS))
            # header0 has 2 + 1 + len(cols) blanks = one extra cell for Opatření in total.
            header1=['',''] + [_RotatedHeader(EXTERNAL_META.get(c,{}).get('name',c),width=matrix_code_w) for c in EXTERNAL_COLUMNS] + [_RotatedHeader('Opatření',width=matrix_measure_w)]
            header2=['',''] + [Paragraph(f'<b>{esc(c)}</b>',matrix_head) for c in EXTERNAL_COLUMNS] + ['']
            mdata=[header0,header1,header2]
            floor_row=len(mdata)
            mdata.append([Paragraph(f'<b>Podlaží / celek: {esc(floor)}</b>',matrix_head)] + ['']*(len(EXTERNAL_COLUMNS)+2))

            for rr in frows:
                vals1=external_parse_values(rr.get('values_json'))
                refs=_measure_refs_for_room(rr)
                # Číselné doplňkové odkazy se do hlavního sloupce nemíchají, aby
                # nedocházelo ke kolizi s čísly opatření přiřazenými ke konkrétním VV.
                rtext=', '.join(refs)
                required_codes={x.get('code') for x in external_measure_entries(vals1, external_parse_abnormal_measures(rr.get('abnormal_measures_json')))}
                value_cells=[]
                for c in EXTERNAL_COLUMNS:
                    value=str(vals1.get(c,'') or '')
                    tokens=set(_external_value_tokens(c,value))
                    style=matrix_value_emph if tokens.intersection(required_codes) else matrix_style
                    value_cells.append(Paragraph(esc(value),style))
                mdata.append([
                    Paragraph(esc(rr.get('room_no','')),matrix_room),
                    Paragraph(esc(rr.get('room_name','')),matrix_room),
                    *value_cells,
                    Paragraph(esc(rtext or '—'),matrix_value_emph),
                ])

            widths=[matrix_no_w,matrix_name_w]+[matrix_code_w]*len(EXTERNAL_COLUMNS)+[matrix_measure_w]
            row_heights=[6*mm,46*mm,6*mm,6*mm]+[None]*len(frows)
            mt=Table(mdata,colWidths=widths,rowHeights=row_heights,repeatRows=3,hAlign='CENTER')
            mst=TableStyle([
                ('GRID',(0,0),(-1,-1),.28,colors.HexColor('#7F858C')),
                ('BOX',(0,0),(-1,-1),.45,colors.HexColor('#4D5359')),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1),
                ('TOPPADDING',(0,0),(-1,-1),1.2),('BOTTOMPADDING',(0,0),(-1,-1),1.2),
                ('BACKGROUND',(0,0),(-1,2),colors.HexColor('#D9D9D9')),
                ('SPAN',(0,0),(0,2)),('SPAN',(1,0),(1,2)),
                ('SPAN',(2,0),(-1,0)),
                ('SPAN',(0,floor_row),(-1,floor_row)),
                ('FONTNAME',(0,floor_row),(-1,floor_row),FONT_BOLD),
                ('BACKGROUND',(0,floor_row),(-1,floor_row),colors.HexColor('#F4F4F4')),
                ('ALIGN',(0,floor_row),(-1,floor_row),'CENTER'),
                ('TEXTCOLOR',(-1,floor_row+1),(-1,-1),colors.HexColor('#C80000')),
                ('FONTNAME',(-1,floor_row+1),(-1,-1),FONT_BOLD),
            ])
            mt.setStyle(mst)
            story.append(mt)

        # Seznam opatření začíná na nové straně; tabulka místností tak dostane
        # celou šířku i výšku stránky a odpovídá lépe dodanému vzoru.
        if auto_measure_catalog or used_measures:
            story.append(PageBreak())
    else:
        story.append(Paragraph('Nebyly zadány žádné posuzované místnosti / prostory.',small))

    if auto_measure_catalog:
        story.append(Spacer(1,3*mm));story.append(Paragraph('Opatření / požadavky k vnějším vlivům',section))
        mdata=[[Paragraph('<b>Č.</b>',tiny),Paragraph('<b>VV</b>',tiny),Paragraph('<b>Opatření / požadavek</b>',tiny),Paragraph('<b>Zdroj</b>',tiny)]]
        for key,entry in auto_measure_catalog.items():
            mdata.append([Paragraph(esc(auto_measure_no[key]),tiny),Paragraph(esc(entry.get('code','')),tiny),Paragraph(esc(entry.get('requirement') or 'Doplnit konkrétní opatření před uzavřením protokolu.'),tiny),Paragraph(esc(entry.get('source') or '—'),tiny)])
        mt=Table(mdata,colWidths=[12*mm,20*mm,130*mm,28*mm],repeatRows=1);mt.setStyle(_table_style(header=True,font_size=6.2));story.append(mt)

    if used_measures:
        story.append(Paragraph('Doplňková opatření',section))
        mdata=[[Paragraph('<b>Č.</b>',tiny),Paragraph('<b>Opatření / požadavek</b>',tiny)]]
        for code in sorted(used_measures,key=lambda x:int(x) if str(x).isdigit() else 999):
            item=EXTERNAL_MEASURES.get(str(code));text=(f"{item['title']} – {item['text']}" if item else 'Vlastní opatření – viz podklady protokolu.')
            mdata.append([Paragraph('D'+esc(code),tiny),Paragraph(esc(text),tiny)])
        mt=Table(mdata,colWidths=[14*mm,176*mm],repeatRows=1);mt.setStyle(_table_style(header=True,font_size=6.2));story.append(mt)

    if room_notes:
        story.append(Spacer(1,3*mm));story.append(Paragraph('Poznámky k prostorům',section))
        for no,name,note in room_notes:
            label=' – '.join(x for x in [str(no or '').strip(),str(name or '').strip()] if x)
            story.append(Paragraph(f'<b>{esc(label)}</b>: {esc(note)}',small))

    extra=str(special.get('notes') or '').strip()
    if extra and building!=extra:
        story.append(Spacer(1,3*mm));story.append(Paragraph('Doplňující údaje',section));story.append(Paragraph(esc(extra).replace('\n','<br/>'),base))

    if attachments:
        story.append(Spacer(1,3*mm));story.append(Paragraph('Seznam příloh',section))
        for i,a in enumerate(attachments,1):
            title=(a['title'] or a['original_name'] or 'Příloha').strip();story.append(Paragraph(f'{i}. {esc(title)}',small))

    canvasmaker=_external_protocol_canvas_factory(report_no,prepared,revision_seq,appendix_count)
    doc.build(story,canvasmaker=canvasmaker)
    return out


def generate_revision_pdf(db, revision_id: int, output_path: str | Path, default_logo: str | None = None,
                          include_stamp: bool = True, include_signature: bool = True,
                          created_by: str = "PZ-REVIZE") -> Path:
    rev = db.fetchone("""
        SELECT r.*, c.name customer_name, c.ico customer_ico, c.dic customer_dic,
               c.address customer_address, c.city customer_city, c.zip customer_zip,
               c.contact customer_contact, c.phone customer_phone, c.email customer_email
        FROM revisions r
        LEFT JOIN customers c ON c.id=r.customer_id
        WHERE r.id=?
    """, (revision_id,))
    if not rev:
        raise ValueError("Revize nebyla nalezena")
    rt = db.fetchone("SELECT * FROM rt_profile WHERE id=1")
    instruments = db.fetchall("""SELECT i.* FROM instruments i JOIN revision_instruments ri ON ri.instrument_id=i.id WHERE ri.revision_id=? ORDER BY i.name""", (revision_id,))
    defects = db.fetchall("SELECT * FROM revision_defects WHERE revision_id=? ORDER BY id", (revision_id,))
    defect_photos = db.fetchall("SELECT * FROM revision_photos WHERE revision_id=? AND kind='defect' ORDER BY defect_id,sort_order,id", (revision_id,))
    photos_by_defect=defaultdict(list)
    for p in defect_photos: photos_by_defect[p["defect_id"]].append(p)
    attachments = db.fetchall("SELECT * FROM revision_attachments WHERE revision_id=? ORDER BY id", (revision_id,))
    documents = db.fetchall("SELECT * FROM revision_documents WHERE revision_id=? ORDER BY sort_order,id", (revision_id,))
    standards = db.fetchall("SELECT * FROM revision_standards WHERE revision_id=? ORDER BY sort_order,id", (revision_id,))
    networks = db.fetchall("SELECT * FROM revision_networks WHERE revision_id=? ORDER BY sort_order,id", (revision_id,))
    supplies = db.fetchall("SELECT * FROM revision_supplies WHERE revision_id=? ORDER BY sort_order,id", (revision_id,))
    protections = db.fetchall("SELECT * FROM revision_protection_measures WHERE revision_id=? ORDER BY sort_order,id", (revision_id,))
    inspections = db.fetchall("SELECT * FROM revision_inspection_items WHERE revision_id=? AND UPPER(COALESCE(result,''))<>'NEEXISTUJE' ORDER BY sort_order,id", (revision_id,))
    conclusions = db.fetchall("SELECT * FROM revision_conclusion_blocks WHERE revision_id=? ORDER BY sort_order,id", (revision_id,))
    varistors = db.fetchall("SELECT * FROM varistor_measurements WHERE revision_id=? ORDER BY id", (revision_id,)) if rev["revision_type"]=="ELEKTRO" else []
    try:
        special=json.loads(rev["special_json"] or "{}")
    except Exception:
        special={}

    if rev["revision_type"]=="VNEJSI":
        return _generate_external_influences_pdf(
            db, rev, rt, documents, standards, attachments, special,
            output_path, default_logo=default_logo, created_by=created_by
        )

    external_rows_for_status=[]
    if rev["revision_type"]=="VNEJSI":
        raw_ext=db.fetchall("SELECT * FROM external_influences WHERE revision_id=? ORDER BY COALESCE(sort_order,id),id",(revision_id,))
        external_rows_for_status=external_merge_legacy_rows(raw_ext)

    out=Path(output_path);out.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(out),pagesize=A4,rightMargin=10*mm,leftMargin=10*mm,topMargin=18*mm,bottomMargin=15*mm,
                          title=revision_title(rev),author=(rt["name"] if rt else "PZ-REVIZE"))
    styles=getSampleStyleSheet()
    base=ParagraphStyle("base",parent=styles["BodyText"],fontName=FONT,fontSize=8.2,leading=10.3,textColor=DARK,spaceAfter=2)
    small=ParagraphStyle("small",parent=base,fontSize=7.2,leading=8.7)
    instruction_style=ParagraphStyle("instruction",parent=base,fontSize=7.55,leading=9.15,spaceAfter=1.0)
    tiny=ParagraphStyle("tiny",parent=base,fontSize=6.5,leading=7.8)
    bold=ParagraphStyle("bold",parent=base,fontName=FONT_BOLD)
    title_style=ParagraphStyle("title",parent=base,fontName=FONT_BOLD,fontSize=11.8,leading=13.6,alignment=TA_CENTER,spaceAfter=2)
    center=ParagraphStyle("center",parent=base,alignment=TA_CENTER)
    assess=ParagraphStyle("assess",parent=base,fontName=FONT_BOLD,fontSize=10.2,leading=12.5,alignment=TA_CENTER)
    story=[]

    # First-page header: the title stays centered on the sheet. The report number,
    # machine-readable Code 128 barcode and the user's basic logo form a compact
    # identification block in the upper-right corner.
    logo=_safe_img(default_logo,8.5*mm,8.5*mm)
    title_cell=Paragraph(esc(revision_title(rev)),title_style)
    report_no=str(rev["revision_no"] or "").strip()
    id_label_text="ČÍSLO PROTOKOLU" if rev["revision_type"]=="VNEJSI" else "ČÍSLO ZPRÁVY"
    id_label=Paragraph(id_label_text,ParagraphStyle("id_label",parent=tiny,fontName=FONT_BOLD,fontSize=5.2,leading=5.8,alignment=TA_CENTER,spaceAfter=0))
    id_no=Paragraph(f"<b>{esc(report_no)}</b>",ParagraphStyle("id_no",parent=base,fontName=FONT_BOLD,fontSize=9.7,leading=10.2,alignment=TA_CENTER,spaceAfter=0))
    bc=code128.Code128(report_no or "0",barHeight=3.8*mm,barWidth=.14*mm,humanReadable=False)
    id_rows=[[id_label],[id_no],[bc],[logo or Paragraph("",tiny)]]
    id_block=Table(id_rows,colWidths=[30*mm],rowHeights=[4.2*mm,4.4*mm,4.4*mm,9*mm])
    id_block.setStyle(TableStyle([
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
        ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
    ]))
    # Equal empty space on the left keeps the title optically centered on A4.
    head=Table([[Paragraph("",small),title_cell,id_block]],colWidths=[30*mm,130*mm,30*mm])
    head.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),0),
        ("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),
        ("BOTTOMPADDING",(0,0),(-1,-1),1.5),("LINEBELOW",(0,0),(-1,-1),.7,DARK)
    ]))
    story += [head, Spacer(1,1.6*mm)]

    codes=_standards_line(standards)
    if rev["revision_type"]=="ELEKTRO":
        header_basis="Revize provedena dle zákona č. 250/2021 Sb., NV č. 190/2022 Sb., ČSN 33 1500:1991 + Z1 až Z4 a ČSN 33 2000-6 ed. 2."
    elif rev["revision_type"]=="VNEJSI":
        header_basis=("Protokol zpracován podle: "+codes) if codes else f"Protokol zpracován podle: {EXTERNAL_STANDARD_CODE}"
    else:
        header_basis=("Revize provedena dle: "+codes) if codes else ""
    if header_basis:
        story += [Paragraph(esc(header_basis),small),Spacer(1,1.5*mm)]

    customer_addr=" ".join(x for x in [rev["customer_address"],rev["customer_zip"],rev["customer_city"]] if x)
    obj_name=_object_name(rev);obj_loc=_object_location(rev)

    # Compact report metadata; all tables on the first page use the same 190 mm content width.
    if rev["revision_type"]=="VNEJSI":
        meta=[
            [Paragraph("Číslo protokolu",small),Paragraph(f"<b>{esc(rev['revision_no'])}</b>",base),Paragraph("Stav dokumentu",small),Paragraph(f"<b>{esc(rev['status'] or '')}</b>",base)],
            [Paragraph("Datum zpracování",small),Paragraph(esc(fmt_date(rev["issued_on"] or rev["finished_on"] or rev["started_on"])),base),Paragraph("Rozsah prostor",small),Paragraph(esc(special.get('premises','')),small)],
        ]
    else:
        meta=[
            [Paragraph("Ev. č. revizní zprávy",small),Paragraph(f"<b>{esc(rev['revision_no'])}</b>",base),Paragraph("Druh revize",small),Paragraph(f"<b>{esc(rev['revision_kind'])}</b>",base)],
            [Paragraph("Zahájení revize",small),Paragraph(esc(fmt_date(rev["started_on"])),base),Paragraph("Ukončení revize",small),Paragraph(esc(fmt_date(rev["finished_on"])),base)],
            [Paragraph("Datum vyhotovení",small),Paragraph(esc(fmt_date(rev["issued_on"])),base),Paragraph("Třída VTZ",small),Paragraph(f"<b>{esc((rev['vtz_class'] or '')+'. třída' if rev['vtz_class'] else '')}</b>",base)],
        ]
    mt=Table(meta,colWidths=[36*mm,59*mm,36*mm,59*mm])
    mst=_table_style(header=False,font_size=7.4);mst.add('BACKGROUND',(0,0),(0,-1),LIGHT);mst.add('BACKGROUND',(2,0),(2,-1),LIGHT);mst.add('FONTNAME',(0,0),(0,-1),FONT_BOLD);mst.add('FONTNAME',(2,0),(2,-1),FONT_BOLD)
    mt.setStyle(mst);story += [mt,Spacer(1,1.6*mm)]

    # Complete RT identification – this must remain visible in the final report, not only in application settings.
    story += [_gray_label("Revizní technik")]
    if rt:
        rt_addr=" ".join(x for x in [rt["address"],rt["zip"],rt["city"]] if x)
        rt_name=" / ".join(x for x in [rt["business_name"],rt["name"]] if x)
        # On the report front page keep the complete identification of the RT,
        # but do not repeat verbose certificate/authorization scope boilerplate.
        # The scope and validity remain stored and editable in the RT profile.
        cert=("ev. č. "+str(rt["certificate_no"])) if rt["certificate_no"] else ""
        auth=("ev. č. "+str(rt["authorization_no"])) if rt["authorization_no"] else ""
        rtinfo=[
            [Paragraph("Jméno / firma",small),Paragraph(f"<b>{esc(rt_name)}</b>",base),Paragraph("Telefon / e-mail",small),Paragraph(esc(" / ".join(x for x in [rt["phone"],rt["email"]] if x)),small)],
            [Paragraph("Adresa",small),Paragraph(esc(rt_addr),small),Paragraph("IČO / DIČ",small),Paragraph(esc(" / ".join(x for x in [rt["ico"],rt["dic"]] if x)),small)],
            [Paragraph("Osvědčení RT",small),Paragraph(esc(cert),small),Paragraph("Oprávnění",small),Paragraph(esc(auth),small)],
        ]
        rt_table=Table(rtinfo,colWidths=[30*mm,65*mm,30*mm,65*mm])
        rst=_table_style(header=False,font_size=7.2);rst.add('BACKGROUND',(0,0),(0,-1),LIGHT);rst.add('BACKGROUND',(2,0),(2,-1),LIGHT);rst.add('FONTNAME',(0,0),(0,-1),FONT_BOLD);rst.add('FONTNAME',(2,0),(2,-1),FONT_BOLD)
        rt_table.setStyle(rst);story += [rt_table,Spacer(1,1.6*mm)]

    story += [_gray_label("Zákazník / objednatel a revidovaný objekt")]
    cust=[
        [Paragraph("Zákazník / objednatel",small),Paragraph(f"<b>{esc(rev['customer_name'] or '')}</b>",base),Paragraph("IČO / DIČ",small),Paragraph(esc(" / ".join(x for x in [rev["customer_ico"],rev["customer_dic"]] if x)),small)],
        [Paragraph("Adresa zákazníka",small),Paragraph(esc(customer_addr),small),Paragraph("Kontakt",small),Paragraph(esc("; ".join(x for x in [rev["customer_contact"],rev["customer_phone"],rev["customer_email"]] if x)),small)],
        [Paragraph("Revidovaný objekt",small),Paragraph(f"<b>{esc(obj_name)}</b>",base),Paragraph("Adresa / parcela / místo",small),Paragraph(esc(obj_loc),small)],
    ]
    ct=Table(cust,colWidths=[36*mm,59*mm,36*mm,59*mm]);cst=_table_style(header=False,font_size=7.2);cst.add('BACKGROUND',(0,0),(0,-1),LIGHT);cst.add('BACKGROUND',(2,0),(2,-1),LIGHT);cst.add('FONTNAME',(0,0),(0,-1),FONT_BOLD);cst.add('FONTNAME',(2,0),(2,-1),FONT_BOLD);ct.setStyle(cst)
    story += [ct,Spacer(1,1.6*mm)]

    if rev["revision_type"]=="STROJ":
        story += [_gray_label("Identifikace strojního zařízení")]
        machine_rows=[
            [Paragraph("Název / typ",small),Paragraph(f"<b>{esc(' / '.join(dict.fromkeys(x for x in [obj_name,special.get('machine_type','')] if x)))}</b>",base),Paragraph("Druh zařízení",small),Paragraph(esc(special.get('machine_subtype','')),small)],
            [Paragraph("Výrobce",small),Paragraph(esc(special.get('manufacturer','')),small),Paragraph("Výrobní / inventární č.",small),Paragraph(esc(' / '.join(x for x in [special.get('serial',''),special.get('inventory_no','')] if x)),small)],
            [Paragraph("Rok výroby / CE",small),Paragraph(esc(' / '.join(x for x in [special.get('year',''),('CE '+special.get('ce_mark','')) if special.get('ce_mark') else ''] if x)),small),Paragraph("Pn / In",small),Paragraph(esc(' / '.join(x for x in [special.get('power',''),special.get('rated_current','')] if x)),small)],
            [Paragraph("Napájení",small),Paragraph(esc(special.get('supply_voltage','')),small),Paragraph("Řídicí napětí",small),Paragraph(esc(special.get('control_voltage','')),small)],
        ]
        mtm=Table(machine_rows,colWidths=[31*mm,64*mm,31*mm,64*mm])
        mst2=_table_style(header=False,font_size=6.9);mst2.add('BACKGROUND',(0,0),(0,-1),LIGHT);mst2.add('BACKGROUND',(2,0),(2,-1),LIGHT);mst2.add('FONTNAME',(0,0),(0,-1),FONT_BOLD);mst2.add('FONTNAME',(2,0),(2,-1),FONT_BOLD);mtm.setStyle(mst2)
        story += [mtm,Spacer(1,1.4*mm)]

    # Měřicí přístroje jsou součástí revizních zpráv; protokol vnějších vlivů je nepotřebuje.
    if rev["revision_type"]!="VNEJSI":
        story += [_gray_label("Soupis použitých měřicích přístrojů")]
        if instruments:
            data=[[Paragraph("Název",tiny),Paragraph("Typ / výrobce",tiny),Paragraph("Výrobní číslo",tiny),Paragraph("Kalibrace / protokol",tiny),Paragraph("Platnost",tiny)]]
            for i in instruments:
                data.append([_para(i["name"],tiny),_para(" ".join(x for x in [i["manufacturer"],i["model"]] if x),tiny),_para(i["serial_no"],tiny),_para(i["calibration_no"],tiny),_para(fmt_date(i["calibration_due"]),tiny)])
            t=Table(data,colWidths=[44*mm,47*mm,31*mm,40*mm,28*mm],repeatRows=1);t.setStyle(_table_style(header=True,font_size=6.7));story.append(t)
        else:
            story.append(Table([[Paragraph("Nebyl vybrán měřicí přístroj.",small)]],colWidths=[190*mm],style=_table_style(header=False)))
        story += [Paragraph("Uvedené měřicí přístroje mají platnou kalibraci v souladu se zákonem č. 505/1990 Sb.",tiny),Spacer(1,1.5*mm)]

    if networks or supplies:
        story += [_gray_label("Zdroje napájení / napěťové soustavy")]
        # 0.4.3: jedna společná tabulka. Nové záznamy mají celé normalizované
        # označení soustavy v revision_supplies.voltage. Starší samostatné záznamy
        # sítí se zobrazí jako zachovaný legacy řádek, bez umělého párování se zdrojem.
        power_rows=[]
        for sup in supplies:
            power_rows.append((sup["supply_type"],sup["designation"],sup["voltage"],sup["backup"],sup["note"]))
        for net in networks:
            marking=' '.join(x for x in [net["system_name"],net["voltage"]] if x).strip()
            power_rows.append(("Původní záznam sítě / soustavy","",marking,net["scope_text"],net["note"]))
        rows=[[Paragraph("Druh zdroje",tiny),Paragraph("Provozovatel / označení",tiny),Paragraph("Napájecí soustava",tiny),Paragraph("Rozsah / úloha",tiny),Paragraph("Poznámka",tiny)]]
        for src,des,mark,scope,note in power_rows:
            rows.append([_para(src,tiny),_para(des,tiny),_para(mark,tiny),_para(scope,tiny),_para(note,tiny)])
        t=Table(rows,colWidths=[35*mm,38*mm,49*mm,34*mm,34*mm],repeatRows=1)
        t.setStyle(_table_style(header=True,font_size=6.35));story += [t,Spacer(1,1.5*mm)]

    if rev["vtz_class"] and rev["revision_type"]!="VNEJSI":
        noun="elektrická instalace" if rev["revision_type"]=="ELEKTRO" else "elektrické zařízení"
        story += [Paragraph(f"Revidovaná {noun} je vyhrazeným technickým zařízením <b>{esc(rev['vtz_class'])}. třídy</b>, podle NV č. 190/2022 Sb. § 4.",small)]

    if rev["revision_type"]=="VNEJSI":
        story += [Spacer(1,1.5*mm),_gray_label("STAV PROTOKOLU")]
        if not external_rows_for_status:
            assess_text="VNĚJŠÍ VLIVY NEBYLY ZADÁNY"
            assess_fill,assess_stroke,assess_text_color=LIGHT,MID,DARK
        else:
            incomplete=any(external_classify_environment(external_parse_values(r.get('values_json')))=='K DOPLNĚNÍ' or any(w.startswith('chybí') or w.startswith('nevyplněné') for w in external_room_warnings(r)) for r in external_rows_for_status)
            if incomplete:
                assess_text="PROTOKOL OBSAHUJE ÚDAJE K DOPLNĚNÍ"
                assess_fill,assess_stroke,assess_text_color=colors.HexColor('#FFF4E5'),colors.HexColor('#D98200'),colors.HexColor('#A65F00')
            else:
                assess_text="VNĚJŠÍ VLIVY BYLY URČENY PRO UVEDENÝ ROZSAH PROSTORŮ"
                assess_fill,assess_stroke,assess_text_color=GREEN_SOFT,GREEN_STRONG,GREEN_STRONG
        assess_result=ParagraphStyle("assess_result",parent=assess,textColor=assess_text_color)
        story.append(RoundedParagraphBox(assess_text,190*mm,assess_result,fill=assess_fill,stroke=assess_stroke,radius=6,padding=7))
    else:
        story += [Spacer(1,1.5*mm),_gray_label("CELKOVÝ POSUDEK")]
        result_norm=str(rev["result"] or "").strip().lower()
        if "nevyhov" in result_norm:
            assess_text="ELEKTRICKÉ ZAŘÍZENÍ NENÍ Z HLEDISKA BEZPEČNOSTI SCHOPNO PROVOZU"
            assess_fill,assess_stroke,assess_text_color=RED_SOFT,RED_STRONG,RED_STRONG
        elif "vyhov" in result_norm:
            assess_text="ELEKTRICKÉ ZAŘÍZENÍ JE Z HLEDISKA BEZPEČNOSTI SCHOPNO PROVOZU"
            assess_fill,assess_stroke,assess_text_color=GREEN_SOFT,GREEN_STRONG,GREEN_STRONG
        else:
            assess_text="CELKOVÝ POSUDEK NEBYL UZAVŘEN"
            assess_fill,assess_stroke,assess_text_color=LIGHT,MID,DARK
        assess_result=ParagraphStyle("assess_result",parent=assess,textColor=assess_text_color)
        story.append(RoundedParagraphBox(assess_text,190*mm,assess_result,fill=assess_fill,stroke=assess_stroke,radius=6,padding=7))
        if rev["next_revision_on"]:
            story.append(Paragraph(f"V souladu s NV č. 190/2022 Sb. a ČSN 33 2000-6 ed. 2 je doporučený termín příští revize: <b>{esc(fmt_date(rev['next_revision_on']))}</b>",small))

    # One shared signature area. The stamp is deliberately larger than in 0.3.3
    # and shares the same visual block with the RT signature.
    story.append(Spacer(1,4*mm))
    stamp=_safe_img(rt["stamp_path"] if (rt and include_stamp) else None,55*mm,24*mm)
    sig=_safe_img(rt["signature_path"] if (rt and include_signature) else None,58*mm,19*mm)
    stamp_cell=stamp or Spacer(1,23*mm)
    sig_cell=sig or Spacer(1,18*mm)
    inner=Table([[stamp_cell,sig_cell]],colWidths=[88*mm,94*mm],rowHeights=[25*mm])
    inner.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2),
        ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
    ]))
    signature_caption="Podpis zpracovatele: ______________________________" if rev["revision_type"]=="VNEJSI" else "Podpis revizního technika: ______________________________"
    labels=Table([[Paragraph("Razítko",center),Paragraph(signature_caption,center)]],colWidths=[88*mm,94*mm])
    labels.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-1),FONT),("FONTSIZE",(0,0),(-1,-1),6.7),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("LEFTPADDING",(0,0),(-1,-1),1),("RIGHTPADDING",(0,0),(-1,-1),1),
        ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
    ]))
    sign_title="RAZÍTKO A PODPIS ZPRACOVATELE" if rev["revision_type"]=="VNEJSI" else "RAZÍTKO A PODPIS REVIZNÍHO TECHNIKA"
    signbox=Table([
        [Paragraph(f"<b>{sign_title}</b>",base)],
        [inner],
        [labels],
    ],colWidths=[190*mm],rowHeights=[6*mm,25*mm,5*mm])
    signbox.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,MID),("BACKGROUND",(0,0),(-1,0),colors.HexColor('#F3F5F7')),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
        ("TOPPADDING",(0,0),(-1,-1),1.5),("BOTTOMPADDING",(0,0),(-1,-1),1.5),
    ]))
    story += [signbox,Spacer(1,2.2*mm)]

    received=fmt_date(rev["received_on"]) if rev["received_on"] else ""
    hand_title="POTVRZENÍ PŘEVZETÍ PROTOKOLU" if rev["revision_type"]=="VNEJSI" else "POTVRZENÍ PŘEVZETÍ ZPRÁVY"
    hand_text="Protokol převzal objednavatel (osoba odpovědná) dne:" if rev["revision_type"]=="VNEJSI" else "Zprávu o revizi převzal objednavatel (osoba odpovědná) dne:"
    hand=Table([
        [Paragraph(f"<b>{hand_title}</b>",base),""],
        [Paragraph(hand_text,small),Paragraph(f"<b>{esc(received)}</b>" if received else "",small)],
        [Paragraph("Podpis provozovatele (osoby odpovědné):",small),Paragraph("________________________________",center)],
    ],colWidths=[122*mm,68*mm])
    hst=_table_style(header=False,font_size=7.1)
    hst.add("SPAN",(0,0),(-1,0));hst.add("BACKGROUND",(0,0),(-1,0),colors.HexColor('#DDE2E7'));hst.add("FONTNAME",(0,0),(-1,0),FONT_BOLD)
    hst.add("LINEBELOW",(0,0),(-1,0),.65,colors.HexColor('#8F98A3'))
    hand.setStyle(hst);story.append(hand)
    distribution=rev["distribution_text"] or "1× revizní technik, 2× provozovatel"
    story.append(Paragraph(f"<b>Rozdělovník:</b> {esc(distribution)}",tiny))
    story.append(PageBreak())

    # Detailed report body begins on page 2, closely following the numbered table structure of EI.xlsx.
    story += [_gray_label("1. Předmět protokolu" if rev["revision_type"]=="VNEJSI" else "1. Předmět revize")]
    story.append(Paragraph(esc(rev["subject"] or ""),base))
    if rev["scope"]:
        label="Rozsah protokolu" if rev["revision_type"]=="VNEJSI" else "Rozsah revize"
        story.append(Paragraph(f"<b>{label}:</b> {esc(rev['scope'])}",base))
    if rev["revision_type"]=="STROJ":
        if special.get('operating_state'):story.append(Paragraph(f"<b>Stav zařízení při revizi:</b> {esc(special.get('operating_state'))}",base))
        if special.get('changes_since_previous'):story.append(Paragraph(f"<b>Změny od předchozí revize:</b> {esc(special.get('changes_since_previous'))}",base))
        if special.get('supply_description'):story.append(Paragraph(f"<b>Popis / způsob napojení:</b> {esc(special.get('supply_description'))}",base))
    if rev["revision_type"]=="VNEJSI":
        story.append(Paragraph(f"<b>Protokol byl zpracován podle:</b> {esc(codes or EXTERNAL_STANDARD_CODE)}",base))
        vrows=[]
        for label,key in (("Podklad pro určení","protocol_basis"),("Komise / osoby podílející se na určení","committee"),("Rozsah prostor","premises"),("Doplňující údaje","notes")):
            value=str(special.get(key,'') or '').strip()
            if value:vrows.append([Paragraph(f"<b>{esc(label)}</b>",tiny),Paragraph(esc(value).replace('\n','<br/>'),small)])
        if vrows:
            vt=Table(vrows,colWidths=[52*mm,138*mm]);vst=_table_style(header=False,font_size=6.8);vst.add('BACKGROUND',(0,0),(0,-1),LIGHT);vt.setStyle(vst);story.append(vt)
    else:
        story.append(Paragraph(f"<b>Revize byla provedena dle:</b> {esc(codes or 'není zadáno')}",base))
    story.append(Spacer(1,2*mm))

    if protections:
        story += [_gray_label("2. Způsob ochrany")]
        pdata=[[Paragraph("Druh ochranného opatření",tiny),Paragraph("Článek dle ČSN 33 2000-4-41 ed.3",tiny),Paragraph("Článek dle ČSN EN 61140 ed.3",tiny)]]
        last_group=None
        group_rows=[]
        for pr in protections:
            group=pr["group_snapshot"] or ""
            if group!=last_group:
                pdata.append([Paragraph(f"<b>{esc(group)}</b>",tiny),"",""]);group_rows.append(len(pdata)-1);last_group=group
            pdata.append([_para(pr["label_snapshot"],small),_para(pr["csn_ref_snapshot"],small),_para(pr["en_ref_snapshot"],small)])
        pt=Table(pdata,colWidths=[95*mm,51*mm,44*mm],repeatRows=1)
        st=_table_style(header=True,font_size=6.7)
        for rr in group_rows:
            st.add("SPAN",(0,rr),(-1,rr));st.add("BACKGROUND",(0,rr),(-1,rr),colors.HexColor("#F2F2F2"));st.add("FONTNAME",(0,rr),(-1,rr),FONT_BOLD)
        pt.setStyle(st);story += [pt,Spacer(1,2*mm)]

    story += [_gray_label("3. Předložená dokumentace")]
    if documents:
        data=[[Paragraph("Druh dokumentace",tiny),Paragraph("Označení / číslo",tiny),Paragraph("Datum",tiny),Paragraph("Zpracovatel",tiny),Paragraph("Poznámka",tiny)]]
        for d in documents:data.append([_para(d["doc_type"],tiny),_para(d["doc_no"],tiny),_para(fmt_date(d["doc_date"]),tiny),_para(d["author"],tiny),_para(d["note"],tiny)])
        dt=Table(data,colWidths=[45*mm,32*mm,23*mm,37*mm,53*mm],repeatRows=1);dt.setStyle(_table_style(header=True,font_size=6.7));story.append(dt)
    else:story.append(Paragraph("Nebyla zadána předložená dokumentace.",small))
    if attachments:
        story.append(Paragraph("<b>Další podklady:</b> "+esc("; ".join((a["title"] or a["original_name"] or "") for a in attachments)),small))
    story.append(Spacer(1,2*mm))

    story += [_gray_label("4. Prohlídka a kontrola")]
    if inspections:
        data=[[Paragraph("Kontrolovaný bod",tiny),Paragraph("Podklad / článek",tiny),Paragraph("Výsledek",tiny),Paragraph("Poznámka",tiny)]]
        last_group=None;group_rows=[]
        for r in inspections:
            group=r["group_snapshot"] or ""
            if group!=last_group:
                data.append([Paragraph(f"<b>{esc(group)}</b>",tiny),"","",""]);group_rows.append(len(data)-1);last_group=group
            data.append([_para(r["label_snapshot"],tiny),_para(r["source_ref_snapshot"],tiny),Paragraph(f"<b>{esc(r['result'] or 'VYHOVUJE')}</b>",tiny),_para(r["note"],tiny)])
        t=Table(data,colWidths=[88*mm,49*mm,25*mm,28*mm],repeatRows=1);st=_table_style(header=True,font_size=6.4)
        for rr in group_rows:
            st.add("SPAN",(0,rr),(-1,rr));st.add("BACKGROUND",(0,rr),(-1,rr),colors.HexColor("#F2F2F2"));st.add("FONTNAME",(0,rr),(-1,rr),FONT_BOLD)
        t.setStyle(st);story.append(t)
        _insp_results=[str(r['result'] or 'VYHOVUJE').upper() for r in inspections]
        if any(x=='NEVYHOVUJE' for x in _insp_results):
            _insp_summary='NEVYHOVUJÍCÍ'
        elif any(x=='NEPROVEDENO' for x in _insp_results):
            _insp_summary='NEUZAVŘENO – některé body nebyly provedeny'
        else:
            _insp_summary='VYHOVUJÍCÍ'
        story += [Spacer(1,1.5*mm),Paragraph(f"<b>Výsledek prohlídky – {esc(_insp_summary)}</b>",small)]
    else:
        empty_inspection_text=("Pro protokol nebyly zadány samostatné body prohlídky / kontroly." if rev["revision_type"]=="VNEJSI" else "Do revizní zprávy nebyly vybrány jednotlivé body prohlídky / kontroly.")
        story.append(Paragraph(empty_inspection_text,small))
    story.append(Spacer(1,2*mm))

    # Structured measurement tables.
    rtype=rev["revision_type"]
    if rtype=="ELEKTRO":
        rows=db.fetchall("SELECT * FROM circuits WHERE revision_id=? ORDER BY COALESCE(sort_order,id),id",(revision_id,))
        story += [_gray_label("5. Zkoušení a měření – struktura")]

        # One unified technical table preserves the real measurement hierarchy:
        # RCD first, then the circuits supplied through it; continuity is its own measurement row.
        headers=[Paragraph("Ozn.",tiny),Paragraph("Popis / měření",tiny),Paragraph("Jištění",tiny),Paragraph("Kabel / vedení",tiny),Paragraph("U",tiny),Paragraph("Riso / Rp",tiny),Paragraph("Zs / Ik",tiny),Paragraph("Výsledek",tiny)]
        data=[headers];row_kinds=['HEADER'];spans=[]
        def fmt_unit(value,unit):
            text=str(value or '').strip()
            if not text:return ''
            compact=text.lower().replace(' ','')
            checks={'Ω':('ω','ohm','ohms'),'MΩ':('mω','mohm','mohms'),'V':('v',),'A':('a',)}.get(unit,(unit.lower(),))
            if any(compact.endswith(x.lower()) for x in checks):return text
            return f"{text} {unit}"
        keymap={str(r["item_key"] or ""):r for r in rows if str(r["item_key"] or "")}
        roots=[r for r in rows if not str(r["parent_key"] or "") or str(r["parent_key"] or "") not in keymap]

        test_defs=[
            ("ac_pos","AC +"),("ac_neg","AC −"),("a_pos","A +"),("a_neg","A −"),
            ("f_pos","F +"),("f_neg","F −"),("b_pos","B +"),("b_neg","B −")
        ]
        def rcd_test_lines(r):
            lines=[]
            for key,label in test_defs:
                trip=str(r[f"rcd_{key}_trip_ma"] or "").strip();tm=str(r[f"rcd_{key}_time_ms"] or "").strip();uc=str(r[f"rcd_{key}_touch_v"] or "").strip()
                if trip or tm or uc:
                    parts=[]
                    if trip:parts.append(f"IΔ={esc(trip)} mA")
                    if tm:parts.append(f"t={esc(tm)} ms")
                    if uc:parts.append(f"Uc={esc(uc)} V")
                    lines.append(f"<b>{label}</b>: "+"; ".join(parts))
            common=[]
            if r["rcd_no_trip_result"]:common.append(f"20–50 % IΔn: <b>{esc(r['rcd_no_trip_result'])}</b>")
            if r["rcd_5x_pos_ms"]:common.append(f"5× IΔn AC+: {esc(r['rcd_5x_pos_ms'])} ms")
            if r["rcd_5x_neg_ms"]:common.append(f"5× IΔn AC−: {esc(r['rcd_5x_neg_ms'])} ms")
            if r["rcd_test_button"]:common.append(f"TEST: <b>{esc(r['rcd_test_button'])}</b>")
            if common:lines.append(" &nbsp;&nbsp; | &nbsp;&nbsp; ".join(common))
            electrical=[]
            if r["measured_voltage"]:electrical.append(f"U={esc(fmt_unit(r['measured_voltage'],'V'))}")
            if r["riso"]:electrical.append(f"Riso={esc(fmt_unit(r['riso'],'MΩ'))}")
            if r["zs"]:electrical.append(f"Zs={esc(fmt_unit(r['zs'],'Ω'))}")
            if r["zs_limit"]:electrical.append(f"mez Zs={esc(fmt_unit(r['zs_limit'],'Ω'))}")
            if r["ik"]:electrical.append(f"Ik={esc(fmt_unit(r['ik'],'A'))}")
            if r["impedance_result"]:electrical.append(f"impedance: <b>{esc(r['impedance_result'])}</b>")
            if r["insulation_result"]:electrical.append(f"izolace: <b>{esc(r['insulation_result'])}</b>")
            if electrical:lines.append("<b>Jištění / elektrická měření:</b> "+"; ".join(electrical))
            return "<br/>".join(lines) if lines else "Měřené hodnoty nebyly zadány."

        children_by_parent=defaultdict(list)
        for rr in rows:
            children_by_parent[str(rr["parent_key"] or "")].append(rr)

        def append_point(r,depth=1):
            prefix=((">"*depth)+" ") if depth else ""
            des=prefix+str(r["designation"] or "Měřicí bod")
            detail=str(r["name"] or "")
            u=fmt_unit(r["measured_voltage"] if "measured_voltage" in r.keys() else "","V")
            riso=fmt_unit(r["riso"],"MΩ")
            zs=fmt_unit(r["zs"],"Ω")
            lim=fmt_unit(r["zs_limit"],"Ω")
            ik=fmt_unit(r["ik"],"A")
            zparts=[]
            if zs:zparts.append("Zs "+zs)
            if lim:zparts.append("mez "+lim)
            if ik:zparts.append("Ik "+ik)
            data.append([_para(des,tiny),_para(detail,tiny),"","",_para(u,tiny),_para(riso,tiny),_para("; ".join(zparts),tiny),Paragraph(f"<b>{esc(r['result'] or r['impedance_result'] or r['insulation_result'] or '')}</b>",tiny)])
            row_kinds.append('POINT')

        def append_continuity(r,depth=1):
            prefix=((">"*depth)+" ") if depth else ""
            desc=" / ".join(x for x in [r["name"],r["board"]] if x)
            rp=fmt_unit(r["pe_continuity"],"Ω")
            lim=fmt_unit(r["zs_limit"],"Ω")
            if lim:rp=(rp+(" / mez "+lim)) if rp else ("mez "+lim)
            rr=len(data)
            data.append([_para(prefix+str(r["designation"] or ""),tiny),Paragraph(f"<b>Spojitost:</b> {esc(desc)}",tiny),"","","",_para(rp,tiny),"",Paragraph(f"<b>{esc(r['pe_result'] or r['result'] or '')}</b>",tiny)])
            row_kinds.append('CONTINUITY');spans.append((1,rr,3,rr))

        def append_note(r,depth=0):
            prefix=((">"*depth)+" ") if depth else ""
            text=esc(str(r["note"] or "")).replace('\n','<br/>')
            rr=len(data)
            data.append([Paragraph(f"<b>{esc(prefix+'Poznámka:')}</b> {text}",tiny),"","","","","","",""])
            row_kinds.append('NOTE');spans.append((0,rr,7,rr))

        def append_blank():
            rr=len(data);data.append([Spacer(1,4*mm),"","","","","","",""]);row_kinds.append('BLANK');spans.append((0,rr,7,rr))

        def append_circuit(r,child=False):
            des=("> " if child else "")+str(r["designation"] or "")
            child_items=children_by_parent.get(str(r["item_key"] or ""),[])
            measured_descendants=[p for p in child_items if str(p["row_type"] or "").upper() in ("POINT","CONTINUITY")]
            # Jakmile má obvod podřízená měření, naměřené hodnoty se tisknou pouze na jejich řádcích.
            # Textové poznámky ani prázdné řádky toto chování neovlivňují.
            riso="" if measured_descendants else fmt_unit((r["riso"] or r["riso_l_pe"] or ""),"MΩ")
            zs="" if measured_descendants else fmt_unit((r["zs"] or ""),"Ω")
            ik="" if measured_descendants else fmt_unit((r["ik"] or ""),"A")
            u="" if measured_descendants else fmt_unit((r["measured_voltage"] if "measured_voltage" in r.keys() else ""),"V")
            ztxt="; ".join(x for x in [("Zs "+zs) if zs else "",("Ik "+ik) if ik else ""] if x)
            data.append([_para(des,tiny),_para(r["name"],tiny),_para(_breaker_summary(r),tiny),_para(r["cable"],tiny),_para(u,tiny),_para(riso,tiny),_para(ztxt,tiny),Paragraph(f"<b>{esc(r['result'] or '')}</b>",tiny)])
            row_kinds.append('CHILD' if child else 'CIRCUIT')
            for item in child_items:
                ityp=str(item["row_type"] or "").upper()
                depth=2 if child else 1
                if ityp=="CONTINUITY":append_continuity(item,depth)
                elif ityp=="POINT":append_point(item,depth)
                elif ityp=="NOTE":append_note(item,depth)
                elif ityp=="BLANK":append_blank()

        for root in roots:
            typ=str(root["row_type"] or "CIRCUIT").upper()
            if typ=='RCD':
                dev=" ".join(x for x in [root["rcd_device_kind"],("typ "+str(root["rcd_type"])) if root["rcd_type"] else "",root["rcd_delay_type"],root["rcd_poles"],root["name"]] if x)
                ratings=" / ".join(x for x in [(str(root["rcd_in_a"])+" A") if root["rcd_in_a"] else "",(str(root["rcd_idn_ma"])+" mA") if root["rcd_idn_ma"] else ""] if x)
                rr=len(data)
                heading="KOMBINOVANÝ CHRÁNIČ RCBO" if str(root["rcd_device_kind"] or "").upper()=="RCBO" else "PROUDOVÝ CHRÁNIČ"
                data.append([Paragraph(f"<b>{esc(root['rcd_designation'] or root['designation'] or '')}</b>",tiny),Paragraph(f"<b>{heading}</b> &nbsp; {esc(dev)}"+(f" &nbsp; <b>{esc(ratings)}</b>" if ratings else ""),small),"","","","","",Paragraph(f"<b>{esc(root['result'] or root['rcd_result'] or '')}</b>",tiny)])
                row_kinds.append('RCD');spans.append((1,rr,6,rr))
                rr2=len(data)
                data.append(["",Paragraph(rcd_test_lines(root),tiny),"","","","","",""])
                row_kinds.append('RCD_DETAIL');spans.append((1,rr2,7,rr2))
                for child in rows:
                    if str(child["parent_key"] or "")==str(root["item_key"] or ""):
                        ctyp=str(child["row_type"] or "CIRCUIT").upper()
                        if ctyp=='BLANK':append_blank()
                        elif ctyp=='NOTE':append_note(child,1)
                        elif ctyp=='CONTINUITY':
                            append_continuity(child,1)
                        elif ctyp=='POINT':
                            # Measurement points belong to a circuit, not directly to RCD; keep legacy-safe rendering.
                            append_point(child,1)
                        else:append_circuit(child,True)
            elif typ=='CONTINUITY':
                append_continuity(root,0)
            elif typ=='POINT':
                append_point(root,0)
            elif typ=='NOTE':append_note(root,0)
            elif typ=='BLANK':append_blank()
            else:append_circuit(root,False)

        if len(data)>1:
            t=Table(data,colWidths=[16*mm,43*mm,21*mm,25*mm,13*mm,21*mm,31*mm,20*mm],repeatRows=1)
            st=_table_style(header=True,font_size=6.3)
            for x1,y1,x2,y2 in spans:st.add('SPAN',(x1,y1),(x2,y2))
            for rr,kind in enumerate(row_kinds):
                if kind=='RCD':
                    st.add('BACKGROUND',(0,rr),(-1,rr),BLUE_SOFT);st.add('FONTNAME',(0,rr),(-1,rr),FONT_BOLD);st.add('LINEABOVE',(0,rr),(-1,rr),.75,colors.HexColor('#7D99B8'))
                elif kind=='RCD_DETAIL':
                    st.add('BACKGROUND',(0,rr),(-1,rr),colors.HexColor('#F7FAFE'));st.add('BOTTOMPADDING',(0,rr),(-1,rr),5)
                elif kind=='CONTINUITY':
                    st.add('BACKGROUND',(0,rr),(-1,rr),GREEN_SOFT);st.add('FONTNAME',(0,rr),(-1,rr),FONT_BOLD)
                elif kind=='POINT':
                    st.add('BACKGROUND',(0,rr),(-1,rr),colors.HexColor('#FFF8E8'));st.add('TEXTCOLOR',(0,rr),(-1,rr),colors.HexColor('#5B4A1F'))
                elif kind=='CHILD':
                    st.add('BACKGROUND',(0,rr),(-1,rr),colors.HexColor('#FCFDFE'))
                elif kind=='NOTE':
                    st.add('BACKGROUND',(0,rr),(-1,rr),colors.HexColor('#F7F7F7'));st.add('TEXTCOLOR',(0,rr),(-1,rr),colors.HexColor('#4B5563'));st.add('TOPPADDING',(0,rr),(-1,rr),4);st.add('BOTTOMPADDING',(0,rr),(-1,rr),4)
                elif kind=='BLANK':
                    st.add('BACKGROUND',(0,rr),(-1,rr),WHITE);st.add('LINEABOVE',(0,rr),(-1,rr),1,WHITE);st.add('LINEBELOW',(0,rr),(-1,rr),1,WHITE);st.add('TOPPADDING',(0,rr),(-1,rr),4);st.add('BOTTOMPADDING',(0,rr),(-1,rr),4)
            t.setStyle(st);story.append(t)
        else:
            story.append(Paragraph("Nebyla zadána měření.",small))

        has_impedance=any(str(r["zs"] or "").strip() for r in rows if "zs" in r.keys())
        has_breaker_eval=any((str(r["breaker_current_a"] or "").strip() or str(r["breaker_ia_a"] or "").strip()) for r in rows if "breaker_current_a" in r.keys())
        if has_impedance or has_breaker_eval:
            story.append(Spacer(1,1.6*mm))
            note_style=ParagraphStyle("impedance_note",fontName=FONT,fontSize=6.7,leading=8.5,textColor=DARK)
            formula_style=ParagraphStyle("impedance_formula_center",fontName=FONT_BOLD,fontSize=10.0,leading=12.0,textColor=DARK,alignment=TA_CENTER)
            status_values=[]
            for r in rows:
                if "zs" not in r.keys() or not str(r["zs"] or "").strip():
                    continue
                val=str(r["impedance_result"] or "").strip().lower() if "impedance_result" in r.keys() else ""
                if val:
                    status_values.append(val)
            if any("nevyhov" in v for v in status_values):
                status_text="Naměřená hodnota impedance poruchové smyčky nesplňuje stanovenou podmínku."
                status_color=RED_STRONG
            elif status_values and all("vyhov" in v and "nevyhov" not in v for v in status_values):
                status_text="Naměřené hodnoty impedance poruchové smyčky vyhovují stanovené podmínce."
                status_color=GREEN_STRONG
            else:
                status_text=""
                status_color=DARK

            intro=(
                "<b>Posouzení impedance poruchové smyčky</b><br/>"
                "Pro ověření podmínky samočinného odpojení od zdroje je naměřená impedance poruchové smyčky "
                "posuzována se zohledněním bezpečnostního součinitele <b>km = 1,5</b>."
            )
            story.append(RoundedParagraphBox(intro,CONTENT_W,note_style,fill=colors.HexColor('#F7F8FA'),stroke=colors.HexColor('#C7CDD4'),radius=4,padding=5))
            story.append(Spacer(1,0.8*mm))
            story.append(RoundedParagraphBox("Zsm ≤ 2/3 × U0 / Ia",CONTENT_W,formula_style,fill=BLUE_SOFT,stroke=colors.HexColor('#A8B8CA'),radius=4,padding=5))
            defs=(
                "<b>Zsm</b> – naměřená impedance poruchové smyčky; "
                "<b>U0</b> – napětí proti zemi; "
                "<b>Ia</b> – proud zajišťující působení ochranného prvku v požadované době."
            )
            story.append(Spacer(1,0.6*mm))
            story.append(Paragraph(defs,note_style))
            if status_text:
                status_style=ParagraphStyle("impedance_status",parent=note_style,fontName=FONT_BOLD,textColor=status_color,spaceBefore=1.5)
                story.append(Paragraph(status_text,status_style))

        if varistors:
            story += [Spacer(1,2*mm),Paragraph("<b>Měření SPD / varistorů</b>",small)]
            data=[[Paragraph("Označení",tiny),Paragraph("Umístění",tiny),Paragraph("Typ / výrobce",tiny),Paragraph("Uc [V]",tiny),Paragraph("Up [kV]",tiny),Paragraph("I test [mA]",tiny),Paragraph("Uvar + [V]",tiny),Paragraph("Uvar − [V]",tiny),Paragraph("Stav",tiny),Paragraph("Výsledek",tiny)]]
            for v in varistors:
                typ=" / ".join(x for x in [v["spd_type"],v["manufacturer"]] if x)
                data.append([_para(v["designation"],tiny),_para(v["board"],tiny),_para(typ,tiny),_para(v["uc_v"],tiny),_para(v["up_kv"],tiny),_para(v["test_current_ma"],tiny),_para(v["uvar_pos_v"],tiny),_para(v["uvar_neg_v"],tiny),_para(v["status_indicator"],tiny),_para(v["result"],tiny)])
            t=Table(data,colWidths=[18*mm,24*mm,32*mm,14*mm,14*mm,15*mm,17*mm,17*mm,20*mm,19*mm],repeatRows=1)
            t.setStyle(_table_style(header=True,font_size=5.7));story.append(t)
    elif rtype=="LPS":
        rows=db.fetchall("SELECT * FROM lps_measurements WHERE revision_id=? ORDER BY id",(revision_id,));story += [_gray_label("5. Zkoušení a měření LPS")]
        data=[["Označení","Typ","Spojitost [Ω]","Zemní odpor [Ω]","Výsledek","Poznámka"]]+[[r["designation"],r["item_type"],r["continuity"],r["earth_resistance"],r["result"],r["note"]] for r in rows]
        t=Table([[_para(x,tiny) for x in row] for row in data],colWidths=[26*mm,39*mm,28*mm,30*mm,26*mm,41*mm],repeatRows=1);t.setStyle(_table_style(header=True,font_size=6.6));story.append(t)
    elif rtype=="STROJ":
        rows=db.fetchall("SELECT * FROM machine_measurements WHERE revision_id=? ORDER BY COALESCE(sort_order,id),id",(revision_id,));story += [_gray_label("5. Zkoušení, měření a funkční zkoušky")]
        data=[[Paragraph("Označení",tiny),Paragraph("Zkouška / měření",tiny),Paragraph("Hodnota",tiny),Paragraph("Jednotka",tiny),Paragraph("Limit / kritérium",tiny),Paragraph("Výsledek",tiny)]]
        row_kinds=['HEADER'];spans=[]
        keymap={str(r["item_key"] or ""):r for r in rows if "item_key" in r.keys() and str(r["item_key"] or "")}
        roots=[r for r in rows if not ("parent_key" in r.keys() and str(r["parent_key"] or "")) or str(r["parent_key"] or "") not in keymap]
        children=defaultdict(list)
        for r in rows:
            if "parent_key" in r.keys():children[str(r["parent_key"] or "")].append(r)
        def add_machine_row(r,depth=0):
            typ=str(r["row_type"] or "MEASUREMENT").upper() if "row_type" in r.keys() else "MEASUREMENT"
            if typ=='BLANK':
                rr=len(data);data.append([Spacer(1,3.5*mm),"","","","",""]);row_kinds.append('BLANK');spans.append((0,rr,5,rr));return
            if typ=='NOTE':
                prefix=((">"*depth)+" ") if depth else ""
                text=esc(str(r["note"] or "")).replace('\n','<br/>')
                rr=len(data);data.append([Paragraph(f"<b>{esc(prefix+'Poznámka:')}</b> {text}",tiny),"","","","",""]);row_kinds.append('NOTE');spans.append((0,rr,5,rr))
            elif typ=='GROUP':
                rr=len(data);label=" - ".join(x for x in [str(r["designation"] or ""),str(r["measurement_type"] or "")] if x) or "Skupina měření"
                data.append([Paragraph(f"<b>{esc(label)}</b>",small),"","","","",""]);row_kinds.append('GROUP');spans.append((0,rr,5,rr))
            else:
                prefix=((">"*depth)+" ") if depth else ""
                designation=str(r["designation"] or "")
                desc=str(r["measurement_type"] or "")
                value=str(r["value"] or "")
                unit=str(r["unit"] or "")
                limit=str(r["limit_value"] or "")
                result=str(r["result"] or "")
                if typ=='FUNCTION':
                    desc=("Funkční zkouška - "+desc) if desc else "Funkční zkouška"
                elif typ=='CIRCUIT':
                    name=str(r["name"] or "") if "name" in r.keys() else ""
                    desc="Klasický obvod" + ((" - "+name) if name else "")
                    parts=[]
                    breaker=str(r["breaker"] or "") if "breaker" in r.keys() else ""
                    ch=str(r["breaker_characteristic"] or "") if "breaker_characteristic" in r.keys() else ""
                    cur=str(r["breaker_current_a"] or "") if "breaker_current_a" in r.keys() else ""
                    if breaker:parts.append(breaker)
                    if ch or cur:parts.append(" ".join(x for x in [ch,(cur+" A" if cur else "")] if x))
                    value="; ".join(parts)
                    unit=""
                    limit=str(r["cable"] or "") if "cable" in r.keys() else ""
                elif typ=='POINT':
                    desc=(str(r["name"] or "") if "name" in r.keys() and r["name"] else "Klasický měřicí bod")
                    vals=[]
                    for lab,key,u in [("U","measured_voltage","V"),("Riso","riso","MΩ"),("Zs","zs","Ω"),("Ik","ik","A")]:
                        if key in r.keys() and str(r[key] or "").strip():vals.append(f"{lab} {r[key]} {u}")
                    value="; ".join(vals);unit=""
                    if "zs_limit" in r.keys() and str(r["zs_limit"] or "").strip():limit=f"Zs ≤ {r['zs_limit']} Ω"
                elif typ=='CONTINUITY':
                    name=str(r["name"] or "") if "name" in r.keys() else ""
                    desc="Spojitost" + ((" - "+name) if name else "")
                    value=str(r["pe_continuity"] or "") if "pe_continuity" in r.keys() else ""
                    unit="Ω";limit=str(r["zs_limit"] or "") if "zs_limit" in r.keys() else ""
                    if "pe_result" in r.keys() and r["pe_result"]:result=str(r["pe_result"] or "")
                elif typ=='RCD':
                    designation=(str(r["rcd_designation"] or "") if "rcd_designation" in r.keys() and r["rcd_designation"] else designation)
                    kind=str(r["rcd_device_kind"] or "RCD") if "rcd_device_kind" in r.keys() else "RCD"
                    rtyp=str(r["rcd_type"] or "") if "rcd_type" in r.keys() else ""
                    desc=" / ".join(x for x in [kind,("typ "+rtyp if rtyp else "")] if x)
                    vals=[]
                    if "rcd_idn_ma" in r.keys() and r["rcd_idn_ma"]:vals.append(f"IΔn {r['rcd_idn_ma']} mA")
                    if "rcd" in r.keys() and r["rcd"]:vals.append(f"t {r['rcd']} ms")
                    if "rcd_trip_ma" in r.keys() and r["rcd_trip_ma"]:vals.append(f"IΔ {r['rcd_trip_ma']} mA")
                    if "rcd_touch_v" in r.keys() and r["rcd_touch_v"]:vals.append(f"Uc {r['rcd_touch_v']} V")
                    value="; ".join(vals);unit="";limit=""
                    if not result and "rcd_result" in r.keys():result=str(r["rcd_result"] or "")
                data.append([_para(prefix+designation,tiny),_para(desc,tiny),_para(value,tiny),_para(unit,tiny),_para(limit,tiny),Paragraph(f"<b>{esc(result)}</b>",tiny)])
                row_kinds.append('FUNCTION' if typ=='FUNCTION' else ('CLASSIC' if typ in ('CIRCUIT','POINT','CONTINUITY','RCD') else 'MEASUREMENT'))
            key=str(r["item_key"] or "") if "item_key" in r.keys() else ""
            for c in children.get(key,[]):add_machine_row(c,depth+1)
        for r in roots:add_machine_row(r,0)
        if len(data)>1:
            t=Table(data,colWidths=[27*mm,69*mm,25*mm,21*mm,24*mm,24*mm],repeatRows=1);st=_table_style(header=True,font_size=6.5)
            for x1,y1,x2,y2 in spans:st.add('SPAN',(x1,y1),(x2,y2))
            for rr,kind in enumerate(row_kinds):
                if kind=='GROUP':st.add('BACKGROUND',(0,rr),(-1,rr),BLUE_SOFT);st.add('FONTNAME',(0,rr),(-1,rr),FONT_BOLD)
                elif kind=='FUNCTION':st.add('BACKGROUND',(0,rr),(-1,rr),GREEN_SOFT)
                elif kind=='CLASSIC':st.add('BACKGROUND',(0,rr),(-1,rr),colors.HexColor('#F8FBFF'))
                elif kind=='NOTE':st.add('BACKGROUND',(0,rr),(-1,rr),colors.HexColor('#F7F7F7'));st.add('TEXTCOLOR',(0,rr),(-1,rr),colors.HexColor('#4B5563'))
                elif kind=='BLANK':st.add('LINEABOVE',(0,rr),(-1,rr),0,WHITE);st.add('LINEBELOW',(0,rr),(-1,rr),0,WHITE)
            t.setStyle(st);story.append(t)
        else:story.append(Paragraph("Nebyla zadána měření ani funkční zkoušky.",small))
    else:
        raw_rows=db.fetchall("SELECT * FROM external_influences WHERE revision_id=? ORDER BY COALESCE(sort_order,id),id",(revision_id,))
        rows=external_merge_legacy_rows(raw_rows)
        story += [_gray_label(f"5. Určení vnějších vlivů – {EXTERNAL_STANDARD_CODE}")]
        if rows:
            grouped=defaultdict(list)
            order=[]
            for r in rows:
                floor=str(r.get('floor') or 'Bez určení podlaží')
                if floor not in grouped:order.append(floor)
                grouped[floor].append(r)
            ext=ParagraphStyle('external_matrix',parent=tiny,fontSize=4.15,leading=4.8,alignment=TA_CENTER,spaceAfter=0)
            ext_left=ParagraphStyle('external_matrix_left',parent=ext,alignment=TA_LEFT)
            used_measures=set()
            widths=[15*mm,34*mm]+[5.65*mm]*len(EXTERNAL_COLUMNS)+[16*mm]
            for floor in order:
                story.append(Paragraph(f"<b>{esc(floor)}</b>",small))
                data=[[Paragraph('<b>Č.m.</b>',ext),Paragraph('<b>Název místnosti</b>',ext)]+[Paragraph(f'<b>{esc(c)}</b>',ext) for c in EXTERNAL_COLUMNS]+[Paragraph('<b>Opatř.</b>',ext)]]
                for r in grouped[floor]:
                    vals=external_parse_values(r.get('values_json'))
                    mc=external_normalize_measures(r.get('measure_codes',''))
                    used_measures.update(external_measure_codes_list(mc))
                    data.append([Paragraph(esc(r.get('room_no','')),ext_left),Paragraph(esc(r.get('room_name','')),ext_left)]+[Paragraph(esc(vals.get(c,'')),ext) for c in EXTERNAL_COLUMNS]+[Paragraph(esc(mc),ext)])
                table=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
                st=_table_style(header=True,font_size=4.15,grid=.2)
                st.add('LEFTPADDING',(0,0),(-1,-1),1.0);st.add('RIGHTPADDING',(0,0),(-1,-1),1.0)
                st.add('TOPPADDING',(0,0),(-1,-1),1.4);st.add('BOTTOMPADDING',(0,0),(-1,-1),1.4)
                st.add('ALIGN',(2,1),(-1,-1),'CENTER')
                table.setStyle(st);story += [table,Spacer(1,1.5*mm)]
            if used_measures:
                story.append(Paragraph('<b>Použitá opatření</b>',small))
                mdata=[[Paragraph('<b>Č.</b>',tiny),Paragraph('<b>Opatření / požadavek</b>',tiny)]]
                for code in sorted(used_measures,key=lambda x:int(x) if str(x).isdigit() else 999):
                    item=EXTERNAL_MEASURES.get(str(code))
                    text=(f"{item['title']} – {item['text']}" if item else 'Vlastní / neznámý odkaz – viz podklady protokolu.')
                    mdata.append([Paragraph('D'+esc(code),tiny),Paragraph(esc(text),tiny)])
                mt=Table(mdata,colWidths=[14*mm,176*mm],repeatRows=1);mt.setStyle(_table_style(header=True,font_size=6.2));story.append(mt)
        else:
            story.append(Paragraph("Nebyly zadány žádné posuzované místnosti / prostory.",small))
    story.append(Spacer(1,2*mm))

    story += [_gray_label("6. Zjištěné závady")]
    if defects:
        data=[[Paragraph("#",tiny),Paragraph("Závažnost",tiny),Paragraph("Závada",tiny),Paragraph("Normy / články / citace",tiny),Paragraph("Foto",tiny)]]
        defect_row_pairs=[]
        for idx,d in enumerate(defects,1):
            plist=photos_by_defect.get(d["id"],[]);refs=", ".join(f"{idx}.{j}" for j,_ in enumerate(plist,1))
            sev=(d["severity"] if "severity" in d.keys() else "") or ""
            if str(sev).strip().upper() not in ("C1","C2","C3"):
                sev=(d["defect_class"] if "defect_class" in d.keys() else "") or ""
            sev=str(sev).strip().upper() if str(sev).strip().upper() in ("C1","C2","C3") else ""
            data.append([_para(str(idx),tiny),_para(sev,tiny),_para(d["defect_text"],small),_defect_refs_paragraph(d,tiny),_para(refs,tiny)])
            defect_row=len(data)-1
            confirmation=Table([
                [Paragraph("<b>Odstranil:</b>",tiny),"",Paragraph("<b>Datum:</b>",tiny),"",Paragraph("<b>Podpis:</b>",tiny),""]
            ],colWidths=[20*mm,55*mm,15*mm,28*mm,16*mm,48*mm],rowHeights=[7*mm])
            confirmation.setStyle(TableStyle([
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                ("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2),
                ("LINEBELOW",(1,0),(1,0),.5,colors.HexColor('#606873')),
                ("LINEBELOW",(3,0),(3,0),.5,colors.HexColor('#606873')),
                ("LINEBELOW",(5,0),(5,0),.5,colors.HexColor('#606873')),
            ]))
            data.append([confirmation,"","","",""])
            signature_row=len(data)-1;defect_row_pairs.append((defect_row,signature_row))
        t=Table(data,colWidths=[9*mm,18*mm,80*mm,64*mm,19*mm],repeatRows=1)
        dst=_table_style(header=True,font_size=6.5)
        for defect_row,signature_row in defect_row_pairs:
            dst.add("SPAN",(0,signature_row),(-1,signature_row))
            dst.add("BACKGROUND",(0,signature_row),(-1,signature_row),colors.HexColor('#FAFBFC'))
            dst.add("NOSPLIT",(0,defect_row),(-1,signature_row))
            dst.add("TOPPADDING",(0,signature_row),(-1,signature_row),2)
            dst.add("BOTTOMPADDING",(0,signature_row),(-1,signature_row),3)
        t.setStyle(dst);story.append(t)
        story.append(Spacer(1,0.8*mm))
        story.append(Paragraph("<b>C1</b> – Nebezpečný stav&nbsp;&nbsp;&nbsp;•&nbsp;&nbsp;&nbsp;<b>C2</b> – Potenciálně nebezpečný stav&nbsp;&nbsp;&nbsp;•&nbsp;&nbsp;&nbsp;<b>C3</b> – doporučení",tiny))
        if defect_photos:story.append(Paragraph("Fotografie závad jsou uvedeny v samostatné příloze Fotodokumentace závad.",tiny))
    else:
        story.append(Paragraph("<b>NEBYLY ZJIŠTĚNY</b>",base))
    story.append(Spacer(1,2*mm))

    story += [_gray_label("7. Vyhodnocení revize")]
    if conclusions:
        for idx,b in enumerate(conclusions,1):story.append(Paragraph(f"<b>7.{idx}</b>&nbsp;&nbsp;{esc(b['text_snapshot'])}",base))
    if rev["conclusion"]:story.append(Paragraph(esc(rev["conclusion"]),base))
    if rev["next_revision_on"]:story.append(Paragraph(f"V souladu s NV č. 190/2022 Sb. a ČSN 33 2000-6 ed. 2 je doporučený termín příští revize: <b>{esc(fmt_date(rev['next_revision_on']))}</b>",base))
    # Celkový posudek je záměrně pouze na první straně. Tím se neopakuje a nevzniká prázdná závěrečná strana.
    story.append(Spacer(1,2*mm))

    instruction=(rev["operator_instruction"] or "").strip() if "operator_instruction" in rev.keys() else ""
    if instruction:
        instruction_titles={
            "ELEKTRO":"8. Poučení pro provozovatele elektrického zařízení",
            "LPS":"8. Poučení pro provozovatele LPS / ochrany před bleskem",
            "STROJ":"8. Poučení pro provozovatele strojního zařízení",
            "VNEJSI":"8. Upozornění k protokolu o určení vnějších vlivů",
        }
        story += [_gray_label(instruction_titles.get(rev["revision_type"],"8. Poučení pro provozovatele"))]
        # Jednotlivé body jsou oddělené prázdným řádkem. Text je uložen přímo u revize,
        # proto zachováváme uživatelské číslování i případné vlastní víceřádkové odstavce.
        paragraphs=[p.strip() for p in re.split(r"\n\s*\n+",instruction) if p.strip()]
        for para in paragraphs:
            m=re.match(r"^(\d+[.)])\s*(.*)$",para,flags=re.S)
            if m:
                body=esc(m.group(2)).replace("\n","<br/>")
                story.append(Paragraph(f"<b>{esc(m.group(1))}</b>&nbsp;&nbsp;{body}",instruction_style))
            else:
                story.append(Paragraph(esc(para).replace("\n","<br/>"),instruction_style))
            story.append(Spacer(1,0.8*mm))
        story.append(Spacer(1,1.2*mm))

    story += [_gray_label("9. Seznam příloh")]
    appendix_items=[]
    if defect_photos:
        appendix_items.append(("Fotodokumentace závad",f"{len(defect_photos)} foto"))
    for a in attachments:
        title=(a["title"] or a["original_name"] or "Příloha").strip()
        detail=" - ".join(x for x in [(a["category"] or "").strip(),(a["original_name"] or "").strip()] if x)
        appendix_items.append((title,detail))
    if appendix_items:
        adata=[[Paragraph("Příloha",tiny),Paragraph("Název",tiny),Paragraph("Poznámka / soubor",tiny)]]
        for idx,(title,detail) in enumerate(appendix_items,1):
            adata.append([_para(str(idx),tiny),_para(title,small),_para(detail,tiny)])
        at=Table(adata,colWidths=[18*mm,92*mm,80*mm],repeatRows=1);at.setStyle(_table_style(header=True,font_size=6.7));story.append(at)
    else:
        story.append(Paragraph("Bez samostatných příloh.",small))

    # Photo appendix. Working photos are intentionally excluded. Four compact
    # photo cards (2 x 2) are placed on each page while preserving aspect ratio.
    if defect_photos:
        photo_cards=[]
        for didx,d in enumerate(defects,1):
            plist=photos_by_defect.get(d["id"],[])
            for pidx,p in enumerate(plist,1):
                sev=(d["severity"] if "severity" in d.keys() else "") or ""
                if str(sev).strip().upper() not in ("C1","C2","C3"):
                    sev=(d["defect_class"] if "defect_class" in d.keys() else "") or ""
                sev=str(sev).strip().upper() if str(sev).strip().upper() in ("C1","C2","C3") else ""
                cls=f" ({esc(sev)})" if sev else ""
                card=[Paragraph(f"<b>Foto {didx}.{pidx} - závada č. {didx}{cls}</b>",small)]
                card.append(Paragraph(esc(d["defect_text"]),tiny))
                im=_safe_img(p["stored_path"],82*mm,65*mm)
                if im:
                    im.hAlign="CENTER"
                    card.append(im)
                caption=" - ".join(x for x in [p["title"],p["note"]] if x)
                if caption:card.append(Paragraph(esc(caption),tiny))
                photo_cards.append(card)

        for page_start in range(0,len(photo_cards),4):
            story.append(PageBreak())
            story.append(_gray_label("PŘÍLOHA - FOTODOKUMENTACE ZÁVAD"))
            story.append(Spacer(1,2*mm))
            page_cards=photo_cards[page_start:page_start+4]
            rows=[]
            for row_start in range(0,len(page_cards),2):
                row=page_cards[row_start:row_start+2]
                if len(row)<2:row.append("")
                rows.append(row)
            gallery=Table(rows,colWidths=[94*mm,94*mm],hAlign="CENTER")
            gallery.setStyle(TableStyle([
                ("BOX",(0,0),(-1,-1),.45,MID),
                ("INNERGRID",(0,0),(-1,-1),.35,MID),
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",(0,0),(-1,-1),4),
                ("RIGHTPADDING",(0,0),(-1,-1),4),
                ("TOPPADDING",(0,0),(-1,-1),4),
                ("BOTTOMPADDING",(0,0),(-1,-1),4),
            ]))
            story.append(gallery)

    def first_page(canvas,doc_obj):
        # Footer is added by NumberedCanvas after the total page count is known.
        pass

    def later_pages(canvas,doc_obj):
        canvas.saveState();canvas.setFont(FONT,6.8);canvas.setFillColor(DARK);y=A4[1]-8*mm
        rt_name=rt["name"] if rt else ""
        if rev["revision_type"]=="VNEJSI":
            canvas.drawString(10*mm,y,f"Zpracovatel: {rt_name}")
            canvas.drawCentredString(A4[0]/2,y,f"Číslo protokolu: {rev['revision_no'] or ''}")
            obj_prefix="Posuzovaný objekt"
        else:
            canvas.drawString(10*mm,y,f"Revizní technik: {rt_name}")
            canvas.drawCentredString(A4[0]/2,y,f"Číslo revize: {rev['revision_no'] or ''}")
            obj_prefix="Revidované zařízení"
        obj=(obj_name or rev["subject"] or "").replace("\n"," ");obj=obj if len(obj)<80 else obj[:77]+"..."
        canvas.drawRightString(A4[0]-10*mm,y,f"{obj_prefix}: {obj}")
        canvas.setStrokeColor(MID);canvas.line(10*mm,y-2.3*mm,A4[0]-10*mm,y-2.3*mm);canvas.restoreState()

    doc.build(story,onFirstPage=first_page,onLaterPages=later_pages,canvasmaker=_numbered_canvas_factory(created_by,str(rev["revision_no"] or "")))
    return out


def _measurement_style():
    return _table_style(header=True,font_size=6.7)
