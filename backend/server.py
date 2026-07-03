"""
DocDrift API — FastAPI backend.

Phase 0: proves the frontend -> backend -> Supabase wiring.
  GET /api/hello   -> smoke test the Angular app calls on load
  GET /api/health  -> process + live Supabase connectivity

Everything is namespaced under /api so the platform proxy routes it to this
server on port 8001. The Angular app (port 3000) calls these endpoints.
"""
import os
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("docdrift")

# --- Supabase client (lazy + guarded) ---------------------------------------
# The service_role key is server-side only and bypasses Row Level Security, so
# it must never reach the browser. In Phase 0 the credentials may be blank; the
# server still boots so /api/hello works, and /api/health reports DB status.
from supabase import create_client, Client  # noqa: E402

_supabase: Client | None = None


def supabase_configured() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))


def get_supabase() -> Client:
    global _supabase
    if not supabase_configured():
        raise RuntimeError("Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in backend/.env")
    if _supabase is None:
        _supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
    return _supabase


def check_db_connection() -> dict:
    if not supabase_configured():
        return {"ok": False, "detail": "Supabase credentials not set in backend/.env"}
    try:
        get_supabase().table("repos").select("id").limit(1).execute()
        return {"ok": True, "detail": "Connected to Supabase and repos table is reachable."}
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "does not exist" in msg or "42P01" in msg:
            return {"ok": True, "detail": "Connected to Postgres, but run supabase/schema.sql to create tables."}
        return {"ok": False, "detail": msg}


# --- App + routes ------------------------------------------------------------
app = FastAPI(title="DocDrift API", version="0.1.0")
api_router = APIRouter(prefix="/api")


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
        "database": check_db_connection(),
    }


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
