import asyncio
import re
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
        seen_api = set()

        async def inspect_response(resp):
            u = resp.url
            lu = u.lower()
            if "questlog.gg" in lu and ("/api/" in lu or "trpc" in lu):
                if u not in seen_api:
                    seen_api.add(u)
                    print("API:", resp.status, u, resp.headers.get("content-type", ""))
                    try:
                        body = await resp.text()
                        print("API_BODY:", body[:20000])
                    except Exception as e:
                        print("API_BODY_ERROR", repr(e))

        page.on("response", lambda resp: asyncio.create_task(inspect_response(resp)))
        await page.goto(URL, wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(6000)

        print("TITLE:", await page.title())
        print("BODY:", (await page.locator("body").inner_text())[:12000])

        resources = await page.evaluate("performance.getEntriesByType('resource').map(x => x.name)")
        js_urls = []
        for u in resources:
            if "questlog.gg" in u and (u.endswith(".js") or ".js?" in u or "/_nuxt/" in u):
                if u not in js_urls:
                    js_urls.append(u)
        print("JS_COUNT", len(js_urls))

        methods = set()
        for u in js_urls:
            try:
                r = await context.request.get(u, timeout=30000)
                if not r.ok:
                    continue
                text = await r.text()
                low = text.lower()
                if "eventcalendar" not in low and "getfieldbossentries" not in low and "ark boss" not in low and "field bosses" not in low:
                    continue
                print("JS_MATCH_URL", u)
                for needle in ["getFieldBossEntries", "eventCalendar", "Ark Boss", "Archboss", "Field Bosses", "Boss Schedule"]:
                    pos = text.lower().find(needle.lower())
                    if pos >= 0:
                        print("JS_MATCH", needle)
                        print(text[max(0, pos-5000):pos+12000])
                for m in re.findall(r"eventCalendar\.([A-Za-z0-9_]+)", text):
                    methods.add(m)
                for m in re.findall(r"eventCalendar[^A-Za-z0-9_]+([A-Za-z0-9_]{3,})", text):
                    if m.lower() not in {"query", "mutate", "value", "data"}:
                        methods.add(m)
            except Exception as e:
                print("JS_ERR", u, repr(e))

        print("EVENTCAL_METHODS", sorted(methods))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
