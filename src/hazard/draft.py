"""Stage 3: draft plain-language NO+EN text. Two interchangeable backends.

template : deterministic, offline, free. Baseline + fallback.
claude   : headless Claude Code CLI, NO tools, hard budget cap, structured JSON output.
"""
import json
import subprocess
from datetime import date

from . import config
from .normalize import Item

SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "municipality_id": {"type": "string"},
                    "hazard": {"type": "string", "enum": ["flood", "landslide"]},
                    "max_level": {"type": "integer", "minimum": 2, "maximum": 4},
                    "text_nb": {"type": "string"},
                    "text_en": {"type": "string"},
                },
                "required": ["id", "municipality_id", "hazard", "max_level", "text_nb", "text_en"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["entries"],
    "additionalProperties": False,
}


# permission scoping: no built-in tools, no MCP servers, no skills/settings, no session state
LOCKDOWN_FLAGS = ["--tools", "", "--strict-mcp-config", "--setting-sources", "",
                  "--disable-slash-commands", "--no-session-persistence"]


def verify_lockdown() -> dict:
    """Ask the CLI what the agent can actually use. Must report no tools, MCP servers or skills."""
    cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", *LOCKDOWN_FLAGS,
           "--max-budget-usd", "0.05", "--system-prompt", "Reply with one word."]
    proc = subprocess.run(cmd, input="hi", capture_output=True, text=True, encoding="utf-8", timeout=120)
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            return {"tools": ev.get("tools"), "mcp_servers": ev.get("mcp_servers"), "skills": ev.get("skills")}
    raise RuntimeError("no init event from claude CLI")


def date_runs(days) -> list[tuple[str, str]]:
    """Consecutive ISO dates grouped into (first, last) runs. A gap is never bridged."""
    runs = []
    for d in sorted(set(days)):
        if runs and (date.fromisoformat(d) - date.fromisoformat(runs[-1][1])).days == 1:
            runs[-1] = (runs[-1][0], d)
        else:
            runs.append((d, d))
    return runs


def _join(parts: list[str], word: str) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + f" {word} " + parts[-1]


def _periods(it: Item) -> tuple[str, str]:
    runs = date_runs(d["date"] for d in it.days)
    nb = _join([f"den {a}" if a == b else f"fra {a} til {b}" for a, b in runs], "og")
    en = _join([f"on {a}" if a == b else f"from {a} to {b}" for a, b in runs], "and")
    return nb, en


def draft_template(items: list[Item], feedback: str | None = None, budget: float | None = None) -> dict:
    entries = []
    for it in items:
        nb_c, en_c = config.LEVEL_COLORS[it.max_level]
        nb_h, en_h = config.HAZARD_NAMES[it.hazard]
        span_nb, span_en = _periods(it)
        entries.append({
            "id": it.id, "municipality_id": it.municipality_id, "hazard": it.hazard, "max_level": it.max_level,
            "text_nb": f"{it.municipality_name}: {nb_c} varsel om {nb_h} {span_nb} (NVE/Varsom).",
            "text_en": f"{it.municipality_name}: {en_c} warning for {en_h} {span_en} (NVE/Varsom).",
        })
    return {"entries": entries, "backend": "template", "cost_usd": 0.0}


def load_context() -> str:
    """All context files the agent is meant to receive, in a fixed order."""
    parts = []
    for name, title in ("system_prompt.md", "RULES"), ("style_guide.md", "STYLE GUIDE"), ("glossary.md", "GLOSSARY"):
        text = (config.CONTEXT_DIR / name).read_text(encoding="utf-8").strip()
        parts.append(f"## {title}\n{text}")
    return "\n\n".join(parts)


def draft_claude(items: list[Item], feedback: str | None = None, budget: float | None = None) -> dict:
    system = load_context()
    payload = json.dumps([i.to_model_dict() for i in items], ensure_ascii=False, indent=1)
    prompt = f"<items>\n{payload}\n</items>"
    if feedback:
        prompt += f"\n\nYour previous draft failed automatic checks. Fix exactly these problems:\n{feedback}"
    cmd = [
        "claude", "-p", "--output-format", "json", *LOCKDOWN_FLAGS,
        "--max-budget-usd", str(round(budget if budget is not None else config.MAX_BUDGET_USD, 4)),  # cost control
        "--system-prompt", system, "--json-schema", json.dumps(SCHEMA),
    ]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=300)
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out:
        raise RuntimeError(f"claude CLI failed ({proc.returncode}): {(proc.stderr or out).strip()[:500]}")
    env = json.loads(out)
    if isinstance(env, list):  # some CLI versions emit an event array
        env = next(x for x in env if x.get("type") == "result")
    if env.get("is_error"):
        raise RuntimeError(f"claude returned an error: {str(env.get('result'))[:300]}")
    data = env.get("structured_output")
    if data is None:
        data = json.loads(env["result"])
    return {"entries": data["entries"], "backend": "claude", "cost_usd": float(env.get("total_cost_usd", 0.0))}


BACKENDS = {"template": draft_template, "claude": draft_claude}
