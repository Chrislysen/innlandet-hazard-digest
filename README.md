# Innlandet Hazard Digest

Agentic workflow (KIUA-2003, autumn 2026): turns official NVE/Varsom **flood and landslide warnings** for the 46
municipalities of Innlandet into a **plain-language Norwegian + English digest**, with the structured facts (levels, dates, municipalities, numbers, links) verified by code
before a human approves it. Public data only; no personal data.

## Pipeline
`fetch` (NVE API) -> `normalize` (county 34, level >= 2) -> `draft` (LLM agent, no tools, budget-capped; or deterministic template)
-> `validate` (code: exact-match fields, completeness, no unsupported numbers/dates/colours/links/advice words, injection scan, final-output gate) -> **human `approve`**.
Code cannot judge the meaning of free sentences, so a person reads the summary before publishing.
If nothing is at yellow level or above, the LLM is skipped and a deterministic all-clear is produced. The run fails instead of producing an all-clear unless every one of the 46 expected municipalities (`data/reference/`) has an assessed level for every expected day, for both hazards. An all-clear names the dates it covers.

## Requirements
- Python 3.11+ (standard library only)
- Optional: [Claude Code CLI](https://claude.com/claude-code) logged in, for `--backend claude`

## See it (browser)
```powershell
$env:PYTHONPATH = "src"; python -m hazard demo
```
Builds and opens `out/demo.html`: every stage on three scenarios, plus a panel where the validator catches six kinds of tampered drafts.

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

## Official content and attribution
The agent writes only a short summary. The complete official Norwegian warning text is appended unaltered to every entry; English is an unofficial summary and labelled so (NVE's own English can differ). Timestamps are kept as published.
`data/fixtures/historical_hamar_2023` inserts a **genuine archived** NVE warning (Hamar, orange flood, valid 2023-08-10; evidence and hashes in `data/evidence/`) into the 2026-10-28 all-green background; output is marked "ARCHIVED REPLAY". Every fixture has a `label.txt` shown in the output (real snapshot / historical replay / synthetic test data). Official text that contains a link or instruction-like text is withheld and flagged; publishing such a run needs `approve --allow-flagged`.
Data: "Varsler fra Flomvarslingen i Norge og www.varsom.no" / "Varsler fra Jordskredvarslingen i Norge og www.varsom.no". No NVE endorsement is implied.

## Context files used by the agent
`context/system_prompt.md` (rules, untrusted-data handling, output contract), `context/style_guide.md`, `context/glossary.md`.

## Safe operation (summary; details in white paper)
- **Permission scoping:** agent runs with `--tools "" --strict-mcp-config --setting-sources ""` (no tools/MCP/skills); only the harness touches files and network.
- **Secrets:** none in repo; the CLI uses the user's own login/env. `.env` is git-ignored.
- **Cost control:** one USD 0.25 limit per run: each attempt is passed only the remainder as the CLI's own budget limit (max 2 attempts). `log.json` records `cost_measured_usd` (reported by the CLI) separately from `cost_assumed_usd` (the granted remainder is assumed spent if a call fails without a report).
- **Human gate:** nothing is published until `approve`; `approve` refuses runs that failed validation and digests changed after validation (SHA-256 recorded in `log.json`).
- **Kill switch:** `KILL` file halts all runs; auto-engaged after 3 consecutive failed runs (`python -m hazard status`).

## Layout
`src/hazard/` code · `context/` agent context · `data/fixtures/` offline inputs · `tests/` · `logs/` failures, prompts, meeting reports · `PLAN.md` plan vs. assignment checklist

## Data and licence notes
Source: NVE Varsom API (https://api01.nve.no/hydrology/forecast/), open data under NLOD. Digest text links back to varsom.no and is advisory only.
