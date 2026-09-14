PZ-REVIZE Mobile 0.5.1 TABLET

Zdrojový projekt Android aplikace pro Samsung Tab S9+ a jiné tablety od 12 palců.
Aplikační ID cz.pzrevize.mobile zůstalo stejné jako ve verzi 0.4.2. Lokální databáze
se při aktualizaci migruje z verze 5 na 6 bez mazání dosavadních revizí.

NOVÉ V 0.5.1
- U zákazníka jsou dvě samostatné volby: „NOVÁ REVIZE“ a „NOVÝ VV“.
- Nová revize nabízí elektro, stroj a LPS; nový VV rovnou zakládá protokol vnějších vlivů.
- Tabletová tabulka měření má pevné sloupce Prvek / Typ / Hodnoty / Stav a detail uvádí názvy veličin.
- Synchronizace neoznačí pozdější změnu za odeslanou, pokud vznikla během přenosu.
- Konflikt neblokuje práci: lokální data zůstávají čekající a lze přejít do nastavení nebo pokračovat offline.

PRACOVNÍ ROZHRANÍ
- Na velkém tabletu na šířku: stálá levá navigace a samostatně posuvné panely.
- Prohlídka: kontrolní body vlevo, výsledek/poznámka vpravo; vlastní body a katalog;
  přímé vytvoření závady z nevyhovujícího bodu.
- Měření: přehled obvodů/zařízení a navázaných položek vlevo; detail a rychlé
  přidání měřicího bodu, spojitosti či RCD/RCBO vpravo.
- Vnější vlivy: místnosti/prostory, popis, kódy a opatření; editace a mazání.
- Stávající zákazníci, revize, fotografie, závady, import/export JSON a NAS
  synchronizace podporovaných záznamů zůstávají dostupné.
- Na menším displeji a na výšku zůstává původní kompaktní uspořádání prohlídky
  a měření; nová část vnějších vlivů funguje i tam.
- Fyzická klávesnice zapisuje do běžných systémových textových polí.

DŮLEŽITÁ OMEZENÍ
- Vnější vlivy jsou zatím pouze místní pracovní záznam. Úplný export/import JSON
  je zahrnuje, ale současné NAS API a výstupní protokol desktopové verze je
  zatím nepřenášejí. Před výměnou tabletu proveď úplnou JSON zálohu.
- Nejde o automatické odborné posouzení vlivů; kódy i opatření potvrzuje technik.
- Anotování fotografií perem, vyhotovení PDF v Androidu a další rozšíření
  tabulky měření nejsou v této verzi implementovány.

SESTAVENÍ
Na Windows s Android Studiem (Android SDK Platform 35 a Build-Tools) spusť
BUILD_APK.bat. Potřebuješ přístup ke Gradle distribuci a pluginům při prvním
sestavení. Výsledek: PZ_REVIZE_MOBILE_0.5.1_TABLET_DEBUG.apk.
Instalace přes stávající verzi vyžaduje stejný podpisovací klíč. Výchozí debug
klíč na jiném PC se může lišit; v tom případě před odinstalací staré aplikace
nejdřív udělej export její úplné JSON zálohy.

V tomto předaném balíku není hotový soubor APK: zdejší prostředí nemá Android
SDK ani Gradle, takže nebylo možné ověřit sestavení a instalaci na tabletu.
