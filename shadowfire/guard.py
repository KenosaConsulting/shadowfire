"""
Zero-trust content security layer.

Four functions, four threat vectors:
  safe_url()      — SSRF: block RFC1918/loopback/non-HTTP before following links
  sanitize()      — Active content: nh3 allowlist strips scripts/iframes/forms/events
  has_injection() — Prompt injection: invisible-text pre-check + DeBERTa classifier
  wrap()          — Isolation: XML boundary so LLMs treat content as untrusted data

has_injection() lazy-loads protectai/deberta-v3-base-prompt-injection-v2 on first
call (~750MB download once, then cached). Runs on MPS (Apple Silicon) or CPU.
"""
import re
import ipaddress
import socket
from urllib.parse import urlparse
import nh3

# RFC1918, loopback, link-local, cloud metadata endpoint
_BLOCKED = [
    ipaddress.ip_network(n) for n in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        "127.0.0.0/8", "169.254.0.0/16",
        "::1/128", "fc00::/7",
    )
]

_ALLOWED_TAGS = {
    "p", "br", "b", "i", "em", "strong", "a", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "blockquote", "code", "pre", "hr", "div", "span",
}

# Zero-width and invisible Unicode — common dark web injection vector
_INVISIBLE_RE = re.compile(
    r"[​‌‍⁠﻿­\x00-\x08\x0b\x0c\x0e-\x1f]"
)

_clf = None


def _classifier():
    global _clf
    if _clf is None:
        import torch
        from transformers import pipeline
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        _clf = pipeline(
            "text-classification",
            model="protectai/deberta-v3-base-prompt-injection-v2",
            device=device,
        )
    return _clf


def safe_url(url: str) -> bool:
    """Return False for RFC1918, loopback, non-HTTP/S, or unresolvable URLs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.hostname and parsed.hostname.endswith(".onion"):
        return True  # hidden services have no routable IP — SSRF check N/A
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        return not any(ip in net for net in _BLOCKED)
    except (socket.gaierror, ValueError):
        return False


def sanitize(html: str) -> str:
    """Strip all active content — scripts, iframes, forms, event handlers."""
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes={"a": {"href"}, "img": {"src", "alt"}},
        clean_content_tags={"script", "style", "iframe", "form", "input", "button"},
    )


def has_injection(text: str, threshold: float = 0.75) -> bool:
    """Invisible-text pre-check, then DeBERTa classifier for prompt injection."""
    if _INVISIBLE_RE.search(text):
        return True
    result = _classifier()(text[:512], truncation=True)[0]
    return result["label"] == "INJECTION" and result["score"] >= threshold


def wrap(text: str) -> str:
    """Wrap scraped content in an untrusted-source boundary for LLM consumption."""
    return f"<untrusted_source>\n{text}\n</untrusted_source>"
