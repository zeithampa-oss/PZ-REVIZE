# PZ-REVIZE

Zdrojové projekty a automatická sestavení programu PZ-REVIZE.

- `PZ_REVIZE_WINDOWS_0.4.35_SOURCE.zip` – PZ-REVIZE pro Windows
- `PZ_REVIZE_ANDROID_0.5.1_TABLET_SOURCE.zip` – PZ-REVIZE Mobile pro tablet
- `PZ_REVIZE_NAS_SERVER_1.0.2_SOURCE.zip` – společný NAS server

Po každém zápisu do větve `main` GitHub Actions spustí testy a vytvoří:

- `PZ_REVIZE_WINDOWS_0.4.35.exe`
- `PZ_REVIZE_MOBILE_0.5.1_TABLET_DEBUG.apk`

Hotové soubory jsou k dispozici u posledního běhu **Actions → Build PZ-REVIZE → Artifacts**.

Aktualizace aplikací nemaže uživatelskou databázi. Přesto je před první instalací nové testovací verze vhodné vytvořit lokální zálohu/JSON export.
