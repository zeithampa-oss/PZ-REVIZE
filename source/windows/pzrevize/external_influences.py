from __future__ import annotations

"""Datový a importní modul pro určování vnějších vlivů.

Modul je záměrně datový: nenahrazuje odborné určení komise / projektanta / RT.
Kódy a profily jsou připravené pro práci podle ČSN 33 2000-5-51 ed. 3+Z1+Z2
v rozsahu používaném PZ-REVIZE. Konkrétní opatření se ukládají jako snapshot
pro daný protokol, aby pozdější změna katalogu nezměnila starou zprávu.
"""

import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable

STANDARD_CODE = "ČSN 33 2000-5-51 ed. 3+Z1+Z2"
STANDARD_TITLE = "Elektrické instalace nízkého napětí – Část 5-51: Výběr a stavba elektrických zařízení – Všeobecné předpisy"

# Matice odpovídá dodaným tabulkám místností. AJ a BB nejsou v nich používány;
# v UI jsou uvedeny v poznámce, ale nezabírají samostatný sloupec.
DISPLAY_COLUMNS = [
    "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH",
    "AK", "AL", "AM", "AN", "AP", "AQ", "AR", "AS",
    "BA", "BC", "BD", "BE", "CA", "CB",
]

INFLUENCE_META: "OrderedDict[str, dict[str, str]]" = OrderedDict([
    ("AA", {"group": "A", "name": "Teplota okolí"}),
    ("AB", {"group": "A", "name": "Atmosférické podmínky v okolí"}),
    ("AC", {"group": "A", "name": "Nadmořská výška"}),
    ("AD", {"group": "A", "name": "Výskyt vody"}),
    ("AE", {"group": "A", "name": "Výskyt cizích pevných těles"}),
    ("AF", {"group": "A", "name": "Výskyt korozivních nebo znečišťujících látek"}),
    ("AG", {"group": "A", "name": "Mechanické namáhání – ráz"}),
    ("AH", {"group": "A", "name": "Vibrace"}),
    ("AK", {"group": "A", "name": "Výskyt rostlinstva nebo plísní"}),
    ("AL", {"group": "A", "name": "Výskyt živočichů"}),
    ("AM", {"group": "A", "name": "Elektromagnetická, elektrostatická nebo ionizující působení"}),
    ("AN", {"group": "A", "name": "Intenzita slunečního záření"}),
    ("AP", {"group": "A", "name": "Seizmické účinky"}),
    ("AQ", {"group": "A", "name": "Blesková úroveň"}),
    ("AR", {"group": "A", "name": "Pohyb vzduchu"}),
    ("AS", {"group": "A", "name": "Vítr"}),
    ("BA", {"group": "B", "name": "Schopnost osob"}),
    ("BC", {"group": "B", "name": "Kontakt osob s potenciálem země"}),
    ("BD", {"group": "B", "name": "Podmínky úniku v případě nebezpečí"}),
    ("BE", {"group": "B", "name": "Povaha zpracovávaných nebo skladovaných materiálů"}),
    ("CA", {"group": "C", "name": "Stavební materiál"}),
    ("CB", {"group": "C", "name": "Provedení / konstrukce budovy"}),
])

GROUP_TITLES = {
    "A": "A – Vnější podmínky prostředí",
    "B": "B – Využití objektu",
    "C": "C – Konstrukce budovy",
}

# Checklist byl v 0.4.32 auditován proti nahrané ČSN 33 2000-5-51 ed.3+Z1+Z2,
# konsolidovanému vydání z července 2022, zejména příloze ZA a tabulce ZA.1.
# Texty níže jsou zkrácené pracovní formulace pro software, nikoli opis normy.
SOURCE_DATA_NOTE = (
    "Číselník byl auditován proti ČSN 33 2000-5-51 ed. 3+Z1+Z2, "
    "konsolidovanému vydání z července 2022, zejména příloze ZA a tabulce ZA.1. "
    "Normové charakteristiky jsou v programu zkrácené pracovní formulace; konkrétní opatření "
    "zůstávají editovatelná pro daný prostor a nenahrazují odborné posouzení."
)

# Výchozí editovatelný obecný text je převzatý z uživatelem dodaného vzorového
# protokolu, strany 2 až 5. Nejde o normativní text; uživatel jej může libovolně
# upravit pro konkrétní objekt. Vzorce jsou zapsány v čitelné textové podobě a
# PDF renderer je zvýrazní jako samostatné řádky.
GENERAL_PAGE_2_DEFAULT = """Popis budovy – textová část
Celkově jde o typickou administrativní architekturu přelomu tisíciletí – kombinace skla, oceli a betonu s důrazem na prosvětlení a reprezentativní vstupní prostor hodný uživatele budovy na adrese Duhová 1 v Praze 4 - Michle, v areálu Brumlovka/BB Centrum.

Základní údaje a typ konstrukce:
Železobetonový skelet, kombinace zavěšeného a předsazeného obvodového pláště
Počet nadzemních podlaží: 8
Počet podzemních podlaží: 5
Půdorysné řešení: Dvě křídla (vyšší hlavní trakt + nižší kolmé křídlo), spojená atriem
Vstupní prostor: 6 podlažní prosklené atrium se strukturálním zasklením na tahové nosné konstrukci
Vertikální komunikace: 2 komunikační věže, osově symetrické výtahové šachty
Fasádní systém: Kombinace zavěšeného pláště na betonovém parapetu a velkoplošně předsazeného pláště
Stínění: Samonosný systém stínících lamel na jižní fasádě

Hmotové řešení a fasáda:
Budova stojí u malého parku poblíž dálnice D1 směrem na Brno a má osm nadzemních podlaží. Skládá se ze dvou křídel – hlavního, vyššího traktu orientovaného na osu parku, a na něj kolmo navazujícího nižšího, kratšího křídla.
Obě křídla spojuje šestipodlažní prosklené vstupní atrium a dvě komunikační věže.

Konstrukce obvodového pláště:
Fasáda je řešena buď jako plášť zavěšený na betonový parapet, nebo jako velkoplošně předsazený systém před nosnou konstrukcí. Jižní strana budovy je opatřena samonosným předsazeným systémem stínících lamel, který brání přehřívání fasády.
Uvnitř dispozice odpovídá rozdělení na dvě křídla osově symetrickému umístění výtahů do dvou šachet."""

GENERAL_PAGE_3_DEFAULT = """Podklady:
• Komisionální prohlídka areálu
• Původní protokol o určení vnějších vlivů vypracovaný odbornou komisí dne 11.10.2006
• Technická zpráva - požárně bezpečnostní řešení stavby
• Požárně technické charakteristiky používaných látek
• Stavební projektová dokumentace
• Půdorys jednotlivých podlaží – stávající stav

Legislativa:
• ČSN 33 2000-1 ed.2 Elektrické instalace nízkého napětí – Část 1: Základní hlediska, stanovení základních charakteristik, definice
• ČSN 33 2000-4-41 ed.3 Elektrické instalace nízkého napětí – Část 4-41: Ochranná opatření pro zajištění bezpečnosti – Ochrana před úrazem elektrickým proudem
• TNI 33 2000-4-41 Elektrické instalace nízkého napětí – Část 4-41: Ochranná opatření pro zajištění bezpečnosti – Ochrana před úrazem elektrickým proudem – Komentář k ČSN 33 2000-4-41 ed.2
• ČSN 33 2000-5-51 ed.3 + Z1, Z2 Elektrické instalace nízkého napětí – Část 5-51: Výběr a stavba elektrických zařízení – Všeobecné předpisy
• TNI 33 2000-5-51 Elektrické instalace nízkého napětí – Výběr a stavba elektrických zařízení – Všeobecné předpisy – Vnější vlivy, jejich určování a protokol o určení vnějších vlivů – Komentář k ČSN 33 2000-5-51 ed.3+Z1+Z2:2022
• ČSN 33 2000-7-701 ed.2 Elektrické instalace nízkého napětí – Část 7-701: Zařízení jednoúčelová a ve zvláštních objektech – Prostory s vanou nebo sprchou
• ČSN 33 2130 ed.4 Elektrické instalace nízkého napětí – Vnitřní elektrické rozvody
• ČSN EN 1127-1 ed.3 Výbušná prostředí – Prevence a ochrana proti výbuchu – Část 1: Základní koncepce a metodika
• ČSN EN IEC 60079-10-1 ed.3 Určování nebezpečných prostorů – výbušné plynné atmosféry
• ČSN EN 60079-10-2 ed.2 Určování nebezpečných prostorů – výbušné atmosféry s hořlavým prachem
• ČSN EN 60079-14 ed.4 Výbušné atmosféry – návrh, výběr a zřizování elektrických instalací
• ČSN EN 60529 Stupně ochrany krytem (krytí-IP kód)
• CLC/TR 50404 Elektrostatika – Směrnice pro zabránění nebezpečí zaviněného statickou elektřinou, CENELEC, 2003.

Všechny výše uvedené předpisy a normy byly využity ve verzích platných v době vypracování poslední provedené aktualizace dokumentu."""

GENERAL_PAGE_4_DEFAULT = """Vysvětlení určení ZÓN v prostorách s nebezpečím výbuchu hořlavých prachů:
ZÓNA 20: prostor, ve kterém se výbušná atmosféra tvořená oblakem zvířených hořlavých prachů ve směsi se vzduchem očekává trvale, po dlouhá časová období nebo často.
ZÓNA 21: prostor, ve kterém se výbušná atmosféra tvořená oblakem zvířených hořlavých prachů ve směsi se vzduchem očekává, nebude se však vyskytovat trvale nebo po dlouhá časová období.
ZÓNA 22: prostor, ve kterém se výbušná atmosféra tvořená oblakem zvířených hořlavých prachů ve směsi se vzduchem neočekává, a pokud se vyskytne, pouze výjimečně nebo po krátká časová období.

Vysvětlení určení ZÓN v prostorách s nebezpečím výbuchu hořlavých plynů a par hořlavých kapalin:
ZÓNA 0: prostor, ve kterém se výbušná atmosféra tvořená směsí hořlavých plynů nebo par hořlavých kapalin se vzduchem očekává trvale nebo po dlouhá časová období.
ZÓNA 1: prostor, ve kterém se výbušná atmosféra tvořená směsí hořlavých plynů nebo par hořlavých kapalin se vzduchem očekává, nebude se však vyskytovat trvale nebo po dlouhá časová období.
ZÓNA 2: prostor, ve kterém se výbušná atmosféra tvořená směsí hořlavých plynů nebo par hořlavých kapalin se vzduchem neočekává, a pokud se vyskytne, pouze výjimečně nebo po krátká časová období.

Charakteristika úniků hořlavých látek:
Trvalý stupeň úniku – únik, který je trvalý nebo jehož přítomnost je očekávána po dlouhém časovém období.
Primární stupeň úniku – únik, který může vznikat periodicky nebo příležitostně během normálního provozu.
Sekundární stupeň úniku – únik, jehož vznik není za normálního provozu pravděpodobný a pokud vznikne, je pravděpodobnost, že k tomu bude docházet pouze zřídka a po krátké časové období.

Pro elektrická zařízení v místech nebezpečí výbuchu hořlavých plynů a par platí ČSN EN 60079-10-1 ed.3. Pro určování nebezpečných prostorů byly použity následující vzorce.

Vzorce použité pro výpočet
Odhad teoretického objemu Vz
(dV/dt)min – je min. objemová rychlost proudění čerstvého vzduchu (objem za jednotku času v m³/s)
(dG/dt)max – je max. rychlost úniku ze zdroje (hmotnost za jednotku času v kg/s)
LEL – je dolní mez výbušnosti (hmotnost za jednotku objemu v kg/m³)
T – je okolní teplota (v K)
(dV/dt)min = ((dG/dt)max / (k · LEL)) · (T / 293)

Poznámka – Pro výpočet LEL (objemové koncentrace v %) na LEL v kg/m³ může být pro normální podmínky použito vzorce:
LEL (kg/m³) = 0,416×10⁻³ × M × LEL (objemová %)
Kde M je molekulová hmotnost (kg/kmol)
C – je počet výměn čerstvého vzduchu za jednotku času (s⁻¹)
k – je bezpečnostní koeficient vztažený na dolní mez výbušnosti; obvykle k = 0,25 (trvalé a primární stupně úniku), k = 0,5 (sekundární stupně úniku)"""

GENERAL_PAGE_5_DEFAULT = """f – vyjadřuje účinnost větrání ve smyslu jeho účinnosti v rozřeďování výbušné atmosféry; f je v rozsahu 1-5, kde f = 1 (ideální situace) a typický f = 5 (průtok vzduchu s překážkami)
Vz = f · (dV/dt)min / (k · C)

Uzavřený prostor:
Pro uzavřený prostor se C vypočte:
dVc/dt – je celková rychlost průtoku čerstvého vzduchu
Vo – je celkový větraný objem
C = (dVc/dt) / Vo

Venkovní prostor:
Při rychlosti větru přibližně 0,5 m/s je zajištěna výměna vzduchu větší než 100/h (0,03/s)
C = 0,03 /s

Odhad doby přetrvávání výbušné atmosféry t
Doba t nutná na to, aby průměrná koncentrace poklesla po zastavení úniku ze zdroje z počáteční hodnoty X₀ na k-násobek dolní meze výbušnosti může být odhadnuta ze vzorce:
t = -(f / C) · ln((LEL · k) / X₀)

X₀ – je počáteční koncentrace hořlavé látky, měřená ve stejných jednotkách jako dolní mez výbušnosti, tj. v % objemových, nebo kg/m³. Někde ve výbušné atmosféře může být koncentrace 100 % objemová (obecně v těsné blízkosti zdroje úniku). Avšak při výpočtu t se správná hodnota X₀ volí pro každý případ zvlášť, s uvažováním velikosti ovlivňovaného objemu, četnosti a doby trvání úniku.
C – je počet výměn čerstvého vzduchu za jednotku času
t – je ve stejných časových jednotkách jako C
f – je přídavný koeficient nedokonalého míchání; mění se v rozsahu od 5 do 1 podle způsobu větrání
ln – je přirozený logaritmus, tj. 2,303 log10
k – je bezpečnostní koeficient vztažený na dolní mez výbušnosti"""

REFERENCE_STANDARDS = [
    ("ČSN 33 2000-1 ed.2", "Elektrické instalace nízkého napětí – Část 1: Základní hlediska, stanovení základních charakteristik, definice"),
    ("ČSN 33 2000-4-41 ed.3", "Elektrické instalace nízkého napětí – Část 4-41: Ochranná opatření pro zajištění bezpečnosti – Ochrana před úrazem elektrickým proudem"),
    ("TNI 33 2000-4-41", "Elektrické instalace nízkého napětí – Část 4-41 – komentář"),
    ("ČSN 33 2000-5-51 ed.3 + Z1, Z2", "Elektrické instalace nízkého napětí – Část 5-51: Výběr a stavba elektrických zařízení – Všeobecné předpisy"),
    ("TNI 33 2000-5-51", "Elektrické instalace nízkého napětí – Vnější vlivy, jejich určování a protokol o určení vnějších vlivů – komentář"),
    ("ČSN 33 2000-7-701 ed.2", "Elektrické instalace nízkého napětí – Prostory s vanou nebo sprchou"),
    ("ČSN 33 2130 ed.4", "Elektrické instalace nízkého napětí – Vnitřní elektrické rozvody"),
    ("ČSN EN 1127-1 ed.3", "Výbušná prostředí – Prevence a ochrana proti výbuchu – Část 1: Základní koncepce a metodika"),
    ("ČSN EN IEC 60079-10-1 ed.3", "Určování nebezpečných prostorů – výbušné plynné atmosféry"),
    ("ČSN EN 60079-10-2 ed.2", "Určování nebezpečných prostorů – výbušné atmosféry s hořlavým prachem"),
    ("ČSN EN 60079-14 ed.4", "Výbušné atmosféry – návrh, výběr a zřizování elektrických instalací"),
    ("ČSN EN 60529", "Stupně ochrany krytem (krytí-IP kód)"),
    ("CLC/TR 50404", "Elektrostatika – Směrnice pro zabránění nebezpečí zaviněného statickou elektřinou, CENELEC, 2003"),
]

# Jedna položka = kód, krátká charakteristika a stručná pomůcka pro výběr zařízení.
# Texty nejsou reprodukcí normy; jde o provozní číselník pro checklist.
CHECKLIST_OPTIONS: dict[str, list[dict[str, str]]] = {
    "AA": [
        {"code":"AA1","label":"−60 °C až +5 °C","requirement":"Použít speciálně navržené zařízení nebo vhodnou úpravu pro daný teplotní rozsah; podle zařízení mohou být nutná doplňková opatření.","source":"tab. ZA.1, s. 18"},
        {"code":"AA2","label":"−40 °C až +5 °C","requirement":"Použít speciálně navržené zařízení nebo vhodnou úpravu pro daný teplotní rozsah; podle zařízení mohou být nutná doplňková opatření.","source":"tab. ZA.1, s. 18"},
        {"code":"AA3","label":"−25 °C až +5 °C","requirement":"Použít speciálně navržené zařízení nebo vhodnou úpravu pro daný teplotní rozsah; podle zařízení mohou být nutná doplňková opatření.","source":"tab. ZA.1, s. 18"},
        {"code":"AA4","label":"−5 °C až +40 °C","requirement":"Normální podmínky; v určitých případech se dovoluje přijmout zvláštní opatření podle konkrétního zařízení.","source":"tab. ZA.1, s. 18"},
        {"code":"AA5","label":"+5 °C až +40 °C","requirement":"Normální podmínky.","source":"tab. ZA.1, s. 18"},
        {"code":"AA6","label":"+5 °C až +60 °C","requirement":"Použít speciálně navržené zařízení nebo vhodnou úpravu pro daný teplotní rozsah; podle zařízení mohou být nutná doplňková opatření.","source":"tab. ZA.1, s. 19"},
        {"code":"AA7","label":"−25 °C až +55 °C","requirement":"Použít speciálně navržené zařízení nebo vhodnou úpravu pro daný teplotní rozsah; podle zařízení mohou být nutná doplňková opatření.","source":"tab. ZA.1, s. 19"},
        {"code":"AA8","label":"−50 °C až +40 °C","requirement":"Použít speciálně navržené zařízení nebo vhodnou úpravu pro daný teplotní rozsah; podle zařízení mohou být nutná doplňková opatření.","source":"tab. ZA.1, s. 19"},
    ],
    "AB": [
        {"code":"AB1","label":"−60 až +5 °C; RV 3–100 %","requirement":"Pro extrémně nízkou teplotu a současnou vlhkost navrhnout zvláštní opatření a zařízení vhodné pro daný rozsah.","source":"tab. ZA.1, s. 19"},
        {"code":"AB2","label":"−40 až +5 °C; RV 10–100 %","requirement":"Pro extrémně nízkou teplotu a současnou vlhkost navrhnout zvláštní opatření a zařízení vhodné pro daný rozsah.","source":"tab. ZA.1, s. 19"},
        {"code":"AB3","label":"−25 až +5 °C; RV 10–100 %","requirement":"Pro nízkou teplotu a současnou vysokou vlhkost navrhnout zvláštní opatření a zařízení vhodné pro daný rozsah.","source":"tab. ZA.1, s. 20"},
        {"code":"AB4","label":"−5 až +40 °C; RV 5–95 %","requirement":"Normální podmínky pro prostory chráněné před atmosférickými vlivy bez regulace teploty a vlhkosti; ke zvýšení nízké teploty lze použít vytápění.","source":"tab. ZA.1, s. 20"},
        {"code":"AB5","label":"+5 až +40 °C; RV 5–85 %","requirement":"Normální podmínky pro prostory chráněné před atmosférickými vlivy s regulací teploty.","source":"tab. ZA.1, s. 20"},
        {"code":"AB6","label":"+5 až +60 °C; RV 10–100 %","requirement":"Pro extrémně vysokou teplotu a současnou vysokou vlhkost navrhnout zvláštní opatření a zařízení vhodné pro daný rozsah.","source":"tab. ZA.1, s. 20"},
        {"code":"AB7","label":"−25 až +55 °C; RV 10–100 %","requirement":"Pro venkovní / nechráněné podmínky s velkým rozsahem teplot a vlhkosti navrhnout zvláštní opatření.","source":"tab. ZA.1, s. 20"},
        {"code":"AB8","label":"−50 až +40 °C; RV 15–100 %","requirement":"Pro velmi náročné venkovní / nechráněné podmínky s velkým rozsahem teplot a vlhkosti navrhnout zvláštní opatření.","source":"tab. ZA.1, s. 20"},
    ],
    "AC": [
        {"code":"AC1","label":"nadmořská výška ≤ 2 000 m","requirement":"Normální podmínky.","source":"tab. ZA.1, s. 21"},
        {"code":"AC2","label":"nadmořská výška > 2 000 m","requirement":"Mohou být vyžadována speciální bezpečnostní opatření, např. uplatnění korekčních součinitelů s ohledem na nadmořskou výšku; respektovat údaje výrobce.","source":"tab. ZA.1, s. 21"},
    ],
    "AD": [
        {"code":"AD1","label":"výskyt vody zanedbatelný","requirement":"Zanedbatelný výskyt vody; požadované krytí IPX0. V ČR se AD1 považuje za normální.","source":"tab. ZA.1, s. 21"},
        {"code":"AD2","label":"svisle padající kapky","requirement":"Volně padající kapky; požadované krytí IPX1 nebo IPX2 podle podmínek působení.","source":"tab. ZA.1, s. 21"},
        {"code":"AD3","label":"vodní tříšť","requirement":"Vodní tříšť; požadované krytí IPX3.","source":"tab. ZA.1, s. 21"},
        {"code":"AD4","label":"stříkající voda","requirement":"Stříkající voda; požadované krytí IPX4.","source":"tab. ZA.1, s. 21"},
        {"code":"AD5","label":"tryskající voda","requirement":"Tryskající voda; požadované krytí IPX5.","source":"tab. ZA.1, s. 21"},
        {"code":"AD6","label":"vlny / zaplavení","requirement":"Vlny; požadované krytí IPX6.","source":"tab. ZA.1, s. 21"},
        {"code":"AD7","label":"mělké ponoření","requirement":"Mělké ponoření; požadované krytí IPX7 a zařízení vhodné pro předpokládané podmínky ponoření.","source":"tab. ZA.1, s. 22"},
        {"code":"AD8","label":"hluboké ponoření","requirement":"Hluboké ponoření; požadované krytí IPX8, podmínky hloubky / doby podle určení zařízení.","source":"tab. ZA.1, s. 22"},
    ],
    "AE": [
        {"code":"AE1","label":"výskyt cizích pevných těles zanedbatelný","requirement":"Zanedbatelný výskyt cizích pevných těles; IP0X. V ČR se AE1 považuje za normální.","source":"tab. ZA.1, s. 22"},
        {"code":"AE2","label":"malé předměty (2,5 mm)","requirement":"Malé předměty (2,5 mm); požadované krytí IP3X.","source":"tab. ZA.1, s. 22"},
        {"code":"AE3","label":"velmi malé předměty (1 mm)","requirement":"Velmi malé předměty (1 mm); požadované krytí IP4X.","source":"tab. ZA.1, s. 22"},
        {"code":"AE4","label":"lehká prašnost","requirement":"Lehká prašnost; IP5X, pokud pronikání prachu není pro funkci škodlivé.","source":"tab. ZA.1, s. 22"},
        {"code":"AE5","label":"střední prašnost","requirement":"Střední prašnost; IP6X.","source":"tab. ZA.1, s. 22"},
        {"code":"AE6","label":"silná prašnost","requirement":"Silná prašnost; IP6X a zařízení vhodné pro silnou prašnost.","source":"tab. ZA.1, s. 22"},
    ],
    "AF": [
        {"code":"AF1","label":"korozivní / znečišťující látky – zanedbatelný výskyt","requirement":"Zanedbatelný výskyt korozivních nebo znečišťujících látek; normální podmínky.","source":"tab. ZA.1, s. 23"},
        {"code":"AF2","label":"atmosférický výskyt","requirement":"Atmosférický výskyt korozivních nebo znečišťujících látek; volit zařízení a materiály podle povahy látek a požadované korozní odolnosti.","source":"tab. ZA.1, s. 23"},
        {"code":"AF3","label":"občasný nebo příležitostný výskyt","requirement":"Občasný nebo příležitostný výskyt chemických látek; ochranu proti korozi volit podle specifikace zařízení a konkrétních látek.","source":"tab. ZA.1, s. 23"},
        {"code":"AF4","label":"trvalý výskyt","requirement":"Trvalý výskyt korozivních nebo znečišťujících látek; použít zařízení speciálně navržené podle povahy působících látek.","source":"tab. ZA.1, s. 23"},
    ],
    "AG": [
        {"code":"AG1","label":"ráz – mírný","requirement":"Nízká závažnost rázů; normální podmínky, např. domácí a podobná zařízení.","source":"tab. ZA.1, s. 23"},
        {"code":"AG2","label":"ráz – střední","requirement":"Střední závažnost rázů; použít standardní průmyslové zařízení, je-li potřebné, se zesílenou ochranou.","source":"tab. ZA.1, s. 23"},
        {"code":"AG3","label":"ráz – silný","requirement":"Silná závažnost rázů; použít zesílenou ochranu.","source":"tab. ZA.1, s. 23"},
    ],
    "AH": [
        {"code":"AH1","label":"vibrace – mírné","requirement":"Nízká závažnost vibrací; normální podmínky.","source":"tab. ZA.1, s. 24"},
        {"code":"AH2","label":"vibrace – střední","requirement":"Střední závažnost vibrací; pro obvyklé průmyslové podmínky použít speciálně navržené zařízení nebo speciální úpravu.","source":"tab. ZA.1, s. 24"},
        {"code":"AH3","label":"vibrace – silné","requirement":"Silná závažnost vibrací; pro náročné průmyslové podmínky použít speciálně navržené zařízení nebo speciální úpravu.","source":"tab. ZA.1, s. 24"},
    ],
    "AK": [
        {"code":"AK1","label":"rostlinstvo / plísně – bez nebezpečí","requirement":"Bez vážného nebezpečí způsobeného růstem rostlin nebo plísní; normální podmínky.","source":"tab. ZA.1, s. 24"},
        {"code":"AK2","label":"rostlinstvo / plísně – nebezpečný výskyt","requirement":"Nebezpečný výskyt rostlin / plísní; ochrana může zahrnovat zvýšenou ochranu proti pronikání cizích těles, zvláštní materiály nebo nátěry krytů a opatření vylučující přítomnost rostlin v prostoru.","source":"tab. ZA.1, s. 24"},
    ],
    "AL": [
        {"code":"AL1","label":"živočichové – bez nebezpečí","requirement":"Bez škodlivého nebezpečí ze strany živočichů; normální podmínky.","source":"tab. ZA.1, s. 24"},
        {"code":"AL2","label":"živočichové – nebezpečný výskyt","requirement":"Nebezpečný výskyt živočichů; ochrana může zahrnovat vhodný stupeň ochrany proti cizím tělesům, mechanickou odolnost, vyloučení živočichů z prostoru a zvláštní zařízení nebo ochranné nátěry.","source":"tab. ZA.1, s. 24"},
    ],
    "AM": [
        {"code":"AM-1-1","label":"harmonické / meziharmonické – kontrolovaná úroveň","requirement":"Zabezpečit, aby se kontrolovaná úroveň harmonických / meziharmonických nezhoršila.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-1-2","label":"harmonické / meziharmonické – normální úroveň","requirement":"Normální úroveň; bez zvláštních opatření nad rámec běžného návrhu.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-1-3","label":"harmonické / meziharmonické – vysoká úroveň","requirement":"V návrhu instalace použít zvláštní opatření, např. filtry.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-2-1","label":"signální napětí – kontrolovaná úroveň","requirement":"Kontrolovaná úroveň signálního napětí; lze použít blokovací obvody.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-2-2","label":"signální napětí – střední úroveň","requirement":"Střední úroveň signálního napětí; bez dodatečných požadavků.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-2-3","label":"signální napětí – vysoká úroveň","requirement":"Vysoká úroveň signálního napětí; použít zvláštní opatření.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-3-1","label":"změny amplitudy napětí – kontrolovaná úroveň","requirement":"Kontrolovaná úroveň změn amplitudy napětí; např. kontrola pomocí UPS.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-3-2","label":"změny amplitudy napětí – normální úroveň","requirement":"Normální úroveň změn amplitudy napětí; postupovat podle příslušného odkazu normy.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-4","label":"neustálené napětí","requirement":"Neustálené napětí; postupovat podle EN 61000-2-2.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-5","label":"změny kmitočtu","requirement":"Změny kmitočtu; ±1 Hz v souladu s EN 61000-2-2.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-6","label":"indukované napětí nízkého kmitočtu","requirement":"Indukované napětí nízkého kmitočtu; postupovat podle HD 60364-4-444 a požadovat vysokou odolnost signalizačních a řídicích systémů.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-7","label":"stejnosměrný proud v obvodech střídavého proudu","requirement":"Stejnosměrný proud v sítích střídavého proudu; omezit jeho přítomnost v úrovni a čase ve spotřebičích nebo v jejich blízkosti.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-8-1","label":"vyzařovaná magnetická pole – střední úroveň","requirement":"Střední úroveň vyzařovaného magnetického pole; normální podmínky.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-8-2","label":"vyzařovaná magnetická pole – vysoká úroveň","requirement":"Vysoká úroveň vyzařovaného magnetického pole; použít vhodná ochranná opatření, např. clonu a/nebo oddělení.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-9-1","label":"elektrická pole – zanedbatelná úroveň","requirement":"Zanedbatelná úroveň elektrického pole; normální podmínky.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-9-2","label":"elektrická pole – střední úroveň","requirement":"Střední úroveň elektrického pole; posoudit podle IEC/TR 61000-2-5.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-9-3","label":"elektrická pole – vysoká úroveň","requirement":"Vysoká úroveň elektrického pole; posoudit podle IEC/TR 61000-2-5.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-9-4","label":"elektrická pole – velmi vysoká úroveň","requirement":"Velmi vysoká úroveň elektrického pole; posoudit podle IEC/TR 61000-2-5.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-21","label":"indukovaná oscilující napětí nebo proudy","requirement":"Indukovaná oscilační napětí nebo proudy; bez třídění, normální.","source":"tab. ZA.1, s. 25"},
        {"code":"AM-22-1","label":"rychlé přechodné jevy vedením – zanedbatelná úroveň","requirement":"Zanedbatelná úroveň rychlých přechodných jevů; ochranná opatření jsou nezbytná.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-22-2","label":"rychlé přechodné jevy vedením – střední úroveň","requirement":"Střední úroveň rychlých přechodných jevů; ochranná opatření jsou nezbytná.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-22-3","label":"rychlé přechodné jevy vedením – vysoká úroveň","requirement":"Vysoká úroveň rychlých přechodných jevů; normální zařízení.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-22-4","label":"rychlé přechodné jevy vedením – velmi vysoká úroveň","requirement":"Velmi vysoká úroveň rychlých přechodných jevů; použít vysoce odolné zařízení.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-23-1","label":"přechodná přepětí vedením – kontrolovaná úroveň","requirement":"Odolnost zařízení proti přechodným přepětím a ochranné prostředky proti přepětí zvolit podle jmenovitého napětí a kategorie odolnosti proti přepětí.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-23-2","label":"přechodná přepětí vedením – střední úroveň","requirement":"Odolnost zařízení proti přechodným přepětím a ochranné prostředky proti přepětí zvolit podle jmenovitého napětí a kategorie odolnosti proti přepětí.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-23-3","label":"přechodná přepětí vedením – vysoká úroveň","requirement":"Odolnost zařízení proti přechodným přepětím a ochranné prostředky proti přepětí zvolit podle jmenovitého napětí a kategorie odolnosti proti přepětí.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-24-1","label":"oscilační přechodové jevy vedením – střední úroveň","requirement":"Střední úroveň oscilačních přechodových jevů; postupovat podle EN 61000-4-12.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-24-2","label":"oscilační přechodové jevy vedením – vysoká úroveň","requirement":"Vysoká úroveň oscilačních přechodových jevů; postupovat podle EN 60255-22-1.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-25-1","label":"vysokofrekvenční vyzařované jevy – zanedbatelná úroveň","requirement":"Zanedbatelná úroveň vyzařovaných vysokofrekvenčních jevů; úroveň odolnosti 1.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-25-2","label":"vysokofrekvenční vyzařované jevy – střední úroveň","requirement":"Střední úroveň vyzařovaných vysokofrekvenčních jevů; normální zařízení, úroveň odolnosti 2.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-25-3","label":"vysokofrekvenční vyzařované jevy – vysoká úroveň","requirement":"Vysoká úroveň vyzařovaných vysokofrekvenčních jevů; požadována zvýšená odolnost, úroveň 3.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-31-1","label":"elektrostatické výboje – nízká úroveň","requirement":"Nízká úroveň elektrostatických výbojů; normální zařízení, úroveň 1.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-31-2","label":"elektrostatické výboje – střední úroveň","requirement":"Střední úroveň elektrostatických výbojů; normální zařízení, úroveň 2.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-31-3","label":"elektrostatické výboje – vysoká úroveň","requirement":"Vysoká úroveň elektrostatických výbojů; normální zařízení, úroveň 3.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-31-4","label":"elektrostatické výboje – velmi vysoká úroveň","requirement":"Velmi vysoká úroveň elektrostatických výbojů; požadováno vyztužení / zvýšená odolnost, úroveň 4.","source":"tab. ZA.1, s. 26"},
        {"code":"AM-41-1","label":"ionizace – bez třídění","requirement":"Ionizace bez klasifikace; speciální ochrana může zahrnovat vzdálenost od zdroje a vložení clon / krytů ze speciálních materiálů.","source":"tab. ZA.1, s. 26"},
    ],
    "AN": [
        {"code":"AN1","label":"sluneční záření – nízké","requirement":"Nízká intenzita slunečního záření (≤ 500 W/m²); normální podmínky.","source":"tab. ZA.1, s. 26"},
        {"code":"AN2","label":"sluneční záření – střední","requirement":"Střední intenzita slunečního záření; musí být provedena vhodná opatření.","source":"tab. ZA.1, s. 26"},
        {"code":"AN3","label":"sluneční záření – vysoké","requirement":"Vysoká intenzita slunečního záření; vhodná opatření mohou zahrnovat materiály odolné proti UV, speciální barevný nátěr nebo vložení clon.","source":"tab. ZA.1, s. 26"},
    ],
    "AP": [
        {"code":"AP1","label":"seizmické účinky – zanedbatelné","requirement":"Zanedbatelné seizmické účinky (zrychlení ≤ 30 Gal); normální podmínky.","source":"tab. ZA.1, s. 27"},
        {"code":"AP2","label":"seizmické účinky – nízké ohrožení","requirement":"Nízká úroveň seizmických účinků (30 < zrychlení ≤ 300 Gal); konkrétní opatření se zvažují podle objektu a zařízení.","source":"tab. ZA.1, s. 27"},
        {"code":"AP3","label":"seizmické účinky – střední ohrožení","requirement":"Střední úroveň seizmických účinků (300 < zrychlení ≤ 600 Gal); konkrétní opatření se zvažují podle objektu a zařízení.","source":"tab. ZA.1, s. 27"},
        {"code":"AP4","label":"seizmické účinky – vysoké ohrožení","requirement":"Vysoká úroveň seizmických účinků (> 600 Gal); konkrétní opatření se zvažují podle objektu a zařízení.","source":"tab. ZA.1, s. 27"},
    ],
    "AQ": [
        {"code":"AQ1","label":"úder blesku – zanedbatelný","requirement":"Zanedbatelná blesková úroveň / hustota; normální podle posouzení rizika.","source":"tab. ZA.1, s. 27"},
        {"code":"AQ2","label":"nepřímé ohrožení","requirement":"Nepřímé ohrožení; v tabulce ZA.1 uvedeno jako normální, podle hodnot nebo výsledku posouzení rizika.","source":"tab. ZA.1, s. 27"},
        {"code":"AQ3","label":"přímé ohrožení","requirement":"Přímé ohrožení; nebezpečí zasažení zařízení. Je-li ochrana před bleskem důležitá, řešit ji podle souboru EN 62305; části instalace umístěné vně budov posoudit zvlášť.","source":"tab. ZA.1, s. 27"},
    ],
    "AR": [
        {"code":"AR1","label":"pohyb vzduchu – pomalý","requirement":"Pomalý pohyb vzduchu (rychlost < 1 m/s); normální podmínky.","source":"tab. ZA.1, s. 27"},
        {"code":"AR2","label":"pohyb vzduchu – střední","requirement":"Střední pohyb vzduchu (1 až 5 m/s); musí být provedena vhodná opatření.","source":"tab. ZA.1, s. 27"},
        {"code":"AR3","label":"pohyb vzduchu – silný","requirement":"Silný pohyb vzduchu (5 až 10 m/s); musí být provedena vhodná opatření.","source":"tab. ZA.1, s. 27"},
    ],
    "AS": [
        {"code":"AS1","label":"vítr – malý","requirement":"Malý vítr (rychlost ≤ 20 m/s); normální podmínky.","source":"tab. ZA.1, s. 27"},
        {"code":"AS2","label":"vítr – střední","requirement":"Střední vítr (20 až 30 m/s); musí být provedena vhodná opatření.","source":"tab. ZA.1, s. 27"},
        {"code":"AS3","label":"vítr – silný","requirement":"Silný vítr (30 až 50 m/s); musí být provedena vhodná opatření.","source":"tab. ZA.1, s. 27"},
    ],
    "BA": [
        {"code":"BA1","label":"schopnost osob – běžná","requirement":"Laici / nepoučené osoby; normální podmínky.","source":"tab. ZA.1, s. 28"},
        {"code":"BA2","label":"děti","requirement":"Místa určená pro přítomnost dětí: použít zařízení se stupněm ochrany vyšším než IP2XC a znepřístupnit zařízení s povrchovou teplotou nad 60 °C.","source":"tab. ZA.1, s. 28"},
        {"code":"BA3","label":"osoby se sníženými schopnostmi","requirement":"Osoby s omezenými fyzickými nebo duševními schopnostmi; opatření určit podle povahy postižení.","source":"tab. ZA.1, s. 28"},
        {"code":"BA4","label":"poučené osoby","requirement":"Osoby odpovídajícím způsobem poučené nebo pracující pod dohledem osoby znalé tak, aby se mohly vyhnout nebezpečí úrazu elektrickým proudem; typicky elektrotechnické pracovní prostory.","source":"tab. ZA.1, s. 28"},
        {"code":"BA5","label":"odborníci / osoby znalé","requirement":"Osoby znalé: zařízení nechráněná proti přímému dotyku lze připustit jen v místech přístupných řádně označeným a oprávněným osobám s technickými znalostmi nebo zkušenostmi umožňujícími vyhnout se nebezpečí.","source":"tab. ZA.1, s. 28"},
    ],
    "BC": [
        {"code":"BC1","label":"kontakt osob s potenciálem země – žádný","requirement":"Žádný kontakt s potenciálem země; osoby jsou v nevodivém prostředí.","source":"tab. ZA.1, s. 28"},
        {"code":"BC2","label":"kontakt výjimečný","requirement":"Příležitostný kontakt; osoby se obvykle nedotýkají cizích vodivých částí ani nestojí na vodivém podkladu. V ČR je BC2 považován za normální.","source":"tab. ZA.1, s. 28"},
        {"code":"BC3","label":"kontakt částečný","requirement":"Častý kontakt; osoby se obvykle dotýkají cizích vodivých částí nebo stojí na vodivém podkladu. Volbu ochrany přizpůsobit konkrétním podmínkám.","source":"tab. ZA.1, s. 28"},
        {"code":"BC4","label":"kontakt trvalý","requirement":"Trvalý kontakt; osoby jsou ponořené ve vodě nebo dlouhodobě v kontaktu s kovovým prostředím a možnost přerušení kontaktu je omezená. Konkrétní opatření se zvažují individuálně.","source":"tab. ZA.1, s. 28"},
    ],
    "BD": [
        {"code":"BD1","label":"malá hustota osob / snadný únik","requirement":"Malý počet osob a snadné podmínky pro evakuaci; normální podmínky.","source":"tab. ZA.1, s. 29"},
        {"code":"BD2","label":"malá hustota osob / obtížný únik","requirement":"Malý počet osob, obtížné podmínky pro evakuaci (např. vícepodlažní budovy); konkrétní opatření určit podle požárně bezpečnostního řešení a souvisejících předpisů.","source":"tab. ZA.1, s. 29"},
        {"code":"BD3","label":"velká hustota osob / snadný únik","requirement":"Vysoký počet osob, snadné podmínky pro evakuaci (např. veřejně přístupná místa); konkrétní opatření určit podle požárně bezpečnostního řešení a souvisejících předpisů.","source":"tab. ZA.1, s. 29"},
        {"code":"BD4","label":"velká hustota osob / obtížný únik","requirement":"Vysoký počet osob, obtížné podmínky pro evakuaci (např. vícepodlažní veřejně přístupné budovy); konkrétní opatření určit podle požárně bezpečnostního řešení a souvisejících předpisů.","source":"tab. ZA.1, s. 29"},
    ],
    "BE": [
        {"code":"BE1","label":"bez významného nebezpečí","requirement":"Bez významného nebezpečí; normální podmínky.","source":"tab. ZA.1, s. 29"},
        {"code":"BE2","label":"nebezpečí požáru","requirement":"Nebezpečí požáru při výrobě, zpracování nebo skladování hořlavých materiálů včetně prachu; zařízení musí omezovat šíření plamene a úpravami zabránit tomu, aby oteplení nebo jiskra způsobily požár.","source":"tab. ZA.1, s. 29"},
        {"code":"BE3","label":"nebezpečí výbuchu","requirement":"Nebezpečí výbuchu; požadavky na elektrická zařízení určená pro použití ve výbušné atmosféře řešit podle souboru EN 60079 a podle konkrétní klasifikace prostoru.","source":"tab. ZA.1, s. 29"},
        {"code":"BE4","label":"nebezpečí kontaminace","requirement":"Nebezpečí kontaminace nechráněných potravin, léčiv nebo obdobných produktů; podle provozu zabránit kontaminaci např. úlomky z rozbitých světelných zdrojů a škodlivým zářením.","source":"tab. ZA.1, s. 29"},
    ],
    "CA": [
        {"code":"CA1","label":"stavební materiál – nehořlavý","requirement":"Nehořlavé stavební materiály; normální podmínky.","source":"tab. ZA.1, s. 30"},
        {"code":"CA2","label":"stavební materiál – hořlavý","requirement":"Hořlavé stavební materiály / dřevostavby; konkrétní opatření se zvažují podle ochrany před tepelnými účinky a souvisejících pravidel.","source":"tab. ZA.1, s. 30"},
    ],
    "CB": [
        {"code":"CB1","label":"konstrukce budovy – zanedbatelné nebezpečí","requirement":"Zanedbatelné nebezpečí konstrukce budovy; normální podmínky.","source":"tab. ZA.1, s. 30"},
        {"code":"CB2","label":"šíření požáru","requirement":"Nebezpečí šíření požáru; použít zařízení z materiálu zpomalujícího šíření požáru a zachovat / doplnit protipožární bariéry.","source":"tab. ZA.1, s. 30"},
        {"code":"CB3","label":"posun konstrukce","requirement":"Posun konstrukce; zohlednit pohyb konstrukce a použít kontrakční nebo expanzní spoje v elektrickém vedení podle potřeby.","source":"tab. ZA.1, s. 30"},
        {"code":"CB4","label":"poddajná nebo nestabilní konstrukce","requirement":"Poddajná nebo nestabilní konstrukce; instalace musí být konstrukčně samonosná a podle potřeby použít ohebné vedení.","source":"tab. ZA.1, s. 30"},
    ],
}

# Parametry, u nichž checklist dovoluje více současně platných tříd.
# U ostatních skupin se při zaškrtnutí nové položky předchozí automaticky zruší.
CHECKLIST_MULTISELECT = {"AM", "BA"}

VALUE_OPTIONS: dict[str, list[str]] = {
    group: [item["code"] for item in items] for group, items in CHECKLIST_OPTIONS.items()
}

VALUE_HINTS = {
    item["code"]: item["label"]
    for items in CHECKLIST_OPTIONS.values()
    for item in items
}


def checklist_item(code: str) -> dict[str, str]:
    target=str(code or "").strip().upper()
    for items in CHECKLIST_OPTIONS.values():
        for item in items:
            if item["code"].upper() == target:
                return dict(item)
    return {}


def checklist_requirement(group: str, value: Any) -> str:
    parts=[]
    for token in _expanded_tokens(group, value):
        item=checklist_item(token)
        if item:
            line=item.get("requirement","")
            source=item.get("source","")
            if source:
                line += (" — " if line else "") + source
            if line and line not in parts:
                parts.append(line)
    return " | ".join(parts)

# Pomocná klasifikace je pracovní kontrola nad vybranými třídami. Nenahrazuje odborné
# určení. Odpovídá způsobu vyhodnocení v dodaném vzorovém protokolu.
ABNORMAL_VALUES: dict[str, set[str]] = {
    # Audit 0.4.32: klasifikace podle ČSN 33 2000-5-51 ed.3+Z1+Z2, tab. ZA.1.
    # AA4/AA5 a AB4/AB5 jsou normální; AQ2 je normální; v ČR je BC2 normální.
    "AA": {"AA1", "AA2", "AA3", "AA6", "AA7", "AA8"},
    "AB": {"AB1", "AB2", "AB3", "AB6", "AB7", "AB8"},
    "AC": {"AC2"},
    "AD": {"AD2", "AD3", "AD4", "AD5", "AD6", "AD7", "AD8"},
    "AE": {"AE2", "AE3", "AE4", "AE5", "AE6"},
    "AF": {"AF2", "AF3", "AF4"},
    "AG": {"AG2", "AG3"},
    "AH": {"AH2", "AH3"},
    "AK": {"AK2"},
    "AL": {"AL2"},
    "AM": {
        "AM-1-1", "AM-1-3", "AM-2-1", "AM-2-3", "AM-3-1", "AM-4", "AM-6", "AM-7",
        "AM-8-2", "AM-9-2", "AM-9-3", "AM-9-4", "AM-22-1", "AM-22-2", "AM-22-4",
        "AM-23-1", "AM-23-2", "AM-23-3", "AM-24-1", "AM-24-2", "AM-25-2", "AM-25-3",
        "AM-31-4", "AM-41-1",
    },
    "AN": {"AN2", "AN3"},
    "AP": {"AP2", "AP3", "AP4"},
    "AQ": {"AQ3"},
    "AR": {"AR2", "AR3"},
    "AS": {"AS2", "AS3"},
    "BA": {"BA2", "BA3", "BA4", "BA5"},
    "BC": {"BC3", "BC4"},
    "BD": {"BD2", "BD3", "BD4"},
    "BE": {"BE2", "BE3", "BE4"},
    "CA": {"CA2"},
    "CB": {"CB2", "CB3", "CB4"},
}

# Některé třídy nemusí být v pracovním členění označeny jako abnormální, přesto
# mají vlastní provozní / přístupové požadavky. Typický příklad je BA4/BA5 ve
# vzorovém protokolu. I tyto položky proto musí být v editoru opatření dostupné.
MEASURE_REQUIRED_VALUES: dict[str, set[str]] = {k: set(v) for k, v in ABNORMAL_VALUES.items()}
MEASURE_REQUIRED_VALUES.setdefault("BA", set()).update({"BA2", "BA3", "BA4", "BA5"})

IP_BY_WATER = {
    "AD1": "IPX0", "AD2": "IPX1/IPX2", "AD3": "IPX3", "AD4": "IPX4",
    "AD5": "IPX5", "AD6": "IPX6", "AD7": "IPX7", "AD8": "IPX8",
}
# Pro AE se zobrazuje pouze část přiřazení, kterou modul používá jako jistou pracovní
# pomůcku; vyšší třídy prachu se nechávají k odbornému posouzení.
IP_BY_SOLIDS = {"AE1": "IP0X", "AE2": "IP3X", "AE3": "IP4X", "AE4": "IP5X/IP6X", "AE5": "IP6X", "AE6": "IP6X"}


def _expanded_tokens(group: str, value: Any) -> list[str]:
    text=str(value or "").upper().replace(" ", "")
    if not text or text == "---":
        return []
    raw=[x for x in re.split(r"[,;/]+", text) if x]
    out=[]
    for token in raw:
        if token.startswith(group):
            out.append(token)
        elif re.fullmatch(r"\d+(?:-\d+)?", token):
            out.append(group+token)
        else:
            out.append(token)
    return out


def abnormal_codes(values: dict[str, Any]) -> list[str]:
    out=[]
    for group in DISPLAY_COLUMNS:
        tokens=_expanded_tokens(group, values.get(group, ""))
        if any(token in ABNORMAL_VALUES.get(group, set()) for token in tokens):
            out.append(str(values.get(group, "") or "").strip())
    return out


def parse_abnormal_measures_json(value: Any) -> dict[str, str]:
    """Return editable per-VV measure texts stored with a room.

    The keys are exact abnormal VV codes (for example AD4 or BC3).  This is
    deliberately separate from the optional numbered measure catalogue used by
    the example protocol.
    """
    if isinstance(value, dict):
        obj=value
    else:
        try:
            obj=json.loads(value or "{}")
        except Exception:
            obj={}
    if not isinstance(obj, dict):
        return {}
    out={}
    for k,v in obj.items():
        key=str(k or "").strip().upper()
        if not key:
            continue
        if key in {"AM1-1","AM1-2","AM1-3"}:
            key=key.replace("AM1-","AM-1-")
        elif key in {"BE2N1","BE2N2","BE2N3"}:
            key="BE2"
        elif key in {"BE3N1","BE3N2","BE3N3"}:
            key="BE3"
        text=str(v or "").strip()
        if text or key not in out:
            out[key]=text
    return out


def serialize_abnormal_measures(value: dict[str, Any] | None) -> str:
    data={str(k or "").strip().upper(): str(v or "").strip() for k,v in (value or {}).items() if str(k or "").strip()}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def measure_entries(values: dict[str, Any], measure_overrides: Any = None) -> list[dict[str, Any]]:
    """Return editable requirements for every selected VV that needs an explicit measure.

    All values classified as abnormal are included.  BA2-BA5 are abnormal in the
    audited working classification because they carry explicit requirements for
    the persons using or accessing the installation.
    """
    overrides=parse_abnormal_measures_json(measure_overrides)
    entries: list[dict[str, Any]] = []
    for group in DISPLAY_COLUMNS:
        for token in _expanded_tokens(group, values.get(group, "")):
            if token not in MEASURE_REQUIRED_VALUES.get(group, set()):
                continue
            item = checklist_item(token)
            default_requirement = str(item.get("requirement", "") or "").strip() if item else ""
            requirement = overrides[token] if token in overrides else default_requirement
            source = str(item.get("source", "") or "").strip() if item else ""
            label = str(item.get("label", "") or "").strip() if item else ""
            text=str(requirement or "").strip()
            entries.append({
                "group": group,
                "code": token,
                "name": INFLUENCE_META.get(group, {}).get("name", group),
                "label": label,
                "requirement": requirement,
                "default_requirement": default_requirement,
                "source": source,
                "custom": token in overrides,
                "abnormal": token in ABNORMAL_VALUES.get(group, set()),
                "complete": bool(text) and not text.upper().startswith("DOPLNIT"),
            })
    return entries


def abnormal_measure_entries(values: dict[str, Any], measure_overrides: Any = None) -> list[dict[str, Any]]:
    """Backward-compatible helper returning only measures for abnormal VV."""
    return [x for x in measure_entries(values, measure_overrides) if x.get("abnormal")]


def classify_environment(values: dict[str, Any]) -> str:
    vals={c:str(values.get(c, "") or "").strip() for c in DISPLAY_COLUMNS}
    if any(not vals[c] for c in DISPLAY_COLUMNS):
        return "K DOPLNĚNÍ"
    return "ABNORMÁLNÍ" if abnormal_codes(vals) else "NORMÁLNÍ"


def minimum_ip(values: dict[str, Any]) -> tuple[str, str]:
    ad=str(values.get("AD", "") or "").strip().upper()
    ae=str(values.get("AE", "") or "").strip().upper()
    return IP_BY_WATER.get(ad, ""), IP_BY_SOLIDS.get(ae, "")

# Číselník opatření je snapshot dodaného souhrnného protokolu.
MEASURE_LIBRARY: "OrderedDict[str, dict[str, str]]" = OrderedDict([
    ("1", {"title": "Umývací prostory", "text": "Řešit dle ČSN 33 2130 ed. 4 – Vnitřní elektrické rozvody."}),
    ("2", {"title": "Atmosférické podmínky", "text": "Zařízení musí být určeno pro instalaci a provoz v požadovaném rozsahu teplot a relativní vlhkosti."}),
    ("3", {"title": "BD2 – malý počet osob / nesnadný odchod", "text": "Řešit s ohledem na ČSN 33 2000-7-718 a ČSN 73 0848."}),
    ("4", {"title": "BD3 – vysoký počet osob / snadný odchod", "text": "Řešit s ohledem na ČSN 33 2000-7-718 a ČSN 73 0848."}),
    ("5", {"title": "BA4 – osoba poučená", "text": "Nechráněné živé části pouze v místech přístupných řádně pověřeným osobám; obsluhu a práci smějí vykonávat osoby poučené v odpovídajícím rozsahu."}),
    ("6", {"title": "Prostory s vanou nebo sprchou", "text": "Řešit dle ČSN 33 2000-7-701 ed. 3."}),
    ("7", {"title": "AD4 – výskyt vody", "text": "Elektrická zařízení musí mít nejméně krytí IPX4; konkrétní rozsah opatření se určí pro daný prostor."}),
    ("8", {"title": "BA5 – osoba znalá", "text": "Nechráněné živé části pouze v místech přístupných řádně pověřeným osobám; obsluhu a práci smějí vykonávat osoby znalé s odpovídající elektrotechnickou kvalifikací."}),
    ("9", {"title": "CA2 – hořlavé stavební materiály", "text": "Elektrická zařízení provést podle požadavků ČSN 33 2000-4-42 ed. 2."}),
    ("10", {"title": "Nabíjení elektrických vozidel", "text": "Elektrická zařízení provést podle ČSN 33 2000-7-722 ed. 3."}),
])

# Základ profilu vychází z tabulek dodaného protokolu. U profilů jsou uložené
# pouze prakticky používané hodnoty; lze je kdykoliv ručně změnit.
BASE_HEATED = {
    "AA": "AA5", "AB": "AB5", "AC": "AC1", "AD": "AD1", "AE": "AE1", "AF": "AF1",
    "AG": "AG1", "AH": "AH1", "AK": "AK1", "AL": "AL1", "AM": "AM-1-2", "AN": "AN1",
    "AP": "AP1", "AQ": "AQ2", "AR": "AR1", "AS": "AS1", "BA": "BA1", "BC": "BC2",
    "BD": "BD1", "BE": "BE1", "CA": "CA1", "CB": "CB1",
}

BASE_TABLE_ROOM = {
    "AA": "AA5", "AB": "AB5", "AC": "AC1", "AD": "AD1", "AE": "AE1", "AF": "AF1",
    "AG": "AG1", "AH": "AH1", "AK": "AK1", "AL": "AL1", "AM": "AM-1-2", "AN": "AN1",
    "AP": "AP1", "AQ": "AQ2", "AR": "AR1", "AS": "AS1", "BA": "BA1", "BC": "BC2",
    "BD": "BD1", "BE": "BE1", "CA": "CA1", "CB": "CB1",
}


def _profile(base: dict[str, str], **overrides: str) -> dict[str, str]:
    out = dict(base)
    out.update(overrides)
    return out


PROFILE_LIBRARY: "OrderedDict[str, dict[str, Any]]" = OrderedDict([
    ("Vytápěný prostor vnitřní", {"values": _profile(BASE_HEATED), "measures": "", "space_class": "NORMÁLNÍ"}),
    ("Nevytápěný prostor vnitřní", {"values": _profile(BASE_HEATED, AA="AA4", AB="AB4"), "measures": "", "space_class": "NORMÁLNÍ"}),
    ("Chladicí box", {"values": _profile(BASE_HEATED, AA="AA4", AB="AB4", BA="BA4", BC="BC3"), "measures": "", "space_class": "ABNORMÁLNÍ"}),
    ("Mrazicí box", {"values": _profile(BASE_HEATED, AA="AA8", AB="AB8", BA="BA4", BC="BC3"), "measures": "", "space_class": "ABNORMÁLNÍ"}),
    ("Vytápěný vnitřní – stříkající voda", {"values": _profile(BASE_HEATED, AD="AD4", BA="BA4", BC="BC3"), "measures": "", "space_class": "ABNORMÁLNÍ"}),
    ("Venkovní prostor", {"values": _profile(BASE_HEATED, AA="AA8", AB="AB8", AD="AD4", BA="BA4", BC="BC2"), "measures": "", "space_class": "ABNORMÁLNÍ"}),
    ("Venkovní – rozvodny / střechy", {"values": _profile(BASE_HEATED, AA="AA8", AB="AB8", AD="AD4", BA="BA5", BC="BC3"), "measures": "", "space_class": "ABNORMÁLNÍ"}),
    ("Prostor s nebezpečím požáru", {"values": _profile(BASE_HEATED, BA="BA4", BC="BC3", BE="BE2"), "measures": "", "space_class": "ABNORMÁLNÍ"}),
    ("Rozvodna / elektrická provozovna / motogenerátor", {"values": _profile(BASE_HEATED, BA="BA5", BC="BC3"), "measures": "", "space_class": "ABNORMÁLNÍ"}),
    ("Běžná místnost – formát tabulky D1", {"values": _profile(BASE_TABLE_ROOM), "measures": "", "space_class": "NORMÁLNÍ"}),
])


def normalize_measure_codes(value: Any) -> str:
    """Return unique measure numbers sorted numerically, preserving unknown tokens last."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = [p for p in re.split(r"[,;.\s]+", raw) if p]
    seen: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in seen:
            seen.append(p)
    known = sorted((p for p in seen if p.isdigit()), key=lambda x: int(x))
    unknown = [p for p in seen if not p.isdigit()]
    return ",".join(known + unknown)


def measure_codes_list(value: Any) -> list[str]:
    normalized = normalize_measure_codes(value)
    return [p for p in normalized.split(",") if p]


def measures_text(value: Any) -> str:
    lines = []
    for code in measure_codes_list(value):
        item = MEASURE_LIBRARY.get(code)
        if item:
            lines.append(f"D{code}. {item['title']}: {item['text']}")
        else:
            lines.append(f"D{code}. Vlastní / neznámé doplňkové opatření – ověřit popis v protokolu.")
    return "\n".join(lines)




def normalize_legacy_value_token(group: str, token: str) -> str:
    """Normalize values used by pre-0.4.32 test protocols to current ed.3+Z1+Z2 codes."""
    t=str(token or "").strip().upper()
    if group == "AM" and t in {"AM1-1","AM1-2","AM1-3"}:
        return t.replace("AM1-", "AM-1-")
    if group == "BE":
        if t in {"BE2N1","BE2N2","BE2N3"}: return "BE2"
        if t in {"BE3N1","BE3N2","BE3N3"}: return "BE3"
    return t

def parse_values_json(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        obj = value
    else:
        try:
            obj = json.loads(value or "{}")
        except Exception:
            obj = {}
    out = {}
    for code in DISPLAY_COLUMNS:
        raw = str(obj.get(code, "") or "").strip()
        if not raw:
            out[code] = ""
            continue
        parts = [p for p in re.split(r"[,;/\s]+", raw) if p]
        norm = []
        for p in parts:
            q = normalize_legacy_value_token(code, p)
            if q not in norm:
                norm.append(q)
        out[code] = ", ".join(norm) if code in CHECKLIST_MULTISELECT else (norm[0] if norm else raw)
    return out


def serialize_values(values: dict[str, Any]) -> str:
    return json.dumps({c: str(values.get(c, "") or "").strip() for c in DISPLAY_COLUMNS}, ensure_ascii=False, separators=(",", ":"))


def blank_room(floor: str = "", room_no: str = "", room_name: str = "") -> dict[str, Any]:
    values = {c: "" for c in DISPLAY_COLUMNS}
    return {
        "floor": floor, "room_no": room_no, "room_name": room_name,
        "values_json": serialize_values(values), "measure_codes": "",
        "environment_class": "K DOPLNĚNÍ", "source_sheet": "", "sort_order": 0,
        "code": "", "value_code": "", "description": "", "measure": "",
        "result": "K doplnění", "note": "", "room_description": "",
        "abnormal_measures_json": "{}",
    }


def apply_profile(room: dict[str, Any] | None, profile_name: str) -> dict[str, Any]:
    result = dict(room or blank_room())
    profile = PROFILE_LIBRARY.get(profile_name)
    if not profile:
        return result
    values = parse_values_json(result.get("values_json"))
    values.update(profile["values"])
    result["values_json"] = serialize_values(values)
    result["measure_codes"] = normalize_measure_codes(profile.get("measures", ""))
    result["measure"] = measures_text(result["measure_codes"])
    result["environment_class"] = profile.get("space_class", "URČENO")
    result["result"] = "Určeno"
    result["description"] = profile_name
    return result


def room_from_db(row: Any) -> dict[str, Any]:
    """Normalize sqlite.Row/dict including legacy one-influence rows."""
    d = dict(row or {})
    if d.get("values_json"):
        d["values_json"] = serialize_values(parse_values_json(d.get("values_json")))
    else:
        values = {c: "" for c in DISPLAY_COLUMNS}
        code = str(d.get("code", "") or "").strip().upper()
        if code in values:
            values[code] = str(d.get("value_code", "") or "").strip()
        d["values_json"] = serialize_values(values)
        if not d.get("room_name"):
            d["room_name"] = str(d.get("description", "") or "Původní záznam")
        if not d.get("measure_codes"):
            # Legacy measure can be a full sentence; do not invent numeric codes.
            d["measure_codes"] = ""
    d.setdefault("floor", "")
    d.setdefault("room_no", "")
    d.setdefault("room_name", "")
    d.setdefault("measure_codes", "")
    d.setdefault("environment_class", "")
    d.setdefault("source_sheet", "")
    d.setdefault("sort_order", 0)
    d.setdefault("note", "")
    d.setdefault("room_description", "")
    d.setdefault("abnormal_measures_json", "{}")
    d["abnormal_measures_json"] = serialize_abnormal_measures(parse_abnormal_measures_json(d.get("abnormal_measures_json")))
    if not d.get("room_description") and d.get("note"):
        d["room_description"] = str(d.get("note") or "")
    d.setdefault("result", "")
    return d


def _has_token(value: str, token: str) -> bool:
    text = str(value or "").upper().replace(" ", "")
    target = token.upper().replace(" ", "")
    return target in {p for p in re.split(r"[,;/]+", text) if p} or target in text


def suggest_measures(values: dict[str, Any], room_name: str = "") -> list[str]:
    """Conservative suggestions based on the supplied protocol's measure index.

    Suggestions are never silently written to the room. BE2 is intentionally not mapped to
    measure 10: the supplied source uses that number on a BE2 row while its measure index
    defines 10 as EV charging, so the ambiguity must be reviewed by the user.
    """
    suggestions: list[str] = []
    def add(code: str):
        if code not in suggestions:
            suggestions.append(code)

    vals = {k: str(v or "").upper().replace(" ", "") for k, v in values.items()}
    if vals.get("AA") in {"AA1", "AA2", "AA3", "AA6", "AA7", "AA8"} or vals.get("AB") in {"AB1", "AB2", "AB3", "AB6", "AB7", "AB8"}:
        add("2")
    if vals.get("BD") == "BD2": add("3")
    if vals.get("BD") == "BD3": add("4")
    if "BA4" in vals.get("BA", ""): add("5")
    if vals.get("AD") == "AD4": add("7")
    if "BA5" in vals.get("BA", ""): add("8")
    if vals.get("CA") == "CA2": add("9")

    name = (room_name or "").lower()
    if any(x in name for x in ("umýv", "umyv", "mytí", "myti", "úklid", "uklid")): add("1")
    if any(x in name for x in ("sprch", "koupel", "vana", "hyg.")): add("6")
    if any(x in name for x in ("nabíj", "nabij", "ev charger", "wallbox")): add("10")
    return suggestions


def room_warnings(room: dict[str, Any]) -> list[str]:
    values = parse_values_json(room.get("values_json"))
    warnings: list[str] = []
    # Číslo místnosti není povinné (např. technologické celky na střeše jej v podkladu nemají).
    if not str(room.get("room_name", "") or "").strip(): warnings.append("chybí název místnosti")
    missing = [c for c in DISPLAY_COLUMNS if not values.get(c)]
    if missing: warnings.append("nevyplněné vlivy: " + ", ".join(missing))
    for code, value in values.items():
        v = (value or "").strip().upper()
        if not v or v == "---":
            continue
        # Composite codes such as BA1,4 and AM-1-2 are accepted. Warn only on obvious prefix mismatch.
        tokens = [x for x in re.split(r"[,;/\s]+", v) if x]
        if tokens and all(not t.startswith(code) for t in tokens) and not v.startswith(code):
            warnings.append(f"{code}: hodnota „{value}“ neodpovídá označení sloupce")
    computed=classify_environment(values)
    stored=str(room.get("environment_class", "") or "").strip().upper()
    if computed in {"NORMÁLNÍ", "ABNORMÁLNÍ"} and stored in {"NORMÁLNÍ", "ABNORMÁLNÍ"} and stored != computed:
        warnings.append(f"klasifikace prostoru je {stored}, pomocné vyhodnocení dává {computed}")
    auto_measures=measure_entries(values, room.get("abnormal_measures_json"))
    missing_measures=[x["code"] for x in auto_measures if not x.get("complete")]
    if missing_measures:
        warnings.append("chybí konkrétní opatření / požadavek pro vliv: " + ", ".join(missing_measures))
    return warnings


def row_status(room: dict[str, Any]) -> str:
    warnings = room_warnings(room)
    if any(w.startswith("chybí") or w.startswith("nevyplněné") for w in warnings):
        return "K doplnění"
    if warnings:
        return "Ověřit podklad"
    return str(room.get("environment_class") or "Určeno")


def merge_legacy_rows(rows: Iterable[Any]) -> list[dict[str, Any]]:
    """Keep modern room rows as-is and collapse truly legacy code/value rows per pseudo-room."""
    modern: list[dict[str, Any]] = []
    legacy: list[dict[str, Any]] = []
    for raw in rows:
        d = dict(raw)
        if d.get("values_json") or d.get("room_no") or d.get("room_name"):
            modern.append(room_from_db(d))
        else:
            legacy.append(d)
    if legacy:
        room = blank_room(room_name="Původní záznamy vnějších vlivů")
        values = parse_values_json(room["values_json"])
        notes = []
        for d in legacy:
            code = str(d.get("code", "") or "").strip().upper()
            if code in values:
                values[code] = str(d.get("value_code", "") or "").strip()
            if d.get("measure"):
                notes.append(f"{code}: {d.get('measure')}")
            if d.get("note"):
                notes.append(str(d.get("note")))
        room["values_json"] = serialize_values(values)
        room["note"] = "\n".join(notes)
        room["result"] = "Určeno"
        modern.insert(0, room)
    for i, room in enumerate(modern, 1):
        if not room.get("sort_order"):
            room["sort_order"] = i
    return modern


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _find_code_row(ws) -> tuple[int, dict[str, int]]:
    """Locate the row containing AA..CB headers and return code->column mapping."""
    for row in range(1, min(ws.max_row, 30) + 1):
        found: dict[str, int] = {}
        for col in range(1, ws.max_column + 1):
            value = _text(ws.cell(row, col).value).upper()
            if value in DISPLAY_COLUMNS:
                found[value] = col
        if len(found) >= 12 and "AA" in found and "CB" in found:
            return row, found
    raise ValueError(f"List „{ws.title}“ neobsahuje rozpoznatelný řádek kódů AA…CB.")


def _find_room_columns(ws, code_row: int, code_map: dict[str, int]) -> tuple[int, int, int | None]:
    aa_col = code_map["AA"]
    room_no_col = max(1, aa_col - 2)
    room_name_col = max(1, aa_col - 1)
    measure_col = None
    # Prefer a header explicitly named Opatření in a few rows above code row.
    for r in range(max(1, code_row - 4), code_row + 2):
        for c in range(1, ws.max_column + 1):
            if "OPATŘ" in _text(ws.cell(r, c).value).upper():
                measure_col = c
    if measure_col is None:
        measure_col = min(ws.max_column, max(code_map.values()) + 1)
    return room_no_col, room_name_col, measure_col


def import_rooms_xlsx(path: str | Path) -> list[dict[str, Any]]:
    from openpyxl import load_workbook

    wb = load_workbook(filename=str(path), data_only=True, read_only=False)
    rooms: list[dict[str, Any]] = []
    order = 0
    for ws in wb.worksheets:
        try:
            code_row, code_map = _find_code_row(ws)
        except ValueError:
            continue
        room_no_col, room_name_col, measure_col = _find_room_columns(ws, code_row, code_map)
        floor = ws.title.strip()
        for r in range(code_row + 1, ws.max_row + 1):
            room_no = _text(ws.cell(r, room_no_col).value)
            room_name = _text(ws.cell(r, room_name_col).value)
            # Skip the line "Podlaží ..." and empty lines.
            if not room_no and not room_name:
                continue
            combined = f"{room_no} {room_name}".strip().lower()
            if combined.startswith("podlaží") or combined.startswith("podlazi"):
                continue
            # A room row must have at least one influence code value.
            values = {code: _text(ws.cell(r, col).value) for code, col in code_map.items() if code in DISPLAY_COLUMNS}
            for code in DISPLAY_COLUMNS:
                values.setdefault(code, "")
            if not any(values.values()):
                continue
            order += 1
            measures = normalize_measure_codes(ws.cell(r, measure_col).value if measure_col else "")
            room = blank_room(floor=floor, room_no=room_no, room_name=room_name)
            room.update({
                "values_json": serialize_values(values),
                "measure_codes": measures,
                "measure": measures_text(measures),
                "environment_class": "URČENO",
                "result": "Určeno",
                "source_sheet": ws.title,
                "sort_order": order,
                "description": "Import XLSX",
            })
            rooms.append(room)
    if not rooms:
        raise ValueError("V sešitu nebyly nalezeny žádné řádky místností s vnějšími vlivy.")
    return rooms


def export_rooms_xlsx(path: str | Path, rooms: Iterable[dict[str, Any]]) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    data = [room_from_db(r) for r in rooms]
    wb = Workbook()
    wb.remove(wb.active)
    grouped: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for r in data:
        grouped.setdefault(str(r.get("floor") or "Bez podlaží"), []).append(r)
    if not grouped:
        grouped["Bez podlaží"] = []

    thin = Side(style="thin", color="B7BEC7")
    header_fill = PatternFill("solid", fgColor="DDE2E7")
    for floor, floor_rooms in grouped.items():
        title = re.sub(r"[\\/*?:\[\]]", "_", floor)[:31] or "Podlaží"
        original = title; n = 2
        while title in wb.sheetnames:
            suffix = f"_{n}"; title = (original[:31-len(suffix)] + suffix); n += 1
        ws = wb.create_sheet(title)
        ws.append(["Č.m.", "Název místnosti"] + DISPLAY_COLUMNS + ["Opatření / požadavky k VV", "Doplňková opatření", "Stav", "Popis prostoru", "Poznámka"])
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        for room in floor_rooms:
            values = parse_values_json(room.get("values_json"))
            aentries=measure_entries(values, room.get("abnormal_measures_json"))
            abnormal_text=" | ".join(f"{x['code']}: {x['requirement']}" for x in aentries)
            ws.append([
                room.get("room_no", ""), room.get("room_name", ""),
                *[values.get(c, "") for c in DISPLAY_COLUMNS],
                abnormal_text, normalize_measure_codes(room.get("measure_codes", "")), row_status(room),
                room.get("room_description", ""), room.get("note", ""),
            ])
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions
        ws.column_dimensions["A"].width = 13
        ws.column_dimensions["B"].width = 32
        for idx in range(3, 3 + len(DISPLAY_COLUMNS)):
            ws.column_dimensions[get_column_letter(idx)].width = 9
        ws.column_dimensions[get_column_letter(3 + len(DISPLAY_COLUMNS))].width = 55
        ws.column_dimensions[get_column_letter(4 + len(DISPLAY_COLUMNS))].width = 16
        ws.column_dimensions[get_column_letter(5 + len(DISPLAY_COLUMNS))].width = 18
        ws.column_dimensions[get_column_letter(6 + len(DISPLAY_COLUMNS))].width = 45
        ws.column_dimensions[get_column_letter(7 + len(DISPLAY_COLUMNS))].width = 35
        ws.sheet_view.showGridLines = False
        ws.print_title_rows = "1:1"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.sheet_properties.pageSetUpPr.fitToPage = True
    target = str(path)
    wb.save(target)
    return target


def room_summary(room: dict[str, Any]) -> str:
    values = parse_values_json(room.get("values_json"))
    return " ".join(values.get(c, "") for c in DISPLAY_COLUMNS if values.get(c))
