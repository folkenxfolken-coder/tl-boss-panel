import asyncio
from playwright.async_api import async_playwright

URL = "https://questlog.gg/throne-and-liberty/en/event-calendar"
KEYWORDS = ("boss", "event", "calendar", "schedule", "trpc", "graphql", "/api/")

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

        async def inspect_response(resp):
            u = resp.url.lower()
            if not any(k in u for k in KEYWORDS):
                return
            ct = (resp.headers.get("content-type") or "").lower()
            print("RESP:", resp.status, resp.url, ct)
            if any(x in ct for x in ("json", "javascript", "text/plain")):
                try:
                    body = await resp.text()
                    if body:
                        print("RESP_BODY_START", resp.url)
                        print(body[:12000])
                        print("RESP_BODY_END")
                except Exception as e:
                    print("RESP_READ_ERROR", resp.url, repr(e))

        page.on("response", lambda resp: asyncio.create_task(inspect_response(resp)))
        await page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(8000)

        print("TITLE:", await page.title())
        print("URL:", page.url)
        print("LOCALSTORAGE:", await page.evaluate("Object.fromEntries(Object.entries(localStorage))"))

        anchors = await page.locator("a").evaluate_all("els => els.map(e => ({text:(e.innerText||'').trim(), href:e.href, aria:e.getAttribute('aria-label'), title:e.getAttribute('title')}))")
        print("ANCHORS_START")
        for a in anchors:
            blob = f"{a.get('text','')} {a.get('href','')} {a.get('aria','')} {a.get('title','')}".lower()
            if any(k in blob for k in KEYWORDS):
                print(a)
        print("ANCHORS_END")

        html = await page.content()
        for needle in ["Boss Schedule", "Field Bosses", "Ark Boss", "Archboss", "Upcoming Field Bosses"]:
            pos = html.lower().find(needle.lower())
            print("HTML_FIND", needle, pos)
            if pos >= 0:
                print(html[max(0,pos-2500):pos+5000])

        scripts = await page.locator("script").evaluate_all("els => els.map(e => ({src:e.src, text:(e.textContent||'').slice(0,200000)}))")
        print("SCRIPTS_START")
        for s in scripts:
            blob = (s.get("src", "") + " " + s.get("text", "")).lower()
            if any(k in blob for k in KEYWORDS):
                print("SCRIPT_SRC", s.get("src"))
                txt = s.get("text", "")
                for needle in ["field boss", "boss schedule", "archboss", "ark boss", "event-calendar", "schedule"]:
                    pos = txt.lower().find(needle)
                    if pos >= 0:
                        print("SCRIPT_MATCH", needle, txt[max(0,pos-1500):pos+5000])
                        break
        print("SCRIPTS_END")

        text = await page.locator("body").inner_text()
        print("BODY_START")
        print(text[:30000])
        print("BODY_END")
        await page.wait_for_timeout(3000)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
