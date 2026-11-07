from steward.decision.minhash import MinHashCalculator
from steward.search.rrf import reciprocal_rank_fusion


def test_rrf_rewards_agreement_between_rankings():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a"], ["b"]])

    assert [doc_id for doc_id, _ in fused] == ["b", "a", "c"]


def test_minhash_identical_and_different_texts():
    minhash = MinHashCalculator(shingle_size=3)
    a = minhash.compute_signature("gross margin by product line region and quarter")
    b = minhash.compute_signature("gross margin by product line region and quarter")
    c = minhash.compute_signature("clinical trial enrollment by therapeutic area")

    assert minhash.estimate_jaccard(a, b) == 1.0
    assert minhash.estimate_jaccard(a, c) < 0.2


def test_main_question_finds_the_labelled_report_first(steward):
    question = steward.parser.parse("Xarelto net sales in Germany")
    hits = steward.search.search(question)

    assert "AST-0191" in [h.artifact.id for h in hits[:3]]