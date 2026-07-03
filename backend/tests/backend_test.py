"""Backend API tests for DocDrift."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://unruffled-fermi-9.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def cors_repo_id():
    r = requests.get(f"{BASE_URL}/api/repos", timeout=30)
    assert r.status_code == 200
    repos = r.json()
    cors = next((x for x in repos if "cors" in x["name"].lower()), None)
    assert cors, "expressjs/cors repo not indexed"
    return cors["id"]


# ---- Health ----
def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["supabaseConfigured"] is True
    assert d["openaiConfigured"] is True
    assert d["database"]["ok"] is True


# ---- Repos list ----
def test_list_repos_contains_cors():
    r = requests.get(f"{BASE_URL}/api/repos", timeout=30)
    assert r.status_code == 200
    repos = r.json()
    assert isinstance(repos, list) and len(repos) >= 1
    cors = next((x for x in repos if "expressjs/cors" in x["name"]), None)
    assert cors and cors["status"] == "ready"


# ---- Chat: grounded ----
def test_chat_grounded_answer(cors_repo_id):
    r = requests.post(
        f"{BASE_URL}/api/repos/{cors_repo_id}/chat",
        json={"question": "How do I configure allowed origins in cors middleware?"},
        timeout=90,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "answer" in d and "citations" in d
    assert isinstance(d["citations"], list) and len(d["citations"]) > 0
    for c in d["citations"]:
        assert "file_path" in c
        assert "start_line" in c and "end_line" in c
        assert "url" in c and "github.com" in c["url"] and "/blob/" in c["url"]
    # Should be about cors
    assert "cors" in d["answer"].lower() or "origin" in d["answer"].lower()


# ---- Chat: anti-hallucination ----
def test_chat_unrelated_question(cors_repo_id):
    r = requests.post(
        f"{BASE_URL}/api/repos/{cors_repo_id}/chat",
        json={"question": "What is the recipe for chocolate cake?"},
        timeout=90,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "couldn't find" in d["answer"].lower() or "could not find" in d["answer"].lower() or "don't know" in d["answer"].lower()


# ---- Chat guards ----
def test_chat_404_nonexistent_repo():
    r = requests.post(
        f"{BASE_URL}/api/repos/00000000-0000-0000-0000-000000000000/chat",
        json={"question": "hi"},
        timeout=30,
    )
    assert r.status_code == 404


def test_chat_400_empty_question(cors_repo_id):
    r = requests.post(
        f"{BASE_URL}/api/repos/{cors_repo_id}/chat",
        json={"question": "   "},
        timeout=30,
    )
    assert r.status_code == 400


# ---- Drift ----
def test_drift_flags_list(cors_repo_id):
    r = requests.get(f"{BASE_URL}/api/repos/{cors_repo_id}/drift", timeout=30)
    assert r.status_code == 200
    flags = r.json()
    assert isinstance(flags, list)
    for f in flags:
        assert "verdict" in f
        assert "severity" in f
        assert "reason" in f


def test_drift_status(cors_repo_id):
    r = requests.get(f"{BASE_URL}/api/repos/{cors_repo_id}/drift/status", timeout=30)
    assert r.status_code == 200
