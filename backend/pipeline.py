"""Score or flag each item. Live LLM first (DEMO_MODE: cached replay), then the cache if the live
call fails, then keyword rules. The demo never crashes: the worst case is source='rules'."""

import re
from concurrent.futures import ThreadPoolExecutor

from .audit import log_decision
from .config import get_settings
from .llm import LLMError, cached, complete_json
from .models import Decision, Item, ScoredItem

# FRIDAY: replace with the challenge's real categories (keep 3-8).
LABELS: dict[str, list[str]] = {
    "billing": ["invoice", "charge", "refund", "payment", "price"],
    "technical": ["error", "crash", "bug", "down", "fail", "broken", "timeout"],
    "account": ["login", "password", "access", "account", "permission"],
    "other": [],
}
URGENT = ["urgent", "asap", "immediately", "outage", "down", "production", "safety", "all users"]


def system_prompt() -> str:
    return (
        f"You triage incoming items for {get_settings().user_role}. "
        f"Allowed labels: {', '.join(LABELS)}. "
        "Pick exactly one label. Priority 5 means act now. Confidence is your honest probability. "
        "Evidence must be short verbatim quotes from the input. If unsure, say so in the reason."
    )


def _has(word: str, text: str) -> bool:
    """Whole-word match with a short suffix: 'fail' hits 'failed', 'down' does not hit 'download'."""
    return re.search(rf"\b{re.escape(word)}\w{{0,3}}\b", text) is not None


def _norm(s: str) -> str:
    return " ".join(s.lower().split()).strip(" \"'“”‘’")


def check_decision(d: Decision) -> None:
    """Runs inside the LLM repair loop: an unknown label is sent back to the model, not hidden."""
    label = d.label.strip().lower()
    if label not in LABELS:
        raise ValueError(f"label {d.label!r} is not one of {list(LABELS)}")
    d.label = label


def verify_evidence(d: Decision, text: str) -> None:
    """Keep only quotes that really occur in the input; say how many were dropped."""
    t = _norm(text)
    kept = [q for q in d.evidence if _norm(q) and _norm(q) in t]
    if dropped := len(d.evidence) - len(kept):
        d.evidence = kept
        d.reason = f"{d.reason} [{dropped} quote(s) not found in the input were removed]"


def rules_fallback(item: Item) -> Decision:
    t = item.text.lower()
    hits = {lab: sum(_has(k, t) for k in kws) for lab, kws in LABELS.items()}
    label = max(hits, key=hits.get) if any(hits.values()) else "other"
    urgent = [w for w in URGENT if _has(w, t)]
    return Decision(
        label=label,
        priority=4 if urgent else 2,
        confidence=0.3,
        reason="Keyword rules (LLM unavailable).",
        evidence=[w for w in LABELS[label] if _has(w, t)][:3] + urgent[:2],
        suggested_action=f"Route to {label} queue",
    )


def score(item: Item, log: bool = True) -> ScoredItem:
    system, user = system_prompt(), item.text
    try:
        decision = complete_json(system, user, Decision, check=check_decision)
        out = ScoredItem(item=item, decision=decision, source="cache" if get_settings().demo_mode else "llm")
    except LLMError:
        hit = cached(system, user, Decision)
        out = ScoredItem(item=item, decision=hit or rules_fallback(item), source="cache" if hit else "rules")
    if out.decision.label not in LABELS:  # only possible from a cache written under an older label set
        out.decision.reason = f"{out.decision.reason} [label {out.decision.label!r} not allowed, shown as 'other']"
        out.decision.label = "other"
    verify_evidence(out.decision, item.text)
    if log:
        log_decision(out)
    return out


def score_all(items: list[Item], workers: int | None = None, log: bool = True) -> list[ScoredItem]:
    with ThreadPoolExecutor(max_workers=workers or get_settings().llm_workers) as ex:
        results = list(ex.map(lambda i: score(i, log=log), items))
    return sorted(results, key=lambda r: (-r.decision.priority, -r.decision.confidence))
