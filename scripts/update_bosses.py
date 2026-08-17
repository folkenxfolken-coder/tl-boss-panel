import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

URL = "https://questlog.gg/throne-and-liberty/en/rain-schedule"
QUESTLOG_PAGES = [
    "https://questlog.gg/throne-and-liberty/en/rain-schedule",
    "https://questlog.gg/throne-and-liberty/en/server-status",
    "https://questlog.gg/throne-and-liberty/en/day-and-night-schedule",
]
OUT = Path("site/boss-data.json")


def chile_time(source_time: str) -> str:
    # Questlog's shared timer sidebar currently exposes the relevant boss slots
    # as 20:00 and 23:00; those are also the observed Eclipse times in Chile.
    h, m = map(int, source_time.split(":"))
    return f"{h:02d}:{m:02d}"


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" -/\n\t")


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)


def fetch_microlink_text() -> tuple[str, str]:
    errors = []
    for page in QUESTLOG_PAGES:
        endpoint = "https://api.microlink.io/?url=" + quote(page, safe="") + "&text=true&meta=false"
        try:
            r = requests.get(
                endpoint,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=75,
            )
            r.raise_for_status()
            payload = r.json()
            candidates = [s for s in strings_in(payload) if len(s) > 200]
            useful = [s for s in candidates if re.search(r"Upcoming Field Bosses|T[123]", s, re.I)]
            if useful:
                return max(useful, key=len), "microlink:" + page.rsplit("/", 1)[-1]
        except Exception as exc:
            errors.append(f"{page}: {exc}")
    raise RuntimeError(" ; ".join(errors) or "Microlink did not return boss text")


def fetch_jina_text() -> tuple[str, str]:
    errors = []
    for page in QUESTLOG_PAGES:
        reader = "https://r.jina.ai/http://" + page.removeprefix("https://")
        try:
            r = requests.get(
                reader,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "text/plain"},
                timeout=60,
            )
            r.raise_for_status()
            text = r.text
            if len(text) > 500 and re.search(r"Upcoming Field Bosses|T[123]", text, re.I):
                return text, "jina:" + page.rsplit("/", 1)[-1]
        except Exception as exc:
            errors.append(f"{page}: {exc}")
    raise RuntimeError(" ; ".join(errors) or "Jina did not return boss text")


def fetch_text() -> tuple[str, str]:
    errors = []
    for label, fn in (("microlink", fetch_microlink_text), ("jina", fetch_jina_text)):
        try:
            return fn()
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    raise RuntimeError(" | ".join(errors))


def parse_field_bosses(text: str):
    rows = []
    lines = [clean_name(re.sub(r"^[*#>\-]+\s*", "", x)) for x in text.splitlines()]
    candidates = [x for x in lines if x]
    candidates += [clean_name(" ".join(lines[i:i+5])) for i in range(len(lines))]

    for line in candidates:
        if not re.search(r"\bT[123]\b", line) or not re.search(r"\b\d{1,2}:\d{2}\b", line):
            continue
        tm = list(re.finditer(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", line))
        if not tm:
            continue
        tmatch = tm[-1]
        source_time = tmatch.group(0)
        before = line[:tmatch.start()].strip()
        bosses = []
        pattern = re.compile(
            r"\bT([123])\s+(.+?)(?=\s*/\s*T[123]\b|\s+T[123]\b|\s+\d{1,2}:\d{2}\b|$)",
            re.I,
        )
        for m in pattern.finditer(before):
            name = clean_name(m.group(2))
            name = re.sub(r"\s+(?:in|hace|em)\s+.*$", "", name, flags=re.I).strip()
            if name and len(name) < 90 and not re.fullmatch(r"Field Boss(?:es)?|Jefes? de Campo", name, re.I):
                bosses.append({"tier": f"T{m.group(1)}", "name": name, "type": "field"})
        if bosses:
            rows.append({"time": chile_time(source_time), "bosses": bosses})

    merged = {}
    for row in rows:
        merged.setdefault(row["time"], [])
        for boss in row["bosses"]:
            if boss not in merged[row["time"]]:
                merged[row["time"]].append(boss)
    return [{"time": t, "bosses": b} for t, b in merged.items()]


def add_archbosses(text: str, slots):
    arch_names = [
        "Ramux", "Ramus", "Ascended Giant Cordy", "Ascended Deluzhnoa",
        "Ascended Queen Bellandir", "Ascended Tevent", "Giant Cordy",
        "Deluzhnoa", "Queen Bellandir", "Tevent",
    ]
    by_time = {s["time"]: s for s in slots}
    flat = clean_name(text)
    for name in arch_names:
        for m in re.finditer(re.escape(name), flat, re.I):
            window = flat[max(0, m.start()-250):m.end()+250]
            if not re.search(r"arch\s*boss|archboss|ark\s*boss|arqui", window, re.I):
                continue
            times = re.findall(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", window)
            if not times:
                continue
            source_time = f"{int(times[0][0]):02d}:{times[0][1]}"
            t = chile_time(source_time)
            slot = by_time.setdefault(t, {"time": t, "bosses": []})
            boss = {"tier": "ARCH", "name": "Ramux" if name == "Ramus" else name, "type": "archboss"}
            if boss not in slot["bosses"]:
                slot["bosses"].append(boss)
    return list(by_time.values())


def main():
    text, fetcher = fetch_text()
    slots = add_archbosses(text, parse_field_bosses(text))
    if not slots:
        print(text[:8000])
        raise RuntimeError(f"No boss rows recognized from {fetcher} output")

    preferred = [
        s for s in slots
        if s["time"] in {"20:00", "23:00"}
        or any(b["type"] == "archboss" for b in s["bosses"])
    ]
    if preferred:
        slots = preferred

    slots.sort(key=lambda x: tuple(map(int, x["time"].split(":"))))
    payload = {
        "source": URL,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fallback": False,
        "fetcher": fetcher,
        "slots": slots,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
