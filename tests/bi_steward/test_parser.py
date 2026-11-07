from steward.query_parser import RuleBasedParser, parse_period


def test_main_demo_question(steward):
    parsed = RuleBasedParser(steward.catalog).parse("What is herbicide revenue in LATAM vs plan for Q3?")

    assert parsed.metrics == ["net_revenue", "plan_revenue"]
    assert parsed.filters == {"product_line": "herbicides", "region": "LATAM"}
    assert parsed.dimensions == ["quarter"]
    assert parsed.period == "Q3"


def test_longest_synonym_wins(steward):
    parsed = RuleBasedParser(steward.catalog).parse("Gross revenue by country")

    assert parsed.metrics == ["gross_revenue"]
    assert parsed.dimensions == ["country"]


def test_filtered_dimension_is_not_a_breakdown(steward):
    parsed = RuleBasedParser(steward.catalog).parse("Margin in the EMEA region")

    assert parsed.filters == {"region": "EMEA"}
    assert "region" not in parsed.dimensions


def test_period_formats():
    assert parse_period("for Q3 2026") == "2026-Q3"
    assert parse_period("for the year") is None


def test_russian_input_is_understood(steward):
    """The dictionary also holds Russian synonyms, so local teams can ask in Russian."""
    parsed = RuleBasedParser(steward.catalog).parse("Какая выручка гербицидов в LATAM против плана за Q3?")

    assert parsed.metrics == ["net_revenue", "plan_revenue"]
    assert parsed.filters == {"product_line": "herbicides", "region": "LATAM"}
    assert parse_period("за третий квартал") == "Q3"
    assert parse_period("за 2-й квартал") == "Q2"


REQ_0001 = "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."


def test_unrecognised_terms_are_kept_not_dropped(steward):
    parsed = RuleBasedParser(steward.catalog).parse(REQ_0001)

    assert {"Nubeqa", "growth", "forecast", "variance", "market", "access"} <= set(parsed.unmapped_terms)
    assert "dashboard" not in parsed.unmapped_terms


def test_req_0001_is_clarify_not_reuse(steward):
    decision = steward.ask(REQ_0001).decision

    assert decision.verdict.value == "CLARIFY"
    assert any(e.severity == "blocker" and e.rule_id is None for e in decision.evidence)
    assert "Nubeqa" in " ".join(decision.reasons)


def test_covered_words_are_not_unmapped(steward):
    parsed = RuleBasedParser(steward.catalog).parse("What is herbicide revenue in LATAM vs plan for Q3?")

    assert parsed.unmapped_terms == []


def test_ambiguous_phrase_is_not_linked_to_a_metric(steward):
    decision = steward.ask("What were first sales in Germany?").decision
    parsed = RuleBasedParser(steward.catalog).parse("What were first sales in Germany?")

    assert parsed.metrics == []
    assert "first sales" in parsed.unmapped_terms
    assert decision.verdict.value == "CLARIFY"


def test_filler_words_do_not_force_clarify_and_worldwide_means_global(steward):
    parsed = RuleBasedParser(steward.catalog).parse("Actually just net revenue by region, really quickly please")
    assert parsed.unmapped_terms == []
    from steward.linking import asks_global

    assert asks_global("Net sales for Kerendia worldwide") and asks_global("globally") and not asks_global("Net sales in Germany")
