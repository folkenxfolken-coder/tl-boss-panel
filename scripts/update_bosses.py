import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path("site/boss-data.json")
CHILE = ZoneInfo("America/Santiago")

# Rotation arrays extracted from Questlog's current TL client bundle.
# Questlog's public widget exposes the EU phase only. Eclipse was calibrated
# against the in-game timetable on 2026-08-17: all three visible daytime slots
# (14:00, 17:00, 21:00) match the same 14-day arrays at phase +4.
BASE_DATE_EU = date(2025, 1, 19)
ECLIPSE_PHASE_OFFSET = 4
CYCLE = 14

T3 = {
    "13:00": ["Ahzreil","Nirma","Morokai","Aridus","Adentus","Junobote","Ahzreil","Grand Aelon","Minezerok","Chernobog","Talus","Excavator-9","Adentus","Kowazan"],
    "16:00": ["Excavator-9","Ahzreil","Cornelius","Malakar","Nirma","Morokai","Aridus","Adentus","Junobote","Ahzreil","Grand Aelon","Minezerok","Chernobog","Talus"],
    "20:00": ["Minezerok","Excavator-9","Adentus","Kowazan","Ahzreil","Cornelius","Malakar","Nirma","Morokai","Aridus","Adentus","Junobote","Ahzreil","Grand Aelon"],
    "23:00": ["Junobote","Minezerok","Chernobog","Talus","Excavator-9","Adentus","Kowazan","Ahzreil","Cornelius","Malakar","Nirma","Morokai","Aridus","Adentus"],
    "01:00": ["Adentus","Junobote","Ahzreil","Grand Aelon","Minezerok","Chernobog","Talus","Excavator-9","Adentus","Kowazan","Ahzreil","Cornelius","Malakar","Nirma"],
}
T2 = {
    "13:00": ["Leviathan","Pakilo Naru","Pakilo Naru","Leviathan","Daigon","Leviathan","Manticus","Manticus","Manticus","Daigon","Leviathan","Daigon","Pakilo Naru","Pakilo Naru"],
    "16:00": ["Daigon","Leviathan","Daigon","Manticus","Pakilo Naru","Pakilo Naru","Leviathan","Daigon","Leviathan","Manticus","Manticus","Manticus","Daigon","Leviathan"],
    "20:00": ["Manticus","Daigon","Pakilo Naru","Pakilo Naru","Leviathan","Daigon","Manticus","Pakilo Naru","Pakilo Naru","Leviathan","Daigon","Leviathan","Manticus","Manticus"],
    "23:00": ["Leviathan","Manticus","Daigon","Leviathan","Daigon","Pakilo Naru","Pakilo Naru","Leviathan","Daigon","Manticus","Pakilo Naru","Pakilo Naru","Leviathan","Daigon"],
    "01:00": ["Daigon","Leviathan","Manticus","Manticus","Manticus","Daigon","Leviathan","Daigon","Pakilo Naru","Pakilo Naru","Leviathan","Daigon","Manticus","Pakilo Naru"],
}

# Current Eclipse/Chile display clock. The 2026-08-17 in-game timetable
# confirms 14:00, 17:00 and 21:00. Overnight rows follow the same +1h mapping.
TIME_MAP = {
    "13:00": (14, 0),
    "16:00": (17, 0),
    "20:00": (21, 0),
    "23:00": (0, 1),
    "01:00": (2, 0),
}


def phase_index(source_day: date, source_time: str) -> int:
    idx = ((source_day - BASE_DATE_EU).days + ECLIPSE_PHASE_OFFSET) % CYCLE
    # Questlog's own client algorithm applies the previous cycle index to 01:00.
    if source_time == "01:00":
        idx = (idx - 1) % CYCLE
    return idx


def bosses_for(source_day: date, source_time: str):
    idx = phase_index(source_day, source_time)
    return [
        {"tier": "T3", "name": f"Ascended {T3[source_time][idx]}", "type": "field"},
        {"tier": "T2", "name": T2[source_time][idx], "type": "field"},
    ]


def target_datetime(source_day: date, source_time: str) -> datetime:
    hour, day_shift = TIME_MAP[source_time]
    d = source_day + timedelta(days=day_shift)
    return datetime(d.year, d.month, d.day, hour, 0, tzinfo=CHILE)


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
    # Start yesterday because 23:00 source time maps to 00:00 the following day.
    start = now.date() - timedelta(days=1)
    for offset in range(10):
        source_day = start + timedelta(days=offset)
        for source_time in ("01:00", "13:00", "16:00", "20:00", "23:00"):
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
        "source": "Questlog TL client rotation + Eclipse in-game phase calibration",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fallback": False,
        "model": "eclipse-calibrated-rotation-v1",
        "region": "Americas",
        "server": "Eclipse",
        "timezone": "America/Santiago",
        "cycle_days": CYCLE,
        "phase_offset": ECLIPSE_PHASE_OFFSET,
        "calibration_date": "2026-08-17",
        "slots": build_slots(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
