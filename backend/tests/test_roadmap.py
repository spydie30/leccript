from datetime import date

from app.retrieval.embeddings import EMBED_DIM, embed_query, embed_texts
from app.retrieval.reranker import rerank_candidates
from app.retrieval.search import compute_rrf


def test_deterministic_embeddings_dimension_and_similarity():
    vecs = embed_texts([
        "N3 is the image segmentation problem in computer vision.",
        "Image segmentation partitions pixels into regions.",
        "Gradient descent updates parameters using learning rate.",
    ])
    assert len(vecs) == 3
    assert all(len(v) == EMBED_DIM for v in vecs)

    # Cosine similarity (vectors are unit-normalized)
    sim_related = sum(a * b for a, b in zip(vecs[0], vecs[1]))
    sim_unrelated = sum(a * b for a, b in zip(vecs[0], vecs[2]))
    assert sim_related > sim_unrelated


def test_rrf_fusion_prioritizes_consensus_hits():
    # Chunk 42 appears near top of both vector and FTS rankings
    vec_ids = [10, 42, 19, 33]
    fts_ids = [42, 88, 10, 71]
    scores = compute_rrf(vec_ids, fts_ids, k=60)
    ranked = sorted(scores, key=scores.get, reverse=True)
    assert ranked[0] == 42
    assert ranked[1] == 10


def test_reranker_boosts_query_match_and_lecturer_share():
    candidates = [
        {
            "chunk_id": 1,
            "normalized_text": "Sir is it N3 segmentation problem now",
            "lecturer_share": 0.1,
            "rrf_score": 0.03,
        },
        {
            "chunk_id": 2,
            "normalized_text": "Yes N3 is the segmentation problem in deep learning",
            "lecturer_share": 1.0,
            "rrf_score": 0.03,
        },
    ]
    ranked = rerank_candidates("What is the N3 segmentation problem?", candidates, top_k=2)
    assert ranked[0]["chunk_id"] == 2
    assert ranked[0]["rerank_score"] > ranked[1]["rerank_score"]