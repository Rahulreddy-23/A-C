## Milestone / task
<!-- e.g. M3 — trace rules engine. Link the BRIEF section. -->

## What & why

## Acceptance criteria (copy from BRIEF §15, tick each with evidence)
- [ ] 
- [ ] 

## How it was tested
<!-- test names, fixtures used -->

## Sample output
<!-- paste a short excerpt of a generated doc/report/CLI output -->

## Live verification for the repo owner
<!-- exact commands needing ADO or paid LLM access, and what result to expect; "none" if not applicable -->

## LLM cost
<!-- $ spent on paid API calls for this PR (should usually be $0 — tests use mock) -->

## Decisions & assumptions
<!-- ambiguities resolved, ADRs appended to docs/DECISIONS.md -->

## Rules checklist (AGENTS.md)
- [ ] No LLM-computed IDs/numbers/links (deterministic first)
- [ ] All LLM output typed, cited, validated
- [ ] No writes to source systems (docs repo PRs only; seeder isolated)
- [ ] Prompts/specs/rules live in `specs/`, not code
- [ ] Tests/CI make no paid API calls
- [ ] No secrets, no real company data, no external rendering services
