import asyncio
from playwright.async_api import async_playwright

URL = "https://questlog.gg/throne-and-liberty/en/event-calendar"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            timezone_id="America/Santiago",
            viewport={"width": 1440, "height": 1200},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(8000)
        print("TITLE:", await page.title())
        print("URL:", page.url)
        print("LOCALSTORAGE:", await page.evaluate("Object.fromEntries(Object.entries(localStorage))"))
        print("COOKIES:", await context.cookies())
        text = await page.locator("body").inner_text()
        print("BODY_START")
        print(text[:30000])
        print("BODY_END")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
