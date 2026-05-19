# LLM Tier — Session Notes (2026-05-19)

Goal: add small-LLM capabilities for jobs the deterministic pipeline can't do, without slowing the hot path.

## TL;DR

- Fixed a silent bug that broke crawl depth>0 on `.onion` targets.
- Built `shadowfire/llm/` — two public functions (`triage`, `enrich`) and a schema dispatcher (`auto`).
- Persisted `page_type` and `language` on every scraped page; wired `triage()` into the loop.
- Benchmarked four small LLMs across two runtimes; chose **Qwen3-1.7B** (triage) and **ReaderLM-v2** (enrich), both Q4_K_M GGUFs running on Metal via llama.cpp.
- Concluded LLM-based markdown extraction does **not** beat markdownify; LLMs earn their keep on classification + structured-data jobs only.

## Files touched

| File | Change |
|---|---|
| `shadowfire/guard.py` | `safe_url()` now short-circuits `.onion` hosts to `True` — hidden services have no routable IP, so the SSRF check is N/A. Previously `gethostbyname()` raised `gaierror` on every onion, silently rejecting all discovered links from the BFS crawler. |
| `shadowfire/store.py` | Two additive migrations: `page_type VARCHAR`, `language VARCHAR`. `insert_page()` signature extended with matching kwargs (default `None`); existing callers unaffected. |
| `shadowfire/llm/__init__.py` | **New module.** `MODELS` dict maps task → (HF repo, GGUF filename). `triage()` returns `{page_type, language, thin}`. `enrich()` takes content + JSON schema, returns extracted dict. `SCHEMAS` covers 8 page types. `CAPS` lets per-type input/output token caps override defaults. `auto(content, page_type)` dispatches to the right schema and caps. |
| `tests/benchmark.py` | **New file.** Head-to-head HTML→Markdown extractor harness. Five extractors (markdownify baseline + two LLMs × {raw HTML, cleaned HTML}). Uses `difflib.SequenceMatcher` for similarity scoring vs baseline. |
| `tests/loop.py` | Imports `triage`; calls it after each scrape and persists `page_type`/`language` via the new `insert_page` kwargs. Try/except so an LLM crash can't take down a long run. Status line now shows page type + language inline. |

## Decisions

### Triage model: Qwen3-1.7B (Apache 2.0)

Tested Gemma 3 270M, Qwen3 0.6B, and Qwen3 1.7B on a 7-case onion-page classification eval:

| Model | Score | Warm latency | Cache size |
|---|---:|---:|---:|
| Gemma 3 270M Q4 | 1/7 | 280ms | 253 MB |
| Qwen3 0.6B Q4 | 2/7 | ~400ms | 378 MB |
| **Qwen3 1.7B Q4** | **4–6/7** | **~700ms** | **1.1 GB** |

The 1.7B step quadruples cache size and adds ~400ms warm latency, but accuracy was the requirement. Bonus: Apache 2.0 keeps every future commercial scenario open.

### Extraction model: keep markdownify

Benchmark across two runtimes on 3 onion pages:

| Runtime | Avg time/page | Avg sim vs markdownify | Best single sim |
|---|---:|---:|---:|
| transformers fp32 MPS | 142s | 0.50 | 0.59 |
| **llama.cpp Q4_K_M Metal** | **33s** | **0.69 (readerlm/clean)** | **0.91** |

ReaderLM-v2 + pre-cleaning matches markdownify at best (sim=0.91) but never beats it — and markdownify runs in milliseconds. **Verdict: LLM-based extraction earns its keep only for jobs markdownify physically cannot do** — schema-driven structured extraction, classification, summarization, entity extraction.

### Schema design

8 page types: `blog`, `blog_index`, `forum`, `market`, `docs`, `index`, `phishing`, `other`. Each schema kept compact via a `_schema()` helper that collapses JSON-Schema boilerplate. Per-type input/output token caps (`CAPS`) tightened `index` and `blog_index` after observing degeneration / truncation on those shapes. ReaderLM-v2 needs `repeat_penalty=1.2` to avoid looping when schema constraints leave string fields unbounded.

### License posture

| Layer | Model | License | Production-safe? |
|---|---|---|---|
| Triage | Qwen3-1.7B | Apache 2.0 | ✓ |
| Enrich | ReaderLM-v2 Q4 (mradermacher GGUF) | CC-BY-NC-4.0 | research only |

If shadowfire ships as a product, `MODELS["enrich"]` must swap to an Apache/MIT alternative. Module docstring flags this.

## Open issues

- **Forum schema** produces valid JSON but empty `subforums`/`recent_thread_titles` arrays and an oddly-named `name_category_count` key — suspect content slicing or a ReaderLM quirk, not a token-cap issue.
- **Backfill**: 126 pages already in DuckDB lack `page_type`/`language`. A small re-triage loop would populate them.
- **Single-post `blog` vs `blog_index` boundary**: triage can't always distinguish a single post from a landing page from markdown alone; URL pattern or post-count heuristic would tighten this.

## Stats

- ~100 lines of new production code (`llm/__init__.py` + edits).
- ~60 lines of new bench/test code (`benchmark.py` + loop wiring).
- One critical bug fixed (`.onion` SSRF check).
- Two new persistent DuckDB columns.
