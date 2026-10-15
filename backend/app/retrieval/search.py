"""Hybrid Search (Dense pgvector + Full-Text Search) with Reciprocal Rank Fusion (RRF) and Reranking."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Chunk, Course, Lecture, Professor
from .embeddings import embed_query
from .reranker import rerank_candidates


def compute_rrf(
    vector_ranked_ids: list[int],
    fts_ranked_ids: list[int],
    k: int = 60,
) -> dict[int, float]:
    """Reciprocal Rank Fusion: RRF(d) = sum_{r in R} 1 / (k + rank_r(d))."""
    scores: dict[int, float] = {}
    for rank, doc_id in enumerate(vector_ranked_ids, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    for rank, doc_id in enumerate(fts_ranked_ids, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


def hybrid_search(
    db: Session,
    query: str,
    top_k: int = 5,
    candidate_pool: int = 25,
    course_code: str | None = None,
    professor: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_lecturer_share: float = 0.0,
    rrf_k: int = 60,
) -> list[dict]:
    """Run hybrid vector + FTS search, fuse with RRF, and rerank."""
    base_stmt = (
        select(Chunk, Lecture, Professor, Course)
        .join(Lecture, Chunk.lecture_id == Lecture.id)
        .join(Professor, Lecture.professor_id == Professor.id)
        .join(Course, Lecture.course_id == Course.id)
    )

    if course_code:
        base_stmt = base_stmt.where(func.upper(Course.code) == course_code.strip().upper())
    if professor:
        base_stmt = base_stmt.where(Professor.name.ilike(f"%{professor.strip()}%"))
    if date_from:
        base_stmt = base_stmt.where(Lecture.lecture_date >= date_from)
    if date_to:
        base_stmt = base_stmt.where(Lecture.lecture_date <= date_to)
    if min_lecturer_share > 0:
        base_stmt = base_stmt.where(Chunk.lecturer_share >= min_lecturer_share)

    query_vec = embed_query(query)
    dialect = db.bind.dialect.name if db.bind else "postgresql"

    row_by_id: dict[int, tuple[Chunk, Lecture, Professor, Course]] = {}
    vector_ids: list[int] = []
    fts_ids: list[int] = []

    if dialect == "postgresql":
        # 1. Dense vector search via pgvector cosine distance
        vec_stmt = base_stmt.order_by(Chunk.embedding.cosine_distance(query_vec)).limit(candidate_pool)
        for ch, lec, prof, crs in db.execute(vec_stmt).all():
            row_by_id[ch.id] = (ch, lec, prof, crs)
            vector_ids.append(ch.id)

        # 2. Full-Text Search via PostgreSQL websearch_to_tsquery + ts_rank_cd
        ts_query = func.websearch_to_tsquery("english", query)
        fts_stmt = (
            base_stmt.where(Chunk.tsv.op("@@")(ts_query))
            .order_by(func.ts_rank_cd(Chunk.tsv, ts_query).desc())
            .limit(candidate_pool)
        )
        for ch, lec, prof, crs in db.execute(fts_stmt).all():
            row_by_id[ch.id] = (ch, lec, prof, crs)
            fts_ids.append(ch.id)
    else:
        # Fallback for SQLite unit tests
        for ch, lec, prof, crs in db.execute(base_stmt.limit(candidate_pool * 2)).all():
            row_by_id[ch.id] = (ch, lec, prof, crs)
            vector_ids.append(ch.id)

    if not row_by_id:
        return []

    rrf_scores = compute_rrf(vector_ids, fts_ids, k=rrf_k)
    candidates: list[dict] = []
    for chunk_id, (ch, lec, prof, crs) in row_by_id.items():
        candidates.append({
            "chunk_id": ch.id,
            "lecture_id": lec.id,
            "chunk_index": ch.chunk_index,
            "professor": prof.name,
            "course_code": crs.code,
            "course_title": crs.title,
            "lecture_date": lec.lecture_date,
            "lecture_title": lec.title,
            "recording_url": lec.recording_url,
            "start_s": ch.start_s,
            "end_s": ch.end_s,
            "first_cue": ch.first_cue,
            "last_cue": ch.last_cue,
            "speakers": ch.speakers,
            "lecturer_share": ch.lecturer_share,
            "raw_text": ch.raw_text,
            "normalized_text": ch.normalized_text,
            "rrf_score": rrf_scores.get(chunk_id, 0.0),
        })

    return rerank_candidates(query=query, candidates=candidates, top_k=top_k)