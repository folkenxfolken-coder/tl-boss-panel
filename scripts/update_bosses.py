import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

OUT = Path("site/boss-data.json")
CHILE = ZoneInfo("America/Santiago")
URL = "https://questlog.gg/throne-and-liberty/en/event-calendar"

# Last-resort fallback only. The live Questlog scrape is always attempted first.
BASE_DATE = datetime(2025, 1, 19).date()
CYCLE = 14
T3 = {
    "13:00": ["Ahzreil", "Nirma", "Morokai", "Aridus", "Adentus", "Junobote", "Ahzreil", "Grand Aelon", "Minezerok", "Chernobog", "Talus", "Excavator-9", "Adentus", "Kowazan"],
    "16:00": ["Excavator-9", "Ahzreil", "Cornelius", "Malakar", "Nirma", "Morokai", "Aridus", "Adentus", "Junobote", "Ahzreil", "Grand Aelon", "Minezerok", "Chernobog", "Talus"],
    "20:00": ["Minezerok", "Excavator-9", "Adentus", "Kowazan", "Ahzreil", "Cornelius", "Malakar", "Nirma", "Morokai", "Aridus", "Adentus", "Junobote", "Ahzreil", "Grand Aelon"],
    "23:00": ["Junobote", "Minezerok", "Chernobog", "Talus", "Excavator-9", "Adentus", "Kowazan", "Ahzreil", "Cornelius", "Malakar", "Nirma", "Morokai", "Aridus", "Adentus"],
    "01:00": ["Adentus", "Junobote", "Ahzreil", "Grand Aelon", "Minezerok", "Chernobog", "Talus", "Excavator-9", "Adentus", "Kowazan", "Ahzreil", "Cornelius", "Malakar", "Nirma"],
}
T2 = {
    "13:00": ["Leviathan", "Pakilo Naru", "Pakilo Naru", "Leviathan", "Daigon", "Leviathan", "Manticus", "Manticus", "Manticus", "Daigon", "Leviathan", "Daigon", "Pakilo Naru", "Pakilo Naru"],
    "16:00": ["Daigon", "Leviathan", "Daigon", "Manticus", "Pakilo Naru", "Pakilo Naru", "Leviathan", "Daigon", "Leviathan", "Manticus", "Manticus", "Manticus", "Daigon", "Leviathan"],
    "20:00": ["Manticus", "Daigon", "Pakilo Naru", "Pakilo Naru", "Leviathan", "Daigon", "Manticus", "Pakilo Naru", "Pakilo Naru", "Leviathan", "Daigon", "Leviathan", "Manticus", "Manticus"],
    "23:00": ["Leviathan", "Manticus", "Daigon", "Leviathan", "Daigon", "Pakilo Naru", "Pakilo Naru", "Leviathan", "Daigon", "Manticus", "Pakilo Naru", "Pakilo Naru", "Leviathan", "Daigon"],
    "01:00": ["Daigon", "Leviathan", "Manticus", "Manticus", "Manticus", "Daigon", "Leviathan", "Daigon", "Pakilo Naru", "Pakilo Naru", "Leviathan", "Daigon", "Manticus", "Pakilo Naru"],
}
TIME_MAP = {"01:00": "02:00", "13:00": "14:00", "16:00": "17:00", "20:00": "21:00", "23:00": "00:00"}


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


def parse_upcoming(text):
    # Questlog renders each upcoming slot on one line, e.g.
    # T3 Ascended Junobote / T2 Leviathan 16:00 · in 5 hours
    section_match = re.search(r"Upcoming Field Bosses\s*(.*?)(?:\n\s*Image|\n\s*English|\n\s*Current Game|\n\s*#\s*Event Calendar|\Z)", text, re.S | re.I)
    section = section_match.group(1) if section_match else text

    pattern = re.compile(
        r"T3\s+(.+?)\s*/\s*T2\s+(.+?)\s+(\d{2}:\d{2})(?:\s*[·•].*)?$",
        re.M,
    )
    found = pattern.findall(section)
    if not found:
        # Some layouts split the countdown text differently; accept the core triplet.
        pattern = re.compile(r"T3\s+(.+?)\s*/\s*T2\s+(.+?)\s+(\d{2}:\d{2})", re.I)
        found = pattern.findall(section)

    # Keep order and remove duplicate cards that may exist in responsive DOMs.
    unique = []
    seen = set()
    for t3, t2, hhmm in found:
        key = (t3.strip(), t2.strip(), hhmm)
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
        await page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(5000)

        # Questlog defaults to Europe. Change the timer region to Americas.
        # The control has changed markup before, so try several safe strategies.
        changed = False
        for selector in [
            "button:has-text('Europe')",
            "[role='button']:has-text('Europe')",
            "text=Europe",
        ]:
            try:
                loc = page.locator(selector).first
                if await loc.count() and await loc.is_visible():
                    await loc.click(timeout=3000)
                    await page.wait_for_timeout(700)
                    americas = page.get_by_text("Americas", exact=True)
                    if await americas.count():
                        for i in range(await americas.count()):
                            a = americas.nth(i)
                            if await a.is_visible():
                                await a.click(timeout=3000)
                                changed = True
                                await page.wait_for_timeout(2500)
                                break
                if changed:
                    break
            except Exception:
                pass

        body = await page.locator("body").inner_text()
        rows = parse_upcoming(body)
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
                {"tier": "T3", "name": t3.strip(), "type": "field"},
                {"tier": "T2", "name": t2.strip(), "type": "field"},
            ],
        })

    return slots, changed


def fallback_slots():
    now = datetime.now(CHILE)
    slots = []
    for offset in range(-1, 8):
        ql_day = now.date() + timedelta(days=offset)
        idx_base = (ql_day - BASE_DATE).days % CYCLE
        for ql_time in ("01:00", "13:00", "16:00", "20:00", "23:00"):
            idx = (idx_base - 1) % CYCLE if ql_time == "01:00" else idx_base
            chile_time = TIME_MAP[ql_time]
            h, m = map(int, chile_time.split(":"))
            target_day = ql_day + (timedelta(days=1) if ql_time == "23:00" else timedelta())
            target = datetime(target_day.year, target_day.month, target_day.day, h, m, tzinfo=CHILE)
            if target <= now:
                continue
            slots.append({
                "date": target_day.isoformat(),
                "time": chile_time,
                "bosses": [
                    {"tier": "T3", "name": f"Ascended {T3[ql_time][idx]}", "type": "field"},
                    {"tier": "T2", "name": T2[ql_time][idx], "type": "field"},
                ],
            })
    slots.sort(key=lambda x: (x["date"], x["time"]))
    return slots[:8]


async def main():
    fallback = False
    region_changed = False
    try:
        slots, region_changed = await scrape_questlog()
        source = "Questlog live Upcoming Field Bosses"
        model = "questlog-live-americas-v1"
    except Exception as exc:
        print("LIVE_SCRAPE_FAILED", repr(exc))
        slots = fallback_slots()
        fallback = True
        source = "Questlog live scrape failed; 14-day emergency fallback"
        model = "questlog-fallback-v1"

    payload = {
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fallback": fallback,
        "model": model,
        "region": "Americas",
        "timezone": "America/Santiago",
        "region_control_changed": region_changed,
        "slots": slots,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
