"""Stage 2: reduce raw payloads to a small, checkable set of Items (one per municipality+hazard)."""
import re
from dataclasses import dataclass, field, asdict

from . import config

_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_text(s: str | None, cap: bool = True) -> str:
    """Untrusted source text: strip control chars, collapse whitespace, optionally cap length."""
    if not s:
        return ""
    s = _CTRL.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[: config.MAX_SOURCE_TEXT_CHARS] if cap else s


_OFFICIAL_FIELDS = (("main", "MainText"), ("warning", "WarningText"), ("advice", "AdviceText"),
                    ("consequence", "ConsequenceText"), ("level_meaning", "LevelMeaningText"))


@dataclass
class Item:
    id: str                 # e.g. "3405-flood"
    municipality_id: str
    municipality_name: str
    hazard: str             # flood | landslide
    max_level: int
    days: list[dict]        # [{"date": "2026-10-29", "level": 3}, ...]
    texts: list[str] = field(default_factory=list)  # capped official texts shown to the agent (untrusted)
    official: list[dict] = field(default_factory=list)  # complete official texts, kept verbatim for the digest

    def to_dict(self):
        return asdict(self)

    def to_model_dict(self):
        """Bounded input for the agent: capped texts only. Complete official text stays out of the prompt."""
        d = asdict(self)
        d.pop("official")
        return d


def normalize(raw: dict[str, dict]) -> tuple[list[Item], dict]:
    """Return (items, stats). Only county 34 and level >= MIN_LEVEL survive."""
    items: dict[str, Item] = {}
    stats = {"municipalities_seen": 0, "warnings_seen": 0, "dropped_green": 0, "dropped_other_county": 0,
             "invalid_levels": 0, "valid_by_hazard": {h: 0 for h in raw}}
    valid_dates: set[str] = set()
    for hazard, payload in raw.items():
        for county in payload["CountyList"]:
            if county["Id"] != config.COUNTY_ID:
                stats["dropped_other_county"] += len(county.get("MunicipalityList") or [])
                continue
            for m in county["MunicipalityList"] or []:
                stats["municipalities_seen"] += 1
                assessed = False
                for w in m.get("WarningList") or []:
                    stats["warnings_seen"] += 1
                    try:
                        level = int(w.get("ActivityLevel"))
                    except (TypeError, ValueError):
                        level = 0
                    if not 1 <= level <= 4:  # missing, unassessed (0) or malformed: never guess, never count as green
                        stats["invalid_levels"] += 1
                        continue
                    assessed = True
                    valid_dates.add((w.get("ValidFrom") or "")[:10])
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
                    full = {k: clean_text(w.get(src), cap=False) for k, src in _OFFICIAL_FIELDS}
                    full["level"] = level
                    full["valid_from"] = w.get("ValidFrom")  # kept exactly as published, offsets not guessed
                    full["valid_to"] = w.get("ValidTo")
                    full["version"] = w.get("Version")
                    same = [o for o in it.official if all(o[k] == full[k] for k, _ in _OFFICIAL_FIELDS)
                            and o["level"] == level]
                    if same:
                        same[0]["dates"].append(d)
                    elif any(full[k] for k, _ in _OFFICIAL_FIELDS):
                        full["dates"] = [d]
                        it.official.append(full)
                if assessed:
                    stats["valid_by_hazard"][hazard] += 1
    stats["valid_dates"] = sorted(d for d in valid_dates if d)
    out = sorted(items.values(), key=lambda i: (-i.max_level, i.municipality_name, i.hazard))
    for it in out:
        it.days.sort(key=lambda x: x["date"])
    return out, stats
