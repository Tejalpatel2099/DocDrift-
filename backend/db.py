"""Supabase access — a single lazily-created, process-wide client.

Separated from server.py so both the API layer and the ingestion pipeline can
import it without a circular dependency. The service_role key bypasses Row
Level Security, so this module (and this key) must stay server-side only.
"""
import os
from functools import lru_cache

from supabase import create_client, Client


def supabase_configured() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Lazy singleton. Exceptions aren't cached, so a call after fixing the
    env will still build the client correctly."""
    if not supabase_configured():
        raise RuntimeError("Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in backend/.env")
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


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
