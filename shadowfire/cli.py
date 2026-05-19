from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from .api import crawl as _crawl, scrape as _scrape, search as _search
from .search import ENGINES
from .guard import has_injection, wrap
from .store import DB_PATH, init


def _print_results(results: dict) -> None:
    row = "{:<60} {:>4} {:>8}  {}"
    print(row.format("URL", "HTTP", "CHARS", "TITLE"))
    print("─" * 88)
    for url, doc in results.items():
        print(row.format(
            url[:60], doc.metadata.status_code or "–",
            len(doc.markdown or ""), (doc.metadata.title or "")[:30],
        ))
    print(f"\n{len(results)} pages")


def _cmd_init_db(_: argparse.Namespace) -> int:
    init()
    print(f"Initialized DuckDB at {DB_PATH}")
    return 0


def _cmd_scrape(args: argparse.Namespace) -> int:
    doc = _scrape(args.url, js=args.js)
    if args.json:
        print(json.dumps(dataclasses.asdict(doc), default=str))
        return 0
    text = doc.markdown or ""
    if args.guard:
        if has_injection(text):
            print("WARNING: prompt injection detected", file=sys.stderr)
        text = wrap(text)
    print(text)
    return 0


def _cmd_crawl(args: argparse.Namespace) -> int:
    results = _crawl(args.url, depth=args.depth, max_pages=args.max_pages, concurrency=args.concurrency)
    if args.json:
        print(json.dumps({u: dataclasses.asdict(d) for u, d in results.items()}, default=str))
        return 0
    _print_results(results)
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    urls = _search(args.query, engine=args.engine, limit=args.limit)
    if not urls:
        print("no results", file=sys.stderr)
        return 1
    if not args.crawl:
        print("\n".join(urls))
        return 0
    results = _crawl(urls, depth=args.depth, max_pages=args.max_pages, concurrency=args.concurrency)
    if args.json:
        print(json.dumps({u: dataclasses.asdict(d) for u, d in results.items()}, default=str))
        return 0
    _print_results(results)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shadowfire", description="Dark-web scraper and crawler")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create DuckDB tables").set_defaults(func=_cmd_init_db)

    sc = sub.add_parser("scrape", help="Fetch a single URL and print Markdown")
    sc.add_argument("url")
    sc.add_argument("--json", action="store_true", help="Emit full Document as JSON")
    sc.add_argument("--js", action="store_true", help="Force browser rendering via Playwright")
    sc.add_argument("--guard", action="store_true", help="Scan for prompt injection and wrap output")
    sc.set_defaults(func=_cmd_scrape)

    cr = sub.add_parser("crawl", help="BFS crawl from a starting URL")
    cr.add_argument("url")
    cr.add_argument("--depth", type=int, default=2)
    cr.add_argument("--max-pages", type=int, default=50, dest="max_pages")
    cr.add_argument("--concurrency", type=int, default=3)
    cr.add_argument("--json", action="store_true", help="Emit full result as JSON")
    cr.set_defaults(func=_cmd_crawl)

    se = sub.add_parser("search", help="Search Ahmia and optionally crawl results")
    se.add_argument("query")
    se.add_argument("--engine", choices=list(ENGINES), default="ahmia")
    se.add_argument("--limit", type=int, default=20, help="Max seed URLs returned")
    se.add_argument("--crawl", action="store_true", help="BFS crawl all result URLs")
    se.add_argument("--depth", type=int, default=2)
    se.add_argument("--max-pages", type=int, default=50, dest="max_pages")
    se.add_argument("--concurrency", type=int, default=3)
    se.add_argument("--json", action="store_true", help="Emit full result as JSON")
    se.set_defaults(func=_cmd_search)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
