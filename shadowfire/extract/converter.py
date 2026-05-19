"""
HTML → GFM Markdown — mirrors Firecrawl's Go html-to-markdown + post_process_markdown.
Primary: markdownify (Python port of Turndown, closest to Firecrawl's Go converter).
Post-processing: escape \\n inside [...] link text, strip skip-to-content links.
"""
import re
from markdownify import markdownify as _md

# Firecrawl options: GFM tables, strip links=False, heading style ATX
_MD_OPTIONS = {
    "heading_style": "ATX",
    "bullets": "-",
    "strip": [],          # don't strip any tags — cleaner.py already did that
    "convert_links": True,
    "newline_style": "backslash",
}

_SKIP_LINK_RE = re.compile(r"\[skip to (main )?content\]\(#[^)]*\)", re.IGNORECASE)
_NEWLINE_IN_LINK_RE = re.compile(r"\[([^\]]*)\]", re.DOTALL)


def _escape_newlines_in_links(md: str) -> str:
    def _replace(m: re.Match) -> str:
        inner = m.group(1).replace("\n", "\\\n")
        return f"[{inner}]"
    return _NEWLINE_IN_LINK_RE.sub(_replace, md)


def _post_process(md: str) -> str:
    md = _escape_newlines_in_links(md)
    md = _SKIP_LINK_RE.sub("", md)
    # Collapse 3+ consecutive blank lines to 2
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def to_markdown(html: str) -> str:
    raw = _md(html, **_MD_OPTIONS)
    return _post_process(raw)
