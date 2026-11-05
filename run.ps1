# Windows equivalent of the Makefile.  Usage: .\run.ps1 <task>
param([string]$task = "help")
$py = ".venv\Scripts\python.exe"
switch ($task) {
    "ui"     { & $py -m streamlit run frontend\app.py }
    "demo"   { $env:DEMO_MODE = "1"; & $py -m streamlit run frontend\app.py }
    "api"    { & $py -m uvicorn backend.main:app --reload --port 8000 }
    "eval"   { & $py eval\eval.py }
    "ping"   { & $py -m backend.llm }
    "models" { & $py -m backend.llm models }
    "test"   { $env:DEMO_MODE = "1"; & $py -m pytest -q }
    default  { "tasks: ui demo api eval ping models test" }
}
