"""
Metadata extraction — mirrors Firecrawl's extractMetadata (Rust + Cheerio).
Extracts title, OG, Dublin Core, and all custom <meta> tags.
"""
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .document import Metadata

_OG_MAP = {
    "og:title": "og_title",
    "og:description": "og_description",
    "og:url": "og_url",
    "og:image": "og_image",
    "og:site_name": "og_site_name",
    "og:locale": "og_locale",
    "og:video": "og_video",
    "og:audio": "og_audio",
    "twitter:title": "_twitter_title",
    "twitter:description": "_twitter_description",
}

_DC_MAP = {
    "dc.date": "dc_date",
    "dcterms.created": "dc_date",
    "dc.description": "dc_description",
    "dcterms.keywords": "dc_keywords",
    "dc.type": "dc_type",
    "dcterms.type": "dc_type",
    "article:published_time": "published_time",
    "article:modified_time": "modified_time",
    "article:tag": "article_tag",
    "article:section": "article_section",
}


def extract(html: str, page_url: str = "") -> Metadata:
    soup = BeautifulSoup(html, "lxml")
    m = Metadata(url=page_url, source_url=page_url)
    _twitter_title = None
    _twitter_description = None

    # Title
    title_tag = soup.find("title")
    if title_tag:
        m.title = title_tag.get_text(strip=True) or None

    # Language
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        m.language = html_tag["lang"]

    # Favicon
    favicon = soup.find("link", rel=lambda r: r and "icon" in r)
    if favicon and favicon.get("href"):
        m.favicon = urljoin(page_url, favicon["href"])

    # All <meta> tags
    for tag in soup.find_all("meta"):
        content = tag.get("content", "").strip()
        if not content:
            continue

        name = (tag.get("name") or tag.get("property") or tag.get("itemprop") or "").lower()
        if not name:
            continue

        if name == "description":
            m.description = content
        elif name == "keywords":
            m.keywords = content
        elif name == "robots":
            m.robots = content
        elif name in _OG_MAP:
            attr = _OG_MAP[name]
            if attr == "_twitter_title":
                _twitter_title = content
            elif attr == "_twitter_description":
                _twitter_description = content
            else:
                setattr(m, attr, content)
        elif name in _DC_MAP:
            setattr(m, _DC_MAP[name], content)
        else:
            # Catch-all: store everything else in extra
            existing = m.extra.get(name)
            if existing is None:
                m.extra[name] = content
            elif isinstance(existing, list):
                existing.append(content)
            else:
                m.extra[name] = [existing, content]

    # Twitter fallbacks for OG fields
    if not m.title and _twitter_title:
        m.title = _twitter_title
    if not m.description and _twitter_description:
        m.description = _twitter_description
    if not m.title and m.og_title:
        m.title = m.og_title

    return m
