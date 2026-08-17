import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

URL = "https://questlog.gg/throne-and-liberty/sa/event-calendar"
READER_URL = "https://r.jina.ai/http://questlog.gg/throne-and-liberty/sa/event-calendar"
OUT = Path("site/boss-data.json")


def chile_time(source_time: str) -> str:
    # Ajuste observado en Eclipse por el usuario: la franja mostrada como
    # 19:00/22:00 en la fuente corresponde a 20:00/23:00 en su horario de Chile.
    h, m = map(int, source_time.split(":"))
    return f"{(h + 1) % 24:02d}:{m:02d}"


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" -/\n\t")


def fetch_text() -> str:
    r = requests.get(
        READER_URL,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "text/plain"},
        timeout=60,
    )
    r.raise_for_status()
    if len(r.text) < 500:
        raise RuntimeError("Reader response too short")
    return r.text


def parse_field_bosses(text: str):
    rows = []
    lines = [clean_name(re.sub(r"^[*#>\-]+\s*", "", x)) for x in text.splitlines()]
    # Además de líneas individuales, inspeccionamos ventanas cortas porque el
    # Markdown puede separar tier, nombre y hora en líneas consecutivas.
    candidates = [x for x in lines if x]
    candidates += [clean_name(" ".join(lines[i:i+4])) for i in range(len(lines))]

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
            if name and len(name) < 90:
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
    text = fetch_text()
    slots = add_archbosses(text, parse_field_bosses(text))
    if not slots:
        print(text[:8000])
        raise RuntimeError("No boss rows recognized from Latin America reader output")

    # El panel prioriza las franjas que el usuario usa en Chile, pero conserva
    # cualquier franja adicional si contiene un Archboss.
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
        "slots": slots,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
