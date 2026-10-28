# What worked (reported alongside failures.md; facts only, with evidence)

- **Failure absorbed by design (F2):** when the first agent call crashed, the pipeline fell back to a deterministic template and still produced a validated digest, marked `degraded`.
- **Injection resisted (one pass):** on the injection fixture the agent ignored the embedded instructions; independent of that, the injected official text is withheld from the output and the run needs `--allow-flagged` to publish. Test: `FinalOutputTests`.
- **Final-output gate paid for itself (F8):** it caught a real bug in our own link tokenizer (it swallowed `</p`) before it shipped.
- **External evidence verified, not trusted:** the archived Hamar warning from the review pack was re-fetched from the live NVE API and was byte-identical (SHA-256 matched). Source: `data/evidence/`.
- **Cost:** agent runs cost USD 0.01-0.03 each on the real historical warning and the injection fixture (`log.json` `total_cost_usd`).
- **Reproducibility:** a fresh `git clone` passes 47 tests (48 with the opt-in live test) and runs the live, replay and demo paths with standard-library Python only.
- **Reviews led to fixes, not defence:** two external reviews produced F4-F10; each was checked against the code, fixed, and covered by tests.

## Limits we still carry
- The validator cannot judge the meaning of free sentences; a person reads the summary.
- Today's real feed is all green; non-green cases use one genuine historical warning plus labelled synthetic data.
- The evaluation harness and stress-test results are exam work and do not exist yet.
