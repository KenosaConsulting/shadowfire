import asyncio
from shadowfire.fetch.http import fetch
from shadowfire.fetch.browser import fetch as browser_fetch
from shadowfire.extract import process
from shadowfire.extract.document import Document
from shadowfire.crawler.spider import crawl as _crawl
from shadowfire.crawler.mapper import map_site as _map_site
from shadowfire.search import search  # noqa: F401 — re-exported

_SPARSE = 200


def scrape(url: str, js: bool = False) -> Document:
    r = fetch(url)
    doc = process(r.text, url=str(r.url))
    doc.metadata.status_code = r.status_code
    if js or len((doc.markdown or "").strip()) < _SPARSE:
        raw = asyncio.run(browser_fetch(url))
        doc = process(raw, url=url)
        doc.metadata.status_code = r.status_code
    return doc


def map(url: str, depth: int = 2, max_urls: int = 200, include_text: bool = False) -> list[str]:
    return asyncio.run(_map_site(url, depth=depth, max_urls=max_urls, include_text=include_text))


def crawl(start: str | list[str], depth: int = 2, max_pages: int = 50, concurrency: int = 3) -> dict[str, Document]:
    return asyncio.run(_crawl(start, depth=depth, max_pages=max_pages, concurrency=concurrency))
