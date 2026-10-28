# Individual working session 2026-10-28 (not a team meeting)

**Goal:** choose a problem, check data sources, build the walking skeleton, align the plan with the assignment PDF.

## What happened
- Read the assignment: two deliverables (Compulsory 2 plan + walking skeleton; final exam with evaluation harness, safe operation, stress testing).
- Short probe of municipal and county websites: no feed or API found. This is not proof that none exists.
- NVE Varsom and MET APIs answered live, no key, open.
- Chose a flood and landslide warning digest for Innlandet. Built fetch, normalize, draft, validate, human gate.
- External reviews found further problems; we checked each against the code and API. See `../failures.md` F4-F10.

## Decisions
1. Scope: Varsom flood + landslide, county 34, level >= 2. Weather and avalanche deferred.
2. Standard-library Python so anyone can reproduce.
3. Stress tests planned for the exam: input perturbation and dependency failure.
