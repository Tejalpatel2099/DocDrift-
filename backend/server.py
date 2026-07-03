"""
DocDrift API — FastAPI backend.

Phase 0: /api/hello, /api/health
Phase 1: repo ingestion (GitHub -> chunks -> embeddings -> pgvector) with
         immediate job id + a status endpoint the Angular UI polls every 2s.
"""
import os
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("docdrift")

from db import supabase_configured, check_db_connection  # noqa: E402
from ingestion import (  # noqa: E402
    upsert_repo, list_repos, get_repo, get_job_status, run_ingestion, parse_github_url,
)
from rag import answer_question  # noqa: E402
from drift import run_drift_scan, get_drift_status, list_drift  # noqa: E402

app = FastAPI(title="DocDrift API", version="0.2.0")
api_router = APIRouter(prefix="/api")


class RepoCreate(BaseModel):
    github_url: str


class ChatRequest(BaseModel):
    question: str


@api_router.get("/hello")
async def hello():
    return {
        "service": "docdrift-api",
        "message": "Hello from the DocDrift FastAPI backend 👋",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/health")
def health():
    return {
        "status": "ok",
        "supabaseConfigured": supabase_configured(),
        "openaiConfigured": bool(os.environ.get("OPENAI_API_KEY")),
        "githubTokenSet": bool(os.environ.get("GITHUB_TOKEN")),
        "database": check_db_connection(),
    }


@api_router.post("/repos")
def create_repo(body: RepoCreate, background: BackgroundTasks):
    """Register a repo and kick off indexing in the background.

    Returns immediately with the repo id so the UI can start polling
    /api/repos/{id}/status. No queue in v1 (see ingestion.py trade-off note).
    """
    if not supabase_configured():
        raise HTTPException(503, "Supabase not configured on the server.")
    try:
        parse_github_url(body.github_url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    repo = upsert_repo(body.github_url)
    background.add_task(run_ingestion, repo["id"], body.github_url)
    return {"repo_id": repo["id"], "status": "indexing", "name": repo["name"]}


@api_router.get("/repos")
def get_repos():
    if not supabase_configured():
        raise HTTPException(503, "Supabase not configured on the server.")
    return list_repos()


@api_router.get("/repos/{repo_id}")
def get_one_repo(repo_id: str):
    repo = get_repo(repo_id)
    if not repo:
        raise HTTPException(404, "Repo not found")
    return repo


@api_router.get("/repos/{repo_id}/status")
def repo_status(repo_id: str):
    return get_job_status(repo_id)


@api_router.post("/repos/{repo_id}/chat")
def chat(repo_id: str, body: ChatRequest):
    """RAG answer for a question, grounded in this repo's indexed chunks."""
    repo = get_repo(repo_id)
    if not repo:
        raise HTTPException(404, "Repo not found")
    if repo.get("status") != "ready":
        raise HTTPException(409, "Repo is still indexing. Try again once it's ready.")
    if not body.question.strip():
        raise HTTPException(400, "Question is empty.")
    return answer_question(repo, body.question.strip())


@api_router.post("/repos/{repo_id}/drift/rescan")
def drift_rescan(repo_id: str, background: BackgroundTasks):
    repo = get_repo(repo_id)
    if not repo:
        raise HTTPException(404, "Repo not found")
    if repo.get("status") != "ready":
        raise HTTPException(409, "Repo is still indexing.")
    background.add_task(run_drift_scan, repo_id)
    return {"status": "scanning"}


@api_router.get("/repos/{repo_id}/drift/status")
def drift_status(repo_id: str):
    return get_drift_status(repo_id)


@api_router.get("/repos/{repo_id}/drift")
def drift_flags(repo_id: str):
    return list_drift(repo_id)


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
