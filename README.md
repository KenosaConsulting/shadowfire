# ShadowFire

Firecrawl for the deep web. Crawls `.onion` sites over Tor and returns clean, LLM-ready Markdown — with a zero-trust security layer, circuit telemetry, and persistent analytics storage.

## Architecture

```
TorController (stem)            — Tor process lifecycle, NEWNYM circuit rotation,
    │                             active circuit + exit node telemetry
    └── SOCKS5 @ 127.0.0.1:9050
            │
            ├── guard.py               — zero-trust layer (runs first, always)
            │       ├── sanitize()     — nh3 allowlist: strips scripts/iframes/events
            │       ├── safe_url()     — SSRF: blocks RFC1918/loopback before following links
            │       ├── has_injection() — invisible-text pre-check + DeBERTa ML classifier
            │       └── wrap()         — <untrusted_source> boundary for LLM consumption
            │
            ├── fetch/http.py          — httpx SOCKS5 client, follow redirects
            │
            ├── extract/               — Firecrawl-parity extraction pipeline
            │       ├── cleaner.py     — 42-selector noise removal, main content isolation
            │       ├── metadata.py    — title, OG, Dublin Core, custom meta tags
            │       └── converter.py   — GFM Markdown + Firecrawl post-processing
            │
            ├── crawler/spider.py      — async BFS, .onion link filter + SSRF guard
            │
            ├── llm/                   — small-LLM tier (llama.cpp + Q4_K_M GGUF, Metal)
            │       ├── triage()       — Qwen3-1.7B: page_type + language (<1s, inline-safe)
            │       ├── enrich()       — ReaderLM-v2: schema-driven JSON extraction (async)
            │       └── SCHEMAS        — 8 page types, dispatched via auto()
            │
            ├── api.py                 — scrape() + crawl() public surface
            │
            └── store.py               — DuckDB persistence (data/shadowfire.db)
```

**Extraction** mirrors Firecrawl's pipeline: nh3 sanitization → BS4 noise removal → markdownify GFM conversion → Rust-equivalent post-processing. Output schema matches Firecrawl's `Document` type.

**Security** is zero-trust by default: every page is sanitized before parsing, every discovered link is SSRF-checked before queuing, and every markdown output can be scanned and wrapped before LLM consumption.

## Requirements

- Python 3.11+
- Tor (`brew install tor` on macOS, `sudo apt install tor` on Linux)
- DuckDB Python package (installed with the project; creates a local `data/shadowfire.db` file)

## Stack

- `shadowfire/store.py` uses DuckDB for local persistence and analytics
- `data/shadowfire.db` is the default local database file
- The database file is ignored by Git so each user gets their own local copy
- `shadowfire.store.init()` creates the tables and applies additive migrations
- The test scripts call `init()` automatically before writing results

## Setup

**1. Configure Tor**

`/opt/homebrew/etc/tor/torrc` (macOS) or `/etc/tor/torrc` (Linux):

```
SOCKSPort 9050
ControlPort 9051
CookieAuthentication 1
```

**2. Start Tor**

```bash
# macOS
brew services start tor

# Linux
sudo systemctl enable --now tor
```

**3. Install**

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

**4. Create your local DuckDB**

```bash
python3 -c "from shadowfire.store import init; init()"
```

This creates `data/shadowfire.db` and the `runs` / `pages` tables if they do not exist yet. If you want to reset the local database, delete `data/shadowfire.db` and run the command again.

## Usage

```python
from shadowfire.api import scrape, crawl
from shadowfire.guard import has_injection, wrap

# Single page
doc = scrape("http://example.onion/")
print(doc.metadata.title)
print(doc.markdown)

# Check for prompt injection before passing to an LLM
if not has_injection(doc.markdown):
    llm_input = wrap(doc.markdown)

# BFS crawl — returns {url: Document}
results = crawl("http://example.onion/", depth=2, max_pages=50)
```

### LLM tier

Small open-source models (llama.cpp Q4_K_M GGUFs, Metal on Apple Silicon) for jobs the deterministic pipeline can't do. First call per model downloads ~1.1 GB of weights into the HF cache; subsequent calls reuse the loaded handle.

```python
from shadowfire.llm import triage, enrich, auto, SCHEMAS

# Fast page classification — <1s warm, inline-safe
t = triage(doc.markdown, title=doc.metadata.title)
# → {'page_type': 'forum', 'language': 'en', 'thin': False}

# Schema-driven structured extraction — ~5-30s, async-only
data = enrich(doc.markdown, schema=SCHEMAS["forum"])
# → {'name': ..., 'subforums': [...], 'recent_thread_titles': [...]}

# Dispatcher: pick the schema + token caps by page_type
data = auto(doc.markdown, t["page_type"])
```

| Function | Model | Warm latency | License |
|---|---|---:|---|
| `triage` | Qwen3-1.7B | ~700ms | Apache 2.0 |
| `enrich` | ReaderLM-v2 | ~5-30s | CC-BY-NC-4.0 (research only) |


### `Document` fields

| Field | Type | Description |
|---|---|---|
| `markdown` | `str` | Clean GFM Markdown |
| `html` | `str` | Cleaned HTML (post noise removal) |
| `raw_html` | `str` | Raw HTML as fetched |
| `links` | `list[str]` | All absolute hrefs |
| `images` | `list[str]` | All image URLs (no `data:` URIs) |
| `metadata` | `Metadata` | Title, OG, Dublin Core, status code, etc. |

### Security layer

| Function | Threat | When to call |
|---|---|---|
| `sanitize(html)` | Scripts, iframes, event handlers | Automatic — wired into the pipeline |
| `safe_url(url)` | SSRF, RFC1918 traversal | Automatic — wired into the crawler |
| `has_injection(text)` | Prompt injection | Before passing `doc.markdown` to an LLM |
| `wrap(text)` | LLM instruction following | Before passing `doc.markdown` to an LLM |

## Storage schema

Results persist to `data/shadowfire.db` (DuckDB) across all runs.

The file is local to your machine and not tracked in Git. If it is missing, `shadowfire.store.init()` will recreate it and initialize the schema.

**`runs`** — one row per test execution

| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | UUID |
| `started_at` / `ended_at` | TIMESTAMP | Run window |
| `config` | JSON | Target list, depth, concurrency |

**`pages`** — one row per scraped page

| Column | Type | Description |
|---|---|---|
| `url` | VARCHAR | Final URL after redirects |
| `status_code` | INTEGER | HTTP response code |
| `fetch_ms` | INTEGER | Wall-clock fetch latency |
| `html_bytes` | INTEGER | Raw HTML size |
| `markdown_chars` | INTEGER | Extracted Markdown size |
| `link_count` | INTEGER | Discovered outbound links |
| `image_count` | INTEGER | Discovered images |
| `title` | VARCHAR | Page title |
| `content_type` | VARCHAR | Server-reported content type |
| `injection_detected` | BOOLEAN | DeBERTa classifier result |
| `circuit_id` | VARCHAR | Tor circuit used |
| `exit_fingerprint` | VARCHAR | Exit relay fingerprint |
| `exit_nickname` | VARCHAR | Exit relay nickname |
| `page_type` | VARCHAR | LLM triage classification (blog, forum, market, docs, index, phishing, other) |
| `language` | VARCHAR | LLM-detected ISO-639-1 language code |
| `error` | VARCHAR | Exception message if fetch failed |

## Testing

```bash
# Full capability stress test (fetch, extraction, security, crawl suites)
.venv/bin/python3 tests/stress.py

# Multi-run loop — random targets, circuit + page-type + language telemetry
.venv/bin/python3 tests/loop.py --runs 20

# Head-to-head extractor benchmark (markdownify vs ReaderLM-v2 vs Qwen3-1.7B, GGUF on Metal)
.venv/bin/python3 tests/benchmark.py

# Example analytical queries
python3 -c "
from shadowfire.store import _conn
with _conn() as con:
    # Latency distribution
    print(con.execute('''
        SELECT COUNT(*) pages, AVG(fetch_ms)::INT avg_ms,
               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY fetch_ms)::INT p95_ms
        FROM pages
    ''').fetchone())

    # Exit node performance
    print(con.execute('''
        SELECT exit_nickname, COUNT(*) pages, AVG(fetch_ms)::INT avg_ms
        FROM pages WHERE exit_nickname IS NOT NULL
        GROUP BY exit_nickname ORDER BY avg_ms
    ''').fetchall())
"
```

## Linux / Raspberry Pi

Same `torrc` content. Two changes in code:
- `brew services start tor` → `sudo systemctl enable --now tor`
- Cookie path in `shadowfire/tor/proxy.py`: `/opt/homebrew/var/lib/tor/control_auth_cookie` → `/var/lib/tor/control_auth_cookie`

## Decisions & Roadmap

- [`docs/decisions.md`](docs/decisions.md) — architectural decisions, deferred features, upgrade paths
- [`docs/llm-tier.md`](docs/llm-tier.md) — small-LLM tier: triage, enrich, schema design, benchmark results, license posture

Deferred features:
- **Playwright browser layer** — for JS-heavy sites that return thin content
- **Parallel Tor circuits** — multiple `SOCKSPort` entries for concurrent crawling
- **NEWNYM retry integration** — circuit rotation wired into the crawler's retry ladder
- **PII stripping** — presidio-analyzer before scraped content enters LLM context
- **`enrich` model swap** — replace ReaderLM-v2 (CC-BY-NC) with an Apache/MIT alternative before any commercial deployment
