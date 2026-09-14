PZ-REVIZE 0.4.35

NOVINKY 0.4.35

- Samostatné a jasně označené akce „Nová revize“ a „Nový VV“.
- Přehled i detail zákazníka nabízejí všechny moduly: elektro, stroj, LPS a VV.
- Ochrana proti ztrátě neodeslaných revizí funguje i při ručním stažení celé DB z NAS.
- Stav se kontroluje ještě jednou přímo před nahrazením místní databáze.
- Pokud se během stahování otevře editor nebo uloží nová revize, stažení se zastaví.
- Změna uložená během odesílání zůstane označena jako čekající na další synchronizaci.
- Při nezávislých změnách na dvou PC vznikne konflikt: oba stavy zůstávají zachované, automatické spojení celé DB zatím není podporované.
- Před spuštěním aktualizace si udělej kopii %LOCALAPPDATA%\PZ-REVIZE včetně backups a attachments.
- Pro hledání již ztracené revize spusť NAJIT_REVIZI_V_ZALOHACH.bat. Tento nástroj zálohy nemění.
- Podrobnosti: ZMENY_0.4.35.txt.


NOVINKY 0.4.33
- Bezpečná automatická synchronizace NAS při spuštění, průběžně, po uložení revize a při zavření programu.
- Lokální revize navíc se už kvůli vyšší generaci NAS nikdy automaticky nesmažou: program nejprve porovná oba stavy a lokální nadmnožinu odešle bez předchozího destruktivního stažení.
- Při skutečném konfliktu se nic nepřepíše; při zavírání vznikne bezpečnostní ZIP záloha.
- Strojní zařízení má nově klasické elektrické měření: obvod, měřicí bod, spojitost a RCD/RCBO stejně jako EI.
- Podrobnosti jsou v souboru ZMENY_0.4.33.txt.

NOVINKY 0.4.32
- Kompletní audit modulu Vnější vlivy proti ČSN 33 2000-5-51 ed.3 + Z1 + Z2 (konsolidované vydání 07/2022, tabulka ZA.1).
- Opraveny normální třídy, aktuální kódy AM a BE a normové návrhy opatření AA–CB.
- Vnější vlivy: Kopírovat místnost (Ctrl+D) a ukládání konkrétní místnosti jako vlastního rychlého profilu včetně individuálních opatření.
- Kolečko myši nyní posouvá formuláře, seznamy, tabulky a textové oblasti napříč celým programem.
- Zachovány opravy 0.4.31: tabulka VV se vejde na A4, okna respektují pracovní plochu, ESC zavírá dialog a F11 přepíná fullscreen.
- Podrobnosti jsou v souborech ZMENY_0.4.32.txt a AUDIT_VNEJSI_VLIVY_0.4.32.txt.

NOVINKY 0.4.30
- Kompletně zkontrolován pracovní katalog opatření vnějších vlivů AA–CB proti nahranému normovému podkladu a vzorovému protokolu.
- Opatření lze nastavit pro každý vliv, který vyžaduje zvláštní požadavek; zahrnuty jsou i BA2–BA5.
- BA4 a BA5 mají opravený požadavek na přístup řádně pověřených osob a odpovídající kvalifikaci obsluhy/práce.
- Výstupní matice VV byla přepracována podle vzoru: plné názvy vlivů svisle, řádek AA–CB, samostatný sloupec opatření a zvýraznění vlivů s opatřením.
- Editor místnosti se přizpůsobuje výšce obrazovky a tlačítka Zrušit / Uložit místnost zůstávají vždy dole dostupná.
- Nejednoznačné případy, které vyžadují konkrétní odborné posouzení, jsou označeny DOPLNIT a kontrola je nepovažuje za uzavřené.
- Podrobnosti jsou v souboru ZMENY_0.4.30.txt.


NOVINKY 0.4.28
- Každý abnormální vnější vliv má automaticky vlastní dohledatelné opatření ve výsledném protokolu.
- Obecné je prázdné velké textové pole pro popis celé budovy s odrážkami a číslováním.
- Všechny vybrané normy / předpisy se tisknou do samostatné kapitoly protokolu VV.
- Podrobnosti jsou v souboru ZMENY_0.4.28.txt.


NOVINKY 0.4.22
- Modul Vnější vlivy je přepracován na checklist A / B / C pro každou místnost.
- U položek se zobrazují stručné charakteristiky, požadavky a zdrojové tabulky.
- První strana protokolu VV je nově podle dodaného vzoru.
- Výstup VV má vlastní strukturu: popis objektu, podklady, normy, matice místností a opatření.
- Podrobnosti jsou v souboru ZMENY_0.4.22.txt.


NOVINKY 0.4.21
- V tabulce měření lze vložit samostatný textový řádek / poznámku.
- Poznámku lze vložit do struktury pod obvod nebo RCD/RCBO a následně ji upravit, přesouvat nebo smazat.
- Textová poznámka se tiskne přes celou šířku tabulky měření v PDF.
- Stejná možnost je dostupná také v tabulce měření strojního zařízení.


NOVINKY 0.4.20
- Modul Vnější vlivy je plně začleněn do hlavního programu PZ-REVIZE.
- Editor místností AA–CB průběžně pomocně vyhodnocuje prostor jako NORMÁLNÍ / ABNORMÁLNÍ / K DOPLNĚNÍ.
- U abnormálního prostoru zobrazí přehled rozhodujících kódů a orientační minimální krytí odvozené z AD/AE.
- Rozšířeno zadávání skupiny AM; stávající záznamy zůstávají kompatibilní.
- PDF typu Vnější vlivy používá terminologii protokolu, vlastní stav dokumentu a tiskne podklad, komisi, rozsah prostor a poznámky.
- U protokolu se netiskne seznam měřicích přístrojů ani posudek VTZ určený pro revizní zprávu.
- Podrobnosti jsou v souboru ZMENY_0.4.20.txt.

NOVINKY 0.4.19
- Nový modul Vnější vlivy podle ČSN 33 2000-5-51 ed. 3+Z1+Z2.
- Jedna místnost / prostor tvoří jeden řádek matice AA–CB.
- Importuje přímo sešity XLSX ve formátu Tabulka místností D1 a zachová podlaží, kódy i odkazy na opatření.
- Editor nabízí profily prostorů, editovatelné třídy vlivů, číselník opatření a kontrolu úplnosti.
- PDF protokolu tiskne matici po podlažích a přehled použitých opatření.
- Podrobnosti jsou v souboru ZMENY_0.4.19.txt.

NOVINKY 0.4.18
- Fotodokumentace závad v PDF používá rozložení 2 × 2.
- Na jedné stránce mohou být až čtyři menší fotografie se zachovaným poměrem stran.
- Podrobnosti jsou v souboru ZMENY_0.4.18.txt.

NOVINKY 0.4.17
- Pod každou závadou v PDF je řádek Odstranil, Datum a Podpis.
- Potvrzení je pouze ve zprávě a nemění evidovaná data.
- Podrobnosti jsou v souboru ZMENY_0.4.17.txt.

NOVINKY 0.4.16
- Hierarchie měření používá místo grafických čtverečků znaky > a >>.
- Stejné značení je použito v programu i v PDF.
- Podrobnosti jsou v souboru ZMENY_0.4.16.txt.

NOVINKY 0.4.15
- Pořadí kompletního měření: L–PE, L–N, L–PEN a L–L.
- RCBO zobrazuje vedle zkoušek RCD také celou tabulku měření jističové části.
- Podrobnosti jsou v souboru ZMENY_0.4.15.txt.

NOVINKY 0.4.14
- Jediné kompletní zadání elektrických měření včetně L1/L2/L3–PEN.
- Kombinovaný chránič RCBO obsahuje údaje RCD, jištění, impedance a izolačního odporu.
- Podrobnosti jsou v souboru ZMENY_0.4.14.txt.

NOVINKY 0.4.13
- Zapracován normový katalog z dodané sady dokumentů se samostatnými edicemi.
- Ve výchozím stavu se nabízejí jen ověřené platné a souběžně platné položky.
- Historické a neověřené normy lze zobrazit přepínačem; program před jejich použitím upozorní.
- Zdrojové PDF normy nejsou součástí aplikace, ukládají se pouze katalogová metadata.
- Podrobnosti jsou v souboru ZMENY_0.4.13.txt.

NOVINKY 0.4.12
- Pole „Rozsah revize“ je výrazně vyšší a má vlastní svislý posuvník.
- Formulář RCD má měření v samostatném přehledném bloku; AC+/AC− a další průběhy jsou vždy přímo pod hlavičkou s proudem [mA], časem [ms] a Uc [V].
- Opravena chyba pořadí prvků, kvůli které se řádky AC+/AC− zobrazovaly až pod poznámkou bez popisů.
- U RCD se z IΔn zobrazuje i informativní hodnota zkušebního proudu 5× IΔn.
- Tabulka měření má pevné šířky sloupců a levé zarovnání záhlaví, takže hlavičky sedí nad obsahem.

NOVINKY 0.4.11
- Celkový posudek na první straně už neobsahuje prefix „VYHOVUJE / NEVYHOVUJE“; zůstává jen odborná věta o schopnosti provozu.
- V PDF je u impedance použit zápis U0 bez problematického dolního indexu, takže se nezobrazují náhradní čtverečky.
- Hlídání termínů má pevné, kompaktní sloupce a přijímá i termín zadaný jen jako měsíc/rok (např. 9.2029).

NOVINKY 0.4.10
- PDF má stručné odborné posouzení impedance poruchové smyčky bez popisu funkce programu.
- Zobrazuje vztah Zsm ≤ 2/3 × U0 / Ia pro km = 1,5.
- Pod vzorcem je stručný význam veličin Zsm, U0 a Ia.
- Podle výsledků měření se doplní stručná věta, zda naměřené hodnoty stanovené podmínce vyhovují.

NOVINKY 0.4.9
- U0 pro automatické vyhodnocení Zs se bere z naměřeného U konkrétního bodu (fallback 230 V).
- L1-L2 / L2-L3 / L1-L3 jsou pouze izolační měření; Zs, mez Zs, Ik a U se u nich nepoužívají.
- Celkový posudek na první straně PDF je zelený pro Vyhovuje a červený pro Nevyhovuje.

NOVINKY 0.4.8
- Obvod má samostatně jmenovitý proud jističe In [A] a charakteristiku B / C / D.
- Pro nestandardní nebo nastavitelné ochrany lze zadat vypínací proud Ia ručně.
- Přidáno U0 a bezpečnostní koeficient km (výchozí 1,5).
- Mez impedance poruchové smyčky se u podřízených měřicích bodů dopočítá automaticky: Zsm,max = U0 / (km × Ia).
- Zadaná Zs se automaticky vyhodnotí jako Vyhovuje / Nevyhovuje.
- V PDF je pod tabulkou měření vysvětlující blok se vztahem Zs × Ia ≤ U0 a se započtením km pro měřenou impedanci.
- U jističů B/C/D program umí určit Ia z In a charakteristiky; u jiných ochran zůstává možnost ručního Ia / ručního limitu.

NOVINKY 0.4.7
- Hromadná editace existujících měřených údajů v elektrické revizi.
- V jedné tabulce lze upravit všechny měřicí body: U, Riso, zkušební napětí, Zs, mez Zs, Ik, dílčí výsledky a poznámky.
- Samostatná karta pro hromadnou editaci měření spojitosti.
- Při zadané Zs a mezi se výsledek impedance přepočítá automaticky; stejně tak spojitost.
- Celkový výsledek obvodu se po uložení hromadných změn znovu automaticky přepočítá.
- RCD a SPD zůstávají kvůli odlišné struktuře měření ve svých specializovaných formulářích.


Desktopová aplikace pro revizní zprávy elektrických instalací, LPS, strojních zařízení a vnějších vlivů.

SPUŠTĚNÍ
---------
1. Rozbal ZIP do vlastní složky.
2. Spusť SPUSTIT_PZ_REVIZE.bat.
3. První spuštění vytvoří lokální databázi v uživatelských datech PZ-REVIZE.

EXE
---
VYTVORIT_EXE.bat vytvoří dist\PZ-REVIZE.exe.







NOVINKY 0.4.6
- U jedné závady lze zadat libovolný počet normových odkazů.
- Každý odkaz obsahuje Norma / předpis, Článek / ustanovení a Citaci / normový požadavek.
- Normové odkazy lze přidávat, upravovat, mazat a řadit.
- Závadovník má samostatné tlačítko Normové odkazy; hlavní norma/článek zůstávají kvůli kompatibilitě.
- PDF tiskne všechny normy, články a citace u příslušné závady.
- Excel import/export nově zachovává více odkazů ve sloupci NORMOVÉ ODKAZY.
- Staré závady s jednou normou a článkem se při otevření automaticky převedou na první strukturovaný odkaz.

NOVINKY 0.4.5
- Závažnost závady se zadává přímo jako C1 / C2 / C3; samostatné pole „Kategorie závady“ bylo odstraněno.
- C1 = Nebezpečný stav, C2 = Potenciálně nebezpečný stav, C3 = doporučení.
- Vysvětlení C1/C2/C3 je trvale zobrazeno pod tabulkou závad v programu.
- Stejné vysvětlení se tiskne přímo pod tabulkou zjištěných závad v PDF.
- Staré záznamy z 0.4.4 se převedou bezpečně: pokud obsahují C1/C2/C3 v původním poli kategorie závady, hodnota se použije jako závažnost.
- Závadovník a Excel import/export používají pro C1/C2/C3 sloupec ZÁVAŽNOST.

NOVINKY 0.4.4
- Závady mají nově kategorii C1 / C2 / C3.
- C1 = existující nebezpečí, C2 = potenciálně nebezpečné, C3 = doporučuje se zlepšení.
- Kategorie se zobrazuje v seznamu závad i v PDF revizní zprávě a u fotodokumentace.
- C3 sama neblokuje kladný celkový výsledek; neodstraněná C1/C2 nebo neklasifikovaná závada vyvolá kontrolní upozornění.
- Původní pole Kategorie bylo přejmenováno na Oblast / skupina, aby se nepletlo s C1–C3.

NOVINKY 0.4.3
------------
- Sítě / soustavy a zdroje napájení jsou sjednoceny do jedné tabulky: jeden řádek = jeden zdroj + jeho napájecí soustava v dané části revize.
- Přidán specializovaný editor zdroje s živým náhledem normalizovaného zápisu podle ČSN EN IEC 61293 ed. 2 / IEC 61293.
- Standardní zápis používá např. 3/N/PE AC 230/400 V 50 Hz / TN-S; písmeno L se za počet krajních vodičů nepřidává.
- U TN-C-S lze správně rozlišit část před rozdělením PEN (např. 3/PEN ... / TN-C-S) a část za rozdělením (3/N/PE ... / TN-C-S).
- Editor hlídá zjevně neslučitelné kombinace, např. TN-S s vodičem PEN nebo TN-C s oddělenými N a PE.
- PDF tiskne jednu společnou tabulku Zdroj / Provozovatel / Napájecí soustava / Rozsah / Poznámka.
- Staré samostatné záznamy sítí se při otevření zachovají jako nepárované legacy řádky, takže nedojde k nesprávnému automatickému spojení se zdrojem.




NOVINKY 0.4.2
------------
- přepracovaná záložka Sítě / napájení: dvě samostatné tabulky pod sebou přes celou šířku
- sítě/soustavy a zdroje napájení již nejsou vizuálně ani v PDF párovány podle pořadí řádků
- přidané vysvětlující texty a přesnější názvy sloupců
- tabulky mají vlastní vodorovný i svislý posuvník
- PDF tiskne samostatný blok Sítě / soustavy a samostatný blok Zdroje napájení

NOVINKY 0.4.1
---------------
- Tlačítko + Měření nyní nejprve nabídne volbu „Jedna fáze / jeden měřicí bod“ nebo „Více fází – hromadné zadání“.
- Hromadné měření má jednu velkou tabulku pro L1/L2/L3 vůči PE, N a mezi fázemi. Jeden vyplněný řádek = jeden samostatný podřízený měřicí bod.
- Hromadná tabulka obsahuje U, Riso, Zs, mez Zs, Ik, výsledek a poznámku. Výsledek je přednastaven na Vyhovuje; při zadané Zs a mezi se vztah automaticky zkontroluje.
- Jednotlivý měřicí bod byl rozšířen o provozní / naměřené napětí U.
- Hodnoty v přehledu měření i v PDF se zobrazují včetně jednotek (V, MΩ, Ω, A), aniž by se jednotka duplikovala, pokud ji uživatel zadá ručně.
- Spojitost lze nově přidat přímo pod vybraný obvod (např. kotel) a zadat více bodů spojitosti s vlastním popisem. Samostatná spojitost bez vazby na obvod zůstává zachována.
- Automatický výsledek obvodu nově zohledňuje nejen podřízené měřicí body, ale i spojitosti přiřazené pod obvod.
- Při zavření otevřené revize s neuloženými změnami se program vždy zeptá, zda změny uložit, zahodit, nebo zavření zrušit.

NOVINKY 0.4.0
- Elektrické obvody už neslouží k dvojímu zadávání měření. Obsahují společné údaje o obvodu, jištění a kabelu.
- Jednotlivá měření se přidávají ručně po jednom tlačítkem + Měření; pevné tlačítko + L1/L2/L3 bylo odstraněno.
- Výsledek měřicího bodu se skládá z dílčího vyhodnocení impedance a izolace; při zadání Zs a mezní Zs se impedance vyhodnotí automaticky.
- Výsledek obvodu se automaticky skládá ze všech podřízených měření: jakmile jedno nevyhoví, nevyhoví obvod; při všech vyhovujících měřeních vyhoví obvod; neúplné hodnoty zůstanou jako Nehodnoceno.
- RCD dialog nově zobrazuje srozumitelný popis typu AC/A/F/B/B+ a vysvětlení zobrazovaných sloupců a společných zkoušek.
- PDF při použití podřízených měřicích bodů netiskne duplicitní hodnoty na řádku obvodu.

NOVINKY 0.3.9
---------------
- Vícefázový obvod má nyní pod jedním jističem podřízené měřicí body L1-PE, L2-PE, L3-PE nebo vlastní dvojice.
- Tlačítko + L1/L2/L3 rychle založí tři fáze pod vybraným obvodem.
- Každý měřicí bod má vlastní Riso, Zs, mez Zs, Ik a vyhodnocení; v PDF se tiskne pod společným jističem.
- Modul STROJ má rozšířenou identifikaci stroje a hierarchické měření / funkční zkoušky.
- STROJ umí předvyplnit základní strukturu zkoušek bez Ex/DOPV částí.
- Přibyly rychlé textové vzory z databáze pro zdvihací zařízení, obecné omezení rozsahu stroje a starší elektroinstalace.
- NAS/VPN zůstává kompatibilní se stávajícím NAS serverem 1.0.1.

NOVINKY 0.3.8
---------------
- Záložka „Poučení“ je samostatná a má výchozí text podle typu dokumentu: Elektrická instalace, LPS, Strojní zařízení a Vnější vlivy.
- U nové revize se příslušné poučení automaticky předvyplní; text lze v konkrétní revizi libovolně upravit nebo úplně vymazat.
- Tlačítko „Obnovit výchozí“ vrátí vestavěnou šablonu pro daný typ revize.
- Celý upravený text lze uložit jako vlastní šablonu pouze pro daný typ revizní zprávy.
- PDF používá podle typu dokumentu odpovídající nadpis poučení a zachovává vlastní číslování a odstavce z editoru.
- Elektrická a strojní šablona byly doplněny podle dodaných vzorů; LPS a vnější vlivy mají vlastní přednastavené provozní upozornění.
- Staré revize se nepřepisují: pokud už mají uložený vlastní text poučení, zůstane zachován.

NOVINKY 0.3.7
---------------
- Opraven WinError 32 při NAS synchronizaci na Windows.
- Trvalý indikátor stavu NAS v levém panelu.
- Samostatná LAN a VPN adresa, režim Automaticky / LAN / VPN.
- Automatický fallback LAN -> VPN.
- „Stáhnout kompletní DB“ ukládá celý NAS stav přímo do lokální pracovní DB tohoto PC a stáhne i přílohy/fotky/razítko/podpis.
- Lepší centrování oken a DPI chování na Windows.

NOVINKY 0.3.6
---------------
- NAS synchronizace se serverem PZ-REVIZE NAS SERVER 1.0.0.
- Centrální snapshot DB + příloh, API klíč, kontrola generace a ochrana proti tichému přepsání novějšího NAS stavu.
- Před stažením z NAS se automaticky vytvoří kompletní lokální ZIP záloha.

NOVINKY 0.3.5
---------------
- Hlídání termínu příští revize lze u každé revize / zakázky samostatně zapnout nebo vypnout.
- Nová stránka Termíny ukazuje revize po termínu i blížící se termíny a počet zbývajících dní.
- Vypnutí hlídání nemaže datum příští revize a neovlivňuje jeho tisk do zprávy.
- Seznam revizí má nový sloupec Hlídání a rychlé tlačítko pro zapnutí/vypnutí.

NOVINKY 0.3.3.1
---------------
- Opraveno sestavení Windows EXE: PyInstaller nyní přibaluje dynamicky načítané moduly ReportLab barcode (včetně code93), takže aplikace nespadne při startu po přidání čárového kódu.
- Samotná funkce čárového kódu Code 128 i vzhled revizní zprávy zůstávají beze změny.

NOVINKY 0.3.3
-------------
- První strana byla znovu rozložena podle dodaného vzoru: číslo zprávy je tučně nad malým základním logem a doplněné čárovým kódem Code 128.
- Z bloku RT na první straně byly odstraněny dlouhé texty rozsahu osvědčení/oprávnění a údaj platnosti; zůstávají identifikační údaje RT a evidenční čísla.
- Celkový posudek je posunut níže a spodní část první stránky lépe využívá celou A4.
- Razítko a podpis RT mají samostatné sloupce a samostatné linky.
- Potvrzení převzetí zprávy je samostatná tabulka s vlastním záhlavím.
- Opraveno skloňování názvu pravidelné a mimořádné revize.

NOVINKY 0.3.2
-------------
- Měření elektro je nově strukturální: samostatný RCD -> obvody za RCD, samostatná spojitost a možnost vložení prázdného řádku.
- Proudový chránič se již nezadává jako součást obvodu. RCD je vlastní měřená položka a může mít podřízené obvody.
- Typ citlivosti RCD (AC, A, F, B, B+) mění nabídku měřených průběhů. Typ A např. nabídne AC+/AC- a A+/A-; B/B+ navíc B+/B-.
- U RCD se eviduje druh přístroje (RCCB/RCBO), typ citlivosti, časové provedení, počet pólů, In, IΔn, 20-50 % IΔn, 5x IΔn a TEST.
- Spojitost / přechodový odpor je samostatné měření, ne sloupec obvodu.
- Přidáno přesouvání položek měření nahoru/dolů a zachování struktury při kopii staré revize; měřené hodnoty se při kopii vyčistí.
- PDF výstup má novou strukturovanou tabulku měření, kde je RCD zvýrazněn a obvody za ním jsou odsazené.
- Výstupní zpráva má jednotnou šířku všech tabulek 190 mm, výraznější typografii, jemnější technické rámečky a zakulacené bloky nadpisů / celkového posudku.
- První strana obsahuje identifikační údaje revizního technika: jméno/firma, adresa, IČO/DIČ, telefon/e-mail a evidenční čísla osvědčení/oprávnění; podrobné rozsahy zůstávají v profilu RT.
- Profil RT byl rozšířen o firmu, rozsah osvědčení, platnost osvědčení a rozsah oprávnění.
- Tabulka SPD / varistorů nyní ve výstupu uvádí také zkušební proud.
- Název programu zůstává PZ-REVIZE bez označení ALPHA.

VÝSTUP
------
Náhled, Tisk a Export PDF jsou dostupné přímo v otevřené revizi. Před výstupem lze zvolit, zda se má použít razítko a podpis RT.

DATA
----
Databázové změny jsou nedestruktivní. Před přechodem z předchozí verze je přesto vhodné použít Záloha databáze nebo Export DB.


NOVINKY 0.3.4
- větší společný prostor razítko + podpis
- číslování stran X / Y
- Poučení pro provozovatele s učením
- automatický seznam příloh

NAS A VPN
---------
V NAS synchronizaci lze nastavit dvě adresy:
- LAN: např. http://192.168.1.20:8767
- VPN: např. http://100.x.x.x:8767 pro Tailscale, nebo VPN adresu ze sítě WireGuard/OpenVPN.

Režim Automaticky zkusí LAN a při nedostupnosti přejde na VPN. API klíč je vyžadován v obou případech.
Port 8767 nedoporučujeme vystavovat přímo do internetu; pro vzdálený provoz používej VPN.
