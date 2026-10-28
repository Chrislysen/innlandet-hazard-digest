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

## F4 — design flaw: the model decided which official advice survived; long official text was truncated — 2026-10-28
- **What:** the digest contained only the agent's paraphrase, and source text was cut at 1200 chars. NVE asks that complete warning information be retained.
- **Noticed:** external review of the project (second assistant), checked by us against the assignment and the API.
- **Repair:** `normalize` keeps the complete official fields verbatim (`Item.official`); `render` appends them unaltered under each entry. Test `test_complete_official_text_is_kept_unaltered` fails if any official sentence is dropped.

## F5 — English text looked official — 2026-10-28
- **What:** the English was agent-written but unlabelled. On a real warning the official NO and EN versions differ materially, so English cannot be treated as a translation of the official text.
- **Repair:** every English summary is labelled "Unofficial English summary; NVE's own English text can differ."

## F6 — missing or unassessed data could become "no warnings" — 2026-10-28 (second external review)
- **What:** the guard only counted municipality rows. Removed warning lists, level 0, invalid levels or stale data still gave a successful countywide all-clear.
- **Repair:** coverage check (>= 40 municipalities per hazard with an assessed level 1-4) and, in live mode, a freshness check (a warning must cover today). Tests: `MissingDataIsNotAllClearTests`.

## F7 — validator gaps: look-alike links, invented dates, invented advice/reassurance — 2026-10-28
- **What:** `https://varsom.no.evil-example.com` passed (substring match); an invalid date, evacuation advice and "the town is safe" passed. The claim "every fact is verified by code" was untrue.
- **Repair:** links judged by parsed hostname; dates checked against the warning's valid dates; advice/reassurance keywords rejected unless present in the source. Report and README now say what code can and cannot verify and that a person reads the sentences. Tests: `ValidatorGapsTests`.
- **Known limit:** meaning of free sentences is not machine-verified (candidate for LLM-as-judge plus human review in the exam evaluation).

## F8 — HTML output lacked the Markdown corrections; injected official text reached final output — 2026-10-28
- **What:** HTML had no replay banner, official text or unofficial-English label; synthetic data was not labelled; the injection text was appended verbatim to the final output after draft validation.
- **Repair:** one label per fixture shown in both formats; official text containing a foreign link or instruction-like text is withheld and flagged (publication needs `--allow-flagged`); a final-output gate re-checks both formats. The gate itself caught a bug in my link tokenizer (it swallowed `</p`). Tests: `FinalOutputTests`.

## F9 — the USD 0.25 budget applied per attempt, not per run — 2026-10-28
- **What:** two attempts each got a fresh allowance (mocked 0.24 + 0.24 completed normally).
- **Repair:** one shared run budget; each attempt gets only the remainder; no attempt starts below USD 0.02. Test: `test_budget_is_shared_across_attempts`.

## F10 — documented context did not match what ran — 2026-10-28
- **What:** only `system_prompt.md` was loaded; glossary and style guide were unused; complete official text entered the prompt despite the stated 1200-character cap.
- **Repair:** `load_context()` concatenates all three files; the model gets `Item.to_model_dict()` (capped texts only), the complete text stays outside the prompt. Tests: `test_all_context_files_are_loaded`, `test_model_input_excludes_complete_official_text`.

## Candidates still to induce for the exam (section 3.3)
- Input perturbation: `data/fixtures/synthetic_injection` (done for template + claude, one pass). Needs a proper eval harness + more variants.
- Dependency failure: API outage / malformed payload / silent all-green degradation.
