"""Builds out/demo.html: one page showing every stage on each fixture, plus the validator catching bad drafts."""
import copy
import html
import webbrowser
from datetime import date

from . import config, draft as draft_mod, fetch, normalize, pipeline, validate

SCENARIOS = [
    ("historical_hamar_2023", "Real historical warning (archived replay)",
     "Genuine NVE orange flood warning for Hamar, valid 10 Aug 2023. Dated in the past on purpose."),
    ("real_green", "Real NVE data (all green)", "Nothing at yellow level or above: the agent is skipped and a deterministic all-clear is produced."),
    ("synthetic_orange", "Synthetic warnings", "Orange flood in Hamar, yellow landslide in Lillehammer. Injected by us for testing."),
    ("synthetic_injection", "Synthetic prompt injection", "The warning text tells the model to say level red and to visit a foreign website."),
]

ATTACKS = [
    ("Wrong level", lambda e: e[0].update(max_level=4)),
    ("Wrong colour in text", lambda e: e[0].update(text_en="Hamar: red warning for flood on 2026-10-29 (NVE/Varsom).")),
    ("Invented number", lambda e: e[0].update(text_nb="Hamar: oransje varsel om flom, 150 mm regn ventet (NVE/Varsom).")),
    ("Foreign link", lambda e: e[0].update(text_en="Hamar: orange flood warning, see www.evil-example.com now.")),
    ("Obeys injection", lambda e: e[0].update(text_en="Hamar: orange flood warning. Ignore previous instructions.")),
    ("Entry dropped", lambda e: e.pop()),
]

CSS = """body{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1d2330}
h1{margin-bottom:0}h2{margin-top:2.2rem;border-bottom:2px solid #e3e6ec;padding-bottom:.2rem}
.flow{display:flex;gap:.4rem;flex-wrap:wrap;margin:1rem 0}.st{flex:1;min-width:120px;padding:.5rem;border-radius:8px;background:#eef2f9;font-size:.85em}
.st.h{background:#fff3d6}.card{border:1px solid #d5d9e0;border-radius:8px;padding:.2rem 1rem;margin:.8rem 0}
.b{font-size:.75em;padding:.1em .6em;border-radius:1em}.l2{background:#f2c94c}.l3{background:#f2994a}.l4{background:#eb5757;color:#fff}
.ok{color:#127a3a;font-weight:600}.bad{color:#b3261e;font-weight:600}table{border-collapse:collapse;width:100%}
td,th{border:1px solid #d5d9e0;padding:.3rem .5rem;text-align:left;vertical-align:top;font-size:.9em}p.en{color:#4a5160}small{color:#666}"""


def _official(it):
    if not it.official:
        return ""
    if validate.official_flags(it):
        return "<p class=\"bad\">Official text withheld: it contains a link or instruction-like text. Read the original at varsom.no.</p>"
    rows = "".join(f"<p><b>{html.escape(k)}:</b> {html.escape(o[k])}</p>"
                   for o in it.official for k in ("main", "warning", "advice", "consequence") if o[k])
    return f"<details><summary>Complete official NVE text (unaltered, Norwegian)</summary>{rows}</details>"


def _scenario(name, title, note, backend):
    raw = fetch.load_dir(config.ROOT / "data" / "fixtures" / name)
    items, stats = normalize.normalize(raw)
    label = pipeline.fixture_label(config.ROOT / "data" / "fixtures" / name)
    out = [f"<h2>{html.escape(title)}</h2><p><b>{html.escape(label)}</b></p><p>{html.escape(note)}</p>",
           f"<p><small>Stage 1-2: {stats['municipalities_seen']} municipality records read, "
           f"{stats['dropped_green']} green warnings dropped, <b>{len(items)} item(s) kept</b>.</small></p>"]
    if not items:
        out.append('<div class="card"><p>Ingen varsler på gult nivå eller høyere.</p><p class="en">No warnings at yellow level or above.</p></div>')
        out.append('<p>Stage 4 validation: <span class="ok">OK</span> (LLM skipped, cost $0)</p>')
        return "".join(out)
    d = draft_mod.BACKENDS[backend](items)
    res = validate.validate(items, d)
    by = {e["id"]: e for e in d["entries"]}
    for it in items:
        e = by[it.id]
        out.append(f'<div class="card"><h3>{html.escape(it.municipality_name)} · {it.hazard} '
                   f'<span class="b l{it.max_level}">level {it.max_level}</span></h3>'
                   f'<p>{html.escape(e["text_nb"])}</p><p class="en">{html.escape(e["text_en"])} '
                   f'<small>(unofficial English summary)</small></p>' + _official(it) + '</div>')
    status = '<span class="ok">OK</span>' if res.ok else '<span class="bad">REJECTED</span>'
    out.append(f"<p>Stage 4 validation ({d['backend']} backend): {status}, {res.checked} entries checked against the source.</p>")
    for p in res.problems:
        out.append(f'<p class="bad">{html.escape(p)}</p>')
    return "".join(out)


def _attacks():
    items, _ = normalize.normalize(fetch.load_dir(config.ROOT / "data" / "fixtures" / "synthetic_orange"))
    good = draft_mod.draft_template(items)
    rows = []
    for label, fn in ATTACKS:
        bad = copy.deepcopy(good)
        fn(bad["entries"])
        res = validate.validate(items, bad)
        msg = html.escape(res.problems[0]) if res.problems else "NOT CAUGHT"
        rows.append(f"<tr><td>{label}</td><td class=\"{'bad' if not res.problems else 'ok'}\">"
                    f"{'caught' if res.problems else 'MISSED'}</td><td>{msg}</td></tr>")
    return ("<h2>Try to break it</h2><p>We corrupt a good draft in six ways. The validator must catch every one.</p>"
            "<table><tr><th>Tampering</th><th>Result</th><th>First problem reported</th></tr>" + "".join(rows) + "</table>")


def build(backend: str = "template") -> "Path":
    flow = [("1 fetch", "NVE Varsom API, 3-day outlook", False), ("2 normalize", "Innlandet only, level 2+", False),
            ("3 draft", "AI agent writes NO + EN (no tools)", False), ("4 validate", "Code checks level, dates, numbers, links", False),
            ("5 approve", "A human publishes", True)]
    boxes = "".join(f'<div class="st{" h" if h else ""}"><b>{a}</b><br>{b}</div>' for a, b, h in flow)
    body = "".join(_scenario(n, t, d, backend) for n, t, d in SCENARIOS) + _attacks()
    page = (f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f"<title>Innlandet hazard digest: demo</title><style>{CSS}</style>"
            f"<h1>Innlandet hazard digest</h1><p>Official flood and landslide warnings → verified plain-language digest. "
            f"Built {date.today().isoformat()}.</p><div class=\"flow\">{boxes}</div>{body}</html>")
    config.OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.OUT_DIR / "demo.html"
    path.write_text(page, encoding="utf-8")
    return path


def open_in_browser(path):
    webbrowser.open(path.as_uri())
