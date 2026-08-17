import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://questlog.gg/throne-and-liberty/en/event-calendar"
OUT = Path("site/boss-data.json")


def chile_time(source_time: str) -> str:
    h, m = map(int, source_time.split(":"))
    return f"{(h + 1) % 24:02d}:{m:02d}"


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" -/\n\t")


def rendered_text() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1440, "height": 1200},
            locale="en-US",
            timezone_id="UTC",
        )
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        text = page.locator("body").inner_text(timeout=30000)
        browser.close()
        return text


def parse_field_bosses(text: str):
    rows = []
    lines = [clean_name(x) for x in text.splitlines() if clean_name(x)]

    # Questlog can render each entry on one line or split boss/time into
    # adjacent lines. We therefore inspect short rolling windows of lines.
    windows = []
    for i in range(len(lines)):
        windows.append(" ".join(lines[i:i+4]))

    for line in windows:
        if not re.search(r"\bT[123]\b", line) or not re.search(r"\b\d{1,2}:\d{2}\b", line):
            continue
        tm = list(re.finditer(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", line))
        if not tm:
            continue
        tmatch = tm[-1]
        source_time = tmatch.group(0)
        before = line[:tmatch.start()].strip()

        bosses = []
        # Capture every Tn name before either '/', the next Tn, or the time.
        pattern = re.compile(r"\bT([123])\s+(.+?)(?=\s*/\s*T[123]\b|\s+T[123]\b|\s+\d{1,2}:\d{2}\b|$)", re.I)
        for m in pattern.finditer(before):
            name = clean_name(m.group(2))
            name = re.sub(r"\s+(?:in|ago)\s+.*$", "", name, flags=re.I).strip()
            if name and len(name) < 90:
                bosses.append({"tier": f"T{m.group(1)}", "name": name, "type": "field"})
        if bosses:
            rows.append({"time": chile_time(source_time), "bosses": bosses})

    merged = {}
    for row in rows:
        key = row["time"]
        merged.setdefault(key, [])
        for boss in row["bosses"]:
            if boss not in merged[key]:
                merged[key].append(boss)
    return [{"time": t, "bosses": b} for t, b in merged.items()]


def add_archbosses(text: str, slots):
    arch_names = [
        "Ramux", "Ascended Giant Cordy", "Ascended Deluzhnoa",
        "Ascended Queen Bellandir", "Ascended Tevent",
        "Giant Cordy", "Deluzhnoa", "Queen Bellandir", "Tevent"
    ]
    by_time = {s["time"]: s for s in slots}
    flat = clean_name(text)
    for name in arch_names:
        for m in re.finditer(re.escape(name), flat, re.I):
            window = flat[max(0, m.start()-220):m.end()+220]
            if not re.search(r"arch\s*boss|archboss|ark\s*boss", window, re.I):
                continue
            times = re.findall(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", window)
            if not times:
                continue
            source_time = f"{int(times[0][0]):02d}:{times[0][1]}"
            t = chile_time(source_time)
            slot = by_time.setdefault(t, {"time": t, "bosses": []})
            boss = {"tier": "ARCH", "name": name, "type": "archboss"}
            if boss not in slot["bosses"]:
                slot["bosses"].append(boss)
    return list(by_time.values())


def main():
    text = rendered_text()
    slots = parse_field_bosses(text)
    slots = add_archbosses(text, slots)
    if not slots:
        print(text[:5000])
        raise RuntimeError("Questlog rendered, but no boss rows were recognized")

    preferred = []
    for s in slots:
        if s["time"] in {"20:00", "23:00"} or any(b["type"] == "archboss" for b in s["bosses"]):
            preferred.append(s)
    if preferred:
        slots = preferred

    slots.sort(key=lambda x: tuple(map(int, x["time"].split(":"))))
    payload = {
        "source": URL,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fallback": False,
        "slots": slots,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
