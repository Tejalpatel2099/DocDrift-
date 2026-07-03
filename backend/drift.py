"""Documentation drift detection.

For each documentation chunk we retrieve the code it most likely describes
(vector similarity, filtered to code chunks) and ask the LLM, in strict JSON,
whether the doc is still accurate. Drifted docs become rows in `drift_flags`.

v1 simplification: we evaluate every doc chunk against the *current* related
code rather than diffing "what changed since last index". Production would store
each blob's SHA at index time and only re-check docs whose related code changed
(via blob SHA delta) — far cheaper on large repos and frequent re-scans.
"""
import os
import json

from openai import OpenAI

from db import get_supabase

CHAT_MODEL = "gpt-4o-mini"
MAX_DOCS = 40          # cap LLM calls per scan (cost/latency guard)
RELATED_CODE_K = 4

DRIFT_SYSTEM = (
    "You are a meticulous technical reviewer checking whether a documentation "
    "section still accurately describes the code it refers to. You are given a "
    "DOC section and the most-related CODE snippets from the same repository.\n"
    "Decide if the documentation is still accurate for that code. Respond ONLY "
    "with strict JSON of the form:\n"
    '{"verdict": "in_sync" | "drifted", "severity": "low" | "medium" | "high", '
    '"reason": "<one or two sentences>"}\n'
    "Mark 'drifted' when the doc describes APIs, signatures, options, behavior, "
    "commands, or defaults that no longer match the code. Use 'high' severity for "
    "wrong/removed APIs or incorrect instructions, 'medium' for outdated details, "
    "'low' for minor wording. If the doc is generic prose with nothing to verify, "
    "return in_sync/low."
)

# In-memory scan progress (v1, same pattern as ingestion).
DRIFT_JOBS: dict[str, dict] = {}


def _client() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in backend/.env")
    return OpenAI(api_key=key)


def get_drift_status(repo_id: str) -> dict:
    return DRIFT_JOBS.get(repo_id, {"status": "idle"})


def list_drift(repo_id: str) -> list[dict]:
    sb = get_supabase()
    return (sb.table("drift_flags").select("*")
            .eq("repo_id", repo_id).order("severity", desc=True)
            .order("created_at", desc=True).execute().data)


def _judge(doc: dict, code_chunks: list[dict]) -> dict:
    code_ctx = "\n\n".join(
        f'{c["file_path"]}:{c["start_line"]}-{c["end_line"]}\n{c["content"]}'
        for c in code_chunks
    ) or "(no closely related code found)"
    user = (
        f'DOC section — {doc["file_path"]}:{doc["start_line"]}-{doc["end_line"]}:\n'
        f'{doc["content"]}\n\n---\n\nRELATED CODE:\n{code_ctx}'
    )
    resp = _client().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": DRIFT_SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    try:
        data = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        data = {}
    return {
        "verdict": data.get("verdict", "in_sync"),
        "severity": data.get("severity", "low") if data.get("severity") in ("low", "medium", "high") else "low",
        "reason": data.get("reason", ""),
    }


def run_drift_scan(repo_id: str) -> None:
    sb = get_supabase()
    DRIFT_JOBS[repo_id] = {"status": "scanning", "checked": 0, "total": 0, "flagged": 0, "error": None}
    try:
        # clear previous flags for a fresh report
        sb.table("drift_flags").delete().eq("repo_id", repo_id).execute()

        docs = (sb.table("chunks")
                .select("id,file_path,start_line,end_line,content,embedding")
                .eq("repo_id", repo_id).eq("chunk_type", "doc").limit(MAX_DOCS).execute().data)
        DRIFT_JOBS[repo_id]["total"] = len(docs)

        for i, doc in enumerate(docs):
            related = sb.rpc("match_chunks", {
                "query_embedding": doc["embedding"],
                "match_repo_id": repo_id,
                "match_count": RELATED_CODE_K,
                "filter_type": "code",
            }).execute().data or []

            result = _judge(doc, related)
            if result["verdict"] == "drifted":
                sb.table("drift_flags").insert({
                    "repo_id": repo_id,
                    "doc_chunk_id": doc["id"],
                    "related_code_path": related[0]["file_path"] if related else None,
                    "verdict": result["verdict"],
                    "reason": result["reason"],
                    "severity": result["severity"],
                }).execute()
                DRIFT_JOBS[repo_id]["flagged"] += 1
            DRIFT_JOBS[repo_id]["checked"] = i + 1

        DRIFT_JOBS[repo_id]["status"] = "done"
    except Exception as e:  # noqa: BLE001
        DRIFT_JOBS[repo_id] = {**DRIFT_JOBS.get(repo_id, {}), "status": "error", "error": str(e)}
