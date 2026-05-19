"""
HTML cleaning — mirrors Firecrawl's Rust _transform_html_inner.
Strip noise, optionally isolate main content, rewrite URLs to absolute.
"""
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag
from shadowfire.guard import sanitize

# Always stripped — Firecrawl: head, meta, noscript, style, script
_ALWAYS_STRIP = ["head", "meta", "noscript", "style", "script"]

# Firecrawl's onlyMainContent exclusion list (42 selectors)
_MAIN_CONTENT_EXCLUDE = [
    "header", "footer", "nav", "aside",
    ".header", ".top", ".navbar", "#header",
    ".footer", ".bottom", "#footer",
    ".sidebar", ".side", ".aside", "#sidebar",
    ".modal", ".popup", "#modal",
    ".overlay",
    ".ad", ".ads", ".advert", "#ad",
    ".lang-selector", ".language", "#language-selector",
    ".social", ".social-media", ".social-links", "#social",
    ".menu", ".navigation", "#nav",
    ".breadcrumbs", "#breadcrumbs",
    ".share", "#share",
    ".widget", "#widget",
    ".cookie", "#cookie",
    ".fc-decoration",
]

# Force-include: if an excluded element contains any of these, keep it.
# Firecrawl uses swoogo-* class names; we generalise to standard content landmarks.
_FORCE_INCLUDE = [
    "#main", "main", "article", "[role='main']",
    ".main-content", ".content", ".post", ".entry",
]


def _has_force_include(tag: Tag, soup: BeautifulSoup) -> bool:
    for selector in _FORCE_INCLUDE:
        if tag.select_one(selector):
            return True
    return False


def _resolve_base_url(soup: BeautifulSoup, page_url: str) -> str:
    base = soup.find("base", href=True)
    if base:
        return urljoin(page_url, base["href"])
    return page_url


def _make_absolute(soup: BeautifulSoup, base: str):
    for tag in soup.find_all("a", href=True):
        tag["href"] = urljoin(base, tag["href"])
    for tag in soup.find_all("img"):
        # srcset: pick largest image, set as src
        if tag.get("srcset"):
            candidates = [
                part.strip().split() for part in tag["srcset"].split(",") if part.strip()
            ]
            if candidates:
                # candidates are [url, descriptor?]; pick last (usually largest)
                tag["src"] = candidates[-1][0]
            del tag["srcset"]
        if tag.get("src"):
            tag["src"] = urljoin(base, tag["src"])


def clean(html: str, page_url: str = "", only_main_content: bool = True) -> str:
    html = sanitize(html)  # strip active content before any parsing
    soup = BeautifulSoup(html, "lxml")
    base_url = _resolve_base_url(soup, page_url)

    for tag_name in _ALWAYS_STRIP:
        for el in soup.find_all(tag_name):
            el.decompose()

    if only_main_content:
        for selector in _MAIN_CONTENT_EXCLUDE:
            for el in soup.select(selector):
                if not _has_force_include(el, soup):
                    el.decompose()

    if base_url:
        _make_absolute(soup, base_url)

    body = soup.find("body")
    return str(body) if body else str(soup)
