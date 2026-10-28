"""Orchestrates the stages, enforces the kill switch, writes an auditable run directory."""
import hashlib
import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config, fetch, normalize, draft as draft_mod, validate as validate_mod

FOOTER_NB = "Kilde: NVE/Varsom, {src}. Varselet er veiledende. Ved fare for liv og helse, ring 110/112."
FOOTER_EN = "Source: NVE/Varsom, {src}. Advisory only. In an emergency call 110/112."
UNOFFICIAL_EN = "(Unofficial English summary; NVE's own English text can differ.)"
REVIEW_NOTE = "Summary text is machine-written and checked only for listed facts; a person must read it before publication."
OFFICIAL_LABELS = (("Warning", "main"), ("Situation", "warning"), ("Advice", "advice"),
                   ("Consequences", "consequence"), ("Level meaning", "level_meaning"))
WITHHELD = ("Official text withheld: it contains a link or instruction-like text that this harness does not "
            "reproduce. Read the original at https://www.varsom.no/flom-og-jordskred/ .")


class Halted(RuntimeError):
    pass


class DataQualityError(RuntimeError):
    pass


def baseline_days(stats: dict, expected: dict) -> list[str]:
    """Replay mode: days present for (nearly) every expected municipality and hazard. Days carried by only a few
    records (e.g. one archived warning) are not part of the baseline."""
    pairs = [(h, mid) for h, cov in stats["coverage"].items() for mid in expected if mid in cov]
    count: dict[str, int] = {}
    for h, mid in pairs:
        for d in stats["coverage"][h][mid]:
            count[d] = count.get(d, 0) + 1
    need = 0.9 * len(expected) * len(stats["coverage"])
    return sorted(d for d, n in count.items() if n >= need)


def check_data_quality(stats: dict, today: date | None = None) -> list[str]:
    """Incomplete, unassessed or stale warning data must never be reported as 'all clear'.

    Requires, for EVERY hazard, every expected Innlandet municipality id and an assessed warning level (1-4) for each
    expected day. Live mode: today and the next DAYS_AHEAD days. Replay mode (today=None): the baseline days of the
    snapshot. Returns the covered days so the digest can state exactly what it covers.
    """
    expected = config.expected_municipalities()
    if today is not None:
        days = [(today + timedelta(days=k)).isoformat() for k in range(config.DAYS_AHEAD + 1)]
    else:
        days = baseline_days(stats, expected)
    problems = []
    if not days:
        problems.append("no forecast day is covered for all municipalities")
    for hazard, cov in stats["coverage"].items():
        missing = sorted(set(expected) - set(cov))
        if missing:
            names = ", ".join(f"{expected[m]} ({m})" for m in missing[:5])
            problems.append(f"{hazard}: {len(missing)} expected municipalities missing from the feed: {names}")
        gaps = {mid: [d for d in days if d not in cov[mid]] for mid in expected if mid in cov}
        gaps = {mid: g for mid, g in gaps.items() if g}
        if gaps:
            first = next(iter(gaps))
            problems.append(f"{hazard}: {len(gaps)} municipalities lack an assessed warning level for "
                            f"{sorted({d for g in gaps.values() for d in g})} (e.g. {expected[first]})")
    if problems:
        raise DataQualityError("; ".join(problems) + " (incomplete data is not 'all clear')")
    return days


def _streak() -> int:
    try:
        return int(config.FAILURE_STREAK_FILE.read_text())
    except (OSError, ValueError):
        return 0


def _set_streak(n: int):
    config.OUT_DIR.mkdir(parents=True, exist_ok=True)
    config.FAILURE_STREAK_FILE.write_text(str(n))


def check_kill_switch():
    if config.KILL_FILE.exists():
        raise Halted(f"kill switch engaged ({config.KILL_FILE.name} exists). Fix the cause, then delete it.")


def fixture_label(source_dir: Path | None) -> str | None:
    if source_dir is None:
        return None
    f = Path(source_dir) / "label.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else "OFFLINE INPUT (not live data)."


def facts_line(it) -> str:
    nb, en = config.LEVEL_COLORS[it.max_level]
    hz_nb, hz_en = config.HAZARD_NAMES[it.hazard]
    dates = ", ".join(sorted({d["date"] for d in it.days}))
    return f"Nivå {it.max_level} ({nb}) / level {it.max_level} ({en}) · {hz_nb} / {hz_en} · gyldig / valid {dates}"


def _is_replay(items, today: date) -> bool:
    return bool(items) and all(d["date"] < today.isoformat() for i in items for d in i.days)


def _span(days):
    """'2026-10-28 – 2026-10-30' only for consecutive days; gaps are listed separately, never bridged."""
    return ", ".join(a if a == b else f"{a} – {b}" for a, b in draft_mod.date_runs(days))


def render(items, draft: dict, today: date, label: str | None = None, flags: dict | None = None,
           covered_days: list[str] | None = None) -> str:
    flags = flags or {}
    span = _span(covered_days) if covered_days else "the covered period"
    L = [f"# Innlandet hazard digest — {today.isoformat()}", ""]
    if label:
        L += [f"> **{label}**", ""]
    if _is_replay(items, today):
        L += ["> **ARCHIVED REPLAY:** every warning below is dated before today. This is not a current warning.", ""]
    if not items:
        L += [f"Ingen flom- eller jordskredvarsler på gult nivå eller høyere i Innlandet for {span}.",
              f"No flood or landslide warnings at yellow level or above in Innlandet for {span}.", ""]
    else:
        by_id = {e["id"]: e for e in draft["entries"]}
        for it in items:
            e = by_id[it.id]
            L += [f"## {it.municipality_name} — {it.hazard} (level {it.max_level})",
                  f"**Facts from source data:** {facts_line(it)}", "",
                  e["text_nb"], "", f"{e['text_en']} {UNOFFICIAL_EN}", ""]
            if flags.get(it.id):
                L += [f"**{WITHHELD}**", ""]
                continue
            for o in it.official:
                L += [f"**Official NVE text (Norwegian, complete, unaltered)** — valid {', '.join(o['dates'])}:"]
                for label_, key in OFFICIAL_LABELS:
                    if o[key]:
                        L += [f"- *{label_}:* {o[key]}"]
                L += [""]
    L += ["---", REVIEW_NOTE, FOOTER_NB.format(src=config.SOURCE_URL), FOOTER_EN.format(src=config.SOURCE_URL),
          *sorted({config.ATTRIBUTION[i.hazard] for i in items}),
          f"Generated by backend: {draft.get('backend', 'none')}. Status: PENDING HUMAN APPROVAL."]
    return "\n".join(L) + "\n"


_BADGE = {2: ("#f2c94c", "#000"), 3: ("#f2994a", "#000"), 4: ("#eb5757", "#fff")}


def render_html(items, draft: dict, today: date, label: str | None = None, flags: dict | None = None,
                covered_days: list[str] | None = None) -> str:
    flags = flags or {}
    esc = html.escape
    span = _span(covered_days) if covered_days else "the covered period"
    banners = []
    if label:
        banners.append(f'<p class="warn"><b>{esc(label)}</b></p>')
    if _is_replay(items, today):
        banners.append('<p class="warn"><b>ARCHIVED REPLAY:</b> every warning below is dated before today. '
                       "This is not a current warning.</p>")
    cards = []
    by_id = {e["id"]: e for e in draft["entries"]}
    for it in items:
        e = by_id[it.id]
        bg, fg = _BADGE[it.max_level]
        if flags.get(it.id):
            official = f'<p class="warn"><b>{esc(WITHHELD)}</b></p>'
        else:
            rows = "".join(f"<p><b>{esc(k_)}:</b> {esc(o[k])}</p>" for o in it.official
                           for k_, k in OFFICIAL_LABELS if o[k])
            official = (f"<details><summary>Official NVE text (Norwegian, complete, unaltered)</summary>{rows}"
                        "</details>") if rows else ""
        cards.append(
            f'<section><h2>{esc(it.municipality_name)} <span class="b" style="background:{bg};color:{fg}">'
            f'{esc(it.hazard)} · level {it.max_level}</span></h2>'
            f"<p><small><b>Facts from source data:</b> {esc(facts_line(it))}</small></p>"
            f'<p lang="nb">{esc(e["text_nb"])}</p>'
            f'<p lang="en">{esc(e["text_en"])} <small>{esc(UNOFFICIAL_EN)}</small></p>{official}</section>')
    body = "".join(cards) or (f"<p>Ingen flom- eller jordskredvarsler på gult nivå eller høyere i Innlandet for {esc(span)}.</p>"
                              f"<p>No flood or landslide warnings at yellow level or above in Innlandet for {esc(span)}.</p>")
    attribution = "<br>".join(esc(a) for a in sorted({config.ATTRIBUTION[i.hazard] for i in items}))
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Innlandet hazard digest {today.isoformat()}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem}}
section{{border:1px solid #ccc;border-radius:8px;padding:.5rem 1rem;margin:1rem 0}}
.b{{font-size:.7em;padding:.15em .6em;border-radius:1em;vertical-align:middle}}
.warn{{background:#fff3d6;padding:.4rem .8rem;border-radius:6px}}
p[lang=en]{{color:#444}}footer{{color:#666;font-size:.85em}}</style>
<h1>Innlandet hazard digest — {today.isoformat()}</h1>{"".join(banners)}{body}
<footer><p>{esc(REVIEW_NOTE)}</p><p>{esc(FOOTER_NB.format(src=config.SOURCE_URL))}<br>{esc(FOOTER_EN.format(src=config.SOURCE_URL))}
<br>{attribution}</p>
<p>Backend: {esc(str(draft.get("backend")))}. Status: pending human approval.</p></footer></html>"""


def run(backend: str = "template", source_dir: Path | None = None, today: date | None = None) -> Path:
    check_kill_switch()
    live = source_dir is None
    today = today or date.today()
    run_dir = config.OUT_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log = {"started": datetime.now().isoformat(timespec="seconds"), "backend_requested": backend,
           "mode": "live" if live else "replay", "attempts": [], "total_cost_usd": 0.0}
    try:
        raw = fetch.fetch_all(today) if live else fetch.load_dir(source_dir)             # stage 1
        items, stats = normalize.normalize(raw)                                          # stage 2
        log["stats"] = stats
        days = check_data_quality(stats, today if live else None)
        log["covered_days"] = days
        flags = {i.id: f for i in items if (f := validate_mod.official_flags(i))}
        log["flags"] = flags
        (run_dir / "items.json").write_text(
            json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=1), "utf-8")
        if not items:                                                                    # nothing to say: skip the LLM
            draft = {"entries": [], "backend": "none (all clear)", "cost_usd": 0.0}
            result = validate_mod.validate(items, draft)
        else:
            draft, result = None, None
            feedback, measured, assumed = None, 0.0, 0.0
            for attempt in range(1, config.MAX_DRAFT_ATTEMPTS + 1):                      # stage 3 + 4 with one repair
                remaining = round(config.MAX_BUDGET_USD - measured - assumed, 4)
                if backend != "template" and remaining < config.MIN_ATTEMPT_BUDGET_USD:
                    log["attempts"].append({"n": attempt, "backend": backend, "skipped": "run budget exhausted"})
                    break
                try:
                    cand = draft_mod.BACKENDS[backend](items, feedback, remaining)
                except Exception as e:  # agent/CLI failure: assume the whole remaining budget may be gone
                    log["attempts"].append({"n": attempt, "backend": backend, "error": str(e)[:300]})
                    assumed += remaining  # no cost report: treat what we granted as spent
                    break
                measured += cand.get("cost_usd", 0.0)
                res = validate_mod.validate(items, cand)
                log["attempts"].append({"n": attempt, "backend": backend, "ok": res.ok,
                                        "problems": res.problems, "cost_usd": cand.get("cost_usd", 0)})
                if res.ok:
                    draft, result = cand, res
                    break
                feedback = res.feedback()
            log.update(cost_measured_usd=round(measured, 4), cost_assumed_usd=round(assumed, 4),
                       total_cost_usd=round(measured + assumed, 4))
            if draft is None and backend != "template":                                  # graceful degradation
                cand = draft_mod.draft_template(items)
                res = validate_mod.validate(items, cand)
                log["attempts"].append({"n": "fallback", "backend": "template", "ok": res.ok, "problems": res.problems})
                log["degraded"] = True
                if res.ok:
                    draft, result = cand, res
            if draft is None:
                raise RuntimeError("no valid draft produced (see log.json)")
        label = fixture_label(source_dir)
        md = render(items, draft, today, label, flags, days)
        page = render_html(items, draft, today, label, flags, days)
        final_problems = validate_mod.check_rendered(md) + validate_mod.check_rendered(page)
        if final_problems:
            raise RuntimeError("final output failed the output gate: " + "; ".join(final_problems[:3]))
        (run_dir / "digest.md").write_text(md, "utf-8")
        (run_dir / "digest.html").write_text(page, "utf-8")
        log["digest_sha256"] = {n: _sha256(run_dir / n) for n in ("digest.md", "digest.html")}
        log.update(ok=result.ok, validated_entries=result.checked, status="pending_approval")
        _set_streak(0)
        return run_dir
    except Exception as e:
        log.update(ok=False, error=str(e)[:500], status="failed")
        n = _streak() + 1
        _set_streak(n)
        if n >= config.MAX_CONSECUTIVE_FAILURES:
            config.KILL_FILE.write_text(f"auto-engaged after {n} consecutive failed runs: {e}\n", encoding="utf-8")
        raise
    finally:
        (run_dir / "log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), "utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def approve(run_dir: Path, allow_flagged: bool = False) -> Path:
    log = json.loads((run_dir / "log.json").read_text("utf-8"))
    if not log.get("ok") or log.get("status") != "pending_approval":
        raise Halted("run is not approvable (failed validation or already handled)")
    if log.get("flags") and not allow_flagged:
        raise Halted(f"run has flagged official text for {sorted(log['flags'])}; read the source, then use --allow-flagged")
    recorded = log.get("digest_sha256") or {}
    for name in ("digest.md", "digest.html"):
        if recorded.get(name) != _sha256(run_dir / name):
            raise Halted(f"{name} differs from the version that passed validation; re-run the pipeline instead of editing")
    pub = config.OUT_DIR / "published"
    pub.mkdir(parents=True, exist_ok=True)
    target = pub / f"{run_dir.name}.md"
    text = (run_dir / "digest.md").read_text("utf-8").replace("PENDING HUMAN APPROVAL", "APPROVED BY HUMAN")
    target.write_text(text, "utf-8")
    log["status"] = "approved"
    log["approved_at"] = datetime.now().isoformat(timespec="seconds")
    (run_dir / "log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), "utf-8")
    return target
