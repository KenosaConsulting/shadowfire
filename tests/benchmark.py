"""Compare HTML→Markdown extractors on live onion targets.

LLMs run via llama.cpp Q4_K_M GGUFs (Metal on Apple Silicon).
Add a model = one line in MODELS + EXTRACTORS. Similarity is
SequenceMatcher ratio vs the current pipeline's output.
"""
import difflib
import time
from shadowfire.fetch.http import fetch
from shadowfire.extract import process
from shadowfire.extract.cleaner import clean
from shadowfire.guard import sanitize

TARGETS = [
    "http://pzhdfe7jraknpj2qgu5cz2u3i4deuyfwmonvzu5i3nyw4t4bmg7o5pad.onion/",
    "http://jqyzxhjk6psc6ul5jnfwloamhtyh7si74b4743k2qgpskwwxrzhsxmad.onion/",
    "http://xmrhfasfg5suueegrnc4gsgyi2tyclcy5oz7f5drnrodmdtob6t2ioyd.onion/",
]

MODELS: dict = {
    "readerlm-v2": ("mradermacher/ReaderLM-v2-GGUF", "ReaderLM-v2.Q4_K_M.gguf"),
    "qwen3-1.7b":  ("unsloth/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q4_K_M.gguf"),
}
PROMPT = "Extract the main content from this HTML and convert it to clean Markdown.\n```html\n{}\n```"

_models: dict = {}


def _handle(name: str):
    if name not in _models:
        from llama_cpp import Llama
        repo, fname = MODELS[name]
        _models[name] = Llama.from_pretrained(
            repo_id=repo, filename=fname,
            n_ctx=16384, n_gpu_layers=-1, verbose=False,
        )
    return _models[name]


def _llm(name: str, html: str) -> str:
    out = _handle(name).create_chat_completion(
        messages=[{"role": "user", "content": PROMPT.format(sanitize(html)[:8000])}],
        max_tokens=2048, temperature=0,
    )
    return out["choices"][0]["message"]["content"]


EXTRACTORS: dict = {
    "markdownify":    lambda h, u: process(h, url=u).markdown,
    "readerlm/raw":   lambda h, _: _llm("readerlm-v2", h),
    "qwen3/raw":      lambda h, _: _llm("qwen3-1.7b", h),
    "readerlm/clean": lambda h, u: _llm("readerlm-v2", clean(h, page_url=u)),
    "qwen3/clean":    lambda h, u: _llm("qwen3-1.7b", clean(h, page_url=u)),
}


def _sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.split(), b.split()).ratio()


def run():
    for url in TARGETS:
        print(f"\n{url}", flush=True)
        html = fetch(url).text
        ref = EXTRACTORS["markdownify"](html, url)
        print(f"  {'markdownify':<16} {len(ref):>6} chars   (baseline)", flush=True)
        for name, fn in EXTRACTORS.items():
            if name == "markdownify":
                continue
            t0 = time.monotonic()
            try:
                out = fn(html, url)
                ms = int((time.monotonic() - t0) * 1000)
                print(f"  {name:<16} {len(out):>6} chars  {ms:>6}ms  sim={_sim(ref, out):.2f}", flush=True)
            except Exception as e:
                print(f"  {name:<16} FAIL: {e}", flush=True)


if __name__ == "__main__":
    run()
