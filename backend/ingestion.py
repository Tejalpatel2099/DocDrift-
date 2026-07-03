"""Ingestion pipeline: GitHub repo URL -> chunks -> embeddings -> pgvector.

v1 simplifications (intentional):
  * No queue. The API returns a job id immediately and the pipeline runs in a
    FastAPI BackgroundTask. Progress lives in an in-memory JOBS dict that the
    frontend polls every 2s.
  * Re-indexing is idempotent: we delete a repo's existing chunks first.

PRODUCTION ALTERNATIVE: move the pipeline to a worker (Celery/RQ/BullMQ) with a
durable job store (Redis/Postgres). Trade-off: in-memory progress is simple but
resets on restart and can't scale past one process. Good interview talking point.
"""
import os
import re
import base64
from datetime import datetime, timezone
from typing import Optional

import httpx
from openai import OpenAI

from db import get_supabase

EMBED_MODEL = "text-embedding-3-small"
EMBED_BATCH = 96
GITHUB_API = "https://api.github.com"

# Only index reasonably-sized text/source files; skip vendored + binary noise.
ALLOWED_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".php",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".kt", ".swift", ".scala", ".sh",
    ".md", ".mdx", ".markdown", ".rst", ".txt", ".yml", ".yaml", ".toml", ".sql",
}
SKIP_DIRS = ("node_modules/", "dist/", "build/", ".git/", "vendor/", "__pycache__/",
             ".next/", "venv/", ".venv/", "coverage/")
MAX_FILES = 400
MAX_BLOB_BYTES = 120_000

# In-memory job tracker (v1). repo_id -> progress dict.
JOBS: dict[str, dict] = {}


# --- helpers ---------------------------------------------------------------
def parse_github_url(url: str) -> tuple[str, str]:
    """Return (owner, repo) from a variety of GitHub URL shapes."""
    cleaned = url.strip().rstrip("/")
    cleaned = re.sub(r"\.git$", "", cleaned)
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+)", cleaned)
    if not m:
        raise ValueError("Not a valid GitHub repository URL")
    return m.group(1), m.group(2)


def _gh_headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(client: httpx.Client, path: str) -> dict:
    r = client.get(f"{GITHUB_API}{path}", headers=_gh_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def _openai() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in backend/.env")
    return OpenAI(api_key=key)


def _embed(texts: list[str]) -> list[list[float]]:
    client = _openai()
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        out.extend(d.embedding for d in resp.data)
    return out


def _keep(path: str, size: int) -> bool:
    if any(seg in path for seg in SKIP_DIRS):
        return False
    if size and size > MAX_BLOB_BYTES:
        return False
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext in ALLOWED_EXTS


# --- repo CRUD -------------------------------------------------------------
def upsert_repo(github_url: str) -> dict:
    owner, repo = parse_github_url(github_url)
    sb = get_supabase()
    existing = sb.table("repos").select("*").eq("github_url", github_url).limit(1).execute()
    if existing.data:
        return existing.data[0]
    row = {"github_url": github_url, "name": f"{owner}/{repo}", "status": "pending"}
    return sb.table("repos").insert(row).execute().data[0]


def list_repos() -> list[dict]:
    return get_supabase().table("repos").select("*").order("created_at", desc=True).execute().data


def get_repo(repo_id: str) -> Optional[dict]:
    res = get_supabase().table("repos").select("*").eq("id", repo_id).limit(1).execute()
    return res.data[0] if res.data else None


def get_job_status(repo_id: str) -> dict:
    if repo_id in JOBS:
        return JOBS[repo_id]
    repo = get_repo(repo_id)
    if not repo:
        return {"status": "not_found"}
    return {"status": repo["status"], "processed_files": 0, "total_files": 0, "chunks": 0}


# --- the pipeline ----------------------------------------------------------
def run_ingestion(repo_id: str, github_url: str) -> None:
    owner, repo = parse_github_url(github_url)
    sb = get_supabase()
    JOBS[repo_id] = {"status": "indexing", "phase": "fetching", "processed_files": 0,
                     "total_files": 0, "chunks": 0, "error": None}
    try:
        sb.table("repos").update({"status": "indexing"}).eq("id", repo_id).execute()
        # idempotent re-index
        sb.table("chunks").delete().eq("repo_id", repo_id).execute()

        with httpx.Client() as client:
            meta = _get(client, f"/repos/{owner}/{repo}")
            branch = meta.get("default_branch", "main")
            sb.table("repos").update({"default_branch": branch}).eq("id", repo_id).execute()

            tree = _get(client, f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1")
            files = [t for t in tree.get("tree", [])
                     if t.get("type") == "blob" and _keep(t["path"], t.get("size", 0))][:MAX_FILES]
            JOBS[repo_id]["total_files"] = len(files)

            pending_rows: list[dict] = []
            for idx, f in enumerate(files):
                try:
                    blob = _get(client, f"/repos/{owner}/{repo}/git/blobs/{f['sha']}")
                    if blob.get("encoding") != "base64":
                        continue
                    text = base64.b64decode(blob["content"]).decode("utf-8", errors="ignore")
                except (httpx.HTTPError, ValueError):
                    continue
                from chunking import chunk_file
                for c in chunk_file(f["path"], text):
                    pending_rows.append({
                        "repo_id": repo_id,
                        "file_path": f["path"],
                        "start_line": c["start_line"],
                        "end_line": c["end_line"],
                        "chunk_type": c["chunk_type"],
                        "content": c["content"],
                    })
                JOBS[repo_id]["processed_files"] = idx + 1

        # embed + store
        JOBS[repo_id]["phase"] = "embedding"
        if pending_rows:
            vectors = _embed([r["content"] for r in pending_rows])
            for r, v in zip(pending_rows, vectors):
                r["embedding"] = v
            for i in range(0, len(pending_rows), 200):
                sb.table("chunks").insert(pending_rows[i:i + 200]).execute()
        JOBS[repo_id]["chunks"] = len(pending_rows)

        sb.table("repos").update({
            "status": "ready",
            "last_indexed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", repo_id).execute()
        JOBS[repo_id]["status"] = "ready"
        JOBS[repo_id]["phase"] = "done"
    except Exception as e:  # noqa: BLE001
        JOBS[repo_id] = {**JOBS.get(repo_id, {}), "status": "error", "error": str(e)}
        try:
            sb.table("repos").update({"status": "error"}).eq("id", repo_id).execute()
        except Exception:  # noqa: BLE001
            pass
