"""Stage 4: mechanical verification of the draft against the source Items. No LLM involved.

What this does and does not establish: it proves that the structured fields (id, hazard, level) equal the source,
that every source item is covered, and that the free text contains no colour, number, date, link or flagged
advice/reassurance word that the source does not support. It does NOT understand sentence meaning, so a human
still reviews the summary before publication.
"""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import config
from .normalize import Item

_COLOR_NB = {"gul": 2, "oransje": 3, "rød": 4, "grøn": 1}
_COLOR_EN = {"yellow": 2, "orange": 3, "red": 4, "green": 1}
_HAZ_WORDS = {"flood": {"nb": r"\bflom", "en": r"\bflood"}, "landslide": {"nb": r"\bjordskred", "en": r"\blandslide"}}

_TLDS = "com|no|org|net|io|ru|cn|info|xyz|biz|se|dk|eu|uk|de|me|co|app|dev|ly|gl|tk|ml|site|online|top"
_URLISH = re.compile(rf"(?:https?://|www\.)[^\s)<>\]\"']+|\b(?:[a-z0-9-]+\.)+(?:{_TLDS})\b", re.I)
_INJECTION = re.compile(
    r"ignore (all |the )?(previous|above|prior)|ignorer|disregard|system prompt|systemprompt|"
    r"<items>|</items>|as an ai|new instruction|ny instruks", re.I)
_EMOJI = re.compile("[☀-➿\U0001F300-\U0001FAFF]")
_RISKY = re.compile(
    r"\b(evakuer\w*|evacuat\w*|safe|safely|trygt|trygg|ufarlig|no (?:danger|risk)|ingen (?:fare|risiko)|"
    r"no need to worry|nothing to worry|ikke bekymre\w*)\b", re.I)
_MONTHS = {"januar": 1, "january": 1, "februar": 2, "february": 2, "mars": 3, "march": 3, "april": 4, "mai": 5,
           "may": 5, "juni": 6, "june": 6, "juli": 7, "july": 7, "august": 8, "september": 9, "oktober": 10,
           "october": 10, "november": 11, "desember": 12, "december": 12}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}})\.?\s+(?:av\s+)?({_MONTH_RE})\b", re.I)
_MONTH_DAY = re.compile(rf"\b({_MONTH_RE})\s+(\d{{1,2}})\b", re.I)
_ISO = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_SEP = r"\s*(?:–|—|-|til|to|through|until)\s*(?:den\s+)?"
_BARE_RANGE_NB = re.compile(rf"\b(\d{{1,2}})\.?{_SEP}(\d{{1,2}})\.?\s+(?:av\s+)?({_MONTH_RE})\b", re.I)
_BARE_RANGE_EN = re.compile(rf"\b({_MONTH_RE})\s+(\d{{1,2}}){_SEP}(\d{{1,2}})\b", re.I)
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


def host_allowed(token: str) -> bool:
    """Judge a link by its parsed hostname, never by substring: varsom.no.evil.com is NOT varsom.no."""
    t = re.sub(r"^https?://", "", token.strip(".,;:!?)\"'"), flags=re.I)
    host = re.split(r"[/?#:<]", t, maxsplit=1)[0].lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return any(host == a or host.endswith("." + a) for a in config.URL_ALLOWLIST)


def foreign_links(text: str) -> list[str]:
    return [m for m in _URLISH.findall(text) if not host_allowed(m)] + (["@"] if "@" in text else [])


def _blob(it: Item) -> str:
    return " ".join([it.id, it.municipality_id, str(it.max_level)]
                    + [d["date"] + " " + str(d["level"]) for d in it.days] + it.texts
                    + [" ".join(str(x) for x in o.values()) for o in it.official])


def _allowed_numbers(it: Item) -> set[str]:
    return set(re.findall(r"\d+", _blob(it)))


def _allowed_dates(it: Item) -> tuple[set[str], set[tuple[int, int]]]:
    iso = {d["date"] for d in it.days}
    for o in it.official:
        for k in ("valid_from", "valid_to"):
            if o.get(k):
                iso.add(str(o[k])[:10])
    md = {(int(x[5:7]), int(x[8:10])) for x in iso if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)}
    return iso, md


def _colors(text: str, table: dict, norwegian: bool) -> set[int]:
    low = text.lower()
    found = set()
    for stem, lvl in table.items():
        pat = rf"\b{stem}\w*" if norwegian else rf"\b{stem}\b"
        if re.search(pat, low):
            found.add(lvl)
    return found


def _date_problems(t: str, iso: set[str], md: set[tuple[int, int]]) -> list[str]:
    bad = [x for x in _ISO.findall(t) if x not in iso]
    for d, mo in _DAY_MONTH.findall(t):
        if (_MONTHS[mo.lower()], int(d)) not in md:
            bad.append(f"{d} {mo}")
    for mo, d in _MONTH_DAY.findall(t):
        if (_MONTHS[mo.lower()], int(d)) not in md:
            bad.append(f"{mo} {d}")
    return bad


def _mentions(t: str) -> list[tuple[int, int, tuple[int, int]]]:
    """Every date mention as (start, end, (month, day))."""
    out = [(m.start(), m.end(), (int(m.group()[5:7]), int(m.group()[8:10]))) for m in _ISO.finditer(t)]
    out += [(m.start(), m.end(), (_MONTHS[m.group(2).lower()], int(m.group(1)))) for m in _DAY_MONTH.finditer(t)]
    out += [(m.start(), m.end(), (_MONTHS[m.group(1).lower()], int(m.group(2)))) for m in _MONTH_DAY.finditer(t)]
    return sorted(out)


def _between(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    start = date(2000, *a)
    end = date(2000 if b >= a else 2001, *b)
    if (end - start).days > 31:
        return [a, b, (0, 0)]  # implausible span: report it
    return [((start + timedelta(n)).month, (start + timedelta(n)).day) for n in range((end - start).days + 1)]


def _range_problems(t: str, warned: set[tuple[int, int]]) -> list[str]:
    """'from 28 to 30 October' claims every day in between; each of them must carry a warning in the source."""
    spans = []
    ms = _mentions(t)
    for (s1, e1, a), (s2, e2, b) in zip(ms, ms[1:]):
        if re.fullmatch(_SEP, t[e1:s2], re.I):
            spans.append((t[s1:e2], a, b))
    for m in _BARE_RANGE_NB.finditer(t):
        mo = _MONTHS[m.group(3).lower()]
        spans.append((m.group(0), (mo, int(m.group(1))), (mo, int(m.group(2)))))
    for m in _BARE_RANGE_EN.finditer(t):
        mo = _MONTHS[m.group(1).lower()]
        spans.append((m.group(0), (mo, int(m.group(2))), (mo, int(m.group(3)))))
    bad = []
    for text, a, b in spans:
        try:
            days = _between(a, b)
        except ValueError:
            days = [(0, 0)]
        if any(d not in warned for d in days):
            bad.append(text)
    return bad


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
        if not all(isinstance(e[k], str) for k in ("id", "municipality_id", "hazard")) \
                or isinstance(e["max_level"], bool) or not isinstance(e["max_level"], int):
            r.problems.append(f"entry #{n}: id, municipality_id and hazard must be strings, max_level an integer")
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
        iso, md = _allowed_dates(it)
        blob = _blob(it).lower()
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
            for bd in _date_problems(t, iso, md):
                r.problems.append(f"{eid}.{key}: date not valid for this warning: {bd!r}")
            warned = {(int(d["date"][5:7]), int(d["date"][8:10])) for d in it.days}
            for span in _range_problems(t, warned):
                r.problems.append(f"{eid}.{key}: period includes days without a warning: {span!r}")
            for m in foreign_links(t):
                r.problems.append(f"{eid}.{key}: link/address not allowed: {m!r}")
            for m in _RISKY.finditer(t):
                if m.group(0).lower() not in blob:
                    r.problems.append(f"{eid}.{key}: advice/reassurance wording not in source: {m.group(0)!r}")
            if _INJECTION.search(t):
                r.problems.append(f"{eid}.{key}: contains instruction-like text (possible prompt injection)")
            if _EMOJI.search(t) or "```" in t or "#" in t:
                r.problems.append(f"{eid}.{key}: contains emoji/markdown")
    for missing in sorted(set(src) - seen):
        r.problems.append(f"{missing}: missing from draft (incomplete)")
    return r


def official_flags(it: Item) -> list[str]:
    """Official text is shown verbatim, so first check it is not carrying links or instructions to readers."""
    flags = []
    for o in it.official:
        for key in ("main", "warning", "advice", "consequence", "level_meaning"):
            text = o.get(key) or ""
            flags += [f"{key}: link/address {m!r}" for m in foreign_links(text)]
            if _INJECTION.search(text):
                flags.append(f"{key}: instruction-like text")
    return flags


def check_rendered(text: str) -> list[str]:
    """Final-output gate: the published Markdown/HTML itself must not contain foreign links or instructions."""
    problems = [f"rendered output contains link/address {m!r}" for m in foreign_links(text)]
    if _INJECTION.search(text):
        problems.append("rendered output contains instruction-like text")
    return problems
