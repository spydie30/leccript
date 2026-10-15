"""Answer generation and backend-authoritative citation builder.

Design Rules enforced:
- Citations are built strictly by the backend from chunk/cue IDs, NEVER by the LLM.
- Timestamps are seconds from recording start and map directly to video offsets.
- Verbatim quotes come directly from the `cues` table.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.parser import format_ts
from app.models import Cue
from app.retrieval.search import hybrid_search

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

_CITATION_ID_RE = re.compile(r"\[(?:Source\s+|Chunk\s+|#)?(\d+)\]", re.IGNORECASE)
_PROFESSOR_INTENT_RE = re.compile(r"\b(?:prof(?:essor)?|lecturer|instructor|sir|teacher)\b", re.IGNORECASE)


@dataclass
class VerbatimCue:
    idx: int
    start_s: float
    end_s: float
    timestamp: str
    speaker: str | None
    is_lecturer: bool
    text: str


@dataclass
class Citation:
    chunk_id: int
    lecture_id: int
    professor: str
    course_code: str
    course_title: str | None
    lecture_date: str
    lecture_title: str | None
    start_s: float
    end_s: float
    timestamp_start: str
    timestamp_end: str
    recording_url: str | None
    jump_url: str | None
    lecturer_share: float
    label: str
    cues: list[VerbatimCue]


def _build_jump_url(recording_url: str | None, start_s: float) -> str | None:
    if not recording_url:
        return None
    offset = int(start_s)
    sep = "&" if "?" in recording_url else "?"
    return f"{recording_url}{sep}t={offset}"


def build_citation_from_chunk(db: Session, chunk_dict: dict) -> Citation:
    """Construct an authoritative Citation object from DB Chunk metadata and verbatim Cue rows."""
    cues_stmt = (
        select(Cue)
        .where(
            Cue.lecture_id == chunk_dict["lecture_id"],
            Cue.idx >= chunk_dict["first_cue"],
            Cue.idx <= chunk_dict["last_cue"],
        )
        .order_by(Cue.idx.asc())
    )
    cue_rows = db.scalars(cues_stmt).all()
    verbatim_cues = [
        VerbatimCue(
            idx=c.idx,
            start_s=c.start_s,
            end_s=c.end_s,
            timestamp=format_ts(c.start_s),
            speaker=c.speaker,
            is_lecturer=c.is_lecturer,
            text=c.text,
        )
        for c in cue_rows
    ]

    ts_start = format_ts(chunk_dict["start_s"])
    ts_end = format_ts(chunk_dict["end_s"])
    date_str = (
        chunk_dict["lecture_date"].isoformat()
        if hasattr(chunk_dict["lecture_date"], "isoformat")
        else str(chunk_dict["lecture_date"])
    )
    label = f"Prof. {chunk_dict['professor']} · {chunk_dict['course_code']} · {date_str} @ {ts_start}"

    return Citation(
        chunk_id=chunk_dict["chunk_id"],
        lecture_id=chunk_dict["lecture_id"],
        professor=chunk_dict["professor"],
        course_code=chunk_dict["course_code"],
        course_title=chunk_dict.get("course_title"),
        lecture_date=date_str,
        lecture_title=chunk_dict.get("lecture_title"),
        start_s=chunk_dict["start_s"],
        end_s=chunk_dict["end_s"],
        timestamp_start=ts_start,
        timestamp_end=ts_end,
        recording_url=chunk_dict.get("recording_url"),
        jump_url=_build_jump_url(chunk_dict.get("recording_url"), chunk_dict["start_s"]),
        lecturer_share=round(float(chunk_dict["lecturer_share"]), 3),
        label=label,
        cues=verbatim_cues,
    )


def _extractive_synthesis(query: str, hits: list[dict], citations: list[Citation]) -> dict:
    """Grounded extractive answer builder used when no external LLM API key is configured."""
    top = hits[0]
    top_cit = citations[0]
    intro = (
        f"From Prof. {top['professor']}'s {top['course_code']} lecture on "
        f"{top_cit.lecture_date} ({top_cit.timestamp_start}–{top_cit.timestamp_end}) [{top['chunk_id']}]:"
    )
    points: list[str] = []
    cited_ids: list[int] = []

    for hit, cit in zip(hits[:3], citations[:3]):
        lecturer_cues = [c for c in cit.cues if c.is_lecturer] or cit.cues
        if lecturer_cues:
            snippet = " ".join(c.text for c in lecturer_cues[:2]).strip()
            ts = lecturer_cues[0].timestamp
        else:
            snippet = hit["normalized_text"]
            ts = cit.timestamp_start
        points.append(f"[{hit['chunk_id']}] ({ts}) \"{snippet}\"")
        cited_ids.append(hit["chunk_id"])

    return {
        "intro": intro,
        "points": points,
        "cited_chunk_ids": cited_ids,
    }


def _llm_synthesis(query: str, hits: list[dict]) -> dict | None:
    if not OPENAI_API_KEY:
        return None

    context_blocks = []
    for h in hits:
        context_blocks.append(
            f"[Chunk {h['chunk_id']}]\n"
            f"Raw Transcript:\n{h['raw_text']}"
        )
    system_prompt = (
        "You are Leccript, a precise university study assistant. "
        "Answer the student's question ONLY using the provided transcript chunks. "
        "Never invent professor names, dates, or timestamps—cite sources strictly by their numeric "
        "chunk ID in brackets like [12]. Return JSON with keys: "
        '{"intro": "1-2 sentence direct answer with [chunk_id]", '
        '"points": ["bullet 1 with [chunk_id]", "bullet 2 with [chunk_id]"], '
        '"cited_chunk_ids": [12]}'
    )
    user_prompt = f"Question: {query}\n\nTranscript Chunks:\n" + "\n\n".join(context_blocks)

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": LLM_MODEL,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception:
        return None


def answer_question(
    db: Session,
    query: str,
    course_code: str | None = None,
    professor: str | None = None,
    lecturer_only: bool = False,
    top_k: int = 4,
) -> dict:
    """Run hybrid retrieval, synthesize a grounded response, and attach backend-built citations."""
    # Automatically apply lecturer_share >= 0.8 filter if user asks what the professor said
    min_share = 0.8 if (lecturer_only or _PROFESSOR_INTENT_RE.search(query)) else 0.0

    hits = hybrid_search(
        db=db,
        query=query,
        top_k=top_k,
        course_code=course_code,
        professor=professor,
        min_lecturer_share=min_share,
    )
    # Fallback without strict lecturer_share if no chunk crossed 0.8
    if not hits and min_share > 0:
        hits = hybrid_search(
            db=db,
            query=query,
            top_k=top_k,
            course_code=course_code,
            professor=professor,
            min_lecturer_share=0.0,
        )

    if not hits:
        return {
            "intro": "No matching lecture segments were found in your library yet.",
            "points": [
                "Upload a Zoom (.txt), WebVTT (.vtt), or SRT (.srt) transcript using the attachment icon or the Lecture notes drawer.",
                "Filename format: <professor>-<YYYY-MM-DD>-<subject_code>.txt (or fill in the metadata fields on upload).",
            ],
            "source": "No lecture matched",
            "citations": [],
        }

    citations_by_id: dict[int, Citation] = {}
    ordered_citations: list[Citation] = []
    for h in hits:
        cit = build_citation_from_chunk(db, h)
        citations_by_id[cit.chunk_id] = cit
        ordered_citations.append(cit)

    llm_out = _llm_synthesis(query, hits)
    if not llm_out:
        llm_out = _extractive_synthesis(query, hits, ordered_citations)

    intro = llm_out.get("intro") or ""
    points = llm_out.get("points") or []

    # Extract chunk IDs referenced by LLM/extractive output and validate against retrieved chunks
    referenced_ids: list[int] = []
    for raw_id in llm_out.get("cited_chunk_ids", []):
        try:
            cid = int(raw_id)
            if cid in citations_by_id and cid not in referenced_ids:
                referenced_ids.append(cid)
        except (TypeError, ValueError):
            continue

    for text_part in [intro, *points]:
        for match in _CITATION_ID_RE.findall(str(text_part)):
            cid = int(match)
            if cid in citations_by_id and cid not in referenced_ids:
                referenced_ids.append(cid)

    final_citations = (
        [citations_by_id[cid] for cid in referenced_ids]
        if referenced_ids
        else ordered_citations[:2]
    )

    primary_source = final_citations[0].label if final_citations else "Lecture Library"

    return {
        "intro": intro,
        "points": points,
        "source": primary_source,
        "citations": [asdict(c) for c in final_citations],
    }