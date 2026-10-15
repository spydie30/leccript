"""Embedding service supporting OpenAI-compatible APIs, SentenceTransformers, and a deterministic 1024-d fallback."""
from __future__ import annotations

import hashlib
import math
import os
import re

import httpx

EMBED_DIM = int(os.getenv("EMBED_DIM", "1024"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-large")
LOCAL_ST_MODEL = os.getenv("LOCAL_ST_MODEL", "")

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_st_model = None


def _deterministic_hash_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic feature-hashing embedder (unigrams + bigrams + char trigrams)
    so hybrid search and pgvector work offline and in CI without external API keys.
    """
    vec = [0.0] * dim
    tokens = _TOKEN_RE.findall(text.lower())
    if not tokens:
        return vec

    features: list[tuple[str, float]] = []
    for tok in tokens:
        features.append((f"w:{tok}", 1.0))
        if len(tok) >= 4:
            for i in range(len(tok) - 2):
                features.append((f"c:{tok[i:i+3]}", 0.35))
    for i in range(len(tokens) - 1):
        features.append((f"b:{tokens[i]}_{tokens[i+1]}", 0.75))

    for feat, weight in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        h = int.from_bytes(digest, "little")
        idx = h % dim
        sign = 1.0 if ((h >> 32) & 1) == 0 else -1.0
        vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    if OPENAI_API_KEY:
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{OPENAI_BASE_URL.rstrip('/')}/embeddings",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={"input": texts, "model": EMBED_MODEL, "dimensions": EMBED_DIM},
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                return [item["embedding"][:EMBED_DIM] for item in sorted(data, key=lambda x: x["index"])]
        except Exception:
            pass

    if LOCAL_ST_MODEL:
        global _st_model
        if _st_model is None:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer(LOCAL_ST_MODEL)
        encoded = _st_model.encode(texts, normalize_embeddings=True)
        return [list(map(float, row))[:EMBED_DIM] for row in encoded]

    return [_deterministic_hash_embed(t, EMBED_DIM) for t in texts]


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]