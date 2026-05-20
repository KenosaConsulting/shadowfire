import asyncio
import warnings
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from shadowfire.fetch.http import fetch
from shadowfire.guard import safe_url

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


async def _links(url: str, sem: asyncio.Semaphore) -> list[tuple[str, str]]:
    """Return (anchor_text, url) pairs for same-host internal links."""
    async with sem:
        try:
            r = await asyncio.to_thread(fetch, url)
            host = urlparse(url).netloc
            soup = BeautifulSoup(r.text, "lxml")
            return [
                (a.get_text(" ", strip=True)[:40], href)
                for a in soup.find_all("a", href=True)
                if (href := urljoin(url, a["href"]))
                and urlparse(href).netloc == host
                and safe_url(href)
            ]
        except Exception:
            return []


async def map_site(start: str, depth: int = 2, max_urls: int = 200,
                   include_text: bool = False) -> list[str]:
    visited: set[str] = set()
    found: dict[str, str] = {}  # url → anchor text
    frontier = [(start, 0)]
    sem = asyncio.Semaphore(5)

    while frontier and len(found) < max_urls:
        url, d = frontier.pop(0)
        if url in visited:
            continue
        visited.add(url)
        for text, href in await _links(url, sem):
            if href not in found:
                found[href] = text
        if d < depth:
            frontier.extend((l, d + 1) for l in found if l not in visited)

    if include_text:
        return [f"{text} | {url}" if text else url for url, text in list(found.items())[:max_urls]]
    return list(found)[:max_urls]
