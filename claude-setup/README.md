# Optional Claude Code setup (review, then install yourself)

Not installed automatically: these change what Claude Code may do without asking.

- `commands/*.md`: slash commands /pick /brief /eval /warm /judge-qa /ship-check (plain prompts).
- `settings.json`: pre-approves routine commands (make, pytest, ruff, git status/diff/add/commit, rg),
  blocks reading `.env` and force-push/hard-reset, and auto-formats Python after each edit (ruff hook).

Install after reading them:
    cp -R claude-setup/commands .claude/ && cp claude-setup/settings.json .claude/settings.json
