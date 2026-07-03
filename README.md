<div align="center">

# 📚 DocDrift

### Chat with any public GitHub codebase — and catch your docs *drifting* out of sync with your code.

**Angular 17 · FastAPI · Supabase (PostgreSQL + pgvector) · OpenAI**

</div>

---

## 🎯 What is DocDrift?

Documentation rots. Code changes, docs don't, and six months later your README lies to
every new engineer who reads it. **DocDrift** attacks that problem with two capabilities:

1. **Chat with a codebase (RAG).** Paste a public GitHub URL. DocDrift ingests the repo,
   embeds it, and lets you ask natural-language questions. Every answer is **grounded** in
   the actual source and comes with **clickable citations** (exact `file · line-range`) — so
   you can trust it and jump straight to the code.
2. **Documentation drift detection.** On demand, DocDrift compares the repo's docs against
   its current code and **flags the sections that no longer match**, each with an
   AI-generated reason and a severity — a living "is my documentation still true?" report.

## 💡 Why it's useful (the benefits)

- **Onboard faster** — new hires ask the codebase questions instead of pinging seniors.
- **Trustworthy answers** — citations + a "not in the context" guardrail mean it says
  *"I don't know"* instead of hallucinating.
- **Docs you can rely on** — drift detection turns "are these docs still accurate?" from a
  vibe into a concrete, reviewable list.
- **Zero setup for the reader** — no accounts, no OAuth; just paste a public repo URL.

---

## 🏗️ Architecture

```
                    ┌─────────────────────────────┐
                    │   Angular 17 (standalone)    │
                    │   + Angular Material (dark)  │
                    │  repo sidebar · chat · drift │
                    └───────────────┬─────────────┘
                                    │  HTTPS  (/api/*)
                    ┌───────────────▼─────────────┐
                    │      FastAPI  (Python)       │
                    │  ingestion · RAG · drift     │
                    └───┬───────────┬───────────┬──┘
                        │           │           │
              ┌─────────▼──┐  ┌─────▼─────┐ ┌───▼─────────────┐
              │  GitHub    │  │  OpenAI   │ │   Supabase      │
              │  REST API  │  │ embeddings│ │  Postgres +     │
              │ (Octokit-  │  │  + chat   │ │  pgvector       │
              │  style)    │  │ 4o-mini   │ │  repos/chunks/  │
              └────────────┘  └───────────┘ │  drift_flags    │
                                            └─────────────────┘
```

**Ingestion flow:** `GitHub tree + blobs` → **chunk** (code by symbol, docs by heading) →
**embed** (`text-embedding-3-small`) → **store** vectors in `pgvector` with `file_path` +
line ranges. Runs in a background task; the UI polls a status endpoint every 2s.

**Chat (RAG) flow:** embed the question → **cosine top-k** via the `match_chunks()` SQL
function → feed retrieved chunks + question to `gpt-4o-mini` → return a grounded answer +
citations.

---

## 🧰 Tech stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | **Angular 17** (standalone components) + **Angular Material** | Typed, structured SPA; Material for fast, accessible dark UI |
| Backend | **FastAPI** (Python) | Async, typed, great for AI workloads |
| Database | **Supabase** — PostgreSQL + **pgvector** | Managed Postgres with first-class vector search |
| Embeddings | **OpenAI `text-embedding-3-small`** (1536-dim) | Cheap, strong retrieval quality |
| Generation | **OpenAI `gpt-4o-mini`** | Fast, cheap, good enough for grounded Q&A + drift reasoning |
| Source access | **GitHub REST API** + server-side token | Public repos only, token kept server-side |

---

## 🗄️ Data model

| Table | Purpose |
|---|---|
| `repos` | one row per indexed repo (`github_url`, `name`, `default_branch`, `status`, `last_indexed_at`) |
| `chunks` | embedded pieces — `file_path`, `start_line`, `end_line`, `chunk_type` (`code`/`doc`), `content`, `embedding vector(1536)` |
| `drift_flags` | drift results — `doc_chunk_id`, `related_code_path`, `verdict`, `reason`, `severity` |

Plus a SQL function `match_chunks(query_embedding, repo_id, k, type)` for cosine top-k retrieval.

---

## 🚀 Getting started (local)

### Prerequisites
```bash
node -v            # >= 18
npm i -g yarn @angular/cli@17
python3 --version  # >= 3.11
```

### 1) Supabase (one-time)
1. Create a free project at https://supabase.com.
2. **Project Settings → API**: copy the **Project URL** and the **`service_role`** key.
3. **SQL Editor → New query**: paste all of `supabase/schema.sql` and **Run** (choose
   *Run without RLS* for v1). This enables `pgvector` and creates the tables + `match_chunks()`.

### 2) Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
# fill backend/.env:
#   SUPABASE_URL=...
#   SUPABASE_SERVICE_ROLE_KEY=...
#   OPENAI_API_KEY=...
#   GITHUB_TOKEN=...        # optional but recommended (raises GitHub rate limit)
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```
Verify: `curl http://localhost:8001/api/health`

### 3) Frontend (Angular)
```bash
cd frontend
yarn install
yarn dev            # http://localhost:4200  (talks to the API on :8001)
```

> `yarn start` builds for production and serves on `:3000` (same-origin `/api`) — used by
> hosted deployments.

---

## 🖱️ How to use

1. Open the app and **paste a public GitHub URL** (e.g. `https://github.com/expressjs/cors`).
2. Click **Index repo** — watch the progress bar as files are fetched, chunked, and embedded.
3. When it turns **READY**, open it and **ask questions** — answers come back with
   clickable `file:line` citation chips *(Phase 2)*.
4. Hit **Re-scan** to check for **documentation drift** and review flagged sections
   with reasons + severity *(Phase 3)*.

---

## 📁 Project structure

```
DocDrift/
├── backend/                 # FastAPI API (port 8001)
│   ├── server.py            # routes: /api/hello, /api/health, /api/repos*
│   ├── db.py                # Supabase client (service_role, server-side only)
│   ├── chunking.py          # code-by-symbol / markdown-by-heading / window fallback
│   ├── ingestion.py         # GitHub fetch → chunk → embed → pgvector + job progress
│   └── requirements.txt
├── frontend/                # Angular 17 app (dev :4200 / prod :3000)
│   └── src/app/
│       ├── app.component.*   # shell: repo sidebar + ingest UI
│       └── core/api.service.ts
├── supabase/
│   └── schema.sql           # pgvector + tables + match_chunks()
└── README.md
```

---

## 🗺️ Roadmap

- [x] **Phase 0** — Scaffolding (Angular + FastAPI + Supabase, health endpoint).
- [x] **Phase 1** — Ingestion (repo → chunks → embeddings → pgvector, progress polling).
- [x] **Phase 2** — RAG chat with clickable citations + anti-hallucination guardrail.
- [ ] **Phase 3** — Documentation drift re-scan + dashboard (severity, reason).
- [ ] **Phase 4** — Polish, deployment, live demo on a real repo.

---

## ⚠️ v1 simplifications (intentional)

No auth/OAuth · no Redis/queue (background task + status polling) · no webhooks (manual
re-scan) · public repos only. Each is a deliberate scope decision with a documented
production-grade alternative (queues/workers, tree-sitter chunking, RLS, incremental
indexing by blob SHA).

---

<div align="center">
Built as a portfolio project to demonstrate full-stack + applied-AI engineering.
</div>
