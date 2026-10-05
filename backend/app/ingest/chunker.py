"""Turn cues into retrieval chunks while keeping exact timestamps.

Key ideas
- The *lecturer* comes from upload metadata (filename / form), NOT from speaker
  labels alone: students speak too, and a student can share a surname with a
  professor. Each cue/chunk carries a lecturer_share so "what did the
  professor say" never returns a student's question.
- Chunks are ~60-120 s, end on sentence boundaries, and overlap by a couple of cues.
- raw_text is kept verbatim (for quotes); normalized_text is for embedding/FTS.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .parser import Cue

_FILLER_RE = re.compile(r"\b(?:um+|uh+|hmm+|ah+)\b[,.]?\s*", re.IGNORECASE)


@dataclass
class Chunk:
    index: int
    start: float
    end: float
    first_cue: int
    last_cue: int
    speakers: list[str]
    lecturer_share: float          # fraction of speaking time by the lecturer (0-1)
    raw_text: str
    normalized_text: str
    cue_idxs: list[int] = field(default_factory=list)


def _tokens(name: str) -> set[str]:
    return {t for t in re.split(r"\W+", name.lower()) if t}


def identify_lecturer(cues: list[Cue], hint: str | None = None) -> str | None:
    """Match the lecturer name against speaker labels; fall back to most speaking time."""
    talk: dict[str, float] = defaultdict(float)
    for c in cues:
        if c.speaker:
            talk[c.speaker] += c.end - c.start
    if not talk:
        return None
    if hint:
        h = _tokens(hint)
        scored = [(len(h & _tokens(s)), t, s) for s, t in talk.items()]
        best = max(scored)
        if best[0] > 0:
            return best[2]
    return max(talk, key=talk.get)


def normalize(text: str) -> str:
    text = _FILLER_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _share(cues: list[Cue], lecturer: str | None) -> float:
    total = sum(c.end - c.start for c in cues) or 1.0
    return sum(c.end - c.start for c in cues if c.speaker == lecturer) / total


def _ends_sentence(c: Cue) -> bool:
    return c.text.rstrip().endswith((".", "?", "!"))


def chunk_cues(
    cues: list[Cue],
    lecturer: str | None,
    target_s: float = 75,
    max_s: float = 120,
    max_words: int = 260,
    overlap_cues: int = 2,
    gap_break_s: float = 25,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    cur: list[Cue] = []

    def is_lect(c: Cue) -> bool:
        return c.speaker == lecturer

    def emit() -> None:
        raw = "\n".join(f"{c.speaker}: {c.text}" if c.speaker else c.text for c in cur)
        body = normalize(" ".join(c.text for c in cur))
        chunks.append(Chunk(
            index=len(chunks), start=cur[0].start, end=cur[-1].end,
            first_cue=cur[0].idx, last_cue=cur[-1].idx,
            speakers=sorted({c.speaker for c in cur if c.speaker}),
            lecturer_share=_share(cur, lecturer),
            raw_text=raw, normalized_text=body, cue_idxs=[c.idx for c in cur],
        ))

    for c in cues:
        if cur:
            dur = cur[-1].end - cur[0].start
            words = sum(len(x.text.split()) for x in cur)
            gap = c.start - cur[-1].end > gap_break_s
            hard = gap or (c.end - cur[0].start > max_s) or words > max_words
            soft = dur >= target_s and _ends_sentence(cur[-1])
            role_switch = dur >= target_s / 2 and is_lect(c) != is_lect(cur[-1]) and _ends_sentence(cur[-1])
            if hard or soft or role_switch:
                emit()
                cur = [] if gap else cur[-overlap_cues:] if overlap_cues else []
        cur.append(c)
    if cur and (not chunks or cur[-1].idx != chunks[-1].last_cue):
        emit()
    return chunks
