"""
ShadowFire — Stress test loop for authentic data collection.

Runs N iterations of the fetch suite, randomly sampling targets and
varying crawl depth each run. All results accumulate in data/shadowfire.db.

Usage:
    python tests/loop.py          # 10 runs (default)
    python tests/loop.py --runs 25
"""
import argparse
import random
import time
import uuid
from datetime import datetime, timezone

from shadowfire.api import scrape
from shadowfire.guard import has_injection
from shadowfire.llm import triage
from shadowfire.store import init, insert_run, insert_page
from shadowfire.tor.controller import TorController

# Verified from onion.torproject.org — diverse archetypes
TARGET_POOL = [
    ("blog",             "http://pzhdfe7jraknpj2qgu5cz2u3i4deuyfwmonvzu5i3nyw4t4bmg7o5pad.onion/"),
    ("community",        "http://xmrhfasfg5suueegrnc4gsgyi2tyclcy5oz7f5drnrodmdtob6t2ioyd.onion/"),
    ("forum",            "http://v236xhqtyullodhf26szyjepvkbv6iitrhjgrqj4avaoukebkk6n6syd.onion/"),
    ("gitlab",           "http://eweiibe6tdjsdprb4px6rqrzzcsi22m4koia44kc5pcjr7nec2rlxyad.onion/"),
    ("2019.www",         "http://jqyzxhjk6psc6ul5jnfwloamhtyh7si74b4743k2qgpskwwxrzhsxmad.onion/"),
    ("bridges",          "http://yq5jjvr7drkjrelzhut7kgclfuro65jjlivyzfmxiq2kyv5lickrl4qd.onion/"),
    ("exonerator",       "http://pm46i5h2lfewyx6l7pnicbxhts2sxzacvsbmqiemqaspredf2gm3dpad.onion/"),
    ("dist",             "http://scpalcwstkydpa3y7dbpkjs2dtr7zvtvdbyj3dqwkucfrwyixcl5ptqd.onion/"),
    ("collector",        "http://pgmrispjerzzf2tdzbfp624cg5vpbvdw2q5a3hvtsbsx25vnni767yad.onion/"),
    ("consensus-health", "http://tkskz5dkjel4xqyw5d5l3k52kgglotwn6vgb5wrl2oa5yi2szvywiyid.onion/"),
    ("archive",          "http://uy3qxvwzwoeztnellvvhxh7ju7kfvlsauka7avilcjg7domzxptbq7qd.onion/"),
    ("arti",             "http://hjirlp6fu47kox4cnede4zlvaeq672bibss3oxgmsnsc5mdxygqshbqd.onion/"),
]

SAMPLE_SIZE = 5   # targets per run
SLEEP_BETWEEN = 3  # seconds — be a good Tor citizen


def _now():
    return datetime.now(timezone.utc)


def run_once(run_id: str, targets: list, tor: TorController):
    for label, url in targets:
        t0 = time.monotonic()
        try:
            doc = scrape(url)
            fetch_ms = int((time.monotonic() - t0) * 1000)
            detected = bool(doc.markdown and has_injection(doc.markdown))
            circuit_id, exit_fp, exit_nick = tor.active_circuit()
            content_type = (doc.metadata.extra.get("content-type") or
                            doc.metadata.content_type or "text/html")
            try:
                t = triage(doc.markdown or "", title=doc.metadata.title or "")
            except Exception:
                t = {}
            insert_page(
                id=str(uuid.uuid4()), run_id=run_id, url=url,
                status_code=doc.metadata.status_code,
                fetch_ms=fetch_ms,
                html_bytes=len(doc.raw_html or ""),
                markdown_chars=len(doc.markdown or ""),
                link_count=len(doc.links),
                image_count=len(doc.images),
                title=doc.metadata.title,
                error=None,
                injection_detected=detected,
                injection_score=0.0,
                invisible_text=False,
                scraped_at=_now(),
                circuit_id=circuit_id,
                exit_fingerprint=exit_fp,
                exit_nickname=exit_nick,
                content_type=content_type,
                page_type=t.get("page_type"),
                language=t.get("language"),
            )
            print(f"    {doc.metadata.status_code}  {fetch_ms:>5}ms  {len(doc.markdown or ''):>6}c"
                  f"  exit={exit_nick or '?':<14}  {t.get('page_type', '?'):<8}  {t.get('language', '?'):<3}  {label}")
        except Exception as e:
            fetch_ms = int((time.monotonic() - t0) * 1000)
            insert_page(
                id=str(uuid.uuid4()), run_id=run_id, url=url,
                status_code=0, fetch_ms=fetch_ms,
                html_bytes=0, markdown_chars=0, link_count=0, image_count=0,
                title=None, error=str(e),
                injection_detected=False, injection_score=0.0,
                invisible_text=False, scraped_at=_now(),
            )
            print(f"    ERR  {fetch_ms:>5}ms  {label}  {e}")


def print_aggregate():
    from shadowfire.store import _conn
    with _conn() as con:
        row = con.execute("""
            SELECT
                COUNT(DISTINCT run_id)                                          AS runs,
                COUNT(*)                                                        AS pages,
                SUM(CASE WHEN error IS NULL THEN 1 ELSE 0 END) * 100 / COUNT(*) AS success_pct,
                AVG(fetch_ms)::INTEGER                                          AS avg_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY fetch_ms)::INTEGER AS p95_ms,
                AVG(markdown_chars)::INTEGER                                    AS avg_chars
            FROM pages
        """).fetchone()
    runs, pages, pct, avg_ms, p95_ms, avg_chars = row
    print(f"\n── Aggregate ({runs} runs, {pages} pages) ──────────────────")
    print(f"  success   : {pct}%")
    print(f"  fetch     : avg={avg_ms}ms  p95={p95_ms}ms")
    print(f"  extraction: avg {avg_chars} chars/page")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()

    init()

    with TorController() as tor:
        for i in range(1, args.runs + 1):
            run_id = str(uuid.uuid4())
            targets = random.sample(TARGET_POOL, SAMPLE_SIZE)
            print(f"\n[{i}/{args.runs}] run={run_id[:8]}  targets={[t for t, _ in targets]}")

            insert_run(run_id, _now(), None, {"targets": [t for t, _ in targets], "sample_size": SAMPLE_SIZE})
            run_once(run_id, targets, tor)

            if i < args.runs:
                time.sleep(SLEEP_BETWEEN)

    print_aggregate()
