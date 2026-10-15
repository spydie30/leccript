"""End-to-end transcript ingestion into PostgreSQL (professors, courses, lectures, cues, chunks)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk as ChunkModel, Course, Cue as CueModel, Lecture, Professor
from app.retrieval.embeddings import embed_texts
from .chunker import chunk_cues, identify_lecturer
from .filename import parse_filename
from .parser import parse_transcript


@dataclass
class IngestResult:
    lecture_id: int
    professor: str
    course_code: str
    course_title: str | None
    lecture_date: date
    title: str | None
    lecturer_speaker: str | None
    cues_count: int
    chunks_count: int
    already_existed: bool


def ingest_transcript(
    db: Session,
    raw_bytes: bytes,
    filename: str,
    professor_name: str | None = None,
    course_code: str | None = None,
    course_title: str | None = None,
    lecture_date: date | None = None,
    title: str | None = None,
    recording_url: str | None = None,
) -> IngestResult:
    """Idempotently parse, chunk, embed, and persist a lecture transcript."""
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    existing = db.scalar(select(Lecture).where(Lecture.content_sha256 == sha256))
    if existing:
        cues_count = db.query(CueModel).filter(CueModel.lecture_id == existing.id).count()
        chunks_count = db.query(ChunkModel).filter(ChunkModel.lecture_id == existing.id).count()
        return IngestResult(
            lecture_id=existing.id,
            professor=existing.professor.name,
            course_code=existing.course.code,
            course_title=existing.course.title,
            lecture_date=existing.lecture_date,
            title=existing.title,
            lecturer_speaker=existing.lecturer_speaker,
            cues_count=cues_count,
            chunks_count=chunks_count,
            already_existed=True,
        )

    # Extract fallback metadata from filename if any required field is omitted
    if not (professor_name and course_code and lecture_date):
        meta = parse_filename(filename)
        professor_name = professor_name or meta.professor
        course_code = course_code or meta.subject_code
        lecture_date = lecture_date or meta.lecture_date

    professor_name = professor_name.strip().title()
    course_code = course_code.strip().upper()

    cues = parse_transcript(raw_bytes)
    if not cues:
        raise ValueError(f"No valid timestamped cues found in {filename!r}")

    # Design Rule 1: Lecturer identity comes from upload metadata hint, not speaker labels alone
    lecturer_speaker = identify_lecturer(cues, hint=professor_name)
    chunks = chunk_cues(cues, lecturer=lecturer_speaker)

    prof = db.scalar(select(Professor).where(Professor.name == professor_name))
    if not prof:
        prof = Professor(name=professor_name)
        db.add(prof)
        db.flush()

    course = db.scalar(select(Course).where(Course.code == course_code))
    if not course:
        course = Course(code=course_code, title=course_title or course_code)
        db.add(course)
        db.flush()
    elif course_title and not course.title:
        course.title = course_title

    lecture = Lecture(
        professor_id=prof.id,
        course_id=course.id,
        lecture_date=lecture_date,
        title=title or f"{course_code} Lecture ({lecture_date.isoformat()})",
        recording_url=recording_url,
        source_filename=filename,
        content_sha256=sha256,
        lecturer_speaker=lecturer_speaker,
    )
    db.add(lecture)
    db.flush()

    cue_models = [
        CueModel(
            lecture_id=lecture.id,
            idx=c.idx,
            start_s=c.start,
            end_s=c.end,
            speaker=c.speaker,
            is_lecturer=(c.speaker == lecturer_speaker) if lecturer_speaker else True,
            text=c.text,
        )
        for c in cues
    ]
    db.add_all(cue_models)

    vectors = embed_texts([ch.normalized_text for ch in chunks])
    chunk_models = [
        ChunkModel(
            lecture_id=lecture.id,
            chunk_index=ch.index,
            start_s=ch.start,
            end_s=ch.end,
            first_cue=ch.first_cue,
            last_cue=ch.last_cue,
            speakers=ch.speakers,
            lecturer_share=ch.lecturer_share,
            raw_text=ch.raw_text,
            normalized_text=ch.normalized_text,
            embedding=vec,
        )
        for ch, vec in zip(chunks, vectors)
    ]
    db.add_all(chunk_models)
    db.commit()

    return IngestResult(
        lecture_id=lecture.id,
        professor=prof.name,
        course_code=course.code,
        course_title=course.title,
        lecture_date=lecture.lecture_date,
        title=lecture.title,
        lecturer_speaker=lecturer_speaker,
        cues_count=len(cue_models),
        chunks_count=len(chunk_models),
        already_existed=False,
    )