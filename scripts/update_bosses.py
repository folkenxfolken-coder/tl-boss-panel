import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path("site/boss-data.json")
CHILE = ZoneInfo("America/Santiago")

# Rotation arrays extracted from Questlog's current TL client bundle.
# For Eclipse we only publish the three windows verified against the
# in-game 2026-08-17 calendar: 14:00, 17:00 and 21:00 Chile time.
BASE_DATE_EU = date(2025, 1, 19)
ECLIPSE_PHASE_OFFSET = 4
CYCLE = 14

T3 = {
    "13:00": ["Ahzreil","Nirma","Morokai","Aridus","Adentus","Junobote","Ahzreil","Grand Aelon","Minezerok","Chernobog","Talus","Excavator-9","Adentus","Kowazan"],
    "16:00": ["Excavator-9","Ahzreil","Cornelius","Malakar","Nirma","Morokai","Aridus","Adentus","Junobote","Ahzreil","Grand Aelon","Minezerok","Chernobog","Talus"],
    "20:00": ["Minezerok","Excavator-9","Adentus","Kowazan","Ahzreil","Cornelius","Malakar","Nirma","Morokai","Aridus","Adentus","Junobote","Ahzreil","Grand Aelon"],
}
T2 = {
    "13:00": ["Leviathan","Pakilo Naru","Pakilo Naru","Leviathan","Daigon","Leviathan","Manticus","Manticus","Manticus","Daigon","Leviathan","Daigon","Pakilo Naru","Pakilo Naru"],
    "16:00": ["Daigon","Leviathan","Daigon","Manticus","Pakilo Naru","Pakilo Naru","Leviathan","Daigon","Leviathan","Manticus","Manticus","Manticus","Daigon","Leviathan"],
    "20:00": ["Manticus","Daigon","Pakilo Naru","Pakilo Naru","Leviathan","Daigon","Manticus","Pakilo Naru","Pakilo Naru","Leviathan","Daigon","Leviathan","Manticus","Manticus"],
}

TIME_MAP = {
    "13:00": 14,
    "16:00": 17,
    "20:00": 21,
}


def phase_index(source_day: date) -> int:
    return ((source_day - BASE_DATE_EU).days + ECLIPSE_PHASE_OFFSET) % CYCLE


def bosses_for(source_day: date, source_time: str):
    idx = phase_index(source_day)
    return [
        {"tier": "T3", "name": f"Ascended {T3[source_time][idx]}", "type": "field"},
        {"tier": "T2", "name": T2[source_time][idx], "type": "field"},
    ]


def target_datetime(source_day: date, source_time: str) -> datetime:
    hour = TIME_MAP[source_time]
    return datetime(source_day.year, source_day.month, source_day.day, hour, 0, tzinfo=CHILE)


def validate_calibration():
    d = date(2026, 8, 17)
    expected = {
        "13:00": ("Ascended Junobote", "Leviathan"),
        "16:00": ("Ascended Morokai", "Pakilo Naru"),
        "20:00": ("Ascended Cornelius", "Daigon"),
    }
    for source_time, names in expected.items():
        got = bosses_for(d, source_time)
        pair = (got[0]["name"], got[1]["name"])
        if pair != names:
            raise RuntimeError(f"Eclipse calibration failed for {source_time}: {pair} != {names}")


def build_slots():
    now = datetime.now(CHILE)
    slots = []
    for offset in range(10):
        source_day = now.date() + timedelta(days=offset)
        for source_time in ("13:00", "16:00", "20:00"):
            dt = target_datetime(source_day, source_time)
            if dt <= now:
                continue
            slots.append({
                "date": dt.date().isoformat(),
                "time": dt.strftime("%H:%M"),
                "bosses": bosses_for(source_day, source_time),
                "source_slot": source_time,
            })
    slots.sort(key=lambda x: (x["date"], x["time"]))
    return slots[:20]


def main():
    validate_calibration()
    payload = {
        "source": "Questlog TL client rotation + Eclipse in-game verified windows",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fallback": False,
        "model": "eclipse-verified-windows-v2",
        "region": "Americas",
        "server": "Eclipse",
        "timezone": "America/Santiago",
        "cycle_days": CYCLE,
        "phase_offset": ECLIPSE_PHASE_OFFSET,
        "calibration_date": "2026-08-17",
        "verified_windows": ["14:00", "17:00", "21:00"],
        "slots": build_slots(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
