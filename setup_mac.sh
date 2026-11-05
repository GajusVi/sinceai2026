#!/usr/bin/env bash
# SinceAI 2026 workspace installer for macOS (Intel or Apple Silicon). Idempotent: re-run any time.
#   ./setup_mac.sh                 core: Homebrew tools, Python 3.11 venv, deps, embedding model, docs, git, tests
#   ./setup_mac.sh --all           core + VS Code (if no editor) + Claude Code CLI + Ollama offline LLM + wheelhouse
#   flags: --with-vscode --with-claude-code --with-ollama --wheelhouse
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
WITH_VSCODE=0 WITH_CC=0 WITH_OLLAMA=0 WHEELHOUSE=0
for a in "$@"; do
  case "$a" in
    --all) WITH_VSCODE=1 WITH_CC=1 WITH_OLLAMA=1 WHEELHOUSE=1 ;;
    --with-vscode) WITH_VSCODE=1 ;;
    --with-claude-code) WITH_CC=1 ;;
    --with-ollama) WITH_OLLAMA=1 ;;
    --wheelhouse) WHEELHOUSE=1 ;;
    *) echo "unknown flag $a"; exit 2 ;;
  esac
done

step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32mok\033[0m  %s\n' "$*"; }
warn() { printf '    \033[33m!!\033[0m  %s\n' "$*"; WARNINGS+=("$*"); }
WARNINGS=()

# ---------------------------------------------------------------- machine
step "Machine"
[[ "$(uname)" == "Darwin" ]] || { echo "macOS only"; exit 1; }
ARCH="$(uname -m)"; OSV="$(sw_vers -productVersion)"; OSMAJ="${OSV%%.*}"
RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
FREE_GB=$(df -g / | awk 'NR==2{print $4}')
ok "macOS $OSV · $ARCH · ${RAM_GB} GB RAM · ${FREE_GB} GB free"
(( FREE_GB < 15 )) && warn "Under 15 GB free disk. Empty Trash / Downloads before the event."
SKIP_FASTEMBED=0
if [[ "$ARCH" == "x86_64" && "$OSMAJ" -lt 13 ]]; then
  SKIP_FASTEMBED=1; warn "macOS < 13 on Intel: no onnxruntime wheels, retrieval will use TF-IDF (fine for small corpora)."
fi

# ---------------------------------------------------------------- Xcode CLT
step "Xcode Command Line Tools"
if xcode-select -p >/dev/null 2>&1; then ok "installed"; else
  xcode-select --install || true
  echo "Finish the Command Line Tools dialog, then run ./setup_mac.sh again."; exit 1
fi

# ---------------------------------------------------------------- Homebrew
step "Homebrew"
BREW=""
for b in "$HOME/.homebrew/bin/brew" /opt/homebrew/bin/brew /usr/local/bin/brew "$(command -v brew 2>/dev/null || true)"; do
  [[ -n "$b" && -x "$b" ]] && { BREW="$b"; break; }
done
if [[ -z "$BREW" ]]; then
  echo "    Installing Homebrew (asks for your Mac password once)"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [[ -x "$b" ]] && BREW="$b"; done
fi
eval "$("$BREW" shellenv)"
SHELLENV_LINE="eval \"\$($BREW shellenv)\""
grep -qsF "$SHELLENV_LINE" "$HOME/.zprofile" || echo "$SHELLENV_LINE" >> "$HOME/.zprofile"
ok "$BREW ($(brew --version | head -1))"
export HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 HOMEBREW_NO_ENV_HINTS=1

step "CLI tools"
for p in git gh uv node jq ripgrep; do
  if brew list --versions "$p" >/dev/null 2>&1; then ok "$p $(brew list --versions "$p" | awk '{print $2}')"
  else brew install "$p" && ok "$p installed" || warn "brew install $p failed"; fi
done

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh && export PATH="$HOME/.local/bin:$PATH" && ok "uv via astral installer"
fi

# ---------------------------------------------------------------- optional apps
if (( WITH_VSCODE )); then
  step "Editor"
  if [[ -d "/Applications/Visual Studio Code.app" || -d "/Applications/Cursor.app" || -d "$HOME/Applications/Cursor.app" ]]; then
    ok "VS Code or Cursor already installed"
  else brew install --cask visual-studio-code && ok "VS Code installed" || warn "VS Code install failed"; fi
  if command -v code >/dev/null 2>&1; then
    for ext in ms-python.python charliermarsh.ruff ms-toolsai.jupyter; do code --install-extension "$ext" --force >/dev/null 2>&1 || true; done
    ok "Python, Ruff, Jupyter extensions"
  fi
fi
if (( WITH_CC )); then
  step "Claude Code CLI"
  if command -v claude >/dev/null 2>&1; then ok "claude $(claude --version 2>/dev/null | head -1)"
  else npm install -g @anthropic-ai/claude-code >/dev/null 2>&1 && ok "installed (run: claude)" || warn "Claude Code install failed"; fi
fi
if (( WITH_OLLAMA )); then
  step "Ollama offline fallback (LLM_PROVIDER=ollama)"
  brew list --versions ollama >/dev/null 2>&1 || brew install ollama || warn "ollama install failed"
  if command -v ollama >/dev/null 2>&1; then
    brew services start ollama >/dev/null 2>&1 || true; sleep 3
    ollama pull llama3.2:3b && ok "llama3.2:3b pulled (~2 GB, slow on Intel CPU: fallback only)" || warn "ollama pull failed"
  fi
fi

# ---------------------------------------------------------------- Python env
step "Python 3.11 venv (uv)"
uv python install 3.11 >/dev/null 2>&1 || true
[[ -x .venv/bin/python ]] || uv venv --python 3.11 --seed .venv >/dev/null
ok "$(.venv/bin/python --version)"
REQ="requirements.in"
if (( SKIP_FASTEMBED )); then grep -v '^fastembed' requirements.in > .req.tmp; REQ=".req.tmp"; fi
uv pip install --python .venv/bin/python -r "$REQ" && ok "dependencies installed" || { warn "dependency install failed"; exit 1; }
rm -f .req.tmp
uv pip freeze --python .venv/bin/python > requirements.lock.txt
ok "pinned to requirements.lock.txt ($(wc -l < requirements.lock.txt | tr -d ' ') packages)"
if (( WHEELHOUSE )); then
  .venv/bin/python -m pip download -q -r requirements.lock.txt -d wheelhouse && ok "wheelhouse/ (offline: pip install --no-index -f wheelhouse -r requirements.lock.txt)"
fi

step "Embedding model (offline cache in ./models)"
BACKEND=$(.venv/bin/python -c "from backend.retrieval import Index; print(Index().build(['refund policy','password reset']).backend)" 2>/dev/null || echo failed)
[[ "$BACKEND" == "fastembed" ]] && ok "bge-small cached" || warn "embedding model not cached (backend=$BACKEND); TF-IDF fallback works"

# ---------------------------------------------------------------- docs offline
step "Pinned docs (docs/vendor)"
mkdir -p docs/vendor
fetch() { curl -fsSL --max-time 20 "$1" -o "docs/vendor/$2" && ok "$2" || warn "could not fetch $2"; }
fetch "https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk.md" anthropic-openai-sdk.md
fetch "https://docs.lumi-supercomputer.eu/laif/inference/aitta/" aitta-lumi.html
fetch "https://aitta.csc.fi/page/docs" aitta-docs.html

# ---------------------------------------------------------------- config + git
step "Config"
if [[ ! -f .env ]]; then cp .env.example .env; chmod 600 .env; ok ".env created: add ONE API key"; else ok ".env exists (left untouched)"; fi
chmod +x hackmode.sh setup_mac.sh

step "Git"
if [[ ! -d .git ]]; then
  git init -q -b main
  if git config user.name >/dev/null && git config user.email >/dev/null; then
    git add -A && git commit -qm "Pre-event scaffold (prior work, built before 6 Nov 2026)" && git tag pre-event
    ok "repo initialised, prior work tagged 'pre-event'"
  else warn "set git user.name/user.email, then: git add -A && git commit -m 'Pre-event scaffold' && git tag pre-event"; fi
else ok "repo exists"; fi
git config core.hooksPath .githooks && ok "team pre-commit hook on (OWNERS)"
git config user.name >/dev/null || warn "set your name: git config --global user.name \"Firstname\""
gh auth status >/dev/null 2>&1 && ok "gh logged in" || warn "run: gh auth login   (to push the team repo)"

# ---------------------------------------------------------------- verify
step "Smoke tests (no network, DEMO_MODE)"
if DEMO_MODE=1 .venv/bin/python -m pytest -q >/tmp/sinceai_pytest.log 2>&1; then ok "$(tail -1 /tmp/sinceai_pytest.log)"
else warn "tests failed: see /tmp/sinceai_pytest.log"; fi
step "LLM key check"
if .venv/bin/python -c "from backend.config import get_settings as g; import sys; sys.exit(0 if g().llm_ready() else 1)"; then
  .venv/bin/python -m backend.llm || warn "LLM ping failed: check key/model in .env"
else warn "no LLM key yet: put ANTHROPIC_API_KEY (or AITTA/OPENAI) in .env, then: make ping"; fi

printf '\n\033[1;32mDone.\033[0m  make ui · make demo · make eval · make hack\n'
if ((${#WARNINGS[@]})); then printf '\nTo do:\n'; printf '  - %s\n' "${WARNINGS[@]}"; fi
