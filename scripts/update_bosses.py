import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path("site/boss-data.json")
CHILE = ZoneInfo("America/Santiago")

# Questlog's current boss table uses a 14-day, per-time-slot rotation.  This is
# not one global sequence that advances every spawn: each time has its own T3
# and T2 array, indexed by calendar date.
BASE_DATE = date(2025, 1, 19)
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

# Questlog table time -> Eclipse/Chile clock.  The in-game Eclipse calendar
# supplied on 2026-08-17 confirms the visible boss windows at 14:00, 17:00 and
# 21:00; 20:00 is a Dynamic Event, not a Field Boss.  The overnight windows are
# the same table shifted +1 hour: 23:00 -> 00:00 next day and 01:00 -> 02:00.
TIME_MAP = {
    "01:00": (2, 0),
    "13:00": (14, 0),
    "16:00": (17, 0),
    "20:00": (21, 0),
    "23:00": (0, 1),
}


def rotation_index(ql_day: date, ql_time: str) -> int:
    idx = (ql_day - BASE_DATE).days % CYCLE
    # Questlog explicitly indexes 01:00 against the previous rotation day.
    if ql_time == "01:00":
        idx = (idx - 1) % CYCLE
    return idx


def pair_for(ql_day: date, ql_time: str):
    idx = rotation_index(ql_day, ql_time)
    return [
        {"tier": "T3", "name": f"Ascended {T3[ql_time][idx]}", "type": "field"},
        {"tier": "T2", "name": T2[ql_time][idx], "type": "field"},
    ]


def chile_target(ql_day: date, ql_time: str) -> datetime:
    hour, day_shift = TIME_MAP[ql_time]
    target_day = ql_day + timedelta(days=day_shift)
    return datetime(target_day.year, target_day.month, target_day.day, hour, 0, tzinfo=CHILE)


def build_slots():
    now = datetime.now(CHILE)
    slots = []

    # Include yesterday because its 23:00 Questlog row maps to 00:00 today.
    start = now.date() - timedelta(days=1)
    for offset in range(0, 9):
        ql_day = start + timedelta(days=offset)
        for ql_time in ("01:00", "13:00", "16:00", "20:00", "23:00"):
            target = chile_target(ql_day, ql_time)
            if target <= now:
                continue
            slots.append({
                "date": target.date().isoformat(),
                "time": target.strftime("%H:%M"),
                "bosses": pair_for(ql_day, ql_time),
                "source_slot": ql_time,
            })

    slots.sort(key=lambda x: (x["date"], x["time"]))
    return slots[:16]


def main():
    payload = {
        "source": "Questlog current 14-day per-time boss rotation mapped to Eclipse/Chile",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fallback": False,
        "model": "questlog-eclipse-date-rotation-v4",
        "base_date": BASE_DATE.isoformat(),
        "field_hours_chile": ["00:00", "02:00", "14:00", "17:00", "21:00"],
        "archboss_note": "No exact Archboss name is injected until the current Americas source identifies it explicitly.",
        "slots": build_slots(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
