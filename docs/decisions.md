# ShadowFire — Decision Log

Architectural decisions, deferred features, and the reasoning behind them.
Format: newest first.

---

## [2026-05-19] Heuristic prompt injection detection — ML classifier deferred

**Decision:** Use regex heuristics for prompt injection detection. Do not pull in `llm-guard` yet.

**Rationale:**
- `llm-guard`'s DeBERTa classifier (`ProtectAI/deberta-v3-base-prompt-injection-v2`) is the best OSS option but requires PyTorch or ONNX runtime — significant dependency weight for a scraping pipeline.
- `rebuff` is abandoned (Jan 2024) and requires Pinecone + OpenAI API keys at runtime — wrong for an offline Tor crawler.
- `guardrails-ai` is currently quarantined on PyPI.
- OWASP LLM01:2025 acknowledges no foolproof prevention exists; defense-in-depth (sanitize → detect → wrap) is the canonical baseline.

**When to revisit:**
- When feeding scraped content to an LLM in production where missed injections have real consequences.
- When the pipeline has a GPU or ONNX runtime available.

**Upgrade path:**
1. `pip install llm-guard` with ONNX backend (`USE_ONNX=true`).
2. Replace `has_injection()` regex in `guard.py` with `llm_guard.input_scanners.PromptInjection` + `InvisibleText` scanners.
3. Add `presidio-analyzer` for PII stripping if scraped content feeds a RAG system.

---

## [2026-05-19] Defer Playwright browser layer — HTTP-only fetcher for now

**Decision:** Use `httpx` with `follow_redirects=True` as the sole fetch layer.
Do not integrate Playwright yet.

**Rationale:**
- The majority of `.onion` sites serve static or server-rendered HTML — no JS execution required.
- Playwright spins up a full Firefox process per render, adding ~2–5s cold-start overhead and significant memory pressure per worker. On Tor (already 1–5s latency per hop), the cost is proportionally large.
- An httpx-only pipeline is simpler to reason about, easier to debug, and sufficient to prove the extraction and crawl layers correct.

**When to revisit:**
- Encountering `.onion` sites that return a JS-only shell (thin HTML, no meaningful text after extraction).
- Implementing login flows, form submission, or pagination driven by client-side state.
- A `content_is_thin()` heuristic can gate the fallback automatically once Playwright is added.

**Upgrade path (when ready):**
1. Add `fetch/browser.py` — `async def render(url, socks_port) -> str` using `playwright.async_api`.
2. Use Firefox (not Chromium) — Firefox resolves `.onion` DNS through the SOCKS5 proxy natively; Chromium leaks DNS to the host resolver.
3. In `fetch/__init__.py`, expose a `fetch(url, force_browser=False)` dispatcher that tries httpx first, falls back to Playwright if `content_is_thin(html)`.

---
