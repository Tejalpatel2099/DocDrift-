"""RAG chat: question -> embed -> cosine top-k -> grounded LLM answer + citations.

The whole point is *grounding*: the model may only use the retrieved chunks, and
must say "I don't know" if they don't contain the answer. That single constraint
is what makes the citations trustworthy.

PRODUCTION ALTERNATIVES (interview talking points):
  * Re-ranking: retrieve top-30 then re-rank with a cross-encoder before sending
    top-10 to the LLM — better precision than raw cosine.
  * Streaming: stream tokens over SSE for perceived latency.
  * Hybrid search: combine vector similarity with keyword/BM25 for exact-symbol
    queries ("where is parseHeader defined?").
"""
import os
import re
from functools import lru_cache

from openai import OpenAI

from db import get_supabase

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
TOP_K = 10

SYSTEM_PROMPT = (
    "You are a precise coding assistant answering questions about a specific "
    "GitHub repository. You are given numbered context snippets retrieved from "
    "the codebase. Rules:\n"
    "1. Answer ONLY using the provided context. Do not use outside knowledge.\n"
    "2. Cite the snippets you used inline with their numbers, e.g. [1], [2].\n"
    "3. If the context is only partially relevant, synthesize the best answer you "
    "can from what IS present (e.g. infer the project's purpose from module, class, "
    "test, and file names) and briefly note what's missing. Only respond exactly "
    "\"I couldn't find that in the indexed code.\" when NONE of the context relates "
    "to the question.\n"
    "4. Be concise and technical. Prefer showing the relevant code path."
)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in backend/.env")
    return OpenAI(api_key=key)


def _embed_query(text: str) -> list[float]:
    return _client().embeddings.create(model=EMBED_MODEL, input=[text]).data[0].embedding


def _blob_url(github_url: str, branch: str, path: str, start: int, end: int) -> str:
    cleaned = re.sub(r"\.git$", "", github_url.strip().rstrip("/"))
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+)", cleaned)
    if not m:
        return github_url
    owner, repo = m.group(1), m.group(2)
    return f"https://github.com/{owner}/{repo}/blob/{branch}/{path}#L{start}-L{end}"


def answer_question(repo: dict, question: str) -> dict:
    sb = get_supabase()
    q_emb = _embed_query(question)
    res = sb.rpc("match_chunks", {
        "query_embedding": q_emb,
        "match_repo_id": repo["id"],
        "match_count": TOP_K,
        "filter_type": None,
    }).execute()
    chunks = res.data or []

    if not chunks:
        return {"answer": "I couldn't find that in the indexed code.", "citations": []}

    # Build numbered context + parallel citation list.
    branch = repo.get("default_branch") or "main"
    context_blocks = []
    citations = []
    for i, c in enumerate(chunks, start=1):
        loc = f'{c["file_path"]}:{c["start_line"]}-{c["end_line"]}'
        context_blocks.append(f"[{i}] {loc} ({c['chunk_type']})\n{c['content']}")
        citations.append({
            "index": i,
            "file_path": c["file_path"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "chunk_type": c["chunk_type"],
            "similarity": round(float(c.get("similarity", 0)), 3),
            "url": _blob_url(repo["github_url"], branch, c["file_path"], c["start_line"], c["end_line"]),
        })

    context = "\n\n---\n\n".join(context_blocks)
    user_msg = f"Context snippets:\n\n{context}\n\n---\n\nQuestion: {question}"

    resp = _client().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    answer = resp.choices[0].message.content or ""
    return {"answer": answer, "citations": citations}
