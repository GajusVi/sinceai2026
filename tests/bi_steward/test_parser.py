from steward.query_parser import RuleBasedParser, parse_period


def test_main_demo_question(steward):
    parsed = RuleBasedParser(steward.catalog).parse("Xarelto net sales in Germany by quarter for Q3")

    assert parsed.metrics == ["net_sales"]
    assert parsed.filters == {"product": "P-XAR", "market": "DE"}
    assert parsed.dimensions == ["quarter"]
    assert parsed.period == "Q3"


def test_longest_synonym_wins(steward):
    parsed = RuleBasedParser(steward.catalog).parse("Net sales growth for Nubeqa")

    assert parsed.metrics == ["net_sales_growth"]  # not net_sales: the longer synonym wins


def test_filtered_dimension_is_not_a_breakdown(steward):
    parsed = RuleBasedParser(steward.catalog).parse("Margin in the EMEA region")

    assert parsed.filters == {"region": "EMEA"}
    assert "region" not in parsed.dimensions


def test_period_formats():
    assert parse_period("for Q3 2026") == "2026-Q3"
    assert parse_period("for the year") is None


def test_russian_periods_are_understood():
    assert parse_period("за третий квартал") == "Q3"
    assert parse_period("за 2-й квартал") == "Q2"


REQ_0001 = "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."


def test_unrecognised_terms_are_kept_not_dropped(steward):
    parsed = RuleBasedParser(steward.catalog).parse("Show the zorblax index for Xarelto in Germany")

    assert {"zorblax", "index"} <= set(parsed.unmapped_terms) and parsed.metrics == []
    assert steward.ask("Show the zorblax index for Xarelto in Germany").decision.verdict.value not in (
        "REUSE", "EXTEND", "CREATE", "CONSOLIDATE")


def test_req_0001_names_all_three_kpis(steward):
    parsed = RuleBasedParser(steward.catalog).parse(REQ_0001)

    assert parsed.metrics == ["net_sales_growth", "forecast_variance", "market_access_coverage"]
    assert parsed.filters["product"] == "P-NUB" and "dashboard" not in parsed.unmapped_terms


def test_covered_words_are_not_unmapped(steward):
    parsed = RuleBasedParser(steward.catalog).parse("Xarelto net sales in Germany by quarter for Q3")

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
