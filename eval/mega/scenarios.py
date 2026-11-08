"""Day-to-day situations per role and sub-role: what people type or click, and what a good answer looks like.

A scenario is a dict:
  id       stable id (report groups by it)
  text     what a precise person types; {product} {market} {region} {plant} {other_plant} are filled per session
  vague    what a less savvy person types for the same need (optional)
  want     governed metric ids the person is after ([] = none)
  need     a need with no governed KPI (expect not_governed)
  expect   answer | not_governed | refuse | honest_no | clarify
  weight   how often it comes up for that sub-role
  pick     for interview answers: which values the person means (product / market / site)
Expectations are the person's view of a good outcome, written before looking at the engine (the backtest's oracle).
"""

from __future__ import annotations

import random

SUPPLY = ["on_time_in_full", "inventory_coverage", "demand_forecast_accuracy"]
PRODUCTS = ["Nubeqa", "Kerendia", "Eylea", "Xarelto", "Beyonttra"]
MARKETS = [("Germany", "DE"), ("France", "FR"), ("Japan", "JP"), ("United States", "US"), ("Spain", "ES"),
           ("Brazil", "BR"), ("United Kingdom", "UK"), ("Italy", "IT")]
REGIONS = ["EMEA", "North America", "Asia Pacific", "Latin America"]

S = dict  # short alias: scenarios read as tables

OFF_TOPIC = [
    S(id="off.lunch", text="what is for lunch in the canteen", want=[], expect="clarify", weight=0.3),
    S(id="off.password", text="I forgot my password", want=[], expect="clarify", weight=0.2),
]

WORKER: dict[str, list[dict]] = {
    "Warehouse Ops": [
        S(id="wh.stock", text="how much stock do we have", vague="stok levels?", want=["inventory_coverage"],
          expect="answer", weight=3),
        S(id="wh.otif", text="are deliveries going out on time and complete", vague="r we late",
          want=["on_time_in_full"], expect="answer", weight=3),
        S(id="wh.supply", text="is supply safe at my plant", vague="all good with supply?", want=SUPPLY,
          expect="answer", weight=2),
        S(id="wh.dash", text="show me the stock dashboard", want=["inventory_coverage"], expect="answer", weight=1),
        S(id="wh.lead", text="supplier lead times this week", need="supplier lead times", want=[],
          expect="not_governed", weight=1),
        S(id="wh.other", text="what is the stock at {other_plant}", want=["inventory_coverage"], expect="refuse",
          weight=0.5),
        S(id="wh.sales", text="sales numbers for {product}", want=[], expect="honest_no", weight=0.4),
    ],
    "Equipment Ops": [
        S(id="eq.units", text="units shipped this month", vague="how many went out", want=["units_shipped"],
          expect="answer", weight=3),
        S(id="eq.downtime", text="line downtime yesterday", vague="why was the line down", need="line downtime",
          want=[], expect="not_governed", weight=2),
        S(id="eq.oee", text="OEE for our lines", need="equipment effectiveness (OEE)", want=[],
          expect="not_governed", weight=2),
        S(id="eq.maint", text="planned maintenance windows", need="planned maintenance", want=[],
          expect="not_governed", weight=1),
        S(id="eq.behind", text="are we behind on shipments", want=["on_time_in_full"], expect="answer", weight=1),
        S(id="eq.other", text="units shipped at {other_plant}", want=["units_shipped"], expect="refuse", weight=0.4),
    ],
    "Quality Ops": [
        S(id="qa.yield", text="batch yield last week", need="batch yield", want=[], expect="not_governed", weight=3),
        S(id="qa.dev", text="how many deviations are open", need="quality deviations", want=[],
          expect="not_governed", weight=2),
        S(id="qa.release", text="batch release status", need="batch release status", want=[],
          expect="not_governed", weight=2),
        S(id="qa.fca", text="forecast accuracy", want=["demand_forecast_accuracy"], expect="answer", weight=1),
        S(id="qa.otif", text="deliveries on time", want=["on_time_in_full"], expect="answer", weight=1.5),
    ],
    "Supply Planning": [
        S(id="sp.fca", text="forecast accuracy for {product}", vague="how good is the forecast",
          want=["demand_forecast_accuracy"], expect="answer", weight=3),
        S(id="sp.bias", text="forecast bias", vague="are we over forecasting", want=["demand_forecast_bias"],
          expect="answer", weight=2),
        S(id="sp.cover", text="stock cover and forecast accuracy", want=["inventory_coverage",
          "demand_forecast_accuracy"], expect="answer", weight=2),
        S(id="sp.plan", text="are we on track vs plan", need="a shipping plan to compare against", want=[],
          expect="not_governed", weight=1),
        S(id="sp.units", text="units shipped by month", want=["units_shipped"], expect="answer", weight=1.5),
        S(id="sp.other", text="forecast accuracy at {other_plant}", want=["demand_forecast_accuracy"],
          expect="refuse", weight=0.4),
        S(id="sp.sales", text="revenue for {product} in {market}", want=[], expect="honest_no", weight=0.4),
    ],
}

MANAGER: dict[str, list[dict]] = {
    "Site head": [
        S(id="sh.plant", text="how is my plant doing", vague="hows things", want=["on_time_in_full",
          "inventory_coverage"], expect="answer", weight=3),
        S(id="sh.supply", text="is supply safe at our site", want=SUPPLY, expect="answer", weight=2),
        S(id="sh.board", text="{plant} overview for the board", want=["on_time_in_full", "inventory_coverage"],
          expect="answer", weight=1.5, pick={"site": "{plant}"}),
        S(id="sh.otif", text="on-time in-full by month at my plant", vague="are we shipping on time",
          want=["on_time_in_full"], expect="answer", weight=2),
        S(id="sh.other", text="compare my plant with {other_plant}", want=["on_time_in_full"], expect="refuse",
          weight=0.6),
        S(id="sh.oee", text="OEE and downtime for my plant", want=[], need="equipment effectiveness (OEE)",
          expect="not_governed", weight=0.6),
    ],
    "Operations director": [
        S(id="od.cover", text="inventory coverage by month for {product}", vague="stock for {product}",
          want=["inventory_coverage"], expect="answer", weight=2, pick={"product": "{product}"}),
        S(id="od.otif_fca", text="on-time in-full and forecast accuracy for my plant",
          want=["on_time_in_full", "demand_forecast_accuracy"], expect="answer", weight=2),
        S(id="od.supply", text="supply health overview", want=SUPPLY, expect="answer", weight=2),
        S(id="od.units", text="units shipped for {product} in {market}", want=["units_shipped"], expect="answer",
          weight=1.5, pick={"product": "{product}", "market": "{market}"}),
        S(id="od.other", text="supply at {other_plant}", want=SUPPLY, expect="refuse", weight=0.8),
    ],
    "Finance controller": [
        S(id="fc.sales", text="net sales for {product} in {market}", vague="how are {product} sales",
          want=["net_sales"], expect="answer", weight=3, pick={"product": "{product}", "market": "{market}"}),
        S(id="fc.gtn", text="gross to net rate for {product} by market", want=["gross_to_net_rate"],
          expect="answer", weight=2, pick={"product": "{product}"}),
        S(id="fc.budget", text="budget variance by quarter for {product}", want=["budget_variance"],
          expect="answer", weight=1.5, pick={"product": "{product}"}),
        S(id="fc.contrib", text="operating contribution for {product} in {region}",
          want=["operating_contribution"], expect="answer", weight=1.5, pick={"product": "{product}"}),
        S(id="fc.fv", text="net sales vs forecast for {product} in {market}", want=["net_sales", "forecast_variance"],
          expect="answer", weight=2, pick={"product": "{product}", "market": "{market}"}),
    ],
    "Commercial lead": [
        S(id="cl.access", text="market access coverage for {product} in {market}", vague="is {product} reimbursed",
          want=["market_access_coverage"], expect="answer", weight=2,
          pick={"product": "{product}", "market": "{market}"}),
        S(id="cl.growth", text="net sales growth for {product} in {market}", want=["net_sales_growth"],
          expect="answer", weight=2, pick={"product": "{product}", "market": "{market}"}),
        S(id="cl.launch", text="launch adoption for {product}", want=["launch_adoption_index"], expect="answer",
          weight=1, pick={"product": "{product}"}),
        S(id="cl.reach", text="commercial reach and digital engagement for {product}",
          want=["commercial_reach_index", "digital_engagement_index"], expect="answer", weight=1,
          pick={"product": "{product}"}),
        S(id="cl.roundup", text="Roundup sales in Brazil", want=[], expect="clarify", weight=0.4,
          insist="Roundup"),
    ],
    "Shareholder / exec": [
        S(id="ex.biz", text="how is the business doing", vague="give me the big picture", want=["net_sales"],
          expect="answer", weight=3),
        S(id="ex.world", text="net sales worldwide for all products", want=["net_sales"], expect="answer", weight=2),
        S(id="ex.growth", text="net sales growth by region", want=["net_sales_growth"], expect="answer", weight=1.5),
        S(id="ex.cert", text="share of certified reports", want=["certified_asset_share"], expect="answer",
          weight=0.5),
        S(id="ex.plant", text="how is {plant} running", want=["on_time_in_full", "inventory_coverage"],
          expect="answer", weight=1, pick={"site": "{plant}"}),
    ],
}

TYPOS = {"stock": "stok", "forecast": "forcast", "delivery": "delivry", "shipped": "shiped", "sales": "salse",
         "inventory": "inventroy", "accuracy": "acuracy", "coverage": "coverge"}


def pick_scenario(bank: list[dict], rng: random.Random, off_topic: bool = True) -> dict:
    pool = bank + (OFF_TOPIC if off_topic else [])
    return rng.choices(pool, weights=[s["weight"] for s in pool])[0]


def fill(scenario: dict, persona, plants: list[str], rng: random.Random) -> dict:
    """One concrete session: placeholders filled, the person's wording chosen by savvy (precise, vague or a typo)."""
    others = [p for p in plants if p != persona.user.plant] or plants
    market, market_id = rng.choice(MARKETS)
    values = {"product": rng.choice(PRODUCTS), "market": market, "region": rng.choice(REGIONS),
              "plant": persona.user.plant, "other_plant": rng.choice(others)}
    if scenario.get("vague") and rng.random() > persona.savvy:
        text, wording = scenario["vague"], "vague"
    else:
        text, wording = scenario["text"], "precise"
    if rng.random() < (1 - persona.savvy) * 0.3:
        typed = _typo(text, rng)
        text, wording = typed, ("typo" if typed != text else wording)
    text = text.format(**values)
    pick = {k: v.format(**values) for k, v in (scenario.get("pick") or {}).items()}
    if "market" in pick:
        pick["market_id"] = market_id
    precise = scenario["text"].format(**values)
    return {**scenario, "text": text, "precise": precise, "wording": wording, "values": values, "pick": pick}


def _typo(text: str, rng: random.Random) -> str:
    words = [w for w in TYPOS if w in text]
    if not words:
        return text
    w = rng.choice(words)
    return text.replace(w, TYPOS[w], 1)
