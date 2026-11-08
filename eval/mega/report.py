"""Mega backtest report: per-pack metrics, usage insights, issues, and one demo-readiness verdict (PASS / WARN / FAIL).

Gates (rules mode; an LLM run adds latency, so latency gates are reported, not enforced, with --llm):
  G1 crashes = 0                                   FAIL otherwise
  G2 scope: plant leaks + unrefused other-plant = 0 FAIL otherwise
  G3 expectation met >= 85% (WARN >= 70%)           per pack, people's sessions only
  G4 happy (score >= 4) >= 75% (WARN >= 60%)
  G5 manager interview: median questions <= 3, p95 <= 5
  G6 latency p95: worker <= 2 s, manager <= 5 s     (WARN only)
  G7 display problems on <= 2% of rendered pages (WARN <= 5%)
  G8 escalations decided by the builder >= 90% and the requester saw the outcome >= 80%
  G9 PBIP exports written, determinism differences = 0
  G10 large vs real: met rate drops <= 10 points, p95 latency grows <= 3x (WARN)
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict


def _pct(n: int, d: int) -> float:
    return round(100 * n / d, 1) if d else 0.0


def _p(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    return round(v[min(len(v) - 1, int(q * len(v)))], 2)


def summarize(pack: str, rows: list[dict], issues: list[dict], loops: list[dict], meta: dict) -> dict:
    people = [r for r in rows if r["role"] != "builder"]
    scored = [r for r in people if r.get("score") is not None]
    workers = [r for r in people if r["role"] == "worker"]
    managers = [r for r in people if r["role"] == "management"]
    interviews = [r for r in managers if r.get("path") == "interview"]
    rendered = [r for r in rows if isinstance(r.get("render"), dict) and "problems" in r["render"]]
    by = defaultdict(list)
    for r in scored:
        by[(r["role"], r["subrole"])].append(r)
    subroles = {
        f"{role}/{sub}": {
            "sessions": len(rs), "met_pct": _pct(sum(bool(r["met"]) for r in rs), len(rs)),
            "happy_pct": _pct(sum(bool(r["happy"]) for r in rs), len(rs)),
            "avg_score": round(statistics.mean(r["score"] for r in rs), 2),
            "avg_questions": round(statistics.mean(r["questions"] for r in rs), 2),
            "channels": dict(Counter(r["channel"] for r in rs)),
            "escalated": sum(1 for r in rs if r.get("escalated")),
        } for (role, sub), rs in sorted(by.items())
    }
    scen = defaultdict(list)
    for r in scored:
        scen[r.get("scenario", "?")].append(r)
    scenarios = sorted(
        ({"scenario": k, "n": len(v), "met_pct": _pct(sum(bool(r["met"]) for r in v), len(v)),
          "avg_score": round(statistics.mean(r["score"] for r in v), 2),
          "verdicts": dict(Counter(str(r.get("verdict")) for r in v)),
          "outcomes": dict(Counter(str(r.get("outcome")) for r in v)),
          "example": v[0].get("text")} for k, v in scen.items()),
        key=lambda s: (s["met_pct"], -s["n"]),
    )
    friction = Counter(f.split(" (")[0] if f.startswith("slow") else f for r in people for f in r["friction"])
    esc = [lp for lp in loops]
    decided = [lp for lp in esc if lp.get("decided")]
    seen = [lp for lp in esc if lp.get("seen")]
    turnaround = [lp["decided"] - lp["asked"] for lp in decided]
    weekly = defaultdict(lambda: [0, 0])
    for r in managers:
        w = (r["day"] - 1) // 5 + 1
        weekly[w][0] += 1
        weekly[w][1] += 1 if r.get("typeahead_hit") or r.get("path") == "reused" else 0
    crit = Counter(i["kind"] for i in issues)
    return {
        "pack": pack, "meta": meta,
        "volume": {"interactions": len(rows), "people_sessions": len(people), "worker": len(workers),
                   "management": len(managers), "builder": len(rows) - len(people),
                   "active_people": len({r["user"] for r in people})},
        "met_pct": _pct(sum(bool(r["met"]) for r in scored), len(scored)),
        "partial_pct": _pct(sum(bool(r.get("partial")) for r in scored), len(scored)),
        "happy_pct": _pct(sum(bool(r["happy"]) for r in scored), len(scored)),
        "avg_score": round(statistics.mean(r["score"] for r in scored), 2) if scored else 0,
        "by_role": {role: {"met_pct": _pct(sum(bool(r["met"]) for r in rs), len(rs)),
                           "happy_pct": _pct(sum(bool(r["happy"]) for r in rs), len(rs)), "n": len(rs)}
                    for role, rs in (("worker", [r for r in scored if r["role"] == "worker"]),
                                     ("management", [r for r in scored if r["role"] == "management"]))},
        "expect_mix": dict(Counter(r.get("expect") for r in scored)),
        "met_by_expect": {e: _pct(sum(bool(r["met"]) for r in scored if r.get("expect") == e),
                                  sum(1 for r in scored if r.get("expect") == e))
                          for e in {r.get("expect") for r in scored}},
        "wording": {w: _pct(sum(bool(r["met"]) for r in scored if r.get("wording") == w),
                            sum(1 for r in scored if r.get("wording") == w))
                    for w in ("precise", "vague", "typo") if any(r.get("wording") == w for r in scored)},
        "channels": dict(Counter(r["channel"] for r in people)),
        "search": {"typeahead_sessions": sum(1 for r in managers if r.get("search_used")),
                   "typeahead_hit": sum(1 for r in managers if r.get("typeahead_hit")),
                   "reused_intent": sum(1 for r in managers if r.get("path") == "reused"),
                   "reuse_share_by_week": {w: _pct(v[1], v[0]) for w, v in sorted(weekly.items())}},
        "questions": {"interviews": len(interviews),
                      "median": statistics.median([r["questions"] for r in interviews]) if interviews else 0,
                      "p95": _p([r["questions"] for r in interviews], 0.95),
                      "dist": dict(sorted(Counter(r["questions"] for r in interviews).items())),
                      "skipped_pct": _pct(sum(bool(r.get("skipped")) for r in interviews), len(interviews)),
                      "retried": sum(bool(r.get("retried")) for r in managers)},
        "latency": {"worker_p50": _p([r["latency_s"] for r in workers], 0.5),
                    "worker_p95": _p([r["latency_s"] for r in workers], 0.95),
                    "manager_p50": _p([r["latency_s"] for r in managers], 0.5),
                    "manager_p95": _p([r["latency_s"] for r in managers], 0.95),
                    "builder_p95": _p([r["latency_s"] for r in rows if r["role"] == "builder"], 0.95)},
        "verdicts": dict(Counter(str(r.get("verdict")) for r in rows if r.get("verdict"))),
        "lint": dict(Counter((r.get("lint") or {}).get("worst") for r in rows if r.get("lint"))),
        "lint_rules": dict(Counter(x for r in rows if r.get("lint") for x in r["lint"]["blocks"] + r["lint"]["warns"])),
        "display": {"rendered": len(rendered),
                    "with_problems": sum(1 for r in rendered if r["render"]["problems"]),
                    "problems": dict(Counter(p.split(":")[0] for r in rendered for p in r["render"]["problems"])),
                    "archetypes": dict(Counter(r["render"]["archetype"] for r in rendered)),
                    "avg_dq_notes_worker": round(statistics.mean([r["render"]["dq_notes"] for r in rendered
                                                                  if r["role"] == "worker"] or [0]), 2),
                    "avg_visuals": round(statistics.mean([r["render"]["figures"] + r["render"]["tables"] +
                                                          r["render"]["cards"] + r["render"]["tiles"]
                                                          for r in rendered] or [0]), 1)},
        "escalations": {"total": len(esc), "by_kind": dict(Counter(lp["kind"] for lp in esc)),
                        "decided_pct": _pct(len(decided), len(esc)), "seen_pct": _pct(len(seen), len(esc)),
                        "turnaround_days_median": statistics.median(turnaround) if turnaround else None,
                        "joined_existing": sum(1 for r in people if r.get("escalated") in ("report_joined",)) + sum(
                            1 for r in people if r.get("outcome") == "joined_request"),
                        "dead_ends": sum(1 for r in people if r.get("escalated") == "dead_end"),
                        "builder_outcomes": dict(Counter(r.get("outcome") for r in rows if r["role"] == "builder"
                                                         and r["channel"] in ("approvals", "floor")))},
        "friction": dict(friction.most_common(15)),
        "subroles": subroles,
        "worst_scenarios": scenarios[:12],
        "issues": {"total": len(issues), "by_kind": dict(crit),
                   "critical": sum(1 for i in issues if i["severity"] == "critical")},
    }


def gates(summaries: list[dict], llm: bool) -> list[dict]:
    out = []

    def gate(gid, name, status, detail):
        out.append({"id": gid, "name": name, "status": status, "detail": detail})

    for s in summaries:
        pk, iss = s["pack"], s["issues"]["by_kind"]
        crashes = iss.get("crash", 0) + iss.get("render_crash", 0)
        gate("G1", f"{pk}: no crashes", "PASS" if crashes == 0 else "FAIL", f"{crashes} crashes")
        leaks = iss.get("plant_leak", 0) + iss.get("scope_leak", 0)
        gate("G2", f"{pk}: plant scope holds", "PASS" if leaks == 0 else "FAIL", f"{leaks} leaks")
        m = s["met_pct"]
        gate("G3", f"{pk}: expectation met", "PASS" if m >= 85 else "WARN" if m >= 70 else "FAIL", f"{m}%")
        h = s["happy_pct"]
        gate("G4", f"{pk}: people happy", "PASS" if h >= 75 else "WARN" if h >= 60 else "FAIL",
             f"{h}% (avg {s['avg_score']}/5)")
        q = s["questions"]
        ok = q["median"] <= 3 and q["p95"] <= 5
        gate("G5", f"{pk}: interview length", "PASS" if ok else "WARN",
             f"median {q['median']}, p95 {q['p95']}, skipped {q['skipped_pct']}%")
        lat = s["latency"]
        ok = lat["worker_p95"] <= 2 and lat["manager_p95"] <= 5
        gate("G6", f"{pk}: latency", "PASS" if ok else ("INFO" if llm else "WARN"),
             f"worker p95 {lat['worker_p95']}s, manager p95 {lat['manager_p95']}s")
        d = s["display"]
        share = _pct(d["with_problems"], d["rendered"])
        gate("G7", f"{pk}: dashboards display logically", "PASS" if share <= 2 else "WARN" if share <= 5 else "FAIL",
             f"{d['with_problems']}/{d['rendered']} pages with a problem ({share}%)")
        e = s["escalations"]
        ok = e["total"] == 0 or (e["decided_pct"] >= 90 and e["seen_pct"] >= 80)
        gate("G8", f"{pk}: escalations close the loop", "PASS" if ok else "WARN",
             f"{e['total']} escalations, {e['decided_pct']}% decided, {e['seen_pct']}% seen by requester, "
             f"{e['dead_ends']} dead ends")
        pb = s["meta"].get("pbip", [])
        det = s["meta"].get("determinism", {})
        ok = all(x.get("ok") for x in pb) and det.get("differences", 0) == 0
        gate("G9", f"{pk}: PBIP export + determinism", "PASS" if ok else "FAIL",
             f"{sum(bool(x.get('ok')) for x in pb)}/{len(pb)} exports ok; {det.get('differences', '?')} of "
             f"{det.get('checked', '?')} replays differ")
    by = {s["pack"]: s for s in summaries}
    if "real" in by and "large" in by:
        r, lg = by["real"], by["large"]
        drop = round(r["met_pct"] - lg["met_pct"], 1)
        grow = round((lg["latency"]["manager_p95"] or 0.01) / (r["latency"]["manager_p95"] or 0.01), 1)
        ok = drop <= 10 and grow <= 3
        gate("G10", "scale: 5,000-asset pack vs real", "PASS" if ok else "WARN",
             f"met {r['met_pct']}% -> {lg['met_pct']}% ({-drop:+}), manager p95 x{grow}")
    return out


def verdict(gs: list[dict]) -> str:
    if any(g["status"] == "FAIL" for g in gs):
        return "NOT READY"
    if any(g["status"] == "WARN" for g in gs):
        return "READY WITH CAVEATS"
    return "READY"


def markdown(summaries: list[dict], gs: list[dict], issues: list[dict], llm: bool) -> str:
    v = verdict(gs)
    L = [f"# Mega backtest: demo readiness = **{v}**", "",
         f"Mode: {'live LLM' if llm else 'rules (LLM off, deterministic)'}. "
         "Synthetic people drive the app's own code paths (no UI clicks); expectations are the person's view, "
         "written before the run. Reproduce: `.venv/Scripts/python.exe eval/mega_backtest.py` (see --help).", "",
         "## Gates", "", "| Gate | Check | Status | Detail |", "|---|---|---|---|"]
    L += [f"| {g['id']} | {g['name']} | {g['status']} | {g['detail']} |" for g in gs]
    for s in summaries:
        vol, q, lat, d, e = s["volume"], s["questions"], s["latency"], s["display"], s["escalations"]
        L += ["", f"## Pack: {s['pack']} ({s['meta'].get('assets')} assets, {len(s['meta'].get('plants', []))} plants,"
              f" {s['meta'].get('days')} working days)", "",
              f"- {vol['interactions']} interactions ({vol['worker']} worker, {vol['management']} management, "
              f"{vol['builder']} builder) by {vol['active_people']} people.",
              f"- Expectation met **{s['met_pct']}%** (partial {s['partial_pct']}%), happy **{s['happy_pct']}%**, "
              f"avg score {s['avg_score']}/5. Worker {s['by_role']['worker']['met_pct']}% met / "
              f"{s['by_role']['worker']['happy_pct']}% happy; management {s['by_role']['management']['met_pct']}% / "
              f"{s['by_role']['management']['happy_pct']}%.",
              f"- Met by expectation: {_kv(s['met_by_expect'])}. By wording: {_kv(s['wording'])}.",
              f"- Channels: {_kv(s['channels'])}.",
              f"- Typeahead (search): {s['search']['typeahead_sessions']} sessions, {s['search']['typeahead_hit']} "
              f"picked a colleague's request, {s['search']['reused_intent']} skipped the interview. Reuse share by "
              f"week: {_kv(s['search']['reuse_share_by_week'])}.",
              f"- Interview: {q['interviews']} runs, median {q['median']} questions, p95 {q['p95']}, distribution "
              f"{_kv(q['dist'])}, skip pressed {q['skipped_pct']}%, rephrased after CLARIFY {q['retried']}.",
              f"- Latency p50/p95: worker {lat['worker_p50']}/{lat['worker_p95']} s, manager {lat['manager_p50']}/"
              f"{lat['manager_p95']} s, builder p95 {lat['builder_p95']} s. Engine load "
              f"{s['meta'].get('timings', {}).get('engine_load_s')} s.",
              f"- Verdicts: {_kv(s['verdicts'])}. Lint worst: {_kv(s['lint'])}. Rules hit: {_kv(s['lint_rules'])}.",
              f"- Display: {d['rendered']} pages, {d['with_problems']} with a problem {_kv(d['problems'])}; layouts "
              f"{_kv(d['archetypes'])}; avg {d['avg_visuals']} visuals a page; workers see "
              f"{d['avg_dq_notes_worker']} data-quality footnotes a page.",
              f"- Escalations: {e['total']} ({_kv(e['by_kind'])}), {e['decided_pct']}% decided, {e['seen_pct']}% "
              f"seen by the requester, median turnaround {e['turnaround_days_median']} working days, "
              f"{e['joined_existing']} joined an open request, {e['dead_ends']} dead ends. Builder: "
              f"{_kv(e['builder_outcomes'])}.",
              "", "**Top friction (what people ran into)**", ""]
        L += [f"- {k}: {n}" for k, n in s["friction"].items()] or ["- none"]
        L += ["", "**Sub-roles**", "", "| Sub-role | Sessions | Met | Happy | Score | Questions | Escalated |",
              "|---|---|---|---|---|---|---|"]
        L += [f"| {k} | {x['sessions']} | {x['met_pct']}% | {x['happy_pct']}% | {x['avg_score']} | "
              f"{x['avg_questions']} | {x['escalated']} |" for k, x in s["subroles"].items()]
        L += ["", "**Weakest situations (lowest met rate)**", "", "| Scenario | n | Met | Score | Outcomes | Example |",
              "|---|---|---|---|---|---|"]
        L += [f"| {x['scenario']} | {x['n']} | {x['met_pct']}% | {x['avg_score']} | {_kv(x['outcomes'])} | "
              f"{(x['example'] or '')[:60]} |" for x in s["worst_scenarios"]]
    L += ["", "## Issues (deduplicated, most frequent first)", ""]
    grouped = Counter((i["severity"], i["kind"], i["detail"][:140]) for i in issues)
    order = {"critical": 0, "high": 1, "medium": 2}
    for (sev, kind, detail), n in sorted(grouped.items(), key=lambda kv: (order.get(kv[0][0], 3), -kv[1]))[:40]:
        L.append(f"- **{sev}** `{kind}` x{n}: {detail}")
    if not issues:
        L.append("- none")
    L += ["", "## How to read this", "",
          "- `met` = the person got what they came for (the numbers they wanted, with values on the page; or the "
          "honest answer the situation calls for: refusal for another plant, 'not measured yet', CLARIFY for an "
          "unknown product).",
          "- `happy` = score >= 4 of 5 (points off for missed expectation, more questions than the person's patience, "
          "slow answers, display problems, dead ends). A correct 'no' scores at most 4.",
          "- The simulated people are scripted, not an LLM: they test the app's logic and flow, not its wording. "
          "Run with `--llm` for a sample with the live model (slower, costs credits)."]
    return "\n".join(L) + "\n"


def _kv(d: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in d.items()) if d else "-"
