"""Chunking — turn a file's text into embed-ready pieces with line ranges.

Strategy (v1, deliberately simple):
  * code files  -> split at top-level symbol boundaries (def/class/function/...)
  * doc files   -> split by markdown headings
  * unknown/big -> sliding line window with overlap

Every chunk carries 1-based start/end line numbers so Phase 2 can render exact
"file.py:120-138" citations.

PRODUCTION ALTERNATIVE: use tree-sitter to parse a real AST per language and
chunk on true syntactic nodes (handles nested classes, decorators, comments
correctly). We use regex heuristics here to stay dependency-light; the
trade-off is occasional imperfect boundaries on unusual formatting.
"""
import re
from typing import List, TypedDict

MAX_LINES = 120          # hard cap so a huge function still splits
WINDOW = 80              # fallback window size (lines)
OVERLAP = 15             # fallback overlap so context isn't cut mid-idea
MAX_CHARS = 8000         # keep well under the embedding token limit

DOC_EXTS = {".md", ".mdx", ".markdown", ".rst", ".txt"}

# Lines that begin a new top-level code symbol across common languages.
_BOUNDARY = re.compile(
    r"^\s*(?:"
    r"(?:async\s+)?def\s+|class\s+|"                      # python
    r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+|"  # js/ts
    r"(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\(|"  # js arrow fns
    r"(?:export\s+)?(?:interface|type|enum)\s+|"          # ts types
    r"func\s+|"                                           # go
    r"(?:public|private|protected)\s+"                    # java/c#
    r")"
)


class Chunk(TypedDict):
    start_line: int
    end_line: int
    content: str
    chunk_type: str


def _window_split(lines: List[str], start_offset: int = 0) -> List[tuple]:
    out = []
    i = 0
    n = len(lines)
    while i < n:
        j = min(i + WINDOW, n)
        out.append((start_offset + i + 1, start_offset + j, "\n".join(lines[i:j])))
        if j == n:
            break
        i = j - OVERLAP
    return out


def _split_code(text: str) -> List[tuple]:
    lines = text.split("\n")
    boundaries = [i for i, l in enumerate(lines) if _BOUNDARY.match(l)]
    if not boundaries:
        return _window_split(lines)
    if boundaries[0] != 0:
        boundaries = [0] + boundaries
    ranges = []
    for idx, s in enumerate(boundaries):
        e = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(lines)
        block = lines[s:e]
        if len(block) > MAX_LINES:  # oversized symbol -> window it
            ranges.extend(_window_split(block, start_offset=s))
        else:
            ranges.append((s + 1, e, "\n".join(block)))
    return ranges


def _split_markdown(text: str) -> List[tuple]:
    lines = text.split("\n")
    heading = re.compile(r"^#{1,6}\s")
    heads = [i for i, l in enumerate(lines) if heading.match(l)]
    if not heads:
        return _window_split(lines)
    if heads[0] != 0:
        heads = [0] + heads
    ranges = []
    for idx, s in enumerate(heads):
        e = heads[idx + 1] if idx + 1 < len(heads) else len(lines)
        ranges.append((s + 1, e, "\n".join(lines[s:e])))
    return ranges


def chunk_file(path: str, text: str) -> List[Chunk]:
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    is_doc = ext in DOC_EXTS
    raw = _split_markdown(text) if is_doc else _split_code(text)
    chunks: List[Chunk] = []
    for start, end, content in raw:
        stripped = content.strip()
        if not stripped:
            continue
        chunks.append({
            "start_line": start,
            "end_line": end,
            "content": content[:MAX_CHARS],
            "chunk_type": "doc" if is_doc else "code",
        })
    return chunks
