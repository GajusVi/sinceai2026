"""Mega backtest simulation: run 111 personas through N working days on ONE data pack, through the app's own code paths.

Drives the same functions the Streamlit app calls (frontend/steward_app.py, frontend/worker_view.py), without the UI:
  worker      prompt buttons (worker.reuse_only), chat (worker.suggest -> open_item), Other department
              (inbox.add_floor access request), "Ask the BI team for it" (report request)
  management  typeahead (suggest.Suggestions.for_user / intent_for) or the interview (Interviewer.start/answer,
              finish_with_defaults on impatience) -> ask_intent -> build -> lint -> render -> send to the BI team
  builder     every day: approvals queue (inbox.take -> governance.approve / reject), floor requests (grant, start,
              decline), expert-mode asks of the pack's Business_Requests; weekly estate health + PBIP export
Every interaction becomes one row in interactions.jsonl (the synthetic usage data field). Nothing outside a temp data
dir is written: the journal, inbox, suggestions memory and catalog changes all live in the run's own folder.
"""

from __future__ import annotations

import hashlib
import math
import random
import time
import traceback
from datetime import date, timedelta
from pathlib import Path

ENGINE_DATE = date(2026, 11, 6)  # the pack's as_of; simulated days are labels ending here
BUILDS = {"REUSE", "EXTEND", "CREATE", "CONSOLIDATE"}


def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


class Sim:
    def __init__(self, pack: str, days: int, seed: int, out: Path, llm: bool = False, reload_every: int = 5,
                 pbip: int = 3, workers: int = 100, managers: int = 10):
        self.pack, self.days, self.out, self.llm = pack, days, out, llm
        self.rng = random.Random(seed)
        self.attendance = random.Random(seed + 1)
        self.reload_every, self.pbip_left = reload_every, pbip
        self.n_workers, self.n_managers = workers, managers
        self.rows: list[dict] = []
        self.issues: list[dict] = []
        self.pending: dict[str, dict] = {}  # inbox id -> {day, kind, who}
        self.loops: list[dict] = []  # closed escalations: asked day, decided day, notice seen day
        self.render_memo: dict[str, tuple] = {}
        self.specs_for_pbip: list = []
        self.timings: dict[str, float] = {}

    # -- setup ------------------------------------------------------------------------------------------------------
    def setup(self) -> None:
        import os
        from dataclasses import replace

        data_dir = self.out / "state"
        os.environ["STEWARD_MEMORY_DIR"] = str(self.out / "memory")
        if not self.llm:
            os.environ["STEWARD_USE_LLM"] = "off"
        t = time.perf_counter()
        from steward import Steward
        from steward.config import Settings
        from steward.inbox import Inbox
        from steward.semantic import load_frames
        from steward.suggest import Suggestions

        settings = Settings.from_env()
        settings = replace(settings, data_dir=data_dir, as_of=ENGINE_DATE, **({} if self.llm else {"use_llm": "off"}))
        self.steward = Steward(settings=settings)
        self.timings["engine_load_s"] = round(time.perf_counter() - t, 2)
        t = time.perf_counter()
        self.frames = load_frames()
        sup = self.frames["fact_supply"].merge(self.frames["dim_product"][["product_id", "product_name"]],
                                               on="product_id")
        self.supply = list(sup[["product_name", "market_id", "supply_source"]].itertuples(index=False, name=None))
        self.timings["frames_load_s"] = round(time.perf_counter() - t, 2)
        self.plants = sorted({s for _, _, s in self.supply})
        self.inbox = Inbox(data_dir)
        self.suggestions = Suggestions(self.out / "memory")
        from .personas import build_personas

        self.personas = build_personas(self.plants, self.rng, self.n_workers, self.n_managers)
        from steward.requests import load_requests

        self.business_requests = load_requests()
        self.catalog_size = len(self.steward.catalog.artifacts)

    # -- the clock --------------------------------------------------------------------------------------------------
    def run(self) -> None:
        self.setup()
        days = _working_days(ENGINE_DATE, self.days)
        builder = next(p for p in self.personas if p.user.role == "builder")
        people = [p for p in self.personas if p.user.role != "builder"]
        for i, day in enumerate(days):
            self.rng.shuffle(people)
            for p in people:
                for _ in range(poisson(self.rng, p.rate)):
                    if p.user.role == "worker":
                        self._guard(self.worker_session, p, i, day)
                    else:
                        self._guard(self.manager_session, p, i, day)
            if self.attendance.random() < 0.9:  # the BI team is not in every day (own stream: stable schedule)
                self._guard(self.builder_day, builder, i, day)
            if (i + 1) % self.reload_every == 0:
                t = time.perf_counter()
                self.steward.reload()  # approvals made new provisional assets: the next searches see them
                self.timings.setdefault("reload_s", []).append(round(time.perf_counter() - t, 2))
            print(f"  [{self.pack}] day {i + 1}/{len(days)} {day}: {len(self.rows)} interactions, "
                  f"{len(self.issues)} issues", flush=True)
        self.determinism_check()

    def _guard(self, fn, p, i, day) -> None:
        try:
            fn(p, i, day)
        except Exception as e:  # noqa: BLE001 - a crash is a finding, not an abort
            self.issue("crash", "critical", p, f"{fn.__name__}: {type(e).__name__}: {e}"[:300],
                       trace=traceback.format_exc()[-1200:], day=str(day))

    # -- recording --------------------------------------------------------------------------------------------------
    def base(self, p, i: int, day: date, channel: str) -> dict:
        u = p.user
        return {"pack": self.pack, "day": i + 1, "date": str(day), "user": u.username, "role": u.role,
                "subrole": p.subrole, "plant": u.plant, "department": u.department, "channel": channel,
                "search_used": False, "typeahead_hit": False, "questions": 0, "transcript": [], "verdict": None,
                "asset": None, "spec": False, "lint": None, "render": None, "shown": [], "covered": [], "missing": [],
                "outcome": None, "met": None, "score": None, "happy": None, "friction": [], "escalated": None,
                "latency_s": 0.0, "notices": 0, "error": None}

    def issue(self, kind: str, severity: str, p, detail: str, **extra) -> None:
        self.issues.append({"pack": self.pack, "kind": kind, "severity": severity,
                            "user": p.user.username if p else None, "role": p.user.role if p else None,
                            "subrole": p.subrole if p else None, "detail": detail, **extra})

    def notices(self, p, i: int) -> int:
        seen = self.inbox.pop_notices(p.user.username)
        for text in seen:
            for loop in self.loops:
                if loop["who"] == p.user.username and loop.get("seen") is None and loop["need"][:40] in text:
                    loop["seen"] = i + 1
                    break
        return len(seen)

    def finish(self, row: dict, p, t0: float) -> None:
        row["latency_s"] = round(row["latency_s"] + time.perf_counter() - t0, 3)
        _score(row, p)
        self.rows.append(row)

    # -- rendering + display checks ---------------------------------------------------------------------------------
    def render(self, spec, p, row: dict):
        from steward.render import render

        key = hashlib.sha256(spec.model_dump_json(exclude={"lint", "provenance"}).encode()).hexdigest()
        if key not in self.render_memo:  # render is deterministic: same spec, same page (cost is still charged)
            t = time.perf_counter()
            try:
                dash, err = render(spec, self.frames), None
            except Exception as e:  # noqa: BLE001
                dash, err = None, f"{type(e).__name__}: {e}"[:200]
            self.render_memo[key] = (dash, err, time.perf_counter() - t)
        dash, err, secs = self.render_memo[key]
        row["latency_s"] += secs
        if err:
            self.issue("render_crash", "critical", p, err, text=row.get("text"))
            row["render"] = {"error": err}
            return None
        row["render"] = audit_render(dash, spec, p.user, row, self)
        return dash

    # -- worker -----------------------------------------------------------------------------------------------------
    def worker_session(self, p, i: int, day: date) -> None:
        from steward.inbox import Inbox  # noqa: F401  (same store as self.inbox)
        from steward.worker import (
            NEEDS,
            WorkerAnswer,
            other_plant,
            prompts_for,
            refusal,
            reuse_only,
            sites_named,
            suggest,
        )

        from .scenarios import WORKER, fill, pick_scenario

        u, rng = p.user, self.rng
        granted = self.inbox.grants(u.username)
        channel = rng.choices(list(p.channels), weights=list(p.channels.values()))[0]
        if granted and rng.random() < 0.25:
            channel = "shared"
        row = self.base(p, i, day, channel)
        row["notices"] = self.notices(p, i)
        t0 = time.perf_counter()
        answer, sc = None, None
        if channel in ("button", "shared"):
            dept = rng.choice(granted) if channel == "shared" else u.department
            prompts = prompts_for(self.steward, dept)
            if not prompts:
                row.update(outcome="no_prompts", met=False, text=f"(no buttons for {dept})")
                row["friction"].append("no prompt buttons for department")
                self.finish(row, p, t0)
                return
            prompt = rng.choice(prompts)
            row["text"] = prompt.label
            sc = {"id": f"button.{dept}.{prompt.label}", "want": list(prompt.metric_ids),
                  "need": prompt.not_governed, "expect": "not_governed" if prompt.not_governed else "answer"}
            answer = (WorkerAnswer(not_governed=prompt.not_governed) if prompt.not_governed
                      else reuse_only(self.steward, u, list(prompt.metric_ids), prompt.label, self.supply))
        elif channel == "chat":
            sc = fill(pick_scenario(WORKER[u.department], rng), p, self.plants, rng)
            row.update(text=sc["text"], wording=sc["wording"])
            site = other_plant(u, sites_named(sc["text"]))
            if site:
                answer = WorkerAnswer(refused=refusal(u, site))
                row["transcript"].append(["assistant", answer.refused])
            else:
                sg = suggest(self.steward, u, sc["text"], self.supply)
                row["transcript"].append(["assistant", sg.reply])
                row["offered"] = [s.label for s in sg.items]
                row["lacks"] = list(sg.lacks)
                pick = _pick(sg.items, sc["want"], p, rng, self.steward)
                if pick is not None:
                    from steward.worker import open_item

                    row["transcript"].append(["user", f"(clicks) {pick.label}"])
                    answer = open_item(self.steward, u, pick.id, self.supply)
                else:
                    answer = WorkerAnswer()
                row["reply"] = sg.reply
        else:  # "other": the three-step mini grill for another department at the same plant
            self._access_request(p, i, row, NEEDS)
            self.finish(row, p, t0)
            return
        row.update(scenario=sc["id"], expect=sc["expect"], want=sc["want"], need=sc.get("need", ""))
        self._worker_outcome(p, i, row, sc, answer)
        self.finish(row, p, t0)

    def _access_request(self, p, i: int, row: dict, needs: dict) -> None:
        from steward.auth import can_request
        from steward.worker import CADENCES, log_request, request_entry, same_request

        u, rng = p.user, self.rng
        options = [d for d in needs if can_request(u, u.plant, d)[0] and d not in self.inbox.grants(u.username)]
        if not options:
            row.update(text="(Other department: nothing left to request)", outcome="nothing_to_request", met=True,
                       expect="escalate", scenario="other.none")
            return
        dept = rng.choice(options)
        need = rng.choice(needs[dept])
        entry = request_entry(u, "access", need, dept, rng.choice(CADENCES))
        stored, joined = self.inbox.add_floor(entry, same_request)
        log_request(self.steward.data_dir, stored, "open", entry["who"])
        row.update(text=f"Other department: {dept} / {need}", scenario=f"other.{dept}", expect="escalate",
                   outcome="joined_request" if joined else "access_requested", met=True, questions=3,
                   escalated="access")
        row["transcript"] += [["assistant", "Which department?"], ["user", dept], ["assistant", "What exactly?"],
                              ["user", need], ["assistant", "How often?"], ["user", entry["cadence"]]]
        if not joined:
            self.pending[stored["id"]] = {"day": i + 1, "kind": "access", "who": u.username}
        self.loops.append({"id": stored["id"], "who": u.username, "kind": "access", "need": need, "asked": i + 1})

    def _worker_outcome(self, p, i: int, row: dict, sc: dict, answer) -> None:
        from steward.worker import log_request, request_entry, same_request

        expect, want = sc["expect"], set(sc["want"])
        if answer.refused:
            row["outcome"] = "refused"
        elif answer.result is not None:
            res = answer.result
            row.update(verdict="REUSE", asset=res.decision.best.artifact.id, spec=res.spec is not None,
                       covered=list(answer.covered), missing=list(answer.missing))
            if res.spec is not None:
                row["lint"] = _lint(res.spec)
                row["shown"] = [m.name for m in res.spec.measures]
                self.render(res.spec, p, row)
            row["outcome"] = "answered"
        elif answer.not_governed:
            row["outcome"] = "not_governed_said"
        elif answer.missing:
            row.update(outcome="no_visible_report", missing=list(answer.missing))
        else:
            row["outcome"] = "not_understood"
        reply = (row.get("reply") or "").lower()
        need = (sc.get("need") or "").lower()
        if expect == "answer":
            got = set(answer.covered)
            row["met"] = bool(want) and want <= got and row["outcome"] == "answered" and _has_numbers(row)
            row["partial"] = bool(got & want) and not row["met"]
            if row["outcome"] == "answered" and not got & want:
                row["friction"].append("answer shows other numbers than asked")
        elif expect == "not_governed":
            said = row["outcome"] == "not_governed_said" or (need and (need in reply or need in
                                                                     [x.lower() for x in row.get("lacks", [])]))
            row["met"] = bool(said)
            if not said and row["outcome"] == "answered":
                row["friction"].append("not-governed need answered with an unrelated KPI")
        elif expect == "refuse":
            row["met"] = row["outcome"] == "refused"
            if not row["met"]:
                self.issue("scope_leak", "critical", p, f"other-plant question was not refused: {row.get('text')}")
        elif expect == "honest_no":
            row["met"] = "management and finance" in reply
        elif expect == "clarify":
            row["met"] = not row.get("offered") and row["outcome"] in ("not_understood",)
            if row.get("offered"):
                row["friction"].append("off-topic text answered with KPI suggestions")
        unanswered = row["outcome"] in ("not_governed_said", "no_visible_report", "not_understood") or (
            expect == "answer" and not row["met"])
        if unanswered and expect not in ("refuse", "honest_no", "clarify") and self.rng.random() < p.escalate:
            missing = [m for m in want if m not in set(answer.covered)]
            label = need or ", ".join(self.steward.catalog.metrics[m].name for m in missing
                                      if m in self.steward.catalog.metrics) or row.get("text", "")
            entry = request_entry(p.user, "report", label, metric_ids=[] if need else missing)
            stored, joined = self.inbox.add_floor(entry, same_request)
            log_request(self.steward.data_dir, stored, "open", entry["who"])
            row["escalated"] = "report_joined" if joined else "report"
            if not joined:
                self.pending[stored["id"]] = {"day": i + 1, "kind": "report", "who": p.user.username}
            self.loops.append({"id": stored["id"], "who": p.user.username, "kind": "report", "need": label,
                               "asked": i + 1})

    # -- management ---------------------------------------------------------------------------------------------------
    def manager_session(self, p, i: int, day: date) -> None:
        from steward.intent import Intent
        from steward.interview import InterviewState
        from steward.worker import other_plant, own_plant_scope, refusal

        from .scenarios import MANAGER, fill, pick_scenario

        u, rng = p.user, self.rng
        channel = rng.choices(list(p.channels), weights=list(p.channels.values()))[0]
        row = self.base(p, i, day, channel)
        row["notices"] = self.notices(p, i)
        sc = fill(pick_scenario(MANAGER[p.subrole], rng), p, self.plants, rng)
        row.update(text=sc["text"], wording=sc["wording"], scenario=sc["id"], expect=sc["expect"], want=sc["want"],
                   need=sc.get("need", ""))
        t0 = time.perf_counter()
        state = None
        if channel == "typeahead":
            row["search_used"] = True
            typed = " ".join(sc["text"].split()[: rng.randint(2, 4)])
            hits = self.suggestions.for_user(u, typed=typed, k=6)
            row["typeahead"] = {"typed": typed, "offered": [h.text for h in hits][:6]}
            same = [h for h in hits if h.text.lower() == sc["text"].lower()] or (
                hits[:1] if hits and rng.random() > p.savvy else [])
            if same:
                row["typeahead_hit"] = True
                row["text"] = same[0].text
                known = self.suggestions.intent_for(u, same[0].text)
                if known:
                    state = InterviewState(intent=Intent(**known), turns=[("user", same[0].text)], question=None)
                    row["path"] = "reused"
        if state is None:
            row.setdefault("path", "interview")
            home = u.plant
            state = self.steward.interviewer.start(row["text"], home_plant=home)
            state = self._interview(state, sc, p, row)
        if row.get("abandoned"):
            row.update(outcome="clarified", verdict="CLARIFY", met=True)
            self.suggestions.log(u, row["text"], row["path"], "CLARIFY", None)
            self.finish(row, p, t0)
            return
        site = other_plant(u, state.intent.sites)
        if site:
            row.update(outcome="refused", verdict="REFUSED")
            row["transcript"].append(["assistant", refusal(u, site)])
            self.suggestions.log(u, row["text"], row["path"], "REFUSED", state.intent.model_dump(mode="json"),
                                 other_plant=site)
            if rng.random() < p.escalate:
                row["friction"].append("told to ask the BI team for access, but management has no request button")
                row["escalated"] = "dead_end"
            row["met"] = sc["expect"] == "refuse"
            self.finish(row, p, t0)
            return
        intent = own_plant_scope(u, state.intent)
        res = self.steward.ask_intent(intent)
        res = self.steward.investigate(res, intent)
        res = self.steward.build(res, intent, u)
        if res.decision.verdict.value == "CLARIFY" and sc["wording"] != "precise" and rng.random() < 0.6:
            row["friction"].append("had to rephrase after CLARIFY")
            row["retried"] = True
            precise = sc["text"] if sc["wording"] == "typo" else fill({**sc, "vague": None}, p, self.plants, rng)[
                "text"]
            state = self._interview(self.steward.interviewer.start(precise, home_plant=u.plant), sc, p, row)
            intent = own_plant_scope(u, state.intent)
            res = self.steward.build(self.steward.ask_intent(intent), intent, u)
        self._manager_outcome(p, i, row, sc, res, intent)
        self.finish(row, p, t0)

    def _interview(self, state, sc: dict, p, row: dict):
        for _ in range(8):  # the app caps at 5 questions; 8 turns is a runaway guard
            if state.done:
                break
            row["questions"] += 1
            row["transcript"].append(["assistant", (state.question or "")[:240]])
            if state.last_asked == "clarify" and sc["expect"] == "clarify":
                row["abandoned"] = True  # the app said "not a data question": the person leaves, nothing is built
                return state
            if row["questions"] > p.patience:
                row["transcript"].append(["user", "(Skip - use recommended)"])
                row["skipped"] = True
                state = self.steward.interviewer.finish_with_defaults(state)
                break
            reply = _reply(state, sc, p, self.rng)
            row["transcript"].append(["user", reply])
            state = self.steward.interviewer.answer(state, reply)
        if not state.done:
            self.issue("interview_runaway", "high", p, f"interview not finished after 8 turns: {row['text']}")
            state = self.steward.interviewer.finish_with_defaults(state)
        row["understood"] = state.intent.model_dump(include={"metric_ids", "products", "markets", "regions", "sites",
                                                             "theme", "decision_supported"})
        return state

    def _manager_outcome(self, p, i: int, row: dict, sc: dict, res, intent) -> None:
        from steward.semantic import _slug_to_kpi

        verdict = res.decision.verdict.value
        row.update(verdict=verdict, asset=res.decision.best.artifact.id if res.decision.best else None,
                   spec=res.spec is not None)
        dumped = intent.model_dump(mode="json")
        self.suggestions.log(p.user, row["text"], row.get("path", "interview"), verdict, dumped, row["asset"],
                             spec=res.spec is not None)
        if verdict in BUILDS:
            self.suggestions.record(p.user, row["text"], dumped)
        if res.spec is not None:
            row["lint"] = _lint(res.spec)
            row["shown"] = [m.name for m in res.spec.measures]
            row["archetype"] = getattr(res.spec, "archetype", "") or "template"
            kpis = {m.kpi_id for m in res.spec.measures if m.feasible}
            slug = _slug_to_kpi()
            row["covered"] = [m for m in sc["want"] if slug.get(m, m) in kpis]
            row["missing"] = [m for m in sc["want"] if m not in row["covered"]]
            self.render(res.spec, p, row)
            if len(self.specs_for_pbip) < 12 and verdict in ("CREATE", "EXTEND"):
                self.specs_for_pbip.append(res.spec)
        expect = sc["expect"]
        if expect == "answer" and sc["want"] and _all_gaps(sc["want"]):
            expect = row["expect"] = "gap"  # governed KPIs with no source data: the honest answer is a labelled gap
        if expect == "gap":
            gaps = [m for m in (res.spec.measures if res.spec else []) if not m.feasible]
            row["met"] = verdict == "NOT_FEASIBLE" or bool(gaps)
            row["outcome"] = "labelled_gap" if gaps else verdict.lower()
        elif expect == "answer":
            row["met"] = verdict in BUILDS and res.spec is not None and not row["missing"] and _has_numbers(row)
            row["partial"] = bool(row["covered"]) and not row["met"]
            row["outcome"] = "dashboard" if res.spec is not None else verdict.lower()
        elif expect == "clarify":
            row["met"] = verdict == "CLARIFY"
            row["outcome"] = verdict.lower()
            if not row["met"]:
                self.issue("wrong_build", "high", p, f"expected CLARIFY, got {verdict}: {row['text']}")
        elif expect == "not_governed":
            gap = any(not m.feasible for m in (res.spec.measures if res.spec else []))
            said = any("not measured" in e.claim.lower() or "not used" in e.claim.lower()
                       for e in res.decision.evidence)
            row["met"] = said or gap
            row["outcome"] = "said_not_governed" if row["met"] else verdict.lower()
        elif expect == "refuse":
            row["met"] = False
            row["outcome"] = verdict.lower()
            self.issue("scope_leak", "critical", p, f"other-plant request built a {verdict}: {row['text']}",
                       sites=intent.sites)
        if verdict in ("EXTEND", "CREATE", "CONSOLIDATE") and res.spec is not None and self.rng.random() < p.escalate:
            key = self.inbox.send(res, intent, True, p.user)
            row["escalated"] = "approval"
            if key not in self.pending:
                self.pending[key] = {"day": i + 1, "kind": "approval", "who": p.user.username}
                self.loops.append({"id": key, "who": p.user.username, "kind": "approval", "need": row["text"],
                                   "asked": i + 1})

    # -- builder (admin) ----------------------------------------------------------------------------------------------
    def builder_day(self, p, i: int, day: date) -> None:
        from steward.worker import log_request

        u, rng = p.user, self.rng
        self.notices(p, i)
        for item in self.inbox.open_approvals():
            t0 = time.perf_counter()
            row = self.base(p, i, day, "approvals")
            taken = self.inbox.take(item["id"], u.label)
            if taken is None:
                continue
            q, res, intent = taken
            row.update(text=q["question"], verdict=q["verdict"], scenario="builder.approve", expect="decide",
                       requested_by=q["from"])
            blocks = [r for r in (res.spec.lint if res.spec else []) if r.status == "block"]
            owner = q["username"] if (res.decision.verdict.value == "CREATE" or (
                res.decision.best and not res.decision.best.artifact.has_owner)) else None
            try:
                if blocks or (res.spec is None and q["verdict"] != "REUSE"):
                    reason = "lint block: " + "; ".join(r.rule_id for r in blocks) if blocks else "no dashboard"
                    self.steward.governance.reject(res, actor=f"{u.label}, requested by {q['from']}", reason=reason)
                    self.inbox.decide(item["id"], "sent_back", u.label, reason=reason)
                    row.update(outcome="sent_back", met=True)
                else:
                    entry = self.steward.governance.approve(res, actor=f"{u.label}, requested by {q['from']}",
                                                            owner=owner)
                    detail = f"New artifact: {entry.created_artifact_id}." if entry.created_artifact_id else ""
                    self.inbox.decide(item["id"], "approved", u.label, detail=detail)
                    row.update(outcome="approved", met=True, asset=entry.created_artifact_id)
            except ValueError as e:
                row.update(outcome="approve_refused", met=False, error=str(e)[:200])
                self.inbox.decide(item["id"], "sent_back", u.label, reason=str(e)[:120])
                self.issue("approve_refused", "medium", p, str(e)[:200], text=q["question"])
            self._close_loop(item["id"], i)
            self.finish(row, p, t0)
        for req in self.inbox.floor("open"):
            t0 = time.perf_counter()
            row = self.base(p, i, day, "floor")
            row.update(text=f"{req['kind']}: {req['need']}", scenario=f"builder.floor.{req['kind']}", expect="decide",
                       requested_by=req["who"], joined=len(req.get("also", [])))
            if req["kind"] == "access":
                status = "granted" if rng.random() < 0.85 else "declined"
            elif req.get("metric_ids"):
                status = "started"
                self._start_report(p, req, row)
            else:
                status = "declined"  # a need no governed KPI covers: back to the data owner
                row["friction"].append("builder can only decline a not-governed need (no data-owner hand-off)")
            self.inbox.decide_floor(req["id"], status, u.label)
            log_request(self.steward.data_dir, req, status, u.label)
            row.update(outcome=status, met=True)
            self._close_loop(req["id"], i)
            self.finish(row, p, t0)
        for _ in range(rng.randint(1, 3)):  # the builder's own work: expert-mode asks from the pack's requests
            self._guard(self._expert_ask, p, i, day)
        if i % 5 == 0:
            self._guard(self._estate, p, i, day)

    def _start_report(self, p, req: dict, row: dict) -> None:
        from steward.intent import Intent

        intent = Intent(text=f"{req['need']} for {req['plant']}", metric_ids=req["metric_ids"], sites=[req["plant"]],
                        decision_supported="monitor",
                        confidence={"metric_ids": 1.0, "sites": 1.0, "decision_supported": 1.0})
        res = self.steward.build(self.steward.ask_intent(intent), intent, p.user)
        row.update(verdict=res.decision.verdict.value, spec=res.spec is not None)
        if res.spec is not None:
            row["lint"] = _lint(res.spec)
            row["shown"] = [m.name for m in res.spec.measures]
            self.render(res.spec, p, row)
            if row["lint"]["worst"] != "block" and res.decision.verdict.value in ("CREATE", "EXTEND", "CONSOLIDATE"):
                try:
                    self.steward.governance.approve(res, actor=f"{p.user.label}, requested by {req['who']}",
                                                    owner=req["username"])
                    row["approved"] = True
                except ValueError as e:
                    self.issue("approve_refused", "medium", p, str(e)[:200], text=intent.text)

    def _expert_ask(self, p, i: int, day: date) -> None:
        req = self.rng.choice(self.business_requests)
        t0 = time.perf_counter()
        row = self.base(p, i, day, "expert")
        row.update(text=req.text, scenario=f"pack.{req.request_id}", expect="any", path="expert")
        res = self.steward.ask(req.text, req.context)
        res = self.steward.build(res, None, p.user)
        best = res.decision.best.artifact.id if res.decision.best else None
        row.update(verdict=res.decision.verdict.value, asset=best,
                   spec=res.spec is not None, met=True, outcome=res.decision.verdict.value.lower())
        if res.spec is not None:
            row["lint"] = _lint(res.spec)
            row["shown"] = [m.name for m in res.spec.measures]
            self.render(res.spec, p, row)
        self.finish(row, p, t0)

    def _estate(self, p, i: int, day: date) -> None:
        from steward.estate_view import estate_view, my_assets

        t0 = time.perf_counter()
        row = self.base(p, i, day, "estate")
        h = self.steward.health()
        ev = estate_view(self.steward.catalog)
        owner = next((a.owner for a in self.steward.catalog.artifacts.values() if a.owner), "")
        mine = my_assets(self.steward.catalog, owner) if owner else None
        row.update(text="weekly estate health", scenario="builder.estate", expect="any", met=True, outcome="ok",
                   estate={"duplicates": len(getattr(h, "duplicates", []) or []),
                           "actions": len(ev.actions), "my_assets": len(mine.assets) if mine else 0})
        if self.pbip_left > 0 and self.specs_for_pbip:
            self.pbip_left -= 1
            row["pbip"] = self._pbip(self.specs_for_pbip.pop(0), p)
        self.finish(row, p, t0)

    def _pbip(self, spec, p) -> dict:
        import tempfile

        from steward.pbip import export_pbip

        t = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = export_pbip(spec, self.frames, Path(tmp))
                size = path.stat().st_size if path.exists() else 0
            ok = size > 0
            if not ok:
                self.issue("pbip_empty", "high", p, f"export wrote nothing for {spec.name}")
            return {"ok": ok, "bytes": size, "secs": round(time.perf_counter() - t, 2)}
        except Exception as e:  # noqa: BLE001
            self.issue("pbip_crash", "high", p, f"{type(e).__name__}: {e}"[:200], spec=spec.name)
            return {"ok": False, "error": str(e)[:160]}

    def _close_loop(self, item_id: str, i: int) -> None:
        self.pending.pop(item_id, None)
        for loop in self.loops:
            if loop["id"] == item_id and loop.get("decided") is None:
                loop["decided"] = i + 1

    # -- determinism ----------------------------------------------------------------------------------------------
    def determinism_check(self, n: int = 25) -> None:
        """The same confirmed Intent twice must give the same verdict and report (the rules engine is the contract)."""
        from steward.intent import Intent

        rows = [r for r in self.suggestions.history() if r.get("intent") and r.get("verdict") in BUILDS][:n]
        diffs = 0
        for r in rows:
            res = self.steward.ask_intent(Intent(**r["intent"]), explain=False)
            again = self.steward.ask_intent(Intent(**r["intent"]), explain=False)
            a = (res.decision.verdict.value, res.decision.best.artifact.id if res.decision.best else None)
            b = (again.decision.verdict.value, again.decision.best.artifact.id if again.decision.best else None)
            if a != b:
                diffs += 1
                self.issue("nondeterministic", "high", None, f"{r['text']}: {a} vs {b}")
        self.timings["determinism"] = {"checked": len(rows), "differences": diffs}


# -- helpers ----------------------------------------------------------------------------------------------------------
def _working_days(end: date, n: int) -> list[date]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


def _pick(items, want: list[str], p, rng: random.Random, steward):
    """The person clicks the suggestion that shows what they want (savvy) or simply the first one."""
    if not items:
        return None
    if rng.random() < p.savvy:
        for item in items:
            kind, _, key = item.id.partition(":")
            if kind == "kpi" and key in want:
                return item
    return items[0]


def _reply(state, sc: dict, p, rng: random.Random) -> str:
    """How a person answers one interview question: one-click options when offered, else a few typed words."""
    opts, about = list(state.options or []), state.last_asked
    pick = sc.get("pick") or {}
    if rng.random() < (1 - p.savvy) * 0.2:
        return rng.choice(["not sure", "whatever you think", "hmm", "just show me"])
    if about == "clarify":
        return sc.get("insist") or sc.get("precise") or sc["text"]  # says what they meant, in plain words
    if sc.get("insist") and about in ("unmapped", "products"):
        return sc["insist"]  # "Roundup": the person insists on the product they named
    if about == "decision_supported" and opts:
        prefer = {"Shareholder / exec": "Board update", "Site head": "Weekly review",
                  "Finance controller": "Decide on an action"}.get(p.subrole)
        return next((o for o in opts if o == prefer), opts[0])
    key = {"products": "product", "markets": "market", "sites": "site"}.get(about)
    if key:  # answer the question that was asked: the value meant for it, else "all of them"
        meant = pick.get(key)
        if not meant:
            return next((o for o in opts if o.lower().startswith("all")), "all of them")
        return next((o for o in opts if meant.lower() in o.lower()), meant)
    wanted = [pick.get(k) for k in ("site", "product", "market") if pick.get(k)]
    for w in wanted:
        hit = next((o for o in opts if w.lower() in o.lower()), None)
        if hit:
            return hit
    if opts:
        return opts[0]
    return "yes"


def _all_gaps(metric_ids: list[str]) -> bool:
    from steward.intent import Intent
    from steward.semantic import feasibility

    gaps = feasibility(Intent(metric_ids=list(metric_ids))).gaps
    return len(gaps) == len(metric_ids)


def _lint(spec) -> dict:
    from steward.lint import worst

    res = spec.lint or []
    return {"worst": worst(res) if res else "pass", "blocks": [r.rule_id for r in res if r.status == "block"],
            "warns": [r.rule_id for r in res if r.status == "warn"]}


def _has_numbers(row: dict) -> bool:
    r = row.get("render") or {}
    return bool(r.get("numbers"))


def audit_render(dash, spec, user, row: dict, sim: Sim) -> dict:
    """What the person sees, checked for logic: numbers present, no blank values, gaps labelled not numbered, plant
    filter matches the login (workers), density inside the focus caps, charts that actually hold data."""
    out = {"title": dash.title, "archetype": dash.archetype or "template", "cards": len(dash.cards),
           "tiles": len(dash.tiles), "figures": len(dash.figures), "tables": len(dash.tables), "gaps": len(dash.gaps),
           "dq_notes": len(dash.dq), "filters": dict(dash.filters), "problems": []}
    values = [c.value for c in dash.cards] + [t.value for t in dash.tiles if t.status != "gap"]
    blank = [v for v in values if str(v).strip().lower() in ("", "nan", "none", "n/a", "-", "nan%")]
    empty_figs = [t for t, f in dash.figures if not _fig_has_data(f)]
    empty_tables = [t for t, df in dash.tables if df is None or df.empty]
    out["numbers"] = len(values) - len(blank) + (len(dash.figures) - len(empty_figs)) + (
        len(dash.tables) - len(empty_tables))
    out["sample"] = [f"{c.title}: {c.value} {c.comparison}".strip() for c in dash.cards[:3]] + [
        f"{t.title}: {t.value} {t.delta}".strip() for t in dash.tiles[:3]]
    p = out["problems"]
    if out["numbers"] == 0:
        p.append("no numbers on the page" + (" (only gaps)" if dash.gaps else ""))
    if blank:
        p.append(f"{len(blank)} blank value(s) on cards/tiles")
    if empty_figs:
        p.append(f"{len(empty_figs)} chart(s) with no data: " + "; ".join(empty_figs[:2]))
    if empty_tables:
        p.append(f"{len(empty_tables)} empty table(s)")
    if not dash.title.strip():
        p.append("dashboard has no title")
    gap_kpis = {g.kpi_id for g in dash.gaps}
    numbered = {c.kpi_id for c in dash.cards} | {t.kpi_id for t in dash.tiles if t.status != "gap"}
    if gap_kpis & numbered:
        p.append("a gap KPI is also shown as a number: " + ", ".join(sorted(gap_kpis & numbered)))
    if user.role == "worker":
        site = dash.filters.get("site")
        if site != user.plant:
            p.append(f"worker on {user.plant} sees site filter {site!r}")
            sim.issue("plant_leak", "critical", None, f"{user.username} ({user.plant}) dashboard filter {site!r}",
                      text=row.get("text"))
    if dash.archetype == "OVERVIEW" and (len(dash.tiles) > 8 or len(dash.figures) > 6):
        p.append(f"OVERVIEW too dense: {len(dash.tiles)} tiles, {len(dash.figures)} charts")
    if dash.archetype != "OVERVIEW" and len(dash.figures) + len(dash.tables) > 8:
        p.append(f"template page holds {len(dash.figures) + len(dash.tables)} visuals")
    for problem in p:
        sim.issue("display", "high" if "no numbers" in problem or "blank" in problem else "medium", None, problem,
                  user=user.username, text=row.get("text"), title=dash.title)
    return out


def _fig_has_data(fig) -> bool:
    for tr in fig.data:
        for axis in ("y", "x", "values"):
            v = getattr(tr, axis, None)
            if v is not None and len(v) > 0:
                return True
    return False


def _score(row: dict, p) -> None:
    """1..5 from the person's point of view. Start at 5; lose points for a missed expectation, partial answers, more
    questions than their patience, slow answers, broken pages. A correct 'no' (refusal, not governed) caps at 4:
    honest, but they still lack the number."""
    if row.get("expect") in ("decide", "any"):
        row["score"], row["happy"] = None, None
        return
    s = 5.0
    if row.get("met") is False:
        s -= 1.5 if row.get("partial") else 2.5
    over = row["questions"] - p.patience
    if row["role"] == "management" and over > 0:
        s -= min(2, over)
        row["friction"].append("more questions than the person's patience")
    if row.get("skipped"):
        s -= 0.5
        row["friction"].append("pressed skip in the interview")
    if row.get("retried"):
        s -= 1
    lat = row["latency_s"]
    if lat > (2 if row["role"] == "worker" else 5):
        s -= 1
        row["friction"].append(f"slow ({lat:.1f}s)")
    if lat > (5 if row["role"] == "worker" else 12):
        s -= 1
    problems = (row.get("render") or {}).get("problems") or []
    if problems:
        s -= 1.5
        row["friction"].append("display problem: " + problems[0])
    if row.get("expect") in ("refuse", "not_governed", "honest_no", "escalate", "gap") and row.get("met"):
        s = min(s, 4.0)
    if row["role"] == "worker" and (row.get("render") or {}).get("dq_notes", 0) >= 2:
        row["friction"].append("floor view shows data-quality footnotes")
    if row.get("escalated") == "dead_end":
        s -= 1
    row["score"] = max(1.0, min(5.0, s))
    row["happy"] = row["score"] >= 4
