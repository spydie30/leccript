"""PostgreSQL schema: professors, courses, lectures, cues (exact quotes), chunks (retrieval)."""
from __future__ import annotations

import os
from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean, Computed, Date, Float, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBED_DIM = int(os.getenv("EMBED_DIM", "1024"))


class Base(DeclarativeBase):
    pass


class Professor(Base):
    __tablename__ = "professors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)   # subject_code from filename
    title: Mapped[str | None] = mapped_column(String(300))


class Lecture(Base):
    __tablename__ = "lectures"
    id: Mapped[int] = mapped_column(primary_key=True)
    professor_id: Mapped[int] = mapped_column(ForeignKey("professors.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    lecture_date: Mapped[date] = mapped_column(Date)
    title: Mapped[str | None] = mapped_column(String(300))
    recording_url: Mapped[str | None] = mapped_column(Text)       # for "jump to timestamp"
    source_filename: Mapped[str] = mapped_column(String(300))
    content_sha256: Mapped[str] = mapped_column(String(64), unique=True)  # idempotent re-upload
    lecturer_speaker: Mapped[str | None] = mapped_column(String(200))     # label used in transcript
    professor: Mapped[Professor] = relationship()
    course: Mapped[Course] = relationship()


class Cue(Base):
    """Verbatim transcript lines. The exact-quote engine reads from here."""
    __tablename__ = "cues"
    id: Mapped[int] = mapped_column(primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"))
    idx: Mapped[int] = mapped_column(Integer)
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    speaker: Mapped[str | None] = mapped_column(String(200))
    is_lecturer: Mapped[bool] = mapped_column(Boolean)
    text: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("lecture_id", "idx"),)


class Chunk(Base):
    """Retrieval unit: ~60-120 s of consecutive cues."""
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)          # = the Source ID used in citations
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    first_cue: Mapped[int] = mapped_column(Integer)
    last_cue: Mapped[int] = mapped_column(Integer)
    speakers: Mapped[list[str]] = mapped_column(ARRAY(String))
    lecturer_share: Mapped[float] = mapped_column(Float)      # 0-1; filter >=0.8 for "what the professor said"
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('english', normalized_text)", persisted=True))
    __table_args__ = (
        UniqueConstraint("lecture_id", "chunk_index"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding", "embedding", postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
