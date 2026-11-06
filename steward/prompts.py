from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache
def load_prompt(prompts_dir: Path, name: str) -> dict:
    with open(prompts_dir / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def render_prompt(prompts_dir: Path, name: str, **values: str) -> str:
    prompt = load_prompt(prompts_dir, name)
    return f"{prompt['system'].strip()}\n\n{prompt['template'].format(**values).strip()}"
