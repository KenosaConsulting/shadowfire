# ShadowFire

Firecrawl for the deep web. Crawls `.onion` sites over Tor and returns clean, LLM-ready Markdown — with a zero-trust security layer, multi-engine dark web search, a curated seed database, and an LLM-driven deep research pipeline.

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
            ├── fetch/browser.py       — Playwright/Firefox+Chromium fallback for JS-heavy pages
            │
            ├── extract/               — Firecrawl-parity extraction pipeline
            │       ├── cleaner.py     — 42-selector noise removal, main content isolation
            │       ├── metadata.py    — title, OG, Dublin Core, custom meta tags
            │       └── converter.py   — GFM Markdown + Firecrawl post-processing
            │
            ├── crawler/
            │       ├── spider.py      — async BFS, .onion link filter + SSRF guard
            │       └── mapper.py      — lightweight URL discovery (no content, anchor text)
            │
            ├── search.py              — multi-engine fan-out (torch, tor66, onionland, notevil)
            │
            ├── sources/
            │       └── directories.py — dynamic directory seeding (Hidden Wiki navigation)
            │
            ├── llm/                   — small-LLM tier (llama.cpp + Q4_K_M GGUF, Metal)
            │       ├── triage()       — Qwen3-1.7B: page_type + language (<1s, inline-safe)
            │       ├── enrich()       — ReaderLM-v2: schema-driven JSON extraction (async)
            │       ├── expand()       — Qwen3-8B: research goal → N search queries
            │       ├── filter_urls()  — Qwen3-8B: select relevant URLs from inventory
            │       ├── synthesize()   — Qwen3-8B: crawled docs → research summary
            │       └── SCHEMAS        — 8 page types, dispatched via auto()
            │
            ├── api.py                 — scrape() + crawl() + map() public surface
            │
            └── store.py               — DuckDB persistence (data/shadowfire.db)
                                         tables: runs, pages, sources
```

**Extraction** mirrors Firecrawl's pipeline: nh3 sanitization → BS4 noise removal → markdownify GFM conversion → Rust-equivalent post-processing. Output schema matches Firecrawl's `Document` type.

**Security** is zero-trust by default: every page is sanitized before parsing, every discovered link is SSRF-checked before queuing, and every markdown output can be scanned and wrapped before LLM consumption.

## Requirements

- Python 3.11+
- Tor (`brew install tor` on macOS, `sudo apt install tor` on Linux)
- Playwright browsers (`playwright install firefox chromium`)

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
pip install -e .
playwright install firefox chromium
```

**4. Initialise the database**

```bash
shadowfire init-db
```

Creates `data/shadowfire.db` with `runs`, `pages`, and `sources` tables. Safe to re-run.

## Usage

### CLI

```bash
# Single page → Markdown on stdout
shadowfire scrape http://example.onion/

# Force Playwright rendering (JS-heavy SPAs); auto-triggered when content < 200 chars
shadowfire scrape --js http://example.onion/

# Scan for prompt injection and wrap output for LLM consumption
shadowfire scrape --guard http://example.onion/

# BFS crawl — summary table (URL / HTTP / chars / title)
shadowfire crawl http://example.onion/ --depth 2 --max-pages 50 --concurrency 3

# Discover all internal URLs on a site (no content fetch)
shadowfire map http://example.onion/ --depth 2 --max-urls 200

# Search dark web indexes and return seed URLs
shadowfire search "research chemicals" --engine tor66
shadowfire search "research chemicals" --engine torch --crawl --depth 1

# Full deep research pipeline (expand → search → map → filter → scrape → synthesize)
shadowfire research "research chemical manufacturing" --engines all
shadowfire research "aliens" --engines torch,tor66 --no-synthesize
shadowfire research "goal" --no-crawl   # print expanded queries only
```

### Search engines

| Engine | URL | Notes |
|---|---|---|
| `torch` | `.onion` | Veteran dark web index |
| `tor66` | `.onion` | Best result volume |
| `onionland` | `.onion` | Independent index |
| `notevil` | `.onion` | Small index, clean results |
| `ahmia` | `.onion` | JS-rendered; needs Chromium path |
| `haystak` | — | Address rotates; update `ENGINES["haystak"]` when known |

Add a new engine: one line in `search.py`'s `ENGINES` dict. Automatically included in `--engines all`.

### Research pipeline

`shadowfire research` runs a six-stage pipeline:

```
expand      Qwen3-8B    goal → N free-form queries
search      all engines queries → seed URLs (parallel fan-out)
map         httpx       seeds → internal URL inventory with anchor text
filter      Qwen3-8B    inventory + goal → targeted URL list
scrape      httpx/PW    targeted URLs → Documents (depth=0)
synthesize  Qwen3-8B    all pages × title+200chars → research summary
```

First run downloads ~5GB of Qwen3-8B weights (Q4_K_M, cached in HF). Metal acceleration on Apple Silicon.

### Seed database

`data/shadowfire.db` includes a `sources` table — a curated inventory of categorised `.onion` sites bootstrapped from the Hidden Wiki. The research pipeline merges these seeds with live search results before mapping.

```python
from shadowfire.store import upsert_source, get_sources

upsert_source("http://example.onion/", name="Example", category="forum")
seeds = get_sources()  # all sources
```

Categories currently seeded: `darknet_market`, `drugs`, `forum`, `search`.

### Python API

```python
from shadowfire.api import scrape, crawl, map
from shadowfire.guard import has_injection, wrap
from shadowfire.llm import expand, filter_urls, synthesize

# Single page
doc = scrape("http://example.onion/")
doc = scrape("http://example.onion/", js=True)  # force browser render

# BFS crawl — multi-seed support
results = crawl(["http://a.onion/", "http://b.onion/"], depth=1, max_pages=30)

# URL inventory (no content)
urls = map("http://example.onion/", depth=2, max_urls=200)
urls = map("http://example.onion/", include_text=True)  # anchor | url format

# Injection guard
if not has_injection(doc.markdown):
    llm_input = wrap(doc.markdown)

# LLM research tier
queries  = expand("research chemical synthesis", n=6)
targeted = filter_urls("goal", inventory, n=20, hint="optional context")
summary  = synthesize("goal", results)
```

### JS rendering

`fetch/browser.py` wraps Playwright through the Tor SOCKS5 proxy. Firefox is the default (matches Tor Browser fingerprint). Chromium is available for sites that use `@-moz-document` to block Firefox (e.g. Ahmia's `.onion`).

Auto-triggers in both `scrape()` and the crawler when httpx yields fewer than 200 chars of Markdown.

### LLM tier

| Function | Model | Size | Warm latency | License |
|---|---|---|---:|---|
| `triage` | Qwen3-1.7B | ~1GB | ~700ms | Apache 2.0 |
| `enrich` | ReaderLM-v2 | ~1GB | ~5–30s | CC-BY-NC-4.0 |
| `expand` / `filter_urls` / `synthesize` | Qwen3-8B | ~5GB | ~5–30s | Apache 2.0 |

All models run locally via llama.cpp with Metal acceleration. First call downloads weights to HF cache; subsequent calls reuse the loaded handle.

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

**`sources`** — curated seed inventory

| Column | Type | Description |
|---|---|---|
| `url` | VARCHAR | `.onion` URL |
| `name` | VARCHAR | Human-readable name |
| `category` | VARCHAR | darknet_market, drugs, forum, search, … |
| `added_at` | TIMESTAMP | When seeded |

**`pages`** — one row per scraped page

| Column | Type | Description |
|---|---|---|
| `url` | VARCHAR | Final URL after redirects |
| `status_code` | INTEGER | HTTP response code |
| `fetch_ms` | INTEGER | Wall-clock fetch latency |
| `markdown_chars` | INTEGER | Extracted Markdown size |
| `title` | VARCHAR | Page title |
| `injection_detected` | BOOLEAN | DeBERTa classifier result |
| `circuit_id` | VARCHAR | Tor circuit used |
| `exit_fingerprint` | VARCHAR | Exit relay fingerprint |
| `page_type` | VARCHAR | LLM triage classification |
| `language` | VARCHAR | ISO-639-1 language code |

## Linux / Raspberry Pi

Same `torrc`. Two changes:
- `brew services start tor` → `sudo systemctl enable --now tor`
- Cookie path in `shadowfire/tor/proxy.py`: `/opt/homebrew/var/lib/tor/control_auth_cookie` → `/var/lib/tor/control_auth_cookie`

## Decisions & Roadmap

- [`docs/decisions.md`](docs/decisions.md) — architectural decisions, deferred features, upgrade paths
- [`docs/llm-tier.md`](docs/llm-tier.md) — LLM tier design, benchmark results, license posture

Deferred features:
- **`--deep` mode** — per-page map-reduce synthesis for exhaustive single-site analysis
- **Multi-engine fan-out for directories** — parallel Hidden Wiki category navigation
- **Parallel Tor circuits** — multiple `SOCKSPort` entries for concurrent crawling
- **NEWNYM retry** — circuit rotation wired into the crawler's retry ladder
- **PII stripping** — presidio-analyzer before scraped content enters LLM context
- **`enrich` model swap** — replace ReaderLM-v2 (CC-BY-NC) with Apache/MIT before commercial use
