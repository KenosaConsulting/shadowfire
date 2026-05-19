import asyncio
from shadowfire.fetch.http import fetch
from shadowfire.extract import process
from shadowfire.extract.document import Document
from shadowfire.guard import safe_url


def _onion_links(doc: Document, visited: set) -> list[str]:
    return [
        l for l in doc.links
        if ".onion" in l and l not in visited and safe_url(l)
    ]


async def _fetch_one(url: str, sem: asyncio.Semaphore) -> tuple[str, Document | Exception]:
    async with sem:
        try:
            r = await asyncio.to_thread(fetch, url)
            doc = process(r.text, url=str(r.url))
            doc.metadata.status_code = r.status_code
            return url, doc
        except Exception as e:
            return url, e


async def crawl(start: str, depth: int = 2, max_pages: int = 50, concurrency: int = 3) -> dict[str, Document]:
    visited: set[str] = set()
    results: dict[str, Document] = {}
    sem = asyncio.Semaphore(concurrency)
    frontier = [(start, 0)]

    while frontier and len(results) < max_pages:
        url, d = frontier.pop(0)
        if url in visited:
            continue
        visited.add(url)

        _, doc = await _fetch_one(url, sem)
        if isinstance(doc, Exception):
            continue

        results[url] = doc
        if d < depth:
            frontier.extend((l, d + 1) for l in _onion_links(doc, visited))

    return results
