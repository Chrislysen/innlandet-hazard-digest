"""Stage 4: mechanical verification of the draft against the source Items. No LLM involved.

Every check returns human-readable problems; they are also fed back to the drafter for one repair attempt.
"""
import re
from dataclasses import dataclass, field

from . import config
from .normalize import Item

_COLOR_NB = {"gul": 2, "oransje": 3, "rød": 4, "grøn": 1}
_COLOR_EN = {"yellow": 2, "orange": 3, "red": 4, "green": 1}
_HAZ_WORDS = {"flood": {"nb": r"\bflom", "en": r"\bflood"}, "landslide": {"nb": r"\bjordskred", "en": r"\blandslide"}}
_URL = re.compile(r"https?://\S+|www\.\S+|\b[\w-]+\.(?:com|no|org|net|io|ru|cn)\b|@", re.I)
_INJECTION = re.compile(
    r"ignore (all |the )?(previous|above|prior)|ignorer|disregard|system prompt|systemprompt|"
    r"<items>|</items>|as an ai|new instruction|ny instruks", re.I)
_EMOJI = re.compile("[☀-➿\U0001F300-\U0001FAFF]")
_REQUIRED = ("id", "municipality_id", "hazard", "max_level", "text_nb", "text_en")


@dataclass
class Result:
    problems: list[str] = field(default_factory=list)
    checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems

    def feedback(self) -> str:
        return "\n".join(f"- {p}" for p in self.problems)


def _allowed_numbers(it: Item) -> set[str]:
    blob = " ".join([it.id, it.municipality_id, str(it.max_level)]
                    + [d["date"] + " " + str(d["level"]) for d in it.days] + it.texts)
    return set(re.findall(r"\d+", blob))


def _colors(text: str, table: dict, norwegian: bool) -> set[int]:
    low = text.lower()
    found = set()
    for stem, lvl in table.items():
        pat = rf"\b{stem}\w*" if norwegian else rf"\b{stem}\b"
        if re.search(pat, low):
            found.add(lvl)
    return found


def validate(items: list[Item], draft: dict) -> Result:
    r = Result()
    entries = draft.get("entries")
    if not isinstance(entries, list):
        r.problems.append("draft has no 'entries' list")
        return r
    src = {i.id: i for i in items}
    seen: set[str] = set()
    for n, e in enumerate(entries):
        if not isinstance(e, dict) or any(k not in e for k in _REQUIRED):
            r.problems.append(f"entry #{n}: missing required fields {_REQUIRED}")
            continue
        eid = e["id"]
        if eid in seen:
            r.problems.append(f"{eid}: duplicate entry")
            continue
        seen.add(eid)
        it = src.get(eid)
        if it is None:
            r.problems.append(f"{eid}: not in source (invented entry)")
            continue
        r.checked += 1
        if e["municipality_id"] != it.municipality_id:
            r.problems.append(f"{eid}: municipality_id {e['municipality_id']!r} != source {it.municipality_id!r}")
        if e["hazard"] != it.hazard:
            r.problems.append(f"{eid}: hazard {e['hazard']!r} != source {it.hazard!r}")
        if e["max_level"] != it.max_level:
            r.problems.append(f"{eid}: max_level {e['max_level']!r} != source {it.max_level}")
        levels = {d["level"] for d in it.days} | {it.max_level}
        allowed_nums = _allowed_numbers(it)
        for lang, key, table in (("nb", "text_nb", _COLOR_NB), ("en", "text_en", _COLOR_EN)):
            t = e[key]
            if not isinstance(t, str) or not (20 <= len(t) <= 600):
                r.problems.append(f"{eid}.{key}: missing or length outside 20-600 chars")
                continue
            if it.municipality_name.lower() not in t.lower():
                r.problems.append(f"{eid}.{key}: does not name municipality {it.municipality_name!r}")
            if not re.search(_HAZ_WORDS[it.hazard][lang], t, re.I):
                r.problems.append(f"{eid}.{key}: does not mention the hazard ({it.hazard})")
            other = [h for h in _HAZ_WORDS if h != it.hazard][0]
            if re.search(_HAZ_WORDS[other][lang], t, re.I) and not any(
                    re.search(_HAZ_WORDS[other][lang], x, re.I) for x in it.texts):
                r.problems.append(f"{eid}.{key}: mentions the wrong hazard ({other})")
            bad = _colors(t, table, lang == "nb") - levels
            if bad:
                r.problems.append(f"{eid}.{key}: colour for level(s) {sorted(bad)} not in source levels {sorted(levels)}")
            extra = set(re.findall(r"\d+", t)) - allowed_nums
            if extra:
                r.problems.append(f"{eid}.{key}: numbers not in source: {sorted(extra)}")
            for m in _URL.findall(t):
                if not any(a in m.lower() for a in config.URL_ALLOWLIST):
                    r.problems.append(f"{eid}.{key}: link/address not allowed: {m!r}")
            if _INJECTION.search(t):
                r.problems.append(f"{eid}.{key}: contains instruction-like text (possible prompt injection)")
            if _EMOJI.search(t) or "```" in t or "#" in t:
                r.problems.append(f"{eid}.{key}: contains emoji/markdown")
    for missing in sorted(set(src) - seen):
        r.problems.append(f"{missing}: missing from draft (incomplete)")
    return r
