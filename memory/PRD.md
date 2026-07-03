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

## Backlog / next
- **Phase 1 (P0)**: ingestion — Octokit/PyGithub fetch tree+contents → chunk
  (code by function/class, markdown by heading) → embed → store in pgvector.
  Return job_id immediately; `/api/repos/{id}/status` polled every 2s.
  BLOCKER: needs user's OPENAI_API_KEY + GITHUB_TOKEN + Supabase creds + schema.sql run.
- Phase 2 (P0): RAG chat with citation chips + "not in context" guardrail.
- Phase 3 (P1): drift re-scan + dashboard (severity, reason).
- Phase 4 (P2): polish, empty/error states, architecture diagram, deployment.
