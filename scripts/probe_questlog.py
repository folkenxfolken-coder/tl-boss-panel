import asyncio
import json
import re
from playwright.async_api import async_playwright

URLS = [
    "https://throneandliberty.gameslantern.com/event-calendar",
    "https://throneandliberty.gameslantern.com/server-events",
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            timezone_id="America/Santiago",
            viewport={"width": 1600, "height": 1400},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        seen = set()

        async def inspect_response(resp):
            u = resp.url
            lu = u.lower()
            ctype = resp.headers.get("content-type", "")
            interesting = any(x in lu for x in ["api", "event", "server", "schedule", "calendar", "amazon", "ags", "eclipse"])
            if interesting and u not in seen:
                seen.add(u)
                print("NET", resp.status, ctype, u)
                if "json" in ctype or "/api/" in lu:
                    try:
                        body = await resp.text()
                        print("NET_BODY", body[:30000])
                    except Exception as e:
                        print("NET_BODY_ERR", repr(e))

        page.on("response", lambda r: asyncio.create_task(inspect_response(r)))

        for url in URLS:
            print("OPEN", url)
            try:
                await page.goto(url, wait_until="networkidle", timeout=90000)
            except Exception as e:
                print("GOTO_ERR", repr(e))
            await page.wait_for_timeout(5000)
            print("TITLE", await page.title())
            body = await page.locator("body").inner_text()
            print("BODY", body[:20000])

            selects = await page.locator("select").count()
            print("SELECT_COUNT", selects)
            for i in range(selects):
                sel = page.locator("select").nth(i)
                try:
                    opts = await sel.locator("option").all_text_contents()
                    vals = await sel.locator("option").evaluate_all("els => els.map(x => x.value)")
                    print("SELECT", i, list(zip(vals, opts))[:500])
                    for value, label in zip(vals, opts):
                        if "eclipse" in label.lower():
                            print("FOUND_ECLIPSE_SELECT", i, value, label)
                            await sel.select_option(value=value)
                            await page.wait_for_timeout(5000)
                            print("BODY_AFTER_ECLIPSE", (await page.locator("body").inner_text())[:20000])
                except Exception as e:
                    print("SELECT_ERR", i, repr(e))

            # Dump useful interactive controls for custom dropdowns.
            controls = await page.locator("button, input, [role=button], [role=option], [role=combobox]").evaluate_all(
                "els => els.slice(0,500).map(e => ({tag:e.tagName, text:(e.innerText||e.value||e.getAttribute('aria-label')||'').trim(), role:e.getAttribute('role'), cls:e.className}))"
            )
            print("CONTROLS", json.dumps(controls, ensure_ascii=False)[:40000])

            # Try clicking any visible control mentioning server, then search Eclipse text.
            candidates = page.get_by_text(re.compile("server", re.I))
            for i in range(min(await candidates.count(), 12)):
                try:
                    c = candidates.nth(i)
                    if await c.is_visible():
                        print("CLICK_SERVER_TEXT", i, (await c.inner_text())[:300])
                        await c.click(timeout=3000)
                        await page.wait_for_timeout(1200)
                        eclipse = page.get_by_text(re.compile("^Eclipse$", re.I))
                        if await eclipse.count():
                            for j in range(await eclipse.count()):
                                e = eclipse.nth(j)
                                if await e.is_visible():
                                    print("CLICK_ECLIPSE", j)
                                    await e.click(timeout=3000)
                                    await page.wait_for_timeout(5000)
                                    print("BODY_AFTER_ECLIPSE_CUSTOM", (await page.locator("body").inner_text())[:20000])
                                    break
                except Exception as e:
                    print("CLICK_ERR", i, repr(e))

            resources = await page.evaluate("performance.getEntriesByType('resource').map(x => x.name)")
            print("RESOURCES", json.dumps([u for u in resources if any(x in u.lower() for x in ['api','event','server','calendar','schedule'])], ensure_ascii=False)[:60000])

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
