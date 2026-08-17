import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path("site/boss-data.json")
CHILE = ZoneInfo("America/Santiago")

# Questlog's indexed calendar after update 4.2.0 exposes a stable 16-step
# T3/T2 rotation. 2026-07-09 13:00 is an explicit date anchor where the
# calendar shows Ascended Adentus + Daigon. Hidden slots (01/13/16) still
# advance the rotation even though this dashboard only displays 20/23.
ANCHOR_DATE = datetime(2026, 7, 9, 13, 0, tzinfo=CHILE)
ANCHOR_INDEX = 5
ALL_FIELD_HOURS = [1, 13, 16, 20, 23]
DISPLAY_HOURS = [20, 23]

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
    """Return rotation phase for an exact standard field-boss slot."""
    if target.hour not in ALL_FIELD_HOURS or target.minute != 0:
        raise ValueError("target must be a standard field boss slot")
    days = (target.date() - ANCHOR_DATE.date()).days
    anchor_pos = ALL_FIELD_HOURS.index(ANCHOR_DATE.hour)
    target_pos = ALL_FIELD_HOURS.index(target.hour)
    steps = days * len(ALL_FIELD_HOURS) + target_pos - anchor_pos
    return (ANCHOR_INDEX + steps) % len(ROTATION)


def field_bosses_for(target: datetime):
    i = rotation_index(target)
    t3, t2 = ROTATION[i]
    return [
        {"tier": "T3", "name": t3, "type": "field"},
        {"tier": "T2", "name": t2, "type": "field"},
    ]


def add_known_archbosses(target: datetime, bosses: list[dict]):
    # Update 4.5.0 added Ramux Peace/Guild events on Tuesdays and Fridays
    # at 19:00 and 22:00 server time. For this Eclipse/Chile dashboard the
    # user-observed corresponding display slots are 20:00 and 23:00.
    if target.weekday() in {1, 4}:  # Tuesday, Friday
        bosses.append({"tier": "ARCH", "name": "Ramux", "type": "archboss"})
    return bosses


def build_slots():
    now = datetime.now(CHILE)
    slots = []
    # Include enough future data that the page never has to invent/repeat names.
    for offset in range(0, 8):
        day = (now + timedelta(days=offset)).date()
        for hour in DISPLAY_HOURS:
            target = datetime(day.year, day.month, day.day, hour, 0, tzinfo=CHILE)
            if target <= now:
                continue
            bosses = add_known_archbosses(target, field_bosses_for(target))
            slots.append({
                "date": target.date().isoformat(),
                "time": target.strftime("%H:%M"),
                "bosses": bosses,
            })
    return slots[:10]


def main():
    payload = {
        "source": "Questlog indexed boss rotation + official TL Update 4.5.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fallback": False,
        "model": "dated-rotation-v1",
        "anchor": "2026-07-09T13:00 America/Santiago",
        "slots": build_slots(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
