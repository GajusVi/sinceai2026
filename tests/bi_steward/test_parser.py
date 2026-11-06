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
