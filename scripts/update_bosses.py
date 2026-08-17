import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

OUT = Path("site/boss-data.json")
CHILE = ZoneInfo("America/Santiago")
PAGES = [
    "https://questlog.gg/throne-and-liberty/en/event-calendar",
    "https://questlog.gg/throne-and-liberty/en/db/events?page=1",
]


def infer_dates(times):
    now = datetime.now(CHILE)
    day = now.date()
    result = []
    prev = None
    for hhmm in times:
        h, m = map(int, hhmm.split(":"))
        minutes = h * 60 + m
        if prev is None:
            candidate = datetime(day.year, day.month, day.day, h, m, tzinfo=CHILE)
            if candidate < now - timedelta(minutes=5):
                day += timedelta(days=1)
        elif minutes <= prev:
            day += timedelta(days=1)
        result.append(day.isoformat())
        prev = minutes
    return result


def clean_name(value):
    return re.sub(r"\s+", " ", value).strip(" -·•\t\r\n")


def parse_upcoming(text):
    marker = re.search(r"Upcoming Field Bosses", text, re.I)
    section = text[marker.end(): marker.end() + 6000] if marker else text
    compact = re.sub(r"[\t\r\n]+", " ", section)
    compact = re.sub(r"\s{2,}", " ", compact)
    pattern = re.compile(
        r"T3\s+(.+?)\s*/\s*T2\s+(.+?)\s+(\d{1,2}:\d{2})(?=\s*(?:[·•]|in\b|\d+\s+(?:minute|hour)|T3\b|$))",
        re.I,
    )
    found = pattern.findall(compact)
    unique, seen = [], set()
    for t3, t2, hhmm in found:
        h, m = map(int, hhmm.split(":"))
        key = (clean_name(t3), clean_name(t2), f"{h:02d}:{m:02d}")
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique[:10]


async def scrape_questlog():
    endpoint_hits = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            timezone_id="America/Santiago",
            viewport={"width": 1440, "height": 1600},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        await page.add_init_script("""
            try { localStorage.setItem('tl-rain-schedule-region', 'AMERICAS'); } catch (e) {}
        """)

        async def inspect_response(resp):
            try:
                url = resp.url
                low = url.lower()
                if "questlog.gg/throne-and-liberty/api/" not in low:
                    return
                if not any(k in low for k in ("eventcalendar", "schedule", "calendar", "boss", "event")):
                    return
                ctype = (resp.headers.get("content-type") or "").lower()
                txt = ""
                if any(x in ctype for x in ("json", "text", "javascript")):
                    txt = await resp.text()
                endpoint_hits.append((url, txt[:16000]))
            except Exception as exc:
                print("TRACE_RESPONSE_ERROR", repr(exc))

        page.on("response", inspect_response)
        visible_rows = []
        for target in PAGES:
            print("NAVIGATE", target)
            await page.goto(target, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(9000)
            body = await page.locator("body").inner_text()
            rows = parse_upcoming(body)
            if len(rows) > len(visible_rows):
                visible_rows = rows

        stored_region = await page.evaluate("() => localStorage.getItem('tl-rain-schedule-region')")
        print("QUESTLOG_REGION", stored_region)
        print("QUESTLOG_ENDPOINT_COUNT", len(endpoint_hits))
        seen_urls = set()
        for url, txt in endpoint_hits:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            print("QL_ENDPOINT", url)
            if txt:
                print("QL_BODY_BEGIN")
                print(txt)
                print("QL_BODY_END")
        print("QUESTLOG_VISIBLE_BOSS_ROWS", len(visible_rows))
        await browser.close()

    if len(visible_rows) < 3:
        raise RuntimeError(f"Questlog visible boss rows={len(visible_rows)}; endpoints={len(seen_urls)}")

    dates = infer_dates([r[2] for r in visible_rows])
    slots = []
    for (t3, t2, hhmm), day in zip(visible_rows, dates):
        slots.append({"date": day, "time": hhmm, "bosses": [
            {"tier": "T3", "name": t3, "type": "field"},
            {"tier": "T2", "name": t2, "type": "field"},
        ]})
    return slots, stored_region


async def main():
    try:
        slots, stored_region = await scrape_questlog()
        payload = {
            "source": "Questlog live Upcoming Field Bosses",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "fallback": False,
            "model": "questlog-live-americas-v4",
            "region": "Americas",
            "timezone": "America/Santiago",
            "questlog_region_value": stored_region,
            "slots": slots,
        }
    except Exception as exc:
        print("LIVE_SCRAPE_FAILED", repr(exc))
        payload = {
            "source": "Questlog live scrape unavailable",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "fallback": False,
            "model": "questlog-live-unavailable-v4",
            "region": "Americas",
            "timezone": "America/Santiago",
            "slots": [],
            "error": repr(exc),
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
