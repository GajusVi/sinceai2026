# templates/pbip: ground truth for the .pbip format

Never hand-write PBIR from memory (BUILD_PLAN M3). `steward/pbip.py` copies these files saved by Power BI Desktop.

Desktop installed on Martynas's machine: **2.159.1231.0 (26.10)** (read from PBIDesktop.exe; confirm after saving).

## To save (M3, needs a person at Desktop, about 30 min)
1. No preview toggles needed (TMDL and PBIR are regular features in this Desktop version). Use File > Save as > "Power BI project files (*.pbip)".
2. `empty/`: new blank report, Save as ... type "Power BI project files (*.pbip)" to `templates/pbip/empty/empty.pbip`.
3. `one_of_each/`: Get data > Text/CSV > `templates/pbip/source/sample_sales.csv` (60 rows: Nubeqa, Kerendia x Germany, US, France).
   Change `month` to Date. On one page add exactly: one **Card** (Sum of net_sales_m_eur_syn), one **Line chart**
   (month x net_sales, forecast_m_eur_syn as second value), one **Clustered bar chart** (market_name x net_sales),
   one **Table** (month, product_name, market_name, net_sales). Save as `templates/pbip/one_of_each/one_of_each.pbip`.
4. Commit both folders (not `.pbi/cache.abf`, not `localSettings.json`), then tell Claude: M4 starts from these files.

## What Desktop 2.159 actually saved (checked 7 Nov 10:30; M4 builds on this)
- `*.pbip` -> `<n>.Report/` (`definition.pbir` version 4.0, byPath `../<n>.SemanticModel`; PBIR under `definition/`: `report.json`, `version.json` 2.0.0,
  `pages/pages.json`, `pages/<id>/page.json`, `pages/<id>/visuals/<id>/visual.json`) and `<n>.SemanticModel/` (`definition.pbism`, TMDL under `definition/`:
  `model.tmdl`, `database.tmdl`, `relationships.tmdl`, `cultures/`, `tables/<table>.tmdl`).
- `one_of_each` page "Page 1" is 1920x1080 with four visuals, all on table `sample_sales`: `cardVisual` (Sum net_sales), `lineChart` (month; Sum net_sales + Sum forecast),
  `clusteredBarChart` (market_name; Sum net_sales), `tableEx` (month, product_name, market_name, Sum net_sales). Aggregation `Function: 0` = Sum.
- The card is the NEW card (`cardVisual`), not the legacy `card`. Roles: card `Data`; line `Category` + `Y`; bar `Category` + `Y`; table `Values`.
- Desktop adds a hidden `LocalDateTable_<guid>` + `DateTableTemplate_<guid>` and `relationships.tmdl` for each date column (auto date/time). `pbip.py` should not copy these guids:
  turn auto date/time off in generated models, or write them fresh.
- The CSV partition stores an ABSOLUTE path (`C:\Users\...\sample_sales.csv`). Generated projects must use their own relative/import data, never this path.
- `.pbi/cache.abf` and `localSettings.json` are ignored by git.
