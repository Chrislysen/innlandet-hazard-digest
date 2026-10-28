# Innlandet Hazard Digest

Agentic workflow (KIUA-2003, autumn 2026): turns official NVE/Varsom **flood and landslide warnings** for the 46
municipalities of Innlandet into a **plain-language Norwegian + English digest**, with every fact verified by code
before a human approves it. Public data only; no personal data.

## Pipeline
`fetch` (NVE API) -> `normalize` (county 34, level >= 2) -> `draft` (LLM agent, no tools, budget-capped; or deterministic template)
-> `validate` (code: exact-match facts, completeness, no invented numbers/links, injection scan) -> **human `approve`**.
If nothing is at yellow level or above, the LLM is skipped and a deterministic all-clear is produced.

## Requirements
- Python 3.11+ (standard library only)
- Optional: [Claude Code CLI](https://claude.com/claude-code) logged in, for `--backend claude`

## Reproduce a run (PowerShell, from repo root)
```powershell
$env:PYTHONPATH = "src"

# 1. Offline, deterministic (no network, no API cost)
python -m hazard run --source-dir data/fixtures/synthetic_orange
# 2. Live data from NVE
python -m hazard run
# 3. With the LLM agent (cost capped at $0.25/run, typically ~$0.02)
python -m hazard run --backend claude --source-dir data/fixtures/synthetic_injection
# 4. Human gate: review out/run_*/digest.md, then
python -m hazard approve out/run_YYYYMMDD_HHMMSS_xxxxxx
# 5. Tests
python -m unittest discover -s tests -v
# 6. Also verify the agent really has no tools (costs a few cents)
$env:RUN_LIVE_TESTS = "1"; python -m unittest discover -s tests -v
```
Each run writes `out/run_*/{items.json, digest.md, digest.html, log.json}` (open `digest.html` in a browser) (log has attempts, validator problems, cost, degradation).
Today's real data may be all-green (a valid "all clear" run); `data/fixtures/synthetic_*` contain **synthetic** warnings
injected by `scripts/make_fixtures.py` for testing — they are not real warnings.

## Context files used by the agent
`context/system_prompt.md` (rules, untrusted-data handling, output contract), `context/style_guide.md`, `context/glossary.md`.

## Safe operation (summary; details in white paper)
- **Permission scoping:** agent runs with `--tools "" --strict-mcp-config --setting-sources ""` (no tools/MCP/skills); only the harness touches files and network.
- **Secrets:** none in repo; the CLI uses the user's own login/env. `.env` is git-ignored.
- **Cost control:** `--max-budget-usd 0.25` per draft call; max 2 attempts per run.
- **Human gate:** nothing is published until `approve`; `approve` refuses runs that failed validation.
- **Kill switch:** `KILL` file halts all runs; auto-engaged after 3 consecutive failed runs (`python -m hazard status`).

## Layout
`src/hazard/` code · `context/` agent context · `data/fixtures/` offline inputs · `tests/` · `logs/` failures, prompts, meeting reports · `PLAN.md` plan vs. assignment checklist

## Data and licence notes
Source: NVE Varsom API (https://api01.nve.no/hydrology/forecast/), open data under NLOD. Digest text links back to varsom.no and is advisory only.
