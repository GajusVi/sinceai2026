import os, sys, time, json, shutil, tempfile, warnings
warnings.filterwarnings("ignore")
os.environ["STEWARD_CATALOG"] = "datapack"
os.environ.setdefault("STEWARD_USE_LLM", sys.argv[1] if len(sys.argv) > 1 else "off")
d = tempfile.mkdtemp(); shutil.copytree("demo/steward_seed", d, dirs_exist_ok=True)
os.environ["STEWARD_DATA_DIR"] = d
sys.path.insert(0, ".")
from dataclasses import replace
from steward import Steward, semantic
from steward.config import Settings
from steward.auth import login
from steward.render import render
from steward.worker import other_plant, own_plant_scope, refusal, sites_named, suggest, reuse_only
st = Steward(settings=Settings.from_env())
frames = semantic.load_frames()
A = {"M": ("Manager07","Manage123"), "B": ("Builder12","Admin123"), "W": ("Worker21","Worker123"), "W2": ("Worker22","Worker123")}
def run(tag, who, text):
    u = login(*A[who]); t0 = time.time(); out = {"tag": tag, "user": u.username, "role": u.role, "text": text}
    try:
        if u.role == "worker":
            sites = sites_named(text); s = other_plant(u, sites)
            if s: out.update(verdict="REFUSED", note=refusal(u, s)); return out
            sg = suggest(st, u, text, frames_supply())
            out.update(verdict="WORKER-SUGGEST", reply=sg.reply, items=[(i.label, i.id) for i in sg.items], lacks=sg.lacks, archetype="n/a (worker)")
            return out
        home = u.plant if u.role == "management" else ""
        state = st.interviewer.start(text, home_plant=home)
        s = other_plant(u, state.intent.sites)
        if s: out.update(verdict="REFUSED", note=refusal(u, s), sites=state.intent.sites); return out
        state = st.interviewer.finish_with_defaults(state)
        it = own_plant_scope(u, state.intent)
        res = st.ask_intent(it); res = st.build(res, it, u)
        out.update(verdict=str(res.decision.verdict.value if hasattr(res.decision.verdict,"value") else res.decision.verdict),
                   intent=dict(theme=getattr(it,"theme",""), metrics=it.metric_ids, sites=it.sites, products=getattr(it,"products",None), markets=getattr(it,"markets",None)))
        sp = res.spec
        if sp is None: out["archetype"] = "no spec"; return out
        out["archetype"] = getattr(sp,"archetype","") or "template"; out["layout_source"] = sp.provenance.get("layout_source"); out["hash"] = sp.provenance.get("spec_hash")
        out["visuals"] = [(v.type, v.title, getattr(v,"span",None), getattr(v,"row",None)) for p in sp.pages for v in p.visuals]
        out["lint_nonpass"] = [(r.rule_id, r.status, r.message) for r in sp.lint if r.status != "pass"]
        out["filters"] = sp.filters; out["owner"] = sp.owner_id; out["gaps"] = [m.name for m in sp.measures if not m.feasible]
        for th in ("night","day"):
            r = render(sp, frames, None, theme=th)
        out["render"] = dict(tiles=[(t.title, t.value, t.status, getattr(t,"comparison",None)) for t in r.tiles], cards=[(c.title,c.value,c.comparison) for c in r.cards],
            gaps=[(g.title,g.reason) for g in r.gaps], figures=[f[0] for f in r.figures], tables=[(n, len(df)) for n,df in r.tables], dq=r.dq, grid=len(r.grid))
    except Exception as e:
        import traceback; out["crash"] = traceback.format_exc()[-800:]
    finally:
        out["secs"] = round(time.time()-t0, 2)
    return out
def frames_supply():
    f = frames; sp = f["fact_supply"].merge(f["dim_product"][["product_id","product_name"]], on="product_id")
    return list(sp[["product_name","market_id","supply_source"]].itertuples(index=False, name=None))
if __name__ == "__main__":
    ITER = json.load(open(sys.argv[2]))
    res = [run(*i) for i in ITER]
    json.dump(res, open(sys.argv[3], "w"), indent=1, default=str)
    for r in res: print(r["tag"], r["user"], r.get("verdict"), r.get("archetype"), r.get("secs"), "CRASH" if r.get("crash") else "")
