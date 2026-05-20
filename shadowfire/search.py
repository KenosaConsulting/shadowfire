import asyncio
import re
from urllib.parse import urlencode
from shadowfire.fetch.http import fetch
from shadowfire.guard import safe_url

# (base_url, query_param)  — add engines here, CLI choices update automatically
ENGINES: dict[str, tuple[str, str]] = {
    "torch":      ("http://torchdeecx7spcubonhjsuqz4pv3twne4zd5l63tqnxtk2ncvptrllqd.onion/", "q"),
    "tor66":      ("http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search/", "q"),
    "onionland":  ("http://3bbad7fau4ui3pz2fh7wij3oj7wa5oqc45il5q3thddpp3xlfcr4ekqd.onion/", "q"),
    "notevil":    ("http://notevil2xua3sacjtyvxqpi2vxkk7mqcedq7hhmhncaeszttuwfz2rqd.onion/search", "q"),
    "haystak":    ("", "q"),  # address rotates — update when current .onion is known
    "ahmia":      ("", "q"),  # JS-gated; fix: Playwright/Chromium on .onion (see decisions.md)
}

_ONION_RE = re.compile(r'https?://[a-z2-7]{10,56}\.onion[^\s"<>\']*')
_NOISE_RE = re.compile(r'/banners/|[?&]bads=|banner-click|/advertising/|\.(gif|png|jpg|webp|css|js)([?#]|$)')


def search_all(query: str, engines: list[str] | None = None, limit: int = 20) -> list[str]:
    """Search multiple engines in parallel, deduplicate results."""
    selected = engines or list(ENGINES)
    targets = [e for e in selected if ENGINES.get(e, ("",))[0]]
    use_ahmia = "ahmia" in selected

    async def _gather():
        tasks = [asyncio.to_thread(search, query, engine=e, limit=limit) for e in targets]
        if use_ahmia:
            tasks.append(asyncio.to_thread(search_browser, query, limit))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [u for r in results if not isinstance(r, Exception) for u in r]

    return list(dict.fromkeys(asyncio.run(_gather())))


def search_browser(query: str, limit: int = 20) -> list[str]:
    """Chromium-rendered Ahmia search — bypasses @-moz-document MITM detection."""
    import asyncio
    from shadowfire.fetch.browser import fetch as browser_fetch
    AHMIA_ONION = "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/"
    html = asyncio.run(browser_fetch(f"{AHMIA_ONION}?q={query.replace(' ', '+')}", engine="chromium"))
    seen, results = set(), []
    for u in _ONION_RE.findall(html):
        norm = u.rstrip("/")
        if norm not in seen and safe_url(u) and "juhanurmihxlp" not in u and not _NOISE_RE.search(u):
            seen.add(norm)
            results.append(norm)
    return results[:limit]


def search(query: str, engine: str = "torch", limit: int = 20) -> list[str]:
    base, param = ENGINES[engine]
    if not base:
        raise ValueError(f"'{engine}' has no URL configured — add it to ENGINES in shadowfire/search.py")
    r = fetch(f"{base}?{urlencode({param: query})}")
    base_host = re.search(r'//([^/]+)', base).group(1)[:12]
    seen, results = set(), []
    for u in _ONION_RE.findall(r.text):
        norm = u.rstrip("/")
        if norm not in seen and safe_url(u) and base_host not in u and not _NOISE_RE.search(u):
            seen.add(norm)
            results.append(norm)
    return results[:limit]
