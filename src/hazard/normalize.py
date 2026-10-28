"""Stage 2: reduce raw payloads to a small, checkable set of Items (one per municipality+hazard)."""
import re
from dataclasses import dataclass, field, asdict

from . import config

_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_text(s: str | None) -> str:
    """Untrusted source text: strip control chars, collapse whitespace, cap length."""
    if not s:
        return ""
    s = _CTRL.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[: config.MAX_SOURCE_TEXT_CHARS]


@dataclass
class Item:
    id: str                 # e.g. "3405-flood"
    municipality_id: str
    municipality_name: str
    hazard: str             # flood | landslide
    max_level: int
    days: list[dict]        # [{"date": "2026-10-29", "level": 3}, ...]
    texts: list[str] = field(default_factory=list)  # unique official texts (untrusted)

    def to_dict(self):
        return asdict(self)


def normalize(raw: dict[str, dict]) -> tuple[list[Item], dict]:
    """Return (items, stats). Only county 34 and level >= MIN_LEVEL survive."""
    items: dict[str, Item] = {}
    stats = {"municipalities_seen": 0, "warnings_seen": 0, "dropped_green": 0, "dropped_other_county": 0}
    for hazard, payload in raw.items():
        for county in payload["CountyList"]:
            if county["Id"] != config.COUNTY_ID:
                stats["dropped_other_county"] += len(county.get("MunicipalityList") or [])
                continue
            for m in county["MunicipalityList"] or []:
                stats["municipalities_seen"] += 1
                for w in m.get("WarningList") or []:
                    stats["warnings_seen"] += 1
                    try:
                        level = int(w.get("ActivityLevel"))
                    except (TypeError, ValueError):
                        continue  # malformed level: never guess
                    if level < config.MIN_LEVEL:
                        stats["dropped_green"] += 1
                        continue
                    iid = f"{m['Id']}-{hazard}"
                    it = items.setdefault(iid, Item(iid, str(m["Id"]), m["Name"], hazard, 0, []))
                    it.max_level = max(it.max_level, level)
                    d = (w.get("ValidFrom") or "")[:10]
                    if d and not any(x["date"] == d and x["level"] == level for x in it.days):
                        it.days.append({"date": d, "level": level})
                    for key in ("MainText", "WarningText", "AdviceText"):
                        t = clean_text(w.get(key))
                        if t and t not in it.texts:
                            it.texts.append(t)
    out = sorted(items.values(), key=lambda i: (-i.max_level, i.municipality_name, i.hazard))
    for it in out:
        it.days.sort(key=lambda x: x["date"])
    return out, stats
