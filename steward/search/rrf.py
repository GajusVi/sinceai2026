from __future__ import annotations

RRF_K = 60


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    k: int = RRF_K,
    weights: list[float] | None = None,
) -> list[tuple[str, float]]:
    """score(d) = sum_i w_i / (k + rank_i(d)), rank is 1-based. Documents missing from a list get nothing from it."""
    weights = weights or [1.0] * len(rankings)
    scores: dict[str, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
