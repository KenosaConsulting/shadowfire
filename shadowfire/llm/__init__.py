"""LLM tier — small models for jobs the deterministic pipeline can't do.

triage()  — Gemma 3 270M: page type + language (<1s/page, inline-safe).
enrich()  — ReaderLM-v2:  schema-driven JSON extraction (~30s/page, async-only).

License: ReaderLM-v2 weights are CC-BY-NC-4.0. For commercial deployment,
swap MODELS["enrich"] to an Apache/MIT alternative.
"""
import json
from llama_cpp import Llama

MODELS: dict = {
    "triage": ("unsloth/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q4_K_M.gguf"),
    "enrich": ("mradermacher/ReaderLM-v2-GGUF", "ReaderLM-v2.Q4_K_M.gguf"),
}

PAGE_TYPES = ["blog", "blog_index", "forum", "market", "docs", "index", "phishing", "other"]

_TYPE_DEFS = (
    "blog: a single dated post or article\n"
    "blog_index: a landing page listing multiple blog posts\n"
    "forum: user discussion threads with replies\n"
    "market: listings of items or services for sale\n"
    "docs: technical documentation, dashboards, status pages, project descriptions\n"
    "index: directory listings or link aggregators\n"
    "phishing: deceptive content imitating another service\n"
    "other: anything not fitting above"
)

_TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "page_type": {"type": "string", "enum": PAGE_TYPES},
        "language": {"type": "string", "pattern": "^[a-z]{2}$"},
    },
    "required": ["page_type", "language"],
    "additionalProperties": False,
}

_handles: dict = {}


def _llm(name: str, n_ctx: int = 8192) -> Llama:
    if name not in _handles:
        repo, fname = MODELS[name]
        _handles[name] = Llama.from_pretrained(
            repo_id=repo, filename=fname,
            n_ctx=n_ctx, n_gpu_layers=-1, verbose=False,
        )
    return _handles[name]


def _json(text: str, default: dict) -> dict:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return default


def triage(markdown: str, title: str = "") -> dict:
    """Classify page_type + language; flag thin content. Target: <1s/page."""
    thin = len(markdown.strip()) < 200
    out = _llm("triage", n_ctx=2048).create_chat_completion(
        messages=[{"role": "user", "content":
            f"Classify this page into one type:\n{_TYPE_DEFS}\n\n"
            f"Title: {title}\n\nContent:\n{markdown[:1000]}"}],
        max_tokens=64, temperature=0,
        response_format={"type": "json_object", "schema": _TRIAGE_SCHEMA},
    )["choices"][0]["message"]["content"]
    return {**_json(out, {"page_type": "other", "language": "und"}), "thin": thin}


def enrich(content: str, schema: dict, max_in: int = 12000, max_tokens: int = 2048) -> dict:
    """Schema-driven JSON extraction. Content may be markdown or cleaned HTML."""
    out = _llm("enrich", n_ctx=16384).create_chat_completion(
        messages=[{"role": "user", "content":
            f"Extract data matching this JSON schema:\n{json.dumps(schema)}\n\n"
            f"Content:\n{content[:max_in]}"}],
        max_tokens=max_tokens, temperature=0, repeat_penalty=1.2,
        response_format={"type": "json_object"},
    )["choices"][0]["message"]["content"]
    return _json(out, {})


def _schema(req: list[str], **props) -> dict:
    def f(v):
        if isinstance(v, list): return {"type": "array", "items": f(v[0])}
        if isinstance(v, dict): return {"type": "object", "properties": {k: f(vv) for k, vv in v.items()}}
        return {"type": v}
    return {"type": "object", "properties": {k: f(v) for k, v in props.items()}, "required": req}


SCHEMAS: dict = {
    "blog":       _schema(["title", "summary"], title="string", author="string", published="string", summary="string", tags=["string"]),
    "blog_index": _schema(["posts"], title="string", posts=[{"title": "string", "published": "string", "summary": "string"}]),
    "forum":      _schema(["name"], name="string", category_count="integer", subforums=["string"], recent_thread_titles=["string"]),
    "market":     _schema(["name"], name="string", currency="string", categories=["string"], listings=[{"title": "string", "price": "string", "vendor": "string"}]),
    "docs":       _schema(["title", "summary"], title="string", project="string", summary="string", sections=["string"]),
    "index":      _schema(["entries"], title="string", entries=[{"name": "string", "kind": "string", "modified": "string"}]),
    "phishing":   _schema(["summary"], impersonating="string", indicators=["string"], summary="string"),
    "other":      _schema(["summary"], title="string", summary="string", entities=["string"]),
}

# Per-page-type input/output token caps; defaults (12000, 2048) for unlisted types.
# Listings (index, blog_index) need more output headroom for array entries.
CAPS: dict = {"index": (4000, 4096), "blog_index": (10000, 3072)}


def auto(content: str, page_type: str) -> dict:
    """Run enrich() with the schema and caps matched to page_type."""
    max_in, max_tokens = CAPS.get(page_type, (12000, 2048))
    return enrich(content, SCHEMAS.get(page_type, SCHEMAS["other"]), max_in, max_tokens)
