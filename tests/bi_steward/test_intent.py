from steward.intent import Intent


def _full(**kw) -> Intent:
    base = dict(
        products=["Nubeqa"],
        markets=["DE"],
        metric_ids=["net_sales"],
        decision_supported="monthly sales review",
        confidence={"products": 0.9, "markets": 0.9, "metric_ids": 0.8, "decision_supported": 0.75},
        text="Nubeqa net sales in Germany",
    )
    base.update(kw)
    return Intent(**base)


def test_complete_intent_stops():
    assert _full().is_complete()
    assert _full().should_stop(0)


def test_low_confidence_or_missing_field_keeps_asking():
    assert _full(
        confidence={"products": 0.9, "markets": 0.9, "metric_ids": 0.5, "decision_supported": 0.9}
    ).missing() == ["metric_ids"]
    assert Intent().missing() == ["products", "markets", "metric_ids", "decision_supported"]
    assert not Intent().should_stop(4)
    assert Intent().should_stop(5)


def test_region_counts_as_markets():
    intent = _full(
        markets=[],
        regions=["EMEA"],
        confidence={"products": 0.9, "regions": 0.8, "metric_ids": 0.9, "decision_supported": 0.9},
    )
    assert intent.is_complete()


def test_expert_mode_asks_only_on_conflict():
    assert Intent(mode="expert").should_stop(0)
    assert not Intent(mode="expert", conflicts=["text says Nubeqa, metadata says Beyonttra"]).should_stop(0)


def test_to_parsed_question_adapter():
    q = _full(regions=["EMEA"], markets=[]).to_parsed_question()
    assert q.metrics == ["net_sales"]
    assert q.filters == {"product": "Nubeqa", "region": "EMEA"}
    assert q.dimensions == []  # a time breakdown is required only when the text asks for one (audit F1)
    assert _full(products=["Nubeqa", "Xarelto"]).to_parsed_question().dimensions == ["product"]
    monthly = _full(text="Nubeqa net sales by month", products=["Nubeqa", "Xarelto"])
    assert monthly.to_parsed_question().dimensions == ["product", "month"]
