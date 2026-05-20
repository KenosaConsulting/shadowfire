from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from .api import crawl as _crawl, scrape as _scrape, map as _map
from .search import search as _search, search_all as _search_all, ENGINES
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


def _cmd_map(args: argparse.Namespace) -> int:
    urls = _map(args.url, depth=args.depth, max_urls=args.max_urls)
    print("\n".join(urls))
    return 0


def _log(msg: str, end: str = "\n") -> None:
    print(msg, end=end, flush=True)


def _cmd_research(args: argparse.Namespace) -> int:
    from .llm import expand, filter_urls, synthesize

    # 1. expand
    _log("expanding goal...", end="\r")
    queries = expand(args.goal, n=args.queries)
    _log(f"· {len(queries)} queries")
    for q in queries:
        _log(f"  {q}")

    if args.no_crawl:
        return 0

    # 2. seeds — db inventory + search + directory discovery
    from .store import get_sources
    from .sources.directories import seeds_from_directories

    _log("pulling inventory...", end="\r")
    db_seeds = [s["url"] for s in get_sources()]

    engines = None if args.engines == "all" else [e.strip() for e in args.engines.split(",")]
    _log(f"searching {args.engines}...", end="\r")
    search_seeds = list(dict.fromkeys(
        url for q in queries
        for url in _search_all(q, engines=engines, limit=args.limit_per_query)
    ))

    _log("seeding from directories...", end="\r")
    dir_seeds = seeds_from_directories(args.goal, engine=(engines or list(ENGINES))[0])

    seeds = list(dict.fromkeys(db_seeds + search_seeds + dir_seeds))
    _log(f"· {len(seeds)} seeds ({len(db_seeds)} db, {len(search_seeds)} search, {len(dir_seeds)} directory)")
    if not seeds:
        return 1

    # 3. map
    inventory = []
    for i, seed in enumerate(seeds, 1):
        _log(f"  mapping {i}/{len(seeds)}: {seed[:55]}", end="\r")
        inventory.extend(_map(seed, depth=1, max_urls=100, include_text=True))
    # cap per domain to force diversity across seeds
    from urllib.parse import urlparse
    by_domain: dict[str, list] = {}
    for item in dict.fromkeys(inventory):
        domain = urlparse(item.split(" | ")[-1] if " | " in item else item).netloc
        by_domain.setdefault(domain, [])
        if len(by_domain[domain]) < 5:
            by_domain[domain].append(item)
    inventory = [item for items in by_domain.values() for item in items] or seeds
    _log(f"· {len(inventory)} URLs mapped ({len(by_domain)} domains)                ")

    # 4. filter — pass expanded queries as context so the LLM knows what to look for
    _log(f"filtering {len(inventory)} → {args.max_pages} URLs (LLM)...", end="\r")
    targeted = filter_urls(
        args.goal, inventory, n=args.max_pages,
        hint=f"Expanded search queries for this goal: {'; '.join(queries)}",
    )
    _log(f"· {len(targeted)} URLs selected                             ")

    # 5. scrape
    _log(f"scraping {len(targeted)} pages...")
    results = _crawl(targeted, depth=0, max_pages=args.max_pages, concurrency=args.concurrency)
    if args.json:
        print(json.dumps({u: dataclasses.asdict(d) for u, d in results.items()}, default=str))
        return 0
    _print_results(results)

    # 6. synthesize
    if results and not args.no_synthesize:
        _log("\nsynthesizing...")
        print("\n── Research Summary " + "─" * 69)
        print(synthesize(args.goal, results))
        print("─" * 88)

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

    mp = sub.add_parser("map", help="Discover all internal URLs on a site")
    mp.add_argument("url")
    mp.add_argument("--depth", type=int, default=2)
    mp.add_argument("--max-urls", type=int, default=200, dest="max_urls")
    mp.set_defaults(func=_cmd_map)

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

    rs = sub.add_parser("research", help="Expand goal → search → crawl → synthesize")
    rs.add_argument("goal")
    rs.add_argument("--engines", default="all", metavar="all|e1,e2",
                    help=f"Engines to search (all or comma-separated from: {','.join(ENGINES)})")
    rs.add_argument("--queries", type=int, default=6, help="Number of queries to generate")
    rs.add_argument("--limit-per-query", type=int, default=10, dest="limit_per_query")
    rs.add_argument("--depth", type=int, default=1)
    rs.add_argument("--max-pages", type=int, default=30, dest="max_pages")
    rs.add_argument("--concurrency", type=int, default=3)
    rs.add_argument("--no-crawl", action="store_true", dest="no_crawl", help="Print queries only, skip crawl")
    rs.add_argument("--no-synthesize", action="store_true", dest="no_synthesize", help="Skip synthesis pass")
    rs.add_argument("--json", action="store_true")
    rs.set_defaults(func=_cmd_research)

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
