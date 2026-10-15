"""Initial schema for professors, courses, lectures, cues, and chunks.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-16
"""
from __future__ import annotations

import os
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

EMBED_DIM = int(os.getenv("EMBED_DIM", "1024"))


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "professors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("title", sa.String(length=300), nullable=True),
    )

    op.create_table(
        "lectures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("professor_id", sa.Integer(), sa.ForeignKey("professors.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("lecture_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("source_filename", sa.String(length=300), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("lecturer_speaker", sa.String(length=200), nullable=True),
    )

    op.create_table(
        "cues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lecture_id", sa.Integer(), sa.ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("start_s", sa.Float(), nullable=False),
        sa.Column("end_s", sa.Float(), nullable=False),
        sa.Column("speaker", sa.String(length=200), nullable=True),
        sa.Column("is_lecturer", sa.Boolean(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.UniqueConstraint("lecture_id", "idx"),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lecture_id", sa.Integer(), sa.ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("start_s", sa.Float(), nullable=False),
        sa.Column("end_s", sa.Float(), nullable=False),
        sa.Column("first_cue", sa.Integer(), nullable=False),
        sa.Column("last_cue", sa.Integer(), nullable=False),
        sa.Column("speakers", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("lecturer_share", sa.Float(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIM), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', normalized_text)", persisted=True),
        ),
        sa.UniqueConstraint("lecture_id", "chunk_index"),
    )

    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    op.create_index(
        "ix_chunks_embedding",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_embedding", table_name="chunks")
    op.drop_index("ix_chunks_tsv", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("cues")
    op.drop_table("lectures")
    op.drop_table("courses")
    op.drop_table("professors")