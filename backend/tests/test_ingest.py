import os
from datetime import date

import pytest

from app.ingest.chunker import chunk_cues, identify_lecturer
from app.ingest.filename import parse_filename
from app.ingest.parser import fix_mojibake, format_ts, parse_transcript

SAMPLE = """1
00:00:35.220 --> 00:00:51.299
Utkarsh Khare: Okay, so guys, let's start. We covered N2â€¦ right.

2
00:00:52.490 --> 00:00:55.779
DEEPAK SHARMA: Sir, is it N3 now?

3
00:00:56.000 --> 00:01:10.000
Utkarsh Khare: Yes, N3 is the segmentation problem.
"""


def test_parse_basic():
    cues = parse_transcript(SAMPLE)
    assert [c.idx for c in cues] == [1, 2, 3]
    assert cues[0].speaker == "Utkarsh Khare"
    assert cues[0].start == pytest.approx(35.22)
    assert "…" in cues[0].text and "â€" not in cues[0].text
    assert format_ts(4662.9) == "01:17:42"


def test_parse_tolerates_vtt_header_and_commas():
    cues = parse_transcript("WEBVTT\n\n00:00:01,500 --> 00:00:03,000\nA B: hi there\n")
    assert len(cues) == 1 and cues[0].start == 1.5 and cues[0].speaker == "A B"


def test_mojibake_fallback():
    assert fix_mojibake("Youâ€¦ ok") == "You… ok"


def test_lecturer_by_hint_not_surname():
    cues = parse_transcript(SAMPLE)
    # A student named Sharma must not be mistaken for "Prof. Sharma"
    assert identify_lecturer(cues, hint="Utkarsh Khare") == "Utkarsh Khare"
    assert identify_lecturer(cues) == "Utkarsh Khare"      # fallback: most talk time


def test_chunks_keep_timestamps_and_roles():
    cues = parse_transcript(SAMPLE)
    chunks = chunk_cues(cues, "Utkarsh Khare", target_s=10)
    assert chunks[0].start == pytest.approx(35.22)
    assert chunks[-1].last_cue == 3
    assert min(c.lecturer_share for c in chunks) < 1.0      # student turn reflected


def test_filename():
    m = parse_filename("utkarsh_khare-2026-09-14-DS101.txt")
    assert (m.professor, m.lecture_date, m.subject_code) == ("Utkarsh Khare", date(2026, 9, 14), "DS101")
    with pytest.raises(ValueError):
        parse_filename("random.txt")


REAL = "/mnt/user-data/uploads/prof_name-date-subject_code.txt"


@pytest.mark.skipif(not os.path.exists(REAL), reason="real sample not present")
def test_real_sample():
    cues = parse_transcript(open(REAL, "rb").read())
    assert len(cues) == 480
    assert all("â€" not in c.text for c in cues)
    chunks = chunk_cues(cues, identify_lecturer(cues, "Utkarsh Khare"))
    covered = {i for ch in chunks for i in ch.cue_idxs}
    assert covered == {c.idx for c in cues}                 # nothing dropped
