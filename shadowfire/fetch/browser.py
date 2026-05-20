from playwright.async_api import async_playwright
from shadowfire.tor.proxy import SOCKS_URL

_UA_FIREFOX  = "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"
_UA_CHROME   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


async def fetch(url: str, engine: str = "firefox") -> str:
    """Fetch JS-rendered HTML via Playwright through Tor.
    Use engine='chromium' for sites that use @-moz-document to block Firefox (e.g. Ahmia).
    """
    async with async_playwright() as pw:
        launcher = pw.chromium if engine == "chromium" else pw.firefox
        ua = _UA_CHROME if engine == "chromium" else _UA_FIREFOX
        browser = await launcher.launch()
        ctx = await browser.new_context(proxy={"server": SOCKS_URL}, user_agent=ua)
        page = await ctx.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60_000)
        html = await page.content()
        await browser.close()
        return html
