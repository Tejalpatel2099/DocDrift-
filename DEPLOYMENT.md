# Deploying DocDrift

DocDrift has three pieces: **Supabase** (already hosted), a **FastAPI backend**, and the
**Angular frontend**. Below are the simplest free/low-cost paths.

---

## 0. Supabase
Already hosted — nothing to deploy. Just make sure `supabase/schema.sql` has been run
and you have your `SUPABASE_URL` + `service_role` key.

---

## 1. Backend (FastAPI) → Render / Railway / Fly.io

A `backend/Dockerfile` is included. On any container host:

**Render (example):**
1. New → **Web Service** → connect your GitHub repo → root directory `backend`.
2. Environment: **Docker**. Render provides `$PORT` automatically (the Dockerfile respects it).
3. Add environment variables:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `OPENAI_API_KEY`
   - `GITHUB_TOKEN`
   - `CORS_ORIGINS` = your frontend URL, e.g. `https://docdrift.vercel.app`
4. Deploy. Note the public URL, e.g. `https://docdrift-api.onrender.com`.

> Because indexing runs in a background task, use at least the smallest **always-on**
> instance (free tiers that sleep will pause mid-index). Production: move indexing to a
> worker + queue (see `ingestion.py` notes).

---

## 2. Frontend (Angular) → Vercel / Netlify / Docker

The app calls the API using `src/environments/environment.ts` → `apiBaseUrl`.
**Before building for a separate backend domain, set it:**

```ts
// src/environments/environment.ts
export const environment = {
  production: true,
  apiBaseUrl: 'https://docdrift-api.onrender.com',  // your deployed backend
};
```

**Vercel / Netlify (static):**
- Build command: `yarn build --configuration production`
- Output directory: `dist/client/browser`
- (Netlify) add a redirect for SPA routing: `/* /index.html 200`

**Docker (nginx):** a `frontend/Dockerfile` + `frontend/nginx.conf` are included:
```bash
cd frontend
docker build -t docdrift-web .
docker run -p 8080:80 docdrift-web
```

---

## 3. Wire them together
- Set the backend's `CORS_ORIGINS` to the exact frontend origin.
- Set the frontend's `apiBaseUrl` to the backend URL (or serve both behind one domain and
  use the `/api` proxy block in `nginx.conf`, keeping `apiBaseUrl` empty).

## Checklist
- [ ] `schema.sql` run in Supabase
- [ ] Backend env vars set (Supabase + OpenAI + GitHub + CORS_ORIGINS)
- [ ] Frontend `apiBaseUrl` points at the backend
- [ ] `curl https://<backend>/api/health` returns `database.ok: true`
