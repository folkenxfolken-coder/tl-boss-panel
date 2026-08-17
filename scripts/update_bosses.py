import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

OUT = Path("site/boss-data.json")
CHILE = ZoneInfo("America/Santiago")
# Any normal Questlog database page renders the global live widgets (rain/day-night/bosses).
# The event-calendar route itself does not currently render the individual boss widget.
URL = "https://questlog.gg/throne-and-liberty/en/db/events?page=1"


def infer_dates(times):
    now = datetime.now(CHILE)
    day = now.date()
    result = []
    previous_minutes = None
    for hhmm in times:
        h, m = map(int, hhmm.split(":"))
        minutes = h * 60 + m
        if previous_minutes is None:
            candidate = datetime(day.year, day.month, day.day, h, m, tzinfo=CHILE)
            if candidate < now - timedelta(minutes=5):
                day += timedelta(days=1)
        elif minutes <= previous_minutes:
            day += timedelta(days=1)
        result.append(day.isoformat())
        previous_minutes = minutes
    return result


def clean_name(value):
    return re.sub(r"\s+", " ", value).strip(" -·•\t\r\n")


def parse_upcoming(text):
    # Questlog currently renders cards similar to:
    # T3 Ascended Nirma / T2 Pakilo Naru 20:00 · in 41 minutes
    # Depending on responsive markup, pieces can be split across lines, so normalize first.
    marker = re.search(r"Upcoming Field Bosses", text, re.I)
    if marker:
        section = text[marker.end(): marker.end() + 5000]
    else:
        section = text

    compact = re.sub(r"[\t\r\n]+", " ", section)
    compact = re.sub(r"\s{2,}", " ", compact)

    # Stop before unrelated global widgets/footer when possible.
    for stop in ["Current Game", "Search Database", "NonAggressive", "Enjoying QuestLog", "Image:"]:
        pos = compact.find(stop)
        if pos > 0:
            compact = compact[:pos]

    pattern = re.compile(
        r"T3\s+(.+?)\s*/\s*T2\s+(.+?)\s+(\d{1,2}:\d{2})(?=\s*(?:[·•]|in\b|\d+\s+(?:minute|hour)|T3\b|$))",
        re.I,
    )
    found = pattern.findall(compact)

    unique = []
    seen = set()
    for t3, t2, hhmm in found:
        h, m = map(int, hhmm.split(":"))
        hhmm = f"{h:02d}:{m:02d}"
        key = (clean_name(t3), clean_name(t2), hhmm)
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique[:8]


async def scrape_questlog():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            timezone_id="America/Santiago",
            viewport={"width": 1440, "height": 1600},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        # This is the same region preference Questlog stores in the browser.
        # Set it before the app initializes so the global boss widget loads Americas directly.
        await page.add_init_script("""
            try {
              localStorage.setItem('tl-rain-schedule-region', 'AMERICAS');
            } catch (e) {}
        """)

        await page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(6500)

        # Give the widget a little more time if its heading has not appeared yet.
        try:
            await page.get_by_text("Upcoming Field Bosses", exact=True).first.wait_for(timeout=8000)
        except Exception:
            pass

        body = await page.locator("body").inner_text()
        rows = parse_upcoming(body)
        stored_region = await page.evaluate("() => localStorage.getItem('tl-rain-schedule-region')")

        if len(rows) < 3:
            # Keep a useful diagnostic in Actions logs; no guessed bosses are emitted.
            m = re.search(r"Upcoming Field Bosses", body, re.I)
            if m:
                debug = body[max(0, m.start() - 500): m.start() + 4500]
            else:
                debug = body[:6000]
            print("QUESTLOG_DEBUG_BEGIN")
            print(debug)
            print("QUESTLOG_DEBUG_END")

        await browser.close()

    if len(rows) < 3:
        raise RuntimeError(f"Questlog live scrape returned only {len(rows)} boss slots")

    times = [r[2] for r in rows]
    dates = infer_dates(times)
    slots = []
    for (t3, t2, hhmm), day in zip(rows, dates):
        slots.append({
            "date": day,
            "time": hhmm,
            "bosses": [
                {"tier": "T3", "name": t3, "type": "field"},
                {"tier": "T2", "name": t2, "type": "field"},
            ],
        })

    return slots, stored_region


async def main():
    try:
        slots, stored_region = await scrape_questlog()
        payload = {
            "source": "Questlog live Upcoming Field Bosses",
            "source_url": URL,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "fallback": False,
            "model": "questlog-live-americas-v2",
            "region": "Americas",
            "timezone": "America/Santiago",
            "questlog_region_value": stored_region,
            "slots": slots,
        }
    except Exception as exc:
        print("LIVE_SCRAPE_FAILED", repr(exc))
        # Deliberately publish no guessed rotation. The frontend must show source unavailable.
        payload = {
            "source": "Questlog live scrape unavailable",
            "source_url": URL,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "fallback": False,
            "model": "questlog-live-unavailable-v2",
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
