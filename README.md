# Lecture RAG

Searchable lecture knowledge base with professor / lecture / date / timestamp citations.

## Status
- [x] Compose stack (Postgres+pgvector, Redis, FastAPI stub)
- [x] Schema: professors, courses, lectures, cues (verbatim quotes), chunks (embedding + FTS)
- [x] Zoom transcript parser (mojibake fix, speaker labels, VTT/SRT tolerant)
- [x] Chunker (60-120 s, sentence-aligned, overlap, lecturer_share)
- [ ] Alembic migration + ingest CLI/endpoint
- [ ] Embeddings, hybrid search (RRF), reranker
- [ ] Answer generation + citation engine
- [ ] React UI

## Run
    docker compose up --build
    cd backend && python -m pytest

## Design rules
- Lecturer identity comes from upload metadata, not speaker labels (students speak too).
- Citations are built by the backend from chunk/cue IDs, never by the LLM.
- Timestamps are seconds from recording start, so they map directly to video offsets.
