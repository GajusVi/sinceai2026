# Windows equivalent of the Makefile.  Usage: .\run.ps1 <task>
param([string]$task = "help", [Parameter(ValueFromRemainingArguments = $true)] $rest)
$env:PYTHONUTF8 = "1"          # read/write UTF-8 like the Macs (Finnish text in demo/cache)
$py = ".venv\Scripts\python.exe"
$prevDemo = $env:DEMO_MODE
function Live { Remove-Item Env:DEMO_MODE -ErrorAction SilentlyContinue }
try {
    switch ($task) {
        "ui"     { Live; $d = Join-Path $env:TEMP ("steward-" + [guid]::NewGuid()); New-Item -ItemType Directory $d | Out-Null; Copy-Item demo\steward_seed\* $d -Recurse; $env:STEWARD_DATA_DIR = $d; $env:STEWARD_CATALOG = "datapack"; & $py -m streamlit run frontend\steward_app.py; Remove-Item Env:STEWARD_CATALOG, Env:STEWARD_DATA_DIR -ErrorAction SilentlyContinue }
        "demo"   { $d = Join-Path $env:TEMP ("steward-" + [guid]::NewGuid()); New-Item -ItemType Directory $d | Out-Null; Copy-Item demo\steward_seed\* $d -Recurse; $env:STEWARD_DATA_DIR = $d; $env:STEWARD_CATALOG = "datapack"; $env:STEWARD_USE_LLM = "off"; & $py -m streamlit run frontend\steward_app.py; Remove-Item Env:STEWARD_USE_LLM, Env:STEWARD_CATALOG, Env:STEWARD_DATA_DIR -ErrorAction SilentlyContinue }
        "bayer"  { Live; $env:STEWARD_CATALOG = "datapack"; & $py -m streamlit run frontend\steward_app.py; Remove-Item Env:STEWARD_CATALOG -ErrorAction SilentlyContinue }
        "pack-large"  { & $py tools\make_large_pack.py }
        "bayer-large" { Live; $env:STEWARD_CATALOG = "datapack"; $env:STEWARD_DATAPACK_XLSX = "data\bayer_large\Bayer_Large_Synthetic_Pack.xlsx"; & $py -m streamlit run frontend\steward_app.py; Remove-Item Env:STEWARD_CATALOG, Env:STEWARD_DATAPACK_XLSX -ErrorAction SilentlyContinue }
        "set-webhook" { & $py tools\coord.py set-webhook }
        "board-discord" { & $py tools\coord.py discord }
        "board"  { & $py tools\coord.py board }
        "ask"    { Live; & $py -m steward @rest }
        "ui-old" { Live; & $py -m streamlit run frontend\app.py }
        "api"    { Live; & $py -m uvicorn backend.main:app --reload --port 8000 }
        "eval"   { Live; & $py eval\eval.py }
        "warm"   { Live; & $py -m backend.warm; if ($LASTEXITCODE -eq 0) { & $py eval\eval.py } }
        "ping"   { Live; & $py -m backend.llm }
        "models" { Live; & $py -m backend.llm models }
        "test"   { $env:DEMO_MODE = "1"; & $py -m pytest -q }
        default  { "tasks: ui demo bayer pack-large bayer-large board ask ui-old api eval warm ping models test" }
    }
} finally {
    $env:DEMO_MODE = $prevDemo   # never leave demo mode on in this window
}
