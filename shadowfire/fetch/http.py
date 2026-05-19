import httpx
from shadowfire.tor.proxy import SOCKS_URL

TIMEOUT = httpx.Timeout(connect=30.0, read=60.0, write=10.0, pool=5.0)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Accept-Language": "en-US,en;q=0.5",
}


def make_client() -> httpx.Client:
    return httpx.Client(
        proxy=SOCKS_URL,
        headers=HEADERS,
        timeout=TIMEOUT,
        follow_redirects=True,
        verify=False,  # .onion TLS certs are self-signed; standard CA chain doesn't apply
    )


def fetch(url: str, client: httpx.Client | None = None) -> httpx.Response:
    if client:
        return client.get(url)
    with make_client() as c:
        return c.get(url)
