import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path("site/boss-data.json")
CHILE = ZoneInfo("America/Santiago")

# IMPORTANT:
# The field-boss rotation advances on EVERY field-boss spawn, not only on the
# evening spawns. This is why the previous 20:00/23:00-only model mixed names.
#
# Questlog's indexed calendar for 2026-07-15 shows this consecutive sequence:
#   01:00 Ascended Grand Aelon + Manticus
#   13:00 Ascended Adentus + Daigon
#   16:00 Ascended Nirma + Pakilo Naru
#   20:00 Ascended Ahzreil + Leviathan
#   23:00 Ascended Excavator-9 + Daigon
#
# The user's Eclipse in-game calendar is one hour later on the Chile clock in
# the supplied screenshot, so the corresponding Chile slots are
# 02:00 / 14:00 / 17:00 / 21:00 / 00:00.
# We anchor the rotation at the unambiguous 14:00 Adentus+Daigon slot.
ANCHOR_DATE = datetime(2026, 7, 15, 14, 0, tzinfo=CHILE)
ANCHOR_INDEX = 5

# Actual Chile-local field-boss slots for this Eclipse panel.
FIELD_HOURS = [0, 2, 14, 17, 21]

# 16-step T3/T2 rotation reconstructed from overlapping dated Questlog indexes.
# Repeated bosses in the cycle are intentional: the paired T2 differs.
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
    """Return the rotation phase for an exact Chile-local field-boss slot."""
    if target.hour not in FIELD_HOURS or target.minute != 0:
        raise ValueError("target must be a standard field-boss slot")

    days = (target.date() - ANCHOR_DATE.date()).days
    anchor_pos = FIELD_HOURS.index(ANCHOR_DATE.hour)
    target_pos = FIELD_HOURS.index(target.hour)
    steps = days * len(FIELD_HOURS) + target_pos - anchor_pos
    return (ANCHOR_INDEX + steps) % len(ROTATION)


def field_bosses_for(target: datetime):
    i = rotation_index(target)
    t3, t2 = ROTATION[i]
    return [
        {"tier": "T3", "name": t3, "type": "field"},
        {"tier": "T2", "name": t2, "type": "field"},
    ]


def build_slots():
    now = datetime.now(CHILE)
    slots = []

    # Generate all five daily field-boss slots. The old version only emitted
    # 20/23 and therefore skipped three rotation advances every day.
    for offset in range(0, 6):
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
    return slots[:14]


def main():
    payload = {
        "source": "Questlog indexed dated rotation + Eclipse in-game calendar",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fallback": False,
        "model": "dated-rotation-v2-all-slots",
        "anchor": "2026-07-15T14:00 America/Santiago = Ascended Adentus + Daigon",
        "field_hours_chile": ["00:00", "02:00", "14:00", "17:00", "21:00"],
        "slots": build_slots(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
