import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://questlog.gg/throne-and-liberty/en/event-calendar"
OUT = Path("site/boss-data.json")


def chile_time(source_time: str) -> str:
    # Questlog's currently displayed boss schedule is one hour behind the
    # Chile clock observed on Eclipse by the user (19->20, 22->23).
    h, m = map(int, source_time.split(":"))
    return f"{(h + 1) % 24:02d}:{m:02d}"


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" -/\n\t")


def parse_field_bosses(text: str):
    # Questlog renders entries such as:
    # T3 Ascended Nirma / T2 Pakilo Naru 20:00 · in 10 hours
    # The regex deliberately supports 2+ bosses in the same time slot.
    rows = []
    for line in text.splitlines():
        line = clean_name(line)
        if not re.search(r"\bT[123]\b", line) or not re.search(r"\b\d{1,2}:\d{2}\b", line):
            continue
        tm = list(re.finditer(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", line))
        if not tm:
            continue
        tmatch = tm[-1]
        source_time = tmatch.group(0)
        before = line[:tmatch.start()].strip()
        bosses = []
        for part in re.split(r"\s*/\s*", before):
            m = re.search(r"\bT([123])\s+(.+)$", part, re.I)
            if not m:
                continue
            name = clean_name(m.group(2))
            if name:
                bosses.append({"tier": f"T{m.group(1)}", "name": name, "type": "field"})
        if bosses:
            rows.append({"time": chile_time(source_time), "bosses": bosses})

    # Deduplicate rows that may appear in multiple responsive DOM sections.
    merged = {}
    for row in rows:
        key = row["time"]
        merged.setdefault(key, [])
        for boss in row["bosses"]:
            if boss not in merged[key]:
                merged[key].append(boss)
    return [{"time": t, "bosses": b} for t, b in merged.items()]


def add_archbosses(text: str, slots):
    # Questlog may expose an "Ark Boss" row without the boss name in the
    # compact upcoming list. When a recognizable Archboss name appears near
    # a clock time in the page text, attach it to that slot.
    arch_names = [
        "Ramux", "Ascended Giant Cordy", "Ascended Deluzhnoa",
        "Ascended Queen Bellandir", "Ascended Tevent",
        "Giant Cordy", "Deluzhnoa", "Queen Bellandir", "Tevent"
    ]
    by_time = {s["time"]: s for s in slots}
    flat = clean_name(text)
    for name in arch_names:
        for m in re.finditer(re.escape(name), flat, re.I):
            window = flat[max(0, m.start()-180):m.end()+180]
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    r = requests.get(URL, headers=headers, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    slots = parse_field_bosses(text)
    slots = add_archbosses(text, slots)
    if not slots:
        raise RuntimeError("Questlog responded, but no boss rows were recognized")

    # Prefer the evening slots the Eclipse panel is focused on, while keeping
    # any additional slot containing a detected Archboss.
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
