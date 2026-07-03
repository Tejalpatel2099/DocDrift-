# DocDrift

Chat with any public GitHub codebase (RAG with file/line citations) and detect
when documentation has **drifted** out of sync with the code.

**Stack:** Angular 17 (standalone) + Angular Material · FastAPI (Python) ·
Supabase (PostgreSQL + pgvector) · OpenAI (`text-embedding-3-small`, `gpt-4o-mini`).

---

## Repository layout

```
/app
├── backend/          # FastAPI API (runs on :8001)
│   ├── server.py     # Phase 0: /api/hello, /api/health
│   └── .env          # SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY, GITHUB_TOKEN
├── frontend/         # Angular 17 app (dev on :4200, hosted build on :3000)
│   └── src/app/...
└── supabase/
    └── schema.sql    # repos, chunks (vector 1536), drift_flags, match_chunks()
```

---

## Prerequisites (fresh machine)

```bash
# Node 20 + Yarn
node -v            # should be >= 18
npm i -g yarn @angular/cli@17

# Python 3.11+
python3 --version
```

## 1) Supabase (one-time)

1. Create a free project at https://supabase.com.
2. **Project Settings → API**: copy the **Project URL** and the **service_role** key.
3. **SQL Editor → New query**: paste the contents of `supabase/schema.sql` and **Run**.
   This enables `pgvector` and creates `repos`, `chunks`, `drift_flags`, and the
   `match_chunks()` retrieval function.

## 2) Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt

# edit backend/.env and fill in:
#   SUPABASE_URL=...
#   SUPABASE_SERVICE_ROLE_KEY=...
#   OPENAI_API_KEY=...        # needed from Phase 1
#   GITHUB_TOKEN=...          # needed from Phase 1

uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

Verify:
```bash
curl http://localhost:8001/api/hello
curl http://localhost:8001/api/health   # shows live Supabase connectivity
```

## 3) Frontend (Angular)

```bash
cd frontend
yarn install
yarn dev            # ng serve on http://localhost:4200
```

The dev build talks to `http://localhost:8001` (see `src/environments/`).
Open http://localhost:4200 — the **System check** card should show *connected*
and the Supabase row will turn green once your `.env` + `schema.sql` are set.

> `yarn start` produces a **production** build served on `:3000` (used by the
> hosted preview). It calls the API on the same origin (`/api/...`).

---

## Phase status

- [x] **Phase 0 — Scaffolding**: Angular + FastAPI + Supabase wiring, `/api/hello`.
- [ ] Phase 1 — Ingestion pipeline (repo → chunks → embeddings → pgvector + polling).
- [ ] Phase 2 — RAG chat with citations.
- [ ] Phase 3 — Drift re-scan + dashboard.
- [ ] Phase 4 — Polish, README architecture diagram, deployment.
