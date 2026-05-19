import re
from urllib.parse import urlencode
from shadowfire.fetch.http import fetch
from shadowfire.guard import safe_url

# (base_url, query_param)  — add engines here, CLI choices update automatically
ENGINES: dict[str, tuple[str, str]] = {
    "ahmia":      ("https://ahmia.fi/search/", "q"),
    "torch":      ("http://torchdeecx7spcubonhjsuqz4pv3twne4zd5l63tqnxtk2ncvptrllqd.onion/", "q"),
    "onionland":  ("http://3bbad7fau4ui3pz2fh7wij3oj7wa5oqc45il5q3thddpp3xlfcr4ekqd.onion/", "q"),
    "haystak":    ("http://haystak5njsmn2hqkewecpaxetahtwhsbsa64jom2k22z5afxhnpxfid.onion/", "q"),
}

_ONION_RE = re.compile(r'https?://[a-z2-7]{10,56}\.onion[^\s"<>]*')
_NOISE_RE = re.compile(r'/banners/|[?&]bads=|banner-click|/advertising/|\.(gif|png|jpg|webp|css|js)([?#]|$)')


def search(query: str, engine: str = "ahmia", limit: int = 20) -> list[str]:
    base, param = ENGINES[engine]
    if not base:
        raise ValueError(f"'{engine}' has no URL configured — add it to ENGINES in shadowfire/search.py")
    r = fetch(f"{base}?{urlencode({param: query})}")
    base_host = re.search(r'//([^/]+)', base).group(1)[:12]
    return [
        u for u in dict.fromkeys(_ONION_RE.findall(r.text))
        if safe_url(u) and base_host not in u and not _NOISE_RE.search(u)
    ][:limit]
