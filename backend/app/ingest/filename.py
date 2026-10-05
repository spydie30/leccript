"""Lecture metadata from the upload filename: <professor>-<date>-<subject_code>.txt

The real convention is configurable: swap FILENAME_RE if yours differs.
If parsing fails the caller should fall back to explicit upload-form metadata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

FILENAME_RE = re.compile(
    r"^(?P<prof>.+?)-(?P<date>\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{8})-(?P<subject>[^.]+)\.(?:txt|vtt|srt)$",
    re.IGNORECASE,
)
_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%Y%m%d")


@dataclass
class LectureMeta:
    professor: str
    lecture_date: date
    subject_code: str


def parse_filename(name: str) -> LectureMeta:
    m = FILENAME_RE.match(name.strip())
    if not m:
        raise ValueError(f"Filename does not match <prof>-<date>-<subject>: {name!r}")
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(m["date"], fmt).date()
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"Unrecognised date {m['date']!r} in {name!r}")
    prof = re.sub(r"[_\s]+", " ", m["prof"]).strip().title()
    return LectureMeta(professor=prof, lecture_date=d, subject_code=m["subject"].strip())
