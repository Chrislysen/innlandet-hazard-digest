# Failure log (honest reporting — PDF 3.3: >=3 real failures and >=2 successful repairs score higher)

Format: what failed -> how we noticed -> why (propagation) -> repair -> evidence it holds.

## F1 — "tool-less" agent was not tool-less (permission scoping) — 2026-10-28
- **What:** `claude -p --tools ""` still exposed MCP tools (Google Drive share/trash, Docs) to the drafting agent.
- **Noticed:** debugging an unrelated CLI failure; init event listed the tools.
- **Why it matters:** an injected instruction in warning text could have reached tools with write access.
- **Repair:** added `--strict-mcp-config --setting-sources "" --disable-slash-commands`. Verified via stream-json init event: `tools: [] mcp: [] skills: []`.
- **Status:** repaired. `draft.verify_lockdown()` + `AgentLockdownTests` assert the init event lists zero tools, MCP servers and skills (run with `RUN_LIVE_TESTS=1`).

## F2 — agent stage crashed on first real call; pipeline degraded gracefully — 2026-10-28
- **What:** first `--backend claude` run exited 1 with empty stderr (the cause was the tool/MCP flags + output-format handling).
- **Effect:** pipeline fell back to the deterministic template, marked `degraded: true`, output still validated.
- **Repair:** fixed CLI flags; parser now handles both dict and event-array JSON output and surfaces `is_error`.
- **Status:** repaired; the fallback path itself worked as designed (absorbed failure).

## F3 — terminal/curl corrupted Norwegian characters (æøå) — 2026-10-28
- **What:** payloads saved with curl in Git Bash showed `Gr�nt niv�`; the API actually returns correct UTF-8.
- **Repair:** all fetching via Python `urllib` + explicit UTF-8; fixtures regenerated.
- **Status:** repaired.

## Candidates still to induce for the exam (section 3.3)
- Input perturbation: `data/fixtures/synthetic_injection` (done for template + claude, one pass). Needs a proper eval harness + more variants.
- Dependency failure: API outage / malformed payload / silent all-green degradation.
