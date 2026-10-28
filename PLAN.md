# Battle plan — Innlandet Hazard Digest (KIUA-2003)

**Problem:** Natural-hazard warnings (flood, landslide) for Innlandet are published as machine-readable
data by NVE/Varsom but are not available in plain language, in English, or filtered to Innlandet's 46 municipalities.
**Workflow:** fetch official warnings -> normalise -> agent drafts plain-language NO+EN digest -> code verifies every
fact against the source -> human approves -> publish.
**Constraints met:** public data only (no personal data); official open API (no scraping); Innlandet municipalities only.

## Pipeline (stages)
| # | Stage | Kind | Runs unattended |
|---|-------|------|-----------------|
| 1 | `fetch`     | code (tools: network, files) | yes |
| 2 | `normalize` | code (filter county 34, level>=2, aggregate) | yes |
| 3 | `draft`     | LLM agent (headless, no tools, budget-capped) or deterministic template | yes |
| 4 | `validate`  | code: schema, exact-match of facts, completeness, anti-hallucination, injection scan | yes |
| 5 | `gate`      | human approval before anything is published | NO (by design) |

If stage 2 finds nothing to warn about, stage 3 is skipped (deterministic all-clear): saves cost, removes a failure mode.

## Compulsory 2 checklist (PDF section 2) — tick only when really done
### Report (3-4 pages, English, NeurIPS preprint template, `\usepackage[preprint]{neurips_2025}`, no checklist section)
- [ ] Problem description (need, who, what the workflow produces)
- [ ] Definition of success (checkable)
- [ ] Architecture (context the agent gets, stages/subagents, which parts run unattended)
- [ ] Schedule (milestones working backwards from the demo, weeks 46-47)
- [ ] Risk assessment (what fails + what we do)
- [ ] Repository link
- [ ] Appendix: prompt logs (max 2 pages)
- [ ] Appendix: meeting reports
### Walking skeleton
- [x] One path runs end to end: real input -> harness -> checkable output (live NVE run verified 2026-10-28)
- [x] README that lets anyone reproduce the run
- [x] Context files the harness uses are in the repo (`context/`)
- [ ] Push to a PUBLIC git repo and put the URL in the report (no git repo yet)
### Technical minimum (all four)
- [x] Input -> output whose correctness can be checked (validate.py)
- [x] More than one stage
- [x] Uses tools (network, files, shell/CLI)
- [x] At least one part runs automatically

## Constraints checklist (PDF section 1)
- [x] No personal data (only public hazard warnings + municipality names)
- [x] Official API, no scraping, no republishing of source material beyond short attributed quotes
- [x] Fits Innlandet (Norwegian source language, Innlandet municipalities, NO+EN output)

## Built in from day 1 for the exam (PDF section 3)
- Safe operation: tool-less agent, budget cap, secrets only via env, kill switch (`KILL` file + failure streak), human gate.
- Stress tests (pick 2): **input perturbation** (prompt injection in warning text) + **dependency failure** (API outage / bad data).
- Honest failure log: `logs/failures.md` — record every real failure and repair as we go (target >=3 failures, >=2 repairs).
- Meeting reports: `logs/meetings/` — need >=8 by the exam. Prompt logs: `logs/prompts.md`.

## Schedule (working backwards)
- Compulsory 2 deadline: **CONFIRM ON CANVAS** (not in the PDF)
- Weeks 46-47 (9-22 Nov 2026): live demo — rehearse one week before
- 3 Dec 2026 11:59: white paper via Wiseflow, repo tagged `exam`
- After C2: eval harness + test set -> stress tests + repairs -> safe-operation evidence -> white paper
