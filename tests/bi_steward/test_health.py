from steward.decision.signals import trust


def test_duplicates_point_to_the_trusted_original(steward):
    pairs = steward.health().duplicates
    a, as_of = steward.catalog.artifacts, steward.as_of

    assert pairs
    assert all(trust(a[p.keep_id], as_of) >= trust(a[p.duplicate_id], as_of) for p in pairs)
    assert not {p.keep_id for p in pairs} & {p.duplicate_id for p in pairs}  # a copy of a copy points at the original


def test_retire_candidates(steward):
    retire_ids = {r.artifact_id for r in steward.health().retire}

    assert "AST-0009" in retire_ids  # 0.3 users a month, inactive owner
    assert "AST-0191" not in retire_ids  # the labelled REUSE answer for Xarelto net sales in Germany
