import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path("site/boss-data.json")
CHILE = ZoneInfo("America/Santiago")

# The boss names rotate on every field-boss slot.  The phase below is anchored
# to a dated Eclipse in-game observation and cross-checked against Questlog's
# dated T3/T2 sequence.  Do not add Archboss names here unless a current source
# identifies the exact boss for Americas; showing no name is better than a
# fabricated Ramux entry.
ANCHOR_DATE = datetime(2026, 7, 15, 14, 0, tzinfo=CHILE)
ANCHOR_INDEX = 5

# Eclipse times observed on the Chile clock.  Earlier builds mistakenly used
# 21:00/00:00; the evening slots are 20:00/23:00.
FIELD_HOURS = [2, 14, 17, 20, 23]

ROTATION = [
    ("Ascended Aridus", "Leviathan"),
    ("Ascended Malakar", "Manticus"),
    ("Ascended Kowazan", "Pakilo Naru"),
    ("Ascended Talus", "Leviathan"),
    ("Ascended Grand Aelon", "Manticus"),
    ("Ascended Adentus", "Daigon"),
    ("Ascended Nirma", "Pakilo Naru"),
    ("Ascended Ahzreil", "Leviathan"),
    ("Ascended Excavator-9", "Daigon"),
    ("Ascended Minezerok", "Manticus"),
    ("Ascended Junobote", "Leviathan"),
    ("Ascended Morokai", "Pakilo Naru"),
    ("Ascended Cornelius", "Daigon"),
    ("Ascended Adentus", "Pakilo Naru"),
    ("Ascended Chernobog", "Daigon"),
    ("Ascended Ahzreil", "Manticus"),
]


def rotation_index(target: datetime) -> int:
    if target.hour not in FIELD_HOURS or target.minute != 0:
        raise ValueError("target must be an Eclipse field-boss slot")
    days = (target.date() - ANCHOR_DATE.date()).days
    anchor_pos = FIELD_HOURS.index(ANCHOR_DATE.hour)
    target_pos = FIELD_HOURS.index(target.hour)
    steps = days * len(FIELD_HOURS) + target_pos - anchor_pos
    return (ANCHOR_INDEX + steps) % len(ROTATION)


def field_bosses_for(target: datetime):
    t3, t2 = ROTATION[rotation_index(target)]
    return [
        {"tier": "T3", "name": t3, "type": "field"},
        {"tier": "T2", "name": t2, "type": "field"},
    ]


def build_slots():
    now = datetime.now(CHILE)
    slots = []
    for offset in range(0, 7):
        day = (now + timedelta(days=offset)).date()
        for hour in FIELD_HOURS:
            target = datetime(day.year, day.month, day.day, hour, 0, tzinfo=CHILE)
            if target <= now:
                continue
            slots.append({
                "date": target.date().isoformat(),
                "time": target.strftime("%H:%M"),
                "bosses": field_bosses_for(target),
            })
    slots.sort(key=lambda x: (x["date"], x["time"]))
    return slots[:16]


def main():
    payload = {
        "source": "Questlog dated T3/T2 sequence + Eclipse in-game timing",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fallback": False,
        "model": "eclipse-field-rotation-v3",
        "anchor": "2026-07-15T14:00 America/Santiago = Ascended Adentus + Daigon",
        "field_hours_chile": ["02:00", "14:00", "17:00", "20:00", "23:00"],
        "archboss_note": "Current public Questlog data does not identify the exact Americas Archboss name; no Archboss is injected without verification.",
        "slots": build_slots(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
