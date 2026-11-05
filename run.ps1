# Windows equivalent of the Makefile.  Usage: .\run.ps1 <task>
param([string]$task = "help")
$env:PYTHONUTF8 = "1"          # read/write UTF-8 like the Macs (Finnish text in demo/cache)
$py = ".venv\Scripts\python.exe"
$prevDemo = $env:DEMO_MODE
function Live { Remove-Item Env:DEMO_MODE -ErrorAction SilentlyContinue }
try {
    switch ($task) {
        "ui"     { Live; & $py -m streamlit run frontend\app.py }
        "demo"   { $env:DEMO_MODE = "1"; & $py -m streamlit run frontend\app.py }
        "api"    { Live; & $py -m uvicorn backend.main:app --reload --port 8000 }
        "eval"   { Live; & $py eval\eval.py }
        "warm"   { Live; & $py -m backend.warm; if ($LASTEXITCODE -eq 0) { & $py eval\eval.py } }
        "ping"   { Live; & $py -m backend.llm }
        "models" { Live; & $py -m backend.llm models }
        "test"   { $env:DEMO_MODE = "1"; & $py -m pytest -q }
        default  { "tasks: ui demo api eval warm ping models test" }
    }
} finally {
    $env:DEMO_MODE = $prevDemo   # never leave demo mode on in this window
}
