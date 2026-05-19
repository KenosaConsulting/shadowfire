from playwright.async_api import async_playwright
from shadowfire.tor.proxy import SOCKS_URL

_UA = "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"


async def fetch(url: str) -> str:
    async with async_playwright() as pw:
        browser = await pw.firefox.launch()
        ctx = await browser.new_context(proxy={"server": SOCKS_URL}, user_agent=_UA)
        page = await ctx.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60_000)
        html = await page.content()
        await browser.close()
        return html
