# SinceAI 2026 workspace setup for Windows 10/11. Re-run any time.
# From the repo folder in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
Set-Location $PSScriptRoot
function Step($m) { Write-Host "`n==> $m" -ForegroundColor Green }
function Have($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }

Step "Tools (winget)"
if (-not (Have winget)) { Write-Host "winget missing: install 'App Installer' from the Microsoft Store, then re-run."; exit 1 }
foreach ($p in @(@("git", "Git.Git"), @("gh", "GitHub.cli"), @("uv", "astral-sh.uv"))) {
    if (Have $p[0]) { Write-Host "    ok  $($p[0])" }
    else { winget install --id $p[1] -e --accept-source-agreements --accept-package-agreements }
}
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
if (-not (Have uv)) { Write-Host "uv was just installed: close and reopen PowerShell, then run this script again."; exit 1 }

Step "Python 3.11 venv"
uv python install 3.11
if (-not (Test-Path .venv\Scripts\python.exe)) { uv venv --python 3.11 --seed .venv }
uv pip install --python .venv\Scripts\python.exe -r requirements.in
if ($LASTEXITCODE -ne 0) { Write-Host "Dependency install failed: send the error to Gajus."; exit 1 }
uv pip install --python .venv\Scripts\python.exe -r requirements-extras.in

Step "Embedding model (cached in .\models)"
.venv\Scripts\python.exe -c "from backend.retrieval import Index; print(Index().build(['refund policy','password reset']).backend)"

Step "Config"
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "    .env created: paste your own GEMINI_API_KEY into it (notepad .env)" }
else { Write-Host "    .env exists (left untouched)" }

Step "Git team settings"
git config core.hooksPath .githooks
if (-not (git config user.name)) { Write-Host "    set your name:  git config --global user.name `"Firstname`"" -ForegroundColor Yellow } else { Write-Host "    ok  git user: $(git config user.name)" }

Step "Smoke tests (no network)"
$env:DEMO_MODE = "1"; .venv\Scripts\python.exe -m pytest -q; Remove-Item Env:DEMO_MODE

Write-Host "`nDone. Next: notepad .env  (add GEMINI_API_KEY), then  .\run.ps1 ping  and  .\run.ps1 ui" -ForegroundColor Green
