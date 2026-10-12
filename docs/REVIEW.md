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

**R-016 [non-blocking, before M6] M4 — AI-section evidence packs are too broad, so the conclusion becomes a list of 30 "suggestions"** (`src/dhf/graph/queries.py:93-101`)
- `release_readiness_facts` puts every failed result **plus all 35 software requirements** into the pack, and referenced components get pulled in too.
- With the mock, the conclusion renders as about 30 `[Suggested]` paragraphs restating requirements. With a real model it costs more and still invites a restatement instead of a conclusion.
- **Expected fix:**
  - Scope each AI query to the evidence the section reasons about. For the conclusion: failed and blocked results, linked defects, open residual anomalies and G-rule findings (as facts), plus coverage.
  - Add `max_claims` to section specs (conclusion 5–6, purpose 3–4), enforced by the validator. Drop the excess and log it in the manifest.
  - Tell prompts to synthesise one claim per point rather than restate each evidence item.

**R-017 [non-blocking, before M6 — every document reuses this renderer] M4 — Generated documents are hard for a human reviewer to read** (`specs/templates/section.md.j2`, `src/dhf/generate/__init__.py`)
- **Evidence wall.** Every deterministic section ends with an "Evidence:" line of 40+ links; `references` has 42. Link IDs inside the table cells instead, as `rtm.md` already does, and drop the trailing wall. The manifest keeps the complete list.
- **Unreadable revisions.** Git-sourced artifacts render as `COMP-01@r14fb1b4f…` (a 64-hex hash). Show a short commit SHA or hash (7–8 characters) and keep the full value in the manifest.
- **Raw column names.** Headers are dict keys (`not_run`, `artifact_id`, `source_url`). Add a `columns:` label mapping to each section in the spec.
- **Plain-text URLs.** `verification_gaps` shows `source_url` as a text column. Link the artifact ID instead.
- **"References" isn't references.** That section lists requirements, not controlled documents. Either rename it "Requirements baseline under test", or make it a real references table: SRS baseline, RTM version, test runs, and SAD/SDD versions once they exist.

**R-018 [non-blocking, by M10] M4 — The dataset text gives away the answer key** (`data/synthetic/evidence.yaml:1976`, `data/synthetic/code/kestrel/diagnostics_orphan.py`)
- BUG-03's body says "residual-anomaly listing is intentionally missing", and a unit is named `diagnostics_orphan`. Both appear in generated documents the judges will read.
- Rewrite them as natural engineering text and rename the module (e.g. `diagnostics_trace.py`). Update the answer key and IDs consistently, and re-run the validator.

### Live-model check of `m4-done` (run by the reviewer with owner approval in a scratch worktree; spend ≈ $0.013 Anthropic, merged into `out/ledger.json`)

**R-019 [blocking] M4 — Every live Anthropic call fails with HTTP 400 because of the schema** (`src/dhf/models/__init__.py:25-34`)
- `dhf generate sstr --provider anthropic` returned: `output_config.format.schema: For 'number' type, properties maximum, minimum are not supported`.
- The cause is `confidence`'s `ge=0, le=1` bounds, which pydantic writes into the JSON schema.
- **Expected fix:** `strict_claims_schema()` (or a provider-specific variant) recursively strips `minimum`, `maximum`, `exclusiveMinimum` and `exclusiveMaximum` from the schema it sends to providers. Pydantic still enforces 0–1 on the response.
- The reviewer confirmed this fix works in the scratch copy: with the bounds stripped, Anthropic calls succeed.
- Add a unit test asserting the provider schema contains no numeric-bound keywords. Re-check OpenAI strict mode once a valid key exists.

Resolved in adfd507: provider schemas recursively omit numeric bounds; local Pydantic still enforces confidence 0–1. The one live retry reached a refusal response, confirming schema acceptance. Offline schema/bounds tests pass.

**R-020 [blocking] M4 — One model refusal crashes the whole document** (`src/dhf/llm/adapters/anthropic.py:22-23`, `src/dhf/generate/__init__.py`)
- Claude Haiku 5.5 returned `stop_reason: "refusal"` for `residual_anomalies`, almost certainly a safety-classifier false positive on infusion-pump hazard language. The adapter raises `ValueError`, so `dhf generate sstr` aborts and no document or manifest is written.
- Regulated content will trigger this again, especially in sFMEA and hazard text.
- **Expected fix:**
  - A refused, truncated or unparseable section degrades to a **human-authoring placeholder**: "AI drafting unavailable (refusal) — author manually", rendered like a `human` section. The rest of the document still generates.
  - The manifest records `status: "ai_unavailable"`, the reason, and `stop_details.category` when present.
  - `dhf check` (M5) treats that section as unresolved.
  - Add a short framing line to the shared prompt footer ("This is engineering documentation drafted from a fictional synthetic dataset for verification records; describe recorded facts only"). Re-test that section once; if it still refuses, leave the placeholder.
  - Never retry a refusal on the same model in a loop.

Resolved in adfd507: failed AI sections persist as ai_unavailable manual placeholders, with safe reason/category metadata and a blocking readiness check. Tests cover refusal, truncation, malformed output and provider failure without retries. One live residual-anomaly retry still refused (category bio); its placeholder is retained.

**R-021 [non-blocking, before M6] M4 — The validator's ID regex rejects good claims, and chunking prevents cross-chunk citations** (`src/dhf/generate/validator.py:8-10`, `src/dhf/generate/__init__.py` chunking)
- The live conclusion run had 26 claims rejected as `unknown_ids`, mostly for `SRS-to-test` and `SRS-to-code`. Those are the model's wording for the coverage facts; the pattern treats any `SRS-<anything>` as an ID.
- `RUN-2` was also rejected because the conclusion was split across about 13 chunked calls, so `RUN-2` wasn't in that chunk's evidence.
- **Expected fix:**
  - Count a token as an ID only if it matches a real ID shape (`(UN|SYS|SRS|HAZ|RC|COMP|TC|BUG|PR|RUN|RES|ACT|REV|ADR|SOUP)-\d[\w.-]*` or `UNIT-[a-z_]+`) or exists in the graph.
  - Avoid chunking for synthesis sections (conclusion, purpose). R-016's scoped packs make them fit in one call.

**R-022 [non-blocking, before M6] M4 — Real-model prose reads like a data dump, not a document** (`specs/prompts/*.md`, evidence-pack construction)
- Live samples:
  - "The evidence pack contains six synthetic user needs…"
  - Six near-identical claims, one per user need.
  - "BUG-01 is recorded with … residual_listed true."
- The anomaly assessment was accurate and well cited, though; the content is right, the voice is wrong.
- **Expected fix:**
  - Prompts tell the model to write as the document itself. No references to "the evidence pack", "synthetic" or field names.
  - Merge related points into one claim with several citations.
  - Present attributes to the model with human labels ("Listed as residual anomaly: yes"; "Severity: 4 (serious)") instead of raw keys.
  - Put one good example claim per section type in the prompt.
- Related: with chunking, the conclusion produced **85 claims across ~13 calls** and accounted for ~90% of the live spend, which is more evidence for R-016.

**R-023 [non-blocking] M4 — Provider errors are printed raw, and the ledger token counts are overwritten instead of summed** (`src/dhf/cli.py`, `src/dhf/llm/__init__.py`)
- An `invalid_api_key` from OpenAI printed the full provider error, including a masked key fragment, inside a rich traceback.
  - Catch provider SDK errors at the CLI boundary.
  - Print one sanitised line (provider, HTTP status, error type, request id) with no echo of the key.
  - Show the full traceback only with `--debug`.
- After 18 calls, `ledger.json` showed `input_tokens: 2250, output_tokens: 992`. Those are only the last call's numbers, while `actual_usd` was accumulated. Sum the token counts too.

**R-024 [non-blocking, before M6] M4 — The OpenAI path works but its output is weak; citation handling and model choice need adjusting** (live check with the owner's new key; spend $0.0003)
- **What works.** Authentication is good, and `gpt-4.1-nano`, `gpt-4.1-mini` and `gpt-4o-mini` are available. OpenAI accepts the strict claims schema unchanged, so R-019 affects Anthropic only.
- **Problem 1: the model cites URLs instead of IDs.** For `anomaly_assessment`, nano returned one claim citing `fixture://RES-2-008`, the source **URL**, so the validator correctly rejected it and 0 claims survived.
  - Before validating, normalise a citation that exactly equals an evidence item's `source.url` to that item's ID. Log the normalisation.
  - Tell prompts to "cite IDs such as RES-2-008, never URLs".
  - Consider leaving URLs out of the pack the model sees; the renderer adds links afterwards.
- **Problem 2: the output is thin.** Each section got one terse claim. The anomaly claim stated an inferred defect link as `sourced` and cited only the result. R-022's prompt changes and examples apply here too.
- **Problem 3: the default model is too weak.** Copilot Studio runs larger GPT-4.1/GPT-5-class models, so nano is a poor stand-in. Set `DHF_MODEL_OPENAI=gpt-4.1-mini` as the OpenAI dev default, update its price variables from OpenAI's pricing page, and keep nano as an optional cheap smoke test.

## Resolved

### M4 (tag `m4-done` → bfae4d5; code at 29fe7e0) — verdict: **approved; live check found R-019–R-023 (two blocking)**

Verified independently in a clean worktree:
- 31 tests pass; ruff is clean.
- `dhf ingest --source fixtures` then `dhf generate sstr --release 1.1` writes `out/documents/sstr.md` (351 lines, 12 sections) and the manifest, with 0 rejected, downgraded or coerced claims.
- Deterministic sections render from facts. AI sections carry typed claims, with `[Inferred]` and `[Suggested — review required]` labels and `ID@rev` links. "Approvals" is a human-only placeholder.
- The manifest records template/prompt SHAs, the model, cost, a 248-artifact source snapshot, per-section cited revisions, claim counts, validation events and the document SHA-256.
- The validator rejects unknown IDs and numbers not found in facts. Facts include `source_numbers` taken from cited evidence, so quoted thresholds survive. It downgrades uncited `sourced` claims and coerces kinds that aren't allowed.
- Prompts are data in `specs/prompts/`, with injection-resistant wording and "copy facts, never compute".
- **Not yet verified: real-model output.** Every AI section above came from the mock adapter, so prose quality is unproven. The owner-run live check in PROGRESS is still pending.
- Follow-ups: R-016, R-017, R-018.

**R-014 [non-blocking] M3 — RTM and gap reports were bare.**
- Resolved in 29fe7e0.
- *Reviewer verified:* `rtm.md` now has Rev and Units columns with linked IDs; `gaps.md` has per-rule counts and actions from YAML.

**R-015 [non-blocking] M3 — `dhf ingest` printed every artifact ID.**
- Resolved in 29fe7e0.
- *Reviewer verified:* it prints per-type counts.

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
