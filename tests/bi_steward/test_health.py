def test_duplicates_point_to_the_trusted_original(steward):
    pairs = {(p.keep_id, p.duplicate_id) for p in steward.health().duplicates}

    assert ("fin-margin-001", "fin-margin-002") in pairs
    assert ("fin-margin-001", "fin-margin-003") in pairs
    assert ("fin-rev-001", "fin-rev-002") in pairs


def test_retire_candidates(steward):
    retire_ids = {r.artifact_id for r in steward.health().retire}

    assert {"fin-margin-002", "fin-margin-003", "fin-rev-002"} <= retire_ids
    assert "fin-rev-001" not in retire_ids
    assert "fin-margin-001" not in retire_ids
