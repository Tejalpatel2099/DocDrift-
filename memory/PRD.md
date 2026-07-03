# DocDrift — PRD & Build Log

## Problem statement
Portfolio-grade full-stack + AI project. Two capabilities:
1. **Chat with any public GitHub codebase** — RAG Q&A where every answer cites
   exact files + line ranges.
2. **Documentation drift detection** — compare a repo's docs against current code
   on demand ("Re-scan"), flag stale sections with an AI reason + severity.

Owner: new-grad SWE (MS CS). Learning goals: **Angular**. Mentor-style delivery:
phase-by-phase, design explanation → code → interview Q&A → trade-offs, pause for
confirmation at each phase boundary.

## Fixed tech stack (agreed)
- Frontend: **Angular 17** standalone + Angular Material (dark theme).
- Backend: **FastAPI (Python)** — chosen over Node/Express so it runs on the
  platform's hosted preview URL. (User relaxed the original Node/TS backend goal;
  Angular learning goal retained.)
- DB: **Supabase** (PostgreSQL + pgvector).
- AI: OpenAI `text-embedding-3-small` (embeddings) + `gpt-4o-mini` (chat/drift).
  Uses the **user's own OpenAI API key** (Emergent Universal key is chat-only,
  no embeddings endpoint — not usable for RAG). Needed from Phase 1.
- GitHub: PyGithub/REST with a server-side token, public repos only. Needed Phase 1.

## v1 simplifications (do NOT upgrade)
No auth/OAuth · no Redis/BullMQ (async fn + job-status polling every 2s) ·
no webhooks (manual Re-scan) · local dev first, deploy last.

## Data model (supabase/schema.sql)
- `repos(id, github_url, name, default_branch, status, last_indexed_at, created_at)`
- `chunks(id, repo_id, file_path, start_line, end_line, chunk_type[code|doc], content, embedding vector(1536))`
- `drift_flags(id, repo_id, doc_chunk_id, related_code_path, verdict, reason, severity, created_at)`
- `match_chunks(query_embedding, match_repo_id, match_count, filter_type)` RPC for cosine top-k.

## Environment notes
- Backend served on :8001 (platform proxy routes /api/* here). Frontend hosted build on :3000.
- `frontend yarn start` = prod build + http-server on :3000 (same-origin API).
- `frontend yarn dev` = ng serve :4200 → talks to localhost:8001 (local dev).

## Progress log
- 2026-07-03 — **Phase 0 complete**. Angular app + FastAPI + Supabase-guarded
  connection. `/api/hello` + `/api/health`. Hosted preview verified: frontend
  renders, API "connected", Supabase reports "not set" (creds pending). Dark
  Material theme (Sora / IBM Plex Sans / IBM Plex Mono, electric-mint accent).

- 2026-07-03 — **Phase 1 built (pending live test)**. Backend: `db.py` (supabase
  singleton), `chunking.py` (code by symbol regex / markdown by heading / window
  fallback, 1-based line ranges), `ingestion.py` (GitHub Trees+Blobs fetch, file
  filter, batched `text-embedding-3-small`, batched pgvector insert, in-memory
  JOBS progress, idempotent re-index). Endpoints: POST/GET /api/repos, GET
  /api/repos/{id}, /status. Frontend: repo sidebar + ingest form + 2s polling
  progress bar + health badges. OPENAI_API_KEY set. Chunking unit-tested; server
  boots; POST guarded (503) w/o Supabase. BLOCKED on Supabase creds + GITHUB_TOKEN
  + a non-empty test repo for the live end-to-end demo.

## Backlog / next
- 2026-07-03 — **Phase 2 COMPLETE & VERIFIED LIVE**. `rag.py`: embed question →
  `match_chunks()` cosine top-10 → gpt-4o-mini grounded answer (temp 0.1) with a
  strict system prompt (answer only from context, else "I couldn't find that in
  the indexed code") + citations carrying GitHub blob deep-links (file#Lx-Ly).
  Endpoint `POST /api/repos/{id}/chat` (404 if missing, 409 if not ready). Angular:
  clickable repo sidebar → chat view with user/assistant bubbles, thinking state,
  suggestion chips, and clickable citation chips. Verified in-browser against
  expressjs/cors: accurate answer + 10 citations. Anti-hallucination guardrail
  confirmed (unrelated repo → "couldn't find"). Known polish: answer rendered as
  pre-wrap text (code fences literal) — could add ngx-markdown; no re-ranking/streaming yet.
- 2026-07-03 — **Phase 1 VERIFIED LIVE**. Supabase connected (service_role) +
  schema.sql run (no RLS, v1). Indexed `expressjs/cors`: 14 files → 57 chunks
  embedded into pgvector, job polled to `ready`. Rows confirmed via REST with
  correct file_path + line ranges. Frontend sidebar shows repo READY, db badge lit.
  (No GITHUB_TOKEN yet — fine for small repos; needed to avoid 60/hr unauth limit.)
- **Phase 1 (P0)**: ingestion — Octokit/PyGithub fetch tree+contents → chunk
  (code by function/class, markdown by heading) → embed → store in pgvector.
  Return job_id immediately; `/api/repos/{id}/status` polled every 2s.
  BLOCKER: needs user's OPENAI_API_KEY + GITHUB_TOKEN + Supabase creds + schema.sql run.
- Phase 2 (P0): RAG chat with citation chips + "not in context" guardrail.
- Phase 3 (P1): drift re-scan + dashboard (severity, reason).
- Phase 4 (P2): polish, empty/error states, architecture diagram, deployment.
