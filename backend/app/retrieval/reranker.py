"""Reranker for hybrid RRF candidates."""
from __future__ import annotations

import os
import re
from typing import TypeVar

T = TypeVar("T")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_cross_encoder = None
CROSS_ENCODER_MODEL = os.getenv("CROSS_ENCODER_MODEL", "")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def score_pair(query: str, passage: str, lecturer_share: float = 1.0) -> float:
    """Compute relevance score combining exact token coverage, bigram overlap, and lecturer share."""
    q_tokens = _tokens(query)
    p_tokens = _tokens(passage)
    if not q_tokens or not p_tokens:
        return 0.0

    q_set = set(q_tokens)
    p_set = set(p_tokens)
    token_overlap = len(q_set & p_set) / len(q_set)

    q_bigrams = {f"{q_tokens[i]} {q_tokens[i+1]}" for i in range(len(q_tokens) - 1)}
    p_bigrams = {f"{p_tokens[i]} {p_tokens[i+1]}" for i in range(len(p_tokens) - 1)}
    bigram_overlap = (len(q_bigrams & p_bigrams) / len(q_bigrams)) if q_bigrams else 0.0

    lecturer_bonus = 0.1 * float(lecturer_share)
    return 0.65 * token_overlap + 0.25 * bigram_overlap + lecturer_bonus


def rerank_candidates(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """Re-score RRF candidates using an optional CrossEncoder or lexical+semantic fusion."""
    if not candidates:
        return []

    if CROSS_ENCODER_MODEL:
        global _cross_encoder
        if _cross_encoder is None:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
        pairs = [(query, c["normalized_text"]) for c in candidates]
        ce_scores = _cross_encoder.predict(pairs)
        for c, s in zip(candidates, ce_scores):
            c["rerank_score"] = float(s) + 0.15 * float(c.get("rrf_score", 0.0))
    else:
        for c in candidates:
            lex_score = score_pair(
                query=query,
                passage=c["normalized_text"],
                lecturer_share=c.get("lecturer_share", 1.0),
            )
            c["rerank_score"] = 0.6 * lex_score + 20.0 * float(c.get("rrf_score", 0.0))

    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    return ranked[:top_k]