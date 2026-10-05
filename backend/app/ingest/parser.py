"""Parse Zoom-style transcripts into timestamped, speaker-labelled cues.

Handles the format seen in real exports:

    1
    00:00:35.220 --> 00:00:51.299
    Speaker Name: spoken text...

and also tolerates a WEBVTT header, SRT commas, missing cue numbers,
and multi-line cue text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

TIME = r"(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}"
CUE_TIME_RE = re.compile(rf"^\s*({TIME})\s*-->\s*({TIME})")
# Speaker names: no digits, <= 60 chars. Anything else is treated as "no speaker".
SPEAKER_RE = re.compile(r"^([^:\d\n]{1,60}?):\s+(.*)$", re.S)

# Zoom exports are sometimes UTF-8 bytes decoded as cp1252 ("â€¦" instead of "…").
_MOJIBAKE_MAP = {
    "â€¦": "…", "â€™": "’", "â€˜": "‘", "â€œ": "“", "â€\x9d": "”",
    "â€“": "–", "â€”": "—", "Â ": " ",
}


@dataclass
class Cue:
    idx: int            # 1-based position in the file
    start: float        # seconds from recording start
    end: float
    speaker: str | None
    text: str


def fix_mojibake(s: str) -> str:
    if not any(m in s for m in ("â€", "Ã", "Â")):
        return s
    try:
        return s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        for bad, good in _MOJIBAKE_MAP.items():
            s = s.replace(bad, good)
        return s


def to_seconds(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    secs = float(parts[-1]) + 60 * int(parts[-2])
    if len(parts) == 3:
        secs += 3600 * int(parts[0])
    return secs


def format_ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def parse_transcript(raw: str | bytes) -> list[Cue]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig", errors="replace")
    raw = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        t_i = next((i for i, ln in enumerate(lines) if CUE_TIME_RE.match(ln)), None)
        if t_i is None:                      # WEBVTT header, NOTE blocks, etc.
            continue
        m = CUE_TIME_RE.match(lines[t_i])
        body = fix_mojibake(" ".join(ln.strip() for ln in lines[t_i + 1:])).strip()
        if not body:
            continue
        speaker = None
        sm = SPEAKER_RE.match(body)
        if sm:
            speaker, body = sm.group(1).strip(), sm.group(2).strip()
        number = lines[t_i - 1].strip() if t_i > 0 and lines[t_i - 1].strip().isdigit() else None
        cues.append(Cue(
            idx=int(number) if number else len(cues) + 1,
            start=to_seconds(m.group(1)),
            end=to_seconds(m.group(2)),
            speaker=speaker,
            text=body,
        ))
    return cues
