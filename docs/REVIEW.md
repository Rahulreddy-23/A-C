# Review Log

Written by Claude (PM and reviewer). Codex reads this file at the start of every milestone.

**Item format:** `R-NNN [blocking|non-blocking] M<N> — finding (file:line) — expected fix`

**Codex:**
- Fix every `[blocking]` item before starting new work.
- Append `Resolved in <sha>: <note>` under each item you fix.
- Don't edit or delete the reviewer's text.
- If you disagree with an item, write your reasoning under it.

## Open

**R-012 [non-blocking, revisit in M7] M1 — Expected impacted sections in `change_1` are guesses** (`data/synthetic/scenarios/change_1.yaml`)
- For example, SAD `interfaces` and `architecture` are listed for a threshold change in one unit.
- In M7, derive the expected list from the impact rule (sections whose cited revisions include a changed artifact, plus labelled 1-hop "possibly affected"). Annotate each expected section with the artifact that makes it stale, so the impact precision/recall metric is honest.

**R-013 [non-blocking, by M10] M2 — Test-case steps are one template repeated across all cases** (`data/synthetic/evidence.yaml`, test_case entries)
- Every case has the same four generic steps ("exercise … with nominal input; challenge its boundary; repeat with invalid input"), and titles end in "— case 0NN".
- That's acceptable for the SSTR tables. The demo will open a few cases, though, so give 5–6 safety-critical cases specific stimuli and values: TC-021 occlusion, the air-in-line case, the over-infusion bound, the alarm latch/acknowledge case and the drug-limit case.
- Keep IDs and links unchanged.

**R-014 [non-blocking, by M10] M3 — RTM and gap reports are correct but bare for reviewers** (`src/dhf/cli.py:46-100`, `specs/rules/gaps.yaml`)
- `out/rtm.md` omits the `units` and requirement `revision` data that `rtm.json` already holds. A medical-device RTM should show requirement@rev → component → unit → change → test → latest result. Add `Rev` and `Units` columns, and link every ID to its `source_url`, as `gaps.md` already does.
- `out/gaps.md` is a flat list. Put a per-rule summary table (rule, count, why it matters) at the top. Add a deterministic `action:` string to each rule in `gaps.yaml` (e.g. G05: "Raise or link a defect for the failed result, or record a justified anomaly assessment") and render it.
- These reports appear in the demo and the audit pack, so presentation counts.

Resolved in 29fe7e0: RTM now links all trace IDs and includes Rev/Units; gaps include per-rule counts and YAML-recommended actions.

**R-015 [non-blocking] M3 — `dhf ingest` prints every artifact ID** (`src/dhf/cli.py:20-44`)
- The first ingest prints all 248 IDs. Print counts (added, changed, removed per type) and list changed IDs only, capped at about 20. The full lists can go in a `--verbose` mode or the JSON output.

Resolved in 29fe7e0: normal ingest prints totals and added/changed/removed counts by type, with at most 20 changed IDs; --verbose retains complete lists.

## Resolved

### M3 (tag `m3-done`, eb0f00c) — verdict: **approved**

Verified independently in a clean worktree of `m3-done`:
- 28 tests pass; ruff check and format are clean.
- `dhf ingest --source fixtures`, then `dhf gaps` and `dhf rtm`, ran successfully, producing 16 findings and 35 RTM rows.
- The findings match the answer key exactly (G01–G11): precision = recall = 1.0.
- The rules are declarative (`missing_link`, `match`, `outdated_verification` in `specs/rules/gaps.yaml`), and only `explicit` and `human_confirmed` links count, per BRIEF §4.
- G11 compares the requirement's latest revision time with the last passing result's `completedDate`, using native history rather than metadata. Every finding carries `source_url` and `revision`.
- Presentation follow-ups: R-014 and R-015.

### M2 (tag `m2-done` → cfed7c3) — verdict: **approved**

Verified independently in a clean worktree of the re-tagged `m2-done`:
- 25 tests pass; ruff check and format are clean.
- `test_metadata_stripped_equivalent_graph` removes every `DHF-META` blob from work items, runs and results, re-ingests, and asserts the semantic graph is identical. It also checks that SRS-021's component, the "80 kPa" acceptance criterion and HAZ-01's severity of 5 still come through.
- In `src/`, the metadata blob is read only for the `synthetic` marker (`src/dhf/ingest/native.py:8-16`), as required.

**R-009 [blocking] M1/M2 — The product only worked against our mock, by parsing mock-only metadata.**
- Resolved in b74d84b: native fields and revision history, AreaPath, severity, acceptance criteria, residual-anomaly tags, native result fields, and Related-link types inferred from endpoint types. Unit traces come from `# Implements:` annotations. `verified_revision` is removed.
- *Reviewer verified:* the stripped-metadata equivalence test passes, and `src/` doesn't read the blob beyond the synthetic marker.

**R-010 [blocking] M1 — The synthetic dataset was too thin and unrealistic.**
- Resolved in b74d84b.
- *Reviewer verified, by spot check:*
  - Hazard severities now follow clinical harm (over-infusion, air delivery, alarm unavailable and unintended restart are 5; lost audit evidence is 3), with a scale in `risk_file.md`.
  - SRS-021 has a what/why body and measurable acceptance criteria (80 kPa, 3 s dwell, exact-boundary behaviour).
  - BUG-01 has a description, impact assessment, severity and state.
  - ADR-01 has context, decision and consequences.
  - `sad_v1.md` is now 32 lines.
  - `sensor_pressure.py` has state enums, dataclasses and validation, and carries an `# Implements:` trace header.
  - Follow-up: R-013.

**R-011 [non-blocking] M1 — Mock REST details differed from real ADO.**
- Resolved in b74d84b: `/revisions/N`, `$expand` honoured, public PR shape, 404 for unknown run/PR. All contract-tested.

### M0–M1

**R-001 [blocking] M0 — The cache key could collide and ignored prompt text.**
- Resolved in 9cbfcc0. *Reviewer verified.*

**R-002 [blocking] M0 — Tests read the developer's real `.env` and weren't blocked from the network.**
- Resolved in 9cbfcc0. *Reviewer verified.*

**R-003 [non-blocking] M0 — Anthropic adapter.**
- Resolved in 688a1c3. *Reviewer verified at `m1-done`.*
- *Minor:* `LLM.generate` still defaults `max_output_tokens=1000`. Raise it to about 4000 for Anthropic, because thinking counts toward the cap.

**R-004 [non-blocking] M0 — OpenAI adapter.**
- Resolved in 688a1c3. *Reviewer verified.*

**R-005 [non-blocking] M0 — The ledger only recorded reservations.**
- Resolved in 688a1c3.

**R-006 [non-blocking] M0 — An empty evidence pack blocked real-provider calls.**
- Resolved in 688a1c3.

**R-007 [non-blocking] M0 — PROGRESS.md was stale.**
- Resolved in 9cbfcc0.

**R-008 [non-blocking] M0 — The adapters couldn't see the API keys.**
- Resolved in 4064754. *Reviewer verified.*
