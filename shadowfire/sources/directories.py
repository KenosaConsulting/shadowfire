"""
Dynamic directory seeding — discovers curated .onion link directories,
navigates to categories relevant to the research goal, returns seeds.

Two-stage approach:
  1. Flat fallback  — no internal categories detected, extract all external .onion links
  2. Hierarchical   — LLM picks relevant category pages, extract seeds from those
"""
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from shadowfire.fetch.http import fetch
from shadowfire.guard import safe_url
from shadowfire.search import search
from shadowfire.llm import filter_urls

_BOOTSTRAP = [
    "hidden wiki onion links directory",
    "dark web directory categories tor",
    "onion link list index 2025",
]

# Cached known directories — skip bootstrap rediscovery for these
KNOWN_DIRECTORIES = [
    "http://zqktlwk5ilgohy63eyrptyb4mc76bunfmxcnstkmveyjnskxkpq3b5yd.onion",  # The Hidden Wiki
]

_CATEGORY_HINT = (
    "Navigating a dark web directory. Prefer categories related to: "
    "drugs, chemicals, research chemicals, synthesis, markets, vendors, "
    "pharmaceuticals, darknet markets. Deprioritise financial, technical, or hosting categories."
)

_ONION_RE = re.compile(r'https?://[a-z2-7]{10,56}\.onion[^\s"<>]*')


def _external_onions(html: str, host: str) -> list[str]:
    return [u for u in dict.fromkeys(_ONION_RE.findall(html)) if safe_url(u) and host not in u]


def seeds_from_directories(goal: str, engine: str = "torch", n_dirs: int = 3) -> list[str]:
    discovered = [u for q in _BOOTSTRAP for u in search(q, engine=engine, limit=2)]
    dirs = list(dict.fromkeys(KNOWN_DIRECTORIES + discovered))

    seeds = []
    for dir_url in dirs:
        try:
            r = fetch(dir_url)
            host = urlparse(dir_url).netloc
            soup = BeautifulSoup(r.text, "lxml")

            # collect short-text internal links as candidate categories
            cats = [
                f"{a.get_text(strip=True)} | {urljoin(dir_url, a['href'])}"
                for a in soup.find_all("a", href=True)
                if len(a.get_text(strip=True)) < 50
                and urlparse(urljoin(dir_url, a["href"])).netloc == host
            ]

            if not cats:
                # flat directory — extract external .onion links directly
                seeds.extend(_external_onions(r.text, host))
                continue

            # hierarchical — LLM picks relevant category pages
            for cat_url in filter_urls(goal, cats, n=5, hint=_CATEGORY_HINT):
                try:
                    seeds.extend(_external_onions(fetch(cat_url).text, host))
                except Exception:
                    pass

        except Exception:
            pass

    return list(dict.fromkeys(seeds))
