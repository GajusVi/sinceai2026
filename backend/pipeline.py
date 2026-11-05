"""Score or flag each item. LLM first, cached replay in DEMO_MODE, keyword rules if both fail.
The demo never crashes: the worst case is a rules-based answer marked source='rules'."""

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


def rules_fallback(item: Item) -> Decision:
    t = item.text.lower()
    hits = {lab: sum(k in t for k in kws) for lab, kws in LABELS.items()}
    label = max(hits, key=hits.get) if any(hits.values()) else "other"
    urgent = [w for w in URGENT if w in t]
    return Decision(
        label=label,
        priority=4 if urgent else 2,
        confidence=0.3,
        reason="Keyword rules (LLM unavailable).",
        evidence=[w for w in LABELS[label] if w in t][:3] + urgent[:2],
        suggested_action=f"Route to {label} queue",
    )


def score(item: Item, log: bool = True) -> ScoredItem:
    system, user = system_prompt(), item.text
    hit = cached(system, user, Decision)
    if hit is not None:
        out = ScoredItem(item=item, decision=hit, source="cache")
    else:
        try:
            out = ScoredItem(item=item, decision=complete_json(system, user, Decision), source="llm")
        except LLMError:
            out = ScoredItem(item=item, decision=rules_fallback(item), source="rules")
    if out.decision.label not in LABELS:
        out.decision.label = "other"
    if log:
        log_decision(out)
    return out


def score_all(items: list[Item], workers: int | None = None, log: bool = True) -> list[ScoredItem]:
    with ThreadPoolExecutor(max_workers=workers or get_settings().llm_workers) as ex:
        results = list(ex.map(lambda i: score(i, log=log), items))
    return sorted(results, key=lambda r: (-r.decision.priority, -r.decision.confidence))
