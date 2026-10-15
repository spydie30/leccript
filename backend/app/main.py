from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db, init_db
from app.ingest.parser import format_ts
from app.ingest.service import ingest_transcript
from app.models import Chunk, Course, Cue, Lecture, Professor
from app.rag.engine import answer_question, build_citation_from_chunk
from app.retrieval.search import hybrid_search


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        init_db()
    except Exception:
        # Allows unit tests without a live Postgres instance to import `app`
        pass
    yield


app = FastAPI(title="Lecture RAG", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    course_code: str | None = None
    professor: str | None = None
    lecturer_only: bool = False
    top_k: int = Field(default=4, ge=1, le=12)


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/lectures")
def list_lectures(db: Session = Depends(get_db)):
    stmt = (
        select(
            Lecture,
            Professor.name.label("professor_name"),
            Course.code.label("course_code"),
            Course.title.label("course_title"),
            func.count(func.distinct(Cue.id)).label("cues_count"),
            func.count(func.distinct(Chunk.id)).label("chunks_count"),
        )
        .join(Professor, Lecture.professor_id == Professor.id)
        .join(Course, Lecture.course_id == Course.id)
        .outerjoin(Cue, Cue.lecture_id == Lecture.id)
        .outerjoin(Chunk, Chunk.lecture_id == Lecture.id)
        .group_by(Lecture.id, Professor.name, Course.code, Course.title)
        .order_by(Lecture.lecture_date.desc(), Lecture.id.desc())
    )
    rows = db.execute(stmt).all()
    return [
        {
            "id": lec.id,
            "title": lec.title,
            "professor": prof_name,
            "course_code": crs_code,
            "course_title": crs_title,
            "lecture_date": lec.lecture_date.isoformat(),
            "recording_url": lec.recording_url,
            "source_filename": lec.source_filename,
            "lecturer_speaker": lec.lecturer_speaker,
            "cues_count": cues_count,
            "chunks_count": chunks_count,
        }
        for lec, prof_name, crs_code, crs_title, cues_count, chunks_count in rows
    ]


@app.get("/api/lectures/{lecture_id}/cues")
def get_lecture_cues(
    lecture_id: int,
    start_cue: int | None = Query(default=None),
    end_cue: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    lecture = db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    stmt = select(Cue).where(Cue.lecture_id == lecture_id)
    if start_cue is not None:
        stmt = stmt.where(Cue.idx >= start_cue)
    if end_cue is not None:
        stmt = stmt.where(Cue.idx <= end_cue)
    cues = db.scalars(stmt.order_by(Cue.idx.asc())).all()

    return {
        "lecture_id": lecture.id,
        "title": lecture.title,
        "professor": lecture.professor.name,
        "course_code": lecture.course.code,
        "lecture_date": lecture.lecture_date.isoformat(),
        "recording_url": lecture.recording_url,
        "cues": [
            {
                "idx": c.idx,
                "start_s": c.start_s,
                "end_s": c.end_s,
                "timestamp": format_ts(c.start_s),
                "speaker": c.speaker,
                "is_lecturer": c.is_lecturer,
                "text": c.text,
            }
            for c in cues
        ],
    }


@app.post("/api/lectures/ingest")
async def ingest_endpoint(
    file: UploadFile = File(...),
    professor: str | None = Form(default=None),
    course_code: str | None = Form(default=None),
    course_title: str | None = Form(default=None),
    lecture_date: str | None = Form(default=None),
    title: str | None = Form(default=None),
    recording_url: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    raw_bytes = await file.read()
    parsed_date: date | None = None
    if lecture_date and lecture_date.strip():
        try:
            parsed_date = datetime.strptime(lecture_date.strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {lecture_date}") from exc

    try:
        res = ingest_transcript(
            db=db,
            raw_bytes=raw_bytes,
            filename=file.filename or "transcript.txt",
            professor_name=professor or None,
            course_code=course_code or None,
            course_title=course_title or None,
            lecture_date=parsed_date,
            title=title or None,
            recording_url=recording_url or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "lecture_id": res.lecture_id,
        "professor": res.professor,
        "course_code": res.course_code,
        "course_title": res.course_title,
        "lecture_date": res.lecture_date.isoformat(),
        "title": res.title,
        "lecturer_speaker": res.lecturer_speaker,
        "cues_count": res.cues_count,
        "chunks_count": res.chunks_count,
        "already_existed": res.already_existed,
    }


@app.delete("/api/lectures/{lecture_id}")
def delete_lecture(lecture_id: int, db: Session = Depends(get_db)):
    lecture = db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    db.delete(lecture)
    db.commit()
    return {"deleted": lecture_id}


@app.get("/api/search")
def search_endpoint(
    q: str = Query(..., min_length=1),
    course_code: str | None = Query(default=None),
    professor: str | None = Query(default=None),
    min_lecturer_share: float = Query(default=0.0, ge=0.0, le=1.0),
    top_k: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    hits = hybrid_search(
        db=db,
        query=q,
        top_k=top_k,
        course_code=course_code,
        professor=professor,
        min_lecturer_share=min_lecturer_share,
    )
    return {
        "query": q,
        "results": [
            {
                **h,
                "lecture_date": h["lecture_date"].isoformat(),
                "citation": build_citation_from_chunk(db, h),
            }
            for h in hits
        ],
    }


@app.post("/api/chat")
def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    return answer_question(
        db=db,
        query=payload.query,
        course_code=payload.course_code,
        professor=payload.professor,
        lecturer_only=payload.lecturer_only,
        top_k=payload.top_k,
    )