# templates/pbip: ground truth for the .pbip format

Never hand-write PBIR from memory (BUILD_PLAN M3). `steward/pbip.py` copies these files saved by Power BI Desktop.

Desktop installed on Martynas's machine: **2.159.1231.0 (26.10)** (read from PBIDesktop.exe; confirm after saving).

## To save (M3, needs a person at Desktop, about 30 min)
1. File > Options and settings > Options > Preview features: enable **Power BI Project (.pbip) save option**,
   **Store semantic model using TMDL format**, **Store reports using enhanced metadata format (PBIR)**. Restart Desktop.
2. `empty/`: new blank report, Save as ... type "Power BI project files (*.pbip)" to `templates/pbip/empty/empty.pbip`.
3. `one_of_each/`: Get data > Text/CSV > `templates/pbip/source/sample_sales.csv` (60 rows: Nubeqa, Kerendia x Germany, US, France).
   Change `month` to Date. On one page add exactly: one **Card** (Sum of net_sales_m_eur_syn), one **Line chart**
   (month x net_sales, forecast_m_eur_syn as second value), one **Clustered bar chart** (market_name x net_sales),
   one **Table** (month, product_name, market_name, net_sales). Save as `templates/pbip/one_of_each/one_of_each.pbip`.
4. Commit both folders (not `.pbi/cache.abf`, not `localSettings.json`), then tell Claude: M4 starts from these files.
