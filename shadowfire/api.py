import asyncio
from shadowfire.fetch.http import fetch
from shadowfire.extract import process
from shadowfire.extract.document import Document
from shadowfire.crawler.spider import crawl as _crawl


def scrape(url: str) -> Document:
    r = fetch(url)
    doc = process(r.text, url=str(r.url))
    doc.metadata.status_code = r.status_code
    return doc


def crawl(start: str, depth: int = 2, max_pages: int = 50, concurrency: int = 3) -> dict[str, Document]:
    return asyncio.run(_crawl(start, depth=depth, max_pages=max_pages, concurrency=concurrency))
