"""CLI tool to ingest one or more transcript files or directories.

Usage:
    python -m app.ingest.cli path/to/utkarsh_khare-2026-09-14-DS101.txt
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from app.db import SessionLocal, init_db
from app.ingest.service import ingest_transcript


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Zoom/VTT/SRT lecture transcripts.")
    parser.add_argument("paths", nargs="+", help="Transcript files or directories to ingest")
    parser.add_argument("--professor", help="Override professor name")
    parser.add_argument("--course", help="Override subject/course code")
    parser.add_argument("--course-title", help="Optional course title")
    parser.add_argument("--date", help="Override lecture date (YYYY-MM-DD)")
    parser.add_argument("--title", help="Optional lecture title")
    parser.add_argument("--recording-url", help="Optional video URL for timestamp jumping")
    args = parser.parse_args()

    init_db()
    parsed_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None

    files: list[Path] = []
    for p_str in args.paths:
        p = Path(p_str)
        if p.is_dir():
            for ext in ("*.txt", "*.vtt", "*.srt"):
                files.extend(sorted(p.glob(ext)))
        elif p.is_file():
            files.append(p)

    with SessionLocal() as db:
        for file_path in files:
            res = ingest_transcript(
                db=db,
                raw_bytes=file_path.read_bytes(),
                filename=file_path.name,
                professor_name=args.professor,
                course_code=args.course,
                course_title=args.course_title,
                lecture_date=parsed_date,
                title=args.title,
                recording_url=args.recording_url,
            )
            status = "SKIPPED (idempotent)" if res.already_existed else "INGESTED"
            print(
                f"[{status}] lecture_id={res.lecture_id} | {res.course_code} | "
                f"Prof. {res.professor} (speaker={res.lecturer_speaker!r}) | "
                f"{res.lecture_date} | {res.cues_count} cues -> {res.chunks_count} chunks"
            )


if __name__ == "__main__":
    main()